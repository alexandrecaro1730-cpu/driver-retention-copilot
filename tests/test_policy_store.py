from pathlib import Path

import pytest
from app.domain.enums import IssueType, LoyaltyTier
from app.rag.policy_store import PolicyStore


def test_policy_chunks_by_clause(data_dir: Path) -> None:
    store = PolicyStore.from_path(data_dir / "uk_driver_retention_recovery.md")
    assert {chunk.chunk_id for chunk in store.all()} == {
        "A.1",
        "A.2",
        "A.3",
        "B.1",
        "B.2",
        "B.3",
        "B.4",
    }


def test_retrieval_always_includes_global_guardrails(data_dir: Path) -> None:
    store = PolicyStore.from_path(data_dir / "uk_driver_retention_recovery.md")
    result = store.retrieve(
        "airport fare", issue_type=IssueType.AIRPORT_SHORT_FARE, tier=LoyaltyTier.GOLD
    )
    ids = {chunk.chunk_id for chunk in result}
    assert {"A.1", "A.2", "A.3", "B.1"} <= ids


def test_retrieval_selects_technical_clause(data_dir: Path) -> None:
    store = PolicyStore.from_path(data_dir / "uk_driver_retention_recovery.md")
    result = store.retrieve(
        "GPS geofence", issue_type=IssueType.TECHNICAL_GPS, tier=LoyaltyTier.SILVER
    )
    assert "B.2" in [chunk.chunk_id for chunk in result]


def test_get_clause(data_dir: Path) -> None:
    store = PolicyStore.from_path(data_dir / "uk_driver_retention_recovery.md")
    assert "£150" in store.get("A.1").text


def test_invalid_policy_fails_fast(tmp_path: Path) -> None:
    path = tmp_path / "bad.md"
    path.write_text("no recognised clauses", encoding="utf-8")
    with pytest.raises(ValueError):
        PolicyStore.from_path(path)


def test_parser_accepts_plain_pdf_style_section_numbering(tmp_path: Path) -> None:
    path = tmp_path / "extracted.txt"
    path.write_text(
        "Section A: Caps\n"
        "1. Global Monthly Cap\n"
        "No package may exceed £150.\n"
        "2. Credit Stacking\n"
        "No more than two credits.\n"
        "Section B: Resolutions\n"
        "1. Airport Short Fares\n"
        "Wait above 90 minutes and distance below 3 km.\n",
        encoding="utf-8",
    )
    store = PolicyStore.from_path(path)
    assert [chunk.chunk_id for chunk in store.all()] == ["A.1", "A.2", "B.1"]


def test_policy_chunks_preserve_document_provenance(data_dir: Path) -> None:
    path = data_dir / "uk_driver_retention_recovery.md"
    chunk = PolicyStore.from_path(path).get("B.1")

    assert chunk.source_document == path.name
    assert chunk.source_sha256 is not None
    assert len(chunk.source_sha256) == 64
    assert chunk.source_page is None


def test_page_markers_are_preserved_on_chunks() -> None:
    chunks = PolicyStore._chunk_text(
        "[[PAGE:2]]\nA.1 Global Cap\nNo package may exceed £150.\n",
        source="policy.pdf",
        source_document="policy.pdf",
        source_sha256="a" * 64,
    )

    assert chunks[0].source_page == 2
    assert chunks[0].source_document == "policy.pdf"
