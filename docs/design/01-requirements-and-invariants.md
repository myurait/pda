# 01. 要求と不変条件

- 最終更新: 2026-07-20
- 上位文書: [README.md](README.md)

## 1. 目的

PDA（Personal Delegate Agent）は、本人に帰属する情報・活動履歴・判断履歴・判断基準・
プロジェクト状態・統治条件を継続的に保持し、複数の交換可能なAIエージェントランタイムを
そのコンテキストの上で統合利用する個人専用システムである
（構想の一次資料: [personal_delegate_agent_plan.md](../../personal_delegate_agent_plan.md) 第14節）。

本設計の目的は、この構想を **実装判断に使える具体度** の不変条件・契約・アーキテクチャ・
移行順序へ落とすことである。

## 2. Non-goals

以下はPDAの目的に含まれない。設計上の複雑性を正当化する根拠として使わない。

- **NG-1**: 単一の高性能エージェント（モノリシックAI）を作ること。PDAは複数runtimeの上位に立つコンテキスト・統治層である
- **NG-2**: 汎用のマルチテナントSaaS。運用者・利用者とも本人一名を前提とする
- **NG-3**: 分散システム（複数ノードでの合意、レプリケーション、メッセージブローカー）。単一ホストで成立しない要件が数値で示されるまで導入しない
- **NG-4**: 「すべてを保存すること」自体。最小化・除外・retention・削除がscopeに含まれる（INV-12）
- **NG-5**: 会社業務データの取り込み。法務・契約・組織policyの明示許可と分離構成が成立するまでdefault denyであり、成立させること自体を本設計の前提にしない（INV-6）
- **NG-6**: 無制限な自己書き換え。自己改変は統治条件の維持を前提とする（INV-13）
- **NG-7**: リアルタイム性・高可用性のSLA。個人運用で許容される復旧時間（[07](07-deployment-operations-and-recovery.md) のRTO仮説）を目標とする

## 3. システム境界

### 3.1 何を「PDA本体」と呼ぶか

**PDA本体（PDA core assets）** とは、runtimeを交換しても失われてはならない資産の総体である。

| 資産 | 内容 | 正本の置き場所 |
|------|------|----------------|
| Context Spine | canonical event ledger、blob store、claim／task／run等の運用テーブル | `$PDA_DATA_DIR`（[04](04-context-spine-and-data-contracts.md)） |
| Contracts | CanonicalEvent、Claim、Task、Run、ContextPack、GateVerdict、Approval、AuditEntry等のschema | 本リポジトリ `docs/design/04`, `docs/design/05` およびコード内schema |
| Policy | data policy（機密区分・取込規則）、egress policy、approval policy、gate policy | 本リポジトリ＋protected領域（[06](06-security-privacy-and-governance.md)） |
| 評価資産 | gold set、metric定義、baseline記録 | 本リポジトリ＋protected領域 |
| 監査 | audit chain | Context Spine＋オフホスト複製 |
| 運用資産 | IaC（compose/systemd template）、backup manifest、復元手順 | 本リポジトリ＋backup repo |

### 3.2 何をPDA本体と呼ばないか

| 区分 | 定義 | 例 |
|------|------|-----|
| **Runtime** | タスクを解釈・実行する交換可能なエージェント実行系 | Hermes、Claude Code、Codex、ChatGPT、将来のharness |
| **Adapter** | runtime-neutralなcontractを特定runtimeの呼び出し形式へ変換する薄い層 | adapter-hermes、adapter-claude-code、adapter-codex |
| **Connector** | 外部情報源からContext Spineへの取り込み経路 | conn-hermes、conn-git、conn-chatgpt-export、conn-browser、conn-web |
| **Tool** | runtimeが利用する外部能力 | Firecrawl、MCPサーバー群、git、shell |
| **UI** | 本人との接点 | Open WebUI、Hermes Dashboard、CLI、（将来）Telegram |
| **Projection** | Spineから再生成可能な派生物 | FTS index、project_state、memory providerへの同期内容 |
| **External source** | PDAの外にある情報の発生源 | ChatGPT/Claude会話、ブラウザ、Slack、Backlog、Git hosting、Web |

**境界規則**: Runtime／Adapter／Connector／Tool／UI／Projectionは、失われても
PDA本体（3.1）から再構築または代替できなければならない。逆に、PDA本体は
これらのどれか一つの内部実装に正本を依存してはならない。

### 3.3 現行Hermes中心構成との境界

