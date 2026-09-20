# LLMエージェント時代の実装調査 (一次資料)

作業ディレクトリ: `$WT/tmp/research-core-2026-09-20/`
すべてのファイルパスは `$WT = /Users/fox4foofighter/dev/pda/.claude/worktrees/fable-phase-detection-skill-a20ef7` からの絶対パス。

## 取得状況サマリ

| 対象 | 取得方法 | HTTP/結果 | ローカルパス | commit SHA |
|---|---|---|---|---|
| A2A | `git clone --bare --depth 1` | 成功 (通常clone失敗→bare clone成功、後述) | `_src/A2A.git` (bare) / `_src/A2A-src` (archive展開) | `afda8316c64951a2ecb2a0d3d10867405d2b4095` |
| MCP | 同上 | 成功 | `_src/MCP.git` / `_src/MCP-src` | `24efd6e7cbd7a074e6b3b781eb370891df40afad` |
| MetaGPT | 同上 | 成功 | `_src/MetaGPT.git` / `_src/MetaGPT-src` | `11cdf466d042aece04fc6cfd13b28e1a70341b1f` |
| AutoGen | 同上 | 成功 | `_src/autogen.git` / `_src/autogen-src` | `027ecf0a379bcc1d09956d46d12d44a3ad9cee14` |
| LangGraph | 同上 | 成功 | `_src/langgraph.git` / `_src/langgraph-src` | `aa742fb31e2827d569b843e3600aeda2e0528e4b` |
| OpenAI Agents SDK | 同上 | 成功 | `_src/openai-agents-python.git` / `_src/openai-agents-python-src` | `165390cff0a6a8b0094c396418e6ed7fb9471398` |
| サーベイ1 | `curl -sL` | HTTP 200 | `_src/arxiv_2505.02279.pdf` (+ 抽出テキスト `.txt`) | — (論文、SHA無し) |
| サーベイ2 | `curl -sL` | HTTP 200 | `_src/arxiv_2504.16736.pdf` (+ 抽出テキスト `.txt`) | — (論文、SHA無し) |

### 取得時の障害と回避方法 (作業記録として残す。証拠性に関わるため明記)

通常の `git clone --depth 1 <url> <dir>` は全対象で失敗した。エラー:
```
fatal: cannot copy '/opt/homebrew/opt/git/share/git-core/templates/hooks/commit-msg.sample' to '.../<dir>/.git/hooks/commit-msg.sample': Operation not permitted
```
このサンドボックスは隠しディレクトリ `.git/`（先頭ドットの非表示ディレクトリ）への書き込みを拒否する。`ponyc-bare.git` のように名前が `.git` サフィックスで終わる非表示でないディレクトリへの書き込みは許可される。そのため全対象を `git clone --bare --depth 1 <url> <name>.git` で取得し、`git --git-dir=<name>.git archive HEAD | tar -x -C <name>-src/` でファイル一式を展開した（`.vscode/` 配下のみ同じ理由で展開失敗、調査対象外なので無視）。各リポジトリのcommit SHAは `git --git-dir=<name>.git rev-parse HEAD` で取得し上表に記載。

PDF取得は `curl -sL -o ... https://arxiv.org/pdf/<id>` が最初 `dangerouslyDisableSandbox` なしでネットワーク拒否 (`deny network-outbound arxiv.org:443`) となったため、`allowed_domains: ["arxiv.org"]` を付けて再実行し成功 (HTTP 200)。PDFはpypdf (venv `$TMPDIR/pdfenv`, PyPI経由でインストール) でテキスト抽出し、逐語引用はテキスト抽出結果から行った (WebFetchは要約のみなので使用していない)。

---

## 1. A2A (Agent2Agent)

リポジトリ: `_src/A2A-src` (bare: `_src/A2A.git`, HEAD `afda8316c64951a2ecb2a0d3d10867405d2b4095`)

**重要な発見**: 依頼文は `specification/json/a2a.json` の存在を前提としていたが、現在のHEADではJSON Schemaは非正本のビルド成果物になっており、コミットされていない。正本は Protocol Buffers 定義 `specification/a2a.proto` である。根拠 (`_src/A2A-src/specification/json/README.md`):

> "`a2a.json` is a non-normative build artifact derived from the canonical proto definition at `specification/a2a.proto`. It is generated during builds and intentionally not committed to source control."

以降はすべて `_src/A2A-src/specification/a2a.proto` (812行) を一次資料として引用する。

### (a) 仕事と成果を表すメッセージ型の定義箇所

- `Message` (仕事/対話の単位): `specification/a2a.proto:260-277`
  ```
  260:message Message {
  261-  string message_id = 1 ...
  264-  string context_id = 2;
  266-  string task_id = 3;
  268-  Role role = 4 ...
  270-  repeated Part parts = 5 ...
  ```
- `Artifact` (成果物): `specification/a2a.proto:279-293`
  ```
  279:// Artifacts represent task outputs.
  280:message Artifact {
  281-  string artifact_id = 1 ...
  288-  repeated Part parts = 4 [(google.api.field_behavior) = REQUIRED];
  ```
- `Task` (仕事と成果をまとめる永続単位): `specification/a2a.proto:167-184`
  ```
  167:message Task {
  170-  string id = 1 ...
  175-  TaskStatus status = 3 ...
  177-  repeated Artifact artifacts = 4;
  180-  repeated Message history = 5;
  ```

### (b) 種別の有限enum

