"""LIQUID SANDBOX - OBJECT FIELD v0. Focused proof.

Product Owner authorization (2026-09-26), built exactly: provisional media
retention; a lightweight SandboxObject; turns/attachments projected into
objects; an accessible outline; single/multi-selection; server-side
re-resolution of selected ids; selected objects as bounded Gopilot context.
No canvas, movement, groups, relationships, promotion changes or audio/video.

Selection follows GOV-P-001 - selection supplies context, never permission.
FPR-12 is not activated; the governed "Bug Eye" programme is not used.

Hermetic: every model call is a spy.
"""
from __future__ import annotations

import base64
import inspect
import json
import re
from pathlib import Path
from unittest.mock import patch

from services import llm_gateway
from services import sandbox as sb
from tests.test_sandbox_slice1_01 import MODEL_REPLY, _png_data_url, _Sandbox

MARKER_A = "The client wants a rooftop terrace on the townhouse."
MARKER_B = "The existing stair is too steep for code."
MARKER_C = "Budget is tight this year."


class _Field(_Sandbox):
    def turn(self, text="", data_url=None, selected=(), *, allowed=True, client=None):
        calls = []

        def spy(**kwargs):
            calls.append(kwargs)
            return MODEL_REPLY

        data = {"text": text, "object_id": list(selected)}
        if data_url:
            data["image_data_url"] = data_url
        with patch("routes.portal._project_less_external_ai_allowed", return_value=allowed), \
                patch.object(llm_gateway, "call_llm_json", side_effect=spy):
            response = (client or self.boss).post("/sandbox/turn", data=data)
        return response, calls

    def record(self, username="cover_boss"):
        return sb.SandboxStore(str(self.tmp)).get(username)

    def objects(self, kind=None):
        return [o for o in self.record()["objects"] if kind is None or o["type"] == kind]

    def seeded(self):
        """A: note + image, B: note, C: note - four objects, in field order."""
        self.turn(MARKER_A, _png_data_url(24, 16))
        self.turn(MARKER_B)
        self.turn(MARKER_C)
        a, image, b, c = self.objects()
        return a, image, b, c

    @staticmethod
    def selection_block(prompt):
        if "selected these provisional Sandbox objects" not in prompt:
            return []
        block = prompt.split("selected these provisional Sandbox objects", 1)[1].split("\n\n", 1)[0]
        return [json.loads(line) for line in block.splitlines() if line.startswith("{")]