現在、Hermesは (a) 対話フロントドア、(b) オーケストレーター、(c) セッション履歴の保持者、
(d) ツール実行環境、の4役を兼ねる（[02](02-current-state-and-gaps.md)）。
最終形では (a)(b)(d) は交換可能なruntime/UIの役割であり、(c) は
**外部情報源の一つ**（`~/.hermes/state.db` はconn-hermesの取り込み元）へ格下げされる。
Hermes built-in memoryはPDAの正本ではなく、bootstrap用の小さなキャッシュに限定する
（[ADR-0002](../adr/0002-memory-providers-are-rebuildable-projections.md)）。

## 4. 用語（正本）

| 用語 | 定義 |
|------|------|
| **Context Spine** | PDA所有のcanonicalデータ層。event ledger＋blob store＋運用テーブル＋projectionの総称。実体は `spine-<domain>.db`（SQLite）と `blobs/` |
| **CanonicalEvent** | 出典・時刻・hash・機密区分付きの追記専用観測記録。全情報の最小単位（[04](04-context-spine-and-data-contracts.md) §4.1） |
| **Claim** | eventを根拠として抽出された主張（decision/preference/constraint/open_question/fact/policy）。lifecycleを持つ（[04](04-context-spine-and-data-contracts.md) §4.2） |
| **Context Pack** | タスク単位で組み立てる、根拠付き・予算付きのコンテキスト成果物（[04](04-context-spine-and-data-contracts.md) §4.5） |
| **Task / Run / Artifact** | 委任作業の単位／その1回の実行／実行が生んだ成果物（[04](04-context-spine-and-data-contracts.md) §4.3-4.4） |
| **Gate** | 実行の可否・品質・権限を判定する評価点。決定論的gateと認知gateを区別する（[06](06-security-privacy-and-governance.md) §6） |
| **GateVerdict / Approval / AuditEntry** | gateの判定記録／人間承認記録／監査記録（[04](04-context-spine-and-data-contracts.md) §4.6-4.8） |
| **security_domain** | `public` / `personal` / `work` / `secret` の機密区分（[06](06-security-privacy-and-governance.md) §2） |
| **projection** | Spineから決定論的に再生成できる派生データ。破棄・再構築が常に可能 |
| **pda-mcp** | Context Spineをruntimeへ公開するstdio MCPサーバー（[05](05-orchestration-and-runtime-contracts.md) §5） |
| **pda-cli** | 管理・取込・承認・診断用CLI（`pda` コマンド群） |
| **pda-spined** | 権限分離後にSpineアクセスを仲介するUnix socketデーモン（transition以降。[03](03-target-architecture.md) §5） |
| **ミニPC / agent-node** | GMKtec M8上のUbuntu Server。PDA常時稼働ホスト |
| **開発PC** | macOS。会社Team planのClaude Code等が動く別マシン。PDA常時稼働対象ではない |

## 5. 不変条件（Invariants）

以下はフェーズやruntime構成が変わっても維持する条件である。違反を許す変更は
本人の明示承認とADRの改訂を要する。

| ID | 不変条件 | 由来 |
|----|----------|------|
| **INV-1** | **Runtime交換可能性**: PDAの継続性を担う正本（event/claim/task/decision/policy/audit）を特定runtime・model・UI・memory providerの内部だけに置かない。runtime交換後もContext Spineと本設計文書だけから業務を再開できる | 構想§5.1-5.2、brief命題1,3,4 |
| **INV-2** | **Provenance**: すべてのcanonical recordはsource、locator、observed時刻、content hash、security_domainを持つ | 構想§5.4、brief命題5 |
| **INV-3** | **追記優先の履歴**: 過去の観測を上書きしない。訂正・削除はrevision/tombstone/retraction eventで表現する。物理削除はredaction手続き（[04](04-context-spine-and-data-contracts.md) §7）経由のみとし、削除の事実は監査に残る | brief命題5,11 |
| **INV-4** | **データは命令ではない**: 取り込みデータ・Web本文・tool出力・チャット履歴を命令へ自動昇格しない。Context Packはuntrusted dataとして明示ラベルされる | brief命題6 |
| **INV-5** | **Claim lifecycle**: 自動抽出された主張は`proposed`から開始し、承認境界を通らずに`accepted`へ遷移しない | brief命題5,7 |
| **INV-6** | **Work default deny**: `work` domainのデータは、書面許可と分離構成（別store・別鍵・別backup）が成立するまで取り込み・保存・送信を拒否する | brief命題9 |
| **INV-7** | **Restore-first**: 取り込み量・自動化・自律性の拡大より先に、backup・restore・監査の成立を各マイルストーンのentry conditionとする | brief命題11 |
| **INV-8** | **権限分離**: runtimeはContext Spine正本・gate policy・gold set・approval資格情報・audit chain・backupへ直接書込できない。書込は必ずPDA control plane（policy検査＋監査付き）を経由する | brief命題7、構想§5.5-5.6 |
| **INV-9** | **Egress統制**: security_domain別のegress policyに適合しない外部送信（LLM API・メッセージング・バックアップ先を含む）を行わない | brief命題9,12 |
| **INV-10** | **監査可能性**: 状態を変えるすべての操作はAuditEntryを生成する。audit chainの改変・削除はcore agentの権限外 | brief命題7,11 |
| **INV-11** | **Export可能性**: 全正本はopen format（SQLite/JSONL/files）でexportでき、特定vendorなしに再構築できる | brief命題8 |
| **INV-12** | **最小化**: 保存自体を目的化しない。connectorごとに除外規則・retention・削除要求経路を必須要件とする | brief命題12 |
| **INV-13** | **人間の最終権限**: 統治条件（INV群・gate policy・approval権限・削除policy）の変更、および自己改変の受け入れは人間承認を最終権限とする。approver権限をPDAへ委譲しない | brief命題7、構想§5.5、フェーズ11原則 |

