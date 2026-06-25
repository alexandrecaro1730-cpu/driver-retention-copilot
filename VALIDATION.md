# Validation Report

Validated in the upgrade build environment on 2026-06-25 using Python 3.13.5.

| Check | Result |
|---|---|
| Python compilation (`app`, `scripts`, `tests`) | Passed |
| Ruff lint | Passed |
| Ruff formatting | Passed: 63 files formatted |
| Strict mypy | Passed: 38 source files |
| Bandit static security scan | Passed: no issues identified |
| Pytest | 105 passed |
| Branch-aware coverage | 87.86% (gate: 85%) |
| Reviewer demo | Passed: REJECT → revision → APPROVE + memory follow-up |
| Deterministic evaluation trace | Passed |
| Human-mediated evaluation artifacts | Passed |
| Metadata-bypass regression tests | Passed |
| Citation-grounding regression tests | Passed |
| Policy provenance tests | Passed |

`pip-audit` could not query PyPI from this build sandbox because external DNS resolution is disabled.
The apply script runs `make quality`, including pip-audit, in the user's network-enabled development
environment. No runtime dependency ranges were added by this upgrade.

A Starlette/httpx deprecation warning may appear during tests; it originates from the test dependency
stack and does not affect application behavior.
