# Specified But Unbuilt — Tenancy and Project-Level Authorization

**Status:** Specified, not implemented. Produced as Block 10 of the CLAUDE-P27-B autonomous work plan; deliberately excluded from execution because multiple product decisions remain genuinely unresolved (§5).

## 0. Why this exists

The CLAUDE-P27 architectural review found that this repository has no project-ownership or tenancy concept at all. `routes/workspace.py:120-129`'s `_load_workspace_or_404` resolves a project purely by `project_id` string match:

```python
def _load_workspace_or_404(project_id: str):
    document = get_registry(current_app).get(project_id)
    if document is None:
        abort(404)
    store = _store()
    workspace = store.get_or_create(
        project_id, register_document_source=document_source_payload(document),
    )
    return document, store, workspace
```

Every route in `routes/workspace.py` calls this (or the portal.py equivalents below) with no ownership/membership check — any authenticated user, `admin` or `read_only`, can open any project by knowing or guessing its `project_id`. `services/case_workspace.py`'s Case-level privacy (`visible_cases_for`, `_require_visible_case`) is real and well-tested, but it is a *sub-project* concern layered on top of a *project* layer with zero access control beyond "logged in."

## 1. Domain model

Three new SQLAlchemy tables in `models.py`, alongside the existing `User`/`PasswordResetToken`. Field types match the existing style (`db.Column`, explicit lengths, `db.ForeignKey`).

```python
class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), nullable=False, default="active")  # "active" | "suspended"


class OrganizationMembership(db.Model):
    __tablename__ = "organization_memberships"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    org_role = db.Column(db.String(20), nullable=False, default="member")  # "owner" | "member"
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),)


class ProjectOwnership(db.Model):
    """Maps an existing flat-JSON project_id (RequirementsRegistry /
    CaseWorkspaceStore key -- never a SQL FK, since projects are not a
    SQL table) to exactly one owning Organization. One row per project;
    a project belongs to exactly one org (see open decision #2)."""
    __tablename__ = "project_ownerships"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
```

Org-scoped project-name uniqueness: `services/ingestion.py:60-75`'s `_reject_if_name_taken` currently compares against `existing_names` built from **every** project in the registry (`registry.list_ids()` globally, no org filter). The replacement scopes that same comparison to only the projects owned (via `ProjectOwnership`) by the uploading user's organization — same function shape, one added join/filter, no change to the collision-detection logic itself.

## 2. Route-authorization matrix

**Key finding: this is a one-call-site fix for the entire `routes/workspace.py` blueprint, not 46 separate edits.** Every route in that file reaches project data exclusively through `_load_workspace_or_404(project_id)` (`routes/workspace.py:120-129`) — confirmed by reading every `@workspace_bp.route` definition in the file (grep of all route/decorator/def lines, `routes/workspace.py:243-2408`, 46 routes total). Adding one `require_project_access(project_id)` call as the first line of `_load_workspace_or_404` closes all 46 at once, exactly mirroring how `_require_visible_case` (`routes/workspace.py:178-198`) already centralizes Case-level checks — same architectural pattern, one layer up.

Full route list (all currently `@login_required` only, all reach `_load_workspace_or_404`):
`show_workspace` (243), `create_case` (868), `toggle_star` (894), `edit_project_details` (904), `edit_operating_instructions` (921), `add_document_source` (938), `add_text_record_source` (976), `create_project_snapshot` (1011), `share_case` (1035), `retract_case` (1054), `archive_case` (1076), `derive_case` (1100), `record_case_outcome_route` (1124), `adopt_finding` (1153), `adopt_review_message` (1178), `create_thread` (1206), `create_temporal_obligation_route` (1252), `add_thread_message` (1297), `request_thread_attention` (1327), `respond_to_attention_route` (1356), `resolve_thread` (1395), `reopen_thread` (1423), `add_drawing_source` (1447), `source_file` (1504), `revise_source` (1538), `post_message` (1693), `quick_start` (1712), `discuss_object` (1748), `start_investigation_from_aperture` (1782), `validate_finding` (1825), `set_disposition` (1862), `promote_requirement_item_route` (1898), `register_requirement_route` (1953), `adjudicate_requirement` (1998), `revise_requirement_route` (2031), `register_participant_route` (2066), `set_represented_party_route` (2090), `record_perspective_assessment_route` (2111), `apply_findings` (2147), `cancel_rfi_intent` (2213), `preview_rfi_draft` (2222), `create_rfi_draft` (2242), `update_rfi_question` (2284), `issue_rfi_draft` (2301), `export_rfi_draft` (2343), `artifact_image` (2383), `export_rfi` (2406).

