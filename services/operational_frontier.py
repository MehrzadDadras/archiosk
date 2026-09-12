"""Operation/evidence rules, separate from Gym status and core application truth.

Evidence inputs are assertions with source references, not scores. Acceptance is
explicit and operation-scoped; a count of passes never creates readiness.
"""
import hashlib
import json
import re
from pathlib import Path

U = "UNRESOLVED"
VERSION = "operation-evidence-2"


def classify(facts):
    """Pure categorical rules. Unknowns are not false, and conflicts are not votes."""
    reasons = []
    if not facts.get("capability_id") or facts.get("known_capability") is not True or facts.get("conflicts"):
        return {"application_state": U, "go_state": U, "shared_state": U,
                "gap_owner": U, "qualitative_band": U,
                "why_this_band": "Unknown operation or conflicting evidence; no conclusion selected.",
                "unresolved_reasons": facts.get("conflicts") or ["Unknown capability identifier"]}
    app = facts.get("application", {})
    # Explicit stable handoff is sufficient only within its stated scope and
    # in the absence of an invalidating blocker or contradictory evidence.
    if app.get("invalidating_blocker") is True:
        application = "REACHABLE" if app.get("reachable") is True else "EXPERIMENTAL"
    elif app.get("stable") is True or app.get("stable_handoff") is True or all(app.get(k) is True for k in (
            "implemented", "tested", "deployment_satisfied", "corpus_proof_satisfied", "no_invalidating_blocker")):
        application = "STABLE"
    elif app.get("reachable") is True:
        application = "REACHABLE"
    elif app.get("implemented") is True:
        application = "EXPERIMENTAL"
    elif app.get("implemented") is False and app.get("search_scope"):
        application = "UNAVAILABLE"
        reasons.append("Unavailable only within the recorded implementation search scope.")
    else:
        application = U
        reasons.append("Implementation/reachability not established for this operation.")

    observations = facts.get("observations", [])
    if any(o.get("valid") is None for o in observations):
        reasons.append("Some observations lack mapped instrument/model validity; they do not count as usable controls.")
    positives = [o for o in observations if o.get("control") == "POSITIVE_CONTROL" and o.get("valid") is True and o.get("aligned") is True]
    negatives = [o for o in observations if o.get("control") in ("NEGATIVE_CONTROL", "NULL_TARGET")]
    negative_fail = any(o.get("valid") is True and o.get("aligned") is False for o in negatives)
    negative_invalid = any(o.get("valid") is False for o in negatives)
    negative_pass = any(o.get("valid") is True and o.get("aligned") is True for o in negatives)
    requirement = facts.get("negative_requirement", U)
    negative_ok = requirement == "NOT_REQUIRED" and bool(facts.get("negative_requirement_ref"))
    if requirement == "REQUIRED":
        negative_ok = negative_pass and not negative_fail and not negative_invalid
    acceptance = facts.get("acceptance", {})
    accepted = (acceptance.get("authorized") is True and acceptance.get("capability_id") == facts["capability_id"]
                and bool(acceptance.get("evidence_ref")) and acceptance.get("scope")
                and acceptance.get("model_baseline") == facts.get("model_baseline")
                and facts.get("model_baseline") not in (None, U))
    if positives and negative_ok and accepted and acceptance.get("level") in ("CONDITIONALLY READY", "RELIABLE FOR THIS OPERATION"):
        go = acceptance["level"]
    elif observations:
        go = "DEVELOPING"
        if not accepted:
            reasons.append("No applicable scoped operational acceptance; development/stage closure is not readiness.")
    else:
        go = "UNTESTED"
    governance = facts.get("governance_state", U)
    ready = go in ("CONDITIONALLY READY", "RELIABLE FOR THIS OPERATION")
    # Precedence is explicit. Bad model JSON alone is NOT an invalid instrument.
    if facts.get("instrument_invalid") is True:
        shared, owner, band = "BLOCKED_BY_INSTRUMENT", "CODEX", "BLOCKED"
        why = "An explicit instrument-validity failure prevents a usable observation."
    elif governance in ("UNRESOLVED", "DENIED", "PENDING_PRODUCT_OWNER") and (ready or facts.get("governance_blocker") is True):
        shared, owner, band = "BLOCKED_BY_GOVERNANCE", ("PRODUCT_OWNER" if governance == "PENDING_PRODUCT_OWNER" else "GOVERNANCE"), "BLOCKED"
        why = "An explicit authority/acceptance boundary blocks the scoped operation."
    elif positives and requirement == "REQUIRED" and not negative_ok:
        shared, owner = "BLOCKED_BY_NEGATIVE_CONTROL", "CODEX"
        band = "FRAGILE" if negative_fail else "BLOCKED"
        why = "Positive behavior exists, but required negative evidence is failed, invalid/unscored or absent."
        if application != "STABLE":
            owner = "SHARED / MULTIPLE"
    elif app.get("trainable") is False:
        shared, owner, band = "IMMATURE", facts.get("training_gap_owner", U), "UNTESTED" if go == "UNTESTED" else "BLOCKED"
        why = "Application component evidence does not establish a trainable end-to-end path: " + facts.get("training_boundary", "Explicitly outside safe training frontier.")
    elif application == "STABLE" and ready and governance == "PERMITTED":
        shared, owner, band = "SHARED_FRONTIER", U, U
        why = "Scoped shared use is evidenced; no separate higher performance-band rubric is authorized."
    elif application == "STABLE":
        shared, owner, band = "APPLICATION_AHEAD", "CODEX", ("UNTESTED" if go == "UNTESTED" else U)
        why = "Stable application capability exceeds demonstrated/accepted GO readiness."
    elif ready and application in ("UNAVAILABLE", "EXPERIMENTAL", "REACHABLE"):
        shared, owner, band = "GO_AHEAD", "CLAUDE", U
        why = "Scoped GO behavior is accepted, but the required application capability is not stable."
    elif application in ("EXPERIMENTAL", "REACHABLE", "UNAVAILABLE"):
        shared, owner, band = "IMMATURE", "SHARED / MULTIPLE", ("UNTESTED" if go == "UNTESTED" else U)
        why = "Application stability and GO readiness do not jointly support operational use."
    else:
        shared, owner, band, why = U, U, U, "Missing application evidence prevents a shared-state conclusion."
    return {"application_state": application, "go_state": go, "shared_state": shared,
            "gap_owner": owner, "qualitative_band": band, "why_this_band": why,
            "positive_control_state": "OBSERVED_ALIGNED" if positives else "NOT_ESTABLISHED",
            "negative_control_state": "FAILED_VALID" if negative_fail else "INVALID_UNSCORED" if negative_invalid else "OBSERVED_ALIGNED" if negative_pass else "NOT_REQUIRED" if negative_ok else "NOT_ESTABLISHED",
            "negative_control_findings": [label for label, present in (("FAILED_VALID", negative_fail), ("INVALID_UNSCORED", negative_invalid), ("OBSERVED_ALIGNED", negative_pass)) if present],
            "unresolved_reasons": reasons}


