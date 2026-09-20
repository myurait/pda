# 第2本 — MCP 的な自己宣言

作成・一次資料取得日: 2026-09-20 JST。物差しは `docs/requirements.md`、対象ファイルの最終変更 commit は `cdd90e945d938769aefa17a2b8de3236647f6bdc`（`git log -1 --format=%H -- docs/requirements.md` で確認）。設計・製品選定ではなく、能力の宣言とその検査についての調査記録である。

本文の一次資料は担当調査者が取得して確認した「本体確認」。分担先の未再取得の報告を根拠にした箇所はない。親による独立照合は `02-review.md` の範囲と区別する。根拠集は `02-self-declaration.evidence.md`。以下の資料IDは同根拠集の逐語引用・固定版・行番号を指す。

## 1. 結論

1. 能力を機械可読に公開し、その宣言の一部を検査・強制する対はある。MCP と TypeScript SDK は宣言した入出力スキーマ、A2A と Python SDK は宣言した通信機能、Kubernetes と Nix は配置条件・資源制約、Pony と CHERI は到達権限、OpenAPI と openapi-core、契約による設計と icontract、Koka の effect 型は対応する型・述語を検査する。ただし検査する対象が違い、いずれも単独で要件の能力の宣言の全項目と実態の一致を保証しない。
2. 費用の語彙は既存にある。SLA4OAI の `cost`・`currency`・`billing` と `rates`・`quotas`、OpenSLO の指標・閾値・目標・時間窓を確認した。これは「費用を機械可読に表す語彙がどの抽象にも実装にもない」という広い結論を支持しない。一方、今回確認した料金モデル検査は宣言の構文・宣言同士の比較であり、実際の請求金額や実行時間との不一致を計測するものではない。1回の仕事に対する金額・時間・レート上限の全てを実行器の環境・アカウントと結び付けた宣言・検査の対は未発見である。[S1–S7](02-self-declaration.evidence.md#s1)
3. 到達できる資源については、宣言と強制の双方が存在する。Pony の権限オブジェクト、CHERI のメモリ境界・権限、Nix の必要な特徴と sandbox が具体例である。ただし、メモリ権限、OS資源、HTTPエンドポイントへ接続する側の認証、実行器が外部コネクタに対して持つ権限は同じものではない。A2A の `security_requirements`、OpenAPI の security、MCP の roots を、開発PCのコネクタ権限の実態証明とは認定しない。A11全体を満たす対は未発見である。
4. 取れる state に関係する語彙はある。MCP の追加入力待ちと `requestState`、Tasks 拡張の状態・クライアント再起動後の照会再開、Kubernetes の `restartPolicy` を確認した。これらと「実行器の内部処理を中断位置から再開できる／仕事を再投入するしかない」という能力の宣言は別である。後者を実行器ごとに宣言し、実装への適合まで検査する対は未発見である。1978年の contract net コードにも `RESUME!TASK` は存在するが、シミュレータの継続処理であり、そのまま後者の証拠にはならない。[M8–M10](02-self-declaration.evidence.md#m8)、[K7](02-self-declaration.evidence.md#k7)、[C2](02-self-declaration.evidence.md#c2)
5. MCP の自己宣言とランタイム間のプロトコルは分けて評価する。`tools/list` と入力・出力の宣言は自己宣言に直接対応する。`tools/call` と結果も機械可読な要求・応答なので、「clientがserverのtoolを呼ぶ向き」だけで仕事の受け取りに使えないとは言えない。しかし、固定したSDKの検査はtool呼び出し境界に限られ、環境・アカウント・エージェントの単位、共通の input/output ストア、全ての内部の出来事を外へ出す event stream までは提供しない。自己宣言の部分適合から契約全体の成立を導かない。

## 2. 判定の範囲

「満たす」は該当する契約項目・受け入れ条件の全体への対応を確認した判定、「一部」はその構成要素への対応を確認した判定とする。「満たさない」は取得した機構だけでは該当条件を提供しない意味であり、拡張不能という意味ではない。

1. 宣言文書がスキーマに適合する検査、仕事や成果の値が宣言に適合する検査、宣言された権限を越える操作の拒否、外部観測で能力の申告と実態を比較する検査を区別する。前のものを実施しただけで後のものを実施したとは扱わない。
2. 能力の宣言は、得意・不得意、費用、到達できる資源、入力・出力の種類、取れる state の全てが対象である。自由な拡張欄や説明文に書けることと、共通に解釈できる既存の語彙を持つことを分ける。
3. A4は、特定のLLMを前提にしないことと、判定用実行器を差し替えてもコアが動くことの両方を対象にする。各対の宣言の解析・検査・配置判断が特定のLLMなしに動作することは確認したが、判定用実行器の差し替え後のコア動作は確認していないため、全10対を「一部」とする。A2は、同じ既存インタフェースの対象を登録・追加できても、要件の実行器全体を変更なしに追加できることが示されなければ「一部」とする。
4. 本文の「型の検査」は成果の種別・形式の検査である。自由文の意味内容の分類は対象にしない。要件は仕事と成果の同一型を要求していないため、要求型と応答型が違うことだけでは契約違反としない。

## 3. 抽象・不変量・実装が揃う対

実装のcommitは7節に全長で固定した。表中の実装名はその版を指す。逐語の不変量と検査経路は各対の下に示す。

| 抽象 | 不変量・検査範囲 | 実装（強制箇所） | 契約との対応 | A2 / A4 / A11 | 足りないもの |
|---|---|---|---|---|---|
| FIPA Agent Management の DF 検索 | テンプレートと登録項目の照合。申告の真実性ではない | JADE `src/jade/domain/DFMemKB.java:152–190` | 能力の宣言の登録・探索は一部 | 一部 / 一部 / 満たさない | 費用・到達権限・再開能力の共通語彙と実態検査 |
| MCP tool schema | 指定された出力スキーマに正常な構造化結果が適合する | TypeScript SDK `packages/server/src/server/mcp.ts:272–274,321–373` | 能力の宣言と入出力形式は一部 | 一部 / 一部 / 満たさない | 注釈の真実性、費用、コネクタ権限、全event stream |
| A2A AgentCard | streamingを宣言しないと対応操作を拒否する | a2a-python `default_request_handler.py:432–454` → `request_handler.py:366–377` | 能力の宣言と対応操作の関係は一部 | 一部 / 一部 / 満たさない | skill説明の真実性、費用、到達資源の検査 |
| OpenAPI 3.1 のスキーマ | 宣言に渡された実値を検査し、違反を例外として返す | openapi-core `validation/schemas/validators.py:43–48`、request/response validator | 能力の宣言と仕事・成果の形式は一部 | 一部 / 一部 / 満たさない | 実行器の外部操作・課金・再開の検査 |
| Kubernetes requests/limits・配置条件 | 資源不足や必須node条件の不一致を配置候補から除外する | `fit.go:674–688,736–754`、`node_affinity.go:230–232` | 資源と環境に関する宣言は一部 | 一部 / 一部 / 一部 | nodeのラベルと実際のコネクタ権限の一致 |
| Nix derivation とビルド機械 | 必要な特徴を持つ機械だけを候補にし、条件付きで外部通信を隔離する | `machines.cc:45–57`、`build-remote.cc:169–170`、`linux-derivation-builder.cc:574–581` | 到達資源と必要環境は一部 | 一部 / 一部 / 一部 | 特徴文字列の真実性、外部契約・料金・実行器state |
| Pony object-capability と型付き引数 | 必要な権限オブジェクトを渡せない呼び出しを拒否する | `file_auth.pony:5`、`net/auth.pony:25–31`、`expr/call.c:430–460` | 到達資源を表す能力の宣言は一部 | 一部 / 一部 / 一部 | 変更できない他ランタイムへの適用、外部コネクタ割り振り |
| CHERI ISA のcapability | メモリ参照に有効なtag・権限・境界を要求する | CHERI QEMU `target/cheri-common/cheri-helper-utils.h:98–154` | メモリ資源の権限は一部 | 満たさない / 一部 / 一部 | HTTP・ファイル・コネクタ権限への対応、実行器の一覧 |
| 型付き effect system（Koka） | 関数のeffectを型に反映し、effectの整合を型検査する | `src/Type/Infer.hs:1354–1357`、`src/Type/Unify.hs:374–399` | 可能な操作種類と入出力型は一部 | 一部 / 一部 / 一部 | 特定資源の権限一覧、外部ランタイムと宣言の適合証明 |
| 契約による設計 | 有効化された前条件・後条件に違反すると例外を返す | icontract `icontract/_checkers.py:817–845` | 観測できる入力・結果の述語は一部 | 一部 / 一部 / 満たさない | 任意実行器の内部操作・外部権限を検査する述語 |

### FIPA directory facilitator と JADE

本体確認。FIPA SC00023J §7.1 は、テンプレートの各パラメータを登録項目と照合する規則を定める。JADEは登録された各serviceを走査し、テンプレートのserviceに対応するものがなければ偽を返す。service名・type等はJava側で比較する。宣言が登録され、機械的に探索される経路は実装されている。[F2](02-self-declaration.evidence.md#f2)、[F1](02-self-declaration.evidence.md#f1)

同仕様 §4.1.1 は、DFが登録情報の正しさ・正確さを保証できないと明記する。したがって、検索が成功したことはそのエージェントの費用・権限・能力が実際に使える証拠ではない。JADEの取得元は非公式ミラーであり、これを現行の公式配布物全体の検証結果とは扱わない。[F0](02-self-declaration.evidence.md#f0)

### MCP と TypeScript SDK

本体確認。2025-11-25、2026-07-28両版のtools仕様に、outputSchema指定時の “Servers MUST provide structured results that conform to this schema.” がある。SDKの高水準 `McpServer` は登録済みtoolから宣言を作り、呼び出しで入力検査→handler→出力検査を通る。成功した正常結果の `structuredContent` を宣言スキーマで検査する。[M1](02-self-declaration.evidence.md#m1)、[M6](02-self-declaration.evidence.md#m6)、[M4–M5](02-self-declaration.evidence.md#m4)、[M13](02-self-declaration.evidence.md#m13)

強制の範囲は限定される。入力スキーマ未設定なら引数を検査せず `undefined` を返す。出力スキーマ未設定、追加入力待ち、`isError` の結果では出力スキーマ検査を行わない。通常の検査エラーは `tools/call` のcatchで `isError: true` のtool結果へ変換されるため、常にJSON-RPCエラーが外に出るとは言わない。任意の低水準handlerを含む全SDK利用法の適合までは証明しない。[M4–M5](02-self-declaration.evidence.md#m4)

Toolの `readOnlyHint`、`destructiveHint`、`idempotentHint`、`openWorldHint` は注釈であり、スキーマ自身がその全属性をヒントと位置付ける。`inputSchema`を検査しても「readOnlyと宣言したtoolがファイルを書かなかった」ことは分からない。`openWorldHint`も到達可能なURL、パス、コネクタ権限の列挙ではない。[M2–M3](02-self-declaration.evidence.md#m2)

版の注意として、取得したSDKの公開 `LATEST_PROTOCOL_VERSION` は `2025-11-25` のままで、同じソースには2026版の処理も存在する。本対は両版に共通のtool入出力制約に限定し、SDK全体が2026版に準拠すると認定していない。2026版のstateは4節で仕様として別に扱う。[M7](02-self-declaration.evidence.md#m7)

### A2A AgentCard と Python SDK

本体確認。A2A仕様は `AgentCard.capabilities.streaming` が偽または未指定なら、streaming操作とtask購読操作に `UnsupportedOperationError` を要求する。Pythonの既定handlerはAgentCardを参照するdecoratorを持ち、偽ならhandler実行前に例外を返す。protobufのフィールド型から強制を推定したのではなく、この実行経路を確認した。[A1](02-self-declaration.evidence.md#a1)、[A3–A5](02-self-declaration.evidence.md#a3)

このゲートは「宣言していない操作を受け付けない」を守る。「streaming=trueなら必ず正しく継続できる」「skillの説明どおりの能力がある」は守らない。Cardはskills、入出力メディア型、通信機能、エンドポイントを利用する側のsecurity requirementsを持つが、実行器から外部コネクタへの到達権限そのものではない。固定版 `specification/a2a.proto` 全812行を `cost|price|pricing|budget|quota|rate.?limit` で検索した一致は0件だった。対象はこのファイルであり、将来の拡張を含む全A2Aエコシステムに不在とする主張ではない。[A2](02-self-declaration.evidence.md#a2)

### OpenAPI と openapi-core

本体確認。OpenAPIの `oneOf` は複数の定義のうち正確に一つへの適合を要求する。openapi-coreは宣言文書の検査とは別に、requestとresponseの値をschema validatorへ渡し、適合エラーを `InvalidSchemaValue` 等として上位に返す。スキーマを置いただけの状態と、値の検査を通る状態を区別できる具体例である。[O1–O5](02-self-declaration.evidence.md#o1)

成立するのは当該validatorを通したデータの形式への準拠である。全HTTP通信が自動的にこの経路を通るわけではなく、外部副作用・金額・権限・再開の真実性はJSON Schemaの形式検査からは得られない。要求と応答が異なる型であること自体はPDAの契約違反としない。

### Kubernetes と Nix

本体確認。Kubernetesの仕様は資源容量の検査に失敗するnodeへの配置を拒むとする。実装はPod要求量とnodeのallocatable・既要求量を比較し、不足なら `Unschedulable` を返す。CPU/メモリの上限はkubeletがLinuxランタイムへの要求に設定する。ここで確認したのは配置拒否とランタイムへの設定までであり、実機カーネルでの上限超過試験はしていない。requestsは配置用の要求量であり、金銭費用や各仕事の完了時間を保証しない。[K1–K4](02-self-declaration.evidence.md#k1)

必須node affinityの不一致も配置を拒否する。`securityContext.capabilities` のadd/dropはLinuxランタイムに伝達される。しかしnodeのラベルが「コネクタ使用可」であることと、期限切れやアカウントの違いを含むコネクタ権限の実態は別である。Linux capability名もSaaSのOAuth scopeではない。このためA11は一部に留まる。[K5–K6](02-self-declaration.evidence.md#k5)

Nixの `requiredSystemFeatures` は、必要な特徴を持つ機械以外を使わないという仕様を持つ。`Machine::allSupported` は全ての必要特徴を検査し、remote buildの候補選択がその結果を使う。一方、特徴自体は利用者が定義する文字列であるため、文字列の一致はコネクタ権限の実測ではない。[N1–N3](02-self-declaration.evidence.md#n1)、[N6](02-self-declaration.evidence.md#n6)

Linux builderはsandbox対象のderivationに `CLONE_NEWNET` を設定する。固定出力derivationには外部通信を許す例外があり、全Nix実行で通信が閉じられるとは言えない。これは要求資源を記述して配置する機構と、到達可能な資源を実際に制限する機構が別の位置に存在する例である。[N4–N5](02-self-declaration.evidence.md#n4)

### Pony、CHERI、Koka

本体確認。Ponyのobject-capabilityでは権限オブジェクトを受け取ることがアクセスの条件になる。`FileAuth` は `AmbientAuth` を要求し、限定された `TCPConnectAuth` はファイル権限の代わりにならない。compilerの引数型適合検査が誤った権限型を拒否する。`AmbientAuth` の生成子は非公開である。[P1](02-self-declaration.evidence.md#p1)、[P3–P6](02-self-declaration.evidence.md#p3)

Ponyの参照能力は、同じ対象へのalias・読み書き・共有の扱いを型に表すものであり、ファイルやネットワークへの到達権限をそのまま列挙するものではない。後者にはobject-capabilityを用いる。[P8](02-self-declaration.evidence.md#p8) FFIは信頼境界を越え、FilePathの相対パス制限もsymlinkを解決しないと実装文書が明記する。したがって「Pony型があるので外部資源すべてがOSレベルで閉じる」とは認定しない。[P2](02-self-declaration.evidence.md#p2)、[P7](02-self-declaration.evidence.md#p7)

CHERI ISAv9 §2.3.2は、メモリ参照をcapabilityの上下限に制限し、範囲外の参照を例外にする。CHERI QEMUの `check_cap` はtag、sealed状態、操作権限、アクセス長を含む境界を検査して例外へ進む。DDCを用いるアクセスからこの関数へ到達する経路も確認した。ここで揃うのはISAのアクセス制約とエミュレータの強制であり、製造されたハードウェア全体の証明ではない。コネクタの契約やアカウントを表す宣言ではない。[H0–H2](02-self-declaration.evidence.md#h0)

Kokaの論文は、`exn` effectなしで型付けされた式が未処理例外を投げないという性質を述べる。現行のcompilerは関数と引数のeffectを集めて整合を検査し、effect rowを単一化する。これは型注釈とプログラムとの食い違いを静的に検査する例である。ただし、2014年の論文の全定理が取得した現行compilerについて再証明済みであるとはしていない。`io`や`filesys`のeffectを知ることと、特定のパスやコネクタへの権限を知ることは違う。またeffect handlerの継続を、OSプロセスが切れた後の耐久的な再開と同一視しない。[E0–E4](02-self-declaration.evidence.md#e0)

### 契約による設計と icontract

本体確認。Meyerの前条件・後条件に対して、icontractは呼び出し前に前条件、結果の取得後に後条件を評価し、違反を例外にする。これは宣言と実際の入力・結果の不一致を検出する実装である。[D0–D1](02-self-declaration.evidence.md#d0)

ただし検査の有効化が条件であり、既定値は `__debug__`、無効なら元関数をそのまま返す。今回、固定したicontractソースを一時環境で実行し、負の前条件で本体未実行、負の後条件で本体実行後に違反、`enabled=False`では同じ負の入力を通すことを確認した。契約述語に書いていない外部行為を自動検出するものではない。[D2–D3](02-self-declaration.evidence.md#d2)

## 4. 費用・到達資源・state の独立判定

| 対象 | 宣言できる既存語彙 | 宣言と実態の食い違いを検出できるか | 判定の限界 |
|---|---|---|---|
| 金額 | SLA4OAIのcost/currency/billingはある | 今回のanalyzerで確認したのは宣言の構文・計画上の上限比較。実請求との比較は未確認 | 定額料金等と1回の仕事の金額を同一視しない。MCPのcostPriorityは費用の優先度で、金額ではない。[M12](02-self-declaration.evidence.md#m12) |
| 時間 | OpenSLOに指標、閾値、目標、時間窓がある | 外部の観測指標が必要。今回のSloth経路は宣言読込・変換まで | 集合的な応答時間SLOと各仕事の確定所要時間は別。OpenSLO v1とSloth v1alphaの版差を残す |
| レート上限 | SLA4OAIのrates/quotasがある | 宣言上の条件比較はある。実行回数の測定・超過拒否は今回のanalyzerから確認できない | CPU quotaやSLOのerror budgetをAPIの呼出回数上限に読み替えない |
| メモリ・ファイル・ネットワーク | CHERI capability、Pony権限型、Nix sandbox、Kubernetes資源とsecurityContext | 制御下の操作について拒否経路がある | 各実装の対象・実行条件内に限定。設定の検査だけで全外部権限を実証しない |
| コネクタ権限 | 認証scheme/scopeや独自属性を書ける。実行器の到達可能コネクタを共通に表す専用語彙の対は未発見 | 当該アカウント・環境での実際の到達性との共通検査は未発見 | サーバーへ接続する認証と、サーバーが持つ外向きの権限を区別 |
| 中断後の扱い | MCP requestState/Tasks、Kubernetes restartPolicy、CNETの継続操作がある | 宣言された継続・再投入能力と、異種ランタイムの中断後の実挙動との共通適合検査は未発見 | 通信の再試行、polling再開、コンテナ再起動、内部処理の再開を分ける |

SLA4OAIはOpenAPI本体とは別のDraft仕様である。analyzerの `P0-syntax.js` は宣言objectをスキーマに通す。`P3-compliance.js` は利用者が要求する量と宣言から求めた上限を比較する。実観測データを取り込むコードとしては読めず、名前の「compliance」だけで実態への準拠検査とは扱わない。[S1–S4](02-self-declaration.evidence.md#s1)

OpenSLOの閾値語彙は確認できるが、取得したSloth loaderは `openslo/v1alpha` とratio metricsを扱う。取得したOpenSLOの現行READMEに書かれた任意のv1閾値をそのままSlothが処理できるとは認定しない。SLOの宣言・変換・指標の計測・閾値判定を一つの未検証の対にまとめない。[S5–S7](02-self-declaration.evidence.md#s5)

MCP 2026-07-28の変更記録では、通信が切れた要求は新しいrequest IDで再投入する規定がある。`requestState`は追加入力を付けて要求を再試行する際にサーバーへ返す不透明な値である。Tasks拡張は実行中・追加入力待ち・終端状態と、クライアント再起動後に同じtask IDで照会を再開する形を定める。これらの語彙は存在するが、実行器プロセスのクラッシュ後に保存済み内部stateから再開できるという宣言や保証とはしていない。[M8–M10](02-self-declaration.evidence.md#m8)

## 5. 契約4項目と受け入れ条件の対応

以下は3節の対全てについての判定である。仕事・成果の形式が揃っていても、能力の全項目やevent streamまで揃うとはしない。

| 対 | 能力の宣言 | 仕事の受け取り | 成果の返却 | event stream | A2 | A4 | A11 |
|---|---|---|---|---|---|---|---|
| FIPA DF × JADE | 一部: 登録・探索 | 満たさない: DF単体は仕事受領でない | 満たさない | 満たさない | 一部 | 一部 | 満たさない |
| MCP × TypeScript SDK | 一部: 入出力型・注釈 | 一部: tool要求 | 一部: 型付き結果 | 一部: 通知はあるが内部行為の全出力でない | 一部 | 一部 | 満たさない |
| A2A × Python SDK | 一部: skills・通信機能 | 一部: メッセージ受領 | 一部: メッセージ・成果物 | 一部: task/成果更新、内部行為は不足（[A6](02-self-declaration.evidence.md#a6)） | 一部 | 一部 | 満たさない |
| OpenAPI × openapi-core | 一部: 入出力型 | 一部: request検査 | 一部: response検査 | 満たさない | 一部 | 一部 | 満たさない |
| Kubernetes | 一部: 資源・配置・再起動 | 満たさない: Pod作成と仕事メッセージは別 | 満たさない | 満たさない: インフラ情報だけでは不足 | 一部 | 一部 | 一部 |
| Nix | 一部: 入力・必要特徴・資源制限 | 一部: derivation受領 | 一部: store成果。共通仕事形式は不足 | 満たさない | 一部 | 一部 | 一部 |
| Pony | 一部: 型・権限 | 一部: 型付き呼び出し | 一部: 型付き値 | 満たさない | 一部 | 一部 | 一部 |
| CHERI × QEMU | 一部: メモリ権限 | 満たさない | 満たさない | 満たさない | 満たさない | 一部 | 一部 |
| Koka | 一部: 型・effect | 一部: 型付き関数入力 | 一部: 型付き関数結果 | 満たさない | 一部 | 一部 | 一部 |
| 契約による設計 × icontract | 一部: 述語で表した範囲 | 一部: 前条件 | 一部: 後条件 | 満たさない | 一部 | 一部 | 満たさない |

A2の「一部」は、既存の宣言形式・型に適合する対象を扱う一般経路があるという意味である。別ベンダー・別アカウント・別環境を持つPDA実行器を実際に追加する試験は行っていない。A11の「一部」は、配置条件または資源アクセス拒否の構成要素があるという意味であり、開発PCだけにある実コネクタ権限に基づく割り振りを確認した意味ではない。

## 6. 片側だけ・歴史的コード・未発見

### 三つ組の対応を確定していないもの

| 対象 | 確認できた側 | 揃わない理由 |
|---|---|---|
| WSDL 1.1 / Zeep | WSDLの抽象メッセージ・bindingと、Zeepの送信XMLの必須要素・出現数検査 | WSDL単独の能力保証と、XSD由来の個別制約を混同しない。完全な型適合・外部動作・費用の準拠の対は確定していない。[W0–W1](02-self-declaration.evidence.md#w0) |
| AsyncAPI / parser-js | アプリケーションが宣言に従うという仕様、宣言文書を検査する実装 | 今回追跡したのは文書をSpectralに通す経路。実際に流れる全メッセージや副作用を検査する経路ではない。[Y1–Y2](02-self-declaration.evidence.md#y1) |
| SLA4OAI / analyzer | 費用・レート語彙、宣言の検査 | 宣言対象の実サービスから実消費・課金・所要時間を観測して照合する箇所は未確認。[S1–S4](02-self-declaration.evidence.md#s1) |
| OpenSLO / Sloth | 目標語彙、v1alphaのratio SLO読込・変換 | 仕様版と実装の対応が限定される。今回Prometheusによる実指標評価まで再取得・実行していない。[S5–S7](02-self-declaration.evidence.md#s5) |
| MCP Tasks拡張 | 状態・durable task handle・polling再開の仕様 | 本調査ではTasks拡張の全状態遷移と永続化を強制する実装まで追っていない。coreのtool schema検査とは別扱い。[M10](02-self-declaration.evidence.md#m10) |

### contract net の eligibility specification と node abstraction

本体確認。Smith 1980はeligibility specificationを入札に必要な条件、node abstractionを候補nodeの説明として分ける。条件と持ち物を突き合わせる抽象は古典から存在する。原著者サイトの1978年Interlispコード掲載PDFも取得できた。[C0・C4](02-self-declaration.evidence.md#c0)

掲載コードの `CHECK!ELIGIBILITY`（印刷p.6、PDF第7頁）は、条件列の各項目を `CILPARSE` で評価し、全項目の成立を求める。`PROCESS!TASK!ANNOUNCEMENT`（印刷p.43、PDF第44頁）は、task templateがあり、eligibilityが未指定か検査に通る場合だけ次に進む。原画像を目視してOCRと照合した。これは実装がなかったという結果ではない。[C1・C3](02-self-declaration.evidence.md#c1)

ただし配布形態はコード掲載PDFであり、対応するGit commit SHAはない。PDFのSHA-256で固定できる歴史的実装として別枠に置き、現在ビルド可能なコードと実行試験の揃った対とは数えない。`RESUME!TASK`（印刷p.51、PDF第52頁）は保持するtask process pointerへ `TRYNEXT` を行う。シミュレータの継続であり、外部実行器が自分のクラッシュ後再開能力を宣言するスキーマではない。[C2](02-self-declaration.evidence.md#c2)

### 未発見と探索範囲

| 未発見の対象 | 検索語・確認した資料 | 限定した結論 |
|---|---|---|
| 費用3項目と到達資源・再開能力を同一実行器単位で宣言し、実態まで検査する対 | `executor capability resumable cost schema`、FIPA SC00023J、MCP Tool/Tasks、A2A proto、SLA4OAI、OpenSLO | 調査した範囲で一つに揃う対は未発見。個別の語彙が存在しないとはしない |
| 開発PCのコネクタ権限の実態と宣言を検査してA11の割り振りを行う対 | `capability filesystem network`、Pony object-capability、CHERI、Kubernetes affinity/securityContext、Nix features/sandbox、MCP roots、A2A security | 下位の強制はある。外部コネクタと実行器の組の実態照合まで揃う対は未発見 |
| 中断後に内部処理を再開するか再投入するかを実行器ごとに宣言し検査する対 | `resume\|restart\|checkpoint\|requestState\|taskSupport` をMCP仕様・Tasks拡張、A2A schema、Kubernetes API、CNET掲載コードで確認 | 関連するstate・再試行・継続操作は存在する。要件の能力宣言と実態検査の対は未発見 |
| 改変できない実行器の能力宣言を型検査だけで保証する対 | `effect type safety`、Koka論文とcompiler、Pony、Meyerとicontract | 型・述語を検査できる制御下のプログラムに限った証拠であり、任意の外部ランタイムに拡大しない |

`"Reid Smith" "CNET" source code contract net` の検索は原著者サイトのコードPDFに到達したため、「contract netのソース未発見」の項目には入れない。

### 取得できなかった資料

1. `https://api.github.com/repos/microsoft/Dafny/commits?per_page=1` と `https://api.github.com/repos/microsoft/cheriot-sail/commits?per_page=1` はHTTP 403、`rate limit exceeded`。この未取得内容の主張は使っていない。CHERIは別途 `CTSRD-CHERI/qemu` の公開Git参照と固定SHAのtarballを取得して確認した。
2. 通常sandboxの最初の `https://api.github.com/repos/modelcontextprotocol/typescript-sdk/commits/main` は名前解決失敗でHTTP応答なし。許可された公開資料の取得として再実行後はHTTP 200で取得したため、MCP資料の欠落はない。
3. Webツールによるcontract netコードPDFの画像取得はcache missでHTTP状態未提示。PDF本体はHTTP 200で取得し、ローカル描画した第7・44・52頁を確認した。

### 実際に行った検査と行っていない検査

1. 行ったもの: 固定commitのソース取得、呼び出し元から検査・例外への経路の読解、全A2A protoと関係スキーマの語彙検索、引用が指定した行にあることの機械照合、歴史的コードの画像照合。icontractは前条件違反・後条件違反・検査無効の3ケースを実行し、想定する拒否位置を確認した。
2. 行っていないもの: MCP/A2Aを起動した相互運用試験、Kubernetesクラスタでのscheduler/cgroup試験、Nix sandboxでのアクセス試験、Pony/Kokaのcompiler実行、CHERI emulatorの実行、外部コネクタ・実請求・SLOの実指標照合、プロセス中断からの再開試験。コード読解から確認した強制箇所を、これらの実行試験の結果と混ぜない。

## 7. 固定した一次資料

全て2026-09-20取得。GitHub資料は下表のcommitを使用し、引用のURL・path:line・最小限の原文は根拠集に記録した。

| 資料 | commit SHA |
|---|---|
| [MCP仕様](https://github.com/modelcontextprotocol/modelcontextprotocol) | `24efd6e7cbd7a074e6b3b781eb370891df40afad` |
| [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) | `60321700871029401a2e3bed8fdf4f02c9ec3331` |
| [MCP Tasks拡張](https://github.com/modelcontextprotocol/ext-tasks) | `9263312d11a682ac83f83fe84794d4627efd22f5` |
| [A2A](https://github.com/a2aproject/A2A) | `afda8316c64951a2ecb2a0d3d10867405d2b4095` |
| [a2a-python](https://github.com/a2aproject/a2a-python) | `9a00f9b91fd4e85019c8983278a39d65f67fdd04` |
| [JADE非公式ミラー](https://github.com/ekiwi/jade-mirror) | `2723c7b52269c34d7f2ef366816776bcbcd90b8f` |
| [OpenAPI](https://github.com/OAI/OpenAPI-Specification) | `c9f8f040e825a827bb011955bd41b7e2d899688f` |
| [openapi-core](https://github.com/python-openapi/openapi-core) | `0337b43bd65dac2f5ed041b78996383370f72da3` |
| [Kubernetes](https://github.com/kubernetes/kubernetes) | `400031d69530e018d5c001a922d3c5d2afaba954` |
| [Kubernetes website](https://github.com/kubernetes/website) | `16f40ab512244b5df94714bbaba96f75cae55b8e` |
| [Nix](https://github.com/NixOS/nix) | `af265fd96c62fa4409d05124ce051ae1cdff0b13` |
| [Pony compiler](https://github.com/ponylang/ponyc) | `f8a5e22672dfd2427b45e6845bffcc690e02f57e` |
| [Pony tutorial](https://github.com/ponylang/pony-tutorial) | `782050ed0b25dfc80ecd317f9c68c64e9baafc96` |
| [CHERI QEMU](https://github.com/CTSRD-CHERI/qemu) | `d0bb921cd6d34d1f8f4b3dafd279aa571795c938` |
| [Koka](https://github.com/koka-lang/koka) | `d881e92b61516f84beeebd2a80ebb6c09a9847f0` |
| [icontract](https://github.com/Parquery/icontract) | `3e733f9e790359036c4da2cc550c599107710b60` |
| [SLA4OAI仕様](https://github.com/isa-group/SLA4OAI-Specification) | `1f5dd38d6efd5b8c7ef68e01620a8abbe2f01626` |
| [sla4oai-analyzer](https://github.com/isa-group/sla4oai-analyzer) | `2262457461160c6c608b6b822e48da7004d2bc49` |
| [OpenSLO](https://github.com/OpenSLO/OpenSLO) | `e74b589cc98b98a5413611176d659a72318e7519` |
| [Sloth](https://github.com/slok/sloth) | `8a3be4fab79defa4448d09d91b48422615980b05` |
| [Zeep](https://github.com/mvantellingen/python-zeep) | `1b7072c0dba397b86e8a47cf766a39f981b3a2de` |
| [AsyncAPI](https://github.com/asyncapi/spec) | `1dd65fd2c1ed13f06365c1e870c61cdc82d8a981` |
| [AsyncAPI parser](https://github.com/asyncapi/parser-js) | `e38319f82cf3bc42097f95035c2917ccbae8e77f` |

Git commitを持たない一次資料は、FIPA SC00023Jの保存時刻付きアーカイブ、WSDL 1.1 W3C Note 2001-03-15、Smith 1980論文と1978年コード掲載PDF、Meyer 1992論文、CHERI ISAv9 UCAM-CL-TR-987、Leijen 2014 Koka論文である。原URL・取得日・版・PDFページ・取得物のSHA-256を根拠集に記録し、Git SHAがあるようには記載しない。

## 8. 他の未実施の本へ渡す問い

1. 第3本「ランタイムのラッパー」へ: スキーマ検査、特定APIの拒否、資源アクセスの拒否、外部観測による申告の検査は、改変できない各実行器についてそれぞれどこまで実施できるか。正常結果だけ検査するMCPのような実装で、エラー・追加入力待ち・中断をどの範囲まで既存仕様が覆うか。
2. 第4本「ログストア」へ: 能力宣言の版と、実際に拒否・実行・再投入された出来事を同じ仕事へ結び付けられる一次資料はあるか。state語彙の存在から内部行為のevent streamが得られると推定しない場合、観測可能な範囲はどこまでか。
3. 第5本「全体」へ: 費用・資源・stateの個別の語彙と強制は存在する。空白は、それらがないことではなく、環境・アカウント・エージェントの組の宣言と、外部から確認した実態とが同じ契約で揃うかである。宣言情報の探索とその真実性の確認を分けたうえでA2・A4・A11を判定できるか。
