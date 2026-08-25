"""CLAUDE-MOBILE-ICON-01 - render static/app-icon.svg to the PNG sizes phone
home screens actually request.

    ./venv/Scripts/python.exe tools/render_app_icon.py
    ./venv/Scripts/python.exe tools/render_app_icon.py --proof

WHY THIS EXISTS AT ALL

PNG is a requirement, not a convenience. iOS ignores SVG for `apple-touch-icon`
and falls back to a screenshot of the page, which is how an installed app ends
up on a home screen with no icon. So the PNGs have to exist as real committed
binaries - and a committed binary nobody can regenerate is exactly the kind of
asset that silently drifts from its source. This script is what keeps
`static/app-icon.svg` the single source of truth: change the SVG, change the
matching constants here, re-run, and every size follows.

WHY IT REDRAWS RATHER THAN RASTERISES

There is no SVG rasteriser in this project's dependencies, and adding one
(cairosvg, and with it a native cairo build on Windows) fails
`tools/dependency_fit.py` on the "no build step / minimal dependency surface"
constraints for something this small. Pillow is already a declared dependency,
and the mark is six points and a circle - so the geometry is restated here
instead. The cost of that choice is that the two files can disagree; the test
file asserts the SVG's geometry directly, and the constants below are the same
numbers, so a change to one that isn't mirrored in the other shows up as a
visibly wrong PNG rather than silently.

--proof writes a sheet of the true home-screen sizes (48/60/76/120) into the
system temp directory. Judge the icon there first. A mark that looks
considered at 512px and turns to mush at 48px is a failed icon, and the large
render is the one that flatters it.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = REPO_ROOT / "static" / "icons"

# The same numbers as static/app-icon.svg, in its 512 viewBox.
GROUND = "#0b1f28"
MARK = "#e9f4f7"
ACCENT = "#4db3c9"
POINTS = [(178, 158), (256, 268), (150, 388), (362, 388), (256, 268), (372, 128)]
STROKE = 36
CORNER_RADIUS = 112
WAIST = (256, 268)
WAIST_RADIUS = 20

# Platforms crop up to ~20% off every edge of a maskable icon. 10% inset keeps
# the mark whole under the worst common mask without shrinking it so far that it
# looks lost inside its own square.
MASKABLE_INSET = 0.10

# Supersample factor. Pillow has no round line caps and no antialiased drawing,
# so the honest way to get both is to draw large and downscale.
SUPERSAMPLE = 8


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

    points = [place(p) for p in POINTS]
    width = STROKE * scale * shrink
    # joint="curve" gives round JOINS; the two free ends still need round CAPS,
    # which Pillow cannot do, so they are capped by hand below.
    draw.line(points, fill=MARK, width=int(round(width)), joint="curve")
    for end in (points[0], points[-1]):
        radius = width / 2.0
        draw.ellipse(
            [end[0] - radius, end[1] - radius, end[0] + radius, end[1] + radius], fill=MARK
        )

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
        # 180 is apple-touch-icon; 192 and 512 are what the manifest declares and
        # what Android uses for the home screen and the splash screen.
        path = ICON_DIR / f"app-icon-{size}.png"
        render(size).save(path)
        written.append(path)
    path = ICON_DIR / "app-icon-maskable-512.png"
    render(512, inset=MASKABLE_INSET).save(path)
    written.append(path)
    return written


def write_proof_sheet() -> Path:
    """The small sizes, side by side, on a mid-grey that flatters nothing."""
    sizes = (48, 60, 76, 120)
    gap = 32
    sheet = Image.new(
        "RGB", (sum(sizes) + gap * (len(sizes) + 1), 200), "#3a4a52"
    )
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
    parser.add_argument(
        "--proof",
        action="store_true",
        help="also write a small-size proof sheet to the temp directory",
    )
    args = parser.parse_args()

    for path in write_shipped_icons():
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    if args.proof:
        print(f"proof sheet: {write_proof_sheet()}")


if __name__ == "__main__":
    main()
