"""CLAUDE-PLANNING-WORKSPACE-02A - visual evidence, drawn from what we measured.

    RETRIEVED MUNICIPAL GEOMETRY  ->  SVG PANEL  +  ITS OWN PROVENANCE

THE VISUAL IS THE EVIDENCE, OR IT IS DECORATION. Section 9 asks for official
visual evidence and forbids decorative imagery, and those two requirements
together rule out the obvious implementation. Fetching a rendered basemap tile
from a municipal map service would give a picture that LOOKS authoritative while
being, evidentially, a screenshot: ARCHIOSK could not say which geometry it
contains, could not hash it, could not tell whether the parcel drawn on it is the
parcel the spatial engine measured, and would be redistributing map imagery whose
licensing nobody in this repository has assessed.

So the panels here are drawn from THE EXACT GEOMETRY THE DETERMINISTIC ENGINE
ALREADY RELATED. Same rings, same CRS, same `geometry_hash` that
`deterministic_spatial` puts in a spatial token's provenance. That makes a panel
checkable in a way a basemap never is: the picture and the finding cite the same
bytes, and a test can assert the hash on the panel equals the hash on the token.

NO NEW MUNICIPAL REQUEST IS MADE HERE, and that is deliberate beyond politeness.
This module receives geometry and returns markup; it has no reader, no URL and no
network import, so it cannot become a second retrieval path whose currentness
differs from the result it illustrates. A panel is always as current as the
retrieval that produced the finding beside it, because it IS that retrieval.

WHAT A PANEL MAY NOT IMPLY. It is not a survey, not a plan of survey, not a
municipal map, and not a statement of boundary. The City's own parcel polygon is
a record of a boundary, not a measurement of one, and `toronto_gate01` already
says so about the stated area. Every panel carries that limitation as text,
because a drawing invites a reader to measure it.

COORDINATES ARE EPSG:3857 METRES, which is what the City publishes and what the
engine relates. No reprojection happens here - an untested transform written into
a rendering module would be exactly the silent error `deterministic_spatial`'s own
docstring warns about, and a panel does not need one: a local extent of a few
hundred metres renders correctly from Web Mercator without any correction that
would change what a reader sees at this scale.
"""
from __future__ import annotations

from typing import Optional

VISUAL_VERSION = "planning-visual@1"

#: A panel is a drawing, and a drawing of 280,000 vertices is not a drawing. The
#: cap is a RENDERING bound and never a geometry bound: exceeding it declines the
#: panel rather than simplifying the ring, because a simplified boundary shown as
#: evidence is a different boundary. `deterministic_spatial` refuses to guess
#: outside its competence; so does this.
MAX_PANEL_VERTICES = 4000

#: Panel kinds, each tied to a layer ARCHIOSK actually retrieves.
PANEL_PARCEL = "SUBJECT_PARCEL"
PANEL_ZONING = "ZONING_CONTEXT"

DECLINED_NO_GEOMETRY = "no geometry was retrieved for this layer"
DECLINED_TOO_COMPLEX = ("the retrieved geometry exceeds the panel vertex bound; "
                        "it is not simplified for display")
DECLINED_DEGENERATE = "the retrieved geometry has no extent to draw"

LIMITATION = ("Drawn from the municipality's own retrieved polygon. A municipal "
              "parcel polygon is a record of a boundary, not a survey of one, "
              "and no dimension may be scaled off this panel.")


def _rings(geometry) -> list:
    """Every exterior ring, whatever the GeoJSON type. Holes are not drawn."""
    if not isinstance(geometry, dict):
        return []
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [ring for ring in coordinates[:1] if ring]
    if kind == "MultiPolygon":
        return [part[0] for part in coordinates if part and part[0]]
    return []


def _extent(rings) -> Optional[tuple]:
    xs = [point[0] for ring in rings for point in ring if len(point) >= 2]
    ys = [point[1] for ring in rings for point in ring if len(point) >= 2]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _path(ring, extent, size, pad) -> str:
    minx, miny, maxx, maxy = extent
    width, height = max(maxx - minx, 1e-9), max(maxy - miny, 1e-9)
    scale = (size - 2 * pad) / max(width, height)
    # Centre the extent in the square, and FLIP Y: SVG's y axis grows downward
    # while projected northing grows upward, so a panel drawn without the flip is
    # a mirror image of the parcel - wrong in a way that looks plausible.
    offset_x = pad + ((size - 2 * pad) - width * scale) / 2.0
    offset_y = pad + ((size - 2 * pad) - height * scale) / 2.0
    parts = []
    for index, point in enumerate(ring):
        if len(point) < 2:
            continue
        x = offset_x + (point[0] - minx) * scale
        y = size - offset_y - (point[1] - miny) * scale
        parts.append("%s%.2f %.2f" % ("M" if index == 0 else "L", x, y))
    return " ".join(parts) + " Z" if parts else ""


