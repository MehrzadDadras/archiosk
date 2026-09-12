"""CLAUDE-FEASIBILITY-EGRESS-02 - PydanticAI orchestrates, llm_gateway egresses.

    Agent(output_type=...)  ->  GatewayModel  ->  llm_gateway.call_provider_json
                                                  -> the ONE governed boundary

THE CORRECTION THIS MODULE IS. Version 1 of `feasibility_compiler` built
`GoogleModel(provider=GoogleProvider(api_key=...))` and called Google directly.
That worked, and it was wrong: it created a SECOND production egress path in a
repository that deliberately has one, and it routed around `services/llm_gateway.py`
- and with it the `AI_CALLS_DISABLED` kill switch, the honest-degrade contract,
the timeout policy, and the provider dispatch that exists precisely so content
cannot reach a provider the caller did not name. A bypass that happens to work is
still a bypass; it simply fails later and further from the decision that caused it.

WHY A `Model` SUBCLASS RATHER THAN A FORK. `pydantic_ai.models.Model` is a public
abstract base with exactly three members - `model_name`, `system`, and
`request(messages, model_settings, model_request_parameters) -> ModelResponse`.
Implementing it is the framework's own supported extension point, so nothing here
monkey-patches internals or pins to private structure. Verified against the
installed 2.43.0 API by inspection, not from examples.

WHAT THIS ADAPTER REFUSES TO PRETEND. The gateway speaks one shape: a prompt in, a
parsed JSON object out, or an honest `ran=False` with a reason. It cannot make
tool calls. So if PydanticAI asks for function tools or output tools, this raises
instead of silently dropping them - a model that quietly ignores the tools it was
given is worse than one that admits it has none. In this application there are
never any (the compiler declares zero tools), which makes the check cheap and the
guarantee real.

DEGRADATION IS CARRIED, NOT INVENTED. `ran=False` becomes `GatewayUnavailable`
with the gateway's own `skipped_reason` attached, so "no GEMINI_API_KEY",
"google-genai not installed", "AI_CALLS_DISABLED", a timeout and a truncated
response stay distinguishable all the way up into the compiler's failure envelope.
Nothing here fabricates a response, and nothing here decides governance - the
gateway's own docstring is explicit that it has no opinion about governance, and
this adapter inherits exactly that silence. The authorization gate belongs to the
compiler, which is the caller.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from services import llm_gateway

logger = logging.getLogger(__name__)

ADAPTER_VERSION = "gateway-model@1"

#: The gateway's own provider vocabulary, which is NOT the provider SDK's.
#: `llm_gateway.KNOWN_PROVIDERS` is ("anthropic", "gemini"); PydanticAI and the
#: Google SDK say "google". Version 1 of the compiler defaulted to "google" and
#: would have raised `ValueError: 'google' is not a known provider` the first time
#: it was routed here - a mismatch that only a real integration surfaces.
PROVIDER_ALIASES = {"google": llm_gateway.PROVIDER_GEMINI,
                    "google-genai": llm_gateway.PROVIDER_GEMINI,
                    "gemini": llm_gateway.PROVIDER_GEMINI,
                    "anthropic": llm_gateway.PROVIDER_ANTHROPIC,
                    "claude": llm_gateway.PROVIDER_ANTHROPIC}


class GatewayUnavailable(RuntimeError):
    """The governed gateway declined to run, carrying its own reason.

    Deliberately NOT a fabricated empty response. `skipped_reason` is the
    gateway's own words so the compiler can classify a missing credential apart
    from a timeout apart from the kill switch.
    """

    def __init__(self, skipped_reason, *, provider=None, model=None):
        super().__init__(skipped_reason or "gateway declined without a reason")
        self.skipped_reason = skipped_reason
        self.provider = provider
        self.model = model


class GatewayCapabilityError(RuntimeError):
    """PydanticAI asked for something the governed boundary cannot do."""


def resolve_provider(name) -> str:
    """Map a configured provider name onto the gateway's vocabulary."""
    resolved = PROVIDER_ALIASES.get(str(name or "").strip().lower())
    if resolved is None:
        raise GatewayCapabilityError(
            "provider %r does not map onto the governed gateway (known: %s)"
            % (name, ", ".join(sorted(set(PROVIDER_ALIASES.values())))))
    return resolved


