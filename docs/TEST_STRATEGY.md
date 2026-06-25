# Test Strategy

The suite is weighted toward deterministic business rules and trust boundaries because they are the
highest-risk failure surface.

## Layers

- **Domain contracts:** strict schemas, bounds, authoritative GBP totals, and violation provenance.
- **Repositories/tools:** exact retrieval, ordering, eligibility filtering, malformed payloads, and
  upstream failure translation.
- **Diagnostics:** unit conversion, threshold extraction, missing facts, explicit systemic-failure
  wording, and multi-turn issue context.
- **Compliance:** threshold boundaries, tier caps, monthly cap, stacking, technical and quest rules,
  unavailable incentives, unknown ledgers, and policy clause mapping.
- **Trust-boundary hardening:** category spoofing, action-type spoofing, cap and credit flag bypasses,
  unsourced monetary actions, catalogue over-value, and invented evidence or policy references.
- **Strategist/repair:** issue-specific plans, no invented credits, new-starter preference, and
  deterministic correction of rejected plans.
- **Orchestration:** complete Maria flow, explicit tool/actor trace, reject→revise→approve, and
  conversation memory.
- **Reviewer and evaluation artifacts:** one-command demonstration plus committed deterministic and
  human-mediated correction traces.
- **API:** health, successful contract, validation, and safe error mapping.

## Gates

- 100% passing tests.
- Branch-aware coverage of at least 85%.
- Ruff formatting/lint and strict mypy.
- Bandit and dependency audit.
- Evaluation traces must contain a Critic `REJECT` followed by `APPROVE`.
- Financial recommendations must have valid evidence and policy references.

LLM output quality can additionally be evaluated for empathy and actionability, but an LLM judge must
never replace deterministic compliance tests.
