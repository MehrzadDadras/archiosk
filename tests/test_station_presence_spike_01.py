"""
SPIKE / CLAUDE-STATION-01 + PRESENCE-01 - "the project is mounted; people join it."

WHAT IS BEING PROVEN, AND WHAT IS DELIBERATELY NOT

Proven: a station holds ONE mounted project, re-pointing it does not destroy its
identity, joining tells a companion which project the surface shows WITHOUT
granting access to it, and viewport state is visible to any worker.

Not proven, because it is not built: any UI, any transport, any route. The
transport question is deliberately left open - see the note on SSE below - and
the bus answers `read_since()` identically whichever way the answer travels.

THE SECURITY ASSERTION THAT MATTERS MOST

join_station returns the mounted project id and nothing else. If joining ever
became an entitlement, walking up to a Glass Box with any valid login would be a
route into a project you were never granted. So this file asserts, at source
level, that services/station.py never imports or calls can_access_project - not
because checking would be wrong, but because a module that SOMETIMES grants
access is far worse than one that never can, and the absence is the guarantee.

ON SSE, MEASURED RATHER THAN ASSUMED

This deployment runs 15 gunicorn workers x 4 gthread threads = 60 request slots,
and gthread holds a thread for a request's LIFETIME. Sixty concurrent SSE streams
would exhaust the pool and the whole site would stop serving. nginx also has no
proxy_buffering directive, so it buffers proxied responses by default and SSE
frames would never leave the buffer at all.

Both are real, both were measured on the live host, and neither is a reason to
change this bus - which is why the bus knows nothing about transport.
"""
from __future__ import annotations

import inspect
import multiprocessing
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.presence_bus import PresenceBus
from services.station import (
    StationNotAuthorised,
    StationNotMounted,
    authorise_station,
    enrol_station,
    join_station,
    mount_project,
    mounted_project_for,
    unmount,
)

_PROJECT_A = "project-alpha"
_PROJECT_B = "project-beta"


def _executable_source(module) -> str:
    """The module's CODE, with every docstring and comment removed.

    Written because two assertions in this file first failed on their own
    explanatory prose: the docstrings legitimately discuss `can_access_project`
    and `websocket` while the code touches neither. A line-prefix filter does not
    catch a multi-line docstring, and asking a question about behaviour by
    grepping text answers a different question than the one intended.

    ast.unparse drops comments outright; the walk below removes docstring
    expressions, leaving only statements that actually run.
    """
    import ast

    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(body, list) and body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body.pop(0)
    return ast.unparse(tree)


def _publish_in_subprocess(store_path, station_id, ready, done):
    """A REAL separate process - the stand-in for another gunicorn worker."""
    bus = PresenceBus(store_path)
    ready.wait(timeout=30)
    bus.publish(station_id, {"sheet": "A-201", "level": 2}, published_by="table")
    done.put(bus.read(station_id)["revision"])


class _Stations(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import db

        self.dir = tempfile.mkdtemp(prefix="station-spike-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = self.dir
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        db.create_all()
        self.station, self.token = enrol_station("glass-box-site-1", actor="architect")


class AStationMountsExactlyOneProject(_Stations):
    def test_a_new_station_is_enrolled_with_nothing_mounted(self):
        # A Glass Box out of the box is hardware, not a job.
        self.assertIsNone(self.station.mounted_project_id)
        with self.assertRaises(StationNotMounted):
            mounted_project_for(self.token)

    def test_mounting_binds_the_surface_to_one_project(self):
        mount_project(self.token, _PROJECT_A, actor="architect")
        self.assertEqual(mounted_project_for(self.token), _PROJECT_A)

    def test_there_is_no_call_that_reads_a_project_by_id(self):
        # The mount IS the absence of a switcher. Only mount_project may name a
        # project, because naming one is the whole point of mounting.
        import services.station as module

        for name, function in inspect.getmembers(module, inspect.isfunction):
            if name in ("mount_project",) or name.startswith("_"):
                continue
            self.assertNotIn(
                "project_id", set(inspect.signature(function).parameters),
                "%s exposes a project_id route around the mount" % name)

    def test_remounting_changes_the_job_not_the_station(self):
        mount_project(self.token, _PROJECT_A, actor="architect")
        identity = (self.station.id, self.station.token_hash, self.station.label)
        result = mount_project(self.token, _PROJECT_B, actor="architect")
        self.assertEqual(result["previous_project_id"], _PROJECT_A)
        self.assertEqual(mounted_project_for(self.token), _PROJECT_B)
        self.assertEqual((self.station.id, self.station.token_hash,
                          self.station.label), identity)

    def test_the_same_token_still_works_after_remounting(self):
        # The deviation from StorageAgentEnrolment: re-pointing a table must not
        # invalidate every companion pairing with it.
        mount_project(self.token, _PROJECT_A, actor="architect")
        mount_project(self.token, _PROJECT_B, actor="architect")
        self.assertEqual(authorise_station(self.token).label, "glass-box-site-1")

    def test_unmounting_releases_the_job_and_keeps_the_station(self):
        mount_project(self.token, _PROJECT_A, actor="architect")
        self.assertEqual(unmount(self.token, actor="architect"), _PROJECT_A)
        self.assertEqual(authorise_station(self.token).label, "glass-box-site-1")
        with self.assertRaises(StationNotMounted):
            mounted_project_for(self.token)


class JoiningGrantsNothing(_Stations):
    """The security boundary. Everything else here is convenience."""

    def test_joining_returns_the_project_and_says_it_grants_nothing(self):
        mount_project(self.token, _PROJECT_A, actor="architect")
        joined = join_station(self.token)
        self.assertEqual(joined["mounted_project_id"], _PROJECT_A)
        self.assertIs(joined["grants_access"], False)

    def test_the_station_module_cannot_grant_project_access(self):
        # Asserted as an ABSENCE. A module that sometimes checks access is worse
        # than one that never can - the second cannot be misread as an
        # entitlement by whoever writes the next caller.
        import services.station as module

        code = _executable_source(module)
        for granting in ("can_access_project", "project_access", "load_authorized",
                         "grant_project_access", "access_allow_list"):
            self.assertNotIn(granting, code)

    def test_joining_never_loads_project_data(self):
        import services.station as module

        code = _executable_source(module)
        for reach in ("CaseWorkspaceStore", "workspace.sources", "get_or_create"):
            self.assertNotIn(reach, code)

    def test_an_unmounted_station_cannot_be_joined(self):
        with self.assertRaises(StationNotMounted):
            join_station(self.token)

    def test_unknown_revoked_and_expired_are_refused_identically(self):
        # Distinguishing them would confirm a station exists to someone holding
        # no valid credential.
        from models import db

        messages = []
        try:
            authorise_station("not-a-real-token")
        except StationNotAuthorised as exc:
            messages.append(str(exc))
        self.station.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()
        try:
            authorise_station(self.token)
        except StationNotAuthorised as exc:
            messages.append(str(exc))
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0], messages[1])

    def test_not_mounted_is_a_different_answer_from_not_authorised(self):
        # Different human action: one needs a credential, the other needs an
        # administrator to mount a job.
        self.assertFalse(issubclass(StationNotMounted, StationNotAuthorised))
        self.assertFalse(issubclass(StationNotAuthorised, StationNotMounted))


