# エージェント指示文・文脈ファイル・メモリの書き方と品質測定に関する論文調査 (2026-11-06 時点)

除外: arXiv:2611.04367 (既知)。
凡例: 基準1=書き方の方法論 / 基準2=書いたものの品質の評価基準 / 基準3=抽象原則・経験から具体規則を導く手順 (ニュアンス損失と不要規則の防止)。
引用の扱い: 「」内の短い引用は WebFetch が返した原文断片のみ。原文断片を確認できなかった箇所は「(言い換え)」と明記した。WebFetch は小モデルによる要約を返すため、数値は要約経由である点に注意 (論文内の不整合は個別に注記)。

## 候補一覧 (検証状況)

- 全文または abstract を fetch で確認: 2602.11988 / 2601.20404 / 2604.11088 / 2602.12670 / 2607.01456 / 2510.21413 / 2511.12884 / 2507.11538 / 2509.21051 / 2510.04618 / 2308.10144 / 2507.19457 / 2603.03456
- 検索結果の記述のみ (本文は未 fetch): 2509.14744 / 2504.07952 / 2403.08978 / 2602.14690 / 2607.15557
- 調査しきれず (存在確認なし、記録のみ): Reflexion / A-MEM / Agent Workflow Memory / MemGPT(Letta) / OPRO / APE / DSPy(MIPRO) / TextGrad / PromptWizard / "system prompt learning"。MIPROv2 は GEPA・ACE の比較対象として登場するのを確認したのみ。

---

## 1. エージェント文脈ファイルの研究 (AGENTS.md / CLAUDE.md / 規則ファイル)

### Takeaway
2026 年に、文脈ファイルが成功率を上げない・コストを増やすとする統制研究 (ETH Zurich 系 2602.11988) が実在することを確認した。一方、効率 (時間・出力トークン) は下がるとする研究 (2601.20404) と、規則の中身より存在が効き、「禁止」形の規則だけが個別に有益とする研究 (2604.11088) があり、結果は一方向ではない。実態調査 (2509.14744 / 2511.12884 / 2510.21413) は内容と形式を記述するだけで、書き方の良し悪しの評価基準は持たない。

### Cited Findings

#### [C1] Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?
- URL: https://arxiv.org/abs/2602.11988 (fetch で確認。著者 Gloaguen, Mündler-Sasahara, Müller, Raychev, Vechev。ICLR 2026 掲載。v3 は 2026-09-29 改訂)
- 対象: context file (AGENTS.md 系)
- 基準1: partial。「Human-written files should contain only instructions not already in the README」(言い換え。推奨は慣習・非機能要件に限る、概要は不要)。場所: Recommendations
- 基準2: partial。成功率・ステップ数・推論コストで事後評価する枠組み。書き方の品質指標は無い。場所: Evaluation design
- 基準3: no。規則の導出手順は無い。「any attempts to improve performance should be rigorously evaluated」は評価を促す一文 (abstract)
- 評価設計: SWE-bench Lite 300 タスク (Python 11 リポジトリ、文脈ファイル無し、LLM 生成ファイルで評価) と、新規 CTXbench 138 インスタンス (Python 12 リポジトリ、開発者コミット済みファイルあり、PR 5,694 件から絞り込み)。エージェント: Claude Code (Sonnet-4.5)、Codex (GPT-5.2 / GPT-5.1 mini)、Qwen Code (Qwen3-30b-coder)。条件: 無し / LLM 生成 / 開発者作成 (CTXbench のみ)。各インスタンス 1 回サンプル。指標: 成功率・ステップ数・コスト。
- 結果: LLM 生成 vs 無し は SWE-bench -0.5%、CTXbench -2% (どちらも非有意)。開発者作成 vs 無し は +2.4% (p=0.21、非有意)。開発者作成 vs LLM 生成は約 7% 高く有意 (p=0.038)。LLM 生成でコスト約 +20% (SWE-bench) / +23% (CTXbench)、ステップ +2.5 / +3.9。文書をすべて除くと LLM 生成ファイルは +2.7% 改善し、開発者作成ファイルを上回った (既存文書との重複が原因との著者の解釈)。概要セクションは有益でなかった。
- 注意: 検索要約は「AgentBench」と書いていたが、本文 HTML は「CTXbench」。PDF の図ファイル名には PlanBench の語もあり、ベンチ名は本文で確認が要る。
- タグ: measurement study

