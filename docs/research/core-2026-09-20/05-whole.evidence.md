# 第5本 — 根拠集

取得日: 2026-09-20 JST。対象要件commit: `cdd90e945d938769aefa17a2b8de3236647f6bdc`。本文は [05-whole.md](05-whole.md)。

本書の「本体確認」は、担当調査者が公開一次資料の本文または固定実装を取得して読んだことを指す。前4本の内容は報告として扱い、ここへ元資料を再取得した体裁で転載しない。独立再取得レビューは親が別に作成する。

コードはGitHubのHEADを `git ls-remote` で40桁SHAへ解決し、同SHAのcodeloadアーカイブを取得した。引用行は展開したソースから数えた1始まりの行であり、以下のraw URLは同SHAを指す。PDFは物理ページ（1始まり）とSHA256で固定した。HTMLはページ内見出しと取得HTMLのSHA256で固定した。改行・連続空白だけを正規化して逐語引用を照合した。式の要約は引用とは分けた。

引用台帳はコード30件、PDF25件、HTML5件。再取得用JSONと原資料は調査用一時領域 `/private/tmp/pda-research-05/` に置いた。再現に必要なURL・SHA・位置・引用は本ファイルにも全件収録する。

## 固定実装の一覧

| repository | commit | 本書での範囲 |
|---|---|---|
| [uniba-swt/ia-toolset](https://github.com/uniba-swt/ia-toolset/tree/076b7343591904d65182bd85d14e54ecdee2cc11) | `076b7343591904d65182bd85d14e54ecdee2cc11` | 本文に記載した処理のみ。全製品や全利用経路の認定ではない |
| [lm-sys/RouteLLM](https://github.com/lm-sys/RouteLLM/tree/0b64fdafe049e596a3f5657c219329f24af24198) | `0b64fdafe049e596a3f5657c219329f24af24198` | 本文に記載した処理のみ。全製品や全利用経路の認定ではない |
| [VowpalWabbit/vowpal_wabbit](https://github.com/VowpalWabbit/vowpal_wabbit/tree/13eae731a75066220c5e270adb8ca1dd7d9a857e) | `13eae731a75066220c5e270adb8ca1dd7d9a857e` | 本文に記載した処理のみ。全製品や全利用経路の認定ではない |
| [dbos-inc/dbos-transact-py](https://github.com/dbos-inc/dbos-transact-py/tree/a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59) | `a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59` | 本文に記載した処理のみ。全製品や全利用経路の認定ではない |
| [yawlfoundation/yawl](https://github.com/yawlfoundation/yawl/tree/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f) | `f007a2d0f345dcce6ee702a76a32b48ceaf31f5f` | 本文に記載した処理のみ。全製品や全利用経路の認定ではない |
| [dbos-inc/dbos-vercel-ai](https://github.com/dbos-inc/dbos-vercel-ai/tree/10ce52a8030ec0307946dd80d655da7fb0b842a2) | `10ce52a8030ec0307946dd80d655da7fb0b842a2` | 取得のみ。Python SDKの保証をこのTypeScript adapterへ移さない |

## 固定PDFの一覧

全ファイルHTTP 200。arXivのversionなしURLも取得時のバイト列をSHA256で識別する。改訂後の同URLが同一本文であるとは扱わない。

| 資料 | 物理ページ数 | 取得URL | SHA256 |
|---|---|---|---|
| Interface Automata for Shared Memory（d-nb配布版、2021/2022） | 36 | [配布元](https://d-nb.info/1269288245/34) | `7d6e665b83b845ae3157ff3b770997ad2eb973f93d10d1a97851dfcbc7eaab3b` |
| RouteLLM（arXiv:2406.18665v4、2025-02-23） | 16 | [配布元](https://arxiv.org/pdf/2406.18665) | `c9bc9c8171cab95bb3832cde8767c6b5e0925cd62930e51ddbd60d7cb2616741` |
| Durability, Consistency and Correctness in Data-Oriented Workflow Systems（CIDR 2026） | 7 | [配布元](https://www.vldb.org/cidrdb/papers/2026/p9-stonebraker.pdf) | `62de5ac19de835bc9ac99ac278f2e680387b5de15fbecace17a53285e9d1e280` |
| YAWL User Manual 5.1 | 250 | [配布元](https://yawlfoundation.github.io/assets/files/YAWLUserManual5.1.pdf) | `1e2c4c67e1c345a083cf341fa0324a9d4fe2a50391ea46c7b98b0663a453c35c` |
| Multiparty Session Types for Safe Runtime Adaptation in an Actor Language（ECOOP 2021） | 30 | [配布元](https://drops.dagstuhl.de/storage/00lipics/lipics-vol194-ecoop2021/LIPIcs.ECOOP.2021.10/LIPIcs.ECOOP.2021.10.pdf) | `d23f6f46ee1dd1b2adc22dec90fed76b17c0e8c51d0cc4219567fc2c321a4e77` |
| 同論文Artifact Description（DARTS 7.2.8、2021） | 2 | [配布元](https://drops.dagstuhl.de/storage/05darts/darts-vol007/darts-vol007-issue002_ecoop2021/DARTS.7.2.8/DARTS.7.2.8.pdf) | `c8c1e51d1d3c6c647f8a89556c8f1ff2462086ea2b7af3410c40ebd73dd0c3e7` |
| Open Multiparty Sessions（2019） | 20 | [配布元](https://arxiv.org/pdf/1909.05972) | `56d89e80abc79ee6d901406406c2a9d71e66a5730ca594762b047931e5d2f8f8` |
| The Gaia Methodology for Agent-Oriented Analysis and Design（2000） | 26 | [配布元](https://www.cs.ox.ac.uk/people/michael.wooldridge/pubs/jaamas2000b.pdf) | `d560d4540531077df2c26226b3a340615eadd791b932ccf6c0424b9f38f46528` |
| Integrating Diverse Reasoning Methods in the BB1 Blackboard Control Architecture（AAAI 1987） | 6 | [配布元](https://cdn.aaai.org/AAAI/1987/AAAI87-006.pdf) | `1c24d0f18af8fd1095b69e8c0aab88d4b6f323b5cab963c91f2dbf6912b0bd0c` |
| Principles of Metareasoning（大学アーカイブの1頁断片） | 1 | [配布元](https://iiif.library.cmu.edu/file/Newell_box00014_fld01011_doc0001/Newell_box00014_fld01011_doc0001.pdf) | `957ade260771c5ff84ed17210896806535b0198e192b3f7de93d40937bcc01a5` |
| Rainbow: Architecture-Based Self-Adaptation with Reusable Infrastructure（IEEE Computer 2004） | 9 | [配布元](https://www.cs.cmu.edu/afs/cs/project/able/ftp/computer04/article.pdf) | `8bf56dded05f6992afda3712ed5f6c01cdef10e55c780b21673c4be96584aac4` |
| AIOS: LLM Agent Operating System（取得PDF） | 34 | [配布元](https://arxiv.org/pdf/2403.16971) | `6ac427d318869e82ea5dc2f1e4b1db91a482c640d527cc3f3812eb2d3f835b12` |
| FrugalGPT（arXiv:2305.05176、取得PDF） | 13 | [配布元](https://arxiv.org/pdf/2305.05176) | `035ae8b90333dad8b7817fc8f55e7c4cbca435368c5c1a4dbf7bba9e5db87473` |
| Mixture-of-Agents（arXiv:2406.04692v1、2024-06-07） | 15 | [配布元](https://arxiv.org/pdf/2406.04692) | `b7bc82e95971e60f1ad54c8accd2d2fa101e8b43adb887511bf52c7e98e83a7d` |
| Beyond Message Passing: A Semantic View of Agent Communication Protocols（arXiv:2604.02369v3、2026-04-13） | 34 | [配布元](https://arxiv.org/pdf/2604.02369) | `d65a5ba667a1333cea7e158dc7259216fc54aa02c741826a47c4cc1ad6abf416` |
| CaMeL: Learning Method Preconditions for HTN Planning（AIPS 2002） | 10 | [配布元](https://www.cs.umd.edu/~nau/papers/ilghami2002camel.pdf) | `ed2bfe4a88b5e00049e654c16ba05dc78006182f8dede7937f33c4ebde6e842e` |
| A Formal Analysis and Taxonomy of Task Allocation in Multi-Robot Systems（2004） | 16 | [配布元](https://web2.qatar.cmu.edu/~gdicaro/15382/additional/task-allocation-taxonomy.pdf) | `adc96455d8ada482ed7d4496be368dc723030b22fc692a010160f6ee2773bd1c` |
| An Analysis of Time-Dependent Planning（AAAI 1988） | 6 | [配布元](https://cdn.aaai.org/AAAI/1988/AAAI88-009.pdf) | `6559c7f4933aa178cb0de5d716c3fb3526c24b837997f31235a013aeaab56102` |

## コードの逐語引用と位置

### IA1

1. 根拠: I/O signature不一致拒否とBES solver結果。
2. 固定位置: `uniba-swt/ia-toolset@076b7343591904d65182bd85d14e54ecdee2cc11`、`ialib/src/main/kotlin/ialib/simpleia/refinement/bes/AbstractBesRefinementOperation.kt:45-64`。
3. URL: [raw source](https://raw.githubusercontent.com/uniba-swt/ia-toolset/076b7343591904d65182bd85d14e54ecdee2cc11/ialib/src/main/kotlin/ialib/simpleia/refinement/bes/AbstractBesRefinementOperation.kt) / [行付き表示](https://github.com/uniba-swt/ia-toolset/blob/076b7343591904d65182bd85d14e54ecdee2cc11/ialib/src/main/kotlin/ialib/simpleia/refinement/bes/AbstractBesRefinementOperation.kt#L45-L64)。

```text
throw CoreException("Input and output sets are not equal ($s1 -- $s2)")
```

### IA2

1. 根拠: 遷移のmatching familyが無い場合FALSE。
2. 固定位置: `uniba-swt/ia-toolset@076b7343591904d65182bd85d14e54ecdee2cc11`、`ialib/src/main/kotlin/ialib/iam/refinement/MemBesFormulaBuilder.kt:63-110`。
3. URL: [raw source](https://raw.githubusercontent.com/uniba-swt/ia-toolset/076b7343591904d65182bd85d14e54ecdee2cc11/ialib/src/main/kotlin/ialib/iam/refinement/MemBesFormulaBuilder.kt) / [行付き表示](https://github.com/uniba-swt/ia-toolset/blob/076b7343591904d65182bd85d14e54ecdee2cc11/ialib/src/main/kotlin/ialib/iam/refinement/MemBesFormulaBuilder.kt#L63-L110)。

```text
if (familyStep.errorNoFamilies)
```

### IA3

1. 根拠: 前条件/後条件の含意をSMTで検査。
2. 固定位置: `uniba-swt/ia-toolset@076b7343591904d65182bd85d14e54ecdee2cc11`、`ialib/src/main/kotlin/ialib/iam/simulation/RefinementFamilyProvider.kt:118-155`。
3. URL: [raw source](https://raw.githubusercontent.com/uniba-swt/ia-toolset/076b7343591904d65182bd85d14e54ecdee2cc11/ialib/src/main/kotlin/ialib/iam/simulation/RefinementFamilyProvider.kt) / [行付き表示](https://github.com/uniba-swt/ia-toolset/blob/076b7343591904d65182bd85d14e54ecdee2cc11/ialib/src/main/kotlin/ialib/iam/simulation/RefinementFamilyProvider.kt#L118-L155)。

```text
if (!satImplies(specStep.preCond, or))
```

### IA4

1. 根拠: IAMがBES refinement経路を使用。
2. 固定位置: `uniba-swt/ia-toolset@076b7343591904d65182bd85d14e54ecdee2cc11`、`swtia/src/main/kotlin/swtia/sys/iam/IamRuntimeProvider.kt:85-99`。
3. URL: [raw source](https://raw.githubusercontent.com/uniba-swt/ia-toolset/076b7343591904d65182bd85d14e54ecdee2cc11/swtia/src/main/kotlin/swtia/sys/iam/IamRuntimeProvider.kt) / [行付き表示](https://github.com/uniba-swt/ia-toolset/blob/076b7343591904d65182bd85d14e54ecdee2cc11/swtia/src/main/kotlin/swtia/sys/iam/IamRuntimeProvider.kt#L85-L99)。

```text
MemBesRefinementOperation
```

### RT1

1. 根拠: threshold範囲の実行時拒否。
2. 固定位置: `lm-sys/RouteLLM@0b64fdafe049e596a3f5657c219329f24af24198`、`routellm/controller.py:79-91`。
3. URL: [raw source](https://raw.githubusercontent.com/lm-sys/RouteLLM/0b64fdafe049e596a3f5657c219329f24af24198/routellm/controller.py) / [行付き表示](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/routellm/controller.py#L79-L91)。

```text
if not 0 <= threshold <= 1:
```

### RT2

1. 根拠: 値とthresholdによる二者択一。
2. 固定位置: `lm-sys/RouteLLM@0b64fdafe049e596a3f5657c219329f24af24198`、`routellm/routers/routers.py:41-45`。
3. URL: [raw source](https://raw.githubusercontent.com/lm-sys/RouteLLM/0b64fdafe049e596a3f5657c219329f24af24198/routellm/routers/routers.py) / [行付き表示](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/routellm/routers/routers.py#L41-L45)。

```text
return routed_pair.strong
```

### RT3

1. 根拠: matrix factorization推論は保存済みmodel。
2. 固定位置: `lm-sys/RouteLLM@0b64fdafe049e596a3f5657c219329f24af24198`、`routellm/routers/routers.py:231-242`。
3. URL: [raw source](https://raw.githubusercontent.com/lm-sys/RouteLLM/0b64fdafe049e596a3f5657c219329f24af24198/routellm/routers/routers.py) / [行付き表示](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/routellm/routers/routers.py#L231-L242)。

```text
self.model = self.model.eval().to(device)
```

### RT4

1. 根拠: routing判定に使う最後のmessageと送信するmessagesを区別。
2. 固定位置: `lm-sys/RouteLLM@0b64fdafe049e596a3f5657c219329f24af24198`、`routellm/controller.py:105-119`。
3. URL: [raw source](https://raw.githubusercontent.com/lm-sys/RouteLLM/0b64fdafe049e596a3f5657c219329f24af24198/routellm/controller.py) / [行付き表示](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/routellm/controller.py#L105-L119)。

```text
prompt = messages[-1]["content"]
```

### VW1

1. 根拠: reward入力の学習と推論、epsilon分布構築。
2. 固定位置: `VowpalWabbit/vowpal_wabbit@13eae731a75066220c5e270adb8ca1dd7d9a857e`、`vowpalwabbit/core/src/reductions/cb/cb_explore_adf_greedy.cc:48-82`。
3. URL: [raw source](https://raw.githubusercontent.com/VowpalWabbit/vowpal_wabbit/13eae731a75066220c5e270adb8ca1dd7d9a857e/vowpalwabbit/core/src/reductions/cb/cb_explore_adf_greedy.cc) / [行付き表示](https://github.com/VowpalWabbit/vowpal_wabbit/blob/13eae731a75066220c5e270adb8ca1dd7d9a857e/vowpalwabbit/core/src/reductions/cb/cb_explore_adf_greedy.cc#L48-L82)。

```text
base.learn(examples);
```

### VW2

1. 根拠: 設定の範囲拒否。NaN等全入力の検証とはしない。
2. 固定位置: `VowpalWabbit/vowpal_wabbit@13eae731a75066220c5e270adb8ca1dd7d9a857e`、`vowpalwabbit/core/src/reductions/cb/cb_explore_adf_greedy.cc:148-161`。
3. URL: [raw source](https://raw.githubusercontent.com/VowpalWabbit/vowpal_wabbit/13eae731a75066220c5e270adb8ca1dd7d9a857e/vowpalwabbit/core/src/reductions/cb/cb_explore_adf_greedy.cc) / [行付き表示](https://github.com/VowpalWabbit/vowpal_wabbit/blob/13eae731a75066220c5e270adb8ca1dd7d9a857e/vowpalwabbit/core/src/reductions/cb/cb_explore_adf_greedy.cc#L148-L161)。

```text
THROW("The value of epsilon must be in [0,1]")
```

### VW3

1. 根拠: ADFフィードバック形式の検査。
2. 固定位置: `VowpalWabbit/vowpal_wabbit@13eae731a75066220c5e270adb8ca1dd7d9a857e`、`vowpalwabbit/core/src/reductions/cb/cb_adf.cc:58-101`。
3. URL: [raw source](https://raw.githubusercontent.com/VowpalWabbit/vowpal_wabbit/13eae731a75066220c5e270adb8ca1dd7d9a857e/vowpalwabbit/core/src/reductions/cb/cb_adf.cc) / [行付き表示](https://github.com/VowpalWabbit/vowpal_wabbit/blob/13eae731a75066220c5e270adb8ca1dd7d9a857e/vowpalwabbit/core/src/reductions/cb/cb_adf.cc#L58-L101)。

```text
if (ec->l.cb.costs.size() > 1)
```

### VW4

1. 根拠: model保存は呼出者が明示実行。
2. 固定位置: `VowpalWabbit/vowpal_wabbit@13eae731a75066220c5e270adb8ca1dd7d9a857e`、`python/vowpalwabbit/pyvw.py:794-804`。
3. URL: [raw source](https://raw.githubusercontent.com/VowpalWabbit/vowpal_wabbit/13eae731a75066220c5e270adb8ca1dd7d9a857e/python/vowpalwabbit/pyvw.py) / [行付き表示](https://github.com/VowpalWabbit/vowpal_wabbit/blob/13eae731a75066220c5e270adb8ca1dd7d9a857e/python/vowpalwabbit/pyvw.py#L794-L804)。

```text
pylibvw.vw.save(self, str(filename))
```

### DB1

1. 根拠: 記録済output/errorを再利用、無ければNoResult。
2. 固定位置: `dbos-inc/dbos-transact-py@a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59`、`dbos/_core.py:2297-2330`。
3. URL: [raw source](https://raw.githubusercontent.com/dbos-inc/dbos-transact-py/a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59/dbos/_core.py) / [行付き表示](https://github.com/dbos-inc/dbos-transact-py/blob/a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59/dbos/_core.py#L2297-L2330)。

```text
return NoResult()
```

### DB2

1. 根拠: 外部処理→serialize→recordの順、未記録区間あり。
2. 固定位置: `dbos-inc/dbos-transact-py@a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59`、`dbos/_core.py:2265-2295`。
3. URL: [raw source](https://raw.githubusercontent.com/dbos-inc/dbos-transact-py/a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59/dbos/_core.py) / [行付き表示](https://github.com/dbos-inc/dbos-transact-py/blob/a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59/dbos/_core.py#L2265-L2295)。

```text
output = func()
```

### DB3

1. 根拠: workflow_id/function_idで履歴照合し名前違いを拒否。
2. 固定位置: `dbos-inc/dbos-transact-py@a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59`、`dbos/_sys_db.py:3153-3216`。
3. URL: [raw source](https://raw.githubusercontent.com/dbos-inc/dbos-transact-py/a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59/dbos/_sys_db.py) / [行付き表示](https://github.com/dbos-inc/dbos-transact-py/blob/a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59/dbos/_sys_db.py#L3153-L3216)。

```text
if function_name != recorded_function_name:
```

### YW1

1. 根拠: 現在データで条件分岐し最後に満たす規則を返す。
2. 固定位置: `yawlfoundation/yawl@f007a2d0f345dcce6ee702a76a32b48ceaf31f5f`、`src/org/yawlfoundation/yawl/worklet/rdr/RdrNode.java:268-299`。
3. URL: [raw source](https://raw.githubusercontent.com/yawlfoundation/yawl/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/rdr/RdrNode.java) / [行付き表示](https://github.com/yawlfoundation/yawl/blob/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/rdr/RdrNode.java#L268-L299)。

```text
pair = new RdrPair(lastTrueNode, this);
```

### YW2

1. 根拠: cornerstoneから挿入位置を決定、親と同じノード拒否、永続化。
2. 固定位置: `yawlfoundation/yawl@f007a2d0f345dcce6ee702a76a32b48ceaf31f5f`、`src/org/yawlfoundation/yawl/worklet/rdr/Rdr.java:204-241`。
3. URL: [raw source](https://raw.githubusercontent.com/yawlfoundation/yawl/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/rdr/Rdr.java) / [行付き表示](https://github.com/yawlfoundation/yawl/blob/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/rdr/Rdr.java#L204-L241)。

```text
if (parent.hasIdenticalContent(node))
```

### YW3

1. 根拠: rule種別、結論と参照workletを検証。
2. 固定位置: `yawlfoundation/yawl@f007a2d0f345dcce6ee702a76a32b48ceaf31f5f`、`src/org/yawlfoundation/yawl/worklet/support/WorkletGateway.java:292-320`。
3. URL: [raw source](https://raw.githubusercontent.com/yawlfoundation/yawl/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/support/WorkletGateway.java) / [行付き表示](https://github.com/yawlfoundation/yawl/blob/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/support/WorkletGateway.java#L292-L320)。

```text
if (rType == null) return fail("Invalid rule type: " + rTypeStr);
```

### IA5

1. 根拠: 実行される含意検査の実体。
2. 固定位置: `uniba-swt/ia-toolset@076b7343591904d65182bd85d14e54ecdee2cc11`、`ialib/src/main/kotlin/ialib/iam/expr/solver/DefaultSmtSolver.kt:42-76`。
3. URL: [raw source](https://raw.githubusercontent.com/uniba-swt/ia-toolset/076b7343591904d65182bd85d14e54ecdee2cc11/ialib/src/main/kotlin/ialib/iam/expr/solver/DefaultSmtSolver.kt) / [行付き表示](https://github.com/uniba-swt/ia-toolset/blob/076b7343591904d65182bd85d14e54ecdee2cc11/ialib/src/main/kotlin/ialib/iam/expr/solver/DefaultSmtSolver.kt#L42-L76)。

```text
solveForAllImplies
```

### RT5

1. 根拠: MFはembedding provider/model依存を残す。
2. 固定位置: `lm-sys/RouteLLM@0b64fdafe049e596a3f5657c219329f24af24198`、`routellm/routers/matrix_factorization/model.py:88-127`。
3. URL: [raw source](https://raw.githubusercontent.com/lm-sys/RouteLLM/0b64fdafe049e596a3f5657c219329f24af24198/routellm/routers/matrix_factorization/model.py) / [行付き表示](https://github.com/lm-sys/RouteLLM/blob/0b64fdafe049e596a3f5657c219329f24af24198/routellm/routers/matrix_factorization/model.py#L88-L127)。

```text
OPENAI_CLIENT.embeddings.create(input=[prompt], model=self.embedding_model)
```

### VW5

1. 根拠: 観測cost入力から学習方式へdispatch。
2. 固定位置: `VowpalWabbit/vowpal_wabbit@13eae731a75066220c5e270adb8ca1dd7d9a857e`、`vowpalwabbit/core/src/reductions/cb/cb_adf.cc:241-268`。
3. URL: [raw source](https://raw.githubusercontent.com/VowpalWabbit/vowpal_wabbit/13eae731a75066220c5e270adb8ca1dd7d9a857e/vowpalwabbit/core/src/reductions/cb/cb_adf.cc) / [行付き表示](https://github.com/VowpalWabbit/vowpal_wabbit/blob/13eae731a75066220c5e270adb8ca1dd7d9a857e/vowpalwabbit/core/src/reductions/cb/cb_adf.cc#L241-L268)。

```text
_gen_cs_dr.known_cost = VW::get_observed_cost_or_default_cb_adf(ec_seq);
```

### VW6

1. 根拠: 公式simulation例は選択→cost→learnを反復する。
2. 固定位置: `VowpalWabbit/vowpal_wabbit@13eae731a75066220c5e270adb8ca1dd7d9a857e`、`python/docs/source/tutorials/python_Simulating_a_news_personalization_scenario_using_Contextual_Bandits.ipynb:281-309`。
3. URL: [raw source](https://raw.githubusercontent.com/VowpalWabbit/vowpal_wabbit/13eae731a75066220c5e270adb8ca1dd7d9a857e/python/docs/source/tutorials/python_Simulating_a_news_personalization_scenario_using_Contextual_Bandits.ipynb) / [行付き表示](https://github.com/VowpalWabbit/vowpal_wabbit/blob/13eae731a75066220c5e270adb8ca1dd7d9a857e/python/docs/source/tutorials/python_Simulating_a_news_personalization_scenario_using_Contextual_Bandits.ipynb#L281-L309)。

```text
vw.learn(vw_format)
```

### DB4

1. 根拠: step結果を本体実行前に照合する。workflow外では通常関数。
2. 固定位置: `dbos-inc/dbos-transact-py@a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59`、`dbos/_core.py:2356-2410`。
3. URL: [raw source](https://raw.githubusercontent.com/dbos-inc/dbos-transact-py/a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59/dbos/_core.py) / [行付き表示](https://github.com/dbos-inc/dbos-transact-py/blob/a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59/dbos/_core.py#L2356-L2410)。

```text
.intercept(check_existing_result, dbos=dbos)
```

### DB5

1. 根拠: 記録済結果があるなら関数本体を呼ばないinterceptor。
2. 固定位置: `dbos-inc/dbos-transact-py@a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59`、`dbos/_outcome.py:142-162`。
3. URL: [raw source](https://raw.githubusercontent.com/dbos-inc/dbos-transact-py/a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59/dbos/_outcome.py) / [行付き表示](https://github.com/dbos-inc/dbos-transact-py/blob/a041d4d5d1e69a3b5ce1b044c6ec2033850e7c59/dbos/_outcome.py#L142-L162)。

```text
if isinstance(intercepted, NoResult):
```

### YW4

1. 根拠: 条件評価後workletをcheckout/launch。
2. 固定位置: `yawlfoundation/yawl@f007a2d0f345dcce6ee702a76a32b48ceaf31f5f`、`src/org/yawlfoundation/yawl/worklet/WorkletService.java:388-420`。
3. URL: [raw source](https://raw.githubusercontent.com/yawlfoundation/yawl/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/WorkletService.java) / [行付き表示](https://github.com/yawlfoundation/yawl/blob/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/WorkletService.java#L388-L420)。

```text
RdrPair pair = _rdr.evaluate(wir);
```

### YW5

1. 根拠: 先に既存worklet取消→規則再評価→新規起動。履歴巻戻しではない。
2. 固定位置: `yawlfoundation/yawl@f007a2d0f345dcce6ee702a76a32b48ceaf31f5f`、`src/org/yawlfoundation/yawl/worklet/WorkletService.java:650-679`。
3. URL: [raw source](https://raw.githubusercontent.com/yawlfoundation/yawl/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/WorkletService.java) / [行付き表示](https://github.com/yawlfoundation/yawl/blob/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/WorkletService.java#L650-L679)。

```text
if (! cancelWorkletSet(runners))
```

### YW6

1. 根拠: event記録は永続化有効時。rule変更前後と理由の必須台帳ではない。
2. 固定位置: `yawlfoundation/yawl@f007a2d0f345dcce6ee702a76a32b48ceaf31f5f`、`src/org/yawlfoundation/yawl/worklet/support/EventLogger.java:37-69`。
3. URL: [raw source](https://raw.githubusercontent.com/yawlfoundation/yawl/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/support/EventLogger.java) / [行付き表示](https://github.com/yawlfoundation/yawl/blob/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/support/EventLogger.java#L37-L69)。

```text
if (Persister.getInstance().isPersisting())
```

### YW7

1. 根拠: worklet実行eventの時刻はある。
2. 固定位置: `yawlfoundation/yawl@f007a2d0f345dcce6ee702a76a32b48ceaf31f5f`、`src/org/yawlfoundation/yawl/worklet/support/WorkletEvent.java:35-57`。
3. URL: [raw source](https://raw.githubusercontent.com/yawlfoundation/yawl/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/support/WorkletEvent.java) / [行付き表示](https://github.com/yawlfoundation/yawl/blob/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/support/WorkletEvent.java#L35-L57)。

```text
_stamp = _sdfe.format(new Date());
```

### YW8

1. 根拠: 規則削除は子を再接ぎ木。変更前snapshotへの復元と区別。
2. 固定位置: `yawlfoundation/yawl@f007a2d0f345dcce6ee702a76a32b48ceaf31f5f`、`src/org/yawlfoundation/yawl/worklet/rdr/RdrTree.java:193-203`。
3. URL: [raw source](https://raw.githubusercontent.com/yawlfoundation/yawl/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/rdr/RdrTree.java) / [行付き表示](https://github.com/yawlfoundation/yawl/blob/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/rdr/RdrTree.java#L193-L203)。

```text
graft(node.getTrueChild());
```

### YW9

1. 根拠: 起動と選択ルールIDの対応。成果を親workitemへcheckin。
2. 固定位置: `yawlfoundation/yawl@f007a2d0f345dcce6ee702a76a32b48ceaf31f5f`、`src/org/yawlfoundation/yawl/worklet/WorkletService.java:448-494`。
3. URL: [raw source](https://raw.githubusercontent.com/yawlfoundation/yawl/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/WorkletService.java) / [行付き表示](https://github.com/yawlfoundation/yawl/blob/f007a2d0f345dcce6ee702a76a32b48ceaf31f5f/src/org/yawlfoundation/yawl/worklet/WorkletService.java#L448-L494)。

```text
runner.setRuleNodeID(pair.getLastTrueNode().getNodeId());
```

## PDFの逐語引用と位置

### PIA1

1. 資料: [Interface Automata for Shared Memory（d-nb配布版、2021/2022）](https://d-nb.info/1269288245/34)、物理p.8。
2. 根拠: Definition7のモデル前提。
3. SHA256: `7d6e665b83b845ae3157ff3b770997ad2eb973f93d10d1a97851dfcbc7eaab3b`。
4. 文脈: Definition 7。入力の前条件の重なりを禁止するdata-determinism等をIAMの前提とする。

> data-deterministic for input actions

### PIA2

1. 資料: [Interface Automata for Shared Memory（d-nb配布版、2021/2022）](https://d-nb.info/1269288245/34)、物理p.9。
2. 根拠: Definition8 refinementの前提。
3. SHA256: `7d6e665b83b845ae3157ff3b770997ad2eb973f93d10d1a97851dfcbc7eaab3b`。
4. 文脈: Definition 8。入力・出力・内部遷移のalternating simulation条件。

> with the same signature

### PIA3

1. 資料: [Interface Automata for Shared Memory（d-nb配布版、2021/2022）](https://d-nb.info/1269288245/34)、物理p.26。
2. 根拠: Corollary18 合成互換性保存。
3. SHA256: `7d6e665b83b845ae3157ff3b770997ad2eb973f93d10d1a97851dfcbc7eaab3b`。
4. 文脈: Corollary 18。前提はPがQをrefineし、QとRがcomposableであること。

> P and R are composable

### PRT

1. 資料: [RouteLLM（arXiv:2406.18665v4、2025-02-23）](https://arxiv.org/pdf/2406.18665)、物理p.3。
2. 根拠: 二者routingの定義。
3. SHA256: `c9bc9c8171cab95bb3832cde8767c6b5e0925cd62930e51ddbd60d7cb2616741`。

> This threshold translates the predicted winning probability into a routing decision

### PDB1

1. 資料: [Durability, Consistency and Correctness in Data-Oriented Workflow Systems（CIDR 2026）](https://www.vldb.org/cidrdb/papers/2026/p9-stonebraker.pdf)、物理p.1。
2. 根拠: 論文のtransaction前提。
3. SHA256: `62de5ac19de835bc9ac99ac278f2e680387b5de15fbecace17a53285e9d1e280`。
4. 文脈: stepがtransactionという論文の仮定。通常Python stepの外部副作用のexactly-onceへ拡張しない。

> we assume a step is a single transaction

### PDB2

1. 資料: [Durability, Consistency and Correctness in Data-Oriented Workflow Systems（CIDR 2026）](https://www.vldb.org/cidrdb/papers/2026/p9-stonebraker.pdf)、物理p.2。
2. 根拠: 完了済み結果とcheckpointの保証範囲。
3. SHA256: `62de5ac19de835bc9ac99ac278f2e680387b5de15fbecace17a53285e9d1e280`。
4. 文脈: 同論文のdurability節。完了済みstepのcheckpointから復旧する説明。

> no completed step will be repeated

### PYW1

1. 資料: [YAWL User Manual 5.1](https://yawlfoundation.github.io/assets/files/YAWLUserManual5.1.pdf)、物理p.182。
2. 根拠: runtimeでworklet追加、元process非変更。
3. SHA256: `1e2c4c67e1c345a083cf341fa0324a9d4fe2a50391ea46c7b98b0663a453c35c`。
4. 文脈: §8.1.1。workitemを別caseで実行するworkletへ置換し、入出力をmappingする。

> selected and invoked, and may be created at any time

### PYW2

1. 資料: [YAWL User Manual 5.1](https://yawlfoundation.github.io/assets/files/YAWLUserManual5.1.pdf)、物理p.196。
2. 根拠: 規則説明欄は任意。
3. SHA256: `1e2c4c67e1c345a083cf341fa0324a9d4fe2a50391ea46c7b98b0663a453c35c`。
4. 文脈: §8.6。cornerstoneは新規規則の挿入位置の判断に使う。Descriptionは実行動作へ影響せず任意。

> may be left empty if desired

### PYW3

1. 資料: [YAWL User Manual 5.1](https://yawlfoundation.github.io/assets/files/YAWLUserManual5.1.pdf)、物理p.103。
2. 根拠: Editor soundness検証の状態空間制限。
3. SHA256: `1e2c4c67e1c345a083cf341fa0324a9d4fe2a50391ea46c7b98b0663a453c35c`。
4. 文脈: §4.11のEditor検証説明。有限状態空間・Maximum Markings上限内の解析と、runtimeでのrule結論検査を区別。

> finite state space

### PEN1

1. 資料: [Multiparty Session Types for Safe Runtime Adaptation in an Actor Language（ECOOP 2021）](https://drops.dagstuhl.de/storage/00lipics/lipics-vol194-ecoop2021/LIPIcs.ECOOP.2021.10/LIPIcs.ECOOP.2021.10.pdf)、物理p.8。
2. 根拠: 同じsession typeのactor置換。
3. SHA256: `d23f6f46ee1dd1b2adc22dec90fed76b17c0e8c51d0cc4219567fc2c321a4e77`。
4. 文脈: §3.4、前ページp.7にbehaviour loop先頭でのreplacement。§3.5（p.8）はcompiler/typecheckerの実装を報告するがコード実体は未検査。

> existing and new actors must follow the same session type

### PEN2

1. 資料: [Multiparty Session Types for Safe Runtime Adaptation in an Actor Language（ECOOP 2021）](https://drops.dagstuhl.de/storage/00lipics/lipics-vol194-ecoop2021/LIPIcs.ECOOP.2021.10/LIPIcs.ECOOP.2021.10.pdf)、物理p.23。
2. 根拠: well-formed programのrole集合前提。
3. SHA256: `d23f6f46ee1dd1b2adc22dec90fed76b17c0e8c51d0cc4219567fc2c321a4e77`。
4. 文脈: Definition 9、Theorem 10。各actorの型がprotocolのroleに対応し、protocolのrole集合は互いに別。

> distinct set of roles

### PEN3

1. 資料: [Multiparty Session Types for Safe Runtime Adaptation in an Actor Language（ECOOP 2021）](https://drops.dagstuhl.de/storage/00lipics/lipics-vol194-ecoop2021/LIPIcs.ECOOP.2021.10/LIPIcs.ECOOP.2021.10.pdf)、物理p.24。
2. 根拠: progressのdiscover前提。
3. SHA256: `d23f6f46ee1dd1b2adc22dec90fed76b17c0e8c51d0cc4219567fc2c321a4e77`。
4. 文脈: Theorem 18。programのprogress、sessionごとのprog、unmatched discover無し等の仮定を含む。

> does not contain an unmatched

### PEN4

1. 資料: [同論文Artifact Description（DARTS 7.2.8、2021）](https://drops.dagstuhl.de/storage/05darts/darts-vol007/darts-vol007-issue002_ecoop2021/DARTS.7.2.8/DARTS.7.2.8.pdf)、物理p.2。
2. 根拠: 配布artifact VMの規模、実体未取得。
3. SHA256: `c8c1e51d1d3c6c647f8a89556c8f1ff2462086ea2b7af3410c40ebd73dd0c3e7`。

> 6.33 GiB

### POP

1. 資料: [Open Multiparty Sessions（2019）](https://arxiv.org/pdf/1909.05972)、物理p.1。
2. 根拠: 互換なsessionをgatewayで接続。
3. SHA256: `56d89e80abc79ee6d901406406c2a9d71e66a5730ca594762b047931e5d2f8f8`。
4. 文脈: 物理11頁Definition 5.3、12頁Definition 5.8/6.1、16頁Theorem 6.7も本文確認。gateway変換は入力/出力に中継通信を加える。session間のprocess compatibilityと型付けが前提。引用自体はp.1。

> lock-freedom is preserved by connection

### PGA

1. 資料: [The Gaia Methodology for Agent-Oriented Analysis and Design（2000）](https://www.cs.ox.ac.uk/people/michael.wooldridge/pubs/jaamas2000b.pdf)、物理p.2。
2. 根拠: Gaia適用範囲。
3. SHA256: `d560d4540531077df2c26226b3a340615eadd791b932ccf6c0424b9f38f46528`。
4. 文脈: 適用範囲として組織関係・能力のstatic性を明示。p.4ではroleとagent個体が一対一とは限らない。

> The organisation structure of the system is static

### PBB

1. 資料: [Integrating Diverse Reasoning Methods in the BB1 Blackboard Control Architecture（AAAI 1987）](https://cdn.aaai.org/AAAI/1987/AAAI87-006.pdf)、物理p.1。
2. 根拠: 動的control planでKSARを選択。
3. SHA256: `1c24d0f18af8fd1095b69e8c0aab88d4b6f323b5cab963c91f2dbf6912b0bd0c`。

> A scheduler sequences the

### PMR

1. 資料: [Principles of Metareasoning（大学アーカイブの1頁断片）](https://iiif.library.cmu.edu/file/Newell_box00014_fld01011_doc0001/Newell_box00014_fld01011_doc0001.pdf)、物理p.1。
2. 根拠: 計算自体をutilityで選択。取得PDFは1頁のみ。
3. SHA256: `957ade260771c5ff84ed17210896806535b0198e192b3f7de93d40937bcc01a5`。
4. 文脈: 取得できた配布PDFは1頁のみ。論文全体の定理や実装を確認したとはしていない。

> derived from the expected effects

### PRB

1. 資料: [Rainbow: Architecture-Based Self-Adaptation with Reusable Infrastructure（IEEE Computer 2004）](https://www.cs.cmu.edu/afs/cs/project/able/ftp/computer04/article.pdf)、物理p.4。
2. 根拠: 監視modelのinvariant違反から適応戦略を起動。
3. SHA256: `8bf56dded05f6992afda3712ed5f6c01cdef10e55c780b21673c4be96584aac4`。

> invariant fails, an adaptation strategy is invoked.

### PAI

1. 資料: [AIOS: LLM Agent Operating System（取得PDF）](https://arxiv.org/pdf/2403.16971)、物理p.4。
2. 根拠: 古典schedulerとLLM coreの分離。
3. SHA256: `6ac427d318869e82ea5dc2f1e4b1db91a482c640d527cc3f3812eb2d3f835b12`。
4. 文脈: §3.2–3.4。LLM coreとschedulerを分離しFIFO/RRを説明。コードの固定commit強制位置は未照合。

> two classic algorithms: First-In-First-Out (FIFO)

### PFG

1. 資料: [FrugalGPT（arXiv:2305.05176、取得PDF）](https://arxiv.org/pdf/2305.05176)、物理p.6。
2. 根拠: 学習最適化の期待費用制約。
3. SHA256: `035ae8b90333dad8b7817fc8f55e7c4cbca435368c5c1a4dbf7bba9e5db87473`。

> average cost is bounded by the budget

### PMO

1. 資料: [Mixture-of-Agents（arXiv:2406.04692v1、2024-06-07）](https://arxiv.org/pdf/2406.04692)、物理p.1。
2. 根拠: 前層成果を後層へ渡す多層推論。
3. SHA256: `b7bc82e95971e60f1ad54c8accd2d2fa101e8b43adb887511bf52c7e98e83a7d`。

> agents in the previous layer as auxiliary information

### PSV

1. 資料: [Beyond Message Passing: A Semantic View of Agent Communication Protocols（arXiv:2604.02369v3、2026-04-13）](https://arxiv.org/pdf/2604.02369)、物理p.7。
2. 根拠: surveyにsyntax invariants語彙あり。証明/実装ではない。
3. SHA256: `d65a5ba667a1333cea7e158dc7259216fc54aa02c741826a47c4cc1ad6abf416`。
4. 文脈: §3.2のsyntactic layer。規約としてversioned mappingとschema/invariant検査を述べる箇所であり、既存全protocolへの実証ではない。

> versioned and deterministic

### PHT

1. 資料: [CaMeL: Learning Method Preconditions for HTN Planning（AIPS 2002）](https://www.cs.umd.edu/~nau/papers/ilghami2002camel.pdf)、物理p.1。
2. 根拠: 成功/失敗traceを用いるHTN method学習の抽象。
3. SHA256: `ed2bfe4a88b5e00049e654c16ba05dc78006182f8dede7937f33c4ebde6e842e`。

> Plan traces that are known to be successful or unsuccessful

### PAL

1. 資料: [A Formal Analysis and Taxonomy of Task Allocation in Multi-Robot Systems（2004）](https://web2.qatar.cmu.edu/~gdicaro/15382/additional/task-allocation-taxonomy.pdf)、物理p.5。
2. 根拠: task allocationを最適割当問題へ対応づける。
3. SHA256: `adc96455d8ada482ed7d4496be368dc723030b22fc692a010160f6ee2773bd1c`。

> optimal assignment problem

### PAT

1. 資料: [An Analysis of Time-Dependent Planning（AAAI 1988）](https://cdn.aaai.org/AAAI/1988/AAAI88-009.pdf)、物理p.1。
2. 根拠: anytimeの中断可能な結果と時間utility。
3. SHA256: `6559c7f4933aa178cb0de5d716c3fb3526c24b837997f31235a013aeaab56102`。

> be interrupted at any point during computation

## HTMLの逐語引用と位置

### HD1

1. URL: [一次資料](https://docs.dbos.dev/python/tutorials/workflow-tutorial)。
2. 位置: Determinism; Workflow Guarantees。
3. 根拠: 同じstep結果で同じinputs/orderを要求。step試行とtransactionを区別。
4. SHA256: `831034ea108a77b963488a4f57745ce339db45334f4c967087db106d0792fb27`。HTTP 200、取得日2026-09-20。

> a workflow function must be deterministic

### HD2

1. URL: [一次資料](https://docs.dbos.dev/python/tutorials/step-tutorial)。
2. 位置: Steps, before Configurable Retries。
3. 根拠: 非決定処理をstepへ。workflow外は通常関数。
4. SHA256: `7e413e083717ac72abc99e62af7a5da79665026dcc59388a3db48e92b14e23fb`。HTTP 200、取得日2026-09-20。

> without checkpoints, retries, or timeouts

### HV

1. URL: [一次資料](https://vowpalwabbit.org/docs/vowpal_wabbit/python/9.0.1/tutorials/python_Contextual_bandits_and_Vowpal_Wabbit.html)。
2. 位置: The contextual bandit problem; Python tutorial。
3. 根拠: 文脈選択学習、保存model読込。
4. SHA256: `6f0af29ed9a590334b14b11a24ac02353315414358f06409bdfbde136767a61c`。HTTP 200、取得日2026-09-20。

> observes a loss/cost/reward for the chosen action only

### HV2

1. URL: [一次資料](https://vowpalwabbit.org/docs/vowpal_wabbit/python/9.0.1/tutorials/python_Contextual_bandits_and_Vowpal_Wabbit.html)。
2. 位置: Input format for --cb_explore_adf。
3. 根拠: 標準ADFの観測ラベル制約。VW3の拒否経路と対応。
4. SHA256: `6f0af29ed9a590334b14b11a24ac02353315414358f06409bdfbde136767a61c`。HTTP 200、取得日2026-09-20。

> label information on precisely one action

### HS

1. URL: [一次資料](https://www.cs.umd.edu/projects/shop/description.html)。
2. 位置: Overview; Publications。
3. 根拠: HTNの抽象と実装の所在。コードの強制位置未確認。
4. SHA256: `db592ef85e722adbf88cf448693930933b905c9a45d02179725c15a802185512`。HTTP 200、取得日2026-09-20。

> ordered task decomposition

<a id="acquisition"></a>

## 取得状態・未取得・未発見

| 対象 | 取得状態 | 本文での扱い |
|---|---|---|
| 上記6 repositories、18種PDF、4種HTML | すべてHTTP 200で取得。コードの引用行、PDFの引用ページ、HTMLの引用文を照合 | 本体確認した範囲に限定 |
| EnsembleS compiler・typechecker本体 | [Artifactの公式所在](https://drops.dagstuhl.de/entities/document/10.4230/DARTS.7.2.8) と[説明PDF](https://drops.dagstuhl.de/storage/05darts/darts-vol007/darts-vol007-issue002_ecoop2021/DARTS.7.2.8/DARTS.7.2.8.pdf) を確認。説明の6.33 GiB VM本体はダウンロード要求を送っていない | 実装の所在はあるが本体未取得。HTTP失敗ではない。定理とコードの対には数えない |
| Open Multiparty Sessionsの対応実装 | 論文はHTTP 200。`Open Multiparty Sessions gateway implementation`、`dynamic participants session types implementation github`で、本文の定理に対応する固定実装の強制箇所は未発見 | 抽象側のみ。実装の世界的な不存在とはしない |
| BB1 / Gaia / HTN / market allocation / metareasoning / Rainbow / AIOS / FrugalGPT / MoA / survey | 本文6節の一次資料を取得。各実装の成立箇所へ対応付ける追跡は限定的または未実施 | 抽象側・実装報告・所在と、コード検査済みの対を分離する |
| Principles of Metareasoning | 公開配布PDFはHTTP 200だが1頁のみ | 導入の断片だけ確認。取得成功を論文全文確認とはしない |
| 第3本で報告されたadapter synthesis sourceの取得失敗 | 本書では再取得していない | 第3本の報告。具体URL/HTTPは03の根拠集を参照 |

今回の証拠採用資料の取得にはHTTP失敗はない。ネットワーク要求をしていない資料にHTTP状態を作らない。codeを追っていない資料を「実装なし」に分類しない。

## 検索と確認の範囲

検索語と到達点は本文6節の表を正本とする。Web検索と公開配布元からの取得を併用し、一次論文・提唱者の公式資料・固定実装を根拠とした。検索結果だけを定理・実装の確認とは扱っていない。

1. 交換可能性: `Gaia roles agent types Wooldridge Jennings`、`AUML Bauer Müller agent roles`、`Interface Automata Shared Memory refinement GitHub`。IAMで対応する検査を追った。Gaia/AUMLのrole図だけをruntime強制とは扱わない。
2. 可変制御: `BB1 control blackboard scheduler`、`HTN SHOP CaMeL learning`、`market-based task allocation Gerkey Mataric`、`metareasoning Russell Wefald`、`anytime Dean Boddy`、`MAPE-K models@run.time Rainbow invariant`。制御モデルの存在と実装確認を分けた。
3. LLM系: `AIOS FIFO Round Robin`、`FrugalGPT cascade`、`RouteLLM threshold router`、`Mixture-of-Agents previous layer`、`agent communication interoperability formal invariant survey`。RouteLLMはMF推論とcontrollerを追い、他資料のベンチマーク結果を不変量とはしなかった。
4. 動的workflow/participants: `YAWL worklets ripple down rules`、`dynamic participants session types`、`EnsembleS compiler artifact`、`Open Multiparty Sessions gateway`。YAWLの追加・検査・選択・取消しまで確認。形式体系の既知roleと新instance、新role、gateway合成を区別した。
5. replay: DBOS公式PythonのWorkflows/Steps資料とPython SDKを確認。TypeScriptのdbos-vercel-aiは取得したが、その依存SDKの実行経路までは追っていないため対に含めなかった。

## 検証の限界

1. 逐語引用と固定位置の照合は行ったが、コンパイル、DBを立てたreplay、model学習の再実験、実行器追加の接続試験はしていない。
2. 論文の証明条件、モデル検査、入力拒否、結果の構築、外部動作の観測を別の保証として扱う。モデルにない外部行為の安全性や、全LLMの出力品質を推測しない。
3. 成立した対にも設定・呼出経路・型・観測範囲の前提がある。任意入力・任意組合せ・任意の外部実行器への保証ではない。
4. 前4本の報告は各reviewの留保を含めて採用した。同一protocolと同一型を同一視せず、宣言の存在から実行時強制を推論せず、未発見を不可能性や自作必須へ変換しない。
