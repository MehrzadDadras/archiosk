#!/usr/bin/env python
"""
Back up the SQLite database (users/password-reset tokens) and the flat-
JSON registry store (projects, CaseWorkspaceStore state, GovernanceLog)
into a single timestamped .tar.gz archive (CLAUDE-P27-B).

No backup mechanism existed anywhere in this repository before this --
a server loss meant total, unrecoverable data loss. Read-only with
respect to the source data (a tar archive is built by reading the live
files, nothing under instance/ is ever modified or moved).

    python tools/backup_data.py [--output-dir backups]

Produces backups/archiosk-backup-<UTC timestamp>.tar.gz containing:
    bhive.db          -- copy of the SQLite database file
    registry/          -- copy of the whole registry directory tree

Restoring: see tools/restore_data.py, which extracts one of these
archives into an explicit target directory -- it never writes over a
live instance/ directory by default, specifically to avoid a restore
accidentally clobbering newer live data.
"""
from __future__ import annotations

import argparse
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def _resolve_paths():
    """Same resolution config.py itself uses -- reads .env via get_config(),
    not a hardcoded instance/ path, so an operator's real DATABASE_URL/
    REGISTRY_STORE_PATH override (if any) is honored here too."""
    import os

    from config import get_config

    cfg = get_config(os.getenv("FLASK_ENV"))
    db_uri = cfg.SQLALCHEMY_DATABASE_URI
    if not db_uri.startswith("sqlite:///"):
        raise SystemExit(
            f"This tool only backs up SQLite databases; DATABASE_URL resolved to {db_uri!r}.",
        )
    db_path = Path(db_uri.removeprefix("sqlite:///"))
    registry_path = Path(cfg.REGISTRY_STORE_PATH)
    return db_path, registry_path


def create_backup(output_dir: Path) -> Path:
    db_path, registry_path = _resolve_paths()

    if not db_path.exists():
        raise SystemExit(f"Database file not found: {db_path}")
    if not registry_path.exists():
        raise SystemExit(f"Registry store not found: {registry_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = output_dir / f"archiosk-backup-{timestamp}.tar.gz"

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(db_path, arcname="bhive.db")
        tar.add(registry_path, arcname="registry")

    return archive_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--output-dir", default=str(BASE_DIR / "backups"),
        help="Directory to write the .tar.gz archive into (created if missing). Default: ./backups",
    )
    args = parser.parse_args(argv)

    archive_path = create_backup(Path(args.output_dir))
    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"Backup written: {archive_path} ({size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
