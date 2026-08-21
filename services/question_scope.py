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

_APPLICATION_TERMS = (
    "archiosk", "application", "ui", "user interface", "developer mode",
    "template", "layout", "panel", "sidebar", "left side", "right side",
    "left-hand", "page", "screen", "workspace", "composer", "button",
    "menu", "icon", "css", "interface",
)
_PROJECT_TERMS = (
    "rfp", "project evidence", "document", "source", "requirement",
    "finding", "smoke control", "smoke management", "specification",
    "drawing", "contract", "submission", "what does", "what do",
)


@dataclass(frozen=True)
class QuestionScope:
    """Read-only classification result for diagnostics and future routing."""

    scope: str
    application_signals: tuple[str, ...] = ()
    project_signals: tuple[str, ...] = ()
    template_id: str | None = None


def _signals(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if re.search(r"\b" + re.escape(term) + r"\b", text))


def classify_question_scope(message: str, application_context: dict | None = None) -> QuestionScope:
    """Classify a message without granting routing or authority semantics.

    The active TPL is reported for observability, but never creates an
    APPLICATION signal by itself. Explicit message language remains necessary
    to classify an application question.
    """
    text = " ".join((message or "").lower().split())
    application_signals = _signals(text, _APPLICATION_TERMS)
    project_signals = _signals(text, _PROJECT_TERMS)
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
