from __future__ import annotations

import ctypes
import errno
import fcntl
import grp
import hashlib
import json
import os
import posixpath
import pwd
import re
import shlex
import shutil
import sqlite3
import stat
import subprocess
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from zoneinfo import ZoneInfo


class BackupError(RuntimeError):
    """Raised when a continuity snapshot cannot be completed safely."""


SOURCE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
MANAGED_ROOT_MARKER = ".pda-local-backup-root.json"
MANAGED_ROOT_CONTRACT = {
    "format": "pda-local-continuity-backup-root",
    "schema_version": 1,
}
STAGING_MARKER = ".pda-staging.json"
STAGING_CONTRACT = {
    "format": "pda-local-continuity-staging",
    "schema_version": 1,
}
STAGING_NAME = re.compile(
    r"\.\d{4}-\d{2}-\d{2}T\d{6}[+-]\d{4}(?:-[0-9a-f]{8})?-[0-9a-f]{32}\Z"
)
SUBPROCESS_TIMEOUT_SECONDS = 12 * 60 * 60
SQLITE_BUSY_TIMEOUT_SECONDS = 5 * 60
SQLITE_OPERATION_TIMEOUT_SECONDS = 6 * 60 * 60
CONTAINER_READY_TIMEOUT_SECONDS = 30 * 60
CONTAINER_READY_POLL_SECONDS = 15
CONTAINER_PROBE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class SourceConfig:
    name: str
    kind: str
    path: Path | None
    sqlite: str
    allowed_special_files: tuple[tuple[str, str], ...] = ()
    container: str | None = None
    container_path: str | None = None


class ContainerClient(Protocol):
    def wait_until_ready(self, container: str) -> None: ...

    def export_tree(
        self, container: str, container_path: str, destination: Path
    ) -> None: ...

    def backup_sqlite(
        self,
        container: str,
        container_path: str,
        relative_path: str,
        destination: Path,
    ) -> None: ...


class DockerContainerClient:
    _PREPARE_TEMP_SCRIPT = """
import os
import re
import shutil
import stat
import sys
import time
from pathlib import Path

temporary = Path(sys.argv[1])
pattern = re.compile(r"pda-continuity-[0-9a-f]{32}\\Z")
now = time.time()
for candidate in Path("/tmp").iterdir():
    if pattern.fullmatch(candidate.name) is None:
        continue
    try:
        metadata = candidate.lstat()
    except FileNotFoundError:
        continue
    marker = candidate / ".pda-owned"
    if (
        stat.S_ISDIR(metadata.st_mode)
        and not candidate.is_symlink()
        and marker.is_file()
        and now - metadata.st_mtime > 86400
    ):
        shutil.rmtree(candidate)
os.mkdir(temporary, 0o700)
descriptor = os.open(
    temporary / ".pda-owned", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
)
os.close(descriptor)
""".strip()

    _SQLITE_BACKUP_SCRIPT = """
import os
import sqlite3
import sys
import time
from pathlib import Path

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
os.umask(0o077)
descriptor = os.open(
    destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
)
os.close(descriptor)
source_uri = source.resolve().as_uri() + "?mode=ro"
deadline = time.monotonic() + 21600
def backup_progress(status, remaining, total):
    if time.monotonic() >= deadline:
        raise TimeoutError("SQLite backup timed out")
with sqlite3.connect(source_uri, uri=True, timeout=300) as source_connection:
    with sqlite3.connect(destination, timeout=300) as destination_connection:
        source_connection.backup(
            destination_connection, pages=1024, progress=backup_progress, sleep=0.25
        )
        destination_connection.execute("PRAGMA journal_mode=DELETE")
with sqlite3.connect(destination.resolve().as_uri() + "?mode=ro", uri=True) as check:
    check.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10000)
    if check.execute("PRAGMA integrity_check").fetchone() != ("ok",):
        raise RuntimeError("SQLite integrity check failed")
    if check.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise RuntimeError("SQLite foreign key check failed")
os.chmod(destination, 0o600)
""".strip()

    _CLEANUP_SCRIPT = """
import re
import shutil
import stat
import sys
from pathlib import Path

path = Path(sys.argv[1])
if (
    path.parent == Path("/tmp")
    and re.fullmatch(r"pda-continuity-[0-9a-f]{32}", path.name)
    and path.exists()
    and not path.is_symlink()
    and stat.S_ISDIR(path.lstat().st_mode)
    and (path / ".pda-owned").is_file()
):
    shutil.rmtree(path)
""".strip()

    def __init__(self, docker_binary: str = "docker", group: str = "docker") -> None:
        self.docker_binary = docker_binary
        self.group = group

    def wait_until_ready(self, container: str) -> None:
        deadline = _monotonic() + CONTAINER_READY_TIMEOUT_SECONDS
        last_error = "container is not ready"
        while True:
            try:
                running = self._run(
                    ["inspect", "--format={{.State.Running}}", container],
                    timeout=CONTAINER_PROBE_TIMEOUT_SECONDS,
                )
                if running.stdout.strip().lower() == "true":
                    self._run(
                        ["exec", container, "python", "-c", "import sqlite3"],
                        timeout=CONTAINER_PROBE_TIMEOUT_SECONDS,
                    )
                    return
                last_error = f"container is not running: {container}"
            except BackupError as error:
                last_error = str(error)
            remaining = deadline - _monotonic()
            if remaining <= 0:
                raise BackupError(
                    f"container readiness timed out for {container}: {last_error}"
                )
            _sleep(min(CONTAINER_READY_POLL_SECONDS, remaining))

    def export_tree(
        self, container: str, container_path: str, destination: Path
    ) -> None:
        running = self._run(["inspect", "--format={{.State.Running}}", container])
        if running.stdout.strip().lower() != "true":
            raise BackupError(f"container is not running: {container}")
        destination.mkdir(parents=True, mode=0o700)
        self._run(
            ["cp", f"{container}:{container_path.rstrip('/')}/.", str(destination)]
        )

    def backup_sqlite(
        self,
        container: str,
        container_path: str,
        relative_path: str,
        destination: Path,
    ) -> None:
        relative = PurePosixPath(relative_path)
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise BackupError(f"unsafe container database path: {relative_path}")
        source = posixpath.join(container_path.rstrip("/"), relative.as_posix())
        temporary_directory = f"/tmp/pda-continuity-{uuid.uuid4().hex}"
        temporary = f"{temporary_directory}/backup.sqlite3"
        destination.parent.mkdir(parents=True, exist_ok=True)
        failure: BaseException | None = None
        try:
            self._run(
                [
                    "exec",
                    container,
                    "python",
                    "-c",
                    self._PREPARE_TEMP_SCRIPT,
                    temporary_directory,
                ]
            )
            self._run(
                [
                    "exec",
                    container,
                    "python",
                    "-c",
                    self._SQLITE_BACKUP_SCRIPT,
                    source,
                    temporary,
                ]
            )
            self._run(["cp", f"{container}:{temporary}", str(destination)])
        except BaseException as error:
            failure = error
            raise
        finally:
            try:
                self._run(
                    [
                        "exec",
                        container,
                        "python",
                        "-c",
                        self._CLEANUP_SCRIPT,
                        temporary_directory,
                    ]
                )
            except BackupError:
                if failure is None:
                    raise

    def _run(
        self,
        arguments: list[str],
        *,
        timeout: float = SUBPROCESS_TIMEOUT_SECONDS,
    ) -> subprocess.CompletedProcess[str]:
        docker_command = [self.docker_binary, *arguments]
        command = docker_command
        if self._needs_group_wrapper():
            command = ["sg", self.group, "-c", shlex.join(docker_command)]
        try:
            completed = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except FileNotFoundError as error:
            raise BackupError(f"required command not found: {command[0]}") from error
        except subprocess.TimeoutExpired as error:
            raise BackupError(
                f"Docker command timed out after {timeout} seconds"
            ) from error
        if completed.returncode != 0:
            detail = (
                completed.stderr or completed.stdout or "docker command failed"
            ).strip()
            raise BackupError(detail)
        return completed

    def _needs_group_wrapper(self) -> bool:
        try:
            group = grp.getgrnam(self.group)
        except KeyError:
            return False
        if group.gr_gid == os.getegid() or group.gr_gid in os.getgroups():
            return False
        username = pwd.getpwuid(os.geteuid()).pw_name
        return username in group.gr_mem


