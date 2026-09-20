# 第3本 — ランタイムのラッパー

作成・一次資料取得日: 2026-09-20 JST。物差しは `docs/requirements.md` の commit `cdd90e945d938769aefa17a2b8de3236647f6bdc`。`git log -1 --format=%H -- docs/requirements.md` で確認した。調査記録であり、設計・製品選定・要件追加ではない。根拠の正本は本書、逐語引用・取得版・照合位置は `03-runtime-wrapper.evidence.md`。

本書の「本体確認」は、この第3本の担当が公開一次資料の本文と固定コミットのコードを取得して読んだことを表す。実行試験済みという意味ではない。外部資料について分担先の未再取得の「報告」は使っていない。第1本の記述は探索の起点として読み、今回の判定に必要な箇所は別途確認した。各製品を組み合わせた起動試験、故障注入、PDAの受け入れ試験は実施していない。

## 1. 結論

1. ブリーフの「揃えるべき最小の契約」への回答は、要件が固定した「能力の宣言・仕事の受け取り・成果の返却・event stream」の4項目である。既存の最小契約を調べると、OCI/containerdは実行の状態遷移、OTPはコールバックと終了、LSPは言語機能ごとのメッセージと能力、POSIXはバイト入出力と終了状態に範囲を絞っている。これらの範囲をそのままPDAの最小契約と呼ぶと、成果の種別と実行中のevent streamが欠ける。6系譜で抽象・限定された不変量・実装の対が揃ったが、契約4項目とA1/A2/A5を全て満たす対は確認できなかった。
2. 「何を契約に入れなかったことで成功したか」について、入れていない範囲は特定できた。containerdはランタイム内部の実行方法とshimごとの多重度、OTPは仕事の意味と状態の内部表現、LSPは言語解析アルゴリズムと全機能の必須実装、POSIXは入出力の意味・構造を共通契約にしない。一方、それを除外したことが成功の原因だという比較実験・因果的証拠は取得していない。ここで確認できたのは、異なる実装を共通の接続点で受ける構造と、その境界である。
3. 「ラッパー自身の契約違反を検出できるか」への回答は、違反の種類により異なる。runcは不正なstart状態を拒み、OTPは不正なコールバック戻り値と子プロセス終了を検出し、ACP SDKの受信経路は一部の不正な種別・必須データを拒む。しかし、ACPには不正な任意要素を除去して受理する箇所もある。ラッパーが通知を一つも作らなかった場合や、許された種別のまま出来事を落とした場合に、それだけで欠落を検出する対は未発見である。
4. 「ラッパーと受け入れ検査の境界」への回答は、包んだランタイムから観測できる入力を変換することと、その変換結果を信用せず検査することは別である。ACPの送信メソッドのTypeScript型は実行時検査ではない。同じSDKでも受信側でスキーマを呼び出す経路があり、ラッパーが作った不正データをその境界で検出できる。ただし、その検査に届かなかった出来事の完全性までは保証しない。
5. 「binary session typesの双対性検査で足りるか」への回答は、コアと一実行器の一つの対話について、双方が型で記述された送受信順序に従うことを検査する範囲では適合する。しかし、双対な型があることだけでは、改変できないランタイム、ラッパーの変換、外部での中断、複数の対話の相互依存、event streamの完全性は検査できない。したがって、MPSTの追加装置を必要としないことと、PDAの契約全体を双対性だけで満たすことは同じではない。

## 2. 対の表

「満たす」は要件に記載された項目全体を確認できた場合、「一部」は対応する機構はあるが項目全体は未達、「満たさない」はこの抽象と実装の対に該当する機構がない場合である。汎用ライブラリで将来実装できる可能性を「満たす」とは数えない。A1は記憶・可視化・監査も含み、A2はPDAの実行器を追加できること、A5は出来事の形式・可視化・監査まで含む。本表の全体判定に「満たす」はない。対として成立するのは、各行に明記した限定された不変量についてである。

