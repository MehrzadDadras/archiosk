from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "case_workspace.html").read_text(encoding="utf-8")
DETAIL = (ROOT / "templates" / "_spin_run_detail.html").read_text(encoding="utf-8")
ROUTE = (ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")


def test_history_rows_are_compact_toggleable_run_summaries():
    assert 'class="spin-history-item"' in TEMPLATE
    assert 'class="spin-history-summary"' in TEMPLATE
    assert 'class="spin-history-chevron"' in TEMPLATE
    assert "{{ run.kind_label }}" in TEMPLATE
    assert 'class="spin-timestamp" data-spin-timestamp="{{ run.created_at }}"' in TEMPLATE
    assert "{{ run.findings|length }} finding(s)" in TEMPLATE
    assert "FAILED" in TEMPLATE
    assert 'data-spin-run-id="{{ run.id }}"' in TEMPLATE


def test_history_uses_native_keyboard_details_and_selected_run_expansion():
    assert "<summary class=\"spin-history-summary\" aria-expanded=" in TEMPLATE
    assert "{% if selected_spin_run_view and run.id == selected_spin_run_view.id %} open{% endif %}" in TEMPLATE
    assert "spin_state_reports_view" in TEMPLATE
    assert "spin_state_reports_view =" in ROUTE


def test_expanded_detail_reuses_existing_run_metadata_and_findings():
    for marker in (
        "Spin Run ID",
        "Completed:",
        "Baseline:",
        "Sources examined:",
        "Evidence delta since baseline:",
        "Prior findings reassessed:",
        "Classification summary:",
        "Findings",
    ):
        assert marker in DETAIL
    assert "{{ run.id }}" in DETAIL
    assert "{{ run_report.presented_findings }}" in DETAIL or "run_report.presented_findings" in DETAIL


def test_history_detail_is_included_per_run_and_timestamp_formatter_is_reused():
    assert "{% include '_spin_run_detail.html' %}" in TEMPLATE
    assert "spin_timestamps.js" in TEMPLATE
    assert "sorted(workspace.spin_runs, key=lambda r: r.get(\"created_at\") or \"\", reverse=True)" in ROUTE
