"""Synthetic fixtures only: never copy real private chat data into tests."""
import hashlib
import importlib.util
import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "history.py"
spec = importlib.util.spec_from_file_location("history_desktop_test", SCRIPT)
assert spec is not None and spec.loader is not None
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)
ORG = "11111111-1111-4111-8111-111111111111"
SID = "22222222-2222-4222-8222-222222222222"
MID = "33333333-3333-4333-8333-333333333333"
HEADER = 0xFCFB6D1BA7725C30
FOOTER = 0xF4FA6F45970D41D8


def cache_file(root, obj=None, name="0123456789abcdef_0", route=None, body=None, encoding=""):
    root.mkdir(exist_ok=True)
    route = route or f"chat_conversations/{SID}?tree=True&rendering_mode=messages"
    key = f"1/0/https://claude.ai/api/organizations/{ORG}/{route}".encode()
    if obj is None:
        obj = {"uuid": SID, "name": "Synthetic Desktop chat", "updated_at": "2026-09-01T00:00:00Z", "chat_messages": []}
    body = json.dumps(obj, ensure_ascii=False).encode() if body is None else body
    metadata = b"HTTP/1.1 200 OK\0content-type: application/json\0"
    if encoding:
        metadata += f"content-encoding: {encoding}\0".encode()
    footer = lambda flags, data, size: struct.pack("<QIIII", FOOTER, flags, zlib.crc32(data), size, 0)
    data = (struct.pack("<QIIII", HEADER, 5, len(key), 0, 0) + key + body + footer(1, body, 0)
            + metadata + hashlib.sha256(key).digest() + footer(3, metadata, len(metadata)))
    p = root / name
    p.write_bytes(data)
    return p


def test_desktop_cache_lists_normal_chat_with_honest_coverage(tmp_path):
    p = cache_file(tmp_path)
    result = history.query(tmp_path, source="desktop-cache")
    assert result["ok"] and result["scan_complete"]
    assert result["coverage_complete"] is False
    assert result["source_kind"] == "claude-desktop-cache"
    assert result["total"] == 1
    row = result["items"][0]
    assert row["session_id"] == SID and row["organization_id"] == ORG
    assert row["title"] == "Synthetic Desktop chat"
    assert row["source"] == str(p)
    assert row["body_available"] is True


def compressed(body, encoding):
    if encoding == "gzip":
        import gzip
        return gzip.compress(body)
    import ctypes
    import ctypes.util
    lib = ctypes.CDLL(ctypes.util.find_library("zstd"))
    lib.ZSTD_compress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    lib.ZSTD_compress.restype = ctypes.c_size_t
    output = ctypes.create_string_buffer(len(body) + 1024)
    size = lib.ZSTD_compress(output, len(output), body, len(body), 1)
    assert size < len(output)
    return output.raw[:size]


@pytest.mark.parametrize("encoding", ["zstd", "gzip"])
def test_desktop_decodes_real_cache_compression(tmp_path, encoding):
    doc = {"uuid": SID, "name": "日本語", "chat_messages": []}
    cache_file(tmp_path, body=compressed(json.dumps(doc).encode(), encoding), encoding=encoding)
    result = history.query(tmp_path, source="desktop-cache")
    assert result["scan_complete"] is True
    assert result["items"][0]["title"] == "日本語"


def chat_doc():
    return {"uuid": SID, "name": "Example", "updated_at": "2026-09-01T00:00:00Z", "current_leaf_message_uuid": MID,
            "chat_messages": [{"uuid": MID, "sender": "human", "created_at": "2026-09-01T00:00:00Z",
                "parent_message_uuid": "00000000-0000-0000-0000-000000000000", "text": "not this fallback",
                "content": [{"type": "text", "text": "日本語 needle " + "a" * 50}, {"type": "thinking", "thinking": "DO NOT RETURN"}]}]}


def test_desktop_reads_citable_paginated_text_without_thinking(tmp_path):
    p = cache_file(tmp_path, chat_doc())
    before = (p.read_bytes(), p.stat().st_mtime_ns)
    row = history.query(tmp_path, source="desktop-cache", action="read", session_id=SID, project=ORG,
                        text_offset=4, text_limit=10)["items"][0]
    assert row["text"] == "needle aaa"
    assert row["uuid"] == MID and row["source_message_index"] == 0
    assert row["role"] == "user" and row["text_next_offset"] == 14
    assert row["source_sha256"] == hashlib.sha256(before[0]).hexdigest()
    assert row["source"] == str(p) and row["timestamp"] == "2026-09-01T00:00:00Z"
    assert (p.read_bytes(), p.stat().st_mtime_ns) == before


