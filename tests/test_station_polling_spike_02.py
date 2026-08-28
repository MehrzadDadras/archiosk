"""
SPIKE / CLAUDE-STATION-POLL-01 - the polling transport, over real HTTP.

WHY POLLING RATHER THAN SSE, IN NUMBERS

Measured on the live host, not assumed: 15 gunicorn workers x 4 gthread threads =
60 request slots, and gthread holds a thread for a request's LIFETIME. Sixty
concurrent SSE streams exhausts the pool and the entire site stops serving.
nginx carries no proxy_buffering directive, so it buffers proxied responses by
default and SSE frames would never leave the buffer at all.

A poll reads one small file and returns. A follower occupies a slot for roughly
1% of the time SSE would, needs no infrastructure change, and at ~500ms the lag
is imperceptible for what this is actually for - a phone tracking a table.

THE ASSERTION THAT MATTERS MOST

Joining a station must never become a way into a project. These routes compose
two independent decisions in the open:

    join_station(token)     -> WHICH project the surface shows (grants nothing)
    can_access_project(...) -> whether THIS PERSON may see it

A user with a perfectly valid station token and no project access gets 404 - the
same answer the ordinary URL gives, because a Glass Box is not a side door.
"""
from __future__ import annotations

import unittest

from services.station import enrol_station, mount_project, unmount

_PROJECT = "station-poll-project"


class _StationApp(unittest.TestCase):
    def setUp(self):
        import shutil
        import tempfile

        import app as app_module
        from models import User, db
        from services.case_workspace import CaseWorkspaceStore
        from werkzeug.security import generate_password_hash

        self.dir = tempfile.mkdtemp(prefix="station-poll-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = self.dir
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        db.create_all()

        db.session.add(User(username="owner",
                            password_hash=generate_password_hash("x"), role="user"))
        db.session.add(User(username="stranger",
                            password_hash=generate_password_hash("x"), role="user"))
        db.session.commit()

        store = CaseWorkspaceStore(self.dir)
        workspace = store.get_or_create(_PROJECT)
        store.set_project_owner(workspace, owner="owner", actor="admin")

        self.station, self.token = enrol_station("glass-box-1", actor="admin")
        mount_project(self.token, _PROJECT, actor="admin")
        self.client = self.app.test_client()

    def as_user(self, username, role="user"):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = username
            sess["role"] = role

    def auth(self, token=None):
        return {"Authorization": "Bearer %s" % (token or self.token)}


class ACompanionJoinsTheMountedProject(_StationApp):
    def test_a_permitted_user_learns_which_project_the_surface_shows(self):
        self.as_user("owner")
        response = self.client.get("/api/station/join", headers=self.auth())
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["mounted_project_id"], _PROJECT)
        self.assertEqual(body["station_label"], "glass-box-1")

    def test_the_response_says_plainly_that_it_grants_nothing(self):
        self.as_user("owner")
        body = self.client.get("/api/station/join", headers=self.auth()).get_json()
        self.assertIs(body["grants_access"], False)

    def test_the_poll_cadence_is_server_controlled(self):
        # Advertised rather than hard-coded client-side, so backing off under
        # load never requires shipping a client.
        self.as_user("owner")
        body = self.client.get("/api/station/join", headers=self.auth()).get_json()
        self.assertEqual(body["poll_interval_ms"], 500)


class JoiningIsNotAWayIn(_StationApp):
    """The security boundary these routes exist to compose."""

    def test_a_valid_station_token_does_not_admit_a_stranger(self):
        # The whole point: walking up to a Glass Box with a real login and a
        # real station credential still requires project access.
        self.as_user("stranger")
        response = self.client.get("/api/station/join", headers=self.auth())
        self.assertEqual(response.status_code, 404)

    def test_the_refusal_does_not_confirm_the_project_exists(self):
        self.as_user("stranger")
        body = self.client.get("/api/station/join", headers=self.auth()).get_json()
        self.assertNotIn(_PROJECT, str(body))

    def test_a_stranger_cannot_follow_the_viewport_either(self):
        self.client.post("/api/station/viewport", headers=self.auth(),
                         json={"viewport": {"sheet": "A-201"}})
        self.as_user("stranger")
        response = self.client.get("/api/station/viewport?since=0", headers=self.auth())
        self.assertEqual(response.status_code, 404)

    def test_no_station_token_is_refused_401(self):
        self.as_user("owner")
        self.assertEqual(self.client.get("/api/station/join").status_code, 401)

    def test_a_wrong_station_token_is_refused_401(self):
        self.as_user("owner")
        response = self.client.get("/api/station/join",
                                   headers=self.auth("not-a-real-token"))
        self.assertEqual(response.status_code, 401)

    def test_a_token_in_the_query_string_does_not_work(self):
        self.as_user("owner")
        response = self.client.get("/api/station/join?token=%s" % self.token)
        self.assertEqual(response.status_code, 401)


