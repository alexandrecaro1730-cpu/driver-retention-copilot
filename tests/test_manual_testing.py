"""Tests for the no-cost, human-mediated LLM evaluation workflow."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.domain.enums import ActionType, ChurnRisk, Decision
from app.domain.models import ProposedAction, RetentionPlan
from app.manual_testing import ManualEvaluationResult, ManualLLMTestService, ManualPromptBundle


def _service(tmp_path: Path) -> ManualLLMTestService:
    return ManualLLMTestService(
        Settings(data_dir=Path("data"), state_db_path=tmp_path / "state.sqlite3")
    )


def test_export_writes_prompt_bundle_schema_and_response_file(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    bundle_path = _service(tmp_path).export_initial(
        driver_id="D-LON-001",
        message="Maria waited 135 minutes for a 1.5km airport trip.",
        output_dir=run_dir,
    )

    assert bundle_path.exists()
    assert (run_dir / "prompt.txt").exists()
    assert (run_dir / "retention_plan.schema.json").exists()
    assert (run_dir / "response.json").read_text().strip() == "{}"
    bundle = ManualPromptBundle.model_validate_json(bundle_path.read_text())
    assert bundle.phase == "proposal"
    assert bundle.expected_revision == 0


def test_exported_prompt_is_self_executing_and_forbids_clarification(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _service(tmp_path).export_initial(
        driver_id="D-LON-001",
        message="Maria waited 135 minutes for a 1.5km airport trip.",
        output_dir=run_dir,
    )

    prompt = (run_dir / "prompt.txt").read_text()

    assert prompt.startswith(
        "IMPORTANT: THIS FILE IS AN EXECUTABLE TASK PROMPT, NOT BACKGROUND DOCUMENTATION."
    )
    assert "Do not ask the user what they want you to do." in prompt
    assert "Produce the RetentionPlan now." in prompt
    assert "Return exactly one valid JSON object" in prompt
    assert prompt.rstrip().endswith("or after the JSON.")


def test_valid_manual_response_is_checked_by_critic(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    bundle_path = _service(tmp_path).export_initial(
        driver_id="D-LON-001",
        message="Maria waited 135 minutes for a 1.5km airport trip.",
        output_dir=run_dir,
    )
    response = RetentionPlan(
        driver_id="D-LON-001",
        diagnosis="Qualifying airport short-fare friction.",
        churn_risk=ChurnRisk.HIGH,
        actions=[
            ProposedAction(
                action_type=ActionType.CREDIT,
                name="Standard airport short-fare recovery",
                incentive_id="INC-001",
                category="Airport",
                value_gbp=25,
                immediate_credit=True,
                rationale="Restore trust after a qualifying incident.",
                evidence_ids=["T-1001"],
                policy_chunk_ids=["B.1"],
            )
        ],
    )
    response_file = run_dir / "response.json"
    response_file.write_text(response.model_dump_json(indent=2))

    evaluation_path = _service(tmp_path).evaluate_response(
        bundle_file=bundle_path, response_file=response_file
    )
    result = ManualEvaluationResult.model_validate_json(evaluation_path.read_text())

    assert result.valid_schema is True
    assert result.critic is not None
    assert result.critic.decision is Decision.APPROVE


def test_rejected_response_generates_revision_prompt(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    service = _service(tmp_path)
    bundle_path = service.export_initial(
        driver_id="D-LON-001",
        message="Maria waited 135 minutes for a 1.5km airport trip.",
        output_dir=run_dir,
    )
    unsafe = RetentionPlan(
        driver_id="D-LON-001",
        diagnosis="Repeated airport issue.",
        churn_risk=ChurnRisk.HIGH,
        actions=[
            ProposedAction(
                action_type=ActionType.CREDIT,
                name="Premium airport recovery",
                incentive_id="INC-002",
                category="Airport",
                value_gbp=50,
                immediate_credit=True,
                rationale="Recover driver trust.",
                evidence_ids=["T-1001"],
                policy_chunk_ids=["B.1"],
            )
        ],
    )
    response_file = run_dir / "response.json"
    response_file.write_text(unsafe.model_dump_json())

    evaluation_path = service.evaluate_response(
        bundle_file=bundle_path, response_file=response_file
    )
    result = ManualEvaluationResult.model_validate_json(evaluation_path.read_text())

    assert result.critic is not None
    assert result.critic.decision is Decision.REJECT
    assert result.next_revision_bundle is not None
    revision_path = Path(result.next_revision_bundle)
    revision_bundle = ManualPromptBundle.model_validate_json(revision_path.read_text())
    assert revision_bundle.phase == "revision"
    assert revision_bundle.expected_revision == 1
    assert (revision_path.parent / "prompt.txt").exists()


def test_invalid_json_is_reported_without_crashing(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    service = _service(tmp_path)
    bundle_path = service.export_initial(
        driver_id="D-LON-001", message="Airport issue", output_dir=run_dir
    )
    response_file = run_dir / "response.json"
    response_file.write_text("not json")

    evaluation_path = service.evaluate_response(
        bundle_file=bundle_path, response_file=response_file
    )
    result = ManualEvaluationResult.model_validate_json(evaluation_path.read_text())

    assert result.valid_schema is False
    assert result.errors
