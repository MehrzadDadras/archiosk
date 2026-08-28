"""
CLAUDE-CALM-LAKE-SURFACE-PROTOTYPE-01 -- a bounded, visually inspectable
prototype of the Calm Lake surface.

WHY THIS IS ITS OWN FILE, and not three routes added to routes/portal.py:
a prototype's most important property is that it can be DELETED in one
`git rm` when the experiment concludes. Folding it into a permanent route
module entangles a throwaway with code that has to survive. Nothing else
imports this module; app.py's registration line is the only reference.

WHAT IT IS FOR: giving the Product Owner something to LOOK at, so the
surface grammar in governance/proposals/surface-vs-substrate-interaction-
grammar.md can be judged visually instead of argued from prose. It renders
one representative workspace at desktop and at 390x844 with the SAME
grammar, and it demonstrates the four things the directive named -- calm
dominant surface, progressive disclosure, grounded provenance, and an
actionability horizon ordered by consequence x remaining window.

WHAT IT IS NOT:
- Not a route into real evidence. Every value below is FIXTURE data, held
  in this module, and the surface says so on its face (see PROTOTYPE_NOTICE).
  It reads no CaseWorkspaceStore, touches no AnalysisRun, writes nothing.
- Not authorization to reduce chrome anywhere else. The grammar's SS5.3
  sequencing constraint still binds `main`: pdf_viewer.js resolves 30
  document controls against base.html's menu bar, so chrome deletion
  before a canvas-native Look vocabulary exists deletes navigation. This
  prototype builds a Look vocabulary to LOOK at; it does not remove one.
- Not a merge of origin/spike/multi-surface-canvas, which remains unmerged
  and is a separate Product Owner decision.

SYNTHETIC IDENTITY: the workspace renders as Project Smoke Detector (PSD)
per CLAUDE.md's synthetic test-project identity rule. The document names
are likewise synthetic; no real project, owner, site or source document is
named anywhere in this file.
"""
from __future__ import annotations

from flask import Blueprint, abort, render_template, session

from services.auth import admin_required, is_admin

calm_lake_bp = Blueprint("calm_lake", __name__, url_prefix="/admin/calm-lake")


# ---------------------------------------------------------------------------
# The basis vocabulary -- CLOSED, and owned by whatever derives a citation.
#
# This follows the discipline RESOLUTION_STATUS_* (services/case_workspace.py
# :1177), METADATA_RELIABILITY_* (:3967) and KNOWN_EVIDENCE_CLASSES (:3880)
# already establish in this codebase: the evaluator names its own outcome
# and a caller never supplies one. It is deliberately NOT a parallel
# mechanism -- it is the same shape applied to a property those three do not
# cover, which is what a citation is grounded in.
#
# The grammar's SS4.2 rule is what these exist to make enforceable:
#
#   "Every citation surface must be able to state its own basis, and bases
#    that differ in strength must not be rendered identically."
#
# BASIS_ASSERTED is the dangerous one and the reason the vocabulary is
# written down at all. The blind trial's Arm B parsed sheet tokens out of a
# finding's own prose and rendered them as confident deep links; its subject
# trusted them completely. A citation that can lie carries more authority
# than a UUID, because a raw id is inert and obviously unhelpful while a
# fluent clickable citation TERMINATES INQUIRY. So `asserted` may never
# render in the same visual form as `read` or `located`, and the prototype's
# stylesheet enforces that difference rather than leaving it to good
# intentions -- see .cl-basis--asserted in static/css/calm_lake.css.
# ---------------------------------------------------------------------------
BASIS_LOCATED = "located"    # a specific region of a specific page
BASIS_READ = "read"          # a document the analysis actually opened
BASIS_ASSERTED = "asserted"  # named in the claim's text; NOT verified as read
BASIS_NONE = "none"          # no basis on record

KNOWN_CITATION_BASES = (BASIS_LOCATED, BASIS_READ, BASIS_ASSERTED, BASIS_NONE)

BASIS_LABELS = {
    BASIS_LOCATED: "located",
    BASIS_READ: "read",
    BASIS_ASSERTED: "named only",
    BASIS_NONE: "no basis on record",
}

# What each basis is allowed to CLAIM, in words, at Tier 1. These strings are
# the anti-fluency rule made concrete: `asserted` is phrased as a statement
# about the sentence ("the finding names it"), never as a statement about
# where the analysis has been.
BASIS_MEANINGS = {
    BASIS_LOCATED: "read at a specific region of a specific page",
    BASIS_READ: "a document this analysis opened",
    BASIS_ASSERTED: "the finding's own sentence names it - not verified as read",
    BASIS_NONE: "nothing on record establishes where this came from",
}

