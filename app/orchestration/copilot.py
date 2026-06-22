"""Bounded Strategist/Critic state machine.

Business intent
---------------
A manager receives one accountable recommendation, not a conversation between unconstrained agents.
The workflow gathers evidence first, permits at most a small number of revisions, and never silently
executes an incentive.

Technical intent
----------------
The explicit loop is intentionally simpler than a general agent framework. Nodes are ordinary Python
components, state is typed, and every transition is recorded in an evaluation trace.
"""

from __future__ import annotations

import logging
import re
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
_NAME_HINT = re.compile(r"\b(?:driver\s+)?([A-Z][a-z]+)(?:\s+[A-Z]\.)?\b")


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
        trace.append(self._event("context", "resolved", {"driver_id": profile.driver_id}))

        tickets = self._tickets.for_driver(profile.driver_id, limit=20)
        observation = self._extractor.extract(
            request.message,
            profile,
            tickets,
            previous_issue_type=state.last_issue_type,
        )
        incentives = self._incentives.available_for(profile)
        policy_chunks = self._policies.retrieve(
            request.message,
            issue_type=observation.issue_type,
            tier=profile.loyalty_tier,
        )
        evidence = EvidenceBundle(
            query=request.message,
            profile=profile,
            tickets=tickets,
            incentives=incentives,
            policy_chunks=policy_chunks,
            observation=observation,
            ledger=self._ledger.get(profile.driver_id),
        )
        trace.append(
            self._event(
                "evidence",
                "collected",
                {
                    "ticket_ids": [ticket.ticket_id for ticket in tickets],
                    "incentive_ids": [item.id for item in incentives],
                    "policy_chunk_ids": [chunk.chunk_id for chunk in policy_chunks],
                    "ledger_complete": evidence.ledger.complete,
                    "observation": observation.model_dump(mode="json"),
                },
            )
        )

        plan = request.initial_plan_override or self._strategist.propose(evidence)
        trace.append(self._event("strategist", "proposed", plan.model_dump(mode="json")))

        revisions = 0
        while True:
            critique = self._critic.validate(plan, evidence)
            trace.append(
                self._event("critic", critique.decision.value, critique.model_dump(mode="json"))
            )
            if critique.decision is not Decision.REJECT or revisions >= self._max_revisions:
                break
            plan = self._strategist.revise(plan, critique, evidence)
            revisions += 1
            trace.append(self._event("strategist", "revised", plan.model_dump(mode="json")))

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

        # Conservative name resolution: test each known first name rather than trusting arbitrary
        # capitalised words such as Heathrow or What.
        lowered = request.message.casefold()
        matches = [
            driver for driver in self._drivers.all() if driver.name.split()[0].casefold() in lowered
        ]
        if len(matches) == 1:
            return matches[0]
        raise DriverNotFoundError(
            "Provide a driver ID on the first turn; follow-up turns can reuse conversation state."
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
