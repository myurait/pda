from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from communication_guard import CommunicationGuardRuntime, guard_response


def _owner_message() -> dict[str, str]:
    return {
        "approval_subject": "検証済みのコミュニケーション改善を通常のPDAへ反映することです",
        "purpose": "承認判断に必要な成果とリスクだけを確認できるようにするためです",
        "changes_after_approval": "承認要求と承認一覧が簡潔な判断情報へ統一されます",
        "risk_and_reversibility": "表現の誤検出は残りますが、機能を無効化して元へ戻せます",
        "recommendation": "最終反映の承認を推奨します",
        "action": "承認一覧で「最終反映を承認」を一度押してください",
    }


def _owner_review_summary() -> str:
    message = _owner_message()
    return (
        "承認依頼です。\n"
        f"承認対象: {message['approval_subject']}\n"
        f"目的・成果: {message['purpose']}\n"
        f"承認後の変化: {message['changes_after_approval']}\n"
        f"主要リスクと可逆性: {message['risk_and_reversibility']}\n"
        f"推奨: {message['recommendation']}\n"
        f"必要な操作: {message['action']}"
    )


def test_status_request_blocks_new_tools_and_injects_immediate_report_policy(
    tmp_path: Path,
) -> None:
    runtime = CommunicationGuardRuntime(tmp_path / "audit.db")

    context = runtime.pre_llm_call(
        session_id="session-status",
        turn_id="turn-status",
        user_message="今の進捗を報告してください",
    )
    blocked = runtime.pre_tool_call(
        session_id="session-status",
        turn_id="turn-status",
        tool_name="web_search",
        args={"query": "追加調査"},
    )

    assert context is not None
    assert "新しいツールを実行せず" in context["context"]
    assert blocked == {
        "action": "block",
        "message": "状況報告を先に返すため、新しいツール実行を遮断しました。",
    }


def test_stop_request_allows_cancellation_but_blocks_new_work(tmp_path: Path) -> None:
    runtime = CommunicationGuardRuntime(tmp_path / "audit.db")
    common = {
        "session_id": "session-stop",
        "turn_id": "turn-stop",
    }

    context = runtime.pre_llm_call(**common, user_message="作業を停止してください")
    cancellation = runtime.pre_tool_call(
        **common,
        tool_name="process",
        args={"action": "kill", "session_id": "proc-1"},
    )
    new_work = runtime.pre_tool_call(
        **common,
        tool_name="read_file",
        args={"path": "/tmp/new-investigation"},
    )

    assert context is not None
    assert "停止専用操作以外" in context["context"]
    assert cancellation is None
    assert new_work == {
        "action": "block",
        "message": "停止指示を優先するため、停止専用操作以外を遮断しました。",
    }


def test_future_report_instruction_does_not_preempt_current_work(tmp_path: Path) -> None:
    runtime = CommunicationGuardRuntime(tmp_path / "audit.db")
    common = {
        "session_id": "session-future",
        "turn_id": "turn-future",
    }

    context = runtime.pre_llm_call(
        **common,
        user_message="実装を続け、完了後に現在の進捗を報告してください",
    )
    tool_decision = runtime.pre_tool_call(
        **common,
        tool_name="read_file",
        args={"path": "/tmp/relevant"},
    )

    assert context is None
    assert tool_decision is None


def test_status_response_is_normalized_and_missing_governance_fields_are_explicit(
    tmp_path: Path,
) -> None:
    runtime = CommunicationGuardRuntime(tmp_path / "audit.db")
    runtime.pre_llm_call(
        session_id="session-transform",
        turn_id="turn-transform",
        user_message="今の状況を報告してください",
    )

    transformed = runtime.transform_llm_output(
        session_id="session-transform",
        response_text="調査は完了した。pluginを追加した。",
        model="test-model",
        platform="cli",
    )

    assert transformed == (
        "結論: 調査は完了しました。プラグインを追加しました。\n\n"
        "影響: 元の応答では明示されていません。\n"
        "リスク: 元の応答では明示されていません。\n"
        "必要な対応: 元の応答では明示されていません。"
    )


def test_approval_request_removes_worker_details_and_exposes_every_required_element(
    tmp_path: Path,
) -> None:
    runtime = CommunicationGuardRuntime(tmp_path / "audit.db")
    runtime.pre_llm_call(
        session_id="session-approval",
        turn_id="turn-approval",
        user_message="最終反映の承認依頼を作成してください",
    )

    transformed = runtime.transform_llm_output(
        session_id="session-approval",
        response_text=(
            "承認依頼です。branch pda-auto/example の SHA abcdef123456 をmainへmergeします。\n"
            "pytest 42件成功。変更ファイルはguard.pyです。承認してください。\n"
            "worktreeとcommitを更新します。\n"
            "```text\nSECRET_WORKER_DETAIL\n```"
        ),
    )

    assert transformed is not None
    for label in (
        "承認対象:",
        "目的・成果:",
        "承認後の変化:",
        "主要リスクと可逆性:",
        "推奨:",
        "必要な操作:",
    ):
        assert label in transformed
    for worker_detail in (
        "branch",
        "pda-auto",
        "SHA",
        "abcdef123456",
        "pytest",
        "42件",
        "guard.py",
        "変更ファイル",
        "作業ツリー",
        "コミット",
        "SECRET_WORKER_DETAIL",
    ):
        assert worker_detail not in transformed


