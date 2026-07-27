"""
Post-processes the raw captured HTML (from build_preview.py) into a
static-hostable site under build/site/:
- rewrites internal navigation hrefs to relative static filenames
- leaves every non-navigational href untouched (server actions, downloads,
  logout) - a shared inert script intercepts clicks/submits on anything not
  explicitly a known static page and shows a "static preview" notice instead
- copies the real current static/css + static/js assets unchanged
- injects one banner + one small script, identical on every page, stamped
  with the actual current commit (falls back to "uncommitted changes" if
  the working tree is dirty, so the banner never silently lies about what
  it's showing)

Run build_preview.py first. This script does not modify the repository -
everything it produces lives under build/ (git-ignored).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = Path(__file__).parent / "build"
RAW_DIR = BUILD_DIR / "_raw"
SITE_DIR = BUILD_DIR / "site"
FIXTURE_STORE = BUILD_DIR / "_fixture_store"

if not RAW_DIR.exists():
    sys.exit(f"{RAW_DIR} doesn't exist - run build_preview.py first.")

from services.case_workspace import CaseWorkspaceStore  # noqa: E402

PROJECT_ID = "sample-recreation-centre-rfp"
QUIET_PROJECT_ID = "sample-community-library-rfp"
store = CaseWorkspaceStore(FIXTURE_STORE)
workspace = store.get(PROJECT_ID)


def case_id_of(title, status=None):
    for c in workspace.cases:
        if c["title"] == title and (status is None or c["status"] == status):
            return c["id"]
    raise KeyError(title)


CASE_FILES = {
    case_id_of("Structural Drawing Review — Sheet A101"): "workspace-case1-drawing-review.html",
    case_id_of("Specification Compliance Review"): "workspace-case2-spec-compliance.html",
    case_id_of("Preliminary Site Assessment", "archived"): "workspace-case3-archived.html",
    case_id_of("Preliminary Site Assessment", "open"): "workspace-case4-derived.html",
}

STATIC_PAGE_NAMES = {
    "index.html", "login.html", "gateway.html", "upload.html", "projects.html",
    f"project-home-{PROJECT_ID}.html",
    f"project-home-{QUIET_PROJECT_ID}.html", *CASE_FILES.values(),
}

if SITE_DIR.exists():
    shutil.rmtree(SITE_DIR)
(SITE_DIR / "assets").mkdir(parents=True, exist_ok=True)
shutil.copy(REPO_ROOT / "static" / "css" / "tokens.css", SITE_DIR / "assets" / "tokens.css")
shutil.copy(REPO_ROOT / "static" / "css" / "main.css", SITE_DIR / "assets" / "main.css")
shutil.copy(REPO_ROOT / "static" / "js" / "case_workspace.js", SITE_DIR / "assets" / "case_workspace.js")

# Real generated Artifact crop images (the actual current mock-engine
# output, not a placeholder) - copied as static files since the live
# artifact_image route can't run on a static host.
ARTIFACTS_SRC = FIXTURE_STORE / "workspace_artifacts"
ARTIFACTS_DST = SITE_DIR / "assets" / "artifacts"
ARTIFACTS_DST.mkdir(parents=True, exist_ok=True)
for f in ARTIFACTS_SRC.glob("*.png"):
    shutil.copy(f, ARTIFACTS_DST / f.name)

ARTIFACT_IMAGE_REWRITES = [
    (
        rf'src="/projects/{PROJECT_ID}/workspace/artifacts/{re.escape(a["id"])}/image"',
        f'src="assets/artifacts/{a["image_path"]}"',
    )
    for a in workspace.artifacts
]


def _current_commit_label() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"{sha} + uncommitted changes" if dirty else sha
    except Exception:
        return "unknown"


PREVIEW_CSS = """
.preview-banner {
    position: sticky; top: 0; z-index: 1000;
    background: #6b5227; color: #f2ede3;
    font-family: "IBM Plex Mono", monospace; font-size: 0.78rem;
    text-align: center; padding: 0.55rem 1rem; line-height: 1.4;
    border-bottom: 1px solid #e8a33d;
}
.preview-banner strong { color: #e8a33d; }
.preview-toast {
    position: fixed; left: 50%; bottom: 1.5rem; transform: translate(-50%, 0.5rem);
    background: #16324c; color: #f2ede3; border: 1px solid #24445e;
    font-family: "IBM Plex Mono", monospace; font-size: 0.78rem;
    padding: 0.6rem 1rem; border-radius: 6px; opacity: 0; pointer-events: none;
    transition: opacity 0.15s ease, transform 0.15s ease; z-index: 1001;
}
.preview-toast.show { opacity: 1; transform: translate(-50%, 0); }
"""

PREVIEW_JS = """
(function () {
    var STATIC_PAGES = new Set(%s);
    function isAllowed(href) {
        if (!href) return false;
        if (href.charAt(0) === '#') return true;
        var bare = href.split('#')[0].split('?')[0];
        return STATIC_PAGES.has(bare) || bare === '';
    }
    function toast() {
        var el = document.getElementById('preview-static-toast');
        if (!el) return;
        el.classList.add('show');
        clearTimeout(window.__previewToastTimer);
        window.__previewToastTimer = setTimeout(function () { el.classList.remove('show'); }, 2200);
    }
    document.addEventListener('click', function (e) {
        var a = e.target.closest('a');
        if (!a) return;
        if (!isAllowed(a.getAttribute('href'))) { e.preventDefault(); toast(); }
    }, true);
    document.addEventListener('submit', function (e) {
        e.preventDefault();
        toast();
    }, true);
})();
""" % (repr(sorted(STATIC_PAGE_NAMES)).replace("'", '"'))

(SITE_DIR / "assets" / "preview.css").write_text(PREVIEW_CSS, encoding="utf-8")
(SITE_DIR / "assets" / "preview.js").write_text(PREVIEW_JS, encoding="utf-8")

BANNER_HTML = (
    '<div class="preview-banner">'
    '<strong>STATIC PREVIEW</strong> — a non-interactive snapshot of the current Archiosk UI '
    f'(source commit {_current_commit_label()}). Sign-in, uploads, and all actions are disabled here; '
    'the real application runs locally against Flask.'
    "</div>"
    '<div id="preview-static-toast" class="preview-toast">This control isn\'t active in the static preview.</div>'
)

REWRITES = [
    (r'href="/"', 'href="index.html"'),
    (r'href="/login"', 'href="login.html"'),
    (r'href="/gateway"', 'href="gateway.html"'),
    (r'href="/upload"', 'href="upload.html"'),
    (r'href="/projects"', 'href="projects.html"'),
    (rf'href="/projects/{PROJECT_ID}/workspace"', f'href="project-home-{PROJECT_ID}.html"'),
    (rf'href="/projects/{QUIET_PROJECT_ID}/workspace"', f'href="project-home-{QUIET_PROJECT_ID}.html"'),
]
for case_id, filename in CASE_FILES.items():
    REWRITES.append((rf'href="/projects/{PROJECT_ID}/workspace\?case={re.escape(case_id)}"', f'href="{filename}"'))

ASSET_REWRITES = [
    (r'href="/static/css/tokens\.css\?v=\d+"', 'href="assets/tokens.css"'),
    (r'href="/static/css/main\.css\?v=\d+"', 'href="assets/main.css"'),
    (r'src="/static/js/case_workspace\.js\?v=\d+"', 'src="assets/case_workspace.js"'),
]

for raw_file in RAW_DIR.glob("*.html"):
    html = raw_file.read_text(encoding="utf-8")

    for pattern, replacement in ASSET_REWRITES + REWRITES + ARTIFACT_IMAGE_REWRITES:
        html = re.sub(pattern, replacement, html)

    html = html.replace(
        "</head>",
        '<link rel="stylesheet" href="assets/preview.css">\n</head>',
    )
    html = html.replace("<body>", "<body>\n" + BANNER_HTML, 1)
    html = html.replace(
        "</body>",
        f"<script>{PREVIEW_JS}</script>\n</body>",
    )

    (SITE_DIR / raw_file.name).write_text(html, encoding="utf-8")

print(f"Wrote {len(list(RAW_DIR.glob('*.html')))} static pages to {SITE_DIR}")
print("Case file map:", CASE_FILES)
print("Banner commit label:", _current_commit_label())
