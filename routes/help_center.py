"""CLAUDE-HELP-CENTER-01 - where the long explanations live instead.

WHY THIS EXISTS. The operational surfaces were growing paragraphs. An access
panel that explains token security in four sentences is a panel a superintendent
reads once and then scrolls past forever, and every line of it competes with the
control they actually came for. Desks carry concise labels and a [?]; the
reasoning lives here.

WHAT IS AND IS NOT DOCUMENTED HERE. Only capabilities that exist. Where a guide
describes something not built, it SAYS SO in the guide rather than describing it
in the present tense - documentation that describes an unbuilt feature is
indistinguishable from a lie to the person reading it on a site.

Authenticated, not public: these guides name real project surfaces and role
scopes, and the sign-in page is deliberately isolated from exactly that kind of
content (see templates/auth_shell.html and CLAUDE-P40-D1).
"""
from __future__ import annotations

from flask import Blueprint, abort, render_template

from services.auth import login_required

help_bp = Blueprint("help_center", __name__)

# A closed set. A help route that renders any template name it is handed is a
# template-injection surface, and "guides" is not a directory anyone should be
# able to walk.
GUIDES = {
    "field-access-passes": {
        "template": "help/field_access_passes.html",
        "title": "Field access passes",
        "summary": "Roles, discipline scope, expiry, QR onboarding and revocation.",
    },
    "spatial-coordination": {
        "template": "help/spatial_coordination.html",
        "title": "Spatial coordination",
        "summary": "Split-pane comparison, vector framing, and where a claim came from.",
    },
    "spin-and-survival-modes": {
        "template": "help/spin_and_survival_modes.html",
        "title": "Spin & Survival Mode",
        "summary": "First Spin, Delta Spin, and the Survival lens - what each is for.",
    },
    "building-box-meetings": {
        "template": "help/building_box_meetings.html",
        "title": "Building Box in meetings",
        "summary": "Running a trailer meeting from a Building Box pass.",
    },
}


@help_bp.route("/help")
@login_required
def index():
    return render_template("help/index.html", guides=GUIDES)


@help_bp.route("/help/<guide>")
@login_required
def guide(guide: str):
    entry = GUIDES.get(guide)
    if entry is None:
        abort(404)
    return render_template(entry["template"], guide_key=guide, guides=GUIDES,
                           title=entry["title"])
