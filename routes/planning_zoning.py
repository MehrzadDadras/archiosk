"""CLAUDE-PLANNING-ZONING-DOOR-01 - the front door to the planning line.

    ADDRESS -> ZONING / PLANNING CHECK -> DEVELOPMENT ENVELOPE
            -> PLANNING-LEVEL DESIGN OPTIONS

An address is the only thing a person has when they start. Everything the GO-PDZ
programme has built - the live Toronto and Mississauga readers, the deterministic
spatial engine, the Gate-01 envelope, the FSI originator, the governed compiler -
has been reachable from NO ROUTE AT ALL. This is the door, and only the door.

THE BUTTON DOES NOT RUN THE ENGINE, AND THAT IS DELIBERATE

`planning_analysis_state()` reports BACKEND_NOT_ROUTABLE and the submit path says
so in plain words. It would be easy to import `toronto_gate01` here and get a
real answer for a Toronto address - the code works, it is live-proven, and it is
under an explicit standing instruction not to be deployed. A route is a
deployment. So this page validates intake and then stops at an honest boundary.

WHAT IT MUST NEVER DO IS INVENT A RESULT. Not a sample envelope, not a
placeholder finding, not a "typical" zone. A person reading a fabricated planning
answer cannot tell it from a real one, and this is a surface where being wrong
has professional consequences for the reader rather than for us.

INTAKE IS NOT EVIDENCE. Every field below except the address is OWNER INTENT:
what they hope to build, how much risk they want shown, what they are trying to
find out. None of it may influence zoning, authority or evidence when the engine
is eventually wired - it exists to shape which OPTIONS are presented, and it is
carried through as intent, labelled as intent.

GATE 01 IS PRESERVED. No bedroom mix, no room programme, no budget, no statement
of requirements. Those belong after an envelope exists, behind
GATE_02_OWNER_PROGRAM_ENTRY, and asking for them here would collapse planning
investigation and architectural programming into one screen.
"""
from __future__ import annotations

import logging
import re

from flask import Blueprint, current_app, render_template, request

from services.auth import login_required

logger = logging.getLogger(__name__)

planning_bp = Blueprint("planning_zoning", __name__)

DOOR_VERSION = "planning-zoning-door@2"   # +flag-gated live Toronto path

#: Section 18's classification, stated by the code rather than by a comment so a
#: test can assert it and a reader cannot be misled by a stale note.
BACKEND_READY_TO_WIRE = "BACKEND_READY_TO_WIRE"
BACKEND_PARTIALLY_READY = "BACKEND_PARTIALLY_READY"
BACKEND_NOT_ROUTABLE = "BACKEND_NOT_ROUTABLE"

#: What a person sees when they submit. Deliberately names the condition rather
#: than apologising: "not yet enabled on this environment" is true, checkable,
#: and does not imply the work is missing - it is built and not connected.
UNAVAILABLE_MESSAGE = (
    "Planning analysis is not yet enabled on this environment. Your entry was "
    "checked and nothing was run - ARCHIOSK will not show you a planning result "
    "it did not actually produce."
)

MODE_SINGLE = "single"
MODE_BATCH = "batch"
MODES = (MODE_SINGLE, MODE_BATCH)

#: Section 3. Value first, label second; the default is the middle reading -
#: zoning alone is rarely the real question, and design options are a bigger ask
#: than a first-time visitor should be defaulted into.
ANALYSIS_MODES = (
    ("zoning_check", "Zoning check"),
    ("zoning_constraints", "Zoning + planning constraints"),
    ("development_envelope", "Development envelope"),
    ("zoning_design_options", "Zoning + planning-level design options"),
)
DEFAULT_ANALYSIS_MODE = "zoning_constraints"

#: Section 4. OWNER INTENT ONLY - see the module docstring.
DEVELOPMENT_DIRECTIONS = (
    ("explore", "Explore possibilities"),
    ("residential", "Residential"),
    ("commercial", "Commercial"),
    ("mixed_use", "Mixed-use"),
    ("employment", "Industrial / Employment"),
    ("institutional", "Institutional"),
    ("other", "Other"),
)
DEFAULT_DEVELOPMENT_DIRECTION = "explore"

