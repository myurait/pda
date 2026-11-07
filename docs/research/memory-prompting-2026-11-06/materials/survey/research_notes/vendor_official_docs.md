# Vendor official docs on HOW TO WRITE agent instruction/memory files (methodology view)

Research date: 2026-11-06. Excludes arXiv:2611.04367.

Verification note: pages were fetched with WebFetch, which runs a small model over the page. Quotes marked [raw] were checked against the saved raw page text (grep). Quotes marked [relay] come from the fetch summarizer and were not checked against raw text; treat them as paraphrase-grade. The Model Spec fetch covered only the first 100,000 of 123,029 characters (the tail fetch failed with an API error), so the tail is unread. I did not cover Cline, Windsurf, or the OpenAI prompt optimizer tool page itself (see Gaps).

## Q1. Which official sources give a methodology (not tips) for writing instruction files, scored on the 3 criteria?

### Takeaway
Only Anthropic's Skill-authoring guide and the anthropics/skills skill-creator give an actual write-evaluate-iterate loop with test cases and a baseline. Every other vendor page is tips or a template collection, with at most a "start small, add a rule when you see a mistake" heuristic. No source gives a full procedure for deriving concrete sentences from abstract principles while preventing nuance loss; the closest are partial (skill-creator, Skill best practices, context-engineering post).

### Cited Findings (fixed record per candidate)

**C1. Anthropic, "Skill authoring best practices"**
- URL: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices (fetched; the docs.claude.com URL 302-redirects here; page has no visible date)
- Type: SKILL.md (Agent Skills)
- Criterion 1 (methodology): YES. "Create evaluations BEFORE writing extensive documentation." [raw] — section "Evaluation and iteration > Build evaluations first". Five steps: identify gaps without a Skill, create three evals, baseline, write minimal instructions, iterate. Also the "Claude A / Claude B" loop: "Claude A helps you design and refine instructions" [raw] — "Develop Skills iteratively with Claude".
- Criterion 2 (evaluation): PARTIAL-YES. "Evaluations are your source of truth for measuring Skill effectiveness." [raw] — same section. Gives an eval JSON shape (query, files, expected_behavior list) and a checklist ("At least three evaluations created"; tested on Haiku, Sonnet, Opus). Admits "no built-in way to run these evaluations" [raw].
- Criterion 3 (principle to sentence, no nuance loss, no creep): PARTIAL. Anti-creep: "Challenge each piece of information" [raw] — "Concise is key" (asks "Does this paragraph justify its token cost?"). "Write minimal instructions... just enough content to address the gaps" [raw]. Nuance control by "degrees of freedom" (match specificity to task fragility: high/medium/low freedom). No procedure for decomposing a principle into sentences.
- Eval backing: none published. It prescribes evals; reports no measurement of its own advice.
- Tag: METHODOLOGY (strongest official one for authoring loop).

**C2. anthropics/skills, skill-creator SKILL.md**
- URL: https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md (fetched; [relay] only, I did not read raw text). The same skill is listed in this session as example-skills:skill-creator.
- Type: SKILL.md (meta-skill that writes SKILL.md)
- Criterion 1: YES. Full loop: test prompts saved to `evals/evals.json`; per prompt "spawn two subagents in the same turn" (with-skill vs baseline; baseline = no skill for new, snapshot of old version for improvements); grader subagent (`agents/grader.md`) writes `grading.json`; aggregate script writes `benchmark.json` (pass rate, time, tokens); `generate_review.py` viewer; user feedback in `feedback.json` drives next iteration directory. [relay]
- Criterion 2: YES. Per-assertion grading, pass-rate/time/token benchmark, with-vs-without comparison; an analyst pass flags assertions that pass regardless of the skill ("non-discriminating"). Description-triggering eval split 60% train / 40% held-out test, best chosen by test score "to avoid overfitting". [relay]
- Criterion 3: PARTIAL-STRONG. "Generalize from the feedback" and avoid "fiddly overfitty changes"; "Explain the why"; ALWAYS/NEVER in caps is "a yellow flag" to reframe with reasoning; read transcripts to find steps that waste time and remove the instructions causing them; bundle helper scripts that several runs rewrite. [relay]
- Eval backing: self-reported tooling (mechanism exists; no published results on whether the guidance improves skills).
- Tag: METHODOLOGY (strongest for criterion 2, and the best partial for 3).

