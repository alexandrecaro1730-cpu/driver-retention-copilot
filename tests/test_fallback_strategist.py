from app.agents.fallback import FallbackStrategist
from app.agents.heuristic_strategist import HeuristicStrategist
from app.exceptions import ToolUnavailableError

from tests.factories import evidence


class UnavailableStrategist:
    def propose(self, evidence):
        raise ToolUnavailableError("rate limited")

    def revise(self, plan, critique, evidence):
        raise AssertionError("primary repair should not be used")


def test_unavailable_primary_uses_deterministic_fallback() -> None:
    strategist = FallbackStrategist(UnavailableStrategist(), HeuristicStrategist())
    result = strategist.propose(evidence())
    assert result.driver_id == "D-LON-001"
    assert any(action.incentive_id == "INC-001" for action in result.actions)