#: Section 5. DECISION POSTURE, not authority status: "show me relief-dependent
#: options" changes what is presented, never what is established.
OPTION_STRATEGIES = (
    ("as_of_right", "As-of-right only"),
    ("maximum_compliant", "Maximum compliant"),
    ("include_relief", "Include relief-dependent options"),
    ("include_speculative", "Include speculative test options"),
    ("show_all", "Show all"),
)
DEFAULT_OPTION_STRATEGY = "show_all"

#: Section 6.
EXISTING_CONDITIONS = (
    ("unknown", "Unknown"),
    ("vacant", "Vacant land"),
    ("existing_building", "Existing building"),
    ("addition", "Addition / expansion"),
    ("conversion", "Conversion / change of use"),
    ("redevelopment", "Redevelopment / demolition"),
)
DEFAULT_EXISTING_CONDITION = "unknown"

#: Section 11. The result surface's sections, named here in the GO-PDZ contract's
#: own terms so the page can say what it will produce without a second
#: vocabulary being invented for the same thing.
RESULT_SECTIONS = (
    "Property Identity",
    "Governing Planning Framework",
    "Permitted Development Context",
    "Development Envelope",
    "Mobility / Access Context",
    "Constraints & Opportunities",
    "Planning-Level Development Options",
    "Unresolved / Municipal Confirmation",
    "Pre-Design Conclusion",
    "Evidence Footer",
)

#: A street number followed by something. Deliberately permissive: this is an
#: intake sanity check, NOT address resolution. Deciding whether an address is
#: real is the municipal reader's job and it needs the municipality's own data;
#: a regex that tried would reject real addresses and accept invented ones.
_ADDRESS_SHAPE = re.compile(r"\d.*[A-Za-z]")
MAX_ADDRESS_LENGTH = 300
MAX_QUESTION_LENGTH = 2000
MAX_BATCH_ADDRESSES = 50


def live_enabled() -> bool:
    """Is the live Toronto path switched on for this environment?

    Read from configuration ONLY. Never from DEBUG, the hostname, the presence of
    a credential or anything else ambient: "live" is a governance state, and
    inferring it from the surroundings is how a preview becomes production
    without anyone deciding.
    """
    try:
        return bool(current_app.config.get("PLANNING_ZONING_LIVE_ENABLED", False))
    except RuntimeError:        # outside an application context
        return False


def planning_analysis_state() -> dict:
    """Can this environment actually run a planning analysis right now?

    BACKEND_NOT_ROUTABLE, and the reason is not that the engine is unfinished.
    `services/toronto_gate01.py` runs live against the City of Toronto today and
    `services/deterministic_findings.py` originates a governed FSI finding on
    every eligible run. What does not exist is an authorized route from a signed-
    in person to either of them: the GO-PDZ programme carries a standing "no
    deployment" instruction, and wiring this button would be a deployment.

    Returned as data rather than raised, so the page can be honest about the
    state instead of erroring, and so a test can assert the classification.
    """
    if live_enabled():
        return {
            "classification": BACKEND_READY_TO_WIRE,
            "live": True,
            "message": ("Live City of Toronto planning analysis is enabled on "
                        "this environment. One property per request."),
            "reason": ("PLANNING_ZONING_LIVE_ENABLED is set: a signed-in "
                       "single-property Toronto request reaches the live "
                       "Gate-01 path"),
            "door_version": DOOR_VERSION,
        }
    return {
        "classification": BACKEND_NOT_ROUTABLE,
        "live": False,
        "message": UNAVAILABLE_MESSAGE,
        "reason": (
            "the GO-PDZ planning engine is implemented and live-proven but is "
            "not routable from the application: PLANNING_ZONING_LIVE_ENABLED is "
            "not set, so no route connects a signed-in session to it"
        ),
        "door_version": DOOR_VERSION,
    }


def _selected(field, allowed, default):
    value = (request.form.get(field) or "").strip()
    return value if value in {key for key, _label in allowed} else default


