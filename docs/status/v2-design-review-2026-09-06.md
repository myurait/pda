# PDA v2 全体設計再評価 — 独立読み取り専用レビュー

- レビュー日: 2026-09-06 JST
- 対象: `docs/design/v2-gap-assessment-2026-09-06.md`、`docs/research/pda-v2-platform-landscape-2026-09-06.md`、`docs/roadmap/v2-01-whole-system-reassessment.md`、`docs/roadmap/current-priority.md`、`pda_charter.md`
- 範囲: 約5分のbounded review。本文間の要求・権限・証拠・停止/復帰・候補比較の整合を確認。外部の追加監査、本番操作、全テスト、秘密/credential操作は未実施。
- 結論: **FAIL（条件付き）**。設計の方向性は概ね合っているが、次段階（特にR2/R3）へ進める前にF-1の承認ゲートを明文化し、F-2/F-3を最小修正すべき。

## 重大な指摘（最大3件）

### F-1 [High] R2/R3開始の承認境界が明示的に閉じていない

- 根拠:
  - `docs/roadmap/current-priority.md:12` は、現行許可を文書・調査・隔離probe・commit/pushに限定し、基盤選定、service再起動、本番変更、自律改善再開を包括許可しないとする。
  - `docs/roadmap/v2-01-whole-system-reassessment.md:31` はR1で候補・予算を固定し、ownerが方向と許可範囲を判断するとする。
  - 同`:33` のR3はruntime/memory/UIの比較に加えてmigration/updateまで含む。同`:37` は公開調査、R1整理、runtime read-only確認を並行可能とするが、R1完了からR2/R3へ進む明示的なowner entry approvalがない。
  - 同`:80-82` は独立レビュー・owner承認・現許可の非包括性を記載するものの、R3のprovider/managed候補、外部送信、料金、credential、runtime updateを開始する個別entry gateにはなっていない。
- 影響: 読者/実行者が「R1で候補と予算を固定した」ことをR2/R3開始許可と誤読し得る。現在の停止・provider/課金/外部送信禁止を越え、承認範囲が暗黙に拡大する。憲章第六条・第七条（`pda_charter.md:81,87-93`）の最終決定権・明示停止保持にも反する運用余地が残る。
- 最小修正案: `v2-01:31-37` のR1 exit後に、独立した「R2/R3 entry: owner明示承認」を追加する。承認前は合成・ローカル・read-onlyのみ、provider credential/課金、runtime install/update、managed外部送信、破棄を禁止。候補ごとにscope、budget、egress、cleanup、データ種別を束ね、R4/R5の採用・再開承認とは別であることを明記する。

### F-2 [Medium] 中心ループの「自動復帰」が明示停止を再開しない契約へ直結していない

- 根拠:
  - `docs/design/v2-gap-assessment-2026-09-06.md:52` は最小ループを「canary失敗時は旧正常版へ自動復帰 → 仕事・停止・記憶を照合」と表現する。
  - `pda_charter.md:89-93` は、復帰不能を正常に見せないこと、同一故障経路だけに依存しないこと、そして明示停止・承認境界・所有権を解除せず、無許可再開/重複作用を避けることを要求する。
  - 下流の`docs/roadmap/v2-01-whole-system-reassessment.md:59`（F5）と`docs/research/pda-v2-platform-landscape-2026-09-06.md:112`にはstop epoch/失効承認優先が書かれており、緩和材料はあるが、中心ループの一文だけでは自動rollback後に仕事を自動resumeしてよいようにも読める。
- 影響: 実装者が「旧版へ戻す」と「活動を続ける」を同一操作にして、stop後・approval失効後・effect不明時に再開する危険がある。F5が後段 fixture にしか現れないため、設計の主経路から停止保持が抜ける。
- 最小修正案: `v2-gap:52` を「旧正常版へ自動rollback（活動は自動再開しない。stop epoch/承認/実作用をread-backし、停止・失効・不明作用はhold/diagnosticのみ）」へ限定し、F5を参照する。resumeは停止状態・有効な同一digest・作用照合が確認できた場合だけ別の明示状態遷移とする。

