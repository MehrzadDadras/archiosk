"""CLAUDE-FEASIBILITY-COMPILER-01 - bounded evidence in, typed GO-PDZ out.

    ADDRESS -> deterministic acquisition + GIS seams   (already built, unchanged)
            -> BOUNDED EVIDENCE PACKAGE                (hashed before the call)
            -> feasibility compiler                    (this module)
            -> typed GO-PDZ-1.0-ONEPAGE payload
            -> VR-01..VR-20                            (unchanged, unteachable)
            -> governed Gate-01 output

WHAT THIS IS. A single bounded model call that turns evidence ARCHIOSK already
acquired into a contract-shaped document. It is an orchestration layer and
nothing else.

WHAT THIS IS NOT, stated because each one is a real temptation: a general agent,
a second authority store, a research subsystem, a web agent, a replacement for
`planning_authority`, `deterministic_spatial`, or VR-01..VR-20. Remove this
module and ARCHIOSK's evidence and governance semantics are exactly as they were.

THE MODEL CANNOT ACQUIRE AUTHORITY. There are ZERO tools. The evidence package is
built by deterministic code, canonicalised, hashed, and passed as typed
dependencies; `input_evidence_sha256` is what proves afterwards which evidence
the model actually saw. A model that cannot fetch cannot cite something nobody
retrieved, which is a structural guarantee rather than an instruction it might
ignore.

RETRY IS STRUCTURAL, NEVER SEMANTIC - THE MOST IMPORTANT RULE HERE. Malformed
JSON, a missing typed field or a bad enum may be retried a small, explicit number
of times, because those are transport failures. A VR-01..VR-20 semantic failure
is NEVER sent back to the model. Feeding validator errors to a model until it
passes does not produce a compliant result; it produces a model that has learned
to satisfy the validator, and it destroys the one property that makes the
validator worth having. A semantic failure is EVIDENCE: the original payload is
preserved, the diagnostics are preserved, the result is NOT_PROMOTABLE, and the
failure is returned to the application rather than iterated away.

MODEL OUTPUT IS NOT AUTHORITY. The envelope records provider, exact model id,
evidence hash, payload hash, attempt count and validator verdict so that a reader
can tell what was reasoned from what was retrieved. Nothing here writes to a
canonical record; promotion stays a separate governed operation.

NO HIDDEN REASONING IS REQUESTED OR STORED. Section 11.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from services import go_pdz_contract as contract
from services import go_pdz_validator as validator

logger = logging.getLogger(__name__)

COMPILER_VERSION = "feasibility-compiler@5"

#: Configuration-driven, never hard-coded at the call site. Read from
#: `FEASIBILITY_MODEL_PROVIDER` / `FEASIBILITY_MODEL` when set.
#:
#: THE PROVIDER NAME IS THE GATEWAY'S, NOT THE SDK'S. Version 1 defaulted to
#: "google", which is what PydanticAI and the Google SDK call it and is NOT in
#: `llm_gateway.KNOWN_PROVIDERS` - so the first governed call would have raised
#: `ValueError: 'google' is not a known provider`. `gateway_model` still accepts
#: the alias, but the declared default is now the vocabulary of the boundary that
#: actually performs the egress.
#: The declared fallbacks, used only when `config` cannot be imported at all
#: (a bare script outside the app). NOT read from the environment here - see
#: `resolve_model` for why an import-time getenv is the wrong place.
FALLBACK_PROVIDER = "gemini"
FALLBACK_MODEL = "gemini-3.8-flash"

#: Failure reason used when no authorized credential exists for the configured
#: provider. A named STOP, never a bypass and never a fabricated answer.
PROVIDER_CREDENTIAL_REQUIRED = "PROVIDER_CREDENTIAL_REQUIRED"

#: The configured current model could not be resolved by the provider. A named
#: STOP, distinct from a missing credential, because "we have no key" and "the
#: key works and that model does not exist" call for different actions.
CURRENT_MODEL_UNAVAILABLE = "CURRENT_MODEL_UNAVAILABLE"


def _config():
    """`config.BaseConfig`, or None outside the application.

    Imported lazily and defensively: this module must stay usable from a bare
    script, and must not make `config` a hard import-time dependency of the
    compile path.
    """
    try:
        import config as _module
        return _module.BaseConfig
    except Exception:  # noqa: BLE001 - absence is a supported state
        return None


def resolve_model() -> str:
    """The configured feasibility model, resolved AT CALL TIME.

    NOT a module-level `os.getenv`. `config.py` calls `load_dotenv()` at its own
    import, and this module does not import `config`, so a getenv evaluated here
    at import time can run BEFORE `.env` has been read - returning the literal
    below while an operator's configured value sits unread. The two strings are
    identical today, which is exactly what would have kept that invisible until
    someone changed `.env` and it silently did not take effect.

    A SILENT MODEL DOWNGRADE IS THE FAILURE THIS GUARDS. Section 1 forbids
    falling back to an older Gemini quietly; a stale import-time default is
    precisely how that would have happened, with nothing in the output to show it.
    """
    configured = getattr(_config(), "FEASIBILITY_MODEL", None)
    return (configured or os.getenv("FEASIBILITY_MODEL") or FALLBACK_MODEL)


def resolve_provider_name() -> str:
    """The configured feasibility provider, resolved at call time."""
    configured = getattr(_config(), "FEASIBILITY_MODEL_PROVIDER", None)
    return (configured or os.getenv("FEASIBILITY_MODEL_PROVIDER")
            or FALLBACK_PROVIDER)


def model_configuration() -> dict:
    """What will actually be requested, and where each value came from.

    Reported rather than assumed: section 5 requires the exact model, and
    "what the constant says" is not the same claim as "what the gateway was
    asked for".
    """
    resolved_model, resolved_provider = resolve_model(), resolve_provider_name()
    configuration = _config()
    return {
        "provider": resolved_provider,
        "model": resolved_model,
        "provider_source": ("config.FEASIBILITY_MODEL_PROVIDER" if getattr(
            configuration, "FEASIBILITY_MODEL_PROVIDER", None)
            else ("environment" if os.getenv("FEASIBILITY_MODEL_PROVIDER")
                  else "module fallback")),
        "model_source": ("config.FEASIBILITY_MODEL" if getattr(
            configuration, "FEASIBILITY_MODEL", None)
            else ("environment" if os.getenv("FEASIBILITY_MODEL")
                  else "module fallback")),
        # The gateway's own default, shown so a reader can see that feasibility
        # is NOT sharing it - and that no silent downgrade to it is possible.
        "gateway_default_model_not_used": getattr(
            _config(), "GEMINI_MODEL", None),
        "credential_variable": "GEMINI_API_KEY",
    }

#: Section 10. Small and explicit. Structural only.
MAX_STRUCTURAL_ATTEMPTS = 2

#: A FULL GATE-01 ENVELOPE IS A LONG DOCUMENT, AND 4000 WAS NOT ENOUGH.
#: Measured, and measured only because the same probe was run twice: the first
#: live 35 Taber replay fit under 4000 output tokens and reported promotable; the
#: SECOND was truncated mid-statement at the same setting. The gateway refused to
#: parse the partial response - never a partial parse, which is why this surfaced
#: as an honest failure rather than a silently short document - but a cap that
#: passes or fails on luck is not a cap, it is a coin toss. 35 Taber alone carries
#: 15 statements and 7 spatial tokens; a real envelope is simply large.
DEFAULT_MAX_OUTPUT_TOKENS = 16000


def resolve_max_output_tokens() -> int:
    """Output budget, resolved at call time like the model itself."""
    configured = getattr(_config(), "FEASIBILITY_MAX_OUTPUT_TOKENS", None)
    raw = configured or os.getenv("FEASIBILITY_MAX_OUTPUT_TOKENS")
    try:
        value = int(raw) if raw else DEFAULT_MAX_OUTPUT_TOKENS
    except (TypeError, ValueError):
        value = DEFAULT_MAX_OUTPUT_TOKENS
    return max(1000, value)

#: Section 14. Every one of these is a RESULT, never an exception that escapes.
FAILURE_MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
FAILURE_MODEL_TIMEOUT = "MODEL_TIMEOUT"
FAILURE_MODEL_RATE_LIMIT = "MODEL_RATE_LIMIT"
FAILURE_STRUCTURAL = "STRUCTURAL_OUTPUT_FAILURE"
FAILURE_SCHEMA = "GO_PDZ_SCHEMA_FAILURE"
FAILURE_SEMANTIC = "SEMANTIC_VALIDATION_FAILURE"
FAILURE_EVIDENCE = "EVIDENCE_CONTEXT_INVALID"
FAILURE_PROVIDER_CONFIG = "PROVIDER_CONFIGURATION_ERROR"
FAILURE_OUTPUT_TRUNCATED = "OUTPUT_TRUNCATED_AT_MAX_TOKENS"

#: Section 8. Short and bounded. The machine validator is the enforcement layer,
#: so this does not try to restate twenty rules in prose - a long prompt would
#: only create the impression that governance lives in it.
INSTRUCTIONS = """\
You compile already-retrieved planning evidence into a GO-PDZ Gate-01 envelope.

