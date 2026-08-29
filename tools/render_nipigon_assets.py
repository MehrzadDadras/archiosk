"""Render 5 Nipigon source PDFs into addressable raster assets, with provenance.

WHY THIS EXISTS, AND WHY IT NEEDED A NEW MINIATURE BASIS

The Page-Field grammar deliberately has no `cached` miniature basis: a captured
thumbnail is the one representation that cannot state its own age from inside
itself, so it asserts "this is what that surface looks like" more fluently than
a sentence while possibly being stale.

Real project drawings are PDFs. There is no shared vector macro to render twice,
so `live` is not available and `kind` would be a lie - these faces show specific
content, not a category. The honest answer is a THIRD basis, `rendered`, which
is admissible only because this tool makes it answer the objection: every asset
is written alongside a manifest recording the source filename, its SHA-256, the
page index, the dpi, and the render time. A `rendered` miniature can therefore
state exactly what it is a picture of and when it was taken; an anonymous
thumbnail cannot.

Nothing under the source root is written, moved or renamed. Output is
git-ignored: these are derived bytes, and the PDFs remain authoritative.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - environment guard
    sys.exit("PyMuPDF is required: pip install pymupdf")

DEFAULT_SOURCE = r"C:\Archiosk\Samples\5 Nipigon"
DEFAULT_OUT = os.path.join("static", "nipigon")

# Only the sheets the coordination scenario actually uses. Rendering all 51
# would be 51 rasters nothing references - derived bytes with no consumer.
SHEETS = [
    ("A204", "212109 A204 GROUND FLOOR PLAN.pdf"),
    ("A205", "212109 A205 SECOND FLOOR PLAN.pdf"),
    ("A801", "212109 A801 WASHROOM DETAILS.pdf"),
    ("A701", "212109 A701 PLAN DETAILS.pdf"),
    ("A302", "212109 A302 GROUND FLOOR RCP.pdf"),
    ("A902", "212109 A902 DOOR WINDOW SCH.pdf"),
    ("A100", "212109 A100 COVER PAGE.pdf"),
    # The detail-sheet family, which is the sibling set Pane 2 steps through.
    # Grouped because the cover index lists them as the DETAILS series, not
    # because they were assumed to be related.
    ("A509", "212109 A509 DETAIL.pdf"),
    ("A510", "212109 A510 DETAIL.pdf"),
    ("A511", "212109 A511 DETAIL.pdf"),
    ("RS501", "212109 RS501 STRUCTURAL FRAMING.pdf"),
]

# Crops are declared in PDF points against the source page box, so they are a
# statement about the DRAWING, not about any particular rendered pixel size.
# Verified visually before being written down; see the mission report.
CROPS = {
    # Room 104, the barrier-free washroom, and the 1/A801 callout beneath it.
    "A204": {"washroom-104": (295.0, 555.0, 755.0, 885.0)},
    # Detail 1/A801 HANDICAP WASHROOM PLAN - 104, top-left of the sheet.
    "A801": {"detail-1-104": (60.0, 90.0, 610.0, 760.0)},
}


# ---------------------------------------------------------------------------
# NATIVE VIEWING ORIENTATION
#
# A PDF's /Rotate is not the same question as "which way up is a human meant to
# read this sheet". In this set it answers neither reliably:
#
#   - 38 of 49 sheets are stored PORTRAIT with /Rotate 0 and carry NO text
#     layer at all. Their title block runs along the bottom edge with its text
#     turned 90 degrees; read as stored, every one of them is on its end.
#   - The 10 RS sheets DO carry /Rotate 90, and it is correct - which is why a
#     derivation may not simply overwrite it.
#
# So the derived value is an ADDITIONAL rotation, and the absolute viewing
# rotation is (stored + additional) % 360. Deriving an absolute value instead
# was a real defect: it undid the publisher's own /Rotate on the RS sheets and
# stood them upright when they were already correct.
#
# TWO SIGNALS, strongest first.
#
#   TEXT       When a real text layer exists, the writing direction settles it:
#              rotate until the text reads left-to-right on screen. Note that
#              PyMuPDF reports `dir` in UNROTATED content space and it does not
#              respond to set_rotation - verified - so the additional rotation
#              is computed against the stored /Rotate rather than found by
#              re-reading at each candidate.
#
#   TITLEBLOCK Otherwise, fall back to where the title block is. On these
#              sheets it is the densest band along one edge and belongs on the
#              RIGHT. Only rotations that leave the sheet LANDSCAPE are
#              candidates - these are 24x36 sheets drawn landscape, so a
#              rotation that returns a portrait result has not oriented the
#              drawing, it has stood it on end. That constraint is evidence
#              about the drawing, not a preference, and it is what corrected
#              A508/A603/A606 from a confident-looking 180.
#
# Neither signal invents certainty. When the winning edge is not clearly denser
# than the runner-up the sheet is still rendered - refusing to show a drawing
# helps nobody - but it is flagged `needs_confirmation` so a human can settle
# it, and the surface can say so.
# ---------------------------------------------------------------------------

ORIENTATION_BAND = 0.11      # outer fraction of each side sampled for ink
ORIENTATION_DPI = 20
ORIENTATION_MARGIN = 1.30    # how much denser the winning edge must be
ORIENTATION_MIN_SPANS = 40   # below this a text layer is not a usable signal


def _edge_density(page):
    pix = page.get_pixmap(dpi=ORIENTATION_DPI, colorspace=fitz.csGRAY)
    w, h, data = pix.width, pix.height, pix.samples
    bw = max(1, int(w * ORIENTATION_BAND))
    bh = max(1, int(h * ORIENTATION_BAND))

    def frac(x0, y0, x1, y1):
        ink = tot = 0
        for y in range(y0, y1):
            row = y * w
            for x in range(x0, x1):
                tot += 1
                if data[row + x] < 160:
                    ink += 1
        return ink / float(tot or 1)

    return {"top": frac(0, 0, w, bh), "bottom": frac(0, h - bh, w, h),
            "left": frac(0, 0, bw, h), "right": frac(w - bw, 0, w, h)}


def _text_direction(page):
    """Dominant writing direction in UNROTATED content space, or None."""
    counts = {0: 0, 90: 0, 180: 0, 270: 0}
    total = 0
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            dx, dy = line.get("dir", (1, 0))
            n = len(line.get("spans", []))
            total += n
            if abs(dx) > abs(dy):
                counts[0 if dx > 0 else 180] += n
            else:
                counts[90 if dy < 0 else 270] += n
    if total < ORIENTATION_MIN_SPANS:
        return None, total, counts
    best = max(counts, key=counts.get)
    if counts[best] < 0.5 * total:
        return None, total, counts
    return best, total, counts


def derive_orientation(page):
    """The sheet's native viewing orientation, with the evidence that fixed it."""
    stored = page.rotation

    direction, spans, counts = _text_direction(page)
    if direction is not None:
        additional = (direction - stored) % 360
        return {
            "stored_rotate": stored,
            "additional": additional,
            "absolute": (stored + additional) % 360,
            "signal": "text",
            "evidence": "dominant writing direction %ddeg over %d spans "
                        "in unrotated content space" % (direction, spans),
            "margin": None,
            "needs_confirmation": False,
        }

    landscape_now = page.rect.width > page.rect.height
    candidates = [0, 180] if landscape_now else [90, 270]
    scored = []
    for add in candidates:
        page.set_rotation((stored + add) % 360)
        scored.append((add, _edge_density(page)["right"]))
    page.set_rotation(stored)

    scored.sort(key=lambda t: t[1], reverse=True)
    (best, best_right), (_, runner_right) = scored[0], scored[1]
    margin = (best_right / runner_right) if runner_right else float("inf")

    return {
        "stored_rotate": stored,
        "additional": best,
        "absolute": (stored + best) % 360,
        "signal": "titleblock",
        "evidence": "no text layer; densest edge band placed on the right, "
                    "landscape-constrained (ink ratio %.2f vs runner-up)"
                    % (margin if margin != float("inf") else -1),
        "margin": None if margin == float("inf") else round(margin, 2),
        "needs_confirmation": margin < ORIENTATION_MARGIN,
    }


