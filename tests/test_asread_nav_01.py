"""CLAUDE-ASREAD-NAV-01: the As-Read route must be reachable by clicking.

The Drawing Understanding / As-Read route shipped with the Drawing Intelligence
tranche and worked, but NOTHING in the product linked to it. Its only other
references were its own two POST redirects back to itself, so the only way to
open it was to type the URL. Real As-Read state was promoted into a live project
and remained invisible to the person who owned it.

So the load-bearing test here is not that the anchor exists - it is
`test_no_orphan_route`: it asserts that a template, not just a redirect, points
at the endpoint. That is the assertion that would have failed before this work
and the one that keeps the seam from silently reopening.
"""
from __future__ import annotations

import io
import re
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CaseWorkspaceStore, LEGEND_KIND_SECTION_REFERENCE, LEGEND_STATUS_CONFIRMED,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _file(content: bytes, name: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=name)


class AsReadNavigationTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_asread_nav_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)

        def fake_parse(_parser, _raw, filename):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    _file(b"owner baseline", "owner-program.txt"), self.app,
                    operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="As-Read Nav Fixture",
                )
        self.project_id = self.document.project_id
        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get(self.project_id)
        self.source = self.workspace.sources[0]

        self.snapshot = self.tmp / "snap.png"
        self.snapshot.write_bytes(b"\x89PNG\r\n\x1a\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self, role="read_only"):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "owner"
            session["role"] = role
        return client

    @property
    def workspace_url(self):
        return f"/projects/{self.project_id}/workspace?source={self.source['id']}"

    def _add_items(self, statuses):
        """One legend item per status, so the counts are a real derivation."""
        workspace = self.store.get(self.project_id)
        registered = self.store.register_drawing_sheet_structure(
            workspace, self.source["id"],
            [{"index": 0, "label": "Sheet", "width": 100.0, "height": 100.0,
              "source_rotation": 0, "metadata": {}}], actor="test")
        unit = registered["structural_unit_ids"][0]
        for index, status in enumerate(statuses):
            workspace = self.store.get(self.project_id)
            item = self.store.propose_legend_item(
                workspace, source_id=self.source["id"],
                page_structural_unit_id=unit,
                region={"x": float(index), "y": float(index),
                        "width": 5.0, "height": 5.0},
                proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
                proposed_meaning="probe", interpretation_method="test",
                actor="GO", snapshot_path=str(self.snapshot))
            workspace = self.store.get(self.project_id)
            if status == "confirmed":
                self.store.decide_legend_item(
                    workspace, item["id"], action=LEGEND_STATUS_CONFIRMED,
                    actor="human")
            elif status == "review_needed":
                self.store.flag_legend_item_review(
                    workspace, item["id"], reason="probe", actor="GO")

    # -- the regression this whole file exists for ---------------------------

    def test_no_orphan_route(self):
        """A template must point at the endpoint, not only its own redirects.

        Before CLAUDE-ASREAD-NAV-01 the only references to
        drawing_understanding_review were its definition and two redirects back
        to itself - a working, tested, completely unreachable feature.
        """
        template_hits = [
            path for path in (_REPO_ROOT / "templates").rglob("*.html")
            if "drawing_understanding_review" in path.read_text(encoding="utf-8")
        ]
        self.assertTrue(
            template_hits,
            "No template links to workspace.drawing_understanding_review. The "
            "As-Read surface is reachable only by typing its URL.")

    def test_entry_renders_with_live_counts(self):
        self._add_items(["confirmed", "proposed", "review_needed"])
        body = self._client().get(self.workspace_url).get_data(as_text=True)
        self.assertIn('data-ui-ref="display.document.as-read"', body)
        self.assertIn(
            f"/projects/{self.project_id}/workspace/sources/"
            f"{self.source['id']}/understanding", body)
        self.assertIn("As-Read", body)
        # 3 items exist; one is settled, so two still await a human.
        self.assertIn("3 proposed", body)
        self.assertIn("2 awaiting review", body)

    def test_entry_is_hidden_when_there_is_no_as_read_state(self):
        """No dead link. A Source with no legend items offers no entry."""
        body = self._client().get(self.workspace_url).get_data(as_text=True)
        self.assertNotIn('data-ui-ref="display.document.as-read"', body)

    def test_entry_is_not_admin_gated(self):
        """The route is @login_required, not @admin_required.

        Putting this inside the admin Document Context panel would reproduce
        the exact confusion it exists to end: two unrelated features both
        called "understanding", one of them wrongly restricted.
        """
        self._add_items(["proposed"])
        body = self._client(role="read_only").get(self.workspace_url).get_data(as_text=True)
        self.assertIn('data-ui-ref="display.document.as-read"', body)

    def test_entry_is_outside_the_admin_document_context_panel(self):
        self._add_items(["proposed"])
        body = self._client(role="admin").get(self.workspace_url).get_data(as_text=True)
        self.assertLess(
            body.index('data-ui-ref="display.document.as-read"'),
            body.index('data-ui-ref="display.document.admin-qac"'),
            "The As-Read entry must not sit inside the admin Document Context "
            "panel - it is a different feature on a non-admin route.")

    def test_clicking_the_entry_opens_the_as_read_route(self):
        self._add_items(["proposed", "review_needed"])
        client = self._client()
        body = client.get(self.workspace_url).get_data(as_text=True)
        match = re.search(
            r'data-ui-ref="display\.document\.as-read"\s+href="([^"]+)"', body)
        self.assertIsNotNone(match, "As-Read entry has no href")
        followed = client.get(match.group(1))
        self.assertEqual(followed.status_code, 200)
        self.assertIn("confirm", followed.get_data(as_text=True).lower())

    def test_counts_match_the_understanding_report(self):
        """The template's arithmetic must agree with the page it links to."""
        from services.legend_of_understanding import understanding_report

        self._add_items(["confirmed", "proposed", "review_needed", "proposed"])
        workspace = self.store.get(self.project_id)
        report = understanding_report(self.store, workspace, self.source["id"])
        body = self._client().get(self.workspace_url).get_data(as_text=True)
        self.assertIn("%d proposed" % report["proposed_items"], body)
        self.assertIn("%d awaiting review" % report["awaiting_confirmation"], body)

    def test_amber_treatment_is_applied(self):
        """GO intelligence/action = bold + amber, and never the danger red."""
        self._add_items(["proposed"])
        body = self._client().get(self.workspace_url).get_data(as_text=True)
        self.assertIn("document-asread-action", body)
        css = (_REPO_ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
        block = css[css.index(".document-asread-action"):]
        block = block[:block.index("}")]
        self.assertIn("var(--attention-amber)", block)
        self.assertIn("font-weight: 600", block)
        self.assertNotIn("--failure-red", block)
