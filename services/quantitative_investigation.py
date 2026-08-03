"""
CLAUDE-P40-VW8-QA-R6 - Natural-Language, Evidence-Guided Quantitative
Investigation.

Reported defect: inside an active Investigation, a plain contextual
statement ("Those numbers are geodetic elevations from ground floor to
the basement.") got the same "I didn't recognize an action in that
message" reply as a genuinely unrelated stray message - the reviewer
was providing evidence/context, not issuing an unrecognized command.
services/conversation_interpreter.py's own final fallback now checks
for an open Case FIRST (see interpret_message's own comment) and
routes ordinary discussion to a real acknowledgment instead.

This module is the second half: a GENERAL (not "Nipigon Ramp"-specific)
evidence-guided quantitative pattern for a question shaped like
"is there enough available length/clearance for X, given these
elevations/dimensions" - vertical drop, slope-derived run, and a
feasibility comparison against an available/measured length. Built to
be reused for any distance/elevation-difference/slope/clearance
question of this same shape, not hardcoded to driveways.

Honesty boundary, matching this whole codebase's established pattern
(see services/drawing_intake.py's own header for the identical
reasoning applied to the R2A stage): this module extracts NUMBERS FROM
CONVERSATION TEXT the reviewer has directly typed - never from a
drawing. Real drawing measurement (OCR/vision-based dimension
extraction) is NOT available in this environment (no PDF-rendering
library, no local OCR - see services/drawing_intake.py's own capability
audit, identical conclusion) and is not attempted here. A value this
module proposes is always attributed to the reviewer's own words
(never a drawing citation, since none was actually read) and always
carries an explicit confidence/status - never silently promoted to
"confirmed" without the reviewer's own input.

No external-AI call of any kind - every calculation here is
deterministic arithmetic on numbers the reviewer has already stated in
this conversation, not a model inference.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# -- trigger recognition -----------------------------------------------------
# Deliberately keyword-based, like every other trigger in
# conversation_interpreter.py (see that module's own honesty note) -
# broad enough to cover the reusable pattern this stage asks for
# (distance/elevation/slope/clearance), not narrowed to "ramp"/
# "driveway" specifically, even though the acceptance scenario is one.
_FEASIBILITY_KEYWORDS = (
    "enough length", "enough room", "enough space", "enough clearance",
    "does it fit", "will it fit", "is there enough", "feasib",
    "slope", "grade", "ramp", "driveway", "clearance", "headroom",
    "vertical drop", "elevation difference", "available length",
    "available run", "available distance", "available travel",
)


def looks_like_quantitative_feasibility_question(lowered: str) -> bool:
    return any(kw in lowered for kw in _FEASIBILITY_KEYWORDS)


# -- evidence-backed value extraction ----------------------------------------

@dataclass
class ExtractedValue:
    field: str
    value: float
    unit: Optional[str]
    raw_text: str
    # CLAUDE-P40-VW8-QA-R6 Section "Evidence-backed extraction": every
    # proposed value retains WHERE it came from. "conversation_stated"
    # is the only extraction method this module ever produces - never
    # "drawing_measurement" (not available; see module header) and
    # never fabricated.
    extraction_method: str = "conversation_stated"
    status: str = "user_provided"


_FIELD_PATTERNS: dict[str, list[re.Pattern]] = {
    "entrance_grade_elevation": [
        re.compile(r"(?:entrance|exterior|street|exterior\s*ground)\s*(?:grade|elevation)\D{0,20}?(-?\d+(?:\.\d+)?)", re.IGNORECASE),
        re.compile(r"ground\s*floor\D{0,20}?(-?\d+(?:\.\d+)?)", re.IGNORECASE),
    ],
    "basement_grade_elevation": [
        re.compile(r"basement\s*(?:driveway|garage)?\s*(?:grade|elevation|threshold|slab)\D{0,20}?(-?\d+(?:\.\d+)?)", re.IGNORECASE),
    ],
    "available_travel_length": [
        re.compile(r"available\s*(?:horizontal|travel)?\s*(?:length|run|distance)\D{0,15}?(\d+(?:\.\d+)?)", re.IGNORECASE),
    ],
    "driveway_width": [
        re.compile(r"(\d+(?:\.\d+)?)\s*(?:m|meter|metre)?\s*wide", re.IGNORECASE),
        re.compile(r"width\D{0,15}?(\d+(?:\.\d+)?)", re.IGNORECASE),
    ],
    "longitudinal_slope_percent": [
        re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:slope|grade)?", re.IGNORECASE),
        re.compile(r"slope\D{0,10}?(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),
    ],
}

_UNIT_RE = re.compile(r"\b(m|meter|metre|meters|metres|ft|feet|mm|%)\b", re.IGNORECASE)

FIELD_LABELS: dict[str, str] = {
    "entrance_grade_elevation": "exterior driveway-entry grade elevation",
    "basement_grade_elevation": "basement driveway/garage threshold elevation",
    "available_travel_length": "available horizontal travel length",
    "driveway_width": "proposed driveway width",
    "longitudinal_slope_percent": "applicable maximum longitudinal slope",
}

REQUIRED_FOR_CALCULATION = (
    "entrance_grade_elevation", "basement_grade_elevation", "longitudinal_slope_percent",
)


def extract_values_from_text(text: str) -> list[ExtractedValue]:
    """Never invents a value - only ever returns a number the reviewer
    literally typed, each retaining the exact matched snippet as its
    own evidence. First match per field wins (same "don't over-claim
    precision" discipline services/drawing_intake.py's own extractor
    uses)."""
    values: list[ExtractedValue] = []
    found_fields: set[str] = set()
    for field_name, patterns in _FIELD_PATTERNS.items():
        if field_name in found_fields:
            continue
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            try:
                number = float(match.group(1))
            except (ValueError, IndexError):
                continue
            snippet = text[max(0, match.start() - 15):match.end() + 15].strip()
            if field_name == "longitudinal_slope_percent":
                # Both patterns for this field require a literal '%' to
                # match at all - unambiguous, never scanned for.
                unit = "%"
            else:
                # A unit already inside the match itself (e.g. "6 m
                # wide" - the pattern's own optional unit group) wins;
                # otherwise scanned immediately AFTER the matched number
                # only (never before, which risks picking up an
                # unrelated unit from the end of the PRECEDING
                # sentence/clause).
                unit_match = _UNIT_RE.search(match.group(0))
                if not unit_match:
                    unit_window = text[match.end():match.end() + 12]
                    unit_match = _UNIT_RE.search(unit_window)
                unit = unit_match.group(1) if unit_match else None
            values.append(ExtractedValue(
                field=field_name, value=number, unit=unit,
                raw_text=snippet,
            ))
            found_fields.add(field_name)
            break
    return values


def merge_values(*value_lists: list[ExtractedValue]) -> dict[str, ExtractedValue]:
    """Later lists win on a field collision (a re-stated/corrected value
    supersedes an earlier one in conversation order) - the same
    left-to-right "most recent wins" reasoning ordinary conversation
    already implies."""
    merged: dict[str, ExtractedValue] = {}
    for values in value_lists:
        for v in values:
            merged[v.field] = v
    return merged


# -- transparent calculation --------------------------------------------------

@dataclass
class FeasibilityCalculation:
    vertical_drop: float
    basic_sloped_run: float
    additional_length: float
    total_required_travel: float
    available_travel_length: Optional[float]
    margin: Optional[float]
    feasible: Optional[bool]


def compute_feasibility(
    entrance_grade: float, basement_grade: float, slope_percent: float,
    available_travel_length: Optional[float] = None,
    additional_length: float = 0.0,
) -> FeasibilityCalculation:
    """The exact 5-step formula this stage's own addendum specifies -
    plain arithmetic, no external call, no hidden default slope (the
    caller must have a real, attributed slope value already; this
    function never substitutes one)."""
    vertical_drop = entrance_grade - basement_grade
    basic_sloped_run = vertical_drop / (slope_percent / 100.0)
    total_required_travel = basic_sloped_run + additional_length
    margin = None
    feasible = None
    if available_travel_length is not None:
        margin = available_travel_length - total_required_travel
        feasible = margin >= 0
    return FeasibilityCalculation(
        vertical_drop=vertical_drop, basic_sloped_run=basic_sloped_run,
        additional_length=additional_length, total_required_travel=total_required_travel,
        available_travel_length=available_travel_length, margin=margin, feasible=feasible,
    )


# -- reply/Finding construction -----------------------------------------------

def missing_fields(confirmed: dict[str, ExtractedValue]) -> list[str]:
    return [f for f in REQUIRED_FOR_CALCULATION if f not in confirmed]


def build_source_guidance(has_drawing_source: bool) -> str:
    if has_drawing_source:
        return ""
    return (
        " No drawing Source is attached to this Investigation yet - a site plan (exterior "
        "entry grade and available run), a basement/parking plan (threshold elevation), and "
        "a building section (vertical clearances) would let this be measured rather than "
        "estimated from what you type here. Use \"+ Add drawing Source to this Investigation\" "
        "on this Investigation's own page to attach one."
    )


def build_progress_reply(
    question_text: str, confirmed: dict[str, ExtractedValue], has_drawing_source: bool,
) -> str:
    """Section: 'I understand that you are evaluating...' style reply -
    restates the question in full (never truncated), states what's
    already confirmed, and asks specifically for what's still missing."""
    missing = missing_fields(confirmed)
    parts = [
        f"I understand you're evaluating: \"{question_text.strip()}\"",
    ]
    if confirmed:
        stated = "; ".join(
            f"{FIELD_LABELS[f]} = {v.value}{(' ' + v.unit) if v.unit else ''} (from: \"{v.raw_text}\")"
            for f, v in confirmed.items()
        )
        parts.append(f"Confirmed so far: {stated}.")
    if missing:
        needed = ", ".join(FIELD_LABELS[f] for f in missing)
        parts.append(f"Still needed to calculate this: {needed}.")
    if "longitudinal_slope_percent" in missing:
        parts.append(
            "The applicable maximum slope must come from an already-adopted governed source in this "
            "Project, or you can state it as your own explicit design assumption (e.g. \"assume 15% slope\") "
            "- it is never assumed automatically."
        )
    parts.append(build_source_guidance(has_drawing_source).strip())
    return " ".join(p for p in parts if p)


