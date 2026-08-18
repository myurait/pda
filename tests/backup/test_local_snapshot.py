from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from pda.backup import local_snapshot
from pda.backup.local_snapshot import (
    BackupEngine,
    BackupError,
    DockerContainerClient,
    restore_snapshot,
    verify_snapshot,
)


class FakeContainerClient:
    def __init__(self, live_data: Path) -> None:
        self.live_data = live_data
        self.exports: list[tuple[str, str]] = []
        self.sqlite_backups: list[str] = []

    def wait_until_ready(self, container: str) -> None:
        del container

    def export_tree(
        self, container: str, container_path: str, destination: Path
    ) -> None:
        self.exports.append((container, container_path))
        shutil.copytree(self.live_data, destination, symlinks=True)

    def backup_sqlite(
        self,
        container: str,
        container_path: str,
        relative_path: str,
        destination: Path,
    ) -> None:
        self.sqlite_backups.append(relative_path)
        source = self.live_data / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        with (
            sqlite3.connect(
                source.as_uri() + "?mode=ro", uri=True
            ) as source_connection,
            sqlite3.connect(destination) as destination_connection,
        ):
            source_connection.backup(destination_connection)


def write_config(
    path: Path,
    *,
    backup_root: Path,
    source: Path,
    retention: int = 7,
    opaque_sqlite: tuple[str, ...] = (),
) -> Path:
    config = {
        "schema_version": 1,
        "habit_id": "daily-local-continuity-backup",
        "timezone": "Asia/Tokyo",
        "retention": {"successful_snapshots": retention},
        "backup_root": str(backup_root),
        "sources": [
            {
                "name": "runtime",
                "kind": "tree",
                "path": str(source),
                "sqlite": "discover",
                "opaque_sqlite": list(opaque_sqlite),
            }
        ],
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def rewrite_manifest(snapshot: Path, manifest: dict[str, object]) -> None:
    manifest_path = snapshot / "manifest.json"
    payload = json.dumps(manifest, sort_keys=True) + "\n"
    manifest_path.write_text(payload, encoding="utf-8")
    (snapshot / "COMPLETE").write_text(
        hashlib.sha256(payload.encode()).hexdigest() + "\n", encoding="ascii"
    )


def create_basic_snapshot(tmp_path: Path) -> Path:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA continuity\n", encoding="utf-8")
    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=tmp_path / "backups",
        source=source,
    )
    return BackupEngine.from_file(config_path).run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    ).snapshot_path