def test_good_approval_request_passes_without_extra_detail_or_rewrite() -> None:
    response = (
        "承認依頼です。\n"
        "承認対象: 検証済みのコミュニケーション改善を通常のPDAへ反映することです。\n"
        "目的・成果: 承認判断に必要な成果とリスクだけを確認できるようになります。\n"
        "承認後の変化: 承認要求と承認一覧が簡潔な判断情報へ統一されます。\n"
        "主要リスクと可逆性: 表現の誤検出は残りますが、機能を無効化して元へ戻せます。\n"
        "推奨: 最終反映の承認を推奨します。\n"
        "必要な操作: 承認一覧で「最終反映を承認」を一度押してください。"
    )

    result = guard_response(response, "normal")

    assert result.text == response
    assert result.violations == ()


def test_audit_database_records_only_hashes_and_violation_codes(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.db"
    runtime = CommunicationGuardRuntime(audit_path)
    runtime.pre_llm_call(
        session_id="private-session-id",
        turn_id="private-turn-id",
        user_message="今の進捗を報告してください USER_PRIVATE_TEXT",
    )

    runtime.transform_llm_output(
        session_id="private-session-id",
        response_text="調査は完了した。pluginを追加した。 RESPONSE_PRIVATE_TEXT",
    )

    with sqlite3.connect(audit_path) as connection:
        row = connection.execute(
            "SELECT event_type, intent, outcome, violations, response_hash FROM audit_events"
        ).fetchone()
    assert row is not None
    assert row[0:3] == ("response_checked", "status", "modified")
    assert "plain_japanese_style" in row[3]
    assert "raw_english_vocabulary" in row[3]
    assert len(row[4]) == 64
    raw_database = audit_path.read_bytes()
    assert b"private-session-id" not in raw_database
    assert b"private-turn-id" not in raw_database
    assert b"USER_PRIVATE_TEXT" not in raw_database
    assert b"RESPONSE_PRIVATE_TEXT" not in raw_database


def test_preemption_block_is_audited_without_tool_arguments(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.db"
    runtime = CommunicationGuardRuntime(audit_path)
    common = {"session_id": "session-audit", "turn_id": "turn-audit"}
    runtime.pre_llm_call(**common, user_message="現在の状況を報告してください")

    runtime.pre_tool_call(
        **common,
        tool_name="terminal",
        args={"command": "SECRET_COMMAND_ARGUMENT"},
    )

    with sqlite3.connect(audit_path) as connection:
        row = connection.execute(
            "SELECT event_type, outcome, violations FROM audit_events"
        ).fetchone()
    assert row == ("tool_blocked", "blocked", '["status_preemption"]')
    assert b"SECRET_COMMAND_ARGUMENT" not in audit_path.read_bytes()


def test_output_transform_recovers_the_intent_for_its_own_session(tmp_path: Path) -> None:
    runtime = CommunicationGuardRuntime(tmp_path / "audit.db")
    runtime.pre_llm_call(
        session_id="session-status",
        turn_id="turn-status",
        user_message="現在の進捗を報告してください",
    )
    runtime.pre_llm_call(
        session_id="session-normal",
        turn_id="turn-normal",
        user_message="通常の作業を続けてください",
    )

    transformed = runtime.transform_llm_output(
        session_id="session-status",
        response_text="調査中です。",
    )

    assert transformed is not None
    assert transformed.startswith("結論:")
    assert "必要な対応:" in transformed


def test_approval_runtime_rejects_multiple_owner_operations() -> None:
    response = (
        "承認依頼です。\n"
        "承認対象: 検証済みの改善を通常環境へ反映することです。\n"
        "目的・成果: 判断情報を簡潔にするためです。\n"
        "承認後の変化: 応答前の監査が有効になります。\n"
        "主要リスクと可逆性: 誤検出は残りますが、無効化して戻せます。\n"
        "推奨: 承認を推奨します。\n"
        "必要な操作: 一覧を開いて、内容を確認してから承認してください。"
    )

    result = guard_response(response, "normal")

    assert "一覧を開いて" not in result.text
    assert "必要な操作: 元の応答では明示されていません。" in result.text
    assert "multiple_approval_actions_removed" in result.violations


def test_review_tool_rewrites_generic_summary_to_fixed_approval_template(
    tmp_path: Path,
) -> None:
    runtime = CommunicationGuardRuntime(tmp_path / "audit.db")

    decision = runtime.pre_tool_call(
        session_id="session-review",
        turn_id="turn-review",
        tool_name="kanban_request_review",
        args={
            "summary": "実装と検証が完了しました。",
            "metadata": {"pda_approval": {"owner_message": _owner_message()}},
        },
    )

    assert decision == {
        "action": "modify",
        "args": {"summary": _owner_review_summary()},
    }


def test_review_tool_blocks_missing_or_worker_facing_owner_copy(tmp_path: Path) -> None:
    runtime = CommunicationGuardRuntime(tmp_path / "audit.db")
    missing = runtime.pre_tool_call(
        session_id="session-review",
        turn_id="turn-missing",
        tool_name="kanban_request_review",
        args={"summary": "実装と検証が完了しました。", "metadata": {}},
    )
    noisy_decisions = []
    for turn_id, purpose in (
        ("turn-merge", "検証済み成果を通常環境へmergeするためです"),
        ("turn-sha", "検証識別子abcdef123456を確認するためです"),
    ):
        noisy_message = _owner_message()
        noisy_message["purpose"] = purpose
        noisy_decisions.append(
            runtime.pre_tool_call(
                session_id="session-review",
                turn_id=turn_id,
                tool_name="kanban_request_review",
                args={
                    "summary": "実装と検証が完了しました。",
                    "metadata": {"pda_approval": {"owner_message": noisy_message}},
                },
            )
        )

    for decision in (missing, *noisy_decisions):
        assert decision is not None
        assert decision["action"] == "block"
        assert "固定テンプレート" in decision["message"]
