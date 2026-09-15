"""CLAUDE-SURVEY-REFERENCE-01 - the derived working drawing, and its limits.

    A SURVEY REFERENCE IS A WORKING REFERENCE. IT IS NOT A SURVEY.

Product Owner, 2026-09-15: a survey arriving as a photograph or a scan should
become a clean derived drawing a designer can actually work against - while the
original stays exactly as it arrived and nothing invented appears on the
derivative.

The name is load-bearing and the forbidden alternatives are named in the
direction itself: never "certified survey", "legal survey", "replacement
survey" or "reconstructed authority survey". What this is, in the words that go
on the sheet:

    Source: Derived from uploaded survey image. Original retained.

One short line. Not a disclaimer paragraph - a paragraph nobody reads is worse
protection than a sentence everybody does.

WHAT DECIDES WHETHER ONE IS BUILT AT ALL

`is_survey_like`, and only it. A photograph does not become a Survey Reference
because it happens to contain a straight line, and a floor plan does not become
one because it is a plan. The test is the visual examination's own category,
held to a certainty that can support it - which means a model that could not
tell what it was looking at produces no derivative, rather than a confident one
built on an "unknown".

WHAT REACHES THE SHEET

Only observations whose certainty bears a value, and only geometry the reader
actually traced. `visual_examination` already drops a value whose certainty
does not support it, so this module never has to decide whether to trust a
number - it decides only where a already-qualified fact is printed:

    RECOVERED            -> printed as a fact of the reference
    PARTIALLY_RECOVERED  -> printed, in its own section, marked as partial
    UNRESOLVED           -> named in Unresolved, never valued
    WITHHELD_AS_UNSAFE   -> named in Unresolved, never valued

    THE ONE THING THAT MUST NOT HAPPEN IS A DIMENSION ON A DRAWING THAT
    NOBODY READ OFF THE SURVEY.

PROVENANCE IS ON THE ARTIFACT, not only in the record beside it. The sheet
carries the original filename, the original hash and the generation time,
because a PDF leaves the application and is read by people who never saw the
screen that explained it - the same reasoning `document_export` already applies
to a provisional Finding.

STORAGE. A Survey Reference is a Source with `origin_type="derived_reference"`
and `origin_reference=<the source it came from>`, which is the mechanism
`image_intelligence.extract_bounded_crop` already established for a mechanically
generated derivative. No new store, no new record type, and save/reopen is then
not a feature at all - it is what a Source already is.
"""
from __future__ import annotations

import hashlib
import io
import logging
import math
from datetime import datetime, timezone
from typing import Optional

from services import visual_examination as vx

logger = logging.getLogger(__name__)

REFERENCE_TITLE = "Survey Reference"
REFERENCE_VERSION = "survey-reference-01"
PDF_MIMETYPE = "application/pdf"

#: One line, and the exact words the direction asked for.
SOURCE_NOTE = "Derived from uploaded survey image. Original retained."

#: What this artifact is allowed to be called, in a sentence, for the one place
#: a person may reasonably need more than the line above.
AUTHORITY_NOTE = ("A working reference for planning and design coordination, "
                  "derived from the uploaded source. Not a certified or legal survey.")

#: The evidence record content type for the derivation, so the reference can be
#: found again without re-reading the PDF.
REFERENCE_CONTENT_TYPE = "survey_reference"

#: A category may found a Survey Reference only if the reader was sure enough
#: of the category to be worth building on. `unknown` is excluded by
#: `normalise_payload`, which forces its certainty to UNRESOLVED.
SURVEY_LIKE_CATEGORIES = (vx.CATEGORY_SURVEY,)


def is_survey_like(visual) -> bool:
    """Should this source become a Survey Reference?

    Deliberately strict and deliberately not a keyword test over OCR text: a
    photograph of a street with "SURVEY" on a van is not a survey, and a
    keyword rule cannot tell the difference. The visual reading can.
    """
    if visual is None or not getattr(visual, "ran", False):
        return False
    return (visual.document_category in SURVEY_LIKE_CATEGORIES
            and visual.category_certainty in vx.VALUE_BEARING)


