"""Governed page/surface identities for runtime application context.

The inventory in ``governance/current/page-surface-template-inventory.md`` is
the source of truth.  This small allow-listed projection maps routed surfaces
to the existing inventory IDs; it is intentionally not a second inventory.
"""

from __future__ import annotations


# This is an explicit route-semantics projection, not a second page inventory.
# Keep entries only where the Page/Surface Inventory establishes the route ↔
# TPL relationship. Nested workspace states remain under TPL-005 and are not
# guessed from URL or template names here.
_GOVERNANCE_SOURCE = "governance/current/page-surface-template-inventory.md"

TEMPLATE_SURFACES = {
    "portal.index": {"template_id": "TPL-001", "name": "Home"},
    "workspace.show_workspace": {"template_id": "TPL-005", "name": "Project Workspace"},
    "portal.developer_tools": {"template_id": "TPL-012", "name": "Developer Tools"},
    "portal.login": {"template_id": "TPL-015", "name": "Authentication"},
    "portal.forgot_password": {"template_id": "TPL-015", "name": "Authentication"},
    "portal.reset_password": {"template_id": "TPL-015", "name": "Authentication"},
    "portal.explore": {"template_id": "TPL-016", "name": "Public landing / explore"},
    "portal.removed_projects": {"template_id": "TPL-014", "name": "Archive / removed-project management"},
    "portal.upload": {"template_id": "TPL-017", "name": "New project / upload"},
    "portal.upload_confirm": {"template_id": "TPL-017", "name": "New project / upload"},
    # TPL-018 is an existing governed utility family. The route-level variant
    # is descriptive context only; it does not create a new TPL identity.
    "portal.global_search": {"template_id": "TPL-018", "name": "Search / operations / about", "variant": "Search"},
    "operations.department_home": {"template_id": "TPL-018", "name": "Search / operations / about", "variant": "Operations"},
    "portal.about": {"template_id": "TPL-018", "name": "Search / operations / about", "variant": "About"},
}


def _semantic_identity(entry: dict) -> dict:
    identity = {
        "template_id": entry["template_id"],
        "name": entry["name"],
        "governance_source": _GOVERNANCE_SOURCE,
    }
    if entry.get("variant"):
        identity["variant"] = entry["variant"]
    return identity


def template_identity_for_endpoint(endpoint: str | None) -> dict | None:
    value = TEMPLATE_SURFACES.get(endpoint or "")
    return _semantic_identity(value) if value else None


def is_known_template_id(template_id: str) -> bool:
    return template_id in {value["template_id"] for value in TEMPLATE_SURFACES.values()}


def identity_for_template_id(template_id: str) -> dict | None:
    for value in TEMPLATE_SURFACES.values():
        if value["template_id"] == template_id:
            # ID lookup intentionally returns the parent TPL identity without
            # selecting an arbitrary route variant.
            return _semantic_identity({key: value[key] for key in ("template_id", "name")})
    return None
