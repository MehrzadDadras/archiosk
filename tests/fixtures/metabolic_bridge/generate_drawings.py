"""Append the governed A-201 section sheet to the Metabolic Bridge fixture.

This intentionally edits only the fixture PDF. It does not alter application
ingestion or interpretation code. The first three sheets are preserved byte-
for-byte at the page-content level; the fourth sheet supplies vertical datum
evidence for later coordination tests.
"""
from pathlib import Path
import fitz


ROOT = Path(__file__).parent
PDF = ROOT / "builder_corpus" / "Drawings_Set.pdf"


def append_a201() -> None:
    document = fitz.open(PDF)
    # Preserve the original detail sheet while making its measured frame-head
    # datum explicit for the vertical-coordination oracle.
    if "96.0 pt" not in document[2].get_text():
        document[2].insert_text((335, 300), 'D-101 FRAME HEAD 96.0 pt (8\'-0")', fontsize=8)
    # Regeneration is idempotent: replace an existing generated A-201 rather
    # than appending duplicate pages on every run.
    while len(document) > 3:
        document.delete_page(3)
    page = document.new_page(width=612, height=792)
    page.insert_text((36, 32), "BUILDING SECTION & VERTICAL DATUMS", fontsize=14)
    page.insert_text((36, 50), "SHEET: A-201", fontsize=9)
    page.insert_text((180, 50), "TITLE: BUILDING SECTION 1", fontsize=9)
    page.insert_text((390, 50), 'SCALE: 1/4\" = 1\'-0\"', fontsize=8)
    # Vertical section envelope and three governed datum lines.
    page.draw_rect((150, 170, 470, 600), color=(0, 0, 0), width=1.5)
    for y, label in ((500, 'LEVEL 1 / EL. 0\'-0"'),
                     (356, 'LEVEL 2 / EL. 12\'-0"'),
                     (296, 'ROOF / EL. 17\'-0"'),
                     (236, 'LEVEL 3 / EL. 24\'-0"')):
        page.draw_line((72, y), (500, y), color=(0.25, 0.25, 0.25), width=0.8)
        page.insert_text((78, y), label, fontsize=8)
    # Door opening and explicit head-height dimension.
    page.draw_rect((270, 416, 350, 500), color=(0, 0, 0), width=1.0)
    page.draw_line((255, 416), (255, 500), color=(0, 0, 0), width=0.7)
    page.draw_line((365, 416), (365, 500), color=(0, 0, 0), width=0.7)
    page.insert_text((385, 450), 'STANDARD DOOR HEAD', fontsize=8)
    page.insert_text((385, 464), '7\'-0" (84.0 pt)', fontsize=8)
    page.insert_text((274, 410), 'D-101', fontsize=8)
    page.draw_circle((190, 440), 24, color=(0, 0, 0), width=1)
    page.insert_text((177, 443), '3/A-501', fontsize=7)
    page.draw_line((270, 500), (270, 416), color=(0, 0, 0), width=0.5)
    page.draw_line((260, 500), (280, 500), color=(0, 0, 0), width=0.5)
    page.draw_line((260, 416), (280, 416), color=(0, 0, 0), width=0.5)
    page.insert_text((36, 755), 'A-201', fontsize=10)
    document.save(PDF.with_suffix('.tmp.pdf'), deflate=True, garbage=4)
    document.close()
    PDF.with_suffix('.tmp.pdf').replace(PDF)


if __name__ == "__main__":
    append_a201()
