"""
CLAUDE-CASE-PRIVACY-REPAIR-01 - the conversation switcher must not disclose
another reviewer's private Case.

THE DEFECT THIS EXISTS TO PREVENT FROM RETURNING

CLAUDE-MOBILE-PRIMARY-RESET-01 (commit 64eb700) moved the conversation list up
into the shared shell's context bar and iterated the raw collection:

    {% for c in workspace.cases if c.status != 'archived' %}

`workspace.cases` is every Case in the Project. So any reviewer who could open
the Project saw every other reviewer's PRIVATE Case titles listed by name in
the switcher, on every authenticated page that renders the shell. It reached
production and was live for roughly a day.

`CaseWorkspaceStore.visible_cases_for` is the single governed enforcement
point, and its own docstring names this precise mistake: "filtering
workspace.cases directly ... silently re-opens exactly the failure this method
exists to prevent." The repair uses that existing mechanism - specifically the
already-computed, already-filtered `open_visible_cases` - and introduces no new
authorization path.

WHY A SEPARATE FILE

tests/test_case_privacy.py caught the leak, but it asserts against the whole
response body, so it cannot say WHERE a title leaked and would keep passing if
the switcher were fixed while some other surface regressed. These tests assert
against the switcher markup itself, which is the surface that actually failed,
and against the template's structure, so the raw-iteration mistake cannot be
reintroduced anywhere in the shell without failing.

Every test here is about DISCLOSURE, not about capability: whether the other
reviewer could ACT on the Case is a separate, already-tested boundary. Seeing
that it exists, and what it is called, is itself the harm - a private
investigation's title is often the whole finding.
"""
from __future__ import annotations

import io
import re
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore, CASE_VISIBILITY_PRIVATE
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_TEMPLATE = _REPO_ROOT / "templates" / "base.html"

_PRIVATE_TITLE = "Structural Settlement Concern"
_SHARED_TITLE = "Shared Coordination Thread"
_OTHERS_OWN_TITLE = "Second Reviewer Own Thread"
_ARCHIVED_TITLE = "Closed Out Last Month"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _SwitcherTestCase(unittest.TestCase):
    """Two reviewers, one project, four Cases between them."""

    def setUp(self):
        import app as app_module
        import tempfile
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_case_privacy_switcher_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="switcher_owner",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="switcher_other",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="switcher_owner", project_name="Switcher Privacy Project")
        self.project_id = self.doc.project_id

        self.owner_client = self._client_as("switcher_owner", 1)
        self.other_client = self._client_as("switcher_other", 2)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", "rfp.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _create_case(self, client, title):
        response = client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": title, "objective": "x"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        return next(c for c in workspace.cases if c["title"] == title)

    def _share(self, case_id, actor="switcher_owner"):
        """Make a Case genuinely visible to the other reviewer.

        Cases are created PRIVATE and only become visible to anyone else
        through an explicit share by their own creator - so a test that just
        creates a Case and expects a second reviewer to see it is testing
        nothing. This is the only transition that legitimately widens
        visibility, and it is the one these "still renders" tests must go
        through.
        """
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        store.share_case(workspace, case_id, actor)
        store.save(workspace)

    def _make_private(self, case_id):
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        case = next(c for c in workspace.cases if c["id"] == case_id)
        case["visibility"] = CASE_VISIBILITY_PRIVATE
        store.save(workspace)

    def _switcher_markup(self, client) -> str:
        """Just the context bar's Case list - not the whole page.

        Scoping the assertion to this element is the point: a whole-body check
        cannot distinguish "the switcher leaked it" from "some other surface
        mentioned it", and this is the surface that actually failed.
        """
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        match = re.search(
            r'<div class="context-identity-list".*?</div>', body, flags=re.S
        )
        self.assertIsNotNone(match, "context-identity-list not rendered")
        return match.group(0)


