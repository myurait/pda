from __future__ import annotations

import json
from pathlib import Path

from pda.backup import cli
from pda.backup.cli import main
from pda.backup.local_snapshot import BackupError


def write_config(path: Path, backup_root: Path, source: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "habit_id": "daily-local-continuity-backup",
                "timezone": "Asia/Tokyo",
                "retention": {"successful_snapshots": 7},
                "backup_root": str(backup_root),
                "sources": [
                    {
                        "name": "runtime",
                        "kind": "tree",
                        "path": str(source),
                        "sqlite": "discover",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_cli_run_and_status_return_machine_readable_success(
    tmp_path: Path, capsys
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    config = tmp_path / "backup.json"
    write_config(config, backup_root, source)

    assert main(["run", "--config", str(config)]) == 0
    run_output = json.loads(capsys.readouterr().out)
    assert run_output["ok"] is True
    assert Path(run_output["snapshot"]).is_dir()

    assert main(["status", "--config", str(config)]) == 0
    status_output = json.loads(capsys.readouterr().out)
    assert status_output["ok"] is True
    assert status_output["habit_id"] == "daily-local-continuity-backup"
    assert status_output["retention"] == 7

    restored = tmp_path / "restored-snapshot"
    assert (
        main(
            [
                "restore",
                "--config",
                str(config),
                "--snapshot",
                run_output["snapshot"],
                "--destination",
                str(restored),
            ]
        )
        == 0
    )
    restore_output = json.loads(capsys.readouterr().out)
    assert restore_output["ok"] is True
    assert (restored / "data/runtime/identity.txt").read_text(
        encoding="utf-8"
    ) == "PDA\n"


def test_cli_reports_sqlite_failures_as_structured_backup_errors(
    tmp_path: Path, capsys
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    corrupt = source / "corrupt.db"
    corrupt.write_bytes(b"SQLite format 3\x00" + b"not a valid database")
    config = tmp_path / "backup.json"
    write_config(config, tmp_path / "backups", source)

    assert main(["run", "--config", str(config)]) == 1

    captured = capsys.readouterr()
    error = json.loads(captured.err)
    assert error["ok"] is False
    assert "SQLite" in error["error"]
    assert not captured.out


def test_cli_does_not_report_failure_after_the_snapshot_is_committed(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "runtime"
    source.mkdir()
    (source / "identity.txt").write_text("PDA\n", encoding="utf-8")
    backup_root = tmp_path / "backups"
    config = tmp_path / "backup.json"
    write_config(config, backup_root, source)

    def fail_redundant_verification(path: Path) -> dict[str, object]:
        raise BackupError(f"unexpected post-commit verification: {path}")

    monkeypatch.setattr(cli, "verify_snapshot", fail_redundant_verification)

    assert main(["run", "--config", str(config)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert (backup_root / "latest").resolve() == Path(output["snapshot"])
