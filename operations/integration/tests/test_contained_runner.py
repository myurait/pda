"""Input-validation and argv-assembly tests for the containment wrapper.

These run on any host: no docker, no agent-node paths, no network. The parts
that need real containment (a suite passing inside it, egress actually failing,
the secret tree actually absent) are host-dependent measurements and are
recorded in ``operations/integration/README.md`` instead.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "contained_runner.py"
_spec = importlib.util.spec_from_file_location("pda_contained_runner", _MODULE_PATH)
assert _spec and _spec.loader
cr = importlib.util.module_from_spec(_spec)
# Registered before execution: ``dataclasses`` resolves annotations through
# ``sys.modules[cls.__module__]`` and fails on an unregistered module.
sys.modules[_spec.name] = cr
_spec.loader.exec_module(cr)


# --------------------------------------------------------------------------
# Fixtures: a fake worktree and a fake runtime mount holding an interpreter
# --------------------------------------------------------------------------


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    root = tmp_path / "worktree"
    (root / ".git").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text("def test_x():\n    pass\n")
    return root


@pytest.fixture
def runtime(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    (root / "venv" / "bin").mkdir(parents=True)
    interp = root / "venv" / "bin" / "python"
    interp.write_text("#!/bin/sh\n")
    interp.chmod(interp.stat().st_mode | stat.S_IXUSR)
    return root


def make_config(worktree: Path, runtime: Path, **overrides) -> "cr.ContainmentConfig":
    params = {
        "worktree": worktree,
        "interpreter": runtime / "venv" / "bin" / "python",
        "runtime_mounts": (runtime,),
        # A fake home under tmp_path. This exercises the *real* enumeration
        # (``default_secret_paths`` runs over every name it lists) without
        # making the tests depend on the host's own home, which is what the
        # previous ``secret_paths`` override skipped entirely.
        "secret_home": worktree.parent / "fakehome",
        "baseline_ref": "HEAD",
        "uid": 1000,
        "gid": 1000,
        "lock_path": worktree.parent / "runner.lock",
    }
    params.update(overrides)
    return cr.ContainmentConfig(**params)


# --------------------------------------------------------------------------
# Happy path and argv shape
# --------------------------------------------------------------------------


def test_valid_config_produces_no_violations(worktree, runtime):
    config = make_config(worktree, runtime)
    assert cr.validate(config, ["tests"]) == []


def test_argv_carries_every_containment_flag(worktree, runtime):
    config = make_config(worktree, runtime)
    argv = cr.build_argv(config, ["tests"])
    joined = " ".join(argv)
    for flag in (
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=1000:1000",
    ):
        assert flag in argv, flag
    assert any(a.startswith("--tmpfs=/tmp:") for a in argv)
    tmpfs = next(a for a in argv if a.startswith("--tmpfs=/tmp:"))
    for opt in ("nosuid", "nodev", "noexec"):
        assert opt in tmpfs, opt
    assert "--memory=4g" in argv and "--memory-swap=4g" in argv
    assert f"--volume={worktree}:{worktree}:ro" in argv
    assert f"--volume={runtime}:{runtime}:ro" in argv
    assert config.image in argv
    assert "no:cacheprovider" in joined


def test_every_mount_is_read_only(worktree, runtime):
    argv = cr.build_argv(make_config(worktree, runtime), ["tests"])
    volumes = [a for a in argv if a.startswith("--volume=")]
    assert volumes
    for volume in volumes:
        assert volume.endswith(":ro"), volume


def test_no_docker_socket_or_privileged_flags(worktree, runtime):
    argv = cr.build_argv(make_config(worktree, runtime), ["tests"])
    joined = " ".join(argv)
    for forbidden in (
        "docker.sock",
        "--privileged",
        "--cap-add",
        "--network=host",
        "--pid=host",
        "--userns=host",
    ):
        assert forbidden not in joined, forbidden


def test_container_script_has_no_pipeline_so_exit_code_survives(worktree, runtime):
    argv = cr.build_argv(
        make_config(worktree, runtime), ["tests"], report_token=_TOKEN
    )
    script = argv[-1]
    assert "|" not in script.replace("||", "")
    assert "rc=$?" in script
    assert script.rstrip().endswith("exit $rc")
    assert _BEGIN in script and _END in script


def test_collect_mode_asks_for_collection_only_and_no_junit(worktree, runtime):
    argv = cr.build_argv(make_config(worktree, runtime), ["tests"], mode="collect")
    script = argv[-1]
    assert "--collect-only" in script
    assert "--junit-xml" not in script


def test_targets_are_passed_as_resolved_paths_inside_the_worktree(worktree, runtime):
    argv = cr.build_argv(make_config(worktree, runtime), ["tests"])
    script = argv[-1]
    assert str((worktree / "tests").resolve()) in script


# --------------------------------------------------------------------------
# Environment allowlist
# --------------------------------------------------------------------------


def test_host_environment_is_not_inherited(worktree, runtime, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_DB", "/home/user/.hermes/kanban.db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-never-appear")
    argv = cr.build_argv(make_config(worktree, runtime), ["tests"])
    joined = " ".join(argv)
    assert "sk-should-never-appear" not in joined
    assert "HERMES_KANBAN_DB" not in joined
    env_args = [a for a in argv if a.startswith("--env=")]
    names = {a[len("--env="):].split("=", 1)[0] for a in env_args}
    assert names == set(cr.base_env(make_config(worktree, runtime)))


def test_base_env_points_home_and_tmpdir_at_the_tmpfs(worktree, runtime):
    env = cr.base_env(make_config(worktree, runtime))
    assert env["HOME"].startswith("/tmp/")
    assert env["TMPDIR"].startswith("/tmp/")
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"


@pytest.mark.parametrize(
    "name",
    [
        "HERMES_KANBAN_DB",
        "HERMES_HOME",
        "GITHUB_TOKEN",
        "AWS_ACCESS_KEY_ID",
        "ANTHROPIC_API_KEY",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "MY_SECRET_VALUE",
        "SOME_PASSWORD",
        "A_CREDENTIAL",
        "HOME",
        "PATH",
        "lowercase",
    ],
)
def test_denied_env_names_are_refused(worktree, runtime, name):
    config = make_config(worktree, runtime, extra_env={name: "x"})
    violations = cr.validate(config)
    assert violations, name
    with pytest.raises(cr.ContainmentError):
        cr.build_argv(config, ["tests"])


def test_allowed_extra_env_reaches_the_argv(worktree, runtime):
    config = make_config(worktree, runtime, extra_env={"PDA_GATE_ID": "g2"})
    argv = cr.build_argv(config, ["tests"])
    assert "--env=PDA_GATE_ID=g2" in argv


def test_multiline_env_value_is_refused(worktree, runtime):
    config = make_config(worktree, runtime, extra_env={"PDA_X": "a\nb"})
    assert cr.validate(config)


# --------------------------------------------------------------------------
# Deny-set: secrets and control plane
# --------------------------------------------------------------------------


def test_mount_that_contains_a_denied_path_is_refused(tmp_path, worktree, runtime):
    """A mount of ``~/.hermes`` must be refused because ``auth.json`` is inside
    it, while ``~/.hermes/hermes-agent`` stays allowed."""
    hermes = tmp_path / "hermes"
    (hermes / "hermes-agent" / "venv" / "bin").mkdir(parents=True)
    interp = hermes / "hermes-agent" / "venv" / "bin" / "python"
    interp.write_text("#!/bin/sh\n")
    auth = hermes / "auth.json"
    auth.write_text("{}")

    denied = make_config(
        worktree,
        runtime,
        runtime_mounts=(hermes,),
        interpreter=interp,
        extra_secret_paths=(auth,),
    )
    violations = cr.validate(denied, ["tests"])
    assert any("contains denied path" in v for v in violations), violations

    allowed = make_config(
        worktree,
        runtime,
        runtime_mounts=(hermes / "hermes-agent",),
        interpreter=interp,
        extra_secret_paths=(auth,),
    )
    assert cr.validate(allowed, ["tests"]) == []


def test_mount_inside_a_denied_path_is_refused(tmp_path, worktree, runtime):
    secret_dir = tmp_path / "ssh"
    (secret_dir / "sub").mkdir(parents=True)
    config = make_config(
        worktree,
        runtime,
        runtime_mounts=(runtime, secret_dir / "sub"),
        extra_secret_paths=(secret_dir,),
    )
    violations = cr.validate(config, ["tests"])
    assert any("is inside denied path" in v for v in violations), violations


def test_worktree_pointing_at_a_denied_path_is_refused(tmp_path, runtime):
    secret_dir = tmp_path / "dot-hermes"
    secret_dir.mkdir()
    (secret_dir / ".git").mkdir()
    config = make_config(secret_dir, runtime, extra_secret_paths=(secret_dir,))
    violations = cr.validate(config)
    assert any("denied path" in v for v in violations), violations


def test_symlinked_worktree_is_mounted_from_its_realpath(tmp_path, worktree, runtime):
    """Symlink realisation: a link is never what gets mounted, its target is.
    This is what stops a link from redirecting the mount after validation."""
    link = tmp_path / "link-to-worktree"
    link.symlink_to(worktree)
    argv = cr.build_argv(make_config(link, runtime), ["tests"])
    assert f"--volume={worktree.resolve()}:{worktree.resolve()}:ro" in argv
    assert str(link) not in " ".join(argv)


def test_symlinked_worktree_aimed_at_a_secret_is_refused(tmp_path, runtime):
    secret_dir = tmp_path / "secret-home"
    (secret_dir / ".git").mkdir(parents=True)
    link = tmp_path / "innocent-looking"
    link.symlink_to(secret_dir)
    config = make_config(link, runtime, extra_secret_paths=(secret_dir,))
    violations = cr.validate(config)
    assert any("denied path" in v for v in violations), violations


def test_secret_shaped_file_inside_a_mount_is_refused(worktree, runtime):
    (runtime / ".env").write_text("API_SERVER_KEY=live\n")
    violations = cr.validate(make_config(worktree, runtime), ["tests"])
    assert any("secret-shaped file" in v for v in violations), violations


def test_env_templates_are_not_treated_as_secrets(worktree, runtime):
    (runtime / ".env.example").write_text("API_SERVER_KEY=\n")
    (runtime / ".envrc").write_text("use flake\n")
    assert cr.validate(make_config(worktree, runtime), ["tests"]) == []


# --------------------------------------------------------------------------
# Mount surface
# --------------------------------------------------------------------------


def test_only_the_declared_mounts_appear(worktree, runtime):
    argv = cr.build_argv(make_config(worktree, runtime), ["tests"])
    volumes = [a[len("--volume="):].split(":")[0] for a in argv if a.startswith("--volume=")]
    assert sorted(volumes) == sorted([str(worktree.resolve()), str(runtime.resolve())])


def test_runtime_mount_overlapping_the_worktree_is_refused(worktree, runtime):
    nested = worktree / "nested-runtime"
    (nested / "venv" / "bin").mkdir(parents=True)
    interp = nested / "venv" / "bin" / "python"
    interp.write_text("#!/bin/sh\n")
    config = make_config(worktree, runtime, runtime_mounts=(nested,), interpreter=interp)
    violations = cr.validate(config, ["tests"])
    assert any("overlaps the worktree" in v for v in violations), violations


def test_interpreter_outside_every_runtime_mount_is_refused(tmp_path, worktree, runtime):
    stray = tmp_path / "stray-python"
    stray.write_text("#!/bin/sh\n")
    config = make_config(worktree, runtime, interpreter=stray)
    violations = cr.validate(config, ["tests"])
    assert any("not inside any runtime mount" in v for v in violations), violations


def test_missing_runtime_mount_is_refused(tmp_path, worktree, runtime):
    config = make_config(worktree, runtime, runtime_mounts=(runtime, tmp_path / "gone"))
    violations = cr.validate(config, ["tests"])
    assert any("does not exist" in v for v in violations), violations


def test_alias_mount_target_keeps_the_declared_spelling(tmp_path, worktree, runtime):
    """``pyvenv.cfg`` names the interpreter through an unversioned symlink, so
    the declared path must survive as the mount *target* while the mount
    *source* is the realised directory."""
    alias = tmp_path / "cpython-alias"
    alias.symlink_to(runtime)
    config = make_config(worktree, runtime, runtime_mounts=(runtime, alias))
    argv = cr.build_argv(config, ["tests"])
    assert f"--volume={runtime.resolve()}:{alias}:ro" in argv


# --------------------------------------------------------------------------
# Worktree shape
# --------------------------------------------------------------------------


def test_gitfile_worktree_is_refused_fail_closed(tmp_path, runtime):
    root = tmp_path / "linked-worktree"
    root.mkdir()
    (root / ".git").write_text("gitdir: /elsewhere/.git/worktrees/wt\n")
    config = make_config(root, runtime)
    violations = cr.validate(config)
    assert any("gitfile" in v for v in violations), violations


def test_missing_worktree_is_refused(tmp_path, runtime):
    config = make_config(tmp_path / "absent", runtime)
    violations = cr.validate(config)
    assert any("not an existing directory" in v for v in violations), violations


# --------------------------------------------------------------------------
# Target and argument validation
# --------------------------------------------------------------------------


def test_target_outside_the_worktree_is_refused(tmp_path, worktree, runtime):
    outside = tmp_path / "outside"
    outside.mkdir()
    violations = cr.validate(make_config(worktree, runtime), [str(outside)])
    assert any("resolves outside the worktree" in v for v in violations), violations


def test_traversal_target_is_refused(worktree, runtime):
    violations = cr.validate(make_config(worktree, runtime), ["../escape"])
    assert violations


def test_missing_target_is_refused(worktree, runtime):
    violations = cr.validate(make_config(worktree, runtime), ["tests/nope"])
    assert any("does not exist" in v for v in violations), violations


@pytest.mark.parametrize(
    "arg",
    [
        "-p",
        "-p=evil",
        "--plugins=evil",
        "-c",
        "--config-file=/tmp/pytest.ini",
        "--rootdir=/",
        "--confcutdir=/",
        "--junit-xml=/tmp/other.xml",
        "--junitxml=/tmp/other.xml",
        "--basetemp=/etc",
        "-o",
        "-o=python_files=*.py",
        "--override-ini=addopts=-p evil",
        "-q",
        "--quiet",
        "../escape",
    ],
)
def test_reserved_or_traversing_pytest_args_are_refused(worktree, runtime, arg):
    violations = cr.validate(make_config(worktree, runtime), ["tests"], [arg])
    assert violations, arg


def test_ordinary_pytest_args_are_accepted(worktree, runtime):
    config = make_config(worktree, runtime)
    assert cr.validate(config, ["tests"], ["-x", "-v", "--maxfail=1", "-s"]) == []
    argv = cr.build_argv(config, ["tests"], ["-x"])
    assert "-x" in argv[-1]


# --------------------------------------------------------------------------
# Image pinning
# --------------------------------------------------------------------------


def test_default_image_is_digest_pinned():
    assert cr._IMAGE_RE.match(cr.DEFAULT_IMAGE)
    assert "@sha256:" in cr.DEFAULT_IMAGE


@pytest.mark.parametrize(
    "image",
    ["python:3.11-bookworm", "python:latest", "python@sha256:abc", "python"],
)
def test_unpinned_image_is_refused(worktree, runtime, image):
    violations = cr.validate(make_config(worktree, runtime, image=image), ["tests"])
    assert any("pinned by digest" in v for v in violations), violations


def test_build_argv_raises_with_all_violations_listed(worktree, runtime):
    config = make_config(worktree, runtime, image="python:latest", extra_env={"GH_TOKEN": "x"})
    with pytest.raises(cr.ContainmentError) as excinfo:
        cr.build_argv(config, ["tests"])
    assert len(excinfo.value.violations) >= 2


def test_unknown_mode_is_refused(worktree, runtime):
    with pytest.raises(cr.ContainmentError):
        cr.build_argv(make_config(worktree, runtime), ["tests"], mode="sudo")


# --------------------------------------------------------------------------
# Result interpretation (G2 judgement inputs)
# --------------------------------------------------------------------------


_TOKEN = "0123456789abcdef0123456789abcdef"
_BEGIN, _END = cr.junit_markers(_TOKEN)


def _junit(tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" '
        f'errors="{errors}" failures="{failures}" skipped="{skipped}" tests="{tests}" '
        'time="1.0"></testsuite></testsuites>'
    )


def _stdout(collected: int, junit: str | None, tail: str = "") -> str:
    out = f"collected {collected} items\n{tail}\n"
    if junit is not None:
        out += f"\n{_BEGIN}\n{junit}\n{_END}\n"
    return out


def _interpret(exit_code: int, stdout: str, mode: str = "run") -> "cr.ContainedResult":
    return cr.interpret(
        exit_code,
        stdout,
        "",
        mode=mode,
        duration_s=1.0,
        image=cr.DEFAULT_IMAGE,
        report_token=_TOKEN,
    )


def test_green_run_reports_pass_with_both_counts():
    result = _interpret(0, _stdout(707, _junit(707)))
    assert result.verdict == "pass"
    assert result.collected == 707
    assert result.executed == 707
    assert result.failures == 0 and result.errors == 0


def test_skips_are_excluded_from_the_executed_count():
    result = _interpret(0, _stdout(10, _junit(10, skipped=3)))
    assert result.collected == 10
    assert result.executed == 7
    assert result.skipped == 3


def test_failing_run_reports_fail():
    result = _interpret(1, _stdout(707, _junit(707, failures=1)))
    assert result.verdict == "fail"
    assert result.failures == 1
    assert result.executed == 707


def test_zero_collected_is_an_infrastructure_fault_not_a_pass():
    result = _interpret(5, _stdout(0, _junit(0)))
    assert result.verdict == "infra_error"
    assert "zero tests collected" in " ".join(result.reasons)


def test_collection_error_exit_code_is_an_infrastructure_fault():
    for code in (2, 3, 4):
        result = _interpret(code, _stdout(707, _junit(707)))
        assert result.verdict == "infra_error", code


def test_oom_kill_is_an_infrastructure_fault():
    result = _interpret(137, "collected 707 items\n")
    assert result.verdict == "infra_error"
    joined = " ".join(result.reasons)
    assert "OOM" in joined


def test_missing_collected_line_is_an_infrastructure_fault():
    result = _interpret(0, f"\n{_BEGIN}\n{_junit(1)}\n{_END}\n")
    assert result.verdict == "infra_error"
    assert "collected count not reported" in " ".join(result.reasons)


def test_missing_junit_report_is_an_infrastructure_fault():
    result = _interpret(0, "collected 707 items\n707 passed\n")
    assert result.verdict == "infra_error"
    assert "junit report missing or unparseable" in " ".join(result.reasons)


def test_unparseable_junit_report_is_an_infrastructure_fault():
    result = _interpret(0, _stdout(707, "<not xml"))
    assert result.verdict == "infra_error"


def test_exit_code_disagreeing_with_junit_is_an_infrastructure_fault():
    result = _interpret(0, _stdout(707, _junit(707, failures=2)))
    assert result.verdict == "infra_error"
    assert "disagrees" in " ".join(result.reasons)


def test_zero_executed_with_nonzero_collected_is_an_infrastructure_fault():
    result = _interpret(0, _stdout(5, _junit(5, skipped=5)))
    assert result.verdict == "infra_error"
    assert "zero tests executed" in " ".join(result.reasons)


def test_collect_mode_reports_collected_only():
    result = _interpret(0, "707 tests collected in 1.2s\n", mode="collect")
    assert result.verdict == "pass"
    assert result.collected == 707
    assert result.executed == 0


def test_collect_mode_with_no_tests_is_an_infrastructure_fault():
    result = _interpret(5, "no tests ran in 0.1s\n", mode="collect")
    assert result.verdict == "infra_error"


def test_result_dict_omits_output_unless_asked():
    result = _interpret(0, _stdout(1, _junit(1)))
    result.stdout = "secret-looking output"
    data = result.to_dict()
    assert "stdout" not in data and "argv" not in data
    assert set(data) >= {"verdict", "exit_code", "collected", "executed"}
    assert "stdout" in result.to_dict(include_output=True)
    json.dumps(data)


# --------------------------------------------------------------------------
# Static collection check
# --------------------------------------------------------------------------


def _git(worktree: Path, *args: str) -> None:
    import subprocess

    subprocess.run(
        ["git", "-C", str(worktree), *args],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(worktree)},
    )


@pytest.fixture
def git_worktree(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_a.py").write_text("def test_a():\n    pass\n")
    (root / "conftest.py").write_text("")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def test_static_check_is_clean_on_a_tracked_tree(git_worktree, runtime):
    config = make_config(git_worktree, runtime)
    assert cr.collection_static_check(config, ["tests"]) == []


def test_untracked_conftest_in_a_collection_root_is_flagged(git_worktree, runtime):
    (git_worktree / "tests" / "conftest.py").write_text("# brought in\n")
    config = make_config(git_worktree, runtime)
    findings = cr.collection_static_check(config, ["tests"])
    assert any("untracked collection config" in f for f in findings), findings


def test_untracked_pytest_ini_is_flagged(git_worktree, runtime):
    (git_worktree / "tests" / "pytest.ini").write_text("[pytest]\n")
    config = make_config(git_worktree, runtime)
    findings = cr.collection_static_check(config, ["tests"])
    assert findings


def test_untracked_config_outside_the_collection_root_is_not_flagged(
    git_worktree, runtime
):
    (git_worktree / "elsewhere").mkdir()
    (git_worktree / "elsewhere" / "conftest.py").write_text("")
    config = make_config(git_worktree, runtime)
    assert cr.collection_static_check(config, ["tests"]) == []


def test_tracked_conftest_modified_against_the_baseline_is_flagged(git_worktree, runtime):
    """A collection config the card changes is a finding even when it is tracked.

    Checking untracked files only made this check close to vacuous: a card is
    submitted as commits, so the ordinary submission form produced no finding.
    """
    (git_worktree / "conftest.py").write_text("# worker edit\n")
    config = make_config(git_worktree, runtime)
    findings = cr.collection_static_check(config, ["."])
    assert any("collection config changed against" in f for f in findings), findings


def test_symlink_leaving_the_worktree_is_flagged(git_worktree, runtime, tmp_path):
    (git_worktree / "tests" / "outside").symlink_to(tmp_path)
    config = make_config(git_worktree, runtime)
    findings = cr.collection_static_check(config, ["tests"])
    assert any("symlink leaving the worktree" in f for f in findings), findings


def test_symlink_inside_the_worktree_is_not_flagged(git_worktree, runtime):
    (git_worktree / "tests" / "inside").symlink_to(git_worktree / "conftest.py")
    config = make_config(git_worktree, runtime)
    assert cr.collection_static_check(config, ["tests"]) == []


# --------------------------------------------------------------------------
# Host-side preconditions
# --------------------------------------------------------------------------


def test_run_refuses_before_docker_when_memory_is_below_the_floor(
    git_worktree, runtime, monkeypatch
):
    monkeypatch.setattr(cr, "available_memory_mb", lambda: 128)
    monkeypatch.setattr(cr, "verify_image_present", lambda config: [])
    monkeypatch.setattr(cr, "collection_static_check", lambda config, targets: [])

    def explode(*args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("docker was invoked despite the memory floor")

    monkeypatch.setattr(cr.subprocess, "run", explode)
    config = make_config(git_worktree, runtime, min_free_mem_mb=4096)
    result = cr.run(config, ["tests"])
    assert result.verdict == "infra_error"
    assert any("below the" in r for r in result.reasons)


def test_run_refuses_when_the_pinned_image_is_absent(
    git_worktree, runtime, monkeypatch
):
    monkeypatch.setattr(cr, "available_memory_mb", lambda: 999999)
    monkeypatch.setattr(cr, "collection_static_check", lambda config, targets: [])
    monkeypatch.setattr(
        cr, "verify_image_present", lambda config: ["pinned image is not present"]
    )
    monkeypatch.setattr(
        cr.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("docker was invoked without the pinned image")
        ),
    )
    config = make_config(git_worktree, runtime)
    result = cr.run(config, ["tests"])
    assert result.verdict == "infra_error"


def test_run_refuses_when_the_static_check_finds_a_brought_in_config(
    git_worktree, runtime, monkeypatch
):
    (git_worktree / "tests" / "conftest.py").write_text("# brought in\n")
    monkeypatch.setattr(cr, "available_memory_mb", lambda: 999999)
    monkeypatch.setattr(cr, "verify_image_present", lambda config: [])
    config = make_config(git_worktree, runtime)
    result = cr.run(config, ["tests"])
    assert result.verdict == "infra_error"
    assert any("untracked collection config" in r for r in result.reasons)


def test_serial_lock_refuses_a_second_holder(tmp_path):
    lock = tmp_path / "runner.lock"
    with cr._SerialLock(lock):
        with pytest.raises(cr.ContainmentError):
            with cr._SerialLock(lock):
                pass


def test_agent_node_config_denies_the_hermes_home_itself():
    """The agent-node preset must mount the hermes *checkout*, never its parent:
    the parent holds ``auth.json``, ``.env`` and the Kanban DB that carries the
    ``pda_owner_approvals`` ledger."""
    mounts = cr.ContainmentConfig.for_agent_node("/home/user/projects/pda").runtime_mounts
    assert cr.AGENT_NODE_HERMES_CHECKOUT in mounts
    assert Path("/home/user/.hermes") not in mounts
    secrets = cr.default_secret_paths(Path("/home/user"))
    assert Path("/home/user/.hermes/auth.json") in secrets
    assert Path("/home/user/.hermes/.env") in secrets
    assert Path("/home/user/.hermes/kanban.db") in secrets


def test_cli_print_argv_does_not_execute_docker(git_worktree, runtime, capsys):
    rc = cr.main(
        [
            "--worktree",
            str(git_worktree),
            "--target",
            "tests",
            "--interpreter",
            str(runtime / "venv" / "bin" / "python"),
            "--runtime-mount",
            str(runtime),
            "--print-argv",
        ]
    )
    assert rc == 0
    argv = json.loads(capsys.readouterr().out)
    assert "--network=none" in argv


def test_cli_reports_refusal_as_json(git_worktree, runtime, capsys):
    rc = cr.main(
        [
            "--worktree",
            str(git_worktree),
            "--target",
            "/etc",
            "--interpreter",
            str(runtime / "venv" / "bin" / "python"),
            "--runtime-mount",
            str(runtime),
            "--print-argv",
        ]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "refused"
    assert payload["reasons"]


def test_cli_env_entry_is_validated_by_the_allowlist(git_worktree, runtime, capsys):
    base = [
        "--worktree",
        str(git_worktree),
        "--target",
        "tests",
        "--interpreter",
        str(runtime / "venv" / "bin" / "python"),
        "--runtime-mount",
        str(runtime),
        "--print-argv",
    ]
    assert cr.main(base + ["--env", "PDA_PROBE_WORKTREE=/w"]) == 0
    argv = json.loads(capsys.readouterr().out)
    assert "--env=PDA_PROBE_WORKTREE=/w" in argv

    assert cr.main(base + ["--env", "GITHUB_TOKEN=x"]) == 2
    assert json.loads(capsys.readouterr().out)["verdict"] == "refused"

    assert cr.main(base + ["--env", "NOEQUALS"]) == 2
    assert json.loads(capsys.readouterr().out)["verdict"] == "refused"


def test_probe_asset_is_not_named_like_a_collectable_test():
    """The probe must stay out of directory-wide collection: its assertions are
    false anywhere but inside the containment."""
    probe = _MODULE_PATH.parent / "probe" / "containment_probe.py"
    assert probe.is_file()
    assert not probe.name.startswith("test_")
    assert not probe.name.endswith("_test.py")


def test_serial_lock_is_on_by_default(tmp_path):
    """Design §6 makes contained runs serial, so the lock is not opt-in."""
    config = cr.ContainmentConfig(
        worktree=tmp_path,
        interpreter=tmp_path / "python",
        runtime_mounts=(),
    )
    assert config.lock_path is not None
    assert config.lock_path.name == "pda-contained-runner.lock"


# --------------------------------------------------------------------------
# Judgement-output integrity (review 2026-08-29, B1)
#
# The residual is stated in the module docstring and is not closed here: a
# payload that writes a self-consistent junit report and exits 0 is believed,
# because pytest is the payload's own process. What these tests pin is that a
# forgery is no longer *silent* -- the previous parse took the first marker pair
# and the genuine report was printed last, so a clean block printed during
# collection simply won.
# --------------------------------------------------------------------------


def test_forged_junit_block_printed_before_the_real_one_is_refused():
    """The published repro: a clean block first, the real failing one after."""
    stdout = (
        "collected 707 items\n"
        f"{_BEGIN}\n{_junit(707, failures=0)}\n{_END}\n"
        "=== 3 failed, 704 passed ===\n"
        f"{_BEGIN}\n{_junit(707, failures=3)}\n{_END}\n"
    )
    result = _interpret(0, stdout)
    assert result.verdict == "infra_error"
    assert any("junit begin" in r for r in result.reasons), result.reasons
    assert result.failures != 0 or result.verdict != "pass"


def test_a_second_junit_block_after_the_real_one_is_also_refused():
    stdout = (
        "collected 5 items\n"
        f"{_BEGIN}\n{_junit(5, failures=2)}\n{_END}\n"
        f"{_BEGIN}\n{_junit(5)}\n{_END}\n"
    )
    assert _interpret(0, stdout).verdict == "infra_error"


def test_junit_total_above_the_collected_count_is_refused():
    result = _interpret(0, _stdout(3, _junit(700)))
    assert result.verdict == "infra_error"
    assert any("cannot both be true" in r for r in result.reasons), result.reasons


def test_deselection_keeps_the_junit_total_below_collected_without_a_fault():
    """``-k``/``--deselect`` legitimately run fewer tests than were collected."""
    result = _interpret(0, _stdout(707, _junit(7), tail="700 deselected"))
    assert result.verdict == "pass"
    assert result.collected == 707 and result.executed == 7


def test_conflicting_collected_counts_are_refused():
    stdout = (
        "collected 5 items\ncollected 707 items\n"
        f"{_BEGIN}\n{_junit(5)}\n{_END}\n"
    )
    result = _interpret(0, stdout)
    assert result.verdict == "infra_error"
    assert any("conflicting collected counts" in r for r in result.reasons)


def test_report_markers_are_per_run_not_a_compile_time_constant(worktree, runtime):
    config = make_config(worktree, runtime)
    first = cr.build_argv(config, ["tests"])[-1]
    second = cr.build_argv(config, ["tests"])[-1]
    assert first != second
    # The pre-fix constant must not appear: it was known to the code being judged.
    for script in (first, second):
        assert "<<<PDA-CONTAINED-JUNIT-BEGIN>>>" not in script
        assert "/tmp/pda-contained-junit.xml" not in script


def test_a_block_carrying_another_runs_token_is_not_read():
    other_begin, other_end = cr.junit_markers("f" * 32)
    stdout = f"collected 5 items\n{other_begin}\n{_junit(5)}\n{other_end}\n"
    result = _interpret(0, stdout)
    assert result.verdict == "infra_error"
    assert "junit report missing or unparseable" in " ".join(result.reasons)


def test_junit_report_path_carries_the_token(worktree, runtime):
    script = cr.build_argv(
        make_config(worktree, runtime), ["tests"], report_token=_TOKEN
    )[-1]
    assert cr.junit_path(_TOKEN) in script


# --------------------------------------------------------------------------
# Deny-set base (review 2026-08-29, B2 and M4)
# --------------------------------------------------------------------------


def test_deny_set_does_not_follow_the_environment_home(monkeypatch, tmp_path):
    """``$HOME`` must not move the enumeration.

    The base used to be ``Path.home()``, so a separate principal's home -- or a
    caller setting ``$HOME`` -- silently emptied the guarantee: no denial was
    emitted, so nothing looked wrong.
    """
    config = cr.ContainmentConfig(
        worktree=tmp_path,
        interpreter=tmp_path / "python",
        runtime_mounts=(),
        secret_home=Path("/home/user"),
        baseline_ref="HEAD",
        uid=1000,
        gid=1000,
    )
    monkeypatch.setenv("HOME", "/tmp/nowhere")
    denied = config.effective_secret_paths()
    # Compared resolved, which is how ``validate`` compares them: some hosts
    # reach ``/home`` through a link.
    assert cr._resolve("/home/user/.hermes/kanban.db") in denied
    assert cr._resolve("/home/user/.hermes/auth.json") in denied
    assert cr._resolve("/tmp/nowhere/.hermes/kanban.db") not in denied
    assert cr._resolve("/tmp/nowhere/.ssh") not in denied


def test_unset_secret_home_is_refused(worktree, runtime):
    config = make_config(worktree, runtime, secret_home=None)
    violations = cr.validate(config, ["tests"])
    assert any("secret_home is unset" in v for v in violations), violations


def test_relative_secret_home_is_refused(worktree, runtime):
    config = make_config(worktree, runtime, secret_home=Path("relative/home"))
    violations = cr.validate(config, ["tests"])
    assert any("secret_home must be an absolute path" in v for v in violations)


def test_deny_set_also_covers_the_invoking_user_real_home(worktree, runtime):
    """A misconfigured ``secret_home`` must not expose the runner's own home."""
    real = cr.invoking_user_home()
    assert real is not None
    denied = make_config(worktree, runtime).effective_secret_paths()
    assert real / ".ssh" in denied


