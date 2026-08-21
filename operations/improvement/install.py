"""Install and activate the PDA autonomous improvement control plane."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from hermes_cli import kanban_db


PLUGIN_NAME = "pda-approvals"
WORKER_PROFILE = "default"
WORKER_SKILL = "pda-autonomous-improvement"
OWNER_APPROVAL_AUTHOR = "pda-owner-approval"
APPROVAL_SCHEMA = "PDA_OWNER_APPROVAL_V1"


@dataclass(frozen=True)
class RuntimePaths:
    home: Path
    hermes_home: Path
    python_executable: Path

    @property
    def runtime_config(self) -> Path:
        return self.home / ".config" / "pda" / "autonomous-improvement.json"

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
    desired["enabled"] = bool(activate)
    runtime_config = (json.dumps(desired, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    service_template = (
        repo_root / "infra" / "systemd" / "pda-improvement-cycle.service.in"
    ).read_text(encoding="utf-8")
    service = service_template.replace("@PYTHON@", str(paths.python_executable))

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


def _decode_marker(body: str) -> dict[str, Any] | None:
    if "\n" not in body:
        return None
    try:
        value = json.loads(body.split("\n", 1)[1])
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def verify_owner_approval(
    conn,
    *,
    task_id: str,
    approval_id: str,
    digest: str,
) -> dict[str, Any]:
    task = kanban_db.get_task(conn, task_id)
    if task is None or task.tenant != "pda-improvement":
        raise ValueError("task is not a PDA improvement card")
    comments = kanban_db.list_comments(conn, task_id)
    for comment in reversed(comments):
        if comment.author != OWNER_APPROVAL_AUTHOR:
            continue
        marker = _decode_marker(comment.body)
        if not marker:
            continue
        if (
            marker.get("schema") == APPROVAL_SCHEMA
            and marker.get("task_id") == task_id
            and marker.get("approval_id") == approval_id
            and marker.get("digest") == digest
        ):
            return marker
    raise ValueError("no matching owner approval was found")


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
    if not task.workspace_path:
        raise ValueError("approved task has no workspace")
    workspace = Path(task.workspace_path).expanduser()
    head = _run(["git", "-C", str(workspace), "rev-parse", "HEAD"], timeout=30)
    if head != marker.get("head_sha"):
        raise ValueError("approved workspace HEAD has drifted")
    if _run(["git", "-C", str(workspace), "status", "--porcelain"], timeout=30):
        raise ValueError("approved workspace is dirty")


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


def _update_daily_reconciler(repo_root: Path, paths: RuntimePaths, hermes_bin: str) -> None:
    desired = json.loads(
        (repo_root / "continuity" / "autonomous-improvement.json").read_text(encoding="utf-8")
    )
    job_id = str(desired["daily_reconciler_job_id"])
    prompt = (
        repo_root / "operations" / "improvement" / "daily_reconciler_prompt.txt"
    ).read_text(encoding="utf-8")
    _run(
        [
            hermes_bin,
            "cron",
            "edit",
            job_id,
            "--prompt",
            prompt,
            "--skill",
            "workstream-reconciliation",
            "--skill",
            "task-scope-control",
            "--skill",
            "pda-user-escalation",
            "--skill",
            WORKER_SKILL,
            "--workdir",
            str(repo_root),
            "--continuity",
        ],
        env=_default_env(paths),
    )


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


def activate_runtime(
    repo_root: Path,
    paths: RuntimePaths,
    *,
    task_id: str,
    approval_id: str,
    digest: str,
    hermes_bin: str = "hermes",
) -> dict[str, Any]:
    # Always use the shared control home rather than any ambient profile path.
    old_home = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(paths.hermes_home)
    try:
        kanban_db.init_db()
        with kanban_db.connect_closing() as conn:
            marker = verify_owner_approval(
                conn,
                task_id=task_id,
                approval_id=approval_id,
                digest=digest,
            )
            _verify_approved_artifact(conn, task_id, marker)
    finally:
        if old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = old_home

    result = install_managed_files(
        repo_root,
        paths,
        activate=True,
        approval_marker=marker,
    )
    _enable_dashboard_plugin(paths, hermes_bin)
    _set_human_review(paths, hermes_bin)
    _update_daily_reconciler(repo_root, paths, hermes_bin)
    _run(["systemctl", "--user", "daemon-reload"])
    _run(["systemctl", "--user", "enable", "--now", "pda-improvement-cycle.timer"])
    _run(["systemctl", "--user", "start", "pda-improvement-cycle.service"])
    service_result = _run(
        ["systemctl", "--user", "show", "pda-improvement-cycle.service", "-p", "Result", "--value"]
    )
    if service_result != "success":
        raise RuntimeError(f"improvement-cycle service result is {service_result!r}")
    result.update(
        {
            "mode": "active",
            "approval": marker,
            "cycle_service_result": service_result,
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
        else:
            if not all((args.task_id, args.approval_id, args.digest)):
                parser.error("--activate requires --task-id, --approval-id, and --digest")
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
                {"ok": False, "error": str(exc), "mode": "stage" if args.stage else "activate"},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
