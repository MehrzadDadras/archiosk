"""CLAUDE-PLANNING-WORKSPACE-02A - what a person adds, visibly not authority.

    ORIGINAL GOVERNED RESULT   (host-owned, immutable for this interaction)
      + USER CONTRIBUTION      (classified, provenanced, never a host fact)
      + FOLLOW-UP REVIEW       (deterministic comparison against the result)
      + ADMISSION DECISION     (admitted or quarantined, per 64ddd93)

FOUR LAYERS, NEVER MERGED. A workspace where a person can type into the same
surface that carries municipal authority is exactly where laundering happens by
accident: the typing looks like the record, the record looks like the typing, and
a week later nobody can tell which sentence came from the City. So every layer is
a separate object with its own origin, and `layered()` returns them separately
rather than as one list a template could flatten.

THIS MODULE ADDS NO NEW GOVERNANCE MACHINERY. Entity binding is
`services/entity_binding.py`, posture is `services/planning_posture.py`, statutory
effect is `go_pdz_contract`'s vocabulary and admissibility table, and the
quarantine discipline is the one already committed. What is new here is only the
CLASSIFICATION of human input and the wiring of those three into a follow-up
path. A parallel copy of any of them would be a second definition of a rule whose
whole value is that there is one.

WHAT A CONTRIBUTION CAN AND CANNOT DO. It can contradict the result, supply an
object for evaluation, state what an owner wants, ask a question, or record a
professional's reading. It cannot become a host fact by being typed confidently.
`AUTHORITY_SAYS`, `PROPERTY_FACT` and `DETERMINISTIC_DERIVATION` are host
classes and a contribution may never carry one - not because a person is less
trustworthy than a model, but because neither is the City.

    SILENCE IS EVIDENCE ABOUT WHAT WAS FOUND.
    A VALUE MATCH WITHOUT ROLE FIDELITY IS NOT CORROBORATION.
    AUTHORITY MAY IMPROVE POSTURE. DERIVATION ALONE MAY NOT.

THE REVIEW HERE IS DETERMINISTIC AND SAYS SO. It compares the contribution
against host facts and reports what binds, what does not, and what that implies
for posture. It does NOT call a model. A model-authored follow-up interpretation
would newly route `feasibility_compiler`'s egress through a live signed-in
request, and that is a deployment decision rather than a rendering one - see this
tranche's return note. What is here needs no such authorization and already
answers the question that matters most: does what the person said survive contact
with what the City published?
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

from services import entity_binding
from services import go_pdz_contract as contract
from services import planning_posture as posture

CONTRIBUTION_VERSION = "planning-contribution@1"

# --- section 11. The visible classification vocabulary -----------------------
#: The DEFAULT, and deliberately the weakest thing that is still true. A person
#: who types without choosing has asserted that they typed something.
CLASS_USER_INPUT = "USER_INPUT"
CLASS_USER_OBSERVATION = "USER_OBSERVATION"
CLASS_USER_HYPOTHESIS = "USER_HYPOTHESIS"
CLASS_OWNER_INTENT = "OWNER_INTENT"
CLASS_USER_SUPPLIED_EVIDENCE = "USER_SUPPLIED_EVIDENCE"
CLASS_USER_QUESTION = "USER_QUESTION"
CLASS_PROFESSIONAL_JUDGMENT = "PROFESSIONAL_JUDGMENT"

CLASSIFICATIONS = (
    CLASS_USER_INPUT, CLASS_USER_OBSERVATION, CLASS_USER_HYPOTHESIS,
    CLASS_OWNER_INTENT, CLASS_USER_SUPPLIED_EVIDENCE, CLASS_USER_QUESTION,
    CLASS_PROFESSIONAL_JUDGMENT,
)

#: What a person is shown beside their own words. Plain language on purpose: a
#: classification the contributor cannot read is not a visible classification.
CLASSIFICATION_LABELS = {
    CLASS_USER_INPUT: "Your input",
    CLASS_USER_OBSERVATION: "Your observation",
    CLASS_USER_HYPOTHESIS: "Your hypothesis",
    CLASS_OWNER_INTENT: "Owner intent",
    CLASS_USER_SUPPLIED_EVIDENCE: "Evidence you supplied",
    CLASS_USER_QUESTION: "Your question",
    CLASS_PROFESSIONAL_JUDGMENT: "Professional judgment",
}

#: Section 11's prohibition, as a list rather than as a warning. These are the
#: contract's own host classes; a contribution carrying one would be claiming to
#: be the City, the parcel record, or our own verifier.
HOST_ONLY_CLASSES = (
    "AUTHORITY_SAYS", "PROPERTY_FACT",
    contract.DERIVATION_DIRECT_AUTHORITY, contract.DERIVATION_PROPERTY_FACT,
    contract.DERIVATION_DETERMINISTIC,
)

# --- section 12. What a supplied object carries ------------------------------
#: `USER_SUPPLIED_EVIDENCE` means "the user supplied an object that can be
#: evaluated". It does NOT mean the contents are authoritative, and this is the
#: field that keeps those two apart.
PROVENANCE_SUPPLIED_BY_USER = "SUPPLIED_BY_USER"
AUTHORITY_STATUS_UNVERIFIED = "UNVERIFIED_BY_ARCHIOSK"

# --- section 18. Admission outcomes, reusing the committed vocabulary --------
ADMISSION_ADMITTED = "ADMITTED"
ADMISSION_QUARANTINED = "QUARANTINED"
#: A question asserts nothing, so there is nothing to bind and nothing to admit.
ADMISSION_NOT_APPLICABLE = "NO_FACTUAL_ASSERTION"

#: Wording that claims a grant. Deliberately the SAME shape of test the validator
#: applies to a model (`_PERMISSIVE_VOICE`), because the rule is about the claim,
#: not about who made it.
_PERMISSIVE = re.compile(
    r"\b(?:is permitted|are permitted|is allowed|are allowed|permits|allows|"
    r"no parking requirement|no requirement|there is no limit|unrestricted|"
    r"as[- ]of[- ]right|may be (?:built|constructed|erected|developed))\b",
    re.IGNORECASE)

#: Wording that reasons FROM an absence. "The by-law says nothing about X, so X
#: is fine" is two claims, and the second does not follow from the first.
_FROM_SILENCE = re.compile(
    r"\b(?:no express provision|says nothing|silent|not mentioned|"
    r"nothing prohibits|no provision|does not mention|isn't mentioned|"
    r"is not mentioned|no rule)\b", re.IGNORECASE)

#: Wording that concedes relief is needed - which LOWERS posture, and is
#: therefore always admissible.
_RELIEF_LANGUAGE = re.compile(
    r"\b(?:variance|relief|rezoning|zoning by-?law amendment|"
    r"committee of adjustment|minor variance|may require relief|"
    r"would require relief|official plan amendment)\b", re.IGNORECASE)

#: Wording that proposes testing something rather than asserting it.
_TEST_LANGUAGE = re.compile(
    r"\b(?:test|explore|what if|could we|consider|try|assume|hypothetical|"
    r"wants to|would like to|looking to)\b", re.IGNORECASE)


def classify(requested) -> str:
    """The classification a contribution actually gets.

    FALLS BACK TO THE WEAKEST VALUE, NEVER TO A HOST CLASS. An unrecognised
    request - including a deliberate attempt to submit `AUTHORITY_SAYS` - becomes
    `USER_INPUT`. Refusing loudly would be defensible too, but a refusal that
    discards what the person wrote is worse than recording it honestly at the
    weakest strength, and the strength is what governs.
    """
    if requested in CLASSIFICATIONS:
        return requested
    return CLASS_USER_INPUT


def classification_label(classification) -> str:
    return CLASSIFICATION_LABELS.get(classification,
                                     CLASSIFICATION_LABELS[CLASS_USER_INPUT])


def _digest(value) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def contribution(text, *, classification=None, supplied_by=None,
                 submitted_at=None, object_name=None, object_kind=None,
                 object_bytes=None, relates_to=None) -> dict:
    """One human contribution, with its provenance attached at creation.

    NOTHING HERE IS INTERPRETED. The text is recorded as given, trimmed only at
    the ends; the classification is recorded as resolved; and a supplied object
    keeps its own name, kind, size and digest so the record can say WHAT was
    supplied without the bytes travelling any further than the request.
    """
    resolved = classify(classification)
    record = {
        "contribution_version": CONTRIBUTION_VERSION,
        "classification": resolved,
        "classification_label": classification_label(resolved),
        # Section 11: the contributor sees this, so it is part of the record
        # rather than a presentation detail a template could omit.
        "is_host_owned": False,
        "text": (text or "").strip(),
        "supplied_by": supplied_by,
        "submitted_at": submitted_at,
        "provenance": PROVENANCE_SUPPLIED_BY_USER,
        "authority_status": AUTHORITY_STATUS_UNVERIFIED,
        "relates_to": relates_to,
    }
    if object_name or object_kind or object_bytes is not None:
        # Section 12. The object is DESCRIBED, and described honestly: supplying
        # a municipal email records that a person supplied a file they called a
        # municipal email, which is a different fact from the City having written
        # one.
        record["supplied_object"] = {
            "name": object_name,
            "kind": object_kind,
            "byte_count": len(object_bytes) if object_bytes is not None else None,
            "sha256": (hashlib.sha256(object_bytes).hexdigest()
                       if object_bytes else None),
            "provenance": PROVENANCE_SUPPLIED_BY_USER,
            "authority_status": AUTHORITY_STATUS_UNVERIFIED,
            "label": "USER-SUPPLIED",
        }
    record["text_sha256"] = _digest(record["text"])
    return record


def declared_statutory_effect(text) -> dict:
    """What statutory effect this human text is entitled to, and on what basis.

    Section 15. A person writing "there is no parking requirement" has reported
    what they did not find. That is `NO_EXPRESS_PROVISION` at best, and where
    they go on to draw a permission from it, the EFFECT THEY ASSERTED is not one
    the basis can support - so it types as `UNRESOLVED_EFFECT` and the overreach
    is recorded rather than silently downgraded.

    Never returns `EXPLICIT_PERMISSION`. A contribution cannot supply a governing
    basis for a grant; only an instrument can, and an instrument reaches ARCHIOSK
    through `planning_authority`, not through a textarea.
    """
    body = text or ""
    permissive = _PERMISSIVE.search(body)
    from_silence = _FROM_SILENCE.search(body)

    if permissive and from_silence:
        return {
            "statutory_effect": contract.EFFECT_UNRESOLVED,
            "effect_basis": contract.BASIS_UNRESOLVED,
            "asserted_effect": contract.EFFECT_EXPLICIT_PERMISSION,
            "overreach": True,
            "detail": ("the contribution reasons from an absence to a "
                       "permission; silence is evidence about what was found "
                       "and permission requires a governing basis"),
            "matched": [permissive.group(0), from_silence.group(0)],
        }
    if permissive:
        return {
            "statutory_effect": contract.EFFECT_UNRESOLVED,
            "effect_basis": contract.BASIS_UNRESOLVED,
            "asserted_effect": contract.EFFECT_EXPLICIT_PERMISSION,
            "overreach": True,
            "detail": ("the contribution states a permission; no governing "
                       "instrument was supplied with it, so the effect is "
                       "unresolved rather than granted"),
            "matched": [permissive.group(0)],
        }
    if from_silence:
        return {
            "statutory_effect": contract.EFFECT_NO_EXPRESS_PROVISION,
            "effect_basis": contract.BASIS_UNRESOLVED,
            "asserted_effect": contract.EFFECT_NO_EXPRESS_PROVISION,
            "overreach": False,
            "detail": ("the contribution reports an absence; recorded as an "
                       "absence, which is what it is"),
            "matched": [from_silence.group(0)],
        }
    return {"statutory_effect": None, "effect_basis": None,
            "asserted_effect": None, "overreach": False,
            "detail": None, "matched": []}


def implied_posture(record, *, envelope_establishes=False) -> str:
    """The posture a contribution's premise carries into anything derived from it.

    Section 19. An owner intent the governed envelope does not establish is a
    SPECULATIVE_TEST, and text conceding that relief is needed is
    RELIEF_DEPENDENT - which is more conservative than speculative only in the
    sense that it names a real pathway, so the two are ordered by the ladder and
    not by this function's opinion.

    A QUESTION carries no premise and therefore no posture to inherit.
    """
    classification = record.get("classification")
    text = record.get("text") or ""

    if classification == CLASS_USER_QUESTION:
        return posture.POSTURE_UNSUPPORTED
    if _RELIEF_LANGUAGE.search(text):
        return posture.POSTURE_RELIEF_DEPENDENT
    if classification in (CLASS_OWNER_INTENT, CLASS_USER_HYPOTHESIS):
        if envelope_establishes:
            return posture.POSTURE_AS_OF_RIGHT
        return posture.POSTURE_SPECULATIVE_TEST
    if _TEST_LANGUAGE.search(text):
        return posture.POSTURE_SPECULATIVE_TEST
    if classification == CLASS_PROFESSIONAL_JUDGMENT:
        # A professional's reading is a reading. It is not an entitlement, and
        # the profession the reader belongs to does not change that.
        return posture.POSTURE_SPECULATIVE_TEST
    return posture.POSTURE_SPECULATIVE_TEST


def review(record, document, evidence_facts) -> dict:
    """Compare ONE contribution against the governed result. Never raises.

    Returns the follow-up layer: what its entities bind to, what statutory effect
    it is entitled to, the posture anything derived from it inherits, the
    contradictions found, and the admission decision.

    THE HOST FACTS ARE READ, NEVER WRITTEN. `document` and `evidence_facts` are
    inputs and are not copied back out; a test asserts they are unchanged.
    """
    record = record or {}
    text = record.get("text") or ""

    # ENTITY BINDING, from 64ddd93, over a statement shaped from the
    # contribution. The binder does not care who wrote the sentence - which is
    # the point, and the reason there is no second binder here.
    statement = {"statement_id": "C-%s" % (record.get("text_sha256") or "")[:12],
                 "kind": "GO_INTERPRETS", "text": text}
    bound = entity_binding.bind_statement(
        statement, evidence_facts,
        declared_exceptions=entity_binding.declared_exceptions(document))

    effect = declared_statutory_effect(text)
    stance = implied_posture(record)

    contradictions = []
    for failure in bound["failures"]:
        if failure["failure"] == entity_binding.FAILURE_ROLE_MISMATCH:
            contradictions.append({
                "kind": "ROLE_CONTRADICTION",
                "detail": ("%s appears in the governed result as %s, not as %s"
                           % (failure["value"], failure["host_role"],
                              failure["asserted_role"])),
                "host_role": failure["host_role"],
                "asserted_role": failure["asserted_role"],
                "value": failure["value"],
            })
        elif failure["failure"] == entity_binding.FAILURE_UNBOUNDED_NUMERIC:
            contradictions.append({
                "kind": "UNSUPPORTED_FIGURE",
                "detail": ("%s does not appear in any fact the governed result "
                           "established" % failure["value"]),
                "host_role": None,
                "asserted_role": failure["asserted_role"],
                "value": failure["value"],
            })
        elif failure["failure"] == entity_binding.FAILURE_UNBOUND_EXCEPTION:
            contradictions.append({
                "kind": "UNKNOWN_EXCEPTION",
                "detail": ("%s is not an exception this result declares"
                           % failure["value"]),
                "host_role": None, "asserted_role": "EXCEPTION_ID",
                "value": failure["value"],
            })
    if effect["overreach"]:
        contradictions.append({
            "kind": "EFFECT_OVERREACH",
            "detail": effect["detail"],
            "host_role": None, "asserted_role": effect["asserted_effect"],
            "value": None,
        })

    # SECTION 18. A failure QUARANTINES. There is no confidence to reduce here
    # and deliberately no mechanism to add one.
    if record.get("classification") == CLASS_USER_QUESTION and not bound["failures"]:
        decision = ADMISSION_NOT_APPLICABLE
    elif bound["failures"] or effect["overreach"]:
        decision = ADMISSION_QUARANTINED
    else:
        decision = ADMISSION_ADMITTED

    return {
        "contribution_version": CONTRIBUTION_VERSION,
        "reviewed": True,
        "review_basis": "DETERMINISTIC_COMPARISON",
        "entity_bindings": bound["bindings"],
        "binding_failures": bound["failures"],
        "statutory_effect": effect["statutory_effect"],
        "effect_basis": effect["effect_basis"],
        "effect_overreach": effect["overreach"],
        "effect_detail": effect["detail"],
        "implied_posture": stance,
        "contradictions": contradictions,
        "admission": decision,
        "needs_confirmation": _needs_confirmation(record, contradictions, stance),
    }


def _needs_confirmation(record, contradictions, stance) -> list:
    """What a municipality or an authority would have to confirm. Section 16."""
    items = []
    if stance in (posture.POSTURE_SPECULATIVE_TEST,
                  posture.POSTURE_RELIEF_DEPENDENT):
        items.append(
            "Whether the premise in this contribution is achievable is not "
            "established by the governed result; it would require municipal "
            "confirmation or a planning decision.")
    for contradiction in contradictions:
        if contradiction["kind"] == "ROLE_CONTRADICTION":
            items.append(
                "The figure %s is used here as %s; the governed result "
                "establishes it as %s. Which one governs must be confirmed "
                "against the by-law text."
                % (contradiction["value"], contradiction["asserted_role"],
                   contradiction["host_role"]))
        elif contradiction["kind"] == "UNSUPPORTED_FIGURE":
            items.append(
                "The figure %s is not in the retrieved record and would have to "
                "be sourced before it can be relied on."
                % contradiction["value"])
        elif contradiction["kind"] == "EFFECT_OVERREACH":
            items.append(
                "A permission is asserted without a governing instrument. The "
                "provision that grants it would have to be produced.")
    if record.get("supplied_object"):
        items.append(
            "The supplied object %s has not been verified by ARCHIOSK and its "
            "authority status is unknown."
            % (record["supplied_object"].get("name") or "(unnamed)"))
    return items


def derive_posture(reviews, proposed=None) -> dict:
    """The posture any derived work inherits from a whole set of contributions.

    THE MOST CONSERVATIVE PREMISE GOVERNS. A follow-up standing on two premises
    is no stronger than its weaker one, and taking the maximum rather than the
    minimum is how a qualification gets dropped. Delegates the actual ladder
    comparison to `planning_posture.inherit`, which is the only place that
    comparison is implemented.
    """
    stances = [r.get("implied_posture") for r in reviews or []
               if posture.is_posture(r.get("implied_posture"))]
    if not stances:
        parent = posture.POSTURE_UNSUPPORTED
    else:
        parent = max(stances, key=lambda value: posture.strength_index(value))
    return posture.inherit(parent, proposed)


def layered(document, view, contributions, reviews) -> dict:
    """Section 17. The four layers, returned separately so nothing can flatten them.

    The governed result is passed through UNCHANGED and UNCOPIED-INTO: this
    function adds keys beside it and never writes a key inside it.
    """
    reviews = list(reviews or [])
    return {
        "layers": ("GOVERNED_RESULT", "USER_CONTRIBUTION", "GO_FOLLOW_UP",
                   "ADMISSION_DECISION"),
        "governed_result": {
            "layer": "GOVERNED_RESULT",
            "host_owned": True,
            "immutable_for_interaction": True,
            "view": view,
            "result_status": (document or {}).get("result_status"),
        },
        "contributions": [{"layer": "USER_CONTRIBUTION", "host_owned": False,
                           "record": record}
                          for record in contributions or []],
        "follow_up": [{"layer": "GO_FOLLOW_UP", "host_owned": False,
                       "review": item} for item in reviews],
        "admission": {
            "layer": "ADMISSION_DECISION",
            "host_owned": True,
            "decisions": [item.get("admission") for item in reviews],
            "quarantined": sum(1 for item in reviews
                               if item.get("admission") == ADMISSION_QUARANTINED),
            "admitted": sum(1 for item in reviews
                            if item.get("admission") == ADMISSION_ADMITTED),
            # Section 14: whatever the contribution said, these stay host-owned.
            "host_retains": ("PARCEL_IDENTITY", "AUTHORITY_CURRENTNESS",
                             "STATUTORY_EFFECT", "DETERMINISTIC_FINDINGS",
                             "EXCEPTION_STATE", "CLAIM_STRENGTH",
                             "GOVERNED_RELEASE"),
        },
        "derived_posture": derive_posture(reviews),
    }