def validate_address(raw) -> tuple:
    """`(address, error)`. One of them is always None.

    Checks SHAPE and LENGTH and nothing else. See `_ADDRESS_SHAPE`.
    """
    address = (raw or "").strip()
    if not address:
        return None, "Enter a property address."
    if len(address) > MAX_ADDRESS_LENGTH:
        return None, "That address is too long to be an address."
    if not _ADDRESS_SHAPE.search(address):
        return None, ("Enter a street address, including the street number - "
                      "for example 123 Queen Street West, Toronto, ON.")
    return address, None


def parse_batch(raw) -> tuple:
    """`(addresses, error)` from pasted text, one address per line.

    Stops at VALIDATED INTAKE PREPARATION (section 10). Nothing is queued,
    nothing is stored and no orchestration is attempted, because none of that
    exists yet and building it against an unroutable backend would be building
    against nothing.
    """
    lines = [line.strip() for line in (raw or "").splitlines()]
    addresses = [line for line in lines if line]
    if not addresses:
        return [], "Paste at least one address, one per line."
    if len(addresses) > MAX_BATCH_ADDRESSES:
        return [], ("That is %d addresses. This intake accepts up to %d at a "
                    "time." % (len(addresses), MAX_BATCH_ADDRESSES))
    prepared, rejected = [], []
    for line in addresses:
        address, error = validate_address(line)
        (prepared if address else rejected).append(
            {"address": line, "error": error})
    return ([entry for entry in prepared],
            None if not rejected else
            "%d of %d entries do not look like street addresses: %s"
            % (len(rejected), len(addresses),
               "; ".join(entry["address"][:40] for entry in rejected[:3])))


def _context(**overrides) -> dict:
    context = {
        "analysis_modes": ANALYSIS_MODES,
        "development_directions": DEVELOPMENT_DIRECTIONS,
        "option_strategies": OPTION_STRATEGIES,
        "existing_conditions": EXISTING_CONDITIONS,
        "result_sections": RESULT_SECTIONS,
        # The CURRENTLY SELECTED values, defaulted here so the template never
        # has to decide what a default is - one definition, and a GET renders
        # the same way a re-render after a validation error does.
        "analysis_mode": DEFAULT_ANALYSIS_MODE,
        "development_direction": DEFAULT_DEVELOPMENT_DIRECTION,
        "option_strategy": DEFAULT_OPTION_STRATEGY,
        "existing_condition": DEFAULT_EXISTING_CONDITION,
        "question": "",
        "address": "",
        "raw_addresses": "",
        "backend": planning_analysis_state(),
        "mode": MODE_SINGLE,
        "submitted": None,
        "error": None,
        "batch_error": None,
        "batch_prepared": None,
        "max_batch_addresses": MAX_BATCH_ADDRESSES,
        "live_outcome": None,
        "live_timings": None,
        # Deliberately NOT the reserved benchmark address. It is under a
        # standing seal in this programme, and section 2 permits it as
        # placeholder copy only if governance allows - so a neutral example is
        # used instead, and the sealed address is not written here either. A
        # placeholder becomes seeded example data the moment someone copies it
        # into a test, which is how a seal quietly stops holding.
        "address_placeholder": "123 Queen Street West, Toronto, ON",
    }
    context.update(overrides)
    return context


@planning_bp.route("/planning-zoning", methods=["GET"])
@login_required
def planning_zoning():
    """The intake surface. Signed-in only; no parallel permission system."""
    mode = request.args.get("mode")
    return render_template(
        "planning_zoning.html",
        **_context(mode=mode if mode in MODES else MODE_SINGLE))


