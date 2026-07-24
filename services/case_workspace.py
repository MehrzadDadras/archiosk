"""
Case Workspace — the shared Project / Case / Source / Artifact / Analysis /
Finding / Review / Apply model, prototyped on top of the existing flat-JSON
storage (see RequirementsRegistry, GovernanceLog). One JSON file per
project, alongside that project's existing `{project_id}.json` (the
RFQ/RFP ParsedDocument) and `{project_id}.governance.jsonl`.

Authority sequence, preserved throughout this module:

    Analyze -> Review -> Apply

An Analysis run produces Findings. Findings are provisional
(claim_status="provisional") until a Review records a human decision.
A Review is never itself a mutation of governed project state — Apply is
a separate, explicit action (see apply_findings below) that is the only
thing in this module allowed to write into RequirementsRegistry or mark a
Finding as governed truth. Nothing in this module auto-applies a Finding
just because it was reviewed as "accept".
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Every ingested RFQ/RFP document is registered as this Project's first
# Source automatically (see get_or_create) — the RFQ/RFP pipeline is the
# beginning of the same persistent Project, not a separate product.
SOURCE_KIND_RFQ_RFP_DOCUMENT = "rfq_rfp_document"
SOURCE_KIND_DRAWING = "drawing"

FINDING_STATUS_PROVISIONAL = "provisional"
FINDING_STATUS_APPLIED = "applied"

REVIEW_DECISIONS = (
    "accept",
    "reject",
    "needs_evidence",
    "correction",
)


class CaseWorkspaceError(Exception):
    """Raised for invalid workspace operations (unknown ids, bad decisions, etc)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Source:
    id: str
    project_id: str
    kind: str  # SOURCE_KIND_*
    name: str
    added_at: str
    file_path: Optional[str] = None  # relative to the workspace's binary store, drawings only
    width: Optional[int] = None
    height: Optional[int] = None
    note: Optional[str] = None


@dataclass
class ConversationMessage:
    id: str
    case_id: str
    role: str  # "human" | "system"
    text: str
    created_at: str
    action_taken: Optional[str] = None


@dataclass
class Artifact:
    """
    A derived working object. Never a substitute for its Source — every
    Artifact keeps source_id, page, and crop distinct from the Source it
    was derived from, per the Specimen != Focus Page / Source != Artifact
    principle carried over from the 5173 Information Model.
    """

    id: str
    project_id: str
    case_id: str
    kind: str  # "focus_snip" | "comparison" | "requirement_excerpt"
    source_id: str
    analysis_id: str
    created_at: str
    engine_name: str
    engine_version: str
    page: Optional[int] = None
    crop: Optional[dict] = None  # {"x","y","width","height"} normalized 0-1
    image_path: Optional[str] = None  # relative path to the generated crop, drawing artifacts only
    finding_id: Optional[str] = None


@dataclass
class Finding:
    id: str
    project_id: str
    case_id: str
    analysis_id: str
    statement: str
    machine_confidence: float
    created_at: str
    claim_status: str = FINDING_STATUS_PROVISIONAL
    artifact_id: Optional[str] = None


@dataclass
class Review:
    id: str
    finding_id: str
    decision: str  # one of REVIEW_DECISIONS
    reviewer: str
    reviewed_at: str
    note: Optional[str] = None


@dataclass
class AnalysisRun:
    id: str
    project_id: str
    case_id: str
    source_ids: list[str]
    objective: str
    engine_name: str
    engine_version: str
    started_at: str
    completed_at: str
    finding_ids: list[str] = field(default_factory=list)


@dataclass
class ApplyRecord:
    id: str
    project_id: str
    finding_ids: list[str]
    applied_by: str
    applied_at: str
    target: str  # human-readable description of what governed state changed


@dataclass
class CaseRecord:
    id: str
    project_id: str
    title: str
    objective: str
    created_at: str
    status: str = "open"
    source_ids: list[str] = field(default_factory=list)
    conversation: list[dict] = field(default_factory=list)
    analysis_ids: list[str] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)


@dataclass
class ProjectWorkspace:
    project_id: str
    sources: list[dict] = field(default_factory=list)
    cases: list[dict] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    reviews: list[dict] = field(default_factory=list)
    analyses: list[dict] = field(default_factory=list)
    applies: list[dict] = field(default_factory=list)


