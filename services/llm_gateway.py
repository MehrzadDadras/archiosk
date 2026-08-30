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

import base64
import binascii
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0

# CLAUDE-GEMINI-VISION-01: this module is now a two-provider boundary.
# PROVIDER_NAME is kept, unchanged, as the Anthropic value - it is read
# by services/cross_modal_investigation.py and services/investigation_
# snapshot.py, which define their own local copies of the same constant
# and stamp it into their results; renaming it here would be a silent
# provenance change in stored records, not a tidy-up.
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GEMINI = "gemini"
PROVIDER_NAME = PROVIDER_ANTHROPIC
KNOWN_PROVIDERS = (PROVIDER_ANTHROPIC, PROVIDER_GEMINI)

# Vision calls carry a rendered drawing page, so they are slower than the
# text-only reasoning calls DEFAULT_TIMEOUT_SECONDS was tuned for. A
# separate default rather than raising the shared one - nothing about
# adding a second provider should quietly lengthen every existing
# Anthropic call site's timeout.
DEFAULT_GEMINI_TIMEOUT_SECONDS = 60.0
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


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
    if os.getenv("AI_CALLS_DISABLED", "false").strip().lower() == "true":
        return LLMCallOutcome(
            ran=False,
            skipped_reason=f"AI_CALLS_DISABLED is set - {log_label} was blocked locally.",
        )
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
    return _finish_json_outcome(
        text_out=text_out, stop_reason=response.stop_reason,
        truncated=(response.stop_reason == "max_tokens"),
        log_label=log_label, provider=PROVIDER_ANTHROPIC, model=model,
        requested_at=requested_at,
    )


