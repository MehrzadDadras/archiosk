"""
CLAUDE-DIAGNOSTIC-BRIDGE-01 - capture a live product problem where it happened,
and hand a finished investigation back in a form that can be pasted anywhere.

Product Owner: "I want to be able to receive Claude's diagnostic result and
paste it directly into ChatGPT without manually reconstructing the
investigation."

FIVE DISTINCT ACTS, AND THEY STAY DISTINCT

    capture   -> record()          in the app, by an admin
    investigate -> complete()      by a development agent, from a Claude Code session
    notify    -> email_report()    an explicit, separate call
    modify code / deploy           NOT HERE, and deliberately unrepresentable

The Product Owner asked for that separation. It is enforced by there being no
function in this module that can change code or deploy anything - not by a flag
saying it must not.

WHAT IS NOT HERE, ON PURPOSE

No transport to a development agent. ARCHIOSK cannot call Claude Code, which
runs on an operator's own machine when a human starts it. `record()` writes a
row; a Claude Code session reads it when asked. Anything that claimed to "send
to Claude" would be a fiction, and the receipt wording in the route says
"recorded as" for exactly that reason.

No new mail subsystem either: `email_report` calls services/email.py's existing
`send_email`, with the same "blank config means skip, never error" contract
password reset and trial requests already rely on.
"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from typing import Optional

from flask import current_app

from models import DiagnosticReport, db
from services.email import send_email

logger = logging.getLogger(__name__)

# What a report may carry. Deliberately identifiers and prose - never project
# document content, never conversation text. An investigator with a project_id
# can read the real thing from the store; a mailbox does not need a copy of it.
_MAX_DETAIL = 8000
_MAX_TRACE = 8000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def deployed_build_sha() -> Optional[str]:
    """The commit this code came from, if it can be established honestly.

    The deployed application directory is NOT a git repository (deploy/
    DEPLOYMENT.md: "there is no git pull on the server"), so this returns None
    in production rather than guessing. A None here is a truthful "unknown",
    which is far more useful to an investigator than a plausible wrong answer -
    the live STATIC_VERSION below is the marker that actually distinguishes
    builds in this deployment.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, encoding="utf-8",
            cwd=str(current_app.root_path),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    sha = (result.stdout or "").strip()
    return sha[:40] or None


def record(
    *,
    reported_by: str,
    summary: str,
    detail: Optional[str] = None,
    surface: Optional[str] = None,
    project_id: Optional[str] = None,
    case_id: Optional[str] = None,
    trace: Optional[str] = None,
) -> DiagnosticReport:
    """Capture one problem, filling in what the application already knows.

    The point of this function is that the Product Owner should never retype
    which page they were on, which project was open, or which build was running.
    Everything derivable is derived here.
    """
    report = DiagnosticReport(
        reported_by=reported_by,
        summary=(summary or "").strip()[:300] or "(no summary given)",
        detail=(detail or "").strip()[:_MAX_DETAIL] or None,
        surface=(surface or "").strip()[:300] or None,
        project_id=(project_id or None),
        case_id=(case_id or None),
        build_sha=deployed_build_sha(),
        static_version=str(current_app.config.get("STATIC_VERSION") or "") or None,
        trace=(trace or "").strip()[:_MAX_TRACE] or None,
        status=DiagnosticReport.STATUS_OPEN,
        reported_at=_utc_now(),
    )
    db.session.add(report)
    db.session.commit()
    logger.info("Diagnostic report %s captured by %r.", report.id, reported_by)
    return report


