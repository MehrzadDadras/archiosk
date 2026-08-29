"""CLAUDE-RBAC-TOKENS-01 — project-scoped roles, discipline scope, and tokens.

WHAT QUESTION THIS ANSWERS, AND WHICH ONE IT DOES NOT

`services/project_access.py`'s `can_access_project` answers *"may this account
OPEN this project at all"*, and its first line is `if is_admin: return True`.
This module answers a different and narrower question — *"may this bearer READ
this drawing"* — and its answer for a platform admin is **no**.

That is the Product Owner's Decision 4, stated explicitly: *"Platform Admins
manage infrastructure/tenants but do NOT implicitly bypass project drawing
confidentiality."* It resolves the either/or that
`governance/specified-unbuilt/tenancy-and-project-authorization.md` §5 recorded
as having "no engineering-only answer", and which is why that whole design sat
unbuilt.

`can_access_project` is deliberately NOT modified. Two questions, two answers;
collapsing them into one function is precisely how an admin bypass gets
reintroduced by someone reasonably assuming there is only one access check.

THREE PROPERTIES WORTH NAMING

1. **Isolation is structural where it can be.** `authorize_token` takes a raw
   token and nothing else — it RESOLVES a project rather than accepting one to
   compare against. The route-level helper `authorize_sheet` does take the
   requested project, because a URL supplies one and it must be checked; but
   the authority itself is never caller-supplied. Same instinct as
   `services/storage_agent_access.py`: *"the ability was removed rather than a
   check added."*

2. **Refusals are not an oracle.** Unknown, expired, revoked, wrong project,
   wrong discipline and unrecognised sheet all raise the same exception with
   the same message. A refusal that varies tells someone holding no valid
   credential which guess was closer, and whether a project exists at all.

3. **Unknown never means allowed.** A sheet mark this module cannot classify
   returns `None` from `discipline_for_sheet` and is REFUSED, not waved
   through. Refusing something legitimate is recoverable; serving something
   confidential is not.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence

# -- Roles -----------------------------------------------------------------
# A closed set. `owner` here is a ROLE (the client/owner stakeholder) and is
# NOT `ProjectWorkspace.owner`, which is a username string identifying who owns
# the project record. The collision is inherited from the domain's own
# vocabulary rather than chosen; it is called out here, and in every docstring
# that touches it, because security code that quietly means two things by one
# word is how real mistakes get made.
ROLE_PLATFORM_ADMIN = "platform_admin"
ROLE_ARCHITECT = "architect"
ROLE_PROJECT_OWNER = "owner"
ROLE_ENGINEER = "engineer"
ROLE_TRADE = "trade"

PROJECT_ROLES = (
    ROLE_PLATFORM_ADMIN,
    ROLE_ARCHITECT,
    ROLE_PROJECT_OWNER,
    ROLE_ENGINEER,
    ROLE_TRADE,
)

# Roles that span the whole project and therefore carry no discipline list.
PROJECT_WIDE_ROLES = (ROLE_ARCHITECT, ROLE_PROJECT_OWNER)

# Roles that MUST name their disciplines at issue time.
DISCIPLINE_SCOPED_ROLES = (ROLE_ENGINEER, ROLE_TRADE)

# Roles that may issue and revoke tokens for their project.
TOKEN_MANAGING_ROLES = (ROLE_ARCHITECT,)

# -- Disciplines -----------------------------------------------------------
# The vocabulary read off 5 Nipigon's own A100 drawing index, not invented
# here: ARCHITECTURAL, STRUCTURAL (named twice, as S1-S10 and RS501-RS510),
# MECHANICAL M1-M5, ELECTRICAL E1-E5, LANDSCAPE L1, CIVIL SP1. There is no
# P-series on that project — plumbing is the TITLE of M1 and M2, inside
# mechanical — so no plumbing discipline is defined here.
DISCIPLINE_ARCHITECTURAL = "architectural"
DISCIPLINE_STRUCTURAL = "structural"
DISCIPLINE_MECHANICAL = "mechanical"
DISCIPLINE_ELECTRICAL = "electrical"
DISCIPLINE_CIVIL = "civil"
DISCIPLINE_LANDSCAPE = "landscape"

DISCIPLINES = (
    DISCIPLINE_ARCHITECTURAL,
    DISCIPLINE_STRUCTURAL,
    DISCIPLINE_MECHANICAL,
    DISCIPLINE_ELECTRICAL,
    DISCIPLINE_CIVIL,
    DISCIPLINE_LANDSCAPE,
)

# Ordered longest-prefix-first: "RS" and "SP" must be tested before the bare
# "S" they both start with, or RS501 classifies as structural by luck and SP1
# classifies as structural by mistake.
_SHEET_PREFIXES: Sequence[tuple[str, str]] = (
    ("RS", DISCIPLINE_STRUCTURAL),
    ("SP", DISCIPLINE_CIVIL),
    ("A", DISCIPLINE_ARCHITECTURAL),
    ("S", DISCIPLINE_STRUCTURAL),
    ("M", DISCIPLINE_MECHANICAL),
    ("E", DISCIPLINE_ELECTRICAL),
    ("L", DISCIPLINE_LANDSCAPE),
)

DEFAULT_TOKEN_TTL_SECONDS = 30 * 24 * 3600   # 30 days

# One message for every refusal. See property 2 above.
_REFUSAL = "This project token is not authorised for that."


class ProjectAccessRefused(Exception):
    """Raised for every refusal, with the same message every time."""


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(moment: datetime) -> datetime:
    """SQLite hands back naive datetimes; comparing one to an aware `now`
    raises TypeError, which would surface as a 500 rather than a refusal."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def discipline_for_sheet(sheet_id: Optional[str]) -> Optional[str]:
    """The discipline a sheet mark belongs to, or None if it cannot be told.

    None is a real answer and callers must treat it as "refuse", never as
    "unclassified, therefore fine". A mark must be a letter prefix followed by
    digits — `ZZ999` has a prefix this module does not know and is None;
    `A204` is architectural.
    """
    if not sheet_id:
        return None
    mark = str(sheet_id).strip().upper()
    if not mark or not mark[0].isalpha():
        return None
    letters = "".join(c for c in mark if c.isalpha())
    digits = mark[len(letters):]
    if not digits.isdigit():
        return None
    for prefix, discipline in _SHEET_PREFIXES:
        if letters == prefix:
            return discipline
    return None


