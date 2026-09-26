"""MORPHOSIS SLICE 1 - the Sandbox: a clean, exploratory Gopilot start.

A person can start with Gopilot before they know what kind of work this is.
They say what they are trying to do; Gopilot reflects it back, organizes it
(known facts, unknowns, constraints, next questions), says whether the outside
world should be checked, and RECOMMENDS a landing. Nothing governed is created
until the person accepts one.

NON-CANONICAL BY CONSTRUCTION. A Sandbox is provisional scratch, not project
data: it lives under REGISTRY_STORE_PATH/sandbox/, outside every project's own
store, so no project retrieval, evidence gathering or register ever reads it.
Nothing in it is evidence, a finding, an authority claim or a project record.
It becomes governed work only through an accepted landing, and the landing
carries its origin (lineage) with it.

WHY A STORE AND NOT THE SESSION. Sessions here are signed cookies (~4KB). A
structured, multi-turn Sandbox does not fit, and truncating it silently would
lose the lineage a promotion must carry. One small JSON file per user, holding
that user's current Sandbox, is the minimum that works.

THE MODEL ORGANIZES; IT NEVER DECIDES. The organization text may come from the
model (behind the project-less external-AI policy gate) or from a deterministic
fallback. Whether the outside world should be checked, and which landing is
recommended, are decided HERE, deterministically - a model's opinion never
recommends governed work. This slice supports one landing: NEW PLANNING STUDY.

LIQUID SANDBOX - OBJECT FIELD v0. What a person gives the Sandbox becomes a
provisional SandboxObject: each typed statement a `note`, each accepted image an
`image` whose bytes are RETAINED (SANDBOX_MEDIA_PATH/<owner>/), so it can be seen
again and selected later. Objects are the field; turns are one sensor feeding it.
Selecting objects sends them to Gopilot as bounded context for the next turn -
GOV-P-001: selection supplies context, never permission. The host resolves every
selected id against the owner's own record; anything else is ignored. Caps REFUSE
overflow; nothing is silently truncated. No canvas, groups, relationships or
promotion changes in v0: lineage() is unchanged.

Object envelopes retain their Sandbox-local id, owner, creation order and time,
primitive type and explicit modality. Arrival describes observed Composer input,
not verified authorship; older or unobserved arrival remains unknown. Selected
context carries these same identities and binds image numbers only to bytes
actually supplied through the existing model gateway.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

LANDING_PLANNING_STUDY = "planning_study"
DECISION_CONTINUE = "continue"
DECISION_EXISTING_PROJECT = "existing_project"
DECISION_NEW_PROJECT = "new_project"
_LIST_CAP = 6
_ITEM_CAP = 240

# The planning/permit vocabulary that makes a Planning Study the right landing.
# Deliberately about the WORK (permission to build, zoning, approvals), not
# about any one municipality.
_PLANNING_TERMS = (
    "permit", "zoning", "zone", "by-law", "bylaw", "variance", "committee of adjustment",
    "site plan", "rezoning", "severance", "setback", "planning approval", "official plan",
    "building department", "approval to build", "planning study",
)

PLANNING_STUDY_WHY = (
    "The objective is clear, but jurisdiction, submission requirements, drawing readiness "
    "and professional responsibilities still need to be established."
)
EXTERNAL_WHY = (
    "Permit and planning requirements are set by the local authority and change over time. "
    "Check the current process for the property's municipality before relying on any summary. "
    "Nothing is looked up until you choose to start that research."
)


# -- LIQUID SANDBOX object field v0: caps (each REFUSES overflow, never truncates) --
MAX_TURNS = 40
MAX_OBJECTS = 80
MAX_MEDIA_OBJECTS = 12
MAX_MEDIA_BYTES = 30 * 1024 * 1024          # retained per Sandbox
MAX_SELECTION = 8                           # objects per turn, as Gopilot context
MAX_SELECTED_IMAGES = 3                     # images among them sent to the model
_CONTEXT_TEXT_CAP = 600                     # characters of one selected note

OBJECT_NOTE = "note"
OBJECT_IMAGE = "image"
_MEDIA_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}


class SandboxRefused(Exception):
    """A cap or selection rule refused the turn. Nothing was stored or sent."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_object(kind: str, *, turn: int, sensor: str, content: dict) -> dict:
    return {
        "id": uuid.uuid4().hex, "type": kind,
        "origin": {"sensor": sensor, "turn": turn},
        "created_by": "person", "created_at": _now(),
        "status": "provisional", "canonical": False,
        "content": content,
    }


