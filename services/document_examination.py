"""CLAUDE-DOCUMENT-SHOP-RESULT-01 - what the customer is actually handed.

A presentation layer and explicit human review commands over existing owners.
GET inspection calls no producer and review commands persist in EvidenceItems.
The original result builder introduces no second
As-Read: `ingest_upload` already parses every accepted document and already
runs local OCR over an accepted image, and every fact below is read back from
what those two paths recorded. The defect this closes was never missing
processing - it was that the processing had no customer-facing surface, so a
person who uploaded a document was sent to the analyst bench instead and told
"As-Read has not started on this source".

    SIMPLE OUTSIDE. GOVERNED INSIDE.

Three things this deliberately does NOT do:

- **It does not invent a status transition.** Examination is synchronous
  inside the upload request, so by the time any record exists it has already
  finished. There is therefore no honest PENDING/PROCESSING state to show, and
  inventing one would be a status unsupported by any record. `state_of` returns
  only outcomes that a stored record can actually establish.
- **It does not fabricate an interpretation.** Where the pipeline established
  nothing, this says so by name rather than rendering an empty section that
  reads like a finished answer.
- **It does not translate governed vocabulary into the record.** As-Read,
  Spin, marks, vectorisation and sheet grammar stay exactly where they are;
  they are simply not what a Document Shop customer is shown.
"""
from __future__ import annotations

from services.runtime_observation import observed
from pathlib import Path
from typing import Any, Optional
from copy import deepcopy
import hashlib
import json
import uuid
import difflib


REVIEW_CORRECTION = 'reviewed_transcription'
REVIEW_ACTION = 'transcription_review_action'
REVIEW_RESULT = 'document_review_result'
DOCUMENT_FRAME = 'document_frame'


def _review_records(workspace, source_id, content_type):
    rows = []
    for evidence in getattr(workspace, 'evidence_items', []) or []:
        if evidence.get('source_id') != source_id or evidence.get('content_type') != content_type:
            continue
        try:
            payload = json.loads(evidence['content'])
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict):
            rows.append(dict(payload, id=evidence['id'], reviewer=evidence.get('created_by'),
                             timestamp=evidence.get('created_at')))
    return rows


def _review_signature(workspace, source_id):
    # A consumer result is not a new premise for itself. This fingerprint only
    # detects stale consumption; it cannot establish authority or currentness.
    evidence = [e for e in getattr(workspace, 'evidence_items', []) if e.get('source_id') == source_id
                and e.get('content_type') != REVIEW_RESULT]
    source = next((s for s in getattr(workspace, 'sources', []) if s['id'] == source_id), {})
    return hashlib.sha256(json.dumps([source, evidence, getattr(workspace, 'relationships', []),
        getattr(workspace, 'supersessions', [])], sort_keys=True, default=str).encode()).hexdigest()


def source_review_state(workspace, source_id):
    corrections = _review_records(workspace, source_id, REVIEW_CORRECTION)
    actions = _review_records(workspace, source_id, REVIEW_ACTION)
    for correction in corrections:
        related = [a for a in actions if a.get('correction_id') == correction['id']]
        correction['status'] = related[-1]['action'].upper() if related else 'PROPOSED'
        correction['review_action_id'] = related[-1]['id'] if related else None
        correction['review_history'] = related
        correction['diff'] = list(difflib.ndiff(str(correction['before']).splitlines(),
                                               str(correction['after']).splitlines()))
    results = _review_records(workspace, source_id, REVIEW_RESULT)
    result = results[-1] if results else None
    frames = _review_records(workspace, source_id, DOCUMENT_FRAME)
    return dict(corrections=corrections, result=result, frame=frames[-1] if frames else None,
        stale=bool(result and result.get('premise_signature') != _review_signature(workspace, source_id)),
        pending=bool(corrections or frames) and not result)


def review_text_fields(workspace, source_id):
    """An allowlist of actual machine-read text fields, never arbitrary JSON edits."""
    from services.visual_examination import VISUAL_CONTENT_TYPE
    fields = []
    current_visual = _decoded_record(workspace, source_id, VISUAL_CONTENT_TYPE) or {}
    regions = {r['id']:r for r in workspace.addressable_regions}
    def add(evidence, path, value, label, object_id=None):
        if not isinstance(value, (str, int, float)) or isinstance(value, bool) or not str(value).strip():
            return
        region = regions.get(evidence.get('region_id'), {})
        fields.append(dict(key=evidence['id']+'|'+path, evidence_id=evidence['id'], path=path,
            value=value, label=label, anchor=dict(source_id=source_id, region_id=evidence.get('region_id'),
            structural_unit_id=region.get('structural_unit_id'), address=region.get('address'),
            object_id=object_id, field_path=path)))
    for evidence in workspace.evidence_items:
        if evidence.get('source_id') != source_id:
            continue
        if evidence.get('content_type') == 'positioned_text':
            add(evidence, 'content', evidence.get('content'), 'Positioned text / label / note')
        elif evidence.get('content_type') == VISUAL_CONTENT_TYPE:
            if evidence['id'] != current_visual.get('evidence_item_id'):
                continue
            try:
                visual = json.loads(evidence['content'])
            except (ValueError, TypeError):
                continue
            for index, row in enumerate(visual.get('observations', [])):
                add(evidence, f'observations/{index}/value', row.get('value'), row.get('label') or row.get('key'), row.get('key'))
            for index, segment in enumerate((visual.get('graph') or {}).get('segments', [])):
                for kind in ('dimension', 'bearing'):
                    for key in ('text', 'value'):
                        add(evidence, f'graph/segments/{index}/{kind}/{key}',
                            (segment.get(kind) or {}).get(key), kind.title()+' '+str(segment.get('id')), segment.get('id'))
    # Meaningful title/dimension/label regions precede stray OCR glyphs. The
    # complete immutable read remains accessible; this ordering grants no trust.
    import re
    fields.sort(key=lambda f: (not bool(re.search(r'dat(?:e|ed)|survey|prepared|plan|bearing|dimension|\d{2}',
        str(f['label'])+' '+str(f['value']), re.I)), len(str(f['value']).strip()) < 3))
    return fields


def _store_review(store, workspace, source_id, content_type, payload, actor, region_id=None):
    evidence_class = 'normalized_evidence' if content_type == REVIEW_RESULT else 'user_entered_evidence'
    return store.register_evidence_item(workspace, source_id, evidence_class,
        json.dumps(payload, allow_nan=False), content_type, region_id=region_id, actor=actor)


@observed
def propose_text_correction(store, workspace, source_id, key, after, reason, actor):
    field = next((f for f in review_text_fields(workspace, source_id) if f['key'] == key), None)
    if not field or not reason.strip() or not after.strip() or len(after) > 4000:
        raise ValueError('Select an existing structured reading and supply a correction and source-based reason.')
    if isinstance(field['value'], (int, float)):
        import math
        after = float(after)
        if not math.isfinite(after):
            raise ValueError('Corrected numeric reading must be finite.')
    if after == field['value']:
        raise ValueError('The corrected reading is unchanged.')
    machine = store.get_evidence_item(workspace, field['evidence_id'])
    payload = dict(machine_evidence_id=machine['id'], machine_hash=hashlib.sha256(machine['content'].encode()).hexdigest(),
        field_path=field['path'], anchor=field['anchor'], before=field['value'], after=after,
        reason=reason.strip(), read_certainty='RECOVERED', binding='UNCHANGED', authority='UNCHANGED',
        applicability='UNCHANGED', precedence='UNCHANGED', currentness='UNCHANGED')
    # Duplicate submission is not new evidence.
    for existing in _review_records(workspace, source_id, REVIEW_CORRECTION):
        if all(existing.get(k) == v for k,v in payload.items()):
            return store.get_evidence_item(workspace, existing['id'])
    return _store_review(store, workspace, source_id, REVIEW_CORRECTION, payload, actor, machine.get('region_id'))


@observed
def review_text_correction(store, workspace, source_id, correction_id, action, actor):
    correction = next((c for c in source_review_state(workspace, source_id)['corrections'] if c['id'] == correction_id), None)
    if not correction or action not in ('accept', 'revert'):
        raise ValueError('Unknown correction or review action.')
    machine = store.get_evidence_item(workspace, correction['machine_evidence_id'])
    if not machine or hashlib.sha256(machine['content'].encode()).hexdigest() != correction['machine_hash']:
        raise ValueError('Machine reading changed; the correction must be reviewed against its original premise.')
    if correction['status'] == action.upper():
        return store.get_evidence_item(workspace, correction['review_action_id'])
    return _store_review(store, workspace, source_id, REVIEW_ACTION,
        dict(correction_id=correction_id, machine_evidence_id=machine['id'], action=action,
             anchor=correction['anchor'], reason='Explicit human transcription review; downstream re-evaluation remains separate.'),
        actor, machine.get('region_id'))


def review_source_bytes(store, workspace, source_id, *, allowed_root=None):
    source = next((s for s in workspace.sources if s['id'] == source_id and not s.get('removed_at')), None)
    if not source or not source.get('file_path'):
        raise ValueError('Original source file is unavailable.')
    path = Path(source['file_path']).resolve()
    try:
        path.relative_to(Path(allowed_root or store.store_path).resolve())
    except ValueError:
        raise ValueError('Source path is outside its governed storage boundary.') from None
    raw = path.read_bytes()
    if source.get('file_hash') and hashlib.sha256(raw).hexdigest() != source['file_hash']:
        raise ValueError('Source bytes no longer match the recorded hash.')
    return source, raw, path.name


@observed
def create_document_frame(store, workspace, source_id, corners, aspect, rotation, reason, actor, *, allowed_root=None):
    from services.image_intake import rectify_document_preview
    if not reason.strip():
        raise ValueError('Record why these four corners identify the document frame.')
    source, raw, filename = review_source_bytes(store, workspace, source_id, allowed_root=allowed_root)
    signature = dict(corners=corners, aspect=aspect, rotation=rotation, reason=reason,
                     source_sha256=hashlib.sha256(raw).hexdigest())
    frames = _review_records(workspace, source_id, DOCUMENT_FRAME)
    if frames and frames[-1].get('input') == signature:
        return store.get_evidence_item(workspace, frames[-1]['id'])
    preview, frame = rectify_document_preview(raw, filename, corners, aspect_ratio=aspect, rotation=rotation)
    directory = Path(store.store_path) / 'workspace_sources' / workspace.project_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (uuid.uuid4().hex + '_document_preview.png')
    path.write_bytes(preview)
    derived = store.add_source(workspace, name='Qualified rectified document preview', file_path=str(path),
        kind='drawing', file_hash=hashlib.sha256(preview).hexdigest(), origin_type='derived_reference',
        origin_reference=source_id, actor=actor)
    frame.update(input=signature, source_id=source_id, derived_source_id=derived['id'],
        source_sha256=signature['source_sha256'], reason=reason,
        parent_source_id=source_id, parent_view_id=None, transform_type='PERSPECTIVE_RECTIFICATION',
        origin='EVALUATION_INPUT' if source.get('evaluation_only') else 'USER_REQUESTED',
        coordinate_space_before='NORMALIZED_EXIF_DISPLAY', coordinate_space_after='DOCUMENT_PREVIEW',
        provenance={'source_id': source_id, 'source_sha256': signature['source_sha256']},
        evaluation_only=bool(source.get('evaluation_only')))
    return _store_review(store, workspace, source_id, DOCUMENT_FRAME, frame, actor)


