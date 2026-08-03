"""
Conversation as a project-level aperture (no Case required): a reviewer
looking at a project-level governed object (a Requirement today) can
start talking about it without first opening an Investigation. The
message carries an Anchor naming what was in view and lands in
workspace.project_conversation, not any Case's embedded conversation -
see ConversationMessage's and CaseWorkspaceStore.add_message's own
docstrings for why this is a second list, not a migration of the first.

Honesty note (matches conversation_interpreter.py's own docstring):
none of this adds real language understanding. An anchor changes the
FALLBACK reply for otherwise-unrecognized text (acknowledging what was
in view) and a missing Case turns a would-be Case-bound action (Analyze,
evidence, Compare, correction) into an honest decline instead of a
crash - it does not make the interpreter smarter.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import REQUIREMENT_REGISTRATION_HUMAN_REGISTERED, CaseWorkspaceStore
from services.conversation_interpreter import interpret_message
from services.requirements_registry import RequirementsRegistry


class ConversationApertureRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_conversation_apertures_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-apertures"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _register_requirement(self):
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")  # registers the auto document Source
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        requirement = self.store.register_requirement(
            workspace,
            source_id=source_id,
            original_requirement_identifier="Section 3.1",
            text_reference="Contractor shall provide as-built drawings.",
            created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        return requirement

    def test_discuss_object_creates_a_project_conversation_message_with_no_case(self):
        requirement = self._register_requirement()

        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "Is this requirement still current?",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": "Section 3.1",
            },
        )
        self.assertEqual(resp.status_code, 302)

        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.project_conversation), 2)  # human + system reply
        human = workspace.project_conversation[0]
        self.assertIsNone(human["case_id"])
        self.assertEqual(human["anchor"]["anchor_type"], "requirement")
        self.assertEqual(human["anchor"]["anchor_id"], requirement["id"])

        # No Case exists anywhere - this did not silently create one.
        self.assertEqual(workspace.cases, [])

    def test_discuss_object_reply_acknowledges_the_anchor_honestly(self):
        requirement = self._register_requirement()

        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "just checking in on this one",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": "Section 3.1",
            },
        )

        workspace = self.store.get(self.project_id)
        system_reply = workspace.project_conversation[1]
        self.assertEqual(system_reply["role"], "system")
        self.assertEqual(system_reply["action_taken"], "anchor_acknowledged")
        self.assertIn("requirement", system_reply["text"])
        self.assertIn("Section 3.1", system_reply["text"])

    def test_discuss_object_blank_text_does_not_post_a_message(self):
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={"text": "  "},
        )
        self.assertEqual(resp.status_code, 302)
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.project_conversation, [])

    def test_project_conversation_renders_on_project_home(self):
        requirement = self._register_requirement()
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "Any update?",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": "Section 3.1",
            },
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        # CLAUDE-P40-VW7A-QA: the "Project Conversation (N)" heading text
        # was removed outright (a first correction moved it to the
        # composer as "Chat (N)"; the immediate follow-up removed THAT
        # too as a duplicate of the Lists panel's own "Chats" row, which
        # now carries the count instead - see base.html's own
        # lists.project.chats row).
        self.assertIn('Chats <span class="launcher-count">2</span>', body)
        self.assertNotIn("Project Conversation (2)", body)
        self.assertIn("Any update?", body)
        self.assertIn("Discuss this Requirement", body)

    def test_project_conversation_not_shown_inside_an_open_case(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases", data={"title": "Case A", "objective": "x"},
        )
        case = self.store.get(self.project_id).cases[0]
        resp = self.client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        self.assertNotIn("Project Conversation", resp.get_data(as_text=True))

    def test_posting_inside_an_open_case_still_lands_on_the_case_not_the_project(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases", data={"title": "Case A", "objective": "x"},
        )
        case = self.store.get(self.project_id).cases[0]
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/messages",
            data={"text": "hello"},
        )
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.project_conversation, [])
        case = next(c for c in workspace.cases if c["id"] == case["id"])
        self.assertEqual(len(case["conversation"]), 2)


class InterpretMessageWithoutACaseTests(unittest.TestCase):
    """Direct unit tests of the interpreter itself, independent of the
    route layer - covers the case=None branch added for project-level
    apertures."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_interpret_no_case_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("proj-x")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_case_bound_action_declines_honestly_without_a_case(self):
        result = interpret_message(
            text="Analyze this drawing for datum inconsistencies",
            workspace=self.workspace,
            case=None,
            store=self.store,
            artifacts_dir=self.tmp_dir,
            reviewer="owner1",
            focused_finding_id=None,
        )
        self.assertEqual(result.action_taken, "needs_case")
        self.assertIn("Investigation", result.reply_text)

    def test_unrecognized_text_with_no_anchor_and_no_case_is_the_original_generic_reply(self):
        # CLAUDE-P38 (OBS-01): text that looks like a question (starts
        # with "what"/"why"/etc., or ends in "?") is no longer generic-
        # unrecognized - it's attempted as a real, grounded project
        # question first (see test_project_qa.py). This message
        # deliberately doesn't look like a question at all, to keep
        # testing the true final fallback.
        result = interpret_message(
            text="just leaving a note here, nothing to action",
            workspace=self.workspace,
            case=None,
            store=self.store,
            artifacts_dir=self.tmp_dir,
            reviewer="owner1",
            focused_finding_id=None,
        )
        self.assertEqual(result.action_taken, "unrecognized")

    def test_unrecognized_text_with_an_anchor_acknowledges_it_instead(self):
        result = interpret_message(
            text="what a nice day",
            workspace=self.workspace,
            case=None,
            store=self.store,
            artifacts_dir=self.tmp_dir,
            reviewer="owner1",
            focused_finding_id=None,
            anchor={"anchor_type": "requirement", "anchor_id": "req-1", "description": "Section 3.1"},
        )
        self.assertEqual(result.action_taken, "anchor_acknowledged")
        self.assertIn("requirement", result.reply_text)
        self.assertIn("Section 3.1", result.reply_text)