| 抽象 | 不変量と限界 | 実装（強制箇所、SHAは3節） | 契約との対応（能力／仕事／成果／event stream） | A1／A2／A5との対応 | 足りないもの |
|---|---|---|---|---|---|
| OCI runtime specification＋containerd Runtime v2仕様 | created以外へのstartは状態を変えずエラー。shimのTaskStartはTaskExitに先行する。OCIの状態とshimイベントは別契約 | R1 `runtime.md:123-129`、R2 `start.go:29-55`、R3 `cmd/containerd-shim-runc-v2/task/service.go:184-202,333-347`（O1〜O7） | 一部／一部／満たさない／一部 | 一部／一部／一部 | コンテナ制御を揃えるが、仕事・成果の種別、受け取った指示・呼んだツール・判断のevent streamではない。shim切断検出はイベント完全性検査ではない |
| Erlang/OTP behaviour＋supervisor、supervisor_bridge | callbackの外形を検査し、子のEXITを再起動方針へ接続。指定したPidが終了するとbridgeも終了 | R4 `lib/stdlib/src/gen_server.erl:2552-2569`、`supervisor.erl:1287-1293,1472-1491`、`supervisor_bridge.erl:181-190,211-224`（E1〜E8） | 一部／一部／一部／満たさない | 一部／一部／満たさない | 任意のReplyの成果種別、仕事に絞ったコンテキスト、正常動作中に落ちたevent、宣言の費用・権限等は強制しない |
| ACP v1仕様＋TypeScript SDK＋Claude/Codex adapter、Gemini CLI native | ACPメッセージとして入出力する規約と、受信した`session/update`の一部スキーマ検査。各実装が既知のランタイムeventを共通の更新へ写す | R5 `docs/protocol/v1/transports.mdx:20-28`、R6 `src/acp.ts:1069-1082,1137-1151,1390-1395`／`src/schema/zod.gen.ts:2848-2929`、R7〜R9の4節記載箇所（C1〜C24） | 一部／一部／一部／一部 | 一部／一部／一部 | 不正な任意要素の脱落、未変換event、既知eventの選択的省略。記憶・監査まで同形の実証なし。Gemini CLIはGemini API単体ではない |
| LSP 3.17仕様＋vscode-languageserver-node | initializeで双方の機能を宣言し、例としてhoverはサーバーの提供宣言がなければクライアントに登録しない。フレーム境界とRPC外形は別に検査 | R10 `_specifications/lsp/3.17/specification.md:414-418`、R11 `client/src/common/hover.ts:34-49`、`jsonrpc/src/common/messageReader.ts:224-237`／`messages.ts:505-529`（L1〜L5） | 一部／一部／一部／満たさない | 一部／一部／満たさない | 言語機能の要求・応答を揃える。内部処理の逐次監査event、PDAの能力宣言全項目はない。RPCの外形検査は各resultの完全なスキーマ検査ではない |
| POSIX.1-2024プロセス入出力・pipe・wait＋Linux | pipeで書いたデータをFIFOで読み、waitで子の終了状態を取得する。これは複数streamをまたぐ出来事の順序ではない | POSIX Issue 8の`pipe`／`wait`、R12 `fs/pipe.c:396-448`／`kernel/exit.c:1313-1327`（P1〜P6） | 満たさない／一部／一部／満たさない | 一部／一部／満たさない | stdin/stdoutのバイトとexit codeには成果の種別、能力、イベント語彙がない。exit codeの数値分類は成果の種別分類ではない |
| binary session types（Session Types for Rust論文）＋session-types | 双対の送受信型で両端を作り、送信によりchannelを消費して次の型へ進む。対象はこの型付きchannelを使うプログラム | R13 `src/lib.rs:130-157,209-229,479-488`（B1〜B6） | 満たさない／一部／一部／満たさない | 一部／一部／満たさない | 型外のランタイム出力やevent欠落を監視しない。論文は完全な形式証明を提示しておらず、safe Rust・早期dropの留保がある |

### 2.1 OCIとcontainerdの境界（本体確認）

