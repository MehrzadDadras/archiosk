"""
CLAUDE-P27-B: no backup mechanism existed anywhere in this repository
before tools/backup_data.py / tools/restore_data.py -- a server loss
meant total, unrecoverable data loss. These tests exercise the real
backup->restore round trip against scratch data (never the real
instance/bhive.db or instance/registry) and confirm the safety
behaviors: refusing to extract into a non-empty target, and refusing
to back up a non-SQLite DATABASE_URL.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_backup_"))
        self.db_path = self.tmp_dir / "scratch.db"
        self.registry_path = self.tmp_dir / "registry"
        self.registry_path.mkdir()
        (self.registry_path / "proj1.json").write_text('{"hello": "world"}', encoding="utf-8")
        nested = self.registry_path / "workspace_sources" / "proj1"
        nested.mkdir(parents=True)
        (nested / "source.txt").write_text("source content", encoding="utf-8")

        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        conn.execute("INSERT INTO users (username) VALUES ('scratch_user')")
        conn.commit()
        conn.close()

        self.output_dir = self.tmp_dir / "backups"
        self.restore_dir = self.tmp_dir / "restored"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _fake_config(self, db_uri: str | None = None):
        class FakeConfig:
            SQLALCHEMY_DATABASE_URI = db_uri or f"sqlite:///{self.db_path}"
            REGISTRY_STORE_PATH = str(self.registry_path)
        return FakeConfig

    def test_backup_then_restore_round_trip_preserves_data(self):
        import tools.backup_data as backup_module
        import tools.restore_data as restore_module

        with mock.patch("config.get_config", return_value=self._fake_config()):
            archive_path = backup_module.create_backup(self.output_dir)

        self.assertTrue(archive_path.exists())

        restore_module.restore_backup(archive_path, self.restore_dir)

        restored_db = self.restore_dir / "bhive.db"
        self.assertTrue(restored_db.exists())
        conn = sqlite3.connect(restored_db)
        row = conn.execute("SELECT username FROM users").fetchone()
        conn.close()
        self.assertEqual(row[0], "scratch_user")

        self.assertEqual(
            (self.restore_dir / "registry" / "proj1.json").read_text(encoding="utf-8"),
            '{"hello": "world"}',
        )
        self.assertEqual(
            (self.restore_dir / "registry" / "workspace_sources" / "proj1" / "source.txt").read_text(encoding="utf-8"),
            "source content",
        )

    def test_backup_refuses_non_sqlite_database_url(self):
        import tools.backup_data as backup_module

        with mock.patch("config.get_config", return_value=self._fake_config(db_uri="postgresql://x/y")):
            with self.assertRaises(SystemExit):
                backup_module.create_backup(self.output_dir)

    def test_restore_refuses_a_non_empty_target_directory(self):
        import tools.backup_data as backup_module
        import tools.restore_data as restore_module

        with mock.patch("config.get_config", return_value=self._fake_config()):
            archive_path = backup_module.create_backup(self.output_dir)

        self.restore_dir.mkdir()
        (self.restore_dir / "already-here.txt").write_text("do not overwrite me", encoding="utf-8")

        with self.assertRaises(SystemExit):
            restore_module.restore_backup(archive_path, self.restore_dir)

        # Original file untouched -- the refusal must be a hard stop, not
        # a partial extraction over existing content.
        self.assertEqual(
            (self.restore_dir / "already-here.txt").read_text(encoding="utf-8"), "do not overwrite me",
        )
        self.assertFalse((self.restore_dir / "bhive.db").exists())


if __name__ == "__main__":
    unittest.main()