def mark_managed_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".pda-local-backup-root.json").write_text(
        json.dumps(
            {
                "format": "pda-local-continuity-backup-root",
                "schema_version": 1,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_run_snapshot_backs_up_live_wal_database_and_verifies(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA continuity\n", encoding="utf-8")

    database = source / "state.db"
    writer = sqlite3.connect(database)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE memory (value TEXT NOT NULL)")
    writer.execute("INSERT INTO memory VALUES ('remember me')")
    writer.commit()

    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=tmp_path / "backups",
        source=source,
    )
    engine = BackupEngine.from_file(config_path)

    result = engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo")))
    writer.close()

    assert result.snapshot_path.name.startswith("2026-08-17T050000")
    assert (result.snapshot_path / "data/runtime/identity.txt").read_text(
        encoding="utf-8"
    ) == "PDA continuity\n"
    snapshot_db = result.snapshot_path / "data/runtime/state.db"
    assert not (result.snapshot_path / "data/runtime/state.db-wal").exists()
    assert not (result.snapshot_path / "data/runtime/state.db-shm").exists()
    with sqlite3.connect(snapshot_db.as_uri() + "?mode=ro", uri=True) as restored:
        assert restored.execute("SELECT value FROM memory").fetchone() == (
            "remember me",
        )
        assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert restored.execute("PRAGMA journal_mode").fetchone() == ("delete",)

    verification = verify_snapshot(result.snapshot_path)
    assert verification["ok"] is True
    assert verification["habit_id"] == "daily-local-continuity-backup"
    manifest = json.loads(
        (result.snapshot_path / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["sources"] == [
        {
            "allowed_special_files": [],
            "kind": "tree",
            "name": "runtime",
            "opaque_sqlite": [],
            "origin": str(source.resolve()),
            "sqlite": "discover",
        }
    ]
    rogue = result.snapshot_path / "data/runtime/untracked.txt"
    rogue.write_text("not in manifest\n", encoding="utf-8")
    with pytest.raises(BackupError, match="inventory mismatch"):
        verify_snapshot(result.snapshot_path)


def test_declared_historical_sqlite_is_preserved_as_opaque_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "runtime"
    historical = source / "state-snapshots/legacy/state.db"
    historical.parent.mkdir(parents=True)
    with sqlite3.connect(historical) as connection:
        connection.execute("CREATE TABLE memory (value TEXT)")
        connection.execute("INSERT INTO memory VALUES ('legacy')")
    original = historical.read_bytes()
    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=tmp_path / "backups",
        source=source,
        opaque_sqlite=("state-snapshots/*/state.db",),
    )

    def reject_online_backup(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("opaque historical SQLite must not be opened or rewritten")

    monkeypatch.setattr(local_snapshot, "_backup_sqlite", reject_online_backup)
    result = BackupEngine.from_file(config_path).run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    )

    copied = result.snapshot_path / "data/runtime/state-snapshots/legacy/state.db"
    assert copied.read_bytes() == original
    manifest = json.loads(
        (result.snapshot_path / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["sqlite_databases"] == []
    assert manifest["opaque_sqlite_databases"] == [
        "data/runtime/state-snapshots/legacy/state.db"
    ]
    assert verify_snapshot(result.snapshot_path)["ok"] is True


def test_declared_opaque_sqlite_preserves_native_sidecar_bundle(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime"
    historical = source / "state-snapshots/legacy/state.db"
    historical.parent.mkdir(parents=True)
    with sqlite3.connect(historical) as connection:
        connection.execute("CREATE TABLE memory (value TEXT)")
    wal = Path(str(historical) + "-wal")
    shm = Path(str(historical) + "-shm")
    wal.write_bytes(b"historical-wal-bytes")
    shm.write_bytes(b"historical-shm-bytes")
    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=tmp_path / "backups",
        source=source,
        opaque_sqlite=("state-snapshots/*/state.db",),
    )

    result = BackupEngine.from_file(config_path).run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    )

    copied = result.snapshot_path / "data/runtime/state-snapshots/legacy/state.db"
    assert Path(str(copied) + "-wal").read_bytes() == b"historical-wal-bytes"
    assert Path(str(copied) + "-shm").read_bytes() == b"historical-shm-bytes"
    assert verify_snapshot(result.snapshot_path)["ok"] is True


def test_verify_rejects_file_entry_that_claims_a_symlink_is_regular(
    tmp_path: Path,
) -> None:
    snapshot = create_basic_snapshot(tmp_path)
    external = tmp_path / "outside.txt"
    external.write_text("outside snapshot\n", encoding="utf-8")
    snapshot_file = snapshot / "data/runtime/identity.txt"
    snapshot_file.unlink()
    snapshot_file.symlink_to(external)
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    entry = next(
        item
        for item in manifest["files"]
        if item["path"] == "data/runtime/identity.txt"
    )
    entry["size"] = external.stat().st_size
    entry["sha256"] = hashlib.sha256(external.read_bytes()).hexdigest()
    rewrite_manifest(snapshot, manifest)

    with pytest.raises(BackupError, match="regular file"):
        verify_snapshot(snapshot)


@pytest.mark.parametrize("path_kind", ["absolute", "traversal", "non-inventory"])
def test_verify_rejects_unconfined_or_non_inventory_sqlite_paths(
    tmp_path: Path, path_kind: str
) -> None:
    snapshot = create_basic_snapshot(tmp_path)
    external = tmp_path / "outside.sqlite3"
    with sqlite3.connect(external) as connection:
        connection.execute("CREATE TABLE secret (value TEXT)")
    if path_kind == "absolute":
        sqlite_path = str(external)
    elif path_kind == "traversal":
        sqlite_path = os.path.relpath(external, snapshot)
    else:
        sqlite_path = "data/runtime/not-in-inventory.sqlite3"
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    manifest["sqlite_databases"] = [sqlite_path]
    rewrite_manifest(snapshot, manifest)

    with pytest.raises(BackupError, match="SQLite path"):
        verify_snapshot(snapshot)


def test_verify_rejects_sqlite_inventory_symlink(tmp_path: Path) -> None:
    snapshot = create_basic_snapshot(tmp_path)
    external = tmp_path / "outside.sqlite3"
    with sqlite3.connect(external) as connection:
        connection.execute("CREATE TABLE secret (value TEXT)")
    database = snapshot / "data/runtime/external.sqlite3"
    database.symlink_to(external)
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"].append(
        {
            "path": "data/runtime/external.sqlite3",
            "kind": "symlink",
            "target": str(external),
        }
    )
    manifest["sqlite_databases"] = ["data/runtime/external.sqlite3"]
    rewrite_manifest(snapshot, manifest)

    with pytest.raises(BackupError, match="regular inventory file"):
        verify_snapshot(snapshot)


def test_verify_rejects_symlinked_manifest_metadata(tmp_path: Path) -> None:
    snapshot = create_basic_snapshot(tmp_path)
    manifest_path = snapshot / "manifest.json"
    external_manifest = tmp_path / "outside-manifest.json"
    shutil.copy2(manifest_path, external_manifest)
    manifest_path.unlink()
    manifest_path.symlink_to(external_manifest)

    with pytest.raises(BackupError, match="metadata must be regular files"):
        verify_snapshot(snapshot)


def test_verify_rejects_sqlite_missing_from_classification_inventory(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    with sqlite3.connect(source / "state.db") as connection:
        connection.execute("CREATE TABLE memory (value TEXT)")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
        )
    )
    snapshot = engine.run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    ).snapshot_path
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    manifest["sqlite_databases"] = []
    rewrite_manifest(snapshot, manifest)

    with pytest.raises(BackupError, match="SQLite classification mismatch"):
        verify_snapshot(snapshot)


def test_verify_rejects_restoration_critical_mode_changes(tmp_path: Path) -> None:
    snapshot = create_basic_snapshot(tmp_path)
    identity = snapshot / "data/runtime/identity.txt"
    identity.chmod(0o644 if identity.stat().st_mode & 0o777 == 0o600 else 0o600)

    with pytest.raises(BackupError, match="mode mismatch"):
        verify_snapshot(snapshot)


def test_verify_rejects_unknown_top_level_content(tmp_path: Path) -> None:
    snapshot = create_basic_snapshot(tmp_path)
    (snapshot / "untracked-secret.txt").write_text("unexpected\n", encoding="utf-8")

    with pytest.raises(BackupError, match="top-level layout"):
        verify_snapshot(snapshot)


def test_verify_inventories_empty_directories(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "empty-directory").mkdir()
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
        )
    )
    snapshot = engine.run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    ).snapshot_path
    (snapshot / "data/runtime/empty-directory").rmdir()

    with pytest.raises(BackupError, match="inventory mismatch"):
        verify_snapshot(snapshot)


