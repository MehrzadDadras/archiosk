#!/usr/bin/env python
"""
Extract a tools/backup_data.py archive into an explicit target
directory (CLAUDE-P27-B). Deliberately requires --target-dir with no
default pointing at instance/ -- a restore accidentally overwriting a
live, newer instance/ directory would itself be a data-loss incident,
not a recovery. Verify the extracted contents (row counts, file
counts) yourself before deciding to actually swap it in for a real
instance/ directory; this tool only extracts, it never touches the
live path for you.

    python tools/restore_data.py --archive backups/archiosk-backup-<ts>.tar.gz --target-dir /path/to/scratch
"""
from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path


def restore_backup(archive_path: Path, target_dir: Path) -> None:
    if not archive_path.exists():
        raise SystemExit(f"Archive not found: {archive_path}")
    if target_dir.exists() and any(target_dir.iterdir()):
        raise SystemExit(
            f"Target directory {target_dir} already exists and is non-empty -- "
            "refusing to extract into it. Choose an empty/new directory.",
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as tar:
        # Pre-create every member's parent directory -- tarfile's own
        # extractall() assumes directory members are extracted before
        # the files inside them, which isn't guaranteed by tar member
        # order and was observed to fail with FileNotFoundError on a
        # real archive containing deeply-nested workspace_sources/
        # subdirectories on Windows.
        for member in tar.getmembers():
            (target_dir / member.name).parent.mkdir(parents=True, exist_ok=True)
        tar.extractall(target_dir, filter="data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="Path to a tools/backup_data.py .tar.gz archive.")
    parser.add_argument(
        "--target-dir", required=True,
        help="Empty or non-existent directory to extract into. Never defaults to instance/.",
    )
    args = parser.parse_args(argv)

    restore_backup(Path(args.archive), Path(args.target_dir))
    target = Path(args.target_dir)
    print(f"Restored to {target}:")
    print(f"  {target / 'bhive.db'}")
    print(f"  {target / 'registry'} ({sum(1 for _ in (target / 'registry').rglob('*') if _.is_file())} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
