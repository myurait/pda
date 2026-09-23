import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import httpx

STATIC = Path(__file__).parent / "static"


def cells(workflow: dict) -> list[dict]:
    result = []
    for task in sorted(workflow.get("tasks", []), key=lambda item: item.get("seq", 0)):
        ref = task.get("referenceTaskName", "")
        if not ref.startswith(("c", "judge")):
            continue
        type_name, _, executor = task.get("taskDefName", "").rpartition(".")
        start, end = task.get("startTime", 0), task.get("endTime", 0)
        output = task.get("outputData") or {}
        result.append(
            {
                "ref": ref,
                "type": type_name,
                "executor": executor,
                "status": task.get("status"),
                "retry_count": task.get("retryCount", 0),
                "start_time": start,
                "end_time": end,
                "duration_ms": max(0, (end or int(time.time() * 1000)) - start) if start else 0,
                "reason": task.get("reasonForIncompletion"),
                "output_kind": output.get("kind"),
                "output_excerpt": json.dumps(output.get("payload"), ensure_ascii=False)[:200],
            }
        )
    return result


def summary(row: dict) -> str:
    kind = row.get("body", "")
    fields = {
        "tool.call": ["pda_tool_title"],
        "command.run": ["pda_command", "pda_exit_code"],
        "judge.answer": ["pda_question_id", "pda_answer"],
        "output.classified": ["pda_kind"],
        "engine.task": ["pda_status"],
        "turn.end": ["pda_stop_reason"],
    }
    return " / ".join(str(row.get(field, "")) for field in fields.get(kind, []))


class View:
    def __init__(self, conductor: httpx.Client, observe: httpx.Client, stream: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_]+", stream):
            raise ValueError("invalid_stream")
        self.conductor, self.observe, self.stream = conductor, observe, stream

    def workflow(self, job_id: str) -> dict:
        response = self.conductor.get(f"/api/workflow/{job_id}", params={"includeTasks": "true"})
        response.raise_for_status()
        return response.json()

    def jobs(self) -> list[dict]:
        running = self.conductor.get("/api/workflow/running/pda_job")
        running.raise_for_status()
        params = {"query": "workflowType='pda_job'", "sort": "startTime:DESC", "size": 50}
        recent = self.conductor.get("/api/workflow/search", params=params)
        if recent.is_client_error:
            params["query"] = "workflowType IN (pda_job)"
            recent = self.conductor.get("/api/workflow/search", params=params)
        recent.raise_for_status()
        ids = list(
            dict.fromkeys(
                [*running.json(), *[row["workflowId"] for row in recent.json()["results"]]]
            )
        )
        result = []
        for job_id in ids:
            workflow = self.workflow(job_id)
            result.append(
                {
                    "job_id": job_id,
                    "status": workflow["status"],
                    "start_time": workflow.get("startTime", 0),
                    "end_time": workflow.get("endTime", 0),
                    "executors": list(dict.fromkeys(cell["executor"] for cell in cells(workflow))),
                    "initial_input": workflow.get("input", {}).get("initial_input", "")[:80],
                }
            )
        return sorted(result, key=lambda row: row["start_time"], reverse=True)

    def detail(self, job_id: str) -> dict:
        workflow = self.workflow(job_id)
        return {
            "job_id": job_id,
            "status": workflow["status"],
            "reason": workflow.get("reasonForIncompletion"),
            "initial_input": workflow.get("input", {}).get("initial_input", ""),
            "cells": cells(workflow),
        }

    def events(self, job_id: str, cell: str | None) -> list[dict]:
        def quote(value: str) -> str:
            return value.replace("'", "''")

        sql = f"SELECT * FROM \"{self.stream}\" WHERE pda_job_id = '{quote(job_id)}'"
        if cell:
            sql += f" AND pda_cell_id = '{quote(cell)}'"
        sql += " ORDER BY _timestamp ASC LIMIT 1000"
        response = self.observe.post(
            "/api/default/_search",
            json={
                "query": {
                    "sql": sql,
                    "start_time": 1,
                    "end_time": int(time.time() * 1000000),
                    "from": 0,
                    "size": 1000,
                }
            },
        )
        response.raise_for_status()
        return [
            {
                "time": row.get("_timestamp"),
                "kind": row.get("body"),
                "executor": row.get("pda_executor_id"),
                "cell": row.get("pda_cell_id"),
                "summary": summary(row),
            }
            for row in response.json()["hits"]
        ]


class RouteNotFound(Exception):
    pass


class Handler(BaseHTTPRequestHandler):
    view: View

    def log_message(self, format: str, *args: object) -> None:
        print(json.dumps({"event": "http", "message": format % args}), flush=True)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        static = {
            "/": ("index.html", "text/html"),
            "/static/app.js": ("app.js", "text/javascript"),
            "/static/app.css": ("app.css", "text/css"),
        }
        status, content_type = 200, "application/json"
        try:
            if url.path in static:
                filename, content_type = static[url.path]
                body = (STATIC / filename).read_bytes()
            else:
                parts = url.path.strip("/").split("/")
                if parts == ["api", "jobs"]:
                    data = self.view.jobs()
                elif len(parts) in (3, 4) and parts[:2] == ["api", "jobs"]:
                    job_id = unquote(parts[2])
                    if len(parts) == 3:
                        data = self.view.detail(job_id)
                    elif parts[3] == "events":
                        data = self.view.events(job_id, parse_qs(url.query).get("cell", [None])[0])
                    else:
                        raise RouteNotFound
                else:
                    raise RouteNotFound
                body = json.dumps(data, ensure_ascii=False).encode()
        except RouteNotFound:
            status, body = 404, b'{"reason":"not_found"}'
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            status = 502
            body = json.dumps({"reason": f"upstream_error: {type(exc).__name__}"}).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    with (
        httpx.Client(
            base_url=os.environ.get("CONDUCTOR_URL", "http://localhost:8080"), timeout=10
        ) as conductor,
        httpx.Client(
            base_url=os.environ.get("OPENOBSERVE_URL", "http://openobserve:5080"),
            timeout=10,
            auth=(os.environ["ZO_ROOT_USER_EMAIL"], os.environ["ZO_ROOT_USER_PASSWORD"]),
        ) as observe,
    ):
        Handler.view = View(conductor, observe, os.environ.get("OPENOBSERVE_STREAM", "pda_events"))
        server = ThreadingHTTPServer(
            ("0.0.0.0", int(os.environ.get("PDA_VIEW_PORT", "5081"))), Handler
        )
        server.serve_forever()


if __name__ == "__main__":
    main()
