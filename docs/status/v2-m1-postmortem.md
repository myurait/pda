# V2-M1 postmortem — scope control v2の自己閉塞

状態: 証拠・同型無作用再現を統合したM1成果。旧gateの修正/再有効化、PDA全体の復帰実証ではない。

## 結論

作業を制限する仕組みと、その仕組みを完了・報告・停止記録へ進める道が同じtool budgetを共有していた。未変更sourceで、通常の予算消尽と、再reviewで既消費数を下回るcapを受理した場合の両方から、read/heartbeat/block/scope制御/delegationが閉塞することを実行確認した。

既存DBの障害候補sessionにも、`state=locked`、`tool_calls=8`、`max_tool_calls=6`、`scope_verdict=pass`、未完了のrowが残る。親PDAが独立にread-only照合し、分析laneの報告値を確認した。したがって、消費数とcapの矛盾はsourceだけの仮説ではなく保存された実状態でもある。

ただし、最初に拒否されたtoolの完全なruntime traceと、各再review時の過去cap履歴は未回収である。元incidentの全因果列を復元したとは言わない。M1が固定するのは、既存証拠と結び付いた同型の閉塞と、次設計が回避しなければならない反例である。

## 1. 証拠の区分

| 区分 | 内容 | 証明する範囲 / 限界 |
|---|---|---|
| unchanged source | `integrations/hermes-scope-gate/scope_v2.py` と `plugin_runtime_v2.py` | review、lock、budget予約、pre-tool拒否の実装順。過去のどの呼出が発火したかは単独で証明しない |
| primary persisted state | 既存scope DBをURI `mode=ro` + `query_only=ON`で限定照会 | 障害候補の8/6・pass・locked・未完了。raw prompt/credentialは取得物へ含めない |
| 別の実運転log | 指定されたread-only verifier logの `tool-budget-exhausted` | 同じ拒否が複数tool面を閉じた実記録。障害候補sessionそのものではなく、前後関係を推定して同一incidentにしない |
| secondary owner説明 | 既存sessionの障害説明・postmortem再構成 | cap6への縮小・カード記録とcomplete拒否の説明。DBと整合するが一次dispatch traceではない |
| new actual offline execution | `experiments/v2/m1_scope_repro.py` | temp SQLiteを使い未変更sourceが実際に同型閉塞へ入る。production replay、実model審査、復帰成功ではない |

privateなDB locator、session locator、限定log行、原説明はprivate証拠ノートに分離する。公開可能な正規化値とbyte hashだけを[evidence](../research/evidence/v2-m1/primary-evidence.json)へ保存する。raw会話をpublic PKBへ移さない。

## 2. 証拠付き時系列

1. 2026-09-01〜02の設計/READMEでは、ScopeFrame→事前評価→observed effectsのfinal auditを一つのplugin/hook/storeへ結線した。これは意図した安全境界の記述で、可用性の証明ではなかった。
2. 別のread-only verifier実行には、review/lock frictionと `tool-budget-exhausted` によるtool面の連続拒否が記録されている。これを後日の単一ファイルE2Eと同じrunへまとめない。
3. 2026-09-04 13:24:19 JSTに作られた障害候補sessionの最初のlocked turnは、13:34:10時点で消費8/cap6、pass、未完了を保持している。保存tool rowは8件、内訳はreviewed-exact-command 3、reserved 4、command-not-reviewed 1。process-manage effectも3件あるため、元turnを『全作用ゼロ』とは記さない。
4. 同sessionの後続locked turnはcap15/消費10で、別turnである。これを最初の8/6状態へ混入させない。cap6以前の上限履歴と最初のdenyそのもののrowは欠落している。
5. 2026-09-06のowner決定で最初のPDA開発試行を失敗と分類し、scope control v2は停止、patch/再有効化禁止となった。再開にはpostmortem-ledな計画、独立評価、shadow/canary、独立stop/rollback、owner承認が必要となった。
6. 2026-09-07のM1で、現行sourceを変更せず通常budget1/8/96の消尽と再review cap縮小を再現した。現行サービス・稼働gate・providerには作用していない。

停止決定のsource: [current-priority](../roadmap/current-priority.md)、[旧gate README](../../integrations/hermes-scope-gate/README.md)。R0の元の不足: [gap assessment](../design/v2-gap-assessment-2026-09-06.md)。

## 3. 原因仮説と実行結果

### H1: 再reviewが既消費数以下のcapを受理する

source `scope_v2.py:688-855`では、新containmentを保存する時に累積tool_callsとの下限整合を確認しない。無作用probeではcap8でreadを2回予約した後、cap1の再reviewとrelockが成功し、累積2を保持したまま次のcontrolが拒否された。

