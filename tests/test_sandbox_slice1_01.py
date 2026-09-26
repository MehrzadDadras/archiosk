"""MORPHOSIS SLICE 1 - FILE > New Sandbox. Focused end-to-end proof.

The Sandbox is a clean, exploratory Gopilot start: one canonical Composer, a
quiet centre, nothing inherited from a project. Gopilot organizes a raw idea,
advises whether the outside world should be checked, and recommends a landing
- deterministically - without creating anything. The one landing in this slice
is a Planning Study, reached through the EXISTING planning owner, whose own
submit is the explicit act that runs live retrieval; the study carries the
Sandbox as lineage.
"""
from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from services import llm_gateway
from services import sandbox as sb
from tests.test_gopilot_turn_coverage_01 import _App, capture_labels

TOWNHOUSE = ("I created drawings for an interior renovation to a townhouse and want to get a "
             "permit. What should I do?")


class _Outcome:
    def __init__(self, ran=False, parsed=None):
        self.ran, self.parsed, self.skipped_reason = ran, parsed, None if ran else "stub"
        self.raw_text, self.stop_reason, self.provider, self.model = None, None, "test", "test"


NO_MODEL = _Outcome()
MODEL_REPLY = _Outcome(ran=True, parsed={
    "objective": "Get a building permit for an interior renovation of a townhouse you have drawn.",
    "known_facts": ["Drawings exist for an interior renovation", "The building is a townhouse"],
    "unknowns": ["The municipality", "Whether the work needs a permit, and which"],
    "constraints": ["Work cannot start before a permit, if one is required"],
    "next_questions": ["What is the address?"],
    "landing": "create a project now",   # a model's opinion is never adopted as a landing
})


class _Sandbox(_App):
    def setUp(self):
        super().setUp()
        self.boss = self.client("cover_boss")

    def page(self, url="/sandbox"):
        return self.boss.get(url).get_data(as_text=True)

    def ask(self, text=TOWNHOUSE, outcome=NO_MODEL):
        with patch.object(llm_gateway, "call_llm_json", return_value=outcome):
            return self.boss.post("/sandbox/turn", data={"text": text})

    def planning_project(self, name):
        """An ordinary project the planning owner lists (a Document Shop upload is
        a document container, which planning rightly does not offer)."""
        from services.case_workspace import CaseWorkspaceStore
        pid = self.upload(self.boss, name)
        store = CaseWorkspaceStore(str(self.tmp))
        workspace = store.get(pid)
        workspace.container_state = "programmed"
        store.save(workspace)
        return pid

    def sandbox_id(self):
        return re.search(r'name="sandbox_id" value="(\w+)"', self.page()).group(1)

    def governed_state(self):
        """Everything a Sandbox must never create: projects, studies, cases."""
        from services.case_workspace import CaseWorkspaceStore
        from services.ingestion import get_registry

        registry = get_registry(self.app)
        ids = sorted(registry.list_ids())
        store = CaseWorkspaceStore(str(self.tmp))
        studies = sorted(p.name for p in (self.tmp).rglob("*") if "working" in p.name.lower())
        cases = sum(len(store.get(i).cases) for i in ids if store.get(i))
        return ids, studies, cases


class P1_FileNewSandbox(_Sandbox):
    def test_file_new_sandbox_exists_above_new_project_with_its_tooltip(self):
        html = self.page("/projects")
        file_family = html[html.index(">FILE<"):]
        self.assertLess(file_family.index(">New Sandbox<"), file_family.index(">New Project…<"))
        link = re.search(r'<a href="([^"]+)" title="([^"]+)"[^>]*>New Sandbox</a>', html)
        self.assertIsNotNone(link)
        self.assertEqual(link.group(2), "Start a clean Gopilot workspace to explore an idea "
                                        "before deciding what it should become.")
        response = self.boss.get(link.group(1).replace("&amp;", "&"))
        self.assertEqual((response.status_code, response.headers["Location"]), (302, "/sandbox"))
        self.assertEqual(self.boss.get("/sandbox").status_code, 200)

    def test_a_customer_does_not_reach_the_sandbox(self):
        cust = self.client("cover_cust")
        self.assertEqual(cust.get("/sandbox").status_code, 404)
        self.assertEqual(cust.post("/sandbox/turn", data={"text": TOWNHOUSE}).status_code, 404)


