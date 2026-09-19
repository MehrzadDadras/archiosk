"""Stage 1 live UI proof using an existing maintainer-issued verification link.

Reads existing real/evaluation records only; changes the verification session's
Developer Mode and observation preferences, then revokes that temporary session.
Never provisions an account, creates evidence, or copies the bearer URL to proof.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    access = os.environ.pop("ARCHIOSK_VERIFICATION_URL", "")
    parsed = urlparse(access)
    if parsed.scheme != "https" or parsed.hostname not in ("archiosk.com", "www.archiosk.com") or not parsed.path.startswith("/verification-access/"):
        raise SystemExit("An existing maintainer-issued HTTPS verification link is required.")
    base = parsed.scheme + "://" + parsed.netloc
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    proof = {"runs": [], "browser_errors": []}
    project = "/projects/9c00eeec-4e65-4bde-bcea-de8b09c8beb1/kernel"
    paths = [("Castille real project", project, False),
        ("Earned H", "/admin/survey-evaluation/287369d4b4af47dc8ddaf2e49aa9cb0e/kernel", True),
        ("Missing monument", "/admin/survey-evaluation/60678a60a1ce49d787265790c088b09e/kernel", True),
        ("Qualified traverse", "/admin/survey-evaluation/270812e8302f484890356792b6036b99/kernel", True)]
    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, extra_http_headers={"Referer": base + "/"})
        page = context.new_page()
        page.set_default_timeout(120000)
        page.on("pageerror", lambda error: proof["browser_errors"].append(str(error)))
        assert page.request.get(base + project, max_redirects=0).status == 302
        page.goto(access, wait_until="domcontentloaded")
        access = ""
        csrf = page.locator('meta[name="csrf-token"]').get_attribute("content")
        try:
            assert page.request.get(base + project, max_redirects=0).status == 403
            # Same existing toggle used by the Survey live verifier.
            response = page.request.post(base + "/developer-mode/toggle", form={"csrf_token": csrf})
            assert response.ok, f"Developer Mode toggle failed: {response.status}"
            page.goto(base + "/admin/survey-evaluation", wait_until="domcontentloaded")
            if page.get_by_role("button", name="Observe my real requests", exact=True).count():
                page.get_by_role("button", name="Observe my real requests", exact=True).click()
                page.wait_for_load_state("domcontentloaded")
            for name, path, evaluation in paths:
                response = page.goto(base + path, wait_until="domcontentloaded")
                assert response.status == 200
                assert page.get_by_role("heading", name="Generic kernel mapping", exact=True).count() == 1
                options = page.locator("#kernel-item option").evaluate_all("nodes => nodes.map(n => n.value)")
                selected = [next(v for v in options if v.startswith("sources:")),
                            [v for v in options if v.startswith("evidence_items:")][-1]]
                for address in selected:
                    page.select_option("#kernel-item", address)
                    with page.expect_navigation(wait_until="domcontentloaded") as navigation:
                        page.get_by_role("button", name="Inspect item", exact=True).click()
                    response = navigation.value
                    assert response.status == 200
                    record = json.loads(page.locator("#kernel-record").text_content())
                    assert address.endswith(":" + record["id"])
                    if evaluation:
                        assert "EVALUATION_INPUT" in page.locator("#kernel-selected").inner_text()
                    state = page.locator("#kernel-state").inner_text() if page.locator("#kernel-state").count() else None
                    observation = response.headers.get("x-archiosk-observation")
                    assert observation
                    trace_url = page.locator("#kernel-trace").get_attribute("href")
                    trace = page.request.get(base + trace_url)
                    trace_html = trace.text()
                    assert "services.case_workspace.CaseWorkspaceStore.inspect_kernel_mapping" in trace_html
                    assert 'data-phase="CONSUMED"' in trace_html
                    assert 'data-phase="SURFACED"' in trace_html
                    if address.startswith("evidence_items:"):
                        assert "services.case_workspace.CaseWorkspaceStore.admit_proposition" in trace_html
                    proof["runs"].append(dict(case=name, path=path, address=address, state=state,
                        evaluation_only=evaluation, observation=observation))
                    with page.expect_navigation(wait_until="domcontentloaded") as reload_navigation:
                        page.get_by_role("button", name="Reload view", exact=True).click()
                    refreshed = reload_navigation.value
                    assert refreshed.status == 200
                    assert page.locator("#kernel-item").input_value() == address
                    assert json.loads(page.locator("#kernel-record").text_content()) == record
                    refreshed_state = page.locator("#kernel-state").inner_text() if page.locator("#kernel-state").count() else None
                    assert refreshed_state == state
                    assert refreshed.headers.get("x-archiosk-observation") != observation
                    proof["runs"][-1]["reload_observation"] = refreshed.headers.get("x-archiosk-observation")
                page.screenshot(path=str(output / (name.lower().replace(" ", "-") + ".png")), full_page=True)
            assert page.request.get(base + project + "?item=evidence_items:foreign").status == 404
            assert page.request.get(base + "/admin/survey-evaluation/unknown/kernel").status == 404
            assert not proof["browser_errors"]
            proof["passed"] = True
        finally:
            ended = page.request.post(base + "/verification-access/end", form={"csrf_token": csrf})
            proof["verification_access_revoked"] = ended.ok
            (output / "live-proof.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
            browser.close()
    print(json.dumps({"passed": proof.get("passed", False), "inspections": len(proof["runs"]),
                      "errors": len(proof["browser_errors"]), "revoked": proof["verification_access_revoked"]}))


if __name__ == "__main__":
    main()
