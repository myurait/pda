#!/usr/bin/env python3
"""Prefix-aware reverse proxy for the tailnet-only Hermes dashboard."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Iterable, Sequence
from http.cookies import CookieError, SimpleCookie
from urllib.parse import urlsplit

import aiohttp
from aiohttp import web
from multidict import CIMultiDict

_HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
_UPSTREAM_CLIENT_KEY = web.AppKey("upstream_client", aiohttp.ClientSession)


def validate_listen_host(host: str) -> str:
    """Keep the helper proxy unreachable from LAN and tailnet directly."""
    if host != "127.0.0.1":
        raise ValueError("the dashboard prefix proxy must bind to 127.0.0.1")
    return host


def validate_upstream_origin(origin: str) -> str:
    """Accept only a credential-free loopback HTTP dashboard origin."""
    if any(ord(char) < 32 or ord(char) == 127 for char in origin) or "\\" in origin:
        raise ValueError("invalid control character in upstream origin")
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid upstream origin") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("upstream must be credential-free loopback HTTP with an explicit port")
    return f"http://127.0.0.1:{port}"


def strip_mount_prefix(path: str, prefix: str) -> str:
    """Return the backend path for one exact reverse-proxy mount."""
    normalized_prefix = "/" + prefix.strip("/")
    if path == normalized_prefix or path == normalized_prefix + "/":
        return "/"
    child_prefix = normalized_prefix + "/"
    if not path.startswith(child_prefix):
        raise ValueError("request path is outside the configured mount prefix")
    return path[len(normalized_prefix) :]


def _set_cookie_has_exact_path(value: str, required_path: str) -> bool:
    """Accept one well-formed cookie only when it stays inside the mount."""
    cookies = SimpleCookie()
    try:
        cookies.load(value)
    except CookieError:
        return False
    if len(cookies) != 1:
        return False
    morsel = next(iter(cookies.values()))
    return morsel["path"] == required_path


def _copy_response_headers(
    raw_headers: Iterable[tuple[bytes, bytes]], *, cookie_path: str
) -> CIMultiDict[str]:
    headers: CIMultiDict[str] = CIMultiDict()
    for raw_name, raw_value in raw_headers:
        name = raw_name.decode("latin-1")
        if name.lower() in _HOP_BY_HOP_HEADERS or name.lower() == "content-length":
            continue
        value = raw_value.decode("latin-1")
        if name.lower() == "set-cookie" and not _set_cookie_has_exact_path(
            value, cookie_path
        ):
            continue
        headers.add(name, value)
    return headers


def _rewrite_login_html(body: bytes, prefix: str) -> bytes:
    """Keep the bundled password-login flow inside the public mount."""
    try:
        html = body.decode("utf-8")
    except UnicodeDecodeError:
        return body
    html = html.replace(
        "fetch('/auth/password-login'",
        f"fetch('{prefix}/auth/password-login'",
    )
    html = html.replace(
        "window.location.assign((data && data.next) || '/');",
        f"window.location.assign('{prefix}' + ((data && data.next) || '/'));",
    )
    return html.encode("utf-8")


def _rewrite_dashboard_asset_js(body: bytes, prefix: str) -> bytes:
    """Keep the compiled logout navigation inside the public mount."""
    try:
        javascript = body.decode("utf-8")
    except UnicodeDecodeError:
        return body
    return javascript.replace(
        "window.location.assign(`/login`)",
        f"window.location.assign(`{prefix}/login`)",
    ).encode("utf-8")


def create_app(
    *,
    upstream_origin: str,
    mount_prefix: str = "/hermes",
    public_scheme: str = "https",
) -> web.Application:
    """Create an HTTP reverse proxy that teaches Hermes its public prefix."""
    origin = validate_upstream_origin(upstream_origin)
    upstream_host = urlsplit(origin).netloc
    prefix = "/" + mount_prefix.strip("/")
    app = web.Application()

    async def start_client(application: web.Application) -> None:
        application[_UPSTREAM_CLIENT_KEY] = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            auto_decompress=False,
        )

    async def close_client(application: web.Application) -> None:
        await application[_UPSTREAM_CLIENT_KEY].close()

    async def proxy_http(request: web.Request) -> web.StreamResponse:
        try:
            backend_path = strip_mount_prefix(request.path, prefix)
        except ValueError as exc:
            raise web.HTTPNotFound() from exc

        target = origin + backend_path
        if request.query_string:
            target += "?" + request.query_string

        headers = {
            name: value
            for name, value in request.headers.items()
            if name.lower() not in _HOP_BY_HOP_HEADERS and name.lower() != "content-length"
        }
        public_host = request.headers.get("Host", "")
        headers["Host"] = upstream_host
        if public_host:
            headers["X-Forwarded-Host"] = public_host
        headers["X-Forwarded-Prefix"] = prefix
        headers["X-Forwarded-Proto"] = public_scheme

        client = request.app[_UPSTREAM_CLIENT_KEY]
        if request.headers.get("Upgrade", "").lower() == "websocket":
            websocket_headers = {
                name: value
                for name, value in headers.items()
                if not name.lower().startswith("sec-websocket-")
            }
            upstream_socket = await client.ws_connect(
                target,
                headers=websocket_headers,
                autoping=True,
            )
            downstream_socket = web.WebSocketResponse(autoping=True)
            await downstream_socket.prepare(request)

            async def downstream_to_upstream() -> None:
                async for message in downstream_socket:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        await upstream_socket.send_str(message.data)
                    elif message.type == aiohttp.WSMsgType.BINARY:
                        await upstream_socket.send_bytes(message.data)
                    elif message.type == aiohttp.WSMsgType.ERROR:
                        break

            async def upstream_to_downstream() -> None:
                async for message in upstream_socket:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        await downstream_socket.send_str(message.data)
                    elif message.type == aiohttp.WSMsgType.BINARY:
                        await downstream_socket.send_bytes(message.data)
                    elif message.type == aiohttp.WSMsgType.ERROR:
                        break

            relays = {
                asyncio.create_task(downstream_to_upstream()),
                asyncio.create_task(upstream_to_downstream()),
            }
            try:
                _, pending = await asyncio.wait(
                    relays,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
            finally:
                for task in relays:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*relays, return_exceptions=True)
                await upstream_socket.close()
                if not downstream_socket.closed:
                    await downstream_socket.close()
            return downstream_socket

        async with client.request(
            request.method,
            target,
            headers=headers,
            data=await request.read(),
            allow_redirects=False,
        ) as upstream:
            body = await upstream.read()
            content_type = upstream.headers.get("Content-Type", "")
            if (
                backend_path == "/login"
                and upstream.status == 200
                and content_type.lower().startswith("text/html")
            ):
                body = _rewrite_login_html(body, prefix)
            elif (
                backend_path.startswith("/assets/")
                and backend_path.count("/") == 2
                and backend_path.endswith(".js")
                and content_type.lower().startswith(
                    ("application/javascript", "text/javascript")
                )
                and not upstream.headers.get("Content-Encoding")
            ):
                body = _rewrite_dashboard_asset_js(body, prefix)
            return web.Response(
                status=upstream.status,
                reason=upstream.reason,
                body=body,
                headers=_copy_response_headers(
                    upstream.raw_headers,
                    cookie_path=prefix,
                ),
            )

    app.on_startup.append(start_client)
    app.on_cleanup.append(close_client)
    app.router.add_route("*", "/{path:.*}", proxy_http)
    return app


def _bounded_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _mount_prefix(value: str) -> str:
    normalized = "/" + value.strip("/")
    if normalized != "/hermes":
        raise argparse.ArgumentTypeError("the production mount prefix is fixed to /hermes")
    return normalized


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Loopback-only prefix proxy for the Hermes dashboard",
    )
    parser.add_argument("--listen-host", type=validate_listen_host, default="127.0.0.1")
    parser.add_argument("--listen-port", type=_bounded_port, default=9121)
    parser.add_argument(
        "--upstream",
        type=validate_upstream_origin,
        default="http://127.0.0.1:9119",
    )
    parser.add_argument("--mount-prefix", type=_mount_prefix, default="/hermes")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    web.run_app(
        create_app(
            upstream_origin=args.upstream,
            mount_prefix=args.mount_prefix,
            public_scheme="https",
        ),
        host=args.listen_host,
        port=args.listen_port,
        access_log=None,
        print=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