def token_disciplines(token) -> tuple[str, ...]:
    """What this token may read. Empty tuple means nothing."""
    if token.role == ROLE_PLATFORM_ADMIN:
        # Infrastructure and tenants, never drawings. Decision 4.
        return ()
    if token.role in PROJECT_WIDE_ROLES:
        return DISCIPLINES
    raw = (token.disciplines or "").strip()
    if not raw:
        return ()
    return tuple(d for d in (part.strip() for part in raw.split(",")) if d in DISCIPLINES)


def may_read_discipline(token, discipline: Optional[str]) -> bool:
    if discipline is None:
        return False          # unknown never means allowed
    return discipline in token_disciplines(token)


def issue_token(project_id: str, role: str, *, label: str,
                actor: Optional[str] = None,
                disciplines: Optional[Iterable[str]] = None,
                ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
                expires_at: Optional[datetime] = None):
    """Mint a token. Returns `(row, raw_token)`; the raw value is never stored.

    Refuses at ISSUE time rather than resolving at read time:
      - an unknown role,
      - a discipline-scoped role with no disciplines named,
      - a discipline outside the closed vocabulary.
    An invalid grant that only fails when someone tries to use it is a grant
    that looks issued on every listing until the moment it matters.
    """
    from models import ProjectAccessToken, db

    if role not in PROJECT_ROLES:
        raise ProjectAccessRefused(_REFUSAL)
    if not project_id:
        raise ProjectAccessRefused(_REFUSAL)

    named = tuple(d.strip().lower() for d in (disciplines or ()) if str(d).strip())
    if role in DISCIPLINE_SCOPED_ROLES:
        if not named:
            raise ProjectAccessRefused(_REFUSAL)
        if any(d not in DISCIPLINES for d in named):
            raise ProjectAccessRefused(_REFUSAL)
    else:
        # A project-wide or no-drawing role carries no list; storing one would
        # imply a narrowing that token_disciplines() does not honour.
        named = ()

    # An EXPLICIT expiry wins over a relative one. A pass provisioned before a
    # stakeholder's first visit is usually described as a date ("until Jan 21"),
    # not a duration, and converting a date to seconds at issue time and back
    # for display is how an off-by-one day appears in someone's calendar.
    if expires_at is not None:
        deadline = _aware(expires_at)
    else:
        deadline = _now() + timedelta(seconds=ttl_seconds)

    # A pass that is already dead on arrival is a configuration mistake, not a
    # credential. Refusing at issue time surfaces it while the architect is
    # still looking at the form.
    if deadline <= _now():
        raise ProjectAccessRefused(_REFUSAL)

    raw_token = secrets.token_urlsafe(32)
    row = ProjectAccessToken(
        project_id=project_id,
        role=role,
        disciplines=",".join(named) if named else None,
        label=label,
        token_hash=_hash_token(raw_token),
        created_by=actor,
        expires_at=deadline,
    )
    db.session.add(row)
    db.session.commit()
    return row, raw_token


