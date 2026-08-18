"""
CLAUDE-HOLODECK-WORLDS-SPIN-01 - the first Spin "World": Survival Mode.

A World changes Spin's own rules of attention without changing the
engine - the SAME services.spin.run_spin/CaseWorkspaceStore.record_
spin_run call, framed with a different, product-defined objective and
asked to self-report an inspectable "games_played" trace. Deliberately
ONE real World value (SPIN_WORLD_SURVIVAL) - see services.case_workspace's
own KNOWN_SPIN_WORLDS docstring for why a second World is a vocabulary
addition, not a schema migration.

Covers: ordinary (world=None) Spin remains byte-for-byte unaffected;
Survival Mode's own prompt framing and games_played schema request only
appear when requested; defensive parsing of the model's own self-reported
trace; persistence; route-level end-to-end; and rendering on the Spin
tab (World/Objective/Games Played).

Follows this repo's own hermetic convention (patch("anthropic.Anthropic"))
for every LLM-touching test - never a live model call.

Run via:

    python -m unittest tests.test_holodeck_worlds_spin_01 -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.case_workspace import (
    CaseWorkspaceError,
    CaseWorkspaceStore,
    KNOWN_SPIN_WORLDS,
    SPIN_KIND_FIRST,
    SPIN_WORLD_SURVIVAL,
)
from services.ingestion import RequirementsRegistry
from services.bhive_parser import ParsedDocument
from services.spin import (
    SPIN_WORLD_OBJECTIVES,
    _build_prompt,
    _parse_games_played,
    run_spin,
)
from werkzeug.security import generate_password_hash


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class WorldVocabularyTests(unittest.TestCase):
    def test_survival_is_a_known_world(self):
        self.assertIn(SPIN_WORLD_SURVIVAL, KNOWN_SPIN_WORLDS)

    def test_survival_has_a_stable_product_defined_objective(self):
        self.assertIn(SPIN_WORLD_SURVIVAL, SPIN_WORLD_OBJECTIVES)
        self.assertTrue(SPIN_WORLD_OBJECTIVES[SPIN_WORLD_SURVIVAL])


class ParseGamesPlayedTests(unittest.TestCase):
    def test_valid_items_parsed(self):
        raw = [
            {"game": "Change Game", "triggered_by": "x", "finding": "F-1"},
            {"game": "Authority Game", "triggered_by": "y", "finding": ""},
        ]
        result = _parse_games_played(raw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["game"], "Change Game")
        self.assertEqual(result[1]["finding"], "")

    def test_item_missing_game_name_is_dropped(self):
        self.assertEqual(_parse_games_played([{"triggered_by": "x"}]), [])

    def test_non_list_input_returns_empty(self):
        self.assertEqual(_parse_games_played("not a list"), [])
        self.assertEqual(_parse_games_played(None), [])

    def test_capped_at_max_games_played(self):
        from services.spin import _MAX_GAMES_PLAYED

        raw = [{"game": f"G{i}", "triggered_by": "", "finding": ""} for i in range(_MAX_GAMES_PLAYED + 5)]
        self.assertEqual(len(_parse_games_played(raw)), _MAX_GAMES_PLAYED)


class PromptWorldFramingTests(unittest.TestCase):
    def test_ordinary_prompt_has_no_survival_or_games_played_text(self):
        prompt = _build_prompt(SPIN_KIND_FIRST, "rfp.pdf", [], [], [], world=None)
        self.assertNotIn("SURVIVAL MODE", prompt)
        self.assertNotIn("games_played", prompt)

    def test_survival_prompt_carries_framing_and_schema_request(self):
        prompt = _build_prompt(SPIN_KIND_FIRST, "rfp.pdf", [], [], [], world=SPIN_WORLD_SURVIVAL)
        self.assertIn("SURVIVAL MODE", prompt)
        self.assertIn(SPIN_WORLD_OBJECTIVES[SPIN_WORLD_SURVIVAL], prompt)
        self.assertIn("games_played", prompt)
        self.assertIn("Change Game", prompt)  # example vocabulary present, not a closed enum

    def test_survival_prompt_never_pads_games_played_instruction(self):
        prompt = _build_prompt(SPIN_KIND_FIRST, "rfp.pdf", [], [], [], world=SPIN_WORLD_SURVIVAL)
        self.assertIn("Never fabricate", prompt)


class RunSpinWorldTests(unittest.TestCase):
    """Exercises services.spin.run_spin directly (mocked anthropic.Anthropic)."""

    def _run(self, world, response_json):
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv",
                   side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response(response_json)
            return run_spin(
                spin_kind=SPIN_KIND_FIRST, document_filename="rfp.pdf",
                candidate_requirements=[], governed_requirements=[], milestones=[],
                world=world,
            )

    def test_ordinary_run_has_no_games_played_even_if_model_supplies_them(self):
        """A world=None caller never asked for games_played - even if a
        malformed/unexpected model response included one, it must not
        leak through, since the schema instruction was never sent."""
        response_json = (
            '{"findings": [{"tag": "T", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}], '
            '"games_played": [{"game": "Should not appear", "triggered_by": "", "finding": ""}]}'
        )
        result = self._run(None, response_json)
        self.assertEqual(result.games_played, [])

    def test_survival_run_parses_games_played(self):
        response_json = (
            '{"findings": [{"tag": "T", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}], '
            '"games_played": [{"game": "Change Game", "triggered_by": "x", "finding": "T"}]}'
        )
        result = self._run(SPIN_WORLD_SURVIVAL, response_json)
        self.assertEqual(len(result.games_played), 1)
        self.assertEqual(result.games_played[0]["game"], "Change Game")

    def test_invalid_world_raises(self):
        with self.assertRaises(ValueError):
            self._run("not_a_real_world", '{"findings": []}')


class RecordSpinRunWorldStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_holodeck_worlds_"))
        self.project_id = "test-project-holodeck-worlds"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(
            self.project_id, register_document_source={"filename": "rfp.md"},
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_world_and_games_played_persist(self):
        run = self.store.record_spin_run(
            self.workspace, spin_kind=SPIN_KIND_FIRST, actor="owner1",
            findings=[{"tag": "T", "source_reference": "s", "concern": "c", "unresolved_question": "q",
                       "delta_classification": None, "related_prior_understanding": None}],
            source_signature="", world=SPIN_WORLD_SURVIVAL,
            games_played=[{"game": "Change Game", "triggered_by": "x", "finding": "T"}],
        )
        self.assertEqual(run["world"], SPIN_WORLD_SURVIVAL)
        self.assertEqual(run["games_played"][0]["game"], "Change Game")
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.spin_runs[0]["world"], SPIN_WORLD_SURVIVAL)

    def test_ordinary_run_defaults_to_no_world(self):
        run = self.store.record_spin_run(
            self.workspace, spin_kind=SPIN_KIND_FIRST, actor="owner1", findings=[], source_signature="",
        )
        self.assertIsNone(run["world"])
        self.assertEqual(run["games_played"], [])

    def test_unknown_world_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_spin_run(
                self.workspace, spin_kind=SPIN_KIND_FIRST, actor="owner1", findings=[], source_signature="",
                world="not_a_real_world",
            )


class RunSpinRouteWorldTests(unittest.TestCase):
    """Route-level: proves the real HTTP trigger, persistence, and Spin
    tab rendering all work end to end for Survival Mode, and that
    ordinary (no world posted) Spin remains completely unaffected."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_holodeck_worlds_route_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-holodeck-worlds-route"

        with self.flask_app.app_context():
            db.session.add(User(username="world_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "world_owner"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _run_spin(self, response_json, world=None):
        data = {"spin_kind": "first_spin"}
        if world:
            data["world"] = world
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv",
                   side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response(response_json)
            return self.client.post(
                f"/projects/{self.project_id}/workspace/spin/run", data=data, follow_redirects=True,
            )

    def test_toolbox_offers_survival_mode_checkbox(self):
        body = self.client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.spin.world-survival"', body)

    def test_survival_mode_run_persists_world_and_games_played(self):
        response_json = (
            '{"findings": [{"tag": "T", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}], '
            '"games_played": [{"game": "Change Game", "triggered_by": "x", "finding": "T"}]}'
        )
        self._run_spin(response_json, world=SPIN_WORLD_SURVIVAL)
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.spin_runs[0]["world"], SPIN_WORLD_SURVIVAL)
        self.assertEqual(workspace.spin_runs[0]["games_played"][0]["game"], "Change Game")

    def test_spin_tab_renders_world_objective_and_games_played(self):
        response_json = (
            '{"findings": [{"tag": "Disqualification risk", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "High", "project_stage": ""}], '
            '"games_played": [{"game": "Change Game", "triggered_by": "an addendum changed the requirement", '
            '"finding": "Disqualification risk"}]}'
        )
        self._run_spin(response_json, world=SPIN_WORLD_SURVIVAL)
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=spin").get_data(as_text=True)
        self.assertIn('data-ui-ref="display.spin.report.world"', body)
        self.assertIn("Survival Mode", body)
        self.assertIn(SPIN_WORLD_OBJECTIVES[SPIN_WORLD_SURVIVAL], body)
        self.assertIn('data-ui-ref="display.spin.report.games-played"', body)
        self.assertIn("Change Game", body)
        self.assertIn("Disqualification risk", body)

    def test_history_leaf_shows_world_label(self):
        response_json = '{"findings": [], "games_played": []}'
        self._run_spin(response_json, world=SPIN_WORLD_SURVIVAL)
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=spin").get_data(as_text=True)
        self.assertIn("Survival Mode", body)

    def test_ordinary_spin_run_unaffected_by_world_feature(self):
        """The core regression guard: a normal trigger (no `world` field
        posted at all) must produce byte-identical persisted shape to
        before this stage - world=None, games_played=[]."""
        response_json = (
            '{"findings": [{"tag": "Ordinary", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(response_json, world=None)
        workspace = self.store.get(self.project_id)
        run = workspace.spin_runs[0]
        self.assertIsNone(run["world"])
        self.assertEqual(run["games_played"], [])
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=spin").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="display.spin.report.world"', body)
        self.assertNotIn('data-ui-ref="display.spin.report.games-played"', body)

    def test_unknown_world_form_value_rejected(self):
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/spin/run",
            data={"spin_kind": "first_spin", "world": "not_a_real_world"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Unknown Spin world", resp.get_data(as_text=True))
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.spin_runs, [])  # refused before any run was attempted

    def test_project_isolation_for_world_runs(self):
        other_project_id = "test-project-holodeck-worlds-route-other"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=other_project_id, filename="other.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client.get(f"/projects/{other_project_id}/workspace")
        other_workspace = self.store.get(other_project_id)
        self.store.record_spin_run(
            other_workspace, spin_kind=SPIN_KIND_FIRST, actor="owner1",
            findings=[{"tag": "Only in other project", "source_reference": "s", "concern": "c",
                       "unresolved_question": "q", "delta_classification": None, "related_prior_understanding": None}],
            source_signature="", world=SPIN_WORLD_SURVIVAL,
            games_played=[{"game": "Change Game", "triggered_by": "x", "finding": ""}],
        )
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=spin").get_data(as_text=True)
        self.assertNotIn("Only in other project", body)


if __name__ == "__main__":
    unittest.main()
