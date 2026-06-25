# ruff: noqa: B008
"""Command-line interface for reviewer-friendly execution."""

from __future__ import annotations

from pathlib import Path

import typer

from app.config import Settings
from app.container import build_copilot
from app.domain.enums import ActionType, ChurnRisk
from app.domain.models import ChatRequest, ProposedAction, RetentionPlan
from app.manual_testing import ManualLLMTestService

app = typer.Typer(no_args_is_help=True, help="FREENOW Driver Retention Copilot")


def _settings() -> Settings:
    """Create application settings for local reviewer execution.

    Business intent:
        Make the take-home project runnable with predictable local paths.

    Technical intent:
        Keep CLI-specific configuration in one place.
    """
    return Settings(
        data_dir=Path("data"),
        state_db_path=Path("var/copilot_state.sqlite3"),
    )


@app.command()
def chat(
    message: str = typer.Option(..., help="Manager question or complaint context"),
    driver_id: str | None = typer.Option(None, help="Explicit driver ID for the first turn"),
    conversation_id: str | None = typer.Option(None, help="Reuse for multi-turn context"),
    json_output: bool = typer.Option(False, "--json", help="Print the full typed response"),
) -> None:
    """Run one grounded Driver Retention Copilot interaction."""
    response = build_copilot(_settings()).run(
        ChatRequest(
            message=message,
            driver_id=driver_id,
            conversation_id=conversation_id,
        )
    )

    typer.echo(response.model_dump_json(indent=2) if json_output else response.manager_message)
    typer.echo(f"\nConversation ID: {response.conversation_id}")


@app.command("manual-export")
def manual_export(
    message: str = typer.Option(..., help="Manager question or complaint context"),
    driver_id: str = typer.Option(..., help="Driver ID to ground the prompt"),
    output_dir: Path = typer.Option(
        Path("manual_runs/latest"),
        help="Directory for prompt.txt and request.json",
    ),
) -> None:
    """Export an LLM prompt for free, human-mediated testing."""
    bundle = ManualLLMTestService(_settings()).export_initial(
        driver_id=driver_id,
        message=message,
        output_dir=output_dir,
    )

    typer.echo(f"Prompt: {output_dir / 'prompt.txt'}")
    typer.echo(f"Request bundle: {bundle}")
    typer.echo(f"Paste model JSON into: {output_dir / 'response.json'}")


@app.command("manual-evaluate")
def manual_evaluate(
    bundle_file: Path = typer.Option(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="request.json from manual-export",
    ),
    response_file: Path = typer.Option(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="JSON copied from a chat model",
    ),
    output_dir: Path | None = typer.Option(
        None,
        help="Defaults to the bundle directory",
    ),
) -> None:
    """Validate a manual model response and run the Compliance Critic."""
    result = ManualLLMTestService(_settings()).evaluate_response(
        bundle_file=bundle_file,
        response_file=response_file,
        output_dir=output_dir,
    )

    typer.echo(f"Evaluation: {result}")
    typer.echo(result.read_text(encoding="utf-8"))


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
            message=("Maria waited 135 minutes for a 1.5km airport fare; this keeps happening."),
            driver_id="D-LON-001",
            initial_plan_override=unsafe_initial,
        )
    )

    typer.echo(response.model_dump_json(indent=2))


def main() -> None:
    """Run the Typer command-line application."""
    app()


if __name__ == "__main__":
    main()
