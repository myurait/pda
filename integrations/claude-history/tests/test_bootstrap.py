"""Exercise the real bootstrap's step 2 in Bash, not a macOS E2E test.

macOS executables are simulated because this test host is Linux. No real sudo,
SSH, settings change, or credential access occurs. Production paths stay fixed.
"""
import os
from pathlib import Path
import subprocess


SOURCE = Path(os.environ.get(
    "PDA_BOOTSTRAP_TEST_SOURCE",
    str(Path(__file__).resolve().parents[1] / "bootstrap-main-reverse-ssh.sh"),
))


def run_remote_login_step(*, initially_open=False, sudo_exit=1,
                          diagnostic="simulated Full Disk Access refusal",
                          opens_after_sudo=False):
    source = SOURCE.read_text()
    helper_start = source.index("say() {")
    helper_end = source.index('\n[ "$(uname -s)"', helper_start)
    step_start = source.index('say 2 "')
    step_end = source.index('say 3 "', step_start)
    step = source[step_start:step_end].replace("/usr/bin/nc", "nc_probe")
    simulation = r'''
port_open="$TEST_PORT_OPEN"
nc_probe() { [ "$port_open" = 1 ]; }
sudo() {
  printf '%s\n' 'SIMULATED_SUDO_CALLED' >&2
  printf '%s\n' "$TEST_DIAGNOSTIC"
  if [ "$TEST_OPENS_AFTER_SUDO" = 1 ]; then port_open=1; fi
  return "$TEST_SUDO_EXIT"
}
sleep() { :; }
'''
    program = (
        "set -euo pipefail\n" + source[helper_start:helper_end]
        + simulation + step + "printf 'STEP_3_REACHED\\n'\n"
    )
    environment = {
        **os.environ,
        "TEST_PORT_OPEN": str(int(initially_open)),
        "TEST_SUDO_EXIT": str(sudo_exit),
        "TEST_DIAGNOSTIC": diagnostic,
        "TEST_OPENS_AFTER_SUDO": str(int(opens_after_sudo)),
    }
    return subprocess.run(
        ["/bin/bash", "-c", program], env=environment,
        text=True, capture_output=True, timeout=5,
    )


def test_systemsetup_stdout_failure_is_visible_and_actionable():
    result = run_remote_login_step(sudo_exit=1)
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "STEP_3_REACHED" not in output
    assert "simulated Full Disk Access refusal" in output
    assert "exit 1" in output
    assert "System Settings > General > Sharing > Remote Login" in output


def test_already_listening_skips_sudo_and_continues():
    result = run_remote_login_step(initially_open=True)
    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "SIMULATED_SUDO_CALLED" not in output
    assert "STEP_3_REACHED" in output


def test_successfully_enabled_listener_continues():
    result = run_remote_login_step(sudo_exit=0, opens_after_sudo=True)
    assert result.returncode == 0
    assert "STEP_3_REACHED" in result.stdout


def test_zero_exit_without_listener_does_not_continue():
    result = run_remote_login_step(sudo_exit=0, diagnostic="")
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "STEP_3_REACHED" not in output
    assert "Remote Login is still unavailable" in output


def test_other_failure_code_is_reported_without_assumed_cause():
    result = run_remote_login_step(sudo_exit=7, diagnostic="other setting failure")
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "other setting failure" in output
    assert "exit 7" in output
    assert "STEP_3_REACHED" not in output
