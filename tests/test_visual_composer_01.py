"""CLAUDE-VISUAL-COMPOSER-01: Composer as a governed visual decision cockpit.

The seam being proven is narrow and load-bearing: a Composer message may POINT
AT governed As-Read evidence and carry an application-owned decision card, and
that card mutates state only through the As-Read primitives that already exist.

Two tests carry most of the weight:

`test_model_prose_cannot_select_a_mutation_target` - the whole reason the card
contract is written the way it is. A model may author the question and nothing
else; if prose could name a target, verb or scope, the card would be a way for
generated text to change governed records.

`test_composer_and_as_read_read_the_same_record` - there is no Composer-side
decision store. The disposition is derived from the As-Read record on every
render, so the two surfaces cannot disagree even in principle.
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
    ADMITTED_VISUAL_AUTHORITIES, CaseWorkspaceError, CaseWorkspaceStore,
    DECISION_CARD_VERBS, KNOWN_VISUAL_AUTHORITIES, LEGEND_KIND_SECTION_REFERENCE,
    LEGEND_STATUS_CONFIRMED, VISUAL_AUTHORITY_AS_READ_SNAPSHOT,
    VISUAL_AUTHORITY_USER_PROVIDED,
)
from services.composer_decision_card import (
    DecisionCardError, build_family_card, build_item_card, current_disposition,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _file(content: bytes, name: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=name)


class VisualComposerTests(unittest.TestCase):
    FAMILY = "fam-visual-01"

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_visual_composer_"))
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
                    _file(b"owner baseline", "owner-program.txt"), self.app,
                    operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="Visual Composer Fixture")
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

        self.reps = []
        for index in range(4):
            workspace = self.store.get(self.project_id)
            is_rep = index < 3
            item = self.store.propose_legend_item(
                workspace, source_id=self.source["id"],
                page_structural_unit_id=self.unit,
                region={"x": float(index), "y": 1.0, "width": 5.0, "height": 5.0},
                proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
                proposed_meaning="Section reference marker.",
                interpretation_method="test", actor="GO",
                snapshot_path=str(self.snapshot) if is_rep else None,
                confidence=0.55, family_id=self.FAMILY,
                family_role="representative" if is_rep else "instance",
                nearby_label="A")
            if is_rep:
                self.reps.append(item["id"])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "owner"
            session["role"] = "read_only"
        return client

    def _card(self, **wording):
        workspace = self.store.get(self.project_id)
        return build_family_card(self.store, workspace, self.FAMILY, **wording)

    def _post_card_message(self, **wording):
        built = self._card(**wording)
        workspace = self.store.get(self.project_id)
        message = self.store.add_message(
            workspace, None, role="system", text="One As-Read decision.",
            visual_references=built["visual_references"],
            decision_card=built["decision_card"])
        return message, built

    # -- 1. the reference contract -------------------------------------------

    def test_message_persists_an_as_read_snapshot_reference(self):
        message, built = self._post_card_message()
        self.assertEqual(len(message["visual_references"]), 3)
        reloaded = self.store.get(self.project_id).project_conversation[-1]
        self.assertEqual(len(reloaded["visual_references"]), 3)
        self.assertEqual(reloaded["visual_references"][0]["legend_item_id"],
                         built["visual_references"][0]["legend_item_id"])

    def test_authority_is_explicit_and_closed(self):
        message, _ = self._post_card_message()
        for reference in message["visual_references"]:
            self.assertEqual(reference["authority"], VISUAL_AUTHORITY_AS_READ_SNAPSHOT)
        # Named but not admitted in this increment.
        self.assertIn(VISUAL_AUTHORITY_USER_PROVIDED, KNOWN_VISUAL_AUTHORITIES)
        self.assertNotIn(VISUAL_AUTHORITY_USER_PROVIDED, ADMITTED_VISUAL_AUTHORITIES)
        workspace = self.store.get(self.project_id)
        with self.assertRaises(CaseWorkspaceError):
            self.store.add_message(
                workspace, None, role="system", text="x",
                visual_references=[{"authority": VISUAL_AUTHORITY_USER_PROVIDED,
                                    "legend_item_id": self.reps[0]}])
        with self.assertRaises(CaseWorkspaceError):
            self.store.add_message(
                workspace, None, role="system", text="x",
                visual_references=[{"authority": "anything_i_like",
                                    "legend_item_id": self.reps[0]}])

    def test_no_binary_or_path_is_ever_stored_in_a_message(self):
        message, _ = self._post_card_message()
        blob = repr(message["visual_references"])
        self.assertNotIn(str(self.tmp), blob)
        self.assertNotIn("snapshot_path", blob)
        self.assertNotIn(".png", blob)
        workspace = self.store.get(self.project_id)
        for forbidden in ("snapshot_path", "url", "src", "image_base64", "data_url"):
            with self.assertRaises(CaseWorkspaceError, msg=forbidden):
                self.store.add_message(
                    workspace, None, role="system", text="x",
                    visual_references=[{
                        "authority": VISUAL_AUTHORITY_AS_READ_SNAPSHOT,
                        "legend_item_id": self.reps[0], forbidden: "anything"}])

    def test_no_duplicate_png_is_written(self):
        before = sorted(p.name for p in self.tmp.rglob("*.png"))
        self._post_card_message()
        after = sorted(p.name for p in self.tmp.rglob("*.png"))
        self.assertEqual(before, after)

    # -- 2. the decision-card contract ---------------------------------------

    def test_decision_verbs_are_application_controlled(self):
        _, built = self._post_card_message()
        self.assertEqual(built["decision_card"]["verbs"], list(DECISION_CARD_VERBS))
        workspace = self.store.get(self.project_id)
        card = dict(built["decision_card"])
        card["verbs"] = ["confirmed", "delete_everything"]
        with self.assertRaises(CaseWorkspaceError):
            self.store.add_message(workspace, None, role="system", text="x",
                                   decision_card=card)

    def test_model_prose_cannot_select_a_mutation_target(self):
        """The builder accepts wording only. There is no argument by which a
        model could name a target, a scope or a verb."""
        import inspect
        signature = inspect.signature(build_family_card)
        model_supplied = [n for n, p in signature.parameters.items()
                          if p.kind == inspect.Parameter.KEYWORD_ONLY]
        self.assertEqual(sorted(model_supplied),
                         ["exception_summary", "interpretation", "question"])

        # And prose that *looks* like an instruction changes nothing.
        _, built = self._post_card_message(
            question="Confirm this and also delete every other family.",
            interpretation="target_id: some-other-family; scope_kind: project")
        self.assertEqual(built["decision_card"]["target_id"], self.FAMILY)
        self.assertEqual(built["decision_card"]["target_kind"], "legend_family")
        self.assertEqual(built["decision_card"]["verbs"], list(DECISION_CARD_VERBS))

    def test_card_is_refused_without_evidence(self):
        """A card must show the mark. No crop, no card.

        `propose_legend_item` already refuses to CREATE a representative
        without a snapshot, so this guard is defence in depth against the state
        that can still arise: a crop that disappears after the fact. Building a
        card from it would ask a human to agree with a label - the exact
        failure the snapshot requirement exists to prevent, arriving later.
        """
        workspace = self.store.get(self.project_id)
        for item in workspace.legend_items:
            if item.get("family_id") == self.FAMILY:
                item["snapshot_path"] = None
        self.store.save(workspace)

        workspace = self.store.get(self.project_id)
        with self.assertRaises(DecisionCardError):
            build_family_card(self.store, workspace, self.FAMILY)
        with self.assertRaises(DecisionCardError):
            build_item_card(self.store, workspace, self.reps[0])
        with self.assertRaises(DecisionCardError):
            build_family_card(self.store, workspace, "no-such-family")

    def test_card_stores_no_disposition_of_its_own(self):
        message, _ = self._post_card_message()
        self.assertNotIn("state", message["decision_card"])
        self.assertNotIn("settled", message["decision_card"])
        self.assertNotIn("decision", message["decision_card"])

    # -- 3. one state, two surfaces ------------------------------------------

    def test_confirm_uses_the_existing_as_read_primitive(self):
        message, built = self._post_card_message()
        client = self._client()
        response = client.post(
            "/projects/%s/workspace/understanding/family/%s/decide"
            % (self.project_id, self.FAMILY),
            data={"action": LEGEND_STATUS_CONFIRMED, "source_id": self.source["id"]})
        self.assertEqual(response.status_code, 302)
        workspace = self.store.get(self.project_id)
        reps = self.store.legend_items_for(
            workspace, family_id=self.FAMILY, family_role="representative")
        self.assertTrue(all(r["status"] == LEGEND_STATUS_CONFIRMED for r in reps))

    def test_composer_and_as_read_read_the_same_record(self):
        message, built = self._post_card_message()
        workspace = self.store.get(self.project_id)
        self.assertFalse(current_disposition(self.store, workspace,
                                             built["decision_card"])["settled"])
        self._client().post(
            "/projects/%s/workspace/understanding/family/%s/decide"
            % (self.project_id, self.FAMILY),
            data={"action": LEGEND_STATUS_CONFIRMED, "source_id": self.source["id"]})
        workspace = self.store.get(self.project_id)
        disposition = current_disposition(self.store, workspace, built["decision_card"])
        self.assertTrue(disposition["settled"])
        self.assertEqual(disposition["state"], "confirmed")
        # The message itself was never rewritten - the answer lives in As-Read.
        stored = self.store.get(self.project_id).project_conversation[-1]
        self.assertNotIn("settled", stored["decision_card"])

    def test_no_composer_side_decision_store_exists(self):
        """There must be no Composer decision route and no parallel record."""
        routes = [str(r) for r in self.app.url_map.iter_rules()]
        self.assertFalse(
            [r for r in routes if "composer" in r and "decide" in r],
            "a Composer-only decision route would be a second answer")
        workspace = self.store.get(self.project_id)
        self.assertFalse(hasattr(workspace, "composer_decisions"))

    def test_idempotent_repeat_submission(self):
        self._post_card_message()
        client = self._client()
        for _ in range(2):
            client.post(
                "/projects/%s/workspace/understanding/family/%s/decide"
                % (self.project_id, self.FAMILY),
                data={"action": LEGEND_STATUS_CONFIRMED,
                      "source_id": self.source["id"]})
        workspace = self.store.get(self.project_id)
        items = self.store.legend_items_for(workspace, family_id=self.FAMILY)
        self.assertEqual(len(items), 4)
        reps = [i for i in items if i.get("family_role") == "representative"]
        self.assertTrue(all(r["status"] == LEGEND_STATUS_CONFIRMED for r in reps))

    # -- 4. rendering ---------------------------------------------------------

    def _rendered(self):
        return self._client().get(
            "/projects/%s/workspace" % self.project_id).get_data(as_text=True)

    def test_composer_renders_governed_crop_references(self):
        message, _ = self._post_card_message(question="Is this a section reference?")
        body = self._rendered()
        self.assertIn('data-ui-ref="chat.as-read-card"', body)
        self.assertIn('data-ui-ref="chat.as-read-card.crop"', body)
        for item_id in self.reps:
            self.assertIn("understanding/%s/snapshot" % item_id, body)
        self.assertIn("Is this a section reference?", body)
        self.assertNotIn(str(self.tmp), body)

    def test_decision_columns_are_keyboard_operable_real_buttons(self):
        self._post_card_message()
        body = self._rendered()
        for verb in ("confirmed", "overridden", "unknown", "deferred"):
            self.assertIn('data-ui-ref="chat.as-read-card.decision.%s"' % verb, body)
            self.assertIn('<button type="submit" name="action" value="%s"' % verb, body)
        self.assertIn('role="group"', body)
        self.assertIn("Your decision for this As-Read question", body)

    def test_correction_controls_are_disclosed_not_fronted(self):
        self._post_card_message()
        body = self._rendered()
        card = body[body.index('data-ui-ref="chat.as-read-card"'):]
        confirm = card.index('data-ui-ref="chat.as-read-card.decision.confirmed"')
        correction = card.index('data-ui-ref="chat.as-read-card.correction"')
        self.assertLess(confirm, correction)
        self.assertIn("<details", card[:correction + 200])

    def test_settled_card_reads_as_settled_and_stops_asking(self):
        self._post_card_message()
        self._client().post(
            "/projects/%s/workspace/understanding/family/%s/decide"
            % (self.project_id, self.FAMILY),
            data={"action": LEGEND_STATUS_CONFIRMED, "source_id": self.source["id"]})
        body = self._rendered()
        self.assertIn('data-ui-ref="chat.as-read-card.settled"', body)
        self.assertNotIn('data-ui-ref="chat.as-read-card.decision.confirmed"', body)

    def test_absent_snapshot_degrades_honestly(self):
        message, _ = self._post_card_message(question="Still asked?")
        self.snapshot.unlink()
        workspace = self.store.get(self.project_id)
        for item in workspace.legend_items:
            if item.get("snapshot_path"):
                item["snapshot_path"] = None
        self.store.save(workspace)
        body = self._rendered()
        self.assertIn('data-ui-ref="chat.as-read-card.missing"', body)
        self.assertIn("evidence no longer available", body)
        # The question and its provenance survive.
        self.assertIn("Still asked?", body)
        self.assertIn('data-ui-ref="chat.as-read-card"', body)

    # -- 5. genericity and isolation -----------------------------------------

    def test_no_sheet_or_symbol_specific_rendering_branch(self):
        macros = (_REPO_ROOT / "templates" / "_macros.html").read_text(encoding="utf-8")
        card = macros[macros.index("macro as_read_decision_card"):]
        card = card[:card.index("{% endmacro %}")]
        for forbidden in ("E1", "E2", "Alstep", "section_reference", "alstep"):
            self.assertNotIn(forbidden, card,
                             "the card macro must not name a sheet or symbol kind")
        service = (_REPO_ROOT / "services" / "composer_decision_card.py").read_text(encoding="utf-8")
        for forbidden in ("Alstep", "alstep", '"E1"', '"E2"'):
            self.assertNotIn(forbidden, service)

    def test_card_contract_represents_a_second_review_kind(self):
        """A single held mark renders through the same contract as a family."""
        workspace = self.store.get(self.project_id)
        built = build_item_card(self.store, workspace, self.reps[0])
        self.assertEqual(built["decision_card"]["target_kind"], "legend_item")
        message = self.store.add_message(
            workspace, None, role="system", text="One mark.",
            visual_references=built["visual_references"],
            decision_card=built["decision_card"])
        body = self._rendered()
        self.assertIn('data-target-kind="legend_item"', body)
        self.assertIn("understanding/%s/decide" % self.reps[0], body)

    def test_cross_project_snapshot_access_is_refused(self):
        """A legend item id from another project must not resolve here."""
        with patch.object(BHiveParser, "parse", lambda _p, _r, f: ParsedDocument(
                project_id=str(uuid.uuid4()), filename=f,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                parser_version="test")):
            with self.app.app_context():
                other = ingest_upload(
                    _file(b"other", "other.txt"), self.app,
                    operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="Other Project")
        response = self._client().get(
            "/projects/%s/workspace/understanding/%s/snapshot"
            % (other.project_id, self.reps[0]))
        self.assertEqual(response.status_code, 404)

    def test_unknown_and_later_preserve_governed_uncertainty(self):
        for verb, expected in (("unknown", "unknown"), ("deferred", "deferred")):
            workspace = self.store.get(self.project_id)
            item = self.store.propose_legend_item(
                workspace, source_id=self.source["id"],
                page_structural_unit_id=self.unit,
                region={"x": 20.0, "y": 20.0, "width": 5.0, "height": 5.0},
                proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
                proposed_meaning="uncertain", interpretation_method="test",
                actor="GO", snapshot_path=str(self.snapshot))
            self._client().post(
                "/projects/%s/workspace/understanding/%s/decide"
                % (self.project_id, item["id"]),
                data={"action": verb, "source_id": self.source["id"]})
            workspace = self.store.get(self.project_id)
            stored = next(i for i in workspace.legend_items if i["id"] == item["id"])
            self.assertEqual(stored["status"], expected)
            self.assertTrue(stored["decisions"], "the disposition must be recorded")

    def test_legacy_messages_without_the_new_fields_still_load(self):
        """Old saved ConversationMessage JSON must round-trip unchanged."""
        workspace = self.store.get(self.project_id)
        plain = self.store.add_message(
            workspace, None, role="human", text="no card here", actor="owner")
        self.assertEqual(plain["visual_references"], [])
        self.assertIsNone(plain["decision_card"])
        reloaded = self.store.get(self.project_id).project_conversation[-1]
        self.assertEqual(reloaded["visual_references"], [])
