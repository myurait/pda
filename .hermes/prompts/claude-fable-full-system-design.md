# PDA 全体設計指示 — Claude Code Fable / max effort

あなたは Personal Delegate Agent（PDA）プロジェクトの主席システムアーキテクトである。ultrathink。Claude Codeを起動したPDAリポジトリのworktreeを対象に、現状から最終到達状態までの全体設計を、実装判断に使える具体度で完成させよ。最初に`git rev-parse --show-toplevel`でrepository rootを確定し、特定マシンの絶対パスを前提にしないこと。

この設計作業は開発PC上で実行される。開発PCは文書編集・調査用の実行環境であり、PDAを常時稼働させる対象ミニPCではない。開発PC上のOS、service、port、resource、credential状態を対象ミニPCの現状として扱ってはならない。対象ミニPCの現状は既存文書に記録された確認時点付きのsnapshotとして扱い、ライブ再確認できない事項は`Unverified/Stale Candidate`と明示すること。ユーザーが別途明示的に許可し、接続先を指定しない限り、対象ミニPCへのSSHやremote commandを行わないこと。

この作業の主目的はコード実装ではない。構想、現行環境、既存の提案を批判的に統合し、PDAの長期的な不変条件、目標アーキテクチャ、移行アーキテクチャ、データ契約、セキュリティ／統治、運用、評価、段階的実装順序を一貫した設計文書としてリポジトリへ残すことである。

## 1. 最初に必ず読むもの

設計判断を始める前に、次を省略せず全文読め。

1. `personal_delegate_agent_plan.md`
   - PDAの目的、中心命題、Phase 1〜11、最終到達状態を記した構想上の一次資料。
2. `pda_minipc_setup_record.md`
   - ミニPC、Hermes、Codex、Claude Code、Open WebUI、Firecrawl、MCP、systemd等の現行構成と過去の設計判断の記録。ただし記述時点以降に変化している可能性がある。
3. `.hermes/plans/2026-07-20_202237-pda-current-state-and-next-roadmap.md`
   - 現状分析と実装案。これは承認済み仕様ではなく、批判・修正・棄却可能な仮説である。特に「Phase 3.5」「append-only Event Ledger」「SQLite/WAL/FTS5」「claim/evidence分離」「Context Pack」「共通stdio MCP」「memory providerはprojection」という提案を、追認せず独立に評価せよ。
4. リポジトリ内に新たな文書、設定、コード、指示ファイルがあれば、それらも読むこと。
5. `git status`、ファイル一覧、直近のgit履歴を確認し、追跡済みの史料と未追跡の提案を区別すること。

必要なら、秘密情報に触れない範囲でホストの現状をread-onlyに確認してよい。ただし、認証情報、token、credential file、`.env`本文、個人会話本文、会社情報を読んだり設計文書へ転記したりしてはならない。ライブ状態と文書が矛盾する場合は、確認日時・確認方法・不確実性を明示すること。

変化しやすい製品仕様や技術制約を根拠にする場合は、可能な限り公式一次資料を調査し、URLと確認日を記載すること。古いブログ記事や推測を仕様上の事実として扱わないこと。特にHermes Agent、Claude Code、MCP、Open WebUI、Firecrawl、Tailscale、SQLite、systemd、Docker／rootless container、バックアップ方式については、重要な前提を公式資料で確認せよ。

## 2. 資料の扱い方

次の区分を設計文書全体で厳守せよ。

- Fact: 文書、実機確認、公式仕様で検証できた事実
- Requirement: ユーザーの目的または構想から導かれる要求
- Assumption: 未確認だが設計上いったん置く仮定
- Proposal: 採否未確定の設計案
- Decision: 比較検討後に本設計で採用する判断
- Open Question: ユーザー判断または追加検証が必要な事項