def derive(visual, *, project_id: str, source_id: str, source_filename: str,
           source_sha256: Optional[str] = None, pages_used=None,
           display_name: str = "", frame_size=None) -> dict:
    """The Survey Reference RECORD - everything except the rendered bytes.

    Split from `render_pdf` so the record can be stored, asked about and
    reopened without a PDF ever being produced, and so a test can assert on
    what was derived rather than on what a page happens to look like.
    """
    recovered, partial, withheld = [], [], []
    for observation in (visual.observations or []):
        entry = {"key": observation["key"], "label": observation["label"],
                 "value": observation["value"], "note": observation.get("note") or "",
                 "certainty": observation["certainty"],
                 # WHERE THIS CAME FROM. The direction asks for text-OCR vs
                 # geometry vs visual reading to be distinguishable; every
                 # observation on this path is a visual reading, and saying so
                 # explicitly is what keeps it distinguishable when another
                 # producer is added later.
                 "basis": "visual_reading"}
        if observation["certainty"] == vx.RECOVERED:
            recovered.append(entry)
        elif observation["certainty"] == vx.PARTIALLY_RECOVERED:
            partial.append(entry)
        elif observation["certainty"] == vx.WITHHELD_AS_UNSAFE:
            withheld.append(entry)

    from services import survey_graph

    geometry = dict(visual.geometry or {})
    graph = dict(getattr(visual, "graph", None) or {})
    unresolved = list(visual.unresolved or [])

    # CLAUDE-SURVEY-REFERENCE-02: the geometry is COMPUTED here, once, and the
    # refusals it produces join the unresolved list rather than being discarded.
    # An arc whose radius was not read, a radius that cannot reach its own
    # chord, a boundary that does not close - each is a finding about the
    # sheet, and each would otherwise vanish behind a drawing that looked
    # finished.
    resolved = survey_graph.build_primitives(graph) if graph.get("nodes") else {
        "primitives": [], "unresolved": [],
        "stats": {"arcs": 0, "straights": 0, "nodes": 0, "footprints": 0,
                  "closed": False}}
    for note in resolved["unresolved"]:
        if note not in unresolved:
            unresolved.append(note)
    if not resolved["stats"]["nodes"]:
        note = "No boundary geometry could be reconstructed from the image"
        if not any("geometry" in item.lower() or "outline" in item.lower()
                   for item in unresolved):
            unresolved.append(note)

    return {
        "reference_version": REFERENCE_VERSION,
        "title": REFERENCE_TITLE,
        "source_note": SOURCE_NOTE,
        "authority_note": AUTHORITY_NOTE,
        "display_name": display_name or "",
        # -- provenance, all of it, on the record -------------------------
        "project_id": project_id,
        "source_id": source_id,
        "source_filename": source_filename,
        "source_sha256": source_sha256 or "",
        "pages_used": list(pages_used or [1]),
        # The frame the coordinates are normalised AGAINST. Without it the plan
        # is stretched to whatever panel it lands in, so a square lot prints as
        # a wide rectangle - a drawing that lies about shape while claiming to
        # be traced. Absent on a record written before this field existed, and
        # the renderer then falls back to the panel, exactly as it used to.
        "frame_size": list(frame_size) if frame_size else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_version": getattr(visual, "prompt_version", ""),
        "model": getattr(visual, "model", "") or "",
        # -- what was read -------------------------------------------------
        "graph": graph,
        "geometry_stats": resolved["stats"],
        "document_category": visual.document_category,
        "category_certainty": visual.category_certainty,
        "recovered": recovered,
        "partially_recovered": partial,
        "withheld": withheld,
        "unresolved": unresolved,
        "geometry": geometry,
    }


