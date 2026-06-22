# Git Workflow

Use lightweight trunk-based development with protected `main`.

## Branches

- `feat/<short-description>` for product work.
- `fix/<short-description>` for defects.
- `chore/<short-description>` for maintenance.
- `docs/<short-description>` for documentation-only changes.

Keep branches short-lived and rebase before review. Do not commit directly to protected `main`.

## Commits

Use Conventional Commits:

```text
feat(compliance): enforce airport tier caps
fix(memory): exclude computed fields from checkpoints
test(orchestration): cover critic self-correction loop
docs(design): explain fail-closed ledger behaviour
```

Each commit should compile and preferably pass focused tests. Avoid mixing formatting, refactors, and
behavioural changes in one commit.

## Pull requests

A PR requires:

- problem and business intent;
- technical approach and alternatives;
- tests and evaluation evidence;
- policy or security impact;
- rollout/rollback note;
- green CI on all supported Python versions;
- at least one reviewer for business-rule changes.

Changes to `app/compliance/`, policy source files, or execution integrations require CODEOWNER review.
Squash merge feature branches. Tag releases with Semantic Versioning and update `CHANGELOG.md`.

## Suggested first commit sequence

```bash
git init
git checkout -b feat/initial-copilot

git add pyproject.toml app/domain app/data app/integrations
git commit -m "feat(core): add typed domain and data tools"

git add app/rag app/diagnostics app/compliance
git commit -m "feat(compliance): add policy retrieval and deterministic guardrails"

git add app/agents app/orchestration app/memory app/api.py app/cli.py
git commit -m "feat(orchestration): add strategist critic correction loop"

git add tests evaluations scripts
git commit -m "test(system): add rule and self-correction coverage"

git add Dockerfile compose.yaml .github docs README.md
git commit -m "chore(delivery): add CI container and documentation"
```