def test_control_plane_file_mounted_on_its_own_is_refused(worktree, runtime, tmp_path):
    """``--runtime-mount .../kanban.db``: the published B2 vector.

    Two independent refusals now cover it -- the enumeration, whose base no
    longer drifts, and the structural rule that a mount source is a directory.
    The bounded secret sweep never saw this case: it scandirs its argument, so a
    file raised and yielded zero findings.
    """
    home = worktree.parent / "fakehome"
    (home / ".hermes").mkdir(parents=True, exist_ok=True)
    kanban = home / ".hermes" / "kanban.db"
    kanban.write_bytes(b"SQLite format 3\x00")
    config = make_config(worktree, runtime, runtime_mounts=(runtime, kanban))
    violations = cr.validate(config, ["tests"])
    assert violations
    assert any(str(kanban) in v for v in violations), violations
    # And the enumeration covers it independently of that structural refusal.
    assert cr._resolve(kanban) in config.effective_secret_paths()


def test_any_file_as_a_runtime_mount_is_refused(worktree, runtime, tmp_path):
    stray = tmp_path / "not-a-tree.db"
    stray.write_bytes(b"x")
    config = make_config(worktree, runtime, runtime_mounts=(runtime, stray))
    violations = cr.validate(config, ["tests"])
    assert any("not a directory" in v for v in violations), violations