def test_run_keeps_independent_generations_and_only_successful_retention_count(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    stable = source / "stable.txt"
    changing = source / "changing.txt"
    stable.write_text("unchanged\n", encoding="utf-8")
    changing.write_text("generation 1\n", encoding="utf-8")
    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=tmp_path / "backups",
        source=source,
        retention=2,
    )
    engine = BackupEngine.from_file(config_path)
    zone = ZoneInfo("Asia/Tokyo")

    first = engine.run(now=datetime(2026, 8, 15, 5, 0, tzinfo=zone))
    changing.write_text("generation 2\n", encoding="utf-8")
    second = engine.run(now=datetime(2026, 8, 16, 5, 0, tzinfo=zone))

    first_stable = first.snapshot_path / "data/runtime/stable.txt"
    second_stable = second.snapshot_path / "data/runtime/stable.txt"
    assert first_stable.stat().st_ino != second_stable.stat().st_ino

    changing.write_text("generation 3\n", encoding="utf-8")
    third = engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=zone))

    snapshots = sorted((tmp_path / "backups/snapshots").iterdir())
    assert snapshots == [second.snapshot_path, third.snapshot_path]
    assert not first.snapshot_path.exists()
    assert (tmp_path / "backups/latest").resolve() == third.snapshot_path


def test_retention_keeps_one_successful_generation_per_local_day(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    state = source / "state.txt"
    state.write_text("first\n", encoding="utf-8")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
            retention=7,
        )
    )
    zone = ZoneInfo("Asia/Tokyo")
    first = engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=zone))
    state.write_text("replacement\n", encoding="utf-8")
    replacement = engine.run(now=datetime(2026, 8, 17, 6, 0, tzinfo=zone))

    assert not first.snapshot_path.exists()
    assert sorted((tmp_path / "backups/snapshots").iterdir()) == [
        replacement.snapshot_path
    ]


def test_clock_rollback_cannot_prune_the_new_generation_or_break_latest(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    changing = source / "changing.txt"
    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=tmp_path / "backups",
        source=source,
        retention=2,
    )
    engine = BackupEngine.from_file(config_path)
    zone = ZoneInfo("Asia/Tokyo")

    changing.write_text("first\n", encoding="utf-8")
    first = engine.run(now=datetime(2026, 8, 16, 5, 0, tzinfo=zone))
    changing.write_text("second\n", encoding="utf-8")
    second = engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=zone))
    changing.write_text("clock moved backward\n", encoding="utf-8")
    newest = engine.run(now=datetime(2026, 8, 15, 5, 0, tzinfo=zone))

    assert not first.snapshot_path.exists()
    assert second.snapshot_path.is_dir()
    assert newest.snapshot_path.is_dir()
    assert (tmp_path / "backups/latest").resolve() == newest.snapshot_path
    manifests = [
        json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
        for snapshot in (second.snapshot_path, newest.snapshot_path)
    ]
    assert [manifest["generation_sequence"] for manifest in manifests] == [2, 3]


def test_restore_refuses_every_destination_inside_the_managed_backup_root(
    tmp_path: Path,
) -> None:
    snapshot = create_basic_snapshot(tmp_path)
    backup_root = snapshot.parents[1]
    protected = backup_root / "snapshots/protected-generation"
    protected.mkdir()
    sentinel = protected / "sentinel.txt"
    sentinel.write_text("do not alter\n", encoding="utf-8")

    with pytest.raises(BackupError, match="managed backup root"):
        restore_snapshot(
            snapshot,
            protected / "restore-target",
            backup_root=backup_root,
        )

    assert sentinel.read_text(encoding="utf-8") == "do not alter\n"
    assert not (protected / "restore-target").exists()


