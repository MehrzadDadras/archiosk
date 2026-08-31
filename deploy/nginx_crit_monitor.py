#!/usr/bin/env python3
"""
CLAUDE-NGINX-CRIT-MONITOR-01 - alert on new nginx [crit]/[alert]/[emerg] lines.

WHY THIS EXISTS

On 2026-08-29 a `sudo nginx -t -c /tmp/nginxtest/test.conf` chowned
/var/lib/nginx/* to `nobody`, because that throwaway config declared no
`user www-data;` and nginx fell back to its compiled-in default. nginx workers
run as www-data, so every request body too large to buffer in memory failed with

    open() "/var/lib/nginx/body/00000000NN" failed (13: Permission denied)

and nginx returned 500 BEFORE the request reached gunicorn - so the application
log was clean and showed nothing at all. The defect ran for ~40 hours and was
found only when the Product Owner tried to upload a document and it broke.

nginx had been writing [crit] for those 40 hours. Nothing read it.

WHAT IT DOES

Reads only the bytes appended since the last run, reports lines matching
[crit]/[alert]/[emerg], and advances a cursor. Everything else about the design
follows from two properties:

  IT MUST NOT LOSE AN ALERT. The cursor advances only AFTER delivery succeeds.
  A failed send leaves the cursor where it was, so the next run re-reports the
  same lines rather than silently swallowing them. Duplicate alerts are an
  annoyance; a dropped one recreates exactly the blindness this exists to end.

  IT MUST NOT INVENT ONE. Rotation is detected by st_ino and st_dev, not by
  size: logrotate runs daily here with `create 0640 www-data adm`, so a fresh
  file legitimately starts at 0 bytes and a size-only check would re-report the
  entire previous file every night. On rotation this reads the new file from the
  start; it deliberately does NOT chase the rotated-away tail into
  error.log.1(.gz), because a monitor that reads compressed history is a
  different, much larger program and the window it would miss is bounded by one
  logrotate interval.

FAIL-CLOSED

Any unexpected condition - unreadable log, unwritable state, malformed state,
failed delivery - exits non-zero WITHOUT advancing the cursor. systemd records
the failure. It never edits nginx, the application, or any production config;
its only write is its own state file.

USAGE

    nginx_crit_monitor.py --dry-run     # report, send nothing, touch no state
    nginx_crit_monitor.py               # report and advance the cursor
    nginx_crit_monitor.py --reset       # set cursor to current EOF, alert nothing

Alert routing is chosen by environment (see _deliver): ARCHIOSK_ALERT_WEBHOOK
posts JSON; ARCHIOSK_ALERT_EMAIL sends via the SMTP_* settings already in the
application's .env. With neither set it logs to stderr only, which systemd
captures into the journal - functional, and honest about being the weakest sink.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import urllib.request
from pathlib import Path

LOG_PATH = Path(os.environ.get("ARCHIOSK_NGINX_ERROR_LOG", "/var/log/nginx/error.log"))
STATE_PATH = Path(os.environ.get(
    "ARCHIOSK_MONITOR_STATE", "/var/lib/archiosk-nginx-monitor/state.json"))
ENV_PATH = Path(os.environ.get("ARCHIOSK_ENV_FILE", "/var/www/archiosk/.env"))

SEVERITIES = ("[crit]", "[alert]", "[emerg]")
# Cap what one alert carries. A pathological burst must not produce a
# multi-megabyte email; the count is always reported truthfully even when the
# sample is truncated.
MAX_REPORTED = 20
MAX_READ_BYTES = 8 * 1024 * 1024

# Lines that are [crit] to nginx but are not a fault of this server.
#
# A dry run over the real log found 71 [crit] lines, of which 18 were
# SSL_do_handshake() failures from internet scanners offering key shares nginx
# will not accept. Those arrive continuously and forever. A monitor that pages
# on them every five minutes gets muted within a day, and a muted monitor is
# how the original 40-hour defect would be missed a second time - so alert
# fatigue is not a cosmetic concern here, it is the failure mode.
#
# These are SUPPRESSED, NOT HIDDEN: they never raise an alert on their own, and
# their count is always reported alongside anything that does. Add to this via
# ARCHIOSK_ALERT_IGNORE (regexes, one per line) rather than editing this list.
ROUTINE_PATTERNS = (
    r"SSL_do_handshake\(\) failed",
    r"SSL_read\(\) failed .* while waiting for request",
    r"SSL_shutdown\(\) failed",
)


class MonitorError(RuntimeError):
    """Anything that must fail the run without advancing the cursor."""


def _read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MonitorError("state file %s is unreadable: %s" % (STATE_PATH, exc))
    if not isinstance(state, dict):
        raise MonitorError("state file %s is not an object" % STATE_PATH)
    return state


def _write_state(state: dict) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename: a crash mid-write must not leave a truncated state
        # file, because the next run would treat that as corruption and refuse.
        tmp = STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(STATE_PATH)
    except OSError as exc:
        raise MonitorError("cannot write state %s: %s" % (STATE_PATH, exc))


def _collect(offset):
    """Return (matching lines, new offset, file identity)."""
    try:
        stat = LOG_PATH.stat()
    except OSError as exc:
        raise MonitorError("cannot stat %s: %s" % (LOG_PATH, exc))

    identity = {"inode": stat.st_ino, "device": stat.st_dev}

    if offset > stat.st_size:
        # Truncated in place (copytruncate, or a manual > file). Not rotation -
        # rotation changes the inode, which the caller checks first.
        offset = 0

    try:
        with LOG_PATH.open("rb") as handle:
            handle.seek(offset)
            raw = handle.read(MAX_READ_BYTES)
            new_offset = handle.tell()
    except OSError as exc:
        raise MonitorError("cannot read %s: %s" % (LOG_PATH, exc))

    # A partial trailing line means nginx is mid-write; leave it for the next run
    # so a single line is never split across two alerts.
    if raw and not raw.endswith(b"\n"):
        cut = raw.rfind(b"\n")
        if cut == -1:
            return [], offset, identity
        new_offset = offset + cut + 1
        raw = raw[:cut + 1]

    text = raw.decode("utf-8", errors="replace")
    hits = [line for line in text.splitlines()
            if any(sev in line for sev in SEVERITIES)]
    return hits, new_offset, identity


def _routine_matcher():
    patterns = list(ROUTINE_PATTERNS)
    extra = os.environ.get("ARCHIOSK_ALERT_IGNORE", "")
    patterns.extend(p for p in (line.strip() for line in extra.splitlines()) if p)
    try:
        return re.compile("|".join("(?:%s)" % p for p in patterns)) if patterns else None
    except re.error as exc:
        raise MonitorError("ARCHIOSK_ALERT_IGNORE is not a valid regex: %s" % exc)


def _partition(hits):
    """Split into (actionable, routine). Routine lines never alert alone."""
    matcher = _routine_matcher()
    if matcher is None:
        return hits, []
    actionable, routine = [], []
    for line in hits:
        (routine if matcher.search(line) else actionable).append(line)
    return actionable, routine


def _summarise(hits):
    """Group by the stable part of the message, so 40 hours of one defect reads
    as one problem seen N times rather than N separate problems."""
    buckets = {}
    for line in hits:
        # Drop the leading timestamp/pid and the trailing per-request detail;
        # what remains is the actual fault.
        key = re.sub(r"^\S+ \S+ ", "", line)
        key = re.sub(r"\*\d+", "*", key)
        key = re.sub(r'"/var/lib/nginx/\S+"', '"/var/lib/nginx/<tempfile>"', key)
        key = key.split(", client:")[0]
        buckets[key] = buckets.get(key, 0) + 1
    parts = ["%d x %s" % (count, key)
             for key, count in sorted(buckets.items(), key=lambda kv: -kv[1])]
    return "\n".join(parts[:MAX_REPORTED])


def _load_env_smtp():
    """Read SMTP_* from the application's .env. Values are never printed."""
    settings = {}
    try:
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" not in raw or raw.lstrip().startswith("#"):
                continue
            key, _, value = raw.partition("=")
            key = key.strip()
            if key.startswith("SMTP_"):
                settings[key] = value.strip().strip('"').strip("'")
    except OSError as exc:
        raise MonitorError("cannot read SMTP settings from %s: %s" % (ENV_PATH, exc))
    return settings


