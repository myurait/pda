# PDA v0.2 増分 3 実装報告

入力は main の `046fb9de9ea0c29d7815da7b262ddc1caeaa88ee`。作業ブランチは increment-3。

## 1. 変えたもの

- 2.1: 公開 OTLP エクスポータと Batch プロセッサに変更し、タスク処理後と終了時に flush する。
- 2.2: Claude を個人契約へ変更し、Codex の full access、認証マウント、Claude settings、全実行器と写しの UID 1000 を設定した。
- 2.3: 判定器から workdir を渡し、ラッパーで作成し、ACP と tools の cwd・プロンプト・出来事に反映した。echo は note.txt を書く。
- 2.4: 結果送信を受信から responseTimeoutSeconds まで 1 秒間隔で再試行し、断念時に result_delivery_failed を記録する。
- 2.5: Collector のログとトレースを別ファイルにし、それぞれ 100 MB・バックアップ 5 にした。
- 2.6: イメージに tools/ を収録し、entrypoint で渡されたコマンドを実行できるようにした。
- 2.7: 動的セルが走った回数が 10 以上なら finish:round_limit を記録して終了する。
- 2.8: 単体試験を追加し、e2e 1〜8 を更新して 9〜12 を追加した。

結果送信は少なくとも 1 回の意味論であり、送信を断念したタスクは Conductor の応答時間切れと再試行により同じセルが再び動き得る。

## 2. 使ったイメージと版、依存パッケージと版

増分 2 からの変更は自作イメージ `pda-executor:increment-3` と `pda-executor-real:increment-3`。ID は [images.json](evidence/increment-3/images.json)。基盤イメージの版、pyproject.toml と uv.lock の依存版は変更していない。npm アダプタは宣言の npx 指定で実行時に解決する。今回の実行は codex-acp 1.13.0 / Codex 0.155.1、claude-agent-acp 0.80.1-preview.2 / Claude Agent SDK 0.3.280。[npm-versions.json](evidence/increment-3/npm-versions.json) に記録した。

## 3. 部品ごとの受け入れ条件の合否と確かめ方

| 条件 | 合否 | 確かめ方 |
|---|---|---|
| 出来事: `_internal` import 無し | 合格 | src の全 Python ファイルを走査する単体試験 |
| 出来事: 公開エクスポータと Batch | 合格 | events.py と HTTP 受信側で OTLP protobuf を復号する単体試験 |
| 出来事: OpenObserve とファイル | 合格 | e2e 2・3、02-events.jsonl と 03-openobserve.json |
| 出来事: 決定的なトレース・スパン ID | 合格 | 単体試験で sha256 の先頭 16/8 バイトと実際の OTLP ID を比較、e2e 2 で照合 |
| 出来事: プロセス終了時の未送信 | 合格 | e2e 2 の shutdown-probe が終了後のログ・トレースファイルに出現。単体試験で終了待ちが 5 秒以内 |
| 実行器の宣言 | 合格 | claude-company を削除、claude-personal を追加。単体試験とコンテナ登録で実行器 6・タスク定義 19 |
| Codex と Claude の権限設定 | 合格 | 宣言・Compose・settings の単体試験。根拠は 5 節 |
| 非 root UID 1000 | 合格 | e2e 8 |
| 作業場所 | 合格 | 単体試験と e2e 1。全動的セルの workdir、note.txt、command.run と job.received の属性を確認。judge の属性は空文字 |
| 結果送信 | 合格 | モックの時間・503 応答で受信時刻からの残り期限、1 秒間隔、回復時の成功、断念時の unknown を確認 |
| Collector | 合格 | 設定の単体試験と e2e 2。events.jsonl と traces.jsonl の分離 |
| 繰り返しの上限 | 合格 | 11 回分の continue fixture を用意し、10 回の動的セル履歴を積んだ次の判定で finish と理由を確認 |
| 起動・期限・停止 | 合格 | ポーリング対象、期限計算、実 ACP の期限停止、実 SIGTERM 後の終了・再ポーリング無しを単体試験 |
| 分類とスキーマ検査 | 合格 | 3 分類・終端失敗・入力と出力の JSON Schema 検査の単体試験、e2e 4・7 |
| ACP・jev・tools の操作役 | 合格 | ACP 実往復、jev API のモック、tools の終了コードと停止を単体試験。権限要求の宣言による応答は維持 |
| 試験用エージェント | 合格 | echo/invalid/slow/permission の実 ACP 単体試験。echo のみ note.txt を作成 |
| 写し | 合格 | 最終取得・再試行・破棄・出所照合の単体試験、e2e 2 |
| compose | 合格 | ネットワーク構成の単体試験、e2e 8 |
| 試験 | 合格（10 は停止補助あり） | ruff 合格、単体 76 件合格、最終イメージで e2e 1〜9 合格。10〜12 の実施条件は 4 節 |

