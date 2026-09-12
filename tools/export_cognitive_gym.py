"""Rebuild a sanitized, non-authoritative dashboard projection; never runs GO.

Usage: python tools/export_cognitive_gym.py --source <evaluator> --output <json>
Publish output to instance/cognitive_gym/projection.json on hosts without access
to the evaluator. Re-run after newly completed records; no code edits needed.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.cognitive_gym import scan

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--frontier", action="store_true", help="Export operation/evidence frontier instead of the legacy Gym view")
    args = parser.parse_args()
    output = Path(args.output)
    if output.resolve().is_relative_to(Path(args.source).resolve()):
        parser.error("Output must be outside authoritative evaluator history")
    data = scan(args.source)
    if not data["sessions"]:
        parser.error("No sessions found; refusing to publish an empty replacement")
    sessions, events, issues = len(data["sessions"]), len(data["events"]), data["issues"]
    count = len(data["normalized"]["records"])
    evidence_time = data["generated_at"]
    eligible = data["normalized"]["health_eligible"]
    if args.frontier:
        from services.operational_frontier import snapshot
        data = snapshot(data["normalized"], args.source, Path(__file__).resolve().parents[1])
        eligible = data["ui_eligible"]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({"sessions": sessions, "events": events,
                      "issues": issues, "evidence_timestamp": evidence_time,
                      "snapshot_captured_at": datetime.now(timezone.utc).isoformat(),
                      "snapshot_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                      "normalized_records": count,
                      "health_eligible": eligible}))
