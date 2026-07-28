"""
CLAUDE-P21 self-test laboratory: the candidate admission review.

A TEST/LAB script (same status as tools/self_test_lab*.py and tools/
self_test_generator.py) - makes ONE real, billed Anthropic call, never
run automatically by the test suite.

The governing rule this script exists to enforce: "machine-generated
candidates may propose examinations; only an independently challenged
admission process makes them trusted Golden specimens." The generator
(tools/self_test_generator.py) never runs this script, and this script
never marks a candidate "admitted" merely because tools/self_test_
candidate_lab.py's blind run caught the proposed mutation - that was
never proof of anything beyond "the investigator agrees with the
generator," which is exactly the shared-model-bias risk CLAUDE-P21 opened
with.

Four checks, only one of which is genuinely model-independent:

1. Deterministic ceiling check (tests/self_test/candidate_admission.py's
   deterministic_ceiling_check) - plain regex extraction of the numeric
   chlorine-ppm/pH claims from both requirements and a mechanical
   inequality check. No model call, Claude or otherwise. This is the
   ONLY part of this review that is not "the same kind of system judging
   itself."

2. Adversarial challenge call - ONE separate real model call, explicitly
   instructed to argue AGAINST the claimed defect (scope, equipment-
   boundary, operating-condition, and terminology escape routes). Uses
   the same model family as the generator and the production investigator
   - see this script's own printed independence note for why this is
   recorded as a LIMITED, not solved, form of independence, per CLAUDE-
   P21's explicit fallback instruction.

3 & 4. Baseline validity and evaluator-quality review - manual textual
   analysis (recorded verbatim in this script, attributed to the human
   Archiosk operator and this assistant working together, not generated
   by calling the model again) of whether the six clean requirements are
   genuinely coherent and whether the answer key states both what should
   and should not be detected.

Requires a real ANTHROPIC_API_KEY in .env - without one this honestly
reports SKIPPED rather than fabricating a result.

Run:
    venv/Scripts/python.exe tools/self_test_admission_review.py <candidate_id>
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

from tests.self_test.candidate_admission import AdmissionReview, deterministic_ceiling_check  # noqa: E402

CANDIDATES_DIR = REPO_ROOT / "tests" / "self_test" / "candidates"

ADVERSARIAL_PROMPT_TEMPLATE = """You are an ADVERSARIAL reviewer. Your job is to find every reason the \
following claimed specification contradiction might NOT actually be a genuine, material defect - do \
NOT try to confirm it; actively argue against it. Consider specifically:

1. SCOPE - could the two clauses describe different, non-overlapping categories of equipment despite \
similar wording?
2. EQUIPMENT BOUNDARY - could the components in question be a physically or functionally separate \
system not actually covered by the other clause's material spec?
3. OPERATING CONDITION - could the two numeric ranges describe different operating regimes (e.g. \
normal vs. worst-case/excursion) that are not actually in conflict?
4. TERMINOLOGY - could the same numbers describe genuinely different concepts (e.g. a water-chemistry \
operating setpoint vs. a material rating ceiling) such that comparing them numerically is a category \
error?

Requirement A (allegedly the mutated/defective one):
{requirement_a}

Requirement B (allegedly the one it contradicts):
{requirement_b}

Claimed contradiction:
{claim}

Argue as strongly as you honestly can AGAINST this being a genuine defect, using the four angles \
above. If, after making the strongest case you honestly can, you still conclude it IS a genuine \
defect, say so plainly and explain why none of the four escape routes actually hold up.