def build_calculation_reply(calc: FeasibilityCalculation, confirmed: dict[str, ExtractedValue]) -> str:
    lines = [
        f"Vertical drop = entrance grade elevation ({confirmed['entrance_grade_elevation'].value}) "
        f"- basement entrance elevation ({confirmed['basement_grade_elevation'].value}) "
        f"= {calc.vertical_drop:.2f}",
        f"Basic sloped run = vertical drop ({calc.vertical_drop:.2f}) / longitudinal slope "
        f"({confirmed['longitudinal_slope_percent'].value}%) = {calc.basic_sloped_run:.2f}",
    ]
    if calc.additional_length:
        lines.append(
            f"Additional length (top/bottom transitions + landing/curved geometry, as stated) "
            f"= {calc.additional_length:.2f}"
        )
    else:
        lines.append(
            "Additional length (top/bottom transitions, required landing/curved geometry): "
            "not yet stated - treated as unresolved, not assumed zero for a final Finding."
        )
    lines.append(f"Total required travel = {calc.total_required_travel:.2f}")
    if calc.available_travel_length is not None:
        lines.append(
            f"Available measured travel ({calc.available_travel_length:.2f}) vs. total required "
            f"({calc.total_required_travel:.2f}): margin = {calc.margin:+.2f} "
            f"({'appears feasible' if calc.feasible else 'appears NOT feasible'} on this geometry alone)."
        )
    else:
        lines.append(
            "Available measured/travel length not yet stated - feasibility comparison cannot be "
            "completed until it is."
        )
    lines.append(
        "This is geometric feasibility only, from the values stated in this conversation - not a "
        "regulatory compliance determination and not a substitute for professional design confirmation."
    )
    return " ".join(lines)


