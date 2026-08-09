"""
CLAUDE-POSTCAMEL-VOICE1-PRE - Push-to-Talk Provider & Consent Resolution.

Resolves the two prerequisites CA1C's own audit left open: a speech-to-
text provider decision, and a designed consent/audio-handling UX.
Implements the smallest working Push-to-Talk slice, per the governing
prompt's own Concept-to-Implementation Rule, because the provider
chosen (the browser's own built-in Web Speech API) needs no new
Product Owner decision - no vendor contract, no API key, no cost.

This is overwhelmingly a client-side (template + JS + CSS) feature -
the transcript arrives at the server as ordinary composer text, through
the exact same route/form/context-envelope every typed message already
uses (see governance/current/voice1-pre-push-to-talk.md for the full
architecture). There is very little new server-side Python logic to
test; this file focuses on what IS server-rendered: the mic button's
own markup and attributes, and that nothing about the existing
composer/context-envelope regressed.

Run via:

    python -m unittest tests.test_voice1_pre_push_to_talk -v
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class VoiceButtonRenderingTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_voice1pre_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="voice1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                self.doc = ingest_upload(
                    _fake_file(b"founding content", "founding.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="voice1_owner", project_name="VOICE1-PRE Test Project",
                )
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "voice1_owner"
            sess["role"] = "admin"
        return client

    def test_mic_button_renders_hidden_by_default_server_side(self):
        """The button must start hidden in the raw HTML - only the
        client-side feature-detection script unhides it, never the
        server, so a browser with no JS at all never sees a false
        promise of voice input."""
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn('id="dock-composer-voice"', body)
        self.assertIn('data-ui-ref="chat.composer.voice"', body)
        # The raw <button ... hidden> attribute must be present server-side.
        voice_button_start = body.index('id="dock-composer-voice"')
        surrounding = body[max(0, voice_button_start - 200):voice_button_start + 300]
        self.assertIn("hidden", surrounding)

    def test_mic_button_never_has_a_type_submit(self):
        """The mic button must never itself submit the form - only fill
        the text field, exactly as if the reviewer had typed (Section 6,
        review-before-send)."""
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        voice_button_start = body.index('id="dock-composer-voice"')
        preceding = body[max(0, voice_button_start - 60):voice_button_start]
        self.assertIn('type="button"', preceding)

    def test_mic_button_carries_a_truthful_consent_label(self):
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn("processed by your browser only and is never saved", body)

    def test_composer_context_envelope_fields_still_present_alongside_voice_button(self):
        """Real regression guard: the new button must not have displaced
        or broken CA1A/CA1B's own hidden current_view/selected_source_id
        fields on the same form."""
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn('name="current_view"', body)
        self.assertIn('name="selected_source_id"', body)
        self.assertIn('id="dock-composer-input"', body)


if __name__ == "__main__":
    unittest.main()