class P2_P3_P4_CleanStart(_Sandbox):
    def test_2_one_canonical_composer_in_sandbox_scope(self):
        html = self.page()
        self.assertEqual(html.count('data-ui-ref="chat.composer"'), 1)
        form = html[html.rindex("<form", 0, html.index('data-ui-ref="chat.composer"')):]
        self.assertIn('action="/sandbox/turn"', form[:600])
        self.assertIn('data-go-scope="APPLICATION"', form[:600])
        self.assertIn("What are you working on?", html)
        self.assertIn("Tell Gopilot what you want to accomplish.", html)

    def test_3_no_project_source_or_investigation_clutter(self):
        html = self.page()
        for clutter in ('id="launcher-panel"', 'id="lists-pane"', "thumbnails-list", 'id="toolbox',
                        "to see its context, history and evidence", "workspace-topbar-btn",
                        'data-ui-ref="lists.', 'id="eye-pane"', "data-case-id=",
                        'data-ui-ref="investigation', 'data-ui-ref="finding', 'data-ui-ref="display.'):
            with self.subTest(clutter=clutter):
                self.assertNotIn(clutter, html)
        # The Master menu is the stable shell and stays - but its Investigation
        # commands are grey here: there is nothing to investigate in a Sandbox.
        for command in ("check.investigations", "create.investigation"):
            with self.subTest(command=command):
                self.assertRegex(html, r'class="master-item is-grey" data-command="%s"' % re.escape(command))
        self.assertIn('data-master-shell="identity"', html)      # the anchors remain
        self.assertIn('data-identity-kind="none"', html)

    def test_4_nothing_is_inherited_from_a_project_or_source(self):
        pid = self.upload(self.boss, "Inherited Project")
        self.boss.get("/projects/%s/workspace" % pid)           # a project was just open
        html = self.page()
        self.assertNotIn(pid, html)
        self.assertIn('data-identity-kind="none"', html)
        with capture_labels() as seen:
            self.ask()
        frame = seen[0]["labels"]["frame"]
        self.assertEqual((frame["current_envelope"], frame["context_ids"]), ("APPLICATION", {}))


class P5_P6_P7_OrganizeRecommendCreateNothing(_Sandbox):
    def test_5_townhouse_permit_wording_gets_a_structured_response(self):
        for outcome, source in ((MODEL_REPLY, "model"), (NO_MODEL, "deterministic")):
            with self.subTest(source=source):
                self.boss.get("/sandbox?new=1")
                with patch("routes.portal._project_less_external_ai_allowed", return_value=True):
                    self.ask(outcome=outcome)
                html = self.page()
                self.assertIn('data-ui-ref="sandbox.organized"', html)
                self.assertIn("Your objective", html)
                for title in ("What you have told me", "Not yet known", "Next questions"):
                    self.assertIn(title, html)
                self.assertIn('data-ui-ref="sandbox.external"', html)
                record = sb.SandboxStore(str(self.tmp)).get("cover_boss")
                self.assertEqual(record["turns"][-1]["reply"]["organization"]["source"], source)

    def test_6_it_recommends_a_planning_study_and_creates_nothing(self):
        before = self.governed_state()
        self.ask(outcome=MODEL_REPLY)
        html = self.page()
        self.assertIn("Recommended landing: Planning Study", html)
        self.assertIn(sb.PLANNING_STUDY_WHY, html)
        # A Planning Study lives in a project, so the landing asks which one.
        self.assertIn('data-ui-ref="sandbox.landing.existing-project"', html)
        self.assertIn(">Create New Project<", html)
        self.assertIn(">Continue in Sandbox<", html)
        self.assertEqual(self.governed_state(), before)
        reply = sb.SandboxStore(str(self.tmp)).get("cover_boss")["turns"][-1]["reply"]
        self.assertEqual(reply["landing"]["landing"], "planning_study")   # deterministic, not the model's
        self.assertFalse(reply["canonical"])

    def test_no_landing_without_a_planning_objective(self):
        self.ask(text="I have an idea for a better kitchen layout.")
        html = self.page()
        self.assertNotIn("Recommended landing", html)
        self.assertIn('data-ui-ref="sandbox.no-landing"', html)

    def test_7_continue_in_sandbox_stays_non_canonical(self):
        self.ask()
        before = self.governed_state()
        response = self.boss.post("/sandbox/landing", data={"sandbox_id": self.sandbox_id(), "choice": "continue"})
        self.assertEqual(response.headers["Location"], "/sandbox#sandbox-latest")
        record = sb.SandboxStore(str(self.tmp)).get("cover_boss")
        self.assertEqual(record["decisions"][-1]["choice"], "continue")
        self.assertFalse(record["canonical"])
        self.assertIsNone(record["promoted_to"])
        self.assertEqual(self.governed_state(), before)

    def test_a_landing_cannot_be_forged_for_another_sandbox(self):
        self.ask()
        self.assertEqual(self.boss.post("/sandbox/landing", data={"sandbox_id": "0" * 32,
                                                                  "choice": "new_project"}).status_code, 404)