def complete(
    report_id: int,
    *,
    findings: str,
    root_cause: Optional[str] = None,
    affected: Optional[str] = None,
    recommendation: Optional[str] = None,
    commit_status: Optional[str] = None,
    uncertainty: Optional[str] = None,
) -> Optional[DiagnosticReport]:
    """Write an investigation's conclusions onto the report.

    Separate from record() and separate from email_report() because the Product
    Owner required capture, investigation and notification to be distinct acts.
    Completing a report changes no code and deploys nothing - `commit_status` is
    a STATEMENT ABOUT work that happened elsewhere under its own authorization,
    never a mechanism for causing any.
    """
    report = db.session.get(DiagnosticReport, report_id)
    if report is None:
        return None
    report.findings = (findings or "").strip() or None
    report.root_cause = (root_cause or "").strip() or None
    report.affected = (affected or "").strip() or None
    report.recommendation = (recommendation or "").strip() or None
    report.commit_status = (commit_status or "").strip() or None
    report.uncertainty = (uncertainty or "").strip() or None
    report.investigated_at = _utc_now()
    report.status = DiagnosticReport.STATUS_INVESTIGATED
    db.session.commit()
    return report


def format_email(report: DiagnosticReport) -> tuple[str, str]:
    """(subject, body) - concise, copy-ready, plain text.

    Written to be pasted straight into another conversation, which is the
    Product Owner's stated purpose, so: no HTML, no decoration, short labelled
    lines in the order they asked for them, and an explicit "not established"
    rather than a silently missing field. A gap that says nothing reads as an
    answer of "nothing", which is the wrong thing for an investigation to imply.
    """
    def line(label: str, value: Optional[str]) -> str:
        return f"{label}: {value.strip()}" if (value or "").strip() else f"{label}: not established"

    subject = f"ARCHIOSK diagnostic {report.id} - {report.summary}"

    parts = [
        f"ARCHIOSK diagnostic {report.id}",
        "",
        line("Live build", report.build_sha),
        line("Static version", report.static_version),
        line("Surface", report.surface),
        line("Project", report.project_id),
        line("Q / conversation", report.case_id),
        f"Reported by: {report.reported_by}",
        f"Reported at: {report.reported_at.isoformat() if report.reported_at else 'unknown'}",
        "",
        "ISSUE REPORTED",
        (report.detail or report.summary or "").strip() or "not established",
        "",
        "WHAT WAS FOUND",
        (report.findings or "").strip() or "not established",
        "",
        "ROOT CAUSE",
        (report.root_cause or "").strip() or "not established",
        "",
        "AFFECTED CODE / SURFACE",
        (report.affected or "").strip() or "not established",
        "",
        "FIX / RECOMMENDATION",
        (report.recommendation or "").strip() or "not established",
        "",
        "COMMIT / DEPLOYMENT STATUS",
        (report.commit_status or "").strip() or "not established",
        "",
        "STILL UNCERTAIN",
        (report.uncertainty or "").strip() or "nothing recorded as uncertain",
        "",
        "-- ",
        "Identifiers rather than project content, deliberately: an investigator "
        "reads the real material from the project, a mailbox does not need a copy "
        "of it.",
    ]
    return subject, "\n".join(parts)


def email_report(report_id: int, to_addr: Optional[str] = None) -> tuple[bool, str]:
    """Send a completed report. Returns (sent, human-readable reason).

    A separate act from completing it, and refuses to send an uninvestigated
    report: an email whose findings section says "not established" is worse than
    no email, because it looks like an answer.
    """
    report = db.session.get(DiagnosticReport, report_id)
    if report is None:
        return False, f"No diagnostic report {report_id}."
    if not (report.findings or "").strip():
        return False, (
            f"Diagnostic {report_id} has no findings yet - investigate it before "
            "sending, or the email reads as an answer when it is not one."
        )

    to_addr = to_addr or current_app.config.get("DIAGNOSTIC_NOTIFY_EMAIL") or ""
    if not to_addr:
        return False, "No DIAGNOSTIC_NOTIFY_EMAIL configured."
    if not current_app.config.get("SMTP_HOST"):
        return False, "No SMTP_HOST configured - nothing was sent."

    subject, body = format_email(report)
    delivered = send_email(to_addr=to_addr, subject=subject, body=body)
    if delivered:
        report.emailed_at = _utc_now()
        db.session.commit()
        return True, f"Diagnostic {report_id} emailed."
    return False, f"Diagnostic {report_id} could not be delivered."


def list_reports(limit: int = 50) -> list[DiagnosticReport]:
    return (
        DiagnosticReport.query
        .order_by(DiagnosticReport.reported_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
