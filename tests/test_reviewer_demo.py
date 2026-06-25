"""End-to-end reviewer demonstration tests."""

from scripts.reviewer_demo import render_compact_demo, render_demo, run_reviewer_demo


def test_reviewer_demo_proves_reject_revise_approve_and_memory() -> None:
    result = run_reviewer_demo()

    assert result["critic_decisions"] == ["REJECT", "APPROVE"]
    assert result["final_decision"] == "APPROVE"
    assert result["final_plan"]["actions"][0]["incentive_id"] == "INC-001"
    assert result["final_plan"]["actions"][0]["value_gbp"] == 25
    assert result["follow_up"]["reused_driver_id"] == "D-LON-001"
    assert result["follow_up"]["issue_type"] == "airport_short_fare"
    assert "strategist" in result["actor_flow"]
    assert "compliance_critic" in result["actor_flow"]


def test_reviewer_demo_contains_grounded_evidence_and_policy_details() -> None:
    result = run_reviewer_demo()

    ticket_ids = {item["ticket_id"] for item in result["evidence"]["relevant_tickets"]}
    incentive_ids = {item["id"] for item in result["evidence"]["relevant_incentives"]}
    policy_ids = {item["chunk_id"] for item in result["evidence"]["retrieved_policies"]}
    rule_ids = {item["rule_id"] for item in result["initial_violations"]}

    assert {"T-1001", "T-1007"} <= ticket_ids
    assert {"INC-001", "INC-002"} <= incentive_ids
    assert {"A.1", "A.2", "A.3", "B.1"} <= policy_ids
    assert rule_ids == {"B.1_TIER_CAP", "B.1_INC002_RESTRICTED"}
    assert result["evidence"]["ledger"]["complete"] is True


def test_reviewer_demo_default_text_explains_the_full_value_chain() -> None:
    text = render_demo(run_reviewer_demo())

    assert "1. MANAGER REQUEST AND CONTEXT RESOLUTION" in text
    assert "2. AUTHORITATIVE EVIDENCE COLLECTION" in text
    assert "T-1001" in text
    assert "B.1 — Airport Short Fares" in text
    assert "3. INTENTIONALLY UNSAFE STRATEGIST PROPOSAL" in text
    assert "4. INDEPENDENT COMPLIANCE REVIEW" in text
    assert "B.1_TIER_CAP" in text
    assert "5. BOUNDED SELF-CORRECTION" in text
    assert "6. FINAL COMPLIANCE REVIEW" in text
    assert "7. MULTI-TURN MEMORY" in text
    assert "8. INSPECTABLE AGENT AND TOOL FLOW" in text
    assert "9. PRODUCTION-SAFETY CONTROLS" in text
    assert "Recommendation only; no incentive was issued" in text
    assert "→ critic" not in text


def test_reviewer_demo_compact_text_remains_available() -> None:
    text = render_compact_demo(run_reviewer_demo())

    assert "REVIEWER DEMO (COMPACT)" in text
    assert "Compliance Critic: REJECT" in text
    assert "Final Critic decision: APPROVE" in text
    assert "Recommendation only" in text
    assert "→ critic" not in text
