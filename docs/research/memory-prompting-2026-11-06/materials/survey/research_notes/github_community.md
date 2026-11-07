# GitHub community resources: methodologies for writing agent instruction/memory files

Research date: 2026-11-06. Stars and push dates come from `gh api repos/...` on that date. File contents were read via `gh api ... -H "Accept: application/vnd.github.raw"` (raw files) unless marked "via WebFetch summary". arXiv:2611.04367 excluded as instructed.

Criteria: C1 = methodology for how to write; C2 = evaluation criteria for the written result; C3 = procedure to derive concrete rules from abstract principles while preventing nuance loss and rule bloat.

## Candidate 1: obra/superpowers, skills/writing-skills (Does it meet all three criteria?)

### Takeaway
Of everything found, it is the only community artifact that covers all three criteria in one workflow, with C3 handled by "add text only to counter an observed, verbatim failure". Its evaluation is pass/fail behavioral testing with subagents and is self-reported. No quantitative benchmark was found.

### Cited Findings
- Repo: https://github.com/obra/superpowers — 313,358 stars, last push 2026-11-03; description "An agentic skills framework & software development methodology that works." Type: skills (SKILL.md). Tag: METHODOLOGY. — [repo](https://github.com/obra/superpowers)
- Verified file list under `skills/writing-skills/`: `SKILL.md`, `render-graphs.js`, `references/{CLAUDE_MD_TESTING.md, anthropic-best-practices.md, bulletproofing.md, discovery.md, flowcharts.md, graphviz-conventions.dot, persuasion-principles.md, testing-skills-with-subagents.md}`. Related tests: `tests/systematic-debugging/pressure-scenarios/{CREATION-LOG.md, test-academic.md, test-pressure-1.md, test-pressure-2.md, test-pressure-3.md}`. — [writing-skills dir](https://github.com/obra/superpowers/tree/main/skills/writing-skills)
- SKILL.md headings (via WebFetch summary, then cross-checked against the references): "TDD Mapping for Skills", "The Iron Law (Same as TDD)", "Common Rationalizations for Skipping Testing", "Match the Form to the Failure", "Bulletproofing Against Rationalization", "RED-GREEN-REFACTOR for Skills", "Anti-Patterns", "Skill Creation Checklist (TDD Adapted)". The Iron Law wording "NO SKILL WITHOUT A FAILING TEST FIRST" and "Writing skills IS Test-Driven Development applied to process documentation" came only via the WebFetch summary and were not confirmed in the raw file. — [SKILL.md](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md)
- C1 yes. `references/testing-skills-with-subagents.md`, section "TDD Mapping for Skill Testing" maps the TDD terms: "Verify RED: Capture rationalizations", "REFACTOR: Plug holes". Overview states the loop: run scenarios without the skill (RED), write the skill against those failures (GREEN), close loopholes (REFACTOR). — [testing-skills-with-subagents.md](https://github.com/obra/superpowers/blob/main/skills/writing-skills/references/testing-skills-with-subagents.md)
- C2 partial-to-yes (behavioral, not quantitative). Section "Pressure Types" / "Great scenario": "Best tests combine 3+ pressures." Section "When Skill is Bulletproof" lists the pass condition ("Agent chooses correct option under maximum pressure"; stop when no new rationalizations appear). Scenario examples use forced A/B/C choices. `references/CLAUDE_MD_TESTING.md` applies the same method to CLAUDE.md variants ("Testing different documentation variants to find what actually makes agents discover and use skills under pressure"), with 4 scenarios (time pressure, sunk cost, authority, familiarity). — [CLAUDE_MD_TESTING.md](https://github.com/obra/superpowers/blob/main/skills/writing-skills/references/CLAUDE_MD_TESTING.md)
- C3 partial-to-yes. Section "REFACTOR Phase: Close Loopholes": "Document every excuse." Each excuse gets (1) "Explicit Negation in Rules", (2) "Entry in Rationalization Table", (3) "Red Flag Entry", (4) "Update description". Section "Meta-Testing (When GREEN Isn't Working)" is a debugging procedure for when rules fail. Iteration example: "New rationalization: 'Spirit not letter'" leads to adding a foundational principle. Bloat control comes from baseline-first (text exists only to fix a captured failure) and size targets in `references/discovery.md`, section "Token Efficiency (Critical)": "Frequently-loaded skills: <200 words total", "Other skills: <500 words". The same file has "Skill Discovery Optimization (SDO)" with the rule that a description must contain triggering conditions only, not a workflow summary. — [discovery.md](https://github.com/obra/superpowers/blob/main/skills/writing-skills/references/discovery.md)
- Eval backing: self-reported behavioral pressure tests (`tests/systematic-debugging/pressure-scenarios/CREATION-LOG.md` was not read in detail). The only quantitative figure is a borrowed external study in `references/persuasion-principles.md`: "Meincke et al. (2025) tested 7 persuasion principles with N=28,000 AI conversations", compliance "33% → 72%". That study measures compliance with objectionable requests, not skill quality, so it is a borrowed rationale for emphatic wording. — [persuasion-principles.md](https://github.com/obra/superpowers/blob/main/skills/writing-skills/references/persuasion-principles.md)

### Inferences
- The method turns "how to write" into "how to test": no sentence is added until a baseline agent fails without it. This is the strongest answer to rule bloat among the candidates, but it targets discipline-type rules (agent rationalizes skipping a rule). It is weaker for reference or factual content.
- Nuance loss is handled indirectly (verbatim capture of rationalizations, "spirit vs letter" principle). There is no step that checks a derived rule against the original abstract principle.
- There is no removal test: the method says nothing about deleting a rule that later proves non-discriminating (compare Candidate 2).

### Gaps
- `bulletproofing.md` and `CREATION-LOG.md` content were not read in full; I did not verify the exact wording of the Iron Law in the raw SKILL.md.
- No third-party measurement of whether skills written this way outperform others.

## Candidate 2: vltansky/agents-md-evals (strongest for C2, and C3 as rule pruning)

### Takeaway
Community skill that A/B-tests each rule of an AGENTS.md/CLAUDE.md with and without the file, then cuts rules that do not change behavior. It is the clearest quantitative evaluation procedure for instruction files, but it covers pruning only and does not generate rules from principles.

### Cited Findings
- URL: https://github.com/vltansky/agents-md-evals — 4 stars, pushed 2026-03-09. Type: AGENTS.md / CLAUDE.md. Tag: METHODOLOGY (evaluation/pruning). "Built on Anthropic's skill-creator eval framework." — [README](https://github.com/vltansky/agents-md-evals)
- C1 partial (method for auditing, not for authoring). SKILL.md heading "The Evaluation Loop" with Steps 1-6: "Read and Categorize Rules", "Generate Eval Prompts", "Run Clean A/B Tests", "Grade and Benchmark", "Analyze and Recommend", "Launch the Viewer". — [SKILL.md](https://github.com/vltansky/agents-md-evals/blob/main/SKILL.md)
- C2 yes. README: "Discover which rules actually change model behavior vs. waste context tokens." Evals are derived from the repo's git commit history ("Commit-Derived Evals (Preferred)"). Contaminated baselines are handled by "Clean Baseline Protocol" (the file must be physically absent because Claude Code auto-loads CLAUDE.md into subagents). Key metrics are aggregated via `scripts/aggregate_benchmark.py`; graders are `agents/grader.md` and `agents/analyzer.md`. — [README](https://github.com/vltansky/agents-md-evals)
- C3 partial-to-yes (pruning side). SKILL.md "The Keep Test": every surviving rule must pass at least one of Specificity ("project-unique decision"), Behavior change, Surprise ("surprise a competent dev joining the project"), Pain ("real mistake or recurring PR feedback"), Frequency, "No feedback loop" ("Can't be enforced by tests, types, linters, or CI"). "If it fails all six AND is non-discriminating in A/B tests, it's dead weight." Also: "Prefer feedback loops over prose". `references/eval-categories.md` classifies rule kinds into high-value targets (coupling/parity rules, workflow rules, decision style), low-value (modern coding patterns, tech-stack choices the model infers from code), and untestable-keep (safety guardrails, identity preferences). — [eval-categories.md](https://github.com/vltansky/agents-md-evals/blob/main/references/eval-categories.md)
- Eval backing: self-reported. README: "25 of 26 assertions passed identically with and without a 755-line instruction file", and "Realistic improvement deltas are +3-10% for well-structured projects." Single author, one project; no replication seen.

### Inferences
- Gives the deletion half of "preventing unnecessary rules from creeping in". Pairs naturally with Candidate 1 (which gives the addition half).
- The 25/26 result is a one-file anecdote, not a general measurement.

### Gaps
- No method for writing the rule text itself or for preserving nuance when abstracting.

## Candidate 3: NieZhuZhu/ai-harness-doctor (strongest for C2 at the repo-harness level)

### Takeaway
A CLI/skill that audits, consolidates and measures agent instruction files (AGENTS.md, CLAUDE.md, .cursorrules, copilot-instructions) with a published before/after benchmark. It evaluates consistency and staleness rather than the wording quality of individual rules.

### Cited Findings
- URL: https://github.com/NieZhuZhu/ai-harness-doctor — 3 stars, pushed 2026-10-14. Types: AGENTS.md, CLAUDE.md, Cursor rules, Copilot files. Tag: METHODOLOGY + tooling. — [README](https://github.com/NieZhuZhu/ai-harness-doctor)
- C1 partial. README "The four phases": "0 — Checkup", "1 — Treat", "2 — Follow-up", "3 — Efficacy"; plus a maturity ladder "Ungoverned → Inventoried → Canonicalized → Guarded → Evidenced". Principle: one human-owned canonical `AGENTS.md` with tool-specific files as pointers.
- C2 yes. README table "What it checks" includes "Instruction quality: Oversized context, wholesale README copying, silent conflict adjudication, overlaps, and same-scope conflicts" and "Efficacy: Before/after task correctness, stability, latency, cost". Benchmark (`benchmark/README.md`): 14 objective tasks x 2 runs per side, regex-graded from `claude -p --output-format json`, dated 2026-07-07, model `claude-fable-5`. — [benchmark/README.md](https://github.com/NieZhuZhu/ai-harness-doctor/blob/main/benchmark/README.md)
- C3 partial. "Scripts perform deterministic mechanics. They never silently choose npm over pnpm"; each semantic conflict is a human decision point ("Adjudicate every semantic conflict"). This prevents silent nuance loss during consolidation, but there is no abstract-to-concrete derivation.
- Eval backing: self-reported with published raw results. README: "6/28 to 28/28 correct", latency "-27%", cost "-17%"; real repo trycompai/comp "18/24 to 24/24"; a published null result on openai/codex ("healthy docs left nothing for treatment to improve"). The benchmark is built so that the "before" repo has stale/conflicting files, so the result measures the removal of contradictions, not general writing quality. Its own text says the second run is "to expose answer instability rather than to claim statistical confidence."

### Inferences
- Useful evidence that contradictory or stale instructions cause measurable wrong answers; limited evidence about how to word individual rules.

### Gaps
- Single author; the benchmark corpus is demo repos built by the tool's author.

## Candidate 4: github/awesome-copilot, instructions/instructions.instructions.md (meta-rule file)

### Takeaway
A meta-instruction file that governs how to write other `.instructions.md` files, with an explicit rule-addition policy ("add constraints after observed failures"). No evaluation procedure.

### Cited Findings
- URL: https://github.com/github/awesome-copilot/blob/main/instructions/instructions.instructions.md — repo 40,871 stars, pushed 2026-11-06. Type: GitHub Copilot custom instructions. Tag: methodology (light) inside a template collection. Sibling meta files exist: `instructions/prompt.instructions.md`, `instructions/agents.instructions.md`. — [file](https://github.com/github/awesome-copilot/blob/main/instructions/instructions.instructions.md)
- C1 partial. Heading "Custom Instructions File Guidelines" with "File Structure", "Content Guidelines", "Writing Style".
- C2 no. The only check is an "Optional but Recommended" section "Validation and Verification" listing commands to include in the instructions; no measure of rule effectiveness.
- C3 partial. Heading "Instruction Altitude (Goldilocks Zone)": "Add constraints after observed failures, not hypothetical edge cases" and "Start with the minimum rule set that fully defines expected outcomes". A table gives Over-specified: "Brittle if-else prose"; Under-specified: "Assumes shared context".
- Eval backing: none.

### Inferences
- The rule "constraints only after observed failures" matches Candidate 1's baseline-first idea, in one sentence and without a test procedure.

### Gaps
- I did not check whether the awesome-copilot repo's eval/validation workflows apply to instruction quality.

## Candidate 5: humanlayer, "Writing a good CLAUDE.md" (blog, referenced from GitHub awesome list)

### Takeaway
Widely cited practitioner essay with a reasoned writing method (instruction budget, universal relevance, progressive disclosure, no style rules in prose). No eval of its own; relies on an arXiv paper and a logging-proxy observation.

### Cited Findings
- URL: https://www.humanlayer.dev/blog/writing-a-good-claude-md (published 2025-11-25 per WebFetch summary), listed in hesreallyhim/awesome-claude-code (57,378 stars, pushed 2026-11-06) as "instruction-budget reasoning, progressive disclosure, and the test of whether Claude would err without a given line". Type: CLAUDE.md/AGENTS.md. Tag: methodology (essay). Not a GitHub repo artifact. — [blog](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- C1 yes: structure WHY/WHAT/HOW; keep under about 300 lines (author says consensus, humanlayer's own file is under 60 lines); "file:line" pointers over snippets; separate task-specific files.
- C2 no: no quality metric. It cites arXiv 2507.11538 (frontier models follow roughly 150-200 instructions consistently) as rationale.
- C3 partial: advises against auto-generating with `/init`; style rules go to linters/hooks instead of prose; only universally applicable instructions belong in the file. Source for the claim that Claude Code wraps CLAUDE.md in a "may or may not be relevant" reminder is the author's own proxy observation.
- Eval backing: none (cited paper only). Page itself offers no independent testing.

### Inferences
- Supplies the principle for deletion criteria (non-universal instructions get ignored) that Candidate 2 operationalizes with A/B tests.

### Gaps
- The system-prompt instruction count (about 50) is the author's estimate, unverified.

## Candidate 6: eyaltoledano/claude-task-master, `.cursor/rules/self_improve.mdc` and `cursor_rules.mdc` (meta-rule files)

### Takeaway
The best-known "rules for writing rules" files in the Cursor ecosystem. They give triggers for adding/updating rules and a short quality checklist, with no measurement.

### Cited Findings
- URLs: https://github.com/eyaltoledano/claude-task-master/blob/main/.cursor/rules/self_improve.mdc and `.../cursor_rules.mdc` (both fetched via WebFetch; summarizer-based paraphrase, quotes are as returned). Type: Cursor rules. Tag: methodology (light) / template. Code search for `filename:cursor_rules.mdc` shows the file was copied into many repos (e.g. SiriusScan/Sirius, devfullcycle/imersao22), so it functions as a de facto template.
- C1 partial: `cursor_rules.mdc` — "Include specific, actionable requirements", "Keep rules DRY by referencing other rules", "Include both DO and DON'T examples".
- C2 partial (checklist, not measurement): `self_improve.mdc` section "Rule Quality Checks": "Rules should be actionable and specific".
- C3 partial: section "Add New Rules When": "A new technology/pattern is used in 3+ files", "Code reviews repeatedly mention the same feedback". Maintenance: "Remove outdated patterns."
- Eval backing: none.

### Inferences
- A frequency-based trigger (3+ files, repeated review feedback) is a cheap bloat guard similar to the "Pain" and "Frequency" tests in Candidate 2.

### Gaps
- The raw files were not read directly; wording is from the WebFetch summary.

## Candidate 7: rohitg00/pro-workflow ("lessons learned to rules")

### Takeaway
Tool that turns user corrections into stored rules loaded at session start. A rule-capture mechanism with human approval; no quality evaluation seen.

### Cited Findings
- URL: https://github.com/rohitg00/pro-workflow — 2,945 stars, pushed 2026-09-29. Type: Claude Code memory/rules. Tag: tool/tips with a capture procedure. — [README](https://github.com/rohitg00/pro-workflow)
- C1 partial: README flow "Claude → Proposes rule → You approve → Saved to SQLite"; `/learn-rule` captures a correction as a rule.
- C2 no: README claim "Correction rate near zero" at session 50 is marketing-level and unmeasured as far as I saw.
- C3 no: no pruning or abstraction procedure found in the README.
- Eval backing: none (self-claim).

### Inferences
- Example of the failure mode the objective warns about (rules accumulate from each correction with no removal test).

### Gaps
- I read only grep matches from the README, not the skills' source.

## Candidate 8: felixgeelhaar/cclint (CLAUDE.md linter)

### Takeaway
Static linter for CLAUDE.md/skills/subagents/hooks; checks structure and some wording smells. It is a tool of mechanical criteria, not a methodology.

### Cited Findings
- URL: https://github.com/felixgeelhaar/cclint — 12 stars, pushed 2026-09-28. Type: CLAUDE.md, skills, subagents, hooks. Tag: tooling. — [README](https://github.com/felixgeelhaar/cclint)
- C1 no. C2 partial: README "What it catches": "Vague instructions" ("follow best practices") "that degrade model adherence"; "Duplicate content across parent / sibling CLAUDE.md files"; unresolved `@path` imports. C3 no.
- Eval backing: none for the claim that vagueness degrades adherence.

### Gaps
- No evidence linking lint rules to measured behavior.

## Candidate 9: jrenaldi79/harness-engineering

### Takeaway
Field guide and readiness scorer for repos used by coding agents; scoring framework, not writing methodology.

### Cited Findings
- URL: https://github.com/jrenaldi79/harness-engineering — 126 stars, pushed 2026-11-02. Type: CLAUDE.md templates, harness. Tag: template collection + assessment. — [README](https://github.com/jrenaldi79/harness-engineering)
- C1 partial (field guide of "20+ best practices"). C2 partial: README "Readiness Analysis" scores "8 pillars and 37 criteria" with maturity levels 1-5 (structure of the repo, not wording quality of rules; the SKILL.md is "agent-guided, not script-based"). C3 no.
- Eval backing: none seen.

### Gaps
- Not verified what the 37 criteria are.

## Candidate 10: josix/awesome-claude-md (curated list with quality criteria)

### Takeaway
Curated analyses of public CLAUDE.md files, with a stated quality rubric for inclusion. Mostly an examples collection.

### Cited Findings
- URL: https://github.com/josix/awesome-claude-md — 628 stars, pushed 2026-10-23. Type: CLAUDE.md. Tag: tips/template collection. README has "Quality Standards" with "Primary Criteria (70% weight)" and "Secondary Criteria (30% weight)" (criteria content not read). — [README](https://github.com/josix/awesome-claude-md)
- C1 partial; C2 partial (a selection rubric for examples); C3 no. Eval backing: none.

### Gaps
- Criteria details and their grounding were not read.

## Candidate 11: Template/awesome collections (tag: TIPS / TEMPLATES, no methodology found)

### Takeaway
The large awesome lists are template or link collections. The only methodology-like content in them is links out to other sources.

### Cited Findings
- PatrickJS/awesome-cursorrules — 41,114 stars, pushed 2026-05-30. README has rule-file links (`rules/*.mdc`) and a generic motivation text ("Consistency is the other big win"); no method for writing or evaluating rules found in the README. Tag: TEMPLATE COLLECTION. — [repo](https://github.com/PatrickJS/awesome-cursorrules)
- hesreallyhim/awesome-claude-code — 57,378 stars, pushed 2026-11-06. Link list; entries relevant here: HumanLayer essay (Candidate 5), multica-ai/andrej-karpathy-skills ("A drop-in CLAUDE.md distilling four behavioral guidelines"), and Piebald-AI/claude-code-system-prompts (Claude Code's own prompts, including a CLAUDE.md-related utility prompt). Tag: LINK COLLECTION. — [repo](https://github.com/hesreallyhim/awesome-claude-code)
- agentsmd/agents.md — 25,359 stars, pushed 2026-09-10. Format spec/site; I did not read it for writing guidance. — [repo](https://github.com/agentsmd/agents.md)
- humanlayer/12-factor-agents, Factor 2 "Own your prompts" — 27,004 stars, last push 2025-09-21. "Don't outsource your prompt engineering to a framework."; it adds "treat them as first-class code". A principle, with no procedure or evaluation. Tag: principle. — [factor-02](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-02-own-your-prompts.md)
- Eval backing for all of the above: none.

### Gaps
- Did not examine cline/cline Memory Bank docs, coleam00/context-engineering-intro (13,902 stars) or gsd-build/get-shit-done (64,155 stars) for methodology content; they appeared in search but I did not open them.

## Issues/Discussions (anthropics/claude-code, openai/codex, agentsmd/agents.md)

### Takeaway
GitHub issues I found are mostly feature requests or bug reports about instructions being ignored, not discussions of writing/measuring methodology. I found no issue thread that proposes an evaluation method for CLAUDE.md quality.

### Cited Findings
- anthropics/claude-code#6235 "Feature Request: Support AGENTS.md" (6,690 reactions, created 2025-08-21) and #31005 (600 reactions) show demand for AGENTS.md interoperability; not about how to write. — [#6235](https://github.com/anthropics/claude-code/issues/6235), [#31005](https://github.com/anthropics/claude-code/issues/31005)
- anthropics/claude-code#77136 (578 reactions, created 2026-07-13, open): style instructions ignored by recent models ("despite explicit style instructions" in the title). Bug report with user anecdotes from a Reddit thread; no measurement. — [#77136](https://github.com/anthropics/claude-code/issues/77136)
- anthropics/claude-code#65961 (255 reactions, 2026-06-07): "ignores instructions to stop" verbose code comments. Anecdotal. — [#65961](https://github.com/anthropics/claude-code/issues/65961)

### Gaps
- I did not search openai/codex or agentsmd/agents.md issues/discussions, or discussions on emphasis words (IMPORTANT/MUST); my one search for that returned only irrelevant hits.
- GitHub Discussions were not searched (the `gh` search API used covers issues/PRs only).

## Summary: strongest candidates

- Strongest for C3 (rule derivation and bloat): obra/superpowers writing-skills. Method: capture baseline failures verbatim without the skill, write the minimum text addressing them, re-test under combined pressure, and add explicit negations, rationalization-table entries and red flags for each newly observed excuse. Evaluation is pass/fail behavior under 3+ combined pressures, self-reported. Bloat is limited by "text only to fix an observed failure" plus word budgets; nuance loss is handled by verbatim capture and a "spirit vs letter" principle, but there is no check of derived rules against the source principle, and no deletion step.
- Strongest for C2: vltansky/agents-md-evals. Method: split the rules, generate prompts from git history, run clean with/without-file A/B tests, grade by assertions, and cut rules that are non-discriminating and fail the six-part Keep Test. Evaluation is self-reported (25 of 26 assertions identical on a 755-line file; +3-10% deltas). Handles bloat directly by deletion; does not address authoring or nuance loss.
- Strongest benchmark-style evidence on instruction files: NieZhuZhu/ai-harness-doctor (published raw results, 6/28 to 28/28), but it measures consistency/staleness repair, with demo repos made by the tool's author.
- Combination note: Candidate 1 (addition gated by observed failure) plus Candidate 2 (removal gated by A/B non-discrimination) together cover addition and removal. No single GitHub artifact found does both, and none provides an explicit abstract-principle-to-sentence derivation with a nuance-preservation check.
- No third-party measurement of any writing methodology was found in this sweep.
