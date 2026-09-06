# PDA v2 全体設計再評価 — 現行設計の不足と実現性

- 更新: 2026-09-06 JST
- 種別: オーナー指示による設計再評価。実装・運用達成の宣言ではない。
- 規範: [PDA憲章](../../pda_charter.md)、特に第四条・第五条・第六条・第七条。
- 次の順序の正本: [v2第1ロードマップ](../roadmap/v2-01-whole-system-reassessment.md)。
- 選択肢と公開根拠: [基盤比較調査](../research/pda-v2-platform-landscape-2026-09-06.md)。

## 1. 診断

問題を「Hermesの記憶をグラフDBへ交換する」「Open WebUIを別のチャットへ交換する」だけに縮めない。現在の設計は、記憶、実行、統治、表示、回復を個別に構想しているが、改善を引き受けてから失敗・復帰・次の改善へ至る全体の受入条件が閉じていない。

既存の安全策を捨てるのではない。憲章の優越、Git/worktree隔離、exact-artifact承認、明示停止、raw/derived分離、ローカル整合バックアップ等は再利用候補である。ただし、それがあることと自己完全性が成立することは別である。巨大な独自Context Spineや第二のdispatcherを先に造ることも結論にしない。

## 2. 現状の根拠と限界

| ID | 観測・原資料 | そこから言えること / 言えないこと |
|---|---|---|
| L1 | `personal_delegate_agent_plan.md` の第3〜6節・Phase 9/10 | Hermes中心、Open WebUI入口、後段のidentity/core交換という旧構想がある。実装証明ではない |
| L2 | `docs/roadmap/current-priority.md` の2026-08-22履歴、`autonomous-improvement-goal.md`、`improvement-orchestrator.md` | 通信完全性、自律改善、停止、claim、通知、審査の設計はある。旧「進行中」表示を現在の再開許可にできない |
| L3 | `docs/design/self-improvement-governance-adr.md`、`integrations/hermes-scope-gate/README.md` | 別審査、effect-based scope、統治領域保護などを設計・実装した履歴。scope control v2の自己閉塞失敗を解決した証拠ではない |
| L4 | `.hermes/plans/2026-08-17_172757-pda-identity-portability-and-runtime-injection.md` 1〜7節 | identity、release/state/secret/cache分離、fresh-host復元の詳細提案がある。別runtimeはdeferredで、計画の存在は達成ではない |
| L5 | 2026-09-06読取専用観測: `hermes --version`、installed-source HEAD | 稼働環境のCLIはHermes v0.20.2 (2026.8.16)、installed source `b5ae2debe7c51bf728127c7314e75f4f19b80b9a`。公式最新docs/上流mainと同一ではない |
| L6 | 同日: live `~/.config/pda/autonomous-improvement.json` の `enabled=false`。`pda-improvement-cycle.service/.timer` はdisabled | 自律改善停止設定を確認。Gitの `continuity/autonomous-improvement.json` は `enabled=true` の旧宣言を保持するため、無条件再配布は危険。今回はruntimeも宣言値も変更しない |
| L7 | 同日: `pda-local-backup.timer` active/enabled。`docs/operations/local-continuity-backup.md` | ローカル整合バックアップの既存資産。今回はrestore drill・オフホスト復元・ホスト故障時の切替を新たに試していない |
| L8 | 同日: default configのmemory設定はbuilt-in有効、`memory.provider`指定なし。会話には常設メモと過去session検索がある | 現在の基準線を記録できる。想起精度、判断改善、別runtime移行を比較測定した証明ではない |
| L9 | Kanban `t_395213b7` のオーナー要求と本会話 | 自己改善は中核、最初の体験は自己完全性。通常チャットではサイクルが閉じない。文書・調査・pushの明示許可。自律動作再開の許可ではない |

観測はこの判断に必要な最小範囲に限定した。全サービス監査、脆弱性診断、本番故障注入、認証・課金経路試験は実施していない。過去資料の数値・完了表記を現在の実効状態へ転記しない。

## 3. 要求 → 不足 → 実現性

以下の「不足」は、実装の不存在を全ファイルから証明した意味ではなく、現行設計・観測では要求を満たしたと判定できない点である。