class FollowingIsCheapAndCurrent(_StationApp):
    def test_publishing_then_polling_returns_the_current_view(self):
        self.client.post("/api/station/viewport", headers=self.auth(),
                         json={"viewport": {"sheet": "A-201", "level": 2}})
        self.as_user("owner")
        response = self.client.get("/api/station/viewport?since=0", headers=self.auth())
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["viewport"], {"sheet": "A-201", "level": 2})
        self.assertEqual(body["revision"], 1)

    def test_an_unchanged_view_answers_204_with_no_body(self):
        # The common case, and the reason polling is cheap.
        self.client.post("/api/station/viewport", headers=self.auth(),
                         json={"viewport": {"sheet": "A-201"}})
        self.as_user("owner")
        response = self.client.get("/api/station/viewport?since=1", headers=self.auth())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.get_data(), b"")
        self.assertEqual(response.headers["X-Poll-Interval-Ms"], "500")

    def test_a_follower_gets_the_latest_not_the_backlog(self):
        # Three pans, one answer: the current view. A follower wants the river,
        # not every creek that fed it.
        for sheet in ("A-201", "A-202", "A-203"):
            self.client.post("/api/station/viewport", headers=self.auth(),
                             json={"viewport": {"sheet": sheet}})
        self.as_user("owner")
        body = self.client.get("/api/station/viewport?since=0",
                               headers=self.auth()).get_json()
        self.assertEqual(body["viewport"]["sheet"], "A-203")
        self.assertEqual(body["revision"], 3)

    def test_a_malformed_since_is_treated_as_zero_not_an_error(self):
        self.client.post("/api/station/viewport", headers=self.auth(),
                         json={"viewport": {"sheet": "A-201"}})
        self.as_user("owner")
        response = self.client.get("/api/station/viewport?since=banana",
                                   headers=self.auth())
        self.assertEqual(response.status_code, 200)


class OnlyTheStationPublishes(_StationApp):
    def test_a_viewport_must_be_an_object(self):
        response = self.client.post("/api/station/viewport", headers=self.auth(),
                                    json={"viewport": "A-201"})
        self.assertEqual(response.status_code, 400)

    def test_an_oversized_viewport_is_refused(self):
        response = self.client.post(
            "/api/station/viewport", headers=self.auth(),
            json={"viewport": {"blob": "x" * 5000}})
        self.assertEqual(response.status_code, 413)

    def test_publishing_without_a_station_token_is_refused(self):
        self.as_user("owner")
        response = self.client.post("/api/station/viewport",
                                    json={"viewport": {"sheet": "A-201"}})
        self.assertEqual(response.status_code, 401)


class AnUnmountedStationIsItsOwnAnswer(_StationApp):
    def test_it_is_409_not_401_and_not_404(self):
        # A real station waiting for an administrator is neither an
        # authorisation failure nor a missing thing. Answering 401 would send
        # someone to fetch a credential they already have.
        unmount(self.token, actor="admin")
        self.as_user("owner")
        response = self.client.get("/api/station/join", headers=self.auth())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "station_not_mounted")

    def test_remounting_moves_every_companion_at_once(self):
        # The mount is the context. Changing it changes what all joined devices
        # are looking at, which is the point of mounting rather than navigating.
        second = "station-poll-project-two"
        from services.case_workspace import CaseWorkspaceStore

        store = CaseWorkspaceStore(self.dir)
        workspace = store.get_or_create(second)
        store.set_project_owner(workspace, owner="owner", actor="admin")

        self.as_user("owner")
        self.assertEqual(
            self.client.get("/api/station/join",
                            headers=self.auth()).get_json()["mounted_project_id"],
            _PROJECT)
        mount_project(self.token, second, actor="admin")
        self.assertEqual(
            self.client.get("/api/station/join",
                            headers=self.auth()).get_json()["mounted_project_id"],
            second)


