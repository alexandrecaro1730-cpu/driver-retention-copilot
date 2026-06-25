from __future__ import annotations

from datetime import datetime

from app.domain.enums import ActionType, IssueType, LoyaltyTier
from app.domain.models import (
    DriverObservation,
    DriverProfile,
    EvidenceBundle,
    Incentive,
    LedgerSnapshot,
    PolicyChunk,
    ProposedAction,
    RetentionPlan,
    SupportTicket,
)


def profile(
    *,
    driver_id: str = "D-LON-001",
    tier: LoyaltyTier = LoyaltyTier.GOLD,
    tenure: int = 24,
    status: str = "ONLINE",
    sentiment: str = "Frustrated - airport queue issue",
) -> DriverProfile:
    return DriverProfile(
        driver_id=driver_id,
        name="Test Driver",
        city="London",
        loyalty_tier=tier,
        tenure_months=tenure,
        lifetime_value_euro=12_000,
        avg_cancellation_rate=0.02,
        airport_short_fare_count_30d=3,
        confirmed_valid_complaints_1y=1,
        current_status=status,
        recent_sentiment=sentiment,
    )


def ticket(
    *,
    ticket_id: str = "T-1",
    driver_id: str = "D-LON-001",
    category: str = "Airport",
    message: str = "Waited 120 minutes for a 1.5km trip",
) -> SupportTicket:
    return SupportTicket(
        ticket_id=ticket_id,
        driver_id=driver_id,
        timestamp=datetime(2026, 3, 2, 10, 0),
        category=category,
        message=message,
        status="OPEN",
    )


def incentives() -> list[Incentive]:
    return [
        Incentive(
            id="INC-001",
            type="CREDIT",
            category="Airport",
            name="Standard Airport Short Fare Recovery",
            value=25,
            currency="GBP",
            min_tier=LoyaltyTier.BRONZE,
        ),
        Incentive(
            id="INC-002",
            type="CREDIT",
            category="Airport",
            name="Premium Airport Short Fare Recovery",
            value=50,
            currency="GBP",
            min_tier=LoyaltyTier.GOLD,
        ),
        Incentive(
            id="INC-003",
            type="CREDIT",
            category="Technical",
            name="Geofence/GPS Glitch Credit",
            value=10,
            currency="GBP",
            min_tier=LoyaltyTier.BRONZE,
        ),
        Incentive(
            id="INC-004",
            type="CREDIT",
            category="Technical",
            name="Priority Technical Support Access",
            value=0,
            currency="GBP",
            min_tier=LoyaltyTier.SILVER,
        ),
        Incentive(
            id="INC-006",
            type="DISCOUNT",
            category="Commission",
            name="First Month Commission Shield",
            value=50,
            currency="PERCENT",
            min_tier=LoyaltyTier.BRONZE,
            max_tenure_months=1,
        ),
        Incentive(
            id="INC-007",
            type="CREDIT",
            category="Churn",
            name="High-Value Partner Goodwill",
            value=75,
            currency="GBP",
            min_tier=LoyaltyTier.GOLD,
        ),
        Incentive(
            id="Q-103",
            type="QUEST",
            category="Engagement",
            name="Airport Fast-Track Voucher",
            value=0,
            currency="GBP",
            min_tier=LoyaltyTier.GOLD,
        ),
    ]


def policy_chunks() -> list[PolicyChunk]:
    return [
        PolicyChunk(
            chunk_id="A.1",
            title="Global Monthly Cap",
            text="No package over £150",
            is_global_guardrail=True,
            source="test",
        ),
        PolicyChunk(
            chunk_id="A.2",
            title="Credit Stacking",
            text="No more than two credits",
            is_global_guardrail=True,
            source="test",
        ),
        PolicyChunk(
            chunk_id="A.3",
            title="Tier Multipliers",
            text="Churn goodwill is for Silver and Gold",
            is_global_guardrail=True,
            source="test",
        ),
        PolicyChunk(
            chunk_id="B.1",
            title="Airport Short Fares",
            text="Wait >90 and distance <3km",
            issue_types=[IssueType.AIRPORT_SHORT_FARE],
            source="test",
        ),
        PolicyChunk(
            chunk_id="B.2",
            title="Technical & GPS Glitches",
            text="Technical compensation is capped at £10",
            issue_types=[IssueType.TECHNICAL_GPS],
            source="test",
        ),
        PolicyChunk(
            chunk_id="B.3",
            title="New Starters",
            text="Prefer commission shields",
            issue_types=[IssueType.NEW_STARTER],
            source="test",
        ),
        PolicyChunk(
            chunk_id="B.4",
            title="Infeasible Quests",
            text="Goodwill is capped at £20 with diagnostics",
            issue_types=[IssueType.QUEST],
            source="test",
        ),
    ]


def evidence(
    *,
    tier: LoyaltyTier = LoyaltyTier.GOLD,
    tenure: int = 24,
    issue: IssueType = IssueType.AIRPORT_SHORT_FARE,
    wait: float | None = 120,
    distance: float | None = 1.5,
    mtd: float | None = 0,
    credits: int | None = 0,
    recurring_technical: int = 0,
    quest_ratio: float | None = None,
    offers: float | None = None,
    systemic: bool = False,
    available: list[Incentive] | None = None,
) -> EvidenceBundle:
    p = profile(tier=tier, tenure=tenure)
    return EvidenceBundle(
        query="test query",
        profile=p,
        tickets=[ticket(category="Technical" if issue is IssueType.TECHNICAL_GPS else "Airport")],
        incentives=available if available is not None else incentives(),
        policy_chunks=policy_chunks(),
        observation=DriverObservation(
            issue_type=issue,
            wait_minutes=wait,
            trip_distance_km=distance,
            quest_completion_ratio=quest_ratio,
            offers_per_hour=offers,
            multi_day_systemic_failure=systemic,
            related_ticket_count=1,
            recurring_technical_tickets_7d=recurring_technical,
        ),
        ledger=LedgerSnapshot(
            driver_id=p.driver_id,
            month_to_date_gbp=mtd,
            immediate_credits_last_24h=credits,
            source="test",
        ),
    )


def action(
    *,
    incentive_id: str | None = "INC-001",
    category: str = "Airport",
    value: float = 25,
    value_percent: float = 0,
    immediate: bool = True,
    counts_toward_monthly_cap: bool = True,
    action_type: ActionType = ActionType.CREDIT,
    evidence_ids: list[str] | None = None,
    policy_chunk_ids: list[str] | None = None,
) -> ProposedAction:
    return ProposedAction(
        action_type=action_type,
        name="Test action",
        incentive_id=incentive_id,
        category=category,
        value_gbp=value,
        value_percent=value_percent,
        immediate_credit=immediate,
        counts_toward_monthly_cap=counts_toward_monthly_cap,
        rationale="test rationale",
        evidence_ids=["T-1"] if evidence_ids is None else evidence_ids,
        policy_chunk_ids=["B.1"] if policy_chunk_ids is None else policy_chunk_ids,
    )


def plan(*actions: ProposedAction) -> RetentionPlan:
    return RetentionPlan(
        driver_id="D-LON-001",
        diagnosis="Test diagnosis",
        churn_risk="high",
        actions=list(actions),
    )
