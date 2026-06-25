from __future__ import annotations

from typing import TypeVar

import pytest
from app.agents.llm_strategist import LLMStrategist
from app.compliance.engine import ComplianceCritic
from app.domain.models import RetentionPlan
from app.exceptions import ToolUnavailableError
from pydantic import BaseModel

from tests.factories import action, evidence, plan

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class QueueLLM:
    provider_name = "fake"
    model_name = "fake-structured-model"

    def __init__(self, outputs: list[BaseModel]) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, object]] = []

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseT],
    ) -> ResponseT:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_model": response_model,
            }
        )
        output = self.outputs.pop(0)
        assert isinstance(output, response_model)
        return output


def test_llm_strategist_returns_typed_initial_plan() -> None:
    expected = plan(action(value=25))
    llm = QueueLLM([expected])

    result = LLMStrategist(llm).propose(evidence())

    assert result == expected
    assert llm.calls[0]["response_model"] is RetentionPlan
    assert "untrusted evidence" in str(llm.calls[0]["user_prompt"])


def test_llm_strategist_uses_critic_feedback_for_revision() -> None:
    bad = plan(action(incentive_id="INC-002", value=50))
    ev = evidence()
    critique = ComplianceCritic().validate(bad, ev)
    corrected = plan(action(incentive_id="INC-001", value=25))
    corrected.revision = 1
    llm = QueueLLM([corrected])

    result = LLMStrategist(llm).revise(bad, critique, ev)

    assert result.revision == 1
    assert result.actions[0].value_gbp == 25
    assert "critic_result" in str(llm.calls[0]["user_prompt"])


def test_llm_strategist_rejects_wrong_driver_identity() -> None:
    wrong = plan(action(value=25))
    wrong.driver_id = "D-LON-999"

    with pytest.raises(ToolUnavailableError, match="wrong driver"):
        LLMStrategist(QueueLLM([wrong])).propose(evidence())


def test_llm_strategist_rejects_invalid_revision_number() -> None:
    bad = plan(action(incentive_id="INC-002", value=50))
    ev = evidence()
    critique = ComplianceCritic().validate(bad, ev)
    invalid = plan(action(incentive_id="INC-001", value=25))
    invalid.revision = 3

    with pytest.raises(ToolUnavailableError, match="invalid revision"):
        LLMStrategist(QueueLLM([invalid])).revise(bad, critique, ev)
