"""Read-only, rebuildable projection of evaluator evidence. Never an execution API.

Only public-to-examiner summaries are read; no keys, outbound requests, tools,
provider wire dumps, or assessment stimuli are loaded. Unknown schemas stay
visible as unparsed sessions, not inferred performance or governed status.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "governance/cognitive-gym/CAPABILITY-CATALOG.md"
SCHEMA = 1
MAX_BYTES = 2_000_000
STATUSES = {"UNTESTED", "LEARNING", "NEEDS MORE TRAINING", "RELIABLE AT THIS LEVEL",
            "READY TO RAISE BAR", "READY TO RAISE THE BAR", "TRANSFER IN PROGRESS", "TRANSFERRED"}


def clean(value):
    text = str(value) if value is not None else "Not recorded"
    return re.sub(r"(?i)(?:sk-ant-|sk-)[a-z0-9_-]{12,}|(?:api_key|authorization|password|secret)\s*[:=]\s*[^\s,}]+", "[redacted]", text)


def catalog():
    text = CATALOG.read_text(encoding="utf-8")
    return [{"code": c, "name": n} for c, n in
            re.findall(r"\| (C\d{2}) \| \*\*([^:]+):", text)]


class Reader:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.issues = []
        self.refs = {}

    def get(self, path, text=False):
        path = Path(path)
        try:
            if not path.is_file():
                return "" if text else {}
            if not path.resolve().is_relative_to(self.root) or path.is_symlink():
                raise ValueError("outside source root")
            if path.stat().st_size > MAX_BYTES:
                raise ValueError("oversized summary")
            raw = path.read_bytes()
            ref = path.relative_to(self.root).as_posix()
            self.refs[ref] = hashlib.sha256(raw).hexdigest()
            result = raw.decode("utf-8-sig") if text else json.loads(raw)
            if not text and not isinstance(result, dict):
                raise ValueError("summary must be an object")
            if not text:
                for key in ("usage", "parsed", "parsed_action", "state", "next_decision"):
                    if key in result and result[key] is not None and not isinstance(result[key], dict):
                        raise ValueError("unsupported nested summary")
                for key in ("phase", "raw", "raw_response"):
                    if key in result and not isinstance(result[key], str):
                        raise ValueError("unsupported response field")
            return result
        except (OSError, ValueError, UnicodeError) as exc:
            self.issues.append(f"{path.name}: unreadable or unsupported artifact ({type(exc).__name__})")
            return "" if text else {}

    def timestamp(self, path, data=None):
        data = data or {}
        for key in ("timestamp", "timestamp_utc", "created_utc", "reviewed_utc"):
            if isinstance(data.get(key), str):
                return data[key], "recorded"
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(), "file time (fallback)"
        except OSError:
            return "", "not recorded"


def _parse(raw):
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def scan(root):
    reader = Reader(root)
    sessions, events = [], []
    if not reader.root.is_dir():
        reader.issues.append("Evaluator source unavailable; no evidence can be inferred.")
    for folder in sorted(reader.root.glob("GO-COGNITIVE-GYM*")):
        if not folder.is_dir() or folder.is_symlink():
            continue
        match = re.search(r"-C(\d{2})-", folder.name)
        # GOtex instrument qualification supports C01's teaching seam, not GO performance.
        code = "C" + match[1] if match else "C01"
        report = reader.get(folder / "REPORT.md", text=True)
        records = folder / "records"
        examiner = folder / "examiner"
        qualified = "QUALIFICATION" in folder.name
        preflight = reader.get(folder / "preflight.json")
        stopped = reader.get(records / "stopped-result.json")
        seals = []
        for directory in (folder, examiner):
            for path in sorted(directory.glob("*seal.json")):
                data = reader.get(path)
                seals.append({"ref": path.relative_to(reader.root).as_posix(),
                              "status": clean(data.get("status", data.get("type", data.get("classification", "Seal present; scope in source"))))})
        kind = "QUALIFICATION" if qualified else "PREPARATION"
        if stopped or preflight.get("status") == "PRE_FLIGHT_BLOCKED" or any("stopped" in s["ref"] for s in seals):
            kind = "STOPPED / DEFECT"
        stamp, basis = reader.timestamp(folder / "REPORT.md", preflight)
        session = {"identity": folder.name, "code": code, "kind": kind,
                   "time": stamp, "time_basis": basis, "report": clean(report) if report else "No readable report; inspect artifact references.",
                   "seals": seals, "events": [], "qualification": qualified,
                   "status": clean(stopped.get("status", preflight.get("status", "See evidence")))}
        expected = reader.get(examiner / "expected.json") if not qualified and "C01" in folder.name else {}
        summary = reader.get(records / "development-record.json")
        early = reader.get(examiner / "development-record.json")
        cycle = reader.get(examiner / "cycle-results.json")
        decision = reader.get(records / "next-developmental-move.json") or reader.get(examiner / "next-developmental-move.json")
        decision_paths = sorted(records.glob("go*-next-developmental-move.json"))
        if decision_paths:
            decision = reader.get(decision_paths[-1])
        move = decision.get("next_move") or summary.get("next_move") or early.get("adaptive_decision")
        if not move and isinstance(cycle.get("next_decision"), dict):
            move = cycle["next_decision"].get("next_move")
        session["next_move"] = clean(move) if move else "Not recorded"
        session["rationale"] = clean(decision.get("rationale", decision.get("reason", summary.get("rationale", early.get("rationale")))))
        session["next_step"] = clean(decision.get("recommended_cadence", summary.get("recommended_cadence", early.get("next_candidate"))))
        assessment = reader.get(records / "assessment-record.json") or reader.get(examiner / "assessment-record.json")
        transfer = reader.get(records / "transfer-record.json") or reader.get(examiner / "transfer-record.json")
        status_record = reader.get(records / "capability-status.json")
        session["assessment_completed"] = assessment.get("mode") == "ASSESSMENT" and assessment.get("execution_valid") is True and assessment.get("completed") is True
        session["transfer_activity"] = transfer.get("executed") is True and bool(transfer.get("source_realm")) and bool(transfer.get("destination_realm"))
        session["governed_status"] = status_record.get("status") if status_record.get("authorized") is True and status_record.get("authority_ref") and status_record.get("status") in STATUSES else None
        session["assessment_record"] = clean(json.dumps(assessment)) if assessment else ""
        session["transfer_record"] = clean(json.dumps(transfer)) if transfer else ""
        if session["assessment_completed"]:
            session["kind"] = "ASSESSMENT"
        elif session["transfer_activity"]:
            session["kind"] = "TRANSFER"
        source = reader.get(records / "source.json")
        intervention = reader.get(examiner / "intervention-record.json")
        source_ref = source.get("record", "")
        session["source_exercise"] = clean(source_ref.replace("\\", "/").split("/evaluator/")[-1]) if source_ref else clean(intervention.get("source_GO_session", "See source facts in teaching record"))
        candidates = []
        if not qualified:
            candidates += [(p, reader.get(p)) for p in sorted(records.glob("*-result.json")) if p.name != "stopped-result.json"]
            candidates += [(p, reader.get(p)) for p in sorted(examiner.glob("*-complete.json"))]
            if early.get("raw_response"):
                candidates.append((examiner / "development-record.json", {**early, "phase": "go1", "raw": early["raw_response"]}))
        for path, data in candidates:
            if not isinstance(data.get("raw"), str):
                continue
            phase = data.get("phase", path.stem.replace("-result", ""))
            actor = "GOTEX" if phase == "gotex" else ("GO TEACHING" if phase in ("cheat", "teach") else "GO")
            material = reader.get(records / (phase + "-material.json"))
            state = reader.get(folder / "material" / phase / "state.json")
            legacy = reader.get(examiner / "policy.json") if not material else {}
            if not state and isinstance(legacy.get("state"), dict) and actor == "GO":
                state = legacy["state"]
            objective = material.get("objective", data.get("question"))
            if not objective:
                objective = next((e.get("data", {}).get("wording") for e in reversed(state.get("events", [])) if e.get("kind") == "target"), None)
            if actor == "GOTEX" and not objective:
                # Older text application is preserved in the examiner intervention record/report.
                task = intervention.get("GOtex_task", "Legacy text application; see session report")
                objective = " ".join(str(task.get(k, "")) for k in ("objective", "available")).strip() if isinstance(task, dict) else task
            target = material.get("target", expected.get(phase, expected.get("aligned") if phase == "go1" else None))
            parsed = data.get("parsed") or data.get("parsed_action") or _parse(data["raw"])
            selected = parsed.get("selected")
            annotation = data.get("observable_annotation", "")
            aligned = selected == [target] if target and isinstance(selected, list) else (True if annotation == "TARGET-ALIGNED BEHAVIOR" else None)
            dispatch_path = records / (phase + "-dispatch.json")
            dispatch = reader.get(dispatch_path)
            if not dispatch:
                dispatch_path = examiner / ("real-started.json" if phase == "go1" else phase + "-started.json")
                dispatch = reader.get(dispatch_path)
            event_time, event_basis = reader.timestamp(path, dispatch)
            validity = data.get("execution_valid")
            if validity is None and cycle.get("audit"):
                audit = next((a for a in cycle["audit"] if a.get("phase") == phase), {})
                validity = True if audit.get("exact_wire") and audit.get("raw_preserved") else None
            event = {"id": f"{folder.name}/{phase}", "session": folder.name, "code": code,
                     "title": "GO Exercise " + phase[2:] if re.fullmatch(r"go\d+", phase) else actor,
                     "actor": actor, "kind": "DEVELOPMENT OBSERVATION", "mode": "DEVELOPMENT",
                     "phase": phase, "time": event_time, "time_basis": event_basis,
                     "encounter": material.get("encounter", data.get("encounter", state.get("encounter", "Not recorded"))),
                     "objective": clean(objective), "target": clean(target),
                     "condition": clean(material.get("salience", material.get("factor_increased", "Not recorded / see report"))),
                     "distractor": clean(material.get("distractor")), "raw": clean(data["raw"]),
                     "valid": validity, "aligned": aligned, "clarification": parsed.get("type") == "CLARIFY" if parsed else None,
                     "usage": {k: data.get("usage", {}).get(k) for k in ("input_tokens", "output_tokens")},
                     "cost": data.get("cost_usd"), "elapsed": data.get("elapsed_seconds"),
                     "ref": path.relative_to(reader.root).as_posix(), "causation": "NOT ESTABLISHED",
                     "source_exercise": session["source_exercise"]}
            session["events"].append(event)
            events.append(event)
        if session["events"] and session["kind"] == "PREPARATION":
            session["kind"] = "DEVELOPMENT OBSERVATION"
        # Preserve incomplete authored text without counting it as completed teaching.
        if stopped:
            session["incomplete_raw"] = clean(reader.get(records / "cheat.raw", text=True))
        if session["events"]:
            session["time"] = max(e["time"] for e in session["events"])
            session["time_basis"] = "latest encounter"
        session["refs"] = sorted(k for k in reader.refs if k.startswith(folder.name + "/"))
        sessions.append(session)
    sessions.sort(key=lambda s: (s["time"], s["identity"]))
    events.sort(key=lambda e: (e["time"], e["id"]))
    bars = []
    for item in catalog():
        related = [s for s in sessions if s["code"] == item["code"]]
        observed = [e for e in events if e["code"] == item["code"]]
        developments = [s for s in related if s["events"]]
        last = developments[-1] if developments else (related[-1] if related else None)
        latest_move = next((s["next_move"] for s in reversed(developments) if s["next_move"] != "Not recorded"), "Not recorded")
        governed = next((s["governed_status"] for s in reversed(related) if s["governed_status"]), None)
        assessments = sum(s["assessment_completed"] for s in related)
        transfers = sum(s["transfer_activity"] for s in related)
        # These are event labels, never capability-status transitions.
        movement = "— untested"
        if observed:
            movement = "→ gathering evidence"
            if latest_move == "SIMPLIFY":
                movement = "↘ simplification proposed"
            elif latest_move in ("RAISE", "INCREASE DISTRACTOR", "INCREASE DISTRACTOR PRESSURE"):
                movement = "↑ increased challenge proposed"
            elif latest_move == "TRANSFER":
                movement = "↗ transfer proposed (not begun)"
        if related and related[-1]["kind"] == "STOPPED / DEFECT":
            movement = "! material / instrument issue"
        if transfers:
            movement = "↗ recorded transfer activity"
        bars.append({**item, "status": governed or ("DEVELOPMENT ONLY" if observed else "UNTESTED"),
                     "status_note": "Governed status record present" if governed else ("No governed capability promotion record" if observed else "No assessed capability status recorded"),
                     "movement": movement, "latest": last["identity"] if last else "No activity recorded",
                     "time": last["time"] if last else "—", "time_basis": last["time_basis"] if last else "",
                     "condition": observed[-1]["condition"] if observed else "Not established",
                     "next_move": latest_move, "assessment": f"{assessments} completed record(s)" if assessments else "NOT RUN / no completed assessment record",
                     "next_step": last["next_step"] if last else "Not recorded",
                     "transfer": "ACTIVITY RECORDED / not a transfer competence claim" if transfers else "NOT ESTABLISHED", "sessions": related, "events": observed})
    focus = next((b for b in sorted(bars, key=lambda b: b["time"], reverse=True) if b["events"]), None)
    ticker = [{"code": e["code"], "text": e["title"] + " · " + ("target aligned" if e["aligned"] is True else "response recorded"), "time": e["time"]} for e in events]
    ticker += [{"code": s["code"], "text": s["kind"] + " · " + (s["next_move"] if s["next_move"] != "Not recorded" else s["status"]), "time": s["time"]} for s in sessions]
    ticker.sort(key=lambda e: e["time"], reverse=True)
    return {"schema": SCHEMA, "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "Evaluator scan", "bars": bars, "focus": focus["code"] if focus else None,
            "sessions": sessions, "events": events, "ticker": ticker[:16], "issues": reader.issues,
            "source_hashes": reader.refs,
            "metrics": {"Active bars": sum(bool(b["events"]) for b in bars),
                        "Untested bars": sum(not b["events"] for b in bars),
                        "Development sessions": sum(bool(s["events"]) for s in sessions),
                        "GOtex interventions": sum(e["actor"] == "GOTEX" for e in events),
                        "Assessments run": sum(s["assessment_completed"] for s in sessions),
                        "Transfer activities": sum(s["transfer_activity"] for s in sessions)},
            "coverage": "Counts cover recognized completed developmental records. Qualification/preflight is never Assessment. Unknown formats remain visible in session reports; zero assessment/transfer means no recognized completed record, not proof of absence."}


def dashboard(config, instance_path):
    root = Path(config.get("COGNITIVE_GYM_EVALUATOR_ROOT") or r"C:\Archiosk\FlightTests\evaluator")
    if root.is_dir():
        return scan(root)
    snapshot = Path(instance_path) / "cognitive_gym" / "projection.json"
    reader = Reader(snapshot.parent)
    data = reader.get(snapshot)
    if (data.get("schema") == SCHEMA and isinstance(data.get("bars"), list)
            and len(data["bars"]) == 28 and all(isinstance(b, dict) and
            {"code", "name", "status", "events", "sessions", "next_move"} <= b.keys() for b in data["bars"])
            and isinstance(data.get("metrics"), dict) and isinstance(data.get("ticker"), list)):
        data["source"] = "Published evaluator projection (snapshot)"
        return data
    data = scan(root)
    data["issues"] += reader.issues
    return data
