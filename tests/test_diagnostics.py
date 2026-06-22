from pathlib import Path

from app.data.driver_repository import DriverRepository
from app.data.ticket_repository import TicketRepository
from app.diagnostics.extractor import ObservationExtractor
from app.domain.enums import IssueType


def _components(data_dir: Path):
    drivers = DriverRepository(data_dir / "driver_profiles.json")
    tickets = TicketRepository(data_dir / "support_tickets.csv")
    return drivers, tickets, ObservationExtractor(tickets)


def test_extracts_driver_id() -> None:
    assert ObservationExtractor.extract_driver_id("Please check d-lon-001") == "D-LON-001"


def test_extracts_wait_and_km_from_message(data_dir: Path) -> None:
    drivers, tickets, extractor = _components(data_dir)
    profile = drivers.get("D-LON-001")
    result = extractor.extract(
        "Airport queue was 135 minutes and the trip was 1.5km",
        profile,
        tickets.for_driver(profile.driver_id),
    )
    assert result.wait_minutes == 135
    assert result.trip_distance_km == 1.5
    assert result.issue_type is IssueType.AIRPORT_SHORT_FARE


def test_converts_miles_to_km(data_dir: Path) -> None:
    drivers, tickets, extractor = _components(data_dir)
    profile = drivers.get("D-LON-012")
    result = extractor.extract(
        "Gatwick wait 110 mins and a 2 mile trip",
        profile,
        tickets.for_driver(profile.driver_id),
    )
    assert result.trip_distance_km == 2 * 1.609344


def test_extracts_quest_ratio_and_offers(data_dir: Path) -> None:
    drivers, tickets, extractor = _components(data_dir)
    profile = drivers.get("D-LON-004")
    result = extractor.extract(
        "I completed 48/50 and diagnostics show 1.2 offers per hour",
        profile,
        tickets.for_driver(profile.driver_id),
    )
    assert result.quest_completion_ratio == 0.96
    assert result.offers_per_hour == 1.2
    assert result.issue_type is IssueType.QUEST


def test_systemic_failure_requires_explicit_language(data_dir: Path) -> None:
    drivers, tickets, extractor = _components(data_dir)
    profile = drivers.get("D-LON-001")
    normal = extractor.extract(
        "This happened repeatedly", profile, tickets.for_driver(profile.driver_id)
    )
    systemic = extractor.extract(
        "This is a documented multi-day systemic failure",
        profile,
        tickets.for_driver(profile.driver_id),
    )
    assert normal.multi_day_systemic_failure is False
    assert systemic.multi_day_systemic_failure is True


def test_previous_issue_is_used_for_follow_up(data_dir: Path) -> None:
    drivers, tickets, extractor = _components(data_dir)
    profile = drivers.get("D-LON-001")
    result = extractor.extract(
        "What is the policy for her tier?",
        profile,
        tickets.for_driver(profile.driver_id),
        previous_issue_type=IssueType.AIRPORT_SHORT_FARE,
    )
    assert result.issue_type is IssueType.AIRPORT_SHORT_FARE


def test_recurring_technical_count_uses_seven_day_window(data_dir: Path) -> None:
    drivers, tickets, extractor = _components(data_dir)
    profile = drivers.get("D-LON-003")
    result = extractor.extract(
        "GPS geofence glitch", profile, tickets.for_driver(profile.driver_id)
    )
    assert result.recurring_technical_tickets_7d == 2


def test_missing_measurements_remain_none(data_dir: Path) -> None:
    drivers, _tickets, extractor = _components(data_dir)
    profile = drivers.get("D-LON-008")
    result = extractor.extract("General account question", profile, [])
    assert result.wait_minutes is None
    assert result.trip_distance_km is None
