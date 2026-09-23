# 増分 4 の配置・実行・可視化の手順

人が実施する手順。コマンドはミニ PC の `~/pda` で実行する。認証ファイルと `deploy/.env` は Git 管理外に置き、値を引数や履歴へ書かない。

## 1. ミニ PC への配置

承認済みの変更を main に取り込んでから、開発 PC で `git push minipc main`、ミニ PC で次を実行する。

```sh
cd ~/pda
git switch main
git pull --ff-only
uv sync --frozen
free -h
```

メモリの available が 4 GB 以上あることを確かめる。既存の `deploy/.env` はそのまま使う。新規配置時だけ次を実行し、OpenObserve の認証をエディタで設定する。

```sh
umask 077
cp deploy/.env.example deploy/.env
"${EDITOR:-vi}" deploy/.env
```

プロジェクト名は `pda`、自作イメージは `pda-executor:local` と `pda-executor-real:local`。旧プロジェクトのコンテナと名前付きボリュームを削除する。旧実行記録も削除される。

```sh
docker compose -f deploy/docker-compose.yaml -p pda-increment-2 --profile real down -v
nice docker compose -f deploy/docker-compose.yaml up -d --build
docker compose -f deploy/docker-compose.yaml run --rm --no-deps exec-tools python /app/tools/generate_defs.py --conductor http://conductor-server:8080 --registry /registry
```

認証は次節以降で準備する。登録はタスク定義 19、ワークフロー定義 1 で、繰り返し実行できる。ホストから登録する場合は次を使う。

```sh
.venv/bin/python tools/generate_defs.py --conductor http://localhost:8080 --registry registry
```

宣言を追加したら再登録し、`exec-jev` を再作成する。実行器・写し・可視化は UID 1000 で動く。認証ディレクトリは UID 1000 がアクセスできる所有者・権限にする。

Conductor API は 8080、UI は 5000（`CONDUCTOR_UI_PORT` で変更可能）、OpenObserve は 5080、可視化は 5081。出来事は OpenObserve の `pda_events` と Collector の `/var/lib/pda/events/events.jsonl`、トレースは `traces.jsonl` に保存する。ファイルは各 100 MB、バックアップ 5。

## 2. Codex の個人契約の認証

ミニ PC のホストでは個人契約でログイン済みとする。ホストの `~/.codex` 全体は履歴やキャッシュを含むため直接マウントしない。認証ファイルだけ複製する。

```sh
umask 077
mkdir -p secrets/codex
chmod 700 secrets secrets/codex
cp ~/.codex/auth.json secrets/codex/auth.json
chmod 600 secrets/codex/auth.json
printf '%s\n' 'cli_auth_credentials_store = "file"' > secrets/codex/config.toml
chmod 600 secrets/codex/config.toml
sudo chown -R 1000:1000 secrets/codex
```

`config.toml` は上の 1 行だけ。承認方針やサンドボックスの設定は不要。宣言の `INITIAL_AGENT_MODE=agent-full-access` をアダプタが各ターンの `never` と `danger-full-access` に写す。

