"""Advisory question-scope classification.

This is deliberately a small, deterministic diagnostic seam. It does not
select an answer path, invoke a model, inspect project evidence, authorize a
mutation, or change any existing Composer/workspace routing.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


QUESTION_SCOPE_APPLICATION = "APPLICATION"
QUESTION_SCOPE_PROJECT = "PROJECT"
QUESTION_SCOPE_MIXED = "MIXED"
QUESTION_SCOPE_UNKNOWN = "UNKNOWN"

APPLICATION_EVIDENCE_NONE = "NONE"
APPLICATION_EVIDENCE_AMBIGUOUS = "AMBIGUOUS"
APPLICATION_EVIDENCE_AFFIRMATIVE = "AFFIRMATIVE"

# These are affirmative application terms. Ambiguous construction words such
# as panel, screen, layout, page, document, and source are intentionally not
# standalone application signals.
_APPLICATION_TERMS = (
    "archiosk", "ui", "user interface", "developer mode", "sidebar",
    "composer", "css",
)

# These terms occur in both application and construction language. They only
# become application evidence when corroborated by an unambiguous UI pattern.
_CORROBORATION_APPLICATION_TERMS = (
    "application", "template", "workspace", "interface", "menu", "button",
    "icon",
)

# Project vocabulary is represented as audited singular/plural variants. This
# avoids a broad stemmer while preserving understandable diagnostic labels.
_PROJECT_SIGNAL_VARIANTS = {
    "rfp": ("rfp",),
    "project evidence": ("project evidence",),
    "document": ("document", "documents"),
    "source": ("source", "sources"),
    "requirement": ("requirement", "requirements"),
    "finding": ("finding", "findings"),
    "smoke control": ("smoke control",),
    "smoke management": ("smoke management",),
    "specification": ("specification", "specifications"),
    "drawing": ("drawing", "drawings"),
    "contract": ("contract", "contracts"),
    "submission": ("submission", "submissions"),
    "what does": ("what does",),
    "what do": ("what do",),
}

# Ambiguous interface/construction vocabulary becomes an application signal
# only when paired with an affirmative UI action or spatial UI language.
_APPLICATION_PATTERNS = (
    (
        "ui-action",
        re.compile(
            r"\b(?:create|close|delete|hide|remove|add|resize|"
            r"move|restore|collapse|expand)\b.{0,60}\b(?:panel|sidebar|"
            r"menu|button|composer|workspace|icon)\b"
        ),
    ),
    (
        "ui-spatial",
        re.compile(r"\b(?:left|right|bottom|top)\s+(?:side|panel|sidebar|rail|column)\b"),
    ),
    (
        "ui-placement",
        re.compile(
            r"\b(?:put|place|move|display|show)\b.{0,60}\b(?:panel|sidebar|workspace)\b"
        ),
    ),
    (
        "ui-referent",
        re.compile(r"\bthis\s+(?:button|menu|icon|sidebar|composer)\b"),
    ),
)

_AMBIGUOUS_UI_MARKERS = (
    "note", "schedule", "detail", "locations", "layout", "general notes",
)

# Built-work vocabulary is a negative-only safety veto. It is intentionally
# not included in project signals and can never create PROJECT classification.
_BUILT_WORK_TERMS = (
    "electrical", "mechanical", "structural", "architectural", "civil", "hvac",
    "fire alarm", "damper", "switchgear", "generator", "ductwork", "exhaust",
    "pressurization", "sprinkler", "guardrail", "column", "slab", "mezzanine",
    "atrium", "corridor", "stair", "shaft", "door", "wall", "roof", "elevation",
    "framing", "grid line", "control room", "officer station", "building",
    "occupancy", "egress", "schedule", "addendum", "obc", "code", "division",
    "permit", "detention", "commissioning", "sheet", "csi", "contractor", "bidder",
    "substitution", "alternative solution", "rfi", "shop drawing",
)


@dataclass(frozen=True)
class QuestionScope:
    """Read-only classification result for diagnostics and future routing."""

    scope: str
    application_signals: tuple[str, ...] = ()
    project_signals: tuple[str, ...] = ()
    built_work_signals: tuple[str, ...] = ()
    template_id: str | None = None
    application_evidence: str = APPLICATION_EVIDENCE_NONE


SCOPE_DIAGNOSTIC_STATUS = "ADVISORY_NON_AUTHORIZING_NOT_ROUTING"


def _contains_term(text: str, term: str) -> bool:
    return re.search(r"\b" + re.escape(term) + r"\b", text) is not None


def _signals(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    """Return exact lexical signals for the small explicit vocabulary."""
    return tuple(term for term in terms if _contains_term(text, term))


def _project_signals(text: str) -> tuple[str, ...]:
    return tuple(
        label
        for label, variants in _PROJECT_SIGNAL_VARIANTS.items()
        if any(_contains_term(text, variant) for variant in variants)
    )


def _application_signals(text: str) -> tuple[str, ...]:
    signals = list(_signals(text, _APPLICATION_TERMS))
    signals.extend(label for label, pattern in _APPLICATION_PATTERNS if pattern.search(text))
    return tuple(dict.fromkeys(signals))


def _built_work_signals(text: str) -> tuple[str, ...]:
    return _signals(text, _BUILT_WORK_TERMS)


def _application_evidence(
    text: str,
    application_signals: tuple[str, ...],
    project_signals: tuple[str, ...],
    built_work_signals: tuple[str, ...],
) -> str:
    """Characterize application evidence without granting routing authority."""
    safe_terms = set(_signals(text, _APPLICATION_TERMS))
    if safe_terms:
        return APPLICATION_EVIDENCE_AFFIRMATIVE

    # A create/delete/etc. UI action is affirmative only when construction
    # vocabulary does not make the target plausibly a built-work object.
    if (
        "ui-action" in application_signals
        and not built_work_signals
        and not any(_contains_term(text, marker) for marker in _AMBIGUOUS_UI_MARKERS)
    ):
        return APPLICATION_EVIDENCE_AFFIRMATIVE

    # Placement language becomes affirmative only when a project signal makes
    # the cross-scope intent explicit. Without that corroboration it remains
    # legitimately ambiguous (for example, "move the panel note").
    if "ui-placement" in application_signals and project_signals and not built_work_signals:
        return APPLICATION_EVIDENCE_AFFIRMATIVE

    if application_signals or any(
        _contains_term(text, term) for term in _CORROBORATION_APPLICATION_TERMS
    ):
        return APPLICATION_EVIDENCE_AMBIGUOUS
    return APPLICATION_EVIDENCE_NONE


def classify_question_scope(message: str, application_context: dict | None = None) -> QuestionScope:
    """Classify a message without granting routing or authority semantics.

    The active TPL is reported for observability, but never creates an
    APPLICATION signal by itself. Explicit message language remains necessary
    to classify an application question.
    """
    text = " ".join((message or "").lower().split())
    application_signals = _application_signals(text)
    project_signals = _project_signals(text)
    built_work_signals = _built_work_signals(text)
    application_evidence = _application_evidence(
        text, application_signals, project_signals, built_work_signals
    )
    effective_application = application_evidence == APPLICATION_EVIDENCE_AFFIRMATIVE
    if effective_application and project_signals:
        scope = QUESTION_SCOPE_MIXED
    elif effective_application:
        scope = QUESTION_SCOPE_APPLICATION
    elif project_signals:
        scope = QUESTION_SCOPE_PROJECT
    else:
        scope = QUESTION_SCOPE_UNKNOWN

    template_id = None
    if isinstance(application_context, dict):
        identity = application_context.get("template_identity")
        if isinstance(identity, dict):
            template_id = identity.get("template_id")
        elif isinstance(application_context.get("template_id"), str):
            template_id = application_context["template_id"]
    return QuestionScope(
        scope=scope,
        application_signals=application_signals,
        project_signals=project_signals,
        built_work_signals=built_work_signals,
        template_id=template_id,
        application_evidence=application_evidence,
    )


def scope_diagnostic(message: str, application_context: dict | None = None) -> dict:
    """Return a bounded, inspectable diagnostic envelope for one turn."""
    result = classify_question_scope(message, application_context)
    return {
        "classification": result.scope,
        "status": SCOPE_DIAGNOSTIC_STATUS,
        "template_id": result.template_id,
        "application_signals": result.application_signals,
        "project_signals": result.project_signals,
        "built_work_signals": result.built_work_signals,
        "application_evidence": result.application_evidence,
    }
