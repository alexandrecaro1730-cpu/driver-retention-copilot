"""Pure policy rules.

Business intent: monetary caps and categorical eligibility are not delegated to probabilistic model
judgement. Each function emits a stable rule ID that can be monitored, tested, and audited.

Technical intent: rules are pure functions over typed evidence and plans. No I/O occurs here, which
keeps edge-case testing fast and exhaustive.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.enums import ActionType, LoyaltyTier, Severity
from app.domain.models import EvidenceBundle, PolicyViolation, RetentionPlan

GLOBAL_MONTHLY_CAP = 150.0
AIRPORT_CAPS = {
    LoyaltyTier.GOLD: 25.0,
    LoyaltyTier.SILVER: 15.0,
    LoyaltyTier.BRONZE: 15.0,
}


def violation(
    rule_id: str,
    message: str,
    fix: str,
    *,
    severity: Severity = Severity.ERROR,
    action_index: int | None = None,
) -> PolicyViolation:
    return PolicyViolation(
        rule_id=rule_id,
        severity=severity,
        message=message,
        suggested_fix=fix,
        action_index=action_index,
    )


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
    proposed = sum(1 for action in plan.actions if action.immediate_credit)
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


def check_action_rules(plan: RetentionPlan, evidence: EvidenceBundle) -> Iterable[PolicyViolation]:
    results: list[PolicyViolation] = []
    available = {incentive.id: incentive for incentive in evidence.incentives}
    tier = evidence.profile.loyalty_tier
    observation = evidence.observation

    for index, action in enumerate(plan.actions):
        if (
            action.incentive_id
            and not action.incentive_id.startswith("POLICY-")
            and action.incentive_id not in available
        ):
            results.append(
                violation(
                    "TOOL_INCENTIVE_NOT_AVAILABLE",
                    f"{action.incentive_id} was not returned by the Incentive Service.",
                    "Remove the action or refresh eligible incentives.",
                    action_index=index,
                )
            )
            continue

        if action.category.casefold() == "churn" and tier is LoyaltyTier.BRONZE:
            results.append(
                violation(
                    "A.3_CHURN_TIER",
                    "Churn goodwill credits are not permitted for Bronze drivers.",
                    "Remove the goodwill credit or use a non-credit engagement action.",
                    action_index=index,
                )
            )

        if action.category.casefold() == "airport" and action.value_gbp > 0:
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

        if action.category.casefold() == "technical" and action.value_gbp > 10:
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

        if action.category.casefold() == "quest" and action.value_gbp > 0:
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
        direct_credit = any(a.action_type is ActionType.CREDIT for a in plan.actions)
        shield_available = "INC-006" in available
        shield_selected = any(a.incentive_id == "INC-006" for a in plan.actions)
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
        *check_monthly_cap(plan, evidence),
        *check_credit_stacking(plan, evidence),
        *check_action_rules(plan, evidence),
    ]