OCIはstartの前提を定め、runcの`start.go`はCreatedだけを実行し、それ以外を拒む。containerdのshimはその上に共通の制御RPCとイベントを載せる。`preStart`が早すぎるプロセス終了を保持し、startイベントを送信キューへ入れてから`handleStarted`が保留中の終了を処理するため、同じshimの観測上のstart/exit逆転を防ぐ具体的な強制箇所がある。仕様の逐語不変量はO1・O4、実装の順序はO6・O7に記録した。

一方、`forward`のPublish失敗分岐はエラー記録であり、完全な業務event列との突き合わせではない（O8）。shim切断はcontainerd側で検出してcleanupへ進むが（O9）、接続が生きたまま通知を省いたshimを検出するコードとはいえない。`RuntimeInfo.features`は機械可読だが、`-info`はSHOULDで、費用・得意不得意・到達資源をPDAの意味で必須にする契約ではない（O11）。

### 2.2 OTPの境界（本体確認）

`gen_server`は`{reply, Reply, State}`等の外形を要求し、不正な戻り値は`bad_return_value`で終了させる。外形が正しければ、Replyが仕事の成果として正しい種別かどうかをこの共通層は検査しない（E2・E3）。supervisorはEXITと再起動頻度を扱う（E4・E5）。生存したまま誤ったReplyを返すことや、ログを出さないことは、この検出対象と異なる。

`supervisor_bridge`は「非OTP subsystemを監督に接続する」実在のラッパーである。callbackから得たPidをlinkし、そのPidのEXITを自身の終了へ写す（E6〜E8）。したがって、対象の内部をOTPに書き直さなくても生存監督へ揃えられる。ただし、subsystemの内部処理を共通の仕事・成果・event streamにする機能まであるとはいえない。

### 2.3 LSPとPOSIXの境界（本体確認）

LSPの共通契約は具体的な言語機能の要求・応答とcapabilityにある。`HoverFeature.initialize`が宣言を見て登録を止めるため、capabilityは文書上だけの情報ではない（L1・L2）。一方、JSON-RPCの`Message.isRequest`等はmethod/id等を検査する外形判別であり、型宣言に書かれた全てのresultを実行時に検査する証拠にはならない。Content-Lengthの欠落や未処理request methodの検出は別途ある（L3〜L5）。言語サーバーの内部の推論や解析を全件出す仕様ではない。

POSIXでは0/1/2の入出力規約、pipeのFIFO、waitの終了状態が共通点であり、Linuxはpipeのtailからバイトを取り出して進める（P1〜P6）。ここから、「任意のプログラムを起動してstdoutを読む」だけでは、型付き成果や共通event streamは得られないと判断する。stdoutとstderrの別々の列を集めても、内部で起きた全出来事の順序が自動的に証明されるわけではない。

## 3. 固定したコミット

以下はすべて本体確認。`path:line`はこのSHAのファイルを指す。先頭ブランチの将来の状態は根拠にしない。