`TaskState` enum、全値を列挙 (`specification/a2a.proto:187-208`):
```
187:enum TaskState {
189-  TASK_STATE_UNSPECIFIED = 0;
191-  TASK_STATE_SUBMITTED = 1;
193-  TASK_STATE_WORKING = 2;
195-  TASK_STATE_COMPLETED = 3;   // "This is a terminal state."
197-  TASK_STATE_FAILED = 4;     // terminal
199-  TASK_STATE_CANCELED = 5;   // terminal
201-  TASK_STATE_INPUT_REQUIRED = 6; // "interrupted state"
205-  TASK_STATE_REJECTED = 7;   // terminal
207-  TASK_STATE_AUTH_REQUIRED = 8;  // "interrupted state"
208:}
```
9値。ただし「terminal」「interrupted」の区別はコメント上の記述のみで、`.proto` 定義自体には遷移合法性を強制する仕組みはない（enumは単なる整数ラベルであり、`TASK_STATE_COMPLETED` から `TASK_STATE_WORKING` に戻す代入を型レベルで禁止する機構は無い）。

`Role` enum (`specification/a2a.proto:245-252`): `ROLE_UNSPECIFIED=0, ROLE_USER=1, ROLE_AGENT=2`。

`Part` の union (`oneof`) 定義 (`specification/a2a.proto:224-241`):
```
224:message Part {
225-  oneof content {
227-    string text = 1;
229-    bytes raw = 2;
231-    string url = 3;
233-    google.protobuf.Value data = 4;
234-  }
236-  google.protobuf.Struct metadata = 5;
238-  string filename = 6;
241-  string media_type = 7;
242:}
```
`Message.parts` (`a2a.proto:270`: `repeated Part parts = 5`) と `Artifact.parts` (`a2a.proto:288`: `repeated Part parts = 4`) は**同一の `Part` 型**を共有している。つまりある実行器が生成した `Artifact.parts` (成果) を、そのまま別の実行器への `Message.parts` (仕事の中身) にコピーして渡すことが型構造上そのまま可能——`Part` に区別用のタグやオリジン (artifact由来かmessage由来か) を持たないフィールドは無く、`repeated Part` という同一のコンテナ型として扱われるため、変換なしで代入できる。根拠: `a2a.proto:270`, `a2a.proto:288`, `a2a.proto:224`。

なお `oneof content` はproto3の意味論上「複数フィールドの同時設定を防ぐ」ものであり「最低1つの設定を強制する」ものではない (proto3のoneof仕様に基づく一般的事実、コード上の追加チェックは本ファイル中に確認できず)。よって「必ずどれか1種類のコンテンツを持つ」という不変量はスキーマだけでは強制されていない。

### (c) 永続ストア

`Task` message自体がプロトコル上のストア定義。`status` (現在状態) + `artifacts` (成果) + `history` (Message列) を1つの永続レコードとして保持する (`a2a.proto:167-184`、上記(a)で引用済み)。

`GetTask` RPCの存在によりタスク保存がプロトコル上要求されている:
```
19:service A2AService {
21-  rpc SendMessage(SendMessageRequest) returns (SendMessageResponse) {
33-  rpc SendStreamingMessage(SendMessageRequest) returns (stream StreamResponse) {
45-  rpc GetTask(GetTaskRequest) returns (Task) {
64-  rpc CancelTask(CancelTaskRequest) returns (Task) {
```
(`specification/a2a.proto:19,21,33,45,64`)。`GetTask` が `Task` を返す設計は、サーバー側が `task_id` をキーにタスクの状態・履歴・成果物を永続化していることを前提にしている(そうでなければ後から取得できない)。

### (d) 順序付きイベントストリーム

`SendStreamingMessage` は `stream StreamResponse` を返す (`a2a.proto:33`)。`StreamResponse` は oneof:
```
791:message StreamResponse {
793-  oneof payload {
795-    Task task = 1;
797-    Message message = 2;
799-    TaskStatusUpdateEvent status_update = 3;
801-    TaskArtifactUpdateEvent artifact_update = 4;
802-  }
803:}
```
イベント型定義:
```
296:message TaskStatusUpdateEvent {
298-  string task_id = 1 ...
300-  string context_id = 2 ...
302-  TaskStatus status = 3 ...
304-  google.protobuf.Struct metadata = 4;
305:}
...
308:message TaskArtifactUpdateEvent {
310-  string task_id = 1 ...
312-  string context_id = 2 ...
314-  Artifact artifact = 3 ...
317-  bool append = 4;   // 部分成果物の追記フラグ
319-  bool last_chunk = 5; // 最終チャンクフラグ
321-  google.protobuf.Struct metadata = 6;
322:}
```
(`specification/a2a.proto:296-305, 308-320`)。gRPC streamはメッセージの到着順序を保証するため、これは「実行中の出来事を順序付きで外へ出す」仕組みに該当する。

### AgentCard (能力の宣言)

`specification/a2a.proto:362-399`:
```
362:message AgentCard {
365-  string name = 1 [(google.api.field_behavior) = REQUIRED];
369-  string description = 2 [(google.api.field_behavior) = REQUIRED];
371-  repeated AgentInterface supported_interfaces = 3 [(google.api.field_behavior) = REQUIRED];
373-  AgentProvider provider = 4;
376-  string version = 5 [(google.api.field_behavior) = REQUIRED];
380-  AgentCapabilities capabilities = 7 [(google.api.field_behavior) = REQUIRED];
382-  map<string, SecurityScheme> security_schemes = 8;
388-  repeated string default_input_modes = 10 [(google.api.field_behavior) = REQUIRED];
390-  repeated string default_output_modes = 11 [(google.api.field_behavior) = REQUIRED];
394-  repeated AgentSkill skills = 12 [(google.api.field_behavior) = REQUIRED];
```
必須(`REQUIRED`)フィールド: `name`, `description`, `supported_interfaces`, `version`, `capabilities`, `default_input_modes`, `default_output_modes`, `skills`。

