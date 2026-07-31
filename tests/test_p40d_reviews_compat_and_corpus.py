"""
CLAUDE-P40-D - Persisted-Project Compatibility Closure, Mutation-Free
Corpus Validation.

A second, structurally different legacy-record defect than P40-C's
Case-visibility KeyError, found during P40-C's own bounded regression
audit and deliberately deferred there: a workspace record serialized
before commit d1ac48e ("Extend Case Workspace with three-part review
model...") has a top-level "reviews" key - the single original Review
concept (decision one of accept/reject/needs_evidence/correction,
commit 0e86380) - that TypeErrors on ProjectWorkspace(**data) because
d1ac48e replaced it with two deliberately DIFFERENT concepts
(reviewer_validations / dispositions) with no honest 1:1 mapping back
onto the old vocabulary. See CaseWorkspaceStore._hydrate_legacy_reviews
for the full reasoning.

Unlike the visibility KeyError, every real call site of
CaseWorkspaceStore.get()/get_or_create() already wrapped this exact
TypeError in a try/except -> fail closed (CLAUDE-P37 hardening,
app.py/routes/workspace.py/routes/portal.py/routes/security.py/
services/ingestion.py/services/project_access.py/services/
security_assurance.py) - so this was never a traceback-exposure/
security incident the way the visibility KeyError was. It was a
product-availability defect: the affected project's owner could not
open it at all (silently treated as "not accessible", same as a
nonexistent project). The fix here restores real access, it does not
change the security posture.

Three layers, mirroring test_p40c_legacy_compat_and_safety.py's shape:
  - LegacyReviewsHydrationTests: the compatibility fix itself.
  - ReviewsAccessInvariantTests: authorization is unaffected -
    including the owner=None (never-established-owner, admin-only)
    case, which the real affected project actually has.
  - CorpusSweepTests: a bounded, synthetic-fixture, mutation-free load
    sweep exercising both compatibility adapters together.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry

_LEGACY_REVIEWS_PROJECT_ID = "legacy-reviews-fixture-project"
_UNOWNED_LEGACY_PROJECT_ID = "legacy-reviews-unowned-fixture-project"
_CURRENT_SCHEMA_PROJECT_ID = "current-schema-fixture-project"


def _legacy_reviews_payload() -> list[dict]:
    """The real pre-d1ac48e shape: id, finding_id, decision (one of the
    old REVIEW_DECISIONS vocabulary), reviewer, reviewed_at, note."""
    return [
        {
            "id": "review-1", "finding_id": "finding-1", "decision": "accept",
            "reviewer": "legacyreviewowner", "reviewed_at": "2020-01-01T00:00:00+00:00", "note": None,
        },
        {
            "id": "review-2", "finding_id": "finding-2", "decision": "correction",
            "reviewer": "legacyreviewowner", "reviewed_at": "2020-01-01T00:05:00+00:00",
            "note": "This is not a datum. It is a civil reference.",
        },
    ]


def _write_legacy_reviews_fixture(tmp_dir: Path, project_id: str, owner) -> None:
    RequirementsRegistry(tmp_dir).save(ParsedDocument(
        project_id=project_id, filename="legacy_reviews_probe.txt", ingested_at="2020-01-01T00:00:00+00:00",
        requirements=[RequirementItem(id="r1", text="Legacy requirement text.", category="other", confidence=0.5, source_line=1)],
    ))
    workspace_path = tmp_dir / f"{project_id}.workspace.json"
    workspace_data = {
        "project_id": project_id,
        "owner": owner,
        "access_allow_list": [],
        "cases": [],
        "findings": [
            {"id": "finding-1", "project_id": project_id, "case_id": "c1", "analysis_id": "a1",
             "statement": "Finding one.", "machine_confidence": 0.5, "created_at": "2020-01-01T00:00:00+00:00",
             "claim_status": "applied", "artifact_id": None},
            {"id": "finding-2", "project_id": project_id, "case_id": "c1", "analysis_id": "a1",
             "statement": "Finding two.", "machine_confidence": 0.5, "created_at": "2020-01-01T00:00:00+00:00",
             "claim_status": "provisional", "artifact_id": None},
        ],
        "reviews": _legacy_reviews_payload(),
        "version": 1,
    }
    if owner is None:
        del workspace_data["owner"]
    workspace_path.write_text(json.dumps(workspace_data), encoding="utf-8")


def _write_current_schema_fixture(tmp_dir: Path, project_id: str, owner: str) -> None:
    RequirementsRegistry(tmp_dir).save(ParsedDocument(
        project_id=project_id, filename="current_probe.txt", ingested_at="2026-01-01T00:00:00+00:00",
        requirements=[RequirementItem(id="r1", text="Current requirement text.", category="other", confidence=0.5, source_line=1)],
    ))
    workspace_path = tmp_dir / f"{project_id}.workspace.json"
    workspace_data = {
        "project_id": project_id,
        "owner": owner,
        "access_allow_list": [],
        "cases": [],
        "reviewer_validations": [
            {"id": "rv1", "finding_id": "f1", "validation": "Correct", "reviewer": owner,
             "validated_at": "2026-01-01T00:00:00+00:00", "correction_note": None},
        ],
        "dispositions": [
            {"id": "d1", "finding_id": "f1", "disposition": "Confirmed", "reviewer": owner,
             "recorded_at": "2026-01-01T00:00:00+00:00"},
        ],
        "version": 1,
    }
    workspace_path.write_text(json.dumps(workspace_data), encoding="utf-8")


class LegacyReviewsHydrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40d_"))
        _write_legacy_reviews_fixture(self.tmp_dir, _LEGACY_REVIEWS_PROJECT_ID, owner="legacyreviewowner")
        _write_current_schema_fixture(self.tmp_dir, _CURRENT_SCHEMA_PROJECT_ID, owner="currentowner")
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_legacy_reviews_hydrates_without_typeerror(self):
        workspace = self.store.get(_LEGACY_REVIEWS_PROJECT_ID)
        self.assertEqual(len(workspace.legacy_reviews), 2)

    def test_legacy_review_content_is_preserved_verbatim(self):
        workspace = self.store.get(_LEGACY_REVIEWS_PROJECT_ID)
        self.assertEqual(workspace.legacy_reviews, _legacy_reviews_payload())

    def test_nothing_is_invented_into_current_schema_review_concepts(self):
        # Section C: "avoid inventing decisions ... map legacy
        # information only where the canonical semantic equivalent is
        # established." No honest 1:1 mapping exists, so nothing is
        # synthesized into reviewer_validations/dispositions.
        workspace = self.store.get(_LEGACY_REVIEWS_PROJECT_ID)
        self.assertEqual(workspace.reviewer_validations, [])
        self.assertEqual(workspace.dispositions, [])

    def test_current_schema_project_is_unaffected(self):
        workspace = self.store.get(_CURRENT_SCHEMA_PROJECT_ID)
        self.assertEqual(workspace.legacy_reviews, [])
        self.assertEqual(len(workspace.reviewer_validations), 1)
        self.assertEqual(len(workspace.dispositions), 1)

    def test_get_alone_never_writes_back_to_the_persisted_file(self):
        raw_before = (self.tmp_dir / f"{_LEGACY_REVIEWS_PROJECT_ID}.workspace.json").read_text(encoding="utf-8")
        self.store.get(_LEGACY_REVIEWS_PROJECT_ID)
        raw_after = (self.tmp_dir / f"{_LEGACY_REVIEWS_PROJECT_ID}.workspace.json").read_text(encoding="utf-8")
        self.assertEqual(raw_before, raw_after)
        self.assertIn('"reviews"', raw_after)
        self.assertNotIn('"legacy_reviews"', raw_after)

    def test_legacy_record_survives_a_fresh_store_load_after_restart(self):
        fresh_store = CaseWorkspaceStore(self.tmp_dir)
        workspace = fresh_store.get(_LEGACY_REVIEWS_PROJECT_ID)
        self.assertEqual(len(workspace.legacy_reviews), 2)

    def test_survives_an_actual_save_and_restart_round_trip(self):
        # If some unrelated write path (e.g. show_workspace's
        # last_viewed_by tracking, per _hydrate_legacy_cases' own
        # precedent) later saves this workspace, the renamed field must
        # persist correctly and still be loadable after that.
        workspace = self.store.get(_LEGACY_REVIEWS_PROJECT_ID)
        self.store.save(workspace)
        raw = json.loads((self.tmp_dir / f"{_LEGACY_REVIEWS_PROJECT_ID}.workspace.json").read_text(encoding="utf-8"))
        self.assertNotIn("reviews", raw)
        self.assertIn("legacy_reviews", raw)

        fresh_store = CaseWorkspaceStore(self.tmp_dir)
        reloaded = fresh_store.get(_LEGACY_REVIEWS_PROJECT_ID)
        self.assertEqual(reloaded.legacy_reviews, _legacy_reviews_payload())

    def test_repeated_reads_are_idempotent(self):
        first = self.store.get(_LEGACY_REVIEWS_PROJECT_ID)
        second = self.store.get(_LEGACY_REVIEWS_PROJECT_ID)
        self.assertEqual(first.legacy_reviews, second.legacy_reviews)


class ReviewsAccessInvariantTests(unittest.TestCase):
    """The reviews compatibility fix must never grant, widen, or
    substitute for project-level access authorization - including the
    owner=None case, which the real affected project actually has."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40d_access_"))
        _write_legacy_reviews_fixture(self.tmp_dir, _LEGACY_REVIEWS_PROJECT_ID, owner="legacyreviewowner")
        _write_legacy_reviews_fixture(self.tmp_dir, _UNOWNED_LEGACY_PROJECT_ID, owner=None)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="legacyreviewowner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="reviews_unauthorized_user", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.add(User(username="reviews_admin_user", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def test_owner_can_open_the_legacy_reviews_project(self):
        client = self._client_as("legacyreviewowner", 1)
        resp = client.get(f"/projects/{_LEGACY_REVIEWS_PROJECT_ID}/workspace")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("TypeError", resp.get_data(as_text=True))

    def test_unauthorized_authenticated_user_is_denied_for_an_owned_project(self):
        client = self._client_as("reviews_unauthorized_user", 2, role="read_only")
        resp = client.get(f"/projects/{_LEGACY_REVIEWS_PROJECT_ID}/workspace")
        self.assertEqual(resp.status_code, 404)

    def test_admin_can_open_an_unowned_legacy_reviews_project(self):
        # owner is None (never established) - services.project_access.
        # can_access_project's admin bypass still applies; unaffected
        # by the reviews hydration.
        client = self._client_as("reviews_admin_user", 3, role="admin")
        resp = client.get(f"/projects/{_UNOWNED_LEGACY_PROJECT_ID}/workspace")
        self.assertEqual(resp.status_code, 200)

    def test_non_admin_is_denied_an_unowned_legacy_reviews_project(self):
        # owner=None fails CLOSED for a non-admin (services.
        # project_access.can_access_project's own documented invariant)
        # - the reviews hydration must not change this.
        client = self._client_as("reviews_unauthorized_user", 2, role="read_only")
        resp = client.get(f"/projects/{_UNOWNED_LEGACY_PROJECT_ID}/workspace")
        self.assertEqual(resp.status_code, 404)


