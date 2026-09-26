"""GOPILOT NERVOUS SYSTEM - Foundation 01. Structural proof of inheritance.

NEW SURFACE = CONTEXT + AUTHORITY + EXPLICIT EXCEPTIONS.

Every canonical Composer scope inherits the capability contract declared beside
app.resolve_go_scope; a capability is off only when the scope names it, with a
reason, in disabled=/blocked=. Every Composer image, on every surface, enters
through ONE governed intake (services/composer_image). These tests fail when a
new surface re-lists, omits or bypasses either.
"""
from __future__ import annotations

import base64
import inspect
import io
import re
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import app as app_module
from services import composer_image
from tests.test_gopilot_turn_coverage_01 import _App

ROOT = Path(__file__).resolve().parent.parent


def data_url(media_type="image/png", payload=None):
    if payload is None:
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), (10, 120, 90)).save(buf, "PNG")
        payload = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:%s;base64,%s" % (media_type, payload)


# -- 1-5: the ONE governed image intake --------------------------------------------
class OneGovernedImageIntake(unittest.TestCase):
    def test_1_allowed_raster_types_under_the_limit_pass(self):
        for media_type in composer_image.ALLOWED_MEDIA_TYPES:
            with self.subTest(media_type=media_type):
                image = composer_image.validate(data_url(media_type))
                self.assertTrue(image.accepted)
                self.assertEqual(image.media_type, media_type)

    def test_2_an_oversized_image_is_rejected_before_decoding(self):
        big = "A" * (int(composer_image.MAX_IMAGE_BYTES * 4 / 3) + 8)
        image = composer_image.validate(data_url("image/png", big))
        self.assertEqual(image.status, composer_image.STATUS_TOO_LARGE)
        self.assertIsNone(image.base64)

    def test_3_svg_and_other_types_are_rejected(self):
        for hostile in ("data:image/svg+xml;base64,PHN2Zy8+", "data:image/bmp;base64,Qk0=",
                        "data:image/tiff;base64,SUkq"):
            with self.subTest(hostile=hostile):
                self.assertEqual(composer_image.validate(hostile).status, composer_image.STATUS_UNSUPPORTED)
        for malformed in ("data:text/html;base64,PHA+", "javascript:alert(1)", "data:image/png;base64,",
                          "data:image/png;base64,***not base64***", "data:image/png,rawbytes"):
            with self.subTest(malformed=malformed):
                self.assertEqual(composer_image.validate(malformed).status, composer_image.STATUS_MALFORMED)
        self.assertEqual(composer_image.validate("").status, composer_image.STATUS_ABSENT)

    def test_4_workspace_developer_and_sandbox_use_the_same_validator(self):
        """Every route module that reads a Composer image reads it through the
        shared intake - and nothing else parses a data: URL for itself."""
        readers = {}
        for module in (ROOT / "routes").glob("*.py"):
            code = "\n".join(l for l in module.read_text(encoding="utf-8").splitlines()
                             if not l.strip().startswith("#"))
            # A reader either names the field or takes it through the intake
            # (from_request reads image_data_url by default).
            if "image_data_url" in code or "composer_image." in code:
                readers[module.name] = code
            with self.subTest(module=module.name):
                self.assertNotIn('startswith("data:image/")', code)
                self.assertNotIn("def _parse_image_data_url", code)
        for name, code in readers.items():
            with self.subTest(reader=name):
                if "composer_image." in code:
                    continue
                # The only other permitted reader is an explicit refusal (Planning).
                refusing = [line for line in code.splitlines() if "image_data_url" in line]
                self.assertTrue(all("abort(" in code[code.index(line):code.index(line) + 300]
                                    for line in refusing), name)
        self.assertIn("composer_image.", readers["workspace.py"])
        self.assertIn("composer_image.", readers["portal.py"])
        self.assertIn("composer_image.", readers["sandbox.py"])
        self.assertEqual(readers["workspace.py"].count("composer_image.validate(")
                         + readers["workspace.py"].count("composer_image.from_request("), 2)

    def test_5_policy_denial_drops_the_image_so_nothing_can_send_it(self):
        image = composer_image.from_request({"image_data_url": data_url()}, policy_allowed=lambda: False)
        self.assertEqual(image.status, composer_image.STATUS_POLICY_DENIED)
        self.assertIsNone(image.base64)


# -- 12-13: every canonical Composer scope, rendered, with its inheritance report ---
@contextmanager
def capture_scopes():
    seen = []
    original = app_module.resolve_go_scope

    def spy(values):
        result = original(values)
        seen.append(result)
        return result

    with patch.object(app_module, "resolve_go_scope", spy):
        yield seen


STATIC_SCOPES = set(re.findall(r'return scope\("([A-Z_]+)", "([^"]+)"',
                               inspect.getsource(app_module.resolve_go_scope)))


