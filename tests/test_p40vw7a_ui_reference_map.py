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
# CLAUDE-UI-ACTION-REDUNDANCY-REVIEW-01, Disposition 2/3: the entire
# application menu bar (every menu.* ref) was extracted out of
# base.html's own source into this shared partial, {% include %}d by
# both base.html and gateway_shell.html - a plain source-text scan of
# base.html alone would no longer find any menu.* ref at all now that
# they only live here.
_APP_MENU_HTML_PATH = _REPO_ROOT / "templates" / "_app_menu.html"
_CASE_WORKSPACE_HTML_PATH = _REPO_ROOT / "templates" / "case_workspace.html"
_REPLACE_DOCUMENT_HTML_PATH = _REPO_ROOT / "templates" / "replace_document.html"
_MACROS_HTML_PATH = _REPO_ROOT / "templates" / "_macros.html"
# CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Option C: gateway.html
# itself is retired (the route it used to render now only redirects) -
# its own refs live on index.html now, scanned below.
_INDEX_HTML_PATH = _REPO_ROOT / "templates" / "index.html"
_GATEWAY_SHELL_HTML_PATH = _REPO_ROOT / "templates" / "gateway_shell.html"
_PROJECT_CHOOSER_HTML_PATH = _REPO_ROOT / "templates" / "project_chooser.html"
_LOGIN_HTML_PATH = _REPO_ROOT / "templates" / "login.html"
_UPLOAD_HTML_PATH = _REPO_ROOT / "templates" / "upload.html"
_LANDING_HTML_PATH = _REPO_ROOT / "templates" / "landing.html"
_EXPLORE_HTML_PATH = _REPO_ROOT / "templates" / "explore.html"
_START_TRIAL_HTML_PATH = _REPO_ROOT / "templates" / "start_trial.html"
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
# CLAUDE-CA1D-INSTRUMENT-RAIL-01: operations.html passes its two refs as
# macro CALL arguments (ui_ref='operations.telemetry'), the exact same
# security_department.html shape the comment above this one already
# documents - added to the scanned list from the start, not left as a
# second silent blind spot.
_OPERATIONS_HTML_PATH = _REPO_ROOT / "templates" / "operations.html"
# CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01: reset_project_data.html gained
# real data-ui-ref attributes for the first time this stage (its "Project
# Data Management" identity) - added to the scanned list from the start,
# same discipline as _OPERATIONS_HTML_PATH's own comment above.
_RESET_PROJECT_DATA_HTML_PATH = _REPO_ROOT / "templates" / "reset_project_data.html"
# CLAUDE-SPIN-00A: _spin_prototype.html is included (not extended) by
# case_workspace.html's own {% block toolbox %} - its own refs are real
# rendered markup (when ?spin=1), same as any other template here, just
# never inlined into case_workspace.html's own source text for the
# _DATA_REF_RE scan above to find without this separate path.
_SPIN_PROTOTYPE_HTML_PATH = _REPO_ROOT / "templates" / "_spin_prototype.html"
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

# CLAUDE-P40-VW8-QA: the Appearance selector constructs its own
# data-ui-ref VALUES from a Jinja loop variable (data-ui-ref="menu.
# appearance.{{ ref_suffix }}") - unlike every other pattern ref (a
# literal, static string reused across repeated instances), a plain
# regex over the template SOURCE can never recover the resolved values,
# since the source never contains them literally. Enumerated here from
# the exact same fixed tuple base.html's own {% for %} loop iterates
# over, so registry-vs-template drift (e.g. a mode added to one but not
# the other) is still genuinely caught, not silently exempted.
#
# CLAUDE-APPEARANCE-SIMPLIFY-01: retired the five-per-surface dimension
# entirely (Product Owner: "do not allow panel-by-panel theme mixing") -
# ONE global choice now, so this is a flat set of modes, no more
# surface x mode cross product and no more separate "all" namespace.
# "tinted" and "dark" stayed as the RETAINED ref suffixes for Midnight
# Blue/Black (label/palette revisions, not renumbering - see tokens.css's
# own comment); "deep-ocean" is the one genuinely new suffix this stage
# adds.
_APPEARANCE_MODES = ("light", "dark", "tinted", "deep-forest", "deep-ocean")
_APPEARANCE_DYNAMIC_REFS = {f"menu.appearance.{mode}" for mode in _APPEARANCE_MODES}

# CLAUDE-P40-VW8-QA (Project-Creation Upload-Capacity Correction):
# errors/error.html's action link renders `data-ui-ref="{{ ui_ref }}"`
# - a Jinja variable, not a literal string, so (like the Appearance
# refs above) a plain regex over the template source can never recover
# it. app.py's own 413 handler is the one real call site that ever
# passes a non-None `ui_ref` - hardcoded here from that exact literal.
_ERROR_PAGE_DYNAMIC_REFS = {"errors.upload-too-large"}

