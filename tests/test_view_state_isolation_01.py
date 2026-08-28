"""
CLAUDE-VIEW-STATE-ISOLATION-01 - a page view cannot destroy evidence.

THE DEFECT

record_last_viewed read the WHOLE workspace document, patched one key, and wrote
the whole document back - with no version read, no check and no bump - on every
ordinary Project Home GET (routes/workspace.py:1187). CaseWorkspaceStore's
_save_lock is a threading.Lock, so across the fifteen gunicorn worker processes
production runs (cpu_count()*2+1, deploy/gunicorn.conf.py) it serialised nothing.

So: Alice POSTs a Disposition in worker 7. Bob merely OPENS the project in worker
3, having read the file microseconds earlier. Bob's whole-document write lands
second and silently reverts Alice's governed write - Finding, Disposition and
version counter together. Alice sees a 302 and nothing wrong. Her next write then
raises ConcurrentModificationError and shows a 409 about a collision that already
destroyed her work, and the GovernanceLog still asserts a review the workspace no
longer contains.

WHY THE FIX IS ISOLATION RATHER THAN A VERSION CHECK

A version check on the patch would have DETECTED the collision and turned an
ordinary page view into a 409. That is not an improvement. A view has no business
touching evidence at all, so the ability was removed rather than guarded - the
same reasoning visible_cases_for records for Case privacy, and the same reasoning
that made `file_path is None` the custody claim rather than a stored flag.

WHY THESE TESTS USE REAL PROCESSES

The bug is cross-process by definition: within one process the threading.Lock
already serialised everything, and every existing test ran in-process, which is
exactly why this survived. tests/test_ca1d_attention_state_02.py:209-216 even
names the gap in a comment and disclaims it. A test that shares memory cannot
detect a bug caused by not sharing memory.
"""
from __future__ import annotations

import json
import multiprocessing
import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import CaseWorkspaceStore

_PROJECT = "view-isolation"


# --- module-level, because Windows spawns rather than forks ----------------

def _view_storm(store_path, project_id, reviewer, rounds, ready, done):
    """A worker doing nothing but ordinary page views."""
    store = CaseWorkspaceStore(store_path)
    ready.wait(timeout=30)
    for _ in range(rounds):
        workspace = store.get(project_id)
        if workspace is not None:
            store.record_last_viewed(workspace, reviewer)
    done.put(reviewer)


def _governed_writer(store_path, project_id, count, ready, done):
    """A worker doing governed structural writes, retrying on collision."""
    from services.case_workspace import ConcurrentModificationError

    store = CaseWorkspaceStore(store_path)
    ready.wait(timeout=30)
    written = []
    for index in range(count):
        for _attempt in range(60):
            workspace = store.get(project_id)
            case = store.create_case(
                workspace, title="Governed %d" % index,
                objective="written under a view storm", created_by="alice")
            try:
                store.save(workspace)
            except ConcurrentModificationError:
                continue
            written.append(case["id"])
            break
    done.put(written)


class _Project(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="view-isolation-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.dir)
        workspace = self.store.get_or_create(_PROJECT)
        self.store.create_case(workspace, title="Seed", objective="pre-existing",
                               created_by="alice")
        self.store.save(workspace)

    def raw(self):
        path = Path(self.dir) / ("%s.workspace.json" % _PROJECT)
        return json.loads(path.read_text(encoding="utf-8"))


class AViewNeverTouchesTheEvidenceDocument(_Project):
    def test_a_view_leaves_the_workspace_file_byte_identical(self):
        path = Path(self.dir) / ("%s.workspace.json" % _PROJECT)
        before = path.read_bytes()
        workspace = self.store.get(_PROJECT)
        self.store.record_last_viewed(workspace, "bob")
        self.assertEqual(path.read_bytes(), before)

    def test_the_timestamp_lands_in_the_sidecar_instead(self):
        workspace = self.store.get(_PROJECT)
        stamp = self.store.record_last_viewed(workspace, "bob")
        sidecar = Path(self.dir) / "_view_state" / ("%s.json" % _PROJECT)
        self.assertTrue(sidecar.is_file())
        self.assertEqual(
            json.loads(sidecar.read_text(encoding="utf-8"))["last_viewed_by"]["bob"],
            stamp)

    def test_it_is_read_back_through_the_ordinary_accessor(self):
        # Routes and templates read workspace.last_viewed_by; the overlay means
        # none of them changed.
        workspace = self.store.get(_PROJECT)
        stamp = self.store.record_last_viewed(workspace, "bob")
        self.assertEqual(self.store.get(_PROJECT).last_viewed_by["bob"], stamp)

    def test_item_review_state_is_isolated_the_same_way(self):
        path = Path(self.dir) / ("%s.workspace.json" % _PROJECT)
        before = path.read_bytes()
        workspace = self.store.get(_PROJECT)
        self.store.record_item_reviewed(workspace, "bob", "finding-1")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(
            self.store.get(_PROJECT).item_reviewed_at["bob"]["finding-1"],
            workspace.item_reviewed_at["bob"]["finding-1"])

    def test_the_sidecar_never_lands_where_a_json_glob_would_find_it(self):
        # requirements_registry.list_ids() globs "*.json" at the registry root
        # and strips one suffix. The first version of this fix put the sidecar
        # there and produced a bogus "<project_id>.view" id that failed with
        # KeyError: 'project_id'. That module's own comment already warns about
        # this for ".workspace".
        self.store.record_last_viewed(self.store.get(_PROJECT), "bob")
        root_json = {p.name for p in Path(self.dir).glob("*.json")}
        self.assertEqual(root_json, {"%s.workspace.json" % _PROJECT})

    def test_the_registry_still_lists_only_real_projects(self):
        from services.requirements_registry import RequirementsRegistry

        self.store.record_last_viewed(self.store.get(_PROJECT), "bob")
        ids = RequirementsRegistry(self.dir).list_ids()
        self.assertNotIn("%s.view" % _PROJECT, ids)
        self.assertNotIn("%s.workspace" % _PROJECT, ids)


class LegacyEmbeddedViewStateStillReads(_Project):
    """Records written before this change carry the keys inside the document.

    Not migrated: a migration would rewrite every workspace file to move data
    with no governance meaning. The overlay makes the old copy harmless as soon
    as anything new is written.
    """

    def test_an_embedded_timestamp_is_still_visible(self):
        path = Path(self.dir) / ("%s.workspace.json" % _PROJECT)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["last_viewed_by"] = {"legacy_user": "2026-01-01T00:00:00+00:00"}
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.store.get(_PROJECT).last_viewed_by["legacy_user"],
                         "2026-01-01T00:00:00+00:00")

    def test_the_sidecar_wins_over_a_stale_embedded_copy(self):
        path = Path(self.dir) / ("%s.workspace.json" % _PROJECT)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["last_viewed_by"] = {"bob": "2020-01-01T00:00:00+00:00"}
        path.write_text(json.dumps(data), encoding="utf-8")
        fresh = self.store.record_last_viewed(self.store.get(_PROJECT), "bob")
        self.assertEqual(self.store.get(_PROJECT).last_viewed_by["bob"], fresh)