### 古典的抽象への対応と落ちている不変量 (A2A)

- **最も近い抽象**: `Task` は `task_id` をキーに複数者(クライアント/サーバー、将来的には別エージェント)が `GetTask` で読み出せる共有可変レコードであり、Linda型タプルスペースの「原子的take(読み出しと同時に消費)」ではなく置きっぱなしで何度でも読める点で**blackboard**に近い。同時に `TaskState` enumが明示的な生成/終了状態を列挙している点は**workflow net**のplace集合に近い。両方の性質が混在しており、単一の抽象に還元しない方が正確。
- **落ちている不変量1**: 状態遷移の合法性が型で強制されない。`TaskState` はコメントで「terminal」「interrupted」と書かれているだけで (`a2a.proto:195,197,199,201,205,207`)、`.proto` 定義にはpre/post状態を制約する仕組みが無い。ワークフローネットが本来持つ「不正な遷移は構造上発生しない」という不変量が、ここでは規約(コメント)止まりになっている。
- **落ちている不変量2**: `Part.oneof content` は「複数同時設定の禁止」は守るが「最低1つの設定」を強制しない (proto3の一般的仕様から)。ACT/直和型が本来持つ「必ずどれか1つ」という完全性が型レベルでは保証されていない。
- **推測**: 実際のクライアント/サーバーSDK実装(この`a2a.proto`だけでなく`a2a-python`等)では実行時バリデーションで補っている可能性があるが、本リポジトリの `specification/` 配下にそのバリデーションコードは無く未確認。

---

## 2. MCP (Model Context Protocol)

リポジトリ: `_src/MCP-src` (bare: `_src/MCP.git`, HEAD `24efd6e7cbd7a074e6b3b781eb370891df40afad`)

最新の確定版スキーマ: `schema/2026-07-28/schema.ts` (draft側 `schema/draft/schema.ts:30` の `export const LATEST_PROTOCOL_VERSION = "2026-07-28";` と一致することを確認)。以下すべて `_src/MCP-src/schema/2026-07-28/schema.ts` から引用 (全3197行)。

### (a) メッセージ型定義 (JSON-RPCベース、有限列挙)

```
26:export type JSONRPCMessage =
27-  JSONRPCRequest | JSONRPCNotification | JSONRPCResponse;
```
(`schema/2026-07-28/schema.ts:26-27`)

リクエスト/通知/結果の有限列挙 (`schema/2026-07-28/schema.ts:3153-3197`):
```
3153:export type ClientRequest =
3154-  | DiscoverRequest
3155-  | CompleteRequest
3156-  | GetPromptRequest
3157-  | ListPromptsRequest
3158-  | ListResourcesRequest
3159-  | ListResourceTemplatesRequest
3160-  | ReadResourceRequest
3161-  | SubscriptionsListenRequest
3162-  | CallToolRequest
3163-  | ListToolsRequest;
3166:export type ClientNotification = CancelledNotification;
3169:export type ClientResult = EmptyResult;
3174:export type ServerNotification =
3175-  | CancelledNotification
3176-  | ProgressNotification
3177-  | LoggingMessageNotification
3178-  | ResourceUpdatedNotification
3179-  | ResourceListChangedNotification
3180-  | ToolListChangedNotification
3181-  | PromptListChangedNotification
3182-  | SubscriptionsAcknowledgedNotification;
3185:export type ServerResult =
3186-  | EmptyResult
3187-  | DiscoverResult
3188-  | CompleteResult
3189-  | GetPromptResult
3190-  | ListPromptsResult
3191-  | ListResourceTemplatesResult
3192-  | ListResourcesResult
3193-  | ReadResourceResult
3194-  | SubscriptionsListenResult
3195-  | CallToolResult
3196-  | ListToolsResult
3197-  | InputRequiredResult;
```
TypeScriptの直和型 (union) として有限に閉じている。JSON-RPCの `JSONRPCRequest`/`JSONRPCNotification`/`JSONRPCErrorResponse` のインターフェース定義は `schema/2026-07-28/schema.ts:268, 278, 298`。

### (b) 種別の有限enum判定

上記の通り、リクエスト/通知/結果の種類はTypeScript union型として機械的に有限列挙されている(実装側がこのunionを網羅的にswitchできる)。ただし「有限」なのはプロトコルメソッド名の集合であり、ペイロード内の自由データ (`data: unknown` 等、下記参照) は型で閉じていない。

### (c) 永続ストア

**無い**。`CallToolResult` はリクエストへの同期レスポンスとして即座に返る値であり (`schema/2026-07-28/schema.ts:1809-1821`):
```
1809:export interface CallToolResult extends Result {
1813-  content: ContentBlock[];
1821-  structuredContent?: unknown;
```
スキーマ全文 (3197行) を `task` というキーワードでgrepしても該当する型定義は0件だった (検索: `grep -ni "task\b" schema/2026-07-28/schema.ts` → 0マッチ)。A2Aの `Task`/`GetTask` に相当する「後から結果を取得する」ためのプロトコル上のストアはMCPには規定されていない。ツール呼び出しの結果はその場のJSON-RPCレスポンスの中にしか存在しない。

### Tool宣言 (能力の宣言) と機械可読な強制の有無

`Tool` interface (`schema/2026-07-28/schema.ts:1973-2005`):
```
1973:export interface Tool extends BaseMetadata, Icons {
1979-  description?: string;
1997-  inputSchema: { $schema?: string; type: "object"; [key: string]: unknown };
2005-  outputSchema?: { $schema?: string; [key: string]: unknown };
```
`inputSchema` は型定義上 `type: "object"` を必須にし、それ以外は `[key: string]: unknown` として JSON Schema 2020-12 のキーワードを許容する構造になっている(コメントに "Defaults to JSON Schema 2020-12" と明記、`schema.ts:1995`)。これは「機械可読なスキーマである」ことを型システムが要求している証拠。

