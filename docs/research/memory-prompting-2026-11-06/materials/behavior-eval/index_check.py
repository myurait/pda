"""索引の行の説明がメモリの description と同じ文字列かを数える。

使い方: python3 index_check.py out/r3/reflection/with3 ...
"""
import pathlib
import re
import sys

for d in sys.argv[1:]:
    ok = 0
    n = 0
    for p in sorted(pathlib.Path(d).glob("*.txt")):
        t = p.read_text()
        n += 1
        m = re.search(r"^description:\s*(.+)$", t, re.M)
        lines = re.findall(r"^- \[.*?\]\(.*?\)\s*[—-]+\s*(.+)$", t, re.M)
        if m and any(l.strip() == m.group(1).strip() for l in lines):
            ok += 1
    print(f"{d}: {ok}/{n}")
