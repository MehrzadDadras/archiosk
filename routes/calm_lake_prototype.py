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
# PROMINENCE - jointly informed by consequence, evidence, authority and
# remaining actionability, and DELIBERATELY NOT A NUMBER.
#
# An earlier revision of this file scored prominence as a weighted product
# and rendered values like 0.771 on the surface. That was wrong twice over,
# and the reasons are worth keeping because both are easy to re-commit:
#
# 1. The precision was manufactured. None of the four weights was measured;
#    they were chosen to make the fixture come out right. A number computed
#    from invented constants LOOKS like evidence and is not - the same
#    fluency failure as a citation parsed from prose, one level up. This
#    repository already carries the concern under its own name: two model
#    self-reported confidence floats still render as precise percentages on
#    `main`, and that is a known open reservation, not a pattern to copy.
#
# 2. A single scalar destroys the reason. "0.319" cannot be argued with.
#    "Its window is established and not yet closing - 31 days remain, 35% of
#    the original 48 elapsed" can be, by anyone, including someone who thinks
#    31 days IS closing for this trade.
#
# So the model below is a small set of stated RULES, and each finding carries
# the reasons it landed where it did, in words. The rules are readable in one
# sitting, disagreeable in specific parts, and carry no false precision.
#
# The four dimensions still all participate. What changed is that they
# combine as conditions rather than as factors:
#
#   Consequence  - how bad if unresolved
#   Evidence     - is every side record-grounded, or does one rest on the
#                  claim's own sentence?
#   Authority    - is there a governed action to take at all?
#   Horizon      - is the window established, and is it closing?
#
# NO BINARY SILENCE. There are two bands and every finding is in one of
# them. `tracked` is not "hidden" - it is a pin on the drawing and a line in
# the tracked band, one tap from its own evidence. A long runway buys quiet,
# never absence.
# ---------------------------------------------------------------------------

THRESHOLD_DAYS = 7
"""Days remaining at or below which a window counts as closing.

An inflection point, not an on/off switch for visibility. The earlier binary
use of this constant is exactly what the two-band model replaces: it removed
a high-consequence, well-evidenced finding from every surface except an
unlabelled dot because its runway was long, which is not calm, it is quiet."""

SPENT_FRACTION_CLOSING = 0.75
"""A window can also close by proportion, not only by absolute days.

Both readings are kept because they disagree in the cases worth catching: a
long window nearly exhausted, and a short window barely begun. Either one
alone would miss half of them."""

PROMINENCE_FOREGROUND = "foreground"
PROMINENCE_TRACKED = "tracked"


def window_is_established(window):
    """A window with no basis on record is not a window, it is a blank.

    It must never read as urgent by default: "we do not know when" becoming
    "act now" is truth-promotion wearing scheduling clothes.
    """
    return window["basis"] != BASIS_NONE and window["days_remaining"] is not None


def window_is_closing(window):
    if not window_is_established(window):
        return False
    if window["days_remaining"] <= THRESHOLD_DAYS:
        return True
    total = window.get("total_days")
    if not total:
        return False
    return ((total - window["days_remaining"]) / float(total)) >= SPENT_FRACTION_CLOSING


def evidence_is_grounded(finding):
    """Every side traces to the record - none rests on the claim's own text.

    Deliberately ALL, not any. Taking "any" would let one located citation
    launder a second leg that is only a sentence, which is precisely the
    failure the basis vocabulary exists to prevent.
    """
    sides = finding.get("sides") or []
    return bool(sides) and all(
        side["basis"] in (BASIS_LOCATED, BASIS_READ) for side in sides
    )


def has_governed_action(finding):
    return bool(finding.get("action"))


