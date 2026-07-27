"""
Diffs two captures of tools/static_preview/build_preview.py's raw HTML
output (see build_preview.py's own docstring) to prove a template/CSS
change is behavior-preserving, not just visually similar.

Normalizes away noise that legitimately differs between two runs of the
same fixture (timestamps, generated UUIDs, whitespace/indentation) so
the only differences reported are real content/markup differences.

Usage:
    # before making a change:
    python tools/static_preview/build_preview.py
    cp -r tools/static_preview/build/_raw /path/to/snapshot

    # after making the change:
    python tools/static_preview/build_preview.py
    python tools/static_preview/diff_snapshot.py /path/to/snapshot

Exits non-zero if any page differs, so it can gate a refactor ("don't
call this done until every page prints IDENTICAL").
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAW_DIR = Path(__file__).parent / "build" / "_raw"

TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T[\d:.+]+")
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def normalize(text: str, extra_replacements: list[tuple[str, str]] = ()) -> str:
    text = TIMESTAMP_RE.sub("TIMESTAMP", text)
    text = UUID_RE.sub("UUID", text)
    for old, new in extra_replacements:
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def diff_one(before_path: Path, after_path: Path, extra_replacements) -> bool:
    """Returns True if identical after normalization."""
    a = normalize(before_path.read_text(encoding="utf-8"), extra_replacements)
    b = normalize(after_path.read_text(encoding="utf-8"), extra_replacements)
    if a == b:
        print(f"{after_path.name}: IDENTICAL")
        return True

    print(f"{after_path.name}: DIFFERS")
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            print(f"  first diff at char {i} (before len={len(a)}, after len={len(b)})")
            print(f"  BEFORE: ...{a[max(0, i - 90):i + 150]}...")
            print(f"  AFTER : ...{b[max(0, i - 90):i + 150]}...")
            break
    else:
        print(f"  one is a prefix of the other (before len={len(a)}, after len={len(b)})")
    return False


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("Usage: diff_snapshot.py <before_raw_dir> [expected_class_change_old new]...")
    before_dir = Path(sys.argv[1])
    # Optional pairs of (old_substring, new_substring) for deliberate, known
    # changes (e.g. a class rename) that shouldn't count as a real diff -
    # pass them explicitly rather than silently swallowing all differences.
    extra = list(zip(sys.argv[2::2], sys.argv[3::2]))

    if not before_dir.is_dir():
        sys.exit(f"{before_dir} is not a directory")
    if not RAW_DIR.is_dir():
        sys.exit(f"{RAW_DIR} doesn't exist - run build_preview.py first")

    all_identical = True
    before_files = sorted(before_dir.glob("*.html"))
    if not before_files:
        sys.exit(f"No .html files found in {before_dir}")
    for before_file in before_files:
        after_file = RAW_DIR / before_file.name
        if not after_file.exists():
            print(f"{before_file.name}: MISSING from current build/_raw (page removed or renamed?)")
            all_identical = False
            continue
        if not diff_one(before_file, after_file, extra):
            all_identical = False

    print()
    print("ALL IDENTICAL" if all_identical else "DIFFERENCES FOUND - review above before calling this behavior-preserving")
    return 0 if all_identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