def headline(reference: dict) -> dict:
    """The slim, factual summary the result page and GO both read.

    ONE derivation of the compact form, so the page a person sees and the
    answer GO gives cannot describe the same reference differently.
    """
    def _phrases(entries):
        out = []
        for entry in entries:
            out.append("%s: %s" % (entry["label"], entry["value"])
                       if entry["value"] else entry["label"])
        return out

    return {
        "title": reference.get("title") or REFERENCE_TITLE,
        "source_note": reference.get("source_note") or SOURCE_NOTE,
        "recovered": _phrases(reference.get("recovered") or []),
        "partially_recovered": _phrases(reference.get("partially_recovered") or []),
        "unresolved": list(reference.get("unresolved") or []),
        "has_geometry": bool((reference.get("geometry") or {}).get("parcel")),
    }


# -- The sheet ---------------------------------------------------------------

def _escape(value) -> str:
    from services.document_export import _safe

    return _safe(value)

#: Built on first render and cached. `reportlab` is imported lazily throughout
#: this codebase (see `document_export.build_pdf`) so importing a service never
#: costs a PDF library - and a Flowable subclass cannot be declared until the
#: base class exists.
_PLAN_PANEL_CLASS = None


def plan_panel(resolved: dict, width: float, height: float, frame_size=None):
    """The reconstructed plan as a platypus flowable.

    CLAUDE-SURVEY-REFERENCE-02: takes RESOLVED PRIMITIVES, not a geometry dict.
    The geometry was computed once by `survey_graph.build_primitives`, and this
    flowable and the SVG on the review screen consume the same list - so the
    sheet the Product Owner exports and the drawing they compared against the
    photograph cannot diverge.
    """
    global _PLAN_PANEL_CLASS
    if _PLAN_PANEL_CLASS is None:
        from reportlab.platypus import Flowable

        class _PlanPanel(Flowable):
            def __init__(self, resolved, width, height, frame_size=None):
                super().__init__()
                self.resolved = resolved or {"primitives": []}
                self.width = width
                self.height = height
                self.frame_size = frame_size

            def wrap(self, *_args):
                return self.width, self.height

            def draw(self):
                draw_plan(self.canv, self.resolved, self.width, self.height,
                          self.frame_size)

        _PLAN_PANEL_CLASS = _PlanPanel
    return _PLAN_PANEL_CLASS(resolved, width, height, frame_size)


#: Boundary styling, keyed by the role the surveyor gave the line. A street
#: line is the heaviest because it is the one a reader looks for first.
_ROLE_STYLE = {
    "street_line": ("#1f2933", 1.6),
    "lot_line": ("#1f2933", 1.1),
    "interior": ("#6b7785", 0.7),
    "easement": ("#6b7785", 0.7),
    "unknown": ("#6b7785", 0.9),
}


