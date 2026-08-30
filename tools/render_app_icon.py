"""CLAUDE-MOBILE-ICON-01 - generate the ARCHIOSK app icon.

    ./venv/Scripts/python.exe tools/render_app_icon.py
    ./venv/Scripts/python.exe tools/render_app_icon.py --proof

Writes static/app-icon.svg, the PNG sizes phone home screens request, and the
static/icons/app-icon.ico a browser asks for at /favicon.ico - all from the
single geometry definition below. One source, so the vector and the
rasters cannot drift apart - an earlier version of this tool restated the
geometry separately from the SVG and that duplication was a defect waiting to
happen.

WHY PNG IS REQUIRED, NOT A CONVENIENCE

iOS ignores SVG for `apple-touch-icon` and falls back to a screenshot of the
page, which is how an installed app ends up on a home screen with no icon. So
the PNGs must exist as real committed binaries - and a committed binary nobody
can regenerate is exactly the kind of asset that silently drifts from its
source. This script is what keeps that from happening.

WHY THE MARK IS A FILLED OUTLINE AND NOT A STROKED LINE

Product Owner: "Cut the icon's ends with a knife. The left shorter one
horizontally and the right one vertically. And make the edges of the base
angles sharp."

A stroked polyline cannot do that. SVG offers exactly three line caps - butt,
round, square - and every one of them is PERPENDICULAR to the stroke's own
direction. Both free ends here are diagonal, so no cap setting can produce a
horizontal cut on one and a vertical cut on the other; `butt` would give two
diagonal cuts at different angles, which is not what was asked for.

So the centreline is offset into a real closed polygon here, in code, with
MITRE joins (the sharp base angles) and each end terminated against a chosen
line rather than against the stroke's own perpendicular. That makes the two
knife cuts a property of the geometry instead of something the renderer decides.

--proof writes a sheet at true home-screen sizes (48/60/76/120) to the system
temp directory. Judge the icon there first: a mark that looks considered at
512px and turns to mush at 48px is a failed icon, and the large render is the
one that flatters it.
"""
from __future__ import annotations

import argparse
import math
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = REPO_ROOT / "static" / "icons"
SVG_PATH = REPO_ROOT / "static" / "app-icon.svg"
ICO_PATH = ICON_DIR / "app-icon.ico"

GROUND = "#0b1f28"
MARK = "#e9f4f7"
ACCENT = "#4db3c9"

# The centreline, in a 512 box. Product Owner geometry: an X whose BOTTOM IS
# CLOSED and whose UPPER-LEFT ARM IS SHORTER. Read as one continuous walk:
#   short upper-left arm -> waist -> bottom-left foot -> CLOSING BASE ->
#   bottom-right foot -> back through the waist -> long upper-right arm.
CENTRELINE = [
    (178.0, 158.0),   # upper-left end   - cut HORIZONTALLY
    (256.0, 268.0),   # waist
    (150.0, 388.0),   # bottom-left foot - sharp
    (362.0, 388.0),   # bottom-right foot- sharp
    (256.0, 268.0),   # waist again
    (372.0, 128.0),   # upper-right end  - cut VERTICALLY
]
WIDTH = 36.0
CORNER_RADIUS = 112
WAIST = (256.0, 268.0)
WAIST_RADIUS = 20.0

# The knife cuts. The left arm ends against a horizontal line, the right arm
# against a vertical one - so the two terminations disagree with each other on
# purpose, which is what stops the form reading as a symmetrical X.
LEFT_CUT_Y = 158.0
RIGHT_CUT_X = 372.0

MASKABLE_INSET = 0.10
# The frames a .ico carries. 16 is the browser tab, 32 the Windows taskbar and
# bookmark bar, 48 the desktop shortcut; 64 covers a HiDPI tab strip.
ICO_SIZES = (16, 32, 48, 64)
SUPERSAMPLE = 8


def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def _normal(direction):
    return -direction[1], direction[0]


