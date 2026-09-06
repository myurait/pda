# v2-01: 全体設計の見直し — 最初のロードマップ

- 状態: **文書・公開調査の初期成果あり。基盤選定・実装・運用再開は未承認**。
- オーナー決定日: 2026-09-06 JST。「全体設計の見直しをv2最初のロードマップとする」。
- 最上位規範: [PDA憲章](../../pda_charter.md)。[改訂記録](../status/charter-self-integrity-decision-2026-09-06.md)。
- 入力: [gap assessment](../design/v2-gap-assessment-2026-09-06.md)、[広域基盤調査](../research/pda-v2-platform-landscape-2026-09-06.md)。
- 追跡正本: Hermes default board / tenant `pda-improvement` / 未割当Triage `t_395213b7`。子カードの自動割当やworker実行は開始しない。
- 用語: ここでの「PDA v2」は失敗後の再設計を指す。停止した「scope control v2」のpatch/再有効化を意味しない。

## 1. このロードマップが置き換える順序

2026-08-22以前の「Hermes中心で改善サイクルを構築し、identity/core交換は後段」という実装順を、今後の既定にはしない。自己完全性を先送りせず、最初の価値を **改善を任せても、失敗の後始末と文脈再構築がオーナーへ戻らないこと** に置く。

既存実装・文書・backup・Kanban・skillsは検証と再利用の資産であり、実装済みという理由だけで残さない。逆に、過去の失敗を理由に全てを捨てて全面スクラッチへ進まない。Hermes継続、部分利用、Letta/OpenClaw等への交換、既製SDKによる組立、managed/混成構成を同じ要求で比較する。

このロードマップは設計再評価の順序の正本である。既存の統治・承認境界、停止指示、情報区分は引き続き有効で、緩和・再開は別の明示承認を要する。通信/停止要求への即応も全段階の制約である。

## 2. 非目標と投資上限の原則

今回の許可で本番のruntime、provider、memory、UI、service、cron、secret、権限を変更しない。scope control v2を修理して再開しない。現在の失敗を無かったことにするstatus変更をしない。

初期に作ってよい設計上の独自資産は、PDA固有の受入fixture、最小contract、必要なadapter、独立復帰の結線までに絞る提案とする。万能Context Spine、汎用workflow engine、全履歴の独自DB移行、専用chat製品の同時開発を前提にしない。調査用のprobeは投資済みだから本番へ昇格させない。

実験予算（時間・provider費用・最大追加service・維持するadapter範囲）はR1で明文化する。今回は予算の根拠がないため、人日・月額・総合点を捏造しない。候補を増やす時は、どの未解決の判断が変わるかを説明する。

## 3. 段階と証拠

| 段階 | 内容 | 成果と完了条件 | 現在 |
|---|---|---|---|
| R0: 失敗を固定する | scope v2自己閉塞のpostmortem。最初の故障点、拒否/沈黙経路、救出に必要だった操作、同じ権限に依存していた箇所を証拠から再構成 | 事実/仮説/不明を分けた時系列、根本原因候補、合成再現。独立評価者が因果の飛躍を検査。新設計が回避すべき失敗fixtureができる | **未完了**。今回のgapはpostmortemの代替ではない |
| R1: 要求・所有・比較条件を固定 | G1〜G12を受入契約へ落とす。既存stateの所有者、可用性の故障範囲、承認/停止、data-flow、候補と予算を固定 | 境界図、store/secret/backup/export台帳、同条件fixture、候補の失格条件、将来費用sheet。オーナーが方向と許可範囲を判断できる | 初期gapと候補調査を本書に添付。未確定 |
| R2: 独立復帰の小実証 | 主agent/runtimeが壊れた状態で、別の故障単位の復帰経路が最終正常版へ戻す。作用照合と停止保持も同時に試す | 合成環境で下記F1〜F9を満たし、復帰主体・制御DB・権限・ログを実物で確認。オーナーの救出操作なし。PDA側で勝手に再開しない | 未着手。DBOS単体probeは前提調査のみ |
| R3: 基盤・記憶・UIの比較 | 完成型runtimeとmanaged案の代表を同じ小さな活動で比較。memoryは別の仮説として評価。migrationとupdateも試す | どの独自codeが不要になったか、残る運用/退出費、失敗時挙動、日本語判断品質、同一activityのUI操作を比較。採用/不採用/保留を理由付き記録 | 未着手 |
| R4: 全体設計の選択と外部評価 | 採用構成、再利用/廃止/延期、最小adapter、復帰・権限・migration契約をADRへ確定 | 実験結果とartifact digestに結び付いた独立レビュー。反証への応答とrollback plan。オーナー承認 | 未着手 |
| R5: shadow → canary → 最初の一周 | 承認後、非作用shadowから単一の承認済み改善へ。canary失敗で復帰し、活動・記憶・経験を次へ返す | F1〜F12を実環境に近い範囲で実証。段階ごとに独立した停止・rollback。オーナーに救出を依頼しない一周が確認される | 未承認。ここで初めて自律改善再開の可否を決める |