資料間の矛盾を黙って平均化してはならない。矛盾一覧を作り、どちらを採用したか、なぜか、追加確認が必要かを示せ。既存ロードマップの語彙や技術選定にアンカリングされず、必要ならフェーズ定義、順序、構成要素、技術スタックを変更せよ。ただし、変更理由と移行影響を明記すること。

## 3. PDAとして守るべき中心命題

設計は少なくとも次の原則を満たさなければならない。原則間に緊張がある場合は、優先順位と解決方法を示せ。

1. PDAは単一LLM、単一agent runtime、単一UI、単一memory providerではない。
2. 本人に帰属するコンテキスト、活動履歴、判断履歴、判断基準、プロジェクト状態、統治条件がPDAの継続性を担う。
3. Hermes、Claude Code、Codex、ChatGPT、将来のruntime／modelは交換可能な実行主体である。
4. コンテキストの正本と統治条件を、交換対象であるruntime内部だけに置かない。
5. raw source、抽出された主張、決定、選好、命令、推測を区別し、出典、時刻、有効期間、revision、失効、矛盾、利用履歴を追跡できること。
6. 外部文書、Web本文、チャット履歴、tool outputは原則としてuntrusted dataであり、命令へ自動昇格させない。
7. 自己改善を可能にする一方、評価条件、承認境界、監査記録、復元手段を自己正当化によって無効化できないこと。
8. 本人がデータと鍵を管理し、特定vendorからexport／再構築可能であること。
9. 会社情報と個人情報の境界を維持すること。会社情報は明示的な許可と分離構成が成立するまでdefault denyとすること。
10. 高度な最終系を描くだけでなく、現在の小型ミニPC、現行サービス、個人運用、限られたRAM／保守時間で段階的に成立すること。
11. 復元可能性、監査可能性、可逆性を、取り込み量や自律性より先に確立すること。
12. 「すべてを保存すること」自体を目的化せず、最小化、除外、retention、削除要求、legal／contractual boundaryを設計すること。

## 4. 必ず答える設計上の問い

全体設計では、最低限次を具体的に答えよ。

### 4.1 システム境界と継続的な自己

- 何をPDA本体と呼び、何をadapter、runtime、tool、UI、projection、external sourceと呼ぶか。
- 現在のHermes中心構成と、最終的なruntime非依存PDAの境界はどこか。
- modelやorchestratorを交換しても維持すべきidentity／continuity invariantは何か。
- canonical state、derived state、cache、ephemeral stateの所有者と再構築方法は何か。
- 各構成要素のread/write authorityとtrust levelは何か。

### 4.2 Context Spine／データ設計

- 取り込み、正規化、保存、revision、削除／tombstone、retraction、deduplication、provenance、temporal query、entity resolution、claim lifecycle、conflict handlingの全経路。
- source event、artifact、entity、claim、decision、preference、constraint、project state、task、run、context pack、gate verdict、approval、audit eventの関係。
- 正本を何に置くか。append-only ledgerを採用するか、別方式にするか。その理由と代替案。
- SQLite／PostgreSQL／event store、FTS／vector retrieval／graph DB、blob storeの役割分担と導入条件。
- 日本語検索、as-of再現、citation、削除伝播、schema migration、content-addressing、バックアップ／復元をどう保証するか。
- memory providerを使う場合の位置付け、同期方向、再生成、vendor lock-in回避。
- Context Pack相当のtask-scoped contextをどう構成し、token budget、根拠、矛盾、不明、security domainをどう表現するか。

最低限、以下のcontractについて、フィールド、識別子、versioning、状態遷移、idempotency key、error semantics、機密区分を示した具体例を含めよ。

- canonical event
- claim／decision
- task
- agent run／artifact
- context pack
- gate verdict
- human approval
- audit event

### 4.3 オーケストレーションとruntime交換

