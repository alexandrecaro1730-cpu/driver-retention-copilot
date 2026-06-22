"""Dependency composition root.

All concrete dependencies are constructed in one place. This keeps business code free from hidden
singletons and makes integration tests able to substitute temporary paths or fake services.
"""

from __future__ import annotations

from app.agents.fallback import FallbackStrategist
from app.agents.heuristic_strategist import HeuristicStrategist
from app.agents.openai_strategist import OpenAIStrategist
from app.compliance.engine import ComplianceCritic
from app.config import Settings
from app.data.driver_repository import DriverRepository
from app.data.ledger_repository import LedgerRepository
from app.data.ticket_repository import TicketRepository
from app.diagnostics.extractor import ObservationExtractor
from app.integrations.incentive_adapter import IncentiveAdapter
from app.memory.sqlite_store import SQLiteConversationStore
from app.orchestration.copilot import DriverRetentionCopilot
from app.rag.policy_store import PolicyStore


def build_copilot(settings: Settings) -> DriverRetentionCopilot:
    data = settings.data_dir
    drivers = DriverRepository(data / "driver_profiles.json")
    tickets = TicketRepository(data / "support_tickets.csv")
    ledger = LedgerRepository(data / "demo_retention_ledger.json")
    incentives = IncentiveAdapter.from_mock_file(data / "incentive_service_mock.py")
    policies = PolicyStore.from_path(data / "uk_driver_retention_recovery.md")
    extractor = ObservationExtractor(tickets)
    heuristic = HeuristicStrategist()
    strategist = (
        FallbackStrategist(
            primary=OpenAIStrategist(api_key=settings.openai_api_key, model=settings.openai_model),
            fallback=heuristic,
        )
        if settings.strategist_provider == "openai"
        else heuristic
    )
    return DriverRetentionCopilot(
        drivers=drivers,
        tickets=tickets,
        ledger=ledger,
        incentives=incentives,
        policies=policies,
        extractor=extractor,
        strategist=strategist,
        critic=ComplianceCritic(),
        memory=SQLiteConversationStore(settings.state_db_path),
        max_revisions=settings.max_revisions,
    )
