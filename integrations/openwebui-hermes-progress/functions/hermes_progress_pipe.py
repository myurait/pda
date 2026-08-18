"""
title: Hermes Agent (Progress)
author: Local audited adaptation of Hannah's openwebui-hermes
version: 2.1.0-local.11
required_open_webui_version: 0.10.2
description: Hermes Runs API adapter with model-invisible tool status, per-chat sessions, interactive approvals, fail-safe cleanup, and titled completion push.
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
import importlib
import ipaddress
import json
import logging
import os
import re
import time
import uuid
from typing import Any, AsyncGenerator, Awaitable, Callable, Optional
from urllib.parse import quote, urlsplit, urlunsplit

import aiohttp
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

FUNCTION_ID = "hermes_progress_pipe"
MODEL_NAME = "Hermes Agent (Progress)"
TERMINAL_EVENTS = frozenset({"run.completed", "run.failed", "run.cancelled"})
_SAFE_ROLE = frozenset({"user", "assistant"})
_UNTITLED_CHAT_NAMES = frozenset({"", "New Chat", "新しいチャット"})
_NONINTERACTIVE_REQUEST_PATHS = frozenset(
    {
        "/api/v1/automations/internal",
        "/api/v1/timers/internal",
        "/api/v1/subagents/internal",
    }
)
_NOTIFICATION_TITLE_CHARS = 100
_NOTIFICATION_PREVIEW_CHARS = 240
_SAFE_PROGRESS_TOOL_NAMES = frozenset(
    {
        "browser_back",
        "browser_click",
        "browser_console",
        "browser_get_images",
        "browser_navigate",
        "browser_press",
        "browser_scroll",
        "browser_snapshot",
        "browser_type",
        "browser_vision",
        "cronjob",
        "delegate_task",
        "execute_code",
        "image_generate",
        "memory",
        "patch",
        "process",
        "read_file",
        "search_files",
        "session_search",
        "skill_manage",
        "skill_view",
        "skills_list",
        "terminal",
        "todo",
        "vision_analyze",
        "web_extract",
        "web_search",
        "write_file",
    }
)


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
        PROGRESS_HEARTBEAT_SECONDS: int = Field(
            default=900,
            ge=0,
            le=86400,
            description=(
                "Interval for model-invisible long-run progress status in seconds; "
                "0 disables periodic updates."
            ),
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
        NTFY_ALLOWED_USER_ID: str = Field(
            default="",
            description="Only this authenticated Open WebUI user may emit completion push.",
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
            NTFY_ALLOWED_USER_ID=os.getenv("PDA_NTFY_ALLOWED_USER_ID", ""),
            OPENWEBUI_PUBLIC_URL=os.getenv("PDA_OPENWEBUI_PUBLIC_URL", ""),
        )
        self.user_valves = self.UserValves()
        # asyncio keeps only weak references to tasks. Retain completion-push
        # tasks until delivery finishes so closing the response generator does
        # not silently discard them.
        self._notification_tasks: set[asyncio.Task] = set()
        # Notification delivery is advisory and at-most-once per Open WebUI
        # assistant message for the lifetime of this Function instance.
        self._notified_message_keys: set[str] = set()

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
        __task__: Optional[str] = None,
        __request__: Any = None,
    ) -> Any:
        messages = body.get("messages") or []
        if not messages:
            return {"error": {"detail": "No messages supplied"}}

        authenticated_user_id = str((__user__ or {}).get("id") or "").strip()
        user_id = authenticated_user_id or "unknown-user"
        metadata = __metadata__ or {}
        user_message = metadata.get("user_message")
        user_message_meta = (
            user_message.get("meta") if isinstance(user_message, dict) else None
        )
        request_path = self._request_path(__request__)
        is_internal = bool(
            metadata.get("internal") is True
            or (
                isinstance(user_message_meta, dict)
                and user_message_meta.get("internal") is True
            )
            or request_path in _NONINTERACTIVE_REQUEST_PATHS
        )
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
        task_name = str(__task__ or metadata.get("task") or "").strip()
        user_visible_turn = not is_internal and not task_name

        common = dict(
            message=message,
            history=history,
            instructions=instructions,
            session_id=hermes_session_id,
            session_key=hermes_session_key,
            event_emitter=(__event_emitter__ if user_visible_turn else None),
            event_call=(__event_call__ if user_visible_turn else None),
            chat_id=str(
                __chat_id__ or metadata.get("chat_id") or ""
            ),
            user_id=authenticated_user_id,
            is_internal=is_internal,
            task=task_name,
            message_id=str(__message_id__ or "").strip(),
            host_task=self._current_openwebui_host_task(),
            require_host_task=True,
            ui_context=bool(
                __event_emitter__ is not None
                and __chat_id__
                and __session_id__
                and __message_id__
                and not is_internal
            ),
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
    def _request_path(request: Any) -> str:
        if request is None:
            return ""
        path = str(getattr(getattr(request, "url", None), "path", "") or "")
        if not path:
            scope = getattr(request, "scope", None)
            if isinstance(scope, dict):
                path = str(scope.get("path") or "")
        if path != "/":
            path = path.rstrip("/")
        return path

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

    @staticmethod
    def _validated_notification_url(
        value: Any, *, allow_loopback_http: bool = False
    ) -> Optional[str]:
        supplied = str(value or "")
        if supplied != supplied.strip():
            return None
        raw = supplied.rstrip("/")
        if (
            not raw
            or "\\" in raw
            or "%" in raw
            or any(
                char.isspace() or ord(char) < 33 or ord(char) == 127
                for char in raw
            )
        ):
            return None
        try:
            parsed = urlsplit(raw)
            hostname = parsed.hostname
            port = parsed.port
        except (TypeError, ValueError):
            return None
        if not hostname:
            return None
        try:
            ipaddress.ip_address(hostname)
            valid_hostname = True
        except ValueError:
            try:
                ascii_hostname = hostname.rstrip(".").encode("idna").decode("ascii")
            except UnicodeError:
                return None
            labels = ascii_hostname.split(".")
            valid_hostname = (
                0 < len(ascii_hostname) <= 253
                and all(
                    re.fullmatch(
                        r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",
                        label,
                    )
                    for label in labels
                )
            )
        if not valid_hostname:
            return None
        loopback = hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https" and not (
            allow_loopback_http and parsed.scheme == "http" and loopback
        ):
            return None
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or (port is not None and not 1 <= port <= 65535)
        ):
            return None
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
        )

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

    def _safe_progress_tool_name(self, value: Any) -> str:
        name = self._clean_text(value, 120)
        return name if name in _SAFE_PROGRESS_TOOL_NAMES else "ツール"

    def _tool_description(self, event: dict, *, completed: bool) -> str:
        name = self._safe_progress_tool_name(event.get("tool"))
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

    @staticmethod
    def _initial_progress_state() -> dict[str, Any]:
        return {
            "active_tools": {},
            "completed_tools": 0,
            "last_activity": "処理を開始",
        }

    def _track_progress_event(self, progress: dict[str, Any], event: dict) -> None:
        event_type = str(event.get("event") or "")
        if event_type == "tool.started":
            name = self._safe_progress_tool_name(event.get("tool"))
            active_tools = progress.setdefault("active_tools", {})
            active_tools[name] = int(active_tools.get(name, 0)) + 1
            progress["last_activity"] = f"{name}を開始"
        elif event_type == "tool.completed":
            name = self._safe_progress_tool_name(event.get("tool"))
            active_tools = progress.setdefault("active_tools", {})
            remaining = max(0, int(active_tools.get(name, 0)) - 1)
            if remaining:
                active_tools[name] = remaining
            else:
                active_tools.pop(name, None)
            progress["completed_tools"] = int(progress.get("completed_tools", 0)) + 1
            progress["last_activity"] = (
                f"{name}が失敗" if bool(event.get("error")) else f"{name}が完了"
            )
        elif event_type == "reasoning.available":
            progress["last_activity"] = "Hermesが考えています"
        elif event_type == "message.delta":
            progress["last_activity"] = "回答を生成中"
        elif event_type == "approval.request":
            progress["last_activity"] = "ユーザーの承認待ち"

    @staticmethod
    def _format_elapsed(elapsed_seconds: float) -> str:
        total_seconds = max(1, int(elapsed_seconds))
        if total_seconds < 60:
            return f"{total_seconds}秒"
        total_minutes = total_seconds // 60
        hours, minutes = divmod(total_minutes, 60)
        if hours and minutes:
            return f"{hours}時間{minutes}分"
        if hours:
            return f"{hours}時間"
        return f"{minutes}分"

    def _heartbeat_description(
        self,
        *,
        elapsed_seconds: float,
        progress: dict[str, Any],
    ) -> str:
        elapsed = self._format_elapsed(elapsed_seconds)
        active_tools = progress.get("active_tools") or {}
        active_names = sorted(str(name) for name, count in active_tools.items() if count)
        if active_names:
            current = f"現在: {active_names[0]}を実行中。"
        else:
            current = "処理を継続中。"
            last_activity = self._clean_text(progress.get("last_activity"), 160)
            if last_activity:
                current += f"直近: {last_activity}。"
        completed_tools = int(progress.get("completed_tools", 0))
        if completed_tools:
            current += f"完了したツール: {completed_tools}件。"
        return f"⏳ 開始から{elapsed}。{current}"

    async def _progress_heartbeat(
        self,
        *,
        emitter: Optional[Callable[[dict], Awaitable[Any]]],
        run_id: str,
        started_at: float,
        interval_seconds: float,
        progress: dict[str, Any],
        stop_event: asyncio.Event,
    ) -> None:
        if emitter is None or interval_seconds <= 0:
            return
        loop = asyncio.get_running_loop()
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=interval_seconds,
                )
                return
            except asyncio.TimeoutError:
                pass
            if stop_event.is_set():
                return
            elapsed_seconds = max(0.0, loop.time() - started_at)
            await self._emit_status(
                emitter,
                self._heartbeat_description(
                    elapsed_seconds=elapsed_seconds,
                    progress=progress,
                ),
                done=False,
                heartbeat=True,
                elapsed_seconds=int(elapsed_seconds),
                completed_tools=int(progress.get("completed_tools", 0)),
                run_id=run_id,
            )

    @staticmethod
    async def _stop_progress_heartbeat(
        task: Optional[asyncio.Task], stop_event: asyncio.Event
    ) -> None:
        stop_event.set()
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug("Progress heartbeat task failed during shutdown", exc_info=True)

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

    @classmethod
    def _saved_assistant_text(cls, message: Any) -> str:
        if not isinstance(message, dict):
            return ""
        direct = cls._extract_text(message.get("content"))
        if direct:
            return direct

        parts: list[str] = []

        def visit(value: Any) -> None:
            if isinstance(value, str):
                if value:
                    parts.append(value)
                return
            if isinstance(value, list):
                for item in value:
                    visit(item)
                return
            if not isinstance(value, dict):
                return
            item_type = str(value.get("type") or "").lower()
            # Never include reasoning or tool traces in notification previews.
            if item_type in {"reasoning", "tool", "tool_call", "tool_result"}:
                return
            if item_type in {"output_text", "text"}:
                visit(value.get("text"))
                return
            if item_type == "message":
                visit(value.get("content"))

        visit(message.get("output"))
        return "".join(parts).strip()

    async def _load_openwebui_completion(
        self, chat_id: str, message_id: str, user_id: str
    ) -> Optional[tuple[str, bool, str]]:
        try:
            chats_module = importlib.import_module("open_webui.models.chats")
            chat = await chats_module.Chats.get_chat_by_id_and_user_id(
                chat_id, user_id
            )
            if chat is None:
                return None
            message = await chats_module.Chats.get_message_by_id_and_message_id(
                chat_id, message_id
            )
        except Exception:
            logger.warning("Could not load owned Open WebUI completion", exc_info=True)
            return None
        if not isinstance(message, dict) or message.get("role") != "assistant":
            return None
        title = self._clean_text(
            getattr(chat, "title", ""), _NOTIFICATION_TITLE_CHARS
        ) or "New Chat"
        return title, message.get("done") is True, self._saved_assistant_text(message)

    async def _await_openwebui_completion(
        self, chat_id: str, message_id: str, user_id: str
    ) -> Optional[tuple[str, str]]:
        last_ready: Optional[tuple[str, str]] = None
        for attempt in range(80):
            loaded = await self._load_openwebui_completion(
                chat_id, message_id, user_id
            )
            if loaded is None:
                return None
            title, done, answer = loaded
            if done:
                last_ready = (title, answer)
                if title not in _UNTITLED_CHAT_NAMES:
                    return last_ready
            if attempt < 79:
                await asyncio.sleep(0.25)
        return last_ready

    async def _publish_completion_notification(
        self,
        session_id: Any,
        *,
        chat_id: Any = "",
        user_id: Any = "",
        is_internal: bool = False,
        task: Any = "",
        message_id: Any = "",
        host_task: Optional[asyncio.Task] = None,
    ) -> None:
        if is_internal or str(task or "").strip():
            return
        allowed_user_id = str(self.valves.NTFY_ALLOWED_USER_ID or "").strip()
        authenticated_user_id = str(user_id or "").strip()
        if not allowed_user_id or authenticated_user_id != allowed_user_id:
            return
        # This exact shape is created only by _hermes_session_ids() for an
        # interactive Open WebUI chat. Direct/async API runs, cron sessions,
        # live probes, and delegated subagents must not produce this push.
        if not re.fullmatch(r"owui_[0-9a-f]{32}", str(session_id or "")):
            return

        chat_id_text = str(chat_id or "").strip()
        if not re.fullmatch(r"[-_:A-Za-z0-9]{1,256}", chat_id_text):
            return

        click_url = self._validated_notification_url(
            self.valves.OPENWEBUI_PUBLIC_URL
        )
        if click_url is None:
            return
        click_target = f"{click_url}/c/{quote(chat_id_text, safe='')}"

        topic = str(self.valves.NTFY_TOPIC or "").strip()
        if not topic:
            return
        if not re.fullmatch(r"[-_A-Za-z0-9]{1,64}", topic):
            logger.warning("Skipping ntfy notification: invalid topic name")
            return

        server = self._validated_notification_url(
            self.valves.NTFY_SERVER_URL,
            allow_loopback_http=True,
        )
        if server is None:
            logger.warning("Skipping ntfy notification: invalid server URL")
            return

        message_id_text = str(message_id or "").strip()
        if not re.fullmatch(r"[-_:A-Za-z0-9]{1,256}", message_id_text):
            return
        if host_task is not None:
            try:
                await asyncio.shield(host_task)
            except asyncio.CancelledError:
                # The host request may finish by cancellation after Open WebUI
                # has already persisted a non-empty done response.  In that case
                # the database record, not the task outcome, is authoritative.
                # Preserve cancellation only when this notification task itself
                # was cancelled while the host task remains active.
                if not host_task.cancelled():
                    raise
                logger.debug(
                    "Open WebUI host task was cancelled; checking persisted completion"
                )
            except Exception:
                # A failed outlet/host task can still leave the user-visible
                # assistant response persisted as done.  Check that record and
                # send only its sanitized content if present.
                logger.warning(
                    "Open WebUI host task failed; checking persisted completion",
                    exc_info=True,
                )
        persisted = await self._await_openwebui_completion(
            chat_id_text,
            message_id_text,
            authenticated_user_id,
        )
        if persisted is None:
            return
        title, persisted_answer = persisted
        preview = self._clean_text(
            persisted_answer, _NOTIFICATION_PREVIEW_CHARS
        )
        if not preview:
            return

        headers = {
            "Title": title,
            "Priority": "default",
            "Click": click_target,
        }

        timeout = aiohttp.ClientTimeout(total=5, connect=3, sock_read=3)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{server}/{topic}",
                    headers=headers,
                    data=preview.encode("utf-8"),
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

    def _schedule_completion_notification(
        self,
        session_id: Any,
        *,
        chat_id: Any = "",
        user_id: Any = "",
        is_internal: bool = False,
        task: Any = "",
        message_id: Any = "",
        host_task: Optional[asyncio.Task] = None,
        require_host_task: bool = False,
        ui_context: bool = True,
    ) -> None:
        if is_internal or str(task or "").strip() or not ui_context:
            return
        message_id_text = str(message_id or "").strip()
        if not re.fullmatch(r"[-_:A-Za-z0-9]{1,256}", message_id_text):
            return
        if require_host_task and not isinstance(host_task, asyncio.Task):
            logger.warning(
                "Skipping completion push because the Open WebUI host task was unavailable"
            )
            return
        notification_key = f"{user_id}:{chat_id}:{message_id_text}"
        if notification_key in self._notified_message_keys:
            return
        self._notified_message_keys.add(notification_key)
        notification_task = asyncio.create_task(
            self._publish_completion_notification(
                session_id,
                chat_id=chat_id,
                user_id=user_id,
                is_internal=is_internal,
                task=task,
                message_id=message_id_text,
                host_task=host_task,
            ),
            name="openwebui-completion-push",
        )
        self._notification_tasks.add(notification_task)
        notification_task.add_done_callback(self._notification_tasks.discard)

    @staticmethod
    def _current_openwebui_host_task() -> Optional[asyncio.Task]:
        try:
            return asyncio.current_task()
        except RuntimeError:
            return None

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
        progress = self._initial_progress_state()
        heartbeat_stop = asyncio.Event()
        heartbeat_task: Optional[asyncio.Task] = None
        status_emitter = event_emitter
        if event_emitter is not None:
            raw_status_emitter = event_emitter
            status_emitter_lock = asyncio.Lock()

            async def emit_status_serially(event: dict) -> Any:
                async with status_emitter_lock:
                    return await raw_status_emitter(event)

            status_emitter = emit_status_serially

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

                heartbeat_started_at = asyncio.get_running_loop().time()
                await self._emit_status(
                    status_emitter,
                    "Hermesが処理を開始しました…",
                    done=False,
                    run_id=run_id,
                )
                heartbeat_interval = int(self.valves.PROGRESS_HEARTBEAT_SECONDS)
                if status_emitter is not None and heartbeat_interval > 0:
                    heartbeat_task = asyncio.create_task(
                        self._progress_heartbeat(
                            emitter=status_emitter,
                            run_id=run_id,
                            started_at=heartbeat_started_at,
                            interval_seconds=heartbeat_interval,
                            progress=progress,
                            stop_event=heartbeat_stop,
                        ),
                        name=f"hermes-progress-heartbeat-{run_id}",
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
                        self._track_progress_event(progress, event)

                        if event_type == "tool.started":
                            await self._emit_status(
                                status_emitter,
                                self._tool_description(event, completed=False),
                                done=False,
                                tool=self._safe_progress_tool_name(event.get("tool")),
                                run_id=run_id,
                            )
                        elif event_type == "tool.completed":
                            await self._emit_status(
                                status_emitter,
                                self._tool_description(event, completed=True),
                                done=True,
                                tool=self._safe_progress_tool_name(event.get("tool")),
                                run_id=run_id,
                                error=bool(event.get("error")),
                            )
                        elif (
                            event_type == "reasoning.available"
                            and self.valves.SHOW_REASONING_STATUS
                        ):
                            # Deliberately do not display or persist reasoning text.
                            await self._emit_status(
                                status_emitter,
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
                                event_emitter=status_emitter,
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

                        if event_type in TERMINAL_EVENTS:
                            await self._stop_progress_heartbeat(
                                heartbeat_task, heartbeat_stop
                            )
                            heartbeat_task = None
                            yield event
                            return
                        yield event

                raise RuntimeError("Hermes event stream closed without a terminal event")

        except asyncio.CancelledError:
            final_status = "キャンセル済み"
            raise
        except GeneratorExit:
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
            await self._stop_progress_heartbeat(heartbeat_task, heartbeat_stop)
            if run_id and not terminal:
                try:
                    base = self._api_base()
                    headers = self._headers(session_key)
                    await self._best_effort_stop(base, headers, run_id)
                except Exception:
                    logger.debug("Unable to prepare best-effort run stop", exc_info=True)
            await self._emit_status(
                status_emitter,
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
        chunk_stream = self._stream_response_chunks(**run_args)
        try:
            async for chunk in chunk_stream:
                yield chunk
        finally:
            try:
                # Explicitly close the inner generator so its Hermes event
                # stream and heartbeat finish before this wrapper returns.
                await chunk_stream.aclose()
            finally:
                # Cover every consumer close point: during Hermes events, after
                # final content, after the stop chunk, and after [DONE]. The
                # publisher still requires a persisted, owned, non-empty done
                # message before exporting it.
                self._schedule_completion_notification(
                    run_args.get("session_id"),
                    chat_id=run_args.get("chat_id", ""),
                    user_id=run_args.get("user_id", ""),
                    is_internal=bool(run_args.get("is_internal", False)),
                    task=run_args.get("task", ""),
                    message_id=run_args.get("message_id", ""),
                    host_task=run_args.get("host_task"),
                    require_host_task=bool(
                        run_args.get("require_host_task", False)
                    ),
                    ui_context=bool(run_args.get("ui_context", False)),
                )

    async def _stream_response_chunks(
        self, **run_args: Any
    ) -> AsyncGenerator[str, None]:
        chat_id = run_args.pop("chat_id", "")
        user_id = run_args.pop("user_id", "")
        is_internal = bool(run_args.pop("is_internal", False))
        task = run_args.pop("task", "")
        message_id = run_args.pop("message_id", "")
        host_task = run_args.pop("host_task", None)
        require_host_task = bool(run_args.pop("require_host_task", False))
        ui_context = bool(run_args.pop("ui_context", False))
        completion_id = f"chatcmpl-hermes-{uuid.uuid4().hex[:16]}"
        accumulated = ""
        terminal_output: Optional[str] = None
        terminal_error: Optional[str] = None
        cancelled = False
        timed_out = False

        yield self._completion_chunk(completion_id, {"role": "assistant"})

        event_stream = self._run_events(**run_args)
        event_stream_finished = False
        try:
            async for event in event_stream:
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
            event_stream_finished = True
        finally:
            if not event_stream_finished:
                try:
                    await event_stream.aclose()
                finally:
                    # Open WebUI can persist a partial response before closing
                    # the stream. Arrange the same DB-backed completion check as
                    # terminal outcomes without leaving the run heartbeat alive.
                    self._schedule_completion_notification(
                        run_args.get("session_id"),
                        chat_id=chat_id,
                        user_id=user_id,
                        is_internal=is_internal,
                        task=task,
                        message_id=message_id,
                        host_task=host_task,
                        require_host_task=require_host_task,
                        ui_context=ui_context,
                    )

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
        yield "data: [DONE]\n\n"

    async def _blocking_response(self, **run_args: Any) -> dict:
        chat_id = run_args.pop("chat_id", "")
        user_id = run_args.pop("user_id", "")
        is_internal = bool(run_args.pop("is_internal", False))
        task = run_args.pop("task", "")
        message_id = run_args.pop("message_id", "")
        host_task = run_args.pop("host_task", None)
        require_host_task = bool(run_args.pop("require_host_task", False))
        ui_context = bool(run_args.pop("ui_context", False))
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

        self._schedule_completion_notification(
            run_args.get("session_id"),
            chat_id=chat_id,
            user_id=user_id,
            is_internal=is_internal,
            task=task,
            message_id=message_id,
            host_task=host_task,
            require_host_task=require_host_task,
            ui_context=ui_context,
        )

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
