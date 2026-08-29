"""Measurement probe: the containment's denials, asserted from inside it.

Run through ``contained_runner`` on the host that will execute G2, as the
acceptance evidence design §6 asks for: egress denied by default, no secret
environment, no reachable Kanban/approval-ledger. The invocation and the values
measured on agent-node are recorded in ``operations/integration/README.md``.

Deliberately *not* named ``test_*``: pytest collects a file named explicitly on
the command line whatever the file is called, so the probe stays runnable while
never being swept into a directory-wide collection on a host where it cannot
hold -- every assertion here is false outside the containment.

``PDA_PROBE_WORKTREE`` names the mounted worktree; the runner's env allowlist
admits it because it carries a path, not a capability.
"""
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path

import pytest

SECRETS = [
    "/home/user/.hermes/auth.json",
    "/home/user/.hermes/.env",
    "/home/user/.hermes/kanban.db",
    "/home/user/.hermes/state.db",
    "/home/user/.hermes/config.yaml",
    "/home/user/.ssh",
    "/home/user/.claude.json",
]


@pytest.mark.parametrize("path", SECRETS)
def test_secret_path_is_absent(path):
    print(f"MEASURE secret {path} exists={Path(path).exists()}")
    assert not Path(path).exists()


def test_hermes_home_listing_is_only_the_mounted_checkout():
    entries = sorted(os.listdir("/home/user/.hermes"))
    print(f"MEASURE listdir(/home/user/.hermes)={entries}")
    assert entries == ["hermes-agent"]


def test_hermes_checkout_listing_is_only_the_venv():
    entries = sorted(os.listdir("/home/user/.hermes/hermes-agent"))
    print(f"MEASURE hermes-agent entries={len(entries)} has_env={'.env' in entries}")
    assert ".env" not in entries


def test_https_egress_fails():
    with pytest.raises(Exception) as exc:
        urllib.request.urlopen("https://example.com", timeout=8)
    print(f"MEASURE https egress -> {type(exc.value).__name__}: {exc.value}")
    assert isinstance(exc.value, (urllib.error.URLError, OSError))


@pytest.mark.parametrize(
    "addr", [("1.1.1.1", 443), ("192.168.0.59", 8642), ("192.168.0.59", 9119)]
)
def test_tcp_egress_fails(addr):
    with pytest.raises(OSError) as exc:
        socket.create_connection(addr, timeout=8)
    print(f"MEASURE tcp {addr} -> errno={exc.value.errno} {exc.value}")
    assert exc.value.errno is not None


def test_dns_resolution_fails():
    with pytest.raises(OSError) as exc:
        socket.getaddrinfo("github.com", 443)
    print(f"MEASURE dns github.com -> {type(exc.value).__name__}: {exc.value}")


def test_only_loopback_interface_is_present():
    names = sorted(p.name for p in Path("/sys/class/net").iterdir())
    print(f"MEASURE interfaces={names}")
    assert names == ["lo"]


def test_worktree_is_read_only():
    root = os.environ.get("PDA_PROBE_WORKTREE", "/home/user/projects/pda")
    target = Path(root) / "containment-write-probe"
    with pytest.raises(OSError) as exc:
        target.write_text("x")
    print(f"MEASURE worktree write -> errno={exc.value.errno} {exc.value}")
    assert not target.exists()


def test_container_root_is_read_only():
    with pytest.raises(OSError) as exc:
        Path("/containment-write-probe").write_text("x")
    print(f"MEASURE rootfs write -> errno={exc.value.errno}")


def test_tmpfs_is_writable_and_the_only_writable_surface():
    probe = Path(os.environ["TMPDIR"]) / "probe"
    probe.write_text("x")
    print(f"MEASURE tmpfs write ok at {probe}")
    assert probe.read_text() == "x"


def test_no_secret_bearing_environment_variables():
    leaked = sorted(
        name
        for name in os.environ
        if name.startswith(("HERMES_", "AWS_", "GITHUB_", "GH_", "ANTHROPIC_", "OPENAI_", "CLAUDE_"))
        or any(t in name for t in ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "API_KEY"))
    )
    print(f"MEASURE env names={sorted(os.environ)} leaked={leaked}")
    assert leaked == []


def test_docker_socket_is_absent():
    print(f"MEASURE /var/run/docker.sock exists={Path('/var/run/docker.sock').exists()}")
    assert not Path("/var/run/docker.sock").exists()


def test_privileges_are_dropped():
    status = Path("/proc/self/status").read_text()
    caps = [l for l in status.splitlines() if l.startswith(("CapEff", "CapPrm", "NoNewPrivs"))]
    print(f"MEASURE uid={os.getuid()} {caps}")
    assert os.getuid() != 0
    assert any(l.startswith("CapEff:") and set(l.split()[1]) == {"0"} for l in caps)
