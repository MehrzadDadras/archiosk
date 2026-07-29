"""
CLAUDE-P25 supplementary recheck: additional repetitions of ONLY the
isolated_pair_clean condition for candidate 276cac42-07c8-4866-be91-
b78c9798cb6e, against the just-fixed structured scope-reconciliation
production path.

Why this exists as a separate script: the first full 8-condition recheck
(tools/self_test_candidate_recheck_276cac42.py) got 0/2 valid (parseable)
results for isolated_pair_clean - both real model responses correctly
reasoned scopes_overlap=false and a disjoint occupied/non-occupied
temporal scope, but then appended "wait, let me reconsider" narration
after an initial JSON array, followed by a second JSON array, breaking
strict single-JSON-blob parsing. This script exists purely to gather
more repetitions on that ONE condition to tell reproducible instability
apart from a one-off malformed-output rate - it changes nothing about
the candidate, the prompt, or the parser.

Read-only with respect to every existing candidate/admission/recheck
file. Writes only a new, separate results file.

Run:
    venv/Scripts/python.exe tools/self_test_isolated_pair_recheck_276cac42.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

from services.bhive_parser import BHiveParser, CONSISTENCY_PROMPT_VERSION  # noqa: E402
from services.case_workspace import CaseWorkspaceStore  # noqa: E402
from tools.self_test_candidate_lab import as_requirement_items, materialize_clean  # noqa: E402

CANDIDATES_DIR = REPO_ROOT / "tests" / "self_test" / "candidates"
CANDIDATE_ID = "276cac42-07c8-4866-be91-b78c9798cb6e"
TARGET_IDENTIFIER = "SPEC-22-41-04"
REFERENCE_IDENTIFIER = "SPEC-22-41-06"
REPS = 6


@dataclass
class Run:
    repetition: int
    checked: bool
    note: str | None
    flags: list[dict]
    raw_response_text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_seconds: float | None
    timestamp: str


def main() -> int:
    candidate = json.loads((CANDIDATES_DIR / f"{CANDIDATE_ID}.json").read_text(encoding="utf-8"))
    parser = BHiveParser()
    if not parser.api_key:
        print("SKIPPED: no ANTHROPIC_API_KEY configured - cannot run a real recheck.")
        return 1

    tmp_dir = Path(tempfile.mkdtemp(prefix="self_test_isolated_pair_recheck_"))
    runs: list[Run] = []
    try:
        store = CaseWorkspaceStore(tmp_dir)
        workspace = store.get_or_create("candidate-276cac42-isolated-recheck")
        ids_by_identifier = materialize_clean(store, workspace, tmp_dir / "sources_clean", candidate)
        workspace = store.get(workspace.project_id)
        clean_items = as_requirement_items(workspace, list(ids_by_identifier.values()))
        clean_by_id = {item.id: item for item in clean_items}
        target_id = ids_by_identifier[TARGET_IDENTIFIER]
        reference_id = ids_by_identifier[REFERENCE_IDENTIFIER]
        pair = [clean_by_id[target_id], clean_by_id[reference_id]]

        print(f"=== isolated_pair_clean ({REPS} reps) ===")
        for rep in range(1, REPS + 1):
            usage_sink: dict = {}
            flags, checked, note = parser._check_consistency(pair, usage_sink=usage_sink)  # noqa: SLF001
            run = Run(
                repetition=rep, checked=checked, note=note,
                flags=[{"a": f.requirement_a_id, "b": f.requirement_b_id, "explanation": f.explanation,
                        "scopes_overlap": f.scopes_overlap, "scope_reconciliation_reasoning": f.scope_reconciliation_reasoning}
                       for f in flags],
                raw_response_text=usage_sink.get("raw_response_text", ""),
                input_tokens=usage_sink.get("input_tokens"), output_tokens=usage_sink.get("output_tokens"),
                latency_seconds=usage_sink.get("latency_seconds"),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            runs.append(run)
            status = "SKIPPED (malformed)" if not checked else f"{len(flags)} flag(s)"
            print(f"  #{rep}: {status}")

        out_path = CANDIDATES_DIR / f"{CANDIDATE_ID}-isolated-pair-recheck-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        out_path.write_text(json.dumps([asdict(r) for r in runs], indent=2), encoding="utf-8")

        valid = [r for r in runs if r.checked]
        clean = [r for r in valid if len(r.flags) == 0]
        print(f"\n{len(valid)}/{len(runs)} valid (parseable) runs; {len(clean)}/{len(valid)} of those correctly clean.")
        print(f"All runs recorded: {out_path.relative_to(REPO_ROOT)}")
        return 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
