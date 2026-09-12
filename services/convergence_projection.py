"""Cognitive Gym plugin read-model adapter. No application writes or execution.

Schema-specific evidence projection, not a capability/status authority. The caller
supplies the existing bounded Reader; raw requests, tools and assessment stimuli
are never read. Narrative frontiers remain narrative, not invented matrix points.
"""
import hashlib
import json
import re

UNRESOLVED = "UNRESOLVED"
SCHEMA = 1
FIELDS = (
    "record_family record_id capability actor application_capability task_kind "
    "control_type task_content_result contract_compliance instrument_validity "
    "application_defect governance_boundary model_baseline handoff_reference "
    "application_frontier_state go_development_frontier_state shared_frontier_state "
    "gap_owner timestamp evidence_refs qualitative_band unresolved_fields"
).split()
MARKERS = ("development-record.json", "frontier-ledgers.json", "stage-checkpoints.json")


def discover(root):
    """Also discover explicitly marked blocks outside historical name prefixes."""
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink()
                  and ("COGNITIVE-GYM" in p.name or any(
                      (p / "records" / name).is_file() for name in MARKERS)))


def attribution(field, documents, folder=""):
    values, supplied = set(), False
    for data in documents:
        if not isinstance(data, dict) or field not in data:
            continue
        supplied = True
        value = data[field]
        if field == "actor":
            value = {"GO": "GO", "GOTEX": "GOtex", "GOtex": "GOtex",
                     "GO_CHEAT_SHEET": "GO", "GO TEACHING": "GO", "GO_TEACHING": "GO",
                     "EVALUATOR": "EVALUATOR", "APPLICATION / INSTRUMENT":
                     "APPLICATION / INSTRUMENT"}.get(str(value), UNRESOLVED)
        elif not isinstance(value, str) or not re.fullmatch(r"C(?:0[1-9]|1[0-9]|2[0-8])", value):
            value = UNRESOLVED
        values.add(value)
    if supplied:
        return (next(iter(values)), "explicit") if len(values) == 1 else (UNRESOLVED, "conflicting explicit attribution")
    if field == "capability":
        match = re.search(r"(?:^|-)C(0[1-9]|1[0-9]|2[0-8])(?:-|$)", folder)
        if match:
            return "C" + match[1], "legacy directory association; no explicit capability"
    return UNRESOLVED, "no explicit attribution"


def family(path):
    name = path.name.lower()
    if name == "frontier-ledgers.json":
        return "FRONTIER"
    if "handoff" in name:
        return "HANDOFF"
    if "specimen" in name or name in {"approval-gate-presented.json", "acquisition-history.json"}:
        return "SPECIMEN"
    if "qualification" in name or name == "preflight.json":
        return "QUALIFICATION"
    if name in ("final-results.json", "release-manifest.json"):
        return "QUALIFICATION" if "QUALIFICATION" in str(path.parent.parent) else "DEVELOPMENT_SUMMARY"
    if "stop" in name or name in {"termination.json", "authority-boundary.json"}:
        return "STOPPED"
    if "seal" in name:
        return "SEAL"
    if name == "assessment-record.json":
        return "ASSESSMENT"
    if name == "transfer-record.json":
        return "TRANSFER"
    if "closeout" in name or name == "stage-checkpoints.json":
        return "STAGE_CLOSEOUT"
    if "instrument" in name or "contract-verification" in name or name == "teaching-review.json":
        return "INSTRUMENT_FINDING"
    if "observation" in name or name == "claude-behavioral-feedback.json":
        return "OBSERVATION"
    if name == "intervention-record.json":
        return "APPRENTICESHIP"
    if name.endswith("-result.json") or name.endswith("-complete.json"):
        return "ENCOUNTER"
    if "development-record" in name or name == "cycle-results.json":
        return "DEVELOPMENT_SUMMARY"
    if "next-developmental-move" in name:
        return "ADAPTIVE_DECISION"
    return None


def linked_actor(data, intervention, audit=()):
    """Match action by audited request identity AND raw hash, never raw equality alone."""
    raw = data.get("raw")
    if not isinstance(raw, str):
        return []
    digest = hashlib.sha256(raw.encode()).hexdigest()
    request_ids = {data["request_id"]} if isinstance(data.get("request_id"), str) else set()
    if isinstance(audit, list):
        request_ids.update(a["request_id"] for a in audit if isinstance(a, dict) and
                           a.get("phase") == data.get("phase") and isinstance(a.get("request_id"), str))
    if len(request_ids) != 1:
        return []
    return [a for key in ("GOtex_action", "teacher_action")
            if isinstance((a := intervention.get(key)), dict) and
            a.get("request_id") in request_ids and a.get("raw") == raw and
            a.get("raw_sha256") == digest and "actor" in a]


