"""CLAUDE-HELP-VOCABULARY-01 - canonical terminology, INTERNAL USE ONLY.

THIS IS NOT A FEATURE, AND MUST NOT BECOME ONE

A visible suggestion surface was built on this module and superseded by the
Product Owner before it shipped. The reasoning is worth keeping attached to the
code: a context-aware Help system should infer what "this" refers to from the UI
context the user came from, and asking someone to learn a glossary is precisely
what such a system exists to make unnecessary. The chips, their CSS and the
generate-time prompt were removed; this module was kept because none of the
reasons to have it depended on showing it.

Permitted uses are normalization, consistency, retrieval, matching Help Scripts,
and output wording. Not permitted: a vocabulary panel, a glossary users consult,
a list of preferred words they are expected to learn, or a required authoring
step. `tests/test_help_vocabulary.py` asserts no route imports this and no
template renders a terminology surface, so a return would be a deliberate act
rather than a quiet drift.

THE PART THAT MATTERS FOR CONTEXTUAL HELP

`suggest_terms` labels every match CANONICAL or AMBIGUOUS, and the second label
is the useful one. A contextual resolver may answer silently only when exactly
one reading is plausible; when two remain it must ask something concise ("Do you
mean Delta Spin or Survival Mode?"). That distinction is the reason this module
survives at all.

THE GOVERNING RULE

Vocabulary may guide wording. Vocabulary must not create facts, claims,
evidence, or authority. Everything in this module is shaped by that one line.

WHY THIS IS A REGISTRY AND NOT A REUSE

The inspection looked for an existing authoritative vocabulary to reuse and did
not find one. `UI_REFERENCE_MAP.md` is a stable-ID registry for CONTROLS - the
wrong axis, it names what a button is rather than what a product noun is called.
The closed vocabularies in `services/` (`OPERATING_ENVIRONMENT_LABELS`,
`_HELP_STATUS_LABELS`, `SPIN_WORLD_OBJECTIVES`) are real and authoritative but
each is a per-feature enum, not a naming vocabulary. `governance/` holds process
vocabulary, not product naming.

So this is a new registry, kept as small as the task allows: a flat list of
terms, not a taxonomy. There is no hierarchy, no category system, no relations
between entries, no per-term metadata beyond what a suggestion needs. If it ever
starts growing structure, that is the signal to ask whether it should have been
derived from somewhere else instead.

WHAT MAKES IT AUTHORITATIVE ANYWAY

The terms are not invented here. Each canonical spelling is one already used by
the published Help guides and the engine's own constants, and
`tests/test_help_vocabulary.py` asserts that every canonical term still appears
in the Help corpus - so a term renamed in the product breaks this registry
rather than silently contradicting it. That check is the whole reason to trust a
list this simple.

DETERMINISTIC, AND THEREFORE FREE

Matching is literal and word-boundary - case-insensitive when looking for a
VARIANT, case-sensitive when deciding a term is already correct (see `_pattern`;
getting that backwards silently suppressed the commonest suggestion there is).
No model call is made or needed. A vocabulary suggestion costs nothing, which is
what lets it run on every submission without reintroducing the continuous-
model-call problem the Studio was careful to avoid.

WHAT IT NEVER DOES

Rewrite anything on its own. `apply_accepted_terms` acts ONLY on terms a caller
explicitly passes in, so normalization is always something a caller chose rather
than something this module decided. It reports ambiguity and never resolves it -
a matcher that quietly picked one reading would be making a content decision
while looking like a spell-checker, and that stays wrong whether the result is
shown to a person or fed to a retrieval step.
"""
from __future__ import annotations

import re
from typing import Optional

# Confidence in a match, and the two behave differently on purpose.
#
# CANONICAL - the variant is an unambiguous misspelling or spacing of exactly
# one product term ("survival mode" -> "Survival Mode"). Stating the preferred
# term is safe because there is nothing else it could have meant.
#
# AMBIGUOUS - the wording plausibly points at a term but could mean something
# else ("second spin" -> Delta Spin?). These are phrased as a QUESTION and are
# never applied without the reviewer saying yes, which is the difference between
# helping someone say what they meant and deciding it for them.
CONFIDENCE_CANONICAL = "canonical"
CONFIDENCE_AMBIGUOUS = "ambiguous"


class Term:
    """One product noun, its canonical spelling, and how people mis-say it.

    A plain class rather than a dataclass hierarchy: this is a list of words.
    The moment it needs inheritance it has stopped being a wording aid.
    """

    __slots__ = ("canonical", "variants", "ambiguous", "note")

    def __init__(self, canonical: str, variants=(), ambiguous=(), note: str = ""):
        self.canonical = canonical
        self.variants = tuple(variants)
        self.ambiguous = tuple(ambiguous)
        self.note = note


