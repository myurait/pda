# 第3本 — ランタイムのラッパー 根拠集

本文: `03-runtime-wrapper.md`。物差し: `docs/requirements.md` commit `cdd90e945d938769aefa17a2b8de3236647f6bdc`。取得日: 2026-09-20 JST。

全項目は第3本担当による本体確認。公開リポジトリは固定SHAの配布物またはrawファイルを取得して該当コードを読んだ。URLは同じSHAのファイルへ固定している。型宣言、検査の呼び出し、検査後の失敗処理を別項目にした。コードを稼働させた試験は含まない。短い逐語引用の外側は、指定範囲を読んだ要約である。

文献PDFは取得版の物理ページを1始まりで示す。改行・行末ハイフネーションのみを正規化して引用した。Gitコミットが存在しない資料は版・取得日・SHA-256で固定する。HTTP 200で取得した資料だけを本文の主張に使用した。

## OCI runtime specification・runc・containerd

### O1

本体確認。`opencontainers/runtime-spec@6999a89a76a0329f440d5740497bedb9dd431297`。[runtime.md:123-129](https://github.com/opencontainers/runtime-spec/blob/6999a89a76a0329f440d5740497bedb9dd431297/runtime.md#L123-L129)。

> MUST have no effect on the container

created以外のstartは無効かつエラー。スキーマ定義とは別の操作不変量。

### O2

本体確認。`opencontainers/runc@c17aefd6c669df803b7dada41a9dc1737b54f78c`。[start.go:29-55](https://github.com/opencontainers/runc/blob/c17aefd6c669df803b7dada41a9dc1737b54f78c/start.go#L29-L55)。

> cannot start an already running container

Created分岐だけExec。Stopped/Running/その他はエラー。

### O3

本体確認。`containerd/containerd@b0a37b632b22993f9a85ea7583b8ae0102d3d4a2`。[docs/runtime-v2.md:16-18](https://github.com/containerd/containerd/blob/b0a37b632b22993f9a85ea7583b8ae0102d3d4a2/docs/runtime-v2.md#L16-L18)。

> scoped to the execution lifecycle

shim APIの範囲。

### O4

本体確認。`containerd/containerd@b0a37b632b22993f9a85ea7583b8ae0102d3d4a2`。[docs/runtime-v2.md:388-404](https://github.com/containerd/containerd/blob/b0a37b632b22993f9a85ea7583b8ae0102d3d4a2/docs/runtime-v2.md#L388-L404)。

> MUST (follow `TaskStartEventTopic`)

TaskExitはTaskStartに後続する要求。

### O5

本体確認。`containerd/containerd@b0a37b632b22993f9a85ea7583b8ae0102d3d4a2`。[docs/runtime-v2.md:43-52](https://github.com/containerd/containerd/blob/b0a37b632b22993f9a85ea7583b8ae0102d3d4a2/docs/runtime-v2.md#L43-L52)。

> entirely within the scope of the runtime implementation

実行方法をランタイムに委ね、OCI互換engineを同じshimで扱う説明。

### O6

本体確認。`containerd/containerd@b0a37b632b22993f9a85ea7583b8ae0102d3d4a2`。[cmd/containerd-shim-runc-v2/task/service.go:184-202](https://github.com/containerd/containerd/blob/b0a37b632b22993f9a85ea7583b8ae0102d3d4a2/cmd/containerd-shim-runc-v2/task/service.go#L184-L202)。

> s.handleProcessExit(ee, c, p)

preStartは早期exitを保管しhandleStartedで処理。

### O7

本体確認。`containerd/containerd@b0a37b632b22993f9a85ea7583b8ae0102d3d4a2`。[cmd/containerd-shim-runc-v2/task/service.go:333-347](https://github.com/containerd/containerd/blob/b0a37b632b22993f9a85ea7583b8ae0102d3d4a2/cmd/containerd-shim-runc-v2/task/service.go#L333-L347)。

> s.send(&eventstypes.TaskStart{

start通知をキューに入れてからhandleStarted。

### O8

本体確認。`containerd/containerd@b0a37b632b22993f9a85ea7583b8ae0102d3d4a2`。[cmd/containerd-shim-runc-v2/task/service.go:818-841](https://github.com/containerd/containerd/blob/b0a37b632b22993f9a85ea7583b8ae0102d3d4a2/cmd/containerd-shim-runc-v2/task/service.go#L818-L841)。

> Error("post event")

逐次forward。Publish失敗はログ。完全性検証とは異なる。

### O9

本体確認。`containerd/containerd@b0a37b632b22993f9a85ea7583b8ae0102d3d4a2`。[core/runtime/v2/shim_manager.go:286-306](https://github.com/containerd/containerd/blob/b0a37b632b22993f9a85ea7583b8ae0102d3d4a2/core/runtime/v2/shim_manager.go#L286-L306)。

> cleanupAfterDeadShim

shim切断を検出しcleanup。

### O10

本体確認。`containerd/containerd@b0a37b632b22993f9a85ea7583b8ae0102d3d4a2`。[core/runtime/v2/shim_manager.go:422-460](https://github.com/containerd/containerd/blob/b0a37b632b22993f9a85ea7583b8ae0102d3d4a2/core/runtime/v2/shim_manager.go#L422-L460)。

> shimbinary.BinaryName(runtime)

runtime名からshim実行ファイルを解決。追加時に分岐コード編集を必須にしない。

### O11

本体確認。`containerd/containerd@b0a37b632b22993f9a85ea7583b8ae0102d3d4a2`。[docs/runtime-v2.md:290-309](https://github.com/containerd/containerd/blob/b0a37b632b22993f9a85ea7583b8ae0102d3d4a2/docs/runtime-v2.md#L290-L309)。

> google.protobuf.Any features = 4;

機械可読infoはSHOULD。host level設定はshim固有。

### O12

本体確認。`containerd/containerd@b0a37b632b22993f9a85ea7583b8ae0102d3d4a2`。[docs/runtime-v2.md:84-98](https://github.com/containerd/containerd/blob/b0a37b632b22993f9a85ea7583b8ae0102d3d4a2/docs/runtime-v2.md#L84-L98)。

> one-to-many

shimとcontainerの多重度はshimが選ぶ。

## Erlang/OTP

### E1

本体確認。`erlang/otp@10078218203aa3ac90175c547fb4e7c91a33677c`。[system/doc/design_principles/sup_princ.md:26-34](https://github.com/erlang/otp/blob/10078218203aa3ac90175c547fb4e7c91a33677c/system/doc/design_principles/sup_princ.md#L26-L34)。

> processes alive by restarting them when necessary.

監督の対象は子プロセスの生存。

### E2

本体確認。`erlang/otp@10078218203aa3ac90175c547fb4e7c91a33677c`。[lib/stdlib/src/gen_server.erl:136-149](https://github.com/erlang/otp/blob/10078218203aa3ac90175c547fb4e7c91a33677c/lib/stdlib/src/gen_server.erl#L136-L149)。

> {reply, Reply, State}

コールバック契約の戻り値形。Replyの業務種別を固定しない。

### E3

本体確認。`erlang/otp@10078218203aa3ac90175c547fb4e7c91a33677c`。[lib/stdlib/src/gen_server.erl:2552-2569](https://github.com/erlang/otp/blob/10078218203aa3ac90175c547fb4e7c91a33677c/lib/stdlib/src/gen_server.erl#L2552-L2569)。

> {bad_return_value, BadReturn}

不正な外形戻り値でterminate。

### E4

本体確認。`erlang/otp@10078218203aa3ac90175c547fb4e7c91a33677c`。[lib/stdlib/src/supervisor.erl:1287-1293](https://github.com/erlang/otp/blob/10078218203aa3ac90175c547fb4e7c91a33677c/lib/stdlib/src/supervisor.erl#L1287-L1293)。

> handle_info({'EXIT', Pid, Reason}, State)

EXITをrestart_childへ渡す。

### E5

本体確認。`erlang/otp@10078218203aa3ac90175c547fb4e7c91a33677c`。[lib/stdlib/src/supervisor.erl:1472-1491](https://github.com/erlang/otp/blob/10078218203aa3ac90175c547fb4e7c91a33677c/lib/stdlib/src/supervisor.erl#L1472-L1491)。

> reached_max_restart_intensity

再起動回数制限超過でshutdown。

### E6

本体確認。`erlang/otp@10078218203aa3ac90175c547fb4e7c91a33677c`。[lib/stdlib/src/supervisor_bridge.erl:24-35](https://github.com/erlang/otp/blob/10078218203aa3ac90175c547fb4e7c91a33677c/lib/stdlib/src/supervisor_bridge.erl#L24-L35)。

> subsystem not designed according to the OTP design principles

非OTP subsystemを監督へ接続する定義。

### E7

本体確認。`erlang/otp@10078218203aa3ac90175c547fb4e7c91a33677c`。[lib/stdlib/src/supervisor_bridge.erl:181-190](https://github.com/erlang/otp/blob/10078218203aa3ac90175c547fb4e7c91a33677c/lib/stdlib/src/supervisor_bridge.erl#L181-L190)。

> link(Pid)

callbackが返したPidをlink。

### E8

本体確認。`erlang/otp@10078218203aa3ac90175c547fb4e7c91a33677c`。[lib/stdlib/src/supervisor_bridge.erl:211-224](https://github.com/erlang/otp/blob/10078218203aa3ac90175c547fb4e7c91a33677c/lib/stdlib/src/supervisor_bridge.erl#L211-L224)。

> {stop, Reason, State#state{pid = undefined}}

該当Pid終了はbridge終了。他のメッセージはnoreply。

## ACP仕様・SDK・3実装

### C1

本体確認。`agentclientprotocol/agent-client-protocol@f0a04b2172614ca37f2fecf2a2d877a063b37e5f`。[docs/protocol/v1/transports.mdx:20-28](https://github.com/agentclientprotocol/agent-client-protocol/blob/f0a04b2172614ca37f2fecf2a2d877a063b37e5f/docs/protocol/v1/transports.mdx#L20-L28)。

> not a valid ACP message

stdoutへのACP以外の書き込み禁止。

### C2

本体確認。`agentclientprotocol/agent-client-protocol@f0a04b2172614ca37f2fecf2a2d877a063b37e5f`。[docs/protocol/v1/prompt-turn.mdx:171-184](https://github.com/agentclientprotocol/agent-client-protocol/blob/f0a04b2172614ca37f2fecf2a2d877a063b37e5f/docs/protocol/v1/prompt-turn.mdx#L171-L184)。

> these are also reported immediately

モデルが求めたtool callの即時報告。

### C3

本体確認。`agentclientprotocol/agent-client-protocol@f0a04b2172614ca37f2fecf2a2d877a063b37e5f`。[docs/protocol/v1/initialization.mdx:188-206](https://github.com/agentclientprotocol/agent-client-protocol/blob/f0a04b2172614ca37f2fecf2a2d877a063b37e5f/docs/protocol/v1/initialization.mdx#L188-L206)。

> all Agents **MUST** support

text/resource_linkが基準、他は宣言で有効化。loadSessionも宣言。

### C4

本体確認。`agentclientprotocol/typescript-sdk@f7941e753be6c809230307c7cf8b4f9ee220018c`。[src/acp.ts:1069-1082](https://github.com/agentclientprotocol/typescript-sdk/blob/f7941e753be6c809230307c7cf8b4f9ee220018c/src/acp.ts#L1069-L1082)。

> return parser.parse(params);

params検査の実際の呼び出し。

### C5

本体確認。`agentclientprotocol/typescript-sdk@f7941e753be6c809230307c7cf8b4f9ee220018c`。[src/acp.ts:1137-1151](https://github.com/agentclientprotocol/typescript-sdk/blob/f7941e753be6c809230307c7cf8b4f9ee220018c/src/acp.ts#L1137-L1151)。

> (params) => parseParams(spec.params, params)

通知ハンドラ登録から検査へ接続。

### C6

本体確認。`agentclientprotocol/typescript-sdk@f7941e753be6c809230307c7cf8b4f9ee220018c`。[src/acp.ts:1390-1395](https://github.com/agentclientprotocol/typescript-sdk/blob/f7941e753be6c809230307c7cf8b4f9ee220018c/src/acp.ts#L1390-L1395)。

> validate.zSessionNotification

session/updateに選ばれるスキーマ。

### C7

本体確認。`agentclientprotocol/typescript-sdk@f7941e753be6c809230307c7cf8b4f9ee220018c`。[src/schema/zod.gen.ts:2848-2929](https://github.com/agentclientprotocol/typescript-sdk/blob/f7941e753be6c809230307c7cf8b4f9ee220018c/src/schema/zod.gen.ts#L2848-L2929)。

> sessionUpdate: z.literal("tool_call_update")

sessionUpdateはこの版の有限union。未知タグを受けるcatch-all無し。

### C8

本体確認。`agentclientprotocol/typescript-sdk@f7941e753be6c809230307c7cf8b4f9ee220018c`。[src/schema/zod.gen.ts:2385-2414](https://github.com/agentclientprotocol/typescript-sdk/blob/f7941e753be6c809230307c7cf8b4f9ee220018c/src/schema/zod.gen.ts#L2385-L2414)。

> vecSkipError(zToolCallContent)

tool_callのcontentでは不正要素を除去する。すべて拒否するわけではない。

### C9

本体確認。`agentclientprotocol/typescript-sdk@f7941e753be6c809230307c7cf8b4f9ee220018c`。[src/schema-deserialize.ts:115-123](https://github.com/agentclientprotocol/typescript-sdk/blob/f7941e753be6c809230307c7cf8b4f9ee220018c/src/schema-deserialize.ts#L115-L123)。

> items.filter((item) => item !== skippedItem)

不正配列要素を消す実体。

### C10

本体確認。`agentclientprotocol/typescript-sdk@f7941e753be6c809230307c7cf8b4f9ee220018c`。[src/jsonrpc.ts:1416-1435](https://github.com/agentclientprotocol/typescript-sdk/blob/f7941e753be6c809230307c7cf8b4f9ee220018c/src/jsonrpc.ts#L1416-L1435)。

> "Error handling notification"

通知検査例外はconsole.error。受信handlerには到達しないが全接続停止ではない。

### C11

本体確認。`agentclientprotocol/typescript-sdk@f7941e753be6c809230307c7cf8b4f9ee220018c`。[src/acp.ts:2711-2717](https://github.com/agentclientprotocol/typescript-sdk/blob/f7941e753be6c809230307c7cf8b4f9ee220018c/src/acp.ts#L2711-L2717)。

> return this.connection.sendNotification(

送信メソッドには受信と同等のparseが無い。

### C12

本体確認。`agentclientprotocol/claude-agent-acp@d421f56a6c43cde16d9a7531d08a750a5ef2f04a`。[src/acp-agent.ts:5923-5948](https://github.com/agentclientprotocol/claude-agent-acp/blob/d421f56a6c43cde16d9a7531d08a750a5ef2f04a/src/acp-agent.ts#L5923-L5948)。

> sessionUpdate: "tool_call_update"

Claude SDK eventからACP通知を構成。

### C13

本体確認。`agentclientprotocol/claude-agent-acp@d421f56a6c43cde16d9a7531d08a750a5ef2f04a`。[src/acp-agent.ts:5988-6000](https://github.com/agentclientprotocol/claude-agent-acp/blob/d421f56a6c43cde16d9a7531d08a750a5ef2f04a/src/acp-agent.ts#L5988-L6000)。

> unreachable(message, this.logger);

未知メッセージはunreachableへ。

### C14

本体確認。`agentclientprotocol/claude-agent-acp@d421f56a6c43cde16d9a7531d08a750a5ef2f04a`。[src/utils.ts:77-85](https://github.com/agentclientprotocol/claude-agent-acp/blob/d421f56a6c43cde16d9a7531d08a750a5ef2f04a/src/utils.ts#L77-L85)。

> logger.error(`Unexpected case: ${valueAsString}`);

unreachableは例外を投げずログ。

### C15

本体確認。`agentclientprotocol/codex-acp@d7b07c1b44a28890cdf3d5450f8974a812db5ae2`。[src/CodexEventHandler.ts:512-534](https://github.com/agentclientprotocol/codex-acp/blob/d7b07c1b44a28890cdf3d5450f8974a812db5ae2/src/CodexEventHandler.ts#L512-L534)。

> case "item/agentMessage/delta":

app-server通知をACPへ写す分岐。

### C16

本体確認。`agentclientprotocol/codex-acp@d7b07c1b44a28890cdf3d5450f8974a812db5ae2`。[src/CodexEventHandler.ts:684-697](https://github.com/agentclientprotocol/codex-acp/blob/d7b07c1b44a28890cdf3d5450f8974a812db5ae2/src/CodexEventHandler.ts#L684-L697)。

> case "process/exited":

既知通知にもreturn nullの枝がある。全原始eventの忠実な複製ではない。

### C17

本体確認。`google-gemini/gemini-cli@cfbcaa8df13ea4610bb379b377b56d62980c0032`。[packages/cli/src/acp/acpSession.ts:411-446](https://github.com/google-gemini/gemini-cli/blob/cfbcaa8df13ea4610bb379b377b56d62980c0032/packages/cli/src/acp/acpSession.ts#L411-L446)。

> sessionUpdate: 'agent_thought_chunk'

CLI内部のstreamをACPへ変換。Gemini API単体のラッパーではない。

### C18

本体確認。`google-gemini/gemini-cli@cfbcaa8df13ea4610bb379b377b56d62980c0032`。[packages/cli/src/acp/acpSession.ts:469-485](https://github.com/google-gemini/gemini-cli/blob/cfbcaa8df13ea4610bb379b377b56d62980c0032/packages/cli/src/acp/acpSession.ts#L469-L485)。

> default:
>               break;

列挙外イベントの既定分岐は何も返さない。

### C19

本体確認。`agentclientprotocol/typescript-sdk@f7941e753be6c809230307c7cf8b4f9ee220018c`。[src/schema/zod.gen.ts:260-286](https://github.com/agentclientprotocol/typescript-sdk/blob/f7941e753be6c809230307c7cf8b4f9ee220018c/src/schema/zod.gen.ts#L260-L286)。

> type: z.literal("text")

ContentBlockは有限union。意味内容は検査しない。

### C20

本体確認。`agentclientprotocol/typescript-sdk@f7941e753be6c809230307c7cf8b4f9ee220018c`。[src/schema/zod.gen.ts:3636-3642](https://github.com/agentclientprotocol/typescript-sdk/blob/f7941e753be6c809230307c7cf8b4f9ee220018c/src/schema/zod.gen.ts#L3636-L3642)。

> prompt: z.array(zContentBlock)

入力promptは通常arrayで検査する。

### C21

本体確認。`agentclientprotocol/claude-agent-acp@d421f56a6c43cde16d9a7531d08a750a5ef2f04a`。[package.json:65-72](https://github.com/agentclientprotocol/claude-agent-acp/blob/d421f56a6c43cde16d9a7531d08a750a5ef2f04a/package.json#L65-L72)。

> "@agentclientprotocol/sdk": "1.4.0"

調査SDKの版と一致。

### C22

本体確認。`agentclientprotocol/codex-acp@d7b07c1b44a28890cdf3d5450f8974a812db5ae2`。[package.json:64-72](https://github.com/agentclientprotocol/codex-acp/blob/d7b07c1b44a28890cdf3d5450f8974a812db5ae2/package.json#L64-L72)。

> "@agentclientprotocol/sdk": "^1.4.0"

依存範囲。本調査は1.4.0実装を確認し全インストール状態を保証しない。

### C23

本体確認。`google-gemini/gemini-cli@cfbcaa8df13ea4610bb379b377b56d62980c0032`。[packages/cli/package.json:30-36](https://github.com/google-gemini/gemini-cli/blob/cfbcaa8df13ea4610bb379b377b56d62980c0032/packages/cli/package.json#L30-L36)。

> "@agentclientprotocol/sdk": "0.16.1"

Gemini native側のSDKは別版。1.4.0の検査をそのまま帰属させない。

### C24

本体確認。`agentclientprotocol/typescript-sdk@f7941e753be6c809230307c7cf8b4f9ee220018c`。[src/schema/zod.gen.ts:2693-2716](https://github.com/agentclientprotocol/typescript-sdk/blob/f7941e753be6c809230307c7cf8b4f9ee220018c/src/schema/zod.gen.ts#L2693-L2716)。

> cost: defaultOnError

使用費用のeventはあるが能力の事前宣言と同じではない。

## Language Server Protocol

### L1

本体確認。`microsoft/language-server-protocol@c2f3a1abfb613de5d55271f0d07ff103068b0d04`。[_specifications/lsp/3.17/specification.md:414-418](https://github.com/microsoft/language-server-protocol/blob/c2f3a1abfb613de5d55271f0d07ff103068b0d04/_specifications/lsp/3.17/specification.md#L414-L418)。

> The set of capabilities is exchanged

initializeで双方の能力を交換する仕様。

### L2

本体確認。`microsoft/vscode-languageserver-node@87f58727b5d287ef9049fb0b4b52984a6e62d604`。[client/src/common/hover.ts:34-49](https://github.com/microsoft/vscode-languageserver-node/blob/87f58727b5d287ef9049fb0b4b52984a6e62d604/client/src/common/hover.ts#L34-L49)。

> capabilities.hoverProvider

hover提供宣言がなければ登録しない。

### L3

本体確認。`microsoft/vscode-languageserver-node@87f58727b5d287ef9049fb0b4b52984a6e62d604`。[jsonrpc/src/common/messageReader.ts:224-237](https://github.com/microsoft/vscode-languageserver-node/blob/87f58727b5d287ef9049fb0b4b52984a6e62d604/jsonrpc/src/common/messageReader.ts#L224-L237)。

> Header must provide a Content-Length property.

フレーム境界不正を検出。

### L4

本体確認。`microsoft/vscode-languageserver-node@87f58727b5d287ef9049fb0b4b52984a6e62d604`。[jsonrpc/src/common/messages.ts:505-529](https://github.com/microsoft/vscode-languageserver-node/blob/87f58727b5d287ef9049fb0b4b52984a6e62d604/jsonrpc/src/common/messages.ts#L505-L529)。

> is.string(candidate.method)

request/notification/responseの外形識別。payload全体検査ではない。

### L5

本体確認。`microsoft/vscode-languageserver-node@87f58727b5d287ef9049fb0b4b52984a6e62d604`。[jsonrpc/src/common/connection.ts:882-901](https://github.com/microsoft/vscode-languageserver-node/blob/87f58727b5d287ef9049fb0b4b52984a6e62d604/jsonrpc/src/common/connection.ts#L882-L901)。

> ErrorCodes.MethodNotFound

未知request methodはエラー。

## POSIX・Linux

### P1

本体確認。`torvalds/linux@518e5b794c06c0f0eb40df3e202274a66202c137`。[fs/pipe.c:396-438](https://github.com/torvalds/linux/blob/518e5b794c06c0f0eb40df3e202274a66202c137/fs/pipe.c#L396-L438)。

> struct pipe_buffer *buf = pipe_buf(pipe, tail);

通常pipeのreadはtailからバイトを読む。

### P2

本体確認。`torvalds/linux@518e5b794c06c0f0eb40df3e202274a66202c137`。[fs/pipe.c:432-448](https://github.com/torvalds/linux/blob/518e5b794c06c0f0eb40df3e202274a66202c137/fs/pipe.c#L432-L448)。

> tail = pipe_update_tail(pipe, buf, tail);

読み切ったbufferのtailを進める。

### P3

本体確認。`torvalds/linux@518e5b794c06c0f0eb40df3e202274a66202c137`。[kernel/exit.c:1313-1327](https://github.com/torvalds/linux/blob/518e5b794c06c0f0eb40df3e202274a66202c137/kernel/exit.c#L1313-L1327)。

> infop->cause = CLD_EXITED;

wait結果を終了種別とstatusへ変換。

### P4

本体確認。[一次資料](https://pubs.opengroup.org/onlinepubs/9799919799/functions/pipe.html)。版: POSIX.1-2024 / Issue 8。取得HTML `posix-pipe.html:39-47`。commit SHA: 対象なし。SHA-256: `d8425cee340fdacb4f8b3db37a7ed1bced59e9b8227aed4a0cff387ced8d81f4`。

> on a first-in-first-out basis

pipe両端とFIFO。

### P5

本体確認。[一次資料](https://pubs.opengroup.org/onlinepubs/9799919799/functions/wait.html)。版: POSIX.1-2024 / Issue 8。取得HTML `posix-wait.html:41-52`。commit SHA: 対象なし。SHA-256: `8c9d5d9bf54b098e460832d466503567376fdd61d24cbef0d461389d113a36e5`。

> shall obtain status information

waitは子プロセスの状態を取得。成果の種別ではない。

### P6

本体確認。[一次資料](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap03.html)。版: POSIX.1-2024 / Issue 8。取得HTML `posix-definitions.html:802-807`。commit SHA: 対象なし。SHA-256: `0037b423cc292c3cd7c55d347a2273407d156be2a161e56771b08c1c0d421d5a`。

> The values 0, 1, and 2

stdin/stdout/stderrのfd。

## binary session types

### B1

本体確認。`Munksgaard/session-types@86d45aec3c1700f189e69ba7fc580c6938c9cc50`。[src/lib.rs:130-157](https://github.com/Munksgaard/session-types/blob/86d45aec3c1700f189e69ba7fc580c6938c9cc50/src/lib.rs#L130-L157)。

> type Dual = Recv<A, P::Dual>;

Send/RecvとChoose/Offerの双対を定義。

### B2

本体確認。`Munksgaard/session-types@86d45aec3c1700f189e69ba7fc580c6938c9cc50`。[src/lib.rs:209-229](https://github.com/Munksgaard/session-types/blob/86d45aec3c1700f189e69ba7fc580c6938c9cc50/src/lib.rs#L209-L229)。

> pub fn send(self, v: A)

送信で元channelを消費し次状態を返す。

### B3

本体確認。`Munksgaard/session-types@86d45aec3c1700f189e69ba7fc580c6938c9cc50`。[src/lib.rs:479-488](https://github.com/Munksgaard/session-types/blob/86d45aec3c1700f189e69ba7fc580c6938c9cc50/src/lib.rs#L479-L488)。

> (Chan<(), P>, Chan<(), P::Dual>)

channel構築で双対の両端を一組で作る。

### B4

本体確認。`Munksgaard/session-types@86d45aec3c1700f189e69ba7fc580c6938c9cc50`。[src/lib.rs:176-180](https://github.com/Munksgaard/session-types/blob/86d45aec3c1700f189e69ba7fc580c6938c9cc50/src/lib.rs#L176-L180)。

> prematurely dropped

未終端channelのDropはpanic。生存中の欠落event検査ではない。

### B5

本体確認。[一次資料](https://munksgaard.me/papers/laumann-munksgaard-larsen.pdf)。版: Jespersen, Munksgaard, Larsen, WGP 2015, author PDF (10 pages)。PDF物理1頁。commit SHA: 対象なし。SHA-256: `510fd2a75f372388756c4038967149954130c7a5972ec0832e41ef4a97d55197`。

> no run-time checks to ensure protocol safety

型付きDSL内でのprotocol safetyを対象としランタイム全般を監視しない。

### B6

本体確認。[一次資料](https://munksgaard.me/papers/laumann-munksgaard-larsen.pdf)。版: same author PDF, §6.2–6.3。PDF物理9頁。commit SHA: 対象なし。SHA-256: `510fd2a75f372388756c4038967149954130c7a5972ec0832e41ef4a97d55197`。

> We will not give a formal proof for our claims

§6.2の留保。§6.3は早期dropとaffineの限界。

## adapter・Wrapper Facade

### F1

本体確認。[一次資料](https://arxiv.org/pdf/1504.07504v2)。版: arXiv:1504.07504v2, 2015-05-04, 8 pages。PDF物理1頁。commit SHA: 対象なし。SHA-256: `c546aeb4e3c2e279e7086b5dc8ec68313b3df2b4acc951b64e1018a56dd52d41`。

> coordinator which avoids incompatible interactions

LTSとdesired behaviorのモデルからcoordinatorを合成。実装の強制箇所未取得。

### F2

本体確認。[一次資料](https://www.dre.vanderbilt.edu/~schmidt/PDF/wrapper-facade.pdf)。版: Douglas C. Schmidt, C++ Report, February 1999, 10 pages。PDF物理1頁。commit SHA: 対象なし。SHA-256: `432f90c803944567a63f2fcacde62794a24513e45d3a7a5f6726580d7bd11002`。

> Encapsulate low-level functions and data structures within

§2.1 Intent。class interfaceへの包み替えというパターン。trace完全性の不変量ではない。

## 取得失敗と未発見の記録

1. `http://www.di.univaq.it/tivoli/SYNTHESIS/synthesis.html`: HTTP 404。F1が記す配布先。実装ソースの強制箇所を引用できず、抽象のみとして扱う。
2. `https://www.di.univaq.it/tivoli/SYNTHESIS/synthesis.html`: 接続拒否、HTTP応答なし（Errno 61）。
3. OTP `system/doc/design_principles/des_princ.md`（R4のSHA）: HTTP 404。現存する`gen_server_concepts.md`、`sup_princ.md`、実装の文書部分を取得して代替。
4. `https://arxiv.org/pdf/1504.07504v2`はweb表示ツールで内部エラーになったが、直接取得ではHTTP 200で、版なしURLの取得物とSHA-256が一致した。資料内容は取得済み。
5. `https://munksgaard.me/papers/laumann-munksgaard-larsen.pdf`のweb screenshotはcache missで失敗した。PDF本体と文字層は直接取得でき、HTTP 200とSHA-256を記録した。

追加の探索資料として`https://arxiv.org/pdf/1412.0527`もHTTP 200で取得して全文を検索した（SHA-256 `48805b268d3809243d2ffc988aeab87cfc2ef2c6dd612f4878eb676bfc57a2d5`）。本文でその主張を独立に引用していないため対として重複計上しない。検索語と未発見の範囲は本文8節に記録した。

## 再取得用台帳

本調査時の一時ディレクトリは`/private/tmp/pda-research-03/`。`manifest.json`は固定コミットの引用、`manifest-html.json`はPOSIX、`manifest-pdf.json`は論文のURL・取得版・引用位置・短い原文・ハッシュを持つ。これらは再照合の補助ファイルであり、恒久的な根拠は上記のURL・SHA・path:line・版情報である。
