"""Exercise real SSH/CLI history, retaining only sanitized integrity evidence."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time

if not __debug__:
    raise SystemExit("Live verification refuses Python optimization; assertions must remain active")

p = argparse.ArgumentParser()
p.add_argument("--reader", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1]/"history.py")
p.add_argument("--connection", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1]/"connection.main.json")
p.add_argument("--output", type=pathlib.Path, required=True)
args = p.parse_args()
config = json.loads(args.connection.read_text())
SSH = ["/usr/bin/ssh", "-F", "/dev/null", "-T", "-a", "-x", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
       "-o", "StrictHostKeyChecking=yes", "-o", "UpdateHostKeys=no", "-o", "IdentitiesOnly=yes", "-o", "ClearAllForwardings=yes",
       "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2", "-i", config["identity_file"], "-p", str(config["port"]),
       "-l", config["user"], config["host"], "/usr/bin/python3 -I -B -"]
SNAPSHOT = r'''
import pathlib,hashlib,json,re,struct,os,platform
root=pathlib.Path.home()/'Library/Application Support/Claude/Cache/Cache_Data'
items={}; ids=set()
for path in root.glob('*_0'):
    if path.is_symlink() or not path.is_file(): continue
    with path.open('rb') as f:
        first=f.read(24)
        if len(first)!=24: continue
        magic,version,n,_,_=struct.unpack('<QIIII',first)
        if magic!=0xfcfb6d1ba7725c30 or n>8192: continue
        key=f.read(n)
        match=re.search(rb'https://claude\.ai/api/organizations/([0-9a-f-]{36})/chat_conversations/([0-9a-f-]{36})(?:\?[^\x00]*)?$',key)
        if not match: continue
        before=os.fstat(f.fileno()); body=f.read(64*1024*1024+1); after=os.fstat(f.fileno())
        assert len(body)<=64*1024*1024 and before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns
        items[str(path)]=[hashlib.sha256(first+key+body).hexdigest(),after.st_mtime_ns]
        ids.add(tuple(x.decode() for x in match.groups()))
print(json.dumps({'host':platform.node(),'os':platform.system(),'items':items,'identities':sorted(ids)}))
'''


def snapshot():
    result = subprocess.run(SSH, input=SNAPSHOT, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError("remote inventory failed")
    return json.loads(result.stdout)


durations = []


def query(action, **kwargs):
    argv = [sys.executable, "-B", str(args.reader), action, "--source=desktop-cache", "--connection", str(args.connection)]
    argv += ["--" + k.replace("_", "-") + "=" + str(v) for k, v in kwargs.items()]
    started = time.monotonic()
    process = subprocess.run(argv, capture_output=True, text=True, timeout=50)
    durations.append(time.monotonic() - started)
    result = json.loads(process.stdout)
    assert process.returncode == 0 and result["ok"], "actual CLI failed"
    assert result["transport"] == "ssh" and result["source_kind"] == "claude-desktop-cache"
    assert result["scan_complete"] and not result["coverage_complete"], "cache scope/warnings misreported"
    return result


before = snapshot()
assert before["host"] == "main" and before["os"] == "Darwin"
all_rows = []
offset = 0
while True:
    result = query("list", limit=7, offset=offset)
    all_rows.extend(result["items"])
    if result["next_offset"] is None:
        break
    offset = result["next_offset"]
assert len(all_rows) == result["total"]
assert {(x["organization_id"], x["session_id"]) for x in all_rows} == {tuple(x) for x in before["identities"]}
messages_read = 0
nonempty_sessions = 0
for row in all_rows:
    result = query("read", project=row["organization_id"], session_id=row["session_id"], limit=100, text_limit=100000)
    offset = 0
    while True:
        for item in result["items"]:
            assert item["source_sha256"] == before["items"][item["source"]][0]
            assert item["source_sha256"] == row["source_sha256"]
            assert item["uuid"] and item["role"] in ("user", "assistant")
            if item["text_next_offset"] is not None:
                nxt = item["text_next_offset"]
                while nxt is not None:
                    continuation = query("read", project=row["organization_id"], session_id=row["session_id"],
                                         offset=item["index"], limit=1, text_limit=100000, text_offset=nxt)["items"][0]
                    assert continuation["source_sha256"] == item["source_sha256"] and continuation["uuid"] == item["uuid"]
                    nxt = continuation["text_next_offset"]
            messages_read += 1
        if result["next_offset"] is None:
            break
        offset = result["next_offset"]
        result = query("read", project=row["organization_id"], session_id=row["session_id"], offset=offset, limit=100, text_limit=100000)
    nonempty_sessions += bool(row["messages"])
assert messages_read == sum(x["messages"] for x in all_rows)
search = query("search", search="の", limit=100)
assert search["total"] > 0, "real source search did not produce a hit"
hit = search["items"][0]
reread = query("read", project=hit["organization_id"], session_id=hit["session_id"], offset=hit["message_index"], limit=1)["items"][0]
assert reread["uuid"] == hit["uuid"] and reread["source_sha256"] == hit["source_sha256"]
assert "の" in reread["text"]
after = snapshot()
unchanged = before == after
report = {"ok": unchanged, "scope": "Desktop normal Chat cached text snapshots, not complete/live cloud history",
          "host": "main", "os": "Darwin", "cache_files": len(before["items"]), "sessions": len(all_rows),
          "nonempty_sessions": nonempty_sessions, "text_messages_read": messages_read, "list_identity_set_matches_raw_cache": True,
          "search_hits": search["total"], "search_read_uuid_and_digest_match": True,
          "all_source_sha256_and_mtime_unchanged": unchanged,
          "aggregate_inventory_digest": hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
          "cli_calls": len(durations), "max_cli_seconds": round(max(durations), 3),
          "reader_sha256": hashlib.sha256(args.reader.read_bytes()).hexdigest(),
          "private_text_persisted": False, "credentials_accessed": False}
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
raise SystemExit(0 if unchanged else 1)