class PresenceIsTheCurrentNotTheHistory(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="presence-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.bus = PresenceBus(self.dir)

    def test_publishing_replaces_rather_than_appends(self):
        for level in (1, 2, 3):
            self.bus.publish("station-1", {"sheet": "A-201", "level": level})
        record = self.bus.read("station-1")
        self.assertEqual(record["viewport"]["level"], 3)
        self.assertEqual(record["revision"], 3)
        # One document per station. A follower wants the current, not every pan.
        self.assertEqual(len(list(Path(self.dir).rglob("*.json"))), 1)

    def test_a_follower_is_told_nothing_when_nothing_changed(self):
        published = self.bus.publish("station-1", {"sheet": "A-201"})
        self.assertIsNone(self.bus.read_since("station-1", published["revision"]))

    def test_a_follower_gets_the_current_view_when_it_moves(self):
        first = self.bus.publish("station-1", {"sheet": "A-201"})
        self.bus.publish("station-1", {"sheet": "A-202"})
        fresh = self.bus.read_since("station-1", first["revision"])
        self.assertEqual(fresh["viewport"]["sheet"], "A-202")

    def test_a_stale_station_stops_presenting(self):
        bus = PresenceBus(self.dir, stale_after_seconds=60)
        bus.publish("station-1", {"sheet": "A-201"}, now=1000.0)
        self.assertIsNotNone(bus.read_since("station-1", 0, now=1000.0 + 59))
        self.assertIsNone(bus.read_since("station-1", 0, now=1000.0 + 61))

    def test_unmounting_clears_the_broadcast(self):
        self.bus.publish("station-1", {"sheet": "A-201"})
        self.bus.clear("station-1")
        self.assertIsNone(self.bus.read("station-1"))

    def test_stations_do_not_see_each_other(self):
        self.bus.publish("station-1", {"sheet": "A-201"})
        self.bus.publish("station-2", {"sheet": "S-101"})
        self.assertEqual(self.bus.read("station-1")["viewport"]["sheet"], "A-201")
        self.assertEqual(self.bus.read("station-2")["viewport"]["sheet"], "S-101")

    def test_there_is_nothing_to_sweep(self):
        # A basin that never fills cannot stagnate. Contrast pending_reconciles/,
        # which holds nine-day-old files against a 24h TTL because its sweep only
        # runs on inflow.
        for _ in range(50):
            self.bus.publish("station-1", {"sheet": "A-201"})
        self.assertEqual(len(list(Path(self.dir).rglob("*.json"))), 1)


class AnyWorkerSeesTheCurrentViewport(unittest.TestCase):
    """The bug this session already fixed twice, not repeated a third time."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="presence-mp-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def test_a_publish_in_one_process_is_visible_in_another(self):
        ready, done = multiprocessing.Event(), multiprocessing.Queue()
        worker = multiprocessing.Process(
            target=_publish_in_subprocess, args=(self.dir, "station-1", ready, done))
        worker.start()
        ready.set()
        worker.join(timeout=60)
        self.assertFalse(done.empty(), "the publishing process did not finish")
        # Read from a store constructed HERE, sharing nothing but the filesystem.
        record = PresenceBus(self.dir).read("station-1")
        self.assertIsNotNone(record)
        self.assertEqual(record["viewport"]["sheet"], "A-201")

    def test_no_module_level_state_backs_the_bus(self):
        import ast

        import services.presence_bus as module

        tree = ast.parse(inspect.getsource(module))
        mutable = [n for n in tree.body
                   if isinstance(n, (ast.Assign, ast.AnnAssign))
                   and isinstance(getattr(n, "value", None), (ast.Dict, ast.List, ast.Set))]
        self.assertEqual(mutable, [])

    def test_the_bus_knows_nothing_about_transport(self):
        # Transport is a deployment question, not an architectural one. SSE needs
        # nginx proxy_buffering off and holds one of 60 request slots per stream;
        # polling needs neither. The bus must not care.
        import services.presence_bus as module

        code = _executable_source(module)
        for transport in ("text/event-stream", "yield", "websocket", "Response("):
            self.assertNotIn(transport, code)


if __name__ == "__main__":
    unittest.main()
