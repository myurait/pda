from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from hermes_cli import kanban_db

import operations.improvement.install as install_module
from operations.improvement.install import (
    RuntimePaths,
    _resolve_python_executable,
    _snapshot_daily_reconciler,
    _desired_daily_reconciler_state,
    _verify_approved_artifact,
    check_approval_runtime,
    install_managed_files,
    verify_owner_approval,
)


REPO = Path(__file__).parents[3]


def _paths(tmp_path: Path) -> RuntimePaths:
    home = tmp_path / "user"
    hermes_home = home / ".hermes"
    hermes_home.mkdir(parents=True)
    return RuntimePaths(
        home=home,
        hermes_home=hermes_home,
        python_executable=Path(sys.executable),
    )


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def _create_approval_ledger(conn) -> None:
    conn.execute(
        """
        CREATE TABLE pda_owner_approvals (
            approval_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            digest TEXT NOT NULL,
            head_sha TEXT NOT NULL,
            review_run_id INTEGER NOT NULL,
            approved_at INTEGER NOT NULL,
            revoked_at INTEGER,
            UNIQUE(task_id, review_run_id, digest)
        )
        """
    )
    conn.commit()


def test_default_systemd_python_is_the_hermes_venv(tmp_path):
    hermes_home = tmp_path / ".hermes"
    python_path = hermes_home / "hermes-agent" / "venv" / "bin" / "python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(Path(sys.executable))

    assert _resolve_python_executable(hermes_home, None) == python_path.absolute()
    with pytest.raises(ValueError, match="Hermes Python executable is missing"):
        _resolve_python_executable(tmp_path / "missing", None)


