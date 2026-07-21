#!/usr/bin/env python
"""
Dependency/architecture fit checker for ArchiOSK / B-Hive.

A maintainer-run CLI, not part of the running app -- checks a proposed
library, tool, or architectural pattern against constraints this project
has actually and deliberately established. Every rule below is tied to a
specific, verifiable fact about the current codebase, not a hypothetical
policy -- see each rule's `justification`.

Usage:
    python tools/dependency_fit.py --name "some-library" \\
        --requires-client-build \\
        --requires-database --database-type postgres \\
        --requires-async-runtime \\
        --cloud-only \\
        --requires-background-worker \\
        --language javascript

Only pass the flags that actually apply to the candidate; everything
else defaults to "no". Exit code is 0 if nothing FAILs, 1 otherwise --
usable as a quick gate in a review checklist or CI step.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import Enum


class Verdict(Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class RuleResult:
    rule_id: str
    verdict: Verdict
    reason: str


@dataclass
class Rule:
    rule_id: str
    description: str
    justification: str
    check: "callable"  # (argparse.Namespace) -> RuleResult


def _no_client_build(args: argparse.Namespace) -> RuleResult:
    if args.requires_client_build:
        return RuleResult(
            "no-client-build", Verdict.FAIL,
            "Requires a client-side build step. This app has none -- "
            "static/css/main.css and static/js/dashboard.js are hand-written, "
            "no bundler/npm build anywhere in the repo.",
        )
    return RuleResult("no-client-build", Verdict.PASS, "No client build step required.")


def _flat_json_storage(args: argparse.Namespace) -> RuleResult:
    if args.requires_database:
        db = f" ({args.database_type})" if args.database_type else ""
        return RuleResult(
            "flat-json-storage", Verdict.WARN,
            f"Requires a database{db}. Storage today is deliberately flat JSON "
            "files (services/requirements_registry.py, services/governance.py) -- "
            "a SQLite-backed rewrite was explicitly proposed and explicitly "
            "rejected in favor of staying flat-file. Needs a real justification "
            "before adding a DB dependency, not just \"it's more standard\".",
        )
    return RuleResult("flat-json-storage", Verdict.PASS, "Works with flat-JSON-file storage.")


def _no_async_runtime(args: argparse.Namespace) -> RuleResult:
    if args.requires_async_runtime:
        return RuleResult(
            "no-async-runtime", Verdict.FAIL,
            "Requires an async-native runtime (asyncio event loop / gevent / "
            "eventlet). deploy/gunicorn.conf.py uses gthread workers "
            "(threaded, not event-loop-based) specifically because nothing "
            "in this app needed that model -- verified thread-safety, not "
            "async-safety, when that choice was made.",
        )
    return RuleResult("no-async-runtime", Verdict.PASS, "No async-native runtime required.")


def _no_new_cloud_dependency(args: argparse.Namespace) -> RuleResult:
    if args.cloud_only:
        return RuleResult(
            "no-new-cloud-dependency", Verdict.WARN,
            "Cloud-only / requires a hosted service. The one existing external "
            "dependency (Anthropic) is optional and degrades gracefully -- the "
            "whole app is documented to run fully offline without it. A new "
            "hard cloud dependency needs the same kind of graceful-degradation "
            "story, not just an API key check.",
        )
    return RuleResult("no-new-cloud-dependency", Verdict.PASS, "No new required cloud dependency.")


def _no_background_worker_infra(args: argparse.Namespace) -> RuleResult:
    if args.requires_background_worker:
        return RuleResult(
            "no-background-worker-infra", Verdict.FAIL,
            "Requires background worker/task-queue infrastructure (Celery, RQ, "
            "a cron daemon, etc). deploy/ documents exactly one process model: "
            "a single gunicorn+nginx VPS, no queue/worker infra anywhere in it.",
        )
    return RuleResult("no-background-worker-infra", Verdict.PASS, "No background worker infra required.")


def _python_native_preferred(args: argparse.Namespace) -> RuleResult:
    if args.language and args.language.lower() != "python":
        return RuleResult(
            "python-native-preferred", Verdict.WARN,
            f"Language is {args.language}, not Python. The entire backend is "
            "Python (Flask) -- a non-Python dependency needs a real reason "
            "(e.g. no Python equivalent exists) rather than just preference.",
        )
    return RuleResult("python-native-preferred", Verdict.PASS, "Python-native.")


RULES: list[Rule] = [
    Rule("no-client-build", "No client-side build step", "static/ has zero build tooling", _no_client_build),
    Rule("flat-json-storage", "Works with flat-JSON storage", "SQLite was explicitly proposed and rejected", _flat_json_storage),
    Rule("no-async-runtime", "No async-native runtime requirement", "gunicorn uses gthread, not async workers", _no_async_runtime),
    Rule("no-new-cloud-dependency", "No new required cloud/hosted dependency", "Anthropic is the one exception, and it degrades gracefully", _no_new_cloud_dependency),
    Rule("no-background-worker-infra", "No background worker/queue infra required", "deploy/ is a single gunicorn+nginx process, nothing else", _no_background_worker_infra),
    Rule("python-native-preferred", "Python-native preferred", "The entire backend is Python", _python_native_preferred),
]


def run_checks(args: argparse.Namespace) -> list[RuleResult]:
    return [rule.check(args) for rule in RULES]


def print_report(name: str, results: list[RuleResult]) -> Verdict:
    print(f"\nDependency fit check: {name}\n" + "=" * (22 + len(name)))
    worst = Verdict.PASS
    for result in results:
        marker = {"PASS": "  ", "WARN": "! ", "FAIL": "X "}[result.verdict.value]
        print(f"{marker}[{result.verdict.value:4}] {result.rule_id}")
        print(f"          {result.reason}")
        if result.verdict == Verdict.FAIL:
            worst = Verdict.FAIL
        elif result.verdict == Verdict.WARN and worst != Verdict.FAIL:
            worst = Verdict.WARN

    print()
    if worst == Verdict.PASS:
        print(f"Overall: PASS -- no conflicts with this project's established constraints.")
    elif worst == Verdict.WARN:
        print(f"Overall: WARN -- needs a documented justification before adopting.")
    else:
        print(f"Overall: FAIL -- conflicts with a constraint this project has deliberately chosen.")
    print()
    return worst


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check a proposed dependency/pattern against ArchiOSK/B-Hive's "
        "actual, established architectural constraints.",
    )
    parser.add_argument("--name", required=True, help="Name of the candidate library/tool/pattern.")
    parser.add_argument("--requires-client-build", action="store_true",
                         help="Needs a JS/frontend build step (bundler, transpiler, etc).")
    parser.add_argument("--requires-database", action="store_true",
                         help="Needs a database rather than flat files.")
    parser.add_argument("--database-type", default=None, help="e.g. sqlite, postgres, mysql.")
    parser.add_argument("--requires-async-runtime", action="store_true",
                         help="Needs asyncio/gevent/eventlet rather than sync/threaded code.")
    parser.add_argument("--cloud-only", action="store_true",
                         help="Only works against a hosted service -- no local/offline mode.")
    parser.add_argument("--requires-background-worker", action="store_true",
                         help="Needs Celery/RQ/a cron daemon or similar.")
    parser.add_argument("--language", default="python", help="Primary implementation language.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    results = run_checks(args)
    worst = print_report(args.name, results)
    return 1 if worst == Verdict.FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
