"""
CLAUDE-P40-VW9A (Files Cockpit Close-Out and Camel Programme Record).

Focused regression coverage for the four VW9 cockpit residuals (A1-A4)
identified in the CLAUDE-P40-VW9 final report and resolved in this stage:

A1: folder-row "..." action menus (.files-folder-actions,
    static/js/files_folder_menus.js) behave as an exclusive group with
    click-outside and Escape dismissal - adapting document_tabs.js's own
    document-level dismissal pattern to native <details>/<summary>
    elements rather than rebuilding a synthetic menu framework, so
    native keyboard/screen-reader semantics are never touched, only
    exclusivity/outside-dismissal are added.

A2: the Move destination <select> now shows each candidate's full
    ancestor path (routes/workspace.py's design_builder_move_targets,
    "path_label"), so two same-named folders in different branches are
    visibly distinguishable while the submitted value stays the
    authoritative folder id.

A3: the folder-actions panel now always renders in-flow (no
    position:absolute overlay, at any width) - real testing found the
    same overlap/reachability problem at both the realistic ~300-400px
    center-workspace width of a multi-Display division AND at ordinary
    desktop width (a tall open panel could cover several rows below
    it), so the fix is unconditional rather than gated behind a width
    breakpoint; only the panel's OWN internal form layout still gets a
    dedicated narrow-width (<=480px) stacking rule.

A4: the delete-folder confirmation page's "Back without deciding" link
    now returns to the folder's own real parent context (server-derived
    from the already-loaded, project-scoped folder record, never raw
    request input), not always the bare Files root.
"""
from __future__ import annotations

import io
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload
import services.case_workspace as cw

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_TOKENS_CSS_PATH = _REPO_ROOT / "static" / "css" / "tokens.css"
_FILES_FOLDER_MENUS_JS_PATH = _REPO_ROOT / "static" / "js" / "files_folder_menus.js"

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - environment-dependent, not installed
    sync_playwright = None


def _real_chromium_available() -> bool:
    if sync_playwright is None:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


