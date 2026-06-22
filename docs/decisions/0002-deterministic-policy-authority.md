# ADR 0002: Deterministic code is the compliance authority

**Status:** Accepted

LLMs may generate and explain strategies but may not decide numerical caps, stacking limits, or tier
eligibility. Pure Python rules emit stable IDs and the Critic verdict. This reduces hallucination risk,
supports auditability, and allows boundary-value tests. Policy-as-code must remain synchronised with
the versioned source document and reviewed by policy owners.