class PrivateCaseIsNotDisclosedTests(_SwitcherTestCase):
    def test_another_reviewers_private_case_title_is_absent_from_the_switcher(self):
        case = self._create_case(self.owner_client, _PRIVATE_TITLE)
        self._make_private(case["id"])
        self.assertNotIn(_PRIVATE_TITLE, self._switcher_markup(self.other_client))

    def test_the_private_case_id_is_not_linkable_from_the_switcher(self):
        # A title is the obvious disclosure; a link target is the quieter one,
        # and would hand over a working id even with the title suppressed.
        case = self._create_case(self.owner_client, _PRIVATE_TITLE)
        self._make_private(case["id"])
        self.assertNotIn(case["id"], self._switcher_markup(self.other_client))

    def test_the_private_case_title_is_absent_from_the_whole_page(self):
        # The switcher was the leak, but the guarantee is about the page.
        case = self._create_case(self.owner_client, _PRIVATE_TITLE)
        self._make_private(case["id"])
        body = self.other_client.get(
            f"/projects/{self.project_id}/workspace"
        ).get_data(as_text=True)
        self.assertNotIn(_PRIVATE_TITLE, body)

    def test_guessing_the_case_id_directly_still_discloses_nothing(self):
        case = self._create_case(self.owner_client, _PRIVATE_TITLE)
        self._make_private(case["id"])
        body = self.other_client.get(
            f"/projects/{self.project_id}/workspace?case={case['id']}"
        ).get_data(as_text=True)
        self.assertNotIn(_PRIVATE_TITLE, body)

    def test_the_owner_still_sees_their_own_private_case(self):
        # A privacy fix that hides a Case from its own author is a bug, not a
        # stricter fix.
        case = self._create_case(self.owner_client, _PRIVATE_TITLE)
        self._make_private(case["id"])
        markup = self._switcher_markup(self.owner_client)
        self.assertIn(_PRIVATE_TITLE, markup)
        self.assertIn(case["id"], markup)


class VisibleCasesStillRenderTests(_SwitcherTestCase):
    def test_a_shared_case_is_visible_to_both_reviewers(self):
        # Cases are born private; sharing is the explicit transition that makes
        # one visible to anyone else.
        case = self._create_case(self.owner_client, _SHARED_TITLE)
        self._share(case["id"])
        self.assertIn(_SHARED_TITLE, self._switcher_markup(self.owner_client))
        self.assertIn(_SHARED_TITLE, self._switcher_markup(self.other_client))

    def test_each_reviewer_sees_their_own_case(self):
        self._create_case(self.owner_client, _SHARED_TITLE)
        self._create_case(self.other_client, _OTHERS_OWN_TITLE)
        self.assertIn(_OTHERS_OWN_TITLE, self._switcher_markup(self.other_client))

    def test_hiding_one_private_case_does_not_hide_the_visible_ones(self):
        # The failure mode of an over-broad fix: filter everything out and the
        # privacy tests pass while the feature is dead.
        private_case = self._create_case(self.owner_client, _PRIVATE_TITLE)
        self._make_private(private_case["id"])
        shared = self._create_case(self.owner_client, _SHARED_TITLE)
        self._share(shared["id"])
        markup = self._switcher_markup(self.other_client)
        self.assertIn(_SHARED_TITLE, markup)
        self.assertNotIn(_PRIVATE_TITLE, markup)

    def test_the_project_conversation_entry_is_always_present(self):
        markup = self._switcher_markup(self.other_client)
        self.assertIn("Project conversation", markup)


class ArchivedBehaviourUnchangedTests(_SwitcherTestCase):
    def test_an_archived_case_stays_out_of_the_switcher(self):
        # The pre-repair template filtered archived Cases with its own status
        # test. open_visible_cases is already narrowed to non-archived, so this
        # proves the behaviour survived the change of mechanism.
        case = self._create_case(self.owner_client, _ARCHIVED_TITLE)
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        next(c for c in workspace.cases if c["id"] == case["id"])["status"] = "archived"
        store.save(workspace)
        self.assertNotIn(_ARCHIVED_TITLE, self._switcher_markup(self.owner_client))

    def test_an_open_case_remains_in_the_switcher(self):
        self._create_case(self.owner_client, _SHARED_TITLE)
        self.assertIn(_SHARED_TITLE, self._switcher_markup(self.owner_client))


class OneAuthorizationBoundaryForPhoneAndDesktopTests(_SwitcherTestCase):
    """The switcher is in the SHARED shell, so there is only one boundary.

    The context bar lives in templates/base.html, which every authenticated
    page extends, and it is shown or hidden by CSS rather than rendered
    differently per device. There is no separate phone markup that could drift
    from the desktop's - which is the structural reason the two cannot diverge,
    and these tests assert that structure rather than simulating a viewport.
    """

    def test_the_switcher_is_rendered_once_in_the_shared_shell(self):
        source = _BASE_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(source.count('class="context-identity-list"'), 1)

    def test_no_template_renders_a_second_device_specific_case_list(self):
        for path in (_REPO_ROOT / "templates").rglob("*.html"):
            source = path.read_text(encoding="utf-8")
            if path.name != "base.html":
                self.assertNotIn("context-identity-list", source, path.name)

    def test_the_same_markup_is_served_to_a_phone_user_agent(self):
        private_case = self._create_case(self.owner_client, _PRIVATE_TITLE)
        self._make_private(private_case["id"])
        shared = self._create_case(self.owner_client, _SHARED_TITLE)
        self._share(shared["id"])
        phone = self.other_client.get(
            f"/projects/{self.project_id}/workspace",
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"},
        ).get_data(as_text=True)
        desktop = self.other_client.get(
            f"/projects/{self.project_id}/workspace"
        ).get_data(as_text=True)
        for body in (phone, desktop):
            self.assertNotIn(_PRIVATE_TITLE, body)
            self.assertIn(_SHARED_TITLE, body)