**不変条件間の緊張と優先順位**:

- INV-3（追記保持）と INV-12（最小化・削除）は緊張する。優先順位は「本人の削除意思・法的義務 ＞ 履歴保持」。解決手段はredaction（本文の物理削除＋hashと削除記録の保持）であり、[04 §7](04-context-spine-and-data-contracts.md) で契約化する
- INV-1（runtime交換）と 実利（Hermes等の便利な内蔵機能の活用）は緊張する。優先順位は「正本の非依存 ＞ 機能の即時利用」。内蔵機能はprojection/cacheとしてのみ使う
- INV-7（restore-first）と 価値実証の速度は緊張する。優先順位は固定だが、対象を「これから増やすデータ」に限定することで初期コストを抑える（[09](09-transition-roadmap.md) M0のscope）

**不変条件の強制水準はフェーズで変わる（重要）**: INV-8（権限分離）・INV-10（監査可能性）・
INV-13（人間承認）は **目標条件** であり、その強制手段は段階的に強くなる。
near-term（M0〜M2）ではPDAの全プロセスがミニPCの単一ユーザーで動くため、これらの強制は
**規約＋監査による近似にとどまり、OS強制はない**。この期間は、injectionを受けた1ターンのruntimeが
Spineファイルの直接改変・`~/.hermes/.env` 等のsecret読取・audit行の再ハッシュによる改竄を
技術的には行い得る（[06 §4](06-security-privacy-and-governance.md) 脅威T-5/T-8/T-10）。
すなわち **near-term期間中、audit chainのtamper-evidenceとapproverの真正性はOS的に保証されない**。
これを補償するのはオフホスト複製（runtimeの資格で書き換えられない別系統。最大24hの改竄窓）であり、
OS強制（`pda`/`pda-admin` ユーザー分離・socket仲介）はtransition（M3）で確立する
（[03 §5](03-target-architecture.md)、[06 §7](06-security-privacy-and-governance.md)）。
この残余リスクの範囲と受容は [06 §4](06-security-privacy-and-governance.md) で明示する。

## 6. 要求一覧

出典略号: PLAN=構想書、REC=セットアップ記録、BRIEF=設計指示書、HYP=ロードマップ仮説。
種別: F=機能、D=データ、G=統治、O=運用、E=評価。

