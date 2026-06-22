"""Deterministic Strategist and repair agent.

Business intent: provide a trustworthy baseline that demonstrates the actor/validator architecture
without requiring paid infrastructure. It also serves as a fallback when an LLM is rate-limited.

Technical intent: this class is intentionally policy-aware but not policy-authoritative. The
Compliance Critic still re-checks every action, including those produced by this implementation.
"""

from __future__ import annotations

from copy import deepcopy

from app.compliance.rules import AIRPORT_CAPS, GLOBAL_MONTHLY_CAP
from app.domain.enums import ActionType, ChurnRisk, IssueType, LoyaltyTier
from app.domain.models import (
    CriticResult,
    EvidenceBundle,
    ProposedAction,
    RetentionPlan,
)

_NEGATIVE = ("angry", "frustrated", "upset", "furious", "annoyed")


class HeuristicStrategist:
    def propose(self, evidence: EvidenceBundle) -> RetentionPlan:
        profile = evidence.profile
        observation = evidence.observation
        available = {item.id: item for item in evidence.incentives}
        ticket_ids = [ticket.ticket_id for ticket in evidence.tickets[:5]]
        policy_ids = [chunk.chunk_id for chunk in evidence.policy_chunks]
        actions: list[ProposedAction] = []
        missing: list[str] = []
        assumptions: list[str] = []

        if observation.policy_question:
            if observation.issue_type is IssueType.AIRPORT_SHORT_FARE:
                cap = AIRPORT_CAPS[profile.loyalty_tier]
                explanation = (
                    f"For {profile.loyalty_tier.value} drivers, airport short-fare recovery requires "
                    f"a wait above 90 minutes and a trip below 3 km; the per-instance cap is £{cap:.2f}."
                )
            else:
                explanation = (
                    f"Explain the retrieved {observation.issue_type.value.replace('_', ' ')} clauses "
                    f"for the driver's {profile.loyalty_tier.value} tier without issuing a new benefit."
                )
            actions.append(
                ProposedAction(
                    action_type=ActionType.COMMUNICATION,
                    name="Explain the applicable retention policy",
                    category="Policy",
                    counts_toward_monthly_cap=False,
                    rationale=explanation,
                    evidence_ids=ticket_ids,
                    policy_chunk_ids=policy_ids,
                )
            )

        elif observation.issue_type is IssueType.AIRPORT_SHORT_FARE:
            qualified = (
                observation.wait_minutes is not None
                and observation.wait_minutes > 90
                and observation.trip_distance_km is not None
                and observation.trip_distance_km < 3
            )
            if qualified and "INC-001" in available:
                cap = AIRPORT_CAPS[profile.loyalty_tier]
                parameterised = available["INC-001"].value != cap
                actions.append(
                    ProposedAction(
                        action_type=ActionType.CREDIT,
                        name="Standard airport short-fare recovery",
                        incentive_id="INC-001",
                        category="Airport",
                        value_gbp=cap,
                        immediate_credit=True,
                        rationale="Restore trust after a policy-qualifying airport wait and short trip.",
                        evidence_ids=ticket_ids,
                        policy_chunk_ids=["B.1", "A.1", "A.2"],
                        requires_human_approval=parameterised,
                    )
                )
            else:
                if observation.wait_minutes is None:
                    missing.append("Exact airport wait time")
                if observation.trip_distance_km is None:
                    missing.append("Exact trip distance")
                actions.append(
                    ProposedAction(
                        action_type=ActionType.SUPPORT,
                        name="Verify airport trip telemetry",
                        category="Airport",
                        counts_toward_monthly_cap=False,
                        rationale="Do not issue money until both SFP eligibility measurements are verified.",
                        evidence_ids=ticket_ids,
                        policy_chunk_ids=["B.1"],
                    )
                )
            if profile.loyalty_tier is LoyaltyTier.GOLD and "Q-103" in available:
                actions.append(
                    ProposedAction(
                        action_type=ActionType.QUEST,
                        name=available["Q-103"].name,
                        incentive_id="Q-103",
                        category="Engagement",
                        counts_toward_monthly_cap=False,
                        rationale="Offer a non-cash confidence reset for the next airport session.",
                        evidence_ids=ticket_ids,
                        policy_chunk_ids=["B.1"],
                    )
                )
            if observation.related_ticket_count >= 3:
                actions.append(
                    ProposedAction(
                        action_type=ActionType.ESCALATION,
                        name="Airport queue quality investigation",
                        category="Operations",
                        counts_toward_monthly_cap=False,
                        rationale="Repeated short-fare complaints indicate a possible operational pattern.",
                        evidence_ids=ticket_ids,
                        policy_chunk_ids=["B.1"],
                        requires_human_approval=True,
                    )
                )

        elif observation.issue_type is IssueType.TECHNICAL_GPS:
            if "INC-003" in available and observation.related_ticket_count > 0:
                actions.append(
                    ProposedAction(
                        action_type=ActionType.CREDIT,
                        name=available["INC-003"].name,
                        incentive_id="INC-003",
                        category="Technical",
                        value_gbp=10,
                        immediate_credit=True,
                        rationale="Compensate one confirmed GPS/geofence incident at the policy cap.",
                        evidence_ids=ticket_ids,
                        policy_chunk_ids=["B.2", "A.1", "A.2"],
                    )
                )
            if observation.recurring_technical_tickets_7d > 2 and "INC-004" in available:
                actions.append(
                    ProposedAction(
                        action_type=ActionType.SUPPORT,
                        name=available["INC-004"].name,
                        incentive_id="INC-004",
                        category="Technical",
                        counts_toward_monthly_cap=False,
                        rationale="Recurring geofence incidents meet the priority-support threshold.",
                        evidence_ids=ticket_ids,
                        policy_chunk_ids=["B.2"],
                    )
                )

        elif profile.tenure_months < 3 or observation.issue_type is IssueType.NEW_STARTER:
            if "INC-006" in available:
                shield = available["INC-006"]
                actions.append(
                    ProposedAction(
                        action_type=ActionType.DISCOUNT,
                        name=shield.name,
                        incentive_id=shield.id,
                        category="Commission",
                        value_percent=shield.value,
                        counts_toward_monthly_cap=False,
                        rationale="Policy prioritises continued usage via a commission shield.",
                        evidence_ids=ticket_ids,
                        policy_chunk_ids=["B.3"],
                    )
                )
            else:
                actions.append(
                    ProposedAction(
                        action_type=ActionType.SUPPORT,
                        name="New-starter coaching and offer visibility review",
                        category="Tenure",
                        counts_toward_monthly_cap=False,
                        rationale="The preferred shield is not service-eligible; avoid inventing a cash substitute.",
                        evidence_ids=ticket_ids,
                        policy_chunk_ids=["B.3"],
                        requires_human_approval=True,
                    )
                )

        elif observation.issue_type is IssueType.QUEST:
            if (
                observation.quest_completion_ratio is not None
                and observation.quest_completion_ratio > 0.8
                and observation.offers_per_hour is not None
                and observation.offers_per_hour < 1.5
            ):
                actions.append(
                    ProposedAction(
                        action_type=ActionType.CREDIT,
                        name="Infeasible Quest goodwill gesture",
                        incentive_id="POLICY-QUEST-20",
                        category="Quest",
                        value_gbp=20,
                        immediate_credit=True,
                        rationale="Completion and low-demand diagnostics satisfy the policy exception.",
                        evidence_ids=ticket_ids,
                        policy_chunk_ids=["B.4", "A.1", "A.2"],
                        requires_human_approval=True,
                    )
                )
            else:
                missing.extend(["Quest completion above 80%", "Demand below 1.5 offers/hour"])
                actions.append(
                    ProposedAction(
                        action_type=ActionType.SUPPORT,
                        name="Retrieve Quest and demand diagnostics",
                        category="Quest",
                        counts_toward_monthly_cap=False,
                        rationale="The goodwill exception cannot be applied without both diagnostics.",
                        evidence_ids=ticket_ids,
                        policy_chunk_ids=["B.4"],
                    )
                )

        else:
            actions.append(
                ProposedAction(
                    action_type=ActionType.ESCALATION,
                    name="Route issue to the responsible operations queue",
                    category=observation.issue_type.value,
                    counts_toward_monthly_cap=False,
                    rationale="No supplied policy authorises an automated financial recovery for this issue.",
                    evidence_ids=ticket_ids,
                    policy_chunk_ids=policy_ids,
                    requires_human_approval=True,
                )
            )

        if evidence.ledger.month_to_date_gbp is None:
            assumptions.append(
                "Monetary actions remain pending until month-to-date spend is fetched."
            )
        if evidence.ledger.immediate_credits_last_24h is None:
            assumptions.append("Immediate credits remain pending until 24-hour history is fetched.")

        return RetentionPlan(
            driver_id=profile.driver_id,
            diagnosis=self._diagnosis(evidence),
            churn_risk=self._risk(evidence),
            actions=actions,
            assumptions=assumptions,
            missing_data=sorted(set(missing)),
        )

    def revise(
        self, plan: RetentionPlan, critique: CriticResult, evidence: EvidenceBundle
    ) -> RetentionPlan:
        revised = deepcopy(plan)
        revised.revision += 1
        removal_indices: set[int] = set()

        for problem in critique.violations:
            index = problem.action_index
            if problem.rule_id in {"B.1_TIER_CAP", "B.1_INC002_RESTRICTED"} and index is not None:
                action = revised.actions[index]
                action.incentive_id = "INC-001"
                action.name = "Standard airport short-fare recovery"
                action.value_gbp = AIRPORT_CAPS[evidence.profile.loyalty_tier]
                action.requires_human_approval = (
                    evidence.profile.loyalty_tier is not LoyaltyTier.GOLD
                )
            elif (
                problem.rule_id
                in {
                    "B.1_MISSING_EVIDENCE",
                    "B.1_WAIT_THRESHOLD",
                    "B.1_DISTANCE_THRESHOLD",
                    "B.4_QUEST_ELIGIBILITY",
                    "A.3_CHURN_TIER",
                    "TOOL_INCENTIVE_NOT_AVAILABLE",
                    "B.2_PRIORITY_SUPPORT_THRESHOLD",
                }
                and index is not None
            ):
                removal_indices.add(index)
            elif problem.rule_id == "B.2_TECHNICAL_CAP" and index is not None:
                revised.actions[index].value_gbp = 10
            elif problem.rule_id == "B.4_QUEST_CAP" and index is not None:
                revised.actions[index].value_gbp = 20
            elif problem.rule_id == "A.2_CREDIT_STACKING":
                removal_indices.update(
                    idx for idx, action in enumerate(revised.actions) if action.immediate_credit
                )
                revised.actions.append(
                    ProposedAction(
                        action_type=ActionType.ESCALATION,
                        name="City Manager review required",
                        category="Compliance",
                        counts_toward_monthly_cap=False,
                        rationale="A third immediate credit in 24 hours is prohibited.",
                        policy_chunk_ids=["A.2"],
                        requires_human_approval=True,
                    )
                )
            elif problem.rule_id == "A.1_MONTHLY_CAP":
                current = evidence.ledger.month_to_date_gbp or 0
                remaining = max(0.0, GLOBAL_MONTHLY_CAP - current)
                for action in revised.actions:
                    if action.counts_toward_monthly_cap and action.value_gbp > remaining:
                        action.value_gbp = remaining
                        action.requires_human_approval = True
                        remaining = 0
                    elif action.counts_toward_monthly_cap:
                        remaining -= action.value_gbp

        revised.actions = [
            action for idx, action in enumerate(revised.actions) if idx not in removal_indices
        ]
        if not revised.actions:
            revised.actions.append(
                ProposedAction(
                    action_type=ActionType.SUPPORT,
                    name="Collect missing evidence and reassess",
                    category="Compliance",
                    counts_toward_monthly_cap=False,
                    rationale="The original monetary action could not be made compliant.",
                    policy_chunk_ids=[item.rule_id.split("_")[0] for item in critique.violations],
                )
            )
        revised.assumptions.append(
            "Revision generated from Compliance Critic feedback; no rejected action may be executed."
        )
        return revised

    @staticmethod
    def _risk(evidence: EvidenceBundle) -> ChurnRisk:
        sentiment = evidence.profile.recent_sentiment.casefold()
        score = 0
        if any(word in sentiment for word in _NEGATIVE):
            score += 2
        if evidence.profile.current_status.casefold() == "offline":
            score += 1
        if evidence.observation.related_ticket_count >= 3:
            score += 1
        if evidence.profile.lifetime_value_euro >= 10_000:
            score += 1
        if score >= 4:
            return ChurnRisk.HIGH
        if score >= 2:
            return ChurnRisk.MEDIUM
        return ChurnRisk.LOW

    @staticmethod
    def _diagnosis(evidence: EvidenceBundle) -> str:
        issue = evidence.observation.issue_type.value.replace("_", " ")
        return (
            f"{evidence.profile.name} shows {issue} friction with "
            f"{evidence.observation.related_ticket_count} relevant ticket(s); "
            f"current sentiment is {evidence.profile.recent_sentiment}"
        )
