# PDA Current-State Hardening and Context Spine Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 現在の「常時稼働するHermes＋Claude Code接続実証」を、復元可能・監査可能・ランタイム非依存なPDAへ進めるため、まず安全なPhase 4進入条件を満たし、Hermes履歴から出典付きContext Packを生成してHermesとClaude Codeが共有できる最小垂直スライスを成立させる。

**Architecture:** PDAの正本はHermesの組み込みmemoryや特定memory providerではなく、Hermes外に置くappend-onlyなイベント台帳とする。各情報源はConnectorで台帳へ取り込み、claim・関係・Context Packは再構築可能な投影として生成し、共通stdio MCPを通じて交換可能な各ランタイムへ供給する。既製memory providerは承認済みclaimだけを流す補助キャッシュとして評価し、正本にはしない。

**Tech Stack:** Python 3.11、uv、SQLite/WAL、FTS5 trigram、JSON Schema、pytest、ruff、mypy、公式MCP Python SDK（stdio）、systemd、Docker Compose、restic等の暗号化バックアップ。

---

## 1. 調査結果

### 1.1 リポジトリの実体

- Git root: `/home/user/projects/pda`
- branch: `main`
- HEAD: `3cb02aea788f6226d5b222e33eb5df6132f62d4e`
- origin: `git@github.com:myurait/pda.git`
- 調査開始時のworking tree: clean
- 追跡ファイルは次の2件だけ。
  - `personal_delegate_agent_plan.md`（762行）
  - `pda_minipc_setup_record.md`（516行）
- 合計1,278行、59,486 bytes。README、実装、テスト、スキーマ、IaC、復旧手順、プロジェクト指示ファイルはない。

したがって、このリポジトリは現時点では「PDA本体」ではなく、構想書と手作業の運用記録である。実際のPDAは`~/.hermes/`、`~/firecrawl/`、`~/openwebui/`、systemd user units、Docker volumesに分散し、再構築可能な形で管理されていない。

### 1.2 ライブ環境で確認できたもの

- Hermes Agent v0.18.2、`gpt-5.6-sol`、OpenAI Codex OAuth、local terminal backend
- `hermes doctor`: 全必須チェック通過
- GatewayとWeb Dashboard: active/enabled
- Hermes API: `:8642/health`および`:8642/v1/health`がHTTP 200
- Open WebUI: `:9120`がHTTP 200
- Firecrawl: `:3002`がHTTP 200
- Dashboard: `:9119`がHTTP 302（認証画面への遷移）
- Claude Code 2.1.205、`CLAUDE_CODE_OAUTH_TOKEN`認証
- HermesセッションDB: 調査開始時19 sessions / 132 messages / 4.4 MB。調査中にも増加しており、現在の会話が保存されることを確認
- Hermes built-in memoryは有効だが、`MEMORY.md`と`USER.md`は未作成
- Hermes cron job: 0
- Hermes側MCP client設定: 0（開発PC側Claude Code→HermesのMCP設定とは別）
- Tailscale: 未導入
- restic / borg / rclone: 未導入
- 実効RAM: 12 GiB、利用可能約7 GiB。SSD空き約396 GiB

### 1.3 運用上の不整合

- `openwebui.service`はenabledだがinactive。
- user unitが`Requires=docker.service`を宣言しているが、user manager上の`docker.service`は`not-found`。
- 実行ユーザーはdocker groupに所属せず、Docker socketへアクセスできない。
- Open WebUI自体はDockerの`restart: unless-stopped`で稼働しているため、「systemdとDocker restart policyの二重・分裂管理」になっている。
- `ghcr.io/open-webui/open-webui:main`という可変タグを使用しており、再構築時の同一性を保証できない。
- Firecrawlの`nuq-postgres`には永続volumeがない。
- `3002/8642/9119/9120`が`0.0.0.0`で待受。特にFirecrawlは認証なしの構成である。
- fresh-host復元、再起動後の全サービスhealth、オフホストバックアップは未実証。

---

## 2. 現在ステップの判定

### Phase 1: 常時稼働基盤

判定: 機能上は完了、運用品質は再オープン。