判定: このrevisionの実装上の因果は確認済み。元incidentのcap8→1というpayloadを再現したのではない。元DBの8/6状態との同型性を確認している。

### H2: 作業制限がread/control/終端へ連座する

source `scope_v2.py:896-1014`ではlocked状態のread/controlもbudget予約を通る。`scope_gate`はread/control catalogにいても、予算消尽時にはhandlerより前で拒否される。実行した1/8/96条件の全てでread_file、kanban_heartbeat、kanban_block、scope_gate、delegate_taskがtool-budget-exhaustedとなり、completion signalはfinal-audit-requiredだった。DBをreopenしても同じ拒否を保持した。

判定: 判定関数と永続stateの閉塞は確認済み。HTTP/UI/Hermes dispatcher全体のE2Eを実行したわけではない。`plugin_runtime_v2.py:316-375`のpre-tool/middlewareがdenyをhandler前で返す接続はsourceで確認した。

### H3: 拒否試行も消費を増やす

mutation pathはreserveしてからallowed_effects等を判定する。source上は無作用denyにも予算消費がある。元DBにもcommand-not-reviewedが1件ある。

判定: sourceと保存decisionで支持される寄与候補。元incidentで何回の拒否がcap矛盾を生んだかまでは確定しない。H1/H2の反例成立に追加の推定は不要なため、今回の実行は原因を分離できる最小範囲に止めた。

### H4: 同じ故障面に修理・診断・停止記録が依存する

pre-tool validatorの例外/denyと実行middlewareの例外/denyは、後続handlerを呼ばない。独立したstate/stop/rollback経路の実証が無いまま、fail-closedの強さを自己完全性と混同した。

判定: 設計上の共通依存は確認済み。v2-PDA全体で独立復帰があるとの主張は未実証であり、M2の新しい実物境界で反証試験が必要。

## 4. tight loopと合成境界

実行:

```sh
python -m pytest tests/v2/fixtures/test_scope_v2_self_blocking.py -q
python -B -I experiments/v2/m1_scope_repro.py --budget 1
python -B -I experiments/v2/m1_scope_repro.py --budget 8
python -B -I experiments/v2/m1_scope_repro.py --budget 96
python -B -I experiments/v2/m1_scope_repro.py --scenario shrink
python -m pytest integrations/hermes-scope-gate/tests/test_scope_v2.py -q
```

新規witness testは、runner未実装→RED、実装→GREEN、複数budgetと再review縮小の各追加sliceもRED→GREENで作成した。旧gate suiteの19件は通ったが、今回の閉塞も成立した。つまり既存suiteのgreenはこの可用性要件を覆っていなかった。

fixture reviewerはlocked-stateの前提を作るためにscripted passを返す。審査品質・正規owner承認・LLM利用の証拠ではない。source判定、SQLite永続化、counter、再review、lock、reopenは実物であり、閉塞判定そのものをstubにしていない。probeの明示writeはtemp directoryのSQLite/containmentに限定し、repository moduleをloadする前にbytecode書込も無効化する。空cacheのsourceコピーでファイル一覧/内容の前後一致を検査した。source hash一致だけをhost全体の無書込証明とは扱わない。実tool handlerの外部作用は行わない。実行結果とsource hashは[evidence directory](../research/evidence/v2-m1/)で固定する。

## 5. 次設計で必須になる回避条件

作業予算が尽きても、認証されたstop受付、状態説明、receipt照会、承認失効、独立監督は動くこと。無制限の作業継続を認めるのではなく、制御操作を別のbounded経路へ分けること。

再review/cap変更は累積消費と整合し、変更後に必要な完了/停止操作が存在しない契約をlockしないこと。retry/run再生成/rollbackで消費を初期化しないこと。

read-only/negative/effect-not-reviewedの試験だけでなく、実worker停止、tool自己閉塞、監督再起動、authority到達不能、stopと作用のraceを、同じ活動IDで試すこと。新gateの強い拒否を診断不能・救援要求で達成してはならない。

これらを[state custody](../design/v2-state-custody.md)と[acceptance](../design/v2-acceptance-contract.md)へ渡す。旧scope control v2への修理提案ではない。

## 6. 未確定事項とM1判定条件

元の最初のdenyのcall ID/時刻、各再reviewの旧cap履歴、カード作用先とdispatch有無の完全join、実model応答の因果は未確定。欠落を『問題なし』として埋めない。独立reviewはこの飛躍が無いこと、同型閉塞の実コードprobe、control正本/遷移、次段entryの範囲を確認する。

M1のPASSは「元incidentの全てが分かった」「新PDAが復帰できる」ではなく、「証拠の強さを区別し、回避すべき実行済み反例と次の実証契約を固定した」に限る。
