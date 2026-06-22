from app.agents.heuristic_strategist import HeuristicStrategist
from app.compliance.engine import ComplianceCritic
from app.domain.enums import ActionType, Decision, IssueType, LoyaltyTier

from tests.factories import action, evidence, plan


def test_strategist_proposes_gold_airport_recovery() -> None:
    result = HeuristicStrategist().propose(evidence())
    credit = next(item for item in result.actions if item.incentive_id == "INC-001")
    assert credit.value_gbp == 25
    assert any(item.incentive_id == "Q-103" for item in result.actions)


def test_strategist_uses_silver_cap_and_marks_parameterisation() -> None:
    result = HeuristicStrategist().propose(evidence(tier=LoyaltyTier.SILVER))
    credit = next(item for item in result.actions if item.incentive_id == "INC-001")
    assert credit.value_gbp == 15
    assert credit.requires_human_approval is True


def test_strategist_does_not_invent_airport_credit_without_distance() -> None:
    result = HeuristicStrategist().propose(evidence(distance=None))
    assert all(item.value_gbp == 0 for item in result.actions)
    assert "Exact trip distance" in result.missing_data


def test_strategist_proposes_technical_credit_and_priority_support() -> None:
    result = HeuristicStrategist().propose(
        evidence(issue=IssueType.TECHNICAL_GPS, recurring_technical=3)
    )
    assert {item.incentive_id for item in result.actions} >= {"INC-003", "INC-004"}


def test_strategist_prefers_new_starter_shield() -> None:
    result = HeuristicStrategist().propose(evidence(issue=IssueType.NEW_STARTER, tenure=1))
    shield = next(item for item in result.actions if item.incentive_id == "INC-006")
    assert shield.action_type is ActionType.DISCOUNT
    assert shield.value_percent == 50


def test_reviser_repairs_premium_airport_plan() -> None:
    strategist = HeuristicStrategist()
    bad = plan(action(incentive_id="INC-002", value=50))
    ev = evidence()
    critique = ComplianceCritic().validate(bad, ev)
    revised = strategist.revise(bad, critique, ev)
    assert revised.revision == 1
    assert revised.actions[0].incentive_id == "INC-001"
    assert revised.actions[0].value_gbp == 25
    assert ComplianceCritic().validate(revised, ev).decision is Decision.APPROVE


def test_reviser_removes_action_with_missing_evidence() -> None:
    strategist = HeuristicStrategist()
    bad = plan(action(value=25))
    ev = evidence(wait=None, distance=None)
    revised = strategist.revise(bad, ComplianceCritic().validate(bad, ev), ev)
    assert all(item.value_gbp == 0 for item in revised.actions)
