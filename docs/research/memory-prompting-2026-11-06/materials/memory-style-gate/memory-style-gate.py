#!/usr/bin/env python3
"""メモリ・skill・CLAUDE.md の書き換えを検査し、書き方の規則から外れた行を書き手に返して直させる。

書き方の規則は ~/.claude/memory/feedback_memory_writing_rules.md にある。各ルールを言い切りの
命令文で書き、条件節・禁止形・理由を本文に入れない形。

起動の仕方 (settings.json):
- PostToolUse (Write|Edit|MultiEdit): `memory-style-gate.py --post-tool-use`
  書き換えたファイルが検査の対象なら検査する
- Stop: `memory-style-gate.py --stop`
  このターンの開始 (mark-turn-start.py の記録) 以降に変わった対象のファイルを検査する。
  Bash (sed・cp など) での書き換えはここで拾う

検査は 2 段。
1. 構造 (このスクリプト内): 強調の `**`、`Why:` / `How to apply` の見出し、「発火」の表、
   frontmatter の name と description、索引への登録、`[[name]]` の参照先
2. 文の書き方 (Jev): 本文を 1 文ずつに切り、文ごとに Jev へ書き方の分類を問う。
   問いと通すラベルは memory-style-gate-questions.json にある。分類の結果は文の内容ごとに
   保存し、同じ文は 2 回目から問わない。Jev が失敗した文は、語の形で拾う検査で代える

返し方: 外れた行があれば decision=block と、直す行の一覧を返す。同じファイルを同じセッションで
2 回返したあとは、3 回目から通す (止めることに意味は無く、直し方を案内するのが目的のため)。
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time

HOME = pathlib.Path.home()
CLAUDE = HOME / ".claude"
HERE = pathlib.Path(__file__).resolve().parent
QUESTIONS = HERE / "memory-style-gate-questions.json"
JUDGE = CLAUDE / "skills" / "jev-judge" / "scripts" / "jev_judge.py"
STATE_DIR = pathlib.Path(os.environ.get("MEMORY_STYLE_GATE_STATE_DIR") or (CLAUDE / "hook-state"))
TRACE = pathlib.Path(os.environ.get("MEMORY_STYLE_GATE_TRACE") or (CLAUDE / "debug" / "memory-style-gate.log"))
RULE_MEMORY = "~/.claude/memory/feedback_memory_writing_rules.md"

MAX_BLOCKS_PER_FILE = 2
JUDGE_TIMEOUT = 20
WORKERS = 8
MAX_SENTENCES = 400

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)")
TABLE_RULE = re.compile(r"^\|?[-\s|:]+\|?$")
WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")

# Jev が使えない文に代わりに当てる、語の形での検査
FALLBACK_PATTERNS = [
    ("conditional", re.compile(r"とき[、はに]|場合[、はに]|ならば|なら[、。]|たら[、。]|れば[、。]|際[はに、]")),
    ("prohibitive", re.compile(r"しない[。、]|ない[。]|ないこと|禁止|NEVER|Never |Do not|DO NOT|避ける|控える")),
    ("rationale", re.compile(r"ため[。、に]|ためである|からである|ので[、。]|なぜなら|Why:")),
]


# ---------------------------------------------------------------- 対象の判定

def is_target(path: pathlib.Path) -> bool:
    p = str(path)
    if not p.endswith(".md"):
        return False
    for skip in ("/skills/synced/", "/plugins/", "/tmp/", "/backup/", "/node_modules/", "/results/"):
        if skip in p:
            return False
    if path == (CLAUDE / "CLAUDE.md").resolve() or p == str(CLAUDE / "CLAUDE.md"):
        return True
    if path.name == "MEMORY.md" and (path.parent == CLAUDE or path.parent.name == "memory"):
        return True
    if "/memory/" in p:
        return True
    if "/skills/" in p:
        return True
    return False


def kind_of(path: pathlib.Path) -> str:
    """index / skill / claude_md / memory のどれか。検査する構造が変わる。"""
    if path.name in ("MEMORY.md", "communication-index.md"):
        return "index"
    if path.name == "CLAUDE.md":
        return "claude_md"
    if "/skills/" in str(path):
        return "skill"
    return "memory"


# ---------------------------------------------------------------- 文の切り出し

def split_body(text: str) -> tuple[dict, list[tuple[int, str]]]:
    """frontmatter と、本文の (行番号, 文) の一覧を返す。コードブロックと見出しは除く。"""
    lines = text.splitlines()
    front: dict = {}
    start = 0
    if lines and lines[0].strip() == "---":
        j = 1
        while j < len(lines) and lines[j].strip() != "---":
            m = re.match(r"^(\w+):\s*(.*)$", lines[j])
            if m:
                front[m.group(1)] = m.group(2).strip()
            j += 1
        start = j + 1
    out: list[tuple[int, str]] = []
    if "description" in front and front["description"] not in ("", ">", "|"):
        out.append((2, front["description"]))
    fence = False
    for idx in range(start, len(lines)):
        raw = lines[idx]
        if FENCE.match(raw):
            fence = not fence
            continue
        if fence:
            continue
        s = raw.strip()
        if not s or s.startswith("#") or TABLE_RULE.fullmatch(s):
            continue
        s = re.sub(r"^(?:[-*]|\d+\.)\s+", "", s)
        if s.startswith("|"):
            out.append((idx + 1, " | ".join(c.strip() for c in s.strip("|").split("|"))))
            continue
        for part in re.split(r"(?<=。)", s):
            part = part.strip()
            if len(part) >= 6:
                out.append((idx + 1, part))
    return front, out


# ---------------------------------------------------------------- 構造の検査

def known_names(path: pathlib.Path) -> set[str]:
    names: set[str] = set()
    dirs = {CLAUDE / "memory", path.parent}
    for d in dirs:
        if not d.is_dir():
            continue
        for f in d.glob("*.md"):
            names.add(f.stem)
            names.add(f.stem.replace("_", "-"))
            try:
                head = f.read_text(encoding="utf-8")[:600]
            except OSError:
                continue
            m = re.search(r"^name:\s*(\S+)", head, re.M)
            if m:
                names.add(m.group(1))
    return names


def index_texts(given: pathlib.Path) -> str:
    """そのメモリが載るべき索引の本文を返す。"""
    texts = []
    if (CLAUDE / "projects") in given.parents:
        idx = given.parent / "MEMORY.md"
        cands = [idx]
    else:
        cands = [CLAUDE / "MEMORY.md", CLAUDE / "memory" / "communication-index.md"]
    for c in cands:
        try:
            texts.append(c.read_text(encoding="utf-8"))
        except OSError:
            pass
    return "\n".join(texts)


def structure_findings(given: pathlib.Path, text: str, front: dict) -> list[tuple[int, str, str]]:
    found: list[tuple[int, str, str]] = []
    kind = kind_of(given)
    fence = False
    for no, raw in enumerate(text.splitlines(), 1):
        if FENCE.match(raw):
            fence = not fence
            continue
        if fence:
            continue
        raw = INLINE_CODE.sub("", raw)
        if "→" in raw:
            continue
        if "**" in raw:
            found.append((no, "emphasis", "強調の ** を外し、平叙の命令文にする"))
        if re.search(r"\bWhy\b\s*[:：]|How to apply", raw):
            found.append((no, "heading", "Why / How to apply の見出しを消し、ルールの文の箇条書きにする"))
        if raw.lstrip().startswith("|") and "発火" in raw:
            found.append((no, "table", "「発火する事象 | 実行する操作」の表をルールの文の箇条書きにする"))
    if kind == "memory":
        for key in ("name", "description"):
            if not front.get(key):
                found.append((1, "frontmatter", f"frontmatter に {key} を書く"))
        if given.name not in index_texts(given):
            found.append((1, "index", f"{given.name} を索引に 1 行で載せる"))
    if kind in ("memory", "index"):
        names = known_names(given)
        for no, raw in enumerate(text.splitlines(), 1):
            for ref in WIKILINK.findall(INLINE_CODE.sub("", raw)):
                key = ref.strip()
                if key not in names and key.replace("_", "-") not in names:
                    found.append((no, "link", f"[[{key}]] を、実在するメモリの name に書き換える"))
    return found


# ---------------------------------------------------------------- 文の書き方の検査 (Jev)

def questions_digest() -> str:
    try:
        return hashlib.sha1(QUESTIONS.read_bytes()).hexdigest()[:12]
    except OSError:
        return "none"


def cache_file() -> pathlib.Path:
    return STATE_DIR / "memory-style-gate-cache.json"


def load_json(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path: pathlib.Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def ask_jev(sentence: str) -> str | None:
    try:
        proc = subprocess.run(
            [sys.executable, str(JUDGE), str(QUESTIONS)],
            input=sentence, capture_output=True, text=True, timeout=JUDGE_TIMEOUT,
        )
        out = json.loads(proc.stdout or "{}")
    except Exception:
        return None
    if out.get("error"):
        return None
    label = out.get("decision")
    return label if isinstance(label, str) else None


def is_structural(sentence: str) -> bool:
    """書き換えの対応・例示・関連の列挙の行。規則として読まれないので Jev に問わない。"""
    return "→" in sentence or sentence.startswith(("例:", "例：", "関連:", "関連：", "[["))


def fallback_label(sentence: str) -> str:
    if is_structural(sentence):
        return "not_a_rule"
    for label, rx in FALLBACK_PATTERNS:
        if rx.search(sentence):
            return label
    return "prescriptive"


def pass_labels() -> set[str]:
    q = load_json(QUESTIONS)
    return set(q.get("pass_labels") or ["prescriptive", "not_a_rule"])


def style_findings(sentences: list[tuple[int, str]]) -> list[tuple[int, str, str]]:
    sentences = sentences[:MAX_SENTENCES]
    digest = questions_digest()
    cache = load_json(cache_file())
    keyed = [(no, s, digest + ":" + hashlib.sha1(s.encode("utf-8")).hexdigest()) for no, s in sentences]
    for _, s, k in keyed:
        if k not in cache and is_structural(s):
            cache[k] = "not_a_rule"
    todo = sorted({(s, k) for _, s, k in keyed if k not in cache})
    use_jev = JUDGE.is_file() and QUESTIONS.is_file() and os.environ.get("MEMORY_STYLE_GATE_NO_JEV") != "1"
    fresh: dict[str, str] = {}
    if todo and use_jev:
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for (s, k), label in zip(todo, pool.map(lambda t: ask_jev(t[0]), todo)):
                if label:
                    fresh[k] = label
    if fresh:
        cache.update(fresh)
        save_json(cache_file(), cache)
    ok = pass_labels()
    found = []
    for no, s, k in keyed:
        label = cache.get(k) or fallback_label(s)
        if label not in ok:
            found.append((no, label, s))
    return found


# ---------------------------------------------------------------- 返し方

HINT = {
    "conditional": "条件節を外し、適用範囲を目的語の名詞句に入れた言い切りの文にする",
    "prohibitive": "代わりに取る操作を言い切る文にする",
    "rationale": "理由・背景・経緯の文を消し、ルールの文だけを残す",
}


def check_file(given: pathlib.Path) -> list[str]:
    try:
        text = given.read_text(encoding="utf-8")
    except OSError:
        return []
    front, sentences = split_body(text)
    lines = []
    for no, kind, hint in structure_findings(given, text, front):
        lines.append(f"- {no} 行目 ({kind}): {hint}")
    for no, label, sentence in style_findings(sentences):
        short = sentence if len(sentence) <= 80 else sentence[:80] + "…"
        lines.append(f"- {no} 行目 ({label}): {HINT.get(label, '言い切りの命令文にする')}。「{short}」")
    return lines


def block_count_file(session_id: str) -> pathlib.Path:
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_") or "nosession"
    return STATE_DIR / f"memory-style-gate.{safe}.json"


def reason_for(results: dict[str, list[str]]) -> str:
    parts = [
        f"memory-style-gate: 書き換えたルール文書に、{RULE_MEMORY} の書き方から外れた行があります。"
        "その規則を Read で読み、下の行を言い切りの命令文に書き換えてください。意味は保ったまま、形だけを直してください。"
    ]
    for path, lines in results.items():
        parts.append(f"\n{path}")
        parts.extend(lines[:60])
        if len(lines) > 60:
            parts.append(f"- ほか {len(lines) - 60} 行")
    return "\n".join(parts)


def trace(**fields) -> None:
    try:
        TRACE.parent.mkdir(parents=True, exist_ok=True)
        fields["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        with TRACE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fields, ensure_ascii=False) + "\n")
    except OSError:
        pass


def gate(paths: list[pathlib.Path], session_id: str, event: str, agent: str = "") -> int:
    counts_path = block_count_file(session_id)
    counts = load_json(counts_path)
    results: dict[str, list[str]] = {}
    for given in paths:
        real = str(given.resolve())
        lines = check_file(given)
        trace(event=event, agent=agent, path=str(given), findings=len(lines), blocks=counts.get(real, 0))
        if not lines:
            continue
        if counts.get(real, 0) >= MAX_BLOCKS_PER_FILE:
            continue
        counts[real] = counts.get(real, 0) + 1
        results[str(given)] = lines
    if not results:
        return 0
    save_json(counts_path, counts)
    print(json.dumps({"decision": "block", "reason": reason_for(results)}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- 入口

def post_tool_use(payload: dict) -> int:
    if payload.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return 0
    fp = (payload.get("tool_input") or {}).get("file_path") or ""
    if not fp:
        return 0
    given = pathlib.Path(os.path.expanduser(fp))
    if not (is_target(given) or is_target(given.resolve())):
        return 0
    return gate([given], str(payload.get("session_id") or ""), "post_tool_use", str(payload.get("agent_id") or ""))


def roots() -> list[pathlib.Path]:
    out = [CLAUDE / "CLAUDE.md", CLAUDE / "MEMORY.md"]
    out += sorted((CLAUDE / "memory").glob("*.md"))
    out += sorted(CLAUDE.glob("projects/*/memory/*.md"))
    out += sorted(CLAUDE.glob("skills/*/*.md"))
    return [p for p in out if p.exists() and is_target(p)]


def stop(payload: dict) -> int:
    if payload.get("stop_hook_active"):
        return 0
    session_id = str(payload.get("session_id") or "")
    start_file = STATE_DIR / f"{session_id}.start"
    try:
        since = float(start_file.read_text(encoding="utf-8").strip())
    except Exception:
        return 0
    seen: set[str] = set()
    changed = []
    for p in roots():
        try:
            real = p.resolve()
            if str(real) in seen or real.stat().st_mtime < since:
                continue
        except OSError:
            continue
        seen.add(str(real))
        changed.append(p)
    if not changed:
        return 0
    return gate(changed, session_id, "stop")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    try:
        if "--post-tool-use" in sys.argv:
            return post_tool_use(payload)
        if "--stop" in sys.argv:
            return stop(payload)
    except Exception as exc:  # 検査の失敗で作業を止めない
        trace(event="error", error=repr(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
