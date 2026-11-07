# Documented procedures for deriving concrete behavioral rules from abstract principles (AI instruction authoring)

Scope note: fetched ~24 pages (as of 2026-11-06). Not fetched or not verified: BMAD, Tessl, Windsurf memories, Devin knowledge, Collective Constitutional AI, OpenAI "approach to the Model Spec" blog (403), Deliberative Alignment full paper (blog 403; abstract only), Alignment as Jurisprudence full text (PDF unreadable; abstract only), last ~23k chars of Model Spec 2026-10-29, last ~95k chars of Anthropic constitution. These are Gaps, not negatives.

Headline finding: no source found gives a full "abstract principle -> criteria -> concrete sentence" procedure for authoring memory-type files. The closest pieces are scattered: (1) Anthropic's "a rule must be derivable from / explicable by the principles" test, (2) the ICAI algorithm (the only fully specified, measured procedure, but it runs concrete -> principle, the reverse direction), (3) spec-kit's principle -> yes/no gate conversion, (4) EARS templates with an underlying ruleset, (5) Claude Code / Cursor operational criteria for when a lesson becomes a rule and how to prune.

## Key Question 1: OpenAI Model Spec and deliberative alignment (structure, examples, conflict resolution, derivation)

### Takeaway
The Model Spec uses a layered structure (values -> authority-ranked instructions -> defaults/guidelines) and pins meaning with paired Compliant/Violation examples. It states a conflict rule (higher authority wins). The fetched page does not document how rules were derived from the values; deliberative alignment only says the model is trained to reason over spec text.

