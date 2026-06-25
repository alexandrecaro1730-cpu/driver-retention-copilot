import pytest
from app.domain.enums import ActionType
from app.domain.models import ProposedAction, RetentionPlan
from pydantic import ValidationError


def test_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ProposedAction(
            action_type=ActionType.CREDIT,
            name="x",
            category="Airport",
            rationale="x",
            invented_field=True,
        )


def test_plan_counts_all_positive_gbp_regardless_of_model_flag() -> None:
    plan = RetentionPlan(
        driver_id="D-LON-001",
        diagnosis="x",
        churn_risk="low",
        actions=[
            ProposedAction(
                action_type=ActionType.CREDIT,
                name="credit",
                category="Airport",
                value_gbp=10,
                rationale="x",
            ),
            ProposedAction(
                action_type=ActionType.QUEST,
                name="zero-value access",
                category="Engagement",
                value_gbp=50,
                counts_toward_monthly_cap=False,
                rationale="x",
            ),
        ],
    )
    assert plan.total_gbp_value == 60


def test_negative_money_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProposedAction(
            action_type=ActionType.CREDIT,
            name="bad",
            category="Airport",
            value_gbp=-1,
            rationale="x",
        )
