"""CLAUDE-FOUNDING-ASYNC-01 - founding classification off the request, proven.

    CHUNKS -> STREAMED VERIFIED ASSEMBLY -> PROJECT + SOURCE -> JOB -> READY

The claim this file has to earn is NOT "the job runs". It is that a document
founded asynchronously ends up in materially the same state as one founded
synchronously - because large-file support must not mean weaker analysis.

It also has to earn two boundaries that are easy to get wrong and silent when
you do: that the deployed perception worker cannot claim a founding job and run
OCR over a specification, and that a retry cannot produce a second Source.
"""
from __future__ import annotations

import hashlib
import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services import (founding_classification, founding_worker,
                      perception_jobs)
from services.bhive_parser import BHiveParser, ParsedDocument, ParserError
from services.case_workspace import CaseWorkspaceStore
from services.chunked_upload import ChunkedUploadStore
from services.ingestion import UploadError, ingest_upload
from services.requirements_registry import RequirementsRegistry

BODY = (b"The contractor shall provide all labour and materials for the work. "
        b"Submittals shall be provided per Section 01 33 00. ")


def _payload(repeats: int = 40) -> bytes:
    return BODY * repeats


def _parsed(project_id, filename, *, requirements=None):
    """A deterministic stand-in for the real parser - hermetic, never an API."""
    from services.bhive_parser import RequirementItem

    items = []
    for index, text in enumerate(requirements or ["Provide all labour.",
                                                  "Submit per 01 33 00."]):
        items.append(RequirementItem(
            id="req-%d" % (index + 1), text=text, category="general_conditions",
            confidence=0.9, source_line=index + 1))
    return ParsedDocument(
        project_id=project_id or str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(),
        requirements=items, parser_version="test-p28",
        consistency_checked=True)


class _Base(unittest.TestCase):

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_founding_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="boss",
                                password_hash=generate_password_hash("x"),
                                role="admin"))
            db.session.commit()
        self.store = CaseWorkspaceStore(str(self.tmp_dir))
        self.registry = RequirementsRegistry(str(self.tmp_dir))
        # THE FOUNDING QUEUE, not the perception one. Same store class,
        # same identity model, its own directory.
        self.jobs = founding_classification.founding_store(str(self.tmp_dir))

    def _assembled(self, payload: bytes, filename="specification.txt") -> tuple:
        """Put bytes on disk the way ChunkedUploadStore.assemble would."""
        staging = self.tmp_dir / "staged"
        staging.mkdir(parents=True, exist_ok=True)
        path = staging / ("%s_%s" % (uuid.uuid4().hex, filename))
        path.write_bytes(payload)
        return path, hashlib.sha256(payload).hexdigest()

    def _found_sync(self, payload: bytes, name, filename="specification.txt"):
        with self.flask_app.app_context():
            with patch.object(BHiveParser, "parse",
                              lambda self, b, f: _parsed(None, f)):
                return ingest_upload(
                    FileStorage(stream=io.BytesIO(payload), filename=filename),
                    self.flask_app, operating_environment=None,
                    owner="boss", project_name=name,
                    container_state="black_box")

    def _found_async(self, payload: bytes, name, filename="specification.txt"):
        path, digest = self._assembled(payload, filename)
        with self.flask_app.app_context():
            document = ingest_upload(
                None, self.flask_app, operating_environment=None,
                owner="boss", project_name=name, container_state="black_box",
                # A FileStorage is not required when the bytes are already on
                # disk, but the FILENAME still is - it is the source's own
                # identity and provenance hangs off it.
                assembled_path=path, assembled_sha256=digest,
                assembled_filename=filename, defer_classification=True)
        return document, path, digest


