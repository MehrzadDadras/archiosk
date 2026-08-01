"""
HTML pages: marketing home, upload form, and the Agility Engine dashboard.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from services.auth import admin_required, check_credentials, is_admin, is_authenticated, log_in, log_out, login_required
from services.rate_limit import limiter
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import OPERATING_ENVIRONMENT_LABELS
from services.governance import GovernanceError
from services.ingestion import UploadError, get_governance_log, get_registry, ingest_upload
from services.password_reset import (
    complete_password_reset, get_valid_reset_token, is_dev_fallback_active, request_password_reset,
)
from services.requirements_registry import RequirementsRegistry

portal_bp = Blueprint('portal', __name__)


def _safe_workspace(store: CaseWorkspaceStore, project_id: str):
    """
    Best-effort workspace load for DISPLAY purposes only (project summary
    cards, sidebar names) - never used for anything that writes or governs.
    A workspace file that predates the current schema must not crash an
    entire listing page; _project_summary already tolerates workspace=None
    everywhere, so degrading to "no display_title available yet" for that
    one project is the honest, safe fallback.
    """
    try:
        return store.get(project_id)
    except TypeError:
        return None


def _accessible_documents(registry, store, include_removed: bool = False):
    """
    CLAUDE-P32: every project-LISTING route in this file (index's
    recent-projects, projects_list, global_search) must filter to only
    the accessible set, not merely block direct navigation into an
    unauthorized project -- otherwise a project's filename/metadata
    still leaks through these pages even though opening it 404s.
    Backfills a legacy project's owner the same way
    routes/workspace.py's _load_workspace_or_404 does, so a project
    doesn't sit permanently admin-only just because no one has opened
    its workspace page yet to trigger that backfill.

    CLAUDE-P40-E2: excludes a removed Project (workspace.removed_at)
    from every ordinary listing by default - "Remove Project" (Section
    C) must actually remove it from active Projects/Chats, not just
    hide a button. `include_removed=True` is the one deliberate
    exception, used only by the Removed Projects view below, which
    still goes through this same P32 access filter first - a project
    someone can't already open never becomes visible just because it
    was also removed.
    """
    from services.project_access import can_access_project, ensure_owner_backfilled, known_usernames

    governance_log = get_governance_log(current_app)
    usernames = known_usernames()
    username = session.get("username")
    admin = is_admin()

    documents = [d for pid in registry.list_ids() if (d := registry.get(pid)) is not None]
    accessible = []
    for document in documents:
        # A workspace file that predates the current schema must not
        # take down every project's listing for every user -- fails
        # CLOSED (excluded) on a load error, same reasoning as
        # app.py's _nav_recent_projects fix for the identical risk.
        try:
            workspace = store.get_or_create(document.project_id)
            ensure_owner_backfilled(store, workspace, governance_log, usernames)
            allowed = can_access_project(workspace, username, admin)
            removed = bool(workspace.removed_at)
        except TypeError:
            allowed = False
            removed = False
        if allowed and (removed == include_removed):
            accessible.append(document)
    return accessible


def _require_project_access_or_404(store, project_id: str):
    """Single-project counterpart to _accessible_documents, for the two
    routes below that operate on one project_id directly
    (delete_project, dashboard) rather than listing many."""
    from services.project_access import can_access_project, ensure_owner_backfilled, known_usernames

    workspace = store.get_or_create(project_id)
    ensure_owner_backfilled(store, workspace, get_governance_log(current_app), known_usernames())
    if not can_access_project(workspace, session.get("username"), is_admin()):
        abort(404)
    return workspace


def _project_summary(document, workspace, events) -> dict:
    """
    Shared, read-only project summary used by both the home page's
    recent-projects list and the Projects directory - one real, already-
    governed indicator set, never a fabricated project-health score:
    - requirements_count: len(workspace.requirements) - existing, unmodified.
    - open_rfi_count: RFIDrafts not yet issued - existing status field.
    - pending_attention_count (amber): Attentions still pending response.
    - unresolved_conflict_count (red): the legacy consistency-check's own
      flagged cross-requirement contradictions (document.consistency_flags)
      - the one real "conflict" signal that already exists, not invented.
    - last_activity: the most recent GovernanceLog event's timestamp where
      one exists, else the document's own ingested_at ("created_at").
    No new domain/store methods were added for this - every value above
    comes from an existing, unmodified public read (RequirementsRegistry,
    CaseWorkspaceStore.get, GovernanceLog.read).
    """
    return {
        "project_id": document.project_id,
        "filename": document.filename,
        # Pagescape correction #11: the professional-facing project
        # identity should be its own display_title, not the accident of
        # which document happened to be uploaded first - falls back to
        # filename only until a human sets one via Edit Project Details.
        "display_name": (workspace.display_title if workspace else None) or document.filename,
        "created_at": document.ingested_at,
        "last_activity": events[-1].created_at if events else document.ingested_at,
        "requirements_count": len(workspace.requirements) if workspace else 0,
        "open_rfi_count": (
            len([d for d in workspace.rfi_drafts if d["status"] != "issued"]) if workspace else 0
        ),
        "pending_attention_count": (
            len([a for a in workspace.attentions if a["status"] == "pending"]) if workspace else 0
        ),
        "unresolved_conflict_count": len(document.consistency_flags) if document.consistency_checked else 0,
    }


@portal_bp.route('/')
def index():
    """
    Project-first entry point: "what project are we working on," not a
    marketing page and not "how can I help you today." Anonymous visitors
    see the identity line + sign-in only. Authenticated visitors see a
    small, restrained recent-projects list - see _project_summary for the
    indicator set.
    """
    if not is_authenticated():
        return render_template('index.html', recent_projects=[])

    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    governance_log = get_governance_log(current_app)

    documents = _accessible_documents(registry, store)
    documents.sort(key=lambda d: d.ingested_at, reverse=True)

    recent_projects = [
        _project_summary(document, _safe_workspace(store, document.project_id), governance_log.read(document.project_id))
        for document in documents[:6]
    ]

    return render_template('index.html', recent_projects=recent_projects)


@portal_bp.route('/health')
def health():
    """Liveness/readiness probe for the load balancer and systemd.

    Un-prefixed and unauthenticated by design so it stays stable across
    /api/v1 version bumps. Checks the registry store (the app's only
    real runtime dependency) rather than the Anthropic API, since a
    slow/unreachable model API shouldn't take the whole app out of
    rotation — BHiveParser already degrades to rule-based classification.
    """
    try:
        get_registry(current_app).list_ids()
        registry_ok = True
    except OSError:
        registry_ok = False

    missing_config = []
    if not current_app.config.get('SECRET_KEY'):
        missing_config.append('FLASK_SECRET_KEY')
    if not current_app.config.get('ANTHROPIC_API_KEY'):
        missing_config.append('ANTHROPIC_API_KEY')

    status_code = 200 if registry_ok else 503
    return jsonify(
        status='ok' if registry_ok else 'error',
        checks={'registry_store': 'ok' if registry_ok else 'unreachable'},
        missing_config=missing_config,
    ), status_code


def _resolve_next_url() -> str:
    """?next= target after a successful/already-satisfied login - the
    project gateway (pick ingest vs. dashboard) when none was given.
    Only follows same-site relative paths -- ?next=https://evil.example
    would otherwise redirect an authenticated session off-site."""
    next_url = request.args.get('next') or url_for('portal.gateway')
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = url_for('portal.gateway')
    return next_url


@portal_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    # CLAUDE-P40-D1: an already-authenticated session must never be
    # shown the sign-in form at all - it previously rendered login.html
    # with the real authenticated app shell (nav, real project names)
    # wrapped around it, since nothing here checked session state
    # before rendering. Checked before either branch below, so it also
    # covers a stray POST from an already-authenticated session.
    if is_authenticated():
        return redirect(_resolve_next_url())

    if request.method == 'GET':
        return render_template('login.html', error=None)

    username = request.form.get('username', '')
    password = request.form.get('password', '')
    user = check_credentials(username, password)
    if user is not None:
        log_in(user)
        return redirect(_resolve_next_url())

    # Deliberately generic -- doesn't distinguish "no such user" from
    # "wrong password" (there's only one shared username anyway).
    return render_template('login.html', error='Invalid username or password.'), 401


@portal_bp.route('/logout')
def logout():
    log_out()
    # CLAUDE-P40-D1: was portal.index (the marketing/zero-state page) -
    # sign-out shall return to the isolated sign-in page itself, not a
    # page that merely also happens to be safe for an anonymous visitor.
    return redirect(url_for('portal.login'))


@portal_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"])
def forgot_password():
    """
    CLAUDE-P28: the self-service recovery path referenced by login.html's
    "Forgot password?" link.

    The confirmation MESSAGE text is decided purely from whether SMTP is
    configured at all (current_app.config['SMTP_HOST'], a fact identical
    for every single request) - never from whether this particular email
    matched an account, and never from whether this particular delivery
    attempt actually succeeded. Conditioning the message on per-request
    outcome would reintroduce an enumeration oracle: a real account's
    delivery genuinely failing (SMTP down) would then read differently
    than "no such account" (no delivery ever attempted), letting an
    attacker distinguish the two by probing during any SMTP outage. Real
    per-request delivery success/failure is reported in the server log
    only (services/password_reset.py) - see CLAUDE-P29 for this
    reasoning in full.

    dev_reset_link is the one deliberate exception: on a real match, in
    dev/testing only, with SMTP not having delivered it, the raw link is
    rendered directly on THIS page (clearly labelled, never in
    production) instead of only being logged - convenience, not a
    change to the message contract above. Renders directly rather than
    redirecting (unlike this file's other POST handlers) specifically
    so dev_reset_link can reach the response without being stashed
    anywhere persistent (a session/cookie) in between.
    """
    if request.method == 'GET':
        return render_template('forgot_password.html')

    dev_reset_link = request_password_reset(request.form.get('email', ''), base_url=request.host_url)

    if current_app.config.get('SMTP_HOST'):
        message = "If an account with that email exists, a password reset email has been sent."
    else:
        message = (
            "If an account with that email exists, a password reset has been initiated. "
            "Email delivery isn't configured in this environment."
        )
    flash(message, 'success')

    # Checked again here (request_password_reset already gates this) so a
    # future change to that function can't silently start leaking a real
    # reset link into a production response just by returning one.
    if dev_reset_link and is_dev_fallback_active():
        return render_template('forgot_password.html', dev_reset_link=dev_reset_link)
    return render_template('forgot_password.html')


@portal_bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit("10 per hour", methods=["POST"])
def reset_password():
    """
    The link a reset email (or the dev-only log fallback) points at.
    Deliberately one generic "invalid or expired" outcome for every
    invalid case (missing/unknown/already-used/expired token) - never
    distinguishing which, for the same account-existence/state reason
    request_password_reset never distinguishes "no such account" from
    "wrong password" elsewhere in this file.
    """
    token = request.args.get('token') if request.method == 'GET' else request.form.get('token')
    token_row = get_valid_reset_token(token or '')

    if token_row is None:
        flash("This reset link is invalid or has expired. Request a new one below.", 'error')
        return redirect(url_for('portal.forgot_password'))

    if request.method == 'GET':
        return render_template('reset_password.html', token=token)

    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    if len(new_password) < 8:
        flash("Choose a password at least 8 characters long.", 'error')
        return render_template('reset_password.html', token=token), 400
    if new_password != confirm_password:
        flash("Those passwords didn't match.", 'error')
        return render_template('reset_password.html', token=token), 400

    complete_password_reset(token_row, new_password)
    flash("Your password has been updated. Sign in with your new password.", 'success')
    return redirect(url_for('portal.login'))


@portal_bp.route('/gateway')
@login_required
def gateway():
    """Post-login landing: pick "ingest a new document" vs "view dashboard"
    instead of jumping straight into one, mirroring a project-selection
    style entry point rather than a single default destination."""
    return render_template('gateway.html')


_PROJECT_SORT_KEYS = {
    "last_updated": lambda p: p["last_activity"],
    "name": lambda p: p["display_name"].lower(),
    "created": lambda p: p["created_at"],
}


@portal_bp.route('/projects')
@login_required
def projects_list():
    """The project directory: every previously ingested project, so a
    returning user can find and reopen one without already knowing its
    project_id or having bookmarked its dashboard URL. Before this route
    existed, the only way back into a project was the redirect landed on
    right after uploading it -- there was no way to "reopen tomorrow"
    through the UI at all.

    Search and sort are both server-side over fields the application
    already has (filename/project_id, and the same last-updated/created
    timestamps _project_summary already computes for the home page) - no
    new metadata or search index was introduced.
    """
    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    governance_log = get_governance_log(current_app)

    query = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'last_updated')
    if sort not in _PROJECT_SORT_KEYS:
        sort = 'last_updated'

    documents = _accessible_documents(registry, store)
    if query:
        needle = query.lower()
        documents = [
            d for d in documents
            if needle in d.filename.lower() or needle in d.project_id.lower()
        ]

    projects = [
        _project_summary(document, _safe_workspace(store, document.project_id), governance_log.read(document.project_id))
        for document in documents
    ]
    projects.sort(key=_PROJECT_SORT_KEYS[sort], reverse=(sort != 'name'))

    return render_template('projects.html', projects=projects, query=query, sort=sort)


@portal_bp.route('/removed-projects')
@login_required
def removed_projects():
    """CLAUDE-P40-E2, Section B: "Removed Projects" - where an
    authorized user restores a whole Project removed via
    workspace.remove_project_route. A removed Project's own workspace
    page stays directly reachable to an authorized user (removal never
    changes P32 access, only listing visibility - see
    _accessible_documents), but nothing in the ordinary nav links to it
    any more once removed; this page is the deliberate, explicit way
    back to it."""
    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    governance_log = get_governance_log(current_app)

    documents = _accessible_documents(registry, store, include_removed=True)
    removed = [
        _project_summary(document, _safe_workspace(store, document.project_id), governance_log.read(document.project_id))
        for document in documents
    ]
    for row, document in zip(removed, documents):
        workspace = _safe_workspace(store, document.project_id)
        row["removed_at"] = workspace.removed_at if workspace else None
        row["removed_by"] = workspace.removed_by if workspace else None

    return render_template('removed_projects.html', removed=removed)


def _delete_project_files(app, project_id: str) -> None:
    """
    Permanently removes every stored artifact for a project - the legacy
    RequirementsRegistry record, its GovernanceLog, its CaseWorkspaceStore
    workspace, and any project-scoped uploaded files. Deliberately NOT a
    governed operation: no Supersession, no Snapshot, nothing preserved -
    this exists for removing unwanted/duplicate/test project entries
    (Project Entry Rule), never for real project history, which is why it
    carries its own honest confirmation wording rather than reusing the
    Approval Gate's "this changes governed project state" framing (this
    is the opposite of a governed state change - it's erasure).
    """
    store_path = Path(app.config["REGISTRY_STORE_PATH"])
    for suffix in (".json", ".governance.jsonl", ".workspace.json"):
        (store_path / f"{project_id}{suffix}").unlink(missing_ok=True)

    sources_dir = store_path / "workspace_sources" / project_id
    if sources_dir.exists():
        shutil.rmtree(sources_dir)


@portal_bp.route('/projects/<project_id>/delete', methods=['POST'])
@admin_required
def delete_project(project_id):
    """
    Same confirm-gate idiom already used for consequential actions
    elsewhere in this app (submit once with no `confirm` value -> shown
    the gate; submit again with confirm=yes/no -> acted on) - not a new
    pattern, just this route's own honestly-worded version of it, since
    deletion is not a governed action the existing Approval Gate wording
    could accurately describe.
    """
    document = get_registry(current_app).get(project_id)
    if document is None:
        abort(404)
    # CLAUDE-P32: this route is already @admin_required, so an admin
    # session always passes this gate -- kept here anyway for defense in
    # depth and consistency with every other project-scoped route, not
    # because a non-admin could otherwise reach this route at all.
    _require_project_access_or_404(CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"]), project_id)

    confirm = request.form.get('confirm')
    if confirm == 'no':
        flash('Deletion cancelled - no change was made.', 'success')
        return redirect(url_for('portal.projects_list'))
    if confirm != 'yes':
        return render_template(
            'confirm_delete_project.html', project_id=project_id, filename=document.filename,
        )

    _delete_project_files(current_app, project_id)
    flash(f'Project "{document.filename}" permanently deleted.', 'success')
    return redirect(url_for('portal.projects_list'))


# -- CLAUDE-P40-E2/E2A, Section D/B: Reset Project Data (administrator-only
# clean test reset) and reset-snapshot restoration ------------------------
#
# Every snapshot this module creates (a Reset's own pre-wipe copy, or a
# Restore's own pre-restore safety copy) carries a manifest -
# SNAPSHOT_MANIFEST_FILENAME, written inside the snapshot directory
# itself - recording who/when/what-kind and a sha256 checksum of every
# file, so a later restore can PROVE the snapshot it's about to use is
# exactly what was captured, not silently corrupted or partially copied.

RESET_CONFIRMATION_PHRASE = "RESET PROJECT DATA"
RESTORE_CONFIRMATION_PHRASE = "RESTORE SNAPSHOT"

# Deliberately NOT ".json" - RequirementsRegistry.list_ids() globs "*.json"
# directly against whatever store_path it's given (see that module's own
# comment on why ".workspace.json" needs its own exclusion), and this
# manifest lives inside snapshot directories that get inventoried the
# exact same way a live store does (_inventory_from_store_path below). A
# ".json" name here would be misread as a bogus extra "project".
SNAPSHOT_MANIFEST_FILENAME = "_snapshot_manifest.snapshot"


def _win_long_path(path: Path) -> str:
    """
    CLAUDE-P40-E2A1: a real, live isolated-process run of Reset Project
    Data raised `shutil.Error([WinError 3] The system cannot find the
    path specified)` from `shutil.copytree` the moment a snapshot's own
    directory (registry_snapshots/<stamp>/) added one more level of
    nesting on top of an already-deep `workspace_sources/<project_id>/
    <hash>_<filename>` path - not an artifact of that verification
    environment (its shorter, un-nested source path copied fine at
    ingestion time), a genuine Windows MAX_PATH (260 character) limit
    that any sufficiently long REGISTRY_STORE_PATH/filename combination
    can hit in the real deployment too, snapshot-nesting or not.

    The Windows-sanctioned fix without any OS-level configuration
    change (a `LongPathsEnabled` registry/group-policy opt-in cannot be
    assumed present on a given deployment host) is the `\\\\?\\`
    extended-length prefix, which raises the effective limit to ~32,767
    characters for that one call. Applied at the exact point every
    shutil/os call in this snapshot/reset/restore code path touches the
    filesystem - never earlier, since `\\\\?\\`-prefixed strings skip
    normal path normalization (they must already be absolute, backslash-
    separated, with no `..` segments) and would break ordinary Path
    methods (`.relative_to`, `.name`, glob) used everywhere else in this
    module. A no-op (returns the plain resolved path) on any other OS.
    """
    resolved = str(path.resolve())
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    return "\\\\?\\" + resolved


class SnapshotIntegrityError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_win_long_path(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory_from_store_path(store_path: Path) -> dict:
    """Exact counts of everything under an arbitrary registry store
    directory - every Project (active or removed), and the Documents/
    Investigations/Findings/Requirements inside them. Works identically
    against the live store (Reset's own preview) or a snapshot's copy
    (the snapshot-listing/restore-preview pages), since both are just
    RequirementsRegistry/CaseWorkspaceStore-shaped directories."""
    registry = RequirementsRegistry(str(store_path))
    store = CaseWorkspaceStore(str(store_path))
    inventory = {"projects": 0, "documents": 0, "investigations": 0, "findings": 0, "requirements": 0}
    for project_id in registry.list_ids():
        document = registry.get(project_id)
        if document is None:
            continue
        inventory["projects"] += 1
        workspace = _safe_workspace(store, project_id)
        if workspace is None:
            continue
        inventory["documents"] += len(workspace.sources)
        inventory["investigations"] += len(workspace.cases)
        inventory["findings"] += len(workspace.findings)
        inventory["requirements"] += len(workspace.requirements)
    return inventory


def _project_data_inventory(app) -> dict:
    return _inventory_from_store_path(Path(app.config["REGISTRY_STORE_PATH"]))


def _create_snapshot(store_path: Path, snapshot_root: Path, actor: str, kind: str) -> Path:
    """
    Copies the whole store_path tree into a new timestamped directory
    under snapshot_root, then writes SNAPSHOT_MANIFEST_FILENAME inside
    that same directory: actor/time/kind, the inventory computed once
    at creation time, and a sha256 checksum of every real file (recorded
    BEFORE the manifest itself is written, so the manifest never has to
    describe its own checksum). `kind` distinguishes a Reset Project
    Data snapshot ("reset") from a pre-restore safety snapshot
    ("pre_restore_safety") taken automatically by _restore_snapshot -
    both are ordinary, equally restorable snapshots; `kind` is a label
    for the listing page, not a behavioral difference.
    """
    snapshot_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    snapshot_dir = snapshot_root / stamp
    shutil.copytree(_win_long_path(store_path), _win_long_path(snapshot_dir))

    checksums = {
        str(path.relative_to(snapshot_dir).as_posix()): _sha256_of(path)
        for path in sorted(snapshot_dir.rglob("*"))
        if path.is_file()
    }
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "kind": kind,
        "inventory": _inventory_from_store_path(snapshot_dir),
        "file_count": len(checksums),
        "checksums": checksums,
    }
    with open(_win_long_path(snapshot_dir / SNAPSHOT_MANIFEST_FILENAME), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(manifest, indent=2))
    return snapshot_dir


def _verify_snapshot_integrity(snapshot_dir: Path) -> tuple[bool, list[str]]:
    """Recomputes checksums of every file CURRENTLY in snapshot_dir and
    compares against what its own manifest recorded at creation time -
    Section B: "verifies the snapshot manifest and checksums before
    restoration". A missing file, a changed file, or an unexplained
    extra file are all reported; restoration never proceeds if this
    returns any problems."""
    manifest_path = snapshot_dir / SNAPSHOT_MANIFEST_FILENAME
    if not manifest_path.exists():
        return False, ["No manifest found for this snapshot - cannot verify integrity."]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"Manifest could not be read: {exc}"]

    recorded = manifest.get("checksums", {})
    current_files = {
        str(path.relative_to(snapshot_dir).as_posix())
        for path in snapshot_dir.rglob("*")
        if path.is_file() and path.name != SNAPSHOT_MANIFEST_FILENAME
    }

    problems = []
    for rel_path, expected_hash in recorded.items():
        if rel_path not in current_files:
            problems.append(f"Missing file: {rel_path}")
            continue
        if _sha256_of(snapshot_dir / rel_path) != expected_hash:
            problems.append(f"Checksum mismatch: {rel_path}")
    for rel_path in sorted(current_files - set(recorded.keys())):
        problems.append(f"Unexpected extra file (not in manifest): {rel_path}")
    return (len(problems) == 0), problems


def _list_snapshots(app) -> list[dict]:
    store_path = Path(app.config["REGISTRY_STORE_PATH"])
    snapshot_root = store_path.parent / "registry_snapshots"
    if not snapshot_root.exists():
        return []
    rows = []
    for entry in snapshot_root.iterdir():
        if not entry.is_dir():
            continue
        manifest_path = entry / SNAPSHOT_MANIFEST_FILENAME
        if not manifest_path.exists():
            # Not a manifest-bearing snapshot (a directory that predates
            # this stage, or something unrelated left in the same
            # parent folder) - skip rather than guess at its shape.
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.append({
            "snapshot_id": entry.name,
            "created_at": manifest.get("created_at"),
            "actor": manifest.get("actor"),
            "kind": manifest.get("kind"),
            "inventory": manifest.get("inventory", {}),
            "file_count": manifest.get("file_count"),
        })
    rows.sort(key=lambda r: r["created_at"] or "", reverse=True)
    return rows


def _resolve_snapshot_dir(snapshot_root: Path, snapshot_id: str) -> Optional[Path]:
    """`snapshot_id` arrives as a raw URL segment - validated against
    path traversal two ways (a plain substring check, and confirming
    the resolved path actually lives inside snapshot_root) before it's
    ever used to build a filesystem path, matching this codebase's
    existing "never trust a raw id from the request" discipline
    (see e.g. show_workspace's own ?source= handling)."""
    if not snapshot_id or "/" in snapshot_id or "\\" in snapshot_id or ".." in snapshot_id:
        return None
    candidate = (snapshot_root / snapshot_id).resolve()
    try:
        candidate.relative_to(snapshot_root.resolve())
    except ValueError:
        return None
    if not candidate.is_dir() or not (candidate / SNAPSHOT_MANIFEST_FILENAME).exists():
        return None
    return candidate


def _lock_info(lock_path: Path) -> Optional[dict]:
    """Section E/B: "safely handles interruption and stale duplicate-
    submission locks" - a lock left behind by a crashed/interrupted
    reset or restore blocks new ones (correct - never race two against
    the same store), but must not be a silent, unexplained wall. Shows
    how long it's been held so an administrator can tell "this is
    normal, wait" from "this is stuck, something crashed" - clearing it
    is a manual filesystem action (deleting one lock file), deliberately
    not exposed as an in-app override button that would defeat the
    guard's own purpose."""
    if not lock_path.exists():
        return None
    return {"age_seconds": int(time.time() - lock_path.stat().st_mtime)}


def _reset_project_data(app, actor: str) -> Path:
    """
    Wipes every Project's data and returns to a clean no-project state,
    while retaining user accounts (instance/bhive.db - a wholly separate
    file this function never touches), application config/.env/schema
    version (also never touched - this only ever acts inside
    REGISTRY_STORE_PATH), and security policy/authorization config
    (instance/registry/security_governance/ - password-reset and
    rate-limit state, not project content - explicitly skipped below).

    Never a destructive wipe with nothing kept: the whole
    REGISTRY_STORE_PATH tree is copied to a checksummed, manifest-
    bearing snapshot via _create_snapshot first - the same snapshot
    format _restore_snapshot below knows how to verify and restore from
    (CLAUDE-P40-E2A, Section B - restoration is now a real, tested,
    in-app path, not "a manual filesystem operation" as this function's
    own docstring previously, incorrectly, claimed).
    """
    store_path = Path(app.config["REGISTRY_STORE_PATH"])
    snapshot_root = store_path.parent / "registry_snapshots"
    snapshot_dir = _create_snapshot(store_path, snapshot_root, actor=actor, kind="reset")

    removed_entries = []
    for entry in store_path.iterdir():
        if entry.name == "security_governance":
            continue
        removed_entries.append(entry.name)
        if entry.is_dir():
            shutil.rmtree(_win_long_path(entry))
        else:
            entry.unlink()

    # Recorded here, not via GovernanceLog (per-project, and every
    # project's own log was just wiped/snapshotted above) - this is the
    # one durable record of the reset itself: actor, time, and what was
    # removed (Section E: "record actor/time/reason/affected
    # identifiers"). Lives under security_governance/, the one
    # subdirectory this function deliberately never removes.
    audit_dir = store_path / "security_governance"
    audit_dir.mkdir(parents=True, exist_ok=True)
    with (audit_dir / "reset_audit.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "event": "reset",
            "actor": actor,
            "at": datetime.now(timezone.utc).isoformat(),
            "snapshot_dir": str(snapshot_dir),
            "removed_entries": sorted(removed_entries),
        }) + "\n")

    return snapshot_dir


def _restore_snapshot(app, snapshot_dir: Path, actor: str) -> dict:
    """
    CLAUDE-P40-E2A, Section B: restores the complete project-record
    family from a verified snapshot, atomically as the filesystem
    allows.

    Never reverts security_governance/ - accounts/security state stays
    whatever is CURRENTLY live, never the snapshot's old copy ("retains
    accounts, security governance, configuration, credentials and
    schema" applies to a RESTORE too, not just a Reset). Never copies
    the snapshot's own manifest file into the live store.

    Atomicity - stated honestly, not oversold: a flat-JSON-file
    directory tree has no built-in multi-file transaction the way a
    database does. This gets as close as the filesystem allows: the
    complete restored tree is built in a STAGING directory first (a
    failure while copying never touches the live store at all), then
    swapped into place with two single-directory os.rename calls, each
    individually atomic on the same volume. The one residual risk is a
    crash landing in the near-zero window BETWEEN those two renames,
    which would leave the live store path briefly missing - this is
    "safely recoverable", not full ACID atomicity. Mitigated three ways
    rather than eliminated: (1) a safety snapshot of the CURRENT live
    state is taken immediately before that window even opens, so
    whatever was live is never lost regardless of what happens next;
    (2) the shared reset/restore lock file makes an interrupted
    operation visibly "in progress" rather than silently appearing to
    have succeeded; (3) manual recovery from either snapshot is always
    a plain filesystem copy, and both are named in the audit record
    this function writes. If a future architecture needs stronger
    guarantees than this, that is the exact limitation to report -
    this implementation does not claim more than the above.
    """
    store_path = Path(app.config["REGISTRY_STORE_PATH"])
    snapshot_root = store_path.parent / "registry_snapshots"

    ok, problems = _verify_snapshot_integrity(snapshot_dir)
    if not ok:
        raise SnapshotIntegrityError(problems)

    safety_snapshot_dir = _create_snapshot(store_path, snapshot_root, actor=actor, kind="pre_restore_safety")

    token = uuid.uuid4().hex[:8]
    staging_dir = store_path.parent / f".{store_path.name}.restoring_{token}"
    old_dir = store_path.parent / f".{store_path.name}.superseded_{token}"

    staging_dir.mkdir(parents=True)
    for entry in snapshot_dir.iterdir():
        if entry.name in (SNAPSHOT_MANIFEST_FILENAME, "security_governance"):
            continue
        dest = staging_dir / entry.name
        if entry.is_dir():
            shutil.copytree(_win_long_path(entry), _win_long_path(dest))
        else:
            shutil.copy2(_win_long_path(entry), _win_long_path(dest))
    # security_governance/ comes from the CURRENT live store, never the
    # snapshot - see this function's own docstring.
    live_security_dir = store_path / "security_governance"
    if live_security_dir.exists():
        shutil.copytree(_win_long_path(live_security_dir), _win_long_path(staging_dir / "security_governance"))

    os.rename(_win_long_path(store_path), _win_long_path(old_dir))
    os.rename(_win_long_path(staging_dir), _win_long_path(store_path))
    shutil.rmtree(_win_long_path(old_dir), ignore_errors=True)

    audit_dir = store_path / "security_governance"
    audit_dir.mkdir(parents=True, exist_ok=True)
    with (audit_dir / "reset_audit.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "event": "snapshot_restored",
            "actor": actor,
            "at": datetime.now(timezone.utc).isoformat(),
            "restored_snapshot_dir": str(snapshot_dir),
            "safety_snapshot_dir": str(safety_snapshot_dir),
        }) + "\n")

    return {"safety_snapshot_dir": safety_snapshot_dir}