**C3. Anthropic, "Effective context engineering for AI agents" (Sep 29, 2025)**
- URL: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents (fetched; [relay])
- Type: system prompt (also informs CLAUDE.md)
- Criterion 1: PARTIAL. "Right altitude": between brittle hardcoded logic and vague guidance; "specific enough to guide behavior effectively, yet flexible enough" [relay] — "The anatomy of effective context".
- Criterion 2: NO. No measurement procedure for prompt quality.
- Criterion 3: PARTIAL. "Minimal does not mean short" [relay]; start with a minimal prompt on the best model, then add instructions/examples only for observed failure modes; do not stuff edge-case rules; use a few diverse canonical examples.
- Eval backing: none.
- Tag: methodology-lite (principles plus the "add rules only on observed failure" rule).

**C4. Anthropic, "Prompting best practices" (successor of the "Claude 4 best practices" page)**
- URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices (fetched; the claude-4-best-practices URL redirects to it; lists models up to Fable 5.1 / Sonnet 5.5)
- Type: system prompt / CLAUDE.md-style instructions
- Criterion 1: PARTIAL (tips organized by topic). Why-first: "Providing context or motivation behind your instructions... can give Claude more information" [raw]; "Claude can generalize from the explanation." [raw].
- Criterion 2: PARTIAL. "Key test: Show your prompt to a colleague with minimal context" [raw]; model-specific techniques should be re-checked "against your own evals" [raw] before reuse on another model.
- Criterion 3: PARTIAL. Examples should be "Diverse" so Claude does not pick up unintended patterns; 3-5 examples; can ask Claude to evaluate examples for relevance and diversity [raw]. Remove over-prompting: soften "CRITICAL: You MUST..." language because newer models overtrigger [raw]. Explicit anti-overengineering sample prompt. Mechanism for removing stale rules: instructions written for older models cause over-application.
- Eval backing: mostly none; one claim "Queries at the end can improve response quality by up to 30 percent in tests" [raw] (long-context placement only; no method shown).
- Tag: tips (large, high quality), with an explain-why generalization principle.

**C5. Anthropic, "Writing effective tools for agents" (Sep 11, 2025)**
- URL: https://www.anthropic.com/engineering/writing-tools-for-agents (fetched; [relay])
- Type: tool descriptions (adjacent to system prompt; not a memory file — scope caveat)
- Criterion 1: YES. Prototype, build eval, run, analyze transcripts, let Claude refactor tool descriptions, repeat. 
- Criterion 2: YES. Realistic tasks with verifiable outcomes; metrics: accuracy, runtime, number of tool calls, tokens, tool errors; held-out test set against overfitting.
- Criterion 3: PARTIAL. Transcript analysis turns observed confusion into description edits (example: Claude appended "2025" to web search queries; description fix removed it).
- Eval backing: self-reported (Claude-optimized Slack/Asana tools beat human-written ones on held-out sets, charts only; SWE-bench Verified error reduction from description refinements; no exact numbers in text).
- Tag: METHODOLOGY (for tool descriptions).

**C6. Anthropic, "Create strong empirical evaluations / Define success criteria" docs**
- URL: https://platform.claude.com/docs/en/test-and-evaluate/develop-tests (fetched; first 100k of ~153k chars read; [relay])
- Type: prompts in general
- Criterion 1: PARTIAL. Success criteria first, then evals.
- Criterion 2: YES. Criteria must be "Specific", "Measurable", "Achievable", "Relevant"; eval principles: task-specific, automate grading, "volume over quality"; grading methods (exact match, LLM Likert, LLM binary); grader should be a different model from the generator.
- Criterion 3: NO.
- Eval backing: none (it is the eval-design reference itself).
- Tag: methodology for eval design (not specific to instruction files).