def _slug(name):
    return "op." + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _ref(path, text, excerpt):
    return {"path": str(path), "sha256": hashlib.sha256(text.encode()).hexdigest(), "excerpt": excerpt}


def handoff_catalog(repo):
    """Read the explicitly headed handoff tables, not every READY word in a log."""
    path = Path(repo) / "CONTINUATION_CHECKPOINT.md"
    text = path.read_bytes().decode("utf-8")
    heading = "### Capability handoff baseline"
    start = text.find(heading)
    end = text.find("### Lane discipline", start)
    if start < 0 or end < 0:
        return [], {"active": U, "stable_handoff": U, "conflicts": ["Handoff table section missing"]}
    section = text[start:end]
    operations = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("|") or len(cells) not in (3, 4) or cells[0] in ("Capability", "---"):
            continue
        if not cells[1].startswith("**"):
            continue
        operations.append({"capability_id": _slug(cells[0]), "capability_name": cells[0],
                           "application": {"stable_handoff": cells[1].startswith("**READY")},
                           "safe_for_training": cells[1].startswith("**READY"),
                           "evidence_refs": [_ref("CONTINUATION_CHECKPOINT.md", text, line)],
                           "scope": cells[2:], "source_priority": "Explicit capability handoff table; later explicit promotions supersede this historical baseline only for their named operation."})
    # Later named promotions, not deployment/commit existence, advance safe use.
    promotions = re.findall(r"\*\*CODEX SAFE TRAINING FRONTIER:\*\*\s*`([^`]+)`", text)
    for handoff, name in (("CLAUDE-GO-PERCEPTION-LEGEND-SLICE-01", "Legend entry slicing"),
                          ("CLAUDE-GO-PERCEPTION-PDF-OCR-01", "PDF positioned evidence"),
                          ("CLAUDE-GO-PERCEPTION-WORKING-FRAME-01", "Working-frame evidence")):
        if handoff not in promotions:
            continue
        excerpt = next(m.group(0) for m in re.finditer(r"\*\*CODEX SAFE TRAINING FRONTIER:\*\*\s*`[^`]+`[^\n]*(?:\n[^\n]+)?", text) if handoff in m.group(0))
        existing = next((o for o in operations if o["capability_name"] == name), None)
        value = existing or {"capability_id": _slug(name), "capability_name": name, "evidence_refs": []}
        value.update(application={"stable_handoff": True}, safe_for_training=True,
                     scope="Named stable promotion only; no newer sheet/relationship behavior implied.",
                     source_priority="Explicit named promotion supersedes earlier NOT YET STABLE baseline for this operation.")
        value["evidence_refs"].append(_ref("CONTINUATION_CHECKPOINT.md", text, excerpt))
        if not existing:
            operations.append(value)
    active = re.findall(r"\*\*Claude application frontier:\*\*([^\n]+)", text)
    safe = re.findall(r"\*\*Codex safe frontier:\*\*([^\n]+)", text)
    frontier = {"active": active[0].strip() if active else U,
                "stable_handoff": safe[0].strip() if safe else U,
                "source_priority": "Topmost current-frontier section; retained older sections are history, not competing current claims.",
                "evidence_refs": [_ref("CONTINUATION_CHECKPOINT.md", text, "\n".join((active[:1] + safe[:1])))],
                "conflicts": []}
    # Explicitly shipped table supplies reachability, not a stable training grant.
    shipped_start = text.find("### Shipped, gated and deployed")
    shipped_end = text.find("### ", shipped_start + 5) if shipped_start >= 0 else -1
    shipped = text[shipped_start:shipped_end] if shipped_end > shipped_start else ""
    for line in shipped.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or not re.fullmatch(r"`[0-9a-f]{7,40}`", cells[0]):
            continue
        name = cells[1].replace("**", "").split(" — ", 1)[0].split(" wired", 1)[0]
        identity = "op.datum-corroboration" if name == "Datum corroboration boundary" else _slug(name)
        operations.append({"capability_id": identity, "capability_name": name,
                           "application": {"implemented": True, "reachable": True},
                           "safe_for_training": False, "scope": "Explicit shipped operation; no stable training handoff inferred.",
                           "evidence_refs": [_ref("CONTINUATION_CHECKPOINT.md", text, line)],
                           "source_priority": "Current shipped table establishes reachability only; stable handoff remains separate."})
    # A literal source/module named by the handoff can prove implementation,
    # never stable semantics. Unknown prose-only capabilities stay unresolved.
    for operation in operations:
        if operation["application"].get("stable_handoff") is True:
            continue
        literals = re.findall(r"`([A-Za-z_][A-Za-z_0-9]*)`", str(operation["scope"]))
        for literal in literals:
            source = Path(repo) / "services" / (literal + ".py")
            if literal == "may_compare_spatially":
                source = Path(repo) / "services" / "derived_view.py"
            if source.is_file():
                content = source.read_bytes().decode("utf-8")
                operation["application"]["implemented"] = True
                operation["evidence_refs"].append(_ref(source.relative_to(repo).as_posix(), content, "Named implementation module exists; not a stable handoff."))
    # Additional operations explicitly represented in the current kernel/contracts.
    # These are source bindings, not manually assigned readiness conclusions.
    bindings = (("op.source-ingestion", "Source ingestion", "services/ingestion.py", "def ingest_upload(", "governance/current/kernel-object-model.md"),
                ("op.governed-finding", "Governed finding", "services/case_workspace.py", "class Finding", "governance/current/kernel-object-model.md"),
                ("op.helix", "Helix", "services/spin.py", "KNOWN_HELIX_ASSESSMENTS", "governance/current/contracts/CIC-SPIN-INTELLIGENCE-v1.1.md"),
                ("op.datum-corroboration", "Stated-datum corroboration", "services/datum_corroboration.py", "def corroborate(", "MANIFEST.md"))
    for identity, name, relative, symbol, authority in bindings:
        source, spec = Path(repo) / relative, Path(repo) / authority
        if not source.is_file() or not spec.is_file():
            continue
        content, specification = source.read_bytes().decode("utf-8"), spec.read_bytes().decode("utf-8")
        if symbol not in content:
            continue
        operations.append({"capability_id": identity, "capability_name": name,
                           "application": {"implemented": True}, "safe_for_training": False,
                           "scope": "Implementation plus architecture/manifest reference; stable operational handoff not established by these alone.",
                           "evidence_refs": [_ref(relative, content, symbol), _ref(authority, specification, "Architecture/manifest source; no stability inference from file existence.")],
                           "source_priority": "Implementation binding does not override stable handoff scope or establish deployment/corpus acceptance."})
    merged = {}
    for operation in operations:
        identity = operation["capability_id"]
        if identity not in merged:
            merged[identity] = operation
            continue
        prior = merged[identity]
        disagreements = [key for key in operation["application"] if key in prior["application"] and
                         prior["application"][key] != operation["application"][key]]
        if disagreements:
            prior.setdefault("conflicts", []).append("Conflicting application assertions for " + identity + ": " + ", ".join(disagreements))
        else:
            prior["application"].update(operation["application"])
        prior["evidence_refs"].extend(operation["evidence_refs"])
    return list(merged.values()), frontier


