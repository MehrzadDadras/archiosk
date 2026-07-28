"""
CLAUDE-P13R self-test laboratory - the Golden Corpus.

Deliberately a small, hand-written synthetic requirement set, not a
reuse of the real NREOCRC corpus (tests/fixtures/nreocrc/) - that corpus
exists for faithfulness auditing against real, complex document text;
this one exists to be a fast, cheap, unambiguously-coherent baseline a
mutation can be planted into with a precisely-known, single change. It
is "golden" in the sense this package's own name uses it: believed
internally consistent until Archiosk's own blind run proves otherwise
(see mutations.py's docstring on why the CLEAN run matters as much as
the mutated one).

Returns fresh RequirementItem instances every call (never a shared
mutable list) so a mutation function can never accidentally corrupt the
baseline other tests rely on.
"""
from __future__ import annotations

from services.bhive_parser import RequirementItem


def golden_requirements() -> list[RequirementItem]:
    return [
        RequirementItem(
            id="R1", category="technical_specification", confidence=0.9, source_line=1,
            text=(
                "The Facility shall support 72 hours of autonomous backup power "
                "operation for critical loads without normal utility power."
            ),
        ),
        RequirementItem(
            id="R2", category="technical_specification", confidence=0.9, source_line=2,
            text=(
                "Backup generator fuel storage shall be sized to provide 72 hours of "
                "continuous operation at full critical load, per the autonomy "
                "requirement in R1."
            ),
        ),
        RequirementItem(
            id="R3", category="submission_instruction", confidence=0.85, source_line=3,
            text="Proposals shall be submitted no later than 45 days after the Request for Proposals issue date.",
        ),
        RequirementItem(
            id="R4", category="evaluation_criteria", confidence=0.85, source_line=4,
            text="Evaluation of proposals shall weigh technical merit at 60% and price at 40%.",
        ),
        RequirementItem(
            id="R5", category="scope_of_work", confidence=0.85, source_line=5,
            text="The Design-Builder shall provide as-built drawings within 30 days of Substantial Completion.",
        ),
    ]
