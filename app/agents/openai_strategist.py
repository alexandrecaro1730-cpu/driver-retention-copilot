"""Optional OpenAI-backed Strategist.

The external model is used only to propose a typed plan. Tool results and policy chunks are supplied
as evidence, and the deterministic Compliance Critic remains authoritative. Non-streaming structured
output is used so an incomplete response cannot be mistaken for a valid business object.
"""

from __future__ import annotations

import json
import time
from typing import Any

from app.agents.heuristic_strategist import HeuristicStrategist
from app.domain.models import CriticResult, EvidenceBundle, RetentionPlan
from app.exceptions import ConfigurationError, ToolUnavailableError


class OpenAIStrategist:
    def __init__(self, *, api_key: str | None, model: str | None, max_attempts: int = 3):
        if not api_key or not model:
            raise ConfigurationError(
                "OPENAI_API_KEY and OPENAI_MODEL are required for the OpenAI strategist"
            )
        self._api_key = api_key
        self._model = model
        self._max_attempts = max_attempts
        self._repair = HeuristicStrategist()

    def propose(self, evidence: EvidenceBundle) -> RetentionPlan:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional integration
            raise ConfigurationError("Install the 'ai' extra to use OpenAI") from exc

        client = OpenAI(api_key=self._api_key)
        payload = evidence.model_dump(mode="json")
        instructions = (
            "You are the Strategist in a driver-retention actor/validator workflow. "
            "Use only the supplied evidence. Never claim an action was issued. Produce a practical "
            "retention plan with evidence IDs and policy chunk IDs. Missing facts must be explicit. "
            "The separate Compliance Critic will enforce all financial rules."
        )
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                response: Any = client.responses.parse(
                    model=self._model,
                    instructions=instructions,
                    input=json.dumps(payload, ensure_ascii=False),
                    text_format=RetentionPlan,
                )
                if getattr(response, "status", "completed") != "completed":
                    raise ToolUnavailableError("LLM response was incomplete")
                parsed = getattr(response, "output_parsed", None)
                if not isinstance(parsed, RetentionPlan):
                    raise ToolUnavailableError("LLM did not return a valid RetentionPlan")
                return parsed
            except Exception as exc:  # pragma: no cover - requires external service
                last_error = exc
                if attempt + 1 < self._max_attempts:
                    time.sleep(2**attempt)
        raise ToolUnavailableError("OpenAI strategist failed after bounded retries") from last_error

    def revise(
        self, plan: RetentionPlan, critique: CriticResult, evidence: EvidenceBundle
    ) -> RetentionPlan:
        # Repair is deterministic by design. This guarantees that a valid critic finding is not
        # reinterpreted or ignored by a second probabilistic call.
        return self._repair.revise(plan, critique, evidence)
