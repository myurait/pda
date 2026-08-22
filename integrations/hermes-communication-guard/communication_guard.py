"""Deterministic runtime guard for PDA owner communication."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

IntentKind = Literal["normal", "status", "stop"]

_STATUS_PATTERNS = (
    re.compile(r"(?:今|現在|現時点).{0,12}(?:状況|状態|進捗|現在地).{0,12}(?:報告|教え|示し)"),
    re.compile(r"(?:状況|状態|進捗|現在地).{0,12}(?:報告|教え|示し)(?:て|なさい|ください|くれ)"),
    re.compile(r"どうなって(?:い)?る"),
)
_STATUS_DEFERRED = re.compile(
    r"(?:完了したら|完了後|終了後|終わったら|終わった後|後で|最後に).{0,24}報告"
)
_STOP_PATTERN = re.compile(
    r"(?:作業|処理|実行|調査)?を?(?:停止|中止|中断|キャンセル)(?:して|しろ|してください|せよ|する)"
    r"|(?:作業|処理|実行|調査)?を?(?:止めて|やめて)(?:ください)?"
    r"|^(?:stop|pause|cancel)(?:\s+(?:now|work|it))?[.!]?\s*$",
    re.IGNORECASE,
)
_STOP_NEGATION = re.compile(r"(?:停止|中止|中断|キャンセル)しない|(?:止め|やめ)ない")

_STATUS_CONTEXT = (
    "これは直接の状況報告要求です。新しいツールを実行せず、すでに確認済みの事実だけで"
    "次の応答を返してください。未確認事項は未確認と明示し、結論、影響、リスク、"
    "ユーザーに必要な対応を簡潔な敬語で示してください。"
)
_STATUS_BLOCK_MESSAGE = "状況報告を先に返すため、新しいツール実行を遮断しました。"
_STOP_CONTEXT = (
    "これは直接の停止指示です。新しい作業を始めず、停止専用操作以外を実行しないでください。"
    "安全に停止できる対象だけを停止した後、停止済み、停止不能、未着手を区別し、すでに確認済みの"
    "事実だけを簡潔な敬語で報告してください。"
)
_STOP_BLOCK_MESSAGE = "停止指示を優先するため、停止専用操作以外を遮断しました。"

_PROTECTED_MARKDOWN = re.compile(r"(```.*?```|`[^`\n]*`|https?://\S+)", re.DOTALL)
_REPORT_PREFIX = re.compile(r"^(?:完了報告|進捗報告|状況報告|判断依頼|承認依頼|障害報告|提案)")
_APPROVAL_PREFIX = re.compile(r"^承認依頼")
_APPROVAL_FIELDS = (
    ("approval_subject", "承認対象", re.compile(r"承認対象\s*[:：]")),
    ("purpose", "目的・成果", re.compile(r"目的(?:・成果)?\s*[:：]|得られる成果\s*[:：]")),
    (
        "changes_after_approval",
        "承認後の変化",
        re.compile(r"承認後(?:の変化|に変わること)\s*[:：]"),
    ),
    (
        "risk_and_reversibility",
        "主要リスクと可逆性",
        re.compile(r"(?:主要)?リスク(?:と|・).*可逆性\s*[:：]"),
    ),
    ("recommendation", "推奨", re.compile(r"推奨\s*[:：]")),
    ("action", "必要な操作", re.compile(r"必要な操作\s*[:：]")),
)
_REPORT_CUES = {
    "conclusion": re.compile(r"結論|結果|現状|進捗|推奨|障害"),
    "impact": re.compile(r"影響|可能にな|変わり|意味|結果として"),
    "risk": re.compile(r"リスク|残存|制約|未確認|不明|懸念|注意"),
    "action": re.compile(r"必要な対応|お願い|判断|操作|承認|対応は不要|必要ありません"),
}
_MISSING_FIELD_TEXT = "元の応答では明示されていません。"
_VOCABULARY = {
    "commit": "コミット",
    "push": "プッシュ",
    "plugin": "プラグイン",
    "hook": "フック",
    "worktree": "作業ツリー",
    "runtime": "実行環境",
    "rollback": "ロールバック",
    "dashboard": "ダッシュボード",
    "core": "本体",
    "stage": "準備段階",
}
_ACTION_VERB_RE = re.compile(
    r"(?:押(?:し|して)|選択(?:し|して)|入力(?:し|して)|確認(?:し|して)|"
    r"開(?:い|いて|く)|実行(?:し|して)|送信(?:し|して)|返信(?:し|して)|"
    r"再読込(?:し|して)|承認(?:し|して)|差し戻(?:し|して)|依頼(?:し|して))"
)
_WORKER_DETAIL_PATTERNS = (
    re.compile(r"`"),
    re.compile(
        r"\b(?:branch|worktree|sha|head|commit|diff|pytest|ruff|git|systemctl|docker|"
        r"command|path|changed[_ -]?files?|merge|hash|digest|checksum)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:^|\s)/(?:home|Users|tmp|etc|var|opt|srv)/"),
    re.compile(r"\b[A-Za-z]:[\\/][^\s]+"),
    re.compile(r"(?<!\w)(?:\.{1,2}[\\/])?[A-Za-z0-9_.-]+[\\/][A-Za-z0-9_./\\-]+"),
    re.compile(r"\b[0-9a-f]{6,64}\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,10}\b"),
    re.compile(
        r"ブランチ|ワークツリー|作業ツリー|コミット|差分|実行コマンド|設定値|"
        r"変更ファイル|テスト(?:手順|件数)|\d+\s*件(?:の)?テスト|実装順序|"
        r"(?:ファイル|絶対)?パス(?:[:：]|$|\s|を|へ|が|の)"
    ),
)


@dataclass(frozen=True)
class TurnIntent:
    kind: IntentKind
    session_id: str
    turn_id: str


@dataclass(frozen=True)
class GuardResult:
    text: str
    violations: tuple[str, ...]


class AuditStore:
    """Persist data-minimized audit evidence without prompt or response bodies."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record(
        self,
        *,
        session_id: str,
        turn_id: str,
        event_type: str,
        intent: IntentKind,
        outcome: str,
        violations: tuple[str, ...],
        response_hash: str,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        now = int(time.time())
        with sqlite3.connect(self.path, timeout=3) as connection:
            connection.execute("PRAGMA busy_timeout = 3000")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at INTEGER NOT NULL,
                    session_hash TEXT NOT NULL,
                    turn_hash TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    violations TEXT NOT NULL,
                    response_hash TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "DELETE FROM audit_events WHERE created_at < ?",
                (now - 30 * 24 * 60 * 60,),
            )
            connection.execute(
                """
                INSERT INTO audit_events (
                    created_at, session_hash, turn_hash, event_type, intent,
                    outcome, violations, response_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    _hash_text(session_id),
                    _hash_text(turn_id),
                    event_type,
                    intent,
                    outcome,
                    json.dumps(violations, ensure_ascii=False, separators=(",", ":")),
                    response_hash,
                ),
            )
            connection.commit()


def classify_request(message: str) -> IntentKind:
    """Classify only high-confidence direct preemption requests."""

    normalized = " ".join(str(message or "").strip().split())
    if not normalized or _STATUS_DEFERRED.search(normalized):
        return "normal"
    if not _STOP_NEGATION.search(normalized) and _STOP_PATTERN.search(normalized):
        return "stop"
    if any(pattern.search(normalized) for pattern in _STATUS_PATTERNS):
        return "status"
    return "normal"


class CommunicationGuardRuntime:
    """Bind one owner-message intent to its turn and enforce it at tool dispatch."""

    def __init__(self, audit_path: str | Path) -> None:
        self.audit_path = Path(audit_path)
        self.audit = AuditStore(self.audit_path)
        self._intents: dict[tuple[str, str], TurnIntent] = {}
        self._lock = threading.RLock()
        self._current_intent: ContextVar[TurnIntent | None] = ContextVar(
            f"pda_communication_intent_{id(self)}",
            default=None,
        )

    def pre_llm_call(self, **kwargs: Any) -> dict[str, str] | None:
        session_id = str(kwargs.get("session_id") or "")
        turn_id = str(kwargs.get("turn_id") or "")
        kind = classify_request(str(kwargs.get("user_message") or ""))
        intent = TurnIntent(
            kind=kind,
            session_id=session_id,
            turn_id=turn_id,
        )
        self._current_intent.set(intent)
        if session_id and turn_id:
            with self._lock:
                self._intents[(session_id, turn_id)] = intent
        if kind == "status":
            return {"context": _STATUS_CONTEXT}
        if kind == "stop":
            return {"context": _STOP_CONTEXT}
        return None

    def pre_tool_call(self, **kwargs: Any) -> dict[str, str] | None:
        key = (str(kwargs.get("session_id") or ""), str(kwargs.get("turn_id") or ""))
        with self._lock:
            intent = self._intents.get(key)
        if intent is not None and intent.kind == "status":
            self._audit_tool_block(intent, str(kwargs.get("tool_name") or ""))
            return {"action": "block", "message": _STATUS_BLOCK_MESSAGE}
        if intent is not None and intent.kind == "stop":
            if _is_cancellation_tool(
                str(kwargs.get("tool_name") or ""),
                kwargs.get("args"),
            ):
                return None
            self._audit_tool_block(intent, str(kwargs.get("tool_name") or ""))
            return {"action": "block", "message": _STOP_BLOCK_MESSAGE}
        return None

    def _audit_tool_block(self, intent: TurnIntent, tool_name: str) -> None:
        try:
            self.audit.record(
                session_id=intent.session_id,
                turn_id=intent.turn_id,
                event_type="tool_blocked",
                intent=intent.kind,
                outcome="blocked",
                violations=(f"{intent.kind}_preemption",),
                response_hash=_hash_text(tool_name),
            )
        except (OSError, sqlite3.Error):
            pass

    def transform_llm_output(self, **kwargs: Any) -> str | None:
        response = str(kwargs.get("response_text") or "")
        session_id = str(kwargs.get("session_id") or "")
        current_intent = self._current_intent.get()
        intent = (
            current_intent
            if current_intent is not None and current_intent.session_id == session_id
            else None
        )
        if intent is current_intent:
            self._current_intent.set(None)
        if intent is None and session_id:
            with self._lock:
                candidates = [
                    candidate
                    for (candidate_session, _turn_id), candidate in self._intents.items()
                    if candidate_session == session_id
                ]
            if len(candidates) == 1:
                intent = candidates[0]
        kind: IntentKind = intent.kind if intent is not None else "normal"
        result = guard_response(response, kind)
        try:
            self.audit.record(
                session_id=session_id,
                turn_id=intent.turn_id if intent is not None else "",
                event_type="response_checked",
                intent=kind,
                outcome="modified" if result.text != response else "passed",
                violations=result.violations,
                response_hash=_hash_text(response),
            )
        except (OSError, sqlite3.Error):
            pass
        return result.text if result.text != response else None

    def post_llm_call(self, **kwargs: Any) -> None:
        key = (str(kwargs.get("session_id") or ""), str(kwargs.get("turn_id") or ""))
        with self._lock:
            self._intents.pop(key, None)

    def on_session_end(self, **kwargs: Any) -> None:
        session_id = str(kwargs.get("session_id") or "")
        with self._lock:
            stale = [key for key in self._intents if key[0] == session_id]
            for key in stale:
                self._intents.pop(key, None)
        self._current_intent.set(None)


def _is_cancellation_tool(tool_name: str, raw_args: Any) -> bool:
    args = raw_args if isinstance(raw_args, dict) else {}
    action = str(args.get("action") or "")
    return (tool_name == "process" and action in {"kill", "close"}) or (
        tool_name == "delegate_task" and action == "stop"
    )


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def guard_response(response: str, intent: IntentKind) -> GuardResult:
    """Normalize high-confidence style defects and expose report omissions."""

    violations: list[str] = []
    normalized = _transform_markdown_prose(response, violations)
    if _APPROVAL_PREFIX.search(normalized):
        return _guard_approval_request(normalized, violations)
    report_like = intent in {"status", "stop"} or bool(_REPORT_PREFIX.search(normalized))
    if not report_like:
        return GuardResult(normalized, tuple(dict.fromkeys(violations)))

    missing = [name for name, pattern in _REPORT_CUES.items() if not pattern.search(normalized)]
    if "conclusion" in missing:
        normalized = f"結論: {normalized.strip()}"
        violations.append("missing_conclusion")
    additions: list[str] = []
    for name, label in (
        ("impact", "影響"),
        ("risk", "リスク"),
        ("action", "必要な対応"),
    ):
        if name in missing:
            additions.append(f"{label}: {_MISSING_FIELD_TEXT}")
            violations.append(f"missing_{name}")
    if additions:
        normalized = normalized.rstrip() + "\n\n" + "\n".join(additions)
    return GuardResult(normalized, tuple(dict.fromkeys(violations)))


def _guard_approval_request(text: str, violations: list[str]) -> GuardResult:
    safe_lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            violations.append("worker_detail_removed")
            if line.count("```") < 2:
                in_fence = not in_fence
            continue
        if in_fence:
            violations.append("worker_detail_removed")
            continue
        if re.match(r"\s*必要な操作\s*[:：]", line):
            action = re.split(r"[:：]", line, maxsplit=1)[-1].strip()
            if not _is_single_owner_action(action):
                violations.append("multiple_approval_actions_removed")
                continue
        if any(pattern.search(line) for pattern in _WORKER_DETAIL_PATTERNS):
            violations.append("worker_detail_removed")
            if line.strip().startswith("承認依頼"):
                safe_lines.append("承認依頼です。")
            continue
        safe_lines.append(line)
    safe = "\n".join(safe_lines).strip() or "承認依頼です。"
    additions: list[str] = []
    for key, label, pattern in _APPROVAL_FIELDS:
        if pattern.search(safe) is None:
            additions.append(f"{label}: {_MISSING_FIELD_TEXT}")
            violations.append(f"missing_approval_{key}")
    if additions:
        safe = safe.rstrip() + "\n\n" + "\n".join(additions)
    return GuardResult(safe, tuple(dict.fromkeys(violations)))


def _is_single_owner_action(action: str) -> bool:
    return (
        action.count("してください") == 1
        and len(_ACTION_VERB_RE.findall(action)) == 1
        and re.search(
            r"、|してから|した後|次に|その後|あわせて|加えて|さらに|"
            r"および|ならびに|または|もしくは|あるいは",
            action,
        )
        is None
    )


def _transform_markdown_prose(text: str, violations: list[str]) -> str:
    parts = _PROTECTED_MARKDOWN.split(text)
    for index in range(0, len(parts), 2):
        original = parts[index]
        transformed = _normalize_vocabulary(original)
        if transformed != original:
            violations.append("raw_english_vocabulary")
        polite = _normalize_politeness(transformed)
        if polite != transformed:
            violations.append("plain_japanese_style")
        parts[index] = polite
    return "".join(parts)


def _normalize_vocabulary(text: str) -> str:
    for source, replacement in _VOCABULARY.items():
        text = re.sub(
            rf"(?<![A-Za-z0-9_/.\-]){re.escape(source)}(?![A-Za-z0-9_/.\-])",
            replacement,
            text,
            flags=re.IGNORECASE,
        )
    return text


def _normalize_politeness(text: str) -> str:
    action_nouns = "完了|確認|実装|変更|追加|削除|検証|停止|中止|再開|失敗|成功|記録|反映|調査"
    text = re.sub(rf"({action_nouns})した([。！？!?])", r"\1しました\2", text)
    text = re.sub(r"である([。！？!?])", r"です\1", text)
    text = re.sub(r"(?:必要|不要|問題)だ([。！？!?])", lambda match: {
        "必要だ": "必要です",
        "不要だ": "不要です",
        "問題だ": "問題です",
    }[match.group(0)[:-1]] + match.group(1), text)
    return text
