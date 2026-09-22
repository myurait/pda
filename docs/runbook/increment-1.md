# PDA v0.2 増分1の手順

ここに記載した認証、実 Codex・実 Claude の実行、jev の実データ検証は開発試験では実施していません。コマンドはリポジトリのルートから実行します。Python は3.12、依存は `uv.lock` に固定されています。

## 1. ミニ PC への配置

1. Docker Engine と Compose、uv を用意し、このリポジトリの `increment-1` ブランチを取得します。
   ```sh
   git clone --branch increment-1 <このリポジトリのURL> pda
   cd pda
   uv sync --frozen --python 3.12
   mkdir -p secrets
   chmod 700 secrets
   cp deploy/.env.example deploy/.env
   chmod 600 deploy/.env
   ```
2. `deploy/.env` の `ZO_ROOT_USER_EMAIL` と `ZO_ROOT_USER_PASSWORD` を設定します。`OPENOBSERVE_AUTH` は同じメールアドレスとパスワードの Basic 認証値です。以下は認証値を画面に表示せず、`.env` に書き込みます。例の値を実際の値に置き換えた後で実行してください。
   ```sh
   uv run python - <<'PY'
   import base64
   from pathlib import Path
   p = Path('deploy/.env')
   lines = p.read_text().splitlines()
   env = dict(line.split('=', 1) for line in lines if line and not line.startswith('#'))
   token = base64.b64encode((env['ZO_ROOT_USER_EMAIL'] + ':' +
                            env['ZO_ROOT_USER_PASSWORD']).encode()).decode()
   p.write_text('\n'.join('OPENOBSERVE_AUTH=Basic ' + token
                          if line.startswith('OPENOBSERVE_AUTH=') else line
                          for line in lines) + '\n')
   PY
   ```
3. fixture 構成を起動し、定義を登録します。定義の登録は繰り返し実行できます。
   ```sh
   docker compose -f deploy/docker-compose.yaml up -d --build
   uv run python tools/generate_defs.py --conductor http://localhost:8080 --registry registry/
   ```
4. Conductor UI は `http://<ミニPC>:5000`、API は `http://<ミニPC>:8080`、OpenObserve は `http://<ミニPC>:5080` です。OpenObserve は `.env` で設定したユーザーでログインし、ログストリーム `pda` の `pda_job_id` で検索します。Mac の Control Center が5000番を使用している場合だけ、`.env` に `CONDUCTOR_UI_PORT=15000` を追加できます。
5. fixture の実行は次のとおりです。`verify.test` は共有ボリューム `/work` で `pytest -q` を実行するため、仕事のファイルとテストを先に配置します。テストが存在しなければ pytest は終了コード5を返し、その結果が成果に残ります。
   ```sh
   curl -fsS http://localhost:8080/api/workflow \
     -H 'Content-Type: application/json' \
     -d '{"name":"pda_job","version":1,"input":{"initial_input":"README を要約せよ","context":{}}}'
   ```
6. 開発用の全試験は次のとおりです。e2e は fake-b と jev を一時的に再作成し、試験後に既定設定へ戻します。他の仕事を走らせていない fixture 環境で実施します。e2e は `/work/pda_e2e_fixture/` にサンプルを作成し、`docs/reports/evidence/increment-1/` に結果を保存します。
   ```sh
   uv run ruff check
   uv run pytest tests/unit
   PDA_E2E=1 uv run pytest tests/e2e -v
   ```

## 2. Codex 個人契約の認証

1. ホスト側で Codex CLI を用意して `codex login` を実行します。個人契約でログインした認証ディレクトリを使用します。認証操作をラッパーは代行しません。
2. `deploy/.env` に `CODEX_AUTH_DIR=/絶対パス/個人契約のcodex設定ディレクトリ` を設定します。コンテナ内のマウント先は `/root/.codex` です。ホスト上のディレクトリは所有者だけが読める700、認証ファイルは600を目安にし、UID 0で動くコンテナから読み書きできる状態にします。トークン更新があるためマウントは読み書き可能です。認証ファイルをリポジトリへコピーしないでください。
3. 実行するコマンドは宣言どおり `npx -y @agentclientprotocol/codex-acp`、`INITIAL_AGENT_MODE=agent` です。認証情報がアダプタから利用できることは実機で確認します。

## 3. Claude Code 会社契約の認証

1. ホスト側で会社契約に対応する設定ディレクトリを指定して `claude` を起動し、ログインを済ませます。
   ```sh
   CLAUDE_CONFIG_DIR=/絶対パス/会社契約のclaude設定ディレクトリ claude
   ```
2. `deploy/.env` に `CLAUDE_AUTH_DIR=/絶対パス/会社契約のclaude設定ディレクトリ` を設定します。コンテナでは `/claude-config` に読み書き可能でマウントし、`CLAUDE_CONFIG_DIR=/claude-config` を設定します。ディレクトリ700、認証ファイル600を目安にし、コンテナから読めることを確認します。ホストの認証がキーチェーンだけに保存されている場合、ディレクトリのマウントだけで利用できるかは未確認です。
3. 実行するコマンドは `npx -y @agentclientprotocol/claude-agent-acp@preview` です。

## 4. jev の API キー

1. `secrets/typesafe_credentials` を作成し、1行で `API_KEY=<実際のキー>` を書きます。ファイルの権限を600にします。
   ```sh
   chmod 600 secrets/typesafe_credentials
   ```
2. `/secrets/typesafe_credentials` に読み取り専用でマウントされます。プロセスの環境変数 `TYPESAFE_API_KEY` があればそちらを優先します。通常の compose はファイルを使用します。
3. 実 API を使うときだけ `.env` の `JEV_MODE=fixture` を `JEV_MODE=api` に変更し、`exec-jev` を再作成します。fixture では API を呼びません。

## 5. profile real と実 Codex の確認

1. 認証の準備後、real profile を起動します。実行器はホストへポートを公開しません。
   ```sh
   docker compose -f deploy/docker-compose.yaml --profile real up -d --build
   ```
2. jev は fixture のままにし、最初のセルを Codex の implement 一つに固定して再作成します。
   ```sh
   PDA_FIXTURE_EXECUTOR=codex-personal PDA_FIXTURE_TYPE=implement \
     docker compose -f deploy/docker-compose.yaml up -d --no-deps exec-jev
   curl -fsS http://localhost:8080/api/workflow \
     -H 'Content-Type: application/json' \
     -d '{"name":"pda_job","version":1,"input":{"initial_input":"/work/hello.py に hello と表示するPythonコードを作成してください","context":{}}}'
   ```
3. 返ったワークフローIDを Conductor UI で開き、`implement.codex-personal` の `COMPLETED`、`outputData.meta.executor_id`、`meta.stop_reason`、共有ボリュームのファイルを確認します。OpenObserve では同じ `pda_job_id` の `job.received`、`tool.call`、`turn.end`、`output.classified` を確認します。権限要求が来た場合だけ `permission.request` と `permission.response` が出ます。`job.received` の `pda.agent_mode` には起動設定を記録します。
4. 確認後、fixture のセル指定を戻します。
   ```sh
   PDA_FIXTURE_EXECUTOR= docker compose -f deploy/docker-compose.yaml up -d --no-deps exec-jev
   ```

## 6. 判定器の問いの検証

`registry/judge/questions.json` の問いは英語、state は日本語のままです。`is_complete` の0.7は仮の閾値で、未検証です。`jev-verify` に実際の初期入力・直前出力・実行器の宣言を state として渡し、返る4問の答えを確認してから閾値を決めます。この実データ検証は今回実施していません。