### Cited Findings
- Candidate 1 record. URL: https://model-spec.openai.com/2026-10-29.html (root URL redirects here; verified by fetch). Artifact type: spec. C1 (how to write): partial — "intentionally leaves many details of style, personality, and interaction unspecified" (Overview; summarizer paraphrase of page, quote not verbatim-verified); C2 (evaluation criteria): no; C3 (abstract->concrete procedure): partial via examples only; the page states little explicit drafting guidance. Eval backing: none on the page (spec text itself); the repo page mentions no evals. Layer mapping: methodology = absent; criteria = absent; rules = five value headings (Be faithful to human intent, Minimize harm, Be honest and transparent, Facilitate human agency, Act with care) with subsections, plus authority levels Root/System/Developer/User/Guideline.
- Authority levels: Root rules come only from the Model Spec; user-level items are defaults; Guidelines are weak biases that context can override implicitly. Higher-authority instructions take precedence and lower-level content cannot reinterpret higher-level rules — [Model Spec](https://model-spec.openai.com/2026-10-29.html)
- Examples pair a "Compliant" and a "Violation" response with short annotations that show edge cases — [Model Spec](https://model-spec.openai.com/2026-10-29.html)
- Spec says it prefers placing "as many instructions as possible" at Guideline level to avoid paternalism (a bloat/over-constraint control, per summarizer) — [Model Spec](https://model-spec.openai.com/2026-10-29.html)
- Spec "will be continuously updated based on feedback and lessons from serving users" and production models "do not yet fully reflect" it — [Model Spec](https://model-spec.openai.com/2026-10-29.html)
- Candidate 2 record. URL: https://github.com/openai/model_spec. Artifact type: spec (source repo). C1: no; C2: no; C3: no. Contents: model_spec.md, CHANGELOG.md, archived HTML releases from 2025-02-12; page mentions no evals. Eval backing: none stated. Mapping: maintenance/versioning only (not a layer in the requester's scheme).
- Candidate 3 record. URL: https://arxiv.org/abs/2412.16339 (Deliberative Alignment; abstract only). Artifact type: spec used as training input. C1: no; C2: no; C3: no. Method: train the model to "explicitly recall and accurately reason over the specifications" without human-written CoTs; reported gains in jailbreak robustness, less overrefusal, better OOD generalization. Eval backing: self-reported (OpenAI o-series). Mapping: consumption of rules, not their derivation.

### Inferences
- Model Spec's contribution to the requester's problem is the example-pair device (rule + Compliant + Violation) as the nuance-preservation mechanism; its authority-level ordering is the conflict-resolution mechanism. The derivation layer (values -> rules) is not documented in what I could read.

### Gaps
- OpenAI's "Inside our approach to the Model Spec" blog returned 403; the part of the Model Spec after char 100000 and the full Deliberative Alignment paper (spec-writing guidance, how spec-grounded training data is made) were not read.

## Key Question 2: Anthropic constitution, Constitutional AI, Inverse CAI, specific vs general principles

### Takeaway
Anthropic's constitution gives the clearest stated meta-rule: prefer judgment, explain every rule, and require any specific guideline to be "explicable" by the constitution (conflict -> revise the constitution). ICAI is the only fully specified, measured algorithm, but it goes concrete -> principle.

### Cited Findings
- Candidate 4 record. URL: https://www.anthropic.com/constitution. Artifact type: constitution. C1 (how to write): yes — "we try to explain any rules we do want Claude to follow." (heading "Why Anthropic explains its reasoning"/overview sections as summarized); C2 (criteria): partial — rules fit when "the costs of errors are severe enough that predictability and evaluability become critical"; C3 (procedure preventing nuance loss/bloat): partial — wants understanding so "it could construct any rules we might come up with itself", and guidelines "should be explicable with reference to the principles". Eval backing: none for the writing method (not measured). Mapping: methodology = favor judgment, explain rules; criteria = when rules are warranted (cost of error, predictability, manipulation risk); rules = hard constraints and guidelines that must be derivable from the document. Page truncated: sections after char 100000 unread.
- Rules vs judgment trade-off: rules give "up-front transparency and predictability" but "fail to anticipate every situation"; judgment adapts at some cost to predictability/evaluability — [Anthropic constitution](https://www.anthropic.com/constitution)
- Narrow rules can generalize badly: example "Always recommend professional help when discussing emotional topics" may generalize into a self-image of caring more about covering oneself — [Anthropic constitution](https://www.anthropic.com/constitution)
- Conflict handling: guidelines rank above general helpfulness but below safety/ethics; a conflicting guideline "suggests" a drafting mistake, and the constitution is revised instead of keeping inconsistent guidance — [Anthropic constitution](https://www.anthropic.com/constitution)
- Candidate 5 record. URL: https://arxiv.org/abs/2406.06560 (HTML v2 https://arxiv.org/html/2406.06560v2 fetched). Artifact type: constitution (set of principles) extracted from preference data. C1: yes (explicit algorithm); C2: yes (agreement metric); C3: partial (testing + filtering remove principles that do not reconstruct labels or apply to <10% of items). Eval backing: self-reported with held-out split only for AlpacaEval (65/65); e.g. 61% vs 34% agreement on unaligned 648-pair set; ablation: removing testing and filtering gave the largest drop. Mapping: methodology = 5-step pipeline; criteria = reconstruction agreement, correct-minus-incorrect ranking, relevance threshold; rules = resulting short constitution. Direction is concrete -> abstract (reverse of the requester's step); paper notes non-uniqueness (many constitutions fit equally), lossy compression, no causal claim, personal/group constitutions transferred poorly.
- ICAI steps: LLM proposes principles from each labeled pair; embed and k-means cluster; sample one per cluster; LLM labels each principle per pair as first/second/not relevant; keep principles that improve reconstruction, drop those relevant to <10% of items, rank by correct minus incorrect, keep top n — [ICAI v2](https://arxiv.org/html/2406.06560v2)
- Candidate 6 record. URL: https://arxiv.org/abs/2310.13798 (Specific versus General Principles for CAI; fetched via search snippet only, not page text — weak verification). Artifact type: constitution. C1: partial; C2: yes (trait-targeted evaluations); C3: no. Reported: a single "do what's best for humanity" principle generalizes in the largest models but detailed principles give finer control over specific harms. Eval backing: self-reported (Anthropic). Mapping: supplies the criterion for choosing abstraction level (breadth vs fine-grained control). Source: [search result](https://arxiv.org/abs/2310.13798v1); a critique, [Alignment as Jurisprudence](https://arxiv.org/abs/2605.08416), says gains in generality may cost transparency/predictability (abstract-level; full text unread).
- Constitutional AI (https://arxiv.org/abs/2212.08073): constitution is "a list of rules or principles", the only human oversight; principles drive critique/revision and AI preference labels (abstract only; does not say how principles were written).

### Inferences
- The "could the reader construct this rule itself from the stated principles" test (Anthropic) is a usable evaluation criterion for layer 2 and a nuance-loss guard. ICAI's testing/filtering is a measurable analogue: a rule survives only if it explains observed cases and is relevant to enough of them. Neither is applied to memory-file authoring in the sources.

### Gaps
- Collective Constitutional AI not fetched. Anthropic constitution text after char 100000 unread. "Specific vs General" paper body and Jurisprudence paper body not read.

## Key Question 3: Spec-driven development tools (spec-kit, Kiro/EARS, BMAD, Tessl)

### Takeaway
spec-kit and Kiro supply concrete mechanics for turning principles/requirements into checkable statements (MUST wording, gates as yes/no questions, EARS sentence templates). Neither documents how to derive the principle itself, and neither documents deleting rules.

### Cited Findings
- Candidate 7 record. URL: https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/constitution.md and https://raw.githubusercontent.com/github/spec-kit/main/templates/constitution-template.md. Artifact type: constitution (rule file). C1: yes (6-step command outline); C2: yes — principles must be "declarative, testable, and free of vague language" (Outline, step 5); C3: partial — rationale "where it is not obvious" (step 3), SHOULD->MUST replacement, versioning MAJOR/MINOR/PATCH, TODO placeholders for unknown fields rather than guessing. Eval backing: none. Mapping: methodology = command outline (load current -> collect values -> draft -> sync report); criteria = step 5 validation (testable, no vague words, version matches report); rules = principles with name + non-negotiable rules + rationale. Template has no separate rationale field; reasons go in the description.
- spec-kit "Phase -1 gates": Simplicity (<=3 projects), Anti-Abstraction, Integration-First gates are yes/no checkboxes in the plan template; the LLM may not proceed unless each gate passes or an exception is documented under "Complexity Tracking"; described as "compile-time checks for architectural principles" — [spec-driven.md](https://raw.githubusercontent.com/github/spec-kit/main/spec-driven.md). Templates also force `[NEEDS CLARIFICATION: ...]` markers instead of guessing and bar "might need" features (anti-bloat).
- Candidate 8 record. URL: https://kiro.dev/docs/specs/feature-specs/ (https://kiro.dev/docs/specs/concepts/ returned 404 at /specs/concepts/; /specs/ fetched). Artifact type: requirement. C1: yes — pattern `WHEN [condition/event] THE SYSTEM SHALL [expected behavior]`; C2: partial — each EARS requirement "can be directly translated into test cases"; "Analyze Requirements" checks inconsistencies, ambiguities, conflicts, gaps before design; C3: partial — Requirements -> Design -> Tasks flow (or Design-first). Eval backing: none. Mapping: methodology = EARS template; criteria = test-case translatability + analyze step; rules = individual SHALL statements.
- Candidate 9 record. URL: https://en.wikipedia.org/wiki/Easy_Approach_to_Requirements_Syntax (secondary; via search results, page not fetched directly). Artifact type: requirement. C1: yes — five sentence patterns, general form "WHILE <precondition>, WHEN <trigger>, the <system> SHALL <response>"; C2: partial; C3: no. Origin: Mavin et al., Rolls-Royce, RE'09. Caveat from one blog: a grammatical EARS sentence can still specify the wrong behavior. Eval backing: published in RE conference papers (not independently verified here). Mapping: rules-layer sentence grammar only (the requester's "concrete sentence" form). Direct human-side link to AI tooling (Kiro) is documented.
- Kiro steering files and BMAD/Tessl: not found/fetched.

### Inferences
- spec-kit's gate conversion (principle -> yes/no question answered before proceeding) and EARS (fixed sentence grammar with trigger/response) are the two documented ways to make the rules layer checkable; neither addresses nuance loss beyond "add rationale".

### Gaps
- BMAD, Tessl, Kiro steering docs, and any documented deletion/minimality criteria for spec-kit/Kiro not found.

## Key Question 4: Failure -> rule pipelines (memory features and rule files)

### Takeaway
Vendors document operational criteria for when to add a rule (repeat failure) and how to keep rule files lean/consistent, but not a procedure for generalizing a failure into a rule without overfitting.

### Cited Findings
- Candidate 10 record. URL: https://code.claude.com/docs/en/memory. Artifact type: memory / rule file (CLAUDE.md, auto memory). C1: yes — instructions "concrete enough to verify", e.g. "Use 2-space indentation" instead of "Format code properly"; C2: yes — add when "Claude makes the same mistake a second time", code review catches a codebase fact, same correction typed again, or a new teammate would need it; keep facts held every session, move multi-step procedures to skills; C3: partial — size under 200 lines, remove "outdated or conflicting instructions", `/doctor prompt-audit` flags instructions for older models, missing files/commands, contradictions; auto-memory index kept to one line per entry and stale entries merged or dropped. Eval backing: none stated. Mapping: methodology = when-to-add triggers (failure-driven); criteria = verifiability, size, consistency; rules = concrete one-line instructions; also states CLAUDE.md is context, not enforcement; use hooks to block actions.
- Conflict handling: contradicting instructions may be chosen "arbitrarily"; user vs project rules conflict resolution is not defined ("keep the two consistent") — [Claude Code memory docs](https://code.claude.com/docs/en/memory)
- Candidate 11 record. URL: https://cursor.com/docs/context/rules. Artifact type: rule file. C1: yes — rules should be "focused, actionable, and scoped", under 500 lines; C2: partial — add a rule only when the agent "repeatedly" makes the same mistake; C3: partial — exclude rare edge cases, full style guides (use a linter), duplicated code; reference files rather than copy to avoid staleness; `/create-rule` generates a rule file from a description. Eval backing: none. Mapping: methodology = start simple, add on repeat failure; criteria = scoped/concrete/short; rules = rule files with frontmatter application modes.

### Inferences
- Both vendors converge on the same two-part criterion: a repeat (not single) failure triggers a rule, and a rule is only kept if concrete/verifiable and consistent. This is a partial match for the requester's type (a) "reflection on a failure" memory, with the "second occurrence" gate acting as an overfitting guard.

### Gaps
- Windsurf memories, Devin knowledge, and any documented generalization-vs-overfitting guidance for lesson capture were not found or fetched.

## Key Question 5: Human-side methods cited by AI-instruction sources

### Takeaway
Only EARS is directly cited by an AI-instruction source (Kiro). Rules-vs-standards, checklists/killer items, and style-guide rationale were not found cited in the AI sources I fetched; Anthropic's constitution discusses the rules-vs-judgment trade-off in its own words without citing the legal literature on the page excerpt read.

### Cited Findings
- EARS is cited by Kiro (see Candidate 8-9).
- "Alignment as Jurisprudence" (arXiv 2605.08416) draws on Dworkin and Sunstein and argues for "the interplay of rules and cases in finetuning alignment" — [arXiv abstract](https://arxiv.org/abs/2605.08416). This is an academic bridge, not an authoring procedure.

### Gaps
- Gawande/Boorman checklist "killer items" and Google style guide rationale: no AI-instruction source citing them was found in this pass; not searched directly.

## Derivation procedures for the strongest candidates (criterion 3)

None fully satisfies criterion 3. Ranked by closeness, with what each actually provides:

### A. Anthropic constitution (derivability test)
Procedure as documented: (1) state broad considerations and the reasoning in prose; (2) permit a specific rule only if its cost-of-error / predictability / manipulation-risk justifies firmness; (3) require that each specific guideline be "explicable with reference to the principles"; (4) if a guideline conflicts with the document, treat it as a drafting error and revise the constitution. Mechanisms against nuance loss: rationale attached to rules, and the aim that the reader could rebuild the rule itself. Mechanisms against bloat: default preference for judgment over rules (a rule needs a stated justification to exist) and the conflict-triggers-revision step. Limitation: no measurement and no step-by-step conversion procedure is stated in the portion read; step (3) is a test, not a generator.

### B. ICAI (measured selection of rules against observed cases)
Procedure: generate many candidate principles from individual labeled cases; cluster to remove near-duplicates; sample one per cluster; test every candidate against every case (agrees / disagrees / irrelevant); drop candidates relevant to fewer than 10% of cases or that do not improve reconstruction; rank by correct minus incorrect and keep the top n. Nuance loss is controlled by testing against cases (principles that mis-predict are demoted); bloat is controlled by dedup clustering, the 10% relevance floor, and the top-n cap. Limits: direction is concrete -> principle; only AlpacaEval has a held-out split, filtering uses training votes, many constitutions fit equally well, and it measures agreement with labels, not rule quality for instruction files. Reusable idea for the requester: a rule candidate is retained only if it demonstrably explains the failure cases it is meant to cover and is relevant to enough of them.

### C. spec-kit (principle -> yes/no gate, with rationale and exceptions)
Procedure: draft principle as name + non-negotiable rule + rationale-if-not-obvious; validate that it is declarative, testable, and free of vague words (SHOULD -> MUST); translate it into a checkbox question in the plan template (e.g. "<=3 projects?"); require a pass or a documented exception under "Complexity Tracking"; version changes MAJOR/MINOR/PATCH and, if the bump is ambiguous, state reasoning first. Nuance loss is handled by the rationale field and the exception log (deviations are recorded, not silently dropped); bloat is handled by gates that bar speculative "might need" items. Limits: documents no procedure for deriving the principle, no deletion criteria, no measurement; the summaries I fetched were via a small model, so exact template wording should be re-verified before quoting.

### D. Claude Code memory docs + Cursor rules (failure-driven admission and pruning)
Procedure: (1) admit an entry only on a repeat failure (second occurrence, repeated correction, review finding); (2) write it concrete enough to verify; (3) put it at the narrowest scope (path-scoped rule, skill for multi-step procedures); (4) keep the file short (<200 lines Claude Code; <500 per rule Cursor); (5) periodically audit for outdated/conflicting entries (`/doctor prompt-audit`); (6) if the behavior must be guaranteed, move it out of memory into a hook. Nuance loss: not addressed (concrete examples encouraged). Bloat: size caps, repeat-failure gate, "leave out rare edge cases", scope-based loading, audit. Maps best to the requester's type (a) failure memories and the pruning part of the rules layer.

## Layer mapping summary (requester's methodology -> criteria -> rules)
- Methodology layer: Anthropic constitution (prefer explained judgment; rules only when error cost is severe), spec-kit command outline, Claude Code "when to add" triggers, ICAI pipeline.
- Evaluation-criteria layer: spec-kit step 5 (declarative, testable, no vague language), Claude Code ("concrete enough to verify", size, consistency), Anthropic ("explicable by the principles"), ICAI (reconstruction agreement, relevance >=10%), EARS/Kiro (translatable to test cases).
- Rules layer: EARS SHALL sentences, spec-kit principle bodies and gates, Model Spec Compliant/Violation example pairs, Claude Code one-line concrete instructions.
- Weak across all sources: the step linking criteria to a concrete sentence for a given source type (failure reflection vs explicit instruction vs fact). No source separates these three memory types.
