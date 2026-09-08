"""CLAUDE-ASREAD-MATRIX-02: the As-Read surface must be governable in minutes.

The previous surface was functionally correct and interactively unusable. On
the real E1 sheet it rendered two family rows and then TWENTY-FIVE individual
rows asking the same question, each fronted by a free-text box and a scope
dropdown that made a one-click answer look like a form to fill in.

Every decision the reviewer needed was already a single button. Nothing but
presentation stood between them and a one-minute review - which is why these
tests assert INTERACTION BURDEN (rows on load, controls on load, clicks to
govern) and not merely that markup exists. A surface that renders every element
correctly and still cannot be finished is the defect being fixed.

Nothing here changes a record. `test_presentation_only_no_record_changed` is
the guard on that.
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
    LEGEND_SCOPE_SOURCE,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _file(content: bytes, name: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=name)


class _AsReadFixture:
    """Fixture only - no assertions. A family of 12 marks: 3 representatives, 9 instances, 9 held for the
    SAME reason - the shape of the real E1 sheet, in miniature."""

    HELD_REASON = "direction was never recorded, and section_reference meaning depends on it"

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_asread_matrix_"))
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
                    project_name="As-Read Matrix Fixture",
                )
        self.project_id = self.document.project_id
        self.store = CaseWorkspaceStore(self.tmp)
        self.source = self.store.get(self.project_id).sources[0]
        self.snapshot = self.tmp / "snap.png"
        self.snapshot.write_bytes(b"\x89PNG\r\n\x1a\n")

        workspace = self.store.get(self.project_id)
        registered = self.store.register_drawing_sheet_structure(
            workspace, self.source["id"],
            [{"index": 0, "label": "Sheet", "width": 100.0, "height": 100.0,
              "source_rotation": 0, "metadata": {}}], actor="test")
        self.unit = registered["structural_unit_ids"][0]

        self.family_id = "fam-matrix-01"
        self.representatives, self.held = [], []
        for index in range(12):
            workspace = self.store.get(self.project_id)
            is_rep = index < 3
            item = self.store.propose_legend_item(
                workspace, source_id=self.source["id"],
                page_structural_unit_id=self.unit,
                region={"x": float(index), "y": 1.0, "width": 5.0, "height": 5.0},
                proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
                proposed_meaning="Section reference. Letter identifies the section.",
                interpretation_method="test", actor="GO",
                snapshot_path=str(self.snapshot) if is_rep else None,
                confidence=0.55, family_id=self.family_id,
                family_role="representative" if is_rep else "instance",
                nearby_label="A")
            if is_rep:
                self.representatives.append(item["id"])
            else:
                workspace = self.store.get(self.project_id)
                self.store.flag_legend_item_review(
                    workspace, item["id"], reason=self.HELD_REASON, actor="GO")
                self.held.append(item["id"])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "owner"
            session["role"] = "read_only"
        return client

    @property
    def url(self):
        return ("/projects/%s/workspace/sources/%s/understanding"
                % (self.project_id, self.source["id"]))

    def _body(self):
        response = self._client().get(self.url)
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    @staticmethod
    def visible(html):
        """Strip CLOSED <details> - their content is not on screen at load.

        Depth-aware on purpose. A naive non-greedy `</details>` stops at the
        FIRST close tag, which here is the nested correction block inside the
        exceptions container - so the exceptions never got stripped and the
        measurement reported 104 controls "visible" when 8 are.
        """
        out, i = [], 0
        while i < len(html):
            m = re.search(r"<details(?![^>]*open)[^>]*>", html[i:])
            if not m:
                out.append(html[i:]); break
            start = i + m.start()
            out.append(html[i:start])
            depth, j = 1, i + m.end()
            while depth and j < len(html):
                nxt = re.search(r"<details[^>]*>|</details>", html[j:])
                if not nxt:
                    j = len(html); break
                depth += 1 if nxt.group(0).startswith("<details") else -1
                j += nxt.end()
            i = j
        return "".join(out)


class AsReadMatrixTests(_AsReadFixture, unittest.TestCase):
    """The 12-mark family: does the matrix render and govern correctly?"""

    # -- the burden the whole change exists to reduce -------------------------

    def test_held_instances_are_collapsed_on_load(self):
        """The 9 held rows must not be open on arrival.

        This is the assertion that would have failed before: the old surface
        rendered every held mark as a top-level row, so E1 opened with 25
        identical questions in front of the reviewer.
        """
        body = self._body()
        self.assertIn('data-ui-ref="drawing-understanding.exceptions"', body)
        exceptions_open = re.search(
            r'<details[^>]*data-ui-ref="drawing-understanding\.exceptions"[^>]*\bopen\b', body)
        self.assertIsNone(exceptions_open, "held marks must be collapsed on load")

    def test_one_family_row_replaces_repeated_instance_prose(self):
        """The reading is stated per QUESTION, never per occurrence.

        With the case layer the reading appears once for the family row and
        once for each DISTINCT open question - here two, because the three
        proposed representatives and the nine held instances ask different
        things. Twelve marks still do not produce twelve readings, which is the
        economy this test has always defended.
        """
        body = self._body()
        self.assertEqual(
            body.count('data-ui-ref="drawing-understanding.family-row"'), 1)
        # Measured against what is ON SCREEN, using this file's own established
        # `visible()` helper - collapsed peers stay in the DOM on purpose, so
        # every case remains reachable with its own crop and controls. Decision
        # economy is about what a reviewer must read, not about withholding
        # evidence from the page.
        readings = self.visible(body).count("Letter identifies the section")
        self.assertLessEqual(readings, 4, "one per distinct question, not per mark")
        self.assertLess(readings, 12)
        self.assertGreaterEqual(
            body.count("Letter identifies the section"), readings,
            "collapsed cases must still be present and expandable")

    def test_representative_crops_are_capped(self):
        """Crops follow REPRESENTATIVES, not occurrences.

        CLAUDE-ASREAD-SURFACE-01 added a case layer above the family bench, so
        the page now carries the same three representative crops twice - once
        per surface - for twelve marks. The assertion is rewritten to the
        intent it always had (a crop per representative, never per occurrence)
        rather than to the single number the previous layout happened to
        produce. Nine crop-less held instances still generate no crops.
        """
        body = self._body()
        crops = body.count('class="legend-snapshot asread-crop"')
        self.assertEqual(crops, 6, "3 representatives, rendered on both surfaces")
        self.assertLess(crops, 12, "never one crop per occurrence")

    def test_decision_columns_exist_for_the_family(self):
        body = self._body()
        for action in ("confirm", "correct", "unknown", "later"):
            self.assertIn(
                'data-ui-ref="drawing-understanding.decision.%s"' % action, body)

    def test_one_click_governs_the_whole_family(self):
        """No form-filling prerequisite: action alone is a complete decision."""
        client = self._client()
        response = client.post(
            "/projects/%s/workspace/understanding/family/%s/decide"
            % (self.project_id, self.family_id),
            data={"action": LEGEND_STATUS_CONFIRMED,
                  "source_id": self.source["id"]},
            follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        workspace = self.store.get(self.project_id)
        reps = self.store.legend_items_for(
            workspace, family_id=self.family_id, family_role="representative")
        self.assertTrue(all(r["status"] == LEGEND_STATUS_CONFIRMED for r in reps))

    def test_correction_control_is_progressive_disclosure(self):
        """The meaning box exists but must not front the decision."""
        body = self._body()
        self.assertIn('data-ui-ref="drawing-understanding.correction"', body)
        correction = body.index('data-ui-ref="drawing-understanding.correction"')
        confirm = body.index('data-ui-ref="drawing-understanding.decision.confirm"')
        self.assertLess(confirm, correction,
                        "the decision buttons must come before the correction form")

    def test_expanding_exceptions_preserves_every_control(self):
        body = self._body()
        self.assertIn('data-ui-ref="drawing-understanding.exception-table"', body)
        self.assertEqual(
            body.count('data-ui-ref="drawing-understanding.row"'), len(self.held))
        self.assertIn('value="informative"', body)   # the per-mark-only action
        self.assertIn('data-ui-ref="drawing-understanding.hold-reason"', body)

    def test_held_marks_are_grouped_by_reason(self):
        body = self._body()
        self.assertIn("1 distinct reason(s) across %d mark(s)" % len(self.held), body)

    # -- honesty of the summary ----------------------------------------------

    def test_no_false_contradiction_label(self):
        """9 marks waiting on an unmeasured direction are not contradictions."""
        body = self._body()
        self.assertIn('data-ui-ref="drawing-understanding.summary-directional"', body)
        self.assertIn("%d</strong> need directional review" % len(self.held), body)
        self.assertNotIn('data-ui-ref="drawing-understanding.summary-contradiction"', body)
        self.assertNotIn("Contradictions", body)

    def test_counts_remain_accurate(self):
        """Counts are per MARK, and the family count says what it counts.

        "repeated-mark family(ies)" became "visual family(ies) - evidence
        grouping, not meaning" under CLAUDE-ASREAD-SURFACE-01: a visual family
        is an evidence-organising mechanism, and letting it read as a semantic
        one is the conflation this tranche has been separating.
        """
        body = self._body()
        self.assertIn("<strong>12</strong> mark(s) recognised", body)
        self.assertIn("<strong>1</strong> visual family(ies)", body)
        self.assertIn("evidence grouping, not meaning", body)
        # Two propositions on one mark must never double the mark count.
        self.assertNotIn("<strong>24</strong>", body)

    def test_confirmed_family_reads_as_settled(self):
        client = self._client()
        client.post(
            "/projects/%s/workspace/understanding/family/%s/decide"
            % (self.project_id, self.family_id),
            data={"action": LEGEND_STATUS_CONFIRMED,
                  "scope_kind": LEGEND_SCOPE_SOURCE,
                  "source_id": self.source["id"]})
        body = self._body()
        self.assertIn('data-ui-ref="drawing-understanding.settled"', body)
        self.assertIn("Confirmed by a person", body)
        self.assertIn("asread-row-settled", body)

    # -- terminology, accessibility, responsiveness ---------------------------

    def test_user_facing_term_is_as_read(self):
        body = self._body()
        self.assertIn("As-Read &mdash; %s" % self.source["name"], body)
        self.assertNotIn("Root", body)

    def test_decisions_are_real_buttons_with_visible_focus(self):
        body = self._body()
        self.assertIn('<button type="submit" name="action" value="confirmed"', body)
        self.assertIn('role="group"', body)
        self.assertIn('aria-label="Your decision for this row"', body)
        css = (_REPO_ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
        block = css[css.index(".asread-decision {"):]
        self.assertIn(":focus-visible", css[css.index(".asread-decision {"):
                                            css.index(".asread-correction")])
        self.assertIn("outline", block[:2000])

    def test_colour_is_not_the_only_state_indicator(self):
        """Every state carries a word or a mark as well as an accent."""
        client = self._client()
        client.post(
            "/projects/%s/workspace/understanding/family/%s/decide"
            % (self.project_id, self.family_id),
            data={"action": LEGEND_STATUS_CONFIRMED, "source_id": self.source["id"]})
        body = self._body()
        self.assertIn("Confirmed by a person", body)
        self.assertIn("need directional review", body)

    def test_go_accent_preserved_and_no_raw_colour_literal(self):
        css = (_REPO_ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
        confirm = css[css.index(".asread-decision-confirm {"):]
        confirm = confirm[:confirm.index("}")]
        self.assertIn("var(--go-accent)", confirm)
        self.assertIn("font-weight: 600", confirm)
        self.assertNotRegex(css, r"#[0-9a-fA-F]{6}\b")

    def test_narrow_layout_keeps_every_decision_control(self):
        """Stacking is allowed; removing a DECISION is not.

        `thead { display: none }` is legitimate here - a stacked card carries
        its labels inline, so the column header row is redundant rather than
        lost. The rule that matters is narrower than "no display:none": no
        decision control may be hidden at any width.
        """
        css = (_REPO_ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
        start = css.index("@media (max-width: 860px)")
        block = css[start:start + 1400]
        self.assertIn(".asread-decision-columns", block)
        for hidden in re.findall(r"([^{}]+)\{[^}]*display:\s*none[^}]*\}", block):
            self.assertNotIn("asread-decision", hidden)
            self.assertNotIn("asread-correction", hidden)
        # And the columns are re-laid-out, not dropped.
        columns = block[block.index(".asread-decision-columns"):]
        self.assertIn("grid-template-columns", columns[:columns.index("}")])

    # -- the governance guard -------------------------------------------------

    def test_presentation_only_no_record_changed(self):
        """Rendering the surface must not write anything."""
        workspace = self.store.get(self.project_id)
        before = [(i["id"], i.get("status"), len(i.get("decisions") or []))
                  for i in self.store.legend_items_for(
                      workspace, source_id=self.source["id"])]
        self._body()
        self._body()
        workspace = self.store.get(self.project_id)
        after = [(i["id"], i.get("status"), len(i.get("decisions") or []))
                 for i in self.store.legend_items_for(
                     workspace, source_id=self.source["id"])]
        self.assertEqual(before, after)
        self.assertEqual(len(after), 12)
        self.assertEqual(
            len([r for r in after if r[1] == "review_needed"]), len(self.held))


class AsReadBurdenAtE1ScaleTests(_AsReadFixture, unittest.TestCase):
    """The real E1 shape: 31 marks, 2 families, 6 representatives, 25 held.

    Burden is asserted as BOUNDS, not recorded as prose, because the whole
    point of this change is an interaction budget - and a budget nobody
    measures drifts back. The old surface put all 25 held marks on screen at
    load; these bounds are what stops that returning.
    """

    def setUp(self):
        super().setUp()
        # Extend the inherited 12 (3 rep + 9 held, famA) to the E1 shape:
        # a second family of 3 representatives, and 16 more held members.
        workspace = self.store.get(self.project_id)
        for index in range(16):
            workspace = self.store.get(self.project_id)
            item = self.store.propose_legend_item(
                workspace, source_id=self.source["id"],
                page_structural_unit_id=self.unit,
                region={"x": float(index), "y": 2.0, "width": 5.0, "height": 5.0},
                proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
                proposed_meaning="Section reference. Letter identifies the section.",
                interpretation_method="test", actor="GO",
                confidence=0.55, family_id=self.family_id,
                family_role="instance", nearby_label="B")
            workspace = self.store.get(self.project_id)
            self.store.flag_legend_item_review(
                workspace, item["id"], reason=self.HELD_REASON, actor="GO")
            self.held.append(item["id"])
        for index in range(3):
            workspace = self.store.get(self.project_id)
            self.store.propose_legend_item(
                workspace, source_id=self.source["id"],
                page_structural_unit_id=self.unit,
                region={"x": float(index), "y": 3.0, "width": 7.0, "height": 5.0},
                proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
                proposed_meaning="Section reference. Letter identifies the section.",
                interpretation_method="test", actor="GO",
                snapshot_path=str(self.snapshot), confidence=0.55,
                family_id="fam-matrix-02", family_role="representative",
                nearby_label="E")

    @staticmethod
    def _visible(html):
        """What is actually on screen: closed <details> content is not."""
        return re.sub(r"<details(?![^>]*\bopen\b)[^>]*>.*?</details>", "",
                      html, flags=re.S)

    def test_fixture_is_the_real_e1_shape(self):
        workspace = self.store.get(self.project_id)
        items = self.store.legend_items_for(workspace, source_id=self.source["id"])
        self.assertEqual(len(items), 31)
        self.assertEqual(
            len([i for i in items if i.get("status") == "review_needed"]), 25)

    def test_rows_needing_attention_on_load_is_small(self):
        visible = self.visible(self._body())
        rows = visible.count('data-ui-ref="drawing-understanding.family-row"')
        held_rows = visible.count('data-ui-ref="drawing-understanding.row"')
        self.assertEqual(rows, 2, "one row per family, not per occurrence")
        self.assertEqual(held_rows, 0, "held marks must not be on screen at load")

    def test_visible_decision_controls_on_load_are_bounded(self):
        """4 columns x 2 family rows. The old surface offered 4 + 25x5 = 129."""
        visible = self.visible(self._body())
        buttons = len(re.findall(
            r'data-ui-ref="drawing-understanding\.decision\.', visible))
        self.assertEqual(buttons, 8)
        self.assertLessEqual(buttons, 12, "decision controls on load must stay small")

    def test_no_free_text_or_scope_control_fronts_a_decision(self):
        """Scoped to the As-Read panel: base.html has its own chrome inputs,
        and counting those would measure the shell rather than this surface."""
        visible = self.visible(self._body())
        start = visible.index('data-ui-ref="drawing-understanding.panel"')
        panel = visible[start:]
        self.assertEqual(len(re.findall(r'<input[^>]*type="text"', panel)), 0)
        self.assertEqual(len(re.findall(r"<select", panel)), 0)

    def test_two_clicks_govern_every_family_on_the_sheet(self):
        """One click per family. 31 marks, 2 clicks."""
        client = self._client()
        for family_id in ("fam-matrix-01", "fam-matrix-02"):
            response = client.post(
                "/projects/%s/workspace/understanding/family/%s/decide"
                % (self.project_id, family_id),
                data={"action": LEGEND_STATUS_CONFIRMED,
                      "source_id": self.source["id"]})
            self.assertEqual(response.status_code, 302)
        workspace = self.store.get(self.project_id)
        reps = [i for i in self.store.legend_items_for(
            workspace, source_id=self.source["id"])
            if i.get("family_role") == "representative"]
        self.assertEqual(len(reps), 6)
        self.assertTrue(all(r["status"] == LEGEND_STATUS_CONFIRMED for r in reps))