def _apply_reviewed_fields(workspace, source_id, store):
    from services.visual_examination import VISUAL_CONTENT_TYPE
    visual = visual_reading(workspace, source_id, store=store, use_review=False)
    texts = {}
    accepted = [c for c in source_review_state(workspace, source_id)['corrections'] if c['status'] == 'ACCEPT']
    slots = {}
    for correction in accepted:
        slot = (correction['machine_evidence_id'], correction['field_path'])
        if slot in slots and slots[slot]['after'] != correction['after']:
            raise ValueError('Conflicting accepted corrections; revert one before re-evaluation.')
        slots[slot] = correction
    for correction in slots.values():
        machine = next((e for e in workspace.evidence_items if e['id'] == correction['machine_evidence_id']), None)
        if not machine or hashlib.sha256(machine['content'].encode()).hexdigest() != correction['machine_hash']:
            raise ValueError('Correction premise changed; re-review is required.')
        if correction['field_path'] == 'content':
            texts[machine['id']] = correction['after']
        elif visual and machine['id'] == visual.get('evidence_item_id'):
            parts = correction['field_path'].split('/')
            target = visual
            for part in parts[:-1]:
                target = target[int(part)] if isinstance(target, list) else target[part]
            target[parts[-1]] = correction['after']
            # Reading alone cannot upgrade the old effective binding ceiling.
            from services.binding import bound_certainty, weaker
            ceiling = bound_certainty(target)
            target['read_certainty'] = 'RECOVERED'
            target['certainty'] = weaker('RECOVERED', ceiling)
            target['correction_evidence_id'] = correction['id']
        else:
            raise ValueError('The accepted correction targets a superseded machine reading; re-review the current anchored reading.')
    return visual, texts, [c['id'] for c in accepted]


def frame_qualification(workspace, source_id):
    source = next((s for s in getattr(workspace, 'sources', []) or [] if s['id'] == source_id), {})
    from services.image_intake import is_supported_image
    if not is_supported_image(source.get('file_path') or source.get('name') or ''):
        return None
    frames = _review_records(workspace, source_id, DOCUMENT_FRAME)
    frame = frames[-1] if frames else None
    return dict(state='QUALIFIED' if frame else 'UNRESOLVED', frame_evidence_id=(frame or {}).get('id'),
        capture_frame='EXIF_DISPLAY', document_frame='PROJECTIVE_PREVIEW' if frame else 'UNRECTIFIED',
        sheet_reading_orientation=(frame or {}).get('sheet_reading_rotation', 'UNRESOLVED'),
        geometry_level='PROJECTIVE', angles='UNRESOLVED', metric_scale='NOT_ESTABLISHED',
        reason='Image positions are not survey angles. A display rectangle does not establish a Euclidean or metric frame.')


@observed
def reevaluate_source_review(store, workspace, source_id, actor):
    """Explicit deterministic consumption of reviewed premises; never OCR/LLM."""
    from services import survey_reference as sr, survey_north
    visual, texts, corrections = _apply_reviewed_fields(workspace, source_id, store)
    signature = _review_signature(workspace, source_id)
    current = source_review_state(workspace, source_id)['result']
    if current and current.get('premise_signature') == signature:
        return store.get_evidence_item(workspace, current['id'])
    frame = frame_qualification(workspace, source_id)
    if visual and frame:
        visual.setdefault('graph', {})['frame_qualification'] = frame
    recovered, partial, unresolved = _visual_lines(visual)
    reference = _decoded_record(workspace, source_id, sr.REFERENCE_CONTENT_TYPE)
    source = next(s for s in workspace.sources if s['id'] == source_id)
    if visual:
        reference = reference or dict(source_filename=source.get('name',''), source_sha256=source.get('file_hash',''))
        previous_derived_id = reference.get('derived_source_id')
        from types import SimpleNamespace
        reference = sr.derive(SimpleNamespace(**dict(visual, geometry=visual.get('geometry') or {})),
            project_id=workspace.project_id, source_id=source_id,
            source_filename=reference.get('source_filename',''), source_sha256=reference.get('source_sha256',''),
            pages_used=reference.get('pages_used'), frame_size=reference.get('frame_size'),
            display_name=reference.get('display_name'))
        reference['unresolved'] = list(dict.fromkeys(reference['unresolved'] + unresolved))
        reference['source_note'] = 'Reconstructed from retained source positions; not an angle-faithful or legal survey.'
        reference['authority_note'] = ('EVALUATION_INPUT. No canonical authority. ' if source.get('evaluation_only') else '') + 'QUALIFIED DISPLAY. Observed image positions, calculated constraints and unresolved placeholders are not legal survey authority.'
        directory = Path(store.store_path) / 'workspace_sources' / workspace.project_id
        directory.mkdir(parents=True, exist_ok=True)
        pdf = sr.render_pdf(reference)
        path = directory / (uuid.uuid4().hex + '_reviewed_survey_reference.pdf')
        path.write_bytes(pdf)
        derived = store.add_source(workspace, name='Reviewed Survey Reference', file_path=str(path),
            kind='drawing', file_hash=hashlib.sha256(pdf).hexdigest(), origin_type='derived_reference',
            origin_reference=source_id, actor=actor)
        reference['derived_source_id'] = derived['id']
        reference['artifact_sha256'] = hashlib.sha256(pdf).hexdigest()
        reference['artifact_filename'] = path.name
        reference['review_consumer_svg'] = sr.review_svg(reference)
        reference['review_consumer_stats'] = sr.resolved_plan(reference)['stats']
        reference['review_correction_ids'] = corrections
        reference.pop('evidence_item_id', None)
        from services.case_workspace import EVIDENCE_CLASS_AI_GENERATED_PROPOSAL
        reference_record = store.register_evidence_item(workspace, source_id,
            EVIDENCE_CLASS_AI_GENERATED_PROPOSAL, json.dumps(reference, allow_nan=False),
            sr.REFERENCE_CONTENT_TYPE, actor=actor)
        reference['evidence_item_id'] = reference_record['id']
        # Same derivative revision convention as visual_classification. Historical
        # downloads remain retained; the normal reference owner selects this one.
        old = next((s for s in workspace.sources if s['id'] == previous_derived_id), None)
        new = next(s for s in workspace.sources if s['id'] == derived['id'])
        if old:
            old['superseded_by_source_id'] = derived['id']
            new['supersedes_source_id'] = old['id']
            store.save(workspace)
    rows = survey_north.orientation_propositions(visual or {}, frame)
    groups = unresolved_by_stage(unresolved, source_id=source_id,
        evidence_id=(visual or {}).get('evidence_item_id'), orientation=rows, frame=frame)
    payload = dict(premise_signature=_review_signature(workspace, source_id), visual=visual, text_overrides=texts,
        correction_ids=corrections, frame=frame, orientation=rows, unresolved_groups=groups,
        recovered=recovered, partially_recovered=partial, unresolved=unresolved,
        reference=reference, reference_svg=reference.get('review_consumer_svg', '') if reference else '',
        qualification='Reviewed transcription is not binding, authority, applicability, precedence or currentness.',
        state='PARTIAL' if unresolved or frame else 'RECORDED')
    return _store_review(store, workspace, source_id, REVIEW_RESULT, payload, actor)


def unresolved_by_stage(items, *, source_id, evidence_id=None, orientation=(), frame=None):
    """Presentation grouping of owned refusal text; no state is recomputed."""
    stages = ['Document frame','Sheet identity','Orientation/North','Building front/frontage',
              'Parcel/geometry','Measurements','Measurement genealogy','Authority/currentness','Access','Structure containment']
    groups = {s:[] for s in stages}
    rules = [('Structure containment', ('containment','footprint')), ('Measurement genealogy', ('genealogy','current_value','historical')),
        ('Building front/frontage', ('frontage','building front','entrance')), ('Orientation/North', ('north','direction','bearing reference')),
        ('Document frame', ('frame','rectif','distort')), ('Sheet identity', ('title','sheet','plan number','surveyor','date')),
        ('Authority/currentness', ('authority','datum','currentness','applicab')), ('Access', ('access','street')),
        ('Measurements', ('dimension','measurement','bearing','radius','length'))]
    next_steps = {'Document frame':'Identify document corners and reading orientation; obtain independent frame/scale evidence for angular or metric use.',
        'Sheet identity':'Review the anchored title block and supply a legible source region.',
        'Orientation/North':'Supply an applicable north reference and independently justified angular frame.',
        'Building front/frontage':'Review entry evidence separately from functional designation and applicable municipal front-lot-line rules.',
        'Parcel/geometry':'Supply bound boundary observations and the missing geometric premises.',
        'Measurements':'Review the exact annotation and its object binding separately.',
        'Measurement genealogy':'Review competing readings, explicit supersession and precedence evidence.',
        'Authority/currentness':'Supply the governing authority, applicability and revision evidence.',
        'Access':'Review the street, entry and access relationship at their source regions.',
        'Structure containment':'Supply a traceable footprint and a qualified parcel boundary in the same frame.'}
    missing = {'Document frame':'Document-plane controls, flatness and independent angular/metric calibration.',
        'Sheet identity':'An unambiguous legible field bound to this sheet/view.',
        'Orientation/North':'An applicable North reference in an independently established angular frame.',
        'Building front/frontage':'Independent entry/use designation or applicable municipal front-lot-line rule and parcel context.',
        'Parcel/geometry':'The missing bound boundary / closure / curve / common-frame premise described in the finding.',
        'Measurements':'A legible value, its units and a justified binding to the measured object.',
        'Measurement genealogy':'Evidence of precedence and applicability between the competing measurements.',
        'Authority/currentness':'Established authority, applicability and explicit revision/currentness evidence.',
        'Access':'Reviewed entry, street and building/parcel relationships.',
        'Structure containment':'Qualified footprint and parcel boundary with traceable identity in a common frame.'}
    findings = [(next((s for s,words in rules if any(word in str(item).lower() for word in words)), 'Parcel/geometry'), str(item),
        'REFUSED' if 'REFUSED' in str(item) else 'UNRESOLVED') for item in items]
    if frame:
        findings.append(('Document frame', frame['reason'], frame['state']))
    for row in orientation:
        if row['state'] in ('UNRESOLVED','CANDIDATE','QUALIFIED'):
            findings.append(('Building front/frontage' if 'front' in row['proposition'].lower() or 'entrance' in row['proposition'].lower() else 'Orientation/North', row['reason'], row['state']))
    for stage, reason, state in findings:
        groups[stage].append(dict(state=state, reason=reason,
            evidence_available=[v for v in (source_id,evidence_id) if v],
            missing_premise=missing[stage], next_step=next_steps[stage]))
    return [dict(stage=s, items=groups[s]) for s in stages]


@observed
def inspect_source_review(workspace, source_id):
    """Read persisted review/consumer records. No producer runs on Reload."""
    source = next((s for s in workspace.sources if s['id'] == source_id and not s.get('removed_at')), None)
    if not source:
        raise ValueError('Source unavailable.')
    review = source_review_state(workspace, source_id)
    result = review['result'] or {}
    return dict(source=source, review=review, fields=review_text_fields(workspace, source_id),
        result=result, project_id=workspace.project_id,
        frame=frame_qualification(workspace, source_id),
        working_views=[view for view in workspace.derived_views
                       if view.get('source_id') == source_id and view.get('view_transform')])


