# Production Readiness and Scale Path

## Controls represented in this repository

- Strict Pydantic contracts and explicit application exceptions.
- Separate Strategist and deterministic Compliance Critic responsibilities.
- Authoritative classification of catalogue-backed category, action type, cap treatment, and credit
  stacking; model-provided flags cannot disable their own guardrails.
- Validation of ticket, structured-field, and policy-clause references.
- Fail-closed handling of unknown monthly spend and recent credit history.
- Bounded Strategist revisions and bounded provider retries with deterministic fallback.
- Policy document name, SHA-256 digest, and optional PDF page provenance.
- Structured logging without raw complaint content or provider secrets.
- Health endpoint, request IDs, non-root container runtime, and read-only container filesystem.
- Unit, integration, contract, failure-mode, hardening, reviewer-demo, and evaluation-artifact tests.

## Before issuing real incentives

1. Replace the synthetic ledger with an authoritative, strongly consistent spend and credit service.
2. Add an idempotent execution endpoint that requires manager approval, a policy version, and a signed
   decision hash. Keep recommendation and execution permissions separate.
3. Ingest the original policy document with effective date, jurisdiction, owner, source page, version,
   and access-control metadata. Alert when policy text and policy-as-code diverge.
4. Add RBAC, SSO, tenant isolation, encryption, audit retention, and GDPR deletion workflows.
5. Add distributed tracing, metrics, alerting, rate limits, circuit breakers, deadlines, and dead-letter
   handling for tool and execution failures.
6. Red-team prompt injection and data exfiltration through tickets, policy files, and tool payloads.
7. Run in shadow mode, then human-approved limited rollout, before enabling any execution workflow.

## 20,000-driver scale

Run stateless API replicas behind a load balancer. Move checkpoints to PostgreSQL or Redis, source data
to operational services, and policy retrieval to a versioned hybrid service. Fetch independent tools
concurrently under deadlines. Cache immutable policy chunks by version. Route conditional and
escalation outcomes through a queue-backed human review service.

Key service indicators include p50/p95 latency, tool timeout rate, LLM fallback rate, Critic rejection
rate, average revisions, citation-failure rate, metadata-bypass attempts, human override rate,
issuance failure rate, cost per case, and retention-outcome drift by city and policy version.

## Hallucination and manipulation controls

- Facts require retrieved source data or approved structured field references.
- Financial actions require both evidence and policy citations.
- Incentive IDs must come from the service or the explicit policy-action registry.
- Catalogue category and type override conflicting proposal fields.
- Every positive GBP value counts toward the monthly cap.
- Credit stacking uses deterministic classification, not the model's `immediate_credit` flag.
- Unknown measurements remain null and block unsafe approval.
- Deterministic rules remain authoritative for every Strategist implementation.
