"""
CLAUDE-P26 - classifies a raw consistency-check model response into one
of seven categories.

Lives in services/, not tests/, because services/bhive_parser.py's
_check_consistency uses this directly in production: a controlled
investigation (tools/self_test_structured_output_reliability_
experiment.py) found real (if intermittent - 0/57 in a fresh sample,
but repeatedly observed in CLAUDE-P25's actual production recheck
runs) cases where the model's response contains a valid JSON array
plus harmless self-correction prose, or plus a second, materially
different JSON array - both of which the previous single strict
`json.loads(cleaned)` call discarded outright as a parse failure, even
when the response contained a perfectly good, usable answer.

Pure text-processing, no network calls, no dependency on BHiveParser
itself - hermetically testable in isolation (tests/test_structured_
output_classifier.py) and reused as-is by the self-test tooling above.

The seven categories, in the order CLAUDE-P26 asked they be
distinguished:

  SINGLE_VALID_JSON            - exactly one well-formed top-level JSON
                                  array, and nothing else in the response.
  VALID_JSON_THEN_HARMLESS_PROSE - exactly one well-formed array, plus
                                  surrounding/trailing text that is not
                                  itself an attempt at a second JSON
                                  value (no other unmatched bracket).
  MULTIPLE_EQUIVALENT_JSON     - 2+ well-formed arrays whose FLAGGED
                                  PAIRS (by id-pair + scopes_overlap)
                                  agree - e.g. a self-correction that
                                  restates the same conclusion.
  MULTIPLE_CONFLICTING_JSON    - 2+ well-formed arrays that disagree on
                                  what should be flagged - never silently
                                  resolved by picking one.
  MALFORMED_BUT_REPAIRABLE     - no well-formed array found directly,
                                  but a bounded repair (closing an
                                  unterminated array/object, most
                                  commonly from output truncation)
                                  recovers exactly one valid array.
  UNUSABLE                     - no valid JSON recoverable by any of the
                                  above.
  TRANSPORT_FAILURE            - the API call itself did not return a
                                  response (network/timeout/5xx) - never
                                  produced from response TEXT; the caller
                                  reports this directly from the
                                  exception path.

Distinguishing MULTIPLE_EQUIVALENT_JSON from MULTIPLE_CONFLICTING_JSON,
rather than ever silently taking "the first" or "the last" block, is
the direct answer to CLAUDE-P26's instruction: "Do not silently accept
the first JSON block if later content materially contradicts it."
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

SINGLE_VALID_JSON = "single_valid_json"
VALID_JSON_THEN_HARMLESS_PROSE = "valid_json_then_harmless_prose"
MULTIPLE_EQUIVALENT_JSON = "multiple_equivalent_json"
MULTIPLE_CONFLICTING_JSON = "multiple_conflicting_json"
MALFORMED_BUT_REPAIRABLE = "malformed_but_repairable"
UNUSABLE = "unusable"
TRANSPORT_FAILURE = "transport_failure"


@dataclass
class ClassifiedResponse:
    category: str
    blocks: list = field(default_factory=list)          # each successfully-parsed JSON array value
    repaired_value: list | None = None                    # only set for MALFORMED_BUT_REPAIRABLE
    resolved_value: list | None = None                    # the value a caller SHOULD use, or None if unsafe to pick one
    notes: str = ""


def _strip_code_fences(text: str) -> str:
    lines = text.strip().splitlines()
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        out.append(line)
    return "\n".join(out)


def _scan_balanced_arrays(text: str) -> tuple[list[tuple[int, int, str]], tuple[int, str] | None]:
    """Scans for top-level '[' ... ']' spans, respecting JSON string
    literals so brackets inside quoted evidence text don't miscount.

    Returns (complete_spans, trailing_incomplete) where complete_spans is
    a list of (start, end, substring) for every balanced array found, and
    trailing_incomplete is (start, substring_to_end) if the text ends
    with an unclosed '[' - a common truncation signature - or None.
    """
    complete: list[tuple[int, int, str]] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "[":
            i += 1
            continue
        start = i
        depth = 0
        in_string = False
        escape = False
        j = i
        closed = False
        while j < n:
            c = text[j]
            if in_string:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    in_string = False
            else:
                if c == '"':
                    in_string = True
                elif c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        closed = True
                        break
            j += 1
        if closed:
            complete.append((start, j, text[start:j]))
            i = j
        else:
            return complete, (start, text[start:])
    return complete, None


def _attempt_repair(fragment: str) -> list | None:
    """Bounded repair for a truncated trailing array: progressively trim
    back to the last complete top-level object and close the array.
    Never invents content - only removes an incomplete tail."""
    body = fragment.lstrip()
    if not body.startswith("["):
        return None
    body = body[1:]
    # Try trimming back to each "}," or "}" boundary, closing with "]".
    candidates: list[int] = [m for m in range(len(body)) if body[m] == "}"]
    for end in reversed(candidates):
        trimmed = body[: end + 1].rstrip()
        if trimmed.endswith(","):
            trimmed = trimmed[:-1]
        try:
            value = json.loads("[" + trimmed + "]")
        except json.JSONDecodeError:
            continue
        return value
    return None


def pair_signature(parsed: list) -> frozenset:
    """Public so callers comparing JSON obtained via a different transport
    (e.g. tool-use blocks, which are never free text) can reuse the same
    equivalent-vs-conflicting comparison this module uses internally."""
    sig = set()
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        pair = frozenset([entry.get("a"), entry.get("b")])
        sig.add((pair, entry.get("scopes_overlap")))
    return frozenset(sig)


_pair_signature = pair_signature


def classify_response(raw_text: str) -> ClassifiedResponse:
    cleaned = _strip_code_fences(raw_text)
    complete_spans, trailing_incomplete = _scan_balanced_arrays(cleaned)

    parsed_blocks: list[tuple[int, int, list]] = []
    for start, end, substring in complete_spans:
        try:
            value = json.loads(substring)
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            parsed_blocks.append((start, end, value))

    if not parsed_blocks:
        if trailing_incomplete is not None:
            repaired = _attempt_repair(trailing_incomplete[1])
            if repaired is not None:
                return ClassifiedResponse(
                    category=MALFORMED_BUT_REPAIRABLE,
                    repaired_value=repaired,
                    resolved_value=repaired,
                    notes="Recovered by closing a truncated trailing array.",
                )
        return ClassifiedResponse(category=UNUSABLE, notes="No recoverable JSON array found.")

    if len(parsed_blocks) == 1:
        start, end, value = parsed_blocks[0]
        remainder = (cleaned[:start] + cleaned[end:]).strip()
        if not remainder:
            return ClassifiedResponse(category=SINGLE_VALID_JSON, blocks=[value], resolved_value=value)
        return ClassifiedResponse(
            category=VALID_JSON_THEN_HARMLESS_PROSE, blocks=[value], resolved_value=value,
            notes=f"Trailing/surrounding non-JSON text ({len(remainder)} chars) ignored.",
        )

    values = [v for _, _, v in parsed_blocks]
    signatures = {_pair_signature(v) for v in values}
    if len(signatures) == 1:
        # Equivalent conclusions - the LAST is the model's own final,
        # self-corrected statement, so it's the one to use.
        return ClassifiedResponse(
            category=MULTIPLE_EQUIVALENT_JSON, blocks=values, resolved_value=values[-1],
            notes=f"{len(values)} blocks, all reaching the same flagged-pair conclusion.",
        )
    return ClassifiedResponse(
        category=MULTIPLE_CONFLICTING_JSON, blocks=values, resolved_value=None,
        notes=(
            f"{len(values)} blocks with DIFFERING conclusions about which pairs to flag - "
            "not safe to resolve automatically."
        ),
    )
