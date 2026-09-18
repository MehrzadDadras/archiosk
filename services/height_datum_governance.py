"""Rule 6 governance projection over datum candidate evidence.

The protected datum_corroboration engine retains all deterministic datum
mathematics and provisional cross-document corroboration. Corroboration alone
cannot establish a governing height datum. This adapter owns only the separate
review/projection chain for survey centerline candidates: existing EvidenceItem
proposals, governed relationship reviews, anchor currentness, evidence trust,
and independently acquired planning authority. No new authority mechanism.

Document examination and Ask GO consume this projection after reloading evidence.
Historical evidence is retained; review state is recomputed rather than cached.
"""
from __future__ import annotations

import re

# Survey height datum: independent premises, stored in existing EvidenceItems.
# This extends datum evidence; it neither creates a statutory authority nor
# promotes source text merely because the extraction was legible.
HEIGHT_PREMISE_TYPE = "survey_height_datum_premise"
HEIGHT_AXES = ("street_centerline_geometry", "regulatory_requirement", "authority",
               "applicability", "selected_governing_street", "building_reference_alignment_or_midpoint")


def normalise_height_datums(raw):
    from services import binding, survey_graph, visual_examination as vx
    result = []
    for item in raw[:24] if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        candidate = {k: str(item.get(k) or "")[:160] for k in ("id", "subject_id")}
        for axis in HEIGHT_AXES:
            value = item.get(axis) if isinstance(item.get(axis), dict) else {}
            record = binding.bind(value.get("value"), read_certainty=survey_graph._certainty(value.get("read_certainty")),
                bind_basis=value.get("bind_basis", "none"), claimed_bind_certainty=survey_graph._certainty(value.get("bind_certainty")),
                bound_to=value.get("bound_to"), note=str(value.get("provenance") or "")[:1000])
            for key in ("kind", "street_id", "street_name", "building_id", "text", "locator", "subject_id"):
                record[key] = str(value.get(key) or "")[:500]
            record["source_region"] = vx._bbox(value.get("source_region"))
            region = record["source_region"]
            if (not region or any(survey_graph._num(v) is None for v in region.values())
                    or region["x"] < 0 or region["y"] < 0 or region["w"] <= 0 or region["h"] <= 0
                    or region["x"] + region["w"] > 1 or region["y"] + region["h"] > 1):
                record["source_region"] = {}
            record["coordinate_space"] = "OBSERVED_IMAGE_FRACTIONS"
            points = value.get("points") or []
            record["points"] = [p for p in (survey_graph._point(p) for p in points[:50] if isinstance(p, dict)) if p is not None] if isinstance(points, list) else []
            # No model-supplied authority, review state, coordinate scale or
            # computed midpoint can survive normalization as established fact.
            candidate[axis] = record
        result.append(candidate)
    return result


def height_snapshot(candidate):
    import hashlib
    import json
    return hashlib.sha256(json.dumps({k: candidate.get(k) for k in ("id", "subject_id", *HEIGHT_AXES)},
                                    sort_keys=True).encode()).hexdigest()


def propose_height_datums(store, workspace, visual_evidence, graph):
    import json
    from services.case_workspace import EVIDENCE_CLASS_AI_GENERATED_PROPOSAL
    for candidate in graph.get("height_datums", []):
        for axis in HEIGHT_AXES:
            record = {"candidate_id": candidate["id"], "subject_id": candidate["subject_id"],
                      "snapshot": height_snapshot(candidate), "visual_evidence_id": visual_evidence["id"],
                      "axis": axis, "reading": candidate[axis],
                      "review_obligation": "Establish this exact premise for this subject and occurrence. Authority additionally requires a reviewed supports link from independently acquired planning authority evidence to the authority premise. Recovery is not applicability; image geometry is not regulatory authority."}
            row = store.register_evidence_item(workspace, visual_evidence["source_id"], EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
                json.dumps(record, sort_keys=True), HEIGHT_PREMISE_TYPE, actor="visual-worker")
            store.record_evidence_relationship(workspace, "evidence_item", row["id"], "evidence_item", visual_evidence["id"],
                "supports", provisional=True, created_by="visual-worker", reason="Proposed height datum premise: " + axis)


