"""
CLAUDE-P40-VW7A - Left Lists / Menu / Display / Toolbox / Chat UI
Reference Registry.

A purely additive, instrumentation-only stage: every control already
existed before this stage - a stable data-ui-ref="<id>" attribute was
added directly on the existing element (never a new wrapper, never a
behavioral change), plus one new reviewer/device-preference toggle
("UI Reference Mode") that overlays each data-ui-ref value as a small CSS
badge for inspection. UI_REFERENCE_MAP.md is the central registry this
and future stages (starting with CLAUDE-P40-VW7B) read/update.

Coverage: registry-vs-template consistency (every data-ui-ref in the
templates has a matching, non-duplicated, correctly-statused registry
row and vice versa), authorization-aware rendering of referenced
controls (admin-only/owner-only refs absent for an unauthorized
viewer), Sign-in/Gateway isolation (VW5 preserved - zero data-ui-ref
anywhere on either), the UI Reference Mode toggle and its CSS, and a
light no-behavior-change spot check (existing routes/counts unchanged)
- the full pre-existing suite is the real proof of that, not this
file.
"""
from __future__ import annotations

import io
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_CASE_WORKSPACE_HTML_PATH = _REPO_ROOT / "templates" / "case_workspace.html"
_MACROS_HTML_PATH = _REPO_ROOT / "templates" / "_macros.html"
_GATEWAY_HTML_PATH = _REPO_ROOT / "templates" / "gateway.html"
_GATEWAY_SHELL_HTML_PATH = _REPO_ROOT / "templates" / "gateway_shell.html"
_PROJECT_CHOOSER_HTML_PATH = _REPO_ROOT / "templates" / "project_chooser.html"
_LOGIN_HTML_PATH = _REPO_ROOT / "templates" / "login.html"
_UPLOAD_HTML_PATH = _REPO_ROOT / "templates" / "upload.html"
_UPLOAD_CONFIRM_HTML_PATH = _REPO_ROOT / "templates" / "upload_confirm.html"
_ERROR_HTML_PATH = _REPO_ROOT / "templates" / "errors" / "error.html"
_SECURITY_DEPARTMENT_HTML_PATH = _REPO_ROOT / "templates" / "security_department.html"
_PROJECTS_HTML_PATH = _REPO_ROOT / "templates" / "projects.html"
_REMOVED_PROJECTS_HTML_PATH = _REPO_ROOT / "templates" / "removed_projects.html"
_APP_PY_PATH = _REPO_ROOT / "app.py"
# CLAUDE-P40-VW9 (Governed Files Display and Project File Architecture):
# the first confirm_*.html template to ever carry a data-ui-ref (its own
# governing prompt's own explicit "confirmation choices" requirement) -
# confirm_remove_document.html/confirm_remove_project.html, the pre-
# existing precedent this template's own structure otherwise mirrors,
# were never added to this scanned list and so were never registered
# either; extending the scan here rather than leaving this template's
# own new refs silently unchecked.
_CONFIRM_DELETE_FOLDER_HTML_PATH = _REPO_ROOT / "templates" / "confirm_delete_folder.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_REFERENCE_MAP_PATH = _REPO_ROOT / "UI_REFERENCE_MAP.md"

_DATA_REF_RE = re.compile(r'data-ui-ref="([a-z0-9._\-]+)"')
# CLAUDE-P40-VW8-QA (Complete Root and Subfolder UI Reference Tagging):
# security_department.html passes its references as macro CALL
# ARGUMENTS (ui_ref='security.floor') - the actual data-ui-ref="..."
# attribute text only ever exists inside _macros.html's own macro
# bodies (accordion/subdisclosure), never literally in the calling
# template's own source, so _DATA_REF_RE alone can never find these.
# This second pattern catches the macro-argument shape directly (the
# literal string genuinely IS present in source, just not as an HTML
# attribute) - a real scan, not a hardcoded set like the Jinja-
# variable-constructed refs above/below need.
_MACRO_UI_REF_RE = re.compile(r"ui_ref=['\"]([a-z0-9._\-]+)['\"]")
# CLAUDE-P40-VW8-QA: a row's own FIRST CELL may name more than one
# data-ui-ref value (e.g. "`menu.appearance.all.light`,
# `menu.appearance.all.dark`, `menu.appearance.all.tinted`") rather
# than one row per combinatorial value - captures the whole cell now,
# _registry_rows() below expands every backtick-quoted token inside it
# against that one row's status, so a genuinely readable multi-value
# row is still exactly as machine-checked as a single-value one.
_REGISTRY_ROW_RE = re.compile(r"^\| (.+?) \|.*\| (active|retired) \|$", re.MULTILINE)
_REF_TOKEN_RE = re.compile(r"`([a-z0-9._\-]+)`")