def test_extra_secret_paths_cannot_shrink_the_deny_set(worktree, runtime):
    """It is additive. As ``secret_paths`` it replaced the enumeration, so an
    empty tuple left every mount allowed."""
    base = make_config(worktree, runtime).effective_secret_paths()
    emptied = make_config(worktree, runtime, extra_secret_paths=()).effective_secret_paths()
    assert set(base) == set(emptied)
    assert len(emptied) >= len(cr.default_secret_paths(Path("/home/user")))
    widened = make_config(
        worktree, runtime, extra_secret_paths=(worktree.parent / "extra",)
    ).effective_secret_paths()
    assert set(base) < set(widened)


def test_run_has_no_static_check_opt_out():
    import inspect

    assert "skip_static_check" not in inspect.signature(cr.run).parameters


# --------------------------------------------------------------------------
# Reserved pytest arguments (review 2026-08-29, M1)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "arg",
    [
        # Attached short-option values: pytest's parser accepts these, and the
        # previous exact/``=``-suffix match let every one of them through.
        "-pmyplugin",
        "-pno:cacheprovider",
        "-opython_files=*.py",
        "-oaddopts=-p evil",
        "-qq",
        "-csetup.cfg",
        # argparse's unique-prefix abbreviations reach the same options.
        "--overr=python_files=*.py",
        "--override=addopts=-p evil",
        "--rootd=/",
        "--basete=/etc",
        "--quie",
    ],
)
def test_attached_and_abbreviated_reserved_args_are_refused(worktree, runtime, arg):
    violations = cr.validate(make_config(worktree, runtime), ["tests"], [arg])
    assert violations, arg
    with pytest.raises(cr.ContainmentError):
        cr.build_argv(make_config(worktree, runtime), ["tests"], [arg])