class CorpusSweepTests(unittest.TestCase):
    """Section D: a bounded, mutation-free load sweep over a synthetic
    corpus spanning every compatibility shape this stage and P40-C
    together address, in one isolated directory."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40d_corpus_"))
        _write_current_schema_fixture(self.tmp_dir, "corpus-current", owner="corpusowner")
        _write_legacy_reviews_fixture(self.tmp_dir, "corpus-legacy-reviews", owner="corpusowner")
        _write_legacy_reviews_fixture(self.tmp_dir, "corpus-legacy-reviews-unowned", owner=None)
        # legacy Case-visibility shape (P40-C), reused here to prove
        # both adapters coexist safely in one sweep
        workspace_path = self.tmp_dir / "corpus-legacy-visibility.workspace.json"
        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id="corpus-legacy-visibility", filename="probe.txt", ingested_at="2020-01-01T00:00:00+00:00",
            requirements=[RequirementItem(id="r1", text="Text.", category="other", confidence=0.5, source_line=1)],
        ))
        workspace_path.write_text(json.dumps({
            "project_id": "corpus-legacy-visibility", "owner": "corpusowner", "access_allow_list": [],
            "cases": [{
                "id": "c1", "project_id": "corpus-legacy-visibility", "title": "T", "objective": "",
                "created_at": "2020-01-01T00:00:00+00:00", "status": "open",
                "source_ids": [], "finding_ids": [], "analysis_ids": [], "artifact_ids": [], "activity_ids": [],
                "conversation": [],
            }],
            "version": 1,
        }), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _fingerprint(self) -> dict:
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in self.tmp_dir.glob("*.json")
        }

    def test_every_shape_loads_without_crashing_and_nothing_is_mutated(self):
        before = self._fingerprint()

        store = CaseWorkspaceStore(self.tmp_dir)
        registry = RequirementsRegistry(self.tmp_dir)
        project_ids = sorted({p.name.split(".")[0] for p in self.tmp_dir.glob("*.workspace.json")})
        self.assertEqual(len(project_ids), 4)

        for pid in project_ids:
            workspace = store.get(pid)
            self.assertIsNotNone(workspace, f"{pid} failed to load")
            store.visible_cases_for(workspace, "corpusowner")
            registry.get(pid)

        after = self._fingerprint()
        self.assertEqual(before, after, "corpus sweep mutated a source file")