単体試験結果は [unit.txt](evidence/increment-3/unit.txt)、静的検査は [ruff.txt](evidence/increment-3/ruff.txt)。

## 4. e2e 1〜12 の結果

| e2e | 実施 | 結果 | 証拠 |
|---|---|---|---|
| 1 fixture の繰り返しと入力 | 実施 | 合格 | 01-workflow.json、01-workdir.json |
| 2 出来事・出所・終了時 flush | 実施 | 合格 | 02-events.jsonl、02-traces.jsonl |
| 3 OpenObserve SQL | 実施 | 合格 | 03-openobserve.json |
| 4 不正出力 | 実施 | 合格 | 04-invalid-workflow.json、04-invalid-events.jsonl |
| 5 ワーカー消失・再試行 | 実施 | 合格 | 05-retry-workflow.json、05-retry-events.jsonl |
| 6 ランタイム期限 | 実施 | 合格 | 06-deadline-timing.json、06-deadline-workflow.json |
| 7 ワークフロー入力スキーマ | 実施 | 合格 | 07-schema-response.json、07-schema-workflow.json |
| 8 メモリ・ネットワーク・UID・UI | 実施 | 合格 | 08-docker-stats.txt、08-isolation.json、08-uid.json |
| 9 宣言の追加 A2 | 実施 | 合格 | 09-definitions.json、09-workflow.json、09-events.jsonl |
| 10 実 Codex | 実施（1 ジョブ） | COMPLETED、hello 確認。終了処理の補助あり | 10-result.json、10-workflow.json、10-events.jsonl、10-cleanup.json |
| 11 実 Claude | 実施（1 ジョブ） | 合格（補助なし） | 11-result.json、11-workflow.json、11-events.jsonl |
| 12 実行器の比較 A1 | 実施（追加ジョブなし） | 合格（10 の補助ありの記録を使用） | 12-comparison.json |

初回実行の pytest は 12 件合格（435.33 秒）。10 は停止補助ありであり、自律完了の合格とは区別する。ACP 終了処理修正後の最終イメージで e2e 1〜9 を再実施して 9 件合格。11 は修正後のイメージで補助なしで合格した。試験ログは [e2e-initial.txt](evidence/increment-3/e2e-initial.txt) と [e2e-final-fixture.txt](evidence/increment-3/e2e-final-fixture.txt)。

証拠は [evidence/increment-3/](evidence/increment-3/) に抜粋だけ保存した。1 ファイル 300 行以内。出来事は対象 job_id のものだけ。

宣言の追加には判定器 exec-jev の再作成が必要。e2e 9 では追加と削除の両方で再作成した。fake-c の一時コンテナ・宣言・4 定義は試験終了時に削除した。最終確認で定義 19 件、実行中ジョブ 0 件。real の両実行器は停止し、fixture を通常設定へ戻した。

## 5. Codex の権限モードの値と Codex 本体の設定キーの根拠、Claude の権限モードの設定

