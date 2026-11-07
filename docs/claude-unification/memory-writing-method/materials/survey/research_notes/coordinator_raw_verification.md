# Coordinator raw-text verification (fetched raw files via raw.githubusercontent.com, main branch, 2026-11-06)

These supersede any [relay] markers on the same items in other note files: the items below are confirmed in the raw files.

## obra/superpowers — skills/writing-skills/SKILL.md (raw confirmed)

- "## The Iron Law (Same as TDD)" heading exists; text "NO SKILL WITHOUT A FAILING TEST FIRST" confirmed (line ~166). [raw]
- "## TDD Mapping for Skills": RED = agent violates rule without skill (baseline); GREEN = complies with skill present; Refactor = close loopholes while maintaining compliance. [raw]
- "### GREEN: Write Minimal Skill": "Don't add extra content for hypothetical cases." [raw] → rule-bloat guard.
- NEW, missed by the community researcher — highly relevant to criterion 3 (abstract → concrete form selection):
  - "## Match the Form to the Failure": "Before writing guidance, classify the baseline failure." A table maps failure type → right form → wrong form [raw]:
    - Skips/violates a rule under pressure → prohibition + rationalization table + red flags (wrong: soft guidance "prefer/consider")
    - Complies but output has the wrong shape → positive recipe/contract stating what the output IS, parts in order (wrong: prohibition list)
    - Omits a required element → structural REQUIRED field/slot in a template (wrong: prose reminders)
    - Behavior should depend on a condition → conditional keyed to an observable predicate (wrong: unconditional rule + exemption clauses)
  - It reports self-run "head-to-head wording tests on dispatch-prompt guidance": prohibition arm produced more unwanted content than the recipe arm and trended worse than the no-guidance control. (self-reported, no numbers published in the file)
  - "**No nuance clauses.**" "Don't X unless it matters" reopens negotiation; appending one nuance clause to a winning recipe degraded it from consistent to noisy. Real exceptions → own conditional on an observable predicate. [raw]
  - "**Exemption clauses don't scope.**" e.g., "This limit doesn't apply to code blocks" still suppresses code blocks → restructure so the rule can't reach it. [raw]
  - "### Micro-Test Wording Before Full Scenarios" — a 5-step wording-eval procedure [raw]:
    1. one fresh-context sample per call; system prompt = the realistic full context the guidance lives in; user message = a task that tempts the failure
    2. always include a no-guidance control; if the control doesn't fail, there's nothing to fix — don't author the guidance (rule-bloat guard)
    3. 5+ reps per variant
    4. manually read every flagged match (automated counts overstate)
    5. "Variance is a metric": convergent outputs = binding wording; divergent = tighten the form before adding words
- references/bulletproofing.md headings [raw]: "Close Every Loophole Explicitly", "Address 'Spirit vs Letter' Arguments" ("Violating the letter of the rules is violating the spirit of the rules."), "Build Rationalization Table", "Create Red Flags List".

Implication for the report: superpowers covers criterion 3 more strongly than the community note says — it has an explicit procedure that classifies the observed failure first and derives the sentence FORM from the failure type, plus a wording micro-test with control and variance as the metric. Criterion 2 remains self-reported (no published numbers), but the evaluation procedure itself is concrete.

## anthropics/skills — skills/skill-creator/SKILL.md (raw confirmed)

- "### Writing Style": explain to the model why things are important instead of heavy-handed MUSTs; make the skill general, not narrow to specific examples. [raw]
- "### Test Cases": save to `evals/evals.json`; assertions drafted later. [raw]
- "### Step 1: Spawn all runs (with-skill AND baseline) in the same turn"; baseline = without_skill for new skills, old snapshot for improvements. [raw]
- "### Step 2 ... draft assertions": good assertions are objectively verifiable; subjective qualities evaluated qualitatively, not forced into assertions. [raw]
- "### Step 4": grader subagent (agents/grader.md) → grading.json; `scripts.aggregate_benchmark` → benchmark.json with pass_rate, time, tokens, mean ± stddev and delta; analyst pass looks for non-discriminating assertions (always pass regardless of skill) and high-variance evals. [raw]
- "### How to think about improvements": (1) "Generalize from the feedback" — avoid "fiddly overfitty changes" and "oppressively constrictive MUSTs"; (3) "Explain the why"; ALWAYS/NEVER in all caps is "a yellow flag". [raw]
- "## Advanced: Blind comparison" (agents/comparator.md, agents/analyzer.md). [raw]
- "## Description Optimization" Step 3: 60% train / 40% held-out test, each query run 3 times, up to 5 iterations, best_description selected by test score to avoid overfitting. [raw]
