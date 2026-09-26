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

from flask import Blueprint, abort, current_app, render_template, request, send_file, session, redirect, url_for

from services.auth import login_required

logger = logging.getLogger(__name__)

planning_bp = Blueprint("planning_zoning", __name__)


def _working_studies():
    from services.planning_studies import WorkingResults
    return WorkingResults(current_app.config['REGISTRY_STORE_PATH'])


def _study_workspace(project_id):
    from routes.workspace import _load_workspace_or_404
    return _load_workspace_or_404(project_id)


def _study_projects():
    """The projects this person may put a study in: the access-scoped list, each
    labelled by the PROJECT record's own identity - never a source filename.

    Label = the governed name (ProjectWorkspace.display_title), then the project
    code, in the Context rail's established "Name · CODE" form. Project codes are
    unique and never reused, so two projects with the same name stay
    distinguishable. A project with no display title falls back to its code, then
    its id. The submitted value is always the project id."""
    from services.ingestion import get_registry
    from services.case_workspace import CaseWorkspaceStore
    from routes.portal import _accessible_documents, _safe_workspace
    store=CaseWorkspaceStore(current_app.config['REGISTRY_STORE_PATH'])
    projects=[]
    for d in _accessible_documents(get_registry(current_app),store):
        workspace=_safe_workspace(store, d.project_id)
        name=((getattr(workspace,'display_title',None) or '').strip()) if workspace else ''
        code=(getattr(workspace,'project_code',None) or '').strip() if workspace else ''
        label=' · '.join(part for part in (name, code) if part) or d.project_id
        projects.append({'id':d.project_id,'label':label})
    return projects


@planning_bp.route('/planning-zoning/studies')
@login_required
def saved_studies():
    project_id=request.args.get('project_id')
    studies=[]
    if project_id:
        _,store,workspace=_study_workspace(project_id)
        studies=list(reversed(workspace.planning_studies))
    return render_template('planning_studies.html', projects=_study_projects(),
                           project_id=project_id, studies=studies)


@planning_bp.route('/planning-zoning/projects/<project_id>/studies', methods=['POST'])
@login_required
def save_study(project_id):
    from services import planning_studies
    from routes.workspace import _require_export_allowed
    _,store,workspace=_study_workspace(project_id)
    formats=request.form.getlist('formats')
    if formats:
        denied=_require_export_allowed(workspace,project_id)
        if denied:return denied
    key=request.form.get('study_token','')
    try:
        record=_working_studies().save_study(store,key,project_id,session.get('username'),formats=formats)
    except (ValueError, FileExistsError) as exc:
        abort(409,description=str(exc))
    return redirect(url_for('planning_zoning.open_study',project_id=project_id,study_id=record['id']))


@planning_bp.route('/planning-zoning/projects/<project_id>/studies/<study_id>')
@login_required
def open_study(project_id,study_id):
    from services import planning_studies, planning_result_view
    _,store,workspace=_study_workspace(project_id)
    try:result=planning_studies.reopen(store,workspace,study_id)
    except (ValueError, OSError):abort(404)
    record=next(s for s in workspace.planning_studies if s['id']==study_id)
    if result.get('workspace_context'):
        return _render_composer(result, project_id, saved_study=record)
    return render_template('planning_zoning_result.html',view=planning_result_view.build_view(result),
        backend=planning_analysis_state(),panels=[],user_panels=[],has_contributions=False,
        exportable=False,saved_study=record,study_project_id=project_id,
        address=record['address'],classifications=[],classification_labels={})


def _render_composer(result, project_id, run_id=None, saved_study=None):
    from services import planning_composer, planning_result_view, planning_report, planning_visual
    sites = []
    for index, item in enumerate(planning_composer.properties(result)):
        view = planning_result_view.build_view(item)
        sites.append({'index': index, 'view': view, 'report': planning_composer.report_view(view, item, result['workspace_context']),
                      'panels': planning_visual.panels_for(item.get('retrieval') or {}, tokens=item.get('spatial_tokens'))})
    return render_template('planning_composer.html', sites=sites, context=result['workspace_context'],
                           project_id=project_id, run_id=run_id, saved_study=saved_study,
                           planning_composer_active=True)


