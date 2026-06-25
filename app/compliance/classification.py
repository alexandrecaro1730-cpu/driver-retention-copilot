"""Authoritative action classification for compliance checks.

Business intent
---------------
A model must not decide which financial guardrails apply to its own proposal. Catalogue-backed
properties are therefore derived from the Incentive Service response, while explicitly supported
policy actions are defined in code.

Technical intent
----------------
This module converts an untrusted ``ProposedAction`` into deterministic attributes used by the
Compliance Critic. Presentation fields remain on the proposal for manager readability, but they do
not control cap, stacking, category, or action-type enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import ActionType
from app.domain.models import EvidenceBundle, Incentive, ProposedAction


@dataclass(frozen=True)
class PolicyActionDefinition:
    """Authoritative metadata for a policy-defined action absent from the mock catalogue."""

    action_type: ActionType
    category: str
    immediate_credit: bool


POLICY_ACTIONS: dict[str, PolicyActionDefinition] = {
    "POLICY-QUEST-20": PolicyActionDefinition(
        action_type=ActionType.CREDIT,
        category="Quest",
        immediate_credit=True,
    )
}

# The mock labels priority support as CREDIT despite carrying no monetary value. The business action
# is support access, so the deterministic boundary corrects that catalogue inconsistency.
_ACTION_TYPE_OVERRIDES: dict[str, ActionType] = {
    "INC-004": ActionType.SUPPORT,
}

_TYPE_MAP: dict[str, ActionType] = {
    "CREDIT": ActionType.CREDIT,
    "DISCOUNT": ActionType.DISCOUNT,
    "QUEST": ActionType.QUEST,
    "SUPPORT": ActionType.SUPPORT,
}


@dataclass(frozen=True)
class AuthoritativeAction:
    """Compliance-relevant interpretation of a proposed action."""

    category: str
    action_type: ActionType
    counts_toward_monthly_cap: bool
    immediate_credit: bool
    catalogue_item: Incentive | None
    source: str


def _catalogue_item(action: ProposedAction, evidence: EvidenceBundle) -> Incentive | None:
    if action.incentive_id is None:
        return None
    return next((item for item in evidence.incentives if item.id == action.incentive_id), None)


def classify_action(action: ProposedAction, evidence: EvidenceBundle) -> AuthoritativeAction:
    """Derive guardrail attributes without trusting model-controlled classification flags."""

    catalogue_item = _catalogue_item(action, evidence)
    if catalogue_item is not None:
        action_type = _ACTION_TYPE_OVERRIDES.get(
            catalogue_item.id,
            _TYPE_MAP.get(catalogue_item.type.upper(), action.action_type),
        )
        category = catalogue_item.category
        source = "incentive_service"
    elif action.incentive_id in POLICY_ACTIONS:
        definition = POLICY_ACTIONS[action.incentive_id]
        action_type = definition.action_type
        category = definition.category
        source = "policy_action_registry"
    else:
        action_type = action.action_type
        category = action.category
        source = "proposal"

    counts_toward_monthly_cap = action.value_gbp > 0
    if action.incentive_id in POLICY_ACTIONS:
        immediate_credit = (
            POLICY_ACTIONS[action.incentive_id].immediate_credit and action.value_gbp > 0
        )
    else:
        immediate_credit = action_type is ActionType.CREDIT and action.value_gbp > 0

    return AuthoritativeAction(
        category=category,
        action_type=action_type,
        counts_toward_monthly_cap=counts_toward_monthly_cap,
        immediate_credit=immediate_credit,
        catalogue_item=catalogue_item,
        source=source,
    )


def verified_total_gbp(plan_actions: list[ProposedAction]) -> float:
    """Return all positive GBP value, independent of proposal flags."""

    return round(sum(action.value_gbp for action in plan_actions), 2)
