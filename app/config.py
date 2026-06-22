"""Runtime configuration.

Business intent: configuration must make safe behaviour the default. The deterministic
strategist is selected unless an operator explicitly enables an external LLM provider.

Technical intent: paths are resolved once and injected into repositories, avoiding hidden
global filesystem dependencies and making tests straightforward.
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