**ただし** — このリポジトリ (`modelcontextprotocol/modelcontextprotocol`) は仕様とドキュメントのみで、`inputSchema` を実際に検査(バリデーション)する実装コードは含まれていない。`find` で `tools/`, `plugins/`, `scripts/` を確認したが、JSON Schemaバリデータ(ajv等)や実行時チェックのコードは存在しなかった(該当なしを確認: `grep -rn "ajv\|json-schema\|jsonschema\|zod" schema/2026-07-28/schema.ts` → 0マッチ、かつリポジトリ構成自体に実装用ディレクトリ (`src/`, `sdk/`) が無い)。つまり「機械可読なスキーマであることは型で要求されているが、それを検査する実装コードはこのリポジトリの外(各言語SDK)にある」というのが正確な言い方であり、本リポジトリ内では「強制している」とは言えない。

### 進捗/ログ通知

`ProgressNotification` (`schema/2026-07-28/schema.ts:1009-1042`):
```
1009:export interface ProgressNotificationParams extends NotificationParams {
1013-  progressToken: ProgressToken;
1019-  progress: number;
1025-  total?: number;
1029-  message?: string;
1040:export interface ProgressNotification extends JSONRPCNotification {
1041-  method: "notifications/progress";
1042-  params: ProgressNotificationParams;
```
`LoggingMessageNotification` (`schema/2026-07-28/schema.ts:2031-2060`, **2026-07-28時点でdeprecated (SEP-2577)**):
```
2031:export interface LoggingMessageNotificationParams extends NotificationParams {
2035-  level: LoggingLevel;
2039-  logger?: string;
2043-  data: unknown;
2058:export interface LoggingMessageNotification extends JSONRPCNotification {
2059-  method: "notifications/message";
2060-  params: LoggingMessageNotificationParams;
```
`LoggingLevel` の有限enum (`schema/2026-07-28/schema.ts:2075-2084`、こちらもdeprecated):
```
2075:export type LoggingLevel =
2076-  | "debug"
2077-  | "info"
2078-  | "notice"
2079-  | "warning"
2080-  | "error"
2081-  | "critical"
2082-  | "alert"
2083-  | "emergency";
```
8値、有限。イベント種別(通知メソッド名)自体は `ServerNotification` unionで有限 (前掲(a))。ただし通知の`data: unknown` (ログの中身) は型で閉じていない。

### 古典的抽象への対応と落ちている不変量 (MCP)

- **最も近い抽象**: 状態を持たないRPC(Actor的というより古典的クライアント/サーバーRPC、ACLでいう単純なrequest–replyに近い)。`ClientRequest`/`ServerResult` unionは閉じているという点でFIPA ACLの「有限なperformative集合」に似ているが、MCPの場合それは会話行為の種類ではなく単なるメソッドディスパッチ表であり、話者の意図(inform/request/agree等)を区別する概念はない。
- **落ちている不変量**: 「仕事の結果を後から取り出す」ための永続ストアが無い(上記(c))。したがってタスクの再開・監査・ポーリングによる進捗確認はプロトコルの外(実装依存)になる。これはA2Aの`Task`/`GetTask`と対照的な、意図的な設計上のシンプルさ(ステートレスなツール呼び出し)である。

---

## 3. MetaGPT

リポジトリ: `_src/MetaGPT-src` (bare: `_src/MetaGPT.git`, HEAD `11cdf466d042aece04fc6cfd13b28e1a70341b1f`)

### (a) `Message` クラス定義 (`metagpt/schema.py:232-243`)

```
232:class Message(BaseModel):
233-    """list[<role>: <content>]"""
234-
235-    id: str = Field(default="", validate_default=True)
236-    content: str  # natural language for user or agent
237-    instruct_content: Optional[BaseModel] = Field(default=None, validate_default=True)
238-    role: str = "user"  # system / user / assistant
239-    cause_by: str = Field(default="", validate_default=True)
240-    sent_from: str = Field(default="", validate_default=True)
241-    send_to: set[str] = Field(default={MESSAGE_ROUTE_TO_ALL}, validate_default=True)
242-    metadata: Dict[str, Any] = Field(default_factory=dict)
```
`MESSAGE_ROUTE_TO_ALL = "<all>"` (`metagpt/const.py:81`)。

`cause_by` を文字列化するvalidator (`metagpt/schema.py:266-269`):
```
266:    @field_validator("cause_by", mode="before")
267-    @classmethod
268-    def check_cause_by(cls, cause_by: Any) -> str:
269-        return any_to_str(cause_by if cause_by else import_class("UserRequirement", "metagpt.actions.add_requirement"))
```

### (b) 種別の有限enum判定 → **していない (規約止まり)**

`role: str` (`schema.py:238`, コメントで "system / user / assistant" と書かれているだけで型はただの `str`)、`cause_by: str` (`schema.py:239`、任意のAction/クラスを文字列化して格納。`Enum`ではない)、`send_to: set[str]` (`schema.py:241`、任意文字列の集合)。いずれも Pydanticの `Enum` 型やリテラル型ではなく `str`/`set[str]` であり、Pythonの型システムはこれらの値を有限集合に制限しない。「種別が有限のenumとして機械的に分類可能か」という問いには**否**と答えられる、コード上の事実(フィールド型が `str`)に基づく判定。

### (c) 永続ストア

