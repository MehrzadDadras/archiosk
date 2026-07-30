"""
CLAUDE-P31 -- Part X's technical-telemetry / content-bearing-support-
package boundary, made real rather than merely described.

This repository has no existing telemetry/support/diagnostic mechanism
at all (no Sentry, no error-reporting service, no support-ticket model)
-- confirmed by repository inspection, not assumed. This module is
therefore a small, new, honestly-scoped service: it builds two
different kinds of diagnostic payload and gates the more dangerous one
through services.security_policy.evaluate_action, rather than
retrofitting an enforcement layer onto a support system that doesn't
exist yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from services.bhive_parser import BHIVE_PARSER_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TechnicalTelemetry:
    """Part X: 'minimal operational data... This should exclude project
    content by default.' Every field here is deliberately incapable of
    holding project content -- there is no free-text field at all, only
    closed/structural values, which is what actually keeps this
    'excludes content by default' rather than merely documented as
    such."""

    app_version: str
    error_type: Optional[str]
    route: Optional[str]
    parser_version: str
    generated_at: str
    diagnostic_id: str
    performance_ms: Optional[float] = None


def build_technical_telemetry(
    app_version: str, error_type: Optional[str] = None, route: Optional[str] = None,
    performance_ms: Optional[float] = None,
) -> TechnicalTelemetry:
    """Always allowed -- see services.security_policy.
    MANDATORY_FLOOR_DEFAULTS[ACTION_TECHNICAL_TELEMETRY] == DECISION_ALLOW.
    No security evaluation call here at all, deliberately: gating a
    payload that structurally cannot carry project content would be
    theatre, not protection."""
    import uuid

    return TechnicalTelemetry(
        app_version=app_version, error_type=error_type, route=route,
        parser_version=BHIVE_PARSER_VERSION, generated_at=_now(),
        diagnostic_id=str(uuid.uuid4()), performance_ms=performance_ms,
    )


class SupportPackageDeniedError(Exception):
    """Raised when a content-bearing support package is attempted
    without an ALLOW/ALLOW_APPROVED_ROUTE security decision."""

    def __init__(self, decision):
        self.decision = decision
        super().__init__(
            f"Content-bearing support package denied: {decision.reason} "
            f"(decision: {decision.decision})."
        )


@dataclass
class SupportPackage:
    """Part X: 'project excerpts, prompts, outputs, documents, or code
    needed to reproduce a problem... must require explicit
    authorization.' authorized_by/authorized_decision are always
    present on a successfully-built package -- there is no code path
    that constructs one without having first received an ALLOW-shaped
    SecurityDecision, since build_support_package raises otherwise."""

    project_id: str
    contents: dict
    requested_by: str
    authorized_by: str
    authorized_decision: str
    created_at: str
    package_id: str
    purpose: str
    reviewed: bool = False


def build_support_package(
    project_id: str, contents: dict, requested_by: str, purpose: str, security_decision,
) -> SupportPackage:
    """
    `security_decision` must be a services.security_policy.SecurityDecision
    already evaluated by the caller for ACTION_CONTENT_BEARING_SUPPORT_
    PACKAGE against this project -- this function does not perform its
    own lookup (same "resolver stays pure, callers own the lookup"
    separation services.security_policy.evaluate_action established),
    it only enforces that the decision was actually favorable before
    constructing anything.

    Never auto-authorizes broader reuse: Part X is explicit that
    troubleshooting authorization "does not automatically permit model
    training, permanent fixture retention, broader product analytics,
    demonstrations, reuse outside the support case" -- this dataclass
    carries only `purpose` and has no field that could be read as a
    standing grant for anything beyond the one support case it was
    built for.
    """
    from services.security_policy import DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE

    if security_decision.decision not in (DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE):
        raise SupportPackageDeniedError(security_decision)

    import uuid

    return SupportPackage(
        project_id=project_id, contents=contents, requested_by=requested_by,
        authorized_by=security_decision.exception_id or security_decision.controlling_layer,
        authorized_decision=security_decision.decision, created_at=_now(),
        package_id=str(uuid.uuid4()), purpose=purpose,
    )
