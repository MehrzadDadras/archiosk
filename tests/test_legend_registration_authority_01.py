"""CLAUDE-LEGEND-REGISTRATION-AUTHORITY-CONTAINMENT-01.

READ ACCESS IS NOT REGISTRATION AUTHORITY.

`governance/current/legend-of-understanding-and-craft-workshop.md` §8 ratifies
that the indexing act is separate from the authority of the meaning, and §7 of
that same record states plainly that nothing enforced it: both decision routes
were `@login_required` only, and `scope_kind` was taken from the submitted form.
A Document Shop customer who owned a container could therefore turn GO's
proposal into REGISTERED, REUSABLE meaning at project or discipline scope -
authority conferred by owning the sheet a mark was found on.

This file pins the containment and, just as deliberately, pins what it did NOT
change. Every non-customer account keeps every scope it could already use.
Whether that is right is the open Product Owner question; a test asserting an
answer to it here would manufacture the authority the containment refused to
invent.

Three properties carry the weight:

`test_owning_the_source_does_not_authorize_registration` - the actual defect,
stated as the product sentence rather than as a status code.

`test_an_unknown_scope_is_refused_rather_than_stored_verbatim` - the second
half. `normalize_open_world_value` stores an unrecognised scope UNCHANGED,
which is right for a vocabulary a human is describing and wrong for a value
arriving from a form and used as an authority boundary.

`test_every_post_route_that_mutates_legend_state_passes_the_gate` - the
carry-through. Fixing the two known routes is not the correction if a third
can be added ungated tomorrow, so the guard is a scan, not a list.
"""
from __future__ import annotations

import ast
import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from models import ROLE_ADMIN, ROLE_CUSTOMER, ROLE_READ_ONLY
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX,
    KNOWN_LEGEND_SCOPES,
    LEGEND_KIND_SECTION_REFERENCE,
    LEGEND_STATUS_CONFIRMED,
    LEGEND_STATUS_PROPOSED,
    CaseWorkspaceStore,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKSPACE_ROUTES = _REPO_ROOT / "routes" / "workspace.py"
_AUTH = _REPO_ROOT / "services" / "auth.py"

#: Every service call that turns a proposal into a recorded/reusable decision.
#: Read from `services/legend_of_understanding.py` and `case_workspace.py` by
#: hand once, and guarded below against a route reaching one of them ungated.
_LEGEND_MUTATIONS = (
    "decide_proposition",
    "confirm_family",
    "apply_family_decision",
    "inherit_proposition",
    "inherit_group_understanding",
    "break_inheritance",
    "decide_legend_item",
    "propose_legend_item",
    "register_family",
    "propose_target",
)

_GATE = "_require_legend_decision_authority"


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


def _file(content: bytes, name: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=name)


class _LegendCase(unittest.TestCase):
    """One container, one sheet, one standalone mark and one family of two.

    Built twice by the subclasses - once as a Document Shop container owned by a
    customer, once as an ordinary Project - so the two operating lines are
    measured against the SAME legend state rather than against two fixtures that
    could quietly differ.
    """

    OWNER = "owner"
    ENVIRONMENT = CLIENT_OWNER
    CONTAINER_STATE = None
    FAMILY_ID = "fam-authority-01"

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_legend_auth_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    _file(b"a sheet", "sheet.txt"), self.app,
                    owner=self.OWNER, operating_environment=self.ENVIRONMENT,
                    container_state=self.CONTAINER_STATE,
                    project_name="Legend Authority Fixture")
        self.project_id = self.document.project_id
        self.source = self.store.get(self.project_id).sources[0]

        self.snapshot = self.tmp / "snap.png"
        self.snapshot.write_bytes(b"\x89PNG\r\n\x1a\n")

        workspace = self.store.get(self.project_id)
        registered = self.store.register_drawing_sheet_structure(
            workspace, self.source["id"],
            [{"index": 0, "label": "Sheet", "width": 100.0, "height": 100.0,
              "source_rotation": 0, "metadata": {}}], actor="test")
        self.unit = registered["structural_unit_ids"][0]

        self.mark_id = self._propose(0)["id"]
        self.representative_id = self._propose(1, family_role="representative")["id"]
        self._propose(2, family_role="instance")

    def _propose(self, index, family_role=None):
        workspace = self.store.get(self.project_id)
        return self.store.propose_legend_item(
            workspace, source_id=self.source["id"],
            page_structural_unit_id=self.unit,
            region={"x": float(index), "y": 1.0, "width": 5.0, "height": 5.0},
            proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
            proposed_meaning="Section reference.",
            interpretation_method="test", actor="GO",
            snapshot_path=str(self.snapshot),
            confidence=0.5,
            family_id=self.FAMILY_ID if family_role else None,
            family_role=family_role, nearby_label="A")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers -------------------------------------------------------------

    def _client(self, username=None, role=ROLE_READ_ONLY, user_id=1):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = user_id
            session["username"] = username or self.OWNER
            session["role"] = role
        return client

    def _item_url(self, legend_item_id=None, project_id=None):
        return ("/projects/%s/workspace/understanding/%s/decide"
                % (project_id or self.project_id, legend_item_id or self.mark_id))

    def _family_url(self, project_id=None):
        return ("/projects/%s/workspace/understanding/family/%s/decide"
                % (project_id or self.project_id, self.FAMILY_ID))

    def _bench_url(self):
        return ("/projects/%s/workspace/sources/%s/understanding"
                % (self.project_id, self.source["id"]))

    def _item(self, legend_item_id=None):
        wanted = legend_item_id or self.mark_id
        return next(i for i in self.store.get(self.project_id).legend_items
                    if i["id"] == wanted)

    def _legend_log_events(self):
        from services.governance import GovernanceLog

        log = GovernanceLog(self.app.config["REGISTRY_STORE_PATH"])
        return [e.event_type for e in log.read(self.project_id)
                if "legend" in (e.event_type or "")]

    def assertUntouched(self, snapshot, legend_item_id=None):
        """No decision, no status move, no history growth. The whole point of a
        refusal is that the record is exactly where it was."""
        item = self._item(legend_item_id)
        self.assertEqual(item["status"], snapshot["status"])
        self.assertEqual(len(item.get("decisions") or []), snapshot["decisions"])
        self.assertEqual(item.get("scope_kind"), snapshot["scope_kind"])

    def snapshot_of(self, legend_item_id=None):
        item = self._item(legend_item_id)
        return {"status": item["status"],
                "decisions": len(item.get("decisions") or []),
                "scope_kind": item.get("scope_kind")}


