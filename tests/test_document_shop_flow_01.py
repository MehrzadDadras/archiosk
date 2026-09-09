"""CLAUDE-DOCUMENT-SHOP-FLOW-01 - four reported defects, one shared journey.

All four were observed by the Product Owner on a real phone, and three of them
turned out to be ONE cause:

  * "name is already in use" for a name never typed
  * "a photo can be uploaded but is not examined"
  * eight junk containers from one session

`ingest_upload` checked uniqueness against `project_name OR FILENAME`. iOS names
every photo from the library "image.jpg", so the second photo collided with the
first - on a filename, not on anything the customer chose. The upload was
REFUSED, which is why nothing appeared to be examined.

The fourth defect is separate: a working examination of a photographed drawing
read as gibberish, because the page said "Result ready - 14,306 characters
recovered" beside "No interpretation was reached", with OCR noise under a
heading that promised a reading.
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
from models import ROLE_CUSTOMER, User, db
from services import document_examination as dx
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import EVIDENCE_CLASS_EXTRACTED, CaseWorkspaceStore

PW = "TestCustomer!2026"
_REPO_ROOT = Path(__file__).resolve().parent.parent
INTAKE_HTML = (_REPO_ROOT / "templates" / "document_shop_intake.html").read_text(encoding="utf-8")
HELP_HTML = (_REPO_ROOT / "templates" / "help" / "file_types_and_limits.html").read_text(encoding="utf-8")

# Verbatim from the Product Owner's own phone upload, stored on production.
# Real OCR noise from a photographed drawing - not a hand-written imitation.
REAL_NOISE = ("Tt\nkee\nb\nhilii ' | aa\n117} | fr a3 iT\n1] |\n[ | (Ti] Ha rey cae) Fa\n"
              "he|\nrTrT\neee\n]\n \n \n, \n.\n~\njn\nae\n.\not\nq\nBaha 7\n:\nged ,adael\n"
              "hee eee\nTET\n:\nfreee\n*\nt Hie Hib\nH.\n1)\na\nPit\niI\nIE\nEE\n")


def _jpeg():
    """REAL JPEG bytes. image_intake verifies the signature against the
    extension, so PNG bytes named .jpg are refused - correctly, and it is not
    the defect under test here."""
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), (240, 240, 235)).save(buf, "JPEG")
    return buf.getvalue()


def _fake_parse(_p, raw, filename):
    text = raw.decode("utf-8", errors="ignore")
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
        text_extraction_status="extracted" if text.strip() else "no_native_text")


class PageCopyTests(unittest.TestCase):
    """Section 1: redundant explanation off the main surface, kept in Help."""

    def test_the_explanatory_paragraph_is_gone_from_the_main_surface(self):
        self.assertNotIn('data-ui-ref="document-shop.intro"', INTAKE_HTML)
        self.assertNotIn("GO will examine it", INTAKE_HTML)

    def test_the_controls_that_made_it_redundant_are_still_there(self):
        for ref in ("document-shop.page-title", "document-shop.file",
                    "document-shop.accepted-formats", "document-shop.name",
                    "document-shop.submit"):
            self.assertIn('data-ui-ref="%s"' % ref, INTAKE_HTML)

    def test_the_useful_part_was_preserved_in_help_not_deleted(self):
        self.assertIn("Document Shop", HELP_HTML)
        self.assertIn("does not have to become anything else", HELP_HTML)
        self.assertIn("Naming the work is optional", HELP_HTML)


class NameUniquenessTests(unittest.TestCase):
    """Section 2: the false positive, and the true collision that must stay."""

    def setUp(self):
        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_flow_"))
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        from werkzeug.security import generate_password_hash
        for name in ("cust", "cust2"):
            if not User.query.filter_by(username=name).first():
                u = User(username=name, role=ROLE_CUSTOMER)
                u.password_hash = generate_password_hash(PW)
                db.session.add(u)
        db.session.commit()
        self.client = self.app.test_client()
        self.client.post("/login", data={"username": "cust", "password": PW})

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _upload(self, name, filename="image.jpg", client=None):
        c = client or self.client
        with patch.object(BHiveParser, "parse", _fake_parse):
            r = c.post("/document-shop", data={
                "file": (io.BytesIO(_jpeg()), filename), "name": name},
                content_type="multipart/form-data")
        body = r.get_data(as_text=True)
        return r.status_code, ("already in use" in body)

    def test_two_unnamed_uploads_of_the_same_filename_both_succeed(self):
        """THE reported defect. iOS calls every photo image.jpg."""
        first, err1 = self._upload("")
        second, err2 = self._upload("")
        self.assertEqual(first, 302)
        self.assertFalse(err1)
        self.assertEqual(second, 302,
                         "a second unnamed photo was refused - the filename "
                         "fallback is back")
        self.assertFalse(err2, "told the customer a name they never typed is taken")

    def test_a_blank_name_never_produces_a_name_message(self):
        for _ in range(3):
            status, err = self._upload("   ")
            self.assertFalse(err)
            self.assertEqual(status, 302)

    def test_a_chosen_name_still_cannot_be_reused(self):
        """The rule itself is intact where it means something."""
        self.assertEqual(self._upload("Site survey")[0], 302)
        status, err = self._upload("Site survey")
        self.assertTrue(err, "a real duplicate chosen name was accepted")
        self.assertEqual(status, 400)

    def test_a_chosen_name_is_still_private_to_its_owner(self):
        self.assertEqual(self._upload("Shared words")[0], 302)
        other = self.app.test_client()
        other.post("/login", data={"username": "cust2", "password": PW})
        status, err = self._upload("Shared words", client=other)
        self.assertEqual(status, 302, "owner scoping was lost")
        self.assertFalse(err, "one customer learned another holds a name")


class ResultIntelligibilityTests(unittest.TestCase):
    """Sections 5-10: a working examination must not read as a finished one."""

    def setUp(self):
        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_flowr_"))
        self.store = CaseWorkspaceStore(self.tmp)
        self.ws = self.store.get_or_create(str(uuid.uuid4()))
        self.source_id = self.store.add_source(
            self.ws, name="image.jpg", file_path=str(self.tmp / "image.jpg"),
            kind="unclassified", actor="test")["id"]
        self.ws = self.store.get(self.ws.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _register(self, text):
        self.store.register_pdf_page_structure(
            self.ws, source_id=self.source_id, pages=[text],
            extractor_version="tesseract 4.1.1", actor="test",
            evidence_class_by_page={0: EVIDENCE_CLASS_EXTRACTED})
        self.ws = self.store.get(self.ws.project_id)

    def _doc(self, **kw):
        base = dict(project_id=self.ws.project_id, filename="image.jpg",
                    ingested_at="2026-09-09T00:00:00Z",
                    text_extraction_status="no_native_text")
        base.update(kw)
        return ParsedDocument(**base)

    def test_noise_with_no_interpretation_is_not_result_ready(self):
        """The exact production case, with the Product Owner's own OCR text."""
        self._register(REAL_NOISE)
        result = dx.build_result(self._doc(), self.ws, display_name="Photo")
        self.assertEqual(result["state"], dx.STATE_READ_NOT_INTERPRETED)
        self.assertEqual(result["state_label"], "Read, not interpreted")

    def test_it_says_nothing_was_concluded_without_judging_the_text(self):
        """CORRECTED after a live proof, CLAUDE-DOCUMENT-SHOP-FLOW-01.

        The first wording said the text "could not be made sense of". A clean
        photograph whose text OCR read perfectly got that caption too, because
        an image never reaches an interpretation at all - so the claim was
        false, in the opposite direction from the overclaim it replaced.
        """
        self._register(REAL_NOISE)
        result = dx.build_result(self._doc(), self.ws, display_name="Photo")
        labels = " ".join(i["label"] for i in result["not_established"])
        values = " ".join(i["value"] for i in result["not_established"])
        self.assertIn("Nothing has been concluded", labels)
        self.assertNotIn("could not be made sense of", labels)
        self.assertNotIn("not enough of them form readable words", values)

    def test_cleanly_read_text_is_not_described_as_unreadable(self):
        """The live case that caught the over-correction."""
        self._register("FIRE DAMPER SCHEDULE\nROOM 101 DETECTOR FD-1\n"
                       "DAMPER FD-1 CLOSE ON ALARM")
        result = dx.build_result(self._doc(), self.ws, display_name="Clean photo")
        blob = " ".join(i["label"] + " " + i["value"]
                        for i in result["not_established"])
        for false_claim in ("could not be made sense of", "unreadable",
                            "not enough of them form readable"):
            self.assertNotIn(false_claim, blob)
        self.assertIn("FIRE DAMPER", result["preview_text"])

    def test_the_raw_text_is_flagged_as_fragments_not_a_reading(self):
        self._register(REAL_NOISE)
        result = dx.build_result(self._doc(), self.ws, display_name="Photo")
        self.assertTrue(result["fragmentary"])
        values = " ".join(i["value"] for i in result["not_established"])
        self.assertIn("for you to judge", values)

    def test_the_character_count_is_not_left_reading_as_success(self):
        """14,306 characters of nothing is still nothing."""
        self._register(REAL_NOISE)
        result = dx.build_result(self._doc(), self.ws, display_name="Photo")
        established = " ".join(i["label"] for i in result["established"])
        self.assertIn("Text recovered", established)
        self.assertTrue(result["not_established"],
                        "a character count with no caveat beside it")

    def test_the_two_statements_no_longer_contradict(self):
        """It said 'Result ready' AND 'No interpretation was reached'."""
        self._register(REAL_NOISE)
        result = dx.build_result(self._doc(), self.ws, display_name="Photo")
        labels = " ".join(i["label"] for i in result["not_established"])
        self.assertNotIn("No interpretation was reached", labels,
                         "the vaguer duplicate line is still rendered")

    def test_a_real_interpretation_is_still_result_ready(self):
        from services.bhive_parser import RequirementItem
        self._register("The contractor shall provide detection.")
        doc = self._doc(text_extraction_status="extracted")
        doc.consistency_checked = True
        result = dx.build_result(doc, self.ws, display_name="Spec")
        self.assertEqual(result["state"], dx.STATE_RESULT_READY)
        self.assertFalse(result["fragmentary"])

    def test_nothing_recovered_at_all_is_still_needs_attention(self):
        result = dx.build_result(self._doc(), self.ws, display_name="Blank")
        self.assertEqual(result["state"], dx.STATE_NEEDS_ATTENTION)
        self.assertIn("No text could be read",
                      " ".join(i["label"] for i in result["not_established"]))

    def test_no_quality_score_is_invented(self):
        """Measured on real evidence, a word-ratio does not separate noise from
        signal (0.434 noise vs 0.195 legitimate). The state must come from
        records, never from a threshold pretending to be a measurement."""
        src = (_REPO_ROOT / "services" / "document_examination.py").read_text(encoding="utf-8")
        code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
        # Names of a MECHANISM, not words that may appear in prose. The module
        # documents why a score was rejected, and forbidding that vocabulary
        # would fail on the explanation rather than on an implementation.
        for invented in ("legibility", "quality_score", "confidence_threshold",
                         "def _score", "WORDLIKE", "_VOWEL"):
            self.assertNotIn(invented, code)


if __name__ == "__main__":
    unittest.main()
