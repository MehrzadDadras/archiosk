"""
CLAUDE-P21 - the candidate admission gate's shared record shape and its
ONE genuinely model-independent check.

Pure data + pure functions only (like mutation_schema.py and run_record.py)
- no imports from services/, no model calls in this module. The real,
billed adversarial-review model call lives in tools/self_test_admission_
review.py, which is a lab script, not this module.

`deterministic_ceiling_check` is the ONE piece of this admission process
that is NOT the same model reviewing its own output: it extracts the
numeric chlorine-ppm ceiling and pH range each requirement's text
literally states, via plain regex, and mechanically checks the
inequality - no LLM call, Claude or otherwise, is involved. It cannot
judge SCOPE overlap (whether "dosing system wetted components" really
falls within "pipe, fittings, valves, and pump casings... in contact
with pool water") - that remains a judgment call, made explicitly by a
human-reviewed adversarial pass (see AdmissionReview.independence_note
for why this is recorded as a real, named limitation rather than solved).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


def extract_ceiling_ppm(text: str) -> Optional[float]:
    match = re.search(r"up to (\d+(?:\.\d+)?)\s*ppm", text)
    return float(match.group(1)) if match else None


def extract_ph_range(text: str) -> Optional[tuple[float, float]]:
    match = re.search(
        r"pH (?:values? )?(?:within the range of |between )?(\d+(?:\.\d+)?)\s*(?:to|and|[-–])\s*(\d+(?:\.\d+)?)",
        text,
    )
    return (float(match.group(1)), float(match.group(2))) if match else None


@dataclass
class DeterministicCheckResult:
    """The one part of this admission process that is genuinely
    model-independent: mechanical numeric extraction and comparison,
    not a semantic judgment."""

    mutated_ceiling_ppm: Optional[float]
    reference_ceiling_ppm: Optional[float]
    mutated_ph_range: Optional[tuple[float, float]]
    reference_ph_range: Optional[tuple[float, float]]
    ceiling_conflict: bool
    ph_range_conflict: bool

    @property
    def numeric_conflict_confirmed(self) -> bool:
        return self.ceiling_conflict or self.ph_range_conflict


def deterministic_ceiling_check(mutated_text: str, reference_text: str) -> DeterministicCheckResult:
    mutated_ceiling = extract_ceiling_ppm(mutated_text)
    reference_ceiling = extract_ceiling_ppm(reference_text)
    mutated_ph = extract_ph_range(mutated_text)
    reference_ph = extract_ph_range(reference_text)

    ceiling_conflict = (
        mutated_ceiling is not None and reference_ceiling is not None and mutated_ceiling < reference_ceiling
    )
    ph_range_conflict = (
        mutated_ph is not None and reference_ph is not None
        and (mutated_ph[0] > reference_ph[0] or mutated_ph[1] < reference_ph[1])
    )
    return DeterministicCheckResult(
        mutated_ceiling_ppm=mutated_ceiling, reference_ceiling_ppm=reference_ceiling,
        mutated_ph_range=mutated_ph, reference_ph_range=reference_ph,
        ceiling_conflict=ceiling_conflict, ph_range_conflict=ph_range_conflict,
    )


@dataclass
class AdmissionReview:
    """
    The governed record of one candidate's admission review - the
    ONLY thing that can turn a candidate into a trusted Golden specimen.
    Never produced by the generator itself (CLAUDE-P21's own governing
    rule: "the generator must not approve its own candidate").
    """

    candidate_id: str
    reviewed_at: str
    reviewer: str  # who/what actually performed this review - see independence_note
    baseline_validity_note: str
    mutation_validity_note: str
    both_anchors_identifier: tuple[str, str]  # (target, the one it conflicts with)
    evaluator_quality_note: str
    added_false_positive_bait: Optional[str]  # description of any companion clause added to strengthen the evaluator
    deterministic_check: dict  # asdict(DeterministicCheckResult)
    adversarial_review_note: str
    independence_note: str  # MUST name the shared-model-family limitation plainly - never claim it is solved
    verdict: str  # "admitted" | "rejected" | "returned_for_revision"
    verdict_reasoning: str