def _finish_json_outcome(
    text_out: str,
    stop_reason: Optional[str],
    truncated: bool,
    log_label: str,
    provider: str,
    model: str,
    requested_at: str,
) -> LLMCallOutcome:
    """
    CLAUDE-GEMINI-VISION-01: the fence-stripping / JSON-parsing /
    truncation-vs-malformed distinction, extracted verbatim from the
    Anthropic path above so the Gemini path cannot drift from it. This
    is the same "one implementation instead of N" discipline that
    produced this module in the first place - a second provider is
    exactly the moment that discipline would otherwise be quietly
    abandoned.

    Behavior for the Anthropic caller is unchanged: `truncated` is
    simply the `stop_reason == "max_tokens"` test that used to be
    inline. Providers report truncation differently (Gemini uses a
    finish_reason enum), so the CALLER decides what truncation means
    for its own API and this function only decides what to do about it.
    """
    cleaned = re.sub(r"^```(json)?|```$", "", (text_out or "").strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        if truncated:
            logger.warning("%s was truncated at max_tokens: %r", log_label, (text_out or "")[-200:])
            return LLMCallOutcome(
                ran=False, skipped_reason="Model's response was cut off before it finished (max_tokens).",
                stop_reason=stop_reason,
            )
        logger.warning("%s returned non-JSON output: %r", log_label, (text_out or "")[:200])
        return LLMCallOutcome(ran=False, skipped_reason="Model returned malformed output.")

    return LLMCallOutcome(
        ran=True, parsed=parsed, raw_text=text_out, stop_reason=stop_reason,
        provider=provider, model=model, requested_at=requested_at,
    )


def _import_google_genai():
    """
    CLAUDE-GEMINI-VISION-01: the lazy-import seam for `google-genai`,
    a named function rather than a bare inline `import` (which is how
    the Anthropic path does it) for one concrete reason: `anthropic` is
    installed, so its tests patch `anthropic.Anthropic` directly, while
    `google-genai` is a genuinely optional pin that may be absent from a
    given venv. A test - and the running app - must both behave
    correctly when the package simply is not there, and a seam is the
    only way to exercise that honestly without requiring the package to
    prove it degrades when the package is missing.

    Returns (genai, types). Raises ImportError, which call_gemini_json
    converts into an honest skipped_reason rather than a traceback.
    """
    from google import genai
    from google.genai import types

    return genai, types


def call_gemini_json(
    user_prompt: str,
    system_prompt: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
    max_tokens: int = 1500,
    log_label: str = "Gemini call",
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
) -> LLMCallOutcome:
    """
    CLAUDE-GEMINI-VISION-01: the Gemini half of this boundary. Signature
    is deliberately IDENTICAL to call_llm_json's, and the return type is
    the same LLMCallOutcome - that parity is what lets
    call_provider_json below be a real dispatcher rather than two call
    paths wearing a shared name, and it is why the image is taken as
    base64 here (Gemini's own SDK wants raw bytes, so this function
    decodes internally) instead of exposing a second image convention
    that callers would have to branch on.

    Every honest-degrade path the Anthropic side already guarantees is
    reproduced, plus one specific to this provider:

      - AI_CALLS_DISABLED set          -> ran=False (the kill switch was
                                          never Anthropic-specific)
      - no GEMINI_API_KEY              -> ran=False
      - `google-genai` not installed   -> ran=False, named plainly
      - timeout / transport error      -> ran=False
      - truncated at max_output_tokens -> ran=False, never a partial parse
      - non-JSON output                -> ran=False

    A skipped_reason is always set when ran=False, and parsed/raw_text
    are always None. Never a fabricated result - the identical contract
    to the Anthropic path, which is the point of sharing LLMCallOutcome
    rather than inventing a GeminiCallOutcome.

    This function does NOT consult services/security_policy.py. Neither
    does call_llm_json - the governance check is the caller's, exactly
    as this module's own docstring already states ("This module has no
    opinion about governance at all"). services/sheet_vision.py holds
    the ACTION_GEMINI_VISION_REQUEST gate for the one caller that
    actually transmits drawing content.
    """
    if os.getenv("AI_CALLS_DISABLED", "false").strip().lower() == "true":
        return LLMCallOutcome(
            ran=False,
            skipped_reason=f"AI_CALLS_DISABLED is set - {log_label} was blocked locally.",
        )
    api_key = api_key or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return LLMCallOutcome(
            ran=False,
            skipped_reason=f"No GEMINI_API_KEY configured - {log_label} cannot run in this deployment.",
        )

    model = model or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    if timeout is None:
        timeout = float(os.getenv("GEMINI_TIMEOUT_SECONDS", DEFAULT_GEMINI_TIMEOUT_SECONDS))
    requested_at = datetime.now(timezone.utc).isoformat()

    try:
        genai, types = _import_google_genai()
    except ImportError:
        logger.warning("%s: google-genai is not installed.", log_label)
        return LLMCallOutcome(
            ran=False,
            skipped_reason=(
                "The google-genai package is not installed - "
                f"{log_label} cannot run in this deployment."
            ),
        )

    # google-genai expresses its HTTP timeout in MILLISECONDS, unlike
    # anthropic's seconds. Converting here - rather than asking callers
    # to know which provider wants which unit - is what keeps `timeout`
    # a single meaning, seconds, across this whole module.
    try:
        http_options = types.HttpOptions(
            timeout=int(timeout * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
        )
    except (AttributeError, TypeError):
        # CLAUDE-GEMINI-VISION-HARDENING-01: FAIL CLOSED, deliberately.
        #
        # `attempts=1` means "try once, never retry". Without it the SDK
        # may transparently re-send on a transport error, and for the one
        # caller that matters here - services/sheet_vision.py - each send
        # is a fresh transmission of a project's drawing to Google under
        # a SINGLE human approval. A retry is therefore not a resilience
        # detail, it is egress the reviewer authorized once and received
        # several times.
        #
        # If this SDK build cannot express that, the honest answer is
        # that the guarantee does not hold, so no call is made. Degrading
        # to "send anyway and hope" would silently trade the property the
        # approval gate exists to provide. The operator gets a named
        # reason and a version to fix, not a quiet weakening.
        logger.error(
            "%s: this google-genai build does not support HttpRetryOptions, so automatic "
            "retries cannot be disabled. Refusing to call rather than risk repeated egress.",
            log_label,
        )
        return LLMCallOutcome(
            ran=False,
            skipped_reason=(
                "This google-genai version cannot disable automatic retries, which is "
                "required before content may be transmitted. Install the pinned version "
                "from requirements.txt."
            ),
        )

    try:
        client = genai.Client(api_key=api_key, http_options=http_options)
    except Exception:  # noqa: BLE001 - an SDK surface mismatch must not 500 a request
        logger.warning("%s: could not construct the Gemini client.", log_label, exc_info=True)
        return LLMCallOutcome(ran=False, skipped_reason="An error occurred calling the model.")

    contents = []
    if image_base64 and image_media_type:
        try:
            image_bytes = base64.b64decode(image_base64, validate=True)
        except (binascii.Error, ValueError):
            logger.warning("%s was given undecodable image data.", log_label)
            return LLMCallOutcome(ran=False, skipped_reason="Image data could not be decoded.")
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=image_media_type))
    contents.append(user_prompt)

    config_kwargs = {
        # The direct counterpart of anthropic's max_tokens. Named
        # differently by the provider; the caller's single `max_tokens`
        # argument governs both, so a token budget means the same thing
        # whichever provider serves the request.
        "max_output_tokens": max_tokens,
        # Both call paths in this module exist to return parseable JSON.
        # Gemini can be told that directly, which the Anthropic API has
        # no equivalent for. _finish_json_outcome still strips fences and
        # still refuses malformed output either way, so this is a
        # reliability improvement, never a reason to trust output more.
        "response_mime_type": "application/json",
    }
    if system_prompt:
        config_kwargs["system_instruction"] = system_prompt

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )
    except Exception:  # noqa: BLE001 - same best-effort discipline as the Anthropic path
        logger.warning("%s failed.", log_label, exc_info=True)
        return LLMCallOutcome(ran=False, skipped_reason="An error occurred calling the model.")

    finish_reason = _gemini_finish_reason(response)
    return _finish_json_outcome(
        text_out=getattr(response, "text", None) or "",
        stop_reason=finish_reason,
        truncated=(finish_reason == "MAX_TOKENS"),
        log_label=log_label, provider=PROVIDER_GEMINI, model=model,
        requested_at=requested_at,
    )


