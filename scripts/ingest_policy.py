"""Parse a Markdown, text, or PDF policy into inspectable clause JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.rag.policy_store import PolicyStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/policy_chunks.json"))
    args = parser.parse_args()

    chunks = PolicyStore.from_path(args.source).all()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps([chunk.model_dump(mode="json") for chunk in chunks], indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(chunks)} chunks to {args.output}")


if __name__ == "__main__":
    main()
