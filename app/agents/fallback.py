"""Resilient Strategist wrapper.

Business intent: a transient model outage must not leave a manager without a safe diagnostic path.
The fallback remains recommendation-only and is validated by the same Compliance Critic.

Technical intent: availability failures trigger deterministic fallback for both proposal and repair.
Configuration errors still fail during composition so a broken deployment is visible immediately.
"""

from __future__ import annotations

import logging

from app.agents.base import Strategist
from app.domain.models import CriticResult, EvidenceBundle, RetentionPlan
from app.exceptions import ToolUnavailableError

LOGGER = logging.getLogger(__name__)


class FallbackStrategist:
    def __init__(self, primary: Strategist, fallback: Strategist):
        self._primary = primary
        self._fallback = fallback

    def propose(self, evidence: EvidenceBundle) -> RetentionPlan:
        try:
            return self._primary.propose(evidence)
        except ToolUnavailableError:
            LOGGER.warning(
                "primary_strategist_unavailable_using_fallback",
                extra={"driver_id": evidence.profile.driver_id, "operation": "propose"},
            )
            return self._fallback.propose(evidence)

    def revise(
        self, plan: RetentionPlan, critique: CriticResult, evidence: EvidenceBundle
    ) -> RetentionPlan:
        try:
            return self._primary.revise(plan, critique, evidence)
        except ToolUnavailableError:
            LOGGER.warning(
                "primary_strategist_unavailable_using_fallback",
                extra={"driver_id": evidence.profile.driver_id, "operation": "revise"},
            )
            return self._fallback.revise(plan, critique, evidence)