| ID | 種別 | 要求 | 出典 |
|----|------|------|------|
| R-01 | F | 複数runtimeを跨いでコンテキストの連続性を維持する | PLAN§3.1,5.1 |
| R-02 | D | エージェント会話・実行履歴（ChatGPT/Claude/Claude Code/Codex/Hermes）を統合参照できる | PLAN§6.1 |
| R-03 | D | ブラウザ・Web活動を選択的に取り込める | PLAN§6.2 |
| R-04 | D | 業務コミュニケーション（Slack）を取り込める — **work条件付き（INV-6）** | PLAN§6.3 |
| R-05 | D | プロジェクト管理情報（Backlog）を取り込める — **work条件付き（INV-6）** | PLAN§6.4 |
| R-06 | D | 開発履歴（Git）を取り込める（まず個人repo） | PLAN§6.5 |
| R-07 | D | PDA自身の入出力・実行・評価を記録する（除外規則付き） | PLAN§6.6＋INV-12 |
| R-08 | D | 情報の出典・取得時刻・生成主体・種別・有効性・利用履歴・失効を追跡できる | PLAN§5.4 |
| R-09 | F | 依頼に必要な背景・決定・制約・未解決・根拠をタスク単位で束ねられる（Context Pack） | PLAN P5 |
| R-10 | F | 本人の判断履歴・判断基準を蓄積し、整合する範囲で下流判断を代行できる | PLAN§3.2,P7 |
| R-11 | F | 複数並行プロジェクトの状態・依存・次アクションを保持し再開コンテキストを出せる | PLAN P6 |
| R-12 | F | タスクをruntimeへ委任し、結果・成果物・コストを回収できる | PLAN P3 |
| R-13 | F | runtime選択を手動→静的ルール→評価に基づく自動routingへ段階進化できる | PLAN目標6 |
| R-14 | F | 実行履歴・失敗・指摘から改善案を生成し、統制下で反映できる | PLAN P9 |
| R-15 | G | 独立した多層ゲートで意図・権限・品質・記憶更新・外部送信・自己変更を統制できる | PLAN P8 |
| R-16 | F | コアruntime・orchestrator・modelを交換しても継続性を維持できる | PLAN P10 |
| R-17 | G | 統治条件を維持したままPDA自身の構成・実装を改善対象にできる | PLAN P11 |
| R-18 | O | 常時稼働し、再起動後に自動復旧する | PLAN P1 |
| R-19 | F | PC・スマホ・CLI等の複数UIから利用できる（外出先を含む） | PLAN§8.1、REC§7.1 |
| R-20 | D | 本人がデータと鍵を所有し、open formatでexport・再構築できる | BRIEF命題8 |
| R-21 | G | 会社情報と個人情報の境界を維持し、会社情報はdefault denyとする | BRIEF命題9 |
| R-22 | O | 復元可能性・監査可能性・可逆性を取り込み量・自律性より先に確立する | BRIEF命題11 |
| R-23 | D | 除外・retention・削除要求・redactionを設計に含める | BRIEF命題12 |
| R-24 | G | 外部由来データを命令へ自動昇格させない | BRIEF命題6 |
| R-25 | G | 評価条件・承認境界・監査・復元手段を自己正当化で無効化できない | BRIEF命題7 |
| R-26 | O | 現行ミニPC・個人運用・限られた保守時間で段階的に成立する | BRIEF命題10 |
| R-27 | F | 日本語検索、as-of再現、citation付き回答が成立する | BRIEF§4.2 |
| R-28 | G | secret（認証情報等）の本文を保存・送信しない | HYP Task3＋BRIEF |
| R-29 | E | gold setとmetricによる測定でフェーズ進行と改善を判断する | BRIEF§4.6 |
| R-30 | O | 主要障害モードごとのdegraded modeとDR手段を持つ | BRIEF§4.5 |

## 7. Traceability Matrix（表。brief §7-9「requirement→component→phase→test」に対応）

要求 → 主担当component → 実現マイルストーン → 検証手段。
component定義は [03](03-target-architecture.md) §4、マイルストーン定義は [09](09-transition-roadmap.md)、
test/evidence定義は [08](08-evaluation-and-phase-gates.md) を正本とする。