def is_monochrome(page, sample_dpi: int = 24, tolerance: int = 18) -> bool:
    """Does this sheet carry real colour, or is it black line on white paper?

    The answer decides how the drawing may be re-tinted for a dark field. A
    monochrome sheet can be inverted to light-on-black without losing anything,
    because there is nothing in it but ink and paper. A sheet with real colour
    - a coloured hatch, a highlighted zone, a red revision cloud - must be left
    alone: re-tinting it would silently overwrite information the drafter put
    there deliberately, which is a drawing telling a lie about itself.

    Measured, not assumed, and recorded in the manifest so the surface acts on
    a fact rather than on a guess about a file it has never opened.
    """
    pix = page.get_pixmap(dpi=sample_dpi)
    if pix.n < 3:
        return True
    data = pix.samples
    stride = pix.n
    for i in range(0, len(data) - stride, stride * 7):
        r, g, b = data[i], data[i + 1], data[i + 2]
        if max(r, g, b) - min(r, g, b) > tolerance:
            return False
    return True


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render(source_root: str, out_dir: str, thumb_dpi: int, page_dpi: int) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    manifest = {
        "tool": "tools/render_nipigon_assets.py",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": source_root,
        "basis": "rendered",
        "assets": [],
    }

    for sheet, filename in SHEETS:
        path = os.path.join(source_root, filename)
        if not os.path.exists(path):
            print("  MISSING  %s (%s) - skipped, not faked" % (sheet, filename))
            continue

        doc = fitz.open(path)
        page = doc[0]

        orientation = derive_orientation(page)
        # Every render below is produced in the NATIVE orientation, so the
        # miniature and the expanded sheet cannot disagree - they are the same
        # rotation of the same page, not two independent guesses. The source
        # PDF is never written; set_rotation acts on the in-memory document.
        page.set_rotation(orientation["absolute"])

        entry = {
            "sheet": sheet,
            "source_file": filename,
            "source_sha256": sha256(path),
            "source_bytes": os.path.getsize(path),
            "page_index": 0,
            "page_count": doc.page_count,
            "page_width_pt": round(page.rect.width, 2),
            "page_height_pt": round(page.rect.height, 2),
            "monochrome": is_monochrome(page),
            "orientation": orientation,
            # Recorded AFTER rotation: this is the box a viewer actually sees.
            "view_width_pt": round(page.rect.width, 2),
            "view_height_pt": round(page.rect.height, 2),
            "renders": [],
        }

        for label, dpi in (("thumb", thumb_dpi), ("page", page_dpi)):
            pix = page.get_pixmap(dpi=dpi)
            name = "%s_%s.png" % (sheet, label)
            pix.save(os.path.join(out_dir, name))
            entry["renders"].append({
                "role": label, "file": name, "dpi": dpi,
                "width": pix.width, "height": pix.height,
                "clip_pt": None,
            })

        # CROPS are declared in the page's STORED display space, because that
        # is the space they were measured in by looking at the sheet. Applying
        # them after the native rotation silently moved the washroom crop onto
        # a car - a clip rect is not rotation-invariant. So crop in the space
        # the rect belongs to, then rotate the resulting image.
        for label, rect in CROPS.get(sheet, {}).items():
            page.set_rotation(orientation["stored_rotate"])
            clip = fitz.Rect(*rect)
            pix = page.get_pixmap(dpi=page_dpi, clip=clip)
            page.set_rotation(orientation["absolute"])
            name = "%s_%s.png" % (sheet, label)
            dest = os.path.join(out_dir, name)
            pix.save(dest)
            add = orientation["additional"] % 360
            if add:
                # PDF rotation is clockwise; PIL rotates counter-clockwise.
                from PIL import Image
                with Image.open(dest) as img:
                    img.rotate((360 - add) % 360, expand=True).save(dest)
                pix = None
            from PIL import Image as _I
            with _I.open(dest) as _im:
                cw, ch = _im.size
            entry["renders"].append({
                "role": label, "file": name, "dpi": page_dpi,
                "width": cw, "height": ch,
                "clip_pt": [round(v, 2) for v in rect],
                "clip_space": "stored_rotation",
                "rotated_by": add,
            })

        doc.close()
        manifest["assets"].append(entry)
        print("  %-5s /Rot=%-3d +%-3d = %-3d  %-10s %-11s %s%d render(s)"
              % (sheet, orientation["stored_rotate"], orientation["additional"],
                 orientation["absolute"], orientation["signal"],
                 "monochrome" if entry["monochrome"] else "HAS COLOUR",
                 "CONFIRM " if orientation["needs_confirmation"] else "",
                 len(entry["renders"])))

    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default=DEFAULT_SOURCE)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--thumb-dpi", type=int, default=26)
    parser.add_argument("--page-dpi", type=int, default=110)
    args = parser.parse_args()

    if not os.path.isdir(args.source_root):
        sys.exit("Source root not found: %s" % args.source_root)

    print("Rendering from %s" % args.source_root)
    manifest = render(args.source_root, args.out, args.thumb_dpi, args.page_dpi)
    print("\n%d sheet(s) -> %s" % (len(manifest["assets"]), args.out))
    print("Provenance written to %s" % os.path.join(args.out, "manifest.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
