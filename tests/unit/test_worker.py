import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

import httpx
import pytest

from pda_wrapper.events import Events
from pda_wrapper.registry import Registry
from pda_wrapper.worker import Worker, runtime_deadline


@pytest.mark.parametrize(
    ("value", "expected"), [(600, 590), (60, 50), (30, 20), (15, 7.5), (5, 2.5)]
)
def test_deadline_calculation(value, expected) -> None:
    assert runtime_deadline(value) == expected


@pytest.mark.parametrize(
    ("mode", "status", "reason"),
    [
        ("echo", "COMPLETED", None),
        ("invalid", "FAILED_WITH_TERMINAL_ERROR", "invalid_kind_or_missing_payload"),
    ],
)
def test_processing(registry, events, task, tmp_path, monkeypatch, mode, status, reason) -> None:
    monkeypatch.setenv("FAKE_MODE", mode)
    logs = []

    def request(req: httpx.Request) -> httpx.Response:
        logs.append(json.loads(req.content))
        return httpx.Response(200)

    async def scenario() -> dict:
        async with httpx.AsyncClient(
            base_url="http://c", transport=httpx.MockTransport(request)
        ) as c:
            return await Worker(registry, "fake-a", c, events, str(tmp_path)).process(task)

    result = asyncio.run(scenario())
    assert result["status"] == status and result["reasonForIncompletion"] == reason
    if status == "COMPLETED":
        assert result["outputData"]["meta"]["stop_reason"] == "end_turn"
        assert len(logs) == 1 and "\n" not in logs[0]


def test_bad_input_rejected_before_driver(registry, events, task, tmp_path, capsys) -> None:
    del task["inputData"]["input"]

    async def scenario() -> dict:
        async with httpx.AsyncClient(base_url="http://c") as c:
            return await Worker(registry, "fake-a", c, events, str(tmp_path)).process(task)

    result = asyncio.run(scenario())
    assert result["reasonForIncompletion"] == "input_schema_mismatch"
    assert result["status"] == "FAILED_WITH_TERMINAL_ERROR"
    assert "input.assembled" not in capsys.readouterr().out


def test_poll_only_declared_names_and_stop(registry, events) -> None:
    requests = []

    async def scenario() -> None:
        def request(req: httpx.Request) -> httpx.Response:
            requests.append(req.url.path)
            if len(requests) == 4:
                worker.stop()
            return httpx.Response(204)

        async with httpx.AsyncClient(
            base_url="http://c", transport=httpx.MockTransport(request)
        ) as c:
            worker = Worker(registry, "fake-a", c, events)
            await worker.run()
            await worker.run()

    asyncio.run(scenario())
    assert requests == [
        f"/api/tasks/poll/{name}.fake-a" for name in registry.executors["fake-a"]["types"]
    ]


def test_registry_snapshot_loaded_once(monkeypatch, tmp_path) -> None:
    counts = {}
    original = Path.read_text

    def read(path, *args, **kwargs):
        counts[str(path)] = counts.get(str(path), 0) + 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    registry = Registry("registry")
    declaration = registry.executors["fake-a"]

    async def scenario() -> None:
        async with httpx.AsyncClient(
            base_url="http://c", transport=httpx.MockTransport(lambda req: httpx.Response(204))
        ) as c:
            worker = Worker(registry, "fake-a", c, Events(), str(tmp_path))
            pending = asyncio.create_task(worker.run())
            await asyncio.sleep(1.1)
            worker.stop()
            await pending

    asyncio.run(scenario())
    assert registry.executors["fake-a"] is declaration
    assert all(count == 1 for path, count in counts.items() if path.endswith(".yaml"))


def test_runtime_30_second_deadline(registry, events, task, tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("FAKE_MODE", "slow")
    task["responseTimeoutSeconds"] = 30

    async def scenario() -> dict:
        async with httpx.AsyncClient(base_url="http://c") as c:
            return await Worker(registry, "fake-a", c, events, str(tmp_path)).process(task)

    started = time.monotonic()
    result = asyncio.run(scenario())
    elapsed = time.monotonic() - started
    assert 19.5 <= elapsed < 24
    assert result["status"] == "FAILED" and result["reasonForIncompletion"] == "runtime_deadline"
    assert '"pda.stop_reason": "cancelled"' in capsys.readouterr().out


def test_actual_sigterm_cancels_and_never_polls_again(tmp_path, task) -> None:
    code = """
import asyncio, json, signal, sys, httpx
from pda_wrapper.registry import Registry
from pda_wrapper.events import Events, log
from pda_wrapper.worker import Worker
async def main():
    registry = Registry('registry')
    registry.executors['fake-a']['adapter']['command'][0] = sys.executable
    def request(req):
        log('request', method=req.method, path=req.url.path)
        if '/poll/' in req.url.path:
            return httpx.Response(200, json=json.loads(sys.argv[1]))
        log('result', result=json.loads(req.content))
        return httpx.Response(200)
    async with httpx.AsyncClient(base_url='http://c', transport=httpx.MockTransport(request)) as c:
        events = Events()
        worker = Worker(registry, 'fake-a', c, events, sys.argv[2])
        def stop():
            log('sigterm')
            worker.stop()
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop)
        await worker.run()
        await events.close()
asyncio.run(main())
"""

    async def scenario() -> list[dict]:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            code,
            json.dumps(task),
            str(tmp_path),
            env={**os.environ, "FAKE_MODE": "slow"},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        records = []
        try:
            async with asyncio.timeout(10):
                while True:
                    line = await proc.stdout.readline()
                    assert line, (await proc.stderr.read()).decode()
                    record = json.loads(line)
                    records.append(record)
                    if record.get("body") == "tool.result":
                        break
            started = time.monotonic()
            proc.send_signal(signal.SIGTERM)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), 19)
            records.extend(json.loads(line) for line in stdout.splitlines())
            assert proc.returncode == 0, stderr.decode()
            assert time.monotonic() - started < 20
            return records
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()

    records = asyncio.run(scenario())
    interrupted = next(i for i, r in enumerate(records) if r.get("message") == "sigterm")
    assert not any("/poll/" in r.get("path", "") for r in records[interrupted:])
    result = next(r["result"] for r in records if r.get("message") == "result")
    assert result["status"] == "FAILED" and result["reasonForIncompletion"] == "interrupted"
    assert any(r.get("attributes", {}).get("pda.stop_reason") == "cancelled" for r in records)
