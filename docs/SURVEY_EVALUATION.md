# Survey Evaluation

This document records the original controlled-evaluation baseline. For the current
live-project observation, consumer admission, deterministic producers and deployed
proof, see [Survey runtime convergence](SURVEY_RUNTIME_CONVERGENCE.md). Statements
below about absent project selection or retained consumer bypasses describe that
earlier baseline; the convergence increment supersedes them. Controlled runs still
use isolated evaluation registries and never acquire customer authority.

Entry: `/admin/survey-evaluation`, also linked from Developer Tools.
Both the existing admin role and Developer Mode are required. The surface is
for Product Owner evaluation; it is not a public or customer workflow.

## Input and authority boundary

Every run has a separate `instance/survey_evaluation/<uuid>/registry` using the
existing `CaseWorkspaceStore`. The project key `evaluation` is local to that
registry, not a customer project. There is no project selector, import into a
customer registry, promotion endpoint, issued customer document, or external
action. Source PDFs, controlled graph premises and supplied matrices are
explicitly labelled EVALUATION_INPUT. Source pixels are actually examined for
title-block recovery and North measurement; supplied graph premises are not
misrepresented as automatic extraction from those pixels.

The review buttons invoke existing relationship confirmation and scoped change
review/application. Accepting a clause proposal does not apply it. Applying
revalidates scope, predecessor and authority. Missing predecessors remain
refused. A whole-source replacement requires its explicit whole-document
directive. These are evaluation assumptions in this registry only.

## Reachability

The catalog has 27 professional cases and all 34 versioned Rule 7 controls.
The latter reuse only controlled input payloads and the IFC candidate, never
their expected outcomes. The shared adapter in
`services/survey_evaluation_geometry.py` was extracted from the existing fixture
qualifier; both the qualifier and live evaluation call the same real owners.

| Capability | Existing owner invoked | Visible result |
|---|---|---|
| Read versus bind certainty | binding / survey_graph | separate input certainties, qualification and drawing tags |
| Situated unreadable identity | drawing_segmentation / sheet_identity | retained view, unresolved fields and region provenance |
| Historical/current/missing occurrence | measurement_genealogy / sheet_identity | retained earlier measurements, reviewed precedence, expected absent sheet and later arrival |
| Scoped supersession | package_muscles / change_application / CaseWorkspaceStore | proposal, human decision, revalidated EvidenceItem or explicit Source lineage |
| Subject containment | survey_graph.footprint_containment | inside versus unresolved open/unbound parcel |
| True North | survey_north.measure_north / resolve_true_north | measured pixels, applicable direction or conflicting refusal |
| Notation and curves | survey_graph bearing parsing / curve_constraints | parsed bearings, conditional arc family and unresolved placement |
| Access | reviewed access_interpretations | reviewed access role, without legal frontage inference |
| Height datum | height_datum_governance / independent planning_authority record | geometric observation versus reviewed governing evaluation datum |
| Numeric, boundary, polygon, projection | existing IFC and spatial compiler validators | finite/non-finite, degenerate, mismatch and governed refusal |
| Rule 7B | existing spatial_compiler kernel | H validation, point/line transform, inverse, composition, round trip, vanishing direction, horizon residual, vector/domain controls |
| Examination | document_examination.build_result | actual interpreted/not-established rows |
| Survey Reference | survey_reference.derive / resolved_plan / render_pdf / review_svg | real SVG and downloadable evaluation PDF |
| Ask GO | document_conversation.build_context / ask | exact prepared/sent context, provider proposal, deterministically admitted answer |
| IFC | IFCVolumeValidator.export_evidence and diagnostic export | compared governed/direct decisions; only currently admitted governed artifact downloadable |

## Existing evidence route

Source / StructuralUnit / AddressableRegion → supplied source EvidenceItem →
actual deterministic operator → calculated EvidenceItem → derived_from
relationships → persistence/reload → relationship review and trust/currentness →
project_geometry_evidence → examination rows → existing Ask GO context.

Rule 7B validation, inverse, composition, line, direction and residual results
now enter the same existing routing that already admitted point results.
Calculated dependencies are ordinary EvidenceItem relationships, not a second
evidence graph. No new context dictionary or alternate Ask GO was introduced.
The evaluation summary is an inspection view, not an authority record type.

Explicit H retains source/target space, planes, geometry level, conditioning,
tolerance context, uncertainty and operator premises. Default H translates a
point in EUCLIDEAN_RECTIFIED / sheet; it does not earn physical scale. Missing H
passes `None` to the real validator and retains its refusal. Singular,
ill-conditioned, infinity, space mismatch and projective-level controls remain
refusals where required. IFC tests admission of the supplied candidate; it does
not reconstruct a building from H.

## Bounded consumer repairs and retained discrepancies

* Computed drawing primitives retain existing weak binding as a visible tag and
  uncertainty; bearing labels use bound certainty, not reading alone.
* Rule 7B's additional completed operators are consumed by the existing
  calculated-evidence trust/examination path.
* Existing Ask GO still calls the configured provider. For calculated geometry,
  and for evaluation runs, generated prose cannot replace the deterministic
  examination statements. The proposed answer remains inspectable; only the
  admitted statements are issued. Provider unavailability remains explicit.
* Evaluation IFC downloads recheck current admission, including stale artifacts.
  Exported project labels and filenames identify evaluation-only output.