# The surface must never present itself as a live record. Rendered on the
# face of the prototype, not buried in a comment.
PROTOTYPE_NOTICE = (
    "Prototype surface - every finding, document and date below is fixture "
    "data held in routes/calm_lake_prototype.py. Nothing here is a record."
)


# ---------------------------------------------------------------------------
# The Actionability Horizon.
#
# The directive's constraint: order by CONSEQUENCE and REMAINING WINDOW OF
# INTERVENTION, not by a static severity badge. Two things follow, and both
# are deliberate departures from how `main` renders findings today.
#
# 1. A window is a fact with a basis, exactly like a citation. "4 days" is
#    an assertion about the world, and an interface that renders it in the
#    same weight whether it came from a read schedule or from a sentence is
#    committing the SS4.2 fluency error one level up from citations. So each
#    item's window carries its own basis, and BASIS_NONE renders as a real
#    answer ("no basis on record") rather than as a blank or an omission.
#
# 2. Ordering must be inspectable. A ranked list whose ranking cannot be
#    interrogated is a severity badge with extra steps. horizon_order()
#    below is eleven lines and its output is rendered as prose next to the
#    list, so a reader can disagree with the ordering rather than absorb it.
#
# `severity` is retained on each item ON PURPOSE, and it is NOT what the
# ordering uses. Keeping it visible is what makes the departure legible:
# DAMPER-SD-14 outranks DOOR-D-106 while both are "high", because one has
# four days left and the other thirty-one.
# ---------------------------------------------------------------------------

THRESHOLD_DAYS = 7
"""Below this many days remaining, an item stops waiting to be found.

This is the actionability threshold the directive names -- the line the
machinery crosses to surface unbidden. It is a fixture constant here, not a
tuned parameter; the prototype's claim is that a threshold BELONGS in the
model, not that seven is the right number."""


def horizon_order(items):
    """Order the horizon by consequence x remaining window.

    Unresolvable windows (BASIS_NONE) sort last, not first. An item whose
    urgency cannot be established must not be able to claim the top of the
    list by being unknown -- that is how "we don't know" becomes "it's
    urgent", which is the fluency failure in scheduling clothes.
    """
    rank = {"high": 0, "medium": 1, "low": 2}

    def key(item):
        window = item["window"]
        unknown = window["basis"] == BASIS_NONE
        days = window["days_remaining"]
        return (
            0 if (not unknown and days <= THRESHOLD_DAYS) else 1,
            1 if unknown else 0,
            days if days is not None else 10**6,
            rank.get(item["severity"], 3),
        )

    return sorted(items, key=key)


def window_spent_percent(window):
    """How much of the original window is already gone, 0-100.

    This is the "temporal half-life": the banner renders elapsed fraction,
    not just days left. Two findings both showing "4 days" are not the same
    situation if one started with a 21-day window and the other with 5, and
    a static badge cannot express that difference at all.

    Returns None when there is no basis for a window, and the surface must
    render that as a stated absence rather than as a full or empty bar --
    an empty bar would read as "no time has passed", which is a claim.
    """
    total = window.get("total_days")
    left = window.get("days_remaining")
    if not total or left is None:
        return None
    return max(0, min(100, round(((total - left) / total) * 100)))


# ---------------------------------------------------------------------------
# The four verbs. Settled elsewhere, restated here as data so that ONE list
# renders the bar at 390px and at 1600px -- which is what makes "a single
# interaction grammar" checkable rather than merely asserted. If a verb
# appears at one width and not the other, this list is not what rendered it.
#
# `Commit` is present at both widths and is DISABLED until something is
# selected. That is deliberate and is the "selection supplies context, never
# authorization" rule made visible: pointing at a finding is what gives the
# Composer and the Commit gate their subject, and it is emphatically not what
# grants permission to act on it.
# ---------------------------------------------------------------------------
VERBS = [
    {"id": "look", "label": "Look", "hint": "pan, zoom, fit, change sheet"},
    {"id": "point", "label": "Point", "hint": "select an object and see what it rests on"},
    {"id": "ask", "label": "Ask", "hint": "Composer, bound to the current selection"},
    {"id": "commit", "label": "Commit", "hint": "governed action, approval-gated"},
]


