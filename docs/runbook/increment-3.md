# 増分 3 の配置と個人契約の実行器の確認手順

人が実施する手順。コマンドは特記がなければミニ PC の `~/pda` で実行する。認証ファイルや `.env` は Git に追加しない。秘密情報をコマンド引数や履歴へ書かない。

## 1. ミニ PC への配置

リポジトリはミニ PC の `~/pda.git`（bare）と `~/pda`（作業用）。承認済みの変更を main に取り込んだ後、開発 PC から送る。

```sh
git push minipc main
```

ミニ PC で main を取得する。Docker 29 と Compose v5 を使う。ホスト Python の経路を使う場合は uv と同期済み `.venv` が必要。コンテナ経由の登録にはホストの uv は不要。

```sh
cd ~/pda
git switch main
git pull --ff-only
free -h
```

`available` が 4 GB 以上あることを確かめる。ホスト環境を作り直す場合だけ `uv sync --frozen` を実行する。既存の `deploy/.env` があればそのまま使い、新規配置の場合だけ次を行う。

```sh
umask 077
cp deploy/.env.example deploy/.env
"${EDITOR:-vi}" deploy/.env
```

OpenObserve の初期ユーザーとパスワードはエディタで設定する。`JEV_MODE=fixture` を維持する。5000 番が使用中なら `CONDUCTOR_UI_PORT` を空きポートへ変更する。認証の準備（2〜4 節）の後、起動・登録する。

```sh
nice docker compose -f deploy/docker-compose.yaml up -d --build
docker compose -f deploy/docker-compose.yaml run --rm --no-deps exec-tools python /app/tools/generate_defs.py --conductor http://conductor-server:8080 --registry /registry
```

ホストの Python を使う場合も登録できる。

```sh
.venv/bin/python tools/generate_defs.py --conductor http://localhost:8080 --registry registry
```

タスク定義は 19、ワークフロー定義は 1。登録は繰り返せる。実行器の宣言を追加したら再登録し、起動時に正本を読む判定器も再作成する。

```sh
docker compose -f deploy/docker-compose.yaml up -d --force-recreate exec-jev
```

Conductor API は 8080、UI は 5000（変更した場合は指定ポート）、OpenObserve は 5080。OpenObserve の Logs で `pda_events` を選ぶ。ログは Collector の `/var/lib/pda/events/events.jsonl`、トレースは `traces.jsonl`。両方 100 MB、バックアップ 5。Compose のプロジェクト名は既存ボリュームを継続するため `pda-increment-2` のまま。

増分 2 で root が作った作業ボリュームを再利用する場合は、実行中の PDA ジョブが無い状態で所有者を直す。

```sh
docker compose -f deploy/docker-compose.yaml run --rm --no-deps --user 0 exec-tools chown -R 1000:1000 /work
```

実行器と写しは UID 1000 の `pda` で動く。`secrets/` 配下、および `.env` の `CODEX_AUTH_DIR`、`CLAUDE_AUTH_DIR` が指すディレクトリは UID 1000 の所有にする。別ディレクトリを使う場合は、その実パスにも同じ所有者設定を行う。

```sh
sudo chown -R 1000:1000 secrets
```

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

## 4. jev の API キー

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

`exec-jev` は `/secrets/typesafe_credentials` を読む。`TYPESAFE_API_KEY` が設定されていればそちらを優先する。実 API を使うときだけ `.env` の `JEV_MODE=live` に変更して `exec-jev` を再作成する。以下の確認は fixture を使い、jev API を呼ばない。

## 5. 実 Codex と実 Claude の implement の確認

外部 API の費用が掛かる。1 実行器につき仕事は 1 つとする。

```sh
free -h
nice docker compose -f deploy/docker-compose.yaml --profile real up -d --build
docker compose -f deploy/docker-compose.yaml exec exec-fake-a id -u
```

UID が 1000 であることを確認する。npm アダプタは宣言どおり npx で取得するため版は固定していない。外向きネットワークは宛先ドメインで制限していない。

自動の e2e 10〜12 を人が実行する場合は次のとおり。判定器の fixture を環境変数で一時差し替え、各 implement を 1 回だけ動かす。認証失敗時の自動再試行はこの試験だけ無効化し、終了時に元へ戻す。12 は同じ実行結果を比較し、新たな仕事は起動しない。他の PDA ジョブが無いときに実行する。

```sh
PDA_E2E=1 nice .venv/bin/pytest tests/e2e/test_increment_3.py -v -k 'test_10 or test_11 or test_12'
```

初期入力は「作業ディレクトリに hello.py を作り、実行すると hello と表示するようにせよ。作ったファイル名を報告せよ」。Conductor UI で `implement.codex-personal` と `implement.claude-personal` の `COMPLETED`、出力の `meta.stop_reason` を確認する。各 job ID について `/work/jobs/<job_id>/hello.py` が存在し、実行すると hello になることを確かめる。出来事では `job.received` の `pda.workdir`、Codex の `pda.agent_mode=agent-full-access`、`permission.request` の有無、`turn.end` の `pda.stop_reason` を確認する。

全試験を行う場合は以下。e2e は定義と fixture を一時変更し復元する。証拠出力先は `docs/reports/evidence/increment-3/`。

```sh
.venv/bin/ruff check
nice .venv/bin/pytest tests/unit
free -h
PDA_E2E=1 nice .venv/bin/pytest tests/e2e -v
```

## 6. 判定器の問いの検証

4 問と `is_complete=0.7` の閾値は未検証。人が `jev-verify` に実データを流し、答えと期待値を比較して閾値を決める。fixture の成功は問いの品質や実 API の精度を示さない。動的セルが走った回が 10 に達すると、次の判定は `finish:round_limit` で終了する。

## 7. 会社契約の Claude

範囲外。基本設計 10.1.1 の決定により、組織の権限制御の実機観測と、人が承認できる待機状態・受け皿・画面を用意してから接続する。