**C7. Claude Code docs: "How Claude remembers your project" and "Best practices for Claude Code"**
- URLs: https://code.claude.com/docs/en/memory and https://code.claude.com/docs/en/best-practices (both fetched; best-practices is where anthropic.com/engineering/claude-code-best-practices 308-redirects; memory page mentions v2.1.285)
- Type: CLAUDE.md / AGENTS.md / .claude/rules / auto memory
- Criterion 1: PARTIAL (rules of thumb). "Write instructions that are concrete enough to verify" [raw] with before/after pairs ("Use 2-space indentation" vs "Format code properly"); target under 200 lines; keep only what "Claude couldn't work out from the code itself" [raw].
- Criterion 2: PARTIAL. Diagnostic tools, not quality metrics: `/doctor prompt-audit` (finds stale, conflicting, older-model instructions), `/context all` to confirm a file loaded, `InstructionsLoaded` hook to log loads [raw]. "adding IMPORTANT probably won't fix it" [raw] — diagnosis of an ignored line: file too long, or rule belongs in a hook.
- Criterion 3: PARTIAL. Triage rule: "If something has to happen every time, make it a hook" [raw]; "If two instructions contradict each other, Claude may pick one arbitrarily" [raw]. Anti-creep: file passes only lines Claude cannot infer; `/doctor` suggests cuts.
- Eval backing: none ("Longer files... reduce adherence" asserted without data).
- Tag: tips plus a decision rule (instruction vs hook vs skill vs path-scoped rule).

**C8. OpenAI, GPT-4.1 Prompting Guide (cookbook)**
- URL: https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide (fetched; cookbook.openai.com 308-redirects; [relay])
- Type: system prompt / agent prompts
- Criterion 1: PARTIAL. Section template (Role and Objective, Instructions, Reasoning Steps, Output Format, Examples, Context) with "Add or remove sections to suit your needs."
- Criterion 2: PARTIAL. "AI engineering is inherently an empirical discipline." Recommends building evals and iterating; gives no eval procedure.
- Criterion 3: PARTIAL. First check for conflicting or underspecified instructions/examples when behavior is wrong; on conflicts the model follows the later one; "Any important behavior shown in an example should also be stated in the rules" (paraphrase, [relay]) — a nuance-preservation rule between examples and rules; avoid reliance on ALL-CAPS at first.
- Eval backing: not verified for the writing advice (the guide reports model benchmarks elsewhere; I did not check).
- Tag: tips/template collection with one consistency rule.

**C9. OpenAI, GPT-5 Prompting Guide (cookbook; page marked archived)**
- URL: https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide (fetched; no date; [relay])
- Type: system prompt
- Criterion 1: PARTIAL (tips). Treats prompts as living documents reviewed periodically.
- Criterion 2: PARTIAL. "We recommend testing your prompts in our prompt optimizer tool." Meta-prompting: ask the model which minimal phrases to add/remove for a given behavior.
- Criterion 3: PARTIAL. Contradictions cost more with GPT-5 ("expends reasoning tokens searching for a way to reconcile"); removing contradictory or poorly worded instructions improved performance for early users; Cursor softened "Be THOROUGH"-style emphasis and tool use improved; tight limits need an escape hatch.
- Eval backing: self-reported benchmark numbers (Tau-Bench Retail 73.9% to 78.2%) but those measure switching to the Responses API, not instruction wording; Cursor anecdotes are partner-reported, not measured.
- Tag: tips.

**C10. OpenAI Model Spec (version 2026-10-29, marked historical; newer version exists)**
- URL: https://model-spec.openai.com/2026-10-29.html (fetched; [relay]; tail ~23k chars unread)
- Type: model-behavior spec (analogue of a rule file; not an authoring guide)
- Criterion 1: PARTIAL. Structure: objectives and five values, red-line rules, a root-to-no-authority instruction hierarchy, overridable defaults. Describes what the spec contains, not how a third party should write one.
- Criterion 2: NO in visible text (examples illustrate intended behavior, not test procedures).
- Criterion 3: PARTIAL. Principle to concrete case via paired "Compliant" and "Violation" examples with short annotations explaining why; a candidate-instruction filter (discard if conflicting with higher level, superseded, inconsistent with source intent, beyond capability).
- Eval backing: spec says production models do not yet fully reflect it; no measurement in the text read.
- Tag: structure reference (principle, default, annotated example), not a how-to.

