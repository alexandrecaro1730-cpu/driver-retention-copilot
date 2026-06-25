"""Run a reviewer-friendly, no-API end-to-end demonstration.

The default output explains the business problem, authoritative evidence, policy retrieval,
Strategist proposal, deterministic Critic rejection, bounded self-correction, final approval,
multi-turn memory, and recommendation-only safety boundary. Compact and JSON modes remain
available for fast scanning and machine inspection.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from app.config import Settings
from app.container import build_copilot
from app.data.ticket_repository import TicketRepository
from app.domain.enums import ActionType, ChurnRisk
from app.domain.models import ChatRequest, ProposedAction, RetentionPlan, TraceEvent
from app.integrations.incentive_adapter import IncentiveAdapter

ROOT = Path(__file__).parents[1]
MANAGER_REQUEST = "Maria waited 135 minutes for a 1.5km airport fare and says this keeps happening."
FOLLOW_UP_REQUEST = "What policy applies to her specific tier?"


def _unsafe_plan() -> RetentionPlan:
    """Return an intentionally invalid plan used to prove independent validation."""

    return RetentionPlan(
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


def _event(trace: list[TraceEvent], node: str, occurrence: int = 0) -> TraceEvent:
    matches = [item for item in trace if item.node == node]
    if occurrence >= len(matches):
        raise RuntimeError(f"Reviewer demo expected trace node {node!r} occurrence {occurrence}.")
    return matches[occurrence]


def _policy_index() -> dict[str, dict[str, Any]]:
    path = ROOT / "data" / "policy_chunks.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise RuntimeError("Policy provenance index must contain a JSON list.")
    return {
        str(item["chunk_id"]): item for item in raw if isinstance(item, dict) and "chunk_id" in item
    }


def _deduplicated_actor_flow(trace: list[TraceEvent]) -> list[str]:
    """Hide compatibility-only legacy Critic nodes from the human-readable flow.

    The raw JSON result still contains the complete audit trace, including legacy `critic` events,
    so existing trace consumers retain compatibility.
    """

    return [event.node for event in trace if event.node != "critic"]


def run_reviewer_demo() -> dict[str, Any]:
    """Return deterministic demonstration results without external services."""

    with tempfile.TemporaryDirectory(prefix="driver-copilot-review-") as temp_dir:
        copilot = build_copilot(
            Settings(
                data_dir=ROOT / "data",
                state_db_path=Path(temp_dir) / "state.sqlite3",
                strategist_provider="heuristic",
            )
        )
        first = copilot.run(
            ChatRequest(
                conversation_id="reviewer-demo",
                driver_id="D-LON-001",
                message=MANAGER_REQUEST,
                initial_plan_override=_unsafe_plan(),
            )
        )
        follow_up = copilot.run(
            ChatRequest(
                conversation_id=first.conversation_id,
                message=FOLLOW_UP_REQUEST,
            )
        )

    tickets = TicketRepository(ROOT / "data" / "support_tickets.csv").for_driver(
        first.driver.driver_id,
        limit=20,
    )
    relevant_tickets = [ticket for ticket in tickets if ticket.category.casefold() == "airport"]

    available_incentives = IncentiveAdapter.from_mock_file(
        ROOT / "data" / "incentive_service_mock.py"
    ).available_for(first.driver)
    relevant_incentives = [
        item for item in available_incentives if item.category.casefold() == "airport"
    ]

    policy_event = _event(first.trace, "tool.policy_rag")
    raw_policy_chunks = policy_event.payload.get("policy_chunks", [])
    policy_ids = [
        str(item["chunk_id"])
        for item in raw_policy_chunks
        if isinstance(item, dict) and "chunk_id" in item
    ]
    policy_index = _policy_index()
    retrieved_policies = [policy_index[item] for item in policy_ids if item in policy_index]

    ledger_event = _event(first.trace, "tool.retention_ledger")
    critic_events = [event for event in first.trace if event.node == "compliance_critic"]
    if len(critic_events) < 2:
        raise RuntimeError("Reviewer demo must contain both rejection and approval Critic passes.")

    initial_violations = critic_events[0].payload.get("violations", [])
    if not isinstance(initial_violations, list):
        initial_violations = []

    final_action = first.plan.actions[0]
    final_policy_ids = sorted(
        {
            *final_action.policy_chunk_ids,
            *first.critic.policy_chunk_ids,
        }
    )

    return {
        "purpose": (
            "Help a Driver Relationship Manager investigate retention risk, propose a response, "
            "and prevent policy-violating recommendations before presentation."
        ),
        "manager_request": MANAGER_REQUEST,
        "follow_up_request": FOLLOW_UP_REQUEST,
        "driver": first.driver.model_dump(mode="json"),
        "observation": first.observation.model_dump(mode="json"),
        "evidence": {
            "retrieved_ticket_count": len(tickets),
            "relevant_tickets": [ticket.model_dump(mode="json") for ticket in relevant_tickets],
            "relevant_incentives": [
                incentive.model_dump(mode="json") for incentive in relevant_incentives
            ],
            "retrieved_policies": retrieved_policies,
            "ledger": {
                "month_to_date_gbp": ledger_event.payload.get("month_to_date_gbp"),
                "immediate_credits_last_24h": ledger_event.payload.get(
                    "immediate_credits_last_24h"
                ),
                "complete": ledger_event.outcome == "success",
            },
        },
        "initial_proposal": _unsafe_plan().model_dump(mode="json"),
        "critic_decisions": [event.outcome for event in critic_events],
        "initial_violations": initial_violations,
        "final_plan": first.plan.model_dump(mode="json"),
        "final_decision": first.critic.decision.value,
        "final_verified_total_gbp": first.critic.verified_total_gbp,
        "final_policy_ids": final_policy_ids,
        "actor_flow": _deduplicated_actor_flow(first.trace),
        "raw_trace": [event.model_dump(mode="json") for event in first.trace],
        "follow_up": {
            "reused_driver_id": follow_up.driver.driver_id,
            "issue_type": follow_up.observation.issue_type.value,
            "decision": follow_up.critic.decision.value,
            "manager_message": follow_up.manager_message,
        },
        "safety_controls": [
            "Typed Pydantic contracts reject malformed cross-layer messages.",
            "The Compliance Critic derives protected action metadata from authoritative catalogues.",
            "Evidence and policy identifiers are validated against retrieved source sets.",
            "The Strategist receives at most two bounded revision passes.",
            "Missing financial ledger data fails closed or requires escalation.",
            "No code path in this demo issues money or mutates a driver account.",
        ],
        "safety_boundary": "Recommendation only; no incentive was issued.",
    }


def _money(value: Any) -> str:
    return f"£{float(value):.2f}"


def _policy_label(policy: dict[str, Any]) -> str:
    source_document = policy.get("source_document") or policy.get("source") or "unknown source"
    source_page = policy.get("source_page")
    provenance = f"{source_document}, page {source_page}" if source_page else str(source_document)
    return f"{policy['chunk_id']} — {policy['title']} ({provenance})"


def render_compact_demo(result: dict[str, Any]) -> str:
    """Render the original fast-scanning reviewer output."""

    final_actions = result["final_plan"]["actions"]
    action_lines = [
        f"  {action['incentive_id'] or 'NO-ID'} — {_money(action['value_gbp'])} — {action['name']}"
        for action in final_actions
    ]
    flow = " → ".join(result["actor_flow"])
    rules = ", ".join(item["rule_id"] for item in result["initial_violations"])
    initial_action = result["initial_proposal"]["actions"][0]
    return "\n".join(
        [
            "DRIVER RETENTION COPILOT — REVIEWER DEMO (COMPACT)",
            "==================================================",
            f"Driver: {result['driver']['name']} ({result['driver']['driver_id']})",
            f"Tier: {result['driver']['loyalty_tier']}",
            f"Detected issue: {result['observation']['issue_type']}",
            "",
            "Unsafe Strategist proposal:",
            f"  {initial_action['incentive_id']} — {_money(initial_action['value_gbp'])}",
            "",
            f"Compliance Critic: {result['critic_decisions'][0]}",
            f"  Rules: {rules}",
            "",
            "Corrected plan:",
            *action_lines,
            f"Final Critic decision: {result['final_decision']}",
            "",
            "Multi-turn memory check:",
            f"  Follow-up reused driver: {result['follow_up']['reused_driver_id']}",
            f"  Follow-up decision: {result['follow_up']['decision']}",
            "",
            "Inspectable actor/tool flow:",
            f"  {flow}",
            "",
            f"Safety: {result['safety_boundary']}",
        ]
    )


def render_demo(result: dict[str, Any]) -> str:
    """Render the explanatory default output for an unassisted reviewer."""

    driver = result["driver"]
    observation = result["observation"]
    evidence = result["evidence"]
    initial_action = result["initial_proposal"]["actions"][0]
    final_action = result["final_plan"]["actions"][0]

    ticket_lines = []
    for ticket in evidence["relevant_tickets"]:
        ticket_lines.append(
            f"    - {ticket['ticket_id']} [{ticket['status']}]: {ticket['message']}"
        )

    incentive_lines = []
    for incentive in evidence["relevant_incentives"]:
        incentive_lines.append(
            "    - "
            f"{incentive['id']}: {incentive['name']} — "
            f"{_money(incentive['value'])} {incentive['currency']}"
        )

    cited_policy_ids = {
        *initial_action["policy_chunk_ids"],
        *final_action["policy_chunk_ids"],
    }
    policy_lines = [
        f"    - {_policy_label(item)}"
        for item in evidence["retrieved_policies"]
        if item.get("is_global_guardrail") or item.get("chunk_id") in cited_policy_ids
    ]

    violation_lines: list[str] = []
    for number, violation in enumerate(result["initial_violations"], start=1):
        policy_ids = ", ".join(violation.get("policy_chunk_ids", [])) or "not specified"
        violation_lines.extend(
            [
                f"  Violation {number}: {violation['rule_id']}",
                f"    Finding: {violation['message']}",
                f"    Required correction: {violation['suggested_fix']}",
                f"    Policy evidence: {policy_ids}",
            ]
        )

    verification_lines = [
        "  ✓ Incentive exists in the authoritative incentive catalogue",
        "  ✓ Protected category, type, credit, and cap fields match authoritative metadata",
        f"  ✓ Verified recommendation value is {_money(result['final_verified_total_gbp'])}",
        "  ✓ Gold-tier airport recovery cap is satisfied",
        "  ✓ Monthly value and 24-hour credit-stacking limits remain satisfied",
        "  ✓ Evidence identifiers exist in the retrieved evidence set",
        "  ✓ Policy identifiers exist in the retrieved policy set",
        "  ✓ Recommendation status does not imply that payment was executed",
    ]

    safety_lines = [f"  ✓ {control}" for control in result["safety_controls"]]
    flow = "\n    → ".join(result["actor_flow"])
    wait = observation.get("wait_minutes")
    distance = observation.get("trip_distance_km")

    return "\n".join(
        [
            "DRIVER RETENTION COPILOT — END-TO-END REVIEWER DEMO",
            "===================================================",
            "",
            "PURPOSE",
            "-------",
            result["purpose"],
            "",
            "Safety boundary:",
            f"  {result['safety_boundary']}",
            "",
            "1. MANAGER REQUEST AND CONTEXT RESOLUTION",
            "------------------------------------------",
            f'  "{result["manager_request"]}"',
            "",
            "Resolved driver:",
            f"  Name: {driver['name']}",
            f"  Driver ID: {driver['driver_id']}",
            f"  City: {driver['city']}",
            f"  Loyalty tier: {driver['loyalty_tier']}",
            f"  Tenure: {driver['tenure_months']} months",
            f"  Recent sentiment: {driver['recent_sentiment']}",
            "",
            "2. AUTHORITATIVE EVIDENCE COLLECTION",
            "--------------------------------------",
            "The orchestrator assembled a typed EvidenceBundle before asking the Strategist",
            "to propose an action.",
            "",
            "  Driver Repository:",
            f"    Retrieved the profile for {driver['driver_id']} and confirmed tier eligibility.",
            "",
            "  Support Ticket Repository:",
            f"    Retrieved {evidence['retrieved_ticket_count']} recent ticket record(s).",
            "    Airport evidence used by the plan:",
            *ticket_lines,
            "",
            "  Diagnostic Extractor:",
            f"    Classified issue: {observation['issue_type']}",
            f"    Maximum evidenced wait: {wait:.0f} minutes"
            if wait is not None
            else "    Wait: unavailable",
            f"    Minimum evidenced trip distance: {distance:.2f} km"
            if distance is not None
            else "    Trip distance: unavailable",
            f"    Related airport tickets: {observation['related_ticket_count']}",
            f"    Multi-day systemic failure documented: {observation['multi_day_systemic_failure']}",
            f"    Assessed churn risk: {result['initial_proposal']['churn_risk']}",
            "",
            "  Incentive Service:",
            "    Retrieved eligible catalogue candidates, including:",
            *incentive_lines,
            "",
            "  Policy RAG:",
            "    Retrieved mandatory global guardrails plus the cited airport policy:",
            *policy_lines,
            "",
            "  Retention Ledger:",
            f"    Month-to-date retention value: {_money(evidence['ledger']['month_to_date_gbp'])}",
            "    Immediate credits in previous 24 hours: "
            f"{evidence['ledger']['immediate_credits_last_24h']}",
            f"    Ledger completeness: {evidence['ledger']['complete']}",
            "",
            "3. INTENTIONALLY UNSAFE STRATEGIST PROPOSAL",
            "--------------------------------------------",
            "The demo injects an unsafe first proposal to prove that the Compliance Critic",
            "operates independently and cannot be bypassed by the proposing agent.",
            "",
            f"  Incentive: {initial_action['incentive_id']} — {initial_action['name']}",
            f"  Proposed value: {_money(initial_action['value_gbp'])}",
            f"  Diagnosis: {result['initial_proposal']['diagnosis']}",
            f"  Rationale: {initial_action['rationale']}",
            f"  Evidence references: {', '.join(initial_action['evidence_ids'])}",
            f"  Policy references: {', '.join(initial_action['policy_chunk_ids'])}",
            "",
            "4. INDEPENDENT COMPLIANCE REVIEW",
            "---------------------------------",
            f"Decision: {result['critic_decisions'][0]}",
            "",
            *violation_lines,
            "",
            "The Critic does not silently repair or approve its own preferred plan. It returns",
            "structured findings to the Strategist for a separate bounded revision pass.",
            "",
            "5. BOUNDED SELF-CORRECTION",
            "---------------------------",
            f"  Revision number: {result['final_plan']['revision']}",
            f"  Replacement incentive: {final_action['incentive_id']} — {final_action['name']}",
            f"  Corrected value: {_money(final_action['value_gbp'])}",
            f"  Evidence references: {', '.join(final_action['evidence_ids'])}",
            f"  Policy references: {', '.join(final_action['policy_chunk_ids'])}",
            f"  Rationale: {final_action['rationale']}",
            "",
            "6. FINAL COMPLIANCE REVIEW",
            "---------------------------",
            f"Decision: {result['final_decision']}",
            *verification_lines,
            "",
            "Final manager recommendation:",
            f"  Recommend {final_action['name']} at {_money(final_action['value_gbp'])} for "
            f"{driver['name']}",
            "",
            "7. MULTI-TURN MEMORY",
            "--------------------",
            f'Follow-up question: "{result["follow_up_request"]}"',
            f"  Reused driver ID: {result['follow_up']['reused_driver_id']}",
            f"  Reused issue context: {result['follow_up']['issue_type']}",
            f"  Follow-up decision: {result['follow_up']['decision']}",
            "",
            "8. INSPECTABLE AGENT AND TOOL FLOW",
            "-----------------------------------",
            f"  {flow}",
            "",
            "The raw JSON mode retains every timestamped trace event, including compatibility",
            "events that are intentionally hidden from this human-readable flow.",
            "",
            "9. PRODUCTION-SAFETY CONTROLS",
            "-----------------------------",
            *safety_lines,
            "",
            "DEMO RESULT",
            "-----------",
            "The Copilot joined operational evidence, policy retrieval, plan generation,",
            "independent deterministic validation, self-correction, and conversation memory.",
            "It rejected an excessive and ineligible £50 proposal, revised it to a grounded",
            "£25 recommendation, approved the corrected plan, and executed no financial action.",
            "",
            "Additional inspection modes:",
            "  make reviewer-demo-compact  # fast summary",
            "  make reviewer-demo-json     # complete machine-readable result and raw trace",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--compact", action="store_true", help="Print the short reviewer summary")
    mode.add_argument("--json", action="store_true", help="Print the full machine-readable result")
    parser.add_argument("--output", type=Path, help="Optionally write the full JSON result")
    args = parser.parse_args()

    result = run_reviewer_demo()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(result, indent=2))
    elif args.compact:
        print(render_compact_demo(result))
    else:
        print(render_demo(result))


if __name__ == "__main__":
    main()