def scrub(value, clean):
    if isinstance(value, dict):
        return {str(k): scrub(v, clean) for k, v in value.items()
                if not re.search(r"password|secret|api_key|authorization", str(k), re.I)}
    if isinstance(value, list):
        return [scrub(v, clean) for v in value]
    return clean(value) if isinstance(value, str) else value


def explicit_time(*documents):
    for data in documents:
        for key in ("timestamp", "timestamp_utc", "created_utc", "reviewed_utc", "created_at"):
            value = data.get(key)
            if isinstance(value, str):
                return value
    return UNRESOLVED


def contract(data, observation):
    text = str(observation.get("contract_compliance", observation.get("response_contract_compliance",
               data.get("contract_compliance", "")))).upper()
    if data.get("execution_valid") is False or any(x in text for x in ("FAILURE", "INVALID", "TRUNCAT")):
        return "INVALID"
    if text in ("PROSE TEACHING MODE", "NOT_APPLICABLE"):
        return "NOT_APPLICABLE"
    if text in ("CONTRACT-COMPLIANT", "VALID") or data.get("execution_valid") is True:
        return "VALID"
    return UNRESOLVED


def controls(material):
    if material.get("target_present") is False or ("target" in material and material["target"] is None
                                                  and material.get("options")):
        return "NULL_TARGET"
    value = str(material.get("control_type", material.get("control", ""))).upper()
    return {"POSITIVE": "POSITIVE_CONTROL", "POSITIVE_CONTROL": "POSITIVE_CONTROL",
            "NEGATIVE": "NEGATIVE_CONTROL", "NEGATIVE_CONTROL": "NEGATIVE_CONTROL",
            "NULL_TARGET": "NULL_TARGET", "TRANSFER": "TRANSFER", "OTHER": "OTHER"}.get(
                value, "POSITIVE_CONTROL" if material.get("target_present") is True else UNRESOLVED)