Ubuntu、SSH、Hermes、Gateway、UI、Web取得は成立している。一方、再現可能な構成、バックアップ、復元試験、単一のサービス管理、ネットワーク境界が不足する。`personal_delegate_agent_plan.md:371-390`の「常時稼働」は満たすが、長期保存するPDAの土台としては未完成。

### Phase 2: Hermesを中核とした最小PDA

判定: 部分完了。

対話、タスク受付、ツール実行、セッション保存は成立している。しかし`personal_delegate_agent_plan.md:394-413`にあるセッション間記憶の実用確認、定期処理、MCP接続、本人確認が必要な操作の区別は未実証。memory/cron/MCPの「機能が存在する」ことと、PDAとして「運用されている」ことを区別する。

### Phase 3: 複数エージェントランタイム統合

判定: 通信経路のPoCは完了、オーケストレーションは部分完了。

Claude Codeへの委任と結果回収、Claude Code→Hermes MCPの経路は成立している。しかし`personal_delegate_agent_plan.md:417-436`にある共通タスクコンテキスト、エージェント切替後の継続、並列利用、自動選択、役割・品質基準は未実装。Codexは現在Hermesの中核モデルであり、独立委任ランタイムとして統合されたわけではない。

### Phase 4: 情報取り込み基盤

判定: 未着手。準備資産のみ存在。

Hermes自身の履歴は`state.db`へ保存され、Firecrawlも稼働している。しかし過去データ取込、差分取得、共通形式、出典、重複、更新・削除・失効、security domainは存在しない。`pda_minipc_setup_record.md:466-487`の記述どおり次工程である。

### Phase 5: PKB／コンテキストグラフ

判定: 未着手。

現時点の`session_search`は有用なFTS5検索、built-in memoryは少量の常時注入メモであり、どちらも出典・claim状態・関係・判断履歴・タスク別Context Packを持つPDAのPKBではない。

### 現在地の正式な呼称

**「Phase 3の通信PoC完了後、Phase 4進入前のPhase 3.5（運用安定化・情報境界・Context Spine設計）」**とする。

セットアップ記録の「Phase 2・3達成済み」という表現は、通信経路の到達点としては正しいが、元計画の全到達条件に対しては広すぎる。次回更新時に「機能PoC完了」と「フェーズ完了」を分ける。

---

## 3. 最終系へ向けた設計判断

### 3.1 正本をHermesから分離する

PDAの正本は、以下のいずれにも置かない。

- `~/.hermes/state.db`: Hermes固有の会話ストアであり、スキーマはHermes更新に追随する
- `MEMORY.md` / `USER.md`: 合計約1,300 tokensのbootstrap用メモ
- Open WebUI DB: UI固有の会話・設定
- Holographic / Hindsight / OpenViking / Supermemory等: 一度に1 providerだけ有効で、交換・再生成性を保証する必要がある
- 特定LLMの会話履歴やベンダークラウド

正本は`$PDA_DATA_DIR`配下のPDA Event Ledgerとし、各ランタイムはMCP/API adapterから参照する。

### 3.2 最小アーキテクチャ

```text
Hermes state.db ─┐
個人Git / Web ───┼─ Connector ─> Append-only Event Ledger (SQLite/WAL)
将来の各情報源 ─┘                    ├─ content-addressed blobs
                                       ├─ FTS5 trigram index
                                       ├─ Claim / Relation projection
                                       └─ Context Pack builder
                                                  │
                                    PDA stdio MCP
                           context_pack / evidence_get
                              ┌───────────┴───────────┐
                           Hermes                 Claude/Codex
                              │                         │
                              └── same pack_id/evidence ┘

Memory provider ← accepted claimだけを同期する再構築可能な補助投影
Evaluator/Gate  ← event/artifact hashに対して独立verdictを記録
```

### 3.3 Canonical eventの最低契約

すべてのeventは最低限、次を持つ。

- `event_id`
- `schema_version`
- `source_id`
- `external_key`
- `revision_hash`
- `event_type`
- `occurred_at`
- `observed_at`
- `actor`
- `project`
- `security_domain`（初期値: `personal` / `public`; `work`はdefault deny）
- `source_locator`
- `content_hash`
- `payload`またはcontent-addressed blob参照
- `supersedes` / `retracts` / `derived_from`等のedge

