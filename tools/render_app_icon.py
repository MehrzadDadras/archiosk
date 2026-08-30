"""CLAUDE-MOBILE-ICON-01 - generate the ARCHIOSK app icon.
CLAUDE-LETTERMARK-PURGE-01 - the geometry below is now a lettermark.

    ./venv/Scripts/python.exe tools/render_app_icon.py
    ./venv/Scripts/python.exe tools/render_app_icon.py --proof

Writes static/app-icon.svg, the PNG sizes phone home screens request, and the
static/icons/app-icon.ico a browser asks for at /favicon.ico - all from the
single geometry definition below. One source, so the vector and the rasters
cannot drift apart - an earlier version of this tool restated the geometry
separately from the SVG and that duplication was a defect waiting to happen.

WHAT CHANGED, AND WHY

This tool used to draw an X with a closed bottom and a waist - a constructed
symbol, reconciled with templates/_macros.html's archiosk_mark. Product Owner
direction, 2026-08-30, retired both: the constructed mark read as an hourglass
in the tab and as a bowtie in the menu bar and on the sign-in card, and the
acceptance bar the earlier mark was held to ("must not collapse into an
ambiguous X") turned out not to hold at the sizes it actually shipped at - 16px
in a tab strip, 16px beside the app menu.

So there is no constructed symbol in the product any more. The UI surfaces
carry the "Archiosk" wordmark alone, and this file draws the one place a
graphic is unavoidable: a tab, a bookmark and a home screen must show
something. That something is now a letter.

WHY A LETTER, DRAWN, RATHER THAN TYPE

A lettermark cut as geometry rather than set in a font is not decoration - it
is what keeps the icon legible at 16px, where a text glyph's own hinting and
side bearings are outside our control and where the display face's thin strokes
disappear. The strokes here are 50 units in a 512 box, so the thinnest thing in
the mark is about 1.6px at 16px: still a real mark rather than a grey smudge.

The apex is CUT FLAT rather than pointed, and the feet are cut flat too. A
sharp apex is the first thing to vanish under a LANCZOS downsample; a flat one
holds its width all the way down. The counter - the triangular hole above the
crossbar - is what makes it read as A rather than as a tent, and it is sized so
it survives the smallest frame the .ico carries.

WHY PNG IS REQUIRED, NOT A CONVENIENCE

iOS ignores SVG for `apple-touch-icon` and falls back to a screenshot of the
page, which is how an installed app ends up on a home screen with no icon. So
the PNGs must exist as real committed binaries - and a committed binary nobody
can regenerate is exactly the kind of asset that silently drifts from its
source. This script is what keeps that from happening.

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

# The lettermark, in a 512 box. An "A": two legs from a flat apex, one
# crossbar, one triangular counter.
#
# Symmetric on purpose. The retired mark's identity was its asymmetry, and
# asymmetry is exactly what stopped it reading as the letter it was next to.
# A lettermark has no such licence: an A that leans is a worse A.
APEX = (256.0, 128.0)
FOOT_Y = 396.0
LEFT_FOOT = (160.0, FOOT_Y)
RIGHT_FOOT = (352.0, FOOT_Y)   # 160 + 352 = 512, so the form is centred
STROKE = 50.0

# The crossbar sits low. Placed at the optical centre rather than the
# geometric one - a crossbar on the true midline reads as too high, because
# the counter above it is narrower than the space below it.
BAR_Y = 308.0
BAR_HALF = 22.0

CORNER_RADIUS = 112
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


def _leg(apex, foot, width=STROKE):
    """One diagonal, offset into a closed quad with both ends cut FLAT.

    The cut is the point. Offsetting a centreline and letting the ends
    terminate perpendicular to the stroke would leave the apex and the feet
    sloping, which at 16px reads as a blurred edge rather than a deliberate
    one. Each end is instead carried along its own direction until it meets a
    horizontal line - so the apex is level and the feet sit flat on a shared
    baseline, both as real geometry rather than a renderer setting.
    """
    direction = _unit(apex, foot)
    normal = _normal(direction)
    half = width / 2.0

    def cut(point, sign, target_y):
        x = point[0] + sign * half * normal[0]
        y = point[1] + sign * half * normal[1]
        t = (target_y - y) / direction[1]
        return (x + t * direction[0], target_y)

    return [
        cut(apex, 1.0, apex[1]),
        cut(apex, -1.0, apex[1]),
        cut(foot, -1.0, foot[1]),
        cut(foot, 1.0, foot[1]),
    ]


def _crossbar():
    """The bar, spanning between the two legs at BAR_Y.

    Its ends are pushed past each leg's centreline by half a stroke so the
    three shapes overlap rather than abut. An abutment leaves a hairline seam
    at some rasterisation sizes and not others; an overlap filled nonzero
    never does.
    """
    def leg_x_at(foot):
        t = (BAR_Y - APEX[1]) / (foot[1] - APEX[1])
        return APEX[0] + t * (foot[0] - APEX[0])

    left = leg_x_at(LEFT_FOOT) - STROKE / 2.0
    right = leg_x_at(RIGHT_FOOT) + STROKE / 2.0
    return [
        (left, BAR_Y - BAR_HALF),
        (right, BAR_Y - BAR_HALF),
        (right, BAR_Y + BAR_HALF),
        (left, BAR_Y + BAR_HALF),
    ]


def polygons():
    """The three closed shapes the mark is made of, in draw order.

    Three separate polygons rather than one merged outline: filled with the
    nonzero rule they render as a single solid form, and keeping them separate
    means the counter above the crossbar is simply the space they do not
    cover - never a subtracted hole that a fill-rule change could accidentally
    flood.
    """
    return [
        _leg(APEX, LEFT_FOOT),
        _leg(APEX, RIGHT_FOOT),
        _crossbar(),
    ]


def svg_path_data(shapes=None):
    shapes = shapes or polygons()
    subpaths = []
    for shape in shapes:
        parts = ["M %.1f %.1f" % shape[0]]
        parts += ["L %.1f %.1f" % point for point in shape[1:]]
        parts.append("Z")
        subpaths.append(" ".join(parts))
    return " ".join(subpaths)


SVG_TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Archiosk">
    <!-- CLAUDE-LETTERMARK-PURGE-01 - the app icon.

         GENERATED by tools/render_app_icon.py from the geometry in that file.
         Do not hand-edit the path below: change the geometry there and re-run,
         or the SVG and the PNG home-screen icons will disagree.

         PRODUCT OWNER DIRECTION, 2026-08-30: the constructed mark is retired.
         It read as an hourglass in the browser tab and as a bowtie on the
         sign-in card and in the app menu. The UI surfaces now carry the
         "Archiosk" wordmark with no symbol beside it; this file draws the one
         place a graphic cannot be omitted, because a tab, a bookmark and a
         home screen must all show something.

         What replaced it is a letter, cut as geometry rather than set in a
         font - a text glyph's hinting and side bearings are outside our
         control at 16px, which is the size that actually matters here. Flat
         apex and flat feet for the same reason: a sharp apex is the first
         thing a downsample destroys.

         Deliberately symmetric. The retired mark's identity was its asymmetry,
         and that asymmetry is what stopped it reading as a letter. -->
    <rect width="512" height="512" rx="112" fill="%(ground)s"/>
    <path d="%(path)s" fill="%(mark)s" fill-rule="nonzero"/>
</svg>
'''


def write_svg() -> Path:
    SVG_PATH.write_text(
        SVG_TEMPLATE % {
            "ground": GROUND,
            "mark": MARK,
            "path": svg_path_data(),
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

    # The same three polygons the SVG carries - drawn filled, so the flat apex
    # and flat feet survive rasterisation exactly as the vector has them.
    for shape in polygons():
        draw.polygon([place(p) for p in shape], fill=MARK)

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

    points = [p for shape in polygons() for p in shape]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    print("mark bounds: x %.1f..%.1f  y %.1f..%.1f" % (min(xs), max(xs), min(ys), max(ys)))

    print(f"wrote {write_svg().relative_to(REPO_ROOT)}")
    for path in write_shipped_icons():
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    if args.proof:
        print(f"proof sheet: {write_proof_sheet()}")


if __name__ == "__main__":
    main()
