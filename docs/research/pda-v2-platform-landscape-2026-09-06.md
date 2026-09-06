# PDA v2 基盤選択の広域調査 — 自己完全性を、保守できる構成で実現する

観測日: 2026-09-06 JST。対象は公開一次資料、公式リポジトリの固定snapshot、および無認証・無課金・本番非接続の小規模probeです。

これは製品導入の承認書ではありません。[現行設計のgap](../design/v2-gap-assessment-2026-09-06.md) と [v2第1ロードマップ](../roadmap/v2-01-whole-system-reassessment.md) の判断材料です。現在の自律改変停止を維持します。

## 1. 結論

**スクラッチ全面開発は推奨しません。同時に、Hermes継続も既定にしません。** 現段階の推奨は「再利用する成熟したprimitiveを増やし、自分たちが所有する独自契約を小さくする」ことです。これは特定製品の採用決定ではなく、比較と投資の順序です。

最初に直接比較する価値が高いのは、(A) Hermesを公式拡張中心で使う対照系、(B) 現行Letta harnessを主体にする系、(C) 管理サービスを使って運用負担を外へ出す系です。OpenClawは完成型personal-agentのもう一つの候補、LangGraph/Deep AgentsやMicrosoft Agent Frameworkは必要な差分が既製品では埋まらない場合の構築用部品です。既存のClaude Code/Codex/OpenHandsは主として実行laneとして評価し、いきなり個人の関係・記憶・活動の全てを預けません。

最も重要な不足は、memoryの型や画面の見た目だけではありません。「改善を引き受ける → 失敗する → 自分を復帰させる → 作用と承認を照合する → 同じ仕事を続ける → 経験を次へ返す」が、故障した主agentと独立して成立する必要があります。既製品で賄える部分は多い一方、**今回調査したどの製品についても、このPDA全体契約が設定だけで完成すると実証したわけではありません。**

## 2. 調査方法と証拠の強さ

検索はmemory、durable execution、完成型agent、SDK、control/sandbox、UI、evaluationの軸で広げ、短い語句での再検索と公式サイト・リポジトリへの追跡を行いました。検索snippetのみから採用判断はしていません。上流のREADME・licenseをcommitで固定し、memory候補は公式API/manifestも確認しています。

証拠を次のように分離します。

| 記号 | 今回の証拠 | 言える範囲 |
|---|---|---|
| D | 公式docs/API reference | 作者が公開する契約・提供機能。稼働環境での有効性ではない |
| S | commit固定README/license、manifest、GitHub metadata | 観測したrevisionの内容・license。実装全経路の安全性ではない |
| P | DBOSの独立したプロセス停止probe | その版・その条件のprimitive挙動。PDAの復帰、HA、統合E2Eではない |
| I | 本報告の比較・提案 | D/S/Pを踏まえた設計判断。優位性の実測ではない |

検索件数、取得件数、採用citationの数は [evidence/coverage.json](evidence/coverage.json) に機械集計します。固定sourceと短い逐語根拠は [evidence/source-map.json](evidence/source-map.json)、repo snapshotは [evidence/upstream-snapshots.json](evidence/upstream-snapshots.json) に残します。取得失敗・404や検索結果のみのsourceを、読了・実証済みへ数えません。全候補のCI、依存脆弱性、issue全件、provider課金、クラウドSLAを監査した調査ではありません。

## 3. 選択肢を構成として比較する

表の負担は今回の構成を想定した相対的な設計推定です。時間・料金を測って得た総合点ではありません。

