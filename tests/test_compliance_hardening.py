"""Regression tests for model-to-policy trust boundaries."""

from app.compliance.engine import ComplianceCritic
from app.domain.enums import ActionType, Decision

from tests.factories import action, evidence, plan


def rule_ids(result) -> set[str]:
    return {finding.rule_id for finding in result.violations}


def test_category_spoof_cannot_evade_airport_rules() -> None:
    result = ComplianceCritic().validate(
        plan(action(incentive_id="INC-002", category="Engagement", value=50)),
        evidence(),
    )

    assert result.decision is Decision.REJECT
    assert {
        "ACTION_CATEGORY_MISMATCH",
        "B.1_TIER_CAP",
        "B.1_INC002_RESTRICTED",
    } <= rule_ids(result)


def test_model_flag_cannot_exclude_positive_gbp_from_monthly_cap() -> None:
    result = ComplianceCritic().validate(
        plan(action(value=25, counts_toward_monthly_cap=False)),
        evidence(mtd=140),
    )

    assert result.verified_total_gbp == 25
    assert {"ACTION_CAP_BYPASS_ATTEMPT", "A.1_MONTHLY_CAP"} <= rule_ids(result)


def test_model_flag_cannot_hide_credit_from_stacking_rule() -> None:
    result = ComplianceCritic().validate(
        plan(action(value=25, immediate=False)),
        evidence(credits=2),
    )

    assert result.decision is Decision.ESCALATE
    assert {
        "ACTION_CREDIT_CLASSIFICATION_MISMATCH",
        "A.2_CREDIT_STACKING",
    } <= rule_ids(result)


def test_catalogue_action_type_mismatch_is_rejected() -> None:
    result = ComplianceCritic().validate(
        plan(action(value=25, action_type=ActionType.SUPPORT)),
        evidence(),
    )

    assert "ACTION_TYPE_MISMATCH" in rule_ids(result)


def test_unsourced_monetary_value_is_rejected() -> None:
    result = ComplianceCritic().validate(
        plan(action(incentive_id=None, value=10)),
        evidence(),
    )

    assert "ACTION_UNSOURCED_MONETARY_VALUE" in rule_ids(result)


def test_unknown_policy_action_is_rejected() -> None:
    result = ComplianceCritic().validate(
        plan(action(incentive_id="POLICY-NOT-REAL", value=10)),
        evidence(),
    )

    assert "ACTION_UNKNOWN_POLICY_ACTION" in rule_ids(result)


def test_catalogue_value_cannot_be_exceeded() -> None:
    result = ComplianceCritic().validate(
        plan(action(incentive_id="INC-003", category="Technical", value=15)),
        evidence(),
    )

    assert "ACTION_VALUE_EXCEEDS_CATALOGUE" in rule_ids(result)


def test_invented_evidence_reference_is_rejected() -> None:
    result = ComplianceCritic().validate(
        plan(action(evidence_ids=["T-NOT-REAL"])),
        evidence(),
    )

    assert "GROUNDING_UNKNOWN_EVIDENCE" in rule_ids(result)


def test_invented_policy_reference_is_rejected() -> None:
    result = ComplianceCritic().validate(
        plan(action(policy_chunk_ids=["Z.99"])),
        evidence(),
    )

    assert "GROUNDING_UNKNOWN_POLICY" in rule_ids(result)


def test_financial_action_requires_evidence_and_policy_citations() -> None:
    result = ComplianceCritic().validate(
        plan(action(evidence_ids=[], policy_chunk_ids=[])),
        evidence(),
    )

    assert {
        "GROUNDING_MISSING_EVIDENCE",
        "GROUNDING_MISSING_POLICY",
    } <= rule_ids(result)


def test_structured_evidence_references_are_accepted() -> None:
    result = ComplianceCritic().validate(
        plan(
            action(
                evidence_ids=[
                    "profile.loyalty_tier",
                    "observation.wait_minutes",
                    "observation.trip_distance_km",
                    "ledger.month_to_date_gbp",
                ],
                policy_chunk_ids=["A.1", "A.2", "B.1"],
            )
        ),
        evidence(),
    )

    assert result.decision is Decision.APPROVE