def revoke_token(token_id: int, *, actor: Optional[str] = None) -> None:
    """Stop the credential; keep the record. Idempotent."""
    from models import ProjectAccessToken, db

    row = db.session.get(ProjectAccessToken, token_id)
    if row is None or row.revoked_at is not None:
        return
    row.revoked_at = _now()
    row.revoked_by = actor
    db.session.commit()


def list_active_tokens(project_id: str) -> list:
    """Live tokens for one project — never revoked, never expired.

    Rows carry only a digest, so listing them cannot leak a usable secret.
    """
    from models import ProjectAccessToken

    moment = _now()
    rows = ProjectAccessToken.query.filter_by(
        project_id=project_id, revoked_at=None).order_by(ProjectAccessToken.id).all()
    return [r for r in rows if _aware(r.expires_at) >= moment]


def authorize_token(raw_token: Optional[str], *, now: Optional[datetime] = None):
    """Resolve a presented token to its row, or refuse.

    Takes NO project id. The authority is resolved FROM the credential; there
    is no parameter here through which a caller could ask about a project the
    token was not issued for.
    """
    from models import ProjectAccessToken

    if not raw_token:
        raise ProjectAccessRefused(_REFUSAL)
    moment = now or _now()
    row = ProjectAccessToken.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if row is None or row.revoked_at is not None:
        raise ProjectAccessRefused(_REFUSAL)
    if moment > _aware(row.expires_at):
        raise ProjectAccessRefused(_REFUSAL)
    return row


def authorize_sheet(raw_token: Optional[str], project_id: str, sheet_id: str, *,
                    now: Optional[datetime] = None):
    """The one decision the asset route calls. Returns the token, or refuses.

    The requested project IS compared here, because a URL supplies one and an
    unchecked one is a cross-project read. Every refusal below is
    indistinguishable from every other.
    """
    token = authorize_token(raw_token, now=now)
    if token.project_id != project_id:
        raise ProjectAccessRefused(_REFUSAL)
    if not may_read_discipline(token, discipline_for_sheet(sheet_id)):
        raise ProjectAccessRefused(_REFUSAL)
    return token


def note_token_use(token, *, now: Optional[datetime] = None) -> None:
    """Record that a live credential was used. Never fails a request."""
    from models import db

    try:
        token.last_used_at = now or _now()
        db.session.commit()
    except Exception:                      # pragma: no cover - telemetry only
        db.session.rollback()


def scope_ai_context(token, sheets: Iterable[dict]) -> list:
    """Drop everything the bearer may not read, before a prompt is built.

    This exists because an authorization boundary that holds over HTTP and
    leaks through a model is not a boundary. A trade contractor scoped to
    structural must not be able to ask the assistant what is on the
    architectural sheets and be answered from them.

    Pure and side-effect free: it filters a list of `{"sheet_id": ...}` dicts
    and knows nothing about prompts, so it can be unit-tested directly and
    reused by any caller that assembles context.
    """
    allowed = set(token_disciplines(token))
    if not allowed:
        return []
    kept = []
    for sheet in sheets or ():
        discipline = discipline_for_sheet(sheet.get("sheet_id"))
        if discipline is not None and discipline in allowed:
            kept.append(sheet)
    return kept