@planning_bp.route('/planning-zoning/projects/<project_id>/working/<run_id>')
@login_required
def working_study(project_id, run_id):
    _study_workspace(project_id)
    try:
        result = _working_studies().get(run_id, project_id, session.get('username'))
    except ValueError as exc:
        abort(409, description=str(exc))
    return _render_composer(result, project_id, run_id)


@planning_bp.route('/planning-zoning/projects/<project_id>/studies/<study_id>/continue', methods=['POST'])
@login_required
def continue_study(project_id, study_id):
    from services import planning_studies, planning_composer
    _, store, workspace = _study_workspace(project_id)
    try:
        result = planning_studies.reopen(store, workspace, study_id)
        if not result.get('workspace_context'):
            result = planning_composer.initialize([result])
        result['workspace_context']['continued_from_study_id'] = study_id
        key = _working_studies().put(project_id, session.get('username'), result)
    except (ValueError, OSError) as exc:
        abort(409, description=str(exc))
    return redirect(url_for('planning_zoning.working_study', project_id=project_id, run_id=key))


@planning_bp.route('/planning-zoning/projects/<project_id>/working/<run_id>/conversation', methods=['POST'])
@login_required
def converse_study(project_id, run_id):
    from services import planning_composer, conversational_turn
    from services.conversation_interpreter import _evaluate_external_ai_policy
    from services.security_policy import DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE
    _, store, workspace = _study_workspace(project_id)
    text = (request.form.get('text') or '').strip()
    if not text or len(text) > 4000 or request.form.get('image_data_url'):
        abort(400, description='Enter a text message of 1–4000 characters')
    try:
        result = _working_studies().get(run_id, project_id, session.get('username'))
        bounded = planning_composer.envelope(result, project_id, run_id)
    except ValueError as exc:
        abort(409, description=str(exc))
    from routes.portal import gopilot_turn_labels
    gopilot_turn_labels("PLANNING_STUDY", text, context={"project_id": project_id, "run_id": run_id})
    policy = _evaluate_external_ai_policy(store, workspace)
    if policy.decision not in (DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE):
        abort(403, description='Project policy does not allow external AI requests')
    turn = conversational_turn.run_conversational_turn(text=text, workspace=workspace, envelope=bounded,
        recent_history=result['workspace_context']['messages'][-12:])
    if not turn.ran:
        abort(503, description='GO is unavailable; the retained study is unchanged')
    try:
        revised = planning_composer.revise(result, text, turn, run_id, actor=session.get('username'))
        key = _working_studies().put(project_id, session.get('username'), revised)
    except ValueError as exc:
        abort(409, description=str(exc))
    return redirect(url_for('planning_zoning.working_study', project_id=project_id, run_id=key))


@planning_bp.route('/planning-zoning/projects/<project_id>/working/<run_id>/investigate', methods=['POST'])
@login_required
def investigate_study(project_id, run_id):
    from services import planning_composer, planning_live
    _study_workspace(project_id)
    if not live_enabled():
        abort(409, description='Live planning retrieval is disabled')
    try:
        result = _working_studies().get(run_id, project_id, session.get('username'))
        pending = result['workspace_context'].get('pending_action') or {}
        if pending.get('kind') != 'investigate':
            raise ValueError('No pending investigation for this revision')
        index = pending['property_index']
        item = planning_composer.properties(result)[index]
        address = item['document']['subject']['normalized_address']
    except (ValueError, KeyError, IndexError) as exc:
        abort(409, description=str(exc))
    # This is the existing governed retrieval/compiler path. Never accept URLs,
    # facts or authority state from a Composer response.
    live = planning_live.run_live(address)
    if live['outcome'] != planning_live.OUTCOME_OK or not live.get('study_snapshot'):
        abort(409, description=live.get('message') or 'Investigation remains unresolved')
    replacement = live['study_snapshot']
    if replacement['document']['subject'].get('parcel_identifier') != item['document']['subject'].get('parcel_identifier'):
        abort(409, description='Parcel identity changed; start a new analysis')
    sites = planning_composer.properties(result)
    sites[index] = replacement
    revised = planning_composer.initialize(sites)
    revised['workspace_context'] = result['workspace_context']
    revised['workspace_context'].pop('pending_action', None)
    revised['workspace_context']['parent_run_id'] = run_id
    # Proposal calculations refer to the former evidence version. Do not carry
    # their assessments over a new authority read as if recomputed.
    revised['workspace_context']['proposal'] = []
    revised['workspace_context']['messages'].append({'role': 'system',
        'content_class': 'deterministic_calculation',
        'text': 'Planning sources refreshed for ' + address + '. Review remaining unresolved items. Prior comparisons remain in the preceding revision.'})
    key = _working_studies().put(project_id, session.get('username'), revised)
    return redirect(url_for('planning_zoning.working_study', project_id=project_id, run_id=key))


