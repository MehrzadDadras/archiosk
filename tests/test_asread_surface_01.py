"""CLAUDE-ASREAD-SURFACE-01: the proposition model, made visible and usable.

The axis existed and nothing rendered it. These tests hold the two lines that
matter once it does render:

`test_identity_confirmed_target_open_is_not_reviewed` - the count that used to
lie. It was identity-only, so a mark whose meaning was confirmed read as
finished while its target sat unanswered.

`test_unproposed_target_is_not_rendered_as_a_question` - a mark nobody claimed
refers to anything is not a mark whose target is pending. Rendering it would
invent review work that no one owes.
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
    CaseWorkspaceStore, LEGEND_KIND_SECTION_REFERENCE, LEGEND_SCOPE_SOURCE,
    LEGEND_STATUS_CONFIRMED, PROPOSITION_IDENTITY, PROPOSITION_TARGET,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload
from services.legend_of_understanding import (
    break_inheritance, case_review_state, decide_proposition,
    inherit_proposition, legend_proposition, numbered_cases,
    proposition_summary, propose_target,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


class AsReadSurfaceTests(unittest.TestCase):
    FAMILY = "fam-surface-01"

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_asread_surface_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)

        def fake_parse(_parser, _raw, filename):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                parser_version="test")

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename="owner.txt"),
                    self.app, operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="As-Read Surface Fixture")
        self.project_id = self.document.project_id
        self.store = CaseWorkspaceStore(self.tmp)
        self.source = self.store.get(self.project_id).sources[0]
        self.snapshot = self.tmp / "crop.png"
        self.snapshot.write_bytes(b"\x89PNG\r\n\x1a\n")

        workspace = self.store.get(self.project_id)
        self.unit = self.store.register_drawing_sheet_structure(
            workspace, self.source["id"],
            [{"index": 0, "label": "Sheet", "width": 100.0, "height": 100.0,
              "source_rotation": 0, "metadata": {}}],
            actor="test")["structural_unit_ids"][0]

        self.marks = []
        for index in range(4):
            workspace = self.store.get(self.project_id)
            item = self.store.propose_legend_item(
                workspace, source_id=self.source["id"],
                page_structural_unit_id=self.unit,
                region={"x": float(index), "y": 1.0, "width": 5.0, "height": 5.0},
                proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
                proposed_meaning="A section reference marker.",
                interpretation_method="test", actor="GO",
                snapshot_path=str(self.snapshot), confidence=0.55,
                family_id=self.FAMILY, family_role="representative",
                nearby_label="A")
            self.marks.append(item["id"])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ws(self):
        return self.store.get(self.project_id)

    def _item(self, item_id):
        return next(i for i in self._ws().legend_items if i["id"] == item_id)

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

    def _confirm(self, item_id, proposition, action=LEGEND_STATUS_CONFIRMED,
                 value=None):
        return self._client().post(
            "/projects/%s/workspace/understanding/%s/decide"
            % (self.project_id, item_id),
            data={"action": action, "proposition": proposition,
                  "source_id": self.source["id"],
                  **({"meaning": value} if value else {})})

    # -- the count that used to lie ------------------------------------------

    def test_identity_confirmed_target_open_is_not_reviewed(self):
        propose_target(self.store, self._ws(), self.marks[0],
                       proposed_value="Section E on sheet E2")
        self._confirm(self.marks[0], PROPOSITION_IDENTITY)
        state = case_review_state(self._item(self.marks[0]))
        self.assertFalse(state["settled"])
        self.assertEqual(state["open"], [PROPOSITION_TARGET])
        counts = proposition_summary(self.store, self._ws(),
                                     source_id=self.source["id"])
        self.assertEqual(counts["marks"], 4)
        self.assertEqual(counts["identity_settled"], 1)
        self.assertEqual(counts["target_settled"], 0)
        self.assertNotIn(self.marks[0],
                         [c["legend_item_id"] for c in
                          numbered_cases(self.store, self._ws(),
                                         source_id=self.source["id"])
                          if c["settled"]])

    def test_mark_counts_do_not_double_with_two_propositions(self):
        for item_id in self.marks:
            propose_target(self.store, self._ws(), item_id,
                           proposed_value="Section E on sheet E2")
        counts = proposition_summary(self.store, self._ws(),
                                     source_id=self.source["id"])
        self.assertEqual(counts["marks"], 4, "four marks, not eight")
        self.assertEqual(counts["open_propositions"], 8,
                         "the proposition-level figure is separate and labelled")
        body = self._body()
        self.assertIn("<strong>4</strong> mark(s) recognised", body)
        self.assertNotIn("<strong>8</strong> mark(s) recognised", body)

    def test_unknown_counts_as_reviewed_uncertainty_not_outstanding(self):
        self._confirm(self.marks[0], PROPOSITION_IDENTITY, action="unknown")
        state = case_review_state(self._item(self.marks[0]))
        self.assertTrue(state["settled"],
                        "recorded uncertainty is an answer, not an open question")

    def test_visual_family_count_stays_a_visual_count(self):
        counts = proposition_summary(self.store, self._ws(),
                                     source_id=self.source["id"])
        self.assertEqual(counts["visual_families"], 1)
        self.assertIn("evidence grouping, not meaning", self._body())

    # -- rendering -----------------------------------------------------------

    def test_unproposed_target_is_not_rendered_as_a_question(self):
        body = self._body()
        cases = numbered_cases(self.store, self._ws(), source_id=self.source["id"])
        for case in cases:
            self.assertEqual([p["proposition"] for p in case["propositions"]],
                             [PROPOSITION_IDENTITY])
        self.assertNotIn('data-proposition="target"', body)

    def test_identity_and_target_render_independently(self):
        propose_target(self.store, self._ws(), self.marks[0],
                       proposed_value="Section E on sheet E2")
        body = self._body()
        self.assertIn('data-proposition="identity"', body)
        self.assertIn('data-proposition="target"', body)
        self.assertIn("Section E on sheet E2", body)

    def test_confirming_identity_leaves_target_open_on_screen(self):
        propose_target(self.store, self._ws(), self.marks[0],
                       proposed_value="Section E on sheet E2")
        self._confirm(self.marks[0], PROPOSITION_IDENTITY)
        body = self._body()
        case = body[body.index('data-legend-item-id="%s"' % self.marks[0]):]
        case = case[:case.index("</article>")]
        identity = case[case.index('data-proposition="identity"'):]
        identity = identity[:identity.index('data-proposition="target"')]
        target = case[case.index('data-proposition="target"'):]
        self.assertIn("Confirmed", identity)
        self.assertNotIn('value="confirmed"', identity,
                         "a settled proposition must not keep an active Confirm")
        self.assertIn('value="confirmed"', target,
                      "the target is still an open question")

    def test_case_numbers_are_display_only(self):
        body = self._body()
        self.assertIn('data-ui-ref="drawing-understanding.case.number"', body)
        self.assertRegex(body, r"#0[1-4]")
        for item in self._ws().legend_items:
            self.assertNotIn("number", item)
            self.assertNotIn("display_ordinal", item)

    def test_reversing_order_does_not_break_durable_lineage(self):
        self._confirm(self.marks[0], PROPOSITION_IDENTITY)
        inherit_proposition(self.store, self._ws(), self.marks[2],
                            PROPOSITION_IDENTITY,
                            from_legend_item_id=self.marks[0],
                            evidence="same confirmed convention")
        workspace = self._ws()
        workspace.legend_items.reverse()
        self.store.save(workspace)
        cases = numbered_cases(self.store, self._ws(), source_id=self.source["id"])
        moved = next(c for c in cases if c["legend_item_id"] == self.marks[2])
        identity = moved["propositions"][0]
        origin = next(c for c in cases if c["legend_item_id"] == self.marks[0])
        self.assertEqual(identity["same_as_legend_item_id"], self.marks[0])
        self.assertEqual(identity["same_as_display"], origin["number"])

    def test_same_as_renders_only_from_governed_inheritance(self):
        body = self._body()
        self.assertNotIn("SAME AS", body,
                         "four marks in one visual family, and nobody has "
                         "confirmed anything - similarity is not lineage")
        self._confirm(self.marks[0], PROPOSITION_IDENTITY)
        inherit_proposition(self.store, self._ws(), self.marks[1],
                            PROPOSITION_IDENTITY,
                            from_legend_item_id=self.marks[0],
                            evidence="same confirmed convention")
        body = self._body()
        self.assertIn("SAME AS", body)
        self.assertIn('data-ui-ref="drawing-understanding.proposition.applied"', body)

    def test_settled_state_is_state_not_an_active_button(self):
        self._confirm(self.marks[0], PROPOSITION_IDENTITY)
        body = self._body()
        case = body[body.index('data-legend-item-id="%s"' % self.marks[0]):]
        case = case[:case.index("</article>")]
        self.assertIn('data-ui-ref="drawing-understanding.proposition.settled"', case)
        self.assertNotIn('data-ui-ref="drawing-understanding.proposition.confirm"', case)

    def test_repeated_confirm_shows_settled_not_a_silent_no_op(self):
        self._confirm(self.marks[0], PROPOSITION_IDENTITY)
        first = self._body()
        self._confirm(self.marks[0], PROPOSITION_IDENTITY)
        second = self._body()
        self.assertIn("Confirmed", first)
        self.assertIn("Confirmed", second)
        self.assertTrue(
            legend_proposition(self._item(self.marks[0]),
                               PROPOSITION_IDENTITY)["settled"])

    def test_correct_me_reveals_only_that_propositions_control(self):
        propose_target(self.store, self._ws(), self.marks[0],
                       proposed_value="Section E on sheet E2")
        body = self._body()
        case = body[body.index('data-legend-item-id="%s"' % self.marks[0]):]
        case = case[:case.index("</article>")]
        self.assertIn("What this mark actually signifies", case)
        self.assertIn("What it actually refers to", case)
        # No generic scope/admin field is offered up front.
        self.assertNotIn("<select", case)

    def test_correcting_target_records_against_target_only(self):
        propose_target(self.store, self._ws(), self.marks[0],
                       proposed_value="Section E on sheet E2")
        self._confirm(self.marks[0], PROPOSITION_TARGET, action="overridden",
                      value="Section F on sheet E2")
        item = self._item(self.marks[0])
        self.assertEqual(
            legend_proposition(item, PROPOSITION_TARGET)["value"],
            "Section F on sheet E2")
        self.assertFalse(legend_proposition(item, PROPOSITION_IDENTITY)["settled"])

    # -- reassessment ---------------------------------------------------------

    def test_local_exception_does_not_reopen_unrelated_propositions(self):
        self._confirm(self.marks[0], PROPOSITION_IDENTITY)
        for item_id in self.marks[1:]:
            inherit_proposition(self.store, self._ws(), item_id,
                                PROPOSITION_IDENTITY,
                                from_legend_item_id=self.marks[0],
                                evidence="same convention")
        break_inheritance(self.store, self._ws(), self.marks[2],
                          PROPOSITION_IDENTITY, actor="Product Owner",
                          reason="local exception", broader_distinction=False)
        body = self._body()
        self.assertNotIn("REVIEW AGAIN", body)

    def test_broader_distinction_renders_review_again_for_that_proposition(self):
        self._confirm(self.marks[0], PROPOSITION_IDENTITY)
        for item_id in self.marks[1:]:
            propose_target(self.store, self._ws(), item_id,
                           proposed_value="Section E on sheet E2")
            inherit_proposition(self.store, self._ws(), item_id,
                                PROPOSITION_IDENTITY,
                                from_legend_item_id=self.marks[0],
                                evidence="same convention")
            self._confirm(item_id, PROPOSITION_TARGET)
        break_inheritance(self.store, self._ws(), self.marks[2],
                          PROPOSITION_IDENTITY, actor="Product Owner",
                          reason="two different symbols after all",
                          broader_distinction=True)
        body = self._body()
        self.assertIn("REVIEW AGAIN", body)
        reopened = self._item(self.marks[1])
        self.assertEqual(
            legend_proposition(reopened, PROPOSITION_IDENTITY)["status"],
            "review_again")
        self.assertTrue(
            legend_proposition(reopened, PROPOSITION_TARGET)["settled"],
            "the target was never in question and must stay settled")

    # -- economy, isolation, genericity --------------------------------------

    def test_identical_questions_collapse_but_stay_reachable(self):
        body = self._body()
        visible = re.sub(r"<details(?![^>]*\bopen\b)[^>]*>.*?</details>", "",
                         body, flags=re.S)
        self.assertLess(visible.count('data-ui-ref="drawing-understanding.case"'),
                        body.count('data-ui-ref="drawing-understanding.case"') + 1)
        self.assertIn('data-ui-ref="drawing-understanding.cases-same-question"', body)
        # Every mark is still present somewhere on the page.
        for item_id in self.marks:
            self.assertIn(item_id, body)

    def test_family_evidence_remains_reachable(self):
        body = self._body()
        self.assertIn('data-ui-ref="drawing-understanding.family-table"', body)

    def test_project_and_source_isolation_preserved(self):
        with patch.object(BHiveParser, "parse", lambda _p, _r, f: ParsedDocument(
                project_id=str(uuid.uuid4()), filename=f,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                parser_version="test")):
            with self.app.app_context():
                other = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"y"), filename="o.txt"),
                    self.app, operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="Other")
        response = self._client().post(
            "/projects/%s/workspace/understanding/%s/decide"
            % (other.project_id, self.marks[0]),
            data={"action": LEGEND_STATUS_CONFIRMED,
                  "proposition": PROPOSITION_IDENTITY})
        self.assertIn(response.status_code, (302, 404))
        self.assertFalse(
            legend_proposition(self._item(self.marks[0]),
                               PROPOSITION_IDENTITY)["settled"])

    def test_an_invented_proposition_is_refused(self):
        response = self._client().post(
            "/projects/%s/workspace/understanding/%s/decide"
            % (self.project_id, self.marks[0]),
            data={"action": LEGEND_STATUS_CONFIRMED, "proposition": "whatever"})
        self.assertEqual(response.status_code, 400)

    def test_no_sheet_or_project_specific_branch(self):
        for path in (_REPO_ROOT / "templates" / "_macros.html",
                     _REPO_ROOT / "templates" / "drawing_understanding.html"):
            text = path.read_text(encoding="utf-8")
            block = text[text.index("proposition"):] if "proposition" in text else ""
            for forbidden in ("Alstep", "alstep", "222109"):
                self.assertNotIn(forbidden, block)

    def test_identity_storage_was_not_migrated(self):
        """The deliberate asymmetry survives: IDENTITY is still the legacy fields."""
        item = self._item(self.marks[0])
        self.assertIn("proposed_meaning", item)
        self.assertIn("status", item)
        self.assertIsNone(item.get("identity_proposition"),
                          "IDENTITY must not have grown a parallel record")
