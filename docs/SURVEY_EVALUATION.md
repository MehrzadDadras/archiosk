# Survey Evaluation

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