class P9_NoAutomaticRetrieval(_Sandbox):
    def test_9_no_sandbox_step_runs_live_municipal_retrieval(self):
        with patch("services.planning_live.run_live") as live:
            self.ask()
            sid = self.sandbox_id()
            self.boss.post("/sandbox/landing", data={"sandbox_id": sid, "choice": "continue"})
            pid = self.planning_project("Existing Planning Project")
            start = self.boss.post("/sandbox/landing", data={"sandbox_id": sid, "choice": "existing_project",
                                                             "project_id": pid})
            self.assertEqual(start.headers["Location"], "/planning-zoning?sandbox=%s&project_id=%s" % (sid, pid))
            entry = self.boss.get(start.headers["Location"]).get_data(as_text=True)
            self.boss.post("/sandbox/landing", data={"sandbox_id": sid, "choice": "new_project"})
        self.assertFalse(live.called)
        self.assertIn("Started from your Sandbox", entry)
        self.assertIn('name="sandbox_origin" value="%s"' % sid, entry)


class P10_ExistingRoutesUnchanged(_Sandbox):
    def test_10_new_project_upload_and_planning_are_unchanged(self):
        for url in ("/upload", "/document-shop", "/planning-zoning"):
            with self.subTest(url=url):
                html = self.page(url)
                self.assertEqual(html.count('data-ui-ref="chat.composer"'), 1)
                self.assertNotIn("Started from your Sandbox", html)
                self.assertNotIn('name="sandbox_origin"', html)
                self.assertIn('id="launcher-panel"', html)          # their chrome is untouched
        self.assertIn('href="/upload"', self.page("/projects"))