# CLAUDE-P40-VW8-QA: the Appearance matrix constructs its own data-ui-ref
# VALUES from a Jinja loop variable (data-ui-ref="menu.appearance.
# {{ surface_key }}.{{ mode_key }}") - unlike every other pattern ref
# (a literal, static string reused across repeated instances), a plain
# regex over the template SOURCE can never recover the resolved values,
# since the source never contains them literally. Enumerated here from
# the exact same fixed (key, label) tuples base.html's own {% for %}
# loops iterate over, so registry-vs-template drift (e.g. a surface
# added to one but not the other) is still genuinely caught, not
# silently exempted.
_APPEARANCE_SURFACES = ("menu", "lists", "display", "toolbox", "chat")
# CLAUDE-P40-VW8-QA (Approved Theme Set) added Deep Forest as a 4th
# choice - "tinted" and "dark" stayed as the RETAINED ref suffixes for
# Midnight Blue/Black (label/palette revisions, not renumbering - see
# tokens.css's own comment); "deep-forest" is the one genuinely new one.
_APPEARANCE_MODES = ("light", "dark", "tinted", "deep-forest")
_APPEARANCE_DYNAMIC_REFS = {
    f"menu.appearance.{surface}.{mode}" for surface in _APPEARANCE_SURFACES for mode in _APPEARANCE_MODES
} | {f"menu.appearance.all.{mode}" for mode in _APPEARANCE_MODES} | {
    f"menu.appearance.{surface}" for surface in _APPEARANCE_SURFACES
}

# CLAUDE-P40-VW8-QA (Project-Creation Upload-Capacity Correction):
# errors/error.html's action link renders `data-ui-ref="{{ ui_ref }}"`
# - a Jinja variable, not a literal string, so (like the Appearance
# refs above) a plain regex over the template source can never recover
# it. app.py's own 413 handler is the one real call site that ever
# passes a non-None `ui_ref` - hardcoded here from that exact literal.
_ERROR_PAGE_DYNAMIC_REFS = {"errors.upload-too-large"}

# CLAUDE-P40-VW8-QA-R2A: found while adding this stage's own dynamic-ref
# handling for upload_confirm.html - templates/upload.html's Operating
# Environment radios (data-ui-ref="upload.operating-environment.
# {{ value }}") were ALREADY a Jinja-loop-constructed ref (added in the
# earlier upload-capacity stage) with no dynamic-ref registration of
# their own, so this consistency check had a silent blind spot for them
# the whole time - never actually verified. Fixed here, not carried
# forward as a known gap.
from services.environment_capabilities import OPERATING_ENVIRONMENT_LABELS as _OPERATING_ENVIRONMENT_LABELS  # noqa: E402

_UPLOAD_ENVIRONMENT_DYNAMIC_REFS = {
    f"upload.operating-environment.{value}" for value in _OPERATING_ENVIRONMENT_LABELS
}

# CLAUDE-P40-VW8-QA-R2A: templates/upload_confirm.html builds three
# data-ui-ref families from services/drawing_intake.py's own
# CANDIDATE_FIELDS loop variable (data-ui-ref="upload.confirm.field.
# {{ field_name }}" etc.) - a plain source regex can never recover
# these, same reasoning as _APPEARANCE_DYNAMIC_REFS above. Enumerated
# from the exact same fixed field-name tuple the template's own
# {% for %} loop iterates over.
from services.drawing_intake import CANDIDATE_FIELDS as _DRAWING_CANDIDATE_FIELDS  # noqa: E402

