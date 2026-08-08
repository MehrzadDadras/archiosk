"""
CLAUDE-POSTCAMEL-INVESTIGATION-AR1 - a concise, read-only orientation
recap ("Snapshot") for an ARCHIVED Investigation (Case), shown in the
"Continue from Archive" chooser before a reviewer decides whether to
derive a new active Investigation from it.

Mirrors services/project_qa.py's Anthropic integration pattern exactly
(lazy `anthropic` import, api_key/model/timeout read from the same env
vars, a prompt that demands strict JSON with no prose/markdown fences,
honest degrade-on-no-key/timeout/malformed-output) - reusing that
module's own honest-abstention mechanism rather than inventing a
second AI-governance path for this one feature, per this stage's own
explicit instruction.

Deliberately narrow and ephemeral: grounded ONLY in the archived Case's
own title/objective, its own Findings, and its own conversation - never
the model's world knowledge, never another Case's material, never
another Project's material. A human-asserted "fact" recorded in the
Case's conversation (e.g. a claimed municipal by-law change) is
evidence of what was DISCUSSED, not independently verified - the
prompt below tells the model explicitly not to upgrade a recorded
human statement into a confirmed fact.

Snapshot assists recall; it does not create authority (Section 10).
This module writes nothing: no Finding, no Task, no Work Product, no
ConversationMessage, no GovernanceLog entry, no mutation of the
archived Case or any other record. The caller (routes/workspace.py's
snapshot_archived_case) must only ever render this result as an
ephemeral page fragment, never persist it.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0
PROVIDER_NAME = "anthropic"

# A real, bump-on-meaningful-change marker, same discipline as
# services/project_qa.py's PROJECT_QA_PROMPT_VERSION.
INVESTIGATION_SNAPSHOT_PROMPT_VERSION = "ar1a"

_MAX_FINDINGS_IN_PROMPT = 30
_MAX_CONVERSATION_MESSAGES_IN_PROMPT = 40


@dataclass
class InvestigationSnapshotResult:
    """`ran=False` means no real reasoning happened - a skipped_reason
    is always set in that case. Mirrors ProjectQAResult's shape."""

    ran: bool
    summary: Optional[str] = None
    grounded_in: list[str] = field(default_factory=list)
    not_covered: Optional[str] = None
    skipped_reason: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    requested_at: Optional[str] = None


def build_archive_snapshot(
    case: dict,
    findings: list[dict],
    conversation: list[dict],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
) -> InvestigationSnapshotResult:
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return InvestigationSnapshotResult(
            ran=False,
            skipped_reason="No ANTHROPIC_API_KEY configured - a Snapshot cannot be generated in this deployment.",
        )

    model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    timeout = timeout if timeout is not None else float(
        os.getenv("ANTHROPIC_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    )
    requested_at = datetime.now(timezone.utc).isoformat()

    import anthropic  # imported lazily so the dep is optional in dev

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    prompt = _build_prompt(case, findings, conversation)

    try:
        response = client.messages.create(
            model=model, max_tokens=1200, messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APITimeoutError:
        logger.warning("Investigation Snapshot timed out after %.0fs.", timeout)
        return InvestigationSnapshotResult(ran=False, skipped_reason=f"Request timed out after {timeout:.0f}s.")
    except Exception:  # noqa: BLE001 - best-effort, mirrors project_qa.py's own discipline
        logger.warning("Investigation Snapshot failed.", exc_info=True)
        return InvestigationSnapshotResult(ran=False, skipped_reason="An error occurred calling the model.")

    text_out = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    cleaned = re.sub(r"^```(json)?|```$", "", text_out.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        if response.stop_reason == "max_tokens":
            logger.warning("Investigation Snapshot was truncated at max_tokens: %r", text_out[-200:])
            return InvestigationSnapshotResult(ran=False, skipped_reason="Model's response was cut off before it finished (max_tokens).")
        logger.warning("Investigation Snapshot returned non-JSON output: %r", text_out[:200])
        return InvestigationSnapshotResult(ran=False, skipped_reason="Model returned malformed output.")

    not_covered = parsed.get("not_covered")
    return InvestigationSnapshotResult(
        ran=True,
        summary=str(parsed.get("summary", "")).strip(),
        grounded_in=[str(g) for g in parsed.get("grounded_in", [])],
        not_covered=(str(not_covered).strip() or None) if not_covered else None,
        provider=PROVIDER_NAME, model=model, requested_at=requested_at,
    )


def _build_prompt(case: dict, findings: list[dict], conversation: list[dict]) -> str:
    lines = [
        "You are producing a brief orientation recap ('Snapshot') of an ARCHIVED "
        "Investigation for a construction/design professional who is deciding "
        "whether to continue work from it. This is a read-only recall aid, not a "
        "new Investigation and not verified evidence in its own right - answer "
        "ONLY from the governed material given below, never your own outside "
        "knowledge. If the material does not answer one of the questions below, "
        "say so plainly rather than guessing.",
        "",
        "IMPORTANT: any statement recorded below as something a human said or "
        "typed (in the conversation) is evidence that the statement was MADE, "
        "not that it is independently verified true (for example, a claim about "
        "a by-law, code, or client instruction is not itself confirmed "
        "legislation or a confirmed instruction merely because it was typed "
        "here). Report such statements as what was discussed/asserted, and do "
        "not upgrade them into confirmed fact.",
        "",
        f"Investigation title: {case.get('title', '')}",
        f"Investigation objective: {case.get('objective', '')}",
        f"Archived at: {case.get('archived_at', '')}",
    ]

    if findings:
        lines.append(
            f"\nFindings recorded in this Investigation ({len(findings)} total, "
            f"showing up to {_MAX_FINDINGS_IN_PROMPT}):"
        )
        for f in findings[:_MAX_FINDINGS_IN_PROMPT]:
            lines.append(f"- [{f.get('claim_status', '')}] {f.get('statement', '')}")
    else:
        lines.append("\nNo Findings were recorded in this Investigation.")

    if conversation:
        recent = conversation[-_MAX_CONVERSATION_MESSAGES_IN_PROMPT:]
        lines.append(
            f"\nDiscussion transcript ({len(conversation)} total messages, showing "
            f"the most recent {len(recent)}):"
        )
        for m in recent:
            speaker = "Reviewer" if m.get("role") == "human" else "System"
            lines.append(f"- {speaker}: {m.get('text', '')}")
    else:
        lines.append("\nNo discussion was recorded in this Investigation.")

    lines.append(
        "\nRespond ONLY with a JSON object, no prose, no markdown fences: "
        '{"summary": "<a concise recap covering, to the extent the material above '
        "supports it: what this Investigation was about, what evidence/documents "
        "were examined, what Findings were reached, what remained unresolved, and "
        "what a new Investigation continuing from this archive would inherit by "
        'lineage>", "grounded_in": ["<short pointer to which Finding(s) or '
        'discussion turn(s) above support each part of the summary>", ...], '
        '"not_covered": "<which of those questions the material above does not '
        'answer, or empty string if all are reasonably covered>"}. Do not invent '
        "content the material above does not contain."
    )
    return "\n".join(lines)