class AViewStormCannotRevertGovernedWrites(_Project):
    """The regression, with real processes. This is the whole point."""

    def test_governed_cases_all_survive_concurrent_view_traffic(self):
        ready = multiprocessing.Event()
        done = multiprocessing.Queue()
        viewers = [
            multiprocessing.Process(target=_view_storm,
                                    args=(self.dir, _PROJECT, "viewer-%d" % i, 40,
                                          ready, done))
            for i in range(4)
        ]
        writer = multiprocessing.Process(
            target=_governed_writer, args=(self.dir, _PROJECT, 8, ready, done))

        for process in viewers + [writer]:
            process.start()
        ready.set()                       # release them all at once
        for process in viewers + [writer]:
            process.join(timeout=120)

        results = []
        while not done.empty():
            results.append(done.get())
        written = next((r for r in results if isinstance(r, list)), [])
        self.assertEqual(len(written), 8, "the writer did not complete")

        surviving = {case["id"] for case in self.store.get(_PROJECT).cases}
        lost = [case_id for case_id in written if case_id not in surviving]
        self.assertEqual(lost, [],
                         "a page view reverted %d governed write(s)" % len(lost))

    def test_the_seed_case_is_never_lost_under_pure_view_traffic(self):
        seed = {case["id"] for case in self.store.get(_PROJECT).cases}
        ready = multiprocessing.Event()
        done = multiprocessing.Queue()
        viewers = [
            multiprocessing.Process(target=_view_storm,
                                    args=(self.dir, _PROJECT, "viewer-%d" % i, 60,
                                          ready, done))
            for i in range(4)
        ]
        for process in viewers:
            process.start()
        ready.set()
        for process in viewers:
            process.join(timeout=120)
        self.assertEqual({case["id"] for case in self.store.get(_PROJECT).cases}, seed)

    def test_the_version_counter_is_never_rolled_back_by_a_view(self):
        version_before = self.raw()["version"]
        ready = multiprocessing.Event()
        done = multiprocessing.Queue()
        viewers = [
            multiprocessing.Process(target=_view_storm,
                                    args=(self.dir, _PROJECT, "viewer-%d" % i, 30,
                                          ready, done))
            for i in range(3)
        ]
        for process in viewers:
            process.start()
        ready.set()
        for process in viewers:
            process.join(timeout=120)
        self.assertGreaterEqual(self.raw()["version"], version_before)


class TheWriteMethodsCannotReachTheDocument(unittest.TestCase):
    """Asserted from source, so a future edit cannot quietly reintroduce it."""

    def test_neither_view_writer_writes_the_workspace_file(self):
        import inspect

        from services.case_workspace import CaseWorkspaceStore as Store

        for name in ("record_last_viewed", "record_item_reviewed"):
            source = inspect.getsource(getattr(Store, name))
            body = "\n".join(line for line in source.splitlines()
                             if not line.strip().startswith("#"))
            for reach in ("json.loads(path.read_text", "tmp_path.replace(path)",
                          "self.save("):
                self.assertNotIn(reach, body,
                                 "%s can still write the evidence document" % name)

    def test_both_go_through_the_one_sidecar_write_path(self):
        import inspect

        from services.case_workspace import CaseWorkspaceStore as Store

        for name in ("record_last_viewed", "record_item_reviewed"):
            self.assertIn("_patch_view_state",
                          inspect.getsource(getattr(Store, name)))


if __name__ == "__main__":
    unittest.main()
