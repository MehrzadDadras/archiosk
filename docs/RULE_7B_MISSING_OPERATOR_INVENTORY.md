# Rule 7B: projective / homography qualification inventory

Status: read-only mathematical and ownership inventory. No new mathematical
operator is implemented or promoted by the Rule 7 adapter tranche. The governing
contract remains [the accepted Rule 7 scope](SURVEY_GEOMETRY_PROOF_QUALIFICATION_SCOPE.md).

## Exact blockers in the 34-fixture map

| Fixture | Required operator | Existing nearest primitive | Why an adapter is insufficient |
|---|---|---|---|
| R7-FIN-ZERO-001 | Vector usability / normalization guard | `spatial_compiler.ToleranceContext`, guarded segment length inside `project_point_to_segment` | A segment projection is not a general vector operator. No qualified vector result contract exists. |
| R7-FIN-DOM-001 | Bounded inverse-trigonometric domain handling | `survey_graph.curve_constraints` uses `math.asin` after a chord/radius guard | That survey-specific scalar rule has no error-bound input or qualified generic `acos` result. |
| R7-FIN-DOM-002 | Invalid inverse-trigonometric domain refusal | Same as above; IFC `_numeric_derivation` translates arithmetic exceptions | An exception wrapper does not establish the required domain/uncertainty contract. |
| R7-FIN-TR-001 | Homography validation and point transform | `drawing_intelligence.transform_point_to_display/original`; `derived_view.to_view_coordinates/to_source_coordinates` | Existing display transforms are restricted rotation/mirroring operations, not arbitrary projective maps. |
| R7-FIN-TR-002 | Stable homogeneous dehomogenization | Numeric admission and finite-output guards | Finite homogeneous coordinates do not prove usable nonzero W or a stable affine point. |
| R7-FIN-TR-003 | Singular homography refusal | Numeric admission only | Finite matrix entries do not establish invertibility, conditioning, or a valid chart. |

These six are `BLOCKED_MISSING_OPERATOR`, not PASS, NOT_APPLICABLE, or failed
adapters. No blocked fixture traversed the evidence/IFC/Ask GO route. All six
remain visible in the machine-readable adapter report.

## Operator set and mathematical contracts to qualify

| Required operator | Mathematical contract | Nearest primitive / reuse limit | Qualification fixture | Dependencies |
|---|---|---|---|---|
| Vector usability | Distinguish exact zero, nonzero below calibrated tolerance, representable usable direction, and non-finite derivation; never silently normalize an unusable vector | Existing centralized tolerance and segment guards; no copy of their arithmetic into a competing library | R7-FIN-ZERO-001 plus exact zero and calibrated scale-equivalent controls | Explicit chart/plane; central tolerance context |
| Domain qualification | Domain and declared numerical error bound must both be validated; any recoverable boundary uncertainty stays weak; invalid domain refuses. No silent clamping | `curve_constraints` is a survey-only guard, not an equivalent | R7-FIN-DOM-001/002 plus threshold and negative-error-bound controls | Numeric admission; explicit uncertainty policy |
| Homography validation | Finite 3x3 matrix, compatible declared source/target planes and spaces; reject singular or unusably conditioned mappings; canonical scale must not confer evidentiary authority | No equivalent found in engine/services | R7-FIN-TR-001/003 plus ill-conditioned matrix and scale-equivalence controls | Matrix representation, centralized conditioning thresholds, earned geometry level |
| Point transform | Homogeneous column-vector convention `x' ~ H x`; finite intermediate arithmetic or structured refusal; no assumed affine chart at W=0 | Existing display transforms cannot supply projective semantics | R7-FIN-TR-001/002 plus finite-input overflow | Validated H; homogeneous point; dehomogenization |
| Dehomogenization | W must be nonzero and numerically usable relative to a qualified scale/tolerance; infinite/unstable points retain their weaker state | Strict numeric admission can be reused, but does not decide usability | R7-FIN-TR-002 plus just-above/below tolerance and homogeneous rescaling | Homogeneous scale convention; uncertainty and tolerance |
| Line transform | `l' ~ H^-T l`; point transforms must never be substituted for line transforms | No typed line/projective transform equivalent | New incidence-preservation and singular-matrix controls | Qualified inversion/transposition; line usability |
| Composition | For AB followed by BC, compose `H2 H1`; reject incompatible spaces/planes; validate resulting matrix and retain premises | No projective composition equivalent | New incompatible-chart and chain-vs-direct point/line controls | Validated transforms; explicit endpoints |
| Inversion | Return a new typed BA transform; refuse singular/ill-conditioned inversion and non-finite output | Display inverse is only the inverse of its restricted display transform | New forward/reverse point and line round trips | Conditioning contract; compatible charts |
| Image normalization | Reuse accepted centered, y-up, image-diagonal normalization contract; zero-size/degenerate image extent refuses | Acquisition already supplies image dimensions and handedness | New corner/center/handedness/degenerate-image controls | Image dimensions, numeric admission |
| Vanishing point / horizon | Separate finite and infinite direction states; explicit station, picture plane, world-up and plane scope; direction near parallel does not earn a remote finite point | Survey North and display rotation are not camera geometry | New level-corner, pitched-corner, shared-horizon and near-infinite controls from the accepted scope | Usable vectors/planes, line incidence, conditioning |

No new dependency, generic geometry library, camera-calibration subsystem, or
parallel evidence graph is approved by this inventory. Choose an existing
unpinned owner only after overlap review. Keep Rule 6 and protected datum logic
outside the implementation boundary.

## Qualification sequence

1. Establish types, spaces/planes, operator/version and tolerance/uncertainty
   semantics; record which existing owner each operator extends.
2. Write independent mathematical controls for the bounded operator set before
   implementation. Add missing controls rather than pretending the three current
   homography fixtures qualify line transforms, composition or inversion.
3. Classify each red control; implement only the qualified increment. Preserve
   weaker valid states and distinguish numerical precision from read/bind certainty.
4. Route results through the existing calculated EvidenceItem, AddressableRegion,
   reviewed relationships and trust projection qualified by the adapter tranche.
5. Reclassify a missing-operator blocker only after its operator and real consumers
   pass. Do not delete or silently retire the original fixture ID.

The current adapter tranche does not start production implementation of this
operator set. Claude live incorporation/proof remains a separate promotion gate.