def _material(row, source_root):
    ref = next((r for r in row["evidence_refs"] if r["path"].endswith("-material.json")), None)
    if not ref:
        return {}
    path = Path(source_root) / ref["path"]
    if not path.resolve().is_relative_to(Path(source_root).resolve()):
        return {}
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("Material changed since projection")
    return json.loads(raw.decode("utf-8-sig"))


def _observation(row, source_root):
    """Augment the accepted projection only with its already-hashed result bytes."""
    ref = next((r for r in row["evidence_refs"] if r["path"] == row["record_id"]), None)
    if not ref:
        return None
    path = Path(source_root) / ref["path"]
    if not path.resolve().is_relative_to(Path(source_root).resolve()):
        return None
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("Evidence changed since normalized projection: " + ref["path"])
    data = json.loads(raw.decode("utf-8-sig"))
    baseline = row["model_baseline"]
    instrument_proven = row["instrument_validity"] == "VALID" or (data.get("delivery_integrity") is True and data.get("material_valid") is True)
    valid = row["contract_compliance"] == "VALID" and instrument_proven and baseline != U
    if row["contract_compliance"] == "INVALID":
        valid = False
    elif not valid:
        valid = None
    control = row["control_type"]
    content = dict(row["task_content_result"])
    if content.get("target_alignment") is None and isinstance(data.get("requested_page_alignment"), bool):
        content["target_alignment"] = data["requested_page_alignment"]
    aligned = content.get("target_alignment")
    if control == U and aligned is True:
        control = "POSITIVE_CONTROL"
    return {"record_id": row["record_id"], "control": control, "valid": valid,
            "aligned": aligned if valid is True else None, "model_baseline": baseline,
            "contract_compliance": row["contract_compliance"], "instrument_validity": row["instrument_validity"],
            "task_content": content, "application_defect": row["application_defect"],
            "raw_response": row.get("raw_response", ""),
            "timestamp": row["timestamp"], "evidence_refs": row["evidence_refs"]}