@portal_bp.route('/admin/reset-project-data', methods=['GET', 'POST'])
@admin_required
def reset_project_data():
    """
    GET shows the exact inventory and a typed-confirmation form. POST
    requires the confirmation phrase to match exactly, and is guarded
    against duplicate submission by an atomic lock file (os.O_EXCL - the
    first request to create it wins; a second, concurrent or
    double-clicked request sees FileExistsError and is told a reset is
    already running, rather than racing a second reset) - Section E:
    "make operations atomic or safely recoverable" /
    "prevent duplicate submission". The SAME lock file also guards
    restore_reset_snapshot below, so a reset and a restore against this
    store can never run concurrently either.
    """
    store_path = Path(current_app.config["REGISTRY_STORE_PATH"])
    # Deliberately a sibling of store_path, not inside it - so the lock
    # file itself is never swept into the snapshot or the wipe loop
    # below (both of which iterate store_path's own contents).
    lock_path = store_path.parent / ".reset_project_data.lock"

    if request.method == 'GET':
        return render_template(
            'reset_project_data.html',
            inventory=_project_data_inventory(current_app),
            confirmation_phrase=RESET_CONFIRMATION_PHRASE,
            lock_info=_lock_info(lock_path),
        )

    if lock_path.exists():
        flash('A Reset or Restore is already in progress - please wait for it to finish.', 'error')
        return redirect(url_for('portal.reset_project_data'))

    typed = (request.form.get('confirmation_phrase') or '').strip()
    if typed != RESET_CONFIRMATION_PHRASE:
        flash(f'Type "{RESET_CONFIRMATION_PHRASE}" exactly to confirm - nothing was reset.', 'error')
        return redirect(url_for('portal.reset_project_data'))

    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        flash('A Reset or Restore is already in progress - please wait for it to finish.', 'error')
        return redirect(url_for('portal.reset_project_data'))

    try:
        _reset_project_data(current_app, actor=session.get('username') or 'unknown')
        flash('Project data reset - the Workspace is clean. Everything that was here was snapshotted first.', 'success')
    finally:
        lock_path.unlink(missing_ok=True)

    return redirect(url_for('portal.projects_list'))


