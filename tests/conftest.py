from pathlib import Path

import pytest
from app.config import Settings
from app.container import build_copilot


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return Path(__file__).parents[1] / "data"


@pytest.fixture()
def settings(data_dir: Path, tmp_path: Path) -> Settings:
    return Settings(
        data_dir=data_dir,
        state_db_path=tmp_path / "state.sqlite3",
        strategist_provider="heuristic",
        max_revisions=2,
    )


@pytest.fixture()
def copilot(settings: Settings):
    return build_copilot(settings)
