"""Annotation-grounded semantic classification of structural linework.

WHAT MAKES THIS "GROUNDED" RATHER THAN "COLOURED IN"

The cheap version of this feature draws a box around a piece of text, tints
whatever vectors fall inside it, and calls the result a classification. That is
proximity, not evidence: it cannot tell a beam tag sitting on its beam from a
beam tag that happens to overlap a dimension line, and it produces confident
colour over geometry nobody annotated.

This derives the link geometrically instead. On these sheets the drafting
convention is that a member designation is placed ON its member, running along
the member's own axis. So a DIRECT link requires all four of:

  1. the text is a real member designation - W-shape, HSS or angle - matched
     against the CISC-style patterns below, not merely "some text";
  2. a straight path exists whose axis AGREES with the text's writing
     direction (a horizontal tag may only claim a horizontal member);
  3. the text sits within a small PERPENDICULAR distance of that path;
  4. the text's extent ALONG the axis lies within the path's own span - a tag
     floating past the end of a member is not labelling it.

If two or more members satisfy that equally, the tag is ambiguous and the
geometry is NOT promoted to DIRECT. Refusing to choose is the point.

INFERRED is reserved for geometry that continues a DIRECT member: collinear,
same axis, sharing an endpoint within tolerance. That is a real structural
continuation, not a guess about an unrelated line.

Everything else is UNRESOLVED and is expected to be the large majority.

Coordinates are emitted in the sheet's NATIVE viewing orientation so the
overlay registers against the rendered image without a second transform.

Read-only: the source PDF is never written.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

try:
    import fitz
except ImportError:  # pragma: no cover
    sys.exit("PyMuPDF is required: pip install pymupdf")

DEFAULT_SOURCE = r"C:\Archiosk\Samples\5 Nipigon"

# CISC-style designations. Deliberately strict: "300" or "1:50" must not become
# a structural member because it happens to sit near a line.
MEMBER_PATTERNS = [
    ("beam", re.compile(r"^W\d{3}X\d{2,3}(\.\d)?$", re.I)),
    ("column", re.compile(r"^HS{1,2}\d{2,3}X\d{2,3}X\d{1,2}(\.\d)?$", re.I)),
    ("angle", re.compile(r"^L\d{2,3}X\d{2,3}X\d{1,2}(\.\d)?$", re.I)),
]

# Annotations that explicitly REFUSE to specify a member. These must never be
# promoted to a classified member; the sheet is saying it does not know.
NON_SPECIFIED = re.compile(r"non[- ]?specified", re.I)

PERP_TOL = 9.0      # pt - how far off its member a tag may sit
ALIGN_TOL = 0.30    # axis agreement
MIN_LEN = 24.0      # pt - shorter paths are ticks, hatching, arrowheads
JOIN_TOL = 4.0      # pt - endpoint sharing for a continuation


def classify_token(token):
    for kind, pattern in MEMBER_PATTERNS:
        if pattern.match(token):
            return kind
    return None


def segments(page):
    """Straight, long-enough line segments, in the page's current orientation."""
    out = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] != "l":
                continue
            p0, p1 = item[1], item[2]
            dx, dy = p1.x - p0.x, p1.y - p0.y
            length = math.hypot(dx, dy)
            if length < MIN_LEN:
                continue
            out.append({
                "x0": p0.x, "y0": p0.y, "x1": p1.x, "y1": p1.y,
                "len": length,
                "ux": dx / length, "uy": dy / length,
                "width": drawing.get("width") or 0,
            })
    return out


def _pt(x, y, m):
    p = fitz.Point(x, y) * m
    return round(p.x, 2), round(p.y, 2)


def _seg_view(seg, m):
    x0, y0 = _pt(seg["x0"], seg["y0"], m)
    x1, y1 = _pt(seg["x1"], seg["y1"], m)
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1}


def _box_view(box, m):
    x0, y0 = _pt(box[0], box[1], m)
    x1, y1 = _pt(box[2], box[3], m)
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def point_to_segment(px, py, seg):
    """Perpendicular distance, and the parametric position along the segment."""
    vx, vy = seg["x1"] - seg["x0"], seg["y1"] - seg["y0"]
    wx, wy = px - seg["x0"], py - seg["y0"]
    denom = vx * vx + vy * vy
    t = 0.0 if denom == 0 else (wx * vx + wy * vy) / denom
    t_clamped = max(0.0, min(1.0, t))
    cx, cy = seg["x0"] + t_clamped * vx, seg["y0"] + t_clamped * vy
    return math.hypot(px - cx, py - cy), t