更新や削除で過去を上書きしない。新revision、tombstone、retractionをeventとして追加する。

### 3.4 Claimと証拠を分離する

- raw eventは「証拠」であって「命令」ではない。
- LLMが抽出した決定・選好・制約・未解決事項は必ず`proposed`から始める。
- claimは根拠event ID、引用範囲、抽出model、prompt versionを必須にする。
- 初期は人間または決定論的ルールで`accepted/rejected/retracted`へ遷移する。
- Context Packへ自動注入するのは、accepted claimと明示的に選択されたraw evidenceだけにする。
- Web本文や外部チャット中の文を、system instructionやmemoryへ直接昇格させない。

### 3.5 Memory providerの扱い

- built-in memory: PDA MCPの存在、安定した少数のユーザー選好、運用上の短いbootstrap hintだけに使う。
- Holographic: canonical ledger完成後の軽量A/B候補。正本にはしない。
- Hindsight: FTS5 baselineを明確に上回る場合だけlocal KGを評価する。
- OpenViking: 大量文書の階層browseが必要になった時点で評価する。
- cloud provider: 個人・業務データの外部送信条件、export、削除、再構築性が明文化されるまで使用しない。

### 3.6 当面は導入しないもの

- Neo4j
- Kafka
- Qdrant等のvector DB
- 汎用オントロジー
- 全情報源の同時接続
- 自動エージェントルーター
- 自己改変

まずSQLite FTS5 trigramのbaselineを作り、gold queryで不足が証明された場合だけ複雑性を追加する。

---

## 4. Phase 4進入前の必須ゲート

高度な多層認知ゲートはPhase 8でよいが、次の決定論的ゲートはPhase 4より前へ移す。

1. **データ境界**
   - 会社Slack、Backlog、会社Git、会社Claude履歴は、明示的な書面許可と分離環境が成立するまで取り込まない。
   - `personal/public/work`の保存先、暗号鍵、index、backupsを混在させない。
   - 「すべての入出力を無条件保存」ではなく、secret、認証画面、削除要求、機微カテゴリの除外規則を先に定める。

2. **復旧性**
   - Hermes DB/config、PDA ledger、Open WebUI data、非秘密IaC、秘密情報を分類してバックアップする。
   - 暗号化されたオフホスト世代バックアップを作る。
   - fresh-hostまたは隔離ディレクトリへの復元試験を合格させる。
   - RPO/RTOを決める。初期提案は日次バックアップ、RPO 24時間以内。

3. **サービス管理**
   - Open WebUIをroot管理system unitまたはrootless containerへ統一し、壊れたuser unitと二重管理を解消する。
   - 安易にユーザーをdocker groupへ追加しない（root相当権限になるため）。
   - imageはversionまたはdigest固定にする。
   - reboot後にGateway、Dashboard、API、Open WebUI、Firecrawlがhealthyになることを実機確認する。

4. **ネットワーク境界**
   - Firecrawl `:3002`はloopbackまたは専用Docker networkへ閉じる。
   - Hermes API `:8642`はOpen WebUI/管理経路以外から到達不能にする。
   - UIは認証に加えてVPN/TLS経由にする。
   - Tailscaleは待受削減とACL設計の後に導入し、ポート開放は行わない。

5. **可逆性と承認**
   - memory更新、外部送信、破壊操作、権限変更は人間承認対象にする。
   - raw ingest処理はtoolなし・書込先限定で動かす。
   - 重複排除、再実行、削除伝播、tombstone、prompt injection、復元のテストを先に作る。

---

## 5. 実装計画

### Task 1: フェーズ定義とプロジェクトの正本化

**Objective:** 構想書、実装、運用状態、受入基準を同じリポジトリで管理できる骨格を作る。

**Files:**
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `docs/status/current-state.md`
- Create: `docs/roadmap/phase-gates.md`
- Create: `docs/adr/0001-canonical-event-ledger.md`
- Create: `docs/adr/0002-memory-providers-are-projections.md`
- Modify: `pda_minipc_setup_record.md`