`MessageQueue` (per-role受信バッファ、`metagpt/schema.py:713-730`):
```
713:class MessageQueue(BaseModel):
714-    """Message queue which supports asynchronous updates."""
718-    _queue: Queue = PrivateAttr(default_factory=Queue)
720-    def pop(self) -> Message | None:
730-    def pop_all(self) -> List[Message]:
```
Environment側の累積履歴 (`metagpt/environment/base_env.py:193`、`publish_message`内):
```
193-        self.history.add(message)  # For debug
```
コメント通り「デバッグ用」であり、協調ロジックが依存する正本ストアではない。正本の状態は各Roleの `MessageQueue`(インメモリ、per-role)であり、プロセスを跨ぐ永続化の規定は無い(実装依存のシリアライズ機構は別途あるが、ルーティングの仕組み自体はインメモリ)。

### (d) 順序付きイベントストリーム

`asyncio.Queue` ベースの `MessageQueue` は到着順を保持するが (Python標準の `Queue` FIFO)、「実行中の出来事」を型付きイベントとして外部へストリーム配信する仕組み(A2AのSSE/gRPC streamやMCPの通知に相当するもの)はコード上見当たらなかった。`environment/base_env.py`, `roles/role.py` の範囲では出来事は `Message` オブジェクトそのものであり、専用の「進捗イベント型」は無い。

### message pool / environment のルーティング (宛先決定の根拠)

`publish_message` (`metagpt/environment/base_env.py:175-195`):
```
175:    def publish_message(self, message: Message, peekable: bool = True) -> bool:
184-        logger.debug(f"publish_message: {message.dump()}")
185-        found = False
187-        for role, addrs in self.member_addrs.items():
188-            if is_send_to(message, addrs):
189-                role.put_message(message)
190-                found = True
191-        if not found:
192-            logger.warning(f"Message no recipients: {message.dump()}")
193-        self.history.add(message)  # For debug
195-        return True
```
`member_addrs: Dict[BaseRole, Set]` (`metagpt/environment/base_env.py:133`)。

`is_send_to` (`metagpt/utils/common.py:423-431`):
```
423:def is_send_to(message: "Message", addresses: set):
424-    """Return whether it's consumer"""
425-    if MESSAGE_ROUTE_TO_ALL in message.send_to:
426-        return True
428-    for i in addresses:
429-        if i in message.send_to:
430-            return True
431-    return False
```

Role側の購読・フィルタ (`metagpt/roles/role.py`):
```
284:    def _watch(self, actions: Iterable[Type[Action]] | Iterable[Action]):
288-        self.rc.watch = {any_to_str(t) for t in actions}
290:    def is_watch(self, caused_by: str):
291-        return caused_by in self.rc.watch
```
`_observe` 内のフィルタ条件 (`metagpt/roles/role.py:410-412`、**宛先決定の核心行**):
```
410:        self.rc.news = [
411-            n for n in news if (n.cause_by in self.rc.watch or self.name in n.send_to) and n not in old_messages
412-        ]
```
宛先の決定は「`cause_by` が自分の `watch` 集合(文字列集合)に含まれる」または「自分の名前(文字列)が `send_to` (文字列集合)に含まれる」という**文字列一致**に基づく。型システムによる強制は無い。

### 古典的抽象への対応と落ちている不変量 (MetaGPT)

- **最も近い抽象**: pub/sub付きActorモデル。各Roleは独立した`MessageQueue`(メールボックス)を持ち(`schema.py:713-730`)、`Environment.publish_message`がマルチキャスト配送を行う(`base_env.py:175-195`)。Environmentの`history`は「デバッグ用」と明記されており(`base_env.py:193`)協調の正本として設計されていないため、blackboardとしては弱い(読み書き共有のための一次資料ではない)。
- **落ちている不変量**: FIPA ACLのperformative(発話行為の種類)に相当する`cause_by`が**型で閉じていない**(`schema.py:239`、plain `str`)。ACLが本来持つ「発話の種類は事前に合意されたレジストリに属する」という不変量が、MetaGPTでは「Pythonのクラス名を文字列化したもの」という開いた集合に置き換わっている。同様に`send_to`(宛先指定)も任意文字列の集合であり、Actorモデルが本来持つ「宛先はアドレス空間内の型付きID」という制約がない。

---

## 4. AutoGen

リポジトリ: `_src/autogen-src` (bare: `_src/autogen.git`, HEAD `027ecf0a379bcc1d09956d46d12d44a3ad9cee14`)
対象パッケージ: `python/packages/autogen-core/src/autogen_core/`

### メッセージ型 (`_agent_runtime.py`)

```
22:    async def send_message(
23-        self,
24-        message: Any,
25-        recipient: AgentId,
```
```
50:    async def publish_message(
51-        self,
52-        message: Any,
53-        topic_id: TopicId,
```
(`python/packages/autogen-core/src/autogen_core/_agent_runtime.py:22-24, 50-53`)

**メッセージ型はユーザー定義の任意型 (`Any`)** であり、有限集合ではない。この事実はランタイムのシグネチャそのもの (`message: Any`) から直接読み取れる。

ディスパッチは受信側で `Type[Any]` をキーにした辞書引き (`_routed_agent.py:462-468`):
```
462-        self._handlers: DefaultDict[
463-            Type[Any],
464-            List[MessageHandler[RoutedAgent, Any, Any]],
465-        ] = DefaultDict(list)
466-
467-        handlers = self._discover_handlers()
468-        for message_handler in handlers:
```
(`python/packages/autogen-core/src/autogen_core/_routed_agent.py:462-468`)。つまり各Agentは「自分が処理できる型」を実行時の `type()` 判定で登録するが、システム全体でのメッセージ型の集合はクローズドではない(ユーザーが新しい `@dataclass` を定義するたびに増える)。

### topic/subscription定義

