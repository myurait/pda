#!/usr/bin/env python3
"""Apply the repository's desired settings to the daily state report job.

The report job runs inside Hermes, so its instruction text, toolsets and
delivery target live in the Hermes job table rather than in this repository.
This script pushes the versioned instruction file and the toolsets the job
needs onto that table, so the job's configuration can be restored from Git
instead of being reconstructed by hand.

The board must be read with the Kanban tools rather than through the shell:
the job holds no scope-control tool, so its turn is never reviewed and any
shell command outside the deterministic read-only set is refused.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

JOB_ID = "4d9f09797922"
TOOLSETS = ["terminal", "kanban"]
DELIVERY = "local"
HERMES_HOME = Path("~/.hermes/hermes-agent").expanduser()


def run() -> int:
    prompt_file = Path(__file__).resolve().parent / "daily_report_prompt.txt"
    prompt = prompt_file.read_text(encoding="utf-8")
    sys.path.insert(0, str(HERMES_HOME))
    from cron.jobs import update_job

    updated = update_job(
        JOB_ID,
        {"prompt": prompt, "enabled_toolsets": list(TOOLSETS), "deliver": DELIVERY},
    )
    if updated is None:
        print(json.dumps({"ok": False, "error": f"job not found: {JOB_ID}"}), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "job_id": updated.get("id"),
                "schedule": updated.get("schedule_display"),
                "deliver": updated.get("deliver"),
                "enabled_toolsets": updated.get("enabled_toolsets"),
                "prompt_characters": len(updated.get("prompt") or ""),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
