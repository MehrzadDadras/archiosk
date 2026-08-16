"""
CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 0) - the one shared Anthropic call
boundary, extracted from what used to be three independently duplicated
copies of the identical pattern (services/requirement_investigation.py,
services/project_qa.py, services/project_briefing.py - each patterned,
by their own docstrings, after services/bhive_parser.py's original
precedent). Duplicating this exact ~20-line client-setup/error-handling
shape a fourth time (for the new Composer conversational turn) is the
point at which "simple and locally obvious" stops being true and starts
meaning "four places to fix identically the next time timeout handling
or a token-budget policy changes" - so it is centralized here instead,
and the three existing call sites are migrated onto it in this same
stage (behavior-preserving; their own test suites must pass unmodified).

Deliberately NOT centralized here: prompt construction (each caller has
a genuinely different evidence shape) and the external-AI governance
check (services/security_policy.py's evaluate_action via each caller's
own _evaluate_external_ai_policy wrapper) - that check stays a
per-call-site duplicate, matching its own already-documented precedent
in services/conversation_interpreter.py ("duplicated rather than shared
... since each has a different way of reaching the registry store
path"). This module has no opinion about governance at all - it is
purely the mechanical request/response boundary.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0
PROVIDER_NAME = "anthropic"


@dataclass
class LLMCallOutcome:
    """`ran=False` means no real model call completed - a skipped_reason
    is always set in that case, and `parsed`/`raw_text` are always None.
    Never a fabricated result. Callers parse their own domain-specific
    fields out of `parsed` (a plain dict from json.loads) into their own
    Result dataclass, exactly as they already did with the model's raw
    response before this extraction."""

    ran: bool
    parsed: Optional[dict] = None
    raw_text: Optional[str] = None
    skipped_reason: Optional[str] = None
    stop_reason: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    requested_at: Optional[str] = None


def resolve_timeout_from_env(explicit: Optional[float], default_seconds: float) -> float:
    """The one piece of env-resolution a caller needs BEFORE it can build
    its own request (e.g. services/project_briefing.py's own prompt-size
    timeout scaling, which needs a base timeout to scale from before the
    final, already-scaled value is handed to call_llm_json below - at
    that point call_llm_json must NOT re-resolve a fresh default and
    silently discard the caller's own scaling)."""
    if explicit is not None:
        return explicit
    return float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", default_seconds))


def scale_timeout_for_prompt_size(
    base_timeout: float,
    prompt: str,
    base_chars_before_scaling: float = 4000,
    seconds_per_extra_1000_chars: float = 3.0,
    max_timeout: float = 90.0,
) -> float:
    """CLAUDE-CA1D-COMPOSER-TIMEOUT-FIX-01: promoted here (from services/
    project_briefing.py's own private `_scale_timeout_for_prompt_size`,
    the only precedent for this) so a second call site
    (services/project_qa.py) doesn't grow a second, drifting copy of the
    same logic - same "one shared implementation" discipline
    call_llm_json/resolve_timeout_from_env above already established for
    Stage 0. Behavior-preserving for project_briefing.py's own call
    (identical formula, identical default constants); project_qa.py is
    the first caller to actually need this (see its own module comment -
    a real live Product Owner report: a genuinely large, multi-item
    "characterize every discrepancy in this project" question was hitting
    both max_tokens truncation AND this same flat, unscaled timeout).

    A compact prompt (<= base_chars_before_scaling) is untouched - the
    timeout only ever grows past base_timeout once the prompt is
    genuinely larger than that, and never past max_timeout regardless of
    size. Reused, not reinvented, rate/base-timeout tuning: any caller
    without a specific reason to differ should pass 3.0s/1000 extra chars
    and a 90s ceiling, project_briefing.py's own already-accepted values.
    """
    extra_chars = max(0, len(prompt) - base_chars_before_scaling)
    scaled = base_timeout + (extra_chars / 1000.0) * seconds_per_extra_1000_chars
    return min(scaled, max_timeout)


def call_llm_json(
    user_prompt: str,
    system_prompt: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
    max_tokens: int = 1500,
    log_label: str = "LLM call",
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
) -> LLMCallOutcome:
    """
    One request/response round trip - no tool use, no re-prompting, no
    multi-step orchestration (matches every existing Anthropic call in
    this app; see requirement_investigation.py's own docstring on why
    that stays out of scope here too). `timeout`, if given explicitly,
    is used as-is (see resolve_timeout_from_env above for why this
    function never re-derives its own default when a caller already
    resolved/scaled one) - if None, the standard ANTHROPIC_TIMEOUT_SECONDS
    env default applies, same as every migrated call site already did.

    CLAUDE-GO-MULTIMODAL-PERCEPTION-GAMES-01: `image_base64`/
    `image_media_type` are optional and, when both given, prepend a
    vision content block ahead of `user_prompt`'s own text block - the
    first and only place in this codebase that constructs one (see the
    Perception Games operational-map findings: no other call site in
    this app has ever sent an image to the model). Every existing caller
    that omits them is completely unaffected - `content` stays the exact
    same plain string it always was, not a list, so this is a strictly
    additive, backward-compatible change to the one shared gateway
    rather than a second call path.
    """
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return LLMCallOutcome(
            ran=False,
            skipped_reason=f"No ANTHROPIC_API_KEY configured - {log_label} cannot run in this deployment.",
        )

    model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    timeout = resolve_timeout_from_env(timeout, DEFAULT_TIMEOUT_SECONDS)
    requested_at = datetime.now(timezone.utc).isoformat()

    import anthropic  # imported lazily so the dep is optional in dev

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

    if image_base64 and image_media_type:
        content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": image_media_type, "data": image_base64},
            },
            {"type": "text", "text": user_prompt},
        ]
    else:
        content = user_prompt

    create_kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if system_prompt:
        create_kwargs["system"] = system_prompt

    try:
        response = client.messages.create(**create_kwargs)
    except anthropic.APITimeoutError:
        logger.warning("%s timed out after %.0fs.", log_label, timeout)
        return LLMCallOutcome(ran=False, skipped_reason=f"Request timed out after {timeout:.0f}s.")
    except Exception:  # noqa: BLE001 - best-effort, mirrors every migrated call site's own prior discipline
        logger.warning("%s failed.", log_label, exc_info=True)
        return LLMCallOutcome(ran=False, skipped_reason="An error occurred calling the model.")

    text_out = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    cleaned = re.sub(r"^```(json)?|```$", "", text_out.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        if response.stop_reason == "max_tokens":
            logger.warning("%s was truncated at max_tokens: %r", log_label, text_out[-200:])
            return LLMCallOutcome(
                ran=False, skipped_reason="Model's response was cut off before it finished (max_tokens).",
                stop_reason=response.stop_reason,
            )
        logger.warning("%s returned non-JSON output: %r", log_label, text_out[:200])
        return LLMCallOutcome(ran=False, skipped_reason="Model returned malformed output.")

    return LLMCallOutcome(
        ran=True, parsed=parsed, raw_text=text_out, stop_reason=response.stop_reason,
        provider=PROVIDER_NAME, model=model, requested_at=requested_at,
    )