def test_restore_rejects_a_dangling_destination_symlink(tmp_path: Path) -> None:
    snapshot = create_basic_snapshot(tmp_path)
    destination = tmp_path / "restore-output"
    symlink_target = tmp_path / "redirected-output"
    destination.symlink_to(symlink_target)

    with pytest.raises(BackupError, match="destination"):
        restore_snapshot(snapshot, destination, backup_root=snapshot.parents[1])

    assert destination.is_symlink()
    assert not symlink_target.exists()


def test_interrupted_restore_never_exposes_the_requested_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = create_basic_snapshot(tmp_path)
    destination = tmp_path / "restore-output"

    def interrupt(command: list[str], **kwargs: object) -> None:
        del kwargs
        staging = Path(command[-1].rstrip("/"))
        (staging / "partial").write_text("not complete\n", encoding="utf-8")
        raise KeyboardInterrupt

    monkeypatch.setattr(local_snapshot.subprocess, "run", interrupt)

    with pytest.raises(KeyboardInterrupt):
        restore_snapshot(snapshot, destination, backup_root=snapshot.parents[1])

    assert not destination.exists()
    assert not any(tmp_path.glob(".restore-output.pda-restore-*"))


def test_restore_is_serialized_with_backup_rotation(tmp_path: Path) -> None:
    snapshot = create_basic_snapshot(tmp_path)
    backup_root = snapshot.parents[1]
    destination = tmp_path / "restore-output"

    with (backup_root / "run.lock").open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BackupError, match="already running"):
            restore_snapshot(
                snapshot,
                destination,
                backup_root=backup_root,
            )

    assert not destination.exists()


def test_run_refuses_unmanaged_nonempty_backup_root(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    sentinel = backup_root / "do-not-delete.txt"
    sentinel.write_text("unmanaged\n", encoding="utf-8")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json", backup_root=backup_root, source=source
        )
    )

    with pytest.raises(BackupError, match="unmanaged nonempty backup root"):
        engine.run()

    assert sentinel.read_text(encoding="utf-8") == "unmanaged\n"
    assert not (backup_root / "snapshots").exists()


def test_run_marks_a_new_backup_root_as_managed(tmp_path: Path) -> None:
    snapshot = create_basic_snapshot(tmp_path)
    marker = snapshot.parents[1] / ".pda-local-backup-root.json"

    assert json.loads(marker.read_text(encoding="utf-8")) == {
        "format": "pda-local-continuity-backup-root",
        "schema_version": 1,
    }


def test_publication_flushes_snapshot_and_directory_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
        )
    )
    real_fsync = os.fsync
    fsynced: list[int] = []

    def record_fsync(descriptor: int) -> None:
        fsynced.append(descriptor)
        real_fsync(descriptor)

    monkeypatch.setattr(local_snapshot.os, "fsync", record_fsync)

    engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo")))

    assert len(fsynced) >= 4


def test_post_commit_fsync_failure_is_reported_as_committed_degraded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    changing = source / "identity.txt"
    changing.write_text("first\n", encoding="utf-8")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
            retention=1,
        )
    )
    first = engine.run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    ).snapshot_path
    changing.write_text("second\n", encoding="utf-8")

    real_fsync_directory = local_snapshot._fsync_directory
    snapshot_fsyncs = 0

    def fail_after_rotation(path: Path) -> None:
        nonlocal snapshot_fsyncs
        if path == engine.config.backup_root / "snapshots":
            snapshot_fsyncs += 1
            if snapshot_fsyncs == 2:
                raise OSError("injected post-commit fsync failure")
        real_fsync_directory(path)

    monkeypatch.setattr(local_snapshot, "_fsync_directory", fail_after_rotation)
    result = engine.run(
        now=datetime(2026, 8, 18, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    )

    assert result.verification["ok"] is True
    assert result.verification["committed"] is True
    assert result.verification["degraded"] is True
    assert not first.exists()
    assert (engine.config.backup_root / "latest").resolve() == result.snapshot_path


def test_recursive_prune_refuses_a_replaced_directory(tmp_path: Path) -> None:
    parent = tmp_path / "snapshots"
    parent.mkdir()
    original = parent / "generation"
    original.mkdir()
    descriptor, identity = local_snapshot._open_directory(original)
    try:
        original.rmdir()
        original.mkdir()
        sentinel = original / "do-not-delete"
        sentinel.write_text("preserve\n", encoding="utf-8")

        with pytest.raises(BackupError, match="identity changed"):
            local_snapshot._quarantine_and_remove_tree(
                original, parent, descriptor, identity
            )

        assert sentinel.read_text(encoding="utf-8") == "preserve\n"
    finally:
        os.close(descriptor)


@pytest.mark.parametrize("managed_child", ["snapshots", "staging"])
def test_run_refuses_symlinked_managed_directories(
    tmp_path: Path, managed_child: str
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    mark_managed_root(backup_root)
    outside = tmp_path / f"outside-{managed_child}"
    outside.mkdir()
    sentinel = outside / "do-not-delete.txt"
    sentinel.write_text("outside\n", encoding="utf-8")
    (backup_root / managed_child).symlink_to(outside, target_is_directory=True)
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json", backup_root=backup_root, source=source
        )
    )

    with pytest.raises(BackupError, match=f"{managed_child}.*real directory"):
        engine.run()

    assert sentinel.read_text(encoding="utf-8") == "outside\n"


