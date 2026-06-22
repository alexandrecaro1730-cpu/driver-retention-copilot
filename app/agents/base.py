"""Strategist protocol used by the orchestration layer."""

from typing import Protocol

from app.domain.models import CriticResult, EvidenceBundle, RetentionPlan


class Strategist(Protocol):
    def propose(self, evidence: EvidenceBundle) -> RetentionPlan: ...

    def revise(
        self, plan: RetentionPlan, critique: CriticResult, evidence: EvidenceBundle
    ) -> RetentionPlan: ...
