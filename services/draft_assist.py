"""
CLAUDE-COMPOSER-DRAFT-ASSIST-01 - sharpen a draft before it is sent, without
taking it over.

Product Owner: "A lot of ARCHIOSK work begins as rough professional language: an
RFI question; a site observation; an email; a meeting note; a Finding
description; a clarification request. I want to write naturally first, then let
GO help sharpen the language without changing my meaning or taking control away
from me."

THE RISK THIS MODULE IS SHAPED AROUND

Not clumsy rewriting. The real hazard in professional construction language is a
model quietly ADDING something - a dimension, a date, a drawing number, a code
clause, a commitment, an admission of liability - into text the reviewer then
issues as an RFI or an email. A rewrite that reads beautifully and contains one
invented reference is far worse than no rewrite at all, because it is signed by
a person who only skimmed it.

So every prompt below carries the same hard instruction, and it is the first
instruction rather than an afterthought: sharpen wording only, never introduce a
fact the original did not contain. Where the model has nothing to work with, it
must say so instead of inventing filler.

CONTROL STAYS WITH THE REVIEWER, STRUCTURALLY

Nothing in this module writes to a draft. It returns a PROPOSAL as data; the
Composer shows it beside the original and the reviewer chooses Replace, Insert
below, or Discard. "Do not silently overwrite the user's draft" is therefore not
a rule anyone has to remember - there is no code path here that could.

CHECK AMBIGUITY IS NOT A REWRITE

It returns observations about what a reader could misread, and the client offers
no Replace for it. Answering "what is ambiguous here?" with silently-resolved
prose would hide the very thing that was asked about.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from services.llm_gateway import call_llm_json

logger = logging.getLogger(__name__)

# A draft is short by nature. This is a guard against pasting a whole document
# into an external call, not a quality judgement.
MAX_DRAFT_CHARS = 6000


@dataclass(frozen=True)
class DraftAction:
    """One thing the reviewer can ask for.

    `rewrites` is False for actions that REPORT rather than revise - the client
    uses it to decide whether Replace is even offered, so an observation can
    never be pasted back over the draft as though it were a revision.
    """

    key: str
    label: str
    instruction: str
    rewrites: bool = True


# A closed vocabulary, deliberately: the action arrives from the client, and an
# open one would let a caller supply arbitrary instructions to the model through
# a form field. Unknown keys are rejected, never passed through.
DRAFT_ACTIONS: tuple[DraftAction, ...] = (
    DraftAction("clarify", "Rewrite clearly",
                "Rewrite it so a busy professional reader understands it on one pass. "
                "Keep every fact, number and reference exactly as given."),
    DraftAction("shorter", "Make shorter",
                "Say the same thing in fewer words. Remove padding and repetition, "
                "never a fact, a qualification or a condition."),
    DraftAction("longer", "Make longer",
                "Expand ONLY what is already implied by the text - fuller sentences, "
                "explicit connections between points the draft already makes. Do not "
                "add new content to reach length; if there is nothing to expand, say so."),
    DraftAction("formal", "Make more formal",
                "Raise the register to professional correspondence. Do not make it "
                "pompous, and do not soften a clear statement into a vague one."),
    DraftAction("direct", "Make more direct",
                "Remove hedging and get to the point. Keep any genuine uncertainty the "
                "author expressed - directness is not false confidence."),
    DraftAction("rfi", "Turn into RFI wording",
                "Recast as a Request for Information: state the specific matter, cite "
                "only references the draft itself gives, and ask one clear question. "
                "Never invent a drawing number, specification section or clause."),
    DraftAction("observation", "Turn into site observation",
                "Recast as a factual site observation: what was seen, where, when, as "
                "stated. No cause, no fault, no compliance conclusion, no recommendation "
                "unless the draft already contains one."),
    DraftAction("meeting_note", "Turn into meeting note",
                "Recast as a concise meeting note: decisions, actions and owners as "
                "recorded in the draft. Never invent an attendee, a date or an action."),
    DraftAction("email", "Turn into email",
                "Recast as a short professional email body. No invented greeting details, "
                "no commitments the draft does not make. Subject line only if the draft "
                "implies one."),
    DraftAction("grammar", "Improve grammar only",
                "Correct grammar, spelling and punctuation. Change nothing else - not "
                "word choice, not structure, not tone."),
    DraftAction("ambiguity", "Check ambiguity",
                "Do NOT rewrite. List what a reader could reasonably misunderstand: "
                "unclear referents, undefined terms, missing scope or dates, statements "
                "that could be read two ways. Be specific and brief. If it is clear, say "
                "so plainly.",
                rewrites=False),
)

_ACTIONS_BY_KEY = {action.key: action for action in DRAFT_ACTIONS}

# Carried into every call, first, before the per-action instruction. The order
# matters: this is the constraint the model must weigh the instruction against.
_SYSTEM_PROMPT = (
    "You are helping a construction and design professional sharpen their own draft "
    "before they send it. "
    "ABSOLUTE RULE, which overrides every other instruction you are given: you may "
    "improve wording, structure and tone, but you must NEVER introduce a fact the "
    "original does not contain. Never invent or alter a dimension, quantity, date, "
    "party, drawing number, specification section, code clause, cost, deadline, "
    "obligation, admission or recommendation. If the draft is too thin to do what was "
    "asked, say so in the 'note' field rather than inventing material to fill it. "
    "Preserve the author's meaning and their level of certainty exactly - do not turn a "
    "tentative observation into a firm conclusion, and do not soften a firm statement. "
    "Return the reviewer's own voice, sharpened; not your own. "
    'Respond ONLY with a JSON object of exactly this shape: '
    '{"proposal": "<the revised text, or your observations>", "note": "<one short '
    'sentence about anything you could not do, or an empty string>"}.'
)


@dataclass
class DraftProposal:
    ran: bool
    action: str
    label: str
    rewrites: bool
    proposal: Optional[str] = None
    note: Optional[str] = None
    reason: Optional[str] = None


def available_actions() -> list[dict]:
    return [{"key": a.key, "label": a.label, "rewrites": a.rewrites} for a in DRAFT_ACTIONS]


def assist(draft: str, action_key: str, *, api_key=None, model=None) -> DraftProposal:
    """Produce a proposal for `draft`. Never mutates anything."""
    action = _ACTIONS_BY_KEY.get((action_key or "").strip())
    if action is None:
        return DraftProposal(ran=False, action=action_key or "", label="", rewrites=False,
                             reason="That is not an available draft action.")

    text = (draft or "").strip()
    if not text:
        return DraftProposal(ran=False, action=action.key, label=action.label,
                             rewrites=action.rewrites,
                             reason="There is nothing in the draft yet.")
    if len(text) > MAX_DRAFT_CHARS:
        return DraftProposal(ran=False, action=action.key, label=action.label,
                             rewrites=action.rewrites,
                             reason=f"That draft is longer than {MAX_DRAFT_CHARS} characters.")

    outcome = call_llm_json(
        user_prompt=(action.instruction + "\n\n--- THE AUTHOR'S DRAFT ---\n" + text),
        system_prompt=_SYSTEM_PROMPT,
        max_tokens=1200,
        log_label=f"Composer draft assist: {action.key}",
        api_key=api_key,
        model=model,
    )
    if not outcome.ran or not isinstance(outcome.parsed, dict):
        return DraftProposal(ran=False, action=action.key, label=action.label,
                             rewrites=action.rewrites,
                             reason="I could not work on that just now. Your draft is untouched.")

    proposal = str(outcome.parsed.get("proposal") or "").strip()
    if not proposal:
        return DraftProposal(ran=False, action=action.key, label=action.label,
                             rewrites=action.rewrites,
                             reason="Nothing came back. Your draft is untouched.")

    return DraftProposal(
        ran=True, action=action.key, label=action.label, rewrites=action.rewrites,
        proposal=proposal,
        note=(str(outcome.parsed.get("note") or "").strip() or None),
    )