#### [C2] On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents
- URL: https://arxiv.org/abs/2601.20404 (HTML を fetch で確認。Lulla, Mohsenimofidi, Galster, Zhang, Baltes, Treude。JAWs 2026)
- 対象: context file (AGENTS.md)
- 基準1: no。書き方の助言なし
- 基準2: partial。時間とトークンのみ測り、正しさは測らない (論文自身が限界として明記)。場所: Evaluation design / Limitations
- 基準3: no
- 評価設計: 132 リポジトリから 10 (資格のある 26 からランダム) 、マージ済み PR 124 件 (各リポジトリ最大 15、変更 100 行以下・5 ファイル以下)。エージェントは Codex (gpt-5.2-codex) のみ。同一スナップショットで AGENTS.md あり/なしの対応あり比較。指標: 実時間と各種トークン。Wilcoxon 符号付順位検定。
- 結果: 実時間の中央値 98.57s → 70.34s (-28.64%)、出力トークン中央値 2,925 → 2,440 (-16.58%)。入力・合計トークンは有意でない。50 件の目視確認は「空でない変更」の確認にとどまる。
- 注意: C1 と結論の向きが違う (効率は改善、C1 は成功率変化なし・コスト増)。エージェント・モデル・測る量・タスク規模 (小さい PR のみ) が違うため、矛盾とは言い切れない。
- タグ: measurement study

