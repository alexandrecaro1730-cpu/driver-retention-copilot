"""Auditable policy RAG for a small, high-stakes corpus.

Business intent
---------------
Every recommendation and compliance decision should cite the exact policy clause that authorised or
blocked it, together with document provenance when available.

Technical intent
----------------
For this small document, heading-aware chunks plus metadata and lexical ranking are more transparent
than an opaque embedding-only index. Global guardrails are always injected. PDF ingestion preserves
the page on which a clause begins and a SHA-256 digest of the source document.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.domain.enums import IssueType, LoyaltyTier
from app.domain.models import PolicyChunk

_HEADING = re.compile(r"^(?:###\s+)?([A-Z]\.\d+)\s*[:.\-]?\s+(.+)$")
_SECTION = re.compile(r"^(?:##\s+)?Section\s+([A-Z])\b", re.I)
_NUMBERED_HEADING = re.compile(r"^(?:###\s+)?(\d+)\.\s+(.+)$")
_PAGE_MARKER = re.compile(r"^\[\[PAGE:(\d+)\]\]$")
_TOKEN = re.compile(r"[a-z0-9]+")

_ISSUE_TAGS: dict[str, list[IssueType]] = {
    "B.1": [IssueType.AIRPORT_SHORT_FARE],
    "B.2": [IssueType.TECHNICAL_GPS],
    "B.3": [IssueType.NEW_STARTER],
    "B.4": [IssueType.QUEST],
}


class PolicyStore:
    def __init__(self, chunks: list[PolicyChunk]):
        self._chunks = chunks
        self._by_id = {chunk.chunk_id: chunk for chunk in chunks}

    @classmethod
    def from_path(cls, path: Path) -> PolicyStore:
        source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.suffix.casefold() == ".pdf":
            text = cls._read_pdf_with_page_markers(path)
        else:
            text = path.read_text(encoding="utf-8")
        return cls(
            cls._chunk_text(
                text,
                source=str(path),
                source_document=path.name,
                source_sha256=source_sha256,
            )
        )

    @staticmethod
    def _read_pdf_with_page_markers(path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError("Install the 'pdf' extra to ingest PDF policies") from exc

        reader = PdfReader(str(path))
        sections: list[str] = []
        for page_number, page in enumerate(reader.pages, start=1):
            sections.append(f"[[PAGE:{page_number}]]")
            sections.append(page.extract_text() or "")
        return "\n".join(sections)

    @staticmethod
    def _chunk_text(
        text: str,
        *,
        source: str,
        source_document: str,
        source_sha256: str,
    ) -> list[PolicyChunk]:
        chunks: list[PolicyChunk] = []
        current_id: str | None = None
        current_title: str | None = None
        current_page: int | None = None
        clause_page: int | None = None
        body: list[str] = []

        def flush() -> None:
            if current_id is None or current_title is None:
                return
            chunk_text = " ".join(line.strip() for line in body if line.strip())
            tiers = [tier for tier in LoyaltyTier if tier.value.casefold() in chunk_text.casefold()]
            chunks.append(
                PolicyChunk(
                    chunk_id=current_id,
                    title=current_title,
                    text=chunk_text,
                    issue_types=_ISSUE_TAGS.get(current_id, []),
                    tiers=tiers,
                    is_global_guardrail=current_id.startswith("A."),
                    source=source,
                    source_document=source_document,
                    source_page=clause_page,
                    source_sha256=source_sha256,
                )
            )

        section_letter: str | None = None
        for line in text.splitlines():
            stripped = line.strip()
            if page_match := _PAGE_MARKER.match(stripped):
                current_page = int(page_match.group(1))
                continue

            section_match = _SECTION.match(stripped)
            if section_match:
                section_letter = section_match.group(1).upper()
                continue

            match = _HEADING.match(stripped)
            numbered_match = _NUMBERED_HEADING.match(stripped) if section_letter else None
            if match:
                flush()
                current_id, current_title = match.group(1), match.group(2)
                section_letter = current_id.split(".", maxsplit=1)[0]
                clause_page = current_page
                body = []
            elif numbered_match and section_letter:
                flush()
                current_id = f"{section_letter}.{numbered_match.group(1)}"
                current_title = numbered_match.group(2)
                clause_page = current_page
                body = []
            elif current_id is not None:
                body.append(line)
        flush()

        if not chunks:
            raise ValueError(f"No policy clauses could be parsed from {source}")
        return chunks

    def retrieve(
        self,
        query: str,
        *,
        issue_type: IssueType,
        tier: LoyaltyTier,
        top_k: int = 6,
    ) -> list[PolicyChunk]:
        query_tokens = set(_TOKEN.findall(query.casefold()))
        selected = [chunk for chunk in self._chunks if chunk.is_global_guardrail]

        def score(chunk: PolicyChunk) -> tuple[int, str]:
            text_tokens = set(_TOKEN.findall(f"{chunk.title} {chunk.text}".casefold()))
            overlap = len(query_tokens & text_tokens)
            metadata = 5 if issue_type in chunk.issue_types else 0
            tier_bonus = 1 if tier in chunk.tiers else 0
            return (overlap + metadata + tier_bonus, chunk.chunk_id)

        ranked = sorted(
            (chunk for chunk in self._chunks if not chunk.is_global_guardrail),
            key=score,
            reverse=True,
        )
        for chunk in ranked:
            if chunk not in selected:
                selected.append(chunk)
            if len(selected) >= top_k:
                break
        return selected[:top_k]

    def get(self, chunk_id: str) -> PolicyChunk:
        return self._by_id[chunk_id]

    def all(self) -> list[PolicyChunk]:
        return list(self._chunks)
