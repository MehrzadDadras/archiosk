"""Opt-in request observations. References and actual returns, never authority.

The existing flight deck describes stored qualification. This records invocation
at the owned call boundary. It does not invoke resolvers or interpret results.
"""
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
import inspect
import hashlib
import json
import time
import uuid

_active = ContextVar("survey_runtime_observation", default=None)
_keys = {"id", "project_id", "source_id", "evidence_item_id", "region_id",
         "state", "status", "errors", "error", "operator", "read_certainty",
         "bind_certainty", "currentness", "authority", "geometry_level",
         "coordinate_space", "source_space", "target_space", "source_plane",
         "target_plane", "plane_id", "evaluation_only", "reason", "computed",
         "qualification", "qualification_preserved", "evidence_class", "field",
         "from_id", "to_id", "relationship_type", "confirmed_by", "ran",
         "skipped_reason", "parse_status", "conditioning", "label", "value",
         "established", "interpretation", "not_established", "primitives", "tags", "filename", "name",
         "uncertainty", "provenance", "admissible", "source_evidence_ids", "premise_ids",
         "action_id", "action_class", "parameters", "degrees", "axis", "user_requested", "view_id",
         "parent_view_id", "matrix", "type", "coordinate_space_before", "coordinate_space_after",
         "clockwise_degrees", "lower", "upper", "subject", "parameter", "unit", "common_interval",
         "baseline", "failure_point", "margin_to_failure", "origin", "canonical", "direction",
         "first_violated_constraints", "subject_key", "property_key", "scope_key", "kind", "basis",
         "qualifiers", "view_basis", "vocabulary", "factual_consistency", "input_status", "command",
         "structured_proposition", "normalization", "source_class", "temporal_class", "as_of", "valid_until",
         "original_quote", "classification_reason", "evidence_fingerprints", "source_file_hash", "content_sha256",
         "adoption_state", "created_by", "created_at", "confidence_state", "claim_class", "claim",
         "derived_observation", "derived_observation_id", "adopted_by", "adopted_at", "adoption_reason",
         "criteria", "mandatory", "required", "candidate", "operator", "blocked_reason", "mandatory_failures",
         "unresolved", "factual_fit", "query_date", "expected_class", "model_label", "target_subject",
         "required_claim_id", "candidate_claim_id", "candidate_temporal_class", "context_key", "require_currentness",
         "used_claim_ids", "unselected_claim_ids", "consumption_state", "premise_statuses", "source_integrity"}


def current_reference():
    """Optional operational link; retaining a link does not confer authority."""
    record = _active.get()
    return record['id'] if record is not None else None


def muscle_exposure(record):
    """Project recorded events against contracts without invoking a domain owner.

    Calls/returns are retained in sequence, not paired by guessed causality.
    A catalogue entry, a return alone or an incomplete trace is not invocation
    proof. No PASS score or stronger governed state is manufactured here.
    """
    from services.capability_registry import MUSCLE_CONTRACTS
    events = (record or {}).get('events', [])
    rows = []
    for owner, contract in MUSCLE_CONTRACTS.items():
        recorded = [event for event in events if event.get('owner') == owner
                    and event.get('phase') in contract['runtime_hooks']]
        invoked = sum(event['phase'] == 'INVOKED' for event in recorded)
        rows.append(dict(owner=owner, contract=contract, events=recorded, invoked_count=invoked,
            invocation_state='INVOKED' if invoked else 'NOT_OBSERVED',
            return_count=sum(event['phase'] == 'RETURNED' for event in recorded),
            error_count=sum(event['phase'] == 'RAISED' for event in recorded)))
    return dict(trace_id=(record or {}).get('id'), request=(record or {}).get('request'),
        truncated=bool((record or {}).get('truncated')), muscles=rows,
        consumer_events=[event for event in events if event.get('phase') in ('CONSUMED', 'SURFACED')],
        qualification='Observational projection of this trace only. NOT_OBSERVED does not mean unimplemented. '
            'Invocation does not prove correctness; returns retain their recorded qualification. '
            'Consumers and surfaced responses are request-level records, not inferred per-muscle success.')


