"""OpenAI implementation of the structured LLM boundary.

Business intent
---------------
A model outage must not bypass policy validation or expose credentials in logs. Failures are reduced
to a safe application exception so the configured deterministic fallback can take over.

Technical intent
----------------
The Responses API parses directly into the requested Pydantic schema. Retries are bounded, apply
only to transient failures, and use exponential backoff with jitter to avoid retry storms.
"""

from __future__ import annotations

import secrets
import time
from typing import Any

from app.exceptions import ConfigurationError, ToolUnavailableError
from app.llm.base import ResponseT

_RETRYABLE_ERROR_NAMES = {
    "APIConnectionError",
    "APITimeoutError",
    "InternalServerError",
    "RateLimitError",
}


class OpenAIStructuredLLM:
    """Schema-constrained OpenAI client with conservative failure semantics."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None,
        timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        max_output_tokens: int = 3_000,
    ) -> None:
        if not api_key:
            raise ConfigurationError("OPENAI_API_KEY is required when STRATEGIST_PROVIDER=openai")
        if not model:
            raise ConfigurationError("OPENAI_MODEL is required when STRATEGIST_PROVIDER=openai")
        if max_attempts < 1:
            raise ConfigurationError("LLM_MAX_ATTEMPTS must be at least 1")

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ConfigurationError(
                "Install the AI dependencies with: python -m pip install -e '.[ai]'"
            ) from exc

        # The SDK receives the secret directly. It is intentionally never stored in a repr, trace,
        # prompt, or application log.
        self._client: Any = OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,  # Retry policy is owned here so behaviour is explicit and testable.
        )
        self._model = model
        self._max_attempts = max_attempts
        self._max_output_tokens = max_output_tokens

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseT],
    ) -> ResponseT:
        last_error: Exception | None = None

        for attempt in range(self._max_attempts):
            try:
                response: Any = self._client.responses.parse(
                    model=self._model,
                    instructions=system_prompt,
                    input=user_prompt,
                    text_format=response_model,
                    max_output_tokens=self._max_output_tokens,
                )
                parsed = getattr(response, "output_parsed", None)
                if not isinstance(parsed, response_model):
                    raise ToolUnavailableError("The LLM returned no valid structured output")
                return parsed
            except ToolUnavailableError:
                raise
            except Exception as exc:  # pragma: no cover - requires external service
                last_error = exc
                retryable = exc.__class__.__name__ in _RETRYABLE_ERROR_NAMES
                final_attempt = attempt + 1 >= self._max_attempts
                if not retryable or final_attempt:
                    break

                # Jitter reduces synchronized retry bursts after transient provider failures.
                # `secrets` avoids static-analysis warnings for standard pseudo-random generators.
                jitter_seconds = secrets.randbelow(251) / 1_000.0
                delay_seconds = (2**attempt) + jitter_seconds
                time.sleep(delay_seconds)

        # Do not leak provider payloads, prompts, credentials, or driver data through exception text.
        raise ToolUnavailableError(
            "OpenAI structured generation failed; deterministic fallback may be used"
        ) from last_error
