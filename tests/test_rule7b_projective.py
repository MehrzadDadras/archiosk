"""Independent numeric oracles for Rule 7B in the existing compiler owner."""
import math
import copy

import pytest
from engine import spatial_compiler as geometry


SCOPE = dict(source_space="EUCLIDEAN_RECTIFIED", target_space="EUCLIDEAN_RECTIFIED",
             source_plane="sheet", target_plane="sheet", geometry_level="EUCLIDEAN")


class TestVectorUsability:
    def test_positive(self):
        result = geometry.vector_usability([3, 4], **SCOPE)
        assert result["value"] == [0.6, 0.8]
        assert result["length"] == 5

    @pytest.mark.parametrize("vector,error", [([0, 0], "ZERO_LENGTH_VECTOR"),
        ([1e-200, 0], "DEGENERATE_GEOMETRY"), ([math.inf, 1], "NON_FINITE_VECTOR"),
        ([1.7e308, 1.7e308], "NON_FINITE_DERIVED_VALUE")])
    def test_refusals(self, vector, error):
        result = geometry.vector_usability(vector, **SCOPE)
        assert result["error"] == error and result["value"] is None

    def test_frame_and_tolerance(self):
        assert geometry.vector_usability([1, 0], **dict(SCOPE, target_plane="other"))["error"] == "PLANE_MISMATCH"
        assert geometry.vector_usability([1, 0], **dict(SCOPE, geometry_level="AFFINE"))["error"] == "PREMISE_UNESTABLISHED"
        tol = geometry.ToleranceContext(vector_length=0.1)
        assert geometry.vector_usability([0.1, 0], tolerance=tol, **SCOPE)["state"] == "DEGENERATE"
        assert geometry.vector_usability([0.1001, 0], tolerance=tol, **SCOPE)["state"] == "ESTABLISHED"


class TestBoundedAcos:
    def test_positive(self):
        result = geometry.bounded_acos(0, 0, **SCOPE)
        assert result["state"] == "ESTABLISHED"
        assert result["value"] == [math.pi / 2, math.pi / 2]

    def test_boundary_uncertainty_is_not_a_scalar_clamp(self):
        value = math.nextafter(1, math.inf)
        result = geometry.bounded_acos(value, 1e-15, **SCOPE)
        assert result["state"] == "WEAK"
        assert result["value"][0] == 0 < result["value"][1]
        assert result["premises"]["input"] == value > 1
        assert result["uncertainty"]["conditional_on_domain"] is True

    @pytest.mark.parametrize("value,bound", [(2, 1e-15), (0, -1), (math.nan, 0)])
    def test_invalid_domain(self, value, bound):
        result = geometry.bounded_acos(value, bound, **SCOPE)
        assert result["error"] == "INVALID_NUMERIC_DOMAIN" and result["value"] is None

    def test_overflow_and_unearned_geometry(self):
        assert geometry.bounded_acos(1e308, 1e308, **SCOPE)["error"] == "NON_FINITE_DERIVED_VALUE"
        assert geometry.bounded_acos(0, 0, **dict(SCOPE, geometry_level="PROJECTIVE"))["error"] == "PREMISE_UNESTABLISHED"


IDENTITY = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


