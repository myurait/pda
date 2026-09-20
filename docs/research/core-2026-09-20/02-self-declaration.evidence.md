# 第2本 根拠集 — MCP 的な自己宣言

本文: `02-self-declaration.md`。要件commit: `cdd90e945d938769aefa17a2b8de3236647f6bdc`。全件の取得日: 2026-09-20 JST。以下は担当調査者が一次資料を取得して確認した「本体確認」であり、未再取得の分担報告を含めていない。親の独立再取得の範囲は別ファイル `02-review.md` を参照。

逐語引用は検証に必要な最小断片に限定した。文脈の位置は引用より広い行範囲で示す。GitHub資料は各引用にcommit SHAを付し、PDF・保存版HTMLは元の公開URLと取得物SHA-256で固定する。Git SHAのない文献に架空のcommitは付けない。

PDFの `path:line` は取得PDFに `pdftotext -layout SOURCE.pdf SOURCE.txt` を実行した結果の改行基準（`\n`）であり、PDFの第何頁かと印刷ページも併記する。OCRの資料は画像確認の有無を記す。HTMLの行番号は保存された応答本体に対するもの。

## FIPA DF と JADE

<a id="f0"></a>

### F0

§4.1.1 登録内容の正しさを保証しない。

出典: [一次資料](https://web.archive.org/web/20211017033623id_/http://www.fipa.org/specs/fipa00023/SC00023J.html)。HTTP 200。Git commitなし。取得物SHA-256: `454dac7d39170b4c4c013748ca8649f795c95481f1228a1e7df2f4a92bb80d97`。位置: `fipa.html:1961–1964`。

```text
the DF cannot guarantee
```

<a id="f1"></a>

### F1

service templateとの適合検査。非公式ミラー。

出典: [ekiwi/jade-mirror/src/jade/domain/DFMemKB.java](https://raw.githubusercontent.com/ekiwi/jade-mirror/2723c7b52269c34d7f2ef366816776bcbcd90b8f/src/jade/domain/DFMemKB.java)。commit `2723c7b52269c34d7f2ef366816776bcbcd90b8f`、HTTP 200。位置: `src/jade/domain/DFMemKB.java:152–190`。

```text
found = compareServiceDesc(templateSvc, factSvc);
```

<a id="f2"></a>

### F2

§7.1 template matching。

出典: [一次資料](https://web.archive.org/web/20211017033623id_/http://www.fipa.org/specs/fipa00023/SC00023J.html)。HTTP 200。Git commitなし。取得物SHA-256: `454dac7d39170b4c4c013748ca8649f795c95481f1228a1e7df2f4a92bb80d97`。位置: `fipa.html:4893–4901`。

```text
Each parameter of the object template is matched
```

## contract net

<a id="c0"></a>

### C0

eligibility specificationの条件。

出典: [一次資料](https://cse-robotics.engr.tamu.edu/dshell/cs631/papers/smith80contract.pdf)。HTTP 200。Git commitなし。取得物SHA-256: `0b098a438af2bfe720c548f810474108c1d95859f9a488190ba49fee837f64cc`。 PDF第3頁、印刷p.1106。位置: `contract-net.txt:205–205`。

```text
a node must meet to be eligible to submit a bid.
```

<a id="c1"></a>

### C1

CHECK!ELIGIBILITY。PDF画像で照合。

出典: [一次資料](https://www.reidgsmith.com/Contract_Net_Code_and_Sample_Output_Interlisp_Dec_1978.pdf)。HTTP 200。Git commitなし。取得物SHA-256: `20ec3300b7a307e7432ca1c0ac470b99f0f873cceb391b97f702ea59f3d88473`。 PDF第7頁、印刷p.6。位置: `contract-net-code.txt:400–401`。

```text
(SETQ pelspec (for x in elspec always (CILPARSE x ELSPECGRAMMAR)))
```

<a id="c2"></a>

### C2

RESUME!TASK。PDF画像で照合。

出典: [一次資料](https://www.reidgsmith.com/Contract_Net_Code_and_Sample_Output_Interlisp_Dec_1978.pdf)。HTTP 200。Git commitなし。取得物SHA-256: `20ec3300b7a307e7432ca1c0ac470b99f0f873cceb391b97f702ea59f3d88473`。 PDF第52頁、印刷p.51。位置: `contract-net-code.txt:3009–3009`。

```text
(TRYNEXT taskprocesspointer])
```

<a id="c3"></a>

### C3

PROCESS!TASK!ANNOUNCEMENTの条件分岐。PDF画像照合。

出典: [一次資料](https://www.reidgsmith.com/Contract_Net_Code_and_Sample_Output_Interlisp_Dec_1978.pdf)。HTTP 200。Git commitなし。取得物SHA-256: `20ec3300b7a307e7432ca1c0ac470b99f0f873cceb391b97f702ea59f3d88473`。 PDF第44頁、印刷p.43。位置: `contract-net-code.txt:2499–2500`。

```text
([AND xtt (OR (NOT
```

<a id="c4"></a>

### C4

入札側が提供するnode abstraction。

出典: [一次資料](https://cse-robotics.engr.tamu.edu/dshell/cs631/papers/smith80contract.pdf)。HTTP 200。Git commitなし。取得物SHA-256: `0b098a438af2bfe720c548f810474108c1d95859f9a488190ba49fee837f64cc`。 PDF第4頁、印刷p.1107。位置: `contract-net.txt:221–228`。

```text
The node abstraction slot of a bid
```

## MCP

<a id="m1"></a>

### M1

outputSchema指定時の不変量。

出典: [modelcontextprotocol/modelcontextprotocol/docs/specification/2026-07-28/server/tools.mdx](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/24efd6e7cbd7a074e6b3b781eb370891df40afad/docs/specification/2026-07-28/server/tools.mdx)。commit `24efd6e7cbd7a074e6b3b781eb370891df40afad`、HTTP 200。位置: `docs/specification/2026-07-28/server/tools.mdx:509–515`。

```text
Servers **MUST** provide structured results that conform to this schema.
```

<a id="m2"></a>

### M2

注釈は真実性を保証しない。

出典: [modelcontextprotocol/modelcontextprotocol/schema/2026-07-28/schema.ts](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/24efd6e7cbd7a074e6b3b781eb370891df40afad/schema/2026-07-28/schema.ts)。commit `24efd6e7cbd7a074e6b3b781eb370891df40afad`、HTTP 200。位置: `schema/2026-07-28/schema.ts:1900–1946`。

```text
all properties in `ToolAnnotations` are **hints**.
```

<a id="m3"></a>

### M3

Toolの語彙範囲。

出典: [modelcontextprotocol/modelcontextprotocol/schema/2026-07-28/schema.ts](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/24efd6e7cbd7a074e6b3b781eb370891df40afad/schema/2026-07-28/schema.ts)。commit `24efd6e7cbd7a074e6b3b781eb370891df40afad`、HTTP 200。位置: `schema/2026-07-28/schema.ts:1967–2015`。

```text
outputSchema?: { $schema?: string; [key: string]: unknown };
```

<a id="m4"></a>

### M4

tool呼び出し前後の検査とcatch。

出典: [modelcontextprotocol/typescript-sdk/packages/server/src/server/mcp.ts](https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/60321700871029401a2e3bed8fdf4f02c9ec3331/packages/server/src/server/mcp.ts)。commit `60321700871029401a2e3bed8fdf4f02c9ec3331`、HTTP 200。位置: `packages/server/src/server/mcp.ts:261–288`。

```text
await this.validateToolOutput(tool, result, request.params.name);
```

<a id="m5"></a>

### M5

入力と正常な構造化出力を実検査。未宣言・input_required・isError除外。

出典: [modelcontextprotocol/typescript-sdk/packages/server/src/server/mcp.ts](https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/60321700871029401a2e3bed8fdf4f02c9ec3331/packages/server/src/server/mcp.ts)。commit `60321700871029401a2e3bed8fdf4f02c9ec3331`、HTTP 200。位置: `packages/server/src/server/mcp.ts:321–373`。

```text
if (!parseResult.success) {
```

<a id="m6"></a>

### M6

2025版にも同じ不変量がある。

出典: [modelcontextprotocol/modelcontextprotocol/docs/specification/2025-11-25/server/tools.mdx](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/24efd6e7cbd7a074e6b3b781eb370891df40afad/docs/specification/2025-11-25/server/tools.mdx)。commit `24efd6e7cbd7a074e6b3b781eb370891df40afad`、HTTP 200。位置: `docs/specification/2025-11-25/server/tools.mdx:335–343`。

```text
Servers **MUST** provide structured results that conform to this schema.
```

<a id="m7"></a>

### M7

SDK公開定数と実装経路の版差を明示。

出典: [modelcontextprotocol/typescript-sdk/packages/core/src/constants.ts](https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/60321700871029401a2e3bed8fdf4f02c9ec3331/packages/core/src/constants.ts)。commit `60321700871029401a2e3bed8fdf4f02c9ec3331`、HTTP 200。位置: `packages/core/src/constants.ts:1–14`。

```text
LATEST_PROTOCOL_VERSION = '2025-11-25'
```

<a id="m8"></a>

### M8

2026版の通信切断時は新規再投入。

出典: [modelcontextprotocol/modelcontextprotocol/docs/specification/2026-07-28/changelog.mdx](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/24efd6e7cbd7a074e6b3b781eb370891df40afad/docs/specification/2026-07-28/changelog.mdx)。commit `24efd6e7cbd7a074e6b3b781eb370891df40afad`、HTTP 200。位置: `docs/specification/2026-07-28/changelog.mdx:12–28`。

```text
clients **MUST** re-issue it as a new request with a new request ID
```

<a id="m9"></a>

### M9

追加入力を得るためのrequest継続token。

出典: [modelcontextprotocol/modelcontextprotocol/schema/2026-07-28/schema.ts](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/24efd6e7cbd7a074e6b3b781eb370891df40afad/schema/2026-07-28/schema.ts)。commit `24efd6e7cbd7a074e6b3b781eb370891df40afad`、HTTP 200。位置: `schema/2026-07-28/schema.ts:571–609`。

```text
requestState?: string;
```

<a id="m10"></a>

### M10

クライアント再起動後のpollingと実行器再開を区別。

出典: [modelcontextprotocol/ext-tasks/specification/2026-07-28/tasks.md](https://raw.githubusercontent.com/modelcontextprotocol/ext-tasks/9263312d11a682ac83f83fe84794d4627efd22f5/specification/2026-07-28/tasks.md)。commit `9263312d11a682ac83f83fe84794d4627efd22f5`、HTTP 200。位置: `specification/2026-07-28/tasks.md:300–310`。

```text
polling can resume after a crash or restart.
```

<a id="m11"></a>

### M11

rootsは提供範囲。サーバー側境界尊重はSHOULD。

出典: [modelcontextprotocol/modelcontextprotocol/docs/specification/2026-07-28/client/roots.mdx](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/24efd6e7cbd7a074e6b3b781eb370891df40afad/docs/specification/2026-07-28/client/roots.mdx)。commit `24efd6e7cbd7a074e6b3b781eb370891df40afad`、HTTP 200。位置: `docs/specification/2026-07-28/client/roots.mdx:135–148`。

```text
Respect root boundaries during operations
```

<a id="m12"></a>

### M12

金額ではなくモデル選択時の優先度。

出典: [modelcontextprotocol/modelcontextprotocol/schema/2026-07-28/schema.ts](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/24efd6e7cbd7a074e6b3b781eb370891df40afad/schema/2026-07-28/schema.ts)。commit `24efd6e7cbd7a074e6b3b781eb370891df40afad`、HTTP 200。位置: `schema/2026-07-28/schema.ts:2520–2529`。

```text
costPriority?: number;
```

<a id="m13"></a>

### M13

登録済みtoolから宣言を生成する経路。

出典: [modelcontextprotocol/typescript-sdk/packages/server/src/server/mcp.ts](https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/60321700871029401a2e3bed8fdf4f02c9ec3331/packages/server/src/server/mcp.ts)。commit `60321700871029401a2e3bed8fdf4f02c9ec3331`、HTTP 200。位置: `packages/server/src/server/mcp.ts:230–259`。

```text
tools: Object.entries(this._registeredTools)
```

## A2A

<a id="a1"></a>

### A1

未宣言streamingの拒否。

出典: [a2aproject/A2A/docs/specification.md](https://raw.githubusercontent.com/a2aproject/A2A/afda8316c64951a2ecb2a0d3d10867405d2b4095/docs/specification.md)。commit `afda8316c64951a2ecb2a0d3d10867405d2b4095`、HTTP 200。位置: `docs/specification.md:569–577`。

```text
**MUST** return [`UnsupportedOperationError`](#332-error-handling).
```

<a id="a2"></a>

### A2

AgentCard/Capabilities/Skill、費用と到達権限の専用欄を調査。

出典: [a2aproject/A2A/specification/a2a.proto](https://raw.githubusercontent.com/a2aproject/A2A/afda8316c64951a2ecb2a0d3d10867405d2b4095/specification/a2a.proto)。commit `afda8316c64951a2ecb2a0d3d10867405d2b4095`、HTTP 200。位置: `specification/a2a.proto:360–454`。

```text
optional bool streaming = 1;
```

<a id="a3"></a>

### A3

AgentCard宣言を実行ゲートが参照。

出典: [a2aproject/a2a-python/src/a2a/server/request_handlers/default_request_handler.py](https://raw.githubusercontent.com/a2aproject/a2a-python/9a00f9b91fd4e85019c8983278a39d65f67fdd04/src/a2a/server/request_handlers/default_request_handler.py)。commit `9a00f9b91fd4e85019c8983278a39d65f67fdd04`、HTTP 200。位置: `src/a2a/server/request_handlers/default_request_handler.py:432–454`。

```text
lambda self: self._agent_card.capabilities.streaming,
```

<a id="a4"></a>

### A4

拒否エラー既定値。

出典: [a2aproject/a2a-python/src/a2a/server/request_handlers/request_handler.py](https://raw.githubusercontent.com/a2aproject/a2a-python/9a00f9b91fd4e85019c8983278a39d65f67fdd04/src/a2a/server/request_handlers/request_handler.py)。commit `9a00f9b91fd4e85019c8983278a39d65f67fdd04`、HTTP 200。位置: `src/a2a/server/request_handlers/request_handler.py:290–299`。

```text
error_type: type[Exception] = UnsupportedOperationError,
```

<a id="a5"></a>

### A5

偽ならhandler実行前に拒否。

出典: [a2aproject/a2a-python/src/a2a/server/request_handlers/request_handler.py](https://raw.githubusercontent.com/a2aproject/a2a-python/9a00f9b91fd4e85019c8983278a39d65f67fdd04/src/a2a/server/request_handlers/request_handler.py)。commit `9a00f9b91fd4e85019c8983278a39d65f67fdd04`、HTTP 200。位置: `src/a2a/server/request_handlers/request_handler.py:366–377`。

```text
raise error_type(final_message)
```

<a id="a6"></a>

### A6

応答とstreamの型。内部行為を全て送る規定とは別。

出典: [a2aproject/A2A/specification/a2a.proto](https://raw.githubusercontent.com/a2aproject/A2A/afda8316c64951a2ecb2a0d3d10867405d2b4095/specification/a2a.proto)。commit `afda8316c64951a2ecb2a0d3d10867405d2b4095`、HTTP 200。位置: `specification/a2a.proto:779–803`。

```text
TaskStatusUpdateEvent status_update = 3;
```

## OpenAPI

<a id="o1"></a>

### O1

oneOfで要求される性質。記述と実検査は別。

出典: [OAI/OpenAPI-Specification/versions/3.1.0.md](https://raw.githubusercontent.com/OAI/OpenAPI-Specification/c9f8f040e825a827bb011955bd41b7e2d899688f/versions/3.1.0.md)。commit `c9f8f040e825a827bb011955bd41b7e2d899688f`、HTTP 200。位置: `versions/3.1.0.md:2715–2725`。

```text
payload _MUST_, by validation, match exactly one of the schemas
```

<a id="o2"></a>

### O2

instanceをjsonschema validatorへ渡し違反を返す。

出典: [python-openapi/openapi-core/openapi_core/validation/schemas/validators.py](https://raw.githubusercontent.com/python-openapi/openapi-core/0337b43bd65dac2f5ed041b78996383370f72da3/openapi_core/validation/schemas/validators.py)。commit `0337b43bd65dac2f5ed041b78996383370f72da3`、HTTP 200。位置: `openapi_core/validation/schemas/validators.py:43–48`。

```text
raise InvalidSchemaValue(value, schema_type, schema_errors=errors)
```

<a id="o3"></a>

### O3

リクエスト検査経路。

出典: [python-openapi/openapi-core/openapi_core/validation/request/validators.py](https://raw.githubusercontent.com/python-openapi/openapi-core/0337b43bd65dac2f5ed041b78996383370f72da3/openapi_core/validation/request/validators.py)。commit `0337b43bd65dac2f5ed041b78996383370f72da3`、HTTP 200。位置: `openapi_core/validation/request/validators.py:288–295`。

```text
raise err
```

<a id="o4"></a>

### O4

レスポンス検査経路。

出典: [python-openapi/openapi-core/openapi_core/validation/response/validators.py](https://raw.githubusercontent.com/python-openapi/openapi-core/0337b43bd65dac2f5ed041b78996383370f72da3/openapi_core/validation/response/validators.py)。commit `0337b43bd65dac2f5ed041b78996383370f72da3`、HTTP 200。位置: `openapi_core/validation/response/validators.py:208–215`。

```text
raise err
```

<a id="o5"></a>

### O5

宣言だけではなく値の検査へ到達。

出典: [python-openapi/openapi-core/openapi_core/validation/validators.py](https://raw.githubusercontent.com/python-openapi/openapi-core/0337b43bd65dac2f5ed041b78996383370f72da3/openapi_core/validation/validators.py)。commit `0337b43bd65dac2f5ed041b78996383370f72da3`、HTTP 200。位置: `openapi_core/validation/validators.py:178–187`。

```text
validator.validate(value)
```

## Kubernetes

<a id="k1"></a>

### K1

CPU/memoryの不足検査。

出典: [kubernetes/kubernetes/pkg/scheduler/framework/plugins/noderesources/fit.go](https://raw.githubusercontent.com/kubernetes/kubernetes/400031d69530e018d5c001a922d3c5d2afaba954/pkg/scheduler/framework/plugins/noderesources/fit.go)。commit `400031d69530e018d5c001a922d3c5d2afaba954`、HTTP 200。位置: `pkg/scheduler/framework/plugins/noderesources/fit.go:713–754`。

```text
Reason:       "Insufficient cpu",
```

<a id="k2"></a>

### K2

LinuxランタイムへCPU上限とmemory上限を設定。

出典: [kubernetes/kubernetes/pkg/kubelet/kuberuntime/kuberuntime_container_linux.go](https://raw.githubusercontent.com/kubernetes/kubernetes/400031d69530e018d5c001a922d3c5d2afaba954/pkg/kubelet/kuberuntime/kuberuntime_container_linux.go)。commit `400031d69530e018d5c001a922d3c5d2afaba954`、HTTP 200。位置: `pkg/kubelet/kuberuntime/kuberuntime_container_linux.go:362–391`。

```text
resources.CpuQuota = cpuQuota
```

<a id="k3"></a>

### K3

要求資源による配置制限の仕様。

出典: [kubernetes/website/content/en/docs/concepts/configuration/manage-resources-containers.md](https://raw.githubusercontent.com/kubernetes/website/16f40ab512244b5df94714bbaba96f75cae55b8e/content/en/docs/concepts/configuration/manage-resources-containers.md)。commit `16f40ab512244b5df94714bbaba96f75cae55b8e`、HTTP 200。位置: `content/en/docs/concepts/configuration/manage-resources-containers.md:248–258`。

```text
a Pod on a node if the capacity check fails.
```

<a id="k4"></a>

### K4

不足検出からUnschedulable返却まで。

出典: [kubernetes/kubernetes/pkg/scheduler/framework/plugins/noderesources/fit.go](https://raw.githubusercontent.com/kubernetes/kubernetes/400031d69530e018d5c001a922d3c5d2afaba954/pkg/scheduler/framework/plugins/noderesources/fit.go)。commit `400031d69530e018d5c001a922d3c5d2afaba954`、HTTP 200。位置: `pkg/scheduler/framework/plugins/noderesources/fit.go:674–691`。

```text
return fwk.NewStatus(statusCode, failureReasons...)
```

<a id="k5"></a>

### K5

nodeSelector/affinityの不一致を拒否。

出典: [kubernetes/kubernetes/pkg/scheduler/framework/plugins/nodeaffinity/node_affinity.go](https://raw.githubusercontent.com/kubernetes/kubernetes/400031d69530e018d5c001a922d3c5d2afaba954/pkg/scheduler/framework/plugins/nodeaffinity/node_affinity.go)。commit `400031d69530e018d5c001a922d3c5d2afaba954`、HTTP 200。位置: `pkg/scheduler/framework/plugins/nodeaffinity/node_affinity.go:218–235`。

```text
return fwk.NewStatus(fwk.UnschedulableAndUnresolvable, ErrReasonPod)
```

<a id="k6"></a>

### K6

Linux権限のadd/dropをランタイムへ渡す。OAuth権限とは別。

出典: [kubernetes/kubernetes/pkg/kubelet/kuberuntime/security_context.go](https://raw.githubusercontent.com/kubernetes/kubernetes/400031d69530e018d5c001a922d3c5d2afaba954/pkg/kubelet/kuberuntime/security_context.go)。commit `400031d69530e018d5c001a922d3c5d2afaba954`、HTTP 200。位置: `pkg/kubelet/kuberuntime/security_context.go:138–155`。

```text
capabilities.DropCapabilities[index] = string(value)
```

<a id="k7"></a>

### K7

再起動policyを宣言。checkpointではない。

出典: [kubernetes/kubernetes/staging/src/k8s.io/api/core/v1/types.go](https://raw.githubusercontent.com/kubernetes/kubernetes/400031d69530e018d5c001a922d3c5d2afaba954/staging/src/k8s.io/api/core/v1/types.go)。commit `400031d69530e018d5c001a922d3c5d2afaba954`、HTTP 200。位置: `staging/src/k8s.io/api/core/v1/types.go:3959–3970`。

```text
RestartPolicyNever     RestartPolicy = "Never"
```

## Nix

<a id="n1"></a>

### N1

requiredSystemFeaturesの制約。

出典: [NixOS/nix/doc/manual/source/language/advanced-attributes.md](https://raw.githubusercontent.com/NixOS/nix/af265fd96c62fa4409d05124ce051ae1cdff0b13/doc/manual/source/language/advanced-attributes.md)。commit `af265fd96c62fa4409d05124ce051ae1cdff0b13`、HTTP 200。位置: `doc/manual/source/language/advanced-attributes.md:156–169`。

```text
Nix will only build the derivation on a machine
```

<a id="n2"></a>

### N2

全特徴を包含するか検査。

出典: [NixOS/nix/src/libstore/machines.cc](https://raw.githubusercontent.com/NixOS/nix/af265fd96c62fa4409d05124ce051ae1cdff0b13/src/libstore/machines.cc)。commit `af265fd96c62fa4409d05124ce051ae1cdff0b13`、HTTP 200。位置: `src/libstore/machines.cc:45–57`。

```text
return supportedFeatures.count(feature) || mandatoryFeatures.count(feature);
```

<a id="n3"></a>

### N3

候補選択で検査を利用。

出典: [NixOS/nix/src/nix/build-remote/build-remote.cc](https://raw.githubusercontent.com/NixOS/nix/af265fd96c62fa4409d05124ce051ae1cdff0b13/src/nix/build-remote/build-remote.cc)。commit `af265fd96c62fa4409d05124ce051ae1cdff0b13`、HTTP 200。位置: `src/nix/build-remote/build-remote.cc:164–175`。

```text
m.allSupported(requiredFeatures)
```

<a id="n4"></a>

### N4

ネットワーク隔離の例外。

出典: [NixOS/nix/src/libstore/linux/build/linux-derivation-builder.cc](https://raw.githubusercontent.com/NixOS/nix/af265fd96c62fa4409d05124ce051ae1cdff0b13/src/libstore/linux/build/linux-derivation-builder.cc)。commit `af265fd96c62fa4409d05124ce051ae1cdff0b13`、HTTP 200。位置: `src/libstore/linux/build/linux-derivation-builder.cc:520–530`。

```text
Fixed-output
```

<a id="n5"></a>

### N5

Linux sandboxの具体的強制要求。

出典: [NixOS/nix/src/libstore/linux/build/linux-derivation-builder.cc](https://raw.githubusercontent.com/NixOS/nix/af265fd96c62fa4409d05124ce051ae1cdff0b13/src/libstore/linux/build/linux-derivation-builder.cc)。commit `af265fd96c62fa4409d05124ce051ae1cdff0b13`、HTTP 200。位置: `src/libstore/linux/build/linux-derivation-builder.cc:574–581`。

```text
options.cloneFlags |= CLONE_NEWNET;
```

<a id="n6"></a>

### N6

features一致は管理者定義の値の一致であり実態の全項目検証ではない。

出典: [NixOS/nix/src/libstore/include/nix/store/globals.hh](https://raw.githubusercontent.com/NixOS/nix/af265fd96c62fa4409d05124ce051ae1cdff0b13/src/libstore/include/nix/store/globals.hh)。commit `af265fd96c62fa4409d05124ce051ae1cdff0b13`、HTTP 200。位置: `src/libstore/include/nix/store/globals.hh:315–326`。

```text
System features are user-defined
```

## Pony

<a id="p1"></a>

### P1

TCPConnectAuthだけを渡した場合の限定。

出典: [ponylang/pony-tutorial/docs/object-capabilities/derived-authority.md](https://raw.githubusercontent.com/ponylang/pony-tutorial/782050ed0b25dfc80ecd317f9c68c64e9baafc96/docs/object-capabilities/derived-authority.md)。commit `782050ed0b25dfc80ecd317f9c68c64e9baafc96`、HTTP 200。位置: `docs/object-capabilities/derived-authority.md:19–45`。

```text
it cannot access the filesystem or listen on a TCP or UDP port.
```

<a id="p2"></a>

### P2

FFI境界。

出典: [ponylang/pony-tutorial/docs/object-capabilities/trust-boundary.md](https://raw.githubusercontent.com/ponylang/pony-tutorial/782050ed0b25dfc80ecd317f9c68c64e9baafc96/docs/object-capabilities/trust-boundary.md)。commit `782050ed0b25dfc80ecd317f9c68c64e9baafc96`、HTTP 200。位置: `docs/object-capabilities/trust-boundary.md:1–25`。

```text
C-FFI can be used to break pretty much every guarantee that Pony makes.
```

<a id="p3"></a>

### P3

ファイル権限の構築に親権限が必要。

出典: [ponylang/ponyc/packages/files/file_auth.pony](https://raw.githubusercontent.com/ponylang/ponyc/f8a5e22672dfd2427b45e6845bffcc690e02f57e/packages/files/file_auth.pony)。commit `f8a5e22672dfd2427b45e6845bffcc690e02f57e`、HTTP 200。位置: `packages/files/file_auth.pony:1–6`。

```text
new create(from: AmbientAuth) =>
```

<a id="p4"></a>

### P4

ネットワーク権限の縮小。

出典: [ponylang/ponyc/packages/net/auth.pony](https://raw.githubusercontent.com/ponylang/ponyc/f8a5e22672dfd2427b45e6845bffcc690e02f57e/packages/net/auth.pony)。commit `f8a5e22672dfd2427b45e6845bffcc690e02f57e`、HTTP 200。位置: `packages/net/auth.pony:25–31`。

```text
new create(from: (AmbientAuth | NetAuth | TCPAuth)) =>
```

<a id="p5"></a>

### P5

関数引数が要求型に合わない場合を拒否。

出典: [ponylang/ponyc/src/libponyc/expr/call.c](https://raw.githubusercontent.com/ponylang/ponyc/f8a5e22672dfd2427b45e6845bffcc690e02f57e/src/libponyc/expr/call.c)。commit `f8a5e22672dfd2427b45e6845bffcc690e02f57e`、HTTP 200。位置: `src/libponyc/expr/call.c:430–460`。

```text
argument not assignable to parameter
```

<a id="p6"></a>

### P6

AmbientAuthの私的コンストラクタ。

出典: [ponylang/ponyc/packages/builtin/ambient_auth.pony](https://raw.githubusercontent.com/ponylang/ponyc/f8a5e22672dfd2427b45e6845bffcc690e02f57e/packages/builtin/ambient_auth.pony)。commit `f8a5e22672dfd2427b45e6845bffcc690e02f57e`、HTTP 200。位置: `packages/builtin/ambient_auth.pony:1–16`。

```text
new _create() =>
```

<a id="p7"></a>

### P7

FilePath型だけをOS sandboxとみなせない。

出典: [ponylang/ponyc/packages/files/walk_handler.pony](https://raw.githubusercontent.com/ponylang/ponyc/f8a5e22672dfd2427b45e6845bffcc690e02f57e/packages/files/walk_handler.pony)。commit `f8a5e22672dfd2427b45e6845bffcc690e02f57e`、HTTP 200。位置: `packages/files/walk_handler.pony:59–100`。

```text
Containment is textual: it does not resolve symlinks
```

<a id="p8"></a>

### P8

参照能力は共有・並行性を制御する型の一部。

出典: [ponylang/pony-tutorial/docs/reference-capabilities/reference-capabilities.md](https://raw.githubusercontent.com/ponylang/pony-tutorial/782050ed0b25dfc80ecd317f9c68c64e9baafc96/docs/reference-capabilities/reference-capabilities.md)。commit `782050ed0b25dfc80ecd317f9c68c64e9baafc96`、HTTP 200。位置: `docs/reference-capabilities/reference-capabilities.md:17–17`。

```text
every reference has both a type and a reference capability
```

## CHERI

<a id="h0"></a>

### H0

CHERI ISAv9 §2.3.2 boundsと参照時例外。

出典: [一次資料](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-987.pdf)。HTTP 200。Git commitなし。取得物SHA-256: `1ec0be89959bf89f66805647219605e936c942d492073cd692407cdebe437afb`。 PDF第49頁、印刷p.49。位置: `cheri.txt:2028–2032`。

```text
Capabilities contain lower and upper bounds for the memory they authorize access to.
```

<a id="h1"></a>

### H1

tag・permission・boundsの実行時拒否。

出典: [CTSRD-CHERI/qemu/target/cheri-common/cheri-helper-utils.h](https://raw.githubusercontent.com/CTSRD-CHERI/qemu/d0bb921cd6d34d1f8f4b3dafd279aa571795c938/target/cheri-common/cheri-helper-utils.h)。commit `d0bb921cd6d34d1f8f4b3dafd279aa571795c938`、HTTP 200。位置: `target/cheri-common/cheri-helper-utils.h:98–143`。

```text
cause = CapEx_LengthViolation;
```

<a id="h2"></a>

### H2

通常DDC経由メモリアクセス検査経路。

出典: [CTSRD-CHERI/qemu/target/cheri-common/cheri-helper-utils.h](https://raw.githubusercontent.com/CTSRD-CHERI/qemu/d0bb921cd6d34d1f8f4b3dafd279aa571795c938/target/cheri-common/cheri-helper-utils.h)。commit `d0bb921cd6d34d1f8f4b3dafd279aa571795c938`、HTTP 200。位置: `target/cheri-common/cheri-helper-utils.h:146–154`。

```text
check_cap(env, ddc, perm, addr, CHERI_EXC_REGNUM_DDC, len,
```

## Koka effect system

<a id="e0"></a>

### E0

Leijen 2014 Koka効果型の性質。

出典: [一次資料](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/paper-20.pdf)。HTTP 200。Git commitなし。取得物SHA-256: `6f7b22ee4b3e30de4344eebc982fe3258786316dba7cc5d3c1306bcf87b187de`。 PDF第1頁、印刷p.1。位置: `koka.txt:14–14`。

```text
typed without an exn effect, then it will never throw an unhandled exception.
```

<a id="e1"></a>

### E1

型へのeffect反映。

出典: [koka-lang/koka/doc/spec/tour.kk.md](https://raw.githubusercontent.com/koka-lang/koka/d881e92b61516f84beeebd2a80ebb6c09a9847f0/doc/spec/tour.kk.md)。commit `d881e92b61516f84beeebd2a80ebb6c09a9847f0`、HTTP 200。位置: `doc/spec/tour.kk.md:452–480`。

```text
automatically infers all the _side effects_
```

<a id="e2"></a>

### E2

関数/引数のeffectを合わせる。

出典: [koka-lang/koka/src/Type/Infer.hs](https://raw.githubusercontent.com/koka-lang/koka/d881e92b61516f84beeebd2a80ebb6c09a9847f0/src/Type/Infer.hs)。commit `d881e92b61516f84beeebd2a80ebb6c09a9847f0`、HTTP 200。位置: `src/Type/Infer.hs:1354–1357`。

```text
inferUnify (checkEffectSubsume rng) (getRange fun) funEff topEff
```

<a id="e3"></a>

### E3

effect row制約処理。

出典: [koka-lang/koka/src/Type/Unify.hs](https://raw.githubusercontent.com/koka-lang/koka/d881e92b61516f84beeebd2a80ebb6c09a9847f0/src/Type/Unify.hs)。commit `d881e92b61516f84beeebd2a80ebb6c09a9847f0`、HTTP 200。位置: `src/Type/Unify.hs:374–399`。

```text
unifyError Infinite
```

<a id="e4"></a>

### E4

検査失敗用診断。

出典: [koka-lang/koka/src/Type/Infer.hs](https://raw.githubusercontent.com/koka-lang/koka/d881e92b61516f84beeebd2a80ebb6c09a9847f0/src/Type/Infer.hs)。commit `d881e92b61516f84beeebd2a80ebb6c09a9847f0`、HTTP 200。位置: `src/Type/Infer.hs:2176–2191`。

```text
effect cannot be subsumed
```

## 契約による設計

<a id="d0"></a>

### D0

Meyer 1992契約による設計。

出典: [一次資料](https://se.inf.ethz.ch/~meyer/publications/computer/contract.pdf)。HTTP 200。Git commitなし。取得物SHA-256: `bc1bab86f8753e5eafb40b7558e961b2c4bc9938c061e8dd8c141b839873ac07`。 PDF第5頁、印刷p.44。位置: `meyer.txt:273–274`。

```text
A postcondition violation is a bug in
```

<a id="d1"></a>

### D1

前条件/後条件の違反を例外化。

出典: [Parquery/icontract/icontract/_checkers.py](https://raw.githubusercontent.com/Parquery/icontract/3e733f9e790359036c4da2cc550c599107710b60/icontract/_checkers.py)。commit `3e733f9e790359036c4da2cc550c599107710b60`、HTTP 200。位置: `icontract/_checkers.py:817–845`。

```text
raise violation_error
```

<a id="d2"></a>

### D2

既定値はPython debug。

出典: [Parquery/icontract/icontract/_decorators.py](https://raw.githubusercontent.com/Parquery/icontract/3e733f9e790359036c4da2cc550c599107710b60/icontract/_decorators.py)。commit `3e733f9e790359036c4da2cc550c599107710b60`、HTTP 200。位置: `icontract/_decorators.py:27–33`。

```text
enabled: bool = __debug__,
```

<a id="d3"></a>

### D3

無効化時には元関数を返す。

出典: [Parquery/icontract/icontract/_decorators.py](https://raw.githubusercontent.com/Parquery/icontract/3e733f9e790359036c4da2cc550c599107710b60/icontract/_decorators.py)。commit `3e733f9e790359036c4da2cc550c599107710b60`、HTTP 200。位置: `icontract/_decorators.py:110–120`。

```text
if not self.enabled:
```

## WSDL と Zeep

<a id="w0"></a>

### W0

WSDL 1.1抽象メッセージとbindingの分離。

出典: [一次資料](https://www.w3.org/TR/2001/NOTE-wsdl-20010315)。HTTP 200。Git commitなし。取得物SHA-256: `f1adcaa3774f20a5edb68014481f60930910ffc8aa764def9acb550aefe071fc`。位置: `wsdl.html:217–220`。

```text
the abstract definition of endpoints and messages is
```

<a id="w1"></a>

### W1

送信XMLにおける必須/繰返し要素検査。

出典: [mvantellingen/python-zeep/src/zeep/xsd/elements/element.py](https://raw.githubusercontent.com/mvantellingen/python-zeep/1b7072c0dba397b86e8a47cf766a39f981b3a2de/src/zeep/xsd/elements/element.py)。commit `1b7072c0dba397b86e8a47cf766a39f981b3a2de`、HTTP 200。位置: `src/zeep/xsd/elements/element.py:260–298`。

```text
"Missing element %s"
```

## AsyncAPI

<a id="y1"></a>

### Y1

宣言とアプリケーション対応の規定。

出典: [asyncapi/spec/spec/asyncapi.md](https://raw.githubusercontent.com/asyncapi/spec/1dd65fd2c1ed13f06365c1e870c61cdc82d8a981/spec/asyncapi.md)。commit `1dd65fd2c1ed13f06365c1e870c61cdc82d8a981`、HTTP 200。位置: `spec/asyncapi.md:186–186`。

```text
everything that is defined in an AsyncAPI document MUST be used
```

<a id="y2"></a>

### Y2

取得したparserは宣言文書の検査経路。

出典: [asyncapi/parser-js/packages/parser/src/validate.ts](https://raw.githubusercontent.com/asyncapi/parser-js/e38319f82cf3bc42097f95035c2917ccbae8e77f/packages/parser/src/validate.ts)。commit `e38319f82cf3bc42097f95035c2917ccbae8e77f`、HTTP 200。位置: `packages/parser/src/validate.ts:46–79`。

```text
spectral.runWithResolved(document, {  });
```

## SLA / SLO

<a id="s1"></a>

### S1

cost/currency/billing語彙。

出典: [isa-group/SLA4OAI-Specification/versions/1.0.0-Draft.md](https://raw.githubusercontent.com/isa-group/SLA4OAI-Specification/1f5dd38d6efd5b8c7ef68e01620a8abbe2f01626/versions/1.0.0-Draft.md)。commit `1f5dd38d6efd5b8c7ef68e01620a8abbe2f01626`、HTTP 200。位置: `versions/1.0.0-Draft.md:217–224`。

```text
Units of cost associated with this service.
```

<a id="s2"></a>

### S2

rateとquotaの語彙。

出典: [isa-group/SLA4OAI-Specification/versions/1.0.0-Draft.md](https://raw.githubusercontent.com/isa-group/SLA4OAI-Specification/1f5dd38d6efd5b8c7ef68e01620a8abbe2f01626/versions/1.0.0-Draft.md)。commit `1f5dd38d6efd5b8c7ef68e01620a8abbe2f01626`、HTTP 200。位置: `versions/1.0.0-Draft.md:257–265`。

```text
Rates are limits computed in **dynamic** time windows
```

<a id="s3"></a>

### S3

検査対象は宣言object。catch時nullを返す。

出典: [isa-group/sla4oai-analyzer/analyzer/operations/P0-syntax.js](https://raw.githubusercontent.com/isa-group/sla4oai-analyzer/2262457461160c6c608b6b822e48da7004d2bc49/analyzer/operations/P0-syntax.js)。commit `2262457461160c6c608b6b822e48da7004d2bc49`、HTTP 200。位置: `analyzer/operations/P0-syntax.js:21–29`。

```text
syntax.validate(sla4oaiObject, sla4oaiSchema);
```

<a id="s4"></a>

### S4

利用者の要求と宣言上の上限の比較。実消費計測ではない。

出典: [isa-group/sla4oai-analyzer/analyzer/operations/P3-compliance.js](https://raw.githubusercontent.com/isa-group/sla4oai-analyzer/2262457461160c6c608b6b822e48da7004d2bc49/analyzer/operations/P3-compliance.js)。commit `2262457461160c6c608b6b822e48da7004d2bc49`、HTTP 200。位置: `analyzer/operations/P3-compliance.js:8–25`。

```text
userNeed[userNeedMetric].max <= limit
```

<a id="s5"></a>

### S5

SLOのthreshold/target/time window。

出典: [OpenSLO/OpenSLO/README.md](https://raw.githubusercontent.com/OpenSLO/OpenSLO/e74b589cc98b98a5413611176d659a72318e7519/README.md)。commit `e74b589cc98b98a5413611176d659a72318e7519`、HTTP 200。位置: `README.md:265–276`。

```text
op: lte | gte | lt | gt
```

<a id="s6"></a>

### S6

SlothはOpenSLO v1alphaを受理、v1との版差。

出典: [slok/sloth/internal/storage/io/openslo.go](https://raw.githubusercontent.com/slok/sloth/8a3be4fab79defa4448d09d91b48422615980b05/internal/storage/io/openslo.go)。commit `8a3be4fab79defa4448d09d91b48422615980b05`、HTTP 200。位置: `internal/storage/io/openslo.go:51–70`。

```text
s.APIVersion != openslov1alpha.APIVersion
```

<a id="s7"></a>

### S7

ratio限定の実装。任意OpenSLO SLOに一般化しない。

出典: [slok/sloth/internal/storage/io/openslo.go](https://raw.githubusercontent.com/slok/sloth/8a3be4fab79defa4448d09d91b48422615980b05/internal/storage/io/openslo.go)。commit `8a3be4fab79defa4448d09d91b48422615980b05`、HTTP 200。位置: `internal/storage/io/openslo.go:124–146`。

```text
if slo.RatioMetrics == nil {
```

## 実行した適合検査

icontractの固定ソース `3e733f9e790359036c4da2cc550c599107710b60` を、調査用の一時Python環境から読み込んだ。依存は `asttokens==2.4.1`、`typing_extensions==4.12.2` を固定して導入した。製品環境やPDA本体へのインストールではない。

| 入力・設定 | 実際の結果 | 確認できる範囲 |
|---|---|---|
| `require(x > 0)` に `x=-1` | `ViolationError`、本体呼出記録は空 | 前条件違反を本体実行前に拒否 |
| `ensure(result > 0)` の関数が `-1` を返す | `ViolationError`、本体呼出記録 `[1]` | 後条件違反を本体実行後に検出 |
| 同じ負の入力、`enabled=False` | `-1` をそのまま返す | 宣言があっても検査の無効化で通る |

再現スクリプト・結果は調査時の `/private/tmp/pda-research-02/check_contract.py` と `check_contract.result.json`。引用台帳は同ディレクトリの `manifest.json`（GitHub資料）と `external-manifest.json`（PDF/HTML）。一時ファイルが消えても資料を再取得できるよう、根拠のURL・版・位置・引用は本ファイルに全件残した。

その他の実装は固定ソースの検査経路を読んだ。MCP/A2Aサーバー、Kubernetes/Nix、Pony/Koka compiler、CHERI emulator、Sloth/Prometheus、CNETの実行試験はしていない。

## 検索の再現範囲

A2A `specification/a2a.proto`（commit `afda8316c64951a2ecb2a0d3d10867405d2b4095`）全812行に対する大文字小文字を区別しない正規表現 `cost|price|pricing|budget|quota|rate.?limit` は0件。MCPの同様の単語検索はschema全体に `costPriority` を見つけるが、Toolの料金を表す欄とは異なる（M12）。未発見の判定をschema全体や他の系譜の語彙の不在へ拡張しない。

HTTP失敗は本文6節に記録。失敗したDafny/cheriot-sailの内容は引用していない。FIPAはアーカイブ版、CHERI実装はQEMU、CNETコードは原著者の公開PDFを実際に取得している。
