#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def run() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "src"))
    from pda.backup.cli import main

    return main()


if __name__ == "__main__":
    raise SystemExit(run())
