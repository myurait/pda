import asyncio
import contextlib
import os
import signal
import time

from pda_wrapper.drivers import RuntimeFailure, RuntimeOutput
from pda_wrapper.events import TaskEvents, json_text


async def _read_tail(stream: asyncio.StreamReader, output: list[str]) -> None:
    import codecs

    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    while chunk := await stream.read(8192):
        output[0] = (output[0] + decoder.decode(chunk))[-4000:]
    output[0] = (output[0] + decoder.decode(b"", final=True))[-4000:]


async def run(
    command: list[str], events: TaskEvents, workdir: str
) -> RuntimeOutput:
    started = time.monotonic()
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=workdir,
            start_new_session=True,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise RuntimeFailure("tools_start_failed") from exc
    stdout, stderr = [""], [""]
    readers = [
        asyncio.create_task(_read_tail(process.stdout, stdout)),
        asyncio.create_task(_read_tail(process.stderr, stderr)),
    ]
    try:
        await process.wait()
    except asyncio.CancelledError:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            await asyncio.wait_for(process.wait(), 2)
        except TimeoutError:
            pass
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()
        raise
    finally:
        await asyncio.gather(*readers)
        events.emit(
            "command.run",
            **{
                "pda.command": command,
                "pda.workdir": workdir,
                "pda.exit_code": process.returncode,
                "pda.duration_ms": int((time.monotonic() - started) * 1000),
            },
        )
    return RuntimeOutput(
        json_text(
            {
                "kind": "result",
                "payload": {
                    "passed": process.returncode == 0,
                    "exit_code": process.returncode,
                    "stdout_tail": stdout[0],
                    "stderr_tail": stderr[0],
                },
            }
        )
    )