@dataclass(frozen=True)
class BackupConfig:
    schema_version: int
    habit_id: str
    timezone: str
    retention: int
    max_age_hours: int
    backup_root: Path
    sources: tuple[SourceConfig, ...]


@dataclass(frozen=True)
class BackupResult:
    snapshot_path: Path
    verification: dict[str, Any]


class BackupEngine:
    def __init__(
        self,
        config: BackupConfig,
        config_path: Path,
        config_sha256: str,
        container_client: ContainerClient | None = None,
    ) -> None:
        self.config = config
        self.config_path = config_path
        self.config_sha256 = config_sha256
        self.container_client = container_client

    @classmethod
    def from_file(
        cls,
        path: Path,
        *,
        container_client: ContainerClient | None = None,
    ) -> BackupEngine:
        config_path = path.expanduser().resolve()
        config_bytes = config_path.read_bytes()
        raw = json.loads(config_bytes.decode("utf-8"))
        if not isinstance(raw, dict):
            raise BackupError("backup configuration must be an object")
        if raw.get("schema_version") != 1:
            raise BackupError("unsupported backup configuration schema")
        retention_config = raw.get("retention")
        if not isinstance(retention_config, dict):
            raise BackupError("retention must be an object")
        retention = retention_config.get("successful_snapshots")
        if (
            not isinstance(retention, int)
            or isinstance(retention, bool)
            or retention < 1
        ):
            raise BackupError(
                "retention.successful_snapshots must be a positive integer"
            )
        freshness = raw.get("freshness", {})
        if not isinstance(freshness, dict):
            raise BackupError("freshness must be an object")
        max_age_hours = freshness.get("max_age_hours", 36)
        if (
            not isinstance(max_age_hours, int)
            or isinstance(max_age_hours, bool)
            or max_age_hours < 1
        ):
            raise BackupError("freshness.max_age_hours must be a positive integer")
        timezone = raw.get("timezone")
        if not isinstance(timezone, str):
            raise BackupError("timezone is required")
        try:
            ZoneInfo(timezone)
        except (KeyError, ValueError) as error:
            raise BackupError(f"invalid timezone: {timezone}") from error
        root = _resolve_lexical_path(raw.get("backup_root"), config_path.parent)
        _reject_symlink_components(root)
        sources: list[SourceConfig] = []
        seen: set[str] = set()
        source_items = raw.get("sources")
        if not isinstance(source_items, list):
            raise BackupError("sources must be an array")
        for item in source_items:
            if not isinstance(item, dict):
                raise BackupError("each backup source must be an object")
            name = item.get("name")
            if (
                not isinstance(name, str)
                or SOURCE_NAME.fullmatch(name) is None
                or name in seen
            ):
                raise BackupError(f"invalid or duplicate source name: {name!r}")
            seen.add(name)
            kind = item.get("kind")
            sqlite_policy = item.get("sqlite", "discover")
            if sqlite_policy not in {"discover", "none"}:
                raise BackupError("source sqlite must be discover or none")
            allowed_special_files = _parse_allowed_special_files(
                item.get("allowed_special_files", [])
            )
            if kind == "tree":
                sources.append(
                    SourceConfig(
                        name=name,
                        kind=kind,
                        path=_resolve_path(item.get("path"), config_path.parent),
                        sqlite=sqlite_policy,
                        allowed_special_files=allowed_special_files,
                    )
                )
            elif kind == "docker-container":
                container = item.get("container")
                container_path = item.get("path")
                if not isinstance(container, str) or not container:
                    raise BackupError("docker-container source requires container")
                if not isinstance(container_path, str) or not container_path.startswith(
                    "/"
                ):
                    raise BackupError("docker-container source path must be absolute")
                sources.append(
                    SourceConfig(
                        name=name,
                        kind=kind,
                        path=None,
                        sqlite=sqlite_policy,
                        allowed_special_files=allowed_special_files,
                        container=container,
                        container_path=container_path,
                    )
                )
            else:
                raise BackupError(f"unsupported source kind: {kind!r}")
        if not sources:
            raise BackupError("at least one backup source is required")
        for source in sources:
            if source.path is not None and _paths_overlap(root, source.path):
                raise BackupError(
                    f"backup root and source must not overlap: {root} / {source.path}"
                )
        for index, source in enumerate(sources):
            for other in sources[index + 1 :]:
                if (
                    source.path is not None
                    and other.path is not None
                    and _paths_overlap(source.path, other.path)
                ):
                    raise BackupError(
                        f"backup sources must not overlap: {source.path} / {other.path}"
                    )
        habit_id = raw.get("habit_id")
        if not isinstance(habit_id, str) or not habit_id:
            raise BackupError("habit_id is required")
        effective_container_client = container_client
        if effective_container_client is None and any(
            source.kind == "docker-container" for source in sources
        ):
            effective_container_client = DockerContainerClient()
        return cls(
            BackupConfig(
                schema_version=1,
                habit_id=habit_id,
                timezone=timezone,
                retention=retention,
                max_age_hours=max_age_hours,
                backup_root=root,
                sources=tuple(sources),
            ),
            config_path,
            hashlib.sha256(config_bytes).hexdigest(),
            effective_container_client,
        )

    def run(self, *, now: datetime | None = None) -> BackupResult:
        zone = ZoneInfo(self.config.timezone)
        current = now.astimezone(zone) if now is not None else datetime.now(zone)
        root = self.config.backup_root
        initialize_backup_root(root)
        _validate_latest_link_shape(root)
        with _exclusive_lock(root / "run.lock"):
            return self._run_locked(current)

    def status(self, *, now: datetime | None = None) -> dict[str, Any]:
        zone = ZoneInfo(self.config.timezone)
        current = now.astimezone(zone) if now is not None else datetime.now(zone)
        root = self.config.backup_root
        if not _is_real_directory(root):
            raise BackupError("no successful local continuity backup exists")
        initialize_backup_root(root)
        _validate_latest(root)
        relative = _latest_relative_target(root)
        if relative is None:
            raise BackupError("no successful local continuity backup exists")
        snapshot = root.joinpath(*relative.parts)
        verification = verify_snapshot(snapshot)
        expected_sources = [
            _source_manifest(source) for source in self.config.sources
        ]
        if (
            verification["config_sha256"] != self.config_sha256
            or verification["habit_id"] != self.config.habit_id
            or verification["timezone"] != self.config.timezone
            or verification["retention"] != self.config.retention
            or verification["sources"] != expected_sources
        ):
            raise BackupError("latest snapshot does not match the current backup policy")
        created_at = datetime.fromisoformat(str(verification["created_at"]))
        age = current - created_at.astimezone(zone)
        if age < timedelta(minutes=-5):
            raise BackupError("latest snapshot creation time is in the future")
        max_age = timedelta(hours=self.config.max_age_hours)
        if age > max_age:
            raise BackupError(
                "latest local continuity backup is stale: "
                f"age={int(age.total_seconds())}s max={int(max_age.total_seconds())}s"
            )
        return {
            **verification,
            "snapshot": str(snapshot),
            "fresh": True,
            "age_seconds": max(0, int(age.total_seconds())),
            "max_age_hours": self.config.max_age_hours,
        }

    def _run_locked(self, current: datetime) -> BackupResult:
        root = self.config.backup_root
        snapshots = root / "snapshots"
        staging_root = root / "staging"
        snapshot_id = current.strftime("%Y-%m-%dT%H%M%S%z")
        _ensure_managed_directory(root, snapshots, "snapshots")
        _ensure_managed_directory(root, staging_root, "staging")
        _remove_stale_staging(staging_root)
        _validate_latest(root)
        for source in self.config.sources:
            if source.kind == "docker-container":
                assert source.container is not None
                assert self.container_client is not None
                self.container_client.wait_until_ready(source.container)
        final = snapshots / snapshot_id
        if _path_exists(final):
            snapshot_id = f"{snapshot_id}-{uuid.uuid4().hex[:8]}"
            final = snapshots / snapshot_id
        verified_snapshots = _verified_snapshots(snapshots)
        generation_sequence = len(verified_snapshots) + 1
        if verified_snapshots:
            generation_sequence = max(
                int(verify_snapshot(path)["generation_sequence"])
                for path in verified_snapshots
            ) + 1
        stage = staging_root / f".{snapshot_id}-{uuid.uuid4().hex}"
        stage.mkdir(mode=0o700)
        stage_marker = stage / STAGING_MARKER
        _write_json(stage_marker, STAGING_CONTRACT)
        os.chmod(stage_marker, 0o600)
        _fsync_tree(stage)
        payload = stage / "payload"
        payload.mkdir(mode=0o700)
        sqlite_paths: list[str] = []
        excluded_special_entries: dict[str, str] = {}
        try:
            data_root = payload / "data"
            data_root.mkdir(mode=0o700)
            for source in self.config.sources:
                destination = data_root / source.name
                if source.kind == "tree":
                    assert source.path is not None
                    if not source.path.is_dir():
                        raise BackupError(
                            f"backup source is not a directory: {source.path}"
                        )
                    special_paths = _discover_special_files(source.path)
                    _copy_tree(source.path, destination)
                    special_paths.update(_discover_special_files(source.path))
                    excluded_special_entries.update(
                        _special_manifest_entries(source, special_paths)
                    )
                    databases = (
                        _discover_sqlite(destination)
                        if source.sqlite == "discover"
                        else []
                    )
                    for snapshot_database in databases:
                        relative = snapshot_database.relative_to(destination)
                        database = source.path / relative
                        source_mode = snapshot_database.lstat().st_mode & 0o7777
                        _remove_copied_sqlite(snapshot_database)
                        _backup_sqlite(database, snapshot_database, mode=source_mode)
                        sqlite_paths.append(
                            (Path("data") / source.name / relative).as_posix()
                        )
                elif source.kind == "docker-container":
                    if self.container_client is None:
                        raise BackupError(
                            "docker-container source requires a container client"
                        )
                    assert source.container is not None
                    assert source.container_path is not None
                    export = payload / ".working" / source.name
                    export.parent.mkdir(mode=0o700, exist_ok=True)
                    self.container_client.export_tree(
                        source.container,
                        source.container_path,
                        export,
                    )
                    special_paths = _discover_special_files(export)
                    _copy_tree(export, destination)
                    excluded_special_entries.update(
                        _special_manifest_entries(source, special_paths)
                    )
                    databases = (
                        _discover_sqlite(destination)
                        if source.sqlite == "discover"
                        else []
                    )
                    for snapshot_database in databases:
                        relative = snapshot_database.relative_to(destination)
                        source_mode = snapshot_database.lstat().st_mode & 0o7777
                        _remove_copied_sqlite(snapshot_database)
                        try:
                            self.container_client.backup_sqlite(
                                source.container,
                                source.container_path,
                                relative.as_posix(),
                                snapshot_database,
                            )
                        except sqlite3.Error as error:
                            raise BackupError(
                                "SQLite container backup failed for "
                                f"{relative.as_posix()}: {error}"
                            ) from error
                        _finalize_sqlite_snapshot(snapshot_database, mode=source_mode)
                        sqlite_paths.append(
                            (Path("data") / source.name / relative).as_posix()
                        )
                    _safe_remove_tree(export, export.parent)
                else:  # pragma: no cover - configuration validation prevents this
                    raise BackupError(f"unsupported source kind: {source.kind}")

            working_root = payload / ".working"
            if _path_exists(working_root):
                _safe_remove_tree(working_root, payload)
            manifest = {
                "schema_version": 1,
                "generation_sequence": generation_sequence,
                "habit_id": self.config.habit_id,
                "created_at": current.isoformat(),
                "timezone": self.config.timezone,
                "retention": self.config.retention,
                "config_sha256": self.config_sha256,
                "sources": [_source_manifest(source) for source in self.config.sources],
                "sqlite_databases": sorted(sqlite_paths),
                "excluded_special_files": [
                    {"path": path, "kind": excluded_special_entries[path]}
                    for path in sorted(excluded_special_entries)
                ],
                "files": _inventory(data_root, payload),
            }
            manifest_path = payload / "manifest.json"
            _write_json(manifest_path, manifest)
            complete_path = payload / "COMPLETE"
            complete_path.write_text(
                _sha256_file(manifest_path) + "\n", encoding="ascii"
            )
            os.chmod(manifest_path, 0o600)
            os.chmod(complete_path, 0o600)
            _fsync_tree(payload)
            verification = verify_snapshot(payload)
            os.replace(payload, final)
            _safe_remove_tree(stage, staging_root)
            _fsync_directory(snapshots)
            _replace_latest(root, final)
            warnings: list[str] = []
            try:
                _fsync_directory(root)
            except OSError as error:
                warnings.append(f"latest directory fsync failed: {error}")
            if not warnings:
                warnings.extend(
                    _rotate_snapshots(
                        snapshots,
                        self.config.retention,
                        [*verified_snapshots, final],
                    )
                )
                try:
                    _fsync_directory(snapshots)
                except OSError as error:
                    warnings.append(f"post-rotation directory fsync failed: {error}")
            verification = {
                **verification,
                "committed": True,
                "degraded": bool(warnings),
                "warnings": warnings,
            }
            return BackupResult(snapshot_path=final, verification=verification)
        except Exception:
            if _path_exists(stage):
                try:
                    _safe_remove_tree(stage, staging_root)
                except (BackupError, OSError):
                    pass
            raise


