"""Driver profile repository.

Business intent: driver identity must be resolved deterministically before any recommendation is
made. A mistaken identity could issue the wrong incentive or expose another driver's information.

Technical intent: keep file parsing behind a repository interface so JSON can later be replaced by a
service, warehouse, or MCP tool without changing orchestration code.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.models import DriverProfile
from app.exceptions import AmbiguousDriverError, DriverNotFoundError


class DriverRepository:
    def __init__(self, path: Path):
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._drivers = [DriverProfile.model_validate(item) for item in raw]
        self._by_id = {driver.driver_id.upper(): driver for driver in self._drivers}

    def get(self, driver_id: str) -> DriverProfile:
        try:
            return self._by_id[driver_id.upper()]
        except KeyError as exc:
            raise DriverNotFoundError(f"Driver {driver_id!r} was not found") from exc

    def search_by_name(self, query: str) -> DriverProfile:
        normalised = query.casefold().strip()
        matches = [driver for driver in self._drivers if normalised in driver.name.casefold()]
        if not matches:
            raise DriverNotFoundError(f"No driver matched name {query!r}")
        if len(matches) > 1:
            ids = ", ".join(driver.driver_id for driver in matches[:5])
            raise AmbiguousDriverError(f"Name {query!r} matched multiple drivers: {ids}")
        return matches[0]

    def all(self) -> list[DriverProfile]:
        return list(self._drivers)