# The registry. Canonical spellings are the ones the published Help guides and
# the engine already use - see this module's docstring and the corpus test.
#
# Kept deliberately short. Every entry here is a term a Help author would
# plausibly get wrong in a way that matters to a reader; a term nobody
# mis-writes does not need an entry, and adding one costs a false positive.
CANONICAL_TERMS = (
    Term("First Spin",
         variants=("first spin", "firstspin", "initial spin", "baseline spin"),
         ambiguous=("first run", "the first one"),
         note="The baseline run. There is no other name for it."),
    Term("Delta Spin",
         variants=("delta spin", "deltaspin"),
         ambiguous=("second spin", "next spin", "follow-up spin", "re-spin", "rerun spin"),
         note="Compares current evidence against the baseline."),
    Term("Survival Mode",
         variants=("survival mode", "survivalmode", "survival lens"),
         ambiguous=("survival review", "survival review button", "survival spin",
                    "survival check", "survival scan"),
         note="A lens on either Spin, not a third kind of Spin."),
    Term("Help / Learning Mode",
         variants=("help mode", "learning mode", "help/learning mode"),
         ambiguous=("help section", "tutorial mode"),
         note="Separate from Project Mode; carries no project context."),
    Term("Project Mode",
         variants=("project mode",),
         ambiguous=("work mode", "normal mode"),
         note="Where project work happens."),
    Term("Reconciliation",
         variants=("reconciliation", "reconcile"),
         ambiguous=("folder compare", "file check", "sync check"),
         note="Compares a folder against what is registered."),
    Term("Investigation",
         variants=("investigation",),
         ambiguous=("enquiry", "inquiry", "look-up", "research step"),
         note="A governed step that produces Claims."),
    Term("RFI",
         variants=("rfi", "r.f.i."),
         ambiguous=("request for info", "information request", "query letter"),
         note="Request for Information."),
    Term("WorkProduct",
         variants=("workproduct", "work product"),
         ambiguous=("deliverable", "output document", "artifact"),
         note="The governed container a Script is one kind of."),
)


def _pattern(phrase: str, case_sensitive: bool = False) -> re.Pattern:
    """Word-boundary matching with flexible internal whitespace.

    Flexible whitespace so "survival  mode" and "survival mode" match the same
    entry. Not fuzzy beyond that: edit-distance matching would start suggesting
    terms for words that merely look similar, which is the false-positive
    behaviour that makes an aid like this annoying enough to be ignored.

    CASE MATTERS FOR ONE CALLER AND NOT THE OTHERS, and getting that backwards
    silently disabled the commonest suggestion there is. Deciding a term is
    ALREADY CORRECT has to be case-SENSITIVE - "survival mode" is precisely the
    wording this aid exists to fix, and an insensitive check treated it as
    already canonical and said nothing. Matching a VARIANT stays insensitive,
    because the variants are lowercase spellings by nature.
    """
    body = r"\s+".join(re.escape(w) for w in phrase.split())
    return re.compile(r"\b%s\b" % body, 0 if case_sensitive else re.IGNORECASE)


def suggest_terms(scenario: str, terms=CANONICAL_TERMS) -> list[dict]:
    """Wording suggestions for one scenario. Deterministic; no model call.

    Returns one entry per term worth mentioning, each carrying the matched
    wording, the canonical term, and its confidence. A term the reviewer already
    spelled correctly produces NO suggestion - telling someone they got it right
    is noise, and an aid that fires constantly stops being read.

    Nothing here writes anything. This is a pure function over a string.
    """
    text = str(scenario or "")
    if not text.strip():
        return []

    suggestions = []
    for term in terms:
        if _pattern(term.canonical, case_sensitive=True).search(text):
            continue  # already correct, exactly as spelled - say nothing

        matched = _first_match(text, term.variants)
        if matched is not None:
            suggestions.append({
                "canonical": term.canonical, "matched": matched,
                "confidence": CONFIDENCE_CANONICAL, "note": term.note,
                "message": "Preferred term: %s" % term.canonical,
            })
            continue

        matched = _first_match(text, term.ambiguous)
        if matched is not None:
            suggestions.append({
                "canonical": term.canonical, "matched": matched,
                "confidence": CONFIDENCE_AMBIGUOUS, "note": term.note,
                # A question, not an instruction. The reviewer may well have
                # meant something this registry has never heard of.
                "message": "Did you mean %s?" % term.canonical,
            })
    return suggestions


def _first_match(text: str, phrases) -> Optional[str]:
    """The longest matching phrase, so "survival review button" is not reported
    as "survival review" - the reviewer should see the words they actually
    wrote, or the suggestion looks like it misread them."""
    best = None
    for phrase in phrases:
        found = _pattern(phrase).search(text)
        if found is not None and (best is None or len(found.group(0)) > len(best)):
            best = found.group(0)
    return best


def apply_accepted_terms(scenario: str, accepted, terms=CANONICAL_TERMS) -> str:
    """Rewrite ONLY the wordings the reviewer explicitly accepted.

    `accepted` is the set of canonical terms the reviewer ticked. A term absent
    from it is left exactly as written, including an ambiguous one this module
    was confident about - confidence is not consent.

    Substitution is on the matched variant only, so surrounding words survive
    untouched. The reviewer's scenario is their text; this repairs a name in it
    and never rephrases the sentence around it.
    """
    text = str(scenario or "")
    wanted = {str(a).strip() for a in (accepted or []) if str(a).strip()}
    if not wanted:
        return text

    for term in terms:
        if term.canonical not in wanted:
            continue
        for phrase in sorted(term.variants + term.ambiguous, key=len, reverse=True):
            text = _pattern(phrase).sub(term.canonical, text)
    return text


def canonical_terms() -> list[str]:
    """Every canonical spelling, for a caller that wants to show the list."""
    return [term.canonical for term in CANONICAL_TERMS]
