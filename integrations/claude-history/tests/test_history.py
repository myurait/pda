"""Synthetic transcript fixtures, never a substitute for remote verification."""
import importlib.util
import json
from pathlib import Path

SOURCE = Path(__file__).parents[1] / "history.py"


def load_reader():
    assert SOURCE.exists(), "read-only Claude history reader is not implemented"
    spec = importlib.util.spec_from_file_location("claude_history", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transcript(root, project="project-a", session="11111111-1111-4111-8111-111111111111", records=None):
    path = root / project / (session + ".jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    if records is None:
        records = [
            {"type": "user", "uuid": "u1", "sessionId": session, "timestamp": "2026-09-01T01:00:00Z", "cwd": "/work/demo", "message": {"role": "user", "content": "日本語の履歴を確認"}},
            {"type": "assistant", "uuid": "a1", "parentUuid": "u1", "timestamp": "2026-09-01T01:00:01Z", "message": {"role": "assistant", "content": [{"type": "text", "text": "確認しました"}]}},
        ]
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    return path


def test_lists_sessions_without_modifying_transcripts(tmp_path):
    source = transcript(tmp_path)
    before = (source.read_bytes(), source.stat().st_mtime_ns)
    result = load_reader().query(tmp_path, action="list", limit=10)
    assert result["ok"] is True
    assert result["total"] == 1
    row = result["items"][0]
    assert row["session_id"] == source.stem
    assert row["project"] == "project-a"
    assert row["title"] == "日本語の履歴を確認"
    assert row["messages"] == 2
    assert row["source"] == str(source)
    assert before == (source.read_bytes(), source.stat().st_mtime_ns)


def test_reads_selected_session_with_message_and_text_pagination(tmp_path):
    source = transcript(tmp_path)
    result = load_reader().query(tmp_path, action="read", session_id=source.stem,
                                 offset=0, limit=1, text_limit=3)
    assert result["items"][0]["text"] == "日本語"
    assert result["items"][0]["text_next_offset"] == 3
    assert result["next_offset"] == 1
    remaining = load_reader().query(tmp_path, action="read", session_id=source.stem,
                                    offset=0, limit=1, text_offset=3)
    assert remaining["items"][0]["text"] == "の履歴を確認"
    last = load_reader().query(tmp_path, action="read", session_id=source.stem, offset=1)
    assert last["items"][0]["role"] == "assistant"
    assert last["items"][0]["line"] == 2
    assert last["next_offset"] is None


def test_searches_literal_text_case_insensitively_with_source_positions(tmp_path):
    source = transcript(tmp_path, records=[
        {"type": "user", "message": {"content": "前置き " + "x" * 400 + " NEEDLE.* 終わり"}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "NEEDLE.*"}}]}},
    ])
    result = load_reader().query(tmp_path, action="search", search="needle.*")
    assert result["total"] == 1
    assert "NEEDLE.*" in result["items"][0]["snippet"]
    assert result["items"][0]["line"] == 1
    assert result["items"][0]["message_index"] == 0
    assert result["items"][0]["source"] == str(source)
    assert load_reader().query(tmp_path, action="search", search="no match")["items"] == []


def test_missing_root_and_invalid_queries_are_not_empty_success(tmp_path):
    import pytest
    reader = load_reader()
    with pytest.raises((ValueError, FileNotFoundError)):
        reader.query(tmp_path / "missing")
    for args in ({"action": "delete"}, {"limit": 0}, {"offset": -1},
                 {"text_limit": 0}, {"action": "search", "search": ""}):
        with pytest.raises(ValueError):
            reader.query(tmp_path, **args)


def test_skips_symlinks_and_reports_partial_transcripts(tmp_path):
    reader = load_reader()
    root = tmp_path / "projects"
    source = transcript(root)
    outside = transcript(tmp_path / "outside", project="private")
    (root / "external-project").symlink_to(outside.parent, target_is_directory=True)
    (source.parent / "external.jsonl").symlink_to(outside)
    with source.open("a") as stream:
        stream.write('{"type":')
    result = reader.query(root)
    assert result["total"] == 1
    assert result["coverage_complete"] is False
    assert result["warnings"][0]["line"] == 3
    assert "malformed" in result["warnings"][0]["reason"]


def test_refuses_oversized_transcript_before_reading(tmp_path, monkeypatch):
    import pytest
    source = transcript(tmp_path)
    reader = load_reader()
    monkeypatch.setattr(reader, "MAX_FILE_BYTES", 8, raising=False)
    with pytest.raises(ValueError, match="size limit"):
        reader.query(tmp_path)