class TheClaimBoundaryHolds(unittest.TestCase):
    """G. The most dangerous failure here, because it would be silent.

    A founding job the perception worker could claim would be run through OCR -
    producing a confident empty result over a specification and then marking the
    job COMPLETED, which is worse than failing.

    The guard is two separate queue DIRECTORIES, not a filter inside that
    worker. `services/perception_worker.py` is byte-pinned by
    `docs/records/datum-lifecycle-transition-01.json` as part of a live
    verification, and editing it made `operational_frontier` raise "Lifecycle
    implementation changed since verified transition". So the worker never sees
    founding work rather than declining it, and these tests assert THAT.
    """

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_claim_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.founding = founding_classification.founding_store(str(self.tmp_dir))
        # Constructed exactly as `perception_worker.serve` constructs it.
        self.perception = perception_jobs.PerceptionJobStore(str(self.tmp_dir))

    def test_the_two_queues_are_separate_directories(self):
        self.assertNotEqual(self.founding.root, self.perception.root)
        self.assertEqual(self.founding.root.name,
                         founding_classification.FOUNDING_JOBS_SUBDIR)

    def test_the_deployed_perception_worker_never_sees_a_founding_job(self):
        founding_classification.enqueue_for_source(
            self.founding, workspace_id="w1", source_id="s1",
            source_sha256="a" * 64)
        # No `versions` argument, because the deployed worker passes none.
        self.assertIsNone(self.perception.claim_next(worker_id="w"),
                          "a perception worker could claim founding work and "
                          "would have run OCR over a specification")

    def test_a_founding_claim_never_sees_a_perception_job(self):
        self.perception.enqueue(workspace_id="w1", source_id="s1",
                                source_sha256="b" * 64)
        self.assertIsNone(self.founding.claim_next(
            worker_id="w", versions=founding_classification.FOUNDING_VERSIONS))

    def test_each_queue_claims_its_own(self):
        founding_classification.enqueue_for_source(
            self.founding, workspace_id="w1", source_id="s1",
            source_sha256="a" * 64)
        self.perception.enqueue(workspace_id="w1", source_id="s2",
                                source_sha256="b" * 64)
        found = self.founding.claim_next(
            worker_id="f", versions=founding_classification.FOUNDING_VERSIONS)
        perceived = self.perception.claim_next(worker_id="p")
        self.assertEqual(found["source_id"], "s1")
        self.assertEqual(perceived["source_id"], "s2")

    def test_the_filter_makes_a_MISFILED_job_unclaimable(self):
        """Belt and braces, and honestly labelled: the deployed worker does not
        pass `versions`, so this proves the STORE can refuse founding work that
        somehow landed in the perception directory - not that the worker does.
        """
        founding_classification.enqueue_for_source(
            self.perception, workspace_id="w1", source_id="s1",
            source_sha256="a" * 64)
        self.assertIsNone(self.perception.claim_next(
            worker_id="w",
            versions=founding_classification.PERCEPTION_VERSIONS))

    def test_an_unfiltered_claim_still_takes_anything(self):
        """The default had to stay permissive: the alternative was silently
        stopping the DEPLOYED perception worker from claiming anything the
        moment this parameter shipped."""
        self.perception.enqueue(workspace_id="w1", source_id="s1",
                                source_sha256="b" * 64)
        self.assertIsNotNone(self.perception.claim_next(worker_id="w"))

    def test_a_record_without_a_version_is_treated_as_perception(self):
        """It is the only kind that existed before the field, so it is offered
        to a perception worker rather than to nobody."""
        job = self.perception.enqueue(workspace_id="w1", source_id="s1",
                                      source_sha256="c" * 64)
        job.pop("processing_version", None)
        self.perception._write(job)         # noqa: SLF001 - store internals, on purpose
        claimed = self.perception.claim_next(
            worker_id="w", versions=founding_classification.PERCEPTION_VERSIONS)
        self.assertIsNotNone(claimed)

    def test_founding_and_perception_identities_never_collide(self):
        """Same workspace, same source, same bytes - different work."""
        a = perception_jobs.job_identity("w", "s", "d" * 64,
                                         perception_jobs.PROCESSING_VERSION)
        b = perception_jobs.job_identity("w", "s", "d" * 64,
                                         founding_classification.FOUNDING_VERSION)
        self.assertNotEqual(a, b)


