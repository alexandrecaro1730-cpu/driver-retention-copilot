from app.domain.enums import ActionType, ChurnRisk, Decision
from app.domain.models import ChatRequest, ProposedAction, RetentionPlan
from app.exceptions import DriverNotFoundError


def _unsafe_maria_plan() -> RetentionPlan:
    return RetentionPlan(
        driver_id="D-LON-001",
        diagnosis="Repeated airport short fare",
        churn_risk=ChurnRisk.HIGH,
        actions=[
            ProposedAction(
                action_type=ActionType.CREDIT,
                name="Premium Airport Short Fare Recovery",
                incentive_id="INC-002",
                category="Airport",
                value_gbp=50,
                immediate_credit=True,
                rationale="Over-generous first attempt",
                evidence_ids=["T-1001"],
                policy_chunk_ids=["B.1"],
            )
        ],
    )


def test_end_to_end_maria_plan_is_approved(copilot) -> None:
    result = copilot.run(
        ChatRequest(
            driver_id="D-LON-001",
            message="Maria waited 135 minutes for a 1.5km airport trip. What should we do?",
        )
    )
    assert result.critic.decision is Decision.APPROVE
    assert result.plan.total_gbp_value == 25
    assert "Decision: APPROVE" in result.manager_message


def test_self_correction_trace_rejects_then_repairs(copilot) -> None:
    result = copilot.run(
        ChatRequest(
            driver_id="D-LON-001",
            message="Maria waited 135 minutes for a 1.5km airport trip; repeated issue.",
            initial_plan_override=_unsafe_maria_plan(),
        )
    )
    critic_outcomes = [event.outcome for event in result.trace if event.node == "critic"]
    assert critic_outcomes == ["REJECT", "APPROVE"]
    assert result.plan.revision == 1
    assert result.plan.actions[0].value_gbp == 25


def test_multi_turn_state_reuses_driver_and_issue(copilot) -> None:
    first = copilot.run(
        ChatRequest(
            driver_id="D-LON-001",
            message="Maria waited 135 minutes for a 1.5km airport trip.",
        )
    )
    second = copilot.run(
        ChatRequest(
            conversation_id=first.conversation_id,
            message="What is the policy for her tier?",
        )
    )
    assert second.driver.driver_id == "D-LON-001"
    assert second.observation.issue_type.value == "airport_short_fare"
    assert second.plan.total_gbp_value == 0
    assert second.plan.actions[0].action_type is ActionType.COMMUNICATION


def test_name_resolution_works_on_first_turn(copilot) -> None:
    result = copilot.run(
        ChatRequest(message="Maria had a 135 minute airport wait for a 1.5km trip")
    )
    assert result.driver.driver_id == "D-LON-001"


def test_first_turn_without_driver_fails(copilot) -> None:
    try:
        copilot.run(ChatRequest(message="What should we do about this complaint?"))
    except DriverNotFoundError as exc:
        assert "driver ID" in str(exc)
    else:
        raise AssertionError("Expected DriverNotFoundError")


def test_unknown_ledger_produces_conditional_approval(copilot) -> None:
    result = copilot.run(
        ChatRequest(
            driver_id="D-LON-012",
            message="Jessica waited 110 minutes for a 1.5km airport trip.",
        )
    )
    assert result.critic.decision is Decision.CONDITIONAL_APPROVE