class TestHomographyValidation:
    def test_positive_and_homogeneous_scale(self):
        for scale in (1., -3., 1e-200, 1e200):
            result = geometry.validate_homography([[v * scale for v in row] for row in IDENTITY], **SCOPE)
            assert result["state"] == "ESTABLISHED"
            assert result["matrix"] == IDENTITY
            assert result["conditioning"] == pytest.approx(1)

    @pytest.mark.parametrize("matrix,error", [([[1, 0, 0], [0, 0, 0], [0, 0, 1]], "HOMOGRAPHY_SINGULAR"),
        ([[1, 0, 0], [0, 1e-12, 0], [0, 0, 1]], "HOMOGRAPHY_ILL_CONDITIONED"),
        ([[1, 0, 0], [0, math.inf, 0], [0, 0, 1]], "INVALID_HOMOGRAPHY")])
    def test_invalid_and_degenerate(self, matrix, error):
        result = geometry.validate_homography(matrix, **SCOPE)
        assert result["error"] == error and result["value"] is None

    def test_weak_conditioning_and_levels(self):
        result = geometry.validate_homography([[1, 0, 0], [0, 1e-9, 0], [0, 0, 1]], **SCOPE)
        assert result["state"] == "WEAK" and result["geometry_level"] == "AFFINE"
        assert geometry.validate_homography(IDENTITY, **dict(SCOPE, geometry_level="PROJECTIVE"))["geometry_level"] == "PROJECTIVE"
        assert geometry.validate_homography([[1, 0, 0], [0, 1, 0], [1, 0, 1]], **SCOPE)["geometry_level"] == "PROJECTIVE"
        assert geometry.validate_homography(IDENTITY, **dict(SCOPE, source_space="UNKNOWN"))["error"] == "SPACE_MISMATCH"


class TestDehomogenization:
    def test_positive_and_scale_invariance(self):
        for factor in (1., -7., 1e-200, 1e200):
            result = geometry.dehomogenize([2 * factor, 3 * factor, factor], **SCOPE)
            assert result["value"] == pytest.approx([2, 3])
            assert result["point_kind"] == "FINITE"

    @pytest.mark.parametrize("point,kind", [([0, 0, 0], "DEGENERATE"), ([1, 0, 0], "INFINITE"),
                                            ([1, 0, 1e-13], "NEAR_INFINITY"), ([1, 0, 1e-12], "NEAR_INFINITY")])
    def test_unusable_w(self, point, kind):
        result = geometry.dehomogenize(point, **SCOPE)
        assert result["value"] is None and result["point_kind"] == kind
        assert result["error"] == "DEHOMOGENIZATION_UNSTABLE"

    def test_invalid(self):
        assert geometry.dehomogenize([1, math.nan, 1], **SCOPE)["error"] == "NON_FINITE_POINT"
        assert geometry.dehomogenize([2, 3, 1], **dict(SCOPE, target_space="SOURCE_PIXELS"))["error"] == "SPACE_MISMATCH"
        assert geometry.dehomogenize([2, 3, 1], **dict(SCOPE, target_plane="other"))["error"] == "PLANE_MISMATCH"


class TestPointTransform:
    def test_positive(self):
        transform = geometry.validate_homography([[1, 0, 4], [0, 2, 5], [0, 0, 1]], **SCOPE)
        result = geometry.transform_homogeneous_point(transform, [2, 3, 1], point_space="EUCLIDEAN_RECTIFIED", point_plane="sheet")
        assert result["value"] == pytest.approx([6, 11])

    @pytest.mark.parametrize("space,plane,error", [("SOURCE_PIXELS", "sheet", "SPACE_MISMATCH"),
                                                  ("EUCLIDEAN_RECTIFIED", "facade", "PLANE_MISMATCH")])
    def test_scope(self, space, plane, error):
        transform = geometry.validate_homography(IDENTITY, **SCOPE)
        result = geometry.transform_homogeneous_point(transform, [2, 3, 1], point_space=space, point_plane=plane)
        assert result["error"] == error and result["value"] is None

    def test_at_infinity_and_singular(self):
        transform = geometry.validate_homography([[1, 0, 0], [0, 1, 0], [1, 0, -1]], **SCOPE)
        result = geometry.transform_homogeneous_point(transform, [1, 3, 1], point_space="EUCLIDEAN_RECTIFIED", point_plane="sheet")
        assert result["point_kind"] == "INFINITE" and result["value"] is None
        transform["matrix"] = [[1, 0, 0], [0, 0, 0], [0, 0, 1]]
        assert geometry.transform_homogeneous_point(transform, [1, 3, 1], point_space="EUCLIDEAN_RECTIFIED", point_plane="sheet")["error"] == "HOMOGRAPHY_SINGULAR"


def point_on(transform, point):
    return geometry.transform_homogeneous_point(transform, point,
        point_space=transform["source_space"], point_plane=transform["source_plane"])


