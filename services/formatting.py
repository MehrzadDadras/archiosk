"""
Presentation-only timestamp formatting. Every stored timestamp in this
app is an ISO 8601 string (GovernanceEvent.created_at, ParsedDocument's
ingested_at) - this module only changes how one is displayed, never how
it is stored, compared, or sorted.
"""
from __future__ import annotations

from datetime import datetime, timezone


def humanize_timestamp(value: str | None, *, now: datetime | None = None) -> str:
    """"2026-02-03T14:05:00+00:00" -> "Feb 3, 2026", or a relative
    "N minutes/hours ago" form for anything within the last day."""
    if not value:
        return ""

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    reference = now or datetime.now(timezone.utc)
    delta = reference - dt
    seconds = delta.total_seconds()

    if 0 <= seconds < 60:
        return "just now"
    if 0 <= seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if 0 <= seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"