def test_desktop_cli_search_then_read(tmp_path):
    import subprocess
    cache_file(tmp_path, chat_doc())
    cmd = [sys.executable, "-B", str(SCRIPT), "search", "--source=desktop-cache", "--root", str(tmp_path), "--search=NEEDLE"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    assert p.returncode == 0, p.stderr
    result = json.loads(p.stdout)
    assert result["total"] == 1 and result["coverage_complete"] is False
    hit = result["items"][0]
    assert "needle" in hit["snippet"]
    read = history.query(tmp_path, source="desktop-cache", action="read", session_id=hit["session_id"],
                         project=hit["organization_id"], offset=hit["message_index"])
    assert read["items"][0]["uuid"] == hit["uuid"]
    assert read["items"][0]["source_sha256"] == hit["source_sha256"]


def test_desktop_prefers_newer_conversation_revision_not_file_mtime(tmp_path):
    import os
    fresh = chat_doc()
    fresh["updated_at"] = "2026-09-02T00:00:00Z"
    p = cache_file(tmp_path, fresh)
    old = cache_file(tmp_path, chat_doc(), name="abcdef0123456789_0")
    os.utime(p, ns=(10, 10))
    os.utime(old, ns=(20, 20))
    result = history.query(tmp_path, source="desktop-cache")
    assert result["total"] == 1
    assert result["items"][0]["source"] == str(p)


@pytest.mark.parametrize("encoding", ["zstd", "gzip", "identity"])
def test_desktop_bounds_decoded_bodies(tmp_path, monkeypatch, encoding):
    doc = json.dumps(chat_doc()).encode()
    body = doc if encoding == "identity" else compressed(doc, encoding)
    cache_file(tmp_path, body=body, encoding=encoding)
    monkeypatch.setattr(history, "DESKTOP_BODY_LIMIT", 100)
    result = history.query(tmp_path, source="desktop-cache")
    assert not result["scan_complete"] and result["total"] == 0


@pytest.mark.parametrize("target", ["body", "key", "footer"])
def test_desktop_rejects_corrupt_cache_with_explicit_warning(tmp_path, target):
    p = cache_file(tmp_path, chat_doc())
    data = bytearray(p.read_bytes())
    pos = 24 + struct.unpack_from("<I", data, 12)[0] if target == "body" else (-1 if target == "footer" else 24)
    data[pos] ^= 1
    p.write_bytes(data)
    result = history.query(tmp_path, source="desktop-cache")
    assert result["total"] == 0 and not result["scan_complete"]


def test_desktop_does_not_read_cookie_cache_or_symlink_target(tmp_path):
    p = cache_file(tmp_path, chat_doc())
    secret = cache_file(tmp_path, {"credential": "SYNTHETIC_SECRET"}, name="fedcba9876543210_0", route="auth/session")
    outside = tmp_path.parent / "outside-cache-fixture"
    p.rename(outside)
    p.symlink_to(outside)
    result = history.query(tmp_path, source="desktop-cache")
    assert result["total"] == 0
    assert "SYNTHETIC_SECRET" not in json.dumps(result)
    with pytest.raises(ValueError, match="symlink"):
        linked = tmp_path.parent / "linked-cache-fixture"
        linked.symlink_to(tmp_path, target_is_directory=True)
        history.query(linked, source="desktop-cache")


def test_desktop_reports_truncated_source_messages(tmp_path):
    doc = chat_doc()
    doc["chat_messages"][0]["truncated"] = True
    cache_file(tmp_path, doc)
    result = history.query(tmp_path, source="desktop-cache")
    assert not result["scan_complete"]
    assert "truncated" in json.dumps(result["warnings"])


def test_desktop_caps_aggregate_decoded_bytes_and_warning_count(tmp_path, monkeypatch):
    cache_file(tmp_path, chat_doc())
    monkeypatch.setattr(history, "DESKTOP_AGGREGATE_LIMIT", 100, raising=False)
    with pytest.raises(ValueError, match="aggregate"):
        history.query(tmp_path, source="desktop-cache")
    monkeypatch.setattr(history, "DESKTOP_AGGREGATE_LIMIT", 256 * 1024 * 1024)
    doc = chat_doc()
    doc["chat_messages"] = [{"sender": "unknown"}] * 1001
    cache_file(tmp_path, doc)
    with pytest.raises(ValueError, match="warnings"):
        history.query(tmp_path, source="desktop-cache")


def test_live_verifier_refuses_optimized_python_before_any_io():
    import subprocess
    verifier = Path(__file__).with_name("verify_desktop_remote.py")
    result = subprocess.run([sys.executable, "-O", "-B", str(verifier), "--help"], capture_output=True, text=True, timeout=5)
    assert result.returncode != 0
    assert "optimization" in result.stderr.lower()


def test_desktop_string_content_is_not_silently_dropped(tmp_path):
    doc = chat_doc()
    doc["chat_messages"][0]["content"] = "string content message"
    del doc["chat_messages"][0]["text"]
    cache_file(tmp_path, doc)
    result = history.query(tmp_path, source="desktop-cache", action="read", session_id=SID)
    assert result["scan_complete"] is True
    assert result["total"] == 1
    assert result["items"][0]["text"] == "string content message"
