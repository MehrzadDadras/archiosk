"""MASTERUI-PREVIEW: the Master command registry - one list of commands for the
whole application, in 19 fixed families.

WHY A NEW MODULE rather than `capability_registry`. That registry is the closed
vocabulary of actions GO may EXECUTE (each with an executor). This one is the
Master Menu's command grammar: navigation and actions a person invokes, each
with an applicability rule. The two overlap (Examine, Re-analyze) and should
converge once the Master UI is accepted; for the Product Owner preview they are
kept apart so nothing GO can do changes.

THE LAWS THIS ENCODES
- Families are fixed, in one order, everywhere. `resolve_master_menu` always
  returns all 19, whatever the page, role or object.
- Context changes STATE only: every command resolves to `active`, `grey` (with
  a reason) or `current`. Nothing is removed for role, project type or page.
- A grey command carries NO route: its href is never computed, so an
  unavailable action is not exposed.
- `NOT_YET` marks capability that genuinely does not exist in ARCHIOSK yet.
  Everything else maps to a real, existing route or control.

Resolution is presentation only: it reads the request and the governed
identity and writes nothing. Route gates are unchanged and remain the
authority - a menu item being active never grants anything.
"""

from __future__ import annotations

import uuid
from typing import Callable, Optional
from urllib.parse import urlencode

FAMILIES = (
    "FILE", "EDIT", "VIEW", "DOCUMENT", "DATA", "QUERY", "MODEL", "MARKET",
    "COMPARE", "CHECK", "CREATE", "PROJECT", "PORTFOLIO", "DEAL",
    "RELATIONSHIPS", "TRACE", "TOOLS", "WINDOW", "HELP",
)

NOT_YET = "Not available yet"
NEED_PROJECT = "Open a project or document first"
NEED_DOCUMENT = "Open a document first"
NEED_PROJECT_KIND = "Available inside a project"
NEED_DOCUMENTS_KIND = "Available for uploaded documents"
ADMIN_ONLY = "Admin only"
DEVELOPER_ONLY = "Developer Mode only"
NEED_VIEWER = "Available while a document is open in the viewer"


class Ctx:
    """Everything a command's rule may read. Built once per render."""

    def __init__(self, *, identity, endpoint, args, admin, developer, customer,
                 username, result=None, url_for=None, path="", can_publish=False):
        identity = identity or {}
        self.project = identity.get("project")
        self.source = identity.get("source")
        self.kind = (self.project or {}).get("kind")
        self.endpoint = endpoint or ""
        self.args = dict(args or {})
        self.admin = bool(admin)
        self.developer = bool(developer)
        self.customer = bool(customer)
        self.username = username
        self.result = result if isinstance(result, dict) else None
        self.url_for = url_for
        self.path = path
        # The workspace route's own eligibility answer (an Owner project still in
        # pre-publication) - the same flag the classic File > Publish RFP used.
        self.can_publish = bool(can_publish)

    # -- small predicates ---------------------------------------------------
    @property
    def pid(self):
        return (self.project or {}).get("id")

    @property
    def sid(self):
        return (self.source or {}).get("id")

    def on(self, *endpoints):
        return self.endpoint in endpoints

    def workspace_view(self, view=None):
        """On the project workspace, in a given `view` state (None = default)."""
        if self.endpoint != "workspace.show_workspace":
            return False
        return (self.args.get("view") or None) == view

    def density_url(self, density):
        args = dict(self.args)
        args["density"] = density
        return self.path + "?" + urlencode(args)


class Command:
    def __init__(self, cid, family, label, *, href=None, post=None, fields=None,
                 proxy=None, action=None, bulk=None, needs=None, current=None, not_yet=False,
                 capability=None):
        self.id, self.family, self.label = cid, family, label
        self.href = href            # ctx -> url  (GET)
        self.post = post            # ctx -> url  (POST form)
        self.fields = fields        # ctx -> {name: value} hidden fields
        self.proxy = proxy          # id of an existing on-page control to click
        self.action = action        # an app_menu.js named action
        self.bulk = bulk            # ctx -> action value submitted with the page's
                                    # selection form (#document-bulk); None = n/a here
        self.capability = capability  # the GO ACTION_REGISTRY id this command IS
        self.needs = needs          # ctx -> None | reason (grey)
        self.current = current      # ctx -> bool
        self.not_yet = not_yet