def normalize(reader, path, data, clean, *, folder, context=None):
    context = context or {}
    kind = family(path) or "UNMAPPED"
    if path.name == "development-record.json" and "raw_response" in data:
        kind = "ENCOUNTER"
    phase = data.get("phase", path.stem.removesuffix("-result").removesuffix("-complete"))
    safe_phase = isinstance(phase, str) and re.fullmatch(r"[A-Za-z0-9_-]+", phase)
    material_path = folder / "records" / (phase + "-material.json") if safe_phase else None
    observation_path = folder / "records" / (phase + "-observation.json") if safe_phase else None
    material = reader.get(material_path) if material_path else {}
    observation = reader.get(observation_path) if observation_path and observation_path != path else {}
    dispatch_path = folder / "records" / (phase + "-dispatch.json") if safe_phase else None
    dispatch = reader.get(dispatch_path) if dispatch_path else {}
    if not dispatch and safe_phase:
        dispatch_path = folder / "examiner" / (phase + "-started.json")
        dispatch = reader.get(dispatch_path)
    provenance_path = folder / "records" / (phase + "-provenance.json") if safe_phase else None
    provenance = reader.get(provenance_path) if provenance_path else {}
    docs = [data, material, observation]
    intervention_path = folder / "examiner" / "intervention-record.json"
    audit_path = folder / "examiner" / "cycle-results.json"
    links = linked_actor(data, reader.get(intervention_path), reader.get(audit_path).get("audit", [])) if kind == "ENCOUNTER" else []
    capability, cap_basis = attribution("capability", docs, folder.name)
    actor, actor_basis = attribution("actor", docs + links)
    if actor == UNRESOLVED and actor_basis == "no explicit attribution" and kind != "ENCOUNTER":
        actor, actor_basis = "EVALUATOR", "record is an evaluator summary, not a model encounter"
    value = {key: UNRESOLVED for key in FIELDS}
    value.update(record_family=kind, record_id=path.relative_to(reader.root).as_posix(),
                 capability=capability, actor=actor, timestamp=explicit_time(dispatch, data),
                 attribution_basis={"capability": cap_basis, "actor": actor_basis})
    value["contract_compliance"] = contract(data, observation) if kind == "ENCOUNTER" else "NOT_APPLICABLE"
    value["control_type"] = controls(material)
    value["task_kind"] = "TEACHING" if any(d.get("actor") in ("GO_CHEAT_SHEET", "GO TEACHING", "GO_TEACHING") for d in docs + links) else data.get("mode", context.get("mode", UNRESOLVED))
    if "QUALIFICATION" in folder.name or kind == "QUALIFICATION":
        value["task_kind"] = "QUALIFICATION"
    content = observation.get("task_content", data.get("task_content", data.get("observation", data.get("observed", UNRESOLVED))))
    scoring = observation.get("task_alignment", observation.get("task_scoring", data.get("task_scoring")))
    value["task_content_result"] = {"observation": content, "scoring": "UNSCORED" if
        value["contract_compliance"] == "INVALID" or scoring == "UNSCORED" else scoring or UNRESOLVED,
        "target_alignment": None if value["contract_compliance"] == "INVALID" else data.get("target_alignment", data.get("target_aligned"))}
    value["application_defect"] = observation.get("application_defect", data.get("application_defect", data.get("instrument_application_defect", UNRESOLVED)))
    instrument = observation.get("instrument_validity", data.get("instrument_validity"))
    value["instrument_evidence"] = instrument or UNRESOLVED
    # Do not turn a malformed model response into an application/delivery defect.
    if instrument in ("VALID", "INVALID", "INDETERMINATE"):
        value["instrument_validity"] = instrument
    elif isinstance(instrument, dict) and all(instrument.get(k) is True for k in ("material_reviewed", "exact_wire", "model_match", "cold_context")):
        value["instrument_validity"] = "VALID"
    elif instrument:
        value["instrument_validity"] = "INDETERMINATE"
    value["model_baseline"] = data.get("model", context.get("model", UNRESOLVED))
    value["application_capability"] = material.get("application_capability", data.get("application_capability",
        provenance.get("read_surfaces", data.get("read_surface", UNRESOLVED))))
    value["handoff_reference"] = data.get("handoff_reference", data.get("handoffs_used",
        provenance.get("handoffs", provenance.get("handoff", UNRESOLVED))))
    value["governance_boundary"] = data.get("governance_boundary", data.get("condition", UNRESOLVED))
    value["gap_owner"] = data.get("gap_owner", data.get("GAP_OWNER", UNRESOLVED))
    for field, source in (("application_frontier_state", "CLAUDE_APPLICATION_FRONTIER"),
                          ("go_development_frontier_state", "GO_DEVELOPMENT_FRONTIER")):
        value[field] = data.get(field, data.get(source, UNRESOLVED))
    value["shared_frontier_evidence"] = data.get("SHARED_OPERATIONAL_FRONTIER", UNRESOLVED)
    value["application_frontier_state"] = data.get("application_frontier_state", value["application_frontier_state"])
    value["go_development_frontier_state"] = data.get("go_development_frontier_state", value["go_development_frontier_state"])
    value["raw_response"] = data.get("raw", data.get("raw_response", ""))
    value["qualitative_band"] = UNRESOLVED
    value["band_reason"] = "No governed operation-level band with supporting evidence; positive observations alone do not establish readiness."
    if value["contract_compliance"] == "INVALID":
        value.update(shared_frontier_state="BLOCKED_BY_INSTRUMENT", qualitative_band="BLOCKED",
                     band_reason="This observation cannot support operational readiness: response contract invalid; task scoring remains separate.")
    elif value["control_type"] in ("NEGATIVE_CONTROL", "NULL_TARGET") and value["task_content_result"]["target_alignment"] is False:
        value.update(shared_frontier_state="BLOCKED_BY_NEGATIVE_CONTROL", qualitative_band="FRAGILE",
                     band_reason="This valid negative/null observation is explicitly recorded as not target-aligned; no capability-wide score inferred.")
    if kind == "STOPPED" and data.get("condition") == "REPEATED INSTRUMENT FAILURE PREVENTS VALID NEGATIVE-CONTROL OBSERVATION":
        value.update(shared_frontier_state="BLOCKED_BY_INSTRUMENT", qualitative_band="BLOCKED",
                     band_reason="Explicit recorded termination: " + data["condition"])
    value["operator_risks"] = []
    # Only an examiner's explicit observation supports a risk label; never diagnose raw model prose.
    prose = str(content).lower()
    if ("compound" in prose or "visible prose" in prose or "visible output" in prose) and (
            "neither" in prose or "both claims unsupported" in prose or "both options" in prose):
        value["operator_risks"] = [{"kind": "PREMATURE COMMITMENT", "basis": content,
                                    "scope": "Recorded content/form pattern; cognitive scoring unchanged"}]
    value["details"] = {k: data[k] for k in (
        "status", "outcome", "observed", "not_established", "does_not_establish", "limits", "stage_closeout",
        "c01_status", "stages", "next_move", "next_target", "next_target_recommendation", "CURRENT_GAP",
        "NEXT_ACTION", "condition", "detail", "stop", "interpretation", "current_frontier_excerpt",
        "baseline_excerpt", "read_surface", "current_source_ids", "copy_hashes", "supersession",
        "verdicts", "overall", "scope", "failure", "limitations", "causal_effect_established") if k in data}
    if kind == "STAGE_CLOSEOUT" and path.name == "stage-checkpoints.json":
        value["details"]["capability_checkpoints"] = data
    refs = [path, material_path, observation_path, dispatch_path, provenance_path,
            folder / "records" / "plan.json", folder / "examiner" / "config.json"] + ([intervention_path, audit_path] if links else [])
    value["evidence_refs"] = [{"path": p.relative_to(reader.root).as_posix(),
                               "sha256": reader.refs[p.relative_to(reader.root).as_posix()]}
                              for p in refs if p is not None and p.relative_to(reader.root).as_posix() in reader.refs]
    value["evidence_refs"] = list({r["path"]: r for r in value["evidence_refs"]}.values())
    value["unresolved_fields"] = [k for k in FIELDS if value[k] == UNRESOLVED]
    return scrub(value, clean)


