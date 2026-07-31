"""
CLAUDE-P40-D2 - the view-persistence boundary.

P40-C/P40-D added in-memory-only compatibility hydration
(CaseWorkspaceStore._hydrate_legacy_cases / _hydrate_legacy_reviews)
for legacy records, and both stages' own docstrings claimed reading a
legacy record "never writes anything" on its own. That claim was true
for CaseWorkspaceStore.get() in isolation, but incomplete: routes/
workspace.py's show_workspace already called store.save(workspace)
unconditionally on every ordinary Project Home GET (to record
last_viewed_by), and save()'s json.dumps(asdict(workspace)) serializes
the COMPLETE in-memory dataclass - silently persisting the hydrated
Case visibility, the reviews -> legacy_reviews rename, AND every other
dataclass field's default value that was never in the original legacy
file at all, purely as a byproduct of a plain view. An isolated
route-level reproduction (this stage's own Section A) found 21-60
changed fields from a single GET on a legacy record.

Fix: CaseWorkspaceStore.record_last_viewed(workspace, reviewer)
replaces the store.save(workspace) call in show_workspace. It patches
ONLY last_viewed_by directly into the raw on-disk JSON - never through
ProjectWorkspace(**data)/asdict(workspace) - so legacy compatibility
hydration stays exactly what it always should have been: in-memory
only, never persisted merely because someone looked.

Every ingestion call in this file spies on BHiveParser.parse rather
than letting it run for real (existing repo-wide convention).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument, RequirementItem
from services.case_workspace import CASE_VISIBILITY_SHARED, CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload
from services.requirements_registry import RequirementsRegistry

_LEGACY_VISIBILITY_PROJECT_ID = "p40d2-legacy-visibility-fixture"
_LEGACY_REVIEWS_PROJECT_ID = "p40d2-legacy-reviews-fixture"
_CURRENT_SCHEMA_PROJECT_ID = "p40d2-current-schema-fixture"

_LEGACY_REVIEWS_PAYLOAD = [
    {"id": "review-1", "finding_id": "finding-1", "decision": "accept",
     "reviewer": "legacyreviewowner", "reviewed_at": "2020-01-01T00:00:00+00:00", "note": None},
    {"id": "review-2", "finding_id": "finding-2", "decision": "correction",
     "reviewer": "legacyreviewowner", "reviewed_at": "2020-01-01T00:05:00+00:00",
     "note": "This is not a datum. It is a civil reference."},
]


def _write_legacy_visibility_fixture(tmp_dir: Path, owner="legacyowner") -> None:
    RequirementsRegistry(tmp_dir).save(ParsedDocument(
        project_id=_LEGACY_VISIBILITY_PROJECT_ID, filename="legacy_visibility.txt",
        ingested_at="2020-01-01T00:00:00+00:00",
        requirements=[RequirementItem(id="r1", text="Text.", category="other", confidence=0.5, source_line=1)],
    ))
    (tmp_dir / f"{_LEGACY_VISIBILITY_PROJECT_ID}.workspace.json").write_text(json.dumps({
        "project_id": _LEGACY_VISIBILITY_PROJECT_ID, "owner": owner, "access_allow_list": [],
        "cases": [{
            "id": "legacy-case-no-visibility", "project_id": _LEGACY_VISIBILITY_PROJECT_ID,
            "title": "Legacy Investigation", "objective": "", "created_at": "2020-01-01T00:00:00+00:00",
            "status": "open", "source_ids": [], "finding_ids": [], "analysis_ids": [], "artifact_ids": [],
            "activity_ids": [], "conversation": [],
            # deliberately no "visibility" key at all
        }],
        "version": 1,
    }), encoding="utf-8")


def _write_legacy_reviews_fixture(tmp_dir: Path, owner=None) -> None:
    RequirementsRegistry(tmp_dir).save(ParsedDocument(
        project_id=_LEGACY_REVIEWS_PROJECT_ID, filename="legacy_reviews.txt",
        ingested_at="2020-01-01T00:00:00+00:00",
        requirements=[RequirementItem(id="r1", text="Text.", category="other", confidence=0.5, source_line=1)],
    ))
    data = {
        "project_id": _LEGACY_REVIEWS_PROJECT_ID, "owner": owner, "access_allow_list": [],
        "cases": [],
        "findings": [
            {"id": "finding-1", "project_id": _LEGACY_REVIEWS_PROJECT_ID, "case_id": "c1", "analysis_id": "a1",
             "statement": "F1.", "machine_confidence": 0.5, "created_at": "2020-01-01T00:00:00+00:00",
             "claim_status": "applied", "artifact_id": None},
            {"id": "finding-2", "project_id": _LEGACY_REVIEWS_PROJECT_ID, "case_id": "c1", "analysis_id": "a1",
             "statement": "F2.", "machine_confidence": 0.5, "created_at": "2020-01-01T00:00:00+00:00",
             "claim_status": "provisional", "artifact_id": None},
        ],
        "reviews": [dict(r) for r in _LEGACY_REVIEWS_PAYLOAD],
        "version": 1,
    }
    if owner is None:
        del data["owner"]
    (tmp_dir / f"{_LEGACY_REVIEWS_PROJECT_ID}.workspace.json").write_text(json.dumps(data), encoding="utf-8")


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseP40D2TestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40d2_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="legacyowner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="p40d2_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="p40d2_outsider", password_hash=generate_password_hash("x"), role="read_only"))
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

    def _raw_workspace(self, project_id) -> dict:
        return json.loads((self.tmp_dir / f"{project_id}.workspace.json").read_text(encoding="utf-8"))

    def _ingest_current_schema_project(self, owner="p40d2_admin"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", "current.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=_CURRENT_SCHEMA_PROJECT_ID,
                )


class InMemoryHydrationStillWorksTests(_BaseP40D2TestCase):
    """1/3: the in-memory compatibility hydration itself (P40-C/P40-D)
    is unaffected by this stage - still verified directly against the
    store, not just indirectly through the route."""

    def test_missing_visibility_hydrates_as_shared_in_memory(self):
        _write_legacy_visibility_fixture(self.tmp_dir)
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(_LEGACY_VISIBILITY_PROJECT_ID)
        self.assertEqual(workspace.cases[0]["visibility"], CASE_VISIBILITY_SHARED)

    def test_legacy_reviews_load_completely_in_memory(self):
        _write_legacy_reviews_fixture(self.tmp_dir, owner="legacyowner")
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(_LEGACY_REVIEWS_PROJECT_ID)
        self.assertEqual(workspace.legacy_reviews, _LEGACY_REVIEWS_PAYLOAD)


class RouteLevelGetDoesNotPersistHydrationTests(_BaseP40D2TestCase):
    """2/4/5/6: the actual GET /projects/<id>/workspace route - not
    just the store in isolation - must never persist compatibility
    hydration, must only ever touch last_viewed_by, and must stay
    stable across repeated views."""

    def test_route_level_get_does_not_persist_hydrated_visibility(self):
        _write_legacy_visibility_fixture(self.tmp_dir)
        client = self._client_as("legacyowner", 1)
        resp = client.get(f"/projects/{_LEGACY_VISIBILITY_PROJECT_ID}/workspace")
        self.assertEqual(resp.status_code, 200)

        raw = self._raw_workspace(_LEGACY_VISIBILITY_PROJECT_ID)
        self.assertNotIn("visibility", raw["cases"][0])

    def test_route_level_get_does_not_rename_reviews(self):
        _write_legacy_reviews_fixture(self.tmp_dir, owner="legacyowner")
        client = self._client_as("legacyowner", 1)
        resp = client.get(f"/projects/{_LEGACY_REVIEWS_PROJECT_ID}/workspace")
        self.assertEqual(resp.status_code, 200)

        raw = self._raw_workspace(_LEGACY_REVIEWS_PROJECT_ID)
        self.assertIn("reviews", raw)
        self.assertEqual(raw["reviews"], _LEGACY_REVIEWS_PAYLOAD)
        self.assertNotIn("legacy_reviews", raw)

    def test_view_metadata_updates_without_rewriting_structural_content(self):
        _write_legacy_visibility_fixture(self.tmp_dir)
        before = self._raw_workspace(_LEGACY_VISIBILITY_PROJECT_ID)

        client = self._client_as("legacyowner", 1)
        client.get(f"/projects/{_LEGACY_VISIBILITY_PROJECT_ID}/workspace")

        after = self._raw_workspace(_LEGACY_VISIBILITY_PROJECT_ID)
        changed_keys = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        self.assertEqual(changed_keys, {"last_viewed_by"})
        self.assertEqual(before["cases"], after["cases"])
        # record_last_viewed never reads/bumps version - the fixture's
        # own pre-existing version value (1) must be completely untouched,
        # not merely present.
        self.assertEqual(before["version"], after["version"])

    def test_repeated_gets_produce_no_further_structural_drift(self):
        _write_legacy_reviews_fixture(self.tmp_dir, owner="legacyowner")
        client = self._client_as("legacyowner", 1)

        client.get(f"/projects/{_LEGACY_REVIEWS_PROJECT_ID}/workspace")
        after_first = self._raw_workspace(_LEGACY_REVIEWS_PROJECT_ID)

        client.get(f"/projects/{_LEGACY_REVIEWS_PROJECT_ID}/workspace")
        after_second = self._raw_workspace(_LEGACY_REVIEWS_PROJECT_ID)

        changed_keys = {k for k in set(after_first) | set(after_second) if after_first.get(k) != after_second.get(k)}
        self.assertEqual(changed_keys, {"last_viewed_by"})
        self.assertEqual(after_first["reviews"], after_second["reviews"])


class CurrentSchemaSaveUnaffectedTests(_BaseP40D2TestCase):
    """7: a genuinely current-schema project's real, explicit writes
    (not the implicit view-tracking path) still save normally through
    the ordinary save()."""

    def test_current_schema_project_saves_normally_on_explicit_write(self):
        doc = self._ingest_current_schema_project(owner="p40d2_admin")
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(doc.project_id)
        client = self._client_as("p40d2_admin", 1)

        resp = client.post(f"/projects/{doc.project_id}/workspace/star")
        self.assertIn(resp.status_code, (200, 302, 303))

        reloaded = store.get(doc.project_id)
        self.assertTrue(reloaded.starred)

    def test_current_schema_project_workspace_view_still_works(self):
        doc = self._ingest_current_schema_project(owner="p40d2_admin")
        client = self._client_as("p40d2_admin", 1)
        resp = client.get(f"/projects/{doc.project_id}/workspace")
        self.assertEqual(resp.status_code, 200)


class OwnerlessLegacyAccessFailClosedTests(_BaseP40D2TestCase):
    """8: the reviews-era fixture's real shape (no owner key at all) -
    admin-only, fail-closed for everyone else - is unaffected."""

    def test_admin_can_open_the_ownerless_legacy_project(self):
        _write_legacy_reviews_fixture(self.tmp_dir, owner=None)
        client = self._client_as("p40d2_admin", 1, role="admin")
        resp = client.get(f"/projects/{_LEGACY_REVIEWS_PROJECT_ID}/workspace")
        self.assertEqual(resp.status_code, 200)

    def test_non_admin_is_denied_the_ownerless_legacy_project(self):
        _write_legacy_reviews_fixture(self.tmp_dir, owner=None)
        client = self._client_as("p40d2_outsider", 2, role="read_only")
        resp = client.get(f"/projects/{_LEGACY_REVIEWS_PROJECT_ID}/workspace")
        self.assertEqual(resp.status_code, 404)


class NineteenProjectSyntheticSweepTests(_BaseP40D2TestCase):
    """11: a bounded, synthetic-fixture sweep spanning every
    compatibility shape addressed by P40-C/P40-D/P40-D2 together, all
    routed through the real GET path in one isolated directory - the
    same spirit as the real 19-project corpus sweep (run manually
    against an isolated copy of instance/registry/ for this stage's own
    report), kept synthetic here per this repo's hermetic-test
    convention."""

    def test_every_shape_survives_the_view_path_with_only_last_viewed_by_changing(self):
        _write_legacy_visibility_fixture(self.tmp_dir, owner="legacyowner")
        _write_legacy_reviews_fixture(self.tmp_dir, owner="legacyowner")
        doc = self._ingest_current_schema_project(owner="p40d2_admin")

        project_ids = [_LEGACY_VISIBILITY_PROJECT_ID, _LEGACY_REVIEWS_PROJECT_ID, doc.project_id]
        before = {pid: self._raw_workspace(pid) for pid in project_ids}

        client = self._client_as("p40d2_admin", 1, role="admin")
        for pid in project_ids:
            resp = client.get(f"/projects/{pid}/workspace")
            self.assertEqual(resp.status_code, 200, f"{pid} failed to load")

        for pid in project_ids:
            after = self._raw_workspace(pid)
            b, a = before[pid], after
            changed_keys = {k for k in set(b) | set(a) if b.get(k) != a.get(k)}
            self.assertEqual(changed_keys, {"last_viewed_by"}, f"{pid} had unexpected structural drift: {changed_keys}")


if __name__ == "__main__":
    unittest.main()