def draw_plan(canvas, resolved: dict, width: float, height: float,
              frame_size=None) -> None:
    """Every stroke on the sheet, from resolved primitives.

    THE SOURCE'S ASPECT RATIO IS PRESERVED, letterboxed inside the panel: the
    coordinates are fractions of the source frame, so stretching them would
    change every angle on a drawing whose whole claim is that it was measured.

    AN ARC IS DRAWN AS AN ARC. `canvas.arcTo` emits Bezier curve operators into
    the PDF content stream - native vector geometry, which is what makes
    `page.get_drawings()` report curve items rather than a polyline pretending
    to be a curve.
    """
    from reportlab.lib import colors

    primitives = (resolved or {}).get("primitives") or []
    inset = 22.0
    panel_w, panel_h = width - 2 * inset, height - 2 * inset
    plot_w, plot_h = panel_w, panel_h
    if frame_size and len(frame_size) == 2 and frame_size[0] and frame_size[1]:
        aspect = float(frame_size[0]) / float(frame_size[1])
        if panel_w / panel_h > aspect:
            plot_w = panel_h * aspect
        else:
            plot_h = panel_w / aspect
    ox = inset + (panel_w - plot_w) / 2.0
    oy = inset + (panel_h - plot_h) / 2.0

    def point(pair):
        # Image fractions are top-left origin, y down; PDF user space is
        # bottom-left origin, y up.
        return (ox + pair[0] * plot_w, oy + (1.0 - pair[1]) * plot_h)

    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#b9c0c7"))
    canvas.setLineWidth(0.5)
    canvas.rect(0, 0, width, height, stroke=1, fill=0)

    # Footprints first, so boundary lines and labels sit above them.
    for item in primitives:
        if item["type"] != "polygon":
            continue
        path = canvas.beginPath()
        for index, pair in enumerate(item["points"]):
            px, py = point(pair)
            path.moveTo(px, py) if index == 0 else path.lineTo(px, py)
        path.close()
        canvas.setFillColor(colors.HexColor("#d8dee4"))
        canvas.setStrokeColor(colors.HexColor("#1f2933"))
        canvas.setLineWidth(0.9)
        if not item.get("certain"):
            canvas.setDash(3, 2)
        canvas.drawPath(path, stroke=1, fill=1)
        canvas.setDash()

    for item in primitives:
        kind = item["type"]
        if kind == "line":
            colour, weight = _ROLE_STYLE.get(item.get("role"), _ROLE_STYLE["unknown"])
            canvas.setStrokeColor(colors.HexColor(colour))
            canvas.setLineWidth(weight)
            if not item.get("certain"):
                canvas.setDash(4, 3)
            a, b = point(item["a"]), point(item["b"])
            canvas.line(a[0], a[1], b[0], b[1])
            canvas.setDash()
        elif kind == "arc":
            colour, weight = _ROLE_STYLE.get(item.get("role"), _ROLE_STYLE["unknown"])
            canvas.setStrokeColor(colour if not isinstance(colour, str)
                                  else colors.HexColor(colour))
            canvas.setLineWidth(weight)
            if not item.get("certain"):
                canvas.setDash(4, 3)
            # The circle's bounding box in PDF space. The y flip inverts the
            # sweep, which is why the extent is negated here and nowhere else.
            cx, cy = point(item["centre"])
            rx = item["radius"] * plot_w
            ry = item["radius"] * plot_h
            path = canvas.beginPath()
            # `arc` rather than `arcTo`: arcTo appends to a current point and
            # asserts one exists, so it needs a preceding moveTo. `arc` opens
            # the path at the arc's own start. Both emit the same Bezier
            # operators - this is about where the subpath begins, not about
            # what geometry reaches the PDF.
            path.arc(cx - rx, cy - ry, cx + rx, cy + ry,
                     -item["start_deg"], -item["extent_deg"])
            canvas.drawPath(path, stroke=1, fill=0)
            canvas.setDash()

    canvas.setFont("Helvetica", 6.5)
    for item in primitives:
        if item["type"] == "label":
            px, py = point(item["at"])
            canvas.setFillColor(colors.HexColor("#1f2933" if item.get("certain")
                                                else "#6b7785"))
            canvas.drawCentredString(px, py + 2, item["text"][:28])
        elif item["type"] == "north":
            _draw_north(canvas, colors, item, width, height)

    # FOOTPRINT LABELS LAST, and OUTSIDE the polygon when they will not fit
    # inside it. Centroid-anchored labels collided on the Castille sheet -
    # "EXISTING CONC. BLOCK GARAGE" is far wider than the garage it names, so it
    # ran straight through "1 STORY BRICK DWELLING" next door and made both
    # unreadable. A label that obscures the drawing it annotates is worse than
    # one sitting just below it.
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(colors.HexColor("#1f2933"))
    for item in primitives:
        if item["type"] != "polygon" or not item.get("label"):
            continue
        pts = [point(p) for p in item["points"]]
        cx = sum(p[0] for p in pts) / len(pts)
        text = item["label"][:34]
        text_width = canvas.stringWidth(text, "Helvetica", 6.5)
        box_width = max(p[0] for p in pts) - min(p[0] for p in pts)
        if text_width <= box_width - 4:
            cy = sum(p[1] for p in pts) / len(pts)
        else:
            cy = min(p[1] for p in pts) - 7.5
        canvas.drawCentredString(cx, cy, text)

    canvas.restoreState()