class TestInverse:
    def test_round_trip_and_new_endpoints(self):
        transform = geometry.validate_homography([[2, 0, 4], [0, 3, 5], [0.01, 0, 1]],
            **dict(SCOPE, target_space="RECTIFIED_DISPLAY_PIXELS", target_plane="display"))
        before = copy.deepcopy(transform)
        inverse = geometry.invert_homography(transform)
        assert inverse["source_space"] == transform["target_space"]
        assert inverse["target_plane"] == transform["source_plane"]
        assert transform == before
        for original in ([2, 3, 1], [-1, 4, 1], [0, 0, 1]):
            forward = point_on(transform, original)["value"]
            restored = point_on(inverse, [*forward, 1])["value"]
            assert restored == pytest.approx(original[:2], abs=geometry.ToleranceContext().round_trip)
        assert inverse["conditioning"] == pytest.approx(transform["conditioning"])

    @pytest.mark.parametrize("middle", [0, 1e-12])
    def test_noninvertible(self, middle):
        transform = geometry.validate_homography([[1, 0, 0], [0, middle, 0], [0, 0, 1]], **SCOPE)
        assert geometry.invert_homography(transform)["state"] == "DEGENERATE"

    def test_weak_input_is_not_strengthened(self):
        transform = geometry.validate_homography(IDENTITY, **SCOPE)
        transform["state"] = "WEAK"
        assert geometry.invert_homography(transform)["state"] == "WEAK"


class TestComposition:
    def pair(self):
        first = geometry.validate_homography([[1, 0, 2], [0, 1, 0], [0, 0, 1]],
            **dict(SCOPE, source_space="SOURCE_PIXELS", target_space="NORMALIZED_IMAGE", target_plane="middle"))
        second = geometry.validate_homography([[2, 0, 0], [0, 2, 0], [0, 0, 1]],
            **dict(SCOPE, source_space="NORMALIZED_IMAGE", target_space="AFFINE_RECTIFIED", source_plane="middle", target_plane="output"))
        return first, second

    def test_order_is_h2_h1(self):
        first, second = self.pair()
        composed = geometry.compose_homographies(first, second)
        assert point_on(composed, [1, 3, 1])["value"] == pytest.approx([6, 6])
        assert composed["source_space"] == "SOURCE_PIXELS" and composed["target_plane"] == "output"

    def test_reversed_and_plane_mismatch(self):
        first, second = self.pair()
        assert geometry.compose_homographies(second, first)["error"] == "SPACE_MISMATCH"
        second["source_plane"] = "other"
        assert geometry.compose_homographies(first, second)["error"] == "PLANE_MISMATCH"

    def test_singular_operand_and_weak_operand(self):
        first, second = self.pair()
        first["state"] = "WEAK"
        assert geometry.compose_homographies(first, second)["state"] == "WEAK"
        second["matrix"][1] = [0, 0, 0]
        assert geometry.compose_homographies(first, second)["error"] == "HOMOGRAPHY_SINGULAR"


class TestLineTransform:
    def test_inverse_transpose_preserves_incidence(self):
        transform = geometry.validate_homography([[1, 0, 4], [0, 1, 5], [0, 0, 1]], **SCOPE)
        line = geometry.transform_homogeneous_line(transform, [1, 0, -2], line_space="EUCLIDEAN_RECTIFIED", line_plane="sheet")
        assert line["value"] == pytest.approx([1 / 6, 0, -1])
        for point in ([2, 0, 1], [2, 3, 1]):
            mapped = point_on(transform, point)["value"]
            assert sum(a * b for a, b in zip(line["value"], [*mapped, 1])) == pytest.approx(0, abs=1e-12)

    @pytest.mark.parametrize("line,error", [([0, 0, 0], "DEGENERATE_GEOMETRY"), ([1, math.inf, 0], "INVALID_LINE")])
    def test_degenerate_and_invalid(self, line, error):
        transform = geometry.validate_homography(IDENTITY, **SCOPE)
        assert geometry.transform_homogeneous_line(transform, line, line_space="EUCLIDEAN_RECTIFIED", line_plane="sheet")["error"] == error

    def test_scope_and_infinite_line(self):
        transform = geometry.validate_homography(IDENTITY, **SCOPE)
        assert geometry.transform_homogeneous_line(transform, [1, 0, 0], line_space="SOURCE_PIXELS", line_plane="sheet")["error"] == "SPACE_MISMATCH"
        assert geometry.transform_homogeneous_line(transform, [0, 0, 1], line_space="EUCLIDEAN_RECTIFIED", line_plane="sheet")["line_kind"] == "INFINITE"


