# ADR-0003: runtime非依存契約（ContextPack / TaskSpec / RunResult）をMCP stdio主経路で提供する

- Status: Accepted
- Date: 2026-07-20
- 対応Decision: D-4（接続経路）、D-5（orchestration位置付け）
- 関連: [design/05](../design/05-orchestration-and-runtime-contracts.md)、INV-1、INV-8

## Context

PDAはHermes・Claude Code・Codex・将来runtimeへ同一のコンテキストとタスクを渡せなければ
ならない（R-01, R-12, R-16）。確認済み事実（2026-07-20）: MCP仕様（rev 2025-11-25）の標準
transportはstdioとStreamable HTTP。Claude Code・Codex CLI・HermesはいずれもMCP clientとして
stdioサーバーを登録できる。ホスト間はSSHでstdioを延長する構成が実績を持つ（REC§5.16）。

## Decision

1. **契約が正本、経路は従属**: runtime連携の中心は ContextPack（[design/04 §4.5](../design/04-context-spine-and-data-contracts.md)）、
   TaskSpec / RunResult（[design/05 §2](../design/05-orchestration-and-runtime-contracts.md)）の
   JSON契約とし、transportはこれを運ぶ手段に留める
2. **主経路はMCP stdio**（`pda-mcp`）。同一ホスト内で露出ゼロ、全対象runtimeがclient対応済み
3. **ホスト間はSSH-wrapped stdio**（`ssh agent-node pda-mcp` 形式）。認証・暗号化はSSH鍵に委ねる
4. **Streamable HTTPは保留**: 常駐server・複数リモートclientが必要になった時点で、
   仕様の要求（Origin検証MUST・localhost bind SHOULD・認証SHOULD）を満たす形で導入
5. **message queueは不採用**: 非同期待ち行列はSpine内の `tasks/runs` テーブル＋pollingで実現
6. **orchestrationの位置付け（D-5）**: near-termのorchestratorはHermesを継続利用する。
   ただしtask/run/packの状態はSpine側の契約に記録し、orchestrator交換をM6で実証する。
   PDA独自のcontrol plane常駐化（pda-spined）は権限分離の必要（M3）から導入し、
   「Hermes競合の第二orchestrator」を先行して作らない

## Alternatives considered

### 独自HTTP APIを最初から立てる — 棄却

- 認証・TLS・CORS・常駐管理のコストが増える一方、現時点のclientは全てMCP stdioで足りる。
  ネットワーク待受を増やすことは[07 §4](../design/07-deployment-operations-and-recovery.md)の
  最小化方針にも反する

### runtimeごとの個別統合（Hermes memory API直結等） — 棄却

- runtimeごとにN個の統合を持つとINV-1が空洞化する。契約1つ＋薄adapter Nが正しい依存方向

### message queue（Redis/RabbitMQ等の流用含む） — 棄却

- 単一運用者・低頻度委任にブローカー運用は過剰（NG-3）。FirecrawlのRabbitMQは
  Firecrawl内部実装であり、PDAが相乗りすると障害・upgrade結合が生まれる

### PDA独自orchestratorの即時開発 — 棄却

- Hermesの対話・gateway・承認機構は稼働資産であり、先に置き換えると価値実証が遅れる。
  交換可能性は「契約の外部化＋M6の交換実証」で担保する

## Consequences

- (+) runtime追加はadapter1枚＋MCP登録で済む。契約はgold set（GS-CONTINUITY）で回帰検証できる
- (+) stdio主経路によりネットワーク面の攻撃面が増えない
- (−) stdioサーバーはclientごとにプロセスが起動する。Spine排他はSQLite側の
  短トランザクション設計で吸収する（[ADR-0001](0001-canonical-store-sqlite-append-only-ledger.md)）
- (−) SSH経由MCPはセッション断で切れる（REC§5.16の既知制約）。再接続はclient側の再起動で行う

## Revisit conditions

1. 複数のリモートclientが常時接続する必要が生じた → Streamable HTTP（認証＋tailnet内）導入
2. 複数ホストでの分散実行が確定した → queue再評価
3. Hermesの保守停止・破壊的変更 → orchestrator交換の前倒し（M6を待たない）