def test_run_refuses_latest_symlink_outside_managed_snapshots(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    mark_managed_root(backup_root)
    outside = tmp_path / "outside-snapshot"
    outside.mkdir()
    (backup_root / "latest").symlink_to(outside, target_is_directory=True)
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json", backup_root=backup_root, source=source
        )
    )

    with pytest.raises(BackupError, match="unsafe latest symlink"):
        engine.run()

    assert (backup_root / "latest").resolve() == outside
    assert not (backup_root / "snapshots").exists()


def test_run_refuses_symlinked_lock_without_touching_target(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    mark_managed_root(backup_root)
    outside = tmp_path / "outside.lock"
    outside.write_text("outside\n", encoding="utf-8")
    outside.chmod(0o644)
    (backup_root / "run.lock").symlink_to(outside)
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json", backup_root=backup_root, source=source
        )
    )

    with pytest.raises(BackupError, match="lock.*regular file"):
        engine.run()

    assert outside.read_text(encoding="utf-8") == "outside\n"
    assert outside.stat().st_mode & 0o777 == 0o644


def test_failed_staged_verification_preserves_latest_and_prior_generations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    changing = source / "changing.txt"
    changing.write_text("generation 1\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=backup_root,
            source=source,
            retention=2,
        )
    )
    zone = ZoneInfo("Asia/Tokyo")
    first = engine.run(now=datetime(2026, 8, 15, 5, 0, tzinfo=zone))
    changing.write_text("generation 2\n", encoding="utf-8")
    second = engine.run(now=datetime(2026, 8, 16, 5, 0, tzinfo=zone))
    real_verify = local_snapshot.verify_snapshot

    def fail_staging_verification(path: Path) -> dict[str, object]:
        if "staging" in path.parts:
            raise BackupError("injected staged verification failure")
        return real_verify(path)

    monkeypatch.setattr(local_snapshot, "verify_snapshot", fail_staging_verification)
    changing.write_text("generation 3\n", encoding="utf-8")

    with pytest.raises(BackupError, match="injected staged verification failure"):
        engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=zone))

    assert (backup_root / "latest").resolve() == second.snapshot_path
    assert first.snapshot_path.is_dir()
    assert second.snapshot_path.is_dir()
    assert sorted((backup_root / "snapshots").iterdir()) == [
        first.snapshot_path,
        second.snapshot_path,
    ]


def test_retention_does_not_delete_marker_only_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    changing = source / "changing.txt"
    changing.write_text("generation 1\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=backup_root,
            source=source,
            retention=1,
        )
    )
    zone = ZoneInfo("Asia/Tokyo")
    first = engine.run(now=datetime(2026, 8, 16, 5, 0, tzinfo=zone))
    marker_only = backup_root / "snapshots/0000-marker-only"
    marker_only.mkdir()
    (marker_only / "manifest.json").write_text("{}\n", encoding="utf-8")
    (marker_only / "COMPLETE").write_text("not-a-hash\n", encoding="ascii")
    changing.write_text("generation 2\n", encoding="utf-8")

    second = engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=zone))

    assert marker_only.is_dir()
    assert not first.snapshot_path.exists()
    assert second.snapshot_path.is_dir()


def test_run_refuses_symlinked_snapshot_generation_without_deleting_outside(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    changing = source / "changing.txt"
    changing.write_text("generation 1\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json", backup_root=backup_root, source=source
        )
    )
    zone = ZoneInfo("Asia/Tokyo")
    first = engine.run(now=datetime(2026, 8, 16, 5, 0, tzinfo=zone))
    outside = tmp_path / "outside-snapshot"
    shutil.copytree(first.snapshot_path, outside)
    sentinel = outside / "do-not-delete.txt"
    sentinel.write_text("outside\n", encoding="utf-8")
    (backup_root / "snapshots/0000-symlink").symlink_to(
        outside, target_is_directory=True
    )
    changing.write_text("generation 2\n", encoding="utf-8")

    with pytest.raises(BackupError, match="symlinked snapshot generation"):
        engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=zone))

    assert (backup_root / "latest").resolve() == first.snapshot_path
    assert sentinel.read_text(encoding="utf-8") == "outside\n"
    assert list((backup_root / "staging").iterdir()) == []


