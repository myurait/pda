"""過去 7 日のセッション記録から、人間の発言と直前の Claude の応答だけを抜き出してダイジェストにする。

使い方: python3 -I extract_turns.py <出力先ディレクトリ> [除外するセッション ID]
出力: <出力先>/digests/<セッション ID>.md と <出力先>/index.jsonl。
期間外の発言、分岐で重複した発言 (大きい記録の側に残す)、自動実行 (sdk-py・sdk-cli) は除く。
出力には業務の内容と同僚の名前が入るので、リポジトリの外 (git 管理外の tmp/ など) に出す。
"""
import json, os, sys, time, glob, re

ROOT = os.path.expanduser("~/.claude/projects")
OUT = sys.argv[1]
SELF = sys.argv[2] if len(sys.argv) > 2 else ""
os.makedirs(OUT + "/digests", exist_ok=True)
cutoff = time.time() - 7 * 86400

SKIP_PREFIX = ("<command-name>", "<command-message>", "<local-command", "Caveat:", "<task-notification>",
               "<side-sessions-event>", "[Request interrupted", "<bash-input>", "<bash-stdout>", "<ci-monitor-event>",
               "This session is being continued", "<user-memory-input>")

def text_of(content):
    if isinstance(content, str):
        return content, False
    parts, has_tool_result = [], False
    for b in content or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            parts.append(b.get("text", ""))
        elif b.get("type") == "tool_result":
            has_tool_result = True
    return "\n".join(parts), has_tool_result

def strip_reminders(t):
    t = re.sub(r"<system-reminder>.*?</system-reminder>", "", t, flags=re.S)
    return t.strip()

index = []
seen = set()
cut_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(cutoff))
for path in sorted(glob.glob(ROOT + "/*/*.jsonl"), key=os.path.getsize, reverse=True):
    if os.path.getmtime(path) < cutoff or os.path.getsize(path) < 20000:
        continue
    sid = os.path.basename(path)[:-6]
    if sid == SELF:
        continue
    proj = os.path.basename(os.path.dirname(path)).replace("-Users-fox4foofighter-", "")
    turns, last_assistant, entry, first_ts, last_ts, title = [], "", set(), None, None, None
    try:
        f = open(path, errors="replace")
    except Exception:
        continue
    for line in f:
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("entrypoint"):
            entry.add(d["entrypoint"])
        if d.get("type") in ("summary", "ai-title", "custom-title"):
            title = d.get("summary") or d.get("title") or d.get("aiTitle") or d.get("customTitle") or title
        ts = d.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        if d.get("isSidechain"):
            continue
        if d.get("type") == "assistant":
            t, _ = text_of((d.get("message") or {}).get("content"))
            if t.strip():
                last_assistant = t.strip()
        elif d.get("type") == "user" and not d.get("isMeta") and not d.get("isCompactSummary"):
            t, has_tr = text_of((d.get("message") or {}).get("content"))
            if has_tr:
                continue
            t = strip_reminders(t)
            if not t or t.startswith(SKIP_PREFIX):
                continue
            key = (ts, t[:200])
            if (ts or "") < cut_iso or key in seen:
                last_assistant = ""
                continue
            seen.add(key)
            turns.append({"ts": ts, "prev_assistant": last_assistant[-2500:], "user": t[:4000]})
            last_assistant = ""
    if not turns or entry & {"sdk-py", "sdk-cli"} or (len(turns) == 1 and len(turns[0]["user"]) < 40):
        continue
    if last_ts and last_ts < time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(cutoff)):
        continue
    with open(f"{OUT}/digests/{sid}.md", "w") as w:
        w.write(f"# session {sid}\nproject: {proj}\nsource: {path}\nentrypoint: {','.join(sorted(entry))}\nperiod: {first_ts} - {last_ts}\ntitle: {title}\nhuman_turns: {len(turns)}\n\n")
        for i, tr in enumerate(turns, 1):
            w.write(f"## turn {i} ({tr['ts']})\n")
            if tr["prev_assistant"]:
                w.write("### Claude の直前の応答 (末尾 2500 字)\n" + tr["prev_assistant"] + "\n\n")
            w.write("### ユーザー\n" + tr["user"] + "\n\n")
        if last_assistant:
            w.write("## 最後の Claude の応答 (末尾 2500 字)\n" + last_assistant[-2500:] + "\n")
    index.append({"sid": sid, "project": proj, "entry": ",".join(sorted(entry)), "start": first_ts, "end": last_ts,
                  "turns": len(turns), "bytes": os.path.getsize(f"{OUT}/digests/{sid}.md"),
                  "first": turns[0]["user"][:150].replace("\n", " ")})

index.sort(key=lambda x: x["start"] or "")
with open(OUT + "/index.jsonl", "w") as w:
    for r in index:
        w.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(index))
