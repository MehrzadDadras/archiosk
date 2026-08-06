"""
CLAUDE-P40-VW8-QA1 (Governed Display Tab System sufficiency review).

VW8 (see tests/test_p40vw8_governed_display_tab_system.py) audited and
formalized this app's two DYNAMIC-RECORD Display tab mechanisms (Document
tab strip, Investigation Attention Positions) but never generalized the
separate STABLE-SURFACE pattern Overview/Chats already use (a Project-level
singleton, no tab-strip pill, represented via Lists active-state + a
Display division header). The product-owner purpose of VW8 was to prove a
real Display foundation for a *future* dedicated, persistent Files Display
tab - which, per VW8's own audit, would be a second stable surface, not a
third dynamic-record tab strip.

Grounded repository evidence that this did NOT yet exist as a real
extension point, before this stage: `directory_view == 'overview'` was a
bare string literal independently repeated in routes/workspace.py's own
`?view=` whitelist (`if directory_view not in ("overview",)`), the
breadcrumb in templates/base.html, and the Display division-0 header name
in templates/case_workspace.html - three copies with nothing enforcing
they stay in sync, and no place naming "the set of registered stable
kinds" at all. static/js/case_workspace.js's own `kind` dispatch
(buildPanelUrl/populateDivision/syncListsActiveState) had the same
problem one layer down, for the multi-Display split-screen embedding path:
three independent `kind === 'case' || kind === 'overview' || kind ===
'new-case'`-shaped chains, one of which (`syncListsActiveState`'s own
final fallback, `: 'a[data-view="overview"]'`) was a genuine latent bug -
it applied to ANY unrecognized kind, not only 'overview', so a future
unknown kind would have silently marked Overview's own Lists leaf active.

Fix: `routes.workspace.STABLE_DIRECTORY_KINDS` (server) and
`static/js/case_workspace.js`'s `PANEL_KINDS` (client) are now the two
single sources of truth those sites read from. This is deliberately NOT
Files itself - no Lists leaf, no picker entry, no content branch exists
for anything but 'overview' - so registering a new kind's IDENTITY alone
can never fabricate placeholder content; only a kind's own dedicated
`directory_view == '<kind>'` content branch (added later, same as
Overview's) renders anything.

These tests prove the extension point is real by registering a synthetic,
non-user-facing test-only kind into the registry for the duration of a
test (Section A's own suggested proof technique) and confirming the
breadcrumb, division-0 header, and `?view=` whitelist all pick it up with
ZERO template changes - while its content area stays genuinely blank,
and the pre-existing "?case=/?source= always wins" precedence rule still
holds for it exactly as it already does for 'overview'.
"""
from __future__ import annotations

import io
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
import routes.workspace as workspace_routes

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CASE_WORKSPACE_JS_PATH = _REPO_ROOT / "static" / "js" / "case_workspace.js"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_vw8qa1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="vw8qa1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename="spec.pdf", content=b"content", owner="vw8qa1_owner"):
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

    def _client(self, username="vw8qa1_owner", user_id=1):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = "admin"
        return client

    def _create_case(self, client, project_id, title):
        resp = client.post(f"/projects/{project_id}/workspace/cases", data={"title": title, "objective": ""})
        location = resp.headers["Location"]
        return location.split("case=")[1].split("&")[0]