#### [C3] Guardrails Beat Guidance: A Large-Scale Study of Rules, Skills, and Persistent Configuration for Coding Agents (v1 題名 "Do Agent Rules Shape or Distort? ...")
- URL: https://arxiv.org/abs/2604.11088 (fetch で確認。Zhang ら。2026-04 提出、v2 2026-05-28)
- 対象: rule file (CLAUDE.md / .cursorrules)。題名に Skills とあるが、skill・persona の実験は無く関連チャネルとして論じるのみ
- 基準1: partial。「Prefer negative constraints」(言い換え。「do not X」を「do X」より優先、位置づけは Box 1 の実務推奨)。「presence beats phrasing」(言い換え。文言は凝らない)。場所: Practical recommendations
- 基準2: yes。規則 1 本ずつの除去 (ablation)、単独適用での破壊タスク数 (distortion)、規則対の加法性 (superposition) という 3 種の測定を定義。場所: Experiment 4
- 基準3: partial。規則の「効く/歪める/無関係」を実測で仕分ける手順はあるが、抽象原則から規則を導く手順ではない
- 評価設計: SWE-bench Verified 500 件を 3 回ずつ走らせ (1,500 回)、1〜2 回だけ解ける 58 件を「判別的」タスクとして採用。Claude Code + Claude Opus 4.6 を固定し、CLAUDE.md の差し替えのみ変える対応あり設計 (McNemar / Cochran's Q)。実験 1 (規則の出所 8 条件: 無し・厳選・ランダム・人気・同領域・別領域・形式未変換・文シャッフル): 50.0%〜63.8%、条件間に有意差なし (Q=4.70, p=0.697)。実験 2 (規則数 0〜50): 59〜67% の帯、有意差なし (p=0.227)、シード間差が最大 17pp。実験 3 (規則種別 5 種各 10 本): 有意差なし。実験 4 (35 タスク、手作り 18 規則): 5pp 超の変化で shaping 3 本・distorting 4 本・inert 11 本。単独適用では 18 本中 14 本が、ベースラインで安定して解けていた 17 タスクのうち 2 件以上を壊した。
- 結論の強さ: 著者自身が低検出力 (n=58 / 35 で検出可能なのは約 15pp 差)、単一ベンダー・単一モデル・Python バグ修正のみ、と限界を明記。個別有意差は多重比較補正で残らない。見出しの「全ての有益規則は否定形」は 7 条件の符号検定 (p=0.008) に依拠。
- 本文と abstract の差: abstract 要約は「ランダム規則も厳選と同等 (+13.8pp)」としており、ランダム規則が効く理由を context priming と解釈している。
- 補足: 679 規則ファイル (25,532 規則) の収集は abstract にあるが、本文での扱いは未確認。
- タグ: measurement study

#### [C4] On the Use of Agentic Coding Manifests: An Empirical Study of Claude Code
- URL: https://arxiv.org/abs/2509.14744 (検索結果のみ。本文は未 fetch。HTML は https://arxiv.org/html/2509.14744v1)
- 対象: context file (CLAUDE.md)
- 基準1/2/3: 未確認 (検索要約には内容分析のみ。253 ファイル・242 リポジトリ、構造は浅い、最頻内容は build/run・実装詳細・アーキテクチャ)
- 評価設計: 内容分析のみ (言い換え、検索要約)
- タグ: measurement study

#### [C5] Agent READMEs: An Empirical Study of Context Files for Agentic Coding
- URL: https://arxiv.org/abs/2511.12884 (HTML を fetch で確認)
- 対象: context file (CLAUDE.md / AGENTS.md / copilot-instructions.md)
- 基準1: no。公式の品質基準は無く、推奨は暗黙 (build・test・アーキテクチャを書く、非機能要件を明記、コードと同期を保つ)
- 基準2: partial。可読性 (Flesch Reading Ease: Claude Code 中央値 16.6 =「非常に難しい」)、語数、更新頻度で記述的に測る。品質との相関は測っていない
- 基準3: no
- 評価設計: AIDev データセットから 8,370 リポジトリ (星 5 以上) を絞り、2,303 ファイル / 1,925 リポジトリ (Claude Code 922・Codex 694・Copilot 687)。16 カテゴリの人手ラベルは Claude Code 332 ファイル。GPT-5 による自動分類は micro-F1 0.79。
- 結果: 内容は機能面に偏る (テスト 75.0%・実装詳細 69.9%・アーキテクチャ 67.7%・ビルド 62.3%、セキュリティ 14.5%・性能 14.5%・UI/UX 8.7%)。更新は追記中心で削除は無視できる量。Claude Code ファイルの 67.4% が複数コミットで修正。
- タグ: measurement study

#### [C6] Context Engineering for AI Agents in Open-Source Software
- URL: https://arxiv.org/abs/2510.21413 (HTML を fetch で確認。Mohsenimofidi ら)
- 対象: context file (AGENTS.md ほか 4 形式)
- 基準1: no (論文自身が「evidence-based な推奨は無い」と明言する構造)
- 基準2: no。品質基準なし。エージェント挙動や成果は測っていない
- 基準3: no
- 内容: 10,000 リポジトリ (48,795 から絞り込み) 中 466 (5%) が文脈ファイルを持つ。AGENTS.md 155 件を分析。「Conventions」節 50 件から書き方の 5 分類 (記述的・指示的・禁止的・説明的・条件的) を作成。AGENTS.md の 50% は一度も変更されない。
- 位置づけ: 既知の 2611.04367 が比較した 4 つの書き方 (指示・理由付き・条件・禁止) は、この 5 分類の語彙と重なる。2611.04367 の前提となる実態分類として使える。
- タグ: measurement study

#### [C7] Asymmetric Goal Drift in Coding Agents Under Value Conflict
- URL: https://arxiv.org/abs/2603.03456 (HTML を fetch で確認。Saebo ら)
- 対象: context file (AGENTS.md に置いた制約)
- 基準1: no (著者は書き方を検証していない)
- 基準2: partial。制約の違反を正規表現でステップごとに採点し、LLM 判定は妥当性検証にとどめる
- 基準3: no
- 評価設計: OpenCode、12 の機能実装タスクを毎回ランダム順、コード内コメントによる圧力あり/なしの 2×2、各実験 10 回、モデル 3 種 (GPT-5 mini・Haiku 4.5・Grok Code Fast 1)、価値対 3 種。例: GPT-5 mini の Efficiency→Security で 9 ステップ目までに違反 100%。
- 含意: AGENTS.md の制約は長いセッションとコード内の反対コメントで破られる。この論文自身は文言を変えた実験をしていない。
- タグ: measurement study

#### 補足 (検索結果のみ、本文未確認)
- Configuring Agentic AI Coding Tools: An Exploratory Study — https://arxiv.org/abs/2602.14690 (検索要約: 5 ツール 8 機構、2,926 リポジトリ。内容分析)

### Inferences
- C1 と C3 は、文脈ファイルの「中身の良し悪し」ではなく「存在」「概要の重複」「検出力」が結果を左右している可能性を示す。規則の質を測るには、タスクを判別的に絞る (C3) か、既存文書との重複を除いて測る (C1) 設計が要る。
- C1 (成功率ほぼ不変・コスト増) と C2 (時間短縮) は測る量が違い、「文脈ファイルは役に立つか」には単一の答えが無い。効率・成功率・コストを分けて報告する必要がある。
- 実態調査 (C4〜C6) は書き方の因果を測っていない。書き方と成果を結ぶ測定は C3 と、既知の 2611.04367 に限られる。

### Gaps
- C1 の本文 (HTML) は最後の約 3,000 文字を読めていない。人手/LLM 生成の差の統計処理の細部は未確認。
- C4 (2509.14744) と 2602.14690 は検索要約のみ。

---

## 2. 指示数・遵守・書き方 (IFScale、curse of instructions、否定形、順序)

### Takeaway
指示数が増えると遵守率が下がる (IFScale・When Instructions Multiply) ことは測定されている。否定形/肯定形の効果を規則ファイルで測ったのは 2604.11088 のみ確認できた (強調語の効果、規則順序、system prompt 内の "lost in the middle" を直接測った論文は今回の調査で見つからなかった)。

### Cited Findings

#### [C8] How Many Instructions Can LLMs Follow at Once? (IFScale)
- URL: https://arxiv.org/abs/2507.11538 (fetch で確認。Jaroslawicz, Whiting, Shah, Maamari。2025-07)
- 対象: system prompt 型のタスク指示 (規則ファイルそのものではない)
- 基準1: no
- 基準2: partial。キーワード包含を自動採点する指標 (業務レポート作成)。場所: Evaluation design
- 基準3: no
- 評価設計: キーワード包含の指示を 10〜500 個 (10 刻み) に増やす。20 モデル・7 社。
- 結果: 最良の最前線モデルでも 500 指示で約 68%。モデルの規模・推論能力に応じて 3 つの劣化パターン (推論モデルは閾値型の劣化)。「bias toward earlier instructions」(先の指示への偏り)。誤りは脱落が支配的 (検索要約。fetch ページには脱落/変更の内訳なし)。
- 限界: 指示は無関係なキーワード包含で、実務の規則とは性質が異なる。
- タグ: measurement study

#### [C9] When Instructions Multiply: Measuring and Estimating LLM Capabilities of Multiple Instructions Following
- URL: https://arxiv.org/abs/2509.21051 (fetch で確認。Harada ら。EMNLP 2025 採択)
- 対象: system prompt 型のタスク指示
- 基準1: no / 基準3: no
- 基準2: partial。指示数を説明変数とするロジスティック回帰で未見の指示組合せの遵守率を約 10% 誤差で推定する。500 件 (ManyIFEval) / 300 件 (StyleMBPP) で推定に足りるとする。
- 評価設計: ManyIFEval (IFEval を拡張、最大 10 指示)、StyleMBPP (コード生成、最大 6)、10 モデル。
- 前身「Curse of Instructions」(ICLR 2025、Harada ら): OpenReview ID R6q67CDBCH は検索結果で得たが、ページは認証画面で内容を確認できなかった。同論文の数値 (GPT-4o 約 15%、Claude-3.5 約 44% など) と自己修正の効果は二次情報 (ベトナム語要約) のみで、本ノートでは採用しない。
- タグ: measurement study

### Inferences
- 規則を増やすほど全規則を守る確率は下がるが、C3 は 0〜50 規則で成功率が劣化しなかったと報告する。指示遵守と、コーディングタスクの成功率は別の量。規則数の上限は、測る量 (遵守か成功か) を決めてから議論する必要がある。

### Gaps
- 強調語 (MUST / IMPORTANT / 大文字)、規則の順序、system prompt 中央の埋没を規則ファイルで測った論文は見つからなかった。C3 は「文言は凝らない」と述べるが、強調語の変種は測っていない (fetch で確認)。
- Curse of Instructions 原論文の arXiv ページを見つけられなかった。
- 否定形の失敗機構を調べた arXiv 2601.08070 は検索結果で存在を見ただけで、内容は未確認。

---

## 3. 経験の規則化・メモリ蒸留

### Takeaway
ACE・ExpeL・Dynamic Cheatsheet・AutoGuide は、いずれも経験から自然言語の知見を取り出して文脈に積む。肥大とニュアンス損失への対処は、(a) 差分更新、(b) 票数・カウンタによる除去、(c) 条件付き記述による適用範囲の限定、の 3 系統に分かれる。

### Cited Findings

#### [C10] Agentic Context Engineering (ACE)
- URL: https://arxiv.org/abs/2510.04618 (fetch で確認。Zhang ら、Zou・Olukotun を含む 13 名。ICLR 2026、最新 v3 は 2026-03)
- 対象: memory / system prompt (進化する playbook)
- 基準1: partial。「comprehensive, evolving playbooks」(言い換え)。短い要約でなく詳細な項目の積み上げを推奨。場所: Method
- 基準2: yes。AppWorld・FiNER・Formula で、ablation (Reflector 有無・複数エポック有無) とコスト (遅延・rollout 数・トークン費用) を併せて測る。場所: Experiments
- 基準3: yes。Generator が試行を出し、Reflector が批評して教訓を抽出 (最大 5 ラウンド) し、Curator が差分項目 (delta) に変換、マージは LLM でなく非 LLM のロジックで行う。場所: Method
- 評価設計: 全役割 DeepSeek-V3.1 (非思考)、batch size 1。比較対象: ICL・MIPROv2・GEPA・Dynamic Cheatsheet。AppWorld 平均: Base ReAct 42.4 / ICL 46.0 / GEPA 46.4 / ACE offline (正解あり) 59.4 / online 59.5。リーダーボードで IBM CUGA (60.3) とほぼ同等、challenge split で CUGA を TGC 8.4% 上回る。金融 (FiNER/Formula): Base 69.1 / GEPA 72.5 / ACE offline 81.9。Ablation: Reflector・複数エポックなし 55.1、複数エポックなし 56.8、完全版 59.4。遅延は offline AppWorld で GEPA 比 -82.3%、online FiNER で DC 比 -91.5%。
- 不整合: 本文は ICL・GEPA に対し +12.3% / +11.9% と書くが、表から計算すると約 13.4 / 13.0 ポイント。
- タグ: memory-distillation method

#### [C11] ExpeL: LLM Agents Are Experiential Learners
- URL: https://arxiv.org/abs/2308.10144 (fetch で確認。Zhao ら。AAAI-24)
- 対象: memory (自然言語の insight)
- 基準1: no
- 基準2: partial。HotpotQA・ALFWorld・WebShop の成功率で、insight のみ / 成功軌跡の検索のみ / 手作り insight との ablation。場所: Experiments
- 基準3: yes。成功/失敗対、または成功軌跡 L 本から LLM が ADD・EDIT・UPVOTE・DOWNVOTE を発行。「If an insight's importance count reaches zero, it will be removed」。新規 insight の重要度は 2 から開始。場所: Method (Insight Extraction)
- 評価設計: HotpotQA 100 タスク、ALFWorld 134 タスク、WebShop 100 タスク、FEVER は転移先 (件数は本文に明記なし)。4 分割検証、平均と標準誤差。抽出モデルは gpt-4-0613。
- 結果 (Table 3 成功率%): HotpotQA は ReAct 28.0、手作り insight 32.0、reflections 追加 29.0、gpt-3.5 で抽出 32.0、ExpeL 39.0。ALFWorld は ReAct 40.0、ランダム検索 42.5、推論類似検索 48.5、ExpeL 59.0。学習した insight が手作りに勝つ。reflections を足すと悪化。
- 不整合: 本文は ALFWorld R3 で Reflexion 54%、表は 54.4% で、ExpeL の差 (59 vs 54) の読み方は表で確認が要る。
- タグ: memory-distillation method

#### [C12] Dynamic Cheatsheet: Test-Time Learning with Adaptive Memory
- URL: https://arxiv.org/abs/2504.07952 (検索結果のみ。Suzgun, Yuksekgonul, Bianchi, Jurafsky, Zou。EACL 2026)
- 対象: memory
- 基準1: no / 基準2: partial (空メモリ・全履歴追記・キュレーション無し検索との比較。検索要約)
- 基準3: partial。curator が正解ラベル無しで解の質を判断し、簡潔で転用可能な断片を保つ (言い換え)。DC-Cu は逐次更新、DC-RS は類似検索を足す。
- 結果 (論文自己報告、検索要約): GPT-4o の Game of 24 が 10% → 99% (Python solver の再利用)、Claude 3.5 Sonnet の AIME 精度が 2 倍超。
- 本文は未 fetch。
- タグ: memory-distillation method

#### [C13] AutoGuide: Automated Generation and Selection of State-Aware Guidelines for LLM Agents
- URL: https://arxiv.org/abs/2403.08978 (検索結果のみ。Fu, Kim ら)
- 対象: rule / guideline (プロンプトに入れる指針)
- 基準1: partial。各指針を「適用される状態」を述べた条件付きの簡潔な自然言語で書く (言い換え)
- 基準2: partial。逐次意思決定ベンチ (実環境の Web ナビゲーション含む) で LLM ベースラインに勝つ (検索要約。N と数値は未確認)
- 基準3: yes (言い換え)。オフライン経験から指針を抽出し、テスト時は軌跡を状態説明に要約して該当指針だけをプロンプトに入れる。成功のみ/失敗のみのデータでも抽出可能。
- 本文は未 fetch。
- タグ: memory-distillation method

#### 補足: 調べきれなかったもの
- Reflexion / A-MEM / Agent Workflow Memory / MemGPT(Letta): 存在確認も fetch もしていない。

### Inferences
- ACE の delta 更新、ExpeL の票とカウンタ、AutoGuide の適用条件は、肥大を防ぐ位置が違う。ACE は書き換え方 (全面書き換えをしない)、ExpeL は残す条件 (票が尽きたら消す)、AutoGuide は入れる条件 (状態が合うときだけ入れる)。
- いずれも実行環境で成功/失敗が測れるタスクが前提。評価の無い領域 (対人コミュニケーションの規約など) に直接は移せない。

### Gaps
- C12・C13 は本文を読んでいない。N・指標・ablation の数値は未確認。
- 各手法の「規則の抽象度」を保つ仕組みを直接測った実験は、ACE の context collapse 測定 (後述) 以外に見つからなかった。

---

## 4. プロンプト/指示の最適化 (評価駆動の規則導出)

### Takeaway
GEPA は、実行軌跡と文字のフィードバックから指示を反射的に書き換え、候補を事例ごとの Pareto で保持する。評価で候補を選ぶ点が、他のメモリ系手法 (C10〜C13) との違い。OPRO・APE・DSPy・TextGrad・PromptWizard は今回 fetch していない。

### Cited Findings

#### [C14] GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning
- URL: https://arxiv.org/abs/2507.19457 (HTML v2 を fetch で確認。Agrawal ら。ICLR 2026 oral)
- 対象: system prompt (モジュール単位の指示)
- 基準1: no
- 基準2: yes。訓練データを feedback 用と Pareto 用に分け、ミニバッチで改善した候補だけを Pareto 集合で全面評価する。フィードバック関数 μf は、スカラー指標にコンパイルエラーや落ちた採点基準などの文字情報を足す。場所: Method
- 基準3: yes。リフレクション LM が軌跡を読み 1 モジュールの指示を改訂し、ミニバッチ得点が上がったときだけ採用 (場所: Method)。事例ごとの最良候補を残す Pareto 選択で単一系統への収束を避ける。
- 評価設計: HotpotQA・IFBench・HoVer・PUPA (+ AIME-2025・LiveBench-Math)。Qwen3 8B と GPT-4.1 Mini。GEPA は 2,400〜7,100 rollout、GRPO は全タスク 24,000 rollout。Qwen3 8B の合計改善: GEPA +9.62、GEPA+Merge +7.17、GRPO +3.68、MIPROv2 +2.61。GPT-4.1 Mini: GEPA+Merge +13.33、GEPA +12.19、MIPROv2 +5.64。IFBench は 678 rollout で 38.61% (GRPO は 24,000 rollout で 35.88%)。Qwen3 8B で最適化した指示を GPT-4.1 Mini に移して +9.00。Pareto 選択 +12.44 に対し、常に最良候補 +6.05、ビーム探索 +5.11。GEPA の指示は MIPROv2 の最大 9.2 倍短い。
- 版差: v1 abstract は GRPO 比「最大 20%・rollout 最大 35 倍少」、v2 は 19% に下げ、ICLR 掲載ページは 4 タスク平均 6%。引用時は版を明記。
- 注意: 規則の「ニュアンス損失」を主題とした実験ではない。検証用 Pareto 集合と test の汎化差が小さいという報告と、宣言的で具体的な指針を含む例の提示が間接的な根拠。
- タグ: prompt optimization

### Inferences
- 候補指示の評価に「事例ごとの得点」と「文字の失敗理由」を両方使う点が、他の最適化 (MIPROv2) との差。規則 1 本の効果を事例単位で測る C3 の ablation と、評価の単位が近い。

### Gaps
- OPRO・APE・DSPy (MIPRO)・TextGrad・PromptWizard・"system prompt learning" は未調査。GEPA 論文が MIPROv2 を比較対象にしていることのみ確認。
- GEPA の全文の後半 (約 81,000 文字) は未読。

---

## 5. SKILL.md の書き方と評価 (2025–2026)

### Takeaway
SkillsBench (2602.12670) が、skill の有無・自己生成を比較する最初の大規模ベンチとして実在する。手作業で厳選した skill は平均 +16.2pp、自己生成は効かない。SKILL.md の品質を静的に検査する研究 (2607.01456) も 2026-07 に出ているが、品質と成果の相関は未確認。

### Cited Findings

#### [C15] SkillsBench: Benchmarking How Well Agent Skills Work Across Diverse Tasks
- URL: https://arxiv.org/abs/2602.12670 (HTML v1 を fetch で確認。Li ら。2026-02)
- 対象: skill (SKILL.md)
- 基準1: yes。「concise, stepwise guidance with at least one working example」(Discussion。手順型の how-to を書き、事実の検索は書かない。一事例でなくタスクの類に適用できる形にする。タスク固有のファイル名・パス・定数・解答のコマンド列は含めない)。場所: Discussion / Skill construction
- 基準2: yes。エコシステム用ルーブリック: 完全性・明確さ・具体性・例の 4 観点を各 0〜3 点 (12 点満点)。採用 skill は 9 点以上、採用分の平均は 10.1/12。人手レビューは「誤り無し・内部矛盾無し・ベンチ外の類似タスクにも有用」。場所: Skill quality criteria
- 基準3: partial。自己生成 skill が効かないことを実測で示す (−1.3pp)。ただし、抽象原則から規則を導く手順そのものは扱わない。
- 評価設計: 84 タスク (abstract は 86、付録 B は 86 が審査通過と記載。論文内の不整合) / 11 領域、エージェント・モデル 7 構成 (Claude Code・Gemini CLI・Codex CLI。GPT-5.2・Claude Opus 4.5/4.6・Sonnet 4.5・Haiku 4.5・Gemini 3 Pro/Flash)、7,308 本の有効軌跡。条件: skill 無し / 厳選 / 自己生成 (自己生成は 5 構成)。指標: 5 試行平均の合格率、正規化利得。
- 結果: 無し 24.3% → 厳選 40.6% (+16.2pp、構成別 +13.6〜+23.3pp)。領域別は医療 +51.9pp、ソフトウェア工学 +4.5pp。84 タスク中 16 が負の効果。skill 数は 1 つで +17.8pp、2〜3 つで +18.6pp、4 つ以上で +5.9pp。長さは詳細 +18.8pp、簡潔 +17.1pp、標準 +10.1pp、網羅的 −2.9pp。Haiku 4.5 は skill ありで 27.7% (なしは 11.0%)。
- タグ: measurement study / methodology (skill 構成の推奨を含む)

#### [C16] From Anatomy to Smells: An Empirical Study of SKILL.md in Agent Skills
- URL: https://arxiv.org/abs/2607.01456 (fetch で確認。Hong, Imani, Ahmed。2026-07)
- 対象: skill (SKILL.md)
- 基準1: partial。文献レビュー 29 件から執筆のベストプラクティスを抽出 (一覧は abstract に無く未確認)
- 基準2: yes (候補)。ベストプラクティス違反を「skill smell」と定義し、自動検出器で数える。「over 99% of SKILL.md files contain at least one skill smell」。場所: abstract。検出器の精度・smell と成果の相関は fetch したページに記載なし。
- 基準3: no
- 評価設計: 実在 skill 238 件を質的分析し、13 の上位・44 の下位の意味構成要素に分類。smell は進化しても「rarely disappear」。
- 注意: 検索結果は docshare の複製ページも出していた。arXiv の abstract は fetch 済み。
- タグ: measurement study / methodology

#### 補足 (検索結果のみ、本文未確認)
- SkillCorpus: https://arxiv.org/abs/2607.15557 (検索要約: 約 82.1 万件の skill から 96,401 件に絞り、有用性・頑健性・安全性で採点。出所は alphaxiv / papers.cool の要約)

### Inferences
- C15 の「厳選 skill のみ有効、自己生成は無効」は、抽象から具体への変換を人手の審査で通した成果物だけが効くという読み方ができる。ただし 4 観点ルーブリックの点数と成果の関係は論文内で未確認。
- C15 の skill 数・長さの結果は、短く焦点を絞る方が良いという方向で C1 (文脈ファイルは最小限) と一致する。

### Gaps
- C15 は本文の後半約 58,000 文字を未読。ルーブリックの点数と合格率の関係の有無は未確認。
- skill の書き方の因果を、文言を変えて測った研究は見つからなかった。

---

## 重点 4 件の方法と、抽象から具体への段階の扱い

### ACE (2510.04618): 肥大とニュアンス損失を「差分だけ足す」ことで防ぐ
Generator が実行軌跡を出し、Reflector が成功・失敗の原因を批評して教訓を抽出し、Curator がそれを ID と helpful/harmful カウンタを持つ箇条書き項目の差分に変換する。マージは LLM ではなく決まったロジックで行い、新規項目は追記、既存項目は更新してカウンタを増やし、意味埋め込みで重複を除く。文脈全体を LLM に書き直させないため、書き直しのたびに詳細が落ちる現象 (context collapse) を避ける。AppWorld の実測では、ある文脈が 18,282 トークン・精度 66.7 だった次のステップで 122 トークン・57.1 に崩れ、無適応のベースライン 63.7 を下回った。短く要約する最適化器が領域固有の洞察を落とす傾向 (brevity bias) も、同じ論文が問題として定義している。抽象度の管理は項目単位 (戦略・概念・失敗モード) で行い、不要規則の除去は helpful/harmful カウンタと重複除去が担う。ただし、不要規則を実際に削る基準の効果を単独で測った ablation は確認していない。評価は、ablation (Reflector・複数エポックの有無: 55.1 / 56.8 / 59.4) とコスト (GEPA 比で遅延 -82.3%) を併記する設計。

### ExpeL (2308.10144): 票で規則を育て、票が尽きたら消す
成功/失敗の対、または成功軌跡の集合を LLM に見せ、既存の insight 集合に対して ADD・EDIT・UPVOTE・DOWNVOTE のどれかを発行させる。新規 insight は重要度 2 で始まり、EDIT と UPVOTE で増え、DOWNVOTE で減り、0 になれば除去される。肥大は「票の尽きた規則を消す」ことで抑え、ニュアンスは EDIT で既存の insight を直す形で残す。評価は ablation で、学習した insight が手作りより良く (HotpotQA 39.0 対 32.0)、reflections を足すと悪化する (29.0)、成功軌跡の検索とも比較する。限界は、抽出に使うモデルの品質依存 (gpt-4-0613 が gpt-3.5 より演算子に従い幻覚が少ないと著者が報告) と、成功/失敗が測れる環境が前提な点。

### GEPA (2507.19457): 評価で候補を選び、事例ごとの最良を捨てない
ミニバッチで走らせて得た軌跡・得点・文字フィードバックを、リフレクション LM に読ませて 1 モジュールの指示を改訂させる。ミニバッチで改善したときだけ候補に加え、Pareto 用の検証集合で全面評価する。選択は、事例ごとに最良の候補を残す Pareto 方式。常に最良 1 本を選ぶ方式 (+6.05) やビーム探索 (+5.11) より高い (+12.44)。ニュアンス損失に直接対処する機構ではないが、事例ごとの専門性を持つ候補を残すことで、平均では劣る特化した指示が消えるのを防ぐ。肥大の抑制は、結果として指示が MIPROv2 の最大 9.2 倍短くなるという観察にとどまる。

### Guardrails Beat Guidance (2604.11088): 規則 1 本ずつの必要性を、除去と単独適用で測る
規則そのものの導出法ではなく、書かれた規則の「不要さ」を測る手順を提供する。判別的タスク (3 回中 1〜2 回解ける) だけに絞って検出力を確保し、規則を 1 本ずつ除去 (ablation) して 5pp 超の変化を shaping / distorting、それ未満を inert と分類した。18 規則のうち inert が 11 本。さらに規則を単独で適用して、元々解けていたタスクを壊すか (distortion) を調べ、18 本中 14 本が 2 件以上を壊した。規則対の加法性も測る。結論は、否定形の制約のみが個別に有益で肯定形の指示が有害という傾向。ただし著者自身が、検出力が低く (n=58 / 35 で約 15pp 差が検出限界)、個別の有意差は多重比較補正に耐えないと明記しており、傾向の強さは符号検定 (7 条件・p=0.008) に依存する。規則数 0〜50 で成功率が劣化しなかった点と、ランダム規則が厳選規則と同等だった点は、規則の中身より存在が効くという解釈 (context priming) を支持するが、規則の質を測る指標としてこの実験設計をそのまま使うと、質の差を検出できない恐れがある。

### 次点 (重点には入れなかった理由)
- AutoGuide (2403.08978): 基準3 に合うが、本文未確認。適用条件を規則に埋め込む設計は、本ノートの根拠が検索要約のみ。
- SkillsBench (2602.12670): 基準1・2 は強いが、基準3 (導出手順) は弱い。
