"""Read-only diagnostic presentation. No registry, provider or evaluator writes."""
import hashlib
import json
from pathlib import Path

from services.operational_frontier import VERSION, U, snapshot


def _validate(data):
    if not isinstance(data, dict) or data.get("schema") != VERSION:
        raise ValueError("Unsupported frontier snapshot schema")
    payload = dict(data)
    digest = payload.pop("sha256", None)
    actual = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                       separators=(",", ":")).encode()).hexdigest()
    if digest != actual:
        raise ValueError("Frontier snapshot integrity check failed")
    rows = data.get("capabilities")
    required = {"capability_id", "capability_name", "application_state", "go_state", "shared_state",
                "gap_owner", "application_facets", "latest_evidence", "observations", "why_this_band"}
    if not isinstance(rows, list) or any(not isinstance(r, dict) or not required <= r.keys() for r in rows):
        raise ValueError("Incomplete operation records")
    if len({r["capability_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate operation identifiers")
    for row in rows:
        if not isinstance(row["application_facets"], dict) or not isinstance(row["observations"], list) or not isinstance(row["latest_evidence"], list):
            raise ValueError("Malformed operation evidence")
        if any(not isinstance(o, dict) or not isinstance(o.get("task_content"), dict) for o in row["observations"]):
            raise ValueError("Malformed encounter evidence")
    if not isinstance(data.get("frontiers"), dict) or not isinstance(data.get("taxonomy_reconciliation"), dict):
        raise ValueError("Missing frontier or taxonomy evidence")
    return data


def _sanitize(value):
    from services.cognitive_gym import clean
    if isinstance(value, str):
        return clean(value)
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    return value


def dashboard(config, instance_path):
    """Local evidence when present, otherwise an explicitly published derived snapshot."""
    root = Path(config.get("COGNITIVE_GYM_EVALUATOR_ROOT") or r"C:\Archiosk\FlightTests\evaluator")
    repo = Path(__file__).resolve().parents[1]
    source = "Local evaluator projection"
    try:
        if root.is_dir():
            from services.cognitive_gym import scan
            data = snapshot(scan(root)["normalized"], root, repo)
        else:
            path = Path(instance_path) / "convergence" / "frontier.json"
            if path.stat().st_size > 8_000_000:
                raise ValueError("Frontier snapshot exceeds the read limit")
            data = json.loads(path.read_bytes().decode("utf-8-sig"))
            source = "Manually published evidence snapshot"
        data = _sanitize(_validate(data))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {"available": False, "issues": [type(exc).__name__ + ": " + str(exc)], "source": source}
    if not data.get("ui_eligible"):
        return {"available": False, "issues": data.get("ui_blockers") or ["Projection eligibility unresolved"], "source": source}
    rows = data["capabilities"]
    by_id = {r["capability_id"]: r for r in rows}
    records = data.get("frontier_records", [])
    # Undated competing narratives are not silently ranked by directory name.
    narrative = records[0] if len(records) == 1 else {}
    details = narrative.get("details", {})
    shared = [r for r in rows if r["shared_state"] == "SHARED_FRONTIER"]
    developing = [r for r in rows if r["go_state"] == "DEVELOPING"]
    axes = {"application": ["UNAVAILABLE", "EXPERIMENTAL", "REACHABLE", "STABLE"],
            "go": ["RELIABLE FOR THIS OPERATION", "CONDITIONALLY READY", "DEVELOPING", "UNTESTED"]}
    matrix = [{"app": app, "go": go, "rows": [r for r in rows if r["application_state"] == app and r["go_state"] == go]}
              for go in axes["go"] for app in axes["application"]]
    # Ordered diagnostic spine selects existing mapped operations, not invented stages.
    spine_ids = ["op.source-ingestion", "op.pdf-positioned-evidence", "op.sheet-identity-reference",
                 "op.detail-callout-reference", "op.relationship-sachet", "op.cross-discipline-micro-context",
                 "op.datum-corroboration", "op.evidence-trust-explanation.supported-claim-limits", "op.governed-finding"]
    return {"available": True, "source": source, "data": data, "rows": rows, "axes": axes, "matrix": matrix,
            "spine": [by_id[key] for key in spine_ids if key in by_id], "developing": developing, "shared": shared,
            "transitions": [r for r in rows if r.get("state_transitions")],
            "product_target": narrative.get("shared_frontier_evidence", {}).get("product_target", U),
            "current_gap": details.get("CURRENT_GAP", U), "next_action": details.get("NEXT_ACTION", U),
            "gap_owner": narrative.get("gap_owner", U), "frontier_records": records,
            "last_evidence_at": max((r["last_verified_at"] for r in rows if r.get("last_verified_at") != U), default=U)}
