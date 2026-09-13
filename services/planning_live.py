"""CLAUDE-PLANNING-LIVE-01 - one bounded live Toronto planning request.

    SIGNED-IN ADDRESS -> TORONTO GATE-01 -> RESULT VIEW -> RENDERED RESULT

ONE municipality, ONE property, ONE synchronous request. No batch, no queue, no
background job, no cache, and nothing written anywhere.

WHY THIS IS A SEPARATE MODULE AND NOT A BRANCH IN THE ROUTE

The route's job is authorization, form handling and rendering. This module's job
is the only thing in the application that may reach a municipal source on a
signed-in person's behalf - so it is one file, with one entry point, that a
reader can audit end to end. A flag-gated branch buried in a view function would
have put that boundary somewhere nobody looks.

NOTHING IS PERSISTED. Product Owner decision, section 1-A: result lifecycle,
supersession, retention and ownership are not governed yet, so a result lives for
exactly as long as the response that carries it. This module holds no store
handle, writes no file and creates no record - asserted by test rather than
promised here.

FAILURE IS LOCAL AND VISIBLE, NEVER SUBSTITUTED. Section 1-B: a municipal source
that times out produces a NAMED failure attached to the thing it failed to
establish. It does not produce a different authority's answer, a retry storm, or
a generic "something went wrong" that discards the evidence already gathered. If
zoning is established and one overlay times out, the zoning stays.

UNRESOLVED IS A RESULT. Section 1-C. On real Toronto evidence it is the common
one: the Official Plan designation is a map schedule, not a machine-readable
layer, so a governed result usually carries at least one material unresolved
item. A surface that refused to render until everything was established would
refuse to render almost always, which is not caution - it is uselessness.

TIMING IS MEASURED, NOT OPTIMISED. Section 10 asks what the wait actually is
before anyone tries to shorten it.
"""
from __future__ import annotations

import logging
import re
import time

from services import planning_result_view

logger = logging.getLogger(__name__)

LIVE_VERSION = "planning-live@1"

#: Section 4. This tranche is Toronto and nothing else, so an address elsewhere
#: is refused BY NAME rather than quietly routed through Toronto's readers, which
#: would resolve nothing and report it as an unresolvable address.
SUPPORTED_MUNICIPALITY = "City of Toronto"

#: Section 8's vocabulary. Each names WHAT failed, so a reader is told which
#: source could not be established rather than that "an error occurred".
OUTCOME_OK = "OK"
OUTCOME_DISABLED = "LIVE_DISABLED"
OUTCOME_UNSUPPORTED_MUNICIPALITY = "UNSUPPORTED_MUNICIPALITY"
OUTCOME_ADDRESS_UNRESOLVED = "ADDRESS_UNRESOLVED"
OUTCOME_SOURCE_TIMEOUT = "SOURCE_TIMEOUT"
OUTCOME_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
OUTCOME_SOURCE_RESPONSE_INVALID = "SOURCE_RESPONSE_INVALID"
OUTCOME_AUTHORITY_UNRESOLVED = "AUTHORITY_UNRESOLVED"

#: Municipalities this tranche knows it does NOT serve. Checked before any
#: network call: refusing in 2 ms beats refusing in 20 seconds, and naming the
#: municipality is more use to a person than "no property found".
_OTHER_MUNICIPALITIES = (
    "mississauga", "brampton", "vaughan", "markham", "richmond hill",
    "oakville", "burlington", "hamilton", "pickering", "ajax", "whitby",
    "oshawa", "milton", "newmarket", "aurora", "caledon", "halton hills",
    "king city", "georgina", "uxbridge", "scugog", "brock", "clarington",
    "ottawa", "london", "windsor", "kitchener", "waterloo", "guelph",
    "barrie", "kingston", "sudbury", "thunder bay", "montreal", "vancouver",
    "calgary", "edmonton", "winnipeg", "halifax",
)

#: Toronto's own former municipalities and common local names. Present because a
#: Toronto address very often does NOT contain the word "Toronto": "Etobicoke",
#: "North York" and "Scarborough" are all City of Toronto, and refusing them
#: would refuse a large part of the city.
_TORONTO_NAMES = (
    "toronto", "etobicoke", "north york", "scarborough", "york", "east york",
)


#: Section 10's phases. Bucketed by the URL each read actually goes to, because
#: `toronto_gate01.run` is one call and a single "gate01_ms" number cannot tell a
#: slow address lookup from a slow overlay sweep - which is the distinction that
#: decides what would be worth optimising later.
PHASE_ADDRESS = "address_resolution_ms"
PHASE_ZONING = "zoning_gis_ms"
PHASE_OVERLAYS = "overlay_gis_ms"
PHASE_AUTHORITY = "authority_retrieval_ms"
PHASE_OTHER = "other_source_ms"