@observed
def create_working_view(store, workspace, source_id, action, reason, actor, *, parent_view_id=None, allowed_root=None, parameters=None):
    """Existing DerivedView owns lineage; image_intake samples immutable bytes."""
    from services.image_intake import transform_document_preview
    from services.capability_registry import VIEW_ACTIONS
    if action not in VIEW_ACTIONS or not isinstance(reason, str) or not reason.strip():
        raise ValueError('Select a supported view action and record its justification.')
    source, raw, filename = review_source_bytes(store, workspace, source_id, allowed_root=allowed_root)
    original_hash = hashlib.sha256(raw).hexdigest()
    parent = None
    north_premise = None
    if action == 'ALIGN_NORTH_UP':
        if parent_view_id or parameters:
            raise ValueError('North-up requires the original governed frame; transformed-parent alignment is not established.')
        from services.survey_north import resolve_true_north
        visual = visual_reading(workspace, source_id, store=store)
        north_premise = resolve_true_north((visual or {}).get('graph') or {})
        if north_premise['state'] != 'ESTABLISHED':
            raise ValueError('North-up is unresolved: ' + north_premise['reason'])
        north_premise = dict(north_premise, visual_evidence_id=visual.get('evidence_item_id'))
    if parent_view_id:
        parent = next((v for v in workspace.derived_views
                       if v['id'] == parent_view_id and v['source_id'] == source_id), None)
        if not parent or not parent.get('view_transform'):
            raise ValueError('Parent working view is unavailable for this source.')
        if parent['view_transform'].get('source_sha256') != original_hash:
            raise ValueError('The parent view no longer matches the immutable original source.')
        raw, filename = working_view_bytes(store, workspace, parent)
    rendering = None
    if not parent and raw.startswith(b'%PDF-'):
        import pymupdf
        from services.visual_classification import _pdf_page_raster
        with pymupdf.open(stream=raw, filetype='pdf') as pdf:
            if len(pdf) != 1:
                raise ValueError('Select an explicit page before transforming a multi-page document.')
            if north_premise and (pdf[0].get_images(full=True) or not pdf[0].get_drawings()):
                raise ValueError('North-up frame is unresolved: an embedded raster is not an established angular document frame.')
        rendered = _pdf_page_raster(raw, 1)
        if not rendered:
            raise ValueError('The source page could not be rendered within existing bounds.')
        rendering = dict(source_sha256=original_hash, page_number=1,
                         raster_sha256=hashlib.sha256(rendered).hexdigest(), owner='visual_classification._pdf_page_raster',
                         angular_frame='NATIVE_VECTOR_PAGE' if north_premise else 'UNRESOLVED')
        raw, filename = rendered, 'retained-page.png'
    if north_premise:
        from services import survey_north
        north_premise['source_rechecks'] = []
        established_ids = {p['candidate_id'] for p in north_premise['premises'] if p['state'] == 'ESTABLISHED'}
        for candidate in (visual.get('graph') or {}).get('north_candidates', []):
            if candidate.get('id') not in established_ids:
                continue
            measured = survey_north.measure_north(raw, candidate.get('bbox') or candidate.get('source_region'))
            if (not measured['ok'] or survey_north.angular_delta(measured['degrees'], candidate['measured_degrees'])
                    > survey_north.CORROBORATION_DELTA_DEGREES):
                raise ValueError('North-up is unresolved: the retained source does not corroborate the recorded arrow measurement.')
            north_premise['source_rechecks'].append(dict(candidate_id=candidate['id'], source_sha256=original_hash,
                rendered_sha256=hashlib.sha256(raw).hexdigest(), measurement=measured))
        if not north_premise['source_rechecks']:
            raise ValueError('North-up is unresolved: no source-bound directional measurement is available.')
    preview, transform = transform_document_preview(raw, filename,
        'ROTATE_ANGLE' if north_premise else action,
        {'clockwise_degrees': -north_premise['degrees']} if north_premise else parameters)
    if north_premise:
        transform.update(type='ALIGN_NORTH_UP', north_premise=north_premise,
            qualification='True-north-up display uses the retained directional premises. No metric, legal or survey authority is added.')
    if rendering:
        transform.update(rendering=rendering, coordinate_space_before='NORMALIZED_PDF_PAGE_RENDER')
    pages = [p for p in workspace.structural_units if p['source_id'] == source_id
             and p.get('unit_type') in ('page', 'sheet', 'image')
             and (not rendering or p.get('order_index') == 0)]
    if not pages:
        # Verified raster is one image; this records its address, not sheet identity.
        pages = [store.create_structural_unit(workspace, source_id, 'page' if rendering else 'image', 0,
                                              label='Retained source page 1' if rendering else 'Retained source image', actor=actor)]
    page_id = parent['page_structural_unit_id'] if parent else pages[0]['id']
    directory = Path(store.store_path) / 'workspace_sources' / workspace.project_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (uuid.uuid4().hex + '_working_view.png')
    path.write_bytes(preview)
    transform.update(parent_source_id=source_id, parent_view_id=parent_view_id,
        source_sha256=original_hash, parent_sha256=hashlib.sha256(raw).hexdigest(),
        output_sha256=hashlib.sha256(preview).hexdigest(), file_path=str(path),
        origin='EVALUATION_INPUT' if source.get('evaluation_only') else 'USER_REQUESTED',
        reason=reason.strip(), evaluation_only=bool(source.get('evaluation_only')),
        provenance={'source_id': source_id, 'parent_view_id': parent_view_id})
    return store.create_derived_view(workspace, source_id, page_id,
        region={'x': 0, 'y': 0, 'width': 1, 'height': 1},
        derivation_reason=reason.strip(), actor=actor, view_transform=transform)


@observed
def working_view_bytes(store, workspace, view):
    """Read a committed, project-owned artifact; GET never regenerates it."""
    transform = view.get('view_transform') or {}
    path = Path(transform.get('file_path') or '').resolve()
    root = (Path(store.store_path) / 'workspace_sources' / workspace.project_id).resolve()
    if view.get('project_id') != workspace.project_id or not path.is_relative_to(root):
        raise ValueError('Working view is outside this project.')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != transform.get('output_sha256'):
        raise ValueError('Working view bytes no longer match their committed provenance.')
    return raw, path.name


def apply_source_review_action(store, workspace, source_id, form, actor, *, allowed_root=None):
    action = form.get('action')
    if action == 'view_transform':
        from services.capability_registry import VIEW_ACTIONS, resolve_view_action
        typed = form.get('view_action')
        if form.get('view_instruction', '').strip():
            typed = resolve_view_action(form['view_instruction'])
        if typed not in VIEW_ACTIONS:
            raise ValueError('View action is unresolved. Select an explicit transform; opposite side, alignment and north-up require additional premises.')
        return create_working_view(store, workspace, source_id, typed, form.get('reason', ''), actor,
                                   parent_view_id=form.get('parent_view_id') or None, allowed_root=allowed_root,
                                   parameters=json.loads(form.get('parameters') or '{}'))
    if action == 'propose':
        return propose_text_correction(store, workspace, source_id, form.get('field',''),
            form.get('after',''), form.get('reason',''), actor)
    if action in ('accept','revert'):
        return review_text_correction(store, workspace, source_id, form.get('correction_id'), action, actor)
    if action == 'rectify':
        return create_document_frame(store, workspace, source_id, json.loads(form.get('corners','[]')),
            float(form.get('aspect','1.414214')), int(form.get('rotation','0')), form.get('reason',''), actor,
            allowed_root=allowed_root)
    if action == 'reevaluate':
        return reevaluate_source_review(store, workspace, source_id, actor)
    raise ValueError('Unknown source review action.')

# What a person is told about their job, and the only three outcomes a stored
# record can support. Ordered worst-last so a listing can sort by concern.
STATE_RESULT_READY = "result_ready"
STATE_READ_NOT_INTERPRETED = "read_not_interpreted"
STATE_NEEDS_ATTENTION = "needs_attention"
STATE_COULD_NOT_COMPLETE = "could_not_complete"

# CLAUDE-GO-PERCEPTION-WORKER-01: two states that only became TRUE when the
# work actually moved off the request.
#
# This module previously refused to render "Processing", and that refusal was
# right: examination ran inside the upload request, so by the time any record
# existed it had finished, and a pending state would have been a status no
# record could support. Asynchronous perception creates the record that makes
# it true. The rule did not change - the facts did.
STATE_QUEUED = "queued"
STATE_PROCESSING = "processing"

STATE_LABELS = {
    STATE_QUEUED: "Waiting to be examined",
    STATE_PROCESSING: "Being examined",
    STATE_RESULT_READY: "Result ready",
    STATE_READ_NOT_INTERPRETED: "Read, not interpreted",
    STATE_NEEDS_ATTENTION: "Needs attention",
    STATE_COULD_NOT_COMPLETE: "Could not complete",
}

# CLAUDE-EXAMINATION-ACTIVITY-01: what the person is told WHILE it runs.
#
# `STATE_LABELS` answers "what is the outcome", and while an examination is in
# flight there is no outcome yet - so a page showing only those two pending
# labels tells someone waiting almost nothing, and tells them the same thing
# for a minute whatever is happening underneath.
#
# These are finer, and each one is a fact a stored job record can actually
# establish. THEY NAME THE WORK, NEVER THE MACHINERY: no worker, no queue, no
# job id, no processing version, no model. "Examining document" is true and
# useful; "orientation-ocr@1 claimed by vps-a12692b3:905538" is neither.
ACTIVITY_QUEUED = "Waiting to be examined"
ACTIVITY_READING = "Examining document…"
ACTIVITY_LOOKING = "Visual analysis in progress…"

# Ordered worst-last: an aggregate takes the LEAST settled state among its
# sources, so an examination never looks finished while part of it is not.
_AGGREGATE_PRECEDENCE = (
    STATE_COULD_NOT_COMPLETE,
    STATE_QUEUED,
    STATE_PROCESSING,
    STATE_NEEDS_ATTENTION,
    STATE_READ_NOT_INTERPRETED,
    STATE_RESULT_READY,
)

# Plain-language equivalents. The key is the file's own extension, so nothing
# here claims to know what the document IS - only what kind of file arrived.
_MATERIAL_BY_EXT = {
    ".pdf": "a PDF document",
    ".docx": "a Word document",
    ".txt": "a plain text file",
    ".md": "a text document",
    ".csv": "a comma-separated data file",
    ".png": "an image (PNG)",
    ".jpg": "an image (JPEG)",
    ".jpeg": "an image (JPEG)",
}

_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


