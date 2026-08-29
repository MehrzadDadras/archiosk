"""5 NIPIGON — Phase 2 Scenario 01: architectural washroom coordination.

A separate blueprint from routes/calm_lake_prototype.py on purpose. Calm Lake is
a fixture-fed grammar study; this is the first surface driven by a REAL project
set, and the scope for this scenario is explicitly "do not redesign Calm Lake
globally". They share the Page-Field grammar and nothing else.

=============================================================================
EVIDENCE RULE
=============================================================================
The reconnaissance scaffold under `5 Nipigon\\reconnaissance` was used for
ORIENTATION ONLY. Every sheet, room, and relationship asserted below was
verified by opening the source PDF and looking at it. Where the scaffold and
the source disagree, or where the source does not settle a question, this
module says so rather than reconciling silently.

WHAT WAS VERIFIED, AND HOW

  A204 GROUND FLOOR PLAN
    - Title block reads "5 NIPIGON / OFFICE BUILDING", "GROUND FLOOR PLAN",
      A204, project 212109, Dadras Architects Inc., sheet 7 OF 36.
    - Room 104 is labelled with the room tag `104` and the annotation `H/C`,
      and contains a WC, a lavatory with MIRR, grab bars (GB), DTT, ND, H.D.,
      SD and P.S., a 1900 barrier-free turning circle, FFL 192.61, and a
      POWER DOOR H/C BUTTON. It opens off CORRIDOR 103.
    - A detail callout bubble reading `1 / A801` sits immediately below the
      room with a leader into it.

  A801 WASHROOM DETAILS
    - Title block reads WASHROOM DETAILS, A801, sheet 34 OF 36.
    - Detail 1 is titled "HANDICAP WASHROOM PLAN - 104" and shows the same
      room at larger scale with the same fixture set.
    - Detail 2 is "ELEVATIONS - RM 104" (ELEV 1-4 - RM 104).
    - Detail 3 is "ELEVATOR LOBBY ELEVATION - RM 103".
    - Details 4-6 are the second-floor equivalents for RM 206.

  INDEPENDENT CROSS-CHECK
    - The dimension string 2653 appears on the room on BOTH sheets. Two sheets
      agreeing on a measured dimension is stronger evidence that they depict
      the same room than a shared room number alone, which could be a
      numbering coincidence.

  A100 COVER PAGE — the only sheet in the set with a text layer
    - Its drawing index contains the literal string "A801 WASHROOM DETAILS 34".
    - Its index also names "U / G GARAGE PLAN PLUMBING AND HAVAC" under
      MECHANICAL as M1, and an ELECTRICAL series E2-E5.

=============================================================================
THE DISCREPANCY THAT CHANGES THE SCENARIO
=============================================================================
The mission is titled "Architectural -> Plumbing". THERE ARE NO PLUMBING
DRAWINGS IN THIS SET. The cover's own index names M1 as carrying plumbing and
HVAC, and no M-, P- or E-prefixed PDF exists in the directory: the 51 files are
architectural (`A`), structural framing (`RS`), one combined 49-page reference
PDF and one starter document.

So the plumbing pathway is UNRESOLVED, and this module renders it as such
rather than substituting the architectural detail and calling the coordination
complete. Substituting a sheet that happens to exist for the one the scenario
asked for is precisely the fluent-answer failure this programme exists to
refuse.

What CAN be demonstrated end to end, on real evidence, is architectural
washroom coordination: A204 room 104 -> A801 detail 1.
"""
from __future__ import annotations

import json
import os

from flask import Blueprint, abort, current_app, render_template, request, session

from services.auth import is_admin

nipigon_bp = Blueprint("nipigon", __name__, url_prefix="/admin/nipigon")

PROJECT = {
    "number": "212109",
    "name": "5 Nipigon New Office Building",
    "short": "5 Nipigon",
    "address": "5 Nipigon Avenue, Toronto, Ontario",
    "architect": "Dadras Architects Inc.",
    "discipline": "Architectural coordination",
}