| 構成案 | 既製品から得るもの | PDA側に残る保守 | 移行/退出の主な負債 | 位置付け |
|---|---|---|---|---|
| A0: 現状に近いHermes + files/FTS + 既存Kanban | 既存tool/channel/skill/session、運用資産 | 既存patch/bridge追従、復帰・制御境界、活動UI | Hermes session/profile、ローカルpatch、二重管理state | 必須対照。採用済みだから勝者とはしない |
| A1: Hermesを交換可能なexecutorにし、必要部分だけ外部化 | 公式memory provider、context engine/pluginの拡張面 | adapter、永続活動と復帰、versionごとのcontract test | 追加DB/同期/再送・消去。独自制御層を作りすぎる危険 | 有力。core fork増大なしで成立するかが条件 |
| B: 現行Letta harness中心 | identity、MemFS、skills、schedules、reflection、複数UI/channel | 独立release/復旧・安全境界、既存活動移行、必要な接続 | 新runtimeへの移行、mods追従、local/cloud状態差 | **直接比較の優先候補**。旧Letta V1の説明で評価しない |
| C: OpenClaw中心 | personal-agent向け運用面、memory/doctor、channel/tool群 | 権限・sandbox・更新・復帰のPDA契約 | config/plugin/session差、移行と更新頻度 | ready-madeの追加候補。Doctorは独立復旧の証明ではない |
| D: LangGraph/Deep Agents または Microsoft Agent Frameworkで組む | checkpoint/interrupt、agent loopの部品、provider接続 | 製品としての統合、connector、運用、UI、承認/復帰の設計 | SDK/API変化と自作hostの長期保守 | 「スクラッチより少ない自作」だが「完成品採用」ではない |
| E: Cloudflare Agents、Temporal Cloud等のmanaged中心/混成 | 継続実行・状態サービスの運用を委託する選択 | local connector、data-flow/認証、effect照合、export、vendor障害時の縮退 | cloud固有API・DB・課金・利用条件、外向き接続 | **運用負担を最重要視するため必ず比較**。local-firstを未承認の除外条件にしない |
| F: Dify/n8n + 既存agent | 可視workflow、外部integration、定型処理の組立 | 個人の継続記憶・長期活動・自己変更の統合 | workflow定義/edition/connector、別管理画面 | 主体の丸ごと代替より周辺laneに向くという仮説 |
| G: 全面スクラッチ | 要求へ自由に合わせられる | runtime・memory・control・UI・運用の全責任 | 自作codeと独自schemaが最大のsunk costになる | 最後。既製候補の具体的失格理由と退出計画が必要 |

Hermesは外部memory providerとcontext-engine/plugin契約を公式に提供しています。[1][179][180] Lettaの現行READMEはmemory・identity・長期学習・always-on利用を明示し、実装は旧`letta` serverから`letta-code`へ移っています。[75][220] OpenClawにはmemoryとDoctorの公式操作面があります。[36][37] LangGraphはthread checkpointとstore、interruptを提供し、Microsoft Agent FrameworkはAutoGen/Semantic Kernelの後継として案内されています。[41][43][122] Cloudflare Agentsはpersistent stateful executionをSDKの中心に置いています。[165] Difyはworkflowを含むLLM app開発基盤であり、n8nのCommunity licenseはSustainable Use Licenseで、無制限なOSS一般と同一ではありません。[158][214]

## 4. HermesとLettaを公平に比較する

### Hermesの残す価値と負担

常設の小さなcurated memoryと、必要時のSQLite/FTS会話検索は、毎回全履歴を読み直さず継続性を持つ合理的なbaselineです。一方、memoryは自動圧縮ではなく、固定枠の手入れが必要です。これがユーザー理解の質をどれだけ高めるかは別問題です。[2]

外部providerは同時に一つがactiveという契約です。built-in memoryとの併用を案内していますが、別ページにはmemory/user-profile双方を無効化する設定もあり、「built-inを絶対外せない」とは読みません。provider同期・memory mirror・切替時の二重書き込みや、fallbackの実効性を個別に試します。[1][2]

pluginの拡張点があることはupstream patchを減らす可能性を持ちます。ただし新providerの受付範囲はupstream方針に従い、任意拡張が将来も取り込まれるとは限りません。[3] またplugin Doctor自体、pluginは同一process・同一user権限で実行されsandboxではないと明記しています。plugin化は保守境界であって、それだけで統治の独立性にはなりません。[179]