def _ext(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def _stored_filename(source: dict) -> str:
    """The name of the file actually on disk, for questions about its FORMAT.

    CLAUDE-DOCUMENT-UPLOAD-01. `ingestion` stores bytes as
    `<uuid4hex>_<secure_filename>`, so the real extension is always on
    `file_path` - which is the field provenance and evidence identity hang off,
    and the one that never changes. `Source.name` is a display label and now
    legitimately carries a work-item name with no extension at all.

    Falls back to the display name so a record written before bytes were stored
    (an external-connector source has `file_path is None` by design) behaves
    exactly as it did before.
    """
    return source.get("file_path") or source.get("name") or ""


def _live_sources(workspace) -> list[dict]:
    """The sources the PERSON sent, which is not every Source on the record.

    CLAUDE-SURVEY-REFERENCE-01: a Survey Reference is stored as a Source, so
    that save, reopen, download and provenance are what a Source already does
    rather than a second storage mechanism. It is not a thing anybody uploaded,
    so it must not appear in "What you sent", must not be counted in
    "Processing 2 of 5", and must not drag the aggregate state - an artifact
    this application composed cannot be evidence about how the examination is
    going.
    """
    from services.case_workspace import GENERATED_SOURCE_ORIGIN_TYPES

    return [s for s in (getattr(workspace, "sources", None) or [])
            if not s.get("removed_at")
            and s.get("origin_type") not in GENERATED_SOURCE_ORIGIN_TYPES]


def _page_units(workspace, source_id: str) -> list[dict]:
    return [u for u in (getattr(workspace, "structural_units", None) or [])
            if u.get("source_id") == source_id and u.get("unit_type") == "page"]


def _regions_for(workspace, unit_ids: set) -> dict:
    """The addressing records for this source's pages, keyed by id.

    A region carries WHERE something is (`region_type`, `address` with
    page_index/paragraph_index) and nothing about what it says. That division
    is the storage model, and this reader follows it rather than asking a
    region for content it was never given.
    """
    return {r["id"]: r for r in (getattr(workspace, "addressable_regions", None) or [])
            if r.get("structural_unit_id") in unit_ids}


def _recovered(workspace, source_id: str) -> dict:
    """Text held against this Source, and HOW it got there.

    CLAUDE-DOCUMENT-SHOP-OCR-READER-01. This function previously read
    `content` / `content_type` / `evidence_class` off `addressable_regions`,
    where none of those fields exist. The storage model, confirmed against real
    production records rather than inferred from a function's parameter names:

        Source
          -> StructuralUnit   (unit_type="page", source_id)      WHICH PAGE
          -> AddressableRegion(structural_unit_id, address)       WHERE ON IT
          -> EvidenceItem     (source_id, region_id, content,     WHAT IT SAYS
                               content_type, evidence_class,
                               extractor_version)

    The consequence of reading the wrong record was not a blank section: a
    successfully OCR-read image was told "No text could be read from this
    image" while its text sat in evidence_items, and its state read Needs
    attention. A customer-facing contradiction of the system's own evidence.

    Scoped three ways, deliberately, because this text is customer material:
    only this workspace (we are handed one), only evidence whose own
    `source_id` matches, and only evidence anchored to a region belonging to a
    page unit OF that source. `source_id` alone would be enough today; the
    region join means a future record that carries a stale or absent source_id
    still cannot cross a source boundary.
    """
    from services.case_workspace import (
        EVIDENCE_CLASS_DIRECT_SOURCE, EVIDENCE_CLASS_EXTRACTED,
    )

    units = _page_units(workspace, source_id)
    regions = _regions_for(workspace, {u["id"] for u in units})
    items = [
        e for e in (getattr(workspace, "evidence_items", None) or [])
        if e.get("source_id") == source_id
        and e.get("content_type") == "text"
        and (e.get("content") or "").strip()
        and e.get("region_id") in regions
    ]

    def _address(item):
        addr = (regions[item["region_id"]].get("address") or {})
        return (addr.get("page_index") or 0, addr.get("paragraph_index") or 0)

    items.sort(key=_address)
    passages = [e["content"] for e in items]
    review = source_review_state(workspace, source_id)
    if review['result'] and not review['stale']:
        overrides = review['result'].get('text_overrides') or {}
        if overrides:
            # Region text does not silently rewrite the whole-page OCR stream.
            # Consumers see explicitly attributed reviewed readings first.
            passages.insert(0, 'Reviewed anchored transcription (binding and authority unchanged):\n' +
                '\n'.join(f'{identifier}: {value}' for identifier, value in overrides.items()))
    classes = {e.get("evidence_class") for e in items if e.get("evidence_class")}
    engines = {e.get("extractor_version") for e in items if e.get("extractor_version")}
    return {
        "page_count": len(units),
        "passage_count": len(passages),
        "character_count": sum(len(p) for p in passages),
        "preview": "\n\n".join(passages[:3])[:1200],
        # OCR-recovered text is a READING of an image; text a document carries
        # is the document speaking. The evidence class already records which,
        # so this reports it rather than guessing from the engine's name.
        "was_recovered": EVIDENCE_CLASS_EXTRACTED in classes,
        "is_direct_source": EVIDENCE_CLASS_DIRECT_SOURCE in classes,
        "read_by": sorted(e for e in engines if e),
    }


def _decoded_record(workspace, source_id: str, content_type: str):
    """The most recent JSON record of one kind held against this Source.

    Evidence is append-only, so a re-examination adds rather than replaces and
    the LAST one is the current reading. A record that will not parse is
    treated as absent rather than raising: a malformed evidence row must not be
    able to take down the page that reports the examination.
    """
    import json

    rows = [e for e in (getattr(workspace, "evidence_items", None) or [])
            if e.get("source_id") == source_id
            and e.get("content_type") == content_type]
    for row in reversed(rows):
        try:
            decoded = json.loads(row.get("content") or "")
        except (TypeError, ValueError):
            continue
        if isinstance(decoded, dict):
            decoded["evidence_item_id"] = row.get("id")
            return decoded
    return None


def visual_reading(workspace, source_id: str, *, store=None, use_review=True):
    """What GO SAW in this source, or None. The visual counterpart to
    `_recovered`, and read the same way: off the record, never recomputed."""
    from services import visual_examination as vx

    visual = _decoded_record(workspace, source_id, vx.VISUAL_CONTENT_TYPE)
    reviewed = source_review_state(workspace, source_id)
    if use_review and reviewed['result'] and not reviewed['stale']:
        visual = deepcopy(reviewed['result'].get('visual'))
    frame = frame_qualification(workspace, source_id)
    if visual and frame:
        visual.setdefault('graph', {})['frame_qualification'] = frame
    if visual and store is None and (any(s.get("measurements") for s in (visual.get("graph") or {}).get("segments", []))
            or any((visual.get("graph") or {}).get(key) for key in ("north_candidates","access_occurrences","height_datums"))):
        from flask import current_app
        from services.case_workspace import CaseWorkspaceStore
        store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    if visual and any(s.get("measurements") for s in (visual.get("graph") or {}).get("segments", [])):
        from flask import current_app
        from services.case_workspace import CaseWorkspaceStore
        from services.survey_graph import resolve_measurement_premises
        resolve_measurement_premises(store, workspace, visual)
    if visual and (visual.get("graph") or {}).get("north_candidates"):
        from flask import current_app
        from services.case_workspace import CaseWorkspaceStore
        from services.survey_north import resolve_conversions
        resolve_conversions(store, workspace, visual)
    if visual and (visual.get("graph") or {}).get("access_occurrences"):
        from flask import current_app
        from services.case_workspace import CaseWorkspaceStore
        from services.survey_graph import resolve_access_interpretations
        resolve_access_interpretations(store, workspace, visual)
    if visual and (visual.get("graph") or {}).get("height_datums"):
        from flask import current_app
        from services.case_workspace import CaseWorkspaceStore
        from services.height_datum_governance import resolve_height_datums
        resolve_height_datums(store, workspace, visual)
    return visual


def survey_reference_of(workspace, source_id: str):
    """The Survey Reference derived from this source, or None."""
    from services import survey_reference as sr

    reference = _decoded_record(workspace, source_id, sr.REFERENCE_CONTENT_TYPE)
    reviewed = source_review_state(workspace, source_id)
    if reviewed['stale']:
        return None  # Retained download is history, not a current consumer result.
    if reviewed['result'] and not reviewed['stale']:
        reference = deepcopy(reviewed['result'].get('reference'))
    frame = frame_qualification(workspace, source_id)
    if reference and frame:
        reference.setdefault('graph', {})['frame_qualification'] = frame
        reference['authority_note'] = 'QUALIFIED DISPLAY: source positions are not angle-faithful survey geometry or legal authority.'
    if reference and (reference.get("graph") or {}).get("north_candidates"):
        from flask import current_app
        from services.case_workspace import CaseWorkspaceStore
        from services.survey_north import resolve_conversions
        visual = visual_reading(workspace, source_id)
        if visual:
            resolve_conversions(CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"]), workspace,
                                {"graph": reference["graph"], "evidence_item_id": visual["evidence_item_id"]})
    return reference


def _visual_established_anything(visual) -> bool:
    from services import visual_examination as vx

    return any(o.get("certainty") in vx.VALUE_BEARING
               for o in ((visual or {}).get("observations") or []))


def _visual_lines(visual) -> tuple[list, list, list]:
    """The three short lists a visually-read document is described by.

    Returns (recovered, partially_recovered, unresolved) as plain phrases.
    Values are joined to their labels here rather than in the template, so the
    result page, the Survey Reference sheet and GO all describe one reading in
    one vocabulary.
    """
    from services import visual_examination as vx

    if not visual:
        return [], [], []

    def _phrase(observation):
        return ("%s: %s" % (observation["label"], observation["value"])
                if observation.get("value") else observation["label"])

    observations = visual.get("observations") or []
    directional_unresolved = []
    if visual.get("document_category") == "survey":
        from services import survey_north
        north_resolution = survey_north.resolve_true_north(visual.get("graph") or {})
        admitted = []
        for observation in observations:
            import re
            from services.height_datum_governance import is_height_datum_claim
            if is_height_datum_claim(observation):
                directional_unresolved.append("Regulatory datum UNRESOLVED from recovered text alone; observed %s; use independently established authority/applicability/alignment premises" % _phrase(observation))
                continue
            if observation.get("key") not in ("address", "streets") and re.search(
                    r"\b(?:primary frontage|building front|primary access|main entr(?:y|ance))\b", observation.get("value", ""), re.I):
                directional_unresolved.append("Access interpretation UNRESOLVED from free-form text alone; observed %s [directional reference %s; true North %s]; use scoped reviewed access evidence" % (
                    _phrase(observation), observation.get("directional_reference", "UNRESOLVED"), north_resolution["state"]))
            elif survey_north.directional_observation(observation) and not survey_north.admits_true_direction(observation, north_resolution):
                directional_unresolved.append("Directional conclusion UNRESOLVED; observed %s [reference %s; true North %s]" % (
                    _phrase(observation), observation.get("directional_reference", "UNRESOLVED"), north_resolution["state"]))
            else:
                admitted.append(observation)
        observations = admitted
        if north_resolution["state"] != "ESTABLISHED":
            directional_unresolved.append("True North UNRESOLVED: " + north_resolution["reason"])
    survey = visual.get("document_category") == "survey"
    structures = [o for o in observations if o.get("key") in ("building_footprint", "accessory_structures")]
    if survey:
        observations = [o for o in observations if o not in structures]
    recovered = [_phrase(o) for o in observations
                 if o.get("certainty") == vx.RECOVERED]
    partial = [_phrase(o) for o in observations
               if o.get("certainty") == vx.PARTIALLY_RECOVERED]
    unresolved = list(visual.get("unresolved") or []) + directional_unresolved
    from services import binding

    if survey:
        from services import survey_graph
        graph = visual.get("graph") or {}
        from services.height_datum_governance import height_datum_projection
        for datum in height_datum_projection(graph):
            geometry = datum["street_centerline_geometry"] or {}
            review = datum["review"]
            phrase = "Height datum %s: %s; subject %s; street %s; geometry provenance %s; premises %s; authority evidence %s" % (
                datum["candidate_id"], datum["datum_status"], datum["subject_id"], geometry.get("street_name"), geometry.get("note"),
                "; ".join("%s=%s [evidence %s]" % (axis, p["state"], ",".join(p["evidence_ids"])) for axis, p in review.get("premises", {}).items()),
                ",".join(a["evidence_id"] for a in review.get("authorities", [])))
            (recovered if datum["datum_status"] in ("GOVERNING_DATUM_ESTABLISHED", "GEOMETRY_ONLY") else unresolved).append(phrase)
            for axis in ("street_centerline_geometry", "regulatory_requirement", "applicability", "selected_governing_street", "building_reference_alignment_or_midpoint"):
                value = datum.get(axis) or {}
                partial.append("Datum observation %s / %s: %s; read %s; binding %s; provenance %s" % (
                    datum["candidate_id"], axis, value.get("value"), value.get("read_certainty"), binding.bound_certainty(value), value.get("note")))
        accesses = survey_graph.access_interpretations(graph)
        if not accesses:
            unresolved.append("Primary public access UNRESOLVED: street adjacency does not establish access or building front")
        for access in accesses:
            occurrence = access["occurrence"]
            phrase = "Access %s on edge %s (%s): %s; provenance %s; review evidence %s; access interpretation only, not legal frontage or building-front designation" % (
                occurrence["id"], occurrence["edge_id"], occurrence["street_name"], access["state"], occurrence["provenance"],
                ", ".join((occurrence.get("validated_access") or {}).get("evidence_ids", [])))
            phrase += "; premise " + access["premise_state"]
            for trust in (occurrence.get("validated_access") or {}).get("trust_records", []):
                for edge in trust.get("contradicting_relationships", []):
                    phrase += "; counterevidence relationship %s (%s)" % (edge["relationship_id"], edge["status"])
            (unresolved if access["state"] == "UNRESOLVED" else recovered).append(phrase)
            for name in survey_graph.ACCESS_FEATURES:
                feature = occurrence.get(name) or {}
                if feature.get("value") is not None:
                    partial.append("Access observation %s / %s: %s; read %s; binding %s; provenance %s" % (
                        occurrence["id"], name, feature["value"], feature.get("read_certainty"),
                        binding.bound_certainty(feature), feature.get("note")))
        footprints = graph.get("footprints") or []
        if structures and not footprints:
            unresolved.append("Structure containment UNRESOLVED: no traceable footprint outlines; "
                              + "; ".join(_phrase(o) for o in structures))
        for footprint in footprints:
            containment = survey_graph.footprint_containment(graph, footprint)
            name = footprint.get("label") or footprint.get("id") or "Unidentified structure"
            from services import survey_north
            if survey_north.directional_observation({"key": "structure_label", "value": name}):
                name += " [label as observed; directional reference UNRESOLVED]"
            state = containment["state"]
            provenance = containment["provenance"]
            detail = (" (parcel %s; %s; read %s; binding %s; occurrence %s; boundary %s; source basis: %s)" % (
                containment["subject_identity"], state, containment["read_certainty"],
                containment["bind_certainty"], footprint.get("id"),
                ", ".join(provenance["boundary_segments"]), provenance["identity_basis"] or "unestablished"))
            if state == "INSIDE_SUBJECT_PARCEL":
                recovered.append("Existing building on subject property: " + name + detail)
            elif state == "OUTSIDE_SUBJECT_PARCEL":
                recovered.append("Neighboring context only: " + name + detail)
            else:
                unresolved.append("Structure containment UNRESOLVED: " + name + detail + "; " + containment["reason"])

    # Read the persisted components again; a cached aggregate is not evidence.
    for segment in (visual.get("graph") or {}).get("segments") or []:
        from services import survey_graph
        if segment.get("bearing"):
            bearing = survey_graph._bearing(segment["bearing"])
            partial.append("Printed bearing on %s: %s; parsing %s; reference %s; read %s; binding %s" % (
                segment["id"], segment["bearing"].get("text", ""),
                (bearing or {}).get("parse_state", "UNRESOLVED"),
                (visual.get("graph") or {}).get("bearing_reference", "UNRESOLVED"),
                (bearing or {}).get("read_certainty", "UNRESOLVED"), binding.bound_certainty(bearing)))
        if segment.get("kind") == "arc":
            curve = survey_graph.curve_constraints(segment)
            partial.append("Curve evidence on %s: %s; binding %s; parameters %s" % (
                segment["id"], curve["state"], curve["binding_certainty"],
                "; ".join("%s=%s" % (name, value.get("text") or "UNRESOLVED")
                          for name, value in curve["parameters"].items())))
            unresolved.append("Curve on %s: %s" % (segment["id"], curve["reason"]))
        if segment.get("measurements"):
            from services import survey_graph
            genealogy = survey_graph.measurement_genealogy(segment)
            for measurement in genealogy["history"]:
                partial.append("Measurement premises %s: %s" % (
                    measurement["occurrence_id"], "; ".join(
                        "%s=%s [evidence %s]" % (axis, (measurement.get("validated_premises", {}).get(axis) or {}).get("state", "UNRESOLVED"),
                                                   ", ".join((measurement.get("validated_premises", {}).get(axis) or {}).get("evidence_ids", [])))
                        for axis in survey_graph.MEASUREMENT_PREMISES)))
                partial.append("Measurement evidence %s: %s %s; segment %s; plan %s; date %s; role %s; read %s; binding %s; provenance: %s" % (
                    measurement["occurrence_id"], measurement["text"], measurement["unit"],
                    measurement["segment_id"], measurement["source_plan"], measurement["survey_date"] or "UNRESOLVED",
                    measurement["printed_role"] or "UNRESOLVED", measurement["read_certainty"],
                    binding.bound_certainty(measurement), measurement["provenance"]))
                for premise in measurement.get("validated_premises", {}).values():
                    for trust in premise.get("trust_records", []):
                        for edge in trust.get("contradicting_relationships", []):
                            partial.append("Measurement counterevidence relationship %s (%s); premise %s" % (
                                edge["relationship_id"], edge["status"], premise["state"]))
            current = genealogy["current"]
            if current:
                recovered.append("Current working measurement for %s: %s %s (occurrence %s; authority basis: %s; applicability: %s; precedence: %s)" % (
                    segment["id"], current["text"], current["unit"], current["occurrence_id"],
                    current["authority_basis"], current["applicability_basis"], current["precedence_basis"]))
            else:
                unresolved.append("CURRENT_VALUE = UNRESOLVED for %s: %s" % (segment["id"], genealogy["reason"]))
            if genealogy["discrepancy"]:
                partial.append("Measurement discrepancy for %s: %s; not an established contradiction" % (segment["id"], genealogy["discrepancy"]))
            continue
        dimension = segment.get("dimension") or {}
        if not dimension:
            continue
        target = segment.get("label") or segment.get("id") or "boundary segment"
        certainty = binding.bound_certainty(dimension)
        phrase = "%s: %s (attachment %s; read %s)" % (
            target, dimension.get("text", ""), certainty,
            dimension.get("read_certainty", dimension.get("certainty", "UNRESOLVED")))
        if certainty == vx.RECOVERED:
            recovered.append(phrase)
        elif certainty == vx.PARTIALLY_RECOVERED:
            partial.append(phrase)
        else:
            unresolved.append("Dimension attachment to %s is %s; do not use it as a bound value"
                              % (target, certainty))
    return recovered, partial, unresolved


def _reached_an_interpretation(document) -> bool:
    """Did the examination conclude ANYTHING beyond "here are some characters"?

    Requirements, tables and a completed consistency check are the three things
    that produce a "What GO made of it" line. If none of them happened, nothing
    was interpreted - however many characters came back.
    """
    return bool(getattr(document, "requirements", None)
                or getattr(document, "tables", None)
                or getattr(document, "consistency_checked", False))


def _job_state_for(jobs, workspace_id, source_id):
    """What the PERSISTED job says about this source, or None if there is none.

    Historical containers pre-date the job store entirely; for them there is no
    job and the answer must come from the evidence, exactly as before. A
    missing job is not a pending job.
    """
    if jobs is None:
        return None
    try:
        record = jobs.latest_for_source(workspace_id, source_id)
    except Exception:
        return None
    if record is None:
        return None
    return record.get("state")


def _visual_jobs_beside(jobs):
    """The VISUAL queue that belongs to the same registry as `jobs`.

    CLAUDE-SURVEY-REFERENCE-02. Examination is now TWO stages on two queues -
    OCR on `perception_jobs`, looking on `visual_jobs` - and a page that
    consults only the first reports a finished examination while the second is
    still running. That is what produced the Cassidy window: perception
    completed at 22:10:45, the visual reading at 22:11:13, and in between the
    page asserted conclusions about a reading that had not happened.

    Derived from the store it is handed rather than added as a parameter,
    because every caller already passes the perception store and the two queues
    live in one registry by construction. A caller cannot forget to pass the
    second one, which is exactly the failure this repairs.
    """
    if jobs is None:
        return None
    root = getattr(jobs, "root", None)
    if root is None:
        return None
    try:
        from services import visual_classification

        return visual_classification.visual_store(root.parent)
    except Exception:  # noqa: BLE001 - a missing queue is "no job", not an error
        return None


def examination_stage_states(workspace, source_id, *, jobs=None) -> list:
    """Every examination stage's state for this source, in pipeline order.

    ONE reader for both queues, so "is this source still being examined" has a
    single answer that the state function and the page cannot disagree about.
    """
    workspace_id = getattr(workspace, "project_id", "")
    return [
        _job_state_for(jobs, workspace_id, source_id),
        _job_state_for(_visual_jobs_beside(jobs), workspace_id, source_id),
    ]



def examination_activity(workspace, source_id, *, jobs=None):
    """What is happening to this source RIGHT NOW, or None when nothing is.

    Derived from the same `examination_stage_states` the state function reads,
    so the indicator and the state can never describe different work. Returns
    None the moment both stages are terminal - the caller then shows the
    result, and there is nothing left to animate.
    """
    from services import perception_jobs as pj

    reading, looking = examination_stage_states(workspace, source_id, jobs=jobs)
    open_states = (pj.STATE_QUEUED, pj.STATE_RUNNING)

    if reading == pj.STATE_RUNNING:
        return ACTIVITY_READING
    if reading == pj.STATE_QUEUED:
        return ACTIVITY_QUEUED
    # Reading is terminal (or never existed). If the looking stage is still
    # open, the examination has MOVED ON to it rather than gone back to
    # waiting - which is why this is not simply "queued means queued".
    if looking in open_states:
        return ACTIVITY_LOOKING
    return None


def aggregate_activity(workspace, *, jobs=None):
    """The activity for a whole examination: the EARLIEST stage still open.

    An examination of five photographs is doing the earliest thing any of them
    still needs, because that is what the person is actually waiting for.
    """
    order = [ACTIVITY_QUEUED, ACTIVITY_READING, ACTIVITY_LOOKING]
    seen = [examination_activity(workspace, source["id"], jobs=jobs)
            for source in _live_sources(workspace)]
    for label in order:
        if label in seen:
            return label
    return None


def source_state(document, workspace, source_id, *, jobs=None) -> str:
    """One Source's honest state.

    Job facts outrank evidence facts while a job is open: a source that has not
    been looked at yet must never render as "Read, not interpreted", which
    would be a statement about a reading that has not happened.
    """
    from services import perception_jobs as pj

    # CLAUDE-SURVEY-REFERENCE-02: EVERY stage, not just the first one.
    #
    # Examination is two stages on two queues now. Consulting only perception
    # reported a finished examination while the looking was still queued - the
    # Cassidy window, where the page said "no text could be read" and "no
    # interpretation was reached" twenty-eight seconds before the visual
    # reading named the lot, the plan and both streets.
    #
    # PENDING WINS OVER EVERYTHING, including a failure in the other stage: a
    # source with one stage still running is still being examined, and saying
    # anything else is a claim about work in flight. Queued outranks running
    # for the same reason the aggregate takes the least settled state.
    stages = examination_stage_states(workspace, source_id, jobs=jobs)
    # RUNNING OUTRANKS QUEUED ACROSS STAGES - the opposite of the rule across
    # SOURCES, and the difference is not an inconsistency.
    #
    # `_AGGREGATE_PRECEDENCE` governs several INDEPENDENT sources, where the
    # least settled one is the honest summary: five photographs with two done
    # and three waiting is not "ready". These are SEQUENTIAL STAGES of one
    # source's single examination, and the question a person is asking is "has
    # my document started being looked at". With OCR actively running and the
    # visual stage queued behind it, "Waiting to be examined" would say nothing
    # has begun, which is false and reads as though the upload were stuck.
    #
    # Three pre-existing tests in test_perception_worker_01 assert the user-
    # facing meaning here, and they caught this the first time it was written
    # the other way round.
    if pj.STATE_RUNNING in stages:
        return STATE_PROCESSING
    if pj.STATE_QUEUED in stages:
        return STATE_QUEUED
    # FAILURE IS READ FROM PERCEPTION ONLY, and the asymmetry is deliberate.
    # Pending is a property of EITHER stage - work in flight is work in flight.
    # Failure is not: the visual stage terminates honestly for every file that
    # has no visual representation at all, so letting it force
    # `needs_attention` would put every .txt and .docx in the deployment into a
    # failed-looking state for doing exactly the right thing.
    if stages[0] == pj.STATE_FAILED:
        return STATE_NEEDS_ATTENTION

    # CLAUDE-SURVEY-REFERENCE-01: a VISUAL reading is an interpretation.
    #
    # Checked before the text tests, and that order is the repair. A survey
    # image yields no text and no parsed requirements, so both tests below
    # failed and the source landed on `needs_attention` - "we could not do
    # anything with this" - while a completed visual reading of the same sheet
    # sat in evidence naming the address, the north arrow and the footprint.
    # Whether anything was READ and whether anything was CONCLUDED are
    # different questions, and only the second one decides this state.
    if _visual_established_anything(visual_reading(workspace, source_id)):
        return STATE_RESULT_READY

    recovered = _recovered(workspace, source_id)
    if recovered["passage_count"]:
        return (STATE_RESULT_READY if _reached_an_interpretation(document)
                else STATE_READ_NOT_INTERPRETED)
    if _reached_an_interpretation(document):
        return STATE_RESULT_READY
    return STATE_NEEDS_ATTENTION


def state_of(document, workspace, *, jobs=None) -> str:
    """The job's outcome, derived only from what is actually recorded.

    CLAUDE-DOCUMENT-SHOP-FLOW-01. This used to return "Result ready" the moment
    ANY passage existed. A Product Owner phone photo of a drawing then produced
    a page reading "Result ready - 14,306 characters recovered" beside "No
    interpretation was reached", with pages of OCR noise under a heading that
    said "Some of what was read". Confident gibberish, which is the one thing
    this surface exists not to be.

    The fix is NOT a text-quality score. Measured against real production
    evidence, a word-like-token ratio does not separate noise from signal:
    the pure-noise photo scored 0.434 while a legitimate low-yield scan scored
    0.195 and a clean control 0.636. A threshold there would be invented
    certainty dressed as a measurement.

    So the state is derived from what the records already establish: text came
    back, and nothing was concluded from it.

    IT IS DELIBERATELY NOT CALLED "LIMITED RECOVERY". That was the first
    attempt, and a live proof caught it overclaiming in the opposite direction:
    a clean photograph whose text OCR read perfectly - "FIRE DAMPER SCHEDULE /
    ROOM 101 DETECTOR FD-1" - was labelled Limited recovery and captioned "could
    not be made sense of", which is false. An IMAGE never reaches an
    interpretation at all, because the parser finds no native text in one, so
    that state applies to every image equally and cannot mean the recovery went
    badly.

    "Read, not interpreted" is what actually happened, and it is true of the
    clean photograph and the dense drawing alike. Which of the two a person is
    holding is visible in the recovered text itself, which is shown to them -
    and judging that for them would need the quality score this refuses to
    invent.
    """
    sources = _live_sources(workspace)
    if document is None or not sources:
        return STATE_COULD_NOT_COMPLETE

    # CLAUDE-GO-PERCEPTION-MULTISOURCE-01: an examination holds ONE OR MORE
    # sources, and its state is the LEAST settled among them. Five photographs
    # with two done and three waiting is not "ready" - and one that failed must
    # not erase the four that succeeded, which is why failure is not simply
    # propagated upward either.
    states = [source_state(document, workspace, s["id"], jobs=jobs)
              for s in sources]
    for candidate in _AGGREGATE_PRECEDENCE:
        if candidate in states:
            return candidate
    return STATE_NEEDS_ATTENTION


def _calculated_geometry_lines(workspace, source_id):
    """Project scoped calculation evidence into the existing examination rows.

    Storage is not acceptance. Recompute trust and input-link reviews on every
    read; neither a reviewed link nor a finite number upgrades a refused result.
    Provenance stays on the row for inspection, while conversation's existing
    label/value projection carries only the customer-facing qualification.
    """
    import json
    from flask import current_app
    from services.case_workspace import CaseWorkspaceStore, EVIDENCE_CLASS_CALCULATED_VALUE

    rows = []
    for evidence in getattr(workspace, "evidence_items", []) or []:
        if (evidence.get("source_id") != source_id
                or evidence.get("evidence_class") != EVIDENCE_CLASS_CALCULATED_VALUE
                or evidence.get("content_type") != "application/json"):
            continue
        try:
            record = json.loads(evidence.get("content") or "")
        except (TypeError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        derivation = record.get("derivation") or {}
        if not isinstance(derivation, dict) or derivation.get("operator") not in (
                "numeric_validity@1", "segment_projection@1", "polygon_region@1",
                "semantic_binding@1", "wall_host@1", "vector_usability@1", "bounded_acos@1",
                "homography_point@1", "homography_validation@1", "homography_inverse@1",
                "homography_composition@1", "homography_line@1", "vanishing_direction@1", "horizon_residual@1",
                    "monument_correspondence@1", "occupation_comparison@1", "control_homography@1", "relative_traverse@1"):
            continue
        field = record.get("field")
        label = {"height": "Height", "thickness": "Wall thickness",
                 "projection": "Segment projection", "point": "Point",
                 "endpoint": "Segment endpoint", "polygon": "Polygon",
                 "wall": "Wall placement", "vector": "Direction vector", "domain": "Angle",
                 "transform": "Homography", "inverse": "Inverse transform", "composition": "Composed transform",
                 "line": "Transformed line", "vanishing": "Projective direction", "horizon": "Horizon residual",
                 "correspondence": "Monument correspondence", "occupation_offset": "Occupation offset", "traverse": "Qualified relative traverse"}.get(field)
        if not label:
            continue
        store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
        governed = store.project_geometry_evidence(workspace, evidence["id"])
        usable = governed["state"] in ("FINITE", "ESTABLISHED") and not governed["errors"]
        qualified = governed["state"] in ("PARTIALLY_RECOVERED", "WEAK")
        text = str(governed["value"]) if usable else label + " could not be established."
        if usable and field in ("correspondence", "occupation_offset"):
            text += " Identity/geometric comparison only; legal boundary authority is not established."
        if usable and derivation.get("operator") == "control_homography@1":
            text += " Calculated from identified controls; physical scale is not established."
        if qualified:
            text += (" The calculation remains uncertain." if governed["state"] == "WEAK"
                     else " The evidence is only partially recovered.")
        rows.append(("interpretation" if usable or qualified else "not_established", {
            "label": label,
            "value": text,
            "evidence_item_id": evidence["id"], "object_id": record.get("object_id"),
            "field": field, "state": governed["state"], "errors": governed["errors"],
            "derivation_record": record, "trust": governed["trust"],
        }))
    return rows


@observed
def build_result(document, workspace, *, display_name: str, jobs=None) -> dict[str, Any]:
    """Everything the Document Examination Result page renders.

    Returns plain data, so the template makes no decisions and nothing here
    depends on Flask. The three-way split the record keeps - established from
    the source, GO's reading of it, and what was not established - is built
    here rather than in markup, because it is a claim about evidence.
    """
    from services import source_identity

    sources = _live_sources(workspace)
    source = sources[0] if sources else None
    filename = (source or {}).get("name") or getattr(document, "filename", "") or ""
    # CLAUDE-SURVEY-REFERENCE-01: THE FILE'S TYPE COMES FROM THE FILE.
    #
    # This read `_ext(filename)`, and `filename` is the DISPLAY name - which
    # `document_shop_intake` sets to the work-item name ("226104 1 Castille")
    # after the batch completes, deliberately and correctly. A display name has
    # no suffix, so a JPEG survey reported "Kind of file: a file of type
    # unknown", `is_image` was False so the picture was never shown, and the
    # image branch below was skipped in favour of the "no text layer" sentence
    # the Product Owner reported.
    #
    # `_source_rows` was repaired for exactly this in CLAUDE-DOCUMENT-UPLOAD-01
    # and `build_result` was not - the same condition, in the same file, left
    # live in the second place. That is the carry-through failure this
    # repository's own operating notes describe, and it is why the fix here is
    # the SHARED reader rather than a second copy of the suffix logic.
    identity = source_identity.identify_path(_stored_filename(source or {}))
    ext = identity["extension"] or _ext(filename)
    is_image = source_identity.is_raster_image(identity)
    recovered = _recovered(workspace, source["id"]) if source else {
        "page_count": 0, "passage_count": 0, "character_count": 0,
        "preview": "", "was_recovered": False, "is_direct_source": False,
        "read_by": [],
    }
    visual = visual_reading(workspace, source["id"]) if source else None
    reference = survey_reference_of(workspace, source["id"]) if source else None

    # CLAUDE-SURVEY-REFERENCE-02: THE STATE IS DECIDED BEFORE ANY CONCLUSION
    # IS WRITTEN, because whether the examination has finished governs which
    # conclusions may be written at all.
    #
    # It used to be computed at the END, after `not_established` was already
    # built - so the page assembled "No text could be read" and "No
    # interpretation was reached" and only afterwards discovered it was still
    # queued. `pending` then suppressed the raw-text block and nothing else,
    # which is the half-implemented intent this module's own docstring
    # describes. The Cassidy record showed it: for 49 seconds the page stated
    # three conclusions about a reading that had not happened.
    state = state_of(document, workspace, jobs=jobs)
    pending = state in (STATE_QUEUED, STATE_PROCESSING)


    established: list[dict[str, str]] = []
    interpretation: list[dict[str, str]] = []
    not_established: list[dict[str, str]] = []

    established.append({
        # CLAUDE-DOCUMENT-SHOP-LAYOUT-01: the date, and only the date.
        #
        # This row read "<filename>, received <date>" - two facts under a label
        # that announced neither, so a person scanning for when they uploaded
        # something had to read past the filename to find it. The filename is
        # not lost: it names the Open file action and captions the image.
        "label": "Date",
        "value": (getattr(document, "ingested_at", "") or "")[:10],
    })
    established.append({
        # CLAUDE-DOCUMENT-SHOP-COPY-01: "File type", not "Kind of file".
        # The VALUE and the logic behind it are untouched - this line still
        # answers what the bytes say the file is. "Document" below remains the
        # separate, interpreted classification, and the two stay distinct:
        # "an image (JPEG)" is provenance, "Survey image" is the point.
        "label": "File type",
        # The bytes first, the extension second, and the word "unknown" only
        # when neither says anything at all.
        "value": identity["label"] if identity["media_type"]
        else _MATERIAL_BY_EXT.get(ext, identity["label"]),
    })
    if visual and (visual.get("label") or visual.get("classification")):
        # WHAT THE DOCUMENT IS, as distinct from what the FILE is. "an image
        # (JPEG)" and "Survey image" answer two different questions and a
        # person needs both - the first is provenance, the second is the point.
        established.append({"label": "Document", "value": visual["label"]})
    # CLAUDE-DOCUMENT-SHOP-LAYOUT-02: the checksum row is gone from this
    # surface. THE GUARANTEE IS NOT GONE - `original_file_hash` is still
    # recorded, still verified, and still what the Survey Reference cites as
    # its provenance. It was reassurance written for whoever built the system,
    # printed to someone who wanted to know what their drawing says.

    # CLAUDE-DOCUMENT-SHOP-LAYOUT-02: the passage and character count, and the
    # engine that produced it, are gone from this surface. They measured the
    # EXTRACTION, not the document - "12 passages across 1 page (858
    # characters) - read from the image by Tesseract" tells a person nothing
    # about their survey and a great deal about our pipeline.
    #
    # `recovered` is untouched and still drives everything below, including the
    # honest "nothing has been concluded" line, which is the part of this block
    # that was ever for the customer.
    if recovered["passage_count"]:
        if (not pending and not _reached_an_interpretation(document)
                and not _visual_established_anything(visual)):
            # Said HERE, beside the character count, because the count on its
            # own reads as success. 14,306 characters of nothing is still
            # nothing, and the customer should not have to infer that.
            #
            # CLAUDE-SURVEY-REFERENCE-01 added the second clause, and the real
            # production record is why. The reported Castille survey carries
            # 858 OCR characters AND a visual reading naming the address, the
            # north arrow and the footprint. Without this clause the page would
            # print "Nothing has been concluded" directly beneath a Recovered
            # list - contradicting itself in adjacent sections, which is the
            # same class of defect as the one being repaired.
            not_established.append({
                "label": "Nothing has been concluded from the recovered text",
                "value": (
                    "The text below was read off your file and is shown exactly "
                    "as the engine produced it. Nothing has been worked out from "
                    "it. Photographing a drawing often returns marks and "
                    "fragments as well as words - linework and symbols get read "
                    "as stray characters - so it is shown for you to judge "
                    "rather than summarised for you."
                    if recovered["was_recovered"] else
                    "Text came back, but nothing has been concluded from it."
                ),
            })

    requirements = list(getattr(document, "requirements", None) or [])
    tables = list(getattr(document, "tables", None) or [])
    if requirements:
        interpretation.append({
            "label": "Statements identified",
            "value": "GO picked out %d passage%s that read as obligations or "
                     "requirements. These are GO's reading of the text, not a "
                     "quotation of it." % (len(requirements),
                                           "" if len(requirements) == 1 else "s"),
        })
    if tables:
        interpretation.append({
            "label": "Tables found",
            "value": "%d table%s recognised in the layout." % (
                len(tables), "" if len(tables) == 1 else "s"),
        })

    # CLAUDE-SURVEY-REFERENCE-01: WHAT GO SAW. Slim and factual, in the order
    # the Product Owner's own example gives - recovered, partly recovered,
    # unresolved - and nothing else. No paragraph about how vision works, no
    # explanation of what a certainty state is.
    visual_recovered, visual_partial, visual_unresolved = _visual_lines(visual)
    if source:
        from services.sheet_identity import title_block_readings

        for page in title_block_readings(workspace, source["id"]):
            for key, field in page["fields"].items():
                entry = {"label": "Sheet " + key.replace("_", " "),
                         "value": (str(field["value"]) + " (" + field["certainty"] + ")"
                                   if field["value"] is not None else "UNRESOLVED")}
                (interpretation if field["value"] is not None else not_established).append(entry)
    if visual_recovered:
        interpretation.append({"label": "Recovered",
                               "value": "; ".join(visual_recovered)})
    if visual_partial:
        interpretation.append({"label": "Partially recovered",
                               "value": "; ".join(visual_partial)})

    flags = list(getattr(document, "consistency_flags", None) or [])
    if getattr(document, "consistency_checked", False):
        interpretation.append({
            "label": "Internal consistency",
            "value": ("%d point%s worth a second look." % (
                len(flags), "" if len(flags) == 1 else "s")) if flags
            else "Nothing inconsistent stood out.",
        })
    elif not pending and not visual_recovered and not visual_partial:
        # Said only where there is nothing better to say, and only once the
        # examination has actually finished - "was not checked" is a claim
        # about a completed pass.
        not_established.append({
            "label": "Internal consistency was not checked",
            "value": getattr(document, "consistency_note", None)
            or "This document was not compared against itself for contradictions.",
        })

    if pending:
        # WHILE ANY STAGE IS STILL IN FLIGHT, THE PAGE SAYS ONLY THAT.
        #
        # Product Owner rule, 2026-09-15: no completed-reading conclusion until
        # every required stage is done. Everything below this branch - "No text
        # could be read", "No interpretation was reached", "Nothing was
        # concluded", and even a partial Unresolved list - is a statement about
        # a finished examination. Emitting any of them early is not a cosmetic
        # problem: it tells someone their survey is unreadable while it is
        # being read.
        pass
    elif visual_unresolved:
        # The ONLY not-established line a visually-read document gets, and it
        # names real items rather than describing a missing capability.
        not_established.append({"label": "Unresolved",
                                "value": "; ".join(visual_unresolved)})
    elif visual and not _visual_established_anything(visual):
        not_established.append({
            "label": "Nothing legible was found in this image",
            "value": "GO looked at the picture and could not make out anything "
                     "it would stand behind. Nothing has been guessed.",
        })
    elif not visual:
        # THE OLD BRANCHES, unchanged, for everything that was NOT looked at.
        # They were never wrong about a text document; they were wrong about an
        # image, because an image had no other reading to report.
        if is_image and not recovered["passage_count"]:
            not_established.append({
                "label": "No text could be read from this image",
                "value": "An image carries no text of its own, and the text-recognition "
                         "step did not recover any. The picture itself is kept and can "
                         "be viewed below.",
            })
        elif getattr(document, "text_extraction_status", "") == "no_native_text":
            not_established.append({
                "label": "This file has no text layer",
                "value": "It appears to be a scan or picture rather than a document with "
                         "selectable text, so there was nothing to read directly.",
            })
        elif not recovered["passage_count"] and not requirements:
            not_established.append({
                "label": "Nothing was recovered from this file",
                "value": "The file was received and stored, but no readable content came "
                         "out of it.",
            })

    if not pending and not interpretation and not recovered["passage_count"] and not visual:
        # Only when there is genuinely nothing, which now includes "and nobody
        # looked". A visually-examined source has already said what it found or
        # that it found nothing, and this line would contradict the first and
        # repeat the second.
        not_established.append({
            "label": "No interpretation was reached",
            "value": "There was not enough recovered content for GO to say what this "
                     "document requires or describes.",
        })

    # `state` and `pending` were resolved above, before any conclusion was
    # written; recomputing here would re-read both queues for the same answer.
    # CLAUDE-DOCUMENT-SHOP-FLOW-01: a photograph of a drawing yields marks and
    # fragments, not sentences. When nothing was concluded from them, the page
    # must present them AS fragments - the old heading "Some of what was read"
    # framed pages of OCR noise as a reading, which is what made a working
    # examination read as gibberish.
    #
    # CLAUDE-SURVEY-REFERENCE-01: asked of THE RECOVERED TEXT, not of the
    # aggregate state, and the distinction is load-bearing. Reading it off the
    # state meant a successful VISUAL reading flipped the state to
    # `result_ready` and so re-framed the same 858 characters of OCR noise as
    # "Some of what was read" - reintroducing the exact defect the line above
    # describes. Seeing the north arrow concludes nothing about the characters.
    fragmentary = bool(recovered["passage_count"]) and not _reached_an_interpretation(document)
    # CLAUDE-MUSCLE-F5-01: sheets this package declared and did not deliver.
    #
    # `register_sheet_index` has computed this since CLAUDE-SHEET-IDENTITY-
    # WIRING-01, and `perception_worker` reduces it to a COUNT in a log line.
    # The capability existed and had no door - the fourth time that pattern has
    # appeared here. Each absence is stated and nothing is inferred about what
    # the missing sheet would have shown.
    try:
        from services import sheet_identity

        missing_sheets = [entry for package_source in _live_sources(workspace)
                          for entry in sheet_identity.declared_but_absent(
                              workspace, package_source["id"])] if workspace else []
    except Exception:  # noqa: BLE001 - a manifest check never fails a result
        missing_sheets = []
    for entry in missing_sheets:
        not_established.append({
            "label": "Missing evidence: " + entry["reference_text"],
            "value": entry["statement"],
        })

    if source and not pending:
        for group, entry in _calculated_geometry_lines(workspace, source["id"]):
            (interpretation if group == "interpretation" else not_established).append(entry)

    review = source_review_state(workspace, (source or {}).get('id'))
    if review['pending'] or review['stale']:
        not_established.append(dict(label='Reviewed source requires re-evaluation',
            value='Review premises changed. Accepted corrections have not been consumed by a current result. Retained machine readings are historical; explicitly re-evaluate before relying on affected conclusions.'))
    return {
        "name": display_name,
        "fragmentary": fragmentary,
        "state": state,
        "state_label": STATE_LABELS[state],
        "filename": filename,
        "received_at": getattr(document, "ingested_at", "") or "",
        "source_id": (source or {}).get("id"),
        "is_image": is_image,
        "established": established,
        "interpretation": interpretation,
        "not_established": not_established,
        "unresolved_groups": unresolved_by_stage(visual_unresolved if visual else [],
            source_id=(source or {}).get('id'), evidence_id=(visual or {}).get('evidence_item_id'),
            frame=frame_qualification(workspace, (source or {}).get('id'))),
        "preview_text": recovered["preview"],
        "sources": _source_rows(document, workspace, jobs=jobs),
        # While anything is still queued or running, the page must not present
        # the raw-text block or the "nothing was concluded" grammar: both are
        # statements about a completed reading.
        "pending": pending,
        # CLAUDE-EXAMINATION-ACTIVITY-01: what to animate, and what to say
        # while animating. None once nothing is running.
        "activity": aggregate_activity(workspace, jobs=jobs) if pending else None,
        # CLAUDE-SURVEY-REFERENCE-01: the derived artifact, if one was built.
        # `reference_source_id` is what the download link needs; the rest is
        # what the page says about it, which is deliberately three words.
        "survey_reference": _reference_view(reference,
                                            source_id=(source or {}).get("id")),
        "visual_ran": bool(visual),
    }


def _reference_view(reference, *, source_id=None) -> Optional[dict[str, Any]]:
    """What the result page shows about a Survey Reference: that there is one,
    what it is, and how to open it. Not its contents - those are already the
    Recovered / Partially recovered / Unresolved lines above, and printing them
    twice is how a slim page stops being slim."""
    if not reference:
        return None
    from services import survey_reference as sr

    # CLAUDE-SURVEY-REFERENCE-02: the review drawing, as inline SVG.
    #
    # THE SAME PRIMITIVES THE PDF IS DRAWN FROM. `sr.review_svg` resolves the
    # stored graph through the one resolver the exported sheet uses, so the
    # drawing a person compares against their photograph is the reconstruction
    # itself - not a second rendering that could agree with the PDF today and
    # drift from it tomorrow.
    try:
        if 'review_consumer_svg' in reference:
            svg = reference['review_consumer_svg']
            stats = reference['review_consumer_stats']
        else:
            svg = sr.review_svg(reference)
            stats = sr.resolved_plan(reference)["stats"]
    except Exception:  # noqa: BLE001 - a review drawing is never worth a 500
        svg, stats = "", {}

    # CLAUDE-SURVEY-REFERENCE-REPAIR-01: AN EMPTY FRAME IS NOT A DRAWING.
    #
    # This shipped and reached production, and the Product Owner saw the
    # result: a blank white panel beside their survey photograph. The cause is
    # that `review_svg` is honest and the GUARD WAS NOT. A graph with no nodes
    # and no segments resolves to a valid SVG containing only its own border -
    # 227 bytes on the live record - and the template asked `{% if plan_svg %}`,
    # which a 227-byte string passes. The page then promised a comparison and
    # showed an empty box.
    #
    # The guard now asks what the drawing CONTAINS, not whether a string was
    # produced. Nothing drawn, nothing shown, and `plan_empty` lets the page
    # say why instead of leaving a hole where a promise was.
    drawn = sum(int(stats.get(key) or 0)
                for key in ("straights", "arcs", "footprints"))
    if not drawn:
        svg = ""

    return {
        "title": reference.get("title") or "Survey Reference",
        "source_note": reference.get("source_note") or "",
        "source_id": reference.get("derived_source_id"),
        "filename": reference.get("artifact_filename") or "",
        "sha256": reference.get("artifact_sha256") or "",
        "generated_at": reference.get("generated_at") or "",
        # The side-by-side needs the ORIGINAL's source id too, so the photo can
        # be shown beside the reconstruction at the same size.
        "original_source_id": source_id,
        "plan_svg": svg,
        # True when a Survey Reference exists but nothing could be drawn from
        # it - the honest state the blank panel was hiding.
        "plan_empty": not svg,
        "stats": stats,
        "withheld": [entry["label"] for entry in (reference.get("withheld") or [])],
        "unresolved": list(reference.get("unresolved") or []),
    }


def _source_rows(document, workspace, *, jobs=None) -> list[dict[str, Any]]:
    """One row per Source, in the order the CUSTOMER chose.

    intake_order when the record states one; list position otherwise, which is
    what every container created before that field existed has. Never a
    filename, never a completion time, never a UUID.
    """
    rows = []
    for index, source in enumerate(_live_sources(workspace)):
        recovered = _recovered(workspace, source["id"])
        state = source_state(document, workspace, source["id"], jobs=jobs)
        order = source.get("intake_order")
        rows.append({
            "source_id": source["id"],
            "name": source.get("name") or "",
            "order": index if order is None else order,
            "state": state,
            "state_label": STATE_LABELS[state],
            # CLAUDE-DOCUMENT-UPLOAD-01: the STORED FILE's own name, not the
            # display name. `Source.name` was the filename for every source
            # this row has ever described, so reading a suffix off it worked by
            # coincidence rather than by design - and the coincidence ended the
            # moment a work-item name became the display name. A photo whose
            # display name is "SRPC Drawing Review 2" is still a photo.
            "is_image": _ext(_stored_filename(source)) in _IMAGE_EXTS,
            # CLAUDE-SURVEY-REFERENCE-01: per-source, so a batch where one
            # photo was looked at and one was not says so per row rather than
            # taking the whole examination's word for it.
            "visual_ran": bool(visual_reading(workspace, source["id"])),
            "passage_count": recovered["passage_count"],
            "character_count": recovered["character_count"],
            "read_by": recovered["read_by"],
            "preview": recovered["preview"],
            "pending": state in (STATE_QUEUED, STATE_PROCESSING),
        })
    rows.sort(key=lambda r: r["order"])
    return rows


def summarise_job(document, workspace, *, display_name: str,
                  project_id: str, jobs=None) -> dict[str, Any]:
    """One row in My Documents. Same state function as the result page uses,
    so a listing can never disagree with the page it links to."""
    sources = _live_sources(workspace)
    state = state_of(document, workspace, jobs=jobs)
    first: Optional[dict] = sources[0] if sources else None
    per_source = [source_state(document, workspace, s["id"], jobs=jobs)
                  for s in sources]
    settled = len([x for x in per_source
                   if x not in (STATE_QUEUED, STATE_PROCESSING)])
    return {
        "project_id": project_id,
        "name": display_name,
        "added_at": getattr(document, "ingested_at", "") or "",
        "source_count": len(sources),
        "first_source_id": (first or {}).get("id"),
        "state": state,
        "state_label": STATE_LABELS[state],
        # "Processing 2 of 5" - real counts from real job records, never a
        # progress bar animating over nothing.
        "settled_count": settled,
        "pending_count": len(sources) - settled,
    }


def preserved_analysis_sources(workspace):
    """Original active sources only; generated references are analysis outputs."""
    from services.case_workspace import GENERATED_SOURCE_ORIGIN_TYPES, CaseWorkspaceError
    sources = [s for s in workspace.sources if not s.get('removed_at')
               and s.get('origin_type') not in GENERATED_SOURCE_ORIGIN_TYPES]
    if not sources:
        raise CaseWorkspaceError('No preserved original source is available.')
    for source in sources:
        path = Path(source.get('file_path') or '')
        if not path.is_file() or not source.get('file_hash'):
            raise CaseWorkspaceError('The preserved source or its recorded hash is unavailable.')
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['file_hash']:
            raise CaseWorkspaceError('Source bytes differ from their recorded hash; re-analysis is refused.')
    return sources


@observed
def queue_reanalysis(app, store, workspace, actor, request_id):
    """Explicit new runs through the existing OCR and visual workers."""
    from services.case_workspace import CaseWorkspaceError, CONTAINER_STATE_BLACK_BOX
    from services import perception_jobs, visual_classification, founding_classification, image_intake
    current = store.get(workspace.project_id)
    if not current or current.owner != actor or current.removed_at or current.container_state != CONTAINER_STATE_BLACK_BOX:
        raise CaseWorkspaceError('Only your active disposable analyses can be re-analyzed.')
    sources = preserved_analysis_sources(current)
    queued = []
    for source in sources:
        values = dict(workspace_id=current.project_id, source_id=source['id'], source_sha256=source['file_hash'],
                      source_name=Path(source['file_path']).name, analysis_run_id=request_id)
        if not (values['source_name'].lower().endswith('.pdf') or image_intake.is_supported_image(values['source_name'])):
            reading = founding_classification.enqueue_for_source(founding_classification.founding_store(store.store_path), **values)
            queued.append(dict(source_id=source['id'], reading=reading['job_id']))
            continue
        reading = perception_jobs.PerceptionJobStore(store.store_path).enqueue(**values)
        looking = visual_classification.enqueue_for_source(
            perception_jobs.PerceptionJobStore(store.store_path, subdir='visual_jobs'), **values)
        queued.append(dict(source_id=source['id'], reading=reading['job_id'], looking=looking['job_id']))
    return queued


def comparison_source(workspace):
    """The existing comparator accepts exactly one retained raster per selection."""
    from PIL import Image
    from services.case_workspace import CaseWorkspaceError
    sources = preserved_analysis_sources(workspace)
    if len(sources) != 1:
        raise CaseWorkspaceError('Comparison currently supports two analyses with one original image each.')
    try:
        with Image.open(sources[0]['file_path']) as picture:
            picture.verify()
    except (OSError, ValueError) as exc:
        raise CaseWorkspaceError('Comparison currently supports retained raster images only.') from exc
    return sources[0]


@observed
def compare_document_analyses(workspaces, actor, *, store=None, view_ids=None):
    """Read-only adapter to the governed pixel comparator; no semantic inference."""
    from services.case_workspace import CaseWorkspaceError, CONTAINER_STATE_BLACK_BOX
    from services.region_comparison import compare_region
    if len(workspaces) != 2 or len({w.project_id for w in workspaces}) != 2:
        raise CaseWorkspaceError('Select exactly two compatible analyses.')
    if any(w.owner != actor or w.removed_at or w.container_state != CONTAINER_STATE_BLACK_BOX for w in workspaces):
        raise CaseWorkspaceError('Only your active disposable analyses can be compared.')
    sources = [comparison_source(w) for w in workspaces]
    view_ids = view_ids or [None, None]
    if len(view_ids) != 2:
        raise CaseWorkspaceError('Exactly two view selections are required.')
    views, paths, available = [], [], []
    for workspace, source, view_id in zip(workspaces, sources, view_ids):
        candidates = [v for v in workspace.derived_views if v.get('source_id') == source['id'] and v.get('view_transform')]
        available.append([dict(id=v['id'], label=v['view_transform']['type']) for v in candidates])
        view = next((v for v in candidates if v['id'] == view_id), None) if view_id else None
        if view_id and (not view or not store):
            raise CaseWorkspaceError('Selected view is unavailable for this original source.')
        if view:
            if view['view_transform'].get('source_sha256') != source['file_hash']:
                raise CaseWorkspaceError('Selected view does not match the retained original hash.')
            working_view_bytes(store, workspace, view)
        views.append(view)
        paths.append(Path(view['view_transform']['file_path'] if view else source['file_path']))
    from services.package_muscles import inspect_view_normalization
    normalization = inspect_view_normalization(sources, views)
    state = compare_region(paths[0], paths[1],
                           dict(x=0, y=0, width=1, height=1))
    return dict(state=state, canonical=False, qualification='Pixel comparison only; document alignment and semantic agreement remain unresolved.',
        normalization=normalization, available_views=available, selected_views=view_ids,
        unsupported=['Semantic conflicts', 'Missing requirements', 'Supersession authority'],
        sources=[dict(project_id=w.project_id, source_id=s['id'], name=s['name'],
                      original_filename=Path(s['file_path']).name, sha256=s['file_hash'],
                      origin_type=s.get('origin_type'), origin_reference=s.get('origin_reference'),
                      authority=s.get('authority', 'UNRESOLVED'), currentness=s.get('currentness', 'UNRESOLVED'))
                 for w, s in zip(workspaces, sources)])