def _source_manifest(source: SourceConfig) -> dict[str, Any]:
    value: dict[str, Any] = {
        "name": source.name,
        "kind": source.kind,
        "sqlite": source.sqlite,
        "allowed_special_files": [
            {"path": path, "kind": kind}
            for path, kind in source.allowed_special_files
        ],
    }
    if source.kind == "tree":
        assert source.path is not None
        value["origin"] = str(source.path)
    else:
        value["container"] = source.container
        value["origin"] = source.container_path
    return value


def _special_manifest_entries(
    source: SourceConfig, special_paths: dict[Path, str]
) -> dict[str, str]:
    allowed = dict(source.allowed_special_files)
    entries: dict[str, str] = {}
    for relative, kind in special_paths.items():
        relative_text = relative.as_posix()
        if allowed.get(relative_text) != kind:
            raise BackupError(
                f"unknown special file in {source.name}: {relative_text} ({kind})"
            )
        entries[(Path("data") / source.name / relative).as_posix()] = kind
    return entries


def restore_snapshot(
    snapshot_path: Path,
    destination_path: Path,
    *,
    backup_root: Path | None = None,
) -> dict[str, Any]:
    managed_root = (
        _resolve_lexical_path(str(backup_root), Path.cwd())
        if backup_root is not None
        else None
    )
    if managed_root is not None:
        _reject_symlink_components(managed_root)
    if managed_root is not None and _is_real_directory(managed_root):
        initialize_backup_root(managed_root)
        with _exclusive_lock(managed_root / "run.lock"):
            return _restore_snapshot_unlocked(
                snapshot_path,
                destination_path,
                managed_root,
            )
    return _restore_snapshot_unlocked(snapshot_path, destination_path, managed_root)