現行PDA installed版と公式最新docsの差はgap文書L5に固定しました。本調査はHermesのupgradeや新plugin導入をしていません。公式拡張だけで必要経路が成立するか、現在抱えるlocal差分をどれだけ捨てられるかが採否を左右します。

### 現行Lettaは古い「memory server」と同じ候補ではない

現在のharnessはMemFS、skills、sleep-time学習、channels、schedules、modsをまとめて提供しています。今回固定したcurrent sourceのpackageは`@letta-ai/letta-code 0.31.12`、licenseはApache-2.0です。旧landing repoのrelease番号を現行runtimeの版番号にしていません。[220][221][222]

MemFSはGit repositoryをMarkdownとして投影し、`system/`は常時context、その他は必要時に読む方式です。semantic/vector indexは既定で含まず、localの会話検索はfull-textのみ、cloudでは異なる契約です。local-only記憶のbackup責任は利用側に残ります。「Gitだから全stateの復元済み」「Lettaだからグラフ記憶」という読み方はできません。[216]

Modsによる自己改変は今回の憲章に近い機能です。ただしfully trustedな同一process codeで、tool、権限policy、provider adapterにも触れます。対話CLIのdefault permission modeも公式docsでは`unrestricted`です。これをそのまま安全な自己改変と呼ばず、独立したrelease/回復経路の外側で扱えるかを比較します。[217][218]

local App Serverはon-device stateを持つ候補であり、Letta accountなしの利用も案内されています。[6][76] ただしAgentFileの公開資料はV1 SDK legacyとして扱われています。MemFSの退出性と、message/approval/provider/configを含む全stateの移行性を混同しません。現行runtimeのfresh-host復帰は未実証です。[7][216]

## 5. 長期記憶とPKB — graphへの移行を結論にしない

比較対象を三つに分けます。原資料・決定・削除指示などの**正本**、想起を助ける**semantic/graph projection**、task/run/approval/stopなどの**活動state**です。semantic recallだけから許可や未完了の仕事を復元しません。正本は最初から全てを独自共通DBへ写すのではなく、既存storeの所有と最小export契約を明示します。

| 候補 | 主な強みと公式契約 | 運用・退出に残る負担 | 今回の判断 |
|---|---|---|---|
| files/Markdown + SQLite FTS | 人間可読、少ない部品。Hermes/Lettaでも形を変えて採用されている。[2][216] | 想起の気づき、意味検索、矛盾/期限の手入れ。filesというだけでは履歴・削除契約にならない | 全比較の対照。既存方式を無評価で優位とはしない |
| Hindsight | retain/recall/reflect、observations、Postgres+pgvector/embedded経路。[204] APIには訂正、文書連鎖削除、bank削除、文書transferとMarkdown exportがある。[215] | LLM/embedding、DB、async処理。exportはembedding/DB IDを含まずimportで再計算する。全状態・backupまで同じとは限らない。[215] | 経験→判断への有力な比較候補。API契約は確認、ローカル復元は未実測 |
| Mem0 OSS | local Qdrant+SQLite history等の構成とlibrary/server/cloudを分けた導線。[23] 現行READMEはADD-only extractionを説明。[200] | 自動抽出がADD-onlyであることは、update/delete APIの不存在を意味しない。訂正・重複・消去・provenanceを別試験にする | 軽量semantic対照候補。managedのbenchmarkをOSSへ転用しない |
| Honcho | 変化する人・agent・project等のpeer modeling。self-hostはPostgres/pgvector、Redis/API/deriver等。[13][199] | service側AGPL-3.0、背景推論と複数component。心理/関係の解釈が正しいかも評価が必要。[198][199] | 「長年のユーザー理解」を直接試す有力候補。単純fact memoryより良いかで判定 |
| Graphiti / Zep | Graphitiは時間付きfact validity、episodeへのprovenance。旧factはinvalidatedでありdeletedではない。[202] | graph DBとstructured-output LLM等。Zepのmanaged engineとOSS Graphitiは同一製品ではない。[202] | graph案の正面比較候補。localとmanagedは別構成として残す |
| OpenViking | `viking://`仮想filesystemでmemory/resource/skill、階層的なcontextを扱う。[206] | manifestはAGPL-3.0/Alpha。file-like表示だけで通常fileとして完全退出できるとしない。[207] | 階層contextの候補。削除・backup・再構築とlicenseを試験入口にする |
| Cognee | graph/vector/session distillationを広く扱い、forget APIも説明する。[208] | Apache-2.0/Betaのmanifest、広いstorage/pipeline依存。Postgres graphはREADMEでdemo注意。[208][209] | 一体型knowledge platformの候補。小さな記憶差し替えと同じ工数扱いにしない |
| Letta MemFS | Git化したcontextとagent runtimeの結合。[216] | memoryだけを差し替える比較ではない | runtime比較Bに含め、memory単体の順位と混ぜない |