@pytest.mark.parametrize(
    "arg", ["-x", "-v", "-vv", "-s", "--maxfail=1", "--tb=short", "--durations=10", "--"]
)
def test_ordinary_args_survive_the_stricter_matching(worktree, runtime, arg):
    assert cr.validate(make_config(worktree, runtime), ["tests"], [arg]) == []


# --------------------------------------------------------------------------
# Collection surface against the Git canon (review 2026-08-29, M2)
# --------------------------------------------------------------------------


def test_committed_conftest_is_flagged_against_the_baseline(git_worktree, runtime):
    """The ordinary submission form -- a commit -- used to pass unexamined."""
    import subprocess as sp

    baseline = sp.run(
        ["git", "-C", str(git_worktree), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    (git_worktree / "tests" / "conftest.py").write_text("# brought in and committed\n")
    _git(git_worktree, "add", "-A")
    _git(git_worktree, "commit", "-q", "-m", "add conftest")

    config = make_config(git_worktree, runtime, baseline_ref=baseline)
    findings = cr.collection_static_check(config, ["tests"])
    assert any("collection config changed against" in f for f in findings), findings


def test_committed_pyproject_addopts_is_flagged_against_the_baseline(
    git_worktree, runtime
):
    import subprocess as sp

    baseline = sp.run(
        ["git", "-C", str(git_worktree), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    (git_worktree / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\naddopts = '-p evil'\n"
    )
    _git(git_worktree, "add", "-A")
    _git(git_worktree, "commit", "-q", "-m", "add pyproject")

    config = make_config(git_worktree, runtime, baseline_ref=baseline)
    findings = cr.collection_static_check(config, ["."])
    assert any("pyproject.toml" in f for f in findings), findings


def test_unresolvable_baseline_ref_is_a_finding(git_worktree, runtime):
    config = make_config(git_worktree, runtime, baseline_ref="origin/does-not-exist")
    findings = cr.collection_static_check(config, ["tests"])
    assert any("cannot be resolved" in f for f in findings), findings


def test_unset_baseline_ref_is_refused_by_validate(worktree, runtime):
    config = make_config(worktree, runtime, baseline_ref=None)
    violations = cr.validate(config, ["tests"])
    assert any("baseline_ref is unset" in v for v in violations), violations


# --------------------------------------------------------------------------
# Absent docker and exit-code separation (review 2026-08-29, M3)
# --------------------------------------------------------------------------


def test_absent_docker_is_reported_not_raised(worktree, runtime):
    config = make_config(worktree, runtime, docker="pda-docker-does-not-exist")
    problems = cr.verify_image_present(config)
    assert problems
    assert any("not usable" in p for p in problems), problems


def test_run_with_absent_docker_returns_infra_error(git_worktree, runtime, monkeypatch):
    monkeypatch.setattr(cr, "available_memory_mb", lambda: 999999)
    monkeypatch.setattr(cr, "collection_static_check", lambda config, targets: [])
    config = make_config(git_worktree, runtime, docker="pda-docker-does-not-exist")
    result = cr.run(config, ["tests"])
    assert result.verdict == "infra_error"
    assert result.collected is None


def test_absent_docker_exit_code_is_not_the_failure_exit_code(
    git_worktree, runtime, capsys
):
    rc = cr.main(
        [
            "--worktree", str(git_worktree),
            "--target", "tests",
            "--interpreter", str(runtime / "venv" / "bin" / "python"),
            "--runtime-mount", str(runtime),
            "--secret-home", "/home/user",
            "--baseline-ref", "HEAD",
            "--check-image",
        ]
    )
    assert rc == cr._EXIT_INFRA_ERROR
    assert rc != cr._EXIT_FAIL


def test_cli_exit_codes_distinguish_every_verdict():
    codes = {
        verdict: cr._EXIT_CODES[verdict]
        for verdict in ("pass", "fail", "refused", "infra_error")
    }
    assert len(set(codes.values())) == 4, codes
    assert codes["pass"] == 0
    assert codes["fail"] != codes["infra_error"]


# --------------------------------------------------------------------------
# Host-side subprocess environment and mount fields (m1, m2, m3)
# --------------------------------------------------------------------------


def test_host_subprocess_env_drops_daemon_and_git_redirection(monkeypatch):
    for name in ("DOCKER_HOST", "GIT_DIR", "GIT_WORK_TREE", "DOCKER_CONTEXT"):
        monkeypatch.setenv(name, "/attacker-controlled")
    env = cr.host_subprocess_env()
    assert set(env) == {"PATH"}


def test_the_image_check_and_the_run_agree_on_the_environment(monkeypatch, worktree, runtime):
    """Both used to differ: the run scrubbed the environment, the digest check
    inherited it, so an ambient ``DOCKER_HOST`` could answer "is the pinned
    image present" about a different daemon than the one that ran it."""
    seen = []

    def record(argv, **kwargs):
        seen.append(kwargs.get("env"))
        class P:
            returncode = 0
            stdout = ""
            stderr = ""
        return P()

    monkeypatch.setenv("DOCKER_HOST", "tcp://attacker:2375")
    monkeypatch.setattr(cr.subprocess, "run", record)
    cr.verify_image_present(make_config(worktree, runtime))
    cr._untracked_paths(worktree)
    assert seen and all(env is not None and "DOCKER_HOST" not in env for env in seen)


@pytest.mark.parametrize("bad", ["with:colon", "with,comma"])
def test_mount_path_containing_a_volume_separator_is_refused(tmp_path, runtime, bad):
    root = tmp_path / bad
    (root / ".git").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text("def test_x():\n    pass\n")
    config = make_config(root, runtime)
    violations = cr.validate(config, ["tests"])
    assert any("field separator" in v for v in violations), violations


@pytest.mark.parametrize("uid,gid", [(None, None), (0, 0), (1000, 0), (0, 1000)])
def test_root_or_unset_user_is_refused(worktree, runtime, uid, gid):
    config = make_config(worktree, runtime, uid=uid, gid=gid)
    violations = cr.validate(config, ["tests"])
    assert violations
    assert any("root" in v for v in violations), violations


def test_agent_node_preset_sets_a_non_root_user_and_a_fixed_secret_home():
    config = cr.ContainmentConfig.for_agent_node("/home/user/projects/pda")
    assert config.secret_home == Path("/home/user")
    assert config.baseline_ref == "origin/main"
    assert config.uid is not None and config.uid != 0
    assert config.gid is not None and config.gid != 0
