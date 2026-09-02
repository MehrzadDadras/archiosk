"""Targeted regression coverage for aggregate Spin evidence packing."""
from unittest.mock import patch

from services.llm_gateway import LLMCallOutcome
from services.spin import (
    SPIN_KIND_FIRST,
    _MAX_DOCUMENT_EVIDENCE_CHARS_IN_PROMPT,
    _select_comprehensive_document_evidence,
    run_spin,
)


def _doc(name, category="project_document", authority=None, excerpts=None, **extra):
    return {
        "filename": name,
        "relative_path": name,
        "source_id": name,
        "source_type": category,
        "document_authority": authority,
        "excerpts": excerpts or [f"evidence from {name}"],
        **extra,
    }


def _chars(selected):
    return sum(len(item) for doc in selected for item in doc["excerpts"])


def test_aggregate_evidence_strictly_obeys_character_budget():
    docs = [_doc(f"doc-{i}.pdf", excerpts=["x" * 41] * 8) for i in range(8)]
    selected = _select_comprehensive_document_evidence(docs, None, max_evidence_chars=500)
    assert _chars(selected) <= 500
    assert _chars(selected) == 492


def test_governing_source_survives_before_auxiliary_under_tight_budget():
    docs = [
        _doc("site-visit-register.pdf", authority="informational", excerpts=["a" * 100]),
        _doc("project-agreement.pdf", authority="project_agreement", excerpts=["g" * 100]),
    ]
    selected = _select_comprehensive_document_evidence(docs, None, max_evidence_chars=100)
    assert [doc["filename"] for doc in selected] == ["project-agreement.pdf"]


def test_distinct_source_classes_keep_representative_breadth():
    docs = [
        _doc("RFP.pdf", excerpts=["r" * 50]),
        _doc("Addendum-1.pdf", excerpts=["a" * 50]),
        _doc("Mechanical Drawings.pdf", excerpts=["m" * 50]),
        _doc("RFP-appendix.pdf", excerpts=["p" * 50]),
    ]
    selected = _select_comprehensive_document_evidence(docs, None, max_evidence_chars=150)
    assert {doc["source_class"] for doc in selected} == {
        "procurement_governing", "addendum_amendment", "coordination",
    }


def test_small_corpus_keeps_all_evidence_unhindered():
    docs = [_doc("RFP.pdf", excerpts=["one", "two"]), _doc("schedule.pdf", excerpts=["three"])]
    selected = _select_comprehensive_document_evidence(docs, None)
    assert sum(len(doc["excerpts"]) for doc in selected) == 3
    assert {doc["filename"] for doc in selected} == {"RFP.pdf", "schedule.pdf"}
    assert _chars(selected) < _MAX_DOCUMENT_EVIDENCE_CHARS_IN_PROMPT


def test_delta_changed_source_priority_remains_intact_within_source_class():
    docs = [
        _doc("old-drawing.pdf", excerpts=["o" * 60]),
        _doc("changed-drawing.pdf", excerpts=["c" * 60]),
    ]
    selected = _select_comprehensive_document_evidence(
        docs, {"changed-drawing.pdf"}, max_evidence_chars=60,
    )
    assert [doc["filename"] for doc in selected] == ["changed-drawing.pdf"]
    assert selected[0]["is_changed_since_baseline"] is True


def test_run_reports_known_vs_examined_coverage_from_the_actual_pack():
    docs = [_doc("project-agreement.pdf", excerpts=["g" * 60_000]), _doc("register.pdf", excerpts=["a" * 60_000])]
    with patch(
        "services.spin.call_llm_json",
        return_value=LLMCallOutcome(ran=True, parsed={"findings": []}),
    ):
        result = run_spin(SPIN_KIND_FIRST, "founding.pdf", [], [], [], additional_document_evidence=docs)
    assert result.evidence_sources_considered == 2
    assert result.evidence_sources_included == 1
    assert result.evidence_items_considered == 2
    assert result.total_evidence_items_budgeted == 1
    assert result.evidence_chars_budgeted == 60_000