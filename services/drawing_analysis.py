"""CLAUDE-ANALYZE-BOUNDARY-01 - THIS MODULE IS A PROTOTYPE. IT DOES NOT SEE.

Everything exported here generates ILLUSTRATIVE output. It must never be
presented, stored or relied upon as production perception. `analysis_capability()`
is the boundary a caller is required to consult before using any of it, and
`services/conversation_interpreter.py` is the one caller that does.

WHAT MOVED OUT, AND WHY IT MATTERS. `compare_region` used to live here and is
REAL production logic - it decides revision-awareness on a live path. It now
lives in `services/region_comparison.py`, so that disabling the prototype can
never disable a real capability by accident. The dependency runs one way only:
this module imports the real geometry helper, never the reverse.

Mock/heuristic drawing-analysis engine for the Case Workspace prototype.

Honesty note: this is NOT a trained vision model. It does not "see" the
drawing's content. It picks from a small set of illustrative, plausible
finding statements (deterministic, keyword-nudged by the reviewer's stated
objective) and treats fixed normalized regions of the source image as the
"evidence" for each one. What IS real: the image being analyzed, the crop
coordinates, and the cropped Artifact file this module generates via
Pillow -- so every Artifact this produces is traceable back to actual
pixels in the actual Source image, even though the Finding text that
motivated the crop is a canned example rather than a genuine visual
inference. See Prompt 4 #4: "Use realistic placeholder/mock analysis if a
live model connection would complicate this first interaction prototype."

This mirrors services/bhive_parser.py's existing shape (an `engine_name`/
`engine_version` identity, a deterministic fallback path, never a hard
failure) rather than inventing an unrelated pattern.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from services.region_comparison import region_to_pixel_box

#: What kind of engine this is. Recorded beside ENGINE_NAME so the class of
#: the engine is machine-readable and not merely implied by a product name.
ENGINE_CLASS = "PROTOTYPE"

#: The capability a caller may find here. There is deliberately no third
#: value: no real drawing-analysis engine serves the Analyze intent today, and
#: inventing a registry for one that does not exist would be scaffolding, not
#: integration. When a real engine arrives, it is named here and the caller's
#: existing branch order picks it up.
CAPABILITY_PROTOTYPE = "PROTOTYPE"
CAPABILITY_UNAVAILABLE = "UNAVAILABLE"

#: Set to 0/false/no/off to withdraw the prototype entirely. DEFAULT ON,
#: because switching it off by default would silently delete a working
#: user-facing path - which this tranche is explicitly forbidden to do. What
#: changes here is that the path is now unmistakably labelled, not that it
#: disappears.
PROTOTYPE_ENABLED_ENV = "ARCHIOSK_PROTOTYPE_DRAWING_ANALYSIS"

ENGINE_NAME = "beehive-mock-vision"
ENGINE_VERSION = "0.1.0-prototype"

# (statement, base_confidence, (x, y, width, height) normalized 0-1,
#  objective keywords that should surface this finding first)
def analysis_capability() -> str:
    """What kind of drawing analysis can actually serve a request right now.

    Returns CAPABILITY_PROTOTYPE or CAPABILITY_UNAVAILABLE - never a value
    implying real perception, because this module has none. A caller that does
    not consult this is free to call the generators directly; what it may not
    do is present the result as a reading of the drawing.
    """
    import os

    raw = os.environ.get(PROTOTYPE_ENABLED_ENV)
    if raw is not None and raw.strip().lower() in ("0", "false", "no", "off"):
        return CAPABILITY_UNAVAILABLE
    return CAPABILITY_PROTOTYPE


_MOCK_FINDING_LIBRARY = [
    (
        "Elevation callout in this region may reference a datum inconsistent "
        "with the project benchmark stated on the cover sheet.",
        0.62,
        (0.06, 0.70, 0.32, 0.18),
        ("datum", "elevation", "benchmark", "survey"),
    ),
    (
        "Dimension string in this region does not appear to close against "
        "the adjacent grid line.",
        0.55,
        (0.42, 0.12, 0.26, 0.20),
        ("dimension", "grid", "structural", "framing"),
    ),
    (
        "Legend symbol in this region could not be matched against the "
        "drawing's published legend.",
        0.48,
        (0.64, 0.55, 0.24, 0.26),
        ("legend", "symbol", "unclear", "unresolved"),
    ),
    (
        "Note callout in this region references a detail that does not "
        "appear elsewhere on this sheet.",
        0.51,
        (0.10, 0.30, 0.28, 0.18),
        ("detail", "note", "reference", "missing"),
    ),
]


class DrawingAnalysisError(Exception):
    """Raised when the source image can't be opened or cropped."""