class TestVanishingDirection:
    def direction(self, degrees):
        angle = math.radians(degrees)
        return [math.cos(angle), 0., math.sin(angle)]

    @pytest.mark.parametrize("degrees,kind,state", [(0, "INFINITE", "ESTABLISHED"),
        (0.25, "INFINITE", "DEGENERATE"), (0.251, "NEAR_INFINITY", "DEGENERATE"),
        (1, "FINITE", "WEAK"), (90, "FINITE", "ESTABLISHED")])
    def test_angular_bands_and_finite_conditioning(self, degrees, kind, state):
        result = geometry.classify_vanishing_direction([0, 0, 1], self.direction(degrees), **SCOPE)
        assert result["direction_kind"] == kind and result["state"] == state
        assert result["finite_vp"] is None  # No station point or plane origin invented.
        assert result["exact_parallel"] == (degrees == 0)

    def test_condition_boundaries(self):
        for condition, state in ((19.9, "ESTABLISHED"), (20., "WEAK"), (99.9, "WEAK"), (100., "DEGENERATE")):
            dot = 1 / condition
            result = geometry.classify_vanishing_direction([0, 0, 1], [math.sqrt(1 - dot * dot), 0, dot], **SCOPE)
            assert result["conditioning"] == pytest.approx(condition)
            assert result["state"] == state

    def test_degenerate_and_unearned_metric(self):
        assert geometry.classify_vanishing_direction([0, 0, 0], [1, 0, 0], **SCOPE)["error"] == "ZERO_LENGTH_VECTOR"
        assert geometry.classify_vanishing_direction([0, 0, 1], [1, 0, 0], **dict(SCOPE, geometry_level="AFFINE"))["error"] == "PREMISE_UNESTABLISHED"


class TestHorizonResidual:
    @pytest.mark.parametrize("residual,state", [(0, "ESTABLISHED"), (0.001, "ESTABLISHED"),
        (0.001001, "WEAK"), (0.003, "WEAK"), (0.003001, "UNRESOLVED")])
    def test_thresholds(self, residual, state):
        result = geometry.classify_horizon_residual(residual, residual_units="IMAGE_DIAGONAL", **SCOPE)
        assert result["state"] == state
        assert result["geometry_level"] == SCOPE["geometry_level"]

    def test_negative_unknown_units_and_plane_mismatch(self):
        assert geometry.classify_horizon_residual(-1, residual_units="IMAGE_DIAGONAL", **SCOPE)["error"] == "INVALID_NUMERIC_DOMAIN"
        assert geometry.classify_horizon_residual(0.001, **SCOPE)["error"] == "PREMISE_UNESTABLISHED"
        assert geometry.classify_horizon_residual(0.001, residual_units="IMAGE_DIAGONAL", **dict(SCOPE, target_plane="other"))["error"] == "PLANE_MISMATCH"


def test_every_operator_result_keeps_scope_tolerance_and_uncertainty():
    uncertainty = {"state": "WEAK", "sigma": 0.03}
    transform = geometry.validate_homography(IDENTITY, uncertainty=uncertainty, **SCOPE)
    for result in (transform, geometry.invert_homography(transform), point_on(transform, [2, 3, 1])):
        for field in ("source_space", "target_space", "source_plane", "target_plane", "geometry_level",
                      "conditioning", "uncertainty", "tolerance_context"):
            assert field in result
        assert result["uncertainty"] == uncertainty
