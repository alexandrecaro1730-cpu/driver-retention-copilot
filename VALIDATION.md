# Validation Report

Validated in a clean Python 3.13 virtual environment on 2026-06-22.

| Check | Result |
|---|---|
| Editable installation | Passed |
| `pip check` in clean environment | Passed |
| Ruff lint | Passed |
| Ruff formatting | Passed |
| Strict mypy | Passed |
| Bandit static security scan | Passed |
| Pytest | 71 passed |
| Branch-aware coverage | 88.74% (gate: 85%) |
| CLI Maria scenario | Passed |
| Reject → revise → approve trace | Passed |
| Python compilation | Passed |

`pip-audit` is configured in CI. The local vulnerability database lookup could not complete because
this execution sandbox could not resolve the public PyPI audit endpoint. This is an environment
limitation, not a passing audit result.
