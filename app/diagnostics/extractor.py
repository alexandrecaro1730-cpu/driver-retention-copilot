"""Deterministic diagnostic extraction.

Business intent: policy eligibility must be based on explicit evidence, not an LLM's guess. The
extractor records exactly which measurable facts were found and leaves absent facts as ``None``.

Technical intent: regular expressions cover the constrained take-home data. In production, this
component would combine typed trip diagnostics, ticket labels, and an extraction model with source
spans.
"""

from __future__ import annotations

import re
from collections import Counter

from app.data.ticket_repository import TicketRepository
from app.domain.enums import IssueType
from app.domain.models import DriverObservation, DriverProfile, SupportTicket

_WAIT = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:min|mins|minutes)\b", re.I)
_DISTANCE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>km|kilometres?|miles?|mi)\b", re.I)
_QUEST = re.compile(r"(?P<done>\d+)\s*/\s*(?P<target>\d+)")
_OFFERS = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*offers?\s*(?:/|per)\s*hour", re.I)
_DRIVER_ID = re.compile(r"\bD-LON-\d{3}\b", re.I)

_KEYWORDS: list[tuple[IssueType, tuple[str, ...]]] = [
    (
        IssueType.AIRPORT_SHORT_FARE,
        ("airport", "heathrow", "gatwick", "lhr", "short fare", "queue"),
    ),
    (IssueType.TECHNICAL_GPS, ("gps", "geofence", "app crash", "app froze", "technical", "glitch")),
    (IssueType.QUEST, ("quest", "offers per hour", "low demand")),
    (IssueType.PAYMENT, ("payment", "paid", "balance", "processing", "earnings")),
    (IssueType.CANCELLATION, ("cancellation", "cancelled", "no-show")),
]


class ObservationExtractor:
    def __init__(self, tickets: TicketRepository):
        self._ticket_repository = tickets

    @staticmethod
    def extract_driver_id(message: str) -> str | None:
        match = _DRIVER_ID.search(message)
        return match.group(0).upper() if match else None

    @staticmethod
    def infer_issue_type(
        message: str, tickets: list[SupportTicket], previous: IssueType
    ) -> IssueType:
        haystack = message.casefold()
        for issue_type, keywords in _KEYWORDS:
            if any(keyword in haystack for keyword in keywords):
                return issue_type
        if previous is not IssueType.UNKNOWN:
            return previous
        if tickets:
            category = Counter(ticket.category.casefold() for ticket in tickets).most_common(1)[0][
                0
            ]
            return {
                "airport": IssueType.AIRPORT_SHORT_FARE,
                "technical": IssueType.TECHNICAL_GPS,
                "quest": IssueType.QUEST,
                "payment": IssueType.PAYMENT,
                "cancellation": IssueType.CANCELLATION,
                "general": IssueType.GENERAL,
            }.get(category, IssueType.UNKNOWN)
        return IssueType.UNKNOWN

    @staticmethod
    def _extract_wait(texts: list[str]) -> float | None:
        values = [float(m.group("value")) for text in texts for m in _WAIT.finditer(text)]
        return max(values) if values else None

    @staticmethod
    def _extract_distance(texts: list[str]) -> float | None:
        values: list[float] = []
        for text in texts:
            for match in _DISTANCE.finditer(text):
                value = float(match.group("value"))
                unit = match.group("unit").casefold()
                values.append(value * 1.609344 if unit in {"mile", "miles", "mi"} else value)
        return min(values) if values else None

    @staticmethod
    def _extract_quest_ratio(texts: list[str]) -> float | None:
        values: list[float] = []
        for text in texts:
            for match in _QUEST.finditer(text):
                target = int(match.group("target"))
                if target:
                    values.append(int(match.group("done")) / target)
        return max(values) if values else None

    @staticmethod
    def _extract_offers_per_hour(texts: list[str]) -> float | None:
        values = [float(m.group("value")) for text in texts for m in _OFFERS.finditer(text)]
        return min(values) if values else None

    def extract(
        self,
        message: str,
        profile: DriverProfile,
        tickets: list[SupportTicket],
        *,
        previous_issue_type: IssueType = IssueType.UNKNOWN,
    ) -> DriverObservation:
        issue_type = self.infer_issue_type(message, tickets, previous_issue_type)
        relevant = [ticket for ticket in tickets if self._ticket_matches_issue(ticket, issue_type)]
        texts = [message, *(ticket.message for ticket in relevant)]
        wait = self._extract_wait(texts)
        distance = self._extract_distance(texts)
        quest_ratio = self._extract_quest_ratio(texts)
        offers = self._extract_offers_per_hour(texts)
        technical_count = self._ticket_repository.count_recent(
            profile.driver_id, days=7, category="Technical"
        )
        systemic = bool(
            re.search(r"\b(?:multi[- ]day|systemic failure|citywide outage)\b", message, re.I)
        )
        policy_question = bool(
            re.search(r"\b(?:policy|cap|eligible|eligibility|rule|tier)\b", message, re.I)
        )
        facts: list[str] = []
        if wait is not None:
            facts.append(f"Maximum evidenced wait: {wait:g} minutes")
        if distance is not None:
            facts.append(f"Minimum evidenced trip distance: {distance:.2f} km")
        if quest_ratio is not None:
            facts.append(f"Quest completion: {quest_ratio:.1%}")
        if offers is not None:
            facts.append(f"Documented demand: {offers:g} offers/hour")
        if technical_count:
            facts.append(f"Technical tickets in seven-day data window: {technical_count}")

        return DriverObservation(
            issue_type=issue_type,
            wait_minutes=wait,
            trip_distance_km=distance,
            quest_completion_ratio=quest_ratio,
            offers_per_hour=offers,
            multi_day_systemic_failure=systemic,
            policy_question=policy_question,
            related_ticket_count=len(relevant),
            recurring_technical_tickets_7d=technical_count,
            extracted_facts=facts,
        )

    @staticmethod
    def _ticket_matches_issue(ticket: SupportTicket, issue_type: IssueType) -> bool:
        expected = {
            IssueType.AIRPORT_SHORT_FARE: "airport",
            IssueType.TECHNICAL_GPS: "technical",
            IssueType.QUEST: "quest",
            IssueType.PAYMENT: "payment",
            IssueType.CANCELLATION: "cancellation",
            IssueType.GENERAL: "general",
        }.get(issue_type)
        return expected is None or ticket.category.casefold() == expected
