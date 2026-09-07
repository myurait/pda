# PDA v2追補 — 注意の切替と、記憶・skillの部分的忘却

- 更新: 2026-09-07 JST。
- 要求源: オーナーによるv2設計再評価への追加要求。生活の多数のトピックについて、全件想起ではなく適切な注意切替、不要な想起の抑制、抽象化を伴う部分的忘却、休眠skillの再発見を重視する。
- 位置付け: [v2-01ロードマップ](../roadmap/v2-01-whole-system-reassessment.md) R1/R3の要求・比較条件の追補。[既存gap](v2-gap-assessment-2026-09-06.md) G5/G13/G14を具体化する。実装完了、製品採用、記憶の移動・削除・再編の許可ではない。
- 公開根拠の観測日: 2026-09-07。製品についての記述は公式仕様の確認であり、PDAでの統合・性能・安全性の実測ではない。[出典台帳](../research/evidence/attention-lifecycle-2026-09-07/source-map.json)。

## 1. 修正する目的関数

**PDAは、過去を最大限提示する装置ではなく、現在の場面に必要な経験を適切な粒度で働かせる存在である。** 記憶に残すこと、検索候補にすること、モデルのcontextへ入れること、回答で持ち出すこと、行動の根拠にすることは別の判断である。

既存G5は出典・訂正・忘却・判断品質を扱い、F11は失効・削除後の再出現を防ぐ。しかし「正しいが今は不要な記憶」「過去の細部を索引上の抽象的経験へ降ろすこと」「休眠skillを名前を知らずに再発見すること」を受入条件にしていなかった。単なる追加ストレージ機能ではなく、選択・表現・寿命の契約の不足である。

常時contextが小さくても、背後で毎回全履歴を読む、全skill名を平坦に列挙する、無関係な経験を毎回回答へ差し込むなら達成ではない。逆に、検索を全停止して静かになっても、必要な経験を使えないなら失格である。

## 2. 分離する三つの軸

| 軸 | 判断 | 誤った代替 |
|---|---|---|
| 情報へのアクセス権 | その主体・送信先・用途で、原文や要約を読んでよいか | topicタグや類似度だけを認可にする |
| 注意と粒度 | 今の目的で、何を、どこまで、いつ取り出すか | 許可済み情報を全てcontextへ注入する |
| 寿命と有効性 | 現役、休眠、歴史資料、訂正済み、失効、削除のどれか | 古い情報を全部消す／古い手順を現在も有効と扱う |

生活の領域を別々の人格や永久に交わらない箱へ分断する要求ではない。同じ目的に役立つなら、許可された健康・旅行等の知識を横断してよい。アクセス権は強制境界、topicは注意の手掛かりである。曖昧な類似度だけで別領域へ拡張しないが、別topicというだけで有用なつながりを遮断もしない。

「検索しない」「概要で止める」「詳細まで読む」は正常な選択肢にする。ただし検出済みの重大な危険、明示停止、承認条件、引き受けた義務を注意節約の名目で無効にしない。これらは必要な時点で正本から確実に照合する。

## 3. 部分的忘却の契約

| 操作 | 残すもの・変えるもの | 後の扱い |
|---|---|---|
| 今回は想起しない | 保存物は変えず、今回の選択から除く | 場面が変われば再評価 |
| 抽象化・休眠 | 再利用可能な経験の概要と出典への手掛かりを通常索引に残し、詳細を通常の候補集合から降ろす | 許可された詳細は冷たい索引／原資料から必要時に回収可能 |
| 訂正・失効 | 旧値の適用期間・反証・後継を区別する | 歴史質問には応答できても、現在の判断を旧値で支配しない |
| 明示削除 | 削除契約の対象を原文・要約・関連projectionから除く | 復元可能な休眠と区別し、backup等に残る範囲と期限を明示 |

合成例: 終了済みの開発案件の詳細なリリースrunbookを、日常の索引には「過去にGitHub Actionsを使ったリリース自動化の事例がある。詳細は履歴資料で、現在の適用性は未検証」という経験へ降ろす。実際のユーザーの案件・技能を表す事実としては保存しない。

「その事例があった」は残すが、単発経験から「ユーザーはGitHub Actionsの専門家」「常にこの方式を好む」「そのrunbookが現行標準」という一般化を作らない。再利用できる教訓が確認できる場合のみ、適用条件と証拠を付けて抽出する。

