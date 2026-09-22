"""CLAUDE-PROJECT-CHANGE-LANE-01 - what changed, answered from the ledger.

Asked live on 2026-09-22: "what is new in this project if anything has changed
during this week". The answer was a dump of every evidence item in the project,
each qualified SOURCE_REFERENCE - not established as a project fact - followed
by source excerpts. Nothing in the path had looked at when anything happened,
because nothing in the path knew the question was about time.

The truthful answer was one sentence, and the data for it was already there:
82 governance events, none in the last seven days; 17 sources, none added.

THIS IS A PROJECTION, NOT A SECOND HISTORY ENGINE. It opens no store of its
own, writes nothing, and indexes nothing. Every signal below is read from the
record that already owns it:

    GovernanceLog.read(project_id)   - the event ledger, already the source
                                       routes/portal.py:229 uses for a
                                       project's `last_activity`
    workspace.sources[].added_at     - source arrival
    workspace.cases[].created_at     - investigations opened
    workspace.findings[].created_at  - findings recorded
    workspace.analyses[].completed_at- analysis runs

AUTHORITY IS UNCHANGED, because none is asserted. Counting that an event was
recorded is not a claim about what the event established; this module never
reads a payload's meaning, never admits a proposition and never promotes
anything. It answers "did anything happen, and when" - a question about the
ledger, not about the evidence.

ABSENCE IS AN ANSWER HERE. "No changes were recorded this week" is a finding,
not a failure, and it is stated plainly rather than as an empty result the
caller has to interpret. That is the whole reason the previous behaviour was
wrong: a project with nothing to report produced seven screens of unrelated
source text.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

# Windows a person actually asks about. Deliberately small and closed: this is
# deterministic phrase matching, not date parsing, and it refuses anything it
# does not recognise rather than guessing a range.
WINDOW_WEEK = "week"
WINDOW_TODAY = "today"
WINDOW_MONTH = "month"

_WINDOW_DAYS = {WINDOW_TODAY: 1, WINDOW_WEEK: 7, WINDOW_MONTH: 31}
_WINDOW_LABEL = {WINDOW_TODAY: "today", WINDOW_WEEK: "this week", WINDOW_MONTH: "this month"}


def _parse(value) -> Optional[datetime]:
    """An ISO timestamp, or None. Never raises on a malformed record."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def window_for(text: str) -> Optional[str]:
    """The window a question asks about, or None if it does not ask about one.

    Matched on explicit words only. "this week", "past week", "last 7 days" are
    a window; "recently" is not, because a system that answered "recently" with
    a seven-day count would be inventing the boundary and reporting it as fact.
    """
    lowered = (text or "").lower()
    if re.search(r"\b(today|since yesterday|last 24 hours)\b", lowered):
        return WINDOW_TODAY
    if re.search(r"\b(this|past|last)\s+week\b", lowered) or re.search(r"\blast\s+7\s+days\b", lowered):
        return WINDOW_WEEK
    if re.search(r"\b(this|past|last)\s+month\b", lowered) or re.search(r"\blast\s+30\s+days\b", lowered):
        return WINDOW_MONTH
    return None


def changes_since(workspace, window: str, *, governance_events=(), now: Optional[datetime] = None) -> dict:
    """Activity counts for `window`. Reads; never writes.

    `governance_events` is passed in rather than read here, so this module
    stays free of the GovernanceLog import and the caller keeps ownership of
    which project's log it opened - the same shape gather_project_evidence
    already uses for its store.
    """
    days = _WINDOW_DAYS.get(window)
    if days is None:
        raise ValueError(f"'{window}' is not a recognised change window.")

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    def within(value) -> bool:
        parsed = _parse(value)
        return parsed is not None and parsed >= cutoff

    events = [e for e in governance_events
              if within(getattr(e, "created_at", None) or (e.get("created_at") if isinstance(e, dict) else None))]
    sources = [s for s in (workspace.sources or []) if within(s.get("added_at"))]
    cases = [c for c in (workspace.cases or []) if within(c.get("created_at"))]
    findings = [f for f in (workspace.findings or []) if within(f.get("created_at"))]
    analyses = [a for a in (workspace.analyses or []) if within(a.get("completed_at") or a.get("started_at"))]

    # The most recent thing that happened AT ALL, so an empty window can say
    # when the project was last touched instead of only that it was not.
    stamps = [
        _parse(getattr(e, "created_at", None) or (e.get("created_at") if isinstance(e, dict) else None))
        for e in governance_events
    ] + [_parse(s.get("added_at")) for s in (workspace.sources or [])]
    known = [s for s in stamps if s is not None]

    counts = {
        "governance_events": len(events),
        "sources_added": len(sources),
        "cases_opened": len(cases),
        "findings_recorded": len(findings),
        "analyses_completed": len(analyses),
    }
    return {
        "window": window,
        "window_label": _WINDOW_LABEL[window],
        "cutoff": cutoff.isoformat(),
        "counts": counts,
        "total": sum(counts.values()),
        "changed": sum(counts.values()) > 0,
        "last_activity_at": max(known).isoformat() if known else None,
        "event_types": sorted({
            str(getattr(e, "event_type", None) or (e.get("event_type") if isinstance(e, dict) else ""))
            for e in events
        } - {""}),
        "source_names": [s.get("name") for s in sources if s.get("name")][:10],
    }


_LABELS = (
    ("governance_events", "governance event", "governance events"),
    ("sources_added", "source added", "sources added"),
    ("cases_opened", "investigation opened", "investigations opened"),
    ("findings_recorded", "finding recorded", "findings recorded"),
    ("analyses_completed", "analysis completed", "analyses completed"),
)


def summarise(change: dict) -> str:
    """The answer, result first.

    One sentence saying whether anything changed, then the counts that support
    it - never the other way round, and never a wall of evidence in front of a
    one-word answer. This is the same ordering answer_presentation.py applies
    on the document page, written here in plain text because this reply has no
    machinery worth deferring.
    """
    label = change["window_label"]
    if not change["changed"]:
        line = f"No confirmed project changes were recorded {label}."
        parts = []
        if change["counts"]["governance_events"] == 0:
            parts.append("no governance events occurred")
        if change["counts"]["sources_added"] == 0:
            parts.append("no new sources were added")
        if parts:
            line += " " + " and ".join(parts).capitalize() + " during the period."
        if change["last_activity_at"]:
            line += f" The most recent recorded activity was {change['last_activity_at'][:10]}."
        return line

    bits = []
    for key, singular, plural in _LABELS:
        count = change["counts"][key]
        if count:
            bits.append(f"{count} {singular if count == 1 else plural}")
    line = f"{change['total']} change{'' if change['total'] == 1 else 's'} recorded {label}: " + ", ".join(bits) + "."
    if change["source_names"]:
        line += " New sources: " + ", ".join(change["source_names"]) + "."
    if change["event_types"]:
        line += " Event types: " + ", ".join(change["event_types"][:6]) + "."
    return line