def assess(finding):
    """Which band a finding is in, and the reasons, in words.

    Returns reasons for BOTH bands. A foreground finding says what earned it
    the interruption; a tracked finding says what is keeping it quiet - which
    is the more important of the two, because that is the sentence a reader
    needs in order to disagree with the surface.
    """
    window = finding["window"]
    closing = window_is_closing(window)
    grounded = evidence_is_grounded(finding)
    actionable = has_governed_action(finding)
    severe = finding["severity"] == "high"

    # A finding interrupts only when all four line up. Any one of them
    # missing is a real reason not to take over someone's attention.
    tier = (
        PROMINENCE_FOREGROUND
        if (closing and grounded and actionable and severe)
        else PROMINENCE_TRACKED
    )

    reasons = []
    if tier == PROMINENCE_FOREGROUND:
        reasons.append(
            "The window is closing - %d days remain of %d."
            % (window["days_remaining"], window["total_days"])
        )
        reasons.append("Every side of the finding traces to a document on record.")
        reasons.append("A governed action is available.")
    else:
        if not window_is_established(window):
            reasons.append(
                "No basis on record establishes when acting on this stops "
                "being possible, so it is not allowed to interrupt."
            )
        elif not closing:
            spent = window_spent_percent(window)
            reasons.append(
                "The window is established and not yet closing - %d days "
                "remain, %d%% of the original %d elapsed."
                % (window["days_remaining"], spent, window["total_days"])
            )
        if not grounded:
            reasons.append(
                "One side rests on the claim's own sentence rather than on a "
                "document that was opened."
            )
        if not actionable:
            reasons.append("No governed action is available from here.")
        if not severe:
            reasons.append("Consequence is not rated high.")

    return {
        "tier": tier,
        "reasons": reasons,
        "closing": closing,
        "grounded": grounded,
        "actionable": actionable,
        "severe": severe,
    }