| ID | 一次資料 | commit SHA |
|---|---|---|
| R1 | [opencontainers/runtime-spec](https://github.com/opencontainers/runtime-spec/tree/6999a89a76a0329f440d5740497bedb9dd431297) | `6999a89a76a0329f440d5740497bedb9dd431297` |
| R2 | [opencontainers/runc](https://github.com/opencontainers/runc/tree/c17aefd6c669df803b7dada41a9dc1737b54f78c) | `c17aefd6c669df803b7dada41a9dc1737b54f78c` |
| R3 | [containerd/containerd](https://github.com/containerd/containerd/tree/b0a37b632b22993f9a85ea7583b8ae0102d3d4a2) | `b0a37b632b22993f9a85ea7583b8ae0102d3d4a2` |
| R4 | [erlang/otp](https://github.com/erlang/otp/tree/10078218203aa3ac90175c547fb4e7c91a33677c) | `10078218203aa3ac90175c547fb4e7c91a33677c` |
| R5 | [agentclientprotocol/agent-client-protocol](https://github.com/agentclientprotocol/agent-client-protocol/tree/f0a04b2172614ca37f2fecf2a2d877a063b37e5f) | `f0a04b2172614ca37f2fecf2a2d877a063b37e5f` |
| R6 | [agentclientprotocol/typescript-sdk](https://github.com/agentclientprotocol/typescript-sdk/tree/f7941e753be6c809230307c7cf8b4f9ee220018c) | `f7941e753be6c809230307c7cf8b4f9ee220018c` |
| R7 | [agentclientprotocol/claude-agent-acp](https://github.com/agentclientprotocol/claude-agent-acp/tree/d421f56a6c43cde16d9a7531d08a750a5ef2f04a) | `d421f56a6c43cde16d9a7531d08a750a5ef2f04a` |
| R8 | [agentclientprotocol/codex-acp](https://github.com/agentclientprotocol/codex-acp/tree/d7b07c1b44a28890cdf3d5450f8974a812db5ae2) | `d7b07c1b44a28890cdf3d5450f8974a812db5ae2` |
| R9 | [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli/tree/cfbcaa8df13ea4610bb379b377b56d62980c0032) | `cfbcaa8df13ea4610bb379b377b56d62980c0032` |
| R10 | [microsoft/language-server-protocol](https://github.com/microsoft/language-server-protocol/tree/c2f3a1abfb613de5d55271f0d07ff103068b0d04) | `c2f3a1abfb613de5d55271f0d07ff103068b0d04` |
| R11 | [microsoft/vscode-languageserver-node](https://github.com/microsoft/vscode-languageserver-node/tree/87f58727b5d287ef9049fb0b4b52984a6e62d604) | `87f58727b5d287ef9049fb0b4b52984a6e62d604` |
| R12 | [torvalds/linux](https://github.com/torvalds/linux/tree/518e5b794c06c0f0eb40df3e202274a66202c137) | `518e5b794c06c0f0eb40df3e202274a66202c137` |
| R13 | [Munksgaard/session-types](https://github.com/Munksgaard/session-types/tree/86d45aec3c1700f189e69ba7fc580c6938c9cc50) | `86d45aec3c1700f189e69ba7fc580c6938c9cc50` |

## 4. ACPで実際に揃う範囲と検出範囲

ここではR5のv1仕様とR6のSDK 1.4.0を対象にする。R5にはv2の文書も同居するが、その内容をv1実装の根拠に混ぜない。R7はSDK 1.4.0、R8は`^1.4.0`を宣言する。R9は0.16.1を宣言するため、R6の検査をR9の実際の接続へそのまま帰属させない。依存宣言と読んだソースの照合であり、三者を同時に動かした相互運用の実証ではない（C21〜C23）。

| 対象 | 本体確認した変換・検査 | 検出できるもの | この証拠で保証できないもの |
|---|---|---|---|
| ACP仕様 | stdoutは有効なACPメッセージに限定。promptと更新が同じプロトコル上を流れ、共通ContentBlockを使用（C1〜C3・C19・C20） | 仕様は違反条件を定義する | MUSTの記載だけで実行時の拒否を証明できない |
| SDK受信経路 | `registerAppNotification`→`parseParams`→`zSessionNotification`→`zSessionUpdate`（C4〜C7） | この版の未知`sessionUpdate`や、例えば`agent_message_chunk`の不正な必須contentを、handlerへ渡す前に検出 | 全フィールドの無損失性、未到着通知の欠落 |
| SDKの例外処理 | 通知の検査例外は`jsonrpc.ts:1416-1435`でエラー記録（C10） | 不正通知を通常handlerに渡さない | 相手への通知応答、接続の自動停止、PDAの監査ストアへの記録はこの分岐では保証しない |
| SDKの許容的な処理 | `zToolCall.content`は`vecSkipError`を使い、不正要素を除去。`_meta`等は既定値へ戻す処理を持つ（C8・C9） | 正しい必須外形の範囲で残ったデータを受理する | content配列の一部が失われたことを成果の違反として必ず拒否する保証 |
| SDK送信経路 | `AgentSideConnection.sessionUpdate`は`sendNotification`へ値を渡す。受信側のparseは呼ばない（C11） | 静的なTypeScript型による開発時検査 | ラッパーの実行時データが正しいこと。型アサーションやJavaScript呼び出しを通じた値まで拒むとはいえない |
| Claude adapter | `src/acp-agent.ts:5923-5948`でtool進捗を`tool_call_update`へ。未知メッセージは`:5988-6000`から`utils.ts:77-85`へ（C12〜C14） | 既知のランタイム出力の変換。未知入力の診断ログ | `unreachable`は名前に反して例外を投げずログを出す。未知入力を契約違反eventとして必ず返すわけではない |
| Codex adapter | `src/CodexEventHandler.ts:512-534`でmessage deltaやitemの開始・完了を変換。`:684-697`には`process/exited`等を`null`へする分岐（C15・C16） | 対象として列挙したapp-server通知の変換 | 全ての原始通知を同じ粒度で保存すること。個々の省略がPDA上も欠落に当たるかは別途対応関係が必要 |
| Gemini CLI native | `packages/cli/src/acp/acpSession.ts:411-446`でContent/Thoughtを更新へ。`:469-485`の既定分岐は`break`（C17・C18） | 列挙したCLI内部eventの変換 | 未対応eventを拒否・報告すること。要件のGemini API単体を同じ契約へ包む実装の実証 |

この検査は「成果がどの形式で来たか」を扱い、文章が何を意味するかを分類するものではない。仕事と成果で同じJSON型を使う必要があるという判定もしていない。要件は同じプロトコルに基づくメッセージを求めている。

`UsageUpdate.cost`はこのSDKに存在する（C24）。したがって「ACPに費用の語彙が一切ない」とは結論しない。実行中の使用費用の報告と、実行器の能力として事前に示す費用・到達資源・不得意・取れるstateの網羅的宣言は別であり、この対だけで能力の宣言全体を満たしたとは確認していない。

### 4.1 ラッパー自身の欠落を検査できるか

本体確認したのは、不正値が検査境界に到着すれば検出できる箇所と、途中で情報を落としても動作を続ける箇所の両方である。後者について、削除前の値を再取得する監査機構まで存在すると解釈しない。

ここからの論理的帰結は次のとおりである。内部でtool呼び出しが起きず通知もない実行と、tool呼び出しは起きたがラッパーがその通知を落とした実行が、同じ受信メッセージ列になるなら、受け入れ検査はその列だけから両者を区別できない。種別検査は、何も届かなかった出来事を復元しない。これは実装の不在を世界全体について断定したものではなく、調査した境界で得られる情報の限界である。

OCIとOTPの終了検出はラッパー自身の停止を外側で観測する例である。一方、生存したラッパーのevent欠落の独立検出は、今回の対では確認できていない。欠落した通知がまだ正常な実行の一部である可能性を、恣意的な時間制限で違反と決めることもしていない。

## 5. 契約に含めない範囲と、成功について言えること

以下の「含めない」は、既存の系譜で共通に固定していない範囲の記述である。PDAの契約を削る提案ではない。

| 系譜 | 共通契約に含めない範囲 | 確認できた効果と限界 |
|---|---|---|
| OCI/containerd | コンテナ内部の仕事・成果の意味、engine内部の実行方法、shimとコンテナの1対1/1対多の選択、host共通設定の一律化（O3・O5・O11・O12） | 名前から別shimを解決するコードと、同じshimから別OCI engineを扱う仕様を確認（O10）。他のengineとの実動比較や普及原因の立証はしていない |
| OTP | Reply・Stateの内部構造、仕事のアルゴリズム。bridge対象subsystemのOTPへの書き直し（E2・E6〜E8） | 生存監督の接続は共通化できる。ただし仕事の成果やeventの完全性はcallback外形からは決まらない |
| ACP | モデルの内部推論手順、全入力種別の必須対応。入力はtext/resource_linkの基準と追加能力に分かれる（C3・C19） | 3実装に共通の更新種別への変換を確認した。標準種別へ写らないベンダー情報、未知入力、依存版の差は残る |
| LSP | 言語解析アルゴリズム、全言語機能の必須実装（L1・L2） | hoverのように宣言された機能だけを提供するコードを確認。PDAの任意の仕事と監査を扱う証拠ではない |
| POSIX | stdoutの構造・意味、入力に応じた成果の種別、業務event（P1〜P6） | byte列のFIFOと終了観測で異なるプログラムを接続できる。PDAが要求する成果種別を捨ててよい根拠にはならない |

これらの除外が各系譜の「成功の原因だった」と判断する一次資料は、今回の探索では未取得である。確認した仕様・実装の境界と、成功の因果関係を区別する。

## 6. binary session typesが保証する範囲

[Session Types for Rust](https://munksgaard.me/papers/laumann-munksgaard-larsen.pdf)は、型付きchannel上のプロトコル安全性を対象にする。取得版のPDF物理1頁と9頁（§6.2〜6.3）を確認した。§6.2は完全な形式証明を出していないと明記し、§6.3はaffineな値が早期に捨てられる問題を述べる（B5・B6）。この留保を省いて「証明済みのあらゆる通信安全性」とは扱わない。

現在の固定実装は`session_channel<P: HasDual>()`で双対の両端を作り、`send(self, v)`が元のchannelを消費する（B1〜B3）。`HasDual`はsealedであり、論文当時の独自実装許容の説明を現在のAPIへそのまま移さない。現在の未終端channelのDropにはpanicもある（B4）。これらは実際の強制箇所だが、型に従ったまま内部eventを出さない処理を検出する機構ではない。

PDAに対する判定は、次の順序で前提を限定したものになる。

1. 一つのコア・実行器間の対話を双方の送受信型で表し、その型を使う実装を検査するなら、参加者全体のglobal typeやprojectionを導入せずに、その対話の双対性を検査する範囲を記述できる。
2. ベンダーのプロセスはその型付きプログラムではない。双対なAPIをラッパー側に付けても、変換前の自由な出力と変換後のメッセージが正しく対応する証明にはならない。
3. 二者間の各対話が双対でも、他の対話の完了待ちや外部の中断まで自動的に解決しない。ここは今回確認したライブラリの型と受信手順から導く限界であり、別の方式を追加する提案ではない。

## 7. 片側だけ

| 対象 | 今回揃った側 | 揃わない理由 |
|---|---|---|
| Autili・Inverardi・Tivoli・Garlan, [Synthesis of “correct” adaptors for protocol enhancement in component-based systems](https://arxiv.org/pdf/1504.07504v2) | 抽象・不変量（論文は本体確認） | LTSで表したcomponentとdesired behaviorからcoordinatorを合成し、不整合な相互作用を避ける。取得版はarXiv v2、全8頁。SYNTHESISという実装の存在を著者は記すが、配布先がHTTP 404で、対応する公開コードをSHA/path:lineで固定できなかった。したがって本調査では「抽象のみ」とし、実装がないとは書かない（F1） |
| Schmidt, [Wrapper Facade](https://www.dre.vanderbilt.edu/~schmidt/PDF/wrapper-facade.pdf), C++ Report, 1999 | パターンの抽象と実装例の記述（本体確認） | 低水準関数をclass interfaceで包むパターンとACE等の例はある。event streamの完全性や成果の種別保存を述べる形式的不変量、それを保証する実装の箇所の組は本稿から特定できなかった。名称がwrapperであるだけで正しさの対として採用しない（F2） |
| Gemini API単体、jev HTTP API、決定論的検証ツールを一つの共通契約に揃えた実装 | 今回は揃わず | Gemini CLI nativeは確認したがAPI単体と同一視しない。jevの特定公開仕様・リポジトリは今回の入力で指定されていない。CLI/HTTPという輸送形態だけから仕事・成果・eventの契約を補わない |

## 8. 未発見・取得できなかった資料

「未発見」は次の探索範囲内の結論である。

| 探したもの | 検索語・照合した資料 | 到達点 |
|---|---|---|
| ラッパーが省いたeventを、ラッパーと独立に全件検出する実装 | `containerd shim runtime v2 API OCI runtime specification lifecycle`、`TaskExit`、`forward`、`preStart`、`cleanupAfterDeadShim`、ACPの`session/update`／`default`／`unreachable` | 切断、終了、既知eventの順序、受信データの検査は確認。ラッパー生存中の全event欠落を独立に検出する箇所は未発見 |
| adapter/facadeの正しさを形式化し、公開実装まで照合できる対 | `software adaptors protocol interoperability Yellin Strom formal correctness adapter`、`SYNTHESIS tool Tivoli adaptor source code github Autili Inverardi`、`facade wrapper formal verification design pattern research`。Autili論文2本、Schmidt著者公開論文 | 形式的adapter合成の研究と、Wrapper Facadeの実装例は存在。今回の取得範囲では不変量と公開コードの強制箇所が揃わず |
| 二者間の型検査だけで未改変のベンダーランタイムの監査eventを保証する対 | `Session Types for Rust`論文とsession-types全`src/lib.rs` | 双対構築と状態を進めるAPIは確認。型の外のプロセス出力との対応・欠落検出は未発見 |
| 全対象の差し替え後も記憶・可視化・監査まで同形となる実証 | ACPの3実装、OCI/runc/shim、OTP、LSP、POSIX、binary session typesを契約4項目とA1/A2/A5で照合 | 部分機構の対は6件。PDAの条件全体の実証は未発見 |

| 取得できなかったURL | 結果 | 扱い |
|---|---|---|
| [SYNTHESIS配布先（HTTP）](http://www.di.univaq.it/tivoli/SYNTHESIS/synthesis.html) | HTTP 404 | 実装の内容に関する主張には使用しない。論文に書かれた配布先を試した事実だけを記録 |
| [同HTTPS](https://www.di.univaq.it/tivoli/SYNTHESIS/synthesis.html) | 接続拒否（HTTP応答なし、Errno 61） | HTTP 403/404等と混同しない |
| [OTPの旧推定パス](https://raw.githubusercontent.com/erlang/otp/10078218203aa3ac90175c547fb4e7c91a33677c/system/doc/design_principles/des_princ.md) | HTTP 404 | `gen_server_concepts.md`・`sup_princ.md`と実装を取得して代替。旧パスの内容は使用しない |

PDFのweb表示補助で取得エラーが出たものは、公開URLから直接取得してHTTP 200と内容を確認した。上表は内容自体を取得できなかった資料である。

## 9. 要件への疑義と第5本へ渡す問い

要件への変更要求はない。「種別」は形式の分類、「自由な発話を許容しない」はコア側のラッパーと受け入れ検査が守らせる意味として扱った。未観測のeventの完全性が、受信データの種別検査とは別の性質であることを今回の留保として残す。

1. 第5本では、各ラッパーが取得可能なeventと取得不能なeventを区別したうえで、A5・A8の充足をどこまで一次資料で示せるか。通知が共通の形であることだけを、実行中の出来事が全て出ている証拠にしない。
2. 第5本では、自己宣言が示すstate・入出力種別と、ラッパーが実際に扱う操作・型・中断後の挙動が一致しているか。宣言スキーマと実装された拒否・既定値・無視を別々に照合できるか。
3. 第5本では、ログストアに届いたeventの順序・完全性と、ラッパーが生成する以前のeventの欠落を分けて評価できるか。ログへの正常な書き込みだけで後者が保証されたとは判定しない。
4. 第5本では、A1の記憶・可視化・監査とA2の追加が、共通RPCに接続できることから独立に示されているか。今回の6対が提供する部分機構を、全体の達成へ繰り上げない。
