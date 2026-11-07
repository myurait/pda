# 指示文の書き方は「足す関門」と「削る関門」に分かれる

エージェント向けの指示文・メモリ・規則ファイルの書き方を方法論として文書化した事例は、公式ドキュメント・GitHub・論文・仕様の各所に 40 件余りある。しかし、(1) 書き方の方法論、(2) 書いた物の水準を測る評価基準、(3) 抽象的な方針から具体的な文を導く手順の 3 つを、一つの出典で揃えて持つ事例は見つからなかった。最も近いのは obra/superpowers の writing-skills と Anthropic の skill-creator で、どちらも「指示が無い状態で失敗を観察し、その失敗を塞ぐ最小の文を書き、有り無しで比べる」という試験先行の形をとる。superpowers はさらに、観察した失敗の種類から文の形 (禁止・出力の型の指定・必須の欄・観察できる条件つきの規則) を選ぶ表と、指示なしの対照を置いた文言の小試験を持ち、(3) に最も踏み込んでいる。ただし規則を足す側しか持たず、規則を削る側は vltansky/agents-md-evals と arXiv:2604.11088 の除去実験が別々に担う。抽象から具体への段階でニュアンスの欠落を防ぐ機構は、規則に理由を添える (Anthropic の憲法・spec-kit)、適合例と違反例を対で示す (OpenAI Model Spec)、観察した事例に照らして規則を残すか決める (ICAI・ExpeL) の 3 系統に分かれる。書き方の方法論そのものの効果を第三者が測った研究は無く、第三者計測は「文脈ファイルの有無」「規則 1 本の有無」「skill の有無」を測るにとどまる。読み手が区別している 3 種のメモリ (失敗への反省・ユーザーの具体的な指示・事実や状態) を区別する出典も無い。

---

## 候補の一覧

記号は (1) 書き方の方法論、(2) 水準を測る評価基準、(3) 方針から規則を導く手順 (ニュアンス欠落と不要規則の混入の防止) について、○ = 持つ、△ = 一部だけ持つ、× = 持たない、? = 本文未確認で判定できない、を表す。評価の裏付けは「なし」「自己申告」(作者が自分の方法・道具を測った)「第三者計測」(他者が書いた物を測った) に分けた。「要約経由」は要約を挟んだ取得で原文の文言を確かめていないことを示す。

### 公式ドキュメント

