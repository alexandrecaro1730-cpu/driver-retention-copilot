"""Closed vocabularies for decisions and business concepts.

Enums prevent prompt or tool output from introducing unrecognised decision states that
would be difficult to monitor or audit in production.
"""

from enum import StrEnum


class LoyaltyTier(StrEnum):
    BRONZE = "Bronze"
    SILVER = "Silver"
    GOLD = "Gold"


class IssueType(StrEnum):
    AIRPORT_SHORT_FARE = "airport_short_fare"
    TECHNICAL_GPS = "technical_gps"
    NEW_STARTER = "new_starter"
    QUEST = "quest"
    PAYMENT = "payment"
    CANCELLATION = "cancellation"
    GENERAL = "general"
    UNKNOWN = "unknown"


class ActionType(StrEnum):
    CREDIT = "credit"
    DISCOUNT = "discount"
    QUEST = "quest"
    SUPPORT = "support"
    ESCALATION = "escalation"
    COMMUNICATION = "communication"


class Decision(StrEnum):
    APPROVE = "APPROVE"
    CONDITIONAL_APPROVE = "CONDITIONAL_APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class Severity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ChurnRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