`TopicId` (`_topic.py:12-27`):
```
12:class TopicId:
19-    type: str
27-    source: str
33-    def __post_init__(self) -> None:
34-        if is_valid_topic_type(self.type) is False:
35-            raise ValueError(...)
```
(`python/packages/autogen-core/src/autogen_core/_topic.py:12-35`)。`type`と`source`は両方 `str`(CloudEvents仕様に準拠する正規表現チェックのみ、値そのものは開いた文字列空間)。

`Subscription` protocol (`_subscription.py`、全文引用済み):
```
class Subscription(Protocol):
    def is_match(self, topic_id: TopicId) -> bool: ...
    def map_to_agent(self, topic_id: TopicId) -> AgentId: ...
```
(`python/packages/autogen-core/src/autogen_core/_subscription.py`、`is_match`/`map_to_agent`のシグネチャ部分)。

### 古典的抽象への対応と落ちている不変量 (AutoGen)

- **最も近い抽象**: CloudEvents的なトピックベースpub/sub Actorモデル(Erlang/Akkaの分散イベントバスに類似)。`TopicId(type, source)`は明確に「イベント」概念であり、Actor同士は直接アドレスを知らずtopicを介して疎結合になる。
- **落ちている不変量**: セッション型(session types)が要求する「プロトコル全体の型による静的検証」が無い。メッセージ型が`Any`(`_agent_runtime.py:24,52`)である以上、「このAgentは次にこの型のメッセージだけを受信できる」という制約はコンパイル時には存在せず、実行時の`Type`辞書引き(`_routed_agent.py:462-468`)でのみ解決される。型が合わなければ単にどのハンドラにもマッチせず無視される(黙殺)という失敗モードになりうる。

---

## 5. LangGraph

リポジトリ: `_src/langgraph-src` (bare: `_src/langgraph.git`, HEAD `aa742fb31e2827d569b843e3600aeda2e0528e4b`)

### 状態スキーマとreducerの扱い (`libs/langgraph/langgraph/graph/state.py`)

チャンネル抽出のコア関数 (`state.py:1815-1834`):
```
1815:def _get_channels(
1816-    schema: type[dict],
1817-) -> tuple[dict[str, BaseChannel], dict[str, ManagedValueSpec], dict[str, Any]]:
1825-    type_hints = get_type_hints(schema, include_extras=True)
1826-    all_keys = {
1827-        name: _get_channel(name, typ)
1828-        for name, typ in type_hints.items()
1829-        if name != "__slots__"
1830-    }
```
`get_type_hints`(Python標準ライブラリの実行時型ヒント読み取り関数)でスキーマの注釈を読み、チャンネル(`BaseChannel`)を組み立てる。**これは実行時のリフレクションであり、静的型チェッカーによる強制ではない**。

reducer(`Annotated[type, reducer]`)のシグネチャ検査 (`state.py:1904-1922`、`_is_field_binop`):
```
1904:def _is_field_binop(typ: type[Any]) -> BinaryOperatorAggregate | None:
1905-    if hasattr(typ, "__metadata__"):
1906-        meta = typ.__metadata__
1907-        if len(meta) >= 1 and callable(meta[-1]):
1908-            sig = signature(meta[-1])
1909-            params = list(sig.parameters.values())
1910-            if (
1911-                sum(
1912-                    p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
1913-                    for p in params
1914-                )
1915-                == 2
1916-            ):
1917-                return BinaryOperatorAggregate(typ, meta[-1])
1918-            else:
1919-                raise ValueError(
1920-                    f"Invalid reducer signature. Expected (a, b) -> c. Got {sig}"
1921-                )
1922-    return None
```
reducerの引数個数(2個であること)は `inspect.signature` を使った**実行時チェック**で強制されている(グラフ構築時に `ValueError` を送出、`state.py:1919-1921`)。reducerが指定されない場合のフォールバックは「最後の値で上書き」する `LastValue` チャンネル (`state.py:1871-1873`):
```
1871-    fallback: LastValue = LastValue(annotation)
1872-    fallback.key = name
1873-    return fallback
```

**結論**: 状態遷移(チャンネル更新)は「型で強制」ではなく「グラフ構築時のreducerシグネチャの実行時検査」で担保されている。値そのものの型適合性(例えば `int` 注釈のチャンネルに `str` を書き込むこと)を防ぐ実行時バリデーションはこの関数群には無い(Pythonの型ヒントは実行時には無視されるのが標準動作であり、ここでのチェックは「reducerの引数個数」のみ)。

### チェックポイント (永続ストア) の型定義

`Checkpoint` TypedDict (`libs/checkpoint/langgraph/checkpoint/base/__init__.py:93-124`):
```
93:class Checkpoint(TypedDict):
94-    """State snapshot at a given point in time."""
96-    v: int
98-    id: str
103-    ts: str
105-    channel_values: dict[str, Any]
110-    channel_versions: ChannelVersions
116-    versions_seen: dict[str, ChannelVersions]
122-    updated_channels: list[str] | None
```
`CheckpointTuple` (`libs/checkpoint/langgraph/checkpoint/base/__init__.py:140-147`):
```
140:class CheckpointTuple(NamedTuple):
143-    config: RunnableConfig
144-    checkpoint: Checkpoint
145-    metadata: CheckpointMetadata
146-    parent_config: RunnableConfig | None = None
147-    pending_writes: list[PendingWrite] | None = None
```
`BaseCheckpointSaver` の説明 (`libs/checkpoint/langgraph/checkpoint/base/__init__.py:177-191`、`thread_id`がプライマリキーである旨のdocstring)。

