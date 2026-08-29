"""CLAUDE-TRIAL-SAFE-LANDING-01 — running out of fuel without crashing.

THE PROMISE, AND WHAT MAKES IT TRUE

    "You have run out of fuel, but the system allows you to get home safely.
     Contact admin for further help."

That second clause is a commitment, not decoration. It is only honest if
everything a person can do WITHOUT a model keeps working when the allowance is
gone: opening sheets, zooming, panning, the split pane, sheet navigation,
escalating to a human. So the meter counts exactly one thing — an OUTBOUND LLM
CALL — and touches nothing else. `services/project_assets.py`,
`services/project_entry.py` and the viewer never import this module, and a test
asserts that rather than trusting it.

THREE STATES, AND THE MIDDLE ONE IS THE INTERESTING ONE

    ALLOWED    room left; the call proceeds, nothing is appended.
    FINAL      this call is the last one. It PROCEEDS AND COMPLETES IN FULL,
               and the message is appended to the finished answer.
    EXHAUSTED  no allowance remains. No model is called AT ALL - the same
               message is returned directly.

FINAL exists because cutting somebody off mid-thought is the failure this
whole feature is designed to avoid. The query that crosses the line is
answered properly first; the warning arrives attached to a complete response,
not instead of one.

WHAT THIS MODULE DELIBERATELY DOES NOT DO

It does not store an API key. The BYOK trigger below is a payload flag saying
"offer this", and the key seam already exists — `services/llm_gateway.py`'s
`call_llm_json(api_key=...)` takes one per call. Persisting a customer's
provider credential is a separate security surface (encryption at rest,
scoping, rotation, revocation, blast radius when it leaks) and is not being
smuggled in behind a quota feature.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

# The exact words. One definition, so a template and a JSON payload cannot
# drift into saying two different things.
SAFE_LANDING_MESSAGE = (
    "You have run out of fuel, but the system allows you to get home safely. "
    "Contact admin for further help."
)

STATE_ALLOWED = "allowed"
STATE_FINAL = "final"
STATE_EXHAUSTED = "exhausted"

TRIGGER_BYOK = "byok"
TRIGGER_CONTACT_ADMIN = "contact_admin"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row(project_id: str, *, create: bool = True):
    from models import TrialAllowance, db

    row = TrialAllowance.query.filter_by(project_id=project_id).first()
    if row is None and create:
        row = TrialAllowance(project_id=project_id, used_count=0)
        db.session.add(row)
        db.session.commit()
    return row


def usage(project_id: str, *, limit: int) -> dict:
    """What is left, without consuming anything. Safe to call for display."""
    row = _row(project_id, create=False)
    used = row.used_count if row else 0
    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "exhausted": used >= limit,
    }


# BYOK. A project that brings its own provider credential is not on the trial
# meter at all: the cap exists to bound OUR cost, and their key is their cost.
#
# What this module does and does not do, stated because the difference matters:
# it reads whether a key is PRESENT and returns a bypass. It does not accept,
# decrypt, validate, transmit or store one. `services/llm_gateway.py` already
# takes `api_key=` per call, which is the seam a key would travel through.
# Building the store itself - encryption at rest, rotation, revocation, and the
# blast radius when a customer's provider credential leaks - is its own piece of
# work and is deliberately not smuggled in behind a quota feature.
BYOK_ATTRIBUTE = "byok_api_key_encrypted"


def byok_key_present(workspace) -> bool:
    """Whether this project carries its own encrypted provider key.

    Reads only for PRESENCE. The value is never returned, logged or compared,
    so nothing here can leak it even by accident.
    """
    if workspace is None:
        return False
    value = getattr(workspace, BYOK_ATTRIBUTE, None)
    return bool(value)


def consume_query(project_id: str, *, limit: int, byok: bool = False) -> str:
    """Claim one model-backed query and say what the caller may do.

    Returns STATE_ALLOWED, STATE_FINAL or STATE_EXHAUSTED.

    EXHAUSTED consumes nothing. Counting refused queries would let a caller
    push the number arbitrarily high against a project that is already stopped,
    which corrupts the only record of how much a trial actually used.
    """
    from models import db

    # Bring your own key, pay your own way: the meter is not consulted and not
    # advanced. Recorded as the FIRST check so it cannot be reached around by
    # any later condition.
    if byok:
        return STATE_ALLOWED

    if limit <= 0:
        return STATE_EXHAUSTED

    row = _row(project_id)
    if row.used_count >= limit:
        return STATE_EXHAUSTED

    row.used_count += 1
    if row.first_used_at is None:
        row.first_used_at = _now()
    if row.used_count >= limit:
        row.exhausted_at = _now()
    db.session.commit()

    return STATE_FINAL if row.used_count >= limit else STATE_ALLOWED


def admin_mailto(admin_email: str, *, project_id: str, project_name: Optional[str] = None,
                 organization: Optional[str] = None,
                 now: Optional[datetime] = None) -> str:
    """A pre-addressed message to the administrator.

    Carries the project name, its id and today's date, because an
    administrator receiving "I ran out" with no context has to go and ask.

    Carries NOTHING ELSE. No access token, no query text, no sheet the person
    was looking at: a mailto opens in the sender's own mail client and its
    contents land in their sent folder, their drafts, and any client-side
    sync — none of which is a place for a credential or for someone's
    question.
    """
    stamp = (now or _now()).strftime("%Y-%m-%d %H:%M UTC")
    label = project_name or project_id
    # Subject fixed by the Product Owner, and it is the PROJECT ID rather than
    # the display name on purpose: an administrator triaging these needs the
    # thing they can look up, and an id survives a project being renamed.
    subject = f"Refuel AI Access - {project_id}"
    body = (
        "Hello,\n\n"
        f"The trial allowance for this project has been used up.\n\n"
        f"Project: {label}\n"
        f"Project ID: {project_id}\n"
        f"Organization: {organization or 'not recorded'}\n"
        f"Timestamp: {stamp}\n\n"
        "Could you advise on continuing?\n"
    )
    return (f"mailto:{quote(admin_email)}"
            f"?subject={quote(subject)}&body={quote(body)}")


def safe_landing_payload(*, project_id: str, project_name: Optional[str],
                         admin_email: str, organization: Optional[str] = None,
                         now: Optional[datetime] = None) -> dict:
    """The message and its two action triggers, in one shape.

    Both triggers are DECLARATIONS the client renders, not behaviour performed
    here. `byok` says "offer the key entry"; nothing in this module accepts,
    validates or stores a key.
    """
    return {
        "message": SAFE_LANDING_MESSAGE,
        "triggers": [
            {
                "kind": TRIGGER_BYOK,
                "label": "Use my own API key",
                # Declared so a client cannot invent its own endpoint, and so
                # the absence of a storage endpoint is visible here.
                "action": "open_byok_modal",
            },
            {
                "kind": TRIGGER_CONTACT_ADMIN,
                "label": "Contact admin",
                "action": "open_mailto",
                "href": admin_mailto(admin_email, project_id=project_id,
                                     project_name=project_name,
                                     organization=organization, now=now),
            },
        ],
    }


def apply_to_answer(answer_text: str, state: str, payload: dict) -> dict:
    """Attach the safe landing to a completed answer, or return it alone.

    On FINAL the answer is delivered IN FULL and the message is appended — the
    person gets the thing they asked for, and then learns it was the last one.
    On EXHAUSTED there is no answer to attach to, because no model was called.
    """
    if state == STATE_ALLOWED:
        return {"answer": answer_text, "safe_landing": None, "model_called": True}
    if state == STATE_FINAL:
        return {
            "answer": answer_text,
            "safe_landing": payload,
            "model_called": True,
        }
    return {"answer": None, "safe_landing": payload, "model_called": False}
