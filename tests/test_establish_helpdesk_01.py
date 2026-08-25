"""
CLAUDE-ESTABLISH-HELPDESK-01 - the registry help desk.

Authorized by governance/records/GOV-D-001.md. These tests are the compliance
evidence that record names under "HOW COMPLIANCE IS DEMONSTRATED", so they are
written against the boundary the record draws, not merely against the feature.

The boundary, restated because it is the whole point: this surface may reason,
and may read one candidate founding document. It may not commit anything. No
project, no Source, no governance-log entry, no persisted conversation, no
persisted document. Registration stays behind the explicit controls on the form
below the helper.

Hermetic: every test replaces services.establish_help_desk.call_llm_json with a
spy. Nothing here may reach a real Anthropic API - CLAUDE.md's 8.5-hour incident
is what that rule is made of.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import services.establish_help_desk as helpdesk
from services.establish_help_desk import (
    ESTABLISH_HELP_DESK_CONTRACT, MAX_DOCUMENT_CHARS, advise, extract_candidate_text,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


class _Outcome:
    def __init__(self, ran=True, parsed=None, skipped_reason=None):
        self.ran = ran
        self.parsed = parsed or {}
        self.skipped_reason = skipped_reason


def _spy(reply="Advice.", record=None):
    def fake(**kwargs):
        if record is not None:
            record.append(kwargs)
        return _Outcome(parsed={"text": reply})
    return fake


def _flat(text: str) -> str:
    """Collapse the wrapped prose block onto one line.

    The contract is hard-wrapped, so "It has not been\\n   filed" does not
    contain "not been filed" - a phrase assertion would fail on where a line
    happens to break rather than on a missing rule.
    """
    return " ".join(text.split())


class TheContractForbidsTheThingsThatMatter(unittest.TestCase):
    """The system prompt is the only thing standing between a helpful reply and
    one that tells someone their project has been created."""

    def test_it_states_that_nothing_has_been_created(self):
        self.assertIn("created nothing and registered nothing",
                      _flat(ESTABLISH_HELP_DESK_CONTRACT))

    def test_it_forbids_advising_a_bypass_of_registration(self):
        self.assertIn("Never tell anyone to skip, bypass, or work around registration",
                      _flat(ESTABLISH_HELP_DESK_CONTRACT))

    def test_it_names_a_supplied_document_as_a_candidate_not_evidence(self):
        c = _flat(ESTABLISH_HELP_DESK_CONTRACT)
        self.assertIn("CANDIDATE, not evidence", c)
        self.assertIn("not been filed", c)

    def test_it_forbids_filling_a_gap_with_a_guess(self):
        # A wrong project name established at registration is expensive to fix,
        # which is the reason this conversation exists at all.
        self.assertIn("Never fill a gap with a plausible guess",
                      _flat(ESTABLISH_HELP_DESK_CONTRACT))

    def test_the_absolute_rules_come_first(self):
        c = ESTABLISH_HELP_DESK_CONTRACT
        self.assertLess(c.index("ABSOLUTE RULES"), c.index("WHAT YOU CAN ACTUALLY HELP WITH"))


class AdviseIsOneTurnAndCommitsNothing(unittest.TestCase):
    def test_it_answers_a_real_question(self):
        with patch.object(helpdesk, "call_llm_json", _spy("Declare the position "
                                                          "this project runs under.")):
            r = advise("If I am the architect and the CM, how should I register this?")
        self.assertTrue(r.ran)
        self.assertIn("position", r.text)
        self.assertFalse(r.read_document)

    def test_an_empty_question_never_reaches_the_model(self):
        calls = []
        with patch.object(helpdesk, "call_llm_json", _spy(record=calls)):
            r = advise("   ")
        self.assertFalse(r.ran)
        self.assertEqual(r.skipped_reason, "empty_message")
        self.assertEqual(calls, [])

    def test_the_document_is_passed_as_text_and_labelled_provisional(self):
        calls = []
        with patch.object(helpdesk, "call_llm_json", _spy(record=calls)):
            r = advise("How should I name this?",
                       document_text="PROJECT 222109 - 1860 ALSTEP DR",
                       document_name="drawings.pdf")
        self.assertTrue(r.read_document)
        prompt = calls[0]["user_prompt"]
        self.assertIn("222109", prompt)
        self.assertIn("NOT registered and NOT evidence", prompt)
        self.assertIn("drawings.pdf", prompt)

    def test_without_a_document_the_prompt_says_so_rather_than_staying_silent(self):
        calls = []
        with patch.object(helpdesk, "call_llm_json", _spy(record=calls)):
            advise("What should I call it?")
        self.assertIn("No document was supplied", calls[0]["user_prompt"])

    def test_an_empty_model_reply_is_not_passed_off_as_advice(self):
        with patch.object(helpdesk, "call_llm_json",
                          lambda **k: _Outcome(parsed={"text": "   "})):
            r = advise("anything")
        self.assertFalse(r.ran)
        self.assertEqual(r.skipped_reason, "empty_reply")

    def test_a_skipped_gateway_is_reported_not_swallowed(self):
        with patch.object(helpdesk, "call_llm_json",
                          lambda **k: _Outcome(ran=False, skipped_reason="no_api_key")):
            r = advise("anything")
        self.assertFalse(r.ran)
        self.assertEqual(r.skipped_reason, "no_api_key")


class ReadingACandidateDocumentWritesNothing(unittest.TestCase):
    def test_plain_text_is_read(self):
        text = extract_candidate_text(b"1860 Alstep Dr, project 222109", "founding.txt")
        self.assertIn("222109", text)

    def test_an_unsupported_extension_is_declined_quietly(self):
        # Declining is not an error worth interrupting the conversation for -
        # advise without it.
        self.assertEqual(extract_candidate_text(b"\x00\x01binary", "photo.heic"), "")

    def test_a_corrupt_file_does_not_raise(self):
        self.assertEqual(extract_candidate_text(b"not really a pdf", "broken.pdf"), "")

    def test_empty_bytes_are_declined(self):
        self.assertEqual(extract_candidate_text(b"", "empty.txt"), "")

    def test_a_long_document_is_truncated_rather_than_sent_whole(self):
        # This is a conversation, not an ingestion path, and must never become
        # one - a founding document's full text belongs in the real parse
        # pipeline after registration, where it gets provenance.
        text = extract_candidate_text(b"A" * (MAX_DOCUMENT_CHARS * 3), "big.txt")
        self.assertEqual(len(text), MAX_DOCUMENT_CHARS)

    def test_extraction_touches_no_file_on_disk(self):
        before = {p for p in _REPO_ROOT.rglob("*.txt") if ".git" not in str(p)}
        extract_candidate_text(b"transient content", "candidate.txt")
        after = {p for p in _REPO_ROOT.rglob("*.txt") if ".git" not in str(p)}
        self.assertEqual(before, after)

    def test_the_supported_set_matches_what_the_form_itself_accepts(self):
        # The helper must never read something the user could not have
        # submitted through the real path.
        form = (_REPO_ROOT / "templates" / "upload.html").read_text(encoding="utf-8")
        accept = form.split('accept="')[1].split('"')[0]
        self.assertEqual(sorted(helpdesk.SUPPORTED_EXTENSIONS),
                         sorted(accept.split(",")))


class TheRouteHonoursTheGovernanceBoundary(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            db.session.add(User(username="desk_admin",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "desk_admin"
            sess["role"] = "admin"

    def _post(self, message="how should I establish this project", **extra):
        data = {"message": message, "context": "establish-project"}
        data.update(extra)
        return self.client.post("/gateway/orientation", data=data)

    def test_a_real_question_now_gets_a_real_answer(self):
        # The defect this whole stage exists for: before it, this exact question
        # returned the keyword table's generic deflection.
        with patch("routes.portal._project_less_external_ai_allowed", lambda: True), \
             patch.object(helpdesk, "call_llm_json",
                          _spy("Declare the position this project is run under.")):
            resp = self._post("If I am the architect and the CM, how do I register this?")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("position this project is run under", resp.get_json()["text"])

    def test_it_falls_back_to_the_keyword_answer_when_external_ai_is_denied(self):
        # Degrading to a real FAQ answer beats degrading to an error, and it
        # keeps the pre-existing behaviour reachable rather than replaced.
        calls = []
        with patch("routes.portal._project_less_external_ai_allowed", lambda: False), \
             patch.object(helpdesk, "call_llm_json", _spy(record=calls)):
            resp = self._post("what does Client / Owner mean?")
        self.assertEqual(calls, [], "the model was called despite a denied gate")
        self.assertIn("Client / Owner", resp.get_json()["text"])

    def test_it_falls_back_when_the_model_cannot_run(self):
        with patch("routes.portal._project_less_external_ai_allowed", lambda: True), \
             patch.object(helpdesk, "call_llm_json",
                          lambda **k: _Outcome(ran=False, skipped_reason="no_api_key")):
            resp = self._post("what does Client / Owner mean?")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Client / Owner", resp.get_json()["text"])

    def test_the_gate_fails_closed_when_the_security_record_is_unreadable(self):
        from routes.portal import _project_less_external_ai_allowed
        with self.flask_app.test_request_context():
            with patch("services.security_governance.SecurityGovernanceStore",
                       side_effect=OSError("unreadable")):
                self.assertFalse(_project_less_external_ai_allowed())

    def _project_ids(self):
        from services.ingestion import get_registry
        with self.flask_app.app_context():
            return sorted(get_registry(self.flask_app).list_ids())

    def test_asking_creates_no_project(self):
        # Counted against the registry itself, not against page bytes: the
        # rendered page carries a fresh CSP nonce per request, so two identical
        # pages never compare equal and this would fail for a reason that has
        # nothing to do with project creation.
        with patch("routes.portal._project_less_external_ai_allowed", lambda: True), \
             patch.object(helpdesk, "call_llm_json", _spy()):
            before = self._project_ids()
            self._post("here is my drawing set, please register it for me")
            after = self._project_ids()
        self.assertEqual(before, after)

    def test_a_supplied_document_is_read_but_never_ingested(self):
        import io
        calls = []
        with patch("routes.portal._project_less_external_ai_allowed", lambda: True), \
             patch.object(helpdesk, "call_llm_json", _spy(record=calls)), \
             patch("services.ingestion.ingest_upload") as ingest:
            resp = self.client.post("/gateway/orientation", data={
                "message": "what should I call this?",
                "context": "establish-project",
                "candidate_document": (io.BytesIO(b"PROJECT 222109 - 1860 ALSTEP DR"),
                                       "founding.txt"),
            }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        ingest.assert_not_called()
        self.assertIn("222109", calls[0]["user_prompt"])

    def test_the_home_orientation_path_is_untouched(self):
        # GOV-D-001 authorizes ONE surface. The Product Owner explicitly held
        # Home orientation separate; it must still reach the rule-based
        # classifier and never the help desk.
        calls = []
        with patch.object(helpdesk, "call_llm_json", _spy(record=calls)):
            resp = self.client.post("/gateway/orientation", data={"message": "hello"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(calls, [], "the home orientation path reached the model")


if __name__ == "__main__":
    unittest.main()
