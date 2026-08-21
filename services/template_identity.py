"""Governed page/surface identities for Developer UI Reveal.

The inventory in ``governance/current/page-surface-template-inventory.md`` is
the source of truth.  This small allow-listed projection maps routed surfaces
to the existing inventory IDs; it is intentionally not a second inventory.
"""

from __future__ import annotations

TEMPLATE_SURFACES = {
    "portal.index": ("TPL-001", "Home"),
    "workspace.show_workspace": ("TPL-005", "Project Workspace"),
    "portal.developer_tools": ("TPL-012", "Developer Tools"),
}


def template_identity_for_endpoint(endpoint: str | None) -> dict | None:
    value = TEMPLATE_SURFACES.get(endpoint or "")
    if not value:
        return None
    template_id, name = value
    return {"template_id": template_id, "name": name}


def is_known_template_id(template_id: str) -> bool:
    return template_id in {value[0] for value in TEMPLATE_SURFACES.values()}


def identity_for_template_id(template_id: str) -> dict | None:
    for known_id, name in TEMPLATE_SURFACES.values():
        if known_id == template_id:
            return {"template_id": known_id, "name": name}
    return None