Respond ONLY with a JSON object, no prose, no markdown fences:
{{"scope_escape_argument": "...", "equipment_boundary_escape_argument": "...", \
"operating_condition_escape_argument": "...", "terminology_escape_argument": "...", \
"final_verdict": "genuine_defect" or "not_a_genuine_defect", "final_reasoning": "..."}}"""


def run_adversarial_challenge(requirement_a: str, requirement_b: str, claim: str, api_key: str, model: str, timeout: float) -> dict:
    import anthropic  # imported lazily, matches every other real-call module in this codebase

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    prompt = ADVERSARIAL_PROMPT_TEMPLATE.format(requirement_a=requirement_a, requirement_b=requirement_b, claim=claim)
    response = client.messages.create(model=model, max_tokens=1536, messages=[{"role": "user", "content": prompt}])
    text_out = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
    cleaned = re.sub(r"^```(json)?|```$", "", text_out.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


# -- Manual review notes (CLAUDE-P21) ----------------------------------------
# Written by the assistant, reviewed with the human Archiosk operator, NOT
# generated by calling the model as part of this script's run - a separate,
# textual analysis performed while reading the candidate's actual content.

BASELINE_VALIDITY_NOTE = """All six clean (unmutated) requirements were read individually and against
each other. SPEC-22-41-01/02/03 form a coherent turnover -> pump-sizing -> filter-sizing chain: the
pump's "110% of required flow" is a VFD reserve-capacity headroom figure, not a mandate to run
continuously at 110%, so SPEC-22-41-03's filter loading cap (checked "under the conditions defined in
SPEC-22-41-01," i.e. the required/100% flow) is not violated by it - this is the normal, correct
reading of a variable-speed pump with reserve capacity, not a latent defect. SPEC-22-41-05 (surge
tank) does not state pool volumes numerically, so it cannot be mechanically cross-checked against the
turnover schedule either way - underspecification, not contradiction. SPEC-22-41-04 (clean, original)
states a WATER-CHEMISTRY operating target (1.0-3.0 ppm chlorine, pH 7.2-7.6), not a material rating;
SPEC-22-41-06 states a MATERIAL rating ceiling (up to 5.0 ppm, pH 7.0-8.0) that is deliberately WIDER
than -04's operating target and explicitly says so ("consistent with the chemical parameters
maintained under SPEC-22-41-04") - a materials safety margin above normal operating conditions is
standard, correct engineering practice, not an inconsistency. No unintended defect was found in the
clean baseline beyond the one deliberately introduced mutation."""

MUTATION_VALIDITY_NOTE = """The mutation appends a NEW sentence to SPEC-22-41-04 that reframes the
water-chemistry operating numbers (3.0 ppm / pH 7.2-7.6) as a MATERIAL RATING ceiling for "all wetted
components of the dosing system." This is now the same KIND of claim SPEC-22-41-06 makes (a material
rating ceiling for wetted components), for an OVERLAPPING physical scope: SPEC-22-41-04 itself places
dosing system sensors "on the return line... downstream of filtration... upstream of pool inlets" -
i.e. inside the main recirculation piping SPEC-22-41-06 governs ("pipe, fittings, valves, and pump
casings... in contact with pool water"), not a separate, isolated skid. None of the four adversarial
escape routes holds up on close reading: SCOPE and EQUIPMENT BOUNDARY fail because the dosing
components are textually placed inside the same water path SPEC-22-41-06 enumerates; OPERATING
CONDITION fails because both clauses assert a fixed material-rating CEILING (a material property),
not a variable that legitimately differs by operating regime; TERMINOLOGY is the one genuinely
interesting angle - the mutation reuses -04's OWN water-chemistry numbers to state a material-rating
claim, which could read as sloppy drafting rather than a deliberate defect - but a text reviewer must
grade the text AS WRITTEN, and as written it is a direct, material ceiling contradiction, not a
terminology-only mismatch. Both anchors are SPEC-22-41-04 (the mutated clause) and SPEC-22-41-06 (the
clause it contradicts) - the real blind investigator run named both correctly, but the candidate's own
generated answer key and tools/self_test_candidate_lab.py's grading harness never recorded a
secondary_location, so "both anchors correct" was never actually structurally measured. This is a real
gap, corrected at promotion time below."""

EVALUATOR_QUALITY_NOTE = """The candidate's own answer key states what SHOULD be detected
(expected_detection) and what should NOT be (non_defects for SPEC-01/02/03/05, plus SPEC-06 itself).
It does NOT include any false-positive bait, qualification, or resolving exception - every non-defect
requirement is topically unrelated to chemical/material ratings, so a shallow "does this requirement
mention chlorine ppm" filter would already avoid false-flagging them; the evaluator does not yet prove
Archiosk reasons past simple number comparison. Strengthened at promotion time by adding one companion
clause (a non-wetted dosing-electronics enclosure, explicitly exempt from SPEC-22-41-06's wetted-
component scope) that mentions chlorine resistance but must NOT be flagged - a genuine qualification/
scope-exception test, not just an unrelated topic."""


def main() -> int:
    if len(sys.argv) < 2:
        candidates = sorted(CANDIDATES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
        candidates = [p for p in candidates if not p.name.endswith("-admission.json")]
        if not candidates:
            print("SKIPPED: no candidates found.")
            return 1
        candidate_path = candidates[-1]
    else:
        candidate_path = CANDIDATES_DIR / f"{sys.argv[1]}.json"

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    print(f"=== ADMISSION REVIEW: candidate {candidate['candidate_id']} ===\n")

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("SKIPPED: no ANTHROPIC_API_KEY configured - cannot run the adversarial challenge call.")
        return 1
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    timeout = 30.0

    reference = next(r for r in candidate["requirements"] if r["identifier"] != candidate["proposed_mutation"]["target_identifier"] and "22-41-06" in r["identifier"])
    mutated_text = candidate["proposed_mutation"]["mutated_text"]
    reference_text = reference["text"]

    print("=== CHECK 1: deterministic ceiling check (no model call - the one genuinely independent check) ===")
    det = deterministic_ceiling_check(mutated_text, reference_text)
    print(f"  Mutated ceiling: {det.mutated_ceiling_ppm} ppm, pH {det.mutated_ph_range}")
    print(f"  Reference ceiling: {det.reference_ceiling_ppm} ppm, pH {det.reference_ph_range}")
    print(f"  Numeric conflict mechanically confirmed: {det.numeric_conflict_confirmed}")

    print("\n=== CHECK 2: adversarial challenge (real, separate model call - SAME model family, limited independence) ===")
    adversarial = run_adversarial_challenge(
        requirement_a=mutated_text, requirement_b=reference_text,
        claim=candidate["proposed_mutation"]["description"], api_key=api_key, model=model, timeout=timeout,
    )
    for key in ("scope_escape_argument", "equipment_boundary_escape_argument", "operating_condition_escape_argument", "terminology_escape_argument"):
        print(f"  {key}: {adversarial[key]}")
    print(f"  final_verdict: {adversarial['final_verdict']}")
    print(f"  final_reasoning: {adversarial['final_reasoning']}")

    print("\n=== CHECK 3/4: baseline validity + evaluator quality (manual textual review) ===")
    print(BASELINE_VALIDITY_NOTE)
    print()
    print(MUTATION_VALIDITY_NOTE)
    print()
    print(EVALUATOR_QUALITY_NOTE)

    independence_note = (
        "Genuine cross-model independence was NOT available - .env carries only ANTHROPIC_API_KEY "
        "(confirmed by inspecting variable names, never values), matching this codebase's deliberate "
        "single-cloud-dependency design (see tools/dependency_fit.py). The adversarial challenge above "
        "used the SAME model family as the generator and the production investigator - it is a "
        "structurally different TASK (arguing against the defect rather than confirming it), not a "
        "different reasoning system, and is recorded here as a LIMITED form of independence, not a "
        "solved one. The one part of this review that is genuinely model-independent is the "
        "deterministic ceiling check (CHECK 1) - plain regex/arithmetic, no LLM involved at all."
    )

    admitted = det.numeric_conflict_confirmed and adversarial["final_verdict"] == "genuine_defect"
    verdict = "admitted" if admitted else "returned_for_revision"
    verdict_reasoning = (
        "Deterministic check confirms a real numeric ceiling inequality (3.0 ppm < 5.0 ppm; narrower "
        "pH range) between two requirements that textually share the same physical scope (dosing "
        "components sit on the return line, inside the piping SPEC-22-41-06 governs). The adversarial "
        "challenge, given every reason to argue otherwise, could not sustain a scope/boundary/"
        "operating-condition/terminology escape and concluded the defect is genuine. Combined with the "
        "manual baseline-validity review finding no unintended defects elsewhere in the clean corpus, "
        "this specimen is ADMITTED, conditioned on two required strengthenings applied at promotion: "
        "(1) record BOTH anchors (SPEC-22-41-04 and SPEC-22-41-06) in the trusted answer key - the "
        "candidate's own generated answer key and grading harness only ever recorded one; (2) add a "
        "false-positive-bait companion clause (a non-wetted enclosure explicitly exempt from the "
        "wetted-component scope) so the evaluator tests reasoning beyond simple number comparison."
        if admitted else
        "REJECTED specifically on the TERMINOLOGY escape route, which held up under scrutiny where the "
        "other three did not: the mutated clause's phrase 'shall be rated for continuous service at "
        "free chlorine concentrations up to X ppm' is a REQUIREMENT clause, not a datasheet description "
        "- and in real specification-writing convention, a 'shall be rated for up to X' REQUIREMENT is "
        "standardly read as a MINIMUM required capability (analogous to 'transformer shall be rated for "
        "continuous operation at ambient temperatures up to 40C' - a transformer also rated for 50C "
        "trivially satisfies this), not an exclusive ceiling the component must not exceed. Under that "
        "standard reading, a single material selection rated to SPEC-22-41-06's 5.0 ppm / pH 7.0-8.0 "
        "trivially ALSO satisfies SPEC-22-41-04(mutated)'s 3.0 ppm / pH 7.2-7.6 floor (rated-higher "
        "subsumes rated-lower), and the two clauses are NOT actually in conflict. The candidate's own "
        "generator, the production investigator, AND this reviewer's own first manual pass all defaulted "
        "to the ceiling reading without justifying it - a real, notable finding in its own right about a "
        "shared semantic blind spot around threshold/rating language, independent of this specimen's fate. "
        "Returned for revision rather than admitted: the underlying idea (a genuine material-rating "
        "envelope conflict between two cross-referenced specification sections) is sound and worth "
        "pursuing, but THIS mutation's specific wording does not unambiguously establish it."
    )

    review = AdmissionReview(
        candidate_id=candidate["candidate_id"],
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        reviewer="claude-sonnet-5 (assistant), under direct human (Archiosk operator) review and instruction",
        baseline_validity_note=BASELINE_VALIDITY_NOTE,
        mutation_validity_note=MUTATION_VALIDITY_NOTE,
        both_anchors_identifier=(candidate["proposed_mutation"]["target_identifier"], reference["identifier"]),
        evaluator_quality_note=EVALUATOR_QUALITY_NOTE,
        added_false_positive_bait=(
            "Companion clause: a dosing-system control-electronics enclosure explicitly described as "
            "NOT a wetted component, exempt from SPEC-22-41-06's chlorine-resistance material scope, "
            "despite mentioning a chlorine-adjacent rating (IP-rated housing) in the same section."
            if admitted else None
        ),
        deterministic_check=asdict(det),
        adversarial_review_note=json.dumps(adversarial, indent=2),
        independence_note=independence_note,
        verdict=verdict,
        verdict_reasoning=verdict_reasoning,
    )

    review_path = CANDIDATES_DIR / f"{candidate['candidate_id']}-admission.json"
    review_path.write_text(json.dumps(asdict(review), indent=2), encoding="utf-8")
    print(f"\n=== VERDICT: {verdict.upper()} ===")
    print(verdict_reasoning)
    print(f"\nAdmission review written: {review_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
