# 第5本 — 異種エージェントを交換可能な実行器として扱う系

作成・取得日: 2026-09-20 JST。物差しは `docs/requirements.md`、commit `cdd90e945d938769aefa17a2b8de3236647f6bdc`。要件→研究README→本書ブリーフ→第1本v2とreview→第2〜4本とreviewの順に読み、全体を調査した。設計・製品選定・要件追加は行わない。

本書で取得して読んだ外部資料を「本体確認」、第1〜4本の結果を入力にする箇所を「報告」とする。引用のURL、固定SHA、path:line、PDFページとSHA256は [根拠集](05-whole.evidence.md) にまとめた。コードの実行、障害注入、複数実装の接続実験、定理と現行コードの正しさの再証明は行っていない。

## 1. 4つの問いへの回答

1. 交換しても保持する性質を定義した理論はある。Interface Automata for Shared Memory（IAM）のrefinementは、同じsignature、入力のdata-determinism等の前提の下で、互換だった環境との合成が置換後も成立することを保証する。IA-Toolsetには前後条件の含意と遷移の対応を検査する実装がある。ただし保存するのはモデル内の通信互換性であり、PDAの仕事・成果・記憶・可視化・監査の全形、LLMの回答品質、外部ランタイムとモデルの一致ではない。[PIA1–3](05-whole.evidence.md#pia1)、[IA1–5](05-whole.evidence.md#ia1)
2. 非LLMの判定規則を成果から更新する実装はある。Vowpal Wabbit（VW）のcontextual banditは、文脈から選んだactionの観測costを学習し、以後のpolicyを変える。公式simulationにも選択→成果→学習の反復がある。YAWLは、実行中のcaseを根拠に人が規則を追加し、以後のworklet選択を変えられる。一方、両者でA9の「いつ・根拠・変更前後・復元」を一体の必須契約としては確認していない。RouteLLMの固定MF経路は、学習済みscoreとthresholdによる選択であり、その稼働経路に成果からの自動policy更新は確認できない。[VW1–6](05-whole.evidence.md#vw1)、[YW1–9](05-whole.evidence.md#yw1)、[RT1–5](05-whole.evidence.md#rt1)
3. 非決定な処理を記録されるstepへ置き、制御部分の再実行と分ける例はある。DBOS Pythonは、workflowのstep呼出順を決定的に保つことを要求し、記録済みstepの出力または例外を読み戻す。LLMを再度呼んで同じ回答を得る保証ではない。外部呼出が成功してから結果を記録するまでに停止した場合や、まだ記録のないstepでは、外部処理が再実行されうる。[HD1–2](05-whole.evidence.md#hd1)、[DB1–5](05-whole.evidence.md#db1)
4. 参加者を実行時に発見・接続・置換する形式化はある。EnsembleSは同じsession typeに従うactorを発見・置換し、型安全性と条件付きprogressを示す。Open Multiparty Sessionsは互換なsessionをgatewayで結び、lock-freedomを保存する。ただし、既知のroleを担う新instance、未使用だったroleの接続、別protocolとの合成、未定義の新roleの導入は異なる。今回確認した定理から、別アカウント・別環境・別ベンダーを含むPDAのA2全体は導けない。[PEN1–4](05-whole.evidence.md#pen1)、[POP](05-whole.evidence.md#pop)

以上は限定された性質についての回答である。契約4項目、3.1の定義、3.2-1〜5、A1〜A4・A9を一体で満たす抽象・不変量・実装の対は、今回の探索では未発見だった。

## 2. 前4本から引き継ぐ事実と、引き継がない一般化

次の表は報告の利用であり、各要素の再調査ではない。

| 入力 | 本書へ引き継ぐ報告 | 全体へ拡張できない範囲 |
|---|---|---|
| [第1本v2](01-store-and-protocol.v2.md)・[review](01-review.md) | session types/choreography、actor/dataflow、durable workflow、メッセージ規約等に個別の対がある | 同じプロトコルは同一JSON型を意味しない。仕事と成果の型の相違だけで失格にしない。非決定な処理をstepへ分ける含意は、本書で実装経路を追加確認する |
| [第2本](02-self-declaration.md)・[review](02-review.md) | 機械可読宣言、入出力検査、資源配置の拒否、capability/effectの制限がある。費用・資源・stateの語彙も存在する | 宣言の構文、許可操作、実際の到達権限、実請求額、中断後の再開可能性を同じ検査としない。非LLMで動く要素だけではA4全体を満たさない |
| [第3本](03-runtime-wrapper.md)・[review](03-review.md) | ラッパーによる状態遷移、受信時の形式検査、種別変換は実装されている | 未知通知の無視、失敗要素の除去、観測できない内部動作がある。adapterとSDKの版差を越えた組合せ動作は未実証。binary session typeは任意の外部ランタイムの全発話を支配しない |
| [第4本](04-log-store.md)・[review](04-review.md) | schema検査、順序付き履歴、実行中の出力、追記証明には対がある。完全性もPeerReview・SLiC等の前提付き抽象がある | schema登録と個々のpayload検査、観測した履歴と実行器内部の全行為、変更履歴とA9を分ける。型宣言だけをruntime拒否としない |

「event streamの種別検査は必ずストア自身で行う」「費用・資源・stateの語彙はどこにもない」「event完全性には抽象がない」という一般化は採用しない。要件は最終的な共通契約を要求しており、検査を置く位置を本書が追加決定するものではない。proto3のenum/oneofやPythonの型注釈だけから、不正値が実行時に拒否されるとも推論しない。

## 3. 判定の読み方

「満たす」は対象条件の全文を確認した場合、「一部」はその条件を支える性質を確認した場合、「満たさない」は当該対の提供範囲では条件を満たさない場合とする。未確認の機能を製品全体に存在しないと主張する判定ではない。

実行器は要件どおり「環境・アカウント・エージェント」の組である。agent class、モデル名、worklet、banditのaction、protocol roleをそのままこの組と見なさない。平等は単に複数モデルを呼べることではなく、コアが特定のベンダー等に依存しないことまで含む。交換可能性は回答が同じ意味になることではなく、要件に列挙された受渡し・記憶・可視化・監査・追加削除の形に関する条件として評価する。

本書で実装の強制位置まで揃えた対は5件である。EnsembleSとOpen Multiparty Sessionsは抽象側の本体確認であり、同じ表に置く場合も実装の確認状況を明示する。

## 4. 抽象・不変量・実装の対応

| ID・対象 | 抽象と保持する性質 | 不変量の逐語引用の位置 | 実装または検査位置 | 成立の境界 |
|---|---|---|---|---|
| I: IAM / IA-Toolset | 置換前QをrefineするPは、互換な環境Rとの合成可能性とrefinementを保存する | [PIA2–3](05-whole.evidence.md#pia2)、Definition 8 / Corollary 18 | signature不一致の例外、遷移familyのBES生成、前後条件の含意をSMTで検査 [IA1–5] | 与えたモデルの検査。外部プログラムの動作を自動的にモデル化して監視する機構ではない |
| V: contextual bandit / VW | 標準ADF入力の観測ラベルを一つのactionに限定し、文脈・選択確率・costからpolicyを更新する。有限εと非空候補の下でε-greedy分布を作る | [HV2](05-whole.evidence.md#hv2)、ADF仕様 | 複数cost等の形式違反を拒否し、観測costをlearnerへ渡す。εの範囲検査と分布構築 [VW1–3,5–6] | 学習機構と分布構築の対。仕事の意味的成功や任意環境での最適性・収束を保証しない |
| R: binary routing / RouteLLM MF | scoreがthreshold以上ならstrong、それ以外ならweakを選ぶ | [PRT](05-whole.evidence.md#prt)、§3.1の問題定式化 | controllerのthreshold検査とRouter.routeの分岐、MFの推論 [RT1–5] | 有効なscoreを得た呼出しの二者択一。scoreの較正、成果改善、稼働中の自己学習の保証ではない |
| D: durable workflow / DBOS Python | 同じstep結果を与えたworkflowは同じ順序でstepを呼ぶ。記録済み結果を再利用する | [HD1](05-whole.evidence.md#hd1)、Determinism | workflow ID・step位置・関数名の照合、記録済output/errorの読戻し、本体実行を省くinterceptor [DB1–5] | workflowの決定性は利用側の前提。検査があらゆる非決定性を発見するわけではない |
| Y: RDRによる動的worklet選択 / YAWL | caseデータと規則木から最後に成立した規則を選び、その結論のworkletを起動する。規則木を稼働中に増やせる | [PYW1](05-whole.evidence.md#pyw1)、Worklets概説 | 条件評価、cornerstoneによる挿入、規則種別・結論検査、既存worklet取消後の再選択 [YW1–9] | 規則による選択の対。過去全caseへの影響不変や、変更後workflowのsoundnessをここからは保証しない |
| E: EnsembleS（抽象側） | 同一session typeのactorの発見・置換、型安全性、unmatched discoverがない等の前提付きprogress | [PEN1](05-whole.evidence.md#pen1)、§3.4の発見・置換 | 論文の型規則・操作意味論・定理を確認。compiler同梱artifactの存在は確認、コード実体未取得 [PEN2–4] | 実装の強制箇所まで揃った対には数えない。既知protocolの役割型への適合が前提 |
| O: Open Multiparty Sessions（抽象側） | 互換なsessionをgatewayで接続した合成系のlock-freedom | [POP](05-whole.evidence.md#pop)、Abstract / Theorem 6.7 | 論文のgateway変換と合成の定理を確認。対応する固定実装の強制位置は未発見 | 任意の新roleを無条件追加する定理ではない。gatewayへの変換を含む |

### 4.1 I — 交換で保存するのは、モデル化した通信互換性

本体確認。IAMのDefinition 7は入力遷移のdata-determinismを要求し、Definition 8は同じsignature間のalternating simulationを定義する。入力を受けられる範囲と出力の許容範囲を、前後条件と遷移familyで比較する。Corollary 18は、QとRが合成可能でPがQをrefineするとき、PとRも合成可能で、元の合成が定義されれば置換後の合成もrefinementを保つという命題である。[PIA1–3]

`uniba-swt/ia-toolset@076b7343591904d65182bd85d14e54ecdee2cc11` の `swtia/src/main/kotlin/swtia/sys/iam/IamRuntimeProvider.kt:85-99` から、`ialib/src/main/kotlin/ialib/simpleia/refinement/bes/AbstractBesRefinementOperation.kt:45-64` の検査へ入る。I/O集合が違えば例外、式を作れなければfalse、作れればBES solverの結果を返す。`iam/refinement/MemBesFormulaBuilder.kt:63-110` は対応familyがなければfalseを組み込み、`iam/simulation/RefinementFamilyProvider.kt:118-155` は前後条件の含意を調べる。単なる図の表示ではなく、不適合を返す検査処理がある。[IA1–5]

ただし、これはモデルを入力する検査ツールである。ある実行器を交換する実際の入口にこの検査が必ず置かれることや、実行器の全動作が入力モデルに一致することまで確認したものではない。PDAの記憶書込み・可視化・監査の操作をモデルに含めた検証も未実施である。したがってA1は一部であり、通信互換性の保存を「同じ成果品質」へ読み替えない。

### 4.2 V — 非LLMの成果による規則変更は存在する

本体確認。contextual banditのpolicyは文脈からactionを選び、選んだactionのcostを観測して更新する。VWの公式simulationは、文脈を渡してactionと確率を取得し、costを求め、`vw.learn` に戻す反復を実装する。ここには生成LLMを判定器とする前提がない。ただし例のactionはコンテンツ候補であり、PDAの実行器の組を既に登録・操作している実装だとはしない。[HV][VW6]

公式ADF仕様は、一つのexampleに観測ラベルを付けられるactionを一つに限る。標準経路の `test_cb_adf_sequence` は、空列、各行の複数cost、複数行の観測costを拒否する。この形式上の不変量が仕様と実装で対応する。複数costを許す引数付きの別経路を含む全利用法への保証には拡張しない。[HV2][VW3]

`VowpalWabbit/vowpal_wabbit@13eae731a75066220c5e270adb8ca1dd7d9a857e` の `vowpalwabbit/core/src/reductions/cb/cb_adf.cc:58-101,241-268` は入力列を検査し、観測costがあれば学習方式へ分岐する。`cb_explore_adf_greedy.cc:48-82` はactionにε/Nを配り、最良action側に残りを加える。`:150` はεが0未満または1超なら拒否する。この比較だけをNaN等も含む全値の完全検証とはしない。成立させる分布の不変量は、有限のε∈[0,1]、非空候補集合等を前提とする。[VW1–3,5]

`python/vowpalwabbit/pyvw.py:794-804` にmodel保存があり、公式資料は保存済みmodelの読込みを示す。したがって保存した旧policyを再利用する手段はある。しかし、学習呼出ごとに理由・時刻・旧model・新modelを必須で一組に記録する処理ではない。成果をcostへ変換する責任、どのmodelをいつ実行へ適用したか、変更を取り消した際の外部処理への影響も、この機構の外側である。A9は一部に留まる。[VW4][HV]

### 4.3 R — 学習したrouterと、稼働中に自己改変するrouterは異なる

本体確認。RouteLLM論文§3は選好データからscoreを学習し、thresholdによって二つのモデル群を選ぶ関数を定義する。`lm-sys/RouteLLM@0b64fdafe049e596a3f5657c219329f24af24198` の `routellm/controller.py:79-91` はrouter未指定と不正thresholdを拒否し、`routellm/routers/routers.py:41-45` が二者択一を実行する。これが確認した不変量である。[PRT][RT1–2]

MF経路は保存済みmodelを `eval()` へ切り替えてscoreを計算する。`routellm/routers/matrix_factorization/model.py:88,113-115` は `text-embedding-3-small` と `OPENAI_CLIENT.embeddings.create` に依存する。判定が生成LLMの自由文でないことと、特定provider/modelに依存しないことは異なる。routing先モデル対の変更可能性から、3.1の平等全体を認定しない。[RT3,5]

`controller.py:105-119` がrouting用に切り出すのは最後のmessageのcontentであり、実行先へ渡すmessages全体を仕事に必要な範囲へ絞る処理とは違う。この経路の切出しを3.2-2の達成とは数えない。調べたcontrollerとMF推論経路には、返答成果を受けてpolicyを書き換え、変更前後と理由を記録して取り消す経路は確認できなかった。論文の品質・費用の実験結果は、すべての仕事での改善不変量ではない。[RT3–5][PRT]

### 4.4 D — 再生するのは記録された結果、再生成するのは未記録の処理

本体確認。DBOS Pythonの公式Workflows資料は、同じ入力と同じstep結果に対してstep呼出が同じ入力・同じ順序になることを要求する。非決定なAPI呼出等はstepへ置く。保証にはプロセスとDBが復帰する前提があり、通常stepの試行とtransactionのcommitも区別されている。[HD1–2]

`dbos-inc/dbos-transact-py@a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59` の `dbos/_sys_db.py:3153-3216` はworkflow IDとfunction IDで記録を引き、同じ位置の関数名が違えば `DBOSUnexpectedStepError` にする。`dbos/_core.py:2297-2330` は記録済みoutputをdeserializeして返し、記録済みerrorを再送出する。`dbos/_outcome.py:142-162` のinterceptorは記録がない場合だけ本体を呼ぶ。[DB1,3,5]

この検査は全入力値の一致や任意の非決定分岐を証明する検査ではない。確認した照合では、同じ位置・同じ関数名でも実引数を比較しない。workflowの決定性という使用条件は残る。また `run_step` はworkflow外では通常関数として動くので、同じ関数を呼んだだけでは履歴再生にならない。[DB3–4]

`_core.py:2265-2295` の順序は本体実行→serialize→記録である。LLM APIの応答が得られた後、記録前に停止すれば、復旧時には記録が見つからず再呼出しになりうる。記録済みなら以前の回答を再利用し、未記録なら新しい回答になりうる。この二つを「LLMを決定的にした」とまとめない。内部のtool callや途中判断まで記録したことにもならず、live event streamの完全性は第4本の留保を引き継ぐ。[DB1–5]

CIDR論文のAC/DCはstepをtransactionとする前提を置く。そこで述べる完了stepの一度限りの扱いを、通常Python stepの外部API副作用まで一度限りとする根拠には用いない。別に取得した `dbos-vercel-ai` はTypeScript側の実装なので、本書のPython経路の保証をそのまま移していない。[PDB1–2]

### 4.5 Y — 規則を増やすこと、soundnessを保つこと、変更を戻すこと

本体確認。YAWLのworkletは実行中に選ぶ独立したsubprocessであり、元のprocess仕様を変更せずに候補と規則を増やせる。規則作成時のcaseデータをcornerstoneとして持ち、ユーザーの不適切な選択への指摘を新しい規則へ反映する仕組みである。自動で成果を数値学習するVWとは更新主体が異なる。[PYW1–2]

`yawlfoundation/yawl@f007a2d0f345dcce6ee702a76a32b48ceaf31f5f` の `src/org/yawlfoundation/yawl/worklet/rdr/RdrNode.java:268-299` はcaseデータで条件を評価し、成立/不成立の枝をたどり、最後に成立したnodeを返す。条件評価例外はlogへ出してnullを返す場合がある。`rdr/Rdr.java:204-241` はcornerstoneで親を探し、親と同じ内容のnodeを拒否して木へ追加する。`support/WorkletGateway.java:292-320` はrule type、空結論、参照worklet等を検査する。[YW1–3]

`WorkletService.java:388-420,448-494` は規則の結論からworkletを起動し、rule node IDと親workitemを対応付け、終了後に成果を戻す。`:650-679` の置換は、稼働中workletの取消し→規則再評価→新worklet起動である。変更前の全体状態へ原子的に戻す処理ではない。元workletを取消した後に次の規則が見つからず失敗する経路もある。[YW4–5,9]

A9に関連するものとして、実行eventには時刻があり、選択rule IDも保持される。しかしevent永続化は設定条件付きで、規則の説明欄は任意である。規則削除は子nodeを再接ぎ木する処理であり、旧規則木snapshotの復元と同じではない。確認した追加・選択・取消し経路は、変更根拠と変更前後を必須記録する一体の監査台帳を提供していない。[YW6–8][PYW2]

YAWL Editorにはsoundness解析があるが、公式資料は有限状態空間と探索上限を明記する。これとgatewayの結論検査は別であり、実行時の全規則追加に変更後workflow全体のsoundness検証が必ず掛かるという経路は確認できない。さらにRDRの親への例外追加から、過去すべてのcaseの選択結果が不変だとも推論しない。[PYW3][YW2–3]

### 4.6 E・O — 動的参加の形式化とA2の間

本体確認。EnsembleSは、actorが同じinterfaceとsession typeを持つ場合の発見・置換を扱う。論文§3.4では置換はactorのbehaviour loopの先頭で起き、§3.5ではsession typeをruntimeにも保持すると説明する。一方、定理が扱うwell-formed programではactorの型は定義済みprotocolのroleの型に一致し、protocol同士のrole集合は分離されている。新しいinstanceを発見することは、protocolに存在しなかった任意の新roleをそのまま追加することではない。[PEN1–2]

Theorem 10は安全な型環境の下で型を保存する。Theorem 18のprogressには、program自身のprogress条件とunmatched discoverがないこと等が必要である。登録されていない相手を無限に探しても進むという保証ではない。PDAの環境・アカウントの識別、権限実態、記憶と可視化までがその型に含まれているとする根拠もない。artifactのcompilerの所在は確認できたが、6.33 GiBのVM内コードを取得・検査していないため、理論と現行実装が揃った対とは認定しない。[PEN2–4]

Open Multiparty Sessionsは、別々に型付けされたsessionの互換なprocessをgatewayへ変換して接続し、global typeを合成する。その条件下のlock-freedom保存は確認できる。しかしgateway変換を含む合成は「コアと既存実行器を一切変更せず、新しい実行器を追加する」ことと自動的には同じにならない。対応実装の固定code位置は今回未発見である。[POP]

既知roleの新instanceであってもPDA上は別アカウント・別環境の実行器になりうるため、静的roleという理由だけでA2不適合ともしない。結論は、これらの形式化によりA2の通信互換性部分を扱えるが、要件の組全体について追加無変更を保証した対は未確認、という範囲に留まる。

## 5. 要件への判定表

I/V/R/D/Yは4節の実装まで確認した対、E/Oは抽象側だけを確認した対象である。E/Oの「一部」は理論の射程との対応であり、実装での達成確認ではない。

| 対象 | 能力の宣言 | 仕事の受け取り | 成果の返却 | event stream | 3.1 実行器の組 | 3.1 平等 | 3.1 交換可能 |
|---|---|---|---|---|---|---|---|
| I IAM | 一部 | 一部 | 一部 | 満たさない | 満たさない | 一部 | 一部 |
| V VW | 一部 | 一部 | 一部 | 満たさない | 満たさない | 一部 | 一部 |
| R RouteLLM MF | 一部 | 一部 | 一部 | 満たさない | 満たさない | 満たさない | 一部 |
| D DBOS Python | 一部 | 一部 | 一部 | 一部 | 満たさない | 一部 | 一部 |
| Y YAWL worklet | 一部 | 一部 | 一部 | 一部 | 満たさない | 一部 | 一部 |
| E EnsembleS（抽象側） | 一部 | 一部 | 一部 | 満たさない | 満たさない | 一部 | 一部 |
| O Open Multiparty Sessions（抽象側） | 一部 | 一部 | 一部 | 満たさない | 満たさない | 一部 | 一部 |

能力欄の一部は、I/E/OのI/Oと状態、Vのaction特徴、Rのモデル対とscore、Dのstep再実行規則、Yのworklet I/O等に限る。契約の費用・資源・中断後stateを一体で公開したという意味ではない。成果欄も、通信型・action番号・関数結果・worklet出力などの一部を受け渡せる範囲に限り、共通protocolのまま任意実行器へ注入できることまで確認していない。D/Yのevent欄は内部で観測した履歴・実行eventに限る。[IA1–5][VW1–6][RT1–5][DB1–5][YW1–9][PEN1–3][POP]

| 対象 | 3.2-1 割り振り | 3.2-2 文脈絞込み | 3.2-3 多層統合 | 3.2-4 メッシュ | 3.2-5 自己改変 | その判定を制限する具体点 |
|---|---|---|---|---|---|---|
| I IAM | 満たさない | 満たさない | 満たさない | 一部 | 満たさない | 合成の互換性検査はあるが、仕事を判定する実行器や成果による規則変更はない |
| V VW | 一部 | 一部 | 満たさない | 満たさない | 一部 | 成果によるpolicy更新はある。文脈は特徴入力であり、必要最小範囲の強制ではない。判定器自身のPDA契約とworkflow変更履歴は未対応 |
| R RouteLLM MF | 一部 | 満たさない | 満たさない | 満たさない | 満たさない | 選択は実装されるが固定推論経路。最後のmessageをrouterへ渡すことは実行先への履歴制限ではない |
| D DBOS Python | 満たさない | 一部 | 一部 | 一部 | 満たさない | step引数、子workflow、順序付き呼出しは土台。仕事別の最小文脈、監査/再確認、成果からの規則更新と復元をこの経路は規定しない |
| Y YAWL worklet | 一部 | 一部 | 一部 | 一部 | 一部 | caseに基づく規則変更と動的subprocessはある。PDAの監査を含む可変段数統合、相互監査、A9全体は未確認 |
| E EnsembleS（抽象側） | 一部 | 一部 | 満たさない | 一部 | 一部 | propertiesと型によるdiscover/replace。成果由来のpolicy変更・変更記録・取消しは定理の対象外 |
| O Open Multiparty Sessions（抽象側） | 満たさない | 一部 | 満たさない | 一部 | 一部 | 互換sessionの合成とgateway化まで。文脈最小化や成果による変更記録を扱わない |

DBOSの子workflow等は公式Workflows資料の範囲で確認した性質であり、全体のメッシュ監査実装を実行確認したものではない。[HD1] 多層統合についてはMoAにも前層成果を次層へ渡す抽象があるが、監査・再確認・仕事ごとの段数変更を含む3.2-3全体の対は今回確認できていない。[PMO]

| 対象 | A1 | A2 | A3 | A4 | A9 | 足りない確認 |
|---|---|---|---|---|---|---|
| I IAM | 一部 | 一部 | 満たさない | 一部 | 満たさない | モデルの適合を実行器全体へ結び、5種類の形とaccount/environmentの追加へ拡張する対応 |
| V VW | 一部 | 一部 | 満たさない | 一部 | 一部 | ADFの候補追加は実行器の追加契約ではない。判定器交換と変更監査の必須経路 |
| R RouteLLM MF | 一部 | 一部 | 満たさない | 一部 | 満たさない | routing先の差替えと、MFの固定embedding依存解消・実行器契約・自己更新は別 |
| D DBOS Python | 一部 | 一部 | 満たさない | 一部 | 満たさない | 同じstep規則の新関数と、任意vendor/account/environmentの無変更追加は別。履歴replayはpolicy rollbackではない |
| Y YAWL worklet | 一部 | 一部 | 満たさない | 一部 | 一部 | worklet追加と実行器の組の追加は別。取消し・再選択は規則の完全な変更台帳/復元ではない |
| E EnsembleS（抽象側） | 一部 | 一部 | 満たさない | 一部 | 満たさない | 同一session typeの新instanceとの通信安全性より広いPDA全契約の保持 |
| O Open Multiparty Sessions（抽象側） | 一部 | 一部 | 満たさない | 一部 | 満たさない | gateway化を要する合成から、既存実行器の無変更と共通操作までは導けない |

A4の「一部」は、確認した制御・検査を特定の生成LLMなしで記述・実行できる範囲を指す。判定用実行器の差替え後もPDAコアが継続動作する確認を含まない。どの行もA3の会社契約と個人契約を同じ一覧・同じ操作で扱うところまでを提供していない。

## 6. 指定起点の探索結果

「片側」は抽象または実装の資料を確認したが、同じ性質を強制する位置まで対を閉じていないことを意味する。「未発見」は記載した検索・取得資料の範囲に限る。HTTP失敗、所在だけ確認した未取得、取得したがコードを追っていない場合を分ける。

| 起点・検索語 | 確認した一次資料 | 到達点と未確認部分 |
|---|---|---|
| Gaia / Wooldridge Jennings roles agents / AUML roles | Gaia原論文pp.2,4、roleとagentの分離 [PGA] | 抽象側。Gaiaは組織と能力のruntime不変を適用範囲に置く一方、roleと個人は一対一ではない。役割概念だけで追加無変更は導けない。AUMLを含む探索で本書の全契約を強制する固定実装は未発見 |
| Hearsay-II / BB1 control blackboard scheduler | Johnson・Hayes-RothのBB1論文p.1 [PBB] | 抽象側。control KSがcontrol planを書き、schedulerがそれを使う。実装/実験の報告はあるが、PROTEAN等の固定コードで制御更新とA9を確認するところは未完。blackboard一般を「仕様が全くない」と扱わない |
| HTN / SHOP / CaMeL / market-based allocation / contract net | SHOP公式研究ページ、CaMeL、task-allocation論文 [HS][PHT][PAL]。contract netは第2本の報告 | HTNのmethod学習やallocationの定式化は存在する。宣言済み作用のplan正しさと、外部実行器の成果・監査契約は別。各planner/auction実装の強制位置との対は本書では未確認 |
| metareasoning / Russell Wefald / anytime / Dean Boddy | metareasoning導入の取得断片、anytime原論文 [PMR][PAT] | 抽象側。計算時間等を含むutilityで推論を選ぶ。計算資源の配分とPDA契約は別。完全なメタ推論実装とA9の対は未発見。metareasoning PDFは1頁のみで、論文全体を読んだとは扱わない |
| MAPE-K / models@run.time / Rainbow invariants | Rainbow原論文の監視modelとconstraint違反による適応 [PRB] | 抽象側。モデルの不変量を明示できるが、観測モデルと実システムの対応は前提。適応の図式だけでは新構成の安全性が自動強制される根拠にならない。固定runtimeの検査経路は未確認 |
| AIOS / FIFO / Round Robin | AIOS論文§3.2–3.4 [PAI] | schedulerとLLM coreを分離し、text/logits別の中断処理を説明。元論文の実装例を確認したが、固定実装の強制位置との対は未完成。PDAのaccount単位やA9はそこから導けない |
| FrugalGPT / RouteLLM / cascade | FrugalGPTの費用制約、RouteLLMの閾値関数と固定コード [PFG][PRT][RT1–5] | RouteLLMの限定した対は成立。FrugalGPTの期待費用制約は各実行の費用上限ではない。FrugalGPT実装の制約強制は未照合 |
| mixture-of-agents / previous layer / integration | MoA原論文 [PMO] | 多層の抽象側。ベンチマーク上の改善と、各層で品質が単調増加する不変量を同一視しない。PDA契約下の監査/再確認/可変段数の対は未発見 |
| interoperability survey formal invariants | Beyond Message Passing v3、§3の3層区分とschema/invariantsへの言及 [PSV] | 第1本とは別のsurveyに不変量という語彙は見つかった。ただし構文/意味の枠組みと提案であり、全18protocolのruntime適合定理や実装検証ではない。A12へ意味理解要件を追加しない |
| adaptive workflow / YAWL worklets / ripple-down rules | YAWL公式manualと固定source [PYW1–3][YW1–9] | 選択と規則追加の対は成立。全runtime改変のsoundness・A9との対は未完 |
| dynamic participants / explicit connections / safe runtime adaptation / open sessions | EnsembleS、Open Multiparty Sessions [PEN1–4][POP] | 抽象側を確認。EnsembleS artifactは所在・規模確認、実体未取得。Open Sessionsの対応実装の強制位置は未発見 |

取得できなかった実装と未取得資料は、[根拠集の取得状態](05-whole.evidence.md#acquisition) に分離した。証拠に採用した資料のHTTP失敗はなく、EnsembleSのVM本体は要求を送っていない未取得である。対応実装の未発見とHTTP失敗を同じ理由にはしない。探索で取得したが主たる対に採用しなかった資料、取得状態、検索語も根拠集に残した。実装の成功について、抽象の採用が成功を生んだという因果までは立証していない。ここで確認したのは、主張された性質と、その性質を検査・構築するコードの対応である。

## 7. 5本を通した、未対応の抽象・実装の集約

この表の「未対応」は今回の5本の範囲で対応する根拠が揃っていないことを示す。既存抽象が一切ない、世界に実装がない、または必ず自作する必要があるという意味ではない。前4本に関する行は報告、本書の行は上記の本体確認を基にする。

| 範囲 | 確認済みの抽象側 | 確認済みの実装側 | 残る対応関係・未発見部分 | 根拠 |
|---|---|---|---|---|
| blackboardで制御知識を変える | BB1のcontrol planとscheduler | 論文に実装例の報告。固定コード未照合 | 抽象側のみ。制御規則更新からその根拠・変更前後・復元までの実装 | 第1本の報告、本書[PBB] |
| ラッパーによるprotocol整合 | session types、adapter synthesis、Wrapper Facade | ACP等の実adapter、SDKの検査/変換。adapter synthesisの対応sourceは取得失敗の報告 | 抽象側だけの合成手法と、実装側だけで追った変換処理の対応。外部ランタイムの未観測発話まで閉じた契約の実装 | 第3本・reviewの報告 |
| 動的なparticipant追加・置換 | EnsembleS、Open Multiparty Sessions、IAMの合成/refinement | IAM model checker。EnsembleSはartifact所在のみ | 動的発見の定理と本体実装の強制位置。さらに環境・account・agentの組へ結ぶA2全体 | 本書I/E/O |
| 能力宣言と実態 | FIPA/MCP等の宣言、費用・資源・state語彙、capability/effect/前後条件 | schema検査、配置拒否、権限制限の部分機構 | 抽象も実装も部分的にはある。PDAの全宣言項目と各実行器の実態を一体で照合する対は未発見 | 第2本・reviewの報告 |
| 成果をそのまま別実行器へ渡す | 型付きメッセージ、session/入出力契約 | 個別protocolの受信検査とadapter変換 | 同一protocolの異なる型は許される。種別分類と再注入が全実行器の実経路で保たれる対応は未確認 | 第1〜3本の報告、本書の解釈留保 |
| event完全性と監査可能性 | PeerReview・SLiC等の前提付き完全性、CTの提出済み記録 | 実行中event出力、journal、schema検査、追記証明 | 完全性の抽象側に対する固定実装未照合部分がある。adapter実装が観測したeventと任意の内部行為全件を結ぶ抽象/強制は未確認 | 第3〜4本・reviewの報告 |
| 非決定処理を含むreplay | durable workflowのstep分割と決定的制御 | DBOSの結果再利用と名前不一致拒否。Temporal/Restateは第4本報告 | 対は部分的に成立。任意の非決定性の検出、未記録外部呼出の一度限り、LLM回答の再生成同一性には拡張できない | 第1・4本の報告、本書D |
| 成果による割り振り規則の変更 | contextual bandit、routing、RDR | VWの学習、RouteLLMの選択、YAWLの規則追加 | 個別の対は存在する。判定器自身もPDA実行器契約に従い、差替え可能である全体の対応は未確認 | 本書V/R/Y |
| 可変段数の統合とメッシュ監査 | MoAの多層推論、workflow/合成理論 | worklet選択・復帰、workflow再実行の部分機構 | 共通契約上で統合→監査→再確認を行い、相互参照/エスカレーションする全体の対は未発見。層の図や関数呼出だけで監査機構と数えない | 第1本の報告、本書[PMO]・D/Y |
| A9の自己改変の記録と取消し | policy更新、動的規則、変更履歴 | VW model保存、YAWL規則編集/実行event、Git commit/revert | 双方に部分機構はある。いつ・根拠・変更前後・元への復元を一体にした対は未発見。Gitの履歴だけで適用時刻や外部効果の取消しは保証しない | 第4本の報告、本書V/Y |
| 全契約を保つ実行器の交換 | IAM等の限定された置換理論と第1〜4本の個別抽象 | 部分機構は多数確認 | A1〜A4を満たす同じ全体実装との対応、特に会社/個人を別実行器として同じ一覧・操作で扱うA3は未確認 | 第1〜5本 |

既存の対を組み合わせれば自動的に全体の保証が合成されるとは判定しない。同時に、未発見という調査結果を、不可能性や新規実装の必須性へ変換しない。
