# 増分 2 の配置と実実行器の確認手順

この文書は人が実施する手順です。認証、実 Codex・実 Claude・jev API の呼び出し、ミニ PC への配置は今回の実装試験では実施していません。コマンドは各機械のリポジトリ直下で実行します。

## 1. ミニ PC への配置

1. 開発 PC から `increment-2` の Git bundle を作り、ミニ PC に転送します。`mini-pc` は実際の SSH 接続先に置き換えます。この方法はブランチの push を必要としません。

   ```sh
   git bundle create /tmp/pda-increment-2.bundle increment-2
   scp /tmp/pda-increment-2.bundle mini-pc:~/pda-increment-2.bundle
   ```

2. Docker Engine と Compose、uv が利用できるミニ PC 上で取得し、Python 環境を作ります。

   ```sh
   git clone --branch increment-2 ~/pda-increment-2.bundle ~/pda
   cd ~/pda
   uv sync --frozen --python 3.12
   umask 077
   cp deploy/.env.example deploy/.env
   "${EDITOR:-vi}" deploy/.env
   ```

   エディタで `ZO_ROOT_USER_EMAIL` と `ZO_ROOT_USER_PASSWORD` を設定します。パスワードはシェルに直接入力しません。`JEV_MODE=fixture` を維持します。5000 番が使用中なら `CONDUCTOR_UI_PORT=15000` などに変更します。

3. 既定のサービスを起動し、定義を登録します。`real` profile はまだ起動しません。

   ```sh
   docker compose -f deploy/docker-compose.yaml up -d --build
   uv run python tools/generate_defs.py --conductor http://localhost:8080 --registry registry/
   ```

   Conductor API は `http://ミニPCのアドレス:8080`、Conductor UI は `http://ミニPCのアドレス:5000`（変更時は指定したポート）、OpenObserve は `http://ミニPCのアドレス:5080` です。OpenObserve には設定した初期ユーザーで入り、Logs の `pda_events` を選びます。実行器はホストにポートを公開しません。

4. 配置先で fixture の受け入れ試験を実行する場合は、次を実行します。試験は `implement.fake-b` の定義と fake-b のモードを一時変更し、終了時に復元します。作業対象の別ジョブを走らせずに実施します。

   ```sh
   uv run ruff check
   uv run pytest tests/unit
   PDA_E2E=1 uv run pytest tests/e2e -v
   ```

## 2. Codex の個人契約の認証

1. ホスト側に Codex CLI を用意し、専用の認証ディレクトリを作ります。既存セッションを利用せず、このディレクトリで個人契約へログインします。

   ```sh
   mkdir -p secrets/codex
   chmod 700 secrets secrets/codex
   "${EDITOR:-vi}" secrets/codex/config.toml
   ```

   `config.toml` に次を設定します。

   ```toml
   cli_auth_credentials_store = "file"
   ```