_BROWSER_AVAILABLE = _real_chromium_available()
_SKIP_REASON = (
    "Real Chromium (the `playwright` package + a downloaded browser) is not "
    "available in this environment - these tests provide genuine "
    "browser-executed-JS/CSS evidence that a source-text assertion cannot; "
    "skip rather than fake it when the browser isn't installed."
)


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_vw9a_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="vw9a_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.store = cw.CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename="spec.pdf", content=b"content", owner="vw9a_owner"):
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

    def _client(self, username="vw9a_owner", user_id=1, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


# ---------------------------------------------------------------------------
# A2 - move-destination disambiguation (request-level, no browser needed).
# ---------------------------------------------------------------------------

class MoveDisambiguationTests(_BaseTestCase):
    def test_move_dropdown_disambiguates_same_named_folders_in_different_branches(self):
        doc = self._ingest("VW9A Move Disambiguation Project")
        ws = self.store.get(doc.project_id)
        branch_a = self.store.create_folder(ws, "Branch A", actor="vw9a_owner")
        branch_b = self.store.create_folder(ws, "Branch B", actor="vw9a_owner")
        drawings_a = self.store.create_folder(ws, "Drawings", parent_folder_id=branch_a["id"], actor="vw9a_owner")
        drawings_b = self.store.create_folder(ws, "Drawings", parent_folder_id=branch_b["id"], actor="vw9a_owner")
        movable = self.store.create_folder(ws, "Movable", actor="vw9a_owner")
        client = self._client()

        body = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        row_idx = body.index(f'href="/projects/{doc.project_id}/workspace?view=files&amp;folder={movable["id"]}"')
        panel = body[row_idx:row_idx + 2500]

        # Same bare name ("Drawings") in two different branches - the
        # rendered option text must disambiguate them via ancestor path,
        # not just repeat "Drawings" twice.
        self.assertIn(f'value="{drawings_a["id"]}">Branch A › Drawings<', panel)
        self.assertIn(f'value="{drawings_b["id"]}">Branch B › Drawings<', panel)

        # The id, not the (ambiguous) name, stays authoritative: moving
        # into drawings_a must never land in drawings_b.
        resp = client.post(
            f"/projects/{doc.project_id}/workspace/folders/{movable['id']}/move",
            data={"parent_folder_id": drawings_a["id"]},
        )
        self.assertEqual(resp.status_code, 302)
        ws2 = self.store.get(doc.project_id)
        moved = next(f for f in ws2.folders if f["id"] == movable["id"])
        self.assertEqual(moved["parent_folder_id"], drawings_a["id"])
        self.assertNotEqual(moved["parent_folder_id"], drawings_b["id"])

    def test_root_level_candidate_path_label_is_just_its_own_name(self):
        # A root-level candidate has no ancestors, so its path_label must
        # equal its bare name (no leading separator, no empty segments) -
        # the degenerate case of the same _folder_path() derivation the
        # nested case above exercises.
        doc = self._ingest("VW9A Root Path Label Project")
        ws = self.store.get(doc.project_id)
        target = self.store.create_folder(ws, "Elsewhere", actor="vw9a_owner")
        movable = self.store.create_folder(ws, "Movable Root", actor="vw9a_owner")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        row_idx = body.index(f'href="/projects/{doc.project_id}/workspace?view=files&amp;folder={movable["id"]}"')
        panel = body[row_idx:row_idx + 2500]
        self.assertIn(f'value="{target["id"]}">Elsewhere<', panel)


# ---------------------------------------------------------------------------
# A4 - delete-cancellation return context (request-level, no browser needed).
# ---------------------------------------------------------------------------

class DeleteCancelReturnContextTests(_BaseTestCase):
    def test_delete_cancel_returns_to_parent_folder_context_for_a_nested_folder(self):
        doc = self._ingest("VW9A Nested Delete Cancel Project")
        ws = self.store.get(doc.project_id)
        parent = self.store.create_folder(ws, "Parent", actor="vw9a_owner")
        nested = self.store.create_folder(ws, "Nested Empty", parent_folder_id=parent["id"], actor="vw9a_owner")
        client = self._client()

        confirm_page = client.post(
            f"/projects/{doc.project_id}/workspace/folders/{nested['id']}/delete", data={},
        ).get_data(as_text=True)
        self.assertIn(
            f'href="/projects/{doc.project_id}/workspace?view=files&amp;folder={parent["id"]}"',
            confirm_page,
        )

    def test_delete_cancel_returns_to_bare_files_root_for_a_root_level_folder(self):
        doc = self._ingest("VW9A Root Delete Cancel Project")
        ws = self.store.get(doc.project_id)
        root_level = self.store.create_folder(ws, "Root Level Empty", actor="vw9a_owner")
        client = self._client()

        confirm_page = client.post(
            f"/projects/{doc.project_id}/workspace/folders/{root_level['id']}/delete", data={},
        ).get_data(as_text=True)
        self.assertIn(f'href="/projects/{doc.project_id}/workspace?view=files"', confirm_page)
        self.assertNotIn("folder=None", confirm_page)
        self.assertNotIn("folder=none", confirm_page)

    def test_cancelling_from_the_confirm_page_actually_lands_on_the_recorded_back_link(self):
        # End-to-end: follow the SAME link the page rendered, confirm it
        # is a real, working route (not merely a plausible-looking href).
        doc = self._ingest("VW9A Delete Cancel Navigation Project")
        ws = self.store.get(doc.project_id)
        parent = self.store.create_folder(ws, "Parent Nav", actor="vw9a_owner")
        nested = self.store.create_folder(ws, "Nested Nav", parent_folder_id=parent["id"], actor="vw9a_owner")
        client = self._client()
        confirm_page = client.post(
            f"/projects/{doc.project_id}/workspace/folders/{nested['id']}/delete", data={},
        ).get_data(as_text=True)
        href_match = re.search(r'<a href="([^"]+)" style="color:var\(--text-secondary\);">\s*&larr;', confirm_page)
        self.assertIsNotNone(href_match)
        back_url = href_match.group(1).replace("&amp;", "&")
        resp = client.get(back_url)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("Nested Nav", body)  # genuinely landed inside Parent Nav's own listing


# ---------------------------------------------------------------------------
# A1 / A3 - genuine browser-executed JS/CSS evidence.
# ---------------------------------------------------------------------------

_FAKE_ORIGIN = "http://vw9a-files-cockpit-test.invalid"


@unittest.skipUnless(_BROWSER_AVAILABLE, _SKIP_REASON)
class RealBrowserFolderMenuTests(_BaseTestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        cls.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        cls.folder_menus_js = _FILES_FOLDER_MENUS_JS_PATH.read_text(encoding="utf-8")

    def _render(self, client, url) -> str:
        body_html = client.get(url).get_data(as_text=True)
        combined_style = f"<style>{self.tokens_css}\n{self.main_css}</style>"
        html, n = re.subn(
            r'<link[^>]*href="[^"]*tokens\.css[^"]*"[^>]*>\s*'
            r'<link[^>]*href="[^"]*main\.css[^"]*"[^>]*>',
            lambda _m: combined_style,
            body_html, count=1,
        )
        assert n == 1
        html, n2 = re.subn(
            r'<script[^>]+src="[^"]*files_folder_menus\.js[^"]*"[^>]*></script>',
            lambda _m: f"<script>{self.folder_menus_js}</script>", html, count=1,
        )
        assert n2 == 1
        html = re.sub(r'<script[^>]+src="[^"]*"[^>]*></script>', "", html)
        return html

    def _serve_and_capture_navigation(self, page, entry_path, html):
        def on_route(route):
            url = route.request.url
            if url == _FAKE_ORIGIN + entry_path:
                route.fulfill(status=200, content_type="text/html", body=html)
            else:
                route.abort()
        page.route(_FAKE_ORIGIN + "/**", on_route)

    def test_opening_one_folder_menu_closes_another_and_outside_click_dismisses(self):
        # Two ADJACENT rows deliberately - this is also a regression
        # proof for a real reachability defect found while writing this
        # test: the panel used to be a floating position:absolute
        # overlay, tall enough (three stacked forms) to visually cover
        # the very next row's own trigger, which made it unclickable
        # (and unreachable even via focus()+Enter) until the first menu
        # was closed. The panel now renders in-flow (main.css's own
        # .files-folder-row:has(.files-folder-actions[open]) rule) and
        # pushes row 2 down instead of covering it, so an ordinary,
        # un-forced click on row 2's trigger while row 1's menu is open
        # must work directly - exactly what this test does.
        doc = self._ingest("VW9A Menu Exclusivity Project")
        ws = self.store.get(doc.project_id)
        self.store.create_folder(ws, "Alpha", actor="vw9a_owner")
        self.store.create_folder(ws, "Beta", actor="vw9a_owner")
        client = self._client()
        entry_path = f"/projects/{doc.project_id}/workspace?view=files"
        html = self._render(client, entry_path)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1200, "height": 800})
                self._serve_and_capture_navigation(page, entry_path, html)
                page.goto(_FAKE_ORIGIN + entry_path, wait_until="load")

                rows = page.query_selector_all(".files-folder-actions")
                self.assertEqual(len(rows), 2)
                first, last = rows[0], rows[1]

                # <details>'s own "toggle" event is dispatched as a
                # queued task, not synchronously with the click that
                # flips its `open` IDL attribute (current HTML spec) -
                # the exclusivity-closing logic lives in that event's
                # own handler, so each step waits on the actual SIDE
                # EFFECT (the OTHER menu's state changing), not on the
                # clicked element's own `open` flipping.
                first.query_selector("summary").click()
                page.wait_for_function("document.querySelectorAll('.files-folder-actions')[0].open === true")

                # Deliberately NOT force=True - an un-forced click that
                # succeeds IS the reachability proof.
                last.query_selector("summary").click(timeout=5000)
                page.wait_for_function("document.querySelectorAll('.files-folder-actions')[0].open === false")
                self.assertIsNone(first.get_attribute("open"), "opening the second menu must close the first")
                self.assertIsNotNone(last.get_attribute("open"))

                # Outside click dismisses the open menu (page header
                # text, well above the folder list, is never covered by
                # any panel).
                page.click("text=Owner Workspace")
                page.wait_for_function("document.querySelectorAll('.files-folder-actions')[1].open === false")
                self.assertIsNone(last.get_attribute("open"))
            finally:
                browser.close()

    def test_folder_menu_opens_via_keyboard_and_escape_dismisses_and_restores_focus(self):
        # A single, unobstructed menu - isolates keyboard semantics
        # (native <summary> Enter/Space activation; Escape dismissal;
        # focus returning to the trigger, not lost to <body>) from the
        # exclusivity/reachability concerns the other test covers.
        doc = self._ingest("VW9A Keyboard Menu Project")
        ws = self.store.get(doc.project_id)
        self.store.create_folder(ws, "Solo Folder", actor="vw9a_owner")
        client = self._client()
        entry_path = f"/projects/{doc.project_id}/workspace?view=files"
        html = self._render(client, entry_path)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1200, "height": 800})
                self._serve_and_capture_navigation(page, entry_path, html)
                page.goto(_FAKE_ORIGIN + entry_path, wait_until="load")

                menu = page.query_selector(".files-folder-actions")
                summary = menu.query_selector("summary")

                summary.focus()
                page.keyboard.press("Enter")
                page.wait_for_function("document.querySelector('.files-folder-actions').open === true")
                self.assertIsNotNone(menu.get_attribute("open"))

                page.keyboard.press("Escape")
                page.wait_for_function("document.querySelector('.files-folder-actions').open === false")
                self.assertIsNone(menu.get_attribute("open"))
                focused_label = page.evaluate("document.activeElement.getAttribute('aria-label')")
                self.assertEqual(focused_label, summary.get_attribute("aria-label"))
            finally:
                browser.close()

    def test_folder_actions_panel_stays_in_bounds_at_a_representative_narrow_division_width(self):
        # panel=1 -> panel_shell.html, the SAME minimal document a
        # multi-Display division's own <iframe> actually renders - and
        # 360px is inside the governing prompt's own "representative
        # center-workspace widths around 300-400px", well below the
        # pre-existing 900px .files-roots grid breakpoint (already
        # verified separately). The panel is in-flow unconditionally now
        # (not just below a narrow-width breakpoint - see A1/A3's own
        # main.css comment), so this also doubles as evidence that
        # holds at any width, this one included.
        doc = self._ingest("VW9A Narrow Division Project")
        ws = self.store.get(doc.project_id)
        self.store.create_folder(ws, "Narrow Test Folder", actor="vw9a_owner")
        client = self._client()
        entry_path = f"/projects/{doc.project_id}/workspace?view=files&panel=1"
        html = self._render(client, entry_path)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 360, "height": 700})
                self._serve_and_capture_navigation(page, entry_path, html)
                page.goto(_FAKE_ORIGIN + entry_path, wait_until="load")

                row = page.query_selector(".files-folder-actions")
                self.assertIsNotNone(row)
                row.query_selector("summary").click()
                panel = page.query_selector(".files-folder-actions-panel")
                self.assertIsNotNone(panel)

                position = page.evaluate(
                    "getComputedStyle(document.querySelector('.files-folder-actions-panel')).position"
                )
                self.assertEqual(position, "static", "panel must be in-flow, never a floating absolute overlay")

                box = panel.bounding_box()
                self.assertIsNotNone(box)
                self.assertGreaterEqual(round(box["x"]), 0, "panel must not escape the left edge of the viewport")
                self.assertLessEqual(round(box["x"] + box["width"]), 360, "panel must not escape the right edge")

                # The Rename field specifically (the control the original
                # cockpit finding flagged as "taken out of reach") must be
                # genuinely visible and clickable, not merely present in
                # the DOM.
                rename_input = page.query_selector('.files-folder-actions-panel input[name="name"]')
                self.assertIsNotNone(rename_input)
                self.assertTrue(rename_input.is_visible())
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
