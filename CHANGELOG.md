# Changelog

All notable changes follow Keep a Changelog and Semantic Versioning.

## [0.4.0] - 2026-06-25

### Added

- Authoritative action classification so model-provided category, type, cap, and credit flags cannot bypass guardrails.
- Evidence and policy citation validation for every financial recommendation.
- Policy document name, SHA-256 digest, and optional PDF page provenance on retrieved chunks.
- One-command reviewer demonstration and five-minute reviewer guide.
- Explicit tool and agent steps in the audit trace.
- Regression tests for metadata spoofing, invented citations, reviewer flow, and provenance.

### Changed

- Every positive GBP amount now counts toward the monthly cap regardless of model-provided flags.
- Evaluation artifacts now include policy clause IDs on individual violations.
- Documentation and validation evidence were refreshed for the hardened architecture.

## [0.2.0] - 2026-06-22

### Added

- Provider-neutral structured LLM Strategist with OpenAI adapter and deterministic fallback.
- No-cost manual prompt export/import workflow with schema validation and critic-driven revision prompts.
- Automated tests for live-adapter contracts, fallback behaviour, and manual response evaluation.

## [0.1.0] - 2026-06-22

### Added

- Typed Strategist/Compliance Critic workflow with bounded self-correction.
- Driver, ticket, policy, incentive, and ledger tools.
- Deterministic policy guardrails and fail-closed missing-data behaviour.
- SQLite multi-turn memory, FastAPI, CLI, optional Streamlit and OpenAI integrations.
- Docker, CI, Git workflow, evaluation trace, and extensive automated tests.