class ApertureEscalationTests(unittest.TestCase):
    """
    The "contextual aperture -> Conversation -> Investigation" escalation:
    a project-level message that got an honest needs_case decline can be
    turned into a real Case that re-runs the same text (with its Anchor)
    for real - offered, never silent, and never for an ordinary
    unmatched question.
    """

    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_aperture_escalation_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-aperture-escalation"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _register_requirement(self):
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        return self.store.register_requirement(
            workspace,
            source_id=source_id,
            original_requirement_identifier="Section 3.1",
            text_reference="Contractor shall provide as-built drawings.",
            created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    def test_case_shaped_question_offers_start_investigation(self):
        requirement = self._register_requirement()
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "Analyze this drawing for datum inconsistencies",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": "Section 3.1",
            },
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertIn("Start an Investigation from this", resp.get_data(as_text=True))

    def test_ordinary_unmatched_question_does_not_offer_it(self):
        requirement = self._register_requirement()
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "just wondering about this one",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": "Section 3.1",
            },
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertNotIn("Start an Investigation from this", resp.get_data(as_text=True))

    def test_accepting_creates_a_case_titled_from_the_anchor_and_reruns_the_text(self):
        requirement = self._register_requirement()
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "Analyze this drawing for datum inconsistencies",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": "Section 3.1",
            },
        )
        workspace = self.store.get(self.project_id)
        system_message = workspace.project_conversation[1]
        self.assertTrue(system_message["action_taken"].startswith("needs_case:"))
        human_message_id = system_message["action_taken"].split(":", 1)[1]
        self.assertEqual(human_message_id, workspace.project_conversation[0]["id"])

        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/apertures/{human_message_id}/start-investigation",
        )
        self.assertEqual(resp.status_code, 302)

        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.cases), 1)
        case = workspace.cases[0]
        self.assertEqual(case["title"], "Section 3.1")
        self.assertEqual(len(case["conversation"]), 2)
        self.assertEqual(case["conversation"][0]["text"], "Analyze this drawing for datum inconsistencies")
        self.assertEqual(case["conversation"][0]["anchor"]["anchor_id"], requirement["id"])
        # Case-bound now for real - "analyze_failed" (no drawing Source
        # in the new Case), not another needs_case decline.
        self.assertEqual(case["conversation"][1]["action_taken"], "analyze_failed")

        # The original project-level message is untouched, not moved.
        self.assertEqual(len(workspace.project_conversation), 2)

    def test_delegation_button_disappears_after_a_later_message(self):
        requirement = self._register_requirement()
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "Analyze this drawing for datum inconsistencies",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": "Section 3.1",
            },
        )
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={"text": "never mind, something else entirely"},
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertNotIn("Start an Investigation from this", resp.get_data(as_text=True))


class RecentFocusTests(unittest.TestCase):
    """
    The contextual-companion continuity trail: a reviewer's own recent
    anchored conversation, resolved to each anchor's current state.
    Deliberately tested as a derived VIEW over ordinary
    ConversationMessage records, not a separate memory store - these
    tests exist to prove that property, not just the happy path.
    """

    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_recent_focus_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-recent-focus"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _register_requirement(self, client, identifier="Section 3.1"):
        client.get(f"/projects/{self.project_id}/workspace?view=overview")  # registers the auto document Source
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        return self.store.register_requirement(
            workspace,
            source_id=source_id,
            original_requirement_identifier=identifier,
            text_reference="Contractor shall provide as-built drawings.",
            created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    def _discuss(self, client, requirement, text="Any update?"):
        client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": text,
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": requirement["original_requirement_identifier"],
            },
        )

    def test_discussing_a_requirement_surfaces_it_in_recent_focus(self):
        requirement = self._register_requirement(self.client)
        self._discuss(self.client, requirement)

        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("Recent Focus (1)", body)
        self.assertIn("Contractor shall provide as-built drawings.", body)

    def test_recent_focus_is_per_reviewer_not_shared(self):
        requirement = self._register_requirement(self.client)
        self._discuss(self.client, requirement)

        other_client = self.flask_app.test_client()
        with other_client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "owner2"
            sess["role"] = "admin"

        resp = other_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("Recent Focus (0)", body)
        # owner2 can still see the message itself in Project Conversation -
        # that stays project-wide - just not in owner2's OWN focus trail.
        # CLAUDE-P40-VW7A-QA: the count now lives on the Lists "Chats"
        # row, not a "Project Conversation (N)" heading (removed).
        self.assertIn('Chats <span class="launcher-count">2</span>', body)

    def test_recent_focus_deduplicates_by_anchor_keeping_only_the_latest(self):
        requirement = self._register_requirement(self.client)
        self._discuss(self.client, requirement, text="first pass")
        self._discuss(self.client, requirement, text="second pass, still current?")

        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("Recent Focus (1)", body)

    def test_recent_focus_flags_a_requirement_adjudicated_after_the_message(self):
        requirement = self._register_requirement(self.client)
        self._discuss(self.client, requirement)

        self.client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement['id']}/adjudicate",
            data={"outcome": "Satisfied", "reasoning": "As-built set received.", "case_id": ""},
        )

        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("changed since you looked", body)

    def test_recent_focus_empty_state(self):
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("Recent Focus (0)", body)
        self.assertIn("anchored conversation", body)


if __name__ == "__main__":
    unittest.main()
