"""Support ticket retrieval with exact driver filtering and recency helpers."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

from app.domain.models import SupportTicket


class TicketRepository:
    def __init__(self, path: Path):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            self._tickets = [SupportTicket.model_validate(row) for row in csv.DictReader(handle)]

    def for_driver(self, driver_id: str, *, limit: int | None = None) -> list[SupportTicket]:
        tickets = [t for t in self._tickets if t.driver_id.upper() == driver_id.upper()]
        tickets.sort(key=lambda t: t.timestamp, reverse=True)
        return tickets[:limit] if limit is not None else tickets

    def recent_for_driver(
        self,
        driver_id: str,
        *,
        days: int,
        category: str | None = None,
        reference_time: datetime | None = None,
    ) -> list[SupportTicket]:
        candidates = self.for_driver(driver_id)
        if not candidates:
            return []
        # Dataset timestamps are historical. Anchoring to the driver's latest ticket makes tests and
        # offline evaluation reproducible; callers can inject wall-clock time in production.
        anchor = reference_time or max(ticket.timestamp for ticket in candidates)
        threshold = anchor - timedelta(days=days)
        return [
            ticket
            for ticket in candidates
            if ticket.timestamp >= threshold
            and (category is None or ticket.category.casefold() == category.casefold())
        ]

    def count_recent(
        self,
        driver_id: str,
        *,
        days: int,
        category: str,
        reference_time: datetime | None = None,
    ) -> int:
        return len(
            self.recent_for_driver(
                driver_id,
                days=days,
                category=category,
                reference_time=reference_time,
            )
        )
