"""Generate the required Maria reject→repair→approve evaluation artifact."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings
from app.container import build_copilot
from app.domain.enums import ActionType, ChurnRisk
from app.domain.models import ChatRequest, ProposedAction, RetentionPlan

ROOT = Path(__file__).parents[1]


def main() -> None:
    initial = RetentionPlan(
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
                rationale="Recover the relationship after repeated airport losses.",
                evidence_ids=["T-1001", "T-1007"],
                policy_chunk_ids=["B.1"],
            )
        ],
    )
    settings = Settings(
        data_dir=ROOT / "data",
        state_db_path=ROOT / "var" / "evaluation_state.sqlite3",
        strategist_provider="heuristic",
    )
    result = build_copilot(settings).run(
        ChatRequest(
            conversation_id="eval-maria-self-correction",
            driver_id="D-LON-001",
            message=(
                "Maria waited 135 minutes for a 1.5km airport fare and says the issue has repeated."
            ),
            initial_plan_override=initial,
        )
    )
    output = ROOT / "evaluations" / "maria_self_correction.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
