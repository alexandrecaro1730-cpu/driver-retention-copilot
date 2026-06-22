# ADR 0001: Use an explicit state machine for the take-home

**Status:** Accepted

A custom typed loop is used instead of LangGraph. The workflow has few nodes, no parallel long-running
work, and a strict maximum of two revisions. An explicit implementation improves reviewer visibility,
offline reproducibility, and test coverage while retaining interfaces that permit a future LangGraph
migration. Reconsider when human interrupts, distributed checkpoints, or dynamic graph composition
become requirements.
