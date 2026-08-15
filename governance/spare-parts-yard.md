# Spare Parts Yard — Components Parked from an Active Surface

**Distinct from `deferred-reserved/reservations.md`** (gaps this project has
never designed) **and from `specified-unbuilt/`** (concepts fully designed but
never built). Everything named here was already built, working, tested code
that was deliberately unassigned from a user-facing surface — the code itself
still exists in git history at the commit named below; nothing here requires
re-implementation, only a decision about where it should be reachable again.

Lifecycle grammar (Product Owner, `CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01`):

- **Active** — deployed and assigned to a current surface.
- **Reserve / Spare Parts Yard** — useful capability or component preserved
  but not currently assigned to an active user-facing surface. *(this file)*
- **Prototype** — tested/experimental assembly.
- **Future** — sufficiently shaped future concept preserved for later
  promotion (→ `specified-unbuilt/`).
- **Scrap** — obsolete/disproven/unsafe and genuinely safe to delete.

Nothing in this file is Scrap. Every item below still has its real,
unmodified route and store method in the current codebase — only its
*visible entry point* was removed.

---

## 1. "+ Add Text Record"

- **Status:** Reserve / Spare Parts Yard.
- **Was:** a left-rail "Project Tools" subdisclosure form (title + freeform
  content → a real, governed `Source` of `kind="text_record"`).
- **Route (unchanged, still real):** `workspace.add_text_record_source`,
  `POST /projects/<project_id>/workspace/sources/text-record`.
- **Removed from:** `templates/base.html`'s rail, commit
  `CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01` (this stage).
- **Reason parked:** the left rail must remain a compact project/evidence
  navigation surface, not an action drawer — Product Owner: "the left rail
  is principally project switching + project/evidence navigation, not an
  action drawer or administration panel." Unlike "+ Add Documents," no
  decided new home (Admin/elsewhere) was named for this one specifically.
- **Promotion/reassignment trigger:** a later Product Owner decision
  establishing the correct surface for freeform-note evidence capture
  (candidates not yet evaluated: alongside Add Documents on Project Data
  Management; a GO-conversational intake path per
  `governance/specified-unbuilt/` future-intake work; its own dedicated
  surface).

## 2. "+ Register a Document Revision"

- **Status:** Reserve / Spare Parts Yard.
- **Was:** a left-rail "Project Tools" subdisclosure listing every
  revisable (non-drawing, non-superseded) active Source with a per-Source
  upload form to register a new revision.
- **Route (unchanged, still real):** `workspace.revise_document_source`,
  `POST /projects/<project_id>/workspace/sources/<source_id>/revise`.
- **Removed from:** `templates/base.html`'s rail, same commit as above.
- **Reason parked:** same rail-compactness rationale as Add Text Record
  above; no decided new home named this stage.
- **Promotion/reassignment trigger:** same as Add Text Record — a later
  Product Owner decision. Revision registration is closely related to
  Archive Documents (both are governed changes to the evidence set), so
  Project Data Management is a plausible future home, not yet decided.

## 3. "+ Add External Source"

- **Status:** Reserve / Spare Parts Yard — but already inert before this
  stage (worth naming honestly: there was no real capability behind this
  entry to protect). Its own content was always the static message "Not
  yet available — no external source connector is configured for this
  deployment" (`SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR` is a named enum
  value in `services/case_workspace.py`'s `KNOWN_SOURCE_ORIGIN_TYPES`, but
  nothing in this codebase has ever set it — confirmed during
  `CLAUDE-RFP27-TERRITORY-01`'s own Bug Eye governance research this same
  session).
- **Removed from:** `templates/base.html`'s rail, same commit as above.
- **Reason parked:** same rail-compactness rationale; recorded here for
  completeness of the historical "Project Tools" set, not because real
  functionality needs protecting.
- **Promotion/reassignment trigger:** whenever an actual external-source
  connector is built (a real future project, not scoped by this record).

## Not parked — promoted to a new Active home instead

For contrast, two former "Project Tools" items were **not** parked here —
the Product Owner named a real, decided new home for them:

- **"+ Add Documents"** → Active on Admin → Project Data Management
  (`templates/reset_project_data.html`'s own "Add documents to project"
  section), reusing the identical `workspace.add_document_source` route.
- **"Removed Items"** (view + restore already-archived Documents) →
  Active, merged into Project Data Management's own "Archive documents"
  section, reusing the identical `workspace.remove_document_route` /
  `workspace.restore_document_route` routes.

Both are now admin-gated (`portal.reset_project_data` is
`@admin_required`) where they were previously reachable by any authorized
project participant — a real, deliberate authorization narrowing that
follows directly from the Product Owner's own "belongs under Admin"
framing, not an oversight. See `CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01`'s
own commit message for the full record.

## "Files" — not parked, not retired, de-duplicated only

The left rail's own "Files" leaf was removed, but this is **not** a Spare
Parts Yard entry: the underlying capability (`workspace.show_workspace`'s
`?view=files` — the real, governed Data Room/Design-Builder folder view
built in `CLAUDE-RFP27-TERRITORY-01`) stays fully **Active**, reachable via
Overview's own independent, pre-existing `display.overview.files-link`
("Open Files →"). Removing the rail's own copy is de-duplication, not a
lifecycle change.