def registry_bulk(capability_id):
    """The action value GO's own registry submits for this capability.

    Registry convergence: a Master selection command and GO's governed desk
    action are ONE act, so the Master command takes its submitted value from
    capability_registry.ACTION_REGISTRY rather than restating it.
    """
    from services.capability_registry import ACTION_REGISTRY
    return ACTION_REGISTRY[capability_id]["bulk_action"]


def _need(*checks: Callable[[Ctx], Optional[str]]):
    def run(c):
        for check in checks:
            reason = check(c)
            if reason:
                return reason
        return None
    return run


def project(c):
    return None if c.pid else NEED_PROJECT


def project_kind(c):
    return project(c) or (None if c.kind == "project" else NEED_PROJECT_KIND)


def documents_kind(c):
    return project(c) or (None if c.kind == "documents" else NEED_DOCUMENTS_KIND)


def document(c):
    return project(c) or (None if c.sid else NEED_DOCUMENT)


def admin(c):
    return None if c.admin else ADMIN_ONLY


def developer(c):
    return admin(c) or (None if c.developer else DEVELOPER_ONLY)


def staff(c):
    return None if not c.customer else "Not available for Document Shop accounts"


def viewer(c):
    return project_kind(c) or (None if c.sid and c.endpoint == "workspace.show_workspace"
                               else NEED_VIEWER)


def owned(c):
    return None if (c.project or {}).get("owned") else "Only for documents you uploaded"


def examinable(c):
    if c.result is None:
        return "Open the document's result to examine it"
    return None if c.result.get("examinable") else "Already examined"


def on_desk(c):
    return None if c.on("portal.document_shop_jobs") else "Select documents in My Documents"


def desk_view(c):
    return c.args.get("view") or "active"


def on_active_desk(c):
    return on_desk(c) or (None if desk_view(c) == "active" else "Available in My Documents")


def on_recovery_desk(c):
    return on_desk(c) or (None if desk_view(c) in ("archive", "trash") else "Open Archive or Recently Deleted")


def two_sources(c):
    ids = (c.project or {}).get("source_ids") or []
    return None if len(ids) >= 2 else "Needs two documents in this project"


def U(endpoint, **values):
    return lambda c: c.url_for(endpoint, **{k: (v(c) if callable(v) else v)
                                            for k, v in values.items()})


def soon(cid, family, label):
    return Command(cid, family, label, not_yet=True)