def _draw_north(canvas, colors, north, width, height) -> None:
    """A north arrow pointing where the SOURCE's arrow pointed.

    Degrees are clockwise from straight up on the source image, which is also
    straight up on this sheet: the plan is drawn in the source's own frame and
    is never rotated to put north up. Rotating it would silently re-register
    every coordinate on the page against a frame nobody saw.
    """
    radius = 15.0
    cx = width - radius - 14.0
    cy = height - radius - 14.0
    angle = math.radians(90.0 - float(north["degrees"]))
    tip = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
    left = (cx + radius * 0.42 * math.cos(angle + 2.5),
            cy + radius * 0.42 * math.sin(angle + 2.5))
    right = (cx + radius * 0.42 * math.cos(angle - 2.5),
             cy + radius * 0.42 * math.sin(angle - 2.5))

    canvas.setStrokeColor(colors.HexColor("#1f2933"))
    canvas.setFillColor(colors.HexColor("#1f2933"))
    canvas.setLineWidth(0.7)
    canvas.circle(cx, cy, radius, stroke=1, fill=0)
    path = canvas.beginPath()
    path.moveTo(*tip)
    path.lineTo(*left)
    path.lineTo(cx, cy)
    path.lineTo(*right)
    path.close()
    canvas.drawPath(path, stroke=1, fill=1)
    canvas.setFont("Helvetica-Bold", 6.5)
    canvas.drawCentredString(cx, cy - radius - 8, "N")