- ユーザー要求がintent、plan、context selection、runtime selection、tool execution、review、result統合、記憶更新へ進む状態機械。
- task ID、run ID、pack ID、artifact hash、runtime／model／prompt／tool versionをどう結ぶか。
- Hermes、Claude Code、Codex等へ同一タスクを渡すruntime-neutral contract。
- MCP stdio、SSH wrapper、HTTP API、queue等の境界と、それぞれの採否。
- 並列実行、handoff、再開、timeout、retry、cancellation、duplicate execution、partial failure、fallback、human escalation。
- runtime選択ルールの初期形と、将来の自動routing／評価学習への進化。
- agentごとのcapability、permission、cost、latency、privacy、qualityをどう登録・評価するか。
- runtimeがPDAの正本やgate policyを勝手に変更できない権限構造。

### 4.4 セキュリティ、プライバシー、統治

- trust boundaryとthreat model。少なくともprompt injection、memory poisoning、data exfiltration、confused deputy、credential leakage、supply-chain compromise、malicious connector、compromised runtime、stale／false claim、unauthorized self-modification、backup leakageを扱うこと。
- `public`、`personal`、`work`、`secret`等のsecurity domain、物理／論理分離、暗号鍵、index、backup、外部LLM送信条件。
- least privilege、capability grant、approval policy、break-glass、audit、retention、right-to-delete、redaction。
- proposer、executor、evaluator、approverの分離。
- gate policy、gold set、approval key、audit log、backup等のうち、core agentの書込み対象外にすべきもの。
- Phase 8以前にも必要な決定論的安全ゲートと、後段の認知ゲートの区別。
- 自己改善／自己改変の提案、sandbox、evaluation、canary、承認、反映、rollback、失敗隔離の完全な流れ。

### 4.5 配備、運用、信頼性

- 現行ミニPC上のdeployment topology。process／container／systemd／network／volume／port／user／permission境界。
- Open WebUI、Hermes API、Dashboard、Gateway、Firecrawl、PDA core servicesをどう管理し、二重管理を避けるか。
- LAN、loopback、private container network、Tailscale、TLS、認証、ACLの順序と到達可能性。
- secret management、config management、version／digest pin、upgrade、migration、rollback。
- health check、structured log、metric、trace、audit、alert、容量監視。
- RPO／RTO、snapshot、encrypted off-host backup、fresh-host restore drill、disaster recovery。
- 障害モードごとのdegraded mode。Hermes停止、runtime停止、ledger破損、index再構築、ネットワーク断、LLM vendor停止、disk pressure、connector異常を含めること。
- 現行ハードウェアでのCPU、RAM、disk、latency、保守負荷の概算budgetと、別ホスト／managed serviceへ分離する閾値。

### 4.6 評価とフェーズ設計

- 構想のPhase 1〜11をそのまま採用する必要はないが、全要求を漏れなく最終系へ写像すること。
- 「機能PoC」「運用完了」「評価完了」を区別し、現在地を再判定すること。
- 各phase／milestoneにentry criteria、exit criteria、測定方法、test evidence、rollback条件、依存関係を定義すること。
- retrieval、citation、temporal correctness、unsupported answer、cross-runtime continuity、routing、gate quality、recovery、自律性についてgold setとmetricを設計すること。
- metricの数値は根拠なしに断定しない。初期仮説、測定方法、再調整条件を区別すること。
- 最初のvertical sliceは、価値を実証しつつ最終アーキテクチャを誤って固定しない最小範囲とすること。
- 直近90日相当の実施順序はcalendar dateを捏造せず、依存関係、relative size、critical path、stop/go decisionで示すこと。
- Phase 11までの長期ロードマップは、近いphaseほど具体的、遠いphaseほど不変条件と評価条件中心にすること。

## 5. 比較検討が必要な主要判断

次の論点は少なくとも2案以上を比較し、採用案、棄却案、採用条件の変化、移行コストを記録せよ。