Hindsightについては、最初のREADME中心の調査ではexport/deleteを未確認としていました。公式API referenceまで追跡し、上表の契約を確認して判断を更新しました。特にdocument transferは抽出済みfact・entity名・causal link・chunkを持ち、embedding/DB IDを除外します。observationとknowledge baseの付帯exportは既定falseの別optionです。存在だけでなく、**何が入らないか**が退出コストの証拠になります。[215]

最初のmemory比較はbaselineを必須とし、Hindsightの経験記憶、Honchoのuser modeling、Graphitiの時間・関係という異なる仮説を同じ小fixtureで段階比較する提案です。三つを同時運用する提案ではありません。導入負担が過大ならMem0を軽量対照へ切り替えます。OpenViking/Cogneeは固有のgapが残った時の次候補です。

vendor benchmark順位は採否根拠にしません。LongMemEval-V2はreader/embedding構成を固定した実験であり、各社READMEのscoreは同じ条件とは限りません。[210] Hindsight自身も他社scoreにself-reported値があると記載し、Cogneeも比較条件差を明示しています。[204][208] 日本語での訂正、出典、適用期限、不採用の記憶、privacy境界、削除後の再出現、失敗後の継続を同条件で測ります。

## 6. 活動stateと復帰 — 既製の永続実行を使う価値と限界

| 選択肢 | 賄えるprimitive | 別途必要 / 保守判断 |
|---|---|---|
| 既存Kanban + 最小event/checkpoint | 現行資産から出発し、DB/service追加を抑える | 自分でqueue/retry/replay基盤を増築し始めるなら既製品と再比較する |
| DBOS Python | workflow/stepの永続化、SQLite既定、Postgres選択。[27][176] libraryはMIT。[132] | 同一host/DBの故障、更新互換、作用照合、process再起動主体は別。小規模local構成に適合するかを先に測れる |
| Temporal | durable execution、worker orchestration。self-hostは自分でcluster運用。[131][111] | 強いがservice運用・DB・upgrade・workflow versioningの責任がある。Cloud利用も別案として比較する |
| Restate | serverを一つのbinaryとして展開するself-host経路と、service前段での状態/retry制御。[32][35] | library内蔵と異なりserverが増える。server licenseはBSL 1.1とadditional grantで、MIT/Apacheと同じ扱いにしない。[136] |
| LangGraph checkpointer / Store | thread単位stateとthread間store、interruptによるpause/resume。[41][43] | host recoveryや外部effectのtransactionとは別。durable実行のためのdeterminism/side-effect分離が必要 |
| Cloudflare Agents | stateful instance、HTTP/WebSocket/schedule等のmanaged execution。[165] | local machineへ作用する接続経路とoffline時挙動、provider/data/billing、platform外へのexportを別途検証 |

### 実測した境界

使い捨てvenvへ`dbos==2.31.0`を導入し、合成fileへのappendを外部作用に見立て、child processをSIGKILLしたあと別processで同じworkflow IDを開きました。成功例だけでなくcheckpoint前の失敗窓も試しています。詳細・コード・生出力は [dbos-probe](evidence/dbos-probe/README.md) に保存します。