def horizon_order(items):
    """Foreground first, then by how soon the window closes.

    Unestablished windows sort last: an item whose urgency cannot be
    established does not get to claim the top of the list by being unknown.
    """
    def key(item):
        state = item.get("prominence") or assess(item)
        window = item["window"]
        return (
            0 if state["tier"] == PROMINENCE_FOREGROUND else 1,
            0 if window_is_established(window) else 1,
            window["days_remaining"] if window["days_remaining"] is not None else 10**6,
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

# ---------------------------------------------------------------------------
# SCENE 1 - THE PAGE-FIELD ENTRY.
#
# A Page-Field is a stable, touchable MINIATURE WINDOW INTO AN ACTUAL SURFACE.
# It is not a navigation button and not an icon card. The interior face carries
# identity - a reader should recognise the drawing without reading the label -
# and the footer strip only confirms what the face already said.
#
# BUILT ONE SPECIMEN AT A TIME. Each interior face is a distinct visual
# species and gets its own review before the next is added, so PAGE_FIELDS
# below holds exactly the faces that have been built. Nothing is declared
# here that the template cannot render.
#
# Recovered from the Holodeck design archive (governance/proposals/
# fish-tank-design-archaeology.md), with the motion deliberately left behind.
# The archive's word-fish swam; these do not. What carried over is the part
# that was load-bearing rather than atmospheric:
#
#   - The object is a real, focusable <button> with pointer-events. The
#     archive's first attempt (v1.9) was pointer-events:none and faked being
#     caught with cursor-distance arithmetic - it LOOKED interactive and was
#     inert to keyboard and touch entirely. That is the failure this avoids.
#
#   - CHANNEL SEPARATION. Both surviving archive engines moved their objects
#     by LAYOUT POSITION - `left`/`top` in archiosk_holodeck_v_3.html,
#     `margin-*` keyframes in v2.20 - and neither ever wrote `transform`,
#     because a running animation on `transform` wins the cascade over the
#     `:hover`/`:focus-visible` transform and silently deletes the focus
#     affordance. The physics owns position; the interaction state owns
#     `transform`. Standing still does not make that rule optional: this
#     surface reserves `transform` for elevation and expansion alone.
#
#   - PROXIMITY MAY CHANGE APPEARANCE, NEVER POSITION. v1.9 drifted its fish
#     toward the cursor and so could not be acquired; v_3.html kept the
#     proximity band and deleted the drift. Territory therefore stops being a
#     wander-lane and becomes DETERMINISTIC LAYOUT - the archive gave each
#     object an elliptical home orbit so it stayed roughly findable, and a
#     still field gives it an exact one, which is strictly better: the same
#     surface is in the same place every visit, and is remembered across the
#     expansion so it can contract back into its own coordinate.
#
# The archive reached this position itself. Its v3.0 introduced `signal-fish`
# - Risk, Assumption, Decision, RFI, Cost - positioned by static CSS and never
# touched by the animation loop. The moment the objects stopped meaning "where
# you go" and started meaning "what you must not miss", they stopped moving.
#
# WHY A MINIATURE NEEDS A BASIS, exactly like a citation does.
#
# A tile showing a picture of a surface makes a claim - "this is what that
# surface looks like". A picture that is actually a stale cache makes that
# claim more fluently than any sentence could, and terminates inquiry faster,
# which is the Arm B failure in visual form. So the miniature carries its own
# basis in the same closed, derivation-owned discipline the citations use:
#
#   live  - this IS the surface, rendered now from the same markup the
#           workspace renders. It cannot be stale because it is not a copy.
#           Structurally enforced: _calm_lake_plan.html defines the geometry
#           once and both the full canvas and the miniature call that macro.
#   kind  - a schematic standing for the KIND of surface. Honest about being
#           a category face; never pretends to be specific content.
#
# There is deliberately no `cached` member. A captured thumbnail is the one
# representation that cannot state its own age from inside itself, and
# nothing here needs it - standing still is what makes `live` affordable.
# ---------------------------------------------------------------------------

MINIATURE_LIVE = "live"
MINIATURE_KIND = "kind"

KNOWN_MINIATURE_BASES = (MINIATURE_LIVE, MINIATURE_KIND)

MINIATURE_MEANINGS = {
    MINIATURE_LIVE: "the surface itself, rendered now - not a copy",
    MINIATURE_KIND: "a schematic for this kind of surface, not its content",
}

# The miniature crops to the building extent rather than the full sheet.
# Declared here, not in the template, because field_pins() must project pin
# coordinates into exactly this window - a constant two files have to agree
# on belongs in one of them. Sheet is 1000x700; the building occupies
# x 90..910, y 70..630, and this keeps a thin margin around it.
MINIATURE_VIEW = {"x": 70, "y": 50, "w": 860, "h": 600}

FACE_DRAWING = "drawing"      # paper field, plan geometry, coordinate pins
FACE_SPIN = "spin"            # derivation trace: run -> findings -> sides
FACE_COMPOSER = "composer"    # drafting surface: bound context, turns, citations
FACE_DOCUMENTS = "documents"  # stacked cover sheets
FACE_INTAKE = "intake"        # NOT a surface - see below

# Faces are added one reviewed specimen at a time. KNOWN_FACES is the set the
# template can actually draw, not the set eventually intended.
KNOWN_FACES = (FACE_DRAWING, FACE_SPIN, FACE_COMPOSER, FACE_DOCUMENTS, FACE_INTAKE)

# INTAKE IS NOT A PAGE-FIELD, and the model says so rather than pretending.
#
# Every other tile is a miniature WINDOW INTO AN EXISTING SURFACE, and states
# the basis on which it shows it. Intake opens nothing - there is no surface
# behind it yet, which is the entire point of it. Giving it a `live` or `kind`
# miniature would be the same class of lie the vocabulary exists to prevent, so
# it carries NO basis at all and is drawn as an empty frame rather than as a
# picture of something.
#
# It sits in the field because that is where a person looks to begin, not
# because it is the same kind of object as the others.

DOCUMENTS = [
    {"id": "M-201", "name": "M-201 Level 2 Mechanical Plan", "sheets": 2},
    {"id": "M-601", "name": "M-601 Smoke Damper Schedule", "sheets": 1},
    {"id": "A-101", "name": "A-101 Level 1 Floor Plan", "sheets": 1},
    {"id": "A-601", "name": "A-601 Door Schedule", "sheets": 1},
    {"id": "SP-001", "name": "SP-001 Smoke Management Narrative", "sheets": 14},
    {"id": "CS-01", "name": "CS-01 Construction Schedule Rev C", "sheets": 3},
]

# The footer number MEASURES something named. A bare integer on a card is
# exactly the kind of fluent, unsourced claim this prototype exists to refuse.
COUNT_GROUNDED_PINS = "grounded_pins"
COUNT_REPLAYABLE_TRACES = "replayable_traces"
COUNT_BOUND_CONTEXT = "bound_context"
COUNT_SHEETS = "sheets"
COUNT_NONE = "none"

COUNT_MEANINGS = {
    COUNT_GROUNDED_PINS: "findings citing this drawing at a located or read basis",
    COUNT_REPLAYABLE_TRACES: "findings whose derivation reaches at least one grounded side",
    COUNT_BOUND_CONTEXT: "context items bound to the Composer",
    COUNT_SHEETS: "sheets in this document",
    COUNT_NONE: "nothing countable on record",
}

# The singular is carried explicitly rather than derived by stripping an "s".
# The screen reader announcement is the only place this number is ever read as
# a sentence, and "1 findings citing this drawing" is the kind of small
# carelessness that makes a surface sound generated.
COUNT_MEANINGS_ONE = {
    COUNT_GROUNDED_PINS: "finding citing this drawing at a located or read basis",
    COUNT_REPLAYABLE_TRACES: "finding whose derivation reaches at least one grounded side",
    COUNT_BOUND_CONTEXT: "context item bound to the Composer",
    COUNT_SHEETS: "sheet in this document",
    COUNT_NONE: "nothing countable on record",
}

# SPECIMEN 01. `territory` is the remembered coordinate: deterministic, stable
# between visits, and the coordinate an expanded workspace contracts back into.
#
# M-201 is the specimen because it is the ONLY surface whose miniature can
# honestly claim the `live` basis - the full canvas on this page renders
# exactly this plan, so the miniature is the same markup rather than a picture
# of it. It is also the only drawing carrying a foreground finding, which is
# what gives the embedded attention pin something real to be active about.
PAGE_FIELDS = [
    # Intake first, top-left, because beginning is the one thing a person
    # arriving with nothing must be able to do. It opens no surface and
    # therefore declares no miniature basis (see FACE_INTAKE above).
    {
        "id": "INTAKE", "short": "New", "qualifier": "Project intake",
        "face": FACE_INTAKE, "miniature": None, "action": True,
        "counts": COUNT_NONE, "territory": {"row": 1, "col": 1},
    },
    # SPECIMEN 01. The only surface whose miniature can honestly claim `live`:
    # the full canvas renders exactly this plan from the same macro, so the
    # miniature is the drawing rather than a picture of it. Also the only
    # drawing carrying a foreground finding, which is what gives the embedded
    # attention pin something real to be active about.
    {
        "id": "M-201", "short": "M201", "qualifier": "Level 02",
        "face": FACE_DRAWING, "miniature": MINIATURE_LIVE, "action": False,
        "counts": COUNT_GROUNDED_PINS, "territory": {"row": 1, "col": 2},
        "opens": True,
    },
    # SPECIMEN 02. `kind`: a schematic of the derivation STRUCTURE. It does
    # not claim to be a rendering of a Spin report page.
    {
        "id": "SPIN", "short": "Spin", "qualifier": "Clash Trace",
        "face": FACE_SPIN, "miniature": MINIATURE_KIND, "action": False,
        "counts": COUNT_REPLAYABLE_TRACES, "territory": {"row": 2, "col": 1},
    },
    # SPECIMEN 03. Bound to the same document the canvas shows - the Composer
    # takes its context from what is on screen, so its qualifier is derived
    # from that binding rather than written down twice.
    {
        "id": "COMPOSER", "short": "Composer", "qualifier": None,
        "face": FACE_COMPOSER, "miniature": MINIATURE_KIND, "action": False,
        "counts": COUNT_BOUND_CONTEXT, "territory": {"row": 2, "col": 2},
        "bound_to": "M-201",
    },
    # SPECIMEN 04. The specification on record. The directive asked for
    # "Specifications / Addenda"; the fixture holds SP-001 and NO addenda, so
    # this tile is the document that exists rather than a category label
    # implying documents that do not.
    {
        "id": "SP-001", "short": "SP001", "qualifier": "Narrative",
        "face": FACE_DOCUMENTS, "miniature": MINIATURE_KIND, "action": False,
        "counts": COUNT_SHEETS, "territory": {"row": 3, "col": 1},
    },
]

# ---------------------------------------------------------------------------
# THE SPIN FACE - a derivation trace, drawn from the record rather than
# decorated to look analytical.
#
# There is no separate "Spin fixture" in this module and none was invented.
# The trace already exists in the findings themselves: every finding carries
# `sides`, and every side names a document and the BASIS on which it does so.
# That is a real three-level derivation - run -> finding -> side - and it is
# what this face draws:
#
#   root    the Spin run. One node.
#   branch  a finding. Filled when foreground, hollow when tracked - the same
#           form-not-hue rule the canvas pins follow.
#   leaf    a side. Solid when the basis is `located` or `read`; hollow and
#           dashed when the basis is `asserted`, because an asserted side
#           names a document without establishing one and the face must not
#           make it look like evidence. On the current fixture exactly one
#           leaf is hollow, and it belongs to PRESSURE-STAIR-2 - the finding
#           the whole basis vocabulary exists for.
#
# Coordinates are computed here rather than in the template because they are
# derived data, and derived data is testable. Layout is deterministic: leaves
# are spread evenly down the face, and each finding sits at the mean y of its
# own leaves, so the tree balances itself without any hand-placed constant.
# ---------------------------------------------------------------------------

# The face's own coordinate space. Matches the drawing miniature's aspect so
# every Page-Field has an identical outer bounding box regardless of face.
SPIN_VIEW = {"w": 860, "h": 600}

_SPIN_ROOT_X = 74
_SPIN_BRANCH_X = 350
_SPIN_LEAF_X = 700
_SPIN_TOP = 96
_SPIN_BOTTOM = 504


def spin_trace(findings):
    """run -> findings -> sides, as coordinates, straight from the record.

    Returns None when there is nothing to draw. A face with no trace must
    render empty rather than render a plausible-looking one.
    """
    branches = []
    leaf_total = sum(len(f.get("sides") or []) for f in findings)
    if not leaf_total:
        return None

    span = _SPIN_BOTTOM - _SPIN_TOP
    step = span / float(leaf_total - 1) if leaf_total > 1 else 0
    index = 0

    for finding in findings:
        sides = finding.get("sides") or []
        if not sides:
            continue
        leaves = []
        for side in sides:
            y = _SPIN_TOP + step * index
            leaves.append({
                "y": round(y, 1),
                "basis": side["basis"],
                # `grounded` is the ONLY thing the face renders differently,
                # and it is the same located/read test used everywhere else.
                "grounded": side["basis"] in (BASIS_LOCATED, BASIS_READ),
            })
            index += 1
        mid = sum(leaf["y"] for leaf in leaves) / float(len(leaves))
        branches.append({
            "id": finding["id"],
            "tier": finding["prominence"]["tier"],
            "y": round(mid, 1),
            "leaves": leaves,
        })

    return {
        "root_x": _SPIN_ROOT_X,
        "branch_x": _SPIN_BRANCH_X,
        "leaf_x": _SPIN_LEAF_X,
        "root_y": round(SPIN_VIEW["h"] / 2.0, 1),
        "branches": branches,
    }


def documents_cited_by(finding):
    """Which document ids a finding's sides actually name, with their basis.

    Derived from the sides rather than from the claim's prose - the same rule
    the citation surfaces follow. A side whose basis is `asserted` names no
    document on record, so it contributes nothing here; that is the point.
    """
    cited = {}
    for side in finding.get("sides") or []:
        if side["basis"] not in (BASIS_LOCATED, BASIS_READ):
            continue
        token = side["document"].split(" ")[0]
        cited[token] = side["basis"]
    return cited


def field_pins(field, findings):
    """The attention objects embedded IN a Page-Field.

    A pin is a second visual species from the field itself: the field is the
    world, the pin is a grounded matter inside it. Prominence decides the
    pin's weight and never displaces the world - the pin sits at the finding's
    own canvas coordinate, expressed as a percentage of the miniature face, so
    a reader who later opens the full surface finds it in the same place.

    Only drawings carry positioned pins, because only a drawing has a
    coordinate space for a pin to be honest about. Any other face reports a
    count and no position rather than inventing one.
    """
    if field["face"] != FACE_DRAWING:
        return []
    pins = []
    for finding in findings:
        if field["id"] not in documents_cited_by(finding):
            continue
        # canvas x/y are percentages of the FULL sheet. The miniature shows a
        # cropped window of that sheet, so a pin placed at the raw percentage
        # would sit in the wrong room. Project it into the crop.
        sheet_x = finding["canvas"]["x"] / 100.0 * 1000.0
        sheet_y = finding["canvas"]["y"] / 100.0 * 700.0
        pins.append({
            "id": finding["id"],
            "tag": finding["tag"],
            "tier": finding["prominence"]["tier"],
            "x": finding["canvas"]["x"],
            "y": finding["canvas"]["y"],
            "mini_x": round((sheet_x - MINIATURE_VIEW["x"]) / MINIATURE_VIEW["w"] * 100, 2),
            "mini_y": round((sheet_y - MINIATURE_VIEW["y"]) / MINIATURE_VIEW["h"] * 100, 2),
        })
    return pins


def field_count(field, findings):
    """The footer number - never a number without a stated meaning.

    Returns None where nothing is countable on record, and None renders as no
    number at all rather than a zero, which would itself be a measurement.
    """
    if field["counts"] == COUNT_GROUNDED_PINS:
        return len([f for f in findings if field["id"] in documents_cited_by(f)])
    if field["counts"] == COUNT_REPLAYABLE_TRACES:
        # A finding whose every side is `asserted` has a derivation that
        # reaches nothing on record, and must not be counted as replayable.
        return len([f for f in findings if documents_cited_by(f)])
    if field["counts"] == COUNT_BOUND_CONTEXT:
        # What is actually bound at render time. A selection adds a second
        # item at runtime; nothing is selected on arrival, so it is not
        # counted here - a count must describe now, not a possible later.
        return 1 if field.get("bound_to") else 0
    if field["counts"] == COUNT_SHEETS:
        for document in DOCUMENTS:
            if document["id"] == field["id"]:
                return document["sheets"]
        return None
    return None


def composer_state(field, findings):
    """What the Composer face may honestly draw.

    THERE IS NO EXCHANGE FIXTURE IN THIS MODULE, and none was invented for
    this face. The module holds PROJECT, DOCUMENTS, FINDINGS and VERBS; there
    is no conversation anywhere in it. So the face draws the drafting
    STRUCTURE as skeleton geometry - turn shapes, not sentences - and the only
    concrete things on it are the two that are real:

      bound       the document the Composer takes its context from. The real
                  Composer binds to whatever the canvas is showing, so this
                  is derived from the binding rather than written down twice.
      citations   the bases a grounded answer about that document would carry,
                  taken from the sides of the findings that actually cite it.

    Returning None means the face draws nothing. An empty Composer beats a
    convincing invented one.
    """
    bound_id = field.get("bound_to")
    if not bound_id:
        return None
    bound = next((d for d in DOCUMENTS if d["id"] == bound_id), None)
    if bound is None:
        return None

    citations = []
    for finding in findings:
        for side in finding.get("sides") or []:
            if side["basis"] not in (BASIS_LOCATED, BASIS_READ):
                continue
            if side["document"].split(" ")[0] != bound_id:
                continue
            citations.append({"basis": side["basis"]})

    return {
        "bound_id": bound_id,
        "bound_short": bound_id.replace("-", ""),
        "citations": citations,
    }


def document_face(field):
    """Stacked covers. The stack depth is the document's real sheet count,
    capped only by what is legible at this size - never padded to look fuller.
    """
    document = next((d for d in DOCUMENTS if d["id"] == field["id"]), None)
    if document is None:
        return None
    return {
        "sheets": document["sheets"],
        # At 175px more than four covers stop reading as separate sheets.
        # The strip still shows the true count, so the drawing is a
        # simplification and never a contradiction of it.
        "stack": min(document["sheets"], 4),
    }


def page_fields(findings):
    """Scene 1: every built field, at rest, in its remembered territory."""
    by_id = {f["id"]: f for f in PAGE_FIELDS}
    fields = []
    for field in PAGE_FIELDS:
        pins = field_pins(field, findings)
        composer = (composer_state(field, findings)
                    if field["face"] == FACE_COMPOSER else None)

        # A field bound to another surface takes that surface's qualifier
        # rather than repeating it. Written twice, the two drift.
        qualifier = field["qualifier"]
        if qualifier is None and field.get("bound_to") in by_id:
            qualifier = by_id[field["bound_to"]]["qualifier"]

        fields.append({
            "id": field["id"],
            "short": field["short"],
            "qualifier": qualifier,
            "face": field["face"],
            "miniature": field["miniature"],
            "action": field.get("action", False),
            "opens": field.get("opens", False),
            "territory": field["territory"],
            "pins": pins,
            "trace": spin_trace(findings) if field["face"] == FACE_SPIN else None,
            "composer": composer,
            "document": (document_face(field)
                         if field["face"] == FACE_DOCUMENTS else None),
            "count": field_count(field, findings),
            "count_meaning": COUNT_MEANINGS[field["counts"]],
            "count_meaning_one": COUNT_MEANINGS_ONE[field["counts"]],
            "raises_foreground": any(
                p["tier"] == PROMINENCE_FOREGROUND for p in pins
            ),
        })
    return fields


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

    for finding in FINDINGS:
        finding["window"]["spent_percent"] = window_spent_percent(finding["window"])
        finding["prominence"] = assess(finding)

    horizon = horizon_order(FINDINGS)

    # Two bands, and every finding is in exactly one of them. Nothing is
    # dropped: `tracked` is the band the earlier binary model silenced, and
    # it is quiet rather than absent - a pin on the drawing and a line in the
    # tracked band, one tap from its own evidence.
    surfaced = [f for f in horizon if f["prominence"]["tier"] == PROMINENCE_FOREGROUND]
    tracked = [f for f in horizon if f["prominence"]["tier"] == PROMINENCE_TRACKED]
    return render_template(
        "calm_lake_prototype.html",
        project=PROJECT,
        documents=DOCUMENTS,
        fields=page_fields(horizon),
        miniature_view=MINIATURE_VIEW,
        spin_view=SPIN_VIEW,
        verbs=VERBS,
        horizon=horizon,
        surfaced=surfaced,
        tracked=tracked,
        basis_labels=BASIS_LABELS,
        basis_meanings=BASIS_MEANINGS,
        prototype_notice=PROTOTYPE_NOTICE,
        basis_none=BASIS_NONE,
        basis_asserted=BASIS_ASSERTED,
        basis_located=BASIS_LOCATED,
        basis_read=BASIS_READ,
    )