def _object_envelopes(record: dict) -> dict:
    """Complete older envelopes without replacing identities or inventing arrival
    history. Scope and order come from the owning store, never the request."""
    for sequence, obj in enumerate(record.get("objects") or []):
        obj["sandbox_id"] = record["id"]
        obj["owner"] = record["owner"]
        obj["sequence"] = sequence
        obj["modality"] = "image" if obj["type"] == OBJECT_IMAGE else "text"
        obj["origin"].setdefault("arrival", "unknown")
    return record


def arrival(value, kind: str) -> str:
    """Client-observed intake provenance is descriptive, never authority."""
    allowed = {"typed", "pasted", "mixed"} if kind == OBJECT_NOTE else {"pasted", "uploaded"}
    return value if isinstance(value, str) and value in allowed else "unknown"


def _project_legacy_objects(record: dict) -> dict:
    """A Sandbox from before the object field: project its turns and attachment
    identities into objects. Its images were never retained, and say so."""
    if "objects" in record:
        return _object_envelopes(record)
    objects = []

    def stable(obj, n):
        # Reads never write, so a projected id must be the same on every read -
        # or a selection made on one page could never be resolved on the next.
        seed = "%s:%s:%s:%s" % (record.get("id"), obj["origin"]["turn"], obj["type"], n)
        obj["id"] = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
        obj["created_at"] = record.get("created_at")
        return obj

    for index, turn in enumerate(record.get("turns") or []):
        if (turn.get("text") or "").strip():
            objects.append(stable(_new_object(OBJECT_NOTE, turn=index, sensor="composer_text",
                                              content={"text": turn["text"]}), 0))
        for n, att in enumerate((turn.get("reply") or {}).get("attachments") or []):
            if att.get("status") == "provisional":
                media = {k: att.get(k) for k in ("sha256", "media_type", "bytes")}
                objects.append(stable(_new_object(OBJECT_IMAGE, turn=index, sensor="composer_image",
                                                  content={"media": dict(media, retained=False)}), n))
    record["objects"] = objects
    return _object_envelopes(record)


def object_label(obj: dict) -> str:
    if obj.get("type") == OBJECT_IMAGE:
        media = (obj.get("content") or {}).get("media") or {}
        size = media.get("bytes") or 0
        size_text = "under 1 KB" if size < 1024 else "%d KB" % round(size / 1024)
        return "Image (%s, %s)" % ((media.get("media_type") or "image").replace("image/", ""), size_text)
    return " ".join(str((obj.get("content") or {}).get("text") or "").split())


def resolve_selection(record: Optional[dict], requested) -> tuple[list, int]:
    """GOV-P-001: the HOST fixes the selection. Only ids that name an object in
    the owner's own current Sandbox survive; anything else is ignored and
    counted. Returns (objects in field order, ignored count). Over the cap is
    REFUSED, never silently cut down to size."""
    wanted = []
    for value in requested or ():
        value = str(value or "").strip()
        if value and value not in wanted:
            wanted.append(value)
    objects = (record or {}).get("objects") or []
    known = {obj["id"] for obj in objects}
    chosen = [obj for obj in objects if obj["id"] in wanted]
    ignored = len([value for value in wanted if value not in known])
    if len(chosen) > MAX_SELECTION:
        raise SandboxRefused("Select at most %d objects as context for one message. "
                             "Nothing was sent." % MAX_SELECTION)
    if len([o for o in chosen if o["type"] == OBJECT_IMAGE]) > MAX_SELECTED_IMAGES:
        raise SandboxRefused("Select at most %d images as context for one message. "
                             "Nothing was sent." % MAX_SELECTED_IMAGES)
    return chosen, ignored