class StableSurfaceExtensionPointTests(_BaseTestCase):
    _SYNTHETIC_KIND = "_qa1_test_surface"
    _SYNTHETIC_LABEL = "QA1 Test Surface"

    def test_overview_is_registered_in_the_shared_dict_not_an_independent_literal(self):
        self.assertEqual(workspace_routes.STABLE_DIRECTORY_KINDS.get("overview"), "Overview")

    def test_registering_a_new_stable_kind_flows_into_breadcrumb_and_division_header(self):
        doc = self._ingest("VW8-QA1 Extension Point Project")
        client = self._client()
        with patch.dict(workspace_routes.STABLE_DIRECTORY_KINDS, {self._SYNTHETIC_KIND: self._SYNTHETIC_LABEL}):
            resp = client.get(f"/projects/{doc.project_id}/workspace?view={self._SYNTHETIC_KIND}")
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        # Breadcrumb (templates/base.html) - now driven by the shared
        # directory_view_label, not a hardcoded 'Overview' literal.
        self.assertIn(f'<span class="workspace-topbar-doc">{self._SYNTHETIC_LABEL}</span>', body)
        # Display division-0 header (templates/case_workspace.html) -
        # same shared label, same generalization, independently confirmed.
        header_idx = body.index('display-division-header-name')
        self.assertIn(self._SYNTHETIC_LABEL, body[header_idx:header_idx + 400])

    def test_unregistered_view_value_still_degrades_to_no_selection(self):
        doc = self._ingest("VW8-QA1 Unregistered View Project")
        client = self._client()
        resp = client.get(f"/projects/{doc.project_id}/workspace?view=not_a_real_registered_kind")
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("not_a_real_registered_kind", body)
        self.assertNotIn('id="project-overview"', body)

    def test_real_case_selection_still_overrides_a_registered_stable_kind(self):
        doc = self._ingest("VW8-QA1 Precedence Project")
        client = self._client()
        case_id = self._create_case(client, doc.project_id, "Precedence Investigation")
        with patch.dict(workspace_routes.STABLE_DIRECTORY_KINDS, {self._SYNTHETIC_KIND: self._SYNTHETIC_LABEL}):
            resp = client.get(f"/projects/{doc.project_id}/workspace?view={self._SYNTHETIC_KIND}&case={case_id}")
        body = resp.get_data(as_text=True)
        self.assertIn("Precedence Investigation", body)
        self.assertNotIn(self._SYNTHETIC_LABEL, body)

    def test_registering_a_kind_alone_never_fabricates_overview_specific_content(self):
        # Section 9's own "no placeholder Files control": registering an
        # identity in STABLE_DIRECTORY_KINDS must never, by itself, render
        # ANY real content - only a kind's own dedicated
        # `directory_view == '<kind>'` branch does that (Overview's own,
        # unchanged). This synthetic kind has no such branch anywhere.
        doc = self._ingest("VW8-QA1 No Placeholder Project")
        client = self._client()
        with patch.dict(workspace_routes.STABLE_DIRECTORY_KINDS, {self._SYNTHETIC_KIND: self._SYNTHETIC_LABEL}):
            resp = client.get(f"/projects/{doc.project_id}/workspace?view={self._SYNTHETIC_KIND}")
        body = resp.get_data(as_text=True)
        self.assertNotIn("Project Operating Environment", body)
        self.assertNotIn('id="project-overview"', body)


class PanelKindsClientRegistryTests(unittest.TestCase):
    """Source-text evidence that the client-side 'kind' dispatch used by
    the multi-Display split-screen embedding path (a separate mechanism
    from the primary ?view= navigation above - see PANEL_KINDS' own header
    comment in case_workspace.js) is now one shared table, not three
    independently-maintained if/elif chains."""

    def setUp(self):
        self.js = _CASE_WORKSPACE_JS_PATH.read_text(encoding="utf-8")

    def test_panel_kinds_table_exists_with_the_three_real_kinds(self):
        self.assertIn("const PANEL_KINDS = {", self.js)
        table_idx = self.js.index("const PANEL_KINDS = {")
        table_slice = self.js[table_idx:table_idx + 1200]
        for kind in ("case:", "overview:", "'new-case':"):
            self.assertIn(kind, table_slice)
        # 'files' must NOT be registered - no branch, no picker entry
        # anywhere (Section 9's own "no placeholder Files control").
        self.assertNotIn("files:", table_slice)

    def test_build_panel_url_reads_the_shared_table_not_its_own_chain(self):
        start = self.js.index("function buildPanelUrl(")
        body = self.js[start:start + 500]
        self.assertIn("PANEL_KINDS[kind]", body)
        self.assertNotIn("kind === 'case'", body)
        self.assertNotIn("kind === 'overview'", body)

    def test_populate_division_reads_the_shared_table_not_its_own_chain(self):
        start = self.js.index("function populateDivision(")
        # CLAUDE-MM4 widened this window (was 1200) - its own kind ===
        # 'source'/'drawing' branch grew a real explanatory comment about
        # why THAT branch stays a direct DOM insertion rather than the
        # PANEL_KINDS/iframe path below, pushing PANEL_KINDS[kind] further
        # into the function body without changing this test's own actual
        # assertion (PANEL_KINDS[kind] is still there, unconditionally).
        body = self.js[start:start + 2200]
        self.assertIn("PANEL_KINDS[kind]", body)
        self.assertNotIn("kind === 'case' || kind === 'overview'", body)

    def test_sync_lists_active_state_no_longer_has_the_unconditional_overview_fallback(self):
        start = self.js.index("function syncListsActiveState(")
        body = self.js[start:start + 1000]
        self.assertIn("PANEL_KINDS[kind]", body)
        # The fixed latent bug: an unrecognized kind used to silently
        # inherit Overview's own Lists-active selector via an
        # unconditional final ternary branch - it must now resolve to no
        # selector (skipped) instead.
        self.assertNotIn(': \'a[data-view="overview"]\';', body)


if __name__ == "__main__":
    unittest.main()