_UPLOAD_CONFIRM_DYNAMIC_REFS = {
    f"upload.confirm.field.{name}" for name in _DRAWING_CANDIDATE_FIELDS
} | {
    f"upload.confirm.field.{name}.input" for name in _DRAWING_CANDIDATE_FIELDS
} | {
    f"upload.confirm.field.{name}.evidence" for name in _DRAWING_CANDIDATE_FIELDS
}


def _all_template_refs() -> set[str]:
    refs: set[str] = set()
    for path in (
        _BASE_HTML_PATH, _CASE_WORKSPACE_HTML_PATH, _MACROS_HTML_PATH,
        _GATEWAY_HTML_PATH, _GATEWAY_SHELL_HTML_PATH, _PROJECT_CHOOSER_HTML_PATH,
        _LOGIN_HTML_PATH, _UPLOAD_HTML_PATH, _UPLOAD_CONFIRM_HTML_PATH, _ERROR_HTML_PATH,
        _SECURITY_DEPARTMENT_HTML_PATH, _PROJECTS_HTML_PATH, _REMOVED_PROJECTS_HTML_PATH, _APP_PY_PATH,
        _CONFIRM_DELETE_FOLDER_HTML_PATH,
    ):
        text = path.read_text(encoding="utf-8")
        refs |= set(_DATA_REF_RE.findall(text))
        refs |= set(_MACRO_UI_REF_RE.findall(text))
    refs |= _APPEARANCE_DYNAMIC_REFS
    refs |= _ERROR_PAGE_DYNAMIC_REFS
    refs |= _UPLOAD_CONFIRM_DYNAMIC_REFS
    refs |= _UPLOAD_ENVIRONMENT_DYNAMIC_REFS
    return refs


def _registry_rows() -> list[tuple[str, str]]:
    rows = []
    for first_cell, status in _REGISTRY_ROW_RE.findall(_REFERENCE_MAP_PATH.read_text(encoding="utf-8")):
        for ref in _REF_TOKEN_RE.findall(first_cell):
            rows.append((ref, status))
    return rows


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


# ---------------------------------------------------------------------------
# Registry-vs-template consistency (no live app needed).
# ---------------------------------------------------------------------------

class RegistryConsistencyTests(unittest.TestCase):
    def test_registry_file_exists_and_is_non_trivial(self):
        self.assertTrue(_REFERENCE_MAP_PATH.exists())
        self.assertGreater(len(_REGISTRY_ROW_RE.findall(_REFERENCE_MAP_PATH.read_text(encoding="utf-8"))), 40)

    def test_every_template_data_ref_has_a_registry_row(self):
        template_refs = _all_template_refs()
        registry_refs = {ref for ref, _status in _registry_rows()}
        missing = template_refs - registry_refs
        self.assertEqual(missing, set(), f"data-ui-ref values with no UI_REFERENCE_MAP.md row: {missing}")

    def test_every_active_registry_row_actually_exists_in_a_template(self):
        template_refs = _all_template_refs()
        registry_rows = _registry_rows()
        stale_active = [ref for ref, status in registry_rows if status == "active" and ref not in template_refs]
        self.assertEqual(stale_active, [], f"registry claims 'active' but no template renders it: {stale_active}")

    def test_no_duplicate_registry_rows(self):
        refs = [ref for ref, _status in _registry_rows()]
        duplicates = {ref for ref in refs if refs.count(ref) > 1}
        self.assertEqual(duplicates, set(), f"data-ui-ref documented more than once: {duplicates}")

    def test_no_duplicate_data_ref_kind_definitions_across_templates(self):
        # Not a uniqueness-of-instance check (repeating leaf patterns are
        # expected, by design - see UI_REFERENCE_MAP.md's own "a data-ui-ref
        # value identifies a KIND of control, not one instance" note).
        # This instead confirms every value found is well-formed
        # (matches the documented <surface>.<family>... scheme) rather
        # than a stray typo'd id. CLAUDE-P40-VW8-QA added two new
        # surfaces outside the original five (gateway/auth - see
        # UI_REFERENCE_MAP.md's own Gateway/Auth sections and Section
        # 4's "must work on Sign-in, Gateway... too" requirement).
        # CLAUDE-P40-EYE1 added "eye" - the new structural-scaffold pane
        # in the right column (see UI_REFERENCE_MAP.md's own "Right
        # column: Toolbox above Eye" section).
        for ref in _all_template_refs():
            self.assertRegex(
                ref,
                r"^(menu|lists|display|toolbox|chat|eye|shell|gateway|auth|upload|errors|"
                r"security|projects-directory|removed-projects)\.[a-z0-9._\-]+$",
                ref,
            )

    def test_ui_reference_mode_css_rule_exists(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".ui-reference-mode-active [data-ui-ref]", css)
        self.assertIn("content: attr(data-ui-ref);", css)