# ---------------------------------------------------------------------------
# RELATIONSHIP BASIS - the vocabulary the mission requires, kept closed.
#
# The distinction that matters is between a link the DRAWING draws (a callout
# bubble pointing somewhere) and a link a reader could reasonably guess. The
# first is evidence; the second is a hypothesis wearing evidence's clothes.
# ---------------------------------------------------------------------------
REL_DIRECT = "direct"        # the sheet itself carries the reference
REL_INFERRED = "inferred"    # plausible from the set, not drawn on the sheet
REL_UNRESOLVED = "unresolved"  # named somewhere, but the target is not present

KNOWN_RELATIONSHIP_BASES = (REL_DIRECT, REL_INFERRED, REL_UNRESOLVED)

RELATIONSHIP_LABELS = {
    REL_DIRECT: "direct / located",
    REL_INFERRED: "inferred",
    REL_UNRESOLVED: "unresolved",
}

RELATIONSHIP_MEANINGS = {
    REL_DIRECT: "the source sheet carries an explicit reference to the target",
    REL_INFERRED: "consistent with the set, but no reference is drawn on the sheet",
    REL_UNRESOLVED: "named in the index, but the target sheet is not in this set",
}

# `rendered` joins live/kind. See tools/render_nipigon_assets.py for why it is
# admissible: it is a raster that CAN state what it is a picture of and when,
# because the manifest records the source file, its SHA-256, page and dpi.
MINIATURE_RENDERED = "rendered"

# ---------------------------------------------------------------------------
# THEMES. A closed set, validated server-side.
#
# `?theme=` is reflected into a body attribute, so an unvalidated value would
# be an attribute-injection surface on a page that also renders provenance. The
# set is closed and anything unrecognised silently falls back to the default -
# no error page, because a bad theme name is not worth refusing a drawing over.
#
# The variant is CSS-ONLY by construction: it changes token values and nothing
# else, so the DOM, the grid geometry and every test that asserts against
# markup are untouched by it.
# ---------------------------------------------------------------------------
THEME_DEFAULT = "slate"
THEME_GOLD_BLACK = "gold-black"
KNOWN_THEMES = (THEME_DEFAULT, THEME_GOLD_BLACK)


def resolve_theme(requested):
    """Closed vocabulary in, closed vocabulary out."""
    return requested if requested in KNOWN_THEMES else THEME_DEFAULT


ASSET_DIR = os.path.join("static", "nipigon")


PREFS_PATH = os.path.join("config", "engine_preferences.json")


