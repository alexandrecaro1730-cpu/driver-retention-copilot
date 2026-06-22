# Production Readiness and Scale Path

## Already represented

- Typed input/output boundaries and explicit failure classes.
- Deterministic financial guardrails with stable rule IDs.
- Fail-closed missing-data semantics.
- Bounded agent revisions and external-call retries.
- Structured logging without raw complaint content.
- Health endpoint, request IDs, container health check, non-root runtime, and read-only filesystem.
- Unit, integration, contract, failure-mode, and evaluation-trace tests.

## Before issuing real incentives

1. Replace the synthetic ledger with an authoritative, strongly consistent spend/credit service.
2. Add an idempotent execution endpoint requiring a manager approval token and policy decision hash.
3. Store policy version, source page, effective date, jurisdiction, and retrieval score on each decision.
4. Add RBAC, SSO, tenant isolation, encryption, audit retention, and GDPR deletion workflows.
5. Add distributed tracing, metrics, alerting, rate limits, circuit breakers, and dead-letter handling.
6. Red-team prompt injection in tickets and policy documents; tools must never follow retrieved
   instructions outside their schema.
7. Introduce shadow mode, then limited human-approved rollout before any automation.

## 20,000-driver scale

Run stateless API replicas behind a load balancer. Move checkpoints to Postgres/Redis, structured data
to operational services, and policy retrieval to a managed hybrid index. Fetch independent tools
concurrently with deadlines. Cache immutable policy chunks by version. Partition operational metrics
by city and policy version. Use queue-backed human review for conditional and escalation decisions.

Key service-level indicators: p50/p95 latency, tool timeout rate, LLM fallback rate, critic rejection
rate, average revisions, conditional-approval rate, policy-rule frequency, human override rate,
issuance failure rate, cost per case, and retention outcome drift.

## Hallucination controls

- No fact is accepted without structured source data or a cited policy chunk.
- Unknown measurements stay null and block monetary eligibility.
- Incentive IDs must be returned by the tool or explicitly defined as a policy-only action.
- Pydantic rejects unknown fields and out-of-range values.
- Deterministic rules override every Strategist implementation.