def _phase_for(url) -> str:
    """Which measured phase one municipal read belongs to."""
    lowered = (url or "").lower()
    if "cot_geospatial27" in lowered:
        # Address Point and Property Boundary both live here: resolving WHICH
        # property the words name, before any planning question is asked.
        return PHASE_ADDRESS
    if "cot_geospatial11" in lowered:
        # Layer 3 is the zone itself; everything else on this service is an
        # overlay or the heritage register.
        return PHASE_ZONING if "/3/query" in lowered else PHASE_OVERLAYS
    if lowered.endswith((".pdf", ".htm", ".html")) or "law0569" in lowered:
        return PHASE_AUTHORITY
    return PHASE_OTHER


def timing_reader(inner):
    """Wrap a reader so every municipal read is attributed to a phase.

    Instrumentation only: the same bytes come back, the same exceptions
    propagate, and the reader has no idea it is being timed. Returns
    `(read, phases, calls)`.
    """
    import collections

    phases = collections.defaultdict(float)
    calls = collections.Counter()

    def read(url):
        phase = _phase_for(url)
        started = time.perf_counter()
        try:
            return inner(url)
        finally:
            phases[phase] += (time.perf_counter() - started) * 1000.0
            calls[phase] += 1

    return read, phases, calls


def _timer():
    started = time.perf_counter()
    return lambda: round((time.perf_counter() - started) * 1000.0, 1)


def municipality_check(address) -> dict:
    """Is this an address this tranche may serve? Text only, before any call.

    Deliberately conservative in BOTH directions: an address naming another
    municipality is refused, an address naming a Toronto name is accepted, and
    anything else is ACCEPTED and left for the municipal reader to resolve or
    not. Guessing harder than this would reject real Toronto addresses that
    simply omit the city, which is most of how people type them.
    """
    lowered = " %s " % (address or "").lower()
    for name in _OTHER_MUNICIPALITIES:
        if re.search(r"[\s,]%s[\s,]" % re.escape(name), lowered):
            return {"supported": False, "municipality": name.title(),
                    "outcome": OUTCOME_UNSUPPORTED_MUNICIPALITY}
    return {"supported": True, "municipality": None, "outcome": OUTCOME_OK}


def classify_failure(exc) -> str:
    """Map one exception onto section 8's vocabulary. Never re-raises.

    TYPE FIRST, TEXT SECOND. A JSON decode failure is a `ValueError` subclass
    whose message reads "Expecting value: line 1 ..." - no substring of which
    says "json" or "invalid" - so a text-only matcher filed a malformed
    municipal response as an unreachable source. Those are different facts, and
    a reader acting on them would do different things about them.
    """
    import json as _json
    import socket

    if isinstance(exc, _json.JSONDecodeError):
        return OUTCOME_SOURCE_RESPONSE_INVALID
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return OUTCOME_SOURCE_TIMEOUT
    if isinstance(exc, (ConnectionError, OSError)):
        return OUTCOME_SOURCE_UNAVAILABLE

    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "expecting value" in text or "decode" in text:
        return OUTCOME_SOURCE_RESPONSE_INVALID
    if "timeout" in name or "timed out" in text or "timeout" in text:
        return OUTCOME_SOURCE_TIMEOUT
    if "json" in name or "decode" in name or "invalid" in text \
            or "unexpected" in text:
        return OUTCOME_SOURCE_RESPONSE_INVALID
    if "url" in name or "http" in name or "connection" in name \
            or "unreachable" in text or "refused" in text:
        return OUTCOME_SOURCE_UNAVAILABLE
    return OUTCOME_SOURCE_UNAVAILABLE


def _failure_result(outcome, *, message, address, timings, municipality=None):
    """A named failure, carrying whatever timing was already measured.

    NO DOCUMENT AND NO FABRICATION. `document` is absent rather than an empty
    shell, so a caller cannot accidentally render a result-shaped nothing.
    """
    return {
        "outcome": outcome,
        "message": message,
        "address": address,
        "municipality": municipality,
        "timings": timings,
        "live_version": LIVE_VERSION,
        "document": None,
    }