def test_pruning_failure_keeps_backup_success_semantics_and_prior_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    changing = source / "changing.txt"
    changing.write_text("generation 1\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=backup_root,
            source=source,
            retention=1,
        )
    )
    zone = ZoneInfo("Asia/Tokyo")
    first = engine.run(now=datetime(2026, 8, 16, 5, 0, tzinfo=zone))

    def fail_pruning(directory_descriptor: int) -> None:
        del directory_descriptor
        raise OSError("injected pruning failure")

    monkeypatch.setattr(
        local_snapshot, "_remove_directory_contents_fd", fail_pruning
    )
    changing.write_text("generation 2\n", encoding="utf-8")

    second = engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=zone))

    assert (backup_root / "latest").resolve() == second.snapshot_path
    assert first.snapshot_path.is_dir()
    assert second.snapshot_path.is_dir()


def test_config_rejects_symlinked_backup_root_without_touching_target(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    target = tmp_path / "outside"
    target.mkdir()
    sentinel = target / "sentinel"
    sentinel.write_text("preserve\n", encoding="utf-8")
    linked_root = tmp_path / "linked-backups"
    linked_root.symlink_to(target, target_is_directory=True)
    config_path = write_config(
        tmp_path / "backup.json", backup_root=linked_root, source=source
    )

    with pytest.raises(BackupError, match="may not traverse a symlink"):
        BackupEngine.from_file(config_path)

    assert sentinel.read_text(encoding="utf-8") == "preserve\n"


def test_config_rejects_backup_root_inside_a_source(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=source / "backups",
        source=source,
    )

    with pytest.raises(BackupError, match="must not overlap"):
        BackupEngine.from_file(config_path)


def test_snapshot_binds_to_the_exact_configuration_loaded_for_the_run(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=tmp_path / "backups",
        source=source,
    )
    loaded_bytes = config_path.read_bytes()
    engine = BackupEngine.from_file(config_path)
    config_path.write_text("{}\n", encoding="utf-8")

    snapshot = engine.run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    ).snapshot_path
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["config_sha256"] == hashlib.sha256(loaded_bytes).hexdigest()


def test_status_rejects_a_stale_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
        )
    )
    zone = ZoneInfo("Asia/Tokyo")
    engine.run(now=datetime(2026, 8, 15, 5, 0, tzinfo=zone))

    with pytest.raises(BackupError, match="stale"):
        engine.status(now=datetime(2026, 8, 17, 5, 0, tzinfo=zone))


def test_status_rejects_snapshot_from_a_superseded_policy(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=tmp_path / "backups",
        source=source,
    )
    zone = ZoneInfo("Asia/Tokyo")
    BackupEngine.from_file(config_path).run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=zone)
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["sources"][0]["sqlite"] = "none"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(BackupError, match="current backup policy"):
        BackupEngine.from_file(config_path).status(
            now=datetime(2026, 8, 17, 6, 0, tzinfo=zone)
        )


@pytest.mark.parametrize(
    ("source_name", "sqlite_policy", "message"),
    [
        ("..", "discover", "invalid or duplicate source name"),
        ("runtime", "typo", "sqlite must be discover or none"),
    ],
)
def test_config_rejects_unsafe_source_contracts(
    tmp_path: Path, source_name: str, sqlite_policy: str, message: str
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=tmp_path / "backups",
        source=source,
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["sources"][0]["name"] = source_name
    config["sources"][0]["sqlite"] = sqlite_policy
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(BackupError, match=message):
        BackupEngine.from_file(config_path)


def test_config_rejects_malformed_collection_shapes_as_backup_errors(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=tmp_path / "backups",
        source=source,
    )
    valid = json.loads(config_path.read_text(encoding="utf-8"))
    malformed_values = [
        {**valid, "retention": []},
        {**valid, "retention": {"successful_snapshots": True}},
        {**valid, "sources": {}},
        {**valid, "sources": ["not-an-object"]},
    ]

    for malformed in malformed_values:
        config_path.write_text(json.dumps(malformed), encoding="utf-8")
        with pytest.raises(BackupError):
            BackupEngine.from_file(config_path)


def test_run_removes_only_validated_stale_staging_directories(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    mark_managed_root(backup_root)
    (backup_root / "snapshots").mkdir()
    staging = backup_root / "staging"
    staging.mkdir()
    stale = staging / ".2026-08-16T050000+0900-0123456789abcdef0123456789abcdef"
    stale.mkdir()
    (stale / local_snapshot.STAGING_MARKER).write_text(
        json.dumps(local_snapshot.STAGING_CONTRACT), encoding="utf-8"
    )
    (stale / "partial-secret.txt").write_text("partial\n", encoding="utf-8")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=backup_root,
            source=source,
        )
    )

    result = engine.run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    )

    assert result.snapshot_path.is_dir()
    assert list(staging.iterdir()) == []


def test_run_preserves_and_rejects_unowned_staging_directory(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    backup_root = tmp_path / "backups"
    mark_managed_root(backup_root)
    (backup_root / "snapshots").mkdir()
    staging = backup_root / "staging"
    staging.mkdir()
    unowned = staging / "do-not-delete"
    unowned.mkdir()
    sentinel = unowned / "sentinel"
    sentinel.write_text("preserve\n", encoding="utf-8")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json", backup_root=backup_root, source=source
        )
    )

    with pytest.raises(BackupError, match="unsafe stale staging entry"):
        engine.run()

    assert sentinel.read_text(encoding="utf-8") == "preserve\n"