Codex は `INITIAL_AGENT_MODE=agent-full-access`。[README](https://github.com/agentclientprotocol/codex-acp/blob/main/README.md) と [src/AgentMode.ts](https://github.com/agentclientprotocol/codex-acp/blob/main/src/AgentMode.ts) の AgentFullAccess は承認方針 `never`、サンドボックス `danger-full-access` を定義する。承認とサンドボックスを Codex 本体の config.toml に追加しない。

[OpenAI 公式認証資料](https://learn.chatgpt.com/docs/auth) は `cli_auth_credentials_store="file"` が CODEX_HOME 配下の auth.json を使うことを定めている。手順書では config.toml をこの 1 行にし、Compose は CODEX_HOME=/codex-home を渡す。既存の認証ファイルと config.toml は直接読み書きしておらず、設定の実内容は確認していない。

Claude は [アダプタ README](https://github.com/agentclientprotocol/claude-agent-acp)、[権限拡張 docs](https://github.com/agentclientprotocol/claude-agent-acp/blob/main/docs/permission-extension.md)、[src/settings.ts](https://github.com/agentclientprotocol/claude-agent-acp/blob/main/src/settings.ts)、[src/acp-agent.ts](https://github.com/agentclientprotocol/claude-agent-acp/blob/main/src/acp-agent.ts) を確認した。CLAUDE_CONFIG_DIR の settings.json を読み、permissions.defaultMode を初期 permissionMode に使う。ACP のセッション単位のオプションによる指定もあるが、確認した資料では追加すべき起動引数・専用環境変数は無く、宣言には CLAUDE_CONFIG_DIR のみを追加した。設定値は bypassPermissions。要求がコールバックに届いた場合は従来どおり宣言に応答し、両出来事を残す。

[Claude 公式の実行環境資料](https://code.claude.com/docs/en/sandbox-environments) は Linux/macOS の root で確認なし実行を拒否するとしている。Dockerfile の base で pda（UID 1000）を作り、real の構築に必要なリンク作成だけ root へ戻した後、最終 USER を pda にする。

## 6. 実 Codex と実 Claude の権限要求、stop_reason、出来事の種別

Codex: `agent-full-access`、権限要求 0、stop_reason は `end_turn`。hello.py が存在し、実行出力は hello。出来事の種別は `engine.task`, `input.assembled`, `job.received`, `message.output`, `output.classified`, `tool.call`, `tool.result`, `turn.end`, `unknown`, `usage`。`engine.task` は写し由来で、対象実行器の ID を持つ行も比較に含めた。

Claude: 権限要求 0、stop_reason は `end_turn`。hello.py が存在し、実行出力は hello。出来事の種別は Codex と同一の 10 種。job.received の agent_mode は従来どおり Codex にだけ記録し、Claude にはこの属性が無い。

両者の出来事の種別集合の差は空。Conductor のタスク記録 34 欄、inputData 7 欄、outputData 3 欄、meta 4 欄の集合の差もすべて空。入力欄は cell_id/context/input/job_id/prompt_ref/type/workdir、出力欄は kind/meta/payload、meta は declaration_version/executor_id/stop_reason/trace_id。値の同一性ではなく欄の集合を比較した。根拠は [10-result.json](evidence/increment-3/10-result.json)、[11-result.json](evidence/increment-3/11-result.json)、[12-comparison.json](evidence/increment-3/12-comparison.json)。

## 7. 指示に無かった判断と、指示どおりにできなかったこと

- Compose のプロジェクト名は pda-increment-2 のまま維持し、既存ボリュームとの互換性を保った。自作イメージのタグだけ increment-3 にした。
- 終了処理は SDK の flush と shutdown を daemon スレッドで実行し、呼び出し側は合計 5 秒で待ちを切る。独自の送信キューや HTTP 送信は無い。到達不能時の配送保証は無い。
- 結果配送の期限はポーリングで受信した直後の monotonic 時刻から数える。個々の HTTP 呼び出しも残り時間内に制限する。
- e2e の OpenObserve 照会では .env を直接読む旧処理を削除した。テスト用 Compose サービスへ Compose が環境を注入し、資格情報を出力せず照会する。
- 実 API の試験は各 1 ジョブに限定し、失敗時にも有料処理の再試行を増やさないよう implement 定義の retryCount を試験中だけ 0 にして復元する。e2e 12 は 10・11 の記録を比較する。
- e2e 9 の既存定義比較は登録時刻・登録者の管理欄を除き比較する。定義の内容を比較し、除外欄を証拠に列挙する。
- 実 Codex の end_turn 後、npx の子 node/codex が stderr を保持し、既存の ACP 終了処理が待ち続けた。実行中の同じ 1 ジョブについて残存子に SIGTERM を送り、結果配送を完了させた。10 は補助なしで通ったとは扱わない。追加ジョブは起動していない。
- この問題の修正として、ACP の起動を既存イメージにある setsid で独立したプロセスグループにし、終了時にグループ全体を停止する。子が標準入出力を継承するランチャーの再現試験を追加した。これは実試験で判明した、列挙外の必要な終了処理修正である。使用する setsid は既存の base に含まれる util-linux 2.38.1 で、新たな OS パッケージは追加していない。
- Git の著者設定が無かったため、各コミットで Codex <codex@localhost> を指定した。グローバル設定は変更していない。
- 手順書の uv については、指示 2.6 の「ホストに入れない」と 4.1 の「uv がある」の両経路を扱い、コンテナ登録を主手順、既存 .venv を代替手順とした。

## 8. 未実施のこと

jev の実 API 呼び出しと問い・閾値の検証、会社契約の Claude、人による認証操作・再ログイン、手順書に記した配置・認証ファイル複製は未実施。認証ファイルと deploy/.env を直接読み書きする操作は行っていない。実行器は指定の読み書き可能マウントで認証を利用した。修正後の Codex の追加実ジョブは 1 ジョブ制限に従い未実施。修正後の子プロセス終了は再現単体試験と実 Claude で確認した。
