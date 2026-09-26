"""CLAUDE-SESSION-APPROVAL-SCOPE-01 - a "for this session" approval is keyed by
(action_class, project_id).

The Approval Gate's `confirm=session` used to store the bare action class, so
approving Apply in Project A silently approved Apply in every other project the
same login could reach - one approval crossing a project boundary. The gate's
three answers are unchanged:

    once     proceed for this request only; nothing is remembered
    session  proceed, and remember THIS action class for THIS project
    no       cancel; nothing is remembered

Two layers of proof. `_require_approval` itself is driven directly (a stand-in
for the confirmation page, and a plain dict for the session), which is what
isolates the key semantics. Then the real routes show that a stored approval is
never consulted before the project's own access and removal check - it cannot
reopen a removed project or reach one the caller may not open.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

CONFIRM_PAGE = "CONFIRM-PAGE"


class _GateCase(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app("testing")
        self.session = {}

    def gate(self, action_class, project_id, confirm=None):
        import routes.workspace as ws

        data = {"confirm": confirm} if confirm else {}
        with self.app.test_request_context("/gate", method="POST", data=data):
            with patch.object(ws, "session", self.session), \
                    patch.object(ws, "render_template", lambda *a, **k: CONFIRM_PAGE):
                return ws._require_approval(action_class, "Apply findings", project_id, "case-1")


class SessionApprovalIsProjectScoped(_GateCase):
    def test_1_session_approval_in_a_covers_a_second_matching_action_in_a(self):
        self.assertIsNone(self.gate("apply", "project-A", confirm="session"))
        self.assertIsNone(self.gate("apply", "project-A"))
        self.assertIsNone(self.gate("apply", "project-A"))

    def test_2_the_same_action_in_project_b_asks_again(self):
        self.gate("apply", "project-A", confirm="session")
        self.assertEqual(self.gate("apply", "project-B"), CONFIRM_PAGE)

    def test_3_approving_class_x_in_a_does_not_approve_class_y_in_a(self):
        self.gate("apply", "project-A", confirm="session")
        for other in ("rfi_issue", "work_product_issue", "source_revision"):
            with self.subTest(action_class=other):
                self.assertEqual(self.gate(other, "project-A"), CONFIRM_PAGE)

    def test_4_confirm_once_is_one_use_only(self):
        self.assertIsNone(self.gate("apply", "project-A", confirm="once"))
        self.assertEqual(self.gate("apply", "project-A"), CONFIRM_PAGE)
        self.assertEqual(self.session, {}, "once must remember nothing")

    def test_5_confirm_no_cancels_and_approves_nothing(self):
        response = self.gate("apply", "project-A", confirm="no")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.gate("apply", "project-A"), CONFIRM_PAGE)
        self.assertNotIn("approved_project_actions", self.session)

    def test_an_unconfirmed_request_still_pauses(self):
        self.assertEqual(self.gate("apply", "project-A"), CONFIRM_PAGE)

    def test_a_bare_class_approval_from_before_this_change_is_not_honoured(self):
        """An old session carries `approved_action_classes = ["apply"]`. It
        must not approve anything now - it is asked for again, per project."""
        self.session["approved_action_classes"] = ["apply", "rfi_issue"]
        self.assertEqual(self.gate("apply", "project-A"), CONFIRM_PAGE)

    def test_the_stored_approval_names_the_project_and_the_class(self):
        self.gate("apply", "project-A", confirm="session")
        self.gate("rfi_issue", "project-B", confirm="session")
        self.assertEqual(self.session["approved_project_actions"],
                         [["project-A", "apply"], ["project-B", "rfi_issue"]])


def _fake_parse(_self, raw, filename):
    from services.bhive_parser import ParsedDocument

    return ParsedDocument(project_id=str(uuid.uuid4()), filename=filename,
                          ingested_at=datetime.now(timezone.utc).isoformat(),
                          parser_version="test", text_extraction_status="no_native_text")


class StoredApprovalNeverReopensAProject(unittest.TestCase):
    """6 - a removed or inaccessible project cannot reuse a stored approval.

    Every gated route loads its project through `_load_workspace_or_404`
    (access, then removal) BEFORE `_require_approval`. These requests carry an
    approval for exactly that project and action class, in both the current
    and the retired session keys, and are still refused."""

    PW = "Scope!2026x"

    def setUp(self):
        from app import create_app
        from models import ROLE_CUSTOMER, User, db
        from werkzeug.security import generate_password_hash

        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_approval_scope_"))
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for name in ("scope_owner", "scope_other"):
            if not User.query.filter_by(username=name).first():
                user = User(username=name, role=ROLE_CUSTOMER)
                user.password_hash = generate_password_hash(self.PW)
                db.session.add(user)
        db.session.commit()

    def tearDown(self):
        from models import db

        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def client(self, name):
        c = self.app.test_client()
        c.post("/login", data={"username": name, "password": self.PW})
        return c

    def project_with_case(self, c):
        from PIL import Image
        from services.bhive_parser import BHiveParser
        from services.case_workspace import CaseWorkspaceStore

        buf = io.BytesIO()
        Image.new("RGB", (40, 30)).save(buf, "JPEG")
        with patch.object(BHiveParser, "parse", _fake_parse):
            r = c.post("/document-shop", data={"file": (io.BytesIO(buf.getvalue()), "a.jpg"),
                                               "name": "Scope " + uuid.uuid4().hex[:6]},
                       content_type="multipart/form-data")
        pid = r.headers["Location"].rstrip("/").split("/")[-1]
        store = CaseWorkspaceStore(str(self.tmp))
        workspace = store.get(pid)
        case = store.create_case(workspace, "Scope case", "objective", created_by="scope_owner")
        return pid, case["id"]

    def hold_approval(self, c, pid):
        with c.session_transaction() as sess:
            sess["approved_project_actions"] = [[pid, "apply"]]
            sess["approved_action_classes"] = ["apply"]

    def apply(self, c, pid, case_id):
        return c.post("/projects/%s/workspace/cases/%s/apply" % (pid, case_id), data={})

    def test_6a_a_removed_project_cannot_reuse_its_stored_approval(self):
        from services.case_workspace import CaseWorkspaceStore

        removed_notice = "This Project has been removed"
        owner = self.client("scope_owner")
        pid, case_id = self.project_with_case(owner)
        self.hold_approval(owner, pid)
        # Control: while the project is live the request reaches the route
        # (no eligible Findings here, so it returns before the gate - the
        # point is only that it is not refused as removed).
        live = self.apply(owner, pid, case_id)
        self.assertNotEqual(live.status_code, 404)
        self.assertNotIn(removed_notice, owner.get(live.headers.get("Location", "/")).get_data(as_text=True))

        store = CaseWorkspaceStore(str(self.tmp))
        workspace = store.get(pid)
        workspace.removed_at = datetime.now(timezone.utc).isoformat()
        store.save(workspace)
        # An authorized caller on a removed project is stopped by the loader
        # and sent to the one tombstone view (routes/workspace.py
        # _load_workspace_or_404) - before the gate, stored approval or not.
        removed = self.apply(owner, pid, case_id)
        self.assertEqual(removed.status_code, 302)
        self.assertIn("view=overview", removed.headers["Location"])
        self.assertIn(removed_notice, owner.get(removed.headers["Location"]).get_data(as_text=True))

    def test_6b_an_inaccessible_project_cannot_be_reached_with_a_stored_approval(self):
        owner = self.client("scope_owner")
        pid, case_id = self.project_with_case(owner)
        other = self.client("scope_other")
        self.hold_approval(other, pid)
        self.assertEqual(self.apply(other, pid, case_id).status_code, 404)


if __name__ == "__main__":
    unittest.main()