@planning_bp.route('/planning-zoning/projects/<project_id>/studies/<study_id>/artifacts/<path:name>')
@login_required
def study_artifact(project_id,study_id,name):
    import io
    from services import planning_studies
    from routes.workspace import _require_export_allowed
    _,store,workspace=_study_workspace(project_id)
    if name!='evidence/zoning-map.png':
        denied=_require_export_allowed(workspace,project_id)
        if denied:return denied
    try:raw=planning_studies.artifact(store,workspace,study_id,name)
    except (ValueError,OSError):abort(404)
    return send_file(io.BytesIO(raw),download_name=name.rsplit('/',1)[-1],
        mimetype='image/png' if name=='evidence/zoning-map.png' else None,
        as_attachment=name!='evidence/zoning-map.png')

DOOR_VERSION = "planning-zoning-door@3"   # +workspace: export, visuals, contribution

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
        "planning_entry.html",
        **_context(mode=mode if mode in MODES else MODE_SINGLE,
                   planning_projects=_study_projects(), project_id=request.args.get('project_id', ''),
                   sandbox_origin=_sandbox_origin(request.args.get('sandbox'))))


def _sandbox_origin(sandbox_id):
    """MORPHOSIS SLICE 1: the signed-in user's OWN Sandbox this study starts
    from, as lineage - or None. Another user's id, or an unknown one, is None:
    lineage is never borrowed."""
    if not sandbox_id:
        return None
    from services import sandbox as sb
    record = sb.SandboxStore(current_app.config["REGISTRY_STORE_PATH"]).get(
        session.get('username'), sandbox_id)
    return sb.lineage(record) if record and record.get("turns") else None


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
    from services import planning_contribution
    from services import planning_result_view

    return render_template(
        "planning_zoning_result.html",
        view=planning_result_view.development_view(),
        backend=planning_analysis_state(),
        # The fixture carries no municipal geometry, so there are no official
        # panels to draw and the surface says so rather than showing empty frames.
        panels=[], user_panels=[], has_contributions=False,
        # EXPORT IS OFFERED ON THE FIXTURE TOO, and it exports AS a fixture: the
        # document leads with "DEVELOPMENT FIXTURE ... NOT an analysis of any real
        # property", driven by the view's own `preview` flag rather than by which
        # route asked. A preview that exported as though it were analysis would be
        # the worst artifact this tranche could produce.
        exportable=True,
        classifications=planning_contribution.CLASSIFICATIONS,
        classification_labels=planning_contribution.CLASSIFICATION_LABELS)


