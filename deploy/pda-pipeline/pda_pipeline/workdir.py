"""セッションの作業ディレクトリ。絶対パスへの解決と、そのディレクトリのAI向けの指示を役の指示のあとに重ねる文。"""
import os

INSTRUCTION_FILES = ("CLAUDE.md", ".claude/CLAUDE.md", "AGENTS.md")
MAX_CHARS = 30000

HEAD = "## いまの作業ディレクトリ\n\n`{cwd}`\n"
REPO_HEAD = ("## 作業ディレクトリのリポジトリの指示\n\n"
             "次は、作業ディレクトリに置かれたAI向けの指示です。リポジトリの都合として、ここまでの指示の上に重ねて従います。"
             "ここまでの指示と食い違うところは、ここまでの指示に従います。\n")


def resolve(path, base):
    path = os.path.expanduser(path.strip())
    if not os.path.isabs(path):
        path = os.path.join(base, path)
    return os.path.realpath(path)


def repo_root(cwd):
    here = cwd
    while True:
        if os.path.exists(os.path.join(here, ".git")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def instruction_files(cwd):
    dirs = [d for d in (repo_root(cwd), cwd) if d]
    found = []
    for d in dict.fromkeys(dirs):
        for name in INSTRUCTION_FILES:
            path = os.path.join(d, name)
            if os.path.isfile(path):
                found.append(path)
    return found


def notes(cwd):
    out, left = [HEAD.format(cwd=cwd)], MAX_CHARS
    files = instruction_files(cwd)
    if files:
        out.append(REPO_HEAD)
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read(left)
        except OSError:
            continue
        left -= len(text)
        out.append(f"### {path}\n\n{text}")
        if left <= 0:
            break
    return "\n".join(out)
