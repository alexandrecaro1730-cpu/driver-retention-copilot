"""Defensive adapter around the supplied Incentive Service mock.

Business intent: catalogue eligibility is only a candidate signal. Policy validation remains a
separate authority because the supplied service exposes values that can exceed tier-specific caps.

Technical intent: isolate dynamic import and malformed service payload handling at the boundary.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

from app.domain.models import DriverProfile, Incentive
from app.exceptions import ToolUnavailableError


class IncentiveServiceProtocol(Protocol):
    def get_available_incentives(
        self, city: str, loyalty_tier: str, tenure_months: int
    ) -> dict[str, Any]: ...


def _load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("provided_incentive_service", path)
    if spec is None or spec.loader is None:
        raise ToolUnavailableError(f"Could not load incentive service from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IncentiveAdapter:
    def __init__(self, service: IncentiveServiceProtocol):
        self._service = service

    @classmethod
    def from_mock_file(cls, path: Path) -> IncentiveAdapter:
        module = _load_module(path)
        try:
            service = module.IncentiveService()
        except AttributeError as exc:
            raise ToolUnavailableError("Mock does not expose IncentiveService") from exc
        return cls(service)

    def available_for(self, driver: DriverProfile) -> list[Incentive]:
        try:
            payload = self._service.get_available_incentives(
                driver.city, driver.loyalty_tier.value, driver.tenure_months
            )
        except (
            Exception
        ) as exc:  # Boundary catches third-party failures and re-raises a safe error.
            raise ToolUnavailableError("Incentive service call failed") from exc

        if "error" in payload:
            raise ToolUnavailableError(str(payload["error"]))
        raw = payload.get("incentives")
        if not isinstance(raw, list):
            raise ToolUnavailableError("Incentive service returned an invalid payload")
        try:
            return [Incentive.model_validate(item) for item in raw]
        except Exception as exc:
            raise ToolUnavailableError("Incentive service returned malformed incentives") from exc
