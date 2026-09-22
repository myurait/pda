# 第6本 — コアの機能と、コアと実行器の関係

作成・取得日: 2026-09-21 JST。物差しは `docs/requirements.md`、commit `aa2c92c42cf7941406534eb5b99846a4dcdee86c`。3.1のフローとセル・判定の分担・コアの義務・コアと実行器の関係、3.2-1・5、3.3、A13〜A18を対象とする。第1〜5本の物差し `cdd90e945d938769aefa17a2b8de3236647f6bdc` から要件が更新されている。設計、製品選定、要件追加は行わない。

外部資料を取得して読んだ箇所は「本体確認」、第1〜5本の本文・reviewから引き継ぐ箇所は「報告」と記す。固定SHA、完全なpath:line、逐語引用、PDFページ、取得物のSHA-256は [根拠集](06-core-and-relationship.evidence.md)、再取得照合は [review](06-review.md) に置いた。コードの実行、障害注入、部品間の接続実験、PDAの受け入れ試験はしていない。

## 1. 6つの問いへの回答

1. フローの保持と提案ベースの変更には、限定された対応がある。ConductorのDynamic Forkは、入力のtask定義列から後続を生成する。公式例では前段出力をその入力へ結ぶ。AirflowとArgoにも前段出力から既定task/templateの実行数を増やす機構がある。ただしliteralや別の入力元も許され、全変更を直前セルの指示に限定するA17全体は確認できない。TemporalはWorkerのcommandと子workflow開始履歴を対応付けるが、そのWorkerはPDAの直前セルそのものではない。[CON0–5](06-core-and-relationship.evidence.md#con0)[AF0–2](06-core-and-relationship.evidence.md#af0)[AR0–2](06-core-and-relationship.evidence.md#ar0)[TE0–2](06-core-and-relationship.evidence.md#te0)
2. 決定論的な規則への限定には、再起動回数・時間窓・期限・失敗種別・遮断閾値について仕様と実装の対がある。OTP、Kubernetes Job、Temporal、Resilience4jで確認した。規則の記録も、KubernetesのFailJob理由に含むrule index、OPAの成立規則labelsなどの例がある。ただし全規則が必ず一意に記録されるわけではなく、規則外の判断を必ず交換可能な判定器のセルへ渡す全体構造は未発見である。[ER0–3](06-core-and-relationship.evidence.md#er0)[KJ1–3](06-core-and-relationship.evidence.md#kj1)[TE3–5](06-core-and-relationship.evidence.md#te3)[CB1–3](06-core-and-relationship.evidence.md#cb1)[OP0–4](06-core-and-relationship.evidence.md#op0)
3. 指示文を書かない引き渡しを支える部分機構はある。LangfuseとMLflowは事前promptの取得・変数展開・実行との関連付けを持ち、noWorkflowは計測した計算の依存を記録する。しかしpromptへの参照と実際の最終入力の一致、入力元が事前文と直前出力だけであること、すべてのセルで追記が無いことの強制は別である。A16全体の対は未発見である。[LF1–3](06-core-and-relationship.evidence.md#lf1)[ML1–3](06-core-and-relationship.evidence.md#ml1)[NW1–2](06-core-and-relationship.evidence.md#nw1)[HPR](06-core-and-relationship.evidence.md#hpr)[HPA](06-core-and-relationship.evidence.md#hpa)
4. 中央による仕事の状態保持と再試行には、TemporalのMutableState/Describe、KubernetesのJob状態・controllerが対応する。応答不在の判定にも、server側timerやPekkoのheartbeatとphi閾値がある。ただし中央の記録された状態と、遠隔処理が現に停止したという証明は別である。再配信・同じAPIでの再起動だけでは、別のPDA実行器への中断後再投入と、その規則のevent stream記録を含むA15全体にならない。[TE3–7](06-core-and-relationship.evidence.md#te3)[KJ1–3](06-core-and-relationship.evidence.md#kj1)[PH1–2](06-core-and-relationship.evidence.md#ph1)[PCT](06-core-and-relationship.evidence.md#pct)[HSQ](06-core-and-relationship.evidence.md#hsq)
5. 形に合わない発信の拒否と記録には、Kubernetes APIのdecode拒否と条件付きauditの対応がある。Racketには高階契約のblameを例外へ付ける実装があり、値を提供した側へ責任を帰す抽象と対応する。ただしblame例外は共通event streamへの永続的な不受理記録ではない。KubernetesにもWarn/Ignoreやauditの無効化・脱落があり、A13全体を無条件には認定できない。[KA1–3](06-core-and-relationship.evidence.md#ka1)[HKA](06-core-and-relationship.evidence.md#hka)[PFF](06-core-and-relationship.evidence.md#pff)[RA1–3](06-core-and-relationship.evidence.md#ra1)
6. 関係の形は、フローの正本と実行指示を中央が持つ点でオーケストレーションに近い。PDAが参加者へ委ねるのは、次の経路を選ぶ推論と変更指示の出所である。参加者が提案することだけで、正本も分散するコレオグラフィになるわけではない。BPEL/WS-CDLとの対比に基づく本書の整理であり、既存の形式モデルへの同値性の証明ではない。未改変・コアを知らないランタイムを取り込む境界は第3本のラッパー/adapterが扱うが、内部の全行為の可観測性までは導けない。[PBP](06-core-and-relationship.evidence.md#pbp)[HCD](06-core-and-relationship.evidence.md#hcd)、[第3本・review](03-review.md)の報告。

本書で仕様上の限定された性質と強制位置を対応付けた対は14件である。契約4項目、コアの義務7項、A13〜A18を一体で満たす対は、今回の探索では未発見だった。個々の対を組み合わせれば全体保証が自動的に成立する、または既存の抽象・実装が存在しない、という結論ではない。

## 2. 物差しと前5本の扱い

### 2.1 コアの義務は現行要件の7項を使う

ブリーフの出力指定は「6項」だが、参照先の要件表は7項ある。本書では要件本文を優先し、次の7項を省略せず評価する。以下の番号は表を読むための参照であり、優先順位ではない。

| 参照 | コアの義務 | 評価する範囲 |
|---|---|---|
| 1 | 仕事の引き渡し | 同じ形、typeの事前プロンプトと直前出力/初期入力、指示文を追記しない |
| 2 | 発信の受理 | protocol外形を検査し、不正を不受理として記録。成果の種別分類とフロー指示の反映 |
| 3 | 仕事の状態の保持 | 実行先と実行中・中断・再投入・完了を中央記録から答える |
| 4 | フローの保持 | 構造と変更履歴を保持し、追加変更をセルの指示へ対応付ける |
| 5 | 中断と再投入 | 宣言されたstateに従い、列挙済みの規則で中断・再投入・エラー終了し、規則外は判定器へ渡す |
| 6 | 失敗の判定 | 応答不在、形式違反、宣言した出力種別との不一致等の機械的条件 |
| 7 | 記録 | 上記の行為を実行器のevent streamと同じ形・同じログストアへ記録 |

「満たす」は条件全文、「一部」は条件を支える性質まで、「満たさない」は調べた対の提供範囲でその条件を実現しない場合とする。未読の製品全体に機能が存在しないという意味ではない。入力を受信できたことと、契約上受理したことも分ける。

A14は実行器に問い合わせず中央記録から答えられる条件として扱う。実行器が自分の実行状態を一切持ってはならない、遠隔状態を遅延なく知れる、という条件は追加しない。A15の「同じ形」は再投入時も同じ引き渡し契約であることを指し、試行番号やIDまで同一でなければならないとはしない。A9にも外部副作用の原子的な取消しを追加しない。

### 2.2 引き継ぐ報告と今回更新する箇所

| 入力 | 引き継ぐ報告 | 第6本での扱い |
|---|---|---|
| [第1本v2](01-store-and-protocol.v2.md)・[review](01-review.md) | store、protocol、session/choreography、workflowの個別対応。LangGraphの未知遷移の無視という観察 | 同じprotocolを同じJSON型とはしない。今回は変更要求側と受理側を分け、未知要求の処理を記録する |
| [第2本](02-self-declaration.md)・[review](02-review.md) | 能力宣言、資源・費用・stateの語彙、各種検査 | 宣言の存在から実態との一致を導かない。再試行可能という設定も中断後の実態保証とは別 |
| [第3本](03-runtime-wrapper.md)・[review](03-review.md) | OCI/ACP/LSP、監督、adapterによる変換。通知の省略や未観測範囲 | 部品の再評価はしない。OTPは今回、中央の再起動規則として固定版を新たに読む。heartbeatでは生存中のevent省略を補えない |
| [第4本](04-log-store.md)・[review](04-review.md) | 型検査・履歴・追記証明・前提付き完全性。Activity開始記録の留保 | 「検査を置く場所は未決定」という旧要件での留保は引き継がない。現行要件はラッパーがストアを仲介し、コアが受理時に検査する |
| [第5本](05-whole.md)・[review](05-review.md) | IAM、VW、RouteLLM、DBOS、YAWLの部分的な対。BB1等の抽象。A9と判定器の共通契約の未対応 | 既存の部品は再採点しない。フロー変更の出所、規則の発火根拠、入力の出所に焦点を当て、末尾の集約表を更新する |

## 3. 抽象・不変量・実装の対

本節の14件は本体確認。「不変量」は指定した入力・設定・経路の範囲で保つ性質であり、各製品全体の形式証明という意味ではない。逐語は根拠集へ置き、この表は対応を要約する。実装欄の短縮SHAは根拠集の40桁SHAと固定リンクに対応する。義務欄に挙げる番号はいずれも「一部」であり、挙げない義務は当該対だけでは「満たさない」。

| 対 | 抽象 | 不変量と適用条件 | 実装（強制箇所） | コアの義務7項との対応 | A13〜A18との対応 | 足りないもの |
|---|---|---|---|---|---|---|
| F: Conductor | Dynamic Forkのtask列仕様 [CON0](06-core-and-relationship.evidence.md#con0) | 解決したtask定義列を展開し、後続JOINを要求する | `ForkJoinDynamicTaskMapper.java:195–278,369–414` @`8ac94cf3` [CON1–3](06-core-and-relationship.evidence.md#con1) | 1・2・4・6 | A13・A17が一部 | 入力元を直前出力へ限定する制約、全変更と根拠のevent化、復元 |
| A: Airflow | Dynamic Task Mapping [AF0](06-core-and-relationship.evidence.md#af0) | mapping長に応じ既定taskのinstanceを生成。空ならSKIPPED | `models/taskmap.py:160–315`、`models/expandinput.py:125–155` @`01fc0c5f` [AF1–2](06-core-and-relationship.evidence.md#af1) | 1・3・4・6 | A14・A17が一部 | 任意の新しいtype/実行器を指示する一般的フロー変更ではない。literalも許す |
| G: Argo | `withParam`の反復仕様 [AR0](06-core-and-relationship.evidence.md#ar0) | JSON配列の各要素について同じtemplateのtaskを展開 | `workflow/controller/dag.go:931–988` @`5642521e` [AR1–2](06-core-and-relationship.evidence.md#ar1) | 1・2・4・6 | A13・A17が一部 | 直前出力以外のwithItems/sequenceもある。全変更の由来の強制と不受理ログ |
| T: Temporal | 履歴を中央が構築する仕様、RetryPolicy [TE0](06-core-and-relationship.evidence.md#te0)[HTR](06-core-and-relationship.evidence.md#htr) | Worker commandに応じた履歴構築。最大試行数/期限等で再試行を打ち切る | `workflow_task_completed_handler.go:1244–1266`、`workflow/retry.go:32–113` @`f9ddbdac` [TE1–7](06-core-and-relationship.evidence.md#te1) | 1・2・3・4・5・6・7 | A13・A14・A15・A17・A18が一部 | Workflow Workerと直前セルの相違。試行ごとのlive event全件性。PDA実行器stateとの対応 |
| S: OTP | supervisorの最大再起動強度 [ER0](06-core-and-relationship.evidence.md#er0) | MaxT秒にMaxRを超える再起動なら終了する | `lib/stdlib/src/supervisor.erl:1426–1491,2258–2290` @`d7a2b73d` [ER1–3](06-core-and-relationship.evidence.md#er1) | 3・5・6・7 | A14・A15・A18が一部 | process再起動と仕事再投入の相違。宣言された再開state、共通ログ |
| J: Kubernetes Job | 失敗policyの順序と既定処理 [HKJ](06-core-and-relationship.evidence.md#hkj) | 最初に一致した規則のactionを採用。未一致は既定の失敗集計へ | `pkg/controller/job/pod_failure_policy.go:27–76`、`job_controller.go:1075–1105` @`57c05b7d` [KJ1–3](06-core-and-relationship.evidence.md#kj1) | 3・5・6・7 | A14・A15・A18が一部 | すべての再投入/不受理の個別rule履歴ではない。Podと実行器の組は同一ではない |
| D: Pekko | phi accrualの計算仕様 [HPH](06-core-and-relationship.evidence.md#hph) | 観測heartbeat履歴・時計を入力に、phiがthreshold未満ならavailable | `remote/PhiAccrualFailureDetector.scala:136–166,188–222` @`1f573c99` [PH1–2](06-core-and-relationship.evidence.md#ph1) | 6 | A18が一部 | 疑いの判定のみ。仕事の所有、中断、再投入、全判定の記録は別 |
| C: Resilience4j | Circuit Breakerの状態機械 [HCB](06-core-and-relationship.evidence.md#hcb) | 最低件数を満たすCLOSEDで失敗率等が閾値以上ならOPEN | `CircuitBreakerMetrics.java:141–174`、`CircuitBreakerStateMachine.java:659–669` @`a8a33164` [CB1–3](06-core-and-relationship.evidence.md#cb1) | 5・6・7 | A18が一部 | 遮断とfallback先への仕事移動は別。event listener無しでは記録されない |
| O: OPA | 成立規則のlabelsとdecision logの仕様 [OP0](06-core-and-relationship.evidence.md#op0) | labelのある成立規則からmapを集め、同じmapは統合する | `v1/topdown/evaluated.go:34–50`、`v1/server/server.go:1525–1597`、`v1/plugins/logs/plugin.go:771–871` @`8cb39024` [OP1–4](06-core-and-relationship.evidence.md#op1) | 6・7 | A18が一部 | labelsは任意かつ非一意。logのdrop/mask。すべてのコア操作への強制適用 |
| K: Kubernetes API | API受理・auditの仕様 [HKV](06-core-and-relationship.evidence.md#hkv)・[HKA2](06-core-and-relationship.evidence.md#hka2) | 対象decode違反を拒否し、audit有効の経路でresponse statusを記録する | `handlers/create.go:120–151`、`filters/audit.go:38–147` @`57c05b7d` [KA1–3](06-core-and-relationship.evidence.md#ka1) | 2・6・7 | A13・A18が一部 | validationモード、audit policy/sink/欠落条件。実行器全発信への同一検査 |
| B: Racket | 高階契約とblame [PFF](06-core-and-relationship.evidence.md#pff) | 契約の正負位置に応じ責任側を反転し、違反時にそのblameを付ける | `contract/private/arrow-val-first.rkt:675–692`、`blame.rkt:280–285,347–385` @`45f34393` [RA1–3](06-core-and-relationship.evidence.md#ra1) | 2・6 | A13・A18が一部 | 契約に書いた検査対象に限定。共通event streamへの不受理の必須記録 |
| L: Langfuse | prompt取得・template展開の仕様 [HLF](06-core-and-relationship.evidence.md#hlf) | text templateの固定部分と変数値から展開結果を作る | `langfuse/model.py:88–114`、`_client/attributes.py:133–146` @`65392c73` [LF1–3](06-core-and-relationship.evidence.md#lf1) | 1・7 | A16が一部 | 変数の出所と最終入力の一致。fallback時のprompt版属性。追記の禁止 |
| M: MLflow | promptの取得・format仕様 [HML](06-core-and-relationship.evidence.md#hml) | 通常のdouble-brace展開で値を置換し、既定では不足変数を拒否 | `mlflow/genai/prompts/utils.py:1–12`、`prompt_version.py:537–573` @`3e1b7122` [ML1–3](06-core-and-relationship.evidence.md#ml1) | 1・7 | A16が一部 | prompt/trace関連付けは最終入力の強制検査ではない。許される入力源の制限 |
| N: noWorkflow | scriptの実行provenance [PNW](06-core-and-relationship.evidence.md#pnw) | 計測した評価とその依存評価をIDで結び付ける | `prov_definition/definition.py:89–134`、`prov_execution/collector.py:2011–2046` @`4a2c4c8b` [NW1–2](06-core-and-relationship.evidence.md#nw1) | 7 | A16が一部 | 外部ランタイム内部、全依存の捕捉、許容入力源以外の禁止 |

### 3.1 フロー変更の「できる」と「それだけに限定する」

本体確認。Conductorでは、task入力を解決し、動的task列とtaskごとの入力mapを得てからtaskを生成する。これは前段の成果で後続の構造を与える具体例である。公式cookbookは `${prepare.output.result.dynamicTasks}` を参照する。ただしprepare自体はINLINEのJavaScriptであり、PDAの未改変ベンダー実行器の例ではない。一般の入力解決器にはworkflowや各taskの入力・出力が渡る。前段出力だけを唯一の変更根拠にするゲートではない。[CON1–5](06-core-and-relationship.evidence.md#con1)

AirflowではSchedulerXComArgとliteralの長さ取得が別経路になり、既定taskのinstanceにmap_indexを付けて増やす。Argoも既定templateを配列の各要素へ展開する。これらは「実行するinstanceの数が動的」であり、任意のセルtypeと実行器を新たに決め、フロー定義全体を任意に変更することと同一ではない。どちらも前段出力への参照は表せるが、その参照を全変更に義務付けるA17ではない。[AF0–2](06-core-and-relationship.evidence.md#af0)[AR0–2](06-core-and-relationship.evidence.md#ar0)

Temporalの子workflow開始eventには、commandを返したWorkflowTaskの完了event IDが渡される。中央serverが意味的な計画を作らず、Workerが決めたcommandを反映するという役割分担は対応する。しかしWorkflow Workerのコードが行う計画は、PDAの共通契約で包んだ判定器のセルとは限らない。serverは利用者のStart/Cancel/Update/Signal/Reset等も扱う。外部signalの受信自体をフロー変更と数えず、それを受けたWorkerが何のcommandを出したかを分ける必要がある。[TE0–2](06-core-and-relationship.evidence.md#te0)

### 3.2 列挙された規則、決定性、規則の記録

本体確認。OTPはrestart種別と終了reasonを分岐し、monotonic時刻の期間内再起動回数を計算する。上限超過を `reached_max_restart_intensity` としてreportする。一方、未知のinfoはerror logを出して状態を維持する。未知事象を意味判断の実行器へ自動的に送る構造ではない。[ER0–3](06-core-and-relationship.evidence.md#er0)

KubernetesのPod failure policyは配列順に照合する。FailJobのmessageにはactionとrule indexが入り、Job controllerがFailureTargetのreason/messageとして保持する。Ignore/Count/FailIndexの返却には、同じ形式のrule index付きmessageは無い。backoffLimitとactiveDeadlineSecondsにも名前付きの終了理由があるが、これを中断・再投入・エラー終了・不受理の全件履歴と同一視しない。[KJ1–3](06-core-and-relationship.evidence.md#kj1)

OPAでは固定SHAの仕様と実装の双方に `rule_labels` があった。評価時のtrackerを通じて、成立した規則のannotation由来のlabelsをdecision logへ渡す。したがって「判定IDしかなく規則の情報は出せない」とは評価しない。ただしlabel無しは記録せず、同じmapは統合する。規則の一意な識別と全判定の網羅は、この任意labelだけでは成立しない。さらにdrop/mask policyでlogを省ける。[OP0–4](06-core-and-relationship.evidence.md#op0)

Resilience4jのCLOSEDからOPENへの閾値分岐には、失敗率・遅延率のeventと状態遷移がある。しかしlistenerが無ければeventを発行しない。遮断ができることから、別実行器への再投入、fallback順序、共通logへの必須記録は導けない。[CB1–3](06-core-and-relationship.evidence.md#cb1)

規則を機械的に評価すること、同じ観測値と時刻で同じ結果になること、意味的な計画を中央に持たないことは別の条件である。任意のplannerや利用者コードを中央へ置いても「通常のプログラムだから決定的」というだけでは、3.1・3.3の責務制限を満たさない。HYDRAのpolicy/mechanism分離はこの区別の参考となる抽象だが、PDAの規則集合やevent streamを規定するものではない。[PHY](06-core-and-relationship.evidence.md#phy)

### 3.3 応答不在、中央状態、再投入

本体確認。Temporalではserverの時刻とactivity timerで期限を判定し、retry policyを照合する。回数上限、取消要求、再試行しない失敗、期限等に応じたRetryStateがあり、継続時にはattemptを増やしretry taskを作る。Describeは中央のMutableStateからworkflow状態とpending activity/childを組み立てる。これらはA14・A15の部分的な対応である。[TE3–7](06-core-and-relationship.evidence.md#te3)

ただし公式仕様は、ActivityTaskStartedをactivityの完了または再試行尽きによる失敗までhistoryへ載せず、途中のattempt数にはDescribeを使うと説明する。状態照会が可能でも、再試行判断のすべてが実行中のevent streamに逐次残るとは限らない。通常のactivity再試行と「実行中の仕事を中断して別の環境・アカウント・エージェントへ渡す」というA15全体も分ける。[HTR2](06-core-and-relationship.evidence.md#htr2)

Pekkoのphiはheartbeatの経過時間と過去の間隔から計算され、閾値と比較される。履歴に応じた数値計算であり、成果の意味的良否を推論する処理ではない。未監視、すなわちheartbeatを一度も受けていない対象はphiを0として扱う。監視対象として既に確立していることが判定の前提になる。[HPH](06-core-and-relationship.evidence.md#hph)[PH1–2](06-core-and-relationship.evidence.md#ph1)

Chandra–Touegは故障検出器をcompletenessとaccuracyで区分する。完全非同期の環境で遅い処理と停止を安易に同一視できないこと、誤ったsuspectを許す抽象を用いることが重要である。本書はPekkoの閾値実装を、論文のperfect failure detectorの実装証明として対応付けていない。[PCT](06-core-and-relationship.evidence.md#pct)

SQSの可視性期限切れは再び取得可能にする契約であり、処理の成功・停止を証明しない。仕様は期限内の重複配信の可能性も留保する。Kafkaにも、処理後・offset保存前の停止で再処理が起きる例がある。再配信される形式の共通性は確認材料だが、宣言したstateに従う中断・再投入や、その規則の共通記録の代わりにはならない。[HSQ](06-core-and-relationship.evidence.md#hsq)[HKF](06-core-and-relationship.evidence.md#hkf)

第3本が残した「ラッパーが生存し、heartbeatを返しながら必要eventを省く」場合について、今回の故障検知は空白を埋めない。確認できるのは観測された応答や期限の条件であり、未観測の内部行為の全件性ではない。この点は第4本の前提付き完全性の報告と両立する。

### 3.4 不受理と責任の帰属

本体確認。KubernetesのAPI仕様はStrict/Warn/Ignoreを区別する。[HKV](06-core-and-relationship.evidence.md#hkv) create handlerにはdecode失敗をHTTP errorへする経路がある一方、strict decoding errorでもWarnモードなら警告を付けて継続する経路がある。audit filterは有効なpolicy/sinkがあればHTTP statusとResponseComplete stageを記録する。policyのNone、未設定のsink、batchのbuffer超過などを除外して初めて、対象拒否をauditで追う限定した対応になる。[KA1–3](06-core-and-relationship.evidence.md#ka1)[HKA](06-core-and-relationship.evidence.md#hka)

Racketの契約では関数の引数側と戻り値側でblameの向きが変わり、高階の入れ子でも値を供給した責任側を追う。取得コードでは引数個数違反をcaller側へ帰し、blame objectを例外へ格納する経路まで確認した。契約に書いた述語や境界に対する責任帰属であり、任意の実行器の不正全般、意図、成果品質を判定する機構ではない。[PFF](06-core-and-relationship.evidence.md#pff)[RA1–3](06-core-and-relationship.evidence.md#ra1)

このblameをそのままPDAへ移せば自動的に「ベンダー本体とラッパーのどちらが悪いか」が分かるとはしない。コアが検査したメッセージの提供者と、その前の変換をどの契約境界として観測したかに依存する。また例外を作る処理と、A13の不受理をevent streamへ必ず残す処理は別である。

### 3.5 事前文、前段出力、入力の出所

本体確認。Langfuseのtext compileはtemplateの固定部分と与えた変数値を連結する。未指定変数は元のplaceholderを残す。観測属性にはpromptのname/versionを付けられるが、fallback promptでは付けず、観測inputもpromptとは別の引数である。prompt版を参照したことと、その版から得た文字列だけをランタイムへ渡したことは同じ証拠ではない。[HLF](06-core-and-relationship.evidence.md#hlf)[LF1–3](06-core-and-relationship.evidence.md#lf1)

MLflowにも版を指定したprompt取得、通常のdouble-brace置換、不足変数の拒否、active traceとの関連付けがある。allow_partialやJinja形式という別の利用経路もある。公式資料はprompt版のimmutable性を説明するが、本書で実装との対にしたのは取得・展開・関連付けであり、あらゆる書込経路に対する不変性の証明ではない。[HML](06-core-and-relationship.evidence.md#hml)[ML1–3](06-core-and-relationship.evidence.md#ml1)

noWorkflowはPythonのASTを計測用に変換し、評価同士の依存IDを記録する。利用者が元sourceを手で変更しなくても、実行コードには計測が入る。論文はnetwork/DBアクセス自体を直接捕捉せず、その呼出関数を捕捉すると留保する。未改変の外部ベンダーランタイム内部まで透過的に計測できるとは解釈しない。[PNW](06-core-and-relationship.evidence.md#pnw)[PNW2](06-core-and-relationship.evidence.md#pnw2)[NW1–2](06-core-and-relationship.evidence.md#nw1)

W3C PROVはentity/activity/agent等の関係を記述し、その記述の整合性を扱う。PROV-AQはprovenance記録それ自体に正確性や権威性の保証がないと明記する。記録された依存辺から入力の出所を検査することと、記録されていない別の追記経路が無いことを保証することは分かれる。A16の「どのセルも」「だけから成る」まで閉じた対は今回未発見である。[HPR](06-core-and-relationship.evidence.md#hpr)[HPA](06-core-and-relationship.evidence.md#hpa)

### 3.6 計画する側、実行を管理する側、中央を知らない参加者

本体確認。GTPyhopのrun_lazy_lookaheadはplannerを呼び、得たaction列をcommandとして実行し、失敗時には再び計画する。対応するcommandが無ければaction関数を使う。計画と実行の役割分離は確認できるが、両者は同じPython domain/stateを扱う関数であり、判定器がPDAの共通実行器契約を持つという強制ではない。HTNの実行・再計画研究にも、失敗や外生事象で予想外の状態になるという問題設定がある。[HT1](06-core-and-relationship.evidence.md#ht1)[PHT](06-core-and-relationship.evidence.md#pht)

BDI/Jasonのsense・deliberate・actも役割を分けるが、外部event、初期goal、内部演算から新たなintentionを作る。中央のフロー変更を直前セルの出力へ限定する仕様ではない。[HBD](06-core-and-relationship.evidence.md#hbd) 第5本が確認したBB1のcontrol knowledgeとschedulerの分離は、判定器のセルと機械的コアの対応を考える抽象として残るが、固定実装での強制位置は引き続き未確認である（報告）。

要件のjevエントリポイントは、仕事を受けた後のモデル選定を共通契約の判定器へ渡すという制御上の役割である。初期セルを定めることはplannerやworkflowのentrypointに対応付けられるが、特定のjev実装が永続的に不可欠であるという意味には読まない。A4の判定器交換可能性も同時に物差しに残る。今回のplannerやworkflow機構だけから、jevを含むすべての判定器が同じ宣言・受渡し・event契約に従うという対は得られていない。

BPELは一参加者のprocessの振る舞いを記述し、WS-CDLは参加者間の共通かつ補完的な観測可能動作をglobalに記述する。WS-CDL 1.0の取得版は2005年のCandidate Recommendationであり、最終Recommendationとして扱わない。PDAの中央保持と参加者起点の変更は、フローの所有と変更判断の出所を分ける構造として整理できる。[PBP](06-core-and-relationship.evidence.md#pbp)[HCD](06-core-and-relationship.evidence.md#hcd)

参加者内部を外から区別せず観測可能な通信に着目する抽象と、既存runtimeを無変更で接続するadapterは関連するが、前者だけで後者の実装が生じるわけではない。第3本のOCI/LSP/ACPの報告では、境界をラッパーが吸収できる一方、公開された外部interfaceの制約と省略が残る。コアの契約を知る必要があるのはラッパーであり、ランタイム本体がストアに直接触れることは現行要件の前提ではない。

## 4. 契約4項目とA13〜A18の判定

### 4.1 実行器契約

この表は各対を単独で見た判定である。全体の契約を満たすとした行はない。

| 対 | 能力の宣言 | 仕事の受け取り | 成果の返却 | event stream | 不足の要点 |
|---|---|---|---|---|---|
| F: Conductor | 一部 | 一部 | 一部 | 一部 | task定義・入力・出力はあるが、環境/アカウント/エージェントと内部event全件の統一契約ではない |
| A: Airflow | 満たさない | 一部 | 一部 | 一部 | task定義とXCom、状態・task logはPDAの宣言4項と同一ではない |
| G: Argo | 一部 | 一部 | 一部 | 一部 | template/parameter/outputとnode状態。ベンダー実行器の共通event変換は別 |
| T: Temporal | 一部 | 一部 | 一部 | 一部 | task type/queue/timeout等の部分宣言。activity内部と試行中履歴に限界 |
| S: OTP | 一部 | 一部 | 満たさない | 一部 | child仕様・起動引数・report。仕事の成果契約と全eventは別 |
| J: Kubernetes Job | 一部 | 一部 | 満たさない | 一部 | Pod仕様と状態。仕事の成果型、全内部行為は定めない |
| D: Pekko | 満たさない | 満たさない | 満たさない | 満たさない | 対象は故障の疑いを返す検知器の計算経路 |
| C: Resilience4j | 満たさない | 一部 | 一部 | 一部 | 呼出しを包む入出力・例外・状態通知に限定 |
| O: OPA | 満たさない | 一部 | 一部 | 一部 | policy入力と判定結果のAPI。実行器全行為の共通streamではない |
| K: Kubernetes API | 満たさない | 一部 | 一部 | 一部 | API要求・応答の検査とaudit。実行器契約全体ではない |
| B: Racket | 一部 | 一部 | 一部 | 満たさない | 関数の入出力契約の部分宣言。外部実行器のevent形式と永続化は別 |
| L: Langfuse | 満たさない | 一部 | 満たさない | 一部 | prompt展開・trace関連付け。実行器成果の共通受理は対象外 |
| M: MLflow | 満たさない | 一部 | 満たさない | 一部 | prompt展開・trace関連付け。実行器の統一入出力境界ではない |
| N: noWorkflow | 満たさない | 満たさない | 満たさない | 一部 | 計測されたPythonの実行provenance。ベンダー横断の共通live streamではない |

前表は、各資料にある一般的なtask定義や入出力を部分対応として読むもので、コアの全義務の認定ではない。第2〜4本で既に調べた宣言・ラッパー・ログの部品の採点を変更するものでもない。

### 4.2 受け入れ条件

| 対 | A13 不受理と記録 | A14 中央状態 | A15 中断後の別実行器への再投入 | A16 入力の限定 | A17 変更の限定 | A18 規則の特定 |
|---|---|---|---|---|---|---|
| F: Conductor | 一部 | 満たさない | 満たさない | 満たさない | 一部 | 満たさない |
| A: Airflow | 満たさない | 一部 | 満たさない | 満たさない | 一部 | 満たさない |
| G: Argo | 一部 | 満たさない | 満たさない | 満たさない | 一部 | 満たさない |
| T: Temporal | 一部 | 一部 | 一部 | 満たさない | 一部 | 一部 |
| S: OTP | 満たさない | 一部 | 一部 | 満たさない | 満たさない | 一部 |
| J: Kubernetes Job | 満たさない | 一部 | 一部 | 満たさない | 満たさない | 一部 |
| D: Pekko | 満たさない | 満たさない | 満たさない | 満たさない | 満たさない | 一部 |
| C: Resilience4j | 満たさない | 満たさない | 満たさない | 満たさない | 満たさない | 一部 |
| O: OPA | 満たさない | 満たさない | 満たさない | 満たさない | 満たさない | 一部 |
| K: Kubernetes API | 一部 | 満たさない | 満たさない | 満たさない | 満たさない | 一部 |
| B: Racket | 一部 | 満たさない | 満たさない | 満たさない | 満たさない | 一部 |
| L: Langfuse | 満たさない | 満たさない | 満たさない | 一部 | 満たさない | 満たさない |
| M: MLflow | 満たさない | 満たさない | 満たさない | 一部 | 満たさない | 満たさない |
| N: noWorkflow | 満たさない | 満たさない | 満たさない | 一部 | 満たさない | 満たさない |

A18の一部には、規則をコード/設定から指示できるがログの全件性は不足する例も含む。A15の一部には、同じprocess/Activity/Podの再起動・再試行という、別のPDA実行器への移動より狭い例を含む。ここを全文の達成へ繰り上げない。

## 5. 決定論的な規則の一覧と規則外の扱い

本体確認。列挙した処理経路の比較であり、各システムの全判定がこれだけに限定されるという表ではない。

| 対象・規則 | 一覧を外から読めるか | 規則/根拠の記録 | 一致しない事象・未知指示の扱い | PDAとの境界 |
|---|---|---|---|---|
| OTP: restart種別、終了reason、MaxR/MaxT | child spec、supervisor flags、case節 [ER0–2](06-core-and-relationship.evidence.md#er0) | child_terminated、上限超過reason等 | 未知infoはlog後に状態維持 [ER3](06-core-and-relationship.evidence.md#er3) | 規則外を判定器のセルへ委譲しない |
| Kubernetes Job: Ignore/Count/FailIndex/FailJob、backoff、deadline | Job specの順序付きrulesとcontroller [HKJ](06-core-and-relationship.evidence.md#hkj)[KJ1–2](06-core-and-relationship.evidence.md#kj1) | FailJobのindex、名前付きcondition reason | 未一致は通常の失敗集計。終了条件未成立ならreconcile継続 | FailJob以外も含む全規則の発火履歴は別 |
| Temporal: retry回数・期限・非再試行失敗・取消し | RetryPolicyとRetryState、command dispatch [TE1](06-core-and-relationship.evidence.md#te1)[TE3–4](06-core-and-relationship.evidence.md#te3) | RetryState、history、中央attempt状態 | commandは拡張handlerも照合し、無ければInvalidArgument。意味判断をserverが補うわけではない | 途中の全試行がhistoryへ即時掲載されるわけではない [HTR2](06-core-and-relationship.evidence.md#htr2) |
| Pekko: heartbeat間隔からphi、threshold比較 | detector設定と計算式 [HPH](06-core-and-relationship.evidence.md#hph)[PH1–2](06-core-and-relationship.evidence.md#ph1) | 今回確認した計算APIは値/availableを返す | 閾値未満はavailable、heartbeat未観測もavailable扱い | 指示の不受理や意味判断を行う入口ではない |
| Resilience4j: 最低件数、失敗率/遅延率、状態 | configと状態機械 [HCB](06-core-and-relationship.evidence.md#hcb)[CB1–2](06-core-and-relationship.evidence.md#cb1) | 閾値・状態eventはlistener等の条件付き | 最低件数未満/閾値未満はCLOSEDを維持。OPENで呼出しを遮断 | fallback先選択や仕事移管はこの状態機械の外側 |
| OPA: Rego policy評価、labels採取 | policy sourceとbundle revision [OP0–2](06-core-and-relationship.evidence.md#op0) | 任意labels、input/result、decision ID。drop/maskあり | Data APIでundefinedはresultなしの成功応答。呼出し側の方針に委ねる [OP1](06-core-and-relationship.evidence.md#op1) | Regoの一般的な表現能力とPDAの中央判定制限は別。無結果を自動で判定器へ渡さない |
| Kubernetes API: decode/validation | 型、validationモード、handler [KA1–3](06-core-and-relationship.evidence.md#ka1) | audit policyに従うstatus/理由 | Strictで対象違反を拒否、Warnでは一部違反を警告して継続 | 未知fieldも常に拒否し記録するという契約ではない |
| Racket: 関数契約 | contract式とblame位置 [PFF](06-core-and-relationship.evidence.md#pff)[RA1–3](06-core-and-relationship.evidence.md#ra1) | blame objectを持つ例外 | 違反は例外。対象外の行為を監査する規則は生じない | 例外処理と必須event化は別 |

Production rule/RETEの起点ではDroolsのafterMatchFired APIを確認した。発火後の通知口があることまでは分かるが、本書では固定実装で全発火の必須記録を追っていないため、上表の対へ加えていない。RETEという照合アルゴリズム名だけから、全規則の決定性・一意な発火順・監査完全性は認定しない。[HRE](06-core-and-relationship.evidence.md#hre)

## 6. フロー変更の出所

本体確認と第5本からの報告を分けた表である。「中央自身」は、管理側の定義・コード・規則が経路を選ぶ場合を指す。エンジンが提案を機械的に反映するだけの場合まで、自発的な変更とは数えない。

| 対象 | 前段出力からの変更 | 外部からの操作・入力 | 管理側の定義/コードによる経路決定 | 出所をどう区別できるか | A17に足りないもの |
|---|---|---|---|---|---|
| Conductor | 前段のtask列を参照して動的fork可能 | workflow入力も参照可能。全管理APIは未照合 | literal task列やINLINEで生成した列も使える | `${prepare.output...}`等の参照とfork task入力 [CON1–5](06-core-and-relationship.evidence.md#con1) | 入力源の参照は表せるが、全変更を直前セル指示へ制限しない |
| Airflow | XComのlist/dictから展開 | 外部データを返すtaskもある。管理操作全体は未照合 | DAG定義のliteralでも展開 | XComArgとliteralの型分岐、task ID/map_index [AF0–2](06-core-and-relationship.evidence.md#af0) | 既定taskのinstance展開。直前のフロー指示という必須契約ではない |
| Argo | 別stepが返すJSONをwithParamへ利用 | workflow引数等による展開も表現可能 | withItems/withSequence、既定template | workflowの式と展開されたtask。履歴上の全出所分類は未確認 [AR0–2](06-core-and-relationship.evidence.md#ar0) | 配列の出所を前段に限定しない |
| Temporal | Activity成果を読むWorkerがcommandを返せるが、直前セルの指示と同義ではない | Start/Signal/Update/Cancel/Reset等 | Workflow Workerの制御コード。server側はretry/timer規則 | 子開始をWorkflowTaskCompletedEventIdへ結ぶ。利用者要求とWorker要求を区別 [TE0–2](06-core-and-relationship.evidence.md#te0) | 意味的な元指示と全フロー変更の一対一対応、他経路の禁止 |
| YAWL（報告） | caseデータで選択。前段だけには限定されない | 人によるRDR規則追加 | 規則木からworklet選択 | 選択rule ID、cornerstone、任意説明等 [第5本](05-whole.md) | A17の出所限定、A9の一体の必須記録/復元は未確認 |
| GTPyhop | command失敗後に再計画 | 外生変化を再計画の問題として扱う | actorがplannerを直接呼ぶ | plan/actionとverbose出力 [HT1](06-core-and-relationship.evidence.md#ht1)[PHT](06-core-and-relationship.evidence.md#pht) | 判定器のセル出力として指示を受理し、履歴へ必須対応させる境界 |
| AIOC（抽象側） | 直前成果だけに限定しない | Adaptation Manager/Serverの候補と環境情報 | scopeのcoordinatorが更新を調停 | scope・coordinator・更新protocolを形式に持つ [PAI](06-core-and-relationship.evidence.md#pai)[PAI2](06-core-and-relationship.evidence.md#pai2) | PDAの中央正本・共通契約との対応。固定実装の強制位置は未照合 |

前段出力との対応付けにより、A9の「根拠」の一部を具体化できる例は増えた。ただし追加変更前後、日時、元へ戻す操作を一体で確認したわけではない。A17の部分対応だけで第5本のA9の空白が解消したとはしない。

## 7. 片側のみ、未発見、取得の限界

| 探索起点・検索語 | 確認した資料 | 今回の到達点と揃わない理由 |
|---|---|---|
| HTN planning execution monitoring / GTPyhop run_lazy_lookahead | 著者論文、固定GTPyhop [PHT](06-core-and-relationship.evidence.md#pht)[HT1](06-core-and-relationship.evidence.md#ht1) | 計画→command実行→失敗時再計画のコードを確認。論文のIPyHOPの改善定理/結果を別実装GTPyhopへ移さない。PDA契約の判定器・中央との対は未成立 |
| BDI deliberation execution / Jason reasoning cycle | 著者のJason技術資料 [HBD](06-core-and-relationship.evidence.md#hbd) | 抽象・仕様側。3段階の実行とintention生成元は確認。固定interpreterの強制位置は未照合 |
| BB1 control plan / scheduler | 第5本のBB1論文確認（報告） | control knowledgeを外へ分ける抽象。PROTEAN等の固定実装とコア規則・共通ログの対応は未確認 |
| Valk self-modifying nets 1978 / natural extension Petri nets | 著者の書誌 [HVA](06-core-and-relationship.evidence.md#hva) | 論文の所在確認のみ。論文本体と固定実装は未取得。「自己修正」という名前から経路変更の出所制約を推測しない |
| graph rewriting / GROOVE rule application | 著者のGROOVE論文§1.2 [PGR](06-core-and-relationship.evidence.md#pgr) | 抽象側。適用条件、追加・削除、状態空間を表せる。規則のmatchを持つこと自体は、変更根拠が直前セル出力である制約ではない。固定コードは未照合 |
| dynamic process topology / dynamic choreography runtime update | AIOC/DIOC/DPOC論文 [PAI](06-core-and-relationship.evidence.md#pai)[PAI2](06-core-and-relationship.evidence.md#pai2) | 抽象側。scopeの更新主体と同期を扱う。外部の更新候補を含み、生成された参加者のprotocolを使う。未改変の任意runtimeをそのまま扱う対ではない |
| policy mechanism separation / HYDRA | 原論文p.2 [PHY](06-core-and-relationship.evidence.md#phy) | 抽象側。方針を機構から分ける原則。歴史的kernelの固定コードは未照合。OPAをHYDRAの直接実装とはしない |
| production rule RETE fired rule audit / Drools AgendaEventListener | 公式API [HRE](06-core-and-relationship.evidence.md#hre)、OPAの別系統の規則labels [OP0–4](06-core-and-relationship.evidence.md#op0) | DroolsはAPI側のみ。RETEの照合と発火規則の完全な記録を同一視しない。OPAはRETEの実装例として扱っていない |
| circuit breaker retry budget fallback | Resilience4j仕様・コード、Envoy公式資料 [HCB](06-core-and-relationship.evidence.md#hcb)[CB1–3](06-core-and-relationship.evidence.md#cb1)[HRB](06-core-and-relationship.evidence.md#hrb) | 遮断には対あり。retry budgetの指定起点は最大再試行量の説明まで。固定Envoy実装、PDAのfallback順序全体は未照合 |
| lease heartbeat Chandra Toueg failure detector | 論文、Pekko、Temporal、SQS [PCT](06-core-and-relationship.evidence.md#pct)[PH1–2](06-core-and-relationship.evidence.md#ph1)[TE5](06-core-and-relationship.evidence.md#te5)[HSQ](06-core-and-relationship.evidence.md#hsq) | heartbeatの疑いと期限判定には部分機構。特定failure detectorクラスへの現行実装の形式適合は未証明 |
| SQS visibility timeout / Kafka rebalancing at-least-once | 両公式仕様 [HSQ](06-core-and-relationship.evidence.md#hsq)[HKF](06-core-and-relationship.evidence.md#hkf) | 仕様側。今回Kafkaのgroup coordinatorの固定コードは未照合。SQSの非公開serverを検査したとはしない。再配信を仕事の全状態とみなさない |
| Findler Felleisen higher-order contracts blame | 原論文とRacket [PFF](06-core-and-relationship.evidence.md#pff)[RA1–3](06-core-and-relationship.evidence.md#ra1) | blameの限定した対あり。PDAの不受理eventの必須記録へ結ぶ対は未発見 |
| W3C PROV noWorkflow input lineage | PROV仕様、noWorkflow論文/コード [HPR](06-core-and-relationship.evidence.md#hpr)[HPA](06-core-and-relationship.evidence.md#hpa)[PNW](06-core-and-relationship.evidence.md#pnw)[NW1–2](06-core-and-relationship.evidence.md#nw1) | PROVの記述整合性とnoWorkflowの採取を別系譜として確認。noWorkflowの全記録がPROVの全制約を満たすという実装照合はしていない |
| Langfuse MLflow prompt registry version trace / DSPy signature | registry仕様/コード、DSPy公式仕様・固定source [LF1–3](06-core-and-relationship.evidence.md#lf1)[ML1–3](06-core-and-relationship.evidence.md#ml1)[DS1–2](06-core-and-relationship.evidence.md#ds1) | registryの限定した対あり。DSPyは既定instructionをfield名から生成する経路を確認。型付きsignatureだけで「事前文以外を書かない」は成立しない |
| orchestration choreography BPEL WS-CDL / adapter unaware participant | BPEL/WS-CDL一次仕様 [PBP](06-core-and-relationship.evidence.md#pbp)[HCD](06-core-and-relationship.evidence.md#hcd)、第1・3本の報告 | 関係の抽象側。特定BPEL engineの固定強制位置は未照合。外部runtimeが中央を知らないことと、完全な観測契約は別 |

未発見の主要な対応は、A16の全入力の限定、A17の全変更の出所限定、A18の全判定の規則特定と必須記録、それらを共通契約の判定器と未改変runtimeの両方へ結ぶ全体である。表の検索語と一次資料の範囲で未発見であり、一般的な不可能性や実装の不存在を意味しない。

採用資料のHTTP失敗はない。Valkの論文本体は所在確認後も取得先を確定できなかった未取得資料であり、本文の主張には使っていない。DSPyの旧URLと途中の誘導先はHTTP 200でも誘導用HTMLだった。さらに誘導先をたどって公式本文を取得し、固定Git sourceと区別して記録した。取得状態の詳細は [根拠集](06-core-and-relationship.evidence.md#3-取得状態と探索の限界) を参照する。

## 8. 6本を通した、未対応の抽象・実装の集約

第5本の集約表を更新したもの。「抽象側のみ」はその抽象の固定実装の強制位置が今回未確認、「実装側から未対応」は確認したコードを要求全体の抽象へ結ぶ根拠が未確認という意味である。「どの抽象にも実装が無い」「どの実装にも抽象が無い」という世界全体の主張にはしない。前5本部分は報告、第6本の追加部分は本体確認である。

| 範囲 | 確認済みの抽象側 | 確認済みの実装側 | 第6本を含む未対応・未発見部分 | 根拠 |
|---|---|---|---|---|
| blackboardで制御知識を変える | BB1のcontrol plan/scheduler | 論文内の実装報告 | 抽象側のみ。固定コードで制御知識の更新と根拠・前後・復元を確認する対は未完成 | 第5本の報告 |
| ラッパーによるprotocol整合と中央非依存 | session types、adapter synthesis、Wrapper Facade | ACP/OCI/LSP等の検査・変換 | 合成の抽象に対する固定実装未照合、実adapterの変換と形式的保証の対応が残る。未改変runtimeの未観測行為まで閉じた契約は未確認 | 第1・3本の報告、本書3.6 |
| 動的participant追加・置換 | EnsembleS、Open Multiparty Sessions、IAM | IAM model checker。EnsembleSはartifact所在 | 動的発見の定理と実装の強制位置、および環境・account・agentの組でA2全体を保つ対応は未確認 | 第5本の報告 |
| 能力宣言と実態 | FIPA/MCP等、費用・資源・state語彙、契約 | schema・配置・権限の部分検査 | 抽象/実装とも部分的にある。宣言した全項目と実態を一体で照合する対は未発見 | 第2本の報告 |
| 成果の種別と再注入 | 型付きprotocol、入出力契約、blame | 受理検査、adapter変換、Racketの責任付き例外 | 全実行器で種別分類・再注入・不受理記録を保つ対は未確認。blame追加で共通event化までは埋まらない | 第1〜3本の報告、本書B/K |
| event完全性と監査 | PeerReview/SLiC等の前提付き完全性、CT | event/journal/schema/追記証明、条件付きaudit | 抽象側の固定実装未照合と、未観測行為の完全性が残る。heartbeatは生存中のevent省略を補わない | 第3〜4本の報告、本書D/K |
| 非決定処理を含むreplay | durable workflowのstep分離 | DBOS結果再利用、Temporal等の履歴 | 任意非決定性の検出、未記録外部呼出の一度限り、LLMの再生成同一性へは拡張不可 | 第1・4・5本の報告 |
| 判定器による割り振りとentrypoint | contextual bandit、routing、RDR、計画/実行分離 | VW/RouteLLM/YAWL、GTPyhop、Worker commandの処理 | planner/判定器自身が共通実行器契約に従い交換できる全体の対は未発見。jev初期セルという役割だけでは埋まらない | 第5本の報告、本書T・3.6 |
| 可変段数の統合とメッシュ監査 | 多層推論、workflow/合成理論 | worklet、dynamic fork、mapping、子workflow | 経路可変の具体例は増えたが、共通契約で統合→監査→再確認を行う全体の対応は未確認 | 第1・5本の報告、本書F/A/G/T |
| A9の自己改変と取消し | policy更新、動的規則、変更履歴 | model保存、YAWL編集/event、Git、前段出力からの展開 | A17に関係する根拠参照は具体化した。日時・根拠・変更前後・元への復元を一体で保証する対は引き続き未発見 | 第4〜5本の報告、本書6節 |
| A17の前段指示だけによる全変更 | task-generated展開、command/event対応。GROOVE/AIOCは抽象側も確認 | Conductor/Airflow/Argo/Temporalの限定経路 | 実装側から未対応。前段指示との対応を全変更に強制し、literal・外部・管理側コードの別経路を排除する抽象/実装の対は未発見 | 本書F/A/G/T、PGR/PAI |
| A18の規則限定と全判定の記録 | supervisor、Job policy、retry、circuit breaker、policy/mechanism | 回数・時間の分岐、reason、rule index、OPA labels | 個別対は成立。全中断・再投入・エラー終了・不受理を列挙規則と必ず結び、規則外を共通契約の判定器へ渡す対は未発見 | 本書S/J/T/C/O |
| A16の入力源限定と追記不在 | prompt template/version、provenance | Langfuse/MLflowの取得・展開・関連付け、noWorkflow依存採取 | 双方に部分機構あり。全セルの最終入力が事前文と直前出力/初期入力だけであることを強制し、eventから確認する対は未発見 | 本書L/M/N、HPR/HPA |
| A14/A15の状態と別実行器への再投入 | 中央状態機械、retry、failure detector、再配信仕様 | MutableState、Job controller、supervisor、phi閾値 | 中央記録と疑いの判定は具体化した。PDA実行器の宣言stateに従う中断/再投入、同形引渡し、全規則の共通記録を一体にする対は未発見 | 本書T/J/S/D |
| 全契約を保つ実行器交換とコアの義務 | IAM等の限定置換理論、5要素の個別抽象、今回の部分対 | 部分機構は多数確認 | A1〜A4とA13〜A18を同じ全体実装に対応付ける根拠は未確認。会社/個人のA3も残る | 第1〜6本 |

本書がブリーフ群の最終本であり、他の未実施の本へ渡す問いはない。残る対応関係は上表に留め、設計方針や新規実装の必須性へ変換しない。
