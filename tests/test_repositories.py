from pathlib import Path

import pytest
from app.data.driver_repository import DriverRepository
from app.data.ledger_repository import LedgerRepository
from app.data.ticket_repository import TicketRepository
from app.domain.enums import LoyaltyTier
from app.exceptions import DriverNotFoundError
from app.integrations.incentive_adapter import IncentiveAdapter


def test_driver_repository_loads_100_profiles(data_dir: Path) -> None:
    repo = DriverRepository(data_dir / "driver_profiles.json")
    assert len(repo.all()) == 100


def test_driver_repository_get_is_case_insensitive(data_dir: Path) -> None:
    repo = DriverRepository(data_dir / "driver_profiles.json")
    assert repo.get("d-lon-001").name == "Maria S."


def test_driver_repository_name_search(data_dir: Path) -> None:
    repo = DriverRepository(data_dir / "driver_profiles.json")
    assert repo.search_by_name("Maria").driver_id == "D-LON-001"


def test_driver_repository_missing_driver(data_dir: Path) -> None:
    repo = DriverRepository(data_dir / "driver_profiles.json")
    with pytest.raises(DriverNotFoundError):
        repo.get("D-LON-999")


def test_ticket_repository_orders_latest_first(data_dir: Path) -> None:
    repo = TicketRepository(data_dir / "support_tickets.csv")
    tickets = repo.for_driver("D-LON-001")
    assert tickets[0].ticket_id == "T-1099"
    assert {ticket.ticket_id for ticket in tickets} >= {"T-1001", "T-1007"}


def test_ticket_repository_recent_category_count(data_dir: Path) -> None:
    repo = TicketRepository(data_dir / "support_tickets.csv")
    assert repo.count_recent("D-LON-003", days=7, category="Technical") == 2


def test_missing_ledger_is_unknown(tmp_path: Path) -> None:
    snapshot = LedgerRepository(tmp_path / "missing.json").get("D-LON-900")
    assert snapshot.month_to_date_gbp is None
    assert snapshot.complete is False


def test_demo_ledger_is_explicitly_loaded(data_dir: Path) -> None:
    snapshot = LedgerRepository(data_dir / "demo_retention_ledger.json").get("D-LON-001")
    assert snapshot.month_to_date_gbp == 0
    assert snapshot.immediate_credits_last_24h == 0


def test_incentive_adapter_exposes_gold_catalogue(data_dir: Path) -> None:
    drivers = DriverRepository(data_dir / "driver_profiles.json")
    adapter = IncentiveAdapter.from_mock_file(data_dir / "incentive_service_mock.py")
    ids = {item.id for item in adapter.available_for(drivers.get("D-LON-001"))}
    assert {"INC-001", "INC-002", "Q-103"} <= ids


def test_incentive_adapter_filters_gold_only_items_for_bronze(data_dir: Path) -> None:
    drivers = DriverRepository(data_dir / "driver_profiles.json")
    adapter = IncentiveAdapter.from_mock_file(data_dir / "incentive_service_mock.py")
    items = adapter.available_for(drivers.get("D-LON-002"))
    assert all(item.min_tier is LoyaltyTier.BRONZE for item in items)
