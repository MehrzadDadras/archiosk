"""
CLAUDE-P19 - Golden Laboratory Suite v1: the shared run-record schema.

Deliberately data-only (no imports from services/ or tools/) - the same
discipline mutation_schema.py already keeps, so the investigator side can
never accidentally import its way into seeing a run's own expectations.

`SpecimenResult` is intentionally wide and mostly Optional rather than a
single pass/fail bit: six tiers grade very differently underneath (a
bhive_parser ConsistencyFlag pair, a single investigate_requirement call,
a qualitative human-read narrative), and forcing all of them through one
boolean would be exactly the "opaque aggregate score" the tier design
explicitly rejects. A field being None/empty means "not applicable to
this specimen," never "failed" - `passed()` only ever reasons about the
dimensions a given specimen actually populated.

Known, deliberate v1 limitation: `cost_estimate_usd` is always None.
Neither production call path this suite exercises (BHiveParser.
_check_consistency, requirement_investigation.investigate_requirement)
currently returns token usage - instrumenting that is a real, bounded,
valuable follow-up, deliberately left out of this pass rather than
threading a return-shape change through _check_consistency's several
existing callers as a side effect of building this regression harness.
`latency_seconds` and `model_call_count` ARE captured (wrapping a timer
around each real call needs no production change at all), so cost is the
one dimension in the requested list that is honestly reported absent
rather than estimated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

SUITE_VERSION = "golden_laboratory_suite_v1"


@dataclass
class SpecimenResult:
    tier_id: str  # tests.self_test.mutation_schema.DIFFICULTY_TIERS value
    specimen_id: str  # e.g. "006F" - unique within a run, stable across runs
    description: str  # human-readable: what this specimen is testing

    production_reasoning_path: str  # e.g. "BHiveParser._check_consistency"
    corpus_version: str
    mutation_version: Optional[str] = None

    planted_condition: Optional[str] = None
    expected_detection_type: Optional[str] = None
    expected_anchors: list[str] = field(default_factory=list)
    expected_relationships: list[str] = field(default_factory=list)
    expected_non_findings: list[str] = field(default_factory=list)

    model: Optional[str] = None
    prompt_version: Optional[str] = None

    ran: bool = True
    skipped_reason: Optional[str] = None
    malformed_or_truncated_output: bool = False

    # None = not applicable to this specimen; True/False = an actual
    # automatic verdict was reached on this dimension. `caught` is
    # deliberately the most general of the five - "a planted defect was
    # found" for the discrepancy-detection tiers, but also the honest,
    # closest-fit reuse for tiers whose real grading concept is something
    # else structurally verifiable (CLAUDE-P17's polarity-differentiation
    # checks, CLAUDE-P18's convergence/disagreement checks) rather than
    # inventing a new named dimension per tier's own local vocabulary.
    caught: Optional[bool] = None
    anchor_correctness: Optional[bool] = None
    authority_supersession_correctness: Optional[bool] = None
    current_vs_historical_correctness: Optional[bool] = None
    uncertainty_handling: Optional[bool] = None

    unexpected_valid_discoveries: list[str] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)

    # Some specimens (CLAUDE-P17's Case C, CLAUDE-P16's Case B/D, every
    # risk-migration stage in CLAUDE-P18's Case D, etc.) have never been
    # gradable by a bool - "did this correctly distinguish X from Y" is a
    # real reasoning question a human reads, not a string match. Recorded
    # honestly as ungraded rather than forced into a fake automatic verdict.
    requires_qualitative_read: bool = False
    qualitative_note: Optional[str] = None

    model_call_count: int = 0
    cost_estimate_usd: Optional[float] = None  # see module docstring
    latency_seconds: Optional[float] = None

    def passed(self) -> Optional[bool]:
        """None when nothing here supports an automatic verdict (SKIPPED
        or purely qualitative) - never silently coerced to True or False."""
        if not self.ran:
            return False
        if self.requires_qualitative_read:
            return None
        checks = [
            self.caught, self.anchor_correctness, self.authority_supersession_correctness,
            self.current_vs_historical_correctness, self.uncertainty_handling,
        ]
        relevant = [c for c in checks if c is not None]
        has_signal = bool(relevant) or self.false_positives or self.malformed_or_truncated_output
        if not has_signal:
            return None
        return all(relevant) and not self.false_positives and not self.malformed_or_truncated_output


@dataclass
class SuiteRun:
    """
    One execution of some subset of Golden Laboratory Suite v1's tiers.
    `specimens` holds asdict(SpecimenResult) each - plain dicts, so this
    round-trips through JSON with no custom encoder, matching the flat-
    JSON discipline the rest of this app already uses for persistence.
    """

    run_id: str
    suite_version: str
    started_at: str
    completed_at: str
    tiers_executed: list[str]
    app_model_default: Optional[str]  # ANTHROPIC_MODEL at run time, for reference alongside per-specimen model
    specimens: list[dict] = field(default_factory=list)
    notes: Optional[str] = None

    def specimens_for_tier(self, tier_id: str) -> list[dict]:
        return [s for s in self.specimens if s["tier_id"] == tier_id]

    def dimension_summary(self) -> dict:
        """
        Per-dimension counts across every specimen in this run - NOT a
        single aggregate score. Each dimension is reported on its own so
        an improvement in one cannot silently mask a regression in
        another (the tier's own explicit requirement).
        """
        dims = (
            "caught", "anchor_correctness", "authority_supersession_correctness",
            "current_vs_historical_correctness", "uncertainty_handling",
        )
        summary: dict = {}
        for dim in dims:
            applicable = [s[dim] for s in self.specimens if s[dim] is not None]
            summary[dim] = {
                "applicable": len(applicable),
                "true": sum(1 for v in applicable if v),
                "false": sum(1 for v in applicable if not v),
            }
        summary["false_positives_total"] = sum(len(s["false_positives"]) for s in self.specimens)
        summary["unexpected_valid_discoveries_total"] = sum(
            len(s["unexpected_valid_discoveries"]) for s in self.specimens
        )
        summary["malformed_or_truncated_total"] = sum(1 for s in self.specimens if s["malformed_or_truncated_output"])
        summary["did_not_run_total"] = sum(1 for s in self.specimens if not s["ran"])
        summary["qualitative_only_total"] = sum(1 for s in self.specimens if s["requires_qualitative_read"])
        summary["model_call_count_total"] = sum(s["model_call_count"] for s in self.specimens)
        latencies = [s["latency_seconds"] for s in self.specimens if s["latency_seconds"] is not None]
        summary["latency_seconds_total"] = sum(latencies) if latencies else None
        return summary

    def to_dict(self) -> dict:
        return asdict(self)
