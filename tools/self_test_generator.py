"""
CLAUDE-P20 self-test laboratory: the candidate specimen generator
prototype.

This is a TEST/LAB script (same status as tools/self_test_lab*.py) -
makes REAL, billed Anthropic calls, never run automatically by the test
suite. It is deliberately NOT wired into anything trusted: its output
lands under tests/self_test/candidates/, a holding area tests/self_test/
manifest.py and tools/self_test_runner.py never look at. Nothing this
script produces is a Golden Laboratory Suite v1 tier - it is a candidate
for one, and stays a candidate until a human explicitly promotes it (a
manual, out-of-band step this prototype does not automate - see this
script's own closing print for why).

CLAUDE-P19's own closing analysis named the risk this design answers:
"the system must never treat a machine-authored document as 'perfect'
merely because the generator says it is." Concretely, that means:

1. TWO SEPARATE real model calls, not one - generate_clean_corpus() only
   ever asks for an internally-consistent requirement set; it is never
   told a mutation is coming. propose_mutation() is a SEPARATE call, given
   only the clean corpus, asked to introduce exactly one defect. Keeping
   these as genuinely separate calls (mirroring golden_corpus_*.py vs
   mutations_*.py's existing file-level separation for every human-
   authored tier) means the "clean" corpus is never drafted with the
   defect already in mind.

2. The proposed mutation and proposed answer key are the model's OWN
   CLAIM about what it did - carrying zero epistemic weight until a
   human independently reviews tools/self_test_candidate_lab.py's real,
   blind investigator run against it. This script never marks anything
   "validated," "golden," or "trusted" - only "generated."

3. Domain diversity: the generator is explicitly told NOT to reuse the
   standby-power/fuel-autonomy scenario every existing tier already uses
   - a real, if partial, guard against the generator's own output being a
   trivial restatement of a scenario this codebase has already solved.

Known, honestly-stated limitation of this prototype: both real calls use
the SAME model that services/requirement_investigation.py and services/
bhive_parser.py use to investigate. A shared model creates a real,
unresolved risk that the generator's "obvious" defect is obvious
specifically to ITS OWN blind spots, not to defects in general - this
prototype does not attempt to solve that (a genuinely independent second
model, or a human-authored corpus, would be needed to rule it out), it
only names it plainly rather than hiding it.

Requires a real ANTHROPIC_API_KEY in .env - without one this honestly
reports SKIPPED rather than fabricating a result.

Run:
    venv/Scripts/python.exe tools/self_test_generator.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

CANDIDATES_DIR = REPO_ROOT / "tests" / "self_test" / "candidates"
DEFAULT_TIMEOUT_SECONDS = 30.0

CLEAN_CORPUS_PROMPT = """You are authoring a GOLDEN TEST CORPUS for a construction/procurement \
document-understanding system - a small, internally-consistent set of contract/RFP-style \
requirement statements with NO defects, contradictions, or ambiguity between them.

Invent an ORIGINAL project domain of your own choosing - explicitly NOT standby/backup power, \
generator fuel autonomy, or emergency power duration (that scenario is already used elsewhere \
and would not test anything new). Choose a different technical domain entirely (e.g. structural, \
mechanical, electrical, civil, life-safety, envelope, commissioning, or any other real \
construction/procurement subject you judge suitable).

Write between 4 and 6 short requirement statements for this domain. They must be genuinely, \
carefully consistent with each other - a human reviewing them should find nothing to flag.

Respond ONLY with a JSON object, no prose, no markdown fences:
{"domain_narrative": "<one paragraph describing the invented domain, for a human reader>", \
"requirements": [{"identifier": "<short id like 'R1' or a real-looking section number>", \
"source_name": "<a real-sounding document name, e.g. 'RFP Section 6' or 'Structural Basis of Design'>", \
"text": "<the requirement text itself>"}, ...]}"""

MUTATION_PROMPT_TEMPLATE = """Here is a clean, internally-consistent requirement set for a real \
construction/procurement domain:

{corpus_json}