def _restore_snapshot_unlocked(
    snapshot_path: Path,
    destination_path: Path,
    managed_root: Path | None,
) -> dict[str, Any]:
    snapshot = snapshot_path.expanduser().resolve()
    destination = Path(os.path.abspath(destination_path.expanduser()))
    verify_snapshot(snapshot)
    if _path_exists(destination):
        raise BackupError(f"restore destination already exists: {destination}")
    parent = destination.parent
    if not _is_real_directory(parent) or parent.resolve() != parent:
        raise BackupError(
            f"restore destination parent must be an existing real directory: {parent}"
        )
    if managed_root is not None and _paths_overlap(managed_root, destination):
        raise BackupError("restore destination must not overlap the managed backup root")
    if _paths_overlap(snapshot, destination):
        raise BackupError("restore destination must not overlap the source snapshot")
    staging = parent / f".{destination.name}.pda-restore-{uuid.uuid4().hex}"
    staging.mkdir(mode=0o700)
    staging_stat = staging.lstat()
    command = [
        "rsync",
        "--archive",
        "--hard-links",
        "--acls",
        "--xattrs",
        "--checksum",
        str(snapshot) + "/",
        str(staging) + "/",
    ]
    try:
        subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
        verification = verify_snapshot(staging)
        _fsync_tree(staging)
        _rename_noreplace(staging, destination)
        try:
            _fsync_directory(parent)
        except OSError as error:
            raise BackupError(
                f"restore committed but parent directory fsync failed: {destination}"
            ) from error
        return verification
    except FileNotFoundError as error:
        raise BackupError(
            "rsync is required to restore continuity snapshots"
        ) from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "rsync restore failed").strip()
        raise BackupError(detail) from error
    except subprocess.TimeoutExpired as error:
        raise BackupError(
            f"rsync restore timed out after {SUBPROCESS_TIMEOUT_SECONDS} seconds"
        ) from error
    finally:
        if _path_exists(staging):
            current = staging.lstat()
            if (
                stat.S_ISDIR(current.st_mode)
                and current.st_dev == staging_stat.st_dev
                and current.st_ino == staging_stat.st_ino
            ):
                _safe_remove_tree(staging, parent)