def resolve_height_datums(store, workspace, visual):
    """Read current evidence/relationship state; never write authority or history."""
    import json
    from services import planning_authority
    evidence = {e["id"]: e for e in workspace.evidence_items}
    visual_source_id = evidence.get(visual.get("evidence_item_id"), {}).get("source_id")
    def decode(row):
        try:
            value = json.loads(row.get("content") or "")
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}
    def trust_state(row_id):
        trust = store.explain_evidence_trust(workspace, row_id)
        state = ("CONTESTED" if trust.get("confirmed_counterevidence") else
                 "UNRESOLVED" if trust.get("unresolved_counterevidence") or trust.get("status") != "assembled"
                 or trust.get("currentness", {}).get("status") != "current" else "ESTABLISHED")
        return state, trust
    for candidate in (visual.get("graph") or {}).get("height_datums", []):
        reviews = {axis: {"state": "UNRESOLVED", "evidence_ids": [], "trust": []} for axis in HEIGHT_AXES}
        authorities = []
        for edge in workspace.relationships:
            if (edge.get("relationship_type") != "supports" or edge.get("from_type") != "evidence_item"
                    or edge.get("to_type") != "evidence_item" or edge.get("to_id") != visual.get("evidence_item_id")):
                continue
            row = evidence.get(edge["from_id"], {})
            record = decode(row)
            axis = record.get("axis")
            if (row.get("content_type") != HEIGHT_PREMISE_TYPE or axis not in reviews
                    or record.get("snapshot") != height_snapshot(candidate)
                    or record.get("candidate_id") != candidate.get("id")
                    or record.get("visual_evidence_id") != visual.get("evidence_item_id")):
                continue
            state, trust = trust_state(row["id"])
            if store.resolve_relationship_status(workspace, edge["id"])["status"] != "confirmed" or not edge.get("confirmed_by"):
                state = "UNRESOLVED" if state != "CONTESTED" else state
            review = reviews[axis]
            if review["evidence_ids"]:
                state = "CONTESTED" if "CONTESTED" in (state, review["state"]) else (
                    "ESTABLISHED" if state == review["state"] == "ESTABLISHED" else "UNRESOLVED")
            review.update(state=state)
            review["evidence_ids"].append(row["id"])
            review["trust"].append(trust)
            if axis != "authority":
                continue
            for link in workspace.relationships:
                if (link.get("relationship_type") != "supports" or link.get("from_type") != "evidence_item"
                        or link.get("to_type") != "evidence_item" or link.get("to_id") != row["id"]):
                    continue
                authority_evidence = evidence.get(link["from_id"], {})
                authority = decode(authority_evidence)
                authority_state, authority_trust = trust_state(link["from_id"])
                sources = [s for s in workspace.sources if s["id"] == authority_evidence.get("source_id")]
                valid = (store.resolve_relationship_status(workspace, link["id"])["status"] == "confirmed"
                    and bool(link.get("confirmed_by")) and bool(sources) and not sources[0].get("removed_at")
                    and authority_evidence.get("source_id") != visual_source_id
                    and planning_authority.may_satisfy_authority_says(authority)
                    and isinstance(authority.get("url"), str)
                    and planning_authority.classify_source(authority["url"])["source_class"] == planning_authority.CLASS_OFFICIAL
                    and authority.get("acquisition_method") == planning_authority.ACQUISITION_METHOD
                    and authority.get("applicability") == planning_authority.APPLICABILITY_CURRENT
                    and bool(authority.get("provision_locator"))
                    and candidate["regulatory_requirement"].get("locator") == authority.get("provision_locator")
                    and bool(candidate["regulatory_requirement"].get("text"))
                    and isinstance(authority.get("retained_representation"), str)
                    and planning_authority.provenance_hash(authority["retained_representation"]) == authority.get("provenance_hash")
                    and candidate["regulatory_requirement"]["text"] in (authority.get("retained_representation") or ""))
                authorities.append({"evidence_id": link["from_id"], "relationship_id": link["id"],
                    "state": authority_state if valid or authority_state == "CONTESTED" else "UNRESOLVED",
                    "record": authority, "trust": authority_trust})
        authority_review = reviews["authority"]
        if any(a["state"] == "CONTESTED" for a in authorities):
            authority_review["state"] = "CONTESTED"
        elif authority_review["state"] == "ESTABLISHED" and (not authorities or any(a["state"] != "ESTABLISHED" for a in authorities)):
            authority_review["state"] = "UNRESOLVED"
        source_state, source_trust = trust_state(visual.get("evidence_item_id"))
        if any(s.get("removed_at") for s in workspace.sources if s["id"] == visual_source_id):
            source_state = "UNRESOLVED"
        candidate["height_review"] = {"premises": reviews, "authorities": authorities,
                                      "plane_id": visual.get("evidence_item_id"),
                                      "source_state": source_state, "source_trust": source_trust}
    return visual