def panel(kind, geometry, *, title, source, layer, retrieved_at=None,
          evidence_ref=None, parcel_identifier=None, subject_geometry=None,
          size=320, pad=12) -> dict:
    """One visual panel, or an honest refusal to draw one.

    Returns `{kind, title, drawn, svg, provenance, declined_reason, ...}`.
    `drawn` is False with a stated reason rather than an empty box - a panel that
    silently renders nothing is indistinguishable from a layer that does not
    apply, and those are opposite findings.

    `subject_geometry` draws the parcel over a context layer so a reader can see
    WHERE the subject sits inside it, which is the only thing a zoning-context
    panel is for.
    """
    rings = _rings(geometry)
    subject_rings = _rings(subject_geometry) if subject_geometry else []
    vertices = sum(len(ring) for ring in rings + subject_rings)

    record = {
        "visual_version": VISUAL_VERSION,
        "kind": kind,
        "title": title,
        "source": source,
        "layer": layer,
        "retrieved_at": retrieved_at,
        "evidence_ref": evidence_ref,
        "parcel_identifier": parcel_identifier,
        "crs": "EPSG:3857",
        "vertex_count": vertices,
        "limitation": LIMITATION,
        "drawn": False,
        "svg": None,
        "declined_reason": None,
        "is_official": True,
        "is_user_supplied": False,
    }

    if not rings:
        record["declined_reason"] = DECLINED_NO_GEOMETRY
        return record
    if vertices > MAX_PANEL_VERTICES:
        record["declined_reason"] = DECLINED_TOO_COMPLEX
        return record

    extent = _extent(rings + subject_rings)
    if extent is None:
        record["declined_reason"] = DECLINED_NO_GEOMETRY
        return record
    minx, miny, maxx, maxy = extent
    if (maxx - minx) <= 0 and (maxy - miny) <= 0:
        record["declined_reason"] = DECLINED_DEGENERATE
        return record

    layer_paths = "".join(
        '<path d="%s" class="pz-panel-layer"/>' % _path(ring, extent, size, pad)
        for ring in rings)
    subject_paths = "".join(
        '<path d="%s" class="pz-panel-subject"/>' % _path(ring, extent, size, pad)
        for ring in subject_rings)

    # The extent in metres, stated rather than drawn as a scale bar: a bar is
    # measured off the page, and this panel explicitly must not be.
    record["extent_metres"] = (round(maxx - minx, 1), round(maxy - miny, 1))
    record["svg"] = (
        '<svg viewBox="0 0 %d %d" role="img" class="pz-panel-svg" '
        'aria-label="%s" xmlns="http://www.w3.org/2000/svg">'
        '%s%s</svg>' % (size, size, _escape(title), layer_paths, subject_paths))
    record["drawn"] = True
    return record


def _escape(value) -> str:
    return (str(value or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def panels_for(retrieval, *, tokens=None) -> list:
    """Every panel the retrieval supports, in a stable order.

    READS ONLY WHAT THE RETRIEVAL ALREADY CARRIES. A layer whose geometry was not
    surfaced produces no panel and no claim - never a placeholder, because an
    empty frame beside nine real ones reads as "nothing here" rather than as
    "not retrieved".
    """
    retrieval = retrieval or {}
    tokens = tokens or {}
    geometry = retrieval.get("visual_geometry") or {}
    parcel = geometry.get("parcel") or {}
    zoning = geometry.get("zoning") or {}
    retrieved_at = retrieval.get("retrieved_at")
    parcel_id = parcel.get("parcel_identifier")

    built = []
    if parcel.get("geometry"):
        built.append(panel(
            PANEL_PARCEL, parcel["geometry"],
            title="Subject parcel",
            source=parcel.get("source") or "City of Toronto property boundary",
            layer=parcel.get("layer") or "Property Boundary",
            retrieved_at=retrieved_at, parcel_identifier=parcel_id,
            evidence_ref=(tokens.get("zoning_area") or {}).get(
                "provenance", {}).get("subject_geometry_id")
            or parcel.get("geometry_id")))
    if zoning.get("geometry"):
        built.append(panel(
            PANEL_ZONING, zoning["geometry"],
            title="Zoning context and subject parcel",
            source=zoning.get("source") or "City of Toronto Zoning Area",
            layer=zoning.get("layer") or "Zoning Area",
            retrieved_at=retrieved_at, parcel_identifier=parcel_id,
            evidence_ref=(tokens.get("zoning_area") or {}).get(
                "provenance", {}).get("layer_geometry_id")
            or zoning.get("geometry_id"),
            subject_geometry=parcel.get("geometry")))
    return built


def user_supplied_panel(*, name, kind=None, byte_count=None, digest=None) -> dict:
    """Section 23. A person's own visual, labelled so it can never be mistaken.

    NO IMAGE BYTES TRAVEL THROUGH THIS RECORD. What a supplied visual needs in
    order to be discussed is its identity, not its pixels re-encoded into a
    surface that also carries municipal evidence.
    """
    return {
        "visual_version": VISUAL_VERSION,
        "kind": "USER_SUPPLIED_VISUAL",
        "title": name or "(unnamed)",
        "source": "Supplied by a person using ARCHIOSK",
        "layer": kind,
        "retrieved_at": None,
        "evidence_ref": digest,
        "byte_count": byte_count,
        "drawn": False,
        "svg": None,
        "declined_reason": None,
        "label": "USER-SUPPLIED",
        "is_official": False,
        "is_user_supplied": True,
        "limitation": ("Supplied by a person. Not a municipal record, not "
                       "verified by ARCHIOSK, and not deterministic geometry. A "
                       "screenshot is not an authority, a markup is not a "
                       "property fact, and a sketch is not an approved design."),
    }