def _gemini_finish_reason(response) -> Optional[str]:
    """Normalizes Gemini's own finish_reason (an enum on the first
    candidate) to the plain uppercase string LLMCallOutcome.stop_reason
    already carries, so a stored record reads the same shape whichever
    provider produced it. Returns None when the response carries no
    candidate at all - not itself an error here: _finish_json_outcome
    then correctly classifies the empty body as malformed output rather
    than as a truncation."""
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    raw = getattr(candidates[0], "finish_reason", None)
    if raw is None:
        return None
    return str(getattr(raw, "name", raw)).upper()


def call_provider_json(
    provider: str,
    user_prompt: str,
    **kwargs,
) -> LLMCallOutcome:
    """
    CLAUDE-GEMINI-VISION-01: dispatch to one of KNOWN_PROVIDERS, keeping
    LLMCallOutcome as the single contract a caller has to understand.

    Kept deliberately thin, and NOT given a fallback chain: if a caller
    asked for Gemini and Gemini cannot run, this returns Gemini's own
    honest skipped_reason rather than silently re-routing to Anthropic.
    Automatic cross-provider fallback would mean content reaching a
    provider the caller did not name and - more to the point - one that
    ACTION_GEMINI_VISION_REQUEST governs while ACTION_EXTERNAL_AI_REQUEST
    does not, which is a governance bypass dressed up as resilience.
    Choosing a different provider after a failure is a caller's decision
    to make explicitly, with its own gate check.

    An unknown provider name is a programming error, not a runtime
    condition to degrade around, so it raises.
    """
    if provider not in KNOWN_PROVIDERS:
        raise ValueError(
            f"{provider!r} is not a known provider (expected one of {KNOWN_PROVIDERS})."
        )
    if provider == PROVIDER_GEMINI:
        return call_gemini_json(user_prompt=user_prompt, **kwargs)
    return call_llm_json(user_prompt=user_prompt, **kwargs)