`routes/portal.py` — three routes bypass `_load_workspace_or_404` entirely and need their own explicit call:

| Route | Line | Current auth | Fix |
|---|---|---|---|
| `delete_project(project_id)` | 326 | `@admin_required`, loads via `get_registry(...).get(project_id)` directly (335) | Add `require_project_access(project_id)` before the confirm-gate logic — deletion must not even reveal a project's existence to an admin outside its org (open decision #4 addresses whether admin bypasses this at all) |
| `dashboard(project_id=None)` | 421 | `@login_required`, loads via `get_registry(...).get(project_id)` directly (440) | Add `require_project_access(project_id)` before the redirect |
| `global_search()` | 355 | `@login_required`, no single `project_id` — matches across **every** project via `registry.list_ids()` (376) | Not a single gate call — needs the candidate `documents` list filtered to the requester's org-visible `ProjectOwnership` set *before* the substring match, not filtered after |
| `projects_list()` | 264 | `@login_required`, lists via `registry.list_ids()` (286), same as `global_search` | Same treatment as `global_search` — filter `documents` to org-visible projects before building `_project_summary` rows |
| `upload()` | 396 | `@admin_required`, creates a **new** project (`ingest_upload`, 403) | Not an access check — needs a decision on which `organization_id` the newly created project's `ProjectOwnership` row gets (the uploader's own org, assuming single-org membership — see open decision #1) |