**C11. agents.md site + Codex AGENTS.md docs**
- URLs: https://agents.md (fetched) and https://learn.chatgpt.com/docs/agent-configuration/agents-md (fetched; developers.openai.com/codex/guides/agents-md 308-redirects here; [relay])
- Type: AGENTS.md
- Criterion 1: NO. agents.md says "AGENTS.md is just standard Markdown." and suggests sections (overview, build/test, style, testing, security).
- Criterion 2: PARTIAL (Codex only): a load-verification procedure ("Summarize the current instructions" and confirm Codex quotes your items; `--cd` to test nested overrides; session logs). agents.md states no evaluation method.
- Criterion 3: NO. Only "concise and specific"; leave formatting/lint to CI; 32 KiB combined cap (`project_doc_max_bytes`) acts as a forced anti-creep limit; closest file wins on conflict.
- Eval backing: none (agents.md cites adoption counts only).
- Tag: tips/template.

**C12. GitHub Copilot docs, repository custom instructions**
- URL: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions (fetched; [relay])
- Type: .github/copilot-instructions.md, *.instructions.md (`applyTo`)
- Criterion 1: PARTIAL (checklist of what to include: overview, build/validate steps, layout, pre-check-in checks, non-obvious dependencies, "trust" directive).
- Criterion 2: PARTIAL-YES (most operational testing guidance among IDE vendors): run every documented command; vary environment/order; make a sample change; check the response's references list for the instructions file; "temporarily disable repository instructions to compare results" (manual A/B); code review reads the PR head branch so edits can be tried before merge.
- Criterion 3: NO. Anti-creep only as limits: not task-specific, within two pages, avoid conflicts across repo/personal/org sets, do not document unrun commands.
- Eval backing: none.
- Tag: tips plus manual verification procedure.

**C13. Cursor docs, Rules**
- URL: https://cursor.com/docs/context/rules (fetched; [relay])
- Type: .cursor/rules (.mdc), AGENTS.md
- Criterion 1: PARTIAL. "Keep rules under 500 lines", "Avoid vague guidance", reference files instead of copying.
- Criterion 2: NO measurement; only "update the rule when Agent errs".
- Criterion 3: PARTIAL. "Start simple"; add rules only after repeated errors; avoid copying style guides (use a linter), commands the agent already knows, rare edge cases.
- Eval backing: none.
- Tag: tips with an error-driven growth rule.

**C14. Kiro docs, Steering**
- URL: https://kiro.dev/docs/steering/ (fetched; [relay])
- Type: Kiro steering files (product.md / tech.md / structure.md, inclusion modes)
- Criterion 1: PARTIAL. One domain per file; descriptive names.
- Criterion 2: NO ("The page doesn't describe testing steering's effect" — fetch note).
- Criterion 3: PARTIAL. "Explain why decisions were made, not just what the standards are." [relay]; before/after examples; review steering like code.
- Eval backing: none.
- Tag: tips.

**C15. Google Gemini CLI docs, GEMINI.md**
- URL: https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md (fetched; [relay])
- Type: GEMINI.md
- Criterion 1: NO (layout example, hierarchy global/workspace/JIT, `@file` imports). Criterion 2: only inspection (`/memory show` displays the concatenated context). Criterion 3: NO.
- Eval backing: none. Tag: template/reference.

### Inferences
- The two Anthropic authoring loops (C1, C2) share one shape: gap found by running the model without the instruction, minimal instruction written to close the gap, baseline vs with-instruction comparison, edit from transcripts. This is a test-first discipline for instruction files; no other vendor documents it.
- Anti-creep is handled by three different mechanisms across vendors: failure-driven addition (C3, C13), baseline-gated addition (C1, C2), and hard size caps (Claude Code 200 lines, Cursor 500, Copilot two pages, Codex 32 KiB). None defines a removal test other than C2's "remove instructions causing waste" and C7's `/doctor prompt-audit`.
- The explain-why/generalize advice appears in Anthropic (C2, C4), Kiro (C14), and is mirrored by OpenAI's warning against emphasis (C8, C9). It is asserted, not measured, by every source.

### Gaps
- Cline and Windsurf rules docs, OpenAI prompt optimizer page, and Anthropic "Demystifying evals for AI agents" were not fetched (call budget), so nothing is claimed about them.
- Model Spec tail (last ~23k chars) unread; a newer Model Spec version than 2026-10-29 exists but was not fetched.
- skill-creator and most non-Claude-Code pages were read through the fetch summarizer only; quotes marked [relay] need raw confirmation before verbatim use.
- No dated publication info for the Skill authoring guide or Claude Code docs; only the two Anthropic engineering posts (Sep 2025) carry dates.
- No vendor source found that measures whether following its own writing advice improves compliance (no A/B or third-party measurement located).

