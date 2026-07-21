"""
B-Hive Core Chassis — modular ingestion pipeline for RFP/RFQ documents.

Pipeline stages (each is swappable — see `BHiveParser.STAGES`):
    1. extract   — pull raw text out of the uploaded file (pdf/docx/txt/csv)
    2. segment   — split raw text into candidate requirement chunks
    3. classify  — categorize each chunk against the requirement schema
                   (uses the Anthropic API when ANTHROPIC_API_KEY is set;
                   falls back to a rule-based classifier otherwise so the
                   pipeline still runs in dev/test without a key)
    4. assemble  — build the final ParsedDocument record

Each stage is a small, independently testable function/class so new
document types or classification strategies can be added without
touching the others.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# How long to wait on a single classification batch before giving up on it.
DEFAULT_CLASSIFY_TIMEOUT_SECONDS = 30.0

REQUIREMENT_CATEGORIES = [
    "scope_of_work",
    "technical_specification",
    "compliance_legal",
    "budget_commercial",
    "schedule_milestone",
    "submission_instruction",
    "evaluation_criteria",
    "other",
]


class ParserError(Exception):
    """Raised when a document cannot be parsed into requirement records."""


@dataclass
class RequirementItem:
    id: str
    text: str
    category: str
    confidence: float
    source_line: int


@dataclass
class ParsedDocument:
    project_id: str
    filename: str
    ingested_at: str
    requirements: list[RequirementItem] = field(default_factory=list)
    milestones: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "filename": self.filename,
            "ingested_at": self.ingested_at,
            "requirements": [r.__dict__ for r in self.requirements],
            "milestones": self.milestones,
        }


class BHiveParser:
    """Coordinates the extract -> segment -> classify -> assemble pipeline."""

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        # Falls back to the environment so every module gets the key the
        # same way — never hardcode it, never pass it in from a route directly.
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        self.timeout = timeout or float(
            os.getenv("ANTHROPIC_TIMEOUT_SECONDS", DEFAULT_CLASSIFY_TIMEOUT_SECONDS)
        )

    # -- public entrypoint -------------------------------------------------
    def parse(self, raw_bytes: bytes, filename: str) -> ParsedDocument:
        text = self._extract(raw_bytes, filename)
        if not text.strip():
            raise ParserError(f"No extractable text found in '{filename}'.")

        chunks = self._segment(text)
        requirements = self._classify(chunks)
        milestones = self._derive_milestones(requirements)

        return ParsedDocument(
            project_id=str(uuid.uuid4()),
            filename=filename,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            requirements=requirements,
            milestones=milestones,
        )

    # -- stage 1: extract ---------------------------------------------------
    def _extract(self, raw_bytes: bytes, filename: str) -> str:
        ext = Path(filename).suffix.lower()

        if ext == ".txt" or ext == ".csv":
            return raw_bytes.decode("utf-8", errors="ignore")

        if ext == ".docx":
            return self._extract_docx(raw_bytes)

        if ext == ".pdf":
            return self._extract_pdf(raw_bytes)

        raise ParserError(f"Unsupported extension for extraction: {ext}")

    @staticmethod
    def _extract_docx(raw_bytes: bytes) -> str:
        try:
            import docx  # python-docx
        except ImportError as exc:
            raise ParserError("python-docx is required to parse .docx files.") from exc

        document = docx.Document(io.BytesIO(raw_bytes))
        return "\n".join(p.text for p in document.paragraphs)

    @staticmethod
    def _extract_pdf(raw_bytes: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ParserError("pypdf is required to parse .pdf files.") from exc

        reader = PdfReader(io.BytesIO(raw_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    # -- stage 2: segment ----------------------------------------------------
    def _segment(self, text: str) -> list[tuple[int, str]]:
        """Split into non-trivial lines/clauses, keeping 1-indexed line numbers."""
        chunks = []
        for i, line in enumerate(text.splitlines(), start=1):
            cleaned = line.strip(" \t-*•")
            if len(cleaned) >= 8:
                chunks.append((i, cleaned))
        return chunks

    # -- stage 3: classify ----------------------------------------------------
    def _classify(self, chunks: list[tuple[int, str]]) -> list[RequirementItem]:
        if self.api_key:
            try:
                return self._classify_with_model(chunks)
            except Exception:
                # Model classification is best-effort; never let an API hiccup
                # take down ingestion. Fall through to the rule-based path.
                logger.warning(
                    "Model classification failed; falling back to rule-based classification.",
                    exc_info=True,
                )
        return self._classify_with_rules(chunks)

    def _classify_with_model(self, chunks: list[tuple[int, str]]) -> list[RequirementItem]:
        """Batch-classify chunks via the Anthropic API. Requires ANTHROPIC_API_KEY."""
        import anthropic  # imported lazily so the dep is optional in dev

        client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)
        items: list[RequirementItem] = []

        batch_size = 25
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            prompt = self._build_classification_prompt(batch)
            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                )
            except anthropic.APITimeoutError:
                # Don't let one slow batch discard classification results the
                # model already produced for earlier batches — only this
                # batch's chunks fall back to the rule-based classifier.
                logger.warning(
                    "Anthropic classification request timed out after %.0fs for "
                    "lines %d-%d; falling back to rule-based classification for "
                    "this batch.",
                    self.timeout, batch[0][0], batch[-1][0],
                )
                items.extend(self._classify_with_rules(batch))
                continue

            text_out = "".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
            items.extend(self._parse_model_output(text_out, batch))

        return items

    @staticmethod
    def _build_classification_prompt(batch: list[tuple[int, str]]) -> str:
        categories = ", ".join(REQUIREMENT_CATEGORIES)
        lines = "\n".join(f"{line_no}: {text}" for line_no, text in batch)
        return (
            "Classify each numbered line from an RFP/RFQ into exactly one of "
            f"these categories: {categories}.\n"
            "Respond ONLY with a JSON array of objects: "
            '[{"line": <int>, "category": "<one of the categories>", '
            '"confidence": <0-1 float>}]. No prose, no markdown fences.\n\n"'
            f"{lines}"
        )

    @staticmethod
    def _parse_model_output(
        text_out: str, batch: list[tuple[int, str]]
    ) -> list[RequirementItem]:
        cleaned = re.sub(r"^```(json)?|```$", "", text_out.strip(), flags=re.MULTILINE).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ParserError("Model returned non-JSON classification output.") from exc

        text_by_line = dict(batch)
        items = []
        for entry in parsed:
            line_no = entry.get("line")
            if line_no not in text_by_line:
                continue
            items.append(
                RequirementItem(
                    id=str(uuid.uuid4()),
                    text=text_by_line[line_no],
                    category=entry.get("category", "other"),
                    confidence=float(entry.get("confidence", 0.5)),
                    source_line=line_no,
                )
            )
        return items

    @staticmethod
    def _classify_with_rules(chunks: list[tuple[int, str]]) -> list[RequirementItem]:
        """Deterministic fallback classifier — keyword matching, no API needed."""
        # Order matters: more specific phrase-level cues are checked before
        # loose single-word ones so e.g. "evaluated on cost" doesn't get
        # swallowed by the budget_commercial bucket.
        keyword_map = {
            "evaluation_criteria": ("evaluated on", "scoring", "evaluation criteria", "weighted"),
            "schedule_milestone": ("deadline", "milestone", "due by", "completion date"),
            "submission_instruction": ("submit", "proposal must include", "submission"),
            "compliance_legal": ("code", "regulation", "license", "insurance", "liability"),
            "scope_of_work": ("scope", "work shall include", "contractor shall"),
            "technical_specification": ("shall comply with", "specification", "material", "dimension"),
            "budget_commercial": ("budget", "cost", "price", "fee", "$"),
        }

        items = []
        for line_no, text in chunks:
            lowered = text.lower()
            category = "other"
            for cat, keywords in keyword_map.items():
                if any(kw in lowered for kw in keywords):
                    category = cat
                    break
            items.append(
                RequirementItem(
                    id=str(uuid.uuid4()),
                    text=text,
                    category=category,
                    confidence=0.4 if category == "other" else 0.65,
                    source_line=line_no,
                )
            )
        return items

    # -- stage 4: assemble (milestones) --------------------------------------
    @staticmethod
    def _derive_milestones(requirements: list[RequirementItem]) -> list[dict[str, Any]]:
        milestones = []
        for req in requirements:
            if req.category == "schedule_milestone":
                milestones.append(
                    {
                        "id": str(uuid.uuid4()),
                        "label": req.text[:120],
                        "status": "pending",
                        "source_line": req.source_line,
                    }
                )
        return milestones
