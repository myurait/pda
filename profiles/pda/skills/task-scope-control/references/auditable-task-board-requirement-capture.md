# Auditable task-board requirement capture

Use this reference for a narrow request to add or extend work in a canonical task board without starting implementation.

## Bounded workflow

1. Freeze the outcome as “capture this requirement accurately in the canonical board.” Implementation, assignment, promotion, scheduling, and repair are non-goals unless explicitly requested.
2. Perform one bounded search of active cards in the relevant tenant/workstream, including titles, bodies, and comments. Search by outcome and subsystem, not only the user's exact wording.
3. If an existing card owns the same outcome, extend it rather than creating a near-duplicate. Choose one primary owner card for complete acceptance criteria.
4. Use the board's supported CLI or API so the update creates an audit event and enters worker context. For Hermes Kanban, an audited comment is suitable for extending a card when no general body-edit command is available; avoid direct database mutation.
5. When a requirement crosses two existing cards, put lifecycle/transport or other implementation ownership on one card and add a short reciprocal source-of-truth comment to the adjacent card. Do not duplicate the full scope, and do not create a dependency edge unless execution is truly gated.
6. If the new requirement authorizes a narrow exception to an older safety boundary, record the exact channel, audience, allowed fields, redaction, and audit expectations. Do not silently weaken the original boundary.
7. Read back the affected cards and their events, then verify that no extra card was created. Stop without assigning or implementing.

## Hermes Kanban notes

A board slug and a task `tenant` are different namespaces. Confirm existing board slugs before passing `--board`; a tenant value is not automatically a board name. `hermes kanban show` proves the stored body, comments, status, tenant, and audit events. `hermes kanban context` includes comments in the worker's effective task context.

## Report shape

Tell the owner which existing card or class of card received the requirement, summarize the newly binding behavior, state whether a duplicate card was avoided, and say explicitly whether implementation or assignment began. Omit database paths, commands, and internal identifiers unless decision-critical or requested.