@planning_bp.route("/planning-zoning/export", methods=["GET", "POST"])
def export_result():
    """Read-only download from retained state. POST remains compatible.

    GET permits ordinary downloads and login-return navigation. No address-only
    request can reconstruct a live result. Saved artifacts use study_artifact.
    """
    from services import planning_export, planning_result_view, planning_visual
    from services import auth
    from flask import jsonify

    if not auth.is_authenticated():
        # Unlike a mutating form, a download can safely resume as GET. Preserve
        # its bounded identity parameters through login; never replay a POST.
        params = request.args if request.method == 'GET' else request.form
        resume = url_for('planning_zoning.export_result', **{
            k: params[k] for k in ('format','scope','project_id','study_token') if k in params})
        login_url = url_for('portal.login', next=resume)
        if auth.wants_json_response():
            return jsonify(error='session_expired', redirect=login_url), 401
        return redirect(login_url)

    params = request.args if request.method == 'GET' else request.form
    export_format = (params.get('format') or '').strip().lower()
    if export_format not in planning_export.FORMATS:
        abort(400)
    scope = params.get('scope') or planning_export.SCOPE_GOVERNED_ONLY
    if scope not in planning_export.SCOPES:
        abort(400)
    project_id = params.get('project_id','')
    key = params.get('study_token','')
    panels = []
    if key or project_id:
        from routes.workspace import _require_export_allowed
        _, store, workspace = _study_workspace(project_id)
        denied = _require_export_allowed(workspace, project_id)
        if denied: return denied
        try:
            result = _working_studies().get(key, project_id, session.get('username'))
        except ValueError as exc:
            abort(409, description=str(exc))
        view = planning_result_view.build_view(result)
        panels = planning_visual.panels_for(view.get('retrieval') or {})
        # Browser prose is not retained host evidence. The qualified snapshot
        # currently contains the governed result only.
        if scope != planning_export.SCOPE_GOVERNED_ONLY:
            abort(409, description='Follow-up is not part of this retained snapshot')
        if result.get('workspace_context'):
            from services import planning_composer, document_export
            try:
                stream = document_export.build(planning_composer.report_document(result), export_format)
            except ValueError as exc:
                abort(409, description=str(exc))
            return send_file(stream, mimetype=document_export.MIMETYPES[export_format], as_attachment=True,
                             download_name=planning_export.filename_for(view['identity'], export_format))
    elif live_enabled() or params.get('address'):
        abort(409, description='Retained study required; export does not rerun analysis')
    else:
        view = planning_result_view.development_view()
        scope = planning_export.SCOPE_GOVERNED_ONLY

    stream, filename, mimetype = planning_export.export(
        view, export_format, scope=scope, panels=panels, generated_at=_now_iso())
    stream.seek(0)
    return send_file(stream, mimetype=mimetype, as_attachment=True,
                     download_name=filename)


#: CLAUDE-PLANNING-WORKSPACE-02A. What a person may attach to one request.
#:
#: SIZE IS BOUNDED HERE AND NOT FURTHER DOWN. A contribution travels through a
#: synchronous request that also runs a municipal retrieval, so an unbounded
#: textarea is a way to make that request fail slowly.
MAX_CONTRIBUTION_LENGTH = 4000
MAX_CONTRIBUTIONS = 6


def _contributions_from(form) -> list:
    """Every human contribution in this submission, classified and provenanced.

    ONE REQUEST, ONE SET. Nothing is read from a session, a store or a prior
    request, because nothing is written to any of them - see the persistence note
    in this tranche's return. A contribution belongs to the submission that
    carried it and to nothing else.
    """
    from services import planning_contribution

    records = []
    for index in range(MAX_CONTRIBUTIONS):
        suffix = "" if index == 0 else "_%d" % index
        text = (form.get("contribution%s" % suffix) or "").strip()
        if not text:
            continue
        records.append(planning_contribution.contribution(
            text[:MAX_CONTRIBUTION_LENGTH],
            # The CLASSIFICATION IS REQUESTED, NEVER TRUSTED. `classify` falls
            # back to USER_INPUT for anything outside the permitted vocabulary,
            # so a posted `AUTHORITY_SAYS` becomes the weakest value rather than
            # the strongest one.
            classification=form.get("contribution_class%s" % suffix),
            supplied_by=_current_actor(),
            submitted_at=_now_iso(),
            object_name=(form.get("contribution_object%s" % suffix) or "").strip()
            or None,
            object_kind=(form.get("contribution_object_kind%s" % suffix)
                         or "").strip() or None,
            relates_to=form.get("contribution_relates_to%s" % suffix) or None))
    return records


def _current_actor():
    """Who supplied it, for the record. Never an entitlement - just attribution."""
    try:
        from flask_login import current_user
        return getattr(current_user, "username", None) or getattr(
            current_user, "email", None)
    except Exception:      # noqa: BLE001 - attribution must never break a request
        return None


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _workspace_layers(live, form) -> dict:
    """Section 17's four layers plus the visual panels, for one live result.

    THE GOVERNED RESULT GOES IN AND COMES OUT UNCHANGED. Everything added here
    sits beside it in separate keys; nothing writes into `live["view"]` or the
    document it projects.
    """
    from services import planning_contribution
    from services import planning_visual

    view = live.get("view") or {}
    document = live.get("document") or {}
    retrieval = view.get("retrieval") or {}
    panels = planning_visual.panels_for(retrieval)

    records = _contributions_from(form)
    facts = {"zoning": {"attributes": retrieval.get("zoning_attributes") or {}}}
    reviews = [planning_contribution.review(record, document, facts)
               for record in records]
    user_panels = [
        planning_visual.user_supplied_panel(
            name=record["supplied_object"].get("name"),
            kind=record["supplied_object"].get("kind"),
            byte_count=record["supplied_object"].get("byte_count"),
            digest=record["supplied_object"].get("sha256"))
        for record in records if record.get("supplied_object")]

    layered = planning_contribution.layered(document, view, records, reviews)
    return {
        "panels": panels,
        "user_panels": user_panels,
        "layered": layered,
        "contributions": layered["contributions"],
        "follow_up": layered["follow_up"],
        "admission": layered["admission"],
        "derived_posture": layered["derived_posture"],
        "classifications": planning_contribution.CLASSIFICATIONS,
        "classification_labels": planning_contribution.CLASSIFICATION_LABELS,
        "has_contributions": bool(records),
    }


