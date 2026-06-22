# Technical Design — Driver Retention Copilot

## Objective

Help Driver Relationship Managers diagnose friction and recommend a retention response without
allowing a probabilistic model to bypass corporate policy. The deliverable is recommendation-only;
execution remains a separate authorised workflow.

## Orchestration choice

The system uses a small custom state machine rather than a general-purpose agent runtime. The flow is
`resolve context → collect evidence → Strategist → Compliance Critic → bounded repair → response`.
This choice keeps transitions inspectable, removes framework magic from a 48-hour assignment, and
makes every node independently testable. Interfaces allow the orchestrator to be migrated to
LangGraph later if distributed checkpoints, human interrupts, or long-running tasks justify it.

The Strategist may be deterministic or OpenAI-backed and returns a strict Pydantic `RetentionPlan`.
The Critic never edits plans; it returns stable violation IDs and a verdict. A deterministic repair
component applies critic feedback for at most two iterations. Monetary rules always execute in code.

## RAG and tools

Structured data is retrieved exactly: driver ID filters `driver_profiles.json`, then tickets are
filtered by driver, category, and time window. The Incentive Service is wrapped in a defensive adapter.
Its output is treated as an available catalogue, not policy authorisation.

Policy text is split by clause headings (`A.1`, `B.1`, etc.) so citations align with business rules.
Retrieval always includes global clauses A.1–A.3, then ranks issue-specific clauses using metadata and
lexical overlap. For seven clauses this is more auditable than embedding-only retrieval. The same store
accepts PDF input through PyPDF. At scale, I would add a versioned hybrid index with embeddings,
metadata filters for region/effective date, and offline recall/precision evaluation.

## State and memory

SQLite stores the active driver, previous issue type, recent messages, last plan, and critic result by
conversation ID. This supports follow-ups such as “What is the policy for her tier?” without treating
previous assistant text as evidence. Source records are re-read on every financial recommendation.
Production would use Postgres or Redis with encryption, retention limits, tenant isolation, and
optimistic concurrency.

## Reliability and production controls

Pydantic forbids unknown fields. Missing ledger values remain unknown and trigger conditional approval.
The system validates the £150 monthly cap, two-credit/24-hour stacking, tier restrictions, airport
thresholds and caps, technical caps, new-starter preference, and quest diagnostics. Tool errors fail
safely; external LLM calls use bounded retries; raw complaint text is not logged. The API has request
IDs, structured logs, input limits, health checks, and a non-root read-only container.

Evaluation combines 71 unit/integration/contract tests, an 85% coverage gate, deterministic scenario
checks, and a JSON self-correction trace. Scaling to 20,000 drivers requires stateless API replicas,
managed state and vector stores, cached policy indexes, async tool calls, rate limits, idempotent
execution APIs, human approval queues, and monitoring by rule ID, latency, cost, drift, and override rate.