# ---------------------------------------------------------------------------
# Fixture. Synthetic throughout (see module docstring).
#
# The three findings are chosen to exercise every rule the grammar states,
# so a visual judgement can be made against real cases rather than lorem:
#
#   DAMPER-SD-14  contrastive two-sided disclosure (6.1), a stated
#                 denominator (6.2), a closing window, and the governed
#                 action boundary (6.4). Crosses the threshold, so it is
#                 the one item that surfaces unbidden.
#   DOOR-D-106    the repository's OWN validated example, kept because both
#                 blind subjects reconstructed its two-sided form by hand.
#                 Same severity as SD-14, wide window, ranked below it.
#   PRESSURE-STAIR-2  carries a BASIS_ASSERTED side and a BASIS_NONE window.
#                 This is the case the surface must render WORSE-looking
#                 than the other two, and the reason the vocabulary exists.
# ---------------------------------------------------------------------------

DOCUMENTS = [
    {"id": "M-201", "name": "M-201 Level 2 Mechanical Plan", "sheets": 2},
    {"id": "M-601", "name": "M-601 Smoke Damper Schedule", "sheets": 1},
    {"id": "A-101", "name": "A-101 Level 1 Floor Plan", "sheets": 1},
    {"id": "A-601", "name": "A-601 Door Schedule", "sheets": 1},
    {"id": "SP-001", "name": "SP-001 Smoke Management Narrative", "sheets": 14},
    {"id": "CS-01", "name": "CS-01 Construction Schedule Rev C", "sheets": 3},
]

FINDINGS = [
    {
        "id": "DAMPER-SD-14",
        "tag": "SD-14",
        "claim": "Smoke damper SD-14 is shown on the Level 2 mechanical plan "
                 "but has no row in the smoke damper schedule.",
        "severity": "high",
        "verification": "Machine finding - unverified",
        "canvas": {"x": 34, "y": 41},
        # Tier 1, contrastive: role first, then document, then basis. The
        # role is the finding's entire content and a flat list discards it.
        "sides": [
            {
                "role": "present",
                "document": "M-201 Level 2 Mechanical Plan",
                "basis": BASIS_LOCATED,
                "at": "sheet 2, grid E-4",
                "detail": "tagged SD-14 on the return duct at the 2-hour "
                          "corridor wall",
            },
            {
                "role": "absent",
                "document": "M-601 Smoke Damper Schedule",
                "basis": BASIS_READ,
                "at": None,
                # Negative-form citation. Per 4.2's corollary a citation must
                # not assert a LOCATION for a thing that has none: the entire
                # content of this side is that SD-14 is not there.
                "detail": "schedule runs SD-11, SD-12, SD-13, SD-15 - no "
                          "SD-14 row. The gap sits between SD-13 and SD-15.",
            },
        ],
        # 6.2: absence is only meaningful against a checked set.
        "scope": {
            "checked": "9 damper tags on M-201",
            "matched": 8,
            "unmatched": 1,
            "documents_examined": 5,
        },
        "consequence": "The corridor wall SD-14 sits in is scheduled to be "
                       "closed and fire-stopped. After closure the damper is "
                       "not installable without demolishing finished work.",
        # WHAT CHANGED. A disturbance needs a cause, or the surface is just
        # an alarm. This is also what makes the finding NEW rather than
        # merely true - the schedule revision is why a calm surface is
        # entitled to interrupt today and was not entitled to yesterday.
        "what_changed": {
            "when": "2026-08-24",
            "detail": "M-601 was superseded by Rev C. SD-14 had a row on "
                      "Rev B and has none on Rev C. Nothing on M-201 changed.",
        },
        "window": {
            "days_remaining": 4,
            # total_days is what makes the horizon TEMPORAL rather than a
            # severity badge with a number on it: the surface renders the
            # fraction of the original window already spent, so the same
            # finding reads differently on day 2 and on day 18 without any
            # human re-triaging it.
            "total_days": 21,
            "closes_on": "wall closure, Level 2 corridor",
            "basis": BASIS_READ,
            "source": "CS-01 Construction Schedule Rev C",
        },
        "action": {"label": "Issue RFI", "governed": True},
    },
    {
        "id": "DOOR-D-106",
        "tag": "D-106",
        "claim": "Door D-106 is tagged on the Level 1 floor plan but has no "
                 "row in the door schedule.",
        "severity": "high",
        "verification": "Machine finding - unverified",
        "canvas": {"x": 63, "y": 68},
        "sides": [
            {
                "role": "present",
                "document": "A-101 Level 1 Floor Plan",
                "basis": BASIS_LOCATED,
                "at": "sheet 1, grid C-2",
                "detail": "tagged D-106 at the stair vestibule",
            },
            {
                "role": "absent",
                "document": "A-601 Door Schedule",
                "basis": BASIS_READ,
                "at": None,
                "detail": "schedule runs D-101 through D-105, then D-107 - "
                          "no D-106 row. The gap sits between D-105 and D-107.",
            },
        ],
        "scope": {
            "checked": "7 door tags on A-101",
            "matched": 6,
            "unmatched": 1,
            "documents_examined": 4,
        },
        "consequence": "The door's fire rating is unspecified. It is on the "
                       "hardware submittal, which has not been issued.",
        "what_changed": {
            "when": "2026-08-11",
            "detail": "First raised when A-601 was ingested. Neither sheet "
                      "has been revised since.",
        },
        "window": {
            "days_remaining": 31,
            "total_days": 48,
            "closes_on": "door hardware submittal",
            "basis": BASIS_READ,
            "source": "CS-01 Construction Schedule Rev C",
        },
        "action": {"label": "Issue RFI", "governed": True},
    },
    {
        "id": "PRESSURE-STAIR-2",
        "tag": "Stair 2",
        "claim": "The smoke management narrative states 0.05 in. w.g. across "
                 "the Stair 2 door; the mechanical set is said to carry a "
                 "different value.",
        "severity": "high",
        "verification": "Machine finding - unverified",
        "canvas": {"x": 18, "y": 74},
        "sides": [
            {
                "role": "states",
                "document": "SP-001 Smoke Management Narrative",
                "basis": BASIS_READ,
                "at": None,
                "detail": "section 4.2 gives 0.05 in. w.g. at the Stair 2 "
                          "door, doors closed",
            },
            {
                # The dangerous cell, rendered deliberately. The finding's
                # own sentence names the mechanical set; nothing on record
                # says this analysis opened it. It must read as a fact about
                # the SENTENCE, never as a fact about where the analysis has
                # been -- and it must not look like the side above it.
                "role": "named in the finding",
                "document": "the mechanical set",
                "basis": BASIS_ASSERTED,
                "at": None,
                "detail": "the finding's sentence refers to a differing value. "
                          "No document on record was opened to confirm it, and "
                          "no specific sheet is identified.",
            },
        ],
        "scope": {
            "checked": "not established",
            "matched": None,
            "unmatched": None,
            "documents_examined": 1,
        },
        "consequence": "If the two values genuinely differ, the stair "
                       "pressurization design is unresolved. Whether they "
                       "differ has not been established.",
        "what_changed": {
            "when": None,
            "detail": "Not established. No revision on record is known to "
                      "have caused this, and it may have been true since "
                      "ingestion.",
        },
        "window": {
            "days_remaining": None,
            "total_days": None,
            "closes_on": None,
            "basis": BASIS_NONE,
            "source": None,
        },
        # No governed action offered. The surface must not invite a Commit
        # on a claim whose own basis is a sentence -- effortful friction at
        # the approval gate is a feature, and offering the gate at all here
        # would manufacture the confidence 4 forbids.
        "action": None,
    },
]