class PastedImageSurvivesAsAProvisionalObject(_Field):
    def test_a_pasted_image_survives_reload_as_a_retained_provisional_object(self):
        data_url = _png_data_url(24, 16)
        self.turn("What is this crack?", data_url)
        note, image = self.objects()
        self.assertEqual((note["type"], image["type"]), ("note", "image"))
        for obj in (note, image):
            self.assertEqual((obj["status"], obj["canonical"]), ("provisional", False))
            self.assertEqual(obj["origin"]["turn"], 0)
        self.assertTrue(image["content"]["media"]["retained"])

        html = self.page()                                   # a fresh request - the reload
        self.assertIn('data-object-id="%s"' % image["id"], html)
        self.assertIn('src="/sandbox/media/%s"' % image["id"], html)
        served = self.boss.get("/sandbox/media/%s" % image["id"])
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served.data, base64.b64decode(data_url.split(",", 1)[1]))
        self.assertEqual(served.mimetype, "image/png")
        self.assertEqual(served.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", served.headers["Cache-Control"])

    def test_an_image_only_turn_makes_no_note_from_the_default_prompt(self):
        self.turn("", _png_data_url())
        self.assertEqual([o["type"] for o in self.objects()], ["image"])


class NoProjectOrEvidenceStoreReceivesIt(_Field):
    def test_the_image_lands_only_in_the_sandbox_store(self):
        self.planning_project("Existing Work")
        before = self.governed_state()
        data_url = _png_data_url(32, 32)
        raw = base64.b64decode(data_url.split(",", 1)[1])
        self.turn("Does this matter?", data_url)
        self.assertEqual(self.governed_state(), before)          # no project, study or case

        sha = self.objects("image")[0]["content"]["media"]["sha256"]
        sandbox_root = (self.tmp / "sandbox").resolve()
        roots = [self.tmp, Path(self.app.config["PROJECT_ASSET_PATH"])]
        holders = [p for root in roots if root.exists() for p in root.rglob("*")
                   if p.is_file() and sandbox_root not in p.resolve().parents
                   and (raw in p.read_bytes() or sha.encode() in p.read_bytes())]
        self.assertEqual(holders, [])
        retained = list(self.media.rglob("*.png"))
        self.assertEqual([p.name for p in retained], [sha + ".png"])


class SelectionIsExactlyTheSelectedObjects(_Field):
    def test_selecting_two_objects_sends_exactly_those_two(self):
        a, image, b, c = self.seeded()
        _, calls = self.turn("Compare these.", selected=[b["id"], image["id"]])
        self.assertEqual(len(calls), 1)
        block = self.selection_block(calls[0]["user_prompt"])
        self.assertEqual(len(block), 2)
        self.assertEqual([o["id"] for o in block], [image["id"], b["id"]])
        self.assertEqual(block[0]["content"]["image_number"], 1)
        self.assertEqual(block[0]["modality"], "image")
        self.assertEqual(block[1]["content"]["text"], MARKER_B)
        self.assertEqual(block[1]["modality"], "text")
        stored = self.store_bytes(image)
        self.assertEqual(calls[0]["images"], [(base64.b64encode(stored).decode("ascii"), "image/png")])
        self.assertIsNone(calls[0]["image_base64"])                     # no NEW image this turn
        self.assertEqual(self.record()["turns"][-1]["selected"], [image["id"], b["id"]])

    def test_a_single_selection_and_no_selection(self):
        a, image, b, c = self.seeded()
        _, calls = self.turn("Only this.", selected=[c["id"]])
        block = self.selection_block(calls[0]["user_prompt"])
        self.assertEqual([o["id"] for o in block], [c["id"]])
        self.assertEqual(block[0]["content"]["text"], MARKER_C)
        self.assertNotIn("images", calls[0])
        _, calls = self.turn("Nothing selected.")
        self.assertEqual(self.selection_block(calls[0]["user_prompt"]), [])

    def store_bytes(self, obj):
        return sb.SandboxStore(str(self.tmp), str(self.media)).read_media("cover_boss", obj)


class ForgedSelectionIdsAreIgnored(_Field):
    def test_unknown_and_other_peoples_ids_never_reach_gopilot(self):
        a, image, b, c = self.seeded()
        other = sb.SandboxStore(str(self.tmp))
        foreign = other.start("someone_else")
        other.add_turn("someone_else", foreign["id"], "SECRET neighbour note", {"canonical": False})
        foreign_id = other.get("someone_else")["objects"][0]["id"]

        response, calls = self.turn("Look at these.", selected=[a["id"], "f" * 32, foreign_id, "<script>"])
        prompt = calls[0]["user_prompt"]
        block = self.selection_block(prompt)
        self.assertEqual([o["id"] for o in block], [a["id"]])
        self.assertEqual(block[0]["content"]["text"], MARKER_A)
        self.assertNotIn("SECRET neighbour note", prompt)
        self.assertEqual(self.record()["turns"][-1]["reply"]["context"], {"selected": [a["id"]], "ignored": 3})
        self.assertEqual(self.record()["turns"][-1]["selected"], [a["id"]])
        self.assertIn("3 selected items were not in this Sandbox and were ignored.",
                      self.boss.get("/sandbox").get_data(as_text=True))


class ObjectEnvelope(_Field):
    def test_shared_preview_under_response_csp_and_touch_target(self):
        from playwright.sync_api import sync_playwright, expect
        from urllib.parse import urlsplit

        def respond(route):
            response = self.boss.get(urlsplit(route.request.url).path)
            route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.data)

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.route("http://sandbox.test/**", respond)
                page.goto("http://sandbox.test/sandbox")
                box = page.locator(".composer-attach").bounding_box()
                self.assertGreaterEqual(box["width"], 44)
                self.assertGreaterEqual(box["height"], 44)
                page.locator("#dock-composer-image").set_input_files({
                    "name": "sample.png", "mimeType": "image/png",
                    "buffer": base64.b64decode(_png_data_url().split(",", 1)[1])})
                expect(page.locator("#dock-capture-review-image")).to_have_js_property("complete", True)
                self.assertGreater(page.locator("#dock-capture-review-image").evaluate("img => img.naturalWidth"), 0)
                self.assertTrue(page.locator("#dock-capture-review-image").get_attribute("src").startswith("blob:"))
                page.click("#dock-capture-review-use")
                expect(page.locator("#dock-composer-image-data")).to_have_value(re.compile(r"data:image/"))
                self.assertEqual(page.locator("#dock-composer-input").get_attribute("placeholder"), "Ask about this photo")
                self.assertEqual(page.locator("#dock-composer-image-arrival").input_value(), "uploaded")
                page.click("#dock-composer-image-clear")
                self.assertEqual(page.locator("#dock-composer-image-arrival").input_value(), "unknown")
                page.evaluate("""async () => {
                    const canvas = document.createElement('canvas');
                    canvas.width = 48; canvas.height = 32;
                    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
                    const clipboard = new DataTransfer();
                    clipboard.items.add(new File([blob], 'paste.png', {type: 'image/png'}));
                    document.querySelector('#dock-composer-input').dispatchEvent(
                        new ClipboardEvent('paste', {clipboardData: clipboard, bubbles: true, cancelable: true}));
                }""")
                expect(page.locator("#dock-capture-review-image")).to_have_js_property("naturalWidth", 48)
                page.click("#dock-capture-review-use")
                expect(page.locator("#dock-composer-image-data")).to_have_value(re.compile(r"data:image/"))
                self.assertEqual(page.locator("#dock-composer-image-arrival").input_value(), "pasted")
                page.locator("#dock-composer-input").press_sequentially("A note")
                self.assertEqual(page.locator('input[name="text_arrival"]').input_value(), "typed")
                page.reload()
                expect(page.locator("#dock-composer-input")).to_have_value("A note")
                page.locator("#dock-composer-input").press_sequentially(" continued")
                self.assertEqual(page.locator('input[name="text_arrival"]').input_value(), "unknown")
            finally:
                browser.close()

    def test_scope_order_and_identity_survive_reload_and_legacy_completion(self):
        self.seeded()
        store = sb.SandboxStore(str(self.tmp), str(self.media))
        record = self.record()
        ids = [o["id"] for o in record["objects"]]
        for obj in record["objects"]:
            for key in ("sandbox_id", "owner", "sequence", "modality"):
                obj.pop(key)
            obj["origin"].pop("arrival")
        store._save(record)
        before = store._path("cover_boss").read_bytes()
        loaded = store.get("cover_boss")
        self.assertEqual(before, store._path("cover_boss").read_bytes())
        self.assertEqual([o["id"] for o in loaded["objects"]], ids)
        for index, obj in enumerate(loaded["objects"]):
            self.assertEqual((obj["owner"], obj["sandbox_id"], obj["sequence"]),
                             ("cover_boss", record["id"], index))
            self.assertEqual(obj["origin"]["arrival"], "unknown")
        self.turn("One more note")
        self.assertEqual([o["id"] for o in self.record()["objects"][:4]], ids)

    def test_note_mentioning_a_screenshot_remains_text_at_the_model_seam(self):
        self.turn("This screenshot shows a sketch; no image was attached.")
        obj = self.objects()[0]
        _, calls = self.turn("Consider this", selected=[obj["id"]])
        block = self.selection_block(calls[0]["user_prompt"])
        self.assertEqual((block[0]["type"], block[0]["modality"]), ("note", "text"))
        self.assertEqual(block[0]["id"], obj["id"])
        self.assertNotIn("images", calls[0])
        self.assertIsNone(calls[0]["image_base64"])

    def test_missing_selected_image_does_not_shift_image_binding(self):
        self.turn("", _png_data_url(24, 16))
        self.turn("", _png_data_url(32, 32))
        first, second = self.objects()
        store = sb.SandboxStore(str(self.tmp), str(self.media))
        media = first["content"]["media"]
        store._media_path("cover_boss", media["sha256"], media["media_type"]).unlink()
        _, calls = self.turn("Compare", selected=[first["id"], second["id"]])
        block = self.selection_block(calls[0]["user_prompt"])
        self.assertFalse(block[0]["content"]["available_to_model"])
        self.assertIsNone(block[0]["content"]["image_number"])
        self.assertEqual(block[1]["content"]["image_number"], 1)
        self.assertEqual(len(calls[0]["images"]), 1)

    def test_arrival_is_bounded_and_cannot_forge_scope_or_authority(self):
        with patch.object(llm_gateway, "call_llm_json", return_value=MODEL_REPLY), \
                patch("routes.portal._project_less_external_ai_allowed", return_value=True):
            self.boss.post("/sandbox/turn", data={
                "text": "A pasted note", "text_arrival": "pasted", "image_arrival": "uploaded",
                "image_data_url": _png_data_url(), "owner": "another_person",
                "canonical": "true", "type": "evidence", "created_by": "model"})
        note, image = self.objects()
        self.assertEqual(note["origin"]["arrival"], "pasted")
        self.assertEqual(image["origin"]["arrival"], "uploaded")
        for obj in (note, image):
            self.assertEqual(obj["owner"], "cover_boss")
            self.assertEqual(obj["created_by"], "person")
            self.assertFalse(obj["canonical"])
            self.assertEqual(obj["status"], "provisional")
        self.assertEqual(sb.arrival("generated", sb.OBJECT_NOTE), "unknown")
        self.assertEqual(sb.arrival("typed", sb.OBJECT_IMAGE), "unknown")

    def test_blob_permission_is_exclusive_to_image_sources(self):
        response = self.boss.get("/sandbox")
        directives = response.headers["Content-Security-Policy"].split(";")
        blob = [d.strip() for d in directives if "blob:" in d]
        self.assertEqual(blob, ["img-src 'self' data: blob:"])
        self.assertIn("object-src 'none'", response.headers["Content-Security-Policy"])