抽象記録には少なくとも、意味上の手掛かり、対象期間・適用範囲、出典locator、元資料の版、抽象化の由来、不確実性、詳細の所在／回収不能状態を対応付ける。通常索引に過去runbookの全見出し・全aliasを残せば、索引の肥大化を別名で温存するだけである。深い索引を保存しても、常時提示とは切り離す。

抽象化は情報を落とす操作である。要約を繰り返し再要約するだけにせず、根拠に戻る経路、更新時の影響先、過度な一般化の検査、変換履歴を持つ。原資料の訂正・削除が上位要約に反映されるまで、その要約を古い可能性のあるものとして扱う。削除済みの詳細を生成で補って「思い出した」としない。

## 4. skillは「存在・発見・ロード・実行」を分離する

休眠skillは即時利用可能な機能一覧から降りてよい。ただし抽象的な能力の索引や検索から「以前こういう問題を解いた」という手掛かりを発見できることを求める。全休眠skillのdescriptionを起動時に並べ直すだけではない。

想起の流れの案は、現在の目的 → 関連する経験・能力の概要 → 必要なら元skill package → 現在の環境・依存version・対象・権限の照合 → 必要な範囲だけロード、である。packageには本文だけでなくscripts/references/assetsも含める。資料として読むことと、手順として適用することを分ける。

古いskillを発見しても、旧承認・古いsecret・廃止API・過去環境の権限は復活させない。利用可能か不明なら参照資料に留め、実行前の再検証や現在の方法への置換を行う。一度の再読だけで全topicの現役catalogへ永続復帰させない。

## 5. 長期メンテナンスも一級機能にする

昇格だけでなく降格・休眠・統合・再検証を設計する。時間だけで機械的に消さず、案件の終了、適用環境の廃止、反証、再利用価値、再取得費、情報の機微、低頻度でも重要な制約を判断材料にする。「読まれた回数」は「役立った回数」ではない。誤想起で毎回ロードされる記憶が自己強化しないようにする。

保守のtrigger候補は、案件終了、出典変更・訂正、実際の再利用、定期的な有界確認である。毎回全履歴をLLMへ投入することを既定にせず、更新された範囲と再利用が見込まれる抽象記録から処理する。処理のcoalescing、上限、失敗時に未更新と分かる状態を要求する。

backup復帰、index再構築、runtime/provider交換でも、休眠状態、通常／深い索引の区別、失効・削除、出典関係を保つ。復元直後に全履歴・全skillを現役へ戻してはならない。権限・停止・承認の正本をsemantic memoryの減衰に従属させない。

## 6. 公開一次資料で確認できた部品と不足

| 候補・根拠 | 確認できた機能 | これだけでは証明できない点 |
|---|---|---|
| Hermes Curator | `active → stale → archived`、archiveの一覧・restore、統合のopt-in、backup/ledger。現行docsには未使用bundled skillの扱いもある。[1] | 経験の意味的な抽象化、場面ごとのcatalog選択、名前を知らない休眠skillの自動再発見。稼働版の動作は別途確認 |
| Agent Skills仕様 | 起動時metadata、必要時の本文、さらに必要時のresourcesというprogressive disclosure。[2] | 全skillのmetadataが起動時対象という仕様だけでは、catalog自体の長期肥大化・休眠・再発見を解決しない |
| OpenViking | directory単位L0 abstract / L1 overview / L2 detail。sessionを考慮したintent解析、memory/resource/skill別query、検索不要なら0 queryという経路。[3][4] | 案件終了に応じた適切な忘却方針やPDA全体の判断品質。directory要約のsamplingと上位更新にはcoverage・遅延・費用の検査が要る |
| Hindsight | observation、memoryのtype/tag絞込、chunkやsource factの必要時取得。意味的に似た短いruleと長いprocedureをrankingだけで区別しにくいとの明示。[5] | domainタグは認可の代替ではない。生活の場面の選択・適切な降格・休眠skillの実行適格性は利用側の比較課題 |
| Hindsight Mental Models | 要約 → observation → factの階層参照。更新trigger、staleness確認、refresh間隔・scope指定、予算などのAPI。[6] | 用意された要約が正しい抽象度か、削除・訂正後の全派生物が整合するか、維持費が見合うかは別試験 |
| Anthropicのcontext engineering解説 | 有限のattention budget、軽量locatorからのjust-in-time取得、progressive disclosureと探索遅延のtrade-off。[7] | 一般的な設計指針であり、数年規模の個人記憶の部分的忘却を製品として実証した資料ではない |

