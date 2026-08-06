"""
CLAUDE-P27-B: /api/v1/* previously had no authentication at all -- any
of its 9 routes (ingest/read/export) could be called with no
credential. This proves the fix: every route now rejects an
unauthenticated request, the write route additionally rejects a
non-admin authenticated user, and existing authenticated behaviour
(both roles, for the routes each role is meant to use) is unchanged.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.requirements_registry import RequirementsRegistry

# Every route in routes/api.py, paired with its HTTP method -- kept as
# one explicit list so a route added later and left out of this list
# is an obvious gap, and so the "every route rejects unauthenticated
# access" test can't silently drift out of sync with the blueprint.
API_ROUTES = [
    ("POST", "/api/v1/documents/ingest"),
    ("GET", "/api/v1/documents"),
    ("GET", "/api/v1/documents/some-project"),
    ("GET", "/api/v1/documents/some-project/requirements"),
    ("GET", "/api/v1/documents/some-project/milestones"),
    ("GET", "/api/v1/documents/some-project/consistency"),
    ("GET", "/api/v1/documents/some-project/governance"),
    ("GET", "/api/v1/documents/some-project/rfi"),
    ("GET", "/api/v1/categories"),
    # CLAUDE-MM1
    ("GET", "/api/v1/documents/some-project/structural-units"),
    ("GET", "/api/v1/documents/some-project/evidence"),
    ("GET", "/api/v1/documents/some-project/citations/some-region"),
    # CLAUDE-MM2
    ("POST", "/api/v1/documents/some-project/sources/some-source/pdf-structure"),
    # CLAUDE-MM3
    ("POST", "/api/v1/documents/some-project/sources/some-source/spreadsheet-structure"),
    ("POST", "/api/v1/documents/some-project/sources/some-source/spreadsheet-cell"),
    # CLAUDE-MM4
    ("POST", "/api/v1/documents/some-project/sources/some-source/drawing-structure"),
    ("POST", "/api/v1/documents/some-project/sources/some-source/drawing-regions"),
    ("GET", "/api/v1/documents/some-project/regions/some-region/evidence-sachet"),
    # CLAUDE-MM5
    ("POST", "/api/v1/documents/some-project/eye-capture"),
    ("POST", "/api/v1/documents/some-project/sources/some-source/markers"),
    ("POST", "/api/v1/documents/some-project/sources/some-source/derivative-crop"),
    # CLAUDE-MM6
    ("POST", "/api/v1/documents/some-project/relationships"),
    ("GET", "/api/v1/documents/some-project/relationships"),
    ("GET", "/api/v1/documents/some-project/relationships/some-relationship/status"),
    ("POST", "/api/v1/documents/some-project/relationships/some-relationship/confirm"),
    ("POST", "/api/v1/documents/some-project/relationships/some-relationship/dispute"),
    ("POST", "/api/v1/documents/some-project/relationships/some-relationship/reject"),
    ("POST", "/api/v1/documents/some-project/relationships/some-relationship/supersede"),
    ("GET", "/api/v1/documents/some-project/relationships/some-relationship/sachet"),
    ("GET", "/api/v1/documents/some-project/evidence/some-evidence/trust"),
    # CLAUDE-MM7
    ("POST", "/api/v1/documents/some-project/investigations"),
    ("GET", "/api/v1/documents/some-project/investigations/some-step/answer"),
    ("GET", "/api/v1/documents/some-project/investigations/some-step/sachet"),
    ("GET", "/api/v1/documents/some-project/claims/some-claim/status"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/accept-observation"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/accept-finding"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/dispute"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/reject"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/request-specialist"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/request-authority"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/supersede"),
]

# Admin-only write routes - excluded from "read_only can reach every read
# route" the same way "/documents/ingest" already was; kept as its own set
# (not string-matched ad hoc) so a future admin-only route added here can't
# silently fall through the read-only reachability check by accident.
#
# Keyed by (method, path), not path alone: CLAUDE-MM6's own POST
# /relationships (admin-only, create) and GET /relationships (read-only,
# list) share the same path with different methods - a path-only set would
# have silently skipped the GET route out of the read-only reachability
# check the moment the POST entry was added for the same path.
ADMIN_ONLY_ROUTE_PATHS = {
    ("POST", "/api/v1/documents/ingest"),
    ("POST", "/api/v1/documents/some-project/sources/some-source/pdf-structure"),
    ("POST", "/api/v1/documents/some-project/sources/some-source/spreadsheet-structure"),
    ("POST", "/api/v1/documents/some-project/sources/some-source/spreadsheet-cell"),
    ("POST", "/api/v1/documents/some-project/sources/some-source/drawing-structure"),
    ("POST", "/api/v1/documents/some-project/sources/some-source/drawing-regions"),
    ("POST", "/api/v1/documents/some-project/eye-capture"),
    ("POST", "/api/v1/documents/some-project/sources/some-source/markers"),
    ("POST", "/api/v1/documents/some-project/sources/some-source/derivative-crop"),
    ("POST", "/api/v1/documents/some-project/relationships"),
    ("POST", "/api/v1/documents/some-project/relationships/some-relationship/confirm"),
    ("POST", "/api/v1/documents/some-project/relationships/some-relationship/dispute"),
    ("POST", "/api/v1/documents/some-project/relationships/some-relationship/reject"),
    ("POST", "/api/v1/documents/some-project/relationships/some-relationship/supersede"),
    ("POST", "/api/v1/documents/some-project/investigations"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/accept-observation"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/accept-finding"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/dispute"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/reject"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/request-specialist"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/request-authority"),
    ("POST", "/api/v1/documents/some-project/claims/some-claim/supersede"),
}


class ApiAuthenticationTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_api_auth_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "some-project"

        document = ParsedDocument(
            project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00",
        )
        RequirementsRegistry(self.tmp_dir).save(document)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _anonymous_client(self):
        return self.flask_app.test_client()

    def _client_as(self, role, user_id=1, username="tester"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    # -- Unauthenticated: every route rejects, with no route omitted --

    def test_every_route_rejects_unauthenticated_requests(self):
        client = self._anonymous_client()
        for method, path in API_ROUTES:
            with self.subTest(method=method, path=path):
                response = client.open(path, method=method)
                self.assertEqual(
                    response.status_code, 401,
                    f"{method} {path} should reject an unauthenticated request with 401, "
                    f"got {response.status_code}",
                )
                self.assertEqual(response.get_json()["error"], "unauthorized")

    # -- Authenticated, wrong role: the one write route rejects read_only --

    def test_ingest_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/ingest")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_pdf_structure_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/sources/some-source/pdf-structure")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_spreadsheet_structure_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/sources/some-source/spreadsheet-structure")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_spreadsheet_cell_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/sources/some-source/spreadsheet-cell")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_drawing_structure_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/sources/some-source/drawing-structure")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_drawing_regions_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/sources/some-source/drawing-regions")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_eye_capture_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/eye-capture")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_markers_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/sources/some-source/markers")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_derivative_crop_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/sources/some-source/derivative-crop")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_create_relationship_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/relationships")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_confirm_relationship_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/relationships/some-relationship/confirm")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_dispute_relationship_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/relationships/some-relationship/dispute")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_reject_relationship_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/relationships/some-relationship/reject")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_supersede_relationship_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/relationships/some-relationship/supersede")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_create_investigation_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/investigations")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_accept_claim_as_observation_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/accept-observation")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_accept_claim_as_finding_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/accept-finding")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_dispute_claim_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/dispute")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_reject_claim_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/reject")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_request_claim_specialist_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/request-specialist")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_request_claim_authority_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/request-authority")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_supersede_claim_rejects_authenticated_non_admin(self):
        client = self._client_as("read_only")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/supersede")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    # -- Authenticated, correct role: existing behaviour is unchanged --

    def test_admin_can_reach_ingest_route(self):
        client = self._client_as("admin")
        # No file attached -- exercises that auth passes and the route's
        # own existing validation (not this fix) produces the 400, i.e.
        # authorization no longer blocks admins from this route at all.
        response = client.post("/api/v1/documents/ingest")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_upload")

    def test_admin_can_reach_pdf_structure_route(self):
        client = self._client_as("admin")
        # No such source -- exercises that auth/project-access pass and
        # the route's own existing validation produces the expected 400,
        # the same "reachable, not necessarily successful" shape
        # test_admin_can_reach_ingest_route already establishes above.
        response = client.post("/api/v1/documents/some-project/sources/some-source/pdf-structure")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_source")

    def test_admin_can_reach_spreadsheet_structure_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/sources/some-source/spreadsheet-structure")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_source")

    def test_admin_can_reach_spreadsheet_cell_route(self):
        client = self._client_as("admin")
        response = client.post(
            "/api/v1/documents/some-project/sources/some-source/spreadsheet-cell",
            json={"sheet_name": "Sheet1", "cell_ref": "A1", "value": "x"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_edit")

    def test_admin_can_reach_drawing_structure_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/sources/some-source/drawing-structure")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_source")

    def test_admin_can_reach_drawing_regions_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/sources/some-source/drawing-regions")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_region")

    def test_admin_can_reach_eye_capture_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/eye-capture")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_image")

    def test_admin_can_reach_markers_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/sources/some-source/markers")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_marker")

    def test_admin_can_reach_derivative_crop_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/sources/some-source/derivative-crop")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_crop")

    def test_admin_can_reach_create_relationship_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/relationships", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_relationship")

    def test_admin_can_reach_confirm_relationship_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/relationships/some-relationship/confirm")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_relationship")

    def test_admin_can_reach_dispute_relationship_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/relationships/some-relationship/dispute")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_relationship")

    def test_admin_can_reach_reject_relationship_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/relationships/some-relationship/reject")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_relationship")

    def test_admin_can_reach_supersede_relationship_route(self):
        client = self._client_as("admin")
        response = client.post(
            "/api/v1/documents/some-project/relationships/some-relationship/supersede",
            json={"to_type": "evidence_item", "to_id": "x", "relationship_type": "supports", "reason": "x"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_relationship")

    def test_admin_can_reach_create_investigation_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/investigations", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_investigation")

    def test_admin_can_reach_accept_claim_as_observation_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/accept-observation")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_claim")

    def test_admin_can_reach_accept_claim_as_finding_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/accept-finding", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_claim")

    def test_admin_can_reach_dispute_claim_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/dispute")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_claim")

    def test_admin_can_reach_reject_claim_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/reject")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_claim")

    def test_admin_can_reach_request_claim_specialist_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/request-specialist")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_claim")

    def test_admin_can_reach_request_claim_authority_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/request-authority")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_claim")

    def test_admin_can_reach_supersede_claim_route(self):
        client = self._client_as("admin")
        response = client.post("/api/v1/documents/some-project/claims/some-claim/supersede", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_claim")

    def test_read_only_can_reach_every_read_route(self):
        client = self._client_as("read_only")
        for method, path in API_ROUTES:
            if (method, path) in ADMIN_ONLY_ROUTE_PATHS:
                continue
            with self.subTest(method=method, path=path):
                response = client.open(path, method=method)
                self.assertNotEqual(
                    response.status_code, 401,
                    f"{method} {path} should be reachable by an authenticated read_only user",
                )
                self.assertNotEqual(response.status_code, 403)

    def test_categories_route_returns_data_for_authenticated_user(self):
        client = self._client_as("read_only")
        response = client.get("/api/v1/categories")
        self.assertEqual(response.status_code, 200)
        self.assertIn("categories", response.get_json())

    def test_unauthenticated_request_never_reaches_ingestion_logic(self):
        # Regression guard for the specific defect: an anonymous POST to
        # ingest must be rejected before any upload processing happens,
        # not merely produce a different error further down the stack.
        client = self._anonymous_client()
        response = client.post(
            "/api/v1/documents/ingest",
            data={"file": (tempfile.SpooledTemporaryFile(), "x.pdf")},
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
