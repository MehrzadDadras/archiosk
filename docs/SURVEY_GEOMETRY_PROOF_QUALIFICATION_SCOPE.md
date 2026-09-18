# Accepted Rule 7 scope: Euclidean and projective proof

This records the Product Owner's expanded qualification contract. It is not a
promotion handoff, implementation claim, or permission to deploy. Rules 3–6
retain priority; shared geometry work may interrupt them only when required to
preserve their invariants. Milestone full gates remain after Rules 4, 8 and 12.

## Reuse and inventory before implementation

Inventory `survey_graph`, `deterministic_spatial`, `region_comparison`, drawing/
vector geometry, `derived_view` coordinate transforms and datum logic. For each
operator record its exact implementation, consumers, missing qualification and
drawing uses. Do not create another geometry library or parallel evidence graph.

Cover incidence/point-on-segment, containment/overlap, segment intersection and
uniqueness, closure, collinearity, parallelism, perpendicularity, angle, distance,
projection, midpoint, alignment, offset, radius/chord/arc, tangency and tolerant
equality. Qualify chains, not just isolated arithmetic: for example A parallel B
and C perpendicular A can establish C perpendicular B only in a compatible,
established Euclidean plane. Nearness does not establish containment; an open
boundary does not establish a parcel. Contradictory constructions produce
conflict, not an averaged construction.

## Proof record

Every conclusion must retain premises and their establishment state, source
evidence, deterministic operator/version, tolerance, coordinate spaces, plane,
result, exact/approximate/unresolved status, uncertainty and downstream
implications. Expose what follows, what does not follow, and the additional
premise needed for a stronger conclusion. Numerical precision cannot improve
read/bind certainty or confer authority.

Map the requested types onto existing equivalents before introducing any:
CoordinateSpace, PlaneScope, GeometryState, Point2, HPoint2, Direction2/3,
Line2, Segment2, Polygon2, VanishingPoint, Horizon, Homography2D,
MetricConstraint, GeometricPremise, DerivationRecord, ToleranceContext,
GeometryValidationError, GeometryOperationResult and RectificationResult.

## Projective conventions and earned geometry

Use homogeneous column vectors: points `x' ~ H x`; lines `l' ~ H^-T l`.
Never apply a point transform to a line or dehomogenize unstable/zero w.
With station S, picture-plane point P0 and unit normal n, world-up u:

- Picture plane: `n dot (X - P0) = 0`.
- Horizon plane: `u dot (X - S) = 0`; horizon line is its intersection with
  the picture plane. Horizontal world-direction VPs lie on that horizon.
- Projection: `t = n dot (P0-S) / n dot (X-S)`; projected point is `S+t(X-S)`.
- VP of direction v: `S + [n dot (P0-S) / n dot v] v`; zero denominator is
  an infinite direction, not an invented remote finite point.

Keep station point, cone of sight rays, picture/horizon planes, horizon line,
view pitch, principal direction families and finite/infinite VP states separate.
One/two/three finite principal VPs do not define the cone of vision. A level
corner view has vertical VP at infinity; a corner alone does not prove a
three-point view. Pitched views require their own evidence.

Normalize W by H source pixels using `cx=(W-1)/2`, `cy=(H-1)/2`,
`D=sqrt((W-1)^2+(H-1)^2)` and rows of T_img:
`[1/D,0,-cx/D]`, `[0,-1/D,cy/D]`, `[0,0,1]`.
Normalized coordinates are centered, y-up, in image-diagonal units.

Spaces: SOURCE_PIXELS -> NORMALIZED_IMAGE -> AFFINE_RECTIFIED ->
EUCLIDEAN_RECTIFIED -> optional WORLD_SCALED -> RECTIFIED_DISPLAY_PIXELS.
Each primitive and transform declares space and plane. Mismatch refuses as
INCOMPARABLE_COORDINATE_SPACES / SPACE_MISMATCH or PLANE_MISMATCH.

Geometric levels and minimum operator premises:

| Operation | Minimum level |
|---|---|
| Incidence, intersection | PROJECTIVE |
| Topological containment | PROJECTIVE, same plane, valid nonsingular region |
| Parallelism, midpoint, same-line ratio | AFFINE |
| Angle, perpendicularity, equal length | EUCLIDEAN |
| Physical length/area | METRIC_SCALED |

An established horizon earns affine rectification only. For safe nonzero c,
the canonical H_A has rows `[1,0,0]`, `[0,1,0]`, `[a/c,b/c,1]` and maps horizon
`(a,b,c)` to infinity by inverse transpose. Otherwise use a qualified general
basis transform or abstain.

Independent established orthogonality constraints `di^T G dj=0` must provide
sufficient rank and positive-definite symmetric G. Use M with `M^T M=G` for
metric rectification; `H_NE=H_M H_A`. Insufficient constraints retain affine
results. A proven physical length alone earns scale `s=L_real/L_E`; otherwise
Euclidean geometry remains up to scale, with no metres/feet.

