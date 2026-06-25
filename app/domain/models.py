"""Pydantic contracts for every cross-layer message.

Business intent
---------------
A retention recommendation can affect driver trust and company spend. Every recommendation
therefore carries explicit evidence references, monetary value, assumptions, and validation
status.

Technical intent
----------------
Strict models turn agent outputs into validated data rather than free-form text. This reduces
hallucination risk and makes traces, tests, APIs, and future event streaming deterministic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.domain.enums import (
    ActionType,
    ChurnRisk,
    Decision,
    IssueType,
    LoyaltyTier,
    Severity,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)


class DriverProfile(StrictModel):
    driver_id: str
    name: str
    city: str
    loyalty_tier: LoyaltyTier
    tenure_months: int = Field(ge=0)
    lifetime_value_euro: float = Field(ge=0)
    avg_cancellation_rate: float = Field(ge=0, le=1)
    airport_short_fare_count_30d: int = Field(ge=0)
    confirmed_valid_complaints_1y: int = Field(ge=0)
    current_status: str
    recent_sentiment: str


class SupportTicket(StrictModel):
    ticket_id: str
    driver_id: str
    timestamp: datetime
    category: str
    message: str
    status: str


class Incentive(StrictModel):
    id: str
    type: str
    category: str
    name: str
    value: float = Field(ge=0)
    currency: str
    min_tier: LoyaltyTier
    max_tenure_months: int | None = None
    description: str | None = None
    requirement: str | None = None


class PolicyChunk(StrictModel):
    chunk_id: str
    title: str
    text: str
    issue_types: list[IssueType] = Field(default_factory=list)
    tiers: list[LoyaltyTier] = Field(default_factory=list)
    is_global_guardrail: bool = False
    source: str
    source_document: str | None = None
    source_page: int | None = Field(default=None, ge=1)
    source_sha256: str | None = None


class DriverObservation(StrictModel):
    issue_type: IssueType
    wait_minutes: float | None = Field(default=None, ge=0)
    trip_distance_km: float | None = Field(default=None, ge=0)
    quest_completion_ratio: float | None = Field(default=None, ge=0, le=1)
    offers_per_hour: float | None = Field(default=None, ge=0)
    multi_day_systemic_failure: bool = False
    policy_question: bool = False
    related_ticket_count: int = Field(default=0, ge=0)
    recurring_technical_tickets_7d: int = Field(default=0, ge=0)
    extracted_facts: list[str] = Field(default_factory=list)


class LedgerSnapshot(StrictModel):
    driver_id: str
    month_to_date_gbp: float | None = Field(default=None, ge=0)
    immediate_credits_last_24h: int | None = Field(default=None, ge=0)
    source: str = "unavailable"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def complete(self) -> bool:
        return self.month_to_date_gbp is not None and self.immediate_credits_last_24h is not None


class EvidenceBundle(StrictModel):
    query: str
    profile: DriverProfile
    tickets: list[SupportTicket]
    incentives: list[Incentive]
    policy_chunks: list[PolicyChunk]
    observation: DriverObservation
    ledger: LedgerSnapshot


class ProposedAction(StrictModel):
    action_type: ActionType
    name: str
    incentive_id: str | None = None
    category: str
    value_gbp: float = Field(default=0, ge=0)
    value_percent: float = Field(default=0, ge=0, le=100)
    immediate_credit: bool = False
    counts_toward_monthly_cap: bool = True
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    policy_chunk_ids: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False


class RetentionPlan(StrictModel):
    driver_id: str
    diagnosis: str
    churn_risk: ChurnRisk
    actions: list[ProposedAction]
    assumptions: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    revision: int = Field(default=0, ge=0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_gbp_value(self) -> float:
        # All positive GBP value is counted. A model-provided flag must never exempt its own
        # recommendation from the authoritative monthly cap.
        return round(sum(action.value_gbp for action in self.actions), 2)


class PolicyViolation(StrictModel):
    rule_id: str
    severity: Severity
    message: str
    suggested_fix: str
    action_index: int | None = Field(default=None, ge=0)
    policy_chunk_ids: list[str] = Field(default_factory=list)


class CriticResult(StrictModel):
    decision: Decision
    violations: list[PolicyViolation]
    verified_total_gbp: float = Field(ge=0)
    policy_chunk_ids: list[str] = Field(default_factory=list)
    summary: str


class TraceEvent(StrictModel):
    timestamp: datetime
    node: str
    outcome: str
    payload: dict[str, Any]


class ConversationState(StrictModel):
    conversation_id: str
    active_driver_id: str | None = None
    last_issue_type: IssueType = IssueType.UNKNOWN
    messages: list[dict[str, str]] = Field(default_factory=list)
    last_plan: RetentionPlan | None = None
    last_critic_result: CriticResult | None = None


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=5_000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=128)
    driver_id: str | None = Field(default=None, min_length=1, max_length=64)
    # Test/evaluation hook. It is intentionally excluded from public API documentation by
    # convention and is not accepted by the FastAPI request model.
    initial_plan_override: RetentionPlan | None = None


class PublicChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=5_000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=128)
    driver_id: str | None = Field(default=None, min_length=1, max_length=64)


class ChatResponse(StrictModel):
    conversation_id: str
    driver: DriverProfile
    observation: DriverObservation
    plan: RetentionPlan
    critic: CriticResult
    manager_message: str
    trace: list[TraceEvent]
