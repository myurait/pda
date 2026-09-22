"""Run only the command declared by the type; retain bounded output tails."""

import asyncio
import json
import os
import signal
import tempfile
import time
from pathlib import Path

from pda_wrapper.drivers import RuntimeFailure
from pda_wrapper.events import Events, json_text


async def run(
    type_def: dict,
    task_input: dict,
    events: Events,
    default_workdir: str = "/work",
    timeout: float = 600,
) -> tuple[str, str]:
    try:
        value = json.loads(task_input["input"])
    except json.JSONDecodeError:
        value = {}
    workdir = value.get("workdir", default_workdir) if isinstance(value, dict) else default_workdir
    if not isinstance(workdir, str) or not Path(workdir).is_dir():
        raise RuntimeFailure("tools_workdir_not_found")
    command = type_def["command"]
    started = time.monotonic()
    code = -1
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            process = await asyncio.create_subprocess_exec(
                *command, cwd=workdir, stdout=stdout, stderr=stderr, start_new_session=True
            )
            try:
                code = await asyncio.wait_for(process.wait(), timeout=timeout)
            except (TimeoutError, asyncio.CancelledError):
                os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
                code = -9
                raise
        except (OSError, TimeoutError) as exc:
            raise RuntimeFailure(f"tools_runtime:{type(exc).__name__}:{exc}") from exc
        finally:
            events.emit(
                "command.run",
                **{
                    "pda.command": json_text(command),
                    "pda.exit_code": code,
                    "pda.duration_ms": int((time.monotonic() - started) * 1000),
                },
            )

        def tail(file: object) -> str:
            file.seek(0, 2)
            file.seek(max(0, file.tell() - 16000))
            return file.read().decode(errors="replace")[-4000:]

        return json_text(
            {
                "kind": "result",
                "payload": {
                    "passed": code == 0,
                    "exit_code": code,
                    "stdout_tail": tail(stdout),
                    "stderr_tail": tail(stderr),
                },
            }
        ), "end_turn"