Display mapping is separate: `H_forward=T_out H_S H_M H_A T_img`;
reverse is the ordered product of their inverses. Qualify round trips;
never manually undo individual coordinates. Compose AB then BC as `H2 H1`;
reject incompatible spaces/planes. Inversion creates a new typed BA transform.

Canonicalize H by H33 when stable, otherwise Frobenius norm; choose a stable
row-major sign. Compare transforms by effects on canonical points, not only
matrix entries. Preserve handedness and valid source regions.

## Tolerances, uncertainty and refusals

Centralize configurable thresholds in a reused or qualified ToleranceContext.
Starting calibration cases: 0.25-degree parallel/infinite band; 0.251 degrees
near-parallel/near-infinite; beyond 1 degree nonparallel/finite candidate.
Keep exact mathematical state separate from a tolerance-based approximation.
VP conditioning uses `1/abs(n dot unit(v))`, with starting boundaries 20 and
100; horizon residual uses image-diagonal normalization with boundaries .001
and .003. Boundary inclusivity must be pinned by fixtures, not scattered magic
constants. These are calibration starts, not universal production thresholds.

Handle zero vectors/segments, coincident/near-parallel lines, insufficient
families, remote VPs, unknown world-up, cropped convergence, unresolved lens
distortion and orthographic/axonometric inputs explicitly. One homography
rectifies one plane only: sheet, ground and separate facades cannot share an
unproven transform. No full camera-calibration subsystem without a demonstrated
need and reuse audit.

Preserve sigma/intervals, angle uncertainty, residuals and sample counts separately
from evidentiary read/bind certainty. Qualify uncertainty propagation (initially
Monte Carlo if suitable), classifying STABLE / WEAKLY_STABLE / UNSTABLE. A broad
transform family must not be presented as exact.

Stable validation codes must cover the user-specified categories: space/plane
mismatch; zero vectors/segments; invalid lines; points at infinity/unstable
dehomogenization; insufficient/degenerate VP evidence; unresolved/inconsistent
horizon; degenerate affine rectification; insufficient/contradictory metric
constraints or nonpositive metric tensor; singular/ill-conditioned homography;
unstable region; unresolved scale, handedness, or distortion; unestablished
premises and evidence conflict. Blocking a stronger claim retains weaker valid
results.

RectificationResult retains status, plane scope, image size/normalization, VPs,
horizon, all stage/composed homographies, metric constraints/rank, scale,
handedness, North reference, conditioning, uncertainty, valid region, premises,
unresolved items, warnings and errors. Partial statuses include PROJECTIVE_ONLY,
HORIZON_ESTABLISHED, AFFINE_RECTIFIED, AFFINE_WEAK, EUCLIDEAN_UP_TO_SCALE,
EUCLIDEAN_SCALED, UNRESOLVED and DEGENERATE.

## Required deterministic fixtures

Frontal cube; level corner; pitched-up/down corners; common horizon; infinite
and near-infinite VPs; insufficient families; rotated image; photographed planar
sheet; one orthogonality constraint (affine only); contradictory metric
constraints; proven scale; transform round trip; invalid composition; and a
region crossing a homography singularity. Expected mathematics must come from
deterministic qualification, not model behavior.

Support the survey programme without replacing it: rectification, topology,
closure, containment, arc families, frontage/centerline geometry and distinction
between distortion and discrepancy. Never infer ownership, zoning, legal
interest, regulatory authority or measurement precedence from geometry.

Every green capability requires its implementation commit, gates and Claude
Promotion Handoff; this scope record alone establishes no capability.

## Rule 7 reuse inventory after Rule 6 reconciliation

Baseline: Rule 6 implementation `f6b6ecc9e4be3ef3eeb5fdf93e0fab476e4c230e`,
handoff `b6d4a86`. Inventory is not qualification or production promotion.
The active lifecycle digest guard protects `services/datum_corroboration.py`
and `services/perception_worker.py`: **PROTECTED_DO_NOT_TOUCH**. Historical
whole-tree hash snapshots are evidence of prior runs, not permission to repin an
active verification record. No protected implementation is changed here.