def test_cron_snapshot_is_restricted_and_not_overwritten_on_retry(tmp_path):
    paths = _paths(tmp_path)
    jobs_path = paths.hermes_home / "cron" / "jobs.json"
    jobs_path.parent.mkdir(parents=True)
    jobs_path.write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": "64b615bad09c",
                        "prompt": "old prompt",
                        "skills": ["old-skill"],
                        "workdir": None,
                        "context_from": ["self"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    snapshot = _snapshot_daily_reconciler(REPO, paths)
    jobs_path.write_text(
        json.dumps({"jobs": [{"id": "64b615bad09c", "prompt": "newer"}]}),
        encoding="utf-8",
    )
    retried = _snapshot_daily_reconciler(REPO, paths)
    desired = _desired_daily_reconciler_state(REPO)

    assert snapshot == retried
    assert snapshot["prompt"] == "old prompt"
    assert snapshot["continuity"] is True
    assert paths.cron_rollback.stat().st_mode & 0o777 == 0o600
    assert desired["job_id"] == "64b615bad09c"
    assert "pda-autonomous-improvement" in desired["skills"]
    assert desired["workdir"] == str(REPO)


def test_stage_install_is_idempotent_and_keeps_executor_disabled(tmp_path):
    paths = _paths(tmp_path)

    first = install_managed_files(REPO, paths, activate=False)
    second = install_managed_files(REPO, paths, activate=False)

    assert first["enabled"] is False
    assert second["enabled"] is False
    runtime = json.loads(paths.runtime_config.read_text(encoding="utf-8"))
    assert runtime["enabled"] is False
    assert runtime["max_wip"] == 2
    assert (paths.plugin_root / "plugin.yaml").is_file()
    assert (paths.plugin_root / "__init__.py").is_file()
    assert (paths.plugin_root / "dashboard" / "manifest.json").is_file()
    assert (paths.plugin_root / "dashboard" / "plugin_api.py").is_file()
    assert (paths.hermes_home / "skills" / "pda-autonomous-improvement" / "SKILL.md").is_file()
    assert (paths.hermes_home / "skills" / "pda-user-escalation" / "SKILL.md").is_file()
    assert not (paths.hermes_home / "profiles").exists()
    assert not any("SOUL.md" in installed for installed in first["installed"])
    service = (paths.systemd_user / "pda-improvement-cycle.service").read_text(encoding="utf-8")
    assert "@PYTHON@" not in service
    assert "@WORKDIR@" not in service
    assert str(paths.python_executable) in service
    assert "WorkingDirectory=/home/user/projects/pda" in service


def test_stage_runtime_keeps_daily_cron_unchanged(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    commands: list[list[str]] = []

    def fake_run(args, **kwargs):
        commands.append(list(args))
        if "is-active" in args:
            return "active"
        if "is-enabled" in args:
            return "enabled"
        return ""

    monkeypatch.setattr(install_module, "_run", fake_run)
    result = install_module.stage_runtime(REPO, paths, hermes_bin="hermes")

    assert result["enabled"] is False
    assert not any("cron" in command for args in commands for command in args)
    assert any(args[:3] == ["hermes", "plugins", "enable"] for args in commands)
    assert any("restart" in args and "hermes-dashboard.service" in args for args in commands)


def test_activate_install_requires_control_owned_matching_approval(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(paths.hermes_home))
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = kanban_db.create_task(
            conn,
            title="activate",
            tenant="pda-improvement",
            workspace_kind="dir",
            workspace_path=str(REPO),
        )
        marker = {
            "schema": "PDA_OWNER_APPROVAL_V1",
            "approval_id": "pa_1234567890abcdef",
            "task_id": task_id,
            "digest": "a" * 64,
            "head_sha": "b" * 40,
            "review_run_id": 7,
            "approved_at": 123,
        }
        kanban_db.add_comment(
            conn,
            task_id,
            "pda-owner-approval",
            "approved\n" + json.dumps(marker),
        )
        with pytest.raises(ValueError, match="ledger is not installed"):
            verify_owner_approval(
                conn,
                task_id=task_id,
                approval_id=marker["approval_id"],
                digest=marker["digest"],
            )
        _create_approval_ledger(conn)
        conn.execute(
            "INSERT INTO pda_owner_approvals "
            "(approval_id, task_id, digest, head_sha, review_run_id, approved_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                marker["approval_id"],
                task_id,
                marker["digest"],
                marker["head_sha"],
                marker["review_run_id"],
                marker["approved_at"],
            ),
        )
        conn.commit()

        assert verify_owner_approval(
            conn,
            task_id=task_id,
            approval_id=marker["approval_id"],
            digest=marker["digest"],
        ) == marker
        with pytest.raises(ValueError, match="matching owner approval"):
            verify_owner_approval(
                conn,
                task_id=task_id,
                approval_id=marker["approval_id"],
                digest="c" * 64,
            )


def test_activation_rechecks_latest_review_head_and_clean_workspace(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(paths.hermes_home))
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "pda-test@example.invalid")
    _git(repo, "config", "user.name", "PDA Test")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "change.txt").write_text("change\n", encoding="utf-8")
    _git(repo, "add", "change.txt")
    _git(repo, "commit", "-m", "change")
    head = _git(repo, "rev-parse", "HEAD")

    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = kanban_db.create_task(
            conn,
            title="activate verified artifact",
            tenant="pda-improvement",
            assignee="default",
            workspace_kind="dir",
            workspace_path=str(repo),
        )
        conn.execute(
            "UPDATE tasks SET skills = ? WHERE id = ?",
            (json.dumps(["pda-autonomous-improvement"]), task_id),
        )
        conn.commit()
        approval = {
            "schema_version": 1,
            "task_id": task_id,
            "base_sha": base,
            "head_sha": head,
        }
        assert kanban_db.request_review(
            conn,
            task_id,
            summary="verified",
            metadata={"pda_approval": approval},
        )
        run = conn.execute(
            "SELECT id FROM task_runs WHERE task_id = ? AND outcome = 'review_requested'",
            (task_id,),
        ).fetchone()
        digest = hashlib.sha256(
            json.dumps(
                approval,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        marker = {
            "schema": "PDA_OWNER_APPROVAL_V1",
            "approval_id": "pa_artifact_verified",
            "task_id": task_id,
            "digest": digest,
            "head_sha": head,
            "review_run_id": int(run["id"]),
            "approved_at": 123,
        }
        kanban_db.add_comment(
            conn,
            task_id,
            "pda-owner-approval",
            "approved\n" + json.dumps(marker),
        )
        assert kanban_db.reopen_review_task(conn, task_id)
        _create_approval_ledger(conn)
        conn.execute(
            "INSERT INTO pda_owner_approvals "
            "(approval_id, task_id, digest, head_sha, review_run_id, approved_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                marker["approval_id"],
                task_id,
                marker["digest"],
                marker["head_sha"],
                marker["review_run_id"],
                marker["approved_at"],
            ),
        )
        conn.commit()

        _verify_approved_artifact(conn, task_id, marker)
        checked = check_approval_runtime(
            paths,
            task_id=task_id,
            approval_id=marker["approval_id"],
            digest=marker["digest"],
        )
        assert checked["mode"] == "checked"
        (repo / "drift.txt").write_text("drift\n", encoding="utf-8")
        with pytest.raises(ValueError, match="dirty"):
            _verify_approved_artifact(conn, task_id, marker)
        (repo / "drift.txt").unlink()

        newer_approval = dict(approval)
        newer_approval["revision"] = 2
        assert kanban_db.request_review(
            conn,
            task_id,
            summary="new review",
            metadata={"pda_approval": newer_approval},
        )
        assert kanban_db.reopen_review_task(conn, task_id)
        with pytest.raises(ValueError, match="digest has drifted"):
            _verify_approved_artifact(conn, task_id, marker)


def test_activation_failure_restores_disabled_runtime_and_prior_cron(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    marker = {
        "schema": "PDA_OWNER_APPROVAL_V1",
        "approval_id": "pa_transaction",
        "digest": "f" * 64,
    }
    prior = {
        "schema_version": 1,
        "job_id": "64b615bad09c",
        "prompt": "prior",
        "skills": ["old"],
        "workdir": None,
        "continuity": True,
    }
    desired = dict(prior, prompt="desired", skills=["new"])
    applied: list[dict] = []
    commands: list[list[str]] = []

    monkeypatch.setattr(
        install_module,
        "check_approval_runtime",
        lambda *args, **kwargs: {"ok": True, "mode": "checked", "approval": marker},
    )
    monkeypatch.setattr(install_module, "_snapshot_daily_reconciler", lambda *args: prior)
    monkeypatch.setattr(install_module, "_desired_daily_reconciler_state", lambda *args: desired)
    monkeypatch.setattr(
        install_module,
        "_apply_daily_reconciler_state",
        lambda state, *args: applied.append(state),
    )

    def fake_run(args, **kwargs):
        commands.append(list(args))
        if args[:4] == ["systemctl", "--user", "start", "pda-improvement-cycle.service"]:
            raise RuntimeError("synthetic service failure")
        return ""

    monkeypatch.setattr(install_module, "_run", fake_run)

    with pytest.raises(RuntimeError, match="synthetic service failure"):
        install_module.activate_runtime(
            REPO,
            paths,
            task_id="t_test",
            approval_id=marker["approval_id"],
            digest=marker["digest"],
        )

    runtime = json.loads(paths.runtime_config.read_text(encoding="utf-8"))
    assert runtime["enabled"] is False
    assert applied == [desired, prior]
    assert commands[-1][:4] == ["systemctl", "--user", "enable", "--now"]
    assert commands[-1][-1] == "pda-improvement-cycle.timer"


def test_explicit_rollback_restores_snapshot_and_noop_timer(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    prior = {
        "schema_version": 1,
        "job_id": "64b615bad09c",
        "prompt": "prior",
        "skills": ["old"],
        "workdir": None,
        "continuity": True,
    }
    paths.cron_rollback.parent.mkdir(parents=True, exist_ok=True)
    paths.cron_rollback.write_text(json.dumps(prior), encoding="utf-8")
    applied: list[dict] = []
    commands: list[list[str]] = []
    monkeypatch.setattr(
        install_module,
        "_apply_daily_reconciler_state",
        lambda state, *args: applied.append(state),
    )
    monkeypatch.setattr(
        install_module,
        "_run",
        lambda args, **kwargs: commands.append(list(args)) or "",
    )

    result = install_module.rollback_runtime(REPO, paths)

    runtime = json.loads(paths.runtime_config.read_text(encoding="utf-8"))
    assert result["mode"] == "rolled-back"
    assert runtime["enabled"] is False
    assert applied == [prior]
    assert commands[0][:4] == ["systemctl", "--user", "stop", "pda-improvement-cycle.timer"]
    assert commands[-1][:4] == ["systemctl", "--user", "enable", "--now"]


def test_activate_writes_enabled_runtime_only_after_verification_boundary(tmp_path):
    paths = _paths(tmp_path)
    with pytest.raises(ValueError, match="verified owner approval"):
        install_managed_files(REPO, paths, activate=True)
    marker = {
        "schema": "PDA_OWNER_APPROVAL_V1",
        "approval_id": "pa_verified",
        "digest": "d" * 64,
    }

    result = install_managed_files(
        REPO,
        paths,
        activate=True,
        approval_marker=marker,
    )

    assert result["enabled"] is True
    runtime = json.loads(paths.runtime_config.read_text(encoding="utf-8"))
    assert runtime["enabled"] is True
    source = json.loads((REPO / "continuity" / "autonomous-improvement.json").read_text())
    assert source["enabled"] is True