def reconcile(operations, repo):
    """Forward correction from the retained PO/Claude clarification, not history edits."""
    relative = "docs/records/operation-taxonomy-clarification-01.json"
    path = Path(repo) / relative
    if not path.is_file():
        return operations, {"state": U, "reason": "Taxonomy clarification record missing", "product_questions": []}
    raw = path.read_bytes().decode("utf-8")
    data = json.loads(raw)
    if data.get("record_id") != "OPERATION-TAXONOMY-RECONCILIATION-01":
        raise ValueError("Unrecognized taxonomy clarification")
    replacements = data["operations"]
    retired = set(data["supersedes_projection_labels_only"])
    retired.update(identity for row in replacements for identity in row["replaces_projection_ids"])
    retired_rows = [row for row in operations if row["capability_id"] in retired]
    operations = [row for row in operations if row["capability_id"] not in retired]
    for row in replacements:
        row = dict(row)
        row.update(safe_for_training=row["application"]["trainable"],
                   scope=row["record_semantics"],
                   source_priority="Explicit PO-forwarded Claude clarification supersedes earlier projection equivalences only.",
                   evidence_refs=[_ref(relative, raw, json.dumps(row, sort_keys=True))])
        implementation = row.get("implementation")
        if implementation:
            source_name, symbol = implementation.split(":", 1)
            source = Path(repo) / source_name
            if not source.is_file() or "def " + symbol + "(" not in source.read_bytes().decode("utf-8"):
                row["conflicts"] = ["Clarified implementation symbol missing: " + implementation]
            else:
                row["evidence_refs"].append(_ref(source_name, source.read_bytes().decode("utf-8"), "def " + symbol + "("))
        row["evidence_refs"].extend(ref for old in retired_rows if old["capability_id"] in row["replaces_projection_ids"] for ref in old["evidence_refs"])
        operations.append(row)
    transition_path = Path(repo) / "docs/records/datum-lifecycle-transition-01.json"
    if transition_path.is_file():
        transition_raw = transition_path.read_bytes().decode("utf-8")
        transition = json.loads(transition_raw)
        if transition.get("prior_record") != data["record_id"] or transition.get("capability_id") != "op.datum-corroboration":
            raise ValueError("Unrecognized lifecycle transition")
        transition_refs = [_ref("docs/records/datum-lifecycle-transition-01.json", transition_raw, transition["source"])]
        for relative in transition["repository_evidence"]:
            source = Path(repo) / relative
            if not source.is_file():
                raise ValueError("Transition evidence missing: " + relative)
            transition_refs.append(_ref(relative, source.read_bytes().decode("utf-8"), "Lifecycle transition supporting evidence; see named transition record."))
        for operation in operations:
            if operation["capability_id"] == "op.datum-corroboration":
                operation["state_transitions"] = [{"from_record": data["record_id"], "from_facets": dict(operation["application"]),
                    "to_record": transition["record_id"], "to_facets": transition["application"], "commits": transition["commits"]}]
                operation["application"] = transition["application"]
                operation["lifecycle"] = transition["lifecycle"]
                operation["training_boundary"] = transition["training_boundary"]
                operation["scope"] = transition["semantics"]
                operation["evidence_refs"].extend(transition_refs)
                operation["source_priority"] = "Explicit later lifecycle transition corrects forward; earlier unwired state remains inspectable. No safe-frontier promotion."
                # Do not silently apply a historical transition to changed implementation.
                for relative, expected in transition["live_verification"]["files"].items():
                    content = (Path(repo) / relative).read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                    if hashlib.sha256(content).hexdigest() != expected:
                        operation.setdefault("conflicts", []).append("Lifecycle implementation changed since verified transition: " + relative)
            elif operation["capability_id"] == "op.relationship-sachet":
                operation["state_transitions"] = [{"from_record": data["record_id"], "previous_training_boundary": operation["training_boundary"],
                    "to_record": transition["record_id"], "dependency_correction": transition["sachet_dependency_correction"]}]
                operation["training_boundary"] = transition["sachet_dependency_correction"]
                operation["evidence_refs"].extend(transition_refs)
    return operations, {"state": "RECONCILED", "record_id": data["record_id"],
                        "evidence_refs": [_ref(relative, raw, data["source"])],
                        "retired_projection_entries": retired_rows,
                        "history_correction": data["history_correction"],
                        "codex_safe_frontier": data["codex_safe_frontier"],
                        "product_questions": data["product_questions"]}