def _text_of(content) -> str:
    """Flatten a prompt part's content without inventing structure."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        return "\n".join(_text_of(item) for item in content)
    text = getattr(content, "text", None)
    return text if isinstance(text, str) else str(content)


def flatten_messages(messages, model_request_parameters=None) -> tuple:
    """(system_prompt, user_prompt) from PydanticAI's message list.

    The gateway takes one system prompt and one user prompt, which is all this
    single-turn compile needs. Instructions and system parts become the system
    prompt; user parts become the user prompt, in order.
    """
    system_parts, user_parts = [], []
    for message in messages or []:
        instructions = getattr(message, "instructions", None)
        if instructions:
            system_parts.append(_text_of(instructions))
        for part in getattr(message, "parts", None) or []:
            kind = getattr(part, "part_kind", "") or ""
            content = getattr(part, "content", None)
            if kind == "system-prompt":
                system_parts.append(_text_of(content))
            elif kind == "user-prompt":
                user_parts.append(_text_of(content))
            elif kind == "retry-prompt":
                # A STRUCTURAL retry only. PydanticAI emits this when its own
                # output parsing failed; it never carries VR-01..VR-20 findings,
                # because those are evaluated after this module has returned and
                # are never fed back - see feasibility_compiler section 10.
                user_parts.append(_text_of(content))
    for part in getattr(model_request_parameters, "instruction_parts", None) or []:
        system_parts.append(_text_of(getattr(part, "content", part)))

    system = "\n\n".join(p for p in system_parts if p).strip() or None
    user = "\n\n".join(p for p in user_parts if p).strip()
    return system, user


try:
    from pydantic_ai.models import Model as _PydanticAIModel
    PYDANTIC_AI_AVAILABLE = True
except Exception:  # noqa: BLE001 - absence is a supported state, not an error
    _PydanticAIModel = object
    PYDANTIC_AI_AVAILABLE = False


class _GatewayModelBase:
    """All of the behaviour, independent of whether the framework is installed.

    Kept separate from the subclass below because `__bases__` cannot be
    reassigned from `object` to a class with a different deallocator - a real
    CPython constraint that a conditional class definition sidesteps cleanly,
    where a clever late binding does not.
    """

    def __init__(self, model_name, *, provider="gemini", api_key=None,
                 timeout=None, max_tokens=4000, log_label="feasibility compile",
                 caller=None):
        self._model_name = model_name
        # NOT `_provider`: `pydantic_ai.models.Model.provider` returns
        # `getattr(self, '_provider', None)` and expects a Provider OBJECT
        # with a `model_profile()` method. Storing a provider NAME there
        # shadowed the base class's own attribute and surfaced as
        # `AttributeError: 'str' object has no attribute 'model_profile'`
        # from deep inside profile resolution. Subclassing a framework base
        # makes its private attribute names part of the contract.
        self._gateway_provider = resolve_provider(provider)
        self._api_key = api_key
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._log_label = log_label
        #: Injectable so tests never touch a network and never need the
        #: framework's own fakes to prove the gateway is what was called.
        self._caller = caller or llm_gateway.call_provider_json
        self.calls = []

    # -- the three abstract members of pydantic_ai.models.Model ------------
    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def system(self) -> str:
        return self._gateway_provider

    @property
    def provider(self):
        """None, deliberately. PydanticAI resolves a ModelProfile from a provider
        object; the governed gateway is not one and publishes no profile, and the
        framework's own resolution handles `provider is None`. Returning something
        profile-shaped here would be inventing capability metadata."""
        return None

    async def request(self, messages, model_settings, model_request_parameters):
        """The ONE egress point. Async because the base class is; the work is not.

        `call_provider_json` is synchronous and stays synchronous - there is no
        thread pool and no event-loop work here, so nothing about this adapter
        requires the application's threaded worker model to change.
        """
        self._refuse_unsupported(model_request_parameters)
        system_prompt, user_prompt = flatten_messages(
            messages, model_request_parameters)

        outcome = self._caller(
            self._gateway_provider,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            api_key=self._api_key,
            model=self._model_name,
            timeout=self._timeout,
            max_tokens=self._max_tokens,
            log_label=self._log_label,
        )
        self.calls.append({"provider": self._gateway_provider, "model": self._model_name,
                           "ran": getattr(outcome, "ran", None)})

        if not getattr(outcome, "ran", False):
            raise GatewayUnavailable(getattr(outcome, "skipped_reason", None),
                                     provider=getattr(outcome, "provider", None),
                                     model=getattr(outcome, "model", None))

        text = outcome.raw_text
        if not text and outcome.parsed is not None:
            text = json.dumps(outcome.parsed, ensure_ascii=False)
        if not text:
            raise GatewayUnavailable(
                "gateway reported ran=True with no content",
                provider=outcome.provider, model=outcome.model)
        return self._response(text, outcome)

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _refuse_unsupported(model_request_parameters):
        """The governed boundary cannot make tool calls. Say so; never drop them."""
        if model_request_parameters is None:
            return
        for attribute in ("function_tools", "output_tools", "native_tools"):
            requested = getattr(model_request_parameters, attribute, None) or []
            if requested:
                raise GatewayCapabilityError(
                    "the governed gateway cannot execute %s; %d requested. "
                    "Silently dropping them would make the model appear to have "
                    "tools it never had." % (attribute, len(requested)))

    def _response(self, text, outcome):
        from pydantic_ai.messages import ModelResponse, TextPart
        return ModelResponse(
            parts=[TextPart(content=text)],
            model_name=outcome.model or self._model_name,
            provider_name=outcome.provider or self._gateway_provider,
            # Operational metadata only. No hidden reasoning is requested of the
            # provider and none is carried here.
            provider_details={"via": "services/llm_gateway.py",
                              "adapter": ADAPTER_VERSION,
                              "stop_reason": outcome.stop_reason},
        )


class GatewayModel(_GatewayModelBase, _PydanticAIModel):
    """A PydanticAI `Model` whose every request goes through `llm_gateway`.

    A real `pydantic_ai.models.Model` subclass when the framework is installed,
    and a plain object otherwise, so this module imports and its helpers stay
    testable in an environment with no framework at all - the same
    graceful-absence property the gateway guarantees for `google-genai`.
    """

    def __init__(self, *args, **kwargs):
        _GatewayModelBase.__init__(self, *args, **kwargs)
        if PYDANTIC_AI_AVAILABLE:
            try:
                _PydanticAIModel.__init__(self)
            except Exception:  # noqa: BLE001 - a base with no initialiser is fine
                pass