def render_pdf(reference: dict) -> bytes:
    """The Survey Reference sheet. Returns PDF bytes.

    Layout order is the order a person asks the questions in: what is this,
    what does it show, what was read, what is partial, what is unresolved,
    where did it come from. Unresolved items are a compact list, never prose -
    the direction is explicit about that, and a long apology would bury the
    three facts that matter.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        ListFlowable,
        ListItem,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    styles = getSampleStyleSheet()
    small = ParagraphStyle("SurveyRefSmall", parent=styles["BodyText"],
                           fontSize=8, leading=10.5, spaceAfter=2)
    body = ParagraphStyle("SurveyRefBody", parent=styles["BodyText"],
                          fontSize=9, leading=12)
    heading = ParagraphStyle("SurveyRefHeading", parent=styles["Heading2"],
                             fontSize=11, leading=13, spaceBefore=10, spaceAfter=4)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        title=reference.get("title") or REFERENCE_TITLE,
        author="ARCHIOSK GO",
        subject="Derived working reference - not a certified or legal survey")

    flow = [Paragraph(_escape(reference.get("title") or REFERENCE_TITLE), styles["Title"])]
    if reference.get("display_name"):
        flow.append(Paragraph(_escape(reference["display_name"]), styles["Italic"]))
    flow.append(Spacer(1, 4))
    # The short note, not a paragraph of caveat.
    flow.append(Paragraph("<b>Source:</b> %s" % _escape(reference.get("source_note") or SOURCE_NOTE),
                          small))
    flow.append(Paragraph(_escape(reference.get("authority_note") or AUTHORITY_NOTE), small))
    flow.append(Spacer(1, 10))

    resolved = resolved_plan(reference)
    stats = resolved["stats"]
    if resolved["primitives"]:
        flow.append(plan_panel(resolved, 7.1 * inch, 4.0 * inch,
                               reference.get("frame_size")))
        flow.append(Spacer(1, 4))
        legend = []
        if stats["arcs"]:
            legend.append("Curved boundaries are reconstructed as true arcs from "
                          "the radius and chord printed on the source, not "
                          "approximated by straight segments.")
        if stats["straights"]:
            legend.append("Solid lines are boundaries read from the source; "
                          "dashed lines were only partly legible.")
        if stats["footprints"]:
            legend.append("Shaded: building footprints, in their relative "
                          "positions on the source.")
        if not stats["closed"]:
            legend.append("The boundary is drawn OPEN where the source's own "
                          "chain does not close; nothing has been joined up to "
                          "make it look complete.")
        legend.append("Not to scale. No dimension is drawn that was not read "
                      "from the source.")
        flow.append(Paragraph(" ".join(_escape(item) for item in legend), small))
    else:
        flow.append(Paragraph("No boundary geometry could be reconstructed from "
                              "the source image. Everything below was read as "
                              "text.", body))

    def _facts_table(title, entries, note=None):
        if not entries:
            return
        flow.append(Paragraph(_escape(title), heading))
        data = [[Paragraph("<b>%s</b>" % _escape(entry["label"]), body),
                 Paragraph(_escape(entry["value"] or "identified"), body)]
                for entry in entries]
        grid = Table(data, colWidths=[2.0 * inch, 5.1 * inch], hAlign="LEFT")
        grid.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfd6dd")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        flow.append(grid)
        if note:
            flow.append(Spacer(1, 3))
            flow.append(Paragraph(_escape(note), small))

    _facts_table("Recovered", reference.get("recovered") or [])
    _facts_table("Partially recovered", reference.get("partially_recovered") or [],
                 note="Legible in part only. Confirm against the original before use.")

    unresolved = list(reference.get("unresolved") or [])
    unresolved += ["%s - read but not reliable enough to state" % entry["label"]
                   for entry in (reference.get("withheld") or [])]
    if unresolved:
        flow.append(Paragraph("Unresolved", heading))
        flow.append(ListFlowable(
            [ListItem(Paragraph(_escape(item), body), leftIndent=12)
             for item in unresolved],
            bulletType="bullet", start="square", leftIndent=12))

    flow.append(Paragraph("Provenance", heading))
    provenance = [
        ("Original file", reference.get("source_filename") or ""),
        ("Original checksum (SHA-256)", reference.get("source_sha256") or "not recorded"),
        ("Source record", reference.get("source_id") or ""),
        ("Project", reference.get("project_id") or ""),
        ("Pages / images used", ", ".join(str(p) for p in (reference.get("pages_used") or []))),
        ("Source frame examined", "%s x %s px" % tuple(reference["frame_size"])
         if reference.get("frame_size") else "not recorded"),
        ("Generated", reference.get("generated_at") or ""),
        ("Read by", "%s (%s)" % (reference.get("model") or "unrecorded",
                                 reference.get("prompt_version") or REFERENCE_VERSION)),
        ("Basis", "Visual reading of the source image. Every item above is "
                  "GO's reading, not a statement by the surveyor."),
    ]
    grid = Table([[Paragraph("<b>%s</b>" % _escape(k), small),
                   Paragraph(_escape(v), small)] for k, v in provenance],
                 colWidths=[2.0 * inch, 5.1 * inch], hAlign="LEFT")
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    flow.append(grid)

    doc.build(flow)
    return buffer.getvalue()


def resolved_plan(reference: dict) -> dict:
    """The stored graph, resolved to primitives.

    ONE resolver for the exported sheet and the on-screen review drawing, so
    the two cannot describe the same parcel differently. Recomputed from the
    graph rather than stored as primitives: the graph is the evidence, and
    primitives are a rendering of it that a future change to the geometry rules
    should be able to improve without rewriting stored records.
    """
    from services import survey_graph

    graph = (reference or {}).get("graph") or {}
    if not graph.get("nodes"):
        return {"primitives": [], "unresolved": [],
                "stats": {"arcs": 0, "straights": 0, "nodes": 0,
                          "footprints": 0, "closed": False}}
    return survey_graph.fit_to_frame(survey_graph.build_primitives(graph))


def review_svg(reference: dict, width: int = 560, height: int = 420) -> str:
    """The reconstruction as inline SVG, for the side-by-side review."""
    from services import survey_graph

    return survey_graph.emit_svg(resolved_plan(reference), width=width,
                                 height=height,
                                 frame_size=(reference or {}).get("frame_size"))


def artifact_filename(display_name: str = "") -> str:
    stem = (display_name or "").strip() or REFERENCE_TITLE
    return "%s - Survey Reference.pdf" % stem