def build_finding_statement(
    question_text: str, confirmed: dict[str, ExtractedValue], calc: FeasibilityCalculation,
    width: Optional[ExtractedValue], unresolved: list[str],
) -> str:
    """Section 'Finding behavior': every required field, packed into
    Finding.statement (a plain string - Finding has no separate
    structured-field schema, and this stage doesn't invent one; see
    this module's own header on reusing the existing mechanism)."""
    confirmed_lines = "; ".join(
        f"{FIELD_LABELS[f]} = {v.value}{(' ' + v.unit) if v.unit else ''} "
        f"(source: conversation, quote: \"{v.raw_text}\", status: {v.status})"
        for f, v in confirmed.items()
    )
    parts = [
        f"Question evaluated: {question_text.strip()}",
        f"Confirmed inputs: {confirmed_lines}.",
        (
            f"Width/turning considerations: {width.value}{(' ' + width.unit) if width.unit else ''} "
            f"(stated, not yet evaluated for plan fit/turning geometry)."
            if width else "Width/turning considerations: not stated."
        ),
        "Formula: vertical drop = entrance grade - basement grade; basic sloped run = vertical drop / slope; "
        "total required travel = basic sloped run + additional length.",
        f"Vertical drop = {calc.vertical_drop:.2f}; basic sloped run = {calc.basic_sloped_run:.2f}; "
        f"total required travel = {calc.total_required_travel:.2f}.",
    ]
    if calc.available_travel_length is not None:
        parts.append(
            f"Available length = {calc.available_travel_length:.2f}; margin = {calc.margin:+.2f}; "
            f"geometric feasibility (this dimension alone): {'appears feasible' if calc.feasible else 'appears NOT feasible'}."
        )
    if unresolved:
        parts.append(f"Unresolved: {'; '.join(unresolved)}.")
    parts.append(
        "This is an evidence-backed geometric feasibility assessment from reviewer-stated values, not a "
        "final regulatory compliance or professional engineering determination - requires professional "
        "confirmation before reliance."
    )
    return " ".join(parts)


def suggested_title(question_text: str) -> str:
    """A short, real title distinct from the question itself - the
    question's own full text is preserved separately (in the reply and
    the Finding), never replaced by this shorter label. Deliberately
    generic-pattern-derived, not hardcoded to one scenario: falls back
    to a truncated-but-clearly-marked form for anything this pattern
    library doesn't specifically recognize."""
    lowered = question_text.lower()
    if "ramp" in lowered and "basement" in lowered:
        return "Basement driveway ramp feasibility"
    if "ramp" in lowered:
        return "Ramp feasibility"
    if "slope" in lowered or "grade" in lowered:
        return "Slope/grade feasibility"
    stripped = question_text.strip().rstrip("?")
    return stripped if len(stripped) <= 60 else stripped[:57] + "..."
