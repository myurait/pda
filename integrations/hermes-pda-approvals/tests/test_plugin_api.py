from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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


def _git_path(workspace: Path, flag: str) -> str:
    value = Path(_git(workspace, "rev-parse", flag))
    return str((value if value.is_absolute() else workspace / value).resolve())


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "pda-test@example.invalid")
    _git(repo, "config", "user.name", "PDA Test")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    return repo, base


def _approval(
    task_id: str,
    base: str,
    head: str,
    workspace: Path,
    branch: str,
) -> dict:
    return {
        "schema_version": 1,
        "task_id": task_id,
        "owner_outcome": "PDA改善が検証済み成果として反映可能になる",
        "base_sha": base,
        "head_sha": head,
        "workspace_path": str(workspace.resolve()),
        "branch_name": branch,
        "git_common_dir": _git_path(workspace, "--git-common-dir"),
        "git_dir": _git_path(workspace, "--git-dir"),
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
    authenticated_user: str = "owner",
):
    home = tmp_path / "home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_DASHBOARD_BASIC_AUTH_USERNAME", "owner")
    repo, base = _repo(tmp_path)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = kanban_db.create_task(
            conn,
            title="approval test",
            body="verified implementation",
            assignee=assignee,
            tenant="pda-improvement",
            workspace_kind="dir",
            workspace_path="/placeholder",
        )
        branch = f"pda-auto/{task_id}"
        workspace = tmp_path / "task-worktree"
        _git(repo, "worktree", "add", "-b", branch, str(workspace), "main")
        (workspace / "change.txt").write_text("change\n", encoding="utf-8")
        _git(workspace, "add", "change.txt")
        _git(workspace, "commit", "-m", "change")
        head = _git(workspace, "rev-parse", "HEAD")
        kanban_db.set_workspace_path(conn, task_id, workspace)
        kanban_db.set_branch_name(conn, task_id, branch)
        payload = _approval(task_id, base, head, workspace, branch)
        assert kanban_db.request_review(
            conn,
            task_id,
            summary="implementation verified",
            metadata={"pda_approval": payload},
        )
    module = _load_plugin_api()
    app = FastAPI()

    @app.middleware("http")
    async def attach_session(request, call_next):
        request.state.session = SimpleNamespace(
            provider="basic",
            user_id=authenticated_user,
        )
        return await call_next(request)

    app.include_router(module.router)
    return module, TestClient(app), task_id, workspace, payload


def test_existing_approval_ledger_is_migrated_with_owner_identity_columns(
    tmp_path,
    monkeypatch,
):
    home = tmp_path / "home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    kanban_db.init_db()
    with kanban_db.connect() as conn:
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
    module = _load_plugin_api()
    app = FastAPI()
    app.include_router(module.router)

    response = TestClient(app).get("/pending")

    assert response.status_code == 200
    with kanban_db.connect() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(pda_owner_approvals)").fetchall()
        }
        assert {
            "base_sha",
            "workspace_path",
            "branch_name",
            "git_common_dir",
            "git_dir",
            "approved_by_provider",
            "approved_by_user_id",
            "activation_nonce",
            "activation_started_at",
            "consumed_at",
        } <= columns


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