| 条件 | 実測 |
|---|---|
| step完了のcheckpoint後、次step内でkill → harnessがprocessを再起動 | 先頭stepの作用は1回、workflowの最終値は`finished` |
| file append済み、step完了checkpoint前にkill → 再起動 | 同じ作用のappendは2回、workflowの最終値は`finished` |

**結論はPARTIALです。** 再開primitiveは実働しましたが、「完了したか不明な外部作用を勝手に再実行しない」はそれだけでは得られません。Temporal公式もactivityに冪等性を推奨しています。[83] 本probeの再起動主体は試験harnessであり、DBOSやPDAが自力でprocessを蘇生した証明ではありません。単一hostの合成fileであり、停電、DB破損、HA、HTTP相手のidempotency、stop/digest、PDAの実tool、UI復帰は試していません。

採否条件には、effectごとの`idempotency key / remote receipt / read-after-write照合 / 補償 / 不明時保留`を置きます。retryを可能にすることと、retryしてよいことは別です。復帰後も停止・失効承認が優先され、rollbackで昔の承認や取消済み仕事を復活させてはいけません。

## 7. 自己改変・独立境界・復旧主体

Hermes plugin、Letta Mods、Claude Agent SDK hooksは拡張や制御の入口になりますが、同じprocess/OS principalがpolicyやtoolの実行環境を変更できるなら、独立した統治とは呼べません。Claude SDKもhook callbackとpermission controlを提供するAPIであり、任意host accessを持つPDA全体への独立境界を証明するものではありません。[179][217][86]

sandbox候補のOpenShellはpolicyをfilesystem/process等のstatic部分とnetwork/inferenceのdynamic部分に分けています。[97] ただし現行repoはalphaの表示を持つため、基盤の最後の砦として無試験で採用しません。[142] agentgatewayはMCP/A2A/LLM等の接続にauth/観測を置く部品ですが、host filesystem操作やdirect shellを含む万能gateではありません。[145]

自己復帰の実装候補は、まず既存service manager・最終正常release・限定的なread-only health/diagnostic route・外部からのrollbackを組み合わせ、主agentを止めても実行できるかを見ることです。A/B更新のboot success確認のような既成運用パターンは参考になりますが、RAUCそのものをこのサーバーへ導入する結論ではありません。[108]

復帰用権限も万能root agentにしません。許可済みreleaseの起動/切替、health確認、限定diagnosticに絞り、独立したstop stateを読む設計が候補です。LLMを使う診断と、LLMが使えなくても実行できる復帰を分けます。明示停止の解除を「回復」として自動化しません。

## 8. UIと実行lane — チャットを置き換える前に活動の契約を持つ

Open WebUIのFunctionsはserver上の任意Pythonであり、events/status等の表示拡張面もあります。既存入口として使える一方、独自Pipe/イベント対応を持つほどupstream追従負担が残ります。[62][63] 「chat historyに進捗文を足す」だけでは、同じ活動への復帰、承認の失効、失敗理由、成果、次判断が所有されません。

AG-UIにはstate snapshot/deltaの契約があり、CopilotKitはHITLとthread/persistenceを提供する候補です。[66][71][154] ただしprotocolの存在、producerが発行すること、consumerが読むこと、画面から正しいrunを再開できることは別です。Hermes/Lettaとの具体的なbridgeを本番E2E検証していないため、drop-in互換とは書きません。

比較する最小画面は「取り組み一つについて、最新状態・次の判断・審査対象diff/digest・結果・停止/再開・根拠が同じ場所にある」ものです。標準UIで足りるなら専用frontendは作りません。足りない場合も、活動stateを持つ小さな画面を既存UIへ足す案と、AG-UI/CopilotKit等で組む案を比べます。恒久的な独自chat製品の開発を前提にしません。