# ===========================================================================
# CLAUDE-RBAC-TOKENS-02 — when GO cannot answer
# ===========================================================================

# The exact words, in one place. Product Owner specified them verbatim, and a
# message duplicated across a template and a script drifts the first time one
# is edited. Both the route and any UI read this constant.
OUT_OF_LEAGUE_MESSAGE = "Sorry, this is out of my league. Help is underway."

# Friction signals a client may report. A closed set: an open one would let a
# caller write arbitrary text into an operator-facing queue.
FRICTION_RAGE_TAP = "rage_tap"
FRICTION_DEAD_CALLOUT = "dead_callout"
FRICTION_ERRATIC_PAN = "erratic_pan"
FRICTION_UNRESOLVED_QUERY = "unresolved_query"

FRICTION_SIGNALS = (
    FRICTION_RAGE_TAP,
    FRICTION_DEAD_CALLOUT,
    FRICTION_ERRATIC_PAN,
    FRICTION_UNRESOLVED_QUERY,
)

# One bearer cannot fill the architect's queue. A frustrated person taps a lot
# - that is the whole premise of rage-tap detection - so the cap is not a
# nicety, it is what stops the detector becoming the flood.
MAX_OPEN_ESCALATIONS_PER_TOKEN = 5

# Long enough for a real question with context; short enough that the queue
# cannot be used as storage.
MAX_QUERY_CHARS = 2000


def record_escalation(raw_token: Optional[str], *, query_text: str,
                      sheet_id: Optional[str] = None,
                      view_box: Optional[str] = None,
                      friction_signal: Optional[str] = None,
                      now: Optional[datetime] = None):
    """File one unanswered question against the token's OWN project.

    Every authority fact is copied from the credential, never from the caller:
    the project and the asking role come off the token row. There is no
    parameter here through which someone could file an escalation into another
    project, or one that claims a role they do not hold.

    The sheet, if named, must be one this bearer may actually read. A trade
    contractor asking about an architectural sheet they cannot open would put
    that sheet's identity into a queue - and a sheet id is itself information.
    """
    from models import ArchitectEscalation, db

    token = authorize_token(raw_token, now=now)

    text = (query_text or "").strip()
    if not text:
        raise ProjectAccessRefused(_REFUSAL)
    if len(text) > MAX_QUERY_CHARS:
        raise ProjectAccessRefused(_REFUSAL)

    if friction_signal is not None and friction_signal not in FRICTION_SIGNALS:
        raise ProjectAccessRefused(_REFUSAL)

    if sheet_id:
        if not may_read_discipline(token, discipline_for_sheet(sheet_id)):
            raise ProjectAccessRefused(_REFUSAL)

    open_count = ArchitectEscalation.query.filter_by(
        token_id=token.id, resolved_at=None).count()
    if open_count >= MAX_OPEN_ESCALATIONS_PER_TOKEN:
        raise ProjectAccessRefused(_REFUSAL)

    row = ArchitectEscalation(
        project_id=token.project_id,          # from the token, never the caller
        token_id=token.id,
        asked_by_role=token.role,             # likewise
        sheet_id=sheet_id or None,
        view_box=(view_box or None),
        query_text=text,                      # verbatim, never rewritten
        friction_signal=friction_signal,
    )
    db.session.add(row)
    db.session.commit()
    return row


def list_escalations(project_id: str, *, include_resolved: bool = False) -> list:
    """The architect's queue for one project, oldest first."""
    from models import ArchitectEscalation

    query = ArchitectEscalation.query.filter_by(project_id=project_id)
    if not include_resolved:
        query = query.filter_by(resolved_at=None)
    return query.order_by(ArchitectEscalation.id).all()


def resolve_escalation(escalation_id: int, *, actor: Optional[str] = None) -> None:
    """Mark one answered. The row stays: a queue that forgets what was asked
    cannot show whether anyone was ever answered."""
    from models import ArchitectEscalation, db

    row = db.session.get(ArchitectEscalation, escalation_id)
    if row is None or row.resolved_at is not None:
        return
    row.resolved_at = _now()
    row.resolved_by = actor
    db.session.commit()