def _truthy(value, default=False):
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _deliver(subject, body):
    """Send the alert. Returns the sink used. Raises MonitorError on failure."""
    webhook = os.environ.get("ARCHIOSK_ALERT_WEBHOOK", "").strip()
    email_to = os.environ.get("ARCHIOSK_ALERT_EMAIL", "").strip()

    if webhook:
        payload = json.dumps({"text": "%s\n\n%s" % (subject, body)}).encode("utf-8")
        request = urllib.request.Request(
            webhook, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status >= 300:
                    raise MonitorError("webhook returned HTTP %s" % response.status)
        except MonitorError:
            raise
        except Exception as exc:
            raise MonitorError("webhook post failed: %s" % type(exc).__name__)
        return "webhook"

    if email_to:
        import smtplib
        from email.message import EmailMessage

        smtp = _load_env_smtp()
        host = smtp.get("SMTP_HOST")
        if not host:
            raise MonitorError("ARCHIOSK_ALERT_EMAIL is set but SMTP_HOST is not")
        port = int(smtp.get("SMTP_PORT") or 587)
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = smtp.get("SMTP_FROM") or smtp.get("SMTP_USERNAME") or "root"
        message["To"] = email_to
        message.set_content(body)
        try:
            use_ssl = _truthy(smtp.get("SMTP_USE_SSL"))
            opener = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
            with opener(host, port, timeout=30) as server:
                if not use_ssl and _truthy(smtp.get("SMTP_USE_TLS"), default=True):
                    server.starttls()
                if smtp.get("SMTP_USERNAME"):
                    server.login(smtp["SMTP_USERNAME"], smtp.get("SMTP_PASSWORD", ""))
                server.send_message(message)
        except Exception as exc:
            # Report the exception TYPE only. Several smtplib errors embed the
            # server dialogue, which can echo the username back.
            raise MonitorError("smtp delivery failed: %s" % type(exc).__name__)
        return "email"

    # No sink configured. stderr is captured by systemd into the journal.
    print("%s\n%s" % (subject, body), file=sys.stderr)
    return "journal"


def main():
    parser = argparse.ArgumentParser(
        description="Alert on new nginx [crit]/[alert]/[emerg] lines.")
    parser.add_argument("--dry-run", action="store_true",
                        help="report findings; send nothing and do not touch state")
    parser.add_argument("--reset", action="store_true",
                        help="move the cursor to current EOF without alerting")
    parser.add_argument("--since-start", action="store_true",
                        help="ignore the stored cursor and scan the whole current file")
    args = parser.parse_args()

    state = _read_state()
    offset = int(state.get("offset", 0) or 0)

    try:
        stat = LOG_PATH.stat()
    except OSError as exc:
        raise MonitorError("cannot stat %s: %s" % (LOG_PATH, exc))

    rotated = (state.get("inode") not in (None, stat.st_ino)
               or state.get("device") not in (None, stat.st_dev))
    if rotated or args.since_start:
        offset = 0

    hits, new_offset, identity = _collect(offset)

    if args.reset:
        _write_state(dict({"offset": stat.st_size}, **identity))
        print("cursor reset to EOF (%d bytes); nothing alerted" % stat.st_size)
        return 0

    scanned = new_offset - offset
    actionable, routine = _partition(hits)

    if not actionable:
        # Either nothing matched, or everything that did was routine TLS noise.
        # Both advance the cursor; neither is worth waking anyone for. The
        # routine count is still printed, so suppression stays visible in the
        # journal rather than being silent.
        if not args.dry_run:
            _write_state(dict({"offset": new_offset}, **identity))
        print("ok: %d new bytes scanned%s, no actionable [crit]/[alert]/[emerg]"
              "%s"
              % (scanned, " (log rotated)" if rotated else "",
                 " (%d routine TLS line(s) suppressed)" % len(routine) if routine else ""))
        return 0

    subject = "[ARCHIOSK] %d nginx critical line(s) on %s" % (
        len(actionable), socket.gethostname())
    body = (
        "%d new actionable [crit]/[alert]/[emerg] line(s) in %s\n"
        "(%d bytes scanned%s; %d routine TLS line(s) suppressed)\n\n"
        "GROUPED:\n%s\n\nMOST RECENT:\n%s\n"
        % (len(actionable), LOG_PATH, scanned,
           ", log rotated" if rotated else "", len(routine),
           _summarise(actionable), "\n".join(actionable[-5:]))
    )

    if args.dry_run:
        print("DRY RUN - would alert, and would NOT advance the cursor\n")
        print(subject)
        print(body)
        return 0

    sink = _deliver(subject, body)
    # Only now is it safe to advance. See the module docstring.
    _write_state(dict({"offset": new_offset}, **identity))
    print("alerted via %s: %d actionable line(s), %d routine suppressed; cursor -> %d"
          % (sink, len(actionable), len(routine), new_offset))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except MonitorError as exc:
        print("nginx-crit-monitor: %s" % exc, file=sys.stderr)
        sys.exit(1)
