# ADR-0001: 正本はSQLite/WALのdomain別ファイル上のappend-only ledger（ledger-first）とする

- Status: Accepted
- Date: 2026-07-20
- 対応Decision: D-1（canonical store）、D-2（data model）
- 関連: [design/04](../design/04-context-spine-and-data-contracts.md)、INV-1/2/3/11

## Context

PDAの継続性はruntime外部に置くcanonicalなデータ層（Context Spine）に依存する（INV-1）。
要求はprovenance・as-of再現・retraction・監査・export・単一運用者での再構築容易性
（R-08, R-20, R-22, R-27）。実行環境は16GB RAMのミニPC1台、運用者は本人1名である。
書き手は単一プロセスではない: pda-mcpは各runtime（Hermes/Claude Code/Codex）ごとに
別プロセスとして起動し（[ADR-0003](0003-runtime-neutral-contracts-over-mcp-stdio.md)）、
`context_pack` のpack記録・audit追記を行う。加えてpda-cli ingestとorchestrator書込が並行し得る。
すなわち **複数プロセスからの低頻度並行書込** が常態であり、書込直列化の規約が必要になる。

## Decision

1. **ストレージ**: SQLite（WALモード）を採用する。security domainごとに独立したDBファイル
   （当面 `spine-personal.db` のみ。`work` はファイル自体を作らない）。大きな本文・添付・成果物は
   ファイルシステム上のcontent-addressed blob store（`blobs/sha256/...`）に置き、DBはhash参照する
2. **データモデル**: ledger-firstとする。
   - すべての観測は追記専用の `events`（＋`event_edges`）へ入る
   - claim/task/run/approval等の運用テーブルは、対応するlifecycle eventと
     **同一トランザクション** で更新する（dual-writeの不整合をACIDで排除）
   - 検索索引・project_state等のprojectionは常にSpineから再生成可能とする
   - 運用テーブルとevent列の等価性は `pda verify replay` で継続検証する
3. **削除との両立**: 追記原則の例外はredaction手続きのみ（本文の物理削除＋hashと削除記録の保持。
   [design/04 §7](../design/04-context-spine-and-data-contracts.md)）
4. **並行書込の直列化**: 複数プロセスの低頻度並行書込を前提とし、全書込を `BEGIN IMMEDIATE` で
   開始する単一トランザクションで行う。audit hash chainの追記は「chain末尾読取→entry_hash計算
   →insert」を同一トランザクション内で完結させ、2プロセスが同一 `prev_hash` を読んでchainが
   フォークするのを防ぐ。`busy_timeout` を設定し、`SQLITE_BUSY` はタイムアウト付き再試行、
   超過時のみ `E_BUSY` を返す（[design/04 §3](../design/04-context-spine-and-data-contracts.md)）

## Alternatives considered

### PostgreSQL — 棄却

- 利点: 同時書込・行ロック・豊富な拡張・将来の多プロセス化
- 棄却理由: 常駐サービスが1つ増え、upgrade・チューニング・バックアップ（物理/論理）の
  運用負荷が単一運用者予算（A-05）を侵食する。現要件に同時多重書込は存在しない。
  SQLiteはファイル=DBでbackup・export・fresh-host復元が単純（INV-11に直結）

### 専用event store（Kafka / EventStoreDB等） — 棄却

- 棄却理由: 分散基盤の導入はNG-3に反する。パーティション・retention・クラスタ管理は
  個人規模で正当化できない。append-only性はSQLiteのAPI設計（UPDATE/DELETE非公開）で十分実現できる

### mutable relational state中心（履歴テーブル補助） — 棄却

- 利点: 実装が直感的
- 棄却理由: provenance・as-of・retraction・監査が後付けのアドホック機構になり、
  「どの時点で何を知っていたか」の再現（R-27）が保証しづらい。要求集合が実質的に
  イベントログの性質そのものである

### 純イベントソーシング（全状態をreplayのみで導出） — 棄却

- 棄却理由: すべての読み取りにprojection管理が必要になり、個人開発の複雑性予算を超える。
  ledger-first（同一Tx運用テーブル）はreplay検証可能性を保ちながら実装を単純化する

### graph DB first（Neo4j等） — 棄却

- 棄却理由: 関係クエリの必要性が未実証。gold setで不足が数値化されるまで導入しない
  （D-3の採用条件に委ねる）

## Consequences

- (+) backup=ファイルsnapshot（Online Backup API / `VACUUM INTO`）で完結。復元・exportが単純
- (+) FTS5が同一DB内で完結し、追加サービスなしで日本語baseline検索が立つ
- (+) domain別ファイルにより、work解禁時の物理分離（別DB・別鍵・別backup）が自然に実装できる
- (−) 複数プロセス並行書込のため、`BEGIN IMMEDIATE`＋busy_timeout＋短トランザクションの
  直列化規律が必要（Decision 4）。高頻度並行書込には向かない（現要件は低頻度で問題にならない）
- (−) 日本語2字語のFTS制約など、SQLite内での検索品質には上限がある（D-3の見直し条件で管理）
- (−) redaction採用により「hash鎖は残るが内容再検証は不可能」なitemが生じる（受容済みトレードオフ）

## Revisit conditions

次のいずれかが実測で示されたら本ADRを再評価する:

1. 複数ホストからの同時書込が必要になった
2. Spine DBが約50GBを超え、かつVACUUM/backup時間が運用窓に収まらない
3. 書込競合・ロック待ちが対話性能を継続的に劣化させた
4. レプリケーション（ホットスタンバイ）が可用性要件として確定した

移行コスト見積り: schemaはSQL標準寄りに保ち、PostgreSQL移行はスキーマ変換＋一括ロードで
可能な設計を維持する（SQLite固有機能への依存はFTS5とpragmaに限定する）。