class SelectionChangesContextNeverAuthority(_Field):
    def test_a_selected_image_never_leaves_when_policy_denies(self):
        a, image, b, c = self.seeded()
        _, calls = self.turn("What about this?", selected=[image["id"]], allowed=False)
        self.assertEqual(calls, [])                                   # no model call at all
        self.assertEqual(self.record()["turns"][-1]["reply"]["organization"]["source"], "deterministic")

    def test_selecting_creates_nothing_governed_and_unlocks_nothing(self):
        before = self.governed_state()
        a, image, b, c = self.seeded()
        self.turn("Make a project from these.", selected=[a["id"], b["id"], image["id"]])
        self.assertEqual(self.governed_state(), before)
        report = self.sandbox_scope()["capabilities"]
        self.assertEqual(report["selection_context"]["state"], "INHERITED")
        self.assertEqual(report["draft_assist"]["state"], "BLOCKED")
        self.assertEqual(report["case_actions"]["state"], "EXPLICITLY DISABLED")
        # The landing owner never reads a selection: a decision stays the person's own act.
        from routes import sandbox as sandbox_routes
        self.assertNotIn("object_id", inspect.getsource(sandbox_routes.landing))
        self.assertIsNone(self.record()["promoted_to"])

    def test_a_customer_has_no_sandbox_selection(self):
        cust = self.client("cover_cust")
        self.assertEqual(cust.post("/sandbox/turn", data={"text": "hi", "object_id": ["x"]}).status_code, 404)

    def sandbox_scope(self):
        import app as app_module
        seen = []
        original = app_module.resolve_go_scope
        with patch.object(app_module, "resolve_go_scope", lambda v: seen.append(original(v)) or seen[-1]):
            self.page()
        return next(s for s in seen if s["label"] == "Sandbox")