2. ホスト上でログインし、ブラウザの案内に従って個人アカウントを選びます。

   ```sh
   CODEX_HOME="$PWD/secrets/codex" codex login
   test -f secrets/codex/auth.json
   chmod 600 secrets/codex/auth.json secrets/codex/config.toml
   ```

   Codex は認証情報をファイルまたは OS の資格情報ストアに保存します。ディレクトリのマウントで渡すため、この手順はファイル保存を選びます。GUI のある別ホストでログインした場合は、この専用ディレクトリを SSH 経由でミニ PC の `secrets/codex/` へ転送し、同じ権限を設定します。[OpenAI 公式認証資料](https://learn.chatgpt.com/docs/auth)

3. `deploy/.env` の `CODEX_AUTH_DIR=../secrets/codex` を確認します。Compose ファイルを基準に解決され、コンテナの `/root/.codex` に読み書き可能でマウントされます。コンテナ内の実行ユーザーは root です。認証更新の書き込みが必要なので読み取り専用にはしません。別の既存認証ディレクトリを使う場合は、この値をホスト上の絶対パスに変更します。

## 3. Claude Code の会社契約の認証

1. Linux ホスト側に Claude Code を用意し、専用ディレクトリを指定して起動します。表示されるログイン、または `/login` から会社契約のアカウントを選び、ログイン後に終了します。

   ```sh
   mkdir -p secrets/claude
   chmod 700 secrets/claude
   CLAUDE_CONFIG_DIR="$PWD/secrets/claude" claude
   test -f secrets/claude/.credentials.json
   chmod 600 secrets/claude/.credentials.json
   ```

2. `deploy/.env` の `CLAUDE_AUTH_DIR=../secrets/claude` を確認します。コンテナ内の `/claude-config` に読み書き可能でマウントし、`CLAUDE_CONFIG_DIR=/claude-config` を設定しています。コンテナの root がこのディレクトリを読み書きできる権限にします。

3. macOS のログイン情報は通常 Keychain に保存されるため、設定ディレクトリだけのコピーでは移せません。この手順のファイルマウントを使用する場合は Linux ホストでログインします。`CLAUDE_CONFIG_DIR` を指定した Linux の認証ファイルはそのディレクトリ内に置かれます。会社契約の認証が ACP アダプタで利用できるかは未確認です。[Claude Code 公式認証資料](https://code.claude.com/docs/en/authentication#credential-management)

## 4. jev の API キー

1. キーは対話入力で `secrets/typesafe_credentials` に保存します。入力した値は画面やコマンド履歴へ出しません。

   ```sh
   uv run python - <<'PY'
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
   ```

2. `exec-jev` は `/secrets/typesafe_credentials` として読み取ります。`TYPESAFE_API_KEY` がコンテナに設定されている場合はそちらを優先します。実 API を使うときだけ `deploy/.env` の `JEV_MODE=live` に変更し、`exec-jev` を再作成します。以下の Codex 単独確認では `fixture` を使うため、jev API は呼びません。

## 5. real profile と Codex の implement の確認

1. 認証ディレクトリを用意した後、profile を起動します。

   ```sh
   docker compose -f deploy/docker-compose.yaml --profile real up -d --build
   ```

   Codex は `npx -y @agentclientprotocol/codex-acp`、Claude は `npx -y @agentclientprotocol/claude-agent-acp@preview` で起動します。npm パッケージは指示どおりの指定で、解決される版は固定していません。外向きネットワークには接続しますが、宛先ドメインの制限は掛けていません。

2. `deploy/.env` をエディタで開き、次の値にします。初回の判定だけが `implement.codex-personal` を 1 セル生成し、その後の判定は finish になります。

   ```dotenv
   JEV_MODE=fixture
   PDA_FIXTURE_EXECUTOR=codex-personal
   PDA_FIXTURE_TYPE=implement
   ```

   ```sh
   docker compose -f deploy/docker-compose.yaml up -d --force-recreate exec-jev
   curl -fsS http://localhost:8080/api/workflow \
     -H 'Content-Type: application/json' \
     -d '{"name":"pda_job","version":1,"input":{"initial_input":"/work/hello.py に main 関数を作成し、実行時に hello を表示してください。変更結果を報告してください。"}}'
   ```

3. 返った workflow ID を Conductor UI で開きます。`implement.codex-personal` の出力、`meta.executor_id`、`meta.stop_reason`、ワークフローの `COMPLETED` を確認します。OpenObserve では、その job ID について `job.received` の `pda_agent_mode` が `agent` であることを確認します。`permission.request` が発生したかもここで記録します。`permission.request` が無いことから権限制御が無いとは判断しません。

4. 確認後、`.env` の `PDA_FIXTURE_EXECUTOR` と `PDA_FIXTURE_TYPE` を空に戻し、`exec-jev` を再作成します。

   ```sh
   docker compose -f deploy/docker-compose.yaml up -d --force-recreate exec-jev
   ```

## 6. 判定器の問いの検証

`registry/judge/questions.json` の 4 問と `is_complete=0.7` の閾値は未検証です。人が `jev-verify` に実データを流し、答えと期待値を比較して閾値を決めます。fixture の試験成功は、問いの品質や実 API の判定精度を示しません。
