"""
CLAUDE-P20 self-test laboratory: runs a REAL, blind investigator against
a machine-generated candidate specimen (see tools/self_test_generator.py)
and grades the result against that candidate's OWN, still-unvalidated
proposed answer key.

This is a TEST/LAB script (same status as tools/self_test_lab*.py) -
makes REAL, billed Anthropic calls, never run automatically by the test
suite.

Structural separation this script exists to prove, not just claim:
`as_requirement_items()` below is the ONLY function that touches what the
investigator actually sees, and it reads ONLY candidate["requirements"]
(the clean baseline) plus the target identifier's mutated_text for
Stage 2 - never candidate["proposed_mutation"]["description"],
["mutation_kind"], or candidate["proposed_answer_key"] at all. Those are
read ONLY after the real call returns, by the grading step - the exact
same "answer key consulted only after the blind run" discipline every
tools/self_test_lab*.py script already follows, now applied to a
machine-authored specimen instead of a hand-authored one.

This script marks the candidate's validation_status as "lab_run_
completed" - it never marks anything "promoted" or "golden". Promotion
(rewriting a validated candidate into a real tests/self_test/
golden_corpus_*.py + mutations_*.py pair and registering it in tests/
self_test/manifest.py) is a deliberate, separate, human, out-of-band
step this prototype does not automate.

Requires a real ANTHROPIC_API_KEY in .env - without one this honestly
reports SKIPPED rather than fabricating a result.

Run (against the most recently generated candidate):
    venv/Scripts/python.exe tools/self_test_candidate_lab.py

Run against a specific candidate:
    venv/Scripts/python.exe tools/self_test_candidate_lab.py <candidate_id>
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

from services.bhive_parser import BHiveParser, RequirementItem  # noqa: E402
from services.case_workspace import CaseWorkspaceStore, REQUIREMENT_REGISTRATION_HUMAN_REGISTERED  # noqa: E402
from tests.self_test.evaluator import evaluate  # noqa: E402
from tests.self_test.mutation_schema import DIFFICULTY_TIER_OBVIOUS, PlantedMutation  # noqa: E402

CANDIDATES_DIR = REPO_ROOT / "tests" / "self_test" / "candidates"


def load_candidate(candidate_id: str | None) -> dict:
    if candidate_id:
        path = CANDIDATES_DIR / f"{candidate_id}.json"
    else:
        candidates = sorted(CANDIDATES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            raise FileNotFoundError("No candidates found - run tools/self_test_generator.py first.")
        path = candidates[-1]
    return json.loads(path.read_text(encoding="utf-8")), path


def materialize_clean(store: CaseWorkspaceStore, workspace, sources_dir: Path, candidate: dict) -> dict:
    """Registers the candidate's clean requirements as real Requirements,
    via real Sources - one per distinct source_name. Returns id-by-
    identifier so the mutation step can find its target."""
    sources_dir.mkdir(parents=True, exist_ok=True)
    source_by_name: dict[str, dict] = {}
    ids_by_identifier: dict[str, str] = {}
    for req in candidate["requirements"]:
        source_name = req["source_name"]
        if source_name not in source_by_name:
            path = sources_dir / f"{len(source_by_name)}.txt"
            path.write_text(source_name, encoding="utf-8")
            source_by_name[source_name] = store.add_source(
                workspace, name=source_name, file_path=str(path), kind="text_record", actor="self-test-candidate-lab",
            )
        registered = store.register_requirement(
            workspace, source_id=source_by_name[source_name]["id"], original_requirement_identifier=req["identifier"],
            text_reference=req["text"], created_by="self-test-candidate-lab",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        ids_by_identifier[req["identifier"]] = registered["id"]
    return ids_by_identifier


def as_requirement_items(workspace, requirement_ids: list[str]) -> list[RequirementItem]:
    """The investigator's-eye view: id + text only - never anything from
    candidate["proposed_mutation"]/["proposed_answer_key"]."""
    by_id = {r["id"]: r for r in workspace.requirements}
    return [
        RequirementItem(id=rid, text=by_id[rid]["text_reference"], category="scope_of_work", confidence=0.9, source_line=0)
        for rid in requirement_ids
    ]


def run_consistency_check(requirements: list[RequirementItem]):
    parser = BHiveParser()
    if not parser.api_key:
        print("SKIPPED: no ANTHROPIC_API_KEY configured - cannot run a real blind test.")
        return None
    flags, checked, note = parser._check_consistency(requirements)  # noqa: SLF001 - lab script, not production
    if not checked:
        print(f"SKIPPED: consistency check did not actually run ({note}).")
        return None
    return flags


def print_flags(flags) -> None:
    print(f"Flags raised: {len(flags)}")
    for flag in flags:
        print(f"  - ({flag.requirement_a_id}, {flag.requirement_b_id}): {flag.explanation}")


def main() -> int:
    candidate_id = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        candidate, candidate_path = load_candidate(candidate_id)
    except FileNotFoundError as exc:
        print(f"SKIPPED: {exc}")
        return 1

    print(f"=== Candidate {candidate['candidate_id']} (generated {candidate['generated_at']}) ===")
    print(f"Domain: {candidate['domain_narrative']}")
    print("*** UNVALIDATED - machine-authored, not a trusted Golden specimen ***\n")

    tmp_dir = Path(tempfile.mkdtemp(prefix="self_test_candidate_lab_"))
    try:
        store = CaseWorkspaceStore(tmp_dir)
        workspace = store.get_or_create(f"candidate-{candidate['candidate_id'][:8]}")
        ids_by_identifier = materialize_clean(store, workspace, tmp_dir / "sources", candidate)
        all_ids = list(ids_by_identifier.values())

        print("=== STAGE 1: clean candidate corpus (should find nothing) ===")
        clean_flags = run_consistency_check(as_requirement_items(workspace, all_ids))
        if clean_flags is None:
            return 1
        print_flags(clean_flags)
        if clean_flags:
            print(
                "NOTE: the generator's OWN claim of internal consistency did not hold up under a "
                "real blind run - this alone is useful validation signal, independent of the "
                "mutation stage below."
            )
        else:
            print("PASS: the generator's clean baseline held up - no discrepancy manufactured or found.")

        print("\n=== STAGE 2: candidate + its own proposed mutation (should catch it) ===")
        target_identifier = candidate["proposed_mutation"]["target_identifier"]
        if target_identifier not in ids_by_identifier:
            print(f"FAIL: proposed mutation targets unknown identifier '{target_identifier}'.")
            return 1
        target_id = ids_by_identifier[target_identifier]

        mutated_workspace = store.get_or_create(f"candidate-{candidate['candidate_id'][:8]}-mutated")
        mutated_ids: dict[str, str] = {}
        source_by_name: dict[str, dict] = {}
        for req in candidate["requirements"]:
            text = candidate["proposed_mutation"]["mutated_text"] if req["identifier"] == target_identifier else req["text"]
            source_name = req["source_name"]
            if source_name not in source_by_name:
                path = tmp_dir / "sources_mutated" / f"{len(source_by_name)}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source_name, encoding="utf-8")
                source_by_name[source_name] = store.add_source(
                    mutated_workspace, name=source_name, file_path=str(path), kind="text_record",
                    actor="self-test-candidate-lab",
                )
            registered = store.register_requirement(
                mutated_workspace, source_id=source_by_name[source_name]["id"],
                original_requirement_identifier=req["identifier"], text_reference=text,
                created_by="self-test-candidate-lab", registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
            )
            mutated_ids[req["identifier"]] = registered["id"]

        mutated_flags = run_consistency_check(as_requirement_items(mutated_workspace, list(mutated_ids.values())))
        if mutated_flags is None:
            return 1
        print_flags(mutated_flags)

        # CLAUDE-P22: the candidate's own generated answer key may name a
        # SECOND anchor (the requirement the mutation actually conflicts
        # with) via reference_identifier - optional and backward-
        # compatible, since the original CLAUDE-P20 candidate never had
        # this field and must be preserved unchanged, never retrofitted.
        reference_identifier = candidate["proposed_mutation"].get("reference_identifier")
        secondary_location = mutated_ids.get(reference_identifier) if reference_identifier else None

        answer_key = PlantedMutation(
            mutation_id=f"CANDIDATE-{candidate['candidate_id'][:8]}",
            mutation_kind=candidate["proposed_mutation"]["mutation_kind"],
            difficulty_tier=candidate.get("difficulty_tier", DIFFICULTY_TIER_OBVIOUS),
            description=candidate["proposed_mutation"]["description"],
            location=mutated_ids[target_identifier],
            secondary_location=secondary_location,
            expected_detection=candidate["proposed_answer_key"]["expected_detection"],
            non_defects=candidate["proposed_answer_key"].get("non_defects", []),
        )
        result = evaluate(flags=mutated_flags, answer_key=[answer_key])
        print(f"\nResult (graded against the candidate's OWN, unvalidated proposed answer key): {result.summary()}")
        if result.caught:
            print("The proposed mutation was caught by a real blind investigator run.")
        if result.missed:
            print("The proposed mutation was MISSED - either the mutation is too subtle, or the corpus is malformed.")
        if result.confirmed_false_positives:
            print("A flag matched a declared non-defect - a real false positive against the candidate's own claims.")
        if result.unplanted_and_unexplained:
            print("A flag with no answer-key match was raised - needs human judgment.")

        candidate["validation_status"] = "lab_run_completed"
        candidate["lab_run_summary"] = {
            "clean_stage_flags": len(clean_flags),
            "mutation_caught": bool(result.caught),
            "confirmed_false_positives": len(result.confirmed_false_positives),
        }
        candidate_path.write_text(json.dumps(candidate, indent=2), encoding="utf-8")

        print(
            "\n*** validation_status = 'lab_run_completed'. This is still NOT a promotion. A human "
            "must read this transcript and the candidate JSON and explicitly decide whether to "
            "hand-author it into a real tests/self_test/golden_corpus_*.py + mutations_*.py pair "
            "and register it in tests/self_test/manifest.py. Nothing here does that automatically. ***"
        )
        return 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