**このCheckpointは「仕事と成果を置く永続ストア」に該当する**: `channel_values`(現在の状態=進行中の仕事の中身と結果を含む)を `thread_id` をキーに保存・復元できる設計であり、実装は `libs/checkpoint-sqlite`, `libs/checkpoint-postgres` など別パッケージで提供される。ただし `channel_values: dict[str, Any]` (`base/__init__.py:105`)であり、値の型はここでも `Any` — 保存される値の型はチェックポイント層では検証されない。

### 古典的抽象への対応と落ちている不変量 (LangGraph)

- **最も近い抽象**: Kahn Process Networks / Synchronous Dataflow (SDF) に近いデータフローグラフ。`_get_channels`が示す通り、状態は名前付き「チャンネル」の集合であり、各ノード(処理単位)はチャンネルを読み書きするという設計は、Ptolemy IIのSDFアクターモデルの直接的な系譜にある(本セッションの別エージェントが調査中の `lee_sdf87.pdf`, `kahn1974.pdf` に対応する古典)。
- **落ちている不変量**: (1) チャンネル値の型はスキーマの注釈(`get_type_hints`)から導かれるが、実行時に書き込まれる値がその注釈と一致することを検証するコードはこの範囲に無い(`state.py:1825-1830`は型ヒントを"読む"だけで"検証"はしない)。(2) reducerの不変量チェックは「引数が2個の呼び出し可能物であること」のみ(`state.py:1907-1916`)で、reducerが結合則・可換則を満たすか(並行更新の順序に依存しないか)は一切検査されない——並行書き込みの安全性はreducer作者の責任に委ねられている。(3) `Checkpoint.channel_values: dict[str, Any]` (`base/__init__.py:105`)であるためストア層でも型は保証されない。

---

## 6. OpenAI Agents SDK

リポジトリ: `_src/openai-agents-python-src` (bare: `_src/openai-agents-python.git`, HEAD `165390cff0a6a8b0094c396418e6ed7fb9471398`)

**注記**: 依頼文が指す `src/agents/handoffs.py` は現在のHEADでは単一ファイルではなくパッケージ `src/agents/handoffs/__init__.py` (388行) に再編されている。以下はこのファイルと、実際にhandoff時の入力を組み立てる `src/agents/run_internal/turn_resolution.py` を引用する。

### `Handoff` / `HandoffInputData` 定義

```
71:class HandoffInputData:
72-    input_history: str | tuple[TResponseInputItem, ...]
73-    """
74-    The input history before `Runner.run()` was called.
77-    pre_handoff_items: tuple[RunItem, ...]
82-    new_items: tuple[RunItem, ...]
88-    run_context: RunContextWrapper[Any] | None = None
93-    input_items: tuple[RunItem, ...] | None = None
```
(`src/agents/handoffs/__init__.py:71-96`)

`Handoff` dataclass中の `input_filter` フィールドのdocstring (**デフォルト挙動を明記した一次資料**、`src/agents/handoffs/__init__.py:158-171`):
```
158:    input_filter: HandoffInputFilter | None = None
159-    """A function that filters the inputs that are passed to the next agent.
160-
161-    By default, the new agent sees the entire conversation history. In some cases, you may want to
162-    filter inputs (for example, to remove older inputs or remove tools from existing inputs). The
163-    function receives the entire conversation history so far, including the input item that
164-    triggered the handoff and a tool call output item representing the handoff tool's output. You
165-    are free to modify the input history or new items as you see fit. The next agent receives the
166-    input history plus ``input_items`` when provided, otherwise it receives ``new_items``.
```
(`src/agents/handoffs/__init__.py:161`: "By default, the new agent sees the entire conversation history.")

### 実際に次エージェントへ渡す入力を組み立てるコード (`src/agents/run_internal/turn_resolution.py`)

`HandoffInputData`はフィルタまたはネストが指定された場合のみ構築される (`turn_resolution.py:631-660`):
```
631:        input_filter = (
632-            handoff.input_filter
633-            if handoff.input_filter is not None
634-            else run_config.handoff_input_filter
635-        )
...
651:        handoff_input_data: HandoffInputData | None = None
652:        session_step_items: list[RunItem] | None = None
653:        nested_history_owned_items: list[NestedHistoryOwnedItem] | None = None
654:        if input_filter is not None or should_nest_history:
655:            handoff_input_data = HandoffInputData(
656:                input_history=tuple(original_input)
657:                if isinstance(original_input, list)
658:                else original_input,
659:                pre_handoff_items=tuple(pre_step_items),
660:                new_items=tuple(new_step_items),
661:                run_context=context_wrapper,
662:            )
```
`input_filter`もフィルタもnest指定も無い場合の分岐 (`turn_resolution.py:731-732`、コメント原文引用):
```
731:        else:
732-            # No filtering or nesting - session_step_items not needed.
733-            session_step_items = None
```
この`else`節では`original_input`(ここまでの累積入力=会話履歴全体)にも`new_step_items`にも一切手を加えない。関数末尾で返される`SingleStepResult`(`turn_resolution.py:741-745`)の`original_input=original_input`がそのまま次ターン(=ハンドオフ先エージェント)の入力になる:
```
741:    return SingleStepResult(
742-        original_input=original_input,
743-        model_response=new_response,
744-        pre_step_items=pre_step_items,
745-        new_step_items=new_step_items,
```

**結論(コードで確認した事実、要件「全履歴を受け取る前提にしない」に直結)**: `handoff.input_filter` が明示的に設定されていない限り、ハンドオフ先のエージェントは**それまでの累積入力(`original_input`、会話履歴全体)をそのまま**受け取る。「絞られた入力」がデフォルトなのではなく、「絞る」ことをするには利用者が`input_filter`(コールバック関数)を明示的に渡す必要がある。デフォルトは全履歴。根拠: `handoffs/__init__.py:161`(ドキュメント)+ `turn_resolution.py:654,731-732,742`(実装、フィルタ未指定時に`original_input`が無変更のまま次段に渡ることを示すコード)。