@portal_bp.route('/admin/reset-project-data/snapshots')
@admin_required
def list_reset_snapshots():
    """CLAUDE-P40-E2A, Section B: "lists available reset snapshots by
    timestamp, actor and inventory" - every snapshot _create_snapshot
    has ever written (both Reset Project Data's own, and any prior
    restore's automatic pre_restore_safety copy), newest first."""
    store_path = Path(current_app.config["REGISTRY_STORE_PATH"])
    lock_path = store_path.parent / ".reset_project_data.lock"
    return render_template(
        'reset_snapshots.html',
        snapshots=_list_snapshots(current_app),
        lock_info=_lock_info(lock_path),
    )


@portal_bp.route('/admin/reset-project-data/snapshots/<snapshot_id>/restore', methods=['GET', 'POST'])
@admin_required
def restore_reset_snapshot(snapshot_id):
    """
    GET verifies the snapshot's own checksums, previews what restoring
    it would replace (the CURRENT live inventory) against what it would
    bring back (the snapshot's own recorded inventory), and shows the
    typed-confirmation form - refused if integrity verification failed.
    POST re-verifies (never trusts the GET-time check alone), requires
    the confirmation phrase, and is guarded by the same lock file
    reset_project_data uses.
    """
    store_path = Path(current_app.config["REGISTRY_STORE_PATH"])
    snapshot_root = store_path.parent / "registry_snapshots"
    lock_path = store_path.parent / ".reset_project_data.lock"

    snapshot_dir = _resolve_snapshot_dir(snapshot_root, snapshot_id)
    if snapshot_dir is None:
        abort(404)

    if request.method == 'GET':
        try:
            manifest = json.loads((snapshot_dir / SNAPSHOT_MANIFEST_FILENAME).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        ok, problems = _verify_snapshot_integrity(snapshot_dir)
        return render_template(
            'restore_snapshot.html',
            snapshot_id=snapshot_id,
            manifest=manifest,
            integrity_ok=ok,
            integrity_problems=problems,
            current_inventory=_project_data_inventory(current_app),
            confirmation_phrase=RESTORE_CONFIRMATION_PHRASE,
            lock_info=_lock_info(lock_path),
        )

    if lock_path.exists():
        flash('A Reset or Restore is already in progress - please wait for it to finish.', 'error')
        return redirect(url_for('portal.restore_reset_snapshot', snapshot_id=snapshot_id))

    typed = (request.form.get('confirmation_phrase') or '').strip()
    if typed != RESTORE_CONFIRMATION_PHRASE:
        flash(f'Type "{RESTORE_CONFIRMATION_PHRASE}" exactly to confirm - nothing was restored.', 'error')
        return redirect(url_for('portal.restore_reset_snapshot', snapshot_id=snapshot_id))

    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        flash('A Reset or Restore is already in progress - please wait for it to finish.', 'error')
        return redirect(url_for('portal.restore_reset_snapshot', snapshot_id=snapshot_id))

    try:
        _restore_snapshot(current_app, snapshot_dir, actor=session.get('username') or 'unknown')
        flash('Snapshot restored. A safety snapshot of what was live just before this was also taken.', 'success')
    except SnapshotIntegrityError as exc:
        flash('Snapshot failed integrity verification - nothing was restored: ' + '; '.join(exc.problems), 'error')
        return redirect(url_for('portal.restore_reset_snapshot', snapshot_id=snapshot_id))
    finally:
        lock_path.unlink(missing_ok=True)

    return redirect(url_for('portal.projects_list'))


@portal_bp.route('/search')
@login_required
def global_search():
    """
    Global search overlay's backend (UI design-development pass: sidebar
    header / search). Projects are the one real, already-indexed,
    cross-project searchable object in this application today - the same
    filename/project_id substring match the Projects directory's own
    search already uses (see projects_list above), just exposed as JSON
    for the overlay instead of a full-page GET.

    The result shape (kind/title/subtitle/url) is deliberately generic so
    Requirements/Investigations/Findings/RFIs/etc. can become real search
    sources later without changing this shape or the overlay's rendering
    - this route must never claim search coverage the backend doesn't
    actually have.
    """
    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify(results=[])

    needle = query.lower()
    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    documents = _accessible_documents(registry, store)
    matches = [
        d for d in documents
        if needle in d.filename.lower() or needle in d.project_id.lower()
    ][:20]

    results = [
        {
            "kind": "Project",
            "title": d.filename,
            "subtitle": d.project_id,
            "url": url_for('workspace.show_workspace', project_id=d.project_id),
        }
        for d in matches
    ]
    return jsonify(results=results)


@portal_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
@limiter.limit("20 per hour", methods=["POST"])
def upload():
    max_upload_mb = current_app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)

    if request.method == 'GET':
        # CLAUDE-P29: an optional ?environment= deep link from the two
        # gateway entrance cards pre-selects the radio -- convenience
        # only, the POST below validates independently regardless of
        # how the form was reached or what was pre-selected.
        return render_template(
            'upload.html', max_upload_mb=max_upload_mb,
            selected_environment=request.args.get('environment'),
            operating_environments=OPERATING_ENVIRONMENT_LABELS,
        )

    try:
        document = ingest_upload(
            request.files.get('file'),
            current_app,
            operating_environment=request.form.get('operating_environment', ''),
            # CLAUDE-P32: the real, already-authenticated session identity
            # (this route is @admin_required) -- never request.form.get
            # ('actor'), which is free text a caller could type anything
            # into (see ingest_upload's own docstring for why the two
            # must stay separate).
            owner=session.get('username', ''),
            actor=request.form.get('actor'),
            role=request.form.get('role'),
            project_name=request.form.get('project_name'),
        )
    except (UploadError, GovernanceError) as exc:
        return render_template(
            'upload.html', max_upload_mb=max_upload_mb, error=str(exc),
            selected_environment=request.form.get('operating_environment'),
            operating_environments=OPERATING_ENVIRONMENT_LABELS,
        ), 400

    # CLAUDE-P38-D2: routes through the "Preparing your Project
    # Briefing..." interstitial rather than straight to the workspace -
    # that route itself redirects straight through when there's nothing
    # to prepare (AI not allowed/already approval-gated/no Sources), so
    # this is always safe to do unconditionally here.
    return redirect(url_for('workspace.preparing_project_briefing', project_id=document.project_id))


@portal_bp.route('/dashboard')
@portal_bp.route('/dashboard/<project_id>')
@login_required
def dashboard(project_id=None):
    """
    Retired as a real page - Case Workspace is now the one authoritative
    project view (it already showed everything the legacy Dashboard did:
    extracted-not-governed Requirements, governed Requirements, RFI
    Export with the actual flagged-contradiction cards, History/audit
    trail). The one piece deliberately NOT carried forward is the
    milestone lattice: _derive_milestones (bhive_parser.py) only ever
    produces status="pending" for real projects - "done"/"active" only
    ever appeared in this route's own hardcoded demo data - so it never
    reflected real project state and there was nothing genuine to port.

    Kept as a redirect, not deleted outright, so an old bookmark or
    external link to /dashboard/<id> still lands somewhere real instead
    of 404ing.
    """
    if project_id is None:
        return redirect(url_for('portal.projects_list'))

    document = get_registry(current_app).get(project_id)
    if document is None:
        abort(404)
    # CLAUDE-P32: checked here too (not just relying on the redirect
    # target's own gate) so a denied request 404s directly rather than
    # bouncing through an extra redirect first.
    _require_project_access_or_404(CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"]), project_id)
    return redirect(url_for('workspace.show_workspace', project_id=project_id))