# CLAUDE-ENTRY-SIMPLIFY-01: index.html's environment-choice cards are GONE, so
# the dynamic ref set they needed is gone with them. It used to expand
# `data-ui-ref="index.choice.{{ env }}"` over OPERATING_ENVIRONMENTS, because a
# Jinja loop variable is not literal text this file can scan for.
#
# Deleted rather than emptied: an empty set kept here would read as "these refs
# exist and there happen to be none", which is a different and untrue claim
# from "that surface no longer exists". The gate presented as a governed choice
# while persisting nothing and granting no authority; environment filtering
# moved to projects-directory.environment-filter, which is a LITERAL ref and
# needs no dynamic set at all.
_INDEX_CHOICE_DYNAMIC_REFS: set[str] = set()

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

# CLAUDE-PERSPECTIVE-GATE-04: the five project-position radios are built the
# same Jinja-loop way (data-ui-ref="upload.entry-choice.{{ choice.value }}"),
# so they need the same registration here - without it they would inherit
# exactly the silent blind spot the environment radios above had before it
# was closed, and would never actually be verified against the registry.
from services.project_perspective import ENTRY_CHOICES as _ENTRY_CHOICES  # noqa: E402

_UPLOAD_ENTRY_CHOICE_DYNAMIC_REFS = {
    f"upload.entry-choice.{value}" for value in _ENTRY_CHOICES
}

# CLAUDE-ENTRY-REDUNDANCY-01: the upstream question is rendered per position,
# so its refs are a Jinja-loop family too. The operating-environment radios
# above are gone from the creation form entirely - the environment is derived
# from the declared position now - so their dynamic set is no longer unioned
# and their registry rows are retired rather than deleted.
from services.project_perspective import (  # noqa: E402
    ENTRY_CHOICE_RETAINED_BY_OPTIONS as _RETAINED_BY_OPTIONS,
)

