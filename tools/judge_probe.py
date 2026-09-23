import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx

from pda_wrapper.drivers import RuntimeFailure
from pda_wrapper.drivers.jev import available_executors, build_state, live_answers
from pda_wrapper.history import previous_outputs
from pda_wrapper.registry import Registry


async def probe(args: argparse.Namespace) -> dict:
    registry = Registry(args.registry)
    async with httpx.AsyncClient(base_url=args.conductor, timeout=10) as conductor:
        if args.workflow_file:
            workflow = json.loads(args.workflow_file.read_text())
        else:
            response = await conductor.get(
                f"/api/workflow/{args.job_id}", params={"includeTasks": "true"}
            )
            response.raise_for_status()
            workflow = response.json()
        state = build_state(workflow, registry, args.initial_input)
        try:
            state["available_executors"] = await available_executors(conductor, registry)
        except (httpx.HTTPError, ValueError, RuntimeFailure):
            pass
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=120) as client:
        answers = await live_answers(state, registry, client, Path("secrets/typesafe_credentials"))
    summary = {
        "rounds": previous_outputs(workflow)[0],
        "previous_outputs": len(state["previous_outputs"]),
    }
    if "available_executors" in state:
        summary["available_executors"] = state["available_executors"]
    return {
        "state_summary": summary,
        "answers": answers,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--job-id")
    source.add_argument("--workflow-file", type=Path)
    parser.add_argument("--initial-input")
    parser.add_argument("--conductor", default="http://localhost:8080")
    parser.add_argument("--registry", type=Path, default=Path("registry"))
    print(json.dumps(asyncio.run(probe(parser.parse_args())), ensure_ascii=False))


if __name__ == "__main__":
    main()