| Operator/type | Existing implementation and current consumer | Geometry level / gap | Qualification fixture | Classification |
| --- | --- | --- | --- | --- |
| Point-on-line / segment | `deterministic_spatial._segments_cross` has local collinearity/on-segment arithmetic; `_distance_point_to_segment` supplies distance | Incidence is projective; distance is Euclidean; no typed public incidence proof | Interior, endpoint, collinear extension, zero segment | EXTEND_UNPINNED, reuse arithmetic |
| Segment intersection | `deterministic_spatial._segments_cross`, `_rings_cross`; planning `relate`, survey containment | Projective same-plane predicate; Boolean does not prove a unique intersection point | Proper crossing, shared endpoint, coincident overlap, near-parallel | REUSE_AS_IS predicate; unique-point result MISSING |
| Point/polygon containment | Spatial `_point_in_ring`, `_point_in_polygon`; compiler `point_in_polygon`; Rule 1 `footprint_containment` | Same-plane topology; boundary conventions differ and require explicit guards | Inside, outside, edge/vertex, concave exclusion, hole | REUSE_AS_IS spatial/Rule 1; qualify compiler before reuse |
| Polygon containment / overlap | `deterministic_spatial.relate`; GO-PDZ/planning consumers; `survey_graph.footprint_containment` | Provenance/CRS and boundary-tolerance gates already exist; do not fake a CRS for image coordinates | Crossing versus containment; near boundary; wrong CRS | REUSE_AS_IS |
| Closure / shared endpoints | `spatial_compiler.assemble_loops`; compiler spaces; `survey_graph.boundary_closure`, `solve_traverse` | Topological degree alone is not one simple closed parcel; metric traverse has stronger premises | Open chain, two disconnected loops, branch, self-crossing | REUSE_AS_IS bounded operators; stronger proof EXTEND_UNPINNED |
| Collinearity | Local orientation in `_segments_cross`; PDF vector endpoints | Exact predicate exists, typed tolerant relation absent | Collinear triple, small deviation, zero direction | EXTEND_UNPINNED |
| Parallelism | No general proof operator found | AFFINE required; raw pixel likeness insufficient | Established A parallel B; near-parallel band | MISSING |
| Perpendicularity / angle | `survey_graph._azimuth_of`, printed `_bearing`; `survey_north` angle reconciliation | These are survey/North semantics, not generic Euclidean angle proofs | A parallel B and C perpendicular A; weak/contested premise blocks consequence | MISSING generic operator; reuse semantic guards |
| Point-to-line/segment distance | `deterministic_spatial._distance_point_to_segment`; compiler helper of same name | Clamped segment distance exists, not infinite-line distance; declared Euclidean space needed | Foot inside, before endpoint, zero length | REUSE_AS_IS segment arithmetic behind guards |
| Projection / alignment | Compiler `_distance_point_to_segment` returns distance and along-segment position; `_host_wall` uses it | Euclidean projection; host heuristics are not proof of intended alignment | Interior foot versus endpoint clamp; candidate near two walls | REUSE_AS_IS arithmetic, not host inference |
| Midpoint / ratios | No general qualified operator found; Rule 6 retains documented reference only | AFFINE midpoint; image pixel midpoint not established survey midpoint | Affine transform preserves midpoint; projective one need not | MISSING |
| Offset / parallel locus | Compiler wall thickness is declared assumption, not observed offset | Euclidean constraints required; equal distances alone can select multiple loci | Same signed offset on one side; opposite-side counterexample | MISSING |
| Radius/chord/arc | `survey_graph.curve_constraints`; `build_primitives`; `_arc_from_chord_and_radius` refuses unrectified placement | Conditional Euclidean scalar family, no unique branch/placement | c <= 2r; impossible chord; weak binding; missing branch | REUSE_AS_IS |
| Tangency | No qualified general operator found | Euclidean, established circle and contact point | Radius perpendicular tangent; near contact does not prove tangency | MISSING |
| Tolerance-aware equality | Compiler `_key` rounding, spatial boundary tolerance, survey/North tolerances | Scope-specific policies, no shared numerical/evidence tolerance record | Threshold edges; changing units; numerical precision versus evidence | EXTEND_UNPINNED; ToleranceContext MISSING |
| Signed area / handedness | Compiler `signed_area`, `ensure_ccw`, y-up `lift`; PDF extractor supplies y-down coordinates | Orientation/topology versus Euclidean/physical area must be separated | Mirrored/rotated loop; no physical area without scale | REUSE_AS_IS |
| Display transform / inverse | `drawing_intelligence.transform_point_to_display/original`, rectangle variants; MM4 viewer; `derived_view.to_view_coordinates/to_source_coordinates` | Quarter-turn/mirror or rigid view transform only; not projective rectification | All existing rotation/mirror round trips; missing rotation refuses | REUSE_AS_IS |
| Pixel comparison | `region_comparison.region_to_pixel_box`, `compare_region`; drawing analysis | Pixel difference only; neither geometric correspondence nor metric proof | Cropping/rotation differences cannot establish geometry | REUSE_AS_IS within original scope |
| Vector acquisition | `PDFVectorExtractor.extract_document/_extract_page`; sheet vision and spatial compiler | PDF points and declared handedness exist; no observed geometry => legal geometry inference | Native lines versus scanned photograph | REUSE_AS_IS |
| Datum corroboration | `datum_corroboration.corroborate`, `record_corroborations`, `datum_register` | Provisional named-level correspondence only; no governing-datum authority | Same named datum/exact value; mismatch abstains | PROTECTED_DO_NOT_TOUCH |
| CoordinateSpace / PlaneScope / GeometryState | DerivedView has source/region/rotation/scale/North; vector page has coordinate system; spatial engine has CRS | No unified explicit earned projective/affine/Euclidean levels or plane-safe composition | Space/plane mismatch must refuse | EXTEND_UNPINNED existing view metadata; typed operation contract MISSING |
| Point2/HPoint2, directions, Line2, Segment2, Polygon2 | Existing tuples/dicts in vector, graph and spatial modules | Reuse coordinates; homogeneous state, explicit plane/space and infinity handling absent | Zero vectors; finite/infinite points; wrong plane | MISSING typed wrappers; no duplicate arithmetic library |
| GeometricPremise / DerivationRecord | EvidenceItem, AddressableRegion, relationship review, `explain_evidence_trust`, binding certainty | Reuse authority/trust and provenance; operator/version/tolerance/space derivation payload absent | Confirmed support plus active contradiction refuses proof | EXTEND_UNPINNED existing evidence substrate |
| VP / Horizon / Homography2D / MetricConstraint | No implementation found in services or engine | Full projective contract remains unqualified | Cube one-point, level corner two-point, pitched three-point, horizon consistency | MISSING |
| RectificationResult / transforms / validation errors | No equivalent found; display transforms are not an equivalent | Earn stages; retain weaker success; line inverse-transpose; typed composition | One orthogonality constraint, contradictory G, known length, round trip, singular region | MISSING |

