"""Provider-neutral contract for schema-constrained language models.

Business intent
---------------
The Strategist needs language understanding, but the wider application must not be coupled to one
vendor. Reviewers can therefore supply their own supported model while the retention workflow and
compliance controls remain unchanged.

Technical intent
----------------
Only validated Pydantic objects cross this boundary. Free-form model text never enters the
orchestration or compliance layers.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class StructuredLLM(Protocol):
    """Minimal interface required by an agent that needs typed model output."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseT],
    ) -> ResponseT:
        """Generate and validate one response against ``response_model``."""
