"""常駐の設定。既定の値に ~/.config/pda-pipeline/config.json を重ねる。"""
import copy
import json
import os
import pathlib

HOME = pathlib.Path.home()
PKG_DIR = pathlib.Path(__file__).resolve().parent.parent

DEFAULTS = {
    "data_dir": str(HOME / ".local/share/pda-pipeline"),
    "socket": os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "pda-pipeline.sock"),
    "python": "/usr/bin/python3",
    "claude_bin": str(HOME / ".local/bin/claude"),
    "claude_config_dir": str(HOME / "pda/secrets/claude"),
    "codex_bin": str(HOME / ".local/bin/codex"),
    "codex_home": None,
    "t3_bin": str(HOME / "spike-t3code/bin/t3"),
    "t3_base_dir": str(HOME / "spike-t3code/home"),
    "roles": {
        "main": {"model": "claude-opus-5-5", "effort": "medium"},
        "worker": {"model": "claude-sonnet-5-5", "effort": "medium"},
        # 報告係は、中のエージェントを差し替えられる。agent に、agents のどれを使うかを書く。
        # timeout_sec は1回の呼び出しを待つ上限、attempts は失敗したときに呼び直す回数を含めた上限、
        # retry_wait_sec は呼び直す前に待つ秒数
        "reporter": {
            "agent": "codex",
            "agents": {
                "claude": {"model": "claude-sonnet-5-5", "effort": "low"},
                "codex": {"model": "gpt-6.2-sol", "effort": "low"},
                # 試験用。reply と document に、返す文を書く。fail は、先に失敗する回数
                "fixed": {},
            },
            "timeout_sec": 300,
            "attempts": 3,
            "retry_wait_sec": 30,
        },
    },
    "worker_models": ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"],
    # reporter_documents が入のとき、資料の HTML は、作業するセッションが渡した材料から、報告係が作る
    "stages": {"reporter": True, "jev": True, "codex": True, "reporter_documents": True},
    "judge": {
        "codex_model": "gpt-6.2-sol",
        "codex_effort": "medium",
        "timeout_sec": 600,
        # 試験用の固定の判定。{"mode": "always_pass" | "always_reject" | "reject_until", "n": 12, "delay": 0}
        "fixed": None,
    },
    "limits": {
        "completion_rejections": 5,
        "reporter_rewrites": 2,
        "codex_rejudge": 1,
        "stop_hook_blocks": 5,
        "claude_procs": 3,
        "codex_procs": 2,
        "tool_result_chars": 3000,
        "tool_log_chars": 100000,
    },
    "notify": {
        "enabled": True,
        "env_file": str(HOME / ".config/claude-login-notify/ntfy.env"),
        "permission_wait_sec": 10,
        "click": "https://pda-web.tailaff53a.ts.net:19114/",
    },
    "jev": {
        "credentials": str(HOME / "pda/secrets/typesafe_credentials"),
        "endpoint": "https://api.typesafe.ai/v1/systemone",
        "model": "jev-latest",
    },
    # オーナーの規約の正本 (norms/) から、役の指示とゲートの問いを組む。切のときは rules.json と roles/ だけを使う。
    # pre_gate_wait_sec は、依頼を受けた時点のゲートを待つ上限で、超えたら書き出しなしで作業を始める
    "norms": {"enabled": True, "pre_gate": True, "pre_gate_wait_sec": 20},
    # 案件の名前からリポジトリを引き当てるときに、台帳のほかに探すディレクトリ
    "project_roots": [str(HOME / "v03/work/projects")],
    # 開発 PC のブリッジ。開発 PC の Claude の返事を待つ上限と、依頼の文の長さの上限
    "bridge": {"timeout_sec": 900, "request_chars": 20000},
    "disallowed_tools": [
        "AskUserQuestion", "PushNotification", "EnterPlanMode", "ExitPlanMode", "ScheduleWakeup",
        "CronCreate", "CronDelete", "CronList", "RemoteTrigger",
    ],
}


def _merge(base, over):
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def load(path=None):
    cfg = copy.deepcopy(DEFAULTS)
    path = pathlib.Path(path or os.environ.get("PDA_PIPELINE_CONFIG") or HOME / ".config/pda-pipeline/config.json")
    if path.is_file():
        _merge(cfg, json.loads(path.read_text(encoding="utf-8")))
    return cfg