| ID | 憲章からの要求 | このままだと不足する機能・契約 | 既存資産 / 実現性と残る検証 |
|---|---|---|---|
| G1 | 改善失敗でもPDA自身が戻る | 変更対象と独立した検知・最終正常版への復帰主体。壊れたLLM/同一tool pathによる修復待ちから脱する | systemd/既存backup/別起動環境を利用できる見込み。ただし独立principal・権限・復帰経路は未実証 |
| G2 | 復帰後に仕事が続く | task/run/step/approval/stop/effectの永続状態と、再起動後の照合 | Kanban/Gitを再利用。DBOS/Temporal/Restate等の既製primitiveも比較。外部作用のexactly-onceを製品名で仮定しない |
| G3 | 無許可の再開・二重実行をしない | stop epoch、fencing、承認digest、冪等key、作用不明時の保留と照会。コードrollbackと承認状態rollbackの分離 | 現行exact-artifact思想を残せる。全tool/bypass/並行run/復旧直後の実作用試験が必要 |
| G4 | 開発PC不調時の砦 | 開発PCのMCP・権限・単一アカウントに依存しない対話・診断・回復能力 | PDAノード分離は足場。認証失効/プロバイダ停止/ホスト・回線故障まで含む縮退経路は未証明 |
| G5 | 記憶が判断を良くする | 出典付き記憶、時間的更新・反証・忘却、必要時の想起、誤記憶訂正。保存件数ではなく判断の評価 | files/FTSを対照に複数memory方式を比較可能。グラフや自動reflectionの優位は未測定 |
| G6 | 器を選び直せる | 正本の所在、schema/version、削除伝播、export/rebuild、実装非依存の受入fixture。別runtimeへの小さな引継ぎ実証 | 旧可搬性設計は再利用可能。ただしfull universal schemaや全過去会話の正規化を先行実装しない |
| G7 | 会話外でも活動が持続 | 同じ取り組みで調査→採否→差分審査→実行→結果→再評価を扱うactivity中心の状態とUI | Kanban/承認リスト/既存表示を活用。Open WebUI events、AG-UI/CopilotKit、既成agent UIの比較が可能。接続だけで操作可能とは判定しない |
| G8 | 外部ベスプラを取捨選択 | source→仮説→適用範囲→比較→採用/却下→効果→再検討の記録。不採用と陳腐化も知識にする | PKBのraw/curatedとGit/skillsは再利用候補。評価runnerは既存製品を優先し、独自judge群を増築しない |
| G9 | 自己改変で統治を破壊しない | 意味判断、決定論的権限、sandbox、release承認、復旧を責務分離。審査失敗で全診断まで閉塞しない | 現行原則を使い、同一プロセスpluginだけを独立境界と見なさない。危険な実作用はfail-closed、読取・状態表示・許可済み復旧を別経路にする |
| G10 | 「待てば戻る」が見える | 応答可用性と活動継続性を別々に観測。freshness、進展/待機/停止/復旧不能、独立通知 | 既存progress資産を再利用。heartbeatの存在を進捗・復旧成功の証明にしない |
| G11 | 日常の保守を押し返さない | 更新・依存関係・移行・廃止までの責任台帳、互換試験、変更予算、upstream追従方針 | 標準primitiveと公式adapter優先で負担を減らせる見込み。自作量やservice数だけで総負担を断定しない |
| G12 | 思想と情報所有権の継承 | authorityと記憶/skillの区別、public/private/work分離、最小外部送信、復旧先のsecret境界 | 既存憲章・public-only PKB規約を維持。記憶のGit化は秘密・削除問題を解かない。managed選択でも同じ受入条件 |

## 4. 設計の中心を置き直す

最小の一周は「URLから改善仮説を取り出す → 不採用も含めて判断 → 許可された候補を隔離検証 → exact artifactを承認 → 一つをcanary適用 → 失敗時は許可済み正常版へrollback → stop epoch・承認digest・実作用・記憶をread-backして照合 → 結果を次の判断へ返す」である。

サービスの回復と活動のresumeは別の状態遷移にする。rollback自体を活動再開の許可にしない。停止、失効した承認、未照合の作用があればhold/diagnosticだけを行う。有効な既承認範囲と停止不存在、作用照合を確認した場合のみ活動を自動resumeできる設計とし、その都度ユーザーへ通常の救出を戻さない。[v2-01のF5](../roadmap/v2-01-whole-system-reassessment.md) を主経路の不変条件として適用する。

これは一つの万能agent processを作る要求ではない。対話、活動state、再利用知識、実行、権限・release、復帰に責任を割り当てる。**論理的な責務の分離は、六つの新サービスを建てる指示ではない。** 同じDBの別tableや既製サービスで足りるなら増やさない。ただし「独立した復帰・制御」の権限境界だけは、同じ故障単位の中に置いて独立と呼ばない。

## 5. 失敗原因の扱い

scope control v2によってPDA自身が何もできなくなり、オーナーが救出を担ったことは、オーナー申告・停止方針から出発する事実である。しかし本調査は、障害の厳密な時系列、最初の故障点、全拒否経路、反事実的に効いた復帰操作を再現したpostmortemではない。独立復旧を要求する根拠にはなるが、「根本原因を特定し解決した」とはしない。

したがってv2第1ロードマップの先頭は、この失敗を証拠付きで再構成し、同型の自己閉塞を合成環境で再現することである。旧scope v2へその場のpatchを足したり、再有効化して実証を代用したりしない。
