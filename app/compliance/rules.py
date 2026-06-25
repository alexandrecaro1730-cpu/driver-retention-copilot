"""Pure, deterministic policy and grounding rules.

Business intent
---------------
Financial caps, eligibility, and evidence grounding are not delegated to probabilistic model
judgement. A proposal may contain descriptive metadata, but the Compliance Critic derives the
attributes that control guardrails from authoritative catalogue and policy data.

Technical intent
----------------
Rules are side-effect-free functions over typed evidence and plans. Stable rule IDs make failures
explainable, testable, and suitable for production monitoring.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.compliance.classification import POLICY_ACTIONS, classify_action
from app.domain.enums import ActionType, LoyaltyTier, Severity
from app.domain.models import EvidenceBundle, PolicyViolation, RetentionPlan

GLOBAL_MONTHLY_CAP = 150.0
AIRPORT_CAPS = {
    LoyaltyTier.GOLD: 25.0,
    LoyaltyTier.SILVER: 15.0,
    LoyaltyTier.BRONZE: 15.0,
}

_POLICY_PREFIX = re.compile(r"^([AB]\.\d+)")
_RULE_POLICY_OVERRIDES: dict[str, list[str]] = {
    "ACTION_CAP_BYPASS_ATTEMPT": ["A.1"],
    "ACTION_CREDIT_CLASSIFICATION_MISMATCH": ["A.2"],
}


def violation(
    rule_id: str,
    message: str,
    fix: str,
    *,
    severity: Severity = Severity.ERROR,
    action_index: int | None = None,
    policy_chunk_ids: list[str] | None = None,
) -> PolicyViolation:
    """Create a traceable policy finding with stable policy references."""

    if policy_chunk_ids is None:
        policy_chunk_ids = _RULE_POLICY_OVERRIDES.get(rule_id, [])
        match = _POLICY_PREFIX.match(rule_id)
        if match:
            policy_chunk_ids = [match.group(1)]
    return PolicyViolation(
        rule_id=rule_id,
        severity=severity,
        message=message,
        suggested_fix=fix,
        action_index=action_index,
        policy_chunk_ids=policy_chunk_ids,
    )


def _allowed_evidence_ids(evidence: EvidenceBundle) -> set[str]:
    ticket_ids = {ticket.ticket_id for ticket in evidence.tickets}
    structured = {
        *(f"profile.{name}" for name in type(evidence.profile).model_fields),
        *(f"observation.{name}" for name in type(evidence.observation).model_fields),
        *(f"ledger.{name}" for name in type(evidence.ledger).model_fields),
    }
    return ticket_ids | structured


def check_grounding(plan: RetentionPlan, evidence: EvidenceBundle) -> Iterable[PolicyViolation]:
    """Reject invented citations and ungrounded financial recommendations."""

    results: list[PolicyViolation] = []
    allowed_evidence = _allowed_evidence_ids(evidence)
    allowed_policy = {chunk.chunk_id for chunk in evidence.policy_chunks}

    for index, action in enumerate(plan.actions):
        financial = action.value_gbp > 0 or action.value_percent > 0

        if financial and not action.evidence_ids:
            results.append(
                violation(
                    "GROUNDING_MISSING_EVIDENCE",
                    "A financial action has no evidence references.",
                    "Cite retrieved ticket IDs or structured profile, observation, and ledger fields.",
                    action_index=index,
                )
            )
        elif unknown := sorted(set(action.evidence_ids) - allowed_evidence):
            results.append(
                violation(
                    "GROUNDING_UNKNOWN_EVIDENCE",
                    f"The action cites evidence not present in the evidence bundle: {unknown}.",
                    "Remove invented references and cite only retrieved evidence IDs.",
                    action_index=index,
                )
            )

        if financial and not action.policy_chunk_ids:
            results.append(
                violation(
                    "GROUNDING_MISSING_POLICY",
                    "A financial action has no policy clause references.",
                    "Cite at least one retrieved policy clause that authorises or constrains the action.",
                    action_index=index,
                )
            )
        elif unknown_policy := sorted(set(action.policy_chunk_ids) - allowed_policy):
            results.append(
                violation(
                    "GROUNDING_UNKNOWN_POLICY",
                    f"The action cites policy clauses not retrieved for this decision: {unknown_policy}.",
                    "Use only clause IDs supplied in the policy evidence bundle.",
                    action_index=index,
                )
            )

    return results


def check_monthly_cap(plan: RetentionPlan, evidence: EvidenceBundle) -> Iterable[PolicyViolation]:
    if plan.total_gbp_value <= 0:
        return []
    current = evidence.ledger.month_to_date_gbp
    if current is None:
        return [
            violation(
                "A.1_LEDGER_UNKNOWN",
                "Month-to-date retention spend is unavailable, so the £150 cap cannot be verified.",
                "Fetch the authoritative retention ledger before issuing monetary actions.",
                severity=Severity.WARNING,
            )
        ]
    projected = current + plan.total_gbp_value
    if projected > GLOBAL_MONTHLY_CAP:
        return [
            violation(
                "A.1_MONTHLY_CAP",
                f"Projected monthly value £{projected:.2f} exceeds the £150.00 cap.",
                f"Reduce package value by at least £{projected - GLOBAL_MONTHLY_CAP:.2f} or escalate.",
            )
        ]
    return []


def check_credit_stacking(
    plan: RetentionPlan, evidence: EvidenceBundle
) -> Iterable[PolicyViolation]:
    proposed = sum(
        1 for action in plan.actions if classify_action(action, evidence).immediate_credit
    )
    if proposed == 0:
        return []
    existing = evidence.ledger.immediate_credits_last_24h
    if existing is None:
        return [
            violation(
                "A.2_LEDGER_UNKNOWN",
                "Credits issued in the last 24 hours are unavailable.",
                "Fetch credit history before issuing an immediate credit.",
                severity=Severity.WARNING,
            )
        ]
    if existing + proposed > 2:
        return [
            violation(
                "A.2_CREDIT_STACKING",
                f"The plan would create credit number {existing + proposed} in 24 hours.",
                "Remove immediate credits and escalate to a human City Manager.",
            )
        ]
    return []


def check_action_integrity(
    plan: RetentionPlan, evidence: EvidenceBundle
) -> Iterable[PolicyViolation]:
    """Validate proposal metadata against authoritative service and policy definitions."""

    results: list[PolicyViolation] = []
    available = {incentive.id: incentive for incentive in evidence.incentives}

    for index, action in enumerate(plan.actions):
        if action.value_gbp > 0 and action.incentive_id is None:
            results.append(
                violation(
                    "ACTION_UNSOURCED_MONETARY_VALUE",
                    "A GBP-valued action has no authoritative incentive or policy action ID.",
                    "Select an available incentive or a registered policy action.",
                    action_index=index,
                )
            )
            continue

        if action.incentive_id and action.incentive_id.startswith("POLICY-"):
            if action.incentive_id not in POLICY_ACTIONS:
                results.append(
                    violation(
                        "ACTION_UNKNOWN_POLICY_ACTION",
                        f"{action.incentive_id} is not a registered policy action.",
                        "Use a registered policy action or remove the monetary recommendation.",
                        action_index=index,
                    )
                )
                continue
        elif action.incentive_id and action.incentive_id not in available:
            results.append(
                violation(
                    "TOOL_INCENTIVE_NOT_AVAILABLE",
                    f"{action.incentive_id} was not returned by the Incentive Service.",
                    "Remove the action or refresh eligible incentives.",
                    action_index=index,
                )
            )
            continue

        authoritative = classify_action(action, evidence)
        item = authoritative.catalogue_item

        if item is not None and action.category.casefold() != authoritative.category.casefold():
            results.append(
                violation(
                    "ACTION_CATEGORY_MISMATCH",
                    f"The proposal labels {item.id} as {action.category!r}, but the service classifies it as {item.category!r}.",
                    "Use the authoritative Incentive Service category.",
                    action_index=index,
                )
            )

        if item is not None and action.action_type is not authoritative.action_type:
            results.append(
                violation(
                    "ACTION_TYPE_MISMATCH",
                    f"The proposal action type {action.action_type.value!r} conflicts with the authoritative type {authoritative.action_type.value!r} for {item.id}.",
                    "Use the authoritative action type.",
                    action_index=index,
                )
            )

        if authoritative.counts_toward_monthly_cap and not action.counts_toward_monthly_cap:
            results.append(
                violation(
                    "ACTION_CAP_BYPASS_ATTEMPT",
                    "A positive GBP action was marked as excluded from the monthly cap.",
                    "Count every positive GBP action toward the monthly retention cap.",
                    action_index=index,
                )
            )

        if action.immediate_credit != authoritative.immediate_credit:
            results.append(
                violation(
                    "ACTION_CREDIT_CLASSIFICATION_MISMATCH",
                    "The proposal's immediate-credit flag conflicts with the authoritative action classification.",
                    "Use the deterministic credit classification; do not use proposal flags to control stacking checks.",
                    action_index=index,
                )
            )

        if item is not None:
            if item.currency.casefold() == "gbp":
                if action.value_percent > 0:
                    results.append(
                        violation(
                            "ACTION_CURRENCY_MISMATCH",
                            f"{item.id} is GBP-valued but the proposal also supplies a percentage value.",
                            "Remove the percentage value.",
                            action_index=index,
                        )
                    )
                if action.value_gbp > item.value:
                    results.append(
                        violation(
                            "ACTION_VALUE_EXCEEDS_CATALOGUE",
                            f"£{action.value_gbp:.2f} exceeds the service value of £{item.value:.2f} for {item.id}.",
                            f"Reduce the proposal to no more than £{item.value:.2f} before policy caps are applied.",
                            action_index=index,
                        )
                    )
            elif item.currency.casefold() == "percent":
                if action.value_gbp > 0:
                    results.append(
                        violation(
                            "ACTION_CURRENCY_MISMATCH",
                            f"{item.id} is percentage-valued but the proposal supplies a GBP value.",
                            "Use value_percent and set value_gbp to zero.",
                            action_index=index,
                        )
                    )
                if action.value_percent > item.value:
                    results.append(
                        violation(
                            "ACTION_VALUE_EXCEEDS_CATALOGUE",
                            f"{action.value_percent:.2f}% exceeds the service value of {item.value:.2f}% for {item.id}.",
                            f"Reduce the proposal to no more than {item.value:.2f}%.",
                            action_index=index,
                        )
                    )

    return results


def check_action_rules(plan: RetentionPlan, evidence: EvidenceBundle) -> Iterable[PolicyViolation]:
    results: list[PolicyViolation] = []
    available = {incentive.id: incentive for incentive in evidence.incentives}
    tier = evidence.profile.loyalty_tier
    observation = evidence.observation

    for index, action in enumerate(plan.actions):
        authoritative = classify_action(action, evidence)
        category = authoritative.category.casefold()

        if category == "churn" and tier is LoyaltyTier.BRONZE:
            results.append(
                violation(
                    "A.3_CHURN_TIER",
                    "Churn goodwill credits are not permitted for Bronze drivers.",
                    "Remove the goodwill credit or use a non-credit engagement action.",
                    action_index=index,
                )
            )

        if category == "airport" and action.value_gbp > 0:
            if observation.wait_minutes is None or observation.trip_distance_km is None:
                results.append(
                    violation(
                        "B.1_MISSING_EVIDENCE",
                        "Airport compensation requires evidenced wait time and trip distance.",
                        "Collect both measurements before proposing a credit.",
                        action_index=index,
                    )
                )
            else:
                if observation.wait_minutes <= 90:
                    results.append(
                        violation(
                            "B.1_WAIT_THRESHOLD",
                            "Airport wait must be greater than 90 minutes.",
                            "Remove the airport credit or provide qualifying evidence.",
                            action_index=index,
                        )
                    )
                if observation.trip_distance_km >= 3:
                    results.append(
                        violation(
                            "B.1_DISTANCE_THRESHOLD",
                            "Airport trip distance must be less than 3 km.",
                            "Remove the airport credit or provide qualifying evidence.",
                            action_index=index,
                        )
                    )
            cap = AIRPORT_CAPS[tier]
            if action.value_gbp > cap:
                results.append(
                    violation(
                        "B.1_TIER_CAP",
                        f"£{action.value_gbp:.2f} exceeds the {tier.value} airport cap of £{cap:.2f}.",
                        f"Reduce the action to no more than £{cap:.2f}.",
                        action_index=index,
                    )
                )
            if action.incentive_id == "INC-002" and not observation.multi_day_systemic_failure:
                results.append(
                    violation(
                        "B.1_INC002_RESTRICTED",
                        "INC-002 is reserved for documented multi-day systemic failures.",
                        "Use INC-001 at the tier cap for standard short-fare recovery.",
                        action_index=index,
                    )
                )
            catalogue_item = available.get("INC-001")
            if (
                action.incentive_id == "INC-001"
                and catalogue_item is not None
                and action.value_gbp != catalogue_item.value
            ):
                results.append(
                    violation(
                        "SERVICE_PARAMETERISATION_REQUIRED",
                        "The mock exposes INC-001 as a fixed £25 item but policy requires a lower tier cap.",
                        "Route through a parameterised production endpoint or obtain human approval.",
                        severity=Severity.WARNING,
                        action_index=index,
                    )
                )

        if category == "technical" and action.value_gbp > 10:
            results.append(
                violation(
                    "B.2_TECHNICAL_CAP",
                    "Technical/GPS compensation exceeds the £10 per-glitch cap.",
                    "Reduce the action to £10 or less.",
                    action_index=index,
                )
            )

        if action.incentive_id == "INC-004" and observation.recurring_technical_tickets_7d <= 2:
            results.append(
                violation(
                    "B.2_PRIORITY_SUPPORT_THRESHOLD",
                    "INC-004 requires more than two technical tickets in seven days.",
                    "Remove priority support until recurrence is evidenced.",
                    action_index=index,
                )
            )

        if category == "quest" and action.value_gbp > 0:
            if (
                observation.quest_completion_ratio is None
                or observation.quest_completion_ratio <= 0.8
                or observation.offers_per_hour is None
                or observation.offers_per_hour >= 1.5
            ):
                results.append(
                    violation(
                        "B.4_QUEST_ELIGIBILITY",
                        "Quest goodwill requires >80% completion and documented demand below 1.5 offers/hour.",
                        "Collect diagnostics or remove the goodwill gesture.",
                        action_index=index,
                    )
                )
            if action.value_gbp > 20:
                results.append(
                    violation(
                        "B.4_QUEST_CAP",
                        "Quest goodwill exceeds the permitted £20 gesture.",
                        "Reduce the action to £20.",
                        action_index=index,
                    )
                )

    if evidence.profile.tenure_months < 3:
        direct_credit = any(
            classify_action(action, evidence).action_type is ActionType.CREDIT
            and action.value_gbp > 0
            for action in plan.actions
        )
        shield_available = "INC-006" in available
        shield_selected = any(action.incentive_id == "INC-006" for action in plan.actions)
        if direct_credit and shield_available and not shield_selected:
            results.append(
                violation(
                    "B.3_NEW_STARTER_PREFERENCE",
                    "A commission shield is available but the plan prioritises a direct credit.",
                    "Prefer INC-006 and explain any exception.",
                    severity=Severity.WARNING,
                )
            )
    return results


def run_all_rules(plan: RetentionPlan, evidence: EvidenceBundle) -> list[PolicyViolation]:
    return [
        *check_grounding(plan, evidence),
        *check_action_integrity(plan, evidence),
        *check_monthly_cap(plan, evidence),
        *check_credit_stacking(plan, evidence),
        *check_action_rules(plan, evidence),
    ]