Hermesの公式Curatorページには、冒頭の`prune_builtins`説明と、後段に残るagent-created-only説明の差がある。pinの保護対象も節により広狭がある。最新docsの一般説明を現在のインストール済み版へ当てはめず、利用するときは対象revisionのCLI/sourceで確認する。本追補ではCuratorの実行・有効化・adopt/archive/purgeを行わない。[1]

OpenVikingのL0/L1は各通常fileの対の要約ではなくdirectoryのsidecarであり、各層が必ず揃うとも限らない。coverageとpending変更のmetadataは通常のsemantic previewに含まれないため、現行性を確かめるにはそのmetadataを別途読む必要がある。resource/skillの上位要約更新は頻度制御にTODOがあり、採用時の継続費用として測る。[3]

Hindsightの要約更新にもLLMを伴うreflect費用があり、公式APIはまとめ処理・更新間隔と鮮度のtrade-offを明示する。またtag matchingでは非strict modeがuntagged memoryを含むため、「タグを付けたから境界ができた」と判断しない。[5][6]

**比較順の修正**: files/FTSを対照に残しつつ、単なる全文検索ではなく通常の抽象索引・詳細取得の区別を最小構成で試す。今回の固有要件に直接対応するOpenVikingの階層contextと、Hindsightの階層知識・更新制御をR1の一次比較対象に引き上げる。これはインストール／採用の許可ではない。Hermes/Lettaの既存能力で同じ結果をより少ない保守で得られる案も比較し、Graphiti/Honcho等の時間・関係・user modelingを不要と決めない。graphは選択肢だが、graphそのものを注意の選択や忘却の達成としない。

## 7. 共通評価の契約

詳細なGiven/When/ThenはロードマップF13〜F20を正本とする。以下は実装方式を決める前に固定する評価軸であり、実測値はまだない。

| 軸 | 測るもの |
|---|---|
| 不要な注意 | 無関係な記憶の取得・context注入・回答言及・行動への誤適用を別々に記録する。不要な注意喚起・提案も対象 |
| 必要な想起 | 同じ予算で必要な記憶を使えた割合、名称なしでの過去事例／skill再発見、根拠への到達。検索ゼロだけで合格にしない |
| 粒度と鮮度 | 通常索引に出る情報の深さ、原資料との整合、期間・scope、未更新表示、過去事例からの過度な一般化 |
| 長期費用 | 活動・履歴・skillが増えたときの、常設context、候補数、探索turn、取得token、遅延、background refresh費、operator手入れ時間 |
| 継続性 | 休眠・再発見・再休眠、index rebuild、backup復帰、別runtimeへのexport/import後も同じ選択と権限境界を保つこと |

同じmodel/prompt/言語/予算、同じ合成の多topic・長期履歴、意味的に紛らわしいdecoyを使う。小・中・大の履歴集合で総量増大に伴う変化を測り、常時全件列挙・検索完全停止の両方を対照にする。各候補の相違は取り込み・索引・選択・ロード方式として記録する。R1で母集団、取得／言及の正誤label、許容予算、必要想起と不要想起の合否閾値を事前固定し、結果を見て有利に変えない。

認可違反、失効手順の無承認実行、削除済み内容の現在値としての再生は、便利さの総合点で相殺しない。不要な想起を完全ゼロと約束するのではなく、何を絶対禁止とし、何を品質目標とするかを分ける。関連性判定の誤り・再発見不能・探索遅延は未解決になり得るため、検出と改善も維持費に含める。

## 8. 今回の境界

今回は要求・調査・比較順・受入条件を更新する。憲章の新規改定、運用中の記憶削除／降格、skillのarchive・再編、既存PKBの情報区分拡張、provider導入、runtime更新、実証batchの開始はしない。公開PKBへは公開資料に基づく一般的な技術比較のみ保存し、オーナーの私的会話や架空例を本人の経験として混入させない。

「思い出す能力」と「思い出さずに済む能力」を同時に評価することが、この追補の変更点である。

## Sources

[1] https://hermes-agent.nousresearch.com/docs/user-guide/features/curator — Curator | Hermes Agent
    > "The curator is a background maintenance pass for **agent-created skills**. It tracks how often each skill is viewed, used, and patched, moves long-unused skills through `active → stale → archived` states, and periodically spawns a short auxiliary-model review that proposes consolidations or patches drift."
    > "By default (`prune_builtins: true`) the curator can archive **unused bundled built-in skills** (shipped with the repo) after `archive_after_days` of non-use, alongside the agent-created skills it primarily manages. Hub-installed skills (from [agentskills.io](https://agentskills.io/)"
    > "This moves the skill back from `~/.hermes/skills/.archive/` to the active tree and resets its state to `active`. The restore refuses if a bundled or hub-installed skill has since been installed under the same name (would shadow upstream)."
    > "Pinning protects a skill from deletion — both the curator's automated archive passes and the agent's `skill_manage(action="delete")` tool call. Once a skill is pinned:"
