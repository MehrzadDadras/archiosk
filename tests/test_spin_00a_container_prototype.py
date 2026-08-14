"""
CLAUDE-SPIN-00A - Spin container comparison prototype (retired, see below).
CLAUDE-SPIN-01 - Spin's selected canonical container grammar.

CLAUDE-SPIN-00A built three container alternatives (Compact Control Stack /
Instrument Panel / Progressive Engagement) behind a dev-only comparison
switcher and gave the Product Owner a live route to compare them. Following
SPIN-00A/00B's comparison, the Product Owner selected Alternative A as the
base, plus one incorporated characteristic from Alternative B - the status
badge and active-set summary paired together in one header block
(`.spin-status-strip`) so engagement state reads at a glance without
scrolling. Explicitly NOT adopted: B's physical Engaged/Not-Engaged row
regrouping, and C's always-visible engagement-sequence display. The dev-only
switcher and the two unselected variants' markup were removed accordingly -
`SpinRetirementTests` below is the explicit regression guard against
reintroducing that dead comparison code, the same convention this
repository's own `DialogRetirementTests` (test_p40vw8_project_switch_and_
chooser.py) already established for a prior retired-mechanism regression.

Covers `templates/_spin_prototype.html` (the one canonical grammar, built
from shared right-panel primitives - `macros.tool_pane`, `.tool-control-row`,
`.tool-toggle`, `.review-state-badge`, `.active-set-summary`, `.gauge-slot`;
see static/css/main.css's own "Spin canonical grammar" section),
`routes/workspace.py`'s `?spin=1` flag, and the Toolbox launcher
(`toolbox.spin-launcher`) that opens it.

Still a container/interaction-selection prototype - no real evidence
filtering, no persistence, no route mutates anything. The tests below are
structural (server-rendered markup) plus one explicit nonmutation proof; the
actual toggle INTERACTION logic lives in static/js/spin_prototype.js and is
not exercised here (no browser automation tool is connected in this
environment, consistent with every other VW/E-stage test file in this
repository).

Every ingestion call spies on BHiveParser.parse rather than letting it
run for real (existing repo-wide hermetic-test convention).

Run via:

    python -m unittest tests.test_spin_00a_container_prototype -v
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import DESIGN_BUILDER_PROPONENT
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseSpinTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_spin00a_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="spin_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="spin_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="spin_owner", project_name="Spin Prototype Project")

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

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
                    operating_environment=DESIGN_BUILDER_PROPONENT, owner=owner, project_name=project_name,
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

    def _workspace_url(self, spin=False):
        url = f"/projects/{self.doc.project_id}/workspace"
        return url + "?spin=1" if spin else url


class SpinLauncherTests(_BaseSpinTestCase):
    def test_launcher_present_on_default_toolbox_view(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url()).get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.spin-launcher"', body)
        self.assertIn(f'href="/projects/{self.doc.project_id}/workspace?spin=1"', body)

    def test_launcher_reaches_the_authorized_workspace_route_only(self):
        # No new authorization surface - a non-project user still can't
        # reach it, exactly like every other Toolbox/workspace view.
        outsider = self._client_as("spin_outsider", 2, role="read_only")
        resp = outsider.get(self._workspace_url(spin=True))
        self.assertEqual(resp.status_code, 404)

    def test_default_toolbox_view_unaffected_without_the_flag(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url()).get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.project-intelligence"', body)
        self.assertNotIn('data-ui-ref="spin.pane"', body)


class SpinRetirementTests(_BaseSpinTestCase):
    """CLAUDE-SPIN-01: explicit regression guard against reintroducing the
    retired dev-only comparison switcher or the two unselected variants -
    all dead code once the Product Owner made a selection, removed outright
    rather than left unreachable (same reasoning as this repo's own prior
    DialogRetirementTests)."""

    def test_dev_switcher_markup_is_gone(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertNotIn("spin.dev-switcher", body)
        self.assertNotIn("DEV COMPARISON", body)

    def test_unselected_variants_are_gone(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        for retired_ref in ("spin.variant-a", "spin.variant-b", "spin.variant-c"):
            self.assertNotIn(retired_ref, body)
        self.assertNotIn("Instrument Panel", body)
        self.assertNotIn("Progressive Engagement", body)

    def test_b_engaged_disengaged_regrouping_is_gone(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertNotIn(">Engaged<", body)
        self.assertNotIn("Not Engaged", body)
        self.assertNotIn("spin.variant-b.engaged-list", body)
        self.assertNotIn("spin.variant-b.disengaged-list", body)

    def test_c_visible_sequence_display_is_gone(self):
        # The underlying engagement-ORDER tracking is deliberately kept in
        # static/js/spin_prototype.js (harmless, unsurfaced) - only the
        # VISIBLE per-row index/summary markup is retired.
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertNotIn("spin.variant-c.sequence", body)
        self.assertNotIn("data-spin-index", body)
        self.assertNotIn("spin-sequence-index", body)


class SpinContainerRenderTests(_BaseSpinTestCase):
    def test_spin_mode_renders_the_one_canonical_pane(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertIn('data-ui-ref="spin.pane"', body)
        self.assertIn("Spin — Evidence Isolation", body)

    def test_spin_mode_suppresses_the_default_project_intelligence_view(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertNotIn('data-ui-ref="toolbox.project-intelligence"', body)

    def test_status_strip_pairs_badge_and_summary_in_one_header_block(self):
        # The one characteristic incorporated from Alternative B, per the
        # Product Owner's own selection: status + active-set summary
        # grouped together, readable without scrolling.
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertIn('data-ui-ref="spin.status-strip"', body)
        strip = body[body.index('data-ui-ref="spin.status-strip"'):]
        strip = strip[:strip.index("</div>", strip.index("</div>") + 1) + len("</div>")]
        self.assertIn('data-ui-ref="spin.status"', strip)
        self.assertIn('data-ui-ref="spin.summary"', strip)

    def test_built_from_shared_primitives_not_a_new_css_world(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        for shared_class in ("workspace-pane", "tool-control-row", "tool-toggle", "review-state-badge", "active-set-summary", "gauge-slot"):
            self.assertIn(shared_class, body, shared_class)

    def test_shows_the_full_representative_discipline_set(self):
        # Many-item stress test - the 13-entry prototype list (not written
        # into the Project itself - see SpinNonmutationTests below).
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertIn("Architecture", body)
        self.assertIn("Commissioning", body)
        self.assertEqual(body.count('data-ui-ref="spin.toggle"'), 13)

    def test_rows_carry_no_relocation_affordance(self):
        # Spatial stability was the Product Owner's own explicit reason for
        # selecting A over B - there is exactly one discipline list, not a
        # pair of containers rows could move between.
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertEqual(body.count('data-spin-list'), 1)

    def test_baseline_status_by_default(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertIn(">Baseline<", body)
        self.assertIn("None engaged", body)

    def test_global_controls_present(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        for suffix in ("all-on", "all-off", "reset"):
            self.assertIn(f'data-spin-action="{suffix}"', body)

    def test_pulse_placeholder_present_and_neutral_no_fabricated_score(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertIn("Project Pulse", body)
        self.assertIn("Future analytical layer", body)
        # No numeric health/risk score anywhere inside a gauge-slot.
        self.assertNotIn("Project Pulse: ", body)

    def test_toggles_carry_switch_semantics(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        # id="toolbox-eye-divider" is base.html's own next sibling
        # immediately after the Toolbox <aside> closes, so it reliably
        # follows the Spin fragment in document order.
        spin_fragment = body[body.index('data-ui-ref="spin.pane"'):body.index('id="toolbox-eye-divider"')]
        self.assertEqual(spin_fragment.count('aria-pressed="false"'), 13)  # 13 discipline toggles, all off by default


class SpinNonmutationTests(_BaseSpinTestCase):
    def test_visiting_spin_mode_does_not_change_operating_environment(self):
        before = self._store().get(self.doc.project_id).operating_environment
        client = self._client_as("spin_owner", 1)
        client.get(self._workspace_url(spin=True))
        after = self._store().get(self.doc.project_id).operating_environment
        self.assertEqual(before, after)
        self.assertEqual(after, DESIGN_BUILDER_PROPONENT)

    def test_visiting_spin_mode_does_not_change_real_project_content(self):
        # `item_reviewed_at`/`last_viewed_by` are deliberately excluded -
        # both are this route's own pre-existing "since last visit"
        # bookkeeping (services/case_workspace.py), updated on ANY
        # workspace visit regardless of ?spin=1, not something Spin
        # introduces. Every other field - sources, requirements,
        # findings, operating_environment, display fields - must be
        # byte-identical.
        excluded = ("item_reviewed_at", "last_viewed_by")
        before = asdict(self._store().get(self.doc.project_id))
        for key in excluded:
            before.pop(key, None)
        client = self._client_as("spin_owner", 1)
        client.get(self._workspace_url(spin=True))
        after = asdict(self._store().get(self.doc.project_id))
        for key in excluded:
            after.pop(key, None)
        self.assertEqual(before, after)

    def test_prototype_discipline_labels_never_appear_in_the_stored_workspace(self):
        client = self._client_as("spin_owner", 1)
        client.get(self._workspace_url(spin=True))
        workspace = self._store().get(self.doc.project_id)
        stored_text = str(asdict(workspace))
        self.assertNotIn("Commissioning", stored_text)


class SpinRightPanelRegressionTests(_BaseSpinTestCase):
    def test_spin_prototype_js_only_loaded_on_real_workspace_pages(self):
        client = self._client_as("spin_owner", 1)
        gateway_body = client.get("/gateway").get_data(as_text=True)
        self.assertNotIn("spin_prototype.js", gateway_body)
        workspace_body = client.get(self._workspace_url()).get_data(as_text=True)
        self.assertIn("spin_prototype.js", workspace_body)

    def test_toolbox_maximize_and_eye_pane_unaffected_by_spin_mode(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.maximize"', body)
        self.assertIn('data-ui-ref="eye.panel"', body)

    def test_investigation_and_document_selection_still_take_a_normal_workspace_view_without_the_flag(self):
        source_id = self._store().get(self.doc.project_id).sources[0]["id"]
        client = self._client_as("spin_owner", 1)
        body = client.get(f"/projects/{self.doc.project_id}/workspace?source={source_id}").get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.document"', body)
        self.assertNotIn('data-ui-ref="spin.pane"', body)


if __name__ == "__main__":
    unittest.main()
