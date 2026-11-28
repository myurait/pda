"""claude・codex を起こすときの環境変数を、セットのファイル (env/<セットの名前>.json) から組む。

    python3 deploy/pda-pipeline/pda_pipeline/envset.py <セット> [--launch 名前=値 ...] [--show] -- <コマンド> ...

常駐プロセスが組むのと同じ環境で、コマンドを 1 回起こす。--show は、組んだ環境を出して終わる。
開発 PC のブリッジ (dev-pc/pda-bridge) は、同じ処理を自分の中に持つ。直すときは両方を直す。
"""
import json
import os
import pathlib
import re
import sys

PKG_DIR = pathlib.Path(__file__).resolve().parent.parent
ENV_DIR = PKG_DIR / "env"
FIELDS = ("set", "inherit", "config", "launch")
NAME = re.compile(r"^[A-Za-z0-9_-]+$")
VAR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EnvSetError(RuntimeError):
    pass


def load_set(name, env_dir=ENV_DIR):
    """セットのファイルを取得し、形を確かめて返す。"""
    if not NAME.match(str(name)):
        raise EnvSetError(f"セットの名前が正しくない: {name!r}")
    path = pathlib.Path(env_dir, f"{name}.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EnvSetError(f"セット {name} を取得できない: {exc}") from None
    if not isinstance(data, dict) or set(data) - {"description", *FIELDS}:
        raise EnvSetError(f"セット {name} の欄が正しくない")
    fixed, inherit = data.get("set") or {}, data.get("inherit") or []
    config, launch = data.get("config") or {}, data.get("launch") or []
    if not (isinstance(fixed, dict) and isinstance(inherit, list) and isinstance(config, dict)
            and isinstance(launch, list)):
        raise EnvSetError(f"セット {name} の欄の形が正しくない")
    for var, entry in fixed.items():
        if not (isinstance(entry, dict) and isinstance(entry.get("value"), str) and set(entry) <= {"value", "effect"}):
            raise EnvSetError(f"セット {name} の {var} の値が正しくない")
    if not all(isinstance(key, str) and key for key in config.values()):
        raise EnvSetError(f"セット {name} の config の設定のキーが正しくない")
    names = [*fixed, *inherit, *config, *launch]
    bad = [n for n in names if not (isinstance(n, str) and VAR.match(n))]
    if bad:
        raise EnvSetError(f"セット {name} の変数の名前が正しくない: {bad}")
    twice = sorted({n for n in names if names.count(n) > 1})
    if twice:
        raise EnvSetError(f"セット {name} で、同じ変数が 2 つの欄にある: {twice}")
    return {"set": fixed, "inherit": inherit, "config": config, "launch": launch}


def build(name, cfg, launch=None, environ=None, env_dir=ENV_DIR):
    """セットから、子プロセスに渡す環境を空の状態から組んで返す。組めないときは EnvSetError を投げる。"""
    spec = load_set(name, env_dir)
    environ = os.environ if environ is None else environ
    launch = dict(launch or {})
    missing = sorted(set(spec["launch"]) - set(launch))
    extra = sorted(set(launch) - set(spec["launch"]))
    if missing or extra:
        raise EnvSetError(f"セット {name} の launch の変数が合わない (渡されていない: {missing}、セットに無い: {extra})")
    env = {var: entry["value"] for var, entry in spec["set"].items()}
    env.update({var: environ[var] for var in spec["inherit"] if var in environ})
    for var, key in spec["config"].items():
        value = (cfg or {}).get(key)
        if value is not None and value != "":
            env[var] = str(value)
    env.update({var: str(value) for var, value in launch.items()})
    return env


def main(argv):
    sys.path.insert(0, str(PKG_DIR))
    from pda_pipeline import config  # noqa: E402

    if "--" not in argv and "--show" not in argv:
        print(__doc__, file=sys.stderr)
        return 2
    head, cmd = (argv[:argv.index("--")], argv[argv.index("--") + 1:]) if "--" in argv else (argv, [])
    show = "--show" in head
    head = [a for a in head if a != "--show"]
    launch = {}
    while "--launch" in head:
        i = head.index("--launch")
        var, _, value = head[i + 1].partition("=")
        launch[var] = value
        del head[i:i + 2]
    if len(head) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    env = build(head[0], config.load(), launch)
    if show or not cmd:
        print(json.dumps(env, ensure_ascii=False, indent=1, sort_keys=True))
        return 0
    os.execvpe(cmd[0], cmd, env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