def suggest_for_friction(signal: str, context: Optional[dict] = None) -> Optional[dict]:
    """What to offer a person who is visibly stuck. DETERMINISTIC, not a model.

    The Product Owner's own example — "suggesting the referenced detail or
    sheet" — needs no inference: a callout that reads `1/A801` already names
    its target, and the page already knows which sheet it is on. So this reads
    what is there and offers it.

    That is deliberate rather than a shortcut. An LLM call here would be a new
    outbound AI path on a NOISY trigger (three taps), it could invent a sheet
    that does not exist, and it would need the `ACTION_EXTERNAL_AI_REQUEST`
    gate this function does not touch. A suggestion that can only ever name a
    target already present on the page cannot fabricate one.

    Returns None when there is nothing honest to offer — an unhelpful
    suggestion is worse than silence, because it costs a tap to dismiss.
    """
    if signal not in FRICTION_SIGNALS:
        return None
    facts = context or {}
    target = (facts.get("callout_target") or "").strip()

    if signal == FRICTION_DEAD_CALLOUT and target:
        return {
            "kind": "open_sheet",
            "sheet_id": target,
            "message": f"Open {target}?",
        }
    if signal == FRICTION_RAGE_TAP and target:
        return {
            "kind": "open_sheet",
            "sheet_id": target,
            "message": f"Looking for {target}?",
        }
    if signal == FRICTION_ERRATIC_PAN:
        return {
            "kind": "reset_view",
            "sheet_id": None,
            "message": "Fit the sheet to the pane?",
        }
    # Rage-tapping something with no target, or an unresolved query: there is
    # no deterministic suggestion to make. Escalation is the honest path.
    return None


# ===========================================================================
# CLAUDE-RBAC-TOKENS-03 — the bidding marketplace, scaffolded and switched off
# ===========================================================================

# Which roles the marketplace is FOR, once it exists. Recorded now so the
# eventual audience is a decision on the record rather than whatever the first
# template happens to check.
BIDDING_PORTAL_ROLES = (ROLE_TRADE, ROLE_PROJECT_OWNER)


def bidding_portal_visible(token, *, enabled: bool = False) -> bool:
    """Whether the bidding component may be rendered at all.

    TWO conditions, and the flag is checked FIRST and independently. While
    `ENABLE_BIDDING_PORTAL` is False this returns False for every token, every
    role, every project — there is no role, and no combination of arguments,
    that reaches True.

    Being off means the markup is never emitted. That is deliberately stronger
    than rendering it hidden: an element that exists in the DOM is readable in
    devtools, survives any CSS being overridden, and ships to everyone. A
    component nobody can see is not the same as a component that is not there.

    `enabled` is passed in rather than read from `current_app` so this stays a
    pure function that can be tested both ways without faking an app context —
    and so a caller cannot accidentally consult a different config than the one
    the route already resolved.
    """
    if not enabled:
        return False
    if token is None:
        return False
    return token.role in BIDDING_PORTAL_ROLES


# ===========================================================================
# CLAUDE-RBAC-TOKENS-04 — what the architect's management table shows
# ===========================================================================

STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"
STATUS_REVOKED = "revoked"


def token_status(token, *, now: Optional[datetime] = None) -> str:
    """One of three words, in priority order.

    REVOKED beats EXPIRED deliberately. A pass that was withdrawn and then also
    ran out should read as withdrawn: "expired" would suggest it simply lapsed
    and could be renewed, when somebody actually took it away.
    """
    moment = now or _now()
    if token.revoked_at is not None:
        return STATUS_REVOKED
    if moment > _aware(token.expires_at):
        return STATUS_EXPIRED
    return STATUS_ACTIVE


def list_all_tokens(project_id: str, *, now: Optional[datetime] = None) -> list:
    """Every pass ever issued for one project, newest first, with its status.

    Includes revoked and expired ones on purpose: the management table exists
    to answer "who has access", and a table that quietly drops withdrawn passes
    cannot answer "who used to". Rows carry only a digest, so listing them can
    never leak a usable secret.
    """
    from models import ProjectAccessToken

    moment = now or _now()
    rows = ProjectAccessToken.query.filter_by(project_id=project_id).order_by(
        ProjectAccessToken.id.desc()).all()
    return [{"token": row, "status": token_status(row, now=moment)} for row in rows]
