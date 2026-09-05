"""
The seam between semantic question-fit assessment and the stored Script verdict.

Two halves already existed and nothing joined them:
`cross_modal_investigation.assess_question_fit` produces a verdict and is given
no workspace, store or identifier, so it cannot reach anything; and
`CaseWorkspaceStore.record_script_fit_verdict` stores one. This module is the
join, and it is deliberately the only place that knows about both.

WHY THE POLICY DECISION IS A PARAMETER AND NOT A LOOKUP

`routes/workspace.py`'s own `_evaluate_security_action` docstring already
explains that the ingestion gate and the route gate "share the resolver, not the
lookup boilerplate", and judged a shared helper needing a Flask app-context
parameter to be worse than four duplicated lookup lines. Doing that lookup a
third time here would be the copy that comment warns about, and would drag
`current_app` into a service that has no other reason to know Flask exists.

So the caller resolves `ACTION_EXTERNAL_AI_REQUEST` and hands the decision in;
this module *enforces* it. The allow set is imported from
`services.security_policy` rather than restated, so what counts as permission
stays defined in one place. The separation the assessment function established
is preserved exactly: assessment is a pure advisory operation, the caller owns
policy, and this seam owns persistence.

WHAT THIS MAY CAUSE (GOV-P-006)

Nothing, except the recording of a verdict. It does not touch readiness, does
not validate, does not adopt a Claim, and does not alter any WorkProduct
lifecycle state. A model assessment may constrain a governed transition and may
never authorize one, and the way that is guaranteed here is by this function
having no code that could: the only store method it calls is
`record_script_fit_verdict`.

WHEN POLICY SAYS NO

The model is not called at all, and the outcome is REVIEW_NEEDED with an honest
reason - never a fabricated PASS or FAIL. That is the same degrade shape
`assess_question_fit` already applies to a missing key or a timeout, for the
same reason: a verdict nobody produced is not a verdict, and a policy refusal
tells you nothing about whether the Script answers its question.
"""
from __future__ import annotations

from typing import Optional

from services.case_workspace import (
    CaseWorkspaceStore,
    ProjectWorkspace,
    SCRIPT_CHECK_REVIEW_NEEDED,
)
from services.cross_modal_investigation import QuestionFitResult, assess_question_fit
from services.security_policy import DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE

# Mirrors routes/workspace.py's own `_external_ai_status` reading of the same
# gate, deliberately rather than coincidentally: REQUIRE_APPROVAL is NOT an
# allow here either. An approval that has not been given yet is not permission,
# and inventing a more permissive reading in a second place is how two call
# sites quietly stop enforcing the same policy.
_ALLOWED_DECISIONS = (DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE)


def assess_and_record_question_fit(
    store: CaseWorkspaceStore,
    workspace: ProjectWorkspace,
    work_product_id: str,
    question: str,
    policy_decision: str,
    script_text: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
    record: bool = True,
) -> dict:
    """Assess a Script's question fit under policy, and record the verdict.

    `script_text` is derived from the Script's own active scene sections when
    not supplied, so the text assessed is the text stored rather than whatever a
    caller chose to pass - the verdict is bound to the same content the
    checksum covers.

    Returns the stored verdict record, or the unstored equivalent when the
    assessment could not run. `record=False` assesses without storing, for a
    caller that wants a look before committing one.
    """
    script = store.get_work_product(workspace, work_product_id)
    if script is None:
        raise ValueError("No work product %s in this project." % work_product_id)

    if script_text is None:
        script_text = script_narrative_text(script)

    if policy_decision not in _ALLOWED_DECISIONS:
        result = QuestionFitResult(
            outcome=SCRIPT_CHECK_REVIEW_NEEDED,
            reason=(
                "Question fit could not be assessed: external AI requests are not "
                "permitted for this project (policy decision %r)." % policy_decision
            ),
            ran=False,
            skipped_reason="Policy decision %r does not permit an external AI request." % policy_decision,
        )
    else:
        result = assess_question_fit(
            question=question, script_text=script_text, api_key=api_key,
            model=model, timeout=timeout,
        )

    if not record:
        return _as_unstored(result, question)

    return store.record_script_fit_verdict(
        workspace, work_product_id=work_product_id,
        outcome=result.outcome, reason=result.reason,
        assessed_by=result.provider or "policy", question=question,
        ran=result.ran, provider=result.provider, model=result.model,
    )


def script_narrative_text(script: dict) -> str:
    """The Script's narratable text, in order - active scene sections only.

    Directions are excluded on purpose: they instruct a renderer and assert
    nothing, so including them would ask the model to judge whether a camera
    note answers a question.
    """
    scenes = sorted(
        (s for s in script.get("sections", [])
         if s.get("section_type") == "scene" and not s.get("removed")),
        key=lambda s: s.get("order_index", 0),
    )
    return "\n".join(
        str(s.get("content", {}).get("text", "")).strip()
        for s in scenes
        if str(s.get("content", {}).get("text", "")).strip()
    )


def _as_unstored(result: QuestionFitResult, question: str) -> dict:
    """The same shape record_script_fit_verdict returns, minus the checksum -
    which is deliberately absent, so an unstored verdict can never be mistaken
    for one that applies to a Script."""
    return {
        "outcome": result.outcome,
        "reason": result.reason,
        "assessed_by": result.provider or "policy",
        "assessed_at": result.requested_at,
        "content_checksum": None,
        "question": question,
        "ran": result.ran,
        "provider": result.provider,
        "model": result.model,
        "stored": False,
    }