実行laneには、Claude Agent SDKのpermissions/hooks、Codex App Serverの双方向JSON-RPC、OpenHands Agent ServerのREST/WebSocket隔離実行面などがあります。[87][156][78] Codexの調査snapshotではWebSocket transportはexperimental/unsupportedとの記載があるため、remote接続を安定契約として採用しません。[156] interactive subscription、SDK、headless、cloudの認証・課金・session所有は別に検証し、開発PCの会社アカウントをPDAの復旧経路へ無断流用しません。

## 9. 継続改善の評価基盤も可能な限り再利用する

skillを持ち運ぶ形式としてAgent Skillsの公開formatがあります。ただしskill formatは実行権限、状態復帰、評価品質を規定するものではありません。[195] 評価runner候補には複数providerを扱うpromptfooと、tool作業を隔離環境で実行するInspectがあります。[190][186] これらを使うこと自体を合格扱いせず、PDAが守るべきfixture/assertionを少数に固定します。

改善の記録は「記事を保存した」「skillを増やした」で閉じません。source日付、適用仮説、baseline、費用、失格条件、採用/不採用、承認範囲、release、観測、rollback結果、再評価のtriggerをつなぎます。不採用や自分に効かなかった結果も残し、同じベスプラを何度も再導入しません。新機能の追加より先に、不要になった独自code/依存を消せる改善も同じ価値として評価します。

## 10. 保守とsunk costの評価方法

過去の投資額は回収不能な過去費用です。だから無視して全部捨てる、という意味ではありません。残る互換性、運用経験、test、移行費、今後の更新負担は将来費用として比較します。自作の初回生成が速いことは、長期の負担が小さい証拠にはなりません。

候補ごとに、まず同じ期間・同じ改善scenarioで次を実測するcost sheetを作る提案です。現時点で人日や月額の根拠のない見積もりは置きません。

| 観点 | 記録するもの |
|---|---|
| 導入 | 残作業時間、documentどおりに動いた割合、独自patch/adapter、認証/課金の実際の経路 |
| 定常 | operator時間、service/DB・backup・secretの所有者、LLM/embedding呼出と料金、待ち時間 |
| 更新 | version固定とupgrade試験、upstream差分の再適用、deprecated API、migrationの可逆性 |
| 障害 | ユーザーへの救出依頼回数、復帰時間、作業喪失、二重作用、不明stateの照合負担 |
| 退出 | raw/derived/configのexport、別runtime引継ぎ、再index、消去とbackup保有、vendor契約 |
| 効用 | 採否判断の質、自己改善の実効、ユーザーが手作業に戻らず済んだ範囲 |

MIT/Apacheだけが低コストでAGPL/managedが高コストと決めつけません。license、料金、データ条件、運用の移譲範囲を別々に読む必要があります。今回はlicense本文を確認しましたが、法務意見でも将来価格の保証でもありません。DifyにはApacheベースの追加条件、Restate serverにはBSL/additional grantがあり、editionと利用形態を決めてから適合を確認します。[162][136]

独自実装の初期予算を「PDA固有の受入fixture、最小状態contract、必要なadapter、独立復帰の結線」に寄せます。汎用workflow engine、万能memory、plugin marketplace、全UIを同時に自作する方向は却下します。最終的なcustom量は実験後に決め、core patchが毎回必要になる候補は負担を隠さず降格します。

## 11. 今回できたこと / まだできていないこと

できたことは、憲章の要求に照らしたgap整理、広範な既製候補の一次資料調査、現行Lettaへの追跡、Hindsightの退出/削除APIの追加確認、license/依存snapshot、DBOSの再開と二重作用の境界probeです。公開調査部分はpublic PKBへ保存し、非公開のPDA環境・会話・Kanban stateはそこへ混ぜません。

未完了なのは、失敗したscope v2の完全なpostmortem、PDA全体の独立復帰実証、候補runtime/memoryの同条件評価、managed料金/認証/データ条件の適合確認、UIの同一activity E2E、fresh-host/外部provider障害の復帰です。今回の成果をもって自律改善再開や基盤採用を承認済みにしません。

次に進めるのは [v2第1ロードマップ](../roadmap/v2-01-whole-system-reassessment.md) です。そこで製品選定ではなく、証拠を伴う採用・不採用・保留の判断を順に確定します。

