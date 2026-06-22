import pytest
from app.data.driver_repository import DriverRepository
from app.exceptions import ToolUnavailableError
from app.integrations.incentive_adapter import IncentiveAdapter


class ExplodingService:
    def get_available_incentives(self, city: str, loyalty_tier: str, tenure_months: int):
        raise TimeoutError("upstream timed out")


class MalformedService:
    def get_available_incentives(self, city: str, loyalty_tier: str, tenure_months: int):
        return {"incentives": "not-a-list"}


def test_service_timeout_is_translated(data_dir) -> None:
    driver = DriverRepository(data_dir / "driver_profiles.json").get("D-LON-001")
    with pytest.raises(ToolUnavailableError, match="call failed"):
        IncentiveAdapter(ExplodingService()).available_for(driver)


def test_malformed_service_payload_is_rejected(data_dir) -> None:
    driver = DriverRepository(data_dir / "driver_profiles.json").get("D-LON-001")
    with pytest.raises(ToolUnavailableError, match="invalid payload"):
        IncentiveAdapter(MalformedService()).available_for(driver)
