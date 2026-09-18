"""CLAUDE-DOCUMENT-SHOP-RESULT-01 - what the customer is actually handed.

A PRESENTATION layer over governed state that already exists. It runs no
analysis, calls no provider, writes nothing, and introduces no second
As-Read: `ingest_upload` already parses every accepted document and already
runs local OCR over an accepted image, and every fact below is read back from
what those two paths recorded. The defect this closes was never missing
processing - it was that the processing had no customer-facing surface, so a
person who uploaded a document was sent to the analyst bench instead and told
"As-Read has not started on this source".

    SIMPLE OUTSIDE. GOVERNED INSIDE.

Three things this deliberately does NOT do:

- **It does not invent a status transition.** Examination is synchronous
  inside the upload request, so by the time any record exists it has already
  finished. There is therefore no honest PENDING/PROCESSING state to show, and
  inventing one would be a status unsupported by any record. `state_of` returns
  only outcomes that a stored record can actually establish.
- **It does not fabricate an interpretation.** Where the pipeline established
  nothing, this says so by name rather than rendering an empty section that
  reads like a finished answer.
- **It does not translate governed vocabulary into the record.** As-Read,
  Spin, marks, vectorisation and sheet grammar stay exactly where they are;
  they are simply not what a Document Shop customer is shown.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

# What a person is told about their job, and the only three outcomes a stored
# record can support. Ordered worst-last so a listing can sort by concern.
STATE_RESULT_READY = "result_ready"
STATE_READ_NOT_INTERPRETED = "read_not_interpreted"
STATE_NEEDS_ATTENTION = "needs_attention"
STATE_COULD_NOT_COMPLETE = "could_not_complete"

# CLAUDE-GO-PERCEPTION-WORKER-01: two states that only became TRUE when the
# work actually moved off the request.
#
# This module previously refused to render "Processing", and that refusal was
# right: examination ran inside the upload request, so by the time any record
# existed it had finished, and a pending state would have been a status no
# record could support. Asynchronous perception creates the record that makes
# it true. The rule did not change - the facts did.
STATE_QUEUED = "queued"
STATE_PROCESSING = "processing"

STATE_LABELS = {
    STATE_QUEUED: "Waiting to be examined",
    STATE_PROCESSING: "Being examined",
    STATE_RESULT_READY: "Result ready",
    STATE_READ_NOT_INTERPRETED: "Read, not interpreted",
    STATE_NEEDS_ATTENTION: "Needs attention",
    STATE_COULD_NOT_COMPLETE: "Could not complete",
}

# CLAUDE-EXAMINATION-ACTIVITY-01: what the person is told WHILE it runs.
#
# `STATE_LABELS` answers "what is the outcome", and while an examination is in
# flight there is no outcome yet - so a page showing only those two pending
# labels tells someone waiting almost nothing, and tells them the same thing
# for a minute whatever is happening underneath.
#
# These are finer, and each one is a fact a stored job record can actually
# establish. THEY NAME THE WORK, NEVER THE MACHINERY: no worker, no queue, no
# job id, no processing version, no model. "Examining document" is true and
# useful; "orientation-ocr@1 claimed by vps-a12692b3:905538" is neither.
ACTIVITY_QUEUED = "Waiting to be examined"
ACTIVITY_READING = "Examining document…"
ACTIVITY_LOOKING = "Visual analysis in progress…"

# Ordered worst-last: an aggregate takes the LEAST settled state among its
# sources, so an examination never looks finished while part of it is not.
_AGGREGATE_PRECEDENCE = (
    STATE_COULD_NOT_COMPLETE,
    STATE_QUEUED,
    STATE_PROCESSING,
    STATE_NEEDS_ATTENTION,
    STATE_READ_NOT_INTERPRETED,
    STATE_RESULT_READY,
)

# Plain-language equivalents. The key is the file's own extension, so nothing
# here claims to know what the document IS - only what kind of file arrived.
_MATERIAL_BY_EXT = {
    ".pdf": "a PDF document",
    ".docx": "a Word document",
    ".txt": "a plain text file",
    ".md": "a text document",
    ".csv": "a comma-separated data file",
    ".png": "an image (PNG)",
    ".jpg": "an image (JPEG)",
    ".jpeg": "an image (JPEG)",
}

_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


def _ext(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def _stored_filename(source: dict) -> str:
    """The name of the file actually on disk, for questions about its FORMAT.

    CLAUDE-DOCUMENT-UPLOAD-01. `ingestion` stores bytes as
    `<uuid4hex>_<secure_filename>`, so the real extension is always on
    `file_path` - which is the field provenance and evidence identity hang off,
    and the one that never changes. `Source.name` is a display label and now
    legitimately carries a work-item name with no extension at all.

    Falls back to the display name so a record written before bytes were stored
    (an external-connector source has `file_path is None` by design) behaves
    exactly as it did before.
    """
    return source.get("file_path") or source.get("name") or ""


def _live_sources(workspace) -> list[dict]:
    """The sources the PERSON sent, which is not every Source on the record.

    CLAUDE-SURVEY-REFERENCE-01: a Survey Reference is stored as a Source, so
    that save, reopen, download and provenance are what a Source already does
    rather than a second storage mechanism. It is not a thing anybody uploaded,
    so it must not appear in "What you sent", must not be counted in
    "Processing 2 of 5", and must not drag the aggregate state - an artifact
    this application composed cannot be evidence about how the examination is
    going.
    """
    from services.case_workspace import GENERATED_SOURCE_ORIGIN_TYPES

    return [s for s in (getattr(workspace, "sources", None) or [])
            if not s.get("removed_at")
            and s.get("origin_type") not in GENERATED_SOURCE_ORIGIN_TYPES]


def _page_units(workspace, source_id: str) -> list[dict]:
    return [u for u in (getattr(workspace, "structural_units", None) or [])
            if u.get("source_id") == source_id and u.get("unit_type") == "page"]


def _regions_for(workspace, unit_ids: set) -> dict:
    """The addressing records for this source's pages, keyed by id.

    A region carries WHERE something is (`region_type`, `address` with
    page_index/paragraph_index) and nothing about what it says. That division
    is the storage model, and this reader follows it rather than asking a
    region for content it was never given.
    """
    return {r["id"]: r for r in (getattr(workspace, "addressable_regions", None) or [])
            if r.get("structural_unit_id") in unit_ids}


def _recovered(workspace, source_id: str) -> dict:
    """Text held against this Source, and HOW it got there.

    CLAUDE-DOCUMENT-SHOP-OCR-READER-01. This function previously read
    `content` / `content_type` / `evidence_class` off `addressable_regions`,
    where none of those fields exist. The storage model, confirmed against real
    production records rather than inferred from a function's parameter names:

        Source
          -> StructuralUnit   (unit_type="page", source_id)      WHICH PAGE
          -> AddressableRegion(structural_unit_id, address)       WHERE ON IT
          -> EvidenceItem     (source_id, region_id, content,     WHAT IT SAYS
                               content_type, evidence_class,
                               extractor_version)

    The consequence of reading the wrong record was not a blank section: a
    successfully OCR-read image was told "No text could be read from this
    image" while its text sat in evidence_items, and its state read Needs
    attention. A customer-facing contradiction of the system's own evidence.

    Scoped three ways, deliberately, because this text is customer material:
    only this workspace (we are handed one), only evidence whose own
    `source_id` matches, and only evidence anchored to a region belonging to a
    page unit OF that source. `source_id` alone would be enough today; the
    region join means a future record that carries a stale or absent source_id
    still cannot cross a source boundary.
    """
    from services.case_workspace import (
        EVIDENCE_CLASS_DIRECT_SOURCE, EVIDENCE_CLASS_EXTRACTED,
    )

    units = _page_units(workspace, source_id)
    regions = _regions_for(workspace, {u["id"] for u in units})
    items = [
        e for e in (getattr(workspace, "evidence_items", None) or [])
        if e.get("source_id") == source_id
        and e.get("content_type") == "text"
        and (e.get("content") or "").strip()
        and e.get("region_id") in regions
    ]

    def _address(item):
        addr = (regions[item["region_id"]].get("address") or {})
        return (addr.get("page_index") or 0, addr.get("paragraph_index") or 0)

    items.sort(key=_address)
    passages = [e["content"] for e in items]
    classes = {e.get("evidence_class") for e in items if e.get("evidence_class")}
    engines = {e.get("extractor_version") for e in items if e.get("extractor_version")}
    return {
        "page_count": len(units),
        "passage_count": len(passages),
        "character_count": sum(len(p) for p in passages),
        "preview": "\n\n".join(passages[:3])[:1200],
        # OCR-recovered text is a READING of an image; text a document carries
        # is the document speaking. The evidence class already records which,
        # so this reports it rather than guessing from the engine's name.
        "was_recovered": EVIDENCE_CLASS_EXTRACTED in classes,
        "is_direct_source": EVIDENCE_CLASS_DIRECT_SOURCE in classes,
        "read_by": sorted(e for e in engines if e),
    }


def _decoded_record(workspace, source_id: str, content_type: str):
    """The most recent JSON record of one kind held against this Source.

    Evidence is append-only, so a re-examination adds rather than replaces and
    the LAST one is the current reading. A record that will not parse is
    treated as absent rather than raising: a malformed evidence row must not be
    able to take down the page that reports the examination.
    """
    import json

    rows = [e for e in (getattr(workspace, "evidence_items", None) or [])
            if e.get("source_id") == source_id
            and e.get("content_type") == content_type]
    for row in reversed(rows):
        try:
            decoded = json.loads(row.get("content") or "")
        except (TypeError, ValueError):
            continue
        if isinstance(decoded, dict):
            decoded["evidence_item_id"] = row.get("id")
            return decoded
    return None


def visual_reading(workspace, source_id: str):
    """What GO SAW in this source, or None. The visual counterpart to
    `_recovered`, and read the same way: off the record, never recomputed."""
    from services import visual_examination as vx

    visual = _decoded_record(workspace, source_id, vx.VISUAL_CONTENT_TYPE)
    if visual and any(s.get("measurements") for s in (visual.get("graph") or {}).get("segments", [])):
        from flask import current_app
        from services.case_workspace import CaseWorkspaceStore
        from services.survey_graph import resolve_measurement_premises
        store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
        resolve_measurement_premises(store, workspace, visual)
    if visual and (visual.get("graph") or {}).get("north_candidates"):
        from flask import current_app
        from services.case_workspace import CaseWorkspaceStore
        from services.survey_north import resolve_conversions
        resolve_conversions(CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"]), workspace, visual)
    if visual and (visual.get("graph") or {}).get("access_occurrences"):
        from flask import current_app
        from services.case_workspace import CaseWorkspaceStore
        from services.survey_graph import resolve_access_interpretations
        resolve_access_interpretations(CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"]), workspace, visual)
    if visual and (visual.get("graph") or {}).get("height_datums"):
        from flask import current_app
        from services.case_workspace import CaseWorkspaceStore
        from services.height_datum_governance import resolve_height_datums
        resolve_height_datums(CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"]), workspace, visual)
    return visual


def survey_reference_of(workspace, source_id: str):
    """The Survey Reference derived from this source, or None."""
    from services import survey_reference as sr

    reference = _decoded_record(workspace, source_id, sr.REFERENCE_CONTENT_TYPE)
    if reference and (reference.get("graph") or {}).get("north_candidates"):
        from flask import current_app
        from services.case_workspace import CaseWorkspaceStore
        from services.survey_north import resolve_conversions
        visual = visual_reading(workspace, source_id)
        if visual:
            resolve_conversions(CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"]), workspace,
                                {"graph": reference["graph"], "evidence_item_id": visual["evidence_item_id"]})
    return reference


def _visual_established_anything(visual) -> bool:
    from services import visual_examination as vx

    return any(o.get("certainty") in vx.VALUE_BEARING
               for o in ((visual or {}).get("observations") or []))


def _visual_lines(visual) -> tuple[list, list, list]:
    """The three short lists a visually-read document is described by.

    Returns (recovered, partially_recovered, unresolved) as plain phrases.
    Values are joined to their labels here rather than in the template, so the
    result page, the Survey Reference sheet and GO all describe one reading in
    one vocabulary.
    """
    from services import visual_examination as vx

    if not visual:
        return [], [], []

    def _phrase(observation):
        return ("%s: %s" % (observation["label"], observation["value"])
                if observation.get("value") else observation["label"])

    observations = visual.get("observations") or []
    directional_unresolved = []
    if visual.get("document_category") == "survey":
        from services import survey_north
        north_resolution = survey_north.resolve_true_north(visual.get("graph") or {})
        admitted = []
        for observation in observations:
            import re
            from services.height_datum_governance import is_height_datum_claim
            if is_height_datum_claim(observation):
                directional_unresolved.append("Regulatory datum UNRESOLVED from recovered text alone; observed %s; use independently established authority/applicability/alignment premises" % _phrase(observation))
                continue
            if observation.get("key") not in ("address", "streets") and re.search(
                    r"\b(?:primary frontage|building front|primary access|main entr(?:y|ance))\b", observation.get("value", ""), re.I):
                directional_unresolved.append("Access interpretation UNRESOLVED from free-form text alone; observed %s [directional reference %s; true North %s]; use scoped reviewed access evidence" % (
                    _phrase(observation), observation.get("directional_reference", "UNRESOLVED"), north_resolution["state"]))
            elif survey_north.directional_observation(observation) and not survey_north.admits_true_direction(observation, north_resolution):
                directional_unresolved.append("Directional conclusion UNRESOLVED; observed %s [reference %s; true North %s]" % (
                    _phrase(observation), observation.get("directional_reference", "UNRESOLVED"), north_resolution["state"]))
            else:
                admitted.append(observation)
        observations = admitted
        if north_resolution["state"] != "ESTABLISHED":
            directional_unresolved.append("True North UNRESOLVED: " + north_resolution["reason"])
    survey = visual.get("document_category") == "survey"
    structures = [o for o in observations if o.get("key") in ("building_footprint", "accessory_structures")]
    if survey:
        observations = [o for o in observations if o not in structures]
    recovered = [_phrase(o) for o in observations
                 if o.get("certainty") == vx.RECOVERED]
    partial = [_phrase(o) for o in observations
               if o.get("certainty") == vx.PARTIALLY_RECOVERED]
    unresolved = list(visual.get("unresolved") or []) + directional_unresolved
    from services import binding

    if survey:
        from services import survey_graph
        graph = visual.get("graph") or {}
        from services.height_datum_governance import height_datum_projection
        for datum in height_datum_projection(graph):
            geometry = datum["street_centerline_geometry"] or {}
            review = datum["review"]
            phrase = "Height datum %s: %s; subject %s; street %s; geometry provenance %s; premises %s; authority evidence %s" % (
                datum["candidate_id"], datum["datum_status"], datum["subject_id"], geometry.get("street_name"), geometry.get("note"),
                "; ".join("%s=%s [evidence %s]" % (axis, p["state"], ",".join(p["evidence_ids"])) for axis, p in review.get("premises", {}).items()),
                ",".join(a["evidence_id"] for a in review.get("authorities", [])))
            (recovered if datum["datum_status"] in ("GOVERNING_DATUM_ESTABLISHED", "GEOMETRY_ONLY") else unresolved).append(phrase)
            for axis in ("street_centerline_geometry", "regulatory_requirement", "applicability", "selected_governing_street", "building_reference_alignment_or_midpoint"):
                value = datum.get(axis) or {}
                partial.append("Datum observation %s / %s: %s; read %s; binding %s; provenance %s" % (
                    datum["candidate_id"], axis, value.get("value"), value.get("read_certainty"), binding.bound_certainty(value), value.get("note")))
        accesses = survey_graph.access_interpretations(graph)
        if not accesses:
            unresolved.append("Primary public access UNRESOLVED: street adjacency does not establish access or building front")
        for access in accesses:
            occurrence = access["occurrence"]
            phrase = "Access %s on edge %s (%s): %s; provenance %s; review evidence %s; access interpretation only, not legal frontage or building-front designation" % (
                occurrence["id"], occurrence["edge_id"], occurrence["street_name"], access["state"], occurrence["provenance"],
                ", ".join((occurrence.get("validated_access") or {}).get("evidence_ids", [])))
            phrase += "; premise " + access["premise_state"]
            for trust in (occurrence.get("validated_access") or {}).get("trust_records", []):
                for edge in trust.get("contradicting_relationships", []):
                    phrase += "; counterevidence relationship %s (%s)" % (edge["relationship_id"], edge["status"])
            (unresolved if access["state"] == "UNRESOLVED" else recovered).append(phrase)
            for name in survey_graph.ACCESS_FEATURES:
                feature = occurrence.get(name) or {}
                if feature.get("value") is not None:
                    partial.append("Access observation %s / %s: %s; read %s; binding %s; provenance %s" % (
                        occurrence["id"], name, feature["value"], feature.get("read_certainty"),
                        binding.bound_certainty(feature), feature.get("note")))
        footprints = graph.get("footprints") or []
        if structures and not footprints:
            unresolved.append("Structure containment UNRESOLVED: no traceable footprint outlines; "
                              + "; ".join(_phrase(o) for o in structures))
        for footprint in footprints:
            containment = survey_graph.footprint_containment(graph, footprint)
            name = footprint.get("label") or footprint.get("id") or "Unidentified structure"
            from services import survey_north
            if survey_north.directional_observation({"key": "structure_label", "value": name}):
                name += " [label as observed; directional reference UNRESOLVED]"
            state = containment["state"]
            provenance = containment["provenance"]
            detail = (" (parcel %s; %s; read %s; binding %s; occurrence %s; boundary %s; source basis: %s)" % (
                containment["subject_identity"], state, containment["read_certainty"],
                containment["bind_certainty"], footprint.get("id"),
                ", ".join(provenance["boundary_segments"]), provenance["identity_basis"] or "unestablished"))
            if state == "INSIDE_SUBJECT_PARCEL":
                recovered.append("Existing building on subject property: " + name + detail)
            elif state == "OUTSIDE_SUBJECT_PARCEL":
                recovered.append("Neighboring context only: " + name + detail)
            else:
                unresolved.append("Structure containment UNRESOLVED: " + name + detail + "; " + containment["reason"])

    # Read the persisted components again; a cached aggregate is not evidence.
    for segment in (visual.get("graph") or {}).get("segments") or []:
        from services import survey_graph
        if segment.get("bearing"):
            bearing = survey_graph._bearing(segment["bearing"])
            partial.append("Printed bearing on %s: %s; parsing %s; reference %s; read %s; binding %s" % (
                segment["id"], segment["bearing"].get("text", ""),
                (bearing or {}).get("parse_state", "UNRESOLVED"),
                (visual.get("graph") or {}).get("bearing_reference", "UNRESOLVED"),
                (bearing or {}).get("read_certainty", "UNRESOLVED"), binding.bound_certainty(bearing)))
        if segment.get("kind") == "arc":
            curve = survey_graph.curve_constraints(segment)
            partial.append("Curve evidence on %s: %s; binding %s; parameters %s" % (
                segment["id"], curve["state"], curve["binding_certainty"],
                "; ".join("%s=%s" % (name, value.get("text") or "UNRESOLVED")
                          for name, value in curve["parameters"].items())))
            unresolved.append("Curve on %s: %s" % (segment["id"], curve["reason"]))
        if segment.get("measurements"):
            from services import survey_graph
            genealogy = survey_graph.measurement_genealogy(segment)
            for measurement in genealogy["history"]:
                partial.append("Measurement premises %s: %s" % (
                    measurement["occurrence_id"], "; ".join(
                        "%s=%s [evidence %s]" % (axis, (measurement.get("validated_premises", {}).get(axis) or {}).get("state", "UNRESOLVED"),
                                                   ", ".join((measurement.get("validated_premises", {}).get(axis) or {}).get("evidence_ids", [])))
                        for axis in survey_graph.MEASUREMENT_PREMISES)))
                partial.append("Measurement evidence %s: %s %s; segment %s; plan %s; date %s; role %s; read %s; binding %s; provenance: %s" % (
                    measurement["occurrence_id"], measurement["text"], measurement["unit"],
                    measurement["segment_id"], measurement["source_plan"], measurement["survey_date"] or "UNRESOLVED",
                    measurement["printed_role"] or "UNRESOLVED", measurement["read_certainty"],
                    binding.bound_certainty(measurement), measurement["provenance"]))
                for premise in measurement.get("validated_premises", {}).values():
                    for trust in premise.get("trust_records", []):
                        for edge in trust.get("contradicting_relationships", []):
                            partial.append("Measurement counterevidence relationship %s (%s); premise %s" % (
                                edge["relationship_id"], edge["status"], premise["state"]))
            current = genealogy["current"]
            if current:
                recovered.append("Current working measurement for %s: %s %s (occurrence %s; authority basis: %s; applicability: %s; precedence: %s)" % (
                    segment["id"], current["text"], current["unit"], current["occurrence_id"],
                    current["authority_basis"], current["applicability_basis"], current["precedence_basis"]))
            else:
                unresolved.append("CURRENT_VALUE = UNRESOLVED for %s: %s" % (segment["id"], genealogy["reason"]))
            if genealogy["discrepancy"]:
                partial.append("Measurement discrepancy for %s: %s; not an established contradiction" % (segment["id"], genealogy["discrepancy"]))
            continue
        dimension = segment.get("dimension") or {}
        if not dimension:
            continue
        target = segment.get("label") or segment.get("id") or "boundary segment"
        certainty = binding.bound_certainty(dimension)
        phrase = "%s: %s (attachment %s; read %s)" % (
            target, dimension.get("text", ""), certainty,
            dimension.get("read_certainty", dimension.get("certainty", "UNRESOLVED")))
        if certainty == vx.RECOVERED:
            recovered.append(phrase)
        elif certainty == vx.PARTIALLY_RECOVERED:
            partial.append(phrase)
        else:
            unresolved.append("Dimension attachment to %s is %s; do not use it as a bound value"
                              % (target, certainty))
    return recovered, partial, unresolved


def _reached_an_interpretation(document) -> bool:
    """Did the examination conclude ANYTHING beyond "here are some characters"?

    Requirements, tables and a completed consistency check are the three things
    that produce a "What GO made of it" line. If none of them happened, nothing
    was interpreted - however many characters came back.
    """
    return bool(getattr(document, "requirements", None)
                or getattr(document, "tables", None)
                or getattr(document, "consistency_checked", False))


def _job_state_for(jobs, workspace_id, source_id):
    """What the PERSISTED job says about this source, or None if there is none.

    Historical containers pre-date the job store entirely; for them there is no
    job and the answer must come from the evidence, exactly as before. A
    missing job is not a pending job.
    """
    if jobs is None:
        return None
    try:
        record = jobs.latest_for_source(workspace_id, source_id)
    except Exception:
        return None
    if record is None:
        return None
    return record.get("state")


def _visual_jobs_beside(jobs):
    """The VISUAL queue that belongs to the same registry as `jobs`.

    CLAUDE-SURVEY-REFERENCE-02. Examination is now TWO stages on two queues -
    OCR on `perception_jobs`, looking on `visual_jobs` - and a page that
    consults only the first reports a finished examination while the second is
    still running. That is what produced the Cassidy window: perception
    completed at 22:10:45, the visual reading at 22:11:13, and in between the
    page asserted conclusions about a reading that had not happened.

    Derived from the store it is handed rather than added as a parameter,
    because every caller already passes the perception store and the two queues
    live in one registry by construction. A caller cannot forget to pass the
    second one, which is exactly the failure this repairs.
    """
    if jobs is None:
        return None
    root = getattr(jobs, "root", None)
    if root is None:
        return None
    try:
        from services import visual_classification

        return visual_classification.visual_store(root.parent)
    except Exception:  # noqa: BLE001 - a missing queue is "no job", not an error
        return None


def examination_stage_states(workspace, source_id, *, jobs=None) -> list:
    """Every examination stage's state for this source, in pipeline order.

    ONE reader for both queues, so "is this source still being examined" has a
    single answer that the state function and the page cannot disagree about.
    """
    workspace_id = getattr(workspace, "project_id", "")
    return [
        _job_state_for(jobs, workspace_id, source_id),
        _job_state_for(_visual_jobs_beside(jobs), workspace_id, source_id),
    ]



def examination_activity(workspace, source_id, *, jobs=None):
    """What is happening to this source RIGHT NOW, or None when nothing is.

    Derived from the same `examination_stage_states` the state function reads,
    so the indicator and the state can never describe different work. Returns
    None the moment both stages are terminal - the caller then shows the
    result, and there is nothing left to animate.
    """
    from services import perception_jobs as pj

    reading, looking = examination_stage_states(workspace, source_id, jobs=jobs)
    open_states = (pj.STATE_QUEUED, pj.STATE_RUNNING)

    if reading == pj.STATE_RUNNING:
        return ACTIVITY_READING
    if reading == pj.STATE_QUEUED:
        return ACTIVITY_QUEUED
    # Reading is terminal (or never existed). If the looking stage is still
    # open, the examination has MOVED ON to it rather than gone back to
    # waiting - which is why this is not simply "queued means queued".
    if looking in open_states:
        return ACTIVITY_LOOKING
    return None


def aggregate_activity(workspace, *, jobs=None):
    """The activity for a whole examination: the EARLIEST stage still open.

    An examination of five photographs is doing the earliest thing any of them
    still needs, because that is what the person is actually waiting for.
    """
    order = [ACTIVITY_QUEUED, ACTIVITY_READING, ACTIVITY_LOOKING]
    seen = [examination_activity(workspace, source["id"], jobs=jobs)
            for source in _live_sources(workspace)]
    for label in order:
        if label in seen:
            return label
    return None


def source_state(document, workspace, source_id, *, jobs=None) -> str:
    """One Source's honest state.

    Job facts outrank evidence facts while a job is open: a source that has not
    been looked at yet must never render as "Read, not interpreted", which
    would be a statement about a reading that has not happened.
    """
    from services import perception_jobs as pj

    # CLAUDE-SURVEY-REFERENCE-02: EVERY stage, not just the first one.
    #
    # Examination is two stages on two queues now. Consulting only perception
    # reported a finished examination while the looking was still queued - the
    # Cassidy window, where the page said "no text could be read" and "no
    # interpretation was reached" twenty-eight seconds before the visual
    # reading named the lot, the plan and both streets.
    #
    # PENDING WINS OVER EVERYTHING, including a failure in the other stage: a
    # source with one stage still running is still being examined, and saying
    # anything else is a claim about work in flight. Queued outranks running
    # for the same reason the aggregate takes the least settled state.
    stages = examination_stage_states(workspace, source_id, jobs=jobs)
    # RUNNING OUTRANKS QUEUED ACROSS STAGES - the opposite of the rule across
    # SOURCES, and the difference is not an inconsistency.
    #
    # `_AGGREGATE_PRECEDENCE` governs several INDEPENDENT sources, where the
    # least settled one is the honest summary: five photographs with two done
    # and three waiting is not "ready". These are SEQUENTIAL STAGES of one
    # source's single examination, and the question a person is asking is "has
    # my document started being looked at". With OCR actively running and the
    # visual stage queued behind it, "Waiting to be examined" would say nothing
    # has begun, which is false and reads as though the upload were stuck.
    #
    # Three pre-existing tests in test_perception_worker_01 assert the user-
    # facing meaning here, and they caught this the first time it was written
    # the other way round.
    if pj.STATE_RUNNING in stages:
        return STATE_PROCESSING
    if pj.STATE_QUEUED in stages:
        return STATE_QUEUED
    # FAILURE IS READ FROM PERCEPTION ONLY, and the asymmetry is deliberate.
    # Pending is a property of EITHER stage - work in flight is work in flight.
    # Failure is not: the visual stage terminates honestly for every file that
    # has no visual representation at all, so letting it force
    # `needs_attention` would put every .txt and .docx in the deployment into a
    # failed-looking state for doing exactly the right thing.
    if stages[0] == pj.STATE_FAILED:
        return STATE_NEEDS_ATTENTION

    # CLAUDE-SURVEY-REFERENCE-01: a VISUAL reading is an interpretation.
    #
    # Checked before the text tests, and that order is the repair. A survey
    # image yields no text and no parsed requirements, so both tests below
    # failed and the source landed on `needs_attention` - "we could not do
    # anything with this" - while a completed visual reading of the same sheet
    # sat in evidence naming the address, the north arrow and the footprint.
    # Whether anything was READ and whether anything was CONCLUDED are
    # different questions, and only the second one decides this state.
    if _visual_established_anything(visual_reading(workspace, source_id)):
        return STATE_RESULT_READY

    recovered = _recovered(workspace, source_id)
    if recovered["passage_count"]:
        return (STATE_RESULT_READY if _reached_an_interpretation(document)
                else STATE_READ_NOT_INTERPRETED)
    if _reached_an_interpretation(document):
        return STATE_RESULT_READY
    return STATE_NEEDS_ATTENTION


def state_of(document, workspace, *, jobs=None) -> str:
    """The job's outcome, derived only from what is actually recorded.

    CLAUDE-DOCUMENT-SHOP-FLOW-01. This used to return "Result ready" the moment
    ANY passage existed. A Product Owner phone photo of a drawing then produced
    a page reading "Result ready - 14,306 characters recovered" beside "No
    interpretation was reached", with pages of OCR noise under a heading that
    said "Some of what was read". Confident gibberish, which is the one thing
    this surface exists not to be.

    The fix is NOT a text-quality score. Measured against real production
    evidence, a word-like-token ratio does not separate noise from signal:
    the pure-noise photo scored 0.434 while a legitimate low-yield scan scored
    0.195 and a clean control 0.636. A threshold there would be invented
    certainty dressed as a measurement.

    So the state is derived from what the records already establish: text came
    back, and nothing was concluded from it.

    IT IS DELIBERATELY NOT CALLED "LIMITED RECOVERY". That was the first
    attempt, and a live proof caught it overclaiming in the opposite direction:
    a clean photograph whose text OCR read perfectly - "FIRE DAMPER SCHEDULE /
    ROOM 101 DETECTOR FD-1" - was labelled Limited recovery and captioned "could
    not be made sense of", which is false. An IMAGE never reaches an
    interpretation at all, because the parser finds no native text in one, so
    that state applies to every image equally and cannot mean the recovery went
    badly.

    "Read, not interpreted" is what actually happened, and it is true of the
    clean photograph and the dense drawing alike. Which of the two a person is
    holding is visible in the recovered text itself, which is shown to them -
    and judging that for them would need the quality score this refuses to
    invent.
    """
    sources = _live_sources(workspace)
    if document is None or not sources:
        return STATE_COULD_NOT_COMPLETE

    # CLAUDE-GO-PERCEPTION-MULTISOURCE-01: an examination holds ONE OR MORE
    # sources, and its state is the LEAST settled among them. Five photographs
    # with two done and three waiting is not "ready" - and one that failed must
    # not erase the four that succeeded, which is why failure is not simply
    # propagated upward either.
    states = [source_state(document, workspace, s["id"], jobs=jobs)
              for s in sources]
    for candidate in _AGGREGATE_PRECEDENCE:
        if candidate in states:
            return candidate
    return STATE_NEEDS_ATTENTION


def _calculated_geometry_lines(workspace, source_id):
    """Project scoped calculation evidence into the existing examination rows.

    Storage is not acceptance. Recompute trust and input-link reviews on every
    read; neither a reviewed link nor a finite number upgrades a refused result.
    Provenance stays on the row for inspection, while conversation's existing
    label/value projection carries only the customer-facing qualification.
    """
    import json
    from flask import current_app
    from services.case_workspace import CaseWorkspaceStore, EVIDENCE_CLASS_CALCULATED_VALUE

    rows = []
    for evidence in getattr(workspace, "evidence_items", []) or []:
        if (evidence.get("source_id") != source_id
                or evidence.get("evidence_class") != EVIDENCE_CLASS_CALCULATED_VALUE
                or evidence.get("content_type") != "application/json"):
            continue
        try:
            record = json.loads(evidence.get("content") or "")
        except (TypeError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        derivation = record.get("derivation") or {}
        if not isinstance(derivation, dict) or derivation.get("operator") not in (
                "numeric_validity@1", "segment_projection@1", "polygon_region@1",
                "semantic_binding@1", "wall_host@1", "vector_usability@1", "bounded_acos@1",
                "homography_point@1"):
            continue
        field = record.get("field")
        label = {"height": "Height", "thickness": "Wall thickness",
                 "projection": "Segment projection", "point": "Point",
                 "endpoint": "Segment endpoint", "polygon": "Polygon",
                 "wall": "Wall placement", "vector": "Direction vector", "domain": "Angle"}.get(field)
        if not label:
            continue
        store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
        governed = store.project_geometry_evidence(workspace, evidence["id"])
        usable = governed["state"] in ("FINITE", "ESTABLISHED") and not governed["errors"]
        qualified = governed["state"] in ("PARTIALLY_RECOVERED", "WEAK")
        text = str(governed["value"]) if usable else label + " could not be established."
        if qualified:
            text += (" The calculation remains uncertain." if governed["state"] == "WEAK"
                     else " The evidence is only partially recovered.")
        rows.append(("interpretation" if usable or qualified else "not_established", {
            "label": label,
            "value": text,
            "evidence_item_id": evidence["id"], "object_id": record.get("object_id"),
            "field": field, "state": governed["state"], "errors": governed["errors"],
            "derivation_record": record, "trust": governed["trust"],
        }))
    return rows


def build_result(document, workspace, *, display_name: str, jobs=None) -> dict[str, Any]:
    """Everything the Document Examination Result page renders.

    Returns plain data, so the template makes no decisions and nothing here
    depends on Flask. The three-way split the record keeps - established from
    the source, GO's reading of it, and what was not established - is built
    here rather than in markup, because it is a claim about evidence.
    """
    from services import source_identity

    sources = _live_sources(workspace)
    source = sources[0] if sources else None
    filename = (source or {}).get("name") or getattr(document, "filename", "") or ""
    # CLAUDE-SURVEY-REFERENCE-01: THE FILE'S TYPE COMES FROM THE FILE.
    #
    # This read `_ext(filename)`, and `filename` is the DISPLAY name - which
    # `document_shop_intake` sets to the work-item name ("226104 1 Castille")
    # after the batch completes, deliberately and correctly. A display name has
    # no suffix, so a JPEG survey reported "Kind of file: a file of type
    # unknown", `is_image` was False so the picture was never shown, and the
    # image branch below was skipped in favour of the "no text layer" sentence
    # the Product Owner reported.
    #
    # `_source_rows` was repaired for exactly this in CLAUDE-DOCUMENT-UPLOAD-01
    # and `build_result` was not - the same condition, in the same file, left
    # live in the second place. That is the carry-through failure this
    # repository's own operating notes describe, and it is why the fix here is
    # the SHARED reader rather than a second copy of the suffix logic.
    identity = source_identity.identify_path(_stored_filename(source or {}))
    ext = identity["extension"] or _ext(filename)
    is_image = source_identity.is_raster_image(identity)
    recovered = _recovered(workspace, source["id"]) if source else {
        "page_count": 0, "passage_count": 0, "character_count": 0,
        "preview": "", "was_recovered": False, "is_direct_source": False,
        "read_by": [],
    }
    visual = visual_reading(workspace, source["id"]) if source else None
    reference = survey_reference_of(workspace, source["id"]) if source else None

    # CLAUDE-SURVEY-REFERENCE-02: THE STATE IS DECIDED BEFORE ANY CONCLUSION
    # IS WRITTEN, because whether the examination has finished governs which
    # conclusions may be written at all.
    #
    # It used to be computed at the END, after `not_established` was already
    # built - so the page assembled "No text could be read" and "No
    # interpretation was reached" and only afterwards discovered it was still
    # queued. `pending` then suppressed the raw-text block and nothing else,
    # which is the half-implemented intent this module's own docstring
    # describes. The Cassidy record showed it: for 49 seconds the page stated
    # three conclusions about a reading that had not happened.
    state = state_of(document, workspace, jobs=jobs)
    pending = state in (STATE_QUEUED, STATE_PROCESSING)


    established: list[dict[str, str]] = []
    interpretation: list[dict[str, str]] = []
    not_established: list[dict[str, str]] = []

    established.append({
        # CLAUDE-DOCUMENT-SHOP-LAYOUT-01: the date, and only the date.
        #
        # This row read "<filename>, received <date>" - two facts under a label
        # that announced neither, so a person scanning for when they uploaded
        # something had to read past the filename to find it. The filename is
        # not lost: it names the Open file action and captions the image.
        "label": "Date",
        "value": (getattr(document, "ingested_at", "") or "")[:10],
    })
    established.append({
        # CLAUDE-DOCUMENT-SHOP-COPY-01: "File type", not "Kind of file".
        # The VALUE and the logic behind it are untouched - this line still
        # answers what the bytes say the file is. "Document" below remains the
        # separate, interpreted classification, and the two stay distinct:
        # "an image (JPEG)" is provenance, "Survey image" is the point.
        "label": "File type",
        # The bytes first, the extension second, and the word "unknown" only
        # when neither says anything at all.
        "value": identity["label"] if identity["media_type"]
        else _MATERIAL_BY_EXT.get(ext, identity["label"]),
    })
    if visual and (visual.get("label") or visual.get("classification")):
        # WHAT THE DOCUMENT IS, as distinct from what the FILE is. "an image
        # (JPEG)" and "Survey image" answer two different questions and a
        # person needs both - the first is provenance, the second is the point.
        established.append({"label": "Document", "value": visual["label"]})
    # CLAUDE-DOCUMENT-SHOP-LAYOUT-02: the checksum row is gone from this
    # surface. THE GUARANTEE IS NOT GONE - `original_file_hash` is still
    # recorded, still verified, and still what the Survey Reference cites as
    # its provenance. It was reassurance written for whoever built the system,
    # printed to someone who wanted to know what their drawing says.

    # CLAUDE-DOCUMENT-SHOP-LAYOUT-02: the passage and character count, and the
    # engine that produced it, are gone from this surface. They measured the
    # EXTRACTION, not the document - "12 passages across 1 page (858
    # characters) - read from the image by Tesseract" tells a person nothing
    # about their survey and a great deal about our pipeline.
    #
    # `recovered` is untouched and still drives everything below, including the
    # honest "nothing has been concluded" line, which is the part of this block
    # that was ever for the customer.
    if recovered["passage_count"]:
        if (not pending and not _reached_an_interpretation(document)
                and not _visual_established_anything(visual)):
            # Said HERE, beside the character count, because the count on its
            # own reads as success. 14,306 characters of nothing is still
            # nothing, and the customer should not have to infer that.
            #
            # CLAUDE-SURVEY-REFERENCE-01 added the second clause, and the real
            # production record is why. The reported Castille survey carries
            # 858 OCR characters AND a visual reading naming the address, the
            # north arrow and the footprint. Without this clause the page would
            # print "Nothing has been concluded" directly beneath a Recovered
            # list - contradicting itself in adjacent sections, which is the
            # same class of defect as the one being repaired.
            not_established.append({
                "label": "Nothing has been concluded from the recovered text",
                "value": (
                    "The text below was read off your file and is shown exactly "
                    "as the engine produced it. Nothing has been worked out from "
                    "it. Photographing a drawing often returns marks and "
                    "fragments as well as words - linework and symbols get read "
                    "as stray characters - so it is shown for you to judge "
                    "rather than summarised for you."
                    if recovered["was_recovered"] else
                    "Text came back, but nothing has been concluded from it."
                ),
            })

    requirements = list(getattr(document, "requirements", None) or [])
    tables = list(getattr(document, "tables", None) or [])
    if requirements:
        interpretation.append({
            "label": "Statements identified",
            "value": "GO picked out %d passage%s that read as obligations or "
                     "requirements. These are GO's reading of the text, not a "
                     "quotation of it." % (len(requirements),
                                           "" if len(requirements) == 1 else "s"),
        })
    if tables:
        interpretation.append({
            "label": "Tables found",
            "value": "%d table%s recognised in the layout." % (
                len(tables), "" if len(tables) == 1 else "s"),
        })

    # CLAUDE-SURVEY-REFERENCE-01: WHAT GO SAW. Slim and factual, in the order
    # the Product Owner's own example gives - recovered, partly recovered,
    # unresolved - and nothing else. No paragraph about how vision works, no
    # explanation of what a certainty state is.
    visual_recovered, visual_partial, visual_unresolved = _visual_lines(visual)
    if source:
        from services.sheet_identity import title_block_readings

        for page in title_block_readings(workspace, source["id"]):
            for key, field in page["fields"].items():
                entry = {"label": "Sheet " + key.replace("_", " "),
                         "value": (str(field["value"]) + " (" + field["certainty"] + ")"
                                   if field["value"] is not None else "UNRESOLVED")}
                (interpretation if field["value"] is not None else not_established).append(entry)
    if visual_recovered:
        interpretation.append({"label": "Recovered",
                               "value": "; ".join(visual_recovered)})
    if visual_partial:
        interpretation.append({"label": "Partially recovered",
                               "value": "; ".join(visual_partial)})

    flags = list(getattr(document, "consistency_flags", None) or [])
    if getattr(document, "consistency_checked", False):
        interpretation.append({
            "label": "Internal consistency",
            "value": ("%d point%s worth a second look." % (
                len(flags), "" if len(flags) == 1 else "s")) if flags
            else "Nothing inconsistent stood out.",
        })
    elif not pending and not visual_recovered and not visual_partial:
        # Said only where there is nothing better to say, and only once the
        # examination has actually finished - "was not checked" is a claim
        # about a completed pass.
        not_established.append({
            "label": "Internal consistency was not checked",
            "value": getattr(document, "consistency_note", None)
            or "This document was not compared against itself for contradictions.",
        })

    if pending:
        # WHILE ANY STAGE IS STILL IN FLIGHT, THE PAGE SAYS ONLY THAT.
        #
        # Product Owner rule, 2026-09-15: no completed-reading conclusion until
        # every required stage is done. Everything below this branch - "No text
        # could be read", "No interpretation was reached", "Nothing was
        # concluded", and even a partial Unresolved list - is a statement about
        # a finished examination. Emitting any of them early is not a cosmetic
        # problem: it tells someone their survey is unreadable while it is
        # being read.
        pass
    elif visual_unresolved:
        # The ONLY not-established line a visually-read document gets, and it
        # names real items rather than describing a missing capability.
        not_established.append({"label": "Unresolved",
                                "value": "; ".join(visual_unresolved)})
    elif visual and not _visual_established_anything(visual):
        not_established.append({
            "label": "Nothing legible was found in this image",
            "value": "GO looked at the picture and could not make out anything "
                     "it would stand behind. Nothing has been guessed.",
        })
    elif not visual:
        # THE OLD BRANCHES, unchanged, for everything that was NOT looked at.
        # They were never wrong about a text document; they were wrong about an
        # image, because an image had no other reading to report.
        if is_image and not recovered["passage_count"]:
            not_established.append({
                "label": "No text could be read from this image",
                "value": "An image carries no text of its own, and the text-recognition "
                         "step did not recover any. The picture itself is kept and can "
                         "be viewed below.",
            })
        elif getattr(document, "text_extraction_status", "") == "no_native_text":
            not_established.append({
                "label": "This file has no text layer",
                "value": "It appears to be a scan or picture rather than a document with "
                         "selectable text, so there was nothing to read directly.",
            })
        elif not recovered["passage_count"] and not requirements:
            not_established.append({
                "label": "Nothing was recovered from this file",
                "value": "The file was received and stored, but no readable content came "
                         "out of it.",
            })

    if not pending and not interpretation and not recovered["passage_count"] and not visual:
        # Only when there is genuinely nothing, which now includes "and nobody
        # looked". A visually-examined source has already said what it found or
        # that it found nothing, and this line would contradict the first and
        # repeat the second.
        not_established.append({
            "label": "No interpretation was reached",
            "value": "There was not enough recovered content for GO to say what this "
                     "document requires or describes.",
        })

    # `state` and `pending` were resolved above, before any conclusion was
    # written; recomputing here would re-read both queues for the same answer.
    # CLAUDE-DOCUMENT-SHOP-FLOW-01: a photograph of a drawing yields marks and
    # fragments, not sentences. When nothing was concluded from them, the page
    # must present them AS fragments - the old heading "Some of what was read"
    # framed pages of OCR noise as a reading, which is what made a working
    # examination read as gibberish.
    #
    # CLAUDE-SURVEY-REFERENCE-01: asked of THE RECOVERED TEXT, not of the
    # aggregate state, and the distinction is load-bearing. Reading it off the
    # state meant a successful VISUAL reading flipped the state to
    # `result_ready` and so re-framed the same 858 characters of OCR noise as
    # "Some of what was read" - reintroducing the exact defect the line above
    # describes. Seeing the north arrow concludes nothing about the characters.
    fragmentary = bool(recovered["passage_count"]) and not _reached_an_interpretation(document)
    # CLAUDE-MUSCLE-F5-01: sheets this package declared and did not deliver.
    #
    # `register_sheet_index` has computed this since CLAUDE-SHEET-IDENTITY-
    # WIRING-01, and `perception_worker` reduces it to a COUNT in a log line.
    # The capability existed and had no door - the fourth time that pattern has
    # appeared here. Each absence is stated and nothing is inferred about what
    # the missing sheet would have shown.
    try:
        from services import sheet_identity

        missing_sheets = [entry for package_source in _live_sources(workspace)
                          for entry in sheet_identity.declared_but_absent(
                              workspace, package_source["id"])] if workspace else []
    except Exception:  # noqa: BLE001 - a manifest check never fails a result
        missing_sheets = []
    for entry in missing_sheets:
        not_established.append({
            "label": "Missing evidence: " + entry["reference_text"],
            "value": entry["statement"],
        })

    if source and not pending:
        for group, entry in _calculated_geometry_lines(workspace, source["id"]):
            (interpretation if group == "interpretation" else not_established).append(entry)

    return {
        "name": display_name,
        "fragmentary": fragmentary,
        "state": state,
        "state_label": STATE_LABELS[state],
        "filename": filename,
        "received_at": getattr(document, "ingested_at", "") or "",
        "source_id": (source or {}).get("id"),
        "is_image": is_image,
        "established": established,
        "interpretation": interpretation,
        "not_established": not_established,
        "preview_text": recovered["preview"],
        "sources": _source_rows(document, workspace, jobs=jobs),
        # While anything is still queued or running, the page must not present
        # the raw-text block or the "nothing was concluded" grammar: both are
        # statements about a completed reading.
        "pending": pending,
        # CLAUDE-EXAMINATION-ACTIVITY-01: what to animate, and what to say
        # while animating. None once nothing is running.
        "activity": aggregate_activity(workspace, jobs=jobs) if pending else None,
        # CLAUDE-SURVEY-REFERENCE-01: the derived artifact, if one was built.
        # `reference_source_id` is what the download link needs; the rest is
        # what the page says about it, which is deliberately three words.
        "survey_reference": _reference_view(reference,
                                            source_id=(source or {}).get("id")),
        "visual_ran": bool(visual),
    }


def _reference_view(reference, *, source_id=None) -> Optional[dict[str, Any]]:
    """What the result page shows about a Survey Reference: that there is one,
    what it is, and how to open it. Not its contents - those are already the
    Recovered / Partially recovered / Unresolved lines above, and printing them
    twice is how a slim page stops being slim."""
    if not reference:
        return None
    from services import survey_reference as sr

    # CLAUDE-SURVEY-REFERENCE-02: the review drawing, as inline SVG.
    #
    # THE SAME PRIMITIVES THE PDF IS DRAWN FROM. `sr.review_svg` resolves the
    # stored graph through the one resolver the exported sheet uses, so the
    # drawing a person compares against their photograph is the reconstruction
    # itself - not a second rendering that could agree with the PDF today and
    # drift from it tomorrow.
    try:
        svg = sr.review_svg(reference)
        stats = sr.resolved_plan(reference)["stats"]
    except Exception:  # noqa: BLE001 - a review drawing is never worth a 500
        svg, stats = "", {}

    # CLAUDE-SURVEY-REFERENCE-REPAIR-01: AN EMPTY FRAME IS NOT A DRAWING.
    #
    # This shipped and reached production, and the Product Owner saw the
    # result: a blank white panel beside their survey photograph. The cause is
    # that `review_svg` is honest and the GUARD WAS NOT. A graph with no nodes
    # and no segments resolves to a valid SVG containing only its own border -
    # 227 bytes on the live record - and the template asked `{% if plan_svg %}`,
    # which a 227-byte string passes. The page then promised a comparison and
    # showed an empty box.
    #
    # The guard now asks what the drawing CONTAINS, not whether a string was
    # produced. Nothing drawn, nothing shown, and `plan_empty` lets the page
    # say why instead of leaving a hole where a promise was.
    drawn = sum(int(stats.get(key) or 0)
                for key in ("straights", "arcs", "footprints"))
    if not drawn:
        svg = ""

    return {
        "title": reference.get("title") or "Survey Reference",
        "source_note": reference.get("source_note") or "",
        "source_id": reference.get("derived_source_id"),
        "filename": reference.get("artifact_filename") or "",
        "sha256": reference.get("artifact_sha256") or "",
        "generated_at": reference.get("generated_at") or "",
        # The side-by-side needs the ORIGINAL's source id too, so the photo can
        # be shown beside the reconstruction at the same size.
        "original_source_id": source_id,
        "plan_svg": svg,
        # True when a Survey Reference exists but nothing could be drawn from
        # it - the honest state the blank panel was hiding.
        "plan_empty": not svg,
        "stats": stats,
        "withheld": [entry["label"] for entry in (reference.get("withheld") or [])],
        "unresolved": list(reference.get("unresolved") or []),
    }


def _source_rows(document, workspace, *, jobs=None) -> list[dict[str, Any]]:
    """One row per Source, in the order the CUSTOMER chose.

    intake_order when the record states one; list position otherwise, which is
    what every container created before that field existed has. Never a
    filename, never a completion time, never a UUID.
    """
    rows = []
    for index, source in enumerate(_live_sources(workspace)):
        recovered = _recovered(workspace, source["id"])
        state = source_state(document, workspace, source["id"], jobs=jobs)
        order = source.get("intake_order")
        rows.append({
            "source_id": source["id"],
            "name": source.get("name") or "",
            "order": index if order is None else order,
            "state": state,
            "state_label": STATE_LABELS[state],
            # CLAUDE-DOCUMENT-UPLOAD-01: the STORED FILE's own name, not the
            # display name. `Source.name` was the filename for every source
            # this row has ever described, so reading a suffix off it worked by
            # coincidence rather than by design - and the coincidence ended the
            # moment a work-item name became the display name. A photo whose
            # display name is "SRPC Drawing Review 2" is still a photo.
            "is_image": _ext(_stored_filename(source)) in _IMAGE_EXTS,
            # CLAUDE-SURVEY-REFERENCE-01: per-source, so a batch where one
            # photo was looked at and one was not says so per row rather than
            # taking the whole examination's word for it.
            "visual_ran": bool(visual_reading(workspace, source["id"])),
            "passage_count": recovered["passage_count"],
            "character_count": recovered["character_count"],
            "read_by": recovered["read_by"],
            "preview": recovered["preview"],
            "pending": state in (STATE_QUEUED, STATE_PROCESSING),
        })
    rows.sort(key=lambda r: r["order"])
    return rows


def summarise_job(document, workspace, *, display_name: str,
                  project_id: str, jobs=None) -> dict[str, Any]:
    """One row in My Documents. Same state function as the result page uses,
    so a listing can never disagree with the page it links to."""
    sources = _live_sources(workspace)
    state = state_of(document, workspace, jobs=jobs)
    first: Optional[dict] = sources[0] if sources else None
    per_source = [source_state(document, workspace, s["id"], jobs=jobs)
                  for s in sources]
    settled = len([x for x in per_source
                   if x not in (STATE_QUEUED, STATE_PROCESSING)])
    return {
        "project_id": project_id,
        "name": display_name,
        "added_at": getattr(document, "ingested_at", "") or "",
        "source_count": len(sources),
        "first_source_id": (first or {}).get("id"),
        "state": state,
        "state_label": STATE_LABELS[state],
        # "Processing 2 of 5" - real counts from real job records, never a
        # progress bar animating over nothing.
        "settled_count": settled,
        "pending_count": len(sources) - settled,
    }
