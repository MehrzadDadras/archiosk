"""
SPIKE / CLAUDE-STATION-POLL-01 - the transport, deliberately the dullest part.

    GET  /api/station/join            a companion asks what this surface shows
    POST /api/station/viewport        the station says where it is looking
    GET  /api/station/viewport?since= a follower asks if that has moved
    POST /api/station/focus           a companion points at something
    GET  /api/station/focus?since=    what is everyone pointing at

VIEWPORT AUTHORITY IS ASYMMETRIC, AND THAT IS THE PRODUCT DECISION

The station owns its own camera. A companion cannot pan or zoom it remotely,
because people are physically standing around that surface and having the view
wrenched away by a remote tap would make the shared context unusable. Companions
publish DISTURBANCES instead - a highlight, a question, a GO card - which appear
in place over whatever the table is already showing.

Enforced structurally: publish_focus has no path to the viewport document, and
publish_viewport requires the station credential rather than a person.

SHORT-POLLING, NOT SSE, AND THIS IS A MEASURED CHOICE

Measured on the live host: 15 gunicorn workers x 4 gthread threads = 60 request
slots, and gthread holds a thread for a request's LIFETIME. Sixty concurrent SSE
streams would exhaust the pool and the whole site would stop serving anything.
nginx also carries no proxy_buffering directive, so it buffers proxied responses
by default and SSE frames would never leave the buffer at all.

Each request here instead reads one small file and returns in single-digit
milliseconds, so a poller occupies a slot for ~0.005s per 0.5s of following -
roughly a 1% duty cycle against SSE's 100%. At ~500ms, viewport following is
imperceptible for the thing it is actually for: a phone tracking the table.

The bus does not know any of this. read_since(station, revision) is the whole
contract, so swapping in SSE later changes this file and nothing else.

WHERE AUTHORISATION HAPPENS, AND WHY IT IS HERE RATHER THAN THERE

services/station.py cannot grant project access - it never imports
can_access_project, and a test asserts that absence. That is deliberate: a module
which SOMETIMES grants access is worse than one which structurally cannot.

So the composition happens HERE, explicitly, in the open:

    join_station(token)      -> WHICH project this surface shows (grants nothing)
    can_access_project(...)  -> whether THIS PERSON may see it (the gatekeeper)

Both must pass. Walking up to a Glass Box with any valid login gets you the
station's project id and then a 404 unless you were already granted access -
the same 404 the ordinary URL would have given, because joining a station is not
a way in.

404 rather than 403 throughout, matching _load_workspace_or_404's own established
convention: do not confirm a project's existence to someone who may not see it.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from services.presence_bus import PresenceBus
from services.station import (
    StationError, StationNotAuthorised, StationNotMounted, authorise_station,
    join_station, mounted_project_for,
)

station_bp = Blueprint("station", __name__)

# A viewport is a coordinate, not a document.
_MAX_VIEWPORT_BYTES = 4096

# What a follower should wait before asking again. Advertised in the response so
# the cadence is server-controlled: if this ever needs to back off under load,
# clients follow without shipping anything.
POLL_INTERVAL_MS = 500


def _presented_station_token() -> str:
    """Bearer header only - never a query parameter.

    Query strings land in access logs, proxy logs and browser history, and a
    credential that survives in a log is a credential that leaks later.
    """
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):].strip()
    return ""


def _viewer_may_see(project_id: str) -> bool:
    """The gatekeeper, unchanged and failing closed.

    Uses the same centralized decision every other blueprint's loader wraps, so
    a station companion is authorised by exactly the rule that governs the
    ordinary URL - not a parallel one that could drift more permissive.
    """
    from flask import current_app

    from services.case_workspace import CaseWorkspaceStore
    from services.project_access import can_access_project

    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    workspace = store.get(project_id)
    if workspace is None:
        return False
    return can_access_project(workspace, session.get("username"),
                              (session.get("role") == "admin"))


@station_bp.route("/api/station/join", methods=["GET"])
def join():
    """A companion binds to the station's context.

    Two independent checks, in this order: the station credential says which
    project the surface shows, then the PERSON's own access decides whether they
    may have it. Failing the second returns 404, not 403 - the ordinary
    convention for not confirming a project to someone who may not see it.
    """
    project_id = mounted_project_for(_presented_station_token())
    if not _viewer_may_see(project_id):
        return jsonify(error="not_found",
                       message="No such project, or you do not have access."), 404
    payload = join_station(_presented_station_token())
    payload["poll_interval_ms"] = POLL_INTERVAL_MS
    return jsonify(payload), 200


@station_bp.route("/api/station/viewport", methods=["POST"])
def publish_viewport():
    """The station publishes where it is looking. Station credential only.

    A companion cannot publish: following is a one-way relationship in this
    iteration, and giving every joined phone the ability to move the table would
    be a different product decision than the one made.
    """
    from flask import current_app

    station = authorise_station(_presented_station_token())
    project_id = mounted_project_for(_presented_station_token())
    body = request.get_json(silent=True) or {}
    viewport = body.get("viewport")
    if not isinstance(viewport, dict):
        return jsonify(error="invalid_viewport",
                       message="viewport must be an object."), 400
    if len(str(viewport)) > _MAX_VIEWPORT_BYTES:
        return jsonify(error="viewport_too_large",
                       message="A viewport is a coordinate, not a document."), 413

    bus = PresenceBus(current_app.config["REGISTRY_STORE_PATH"])
    record = bus.publish(str(station.id), viewport, published_by=station.label)
    return jsonify(revision=record["revision"], project_id=project_id), 200


@station_bp.route("/api/station/viewport", methods=["GET"])
def poll_viewport():
    """Has the table moved since revision N?

    204 when it has not, which is the common case and the reason polling is
    cheap: no body, no serialisation, one small file read. The client keeps its
    current view and asks again.
    """
    from flask import current_app

    station = authorise_station(_presented_station_token())
    project_id = mounted_project_for(_presented_station_token())
    if not _viewer_may_see(project_id):
        return jsonify(error="not_found",
                       message="No such project, or you do not have access."), 404

    try:
        since = int(request.args.get("since", 0))
    except (TypeError, ValueError):
        since = 0

    bus = PresenceBus(current_app.config["REGISTRY_STORE_PATH"])
    record = bus.read_since(str(station.id), since)
    if record is None:
        response = jsonify()
        response.status_code = 204
        response.headers["X-Poll-Interval-Ms"] = str(POLL_INTERVAL_MS)
        return response
    return jsonify(revision=record["revision"], viewport=record["viewport"],
                   published_by=record["published_by"],
                   poll_interval_ms=POLL_INTERVAL_MS), 200


@station_bp.route("/api/station/focus", methods=["POST"])
def publish_focus():
    """A companion points at something WITHOUT moving the table.

    The asymmetry, enforced here rather than described: this endpoint writes a
    disturbance and has no path to the viewport at all. A companion cannot
    wrench the camera away from the people physically standing at the table -
    which is the entire reason a shared physical surface is worth having.

    Unlike the station endpoints, this one requires a PERSON: a disturbance is
    attributed, and can_access_project decides whether they may be in this
    project at all.
    """
    from flask import current_app

    station = authorise_station(_presented_station_token())
    project_id = mounted_project_for(_presented_station_token())
    author = session.get("username")
    if not author or not _viewer_may_see(project_id):
        return jsonify(error="not_found",
                       message="No such project, or you do not have access."), 404

    body = request.get_json(silent=True) or {}
    focus = body.get("focus")
    if not isinstance(focus, dict):
        return jsonify(error="invalid_focus",
                       message="focus must be an object."), 400
    if len(str(focus)) > _MAX_VIEWPORT_BYTES:
        return jsonify(error="focus_too_large",
                       message="A disturbance is a pointer, not a document."), 413

    bus = PresenceBus(current_app.config["REGISTRY_STORE_PATH"])
    record = bus.publish_focus(str(station.id), author, focus)
    return jsonify(author=record["author"], published_at=record["published_at"]), 200


@station_bp.route("/api/station/focus", methods=["GET"])
def poll_focus():
    """What is everyone pointing at, newer than `since`.

    A SET, not a sequence: the station renders who is pointing where right now.
    One entry per author by construction, so this stays bounded by the number of
    people at the table rather than by how long the meeting has run.
    """
    from flask import current_app

    station = authorise_station(_presented_station_token())
    project_id = mounted_project_for(_presented_station_token())
    if not _viewer_may_see(project_id):
        return jsonify(error="not_found",
                       message="No such project, or you do not have access."), 404
    try:
        since = float(request.args.get("since", 0))
    except (TypeError, ValueError):
        since = 0.0

    bus = PresenceBus(current_app.config["REGISTRY_STORE_PATH"])
    disturbances = bus.read_focus(str(station.id), since=since)
    if not disturbances:
        response = jsonify()
        response.status_code = 204
        response.headers["X-Poll-Interval-Ms"] = str(POLL_INTERVAL_MS)
        return response
    return jsonify(disturbances=disturbances,
                   poll_interval_ms=POLL_INTERVAL_MS), 200


@station_bp.errorhandler(StationNotAuthorised)
def _station_refused(err):
    """401 - the one refusal genuinely about the caller's own credential."""
    return jsonify(error="station_not_authorised",
                   message="This station is not authorised."), 401


@station_bp.errorhandler(StationNotMounted)
def _station_unmounted(err):
    """409, not 401 and not 404.

    A real station with no job mounted is neither an authorisation failure nor a
    missing thing - it is a surface waiting for an administrator. Answering 401
    would send someone to fetch a new credential they do not need.
    """
    return jsonify(error="station_not_mounted",
                   message="This station has no project mounted."), 409


@station_bp.errorhandler(StationError)
def _station_error(err):
    return jsonify(error="station_error", message=str(err)), 422