def test_interrupted_owned_stage_is_reclaimed_by_next_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
        )
    )
    real_fsync_tree = local_snapshot._fsync_tree

    def interrupt_payload(path: Path) -> None:
        if path.name == "payload":
            raise KeyboardInterrupt("injected interruption")
        real_fsync_tree(path)

    monkeypatch.setattr(local_snapshot, "_fsync_tree", interrupt_payload)
    with pytest.raises(KeyboardInterrupt):
        engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo")))

    staging = engine.config.backup_root / "staging"
    leftovers = list(staging.iterdir())
    assert len(leftovers) == 1
    assert (leftovers[0] / local_snapshot.STAGING_MARKER).is_file()

    monkeypatch.setattr(local_snapshot, "_fsync_tree", real_fsync_tree)
    result = engine.run(
        now=datetime(2026, 8, 17, 5, 1, tzinfo=ZoneInfo("Asia/Tokyo"))
    )

    assert result.snapshot_path.is_dir()
    assert list(staging.iterdir()) == []


def test_run_refuses_overlapping_execution(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    config_path = write_config(
        tmp_path / "backup.json",
        backup_root=backup_root,
        source=source,
    )
    engine = BackupEngine.from_file(config_path)
    mark_managed_root(backup_root)

    with (backup_root / "run.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BackupError, match="already running"):
            engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo")))


def test_container_source_replaces_live_copies_with_online_sqlite_backups(
    tmp_path: Path,
) -> None:
    live_data = tmp_path / "container-data"
    live_data.mkdir()
    (live_data / "uploads").mkdir()
    (live_data / "uploads/file.txt").write_text("attachment\n", encoding="utf-8")
    database = live_data / "webui.db"
    writer = sqlite3.connect(database)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE chat (message TEXT NOT NULL)")
    writer.execute("INSERT INTO chat VALUES ('persist this')")
    writer.commit()

    config = {
        "schema_version": 1,
        "habit_id": "daily-local-continuity-backup",
        "timezone": "Asia/Tokyo",
        "retention": {"successful_snapshots": 7},
        "backup_root": str(tmp_path / "backups"),
        "sources": [
            {
                "name": "openwebui-data",
                "kind": "docker-container",
                "container": "openwebui",
                "path": "/app/backend/data",
                "sqlite": "discover",
            }
        ],
    }
    config_path = tmp_path / "backup.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    container_client = FakeContainerClient(live_data)
    engine = BackupEngine.from_file(config_path, container_client=container_client)

    result = engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo")))
    writer.close()

    assert container_client.exports == [("openwebui", "/app/backend/data")]
    assert container_client.sqlite_backups == ["webui.db"]
    assert (result.snapshot_path / "data/openwebui-data/uploads/file.txt").read_text(
        encoding="utf-8"
    ) == "attachment\n"
    snapshot_db = result.snapshot_path / "data/openwebui-data/webui.db"
    assert not Path(str(snapshot_db) + "-wal").exists()
    with sqlite3.connect(snapshot_db.as_uri() + "?mode=ro", uri=True) as restored:
        assert restored.execute("SELECT message FROM chat").fetchone() == (
            "persist this",
        )
    assert verify_snapshot(result.snapshot_path)["ok"] is True


def test_sqlite_snapshot_preserves_source_mode(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    database = source / "state.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE memory (value TEXT)")
    database.chmod(0o640)
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
        )
    )

    result = engine.run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    )

    assert (result.snapshot_path / "data/runtime/state.db").stat().st_mode & 0o777 == 0o640


def test_unrelated_db_extension_file_is_copied_as_a_normal_file(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    unrelated = source / "asset.db"
    unrelated.write_bytes(b"this is not SQLite, despite the extension\n")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
        )
    )

    result = engine.run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    )

    assert (result.snapshot_path / "data/runtime/asset.db").read_bytes() == (
        unrelated.read_bytes()
    )
    manifest = json.loads(
        (result.snapshot_path / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["sqlite_databases"] == []


def test_sqlite_filename_with_rsync_metacharacters_cannot_omit_other_files(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    database = source / "*.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE memory (value TEXT)")
        connection.execute("INSERT INTO memory VALUES ('kept')")
    unrelated = source / "notes.db"
    unrelated.write_bytes(b"ordinary non-SQLite content\n")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
        )
    )

    result = engine.run(
        now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    )

    assert (result.snapshot_path / "data/runtime/notes.db").read_bytes() == (
        unrelated.read_bytes()
    )
    assert verify_snapshot(result.snapshot_path)["ok"] is True


