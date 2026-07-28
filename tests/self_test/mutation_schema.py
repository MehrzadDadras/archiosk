"""
CLAUDE-P13R self-test laboratory - the shared vocabulary between the
mutation logic (which plants a defect and writes the hidden answer key)
and the evaluator (which grades Archiosk's blind output against it).

This module knows nothing about Archiosk itself - no imports from
services/ - it is pure data shape, so the investigator side can never
accidentally import its way into seeing an answer key.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Progressive difficulty (Prompt: "obvious -> cross-document -> supersession
# -> semantic -> perspective-sensitive -> lifecycle") - open-world in
# spirit (a real mutation kind not listed here is still a valid string),
# but named here so the tier a given mutation targets is never a typo.
DIFFICULTY_TIER_OBVIOUS = "obvious"
DIFFICULTY_TIER_CROSS_DOCUMENT = "cross_document"
DIFFICULTY_TIER_SUPERSESSION = "supersession"
DIFFICULTY_TIER_SEMANTIC = "semantic"
DIFFICULTY_TIER_PERSPECTIVE_SENSITIVE = "perspective_sensitive"
DIFFICULTY_TIER_LIFECYCLE = "lifecycle"

DIFFICULTY_TIERS = (
    DIFFICULTY_TIER_OBVIOUS,
    DIFFICULTY_TIER_CROSS_DOCUMENT,
    DIFFICULTY_TIER_SUPERSESSION,
    DIFFICULTY_TIER_SEMANTIC,
    DIFFICULTY_TIER_PERSPECTIVE_SENSITIVE,
    DIFFICULTY_TIER_LIFECYCLE,
)


@dataclass
class PlantedMutation:
    """
    The hidden answer key for one deliberately-introduced defect. Never
    passed to the investigator (see this package's own __init__ docstring)
    - it exists only for the evaluator to grade against, after the
    investigator has already produced its real output blind.

    `location` is the requirement id the defect lives at (or the FIRST of
    a pair, for a cross-requirement defect) - matched against
    ConsistencyFlag.requirement_a_id/requirement_b_id, not a fuzzy text
    search, so evaluation is exact rather than approximate.

    `secondary_location` is the SECOND requirement id, only for a defect
    that genuinely spans two items (CLAUDE-P14's cross-document tier) -
    None for a single-item defect like the obvious tier's numerical
    contradiction, which only ever needed one. Set, it lets the
    evaluator check "found the discrepancy" (location alone) and
    "identified the correct anchors on BOTH sides" (location AND
    secondary_location) as two separate, honest questions rather than
    collapsing them into one.

    `non_defects` names things a naive reviewer (human or machine) might
    mistake for problems but are NOT planted defects - the evaluator uses
    this to tell a "confirmed false positive" apart from a flag that
    might be a genuine unexpected discovery the golden corpus didn't
    actually have coming.
    """

    mutation_id: str
    mutation_kind: str  # open-world: "numerical_contradiction", "cross_document_inconsistency", etc.
    difficulty_tier: str  # DIFFICULTY_TIERS
    description: str  # what was changed, in plain language, for a human reading the answer key
    location: str  # the requirement id the defect lives at
    expected_detection: str  # what a correct investigator run should say
    non_defects: list[str] = field(default_factory=list)
    secondary_location: str | None = None


@dataclass
class SelfTestResult:
    """
    The evaluator's output - four honest categories, not a single pass/
    fail score (Prompt: do not turn this into simplistic model scoring).

    `unplanted_and_unexplained` is deliberately NOT auto-resolved into
    "false positive" vs "unexpected valid discovery" - the evaluator
    only knows the golden corpus's own DECLARED non_defects; anything
    outside that list needs a human to actually judge whether Archiosk
    found something real the corpus author didn't anticipate (which
    would mean the golden corpus wasn't as golden as assumed) or
    hallucinated a contradiction that isn't there. Pretending an
    algorithm can tell these apart would be dishonest.
    """

    caught: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)
    confirmed_false_positives: list[str] = field(default_factory=list)
    unplanted_and_unexplained: list[str] = field(default_factory=list)
    # CLAUDE-P14: only ever populated for a mutation with secondary_location
    # set - "found it" (caught) and "correctly named BOTH anchors" are
    # different questions; a flag can catch a cross-document mutation
    # while still mis-citing one side.
    both_anchors_correct: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"caught={len(self.caught)} missed={len(self.missed)} "
            f"both_anchors_correct={len(self.both_anchors_correct)} "
            f"confirmed_false_positives={len(self.confirmed_false_positives)} "
            f"unplanted_and_unexplained={len(self.unplanted_and_unexplained)}"
        )