def derive(path, sheet, absolute_rotation):
    doc = fitz.open(path)
    page = doc[0]

    # VERIFIED, and it matters: neither get_text("words") bboxes nor
    # get_drawings() coordinates respond to set_rotation - both are reported in
    # UNROTATED content space. That is why classification runs in content
    # space, where text and geometry genuinely share a frame, and only the
    # EMITTED coordinates are transformed into the native view. Classifying in
    # one space while declaring the view box of another is exactly how an
    # overlay ends up confidently drawn over the wrong lines.
    page.set_rotation(absolute_rotation)
    to_view = page.rotation_matrix
    view_rect = page.rect

    words = page.get_text("words")
    segs = segments(page)

    tags = []
    for x0, y0, x1, y1, token, *_ in words:
        kind = classify_token(token)
        if kind:
            tags.append({"token": token, "kind": kind,
                         "x0": x0, "y0": y0, "x1": x1, "y1": y1})

    refusals = [w[4] for w in words if NON_SPECIFIED.search(w[4])]

    direct, ambiguous, unmatched = [], [], []
    claimed = set()

    for tag in tags:
        cx, cy = (tag["x0"] + tag["x1"]) / 2.0, (tag["y0"] + tag["y1"]) / 2.0
        w, h = tag["x1"] - tag["x0"], tag["y1"] - tag["y0"]
        # The tag runs along its longer dimension; that is its writing axis.
        tag_ux, tag_uy = (1.0, 0.0) if w >= h else (0.0, 1.0)

        matches = []
        for i, seg in enumerate(segs):
            # 2. axis agreement
            if abs(seg["ux"] * tag_ux + seg["uy"] * tag_uy) < (1.0 - ALIGN_TOL):
                continue
            dist, t = point_to_segment(cx, cy, seg)
            # 3. perpendicular proximity
            if dist > PERP_TOL:
                continue
            # 4. the tag lies within the member's own span
            if t < -0.02 or t > 1.02:
                continue
            matches.append((dist, i, seg))

        if not matches:
            unmatched.append(tag)
            continue
        matches.sort(key=lambda m: m[0])
        # A single clear winner, or the tag is ambiguous and claims nothing.
        if len(matches) > 1 and matches[1][0] < matches[0][0] * 1.6:
            ambiguous.append({"tag": tag, "candidates": len(matches)})
            continue

        dist, idx, seg = matches[0]
        claimed.add(idx)
        direct.append({
            "token": tag["token"], "kind": tag["kind"],
            # kept in CONTENT space for the continuation pass below, stripped
            # before the result is written - the two spaces must never meet.
            "_content": seg,
            "seg": _seg_view(seg, to_view),
            "tag_box": _box_view([tag["x0"], tag["y0"], tag["x1"], tag["y1"]], to_view),
            "perp_pt": round(dist, 2),
            "basis": "direct",
            "evidence": "designation %s lies on a %s path within %.1fpt, axes "
                        "aligned, tag inside the member span"
                        % (tag["token"],
                           "horizontal" if abs(seg["ux"]) > abs(seg["uy"]) else "vertical",
                           dist),
        })

    # INFERRED - collinear continuation of a DIRECT member.
    inferred = []
    for d in direct:
        s = d["_content"]
        for i, seg in enumerate(segs):
            if i in claimed:
                continue
            ax = (s["x1"] - s["x0"], s["y1"] - s["y0"])
            alen = math.hypot(*ax) or 1
            aux, auy = ax[0] / alen, ax[1] / alen
            if abs(seg["ux"] * aux + seg["uy"] * auy) < (1.0 - ALIGN_TOL):
                continue
            shares = min(
                math.hypot(seg["x0"] - s["x1"], seg["y0"] - s["y1"]),
                math.hypot(seg["x1"] - s["x0"], seg["y1"] - s["y0"]),
                math.hypot(seg["x0"] - s["x0"], seg["y0"] - s["y0"]),
                math.hypot(seg["x1"] - s["x1"], seg["y1"] - s["y1"]),
            )
            if shares > JOIN_TOL:
                continue
            claimed.add(i)
            inferred.append({
                "token": d["token"], "kind": d["kind"],
                "seg": _seg_view(seg, to_view),
                "basis": "inferred",
                "evidence": "collinear continuation sharing an endpoint with "
                            "the %s member within %.1fpt; carries no "
                            "designation of its own" % (d["token"], shares),
            })

    for d in direct:
        d.pop("_content", None)

    result = {
        "sheet": sheet,
        "source_file": os.path.basename(path),
        "orientation_absolute": absolute_rotation,
        "view_width_pt": round(view_rect.width, 2),
        "view_height_pt": round(view_rect.height, 2),
        "coordinate_space": "native view (content coords transformed by "
                            "page.rotation_matrix)",
        "counts": {
            "text_items": len(words),
            "member_designations_found": len(tags),
            "segments_considered": len(segs),
            "direct": len(direct),
            "inferred": len(inferred),
            "unresolved_segments": len(segs) - len(claimed),
            "tags_without_a_member": len(unmatched),
            "tags_ambiguous": len(ambiguous),
            "explicit_non_specified": len(refusals),
        },
        "direct": direct,
        "inferred": inferred,
        "unmatched_tags": [t["token"] for t in unmatched],
        "ambiguous_tags": [a["tag"]["token"] for a in ambiguous],
        "non_specified_notes": refusals,
    }
    doc.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default=DEFAULT_SOURCE)
    parser.add_argument("--sheet", default="RS501")
    parser.add_argument("--file", default="212109 RS501 STRUCTURAL FRAMING.pdf")
    parser.add_argument("--rotation", type=int, default=90)
    parser.add_argument("--out", default=os.path.join("static", "nipigon",
                                                      "semantics_RS501.json"))
    args = parser.parse_args()

    path = os.path.join(args.source_root, args.file)
    if not os.path.exists(path):
        sys.exit("Source not found: %s" % path)

    result = derive(path, args.sheet, args.rotation)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1)

    c = result["counts"]
    print("%s - annotation-grounded classification" % args.sheet)
    for k in ("text_items", "member_designations_found", "segments_considered",
              "direct", "inferred", "unresolved_segments",
              "tags_without_a_member", "tags_ambiguous",
              "explicit_non_specified"):
        print("  %-28s %d" % (k, c[k]))
    if result["ambiguous_tags"]:
        print("  ambiguous:", result["ambiguous_tags"][:10])
    if result["non_specified_notes"]:
        print("  refusals :", result["non_specified_notes"])
    print("wrote", args.out)


if __name__ == "__main__":
    raise SystemExit(main())
