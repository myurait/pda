"""Explicit opt-in live probe. Never stores transcript text or invokes Claude.

Usage: python -B tests/verify_remote.py --connection connection.main.json
This is NOT a pytest test and never automatically contacts a real host.
"""
import argparse
import datetime
import hashlib
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "history.py"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.connection.read_text())
    ssh = ["/usr/bin/ssh", "-T", "-a", "-x", "-i", str(Path(config["identity_file"]).expanduser()),
           "-p", str(config["port"]), "-l", config["user"],
           "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=yes",
           "-o", "UpdateHostKeys=no", "-o", "IdentitiesOnly=yes", "-o", "ClearAllForwardings=yes",
           "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2"]
    if config.get("known_hosts_file"):
        ssh += ["-o", "UserKnownHostsFile=" + str(Path(config["known_hosts_file"]).expanduser())]
    ssh += [config["host"], shlex.join([config.get("remote_python", "python3"), "-I", "-B", "-"])]
    probe = '''import pathlib,hashlib,json,platform,getpass
root=pathlib.Path.home()/".claude/projects"
assert root.is_dir() and root.resolve()==root
files={}
for path in sorted(root.glob("*/*.jsonl")):
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        continue
    before=path.stat()
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            digest.update(block)
    after=path.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns), "changed during fingerprint"
    files[str(path)]={"sha256":digest.hexdigest(),"mtime_ns":after.st_mtime_ns,"size":after.st_size}
print(json.dumps({"host":platform.node(),"os":platform.system(),"user":getpass.getuser(),"root":str(root),"files":files}))
'''

    def snapshot():
        process = subprocess.run(ssh, input=probe, text=True, capture_output=True, timeout=45)
        assert process.returncode == 0, "read-only SSH fingerprint failed: " + process.stderr[:500]
        return json.loads(process.stdout)

    durations = []

    def query(action, **options):
        command = [sys.executable, "-B", str(SOURCE), action, "--connection", str(args.connection)]
        for key, value in options.items():
            # Claude encodes absolute paths as project names beginning with '-'.
            command += ["--" + key.replace("_", "-") + "=" + str(value)]
        started = time.monotonic()
        process = subprocess.run(command, text=True, capture_output=True, timeout=50)
        durations.append(round(time.monotonic() - started, 3))
        result = json.loads(process.stdout)
        assert process.returncode == 0 and result["ok"], "reader failed: " + result.get("error", "unknown")
        assert result["transport"] == "ssh" and result["user"] == config["user"]
        assert result["coverage_complete"] and not result["warnings"], "incomplete source coverage"
        return result

    before = snapshot()
    rows = []
    offset = 0
    while True:
        page = query("list", limit=100, offset=offset)
        rows.extend(page["items"])
        if page["next_offset"] is None:
            break
        assert page["next_offset"] > offset
        offset = page["next_offset"]
    listed_sources = {row["source"] for row in rows}
    assert len(rows) == len(listed_sources) == page["total"] == len(before["files"])
    assert listed_sources == set(before["files"]), "listed inventory differs from actual source files"
    selected = next(row for row in rows if row["messages"] > 0 and row["title"])
    read = query("read", project=selected["project"], session_id=selected["session_id"], limit=2, text_limit=1000)
    first = read["items"][0]
    assert first["text"] and first["source"] == selected["source"]
    assert first["line"] > 0 and first["timestamp"] and first["uuid"]
    needle = first["text"].strip()[:12]
    search = query("search", search=needle, limit=100)
    assert search["total"] > 0
    targeted = query("search", project=selected["project"], session_id=selected["session_id"], search=needle)
    hit = next(item for item in targeted["items"] if item["message_index"] == first["index"])
    assert hit["line"] == first["line"] and hit["source"] == first["source"]
    reopened = query("read", project=hit["project"], session_id=hit["session_id"], offset=hit["message_index"], limit=1, text_limit=1000)
    assert reopened["items"][0]["text"] == first["text"]
    after = snapshot()
    unchanged = before["files"] == after["files"]
    assert unchanged, "history contents or mtimes changed during live verification; do not claim immutability"
    manifest = json.dumps(before["files"], sort_keys=True, separators=(",", ":")).encode()
    print(json.dumps({
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ok": True,
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "connection_sha256": hashlib.sha256(args.connection.read_bytes()).hexdigest(),
        "host": before["host"], "os": before["os"], "user": before["user"], "root": before["root"],
        "source_files": len(before["files"]), "source_bytes": sum(f["size"] for f in before["files"].values()),
        "listed_unique_sessions": len(rows), "list_pages": sum(1 for i in range(0, len(rows), 100)),
        "corpus_search_hits": search["total"], "targeted_search_hits": targeted["total"],
        "read_messages": len(read["items"]), "source_line_uuid_timestamp_verified": True,
        "search_to_read_text_equal": True, "sha256_and_mtime_unchanged": unchanged,
        "inventory_sha256_before": hashlib.sha256(manifest).hexdigest(),
        "inventory_sha256_after": hashlib.sha256(json.dumps(after["files"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "coverage_complete": True, "cli_calls": len(durations), "max_cli_seconds": max(durations),
        "private_text_persisted": False,
        "scope": "All top-level CLI transcripts enumerated; sample text/search round trip; not Desktop/cloud/nested subagent coverage",
        "runtime_deployed": False
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
