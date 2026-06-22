"""Retention ledger snapshot repository.

The supplied assignment package has no real issuance ledger. This repository therefore treats
missing records as unknown rather than zero. That fail-closed distinction is central to preventing
monthly-cap and credit-stacking violations.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.models import LedgerSnapshot


class LedgerRepository:
    def __init__(self, path: Path | None):
        self._path = path
        self._drivers: dict[str, dict[str, float | int]] = {}
        if path is not None and path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            self._drivers = payload.get("drivers", {})

    def get(self, driver_id: str) -> LedgerSnapshot:
        row = self._drivers.get(driver_id)
        if row is None:
            return LedgerSnapshot(driver_id=driver_id, source="unavailable")
        return LedgerSnapshot(
            driver_id=driver_id,
            month_to_date_gbp=float(row["month_to_date_gbp"]),
            immediate_credits_last_24h=int(row["immediate_credits_last_24h"]),
            source=str(self._path),
        )