順序はゲートの依存関係であり、一律の長期工程化ではない。公開調査、R1の整理、runtimeのread-only確認は並行できる。ただし復帰を後回しにしてR3の便利機能を本番へ積まない。R0が新たな原因を示したら比較条件を修正し、既存のprobe結果を無条件に使わない。

### R2/R3への明示entry gate

R1の文書が完成しただけでは、R2/R3の実証batchは開始しない。対象candidate、隔離環境、変更対象、データ種別、外部送信先、credential/課金経路、時間・費用の上限、停止・cleanup/破棄範囲を提示し、**オーナーの明示entry承認**を得る。この許可はR4の採用判断やR5の本番canary/自律改善再開とは別である。

承認前に継続できるのは、現許可内の公開source調査、既存証拠・合成fixtureの分析、read-only確認である。R2/R3用のruntime install/update、provider credential利用、課金、managedへのデータ送信、実データmigration、環境の破棄を包括許可しない。今回既に行ったDBOS単体の合成・使い捨てprobeは調査証拠であり、R2/R3のentry承認取得や完了を意味しない。

## 4. R1で比較する構成と選抜順

まずHermes対照系と、現行Letta harnessの完成型を比較する。Hermesは公式拡張でlocal patchを減らせるか、LettaはMemFS・自己改変・活動継続を少ない自作で得られるかを見る。OpenClawもready-madeの候補として残し、主候補のgapが同製品で減るなら同条件に加える。

managed代表にはCloudflare Agentsまたはmanaged durable executionとlocal executorの混成を置く。サービス委託で運用を減らす案を「個人用だから」「既存がlocalだから」と除外しない。data custody、認証/課金、ネットワーク障害、exportが許可範囲に収まらなければ、その証拠を理由に不採用/保留にする。

LangGraph/Deep Agents、Microsoft Agent Frameworkは、完成型が失格となった具体的差分を既製primitiveで埋める候補とする。Claude Code/Codex/OpenHandsは実行lane、Dify/n8nは定型workflow laneとしても比較し、全体主体を置換する場合と混ぜない。

memoryはHermes採否から独立した評価軸にする。files/FTSを必須対照に、Hindsight（経験/reflect）、Honcho（user modeling）、Graphiti（時間/関係）の異なる仮説を段階的に比べる。全部を常駐採用しない。最小導入が重すぎる時のMem0、階層contextが必要な時のOpenViking、統合knowledge pipelineが必要な時のCogneeという代替も保持する。勝ったsemantic memoryへ活動・承認の正本を自動移管しない。

## 5. 受入fixture案

全項目はこれから実証する目標であり、現行PDAの達成報告ではない。私的な本物の会話・secret・会社データではなく、合成fixtureから始める。