1. canonical store: SQLite/WAL中心か、PostgreSQLか、専用event storeか。
2. data model: event ledger＋projectionか、mutable relational state中心か、graph-firstか。
3. retrieval: FTS baseline、embedding/vector、knowledge graph、hybridの導入順序。
4. runtime interface: MCP stdio、SSH stdio、local HTTP、message queue。
5. orchestration: Hermesを当面のorchestratorとして拡張するか、PDA独自control planeを分離するか。
6. deployment: host systemd、rootless container、root-managed containerの役割分担。
7. work／personal分離: domain columnだけか、別DB／別key／別process／別hostか。
8. claims: manual／deterministic firstか、LLM extraction firstか、承認workflow。
9. memory provider: built-in、外部provider、独自projectionの位置付け。
10. self-improvement governance: 何を自動化し、何を人間承認に固定するか。

判断は流行や一般論ではなく、このPDAの目的、現行資産、個人運用、将来のcore交換可能性、復元性、データ境界を基準に行うこと。

## 6. 作成する成果物

既存の構想書とセットアップ記録は史料として保持し、原則として上書きしないこと。設計成果物は日本語で記述し、識別子、API名、schema名は英語でよい。

最低限、次を作成せよ。

1. `docs/design/README.md`
   - 設計文書の入口、読む順序、文書のauthority、更新規則。
2. `docs/design/01-requirements-and-invariants.md`
   - 目的、non-goals、system boundary、用語、不変条件、requirement traceability。
3. `docs/design/02-current-state-and-gaps.md`
   - verified current state、資料間の矛盾、現在phase、gap／risk、移行制約。
4. `docs/design/03-target-architecture.md`
   - logical／deployment architecture、component responsibility、source of truth、read/write authority、主要sequence、failure boundary。
5. `docs/design/04-context-spine-and-data-contracts.md`
   - data lifecycle、canonical／derived model、schema contract、state machine、retrieval／Context Pack、migration／deletion／rebuild。
6. `docs/design/05-orchestration-and-runtime-contracts.md`
   - task／run lifecycle、runtime adapter、MCP／API contract、routing、handoff、parallelism、failure handling。
7. `docs/design/06-security-privacy-and-governance.md`
   - data classification、trust boundary、threat model、permission／approval、audit、self-modification governance。
8. `docs/design/07-deployment-operations-and-recovery.md`
   - service topology、network、secrets、observability、backup／restore、upgrade／rollback、SLO／RPO／RTO hypothesis。
9. `docs/design/08-evaluation-and-phase-gates.md`
   - evaluation harness、gold sets、metrics、phase entry／exit、evidence requirements。
10. `docs/design/09-transition-roadmap.md`
    - 現状から最終系へのdependency-ordered roadmap、最初のvertical slice、critical path、stop/go、migration／rollback。
11. `docs/design/10-open-questions-and-decisions.md`
    - user decisionが必要な事項を、選択肢、推奨、影響、回答期限となるdecision point付きで整理。
12. `docs/adr/`
    - 本設計で十分な根拠を持って採用する主要判断をADRとして記録する。少なくともcanonical source of truth、memory providerの位置付け、runtime-neutral contract、security-domain分離、self-modification authorityを扱うこと。未確定事項を確定済みADRとして偽装しないこと。

文書を不必要に分断したり、同じ説明を複製したりしないこと。`README.md`を索引にし、詳細は相互参照すること。

## 7. 必須の図と表

MermaidまたはMarkdownで、最低限次を含めよ。

1. 現行deployment topology。
2. 最終logical architectureとtrust boundary。
3. data ingestからevent、claim、projection、retrieval、Context Packまでのdata flow。
4. user requestからplan、context、runtime、tool、gate、result、memory updateまでのsequence。
5. runtime handoff／fallback／resumeのsequence。
6. self-improvement proposalからsandbox、evaluation、approval、canary、rollbackまでのsequence。
7. core runtime交換時に維持されるものと交換されるもの。
8. component responsibility／source-of-truth／read-write authority matrix。
9. requirement-to-component-to-phase-to-test traceability matrix。
10. phase dependency graphとcritical path。