COMMANDS = [
    # FILE -------------------------------------------------------------------
    Command("file.new_project", "FILE", "New Project…", href=U("portal.upload"),
            needs=_need(staff, admin), current=lambda c: c.on("portal.upload")),
    Command("file.upload", "FILE", "Document Upload…", href=U("portal.document_shop_intake"),
            needs=lambda c: None if (c.admin or c.customer) else "Not permitted for this account",
            current=lambda c: c.on("portal.document_shop_intake")),
    Command("file.open_project", "FILE", "Open Project…",
            # With a project open: the chooser scoped to its environment, with it
            # marked current - the classic File > Open Project's scoping, kept.
            href=lambda c: (c.url_for("portal.choose_project", current=c.pid,
                                      environment=(c.project or {}).get("environment"))
                            if c.kind == "project" else c.url_for("portal.choose_project")),
            needs=staff, current=lambda c: c.on("portal.choose_project")),
    Command("file.my_documents", "FILE", "Open My Documents", href=U("portal.document_shop_jobs"),
            current=lambda c: c.on("portal.document_shop_jobs") and desk_view(c) == "active"),
    Command("file.archive", "FILE", "Open Archive", href=U("portal.document_shop_jobs", view="archive"),
            current=lambda c: c.on("portal.document_shop_jobs") and desk_view(c) == "archive"),
    Command("file.trash", "FILE", "Open Recently Deleted", href=U("portal.document_shop_jobs", view="trash"),
            current=lambda c: c.on("portal.document_shop_jobs") and desk_view(c) == "trash"),
    Command("file.export_project", "FILE", "Export Project (Word)",
            href=U("workspace.export_document", project_id=lambda c: c.pid, kind="project", export_format="docx"),
            needs=project_kind),
    Command("file.export_rfi", "FILE", "Export RFI", href=U("workspace.export_rfi", project_id=lambda c: c.pid),
            needs=project_kind),
    Command("file.print", "FILE", "Print", proxy="doc-print", needs=viewer),
    # EDIT -------------------------------------------------------------------
    Command("edit.undo", "EDIT", "Undo", proxy="doc-annotate-undo", needs=viewer),
    Command("edit.redo", "EDIT", "Redo", proxy="doc-annotate-redo", needs=viewer),
    Command("edit.delete_annotation", "EDIT", "Delete Annotation", proxy="doc-annotate-delete", needs=viewer),
    Command("edit.select_all", "EDIT", "Select All Documents", proxy="document-select-all",
            needs=lambda c: None if c.on("portal.document_shop_jobs") else "Available in My Documents"),
    Command("edit.clear_selection", "EDIT", "Clear Selection", proxy="document-clear-selection",
            needs=lambda c: None if c.on("portal.document_shop_jobs") else "Available in My Documents"),
    Command("edit.archive_selected", "EDIT", "Archive Selected", capability="ARCHIVE_ITEMS",
            bulk=lambda c: registry_bulk("ARCHIVE_ITEMS"), needs=on_active_desk),
    Command("edit.delete_selected", "EDIT", "Delete Selected…", capability="DELETE_ITEMS",
            bulk=lambda c: registry_bulk("DELETE_ITEMS"), needs=on_active_desk),
    Command("edit.restore_selected", "EDIT", "Restore Selected", bulk=lambda c: "restore", needs=on_recovery_desk),
    # VIEW -------------------------------------------------------------------
    Command("view.conversation", "VIEW", "Project Conversation",
            href=U("workspace.show_workspace", project_id=lambda c: c.pid), needs=project_kind,
            current=lambda c: c.workspace_view(None) and not any(
                c.args.get(k) for k in ("source", "case", "work_product", "compare_a"))),
    Command("view.zoom_in", "VIEW", "Zoom In", proxy="doc-zoom-in", needs=viewer),
    Command("view.zoom_out", "VIEW", "Zoom Out", proxy="doc-zoom-out", needs=viewer),
    Command("view.fit_width", "VIEW", "Fit Width", proxy="doc-fit-width", needs=viewer),
    # Density is a SETTING, not an operation: it never claims "current". Set in
    # the browser (master_workspace.js) from the page's own URL, so the server
    # never echoes request parameters back into the page.
    Command("view.work_density", "VIEW", "Work Density", action="set-density-work"),
    Command("view.inspect_density", "VIEW", "Inspect Density", action="set-density-inspect"),
    Command("view.full_screen", "VIEW", "Full Screen", action="toggle-fullscreen"),
    soon("view.rulers", "VIEW", "Show Rulers"),
    # DOCUMENT ---------------------------------------------------------------
    Command("document.view", "DOCUMENT", "View Document",
            href=lambda c: (c.url_for("portal.document_shop_result", project_id=c.pid) if c.kind == "documents"
                            else c.url_for("workspace.show_workspace", project_id=c.pid, source=c.sid)),
            needs=lambda c: documents_kind(c) if c.kind == "documents" else document(c),
            current=lambda c: c.on("portal.document_shop_result") or (
                c.on("workspace.show_workspace") and bool(c.args.get("source")))),
    Command("document.open_original", "DOCUMENT", "Open Original",
            href=U("workspace.source_file", project_id=lambda c: c.pid, source_id=lambda c: c.sid, download=1),
            needs=document),
    Command("document.examine", "DOCUMENT", "Examine",
            post=U("workspace.examine_document", project_id=lambda c: c.pid),
            needs=_need(documents_kind, examinable)),
    Command("document.reanalyze", "DOCUMENT", "Re-analyze", capability="REANALYZE_ITEMS",
            post=lambda c: None if c.on("portal.document_shop_jobs") else c.url_for("portal.document_shop_bulk"),
            fields=lambda c: {"project_id": c.pid, "action": registry_bulk("REANALYZE_ITEMS"),
                              "request_id": uuid.uuid4().hex},
            bulk=lambda c: registry_bulk("REANALYZE_ITEMS") if c.on("portal.document_shop_jobs") else None,
            needs=lambda c: on_active_desk(c) if c.on("portal.document_shop_jobs") else _need(documents_kind, owned)(c)),
    Command("document.remove", "DOCUMENT", "Delete Document…",
            post=lambda c: (c.url_for("portal.document_shop_remove_source", project_id=c.pid, source_id=c.sid)
                            if c.kind == "documents"
                            else c.url_for("workspace.remove_document_route", project_id=c.pid, source_id=c.sid)),
            needs=document),
    Command("document.replace", "DOCUMENT", "Replace…",
            href=U("workspace.replace_source_form", project_id=lambda c: c.pid, source_id=lambda c: c.sid),
            needs=_need(project_kind, document), current=lambda c: c.on("workspace.replace_source_form")),
    Command("document.context", "DOCUMENT", "Document Context…", action="open-document-context", needs=viewer),
    Command("document.review_source", "DOCUMENT", "Review Source (Inspect)",
            href=U("workspace.source_review", project_id=lambda c: c.pid, source_id=lambda c: c.sid),
            needs=_need(document, developer), current=lambda c: c.on("workspace.source_review")),
    soon("document.properties", "DOCUMENT", "Document Properties"),
    # DATA -------------------------------------------------------------------
    Command("data.requirements", "DATA", "Requirements",
            href=U("workspace.show_workspace", project_id=lambda c: c.pid, view="requirements"),
            needs=project_kind, current=lambda c: c.workspace_view("requirements")),
    Command("data.files", "DATA", "Project Files",
            href=U("workspace.show_workspace", project_id=lambda c: c.pid, view="files"),
            needs=project_kind, current=lambda c: c.workspace_view("files")),
    soon("data.import", "DATA", "Import Dataset"),
    # QUERY ------------------------------------------------------------------
    Command("query.search", "QUERY", "Search", href=U("portal.search_page"), needs=staff,
            current=lambda c: c.on("portal.search_page")),
    Command("query.find_in_document", "QUERY", "Find in Document", action="focus-document-search", needs=viewer),
    soon("query.saved", "QUERY", "Saved Queries"),
    # MODEL ------------------------------------------------------------------
    Command("model.planning", "MODEL", "Planning & Zoning Analysis", href=U("planning_zoning.planning_zoning"),
            needs=staff, current=lambda c: c.endpoint in (
                "planning_zoning.planning_zoning", "planning_zoning.planning_result",
                "planning_zoning.working_study", "planning_zoning.open_study")),
    Command("model.studies", "MODEL", "Planning Studies", href=U("planning_zoning.saved_studies"),
            needs=staff, current=lambda c: c.on("planning_zoning.saved_studies")),
    soon("model.scenarios", "MODEL", "Scenario Models"),
    # MARKET -----------------------------------------------------------------
    soon("market.data", "MARKET", "Market Data"),
    soon("market.comparables", "MARKET", "Comparables"),
    soon("market.indices", "MARKET", "Indices"),
    # COMPARE ----------------------------------------------------------------
    Command("compare.documents", "COMPARE", "Compare Documents",
            href=lambda c: c.url_for("workspace.show_workspace", project_id=c.pid,
                                     compare_a=(c.sid or c.project["source_ids"][0]),
                                     compare_b=next(i for i in c.project["source_ids"] if i != (c.sid or c.project["source_ids"][0]))),
            needs=_need(project_kind, two_sources),
            current=lambda c: c.on("workspace.show_workspace") and bool(c.args.get("compare_a"))),
    Command("compare.analyses", "COMPARE", "Compare Selected Analyses", capability="COMPARE_ITEMS",
            bulk=lambda c: registry_bulk("COMPARE_ITEMS"),
            needs=lambda c: on_active_desk(c) and "Select two documents in My Documents",
            current=lambda c: c.on("portal.document_shop_bulk")),
    soon("compare.revisions", "COMPARE", "Compare Revisions"),
    # CHECK ------------------------------------------------------------------
    Command("check.investigations", "CHECK", "Investigations",
            href=U("workspace.show_workspace", project_id=lambda c: c.pid, view="overview"),
            needs=project_kind, current=lambda c: c.on("workspace.show_workspace") and bool(c.args.get("case"))),
    Command("check.spin", "CHECK", "Spin", href=U("workspace.show_workspace", project_id=lambda c: c.pid, view="spin"),
            needs=project_kind, current=lambda c: c.workspace_view("spin")),
    Command("check.attention", "CHECK", "GO Attention Review",
            href=U("workspace.go_attention", project_id=lambda c: c.pid),
            needs=_need(project_kind, admin), current=lambda c: c.on("workspace.go_attention")),
    soon("check.code", "CHECK", "Code Check Suite"),
    # CREATE -----------------------------------------------------------------
    Command("create.investigation", "CREATE", "New Investigation",
            href=U("workspace.show_workspace", project_id=lambda c: c.pid, view="new-case"),
            needs=project_kind, current=lambda c: c.workspace_view("new-case")),
    Command("create.work_product", "CREATE", "Work Products",
            href=U("workspace.show_workspace", project_id=lambda c: c.pid),
            needs=project_kind,
            current=lambda c: c.on("workspace.show_workspace") and bool(c.args.get("work_product"))),
    soon("create.report", "CREATE", "Report Builder"),
    # PROJECT ----------------------------------------------------------------
    Command("project.overview", "PROJECT", "Overview",
            href=lambda c: (c.url_for("portal.document_shop_result", project_id=c.pid) if c.kind == "documents"
                            else c.url_for("workspace.show_workspace", project_id=c.pid, view="overview")),
            needs=project, current=lambda c: c.workspace_view("overview")),
    Command("project.access", "PROJECT", "Access Passes",
            href=U("project_manage.manage_access", project_id=lambda c: c.pid),
            needs=project_kind, current=lambda c: c.on("project_manage.manage_access")),
    Command("project.data", "PROJECT", "Project Data Management",
            # Carries the open project forward, as the classic menu did, so the
            # page identifies which project's evidence Add/Archive acts on.
            href=lambda c: c.url_for("portal.reset_project_data", project_id=c.pid if c.kind == "project" else None),
            needs=admin, current=lambda c: c.on("portal.reset_project_data")),
    soon("project.members", "PROJECT", "Members"),
    # PORTFOLIO --------------------------------------------------------------
    Command("portfolio.all", "PORTFOLIO", "All Projects", href=U("portal.projects_list"), needs=staff,
            current=lambda c: c.on("portal.projects_list")),
    Command("portfolio.removed", "PORTFOLIO", "Removed Projects", href=U("portal.removed_projects"),
            needs=staff, current=lambda c: c.on("portal.removed_projects")),
    soon("portfolio.analytics", "PORTFOLIO", "Portfolio Analytics"),
    # DEAL -------------------------------------------------------------------
    Command("deal.publish", "DEAL", "Publish Procurement Package…", action="open-publish-panel",
            needs=_need(project_kind, admin, lambda c: None if c.can_publish
                        else "Only an Owner project not yet published")),
    soon("deal.pipeline", "DEAL", "Deal Pipeline"),
    # RELATIONSHIPS ----------------------------------------------------------
    Command("relationships.drawing", "RELATIONSHIPS", "Drawing Understanding",
            href=U("workspace.drawing_understanding_review", project_id=lambda c: c.pid, source_id=lambda c: c.sid),
            needs=_need(project_kind, document, admin),
            current=lambda c: c.on("workspace.drawing_understanding_review")),
    soon("relationships.map", "RELATIONSHIPS", "Relationship Map"),
    # TRACE ------------------------------------------------------------------
    Command("trace.history", "TRACE", "Analysis History",
            href=U("portal.document_shop_analysis_history", project_id=lambda c: c.pid),
            needs=documents_kind, current=lambda c: c.on("portal.document_shop_analysis_history")),
    Command("trace.kernel", "TRACE", "Evidence Kernel (Inspect)",
            href=U("workspace.kernel_mapping", project_id=lambda c: c.pid),
            needs=_need(project_kind, developer), current=lambda c: c.on("workspace.kernel_mapping")),
    soon("trace.lineage", "TRACE", "Lineage Graph"),
    # TOOLS ------------------------------------------------------------------
    Command("tools.text", "TOOLS", "Text Annotation", proxy="doc-annotate-text", needs=viewer),
    Command("tools.highlight", "TOOLS", "Highlight", proxy="doc-annotate-highlight", needs=viewer),
    Command("tools.draw", "TOOLS", "Draw", proxy="doc-annotate-ink", needs=viewer),
    Command("tools.capture", "TOOLS", "Capture Drawing Region", proxy="doc-region-select", needs=viewer),
    Command("tools.developer", "TOOLS", "Developer Tools", href=U("portal.developer_tools"),
            needs=developer, current=lambda c: c.on("portal.developer_tools")),
    Command("tools.diagnostics", "TOOLS", "Diagnostics", href=U("portal.list_diagnostics"),
            needs=admin, current=lambda c: c.on("portal.list_diagnostics")),
    Command("tools.security", "TOOLS", "Security", href=U("security.department_home"),
            needs=admin, current=lambda c: c.on("security.department_home")),
    Command("tools.operations", "TOOLS", "Operations", href=U("operations.department_home"),
            needs=admin, current=lambda c: c.on("operations.department_home")),
    soon("tools.takeoff", "TOOLS", "Linear / Area Takeoff"),
    soon("tools.sheet_diff", "TOOLS", "Sheet Diff"),
    # WINDOW -----------------------------------------------------------------
    Command("window.hidden_tabs", "WINDOW", "Show Hidden Tabs", action="open-hidden-tabs", needs=viewer),
    Command("window.close_tabs", "WINDOW", "Close All Tabs", action="close-all-tabs", needs=viewer),
    Command("window.split", "WINDOW", "Split / Compare", proxy="toolbox-compare-btn", needs=viewer),
    soon("window.reset_layout", "WINDOW", "Reset Layout"),
    # HELP -------------------------------------------------------------------
    Command("help.centre", "HELP", "Help Centre", href=U("help_center.index"),
            current=lambda c: c.on("help_center.index", "help_center.guide")),
    Command("help.shortcuts", "HELP", "Keyboard Shortcuts", action="open-keyboard-shortcuts"),
]