class CustomerContainment(_LegendCase):
    """A Document Shop customer, on a container they genuinely own."""

    OWNER = "cust"
    ENVIRONMENT = None
    CONTAINER_STATE = CONTAINER_STATE_BLACK_BOX

    def _customer(self):
        return self._client(username="cust", role=ROLE_CUSTOMER, user_id=7)

    # -- the defect, stated as the product sentence --------------------------

    def test_owning_the_source_does_not_authorize_registration(self):
        """The container is theirs, the bench opens, the decision is refused."""
        client = self._customer()
        self.assertEqual(client.get(self._bench_url()).status_code, 200,
                         "read access is unchanged and must stay unchanged")
        before = self.snapshot_of()
        self.assertEqual(
            client.post(self._item_url(), data={"action": "confirmed"}).status_code,
            403)
        self.assertUntouched(before)

    def test_a_customer_cannot_record_a_family_decision_either(self):
        client = self._customer()
        before = self.snapshot_of(self.representative_id)
        self.assertEqual(
            client.post(self._family_url(), data={"action": "confirmed"}).status_code,
            403)
        self.assertUntouched(before, self.representative_id)

    def test_a_customer_cannot_reach_a_wider_scope_by_submitting_one(self):
        client = self._customer()
        for scope in ("source", "discipline", "project"):
            with self.subTest(scope=scope):
                before = self.snapshot_of()
                response = client.post(
                    self._item_url(),
                    data={"action": "confirmed", "scope_kind": scope})
                self.assertEqual(response.status_code, 403)
                self.assertUntouched(before)

    def test_every_decision_verb_is_refused_not_only_confirm(self):
        """Unknown and Later look harmless and are still registrations."""
        client = self._customer()
        for action in ("confirmed", "overridden", "unknown", "informative",
                       "deferred"):
            with self.subTest(action=action):
                before = self.snapshot_of()
                response = client.post(
                    self._item_url(),
                    data={"action": action, "meaning": "a stair section"})
                self.assertEqual(response.status_code, 403)
                self.assertUntouched(before)

    def test_a_refused_request_writes_no_governance_entry(self):
        """A refusal is not an event in the project's own history."""
        client = self._customer()
        client.post(self._item_url(), data={"action": "confirmed"})
        self.assertEqual(self._legend_log_events(), [])

    # -- the refusal keeps them in their own operating line -------------------

    def test_the_refusal_leaves_the_customer_inside_the_document_shop(self):
        response = self._customer().post(self._item_url(),
                                         data={"action": "confirmed"})
        self.assertEqual(response.status_code, 403)
        body = response.get_data(as_text=True)
        self.assertIn("/document-shop/jobs", body)
        self.assertNotIn("Back to Projects", body)
        self.assertNotIn('href="/projects"', body)

    def test_it_is_a_refusal_not_a_redirect_into_somewhere_else(self):
        """403, deliberately. Nothing here is a wrong turn to be steered out
        of - the Projects-directory redirect exists for surfaces a customer
        merely wandered onto, and this is not one."""
        response = self._customer().post(self._item_url(),
                                         data={"action": "confirmed"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(response.status_code, (301, 302, 303, 307, 308))

    # -- read access is untouched --------------------------------------------

    def test_the_bench_still_shows_the_evidence_and_gos_reading(self):
        body = self._customer().get(self._bench_url()).get_data(as_text=True)
        self.assertIn("Section reference.", body)
        self.assertIn("legend-snapshot", body)

    def test_the_crop_is_still_served(self):
        response = self._customer().get(
            "/projects/%s/workspace/understanding/%s/snapshot"
            % (self.project_id, self.mark_id))
        self.assertEqual(response.status_code, 200)

    def test_the_bench_offers_no_control_the_route_would_refuse(self):
        """Grey the control AND gate the route - the two-sided shape
        `user_can_upload_to_storage` already documents. The button is not the
        enforcement; offering one that always fails is its own defect."""
        body = self._customer().get(self._bench_url()).get_data(as_text=True)
        self.assertIn('data-ui-ref="drawing-understanding.decision.not-yours"', body)
        for ref in ("confirm", "correct", "unknown", "later"):
            with self.subTest(control=ref):
                self.assertNotIn(
                    'data-ui-ref="drawing-understanding.decision.%s"' % ref, body)

    # -- cross-tenant -------------------------------------------------------

    def test_another_owners_container_is_still_an_indistinguishable_404(self):
        """The project boundary runs FIRST and is unchanged: a foreign
        container must not answer 403, which would confirm it exists."""
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                other = ingest_upload(
                    _file(b"not theirs", "other.txt"), self.app,
                    owner="someone-else", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Another Job")
        response = self._customer().post(
            self._item_url(project_id=other.project_id), data={"action": "confirmed"})
        self.assertEqual(response.status_code, 404)


class ProjectReviewersAreUnaffected(_LegendCase):
    """The half that must NOT move. Containment that quietly reduces someone
    else's authority is the same defect facing the other way."""

    def test_a_read_only_reviewer_still_records_a_decision(self):
        response = self._client().post(self._item_url(),
                                       data={"action": "confirmed"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._item()["status"], LEGEND_STATUS_CONFIRMED)

    def test_an_admin_still_records_a_decision(self):
        response = self._client(username="root", role=ROLE_ADMIN, user_id=13).post(
            self._item_url(), data={"action": "confirmed"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._item()["status"], LEGEND_STATUS_CONFIRMED)

    def test_every_known_scope_is_still_accepted_and_stored_as_submitted(self):
        """Including `project` and `discipline`. This tranche contained the
        customer; it did not answer who SHOULD hold project-wide registration
        authority, and pretending otherwise here would invent that answer."""
        for scope in KNOWN_LEGEND_SCOPES:
            with self.subTest(scope=scope):
                response = self._client().post(
                    self._item_url(),
                    data={"action": "confirmed", "scope_kind": scope})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self._item()["scope_kind"], scope)

    def test_the_family_route_still_works_and_keeps_its_source_default(self):
        response = self._client().post(self._family_url(),
                                       data={"action": "confirmed"})
        self.assertEqual(response.status_code, 302)
        item = self._item(self.representative_id)
        self.assertEqual(item["status"], LEGEND_STATUS_CONFIRMED)
        self.assertEqual(item["scope_kind"], "source",
                         "the family default is deliberately left where it was")

    def test_the_bench_still_offers_the_controls(self):
        body = self._client().get(self._bench_url()).get_data(as_text=True)
        self.assertIn('data-ui-ref="drawing-understanding.decision.confirm"', body)
        self.assertNotIn('data-ui-ref="drawing-understanding.decision.not-yours"', body)


class ScopeIsNotAuthoritativeBecauseItWasSubmitted(_LegendCase):
    """`normalize_open_world_value` returns an unrecognised value VERBATIM -
    correct for an open-world vocabulary, wrong for an authority boundary
    arriving from a form."""

    def test_an_unknown_scope_is_refused_rather_than_stored_verbatim(self):
        before = self.snapshot_of()
        response = self._client().post(
            self._item_url(),
            data={"action": "confirmed", "scope_kind": "everywhere"})
        self.assertEqual(response.status_code, 400)
        self.assertUntouched(before)
        self.assertNotEqual(self._item().get("scope_kind"), "everywhere")

    def test_the_family_route_refuses_an_unknown_scope_too(self):
        before = self.snapshot_of(self.representative_id)
        response = self._client().post(
            self._family_url(),
            data={"action": "confirmed", "scope_kind": "everywhere"})
        self.assertEqual(response.status_code, 400)
        self.assertUntouched(before, self.representative_id)

    def test_a_refused_scope_is_not_silently_narrowed_to_a_permitted_one(self):
        """Narrowing would record a decision nobody made and hide the
        unauthorised request inside a successful-looking one."""
        response = self._client().post(
            self._item_url(),
            data={"action": "confirmed", "scope_kind": "GLOBAL"})
        self.assertEqual(response.status_code, 400)
        item = self._item()
        self.assertEqual(item["status"], LEGEND_STATUS_PROPOSED)
        self.assertEqual(item.get("decisions") or [], [])

    def test_a_bare_click_with_no_scope_still_works(self):
        """The whole As-Read matrix rests on one-click decisions posting no
        scope at all; the gate must not have made scope mandatory."""
        response = self._client().post(self._item_url(),
                                       data={"action": "confirmed"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._item()["scope_kind"], "instance")


class CarryThrough(unittest.TestCase):
    """WHERE ELSE CAN A CALLER TURN A PROPOSAL INTO REGISTERED MEANING?

    Fixing the two known routes is not the correction if a third can appear
    ungated tomorrow, so this is a scan rather than a list of two.
    """

    def _route_functions(self):
        tree = ast.parse(_WORKSPACE_ROUTES.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            decorated = any(
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Attribute)
                and d.func.attr == "route"
                for d in node.decorator_list)
            if decorated:
                yield node

    @staticmethod
    def _called_names(node):
        names = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name):
                    names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    names.add(func.attr)
        return names

    def test_every_post_route_that_mutates_legend_state_passes_the_gate(self):
        gated, ungated = [], []
        for node in self._route_functions():
            called = self._called_names(node)
            if not called & set(_LEGEND_MUTATIONS):
                continue
            (gated if _GATE in called else ungated).append(node.name)
        self.assertEqual(ungated, [],
                         "route reaches a legend mutation without the gate: %s" % ungated)
        self.assertGreaterEqual(len(gated), 2,
                                "the two known decision routes must still be found")

    def test_no_other_route_module_reaches_a_legend_mutation(self):
        """A second blueprint growing its own decision surface would bypass a
        gate that lives in this one."""
        for path in sorted((_REPO_ROOT / "routes").glob("*.py")):
            if path.name == "workspace.py":
                continue
            source = path.read_text(encoding="utf-8")
            for mutation in _LEGEND_MUTATIONS:
                with self.subTest(module=path.name, mutation=mutation):
                    self.assertNotIn(mutation, source)

    def test_the_gate_is_defined_once_and_asks_the_authority_helper(self):
        source = _WORKSPACE_ROUTES.read_text(encoding="utf-8")
        self.assertEqual(source.count("\ndef %s(" % _GATE), 1)
        window = source[source.index("def %s(" % _GATE):]
        window = window[:window.index("@workspace_bp.route")]
        self.assertIn("user_can_record_registered_understanding", window)
        self.assertIn("KNOWN_LEGEND_SCOPES", window)

    def test_the_authority_question_is_owned_in_one_place(self):
        """No route and no template re-derives a role - the rule the customer
        tranche established and this one had to extend rather than restate."""
        auth = _AUTH.read_text(encoding="utf-8")
        self.assertEqual(auth.count("\ndef user_can_record_registered_understanding("), 1)
        routes = _WORKSPACE_ROUTES.read_text(encoding="utf-8")
        window = routes[routes.index("def %s(" % _GATE):]
        window = window[:window.index("@workspace_bp.route")]
        self.assertNotIn("ROLE_CUSTOMER", window)
        self.assertNotIn('"customer"', window)

    def test_no_permissions_framework_was_introduced(self):
        services = {p.name for p in (_REPO_ROOT / "services").glob("*.py")}
        for invented in ("rbac.py", "permissions.py", "authorization.py",
                         "role_registry.py", "legend_authority.py"):
            with self.subTest(module=invented):
                self.assertNotIn(invented, services)

    def test_the_composer_card_cannot_offer_a_control_by_default(self):
        """`_macros.html` is imported WITHOUT context, so the macro cannot read
        the authority answer - it is passed in, with no default, precisely so a
        future call site cannot forget it silently."""
        macros = (_REPO_ROOT / "templates" / "_macros.html").read_text(encoding="utf-8")
        signature = "{% macro as_read_decision_card(project_id, message, disposition, available, can_decide) %}"
        self.assertIn(signature, macros)
        self.assertNotIn("can_decide=", macros, "a default would defeat the point")
        case_workspace = (_REPO_ROOT / "templates" / "case_workspace.html").read_text(
            encoding="utf-8")
        self.assertEqual(
            case_workspace.count("can_record_registered_understanding"), 2,
            "both call sites must pass the authority answer")


if __name__ == "__main__":
    unittest.main()
