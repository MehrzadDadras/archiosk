"""Slim presentation of retained planning evidence; no retrieval or inference.

The existing full result view remains the audit projection. This view suppresses
only explicit negative background screens; material uncertainty always survives.
"""
import re

HEADERS = ['Fact', 'Value', 'Source', 'Status', 'Action']


def build(view, result):
    sections = []
    suppressed = []
    consumed = set()
    statements = [s for bucket in ('identity','framework','permitted','envelope','mobility')
                  for s in view[bucket]['statements']]
    statements += view['interpretation']['constraints'] + view['interpretation']['opportunities']
    by_topic = {}
    for s in statements:
        by_topic.setdefault(s['topic'], []).append(s)

    def row(fact, value, source='', status='', action=''):
        return [fact, str(value), source, status, action]

    def add(title, rows):
        if rows: sections.append({'title': title, 'rows': rows})

    def source(s):
        return '; '.join(s.get('authority_names') or s.get('authority_refs') or [])

    def take(topic):
        items = by_topic.get(topic, [])
        consumed.update(s['statement_id'] for s in items)
        return items

    identity = view['identity']
    add('Property Identity', [row('Property', identity.get('address') or 'Unresolved'),
        *([row('Municipality', identity['municipality'])] if identity.get('municipality') else [])])
    r = view['retrieval']; attrs = r.get('zoning_attributes') or {}
    framework = []
    zone = by_topic.get('ZONING_DESIGNATION', [])
    if len(zone) == 1 and attrs.get('ZN_STRING') and attrs['ZN_STRING'] in zone[0]['text']:
        take('ZONING_DESIGNATION')
        framework.append(row('Applicable zoning', attrs['ZN_STRING'], source(zone[0]), zone[0]['status']))
    exceptions = list(view['framework']['exceptions'])
    if not exceptions and by_topic.get('SITE_SPECIFIC_EXCEPTION'):
        for feature in r.get('zone_features') or []:
            if feature.get('qualified') and feature.get('exception_identifier') is not None:
                exceptions.append({'exception_id':str(feature['exception_identifier']),
                                   'text_retrieved':feature.get('exception_status') == 'EXCEPTION_TEXT_RETRIEVED'})
    for e in exceptions:
        framework.append(row('Exception', e['exception_id'], e.get('indicated_by',''),
                             'text retrieved' if e.get('text_retrieved') else 'text unresolved',
                             '' if e.get('text_retrieved') else 'Review exception before applying parent-zone standards'))
        if e.get('development_effect'):
            framework.append(row('Exception detail', e['development_effect'], e.get('indicated_by','')))
    # The explicit identifier/status supplements the exception's substantive
    # statements; it must never replace an established exception condition.
    op = by_topic.get('OFFICIAL_PLAN_DESIGNATION', [])
    if len(op) == 1:
        take('OFFICIAL_PLAN_DESIGNATION')
    else:
        op = []
    if op:
        s = op[0]
        framework.append(row('Official Plan — designation', 'Unresolved' if s['status']=='UNRESOLVED' else s['text'],
                             source(s), s['status'], 'Confirm map designation' if s['status']=='UNRESOLVED' else ''))
        authority = next((a for a in view['evidence'] if a.get('authority_id') in s['authority_refs']),{})
        # Do not guess plan/version from today's authority or the address.
        version = authority.get('version_identifier') or authority.get('effective_date')
        if not version:
            match = re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4} Consolidation\b',s['text'])
            version = match.group(0) if match else None
        if version: framework.append(row('Official Plan — plan / year', version, authority.get('citation','')))
    add('Governing Planning Framework', framework)

    # Physical context has a separate presentation slot. No external imagery or
    # public terrain is fetched or admitted by a presentation field.
    add('Site Context', [row('Physical / map context', 'Not supplied', '', 'Unresolved')])
    envelope = []
    exception_open = any(not e.get('text_retrieved') for e in exceptions)
    for layer, topic, fields in (
        ('Zoning Height Overlay','HEIGHT_LIMIT', [('HT_STORIES','Storeys',' max'),('HT_HEIGHT','Height',' m max')]),
        ('Zoning Lot Coverage Overlay','LOT_COVERAGE',[('ZN_COVERAGE','Lot coverage','% max')])):
        candidates = by_topic.get(topic,[])
        overlay = next((o for o in r.get('overlays',[]) if o.get('layer_name')==layer and o.get('present') is True),None)
        if not candidates or not overlay: continue
        s = candidates[0]; values=[]
        if s['status'] == 'UNRESOLVED': continue
        for field,label,unit in fields:
            value=(overlay.get('attributes') or {}).get(field)
            if isinstance(value,(int,float)) and not isinstance(value,bool) and value>=0 and re.search(r'\b'+re.escape(field)+r'\s*=\s*'+re.escape(str(value))+r'(?![\d.])',s['text']):
                display=str(int(value)) if label!='Height' and value==int(value) else str(value)
                values.append(row(label, display+unit, layer+'; '+source(s),
                                  'Provisional — exception text unresolved' if exception_open else s['status']))
        if values:
            consumed.add(s['statement_id']);envelope.extend(values)
    if any(x[0]=='Height' for x in envelope):
        envelope.append(row('Height datum','Unresolved','','Unresolved','Confirm applicable zoning datum'))
    add('Development Envelope',envelope)
    for table in result.get('regulatory_matrices') or []:
        location = table.get('source_location') or {}
        matrix_rows = []
        for item in table.get('normalized_rows') or []:
            values = item.get('values') or {}
            text = '; '.join(role.title()+': '+str(value.get('raw_value',''))
                             for role, value in values.items())
            matrix_rows.append(row(item.get('topic','Matrix row'), text,
                'Working matrix, page '+str(location.get('page','?')),
                item.get('binding_status','UNRESOLVED'),
                'Confirm applicability of source-stated controls'))
        add('Required / Existing / Proposed', matrix_rows)

    remaining = {}
    referenced = {ref for s in statements for ref in (s.get('derived_from') or [])}
    material_open = any(u.get('materiality') == 'MATERIAL' for u in view['unresolved'])
    # Narrow explicit producer pattern: unknown/ambiguous negatives are retained.
    for s in statements:
        if s['statement_id'] in consumed: continue
        text=s['text'] or ''
        if (text.startswith("No polygon of the City's ") and 'applies to the subject parcel.' in text
                and s['status']!='UNRESOLVED' and not material_open
                and s['statement_id'] not in referenced):
            suppressed.append(s['statement_id']);continue
        if s['topic']=='HERITAGE_LISTING' and text.startswith('No individually listed heritage property'):
            remaining.setdefault('Relevant Screening',[]).append(row('Heritage register — 60 m screen',
                'No listed properties returned', "City's Heritage Register",s['status'],'District / designation not established by this screen'))
            continue
        label=(s['topic'] or 'Finding').replace('_',' ').title()
        group='Constraints & Opportunities' if s['kind']=='GO_INTERPRETS' else ('Development Envelope' if s['topic'] in ('DENSITY','HEIGHT_LIMIT','BUILDING_SETBACK','LOT_COVERAGE') else 'Planning Facts')
        remaining.setdefault(group,[]).append(row(label,text,source(s),s['status']))
    for title,rows in remaining.items():add(title,rows)
    for option in view['options']:
        add('Planning-Level Development Options',[row(option.get('label') or option.get('option_id','Option'),
             option.get('summary') or option.get('description',''),'',option.get('posture') or option.get('planning_posture',''),
             '; '.join(option.get('enabling_conditions') or []))])
    unresolved=[]
    for issue in view['unresolved']:
        label=(issue.get('topic') or issue.get('issue_id') or 'Confirmation').replace('_',' ')
        unresolved.append(row(label,'Unresolved','',issue.get('materiality',''),
                              issue.get('required_evidence') or issue.get('question','')))
    add('Unresolved / Municipal Confirmation',unresolved)
    if view.get('conclusion'):
        add('Conclusion', [row('Finding', view['conclusion'], '', view.get('result_status',''))])
    context=result.get('workspace_context') or {}
    if context.get('scenario'):
        add('Scenario / Project Intent',[row('Scenario',context['scenario'],'User supplied','Not authority')])
    return {'sections':sections,'suppressed_statement_ids':suppressed,
            'site_context_slots':['North orientation','Street context','Aerial / map context','Neighbouring built form','Corner-lot / access','Public terrain context','Survey / authoritative project elevation'],
            'workspace_context':context}