def test_cli_reads_real_files_without_importing_claude(tmp_path):
    import subprocess
    import sys
    source = transcript(tmp_path)
    result = subprocess.run([sys.executable, "-B", str(SOURCE), "list", "--root", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip(), "CLI did not emit a result"
    body = json.loads(result.stdout)
    assert body["items"][0]["session_id"] == source.stem
    assert body["transport"] == "local"
    error = subprocess.run([sys.executable, "-B", str(SOURCE), "read", "--root", str(tmp_path), "--session-id", "missing"], capture_output=True, text=True)
    assert error.returncode == 1
    assert json.loads(error.stdout)["ok"] is False


def test_remote_transport_runs_same_reader_over_stdin_without_file_upload(tmp_path):
    import subprocess
    import sys
    import shlex
    source = transcript(tmp_path)
    calls = []
    def simulated_ssh(argv, **kwargs):
        calls.append((argv, kwargs))
        command = shlex.split(argv[-1])
        assert command[:4] == ["python3", "-I", "-B", "-"]
        return subprocess.run([sys.executable] + command[1:], input=kwargs["input"], text=True, capture_output=True, timeout=5)
    reader = load_reader()
    assert hasattr(reader, "remote_query"), "SSH history transport not implemented"
    result = reader.remote_query({"host": "example.test", "user": "test-user", "identity_file": str(SOURCE)},
                                 {"root": str(tmp_path), "action": "list"}, runner=simulated_ssh)
    assert result["items"][0]["session_id"] == source.stem
    assert result["transport"] == "ssh"
    argv, kwargs = calls[0]
    assert "StrictHostKeyChecking=yes" in argv
    assert "UpdateHostKeys=no" in argv
    assert "BatchMode=yes" in argv
    assert argv[argv.index("-i") + 1] == str(SOURCE)  # Opaque file in the simulated runner, not a real key.
    assert argv[argv.index("-F") + 1] == "/dev/null"  # No extra identities from ssh_config.
    assert kwargs["timeout"] == 45
    assert kwargs.get("shell", False) is False


def test_remote_transport_failure_never_falls_back_to_local_history():
    import subprocess
    import pytest
    reader = load_reader()
    assert hasattr(reader, "remote_query"), "SSH history transport not implemented"
    def refused(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 255, "", "connection refused")
    with pytest.raises(RuntimeError, match="connection refused"):
        reader.remote_query({"host": "example.test", "user": "test-user", "identity_file": str(SOURCE)}, {"action": "list"}, runner=refused)
    def timed_out(*args, **kwargs):
        raise subprocess.TimeoutExpired("ssh", 45)
    with pytest.raises(TimeoutError):
        reader.remote_query({"host": "example.test", "user": "test-user", "identity_file": str(SOURCE)}, {"action": "list"}, runner=timed_out)
    for config in ({"host": "-oProxyCommand=evil", "user": "test"}, {"host": "example.test"}):
        with pytest.raises(ValueError):
            reader.remote_query(config, {"action": "list"}, runner=refused)


def test_remote_requires_explicit_existing_key_before_starting_ssh(tmp_path):
    import pytest
    reader = load_reader()
    def forbidden_runner(*args, **kwargs):
        pytest.fail("SSH must not run without the selected existing key")
    for value in (None, "", "  ", 1, str(tmp_path / "missing"), str(tmp_path)):
        config = {"host": "example.test", "user": "test-user", "identity_file": value}
        with pytest.raises(ValueError, match="identity_file"):
            reader.remote_query(config, {"action": "list"}, runner=forbidden_runner)


def test_search_snippet_uses_original_unicode_positions(tmp_path):
    transcript(tmp_path, records=[{"type": "user", "message": {"content": "ß" * 200 + " TARGET"}}])
    result = load_reader().query(tmp_path, action="search", search="target")
    assert "TARGET" in result["items"][0]["snippet"]


def test_opt_in_tool_history_preserves_calls_and_results_without_thinking(tmp_path):
    source = transcript(tmp_path, records=[
        {"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "private thought"}, {"type": "tool_use", "name": "Read", "id": "tool1", "input": {"file_path": "/example"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tool1", "content": "file body"}]}},
    ])
    assert load_reader().query(tmp_path, action="read", session_id=source.stem)["items"] == []
    result = load_reader().query(tmp_path, action="read", session_id=source.stem, include_tools=True)
    assert result["total"] == 2
    assert "Read" in result["items"][0]["text"]
    assert "file body" in result["items"][1]["text"]
    assert "private thought" not in json.dumps(result)


def test_lists_and_searches_corpus_larger_than_legacy_256_mib(tmp_path):
    # Real valid JSONL, no size mocks: similar aggregate scale to a long-lived Mac.
    padding = json.dumps({"type": "progress", "data": "x" * (1024 * 1024)}) + "\n"
    for index in range(9):
        source = transcript(tmp_path, session="scale-%s" % index)
        with source.open("a") as stream:
            for _ in range(32):
                stream.write(padding)
    reader = load_reader()
    listed = reader.query(tmp_path, action="list", limit=5)
    assert listed["total"] == 9
    assert listed["next_offset"] == 5
    assert listed["coverage_complete"] is True
    assert reader.query(tmp_path, action="search", search="履歴")["total"] == 9


def test_aggregate_limit_still_refuses_more_than_one_gib(tmp_path):
    import pytest
    source = transcript(tmp_path)
    # Sparse file proves the discovery cap without allocating/reading 1 GiB.
    with source.open("ab") as stream:
        stream.truncate(1024 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="scan size limit exceeded"):
        load_reader().query(tmp_path)


def test_cli_supports_real_dash_prefixed_project_names(tmp_path):
    import subprocess
    import sys
    source = transcript(tmp_path, project="-Users-demo-dev-project")
    process = subprocess.run([sys.executable, "-B", str(SOURCE), "read", "--root", str(tmp_path),
                              "--project=" + source.parent.name, "--session-id=" + source.stem],
                             text=True, capture_output=True, timeout=5)
    assert process.returncode == 0
    assert json.loads(process.stdout)["items"][0]["text"] == "日本語の履歴を確認"


def test_corrupt_transcript_cannot_grow_unbounded_warning_output(tmp_path):
    import pytest
    source = transcript(tmp_path, records=[])
    source.write_text("not-json\n" * 1001)
    with pytest.raises(ValueError, match="malformed"):
        load_reader().query(tmp_path)
