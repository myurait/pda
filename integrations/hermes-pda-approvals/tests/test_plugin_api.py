from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hermes_cli import kanban_db


PLUGIN_API = Path(__file__).parents[1] / "dashboard" / "plugin_api.py"


def _load_plugin_api():
    name = "pda_approvals_plugin_api_test"
    spec = importlib.util.spec_from_file_location(name, PLUGIN_API)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str, str]:
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
    return repo, base, head


def _approval(task_id: str, base: str, head: str) -> dict:
    return {
        "schema_version": 1,
        "task_id": task_id,
        "owner_outcome": "PDA改善が検証済み成果として反映可能になる",
        "base_sha": base,
        "head_sha": head,
        "changed_files": ["change.txt"],
        "verification": [
            {"command": "pytest -q", "outcome": "passed", "summary": "1 passed"}
        ],
        "impact": "ローカルPDAリポジトリだけを更新する",
        "residual_risks": [],
        "risk_class": "local-reversible",
        "finalization": {
            "kind": "merge-only",
            "targets": ["/home/user/projects/pda"],
            "steps": ["承認済みheadをmainへ統合する"],
            "rollback": ["統合コミットをrevertする"],
        },
    }


def _review_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    assignee: str | None = "default",
):
    home = tmp_path / "home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    repo, base, head = _repo(tmp_path)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = kanban_db.create_task(
            conn,
            title="approval test",
            body="verified implementation",
            assignee=assignee,
            tenant="pda-improvement",
            workspace_kind="dir",
            workspace_path=str(repo),
        )
        payload = _approval(task_id, base, head)
        assert kanban_db.request_review(
            conn,
            task_id,
            summary="implementation verified",
            metadata={"pda_approval": payload},
        )
    module = _load_plugin_api()
    app = FastAPI()
    app.include_router(module.router)
    return module, TestClient(app), task_id, repo, payload