class CaseWorkspaceStore:
    """
    Flat-JSON persistence: one `{project_id}.workspace.json` file per
    project, stored alongside RequirementsRegistry's own
    `{project_id}.json`. Mirrors RequirementsRegistry's own
    storage-agnostic style (save()/get()) deliberately, so a future
    backend swap (if ever justified) touches one class, not call sites.
    """

    def __init__(self, store_path: str | Path):
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.binaries_path = self.store_path / "workspace_artifacts"
        self.binaries_path.mkdir(parents=True, exist_ok=True)

    # -- persistence -------------------------------------------------------

    def _path_for(self, project_id: str) -> Path:
        return self.store_path / f"{project_id}.workspace.json"

    def get(self, project_id: str) -> Optional[ProjectWorkspace]:
        path = self._path_for(project_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectWorkspace(**data)

    def save(self, workspace: ProjectWorkspace) -> ProjectWorkspace:
        path = self._path_for(workspace.project_id)
        path.write_text(json.dumps(asdict(workspace), indent=2), encoding="utf-8")
        return workspace

    def get_or_create(
        self,
        project_id: str,
        register_document_source: Optional[dict] = None,
    ) -> ProjectWorkspace:
        """
        `register_document_source`, if given (filename + counts), is used
        once to auto-register the Project's already-ingested RFQ/RFP
        document as Source #1 — so a Project's lifecycle always starts
        from the same evidence that already exists, rather than asking
        the reviewer to re-upload something already in the registry.
        """
        workspace = self.get(project_id)
        if workspace is not None:
            return workspace

        workspace = ProjectWorkspace(project_id=project_id)

        if register_document_source is not None:
            source = Source(
                id=_new_id(),
                project_id=project_id,
                kind=SOURCE_KIND_RFQ_RFP_DOCUMENT,
                name=register_document_source["filename"],
                added_at=register_document_source.get("ingested_at") or _now(),
                note=(
                    f"{register_document_source.get('requirement_count', 0)} requirements, "
                    f"{register_document_source.get('milestone_count', 0)} milestones "
                    "already extracted by the Extract/Segment/Classify/Assemble pipeline."
                ),
            )
            workspace.sources.append(asdict(source))

        self.save(workspace)
        return workspace

    # -- lookups -------------------------------------------------------------

    @staticmethod
    def _find(items: list[dict], item_id: str, id_field: str = "id") -> Optional[dict]:
        return next((item for item in items if item[id_field] == item_id), None)

    # -- sources ---------------------------------------------------------------

    def add_drawing_source(
        self,
        workspace: ProjectWorkspace,
        name: str,
        file_path: str,
        width: int,
        height: int,
    ) -> dict:
        source = Source(
            id=_new_id(),
            project_id=workspace.project_id,
            kind=SOURCE_KIND_DRAWING,
            name=name,
            added_at=_now(),
            file_path=file_path,
            width=width,
            height=height,
        )
        workspace.sources.append(asdict(source))
        self.save(workspace)
        return asdict(source)

    # -- cases -----------------------------------------------------------------

    def create_case(self, workspace: ProjectWorkspace, title: str, objective: str) -> dict:
        case = CaseRecord(
            id=_new_id(),
            project_id=workspace.project_id,
            title=title,
            objective=objective,
            created_at=_now(),
        )
        workspace.cases.append(asdict(case))
        self.save(workspace)
        return asdict(case)

    def attach_source_to_case(self, workspace: ProjectWorkspace, case_id: str, source_id: str) -> None:
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")
        if source_id not in case["source_ids"]:
            case["source_ids"].append(source_id)
        self.save(workspace)

    def add_message(self, workspace: ProjectWorkspace, case_id: str, role: str, text: str, action_taken: Optional[str] = None) -> dict:
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")
        message = ConversationMessage(
            id=_new_id(),
            case_id=case_id,
            role=role,
            text=text,
            created_at=_now(),
            action_taken=action_taken,
        )
        case["conversation"].append(asdict(message))
        self.save(workspace)
        return asdict(message)

    # -- analysis / findings / artifacts ----------------------------------------

    def record_analysis(
        self,
        workspace: ProjectWorkspace,
        case_id: str,
        source_ids: list[str],
        objective: str,
        engine_name: str,
        engine_version: str,
        findings: list[dict],
    ) -> dict:
        """
        `findings` is a list of {"statement", "machine_confidence", "crop"?,
        "image_path"?, "page"?} dicts already produced by an analysis
        engine (e.g. services/drawing_analysis.py). This method is what
        actually persists them as governed-but-provisional Finding/Artifact
        records — the engine itself never touches the workspace store.
        """
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")

        started_at = _now()
        analysis_id = _new_id()
        finding_ids: list[str] = []

        for item in findings:
            finding_id = _new_id()
            artifact_id = None

            if item.get("crop") or item.get("image_path"):
                artifact = Artifact(
                    id=_new_id(),
                    project_id=workspace.project_id,
                    case_id=case_id,
                    kind=item.get("artifact_kind", "focus_snip"),
                    source_id=item["source_id"],
                    analysis_id=analysis_id,
                    created_at=_now(),
                    engine_name=engine_name,
                    engine_version=engine_version,
                    page=item.get("page"),
                    crop=item.get("crop"),
                    image_path=item.get("image_path"),
                )
                artifact_id = artifact.id
                workspace.artifacts.append(asdict(artifact))
                case["artifact_ids"].append(artifact_id)

            finding = Finding(
                id=finding_id,
                project_id=workspace.project_id,
                case_id=case_id,
                analysis_id=analysis_id,
                statement=item["statement"],
                machine_confidence=item["machine_confidence"],
                created_at=_now(),
                artifact_id=artifact_id,
            )
            workspace.findings.append(asdict(finding))
            case["finding_ids"].append(finding_id)
            finding_ids.append(finding_id)

            if artifact_id is not None:
                artifact_record = self._find(workspace.artifacts, artifact_id)
                artifact_record["finding_id"] = finding_id

        analysis = AnalysisRun(
            id=analysis_id,
            project_id=workspace.project_id,
            case_id=case_id,
            source_ids=source_ids,
            objective=objective,
            engine_name=engine_name,
            engine_version=engine_version,
            started_at=started_at,
            completed_at=_now(),
            finding_ids=finding_ids,
        )
        workspace.analyses.append(asdict(analysis))
        case["analysis_ids"].append(analysis_id)

        self.save(workspace)
        return asdict(analysis)

    # -- review ------------------------------------------------------------------

    def record_review(
        self,
        workspace: ProjectWorkspace,
        finding_id: str,
        decision: str,
        reviewer: str,
        note: Optional[str] = None,
    ) -> dict:
        if decision not in REVIEW_DECISIONS:
            raise CaseWorkspaceError(
                f"'{decision}' is not a recognized review decision. "
                f"Use one of: {', '.join(REVIEW_DECISIONS)}."
            )

        finding = self._find(workspace.findings, finding_id)
        if finding is None:
            raise CaseWorkspaceError(f"Finding {finding_id} was not found.")

        if finding["claim_status"] == FINDING_STATUS_APPLIED:
            raise CaseWorkspaceError(
                "This Finding has already been applied to governed project "
                "state and can no longer be reviewed. Its history remains "
                "in place; it cannot be re-adjudicated retroactively."
            )

        review = Review(
            id=_new_id(),
            finding_id=finding_id,
            decision=decision,
            reviewer=reviewer,
            reviewed_at=_now(),
            note=note,
        )
        workspace.reviews.append(asdict(review))
        # Review records a human decision. It does NOT change claim_status
        # to "applied" — that is Apply's job alone (see apply_findings).
        self.save(workspace)
        return asdict(review)

    def reviews_for_finding(self, workspace: ProjectWorkspace, finding_id: str) -> list[dict]:
        return [r for r in workspace.reviews if r["finding_id"] == finding_id]

    def latest_review(self, workspace: ProjectWorkspace, finding_id: str) -> Optional[dict]:
        reviews = self.reviews_for_finding(workspace, finding_id)
        return reviews[-1] if reviews else None

    # -- apply ---------------------------------------------------------------------

    def apply_findings(
        self,
        workspace: ProjectWorkspace,
        finding_ids: list[str],
        applied_by: str,
        target: str = "Recorded in the Project's governed finding ledger.",
    ) -> dict:
        """
        The only method in this module that may set claim_status to
        "applied". Requires every listed Finding to have an "accept"
        review already on record — Apply never runs off an unreviewed or
        rejected/needs-evidence Finding. This is the explicit,
        separately-authorized step; nothing upstream of this call
        (Analysis, Review) can trigger it on its own.
        """
        for finding_id in finding_ids:
            finding = self._find(workspace.findings, finding_id)
            if finding is None:
                raise CaseWorkspaceError(f"Finding {finding_id} was not found.")

            latest = self.latest_review(workspace, finding_id)
            if latest is None or latest["decision"] != "accept":
                raise CaseWorkspaceError(
                    f"Finding {finding_id} does not have an accepted Review on "
                    "record. Apply requires an explicit 'accept' decision first."
                )

        apply_record = ApplyRecord(
            id=_new_id(),
            project_id=workspace.project_id,
            finding_ids=list(finding_ids),
            applied_by=applied_by,
            applied_at=_now(),
            target=target,
        )
        workspace.applies.append(asdict(apply_record))

        for finding_id in finding_ids:
            finding = self._find(workspace.findings, finding_id)
            finding["claim_status"] = FINDING_STATUS_APPLIED

        self.save(workspace)
        return asdict(apply_record)