@planning_bp.route("/planning-zoning/result", methods=["GET"])
@login_required
def planning_result():
    """CLAUDE-PLANNING-RESULT-SURFACE-01 - the result surface, on a fixture.

    RENDERING IS WHAT THIS PROVES, NOT ANALYSIS. The page is served from
    `planning_result_view.DEVELOPMENT_FIXTURE` - a real GO-PDZ-1.0-ONEPAGE
    document over a synthetic address, validated by the contract and by
    VR-01..VR-21 with zero errors, so the surface is exercised against something
    that could actually exist rather than against convenient shapes.

    NOTHING IS CONSULTED TO PRODUCE IT. No municipal source, no model, no live
    GO-PDZ service, and deliberately NOT the address the visitor typed on the
    intake page: rendering a fixture under someone's own address is precisely how
    a specimen becomes mistakable for an analysis.

    The page says DEVELOPMENT PREVIEW because it is one.
    """
    from services import planning_result_view

    return render_template("planning_zoning_result.html",
                           view=planning_result_view.development_view(),
                           backend=planning_analysis_state())


@planning_bp.route("/planning-zoning/analyze", methods=["POST"])
@login_required
def analyze_property():
    """Validate, then stop at the honest boundary.

    The user's entry is echoed back on every path. Losing a typed address to a
    validation message is a small cruelty that intake forms commit constantly,
    and there is no reason for it.
    """
    mode = request.form.get("mode")
    mode = mode if mode in MODES else MODE_SINGLE
    intent = {
        "analysis_mode": _selected("analysis_mode", ANALYSIS_MODES,
                                   DEFAULT_ANALYSIS_MODE),
        "development_direction": _selected("development_direction",
                                           DEVELOPMENT_DIRECTIONS,
                                           DEFAULT_DEVELOPMENT_DIRECTION),
        "option_strategy": _selected("option_strategy", OPTION_STRATEGIES,
                                     DEFAULT_OPTION_STRATEGY),
        "existing_condition": _selected("existing_condition",
                                        EXISTING_CONDITIONS,
                                        DEFAULT_EXISTING_CONDITION),
        # USER INTENT, never evidence - trimmed and bounded, not interpreted.
        "question": (request.form.get("question") or "").strip()[:MAX_QUESTION_LENGTH],
    }

    if mode == MODE_BATCH:
        prepared, batch_error = parse_batch(request.form.get("addresses"))
        return render_template("planning_zoning.html", **_context(
            mode=MODE_BATCH, batch_prepared=prepared, batch_error=batch_error,
            submitted=intent if prepared and not batch_error else None,
            raw_addresses=request.form.get("addresses") or "", **intent))

    address, error = validate_address(request.form.get("address"))
    if error:
        return render_template("planning_zoning.html", **_context(
            mode=MODE_SINGLE, error=error,
            address=request.form.get("address") or "", **intent))

    if live_enabled():
        # CLAUDE-PLANNING-LIVE-01. ONE municipality, ONE property, ONE
        # synchronous request, nothing persisted. The orchestration lives in
        # `services/planning_live.py` so that the only code in this application
        # permitted to reach a municipal source on a signed-in person's behalf
        # is one auditable file rather than a branch inside a view.
        from services import planning_live

        live = planning_live.run_live(address)
        if live["outcome"] != planning_live.OUTCOME_OK:
            # A NAMED failure, rendered on the intake page beside the address
            # that caused it. No result-shaped nothing, and no substitute
            # authority - the person is told which source could not be
            # established and that nothing was produced.
            logger.info("live planning request refused: %s", live["outcome"])
            return render_template("planning_zoning.html", **_context(
                mode=MODE_SINGLE, address=address, error=live["message"],
                live_outcome=live["outcome"], live_timings=live["timings"],
                **intent))
        logger.info("live planning request served in %.0f ms (%s)",
                    live["timings"].get("total_ms") or 0.0, address)
        return render_template("planning_zoning_result.html",
                               view=live["view"],
                               backend=planning_analysis_state(),
                               timings=live["timings"],
                               source_failures=live["source_failures"],
                               intent=intent)

    # VALID INTAKE, NO ANALYSIS. The one thing this must not do is manufacture a
    # result, so the address is echoed with the development-state boundary and
    # nothing is run, queued or stored.
    logger.info("planning intake accepted (mode=%s) - backend %s",
                intent["analysis_mode"], BACKEND_NOT_ROUTABLE)
    return render_template("planning_zoning.html", **_context(
        mode=MODE_SINGLE, address=address, submitted=intent, **intent))
