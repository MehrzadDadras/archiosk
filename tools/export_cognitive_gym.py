"""Rebuild a sanitized, non-authoritative dashboard projection; never runs GO.

Usage: python tools/export_cognitive_gym.py --source <evaluator> --output <json>
Publish output to instance/cognitive_gym/projection.json on hosts without access
to the evaluator. Re-run after newly completed records; no code edits needed.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.cognitive_gym import scan

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.resolve().is_relative_to(Path(args.source).resolve()):
        parser.error("Output must be outside authoritative evaluator history")
    data = scan(args.source)
    if not data["sessions"]:
        parser.error("No sessions found; refusing to publish an empty replacement")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({"sessions": len(data["sessions"]), "events": len(data["events"]), "issues": data["issues"], "generated_at": data["generated_at"]}))
