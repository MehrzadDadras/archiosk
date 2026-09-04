"""Browser contract for the shared elapsed-time status utility."""
from __future__ import annotations

from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

SCRIPT = (Path(__file__).resolve().parents[1] / "static" / "js" / "elapsed_status.js").read_text(encoding="utf-8")


def test_timer_starts_ticks_stops_and_resets():
    with playwright.sync_playwright() as api:
        browser = api.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("<html><body></body></html>")
        page.add_script_tag(content=SCRIPT)
        page.evaluate("window.__status = ArchioskElapsedStatus.start('First Spin')")
        assert page.locator("#elapsed-action-status").inner_text() == "First Spin started — 00h:00m:00s"
        page.wait_for_timeout(1100)
        assert "First Spin running — 00h:00m:01s" in page.locator("#elapsed-action-status").inner_text()
        page.evaluate("window.__status.completed()")
        completed = page.locator("#elapsed-action-status").inner_text()
        page.wait_for_timeout(1100)
        assert page.locator("#elapsed-action-status").inner_text() == completed
        page.evaluate("ArchioskElapsedStatus.start('Composer').failed()")
        assert page.locator("#elapsed-action-status").inner_text() == "Composer failed — 00h:00m:00s"
        browser.close()


def test_format_and_action_coverage_are_explicit():
    assert "00h:" not in SCRIPT
    for action in ("Folder upload and project creation", "File upload and project creation",
                   "First Spin", "Delta Spin", "Composer", "Report export"):
        assert action in SCRIPT
    for state in ("started", "running", "completed", "failed", "cancelled"):
        assert state in SCRIPT