def test_transient_unix_socket_is_excluded_and_persistent_state_is_kept(
    tmp_path: Path,
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "state.json").write_text('{"node":"pda"}\n', encoding="utf-8")
    socket_path = source / "tailscaled.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    try:
        config_path = write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
        )
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["sources"][0]["allowed_special_files"] = [
            {"path": "tailscaled.sock", "kind": "socket"}
        ]
        config_path.write_text(json.dumps(config), encoding="utf-8")
        engine = BackupEngine.from_file(config_path)
        result = engine.run(
            now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        )
    finally:
        listener.close()

    assert (result.snapshot_path / "data/runtime/state.json").is_file()
    assert not (result.snapshot_path / "data/runtime/tailscaled.sock").exists()
    manifest = json.loads(
        (result.snapshot_path / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["excluded_special_files"] == [
        {"path": "data/runtime/tailscaled.sock", "kind": "socket"}
    ]


def test_unknown_special_file_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    os.mkfifo(source / "unexpected.fifo")
    engine = BackupEngine.from_file(
        write_config(
            tmp_path / "backup.json",
            backup_root=tmp_path / "backups",
            source=source,
        )
    )

    with pytest.raises(BackupError, match="unknown special file"):
        engine.run(now=datetime(2026, 8, 17, 5, 0, tzinfo=ZoneInfo("Asia/Tokyo")))


def test_container_sqlite_temporary_copy_is_private_and_owned() -> None:
    assert "os.O_EXCL, 0o600" in DockerContainerClient._SQLITE_BACKUP_SCRIPT
    assert "os.mkdir(temporary, 0o700)" in DockerContainerClient._PREPARE_TEMP_SCRIPT
    assert 'temporary / ".pda-owned"' in DockerContainerClient._PREPARE_TEMP_SCRIPT
    assert "shutil.rmtree(path)" in DockerContainerClient._CLEANUP_SCRIPT


def test_container_readiness_waits_within_one_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = DockerContainerClient()
    inspections = 0
    calls: list[tuple[list[str], float]] = []

    def delayed_run(
        arguments: list[str], *, timeout: float = local_snapshot.SUBPROCESS_TIMEOUT_SECONDS
    ) -> subprocess.CompletedProcess[str]:
        nonlocal inspections
        calls.append((arguments, timeout))
        if arguments[0] == "inspect":
            inspections += 1
            state = "false\n" if inspections == 1 else "true\n"
            return subprocess.CompletedProcess(arguments, 0, stdout=state, stderr="")
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")

    sleeps: list[float] = []
    monkeypatch.setattr(client, "_run", delayed_run)
    monkeypatch.setattr(local_snapshot, "_sleep", sleeps.append)

    client.wait_until_ready("openwebui")

    assert inspections == 2
    assert sleeps == [local_snapshot.CONTAINER_READY_POLL_SECONDS]
    assert calls[-1][0][:3] == ["exec", "openwebui", "python"]
    assert all(
        timeout == local_snapshot.CONTAINER_PROBE_TIMEOUT_SECONDS
        for _, timeout in calls
    )


def test_rsync_and_docker_subprocesses_use_bounded_multigigabyte_timeouts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="true\n", stderr="")

    monkeypatch.setattr(local_snapshot.subprocess, "run", fake_run)
    source = tmp_path / "source"
    source.mkdir()
    local_snapshot._copy_tree(source, tmp_path / "destination")
    client = DockerContainerClient()
    monkeypatch.setattr(client, "_needs_group_wrapper", lambda: False)
    client._run(["inspect", "container"])

    assert [call["timeout"] for call in calls] == [12 * 60 * 60, 12 * 60 * 60]


def test_subprocess_timeout_becomes_backup_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def time_out(command: list[str], **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(command, timeout=12 * 60 * 60)

    monkeypatch.setattr(local_snapshot.subprocess, "run", time_out)
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(BackupError, match="timed out"):
        local_snapshot._copy_tree(source, tmp_path / "destination")


def test_sqlite_online_backup_has_an_operation_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE memory (value TEXT)")
        connection.execute("INSERT INTO memory VALUES ('remember')")
    readings = iter([0.0, 6 * 60 * 60 + 1.0])
    monkeypatch.setattr(
        local_snapshot,
        "_monotonic",
        lambda: next(readings, 6 * 60 * 60 + 1.0),
        raising=False,
    )

    with pytest.raises(BackupError, match="SQLite backup timed out"):
        local_snapshot._backup_sqlite(source, tmp_path / "backup.sqlite3")


def test_container_source_uses_docker_client_by_default(tmp_path: Path) -> None:
    config = {
        "schema_version": 1,
        "habit_id": "daily-local-continuity-backup",
        "timezone": "Asia/Tokyo",
        "retention": {"successful_snapshots": 7},
        "backup_root": str(tmp_path / "backups"),
        "sources": [
            {
                "name": "openwebui-data",
                "kind": "docker-container",
                "container": "openwebui",
                "path": "/app/backend/data",
                "sqlite": "discover",
            }
        ],
    }
    config_path = tmp_path / "backup.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    engine = BackupEngine.from_file(config_path)

    assert isinstance(engine.container_client, DockerContainerClient)
