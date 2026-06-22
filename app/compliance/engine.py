"""Compliance Critic implementation."""

from __future__ import annotations

from app.compliance.rules import run_all_rules
from app.domain.enums import Decision, Severity
from app.domain.models import CriticResult, EvidenceBundle, RetentionPlan


class ComplianceCritic:
    """Validate a strategy and return a machine-actionable verdict.

    The critic never edits the plan. Separation of duties is deliberate: the strategist owns
    proposals, the critic owns rejection reasons, and the orchestrator decides whether to iterate.
    """

    def validate(self, plan: RetentionPlan, evidence: EvidenceBundle) -> CriticResult:
        violations = run_all_rules(plan, evidence)
        errors = [item for item in violations if item.severity is Severity.ERROR]
        warnings = [item for item in violations if item.severity is Severity.WARNING]

        if any(item.rule_id == "A.2_CREDIT_STACKING" for item in errors):
            decision = Decision.ESCALATE
            summary = "Human City Manager escalation is mandatory under the credit-stacking rule."
        elif errors:
            decision = Decision.REJECT
            summary = f"Plan rejected with {len(errors)} blocking policy violation(s)."
        elif warnings:
            decision = Decision.CONDITIONAL_APPROVE
            summary = "Plan is policy-shaped but requires unresolved checks or human execution."
        else:
            decision = Decision.APPROVE
            summary = "Plan satisfies all deterministic policy checks."

        return CriticResult(
            decision=decision,
            violations=violations,
            verified_total_gbp=plan.total_gbp_value,
            policy_chunk_ids=[chunk.chunk_id for chunk in evidence.policy_chunks],
            summary=summary,
        )
