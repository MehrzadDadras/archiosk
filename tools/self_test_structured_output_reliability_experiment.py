"""
CLAUDE-P26 self-test laboratory: isolated structured-output reliability.

Investigates the malformed-output pattern CLAUDE-P25 observed in the
isolated two-clause condition: correct underlying scope reasoning, an
initial JSON block, appended self-correction prose ("wait, let me
reconsider"), sometimes a second JSON block, ~50% malformed rate - with
little or no recurrence in normal full-batch context.

A TEST/LAB script (same status as every other tools/self_test_*.py
script) - makes MANY real, billed Anthropic calls, never run
automatically by the test suite. Read-only with respect to every
existing candidate/admission/recheck file - CLAUDE-P26 does not
reconsider or promote candidate 276cac42; it only reuses that
candidate's own clean pair as one of three reliability specimens.

Three specimens, each run in ISOLATED (2-item) and BATCH (5-7 item)
context:
  - aquatic       : the aquatic-centre candidate's clean SPEC-22-41-
                    04/-06 pair (reused, unmodified).
  - dense_clean   : CLAUDE-P25's dense HVAC/purge-cooling RECONCILED
                    pair (reused, unmodified).
  - dense_conflict: a NEW dense HVAC/purge-cooling pair, same domain and
                    clause-bundling shape, but a genuine, overlapping-
                    scope contradiction (CLAUDE-P26 addition).

Three calling modes on the ISOLATED context (where the effect was
observed) to test candidate causes:
  - baseline : today's exact production call (plain text, default
               temperature) - establishes the reliability rate as-is.
  - temp0    : identical prompt, temperature=0 - tests whether sampling
               temperature is a contributing factor.
  - tooluse  : the SAME reasoning content, but requested via a forced
               Anthropic tool-use call (schema-enforced structured
               output) instead of "respond only with JSON" free text -
               tests whether API-level structured output is a safe fix.

The BATCH context is run under `baseline` only (P25 already found
batch context to be reliable; this just confirms it directly for these
same three specimens with the P26 classifier, at a handful of reps).

Every response is classified with tests/self_test/
structured_output_classifier.py's seven-way scheme - never silently
resolved by picking "the first" or "the last" block when conclusions
actually conflict. Raw response text (or, for tool-use, the raw
tool_use input) and full classification detail are preserved per run.

Run:
    venv/Scripts/python.exe tools/self_test_structured_output_reliability_experiment.py
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

from services.bhive_parser import BHiveParser, RequirementItem  # noqa: E402
from services.case_workspace import CaseWorkspaceStore  # noqa: E402
from tools.self_test_candidate_lab import as_requirement_items, materialize_clean  # noqa: E402
from services.consistency_response_parser import (  # noqa: E402
    MULTIPLE_CONFLICTING_JSON,
    MULTIPLE_EQUIVALENT_JSON,
    SINGLE_VALID_JSON,
    UNUSABLE,
    ClassifiedResponse,
    classify_response,
    pair_signature,
)
from tests.self_test.structured_output_reliability_bank import (  # noqa: E402
    BATCH_FILLER_ITEMS,
    DENSE_CONFLICT_ITEM_A,
    DENSE_CONFLICT_ITEM_B,
    DENSE_RECONCILED_PAIR,
)

CANDIDATES_DIR = REPO_ROOT / "tests" / "self_test" / "candidates"
AQUATIC_CANDIDATE_ID = "276cac42-07c8-4866-be91-b78c9798cb6e"
AQUATIC_TARGET_IDENTIFIER = "SPEC-22-41-04"
AQUATIC_REFERENCE_IDENTIFIER = "SPEC-22-41-06"


@dataclass
class ReliabilityRun:
    run_id: str
    specimen: str
    context: str  # "isolated" | "batch"
    mode: str  # "baseline" | "temp0" | "tooluse"
    repetition: int
    category: str
    resolved_flag_count: int | None  # None when unsafe to resolve (conflicting) or unusable
    accuracy: str  # "correct" | "incorrect" | "unknown"
    raw_response_text: str
    latency_seconds: float | None
    input_tokens: int | None
    output_tokens: int | None
    stop_reason: str | None
    notes: str
    timestamp: str


def _apply_p25_gate(flags: list[dict]) -> list[dict]:
    """Mirrors services/bhive_parser.py's CLAUDE-P25 deterministic
    post-validation exactly, so this investigation measures the same
    final answer production would actually reach - duplicated here
    deliberately since this is investigation tooling, not production
    code."""
    kept = []
    for entry in flags:
        if not isinstance(entry, dict):
            continue
        reasoning = str(entry.get("scope_reconciliation_reasoning", "")).strip()
        overlap = entry.get("scopes_overlap")
        if not reasoning:
            continue
        if overlap is False:
            continue
        kept.append(entry)
    return kept


def _reasoning_body(requirements: list[RequirementItem]) -> str:
    full_prompt = BHiveParser._build_consistency_prompt(requirements)  # noqa: SLF001
    marker = "Respond ONLY with a JSON array of objects"
    idx = full_prompt.index(marker)
    return full_prompt[:idx].rstrip()


def _tool_schema() -> dict:
    field_schema = {"type": "string"}
    return {
        "name": "report_contradictions",
        "description": (
            "Report any genuine contradictions found among the given requirements, "
            "using the structured scope-reconciliation reasoning described above. "
            "If there are no contradictions, call this with an empty flags array."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flags": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "a": field_schema,
                            "b": field_schema,
                            "requirement_a_evidence": field_schema,
                            "requirement_b_evidence": field_schema,
                            "requirement_a_obligation": field_schema,
                            "requirement_b_obligation": field_schema,
                            "requirement_a_scope": field_schema,
                            "requirement_b_scope": field_schema,
                            "scopes_overlap": {"type": "boolean"},
                            "scope_reconciliation_reasoning": field_schema,
                            "reconciliation_checked": {"type": "boolean"},
                            "explanation": field_schema,
                        },
                        "required": [
                            "a", "b", "requirement_a_evidence", "requirement_b_evidence",
                            "requirement_a_obligation", "requirement_b_obligation",
                            "requirement_a_scope", "requirement_b_scope", "scopes_overlap",
                            "scope_reconciliation_reasoning", "reconciliation_checked", "explanation",
                        ],
                    },
                },
            },
            "required": ["flags"],
        },
    }


def _call_baseline(client, model: str, requirements: list[RequirementItem], temperature: float | None):
    prompt = BHiveParser._build_consistency_prompt(requirements)  # noqa: SLF001
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    start = time.perf_counter()
    response = client.messages.create(
        model=model, max_tokens=1500, messages=[{"role": "user", "content": prompt}], **kwargs,
    )
    latency = time.perf_counter() - start
    text_out = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    return text_out, latency, response


def _classify_tooluse(response) -> ClassifiedResponse:
    tool_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
    if not tool_blocks:
        return ClassifiedResponse(category=UNUSABLE, notes="No tool_use block returned.")
    values = [b.input.get("flags", []) for b in tool_blocks]
    if len(values) == 1:
        return ClassifiedResponse(category=SINGLE_VALID_JSON, blocks=values, resolved_value=values[0])
    signatures = {pair_signature(v) for v in values}
    if len(signatures) == 1:
        return ClassifiedResponse(category=MULTIPLE_EQUIVALENT_JSON, blocks=values, resolved_value=values[-1])
    return ClassifiedResponse(
        category=MULTIPLE_CONFLICTING_JSON, blocks=values, resolved_value=None,
        notes=f"{len(values)} tool_use blocks with differing conclusions.",
    )


def _call_tooluse(client, model: str, requirements: list[RequirementItem]):
    body = _reasoning_body(requirements) + "\n\nCall report_contradictions with your findings."
    start = time.perf_counter()
    response = client.messages.create(
        model=model, max_tokens=1500,
        tools=[_tool_schema()], tool_choice={"type": "tool", "name": "report_contradictions"},
        messages=[{"role": "user", "content": body}],
    )
    latency = time.perf_counter() - start
    return response, latency


def _accuracy(resolved_flags: list[dict] | None, expected_conflict_pair: tuple[str, str] | None) -> str:
    if resolved_flags is None:
        return "unknown"
    kept = _apply_p25_gate(resolved_flags)
    if expected_conflict_pair is None:
        return "correct" if not kept else "incorrect"
    ids = expected_conflict_pair
    found = any({e.get("a"), e.get("b")} == set(ids) for e in kept)
    return "correct" if found else "incorrect"


def run_condition(
    specimen: str, context: str, mode: str, requirements: list[RequirementItem],
    reps: int, client, model: str, expected_conflict_pair: tuple[str, str] | None,
    runs: list[ReliabilityRun],
) -> None:
    print(f"\n=== {specimen} / {context} / {mode} ({reps} reps) ===")
    for rep in range(1, reps + 1):
        try:
            if mode == "tooluse":
                response, latency = _call_tooluse(client, model, requirements)
                raw_text = json.dumps([b.input for b in response.content if getattr(b, "type", None) == "tool_use"])
                classified = _classify_tooluse(response)
            else:
                temperature = 0.0 if mode == "temp0" else None
                text_out, latency, response = _call_baseline(client, model, requirements, temperature)
                raw_text = text_out
                classified = classify_response(text_out)
        except Exception as exc:  # noqa: BLE001 - deliberately broad: this IS the transport-failure path
            run = ReliabilityRun(
                run_id=str(uuid.uuid4()), specimen=specimen, context=context, mode=mode, repetition=rep,
                category="transport_failure", resolved_flag_count=None, accuracy="unknown",
                raw_response_text="", latency_seconds=None, input_tokens=None, output_tokens=None,
                stop_reason=None, notes=str(exc), timestamp=datetime.now(timezone.utc).isoformat(),
            )
            runs.append(run)
            print(f"  #{rep}: TRANSPORT_FAILURE ({exc})")
            continue

        usage = getattr(response, "usage", None)
        accuracy = _accuracy(classified.resolved_value, expected_conflict_pair)
        run = ReliabilityRun(
            run_id=str(uuid.uuid4()), specimen=specimen, context=context, mode=mode, repetition=rep,
            category=classified.category,
            resolved_flag_count=(len(classified.resolved_value) if classified.resolved_value is not None else None),
            accuracy=accuracy, raw_response_text=raw_text,
            latency_seconds=latency, input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None), stop_reason=getattr(response, "stop_reason", None),
            notes=classified.notes, timestamp=datetime.now(timezone.utc).isoformat(),
        )
        runs.append(run)
        print(f"  #{rep}: {classified.category} (accuracy={accuracy}, blocks={len(classified.blocks)})")


def main() -> int:
    parser_cli = argparse.ArgumentParser()
    parser_cli.add_argument("--isolated-reps", type=int, default=6)
    parser_cli.add_argument("--temp0-reps", type=int, default=4)
    parser_cli.add_argument("--tooluse-reps", type=int, default=6)
    parser_cli.add_argument("--batch-reps", type=int, default=3)
    args = parser_cli.parse_args()

    bhive_parser = BHiveParser()
    if not bhive_parser.api_key:
        print("SKIPPED: no ANTHROPIC_API_KEY configured - cannot run a real experiment.")
        return 1

    import anthropic
    client = anthropic.Anthropic(api_key=bhive_parser.api_key, timeout=bhive_parser.consistency_timeout)

    tmp_dir = Path(tempfile.mkdtemp(prefix="self_test_structured_output_reliability_"))
    runs: list[ReliabilityRun] = []
    try:
        candidate = json.loads((CANDIDATES_DIR / f"{AQUATIC_CANDIDATE_ID}.json").read_text(encoding="utf-8"))
        store = CaseWorkspaceStore(tmp_dir)
        workspace = store.get_or_create("p26-reliability-aquatic")
        ids_by_identifier = materialize_clean(store, workspace, tmp_dir / "sources", candidate)
        workspace = store.get(workspace.project_id)
        aquatic_items = as_requirement_items(workspace, list(ids_by_identifier.values()))
        by_id = {item.id: item for item in aquatic_items}
        aquatic_isolated = [
            by_id[ids_by_identifier[AQUATIC_TARGET_IDENTIFIER]],
            by_id[ids_by_identifier[AQUATIC_REFERENCE_IDENTIFIER]],
        ]
        aquatic_batch = aquatic_items

        dense_clean_isolated = [DENSE_RECONCILED_PAIR.item_a, DENSE_RECONCILED_PAIR.item_b]
        dense_clean_batch = BATCH_FILLER_ITEMS + dense_clean_isolated

        dense_conflict_isolated = [DENSE_CONFLICT_ITEM_A, DENSE_CONFLICT_ITEM_B]
        dense_conflict_batch = BATCH_FILLER_ITEMS + dense_conflict_isolated

        specimens = [
            ("aquatic", aquatic_isolated, aquatic_batch, None),
            ("dense_clean", dense_clean_isolated, dense_clean_batch, None),
            (
                "dense_conflict", dense_conflict_isolated, dense_conflict_batch,
                (DENSE_CONFLICT_ITEM_A.id, DENSE_CONFLICT_ITEM_B.id),
            ),
        ]

        for name, isolated_items, batch_items, expected_pair in specimens:
            run_condition(name, "isolated", "baseline", isolated_items, args.isolated_reps, client, bhive_parser.model, expected_pair, runs)
            run_condition(name, "isolated", "temp0", isolated_items, args.temp0_reps, client, bhive_parser.model, expected_pair, runs)
            run_condition(name, "isolated", "tooluse", isolated_items, args.tooluse_reps, client, bhive_parser.model, expected_pair, runs)
            run_condition(name, "batch", "baseline", batch_items, args.batch_reps, client, bhive_parser.model, expected_pair, runs)

        out_path = REPO_ROOT / "tests" / "self_test" / "experiments" / f"structured_output_reliability_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        out_path.write_text(json.dumps([asdict(r) for r in runs], indent=2), encoding="utf-8")

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        by_key: dict[tuple[str, str, str], list[ReliabilityRun]] = {}
        for r in runs:
            by_key.setdefault((r.specimen, r.context, r.mode), []).append(r)
        for key, group in by_key.items():
            cats = {}
            for r in group:
                cats[r.category] = cats.get(r.category, 0) + 1
            incorrect = sum(1 for r in group if r.accuracy == "incorrect")
            print(f"{key}: {cats} | incorrect_accuracy={incorrect}/{len(group)}")

        print(f"\nAll {len(runs)} runs recorded: {out_path.relative_to(REPO_ROOT)}")
        return 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
