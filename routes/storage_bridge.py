"""
CLAUDE-STORAGE-BRIDGE-03 - the three endpoints a private-storage agent calls.

    POST /api/bridge/manifest   here is what is on the storage
    GET  /api/bridge/pending    is there anything you want?
    POST /api/bridge/deliver    here are the bytes you asked for

ALL THREE ARE CALLED INWARD, BY THE AGENT. ARCHIOSK never calls out - there is
no client anywhere in this path, and services/storage_bridge.py is asserted by
AST to import nothing capable of opening a connection. That is what makes SMB
and port 445 unnecessary: the private network always speaks first, so nothing on
it has to accept a connection from outside.

AUTHENTICATION IS NOT THE SESSION

These are machine endpoints. They carry no cookie and no logged-in user, and
they deliberately do NOT use @login_required - an agent is not a person. The
bearer token resolves to exactly one enrolment naming exactly one project, and
that resolution IS the authorisation: there is no route from a project_id to a
bridge, so an agent cannot express a request for a project it was not enrolled
for.

A DELIBERATELY SEPARATE BLUEPRINT

Not folded into routes/api.py, which is human/session-authenticated and whose
_load_authorized_project_or_404 assumes a User. Mixing a machine credential into
that file would put two different notions of "authorised" in one place, and the
first person to add a route there would have to know which one applied.

WHAT THESE ENDPOINTS CANNOT DO

Nothing here writes a governed Source, creates a project, or persists bytes.
The manifest lands in process-local bridge state and the payload is consumed
once. Wiring this into ingestion is a separate, later change that must go
through the existing Reconcile path rather than becoming a second way to
create Sources.
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from services.external_source import ExternalSourceError
from services.storage_agent_access import (
    authorise_agent, bridge_for_token, note_agent_contact,
)
from services.storage_bridge import BridgeEnrolmentRevoked, ManifestEntry

storage_bridge_bp = Blueprint("storage_bridge", __name__)

# An agent has no reason to send anything larger; a manifest is metadata.
_MAX_MANIFEST_ENTRIES = 20000
_MAX_PAYLOAD_BYTES = 64 * 1024 * 1024


def _presented_token() -> str:
    """Bearer header only.

    Never a query parameter: those land in access logs, proxy logs and browser
    history, and a credential that survives in a log is a credential that leaks
    later. Same reason this codebase's own reset links are single-use.
    """
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):].strip()
    return ""


@storage_bridge_bp.route("/api/bridge/manifest", methods=["POST"])
def receive_manifest():
    """The agent has walked its storage and is telling us what is there."""
    enrolment = authorise_agent(_presented_token())
    payload = request.get_json(silent=True) or {}
    rows = payload.get("entries")
    if not isinstance(rows, list):
        return jsonify(error="invalid_manifest",
                       message="entries must be a list."), 400
    if len(rows) > _MAX_MANIFEST_ENTRIES:
        return jsonify(error="manifest_too_large",
                       message="At most %d entries." % _MAX_MANIFEST_ENTRIES), 413
    try:
        entries = [ManifestEntry.from_dict(row) for row in rows]
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify(error="invalid_manifest", message=str(exc)), 400

    bridge = bridge_for_token(_presented_token())
    digest = bridge.record_manifest(entries)
    note_agent_contact(enrolment)
    current_app.logger.info(
        "Storage agent %s advertised %d entries for %s",
        enrolment.agent_label, len(entries), enrolment.project_id)
    return jsonify(manifest_digest=digest, accepted_entries=len(entries)), 200


@storage_bridge_bp.route("/api/bridge/pending", methods=["GET"])
def pending_requests():
    """The agent's outbound poll. An empty answer is still proof of life."""
    enrolment = authorise_agent(_presented_token())
    bridge = bridge_for_token(_presented_token())
    outstanding = bridge.pending()
    note_agent_contact(enrolment)
    return jsonify(requests=[{"id": r.id, "relative_path": r.relative_path}
                             for r in outstanding]), 200


@storage_bridge_bp.route("/api/bridge/deliver", methods=["POST"])
def deliver_bytes():
    """The agent has come back with the bytes for one request.

    Sent as a raw body with the request id in a header rather than as JSON: a
    drawing is not text, and base64 in a JSON envelope would inflate it by a
    third for no benefit.
    """
    enrolment = authorise_agent(_presented_token())
    request_id = request.headers.get("X-Bridge-Request-Id", "").strip()
    if not request_id:
        return jsonify(error="missing_request_id",
                       message="X-Bridge-Request-Id is required."), 400
    body = request.get_data(cache=False)
    if len(body) > _MAX_PAYLOAD_BYTES:
        return jsonify(error="payload_too_large",
                       message="Payload exceeds the bridge limit."), 413

    bridge = bridge_for_token(_presented_token())
    # Integrity is checked inside deliver(): bytes that do not hash to the
    # manifest's own digest are refused as an ERROR, never as a retryable
    # condition - retrying a wrong payload just fetches it again.
    bridge.deliver(request_id, body)
    note_agent_contact(enrolment)
    return jsonify(accepted=True, relative_path=None, bytes_received=len(body)), 200


@storage_bridge_bp.errorhandler(BridgeEnrolmentRevoked)
def _enrolment_refused(err):
    """401, not 403 and not 503.

    This is the one refusal in the whole bridge that IS about the caller's own
    credential, so it is the one place 401 is honest. The storage-side
    refusals - unreachable, or reachable-and-forbidden - are answered by
    app.py's own 503 handlers, which say something entirely different and are
    aimed at a person looking at a project, not at a machine holding a token.
    """
    current_app.logger.warning("Storage agent refused: %s", err)
    return jsonify(error="enrolment_not_authorised",
                   message="This storage agent is not authorised."), 401


@storage_bridge_bp.errorhandler(ExternalSourceError)
def _bridge_error(err):
    """A protocol fault - a hash mismatch, an unknown request, a path the
    manifest never mentioned. 422: the request was understood and refused on
    its merits, and retrying it unchanged will fail identically."""
    current_app.logger.warning("Storage bridge refused a request: %s", err)
    return jsonify(error="bridge_request_refused", message=str(err)), 422