class OutlineAgreesWithStoredState(_Field):
    def test_the_outline_is_the_stored_objects_in_order(self):
        self.seeded()
        html = self.page()
        rendered = re.findall(r'data-object-id="(\w+)" data-object-type="(\w+)"', html)
        self.assertEqual(rendered, [(o["id"], o["type"]) for o in self.record()["objects"]])
        self.assertRegex(html, r"4 provisional\s+objects")
        for obj in self.record()["objects"]:
            box = re.search(r'<input type="checkbox" id="sandbox-object-%s"[^>]*>' % obj["id"], html).group(0)
            self.assertIn('form="sandbox-selection"', box)
            self.assertIn('name="object_id"', box)
            self.assertIn('<label for="sandbox-object-%s">' % obj["id"], html)   # every box is labelled
        form = re.search(r'<form[^>]*data-ui-ref="chat.composer"[^>]*>', html).group(0)
        self.assertIn('data-go-selection="sandbox-selection"', form)
        self.assertIn('data-go-selection-name="object_id"', form)
        self.assertIn("data-go-selection-optional", form)

    def test_a_sandbox_from_before_the_object_field_projects_honestly(self):
        store = sb.SandboxStore(str(self.tmp))
        record = store.start("cover_boss")
        record.pop("objects")
        record["turns"] = [{"at": "t", "text": "Old idea", "reply": {
            "organization": {"objective": "Old idea", "known_facts": [], "unknowns": [], "constraints": [],
                             "next_questions": [], "source": "deterministic"},
            "external": {"appropriate": False}, "landing": None, "canonical": False, "attachments": [
            {"kind": "image", "media_type": "image/png", "bytes": 900, "sha256": "0" * 64,
             "analysed": True, "status": "provisional", "canonical": False}]}}]
        store._save(record)
        with self.boss.session_transaction() as s:
            s["sandbox_id"] = record["id"]
        html = self.page()
        self.assertIn("Old idea", html)
        self.assertIn("not retained (sent before images were kept)", html)
        image = [o for o in store.get("cover_boss")["objects"] if o["type"] == "image"][0]
        self.assertEqual([o["id"] for o in store.get("cover_boss")["objects"]],
                         [o["id"] for o in store.get("cover_boss")["objects"]])   # stable across reads
        self.assertIn('data-object-id="%s"' % image["id"], html)
        self.assertEqual(self.boss.get("/sandbox/media/%s" % image["id"]).status_code, 404)


