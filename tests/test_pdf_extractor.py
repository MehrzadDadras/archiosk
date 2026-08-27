import pymupdf

from engine.pdf_extractor import PDFVectorExtractor


def _pdf(tmp_path):
    path = tmp_path / "drawing.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.draw_line((20, 20), (180, 20), width=2, dashes=(3, 2))
    page.draw_rect((30, 40, 100, 90), width=1)
    page.draw_bezier((120, 100), (150, 20), (220, 180), (280, 100), width=1.5)
    page.insert_text((40, 140), "HORIZONTAL", fontsize=12, color=(1, 0, 0))
    page.insert_text((200, 160), "ROTATED", fontsize=12, rotate=90)
    page.insert_text((280, 220), "ANGLED", fontsize=12, morph=(pymupdf.Point(280, 220), pymupdf.Matrix(45)))
    doc.save(path)
    doc.close()
    return path


def test_extracts_geometry_text_and_boxes(tmp_path):
    result = PDFVectorExtractor().extract_document(str(_pdf(tmp_path)))
    page = result["pages"][0]
    kinds = {item["geometry_type"] for item in page["vectors"]}
    assert {"line", "rect", "bezier"} <= kinds
    bezier = next(item for item in page["vectors"] if item["geometry_type"] == "bezier")
    assert len(bezier["control_points"]) == 4
    assert page["mediabox"]["x1"] == 400.0
    assert page["cropbox"]["y1"] == 300.0
    horizontal = next(item for item in page["text"] if item["content"] == "HORIZONTAL")
    assert horizontal["origin"] == "native_span"
    assert horizontal["bbox_points"]["x1"] > horizontal["bbox_points"]["x0"]
    assert horizontal["color"] == "#ff0000"


def test_text_rotation_is_reported(tmp_path):
    texts = PDFVectorExtractor().extract_document(str(_pdf(tmp_path)))["pages"][0]["text"]
    rotated = next(item for item in texts if item["content"] == "ROTATED")
    assert abs(abs(rotated["rotation_degrees"]) - 90) < 1
    angled = next(item for item in texts if item["content"] == "ANGLED")
    assert abs(abs(angled["rotation_degrees"]) - 45) < 1


def test_dashes_remain_structured(tmp_path):
    vectors = PDFVectorExtractor().extract_document(str(_pdf(tmp_path)))["pages"][0]["vectors"]
    line = next(item for item in vectors if item["geometry_type"] == "line")
    assert line["dash"] is not None
    assert line["stroke_width_points"] == 2.0