class EveryComposerSurfaceInheritsTheContract(_App):
    def render_all(self):
        from services.case_workspace import CaseWorkspaceStore

        boss = self.client("cover_boss")
        pid = self.upload(boss, "Nervous System")
        store = CaseWorkspaceStore(str(self.tmp))
        workspace = store.get(pid)
        source_id = workspace.sources[0]["id"]
        case = store.create_case(workspace, "Case", "objective", created_by="cover_boss")
        pages = [(boss, "/projects"), (boss, "/document-shop/jobs"), (boss, "/document-shop/jobs/%s" % pid),
                 (boss, "/projects/%s/workspace" % pid),
                 (boss, "/projects/%s/workspace?source=%s" % (pid, source_id)),
                 (boss, "/projects/%s/workspace?case=%s" % (pid, case["id"])),
                 (boss, "/project/%s/manage/access" % pid), (boss, "/sandbox")]
        cust = self.client("cover_cust")
        pages += [(cust, "/document-shop/jobs"), (cust, "/help")]
        with capture_scopes() as seen:
            for client, url in pages:
                self.assertEqual(client.get(url).status_code, 200, url)
            boss.post("/developer-mode/toggle")
            self.assertEqual(boss.get("/help").status_code, 200)
            boss.post("/developer-mode/toggle")
        return seen

    def test_12_every_scope_reports_every_capability_with_reasons(self):
        seen = self.render_all()
        labels = set()
        for scope in seen:
            caps = scope["capabilities"]
            labels.add((scope["kind"], scope["label"]))
            with self.subTest(scope=(scope["kind"], scope["label"])):
                self.assertEqual(set(caps), set(app_module.COMPOSER_CAPABILITIES))
                for name, state in caps.items():
                    self.assertIn(state["state"], (app_module.CAPABILITY_INHERITED,
                                                   app_module.CAPABILITY_DISABLED,
                                                   app_module.CAPABILITY_BLOCKED), name)
                    if state["state"] != app_module.CAPABILITY_INHERITED:
                        self.assertTrue(state["reason"].strip(), name)
                    else:
                        self.assertEqual(state["reason"], "")
                # The rendered attach control IS the declared capability.
                self.assertEqual(scope["dock"]["attach"],
                                 caps["image_attach"]["state"] == app_module.CAPABILITY_INHERITED)
        # Every static scope branch was exercised here (the Planning study is proved
        # in the pytest function below) - a new branch that is never rendered fails.
        missing = STATIC_SCOPES - labels - {("PLANNING_STUDY", "Planning study")}
        self.assertEqual(missing, set(), "a Composer scope nobody proved: %s" % missing)

    def test_13_existing_surfaces_keep_exactly_their_behaviour(self):
        expected_attach = {
            ("APPLICATION", "Application"): False,             # staff Gateway orientation; customer (disabled)
            ("APPLICATION", "Selected documents"): False,      # My Documents
            ("DOCUMENT", "Document"): False,
            ("PROJECT", "Project"): True, ("SOURCE", "Document"): True,
            ("INVESTIGATION", "Investigation"): True,
            ("APPLICATION", "Application · Developer"): True,
            ("APPLICATION", "Sandbox"): True,
        }
        for scope in self.render_all():
            key = (scope["kind"], scope["label"])
            if key in expected_attach:
                with self.subTest(scope=key):
                    self.assertEqual(scope["dock"]["attach"], expected_attach[key])

    def test_every_attach_enabled_scope_posts_through_the_shared_intake(self):
        adapter = self.app.url_map.bind("localhost")
        for scope in self.render_all():
            if scope["capabilities"]["image_attach"]["state"] != app_module.CAPABILITY_INHERITED:
                continue
            endpoint, _ = adapter.match(scope["dock"]["post_url"], method="POST")
            source = inspect.getsource(self.app.view_functions[endpoint])
            with self.subTest(scope=(scope["kind"], scope["label"]), endpoint=endpoint):
                self.assertTrue("composer_image." in source or "_composer_photo_turn(" in source, endpoint)
        import routes.workspace as ws
        self.assertIn("composer_image.validate(", inspect.getsource(ws._composer_photo_turn))

    def test_capture_is_semantic_per_scope(self):
        boss = self.client("cover_boss")
        pid = self.upload(boss, "Capture")
        tag = lambda html: re.search(r'<input type="file" id="dock-composer-image"[^>]*>', html).group(0)
        self.assertIn('capture="environment"', tag(boss.get("/projects/%s/workspace" % pid).get_data(as_text=True)))
        self.assertNotIn("capture=", tag(boss.get("/sandbox").get_data(as_text=True)))


class TheContractCannotBeBypassedByANewSurface(unittest.TestCase):
    def test_a_raw_capability_flag_is_refused(self):
        source = inspect.getsource(app_module.resolve_go_scope)
        self.assertIn('if "attach" in dock:', source)
        self.assertIn("raise TypeError", source)
        body = source[source.index("def developer_scope"):]
        self.assertNotRegex(body, r"\battach=(True|False)")

    def test_switching_a_capability_off_needs_a_known_name_and_a_reason(self):
        with self.assertRaises(ValueError):
            app_module.composer_capabilities({}, {"image_attach": "  "}, {})
        with self.assertRaises(ValueError):
            app_module.composer_capabilities({}, {"telepathy": "not built"}, {})
        report = app_module.composer_capabilities({"project_id": "p"}, {}, {})
        self.assertTrue(all(v["state"] == app_module.CAPABILITY_INHERITED for v in report.values()
                            if v is not report["selection_context"]))


# -- The Planning study scope (pytest fixture) ---------------------------------------
from tests.test_planning_word_export_405 import setup_export, sign_in  # noqa: E402,F401


def test_planning_study_scope_declares_its_text_only_exception(setup_export):
    from services import planning_composer as composer, planning_studies as studies

    app, store, result, _ = setup_export
    client = sign_in(app)
    key = studies.WorkingResults(store.store_path).put("p", "export-planner", composer.initialize([result]))
    with capture_scopes() as seen:
        assert client.get("/planning-zoning/projects/p/working/%s" % key).status_code == 200
    study = next(s for s in seen if s["kind"] == "PLANNING_STUDY")
    assert study["capabilities"]["image_attach"]["state"] == app_module.CAPABILITY_DISABLED
    assert "400" in study["capabilities"]["image_attach"]["reason"]
    assert study["dock"]["attach"] is False


if __name__ == "__main__":
    unittest.main()
