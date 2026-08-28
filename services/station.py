"""
SPIKE / CLAUDE-STATION-01 - the project is mounted; people join it.

THE PRINCIPLE, AND WHY IT IS NOT ABOUT CHROME

A Site Glass Box is a physical station for one job. Once mounted, the project IS
the application: no switcher, no breadcrumb, no "which project are you in?".

Removing the dropdown would not achieve that. Today project identity lives ONLY
in the URL - 97 routes in routes/workspace.py take <project_id>, there is no
session-level binding, and the project name in the topbar IS the switcher
(menu.context.switch-project). The URL is the mechanism, so hiding the affordance
changes nothing; typing a different path still switches project.

So a mount has to exist somewhere identity can actually live. It cannot be the
Flask session, because a session is per-browser and a table is one device several
people join - Person A's phone and the Glass Box are different sessions in the
same mounted context. The mount therefore belongs to the STATION.

WE ALREADY BUILT THIS SHAPE, FOR MACHINES

services/storage_agent_access.py's bridge_for_token has no project_id parameter:
a token resolves to exactly one enrolment naming exactly one project, so asking
for another is inexpressible rather than refused. That is "the project is
mounted", implemented for agents. This is the same move for people.

TWO FIELDS, DELIBERATELY SEPARATE

The one place this DEVIATES from the agent template. StorageAgentEnrolment binds
a credential to one project permanently - revoke and re-enrol to change it. A
Glass Box is a physical object that serves a different job next month, so:

    token_hash          IMMUTABLE - this station's identity, forever
    mounted_project_id  MUTABLE   - changed only by an explicit privileged mount

Collapsing them would make re-pointing a table destroy its identity, its history,
and every companion pairing with it.

JOINING IS NOT AUTHORISATION

This is the security boundary, and it is the one that would be easy to get wrong.
A phone joining a station learns WHICH project the surface is showing. It does
NOT thereby gain access to it. can_access_project remains the strict, failing-
closed gatekeeper for every participant, exactly as it is everywhere else - so
walking up to a Glass Box with any valid login cannot become a route into a
project you were never granted.

Structurally: join_station() returns the mounted project id and nothing else. It
performs no access check because it grants no access, and it never loads project
data. The caller must still go through the ordinary authorisation path, and a
test asserts this module never imports or calls it - because a module that
sometimes checks access is worse than one that never does.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

DEFAULT_STATION_TTL_SECONDS = 365 * 24 * 3600


class StationError(Exception):
    """The station cannot be used, and the caller must not pretend it can."""


class StationNotAuthorised(StationError):
    """Unknown, revoked or expired station credential.

    All three are reported identically, for the same reason the storage bridge
    does: distinguishing them tells someone holding no valid credential whether a
    station exists at all.
    """


class StationNotMounted(StationError):
    """A real station with no project mounted.

    Its own type rather than an error string, because the ANSWER differs: an
    unauthorised station needs a credential, an unmounted one needs an
    administrator to mount a job. A surface showing "not authorised" when the
    truth is "nothing mounted yet" sends someone to the wrong person.
    """


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enrol_station(label: str, *, actor: Optional[str] = None,
                  ttl_seconds: int = DEFAULT_STATION_TTL_SECONDS) -> tuple[object, str]:
    """Provision a station. Raw token returned ONCE and never stored.

    Enrolled with NO project mounted - a new Glass Box is a piece of hardware,
    not a job. Mounting is a separate, explicit, privileged act.
    """
    from models import StationEnrolment, db

    raw_token = secrets.token_urlsafe(32)
    station = StationEnrolment(
        label=label,
        token_hash=_hash_token(raw_token),
        mounted_project_id=None,
        created_at=_now(),
        created_by=actor,
        expires_at=_now() + timedelta(seconds=ttl_seconds),
    )
    db.session.add(station)
    db.session.commit()
    return station, raw_token


def authorise_station(raw_token: str, *, now: Optional[datetime] = None):
    """Resolve a presented station token, or refuse."""
    from models import StationEnrolment

    moment = now or _now()
    station = StationEnrolment.query.filter_by(
        token_hash=_hash_token(raw_token)).first()
    refusal = StationNotAuthorised("This station is not authorised.")
    if station is None or station.revoked_at is not None:
        raise refusal
    expires_at = station.expires_at
    if expires_at.tzinfo is None:            # SQLite returns naive datetimes
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if moment > expires_at:
        raise refusal
    return station


def mount_project(raw_token: str, project_id: str, *, actor: str,
                  now: Optional[datetime] = None):
    """The privileged administrative act. Identity is untouched.

    Deliberately takes a project_id - mounting is the ONE operation where naming
    a project is the whole point. Every other call in this module derives the
    project from the mount instead, which is what makes switching impossible
    from the working surface rather than merely hidden.
    """
    from models import db

    station = authorise_station(raw_token, now=now)
    previous = station.mounted_project_id
    station.mounted_project_id = project_id
    station.mounted_at = now or _now()
    station.mounted_by = actor
    db.session.commit()
    return {"station": station, "previous_project_id": previous,
            "mounted_project_id": project_id}


def unmount(raw_token: str, *, actor: str, now: Optional[datetime] = None):
    """Release the job without destroying the station.

    The row stays, the credential stays valid, the label and history stay. Only
    the mount clears - and any presence state with it, so a packed-up table
    cannot keep broadcasting a coordinate into a project it no longer holds.
    """
    from models import db

    station = authorise_station(raw_token, now=now)
    previous = station.mounted_project_id
    station.mounted_project_id = None
    station.mounted_at = None
    station.mounted_by = actor
    db.session.commit()
    return previous


def mounted_project_for(raw_token: str, *, now: Optional[datetime] = None) -> str:
    """What this station is showing. There is no companion taking a project_id.

    That absence is the mount: a station cannot express a request for a project
    other than the one mounted, in the same way an enrolled storage agent cannot.
    """
    station = authorise_station(raw_token, now=now)
    if not station.mounted_project_id:
        raise StationNotMounted(
            "Station %r has no project mounted." % station.label)
    return station.mounted_project_id


def join_station(raw_token: str, *, now: Optional[datetime] = None) -> dict:
    """A companion device binds to the station's context.

    Returns WHICH project the surface is showing, and nothing else. It grants
    nothing: the joining person must still pass can_access_project on every
    subsequent request, exactly as they would had they typed the URL. This
    function deliberately performs no access check, because performing one here
    would imply it had granted something.
    """
    station = authorise_station(raw_token, now=now)
    if not station.mounted_project_id:
        raise StationNotMounted(
            "Station %r has no project mounted." % station.label)
    return {
        "station_id": station.id,
        "station_label": station.label,
        "mounted_project_id": station.mounted_project_id,
        # Stated in the payload itself so a client author cannot mistake this
        # for an entitlement.
        "grants_access": False,
    }