**Steps:**
1. `README.md`に目的、現在地「Phase 3.5」、主要コマンド、データ配置、秘密をcommitしない規則を書く。
2. `AGENTS.md`にTDD、secret禁止、`work` domain default deny、raw contentを命令として扱わない規則を書く。
3. `docs/status/current-state.md`へ本調査の検証結果と検証日時を書く。
4. `docs/roadmap/phase-gates.md`で各フェーズを「機能PoC」「運用完了」「評価完了」に分ける。
5. 2件のADRでcanonical ledgerとmemory providerの位置付けを確定する。
6. `pda_minipc_setup_record.md`の「Phase 2/3完了」を、元計画の未達要件が分かる表現へ修正する。
7. Verify: `git diff --check`
8. Commit: `docs: define PDA phase 3.5 and canonical context spine`

### Task 2: Pythonプロジェクトと品質ゲートを作る

**Objective:** 実装と検証を再現できる最小Python packageを作る。

**Files:**
- Create: `pyproject.toml`
- Create: `uv.lock`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/pda/__init__.py`
- Create: `src/pda/cli.py`
- Create: `tests/test_cli.py`

**Steps:**
1. `uv init --package`相当の構成を作る。Pythonは`>=3.11`。
2. runtime依存は最初は最小化し、MCP実装時までstdlib中心にする。
3. dev依存として`pytest`, `pytest-cov`, `ruff`, `mypy`を追加する。
4. Failing test: `pda --help`と`pda doctor --json`のcontract testを書く。
5. Run: `uv run pytest tests/test_cli.py -v`。Expected: FAIL。
6. `argparse`または同等の最小CLIを実装する。
7. Run: `uv run pytest tests/test_cli.py -v`。Expected: PASS。
8. Run: `uv run ruff check . && uv run mypy src`
9. Commit: `chore: bootstrap PDA package and quality gates`

### Task 3: 機密区分と取込ポリシーを固定する

**Objective:** Phase 4より前にdefault-denyのデータ境界を実装する。

**Files:**
- Create: `config/data-policy.example.yaml`
- Create: `docs/security/data-boundaries.md`
- Create: `src/pda/policy.py`
- Create: `tests/test_policy.py`

**Policy contract:**
- `public`: 取込可
- `personal`: 明示したconnector/pathだけ取込可
- `work`: default deny。書面許可、別store、別key、別backupがない限り拒否
- `secret`: 本文保存禁止。locatorとredacted metadataだけ許可

**Steps:**
1. Failing tests: `work`が既定で拒否されること、secret patternが本文保存されないこと、未知domainが拒否されることを書く。
2. Run: `uv run pytest tests/test_policy.py -v`。Expected: FAIL。
3. 最小policy evaluatorを実装する。
4. RunしてPASSを確認する。
5. `docs/security/data-boundaries.md`に会社データの非取込方針、削除要求、retention、外部LLM送信条件を書く。
6. Commit: `feat: enforce default-deny ingestion policy`

### Task 4: 現行構成をIaC化し、health contractを作る

**Objective:** 手作業で構築された現在のPDAを再現・検証可能にする。

**Files:**
- Create: `infra/compose/openwebui.compose.yaml`
- Create: `infra/compose/firecrawl.override.yaml`
- Create: `infra/systemd/hermes-dashboard.service.in`
- Create: `infra/systemd/openwebui.service.in`またはrootless構成
- Create: `config/services.example.yaml`
- Create: `src/pda/doctor.py`
- Create: `tests/test_doctor.py`
- Create: `docs/operations/rebuild.md`

**Steps:**
1. 現在のunit/composeをsecret抜きでテンプレート化する。
2. Open WebUI imageを可変`main`ではなく検証済みversion/digestに固定する。
3. Firecrawlをloopback/内部networkに限定するoverrideを作る。
4. Docker管理方式を「root system unit」か「rootless Docker」の一方に決め、二重管理を廃止する。docker group追加は採用しない。
5. Failing tests: doctorが`:8642/health`, `:9120`, Firecrawl内部health、systemd状態の不整合をJSONで返すことを書く。
6. doctorをread-onlyで実装する。
7. Run: `uv run pytest tests/test_doctor.py -v`。
8. 実機検証: `uv run pda doctor --json`。
9. 再起動試験はユーザー承認後に実施し、全serviceのhealthを記録する。
10. Commit: `ops: make PDA services reproducible and health-checkable`

### Task 5: バックアップと復元を先に成立させる

**Objective:** 取込データを増やす前に、壊しても戻せる状態を作る。

**Files:**
- Create: `scripts/snapshot_hermes.py`
- Create: `scripts/backup_pda.sh`
- Create: `scripts/restore_pda.sh`
- Create: `config/backup.example.env`
- Create: `tests/test_snapshot_hermes.py`
- Create: `tests/test_restore_manifest.py`
- Create: `docs/operations/backup-restore.md`

**Steps:**
1. SQLite Online Backup APIで`~/.hermes/state.db`の整合スナップショットを取得するfailing testを書く。
2. `hermes sessions export ... --format jsonl`もportable exportとして併用する。
3. Open WebUI volume、PDA ledger、非秘密config、secretsを別manifest itemとして分類する。
4. restic等の暗号化オフホストbackendをユーザーが指定できるようにする。資格情報はrepoへ置かない。
5. backup manifestへSHA-256、取得時刻、schema version、sourceを記録する。
6. 空の隔離ディレクトリへrestoreし、DB integrity checkとsession countを検証する。
7. Run: `uv run pytest tests/test_snapshot_hermes.py tests/test_restore_manifest.py -v`。
8. 実バックアップと復元試験はユーザー承認後に実施する。
9. Commit: `ops: add encrypted backup and restore verification`

### Task 6: Canonical Event LedgerのschemaをTDDで作る

**Objective:** append-only、出典付き、再構築可能な正本を作る。

**Files:**
- Create: `src/pda/storage/schema.sql`
- Create: `src/pda/storage/ledger.py`
- Create: `src/pda/domain/events.py`
- Create: `tests/test_ledger_schema.py`
- Create: `tests/test_ledger_append_only.py`

**Required tables:**
- `sources`
- `ingest_runs`
- `connector_checkpoints`
- `events`
- `event_edges`
- `claims`
- `claim_evidence`
- `context_packs`
- `context_pack_items`
- `schema_migrations`

**Required constraints:**
- unique `(source_id, external_key, revision_hash)`
- content hash必須
- source locator必須
- occurred/observed time必須
- security domain必須
- event UPDATE/DELETEを通常APIから提供しない

**Steps:**
1. Failing testsで重複insert、欠落provenance、上書き禁止、tombstone追加を定義する。
2. Run: `uv run pytest tests/test_ledger_schema.py tests/test_ledger_append_only.py -v`。Expected: FAIL。
3. WAL、foreign keys、busy timeoutを有効にした最小ledgerを実装する。
4. RunしてPASSを確認する。
5. Commit: `feat: add append-only canonical event ledger`

### Task 7: Hermes connectorのfixtureとread-only importを作る

**Objective:** 最初の情報源をHermes履歴だけに限定し、Phase 4の一往復を成立させる。

**Files:**
- Create: `src/pda/connectors/base.py`
- Create: `src/pda/connectors/hermes.py`
- Create: `tests/fixtures/hermes_export.jsonl`
- Create: `tests/test_hermes_connector.py`
- Create: `tests/test_hermes_incremental.py`

**Steps:**
1. private contentを含まない小さなfixtureを手作りする。実セッションdumpをcommitしない。
2. Failing tests:
   - session/message/tool callのsource locatorを保持する
   - 同じsnapshotの再取込で新規eventが0
   - active sessionにmessageが増えた場合だけ新revisionを追加
   - edited/deleted/compacted stateをsupersedes/tombstoneで表現
   - reasoning/secret fieldを既定で取り込まない
3. 最初は`hermes sessions export`のJSONLをsupported interfaceとして読む。必要な差分が不足する場合だけ`state.db`をread-only URIで読むadapterを追加する。
4. Run: `uv run pytest tests/test_hermes_connector.py tests/test_hermes_incremental.py -v`。
5. 実データに対してdry-runを行い、件数と拒否理由だけ表示する。
6. ユーザー承認後にpersonal domainへ初回importする。
7. Commit: `feat: ingest Hermes sessions with provenance and revisions`

### Task 8: 日本語対応FTS5 retrievalを作る

**Objective:** vector DBなしで測定可能な検索baselineを作る。

**Files:**
- Modify: `src/pda/storage/schema.sql`
- Create: `src/pda/retrieval/fts.py`
- Create: `tests/test_fts_japanese.py`
- Create: `tests/test_fts_filters.py`

**Steps:**
1. Failing testsとして日本語の完全一致、部分一致、project/domain/as_of filterを書く。
2. FTS5 trigram indexを実装する。利用SQLiteでtrigramが使えない場合は明示エラーにする。
3. raw evidenceとaccepted claimを別rank groupで返す。
4. Run: `uv run pytest tests/test_fts_japanese.py tests/test_fts_filters.py -v`。
5. Commit: `feat: add provenance-aware Japanese FTS retrieval`

### Task 9: 最小claim projectionを作る

**Objective:** Phase 5を汎用knowledge graphではなく「決定・制約・選好・未解決事項」から始める。

**Files:**
- Create: `src/pda/claims/projector.py`
- Create: `src/pda/claims/models.py`
- Create: `tests/test_claim_evidence.py`
- Create: `tests/test_claim_lifecycle.py`

**Steps:**
1. 最初は手動/決定論的claim登録だけを実装する。
2. Failing tests:
   - evidenceなしclaimを拒否
   - claimは`proposed`から開始
   - accepted/rejected/retractedの遷移履歴をeventで保持
   - superseded evidenceを使うclaimにconflictを付与
3. RunしてFAILを確認する。
4. 最小実装を行いPASSにする。
5. LLM抽出は後続Taskとして、toolなし・JSON Schema固定・model/prompt version保存で追加する。
6. Commit: `feat: add evidence-backed claim lifecycle`

### Task 10: Context Pack builderを作る

**Objective:** 現在の依頼に必要な状態、決定、制約、未解決事項、証拠を監査可能な一つのpackageにする。

**Files:**
- Create: `src/pda/context/builder.py`
- Create: `src/pda/context/schema.py`
- Create: `schemas/context-pack.schema.json`
- Create: `tests/test_context_pack.py`
- Create: `tests/test_context_budget.py`

**Contract:**

```json
{
  "pack_id": "sha256:...",
  "query": "...",
  "as_of": "...",
  "scope": {"project": "pda", "domain": "personal"},
  "current_state": [],
  "decisions": [],
  "constraints": [],
  "open_questions": [],
  "conflicts": [],
  "evidence": [
    {
      "event_id": "...",
      "quote": "...",
      "source": "hermes",
      "locator": "session:<id>/message:<id>",
      "occurred_at": "...",
      "status": "active"
    }
  ]
}
```

**Steps:**
1. Failing testsでtoken budget、as-of再現性、citation必須、retracted claim除外、conflict表示を定義する。
2. 最大約2,000 tokensを初期budgetとしてbuilderを実装する。
3. pack内容と選択eventを`context_packs/context_pack_items`へ記録する。
4. 同一query/scope/as_of/input revision setから同一pack IDを生成する。
5. Run: `uv run pytest tests/test_context_pack.py tests/test_context_budget.py -v`。
6. Commit: `feat: build auditable task-scoped context packs`

### Task 11: 共通stdio MCP adapterを作る

**Objective:** Hermes固有のmemory APIではなく、交換可能なランタイムが同じcontextを使えるようにする。

**Files:**
- Create: `src/pda/mcp_server.py`
- Create: `tests/test_mcp_contract.py`
- Create: `docs/integrations/mcp.md`
- Create: `skills/pda-context/SKILL.md`

**Initial tools:**
- `context_pack(query, project, as_of, token_budget)`
- `evidence_get(event_id)`
- 後から必要なら`pack_feedback(pack_id, item_id, rating)`

**Steps:**
1. Failing contract testsを書く。tool resultはJSON Schemaに適合し、raw dataは命令ではないというlabelを含める。
2. read-only MCP serverを実装する。ledgerへの一般書込toolは公開しない。
3. Run: `uv run pytest tests/test_mcp_contract.py -v`。
4. Hermesへstdio MCPとして登録し、`hermes mcp test pda-context`で確認する。
5. Claude Codeへ同じstdio commandを登録する。
6. `skills/pda-context/SKILL.md`で、タスク開始時のpack取得、委任時のpack ID伝達、最終回答でのevent ID引用を規定する。
7. Commit: `feat: expose PDA context through runtime-neutral MCP`

### Task 12: HermesとClaude Codeの同一Context Pack E2E

**Objective:** Phase 3の未達だった共通コンテキストと切替継続を実証する。

**Files:**
- Create: `tests/e2e/test_cross_runtime_context.py`
- Create: `docs/evaluation/cross-runtime-results.md`

**Steps:**
1. personal test corpusに、明示的な決定・制約・失効済み決定を用意する。
2. Hermesが`context_pack`を取得し、pack IDと根拠eventを回答するテストを実行する。
3. 同じpack IDをClaude Codeへ渡し、同じactive decisionを引用するテストを実行する。
4. 両ランタイムが失効済みdecisionを採用しないことを確認する。
5. 結果を`docs/evaluation/cross-runtime-results.md`へ記録する。
6. Commit: `test: verify cross-runtime context continuity`

### Task 13: Retrieval評価harnessを作る

**Objective:** PKBの改善を印象ではなく固定評価で判断する。

**Files:**
- Create: `eval/gold_queries.jsonl`
- Create: `src/pda/eval/retrieval.py`
- Create: `tests/test_eval_metrics.py`
- Create: `docs/evaluation/baseline.md`

**Initial metrics:**
- evidence Recall@5 ≥ 0.85
- citation precision ≥ 0.95
- superseded decision判定 = 100%
- unsupported/no-answer ≥ 0.90
- pack ≤ 約2,000 tokens
- local build p95 < 250ms（実機測定後に妥当性再確認）
- `session_search` baseline比で正答率+10 points、または同等精度でcontext token 30%以上削減
- raw Web本文のprompt injectionを命令として実行しない

**Steps:**
1. まず20〜30件のgold queryを作る。答え、許容根拠event、誤答、as-ofを記録する。
2. `session_search`単独のbaselineを保存する。
3. Context Packのmetricを計算する。
4. Holographic/Hindsight/OpenViking等は、このbaselineを上回る可能性を検証するspikeとしてのみ追加する。
5. Commit: `test: add PDA retrieval and provenance benchmark`

### Task 14: 一回実行から定期差分取込へ進める

**Objective:** one-shotの安全性が証明された後だけ自動化する。

**Files:**
- Create: `infra/systemd/pda-ingest.service`
- Create: `infra/systemd/pda-ingest.timer`
- Create: `docs/operations/ingestion.md`
- Create: `tests/test_ingest_locking.py`

**Entry conditions:**
- 冪等再実行PASS
- backup/restore PASS
- deletion/tombstone PASS
- prompt injection PASS
- doctor green
- work domain拒否PASS

**Steps:**
1. lock、timeout、dead-letter、run manifest、非0終了を実装する。
2. 最初はHermes personal historyだけを日次差分取込する。
3. 失敗時に勝手にclaimを更新せず、通知だけ行う。
4. `systemd-analyze verify`と手動`start`で確認する。
5. Commit: `ops: schedule guarded Hermes history ingestion`

### Task 15: 次のconnectorを一つずつ追加する

**Objective:** 全情報源を一度に接続せず、同じcontractと評価を通す。

**Order:**
1. synthetic/public fixture
2. 個人Git（低機密repo）
3. 個人のChatGPT/Claude exportの小標本
4. 個人ブラウザ履歴の明示選択分
5. Web article/bookmark
6. 会社情報は承認済み分離環境が成立した場合のみ最後

各connectorは以下を必須にする。
- data policy test
- idempotency test
- provenance test
- update/delete propagation test
- prompt injection test
- backup/restore test
- independent disable/delete path

---

## 6. フェーズ完了条件の再定義

### Phase 3完了

- Hermesと少なくとも1つの外部runtimeが同一`pack_id`を参照する
- agent切替後もactive decisionとopen questionが継続する
- 実行結果を`task_id/run_id/pack_id/runtime/model/artifact hash`で回収する
- role選択ルールと失敗時fallbackがテストされる

### Phase 4完了

- 対象eventの取込漏れ0
- 同一snapshot再実行で新規event 0
- 全eventにsource locator、observed time、hash、security domainがある
- update/delete/失効を履歴付きで再現できる
- backupからledger復元とprojection再構築に成功する
- 会社情報がdefault denyである

### Phase 5完了

- 固定gold setで上記retrieval/citation基準を満たす
- Context Packが現在状態、決定、制約、未解決事項、conflict、根拠を返す
- HermesとClaude Codeが同じpack IDから同じ根拠を引用する
- memory providerを交換・無効化してもcanonical stateを失わない

---

## 7. Phase 6以降への接続

1. **Phase 6 プロジェクト横断管理**
   - `project_state`をclaim/eventから投影
   - next action、blocker、dependencyをContext Packへ追加

2. **Phase 7 判断軸**
   - 過去decisionとoverrideからpolicy candidateを抽出
   - user承認済みpolicyだけを実行判断に使う
   - project固有policyとglobal policyを分離

3. **Phase 8 多層ゲート**
   - proposer、executor、evaluatorを別process/profile/権限に分離
   - verdictを対象artifact/config/commit hashとpolicy versionへ結合
   - gate policyと承認鍵をcore agentの書込権限外に置く

4. **Phase 9 自己改善**
   - 失敗、override、評価差分から変更案を生成
   - sandbox、固定eval、canary、rollbackを通過した変更だけ採用

5. **Phase 10 コア非依存**
   - Context Pack/MCP/event contractsを固定し、Hermes以外のorchestratorでreplay
   - 同じgold setとgate verdictで比較する

6. **Phase 11 自己改変**
   - coreは交換対象にできるが、canonical ledger、監査log、backup、gate policy、承認鍵、削除policyは自己改変対象外に置く
   - gate自身の変更は必ず人間承認とする

---

## 8. 優先順位

### P0: 今すぐ先に行う

1. Phase 3.5の明文化
2. 会社/個人データ境界のdefault deny
3. バックアップとrestore drill
4. Open WebUI/Firecrawl/Hermes APIのサービス管理・待受整理
5. reboot health test
6. その後にTailscale＋ACL/TLS

### P1: 最初の実装

1. Event Ledger
2. Hermes connector
3. FTS5 trigram baseline
4. evidence-backed claims
5. Context Pack
6. 共通stdio MCP
7. Hermes↔Claude Code E2E
8. gold-set評価

### P2: 評価後

1. personal connectorを一つずつ追加
2. memory provider A/B
3. project state
4. agent routing
5. 判断軸
6. 独立gate
7. 自己改善・コア交換

---

## 9. 主なリスクと対策

- **取り込みが先行し、汚染された記憶が永続化する**
  - raw evidence、proposed claim、accepted claimを分離する。
- **特定providerが新しいロックインになる**
  - providerを再構築可能なprojectionに限定する。
- **グラフDBを先に入れ、評価不能な複雑性が増える**
  - SQLite/FTS baselineを固定し、不足を数値で示してから追加する。
- **会社情報が個人PDAへ混入する**
  - work domain default deny、別store/key/index、書面承認をentry conditionにする。
- **PDA自身が監査条件を書き換える**
  - gate policy、承認鍵、gold set、backupをcoreの書込権限外へ置く。
- **可変Docker imageや手作業設定で再現不能になる**
  - digest pin、IaC、manifest、restore drillを必須化する。
- **LAN内だから安全という誤認**
  - loopback/private network、VPN/TLS、最小ACL、token rotationを順番に実施する。

---

## 10. 最初の実用的な次の一手

次の作業単位は「全履歴の取り込み」でも「Neo4j導入」でもない。

**まずPhase 3.5を閉じ、その直後にHermesのpersonal session数件だけを、append-only Event Ledgerへ冪等に取り込み、出典付きContext PackをHermesとClaude Codeの双方から同じpack IDで取得する。**

これが成立すれば、PDAは初めて「一つのHermes環境」から「交換可能なagent群の上位にある継続的な自己」へ移り始める。