### 古典的抽象への対応と落ちている不変量 (OpenAI Agents SDK Handoff)

- **最も近い抽象**: Hewitt Actorモデルの「become」(自分の以降の振る舞いを別の振る舞いに置き換える)に近い。ハンドオフは新しいAgentに制御を譲る際、明示的なメッセージ構築(「これだけを渡す」)ではなく暗黙に文脈全体を引き継ぐ設計になっている。
- **落ちている不変量**: セッション型/Actorモデルが理想とする「各参加者は自分宛てに明示的に構築されたメッセージだけを見る(最小権限)」という境界が、デフォルトでは存在しない。`input_filter`という**オプトイン**の仕組みでしか境界を作れず、何も指定しなければ全履歴が筒抜けになる(`turn_resolution.py:729-730`のコメントが示す通り、「フィルタもネストも無い」場合は何の処理も入らない)。

---

## 7. サーベイ論文 (arXiv, 2024–2026)

### 論文1: arXiv:2505.02279 (v2, 2025-05-23)

**タイトル**: "A Survey of Agent Interoperability Protocols: Model Context Protocol (MCP), Agent Communication Protocol (ACP), Agent-to-Agent Protocol (A2A), and Agent Network Protocol (ANP)"
著者: Abul Ehtesham (Kent State University) ほか。
URL: https://arxiv.org/pdf/2505.02279 (HTTP 200で取得、`_src/arxiv_2505.02279.pdf`, テキスト抽出 `_src/arxiv_2505.02279.txt`)

分類軸に関する逐語引用 (Page 1, Abstract):
> "interaction modes, discovery mechanisms, communication patterns, and security models"

(原文コンテキスト: "The protocols are compared across multiple dimensions, including interaction modes, discovery mechanisms, communication patterns, and security models." — 引用箇所は`_src/arxiv_2505.02279.txt`のPAGE 1、`grep -n "dimensions, including"`で確認可能)

### 論文2: arXiv:2504.16736 (v3, 2025-06-21)

**タイトル**: "A Survey of AI Agent Protocols"
著者: Yingxuan Yang, Huacan Chai 他 (Shanghai Jiao Tong University / ANP Community)。
URL: https://arxiv.org/pdf/2504.16736 (HTTP 200で取得、`_src/arxiv_2504.16736.pdf`, テキスト抽出 `_src/arxiv_2504.16736.txt`)

分類軸に関する逐語引用 (Page 7):
> "first dimension—object orientation—protocols are divided into context-oriented and inter-agent types"

(原文コンテキスト: "On the first dimension—object orientation—protocols are divided into context-oriented and inter-agent types; on the second dimension—application scenario—they are further categorized..." — `_src/arxiv_2504.16736.txt` PAGE 7、`grep -n "two-dimensional classification framework"`で該当箇所を特定可能)

この論文は「object orientation (context-oriented / inter-agent)」×「application scenario」の二軸分類を提案しており、A2A/MetaGPT/AutoGenのような「inter-agent」型プロトコルと、MCPのような「context-oriented」型プロトコルを同じ軸の両端に位置づけている(Page 7の分類記述に基づく)。

---

## 未発見だったもの

- **A2A**: `specification/json/a2a.json` そのもの。検索語: なし(リポジトリ内`find`で直接確認)。辿った経路: `_src/A2A-src/specification/json/README.md`を読み、正本が`.proto`に移行済みで`.json`は非コミットのビルド成果物であることを確認。これは「未発見」というより「設計変更によりリポジトリに存在しない」という一次資料上の事実。
- **MCPの「task」概念**: `schema/2026-07-28/schema.ts`全文検索 (`grep -ni "task\\b"`) でマッチ0件。検索語: `task`。存在しないことを確認できた(仕様上不在)。
- **AutoGenのメッセージ型が有限集合であることを示す定義**: 探したが存在しない。`_agent_runtime.py`, `_routed_agent.py`, `_subscription.py`, `_topic.py`を確認し、すべて`Any`/`str`ベースであることを確認(=「有限enumではない」という結論の根拠であり、探し方が足りなかったわけではない)。

---

## 参照した一次資料ファイル一覧 (file:line 引用元)

- `_src/A2A-src/specification/a2a.proto`
- `_src/A2A-src/specification/json/README.md`
- `_src/MCP-src/schema/2026-07-28/schema.ts`
- `_src/MCP-src/schema/draft/schema.ts`
- `_src/MetaGPT-src/metagpt/schema.py`
- `_src/MetaGPT-src/metagpt/const.py`
- `_src/MetaGPT-src/metagpt/environment/base_env.py`
- `_src/MetaGPT-src/metagpt/roles/role.py`
- `_src/MetaGPT-src/metagpt/utils/common.py`
- `_src/autogen-src/python/packages/autogen-core/src/autogen_core/_agent_runtime.py`
- `_src/autogen-src/python/packages/autogen-core/src/autogen_core/_routed_agent.py`
- `_src/autogen-src/python/packages/autogen-core/src/autogen_core/_topic.py`
- `_src/autogen-src/python/packages/autogen-core/src/autogen_core/_subscription.py`
- `_src/langgraph-src/libs/langgraph/langgraph/graph/state.py`
- `_src/langgraph-src/libs/checkpoint/langgraph/checkpoint/base/__init__.py`
- `_src/openai-agents-python-src/src/agents/handoffs/__init__.py`
- `_src/openai-agents-python-src/src/agents/run_internal/turn_resolution.py`
- `_src/arxiv_2505.02279.pdf` / `.txt`
- `_src/arxiv_2504.16736.pdf` / `.txt`