def analyze_drawing(
    image_path: Path,
    objective: str,
    artifacts_dir: Path,
    max_findings: int = 3,
    prior_corrections: Optional[list[str]] = None,
) -> list[dict]:
    """
    Returns a list of dicts shaped for
    CaseWorkspaceStore.record_analysis(findings=...): each has
    statement, machine_confidence, crop, image_path, page, source_id
    (source_id is filled in by the caller, which has that context).

    `prior_corrections` (Prompt 4 #3/#7): correction notes a reviewer has
    already recorded on Findings in this Case. Any mock finding whose
    topic keywords match a prior correction is excluded from this run -
    a concrete, visible way a reviewer correction changes subsequent
    analysis rather than the system repeating a mistake it was already
    told about.
    """
    try:
        with Image.open(image_path) as source_image:
            width, height = source_image.size

            objective_lower = objective.lower()
            corrections_lower = " ".join(prior_corrections or []).lower()

            candidates = [
                entry for entry in _MOCK_FINDING_LIBRARY
                if not any(kw in corrections_lower for kw in entry[3])
            ] or list(_MOCK_FINDING_LIBRARY)

            ranked = sorted(
                candidates,
                key=lambda entry: any(kw in objective_lower for kw in entry[3]),
                reverse=True,
            )

            results = []
            for statement, confidence, region, _keywords in ranked[:max_findings]:
                crop_box, normalized = region_to_pixel_box(region, width, height)
                cropped = source_image.convert("RGB").crop(crop_box)
                cropped = _annotate_crop(cropped)

                artifact_filename = f"{uuid.uuid4()}.png"
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                cropped.save(artifacts_dir / artifact_filename, format="PNG")

                results.append(
                    {
                        "statement": statement,
                        "machine_confidence": confidence,
                        "crop": normalized,
                        "image_path": artifact_filename,
                        "page": 1,
                    }
                )

            return results
    except OSError as exc:
        raise DrawingAnalysisError(f"Could not open the source image: {exc}") from exc


def _annotate_crop(cropped: Image.Image) -> Image.Image:
    """Thin forensic-style border so a crop is visually identifiable as a
    generated Artifact, not mistaken for an unmodified source excerpt."""
    bordered = Image.new(
        "RGB",
        (cropped.width + 4, cropped.height + 4),
        (79, 169, 162),  # matches --teal
    )
    bordered.paste(cropped, (2, 2))
    return bordered


def make_comparison_artifact(
    label_a: str,
    label_b: str,
    note: str,
    artifacts_dir: Path,
    size: tuple[int, int] = (480, 220),
) -> str:
    """
    Mock comparison Artifact: a generated image summarizing a
    reviewer-requested comparison ("Compare this fragment with the
    structural drawing"). Clearly a generated summary card, not a claim
    of pixel-level comparison analysis.
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, (18, 32, 51))  # matches --panel-raised
    draw = ImageDraw.Draw(image)

    font = ImageFont.load_default()
    draw.rectangle([0, 0, size[0] - 1, size[1] - 1], outline=(232, 163, 61), width=2)
    draw.text((16, 16), f"Comparison: {label_a}  vs.  {label_b}", fill=(242, 237, 227), font=font)
    draw.text((16, 44), "(mock comparison - illustrative, not pixel-level analysis)", fill=(143, 168, 189), font=font)

    _wrap_text(draw, note, (16, 76), size[0] - 32, fill=(242, 237, 227), font=font)

    filename = f"{uuid.uuid4()}.png"
    image.save(artifacts_dir / filename, format="PNG")
    return filename


def _wrap_text(draw, text: str, position: tuple[int, int], max_width: int, fill, font) -> None:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) > max_width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)

    x, y = position
    for line in lines:
        draw.text((x, y), line, fill=fill, font=font)
        y += 16