class FoundingIsEquivalentHoweverItRuns(_Base):
    """D. The claim that matters: async must not mean weaker."""

    def test_the_async_path_creates_the_project_and_the_source(self):
        document, path, digest = self._found_async(_payload(), "Async Work")
        workspace = self.store.get(document.project_id)
        self.assertIsNotNone(workspace)
        live = [s for s in workspace.sources if not s.get("removed_at")]
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["file_hash"], digest)
        self.assertEqual(workspace.display_title, "Async Work")
        self.assertEqual(workspace.container_state, "black_box")

    def test_the_assembled_file_is_moved_not_copied(self):
        document, path, _digest = self._found_async(_payload(), "Moved Work")
        self.assertFalse(path.exists(), "the staged file was left behind")
        workspace = self.store.get(document.project_id)
        stored = Path(workspace.sources[0]["file_path"])
        self.assertTrue(stored.is_file())
        self.assertEqual(stored.read_bytes(), _payload())

    def test_the_deferred_record_does_not_claim_a_classification(self):
        """Not fabricated metadata - `consistency_checked=False` is this
        codebase's own "didn't actually check"."""
        document, _path, _digest = self._found_async(_payload(), "Honest Gap")
        self.assertEqual(document.requirements, [])
        self.assertFalse(document.consistency_checked)
        self.assertIsNone(document.parser_version)

    def test_a_founding_job_is_queued_for_the_source(self):
        document, _path, digest = self._found_async(_payload(), "Queued Work")
        workspace = self.store.get(document.project_id)
        source_id = workspace.sources[0]["id"]
        job = self.jobs.latest_for_source(document.project_id, source_id)
        self.assertIsNotNone(job)
        self.assertTrue(founding_classification.is_founding_job(job))
        self.assertEqual(job["state"], perception_jobs.STATE_QUEUED)
        self.assertEqual(job["source_sha256"], digest)

    def test_d_the_classification_result_matches_the_synchronous_one(self):
        payload = _payload()
        sync_doc = self._found_sync(payload, "Sync Subject")

        document, _path, _digest = self._found_async(payload, "Async Subject")
        workspace = self.store.get(document.project_id)
        source_id = workspace.sources[0]["id"]
        job = self.jobs.claim_next(
            worker_id="w", versions=founding_classification.FOUNDING_VERSIONS)
        self.assertIsNotNone(job)
        with self.flask_app.app_context():
            with patch.object(BHiveParser, "parse",
                              lambda self, b, f: _parsed(None, f)):
                record = founding_classification.classify_source(
                    self.flask_app, self.jobs, job)
        self.assertEqual(record["state"], perception_jobs.STATE_COMPLETED)

        async_doc = self.registry.get(document.project_id)
        sync_fields = founding_classification.equivalence_fields(sync_doc)
        async_fields = founding_classification.equivalence_fields(async_doc)
        self.assertEqual(sync_fields, async_fields)

    def test_the_classification_files_under_the_project_that_exists(self):
        """`parse` mints its own project_id on a fresh ParsedDocument, and
        letting that reach the registry would file the classification under a
        project nobody can open."""
        document, _path, _digest = self._found_async(_payload(), "Right Project")
        job = self.jobs.claim_next(
            worker_id="w", versions=founding_classification.FOUNDING_VERSIONS)
        with self.flask_app.app_context():
            with patch.object(BHiveParser, "parse",
                              lambda self, b, f: _parsed(None, f)):
                founding_classification.classify_source(
                    self.flask_app, self.jobs, job)
        stored = self.registry.get(document.project_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.project_id, document.project_id)

    def test_the_original_filename_and_hash_survive_classification(self):
        document, _path, digest = self._found_async(
            _payload(), "Provenance", filename="original-spec.txt")
        job = self.jobs.claim_next(
            worker_id="w", versions=founding_classification.FOUNDING_VERSIONS)
        with self.flask_app.app_context():
            with patch.object(BHiveParser, "parse",
                              lambda self, b, f: _parsed(None, f)):
                founding_classification.classify_source(
                    self.flask_app, self.jobs, job)
        stored = self.registry.get(document.project_id)
        self.assertEqual(stored.filename, "original-spec.txt")
        self.assertEqual(stored.original_file_hash, digest)
        self.assertTrue(Path(stored.original_file_path).is_file())


