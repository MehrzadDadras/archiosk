"""
CLAUDE-P40-VW7B - Foreground Project Vestibule and Four-Position
Investigation Attention Model.

NOTE ON THE TAG: "CLAUDE-P40-VW7B" was already used once before, for an
unrelated, already-shipped stage (git `a61a7b8`/`9a5c11b`, "generalize
active-Display projection; relocate a misplaced admin control"). This
stage reuses the same tag because that is what its own governing
prompt specified - flagged here, in templates/base.html's own comment,
and in the checkpoint entry so the collision is never silently
ambiguous to a future reader.

Repository-grounded refinements to the prompt's own proposed hierarchy
(see this stage's own checkpoint entry for the full critique):
- "Foreground Project" needs no new persisted state - it is already
  structurally equivalent to "the project_id the current URL names"
  (this is a full-page-reload app, no client router). Section 3's fix
  is therefore a Lists RENDERING change, not a new session concept.
- The Vestibule already existed in most of its needed shape:
  routes/portal.py's choose_project / templates/project_chooser.html
  (CLAUDE-P40-VW8-QA, Section 12) - extended here rather than rebuilt.
- Per-Project workspace restoration (DTAB1 tabs, LTH1's Lists/
  Thumbnails split, EYE1's Toolbox/Eye split) is already ~90% correct
  by construction (localStorage keyed by username+project_id) - this
  stage verifies that, rather than rebuilding it.
- Investigation status already has a real two-state lifecycle
  (CASE_STATUS_OPEN/CASE_STATUS_ARCHIVED) and a real, previously-
  unused-by-any-UI governed completion route (workspace.archive_case).
  No "Waiting/Parked" state exists anywhere in the domain model, so the
  fifth-Investigation capacity dialog offers only Release (pure
  attention-set membership change) and Conclude (the real archive_case
  action) - never a fabricated third option.

No real browser tool exists in this environment - coverage here is
template/CSS/JS source and rendered-HTML structural tests, the same
practical ceiling this repo's prior stages have already established
and stated honestly rather than fabricating a walkthrough.
"""
from __future__ import annotations

import io
import re
import tempfile
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
_CHOOSER_HTML_PATH = _REPO_ROOT / "templates" / "project_chooser.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_ATTENTION_JS_PATH = _REPO_ROOT / "static" / "js" / "investigation_attention.js"
_WORKSPACE_ROUTES_PATH = _REPO_ROOT / "routes" / "workspace.py"