def engine_preferences():
    """Shipped Engine DNA defaults, or None if the file is absent.

    These are the FALLBACK. A viewer's own choices live in localStorage and
    win over them; shipping the defaults as data rather than as literals in
    JavaScript keeps the engine's starting posture reviewable in a diff.
    """
    path = os.path.join(current_app.root_path, PREFS_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _semantics(sheet):
    """Annotation-grounded classification for a sheet, or None.

    Produced by tools/derive_structural_semantics.py and read here rather than
    recomputed per request: the classification is a property of the source
    document, not of a page view, and re-deriving it on every open would let
    two viewers disagree about what the drawing says.
    """
    path = os.path.join(current_app.root_path, ASSET_DIR,
                        "semantics_%s.json" % sheet)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _asset_svg(manifest, sheet):
    """The vector asset for a sheet, or None if it was not produced."""
    for asset in (manifest or {}).get("assets", []):
        if asset["sheet"] == sheet and asset.get("svg"):
            return asset["svg"]
    return None


def _asset_focus(manifest, sheet, label):
    """A focus rectangle in the sheet's NATIVE VIEW space.

    A crop is a VIEW onto the one vector asset, not a second file - a cropped
    SVG is not smaller, because a cropbox changes the viewport and not the
    content. Framing a rectangle keeps the crop and the full sheet incapable
    of disagreeing about what the drawing says.
    """
    for asset in (manifest or {}).get("assets", []):
        if asset["sheet"] == sheet:
            return (asset.get("focus") or {}).get(label)
    return None


def _manifest():
    """Provenance for every rendered asset, or None when assets are absent.

    Absent assets are a real state, not an error: the rasters are git-ignored
    and regenerated by tools/render_nipigon_assets.py. The surface must say the
    faces are missing rather than render empty boxes that look like drawings
    with nothing in them.
    """
    path = os.path.join(current_app.root_path, ASSET_DIR, "manifest.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------
# THE SHEETS. Every row was opened and looked at; `verified` records what that
# inspection actually established, not what the filename suggests.
# ---------------------------------------------------------------------------
SHEETS = [
    {
        "id": "A204", "number": "A204", "title": "Ground Floor Plan",
        "discipline": "Architectural", "sheet_of": "7 of 36",
        "source_file": "212109 A204 GROUND FLOOR PLAN.pdf",
        "verified": "Title block read. Room 104 tagged H/C with WC, lavatory, "
                    "grab bars and a 1900 turning circle; callout 1/A801 below it.",
    },
    {
        "id": "A801", "number": "A801", "title": "Washroom Details",
        "discipline": "Architectural", "sheet_of": "34 of 36",
        "source_file": "212109 A801 WASHROOM DETAILS.pdf",
        "verified": "Detail 1 titled HANDICAP WASHROOM PLAN - 104; detail 2 "
                    "ELEVATIONS - RM 104; detail 3 ELEVATOR LOBBY ELEVATION - RM 103.",
    },
    {
        "id": "A701", "number": "A701", "title": "Plan Details",
        "discipline": "Architectural", "sheet_of": None,
        "source_file": "212109 A701 PLAN DETAILS.pdf",
        "verified": "Referenced from A204 by callouts 4/A701 and 7/A701 near "
                    "room 104. Detail contents not individually verified.",
    },
    {
        "id": "A302", "number": "A302", "title": "Ground Floor RCP",
        "discipline": "Architectural", "sheet_of": None,
        "source_file": "212109 A302 GROUND FLOOR RCP.pdf",
        "verified": "Present and rendered. Ceiling content over room 104 not "
                    "individually verified.",
    },
    {
        "id": "A205", "number": "A205", "title": "Second Floor Plan",
        "discipline": "Architectural", "sheet_of": None,
        "source_file": "212109 A205 SECOND FLOOR PLAN.pdf",
        "verified": "Present and rendered. A801 details 4-6 cover the RM 206 "
                    "washroom on this level; no callout on A205 was traced.",
    },
    {
        "id": "RS501", "number": "RS501", "title": "Structural Framing",
        "discipline": "Structural", "sheet_of": None,
        "source_file": "212109 RS501 STRUCTURAL FRAMING.pdf",
        "verified": "Title block confirms structural framing. Relationship to "
                    "the washroom area not established.",
    },
    {
        "id": "A902", "number": "A902", "title": "Door / Window Schedule",
        "discipline": "Architectural", "sheet_of": None,
        "source_file": "212109 A902 DOOR WINDOW SCH.pdf",
        "verified": "Present and rendered. Door marks P2/P3 appear on A204 and "
                    "A801 at room 104; mark-to-schedule rows not verified.",
    },
]

SHEETS_BY_ID = {s["id"]: s for s in SHEETS}

# Pane 2 steps through the detail-sheet family. Grouped because the cover index
# lists them as the DETAILS series - not because adjacency was assumed.
SIBLING_SET = ["A701", "A801", "A509", "A510", "A511", "RS501"]

SIBLING_TITLES = {
    "A509": "Detail", "A510": "Detail", "A511": "Detail",
    "A701": "Plan Details", "A801": "Washroom Details",
    "RS501": "Structural Framing",
}

# ---------------------------------------------------------------------------
# THE SELECTION. A spatial context on a real sheet, expressed as a fraction of
# the page box so it survives any render resolution.
# ---------------------------------------------------------------------------
SELECTION = {
    "room": "104",
    "label": "H/C washroom",
    "on_sheet": "A204",
    "off_corridor": "103",
    # PDF points on A204's 1728x2592pt page, matching the crop the asset tool
    # renders. Declared against the DRAWING, not against any pixel size.
    "clip_pt": [295.0, 555.0, 755.0, 885.0],
    "verified": "Room tag 104 with H/C annotation, WC, lavatory with MIRR, "
                "GB, DTT, ND, H.D., SD, P.S., 1900 turning circle, FFL 192.61.",
}

# ---------------------------------------------------------------------------
# WHAT GO IS ALLOWED TO CONCLUDE.
#
# Three candidates, ranked, each carrying its own basis. The point of listing
# the losers is that a single confident answer is indistinguishable from a
# guess; a ranked list with bases is inspectable.
# ---------------------------------------------------------------------------
CANDIDATES = [
    {
        "target": "A801",
        "detail": "1",
        "detail_title": "HANDICAP WASHROOM PLAN - 104",
        "basis": REL_DIRECT,
        "evidence": [
            "A204 carries a detail callout bubble reading 1/A801 with a leader "
            "into room 104.",
            "A801 detail 1 is titled HANDICAP WASHROOM PLAN - 104, naming the "
            "same room number.",
            "The dimension 2653 appears on the room on both sheets - an "
            "agreement on a measured value, not only on a label.",
        ],
        # No asset name here. The pane serves A801's VECTOR and frames the
        # detail's focus rectangle on it; naming a raster crop would be naming
        # a file the pipeline deliberately no longer produces.
        "asset": None,
    },
    {
        "target": "A701",
        "detail": "4, 7",
        "detail_title": "Plan Details (contents not individually verified)",
        "basis": REL_INFERRED,
        "evidence": [
            "A204 carries callouts 4/A701 and 7/A701 within the same area of "
            "the sheet as room 104.",
            "Their leaders were not traced to a specific element, so these may "
            "belong to the adjacent wall or stair rather than the washroom.",
        ],
        "asset": "A701_page.png",
    },
    {
        "target": None,
        "detail": None,
        "detail_title": "M1 — U/G GARAGE PLAN PLUMBING AND HAVAC",
        "basis": REL_UNRESOLVED,
        "evidence": [
            "A100's drawing index names M1 under MECHANICAL as carrying "
            "plumbing and HVAC.",
            "No M-, P- or E-prefixed PDF exists in the source directory; the "
            "51 files are architectural, structural framing, one combined "
            "reference PDF and one starter document.",
            "The plumbing pathway therefore cannot be completed from this "
            "evidence, and no architectural sheet was substituted for it.",
        ],
        "asset": None,
    },
]


def go_selection():
    """The ranked candidate set, with the chosen one first.

    GO does not get to return a bare answer here. It returns the ranking and
    the basis of each rank, because "why this surface" is the part a reader
    has to be able to audit.
    """
    chosen = next((c for c in CANDIDATES if c["basis"] == REL_DIRECT), None)
    return {
        "chosen": chosen,
        "candidates": CANDIDATES,
        "unique": len([c for c in CANDIDATES if c["basis"] == REL_DIRECT]) == 1,
    }


# ==========================================================================
# DISCIPLINES - what the project HAS, one entry per trade.
#
# Scene 1 used to be one tile per sheet. That is the wrong first object:
# nobody opens a project looking for "A302", they open it looking for the
# architectural set. The Product Owner said so directly - "the project page
# must have architectural icon [with all the drawing in it], the mechanical,
# the structural and so on and not individual drawings."
#
# EVERY NUMBER BELOW WAS COUNTED, NOT ESTIMATED. Two independent readings,
# because they disagree and the disagreement is the interesting part:
#
#   DELIVERED - counted off the source directory C:\Archiosk\Samples\5 Nipigon
#     A-series  39 PDFs
#     RS-series 10 PDFs (RS501-RS510)
#     (51 files total; the remaining two - "5 Nipigon.pdf" and "Nipigan
#      Starter.pdf" - are not numbered sheets and are not counted as any
#      discipline's)
#
#   NAMED - read out of the DRAWING INDEX on 212109 A100 COVER PAGE.pdf
#     ARCHITECTURAL  CV, A1xx-A9xx
#     STRUCTURAL     S1-S10 AND  RS501-RS510
#     MECHANICAL     M1-M5   (M1 "U/G GARAGE PLAN PLUMBING AND HVAC",
#                             M2 "PLUMBING PLAN" - see below)
#     ELECTRICAL     E1-E5
#     LANDSCAPE      L1
#     CIVIL          SP1     "SITE SERVICING AND GRADING PLAN"
#
# PLUMBING IS NOT A DISCIPLINE ON THIS PROJECT, and neither is a "C-series".
# A directive asked for a "Plumbing / Civil (P / C-Series)" container. The
# index was searched for both: there is NO P-series at all, and the only
# `C1` token on the sheet is a zoning designation in the project-data block
# ("563.34 sq.m | C1 | 5 Nipigon Ave"), not a drawing number. Plumbing scope
# is carried by the MECHANICAL series - it is the TITLE of M1 and M2.
#
# So no P/C container is invented here. Building one would produce a card
# standing for a series this project does not have, which is the same defect
# as naming a sheet A201 because a directive said so when the title block
# says FIRE SCHEMATIC LAYOUT. The discrepancy is reported instead.
#
# Four disciplines are named on the cover and delivered nothing at all. A
# fifth, Structural, is named TWICE under two different numbering systems and
# delivered only one of them. Those gaps are the whole reason this object
# exists: a project page that silently showed three disciplines because three
# had files would be hiding the most useful fact on the screen, which is that
# the mechanical drawings referenced by the cover sheet are not here.
#
# So a discipline with nothing behind it still gets a tile, and it renders
# UNRESOLVED - which is a basis this codebase already has a meaning and a form
# for, and which is deliberately not the same claim as "there are none".
# ==========================================================================
DISCIPLINES = [
    {
        "id": "ARCH", "name": "Architectural", "prefix": "A",
        "delivered": 39,
        "named": "CV, A101-A902",
        "basis": REL_DIRECT,
        "note": "39 sheets delivered. Index numbering matches the files.",
    },
    {
        "id": "STRUCT", "name": "Structural", "prefix": "RS",
        "delivered": 10,
        "named": "S1-S10 and RS501-RS510",
        "basis": REL_INFERRED,
        # Not tidied away. The cover index carries TWO structural sets under
        # two numbering systems; only the RS framing series arrived. Calling
        # this DIRECT would assert a completeness the source does not support,
        # and reconciling the two silently is exactly what the evidence rule
        # for this project forbids.
        "note": "10 framing sheets delivered (RS501-RS510). The index also "
                "names a separate S1-S10 set, which is not in the source "
                "material. Both numberings appear on A100.",
    },
    {
        "id": "MECH", "name": "Mechanical", "prefix": "M",
        "delivered": 0,
        "named": "M1-M5",
        "basis": REL_UNRESOLVED,
        "note": "Named on the A100 index as M1-M5, which is also where "
                "PLUMBING lives on this project - M1 is \u201cU/G GARAGE PLAN "
                "PLUMBING AND HVAC\u201d and M2 is \u201cPLUMBING PLAN\u201d. "
                "There is no separate P-series. No mechanical sheet is in the "
                "source material.",
    },
    {
        "id": "ELEC", "name": "Electrical", "prefix": "E",
        "delivered": 0,
        "named": "E1-E5",
        "basis": REL_UNRESOLVED,
        "note": "Named on the A100 index as E1-E5. No electrical sheet is in "
                "the source material.",
    },
    {
        "id": "LAND", "name": "Landscape", "prefix": "L",
        "delivered": 0,
        "named": "L1",
        "basis": REL_UNRESOLVED,
        "note": "Named on the A100 index as L1, with a landscape consultant "
                "credited. No landscape sheet is in the source material.",
    },
    {
        "id": "CIVIL", "name": "Civil", "prefix": "SP",
        "delivered": 0,
        "named": "SP1",
        "basis": REL_UNRESOLVED,
        # Reading the cover sheet added a discipline nobody had listed. It is
        # kept for that reason: the index is the authority on what the project
        # is supposed to contain, not our memory of it.
        "note": "Named on the A100 index as SP1, \u201cSITE SERVICING AND "
                "GRADING PLAN\u201d. Numbered SP, not C - the only C1 on the "
                "cover is a zoning designation, not a drawing. No civil sheet "
                "is in the source material.",
    },
]


def disciplines(manifest):
    """Scene 1: one tile per trade, each holding the sheets we really have.

    A tile's FACE is built from the actual rendered sheet faces belonging to
    that discipline - never a glyph standing for a drawing, and never more
    faces than were genuinely rendered. The strip says both numbers ("4 of 39
    rendered") because the difference between what exists and what has been
    prepared is a fact the reader needs and cannot recover from a picture.
    """
    have = set()
    mono = {}
    if manifest:
        have = {a["sheet"] for a in manifest["assets"]}
        mono = {a["sheet"]: a.get("monochrome", False) for a in manifest["assets"]}

    out = []
    for row, spec in enumerate(DISCIPLINES, start=1):
        sheets = []
        for sheet in SHEETS:
            if sheet["discipline"] != spec["name"] or sheet["id"] not in have:
                continue
            sheets.append({
                "id": sheet["id"],
                "short": sheet["number"],
                "qualifier": sheet["title"],
                "asset": "%s_thumb.png" % sheet["id"],
                "monochrome": mono.get(sheet["id"], False),
                "opens": sheet["id"] == SELECTION["on_sheet"],
            })
        entry = dict(spec)
        entry["sheets"] = sheets
        entry["rendered"] = len(sheets)
        # The face carries at most four, because a tile this size cannot show
        # more without each one ceasing to be legible as a drawing.
        entry["face_sheets"] = sheets[:4]
        entry["opens"] = bool(sheets)
        out.append(entry)
    return out


def page_fields(manifest):
    """Scene 1 for this project: real surfaces, rendered faces.

    THE SHEET NUMBERS HERE ARE NOT THE ONES THE DIRECTIVE NAMED, and that is
    deliberate. The directive asked for A201 as the Level 2 architectural
    floor plan, A401 as enlarged washroom details, and A301 as the reflected
    ceiling plan. Each was opened and its title block read:

      A201  "FIRE SCHEMATIC LAYOUT"                    sheet 4 of 36
      A401  "FRONT ELEVATION / REAR ELEVATION /
             BUILDING SIGNAGE"                         sheet 13 of 36
      A301  "UNDERGROUND RCP"                          sheet 10 of 36

    None of the three is what the directive expected. Building to those
    numbers would have opened a fire schematic and a building elevation and
    presented them as washroom coordination - fluent, and wrong in exactly the
    way this programme exists to catch. The verified equivalents are used
    instead and the substitution is reported rather than made silently.

    RS501 was checked too and IS structural framing, as given.
    """
    have = set()
    mono = {}
    if manifest:
        have = {a["sheet"] for a in manifest["assets"]}
        # Measured at render time, never guessed here. A sheet with real
        # colour must not be re-tinted for a dark field.
        mono = {a["sheet"]: a.get("monochrome", False) for a in manifest["assets"]}

    fields = [{
        "id": "INTAKE", "short": "New", "qualifier": "Project intake",
        "face": "intake", "miniature": None, "action": True,
        "asset": None, "count": None, "territory": {"row": 1, "col": 1},
        "corrects": None, "opens": False,
    }]

    # (sheet, row, col, the directive's number this stands in for)
    layout = [
        ("A204", 1, 2, None),
        ("A205", 2, 1, "A201"),
        ("A801", 2, 2, "A401"),
        ("A302", 3, 1, "A301"),
        ("RS501", 3, 2, None),
    ]
    for sheet_id, row, col, corrects in layout:
        sheet = SHEETS_BY_ID[sheet_id]
        fields.append({
            "id": sheet_id,
            "short": sheet["number"],
            "qualifier": sheet["title"],
            "face": "sheet",
            "miniature": MINIATURE_RENDERED if sheet_id in have else None,
            "action": False,
            "asset": ("%s_thumb.png" % sheet_id) if sheet_id in have else None,
            "monochrome": mono.get(sheet_id, False),
            "count": None,
            "territory": {"row": row, "col": col},
            "opens": sheet_id == SELECTION["on_sheet"],
            "corrects": corrects,
        })
    return fields


def siblings(manifest):
    """The set Pane 2 steps through, limited to sheets actually rendered."""
    have = {a["sheet"] for a in manifest["assets"]} if manifest else set()
    mono = {a["sheet"]: a.get("monochrome", False)
            for a in manifest["assets"]} if manifest else {}
    out = []
    for sheet_id in SIBLING_SET:
        if sheet_id not in have:
            continue
        out.append({
            "id": sheet_id,
            "title": SIBLING_TITLES.get(sheet_id, "Detail"),
            # The VECTOR asset, not the raster. A pane is the one place a
            # reader zooms, and a stretched raster is exactly what made the
            # linework mush at 200%.
            "asset": "%s.svg" % sheet_id,
            "monochrome": mono.get(sheet_id, False),
            "is_target": sheet_id == "A801",
        })
    return out


def provenance_rows(manifest):
    """Source-level provenance for everything the scenario touches."""
    if not manifest:
        return []
    by_sheet = {a["sheet"]: a for a in manifest["assets"]}
    rows = []
    for sheet_id in ("A204", "A801"):
        asset = by_sheet.get(sheet_id)
        sheet = SHEETS_BY_ID.get(sheet_id)
        if not asset or not sheet:
            continue
        rows.append({
            "sheet": sheet_id,
            "role": "anchor" if sheet_id == "A204" else "opened in pane 2",
            "source_file": asset["source_file"],
            "sha256": asset["source_sha256"],
            "sha_short": asset["source_sha256"][:16],
            "bytes": asset["source_bytes"],
            "page": "%d of %d" % (asset["page_index"] + 1, asset["page_count"]),
            "verified": sheet["verified"],
        })
    return rows


@nipigon_bp.route("/")
def surface():
    """Read-only. Renders fixture-verified evidence and writes nothing."""
    if not is_admin() or not session.get("developer_mode"):
        abort(403)

    manifest = _manifest()
    theme = resolve_theme(request.args.get("theme"))
    return render_template(
        "nipigon_coordination.html",
        project=PROJECT,
        theme=theme,
        theme_default=THEME_DEFAULT,
        theme_gold_black=THEME_GOLD_BLACK,
        sheets=SHEETS,
        fields=page_fields(manifest),
        selection=SELECTION,
        disciplines=disciplines(manifest),
        anchor_svg=_asset_svg(manifest, SELECTION["on_sheet"]),
        anchor_focus=_asset_focus(manifest, SELECTION["on_sheet"], "washroom-104"),
        target_svg=_asset_svg(manifest, "A801"),
        target_focus=_asset_focus(manifest, "A801", "detail-1-104"),
        anchor_monochrome=next(
            (a.get("monochrome", False) for a in (manifest or {}).get("assets", [])
             if a["sheet"] == SELECTION["on_sheet"]), False),
        target_monochrome=next(
            (a.get("monochrome", False) for a in (manifest or {}).get("assets", [])
             if a["sheet"] == "A801"), False),
        go=go_selection(),
        siblings=siblings(manifest),
        provenance=provenance_rows(manifest),
        manifest=manifest,
        semantics=_semantics("RS501"),
        prefs=engine_preferences(),
        relationship_labels=RELATIONSHIP_LABELS,
        relationship_meanings=RELATIONSHIP_MEANINGS,
        rel_direct=REL_DIRECT,
        rel_inferred=REL_INFERRED,
        rel_unresolved=REL_UNRESOLVED,
        assets_missing=manifest is None,
    )
