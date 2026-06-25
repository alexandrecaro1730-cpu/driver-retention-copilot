from app.agents.fallback import FallbackStrategist
from app.agents.heuristic_strategist import HeuristicStrategist
from app.compliance.engine import ComplianceCritic
from app.exceptions import ToolUnavailableError

from tests.factories import action, evidence, plan


class UnavailableStrategist:
    def propose(self, evidence):
        raise ToolUnavailableError("rate limited")

    def revise(self, plan, critique, evidence):
        raise ToolUnavailableError("rate limited")


def test_unavailable_primary_uses_deterministic_fallback() -> None:
    strategist = FallbackStrategist(UnavailableStrategist(), HeuristicStrategist())
    result = strategist.propose(evidence())
    assert result.driver_id == "D-LON-001"
    assert any(action.incentive_id == "INC-001" for action in result.actions)


def test_unavailable_primary_revision_uses_deterministic_fallback() -> None:
    strategist = FallbackStrategist(UnavailableStrategist(), HeuristicStrategist())
    bad = plan(action(incentive_id="INC-002", value=50))
    ev = evidence()
    critique = ComplianceCritic().validate(bad, ev)

    result = strategist.revise(bad, critique, ev)

    assert result.revision == 1
    assert result.actions[0].incentive_id == "INC-001"
    assert result.actions[0].value_gbp == 25
