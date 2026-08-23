"""Install and activate the PDA autonomous improvement control plane."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from hermes_cli import kanban_db


PLUGIN_NAME = "pda-approvals"
WORKER_PROFILE = "default"
WORKER_SKILL = "pda-autonomous-improvement"

# Ambient worker/delegate environments pin these at higher precedence than
# HERMES_HOME (incident t_4a78c98b). Control-plane code must neutralize them
# so the board is always resolved from the HERMES_HOME it sets itself.
KANBAN_ENV_OVERRIDES = (
    "HERMES_KANBAN_DB",
    "HERMES_KANBAN_HOME",
    "HERMES_KANBAN_BOARD",
    "HERMES_KANBAN_WORKSPACES_ROOT",
    "HERMES_KANBAN_ATTACHMENTS_ROOT",
)
APPROVAL_SCHEMA = "PDA_OWNER_APPROVAL_V1"

# Kept in step with the approval plugin's own constants (Judgment A,
# 2026-08-23). The two validators are deliberately independent
# implementations, so the version and the derived-key set are asserted equal
# by the regression tests rather than shared through an import.
APPROVAL_METADATA_SCHEMA_VERSION = 2
GATE_DERIVED_IDENTITY_KEYS = ("git_common_dir", "git_dir")
_ALLOWED_RISK_CLASSES = {
    "local-reversible",
    "service-restart",
    "external-visible",
    "security-sensitive",
}
_ALLOWED_FINALIZATION_KINDS = {
    "merge-only",
    "merge-and-restart",
    "apply-artifacts",
    "no-runtime-change",
}
_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
ACTIVATION_CLAIM_STALE_SECONDS = 15 * 60


@dataclass(frozen=True)
class RuntimePaths:
    home: Path
    hermes_home: Path
    python_executable: Path

    @property
    def runtime_config(self) -> Path:
        return self.home / ".config" / "pda" / "autonomous-improvement.json"

    @property
    def cron_rollback(self) -> Path:
        return self.home / ".config" / "pda" / "autonomous-improvement-cron-before.json"

    @property
    def plugin_root(self) -> Path:
        return self.hermes_home / "plugins" / PLUGIN_NAME

    @property
    def systemd_user(self) -> Path:
        return self.home / ".config" / "systemd" / "user"

    @property
    def libexec(self) -> Path:
        return self.home / ".local" / "libexec" / "pda"


@dataclass(frozen=True)
class _Payload:
    destination: Path
    content: bytes
    mode: int


def _atomic_write(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _managed_payloads(repo_root: Path, paths: RuntimePaths, activate: bool) -> list[_Payload]:
    repo_root = repo_root.resolve()
    dashboard = repo_root / "integrations" / "hermes-pda-approvals" / "dashboard"
    integration = dashboard.parent
    skill = repo_root / "profiles" / "pda" / "skills" / WORKER_SKILL / "SKILL.md"
    escalation_skill = (
        repo_root / "profiles" / "pda" / "skills" / "pda-user-escalation" / "SKILL.md"
    )
    desired = json.loads(
        (repo_root / "continuity" / "autonomous-improvement.json").read_text(encoding="utf-8")
    )
    # The committed policy file is the single source of truth for whether the
    # autonomous cycle may run. Activation can never exceed it: while the
    # policy is suspended, only the owner may lift it by committing a policy
    # change, and the rendered runtime config stays disabled.
    if activate and not bool(desired.get("enabled")):
        raise ValueError(
            "autonomous improvement policy is suspended "
            "(continuity/autonomous-improvement.json enabled=false); "
            "activation requires an owner-committed policy change"
        )
    desired["enabled"] = bool(activate)
    runtime_config = (json.dumps(desired, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    repo_workdir = Path(str(desired.get("repo_root") or "")).expanduser()
    if not repo_workdir.is_absolute():
        raise ValueError("autonomous improvement repo_root must be absolute")
    service_template = (
        repo_root / "infra" / "systemd" / "pda-improvement-cycle.service.in"
    ).read_text(encoding="utf-8")
    service = (
        service_template.replace("@PYTHON@", str(paths.python_executable))
        .replace("@WORKDIR@", str(repo_workdir))
    )

    files: list[tuple[Path, Path, int]] = [
        (
            integration / "plugin.yaml",
            paths.plugin_root / "plugin.yaml",
            0o644,
        ),
        (
            integration / "__init__.py",
            paths.plugin_root / "__init__.py",
            0o644,
        ),
        (
            repo_root / "operations" / "improvement" / "pda_improvement_cycle.py",
            paths.libexec / "pda_improvement_cycle.py",
            0o755,
        ),
        (
            dashboard / "manifest.json",
            paths.plugin_root / "dashboard" / "manifest.json",
            0o644,
        ),
        (
            dashboard / "plugin_api.py",
            paths.plugin_root / "dashboard" / "plugin_api.py",
            0o644,
        ),
        (
            dashboard / "dist" / "index.js",
            paths.plugin_root / "dashboard" / "dist" / "index.js",
            0o644,
        ),
        (
            dashboard / "dist" / "style.css",
            paths.plugin_root / "dashboard" / "dist" / "style.css",
            0o644,
        ),
        (
            skill,
            paths.hermes_home / "skills" / WORKER_SKILL / "SKILL.md",
            0o644,
        ),
        (
            escalation_skill,
            paths.hermes_home / "skills" / "pda-user-escalation" / "SKILL.md",
            0o644,
        ),
        (
            repo_root / "infra" / "systemd" / "pda-improvement-cycle.timer",
            paths.systemd_user / "pda-improvement-cycle.timer",
            0o644,
        ),
    ]
    payloads = [_Payload(destination, _read_bytes(source), mode) for source, destination, mode in files]
    payloads.extend(
        [
            _Payload(paths.runtime_config, runtime_config, 0o600),
            _Payload(
                paths.systemd_user / "pda-improvement-cycle.service",
                service.encode("utf-8"),
                0o644,
            ),
        ]
    )
    return payloads


def _restore_payloads(
    snapshots: dict[Path, bytes | None],
    written: Iterable[_Payload],
) -> None:
    conflicts: list[str] = []
    for payload in reversed(list(written)):
        current = payload.destination.read_bytes() if payload.destination.exists() else None
        if current != payload.content:
            conflicts.append(str(payload.destination))
            continue
        original = snapshots[payload.destination]
        if original is None:
            payload.destination.unlink(missing_ok=True)
        else:
            _atomic_write(payload.destination, original, payload.mode)
    if conflicts:
        raise RuntimeError(
            "rollback conflict; concurrently changed managed files: " + ", ".join(conflicts)
        )


def install_managed_files(
    repo_root: str | Path,
    paths: RuntimePaths,
    *,
    activate: bool,
    approval_marker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if activate and (
        not isinstance(approval_marker, dict)
        or approval_marker.get("schema") != APPROVAL_SCHEMA
        or not approval_marker.get("approval_id")
        or not approval_marker.get("digest")
    ):
        raise ValueError("activation requires a verified owner approval marker")
    repo_root = Path(repo_root)
    payloads = _managed_payloads(repo_root, paths, activate)
    snapshots = {
        payload.destination: (
            payload.destination.read_bytes() if payload.destination.exists() else None
        )
        for payload in payloads
    }
    written: list[_Payload] = []
    try:
        for payload in payloads:
            _atomic_write(payload.destination, payload.content, payload.mode)
            written.append(payload)
    except Exception:
        _restore_payloads(snapshots, written)
        raise
    return {
        "ok": True,
        "enabled": bool(activate),
        "installed": [str(payload.destination) for payload in payloads],
    }


def _configured_basic_owner() -> str:
    env_owner = os.environ.get("HERMES_DASHBOARD_BASIC_AUTH_USERNAME", "").strip()
    if env_owner:
        return env_owner
    try:
        from hermes_cli.config import cfg_get, load_config

        section = cfg_get(load_config(), "dashboard", "basic_auth", default=None)
    except Exception:
        return ""
    if not isinstance(section, dict):
        return ""
    return str(section.get("username") or "").strip()


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any, *, allow_empty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_nonempty_string(item) for item in value)
    )



# Governance surfaces (ADR D3): a worker finalization may never change the
# rules that judge workers. Changes to these paths are owner-committed only,
# so an approval contract whose diff touches them is refused outright.
GOVERNANCE_PATHS = (
    "pda_charter.md",
    "conftest.py",
    "continuity/autonomous-improvement.json",
    "profiles/pda/managed-habits.json",
    "profiles/pda/skills/pda-autonomous-improvement/",
    "docs/design/self-improvement-governance-adr.md",
    "docs/design/task-scope-admission-gate.md",
    "docs/roadmap/autonomous-improvement-goal.md",
    "docs/roadmap/autonomous-improvement-operating-rules.md",
    "docs/roadmap/current-priority.md",
    "docs/operations/adversarial-suite.md",
    "integrations/hermes-kanban-governance/",
    "integrations/hermes-scope-gate/",
    "integrations/hermes-pda-approvals/",
    "operations/improvement/",
    "infra/systemd/",
)


def _is_governance_path(path: str) -> bool:
    normalized = path.strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    # Any conftest.py anywhere is part of the test-isolation guard (C7).
    if Path(normalized).name == "conftest.py":
        return True
    for entry in GOVERNANCE_PATHS:
        if entry.endswith("/"):
            if normalized.startswith(entry):
                return True
        elif normalized == entry:
            return True
    return False


def _validate_approval_contract(task_id: str, value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["pda_approval metadata is missing"]
    if value.get("schema_version") != APPROVAL_METADATA_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {APPROVAL_METADATA_SCHEMA_VERSION}"
        )
    if value.get("task_id") != task_id:
        errors.append("task_id does not match the review card")
    expected_branch = f"pda-auto/{task_id}"
    if value.get("branch_name") != expected_branch:
        errors.append(f"branch_name must be {expected_branch}")
    path_value = value.get("workspace_path")
    if (
        not _nonempty_string(path_value)
        or not Path(str(path_value)).expanduser().is_absolute()
    ):
        errors.append("workspace_path must be an absolute path")
    # Judgment A (2026-08-23): the canonical Git identities are derived by the
    # approval gate and live on the ledger row, never inside the worker object
    # or the approved digest. A declaration here would be unvalidated data.
    for key in GATE_DERIVED_IDENTITY_KEYS:
        if key in value:
            errors.append(f"{key} must not be declared; the gate derives it")
    for key in ("owner_outcome", "impact"):
        if not _nonempty_string(value.get(key)):
            errors.append(f"{key} is required")
    for key in ("base_sha", "head_sha"):
        sha = value.get(key)
        if not isinstance(sha, str) or _SHA_RE.fullmatch(sha) is None:
            errors.append(f"{key} must be a full hexadecimal Git SHA")
    changed_files = value.get("changed_files")
    if not isinstance(changed_files, list) or not _string_list(changed_files):
        errors.append("changed_files must be a string list")
    elif len(set(changed_files)) != len(changed_files):
        errors.append("changed_files must not contain duplicates")
    else:
        for changed in changed_files:
            path = Path(changed)
            if path.is_absolute() or ".." in path.parts or any(
                ord(char) < 32 for char in changed
            ):
                errors.append("changed_files contains an unsafe path")
                break
    if isinstance(changed_files, list) and _string_list(changed_files):
        governance_hits = sorted(
            {changed for changed in changed_files if _is_governance_path(changed)}
        )
        if governance_hits:
            errors.append(
                "changed_files touches governance paths (owner-committed "
                "changes only): " + ", ".join(governance_hits[:3])
            )
    if not _string_list(value.get("residual_risks")):
        errors.append("residual_risks must be a string list")
    if value.get("risk_class") not in _ALLOWED_RISK_CLASSES:
        errors.append("risk_class is invalid")
    verification = value.get("verification")
    if not isinstance(verification, list) or not verification:
        errors.append("verification must contain at least one check")
    else:
        for index, check in enumerate(verification):
            if not isinstance(check, dict):
                errors.append(f"verification[{index}] must be an object")
                continue
            if not _nonempty_string(check.get("command")):
                errors.append(f"verification[{index}].command is required")
            if check.get("outcome") != "passed":
                errors.append(f"verification[{index}] must have outcome=passed")

    # ADR D2 (2026-08-22 owner decision): every change carries an independent
    # verification report. NOTE the current guarantee honestly: until the M2
    # verifier stage exists, these are self-declared labels checked for
    # internal consistency (verifier != implementer, verified_head_sha bound
    # to the real Git HEAD) — they do not yet prove a separate principal ran
    # the verification. Task-bound identity cross-checks happen in
    # _verify_approved_artifact where the task row is available.
    independent = value.get("independent_verification")
    if not isinstance(independent, dict):
        errors.append("independent_verification is required for every change")
    else:
        for key in ("verifier", "implementer", "summary"):
            if not _nonempty_string(independent.get(key)):
                errors.append(f"independent_verification.{key} is required")
        if (
            _nonempty_string(independent.get("verifier"))
            and _nonempty_string(independent.get("implementer"))
            and str(independent.get("verifier")).strip()
            == str(independent.get("implementer")).strip()
        ):
            errors.append(
                "independent_verification.verifier must differ from the implementer"
            )
        if independent.get("verdict") != "pass":
            errors.append("independent_verification.verdict must be pass")
        if independent.get("verified_head_sha") != value.get("head_sha"):
            errors.append(
                "independent_verification.verified_head_sha must match head_sha"
            )
        if not _string_list(independent.get("checks"), allow_empty=False):
            errors.append(
                "independent_verification.checks must be a non-empty string list"
            )

    finalization = value.get("finalization")
    if not isinstance(finalization, dict):
        errors.append("finalization is required")
    else:
        if finalization.get("kind") not in _ALLOWED_FINALIZATION_KINDS:
            errors.append("finalization.kind is invalid")
        for key in ("targets", "steps", "rollback"):
            if not _string_list(finalization.get(key), allow_empty=False):
                errors.append(f"finalization.{key} must be a non-empty string list")
    return errors


def verify_owner_approval(
    conn,
    *,
    task_id: str,
    approval_id: str,
    digest: str,
    activation_nonce: str | None = None,
) -> dict[str, Any]:
    task = kanban_db.get_task(conn, task_id)
    if task is None or task.tenant != "pda-improvement":
        raise ValueError("task is not a PDA improvement card")
    try:
        row = conn.execute(
            "SELECT approval_id, task_id, digest, base_sha, head_sha, workspace_path, "
            "branch_name, git_common_dir, git_dir, review_run_id, approved_at, "
            "approved_by_provider, approved_by_user_id, activation_nonce, consumed_at "
            "FROM pda_owner_approvals WHERE approval_id = ? AND task_id = ? "
            "AND digest = ? AND revoked_at IS NULL AND consumed_at IS NULL",
            (approval_id, task_id, digest),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        raise ValueError("owner approval ledger is not installed") from exc
    if row is None:
        raise ValueError("no matching owner approval was found in the control ledger")
    configured_owner = _configured_basic_owner()
    if not configured_owner:
        raise ValueError("configured owner identity is unavailable")
    if (
        row["approved_by_provider"] != "basic"
        or not secrets.compare_digest(
            str(row["approved_by_user_id"] or ""),
            configured_owner,
        )
    ):
        raise ValueError("owner approval ledger entry does not match the configured owner")
    row_nonce = str(row["activation_nonce"] or "")
    if activation_nonce is None and row_nonce:
        raise ValueError("owner approval activation is already in progress")
    if activation_nonce is not None and not secrets.compare_digest(row_nonce, activation_nonce):
        raise ValueError("owner approval activation claim does not match")
    return {
        "schema": APPROVAL_SCHEMA,
        "approval_id": row["approval_id"],
        "task_id": row["task_id"],
        "digest": row["digest"],
        "base_sha": row["base_sha"],
        "head_sha": row["head_sha"],
        "workspace_path": row["workspace_path"],
        "branch_name": row["branch_name"],
        "git_common_dir": row["git_common_dir"],
        "git_dir": row["git_dir"],
        "review_run_id": int(row["review_run_id"]),
        "approved_at": int(row["approved_at"]),
    }


def _decode_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _verify_approved_artifact(conn, task_id: str, marker: dict[str, Any]) -> None:
    task = kanban_db.get_task(conn, task_id)
    if task is None:
        raise ValueError("approved task disappeared")
    if task.status not in {"ready", "running"}:
        raise ValueError("approved task is not in a finalizable state")
    if task.assignee != WORKER_PROFILE:
        raise ValueError("approved task is not assigned to the dedicated finalizer")
    if WORKER_SKILL not in (task.skills or []):
        raise ValueError("approved task is missing the forced finalizer skill")
    row = conn.execute(
        "SELECT id, metadata FROM task_runs WHERE task_id = ? "
        "AND outcome = 'review_requested' ORDER BY id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    if row is None:
        raise ValueError("approved task has no review handoff")
    metadata = _decode_json(row["metadata"])
    approval = metadata.get("pda_approval") if isinstance(metadata, dict) else None
    if not isinstance(approval, dict):
        raise ValueError("approved task has no pda_approval metadata")
    contract_errors = _validate_approval_contract(task_id, approval)
    independent = (
        approval.get("independent_verification")
        if isinstance(approval, dict)
        else None
    )
    if isinstance(independent, dict):
        assignee = str(task.assignee or "default").strip()
        implementer = str(independent.get("implementer") or "").strip()
        verifier = str(independent.get("verifier") or "").strip()
        if implementer and implementer != assignee:
            contract_errors.append(
                "independent_verification.implementer must match the task assignee"
            )
        if verifier and verifier == assignee:
            contract_errors.append(
                "independent_verification.verifier must not be the task assignee"
            )
    if contract_errors:
        raise ValueError("approved approval contract is invalid: " + "; ".join(contract_errors))
    actual_digest = hashlib.sha256(
        json.dumps(
            approval,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if actual_digest != marker.get("digest"):
        raise ValueError("approved review digest has drifted")
    if int(row["id"]) != marker.get("review_run_id"):
        raise ValueError("approved review run has drifted")
    if approval.get("head_sha") != marker.get("head_sha"):
        raise ValueError("approved review head has drifted")
    # The canonical Git identities are absent from the worker object under
    # Judgment A, so they are not cross-checked here. Their drift check is the
    # live re-derivation against the ledger row further down.
    for key in ("base_sha", "workspace_path", "branch_name"):
        if approval.get(key) != marker.get(key):
            raise ValueError(f"approved review {key} has drifted")
    if not task.workspace_path:
        raise ValueError("approved task has no workspace")
    workspace = Path(task.workspace_path).expanduser()
    if not workspace.is_absolute():
        raise ValueError("approved task workspace path must be absolute")
    declared_workspace = Path(str(approval.get("workspace_path") or "")).expanduser()
    lexical_workspace = Path(os.path.abspath(workspace))
    real_workspace = Path(os.path.realpath(workspace))
    if lexical_workspace != real_workspace:
        raise ValueError("approved workspace path contains a symlink")
    if (
        not declared_workspace.is_absolute()
        or lexical_workspace != Path(os.path.abspath(declared_workspace))
    ):
        raise ValueError("approved workspace path has drifted")
    expected_branch = f"pda-auto/{task_id}"
    if approval.get("branch_name") != expected_branch or task.branch_name != expected_branch:
        raise ValueError("approved task branch has drifted")
    top = Path(
        _run(["git", "-C", str(workspace), "rev-parse", "--show-toplevel"], timeout=30)
    ).resolve()
    if top != workspace.resolve():
        raise ValueError("approved workspace is not the worktree root")
    git_dir = Path(
        _run(["git", "-C", str(workspace), "rev-parse", "--git-dir"], timeout=30)
    )
    common_dir = Path(
        _run(["git", "-C", str(workspace), "rev-parse", "--git-common-dir"], timeout=30)
    )
    resolved_git_dir = (
        git_dir if git_dir.is_absolute() else workspace / git_dir
    ).resolve()
    resolved_common_dir = (
        common_dir if common_dir.is_absolute() else workspace / common_dir
    ).resolve()
    if resolved_git_dir == resolved_common_dir:
        raise ValueError("approved workspace is not a linked worktree")
    # Judgment A: the second point of the two-point drift check. The approval
    # gate derived these identities at approval time and wrote them to the
    # ledger row that `marker` is built from; this re-derivation at consume
    # time must still agree with it. Comparing against `approval` here would
    # compare against a key the worker no longer supplies.
    if str(resolved_git_dir) != marker.get("git_dir"):
        raise ValueError("approved workspace git_dir has drifted")
    if str(resolved_common_dir) != marker.get("git_common_dir"):
        raise ValueError("approved workspace git_common_dir has drifted")
    actual_branch = _run(
        ["git", "-C", str(workspace), "branch", "--show-current"], timeout=30
    )
    if actual_branch != expected_branch:
        raise ValueError("approved workspace branch has drifted")
    head = _run(["git", "-C", str(workspace), "rev-parse", "HEAD"], timeout=30)
    if head != marker.get("head_sha"):
        raise ValueError("approved workspace HEAD has drifted")
    if _run(["git", "-C", str(workspace), "status", "--porcelain"], timeout=30):
        raise ValueError("approved workspace is dirty")
    base = str(approval["base_sha"])
    ancestry = subprocess.run(
        ["git", "-C", str(workspace), "merge-base", "--is-ancestor", base, head],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    if ancestry.returncode != 0:
        raise ValueError("approved base_sha is not an ancestor of head_sha")
    diff = subprocess.run(
        ["git", "-C", str(workspace), "diff", "--no-renames", "--name-only", "-z", base, head],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if diff.returncode != 0:
        raise ValueError("approved Git changed-file verification failed")
    try:
        actual_files = sorted(
            item.decode("utf-8") for item in diff.stdout.split(b"\0") if item
        )
    except UnicodeDecodeError as exc:
        raise ValueError("approved Git diff contains a non-UTF-8 path") from exc
    if actual_files != sorted(approval["changed_files"]):
        raise ValueError("approved changed_files do not match the Git diff")


def _run(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: int = 120,
) -> str:
    result = subprocess.run(
        args,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=timeout,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise RuntimeError(f"{' '.join(args[:3])}: {detail}")
    return result.stdout.strip()


def _default_env(paths: RuntimePaths) -> dict[str, str]:
    env = os.environ.copy()
    for name in KANBAN_ENV_OVERRIDES:
        env.pop(name, None)
    env["HERMES_HOME"] = str(paths.hermes_home)
    env["HERMES_PROFILE"] = "default"
    return env


def _enable_dashboard_plugin(paths: RuntimePaths, hermes_bin: str) -> None:
    _run(
        [hermes_bin, "plugins", "enable", PLUGIN_NAME, "--no-allow-tool-override"],
        env=_default_env(paths),
    )


def _set_human_review(paths: RuntimePaths, hermes_bin: str) -> None:
    _run(
        [hermes_bin, "config", "set", "kanban.review_dispatch", "false"],
        env=_default_env(paths),
    )


def _daily_reconciler_job_id(repo_root: Path) -> str:
    desired = json.loads(
        (repo_root / "continuity" / "autonomous-improvement.json").read_text(encoding="utf-8")
    )
    return str(desired["daily_reconciler_job_id"])


def _read_daily_reconciler_state(paths: RuntimePaths, job_id: str) -> dict[str, Any]:
    jobs_path = paths.hermes_home / "cron" / "jobs.json"
    document = json.loads(jobs_path.read_text(encoding="utf-8"))
    jobs = document.get("jobs") if isinstance(document, dict) else None
    if not isinstance(jobs, list):
        raise ValueError("cron jobs.json has no jobs list")
    job = next((item for item in jobs if isinstance(item, dict) and item.get("id") == job_id), None)
    if job is None:
        raise ValueError(f"daily reconciler cron job is missing: {job_id}")
    return {
        "schema_version": 1,
        "job_id": job_id,
        "prompt": str(job.get("prompt") or ""),
        "skills": [str(skill) for skill in (job.get("skills") or [])],
        "workdir": job.get("workdir"),
        "continuity": "self" in (job.get("context_from") or []),
    }


def _desired_daily_reconciler_state(repo_root: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "job_id": _daily_reconciler_job_id(repo_root),
        "prompt": (
            repo_root / "operations" / "improvement" / "daily_reconciler_prompt.txt"
        ).read_text(encoding="utf-8"),
        "skills": [
            "workstream-reconciliation",
            "task-scope-control",
            "pda-user-escalation",
            WORKER_SKILL,
        ],
        "workdir": str(repo_root),
        "continuity": True,
    }


def _apply_daily_reconciler_state(
    state: dict[str, Any],
    paths: RuntimePaths,
    hermes_bin: str,
) -> None:
    command = [
        hermes_bin,
        "cron",
        "edit",
        str(state["job_id"]),
        "--prompt",
        str(state.get("prompt") or ""),
    ]
    skills = [str(skill) for skill in (state.get("skills") or [])]
    if skills:
        for skill in skills:
            command.extend(["--skill", skill])
    else:
        command.append("--clear-skills")
    command.extend(["--workdir", str(state.get("workdir") or "")])
    command.append("--continuity" if state.get("continuity") else "--no-continuity")
    _run(command, env=_default_env(paths))


def _snapshot_daily_reconciler(repo_root: Path, paths: RuntimePaths) -> dict[str, Any]:
    job_id = _daily_reconciler_job_id(repo_root)
    if paths.cron_rollback.exists():
        existing = json.loads(paths.cron_rollback.read_text(encoding="utf-8"))
        if not isinstance(existing, dict) or existing.get("job_id") != job_id:
            raise ValueError("existing cron rollback snapshot does not match this activation")
        return existing
    snapshot = _read_daily_reconciler_state(paths, job_id)
    _atomic_write(
        paths.cron_rollback,
        (json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        0o600,
    )
    return snapshot


def stage_runtime(
    repo_root: Path,
    paths: RuntimePaths,
    *,
    hermes_bin: str = "hermes",
) -> dict[str, Any]:
    result = install_managed_files(repo_root, paths, activate=False)
    _enable_dashboard_plugin(paths, hermes_bin)
    _set_human_review(paths, hermes_bin)
    _run(["systemctl", "--user", "daemon-reload"])
    _run(["systemctl", "--user", "enable", "--now", "pda-improvement-cycle.timer"])
    _run(["systemctl", "--user", "restart", "hermes-dashboard.service"])
    active = _run(["systemctl", "--user", "is-active", "hermes-dashboard.service"])
    enabled = _run(["systemctl", "--user", "is-enabled", "pda-improvement-cycle.timer"])
    result.update(
        {
            "worker_profile": WORKER_PROFILE,
            "dashboard": active,
            "timer": enabled,
            "mode": "staged",
        }
    )
    return result


def rollback_runtime(
    repo_root: Path,
    paths: RuntimePaths,
    *,
    hermes_bin: str = "hermes",
) -> dict[str, Any]:
    if not paths.cron_rollback.is_file():
        raise ValueError("cron rollback snapshot is missing")
    prior_cron = json.loads(paths.cron_rollback.read_text(encoding="utf-8"))
    expected_job = _daily_reconciler_job_id(repo_root)
    if not isinstance(prior_cron, dict) or prior_cron.get("job_id") != expected_job:
        raise ValueError("cron rollback snapshot does not match this installation")
    _run(["systemctl", "--user", "stop", "pda-improvement-cycle.timer"])
    result = install_managed_files(repo_root, paths, activate=False)
    _apply_daily_reconciler_state(prior_cron, paths, hermes_bin)
    _enable_dashboard_plugin(paths, hermes_bin)
    _set_human_review(paths, hermes_bin)
    _run(["systemctl", "--user", "daemon-reload"])
    _run(["systemctl", "--user", "enable", "--now", "pda-improvement-cycle.timer"])
    result.update(
        {
            "mode": "rolled-back",
            "cron_restored_from": str(paths.cron_rollback),
            "timer_mode": "enabled-noop",
        }
    )
    return result


@contextlib.contextmanager
def _control_board(paths: RuntimePaths):
    saved = {
        name: os.environ.pop(name, None)
        for name in ("HERMES_HOME", *KANBAN_ENV_OVERRIDES)
    }
    os.environ["HERMES_HOME"] = str(paths.hermes_home)
    try:
        kanban_db.init_db()
        with kanban_db.connect_closing() as conn:
            yield conn
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def check_approval_runtime(
    paths: RuntimePaths,
    *,
    task_id: str,
    approval_id: str,
    digest: str,
) -> dict[str, Any]:
    with _control_board(paths) as conn:
        marker = verify_owner_approval(
            conn,
            task_id=task_id,
            approval_id=approval_id,
            digest=digest,
        )
        _verify_approved_artifact(conn, task_id, marker)
    return {"ok": True, "mode": "checked", "approval": marker}


def _claim_approval_activation(
    paths: RuntimePaths,
    *,
    task_id: str,
    approval_id: str,
    digest: str,
    activation_nonce: str | None = None,
) -> str:
    nonce = activation_nonce or ("act_" + secrets.token_hex(16))
    with _control_board(paths) as conn:
        with kanban_db.write_txn(conn):
            marker = verify_owner_approval(
                conn,
                task_id=task_id,
                approval_id=approval_id,
                digest=digest,
            )
            _verify_approved_artifact(conn, task_id, marker)
            updated = conn.execute(
                "UPDATE pda_owner_approvals SET activation_nonce = ?, "
                "activation_started_at = ? WHERE approval_id = ? AND task_id = ? "
                "AND digest = ? AND revoked_at IS NULL AND consumed_at IS NULL "
                "AND activation_nonce IS NULL",
                (nonce, int(time.time()), approval_id, task_id, digest),
            )
            if updated.rowcount != 1:
                raise ValueError("owner approval activation claim raced or was consumed")
    return nonce


def _recheck_activation_claim(
    paths: RuntimePaths,
    *,
    task_id: str,
    approval_id: str,
    digest: str,
    activation_nonce: str,
) -> dict[str, Any]:
    with _control_board(paths) as conn:
        marker = verify_owner_approval(
            conn,
            task_id=task_id,
            approval_id=approval_id,
            digest=digest,
            activation_nonce=activation_nonce,
        )
        _verify_approved_artifact(conn, task_id, marker)
    return marker


def _finish_activation_claim(
    paths: RuntimePaths,
    *,
    task_id: str,
    approval_id: str,
    digest: str,
    activation_nonce: str,
) -> None:
    with _control_board(paths) as conn:
        with kanban_db.write_txn(conn):
            marker = verify_owner_approval(
                conn,
                task_id=task_id,
                approval_id=approval_id,
                digest=digest,
                activation_nonce=activation_nonce,
            )
            _verify_approved_artifact(conn, task_id, marker)
            updated = conn.execute(
                "UPDATE pda_owner_approvals SET consumed_at = ?, activation_nonce = NULL "
                "WHERE approval_id = ? AND task_id = ? AND digest = ? "
                "AND activation_nonce = ? AND revoked_at IS NULL AND consumed_at IS NULL",
                (
                    int(time.time()),
                    approval_id,
                    task_id,
                    digest,
                    activation_nonce,
                ),
            )
            if updated.rowcount != 1:
                raise ValueError("owner approval activation completion lost its claim")


def _release_activation_claim(
    paths: RuntimePaths,
    *,
    task_id: str,
    approval_id: str,
    digest: str,
    activation_nonce: str,
) -> None:
    with _control_board(paths) as conn:
        with kanban_db.write_txn(conn):
            updated = conn.execute(
                "UPDATE pda_owner_approvals SET activation_nonce = NULL, "
                "activation_started_at = NULL WHERE approval_id = ? AND task_id = ? "
                "AND digest = ? AND activation_nonce = ? AND consumed_at IS NULL",
                (approval_id, task_id, digest, activation_nonce),
            )
            if updated.rowcount != 1:
                raise ValueError("owner approval activation rollback lost its claim")


def _recover_stale_activation_claim(
    paths: RuntimePaths,
    *,
    task_id: str,
    approval_id: str,
    digest: str,
    min_age_seconds: int = ACTIVATION_CLAIM_STALE_SECONDS,
) -> str:
    min_age_seconds = max(0, int(min_age_seconds))
    with _control_board(paths) as conn:
        with kanban_db.write_txn(conn):
            row = conn.execute(
                "SELECT activation_nonce, activation_started_at "
                "FROM pda_owner_approvals WHERE approval_id = ? AND task_id = ? "
                "AND digest = ? AND revoked_at IS NULL AND consumed_at IS NULL "
                "AND activation_nonce IS NOT NULL",
                (approval_id, task_id, digest),
            ).fetchone()
            if row is None:
                raise ValueError("no in-progress owner approval activation claim was found")
            nonce = str(row["activation_nonce"] or "")
            started_at = int(row["activation_started_at"] or 0)
            if not nonce or started_at <= 0:
                raise ValueError("activation claim has no valid nonce or start time")
            if int(time.time()) - started_at < min_age_seconds:
                raise ValueError("activation claim is not old enough for recovery")
            marker = verify_owner_approval(
                conn,
                task_id=task_id,
                approval_id=approval_id,
                digest=digest,
                activation_nonce=nonce,
            )
            _verify_approved_artifact(conn, task_id, marker)
            updated = conn.execute(
                "UPDATE pda_owner_approvals SET activation_nonce = NULL, "
                "activation_started_at = NULL WHERE approval_id = ? AND task_id = ? "
                "AND digest = ? AND activation_nonce = ? AND consumed_at IS NULL",
                (approval_id, task_id, digest, nonce),
            )
            if updated.rowcount != 1:
                raise ValueError("stale activation claim recovery lost its CAS")
    return nonce


def recover_activation_claim_runtime(
    paths: RuntimePaths,
    *,
    task_id: str,
    approval_id: str,
    digest: str,
) -> dict[str, Any]:
    runtime = json.loads(paths.runtime_config.read_text(encoding="utf-8"))
    if not isinstance(runtime, dict) or runtime.get("enabled") is not False:
        raise ValueError("runtime must be explicitly disabled before claim recovery")
    _run(["systemctl", "--user", "stop", "pda-improvement-cycle.timer"])
    nonce = _recover_stale_activation_claim(
        paths,
        task_id=task_id,
        approval_id=approval_id,
        digest=digest,
    )
    _run(["systemctl", "--user", "enable", "--now", "pda-improvement-cycle.timer"])
    return {
        "ok": True,
        "mode": "claim-recovered",
        "task_id": task_id,
        "approval_id": approval_id,
        "released_nonce": nonce,
        "timer_mode": "enabled-noop",
    }


def activate_runtime(
    repo_root: Path,
    paths: RuntimePaths,
    *,
    task_id: str,
    approval_id: str,
    digest: str,
    hermes_bin: str = "hermes",
) -> dict[str, Any]:
    checked = check_approval_runtime(
        paths,
        task_id=task_id,
        approval_id=approval_id,
        digest=digest,
    )
    marker = checked["approval"]

    prior_cron = _snapshot_daily_reconciler(repo_root, paths)
    desired_cron = _desired_daily_reconciler_state(repo_root)
    cron_attempted = False
    active_files_written = False
    activation_nonce: str | None = None
    activation_finished = False
    try:
        # The staged timer is stopped while policy and runtime state cross the
        # approval boundary, so no tick can observe a half-applied activation.
        _run(["systemctl", "--user", "stop", "pda-improvement-cycle.timer"])
        rechecked = check_approval_runtime(
            paths,
            task_id=task_id,
            approval_id=approval_id,
            digest=digest,
        )
        marker = rechecked["approval"]
        activation_nonce = "act_" + secrets.token_hex(16)
        _claim_approval_activation(
            paths,
            task_id=task_id,
            approval_id=approval_id,
            digest=digest,
            activation_nonce=activation_nonce,
        )
        cron_attempted = True
        _apply_daily_reconciler_state(desired_cron, paths, hermes_bin)
        result = install_managed_files(
            repo_root,
            paths,
            activate=True,
            approval_marker=marker,
        )
        active_files_written = True
        _enable_dashboard_plugin(paths, hermes_bin)
        _set_human_review(paths, hermes_bin)
        _run(["systemctl", "--user", "daemon-reload"])
        # Reload the approval dashboard so the freshly deployed
        # validator (not a stale in-memory copy) judges /pending.
        _run(["systemctl", "--user", "restart", "hermes-dashboard.service"])
        marker = _recheck_activation_claim(
            paths,
            task_id=task_id,
            approval_id=approval_id,
            digest=digest,
            activation_nonce=activation_nonce,
        )
        _run(["systemctl", "--user", "enable", "--now", "pda-improvement-cycle.timer"])
        _run(["systemctl", "--user", "start", "pda-improvement-cycle.service"])
        service_result = _run(
            [
                "systemctl",
                "--user",
                "show",
                "pda-improvement-cycle.service",
                "-p",
                "Result",
                "--value",
            ]
        )
        if service_result != "success":
            raise RuntimeError(f"improvement-cycle service result is {service_result!r}")
        marker = _recheck_activation_claim(
            paths,
            task_id=task_id,
            approval_id=approval_id,
            digest=digest,
            activation_nonce=activation_nonce,
        )
        _finish_activation_claim(
            paths,
            task_id=task_id,
            approval_id=approval_id,
            digest=digest,
            activation_nonce=activation_nonce,
        )
        activation_finished = True
    except Exception as exc:
        rollback_errors: list[str] = []
        if active_files_written:
            try:
                install_managed_files(repo_root, paths, activate=False)
            except Exception as rollback_exc:
                rollback_errors.append(f"runtime-disable rollback failed: {rollback_exc}")
        if cron_attempted:
            try:
                _apply_daily_reconciler_state(prior_cron, paths, hermes_bin)
            except Exception as rollback_exc:
                rollback_errors.append(f"cron rollback failed: {rollback_exc}")
        if (
            activation_nonce is not None
            and not activation_finished
            and not rollback_errors
        ):
            try:
                _release_activation_claim(
                    paths,
                    task_id=task_id,
                    approval_id=approval_id,
                    digest=digest,
                    activation_nonce=activation_nonce,
                )
            except Exception as rollback_exc:
                rollback_errors.append(f"approval-claim rollback failed: {rollback_exc}")
        if rollback_errors:
            try:
                _run(["systemctl", "--user", "stop", "pda-improvement-cycle.timer"])
            except Exception as rollback_exc:
                rollback_errors.append(f"timer stop after rollback conflict failed: {rollback_exc}")
        else:
            try:
                _run(
                    ["systemctl", "--user", "enable", "--now", "pda-improvement-cycle.timer"]
                )
            except Exception as rollback_exc:
                rollback_errors.append(f"timer recovery failed: {rollback_exc}")
        if rollback_errors:
            raise RuntimeError(f"activation failed: {exc}; " + "; ".join(rollback_errors)) from exc
        raise
    result.update(
        {
            "mode": "active",
            "approval": marker,
            "cycle_service_result": service_result,
            "cron_rollback": str(paths.cron_rollback),
        }
    )
    return result


def _resolve_python_executable(
    hermes_home: Path,
    override: str | None,
) -> Path:
    candidate = (
        Path(override).expanduser()
        if override
        else hermes_home / "hermes-agent" / "venv" / "bin" / "python"
    )
    candidate = Path(os.path.abspath(candidate))
    if not candidate.is_file():
        raise ValueError(f"Hermes Python executable is missing: {candidate}")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--stage", action="store_true")
    mode.add_argument("--activate", action="store_true")
    mode.add_argument("--check-approval", action="store_true")
    mode.add_argument("--rollback-activation", action="store_true")
    mode.add_argument("--recover-activation-claim", action="store_true")
    parser.add_argument("--repo", default=str(Path(__file__).parents[2]))
    parser.add_argument("--home", default=str(Path.home()))
    parser.add_argument("--hermes-home", default=None)
    parser.add_argument("--python", default=None)
    parser.add_argument("--hermes-bin", default="hermes")
    parser.add_argument("--task-id")
    parser.add_argument("--approval-id")
    parser.add_argument("--digest")
    args = parser.parse_args(argv)

    home = Path(args.home).expanduser().resolve()
    hermes_home = (
        Path(args.hermes_home).expanduser().resolve()
        if args.hermes_home
        else home / ".hermes"
    )
    paths = RuntimePaths(
        home=home,
        hermes_home=hermes_home,
        python_executable=_resolve_python_executable(hermes_home, args.python),
    )
    repo_root = Path(args.repo).expanduser().resolve()
    try:
        if args.stage:
            result = stage_runtime(repo_root, paths, hermes_bin=args.hermes_bin)
        elif args.rollback_activation:
            result = rollback_runtime(repo_root, paths, hermes_bin=args.hermes_bin)
        elif args.recover_activation_claim:
            if not all((args.task_id, args.approval_id, args.digest)):
                parser.error(
                    "--recover-activation-claim requires --task-id, "
                    "--approval-id, and --digest"
                )
            result = recover_activation_claim_runtime(
                paths,
                task_id=args.task_id,
                approval_id=args.approval_id,
                digest=args.digest,
            )
        else:
            if not all((args.task_id, args.approval_id, args.digest)):
                parser.error(
                    "--activate/--check-approval requires --task-id, --approval-id, and --digest"
                )
            if args.check_approval:
                result = check_approval_runtime(
                    paths,
                    task_id=args.task_id,
                    approval_id=args.approval_id,
                    digest=args.digest,
                )
            else:
                result = activate_runtime(
                    repo_root,
                    paths,
                    task_id=args.task_id,
                    approval_id=args.approval_id,
                    digest=args.digest,
                    hermes_bin=args.hermes_bin,
                )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "mode": (
                        "stage"
                        if args.stage
                        else "rollback"
                        if args.rollback_activation
                        else "claim-recovery"
                        if args.recover_activation_claim
                        else "check"
                        if args.check_approval
                        else "activate"
                    ),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
