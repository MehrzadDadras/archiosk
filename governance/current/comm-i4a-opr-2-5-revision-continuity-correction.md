# OPR-2.5 Revision Continuity Corrective Tranche (CLAUDE-POSTCAMEL-COMM-I4A)

**Status: OPR-2.5 CORRECTED — PRODUCT OWNER REASSESSMENT REQUIRED.**
Authorized by the Product Owner's own explicit **DO NOT ACCEPT** decision
on the COMM-I4 residual
(`governance/current/comm-i4-foundational-integrity-commissioning-assessment.md`,
commit `6289b12`): OPR-2.5 (Revision Tracking) remained **PARTIALLY
SATISFIED — UNRESOLVED DEVELOPMENTAL DEFICIENCY** because formal Source
revision/supersession was limited to drawings while the adopted
Current-Baseline requirement applies to document supersession
generally. This is the first COMM-stage to change application code —
every prior COMM stage (A1 through I4) was investigation/governance
only.

---

## A. Starting repository/product state

`HEAD == origin/main == 6289b12` confirmed before this stage began;
working tree clean except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture. The
adopted OPR commissioning specimen (project
`0b743d80-13b0-4253-b411-9fa17ff11927`) was **not touched** by this
stage's own implementation or its live demonstration (Section 9's own
instruction) — a separate, disposable throwaway project was used
instead and permanently deleted afterward.

## B. Exact OPR-2.5 failure mechanism before correction

`CaseWorkspaceStore.register_source_revision` was the **only** call
site anywhere in the repository that ever set `supersedes_source_id`
(confirmed by repository-wide search, both at COMM-I4 and re-confirmed
here), and it hardcoded `kind=SOURCE_KIND_DRAWING` on every new revision
regardless of what was actually being revised, with `width`/`height`
required parameters meaningful only for raster images. Its only route,
`revise_source`, required an image file (`PIL.Image.open`) and a
`case_id`. Consequently, no non-drawing Source — a `project_document`,
an `rfq_rfp_document`, or a `text_record` — could be formally registered
as a revision of another Source at all; a "new version" of such a
document could only be added as a brand-new, structurally disconnected
Source with no supersession relationship recorded.

## C. Existing revision architecture reused/generalized

No new canonical store, no second Supersession mechanism, no Source
identity redesign. `register_source_revision`'s signature was changed
minimally:

- `kind: Optional[str] = None`, defaulting to **the old Source's own
  kind** — a revision of a `text_record` stays a `text_record`, a
  revision of a `project_document` stays a `project_document`; the
  pre-existing drawing call path is unaffected (it already resolves to
  `SOURCE_KIND_DRAWING` either way).
- `width`/`height` changed from required to `Optional[int] = None` —
  meaningful only for drawings/images, honestly absent otherwise, the
  same pattern every other optional `Source` field already uses.
- One new guard: revising a Source that has **already** been
  superseded now raises `CaseWorkspaceError` (`"...revise that Source
  instead"`) — prevents an accidental fork where an earlier revision
  in a chain gets a second, competing successor. This did not exist
  before for drawings either; it is a real, if small, hardening
  applied uniformly.
- The Supersession record, the `supersedes_source_id`/
  `superseded_by_source_id` pointers, and the per-Case `RevisionNotice`
  generation (with its `compare_region` image comparison) are all
  **unchanged** and reused exactly as before — the region-comparison
  loop is naturally inert for non-drawing kinds (it only ever
  considers Artifacts with a `crop`, which no non-drawing Source has),
  not specially branched around.

No second canonical truth store was created. No Source-identity field
was redesigned.

## D. Supported Source kinds after correction

Repository-grounded: exactly four `Source` kinds exist in this
codebase (`rfq_rfp_document`, `drawing`, `project_document`,
`text_record`). `drawing` retains its own, already-working,
already-tested `revise_source` route unchanged. The new
`revise_document_source` route (Section E) covers the other three —
`project_document`, `rfq_rfp_document`, `text_record` — uniformly,
since all three are file-backed Sources underneath (even a
`text_record` is written to a `.txt` file by `add_text_record_source`)
and the generalized store method does not need to know or care which
of the three it is revising. No revision semantics were manufactured
for a kind where they make no domain sense — drawing was deliberately
left on its own existing, already-correct path rather than folded in.

## E. Ordinary product workflow provided