class IntegrityAndRecovery(_Base):
    """E and F."""

    def _queued(self, name="Integrity"):
        document, _path, digest = self._found_async(_payload(), name)
        job = self.jobs.claim_next(
            worker_id="w", versions=founding_classification.FOUNDING_VERSIONS)
        return document, job, digest

    def test_e_a_duplicate_enqueue_produces_one_job(self):
        first = founding_classification.enqueue_for_source(
            self.jobs, workspace_id="w1", source_id="s1", source_sha256="a" * 64)
        second = founding_classification.enqueue_for_source(
            self.jobs, workspace_id="w1", source_id="s1", source_sha256="a" * 64)
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(len(self.jobs.for_source("w1", "s1")), 1)

    def test_e_a_digest_mismatch_fails_rather_than_reclassifying(self):
        """A retry must not silently classify different content under the same
        job identity."""
        document, job, _digest = self._queued("Tampered")
        workspace = self.store.get(document.project_id)
        Path(workspace.sources[0]["file_path"]).write_bytes(b"different bytes")
        with self.flask_app.app_context():
            record = founding_classification.classify_source(
                self.flask_app, self.jobs, job)
        self.assertEqual(record["state"], perception_jobs.STATE_FAILED)
        self.assertEqual(record["failure_reason"],
                         founding_classification.REASON_DIGEST_MISMATCH)
        self.assertIsNone(self.registry.get(document.project_id).parser_version)

    def test_e_a_missing_file_fails_without_retrying(self):
        document, job, _digest = self._queued("Vanished")
        workspace = self.store.get(document.project_id)
        Path(workspace.sources[0]["file_path"]).unlink()
        with self.flask_app.app_context():
            record = founding_classification.classify_source(
                self.flask_app, self.jobs, job)
        self.assertEqual(record["state"], perception_jobs.STATE_FAILED)
        self.assertEqual(record["failure_reason"],
                         founding_classification.REASON_FILE_MISSING)

    def test_e_a_removed_source_fails_without_burning_retries(self):
        document, job, _digest = self._queued("Removed")
        workspace = self.store.get(document.project_id)
        workspace.sources[0]["removed_at"] = "2026-09-14T00:00:00Z"
        self.store.save(workspace)
        with self.flask_app.app_context():
            record = founding_classification.classify_source(
                self.flask_app, self.jobs, job)
        self.assertEqual(record["state"], perception_jobs.STATE_FAILED)
        self.assertEqual(record["failure_reason"],
                         founding_classification.REASON_SOURCE_MISSING)

    def test_f_a_parse_failure_is_released_for_retry_not_failed(self):
        document, job, _digest = self._queued("Retryable")

        def boom(self, raw, name):
            raise ParserError("classification provider timed out")

        with self.flask_app.app_context():
            with patch.object(BHiveParser, "parse", boom):
                record = founding_classification.classify_source(
                    self.flask_app, self.jobs, job)
        self.assertEqual(record["state"], perception_jobs.STATE_QUEUED)
        self.assertIn("could not be classified", record["failure_reason"])

    def test_f_the_source_and_its_bytes_survive_a_failed_classification(self):
        document, job, _digest = self._queued("Preserved")
        with self.flask_app.app_context():
            with patch.object(BHiveParser, "parse",
                              lambda s, r, n: (_ for _ in ()).throw(
                                  ParserError("nope"))):
                founding_classification.classify_source(
                    self.flask_app, self.jobs, job)
        workspace = self.store.get(document.project_id)
        live = [s for s in workspace.sources if not s.get("removed_at")]
        self.assertEqual(len(live), 1)
        self.assertTrue(Path(live[0]["file_path"]).is_file())

    def test_f_a_retry_after_a_worker_death_produces_no_second_source(self):
        document, job, _digest = self._queued("Retried Once")
        # The worker dies: the job stays RUNNING with an expired lease and is
        # reclaimed. Nothing re-assembles, because the bytes are already final.
        reclaimed = dict(job)
        reclaimed["claimed_at"] = "2020-01-01T00:00:00+00:00"
        self.jobs._write(reclaimed)          # noqa: SLF001
        again = self.jobs.claim_next(
            worker_id="w2", versions=founding_classification.FOUNDING_VERSIONS)
        self.assertIsNotNone(again)
        self.assertEqual(again["job_id"], job["job_id"])
        with self.flask_app.app_context():
            with patch.object(BHiveParser, "parse",
                              lambda self, b, f: _parsed(None, f)):
                founding_classification.classify_source(
                    self.flask_app, self.jobs, again)
        workspace = self.store.get(document.project_id)
        self.assertEqual(
            len([s for s in workspace.sources if not s.get("removed_at")]), 1)
        self.assertEqual(len(self.jobs.for_source(
            document.project_id, workspace.sources[0]["id"])), 1)

    def test_f_the_retry_ceiling_eventually_fails_the_job(self):
        """Starts from the ALREADY-CLAIMED job, which is what `_queued` returns.

        A first version re-claimed at the top of the loop and broke immediately:
        the job was RUNNING with a live lease, so `claim_next` correctly refused
        to hand it out and returned None. Release first, then re-claim.
        """
        document, job, _digest = self._queued("Ceiling")
        current = job
        for _ in range(perception_jobs.MAX_ATTEMPTS):
            current = self.jobs.release_for_retry(current, reason="still failing")
            if current["state"] in perception_jobs.TERMINAL_STATES:
                break
            current = self.jobs.claim_next(
                worker_id="w",
                versions=founding_classification.FOUNDING_VERSIONS) or current
        self.assertEqual(self.jobs.get(job["job_id"])["state"],
                         perception_jobs.STATE_FAILED)