def _clip(items, cap=_LIST_CAP) -> list[str]:
    out = []
    for item in items or ():
        text = " ".join(str(item).split())[:_ITEM_CAP]
        if text and text not in out:
            out.append(text)
        if len(out) >= cap:
            break
    return out


def is_planning_objective(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in _PLANNING_TERMS)


def recommend_landing(text: str, history_texts=()) -> Optional[dict]:
    """The ONE place a landing is recommended - deterministic, never the model."""
    joined = " ".join([*(history_texts or ()), text or ""])
    if is_planning_objective(joined):
        return {"landing": LANDING_PLANNING_STUDY, "label": "Planning Study", "why": PLANNING_STUDY_WHY}
    return None


def external_check(text: str, history_texts=()) -> dict:
    """Whether the outside world should be checked. Advice only - never triggered here."""
    joined = " ".join([*(history_texts or ()), text or ""])
    if is_planning_objective(joined):
        return {"appropriate": True, "why": EXTERNAL_WHY, "triggered": False}
    return {"appropriate": False, "why": "", "triggered": False}


# -- organization ------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are Gopilot inside ARCHIOSK, helping an architect or builder think through an idea "
    "before any project work exists. Organize what the person said. Reflect their objective "
    "back in one plain sentence. Separate what they have told you (known facts) from what is "
    "not yet known, any constraints they stated or that plainly follow, and the next questions "
    "worth answering. Never state a regulation, requirement, fee or timeline as fact: anything "
    "about what an authority requires is an unknown to confirm. Do not recommend creating "
    "anything. Reply with JSON only."
)
_SCHEMA_HINT = (
    '{"objective": "one plain sentence", "known_facts": ["..."], "unknowns": ["..."], '
    '"constraints": ["..."], "next_questions": ["..."]}'
)


def attachment_identity(image_base64: str, media_type: str, *, analysed: bool) -> dict:
    """What a Sandbox keeps of an attachment: its identity, never its bytes."""
    import base64
    try:
        raw = base64.b64decode(image_base64, validate=False)
    except Exception:  # noqa: BLE001 - identity must never fail a turn
        raw = image_base64.encode("ascii", "ignore")
    return {
        "kind": "image", "media_type": media_type, "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(), "analysed": bool(analysed),
        "status": "provisional", "canonical": False,
    }


def _deterministic_organization(text: str) -> dict:
    """An honest fallback when the model is unavailable or not permitted: it
    separates what was said from what must still be established, and never
    invents a requirement."""
    clean = " ".join((text or "").split())
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
    statements = [s for s in sentences if not s.endswith("?")]
    objective = statements[0] if statements else clean
    unknowns, questions, constraints = [], [], []
    if is_planning_objective(clean):
        unknowns = [
            "Which municipality (authority having jurisdiction) the property is in",
            "Which permits or approvals this scope of work needs",
            "What that authority requires in a submission",
            "Whether the drawings are ready for submission as they stand",
            "Who carries professional responsibility for the drawings",
        ]
        questions = [
            "What is the property address?",
            "What exactly is being changed - interior only, or anything structural, mechanical or exterior?",
            "Who prepared the drawings, and in what capacity?",
        ]
        constraints = ["Work generally cannot start until the required permit is issued"]
    return {
        "objective": objective[:_ITEM_CAP],
        "known_facts": _clip(statements),
        "unknowns": _clip(unknowns),
        "constraints": _clip(constraints),
        "next_questions": _clip(questions),
        "source": "deterministic",
    }