A new route, `POST /projects/<project_id>/workspace/sources/<source_id>/revise-document`,
mirroring `revise_source` exactly in shape (same Approval Gate action
class `source_revision`, same "never replaces the old Source" framing,
same governance-log event) but for a document file instead of an
image, and **not** requiring a `case_id` — Source is project-scoped,
not Case-scoped, by its own docstring, so this route does not force a
Case context the way the drawing route's own historical design does.
A new "+ Register a Document Revision" control was added to the
existing "Project Tools" panel (`templates/base.html`), directly
alongside the pre-existing "+ Add Documents"/"+ Add Text Record"
controls it was modeled on — listing every non-drawing, not-yet-
superseded Source with its own file-upload form. No broader UI
redesign was undertaken; the sign-in/gateway visual reconciliation was
not touched.

## F. Historical Source/provenance preservation result

Verified both by regression test and by a real live demonstration
(Section H): when Source B supersedes Source A, Source A's `name`,
`file_path`, and file bytes are **never mutated** — only its own
`superseded_by_source_id` pointer is set. Source B receives its own
fresh `id` via `_new_id()`. The Supersession relationship is explicit
and queryable (`supersessions_for`). A `Requirement` already registered
against Source A **continues to cite Source A** after the revision —
it is never silently repointed at Source B. Historical evidence
continues to resolve to the exact version it was actually based on.

## G. Relocation-vs-revision distinction