| 候補 | 対象 | (1) | (2) | (3) | 評価の裏付け | タグ |
|---|---|---|---|---|---|---|
| [Anthropic「Skill authoring best practices」](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | SKILL.md | ○ | ○ | △ | なし (eval を処方するが、自らの助言の効果は測っていない。実行の仕組みが無いと明記) | 方法論 |
| [anthropics/skills の skill-creator](https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md) (Anthropic 作、GitHub 上に置かれた skill) | SKILL.md を書く skill | ○ | ○ | △ | 自己申告 (合格率・時間・トークンの平均と標準偏差、有り無しの差を測る仕組みはあるが、結果の公表は無い) | 方法論 |
| [Anthropic「Effective context engineering for AI agents」](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | system prompt | △ | × | △ | なし。要約経由 | 方法論 (軽) |
| [Anthropic「Prompting best practices」](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) | system prompt・CLAUDE.md 型の指示 | △ | △ | △ | ほぼなし (長文で質問を末尾に置くと最大 30% 改善の一文のみ。方法非開示) | tips |
| [Anthropic「Writing effective tools for agents」](https://www.anthropic.com/engineering/writing-tools-for-agents) | tool の説明文 (メモリではない隣接領域) | ○ | ○ | △ | 自己申告 (Claude が直した tool が held-out で人手版に勝つ。図のみで数値なし)。要約経由 | 方法論 (tool 説明) |
| [Anthropic「Define success criteria / develop tests」](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests) | プロンプト一般 | △ | ○ | × | なし (評価設計の参照文書そのもの)。要約経由 | 評価設計の方法論 |
| [Claude Code「How Claude remembers your project」](https://code.claude.com/docs/en/memory)・[「Best practices」](https://code.claude.com/docs/en/best-practices) | CLAUDE.md・.claude/rules・auto memory | △ | △ | △ | なし (長いと遵守が落ちる、を根拠なしに主張) | tips + 振り分けの判断規則 |
| [OpenAI「GPT-4.1 Prompting Guide」](https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide) | system prompt | △ | △ | △ | 書き方の助言について未確認。要約経由 | tips・テンプレート |
| [OpenAI「GPT-5 Prompting Guide」](https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide) | system prompt | △ | △ | △ | 自己申告だが文言の効果ではない (Tau-Bench Retail 73.9%→78.2% は Responses API への移行の効果)。Cursor の逸話は提携先の報告。要約経由 | tips |
| [agents.md](https://agents.md)・[Codex の AGENTS.md 文書](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | AGENTS.md | × | △ | × | なし (agents.md は採用数のみ)。要約経由 | tips・テンプレート |
| [GitHub Copilot「repository custom instructions」](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions) | copilot-instructions.md・*.instructions.md | △ | △ | × | なし (指示を一時無効化して比べる手動 A/B を勧めるが結果なし)。要約経由 | tips + 手動検証手順 |
| [Cursor「Rules」](https://cursor.com/docs/context/rules) | .cursor/rules | △ | × | △ | なし。要約経由 | tips (失敗起点の追加) |
| [Kiro「Steering」](https://kiro.dev/docs/steering/) | steering ファイル | △ | × | △ | なし。要約経由 | tips |
| [Gemini CLI「GEMINI.md」](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md) | GEMINI.md | × | × | × | なし。要約経由 | テンプレート・参照 |

### GitHub コミュニティ

| 候補 | 対象 | (1) | (2) | (3) | 評価の裏付け | タグ |
|---|---|---|---|---|---|---|
| [obra/superpowers の writing-skills](https://github.com/obra/superpowers/tree/main/skills/writing-skills) | SKILL.md・CLAUDE.md | ○ | ○ | ○ (失敗の種類から文の形を選ぶ表と文言の小試験を持つ。足す側のみ) | 自己申告 (複合圧力シナリオでの行動の合否と、文言の対照比較。数値は非公開)。唯一の数値は外部研究の借用 (Meincke et al. 2025、N=28,000 で応諾率 33%→72%。測っているのは不適切な依頼への応諾で、skill の品質ではない) | 方法論 |
| [vltansky/agents-md-evals](https://github.com/vltansky/agents-md-evals) | AGENTS.md・CLAUDE.md | △ | ○ | ○ (削る側のみ) | 自己申告 (755 行のファイルで 26 アサーション中 25 が有無で同一。改善幅は +3〜10% と記述。作者 1 人・1 プロジェクト) | 方法論 (評価・剪定) |
| [NieZhuZhu/ai-harness-doctor](https://github.com/NieZhuZhu/ai-harness-doctor) | AGENTS.md・CLAUDE.md・Cursor・Copilot | △ | ○ | △ | 自己申告・生データ公開 (14 タスク×2 回で 6/28→28/28、遅延 -27%、費用 -17%。trycompai/comp で 18/24→24/24。openai/codex では改善なしという結果も公開。比較元は作者が作った矛盾入りのデモ repo) | 方法論 + 道具 |
| [github/awesome-copilot の instructions.instructions.md](https://github.com/github/awesome-copilot/blob/main/instructions/instructions.instructions.md) | Copilot instructions | △ | × | △ | なし | 軽い方法論 (テンプレート集の中のメタ規則) |
| [HumanLayer「Writing a good CLAUDE.md」](https://www.humanlayer.dev/blog/writing-a-good-claude-md) (awesome-claude-code から参照) | CLAUDE.md・AGENTS.md | ○ | × | △ | なし (IFScale を根拠として引くのみ) | 方法論 (エッセイ) |
| [eyaltoledano/claude-task-master の self_improve.mdc](https://github.com/eyaltoledano/claude-task-master/blob/main/.cursor/rules/self_improve.mdc)・cursor_rules.mdc | Cursor rules | △ | △ | △ | なし。要約経由・原文未確認 | 軽い方法論・事実上のテンプレート |
| [rohitg00/pro-workflow](https://github.com/rohitg00/pro-workflow) | Claude Code の memory・rules | △ | × | × | なし (「訂正率ほぼゼロ」は自己主張) | 道具 (訂正を規則として捕捉) |
| [felixgeelhaar/cclint](https://github.com/felixgeelhaar/cclint) | CLAUDE.md・skills・subagents | × | △ | × | なし (曖昧語が遵守を下げるという主張に根拠なし) | 道具 (静的検査) |
| [jrenaldi79/harness-engineering](https://github.com/jrenaldi79/harness-engineering) | CLAUDE.md テンプレート・harness | △ | △ | × | なし (8 柱 37 基準は repo 構造の採点で文言の質ではない) | テンプレート集 + 採点 |
| [josix/awesome-claude-md](https://github.com/josix/awesome-claude-md) | CLAUDE.md | △ | △ | × | なし (掲載基準の重み付けのみ) | 事例集 |
| [PatrickJS/awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules)・[hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)・[humanlayer/12-factor-agents Factor 2](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-02-own-your-prompts.md) | 各種 | × | × | × | なし | テンプレート集・リンク集・原則 |

### 論文

| 候補 | 対象 | (1) | (2) | (3) | 評価の裏付け | タグ |
|---|---|---|---|---|---|---|
| [arXiv:2602.11988 Evaluating AGENTS.md](https://arxiv.org/abs/2602.11988) | AGENTS.md 系 | △ | △ | × | 第三者計測 (SWE-bench Lite 300 と CTXbench 138 で成功率・ステップ・コスト) | 計測研究 |
| [arXiv:2601.20404 AGENTS.md と効率](https://arxiv.org/abs/2601.20404) | AGENTS.md | × | △ | × | 第三者計測 (Codex、10 repo の PR 124 件で実時間とトークン。正しさは測らない) | 計測研究 |
| [arXiv:2604.11088 Guardrails Beat Guidance](https://arxiv.org/abs/2604.11088) | CLAUDE.md・.cursorrules | △ | ○ | △ | 第三者計測 (SWE-bench Verified の判別的 58 件で規則の除去と単独適用) | 計測研究 |
| [arXiv:2511.12884 Agent READMEs](https://arxiv.org/abs/2511.12884) | CLAUDE.md・AGENTS.md・copilot-instructions | × | △ | × | 第三者計測 (2,303 ファイルの内容・可読性・更新の記述統計。成果との相関なし) | 実態調査 |
| [arXiv:2510.21413 Context Engineering in OSS](https://arxiv.org/abs/2510.21413) | AGENTS.md ほか | × | × | × | 第三者計測 (記述のみ。書き方を記述的・指示的・禁止的・説明的・条件的の 5 分類) | 実態調査 |
| [arXiv:2603.03456 Asymmetric Goal Drift](https://arxiv.org/abs/2603.03456) | AGENTS.md に置いた制約 | × | △ | × | 第三者計測 (制約違反をステップごとに採点。文言の変種は測らない) | 計測研究 |
| [arXiv:2507.11538 IFScale](https://arxiv.org/abs/2507.11538) | system prompt 型の指示 | × | △ | × | 第三者計測 (指示 10〜500 個、20 モデル。最良でも 500 指示で約 68%) | 計測研究 |
| [arXiv:2509.21051 When Instructions Multiply](https://arxiv.org/abs/2509.21051) | 指示一般 | × | △ | × | 第三者計測 (指示数から遵守率を約 10% 誤差で推定) | 計測研究 |
| [arXiv:2602.12670 SkillsBench](https://arxiv.org/abs/2602.12670) | SKILL.md | ○ | ○ | △ | 第三者計測 (84 タスク・7 構成・7,308 軌跡。厳選 skill +16.2pp、自己生成 -1.3pp) | 計測研究 + 方法論 |
| [arXiv:2607.01456 From Anatomy to Smells](https://arxiv.org/abs/2607.01456) | SKILL.md | △ | ○ | × | 第三者計測 (238 件の質的分析と smell 検出。検出器の精度と成果との相関は未記載) | 計測研究 |
| [arXiv:2510.04618 ACE](https://arxiv.org/abs/2510.04618) | memory (進化する playbook) | △ | ○ | ○ | 自己申告 (AppWorld 平均で Base 42.4→59.4、ablation とコストを併記) | メモリ蒸留手法 |
| [arXiv:2308.10144 ExpeL](https://arxiv.org/abs/2308.10144) | memory (自然言語の insight) | × | △ | ○ | 自己申告 (学習した insight が手作りに勝つ) | メモリ蒸留手法 |
| [arXiv:2507.19457 GEPA](https://arxiv.org/abs/2507.19457) | system prompt (モジュール単位) | × | ○ | ○ | 自己申告 (数値は版で異なる。後述) | プロンプト最適化 |
| [arXiv:2504.07952 Dynamic Cheatsheet](https://arxiv.org/abs/2504.07952) | memory | × | △ | △ | 自己申告。本文未確認 (検索要約のみ) | メモリ蒸留手法 |
| [arXiv:2403.08978 AutoGuide](https://arxiv.org/abs/2403.08978) | 状態つきの guideline | △ | △ | ○ | 自己申告。本文未確認 (検索要約のみ) | メモリ蒸留手法 |
| [arXiv:2509.14744](https://arxiv.org/abs/2509.14744)・[arXiv:2602.14690](https://arxiv.org/abs/2602.14690)・[arXiv:2607.15557 SkillCorpus](https://arxiv.org/abs/2607.15557) | CLAUDE.md・設定機構・skill | ? | ? | ? | 本文未確認 (検索要約では内容分析・採点の研究) | 実態調査 |

### 仕様・憲法系

| 候補 | 対象 | (1) | (2) | (3) | 評価の裏付け | タグ |
|---|---|---|---|---|---|---|
| [OpenAI Model Spec 2026-10-29 版](https://model-spec.openai.com/2026-10-29.html) (原本 [openai/model_spec](https://github.com/openai/model_spec)) | モデル挙動の仕様 | △ | × | △ | なし (本番モデルはまだ仕様を完全には反映しないと自ら記述)。要約経由 | 構造の参照 |
| [Anthropic の憲法](https://www.anthropic.com/constitution) | 憲法 | ○ | △ | △ | なし。要約経由 | 方法論 (原則と規則の関係) |
| [arXiv:2406.06560 Inverse Constitutional AI (ICAI)](https://arxiv.org/abs/2406.06560) | 選好データから抽出する原則集 | ○ | ○ | △ (具体→原則の逆方向) | 自己申告 (648 対で一致率 61% 対 34%。held-out 分割は AlpacaEval のみ) | 方法論 (逆方向) |
| [arXiv:2310.13798 Specific versus General Principles](https://arxiv.org/abs/2310.13798) | 憲法 | △ | ○ | × | 自己申告。検索断片のみで本文未確認 | 計測研究 |
| [arXiv:2212.08073 Constitutional AI](https://arxiv.org/abs/2212.08073)・[arXiv:2412.16339 Deliberative Alignment](https://arxiv.org/abs/2412.16339) | 憲法・仕様を訓練の入力に使う | × | × | × | 自己申告。abstract のみ | 規則を使う側の研究 |
| [github/spec-kit の constitution コマンド](https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/constitution.md)・[spec-driven.md](https://raw.githubusercontent.com/github/spec-kit/main/spec-driven.md) | 憲法 (規則ファイル) | ○ | ○ | △ | なし。要約経由・原文未確認 | 方法論 |
| [Kiro「Feature specs」](https://kiro.dev/docs/specs/feature-specs/) と [EARS](https://en.wikipedia.org/wiki/Easy_Approach_to_Requirements_Syntax) | 要件文 | ○ | △ | △ | なし (EARS は RE'09 の発表。本調査では未検証。Wikipedia は検索経由) | 文型テンプレート |

---

## 深掘り

(2) と (3) の強さで 8 件を選んだ。各件について、方法論・評価基準・規則の導出手順、そして抽象から具体への段階で「ニュアンスの欠落を何が防ぐか」「不要な規則の混入を何が防ぐか」を分けて書く。片側しか持たない事例は、持たない側をそのまま書いた。

### superpowers writing-skills は失敗の種類から文の形を選ぶ

**方法論**: skill の執筆を工程文書に対するテスト駆動開発と位置づけ、掟として「NO SKILL WITHOUT A FAILING TEST FIRST」を掲げる。skill の無い状態でエージェントが規則を破るのを観察し (RED)、skill がある状態で従わせ (GREEN)、従ったまま抜け道を塞ぐ (REFACTOR)。GREEN 段は最小の skill を書く段で、「Don't add extra content for hypothetical cases.」とする。同じ方法を CLAUDE.md の文案比較にも当て、時間の圧力・サンクコスト・権威・慣れの 4 シナリオで「どの文案なら圧力下でも skill を見つけて使うか」を試す ([SKILL.md](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md))。

**評価基準**: 2 段ある。全体のシナリオでは行動の合否を見る。「Best tests combine 3+ pressures.」とし、最大の圧力下で正しい選択肢を選び、新しい言い訳が出なくなったら合格とする。その前段に、文言だけを試す小試験の 5 段の手順がある。1 回の呼び出しで新しい文脈の標本を 1 つ取り、system prompt にはその指示が実際に置かれる現実の文脈全体を、ユーザー発話には失敗を誘う課題を置く。指示なしの対照を必ず置き、対照が失敗しなければ直すものが無いので指示を書かない。各案を 5 回以上繰り返す。自動の数え上げは過大に出るので、引っかかった出力はすべて人が読む。そして「Variance is a metric」とし、出力が収束すれば文言が効いている、ばらつけば言葉を足す前に文の形を締める、と判定する。superpowers はこの手順で行った文言の直接比較の結果も書いている。禁止の文言の側は出力の型を指定する側より不要な内容を多く生み、指示なしの対照より悪い傾向だった。ただし数値は公表されておらず、自己申告である。

**導出手順と抽象→具体の扱い**: 「Match the Form to the Failure」の節が、抽象から具体への段階をこの調査で最も明示的に扱う。指示を書く前にベースラインの失敗を分類し、失敗の種類から文の形を選ぶ。圧力下で規則を飛ばす失敗には、禁止 + 言い訳の一覧表 + 危険信号を当てる (「なるべく〜」「〜を検討」の柔らかい指示は誤った形とされる)。従ってはいるが出力の形が違う失敗には、出力が何であるかを部品の順に述べる肯定の型 (recipe・contract) を当てる (禁止の列挙は誤った形)。必須の要素を落とす失敗には、テンプレートの構造上の必須欄を当てる (散文の念押しは誤った形)。条件によって挙動を変えるべき場合には、観察できる述語に結び付けた条件つきの規則を当てる (無条件の規則 + 適用除外の但し書きは誤った形)。

この節はニュアンスの扱いについて、他の出典と逆向きの規則を 2 つ持つ。一つは「No nuance clauses.」で、「重要でなければ X しない」のような但し書きは交渉の余地を開き直すとする。勝っていた型の指定に但し書きを 1 つ足しただけで、出力が一貫していた状態からばらつく状態に落ちたという。本当の例外は、観察できる述語を持つ独立した条件つきの規則にする。もう一つは「Exemption clauses don't scope.」で、「この上限はコードブロックには適用しない」と書いてもコードブロックが抑えられてしまうため、規則が届かない構造に組み替える。つまり superpowers はニュアンスを文の中の但し書きで保とうとせず、観察できる条件を持つ別の規則に切り出して保つ。

REFACTOR 段では「Document every excuse.」とし、捕まえた言い訳 1 件ごとに、規則への明示の否定、言い訳の一覧表への記入、危険信号の記入、description の更新を足す。`references/bulletproofing.md` は「文字に背くことは精神に背くこと」という趣旨の原則を置き、「精神には従っている」という言い訳を先に封じる。規則が効かないときの診断手順 (Meta-Testing) もある。

不要な規則は 3 つの関門で防ぐ。対照が失敗しなければ書かない、仮定の場合のために内容を足さない、語数の上限 (頻繁に読み込まれる skill は 200 語未満、ほかは 500 語未満) である。欠けているのは 2 点で、後から効かなくなった規則を削る工程が無いこと、そして文の形は失敗の種類から選ぶが、抽象的な方針そのものから文を導く工程は無いことである。導出の起点は方針ではなく観察した失敗にある。

**根拠の場所**: `skills/writing-skills/SKILL.md` の「The Iron Law (Same as TDD)」「TDD Mapping for Skills」「GREEN: Write Minimal Skill」「Match the Form to the Failure」「Micro-Test Wording Before Full Scenarios」、`references/testing-skills-with-subagents.md` の「REFACTOR Phase: Close Loopholes」「When Skill is Bulletproof」、`references/bulletproofing.md`、`references/CLAUDE_MD_TESTING.md`、`references/discovery.md` の「Token Efficiency (Critical)」 ([writing-skills](https://github.com/obra/superpowers/tree/main/skills/writing-skills))。

### Anthropic の skill 執筆ループは指示の有り無しを常に比べる

**方法論**: Skill authoring best practices は「Create evaluations BEFORE writing extensive documentation.」とし、skill 無しで欠けている点を見つける → eval を 3 つ作る → ベースラインを取る → 欠けた点を埋める最小限の指示を書く → 反復する、の 5 段を示す ([Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices))。反復は「Claude A が指示を設計し、Claude B が実際に使う」の 2 役で回し、B の具体的な失敗 (例: Q4 の日付で絞るのを忘れた) を A に戻す。Haiku・Sonnet・Opus のすべてで試す。skill-creator はこれを道具にしたもので、テストのプロンプトを `evals/evals.json` に置き、各プロンプトで skill 有りとベースライン (新規なら skill 無し、改良なら旧版のスナップショット) の実行を同じターンで走らせる ([skill-creator](https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md))。

**評価基準**: アサーション単位の採点 (`agents/grader.md` が `grading.json` を書く)、合格率・時間・トークンの平均と標準偏差、有り無しの差の集計 (`benchmark.json`)、人手の確認画面。良いアサーションは客観的に検証できるものとし、主観的な質はアサーションに押し込まず質的に評価する。分析の段では、skill の有無にかかわらず常に合格するアサーション (判別しない物) と、ばらつきの大きい eval を探す。目隠しの比較 (`agents/comparator.md`) もある。description の発火テストは 60% を訓練、40% を held-out に分け、各クエリを 3 回走らせ、最大 5 回の反復のうち held-out の得点で最良を選んで過学習を避ける。best practices 側は eval の JSON 形と「eval を 3 つ以上作ったか」の点検表を持つが、実行する組み込みの仕組みは無いと明記する。

**導出手順と抽象→具体の扱い**: ニュアンスの欠落には 3 つの手当てがある。一つは「自由度」で、作業の壊れやすさに応じて文の具体さを変える (壊れやすい作業ほど文字どおりの手順にする)。二つ目は「Explain the why」で、重い MUST を並べる代わりに、なぜ重要かをモデルに説明する。大文字の ALWAYS/NEVER は「a yellow flag」とされ、理由付きに書き直す対象になる。三つ目は「Generalize from the feedback」で、特定の例に合わせた過学習気味の細かい修正や、息苦しいほどの MUST を避け、skill を一般的な形に保つ。不要な規則には、ベースラインを超えない指示はそもそも書かない関門、各情報がトークンの費用に見合うかを問う「Concise is key」、実行記録を読んで無駄な手順を生む指示を削る工程が当たる。抽象的な方針を文に分解する手順そのものは無い。

**根拠の場所**: best practices の「Evaluation and iteration > Build evaluations first」「Develop Skills iteratively with Claude」「Concise is key」、skill-creator の `skills/skill-creator/SKILL.md` の「Writing Style」「Test Cases」「Step 1: Spawn all runs (with-skill AND baseline) in the same turn」「Step 4」「How to think about improvements」「Advanced: Blind comparison」「Description Optimization」、`agents/grader.md`。

### agents-md-evals は A/B で差の出ない規則を削る

**方法論**: 既存の AGENTS.md / CLAUDE.md を監査する 6 段のループ。規則を読み分類 → eval プロンプトを生成 → 汚染の無い A/B を実行 → 採点と集計 → 分析と推奨 → 確認画面。eval はその repo の git のコミット履歴から作るのを優先する。Claude Code はサブエージェントにも CLAUDE.md を自動で読み込ませるため、ベースライン側ではファイルを物理的に消す (Clean Baseline Protocol)。Anthropic の skill-creator の eval 枠組みの上に作られている ([agents-md-evals](https://github.com/vltansky/agents-md-evals))。

**評価基準**: 規則ごとに、ファイル有りと無しで挙動が変わるか。README は目的を「どの規則が挙動を変え、どれが文脈を浪費するか」の発見としている。

**導出手順と抽象→具体の扱い**: 削る側の手順だけを持つ。「The Keep Test」は、残す規則が 6 つの問いの少なくとも 1 つを満たすことを求める。その repo だけの判断か (Specificity)、挙動を変えるか (Behavior change)、新しく来た有能な開発者を驚かせるか (Surprise)、実際の失敗や繰り返された PR 指摘に由来するか (Pain)、頻度、テスト・型・linter・CI で強制できないか (No feedback loop)。そして「If it fails all six AND is non-discriminating in A/B tests, it's dead weight.」とする。`references/eval-categories.md` は規則の種類を、効果を測る価値が高い物 (連動・対応の規則、作業手順、判断の流儀)、低い物 (モデルがコードから推測できる技術選択や最新のコーディング作法)、測れないが残す物 (安全の歯止め、本人の好み) に分ける。不要な規則は A/B での非判別とこの 6 問の両方で防ぐ。規則の文面を書く方法、ニュアンスの保持の方法は持たない。

**根拠の場所**: `SKILL.md` の「The Evaluation Loop」「The Keep Test」、`references/eval-categories.md`、README の「Clean Baseline Protocol」「Commit-Derived Evals (Preferred)」 ([eval-categories.md](https://github.com/vltansky/agents-md-evals/blob/main/references/eval-categories.md))。

### arXiv:2604.11088 は規則 1 本ずつを除去と単独適用で仕分ける

**方法論**: 書き方の推奨は短い。否定形の制約を優先する、文言に凝らない (存在が言い回しに勝つ) の 2 点で、本文の Box 1 の実務推奨に置かれている (いずれも論文の言い換え)。

**評価基準**: この調査で最も明示的な規則単位の測定手順を持つ。SWE-bench Verified 500 件を 3 回ずつ走らせ、3 回中 1〜2 回だけ解ける 58 件を「判別的」タスクとして残す。Claude Code と Claude Opus 4.6 を固定し、CLAUDE.md だけを差し替える対応あり設計にする。実験 4 では手作りの 18 規則を 1 本ずつ除去し、5pp を超える変化があれば効く (shaping) か歪める (distorting)、それ未満なら無関係 (inert) と分類した。結果は shaping 3 本、distorting 4 本、inert 11 本だった。規則を単独で適用すると、18 本中 14 本が、ベースラインで安定して解けていた 17 タスクのうち 2 件以上を壊した。規則対の加法性も測る ([2604.11088](https://arxiv.org/abs/2604.11088))。

**導出手順と抽象→具体の扱い**: 抽象的な方針から規則を導く手順は無い。書かれた規則の要不要を実測で判定する手順だけがある。不要な規則は除去実験で inert として見つかり、有害な規則は単独適用の破壊数で見つかる。ニュアンスの欠落は扱わない。結論の強さには著者自身が限界を付けている。検出力が低く (n=58 / 35 で検出できるのは約 15pp の差)、単一ベンダー・単一モデル・Python のバグ修正のみで、個別の有意差は多重比較補正に耐えない。「有益な規則はすべて否定形」は 7 条件の符号検定 (p=0.008) に依る。実験 1 では規則の出所 8 条件 (無し・厳選・ランダムなど) の成功率が 50.0%〜63.8% で有意差が無く (p=0.697)、実験 2 では規則数 0〜50 で成功率が劣化しなかった。abstract の要約は「ランダム規則も厳選と同等 (+13.8pp)」と書き、効く理由を context priming と解釈するが、本文の統計では条件間に有意差は無い。この設計をそのまま規則の質の指標に使うと、質の差を検出できない恐れがある。

**根拠の場所**: 本文の「Experiment 4」と「Practical recommendations」(Box 1)。

### ACE と ExpeL は経験を差分と票で規則に変える

**方法論**: どちらも実行経験から自然言語の知見を取り出してメモリに積む。ACE は Generator が試行を出し、Reflector が成功と失敗の原因を批評して教訓を抽出し (最大 5 ラウンド)、Curator が ID と helpful/harmful のカウンタを持つ箇条書き項目の差分 (delta) に変換する。マージは LLM ではなく決まったロジックで行い、意味埋め込みで重複を除く ([ACE](https://arxiv.org/abs/2510.04618))。ExpeL は成功と失敗の対、または成功軌跡の集合を LLM に見せ、既存の insight に対して ADD・EDIT・UPVOTE・DOWNVOTE のどれかを発行させる。新しい insight は重要度 2 で始まり、0 になると除去される ([ExpeL](https://arxiv.org/abs/2308.10144))。

**評価基準**: ACE は AppWorld で Base ReAct 42.4、GEPA 46.4、ACE offline 59.4 / online 59.5、金融系で Base 69.1、ACE offline 81.9。ablation は Reflector と複数エポックの両方なしで 55.1、複数エポックなしで 56.8、完全版 59.4 で、遅延は offline AppWorld で GEPA 比 -82.3%。本文は ICL・GEPA に対し +12.3% / +11.9% と書くが、表から計算すると約 13.4 / 13.0 ポイントになり、本文と表が合わない。ExpeL は HotpotQA で ReAct 28.0、手作り insight 32.0、ExpeL 39.0、reflections を足すと 29.0 に下がる。ALFWorld では ReAct 40.0、ExpeL 59.0。比較対象の Reflexion は本文で 54%、表で 54.4% と表記が揺れる。いずれも自分の手法の自己申告である。

**導出手順と抽象→具体の扱い**: ニュアンスの欠落について、ACE は「context collapse」を測って問題として定義した点で、この調査で唯一の直接の証拠を持つ。文脈全体を LLM に書き直させると、18,282 トークン・精度 66.7 の文脈が次のステップで 122 トークン・57.1 に崩れ、無適応のベースライン 63.7 を下回った。短く要約する最適化器が領域固有の洞察を落とす傾向 (brevity bias) も定義している。対策は全面の書き直しをせず、差分の項目だけを足し・更新することである。ExpeL は EDIT で既存の insight を直す形でニュアンスを残す。不要な規則は、ACE では helpful/harmful のカウンタと重複除去が、ExpeL では票が尽きたら消す規則が抑える。ただし ACE で削る基準の効果を単独で測った ablation は確認できていない。両者とも成功と失敗を実行環境で判定できるタスクが前提で、正解の無い領域にはそのまま移せない。

**根拠の場所**: ACE は「Method」と「Experiments」、ExpeL は「Method (Insight Extraction)」と Table 3。

### ICAI は事例に照らして原則を残すかを決める

**方法論**: 選好データ (どちらの応答が良いかのラベル) から原則集を取り出す 5 段の手順。LLM が各ラベル対から原則の候補を出す → 埋め込みと k-means で重複をまとめる → クラスタごとに 1 つ抜き出す → LLM が各原則を各ラベル対に当て、1 番目を支持・2 番目を支持・無関係のどれかを付ける → ラベルの再現を改善しない原則と、全件の 10% 未満にしか関係しない原則を落とし、正解数から誤り数を引いた値で並べて上位 n 本を残す ([ICAI v2](https://arxiv.org/html/2406.06560v2))。

**評価基準**: 原則集を与えた LLM が元のラベルをどれだけ再現するか (一致率)。648 対の集合で 61% 対 34% (原則なし)。ablation では、検査と絞り込みの段を外したときの低下が最も大きい。held-out の分割を取ったのは AlpacaEval (65/65) だけで、絞り込みには訓練側の票を使う。

**導出手順と抽象→具体の扱い**: 向きが読み手の問いと逆で、具体的な事例から抽象的な原則へ進む。それでも「原則が担うべき事例を実際に説明できるか」で残すかを決める点は、抽象→具体の段階にも当てはまる判定である。ニュアンスの欠落は、事例ごとの当てはめで予測を誤る原則を下位に落とすことで防ぐ。不要な規則は、重複のクラスタ化、10% の関連度の下限、上位 n 本の上限で防ぐ。著者は、同等に当てはまる原則集が多数ありうること、圧縮で情報が落ちること、因果を主張しないこと、個人や集団の原則集は他へ移りにくいことを限界として挙げる。指示ファイルの規則の質を測ったものではない。

**根拠の場所**: HTML v2 の手順説明の節と ablation (要約経由)。

### Anthropic の憲法は「原則から読み手が再構成できる規則」だけを置く

**方法論**: 判断を優先し、置く規則には理由を説明する。規則は事前の透明性と予測可能性を与えるが、すべての状況を予期できない。判断は状況に合わせられるが、予測と評価のしやすさを犠牲にする。この比較を本文で述べ、規則にするのは誤りの費用が大きく、予測可能性と評価可能性が決定的に重要な場合に限るとする (要約経由・原文未確認、[Anthropic の憲法](https://www.anthropic.com/constitution))。

**評価基準**: 規則を置いてよい条件 (誤りの費用・予測可能性・操作されやすさ) と、個別の指針が憲法の原則で説明できること。読み手が原則を十分に理解していれば、Anthropic が作る規則を自分で組み立てられる状態を目標とする。

**導出手順と抽象→具体の扱い**: 手順は 4 つに整理できる。広い考慮事項とその理由を散文で述べる → 規則は誤りの費用などで固さが正当化されるときだけ許す → 個別の指針は原則で説明できることを求める → 指針が憲法と矛盾したら起草の誤りとみなし、矛盾した指針を残さず憲法を直す。ニュアンスの欠落は、規則に理由を添えることと、読み手が規則を自分で再構成できることを目標にすることで防ぐ。狭い規則の悪い一般化の例として、「感情の話題では常に専門家を勧める」という規則が「自分の保身を優先する」自己像に一般化しうることを挙げる。不要な規則は、判断を既定とし規則には正当化を要求すること、矛盾があれば規則を足さず原則を直すことで防ぐ。ただし (3) の「説明できるか」は判定であって規則の生成手順ではなく、測定も無い。読めたのは本文の前半約 10 万文字までである。

OpenAI Model Spec はこれを補う意味の錨を持つ。各規則に「Compliant」と「Violation」の応答例を対で並べ、なぜそう判定するかの短い注釈を付ける。指示の衝突は権威の階層 (Root から Guideline まで) で上位が勝ち、下位が上位の規則を読み替えることを禁じる。ただし価値から規則をどう導いたかは読めた範囲に書かれていない (要約経由、[Model Spec](https://model-spec.openai.com/2026-10-29.html))。

**根拠の場所**: 憲法の「Why Anthropic explains its reasoning」と概要の節。

### spec-kit は原則を yes/no の関門に変換する

**方法論**: constitution コマンドの 6 段の手順で、現在の憲法を読み込む → 価値を集める → 起草する → 同期の報告を出す。各原則は「名前 + 交渉不能な規則 + 自明でないときの理由」で書く。不明な欄は推測せず TODO の印を残し、変更は MAJOR/MINOR/PATCH で版を上げる (要約経由・原文未確認、[constitution コマンド](https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/constitution.md))。

**評価基準**: 手順の 5 段目で、原則が宣言的で、検証可能で、曖昧な語を含まないことを確かめる。SHOULD は MUST に置き換える。

**導出手順と抽象→具体の扱い**: 原則を計画テンプレートの yes/no のチェック項目に変換する (例: プロジェクト数は 3 以下か)。Simplicity・Anti-Abstraction・Integration-First の「Phase -1 gates」がこれにあたり、各関門に合格するか、例外を「Complexity Tracking」に記録しない限り先に進めない。文書はこれを、設計原則に対するコンパイル時の検査と表現する ([spec-driven.md](https://raw.githubusercontent.com/github/spec-kit/main/spec-driven.md))。ニュアンスの欠落は、理由の欄と例外の記録 (逸脱を黙って落とさず残す) で防ぐ。テンプレートは推測の代わりに `[NEEDS CLARIFICATION: ...]` の印を強制する。不要な規則は、「必要になるかもしれない」機能を関門で禁じることで防ぐ。原則そのものを導く手順、規則を削る基準、測定は無い。同じ系統に Kiro の EARS がある。「WHEN [条件] THE SYSTEM SHALL [挙動]」の文型で要件を書き、各要件をそのままテストケースに翻訳できることを基準にする ([Kiro Feature specs](https://kiro.dev/docs/specs/feature-specs/))。文法的に正しい EARS 文でも誤った挙動を指定しうる、という指摘もある。

**根拠の場所**: `templates/commands/constitution.md` の Outline 5 段目、`templates/constitution-template.md`、`spec-driven.md` の Phase -1 gates。

---

## 横断の整理

### 共通の骨格は「無しで失敗を見る → 最小の文を足す → 有り無しで比べる」

試験先行の事例 (superpowers・Anthropic の skill 執筆ループ・tools の記事・agents-md-evals) は同じ骨格を持つ。指示が無い状態の挙動を先に観察し、その差を埋める最小の文だけを書き、指示の有り無しを比べて文の存在を正当化する。論文側の ACE・ExpeL・GEPA も、実行の結果 (成功と失敗、得点、文字のフィードバック) を規則の書き換えの入力にする点で同じ形をとる。GEPA はミニバッチで得点が上がった候補だけを残し、事例ごとの最良候補を保つ Pareto 選択 (+12.44) が、常に最良 1 本を選ぶ方式 (+6.05) やビーム探索 (+5.11) を上回った。数値は版で異なり、GRPO との比較は v1 abstract が最大 20%、v2 が 19%、ICLR 掲載ページが 4 タスク平均で 6% と書く ([GEPA](https://arxiv.org/abs/2507.19457))。

文の形についても共通点がある。検証できる具体さを求めること (Claude Code は「Write instructions that are concrete enough to verify」とし、2 スペースの字下げの指定と「コードを適切に整形せよ」を対比する、[Claude Code memory](https://code.claude.com/docs/en/memory))、大きさの上限を置くこと (Claude Code 200 行、Cursor 500 行、Copilot 2 ページ、Codex 合計 32 KiB、superpowers 200 語 / 500 語)、矛盾が実害を生むこと (Claude Code は矛盾した指示のどちらかを恣意的に選びうると書き、GPT-5 ガイドは矛盾の解消に推論トークンを使うと書く) が多くの出典に出てくる。矛盾の害は計測でも確かめられている。ai-harness-doctor は古い指示と矛盾した指示を整理すると 6/28 が 28/28 になったと報告する。ただしこれは作者が作ったデモ repo での自己申告である ([ai-harness-doctor benchmark](https://github.com/NieZhuZhu/ai-harness-doctor/blob/main/benchmark/README.md))。

### 分かれ目 1: 足す関門と削る関門は別々の事例が持つ

規則を足す関門は「失敗の観察」で揃っている。superpowers は捕まえた失敗にしか文を足さず、文言の小試験でも指示なしの対照が失敗しなければ指示を書かない。Claude Code は同じ誤りが 2 回目に起きたとき、Cursor は繰り返されたとき、claude-task-master は 3 ファイル以上で使われたときや同じレビュー指摘が繰り返されたとき、awesome-copilot は「仮定の端の例ではなく観察した失敗の後で」制約を足す。一方、規則を削る関門は「有り無しで差が出ないこと」で、agents-md-evals (A/B の非判別 + Keep Test)、2604.11088 (除去実験の inert)、skill-creator (skill が無くても合格するアサーションの印)、ExpeL (票の枯渇) が持つ。足す側と削る側を一つの手順にまとめた事例は無い。GitHub の調査でも、superpowers が足す側、agents-md-evals が削る側を担うという組み合わせが最も完全に近い。

肥大を抑える位置はさらに 3 つに分かれる。書き換え方で抑える (ACE は全面の書き直しをせず差分だけ足す)、残す条件で抑える (ExpeL の票、agents-md-evals の Keep Test、ICAI の 10% の下限)、入れる条件で抑える (AutoGuide は状態が合う指針だけを入れる。Claude Code はパスで絞る規則、複数段の手順は skill、毎回必ず起きるべきことは hook に振り分ける)。Claude Code の振り分け規則「If something has to happen every time, make it a hook」は、文章で守らせる対象をそもそも減らす点で、他の事例に無い出口を持つ ([Claude Code best practices](https://code.claude.com/docs/en/best-practices))。

### 分かれ目 2: 理由付きの規則か、固い否定形か、失敗に合わせた形か

理由を添える側には Anthropic の憲法、Prompting best practices (理由の説明から一般化できると書く)、skill-creator (大文字の ALWAYS/NEVER を警告の印とみなす)、Kiro (何を決めたかだけでなく、なぜ決めたかを書く)、spec-kit (自明でないときの理由) が並ぶ。OpenAI の GPT-4.1 / GPT-5 ガイドと Claude Code も、強調語を弱めるよう勧める。反対側には、2604.11088 の「否定形の制約だけが個別に有益で、言い回しより存在が効く」という計測結果がある。

superpowers はこの二択の外にある第三の立場をとる。文の形を一つに決めず、観察した失敗の種類から選ぶ。禁止が正しい形になるのは、圧力下で規則を飛ばす失敗に限られる。出力の形が違う失敗には肯定の型の指定を、要素を落とす失敗には必須欄を、条件で変えるべき挙動には観察できる述語つきの条件を当てる。自前の文言比較では、出力の形の失敗に対して禁止の文言は型の指定より悪く、指示なしの対照より悪い傾向だったと書く (数値は非公開)。この立場に立つと、2604.11088 の「否定形だけが有益」は、SWE-bench のバグ修正という特定の失敗の種類での結果として読める。superpowers が強い言い回しの根拠に借りている説得の研究は不適切な依頼への応諾を測ったもので、skill の品質は測っていない。

ニュアンスの置き場所でも出典は分かれる。憲法・skill-creator・Kiro は理由の説明で規則の意図を伝え、読み手が状況に合わせて判断することを期待する。superpowers は文の中の但し書きを禁じ、例外は観察できる条件を持つ別の規則に切り出す。適用除外の但し書きは除外したい対象まで抑えてしまうため、規則が届かない構造に組み替えるとする。前者は判断の余地でニュアンスを保ち、後者は判断の余地を消して条件の分岐でニュアンスを保つ。

これらの対立は、理由付きの側が測定を持たず、否定形の側の測定が低い検出力に依り、形の選択の側の測定が数値を公開していない点で、決着していない。既知の arXiv:2611.04367 が比べた 4 つの書き方 (指示・理由付き・条件・禁止) は、2510.21413 が実在の AGENTS.md から作った 5 分類 (記述的・指示的・禁止的・説明的・条件的) と語彙が重なる。言い回しと成果を結ぶ計測は、この既知の論文と 2604.11088 にほぼ限られる。

### 分かれ目 3: 例を意味の錨にするか

規則の意味を例で固定する事例は多いが、例の役割は事例ごとに違う。Model Spec は規則ごとに適合例と違反例を対にして注釈を付け、境界の判定を示す。GPT-4.1 ガイドは、例で示した重要な挙動は規則の文にも書けと言う (例と規則の食い違いを防ぐ規則、要約経由)。Prompting best practices は例を多様にして意図しない型を拾わせないよう求める。Claude Code は書き直しの前後を対で示す。SkillsBench は少なくとも 1 つの動く例を含む簡潔な手順を推奨し、タスク固有のファイル名や解答のコマンド列は入れないとする ([SkillsBench](https://arxiv.org/abs/2602.12670))。superpowers の言い訳の一覧表は、違反例を逐語で集めた錨と読める。例そのものがニュアンスを保つかを測った研究は見つからなかった。

### 分かれ目 4: 原則から規則へ進むか、事例から原則へ進むか

原則→規則の向きは憲法 (原則で説明できる規則だけを置く)、spec-kit (原則を yes/no の関門へ)、EARS (要件を文型へ) がとる。事例→原則の向きは ICAI (ラベル対から原則を抽出し、事例で検査して残す)、ExpeL・ACE・AutoGuide (経験から insight を抽出)、GEPA (実行記録から指示を改訂)、superpowers (言い訳から基礎原則を足す) がとる。測定を持つのは事例→原則の側だけで、原則→規則の側は判定基準 (説明できるか・検証できるか・テストに翻訳できるか) を持つが測定を持たない。事例→原則の側は、成功と失敗を自動で判定できる環境を前提にしている。

### 分かれ目 5: 計測研究の結論は測る量によって逆を向く

文脈ファイルが役に立つかについて、計測研究は一方向の答えを出していない。2602.11988 は LLM 生成のファイルで成功率が変わらず (SWE-bench -0.5%、CTXbench -2%、どちらも非有意)、コストが約 20〜23% 増え、開発者が書いたファイルでも +2.4% (p=0.21、非有意) にとどまると報告する ([2602.11988](https://arxiv.org/abs/2602.11988))。この論文のベンチマーク名は、検索の要約では「AgentBench」とされていたが、本文では CTXbench である。2601.20404 は実時間の中央値が -28.64%、出力トークンが -16.58% と効率の改善を報告するが、正しさは測っていない ([2601.20404](https://arxiv.org/abs/2601.20404))。SkillsBench は厳選 skill で合格率が 24.3% から 40.6% (+16.2pp) に上がり、自己生成 skill は -1.3pp だったと報告する。タスク数は本文で 84 件、abstract と付録 B では 86 件と論文内で食い違う。skill の長さでは「網羅的」が -2.9pp、4 つ以上の skill の同時使用は +5.9pp にとどまる。

測る量 (成功率・効率・合格率) とタスクの種類が違うため、これらは矛盾とは言い切れない。共通して言えるのは 2 点である。人が書いた・人が審査した物は LLM が自動生成した物より良い (2602.11988 で約 7%、p=0.038。SkillsBench で厳選 +16.2pp 対自己生成 -1.3pp)。そして長く網羅的にすることは効かない (2602.11988 では既存文書と重複する概要が無益、SkillsBench では網羅的が負、IFScale では指示数とともに遵守率が下がり 500 指示で最良でも約 68%)。ただし 2604.11088 は 0〜50 規則で成功率が劣化しなかったと報告しており、指示の遵守とタスクの成功は別の量として扱う必要がある。

### どの出典も持たない物

(1)(2)(3) を一つの出典で揃える事例は無い。superpowers が最も近く、失敗の種類から文の形を選ぶ表と、対照・反復・ばらつきを使う文言の小試験まで持つが、規則を削る工程が無く、評価の数値を公開していない。抽象的な方針を文に分解し、各文が元の方針のニュアンスを保っているかを照合する工程を持つ出典も無い。superpowers の形の選択は観察した失敗を起点にしており、方針を起点にしていない。方針の側から最も近いのは憲法の「原則で説明できるか」という判定と、ICAI の「事例を説明できるか」という検査で、前者は生成の手順を持たず、後者は向きが逆である。規則の抽象度が保たれるかを直接測った実験は、ACE の context collapse の測定だけだった。書き方の方法論に従った結果、規則の遵守や成果が良くなったかを第三者が測った研究は、公式文書・GitHub・論文のどの範囲でも見つからなかった。

読み手が区別する 3 種のメモリ (失敗への反省から書く物・ユーザーが方法を具体的に指示した物・事実や状態を書く物) を区別する出典も無い。部分的に重なる記述はある。失敗から書く物には、Claude Code と Cursor の失敗起点の追加の契機、superpowers の言い訳の捕捉、ExpeL・ACE の経験の蒸留が対応する。superpowers の形の表は失敗を 4 種類 (圧力下の違反・出力の形の誤り・必須要素の欠落・条件で変えるべき挙動) に分けるが、これは失敗の分類で、メモリの出自の分類ではない。また試験の枠組みが失敗の再現を前提にするため、事実や参照の内容には当てにくい。事実を書く物には、Claude Code の「コードから推測できないことだけを書く」、2602.11988 の「README に無いことだけを書く」、SkillsBench の「事実の検索ではなく手順を書く」が対応し、どれも事実の記述は最小にせよという方向を向く。ユーザーの具体的な指示には、agents-md-evals が本人の好み (identity preferences) を「A/B で測れないが残す」区分に置いている点が近い。これは、ユーザー指示型のメモリが有り無しの比較という評価基準になじまないことを示唆する。

### 読み手の 3 層への対応

方法論の層には、試験先行のループ (Anthropic の skill 執筆ループ・superpowers)、判断を既定とし規則には理由を要求する原則 (憲法)、失敗起点の追加の契機 (Claude Code・Cursor・awesome-copilot)、経験からの蒸留 (ACE・ExpeL)、事例に照らした原則の選別 (ICAI) が入る。

評価基準の層には、行動を測る基準と、文面を検査する基準の 2 種類がある。行動を測る基準は、有り無しの差 (skill-creator・agents-md-evals・2604.11088 の除去と単独適用・Copilot の手動 A/B)、圧力下の合否と、反復した出力のばらつき (superpowers。収束すれば文言が効いている)、事例の再現率 (ICAI) である。文面を検査する基準は、検証できる具体さ (Claude Code)、宣言的・検証可能・曖昧語なし (spec-kit)、テストに翻訳できるか (EARS)、原則で説明できるか (憲法)、完全性・明確さ・具体性・例の 4 観点 12 点満点のルーブリック (SkillsBench)、smell の検出 (2607.01456・cclint)、大きさと矛盾の点検 (`/doctor prompt-audit`・ai-harness-doctor) である。文面の基準と行動の差を結び付けた研究は無い。SkillsBench でもルーブリックの点数と合格率の関係は確認されていない。

規則の層には、文型 (EARS の WHEN … SHALL、spec-kit の名前 + 規則 + 理由、Claude Code の 1 行の具体的な指示、superpowers の失敗の種類ごとの 4 つの形と、但し書きを使わず観察できる条件で分岐させる規則)、意味の錨 (Model Spec の適合例と違反例、superpowers の言い訳の一覧表と危険信号)、肥大の歯止め (語数・行数の上限、差分更新、票、Keep Test) が入る。そして、層と層をつなぐ「評価基準を満たす具体的な文を、メモリの種類ごとにどう作るか」という段階が、どの出典でも最も手薄である。

---

## 調査範囲と限界

Cline と Windsurf の規則の文書、OpenAI の prompt optimizer のページ、Anthropic の「Demystifying evals for AI agents」、BMAD・Tessl・Devin knowledge・Collective Constitutional AI は取得していない。OPRO・APE・DSPy (MIPRO)・TextGrad・PromptWizard・Reflexion・A-MEM・Agent Workflow Memory・MemGPT (Letta) は存在の確認もしていない。GitHub は Issue/PR を検索したが、Discussions と openai/codex・agentsmd/agents.md の Issue は調べていない。cline の Memory Bank、coleam00/context-engineering-intro、gsd-build/get-shit-done は検索に出たが中身を開いていない。Model Spec は末尾約 2.3 万文字、Anthropic の憲法は 10 万文字以降、GEPA と SkillsBench は本文の後半を読んでいない。Model Spec には 2026-10-29 版より新しい版がある。「Curse of Instructions」(ICLR 2025) は原論文を確認できなかったため採用していない。Model Spec・spec-kit・claude-task-master・Copilot・Cursor・Kiro・Gemini CLI・ICAI・憲法の記述は要約を挟んだ取得で、原文の文言を確かめていない。論文の数値 (成功率・pp の差・トークン・p 値) も要約を挟んだ取得で、原文の表とは照合していない。論文内の食い違い (SkillsBench のタスク数、ACE の改善幅、ExpeL の比較値、GEPA の版差、2602.11988 のベンチマーク名) は、見つけた範囲で本文に個別に注記した。