class ACompanionDisturbsWithoutSteeringTheTable(_StationApp):
    """The asymmetry, which is a product decision before it is a technical one."""

    def test_a_companion_can_point_at_something(self):
        self.as_user("owner")
        response = self.client.post("/api/station/focus", headers=self.auth(),
                                    json={"focus": {"element": "D-101", "note": "rating?"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["author"], "owner")

    def test_the_disturbance_does_not_move_the_camera(self):
        # The whole point. People are physically standing at that table.
        self.client.post("/api/station/viewport", headers=self.auth(),
                         json={"viewport": {"sheet": "A-201", "zoom": 1.0}})
        # The session must be established BEFORE the first poll: following is
        # gated by can_access_project, so an unauthenticated read is a 404 with
        # no viewport in it at all.
        self.as_user("owner")
        before = self.client.get("/api/station/viewport?since=0",
                                 headers=self.auth()).get_json()
        self.client.post("/api/station/focus", headers=self.auth(),
                         json={"focus": {"element": "D-101"}})
        after = self.client.get("/api/station/viewport?since=0",
                                headers=self.auth()).get_json()
        self.assertEqual(after["viewport"], before["viewport"])
        self.assertEqual(after["revision"], before["revision"])

    def test_the_station_sees_what_everyone_is_pointing_at(self):
        self.as_user("owner")
        self.client.post("/api/station/focus", headers=self.auth(),
                         json={"focus": {"element": "D-101"}})
        response = self.client.get("/api/station/focus?since=0", headers=self.auth())
        self.assertEqual(response.status_code, 200)
        disturbances = response.get_json()["disturbances"]
        self.assertEqual(len(disturbances), 1)
        self.assertEqual(disturbances[0]["focus"]["element"], "D-101")

    def test_one_entry_per_author_keeps_it_bounded(self):
        # Twenty taps from one phone is one pin, not twenty. Bounded by the
        # number of people at the table, not the length of the meeting.
        self.as_user("owner")
        for n in range(20):
            self.client.post("/api/station/focus", headers=self.auth(),
                             json={"focus": {"element": "D-%d" % n}})
        disturbances = self.client.get("/api/station/focus?since=0",
                                       headers=self.auth()).get_json()["disturbances"]
        self.assertEqual(len(disturbances), 1)
        self.assertEqual(disturbances[0]["focus"]["element"], "D-19")

    def test_nothing_new_answers_204(self):
        self.as_user("owner")
        response = self.client.get("/api/station/focus?since=0", headers=self.auth())
        self.assertEqual(response.status_code, 204)

    def test_a_stranger_cannot_disturb_the_table(self):
        self.as_user("stranger")
        response = self.client.post("/api/station/focus", headers=self.auth(),
                                    json={"focus": {"element": "D-101"}})
        self.assertEqual(response.status_code, 404)

    def test_an_anonymous_caller_cannot_disturb_the_table(self):
        # A disturbance is attributed. There is no such thing as an anonymous
        # pin on a shared surface.
        response = self.client.post("/api/station/focus", headers=self.auth(),
                                    json={"focus": {"element": "D-101"}})
        self.assertEqual(response.status_code, 404)

    def test_the_focus_route_has_no_path_to_the_viewport(self):
        # Enforced structurally, not by convention: a companion endpoint that
        # could reach publish() would be one edit away from hijacking the table.
        import ast
        import inspect

        import routes.station as module

        tree = ast.parse(inspect.getsource(module))
        target = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and n.name == "publish_focus")
        called = {getattr(c.func, "attr", None) for c in ast.walk(target)
                  if isinstance(c, ast.Call)}
        self.assertIn("publish_focus", called)
        self.assertNotIn("publish", called)


class TheTransportStaysOutOfTheBus(unittest.TestCase):
    def test_no_long_lived_streaming_was_introduced(self):
        # This iteration must not hold a gthread slot open: 60 of them exist in
        # production, and SSE would hold one per follower for its lifetime.
        import inspect

        import routes.station as module

        code = inspect.getsource(module)
        body = "\n".join(line for line in code.splitlines()
                         if "#" not in line.split('"')[0])
        for streaming in ("text/event-stream", "stream_with_context", "while True"):
            self.assertNotIn(streaming, body)

    def test_the_bus_still_knows_nothing_about_http(self):
        import ast
        import inspect

        import services.presence_bus as module

        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if (isinstance(body, list) and body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body.pop(0)
        code = ast.unparse(tree)
        for http in ("jsonify", "request", "Blueprint", "Response"):
            self.assertNotIn(http, code)


if __name__ == "__main__":
    unittest.main()