def _rule_body(css: str, selector: str) -> str:
    needle = re.compile(r"(?<![\w-])" + re.escape(selector) + r"(?![\w\-\":])")
    pos = 0
    while True:
        match = needle.search(css, pos)
        assert match, f"no CSS rule found for selector {selector!r}"
        brace_open = css.index("{", match.end())
        between = css[match.end():brace_open]
        if re.fullmatch(r'[\w\s,.#\[\]"=\-:>]*', between):
            brace_close = css.index("}", brace_open)
            return css[brace_open + 1:brace_close]
        pos = match.end()


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_vw7b_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw7b_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="vw7b_other", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename="rfp.txt", content=b"content", owner="vw7b_owner"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )
        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(content, filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self, username="vw7b_owner", user_id=1, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _create_case(self, client, project_id, title):
        resp = client.post(f"/projects/{project_id}/workspace/cases", data={"title": title, "objective": ""})
        location = resp.headers["Location"]
        return location.split("case=")[1].split("&")[0]


# ---------------------------------------------------------------------------
# Section 3: opened-Project Lists composition.
# ---------------------------------------------------------------------------

class OpenedProjectPortfolioRemovalTests(_BaseTestCase):
    def test_no_portfolio_root_other_project_names_or_new_project_inside_open_project(self):
        doc = self._ingest("VW7B Project A")
        other = self._ingest("VW7B Project B (Other)")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="lists.projects"', body)
        self.assertNotIn('data-ui-ref="lists.projects.leaf"', body)
        self.assertNotIn('data-ui-ref="lists.new-project"', body)
        self.assertNotIn('data-ui-ref="lists.removed-projects"', body)
        self.assertNotIn("VW7B Project B (Other)", body)
        self.assertNotIn(other.project_id, body)

    def test_opened_project_lists_still_shows_its_own_family(self):
        doc = self._ingest("VW7B Project C")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        for ref in (
            "lists.project.self", "lists.project.overview", "lists.project.documents",
            "lists.project.investigations", "lists.project.rfis", "lists.project.chats",
            "lists.project.tasks", "lists.project.tags", "lists.project.tools",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', body, ref)

    def test_admin_only_security_and_data_management_still_reachable_when_open(self):
        # Section 3's forbidden list is specific (PROJECTS root, other
        # Project names, +New Project, Removed Projects) - Security and
        # Project Data Management are admin TOOLS, not portfolio
        # Project-selection surfaces, and deliberately stay reachable.
        doc = self._ingest("VW7B Project D")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.security"', body)
        self.assertIn('data-ui-ref="lists.system-data-management"', body)

    def test_removed_project_tombstone_does_not_crash_and_falls_back_to_portfolio(self):
        doc = self._ingest("VW7B Project E")
        store = self._store()
        workspace = store.get(doc.project_id)
        store.remove_project(workspace, actor="vw7b_owner", actor_role="admin")
        client = self._client()
        resp = client.get(f"/projects/{doc.project_id}/workspace")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("Restore Project", body)

    def test_composed_server_side_not_css_hidden(self):
        # A CSS-only hide would still ship the other Project's name in
        # the HTML - confirmed absent from the raw response body above
        # (test_no_portfolio_root...), not merely covered by a class.
        doc = self._ingest("VW7B Project F")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("display: none", body)  # sanity: no inline hide-hack introduced


class DeadDialogRemovalTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_project_switch_dialog_fully_removed(self):
        self.assertNotIn("project-switch-dialog", self.html)
        self.assertNotIn(".project-switch-dialog", self.css)

    def test_sibling_separation_mechanism_fully_removed(self):
        self.assertNotIn("sibling_separation", self.html)
        self.assertNotIn("sibling-project-after-current", self.html)
        self.assertNotIn(".sibling-project-after-current", self.css)

    def test_capacity_dialog_css_reuses_the_renamed_classes(self):
        for selector in (
            ".attention-capacity-dialog", ".attention-capacity-dialog-heading",
            ".attention-capacity-dialog-body", ".attention-capacity-dialog-actions",
        ):
            self.assertIn(selector, self.css, selector)


# ---------------------------------------------------------------------------
# Section 4/5: Project Vestibule and header Switch-Project access.
# ---------------------------------------------------------------------------

class VestibuleTests(_BaseTestCase):
    def test_current_project_section_renders_only_with_valid_current_param(self):
        doc = self._ingest("VW7B Vestibule Current")
        client = self._client()
        with_current = client.get(f"/projects/choose?current={doc.project_id}").get_data(as_text=True)
        self.assertIn('data-ui-ref="gateway.chooser.current"', with_current)
        self.assertIn("Currently entered", with_current)
        without_current = client.get("/projects/choose").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="gateway.chooser.current"', without_current)

    def test_current_project_excluded_from_available_list(self):
        doc = self._ingest("VW7B Vestibule Current 2")
        other = self._ingest("VW7B Vestibule Other 2")
        client = self._client()
        body = client.get(f"/projects/choose?current={doc.project_id}").get_data(as_text=True)
        self.assertEqual(body.count("VW7B Vestibule Current 2"), 1)
        self.assertIn("VW7B Vestibule Other 2", body)

    def test_unauthorized_current_param_silently_ignored_not_404(self):
        # Never a hard authorization boundary of its own - a soft
        # display hint only. Uses a non-admin client - vw7b_owner
        # defaults to role="admin" elsewhere in this file, which (per
        # this repo's own established P32 access pattern) can see
        # every Project regardless of ownership, so it would not
        # actually exercise the unauthorized path this test is for.
        self._ingest("VW7B Vestibule Owner Project")
        stranger_doc = self._ingest("VW7B Vestibule Stranger Project", owner="vw7b_other")
        client = self._client("vw7b_owner", 1, role="read_only")
        resp = client.get(f"/projects/choose?current={stranger_doc.project_id}")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertNotIn('data-ui-ref="gateway.chooser.current"', body)
        self.assertNotIn("VW7B Vestibule Stranger Project", body)

    def test_stale_current_param_silently_ignored(self):
        self._ingest("VW7B Vestibule Stale Project")
        client = self._client()
        resp = client.get("/projects/choose?current=not-a-real-project-id")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('data-ui-ref="gateway.chooser.current"', resp.get_data(as_text=True))

    def test_search_form_preserves_current_param(self):
        doc = self._ingest("VW7B Vestibule Search Preserve")
        client = self._client()
        body = client.get(f"/projects/choose?current={doc.project_id}").get_data(as_text=True)
        self.assertIn(f'name="current" value="{doc.project_id}"', body)

    def test_removed_projects_link_present(self):
        client = self._client()
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn('data-ui-ref="gateway.chooser.removed-projects"', body)

    def test_vestibule_is_selection_only_no_documents_or_findings_content(self):
        doc = self._ingest("VW7B Vestibule Selection Only")
        client = self._client()
        body = client.get(f"/projects/choose?current={doc.project_id}").get_data(as_text=True)
        self.assertNotIn("id=\"launcher-panel\"", body)
        self.assertNotIn("Finding", body)
        self.assertNotIn("conv-", body)

    def test_current_project_badge_is_real_text_not_color_only(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        body = _rule_body(css, ".project-card-current .project-card-link")
        self.assertIn("border-width: 2px", body)
        # The badge text itself ("Currently entered") is what actually
        # satisfies "no color-only distinction" - verified via the
        # rendered-HTML test above (test_current_project_section...).


class HeaderSwitchProjectTests(_BaseTestCase):
    def test_header_project_name_links_to_vestibule_with_current_param(self):
        doc = self._ingest("VW7B Header Project")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.context.switch-project"')
        tag = body[body.rindex("<a", 0, idx):body.index(">", idx) + 1]
        self.assertIn(f'href="/projects/choose?current={doc.project_id}"', tag)

    def test_header_link_has_accessible_purpose_beyond_bare_name(self):
        doc = self._ingest("VW7B Header Project 2")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.context.switch-project"')
        tag = body[body.rindex("<a", 0, idx):body.index(">", idx) + 1]
        self.assertIn("Switch Project", tag)

    def test_header_link_is_a_single_control_no_duplicate_tab_stop(self):
        doc = self._ingest("VW7B Header Project 3")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.context.switch-project"')
        element = body[body.rindex("<a", 0, idx):body.index("</a>", idx) + 4]
        self.assertEqual(element.count("<a "), 1)


# ---------------------------------------------------------------------------
# Section 6/7: switching behavior and per-Project restoration (already
# correct by construction - verified, not rebuilt).
# ---------------------------------------------------------------------------

class PerProjectRestorationGroundingTests(unittest.TestCase):
    """DTAB1/LTH1/EYE1 persistence is already Project-scoped by
    construction (localStorage keyed by username+project_id) - this
    class confirms that grounding directly against the source, rather
    than re-implementing persistence that already exists."""

    def test_document_tabs_keys_include_project_id(self):
        js = (_REPO_ROOT / "static" / "js" / "document_tabs.js").read_text(encoding="utf-8")
        self.assertIn("PINNED_KEY = 'beehive:tabs:pinned:' + username + ':' + projectId", js)

    def test_thumbnails_remembered_source_key_includes_project_id(self):
        js = (_REPO_ROOT / "static" / "js" / "pdf_viewer.js").read_text(encoding="utf-8")
        self.assertIn("'beehive:panel:last-pdf-source:' + username + ':' + projectId", js)

    def test_attention_key_includes_both_username_and_project_id(self):
        js = _ATTENTION_JS_PATH.read_text(encoding="utf-8")
        self.assertIn("'beehive:attention:cases:' + username + ':' + projectId", js)

    def test_no_interruption_dialog_reintroduced_for_ordinary_switching(self):
        # Section 6: "do not show a confirmation merely because the user
        # changes Projects when state is safely persisted."
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        chooser = _CHOOSER_HTML_PATH.read_text(encoding="utf-8")
        self.assertNotIn("Switch Project?", html)
        self.assertNotIn("role=\"dialog\"", chooser)


# ---------------------------------------------------------------------------
# Section 8/9/10: Investigation Attention Positions.
# ---------------------------------------------------------------------------

class AttentionStripMarkupTests(_BaseTestCase):
    def test_attention_strip_and_capacity_dialog_render(self):
        doc = self._ingest("VW7B Attention Project")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="attention-strip"', body)
        self.assertIn('id="attention-strip-list"', body)
        self.assertIn('id="attention-capacity-dialog"', body)
        self.assertIn('id="workspace-visible-cases-data"', body)

    def test_attention_strip_hidden_by_default_server_side(self):
        doc = self._ingest("VW7B Attention Project 2")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('id="attention-strip"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertIn("hidden", tag)

    def test_capacity_dialog_has_real_dialog_semantics(self):
        doc = self._ingest("VW7B Attention Project 3")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('id="attention-capacity-dialog"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertIn('role="dialog"', tag)
        self.assertIn('aria-modal="true"', tag)
        self.assertIn('aria-labelledby="attention-capacity-dialog-heading"', tag)
        self.assertIn("hidden", tag)

    def test_visible_cases_json_carries_no_arbitrary_extra_data(self):
        doc = self._ingest("VW7B Attention Project 4")
        client = self._client()
        self._create_case(client, doc.project_id, "Foundation Review")
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        import json
        start = body.index('id="workspace-visible-cases-data"')
        script_start = body.index(">", start) + 1
        script_end = body.index("</script>", script_start)
        payload = json.loads(body[script_start:script_end])
        self.assertEqual(len(payload), 1)
        self.assertEqual(set(payload[0].keys()), {"id", "title", "status", "created_by"})
        self.assertEqual(payload[0]["status"], "open")

    def test_data_active_case_id_reflects_the_url_selection(self):
        doc = self._ingest("VW7B Attention Project 5")
        client = self._client()
        case_id = self._create_case(client, doc.project_id, "Water Ingress Review")
        body = client.get(f"/projects/{doc.project_id}/workspace?case={case_id}").get_data(as_text=True)
        idx = body.index('id="attention-strip"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertIn(f'data-active-case-id="{case_id}"', tag)

    def test_overflow_notice_renders_hidden_with_pin_and_dismiss(self):
        """CLAUDE-INVESTIGATION-ATTENTION-02: the non-blocking replacement
        for the old auto-opening capacity dialog - server-rendered empty/
        hidden (static/js/investigation_attention.js fills and reveals it
        only when a real overflow actually occurs), never role="dialog"/
        aria-modal (it must never block anything the reviewer is doing)."""
        doc = self._ingest("VW7B Attention Project 6")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('id="attention-overflow-notice"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertIn("hidden", tag)
        self.assertNotIn('role="dialog"', tag)
        self.assertNotIn("aria-modal", tag)
        self.assertIn('aria-live="polite"', tag)
        self.assertIn('id="attention-overflow-notice-text"', body)
        self.assertIn('id="attention-overflow-notice-pin"', body)
        self.assertIn('id="attention-overflow-notice-dismiss"', body)


class AttentionJsSourceTests(unittest.TestCase):
    def setUp(self):
        self.js = _ATTENTION_JS_PATH.read_text(encoding="utf-8")

    def test_max_attention_is_four(self):
        self.assertIn("var MAX_ATTENTION = 4;", self.js)

    def test_reconciliation_never_picks_an_arbitrary_first_investigation(self):
        # Only ever adds the URL-driven activeCaseId - never iterates
        # visibleCases to guess one.
        self.assertNotIn("visibleCases[0]", self.js)
        self.assertNotIn("casesById[Object.keys(casesById)[0]]", self.js)

    def test_stale_or_unauthorized_attention_entries_filtered_on_load(self):
        self.assertIn("loadAttention().filter(function (id) { return !!casesById[id]; })", self.js)

    def test_release_never_navigates(self):
        fn = self.js[self.js.index("function releaseFromAttention("):self.js.index("function onPositionKeydown(")]
        self.assertNotIn("window.location", fn)
        self.assertNotIn("navigateTo", fn)

    def test_release_does_not_mutate_business_status(self):
        # Section 8: "must not delete, close, resolve, archive, or
        # otherwise falsify its real status" - releaseFromAttention only
        # ever touches the local `attention` array + localStorage.
        fn = self.js[self.js.index("function releaseFromAttention("):self.js.index("function onPositionKeydown(")]
        self.assertNotIn("fetch(", fn)
        self.assertNotIn(".submit()", fn)

    def test_conclude_uses_the_real_archive_case_route_pattern(self):
        self.assertIn("/workspace/cases/", self.js)
        self.assertIn("/archive", self.js)

    def test_conclude_passes_next_case_for_smooth_continuation(self):
        self.assertIn("nextCaseInput.value = activeCaseId", self.js)

    def test_cancel_just_closes_without_navigating_away(self):
        """CLAUDE-INVESTIGATION-ATTENTION-02: this dialog is no longer
        forced open automatically on load - it's reached only by the
        reviewer's own "Pin this instead…" choice from the non-blocking
        overflow notice, and the Case it would pin was ALREADY being
        shown, legitimately, before that choice. Cancelling now means
        exactly what it says (don't pin it, stay here) - it must never
        navigate away from content the reviewer was already viewing,
        which is what the OLD, forced-open version of this dialog had to
        do instead (there was nothing else for Cancel to mean when the
        whole page load itself was the interruption)."""
        fn = self.js[self.js.index("cancelBtn.addEventListener"):]
        self.assertIn("closeCapacityDialog()", fn[:200])
        self.assertNotIn("navigateToEmpty", self.js)

    def test_only_release_conclude_cancel_offered_as_real_button_labels(self):
        # Grounded in the real Case model (CASE_STATUS_OPEN/ARCHIVED
        # only, no third governed state) - never a fabricated "move to
        # Waiting/Parked" option. Checked via the actual button-label
        # string literals assigned to .textContent INSIDE the capacity
        # dialog's own per-position action buttons, not a bare
        # substring search across the whole file (which would also
        # match this test's own, and the source's own, explanatory
        # prose mentioning those words by name, and the strip's
        # unrelated Focused/Archived tags).
        start = self.js.index("function openCapacityDialog(")
        end = self.js.index("dialog.hidden = false;", start)
        fn = self.js[start:end]
        labels = set(re.findall(r"\.textContent = '([^']+)';", fn))
        self.assertEqual(labels, {"Release", "Conclude"})

    def test_capacity_check_is_post_load_not_a_click_interceptor(self):
        # Deliberately no addEventListener('click', ...) on the Lists
        # tree root in this file - see its own header comment for why.
        self.assertNotIn("data-tree-root", self.js)

    def test_overflow_never_auto_opens_the_capacity_dialog(self):
        """CLAUDE-INVESTIGATION-ATTENTION-02: reconciliation on load must
        only ever populate the non-blocking overflow notice - the dialog
        itself is opened exclusively from inside showOverflowNotice's own
        Pin-button click handler, never unconditionally at load time the
        way the old capacityDialogNeeded branch used to."""
        reconciliation = self.js[self.js.index("var overflowCase = null;"):self.js.index("function render()")]
        self.assertNotIn("openCapacityDialog()", reconciliation)
        self.assertIn("overflowCase = casesById[activeCaseId];", reconciliation)

    def test_overflow_never_evicts_an_already_pinned_investigation(self):
        # Reaching capacity must leave the existing `attention` array (and
        # its saved copy) completely untouched - overflowCase is set and
        # nothing more; only an explicit Release/Conclude click (inside
        # the voluntarily-opened dialog) ever removes an existing entry.
        reconciliation = self.js[self.js.index("var overflowCase = null;"):self.js.index("if (attentionChanged) saveAttention(attention);") + 1]
        self.assertNotIn("attention.splice", reconciliation)
        self.assertNotIn("attention.shift", reconciliation)
        self.assertNotIn("attention.pop", reconciliation)

    def test_keyboard_roving_tabindex_present(self):
        start = self.js.index("function onPositionKeydown(")
        # "render();" appears earlier in the file too (inside
        # releaseFromAttention, defined before this function) - anchor
        # the end search to AFTER this function's own start, not the
        # first "render();" anywhere in the file.
        end = self.js.index("render();", start)
        fn = self.js[start:end]
        self.assertIn("ArrowRight", fn)
        self.assertIn("ArrowLeft", fn)
        self.assertIn("'Home'", fn)
        self.assertIn("'End'", fn)

    def test_focused_and_archived_use_real_text_tags_not_color_only(self):
        self.assertIn("'Focused'", self.js)
        self.assertIn("'Archived'", self.js)


class ArchiveCaseNextCaseTests(_BaseTestCase):
    def test_next_case_redirect_when_valid(self):
        doc = self._ingest("VW7B Conclude Project")
        client = self._client()
        case_a = self._create_case(client, doc.project_id, "Case A")
        case_b = self._create_case(client, doc.project_id, "Case B")
        resp = client.post(
            f"/projects/{doc.project_id}/workspace/cases/{case_a}/archive",
            data={"next_case": case_b},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn(f"case={case_b}", resp.headers["Location"])

    def test_next_case_ignored_when_unauthorized_or_foreign(self):
        doc = self._ingest("VW7B Conclude Project 2")
        foreign = self._ingest("VW7B Conclude Foreign Project", owner="vw7b_other")
        client = self._client()
        case_a = self._create_case(client, doc.project_id, "Case A2")
        foreign_case_id = str(uuid.uuid4())
        resp = client.post(
            f"/projects/{doc.project_id}/workspace/cases/{case_a}/archive",
            data={"next_case": foreign_case_id},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn(f"case={case_a}", resp.headers["Location"])

    def test_archive_case_still_requires_owner_or_admin(self):
        doc = self._ingest("VW7B Conclude Project 3")
        owner_client = self._client()
        case_a = self._create_case(owner_client, doc.project_id, "Case A3")
        store = self._store()
        workspace = store.get(doc.project_id)
        store.grant_project_access(workspace, username="vw7b_other", actor="vw7b_owner", actor_role="admin")
        stranger_client = self._client("vw7b_other", 2, role="read_only")
        resp = stranger_client.post(f"/projects/{doc.project_id}/workspace/cases/{case_a}/archive")
        self.assertEqual(resp.status_code, 302)
        case = next(c for c in store.get(doc.project_id).cases if c["id"] == case_a)
        self.assertEqual(case["status"], "open")


# ---------------------------------------------------------------------------
# Section 11: cross-Project / cross-account isolation.
# ---------------------------------------------------------------------------

class IsolationTests(_BaseTestCase):
    def test_visible_cases_json_scoped_to_this_project_only(self):
        doc_a = self._ingest("VW7B Isolation Project A")
        doc_b = self._ingest("VW7B Isolation Project B")
        client = self._client()
        self._create_case(client, doc_a.project_id, "Case in A")
        self._create_case(client, doc_b.project_id, "Case in B")
        body = client.get(f"/projects/{doc_a.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Case in A", body)
        self.assertNotIn("Case in B", body)

    def test_unauthorized_project_direct_url_rejected(self):
        # Non-admin client - see VestibuleTests' own note on why
        # role="admin" (this file's default) would not exercise this.
        stranger_doc = self._ingest("VW7B Isolation Stranger", owner="vw7b_other")
        client = self._client("vw7b_owner", 1, role="read_only")
        resp = client.get(f"/projects/{stranger_doc.project_id}/workspace")
        self.assertEqual(resp.status_code, 404)

    def test_vestibule_never_lists_unauthorized_projects(self):
        self._ingest("VW7B Isolation Owner Vis")
        self._ingest("VW7B Isolation Stranger Vis", owner="vw7b_other")
        client = self._client("vw7b_owner", 1, role="read_only")
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn("VW7B Isolation Owner Vis", body)
        self.assertNotIn("VW7B Isolation Stranger Vis", body)

    def test_no_uuid_or_secret_exposed_in_visible_labels(self):
        doc = self._ingest("VW7B Isolation No UUID")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.context.switch-project"')
        tag = body[body.rindex("<a", 0, idx):body.index("</a>", idx)]
        # Visible text must be the display name, not the raw project_id.
        visible_text = tag[tag.index(">") + 1:]
        self.assertNotIn(doc.project_id, visible_text)

    def test_attention_positions_do_not_expose_cross_project_leakage(self):
        # The strip is populated purely from #workspace-visible-cases-
        # data (already Project-scoped) - a foreign Project's Case can
        # never appear in it structurally, since it never appears in
        # that JSON island at all (test_visible_cases_json_scoped_to_
        # this_project_only above is the direct proof).
        js = _ATTENTION_JS_PATH.read_text(encoding="utf-8")
        self.assertIn("workspace-visible-cases-data", js)


# ---------------------------------------------------------------------------
# Section 13: accessibility / Appearance / narrow viewport.
# ---------------------------------------------------------------------------

class AccessibilityAppearanceTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_attention_position_has_focus_visible_outline(self):
        body = _rule_body(self.css, ".attention-position:focus-visible")
        self.assertIn("outline:", body)

    def test_header_switch_project_link_has_focus_visible_outline(self):
        body = _rule_body(self.css, ".workspace-topbar-project:focus-visible")
        self.assertIn("outline:", body)

    def test_attention_strip_uses_tokens_not_hardcoded_colors(self):
        body = _rule_body(self.css, ".attention-position-focused-tag")
        self.assertIn("var(--machine-blue)", body)
        self.assertNotRegex(body, r"#[0-9a-fA-F]{3,6}\b")

    def test_no_new_narrow_viewport_mechanism_invented(self):
        # Section 5/13's own "predictable narrow-viewport behavior" -
        # the strip scrolls horizontally via the SAME .document-tab-list
        # idiom (overflow-x: auto) rather than a new mechanism.
        body = _rule_body(self.css, ".attention-strip-list")
        self.assertIn("overflow-x: auto", body)

    def test_release_button_has_accessible_label_pattern(self):
        js = _ATTENTION_JS_PATH.read_text(encoding="utf-8")
        self.assertIn("'Release ' + c.title + ' from attention'", js)


# ---------------------------------------------------------------------------
# Section 20: no unauthorized scope creep.
# ---------------------------------------------------------------------------

class ScopeBoundaryTests(unittest.TestCase):
    def test_no_cross_project_document_route_added(self):
        routes_src = _WORKSPACE_ROUTES_PATH.read_text(encoding="utf-8")
        self.assertNotIn("cross_project", routes_src.lower().replace("-", "_"))

    def test_no_global_search_route_added(self):
        routes_src = _WORKSPACE_ROUTES_PATH.read_text(encoding="utf-8")
        self.assertNotIn("global_search", routes_src)

    def test_no_confidence_or_urgency_scoring_in_attention_js(self):
        js = _ATTENTION_JS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("confidence", js.lower())
        self.assertNotIn("urgency", js.lower())
        self.assertNotIn("priority", js.lower())


if __name__ == "__main__":
    unittest.main()