## Q2. Which 2-3 are strongest for criteria 2 (evaluation) and 3 (abstract to concrete), and how do they work?

### Takeaway
Strongest: (1) anthropics/skills skill-creator for criterion 2 and the best partial for 3; (2) Anthropic Skill authoring best practices for the evaluation-driven loop and the Claude A/B method; (3) Anthropic "Writing effective tools for agents" for criterion 2 on transcripts and held-out sets (scope: tool descriptions). For criterion 3, no source is complete; skill-creator plus C1 plus C3 jointly cover the pieces.

### Cited Findings
- skill-creator method: write test prompts first; run each with and without the skill (or old vs new version); grade assertions with a grader subagent; aggregate pass rate, time, tokens; human reviews outputs in a viewer; next iteration driven by feedback, with the instruction to generalize instead of patching to examples, to explain the why, to treat caps as a smell, and to delete instructions that waste steps; assertions that pass without the skill are flagged; held-out split used when optimizing descriptions. [relay] — [skill-creator SKILL.md](https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md)
- Skill best practices method: gap-first, three evals, baseline, "minimal instructions" to pass them, then Claude A (author) / Claude B (user) cycles: observe B's real behavior, bring specifics back to A ("it forgot to filter by date for Q4"), revise, retest; test across Haiku/Sonnet/Opus because "What works perfectly for Opus might need more detail for Haiku" [raw]. Abstract-to-concrete handled by "degrees of freedom" (fragility decides how literal the sentence is) and concrete input/output examples ("Examples are concrete, not abstract" in the checklist). — [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- Tools post method: build eval tasks with verifiable outcomes, have agents emit reasoning before tool calls, read transcripts and metrics, paste transcripts back into Claude to rewrite descriptions, check on held-out tasks. [relay] — [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- Abstract-to-concrete pieces found elsewhere: concrete-enough-to-verify rewriting pairs [raw] — [Claude Code memory](https://code.claude.com/docs/en/memory); start minimal then add per observed failure [relay] — [Context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents); examples must also be stated in rules [relay] — [GPT-4.1 guide](https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide); compliant/violation pairs with why-annotations [relay] — [Model Spec](https://model-spec.openai.com/2026-10-29.html).

### Inferences
- None of these tells a writer how to take a stated principle, split it into sentences, and check each sentence keeps the principle's nuance. The nearest operational check is the baseline-delta test (an instruction earns its place only if the with-instruction run beats the baseline) plus transcript review; nuance-loss detection is left to human review of outputs.
- The "meta" layer (a methodology for making methodologies) exists only implicitly: skill-creator is itself a skill that authors skills with an eval loop, but its principles are not stated as a general procedure.

### Gaps
- No source states a rule-derivation procedure (principle to atomic rule to test case) or a check for rule redundancy beyond contradiction audits.

## Q3. Does any eval backing exist (evals, compliance measurement, A/B tests) for the writing advice?

### Takeaway
No vendor page located reports a measurement showing that its own instruction-writing advice improves compliance. Evals are prescribed (Anthropic, OpenAI) and tooling exists (skill-creator, `/doctor prompt-audit`), but results are not published for instruction-file style.

### Cited Findings
- Anthropic Skill guide: "There is not currently a built-in way to run these evaluations" [raw] — [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- Self-reported with charts, no figures in text: Claude-optimized tools beat human-written Slack/Asana MCP tools on held-out tasks [relay] — [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- OpenAI GPT-5 guide: benchmark gain (Tau-Bench Retail 73.9% to 78.2%) attributed to API switch, not wording; Cursor anecdotes only [relay] — [GPT-5 guide](https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide)
- Claude Code docs assert length reduces adherence and emphasis causes over-application without data [raw] — [Best practices](https://code.claude.com/docs/en/best-practices)
- Copilot docs describe a manual A/B (disable instructions, compare) but no results [relay] — [Copilot docs](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions)
- Third-party measurement: none found in this scope.

### Inferences
- Claims such as "under 200 lines" or "explain why" are vendor heuristics; any user-side adoption should be validated with its own evals, which Anthropic's own prompting page also advises ("re-check it against your own evals" [raw]).

### Gaps
- Did not search academic or third-party benchmarks of AGENTS.md/CLAUDE.md compliance (outside the vendor-docs scope of this assignment).
