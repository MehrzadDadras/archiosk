"""
CLAUDE-P13R self-test laboratory - the real, hand-run blind exercise.

This is a TEST/LAB script, not production code (same status as
tests/fixtures/nreocrc/ingest_nreocrc_lab.py) - it makes REAL, billed
Anthropic API calls and is never run automatically by the test suite
(see tests/test_self_test_harness.py for the hermetic, mocked version of
this same plumbing that DOES run on every suite invocation).

Runs services/bhive_parser.py's real, existing consistency-check -
BEEHIVE's own document-understanding capability - blind against:
  1. the Golden Corpus, unmutated - proving Archiosk can leave a good
     document alone rather than manufacturing discrepancies;
  2. the Golden Corpus with one planted mutation - proving Archiosk
     catches a specific, known defect.

The investigator (BHiveParser._check_consistency) is given ONLY
requirement id/category/text - never tests/self_test/mutations.py's
PlantedMutation, never this script's own answer-key variable - so it
cannot "remember the exam answers." The answer key is consulted only
AFTER the real call returns, by the evaluator.

Requires a real ANTHROPIC_API_KEY in .env (see config.py/bhive_parser.py -
without one, the consistency stage honestly skips with checked=False and
this script reports that rather than fabricating a result).

CLAUDE-P19: `run_tier()` is this tier's entry point for tools/self_test_
runner.py's cross-tier regression runner - it does exactly what `main()`
always did, just returning structured SpecimenResult records (see tests/
self_test/run_record.py) instead of only an exit code. `main()` is now a
thin wrapper so standalone hand-running is unchanged:

    venv/Scripts/python.exe tools/self_test_lab.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

from services.bhive_parser import BHiveParser, CONSISTENCY_PROMPT_VERSION  # noqa: E402
from tests.self_test.evaluator import evaluate  # noqa: E402
from tests.self_test.golden_corpus import golden_requirements  # noqa: E402
from tests.self_test.mutation_schema import DIFFICULTY_TIER_OBVIOUS  # noqa: E402
from tests.self_test.mutations import apply_numerical_contradiction  # noqa: E402
from tests.self_test.run_record import SpecimenResult  # noqa: E402

CORPUS_VERSION = "1.0"
MUTATION_VERSION = "1.0"
PRODUCTION_REASONING_PATH = "BHiveParser._check_consistency"


def run_consistency_check(requirements):
    parser = BHiveParser()
    if not parser.api_key:
        print("SKIPPED: no ANTHROPIC_API_KEY configured - cannot run a real blind test.")
        return None
    flags, checked, note = parser._check_consistency(requirements)  # noqa: SLF001 - lab script, not production
    if not checked:
        print(f"SKIPPED: consistency check did not actually run ({note}).")
        return None
    return flags


def run_tier() -> list[SpecimenResult]:
    specimens: list[SpecimenResult] = []
    model = BHiveParser().model

    print("=== STAGE 1: clean Golden Corpus (should find nothing) ===")
    start = time.perf_counter()
    clean_flags = run_consistency_check(golden_requirements())
    elapsed = time.perf_counter() - start
    if clean_flags is None:
        specimens.append(SpecimenResult(
            tier_id=DIFFICULTY_TIER_OBVIOUS, specimen_id="001-clean",
            description="Clean Golden Corpus - should find nothing.",
            production_reasoning_path=PRODUCTION_REASONING_PATH, corpus_version=CORPUS_VERSION,
            model=model, prompt_version=CONSISTENCY_PROMPT_VERSION,
            ran=False, skipped_reason="No ANTHROPIC_API_KEY configured, or consistency check did not run.",
        ))
        return specimens
    print(f"Flags raised on the clean corpus: {len(clean_flags)}")
    for flag in clean_flags:
        print(f"  - ({flag.requirement_a_id}, {flag.requirement_b_id}): {flag.explanation}")
    if clean_flags:
        print(
            "NOTE: the 'golden' corpus was not actually clean, OR Archiosk manufactured "
            "a discrepancy that isn't real - this needs human review either way."
        )
    else:
        print("PASS: Archiosk left the clean document alone.")
    specimens.append(SpecimenResult(
        tier_id=DIFFICULTY_TIER_OBVIOUS, specimen_id="001-clean",
        description="Clean Golden Corpus - should find nothing.",
        production_reasoning_path=PRODUCTION_REASONING_PATH, corpus_version=CORPUS_VERSION,
        model=model, prompt_version=CONSISTENCY_PROMPT_VERSION,
        false_positives=[f.explanation for f in clean_flags],
        model_call_count=1, latency_seconds=elapsed,
    ))

    print("\n=== STAGE 2: Golden Corpus + one planted mutation (should catch it) ===")
    mutated_requirements, answer_key = apply_numerical_contradiction(golden_requirements())
    print(f"Planted: {answer_key.mutation_id} ({answer_key.difficulty_tier}) - {answer_key.description}")

    start = time.perf_counter()
    mutated_flags = run_consistency_check(mutated_requirements)
    elapsed = time.perf_counter() - start
    if mutated_flags is None:
        specimens.append(SpecimenResult(
            tier_id=DIFFICULTY_TIER_OBVIOUS, specimen_id=answer_key.mutation_id,
            description=answer_key.description, production_reasoning_path=PRODUCTION_REASONING_PATH,
            corpus_version=CORPUS_VERSION, mutation_version=MUTATION_VERSION,
            planted_condition=answer_key.description, expected_detection_type=answer_key.mutation_kind,
            expected_anchors=[answer_key.location], expected_non_findings=answer_key.non_defects,
            model=model, prompt_version=CONSISTENCY_PROMPT_VERSION,
            ran=False, skipped_reason="No ANTHROPIC_API_KEY configured, or consistency check did not run.",
        ))
        return specimens

    result = evaluate(flags=mutated_flags, answer_key=[answer_key])
    print(f"Flags raised on the mutated corpus: {len(mutated_flags)}")
    for flag in mutated_flags:
        print(f"  - ({flag.requirement_a_id}, {flag.requirement_b_id}): {flag.explanation}")
    print(f"\nResult: {result.summary()}")
    if result.caught:
        print("PASS: the planted defect was caught.")
    if result.missed:
        print("FAIL: the planted defect was missed.")
    if result.confirmed_false_positives:
        print("NOTE: raised a flag matching a declared non-defect - a real false positive.")
    if result.unplanted_and_unexplained:
        print(
            "NOTE: raised a flag with no answer-key match - needs human judgment: "
            "hallucination, or a genuine discovery this corpus's author didn't anticipate."
        )

    specimens.append(SpecimenResult(
        tier_id=DIFFICULTY_TIER_OBVIOUS, specimen_id=answer_key.mutation_id,
        description=answer_key.description, production_reasoning_path=PRODUCTION_REASONING_PATH,
        corpus_version=CORPUS_VERSION, mutation_version=MUTATION_VERSION,
        planted_condition=answer_key.description, expected_detection_type=answer_key.mutation_kind,
        expected_anchors=[answer_key.location], expected_non_findings=answer_key.non_defects,
        model=model, prompt_version=CONSISTENCY_PROMPT_VERSION,
        caught=bool(result.caught), false_positives=result.confirmed_false_positives,
        unexpected_valid_discoveries=result.unplanted_and_unexplained,
        model_call_count=1, latency_seconds=elapsed,
    ))
    return specimens


def main() -> int:
    specimens = run_tier()
    verdicts = [s.passed() for s in specimens]
    if not specimens or all(v is None for v in verdicts):
        return 1
    return 0 if all(v is not False for v in verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