# ---------------------------------------------------------------------------
# Live-app rendering: authorization-aware presence of referenced controls.
# ---------------------------------------------------------------------------

class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw7a_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw7a_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="vw7a_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="vw7a_granted_reviewer", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="vw7a_owner", project_name="Riverside Terminal VW7A Reference Map")
        self.project_id = self.doc.project_id

        store = self._store()
        workspace = store.get(self.project_id)
        store.grant_project_access(workspace, username="vw7a_granted_reviewer", actor="vw7a_owner", actor_role="admin")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "rfp.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)


class RootFamilyReferencePresenceTests(_BaseTestCase):
    def test_root_family_refs_present_for_an_open_project(self):
        # CLAUDE-P40-VW7B, Section 3: "lists.projects" (the portfolio
        # root) and "lists.removed-projects" no longer render at all
        # while a Project is open - removed from this list, not just
        # left asserted-present incorrectly. See
        # OpenedProjectPortfolioRemovalTests below for the explicit
        # regression coverage of their absence.
        client = self._client_as("vw7a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for ref in (
            "lists.project.self", "lists.project.overview",
            "lists.project.documents", "lists.project.investigations", "lists.project.rfis",
            "lists.project.chats", "lists.project.tasks", "lists.project.tags", "lists.project.tools",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', body, ref)

    def test_menu_refs_present_on_every_authenticated_page(self):
        client = self._client_as("vw7a_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.brand"', body)
        self.assertIn('data-ui-ref="menu.account"', body)

    def test_document_and_investigation_leaf_refs_present(self):
        client = self._client_as("vw7a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Foundation Review", "objective": ""})
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.documents.leaf"', body)
        self.assertIn('data-ui-ref="lists.project.investigations.leaf"', body)

    def test_toolbox_and_display_refs_present_and_context_switches(self):
        client = self._client_as("vw7a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.panel"', body)
        self.assertIn('data-ui-ref="toolbox.empty"', body)
        self.assertIn('data-ui-ref="display.divisions"', body)
        self.assertIn('data-ui-ref="display.division"', body)

        source_id = self._store().get(self.project_id).sources[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.document"', body)
        self.assertNotIn('data-ui-ref="toolbox.empty"', body)

    def test_overview_leaf_projects_display_overview_ref(self):
        client = self._client_as("vw7a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn('data-ui-ref="display.overview"', body)

    def test_chat_refs_present(self):
        client = self._client_as("vw7a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for ref in ("chat.dock", "chat.thread", "chat.composer", "chat.selection-toolbar", "chat.tag-dialog", "chat.task-dialog"):
            self.assertIn(f'data-ui-ref="{ref}"', body, ref)


class AuthorizationAwareReferenceTests(_BaseTestCase):
    def test_admin_only_refs_absent_for_non_admin(self):
        # CLAUDE-P40-VW7B: lists.project.tools.data-management retired
        # and replaced by lists.system-data-management, relocated out of
        # the active Project's own "Project Tools" branch - Reset
        # Project Data resets EVERY Project in the deployment, not just
        # this one (see UI_REFERENCE_MAP.md's own retired-references
        # entry and templates/base.html's relocation comment).
        client = self._client_as("vw7a_granted_reviewer", 3, role="read_only")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="lists.new-project"', body)
        self.assertNotIn('data-ui-ref="lists.security"', body)
        self.assertNotIn('data-ui-ref="lists.system-data-management"', body)

    def test_admin_only_refs_present_for_admin(self):
        # CLAUDE-P40-VW7B, Section 3: "lists.new-project" ("+ New
        # Project") is one of the explicitly forbidden portfolio
        # controls inside an opened Project workspace - removed here
        # even for an admin, since Section 3 draws no admin exception.
        # lists.security/lists.system-data-management are admin TOOLS,
        # not portfolio Project-selection surfaces, and deliberately
        # stay reachable regardless of whether a Project is open.
        client = self._client_as("vw7a_admin", 4, role="admin")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="lists.new-project"', body)
        self.assertIn('data-ui-ref="lists.security"', body)
        self.assertIn('data-ui-ref="lists.system-data-management"', body)

    def test_remove_project_ref_owner_or_admin_only(self):
        client = self._client_as("vw7a_granted_reviewer", 3, role="read_only")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="lists.project.tools.remove-project"', body)

        owner_client = self._client_as("vw7a_owner", 1)
        owner_body = owner_client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.tools.remove-project"', owner_body)

    def test_outsider_gets_404_not_a_filtered_reference_map(self):
        from models import User, db
        with self.flask_app.app_context():
            db.session.add(User(username="vw7a_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()
        client = self._client_as("vw7a_outsider", 5, role="read_only")
        resp = client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(resp.status_code, 404)


class SignInGatewayIsolationTests(_BaseTestCase):
    # CLAUDE-P40-VW8-QA, Section 4: superseded the original "zero
    # data-ui-ref anywhere on Sign-in/Gateway" invariant - that stage
    # explicitly requires "Reference Mode... must work on Sign-in,
    # Gateway... where those surfaces are rendered" and names "Sign-in,
    # Gateway and existing-Project chooser" among the controls needing
    # their own references. auth.html/gateway_shell.html now carry
    # their own auth.*/gateway.* refs (see UI_REFERENCE_MAP.md's own
    # Auth/Gateway sections). What VW5 actually protects - and what
    # still holds, unchanged - is that neither page ever leaks any
    # WORKSPACE-SHELL content (Lists/Display/Toolbox/Chat), which is
    # what these two tests check for directly now.
    def test_sign_in_page_has_no_workspace_shell_refs(self):
        client = self.flask_app.test_client()
        body = client.get("/login").get_data(as_text=True)
        for ref in _DATA_REF_RE.findall(body):
            self.assertFalse(
                ref.startswith(("lists.", "display.", "toolbox.", "chat.", "menu.")),
                f"Sign-in leaked a workspace-shell reference: {ref}",
            )
        self.assertIn("data-ui-ref=\"auth.signin.username\"", body)

    def test_gateway_page_has_no_workspace_shell_refs(self):
        client = self._client_as("vw7a_owner", 1)
        body = client.get("/gateway").get_data(as_text=True)
        for ref in _DATA_REF_RE.findall(body):
            self.assertFalse(
                ref.startswith(("lists.", "display.", "toolbox.", "chat.", "menu.")),
                f"Gateway leaked a workspace-shell reference: {ref}",
            )
        self.assertIn("data-ui-ref=\"gateway.open-existing\"", body)


class UIReferenceModeToggleTests(_BaseTestCase):
    def test_toggle_present_unchecked_by_default(self):
        client = self._client_as("vw7a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="ui-reference-mode-toggle"', body)
        checkbox_tag = re.search(r'<input type="checkbox" id="ui-reference-mode-toggle"[^>]*>', body).group(0)
        self.assertNotIn("checked", checkbox_tag)

    def test_toggle_present_reviewer_wide_not_only_inside_a_project(self):
        client = self._client_as("vw7a_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('id="ui-reference-mode-toggle"', body)


# ---------------------------------------------------------------------------
# Light no-behavior-change spot check - the full pre-existing suite is the
# real proof; this only guards the specific elements this stage touched.
# ---------------------------------------------------------------------------

class NoBehaviorChangeSpotCheckTests(_BaseTestCase):
    def test_documents_count_and_navigation_unchanged(self):
        client = self._client_as("vw7a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Documents <span", body)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        self.assertIn(f'href="/projects/{self.project_id}/workspace?source={source_id}"', body)

    def test_add_document_form_action_unchanged(self):
        client = self._client_as("vw7a_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/sources/document",
            data={"document": (io.BytesIO(b"hello"), "note.txt")},
            content_type="multipart/form-data", follow_redirects=True,
        )
        self.assertIn("Document added as a Project Source.", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