class ProvisionalMediaIsNotAvailableToProjectRetrieval(_Field):
    def test_only_the_owner_can_see_it_and_only_through_the_sandbox(self):
        from models import ROLE_ADMIN, User, db
        from werkzeug.security import generate_password_hash

        self.turn("Photo", _png_data_url())
        image = self.objects("image")[0]
        user = User(username="cover_other", role=ROLE_ADMIN)
        user.password_hash = generate_password_hash(self.PW)
        db.session.add(user)
        db.session.commit()
        self.assertEqual(self.client("cover_other").get("/sandbox/media/%s" % image["id"]).status_code, 404)
        self.assertEqual(self.client("cover_cust").get("/sandbox/media/%s" % image["id"]).status_code, 404)

    def test_no_project_reader_knows_where_sandbox_media_lives(self):
        root = Path(__file__).resolve().parents[1]
        owners = {"services/sandbox.py", "routes/sandbox.py"}
        for folder in ("services", "routes", "engine"):
            for module in (root / folder).rglob("*.py"):
                rel = module.relative_to(root).as_posix()
                if rel in owners:
                    continue
                code = module.read_text(encoding="utf-8")
                with self.subTest(module=rel):
                    self.assertNotIn("media_root", code)
                    self.assertNotIn("SANDBOX_MEDIA_PATH", code)
                    self.assertNotIn("read_media(", code)
                    self.assertNotRegex(code, r'/\s*"sandbox"')          # no path into the store

    def test_retention_ends_with_the_sandbox(self):
        self.turn("Photo", _png_data_url())
        image = self.objects("image")[0]
        self.boss.get("/sandbox?new=1")
        self.turn("A new idea")
        self.assertEqual(self.boss.get("/sandbox/media/%s" % image["id"]).status_code, 404)
        self.assertEqual(list(self.media.rglob("*.png")), [])


class CapsRefuseRatherThanTruncate(_Field):
    def test_a_full_field_refuses_the_turn_and_sends_nothing(self):
        with patch.object(sb, "MAX_OBJECTS", 2):
            self.turn(MARKER_A, _png_data_url())
            before = self.record()
            _, calls = self.turn(MARKER_B)
        self.assertEqual(calls, [])
        self.assertEqual(self.record()["objects"], before["objects"])
        self.assertEqual(len(self.record()["turns"]), 1)
        self.assertIn("This Sandbox is full (2 objects)", self.page())

    def test_the_turn_cap_refuses_instead_of_dropping_the_oldest(self):
        with patch.object(sb, "MAX_TURNS", 2):
            self.turn(MARKER_A)
            self.turn(MARKER_B)
            _, calls = self.turn(MARKER_C)
        self.assertEqual(calls, [])
        self.assertEqual([t["text"] for t in self.record()["turns"]], [MARKER_A, MARKER_B])

    def test_image_caps_refuse(self):
        with patch.object(sb, "MAX_MEDIA_OBJECTS", 1):
            self.turn("one", _png_data_url())
            _, calls = self.turn("two", _png_data_url(20, 20))
        self.assertEqual(calls, [])
        self.assertEqual(len(self.objects("image")), 1)

    def test_an_oversized_selection_is_refused_not_cut_down(self):
        a, image, b, c = self.seeded()
        with patch.object(sb, "MAX_SELECTION", 2):
            _, calls = self.turn("All of it.", selected=[a["id"], b["id"], c["id"]])
        self.assertEqual(calls, [])
        self.assertEqual(len(self.record()["turns"]), 3)
        self.assertIn("Select at most 2 objects", self.page())