_UPLOAD_RETAINED_BY_DYNAMIC_REFS = {
    f"upload.retained-by.{value}"
    for value, options in _RETAINED_BY_OPTIONS.items() if options
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
        _BASE_HTML_PATH, _APP_MENU_HTML_PATH, _CASE_WORKSPACE_HTML_PATH,
        _REPLACE_DOCUMENT_HTML_PATH, _MACROS_HTML_PATH,
        _INDEX_HTML_PATH, _GATEWAY_SHELL_HTML_PATH, _PROJECT_CHOOSER_HTML_PATH,
        _LOGIN_HTML_PATH, _UPLOAD_HTML_PATH, _UPLOAD_CONFIRM_HTML_PATH, _ERROR_HTML_PATH,
        _SECURITY_DEPARTMENT_HTML_PATH, _PROJECTS_HTML_PATH, _REMOVED_PROJECTS_HTML_PATH, _APP_PY_PATH,
        _CONFIRM_DELETE_FOLDER_HTML_PATH, _OPERATIONS_HTML_PATH,
        _LANDING_HTML_PATH, _EXPLORE_HTML_PATH, _START_TRIAL_HTML_PATH,
        _SPIN_PROTOTYPE_HTML_PATH, _RESET_PROJECT_DATA_HTML_PATH,
    ):
        text = path.read_text(encoding="utf-8")
        refs |= set(_DATA_REF_RE.findall(text))
        refs |= set(_MACRO_UI_REF_RE.findall(text))
    refs |= _APPEARANCE_DYNAMIC_REFS
    refs |= _ERROR_PAGE_DYNAMIC_REFS
    refs |= _UPLOAD_CONFIRM_DYNAMIC_REFS
    refs |= _UPLOAD_ENTRY_CHOICE_DYNAMIC_REFS
    refs |= _UPLOAD_RETAINED_BY_DYNAMIC_REFS
    refs |= _INDEX_CHOICE_DYNAMIC_REFS
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
        # CLAUDE-CA1D-INSTRUMENT-RAIL-01 added "operations" - the
        # admin-page half of the four-part Instrument Rail spatial
        # model (see UI_REFERENCE_MAP.md's own "Operations" section).
        # CLAUDE-CA1D-PUBLIC-LANDING-01 added "landing"/"explore"/
        # "start-trial" - the new public front door, its own standalone
        # shell outside gateway/auth (see UI_REFERENCE_MAP.md's own
        # "Public Landing" section).
        # CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 added "pdm" - Project
        # Data Management's own new Add/Archive Documents content (see
        # UI_REFERENCE_MAP.md's own "Project Data Management" section).
        # CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Option C added
        # "index" - the consolidated post-sign-in entry page (portal.index,
        # `/`), replacing the retired separate Gateway shell.
        for ref in _all_template_refs():
            self.assertRegex(
                ref,
                r"^(menu|lists|display|toolbox|chat|eye|shell|gateway|auth|upload|errors|"
                r"security|operations|projects-directory|removed-projects|developer|"
                r"landing|explore|start-trial|spin|pdm|index)\.[a-z0-9._\-]+$",
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
        #
        # CLAUDE-GO-DNA-01 (Panel Zoning): the full project family is
        # still reachable, now split across two zones instead of all
        # living in Lists - "lists.project.overview" is retired outright
        # (lists.project.self already opens the same page); Investigations/
        # RFI/Conversation/Tasks/Tags moved to their toolbox.* equivalents,
        # rendered in the Toolbox's own "nothing selected" Project
        # Intelligence view (no Investigation/Document selected here, so
        # it renders). Project files stay in Lists directly beneath the
        # Project root; the visible lists.project.documents wrapper is
        # retired while lists.project.documents.leaf remains file-territory.
        # CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01: lists.project.tools
        # dropped from this list - retired outright (Part B2), not
        # merely relocated within Lists like the refs above.
        client = self._client_as("vw7a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for ref in ("lists.project.self", "lists.project.search-controls",
                    "lists.project.documents.leaf"):
            self.assertIn(f'data-ui-ref="{ref}"', body, ref)
        for ref in (
            "toolbox.investigations", "toolbox.rfi",
            "toolbox.conversation", "toolbox.tasks", "toolbox.tags",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', body, ref)

    def test_menu_refs_present_on_every_authenticated_page(self):
        # CLAUDE-APP-MENU-01: menu.brand (icon+wordmark single link) is
        # retired - menu.bar/menu.archiosk (the application menu bar and
        # its first entry) are the current equivalents.
        client = self._client_as("vw7a_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.bar"', body)
        self.assertIn('data-ui-ref="menu.archiosk"', body)
        self.assertIn('data-ui-ref="menu.account"', body)

    def test_document_and_investigation_leaf_refs_present(self):
        client = self._client_as("vw7a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Foundation Review", "objective": ""})
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.documents.leaf"', body)
        # CLAUDE-GO-DNA-01 (Panel Zoning): Investigations now renders in the
        # Toolbox's Project Intelligence view, not Lists.
        self.assertIn('data-ui-ref="toolbox.investigations.leaf"', body)

    def test_toolbox_and_display_refs_present_and_context_switches(self):
        client = self._client_as("vw7a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.panel"', body)
        # CLAUDE-GO-DNA-01 (Panel Zoning): the old bare "toolbox.empty" state
        # was replaced by the always-present "toolbox.project-intelligence"
        # section (Requirements/Investigations/RFI/Work Products/
        # Conversation/Tasks/Tags), shown whenever nothing is selected.
        self.assertIn('data-ui-ref="toolbox.project-intelligence"', body)
        self.assertIn('data-ui-ref="display.divisions"', body)
        self.assertIn('data-ui-ref="display.division"', body)

        source_id = self._store().get(self.project_id).sources[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.document"', body)
        self.assertNotIn('data-ui-ref="toolbox.project-intelligence"', body)

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
        # CLAUDE-LEFT-RAIL-01: supersedes CLAUDE-P40-VW7B's own Section 3
        # distinction (new-project forbidden inside an opened Project,
        # security/system-data-management reachable regardless) - that
        # distinction existed only because these lived in two different
        # places (a portfolio-only Lists branch vs. an always-rendered
        # admin Lists branch). All four (New Project, Security,
        # Operations, Project Data Management) now live in exactly ONE
        # place with the same "reachable from any page, admin only"
        # treatment.
        #
        # CLAUDE-APP-MENU-01: that one place moved again - out of the
        # Account menu (which now holds only session-identity actions)
        # and into the new Archiosk application menu, under
        # menu.archiosk.admin.* rather than the retired menu.account.admin.*.
        client = self._client_as("vw7a_admin", 4, role="admin")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="lists.new-project"', body)
        self.assertNotIn('data-ui-ref="lists.security"', body)
        self.assertNotIn('data-ui-ref="lists.system-data-management"', body)
        self.assertNotIn('data-ui-ref="menu.account.admin.new-project"', body)
        self.assertIn('data-ui-ref="menu.archiosk.admin.new-project"', body)
        self.assertIn('data-ui-ref="menu.archiosk.admin.security"', body)
        self.assertIn('data-ui-ref="menu.archiosk.admin.operations"', body)
        self.assertIn('data-ui-ref="menu.archiosk.admin.project-data-management"', body)

    def test_remove_project_ref_owner_or_admin_only(self):
        # CLAUDE-GO-DNA-01 (Panel Zoning): Remove Project moved from Lists'
        # Project Tools into the Toolbox's Project Administration disclosure.
        client = self._client_as("vw7a_granted_reviewer", 3, role="read_only")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="toolbox.project-admin.remove-project"', body)

        owner_client = self._client_as("vw7a_owner", 1)
        owner_body = owner_client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.project-admin.remove-project"', owner_body)

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

    def test_gateway_route_redirects_to_the_consolidated_entry_page(self):
        # CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Option C: /gateway
        # no longer renders its own page - it's kept only as a redirect to
        # / (routes/portal.py's gateway() docstring covers why the route
        # itself was kept rather than deleted). See the next test for the
        # real consolidated destination's own workspace-shell-leak proof.
        client = self._client_as("vw7a_owner", 1)
        resp = client.get("/gateway")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], "/")

    def test_index_page_has_no_active_project_workspace_refs(self):
        # CLAUDE-UI-ACTION-REDUNDANCY-REVIEW-01, Disposition 2/3, revised
        # by CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01 Option C: the
        # original "zero lists./display./toolbox./chat. refs" invariant
        # protected a SEPARATE, deliberately minimal Gateway shell
        # (gateway_shell.html, never including the Lists panel at all)
        # from silently growing full workspace-shell content. Option C
        # retired that separate shell - / now uses the SAME base.html
        # shell as every other authenticated page (/projects, /upload),
        # where lists.* (the reviewer-wide Projects rail) legitimately,
        # deliberately renders regardless of whether a project is open
        # (CLAUDE-LEFT-RAIL-01). What's still real and worth guarding:
        # display.*/toolbox.*/chat.* only ever exist when project_id/
        # workspace are actually defined, which they never are here.
        client = self._client_as("vw7a_owner", 1)
        body = client.get("/").get_data(as_text=True)
        for ref in _DATA_REF_RE.findall(body):
            self.assertFalse(
                ref.startswith(("display.", "toolbox.", "chat.")),
                f"/ leaked an active-project-workspace reference: {ref}",
            )
        self.assertIn("data-ui-ref=\"menu.bar\"", body)
        self.assertIn("data-ui-ref=\"lists.projects\"", body)
        self.assertNotIn("data-ui-ref=\"menu.display-layout\"", body)
        # This test's own fixture project resolves a single accessible
        # environment automatically (State 3 - see index.html's own
        # comment), so the ported "Open Existing Project" disclosure
        # renders under its new index.resolved.open-existing ref (was
        # gateway.open-existing-projects on the now-retired gateway.html).
        self.assertIn("data-ui-ref=\"index.resolved.open-existing\"", body)


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
    def test_document_navigation_unchanged_without_visible_wrapper(self):
        client = self._client_as("vw7a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("Documents <span", body)
        self.assertIn('data-ui-ref="lists.project.documents.leaf"', body)
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


class PanelZoningInvariantTests(_BaseTestCase):
    """CLAUDE-GO-DNA-01 (Panel Zoning), structural guard (Part F.14).

    LEFT (Lists) is file/evidence territory only: project name, folders,
    Documents, Files, and file-related Project Tools actions. Requirements,
    Investigations, RFI Correspondence, Work Products, Conversation, Tasks,
    Tags, and Remove Project must never render as `lists.project.*`
    references again - those categories now live in the Toolbox's Project
    Intelligence view. This asserts the zoning boundary itself (a ref-prefix
    pattern), not any specific markup shape, so it survives future
    reshuffling inside either panel as long as the boundary holds.
    """

    _FORBIDDEN_LISTS_REF_PATTERN = re.compile(
        r'data-ui-ref="lists\.project\.'
        r'(requirements|investigations|rfis|work-products|chats|tasks|tags|tools\.remove-project)'
    )

    def test_lists_panel_never_regresses_into_a_mixed_functional_menu(self):
        client = self._client_as("vw7a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Foundation Review", "objective": ""})
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        match = self._FORBIDDEN_LISTS_REF_PATTERN.search(body)
        self.assertIsNone(
            match,
            f"Lists panel regressed to a mixed functional menu: found {match.group(0) if match else None}",
        )

    def test_the_relocated_categories_still_exist_in_the_toolbox(self):
        # The invariant is a relocation, not a removal - confirm the
        # displaced categories are still reachable, just from the Toolbox.
        client = self._client_as("vw7a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for ref in (
            "toolbox.requirements", "toolbox.investigations", "toolbox.rfi",
            "toolbox.work-products", "toolbox.conversation", "toolbox.tasks", "toolbox.tags",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', body, ref)


if __name__ == "__main__":
    unittest.main()