| 要求 | Component | Milestone | Test / Evidence |
|------|-----------|-----------|-----------------|
| R-01 | C-SPINE, C-PACK, C-MCP | M1（実証）→M3（task継続） | T-E2E-CONT（cross-runtime同一pack引用）、T-RESUME |
| R-02 | C-CONN（hermes→chatgpt/claude export） | M1（Hermes）、M2（他） | T-INGEST-IDEM、T-PROVENANCE |
| R-03 | C-CONN（browser, web） | M2 | connector必須テスト一式（[08 §5](08-evaluation-and-phase-gates.md)） |
| R-04 | C-POLICY（当面deny）、将来C-CONN | Blocked（OQ-4） | T-POLICY-WORKDENY（denyの実証） |
| R-05 | C-POLICY（当面deny）、将来C-CONN | Blocked（OQ-4） | T-POLICY-WORKDENY |
| R-06 | C-CONN（git） | M2 | connector必須テスト一式 |
| R-07 | C-SPINE, C-AUDIT, C-POLICY | M1〜（段階拡大） | T-AUDIT-CHAIN、除外規則テスト |
| R-08 | C-SPINE（event/edge/claim） | M1 | T-PROVENANCE、T-ASOF |
| R-09 | C-PACK | M1 | T-PACK-CONTRACT、T-PACK-BUDGET |
| R-10 | C-CLAIM（policy claim） | M4 | T-CLAIM-LIFECYCLE、判断代行のgold set（GS-DECISION） |
| R-11 | C-SPINE（project_state projection） | M4 | T-PROJECT-RESUME |
| R-12 | C-TASK, C-ADPT | M3 | T-RUN-CONTRACT、T-HANDOFF |
| R-13 | C-ORCH（routing rules） | M4（静的）→M6（評価連動） | GS-ROUTING |
| R-14 | C-GATE, C-EVAL（self-improvement loop） | M5 | T-SELFIMP-PIPELINE |
| R-15 | C-GATE, C-POLICY | M0（policy文書）→M1（決定論的強制の実装）→M5（認知） | T-GATE-DENY（M1）、GS-GATE（M5） |
| R-16 | C-SPINE, C-MCP, C-ORCH | M6 | T-CORE-SWAP（代替経路でのgold set再実行） |
| R-17 | C-GATE, C-AUDIT | M5〜M6 | T-PROTECTED-ASSETS（不正変更拒否） |
| R-18 | C-OPS | M0 | T-REBOOT-HEALTH |
| R-19 | C-UI, C-OPS（Tailscale等） | M0〜M2（OQ-2） | 到達性確認記録 |
| R-20 | C-SPINE, C-OPS | M1 | T-EXPORT-REBUILD |
| R-21 | C-POLICY | M0（policy文書）→M1（強制実装） | T-POLICY-WORKDENY（M1） |
| R-22 | C-OPS | M0 | T-RESTORE-DRILL |
| R-23 | C-SPINE（redaction）, C-POLICY | M1〜M2 | T-REDACTION-PROPAGATION |
| R-24 | C-PACK, C-GATE | M1 | GS-INJECTION |
| R-25 | C-GATE, C-AUDIT, C-OPS | M3〜M5 | T-PROTECTED-ASSETS |
| R-26 | 全体（設計制約） | 常時 | 容量budget遵守（[07 §8](07-deployment-operations-and-recovery.md)） |
| R-27 | C-RETR, C-PACK | M1 | GS-RETRIEVAL、T-ASOF、citation precision |
| R-28 | C-POLICY, C-CONN | M0〜M1 | T-SECRET-EXCLUDE |
| R-29 | C-EVAL | M1〜 | baseline記録の存在（[08](08-evaluation-and-phase-gates.md)） |
| R-30 | C-OPS | M0〜M2 | degraded modeドリル記録（[07 §7](07-deployment-operations-and-recovery.md)） |

**カバレッジ確認**: R-01〜R-30 のすべてがcomponent・milestone・testへ写像されている。
Blocked要求（R-04, R-05）は「denyが正しく機能すること」を先に検証対象とし、
取り込み自体はOQ-4の解決を待つ。

## 8. 安全に置いた仮定（Assumptions）

| ID | 仮定 | 検証方法 / 危うくなる条件 |
|----|------|--------------------------|
| A-01 | ミニPC（16GB RAM/512GB SSD）は M0〜M4 の負荷を賄える | [07 §8](07-deployment-operations-and-recovery.md) の測定手順で毎マイルストーン確認。閾値超過で分離 |
| A-02 | Hermes（MIT license, GitHub公開。確認日2026-07-20）は当面保守され続ける | 保守停止・破壊的変更時はdegraded path（[07 §7](07-deployment-operations-and-recovery.md)）とruntime交換（M6前倒し）で対応 |
| A-03 | `hermes sessions export`（JSONL）または `state.db` read-only読み取りで履歴取得が可能 | M1 conn-hermes実装時に実機検証。不可ならconnector設計を変更（Unverified/Stale Candidate: セットアップ記録・仮説文書由来） |
| A-04 | SQLite 3.45.1（Ubuntu 24.04収録。packages.ubuntu.com確認 2026-07-20）でFTS5 trigramが利用可能 | M1で `pragma compile_options` 実機確認 |
| A-05 | 本人の保守可能時間は限られる（週数時間程度） | 運用負荷が超過したらconnector数・自動化範囲を縮小（[09](09-transition-roadmap.md) stop/go） |
| A-06 | 個人データの一部をOpenAI（Hermes中核=Codex）とAnthropic（Claude Code委任）へ送ることは、egress policy（OQ-3）確定までの暫定運用として本人が黙示的に受け入れている | OQ-3で明示化。確定までは新しいデータクラスの取込を拡大しない |
| A-07 | 本人の実装可処分時間は90日相当で約60〜80時間（A-05の「週数時間」の3か月換算）。この枠で完遂できるのはM0全量＋縮小M1のみ（[09 §2](09-transition-roadmap.md)） | 実測ペースが下振れしたら縮小M1をさらに分割。上振れしたらM2 connectorを前倒し（[09](09-transition-roadmap.md) stop/go） |
