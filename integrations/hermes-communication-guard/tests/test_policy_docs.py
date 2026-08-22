from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ESCALATION_SKILL = REPO / "profiles" / "pda" / "skills" / "pda-user-escalation" / "SKILL.md"
IMPROVEMENT_SKILL = (
    REPO / "profiles" / "pda" / "skills" / "pda-autonomous-improvement" / "SKILL.md"
)
DESIGN = REPO / "docs" / "design" / "communication-quality-runtime-guard.md"
README = REPO / "integrations" / "hermes-communication-guard" / "README.md"


def test_owner_escalation_skill_defines_approval_copy_boundary_and_examples() -> None:
    content = ESCALATION_SKILL.read_text(encoding="utf-8")

    for required in (
        "何を承認するのか",
        "何のためか／得られる成果",
        "承認後に何が変わるか",
        "主要リスクと可逆性",
        "推奨と一つの明確な操作",
        "詳しいほど良い",
        "良い例",
        "悪い例",
        "機械検証用metadata",
    ):
        assert required in content


def test_owner_escalation_skill_contains_fixed_approval_request_template() -> None:
    content = ESCALATION_SKILL.read_text(encoding="utf-8")
    section = content.split("### 固定テキストテンプレート", 1)[1].split("### ", 1)[0]
    expected = (
        "承認依頼です。\n"
        "承認対象: [何を承認するか]\n"
        "目的・成果: [何のためか・得られる成果]\n"
        "承認後の変化: [何が変わるか]\n"
        "主要リスクと可逆性: [判断に必要なリスクと戻せるか]\n"
        "推奨: [推奨判断]\n"
        "必要な操作: [一つだけ]"
    )

    assert expected in section
    for forbidden_field in (
        "変更ファイル:",
        "テスト件数:",
        "実行コマンド:",
        "作業ツリー:",
        "SHA:",
    ):
        assert forbidden_field not in section


def test_improvement_worker_requires_separate_owner_message_contract() -> None:
    content = IMPROVEMENT_SKILL.read_text(encoding="utf-8")

    for field in (
        "owner_message",
        "approval_subject",
        "purpose",
        "changes_after_approval",
        "risk_and_reversibility",
        "recommendation",
        "action",
    ):
        assert field in content
    assert "worker-only technical evidence" in content


def test_design_and_runbook_document_runtime_boundary_and_rollback() -> None:
    design = DESIGN.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    for required in (
        "transform_llm_output",
        "streaming",
        "fail-open",
        "30 days",
        "owner_message",
        "technical evidence",
    ):
        assert required in design
    assert "install.py --disable" in readme
    assert "hermes plugins doctor" in readme
    assert "audit.db" in readme