def outline(points=CENTRELINE, width=WIDTH):
    """Offset the centreline into a closed polygon with mitre joins.

    Returns the polygon in order. It self-intersects at the waist, because the
    centreline passes through that point twice - which is fine and intended:
    filled with the nonzero rule the overlap renders solid, and the alternative
    (splitting the mark into separate shapes) would put a visible seam through
    the middle of the form.
    """
    half = width / 2.0
    directions = [_unit(points[i], points[i + 1]) for i in range(len(points) - 1)]
    normals = [_normal(d) for d in directions]

    def side(sign):
        result = []
        # Start cap: terminate against the horizontal cut line rather than
        # against the segment's own perpendicular.
        start = (
            points[0][0] + sign * half * normals[0][0],
            points[0][1] + sign * half * normals[0][1],
        )
        t = (LEFT_CUT_Y - start[1]) / directions[0][1]
        result.append((start[0] + t * directions[0][0], LEFT_CUT_Y))

        for j in range(1, len(points) - 1):
            n1, n2 = normals[j - 1], normals[j]
            # Standard mitre: where the two offset lines actually meet. At a
            # sharp vertex this runs a long way past the corner, which is
            # precisely the requested "sharp edge" at the feet.
            denominator = 1.0 + (n1[0] * n2[0] + n1[1] * n2[1])
            scale = half / denominator
            result.append((
                points[j][0] + sign * scale * (n1[0] + n2[0]),
                points[j][1] + sign * scale * (n1[1] + n2[1]),
            ))

        end = (
            points[-1][0] + sign * half * normals[-1][0],
            points[-1][1] + sign * half * normals[-1][1],
        )
        t = (RIGHT_CUT_X - end[0]) / directions[-1][0]
        result.append((RIGHT_CUT_X, end[1] + t * directions[-1][1]))
        return result

    left = side(1.0)
    right = side(-1.0)
    return left + list(reversed(right))


def svg_path_data(polygon=None):
    polygon = polygon or outline()
    parts = ["M %.1f %.1f" % polygon[0]]
    parts += ["L %.1f %.1f" % point for point in polygon[1:]]
    parts.append("Z")
    return " ".join(parts)


SVG_TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="ARCHIOSK">
    <!-- CLAUDE-MOBILE-ICON-01 - the home-screen app icon.
         EXPERIMENTAL until Product Owner visual acceptance.

         GENERATED by tools/render_app_icon.py from the centreline in that file.
         Do not hand-edit the path below: change the geometry there and re-run,
         or the SVG and the PNG home-screen icons will disagree.

         PRODUCT OWNER DIRECTION, carried forward:
           - based on an X; THE BOTTOM PORTION IS CLOSED; the upper-left portion
             is SHORTER; intentional, dynamic, recognisable; legible small;
             architectural/technical, not decorative;
           - "Cut the icon's ends with a knife. The left shorter one
             horizontally and the right one vertically. And make the edges of
             the base angles sharp."

         Closing the bottom turns four open arms into a base the form stands on,
         which is also why it survives being shrunk - a closed area holds its
         shape at 48px where four thin open arms do not. The asymmetry is the
         identity: the upper-left arm is about two-thirds the reach of the
         upper-right.

         The knife cuts are why this is a FILLED OUTLINE rather than a stroked
         line: SVG's three line caps are all perpendicular to the stroke, and
         both free ends here are diagonal, so no cap setting can give one a
         horizontal termination and the other a vertical one. The mitred feet
         are sharp for the same reason - the corner is real geometry now, not a
         renderer setting.

         Reconciled with existing branding rather than invented: the waist point
         and the two-arms-from-a-centre construction both come from
         templates/_macros.html's archiosk_mark. -->
    <rect width="512" height="512" rx="112" fill="%(ground)s"/>
    <path d="%(path)s" fill="%(mark)s" fill-rule="nonzero"/>
    <!-- The waist, carried over from the wordmark mark. It is what stops the
         form reading as a plain arrowhead, and it is the one place the accent
         appears - colour is used once, and means "this is the centre". -->
    <circle cx="%(cx)s" cy="%(cy)s" r="%(r)s" fill="%(accent)s"/>
