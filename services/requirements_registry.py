"""
Flat-file JSON registry for parsed RFP/RFQ requirement records.

This is intentionally storage-agnostic at the call site: swap this
class for a SQLAlchemy-backed implementation later without touching
routes/api.py, since both expose save()/get()/list_ids().
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from services.bhive_parser import ConsistencyFlag, ParsedDocument, RequirementItem


class RequirementsRegistry:
    def __init__(self, store_path: str | Path):
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

    def save(self, document: ParsedDocument) -> ParsedDocument:
        with self.lifecycle_lock(document.project_id):
            self.require_live(document.project_id)
            path = self._path_for(document.project_id)
            path.write_text(json.dumps(document.to_dict(), indent=2), encoding="utf-8")
        return document

    def deletion_path(self, project_id: str) -> Path:
        if not project_id or Path(project_id).name != project_id or project_id in (".", "..") or "\\" in project_id:
            raise ValueError("Invalid project identity")
        return self.store_path / "_deleted" / (project_id + ".json")

    def is_deleted(self, project_id: str) -> bool:
        return self.deletion_path(project_id).exists()

    def require_live(self, project_id: str) -> None:
        if self.is_deleted(project_id):
            raise ValueError("This container was permanently deleted.")

    @contextmanager
    def lifecycle_lock(self, project_id: str):
        """Serialize erasure with persistent writers, including other processes.

        Lock and deletion marker are internal registry metadata, never documents.
        The marker is the committed lifecycle decision; it cannot found a project.
        """
        self.deletion_path(project_id)  # validate before constructing any path
        directory = self.store_path / "_lifecycle"
        directory.mkdir(exist_ok=True)
        with (directory / (project_id + ".lock")).open("a+b") as stream:
            if os.name == "nt":
                import msvcrt
                stream.seek(0)
                # Windows permits locking beyond EOF. Do not read/write the
                # lock byte before acquiring it: another process may own it.
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def get(self, project_id: str) -> Optional[ParsedDocument]:
        if self.is_deleted(project_id):
            return None
        path = self._path_for(project_id)
        if not path.exists():
            return None

        data = json.loads(path.read_text(encoding="utf-8"))
        requirements = [RequirementItem(**item) for item in data.get("requirements", [])]
        consistency_flags = [
            ConsistencyFlag(**item) for item in data.get("consistency_flags", [])
        ]
        doc = ParsedDocument(
            project_id=data["project_id"],
            filename=data["filename"],
            ingested_at=data["ingested_at"],
            requirements=requirements,
            milestones=data.get("milestones", []),
            tables=data.get("tables", []),
            consistency_flags=consistency_flags,
            consistency_checked=data.get("consistency_checked", False),
            consistency_note=data.get("consistency_note"),
            original_file_path=data.get("original_file_path"),
            original_file_hash=data.get("original_file_hash"),
            parser_version=data.get("parser_version"),
            text_extraction_status=data.get("text_extraction_status", "extracted"),
        )
        return doc

    def list_ids(self) -> list[str]:
        # CaseWorkspaceStore's own files sit alongside these in the same
        # directory, named "<project_id>.workspace.json" -- Path.stem only
        # strips one suffix level, so a naive "*.json" glob would also
        # yield "<project_id>.workspace" as a bogus extra id. Excluded
        # explicitly rather than relying on load-time failure downstream.
        return [
            p.stem for p in self.store_path.glob("*.json")
            if not p.stem.endswith(".workspace") and not self.is_deleted(p.stem)
        ]

    def _path_for(self, project_id: str) -> Path:
        return self.store_path / f"{project_id}.json"