`routes/api.py` (flagged for completeness, out of this document's originally assigned scope): after CLAUDE-P27-B Block 0 (session-auth added to the whole blueprint), 6 of its 9 routes still take a `project_id` and will need the same `require_project_access` call once this migration lands (`get_document`, `get_requirements`, `get_milestones`, `get_consistency`, `get_governance`, `export_rfi`) — `documents/ingest` and `categories` don't take an existing project_id, `documents` (list) needs the same org-filter treatment as `projects_list`/`global_search`.

## 3. Migration design

Matches `app.py`'s existing idempotent pattern (`_migrate_users_email_column`, `app.py:77-111`) — column/table-presence checks, safe to call on every boot, no version table.

```python
def _migrate_tenancy_tables(app: Flask) -> None:
    # create_all() already creates organizations/organization_memberships/
    # project_ownerships as new tables on both a fresh install and an
    # existing one (create_all only fails to add COLUMNS to existing
    # tables, never fails to add whole new tables) -- this function's
    # only job is the one-time backfill for a database that predates
    # these tables entirely.
    from sqlalchemy import inspect
    from models import db, Organization, OrganizationMembership, ProjectOwnership, User
    from services.ingestion import get_registry

    inspector = inspect(db.engine)
    if "project_ownerships" not in inspector.get_table_names():
        return  # create_all() hasn't run yet this boot -- nothing to backfill against

    if ProjectOwnership.query.first() is not None:
        return  # already backfilled (idempotency check, not a version table)

    app.logger.info("Tenancy backfill: creating default organization for existing data.")
    default_org = Organization(name="Default Organization", status="active")
    db.session.add(default_org)
    db.session.flush()  # get default_org.id without a full commit yet

    for user in User.query.all():
        db.session.add(OrganizationMembership(
            user_id=user.id, organization_id=default_org.id,
            org_role="owner" if user.role == "admin" else "member",
        ))

    registry = get_registry(app)
    for project_id in registry.list_ids():
        db.session.add(ProjectOwnership(project_id=project_id, organization_id=default_org.id))

    db.session.commit()
    app.logger.info("Tenancy backfill complete.")
```

Called from `_register_database` (`app.py:60-74`) after `db.create_all()`, alongside the two existing `_migrate_users_*` calls. Preserves current behavior exactly on day one (every existing project/account lands in one shared default org, so nothing becomes invisible to anyone who could already see it) — the isolation boundary only becomes meaningful once a second organization is created.

**Required before executing, not before designing:** a verified backup (Block 8 of the P27-B plan) and a scratch-copy dry run against a copy of the real `instance/bhive.db` + `instance/registry/`, matching the discipline already used for the P28/P30 migrations per their own commit messages.

## 4. Isolation test matrix

New `tests/test_project_isolation.py`, modeled directly on the existing `tests/test_route_authorization_hardening.py` pattern (`session_transaction()` to set up two genuinely separate authenticated sessions, real HTTP requests via `test_client()`).

Setup: two organizations (`org_a`, `org_b`), one project owned by each (`project_a`, `project_b`), one user in each org (`user_a` in `org_a` only, `user_b` in `org_b` only).

Required cases, one per row of §2's matrix plus the cross-cutting ones:

1. `user_a` can open `project_a`'s workspace (`GET /projects/project_a/workspace`) — 200.
2. `user_a` cannot open `project_b`'s workspace — 404 (not 403, matching `_require_visible_case`'s existing convention of not confirming existence to a non-member).
3. `user_a` cannot POST to any write route under `project_b` (parametrize across all 46 routes in §2's list, or at minimum one representative from each sub-area: case creation, source upload, snapshot creation, requirement adjudication, RFI issuance) — 404.
4. `user_a` cannot GET `project_b`'s `source_file`/`artifact_image`/`export_rfi_draft` — 404 (closes the file-serving inconsistency the P27 review flagged between `source_file` and `artifact_image`).
5. `projects_list()` for `user_a` shows `project_a`, never `project_b`.
6. `global_search()` for `user_a` matching a substring present in both projects' names returns only `project_a`.
7. `delete_project(project_b)` as `user_a` (even if somehow admin) — 404, not a silent no-op that could leak existence via timing/error-shape differences.
8. `dashboard(project_b)` redirect attempt by `user_a` — 404.
9. A user in **both** orgs (membership row in each) can open both projects — proves the membership check is additive, not exclusive.
10. Case-level privacy inside a project is unaffected: `user_a`'s own Private Case inside `project_a` is still invisible to a different `user_a2` who is also a member of `org_a` — proves the new project-level gate doesn't accidentally *widen* access relative to today's Case-level behavior.
11. `_reject_if_name_taken`'s org-scoped version: `org_a` and `org_b` can each have a project named "Phase 2 Expansion" without collision; two projects within the *same* org with that name still collide.
12. Backfill non-regression: after the migration's backfill runs, all three pre-existing accounts (admin, reader, workspacetester) and every pre-existing project remain mutually visible to each other (single default org) — proves the migration doesn't silently lock out existing legitimate access on the day it ships.

## 5. Open product decisions

These are the reasons this migration is not executed today — each is a genuine either/or with no engineering-only answer.

**Decision 1 — Does every user get an implicit personal organization, or is org membership only ever explicit (via invitation/admin action)?**
- *Implicit personal org*: every account always has somewhere to own a project, `upload()` never needs a fallback case, "operate without an organization" never arises as a state to handle. Cost: a "personal org of one" is a fiction that complicates the eventual Organization/Subscription billing story — is a personal org billable the same way an invited-team org is?
- *Explicit only*: cleaner mapping to real billing/team concepts later. Cost: `upload()` and the backfill both need a defined behavior for a user with zero memberships (reject the upload? block until admin assigns an org?) — a real gap that must be resolved before `upload()`'s fix in §2 can be written.

**Decision 2 — Can a project belong to more than one organization, or strictly one?**
- *Strictly one* (as modeled in §1's `ProjectOwnership`, `project_id` uniquely constrained): simpler queries, simpler `require_project_access`, matches how consulting/ownership usually works in this domain (one client's project). Cost: no native way to model a joint-venture project shared between two organizations without a separate cross-org sharing mechanism (analogous to Case-level `share_case`, one layer up) — not designed here.
- *Many-to-many*: matches joint-venture reality more directly. Cost: `require_project_access` becomes a membership-in-any-owning-org check rather than a single FK lookup, and `_reject_if_name_taken`'s org-scoping logic (§1) gets genuinely more complex to reason about (which org's namespace does a shared project's name occupy?).

**Decision 3 — How does the existing global project-name-uniqueness rule (`_reject_if_name_taken`) map onto org-scoped uniqueness for the 3 existing accounts?**
- §3's backfill design (one shared default org) makes this a non-question on day one — global and org-scoped uniqueness are identical while there's only one org. The real decision is deferred, not avoided: *when* a second real organization is created, does the system re-check the default org's existing names for new collisions against the new org (no — they're different orgs, no collision possible), or is there a data-cleanup step needed first? INFERRED no cleanup is needed given org-scoping is per-org from that point forward, but this should be explicitly confirmed against the real `_reject_if_name_taken` replacement before it ships, not assumed here.

**Decision 4 — Does `admin_required` bypass `require_project_access`, or does even an admin need org membership to reach a project?**
- *Admin bypasses*: matches today's behavior exactly (admin already has unrestricted access to every project) — lowest migration risk, preserves current admin workflows unchanged. Cost: this is exactly the "administrators see confidential content by default" question the P27 review flagged — deferring the decision here just re-defers the same open question, doesn't resolve it.
- *Admin also requires membership*: closes the gap properly, but is a genuine behavior change for the current sole admin account (would need to backfill admin into every org, or explicitly design a separate "platform support access" path, per the P27 review's already-deferred "structured support-access model"). This decision and that deferred item are the same open question; resolving one resolves the other.
