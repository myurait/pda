"""Real, isolated OpenSSH checks; never touch production keys or listeners.

The test creates disposable host/client keys and an unprivileged loopback sshd.
It exercises the bootstrap's actual key-option assignment, not macOS launchd.
"""
import getpass
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

import pytest

SOURCE = Path(os.environ.get(
    "PDA_BOOTSTRAP_TEST_SOURCE",
    str(Path(__file__).resolve().parents[1] / "bootstrap-main-reverse-ssh.sh"),
))


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_banner(port, process, seconds=4):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), 0.2) as sock:
                sock.settimeout(0.3)
                if sock.recv(256).startswith(b"SSH-2.0-"):
                    return True
        except OSError:
            pass
        time.sleep(0.05)
    return False


@pytest.fixture
def ssh_lab(tmp_path):
    sshd = shutil.which("sshd") or "/usr/sbin/sshd"
    if not Path(sshd).is_file():
        pytest.skip("OpenSSH server binary required for real authentication test")
    for name in ("host", "client"):
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(tmp_path / name)],
                       check=True, capture_output=True, timeout=5)
    port, reverse_port = unused_port(), unused_port()
    assignment = next(line for line in SOURCE.read_text().splitlines()
                      if line.startswith("TUNNEL_AUTH_LINE="))
    line = subprocess.run(
        ["bash", "-c", assignment + '\nprintf "%s\\n" "$TUNNEL_AUTH_LINE"'],
        env={**os.environ, "REVERSE_PORT": str(reverse_port),
             "TUNNEL_PUB": (tmp_path / "client.pub").read_text().strip()},
        check=True, text=True, capture_output=True, timeout=5,
    ).stdout
    authorized = tmp_path / "authorized_keys"
    authorized.write_text(line)
    authorized.chmod(0o600)
    config = tmp_path / "sshd_config"
    config.write_text("\n".join([
        f"Port {port}", "ListenAddress 127.0.0.1",
        f"HostKey {tmp_path / 'host'}", f"PidFile {tmp_path / 'pid'}",
        f"AuthorizedKeysFile {authorized}", "StrictModes no", "UsePAM no",
        "PasswordAuthentication no", "KbdInteractiveAuthentication no",
        "PubkeyAuthentication yes", f"AllowUsers {getpass.getuser()}",
        "AllowTcpForwarding yes", "GatewayPorts no", "LogLevel DEBUG3", "",
    ]))
    known = tmp_path / "known_hosts"
    known.write_text(f"[127.0.0.1]:{port} " + (tmp_path / "host.pub").read_text())
    logpath = tmp_path / "sshd.log"
    with logpath.open("w") as log:
        server = subprocess.Popen([sshd, "-D", "-e", "-f", str(config)],
                                  stdout=log, stderr=log)
        try:
            assert wait_banner(port, server), logpath.read_text()
            args = ["ssh", "-F", "/dev/null", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2",
                    "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
                    "-o", "UpdateHostKeys=no", "-o", f"UserKnownHostsFile={known}",
                    "-i", str(tmp_path / "client"), "-p", str(port), "-l", getpass.getuser()]
            yield args, port, reverse_port, logpath
        finally:
            server.terminate()
            server.wait(timeout=5)


def test_generated_key_authenticates_and_forwards_approved_listener(ssh_lab):
    args, port, reverse_port, logpath = ssh_lab
    client = subprocess.Popen(
        args + ["-NT", "-o", "ExitOnForwardFailure=yes", "-R",
                f"127.0.0.1:{reverse_port}:127.0.0.1:{port}", "127.0.0.1"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        assert wait_banner(reverse_port, client), logpath.read_text()
    finally:
        client.terminate()
        client.communicate(timeout=5)


def test_generated_key_denies_unapproved_remote_port(ssh_lab):
    args, port, reverse_port, logpath = ssh_lab
    denied_port = unused_port()
    assert denied_port != reverse_port
    result = subprocess.run(
        args + ["-NT", "-o", "ExitOnForwardFailure=yes", "-R",
                f"127.0.0.1:{denied_port}:127.0.0.1:{port}", "127.0.0.1"],
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 255, logpath.read_text()
    assert "remote port forwarding failed" in result.stderr
    assert "Permission denied" not in result.stderr


def test_generated_key_denies_direct_tcp_forwarding(ssh_lab):
    args, port, reverse_port, logpath = ssh_lab
    result = subprocess.run(args + ["-W", f"127.0.0.1:{port}", "127.0.0.1"],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 255, logpath.read_text()
    assert "administratively prohibited" in result.stderr
    assert "Permission denied" not in result.stderr


def test_generated_key_forces_false_instead_of_requested_command(ssh_lab):
    args, port, reverse_port, logpath = ssh_lab
    result = subprocess.run(args + ["-T", "127.0.0.1", "printf UNEXPECTED_COMMAND"],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 1, logpath.read_text()
    assert "UNEXPECTED_COMMAND" not in result.stdout
    assert "Permission denied" not in result.stderr