Introduce EXACTLY ONE deliberate, precisely-located defect: choose ONE requirement above and \
rewrite its text so that it now genuinely contradicts (numerically, logically, or in scheduling \
terms) at least one OTHER requirement in this same set. Change nothing else - every other \
requirement's text must be reproduced completely unchanged in your answer. The defect must be a \
real, unambiguous contradiction a careful reviewer would actually catch - not something contrived \
or merely stylistic.

Respond ONLY with a JSON object, no prose, no markdown fences:
{{"target_identifier": "<the identifier of the ONE requirement you changed>", \
"mutated_text": "<its new, contradictory text>", \
"mutation_kind": "<short label, e.g. 'numerical_contradiction'>", \
"description": "<plain-language description of the defect, for a human reading the answer key>", \
"expected_detection": "<what a correct investigator run should say>", \
"non_defects": ["<a brief note on why each OTHER requirement is unrelated and must not be flagged>", ...]}}"""


def _call_model(prompt: str, api_key: str, model: str, timeout: float) -> dict:
    import anthropic  # imported lazily, matches every other real-call module in this codebase

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    response = client.messages.create(
        model=model, max_tokens=2048, messages=[{"role": "user", "content": prompt}],
    )
    text_out = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
    cleaned = re.sub(r"^```(json)?|```$", "", text_out.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


def generate_clean_corpus(api_key: str, model: str, timeout: float) -> dict:
    """Call #1 - never told a mutation is coming."""
    return _call_model(CLEAN_CORPUS_PROMPT, api_key, model, timeout)


def propose_mutation(clean_corpus: dict, api_key: str, model: str, timeout: float) -> dict:
    """Call #2 - a SEPARATE real call, given only the clean corpus."""
    prompt = MUTATION_PROMPT_TEMPLATE.format(corpus_json=json.dumps(clean_corpus["requirements"], indent=2))
    return _call_model(prompt, api_key, model, timeout)


def main() -> int:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("SKIPPED: no ANTHROPIC_API_KEY configured - cannot generate a real candidate.")
        return 1
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    timeout = float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))

    print("=== CALL 1: generating a clean candidate corpus (no mutation mentioned) ===")
    clean_corpus = generate_clean_corpus(api_key, model, timeout)
    print(f"Domain: {clean_corpus['domain_narrative']}")
    for r in clean_corpus["requirements"]:
        print(f"  [{r['identifier']}] ({r['source_name']}): {r['text']}")

    print("\n=== CALL 2: proposing one mutation against the clean corpus (separate call) ===")
    mutation = propose_mutation(clean_corpus, api_key, model, timeout)
    print(f"Target: {mutation['target_identifier']}")
    print(f"Mutated text: {mutation['mutated_text']}")
    print(f"Mutation kind: {mutation['mutation_kind']}")
    print(f"Description: {mutation['description']}")

    candidate_id = str(uuid.uuid4())
    candidate = {
        "candidate_id": candidate_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_model": model,
        "difficulty_tier": "obvious",
        "domain_narrative": clean_corpus["domain_narrative"],
        "requirements": clean_corpus["requirements"],
        "proposed_mutation": {
            "target_identifier": mutation["target_identifier"],
            "mutated_text": mutation["mutated_text"],
            "mutation_kind": mutation["mutation_kind"],
            "description": mutation["description"],
        },
        "proposed_answer_key": {
            "expected_detection": mutation["expected_detection"],
            "non_defects": mutation.get("non_defects", []),
        },
        "validation_status": "generated",
    }

    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    path = CANDIDATES_DIR / f"{candidate_id}.json"
    path.write_text(json.dumps(candidate, indent=2), encoding="utf-8")

    print(f"\nCandidate written: {path.relative_to(REPO_ROOT)}")
    print(
        "\n*** validation_status = 'generated' - UNVALIDATED. This is a candidate, not a Golden "
        "specimen. Run tools/self_test_candidate_lab.py against it to exercise a real, blind "
        "investigator run, then a HUMAN must read that result and explicitly decide whether to "
        "promote it - this script does not, and will never, do that automatically. ***"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