The direct IFC API remains intact for existing callers. Its differing decision
is visible in evaluation but its artifact is not served. Generic observation
prose, relative traverse calculations and the current Survey Reference stage-one
renderer remain inspectable limitations: a computed tag is not legal authority;
the renderer does not display every building/easement layer; unresolved curves
may use a visibly qualified straight placeholder. Raw observation text can still
enter ordinary conversations without a universal governed-conclusion primitive.
This increment does not claim the whole professional sequence is now enforced.

Qualified monument correspondence, occupation-versus-record reconciliation and
earned rectification estimation are explicitly CAPABILITY NOT YET IMPLEMENTED.
No estimator, camera calibration, physical-scale admission, or professional
certification primitive was invented.

## Qualification and deployment procedure

`tests/test_survey_evaluation.py` exercises all catalog cases, review/refusal,
isolation, actual rendering, authority, supersession, Ask GO admission, protected
routes and downloads. Existing Rule 7 map, projective, IFC, Survey Reference,
conversation, sheet identity and activation lanes remain regression gates.
The deployment gate is the full suite on the clean committed activation worktree.
The existing Nipigon suite requires its ignored rendered assets: generate them
with the unchanged `tools/render_nipigon_assets.py` from the retained source
drawings. These are test prerequisites, not Survey code or deploy payload.

`tools/verify_survey_evaluation_live.py` uses an existing maintainer-issued
verification-access URL from `ARCHIOSK_VERIFICATION_URL`. It runs Chromium against
HTTPS, verifies anonymous/admin-mode boundaries, invokes every catalog case,
checks real artifacts and a live Ask GO refusal, retains screenshots and a JSON
proof, then ends the verification session through the existing revocation route.
The token is not written into proof artifacts or logs.

Deploy only the exact qualified commit using `deploy/DEPLOYMENT.md`, preserving
the existing live code backup and persistent paths. No existing public/project
workflow is removed. The old direct IFC and generic prose paths are retained;
their broader replacement has not been qualified for retirement.
Preserve the live generated `static/nipigon/` directory as well as the standard
persistent-path exclusions; a Git archive intentionally does not contain it.

## Qualified deployment and live proof

* Preserved Survey stack: `727eb1074bdadca130efa7855832c742d1f0bfab`, pushed without
  unrelated working-tree changes.
* Application implementation and controlled deployment:
  `3dfe1f8849949122fca60e5d33fbe1f48af25e7a` (activation increment `71260c5`
  followed by token integration `3dfe1f8`).
* Focused geometry/activation gate: 416 passed. Correction/surface/prerequisite
  gate: 123 passed, 12 subtests. Contrast pairings passed.
* Authoritative full gate on the clean committed application tree: 9,494 passed,
  3 skipped, 10,022 subtests passed, 14 warnings, `PYTEST_EXIT=0`, 803.16 seconds.
  The initial full run was red on five absent ignored Nipigon assets and the
  new stylesheet's raw colors; both causes were qualified and corrected before
  this green run. No failing test was skipped or weakened.
* Exact exported archive SHA-256:
  `d7fa9f423a75efb2b8566f8565574310c124e91dcf2cd8a14e80b1eacd893abe`.
  All 1,118 deployed archive files outside preserved `.claude/` tooling state
  matched byte-for-byte. Git's declared CRLF archive conversion is distinct from
  raw Git blob bytes. Deployment dry run had zero deletions and zero protected
  path changes. All three services were active; public HTTPS health returned 200.
* Live Chromium proof: 61/61 catalog cases reached the actual surface and review
  path, including all 34 Rule 7 controls. Zero browser errors. Scoped clause and
  whole-document acceptance/application, missing-predecessor refusal/rejection,
  and missing-sheet arrival were exercised over HTTPS. Anonymous access returned
  302; authenticated admin without Developer Mode returned 403.
* The verification client initially omitted the HTTPS same-origin Referer on its
  API-driven form posts; existing CSRF protection correctly refused them. Only
  the local proof client was corrected. Application code and CSRF enforcement
  remained unchanged. This verification/documentation follow-up does not replace
  the qualified deployed application SHA above.
* The live provider-backed Ask GO control admitted the deterministic height
  refusal. The provider proposal and exact context remain inspectable. Temporary
  verification access was revoked; residue check found zero account rows.

Retained admin-only demonstrations (Developer Mode required):

* [Survey Reference](https://archiosk.com/admin/survey-evaluation/f3c0207c6e27495f844d8e37b9197150)
* [Explicit H and governed IFC](https://archiosk.com/admin/survey-evaluation/61272dd562cf47e5b76303aa3f31cdda)
* [No H refusal](https://archiosk.com/admin/survey-evaluation/c32a4420c8cd49a5a82d6c811ecacff1)
* [Ask GO height refusal](https://archiosk.com/admin/survey-evaluation/fde160a172af48cd95217b7fb6832d34)

Live proof artifacts are retained in the activation worktree's ignored
`instance/live-survey-3dfe1f8-referer/` directory. The prior live code/environment
is retained at `/var/www/archiosk-backup-a20fe3c-before-survey-3dfe1f8`.
Evaluation reachability is proven; automatic customer homography production,
professional certification and a universally enforced survey sequence are not
claimed.