## Sources

[1] https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers — Memory Providers | Hermes Agent
[2] https://hermes-agent.nousresearch.com/docs/user-guide/features/memory — Persistent Memory | Hermes Agent
[3] https://hermes-agent.nousresearch.com/docs/developer-guide/memory-provider-plugin — Memory Provider Plugins | Hermes Agent
[6] https://docs.letta.com/self-hosting — Self-hosting | Letta Docs
[7] https://docs.letta.com/v1-sdk/concepts/agent-file — AgentFile (.af) | Letta Docs
[13] https://github.com/plastic-labs/honcho — GitHub - plastic-labs/honcho: Memory library for building stateful ...
[23] https://docs.mem0.ai/open-source/overview — Overview - Mem0
[27] https://docs.dbos.dev/python/programming-guide — Learn DBOS Python | DBOS Docs
[32] https://docs.restate.dev/server/overview — Self-hosted Restate Overview
[35] https://docs.restate.dev/foundations/key-concepts — Key Concepts - Restate
[36] https://docs.openclaw.ai/cli/memory — Memory - OpenClaw
[37] https://docs.openclaw.ai/cli/doctor — Doctor - OpenClaw
[41] https://docs.langchain.com/oss/python/langgraph/persistence — Persistence - Docs by LangChain
[43] https://docs.langchain.com/oss/python/langgraph/interrupts — Interrupts - Docs by LangChain
[62] https://docs.openwebui.com/features/extensibility/plugin/functions — Functions / Open WebUI
[63] https://docs.openwebui.com/features/extensibility/plugin/development/events — Events / Open WebUI
[66] https://docs.ag-ui.com/concepts/state — State Management - Agent User Interaction Protocol - docs.ag-ui.com
[71] https://docs.copilotkit.ai/human-in-the-loop — HITL Overview - docs.copilotkit.ai
[75] https://github.com/letta-ai/letta — GitHub - letta-ai/letta: Platform for stateful agents: AI with advanced ...
[76] https://docs.letta.com/platform/app-server — Letta App Server | Letta Docs
[78] https://docs.openhands.dev/sdk/arch/agent-server — Agent Server Package - OpenHands Docs
[83] https://docs.temporal.io/activity-definition — Activity Definition | Temporal Documentation
[86] https://code.claude.com/docs/en/agent-sdk/hooks — Intercept and control agent behavior with hooks - Claude Code Docs
[87] https://code.claude.com/docs/en/agent-sdk/permissions — Configure permissions - Claude Code Docs
[97] https://docs.nvidia.com/openshell/sandboxes/policies — Customize Sandbox Policies | NVIDIA OpenShell
[108] https://rauc.readthedocs.io/en/latest/integration.html — Integration — RAUC 1.15.1.532-1a41 documentation
[111] https://docs.temporal.io/self-hosted-guide/deployment — Deploying a Temporal Service | Temporal Documentation
[122] https://learn.microsoft.com/en-us/agent-framework/overview — Microsoft Agent Framework Overview | Microsoft Learn
[131] https://raw.githubusercontent.com/temporalio/temporal/891d1b648b7252925142cc36f13e40a0e2ed4244/README.md — temporalio/temporal @ 891d1b648b72 README.md
[132] https://raw.githubusercontent.com/dbos-inc/dbos-transact-py/833794f7a1138bacf75ff6d88647a33eb5e35e52/LICENSE — dbos-inc/dbos-transact-py @ 833794f7a113 LICENSE
[136] https://raw.githubusercontent.com/restatedev/restate/64d12f01368b66cf88a3f78ba4397f129b623fc9/LICENSE — restatedev/restate @ 64d12f01368b LICENSE
[142] https://raw.githubusercontent.com/NVIDIA/OpenShell/320d4ef79dd572c642133f175f12bafc20d89fd9/README.md — NVIDIA/OpenShell @ 320d4ef79dd5 README.md
[145] https://raw.githubusercontent.com/agentgateway/agentgateway/748b38b25d6e8c981c42e40b5e808d84c483c1bf/README.md — agentgateway/agentgateway @ 748b38b25d6e README.md
[154] https://raw.githubusercontent.com/CopilotKit/CopilotKit/b5727e49ae893590d3969d300b92b8544388e34e/README.md — CopilotKit/CopilotKit @ b5727e49ae89 README.md
[156] https://raw.githubusercontent.com/openai/codex/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/app-server/README.md — openai/codex @ ac192cd7937b codex-rs/app-server/README.md
[158] https://raw.githubusercontent.com/langgenius/dify/dde1d500b5bcbf8a05b37b3615ebaff6219b84b4/README.md — langgenius/dify @ dde1d500b5bc README.md
[162] https://raw.githubusercontent.com/langgenius/dify/dde1d500b5bcbf8a05b37b3615ebaff6219b84b4/LICENSE — langgenius/dify @ dde1d500b5bc LICENSE
[165] https://raw.githubusercontent.com/cloudflare/agents/ec93caf6ec1efebb521aa9ab30c0a8cb2b4d50d5/README.md — cloudflare/agents @ ec93caf6ec1e README.md
[176] https://docs.dbos.dev/python/tutorials/workflow-tutorial — Workflows | DBOS Docs
[179] https://hermes-agent.nousresearch.com/docs/developer-guide/plugins — Hermes Agent
[180] https://hermes-agent.nousresearch.com/docs/developer-guide/context-engine-plugin — Hermes Agent
[186] https://inspect.aisi.org.uk/sandboxing.html — Sandboxing - Inspect
[190] https://www.promptfoo.dev/docs/providers — LLM Providers | Promptfoo
[195] https://agentskills.io/home — Agent Skills Overview - Agent Skills
[198] https://raw.githubusercontent.com/plastic-labs/honcho/main/LICENSE — Honcho license_url
[199] https://raw.githubusercontent.com/plastic-labs/honcho/main/pyproject.toml — Honcho manifest_url
[200] https://raw.githubusercontent.com/mem0ai/mem0/main/README.md — Mem0
[202] https://raw.githubusercontent.com/getzep/graphiti/main/README.md — Graphiti / Zep
[204] https://raw.githubusercontent.com/vectorize-io/hindsight/main/README.md — Hindsight
[206] https://raw.githubusercontent.com/volcengine/OpenViking/main/README.md — OpenViking
[207] https://raw.githubusercontent.com/volcengine/OpenViking/main/pyproject.toml — OpenViking manifest_url
[208] https://raw.githubusercontent.com/topoteretes/cognee/main/README.md — Cognee
[209] https://raw.githubusercontent.com/topoteretes/cognee/main/pyproject.toml — Cognee manifest_url
[210] https://github.com/xiaowu0162/LongMemEval-V2/blob/main/README.md — LongMemEval / LongMemEval-V2 benchmark comparability
[214] https://raw.githubusercontent.com/n8n-io/n8n/master/LICENSE.md — https://raw.githubusercontent.com/n8n-io/n8n/master/LICENSE.md
[215] https://hindsight.vectorize.io/api-reference — Hindsight HTTP API | Hindsight
[216] https://docs.letta.com/letta-code/memfs — MemFS | Letta Docs
[217] https://docs.letta.com/configuration/mods — Mods | Letta Docs
[218] https://docs.letta.com/letta-code/permissions — Permissions | Letta Docs
[220] https://raw.githubusercontent.com/letta-ai/letta-code/701f2a5367828847313876c735ade27b9df97689/README.md — Letta current runtime README.md @ 701f2a536782
[221] https://raw.githubusercontent.com/letta-ai/letta-code/701f2a5367828847313876c735ade27b9df97689/LICENSE — Letta current runtime LICENSE @ 701f2a536782
[222] https://raw.githubusercontent.com/letta-ai/letta-code/701f2a5367828847313876c735ade27b9df97689/package.json — Letta current runtime package.json @ 701f2a536782