def snapshot(normalized, source_root, repo):
    operations, frontier = handoff_catalog(repo)
    operations, reconciliation = reconcile(operations, repo)
    # Behavioral suboperations are attached to their proven application interface,
    # not treated as applications merely because a cognitive bar has observations.
    bindings = (("PDF positioned evidence", "C01", "page-selection"),
                ("Evidence trust explanation", "C28", "supported-claim-limits"),
                ("Evidence trust explanation", "C26", "unknown-versus-false"),
                ("Supersession behaviour", "C11", None))
    for name, bar, suffix in bindings:
        parent = next((o for o in operations if o["capability_name"] == name), None)
        if not parent:
            continue
        operation = dict(parent, evidence_refs=list(parent["evidence_refs"])) if suffix else parent
        if suffix:
            operation["capability_id"] += "." + suffix
            operation["capability_name"] += " / " + suffix.replace("-", " ")
            operations.append(operation)
        operation["negative_requirement"] = "REQUIRED"
        operation["negative_requirement_ref"] = "docs/OPERATION_EVIDENCE_RULES.md#negative-control-scope"
        operation["observations"] = []
        for row in normalized["records"]:
            if row["record_family"] != "ENCOUNTER" or row["actor"] != "GO" or row["capability"] != bar or row["task_kind"] == "TEACHING":
                continue
            material = _material(row, source_root)
            if not any(r["path"].endswith("-provenance.json") for r in row["evidence_refs"]) and not (material.get("source_review") and material.get("handoff")):
                continue
            if bar == "C11" and "spin_current_sources" not in str(row["application_capability"]):
                continue
            value = _observation(row, source_root)
            if value:
                operation["observations"].append(value)
    rows = []
    for facts in operations:
        facts["known_capability"] = True
        facts.setdefault("observations", [])
        models = {o["model_baseline"] for o in facts["observations"] if o["model_baseline"] != U}
        facts["model_baseline"] = next(iter(models)) if len(models) == 1 else U
        facts.setdefault("conflicts", [])
        if len(models) > 1:
            facts["conflicts"].append("Mixed model baselines; no cross-instrument readiness pooling.")
        facts["instrument_invalid"] = any(o["instrument_validity"] == "INVALID" for o in facts["observations"])
        # DEVELOPMENT authorization is not authority to issue a consequential finding.
        facts["governance_state"] = U
        result = classify(facts)
        app = facts["application"]
        facets = {key: app.get(key, U) for key in ("implemented", "reachable", "deployed", "real_corpus_proven", "stable", "trainable")}
        if app.get("stable_handoff") is True:
            facets.update(stable=True, trainable=True)
        evidence = facts["evidence_refs"] + [r for o in facts["observations"] for r in o["evidence_refs"]]
        rows.append({"capability_id": facts["capability_id"], "capability_name": facts["capability_name"],
                     **result, "governance_state": facts["governance_state"],
                     "application_facets": facets,
                     "lifecycle": facts.get("lifecycle", U), "training_boundary": facts.get("training_boundary", "Existing stable handoff scope only" if facts["safe_for_training"] else "No stable training handoff"),
                     "exclusions": facts.get("exclusions", []), "includes": facts.get("includes", []),
                     "state_transitions": facts.get("state_transitions", []),
                     "safe_for_training": facts["safe_for_training"], "model_baseline": facts["model_baseline"],
                     "positive_control_state": result.get("positive_control_state", U),
                     "negative_control_state": result.get("negative_control_state", U),
                     "latest_evidence": evidence, "observations": facts["observations"],
                     "source_priority": facts["source_priority"], "scope": facts["scope"],
                     "last_verified_at": max((o["timestamp"] for o in facts["observations"] if o["timestamp"] != U), default=U)})
    rows.sort(key=lambda r: r["capability_id"])
    blockers = [r["capability_id"] + ": " + "; ".join(r["unresolved_reasons"]) for r in rows if r["application_state"] == U or r["shared_state"] == U]
    if not rows:
        blockers.append("No operational capability taxonomy could be reconstructed.")
    if frontier["conflicts"]:
        blockers.extend(frontier["conflicts"])
    if frontier["active"] == U or frontier["stable_handoff"] == U:
        blockers.append("Current active or stable handoff frontier is unresolved.")
    if reconciliation["state"] != "RECONCILED":
        blockers.append(reconciliation["reason"])
    result = {"schema": VERSION, "authority": "READ-ONLY DERIVATION; NOT PROMOTION", "frontiers": frontier,
              "capabilities": rows, "taxonomy_reconciliation": reconciliation,
              "frontier_records": [r for r in normalized["records"] if r["record_family"] == "FRONTIER"],
              "normalized_projection_sha256": normalized["projection_sha256"],
              "ui_eligible": not blockers, "ui_blockers": blockers,
              "reserved_bands": ["EXCELLENT", "GOOD", "ADEQUATE", "POOR"]}
    result["sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return result