def test_config_only_basic_auth_owner_can_approve(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(tmp_path, monkeypatch)
    monkeypatch.delenv("HERMES_DASHBOARD_BASIC_AUTH_USERNAME", raising=False)
    from hermes_cli import config as hermes_config

    monkeypatch.setattr(
        hermes_config,
        "load_config",
        lambda: {"dashboard": {"basic_auth": {"username": "owner"}}},
    )

    response = client.post(
        f"/tasks/{task_id}/approve",
        json={"digest": module.approval_digest(payload)},
    )

    assert response.status_code == 200


def test_non_owner_session_cannot_approve(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_DASHBOARD_BASIC_AUTH_USERNAME", "owner")
    module, client, task_id, _repo_path, payload = _review_task(
        tmp_path,
        monkeypatch,
        authenticated_user="another-user",
    )

    response = client.post(
        f"/tasks/{task_id}/approve",
        json={"digest": module.approval_digest(payload)},
    )

    assert response.status_code == 403
    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task is not None and task.status == "review"
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name = 'pda_owner_approvals'"
        ).fetchone()
        if table is not None:
            ledger_count = conn.execute(
                "SELECT COUNT(*) FROM pda_owner_approvals WHERE task_id = ?",
                (task_id,),
            ).fetchone()[0]
            assert ledger_count == 0


def test_task_branch_drift_is_not_approvable(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(tmp_path, monkeypatch)
    with kanban_db.connect() as conn:
        kanban_db.set_branch_name(conn, task_id, f"pda-auto/{task_id}-other")

    pending = client.get("/pending").json()["items"][0]
    response = client.post(
        f"/tasks/{task_id}/approve",
        json={"digest": module.approval_digest(payload)},
    )

    assert pending["eligible"] is False
    assert any("branch" in error for error in pending["errors"])
    assert response.status_code == 409


def test_declared_workspace_path_must_match_task_worktree(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(tmp_path, monkeypatch)
    payload["workspace_path"] = str((tmp_path / "different-worktree").resolve())
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
    assert any("workspace" in error for error in pending["errors"])
    assert response.status_code == 409


def test_symlinked_workspace_path_is_not_approvable(tmp_path, monkeypatch):
    module, client, task_id, workspace, payload = _review_task(tmp_path, monkeypatch)
    alias = tmp_path / "task-worktree-alias"
    alias.symlink_to(workspace, target_is_directory=True)
    payload["workspace_path"] = str(alias.absolute())
    with kanban_db.connect() as conn:
        kanban_db.set_workspace_path(conn, task_id, alias)
        conn.execute(
            "UPDATE task_runs SET metadata = ? WHERE task_id = ? AND outcome = 'review_requested'",
            (json.dumps({"pda_approval": payload}), task_id),
        )
        conn.commit()

    pending = client.get("/pending").json()["items"][0]

    assert pending["eligible"] is False
    assert any("symlink" in error for error in pending["errors"])


def test_git_worktree_identity_is_digest_bound(tmp_path, monkeypatch):
    module, client, task_id, _workspace, payload = _review_task(tmp_path, monkeypatch)
    payload["git_dir"] = str((tmp_path / "different-git-dir").resolve())
    with kanban_db.connect() as conn:
        conn.execute(
            "UPDATE task_runs SET metadata = ? WHERE task_id = ? AND outcome = 'review_requested'",
            (json.dumps({"pda_approval": payload}), task_id),
        )
        conn.commit()

    pending = client.get("/pending").json()["items"][0]

    assert pending["eligible"] is False
    assert any("git_dir" in error for error in pending["errors"])


def test_primary_checkout_is_not_an_isolated_task_worktree(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_DASHBOARD_BASIC_AUTH_USERNAME", "owner")
    repo, base = _repo(tmp_path)
    kanban_db.init_db()
    with kanban_db.connect() as conn:
        task_id = kanban_db.create_task(
            conn,
            title="shared checkout",
            body="must be isolated",
            assignee="default",
            tenant="pda-improvement",
            workspace_kind="dir",
            workspace_path=str(repo),
        )
        branch = f"pda-auto/{task_id}"
        _git(repo, "checkout", "-b", branch)
        (repo / "change.txt").write_text("change\n", encoding="utf-8")
        _git(repo, "add", "change.txt")
        _git(repo, "commit", "-m", "change")
        head = _git(repo, "rev-parse", "HEAD")
        kanban_db.set_branch_name(conn, task_id, branch)
        payload = _approval(task_id, base, head, repo, branch)
        assert kanban_db.request_review(
            conn,
            task_id,
            summary="not actually isolated",
            metadata={"pda_approval": payload},
        )
    module = _load_plugin_api()
    app = FastAPI()

    @app.middleware("http")
    async def attach_owner_session(request, call_next):
        request.state.session = SimpleNamespace(provider="basic", user_id="owner")
        return await call_next(request)

    app.include_router(module.router)
    client = TestClient(app)

    pending = client.get("/pending").json()["items"][0]
    response = client.post(
        f"/tasks/{task_id}/approve",
        json={"digest": module.approval_digest(payload)},
    )

    assert pending["eligible"] is False
    assert any("linked worktree" in error for error in pending["errors"])
    assert response.status_code == 409


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
            "SELECT approval_id, digest, base_sha, head_sha, workspace_path, "
            "branch_name, git_common_dir, git_dir, review_run_id, revoked_at, "
            "approved_by_provider, approved_by_user_id "
            "FROM pda_owner_approvals WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        assert ledger is not None
        assert ledger["approval_id"] == body["approval_id"]
        assert ledger["digest"] == digest
        assert ledger["base_sha"] == payload["base_sha"]
        assert ledger["head_sha"] == payload["head_sha"]
        assert ledger["workspace_path"] == payload["workspace_path"]
        assert ledger["branch_name"] == payload["branch_name"]
        assert ledger["git_common_dir"] == payload["git_common_dir"]
        assert ledger["git_dir"] == payload["git_dir"]
        assert ledger["approved_by_provider"] == "basic"
        assert ledger["approved_by_user_id"] == "owner"
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


def test_idempotent_retry_preserves_the_same_verified_approval(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(tmp_path, monkeypatch)
    digest = module.approval_digest(payload)

    first = client.post(f"/tasks/{task_id}/approve", json={"digest": digest})
    second = client.post(f"/tasks/{task_id}/approve", json={"digest": digest})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["idempotent"] is True
    assert second.json()["approval_id"] == first.json()["approval_id"]


def test_idempotent_retry_rejects_ledger_owner_identity_drift(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(tmp_path, monkeypatch)
    digest = module.approval_digest(payload)
    first = client.post(f"/tasks/{task_id}/approve", json={"digest": digest})
    assert first.status_code == 200
    with kanban_db.connect() as conn:
        conn.execute(
            "UPDATE pda_owner_approvals SET approved_by_user_id = ? WHERE task_id = ?",
            ("another-user", task_id),
        )
        conn.commit()

    second = client.post(f"/tasks/{task_id}/approve", json={"digest": digest})

    assert second.status_code == 409


def test_idempotent_retry_rejects_approved_workspace_drift(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(tmp_path, monkeypatch)
    digest = module.approval_digest(payload)
    first = client.post(f"/tasks/{task_id}/approve", json={"digest": digest})
    assert first.status_code == 200
    with kanban_db.connect() as conn:
        kanban_db.set_branch_name(conn, task_id, f"pda-auto/{task_id}-drift")

    second = client.post(f"/tasks/{task_id}/approve", json={"digest": digest})

    assert second.status_code == 409


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


def test_approval_reclaims_a_dangling_review_run_atomically(tmp_path, monkeypatch):
    module, client, task_id, _workspace, payload = _review_task(tmp_path, monkeypatch)
    with kanban_db.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO task_runs (task_id, profile, status, claim_lock, started_at) "
            "VALUES (?, ?, 'running', ?, ?)",
            (task_id, "default", "stale-claim", 1),
        )
        stale_run_id = int(cursor.lastrowid)
        conn.execute(
            "UPDATE tasks SET current_run_id = ?, claim_lock = ? WHERE id = ?",
            (stale_run_id, "stale-claim", task_id),
        )
        conn.commit()

    response = client.post(
        f"/tasks/{task_id}/approve",
        json={"digest": module.approval_digest(payload)},
    )

    assert response.status_code == 200
    with kanban_db.connect() as conn:
        task = conn.execute(
            "SELECT current_run_id FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        run = conn.execute(
            "SELECT status, outcome, ended_at FROM task_runs WHERE id = ?",
            (stale_run_id,),
        ).fetchone()
        assert task["current_run_id"] is None
        assert run["status"] == "reclaimed"
        assert run["outcome"] == "reclaimed"
        assert run["ended_at"] is not None


def test_workspace_is_revalidated_inside_approval_transaction(tmp_path, monkeypatch):
    module, client, task_id, _workspace, payload = _review_task(tmp_path, monkeypatch)
    original_verify = module.verify_workspace
    drifted = False

    def verify_then_drift(task, approval):
        nonlocal drifted
        errors = original_verify(task, approval)
        if not errors and not drifted:
            drifted = True
            with kanban_db.connect() as conn:
                kanban_db.set_branch_name(conn, task_id, f"pda-auto/{task_id}-drift")
        return errors

    monkeypatch.setattr(module, "verify_workspace", verify_then_drift)

    response = client.post(
        f"/tasks/{task_id}/approve",
        json={"digest": module.approval_digest(payload)},
    )

    assert response.status_code == 409
    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task is not None and task.status == "review"
        count = conn.execute(
            "SELECT COUNT(*) FROM pda_owner_approvals WHERE task_id = ?",
            (task_id,),
        ).fetchone()[0]
        assert count == 0


def test_failed_approval_cas_rolls_back_every_control_write(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, payload = _review_task(tmp_path, monkeypatch)
    digest = module.approval_digest(payload)
    monkeypatch.setattr(
        module,
        "_atomic_reopen_review_task",
        lambda conn, task_id, status: False,
        raising=False,
    )

    failed = client.post(f"/tasks/{task_id}/approve", json={"digest": digest})

    assert failed.status_code == 409
    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task is not None and task.status == "review"
        assert "pda-autonomous-improvement" not in (task.skills or [])
        ledger_count = conn.execute(
            "SELECT COUNT(*) FROM pda_owner_approvals WHERE task_id = ?",
            (task_id,),
        ).fetchone()[0]
        comment_count = conn.execute(
            "SELECT COUNT(*) FROM task_comments WHERE task_id = ? AND author = ?",
            (task_id, module.OWNER_APPROVAL_AUTHOR),
        ).fetchone()[0]
        assert ledger_count == 0
        assert comment_count == 0


def test_failed_request_changes_cas_rolls_back_revocation_and_comment(
    tmp_path,
    monkeypatch,
):
    module, client, task_id, _workspace, payload = _review_task(tmp_path, monkeypatch)
    digest = module.approval_digest(payload)
    client.get("/pending")
    with kanban_db.connect() as conn:
        run = conn.execute(
            "SELECT id FROM task_runs WHERE task_id = ? AND outcome = 'review_requested'",
            (task_id,),
        ).fetchone()
        conn.execute(
            "INSERT INTO pda_owner_approvals "
            "(approval_id, task_id, digest, base_sha, head_sha, workspace_path, "
            "branch_name, git_common_dir, git_dir, review_run_id, approved_at, "
            "approved_by_provider, approved_by_user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "pa_request_changes",
                task_id,
                digest,
                payload["base_sha"],
                payload["head_sha"],
                payload["workspace_path"],
                payload["branch_name"],
                payload["git_common_dir"],
                payload["git_dir"],
                int(run["id"]),
                1,
                "basic",
                "owner",
            ),
        )
        conn.commit()
    monkeypatch.setattr(
        module,
        "_atomic_reopen_review_task",
        lambda conn, task_id, status: False,
    )

    response = client.post(
        f"/tasks/{task_id}/request-changes",
        json={"reason": "must remain atomic"},
    )

    assert response.status_code == 409
    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        ledger = conn.execute(
            "SELECT revoked_at FROM pda_owner_approvals WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        comments = conn.execute(
            "SELECT COUNT(*) FROM task_comments WHERE task_id = ? AND author = ?",
            (task_id, module.OWNER_CHANGES_AUTHOR),
        ).fetchone()[0]
        assert task is not None and task.status == "review"
        assert ledger["revoked_at"] is None
        assert comments == 0


def test_non_owner_session_cannot_request_changes(tmp_path, monkeypatch):
    module, client, task_id, _repo_path, _payload = _review_task(
        tmp_path,
        monkeypatch,
        authenticated_user="another-user",
    )

    response = client.post(
        f"/tasks/{task_id}/request-changes",
        json={"reason": "unauthorized"},
    )

    assert response.status_code == 403
    with kanban_db.connect() as conn:
        task = kanban_db.get_task(conn, task_id)
        assert task is not None and task.status == "review"


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
    monkeypatch.setenv("HERMES_DASHBOARD_BASIC_AUTH_USERNAME", "owner")
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

    @app.middleware("http")
    async def attach_owner_session(request, call_next):
        request.state.session = SimpleNamespace(provider="basic", user_id="owner")
        return await call_next(request)

    app.include_router(module.router)
    client = TestClient(app)

    response = client.post(f"/tasks/{task_id}/approve", json={"digest": "0" * 64})

    assert response.status_code == 404