Reason ONLY from the supplied evidence. You have no tools and no way to retrieve
anything; if something is not in the evidence, it is not available.

Classify every statement:
  AUTHORITY_SAYS  - what a cited official authority states. Must cite the
                    authority_id of a supplied admitted authority.
  PROPERTY_FACT   - a fact about the parcel from the supplied record.
  GO_INTERPRETS   - your own planning-level reading. Never phrased as the
                    authority's own words.

Do not invent an authority, a citation, an owner use or program, or a municipal
approval outcome. Do not predict whether an application would be approved. Do not
assert a definite spatial relationship that the supplied deterministic spatial
results do not contain - copy their tokens; never mint one.

Preserve material ambiguity. If the evidence leaves something genuinely
undetermined, say so and leave it unresolved rather than resolving it plausibly.

Stop at the legal envelope. Owner program, statement of requirements, budget,
unit and room counts, massing and option selection belong to a later gate and
must not appear.
"""


def output_contract_prompt() -> str:
    """The required output shape, taken FROM THE CANONICAL CONTRACT ITSELF.

    The first live probe failed here and the failure was the harness's, not the
    model's. gemini-3.8-flash produced a careful document - correct statement
    kinds, the supplied authority_id cited, the deterministic spatial token
    respected, nothing invented - using field names it had to guess
    (`parcel_identity`, `statement_type`, `unresolved_ambiguities`) because the
    instructions named NONE of the contract's own keys, and `output_type=str`
    meant the framework enforced nothing either. It was asked to hit a target it
    was never shown.

    `go_pdz_contract.SCHEMA` is serialised here rather than restated, so there is
    exactly ONE definition of the contract (section 7: do not create a competing
    duplicate schema). If the contract changes, this prompt changes with it and
    cannot drift out of step.
    """
    return (
        "Return ONE JSON object and nothing else - no prose, no code fence.\n"
        "It must validate against this JSON Schema exactly, including every\n"
        "`required` key, every `const` value and every `enum` value. Keys not in\n"
        "the schema are rejected (`additionalProperties: false`).\n\n"
        + json.dumps(contract.SCHEMA, indent=1, sort_keys=True)
        + "\n\nNotes that the schema states but which are easy to miss:\n"
          "  - `contract` must be exactly %r and `schema_version` exactly %r.\n"
          "  - `gate` must be exactly %r; `next_authorized_gate` exactly %r.\n"
          "  - every statement needs `statement_id`, `kind`, `topic`, `text`,\n"
          "    `statement_status` and `confidence`.\n"
          "  - `result_status` is %s: use UNRESOLVED when any supplied unresolved\n"
          "    issue is MATERIAL, or any site-specific exception was not retrieved.\n"
          "  - copy `spatial_relation` and `spatial_basis` from the supplied\n"
          "    deterministic spatial results. Do not mint a spatial predicate.\n"
        % (contract.CONTRACT_ID, contract.SCHEMA_VERSION, contract.GATE_01,
           contract.GATE_02, " or ".join(contract.RESULT_STATUSES)))


def canonical_evidence(evidence) -> str:
    """Section 12. One canonical form, so the hash means something."""
    return json.dumps(evidence, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)


def evidence_hash(evidence) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_evidence(evidence).encode("utf-8")).hexdigest()


def payload_hash(payload) -> Optional[str]:
    if payload is None:
        return None
    return "sha256:" + hashlib.sha256(
        canonical_evidence(payload).encode("utf-8")).hexdigest()


@dataclass
class FeasibilityEvidence:
    """Section 6. The ONLY thing the model sees.

    What is deliberately absent is as much the design as what is present: no
    repository handle, no store path, no owner program, no statement of
    requirements, no budget, and no design options from historical projects.
    `for_model()` is the single serialisation point, so nothing can reach the
    model that did not pass through it.
    """

    investigation_id: str
    input_address: str
    schema_version: str = contract.SCHEMA_VERSION
    normalized_address: Optional[str] = None
    parcel_identifier: Optional[str] = None
    municipality: Optional[str] = None
    jurisdiction: Optional[str] = None
    identity_confidence: Optional[str] = None
    parcel_geometry_metadata: dict = field(default_factory=dict)
    spatial_results: dict = field(default_factory=dict)
    admitted_authorities: list = field(default_factory=list)
    zoning: dict = field(default_factory=dict)
    site_specific_exceptions: list = field(default_factory=list)
    official_plan: dict = field(default_factory=dict)
    overlays: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    #: Fields a caller might reasonably think belong here and must not. Asserted
    #: rather than merely documented - see `validate_evidence`.
    FORBIDDEN_KEYS = ("owner_program", "statement_of_requirements", "budget",
                      "unit_count", "room_count", "massing", "options",
                      "design_options", "store", "session", "db", "registry")

    def for_model(self) -> dict:
        return {
            "investigation_id": self.investigation_id,
            "input_address": self.input_address,
            "schema_version": self.schema_version,
            "normalized_address": self.normalized_address,
            "parcel_identifier": self.parcel_identifier,
            "municipality": self.municipality,
            "jurisdiction": self.jurisdiction,
            "identity_confidence": self.identity_confidence,
            "parcel_geometry_metadata": self.parcel_geometry_metadata,
            "spatial_results": self.spatial_results,
            "admitted_authorities": self.admitted_authorities,
            "zoning": self.zoning,
            "site_specific_exceptions": self.site_specific_exceptions,
            "official_plan": self.official_plan,
            "overlays": self.overlays,
            "unresolved": self.unresolved,
            "provenance": self.provenance,
        }


def evidence_from_gate01(outcome, *, investigation_id) -> FeasibilityEvidence:
    """Build the bounded package from a deterministic Gate-01 result.

    This is the seam that keeps the compiler downstream of everything governed.
    It reads an already-produced `toronto_gate01` / `mississauga_gate01` outcome -
    authorities already classified and admitted, spatial tokens already computed
    by `deterministic_spatial`, unresolved issues already raised - and carries
    ONLY those forward. The compiler therefore cannot widen the evidence, only
    reason over it.

    Note what is dropped: geometry coordinates. The model needs to know a token
    said INSIDE and what produced it, never the ring it was computed from -
    passing thousands of vertices would cost tokens, invite the model to
    recompute geometry it must not recompute, and prove nothing.
    """
    document = (outcome or {}).get("document") or {}
    subject = document.get("subject") or {}
    retrieval = (outcome or {}).get("retrieval") or {}
    tokens = {}
    for name, token in ((outcome or {}).get("spatial_tokens") or {}).items():
        provenance = (token or {}).get("provenance") or {}
        tokens[name] = {
            "spatial_relation": token.get("spatial_relation"),
            "spatial_basis": token.get("spatial_basis"),
            "engine": token.get("engine"),
            "reason": token.get("reason"),
            "layer_source": provenance.get("layer_geometry_source"),
            "subject_crs": provenance.get("subject_crs"),
            "layer_crs": provenance.get("layer_crs"),
            "transformation": provenance.get("transformation"),
        }
    return FeasibilityEvidence(
        investigation_id=investigation_id,
        input_address=subject.get("address_as_given") or "",
        normalized_address=subject.get("normalized_address"),
        parcel_identifier=subject.get("parcel_identifier"),
        municipality=subject.get("municipality"),
        jurisdiction=subject.get("municipality"),
        identity_confidence=subject.get("identity_confidence"),
        parcel_geometry_metadata={
            "crs": (outcome or {}).get("identity", {}).get("_crs"),
            "geometry_source": (outcome or {}).get("identity", {}).get(
                "_geometry_source"),
        },
        spatial_results=tokens,
        admitted_authorities=document.get("authorities") or [],
        zoning={"statements": [s for s in document.get("statements") or []
                               if s.get("topic") == "ZONING_DESIGNATION"]},
        site_specific_exceptions=document.get("site_specific_exceptions") or [],
        official_plan={"statements": [
            s for s in document.get("statements") or []
            if s.get("topic") == "OFFICIAL_PLAN_DESIGNATION"]},
        overlays=[s for s in document.get("statements") or []
                  if s.get("topic") not in (None, "ZONING_DESIGNATION",
                                            "OFFICIAL_PLAN_DESIGNATION")],
        unresolved=document.get("unresolved") or [],
        provenance={
            "retrieved_at": retrieval.get("retrieved_at"),
            "runner_version": retrieval.get("runner_version"),
            "source_version": retrieval.get("source_version"),
            "gate": document.get("gate"),
        },
    )


def validate_evidence(evidence: FeasibilityEvidence) -> list:
    """Refuse a context that carries what Gate 01 must never see."""
    problems = []
    if not isinstance(evidence, FeasibilityEvidence):
        return ["evidence is not a FeasibilityEvidence"]
    if not evidence.investigation_id:
        problems.append("investigation_id is required")
    if not evidence.input_address:
        problems.append("input_address is required")

    serialised = evidence.for_model()
    blob = canonical_evidence(serialised).lower()
    for forbidden in FeasibilityEvidence.FORBIDDEN_KEYS:
        if ('"%s"' % forbidden) in blob:
            problems.append("evidence carries a forbidden key: %s" % forbidden)
    for record in evidence.admitted_authorities or []:
        if not isinstance(record, dict) or not record.get("authority_id"):
            problems.append("an admitted authority carries no authority_id")
            break
    return problems


@dataclass
class CompilerOutcome:
    """Section 11. Deterministic application envelope, separate from the payload."""

    compiler_version: str = COMPILER_VERSION
    provider: Optional[str] = None
    model: Optional[str] = None
    model_version: Optional[str] = None
    investigation_id: Optional[str] = None
    input_evidence_sha256: Optional[str] = None
    output_payload_sha256: Optional[str] = None
    schema_version: str = contract.SCHEMA_VERSION
    validator_version: Optional[str] = None
    attempt_count: int = 0
    typed_output_valid: bool = False
    semantic_validation_valid: bool = False
    semantic_error_count: int = 0
    semantic_warning_count: int = 0
    promotable: bool = False
    go_pdz_payload: Optional[dict] = None
    validation_result: Optional[dict] = None
    timing_seconds: Optional[float] = None
    usage_metadata: Optional[dict] = None
    failure_reason: Optional[str] = None
    executed_at: Optional[str] = None
    structural_errors: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _classify_exception(exc) -> str:
    """Map a provider failure onto section 14's vocabulary. Never re-raises.

    A `GatewayUnavailable` carries the gateway's own `skipped_reason`, so a
    missing credential, the `AI_CALLS_DISABLED` kill switch, an absent SDK and a
    timeout stay distinguishable here instead of collapsing into one opaque
    "unavailable" - which is the whole reason the gateway sets that field.
    """
    name = type(exc).__name__.lower()
    text = (getattr(exc, "skipped_reason", None) or str(exc)).lower()
    if "gatewaycapability" in name:
        return FAILURE_PROVIDER_CONFIG
    if ("api key" in text or "apikey" in text or "gemini_api_key" in text
            or "anthropic_api_key" in text or "no key" in text
            or "credential" in text):
        return PROVIDER_CREDENTIAL_REQUIRED
    if "disabled" in text:
        return FAILURE_PROVIDER_CONFIG
    # THE CONFIGURED MODEL DOES NOT EXIST is its own answer, distinct from both a
    # missing credential and a dead provider: it means the key worked, the
    # service answered, and the model we are required to use was rejected. The
    # correct response is to STOP and report, never to fall back to an older
    # Gemini - so it must not be collapsed into the generic unavailable case.
    if (("not found" in text or "does not exist" in text
         or "unsupported model" in text or "invalid model" in text)
            and ("model" in text or "gemini" in text)):
        return CURRENT_MODEL_UNAVAILABLE
    if "max_tokens" in text or "cut off" in text or "truncat" in text:
        # Its own reason: the model and credential are fine and the document was
        # simply longer than the budget. Retrying without raising the budget
        # would just burn another call on the same wall.
        return FAILURE_OUTPUT_TRUNCATED
    if "not installed" in text or "unavailable" in text:
        return FAILURE_MODEL_UNAVAILABLE
    if "timeout" in name or "timeout" in text or "deadline" in text:
        return FAILURE_MODEL_TIMEOUT
    if "ratelimit" in name or "rate limit" in text or "429" in text:
        return FAILURE_MODEL_RATE_LIMIT
    if ("unauthenticated" in text or "401" in text or "403" in text):
        return PROVIDER_CREDENTIAL_REQUIRED
    if "validation" in name or "schema" in text:
        return FAILURE_STRUCTURAL
    return FAILURE_MODEL_UNAVAILABLE


ALLOWING_DECISIONS = ("allow", "allow_approved_route", "allow_with_redaction")


def compile_feasibility(evidence: FeasibilityEvidence, *, runner,
                        provider=None, model=None,
                        max_attempts=MAX_STRUCTURAL_ATTEMPTS,
                        authorization=None) -> CompilerOutcome:
    """One bounded compile. NEVER RAISES, and never mutates anything.

    `runner` is injected with no default, exactly as every other external seam in
    this programme: a test that forgets to supply one raises TypeError instead of
    reaching a provider. It is called as `runner(instructions, evidence_dict,
    attempt)` and must return a dict payload or raise.

    THE RETRY LOOP IS STRUCTURAL ONLY. It ends the moment a payload parses and
    satisfies the canonical contract shape. Semantic validation then runs ONCE,
    outside the loop, and its verdict is recorded rather than acted upon.
    """
    started = time.time()
    provider = provider or resolve_provider_name()
    model = model or resolve_model()
    outcome = CompilerOutcome(
        provider=provider, model=model,
        investigation_id=getattr(evidence, "investigation_id", None),
        validator_version=validator.VALIDATOR_VERSION,
        executed_at=_now())

    # GOVERNANCE STAYS OUTSIDE THE FRAMEWORK (section 3). `llm_gateway`'s own
    # docstring is explicit that it has no opinion about governance, and the
    # established pattern in this repository - services/sheet_vision.py - is that
    # a generation module receives an ALREADY-RESOLVED SecurityDecision rather
    # than reaching into a store itself. So the gate lives here, in the caller,
    # and a supplied decision that does not permit egress stops the compile
    # before any prompt is built.
    if authorization is not None:
        decision = getattr(authorization, "decision", None) or (
            authorization.get("decision") if isinstance(authorization, dict) else None)
        if decision not in ALLOWING_DECISIONS:
            outcome.failure_reason = FAILURE_PROVIDER_CONFIG
            outcome.structural_errors = [
                "external AI request not authorized: decision=%r" % decision]
            outcome.timing_seconds = round(time.time() - started, 3)
            return outcome

    problems = validate_evidence(evidence)
    if problems:
        outcome.failure_reason = FAILURE_EVIDENCE
        outcome.structural_errors = problems
        outcome.timing_seconds = round(time.time() - started, 3)
        return outcome

    serialised = evidence.for_model()
    outcome.input_evidence_sha256 = evidence_hash(serialised)

    payload = None
    for attempt in range(1, max(1, int(max_attempts)) + 1):
        outcome.attempt_count = attempt
        try:
            candidate = runner(INSTRUCTIONS, serialised, attempt)
        except Exception as exc:  # noqa: BLE001 - a provider failure is a result
            logger.warning("feasibility compile failed on attempt %d (%s: %s)",
                           attempt, type(exc).__name__, exc)
            outcome.failure_reason = _classify_exception(exc)
            outcome.structural_errors.append(
                "%s: %s" % (type(exc).__name__, str(exc)[:300]))
            if outcome.failure_reason in (FAILURE_PROVIDER_CONFIG,
                                          FAILURE_OUTPUT_TRUNCATED,
                                          PROVIDER_CREDENTIAL_REQUIRED,
                                          FAILURE_MODEL_UNAVAILABLE,
                                          FAILURE_MODEL_RATE_LIMIT,
                                          FAILURE_MODEL_TIMEOUT):
                # Not a structural problem, so retrying cannot fix it.
                break
            continue

        if hasattr(candidate, "model_dump"):
            candidate = candidate.model_dump(mode="json")
        if not isinstance(candidate, dict):
            outcome.structural_errors.append(
                "attempt %d returned %s, not a document"
                % (attempt, type(candidate).__name__))
            outcome.failure_reason = FAILURE_STRUCTURAL
            continue

        # `validate_structure` returns a LIST of (path, problem) pairs and is
        # empty when the shape is right - it does not return a verdict object.
        problems_found = contract.validate_structure(candidate)
        if not problems_found:
            payload = candidate
            outcome.typed_output_valid = True
            outcome.failure_reason = None
            break
        outcome.structural_errors.append(
            "attempt %d: %s" % (attempt, json.dumps(
                [list(p) for p in problems_found[:6]], default=str)[:400]))
        outcome.failure_reason = FAILURE_SCHEMA

    outcome.timing_seconds = round(time.time() - started, 3)
    if payload is None:
        return outcome

    outcome.go_pdz_payload = payload
    outcome.output_payload_sha256 = payload_hash(payload)
    # Section 5: the model that ACTUALLY answered, as the provider reported it -
    # not the configured string restated back as if it were confirmation.
    outcome.model_version = getattr(runner, "last_resolved_model", None)
    outcome.usage_metadata = getattr(runner, "last_usage", None)

    # SEMANTIC VALIDATION RUNS ONCE, AND ITS RESULT IS EVIDENCE. There is no path
    # from here back into the loop above - that absence is the whole point of
    # section 10, and it is asserted by the tests rather than left to discipline.
    verdict = validator.validate(payload)
    outcome.validation_result = verdict
    outcome.semantic_validation_valid = bool(verdict.get("valid"))
    outcome.semantic_error_count = int(verdict.get("error_count") or 0)
    outcome.semantic_warning_count = int(verdict.get("warning_count") or 0)
    outcome.promotable = bool(verdict.get("promotable"))
    if not outcome.promotable:
        outcome.failure_reason = FAILURE_SEMANTIC
    return outcome


def gateway_runner(*, model_name=None, provider=None, api_key=None,
                   timeout=None, max_tokens=None, output_model=None,
                   agent=None, caller=None, instructions=INSTRUCTIONS):
    """PydanticAI orchestration over the ONE governed egress boundary.

    THIS REPLACES A BYPASS. Version 1 built `GoogleModel(provider=GoogleProvider(
    api_key=...))` and talked to Google directly - a second production egress
    path around `services/llm_gateway.py`, its `AI_CALLS_DISABLED` kill switch,
    its timeout policy and its honest-degrade contract. The model handed to the
    `Agent` is now a `gateway_model.GatewayModel`, so every request PydanticAI
    makes leaves through the gateway and nowhere else.

    WHAT PYDANTICAI STILL DOES, and it is worth being precise because the value
    is real: typed output handling, dependency injection, and bounded structural
    retry. What it no longer does is decide where bytes go.

    `tools=()` per section 9 and `retries=0` because THIS module owns the retry
    ceiling - and now the adapter refuses tool calls outright, so zero tools is
    enforced at the boundary rather than merely configured at the Agent.
    """
    from services import gateway_model as gateway

    model_name = model_name or resolve_model()
    provider = provider or resolve_provider_name()
    max_tokens = max_tokens or resolve_max_output_tokens()
    if not model_name:
        # NEVER hand the gateway None: its Gemini path would then
        # resolve `os.getenv('GEMINI_MODEL', DEFAULT_GEMINI_MODEL)`
        # and quietly run on gemini-2.5-flash. An explicit model is
        # what makes 'no silent fallback' true rather than intended.
        raise RuntimeError('no feasibility model is configured')

    if agent is None:
        if not gateway.PYDANTIC_AI_AVAILABLE:
            raise RuntimeError("pydantic-ai is not installed")
        from pydantic_ai import Agent
        built = gateway.GatewayModel(
            model_name, provider=provider, api_key=api_key, timeout=timeout,
            max_tokens=max_tokens, caller=caller)
        agent = Agent(
            built,
            output_type=output_model or str,
            instructions=instructions,
            deps_type=dict,
            tools=(),          # section 9 - ZERO tools
            retries=0,         # section 10 - this module owns the ceiling
        )

    def run(_instructions, evidence_dict, attempt):
        prompt = ("Compile this evidence package into a GO-PDZ Gate-01 envelope.\n"
                  "\n%s\n\nEVIDENCE PACKAGE:\n%s"
                  % (output_contract_prompt(),
                     canonical_evidence(evidence_dict)))
        if attempt > 1:
            # A STRUCTURAL retry only. It says the shape was wrong; it never
            # carries a VR finding, because semantic validation happens after
            # this runner has returned and is never fed back (section 6).
            prompt += ("\n\nThe previous response did not match the schema. "
                       "Return only a JSON object conforming to it exactly.")
        result = agent.run_sync(prompt, deps=evidence_dict)
        run.last_usage = _usage_of(result)
        # The provider's OWN report, surfaced from the adapter rather than
        # inferred from the configured string. `resolved_model` is what actually
        # answered; `model` in the envelope stays what was asked for.
        details = getattr(getattr(result, "response", None), "provider_details",
                          None) or {}
        run.last_resolved_model = details.get("resolved_model")
        if details.get("usage"):
            run.last_usage = dict(run.last_usage or {}, **details["usage"])
        output = getattr(result, "output", result)
        if hasattr(output, "model_dump"):
            return output.model_dump(mode="json")
        if isinstance(output, str):
            # The gateway returns JSON; PydanticAI hands it back as text when
            # `output_type` is str. Parsing here rather than declaring a second
            # Pydantic schema keeps `go_pdz_contract` the single contract.
            return json.loads(output)
        return output

    run.last_usage = None
    run.last_resolved_model = None
    run.agent = agent
    return run


def resolve_credential(provider=None):
    """The configured credential for a provider, or None. NEVER a literal.

    Reads only what the application already governs. Section 5: a missing
    credential is reported as `PROVIDER_CREDENTIAL_REQUIRED`, never worked around,
    and this function does not prompt, generate, or default one.
    """
    provider = (provider or resolve_provider_name()).strip().lower()
    variable = ("GEMINI_API_KEY" if provider in ("gemini", "google", "google-genai")
                else "ANTHROPIC_API_KEY")
    return os.getenv(variable) or None


def credential_status(provider=None) -> dict:
    """Whether a live probe can run at all, without revealing anything."""
    provider = provider or resolve_provider_name()
    key = resolve_credential(provider)
    status = dict(model_configuration())
    status.update({"provider": provider,
                   "credential_present": bool(key),
                   "status": "READY" if key else PROVIDER_CREDENTIAL_REQUIRED,
                   "credential_location": (
                       ".env at the repository root, or the deploying host's "
                       "environment: GEMINI_API_KEY")})
    return status


def _usage_of(result) -> Optional[dict]:
    """Safe operational metadata only. Never hidden reasoning."""
    usage = getattr(result, "usage", None)
    if usage is None:
        return None
    try:
        usage = usage() if callable(usage) else usage
        return {k: v for k, v in vars(usage).items()
                if isinstance(v, (int, float, str)) and not k.startswith("_")}
    except Exception:  # noqa: BLE001
        return None