図と本文を乖離させないこと。図中のcomponent名、interface名、data object名は本文およびcontractと一致させること。

## 8. 品質基準

- 抽象語だけで終わらせず、interface、state transition、failure mode、ownership、testabilityまで落とすこと。
- 逆に、未検証のライブラリ名や製品名を早期に固定しすぎないこと。採用条件と交換境界を先に定義すること。
- 正常系だけでなく、重複、順序逆転、partial write、stale data、conflict、deletion、compromise、restore、runtime outageを設計すること。
- 各canonical objectにstable identity、schema version、provenance、security domain、timestamps、lifecycleを定義すること。
- すべての自動判断について、根拠、confidence／uncertainty、authority、override、audit pathを示すこと。
- 各重要componentについて「失われた場合に何から再構築するか」を明記すること。
- 各重要decisionについて「どの条件なら見直すか」を明記すること。
- 運用者が一人であることを考慮し、分散システムの複雑性を正当化できない限り導入しないこと。
- 現行ミニPCで成立するnear-term architectureと、最終系を混同しないこと。transition architectureを明示すること。
- 会社データの取り込みを当然視しないこと。法務、契約、組織policy、データ境界が未確認ならblockedとすること。
- 「AIが評価するから安全」としないこと。決定論的policy、OS権限、network、cryptographic control、human approvalを組み合わせること。
- 読者が次の実装タスクをissueへ分解できる具体度にするが、この作業ではproduction codeを実装しないこと。

## 9. 作業制約

1. 今回は設計文書とADRだけを作成する。PDA本体、connector、DB、service、systemd unit、container、network、Hermes設定を実装・変更しない。
2. package install、service restart、reboot、port変更、credential変更、実データ取り込み、外部送信を行わない。
3. secretや個人／会社データをcommitまたは文書へ含めない。
4. 既存の2つの主要文書と既存roadmapは削除しない。修正が必要なら、まず新設計文書に差分提案として記録する。
5. git commit、push、branch rewriteを行わない。
6. 不明点を都合よく仮定して埋めない。設計を進められる安全な仮定は明示し、ユーザー判断が必要なものはOpen Questionへ送る。
7. ただし質問待ちで作業を止めない。安全なdefaultで全体設計を完成させ、決定点を明確にすること。

## 10. 進め方

1. repository inventoryと資料読解を行う。
2. requirement、fact、conflict、assumptionを抽出する。
3. 現在地を独立に再評価する。
4. 主要論点ごとに代替案を比較する。
5. invariantsとcontractを先に定め、その後にtechnology mappingを行う。
6. near-term、transition、target architectureを分けて設計する。
7. 文書とADRを作成する。
8. 最後にadversarial self-reviewを行う。少なくともdata architecture、security/privacy、SRE/recovery、agent orchestration、self-modification governanceの観点で反証を試み、重大な穴を本文へ反映する。
9. 全要求がtraceability matrixに現れること、図と本文とcontractが一致すること、phase gatesが測定可能であることを確認する。
10. `git diff --check`を実行し、可能な範囲でリンク、Mermaid syntax、文書内参照を検査する。検査方法と結果を報告する。

必要ならsubagentをレビュー用途に使ってよい。ただし、全体設計の統合、矛盾解消、最終判断は現在のFable/maxセッション自身が行い、複数agentの出力を未統合のまま並べないこと。

## 11. 最終応答の形式

作業完了時の応答には、次だけを簡潔にまとめよ。

1. 作成・変更したファイル一覧。
2. 最重要の設計判断と、既存roadmapから変更した点。
3. 現在地の最終判定。
4. 最初に実施すべき一つのvertical slice。
5. ユーザー判断が必要なblocking decision。
6. 実行した検証と結果。
7. 実装、commit、service変更を行っていないことの確認。

設計書の要約だけで済ませず、必ず指定ファイルをリポジトリ上へ実際に作成し、整合性検査まで完了させよ。
