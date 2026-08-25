"""CLAUDE-DIAGNOSTIC-BRIDGE-01 - read, complete and send a diagnostic report.

    ./venv/Scripts/python.exe tools/diagnostic_report.py list
    ./venv/Scripts/python.exe tools/diagnostic_report.py show 12
    ./venv/Scripts/python.exe tools/diagnostic_report.py complete 12 --findings "..." [--root-cause ...]
    ./venv/Scripts/python.exe tools/diagnostic_report.py preview 12
    ./venv/Scripts/python.exe tools/diagnostic_report.py email 12

THIS IS THE OTHER HALF OF THE BRIDGE, AND IT IS A CLI ON PURPOSE

ARCHIOSK cannot call a development agent. A Claude Code session runs on an
operator's own machine, started by a human, and there is no inbox it polls. So
the honest bridge is a PULL: the application captures a problem into an inert
row, and a development session reads it through this tool when asked to.

That asymmetry is not a limitation to engineer around - it is the boundary the
Product Owner required. "Send this to Claude" cannot silently become permission
to change code or deploy, because a row in a table has no mechanism to do
either, and neither does this file. `complete` writes conclusions; nothing here
touches the repository or the server.

`--commit-status` is a STATEMENT ABOUT work done elsewhere under its own
authorization. Writing "committed as abc1234" here does not commit anything, and
must never be read as evidence that something was authorized.

The five acts stay separate, exactly as instructed:
    capture (in the app) -> investigate -> complete -> email -> (code/deploy,
    which are not this tool's business at all).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module  # noqa: E402
from models import DiagnosticReport, db  # noqa: E402
from services import diagnostic_report as service  # noqa: E402


def _app():
    # The real configuration, not "testing" - this tool operates on the actual
    # captured reports, and a testing app would silently use an in-memory
    # database and report an empty list as though nothing had been captured.
    return app_module.create_app()


def cmd_list(args):
    with _app().app_context():
        reports = service.list_reports(limit=args.limit)
        if not reports:
            print("No diagnostics captured.")
            return
        for r in reports:
            when = r.reported_at.strftime("%Y-%m-%d %H:%M") if r.reported_at else "?"
            mailed = " emailed" if r.emailed_at else ""
            print(f"#{r.id:<4} {r.status:<13}{mailed:<8} {when}  {r.summary}")


def cmd_show(args):
    with _app().app_context():
        report = db.session.get(DiagnosticReport, args.id)
        if report is None:
            print(f"No diagnostic {args.id}.")
            sys.exit(1)
        # The full captured context, which is the point of the whole bridge: an
        # investigator should never have to ask which page, which project, or
        # which build.
        for field in ("id", "status", "reported_by", "reported_at", "summary",
                      "detail", "surface", "project_id", "case_id", "build_sha",
                      "static_version", "trace", "findings", "root_cause",
                      "affected", "recommendation", "commit_status",
                      "uncertainty", "investigated_at", "emailed_at"):
            value = getattr(report, field)
            if value not in (None, ""):
                print(f"{field}: {value}")


def cmd_complete(args):
    with _app().app_context():
        report = service.complete(
            args.id,
            findings=args.findings,
            root_cause=args.root_cause,
            affected=args.affected,
            recommendation=args.recommendation,
            commit_status=args.commit_status,
            uncertainty=args.uncertainty,
        )
        if report is None:
            print(f"No diagnostic {args.id}.")
            sys.exit(1)
        print(f"Diagnostic {report.id} marked {report.status}. Not emailed - that is a separate step.")


def cmd_preview(args):
    """See exactly what would be sent, before sending it."""
    with _app().app_context():
        report = db.session.get(DiagnosticReport, args.id)
        if report is None:
            print(f"No diagnostic {args.id}.")
            sys.exit(1)
        subject, body = service.format_email(report)
        print(f"Subject: {subject}\n")
        print(body)


def cmd_email(args):
    with _app().app_context():
        sent, reason = service.email_report(args.id, to_addr=args.to)
        print(reason)
        if not sent:
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="captured diagnostics, newest first")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="one diagnostic in full")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("complete", help="write an investigation's conclusions")
    p.add_argument("id", type=int)
    p.add_argument("--findings", required=True)
    p.add_argument("--root-cause", dest="root_cause")
    p.add_argument("--affected")
    p.add_argument("--recommendation")
    p.add_argument("--commit-status", dest="commit_status",
                   help="a statement ABOUT work done elsewhere; this changes nothing")
    p.add_argument("--uncertainty")
    p.set_defaults(func=cmd_complete)

    p = sub.add_parser("preview", help="the exact email body, without sending")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("email", help="send a completed diagnostic to the Product Owner")
    p.add_argument("id", type=int)
    p.add_argument("--to", help="override DIAGNOSTIC_NOTIFY_EMAIL")
    p.set_defaults(func=cmd_email)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
