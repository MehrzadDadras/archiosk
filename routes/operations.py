"""
CLAUDE-CA1D-INSTRUMENT-RAIL-01 -- smallest proof slice of the Operations
page half of the four-part Instrument Rail split (see
governance/current/wb1-adaptive-workbench.md and this stage's own
Plan-Mode report): persistent, deployment-wide admin machinery gets a
page at the perimeter, reached the same way Security Department already
is -- not a new rail column.

Admin-only throughout (@admin_required), same reasoning routes/security.py
already documents: this codebase has no role finer than admin/read_only.

Deliberately minimal this stage: wires services.diagnostics.py's
TechnicalTelemetry (built CLAUDE-P31, never previously rendered anywhere)
into a real page, as the first proof that a previously-unwired backend
diagnostic primitive has a legitimate peripheral home. Repository/git
state, subagent orchestration detail, and terminal integration are
explicitly out of scope for this tranche -- see the Plan-Mode report's
Section K.
"""
from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from services.auth import admin_required
from services.diagnostics import build_technical_telemetry

operations_bp = Blueprint("operations", __name__, url_prefix="/operations")


@operations_bp.route("/")
@admin_required
def department_home():
    telemetry = build_technical_telemetry(
        app_version=current_app.config["STATIC_VERSION"],
        route=request.endpoint,
    )
    return render_template("operations.html", telemetry=telemetry)