def height_datum_projection(graph):
    """A conjunction of independently reviewed premises, not a text classifier."""
    from services import binding, survey_graph
    results = []
    candidates = graph.get("height_datums", [])
    subject = graph.get("subject_parcel") or {}
    for candidate in candidates:
        review = candidate.get("height_review") or {}
        premises = review.get("premises") or {}
        geometry = candidate.get("street_centerline_geometry") or {}
        rule = candidate.get("regulatory_requirement") or {}
        application = candidate.get("applicability") or {}
        street = candidate.get("selected_governing_street") or {}
        alignment = candidate.get("building_reference_alignment_or_midpoint") or {}
        def established(axis):
            value = candidate.get(axis) or {}
            return (premises.get(axis, {}).get("state") == "ESTABLISHED"
                and binding.bound_certainty(value) == "RECOVERED" and bool(value.get("note"))
                and bool(value.get("source_region")))
        geometry_ok = (geometry.get("kind") == "STREET_CENTERLINE" and len(geometry.get("points", [])) >= 2
            and len({tuple(p) for p in geometry["points"]}) >= 2 and bool(geometry.get("street_id"))
            and geometry.get("bound_to") == geometry.get("street_id") and established("street_centerline_geometry"))
        authorities = review.get("authorities") or []
        contested = (review.get("source_state") == "CONTESTED" or any(p.get("state") == "CONTESTED" for p in premises.values())
                     or any(a["state"] == "CONTESTED" for a in authorities))
        status = "UNRESOLVED"
        if contested:
            status = "CONTESTED"
        elif geometry_ok and review.get("source_state") == "ESTABLISHED":
            status = "GEOMETRY_ONLY"
            if rule.get("text"):
                status = "APPLICABILITY_UNRESOLVED"
                if established("applicability") and application.get("value") == "DOES_NOT_APPLY":
                    status = "RULE_RECOVERED_NOT_APPLICABLE"
                elif (established("regulatory_requirement") and rule.get("value") == "CENTERLINE_HEIGHT_DATUM"
                      and established("authority") and authorities and all(a["state"] == "ESTABLISHED" for a in authorities)
                      and established("applicability") and application.get("value") == "APPLIES"
                      and application.get("subject_id") == candidate.get("subject_id") == subject.get("identity")
                      and binding.bound_certainty(subject) == "RECOVERED" and subject.get("provenance")):
                    status = "DATUM_CANDIDATE"
                    if not (established("selected_governing_street") and street.get("value") == geometry.get("street_id")
                            and street.get("bound_to") == geometry.get("street_id")):
                        status = "UNRESOLVED"
                    elif (established("building_reference_alignment_or_midpoint")
                          and alignment.get("kind") in ("DOCUMENTED_MIDPOINT", "DOCUMENTED_REFERENCE_AXIS")
                          and alignment.get("street_id") == geometry.get("street_id")
                          and alignment.get("building_id") in {f["id"] for f in graph.get("footprints", [])
                              if survey_graph.footprint_containment(graph, f)["state"] == "INSIDE_SUBJECT_PARCEL"}
                          and alignment.get("bound_to") == alignment.get("building_id")
                          and alignment.get("points")):
                        status = "GOVERNING_DATUM_ESTABLISHED"
        if sum(c.get("id") == candidate.get("id") for c in candidates) != 1 or not candidate.get("id"):
            status = "UNRESOLVED"
        results.append({"candidate_id": candidate.get("id"), "subject_id": candidate.get("subject_id"),
                        "datum_status": status, **{axis: candidate.get(axis) for axis in HEIGHT_AXES}, "review": review})
    governing = [r for r in results if r["datum_status"] == "GOVERNING_DATUM_ESTABLISHED"]
    if len(governing) > 1:
        for row in governing:
            row["datum_status"] = "UNRESOLVED"
    return results


def is_height_datum_claim(observation):
    """Legacy prose admission guard; never establishes a premise or datum."""
    value = observation.get("value") or ""
    return bool(re.search(r"\b(?:governing\s+height\s+datum|height\s+datum|regulatory\s+datum)\b|\bheight\b.*\bcent(?:er|re)line\b", value, re.I))