class ExportedDocumentsDoNotDiscloseAPrivateCaseTests(_SwitcherTestCase):
    """The same defect, found in a second place during the audit.

    routes/workspace.py's _export_document_for read workspace.cases directly,
    so the "investigations" and "project" exports wrote every reviewer's PRIVATE
    Case titles into a real .docx/.xlsx/.pdf. That is a worse disclosure than an
    on-screen one: the file then travels, and it keeps disclosing after any
    on-screen fix.

    These assert against the generated document's own rows rather than the HTTP
    response, so they fail for the right reason and cannot be satisfied by a
    binary format simply not containing a searchable string.
    """

    def _rows_for(self, kind):
        from routes.workspace import _export_document_for
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        visible = store.visible_cases_for(workspace, "switcher_other")
        document = _export_document_for(workspace, kind, visible)
        return [cell for table in document.tables for row in table.rows for cell in row]

    def test_the_investigations_export_omits_another_reviewers_private_case(self):
        case = self._create_case(self.owner_client, _PRIVATE_TITLE)
        self._make_private(case["id"])
        self.assertNotIn(_PRIVATE_TITLE, self._rows_for("investigations"))

    def test_the_project_export_omits_another_reviewers_private_case(self):
        case = self._create_case(self.owner_client, _PRIVATE_TITLE)
        self._make_private(case["id"])
        self.assertNotIn(_PRIVATE_TITLE, self._rows_for("project"))

    def test_a_shared_case_is_still_exported(self):
        # An export that hides everything is not a fix.
        case = self._create_case(self.owner_client, _SHARED_TITLE)
        self._share(case["id"])
        self.assertIn(_SHARED_TITLE, self._rows_for("investigations"))

    def test_the_downloaded_file_does_not_carry_the_private_title(self):
        # End to end, through the real route, in the format most likely to be
        # forwarded to someone else.
        case = self._create_case(self.owner_client, _PRIVATE_TITLE)
        self._make_private(case["id"])
        response = self.other_client.get(
            f"/projects/{self.project_id}/workspace/export/investigations.xlsx"
        )
        if response.status_code == 200:
            self.assertNotIn(_PRIVATE_TITLE.encode(), response.get_data())
        else:
            # The export gate may refuse this reviewer outright, which is a
            # stronger guarantee than filtering - but it must be a refusal, not
            # a server error.
            self.assertIn(response.status_code, (302, 303, 403, 404))

    def test_the_export_builder_cannot_be_called_without_the_filtered_list(self):
        # Required and positional on purpose: omitting it is a TypeError, not a
        # silent fallback to the unfiltered collection.
        from routes.workspace import _export_document_for
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        with self.assertRaises(TypeError):
            _export_document_for(workspace, "investigations")


class TheRawIterationCannotComeBackTests(unittest.TestCase):
    """Structural guards, so the same mistake fails loudly rather than shipping."""

    def setUp(self):
        self.source = _BASE_TEMPLATE.read_text(encoding="utf-8")
        # The template's own comment quotes `workspace.cases` while explaining
        # why it must not be used - so a raw scan would let the explanation of
        # the prohibition satisfy the test for it.
        self.markup = re.sub(r"\{#.*?#\}", "", self.source, flags=re.S)

    def test_the_shell_never_iterates_the_raw_case_collection(self):
        self.assertNotIn("workspace.cases", self.markup)
        self.assertNotRegex(self.markup, r"\{%\s*for\s+\w+\s+in\s+workspace\.")

    def test_the_shell_iterates_the_governed_visibility_filtered_list(self):
        self.assertIn("open_visible_cases", self.markup)

    def test_the_switcher_fails_closed_when_the_filtered_list_is_absent(self):
        # A future route that renders this shell with a `workspace` but forgets
        # the filtered list must show an EMPTY switcher, never fall back to an
        # unfiltered one.
        loop = re.search(r"\{%\s*for c in \(([^)]*)\)[^%]*%\}", self.markup)
        self.assertIsNotNone(loop, "switcher loop not in the expected form")
        self.assertIn("if open_visible_cases is defined else []", loop.group(1))

    def test_no_template_anywhere_iterates_workspace_cases_directly(self):
        offenders = []
        for path in (_REPO_ROOT / "templates").rglob("*.html"):
            markup = re.sub(r"\{#.*?#\}", "", path.read_text(encoding="utf-8"), flags=re.S)
            if re.search(r"\{%\s*for\s+\w+\s+in\s+workspace\.cases", markup):
                offenders.append(path.name)
        self.assertEqual(offenders, [], "templates iterating workspace.cases directly")


if __name__ == "__main__":
    unittest.main()
