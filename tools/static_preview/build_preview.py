"""
Builds a static HTML preview of the current BEEHIVE application by:
1. Seeding a richly representative synthetic PREVIEW project through the
   REAL Flask routes (test client), exercising the actual current
   behavior end to end - not hand-authored fixture JSON.
2. Capturing the real rendered HTML for each representative screen.
3. Post-processing (see postprocess.py): neutralizing every form/button
   (no server behind the static host), rewriting internal navigation
   between captured pages to relative static filenames, injecting one
   "STATIC PREVIEW" banner/script.
4. Copying the actual current static/css and static/js assets unchanged.

This is a maintainer-run build tool. It does not modify the repository -
everything it produces lives under build/ (git-ignored). Run
postprocess.py afterwards to turn the raw capture into the deployable
site/.

Usage:
    python tools/static_preview/build_preview.py
    python tools/static_preview/postprocess.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = Path(__file__).parent / "build"
FIXTURE_STORE = BUILD_DIR / "_fixture_store"
RAW_DIR = BUILD_DIR / "_raw"

import shutil  # noqa: E402

for d in (FIXTURE_STORE, RAW_DIR):
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)

import app as app_module  # noqa: E402
from services.bhive_parser import ConsistencyFlag, ParsedDocument, RequirementItem  # noqa: E402
from services.requirements_registry import RequirementsRegistry  # noqa: E402
from PIL import Image  # noqa: E402

flask_app = app_module.create_app("testing")
flask_app.config["REGISTRY_STORE_PATH"] = str(FIXTURE_STORE)
flask_app.config["SERVER_NAME"] = "preview.local"

PROJECT_ID = "sample-recreation-centre-rfp"

# -- seed the legacy ingestion record (as BHiveParser would produce it) -----
items = [
    RequirementItem(id="req-1", text="Contractor shall provide licensed and insured labor for all trades.",
                     category="compliance_legal", confidence=0.74, source_line=12),
    RequirementItem(id="req-2", text="All structural steel shall comply with CSA S16 and be stamped by a "
                     "Professional Engineer licensed in the province.",
                     category="technical_specification", confidence=0.81, source_line=34),
    RequirementItem(id="req-3", text="Substantial Performance shall be achieved no later than 18 months "
                     "following contract award.",
                     category="schedule_milestone", confidence=0.69, source_line=58),
    RequirementItem(id="req-4", text="Proposals must include an itemized cost breakdown by CSI division.",
                     category="submission_instruction", confidence=0.71, source_line=71),
]
flag = ConsistencyFlag(
    id="flag-1",
    requirement_a_id="req-3", requirement_a_text=items[2].text,
    requirement_b_id="req-5", requirement_b_text="Site mobilization may not begin before month 4 pending "
    "utility relocation, per Addendum 1.",
    explanation="An 18-month Substantial Performance deadline measured from award appears incompatible "
    "with a mobilization delay of up to 4 months described in Addendum 1.",
)
document = ParsedDocument(
    project_id=PROJECT_ID, filename="Sample_Recreation_Centre_RFP.pdf", ingested_at="2026-02-03T14:05:00+00:00",
    requirements=items, consistency_flags=[flag], consistency_checked=True,
)
RequirementsRegistry(FIXTURE_STORE).save(document)

# A second, quieter project - ingested but never worked, for the Projects
# directory page to show real card variety (not every project has open
# attention/conflicts).
QUIET_PROJECT_ID = "sample-community-library-rfp"
RequirementsRegistry(FIXTURE_STORE).save(ParsedDocument(
    project_id=QUIET_PROJECT_ID, filename="Community_Library_Addition_RFP.pdf",
    ingested_at="2026-01-14T10:30:00+00:00",
    requirements=[
        RequirementItem(id="lib-req-1", text="Design shall achieve LEED Silver certification or equivalent.",
                         category="technical_specification", confidence=0.77, source_line=9),
    ],
))


def client_with_session(username, role, user_id):
    c = flask_app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = username
        sess["role"] = role
    return c


owner = client_with_session("j.rivera", "admin", 1)
other = client_with_session("a.chen", "read_only", 2)


def post(client, path, data=None, **kw):
    resp = client.post(path, data=data or {}, follow_redirects=True, **kw)
    assert resp.status_code < 400, f"POST {path} -> {resp.status_code}\n{resp.get_data(as_text=True)[:2000]}"
    return resp


def get(client, path):
    resp = client.get(path)
    assert resp.status_code == 200, f"GET {path} -> {resp.status_code}"
    return resp


def find_id(collection, key, value):
    return next(c for c in collection if c[key] == value)


# -- warm the workspace (auto-registers the RFQ/RFP Source) -----------------
get(owner, f"/projects/{PROJECT_ID}/workspace")

from services.case_workspace import CaseWorkspaceStore  # noqa: E402
store = CaseWorkspaceStore(FIXTURE_STORE)


def workspace():
    return store.get(PROJECT_ID)


def rfq_source_id():
    return find_id(workspace().sources, "kind", "rfq_rfp_document")["id"]


# =====================================================================
# Case 1 — private, active drawing review, discussion + attention + RFI
# =====================================================================
post(owner, f"/projects/{PROJECT_ID}/workspace/cases",
     data={"title": "Structural Drawing Review — Sheet A101", "objective": "Verify datum and dimension callouts against the issued structural set."})
case1 = find_id(workspace().cases, "title", "Structural Drawing Review — Sheet A101")

# a small real placeholder drawing image
drawing_bytes = io.BytesIO()
Image.new("RGB", (900, 600), color=(235, 232, 224)).save(drawing_bytes, format="PNG")
drawing_bytes.seek(0)
post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case1['id']}/sources",
     data={"drawing": (drawing_bytes, "sheet-a101.png")}, content_type="multipart/form-data")

post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case1['id']}/messages",
     data={"text": "Analyze this drawing for datum inconsistencies"})
findings_case1 = [f for f in workspace().findings if f["case_id"] == case1["id"]]
finding_a = findings_case1[0]
if len(findings_case1) > 1:
    finding_b = findings_case1[1]
else:
    finding_b = finding_a

post(owner, f"/projects/{PROJECT_ID}/workspace/findings/{finding_a['id']}/validate",
     data={"validation": "Correct", "case_id": case1["id"]})
post(owner, f"/projects/{PROJECT_ID}/workspace/findings/{finding_a['id']}/disposition",
     data={"disposition": "Confirmed", "case_id": case1["id"]})
post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case1['id']}/apply", data={"confirm": "once"})

if finding_b is not finding_a:
    post(owner, f"/projects/{PROJECT_ID}/workspace/findings/{finding_b['id']}/validate",
         data={"validation": "Needs Evidence", "case_id": case1["id"]})

# discussion + attention (one pending, one responded)
post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case1['id']}/threads",
     data={"title": "Datum callout on gridline C", "text": "Does this elevation reference the project benchmark or a local one?"})
thread1 = find_id(workspace().review_threads, "title", "Datum callout on gridline C")
msg1 = find_id(workspace().review_messages, "thread_id", thread1["id"])
post(owner, f"/projects/{PROJECT_ID}/workspace/threads/{thread1['id']}/attention",
     data={"message_id": msg1["id"], "intended_actor": "a.chen"})

post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case1['id']}/threads",
     data={"title": "Legend symbol unresolved", "text": "This legend symbol doesn't match the published legend sheet."})
thread2 = find_id(workspace().review_threads, "title", "Legend symbol unresolved")
msg2 = find_id(workspace().review_messages, "thread_id", thread2["id"])
post(owner, f"/projects/{PROJECT_ID}/workspace/threads/{thread2['id']}/attention",
     data={"message_id": msg2["id"], "intended_actor": "a.chen"})
post(owner, f"/projects/{PROJECT_ID}/workspace/threads/{thread2['id']}/messages",
     data={"text": "Confirmed against the reissued legend sheet — symbol is correct, legend was outdated."})
resp_msg = [m for m in workspace().review_messages if m["thread_id"] == thread2["id"]][-1]
attention2 = find_id(workspace().attentions, "thread_id", thread2["id"])
post(owner, f"/projects/{PROJECT_ID}/workspace/attentions/{attention2['id']}/respond",
     data={"response_message_id": resp_msg["id"]})
post(owner, f"/projects/{PROJECT_ID}/workspace/threads/{thread2['id']}/resolve",
     data={"resolution_outcome": "no_issue", "summary": "Legend sheet reissue accounted for the mismatch."})

# RFI: one drafted, one issued
post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case1['id']}/rfi-drafts",
     data={"finding_id": finding_a["id"], "question_text": "Please confirm the datum reference used for the elevation callout on gridline C."})
draft1 = find_id(workspace().rfi_drafts, "finding_id", finding_a["id"])

if finding_b is not finding_a:
    post(owner, f"/projects/{PROJECT_ID}/workspace/findings/{finding_b['id']}/validate", data={"validation": "Correct", "case_id": case1["id"]})
    post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case1['id']}/rfi-drafts",
         data={"finding_id": finding_b["id"], "question_text": "Please clarify which legend revision governs this sheet."})
    draft2 = find_id(workspace().rfi_drafts, "finding_id", finding_b["id"])
    post(owner, f"/projects/{PROJECT_ID}/workspace/rfi-drafts/{draft2['id']}/issue", data={"confirm": "once", "case_id": case1["id"]})

# =====================================================================
# Case 2 — shared -> collaborative, promoted Requirement + adjudication
# =====================================================================
post(owner, f"/projects/{PROJECT_ID}/workspace/cases",
     data={"title": "Specification Compliance Review", "objective": "Confirm submitted specifications satisfy stated RFP requirements."})
case2 = find_id(workspace().cases, "title", "Specification Compliance Review")
post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case2['id']}/share")

post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case2['id']}/requirement-items/req-2/promote",
     data={"source_id": rfq_source_id()})
requirement = find_id(workspace().requirements, "original_requirement_identifier", "req-2")
finding_req = find_id(workspace().findings, "case_id", case2["id"])

# a genuine non-owner contribution crosses the collaboration threshold
post(other, f"/projects/{PROJECT_ID}/workspace/findings/{finding_req['id']}/validate",
     data={"validation": "Correct", "case_id": case2["id"]})
post(owner, f"/projects/{PROJECT_ID}/workspace/findings/{finding_req['id']}/disposition",
     data={"disposition": "Confirmed", "case_id": case2["id"]})
post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case2['id']}/apply", data={"confirm": "once"})

post(owner, f"/projects/{PROJECT_ID}/workspace/requirements/{requirement['id']}/adjudicate",
     data={"outcome": "Satisfied", "reasoning": "Submitted structural specification cites CSA S16 and includes the sealed drawing package.",
           "case_id": case2["id"], "evidence_finding_id": [finding_req["id"]]})

# a second, not-yet-adjudicated requirement so the rollup shows a mix of states
post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case2['id']}/requirement-items/req-4/promote",
     data={"source_id": rfq_source_id()})

# =====================================================================
# Case 3 — archived, with an unresolved comment preserved
# =====================================================================
post(owner, f"/projects/{PROJECT_ID}/workspace/cases",
     data={"title": "Preliminary Site Assessment", "objective": "Early review of site constraints prior to RFP issuance."})
case3 = find_id(workspace().cases, "title", "Preliminary Site Assessment")
post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case3['id']}/threads",
     data={"title": "Utility relocation timeline", "text": "Has the utility relocation schedule referenced in Addendum 1 been confirmed with the municipality?"})
post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case3['id']}/archive")

# =====================================================================
# Case 4 — derived from the archived Case 3
# =====================================================================
post(owner, f"/projects/{PROJECT_ID}/workspace/cases/{case3['id']}/derive")
case4 = find_id(workspace().cases, "derived_from_case_id", case3["id"])

print("Fixture build complete.")
print("cases:", [(c["title"], c["status"], c["visibility"]) for c in workspace().cases])

# =====================================================================
# Capture real rendered HTML for each representative screen
# =====================================================================
captures = {
    "index.html": get(owner, "/").data,
    "login.html": get(flask_app.test_client(), "/login").data,
    "gateway.html": get(owner, "/gateway").data,
    "upload.html": get(owner, "/upload").data,
    "projects.html": get(owner, "/projects").data,
    # /dashboard/<id> is retired (redirects into Case Workspace - see
    # routes/portal.py's dashboard()) - nothing left to capture there.
    f"project-home-{PROJECT_ID}.html": get(owner, f"/projects/{PROJECT_ID}/workspace").data,
    "workspace-case1-drawing-review.html": get(owner, f"/projects/{PROJECT_ID}/workspace?case={case1['id']}").data,
    "workspace-case2-spec-compliance.html": get(owner, f"/projects/{PROJECT_ID}/workspace?case={case2['id']}").data,
    "workspace-case3-archived.html": get(owner, f"/projects/{PROJECT_ID}/workspace?case={case3['id']}").data,
    "workspace-case4-derived.html": get(owner, f"/projects/{PROJECT_ID}/workspace?case={case4['id']}").data,
    f"project-home-{QUIET_PROJECT_ID}.html": get(owner, f"/projects/{QUIET_PROJECT_ID}/workspace").data,
}
for name, data in captures.items():
    (RAW_DIR / name).write_bytes(data)

print(f"Captured {len(captures)} raw pages into {RAW_DIR}")