class ProjectLandingGap(_Sandbox):
    """A Planning Study lives in a project. The landing offers Use Existing Project,
    Create New Project and Continue - never a project-less study, never an
    automatic project."""

    def _new_project_via_the_owner(self, sid, name="Townhouse Permit"):
        import io
        from services.bhive_parser import BHiveParser
        from tests.test_gopilot_turn_coverage_01 import _fake_parse

        with patch.object(BHiveParser, "parse", _fake_parse):
            return self.boss.post("/upload", data={
                "file": (io.BytesIO(b"Interior renovation drawings."), "drawings.txt"),
                "project_name": name, "entry_choice": "client_owner", "source_domain": "UNKNOWN",
                "sandbox_resume": sid}, content_type="multipart/form-data")

    def _finish_briefing(self, pid):
        """The New Project owner's own briefing step, hermetic: the policy answer
        that skips the model call takes the route's own hand-off."""
        with patch("routes.workspace._project_briefing_ai_status", return_value=("denied", None)):
            prepared = self.boss.get("/projects/%s/workspace/briefing/preparing" % pid)
            if prepared.status_code == 302:
                return prepared
            return self.boss.post("/projects/%s/workspace/briefing/generate" % pid)

    def test_1_a_brand_new_sandbox_reaches_a_planning_study_through_create_new_project(self):
        from services.ingestion import get_registry

        self.ask()
        html = self.page()
        self.assertIn("You have no projects yet.", html)          # truly pre-project
        sid = self.sandbox_id()
        start = self.boss.post("/sandbox/landing", data={"sandbox_id": sid, "choice": "new_project"})
        self.assertEqual(start.headers["Location"], "/upload?sandbox=%s" % sid)
        form = self.boss.get(start.headers["Location"]).get_data(as_text=True)
        self.assertIn('name="sandbox_resume" value="%s"' % sid, form)
        self.assertIn("Creating this project for your Sandbox", form)
        self.assertEqual(list(get_registry(self.app).list_ids()), [])   # nothing created yet

        created = self._new_project_via_the_owner(sid)
        ids = list(get_registry(self.app).list_ids())
        self.assertEqual(len(ids), 1)                             # the owner created exactly one
        self.assertIn("/workspace/briefing/preparing", created.headers["Location"])   # owner's own next step
        handed = self._finish_briefing(ids[0])
        self.assertEqual(handed.headers["Location"],
                         "/planning-zoning?sandbox=%s&project_id=%s" % (sid, ids[0]))
        entry = self.boss.get(handed.headers["Location"]).get_data(as_text=True)
        self.assertIn('name="sandbox_origin" value="%s"' % sid, entry)
        self.assertRegex(entry, r'<option value="%s" selected>' % ids[0])
        # The resume is spent: the same project later goes to its Overview as always.
        self.assertIn("view=overview", self._finish_briefing(ids[0]).headers["Location"])

        # 5 - the person submits the EXISTING Planning & Zoning form: the one explicit
        # act that runs live retrieval, and the study carries the Sandbox lineage.
        from services import planning_live
        from services.planning_studies import WorkingResults
        from tests.test_planning_map_export import specimen

        self.app.config["PLANNING_ZONING_LIVE_ENABLED"] = True
        snapshot = {"outcome": planning_live.OUTCOME_OK, "study_snapshot": specimen()}
        with patch("services.planning_live.run_live", return_value=snapshot) as live:
            study = self.boss.post("/planning-zoning/analyze", data={
                "composer": "1", "project_id": ids[0], "address": "123 Synthetic Avenue",
                "sandbox_origin": sid})
        self.assertEqual(live.call_count, 1)
        run_id = study.headers["Location"].rstrip("/").split("/")[-1]
        result = WorkingResults(str(self.tmp)).get(run_id, ids[0], "cover_boss")
        self.assertEqual(result["workspace_context"]["origin"]["sandbox_id"], sid)
        self.assertEqual(sb.SandboxStore(str(self.tmp)).get("cover_boss")["promoted_to"]["project_id"], ids[0])

    def test_an_unrelated_new_project_is_never_pulled_into_a_sandbox(self):
        self.ask()
        self.boss.post("/sandbox/landing", data={"sandbox_id": self.sandbox_id(), "choice": "new_project"})
        created = self._new_project_via_the_owner("", name="Unrelated")   # no marker on the form
        pid = created.headers["Location"].split("/projects/")[1].split("/")[0]
        self.assertIn("view=overview", self._finish_briefing(pid).headers["Location"])

    def test_2_an_existing_project_user_can_use_existing_project(self):
        pid = self.planning_project("Harbour Townhouse")
        self.ask()
        html = self.page()
        self.assertIn('<option value="%s">' % pid, html)
        start = self.boss.post("/sandbox/landing", data={"sandbox_id": self.sandbox_id(),
                                                         "choice": "existing_project", "project_id": pid})
        entry = self.boss.get(start.headers["Location"]).get_data(as_text=True)
        self.assertIn("Started from your Sandbox", entry)
        self.assertRegex(entry, r'<option value="%s" selected>' % pid)

    def test_3_inaccessible_projects_are_absent_and_refused(self):
        from models import User, db
        from services.case_workspace import CaseWorkspaceStore
        from werkzeug.security import generate_password_hash

        harbour = self.upload(self.boss, "Harbour Townhouse")
        zeta = self.upload(self.boss, "Zeta Tower")
        store = CaseWorkspaceStore(str(self.tmp))
        for pid in (harbour, zeta):
            workspace = store.get(pid)
            workspace.container_state = "programmed"
            store.save(workspace)
        workspace = store.get(harbour)
        workspace.access_allow_list = ["sb_reader"]
        store.save(workspace)
        reader = User(username="sb_reader", role="read_only")
        reader.password_hash = generate_password_hash(self.PW)
        db.session.add(reader)
        db.session.commit()
        self.boss = self.client("sb_reader")
        self.ask()
        html = self.page()
        self.assertIn('<option value="%s">' % harbour, html)
        self.assertNotIn(zeta, html)
        self.assertNotIn("Zeta Tower", html)
        self.assertNotIn(">Create New Project<", html)           # the owner is admin-only
        refused = self.boss.post("/sandbox/landing", data={"sandbox_id": self.sandbox_id(),
                                                           "choice": "existing_project", "project_id": zeta})
        self.assertEqual(refused.status_code, 404)
        self.assertEqual(self.boss.post("/sandbox/landing", data={"sandbox_id": self.sandbox_id(),
                                                                  "choice": "new_project"}).status_code, 403)

    def test_6_no_duplicate_project_or_planning_owner(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        source = ((root / "routes" / "sandbox.py").read_text(encoding="utf-8")
                  + (root / "services" / "sandbox.py").read_text(encoding="utf-8"))
        for owner_call in ("ingest_upload(", "ingest_folder_upload(", "get_or_create(", "create_case(",
                           "WorkingResults(", ".put(", "planning_composer", "run_live(", "initialize("):
            with self.subTest(owner_call=owner_call):
                self.assertNotIn(owner_call, source)


class ProjectPickerLabels(_Sandbox):
    """The planning owner's project list labels each project by the PROJECT
    record's governed name ("Name · CODE", the Context rail's convention) - never a
    source filename - and the Sandbox inherits the same list unchanged."""

    @staticmethod
    def options(html, select_id):
        block = html[html.index('id="%s"' % select_id):]
        block = block[:block.index("</select>")]
        return [(v, " ".join(label.split())) for v, label in
                re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', block)]

    def planning_options(self):
        return [o for o in self.options(self.page("/planning-zoning"), "planning-project") if o[0]]

    def test_1_to_3_planning_and_sandbox_pickers_show_governed_names_and_submit_ids(self):
        from services.case_workspace import CaseWorkspaceStore

        pid = self.planning_project("Townhouse Renovation")
        workspace = CaseWorkspaceStore(str(self.tmp)).get(pid)
        expected = "Townhouse Renovation · %s" % workspace.project_code if workspace.project_code \
            else "Townhouse Renovation"
        planning = self.planning_options()
        self.assertEqual(planning, [(pid, expected)])                    # 1 name, 3 id as value
        self.assertNotIn("a.jpg", self.page("/planning-zoning"))          # never the source filename
        self.ask()
        self.assertEqual(self.options(self.page(), "sandbox-project"), planning)   # 2 same list

    def test_4_inaccessible_projects_are_absent_from_both_pickers(self):
        from models import User, db
        from services.case_workspace import CaseWorkspaceStore
        from werkzeug.security import generate_password_hash

        mine = self.planning_project("Harbour Townhouse")
        hidden = self.planning_project("Zeta Tower")
        store = CaseWorkspaceStore(str(self.tmp))
        workspace = store.get(mine)
        workspace.access_allow_list = ["label_reader"]
        store.save(workspace)
        reader = User(username="label_reader", role="read_only")
        reader.password_hash = generate_password_hash(self.PW)
        db.session.add(reader)
        db.session.commit()
        self.boss = self.client("label_reader")
        planning = self.planning_options()
        self.assertEqual([o[0] for o in planning], [mine])
        self.assertNotIn("Zeta Tower", self.page("/planning-zoning"))
        self.assertNotIn(hidden, self.page("/planning-zoning"))
        self.ask()
        self.assertEqual(self.options(self.page(), "sandbox-project"), planning)

    def test_5_duplicate_names_stay_distinguishable_by_project_code(self):
        from services.case_workspace import CaseWorkspaceStore

        # The project owner refuses a duplicate name at creation, so a duplicate
        # can only exist in older data: make one directly on the record.
        first = self.planning_project("Townhouse Renovation")
        second = self.planning_project("Townhouse Renovation Two")
        store = CaseWorkspaceStore(str(self.tmp))
        workspace = store.get(second)
        workspace.display_title = "Townhouse Renovation"
        store.save(workspace)
        labels = dict(self.planning_options())
        self.assertEqual(set(labels), {first, second})
        self.assertNotEqual(labels[first], labels[second])
        for label in labels.values():
            self.assertTrue(label.startswith("Townhouse Renovation · "), label)


def _png_data_url(width=24, height=16, colour=(40, 160, 120)):
    import base64
    import io as _io
    from PIL import Image

    buf = _io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


class SandboxMediaInput(_Sandbox):
    """The Sandbox Composer takes an image through the canonical Composer's own
    attachment path: one turn carries text + image to Gopilot; the image is
    provisional context, identity-only, and never becomes a governed object."""

    def send_with_image(self, text, data_url, *, allowed=True, outcome=None):
        calls = []

        def spy(**kwargs):
            calls.append(kwargs)
            return outcome or MODEL_REPLY

        with patch("routes.portal._project_less_external_ai_allowed", return_value=allowed), \
                patch.object(llm_gateway, "call_llm_json", side_effect=spy):
            response = self.boss.post("/sandbox/turn", data={"text": text, "image_data_url": data_url})
        return response, calls

    def last_reply(self):
        return sb.SandboxStore(str(self.tmp)).get("cover_boss")["turns"][-1]["reply"]

    def test_the_sandbox_composer_offers_the_shared_attach_control_with_the_device_chooser(self):
        html = self.page()
        self.assertIn('data-ui-ref="chat.composer.attach"', html)
        self.assertIn('id="dock-composer-image-data"', html)
        tag = re.search(r'<input type="file" id="dock-composer-image"[^>]*>', html).group(0)
        self.assertIn('accept="image/*"', tag)
        self.assertNotIn("capture=", tag)            # the phone offers camera, library AND files

    def test_other_scopes_keep_their_rear_camera_default_unchanged(self):
        pid = self.upload(self.boss, "Photo Project")
        tag = re.search(r'<input type="file" id="dock-composer-image"[^>]*>',
                        self.page("/projects/%s/workspace" % pid)).group(0)
        self.assertIn('capture="environment"', tag)

    def test_one_turn_carries_text_and_image_to_gopilot(self):
        before = self.governed_state()
        data_url = _png_data_url()
        response, calls = self.send_with_image("What is wrong with this interface?", data_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(calls), 1)                                   # one turn, one model call
        self.assertEqual(calls[0]["image_media_type"], "image/png")
        self.assertEqual(calls[0]["image_base64"], data_url.split(",", 1)[1])
        self.assertIn("What is wrong with this interface?", calls[0]["user_prompt"])
        attachment = self.last_reply()["attachments"][0]
        self.assertEqual((attachment["media_type"], attachment["analysed"], attachment["status"],
                          attachment["canonical"]), ("image/png", True, "provisional", False))
        self.assertEqual(len(attachment["sha256"]), 64)
        html = self.page()
        self.assertIn('data-ui-ref="sandbox.attachment"', html)
        self.assertIn("read by Gopilot", html)
        # Nothing canonical, and the bytes are kept nowhere.
        self.assertEqual(self.governed_state(), before)
        payload = data_url.split(",", 1)[1][:40]
        for path in self.tmp.rglob("*"):
            if path.is_file():
                with self.subTest(path=path.name):
                    self.assertNotIn(payload, path.read_text(encoding="utf-8", errors="ignore"))

    def test_an_image_alone_is_a_complete_turn(self):
        response, calls = self.send_with_image("", _png_data_url())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(calls), 1)
        self.assertEqual(sb.SandboxStore(str(self.tmp)).get("cover_boss")["turns"][-1]["text"],
                         "What should I make of this?")

    def test_policy_denial_sends_nothing_and_says_so(self):
        response, calls = self.send_with_image("Help me organize this idea.", _png_data_url(), allowed=False)
        self.assertEqual(calls, [])                                       # no model, no image egress
        reply = self.last_reply()
        self.assertEqual(reply["attachments"][0]["status"], "not accepted")
        self.assertEqual(reply["organization"]["source"], "deterministic")

    def test_validation_is_the_shared_validation(self):
        svg = "data:image/svg+xml;base64,PHN2Zy8+"
        response, calls = self.send_with_image("Is this safe?", svg)
        self.assertTrue(all(c.get("image_base64") is None for c in calls))
        self.assertEqual(self.last_reply()["attachments"][0]["status"], "not accepted")
        with patch("services.composer_image.MAX_IMAGE_BYTES", 10):
            self.send_with_image("Too big?", _png_data_url(64, 64))
        self.assertEqual(self.last_reply()["attachments"][0]["status"], "not accepted")

    def test_attachment_identity_travels_only_with_an_accepted_landing(self):
        self.send_with_image("I want a permit for this townhouse renovation.", _png_data_url())
        record = sb.SandboxStore(str(self.tmp)).get("cover_boss")
        origin = sb.lineage(record)
        self.assertEqual(len(origin["attachments"]), 1)
        self.assertEqual(origin["attachments"][0]["turn"], 0)
        self.assertNotIn("image_base64", str(origin))


class SandboxMediaInBrowser(_Sandbox):
    """Real Chromium drives the canonical Composer's OWN scripts (go_composer.js
    paste, composer_attach.js pick/preview/review/remove) on the real Sandbox page."""

    def browser_page(self, playwright, width, height):
        from pathlib import Path as _P

        html = self.page()
        root = _P(__file__).resolve().parents[1]
        html = re.sub(r'<link rel="stylesheet" href="/static/css/([a-z_]+\.css)[^"]*">',
                      lambda m: "<style>" + (root / "static" / "css" / m.group(1)).read_text(encoding="utf-8")
                      + "</style>", html)
        html = re.sub(r"<script[^>]*src=[^>]*></script>", "", html)
        scripts = "".join("<script>" + (root / "static" / "js" / name).read_text(encoding="utf-8") + "</script>"
                          for name in ("composer_attach.js", "developer_composer_input.js", "go_composer.js"))
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content(html.replace("</body>", scripts + "</body>"), wait_until="load")
        return browser, page

    def accept_review(self, page):
        page.wait_for_timeout(700)
        if page.evaluate("(() => { const r = document.getElementById('dock-capture-review'); return !!r && !r.hidden; })()"):
            page.click("#dock-capture-review-use")
            page.wait_for_timeout(400)

    def state(self, page):
        return page.evaluate("""() => ({
            imageLen: (document.getElementById('dock-composer-image-data').value || '').length,
            chip: !document.getElementById('dock-composer-image-chip').hidden,
            payload: (() => { const fd = new FormData(document.querySelector('form[data-ui-ref="chat.composer"]'));
                              return {text: fd.get('text'), image: (fd.get('image_data_url') || '').slice(0, 22)}; })()})""")

    def test_desktop_paste_preview_text_remove_replace_one_turn(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser, page = self.browser_page(pw, 1440, 900)
            paste = """async (colour) => {
                const c = document.createElement('canvas'); c.width = 120; c.height = 80;
                const g = c.getContext('2d'); g.fillStyle = colour; g.fillRect(0, 0, 120, 80);
                const blob = await new Promise(r => c.toBlob(r, 'image/png'));
                const dt = new DataTransfer(); dt.items.add(new File([blob], 'screenshot.png', {type: 'image/png'}));
                document.getElementById('dock-composer-input').dispatchEvent(
                    new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
            }"""
            page.evaluate(paste, "#3a7")
            self.accept_review(page)
            pasted = self.state(page)
            self.assertTrue(pasted["chip"] and pasted["imageLen"] > 100)          # preview before send
            page.fill("#dock-composer-input", "What is wrong with this interface?")
            page.click("#dock-composer-image-clear")                             # remove before send
            removed = self.state(page)
            self.assertFalse(removed["chip"])
            self.assertEqual(removed["imageLen"], 0)
            page.evaluate(paste, "#a33")                                        # replace
            self.accept_review(page)
            final = self.state(page)
            browser.close()
        self.assertEqual(final["payload"]["text"], "What is wrong with this interface?")
        self.assertEqual(final["payload"]["image"], "data:image/png;base64,")      # text + image, one form

    def test_upload_and_phone_viewport_use_the_same_attach_control(self):
        import base64
        from playwright.sync_api import sync_playwright

        png = base64.b64decode(_png_data_url().split(",", 1)[1])
        for width, height in ((1440, 900), (390, 844)):
            with self.subTest(viewport=width), sync_playwright() as pw:
                browser, page = self.browser_page(pw, width, height)
                page.set_input_files("#dock-composer-image", files=[{"name": "site.png", "mimeType": "image/png",
                                                                     "buffer": png}])
                self.accept_review(page)
                page.fill("#dock-composer-input", "What should I be looking at here?")
                picked = self.state(page)
                attach_visible = page.evaluate(
                    "(() => { const r = document.querySelector('[data-ui-ref=\"chat.composer.attach\"]').getBoundingClientRect();"
                    " return r.width > 0 && r.height > 0 && r.right <= innerWidth + 1; })()")
                overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                browser.close()
            self.assertTrue(picked["chip"])
            self.assertEqual(picked["payload"]["image"], "data:image/png;base64,")
            self.assertEqual(picked["payload"]["text"], "What should I be looking at here?")
            self.assertTrue(attach_visible)
            self.assertFalse(overflow)


# -- 8: Start Planning Study uses the existing planning owner, with lineage --------
from tests.test_planning_word_export_405 import setup_export, sign_in  # noqa: E402,F401


def test_8_start_planning_study_uses_the_planning_owner_and_keeps_lineage(setup_export):
    from services import planning_live
    from services import planning_studies as studies

    app, store, result, _ = setup_export
    client = sign_in(app)
    with patch.object(llm_gateway, "call_llm_json", return_value=NO_MODEL):
        client.post("/sandbox/turn", data={"text": TOWNHOUSE})
    record = sb.SandboxStore(store.store_path).get("export-planner")
    entry = client.get("/planning-zoning?sandbox=%s&project_id=p" % record["id"]).get_data(as_text=True)
    assert 'name="sandbox_origin" value="%s"' % record["id"] in entry

    snapshot = {"outcome": planning_live.OUTCOME_OK, "study_snapshot": result}
    with patch("services.planning_live.run_live", return_value=snapshot) as live:
        created = client.post("/planning-zoning/analyze", data={
            "composer": "1", "project_id": "p", "address": "123 Synthetic Avenue",
            "sandbox_origin": record["id"]})
    assert live.call_count == 1                       # the user's explicit submit, and only it
    assert created.status_code == 302
    run_id = created.headers["Location"].rstrip("/").split("/")[-1]
    study = studies.WorkingResults(store.store_path).get(run_id, "p", "export-planner")
    origin = study["workspace_context"]["origin"]
    assert origin["kind"] == "sandbox" and origin["sandbox_id"] == record["id"]
    assert origin["canonical"] is False and origin["turn_count"] == 1
    promoted = sb.SandboxStore(store.store_path).get("export-planner")["promoted_to"]
    assert promoted["landing"] == "planning_study" and promoted["run_id"] == run_id


if __name__ == "__main__":
    unittest.main()