assert tuple(dict.fromkeys(c.family for c in COMMANDS)) == FAMILIES, "a family is empty or out of order"
assert len({c.id for c in COMMANDS}) == len(COMMANDS), "duplicate command id"


def application_destinations() -> list:
    """GOPILOT CORE step 1: the places a person can be SENT without any project
    open - read from this registry, never restated.

    A command qualifies when it navigates (`href`), is built (not `not_yet`), and
    its own `needs` rule, asked with nothing open, raises no project, document or
    viewer requirement. Who may then OPEN it is still the route's gate; admin-
    and developer-only reasons do not disqualify, because classifying where a
    turn points is not authorizing it."""
    empty = Ctx(identity={}, endpoint="", args={}, admin=False, developer=False,
                customer=False, username=None)
    authority_only = {None, ADMIN_ONLY, DEVELOPER_ONLY}
    out = []
    for command in COMMANDS:
        if command.href is None or command.not_yet:
            continue
        try:
            reason = command.needs(empty) if command.needs else None
        except Exception:  # a rule that cannot even be asked without context needs it
            continue
        if reason in authority_only:
            out.append({"id": command.id, "family": command.family, "label": command.label})
    return out


def resolve_master_menu(ctx: Ctx) -> dict:
    """All 19 families, every command resolved to active / grey / current.

    Returns {"families": [...], "operation": None | {"family", "label"}}.
    A grey item has `href`/`post` of None - its route is never built.
    """
    families = {name: [] for name in FAMILIES}
    operation = None
    for command in COMMANDS:
        item = {"id": command.id, "label": command.label, "state": "active",
                "reason": None, "href": None, "post": None, "fields": None,
                "proxy": None, "action": None, "bulk": None}
        reason = NOT_YET if command.not_yet else (command.needs(ctx) if command.needs else None)
        if reason:
            item.update(state="grey", reason=reason)
        else:
            if command.href:
                item["href"] = command.href(ctx)
            if command.post:
                item["post"] = command.post(ctx)
                item["fields"] = (command.fields(ctx) if command.fields else {}) if item["post"] else None
            if command.bulk:
                item["bulk"] = command.bulk(ctx)
            item["proxy"], item["action"] = command.proxy, command.action
            if command.current and command.current(ctx):
                item["state"] = "current"
                if operation is None:
                    operation = {"family": command.family, "label": command.label}
        families[command.family].append(item)
    return {
        "families": [{"name": name, "items": families[name],
                      "current": bool(operation and operation["family"] == name)}
                     for name in FAMILIES],
        "operation": operation,
    }
