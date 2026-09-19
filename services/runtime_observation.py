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
         "uncertainty", "provenance", "admissible", "source_evidence_ids", "premise_ids"}


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
                (folder / ("_job-"+_job_key(bound)+".json")).write_text(json.dumps(
                    dict(id=parent["id"], actor=parent["actor"], expires=time.time()+900)),encoding="utf-8")
            except OSError:
                current_app.logger.exception("Background observation could not be linked")
        event(owner, "INVOKED", inputs={k: summary(v) for k,v in bound.items()
              if k not in ("self", "app", "store", "api_key", "governance_log", "image_base64")})
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


def _finish_worker(app, record, token):
    try:
        directory(app).mkdir(parents=True,exist_ok=True)
        (directory(app)/(record["id"]+".json")).write_text(json.dumps(
            {k:v for k,v in record.items() if k!="started"},default=str),encoding="utf-8")
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
                         arguments=request.view_args or {}), actor=session.get("username"), events=[])
        g.survey_observation = record
        g.survey_observation_token = _active.set(record)
        event("flask", "REQUEST", route=request.endpoint)

    @app.after_request
    def finish(response):
        record = getattr(g, "survey_observation", None)
        if record is not None:
            event("flask", "SURFACED", http_status=response.status_code,
                  content_type=response.content_type, location=response.headers.get("Location"))
            payload = {k:v for k,v in record.items() if k != "started"}
            try:
                folder = directory(app)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (record["id"]+".json")).write_text(json.dumps(payload, default=str), encoding="utf-8")
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
    return [json.loads(p.read_text(encoding="utf-8")) for p in records]


def read(app, identifier):
    if len(identifier) != 32 or any(c not in "0123456789abcdef" for c in identifier):
        return None
    try:
        return json.loads((directory(app)/(identifier+".json")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
