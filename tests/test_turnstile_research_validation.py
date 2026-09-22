"""Bounded source missions validate content without authority promotion."""
import json
from dataclasses import replace
import pytest
from services import external_research as er
from tests.test_airlock_web_research_01 import _FakeOpener
from tests.test_kernel_mapping import project
from copy import deepcopy

OBC=next(s for s in er.REFERENCE_SOURCES if s.key=='obc')
GOOD='<article><h1>Ontario Building Code O. Reg. 163/24</h1><p>1. The code consists of the provisions set out in this regulation.</p></article>'

@pytest.mark.parametrize('body',[
    '<div id="main-container"></div><script>Building Code 163/24 1. '+('substantive '*300)+'</script>',
    '<div id="root"></div>', '<main>Enable JavaScript to continue</main>',
    '<main>Access denied. Log in to continue.</main>',
    '<nav>'+GOOD+'</nav>', '<main>Accept cookies to continue</main>',
    '<h1>Page not found</h1>', '',
])
def test_shell_is_not_evidence(body):
    with pytest.raises(er.ExternalResearchError) as e:
        er.retrieve_reference(OBC,opener=_FakeOpener(body.encode()))
    assert e.value.validation_state==er.RETRIEVED_NON_SUBSTANTIVE_SHELL

def test_ontario_text_is_substantive_not_applicable_authority():
    r=er.retrieve_reference(OBC,opener=_FakeOpener(GOOD.encode()))
    assert r.validation_state==er.RETRIEVED_SUBSTANTIVE_CONTENT
    assert r.applicability=='APPLICABILITY_UNRESOLVED'
    assert r.raw_bytes==GOOD.encode()

@pytest.mark.parametrize('wrapper',['main','form'])
def test_navigation_without_nav_tag_is_not_product_evidence(wrapper):
    body=('<'+wrapper+'><a href="/product">3000CA turnstile</a>'
          '<a href="/fire">Fire control products and manufacturer installation product pages</a></'+wrapper+'>')
    with pytest.raises(er.ExternalResearchError) as error:
        er.retrieve_reference(er.TURNSTILE_SOURCE_MISSIONS[-1],opener=_FakeOpener(body.encode()))
    assert error.value.validation_state==er.RETRIEVED_NON_SUBSTANTIVE_SHELL

def test_missing_requested_article_and_wrong_identity_refused():
    fire=next(s for s in er.TURNSTILE_SOURCE_MISSIONS if s.key=='turnstile-fire-code')
    for content in (GOOD, '<p>Ontario Fire Code 213/07. 1. General interpretation and provisions of this regulation.</p>'):
        payload=json.dumps({'content':content}).encode()
        with pytest.raises(er.ExternalResearchError) as e:
            er.retrieve_reference(fire,opener=_FakeOpener(payload,content_type='application/json'))
        assert e.value.validation_state==er.CONTENT_VALIDATION_UNRESOLVED


def test_regulation_table_of_contents_is_not_a_provision():
    body=b'<main>Ontario Building Code O. Reg. 163/24 Contents Section 1 Section 2 Section 3 Accessibility Egress Fire Safety</main>'
    with pytest.raises(er.ExternalResearchError) as error:
        er.retrieve_reference(OBC,opener=_FakeOpener(body))
    assert error.value.validation_state==er.CONTENT_VALIDATION_UNRESOLVED

def test_foreign_and_product_are_not_ontario_authority():
    assert er.regulatory_applicability(replace(OBC,jurisdiction='UNRESOLVED'),'Ontario, Canada')=='APPLICABILITY_UNRESOLVED'
    assert er.regulatory_applicability(replace(OBC,jurisdiction='USA'),'Ontario, Canada')=='NON_APPLICABLE_JURISDICTION'
    product=er.TURNSTILE_SOURCE_MISSIONS[-1]
    assert er.regulatory_applicability(product,'Ontario, Canada')=='NOT_REGULATORY_AUTHORITY'
    with pytest.raises(er.ExternalResearchError):
        er.retrieve_reference(OBC,opener=_FakeOpener(b'<article>2024 International Building Code. 1. Turnstiles shall meet all of these requirements.</article>'))

def test_precedent_and_arbitrary_routes_remain_unauthorized():
    assert not any('precedent' in s.key for s in er.TURNSTILE_SOURCE_MISSIONS)
    source=replace(OBC,url='https://example.org/turnstile')
    with pytest.raises(er.ExternalResearchError) as e: er.retrieve_reference(source,opener=_FakeOpener())
    assert e.value.validation_state==er.RETRIEVAL_BLOCKED

def test_missions_not_automatically_selected_by_general_question():
    assert not set(er.select_sources('turnstile manufacturer precedent')).intersection(er.TURNSTILE_SOURCE_MISSIONS)


@pytest.mark.parametrize('substantive',[False,True])
def test_real_retention_keeps_eight_children_and_authority_unchanged(project,monkeypatch,substantive):
    from services.case_workspace import CaseWorkspaceError
    _,store,w,evidence,_=project
    case=store.create_case(w,'Security Turnstile','Prepare a Turnstile Coordination RFI','reviewer')
    for index in range(8):
        store.record_investigation_step(w,case['id'],'cross_modal_investigation',
            {'anchor_type':'evidence_item','anchor_id':evidence['id']},f'Child {index}','reviewer',
            assessment='UNRESOLVED')
    attention=store.record_go_attention(w,'reviewer','Verify Ontario turnstile content',[evidence['id']],evaluation_only=True)
    old=deepcopy((w.cases,w.investigation_steps,w.claims,w.reviewer_validations,w.applies))
    original=er.retrieve_reference
    raw=GOOD.encode() if substantive else b'<div id="root"></div><script>Building Code 163/24</script>'
    monkeypatch.setattr(er,'retrieve_reference',lambda s: original(s,opener=_FakeOpener(raw)))
    if substantive:
        result=store.retain_public_reference(w,'reviewer',attention['id'],'obc','Verify requested content only')['governed_result']
        assert result['state']=='UNRESOLVED' and result['authority']=='NOT_ESTABLISHED'
        assert result['content_validation']==er.RETRIEVED_SUBSTANTIVE_CONTENT
        assert w.sources[-1]['source_domain']=='EXTERNAL_REFERENCE'
        assert w.evidence_items[-1]['validation_status'] is None
    else:
        before=store._path_for(w.project_id).read_bytes()
        with pytest.raises(CaseWorkspaceError,match='RETRIEVED_NON_SUBSTANTIVE_SHELL'):
            store.retain_public_reference(w,'reviewer',attention['id'],'obc','Refuse a shell')
        assert store._path_for(w.project_id).read_bytes()==before
    saved=store.get(w.project_id)
    assert (saved.cases,saved.investigation_steps,saved.claims,saved.reviewer_validations,saved.applies)==old