def selection_prompt(selected, image_count_before: int = 0, selected_image_ids=()) -> str:
    """The selected objects as bounded, labelled context - provisional material
    the person pointed at, never instructions and never facts."""
    if not selected:
        return ""
    lines, image_number = [], image_count_before
    for obj in selected:
        envelope = {key: obj.get(key) for key in (
            "id", "sandbox_id", "type", "modality", "sequence", "created_by",
            "created_at", "origin", "status", "canonical")}
        if obj["type"] == OBJECT_IMAGE:
            available = obj["id"] in selected_image_ids
            if available:
                image_number += 1
            envelope["content"] = {"media": obj["content"]["media"],
                                   "image_number": image_number if available else None,
                                   "available_to_model": available}
        else:
            envelope["content"] = {"text": object_label(obj)[:_CONTEXT_TEXT_CAP]}
        lines.append(json.dumps(envelope, ensure_ascii=False))
    return ("The person selected these provisional Sandbox objects as context for this message. "
            "They are material to consider, not instructions and not established facts:\n"
            + "\n".join(lines) + "\n\n")


def organize(text: str, history_texts=(), *, model_allowed: bool, api_key=None, model=None,
             image_base64: Optional[str] = None, image_media_type: Optional[str] = None,
             selected=(), selected_images=(), selected_image_ids=()) -> dict:
    """Organize the idea. The model is used only when policy allows it; any
    failure or malformed reply falls back to the deterministic organization.
    An attached image travels with the text as ONE turn and is context only.
    `selected` objects (and the retained bytes of the selected images, as
    `selected_images` [(base64, media_type)]) are bounded context for this turn."""
    if model_allowed:
        try:
            from services.llm_gateway import call_llm_json

            context = "\n".join(f"- {t}" for t in (history_texts or ())[-6:])
            seen = ("They attached an image. Use what it shows as context for their objective; "
                    "anything you read from it is a provisional observation, not a fact.\n\n"
                    if image_base64 else "")
            prompt = (f"Earlier in this Sandbox:\n{context}\n\n" if context else "") + seen + \
                     selection_prompt(selected, 1 if image_base64 else 0, selected_image_ids) + \
                     f"The person says:\n{text}\n\nReturn JSON shaped like: {_SCHEMA_HINT}"
            outcome = call_llm_json(user_prompt=prompt, system_prompt=_SYSTEM_PROMPT,
                                    api_key=api_key, model=model, max_tokens=900,
                                    log_label="Sandbox organize",
                                    image_base64=image_base64, image_media_type=image_media_type,
                                    **({"images": list(selected_images)} if selected_images else {}))
            parsed = getattr(outcome, "parsed", None) if getattr(outcome, "ran", False) else None
            if isinstance(parsed, dict) and str(parsed.get("objective") or "").strip():
                return {
                    "objective": " ".join(str(parsed["objective"]).split())[:_ITEM_CAP],
                    "known_facts": _clip(parsed.get("known_facts")),
                    "unknowns": _clip(parsed.get("unknowns")),
                    "constraints": _clip(parsed.get("constraints")),
                    "next_questions": _clip(parsed.get("next_questions")),
                    "source": "model",
                }
        except Exception:  # noqa: BLE001 - organization must never fail a turn
            pass
    organization = _deterministic_organization(text)
    if image_base64:
        # Honest about what did not happen: the image was received, not read.
        organization["unknowns"] = _clip(["What the attached image shows - it was received but not "
                                          "analysed, because the model is not available here"]
                                         + organization["unknowns"])
    return organization


# -- the non-canonical store ------------------------------------------------------

class SandboxConflict(SandboxRefused):
    """The Sandbox changed after this page was drawn (another tab or window).
    Refused, never merged: nothing from the stale request was kept."""


NONE_TOKEN = "none"


