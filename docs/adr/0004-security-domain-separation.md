# ADR-0004: security domainを4区分とし、workは物理分離が成立するまでdefault denyとする

- Status: Accepted
- Date: 2026-07-20
- 対応Decision: D-7
- 関連: [design/06 §2](../design/06-security-privacy-and-governance.md)、INV-6、INV-9、INV-12

## Context

PDAは個人情報を扱い、将来的には会社関連情報（Slack/Backlog/会社Git/会社Claude履歴）の
統合も構想に含まれる（PLAN §6.3-6.4）。一方で、会社情報の私有インフラへの複製は法務・契約・
組織policyの確認なしに行えず（brief命題9）、漏洩時の影響は個人情報と質が異なる。
既にアカウント分離原則（会社Team plan=開発PC、個人プラン=ミニPC）が運用されている（REC§5.18）。

## Decision

1. security domainを `public` / `personal` / `work` / `secret` の4区分とし、
   全canonical objectの必須属性とする
2. **work**: default deny。connectorの取込・保存・送信すべてを拒否し、
   `spine-work.db` という **DBファイル自体を作らない**（denyの物理表現）。
   解禁の必要十分条件: 会社の書面許可＋別DBファイル＋別暗号鍵＋別backup repo
   （必要に応じ別プロセス/別ホスト）。解禁判断はOQ-4
3. **secret**: 本文保存禁止。locatorとredacted metadataのみ許可（APIキー・トークン・
   認証画面等。T-SECRET-EXCLUDEで検証）
4. **public / personal**: `spine-personal.db` 内のdomain列で区分し、egress policy・
   pack組成・検索フィルタの単位とする
5. domain判定はsource単位の静的設定とし、判定不能・未知domainは拒否（fail-close）
6. claimのdomainは根拠eventの最高機密度以上（downgrade禁止）

## Alternatives considered

### domain列のみ（単一DB・単一backupにwork混在） — 棄却

- backup漏洩・DBファイル流出・検索の設定ミスで会社情報が一括露出する。爆発半径がDB単位に
  なる物理分離（別ファイル・別鍵・別repo）が、SQLite採用下ではほぼ無コストで得られる

### 最初から別ホスト分離 — 棄却

- workを扱う予定が未確定の段階でホストを増やすのは過剰（NG-3）。閾値・条件のみ先に定義する

### workを暗黙にpersonal扱いで取り込む — 棄却

- brief命題9への直接違反。取り込み側の判断ミスを防ぐため「fileが存在しない」レベルで拒否する

## Consequences

- (+) 「会社情報が混入していないこと」をファイル一覧・backup対象一覧で機械的に監査できる
- (+) work解禁時の追加要件が明文化され、なし崩し統合を防ぐ
- (−) 会社業務も含む「本人の全活動の統合」という構想の一部（PLAN §6.3-6.4）は
  OQ-4が解決するまでスコープ外に留まる（R-04/R-05はBlocked管理）
- (−) 私物・会社の境界事例（例: 個人PCで読んだ業務関連記事）の判定規約が必要
  → 初期規約は「情報の帰属主体」基準（会社システム由来=work）とし、迷う場合はpersonalに
  入れず取り込まない

## Revisit conditions

1. OQ-4で会社データ統合を目指す決定がなされ、書面許可・分離構成の準備が始まったとき
2. domain区分が実運用で不足（例: 家族domain等）と判明したとき（区分追加はschema versionで管理）