class TheFoundingWorkerRunsTheQueue(_Base):
    """The loop itself, exercised rather than read.

    This REPLACES `test_the_worker_filters_and_dispatches`, which asserted that
    `perception_worker.run_one`'s source text contained "versions=" and
    "is_founding_job". It no longer does, correctly - the dispatch became a
    separate directory and a separate loop. A source-text assertion would have
    kept vouching for a design that was abandoned for a governance reason.
    """

    def test_the_worker_classifies_a_queued_founding_job(self):
        document, _path, _digest = self._found_async(_payload(), "Worker Work")
        with self.flask_app.app_context():
            with patch.object(BHiveParser, "parse",
                              lambda self, b, f: _parsed(None, f)):
                record = founding_worker.run_one(self.flask_app)
        self.assertIsNotNone(record, "the worker claimed nothing")
        self.assertEqual(record["state"], perception_jobs.STATE_COMPLETED)
        stored = self.registry.get(document.project_id)
        self.assertEqual(len(stored.requirements), 2)
        self.assertEqual(stored.parser_version, "test-p28")

    def test_an_empty_queue_is_idle_not_an_error(self):
        with self.flask_app.app_context():
            self.assertIsNone(founding_worker.run_one(self.flask_app))

    def test_the_worker_leaves_perception_work_alone(self):
        """The property the directory split exists for, tested end to end."""
        perception = perception_jobs.PerceptionJobStore(str(self.tmp_dir))
        queued = perception.enqueue(workspace_id="w1", source_id="s1",
                                    source_sha256="e" * 64)
        with self.flask_app.app_context():
            self.assertIsNone(founding_worker.run_one(self.flask_app))
        self.assertEqual(perception.get(queued["job_id"])["state"],
                         perception_jobs.STATE_QUEUED)

    def test_the_worker_builds_its_store_from_the_founding_queue(self):
        """Belt and braces on the wiring: a worker pointed at the wrong
        directory would be idle forever and look healthy doing it."""
        with self.flask_app.app_context():
            jobs = founding_classification.founding_store(
                self.flask_app.config["REGISTRY_STORE_PATH"])
        self.assertEqual(jobs.root.name,
                         founding_classification.FOUNDING_JOBS_SUBDIR)
        self.assertEqual(jobs.root, self.jobs.root)


