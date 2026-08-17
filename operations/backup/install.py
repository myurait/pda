#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def run() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "src"))
    from pda.backup.install import install_units, systemctl_user

    install_units(
        repo_root=repo_root,
        home=Path.home(),
        run_systemctl=systemctl_user,
    )


if __name__ == "__main__":
    run()
