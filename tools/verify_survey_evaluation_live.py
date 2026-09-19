"""Authorized live-browser proof for the protected Survey Evaluation surface.

Uses a maintainer-issued existing verification-access link from the environment.
Never creates credentials or logs the bearer link. Writes only evaluation runs
and local proof artifacts. Requires the existing local Playwright installation.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True)
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
        context=browser.new_context(viewport={"width":1440,"height":1000})
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
        for case in CASES:
            print(case+": exercising live route",flush=True)
            response=page.request.post(base+"/admin/survey-evaluation",form={"case":case,"csrf_token":csrf},max_redirects=0,timeout=120000)
            assert response.status==302, "Case creation failed: "+case+" / "+str(response.status)
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
