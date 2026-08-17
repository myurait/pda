"""
title: Hermes Agent (Progress)
author: Local audited adaptation of Hannah's openwebui-hermes
version: 2.1.0-local.5
required_open_webui_version: 0.10.2
description: Hermes Runs API adapter with model-invisible tool status, per-chat sessions, interactive approvals, fail-safe cleanup, and content-free completion push.
"""

# Derived from MartianInGreen/openwebui-hermes (MIT), pinned during review at
# dbb400dd344344ac9b556c5bef7ccda83f459796.  Local changes keep tool and
# reasoning progress out of assistant content, isolate sessions by Open WebUI
# chat, fail closed on approvals, and close every status/run path.
#
# MIT License
# Copyright (c) 2026 Hannah
# Copyright (c) 2026 local modifications
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

FUNCTION_ID = "hermes_progress_pipe"
MODEL_NAME = "Hermes Agent (Progress)"
TERMINAL_EVENTS = frozenset({"run.completed", "run.failed", "run.cancelled"})
_SAFE_ROLE = frozenset({"user", "assistant"})


class Pipe:
    class Valves(BaseModel):
        HERMES_API_URL: str = Field(
            default="http://host.docker.internal:8642/v1",
            description="Hermes API base URL, including /v1.",
        )
        HERMES_API_KEY: str = Field(
            default="",
            description="Bearer key matching Hermes API_SERVER_KEY. Required by Hermes v0.18+.",
        )
        HERMES_MODEL: str = Field(
            default="hermes-agent",
            description="Hermes API model or configured model-route alias.",
        )
        RUN_TIMEOUT_SECONDS: int = Field(
            default=0,
            ge=0,
            le=604800,
            description="Maximum total time for one Hermes run in seconds; 0 disables the deadline.",
        )
        APPROVAL_TIMEOUT_SECONDS: int = Field(
            default=55,
            ge=15,
            le=1800,
            description=(
                "Maximum time to wait for the Open WebUI approval dialog. "
                "Keep this below Hermes approvals.timeout (60 seconds by default)."
            ),
        )
        SHOW_TOOL_PREVIEW: bool = Field(
            default=False,
            description="Show Hermes' redacted tool preview in status history. Off avoids storing command details in Open WebUI.",
        )
        TOOL_PREVIEW_CHARS: int = Field(
            default=160,
            ge=0,
            le=1000,
            description="Maximum displayed tool-preview length when enabled.",
        )
        SHOW_REASONING_STATUS: bool = Field(
            default=True,
            description="Show only a generic reasoning status; reasoning text is never stored or displayed.",
        )
        NTFY_SERVER_URL: str = Field(
            default="https://ntfy.sh",
            description="ntfy server root URL used for Open WebUI completion push.",
        )
        NTFY_TOPIC: str = Field(
            default="",
            description="Private ntfy topic. Empty disables completion push.",
        )
        OPENWEBUI_PUBLIC_URL: str = Field(
            default="",
            description="HTTPS Open WebUI URL opened when the push notification is tapped.",
        )

    class UserValves(BaseModel):
        pass

    def __init__(self) -> None:
        self.type = "pipe"
        self.id = FUNCTION_ID
        self.name = MODEL_NAME
        self.valves = self.Valves(
            HERMES_API_URL=os.getenv(
                "HERMES_API_URL", "http://host.docker.internal:8642/v1"
            ),
            HERMES_API_KEY=os.getenv("HERMES_API_KEY", ""),
            HERMES_MODEL=os.getenv("HERMES_MODEL", "hermes-agent"),
            NTFY_SERVER_URL=os.getenv("PDA_NTFY_SERVER_URL", "https://ntfy.sh"),
            NTFY_TOPIC=os.getenv("PDA_NTFY_TOPIC", ""),
            OPENWEBUI_PUBLIC_URL=os.getenv("PDA_OPENWEBUI_PUBLIC_URL", ""),
        )
        self.user_valves = self.UserValves()
        # asyncio keeps only weak references to tasks. Retain completion-push
        # tasks until delivery finishes so closing the response generator does
        # not silently discard them.
        self._notification_tasks: set[asyncio.Task] = set()

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[Any]]] = None,
        __event_call__: Optional[Callable[[dict], Awaitable[Any]]] = None,
        __chat_id__: Optional[str] = None,
        __session_id__: Optional[str] = None,
        __message_id__: Optional[str] = None,
        __metadata__: Optional[dict] = None,
    ) -> Any:
        messages = body.get("messages") or []
        if not messages:
            return {"error": {"detail": "No messages supplied"}}

        user_id = str((__user__ or {}).get("id") or "unknown-user")
        scope = self._scope_key(
            user_id=user_id,
            chat_id=__chat_id__,
            session_id=__session_id__,
            message_id=__message_id__,
        )
        hermes_session_id, hermes_session_key = self._hermes_session_ids(scope)

        latest = messages[-1]
        message = self._extract_text(latest.get("content", "")).strip()
        if not message:
            return {"error": {"detail": "The latest user message is empty"}}

        history, instructions = self._build_context(messages[:-1])
        stream = bool(body.get("stream", True))

        common = dict(
            message=message,
            history=history,
            instructions=instructions,
            session_id=hermes_session_id,
            session_key=hermes_session_key,
            event_emitter=__event_emitter__,
            event_call=__event_call__,
        )

        if stream:
            return StreamingResponse(
                self._stream_response(**common),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        return await self._blocking_response(**common)

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    item_type = str(item.get("type", "")).lower()
                    if item_type in {"text", "input_text", "output_text"}:
                        parts.append(str(item.get("text", "")))
                    elif item_type in {"image", "image_url", "input_image"}:
                        parts.append("[Image attached in Open WebUI; this Pipe currently forwards text only]")
            return "\n".join(part for part in parts if part)
        return str(content or "")

    @classmethod
    def _build_context(cls, messages: list[dict]) -> tuple[list[dict], Optional[str]]:
        history: list[dict] = []
        instructions: list[str] = []
        for raw in messages:
            if not isinstance(raw, dict):
                continue
            role = str(raw.get("role", "")).lower()
            content = cls._extract_text(raw.get("content", "")).strip()
            if not content:
                continue
            if role == "system":
                instructions.append(content)
            elif role in _SAFE_ROLE:
                # Deliberately copy only role/content.  Open WebUI statusHistory,
                # tool cards, and other UI metadata never enter Hermes context.
                history.append({"role": role, "content": content})
        return history, "\n\n".join(instructions) or None

    @staticmethod
    def _scope_key(
        *,
        user_id: str,
        chat_id: Optional[str],
        session_id: Optional[str],
        message_id: Optional[str],
    ) -> str:
        # Never collapse missing metadata into a shared "anonymous" session.
        conversation = str(chat_id or session_id or message_id or uuid.uuid4().hex)
        return f"openwebui:{user_id}:{conversation}"

    @staticmethod
    def _hermes_session_ids(scope: str) -> tuple[str, str]:
        digest = hashlib.sha256(scope.encode("utf-8", errors="replace")).hexdigest()[:32]
        return f"owui_{digest}", f"openwebui:{digest}"

    def _api_base(self) -> str:
        raw = str(self.valves.HERMES_API_URL or "").strip().rstrip("/")
        parsed = urlsplit(raw)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("HERMES_API_URL must use http or https")
        if not parsed.hostname:
            raise ValueError("HERMES_API_URL must include a hostname")
        if parsed.username or parsed.password:
            raise ValueError("Credentials are not allowed inside HERMES_API_URL")
        if parsed.query or parsed.fragment:
            raise ValueError("Query strings and fragments are not allowed in HERMES_API_URL")
        path = parsed.path.rstrip("/")
        if not path.endswith("/v1"):
            raise ValueError("HERMES_API_URL must end with /v1")
        return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))

    def _headers(self, session_key: str, *, accept_sse: bool = False) -> dict[str, str]:
        key = str(self.valves.HERMES_API_KEY or "").strip()
        if not key:
            raise ValueError("HERMES_API_KEY is required for Hermes v0.18+")
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "openwebui-hermes-progress/2.1-local",
            "X-Hermes-Session-Key": session_key,
        }
        if accept_sse:
            headers["Accept"] = "text/event-stream"
        return headers

    @staticmethod
    def _clean_text(value: Any, limit: int = 500) -> str:
        text = str(value or "")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > limit:
            return text[: max(0, limit - 1)] + "…"
        return text

    async def _emit_status(
        self,
        emitter: Optional[Callable[[dict], Awaitable[Any]]],
        description: str,
        *,
        done: bool,
        **extra: Any,
    ) -> None:
        if emitter is None:
            return
        data = {
            "action": "hermes_agent",
            "description": self._clean_text(description, 1200),
            "done": bool(done),
            **extra,
        }
        try:
            await emitter({"type": "status", "data": data})
        except Exception:
            # UI status transport must never fail the model run.
            logger.debug("Open WebUI status emission failed", exc_info=True)

    def _tool_description(self, event: dict, *, completed: bool) -> str:
        name = self._clean_text(event.get("tool") or "tool", 120)
        if completed:
            duration = event.get("duration")
            try:
                duration_text = f" ({float(duration):.2f}秒)"
            except (TypeError, ValueError):
                duration_text = ""
            if bool(event.get("error")):
                return f"失敗: {name}{duration_text}"
            return f"完了: {name}{duration_text}"

        description = f"実行中: {name}"
        if self.valves.SHOW_TOOL_PREVIEW and self.valves.TOOL_PREVIEW_CHARS > 0:
            preview = self._clean_text(
                event.get("preview"), int(self.valves.TOOL_PREVIEW_CHARS)
            )
            if preview:
                description += f" — {preview}"
        return description

    def _approval_message(self, event: dict) -> str:
        description = self._clean_text(
            event.get("description") or event.get("message") or event.get("reason"),
            1200,
        )
        command = self._clean_text(event.get("command"), 1800)
        risk = self._clean_text(event.get("risk") or event.get("risk_level"), 120)
        parts = ["Hermesがホスト側の操作承認を求めています。"]
        if description:
            parts.append(f"内容: {description}")
        if command:
            parts.append(f"コマンド: {command}")
        if risk:
            parts.append(f"リスク: {risk}")
        parts.append("実行を1回だけ許可しますか？")
        return "\n\n".join(parts)

    async def _resolve_approval(
        self,
        *,
        session: aiohttp.ClientSession,
        base: str,
        headers: dict[str, str],
        run_id: str,
        event: dict,
        event_emitter: Optional[Callable[[dict], Awaitable[Any]]],
        event_call: Optional[Callable[[dict], Awaitable[Any]]],
    ) -> None:
        prompt = self._approval_message(event)
        await self._emit_status(
            event_emitter,
            "ユーザーの承認を待っています…",
            done=False,
            approval=True,
        )

        choice = "deny"
        if event_call is not None:
            try:
                answer = await asyncio.wait_for(
                    event_call(
                        {
                            "type": "confirmation",
                            "data": {
                                "title": "Hermes: 操作の承認",
                                "message": prompt,
                            },
                        }
                    ),
                    timeout=int(self.valves.APPROVAL_TIMEOUT_SECONDS),
                )
                choice = "once" if bool(answer) else "deny"
            except asyncio.TimeoutError:
                choice = "deny"
                await self._emit_status(
                    event_emitter,
                    "承認がタイムアウトしたため拒否しました",
                    done=True,
                    approval=True,
                    error=True,
                )
            except Exception:
                choice = "deny"
                logger.warning("Open WebUI approval dialog failed; denying", exc_info=True)
        else:
            # No text fallback: an unrelated next chat message must never become
            # implicit approval for a dangerous host command.
            await self._emit_status(
                event_emitter,
                "承認UIを利用できないため操作を拒否しました",
                done=True,
                approval=True,
                error=True,
            )

        async with session.post(
            f"{base}/runs/{run_id}/approval",
            headers=headers,
            json={"choice": choice},
            allow_redirects=False,
        ) as response:
            response_text = await response.text()
            if response.status >= 400:
                error_code = ""
                try:
                    response_data = json.loads(response_text)
                    error_data = (
                        response_data.get("error")
                        if isinstance(response_data, dict)
                        else None
                    )
                    if isinstance(error_data, dict):
                        error_code = str(error_data.get("code") or "")
                except (json.JSONDecodeError, TypeError):
                    pass

                # Hermes owns the canonical approval lifetime. If its shorter
                # deadline expired while Open WebUI still had a dialog open,
                # the run may already have continued and even completed. A
                # stale answer is not a run failure: keep consuming SSE so the
                # real terminal event/output remains visible to the user.
                if response.status == 409 and error_code in {
                    "approval_not_active",
                    "approval_not_pending",
                }:
                    logger.info(
                        "Ignoring stale Open WebUI approval response for run %s (%s)",
                        run_id,
                        error_code,
                    )
                    await self._emit_status(
                        event_emitter,
                        "承認の受付は終了しました。Hermesの処理結果を待ちます",
                        done=True,
                        approval=True,
                    )
                    return

                detail = self._clean_text(response_text, 500)
                raise RuntimeError(
                    f"Hermes approval submission failed ({response.status}): {detail}"
                )

        if choice == "once":
            await self._emit_status(
                event_emitter,
                "操作を1回だけ承認しました",
                done=True,
                approval=True,
            )
        else:
            await self._emit_status(
                event_emitter,
                "操作を拒否しました",
                done=True,
                approval=True,
            )

    @staticmethod
    async def _iter_sse(response: aiohttp.ClientResponse) -> AsyncGenerator[dict, None]:
        buffer = ""
        async for chunk in response.content.iter_any():
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.rstrip("\r").strip()
                if not line or line.startswith(":") or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    logger.debug("Ignoring malformed Hermes SSE payload")
                    continue
                if isinstance(event, dict):
                    yield event
        trailing = buffer.strip()
        if trailing.startswith("data:"):
            try:
                event = json.loads(trailing[5:].strip())
            except json.JSONDecodeError:
                return
            if isinstance(event, dict):
                yield event

    async def _best_effort_stop(
        self, base: str, headers: dict[str, str], run_id: str
    ) -> None:
        timeout = aiohttp.ClientTimeout(total=5, connect=3, sock_read=3)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base}/runs/{run_id}/stop",
                    headers=headers,
                    json={},
                    allow_redirects=False,
                ) as response:
                    await response.read()
        except Exception:
            logger.debug("Best-effort Hermes run stop failed", exc_info=True)

    def _run_client_timeout(self) -> aiohttp.ClientTimeout:
        """Build a timeout that never expires a healthy long-running SSE stream."""
        run_timeout = int(self.valves.RUN_TIMEOUT_SECONDS)
        return aiohttp.ClientTimeout(
            total=run_timeout if run_timeout > 0 else None,
            connect=15,
            sock_connect=15,
            # A model call can legitimately produce no SSE data for many
            # minutes. The total deadline, when explicitly configured, owns
            # run lifetime; an idle socket-read deadline must not do so.
            sock_read=None,
        )

    async def _publish_completion_notification(self, session_id: Any) -> None:
        # This exact shape is created only by _hermes_session_ids() for an
        # interactive Open WebUI chat. Direct/async API runs, cron sessions,
        # live probes, and delegated subagents must not produce this push.
        if not re.fullmatch(r"owui_[0-9a-f]{32}", str(session_id or "")):
            return

        topic = str(self.valves.NTFY_TOPIC or "").strip()
        if not topic:
            return
        if not re.fullmatch(r"[-_A-Za-z0-9]{1,64}", topic):
            logger.warning("Skipping ntfy notification: invalid topic name")
            return

        server = str(self.valves.NTFY_SERVER_URL or "").strip().rstrip("/")
        parsed = urlsplit(server)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            logger.warning("Skipping ntfy notification: invalid server URL")
            return

        headers = {
            "Title": "PDA",
            "Priority": "default",
            "Tags": "white_check_mark,robot_face",
        }
        click_url = str(self.valves.OPENWEBUI_PUBLIC_URL or "").strip()
        if click_url:
            click = urlsplit(click_url)
            if click.scheme == "https" and click.hostname and not click.username and not click.password:
                headers["Click"] = click_url

        timeout = aiohttp.ClientTimeout(total=5, connect=3, sock_read=3)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{server}/{topic}",
                    headers=headers,
                    data="Open WebUIでPDAの応答が完了しました。".encode("utf-8"),
                    allow_redirects=False,
                ) as response:
                    await response.read()
                    if response.status >= 400:
                        logger.warning(
                            "ntfy completion notification failed with HTTP %s",
                            response.status,
                        )
        except Exception:
            # Push is advisory and must never turn a completed chat into an error.
            logger.warning("ntfy completion notification failed", exc_info=True)

    def _schedule_completion_notification(self, session_id: Any) -> None:
        task = asyncio.create_task(
            self._publish_completion_notification(session_id),
            name="openwebui-completion-push",
        )
        self._notification_tasks.add(task)
        task.add_done_callback(self._notification_tasks.discard)

    async def _run_events(
        self,
        *,
        message: str,
        history: list[dict],
        instructions: Optional[str],
        session_id: str,
        session_key: str,
        event_emitter: Optional[Callable[[dict], Awaitable[Any]]],
        event_call: Optional[Callable[[dict], Awaitable[Any]]],
    ) -> AsyncGenerator[dict, None]:
        run_id: Optional[str] = None
        terminal = False
        final_status = "完了"

        try:
            base = self._api_base()
            headers = self._headers(session_key)
            timeout = self._run_client_timeout()
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload: dict[str, Any] = {
                    "input": message,
                    "conversation_history": history,
                    "session_id": session_id,
                    "model": str(self.valves.HERMES_MODEL or "hermes-agent"),
                }
                if instructions:
                    payload["instructions"] = instructions

                async with session.post(
                    f"{base}/runs",
                    headers=headers,
                    json=payload,
                    allow_redirects=False,
                ) as response:
                    body_text = await response.text()
                    if response.status != 202:
                        detail = self._clean_text(body_text, 600)
                        raise RuntimeError(
                            f"Hermes run creation failed ({response.status}): {detail}"
                        )
                    try:
                        created = json.loads(body_text)
                        run_id = str(created["run_id"])
                    except (json.JSONDecodeError, KeyError, TypeError) as exc:
                        raise RuntimeError("Hermes returned an invalid run response") from exc

                await self._emit_status(
                    event_emitter,
                    "Hermesが処理を開始しました…",
                    done=False,
                    run_id=run_id,
                )

                event_headers = dict(headers)
                event_headers["Accept"] = "text/event-stream"
                async with session.get(
                    f"{base}/runs/{run_id}/events",
                    headers=event_headers,
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        detail = self._clean_text(await response.text(), 600)
                        raise RuntimeError(
                            f"Hermes event stream failed ({response.status}): {detail}"
                        )

                    async for event in self._iter_sse(response):
                        event_type = str(event.get("event") or "")

                        if event_type == "tool.started":
                            await self._emit_status(
                                event_emitter,
                                self._tool_description(event, completed=False),
                                done=False,
                                tool=self._clean_text(event.get("tool"), 120),
                                run_id=run_id,
                            )
                        elif event_type == "tool.completed":
                            await self._emit_status(
                                event_emitter,
                                self._tool_description(event, completed=True),
                                done=True,
                                tool=self._clean_text(event.get("tool"), 120),
                                run_id=run_id,
                                error=bool(event.get("error")),
                            )
                        elif (
                            event_type == "reasoning.available"
                            and self.valves.SHOW_REASONING_STATUS
                        ):
                            # Deliberately do not display or persist reasoning text.
                            await self._emit_status(
                                event_emitter,
                                "Hermesが考えています…",
                                done=False,
                                run_id=run_id,
                            )
                        elif event_type == "approval.request":
                            await self._resolve_approval(
                                session=session,
                                base=base,
                                headers=headers,
                                run_id=run_id,
                                event=event,
                                event_emitter=event_emitter,
                                event_call=event_call,
                            )
                        elif event_type == "run.failed":
                            final_status = "失敗"
                            terminal = True
                        elif event_type == "run.cancelled":
                            final_status = "キャンセル済み"
                            terminal = True
                        elif event_type == "run.completed":
                            final_status = "完了"
                            terminal = True

                        yield event
                        if event_type in TERMINAL_EVENTS:
                            return

                raise RuntimeError("Hermes event stream closed without a terminal event")

        except asyncio.CancelledError:
            final_status = "キャンセル済み"
            raise
        except asyncio.TimeoutError:
            final_status = "時間上限で停止"
            timeout_seconds = int(self.valves.RUN_TIMEOUT_SECONDS)
            logger.info(
                "Hermes Progress Pipe reached its configured run deadline (%ss)",
                timeout_seconds,
            )
            yield {
                "event": "adapter.timeout",
                "timeout_seconds": timeout_seconds,
            }
        except Exception as exc:
            final_status = "失敗"
            logger.warning("Hermes Progress Pipe run failed: %s", exc)
            yield {
                "event": "adapter.error",
                "error": self._clean_text(exc, 1000),
            }
        finally:
            if run_id and not terminal:
                try:
                    base = self._api_base()
                    headers = self._headers(session_key)
                    await self._best_effort_stop(base, headers, run_id)
                except Exception:
                    logger.debug("Unable to prepare best-effort run stop", exc_info=True)
            await self._emit_status(
                event_emitter,
                final_status,
                done=True,
                run_id=run_id,
                error=final_status == "失敗",
            )

    @staticmethod
    def _completion_chunk(
        completion_id: str,
        delta: dict,
        finish_reason: Optional[str] = None,
    ) -> str:
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": FUNCTION_ID,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }
            ],
        }
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    async def _stream_response(self, **run_args: Any) -> AsyncGenerator[str, None]:
        completion_id = f"chatcmpl-hermes-{uuid.uuid4().hex[:16]}"
        accumulated = ""
        terminal_output: Optional[str] = None
        terminal_error: Optional[str] = None
        cancelled = False
        timed_out = False

        yield self._completion_chunk(completion_id, {"role": "assistant"})

        async for event in self._run_events(**run_args):
            event_type = str(event.get("event") or "")
            if event_type == "message.delta":
                delta = str(event.get("delta") or "")
                if delta:
                    accumulated += delta
                    yield self._completion_chunk(
                        completion_id, {"content": delta}
                    )
            elif event_type == "run.completed":
                terminal_output = str(event.get("output") or "")
            elif event_type in {"run.failed", "adapter.error"}:
                terminal_error = self._clean_text(
                    event.get("error") or "Hermes run failed", 1000
                )
            elif event_type == "run.cancelled":
                cancelled = True
            elif event_type == "adapter.timeout":
                timed_out = True

        if terminal_output:
            if not accumulated:
                yield self._completion_chunk(
                    completion_id, {"content": terminal_output}
                )
            elif terminal_output.startswith(accumulated):
                suffix = terminal_output[len(accumulated) :]
                if suffix:
                    yield self._completion_chunk(
                        completion_id, {"content": suffix}
                    )
            elif terminal_output.strip() == accumulated.strip():
                # Some providers stream harmless leading/trailing whitespace
                # that is normalized in the final run output.
                pass
            elif terminal_output != accumulated:
                # Deltas are normally byte-identical to output.  On a mismatch,
                # avoid duplicating visible text; log for diagnosis instead.
                logger.warning(
                    "Hermes final output differed from streamed deltas; preserving streamed content"
                )

        if terminal_error:
            separator = "\n\n" if accumulated else ""
            yield self._completion_chunk(
                completion_id,
                {"content": f"{separator}Hermesエラー: {terminal_error}"},
            )
        elif timed_out:
            separator = "\n\n" if accumulated else ""
            yield self._completion_chunk(
                completion_id,
                {
                    "content": (
                        f"{separator}Hermesの実行時間の上限に達したため停止しました。"
                    )
                },
            )
        elif cancelled and not accumulated:
            yield self._completion_chunk(
                completion_id, {"content": "Hermesの実行はキャンセルされました。"}
            )
        elif not accumulated and not terminal_output:
            yield self._completion_chunk(
                completion_id, {"content": "Hermesから応答がありませんでした。"}
            )

        yield self._completion_chunk(completion_id, {}, "stop")
        try:
            yield "data: [DONE]\n\n"
        finally:
            # Open WebUI closes the inner stream as soon as it sees [DONE].
            # Schedule from the generator's close/finalization path, after the
            # consumer has observed completion but without delaying HTTP EOF.
            if terminal_output is not None and terminal_error is None and not cancelled and not timed_out:
                self._schedule_completion_notification(run_args.get("session_id"))

    async def _blocking_response(self, **run_args: Any) -> dict:
        deltas: list[str] = []
        output: Optional[str] = None
        error: Optional[str] = None
        cancelled = False
        timed_out = False

        async for event in self._run_events(**run_args):
            event_type = str(event.get("event") or "")
            if event_type == "message.delta":
                deltas.append(str(event.get("delta") or ""))
            elif event_type == "run.completed":
                output = str(event.get("output") or "")
            elif event_type in {"run.failed", "adapter.error"}:
                error = self._clean_text(
                    event.get("error") or "Hermes run failed", 1000
                )
            elif event_type == "run.cancelled":
                cancelled = True
            elif event_type == "adapter.timeout":
                timed_out = True

        content = output or "".join(deltas)
        if error:
            content = f"Hermesエラー: {error}"
        elif timed_out:
            separator = "\n\n" if content else ""
            content += f"{separator}Hermesの実行時間の上限に達したため停止しました。"
        elif cancelled and not content:
            content = "Hermesの実行はキャンセルされました。"
        elif not content:
            content = "Hermesから応答がありませんでした。"

        return {
            "id": f"chatcmpl-hermes-{uuid.uuid4().hex[:16]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": FUNCTION_ID,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        }
