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
