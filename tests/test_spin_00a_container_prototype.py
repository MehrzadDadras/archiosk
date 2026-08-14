"""
CLAUDE-SPIN-00A - Spin container comparison prototype.

Covers `templates/_spin_prototype.html` (three container alternatives,
built from shared right-panel grammar - `macros.tool_pane`,
`.tool-control-row`, `.tool-toggle`, `.review-state-badge`,
`.active-set-summary`, `.gauge-slot`; see static/css/main.css's own
"CLAUDE-SPIN-00A" section), `routes/workspace.py`'s `?spin=1` flag, and
the Toolbox launcher (`toolbox.spin-launcher`) that opens it.

This is a container/interaction-selection prototype only - no real
evidence filtering, no persistence, no route mutates anything. The tests
below are structural (server-rendered markup) plus one explicit
nonmutation proof; the actual toggle/switch INTERACTION logic lives in
static/js/spin_prototype.js and is not exercised here (no browser
automation tool is connected in this environment, consistent with every
other VW/E-stage test file in this repository).

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
        self.assertNotIn('data-ui-ref="spin.dev-switcher"', body)


class SpinContainerRenderTests(_BaseSpinTestCase):
    def test_spin_mode_renders_the_dev_switcher_and_all_three_variants(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertIn('data-ui-ref="spin.dev-switcher"', body)
        for ref in ("spin.dev-switcher.a", "spin.dev-switcher.b", "spin.dev-switcher.c"):
            self.assertIn(f'data-ui-ref="{ref}"', body)
        for ref in ("spin.variant-a", "spin.variant-b", "spin.variant-c"):
            self.assertIn(f'data-ui-ref="{ref}"', body)

    def test_spin_mode_suppresses_the_default_project_intelligence_view(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertNotIn('data-ui-ref="toolbox.project-intelligence"', body)

    def test_only_variant_a_visible_by_default(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        variant_a = body[body.index('data-spin-variant="a"'):body.index('data-spin-variant="b"')]
        variant_b = body[body.index('data-spin-variant="b"'):body.index('data-spin-variant="c"')]
        variant_c = body[body.index('data-spin-variant="c"'):]
        self.assertNotIn("hidden", variant_a.split(">", 1)[0])
        self.assertIn("hidden", variant_b.split(">", 1)[0])
        self.assertIn("hidden", variant_c.split(">", 1)[0])

    def test_each_variant_built_from_the_same_shared_primitives(self):
        # Not three separate CSS worlds - the governing prompt's own
        # explicit requirement.
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        for shared_class in ("workspace-pane", "tool-control-row", "tool-toggle", "review-state-badge", "active-set-summary", "gauge-slot"):
            self.assertGreaterEqual(body.count(shared_class), 3, shared_class)

    def test_all_variants_show_the_full_representative_discipline_set(self):
        # Many-item stress test - the same 13-entry prototype list appears
        # once per variant (not written into the Project itself - see
        # SpinNonmutationTests below). Each discipline name appears twice
        # per variant (the visible row label plus its data-spin-name
        # attribute), so 3 variants -> 6 occurrences.
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertEqual(body.count("Architecture"), 6)
        self.assertEqual(body.count("Commissioning"), 6)
        self.assertEqual(body.count('data-ui-ref="spin.variant-a.toggle"'), 13)
        self.assertEqual(body.count('data-ui-ref="spin.variant-b.toggle"'), 13)
        self.assertEqual(body.count('data-ui-ref="spin.variant-c.toggle"'), 13)

    def test_baseline_status_and_no_evidence_isolated_yet_by_default(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertEqual(body.count(">Baseline<"), 3)
        self.assertIn('data-spin-switch="a" aria-pressed="true"', body)
        self.assertIn('data-spin-switch="b" aria-pressed="false"', body)
        self.assertIn('data-spin-switch="c" aria-pressed="false"', body)

    def test_global_controls_present_per_variant(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        for suffix in ("all-on", "all-off", "reset"):
            self.assertEqual(body.count(f'data-spin-action="{suffix}"'), 3, suffix)

    def test_pulse_placeholder_present_and_neutral_no_fabricated_score(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertEqual(body.count("Project Pulse"), 3)
        self.assertEqual(body.count("Future analytical layer"), 3)
        # No numeric health/risk score anywhere inside a gauge-slot.
        self.assertNotIn("Project Pulse: ", body)

    def test_variant_c_carries_a_distinct_ordered_sequence_summary(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertIn('data-ui-ref="spin.variant-c.sequence"', body)
        self.assertIn('data-spin-index', body)

    def test_variant_b_groups_rows_into_engaged_and_disengaged_containers(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertIn('data-ui-ref="spin.variant-b.engaged-list"', body)
        self.assertIn('data-ui-ref="spin.variant-b.disengaged-list"', body)

    def test_switcher_and_toggles_carry_switch_semantics(self):
        client = self._client_as("spin_owner", 1)
        body = client.get(self._workspace_url(spin=True)).get_data(as_text=True)
        self.assertIn('role="group"', body)
        self.assertIn('aria-label="Spin container alternative', body)
        # Scoped to the Spin fragment itself (base.html's own maximize
        # buttons elsewhere on the page also carry aria-pressed="false",
        # so an unscoped whole-body count would be fragile/unrelated).
        # id="toolbox-eye-divider" is base.html's own next sibling
        # immediately after the Toolbox <aside> closes, so it reliably
        # follows the Spin fragment in document order (unlike
        # id="chat-region", which base.html renders BEFORE the Toolbox).
        spin_fragment = body[body.index('data-ui-ref="spin.dev-switcher"'):body.index('id="toolbox-eye-divider"')]
        self.assertEqual(spin_fragment.count('aria-pressed="false"'), 13 * 3 + 2)  # 39 discipline toggles (off) + 2 unselected dev-switcher buttons


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
        self.assertNotIn('data-ui-ref="spin.dev-switcher"', body)


if __name__ == "__main__":
    unittest.main()