def verify_snapshot(snapshot_path: Path) -> dict[str, Any]:
    snapshot = snapshot_path.expanduser().resolve()
    if not _is_real_directory(snapshot):
        raise BackupError(f"snapshot is not a regular directory: {snapshot}")
    expected_top_level = {"data", "manifest.json", "COMPLETE"}
    if {path.name for path in snapshot.iterdir()} != expected_top_level:
        raise BackupError("snapshot top-level layout is invalid")
    manifest_path = snapshot / "manifest.json"
    complete_path = snapshot / "COMPLETE"
    if not _is_regular_file(manifest_path) or not _is_regular_file(complete_path):
        raise BackupError("snapshot metadata must be regular files")
    expected_manifest_hash = complete_path.read_text(encoding="ascii").strip()
    if re.fullmatch(r"[0-9a-f]{64}", expected_manifest_hash) is None:
        raise BackupError("snapshot completion marker is invalid")
    if _sha256_file(manifest_path) != expected_manifest_hash:
        raise BackupError("snapshot manifest checksum mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise BackupError("snapshot manifest must be an object")
    expected_manifest_keys = {
        "schema_version",
        "generation_sequence",
        "habit_id",
        "created_at",
        "timezone",
        "retention",
        "config_sha256",
        "sources",
        "sqlite_databases",
        "excluded_special_files",
        "files",
    }
    if set(manifest) != expected_manifest_keys or manifest.get("schema_version") != 1:
        raise BackupError("snapshot manifest schema is invalid")
    generation_sequence = manifest.get("generation_sequence")
    if (
        not isinstance(generation_sequence, int)
        or isinstance(generation_sequence, bool)
        or generation_sequence < 1
    ):
        raise BackupError("snapshot manifest has an invalid generation sequence")
    habit_id = manifest.get("habit_id")
    created_at = manifest.get("created_at")
    timezone = manifest.get("timezone")
    retention = manifest.get("retention")
    config_sha256 = manifest.get("config_sha256")
    sources = manifest.get("sources")
    if not isinstance(habit_id, str) or not habit_id:
        raise BackupError("snapshot manifest has an invalid habit id")
    if not isinstance(created_at, str):
        raise BackupError("snapshot manifest has an invalid creation time")
    try:
        parsed_created_at = datetime.fromisoformat(created_at)
    except ValueError as error:
        raise BackupError("snapshot manifest has an invalid creation time") from error
    if parsed_created_at.tzinfo is None:
        raise BackupError("snapshot manifest creation time must include a timezone")
    if not isinstance(timezone, str) or not timezone:
        raise BackupError("snapshot manifest has an invalid timezone")
    if (
        not isinstance(retention, int)
        or isinstance(retention, bool)
        or retention < 1
    ):
        raise BackupError("snapshot manifest has an invalid retention value")
    if (
        not isinstance(config_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", config_sha256) is None
    ):
        raise BackupError("snapshot manifest has an invalid configuration digest")
    if not isinstance(sources, list) or not all(
        isinstance(source, dict) for source in sources
    ):
        raise BackupError("snapshot manifest has an invalid source inventory")

    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise BackupError("snapshot manifest has no file inventory")
    inventory: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise BackupError("snapshot manifest has an invalid file entry")
        relative = _manifest_data_path(entry["path"], label="file")
        normalized = relative.as_posix()
        if normalized in inventory:
            raise BackupError(f"unsafe or duplicate snapshot path: {entry['path']}")
        kind = entry.get("kind")
        if kind == "file":
            size = entry.get("size")
            checksum = entry.get("sha256")
            mode = entry.get("mode")
            if (
                set(entry) != {"path", "kind", "size", "mode", "sha256"}
                or not isinstance(size, int)
                or isinstance(size, bool)
                or size < 0
                or not _valid_file_mode(mode)
                or not isinstance(checksum, str)
                or re.fullmatch(r"[0-9a-f]{64}", checksum) is None
            ):
                raise BackupError(f"invalid regular file entry: {entry['path']}")
        elif kind == "directory":
            if set(entry) != {"path", "kind", "mode"} or not _valid_file_mode(
                entry.get("mode")
            ):
                raise BackupError(f"invalid directory entry: {entry['path']}")
        elif kind == "symlink":
            if set(entry) != {"path", "kind", "target"} or not isinstance(
                entry.get("target"), str
            ):
                raise BackupError(f"invalid symlink entry: {entry['path']}")
        else:
            raise BackupError(f"invalid snapshot file kind: {entry['path']}")
        inventory[normalized] = entry

    data_root = snapshot / "data"
    if not _is_real_directory(data_root):
        raise BackupError("snapshot data root must be a regular directory")
    actual_inventory = {
        entry["path"]: entry for entry in _inventory(data_root, snapshot)
    }
    if set(actual_inventory) != set(inventory):
        raise BackupError("snapshot file inventory mismatch")
    for relative_path, entry in inventory.items():
        actual = actual_inventory[relative_path]
        kind = entry["kind"]
        if actual.get("kind") != kind:
            if kind == "file":
                raise BackupError(
                    f"snapshot path is not a regular file: {relative_path}"
                )
            raise BackupError(f"snapshot file kind mismatch: {relative_path}")
        if kind == "symlink":
            if actual.get("target") != entry["target"]:
                raise BackupError(f"snapshot symlink mismatch: {relative_path}")
            continue
        if actual.get("mode") != entry["mode"]:
            raise BackupError(f"snapshot mode mismatch: {relative_path}")
        if kind == "file" and (
            actual.get("size") != entry["size"]
            or actual.get("sha256") != entry["sha256"]
        ):
            raise BackupError(f"snapshot file checksum mismatch: {relative_path}")

    excluded_entries = manifest.get("excluded_special_files")
    if not isinstance(excluded_entries, list):
        raise BackupError("snapshot manifest has an invalid special-file inventory")
    seen_excluded: set[str] = set()
    valid_special_kinds = {"socket", "fifo", "character-device", "block-device"}
    for value in excluded_entries:
        if not isinstance(value, dict) or set(value) != {"path", "kind"}:
            raise BackupError("snapshot manifest has an invalid special-file entry")
        special_path = value.get("path")
        special_kind = value.get("kind")
        if not isinstance(special_path, str) or special_kind not in valid_special_kinds:
            raise BackupError("snapshot manifest has an invalid special-file entry")
        normalized = _manifest_data_path(
            special_path, label="special-file"
        ).as_posix()
        if normalized in seen_excluded or normalized in inventory:
            raise BackupError(f"invalid excluded special-file path: {special_path}")
        seen_excluded.add(normalized)

    sqlite_entries = manifest.get("sqlite_databases")
    if not isinstance(sqlite_entries, list):
        raise BackupError("snapshot manifest has an invalid SQLite path inventory")
    seen_sqlite: set[str] = set()
    for value in sqlite_entries:
        if not isinstance(value, str):
            raise BackupError("snapshot manifest has an invalid SQLite path")
        relative = _manifest_data_path(value, label="SQLite")
        normalized = relative.as_posix()
        entry = inventory.get(normalized)
        if normalized in seen_sqlite:
            raise BackupError(f"duplicate snapshot SQLite path: {value}")
        seen_sqlite.add(normalized)
        if entry is None:
            raise BackupError(f"snapshot SQLite path is not in the file inventory: {value}")
        if entry.get("kind") != "file":
            raise BackupError(
                f"snapshot SQLite path is not a regular inventory file: {value}"
            )
        path = snapshot.joinpath(*relative.parts)
        _require_real_parent_directories(snapshot, relative)
        if not _is_regular_file(path):
            raise BackupError(
                f"snapshot SQLite path is not a regular inventory file: {value}"
            )
        for suffix in ("-wal", "-shm", "-journal"):
            if _path_exists(Path(str(path) + suffix)):
                raise BackupError(f"snapshot SQLite sidecar is present: {value}{suffix}")
        _verify_sqlite(path)
    actual_sqlite = {
        path.relative_to(snapshot).as_posix() for path in _discover_sqlite(data_root)
    }
    if actual_sqlite != seen_sqlite:
        raise BackupError("snapshot SQLite classification mismatch")
    return {
        "ok": True,
        "generation_sequence": generation_sequence,
        "habit_id": habit_id,
        "created_at": created_at,
        "timezone": timezone,
        "retention": retention,
        "config_sha256": config_sha256,
        "sources": sources,
        "files": len(entries),
    }


def _valid_file_mode(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= 0o7777
    )


def _manifest_data_path(value: str, *, label: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or relative.parts[0] != "data"
        or relative.as_posix() != value
    ):
        raise BackupError(f"unsafe snapshot {label} path: {value}")
    return relative


def _require_real_parent_directories(
    snapshot: Path, relative: PurePosixPath
) -> None:
    current = snapshot
    for part in relative.parts[:-1]:
        current /= part
        if not _is_real_directory(current):
            raise BackupError(f"snapshot path has an unsafe parent: {relative.as_posix()}")


def _is_regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def _is_real_directory(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def _is_symlink(path: Path) -> bool:
    try:
        return stat.S_ISLNK(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def initialize_backup_root(root: Path) -> None:
    """Create or validate the dedicated local-backup root contract."""
    _reject_symlink_components(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(root)
    if _path_exists(root):
        if not _is_real_directory(root):
            raise BackupError(f"backup root must be a real directory: {root}")
    else:
        root.mkdir(mode=0o700)
    marker = root / MANAGED_ROOT_MARKER
    if not _path_exists(marker):
        if any(root.iterdir()):
            raise BackupError(f"refusing unmanaged nonempty backup root: {root}")
        payload = (
            json.dumps(MANAGED_ROOT_CONTRACT, sort_keys=True, separators=(",", ":"))
            + "\n"
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(marker, flags, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
        except BaseException:
            marker.unlink(missing_ok=True)
            raise
    if not _is_regular_file(marker):
        raise BackupError(f"backup root marker must be a regular file: {marker}")
    try:
        contract = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BackupError(f"backup root marker is invalid: {marker}") from error
    if contract != MANAGED_ROOT_CONTRACT:
        raise BackupError(f"backup root marker contract mismatch: {marker}")
    os.chmod(root, 0o700)
    os.chmod(marker, 0o600)


def _path_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _ensure_managed_directory(root: Path, path: Path, label: str) -> None:
    if path.parent != root or not _is_real_directory(root):
        raise BackupError(f"unsafe managed {label} path: {path}")
    if not _path_exists(path):
        path.mkdir(mode=0o700)
    if not _is_real_directory(path):
        raise BackupError(f"managed {label} must be a real directory: {path}")
    os.chmod(path, 0o700)


def _latest_relative_target(root: Path) -> PurePosixPath | None:
    latest = root / "latest"
    if not _path_exists(latest):
        return None
    if not _is_symlink(latest):
        raise BackupError(f"unsafe latest symlink: {latest}")
    target = os.readlink(latest)
    relative = PurePosixPath(target)
    if (
        relative.is_absolute()
        or relative.as_posix() != target
        or len(relative.parts) != 2
        or relative.parts[0] != "snapshots"
        or relative.parts[1] in {".", ".."}
    ):
        raise BackupError(f"unsafe latest symlink: {latest} -> {target}")
    return relative


def _validate_latest_link_shape(root: Path) -> None:
    _latest_relative_target(root)


def _validate_latest(root: Path) -> None:
    relative = _latest_relative_target(root)
    if relative is None:
        return
    target = root.joinpath(*relative.parts)
    if not _is_real_directory(target):
        raise BackupError(f"unsafe latest symlink target: {target}")
    try:
        verify_snapshot(target)
    except BackupError as error:
        raise BackupError(f"latest snapshot is not valid: {target}: {error}") from error


def _safe_remove_tree(path: Path, expected_parent: Path) -> None:
    if (
        path.parent != expected_parent
        or not _is_real_directory(expected_parent)
        or not _is_real_directory(path)
    ):
        raise BackupError(f"refusing unsafe recursive deletion: {path}")
    shutil.rmtree(path)


def _directory_identity(path: Path) -> tuple[int, int]:
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise BackupError(f"directory disappeared before deletion: {path}") from error
    if not stat.S_ISDIR(metadata.st_mode):
        raise BackupError(f"refusing deletion of non-directory: {path}")
    return metadata.st_dev, metadata.st_ino


def _open_directory(path: Path) -> tuple[int, tuple[int, int]]:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise BackupError(f"refusing deletion of non-directory: {path}")
    return descriptor, (metadata.st_dev, metadata.st_ino)


def _open_child_directory(parent_descriptor: int, name: str) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return os.open(name, flags, dir_fd=parent_descriptor)


def _remove_directory_contents_fd(directory_descriptor: int) -> None:
    for name in os.listdir(directory_descriptor):
        metadata = os.stat(
            name, dir_fd=directory_descriptor, follow_symlinks=False
        )
        if stat.S_ISDIR(metadata.st_mode):
            child_descriptor = _open_child_directory(directory_descriptor, name)
            try:
                opened = os.fstat(child_descriptor)
                if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                    raise BackupError(
                        f"directory identity changed during recursive deletion: {name}"
                    )
                _remove_directory_contents_fd(child_descriptor)
                current = os.stat(
                    name, dir_fd=directory_descriptor, follow_symlinks=False
                )
                if (current.st_dev, current.st_ino) != (
                    metadata.st_dev,
                    metadata.st_ino,
                ):
                    raise BackupError(
                        f"directory identity changed during recursive deletion: {name}"
                    )
                os.rmdir(name, dir_fd=directory_descriptor)
            finally:
                os.close(child_descriptor)
        else:
            os.unlink(name, dir_fd=directory_descriptor)


def _quarantine_and_remove_tree(
    path: Path,
    expected_parent: Path,
    expected_descriptor: int,
    expected_identity: tuple[int, int],
) -> None:
    descriptor_metadata = os.fstat(expected_descriptor)
    descriptor_identity = (descriptor_metadata.st_dev, descriptor_metadata.st_ino)
    if (
        path.parent != expected_parent
        or descriptor_identity != expected_identity
        or _directory_identity(path) != expected_identity
    ):
        raise BackupError(f"directory identity changed before deletion: {path}")
    quarantine = expected_parent / f".prune-{uuid.uuid4().hex}"
    os.rename(path, quarantine)
    if _directory_identity(quarantine) != expected_identity:
        try:
            _rename_noreplace(quarantine, path)
        except (BackupError, OSError):
            pass
        raise BackupError(f"directory identity changed during deletion: {path}")
    try:
        _remove_directory_contents_fd(expected_descriptor)
        parent_descriptor, _ = _open_directory(expected_parent)
        try:
            current = os.stat(
                quarantine.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            if (current.st_dev, current.st_ino) != expected_identity:
                raise BackupError(f"directory identity changed during deletion: {path}")
            os.rmdir(quarantine.name, dir_fd=parent_descriptor)
        finally:
            os.close(parent_descriptor)
    except (BackupError, OSError):
        try:
            _rename_noreplace(quarantine, path)
        except (BackupError, OSError):
            pass
        raise


def _remove_stale_staging(staging_root: Path) -> None:
    for path in staging_root.iterdir():
        marker = path / STAGING_MARKER
        if (
            STAGING_NAME.fullmatch(path.name) is None
            or not _is_real_directory(path)
            or not _is_regular_file(marker)
        ):
            raise BackupError(f"unsafe stale staging entry: {path}")
        try:
            contract = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise BackupError(f"unsafe stale staging entry: {path}") from error
        if contract != STAGING_CONTRACT:
            raise BackupError(f"unsafe stale staging entry: {path}")
        _safe_remove_tree(path, staging_root)


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.EISDIR, errno.ENXIO}:
            raise BackupError(f"backup lock must be a regular file: {path}") from error
        raise
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise BackupError(f"backup lock must be a regular file: {path}")
    os.fchmod(descriptor, 0o600)
    handle = os.fdopen(descriptor, "r+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise BackupError("a local continuity backup is already running") from error
        yield
    finally:
        try:
            fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            handle.close()


def _parse_allowed_special_files(value: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise BackupError("allowed_special_files must be an array")
    allowed: dict[str, str] = {}
    valid_kinds = {"socket", "fifo", "character-device", "block-device"}
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "kind"}:
            raise BackupError("each allowed special file must declare path and kind")
        path_value = item.get("path")
        kind = item.get("kind")
        if not isinstance(path_value, str) or not path_value:
            raise BackupError("allowed special-file path must be relative")
        relative = PurePosixPath(path_value)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != path_value
            or path_value in allowed
        ):
            raise BackupError(f"unsafe or duplicate allowed special-file path: {path_value}")
        if kind not in valid_kinds:
            raise BackupError(f"invalid allowed special-file kind: {kind!r}")
        allowed[path_value] = kind
    return tuple(sorted(allowed.items()))


def _resolve_lexical_path(value: Any, base: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise BackupError("backup paths must be non-empty strings")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return Path(os.path.abspath(path))


def _reject_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        if stat.S_ISLNK(mode):
            raise BackupError(f"backup root may not traverse a symlink: {current}")


def _resolve_path(value: Any, base: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise BackupError("backup paths must be non-empty strings")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _special_file_kind(mode: int) -> str:
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISCHR(mode):
        return "character-device"
    if stat.S_ISBLK(mode):
        return "block-device"
    raise BackupError("unsupported special-file type")


def _discover_special_files(root: Path) -> dict[Path, str]:
    special: dict[Path, str] = {}
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in list(directories):
            path = current_path / name
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError:
                directories.remove(name)
                continue
            if stat.S_ISLNK(mode):
                directories.remove(name)
            elif not stat.S_ISDIR(mode):
                special[path.relative_to(root)] = _special_file_kind(mode)
                directories.remove(name)
        for name in files:
            path = current_path / name
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError:
                continue
            if not (stat.S_ISREG(mode) or stat.S_ISLNK(mode)):
                special[path.relative_to(root)] = _special_file_kind(mode)
    return special


def _discover_sqlite(root: Path) -> list[Path]:
    databases: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            header = path.open("rb").read(16)
        except OSError:
            continue
        if header == b"SQLite format 3\x00":
            databases.append(path)
    return sorted(databases)


def _copy_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    command = [
        "rsync",
        "--archive",
        "--hard-links",
        "--acls",
        "--xattrs",
        "--no-devices",
        "--no-specials",
    ]
    command.extend([str(source) + "/", str(destination) + "/"])
    try:
        subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as error:
        raise BackupError("rsync is required for local continuity backups") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "rsync failed").strip()
        raise BackupError(detail) from error
    except subprocess.TimeoutExpired as error:
        raise BackupError(
            f"rsync timed out after {SUBPROCESS_TIMEOUT_SECONDS} seconds"
        ) from error


def _remove_copied_sqlite(database: Path) -> None:
    for candidate in (
        database,
        Path(str(database) + "-wal"),
        Path(str(database) + "-shm"),
        Path(str(database) + "-journal"),
    ):
        if not _path_exists(candidate):
            continue
        if not _is_regular_file(candidate):
            raise BackupError(f"copied SQLite path is not a regular file: {candidate}")
        candidate.unlink()


def _backup_sqlite(
    source: Path, destination: Path, *, mode: int = 0o600
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = source.resolve().as_uri() + "?mode=ro"
    deadline = _monotonic() + SQLITE_OPERATION_TIMEOUT_SECONDS

    def progress(status: int, remaining: int, total: int) -> None:
        del status, remaining, total
        if _monotonic() >= deadline:
            raise BackupError(f"SQLite backup timed out: {source}")

    try:
        with (
            sqlite3.connect(
                source_uri, uri=True, timeout=SQLITE_BUSY_TIMEOUT_SECONDS
            ) as source_connection,
            sqlite3.connect(
                destination, timeout=SQLITE_BUSY_TIMEOUT_SECONDS
            ) as destination_connection,
        ):
            source_connection.backup(
                destination_connection,
                pages=1024,
                progress=progress,
                sleep=0.25,
            )
    except sqlite3.Error as error:
        raise BackupError(f"SQLite backup failed for {source}: {error}") from error
    _finalize_sqlite_snapshot(destination, mode=mode)


def _finalize_sqlite_snapshot(database: Path, *, mode: int = 0o600) -> None:
    try:
        with sqlite3.connect(
            database, timeout=SQLITE_BUSY_TIMEOUT_SECONDS
        ) as connection, _sqlite_query_deadline(
            connection, "finalization", database
        ):
            journal_mode = connection.execute("PRAGMA journal_mode=DELETE").fetchone()
            if journal_mode != ("delete",):
                raise BackupError(
                    f"could not make SQLite snapshot standalone: {database}"
                )
    except sqlite3.Error as error:
        raise BackupError(f"SQLite finalization failed for {database}: {error}") from error
    os.chmod(database, mode)
    _verify_sqlite(database)
    _remove_sqlite_sidecars(database)


def _remove_sqlite_sidecars(database: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        Path(str(database) + suffix).unlink(missing_ok=True)


def _verify_sqlite(path: Path) -> None:
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(
            uri, uri=True, timeout=SQLITE_BUSY_TIMEOUT_SECONDS
        ) as connection, _sqlite_query_deadline(connection, "verification", path):
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity != ("ok",):
                raise BackupError(f"SQLite integrity check failed: {path}")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise BackupError(f"SQLite foreign key check failed: {path}")
    except sqlite3.Error as error:
        raise BackupError(f"SQLite verification failed for {path}: {error}") from error


@contextmanager
def _sqlite_query_deadline(
    connection: sqlite3.Connection, action: str, path: Path
) -> Iterator[None]:
    deadline = _monotonic() + SQLITE_OPERATION_TIMEOUT_SECONDS
    timed_out = False

    def progress() -> int:
        nonlocal timed_out
        timed_out = _monotonic() >= deadline
        return int(timed_out)

    connection.set_progress_handler(progress, 10_000)
    try:
        yield
    except sqlite3.OperationalError as error:
        if timed_out:
            raise BackupError(f"SQLite {action} timed out: {path}") from error
        raise
    finally:
        connection.set_progress_handler(None, 0)


def _monotonic() -> float:
    return time.monotonic()


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _inventory(data_root: Path, snapshot_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(data_root.rglob("*"), key=lambda value: value.as_posix()):
        relative = path.relative_to(snapshot_root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            entries.append(
                {"path": relative, "kind": "symlink", "target": os.readlink(path)}
            )
        elif stat.S_ISREG(mode):
            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "size": path.lstat().st_size,
                    "mode": mode & 0o7777,
                    "sha256": _sha256_file(path),
                }
            )
        elif stat.S_ISDIR(mode):
            entries.append(
                {
                    "path": relative,
                    "kind": "directory",
                    "mode": mode & 0o7777,
                }
            )
        else:
            raise BackupError(f"unsupported special file in snapshot: {path}")
    return entries


def _replace_latest(root: Path, snapshot: Path) -> None:
    temporary = root / f".latest-{uuid.uuid4().hex}"
    temporary.symlink_to(snapshot.relative_to(root))
    try:
        os.replace(temporary, root / "latest")
    finally:
        if _path_exists(temporary):
            temporary.unlink()


def _rename_noreplace(source: Path, destination: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise BackupError("atomic no-replace rename is unavailable on this host")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(destination),
        1,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise BackupError(f"restore destination already exists: {destination}")
    raise OSError(error_number, os.strerror(error_number), str(destination))


def _fsync_tree(root: Path) -> None:
    directories: list[Path] = [root]
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            flags = os.O_RDONLY
            if hasattr(os, "O_CLOEXEC"):
                flags |= os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(path, flags)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        elif stat.S_ISDIR(mode):
            directories.append(path)
    for directory in sorted(
        directories,
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        _fsync_directory(directory)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _verified_snapshots(snapshots: Path) -> list[Path]:
    verified: list[tuple[int, Path]] = []
    for path in sorted(snapshots.iterdir()):
        if _is_symlink(path):
            raise BackupError(f"refusing symlinked snapshot generation: {path}")
        if not _is_real_directory(path):
            continue
        try:
            verification = verify_snapshot(path)
        except (BackupError, OSError, UnicodeError, ValueError, KeyError, TypeError):
            continue
        verified.append((int(verification["generation_sequence"]), path))
    verified.sort(key=lambda item: (item[0], item[1].name))
    return [path for _, path in verified]


def _rotate_snapshots(
    snapshots: Path, retention: int, verified_candidates: list[Path]
) -> list[str]:
    warnings: list[str] = []
    descriptors: list[int] = []
    records: list[tuple[int, str, Path, int, tuple[int, int]]] = []
    try:
        for candidate in verified_candidates:
            descriptor, identity = _open_directory(candidate)
            descriptors.append(descriptor)
            verification = verify_snapshot(candidate)
            if _directory_identity(candidate) != identity:
                raise BackupError(
                    f"snapshot identity changed during verification: {candidate}"
                )
            created_day = (
                datetime.fromisoformat(verification["created_at"]).date().isoformat()
            )
            records.append(
                (
                    int(verification["generation_sequence"]),
                    created_day,
                    candidate,
                    descriptor,
                    identity,
                )
            )
        latest_by_day: dict[str, tuple[int, Path]] = {}
        for sequence, created_day, candidate, _, _ in records:
            previous = latest_by_day.get(created_day)
            if previous is None or sequence > previous[0]:
                latest_by_day[created_day] = (sequence, candidate)
        kept = {
            candidate
            for _, candidate in sorted(latest_by_day.values())[-retention:]
        }
        expired_candidates = [
            (candidate, descriptor, identity)
            for _, _, candidate, descriptor, identity in records
            if candidate not in kept
        ]
        for expired, descriptor, identity in expired_candidates:
            try:
                _quarantine_and_remove_tree(
                    expired, snapshots, descriptor, identity
                )
            except (BackupError, OSError) as error:
                warnings.append(f"could not prune {expired.name}: {error}")
                break
    except (BackupError, OSError) as error:
        warnings.append(f"could not prepare safe retention pruning: {error}")
    finally:
        for descriptor in descriptors:
            os.close(descriptor)
    return warnings


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