def project(reader, clean):
    records, inventory = [], []
    for folder in discover(reader.root):
        context = reader.get(folder / "records" / "plan.json") or reader.get(folder / "examiner" / "config.json")
        paths = sorted(set(folder.glob("*.json")) | set((folder / "records").glob("*.json")) |
                       set((folder / "examiner").glob("*.json")))
        for path in paths:
            kind = family(path)
            if not kind:
                continue
            # Never inspect qualification answer keys/stimuli; summaries and seals only.
            data = reader.get(path)
            inventory.append({"path": path.relative_to(reader.root).as_posix(), "record_family": kind,
                              "readable": bool(data)})
            if data:
                records.append(normalize(reader, path, data, clean, folder=folder, context=context))
    records.sort(key=lambda r: r["record_id"])
    frontiers = [r for r in records if r["record_family"] == "FRONTIER"]
    blockers = []
    if not frontiers:
        blockers.append("No explicit frontier record available.")
    if any(not isinstance(r["application_frontier_state"], str) or
           r["application_frontier_state"] not in ("UNAVAILABLE", "EXPERIMENTAL", "REACHABLE", "STABLE") or
           not isinstance(r["go_development_frontier_state"], str) or
           r["go_development_frontier_state"] not in ("UNTESTED", "DEVELOPING", "CONDITIONALLY READY", "RELIABLE FOR THIS OPERATION")
           for r in frontiers):
        blockers.append("Frontier evidence is narrative or incomplete: operation-level application stability / GO readiness coordinates are unresolved.")
    if any(r["application_capability"] == UNRESOLVED or r["shared_frontier_state"] == UNRESOLVED for r in frontiers):
        blockers.append("Frontier records lack an explicit operation mapping and evidence-supported shared-state classification; no health interpretation is inferred.")
    if reader.issues:
        blockers.append("Unreadable or unsupported source records require review.")
    if any(r["record_family"] == "ENCOUNTER" and (r["actor"] == UNRESOLVED or r["capability"] == UNRESOLVED) for r in records):
        blockers.append("Some encounters lack unambiguous capability/actor attribution; unresolved records remain visible and are not assigned to C01 or GO.")
    payload = {"schema": SCHEMA, "records": records, "inventory": inventory,
               "authority": "DERIVED READ-ONLY PROJECTION", "health_eligible": not blockers,
               "health_blockers": blockers,
               "band_policy": {"supported": ["BLOCKED", "FRAGILE", "UNRESOLVED"],
                               "reserved_without_governed_evidence": ["EXCELLENT", "GOOD", "ADEQUATE", "POOR", "UNTESTED"],
                               "scope": "Per-observation evidence label; not capability status or promotion"}}
    payload["projection_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                                            separators=(",", ":")).encode()).hexdigest()
    return payload