def summary(value, depth=0):
    if depth > 4:
        return {"omitted": "depth limit"}
    if isinstance(value, dict):
        return {k: summary(v, depth+1) for k,v in value.items() if k in _keys}
    if isinstance(value, (tuple, list)):
        return [summary(v, depth+1) for v in value[:40]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value[:2000] if isinstance(value, str) else value
    return summary(vars(value), depth+1) if hasattr(value, "__dict__") else {"type": type(value).__name__}


def event(owner, phase, **details):
    record = _active.get()
    if record is not None:
        if len(record["events"]) >= 10000:
            record["truncated"] = True
            return
        record["events"].append(dict(sequence=len(record["events"])+1,
            elapsed_ms=round((time.monotonic()-record["started"])*1000, 3),
            owner=owner, phase=phase, **details))


def observed(fn):
    signature = inspect.signature(fn)
    owner = fn.__module__ + "." + fn.__qualname__
    @wraps(fn)
    def call(*args, **kwargs):
        bound = None
        worker = None
        if owner == "services.visual_classification.examine_source" and _active.get() is None:
            bound = signature.bind(*args, **kwargs).arguments
            app, job = bound["app"], bound["job"]
            marker = directory(app) / ("_job-" + _job_key(job) + ".json")
            try:
                parent = json.loads(marker.read_text(encoding="utf-8"))
                if parent["expires"] >= time.time():
                    record = dict(id=uuid.uuid4().hex, started=time.monotonic(), actor=parent["actor"],
                        observed_enqueue_request=parent["id"], events=[],
                        request=dict(method="WORKER",path="visual-job/"+str(job.get("job_id")), endpoint=owner,
                            arguments={k:job.get(k) for k in ("job_id","workspace_id","source_id","source_sha256")}))
                    worker = (app, record, _active.set(record))
            except (OSError, ValueError, KeyError):
                pass
        if _active.get() is None:
            return fn(*args, **kwargs)
        bound = bound or signature.bind(*args, **kwargs).arguments
        if owner == "services.visual_classification.enqueue_for_source":
            from flask import current_app
            try:
                folder = directory(current_app)
                folder.mkdir(parents=True, exist_ok=True)
                parent = _active.get()
                _retain(current_app, dict(id=parent["id"], actor=parent["actor"], expires=time.time()+900,
                    request=dict(arguments=dict(workspace_id=bound.get("workspace_id")))),
                    filename="_job-" + _job_key(bound) + ".json")
            except OSError:
                current_app.logger.exception("Background observation could not be linked")
        event(owner, "INVOKED", inputs={k: summary(v) for k,v in bound.items()
              if k not in ("self", "app", "store", "api_key", "governance_log", "image_base64", "content")})
        if owner == "services.llm_gateway.call_llm_json":
            event(owner, "PROVIDER_INPUT", user_prompt=bound.get("user_prompt"),
                  system_prompt=bound.get("system_prompt"), model=bound.get("model"),
                  image_attached=bool(bound.get("image_base64")))
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            event(owner, "RAISED", exception=type(exc).__name__,
                  diagnostic=summary(getattr(exc, "diagnostic", None)))
            if worker:
                _finish_worker(*worker)
            raise
        event(owner, "RETURNED", result=summary(result))
        if owner == "services.llm_gateway.call_llm_json":
            event(owner, "PROVIDER_OUTPUT", parsed=getattr(result, "parsed", None),
                  raw_text=getattr(result, "raw_text", None), ran=getattr(result, "ran", False))
        if owner == "services.document_conversation.ask":
            event(owner, "FINAL_ADMISSION", answer=result.get("answer"), reason=result.get("reason"))
        if worker:
            _finish_worker(*worker)
        return result
    return call


def directory(app):
    return Path(app.instance_path) / "runtime_observations"


def _job_key(values):
    return hashlib.sha256(json.dumps([values.get(k) for k in ("workspace_id","source_id","source_sha256")]).encode()).hexdigest()


def case_id(record):
    arguments = record.get("request", {}).get("arguments", {})
    selection = record.get("request", {}).get("selection", [])
    return arguments.get("project_id") or arguments.get("workspace_id") or (selection[0] if len(selection) == 1 else None)


def deleted_case(app, record):
    from services.requirements_registry import RequirementsRegistry
    identifier = case_id(record)
    registry = RequirementsRegistry(app.config["REGISTRY_STORE_PATH"])
    if not identifier:
        return False
    if registry.is_deleted(identifier):
        return True
    path = registry.store_path / (identifier + '.workspace.json')
    try:
        workspace = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return workspace.get('container_state') == 'black_box' and workspace.get('document_desk_state', 'active') != 'active'



def remove_case(app, project_id):
    """Remove only observations owned by this case; evaluation runs have independent owners."""
    from services.perception_jobs import PerceptionJobStore
    for job in PerceptionJobStore(app.config["REGISTRY_STORE_PATH"], subdir="visual_jobs").for_workspace(project_id):
        (directory(app) / ("_job-" + _job_key(job) + ".json")).unlink(missing_ok=True)
    for path in directory(app).glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if case_id(record) == project_id:
            path.unlink(missing_ok=True)


def _retain(app, record, filename=None):
    from contextlib import nullcontext
    from services.requirements_registry import RequirementsRegistry
    registry = RequirementsRegistry(app.config["REGISTRY_STORE_PATH"])
    identifier = case_id(record)
    with registry.lifecycle_lock(identifier) if identifier else nullcontext():
        if deleted_case(app, record):
            return False
        directory(app).mkdir(parents=True, exist_ok=True)
        (directory(app) / (filename or record["id"] + ".json")).write_text(json.dumps(
            {k: v for k, v in record.items() if k != "started"}, default=str), encoding="utf-8")
        return True


def _finish_worker(app, record, token):
    try:
        _retain(app, record)
    except OSError:
        app.logger.exception("Background observation could not be retained")
    finally:
        _active.reset(token)


def install(app):
    from flask import g, request, session
    from services.auth import is_admin
    @app.before_request
    def begin():
        if (not session.get("survey_observe") or not session.get("developer_mode")
                or not is_admin() or request.path.startswith("/static/")):
            return
        record = dict(id=uuid.uuid4().hex, started=time.monotonic(),
            request=dict(method=request.method, path=request.path, endpoint=request.endpoint,
                         arguments=request.view_args or {},
                         selection=list(dict.fromkeys(request.form.getlist('project_id'))) if request.endpoint == 'portal.document_shop_bulk' else []),
            actor=session.get("username"), events=[])
        g.survey_observation = record
        g.survey_observation_token = _active.set(record)
        event("flask", "REQUEST", route=request.endpoint)

    @app.after_request
    def finish(response):
        record = getattr(g, "survey_observation", None)
        if record is not None and not deleted_case(app, record):
            event("flask", "SURFACED", http_status=response.status_code,
                  content_type=response.content_type, location=response.headers.get("Location"))
            payload = {k:v for k,v in record.items() if k != "started"}
            try:
                if _retain(app, payload):
                    response.headers["X-ARCHIOSK-Observation"] = record["id"]
            except OSError:
                app.logger.exception("Operational observation could not be retained")
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.teardown_request
    def clear(error):
        token = getattr(g, "survey_observation_token", None)
        if token is not None:
            _active.reset(token)
            del g.survey_observation_token


def recent(app):
    folder = directory(app)
    if not folder.exists():
        return []
    records = sorted((p for p in folder.glob("*.json") if not p.name.startswith("_")), key=lambda p:p.stat().st_mtime, reverse=True)[:30]
    return [record for p in records if (record := read(app, p.stem)) is not None]


def read(app, identifier):
    if len(identifier) != 32 or any(c not in "0123456789abcdef" for c in identifier):
        return None
    try:
        record = json.loads((directory(app)/(identifier+".json")).read_text(encoding="utf-8"))
        return None if deleted_case(app, record) else record
    except (OSError, ValueError):
        return None
