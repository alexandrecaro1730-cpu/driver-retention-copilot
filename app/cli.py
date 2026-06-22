"""Command-line interface for reviewer-friendly execution."""

from __future__ import annotations

from pathlib import Path

import typer

from app.config import Settings
from app.container import build_copilot
from app.domain.enums import ActionType, ChurnRisk
from app.domain.models import ChatRequest, ProposedAction, RetentionPlan

app = typer.Typer(no_args_is_help=True, help="FREENOW Driver Retention Copilot")


def _settings() -> Settings:
    return Settings(data_dir=Path("data"), state_db_path=Path("var/copilot_state.sqlite3"))


@app.command()
def chat(
    message: str = typer.Option(..., help="Manager question or complaint context"),
    driver_id: str | None = typer.Option(None, help="Explicit driver ID for the first turn"),
    conversation_id: str | None = typer.Option(None, help="Reuse for multi-turn context"),
    json_output: bool = typer.Option(False, "--json", help="Print the full typed response"),
) -> None:
    response = build_copilot(_settings()).run(
        ChatRequest(message=message, driver_id=driver_id, conversation_id=conversation_id)
    )
    typer.echo(response.model_dump_json(indent=2) if json_output else response.manager_message)
    typer.echo(f"\nConversation ID: {response.conversation_id}")


@app.command("demo-maria")
def demo_maria() -> None:
    """Generate the assignment's required reject-and-revise trace."""
    unsafe_initial = RetentionPlan(
        driver_id="D-LON-001",
        diagnosis="Repeated airport short-fare friction for a high-value Gold driver.",
        churn_risk=ChurnRisk.HIGH,
        actions=[
            ProposedAction(
                action_type=ActionType.CREDIT,
                name="Premium Airport Short Fare Recovery",
                incentive_id="INC-002",
                category="Airport",
                value_gbp=50,
                immediate_credit=True,
                rationale="Attempt to recover a frustrated Gold driver.",
                evidence_ids=["T-1001", "T-1007"],
                policy_chunk_ids=["B.1"],
            )
        ],
    )
    response = build_copilot(_settings()).run(
        ChatRequest(
            message="Maria waited 135 minutes for a 1.5km airport fare; this keeps happening.",
            driver_id="D-LON-001",
            initial_plan_override=unsafe_initial,
        )
    )
    typer.echo(response.model_dump_json(indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
