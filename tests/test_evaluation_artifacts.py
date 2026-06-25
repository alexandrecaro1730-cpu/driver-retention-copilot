import json
from pathlib import Path


def test_maria_trace_contains_reject_then_approve() -> None:
    path = Path(__file__).parents[1] / "evaluations" / "maria_self_correction.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    critic_outcomes = [event["outcome"] for event in payload["trace"] if event["node"] == "critic"]
    assert critic_outcomes == ["REJECT", "APPROVE"]
    assert payload["plan"]["total_gbp_value"] == 25


def test_scenario_catalogue_has_broad_rule_coverage() -> None:
    path = Path(__file__).parents[1] / "evaluations" / "scenarios.json"
    scenarios = json.loads(path.read_text(encoding="utf-8"))
    assert len(scenarios) >= 12
    assert {item["expected"] for item in scenarios} >= {
        "REJECT",
        "ESCALATE",
        "CONDITIONAL_APPROVE",
    }


def test_manual_trace_contains_reject_revision_and_approve() -> None:
    root = Path(__file__).parents[1] / "evaluations" / "manual_self_correction"
    rejected = json.loads((root / "01_rejected.json").read_text(encoding="utf-8"))
    corrected = json.loads((root / "02_corrected.json").read_text(encoding="utf-8"))
    revision = json.loads((root / "revision_request.json").read_text(encoding="utf-8"))

    assert rejected["critic"]["decision"] == "REJECT"
    assert rejected["next_revision_bundle"] == (
        "evaluations/manual_self_correction/revision_request.json"
    )
    assert revision["phase"] == "revision"
    assert revision["expected_revision"] == 1
    assert corrected["critic"]["decision"] == "APPROVE"
    assert corrected["plan"]["revision"] == 1
    assert corrected["plan"]["actions"][0]["incentive_id"] == "INC-001"
