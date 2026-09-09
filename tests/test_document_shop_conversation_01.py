"""CLAUDE-DOCUMENT-SHOP-CONVERSATION-01 - "Ask GO about this document".

The properties that matter, in the order they would hurt if broken:

  1. NO IMAGE BYTES LEAVE THE HOST. A standing Product Owner constraint.
     `llm_gateway.call_llm_json` accepts image_base64; this feature must never
     pass it. Asserted at the call boundary with a spy, not by reading code.
  2. ONE DOCUMENT CONTEXT. Nothing from another document, another customer, or
     any Project reaches the provider.
  3. THE RESULT IS IMMUTABLE. A conversation explains; it never rewrites the
     examination, its evidence, or its sources.
  4. HONEST FAILURE. A provider outage is told to the customer, never a
     silently weaker answer wearing the same clothes.
"""
import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from models import ROLE_ADMIN, ROLE_CUSTOMER, User, db
from services import document_conversation as dc
from services import document_examination as dx
from services import llm_gateway
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import EVIDENCE_CLASS_EXTRACTED, CaseWorkspaceStore

PW = "TestCustomer!2026"
_REPO_ROOT = Path(__file__).resolve().parent.parent


class _Outcome:
    """Shaped like llm_gateway's own result, without importing its internals."""

    def __init__(self, ran=True, parsed=None, skipped_reason=None):
        self.ran = ran
        self.parsed = parsed
        self.raw_text = None
        self.skipped_reason = skipped_reason
        self.stop_reason = None
        self.provider = "test"
        self.model = "test"
        self.requested_at = None


def _fake_parse(_p, raw, filename):
    text = raw.decode("utf-8", errors="ignore")
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
        text_extraction_status="extracted" if text.strip() else "no_native_text")


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), (240, 240, 235)).save(buf, "PNG")
    return buf.getvalue()


class ConversationContextTests(unittest.TestCase):
    """What is assembled, and what is refused, before anything is sent."""

    def setUp(self):
        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_conv_"))
        self.store = CaseWorkspaceStore(self.tmp)
        self.ws = self.store.get_or_create(str(uuid.uuid4()))
        self.source_id = self.store.add_source(
            self.ws, name="spec.png", file_path=str(self.tmp / "spec.png"),
            kind="unclassified", actor="test")["id"]
        self.ws = self.store.get(self.ws.project_id)
        self.store.register_pdf_page_structure(
            self.ws, source_id=self.source_id,
            pages=["FIRE DAMPER SCHEDULE\n\nROOM 101 CLOSE ON ALARM"],
            extractor_version="tesseract 4.1.1", actor="test",
            evidence_class_by_page={0: EVIDENCE_CLASS_EXTRACTED})
        self.ws = self.store.get(self.ws.project_id)
        self.doc = ParsedDocument(project_id=self.ws.project_id, filename="spec.png",
                                  ingested_at="2026-09-09T00:00:00Z")
        self.result = dx.build_result(self.doc, self.ws, display_name="My scan")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_context_carries_this_documents_recovered_text(self):
        ctx = dc.build_context(self.doc, self.ws, self.result, "What does it say?")
        self.assertIn("FIRE DAMPER", ctx["recovered_text"])
        self.assertTrue(ctx["text_was_read_from_the_image"])
        self.assertIn("tesseract 4.1.1", ctx["read_by"])

    def test_context_carries_the_result_the_customer_can_see(self):
        ctx = dc.build_context(self.doc, self.ws, self.result, "?")
        self.assertTrue(ctx["established"])
        self.assertEqual(ctx["state"], self.result["state_label"])

    def test_another_sources_evidence_never_enters_the_context(self):
        """Two sources, ONE workspace, ONE customer - no access check can help
        here; only correct scoping keeps them apart."""
        other = self.store.add_source(
            self.ws, name="other.png", file_path=str(self.tmp / "other.png"),
            kind="unclassified", actor="test")["id"]
        self.ws = self.store.get(self.ws.project_id)
        self.store.register_pdf_page_structure(
            self.ws, source_id=other, pages=["UNRELATED CONFIDENTIAL CONTENT"],
            extractor_version="tesseract 4.1.1", actor="test",
            evidence_class_by_page={0: EVIDENCE_CLASS_EXTRACTED})
        self.ws = self.store.get(self.ws.project_id)
        ctx = dc.build_context(self.doc, self.ws, self.result, "?")
        self.assertIn("FIRE DAMPER", ctx["recovered_text"])
        self.assertNotIn("UNRELATED", ctx["recovered_text"])
        self.assertNotIn("UNRELATED", dc.render_prompt(ctx))

    def test_no_internal_identifiers_are_sent(self):
        prompt = dc.render_prompt(
            dc.build_context(self.doc, self.ws, self.result, "?"))
        self.assertNotIn(self.ws.project_id, prompt)
        self.assertNotIn(self.source_id, prompt)
        self.assertNotIn(str(self.tmp), prompt)

    def test_the_prompt_states_the_image_cannot_be_seen(self):
        prompt = dc.render_prompt(
            dc.build_context(self.doc, self.ws, self.result, "Where is the door?"))
        self.assertIn("cannot see the image", prompt)

    def test_the_system_prompt_forbids_inferring_layout_from_reading_order(self):
        # Normalised: the prompt is wrapped prose, so asserting on my own line
        # breaks would pin formatting rather than meaning.
        prompt = " ".join(dc.SYSTEM_PROMPT.split()).lower()
        self.assertIn("reading order, not page layout", prompt)
        self.assertIn("cannot see the image", prompt)
        for phrase in ("lower-right", "where is the entrance"):
            self.assertIn(phrase, prompt)

    def test_history_is_bounded(self):
        for i in range(40):
            self.store.add_message(self.ws, None, "human", "q%d" % i, actor="cust")
        self.ws = self.store.get(self.ws.project_id)
        ctx = dc.build_context(self.doc, self.ws, self.result, "?")
        self.assertLessEqual(len(ctx["history"]), dc.MAX_HISTORY_TURNS)