class SandboxStore:
    """One current Sandbox per user, as a small JSON file outside every project.

    STORAGE HARDENING (LIQUID SANDBOX v0):

    CONCURRENCY - optimistic revisions. Every record carries `revision`, and its
    `token()` ("<id>:<revision>", or "none") is drawn into every page that can
    write. A write names the token its page saw; if the owner's Sandbox has
    changed since - another tab sent a turn, chose a landing, or started a new
    Sandbox - the write is REFUSED with SandboxConflict and the person is told
    to refresh. Nothing is merged. The compare-and-swap itself runs under a
    short per-owner lock file, held only for read-check-write, so two in-flight
    requests cannot both pass the check; it is not a session-long lock.
    KNOWN v0 LIMITATION (accepted): a request that becomes stale DURING its
    Gopilot call has already reached the model when the final write conflicts;
    it is refused and nothing from it is persisted or promoted.

    PROVISIONAL MEDIA - retention and deletion. Image bytes live under
    `media_root` (SANDBOX_MEDIA_PATH), a root of their own: outside the registry
    (so registry snapshots and transactions never carry them), outside
    PROJECT_ASSET_PATH, and outside every project store and retrieval path. One
    directory per owner (a digest of the username); only that owner's current
    Sandbox can name a file in it, and every read is checksum-verified. Rules:
      - a file exists only while the owner's CURRENT Sandbox references it;
      - starting a new Sandbox deletes the owner's media directory;
      - after every write, files the record no longer references are deleted
        (a turn refused after its bytes were written leaves nothing behind);
      - bytes never travel in lineage - a landing carries identity only.
    There is no age-based expiry: v0 has no background worker, and a Sandbox's
    images live exactly as long as that Sandbox does.
    """

    _LOCK_TIMEOUT = 5.0         # seconds to wait for the owner's write lock
    _LOCK_STALE = 30.0          # a lock older than this was abandoned by a dead writer

    def __init__(self, registry_root, media_root=None):
        self.root = Path(registry_root) / "sandbox"
        # None for readers that never touch bytes (the planning owner's lineage
        # read and promotion mark); media operations then refuse.
        self.media_root = Path(media_root) if media_root else None

    @staticmethod
    def _digest(username: str) -> str:
        return hashlib.sha256((username or "").encode("utf-8")).hexdigest()[:32]

    def _path(self, username: str) -> Path:
        return self.root / f"{self._digest(username)}.json"

    def _owner_media(self, username: str) -> Path:
        if self.media_root is None:
            raise RuntimeError("this SandboxStore was opened without a media root")
        return self.media_root / self._digest(username)

    def _media_path(self, username: str, sha256: str, media_type: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", sha256 or "") or media_type not in _MEDIA_EXTENSIONS:
            raise ValueError("not a retained media identity")
        return self._owner_media(username) / (sha256 + _MEDIA_EXTENSIONS[media_type])

    def _purge_media(self, username: str) -> None:
        """A new Sandbox replaces the record, so the old one's media goes with it."""
        import shutil
        if self.media_root is not None:
            shutil.rmtree(self._owner_media(username), ignore_errors=True)

    def _sweep_media(self, record: dict) -> None:
        """Delete the owner's media files that the record does not reference."""
        if self.media_root is None:
            return
        folder = self._owner_media(record["owner"])
        if not folder.is_dir():
            return
        keep = set()
        for obj in record.get("objects") or []:
            media = (obj.get("content") or {}).get("media") or {}
            if obj.get("type") == OBJECT_IMAGE and media.get("retained"):
                try:
                    keep.add(self._media_path(record["owner"], media["sha256"], media["media_type"]).name)
                except ValueError:
                    pass
        for path in folder.iterdir():
            if path.is_file() and path.name not in keep:
                try:
                    path.unlink()
                except OSError:
                    pass

    def read_media(self, username: str, obj: dict) -> Optional[bytes]:
        """The retained bytes of one of the owner's image objects, integrity-checked."""
        media = ((obj or {}).get("content") or {}).get("media") or {}
        if obj.get("type") != OBJECT_IMAGE or not media.get("retained") or self.media_root is None:
            return None
        try:
            raw = self._media_path(username, media.get("sha256"), media.get("media_type")).read_bytes()
        except (OSError, ValueError):
            return None
        return raw if hashlib.sha256(raw).hexdigest() == media["sha256"] else None

    def check_capacity(self, record: Optional[dict], *, note: bool, image_bytes: int = 0) -> None:
        """Refuse - never truncate - a turn the Sandbox cannot hold."""
        record = record or {"turns": [], "objects": []}
        objects = record.get("objects") or []
        adding = int(bool(note)) + int(bool(image_bytes))
        if len(record.get("turns") or []) >= MAX_TURNS:
            raise SandboxRefused("This Sandbox is full (%d messages). Start a new Sandbox to keep going; "
                                 "nothing from this message was kept or sent." % MAX_TURNS)
        if len(objects) + adding > MAX_OBJECTS:
            raise SandboxRefused("This Sandbox is full (%d objects). Start a new Sandbox to keep going; "
                                 "nothing from this message was kept or sent." % MAX_OBJECTS)
        if image_bytes:
            images = [o for o in objects if o["type"] == OBJECT_IMAGE and o["content"]["media"].get("retained")]
            held = sum(o["content"]["media"].get("bytes") or 0 for o in images)
            if len(images) + 1 > MAX_MEDIA_OBJECTS or held + image_bytes > MAX_MEDIA_BYTES:
                raise SandboxRefused("This Sandbox cannot hold another image (%d images or %d MB). Start a "
                                     "new Sandbox to keep going; nothing from this message was kept or sent."
                                     % (MAX_MEDIA_OBJECTS, MAX_MEDIA_BYTES // (1024 * 1024)))

    def _read(self, username: str) -> Optional[dict]:
        path = self._path(username)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return record if record.get("owner") == username else None

    def get(self, username: str, sandbox_id: Optional[str] = None) -> Optional[dict]:
        record = self._read(username)
        if record is None:
            return None
        if sandbox_id is not None and record.get("id") != sandbox_id:
            return None
        return _project_legacy_objects(record)

    @staticmethod
    def _token_of(record: Optional[dict]) -> str:
        return NONE_TOKEN if record is None else "%s:%d" % (record.get("id"), int(record.get("revision") or 0))

    def token(self, username: str) -> str:
        """The owner's Sandbox as it stands on disk - what a page must echo back to write."""
        return self._token_of(self._read(username))

    # -- the one write path: compare-and-swap under a short per-owner lock ------

    def _lock(self, username: str):
        import contextlib
        import time

        @contextlib.contextmanager
        def held():
            self.root.mkdir(parents=True, exist_ok=True)
            lock = self.root / f"{self._digest(username)}.lock"
            deadline = time.monotonic() + self._LOCK_TIMEOUT
            while True:
                try:
                    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                    break
                except FileExistsError:
                    try:
                        if time.time() - lock.stat().st_mtime > self._LOCK_STALE:
                            lock.unlink()
                            continue
                    except OSError:
                        continue
                    if time.monotonic() > deadline:
                        raise SandboxConflict("This Sandbox is busy with another request. Refresh and try again; "
                                              "nothing from this request was kept.")
                    time.sleep(0.02)
            try:
                yield
            finally:
                try:
                    lock.unlink()
                except OSError:
                    pass
        return held()

    def _write(self, record: dict) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False)
        os.replace(tmp, self._path(record["owner"]))
        return record

    def _update(self, username: str, expected: Optional[str], change) -> dict:
        """Read, check the caller's token (None = a server-internal write that
        re-reads fresh), apply `change`, bump the revision, write, sweep media."""
        with self._lock(username):
            current = self._read(username)
            if expected is not None and self._token_of(current) != expected:
                raise SandboxConflict("This Sandbox changed in another tab or window. Refresh to see the "
                                      "latest, then try again. Nothing from this request was kept.")
            if current is not None:
                current = _project_legacy_objects(current)
            record = change(current)
            record["revision"] = (int(current.get("revision") or 0) + 1
                                  if current is not None and current.get("id") == record["id"] else 1)
            self._write(record)
        self._sweep_media(record)
        return record

    def _save(self, record: dict) -> dict:
        """Unconditional write - fixtures and legacy tooling only; routes use _update."""
        return self._write(record)

    def start(self, username: str, *, expected: Optional[str] = None) -> dict:
        def fresh(_current):
            self._purge_media(username)
            return {"id": uuid.uuid4().hex, "owner": username, "created_at": _now(),
                    "canonical": False, "turns": [], "objects": [], "decisions": [], "promoted_to": None}
        return self._update(username, expected, fresh)

    def add_turn(self, username: str, sandbox_id: str, text: str, reply: dict, *,
                 note: bool = True, image: Optional[tuple] = None, selected=(),
                 text_arrival: str = "unknown", image_arrival: str = "unknown",
                 expected: Optional[str] = None) -> dict:
        """Record one turn and the objects it contributed: a `note` for what the
        person typed (note=False when the text was only a default prompt), an
        `image` whose bytes are retained, and the ids selected as its context.
        Token and caps are checked first; a refused turn leaves nothing behind."""
        import base64

        raw = base64.b64decode(image[0]) if image else b""

        def append(record):
            if record is None or record.get("id") != sandbox_id:
                raise KeyError("no such Sandbox")
            self.check_capacity(record, note=note, image_bytes=len(raw))
            index = len(record["turns"])
            created = []
            if note:
                created.append(_new_object(OBJECT_NOTE, turn=index, sensor="composer_text",
                                           content={"text": text}))
            if image:
                sha = hashlib.sha256(raw).hexdigest()
                path = self._media_path(username, sha, image[1])
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(raw)
                    os.replace(tmp, path)
                created.append(_new_object(OBJECT_IMAGE, turn=index, sensor="composer_image", content={
                    "media": {"sha256": sha, "media_type": image[1], "bytes": len(raw), "retained": True}}))
            record["objects"].extend(created)
            for obj in created:
                obj["origin"]["arrival"] = arrival(
                    text_arrival if obj["type"] == OBJECT_NOTE else image_arrival, obj["type"])
            _object_envelopes(record)
            record["turns"].append({"at": _now(), "text": text, "reply": reply,
                                    "objects": [obj["id"] for obj in created], "selected": list(selected)})
            return record
        return self._update(username, expected, append)

    def move_object(self, username: str, sandbox_id: str, object_id: str, x, y, *,
                    expected: str) -> dict:
        """Change presentation only, under the same owner lock and revision check."""
        if not expected:
            raise SandboxConflict("Refresh this Sandbox before moving an object.")
        if any(type(v) not in (int, float) or not 0 <= v <= 10000 for v in (x, y)):
            raise SandboxRefused("Positions must be numbers between 0 and 10000.")

        def move(record):
            if record is None or record.get("id") != sandbox_id:
                raise SandboxRefused("This object is not in the current Sandbox.")
            obj = next((o for o in record["objects"] if o["id"] == object_id), None)
            if obj is None:
                raise SandboxRefused("This object is not in the current Sandbox.")
            obj["position"] = {"x": round(x, 2), "y": round(y, 2)}
            return record
        return self._update(username, expected, move)

    def record_decision(self, username: str, sandbox_id: str, choice: str, *,
                        expected: Optional[str] = None) -> dict:
        def decide(record):
            if record is None or record.get("id") != sandbox_id:
                raise KeyError("no such Sandbox")
            record["decisions"].append({"at": _now(), "choice": choice})
            return record
        return self._update(username, expected, decide)

    def mark_promoted(self, username: str, sandbox_id: str, promotion: dict) -> Optional[dict]:
        def promote(record):
            if record is None or record.get("id") != sandbox_id:
                raise KeyError("no such Sandbox")
            record["promoted_to"] = dict(promotion, at=_now())
            return record
        try:
            return self._update(username, None, promote)
        except KeyError:
            return None


def lineage(record: dict) -> dict:
    """What a landing carries forward: where it came from, never the turns as evidence."""
    turns = record.get("turns") or []
    latest = (turns[-1]["reply"] if turns else {}) or {}
    return {
        "kind": "sandbox",
        "sandbox_id": record["id"],
        "objective": (latest.get("organization") or {}).get("objective") or (turns[0]["text"] if turns else ""),
        "turn_count": len(turns),
        "started_at": record.get("created_at"),
        "canonical": False,
        # Attachment IDENTITY only (never bytes), each tied to its turn - carried
        # forward only because a person explicitly chose this landing.
        "attachments": [dict(att, turn=index) for index, turn in enumerate(turns)
                        for att in ((turn.get("reply") or {}).get("attachments") or [])],
    }
