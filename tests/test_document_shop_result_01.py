"""CLAUDE-DOCUMENT-SHOP-DOOR-01 - the customer door and the examination result.

What the live pre-flight found, pinned so it cannot return: Document Shop was
unreachable after a customer signed in, the customer was surrounded by the
Projects/CAD shell, and every upload landed on the analyst bench saying
"As-Read has not started on this source" with no action and no way back.

These tests assert the CUSTOMER-FACING contract. They deliberately do not
assert As-Read's own behaviour, which is unchanged and has its own tests.
"""
import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from models import ROLE_ADMIN, ROLE_CUSTOMER, User, db
from services import document_examination as dx
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore

PW = "TestCustomer!2026"


def _png(w=200, h=140):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (240, 240, 235)).save(buf, "PNG")
    return buf.getvalue()


def _fake_parse(_parser, raw_bytes, filename):
    """Deterministic stand-in - never the real extract/classify pipeline."""
    text = raw_bytes.decode("utf-8", errors="ignore")
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
        text_extraction_status="extracted" if text.strip() else "no_native_text",
    )


class DocumentShopResultTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_ds_result_"))
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for name, role in (("cust", ROLE_CUSTOMER), ("cust2", ROLE_CUSTOMER),
                           ("boss", ROLE_ADMIN)):
            if not User.query.filter_by(username=name).first():
                u = User(username=name, role=role)
                u.password_hash = __import__(
                    "werkzeug.security", fromlist=["x"]).generate_password_hash(PW)
                db.session.add(u)
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers ------------------------------------------------------------
    def _login(self, username="cust", client=None):
        c = client or self.client
        return c.post("/login", data={"username": username, "password": PW},
                      follow_redirects=False)

    def _upload(self, data=b"The contractor shall provide detection.\n",
                name="probe.txt", client=None):
        c = client or self.client
        with patch.object(BHiveParser, "parse", _fake_parse):
            return c.post("/document-shop", data={
                "file": (io.BytesIO(data), name), "name": "Probe job"},
                content_type="multipart/form-data", follow_redirects=False)

    # -- A. the customer can find the shop ----------------------------------
    def test_customer_signin_lands_on_their_documents_not_projects(self):
        r = self._login()
        self.assertEqual(r.status_code, 302)
        self.assertIn("/document-shop/jobs", r.headers["Location"])

    def test_admin_signin_still_lands_on_projects(self):
        r = self._login("boss")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/projects", r.headers["Location"])
        self.assertNotIn("document-shop", r.headers["Location"])

    def test_customer_gets_navigation_of_their_own(self):
        self._login()
        body = self.client.get("/document-shop/jobs").get_data(as_text=True)
        self.assertIn('data-ui-ref="shell.customer.documents"', body)
        self.assertIn('data-ui-ref="shell.customer.signout"', body)

    # -- B. the Projects/CAD shell is not wrapped around a customer ----------
    def test_customer_is_not_given_the_project_application_menu(self):
        self._login()
        body = self.client.get("/document-shop/jobs").get_data(as_text=True)
        for leak in ('data-ui-ref="menu.bar"', "New Project", "Add Document",
                     "Split View", "Undo Annotation", "Removed Projects"):
            self.assertNotIn(leak, body, "Project/CAD chrome shown to a customer: %r" % leak)

    def test_admin_keeps_the_application_menu(self):
        self._login("boss")
        body = self.client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.bar"', body)

    # -- C. accepted formats state the truth --------------------------------
    def test_intake_no_longer_claims_images_are_unsupported(self):
        self._login()
        body = self.client.get("/document-shop").get_data(as_text=True)
        self.assertNotIn("not accepted yet", body)
        self.assertIn(".png", body)
        self.assertIn(".jpg", body)

    def test_intake_still_refuses_spreadsheets_in_copy(self):
        self._login()
        body = self.client.get("/document-shop").get_data(as_text=True)
        self.assertNotIn(".xlsx", body)
        self.assertIn("spreadsheet cannot be the first document", body)

    # -- D. CSRF token is rendered server-side ------------------------------
    def test_upload_form_carries_a_server_rendered_csrf_field(self):
        """The failure this prevents reported itself as an expired session."""
        self._login()
        body = self.client.get("/document-shop").get_data(as_text=True)
        form = body[body.index("<form"):body.index("</form>")]
        self.assertIn('name="csrf_token"', form,
                      "upload form depends on JavaScript to supply its CSRF token")

    # -- E. upload lands on the RESULT, never the analyst bench --------------
    def test_upload_redirects_to_the_examination_result(self):
        self._login()
        r = self._upload()
        self.assertEqual(r.status_code, 302)
        self.assertIn("/document-shop/jobs/", r.headers["Location"])
        self.assertNotIn("understanding", r.headers["Location"])

    def test_result_page_is_not_the_analyst_bench(self):
        self._login()
        loc = self._upload().headers["Location"]
        body = self.client.get(loc).get_data(as_text=True)
        for term in ("As-Read", "Spin", "mark(s) recognised", "Vectorisation",
                     "View segmentation", "drawing grammar", "Sheet not established"):
            self.assertNotIn(term, body, "internal vocabulary shown to a customer: %r" % term)

    def test_result_page_always_offers_a_way_back(self):
        self._login()
        loc = self._upload().headers["Location"]
        body = self.client.get(loc).get_data(as_text=True)
        self.assertIn('data-ui-ref="document-shop.result.back"', body)
        self.assertIn("/document-shop/jobs", body)

    def test_result_names_what_was_established_and_what_was_not(self):
        self._login()
        loc = self._upload().headers["Location"]
        body = self.client.get(loc).get_data(as_text=True)
        self.assertIn('data-ui-ref="document-shop.result.established"', body)
        self.assertIn('data-ui-ref="document-shop.result.not-established"', body)

    def test_image_upload_reaches_a_result_too(self):
        self._login()
        r = self._upload(_png(), "scan.png")
        self.assertEqual(r.status_code, 302)
        body = self.client.get(r.headers["Location"]).get_data(as_text=True)
        self.assertIn('data-ui-ref="document-shop.result.state-label"', body)

    # -- F. job list ---------------------------------------------------------
    def test_job_list_shows_a_state_and_links_to_the_result(self):
        self._login()
        self._upload()
        body = self.client.get("/document-shop/jobs").get_data(as_text=True)
        self.assertIn('data-ui-ref="document-shop.jobs.state"', body)
        self.assertIn("/document-shop/jobs/", body)
        self.assertNotIn("understanding", body)

    # -- G. the boundary holds ----------------------------------------------
    def test_another_customer_cannot_open_the_result(self):
        self._login()
        loc = self._upload().headers["Location"]
        other = self.app.test_client()
        self._login("cust2", client=other)
        self.assertEqual(other.get(loc).status_code, 404)

    def test_an_anonymous_visitor_is_sent_to_sign_in(self):
        self._login()
        loc = self._upload().headers["Location"]
        anon = self.app.test_client()
        r = anon.get(loc, follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_a_real_project_is_not_viewable_through_the_customer_surface(self):
        """Scope, not just ownership: the two operating lines stay separate.

        A container with no container_state is an ordinary Project. Even for an
        ADMIN, who passes the access check on everything, the customer result
        surface must refuse it - otherwise the Project line acquires a
        customer-facing page by accident.
        """
        store = CaseWorkspaceStore(self.app.config["REGISTRY_STORE_PATH"])
        workspace = store.get_or_create(str(uuid.uuid4()))
        workspace.owner = "boss"
        store.save(workspace)
        self._login("boss")
        self.assertEqual(
            self.client.get("/document-shop/jobs/%s" % workspace.project_id).status_code,
            404, "a Project rendered through the customer result surface")

    def test_unknown_id_and_foreign_id_answer_identically(self):
        self._login()
        unknown = self.client.get("/document-shop/jobs/00000000-0000-0000-0000-000000000000")
        self.assertEqual(unknown.status_code, 404)


class ExaminationStateTests(unittest.TestCase):
    """state_of must derive from records, never invent a transition."""

    class _WS:
        def __init__(self, sources=None, units=None, regions=None):
            self.sources = sources or []
            self.structural_units = units or []
            self.addressable_regions = regions or []

    def _doc(self, **kw):
        base = dict(project_id="p", filename="f.txt", ingested_at="2026-09-09")
        base.update(kw)
        return ParsedDocument(**base)

    def test_no_source_cannot_complete(self):
        self.assertEqual(dx.state_of(self._doc(), self._WS()),
                         dx.STATE_COULD_NOT_COMPLETE)

    def test_no_document_cannot_complete(self):
        self.assertEqual(dx.state_of(None, self._WS([{"id": "s1"}])),
                         dx.STATE_COULD_NOT_COMPLETE)

    def test_recovered_text_is_a_result(self):
        ws = self._WS(
            [{"id": "s1"}],
            [{"id": "u1", "source_id": "s1", "unit_type": "page"}],
            [{"structural_unit_id": "u1", "content_type": "text", "content": "hello"}])
        self.assertEqual(dx.state_of(self._doc(), ws), dx.STATE_RESULT_READY)

    def test_nothing_recovered_needs_attention_rather_than_looking_finished(self):
        ws = self._WS([{"id": "s1"}])
        self.assertEqual(dx.state_of(self._doc(), ws), dx.STATE_NEEDS_ATTENTION)

    def test_there_is_no_fabricated_processing_state(self):
        """Examination is synchronous, so no record can support "processing"."""
        self.assertNotIn("processing", {v.lower() for v in dx.STATE_LABELS.values()})

    def test_an_unreadable_image_still_says_what_was_not_established(self):
        ws = self._WS([{"id": "s1", "name": "scan.png"}])
        result = dx.build_result(self._doc(filename="scan.png",
                                           text_extraction_status="no_native_text"),
                                 ws, display_name="Scan")
        labels = " ".join(i["label"] for i in result["not_established"])
        self.assertIn("No text could be read", labels)
        self.assertTrue(result["is_image"])


if __name__ == "__main__":
    unittest.main()
