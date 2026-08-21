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

# These are affirmative application terms. Ambiguous construction words such
# as panel, screen, layout, page, document, and source are intentionally not
# standalone application signals.
_APPLICATION_TERMS = (
    "archiosk", "application", "app", "ui", "user interface",
    "developer mode", "template", "sidebar", "workspace", "composer",
    "button", "menu", "icon", "css", "interface",
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
            r"\b(?:create|open|close|delete|hide|show|remove|add|resize|"
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
)


@dataclass(frozen=True)
class QuestionScope:
    """Read-only classification result for diagnostics and future routing."""

    scope: str
    application_signals: tuple[str, ...] = ()
    project_signals: tuple[str, ...] = ()
    template_id: str | None = None


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


def classify_question_scope(message: str, application_context: dict | None = None) -> QuestionScope:
    """Classify a message without granting routing or authority semantics.

    The active TPL is reported for observability, but never creates an
    APPLICATION signal by itself. Explicit message language remains necessary
    to classify an application question.
    """
    text = " ".join((message or "").lower().split())
    application_signals = _application_signals(text)
    project_signals = _project_signals(text)
    if application_signals and project_signals:
        scope = QUESTION_SCOPE_MIXED
    elif application_signals:
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
        template_id=template_id,
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
    }
