from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class _FakeContext:
    def __init__(self) -> None:
        self.hooks: list[str] = []
        self.sections: dict[str, str] = {}

    def register_hook(self, name: str, callback: object) -> None:
        del callback
        self.hooks.append(name)

    def register_system_prompt_section(
        self,
        section_id: str,
        content: str,
        **kwargs: object,
    ) -> None:
        del kwargs
        self.sections[section_id] = content


def test_plugin_registers_runtime_enforcement_and_approval_policy() -> None:
    spec = importlib.util.spec_from_file_location(
        "pda_communication_guard_plugin",
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = _FakeContext()

    module.register(context)

    assert context.hooks == [
        "pre_llm_call",
        "pre_tool_call",
        "transform_llm_output",
        "post_llm_call",
        "on_session_end",
    ]
    policy = context.sections["pda.communication-quality"]
    for required in (
        "承認対象",
        "目的・成果",
        "承認後の変化",
        "主要リスクと可逆性",
        "推奨",
        "一つの操作",
    ):
        assert required in policy
    assert "SHA" not in policy
    assert "テスト件数" not in policy


def test_real_plugin_manager_enforces_preemption_and_output_transform(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from hermes_cli.plugins import PluginManager

    home = tmp_path / "hermes-home"
    plugin_dir = home / "plugins" / "pda-communication-guard"
    shutil.copytree(ROOT, plugin_dir, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (home / "config.yaml").write_text(
        yaml.safe_dump({"plugins": {"enabled": ["pda-communication-guard"]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    manager = PluginManager()

    manager.discover_and_load()
    context = manager.invoke_hook(
        "pre_llm_call",
        session_id="session-real",
        turn_id="turn-real",
        user_message="現在の進捗を報告してください",
    )
    blocked = manager.invoke_hook(
        "pre_tool_call",
        session_id="session-real",
        turn_id="turn-real",
        tool_name="web_search",
        args={"query": "new work"},
    )
    transformed = manager.invoke_hook(
        "transform_llm_output",
        session_id="session-real",
        response_text="調査は完了した。pluginを追加した。",
        model="test-model",
        platform="cli",
    )

    assert context and "新しいツールを実行せず" in context[0]["context"]
    assert blocked and blocked[0]["action"] == "block"
    assert transformed and "プラグイン" in transformed[0]
    assert "必要な対応:" in transformed[0]