`CODEX_AUTH_DIR` の既定は `../secrets/codex`。Compose は `/codex-home` に読み書きでマウントし、`CODEX_HOME=/codex-home` を渡す。トークン更新は `secrets/codex/auth.json` に保存され、ホスト側に戻す必要は無い。再ログインは [公式認証資料](https://learn.chatgpt.com/docs/auth) に従う。

## 3. Claude Code の個人契約の認証

ミニ PC のホストでは個人契約でログイン済みとする。

```sh
umask 077
mkdir -p secrets/claude
chmod 700 secrets/claude
cp ~/.claude/.credentials.json secrets/claude/.credentials.json
chmod 600 secrets/claude/.credentials.json
sudo chown -R 1000:1000 secrets/claude
```

`CLAUDE_AUTH_DIR` の既定は `../secrets/claude`。`/claude-config` に読み書きでマウントする。`settings.json` は複製しない。Compose が `deploy/executors/claude-settings.json` を読み取り専用でマウントし、`permissions.defaultMode: bypassPermissions` を設定する。宣言の `CLAUDE_CONFIG_DIR=/claude-config` をアダプタが使い、この設定を起動時の権限モードに適用する。

再ログインが必要な場合はコンテナで CLI を起動し、表示された案内に従ってコードを貼る。

```sh
docker compose -f deploy/docker-compose.yaml --profile real run --rm --no-deps exec-claude-personal npx -y @anthropic-ai/claude-code
```

[公式認証資料](https://code.claude.com/docs/en/authentication) を参照する。Linux ホストの UID は 1000。root では確認なし実行が拒否されるため通常の実行ユーザーを変更しない。

## 4. jev の API キーと切り替え

キーは対話入力で保存する。値をコマンドや画面に出さない。

```sh
.venv/bin/python - <<'PY'
import getpass
import os
from pathlib import Path
os.umask(0o077)
directory = Path("secrets")
directory.mkdir(exist_ok=True)
target = directory / "typesafe_credentials"
target.write_text("API_KEY=" + getpass.getpass("TypeSafe API key: ") + "\n")
target.chmod(0o600)
PY
sudo chown 1000:1000 secrets/typesafe_credentials
```

`exec-jev` は `/secrets/typesafe_credentials` を読む。`TYPESAFE_API_KEY` があれば優先する。実 jev を使うと費用が掛かる。個人実行器を準備してから切り替える。

```sh
free -h
nice docker compose -f deploy/docker-compose.yaml --profile real up -d --build exec-codex-personal exec-claude-personal
JEV_MODE=live docker compose -f deploy/docker-compose.yaml up -d --force-recreate exec-jev
```

直近 60 秒にポーリングした実行器だけを可用とする。選ばれた実行器が可用でないか type 非対応なら、宣言ファイル名順の可用な対応実行器に置き換える。候補がなければ finish になる。置き換えは `judge.answer` に記録される。

試験時だけ `PDA_MAX_ROUNDS=2` などを同じ compose コマンドの環境に渡して上限を上書きできる。通常は正本の 10 回。fixture に戻すには次を実行する。`.env` 自体は編集しない。

```sh
JEV_MODE=fixture PDA_MAX_ROUNDS= docker compose -f deploy/docker-compose.yaml up -d --force-recreate exec-jev
docker compose -f deploy/docker-compose.yaml --profile real stop exec-codex-personal exec-claude-personal
```

## 5. 判定器の問いを検証する道具

1 回の実行につき実 jev を 1 回呼ぶ。API キーの取得順は環境変数、`secrets/typesafe_credentials`。仕事 ID、または `input` と `tasks` を含むワークフローの JSON 抜粋を指定する。

```sh
.venv/bin/python tools/judge_probe.py --job-id JOB_ID
.venv/bin/python tools/judge_probe.py --workflow-file workflow.json
.venv/bin/python tools/judge_probe.py --workflow-file workflow.json --initial-input '検証対象の初期入力' --conductor http://localhost:8080 --registry registry
```

`state_summary` は回数、前の回の出力数、取得できた場合だけ可用な実行器の一覧を含む。`answers` は is_complete、next_type、executor、cell_count の実際の応答、`elapsed_ms` は API 呼び出しの所要時間。choice の confidence と、is_complete の noul の値を見て、問いと閾値を人が決める。道具は閾値を適用せず合否を決めない。Conductor に到達できない場合もファイルからの検証は可用性を省略して実行する。

## 6. 可視化を開く

LAN では `http://192.168.0.59:5081`。仕事を選ぶとセルと出来事が現れ、セルを再度選ぶと絞り込みが解除される。3 秒ごとに更新する。

スマートフォンでは同じ tailnet に接続する。ミニ PC の `~/.local/bin/tailscale-pda serve --help` で `--bg`、`--https`、status、reset を確認した。以下は人が実施する設定手順であり、今回の実装作業では実行していない。

```sh
~/.local/bin/tailscale-pda serve status
~/.local/bin/tailscale-pda serve --bg --https=443 http://127.0.0.1:5081
~/.local/bin/tailscale-pda serve status
```

`https://pda-web.tailaff53a.ts.net/` を開く。既存設定の撤去が必要な場合は、status で確認してから `tailscale-pda serve reset` を実行して再設定する。Serve は tailnet 内への公開。

単独起動は `python -m pda_view`。環境変数は `CONDUCTOR_URL`、`OPENOBSERVE_URL`（既定 `http://openobserve:5080`）、`ZO_ROOT_USER_EMAIL`、`ZO_ROOT_USER_PASSWORD`、`OPENOBSERVE_STREAM`（既定 `pda_events`）、`PDA_VIEW_PORT`（既定 5081）。compose は `deploy/.env` の認証を渡す。

## 7. 検証

```sh
.venv/bin/ruff check
nice .venv/bin/pytest tests/unit
free -h
PDA_E2E=1 nice .venv/bin/pytest tests/e2e/test_increment_3.py -v -k 'not test_10 and not test_11 and not test_12'
```

e2e 13 は実 jev 最大 3 回（判定器 2 回と道具 1 回）、セル最大 6 個。全タスク定義の再試行を一時的に 0 にして復元する。実行中の別の仕事がないときだけ行う。10〜12 は今回実行しない。証拠は `docs/reports/evidence/increment-4/`。試験は定義と fixture を変更して終了時に戻す。10〜11 を明示的に選ぶ場合は個人実行器の追加の費用が掛かる。

## 8. 会社契約の Claude

範囲外。組織の権限制御の実機観測と、人が承認できる待機状態・受け皿・画面を用意してから接続する。
