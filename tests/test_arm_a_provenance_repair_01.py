"""
CLAUDE-ARM-A-PROVENANCE-01 - "Is door D-106 rated?"

WHAT THIS FILE IS ACTUALLY PROVING

Two independent audits of ARCHIOSK's own surface converged on one finding:
provenance is stored with unusual rigor and then not delivered. Concretely,
two chains reach a Source from a Finding -

    finding.artifact_id -> Artifact.source_id     -> one Source
    finding.analysis_id -> AnalysisRun.source_ids -> many Sources

- and only the first was ever rendered, because the Findings card was gated on
`{% if artifact %}`. record_analysis mints an Artifact only when an item carries
a crop or an image, and only drawing analysis supplies those. So every Finding
produced by requirement investigation and quantitative investigation showed a
statement, a review badge and NO attribution whatsoever, while
AnalysisRun.source_ids sat in storage recording exactly which documents had been
read. governance/constitutional-invariants.md #3 - "every claim traces to its
source and originator" - held in storage and did not reach the person being
asked to trust the claim.

The verification query is deliberately the real one from the metabolic bridge
blind coordination audit, where ground truth is already known: D-106 is the door
tag that had no schedule row. A reviewer meeting that claim must be able to get
from "D-106 has no rating on record" to the document that was actually read,
without leaving the page and without an id-to-filename lookup they have no way
to perform - the document list shows names, and the Finding card showed a UUID.

TESTED AT BOTH LAYERS ON PURPOSE. The store-layer tests prove the derivation is
correct over both chains; the route-layer tests prove it is actually delivered.
A repair that is right in the service and still absent from the page is the
exact defect being fixed here, so proving only the first half would reproduce it.

Hermetic: nothing here touches ingest_upload, BHiveParser.parse, the Anthropic
API, SMTP or any network. Sources are registered directly through the store and
Findings are recorded through record_analysis with literal statements.

Stdlib unittest only, matching this repository's convention.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    PROVENANCE_BASIS_ANALYSIS,
    PROVENANCE_BASIS_ARTIFACT,
    PROVENANCE_BASIS_NONE,
    AnalysisTrigger,
    CaseWorkspaceStore,
)

FLOOR_PLAN = "A-101 Level 1 Floor Plan.pdf"
DOOR_SCHEDULE = "A-601 Door Schedule.pdf"

D106_STATEMENT = (
    "Door tag D-106 appears on the Level 1 plan but has no corresponding row "
    "in the door schedule, so no fire rating is on record for it."
)
RATED_STATEMENT = "Door D-104 is annotated 45 min on the Level 1 plan."


class _Base(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_arm_a_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-arm-a"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(
                project_id=self.project_id,
                filename="brief.md",
                ingested_at="2026-01-01T00:00:00+00:00",
            )
        )

        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(self.project_id)
        self.store.set_project_owner(self.workspace, owner="owner1", actor="owner1")

        self.plan = self.store.add_source(
            self.workspace, name=FLOOR_PLAN,
            file_path="/drawings/a101.pdf", kind="drawing",
        )
        self.schedule = self.store.add_source(
            self.workspace, name=DOOR_SCHEDULE,
            file_path="/drawings/a601.pdf", kind="drawing",
        )
        self.case = self.store.create_case(
            self.workspace, title="Smoke Management Analysis",
            objective="Door rating coordination", created_by="owner1",
        )
        self.trigger = AnalysisTrigger(
            trigger_type=ANALYSIS_TRIGGER_USER_INITIATED,
            triggered_by_actor="owner1",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # -- fixtures ----------------------------------------------------------

    def _record_d106(self):
        """The artifact-less chain - a requirement/quantitative-style
        investigation that read two documents and produced no crop.

        This is the Finding that rendered no provenance at all before this
        change, and it is the majority case in the product.
        """
        analysis = self.store.record_analysis(
            self.workspace, case_id=self.case["id"],
            source_ids=[self.plan["id"], self.schedule["id"]],
            objective="Is door D-106 rated?",
            engine_name="requirement_investigation", engine_version="1.0",
            findings=[{"statement": D106_STATEMENT, "machine_confidence": 0.5}],
            trigger=self.trigger,
        )
        return analysis, analysis["finding_ids"][0]

    def _record_drawing_finding(self):
        """The artifact chain - drawing analysis, which carries a crop and
        therefore mints an Artifact. The only chain that ever rendered."""
        analysis = self.store.record_analysis(
            self.workspace, case_id=self.case["id"],
            source_ids=[self.plan["id"]],
            objective="Door annotations on A-101",
            engine_name="drawing_analysis", engine_version="1.0",
            findings=[{
                "statement": RATED_STATEMENT,
                "machine_confidence": 0.9,
                "crop": {"x": 0.11, "y": 0.22, "width": 0.08, "height": 0.05},
                "page": 1,
                "source_id": self.plan["id"],
            }],
            trigger=self.trigger,
        )
        return analysis, analysis["finding_ids"][0]

    def _client(self, username="owner1", user_id=1, role="read_only"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _case_page(self, client=None):
        client = client or self._client()
        response = client.get(
            f"/projects/{self.project_id}/workspace?case={self.case['id']}"
        )
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)


# ---------------------------------------------------------------------------
# The structural fact the whole repair rests on.
# ---------------------------------------------------------------------------

class TwoChainsAreRealTests(_Base):
    def test_investigation_findings_genuinely_have_no_artifact(self):
        """If this ever fails, the premise is gone and the template's old
        `{% if artifact %}` gate would have been adequate after all."""
        _, finding_id = self._record_d106()
        finding = self.store._find(self.workspace.findings, finding_id)
        self.assertIsNone(finding.get("artifact_id"))
        self.assertIsNotNone(finding.get("analysis_id"))

    def test_drawing_findings_do_have_an_artifact(self):
        _, finding_id = self._record_drawing_finding()
        finding = self.store._find(self.workspace.findings, finding_id)
        self.assertIsNotNone(finding.get("artifact_id"))

    def test_the_source_ids_were_in_storage_all_along(self):
        """The evidence was never missing - only undelivered."""
        analysis, _ = self._record_d106()
        stored = self.store._find(self.workspace.analyses, analysis["id"])
        self.assertEqual(
            stored["source_ids"], [self.plan["id"], self.schedule["id"]]
        )


# ---------------------------------------------------------------------------
# The derivation.
# ---------------------------------------------------------------------------

class FindingProvenanceDerivationTests(_Base):
    def test_analysis_chain_resolves_every_document_to_a_name(self):
        _, finding_id = self._record_d106()
        prov = self.store.finding_provenance(self.workspace, finding_id)

        self.assertEqual(prov["basis"], PROVENANCE_BASIS_ANALYSIS)
        self.assertEqual(
            [s["name"] for s in prov["sources"]], [FLOOR_PLAN, DOOR_SCHEDULE]
        )
        self.assertTrue(all(s["resolved"] for s in prov["sources"]))
        self.assertTrue(all(not s["removed"] for s in prov["sources"]))
        self.assertIsNone(prov["artifact_id"])

    def test_artifact_chain_resolves_one_document_and_keeps_the_region(self):
        _, finding_id = self._record_drawing_finding()
        prov = self.store.finding_provenance(self.workspace, finding_id)

        self.assertEqual(prov["basis"], PROVENANCE_BASIS_ARTIFACT)
        self.assertEqual([s["name"] for s in prov["sources"]], [FLOOR_PLAN])
        self.assertIsNotNone(prov["artifact_id"])
        self.assertEqual(prov["page"], 1)
        self.assertAlmostEqual(prov["region"]["x"], 0.11)

    def test_a_removed_document_is_still_named_and_flagged(self):
        """remove_source is recoverable and deliberately not a deletion, so a
        Finding may legitimately cite a removed document. Saying so is more
        honest than dropping it or pretending it is current."""
        _, finding_id = self._record_d106()
        self.store.remove_source(
            self.workspace, self.schedule["id"], actor="owner1",
            reason="superseded",
        )
        prov = self.store.finding_provenance(self.workspace, finding_id)

        by_name = {s["name"]: s for s in prov["sources"]}
        self.assertEqual(len(prov["sources"]), 2)
        self.assertTrue(by_name[DOOR_SCHEDULE]["removed"])
        self.assertFalse(by_name[FLOOR_PLAN]["removed"])

    def test_an_unresolvable_source_id_is_reported_never_silently_dropped(self):
        """A missing document is evidence about the claim. Omitting it would
        make the provenance list quietly wrong, which is worse than a UUID."""
        analysis, finding_id = self._record_d106()
        stored = self.store._find(self.workspace.analyses, analysis["id"])
        stored["source_ids"] = [self.plan["id"], "source-that-vanished"]

        prov = self.store.finding_provenance(self.workspace, finding_id)
        self.assertEqual(len(prov["sources"]), 2)
        ghost = prov["sources"][1]
        self.assertFalse(ghost["resolved"])
        self.assertEqual(ghost["id"], "source-that-vanished")
        self.assertIsNone(ghost["name"])

    def test_no_chain_at_all_is_an_honest_answer_not_a_blank(self):
        _, finding_id = self._record_d106()
        finding = self.store._find(self.workspace.findings, finding_id)
        finding["analysis_id"] = None

        prov = self.store.finding_provenance(self.workspace, finding_id)
        self.assertEqual(prov["basis"], PROVENANCE_BASIS_NONE)
        self.assertEqual(prov["sources"], [])

    def test_derivation_stores_nothing(self):
        """It is a read. build_reference_snapshot's output is persisted into
        RFIDraft records; this deliberately is not, which is why it is a
        separate method rather than a widening of that one."""
        _, finding_id = self._record_d106()
        before = self.store.get(self.project_id)
        self.store.finding_provenance(self.workspace, finding_id)
        after = self.store.get(self.project_id)
        self.assertEqual(before.findings, after.findings)
        self.assertEqual(before.analyses, after.analyses)
        self.assertEqual(before.artifacts, after.artifacts)


# ---------------------------------------------------------------------------
# The delivery - "Is door D-106 rated?" as a reviewer actually meets it.
# ---------------------------------------------------------------------------

class D106VerificationQueryTests(_Base):
    def test_the_reviewer_is_told_which_documents_were_read(self):
        self._record_d106()
        body = self._case_page()

        self.assertIn(D106_STATEMENT, body)
        self.assertIn(FLOOR_PLAN, body)
        self.assertIn(DOOR_SCHEDULE, body)

    def test_each_document_is_one_click_away(self):
        """The destination already existed - show_workspace's own ?source=<id>
        opens the document. The Finding card simply never emitted the URL."""
        self._record_d106()
        body = self._case_page()

        for source in (self.plan, self.schedule):
            self.assertIn(
                f'href="/projects/{self.project_id}/workspace?source={source["id"]}"',
                body,
                f'no link to {source["name"]}',
            )

    def test_the_weaker_claim_is_labelled_as_the_weaker_claim(self):
        """An AnalysisRun records the documents a run READ. That is not the
        same claim as "this exact region of this exact page", and flattening
        the two would overstate the evidence."""
        self._record_d106()
        body = self._case_page()
        self.assertIn("Documents this analysis read", body)

    def test_the_artifact_chain_still_renders_everything_it_did_before(self):
        self._record_drawing_finding()
        body = self._case_page()

        self.assertIn(RATED_STATEMENT, body)
        self.assertIn(FLOOR_PLAN, body)
        self.assertIn("region:", body)
        self.assertIn("engine:", body)
        self.assertIn("analysis:", body)

    def test_both_chains_render_provenance_on_the_same_page(self):
        """The regression this file exists for: before the repair, exactly one
        of these two Findings carried any attribution at all."""
        self._record_d106()
        self._record_drawing_finding()
        body = self._case_page()

        marker = 'data-ui-ref="toolbox.investigation-findings.provenance"'
        self.assertEqual(body.count(marker), 2, "one Finding still has no provenance block")

    def test_no_finding_is_left_with_an_unexplained_absence(self):
        self._record_d106()
        body = self._case_page()
        self.assertNotIn("No source document on record for this finding.", body)


class ConfidenceHonestyTests(_Base):
    def test_the_hardcoded_percentage_is_no_longer_rendered(self):
        """conversation_interpreter's quantitative path hardcodes 0.5, so this
        card rendered a literal constant as "confidence 50%".
        case_workspace.py's own rule for this float says it must never be
        "presented on its own as if it carried the categorical meaning"."""
        self._record_d106()
        self._record_drawing_finding()
        body = self._case_page()

        self.assertIsNone(
            re.search(r"confidence\s+\d+\s*%", body, re.IGNORECASE),
            "a confidence percentage is still being rendered",
        )
        self.assertIn("Machine finding", body)

    def test_the_stored_field_is_untouched(self):
        """This is a delivery fix, not a data change - the float still exists
        for whatever wants to reason about it, it is simply not shown to a
        person as if it meant something it does not."""
        _, finding_id = self._record_d106()
        finding = self.store._find(self.workspace.findings, finding_id)
        self.assertEqual(finding["machine_confidence"], 0.5)


# ---------------------------------------------------------------------------
# UI Reference Mode - internal instrumentation, not a customer feature.
# ---------------------------------------------------------------------------

class UIReferenceModeIsAdminOnlyTests(_Base):
    TOGGLE = 'id="ui-reference-mode-toggle"'
    RESTORE = "beehive:ui-reference-mode"

    def test_an_ordinary_signed_in_user_does_not_get_the_developer_toggle(self):
        """It was gated on `{% if authenticated %}` and nothing else."""
        body = self._case_page(self._client(role="read_only"))
        self.assertNotIn(self.TOGGLE, body)

    def test_an_admin_still_gets_it(self):
        body = self._case_page(self._client(username="admin1", user_id=2, role="admin"))
        self.assertIn(self.TOGGLE, body)

    def test_a_stale_device_preference_cannot_survive_the_gate(self):
        """localStorage outlives a session. Gating only the toggle would strand
        a user who had switched it on earlier: badges on, no control to turn
        them off."""
        body = self._case_page(self._client(role="read_only"))
        self.assertNotIn(self.RESTORE, body)

    def test_the_signed_out_sign_in_page_never_restores_it(self):
        client = self.flask_app.test_client()
        body = client.get("/login").get_data(as_text=True)
        self.assertNotIn(self.RESTORE, body)
        self.assertNotIn(self.TOGGLE, body)

    def test_no_shell_anywhere_leaks_the_restore_to_a_non_admin(self):
        """The structural version of the three tests above.

        The restore is duplicated across FOUR shells - base, gateway, panel and
        (formerly) auth. Gating them one at a time is exactly how one gets left
        behind: panel_shell.html renders only as the content of a non-zero
        Display division inside an <iframe>, so it never shows up in an
        ordinary page-source read and was missed on the first pass. This walks
        every template that mentions the key and requires each one to be
        rendered through a real request as a non-admin without leaking it, so a
        fifth shell cannot be added without this failing.
        """
        import re
        from pathlib import Path

        templates_dir = Path(self.flask_app.root_path) / "templates"
        carriers = {
            p.name for p in templates_dir.glob("*.html")
            if self.RESTORE in p.read_text(encoding="utf-8")
        }
        # If this set ever shrinks to nothing the sweep below is vacuous, and
        # if it grows the new shell needs a rendering path added here.
        self.assertEqual(
            carriers,
            {"base.html", "gateway_shell.html", "panel_shell.html"},
            "a shell carrying the UI Reference Mode restore was added or removed",
        )

        client = self._client(role="read_only")
        paths = (
            f"/projects/{self.project_id}/workspace?case={self.case['id']}",   # base
            "/projects",                                                       # gateway
            f"/projects/{self.project_id}/workspace?case={self.case['id']}&panel=1",  # panel
        )
        for url in paths:
            response = client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertNotIn(self.RESTORE, response.get_data(as_text=True), url)

    def test_the_panel_shell_still_serves_its_content_to_a_non_admin(self):
        """Gating the restore must not gate the panel itself - the iframe
        content is ordinary authorized workspace content, not admin content."""
        client = self._client(role="read_only")
        self._record_d106()
        response = client.get(
            f"/projects/{self.project_id}/workspace?case={self.case['id']}&panel=1"
        )
        self.assertEqual(response.status_code, 200)
        # The Investigation OVERVIEW division, not the Findings accordion -
        # panel_shell is the content of one Display division, so the case's own
        # identity is what proves real authorized content was served here.
        self.assertIn("Smoke Management Analysis", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