def run_live(address, *, reader=None, gate=None) -> dict:
    """One live Toronto Gate-01 request, instrumented and fail-visible.

    `reader` and `gate` are injected seams with no defaults resolved until they
    are needed, exactly as every other external boundary in this programme: a
    test that forgets to supply one cannot silently reach the City of Toronto.

    Returns an envelope carrying either a governed Gate-01 document with
    `data_class = DATA_CLASS_LIVE`, or a NAMED failure. Never raises.
    """
    timings = {}
    total = _timer()

    check = municipality_check(address)
    timings["municipality_check_ms"] = total()
    if not check["supported"]:
        return _failure_result(
            check["outcome"], address=address, timings=timings,
            municipality=check["municipality"],
            message=("This tranche serves City of Toronto addresses only. That "
                     "address appears to be in %s, and ARCHIOSK will not route "
                     "it through Toronto's records and report the result as if "
                     "it had." % check["municipality"]))

    if gate is None:
        from services import toronto_gate01
        gate = toronto_gate01.run
    if reader is None:
        from services import toronto_planning_source
        reader = toronto_planning_source.live_reader()
    reader, phases, calls = timing_reader(reader)

    # ONE CALL, ONE FAILURE CLASSIFICATION. `toronto_gate01.run` is documented
    # never to raise for a planning reason - an unresolvable address comes back
    # as a document with UNRESOLVED identity - so an exception here is a
    # TRANSPORT problem, which is what gets classified.
    retrieval = _timer()
    try:
        outcome = gate(address, reader=reader)
    except Exception as exc:  # noqa: BLE001 - a source failure is a result
        timings["gate01_ms"] = retrieval()
        for phase, value in phases.items():
            timings[phase] = round(value, 1)
        timings["source_calls"] = dict(calls)
        timings["total_ms"] = total()
        failure = classify_failure(exc)
        logger.warning("live planning request failed (%s): %s: %s",
                       failure, type(exc).__name__, exc)
        return _failure_result(
            failure, address=address, timings=timings,
            municipality=SUPPORTED_MUNICIPALITY,
            message=("A City of Toronto planning source could not be reached, "
                     "so nothing was established. ARCHIOSK will not show you a "
                     "planning result it did not actually produce. (%s)"
                     % failure))
    timings["gate01_ms"] = retrieval()
    # DETERMINISTIC WORK is what is left once the network is subtracted: the
    # spatial engine, the statement building and the lifecycle assembly. Derived
    # rather than separately timed, because timing it directly would mean
    # reaching inside `toronto_gate01.run` and re-implementing what it does.
    for phase, value in phases.items():
        timings[phase] = round(value, 1)
    timings["source_calls"] = dict(calls)
    timings["deterministic_ms"] = round(
        max(0.0, timings["gate01_ms"] - sum(phases.values())), 1)

    document = (outcome or {}).get("document") or {}
    subject = document.get("subject") or {}
    if subject.get("identity_confidence") in (None, "UNRESOLVED") \
            or not subject.get("parcel_identifier"):
        timings["total_ms"] = total()
        return _failure_result(
            OUTCOME_ADDRESS_UNRESOLVED, address=address, timings=timings,
            municipality=SUPPORTED_MUNICIPALITY,
            message=("That address did not resolve to exactly one City of "
                     "Toronto property. Check the street number and name, or "
                     "try the municipal address as the City writes it."))

    # The retrieval envelope already separates its own phases; they are surfaced
    # rather than re-measured, because re-timing them here would mean calling
    # twice.
    retrieval_record = (outcome or {}).get("retrieval") or {}

    assembly = _timer()
    result = {
        # SECTION 5: the data class is set HERE, by the code that actually ran
        # the live path, and nowhere else. It is never inferred from the route,
        # the environment or the flag - only real engine output carries it, and
        # only it removes the preview banner.
        "data_class": planning_result_view.DATA_CLASS_LIVE,
        "document": document,
        "retrieval": retrieval_record,
        # No options are asserted for a live result in this tranche. A/B/C/D are
        # a presentation of postures and nothing produces them yet; rendering
        # invented ones over real evidence would be the exact fabrication this
        # programme refuses.
        "options": [],
        "conclusion": None,
    }
    view = planning_result_view.build_view(result)
    timings["view_build_ms"] = assembly()
    timings["total_ms"] = total()

    return {
        "outcome": OUTCOME_OK,
        "message": None,
        "address": address,
        "municipality": subject.get("municipality") or SUPPORTED_MUNICIPALITY,
        "timings": timings,
        "live_version": LIVE_VERSION,
        "document": document,
        "view": view,
        "source_failures": _source_failures(outcome),
    }


def _source_failures(outcome) -> list:
    """Which individual sources did NOT establish what they were asked for.

    Section 8: partial evidence stays visible. The Gate-01 runner already records
    per-source acquisition on its retrieval envelope and per-overlay undecidedness
    on its findings; this reads those rather than inventing a second failure
    model, so "the heritage layer could not be decided" reaches the page as the
    specific thing it is.
    """
    retrieval = (outcome or {}).get("retrieval") or {}
    failures = []
    if retrieval.get("authority_acquired") is False:
        failures.append({"source": "Zoning by-law document",
                         "outcome": OUTCOME_AUTHORITY_UNRESOLVED,
                         "note": "the by-law document was not retrieved"})
    if retrieval.get("official_plan_acquired") is False:
        failures.append({"source": "Official Plan",
                         "outcome": OUTCOME_AUTHORITY_UNRESOLVED,
                         "note": "the Official Plan document was not retrieved"})
    for finding in retrieval.get("overlays") or []:
        if not isinstance(finding, dict):
            continue
        if finding.get("present") is None:
            failures.append({
                "source": finding.get("layer_name") or "an overlay layer",
                "outcome": OUTCOME_SOURCE_RESPONSE_INVALID,
                "note": finding.get("note")
                or "whether this layer applies could not be determined"})
    return failures