PROJECT = {
    "name": "Project Smoke Detector",
    "short": "PSD",
    "discipline": "Smoke Management Analysis",
    "sheet": "M-201 Level 2 Mechanical Plan",
    "sheet_index": "2 of 2",
}


@calm_lake_bp.route("/")
@admin_required
def surface():
    """The prototype surface. Read-only, fixture-fed, writes nothing."""
    if not is_admin() or not session.get("developer_mode"):
        # Same double gate routes/portal.py's developer tooling uses: admin
        # alone is not enough, Developer Mode must be explicitly on.
        abort(403)

    horizon = horizon_order(FINDINGS)
    for finding in horizon:
        finding["window"]["spent_percent"] = window_spent_percent(finding["window"])
    surfaced = [
        f for f in horizon
        if f["window"]["basis"] != BASIS_NONE
        and f["window"]["days_remaining"] is not None
        and f["window"]["days_remaining"] <= THRESHOLD_DAYS
    ]
    return render_template(
        "calm_lake_prototype.html",
        project=PROJECT,
        documents=DOCUMENTS,
        verbs=VERBS,
        horizon=horizon,
        surfaced=surfaced,
        threshold_days=THRESHOLD_DAYS,
        basis_labels=BASIS_LABELS,
        basis_meanings=BASIS_MEANINGS,
        prototype_notice=PROTOTYPE_NOTICE,
        basis_none=BASIS_NONE,
        basis_asserted=BASIS_ASSERTED,
        basis_located=BASIS_LOCATED,
    )