**Preserved, not reopened.** As COMM-I4 already found and this stage
re-confirmed: no rename/relocate mutator exists for `Source.name`/
`file_path` anywhere in this codebase (`update_source_identity` never
touches either) — "moving or renaming the same Source" is not a
supported product operation today, drawing or otherwise, so it cannot
currently be confused with a revision through any real user action.
"A changed location is not a changed identity" therefore holds
trivially for the relocation side (the operation doesn't exist) and now
holds substantively for the revision side too (a genuine new revision
gets its own distinct identity and an explicit supersession link,
verified live for a non-drawing document for the first time this
stage).

## H. Non-drawing revision/addendum live demonstration

Performed against a real, disposable throwaway project (`COMM-I4A
Revision Demo (throwaway)`), never the adopted OPR commissioning
specimen, through the real running application (not a test-client
shortcut):

1. Created the throwaway project via the ordinary `/upload` flow.
2. Added a `project_document` Source, "Owner Specification, Revision A"
   (`owner_spec_rev_a.txt`, "Section 3.2: widgets shall be blue").
3. Registered a real Requirement (`SPEC-3.2`) citing Revision A.
4. Registered "Owner Specification, Revision B (Addendum 1)"
   (`owner_spec_rev_b.txt`, "Section 3.2: widgets shall be red") through
   the new `revise-document` route.
5. Confirmed directly against the live registry: Revision A's own
   `superseded_by_source_id` now points to Revision B; Revision B's
   `supersedes_source_id` points back to Revision A; **the SPEC-3.2
   Requirement still cites Revision A's own Source id**, unmigrated;
   both files remain on disk with their original, distinct, unaltered
   content ("blue" / "red").
6. Confirmed live in the browser: the Documents Listing shows all three
   Sources (founding document, Revision A, Revision B) as separate,
   inspectable entries; the "+ Register a Document Revision" control's
   eligible-source list correctly showed the founding document and
   Revision B, and correctly **excluded** the now-superseded Revision A.
7. The throwaway project was permanently deleted afterward
   (`POST /projects/<id>/delete`, confirmed removed from the registry
   directory) — the adopted OPR specimen was never touched.

## I. Tests and regression results

Nine new focused tests added
(`tests/test_comm_i4a_source_revision_generalization.py`):
store-layer non-drawing revision (kind preserved, `width`/`height`
absent), text-record-specific revision, historical-Source-never-
mutated/no-auto-migration, double-supersession rejection,
cross-project-supersession structural impossibility (a Source id from
a different project's own workspace is simply not found — the same
per-project storage partitioning COMM-I4 already verified for OPR-1.2),
a regression guard proving the pre-existing drawing call shape is
unaffected, and three route-level tests (real end-to-end revision
through the Flask test client, refusal for a drawing Source, rejection
of an unsupported extension). All nine pass. The pre-existing
`test_source_revision_creates_supersession_and_pointers_agree`
(`tests/test_foundation_batch_a.py`) — the only pre-existing test
exercising this method — was re-run unchanged and still passes,
confirming no regression to the drawing path.

Full suite: **2978 passed, 0 failed, 65 subtests passed** (30m09s). One
real, legitimate failure surfaced on the first full run — this
repository's own `test_p40vw7a_ui_reference_map.py::RegistryConsistencyTests::test_every_template_data_ref_has_a_registry_row`
correctly caught that the two new `data-ui-ref` values added to
`templates/base.html` (`lists.project.tools.revise-document`,
`lists.project.tools.revise-document.empty`) had no matching
`UI_REFERENCE_MAP.md` row — fixed by adding both rows following the
exact convention the adjacent `add-document`/`add-text-record` rows
already use, then the full suite was re-run clean.

## J. Developmental commissioning classification after correction

**Preserved historical finding, not rewritten:** OPR-2.5 was partially
implemented because the revision mechanism was conceived and
implemented at the drawing-specific grain and never generalized —
self-disclosed by MM2's own `governance/STATUS.md` row at ship time,
assessed against its governing OPR requirement for the first time only
at COMM-I4, and left uncorrected until the Product Owner's own explicit
Do-Not-Accept decision authorized this tranche.

**Classification after correction: Late Correction [DIRECT].** Not
"Timely Correction" — the gap was self-disclosed at MM2's own ship
time and remained open across every subsequent stage (MM3 through
COMM-I4) before being fixed here; "timely" would misrepresent how long
the known gap actually persisted. Not "Early-and-Sound Conception" —
the original design was genuinely incomplete for its own stated
purpose, not merely later refined. Both the original deficiency
(COMM-I4's finding) and this correction are preserved as two separate,
dated facts in the commissioning record — the deficiency is not edited
out of history now that it no longer describes the present.

## K. Agent reassessment of OPR-2.5

**AGENT REASSESSMENT — PRODUCT OWNER REVIEW REQUIRED: Satisfied.**
Formal revision/supersession is now available for every Source kind
this repository has (drawings via the pre-existing `revise_source`,
everything else via the new `revise_document_source`), through the
ordinary product, with historical identity and evidence preserved and
live-demonstrated for a realistic non-drawing addenda scenario. **No
new `RequirementAdjudication` was persisted on the Product Owner's
behalf** — this reassessment is offered for the Product Owner's own
review and decision, per this stage's own explicit instruction and
COMM-I3B's standing human-authority rule.

## L. Residuals/limitations

- The new UI control offers only file-upload revision, mirroring
  `add_document_source`'s own pattern — it does not additionally offer
  a text-content-entry form for revising a `text_record` the way
  `add_text_record_source` offers for creating one. A `text_record`
  revision is fully functional through file upload (proven by the
  dedicated regression test), just not through a second, dedicated
  text-entry form — a minor, honestly-reported UI-parity gap, not a
  capability gap.
- The pre-existing Approval Gate's confirm-page round-trip does not
  resurrect a file upload on a second POST (the confirm page only
  resubmits `confirm=once/session/no`, no file field) — this is a
  pre-existing characteristic of `revise_source` too, not introduced by
  this stage, and was worked around correctly (not silently) by
  submitting `confirm=session` alongside the file in one request, both
  in the live demonstration and in the regression test, exactly as a
  real user's first click of "allow this class of action for the rest
  of this session" would.
- `register_source_revision`'s `RevisionNotice`/`compare_region` path
  remains drawing-oriented in spirit (per-Artifact region comparison);
  it is harmlessly inert for non-drawing kinds rather than meaningfully
  adapted for them, since no non-drawing evidence-comparison concept
  currently exists to adapt it to.

## M. Commits / HEAD / origin/main / working tree

See the final chat report for exact values, recorded after this
document, the regression test file, and the `STATUS.md` row are
committed together.

## N. Recommendation on Product Owner confirmation

OPR-2.5 is ready for Product Owner reassessment from Partially
Satisfied to Satisfied, on the strength of: a generalized, tested,
live-demonstrated mechanism; preserved historical Source identity; no
auto-migration of existing evidence; and an honest developmental record
that keeps the original deficiency and its correction as two distinct,
dated facts rather than one rewritten history.

## O. Recommendation on the remaining 22 Requirements

Not begun automatically, per this stage's own explicit instruction.
Once the Product Owner confirms or overrides this reassessment, the
remaining 22 Requirements are the natural next tranche.