@planning_bp.route("/planning-zoning/analyze", methods=["POST"])
@login_required
def analyze_property():
    """Validate, then stop at the honest boundary.

    The user's entry is echoed back on every path. Losing a typed address to a
    validation message is a small cruelty that intake forms commit constantly,
    and there is no reason for it.
    """
    if request.form.get('composer') == '1':
        from services import planning_live, planning_composer
        project_id = (request.form.get('project_id') or '').strip()
        if not project_id:
            abort(400, description='Choose an existing project for this study')
        _study_workspace(project_id)
        addresses = request.form.getlist('address')
        if not 1 <= len(addresses) <= planning_composer.MAX_PROPERTIES:
            abort(400, description='Enter 1–10 property addresses')
        checked = [validate_address(a) for a in addresses]
        if any(error for _, error in checked):
            abort(400, description=next(error for _, error in checked if error))
        if not live_enabled():
            abort(409, description='Live planning analysis is disabled')
        results = []
        for address, _ in checked:
            live = planning_live.run_live(address)
            if live['outcome'] != planning_live.OUTCOME_OK or not live.get('study_snapshot'):
                abort(409, description=live.get('message') or 'Property analysis unavailable')
            results.append(live['study_snapshot'])
        result = planning_composer.initialize(results, {
            'development_direction': _selected('development_direction', DEVELOPMENT_DIRECTIONS, DEFAULT_DEVELOPMENT_DIRECTION),
            'option_strategy': _selected('option_strategy', OPTION_STRATEGIES, DEFAULT_OPTION_STRATEGY),
            'existing_condition': _selected('existing_condition', EXISTING_CONDITIONS, DEFAULT_EXISTING_CONDITION)})
        # MORPHOSIS SLICE 1: a study started from a Sandbox carries where it came
        # from. The Sandbox's turns are NOT copied in as evidence - only lineage.
        origin = _sandbox_origin(request.form.get('sandbox_origin'))
        if origin:
            result['workspace_context']['origin'] = origin
        key = _working_studies().put(project_id, session.get('username'), result)
        if origin:
            from services import sandbox as sb
            sb.SandboxStore(current_app.config["REGISTRY_STORE_PATH"]).mark_promoted(
                session.get('username'), origin['sandbox_id'],
                {"landing": sb.LANDING_PLANNING_STUDY, "project_id": project_id, "run_id": key})
        return redirect(url_for('planning_zoning.working_study', project_id=project_id, run_id=key))
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

        project_id = (request.form.get('project_id') or '').strip()
        if project_id:
            _study_workspace(project_id)  # access before any project-bound work
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
        workspace = _workspace_layers(live, request.form)
        study_token = None
        if project_id and live.get('study_snapshot'):
            study_token = _working_studies().put(project_id, session.get('username'), live['study_snapshot'])
        return render_template("planning_zoning_result.html",
                               view=live["view"],
                               backend=planning_analysis_state(),
                               timings=live["timings"],
                               source_failures=live["source_failures"],
                               intent=intent,
                               address=address,
                               exportable=True,
                               study_project_id=project_id, study_token=study_token,
                               **workspace)

    # VALID INTAKE, NO ANALYSIS. The one thing this must not do is manufacture a
    # result, so the address is echoed with the development-state boundary and
    # nothing is run, queued or stored.
    logger.info("planning intake accepted (mode=%s) - backend %s",
                intent["analysis_mode"], BACKEND_NOT_ROUTABLE)
    return render_template("planning_zoning.html", **_context(
        mode=MODE_SINGLE, address=address, submitted=intent, **intent))
