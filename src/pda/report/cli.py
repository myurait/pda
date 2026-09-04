from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .daily_delivery import DeliveryError, load_policy, run, status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pda-daily-report")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("deliver", "status"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        policy = load_policy(args.config)
        output = run(policy) if args.command == "deliver" else status(policy)
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 0 if output.get("ok") else 1
    except (DeliveryError, OSError, ValueError, json.JSONDecodeError) as error:
        print(
            json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, sort_keys=True),
            file=sys.stderr,
        )
        return 1
