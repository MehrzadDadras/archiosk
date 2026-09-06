"""CLAUDE-HELP-CONTEXT-01 - resolve what the user means, then look it up.

THE DEFECT THIS REPLACES

`/help/mode/ask` matched a Help Script by exact string equality on its
originating question. "What does this do?" could therefore only ever match a
Script whose stored question was literally "What does this do?" - which would be
a nonsense Script, since that question has no meaning without the control it was
asked from. Contextual Help was impossible by construction, not by omission.

RESOLVE, THEN LOOK UP

Meaning is settled first, from what the application already knows, and only then
is a Script retrieved. The user is never asked to restate something ARCHIOSK can
see: standing on the Survival Mode checkbox and asking "what does this do?" is a
complete question, and treating it as ambiguous would be the system pretending
not to know where the user is standing.

CONTEXT NARROWS MEANING; IT NEVER INVENTS IT

The two halves of that are equally load-bearing. A `ui_ref` tells us WHICH
control is being asked about - it does not tell us the answer, and it confers no
authority. When context leaves more than one reading plausible, this module
returns a clarification rather than picking one, because a resolver that guessed
would be making a content decision while looking like a lookup.

WHY ui_ref AND NOT A NEW TAXONOMY

`data-ui-ref` already identifies every control, is emitted into the DOM, and is
held to bidirectional parity with `UI_REFERENCE_MAP.md` by test - every ref in a
template has a registry row and every active row appears in a template. That is
a stronger identity guarantee than anything a new registry would start with. The
refs are dotted-hierarchical (`toolbox` panel, `.spin` feature,
`.world-survival` control), so panel-level context falls out of the same field
by prefix, and no second vocabulary is needed for pages and panels.

NO PROJECT CONTEXT, STRUCTURALLY

This module is handed a question, a Help context and the Help library. It has no
project workspace parameter and constructs none, so there is no call from here
that could read project evidence, claims, documents or memory. A question that
IS about the user's project is answered with an offer to transition, never with
project material - the same boundary `services/help_mode.py` already draws,
enforced the same way.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from services.help_mode import HELP_LIBRARY_PROJECT_ID, propose_project_transition

# How a subject was settled. Reported back so a caller - and a test - can tell
# "resolved from the control the user was standing on" from "guessed from their
# wording", which are very different levels of confidence wearing the same
# answer.
BASIS_CONTROL = "control"
BASIS_PANEL = "panel"
BASIS_CONVERSATION = "conversation"
BASIS_FREE_TEXT = "free_text"
BASIS_NONE = "none"

# Words that refer to something already on screen or already said. Their
# presence is what makes a question DEPENDENT on context rather than
# self-contained - "what does this do?" needs a referent, "what is Survival
# Mode?" does not.
_REFERENTIAL = re.compile(
    r"\b(this|that|it|these|those|here|the button|the control|the checkbox)\b", re.IGNORECASE)

# Explicit references to the user's own project. Deliberately narrow: these are
# possessive or demonstrative references to a project, not merely any word that
# also appears in project work. "What is an RFI?" is a Help question; "the RFI
# in my project" is not.
_PROJECT_REFERENCE = re.compile(
    r"\b(my|our|this|the)\s+(project|case|job|site)\b|\bin\s+my\s+\w+\b", re.IGNORECASE)

_WORD = re.compile(r"[a-z0-9]+")
_NOISE = frozenset({
    "the", "and", "for", "that", "this", "with", "from", "what", "when", "where",
    "which", "into", "have", "has", "are", "was", "were", "not", "but", "you",
    "your", "does", "did", "do", "is", "be", "as", "at", "or", "of", "to", "in",
    "on", "it", "a", "an", "if", "how", "why", "can", "will", "would", "about",
    "mean", "means", "another", "other", "kind",
})


@dataclass(frozen=True)
class HelpResolution:
    """What the user meant, how we know, and what to do about it."""

    basis: str = BASIS_NONE
    subject: Optional[str] = None
    script_id: Optional[str] = None
    candidates: tuple = ()
    clarification: Optional[str] = None
    project_transition: Optional[dict] = None
    resolved_question: Optional[str] = None

    @property
    def answered(self) -> bool:
        return self.script_id is not None

    def to_dict(self) -> dict:
        return {
            "basis": self.basis,
            "subject": self.subject,
            "script_id": self.script_id,
            "candidates": [dict(c) for c in self.candidates],
            "clarification": self.clarification,
            "project_transition": self.project_transition,
            "resolved_question": self.resolved_question,
        }


def resolve_help_subject(
    store, question: str, context: Optional[dict] = None,
    active_script_id: Optional[str] = None, project_id: Optional[str] = None,
) -> HelpResolution:
    """Settle what a Help question is about, in strict priority order.

    1. EXACT CONTROL. A `ui_ref` in the context is the strongest signal there
       is: the user is standing on the thing they are asking about.
    2. PANEL / PAGE. The ref prefix, when no exact control matched. Narrower
       than nothing, weaker than a control - and it may well leave several
       readings, which becomes a clarification rather than a guess.
    3. HELP CONVERSATION. A referential follow-up ("why?", "what happens
       next?") continues the topic already being explained. Only applied to
       questions that actually need a referent, so a self-contained question
       is never quietly re-pointed at the previous topic.
    4. FREE TEXT. The user's own wording, when the application knows nothing
       useful about where they are.
    5. CLARIFICATION. More than one plausible reading survives.

    Project-specific questions short-circuit ALL of it with a transition offer.
    Answering "how does this affect the smoke-control review in my project?"
    from the Help library would answer a question the user did not ask, using
    general material, while sounding project-specific - worse than declining.
    """
    question = (question or "").strip()
    context = context or {}

    if _is_project_specific(question):
        return HelpResolution(
            basis=BASIS_NONE,
            project_transition=propose_project_transition(question, project_id),
            clarification=None,
        )

    scripts = _answerable_scripts(store)
    ref = str(context.get("control") or "").strip().lower()

    if ref:
        exact = [s for s in scripts if ref in s["ui_refs"]]
        if exact:
            return _settle(exact, BASIS_CONTROL, ref, question)

        prefix = _panel_prefix(ref)
        if prefix:
            near = [s for s in scripts
                    if any(r == prefix or r.startswith(prefix + ".") for r in s["ui_refs"])]
            if near:
                return _settle(near, BASIS_PANEL, prefix, question)

    page = str(context.get("page") or "").strip().lower()
    if page:
        near = [s for s in scripts
                if any(r == page or r.startswith(page + ".") for r in s["ui_refs"])]
        if near:
            return _settle(near, BASIS_PANEL, page, question)

    # A follow-up only continues the topic when it actually needs a referent.
    if active_script_id and _REFERENTIAL.search(question):
        current = [s for s in scripts if s["id"] == active_script_id]
        if current:
            return _settle(current, BASIS_CONVERSATION, current[0]["title"], question)

    matches = _free_text_matches(scripts, question)
    if matches:
        return _settle(matches, BASIS_FREE_TEXT, None, question)

    return HelpResolution(basis=BASIS_NONE, resolved_question=question)


def _settle(candidates: list, basis: str, subject: Optional[str], question: str) -> HelpResolution:
    """One candidate answers; more than one asks."""
    if len(candidates) == 1:
        script = candidates[0]
        return HelpResolution(
            basis=basis, subject=subject or script["title"], script_id=script["id"],
            resolved_question=script["question"] or question,
        )
    return HelpResolution(
        basis=basis, subject=subject,
        candidates=tuple({"script_id": s["id"], "title": s["title"]} for s in candidates),
        clarification=_clarification([s["title"] for s in candidates]),
        resolved_question=question,
    )


def _clarification(titles: list) -> str:
    """One concise question, naming the readings rather than describing that
    ambiguity exists - "please be more specific" tells the user nothing they
    did not already know."""
    named = [t for t in titles if t]
    if len(named) == 2:
        return "Do you mean %s or %s?" % (named[0], named[1])
    return "Do you mean %s, or %s?" % (", ".join(named[:-1]), named[-1])


def _panel_prefix(ref: str) -> Optional[str]:
    """`toolbox.spin.world-survival` -> `toolbox.spin`. One level up, not the
    root: `toolbox` alone would sweep in every unrelated control in the panel
    and turn a narrow question into a wide clarification."""
    parts = ref.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else None


def _is_project_specific(question: str) -> bool:
    """Does this question ask about the user's own project?

    Narrow on purpose. Over-detecting sends ordinary Help questions to a
    transition offer, which is its own failure - "what is an RFI?" must be
    answered, not deflected.
    """
    return bool(_PROJECT_REFERENCE.search(question or ""))


def _terms(text: str) -> set:
    return {w for w in _WORD.findall(str(text or "").lower())
            if len(w) > 2 and w not in _NOISE}


def _free_text_matches(scripts: list, question: str) -> list:
    """Scripts whose subject the wording actually points at.

    Term overlap against each Script's title and originating question. Every
    script sharing the BEST score is returned, not just one - two equally good
    readings is precisely the case that must become a clarification, and
    silently taking the first would be the guess this module exists to avoid.
    """
    wanted = _terms(question)
    if not wanted:
        return []

    scored = []
    for script in scripts:
        # The title is weighted because it names the subject, while the
        # originating question shares filler with every other question.
        overlap = (2 * len(wanted & _terms(script["title"]))
                   + len(wanted & _terms(script["question"])))
        if overlap:
            scored.append((overlap, script))

    if not scored:
        return []
    best = max(score for score, _ in scored)
    return [script for score, script in scored if score == best]


def _answerable_scripts(store) -> list:
    """Every REUSABLE Help Script, with what resolution needs and nothing else.

    Release stays exactly where it was: `help_status_for(...)["answerable"]` is
    true only at REUSABLE, so contextual resolution can reach nothing a human
    has not signed off for reuse. Context decides WHICH Script is relevant; it
    has no bearing on whether that Script may be shown.
    """
    from services.script_fit import help_status_for

    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    out = []
    for script in workspace.work_products:
        if script.get("artifact_type") != "script":
            continue
        readiness = store.resolve_script_readiness(workspace, script["id"])
        if not help_status_for(readiness)["answerable"]:
            continue
        out.append({
            "id": script["id"],
            "title": script.get("title") or "",
            "question": readiness.get("question") or "",
            "ui_refs": [str(r).lower() for r in (script.get("help_ui_refs") or [])],
        })
    return out
