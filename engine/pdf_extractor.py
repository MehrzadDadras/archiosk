"""Headless extraction of PDF vector and native text primitives."""
from __future__ import annotations

import math
import hashlib
from pathlib import Path
from typing import Iterator

try:
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None


def _point(point) -> list[float]:
    return [float(point.x), float(point.y)]


def _color(value):
    if value is None:
        return None
    if isinstance(value, int):
        return f"#{value:06x}"
    if isinstance(value, (tuple, list)):
        channels = [max(0, min(255, round(float(channel) * 255))) for channel in value[:3]]
        return "#%02x%02x%02x" % tuple(channels) if len(channels) == 3 else None
    return value


def _rect(rect) -> dict[str, float]:
    return {"x0": float(rect.x0), "y0": float(rect.y0), "x1": float(rect.x1), "y1": float(rect.y1)}


class PDFVectorExtractor:
    """Extract page-local geometry and native text without rendering a GUI."""

    schema_version = "pdf_geometry_semantics_v1"

    def stream_pages(self, pdf_path: str) -> Iterator[dict]:
        if pymupdf is None:
            raise RuntimeError("PyMuPDF is required for PDF extraction")
        path = Path(pdf_path)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        with pymupdf.open(path) as document:
            source = {"filename": path.name, "sha256": digest.hexdigest(), "page_count": len(document)}
            for index, page in enumerate(document):
                yield self._extract_page(page, index + 1, source)

    def extract_document(self, pdf_path: str) -> dict:
        path = Path(pdf_path)
        pages = list(self.stream_pages(pdf_path))
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return {
            "schema_version": self.schema_version,
            "source": {"filename": path.name, "sha256": digest.hexdigest(), "page_count": len(pages)},
            "pages": pages,
        }

    def _extract_page(self, page, page_number: int, source: dict) -> dict:
        mediabox = page.mediabox
        cropbox = page.cropbox
        vectors = []
        for path_index, drawing in enumerate(page.get_drawings()):
            stroke_width = drawing.get("width")
            common = {
                "stroke_width_points": float(stroke_width) if stroke_width is not None else None,
                "stroke_color": _color(drawing.get("color")),
                "fill_color": _color(drawing.get("fill")),
                "dash": drawing.get("dashes") or drawing.get("dash"),
                "closed": bool(drawing.get("closePath", False)),
                "source_path_index": path_index,
            }
            for item_index, item in enumerate(drawing.get("items", ())):
                kind = item[0]
                record = {"id": f"p{page_number:02d}-v{len(vectors):06d}", **common}
                if kind == "l":
                    record.update(geometry_type="line", points=[_point(item[1]), _point(item[2])])
                elif kind == "re":
                    record.update(geometry_type="rect", bbox_points=_rect(item[1]), points=[
                        [float(item[1].x0), float(item[1].y0)], [float(item[1].x1), float(item[1].y0)],
                        [float(item[1].x1), float(item[1].y1)], [float(item[1].x0), float(item[1].y1)],
                    ])
                elif kind == "c":
                    record.update(geometry_type="bezier", control_points=[_point(p) for p in item[1:5]])
                elif kind == "qu":
                    record.update(geometry_type="quad", points=[_point(p) for p in item[1:]])
                else:
                    record.update(geometry_type=str(kind), points=[_point(p) for p in item[1:] if hasattr(p, "x")])
                vectors.append(record)

        texts = []
        blocks = page.get_text("dict").get("blocks", [])
        for block_index, block in enumerate(blocks):
            for line_index, line in enumerate(block.get("lines", [])):
                direction = line.get("dir", (1.0, 0.0))
                rotation = math.degrees(math.atan2(float(direction[1]), float(direction[0])))
                for span_index, span in enumerate(line.get("spans", [])):
                    bbox = span.get("bbox")
                    if not bbox:
                        continue
                    x0, y0, x1, y1 = map(float, bbox)
                    texts.append({
                        "id": f"p{page_number:02d}-t{len(texts):06d}",
                        "content": span.get("text", ""),
                        "bbox_points": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                        "centroid_points": {"x": (x0 + x1) / 2, "y": (y0 + y1) / 2},
                        "font_size_points": float(span.get("size", 0)),
                        "rotation_degrees": rotation,
                        "font_name": span.get("font"),
                        "color": _color(span.get("color")),
                        "origin": "native_span",
                        "block_index": block_index,
                        "line_index": line_index,
                        "span_index": span_index,
                    })
        return {
            "page_number": page_number,
            "width_points": float(page.rect.width),
            "height_points": float(page.rect.height),
            "mediabox": {"x0": float(mediabox.x0), "y0": float(mediabox.y0), "x1": float(mediabox.x1), "y1": float(mediabox.y1)},
            "cropbox": {"x0": float(cropbox.x0), "y0": float(cropbox.y0), "x1": float(cropbox.x1), "y1": float(cropbox.y1)},
            "coordinate_system": "top_left_origin_y_down",
            "vectors": vectors,
            "text": texts,
        }