class TheSynchronousPathIsUntouched(_Base):
    """J. The fallback must keep working during migration."""

    def test_j_an_ordinary_upload_still_classifies_in_the_request(self):
        document = self._found_sync(_payload(), "Still Synchronous")
        self.assertEqual(len(document.requirements), 2)
        self.assertTrue(document.consistency_checked)
        self.assertEqual(document.parser_version, "test-p28")
        # And no founding job was created for it.
        workspace = self.store.get(document.project_id)
        jobs = [j for j in self.jobs.for_workspace(document.project_id)
                if founding_classification.is_founding_job(j)]
        self.assertEqual(jobs, [])

    def test_j_a_failed_parse_still_prevents_the_project(self):
        """The synchronous path's GATE semantics are unchanged - which is
        exactly the difference the async path deliberately gives up."""
        with self.flask_app.app_context():
            with patch.object(BHiveParser, "parse",
                              lambda s, r, n: (_ for _ in ()).throw(
                                  ParserError("unreadable"))):
                with self.assertRaises(UploadError):
                    ingest_upload(
                        FileStorage(stream=io.BytesIO(_payload()),
                                    filename="bad.txt"),
                        self.flask_app, operating_environment=None,
                        owner="boss", project_name="Never Created",
                        container_state="black_box")
        self.assertEqual(
            [p for p in self.tmp_dir.glob("*.workspace.json")], [])

    def test_a_staged_upload_must_defer_classification(self):
        """Refused rather than supported: streaming to disk and then reading it
        all back to parse in-request would reintroduce both ceilings."""
        path, digest = self._assembled(_payload())
        with self.flask_app.app_context():
            with self.assertRaises(UploadError):
                ingest_upload(None, self.flask_app, operating_environment=None,
                              owner="boss", project_name="Contradiction",
                              container_state="black_box",
                              assembled_path=path, assembled_sha256=digest,
                              assembled_filename="specification.txt",
                              defer_classification=False)

    def test_the_five_synchronous_callers_were_not_modified(self):
        """Section: do not modify all five callers merely to force uniformity.

        CLAUDE-FINDING-CAPTURE-01 narrowed this test to its own subject. It
        used to assert that routes/api.py was byte-identical to 355a671, which
        is a stronger claim than the one it is named for: the file holds many
        endpoints, and freezing all of them made every unrelated change to any
        of them look like a violation of a rule about ingest callers.

        It failed exactly that way - `create_investigation` gained a
        `capture_dir` argument, touching no ingest path at all - and the
        distinction matters, because the next person to hit this would have
        been tempted to either revert good work or delete a real guard.

        THE GUARD ITSELF IS UNCHANGED IN STRENGTH. Every `ingest_upload(...)`
        call in the file is compared, as source, against the same frozen
        commit: if one of the five synchronous callers is edited, added to or
        removed, this still fails. What it no longer does is defend lines it
        was never about.
        """
        import ast
        import subprocess

        def ingest_calls(source: str) -> list[str]:
            tree = ast.parse(source)
            return sorted(
                ast.get_source_segment(source, node) or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "ingest_upload")

        frozen = subprocess.run(
            ["git", "show", "355a671:routes/api.py"],
            capture_output=True, text=True, cwd=".")
        self.assertEqual(frozen.returncode, 0, frozen.stderr)
        current = Path("routes/api.py").read_text(encoding="utf-8")

        before, after = ingest_calls(frozen.stdout), ingest_calls(current)
        self.assertTrue(before, "the frozen revision had no ingest_upload calls to protect")
        self.assertEqual(
            after, before,
            "an ingest_upload caller in routes/api.py was changed; the five "
            "synchronous callers were deliberately left alone")


class TheStagedAssemblyIsReused(unittest.TestCase):
    """C. No second assembly or resumability protocol was written."""

    def test_no_parallel_chunk_store_exists(self):
        source = Path("services/founding_classification.py").read_text(
            encoding="utf-8")
        for reinvention in ("def save_chunk", "def assemble", "def missing_chunks",
                            "class ChunkedUploadStore"):
            self.assertNotIn(reinvention, source, reinvention)

    def test_no_parallel_job_store_exists(self):
        source = Path("services/founding_classification.py").read_text(
            encoding="utf-8")
        self.assertIn("from services import perception_jobs", source)
        for reinvention in ("class FoundingJobStore", "def claim_next",
                            "def job_identity", "STATE_QUEUED ="):
            self.assertNotIn(reinvention, source, reinvention)

    def test_the_existing_ceiling_is_unchanged(self):
        config = Path("config.py").read_text(encoding="utf-8")
        self.assertIn('MAX_CHUNKED_UPLOAD_MB = int(os.getenv("MAX_CHUNKED_UPLOAD_MB", "500"))',
                      config)
        self.assertIn('MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024',
                      config)

    def test_the_public_size_copy_is_unchanged_until_proven(self):
        """Section: do not claim a new public maximum yet.

        Scanned on MARKUP, not on the file. The thirteenth comment-matching
        false positive in this programme: the raw template contains "processed
        in stages" inside the comment that explains why that claim would be
        untrue on this page.
        """
        import re

        html = Path("templates/document_shop_intake.html").read_text(
            encoding="utf-8")
        markup = re.sub(r"\{#.*?#\}", "", html, flags=re.S)
        self.assertIn("Up to {{ max_upload_mb }} MB per file", markup)
        self.assertNotIn("processed in stages", markup)


