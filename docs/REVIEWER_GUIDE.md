# Reviewer Guide — Five-Minute Path

## 1. Run the explanatory business demonstration

```bash
make reviewer-demo
```

This command uses no external API and is designed to stand on its own without a presentation. It
shows:

- the manager request and Maria's resolved driver context;
- the profile, support-ticket, eligible-incentive, policy-RAG, and ledger evidence;
- the intentionally unsafe £50 proposal;
- the independent Compliance Critic's named policy findings;
- the Strategist's bounded £25 correction;
- the second Critic pass and final approval;
- a follow-up turn that reuses the same driver and issue context;
- the agent/tool audit flow and the recommendation-only safety boundary.

Alternative views:

```bash
make reviewer-demo-compact  # short terminal summary
make reviewer-demo-json     # complete structured result and raw timestamped trace
```

## 2. Inspect requirement coverage

| Requirement | Implementation | Primary evidence |
|---|---|---|
| Multi-agent orchestration | Strategist proposes/revises; independent Critic validates | `app/orchestration/copilot.py` |
| Tool use | Driver, ticket, ledger, incentive, and policy boundaries | `app/data/`, `app/integrations/`, `app/rag/` |
| RAG | Clause-aware retrieval with mandatory global guardrails | `app/rag/policy_store.py` |
| State and memory | SQLite conversation checkpoints | `app/memory/sqlite_store.py` |
| Self-correction | REJECT → revision → APPROVE | `evaluations/` |
| Automated evaluation | Unit, integration, contract, trace, and failure tests | `tests/` |
| UI stretch goal | Streamlit manager interface | `app/ui/streamlit_app.py` |

## 3. Inspect the safety boundary

The model cannot decide which guardrails apply to its own output. The Critic derives category, action
type, immediate-credit status, and cap treatment from the Incentive Service or the registered policy
action catalogue. It also rejects invented ticket and policy references.

Relevant files:

```text
app/compliance/classification.py
app/compliance/rules.py
tests/test_compliance_hardening.py
```

## 4. Inspect the evaluation evidence

```text
evaluations/maria_self_correction.json
evaluations/manual_self_correction/01_rejected.json
evaluations/manual_self_correction/revision_request.json
evaluations/manual_self_correction/02_corrected.json
```

## 5. Run the complete quality gate

```bash
make quality
```

The repository is recommendation-only: it never issues an incentive or mutates a driver account.