### F-3 [Medium] 過去の部分実装をPriority 0の完了証拠と誤読できる

- 根拠:
  - `docs/roadmap/current-priority.md:20` は、五分 cadence、stall display、plan-registration enforcementを「implemented, deployed, and live-probe verified」と記述する。
  - 同`:38-46` はPriority 0自体を未完了とし、preemption、平易な報告、outcome/risk/action、五分可視性の全exit gateを要求する。
  - `docs/design/v2-gap-assessment-2026-09-06.md:20,29` は旧進行表示・過去完了表記を現在の再開許可/実効状態へ転記しないとし、`docs/roadmap/v2-01-whole-system-reassessment.md:30,88` もpostmortem・R2〜R5未完了を明示する。
- 影響: `current-priority:20` の部分機能の検証主張にartifact/probeへの直接リンクと「Priority 0全体ではない」という限定がないため、レビュー者が実装済み・運用達成済みと数え、未実証の通信完全性や継続性を過大評価し得る。新文書の慎重な証拠分類と読み手の受け取りがずれる。
- 最小修正案: `current-priority:20` を「以下の3部分契約のみが当時のstatus記録上、実装・反映・probe済み（Priority 0の完了または現行環境の独立再検証ではない）」と明記し、各artifact/probe IDを直結する。`v2-gap:20,29` と同じFact/歴史/未検証の区別を揃える。

## 指定観点の判定

- **ユーザー要求/憲章整合:** 概ね充足。第五条の自己改善中核、第六条の器交換可能性・保守/移行/廃止費、第七条の自己復帰・ユーザー救出非依存が、gap `:41-48`、research `:140-163`、roadmap `:12-24,70-88` に反映されている。
- **Hermes継続/スクラッチ誘導バイアス:** 重大な偏りは確認せず。research `:9,34-43,47-67,140-157` とroadmap `:14,39-47,76` はHermes、Letta、OpenClaw、managed、SDK、全面スクラッチを同じ要求/将来負担で比較し、Hermes既定・全面スクラッチ既定を明示的に退けている。
- **保守・sunk costの現実性:** 良好。既投資を無視も正当化もせず、cost sheet、更新・障害・退出・削除・vendor条件を比較対象にしている。ただしF-1のentry gateがないまま比較を開始しないことが前提。
- **復帰と明示停止:** 原則は整合（charter `:89-93`、research `:112,122`、roadmap F5 `:59`）。F-2のとおり中心ループの表現を明示的に狭める必要がある。
- **未実証を実装済みとする過大表現:** 新3文書は概して抑制的（gap `:29,33`、research `:13,25-28,110,161-163`、roadmap `:30-35,88`）。残るリスクがF-3の歴史的status記述。
- **次段階の承認拡大:** F-1。現許可は限定され、R4/R5には承認記載があるが、R2/R3 entryの個別承認が抜けている。
- **出典の主張支持:** bounded spot-checkでは重大な unsupported claimは確認しなかった。Hindsightの`[215]`はraw API snapshotにdocument transfer/export、embedding/DB ID除外、delete/clear系endpointがあり、research `:76,84`を支持する。DBOSの主張はcache結果（`dbos-probe/result.json`）の1回ずつの合成probeと整合し、research `:103-112`自身がharness再起動・単一host・非PDA統合という限界を明記している。親が生成中の`evidence/source-map.json`、`coverage.json`、repo内dbos添付の一時欠落は、依頼文どおりfindingにしていない。

## 検証・変更状況

- 対象5文書と憲章、関連する改訂記録、調査cacheの必要箇所を読み取り、行番号付きで突合。
- `git diff --check`: 成功。
- 本レビュー中、対象リポジトリのファイルは編集していない。作業開始時から、対象ブランチに既存のmodified/untracked変更（current-priorityを含む）が存在したため、stash/reset/checkoutは行っていない。
- 作成ファイル: `/home/user/.hermes/cache/research/pda-v2-20260906/design-review.md` のみ。
