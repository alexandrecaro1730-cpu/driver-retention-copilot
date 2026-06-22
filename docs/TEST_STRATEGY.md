# Test Strategy

The test suite is intentionally weighted toward deterministic business rules because these are the
highest-risk failure surface.

## Layers

- **Domain contracts:** strict schemas, bounds, and computed totals.
- **Repositories/tools:** exact retrieval, ordering, eligibility filtering, malformed payloads, and
  upstream failure translation.
- **Diagnostics:** unit conversion, threshold extraction, missing facts, explicit systemic-failure
  wording, and multi-turn issue context.
- **Compliance:** boundary values (`90` vs `>90`, `3 km` vs `<3 km`), tier caps, monthly cap,
  stacking, technical rules, quest rules, unavailable incentives, and unknown ledgers.
- **Strategist/repair:** issue-specific plans, no invented credits, new-starter preference, and
  deterministic correction of rejected plans.
- **Orchestration:** full Maria flow, reject→revise→approve trace, conversation memory, and conditional
  approval for missing operational data.
- **API:** health, successful contract, validation, and safe error mapping.

## Gates

- 100% passing tests.
- Branch coverage of at least 85%.
- Ruff format/lint and strict mypy.
- Bandit and dependency audit.
- Generated evaluation trace must contain a Critic `REJECT` followed by `APPROVE`.

LLM output quality should later be evaluated separately for groundedness, empathy, and actionability.
An LLM judge must never replace deterministic compliance tests.
