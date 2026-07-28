"""
CLAUDE-P19 - the thinnest possible manifest: which lab module implements
which Golden Laboratory Suite v1 tier. This is the ONLY place a new tier
needs to be registered to become runnable via tools/self_test_runner.py -
everything else (corpus, mutation, grading) stays exactly where each
tier already put it.

Deliberately does NOT try to make the six tiers structurally uniform.
Tier 1 has no CaseWorkspaceStore at all (a bare RequirementItem list);
tiers 2 and 6 (Cases A/B) grade via BHiveParser._check_consistency +
tests.self_test.evaluator.evaluate(); tiers 3, 4, 5, and 6 (Cases C-F)
grade single-anchor requirement_investigation.investigate_requirement
calls, some structurally (id-matching) and some only qualitatively (a
human reads the assessment text). Forcing all of this into one shared
corpus-building or grading interface would be the "overgeneralized
framework" CLAUDE-P19 explicitly warns against - the only thing every
tier actually shares is "produces a list of SpecimenResult when asked,"
which is exactly what each lab module's own run_tier() function does.
"""
from __future__ import annotations

from dataclasses import dataclass

from tests.self_test.mutation_schema import (
    DIFFICULTY_TIER_CROSS_DOCUMENT,
    DIFFICULTY_TIER_LIFECYCLE,
    DIFFICULTY_TIER_OBVIOUS,
    DIFFICULTY_TIER_PERSPECTIVE_SENSITIVE,
    DIFFICULTY_TIER_SEMANTIC,
    DIFFICULTY_TIER_SUPERSESSION,
)


@dataclass
class TierDescriptor:
    tier_id: str
    name: str
    lab_module: str  # dotted path; must expose a run_tier() -> list[SpecimenResult]


TIERS: tuple[TierDescriptor, ...] = (
    TierDescriptor(DIFFICULTY_TIER_OBVIOUS, "Obvious discrepancy", "tools.self_test_lab"),
    TierDescriptor(DIFFICULTY_TIER_CROSS_DOCUMENT, "Cross-document inconsistency", "tools.self_test_lab_002_cross_document"),
    TierDescriptor(DIFFICULTY_TIER_SUPERSESSION, "Supersession / Addendum authority", "tools.self_test_lab_003_supersession"),
    TierDescriptor(DIFFICULTY_TIER_SEMANTIC, "Semantic incompatibility", "tools.self_test_lab_004_semantic"),
    TierDescriptor(DIFFICULTY_TIER_PERSPECTIVE_SENSITIVE, "Represented-party risk/opportunity", "tools.self_test_lab_005_perspective"),
    TierDescriptor(DIFFICULTY_TIER_LIFECYCLE, "Lifecycle migration", "tools.self_test_lab_006_lifecycle"),
)


def tier_by_id(tier_id: str) -> TierDescriptor:
    for tier in TIERS:
        if tier.tier_id == tier_id:
            return tier
    raise KeyError(f"'{tier_id}' is not a registered Golden Laboratory Suite v1 tier.")
