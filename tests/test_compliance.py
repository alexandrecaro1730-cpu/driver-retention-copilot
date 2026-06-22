import pytest
from app.compliance.engine import ComplianceCritic
from app.domain.enums import ActionType, Decision, IssueType, LoyaltyTier

from tests.factories import action, evidence, plan


@pytest.fixture()
def critic() -> ComplianceCritic:
    return ComplianceCritic()


def rule_ids(result) -> set[str]:
    return {item.rule_id for item in result.violations}


def test_compliant_gold_airport_plan_is_approved(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action(value=25)), evidence())
    assert result.decision is Decision.APPROVE


def test_gold_airport_cap_rejects_50(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action(incentive_id="INC-002", value=50)), evidence())
    assert result.decision is Decision.REJECT
    assert {"B.1_TIER_CAP", "B.1_INC002_RESTRICTED"} <= rule_ids(result)


def test_inc002_allowed_only_when_systemic_but_still_subject_to_cap(
    critic: ComplianceCritic,
) -> None:
    result = critic.validate(
        plan(action(incentive_id="INC-002", value=25)), evidence(systemic=True)
    )
    assert "B.1_INC002_RESTRICTED" not in rule_ids(result)


def test_silver_airport_cap_is_15_and_service_gap_is_conditional(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action(value=15)), evidence(tier=LoyaltyTier.SILVER))
    assert result.decision is Decision.CONDITIONAL_APPROVE
    assert "SERVICE_PARAMETERISATION_REQUIRED" in rule_ids(result)


def test_silver_25_is_rejected(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action(value=25)), evidence(tier=LoyaltyTier.SILVER))
    assert result.decision is Decision.REJECT
    assert "B.1_TIER_CAP" in rule_ids(result)


def test_exactly_90_minutes_does_not_qualify(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action()), evidence(wait=90))
    assert "B.1_WAIT_THRESHOLD" in rule_ids(result)


def test_exactly_3km_does_not_qualify(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action()), evidence(distance=3))
    assert "B.1_DISTANCE_THRESHOLD" in rule_ids(result)


def test_missing_airport_measurements_reject_money(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action()), evidence(wait=None, distance=None))
    assert result.decision is Decision.REJECT
    assert "B.1_MISSING_EVIDENCE" in rule_ids(result)


def test_monthly_cap_rejects_projected_overspend(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action(value=25)), evidence(mtd=140))
    assert "A.1_MONTHLY_CAP" in rule_ids(result)


def test_unknown_monthly_ledger_is_conditional(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action(value=25)), evidence(mtd=None, credits=0))
    assert result.decision is Decision.CONDITIONAL_APPROVE
    assert "A.1_LEDGER_UNKNOWN" in rule_ids(result)


def test_third_credit_requires_escalation(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action(value=10)), evidence(credits=2))
    assert result.decision is Decision.ESCALATE
    assert "A.2_CREDIT_STACKING" in rule_ids(result)


def test_unknown_credit_history_is_conditional(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action(value=10)), evidence(credits=None))
    assert result.decision is Decision.CONDITIONAL_APPROVE


def test_bronze_churn_goodwill_is_rejected(critic: ComplianceCritic) -> None:
    result = critic.validate(
        plan(action(incentive_id="INC-007", category="Churn", value=75)),
        evidence(tier=LoyaltyTier.BRONZE),
    )
    assert "A.3_CHURN_TIER" in rule_ids(result)


def test_technical_cap_is_10(critic: ComplianceCritic) -> None:
    result = critic.validate(
        plan(action(incentive_id="INC-003", category="Technical", value=20)),
        evidence(issue=IssueType.TECHNICAL_GPS),
    )
    assert "B.2_TECHNICAL_CAP" in rule_ids(result)


def test_priority_support_requires_more_than_two_tickets(critic: ComplianceCritic) -> None:
    support = action(
        incentive_id="INC-004",
        category="Technical",
        value=0,
        immediate=False,
        action_type=ActionType.SUPPORT,
    )
    rejected = critic.validate(
        plan(support), evidence(issue=IssueType.TECHNICAL_GPS, recurring_technical=2)
    )
    approved = critic.validate(
        plan(support), evidence(issue=IssueType.TECHNICAL_GPS, recurring_technical=3)
    )
    assert "B.2_PRIORITY_SUPPORT_THRESHOLD" in rule_ids(rejected)
    assert approved.decision is Decision.APPROVE


def test_quest_requires_both_diagnostics(critic: ComplianceCritic) -> None:
    quest = action(incentive_id="POLICY-QUEST-20", category="Quest", value=20)
    result = critic.validate(
        plan(quest), evidence(issue=IssueType.QUEST, quest_ratio=0.96, offers=None)
    )
    assert "B.4_QUEST_ELIGIBILITY" in rule_ids(result)


def test_quest_goodwill_cap_is_20(critic: ComplianceCritic) -> None:
    quest = action(incentive_id="POLICY-QUEST-20", category="Quest", value=25)
    result = critic.validate(
        plan(quest), evidence(issue=IssueType.QUEST, quest_ratio=0.96, offers=1.2)
    )
    assert "B.4_QUEST_CAP" in rule_ids(result)


def test_quest_goodwill_is_approved_with_complete_evidence(critic: ComplianceCritic) -> None:
    quest = action(incentive_id="POLICY-QUEST-20", category="Quest", value=20)
    result = critic.validate(
        plan(quest), evidence(issue=IssueType.QUEST, quest_ratio=0.96, offers=1.2)
    )
    assert result.decision is Decision.APPROVE


def test_unavailable_incentive_is_rejected(critic: ComplianceCritic) -> None:
    result = critic.validate(plan(action(incentive_id="INC-999")), evidence())
    assert "TOOL_INCENTIVE_NOT_AVAILABLE" in rule_ids(result)