| ID | Given / When | Then: 判定できる結果 |
|---|---|---|
| F1 | 正常に動く主agentを停止/kill | 独立主体が異常を検出し、許可された正常版へ戻す。UI/診断の別経路から現況を確認できる |
| F2 | 新releaseが起動しない・tool実行経路が自己閉塞 | 同じ壊れたengineのtoolで修理することなくrollback。復帰用routeの権限・auditは変更対象から独立 |
| F3 | approval待ちでprocess/UIを再起動 | 同じtask/run/digestへ戻り、承認の紛失・別runへの誤適用・暗黙承認がない |
| F4 | 外部作用の後・checkpoint前に停止 | effect ID/receipt/read-after-writeで照合。二重作用ゼロ。照合不能なら作用を保留し、成功したふりをしない |
| F5 | 明示stop後にretry/rollback/再起動・古いapprovalが到着 | stop epochと失効状態が優先され、取消済み仕事を実行しない。コードrollbackが制御stateを巻き戻さない |
| F6 | 二つのrunが同じ活動をclaim、旧workerが遅れて復帰 | fencingにより古い主体が作用できない。leaseを確認できない間は新規の危険作用を止める |
| F7 | memory providerが停止し、後に復旧 | 診断・正本へのアクセス・許可済み復帰は継続。同期/再送の重複と想起汚染がない |
| F8 | 開発PCのMCP/SSH/権限が利用不能 | PDAノード側の対話・状態説明・独立復帰が利用可能。PCを救出しないとPDAが動かない構成にならない |
| F9 | LLM/認証/ネットワークが停止 | 残る能力と待機理由を表示。事前許可された別経路があれば縮退し、なければ無断credential流用や無限retryをしない |
| F10 | backupを別の一時環境へ復元 | 対象として宣言した記憶・活動・停止・設定を検証し、除外したsecret/外部stateを明示。index再生成と削除指示が整合する |
| F11 | 出典付きの好みを訂正/失効/削除後、session・index・runtimeを交換 | 旧値を現在値として答えず、適切なsourceへ追跡。忘却対象を再生成しない。移行欠落を隠さない |
| F12 | 外部記事から一つの改善を提案し、許可されたcanaryが失敗 | 同じactivityで不採用/修正/復帰・効果を確認でき、次の比較へ反映される。ユーザーに救出と文脈再構築を依頼しない |

実用目標として、単一process不調時の状態表示を2分以内、許可済み正常版への復帰を5分以内とする初期案を置く。これはSLAでも実績でもなく、R1の故障モデルと実測で調整する。復帰時間だけでなく、committedな活動・停止・承認状態の喪失、二重作用、誤再開を別々に測る。継続的な停電/回線断/全provider停止まで絶対可用性を保証しない。ホスト・disk障害にはオフホスト/別故障領域が必要で、現在の同一disk backupでは足りない。

## 6. 採用を止める条件

安全・継続性の失格を便利さの総合点で相殺しない。ただし未確認を恒久的な不採用とせず、必要な一つの試験へ落とす。

候補が、明示停止の保持、独立rollback、作用照合、秘密の所在、最低限のexportを説明・実証できない場合は本番採用へ進めない。read-only表示や診断まで一括拒否してユーザーに救出を戻す構成も失格とする。

継続的なcore fork、大量の独自adapter、同じstateを複数の正本で管理する必要が出た場合は、その将来負担を再見積もりする。「既に作ったから」「あと少しで完成しそうだから」を続行理由にしない。managedに任せた方が総負担が低いなら採るし、データ条件・退出コストが高ければ採らない。

## 7. 独立評価と承認の契約

設計、実装、release承認、復帰の判定を同一のLLM判断へ閉じない。独立レビューはsourceと失敗fixtureに基づき、未確認を明示する。最終反映はレビュー後の変更で失効するartifact/digest束縛を維持する。

現在の文書・調査のcommit/push許可は、R2以降の本番side effect、基盤選定、service再起動、自律改変再開への包括許可ではない。隔離実験を進める場合も対象・予算・外部送信・destroy/cleanupを契約化する。オーナーに依頼するのは方向と許可境界であり、通常の復旧手順を代わりに実行してもらうことではない。

## 8. このロードマップの完了

完了は文書が揃うことではなく、要求、失敗証拠、比較実測、将来保守/退出費、選択ADR、独立評価、承認済みshadow/canaryと最初の一周がつながることである。未採用案と撤退理由を残す。

現時点の次の具体作業はR0の証拠付きpostmortemとR1の受入・比較条件の確定である。今回作成した調査とDBOS probeはその入力であり、R2〜R5が完了したとは扱わない。
