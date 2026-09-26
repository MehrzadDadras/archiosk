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
MAX_TURNS = 20
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def organize(text: str, history_texts=(), *, model_allowed: bool, api_key=None, model=None) -> dict:
    """Organize the idea. The model is used only when policy allows it; any
    failure or malformed reply falls back to the deterministic organization."""
    if model_allowed:
        try:
            from services.llm_gateway import call_llm_json

            context = "\n".join(f"- {t}" for t in (history_texts or ())[-6:])
            prompt = (f"Earlier in this Sandbox:\n{context}\n\n" if context else "") + \
                     f"The person says:\n{text}\n\nReturn JSON shaped like: {_SCHEMA_HINT}"
            outcome = call_llm_json(user_prompt=prompt, system_prompt=_SYSTEM_PROMPT,
                                    api_key=api_key, model=model, max_tokens=900,
                                    log_label="Sandbox organize")
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
    return _deterministic_organization(text)


# -- the non-canonical store ------------------------------------------------------

class SandboxStore:
    """One current Sandbox per user, as a small JSON file outside every project."""

    def __init__(self, registry_root):
        self.root = Path(registry_root) / "sandbox"

    def _path(self, username: str) -> Path:
        digest = hashlib.sha256((username or "").encode("utf-8")).hexdigest()[:32]
        return self.root / f"{digest}.json"

    def get(self, username: str, sandbox_id: Optional[str] = None) -> Optional[dict]:
        path = self._path(username)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if record.get("owner") != username:
            return None
        if sandbox_id is not None and record.get("id") != sandbox_id:
            return None
        return record

    def _save(self, record: dict) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(record["owner"])
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False)
        os.replace(tmp, path)
        return record

    def start(self, username: str) -> dict:
        return self._save({
            "id": uuid.uuid4().hex, "owner": username, "created_at": _now(),
            "canonical": False, "turns": [], "decisions": [], "promoted_to": None,
        })

    def add_turn(self, username: str, sandbox_id: str, text: str, reply: dict) -> dict:
        record = self.get(username, sandbox_id)
        if record is None:
            raise KeyError("no such Sandbox")
        record["turns"].append({"at": _now(), "text": text, "reply": reply})
        record["turns"] = record["turns"][-MAX_TURNS:]
        return self._save(record)

    def record_decision(self, username: str, sandbox_id: str, choice: str) -> dict:
        record = self.get(username, sandbox_id)
        if record is None:
            raise KeyError("no such Sandbox")
        record["decisions"].append({"at": _now(), "choice": choice})
        return self._save(record)

    def mark_promoted(self, username: str, sandbox_id: str, promotion: dict) -> Optional[dict]:
        record = self.get(username, sandbox_id)
        if record is None:
            return None
        record["promoted_to"] = dict(promotion, at=_now())
        return self._save(record)


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
    }