class TheGatewayCarriesSeveralImagesAdditively(_Field):
    def test_images_become_vision_blocks_in_order_and_old_callers_are_unchanged(self):
        sent = []

        class _Messages:
            def create(self, **kwargs):
                sent.append(kwargs)
                raise RuntimeError("stop here")

        fake = type("C", (), {"messages": _Messages()})()
        with patch.object(llm_gateway, "anthropic_client", return_value=(fake, None)):
            llm_gateway.call_llm_json("q", api_key="k", model="m", image_base64="AAA", image_media_type="image/png",
                                      images=[("BBB", "image/jpeg"), ("CCC", "image/webp")])
            llm_gateway.call_llm_json("plain", api_key="k", model="m")
        blocks = sent[0]["messages"][0]["content"]
        self.assertEqual([b.get("source", {}).get("data") for b in blocks[:3]], ["AAA", "BBB", "CCC"])
        self.assertEqual(blocks[3], {"type": "text", "text": "q"})
        self.assertEqual(sent[1]["messages"][0]["content"], "plain")


class SelectionInTheBrowser(_Field):
    """Real Chromium drives go_composer.js on the real Sandbox page."""

    def test_multi_selection_counts_and_travels_with_the_message(self):
        from playwright.sync_api import sync_playwright
        from tests.test_sandbox_slice1_01 import SandboxMediaInBrowser

        a, image, b, c = self.seeded()
        with sync_playwright() as pw:
            browser, page = SandboxMediaInBrowser.browser_page(self, pw, 1440, 900)
            count = lambda: page.inner_text('[data-ui-ref="sandbox.selection-count"]').strip()
            submit = """() => { const f = document.querySelector('form[data-ui-ref="chat.composer"]');
                window.__sent = null;
                f.addEventListener('submit', e => { window.__prevented = e.defaultPrevented;
                                                    window.__sent = new FormData(f).getAll('object_id');
                                                    e.preventDefault(); }, {once: true});
                f.requestSubmit(); }"""
            self.assertEqual(count(), "")
            # Nothing selected: an ordinary message, not a refusal (My Documents refuses).
            page.fill("#dock-composer-input", "Nothing selected.")
            page.evaluate(submit)
            none, prevented = page.evaluate("window.__sent"), page.evaluate("window.__prevented")
            page.check("#sandbox-object-%s" % b["id"])
            self.assertEqual(count(), "1 object selected - sent as context with your next message")
            page.focus("#sandbox-object-%s" % image["id"])               # keyboard: Space toggles the box
            page.keyboard.press("Space")
            self.assertEqual(count(), "2 objects selected - sent as context with your next message")
            page.fill("#dock-composer-input", "Compare these.")
            page.evaluate(submit)          # the selection handler adds the fields before any guard
            sent = page.evaluate("window.__sent")
            overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            browser.close()
        self.assertEqual(sorted(sent), sorted([b["id"], image["id"]]))
        self.assertEqual(none, [])                   # an empty selection is an ordinary message
        self.assertFalse(prevented)
        self.assertFalse(overflow)

    def test_the_outline_fits_a_phone(self):
        from playwright.sync_api import sync_playwright
        from tests.test_sandbox_slice1_01 import SandboxMediaInBrowser

        self.seeded()
        with sync_playwright() as pw:
            browser, page = SandboxMediaInBrowser.browser_page(self, pw, 390, 844)
            overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            box = page.evaluate("""(() => { const r = document.querySelector('[data-ui-ref="sandbox.outline.select"]')
                .getBoundingClientRect(); return [r.width, r.height]; })()""")
            browser.close()
        self.assertFalse(overflow)
        self.assertGreaterEqual(min(box), 20)
