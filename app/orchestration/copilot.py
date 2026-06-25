"""Bounded Strategist/Critic state machine.

Business intent
---------------
A manager receives one accountable recommendation, not an unconstrained agent conversation. The
workflow gathers authoritative evidence first, permits only a small number of revisions, and never
executes an incentive.

Technical intent
----------------
The explicit loop is intentionally simpler than a general agent framework. Components are ordinary
Python objects, state is typed, and tool/agent transitions are recorded as an inspectable audit trace.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.agents.base import Strategist
from app.compliance.engine import ComplianceCritic
from app.data.driver_repository import DriverRepository
from app.data.ledger_repository import LedgerRepository
from app.data.ticket_repository import TicketRepository
from app.diagnostics.extractor import ObservationExtractor
from app.domain.enums import Decision
from app.domain.models import (
    ChatRequest,
    ChatResponse,
    ConversationState,
    CriticResult,
    DriverProfile,
    EvidenceBundle,
    RetentionPlan,
    TraceEvent,
)
from app.exceptions import DriverNotFoundError
from app.integrations.incentive_adapter import IncentiveAdapter
from app.memory.sqlite_store import SQLiteConversationStore
from app.rag.policy_store import PolicyStore

LOGGER = logging.getLogger(__name__)


class DriverRetentionCopilot:
    def __init__(
        self,
        *,
        drivers: DriverRepository,
        tickets: TicketRepository,
        ledger: LedgerRepository,
        incentives: IncentiveAdapter,
        policies: PolicyStore,
        extractor: ObservationExtractor,
        strategist: Strategist,
        critic: ComplianceCritic,
        memory: SQLiteConversationStore,
        max_revisions: int = 2,
    ):
        self._drivers = drivers
        self._tickets = tickets
        self._ledger = ledger
        self._incentives = incentives
        self._policies = policies
        self._extractor = extractor
        self._strategist = strategist
        self._critic = critic
        self._memory = memory
        self._max_revisions = max_revisions

    def run(self, request: ChatRequest) -> ChatResponse:
        conversation_id = request.conversation_id or str(uuid.uuid4())
        state = self._memory.load(conversation_id) or ConversationState(
            conversation_id=conversation_id
        )
        trace: list[TraceEvent] = []

        profile = self._resolve_driver(request, state)
        self._record(
            trace,
            "context_resolver",
            "resolved",
            {"driver_id": profile.driver_id, "reused_memory": request.driver_id is None},
        )
        self._record(
            trace,
            "tool.driver_repository",
            "success",
            {"driver_id": profile.driver_id, "loyalty_tier": profile.loyalty_tier.value},
        )

        tickets = self._tickets.for_driver(profile.driver_id, limit=20)
        self._record(
            trace,
            "tool.ticket_repository",
            "success",
            {"ticket_ids": [ticket.ticket_id for ticket in tickets]},
        )

        observation = self._extractor.extract(
            request.message,
            profile,
            tickets,
            previous_issue_type=state.last_issue_type,
        )
        self._record(
            trace,
            "diagnostic_extractor",
            "classified",
            observation.model_dump(mode="json"),
        )

        incentives = self._incentives.available_for(profile)
        self._record(
            trace,
            "tool.incentive_service",
            "success",
            {"incentive_ids": [item.id for item in incentives]},
        )

        policy_chunks = self._policies.retrieve(
            request.message,
            issue_type=observation.issue_type,
            tier=profile.loyalty_tier,
        )
        self._record(
            trace,
            "tool.policy_rag",
            "success",
            {
                "policy_chunks": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "source_document": chunk.source_document,
                        "source_page": chunk.source_page,
                    }
                    for chunk in policy_chunks
                ]
            },
        )

        ledger = self._ledger.get(profile.driver_id)
        self._record(
            trace,
            "tool.retention_ledger",
            "success" if ledger.complete else "incomplete",
            {
                "month_to_date_gbp": ledger.month_to_date_gbp,
                "immediate_credits_last_24h": ledger.immediate_credits_last_24h,
            },
        )

        evidence = EvidenceBundle(
            query=request.message,
            profile=profile,
            tickets=tickets,
            incentives=incentives,
            policy_chunks=policy_chunks,
            observation=observation,
            ledger=ledger,
        )
        self._record(
            trace,
            "evidence_bundle",
            "assembled",
            {
                "driver_id": profile.driver_id,
                "ticket_count": len(tickets),
                "incentive_count": len(incentives),
                "policy_chunk_ids": [chunk.chunk_id for chunk in policy_chunks],
                "ledger_complete": ledger.complete,
            },
        )

        plan = request.initial_plan_override or self._strategist.propose(evidence)
        self._record(trace, "strategist", "proposed", plan.model_dump(mode="json"))

        revisions = 0
        while True:
            critique = self._critic.validate(plan, evidence)
            self._record(
                trace,
                "compliance_critic",
                critique.decision.value,
                critique.model_dump(mode="json"),
            )
            # Keep the legacy node for existing trace consumers while the explicit actor name above
            # makes the multi-agent separation obvious to reviewers.
            self._record(
                trace,
                "critic",
                critique.decision.value,
                {"rule_ids": [item.rule_id for item in critique.violations]},
            )
            if critique.decision is not Decision.REJECT or revisions >= self._max_revisions:
                break
            plan = self._strategist.revise(plan, critique, evidence)
            revisions += 1
            self._record(trace, "strategist", "revised", plan.model_dump(mode="json"))

        state.active_driver_id = profile.driver_id
        state.last_issue_type = observation.issue_type
        state.messages = [
            *state.messages[-8:],
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": critique.summary},
        ]
        state.last_plan = plan
        state.last_critic_result = critique
        self._memory.save(state)
        self._record(
            trace,
            "conversation_memory",
            "saved",
            {
                "conversation_id": conversation_id,
                "active_driver_id": profile.driver_id,
                "last_issue_type": observation.issue_type.value,
            },
        )

        LOGGER.info(
            "copilot_run_completed",
            extra={
                "conversation_id": conversation_id,
                "driver_id": profile.driver_id,
                "decision": critique.decision.value,
            },
        )
        return ChatResponse(
            conversation_id=conversation_id,
            driver=profile,
            observation=observation,
            plan=plan,
            critic=critique,
            manager_message=self._render_manager_message(plan, critique),
            trace=trace,
        )

    def _resolve_driver(self, request: ChatRequest, state: ConversationState) -> DriverProfile:
        explicit = request.driver_id or self._extractor.extract_driver_id(request.message)
        if explicit:
            return self._drivers.get(explicit)
        if state.active_driver_id:
            return self._drivers.get(state.active_driver_id)

        lowered = request.message.casefold()
        matches = [
            driver for driver in self._drivers.all() if driver.name.split()[0].casefold() in lowered
        ]
        if len(matches) == 1:
            return matches[0]
        raise DriverNotFoundError(
            "Provide a driver ID on the first turn; follow-up turns can reuse conversation state."
        )

    @classmethod
    def _record(
        cls,
        trace: list[TraceEvent],
        node: str,
        outcome: str,
        payload: dict[str, Any],
    ) -> None:
        trace.append(
            cls._event(
                node,
                outcome,
                {"sequence": len(trace) + 1, **payload},
            )
        )

    @staticmethod
    def _event(node: str, outcome: str, payload: dict[str, Any]) -> TraceEvent:
        return TraceEvent(timestamp=datetime.now(UTC), node=node, outcome=outcome, payload=payload)

    @staticmethod
    def _render_manager_message(plan: RetentionPlan, critique: CriticResult) -> str:
        action_lines = []
        for action in plan.actions:
            value = f" (£{action.value_gbp:.2f})" if action.value_gbp else ""
            condition = " — human/pending check" if action.requires_human_approval else ""
            action_lines.append(f"- {action.name}{value}{condition}: {action.rationale}")
        violations = [f"- {item.rule_id}: {item.message}" for item in critique.violations]
        checks = "\n".join(violations) if violations else "- No outstanding policy findings."
        return (
            f"Decision: {critique.decision.value}\n"
            f"Diagnosis: {plan.diagnosis}\n"
            f"Recommended actions:\n{chr(10).join(action_lines)}\n"
            f"Compliance checks:\n{checks}"
        )