[2] https://agentskills.io/specification — Specification - Agent Skills
    > "1.  **Metadata** (~100 tokens): The `name` and `description` fields are loaded at startup for all skills"
    > "2.  **Instructions** (< 5000 tokens recommended): The full `SKILL.md` body is loaded when the skill is activated"
[3] https://docs.openviking.ai/en/concepts/03-context-layers — Context Layers (L0/L1/L2) | OpenViking
    > "L0 and L1 are **directory-level semantic sidecars**. They describe a directory; OpenViking does not create a matching L0/L1 sidecar for every ordinary file. File summaries are inputs aggregated into the containing directory's L1."
    > "When the direct-entry count exceeds `semantic.overview_sample_limit` (32 by default), OpenViking uses deterministic, order-preserving stable sampling. Repeated refreshes of an unchanged tree choose the same sample, avoiding noisy body rewrites and Git diffs."
    > "> The current implementation attempts to bubble after every successful resource/skill semantic task, even when the newly generated child summary is unchanged. This is not the intended final scheduling policy. A future implementation should use `freshness` to coalesce, threshold, or time-window parent refreshes—for example by considering `pending_child_changes`, sampling coverage, direct-child change volume, and recent refresh state. The goal is to reduce repeated refreshes and upward write amplification in hot directories while preserving eventual consistency."
    > "| `freshness` | Direct-child coverage and known pending changes |"
[4] https://docs.openviking.ai/en/concepts/07-retrieval — Retrieval Mechanism | OpenViking
    > "*   **0 queries**: Chitchat, greetings that don't need retrieval"
    > "context_type: ContextType  # MEMORY/RESOURCE/SKILL"
    > "*   Last 5 messages"
[5] https://hindsight.vectorize.io/best-practices — Hindsight
    > "When a single bank contains semantically similar memories that serve different purposes (e.g., concise operating rules vs. detailed troubleshooting procedures), ranking alone cannot reliably distinguish them — two memories about "entrypoints" will score similarly regardless of whether one is a one-line rule and the other is a multi-step runbook."
    > "| `any` _(default)_ | Yes | At least one tag matches, OR untagged |"
    > "| `include.chunks` | Disabled | Agent needs exact wording or source quotation |"
[6] https://hindsight.vectorize.io/developer/api/mental-models — Hindsight
    > "Mental models are **saved reflect responses** that you curate for your memory bank. When you create a mental model, Hindsight runs a reflect operation with your source query and stores the result. During future reflect calls, these pre-computed summaries are checked first — providing faster, more consistent answers."
    > "A refresh is a full reflect run: retrieval plus an agentic LLM loop. With `refresh_after_consolidation` on a bank that ingests continuously, every small retain can therefore pay for a rebuild of every model whose scope it touched — and a handful of models on a chatty bank adds up fast."
    > "Both automatic triggers run the same check before spending an LLM call: **is there a memory in this model's resolved scope newer than its last refresh?** The model's `tags`/`tags_match`, `tag_groups`, and `fact_types` all apply to that check, so activity elsewhere in the bank does not trigger a rebuild, and a cron tick over an unchanged scope is skipped entirely. Memories still waiting to be consolidated count — they are already stored, so a model whose scope reaches them is considered stale."
[7] https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — Effective context engineering for AI agents
    > "Context is a critical but finite resource for AI agents. In this post, we explore strategies for effectively curating and managing the context that powers them."
    > "Rather than pre-processing all relevant data up front, agents built with the “just in time” approach maintain lightweight identifiers (file paths, stored queries, web links, etc.) and use these references to dynamically load data into context at runtime using tools. Anthropic’s agentic coding solution [Claude Code](https://www.anthropic.com/claude-code)"
    > "Of course, there's a trade-off: runtime exploration is slower than retrieving pre-computed data. Not only that, but opinionated and thoughtful engineering is required to ensure that an LLM has the right tools and heuristics for effectively navigating its information landscape. Without proper guidance, an agent can waste context by misusing tools, chasing dead-ends, or failing to identify key information."
