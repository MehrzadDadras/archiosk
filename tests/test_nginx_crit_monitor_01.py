"""
CLAUDE-NGINX-CRIT-MONITOR-01 - the nginx critical-error monitor's properties.

WHY THIS IS TESTED HERE AT ALL

deploy/nginx_crit_monitor.py runs on the VPS, not inside this application - it
imports nothing from `services` and the app imports nothing from it. It is
tested here for the same reason tools/storage_bridge_agent.py is (see
test_storage_bridge_agent_04.py): a script that runs unattended on a production
host, whose whole job is to be trusted when it says nothing is wrong, is exactly
the kind of code that must not be verified only by having been run once by hand.

Loaded by path, because deploy/ is not an importable package and the script must
stay runnable as a bare file with only the system python3.

THE TWO PROPERTIES THAT MATTER

It must not LOSE an alert: the cursor advances only after delivery succeeds.
It must not INVENT one: rotation is detected by inode, so a fresh 0-byte file
after logrotate does not replay the previous day.

Both are asserted below against real behaviour rather than by reading the code.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "deploy" / "nginx_crit_monitor.py"
NL = "\n"

CRIT = ('2026/08/31 15:55:02 [crit] 413469#413469: *80650 open() '
        '"/var/lib/nginx/body/0000000082" failed (13: Permission denied), '
        'client: 1.2.3.4, server: archiosk.com, request: "POST /x HTTP/1.1"')
CRIT2 = CRIT.replace("*80650", "*80651").replace("0000000082", "0000000083")
PLAIN_ERROR = ('2026/08/31 15:55:10 [error] 1#1: *1 open() "/nope" failed '
               '(2: No such file or directory)')
EMERG = '2026/08/31 16:00:00 [emerg] 1#1: bind() to 0.0.0.0:443 failed (98)'
SSL_NOISE = ('2026/08/31 17:20:11 [crit] 413469#413469: *81148 '
             'SSL_do_handshake() failed (SSL: error:0A00006C:SSL routines::bad '
             'key share) while SSL handshaking, client: 157.245.5.171, '
             'server: 0.0.0.0:443')

_COUNTER = [0]


def _load(tmp_dir: Path, logname: str = "error.log"):
    """A fresh module instance bound to temp paths, never the real host paths."""
    os.environ["ARCHIOSK_NGINX_ERROR_LOG"] = str(tmp_dir / logname)
    os.environ["ARCHIOSK_MONITOR_STATE"] = str(tmp_dir / "state.json")
    os.environ["ARCHIOSK_ENV_FILE"] = str(tmp_dir / "absent.env")
    os.environ.pop("ARCHIOSK_ALERT_WEBHOOK", None)
    os.environ.pop("ARCHIOSK_ALERT_EMAIL", None)
    _COUNTER[0] += 1
    spec = importlib.util.spec_from_file_location(
        "_nginx_crit_monitor_%d" % _COUNTER[0], _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_nginx_monitor_"))
        self.log = self.tmp / "error.log"
        self.state = self.tmp / "state.json"

    def tearDown(self):
        for name in ("ARCHIOSK_ALERT_IGNORE", "ARCHIOSK_NGINX_ERROR_LOG",
                     "ARCHIOSK_MONITOR_STATE", "ARCHIOSK_ENV_FILE"):
            os.environ.pop(name, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_main(self, module, argv=()):
        sys.argv = ["nginx_crit_monitor.py"] + list(argv)
        return module.main()


class ItDetectsWhatItShouldTests(_Base):
    def test_crit_is_detected(self):
        self.log.write_text(CRIT + NL, encoding="utf-8")
        module = _load(self.tmp)
        hits, _, _ = module._collect(0)
        self.assertEqual(len(hits), 1)

    def test_emerg_is_detected(self):
        self.log.write_text(EMERG + NL, encoding="utf-8")
        module = _load(self.tmp)
        hits, _, _ = module._collect(0)
        self.assertEqual(len(hits), 1)

    def test_plain_error_severity_is_not_alerted_on(self):
        # [error] is ordinary and constant; alerting on it is alerting on noise.
        self.log.write_text((PLAIN_ERROR + NL) * 5, encoding="utf-8")
        module = _load(self.tmp)
        hits, _, _ = module._collect(0)
        self.assertEqual(hits, [])


class ItMustNotLoseAnAlertTests(_Base):
    """The cursor is only allowed to move past a line that was delivered."""

    def test_cursor_does_not_advance_when_delivery_fails(self):
        self.log.write_text(CRIT + NL, encoding="utf-8")
        module = _load(self.tmp)

        def failing_sink(subject, body):
            raise module.MonitorError("simulated sink outage")

        module._deliver = failing_sink
        with self.assertRaises(module.MonitorError):
            self.run_main(module)
        self.assertFalse(
            self.state.exists(),
            "a failed delivery must leave the cursor alone so the next run "
            "re-reports the line instead of swallowing it")

    def test_the_line_is_re_reported_on_the_next_run_after_a_failure(self):
        self.log.write_text(CRIT + NL, encoding="utf-8")
        module = _load(self.tmp)
        module._deliver = lambda s, b: (_ for _ in ()).throw(
            module.MonitorError("down"))
        with self.assertRaises(module.MonitorError):
            self.run_main(module)

        recovered = _load(self.tmp)
        hits, _, _ = recovered._collect(0)
        self.assertEqual(len(hits), 1, "the alert must still be pending")

    def test_partial_trailing_line_is_not_consumed(self):
        # nginx mid-write. Consuming half a line would split one fault across
        # two alerts and lose the half that never matched.
        self.log.write_bytes((CRIT + NL).encode("utf-8")
                             + b'2026/08/31 18:00:00 [crit] truncated')
        module = _load(self.tmp)
        hits, new_offset, _ = module._collect(0)
        self.assertEqual(len(hits), 1)
        self.assertEqual(new_offset, len((CRIT + NL).encode("utf-8")))


class ItMustNotInventAnAlertTests(_Base):
    def test_second_run_over_unchanged_file_reports_nothing(self):
        self.log.write_text(CRIT + NL, encoding="utf-8")
        module = _load(self.tmp)
        self.run_main(module)
        offset = json.loads(self.state.read_text(encoding="utf-8"))["offset"]

        again = _load(self.tmp)
        hits, _, _ = again._collect(offset)
        self.assertEqual(hits, [])

    def test_only_bytes_appended_since_last_run_are_reported(self):
        self.log.write_text(CRIT + NL, encoding="utf-8")
        module = _load(self.tmp)
        self.run_main(module)
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write(CRIT2 + NL)

        again = _load(self.tmp)
        offset = json.loads(self.state.read_text(encoding="utf-8"))["offset"]
        hits, _, _ = again._collect(offset)
        self.assertEqual(len(hits), 1)
        self.assertIn("0000000083", hits[0])

    def test_rotation_is_detected_by_inode_not_by_size(self):
        # logrotate runs daily here with `create 0640 www-data adm`. A size-only
        # check would see 0 < stored offset, reset, and re-report the whole new
        # file - every night, forever.
        self.log.write_text((CRIT + NL) * 3, encoding="utf-8")
        module = _load(self.tmp)
        self.run_main(module)
        before = json.loads(self.state.read_text(encoding="utf-8"))

        self.log.unlink()
        self.log.write_text(CRIT2 + NL, encoding="utf-8")
        rotated = _load(self.tmp)
        self.run_main(rotated)
        after = json.loads(self.state.read_text(encoding="utf-8"))

        self.assertNotEqual(before["inode"], after["inode"])
        self.assertEqual(after["offset"], self.log.stat().st_size)

    def test_dry_run_writes_no_state_at_all(self):
        self.log.write_text(CRIT + NL, encoding="utf-8")
        module = _load(self.tmp)
        self.run_main(module, ["--dry-run"])
        self.assertFalse(self.state.exists())


class ItFailsClosedTests(_Base):
    def test_missing_log_exits_nonzero_rather_than_reporting_ok(self):
        module = _load(self.tmp, logname="not_there.log")
        with self.assertRaises(module.MonitorError):
            self.run_main(module)

    def test_corrupt_state_refuses_rather_than_starting_over(self):
        # Silently restarting from 0 would replay the whole file as new alerts.
        self.log.write_text(CRIT + NL, encoding="utf-8")
        self.state.write_text("{ not json", encoding="utf-8")
        module = _load(self.tmp)
        with self.assertRaises(module.MonitorError):
            self.run_main(module)

    def test_invalid_ignore_regex_refuses_rather_than_ignoring_everything(self):
        self.log.write_text(CRIT + NL, encoding="utf-8")
        module = _load(self.tmp)
        os.environ["ARCHIOSK_ALERT_IGNORE"] = "([unclosed"
        with self.assertRaises(module.MonitorError):
            module._partition([CRIT])


class NoiseSuppressionTests(_Base):
    """A monitor nobody reads is the same as no monitor."""

    def test_routine_tls_noise_alone_does_not_alert(self):
        # 18 of the 71 [crit] lines in the real log at install time were
        # scanner TLS handshake failures. They are permanent background.
        self.log.write_text((SSL_NOISE + NL) * 18, encoding="utf-8")
        module = _load(self.tmp)
        hits, _, _ = module._collect(0)
        actionable, routine = module._partition(hits)
        self.assertEqual(actionable, [])
        self.assertEqual(len(routine), 18)

    def test_the_cursor_still_advances_past_suppressed_noise(self):
        self.log.write_text((SSL_NOISE + NL) * 3, encoding="utf-8")
        module = _load(self.tmp)
        self.run_main(module)
        self.assertEqual(
            json.loads(self.state.read_text(encoding="utf-8"))["offset"],
            self.log.stat().st_size)

    def test_a_real_fault_buried_in_noise_still_alerts(self):
        """Suppression must never swallow the defect this was built to catch."""
        self.log.write_text((SSL_NOISE + NL) * 18 + CRIT + NL, encoding="utf-8")
        module = _load(self.tmp)
        hits, _, _ = module._collect(0)
        actionable, routine = module._partition(hits)
        self.assertEqual(len(actionable), 1)
        self.assertIn("Permission denied", actionable[0])
        self.assertEqual(len(routine), 18)

    def test_suppressed_count_is_reported_not_hidden(self):
        self.log.write_text((SSL_NOISE + NL) * 3 + CRIT + NL, encoding="utf-8")
        module = _load(self.tmp)
        captured = {}

        def capture(subject, body):
            captured["body"] = body
            return "test"

        module._deliver = capture
        self.run_main(module)
        self.assertIn("3 routine TLS line(s) suppressed", captured["body"])


class SummaryTests(_Base):
    def test_repeats_collapse_into_one_grouped_line(self):
        # The real incident was one defect 51 times. It should read as one
        # problem, not 51.
        self.log.write_text((CRIT + NL) * 40, encoding="utf-8")
        module = _load(self.tmp)
        hits, _, _ = module._collect(0)
        summary = module._summarise(hits)
        self.assertIn("40 x", summary)
        self.assertEqual(len(summary.splitlines()), 1)


class TheShippedUnitFilesMatchTheScriptTests(unittest.TestCase):
    """The units are the install contract; drift between them and the script is
    invisible until the timer fires on a production host."""

    def test_service_invokes_the_path_the_installer_creates(self):
        unit = (_ROOT / "deploy" / "archiosk-nginx-monitor.service").read_text(
            encoding="utf-8")
        self.assertIn("ExecStart=/usr/bin/python3 /usr/local/bin/archiosk-nginx-monitor",
                      unit)

    def test_service_can_actually_read_the_nginx_log(self):
        # The first real timer run failed with EACCES because an empty
        # CapabilityBoundingSet drops CAP_DAC_OVERRIDE and error.log is
        # www-data:adm 0640. Group membership is what fixes it.
        unit = (_ROOT / "deploy" / "archiosk-nginx-monitor.service").read_text(
            encoding="utf-8")
        self.assertIn("SupplementaryGroups=adm", unit)

    def test_state_directory_is_the_only_writable_path(self):
        unit = (_ROOT / "deploy" / "archiosk-nginx-monitor.service").read_text(
            encoding="utf-8")
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("ReadWritePaths=/var/lib/archiosk-nginx-monitor", unit)

    def test_timer_interval_is_five_minutes(self):
        timer = (_ROOT / "deploy" / "archiosk-nginx-monitor.timer").read_text(
            encoding="utf-8")
        self.assertIn("OnUnitActiveSec=5min", timer)
        self.assertIn("Persistent=true", timer)


if __name__ == "__main__":
    unittest.main()