def test_pending_list_exposes_only_valid_review_requests(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(tmp_path, monkeypatch)

    response = client.get("/pending")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["task_id"] == task_id
    assert item["approval"] == payload
    assert item["eligible"] is True
    assert item["digest"] == module.approval_digest(payload)
    assert item["digest"] == hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_declared_changed_files_must_exactly_match_git_diff(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(tmp_path, monkeypatch)
    payload["changed_files"] = []
    with kanban_db.connect() as conn:
        conn.execute(
            "UPDATE task_runs SET metadata = ? WHERE task_id = ? AND outcome = 'review_requested'",
            (json.dumps({"pda_approval": payload}), task_id),
        )
        conn.commit()

    pending = client.get("/pending").json()["items"][0]
    response = client.post(
        f"/tasks/{task_id}/approve",
        json={"digest": module.approval_digest(payload)},
    )

    assert pending["eligible"] is False
    assert any("exactly match" in error for error in pending["errors"])
    assert response.status_code == 409
    with kanban_db.connect() as conn:
        assert kanban_db.get_task(conn, task_id).status == "review"


def test_approve_is_fail_closed_on_digest_or_git_head_drift(tmp_path, monkeypatch):
    module, client, task_id, repo, payload = _review_task(tmp_path, monkeypatch)

    wrong = client.post(f"/tasks/{task_id}/approve", json={"digest": "0" * 64})
    assert wrong.status_code == 409

    (repo / "drift.txt").write_text("drift\n", encoding="utf-8")
    _git(repo, "add", "drift.txt")
    _git(repo, "commit", "-m", "drift")
    stale = client.post(
        f"/tasks/{task_id}/approve",
        json={"digest": module.approval_digest(payload)},
    )
    assert stale.status_code == 409

    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task is not None and task.status == "review"
        forged = conn.execute(
            "SELECT COUNT(*) FROM task_comments WHERE task_id = ? AND author = ?",
            (task_id, module.OWNER_APPROVAL_AUTHOR),
        ).fetchone()[0]
        assert forged == 0


def test_approve_records_control_owned_marker_then_reopens_for_finalization(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(tmp_path, monkeypatch)
    digest = module.approval_digest(payload)

    response = client.post(f"/tasks/{task_id}/approve", json={"digest": digest})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "ready"
    assert body["approval_id"].startswith("pa_")
    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task is not None
        assert task.status == "ready"
        assert task.assignee == "default"
        assert "pda-autonomous-improvement" in (task.skills or [])
        ledger = conn.execute(
            "SELECT approval_id, digest, head_sha, review_run_id, revoked_at "
            "FROM pda_owner_approvals WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        assert ledger is not None
        assert ledger["approval_id"] == body["approval_id"]
        assert ledger["digest"] == digest
        assert ledger["head_sha"] == payload["head_sha"]
        assert ledger["revoked_at"] is None
        row = conn.execute(
            "SELECT body FROM task_comments WHERE task_id = ? AND author = ? ORDER BY id DESC LIMIT 1",
            (task_id, module.OWNER_APPROVAL_AUTHOR),
        ).fetchone()
        marker = json.loads(row["body"].split("\n", 1)[1])
        assert marker["schema"] == "PDA_OWNER_APPROVAL_V1"
        assert marker["task_id"] == task_id
        assert marker["digest"] == digest
        assert marker["head_sha"] == payload["head_sha"]


def test_approved_manual_card_is_assigned_to_the_dedicated_finalizer(
    tmp_path,
    monkeypatch,
):
    module, client, task_id, _repo_path, payload = _review_task(
        tmp_path,
        monkeypatch,
        assignee=None,
    )

    response = client.post(
        f"/tasks/{task_id}/approve",
        json={"digest": module.approval_digest(payload)},
    )

    assert response.status_code == 200
    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task is not None
        assert task.status == "ready"
        assert task.assignee == "default"
        assert "pda-autonomous-improvement" in (task.skills or [])


def test_non_finalizer_assignee_cannot_be_approved(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(
        tmp_path,
        monkeypatch,
        assignee="legacy-worker",
    )

    pending = client.get("/pending").json()["items"][0]
    response = client.post(
        f"/tasks/{task_id}/approve",
        json={"digest": module.approval_digest(payload)},
    )

    assert pending["eligible"] is False
    assert response.status_code == 409
    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task.status == "review"
        assert task.assignee == "legacy-worker"


def test_failed_reopen_approval_is_revoked_on_request_changes(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(tmp_path, monkeypatch)
    digest = module.approval_digest(payload)
    original_reopen = module.kanban_db.reopen_review_task
    monkeypatch.setattr(module.kanban_db, "reopen_review_task", lambda conn, task_id: False)

    failed = client.post(f"/tasks/{task_id}/approve", json={"digest": digest})
    monkeypatch.setattr(module.kanban_db, "reopen_review_task", original_reopen)
    changed = client.post(
        f"/tasks/{task_id}/request-changes",
        json={"reason": "再検証してください"},
    )

    assert failed.status_code == 409
    assert changed.status_code == 200
    with kanban_db.connect() as conn:
        row = conn.execute(
            "SELECT revoked_at FROM pda_owner_approvals WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        assert row is not None and row["revoked_at"] is not None


def test_request_changes_never_creates_an_approval_marker(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, _payload = _review_task(tmp_path, monkeypatch)

    response = client.post(
        f"/tasks/{task_id}/request-changes",
        json={"reason": "受入条件の証拠を追加してください"},
    )

    assert response.status_code == 200
    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task is not None and task.status == "ready"
        approval_count = conn.execute(
            "SELECT COUNT(*) FROM task_comments WHERE task_id = ? AND author = ?",
            (task_id, module.OWNER_APPROVAL_AUTHOR),
        ).fetchone()[0]
        assert approval_count == 0
        change_count = conn.execute(
            "SELECT COUNT(*) FROM task_comments WHERE task_id = ? AND author = ?",
            (task_id, module.OWNER_CHANGES_AUTHOR),
        ).fetchone()[0]
        assert change_count == 1


def test_non_pda_or_non_review_tasks_are_not_approvable(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = kanban_db.create_task(
            conn,
            title="foreign",
            tenant="another-tenant",
            assignee="default",
        )
    module = _load_plugin_api()
    app = FastAPI()
    app.include_router(module.router)
    client = TestClient(app)

    response = client.post(f"/tasks/{task_id}/approve", json={"digest": "0" * 64})

    assert response.status_code == 404
