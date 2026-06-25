# Technical Design — Driver Retention Copilot

## Objective and orchestration

The Copilot helps Driver Relationship Managers diagnose driver friction and recommend a safe response.
It uses a small custom typed state machine:

```text
context → tools/RAG → Strategist → Compliance Critic → bounded revision → response
```

The Strategist may be heuristic or LLM-backed and returns a strict Pydantic `RetentionPlan`. The
Critic is an independent deterministic agent: it never edits plans and returns stable violation IDs.
This hybrid design preserves the Actor/Validator separation requested by the assignment while keeping
financial enforcement reproducible and auditable.

## RAG and tool strategy

Structured records are retrieved exactly by driver ID from profile, ticket, ledger, and incentive
boundaries. Policy text is split by business clause (`A.1`, `B.1`, etc.), tagged by issue and tier,
and ranked lexically. Global clauses are always injected even when lexical overlap is low. Policy
chunks retain document name, SHA-256 digest, and PDF page number when available. For this seven-clause
corpus, transparent lexical retrieval is preferable to an embedding-only index; a larger estate would
use a versioned hybrid index with access controls and retrieval evaluation.

## State and memory

SQLite checkpoints store conversation ID, active driver, previous issue type, recent messages, last
plan, and last Critic result. Follow-up turns can reuse driver and issue context, while source records
are re-read for each financial recommendation. Production would move state to PostgreSQL or Redis with
encryption, retention controls, tenant isolation, and optimistic concurrency.

## Safety, correction, and scale

LLM output forbids unknown fields and cannot control its own guardrails. Catalogue-backed category,
action type, immediate-credit status, and monthly-cap treatment are derived authoritatively. The
Critic validates monetary caps, stacking, eligibility, evidence IDs, policy citations, and missing
operational data. Rejected plans receive structured feedback for at most two revisions. Provider calls
use bounded retries and deterministic fallback; no recommendation issues money automatically.

At 20,000 drivers, local files become authenticated services, SQLite becomes managed state, policy
retrieval becomes a cached hybrid service, independent tool calls run concurrently with deadlines,
and decisions flow to central audit, metrics, and human-review queues.