class ProviderBoundaryTests(unittest.TestCase):
    """The call itself: what goes, and what happens when nothing comes back."""

    def setUp(self):
        self.app = create_app("testing")
        self.app.config["ANTHROPIC_API_KEY"] = "test-key"
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_convp_"))
        self.store = CaseWorkspaceStore(self.tmp)
        self.ws = self.store.get_or_create(str(uuid.uuid4()))
        self.source_id = self.store.add_source(
            self.ws, name="scan.png", file_path=str(self.tmp / "scan.png"),
            kind="unclassified", actor="test")["id"]
        self.ws = self.store.get(self.ws.project_id)
        self.doc = ParsedDocument(project_id=self.ws.project_id, filename="scan.png",
                                  ingested_at="2026-09-09T00:00:00Z")
        self.result = dx.build_result(self.doc, self.ws, display_name="Scan")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_image_bytes_are_ever_sent(self):
        """THE constraint. Asserted at the boundary, not inferred from code."""
        seen = {}

        def spy(**kwargs):
            seen.update(kwargs)
            return _Outcome(parsed={"answer": "ok"})

        with patch.object(llm_gateway, "call_llm_json", spy):
            dc.ask(self.doc, self.ws, self.result, "What is this?", app=self.app)

        self.assertIsNone(seen.get("image_base64"),
                          "customer image bytes reached the provider")
        self.assertIsNone(seen.get("image_media_type"))
        self.assertNotIn("\x89PNG", seen.get("user_prompt", ""))
        self.assertNotIn("base64", (seen.get("user_prompt") or "").lower())

    def test_the_call_is_positional_free_and_inspectable(self):
        seen = {}

        def spy(**kwargs):
            seen.update(kwargs)
            return _Outcome(parsed={"answer": "ok"})

        with patch.object(llm_gateway, "call_llm_json", spy):
            dc.ask(self.doc, self.ws, self.result, "hello", app=self.app)
        self.assertIn("user_prompt", seen)
        self.assertIn("system_prompt", seen)
        self.assertEqual(seen["system_prompt"], dc.SYSTEM_PROMPT)

    def test_provider_failure_is_told_plainly_and_never_faked(self):
        with patch.object(llm_gateway, "call_llm_json",
                          lambda **k: _Outcome(ran=False, skipped_reason="timeout")):
            reply = dc.ask(self.doc, self.ws, self.result, "?", app=self.app)
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["answer"], dc.UNAVAILABLE_MESSAGE)
        self.assertIn("could not answer", reply["answer"])

    def test_an_empty_answer_is_a_failure_not_an_answer(self):
        with patch.object(llm_gateway, "call_llm_json",
                          lambda **k: _Outcome(parsed={"answer": "   "})):
            reply = dc.ask(self.doc, self.ws, self.result, "?", app=self.app)
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["answer"], dc.UNAVAILABLE_MESSAGE)

    def test_no_key_configured_says_so_rather_than_calling(self):
        self.app.config["ANTHROPIC_API_KEY"] = None

        def boom(**k):
            raise AssertionError("called the provider with no key configured")

        with patch.object(llm_gateway, "call_llm_json", boom):
            reply = dc.ask(self.doc, self.ws, self.result, "?", app=self.app)
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["answer"], dc.NOT_CONFIGURED_MESSAGE)

    def test_the_module_never_references_an_image_parameter(self):
        src = (_REPO_ROOT / "services" / "document_conversation.py").read_text(encoding="utf-8")
        code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
        self.assertNotIn("image_base64=", code)
        self.assertNotIn("image_media_type=", code)


