"""
SPIKE / CLAUDE-STATION-PRESENCE-01 - where the table is looking, readable by any worker.

THE HYDROLOGICAL POINT, WHICH IS ALSO THE ENGINEERING ONE

A follower needs the CURRENT, not every creek. Person A's phone joining a Glass
Box wants "where is the presenter looking now" - not a replay of every pan since
nine this morning. So this is deliberately NOT an event log, a queue, or a
journal. It is one small last-write-wins document per station, with a monotonic
revision so a poller can ask "anything since 41?" and be told no cheaply.

That choice removes an entire class of problem before it exists: no retention
policy, no compaction, no replay semantics, no ordering guarantees across
publishers, and nothing to sweep. A basin that never fills cannot stagnate - and
this session has already found one pool on production that does.

WHY THE FILESYSTEM, AGAIN

Because a module-level dict is wrong for exactly the reason it was wrong twice
already this session: production runs fifteen gunicorn worker processes. A
viewport published in worker 7 must be visible to a phone polling worker 3, and
in-memory state made the storage bridge's manifest visible to roughly one request
in fifteen - which reads as intermittent rather than broken.

TRANSPORT-AGNOSTIC ON PURPOSE

Nothing here knows about SSE, polling, or websockets. `read_since(station_id,
revision)` answers the only question any transport needs to ask, so the choice of
transport is a deployment question rather than an architectural one. That matters
concretely: SSE against this deployment needs `proxy_buffering off` in nginx
(absent today, so events would sit in nginx's buffer and never stream) AND holds
one of only 60 gthread request slots for the life of each stream. Polling needs
neither. The bus does not care which arrives first.

WHAT THIS IS NOT

Not authorisation. A viewport says which coordinate a surface is showing; it
never says who may see the project. can_access_project remains the gatekeeper for
every participant, and nothing in this module consults or affects it.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

_PRESENCE_SUBDIR = "_station_presence"

# A station nobody has touched in this long is not presenting. Long enough to
# survive a presenter reading a drawing without moving; short enough that a
# packed-up table stops claiming an audience.
DEFAULT_STALE_AFTER_SECONDS = 300


class PresenceBus:
    """One last-write-wins viewport per station. No history, by design."""

    def __init__(self, store_path: str | Path,
                 stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS):
        self.root = Path(store_path) / _PRESENCE_SUBDIR
        self.root.mkdir(parents=True, exist_ok=True)
        self.stale_after = stale_after_seconds

    def _path(self, station_id: str) -> Path:
        return self.root / ("%s.json" % station_id)

    # -- publish -----------------------------------------------------------
    def publish(self, station_id: str, viewport: dict, *,
                published_by: str = "station", now: Optional[float] = None) -> dict:
        """Replace the station's current viewport. Never appends.

        The revision is monotonic per station so a follower can poll cheaply.
        A lost update here is not merely tolerable, it is CORRECT: if two
        publishes race, the later view of the drawing is the one a follower
        wants, and reconstructing an intermediate pan nobody is looking at any
        more would be worse than dropping it.
        """
        path = self._path(station_id)
        current = self.read(station_id) or {}
        record = {
            "station_id": station_id,
            "revision": int(current.get("revision") or 0) + 1,
            "viewport": viewport,
            "published_by": published_by,
            "published_at": now if now is not None else time.time(),
        }
        tmp = path.with_name(path.name + ".tmp-%s" % uuid.uuid4().hex)
        tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
        _replace_with_retry(tmp, path)
        return record

    # -- read --------------------------------------------------------------
    def read(self, station_id: str) -> Optional[dict]:
        try:
            return json.loads(self._path(station_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Absent or caught mid-write. A follower asking again in half a
            # second is the correct recovery, not an exception on a poll.
            return None

    def read_since(self, station_id: str, revision: int, *,
                   now: Optional[float] = None) -> Optional[dict]:
        """The whole transport contract, in one call.

        Returns None when there is nothing new - which a poller answers with 204
        and an SSE loop answers by not writing a frame. Neither needs to know
        anything else about the other.
        """
        record = self.read(station_id)
        if record is None:
            return None
        if int(record.get("revision") or 0) <= int(revision):
            return None
        if self.is_stale(record, now=now):
            return None
        return record

    def is_stale(self, record: dict, *, now: Optional[float] = None) -> bool:
        moment = now if now is not None else time.time()
        return (moment - float(record.get("published_at") or 0)) > self.stale_after

    def clear(self, station_id: str) -> None:
        """Unmounting a station must not leave it presenting a coordinate into
        a project it no longer holds."""
        self._path(station_id).unlink(missing_ok=True)


def _replace_with_retry(tmp_path: Path, target: Path, attempts: int = 40) -> None:
    """Same primitive services/case_workspace.py settled on, same reason.

    rename(2) on Linux replaces a destination another process is reading; Windows
    refuses while a handle is open, which is invisible in production and bites a
    developer running several processes. Retrying preserves atomicity and only
    waits for a reader to finish.
    """
    for attempt in range(attempts):
        try:
            os.replace(tmp_path, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.01 * (attempt + 1))
