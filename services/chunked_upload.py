"""
CLAUDE-CHUNKED-UPLOAD-01 - staging for uploads too large to arrive in one request.

WHY THIS EXISTS

A drawing set is routinely larger than one HTTP request can carry here. Three
separate ceilings apply, and they are not the ones people assume:

    Flask MAX_CONTENT_LENGTH   25 MB   (MAX_UPLOAD_MB, config.py) <- the real one
    nginx client_max_body_size 60 MB   (deploy/nginx.conf)
    gunicorn timeout          150 s    (deploy/gunicorn.conf.py)

The binding limit is Flask's 25 MB, not nginx's 60. Raising all three would be
two lines of config and is a legitimate alternative - but it does not survive a
dropped connection at 90% of a 400 MB transfer, and it holds the whole body in a
`gthread` worker for the duration. Chunking gives per-chunk retry and bounded
worker occupancy, which raising a limit does not.

WHERE THE CHUNKS LIVE, AND WHY NOT /tmp

Under REGISTRY_STORE_PATH, not /tmp. This is not a preference; it is the
conclusion this repository already reached and wrote down:

  - services/bridge_queue.py records Phase 2 discovering that state landing in
    one of fifteen gunicorn workers is invisible to the other fourteen, which
    "presents as intermittent rather than broken - the worst way for something to
    be wrong." Its fix was the filesystem under REGISTRY_STORE_PATH.
  - deploy/gunicorn.service sets PrivateTmp=true, so /tmp is a per-service
    namespace that is discarded on restart. A deploy mid-upload would silently
    take every in-flight chunk with it.
  - services/ingestion.PendingReconcileStore already stages raw upload bytes
    there with a 24-hour expiry sweep, so temporary byte staging with an explicit
    lifecycle is an established, sanctioned pattern here rather than a new one.

WHY NOT SIMPLY EXTEND PendingReconcileStore

It was examined first (CLAUDE.md requires that before adding an abstraction).
Its `create()` takes the COMPLETE bytes of every file up front and writes its
manifest once. Chunked upload is the opposite lifecycle: fragments arrive across
many independent requests, and no manifest can be complete until the last one
lands. Turning a create-once store into an incremental one would complicate a
store whose current simplicity is what makes it verifiable. The PATTERN is
reused - directory under REGISTRY_STORE_PATH, JSON manifest, TTL sweep, the same
24 hours - the contract is not.

THE ISOLATION PROPERTY

An upload is bound to one project at its first chunk, and every later chunk and
the finalize step must present the same project_id. A second project cannot
append to, complete, or read another project's staged upload - not because a
check refuses it, but because the manifest records the owner and every entry
point re-derives the directory from a validated id. Cross-project reach is not
refused; it is inexpressible.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from werkzeug.utils import secure_filename

STAGING_SUBDIR = "pending_chunk_uploads"
# The same 24 hours PendingReconcileStore already uses. Deliberately not a new
# number: two staging areas with two different lifetimes is a thing to explain
# forever, for no benefit.
STAGING_TTL_SECONDS = 24 * 60 * 60

# An upload id is server-shaped, never a path fragment. 32 lowercase hex
# characters and nothing else - so "..", "/", a Windows drive letter and a NUL
# are all rejected by the same rule rather than by a list of things to strip.
_UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{32}$")

MAX_CHUNKS = 4096
MAX_CHUNK_BYTES = 16 * 1024 * 1024


class ChunkedUploadError(RuntimeError):
    """Any refusal. Carries no filesystem paths - callers surface this to a
    browser, and a staging path is not something a client needs or should see."""


def new_upload_id() -> str:
    return uuid.uuid4().hex


def _validate_upload_id(upload_id: str) -> str:
    if not isinstance(upload_id, str) or not _UPLOAD_ID_RE.match(upload_id):
        raise ChunkedUploadError("invalid upload id")
    return upload_id


def _validate_index(chunk_index, total_chunks) -> tuple[int, int]:
    try:
        index = int(chunk_index)
        total = int(total_chunks)
    except (TypeError, ValueError):
        raise ChunkedUploadError("chunk index and total must be integers")
    if total < 1 or total > MAX_CHUNKS:
        raise ChunkedUploadError("total chunk count out of range")
    if index < 0 or index >= total:
        raise ChunkedUploadError("chunk index out of range")
    return index, total


class ChunkedUploadStore:
    """One directory per in-flight upload, one file per chunk, one manifest.

    Concurrency is handled the way bridge_queue handles it: two requests never
    write the same file. Each chunk is `<index>.part`, written to a unique temp
    name and renamed into place, so a retry of chunk 7 cannot interleave with the
    original chunk 7 and produce a half-written file that passes an existence
    check. CaseWorkspaceStore._save_lock is process-local and would protect
    nothing across fifteen workers.
    """

    def __init__(self, store_path):
        self.dir = Path(store_path) / STAGING_SUBDIR
        self.dir.mkdir(parents=True, exist_ok=True)

    # -- paths ------------------------------------------------------------

    def _upload_dir(self, upload_id: str) -> Path:
        return self.dir / _validate_upload_id(upload_id)

    def _manifest_path(self, upload_id: str) -> Path:
        return self._upload_dir(upload_id) / "manifest.json"

    # -- manifest ---------------------------------------------------------

    def _read_manifest(self, upload_id: str) -> Optional[dict]:
        path = self._manifest_path(upload_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A corrupt manifest is not recoverable and must not be treated as
            # "no upload yet", which would silently start a second one beside it.
            raise ChunkedUploadError("staged upload is unreadable")

    def _require_manifest(self, upload_id: str, project_id: str) -> dict:
        manifest = self._read_manifest(upload_id)
        if manifest is None:
            raise ChunkedUploadError("no such staged upload")
        if manifest.get("project_id") != project_id:
            # Same refusal text as "no such upload": telling a caller that an id
            # exists but belongs elsewhere is itself a disclosure.
            raise ChunkedUploadError("no such staged upload")
        return manifest

    # -- writing ----------------------------------------------------------

    def save_chunk(self, project_id: str, upload_id: str, chunk_index,
                   total_chunks, filename: str, data: bytes) -> dict:
        """Persist one chunk. Returns {received, total}."""
        if not project_id:
            raise ChunkedUploadError("project is required")
        if len(data) > MAX_CHUNK_BYTES:
            raise ChunkedUploadError("chunk is too large")
        if not data:
            raise ChunkedUploadError("chunk is empty")

        index, total = _validate_index(chunk_index, total_chunks)
        safe_name = secure_filename(filename or "")
        if not safe_name:
            raise ChunkedUploadError("invalid filename")

        upload_dir = self._upload_dir(upload_id)
        manifest = self._read_manifest(upload_id)

        if manifest is None:
            self._sweep_expired()
            upload_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "upload_id": upload_id,
                "project_id": project_id,
                "filename": safe_name,
                "total_chunks": total,
                "created_at": time.time(),
            }
            self._manifest_path(upload_id).write_text(
                json.dumps(manifest, indent=2), encoding="utf-8")
        else:
            manifest = self._require_manifest(upload_id, project_id)
            if manifest.get("total_chunks") != total:
                raise ChunkedUploadError("chunk count does not match this upload")
            if manifest.get("filename") != safe_name:
                raise ChunkedUploadError("filename does not match this upload")

        # Write-then-rename: a retried chunk must never be observable half
        # written, because assemble() only checks that each part EXISTS.
        temp = upload_dir / ("%d.%s.tmp" % (index, uuid.uuid4().hex))
        temp.write_bytes(data)
        temp.replace(upload_dir / ("%d.part" % index))

        return {"received": self.received_count(project_id, upload_id), "total": total}

    def received_count(self, project_id: str, upload_id: str) -> int:
        manifest = self._require_manifest(upload_id, project_id)
        upload_dir = self._upload_dir(upload_id)
        return sum(1 for i in range(manifest["total_chunks"])
                   if (upload_dir / ("%d.part" % i)).exists())

    def missing_chunks(self, project_id: str, upload_id: str) -> list:
        manifest = self._require_manifest(upload_id, project_id)
        upload_dir = self._upload_dir(upload_id)
        return [i for i in range(manifest["total_chunks"])
                if not (upload_dir / ("%d.part" % i)).exists()]

    # -- finalising -------------------------------------------------------

    def assemble(self, project_id: str, upload_id: str, filename: str,
                 total_chunks, destination: Path, max_total_bytes: int) -> dict:
        """Stream the parts into `destination`. Returns {sha256, size_bytes}.

        Streamed rather than concatenated in memory: the entire point is files
        too large to hold in one request, so holding one in one worker's heap at
        the final step would reintroduce the problem one line from the end.
        """
        _, total = _validate_index(0, total_chunks)
        manifest = self._require_manifest(upload_id, project_id)

        if manifest.get("total_chunks") != total:
            raise ChunkedUploadError("chunk count does not match this upload")
        safe_name = secure_filename(filename or "")
        if manifest.get("filename") != safe_name:
            raise ChunkedUploadError("filename does not match this upload")

        missing = self.missing_chunks(project_id, upload_id)
        if missing:
            preview = ", ".join(str(i) for i in missing[:8])
            more = "" if len(missing) <= 8 else " (and %d more)" % (len(missing) - 8)
            raise ChunkedUploadError("upload incomplete - missing chunk(s) %s%s"
                                     % (preview, more))

        upload_dir = self._upload_dir(upload_id)
        digest = hashlib.sha256()
        written = 0
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + ".assembling")

        try:
            with partial.open("wb") as out:
                for i in range(total):
                    part = upload_dir / ("%d.part" % i)
                    with part.open("rb") as chunk:
                        while True:
                            block = chunk.read(1024 * 1024)
                            if not block:
                                break
                            written += len(block)
                            if written > max_total_bytes:
                                raise ChunkedUploadError("assembled file is too large")
                            digest.update(block)
                            out.write(block)
            # Only a fully written, size-checked file gets the real name. A
            # consumer must never see a partially assembled Source.
            partial.replace(destination)
        except ChunkedUploadError:
            partial.unlink(missing_ok=True)
            raise
        except OSError as exc:
            partial.unlink(missing_ok=True)
            raise ChunkedUploadError("could not assemble upload: %s" % type(exc).__name__)

        return {"sha256": digest.hexdigest(), "size_bytes": written}

    def discard(self, upload_id: str) -> None:
        """Remove one staged upload. Safe to call twice."""
        try:
            shutil.rmtree(self._upload_dir(upload_id), ignore_errors=True)
        except ChunkedUploadError:
            # An invalid id has no directory to remove; nothing to do and
            # nothing to report.
            return

    # -- expiry -----------------------------------------------------------

    def _sweep_expired(self, now: Optional[float] = None) -> list:
        """Drop abandoned uploads. Called on the creation of a new one, matching
        PendingReconcileStore, so it needs no timer and cannot itself fail a
        request that is otherwise fine."""
        now = time.time() if now is None else now
        removed = []
        for child in self.dir.iterdir() if self.dir.exists() else []:
            if not child.is_dir():
                continue
            manifest = child / "manifest.json"
            try:
                created = json.loads(manifest.read_text(encoding="utf-8"))["created_at"]
            except (OSError, ValueError, KeyError, TypeError):
                # No readable manifest: fall back to the directory's own mtime so
                # a corrupt or interrupted upload is still eventually collected
                # rather than living forever.
                try:
                    created = child.stat().st_mtime
                except OSError:
                    continue
            if now - created > STAGING_TTL_SECONDS:
                shutil.rmtree(child, ignore_errors=True)
                removed.append(child.name)
        return removed

    def sweep_expired(self, now: Optional[float] = None) -> list:
        """Public entry point, for a maintenance caller or a test."""
        return self._sweep_expired(now)
