"""
Help Clip visual targets — WHERE to show it, kept apart from WHAT it says.

THE PROBLEM THIS SOLVES

The first real Survival Mode Clip stopped at Needs review because the scenario
asked to "show where the checkbox is" and the Help Library holds no textual
evidence describing screen positions. The gate was RIGHT to block that — as a
CLAIM it was unsupported. But it was never a claim. It is a request to point at
a control, and ARCHIOSK already knows where that control is, by the stable
`data-ui-ref` identity the application emits and a test holds to registry parity.

So the fix is a separation, not a weakening:

    WHAT IT SAYS   -> governed Claims and evidence   (scenes)
    WHERE TO SHOW  -> governed UI identity           (directions)

A DIRECTION ASSERTS NOTHING, and these tests exist mostly to prove that
negative. If a direction could ever influence question fit, evidence fidelity,
unsupported claims, current applicability, semantic fit or evidence
consistency, then presentation metadata would have acquired semantic authority
by the back door — which is the exact inversion the whole design refuses.

No test here reaches the network.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from services.case_workspace import (
    CaseWorkspaceStore,
    CONTENT_CLASS_TEMPLATE_CONTENT,
)
from services.help_mode import (
    HELP_LIBRARY_PROJECT_ID,
    HelpModeError,
    add_help_script_direction,
    help_script_detail,
)

SURVIVAL_REF = "toolbox.spin.world-survival"
SECOND_REF = "toolbox.spin.help-survival"
_REPO_ROOT = Path(__file__).resolve().parent.parent

SCENARIO = (
    "Explain Survival Mode to a new ARCHIOSK user. Show where the checkbox is, "
    "explain that it applies to First Spin or Delta Spin, and make clear that it "
    "is not a third kind of Spin."
)
_ENV = {"ANTHROPIC_API_KEY": "unit-test-key-never-used", "ANTHROPIC_TIMEOUT_SECONDS": "5"}
_PASS = {"outcome": "pass", "reason": "ok", "problem_unit_ids": []}


def _response(payload):
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    r = MagicMock()
    r.content = [block]
    return r


def _client_returning(payloads):
    c = MagicMock()
    c.messages.create.side_effect = [_response(p) for p in payloads]
    return MagicMock(return_value=c)


class DirectionAuthoringTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_visual_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="reviewer",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.script_id = self._script()

    def _script(self):
        from services.help_mode import create_help_script
        return create_help_script(
            self.store, question="What is Survival Mode?", title="Survival Mode",
            actor="reviewer")["id"]

    def _library(self):
        return self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)

    def _readiness(self):
        return self.store.resolve_script_readiness(self._library(), self.script_id)

    def _last_direction(self, work_product):
        """The direction just added.

        `add_help_script_direction` returns the work product, exactly as its
        sibling `add_help_script_scene` does - the consistency is worth more
        than the convenience of returning the section, so the test does the
        lookup instead of the API shape diverging.
        """
        directions = [s for s in work_product["sections"]
                      if s["section_type"] == "direction" and not s["removed"]]
        self.assertTrue(directions, "no direction section was created")
        return sorted(directions, key=lambda s: s["order_index"])[-1]

    # -- 1 / 2: one target, and many ---------------------------------------

    def test_a_direction_can_target_one_ui_ref(self):
        section = self._last_direction(add_help_script_direction(
            self.store, script_id=self.script_id, ui_refs=[SURVIVAL_REF],
            actor="reviewer", text="Highlight the Survival Mode checkbox."))
        self.assertEqual(section["section_type"], "direction")
        self.assertEqual(section["content"]["ui_refs"], [SURVIVAL_REF])
        self.assertEqual(section["content"]["action"], "highlight")
        self.assertEqual(section["content_class"], CONTENT_CLASS_TEMPLATE_CONTENT)

    def test_a_direction_can_target_multiple_ui_refs(self):
        section = self._last_direction(add_help_script_direction(
            self.store, script_id=self.script_id, ui_refs=[SURVIVAL_REF, SECOND_REF],
            actor="reviewer", text="Highlight both."))
        self.assertEqual(section["content"]["ui_refs"], [SURVIVAL_REF, SECOND_REF])

    def test_duplicate_targets_collapse_and_case_is_normalised(self):
        section = self._last_direction(add_help_script_direction(
            self.store, script_id=self.script_id,
            ui_refs=[SURVIVAL_REF, SURVIVAL_REF.upper(), " " + SURVIVAL_REF + " "],
            actor="reviewer"))
        self.assertEqual(section["content"]["ui_refs"], [SURVIVAL_REF])

    def test_a_malformed_ui_ref_is_refused(self):
        with self.assertRaises(HelpModeError):
            add_help_script_direction(
                self.store, script_id=self.script_id, ui_refs=["NOT A REF"], actor="reviewer")

    def test_a_direction_needs_a_target_or_text(self):
        with self.assertRaises(HelpModeError):
            add_help_script_direction(
                self.store, script_id=self.script_id, ui_refs=[], actor="reviewer", text="")

    # -- 3: a ui_ref can never be evidence ---------------------------------

    def test_a_direction_stores_no_evidence_links(self):
        section = self._last_direction(add_help_script_direction(
            self.store, script_id=self.script_id, ui_refs=[SURVIVAL_REF], actor="reviewer"))
        self.assertEqual(section["evidence_links"], [])

    def test_the_function_offers_no_way_to_attach_evidence(self):
        """The affordance is absent, not merely discouraged.

        The kernel would reject a ui_ref in evidence_links anyway - links are
        validated against really-persisted governed objects - but a caller
        cannot even attempt it, which is the stronger guarantee.
        """
        import inspect
        params = set(inspect.signature(add_help_script_direction).parameters)
        self.assertNotIn("evidence_links", params)
        self.assertNotIn("claim_ids", params)

    def test_a_ui_ref_is_not_stored_as_a_claim_or_evidence_item(self):
        add_help_script_direction(
            self.store, script_id=self.script_id, ui_refs=[SURVIVAL_REF], actor="reviewer")
        workspace = self._library()
        self.assertNotIn(SURVIVAL_REF, [c.get("statement") for c in workspace.claims])
        self.assertNotIn(SURVIVAL_REF,
                         [str(e.get("content")) for e in workspace.evidence_items])

    # -- 4 / 7: directions cannot move the semantic gate -------------------

    def test_a_direction_changes_no_semantic_check(self):
        """The load-bearing negative. Every gate reads scenes only."""
        before = self._readiness()["checks"]
        add_help_script_direction(
            self.store, script_id=self.script_id, ui_refs=[SURVIVAL_REF],
            actor="reviewer", text="Highlight the Survival Mode checkbox.")
        after = self._readiness()["checks"]
        self.assertEqual(before, after,
                         "a presentation direction moved a semantic gate")

    def test_a_direction_is_not_narrated_and_not_consistency_checked(self):
        from services.script_fit import script_claim_pairs, script_narrative_text

        add_help_script_direction(
            self.store, script_id=self.script_id, ui_refs=[SURVIVAL_REF],
            actor="reviewer", text="POINTER TEXT that must never be narrated.")
        script = self.store.get_work_product(self._library(), self.script_id)
        self.assertNotIn("POINTER TEXT", script_narrative_text(script))
        pairs = script_claim_pairs(self.store, self._library(), script)
        self.assertNotIn("POINTER TEXT", " ".join(p["text"] for p in pairs))

    def test_an_unresolvable_target_degrades_presentation_only(self):
        """A well-formed ref that no longer exists must not block the answer.

        Presentation targeting failing is a missing highlight, not a reason to
        withhold a true explanation - letting it become REVIEW_NEEDED is exactly
        how presentation metadata would acquire gate authority.
        """
        before = self._readiness()
        add_help_script_direction(
            self.store, script_id=self.script_id,
            ui_refs=["toolbox.spin.control-that-no-longer-exists"],
            actor="reviewer", text="Highlight it.")
        after = self._readiness()
        self.assertEqual(before["checks"], after["checks"])
        self.assertEqual(before["readiness"], after["readiness"])

    # -- 5: "show where" compiles to a direction, not a claim --------------

    def test_show_where_the_checkbox_is_compiles_as_a_direction(self):
        from services.cross_modal_investigation import compile_help_scenario

        payload = {
            "question": "What is Survival Mode, and is it another kind of Spin?",
            "title": "Survival Mode",
            "claims": [{"statement": "Survival Mode is a lens, not a third kind of Spin.",
                        "evidence_ids": ["e1"]}],
            "scenes": [{"text": "Survival Mode is a lens on either Spin.",
                        "claim_indexes": [0]}],
            "directions": [{"action": "highlight", "ui_refs": [SURVIVAL_REF],
                            "text": "Highlight the Survival Mode checkbox."}],
            "unsupported": [],
            "reason": "grounded",
        }
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _client_returning([payload])):
            result = compile_help_scenario(
                SCENARIO, [{"id": "e1", "text": "Survival Mode is a lens."}],
                ui_ref_catalogue=[SURVIVAL_REF])

        self.assertTrue(result.ran)
        self.assertEqual(len(result.directions), 1)
        self.assertEqual(result.directions[0]["ui_refs"], [SURVIVAL_REF])
        # And crucially: location is NOT a claim and NOT an unsupported gap.
        self.assertEqual(len(result.claims), 1)
        self.assertNotIn("where", " ".join(c["statement"] for c in result.claims).lower())
        self.assertEqual(result.unsupported, ())

    def test_a_target_outside_the_catalogue_is_dropped_not_stored(self):
        """Same discipline as evidence ids: only what we offered survives."""
        from services.cross_modal_investigation import compile_help_scenario

        payload = {
            "question": "q", "title": "t",
            "claims": [{"statement": "s", "evidence_ids": ["e1"]}],
            "scenes": [{"text": "scene", "claim_indexes": [0]}],
            "directions": [{"action": "highlight",
                            "ui_refs": ["toolbox.invented.by.the.model"],
                            "text": "Highlight something."}],
        }
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _client_returning([payload])):
            result = compile_help_scenario(
                "x", [{"id": "e1", "text": "y"}], ui_ref_catalogue=[SURVIVAL_REF])
        self.assertEqual(result.directions[0]["ui_refs"], [],
                         "an invented UI target was kept")
        self.assertEqual(result.directions[0]["text"], "Highlight something.",
                         "the instruction should survive losing its target")

    # -- 6: the live pilot blocker -----------------------------------------

    def test_the_pilot_scenario_no_longer_needs_location_evidence(self):
        """End to end: generation produces a clip whose visual request is a
        direction, so 'show where the checkbox is' never reaches the evidence
        gate as an unsupported claim."""
        from services.help_clip_studio import clip_package, generate_help_clip

        ws = self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)
        source = self.store.add_source(ws, name="help-guide:spin", file_path="x",
                                       kind="document", actor="seed")
        evidence_id = self.store.register_plain_text_structure(
            ws, source["id"],
            "Survival Mode is a lens, not a third kind of Spin. It is a checkbox "
            "on either Run button.", actor="seed")["evidence_item_ids"][0]

        payload = {
            "question": "What is Survival Mode, and is it another kind of Spin?",
            "title": "Survival Mode",
            "claims": [{"statement": "Survival Mode is a lens, not a third kind of Spin.",
                        "evidence_ids": [evidence_id]}],
            "scenes": [{"text": "Survival Mode is a lens on either Spin, not a third kind.",
                        "claim_indexes": [0]}],
            "directions": [{"action": "highlight", "ui_refs": [],
                            "text": "Highlight the Survival Mode checkbox."}],
            "unsupported": [],
        }
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _client_returning([payload, _PASS, _PASS])):
            result = generate_help_clip(
                self.store, scenario=SCENARIO, actor="reviewer", policy_decision="allow")

        self.assertEqual(result["unsupported"], [],
                         "visual location was still treated as missing evidence")
        self.assertEqual(result["ungrounded"], [])
        clip = clip_package(self.store, result["script_id"])
        self.assertEqual(len(clip["visual_targets"]), 1)
        self.assertEqual(clip["visual_targets"][0]["text"],
                         "Highlight the Survival Mode checkbox.")
        # The direction is not part of what the clip SAYS.
        self.assertEqual(len(clip["scenes"]), 1)
        self.assertNotIn("Highlight", " ".join(s["text"] for s in clip["scenes"]))

    # -- 2 (clip_package) / 8 / 9 / 10 -------------------------------------

    def test_clip_package_separates_captions_from_visual_targets(self):
        from services.help_clip_studio import clip_package

        add_help_script_direction(
            self.store, script_id=self.script_id, ui_refs=[SURVIVAL_REF],
            actor="reviewer", text="Highlight the checkbox.")
        clip = clip_package(self.store, self.script_id)
        self.assertIn("visual_targets", clip)
        self.assertEqual(clip["visual_targets"][0]["ui_refs"], [SURVIVAL_REF])
        self.assertNotIn("Highlight the checkbox.",
                         " ".join(c["text"] for c in clip["captions"]))

    def test_the_pilot_ui_ref_exists_in_the_authoritative_registry(self):
        registry = (_REPO_ROOT / "UI_REFERENCE_MAP.md").read_text(encoding="utf-8")
        known = set(re.findall(r"`([a-z0-9][a-z0-9._\-]*)`", registry))
        self.assertIn(SURVIVAL_REF, known)

    def test_no_2d_3d_or_renderer_coupling_was_introduced(self):
        """ui_ref is DOM identity for the application's own chrome. The 2D/3D
        track is geometry compiled from drawings. They must share nothing."""
        for module in ("services/help_mode.py", "services/help_clip_studio.py"):
            source = (_REPO_ROOT / module).read_text(encoding="utf-8").lower()
            for forbidden in ("engine.", "ifc", "spatial_compiler", "ffmpeg",
                              "moviepy", "mp4", "codec", "pdf_extractor"):
                self.assertNotIn(forbidden, source, "%s reached into %s" % (module, forbidden))
        engine_dir = _REPO_ROOT / "engine"
        for path in engine_dir.glob("*.py"):
            self.assertNotIn("ui_ref", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
