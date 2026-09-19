"""Authorized live-browser proof for the protected Survey Evaluation surface.

Uses a maintainer-issued existing verification-access link from the environment.
Never creates credentials or logs the bearer link. Writes controlled evaluation
runs, local proof artifacts and, with --operational, the explicitly requested
ordinary document conversation. Does not change source authority. Requires the
existing local Playwright installation.
"""
import argparse
import json
import os
import re
from pathlib import Path
import sys
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True)
    parser.add_argument("--cases",help="Comma-separated affected cases; omit for the full catalog")
    parser.add_argument("--operational",action="store_true",help="Observe actual calls and an eligible ordinary document request")
    arguments=parser.parse_args()
    token_url=os.environ.pop("ARCHIOSK_VERIFICATION_URL","")
    parsed=urlparse(token_url)
    if parsed.scheme!="https" or parsed.hostname not in ("archiosk.com","www.archiosk.com") or not parsed.path.startswith("/verification-access/"):
        raise SystemExit("An existing maintainer-issued HTTPS verification link is required.")
    base=parsed.scheme+"://"+parsed.netloc
    from playwright.sync_api import sync_playwright
    from services.survey_evaluation import CASES
    output=Path(arguments.output);output.mkdir(parents=True,exist_ok=True)
    proof={"base_url":base,"runs":[],"browser_errors":[]}
    with sync_playwright() as driver:
        browser=driver.chromium.launch(headless=True)
        # APIRequestContext posts must carry the same-origin Referer that a
        # real HTTPS form submission supplies; keep production CSRF intact.
        context=browser.new_context(viewport={"width":1440,"height":1000},
                                    extra_http_headers={"Referer":base+"/"})
        page=context.new_page();page.set_default_timeout(120000)
        public=page.request.get(base+"/admin/survey-evaluation",max_redirects=0)
        assert public.status==302, "Public request reached the evaluation surface"
        proof["public_status"]=public.status
        page.goto(token_url,wait_until="domcontentloaded")
        token_url=""
        csrf=page.locator('meta[name="csrf-token"]').get_attribute("content")
        disabled=page.request.get(base+"/admin/survey-evaluation",max_redirects=0)
        assert disabled.status==403, "Developer-mode gate was not enforced"
        proof["developer_disabled_status"]=disabled.status
        toggled=page.request.post(base+"/developer-mode/toggle",form={"csrf_token":csrf})
        assert toggled.ok
        assert page.goto(base+"/admin/survey-evaluation",wait_until="domcontentloaded").status==200
        page.screenshot(path=str(output/"evaluation-catalog.png"),full_page=True)
        page.on("pageerror",lambda error:proof["browser_errors"].append(str(error)))
        if arguments.operational:
            enabled=page.request.post(base+"/admin/survey-evaluation",form={"csrf_token":csrf,"action":"observe","enabled":"yes"})
            assert enabled.ok
            page.goto(base+"/admin/survey-evaluation",wait_until="domcontentloaded")
            candidates=page.locator('main.survey-evaluation a[href^="/document-shop/jobs/"]')
            survey=candidates.filter(has_text=re.compile("survey|castille",re.I))
            live=survey.first if survey.count() else candidates.first
            assert live.count(), "No eligible real Document Shop source was exposed"
            live_name=live.inner_text()
            live_url=base+live.get_attribute("href")
            response=page.goto(live_url,wait_until="domcontentloaded")
            assert response.status==200
            trace_id=response.headers.get("x-archiosk-observation")
            assert trace_id, "Ordinary request was not observed"
            proof["live_project"]={"name":live_name,"url":live_url,"observation":trace_id}
            page.screenshot(path=str(output/"live-project-result.png"),full_page=True)
            csrf=page.locator('meta[name="csrf-token"]').get_attribute("content")
            answered=page.request.post(live_url,form={"csrf_token":csrf,"question":"What is established and what remains unresolved in this source?"},max_redirects=0,timeout=120000)
            assert answered.status==302
            answer_trace=answered.headers.get("x-archiosk-observation")
            page.goto(base+"/admin/survey-evaluation?observation="+answer_trace,wait_until="domcontentloaded")
            assert page.locator('.runtime-event[data-owner="services.document_conversation.ask"][data-phase="INVOKED"]').count()
            assert page.locator('.runtime-event[data-phase="PROVIDER_INPUT"]').count()
            assert page.locator('.runtime-event[data-phase="PROVIDER_OUTPUT"]').count()
            assert page.locator('.runtime-event[data-phase="FINAL_ADMISSION"]').count()
            proof["live_project"]["ask_observation"]=answer_trace
            section=page.locator("section").filter(has=page.get_by_text("Actual request observations",exact=True))
            section.locator("details > summary").first.click()
            page.locator('.runtime-event[data-phase="FINAL_ADMISSION"]').scroll_into_view_if_needed()
            page.screenshot(path=str(output/"live-project-operational-trace.png"))
            (output/"live-proof.json").write_text(json.dumps(proof,indent=2),encoding="utf-8")
        selected=arguments.cases.split(",") if arguments.cases else list(CASES)
        assert all(case in CASES for case in selected), "Unknown qualification case"
        for case in selected:
            print(case+": exercising live route",flush=True)
            response=page.request.post(base+"/admin/survey-evaluation",form={"case":case,"csrf_token":csrf},max_redirects=0,timeout=120000)
            assert response.status==302, "Case creation failed: "+case+" / "+str(response.status)
            creation_trace=response.headers.get("x-archiosk-observation")
            route=response.headers["location"]
            url=base+route if route.startswith("/") else route
            response=page.goto(url,wait_until="domcontentloaded")
            assert response.status==200, "Case surface failed: "+case
            assert page.locator("main.survey-evaluation").count()==1
            assert page.locator(".se-drawing svg").count()==1
            csrf=page.locator('meta[name="csrf-token"]').get_attribute("content")
            reviewed=page.request.post(url,form={"csrf_token":csrf,"action":"confirm"})
            assert reviewed.ok, "Review failed: "+case
            assert page.goto(url,wait_until="domcontentloaded").status==200
            text=page.locator("main.survey-evaluation").inner_text()
            assert "EVALUATION_INPUT" in text and "CAPABILITY NOT YET IMPLEMENTED" in text
            result={"case":case,"url":url,"surface":200,"reviewed":True}
            expected_operations={"monument":"ESTABLISHED","occupation":"ESTABLISHED","earned-h":"ESTABLISHED",
                                 "missing-monument":"UNRESOLVED","degenerate-controls":"DEGENERATE","traverse":"UNRESOLVED"}
            if case in expected_operations:
                operation=page.locator("article").filter(has=page.get_by_text("Survey operation after review/reload",exact=False)).first
                assert "Actual result: "+expected_operations[case] in operation.inner_text(), "Unexpected admitted operation state: "+case
                admission=json.loads(operation.locator("pre").text_content())
                assert admission["evaluation_only"]
                result["operation_state"]=admission["state"]
                if case=="traverse":
                    assert admission["record"]["state"]=="PARTIALLY_RECOVERED"
                    assert admission["record"]["derivation"]["calculation"]["state"]=="CALCULATED_FROM_QUALIFIED_INPUT"
                    assert not admission["admissible"]
                if case=="earned-h":
                    assert admission["record"]["derivation"]["physical_scale"]=="NOT_ESTABLISHED"
                    assert len(admission["record"]["premise_ids"])==5
            if arguments.operational:
                result["observation"]=response.headers.get("x-archiosk-observation")
                result["creation_observation"]=creation_trace
                assert result["observation"], "Case execution was not observed"
            if case in ("supersession","whole-source"):
                for action in ("accept","apply"):
                    assert page.request.post(url,form={"csrf_token":csrf,"action":action}).ok
                page.goto(url,wait_until="domcontentloaded")
                lineage=page.locator("details").filter(has=page.get_by_text("Predecessor / successor lineage",exact=True))
                links=json.loads(lineage.locator("pre").text_content())
                assert len(links)==1 and links[0]["predecessor_type"]==("source" if case=="whole-source" else "evidence_item")
                result["accepted_and_applied"]=True
            if case=="missing-predecessor":
                assert page.request.post(url,form={"csrf_token":csrf,"action":"accept"}).ok
                page.goto(url,wait_until="domcontentloaded")
                assessments=page.locator("details").filter(has=page.get_by_text("Scoped proposals",exact=True))
                records=json.loads(assessments.locator("pre").text_content())
                assert records and all(record["state"]=="proposed" for record in records)
                assert page.request.post(url,form={"csrf_token":csrf,"action":"reject"}).ok
                page.goto(url,wait_until="domcontentloaded")
                records=json.loads(assessments.locator("pre").text_content())
                assert all(record["state"]=="rejected" for record in records)
                result["acceptance_refused_and_rejection_retained"]=True
            if case=="missing-sheet":
                assert page.request.post(url,form={"csrf_token":csrf,"action":"arrival"}).ok
                page.goto(url,wait_until="domcontentloaded")
                assert "ESTABLISHED" in page.locator("article").filter(has_text="Expected-but-absent sheet / retained history").inner_text()
                result["arrival_consumed"]=True
            if case in ("homography","no-h","survey","unreadable","non-finite","curve"):
                page.screenshot(path=str(output/(case+".png")),full_page=True)
                result["screenshot"]=case+".png"
            if case=="homography":
                artifact=page.request.get(url+"/artifact/governed.ifc")
                assert artifact.status==200 and b"EVALUATION_INPUT" in artifact.body()
                result["ifc"]=200
            if case in ("no-h","singular","ill-conditioned","infinity","projective","non-finite","space-mismatch"):
                assert "REFUSED" in text
                artifact=page.request.get(url+"/artifact/governed.ifc")
                assert artifact.status==404, "Refused IFC was served: "+case
                result["ifc"]=404
            if case in ("survey","curve"):
                artifact=page.request.get(url+"/artifact/reference.pdf")
                assert artifact.status==200 and artifact.body().startswith(b"%PDF")
                (output/(case+"-reference.pdf")).write_bytes(artifact.body())
            if case=="non-finite":
                page.locator("#question").fill("What is the height?")
                page.get_by_role("button",name="Ask GO about this evaluation",exact=True).click()
                page.wait_for_load_state("domcontentloaded")
                answer=page.locator("main.survey-evaluation").inner_text()
                assert "Qualification preservation: True" in answer, "Ask GO provider did not return an admitted evaluation answer"
                assert "Height could not be established" in answer
                result["ask_go"]=True
                page.screenshot(path=str(output/"ask-go-governed-refusal.png"),full_page=True)
            proof["runs"].append(result)
            (output/"live-proof.json").write_text(json.dumps(proof,indent=2),encoding="utf-8")
            print(case+": live surface and review PASS",flush=True)
        if arguments.operational:
            for result in proof["runs"]:
                page.goto(base+"/admin/survey-evaluation?observation="+result["observation"],wait_until="domcontentloaded")
                assert page.locator('.runtime-event[data-phase="INVOKED"]').count(), "No actual invocation in retained case trace"
                if result["case"] in ("earned-h","degenerate-controls","monument","occupation","missing-monument","traverse"):
                    page.goto(base+"/admin/survey-evaluation?observation="+result["creation_observation"],wait_until="domcontentloaded")
                    assert page.locator('.runtime-event[data-owner="services.survey_graph.derive_survey_operation"][data-phase="INVOKED"]').count()
                    if result["case"] in ("earned-h","degenerate-controls"):
                        assert page.locator('.runtime-event[data-owner="engine.spatial_compiler.estimate_control_homography"][data-phase="INVOKED"]').count()
        assert not proof["browser_errors"], "Browser errors occurred"
        # End the existing verification session through its own revocation route.
        ended=page.request.post(base+"/verification-access/end",form={"csrf_token":csrf})
        assert ended.ok
        proof["verification_access_revoked"]=True
        (output/"live-proof.json").write_text(json.dumps(proof,indent=2),encoding="utf-8")
        browser.close()
    print("LIVE_PASS",len(proof["runs"]),flush=True)


if __name__=="__main__":
    try:
        main()
    except Exception as error:
        # Browser exception text may contain the one-time login URL.
        print("LIVE_VERIFICATION_FAILED: "+type(error).__name__+(": "+str(error) if isinstance(error,AssertionError) else ""),file=sys.stderr)
        raise SystemExit(1) from None
