"""Dependency composition root.

All concrete dependencies are constructed in one place. Business and orchestration code therefore
depend on interfaces rather than provider SDKs, and tests can substitute fakes without network calls.
"""

from __future__ import annotations

from app.agents.fallback import FallbackStrategist
from app.agents.heuristic_strategist import HeuristicStrategist
from app.agents.llm_strategist import LLMStrategist
from app.compliance.engine import ComplianceCritic
from app.config import Settings
from app.data.driver_repository import DriverRepository
from app.data.ledger_repository import LedgerRepository
from app.data.ticket_repository import TicketRepository
from app.diagnostics.extractor import ObservationExtractor
from app.integrations.incentive_adapter import IncentiveAdapter
from app.llm.openai_provider import OpenAIStructuredLLM
from app.memory.sqlite_store import SQLiteConversationStore
from app.orchestration.copilot import DriverRetentionCopilot
from app.rag.policy_store import PolicyStore


def build_copilot(settings: Settings) -> DriverRetentionCopilot:
    """Construct the application with either API-backed or offline strategy generation.

    Business intent:
        The selected Strategist may propose plans, but every plan always passes through
        the same deterministic Compliance Critic before it can be presented as compliant.

    Technical intent:
        Explicitly declare the union type so mypy accepts either concrete Strategist
        implementation without weakening type checking.
    """
    data = settings.data_dir
    drivers = DriverRepository(data / "driver_profiles.json")
    tickets = TicketRepository(data / "support_tickets.csv")
    ledger = LedgerRepository(data / "demo_retention_ledger.json")
    incentives = IncentiveAdapter.from_mock_file(data / "incentive_service_mock.py")
    policies = PolicyStore.from_path(data / "uk_driver_retention_recovery.md")
    extractor = ObservationExtractor(tickets)

    heuristic = HeuristicStrategist()
    strategist: FallbackStrategist | HeuristicStrategist

    if settings.strategist_provider == "openai":
        llm = OpenAIStructuredLLM(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_attempts=settings.llm_max_attempts,
            max_output_tokens=settings.llm_max_output_tokens,
        )
        strategist = FallbackStrategist(
            primary=LLMStrategist(llm),
            fallback=heuristic,
        )
    else:
        strategist = heuristic

    return DriverRetentionCopilot(
        drivers=drivers,
        tickets=tickets,
        ledger=ledger,
        incentives=incentives,
        policies=policies,
        extractor=extractor,
        strategist=strategist,
        # Financial and eligibility policy remains deterministic and authoritative even when the
        # proposal and revision steps are produced by a real LLM.
        critic=ComplianceCritic(),
        memory=SQLiteConversationStore(settings.state_db_path),
        max_revisions=settings.max_revisions,
    )
