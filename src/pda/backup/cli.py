from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .local_snapshot import BackupEngine, BackupError, restore_snapshot, verify_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pda-backup")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "status", "verify", "restore"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config", required=True, type=Path)
    verify = subparsers.choices["verify"]
    verify.add_argument("--snapshot", type=Path)
    restore = subparsers.choices["restore"]
    restore.add_argument("--snapshot", required=True, type=Path)
    restore.add_argument("--destination", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        engine = BackupEngine.from_file(args.config)
        if args.command == "run":
            result = engine.run()
            output = {
                **result.verification,
                "snapshot": str(result.snapshot_path),
                "retention": engine.config.retention,
            }
        elif args.command == "status":
            output = {
                **engine.status(),
                "retention": engine.config.retention,
            }
        elif args.command == "verify":
            snapshot = args.snapshot or (engine.config.backup_root / "latest")
            verification = verify_snapshot(snapshot)
            output = {
                **verification,
                "snapshot": str(snapshot.resolve()),
                "retention": engine.config.retention,
            }
        else:
            verification = restore_snapshot(
                args.snapshot,
                args.destination,
                backup_root=engine.config.backup_root,
            )
            output = {
                **verification,
                "snapshot": str(args.snapshot.expanduser().resolve()),
                "destination": str(args.destination.expanduser().resolve()),
                "retention": engine.config.retention,
            }
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 0
    except (BackupError, OSError, ValueError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {"ok": False, "error": str(error)}, ensure_ascii=False, sort_keys=True
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
