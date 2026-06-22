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
