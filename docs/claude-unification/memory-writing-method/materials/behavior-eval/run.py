"""メモリの有り無しで Sonnet に同じ依頼を送り、出力を保存する。

使い方:
  python3 run.py --out out/r1 --reps 5 --scenarios reflection,instructed \
      --arm base --arm with=../../../memory/feedback_memory_writing_rules.md \
      [--ablate ../../../memory/feedback_memory_writing_rules.md]
"""
import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
EMPTY = pathlib.Path(tempfile.mkdtemp(prefix="memeval-cwd-"))


def body_lines(path):
    text = pathlib.Path(path).read_text()
    return text.splitlines()


def system_prompt(memory_text):
    base = (HERE / "base_context.md").read_text()
    if memory_text is None:
        return base
    return base + "\n\n# 読み込まれているメモリ\n\n" + memory_text


def call(prompt, sysprompt):
    cmd = [
        "claude", "-p", "--safe-mode", "--tools", "", "--model", "sonnet",
        "--no-session-persistence", "--system-prompt", sysprompt, prompt,
    ]
    r = subprocess.run(cmd, cwd=EMPTY, capture_output=True, text=True, timeout=600)
    return r.stdout.strip() if r.returncode == 0 else "ERROR: " + r.stderr[-2000:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--scenarios", required=True)
    ap.add_argument("--arm", action="append", default=[])
    ap.add_argument("--ablate")
    ap.add_argument("--skip-section", action="append")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    scen = json.loads((HERE / "scenarios.json").read_text())
    arms = {}
    for spec in a.arm:
        if spec == "base":
            arms["base"] = None
        else:
            name, path = spec.split("=", 1)
            arms[name] = pathlib.Path(path).read_text()
    if a.ablate:
        lines = body_lines(a.ablate)
        in_fm = 0
        section = ""
        for i, line in enumerate(lines):
            if line.strip() == "---":
                in_fm += 1
                continue
            if line.startswith("## "):
                section = line[3:].strip()
                continue
            if section in (a.skip_section or []):
                continue
            if in_fm >= 2 and line.lstrip().startswith("- "):
                arms[f"ablate{i + 1:02d}"] = "\n".join(lines[:i] + lines[i + 1:])
        (pathlib.Path(a.out)).mkdir(parents=True, exist_ok=True)
        (pathlib.Path(a.out) / "ablate_map.json").write_text(json.dumps(
            {k: lines[int(k[6:]) - 1] for k in arms if k.startswith("ablate")},
            ensure_ascii=False, indent=1))

    jobs = []
    for s in a.scenarios.split(","):
        for arm, mem in arms.items():
            for rep in range(a.reps):
                dest = pathlib.Path(a.out) / s / arm / f"{rep}.txt"
                if dest.exists():
                    continue
                jobs.append((s, arm, mem, dest))

    def run(job):
        s, arm, mem, dest = job
        out = call(scen[s]["prompt"], system_prompt(mem))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(out)
        return dest

    with cf.ThreadPoolExecutor(a.workers) as ex:
        for d in ex.map(run, jobs):
            print(d, flush=True)


if __name__ == "__main__":
    main()
