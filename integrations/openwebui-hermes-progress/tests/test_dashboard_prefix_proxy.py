from __future__ import annotations

import gzip
import importlib.util
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

MODULE_PATH = Path(__file__).parents[1] / "dashboard_prefix_proxy.py"


def load_proxy_module():
    if not MODULE_PATH.exists():
        pytest.fail("dashboard_prefix_proxy.py is not implemented")
    spec = importlib.util.spec_from_file_location("pda_dashboard_prefix_proxy", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_strip_mount_prefix_preserves_path_and_rejects_outside_paths():
    proxy = load_proxy_module()

    assert proxy.strip_mount_prefix("/hermes", "/hermes") == "/"
    assert proxy.strip_mount_prefix("/hermes/", "/hermes") == "/"
    assert proxy.strip_mount_prefix("/hermes/kanban", "/hermes") == "/kanban"

    with pytest.raises(ValueError):
        proxy.strip_mount_prefix("/unrelated", "/hermes")
    with pytest.raises(ValueError):
        proxy.strip_mount_prefix("/hermes-evil", "/hermes")


@pytest.mark.asyncio
async def test_http_proxy_strips_mount_and_sets_forwarded_prefix():
    proxy = load_proxy_module()
    observed = {}

    async def upstream_handler(request):
        observed.update(
            path_qs=request.path_qs,
            prefix=request.headers.get("X-Forwarded-Prefix"),
            proto=request.headers.get("X-Forwarded-Proto"),
            forwarded_host=request.headers.get("X-Forwarded-Host"),
            host=request.headers.get("Host"),
        )
        return web.Response(text="dashboard-ok", headers={"X-Upstream": "yes"})

    upstream_app = web.Application()
    upstream_app.router.add_route("*", "/{path:.*}", upstream_handler)
    upstream_server = TestServer(upstream_app)
    await upstream_server.start_server()

    upstream_origin = str(upstream_server.make_url("/")).rstrip("/")
    proxy_app = proxy.create_app(
        upstream_origin=upstream_origin,
        mount_prefix="/hermes",
        public_scheme="https",
    )
    client = TestClient(TestServer(proxy_app))
    await client.start_server()
    try:
        response = await client.get(
            "/hermes/kanban?board=pda",
            headers={"Host": "pda-web.example.ts.net"},
        )
        assert response.status == 200
        assert await response.text() == "dashboard-ok"
        assert response.headers["X-Upstream"] == "yes"
        assert observed == {
            "path_qs": "/kanban?board=pda",
            "prefix": "/hermes",
            "proto": "https",
            "forwarded_host": "pda-web.example.ts.net",
            "host": urlsplit(upstream_origin).netloc,
        }
    finally:
        await client.close()
        await upstream_server.close()


@pytest.mark.asyncio
async def test_http_proxy_preserves_upstream_gzip_bytes_and_content_encoding():
    proxy = load_proxy_module()
    encoded_body = gzip.compress(b"dashboard compressed")

    async def upstream_handler(_request):
        return web.Response(
            body=encoded_body,
            headers={"Content-Encoding": "gzip"},
            content_type="application/javascript",
        )

    upstream_app = web.Application()
    upstream_app.router.add_get("/asset.js", upstream_handler)
    upstream_server = TestServer(upstream_app)
    await upstream_server.start_server()

    proxy_app = proxy.create_app(
        upstream_origin=str(upstream_server.make_url("/")).rstrip("/"),
        mount_prefix="/hermes",
        public_scheme="https",
    )
    proxy_server = TestServer(proxy_app)
    await proxy_server.start_server()
    try:
        async with aiohttp.ClientSession(auto_decompress=False) as client:
            response = await client.get(str(proxy_server.make_url("/hermes/asset.js")))
            assert response.headers["Content-Encoding"] == "gzip"
            assert await response.read() == encoded_body
    finally:
        await proxy_server.close()
        await upstream_server.close()


@pytest.mark.asyncio
async def test_proxy_drops_set_cookie_headers_outside_the_mount_path():
    proxy = load_proxy_module()

    async def upstream_handler(_request):
        response = web.Response(text="cookies")
        response.headers.add(
            "Set-Cookie",
            "__Secure-hermes_session=safe; Path=/hermes; Secure; HttpOnly",
        )
        response.headers.add(
            "Set-Cookie",
            "root_scoped=unsafe; Path=/; Secure; HttpOnly",
        )
        response.headers.add(
            "Set-Cookie",
            "missing_path=unsafe; Secure; HttpOnly",
        )
        return response

    upstream_app = web.Application()
    upstream_app.router.add_get("/login", upstream_handler)
    upstream_server = TestServer(upstream_app)
    await upstream_server.start_server()

    proxy_app = proxy.create_app(
        upstream_origin=str(upstream_server.make_url("/")).rstrip("/"),
        mount_prefix="/hermes",
        public_scheme="https",
    )
    client = TestClient(TestServer(proxy_app))
    await client.start_server()
    try:
        response = await client.get("/hermes/login")

        assert response.headers.getall("Set-Cookie", []) == [
            "__Secure-hermes_session=safe; Path=/hermes; Secure; HttpOnly"
        ]
    finally:
        await client.close()
        await upstream_server.close()


@pytest.mark.asyncio
async def test_dashboard_asset_rewrites_only_exact_unencoded_logout_target():
    proxy = load_proxy_module()
    javascript = (
        b"window.location.assign(`/login`);\n"
        b"window.location.assign('/login');\n"
    )
    encoded_javascript = gzip.compress(javascript)

    async def upstream_handler(request):
        if request.path == "/assets/encoded.js":
            return web.Response(
                body=encoded_javascript,
                headers={"Content-Encoding": "gzip"},
                content_type="application/javascript",
            )
        return web.Response(body=javascript, content_type="application/javascript")

    upstream_app = web.Application()
    upstream_app.router.add_get("/{path:.*}", upstream_handler)
    upstream_server = TestServer(upstream_app)
    await upstream_server.start_server()

    proxy_app = proxy.create_app(
        upstream_origin=str(upstream_server.make_url("/")).rstrip("/"),
        mount_prefix="/hermes",
        public_scheme="https",
    )
    proxy_server = TestServer(proxy_app)
    await proxy_server.start_server()
    try:
        async with aiohttp.ClientSession(auto_decompress=False) as client:
            response = await client.get(
                str(proxy_server.make_url("/hermes/assets/index.js"))
            )
            assert await response.read() == (
                b"window.location.assign(`/hermes/login`);\n"
                b"window.location.assign('/login');\n"
            )

            response = await client.get(
                str(proxy_server.make_url("/hermes/assets/encoded.js"))
            )
            assert response.headers["Content-Encoding"] == "gzip"
            assert await response.read() == encoded_javascript
    finally:
        await proxy_server.close()
        await upstream_server.close()


@pytest.mark.asyncio
async def test_login_page_keeps_password_auth_and_next_navigation_under_mount():
    proxy = load_proxy_module()

    async def upstream_login(_request):
        return web.Response(
            text="""
            <script>
              fetch('/auth/password-login', {method: 'POST'}).then(function (resp) {
                return resp.json().then(function (data) {
                  window.location.assign((data && data.next) || '/');
                });
              });
            </script>
            """,
            content_type="text/html",
        )

    upstream_app = web.Application()
    upstream_app.router.add_get("/login", upstream_login)
    upstream_server = TestServer(upstream_app)
    await upstream_server.start_server()

    proxy_app = proxy.create_app(
        upstream_origin=str(upstream_server.make_url("/")).rstrip("/"),
        mount_prefix="/hermes",
        public_scheme="https",
    )
    client = TestClient(TestServer(proxy_app))
    await client.start_server()
    try:
        response = await client.get("/hermes/login?next=%2Fkanban")
        body = await response.text()

        assert response.status == 200
        assert "fetch('/hermes/auth/password-login'" in body
        assert "fetch('/auth/password-login'" not in body
        assert "window.location.assign('/hermes' + ((data && data.next) || '/'))" in body
        assert "window.location.assign((data && data.next) || '/')" not in body
    finally:
        await client.close()
        await upstream_server.close()


@pytest.mark.asyncio
async def test_websocket_proxy_keeps_live_kanban_updates_bidirectional():
    proxy = load_proxy_module()
    observed = {}

    async def upstream_websocket(request):
        observed.update(
            path_qs=request.path_qs,
            prefix=request.headers.get("X-Forwarded-Prefix"),
        )
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        await socket.send_str("upstream-ready")
        async for message in socket:
            if message.type == web.WSMsgType.TEXT:
                await socket.send_str(f"echo:{message.data}")
        return socket

    upstream_app = web.Application()
    upstream_app.router.add_get(
        "/api/plugins/kanban/events", upstream_websocket
    )
    upstream_server = TestServer(upstream_app)
    await upstream_server.start_server()

    proxy_app = proxy.create_app(
        upstream_origin=str(upstream_server.make_url("/")).rstrip("/"),
        mount_prefix="/hermes",
        public_scheme="https",
    )
    client = TestClient(TestServer(proxy_app))
    await client.start_server()
    try:
        socket = await client.ws_connect(
            "/hermes/api/plugins/kanban/events?ticket=abc",
            headers={"Host": "pda-web.example.ts.net"},
        )
        assert (await socket.receive()).data == "upstream-ready"
        await socket.send_str("refresh")
        assert (await socket.receive()).data == "echo:refresh"
        await socket.close()
        assert observed == {
            "path_qs": "/api/plugins/kanban/events?ticket=abc",
            "prefix": "/hermes",
        }
    finally:
        await client.close()
        await upstream_server.close()


def test_proxy_rejects_non_loopback_or_ambiguous_network_configuration():
    proxy = load_proxy_module()

    assert (
        proxy.validate_upstream_origin("http://127.0.0.1:9119")
        == "http://127.0.0.1:9119"
    )
    assert proxy.validate_listen_host("127.0.0.1") == "127.0.0.1"

    for origin in (
        "https://127.0.0.1:9119",
        "http://localhost:9119",
        "http://0.0.0.0:9119",
        "http://192.168.0.59:9119",
        "http://127.0.0.1:9119/path",
        "http://user:pass@127.0.0.1:9119",
        "http://127.0.0.1:9119?token=x",
    ):
        with pytest.raises(ValueError):
            proxy.validate_upstream_origin(origin)

    for host in ("0.0.0.0", "localhost", "192.168.0.59", "::"):
        with pytest.raises(ValueError):
            proxy.validate_listen_host(host)


def test_cli_defaults_pin_the_expected_loopback_topology():
    proxy = load_proxy_module()

    args = proxy.parse_args([])

    assert args.listen_host == "127.0.0.1"
    assert args.listen_port == 9121
    assert args.upstream == "http://127.0.0.1:9119"
    assert args.mount_prefix == "/hermes"


def test_systemd_unit_runs_managed_proxy_with_hardened_loopback_contract():
    unit_path = (
        Path(__file__).parents[3]
        / "infra/systemd/pda-kanban-dashboard-proxy.service"
    )
    if not unit_path.exists():
        pytest.fail("pda-kanban-dashboard-proxy.service is not implemented")

    unit = unit_path.read_text(encoding="utf-8")
    assert "After=network-online.target hermes-dashboard.service" in unit
    assert "--listen-host 127.0.0.1" in unit
    assert "--listen-port 9121" in unit
    assert "--upstream http://127.0.0.1:9119" in unit
    assert "--mount-prefix /hermes" in unit
    assert "%h/.local/libexec/pda/dashboard_prefix_proxy.py" in unit
    assert "%h/projects/" not in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "ProtectHome=read-only" in unit


def test_runbook_installs_tracked_proxy_to_the_unit_runtime_path():
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

    assert "integrations/openwebui-hermes-progress/dashboard_prefix_proxy.py" in readme
    assert '"$HOME/.local/libexec/pda/dashboard_prefix_proxy.py"' in readme
    assert "cmp -s" in readme


def test_dashboard_systemd_dropin_closes_kanban_api_to_loopback():
    dropin_path = (
        Path(__file__).parents[3]
        / "infra/systemd/hermes-dashboard.service.d/10-pda-loopback.conf"
    )
    if not dropin_path.exists():
        pytest.fail("Hermes dashboard loopback drop-in is not implemented")

    dropin = dropin_path.read_text(encoding="utf-8")
    assert "ExecStart=\n" in dropin
    assert "%h/.hermes/hermes-agent/venv/bin/hermes dashboard" in dropin
    assert "--host 127.0.0.1" in dropin
    assert "--port 9119" in dropin
    assert "--host 0.0.0.0" not in dropin
