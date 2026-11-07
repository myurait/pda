#!/usr/bin/env python3
"""ルール文書から、言い切り以外の書き方 (条件・禁止・理由・強調) の候補を行単位で拾う。

使い方: python3 check_rule_style.py <ファイル>...
出力: <ファイル>:<行番号>:<拾った語>:<行>  / 末尾に件数。件数 0 で終了コード 0。
フェンスで囲んだコードブロックと、書き換えの対応を述べる行 (「→」を含む行) は対象外。
"""
import re
import sys

PATTERNS = [
    ("条件", r"とき|時に|場合|ならば|なら[、。\s]|たら[、。\s]|れば[、。\s]|もし|際に|際は|If |if |when |When "),
    ("禁止", r"しない|ない[。、）)]|ないこと|禁止|禁ず|許されない|してはならない|べからず|NEVER|Never |never |Don't|don't|Do not|do not|DO NOT"),
    ("理由", r"ため[。、に]|ためである|からである|から[、。]|なぜなら|理由は|Why:|Why\b|because|Because"),
    ("強調", r"MUST|必ず|絶対|\*\*|IMPORTANT|CRITICAL"),
    ("見出し", r"How to apply"),
]
COMPILED = [(k, re.compile(p)) for k, p in PATTERNS]
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def scan(path):
    hits = []
    in_fence = False
    with open(path, encoding="utf-8") as f:
        for no, line in enumerate(f, 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence or "→" in line:
                continue
            for kind, rx in COMPILED:
                m = rx.search(line)
                if m:
                    hits.append((path, no, f"{kind}:{m.group(0).strip()}", line.rstrip()))
    return hits


def main():
    total = 0
    for p in sys.argv[1:]:
        for path, no, kind, line in scan(p):
            print(f"{path}:{no}:{kind}:{line}")
            total += 1
    print(f"TOTAL {total}")
    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
