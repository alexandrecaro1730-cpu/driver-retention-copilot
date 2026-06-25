"""Runtime configuration.

Business intent: safe, reproducible behaviour is the default. Reviewers can explicitly enable a real
LLM Strategist with their own credentials, while deterministic compliance remains authoritative.

Technical intent: paths and provider settings are resolved once and injected at the composition root,
avoiding hidden globals and making tests straightforward.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    strategist_provider: Literal["heuristic", "openai"] = "heuristic"
    openai_api_key: str | None = None
    openai_model: str | None = None
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    llm_max_attempts: int = Field(default=3, ge=1, le=5)
    llm_max_output_tokens: int = Field(default=3_000, ge=500, le=20_000)

    data_dir: Path = Path("./data")
    state_db_path: Path = Path("./var/copilot_state.sqlite3")
    log_level: str = "INFO"
    max_revisions: int = Field(default=2, ge=0, le=5)

    @field_validator("data_dir", "state_db_path", mode="before")
    @classmethod
    def expand_paths(cls, value: object) -> object:
        return Path(str(value)).expanduser()

    def ensure_runtime_directories(self) -> None:
        """Create only mutable runtime directories; source data remains read-only."""
        self.state_db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_runtime_directories()
    return settings