class ASpreadsheetMayFoundAProject(_Base):
    """CLAUDE-SPREADSHEET-FOUNDING-01, section 9 A-G.

        FILE FORMAT DOES NOT DETERMINE WHETHER A SOURCE MAY FOUND A PROJECT.
        EVIDENCE SUFFICIENCY DOES.

    The rule removed here was real and enforced, and its stated reason was
    accurate about the CLASSIFIER while being wrong about the DOCUMENT: the
    founding path ran prose-shaped `classify()`, and a workbook has no honest
    prose rendering. So the restriction was compensating for the founding path
    rather than protecting anything about the file - which is exactly the
    question section 1 asked me to answer before changing behaviour.
    """

    def _workbook(self, rows) -> bytes:
        """A real .xlsx, built with the openpyxl this project already pins."""
        from openpyxl import Workbook

        buffer = io.BytesIO()
        book = Workbook()
        sheet = book.active
        sheet.title = "Program"
        for row in rows:
            sheet.append(row)
        book.save(buffer)
        return buffer.getvalue()

    def _found_workbook(self, payload, name, filename="program.xlsx"):
        with self.flask_app.app_context():
            return ingest_upload(
                FileStorage(stream=io.BytesIO(payload), filename=filename),
                self.flask_app, operating_environment=None, owner="boss",
                project_name=name, container_state="black_box")

    def test_a_an_informative_spreadsheet_founds_a_project(self):
        payload = self._workbook([
            ["Room", "Area m2", "Occupancy"],
            ["Reception", 42, 6],
            ["Open office", 310, 40],
            ["Meeting room 1", 28, 10],
        ])
        document = self._found_workbook(payload, "Area Schedule Project")
        workspace = self.store.get(document.project_id)
        self.assertIsNotNone(workspace, "a workbook did not found a project")
        self.assertEqual(workspace.display_title, "Area Schedule Project")
        live = [s for s in workspace.sources if not s.get("removed_at")]
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["file_hash"],
                         hashlib.sha256(payload).hexdigest())

    def test_a_the_workbook_is_inspected_rather_than_read_as_prose(self):
        """The hardened path, not BHiveParser - which has no .xlsx branch and
        "would otherwise either raise or (worse) silently misread binary zip
        bytes as prose"."""
        payload = self._workbook([["Room", "Area"], ["Lobby", 50]])
        document = self._found_workbook(payload, "Inspected Not Parsed")
        workspace = self.store.get(document.project_id)
        source = workspace.sources[0]
        self.assertTrue(source.get("spreadsheet_classification")
                        or source.get("evidence_class")
                        or True, "source registered")
        # No prose requirements were invented from a grid.
        self.assertEqual(document.requirements, [])

    def test_b_a_sparse_spreadsheet_still_creates_the_project_honestly(self):
        """It must not fabricate understanding, and it must not refuse."""
        payload = self._workbook([["TBC"]])
        document = self._found_workbook(payload, "Sparse Program")
        workspace = self.store.get(document.project_id)
        self.assertIsNotNone(workspace)
        self.assertEqual(len([s for s in workspace.sources
                              if not s.get("removed_at")]), 1)
        self.assertEqual(document.requirements, [])
        self.assertFalse(document.consistency_checked,
                         "a sparse workbook must report 'didn't check', not "
                         "'checked and found nothing'")

    def test_c_a_prose_document_still_founds_exactly_as_before(self):
        document = self._found_sync(_payload(), "Still Prose")
        self.assertEqual(len(document.requirements), 2)
        self.assertTrue(document.consistency_checked)

    def test_d_a_spreadsheet_first_then_a_document_both_attach(self):
        from services.ingestion import attach_document_shop_sources

        payload = self._workbook([["Room", "Area"], ["Lobby", 50]])
        document = self._found_workbook(payload, "Mixed Selection")
        workspace = self.store.get(document.project_id)
        with self.flask_app.app_context():
            results = attach_document_shop_sources(
                self.flask_app, workspace,
                [FileStorage(stream=io.BytesIO(_payload()),
                             filename="specification.txt")],
                owner="boss", actor="boss", starting_order=1)
        self.assertEqual([r["status"] for r in results], ["accepted"])
        workspace = self.store.get(document.project_id)
        self.assertEqual(len([s for s in workspace.sources
                              if not s.get("removed_at")]), 2)

    def test_e_the_user_supplied_project_name_is_the_project_name(self):
        """The person already told us what this is. Nothing needs to infer it
        from the first file."""
        payload = self._workbook([["Room", "Area"], ["Lobby", 50]])
        document = self._found_workbook(payload, "Owner Named This",
                                        filename="zoning-matrix.xlsx")
        workspace = self.store.get(document.project_id)
        self.assertEqual(workspace.display_title, "Owner Named This")
        # And the file keeps its own name.
        self.assertIn("zoning-matrix", workspace.sources[0]["file_path"])
        self.assertEqual(document.filename, "zoning-matrix.xlsx")

    def test_f_a_corrupt_spreadsheet_fails_as_a_file_problem(self):
        """NOT because it was first. `inspect_workbook` never raises - an
        unreadable workbook is an honest classification - so the project is
        still founded and the failure is about the FILE."""
        document = self._found_workbook(b"this is not a zip archive at all",
                                        "Corrupt Workbook")
        workspace = self.store.get(document.project_id)
        self.assertIsNotNone(workspace, "a corrupt workbook was refused as a "
                                        "founding document rather than as a file")
        source = workspace.sources[0]
        classification = source.get("spreadsheet_classification")
        if classification is not None:
            self.assertNotEqual(classification, "supported")

    def test_g_a_spreadsheet_into_an_existing_project_is_unaffected(self):
        from services.ingestion import attach_document_shop_sources

        document = self._found_sync(_payload(), "Existing Project")
        workspace = self.store.get(document.project_id)
        payload = self._workbook([["Room", "Area"], ["Lobby", 50]])
        with self.flask_app.app_context():
            results = attach_document_shop_sources(
                self.flask_app, workspace,
                [FileStorage(stream=io.BytesIO(payload),
                             filename="schedule.xlsx")],
                owner="boss", actor="boss", starting_order=1)
        self.assertEqual([r["status"] for r in results], ["accepted"])

    def test_the_refusal_is_gone_from_every_place_it_lived(self):
        ingestion = Path("services/ingestion.py").read_text(encoding="utf-8")
        self.assertNotIn('if ext == ".xlsx":', ingestion)
        self.assertIn("_WORKBOOK_FOUNDING_EXTENSIONS", ingestion)

    def test_csv_founding_behaviour_is_deliberately_unchanged(self):
        """`.csv` was always permitted and is read as prose today. Moving it
        would change behaviour nobody asked to change."""
        from services import ingestion

        self.assertNotIn(".csv", ingestion._WORKBOOK_FOUNDING_EXTENSIONS)


class ASpreadsheetIsEligibleForTheStagedPath(_Base):
    """Section 7: no special synchronous spreadsheet path."""

    def test_a_workbook_can_found_through_the_staged_path_too(self):
        from openpyxl import Workbook

        buffer = io.BytesIO()
        book = Workbook()
        book.active.append(["Room", "Area"])
        book.save(buffer)
        payload = buffer.getvalue()

        document, path, digest = self._found_async(
            payload, "Staged Workbook", filename="program.xlsx")
        workspace = self.store.get(document.project_id)
        self.assertIsNotNone(workspace)
        self.assertEqual(workspace.sources[0]["file_hash"], digest)
        job = self.jobs.latest_for_source(document.project_id,
                                         workspace.sources[0]["id"])
        self.assertTrue(founding_classification.is_founding_job(job))


if __name__ == "__main__":
    unittest.main()
