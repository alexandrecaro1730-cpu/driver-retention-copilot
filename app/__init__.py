"""Driver Retention Copilot.

Business intent
---------------
Help Driver Relationship Managers respond consistently and quickly while ensuring that
financial recovery actions never bypass policy guardrails.

Technical intent
----------------
Keep orchestration, evidence retrieval, strategy generation, and compliance validation as
separate replaceable components. The package is deliberately runnable without an LLM so that
reviewers can reproduce every test and evaluation trace offline.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