class ConversationRouteTests(unittest.TestCase):
    """The customer journey, and what it must not disturb."""

    def setUp(self):
        self.app = create_app("testing")
        self.app.config["ANTHROPIC_API_KEY"] = "test-key"
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_convr_"))
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for name, role in (("cust", ROLE_CUSTOMER), ("cust2", ROLE_CUSTOMER),
                           ("boss", ROLE_ADMIN)):
            if not User.query.filter_by(username=name).first():
                from werkzeug.security import generate_password_hash
                u = User(username=name, role=role)
                u.password_hash = generate_password_hash(PW)
                db.session.add(u)
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _login(self, username="cust", client=None):
        (client or self.client).post(
            "/login", data={"username": username, "password": PW})

    def _job(self, data=b"The contractor shall provide detection.\n", name="spec.txt"):
        with patch.object(BHiveParser, "parse", _fake_parse):
            r = self.client.post("/document-shop", data={
                "file": (io.BytesIO(data), name),
                "name": "Job %s" % uuid.uuid4().hex[:8]},
                content_type="multipart/form-data")
        # Owner-scoped display-name uniqueness is a real rule: reusing one name
        # here made the SECOND upload fail silently, and the test then died on
        # a missing Location header instead of saying what went wrong.
        self.assertEqual(r.status_code, 302, "upload did not create a job")
        return r.headers["Location"].rstrip("/").split("/")[-1]

    def _ask(self, pid, question, answer="Here is what it says.", client=None):
        with patch.object(llm_gateway, "call_llm_json",
                          lambda **k: _Outcome(parsed={"answer": answer})):
            return (client or self.client).post(
                "/document-shop/jobs/%s" % pid, data={"question": question})

    def test_the_composer_is_offered_on_the_result(self):
        self._login()
        body = self.client.get("/document-shop/jobs/%s" % self._job()).get_data(as_text=True)
        self.assertIn("Ask GO about this document", body)
        self.assertIn('data-ui-ref="document-shop.conversation.input"', body)
        self.assertIn('data-ui-ref="document-shop.conversation.send"', body)

    def test_the_composer_form_renders_its_own_csrf_token(self):
        self._login()
        body = self.client.get("/document-shop/jobs/%s" % self._job()).get_data(as_text=True)
        form = body[body.index('class="ds-composer"'):]
        self.assertIn('name="csrf_token"', form[:form.index("</form>")])

    def test_disclosure_is_shown_where_the_decision_is_made(self):
        self._login()
        body = self.client.get("/document-shop/jobs/%s" % self._job()).get_data(as_text=True)
        self.assertIn('data-ui-ref="document-shop.conversation.disclosure"', body)
        self.assertIn("never sent", body)

    def test_a_question_and_answer_persist_and_render(self):
        self._login()
        pid = self._job()
        self._ask(pid, "What does this require?")
        body = self.client.get("/document-shop/jobs/%s" % pid).get_data(as_text=True)
        self.assertIn("What does this require?", body)
        self.assertIn("Here is what it says.", body)

    def test_turns_survive_a_fresh_session(self):
        """A phone that sleeps and comes back must not lose the thread."""
        self._login()
        pid = self._job()
        self._ask(pid, "First question")
        fresh = self.app.test_client()
        self._login(client=fresh)
        body = fresh.get("/document-shop/jobs/%s" % pid).get_data(as_text=True)
        self.assertIn("First question", body)

    def test_an_empty_question_is_refused_without_calling_the_provider(self):
        self._login()
        pid = self._job()

        def boom(**k):
            raise AssertionError("called the provider for an empty question")

        with patch.object(llm_gateway, "call_llm_json", boom):
            r = self.client.post("/document-shop/jobs/%s" % pid, data={"question": "  "})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Type a question first", r.get_data(as_text=True))

    def test_the_examination_result_is_unchanged_by_a_conversation(self):
        self._login()
        pid = self._job()
        store = CaseWorkspaceStore(self.app.config["REGISTRY_STORE_PATH"])
        before = self.client.get("/document-shop/jobs/%s" % pid).get_data(as_text=True)
        ws_before = store.get(pid)
        snapshot = (len(ws_before.sources), len(ws_before.evidence_items),
                    len(ws_before.structural_units), ws_before.container_state)

        self._ask(pid, "Explain this")

        ws_after = store.get(pid)
        self.assertEqual(
            (len(ws_after.sources), len(ws_after.evidence_items),
             len(ws_after.structural_units), ws_after.container_state), snapshot,
            "a conversation mutated the examination it was supposed to explain")
        after = self.client.get("/document-shop/jobs/%s" % pid).get_data(as_text=True)
        for section in ("What we can say from the file itself",
                        "What GO made of it", "What we could not establish"):
            self.assertEqual(section in before, section in after)

    def test_another_customer_cannot_read_or_post_to_this_conversation(self):
        self._login()
        pid = self._job()
        self._ask(pid, "Private question about my document")
        other = self.app.test_client()
        self._login("cust2", client=other)
        self.assertEqual(other.get("/document-shop/jobs/%s" % pid).status_code, 404)
        r = self._ask(pid, "Intruding", client=other)
        self.assertEqual(r.status_code, 404)

    def test_a_conversation_does_not_bleed_between_two_of_my_own_documents(self):
        self._login()
        first = self._job(b"First document content.\n", "one.txt")
        second = self._job(b"Second document content.\n", "two.txt")
        self._ask(first, "Question about the first")
        body = self.client.get("/document-shop/jobs/%s" % second).get_data(as_text=True)
        self.assertNotIn("Question about the first", body)

    def test_provider_outage_reaches_the_customer_as_words_not_a_500(self):
        self._login()
        pid = self._job()
        with patch.object(llm_gateway, "call_llm_json",
                          lambda **k: _Outcome(ran=False, skipped_reason="down")):
            r = self.client.post("/document-shop/jobs/%s" % pid,
                                 data={"question": "Anything?"})
        self.assertEqual(r.status_code, 302)
        body = self.client.get("/document-shop/jobs/%s" % pid).get_data(as_text=True)
        self.assertIn("could not answer", body)
        self.assertIn("Anything?", body)

    def test_no_internal_vocabulary_on_the_conversation_surface(self):
        self._login()
        pid = self._job()
        self._ask(pid, "Explain")
        body = self.client.get("/document-shop/jobs/%s" % pid).get_data(as_text=True)
        for term in ("As-Read", "Spin", "container_state", "project_conversation",
                     "ConversationMessage", "llm_gateway", "Anthropic"):
            self.assertNotIn(term, body)

    def test_an_image_job_can_be_asked_about_without_sending_the_image(self):
        self._login()
        pid = self._job(_png(), "scan.png")
        seen = {}

        def spy(**kwargs):
            seen.update(kwargs)
            return _Outcome(parsed={"answer": "I can read the text but not see it."})

        with patch.object(llm_gateway, "call_llm_json", spy):
            self.client.post("/document-shop/jobs/%s" % pid, data={"question": "What is this?"})
        self.assertIsNone(seen.get("image_base64"))
        self.assertNotIn("\x89PNG", seen.get("user_prompt", ""))


if __name__ == "__main__":
    unittest.main()