Initial bounded qualification uses the existing compiler and test file, not a
second geometry library: inside/outside/edge/vertex label occurrence -> geometric
containment predicate -> actual compiled room binding. Exact edge evidence must
not earn strict containment. Existing `point_in_polygon` explicitly documents
that edge labels remain unbound; the control checks every edge/vertex and both
windings, then the real compiler consumer. This does not change Rule 1.

Boundary qualification update: the original 7-failure gate exposed an
IMPLEMENTATION_DEFECT, not a stale expectation. The existing compiler now owns
`classify_point_in_polygon` and a centralized `ToleranceContext`; its Boolean
wrapper admits only INSIDE. `SpatialCompiler.compile` retains explicit
label/space classifications, provenance and warnings. Focused controls: 49
passed. Affected compiler/document-binding lane: 243 passed, 18 subtests after
an explicitly recorded sandbox temporary-directory permission error. See
`GO_PROMOTION_HANDOFF_SURVEY_RULE_7_BOUNDARY.md`. This bounded component is locally
qualified, not the complete kernel and not LIVE_REACHABLE proof. The inventory's
missing general types/projective operations remain missing; the tolerance
context currently covers boundary exclusion only.

Polygon qualification update: `engine/ifc_volume_validator.py::polygon_region`
reuses that tolerance for region validity (area band = boundary distance times
perimeter). Closed zero-area/collinear/collapsed/self-intersecting candidates
refuse. IFC admission now independently rechecks semantic label binding and
retains unknown geometry premises. Final focused 78 passed (including native
vector/text premise propagation); compiler/IFC/document lane 152 passed,
6 subtests; boundary regressions 49 passed. See
`GO_PROMOTION_HANDOFF_SURVEY_RULE_7_POLYGON.md`. The existing IFC `_cross`,
`_segments_intersect`, and `_close` also belong in the reuse inventory; none is
a typed general proof API, and their older local epsilons are not new kernel
defaults. No protected datum, Rule 6, or boundary-classifier behavior changed.

Numeric admission update: the existing IFC validator now has `numeric_validity`
and a shared refusal boundary used before geometry, after relevant derivations,
and before STEP emission. NaN and both infinities never become measurements;
unknown/nonnumeric values are not coerced. Source/field/stage diagnostics retain
failure provenance. Focused 61 passed, affected lane 212 passed, polygon/boundary
regressions 79 passed. See `GO_PROMOTION_HANDOFF_SURVEY_RULE_7_NUMERIC.md` for
the combined-admission milestone full gate and promotion requirements. Finite
input remains insufficient to establish conditioning, geometry level or scale.

Further inventory findings to qualify before reuse: `derive_points_per_foot`
selects majority datum spacing with reported conflicts; that policy cannot be
imported as a generic uncontested-scale proof. `boundary_closure` reports node
degree gaps and does not by itself prove a connected simple ring. Existing
display rotation floors to quarter-turns by contract; it cannot normalize an
arbitrary photographed-sheet perspective. None of these observations authorizes
silently strengthening the existing operators or duplicating them elsewhere.