</svg>
'''


def write_svg() -> Path:
    SVG_PATH.write_text(
        SVG_TEMPLATE % {
            "ground": GROUND,
            "mark": MARK,
            "accent": ACCENT,
            "path": svg_path_data(),
            "cx": "%g" % WAIST[0],
            "cy": "%g" % WAIST[1],
            "r": "%g" % WAIST_RADIUS,
        },
        encoding="utf-8",
    )
    return SVG_PATH


def render(size: int, inset: float = 0.0, ground: bool = True) -> Image.Image:
    canvas = size * SUPERSAMPLE
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scale = canvas / 512.0

    if ground:
        draw.rounded_rectangle(
            [0, 0, canvas - 1, canvas - 1], radius=CORNER_RADIUS * scale, fill=GROUND
        )

    shrink = 1.0 - 2 * inset

    def place(point):
        x, y = point
        return ((x - 256) * shrink + 256) * scale, ((y - 256) * shrink + 256) * scale

    # The same polygon the SVG carries - drawn filled, so the knife cuts and the
    # sharp feet survive rasterisation exactly as the vector has them.
    draw.polygon([place(p) for p in outline()], fill=MARK)

    waist_x, waist_y = place(WAIST)
    waist_r = WAIST_RADIUS * scale * shrink
    draw.ellipse(
        [waist_x - waist_r, waist_y - waist_r, waist_x + waist_r, waist_y + waist_r],
        fill=ACCENT,
    )

    return image.resize((size, size), Image.LANCZOS)


def write_shipped_icons() -> list[Path]:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for size in (180, 192, 512):
        # 180 is apple-touch-icon; 192 and 512 are what the manifest declares.
        path = ICON_DIR / f"app-icon-{size}.png"
        render(size).save(path)
        written.append(path)
    # Platforms crop up to ~20% off every edge of a maskable icon.
    path = ICON_DIR / "app-icon-maskable-512.png"
    render(512, inset=MASKABLE_INSET).save(path)
    written.append(path)
    # CLAUDE-IDENTITY-ICON-RESOLVE-01 - the .ico, for the same reason the PNGs
    # exist: a format the client insists on, not a legacy courtesy. A browser
    # requests /favicon.ico at the site ROOT on its own initiative, regardless
    # of what <link rel="icon"> declares, and nothing in this repository was
    # answering that path. It is generated HERE, from the same render() as
    # every other size, so the tab icon cannot drift from the home-screen one
    # - the same discipline that made the PNGs generated rather than committed
    # by hand. Each embedded size is rendered at its own size rather than
    # downsampled from one large frame: the 16px frame is the one a tab strip
    # actually shows, and it is the one a double resize damages most.
    # Largest first: Pillow's ICO writer silently DROPS any requested size
    # larger than the base image it is called on, so a 16px base would have
    # written a one-frame .ico while reporting success.
    frames = [render(size) for size in sorted(ICO_SIZES, reverse=True)]
    frames[0].save(
        ICO_PATH,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=frames[1:],
    )
    written.append(ICO_PATH)
    return written


def write_proof_sheet() -> Path:
    """The small sizes, side by side, on a mid-grey that flatters nothing."""
    sizes = (48, 60, 76, 120)
    gap = 32
    sheet = Image.new("RGB", (sum(sizes) + gap * (len(sizes) + 1), 200), "#3a4a52")
    x = gap
    for size in sizes:
        icon = render(size)
        sheet.paste(icon, (x, (200 - size) // 2), icon)
        x += size + gap
    out = Path(tempfile.gettempdir()) / "archiosk-app-icon-proof.png"
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof", action="store_true",
                        help="also write a small-size proof sheet to the temp directory")
    args = parser.parse_args()

    polygon = outline()
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    print("mark bounds: x %.1f..%.1f  y %.1f..%.1f" % (min(xs), max(xs), min(ys), max(ys)))

    print(f"wrote {write_svg().relative_to(REPO_ROOT)}")
    for path in write_shipped_icons():
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    if args.proof:
        print(f"proof sheet: {write_proof_sheet()}")


if __name__ == "__main__":
    main()
