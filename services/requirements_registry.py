"""
Flat-file JSON registry for parsed RFP/RFQ requirement records.

This is intentionally storage-agnostic at the call site: swap this
class for a SQLAlchemy-backed implementation later without touching
routes/api.py, since both expose save()/get()/list_ids().
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from services.bhive_parser import ParsedDocument, RequirementItem


class RequirementsRegistry:
    def __init__(self, store_path: str | Path):
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

    def save(self, document: ParsedDocument) -> ParsedDocument:
        path = self._path_for(document.project_id)
        path.write_text(json.dumps(document.to_dict(), indent=2), encoding="utf-8")
        return document

    def get(self, project_id: str) -> Optional[ParsedDocument]:
        path = self._path_for(project_id)
        if not path.exists():
            return None

        data = json.loads(path.read_text(encoding="utf-8"))
        requirements = [RequirementItem(**item) for item in data.get("requirements", [])]
        doc = ParsedDocument(
            project_id=data["project_id"],
            filename=data["filename"],
            ingested_at=data["ingested_at"],
            requirements=requirements,
            milestones=data.get("milestones", []),
        )
        return doc

    def list_ids(self) -> list[str]:
        return [p.stem for p in self.store_path.glob("*.json")]

    def _path_for(self, project_id: str) -> Path:
        return self.store_path / f"{project_id}.json"
