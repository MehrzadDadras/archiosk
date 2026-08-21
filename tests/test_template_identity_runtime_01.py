import unittest

from services.template_identity import (
    identity_for_template_id,
    template_identity_for_endpoint,
)


class RuntimeTemplateIdentityTests(unittest.TestCase):
    def test_explicit_governed_endpoints_resolve_table_driven(self):
        expected = {
            "portal.index": ("TPL-001", "Home"),
            "workspace.show_workspace": ("TPL-005", "Project Workspace"),
            "portal.developer_tools": ("TPL-012", "Developer Tools"),
            "portal.login": ("TPL-015", "Authentication"),
            "portal.explore": ("TPL-016", "Public landing / explore"),
            "portal.removed_projects": ("TPL-014", "Archive / removed-project management"),
            "portal.upload": ("TPL-017", "New project / upload"),
            "portal.global_search": ("TPL-018", "Search / operations / about"),
            "operations.department_home": ("TPL-018", "Search / operations / about"),
            "portal.about": ("TPL-018", "Search / operations / about"),
        }
        for endpoint, (template_id, name) in expected.items():
            with self.subTest(endpoint=endpoint):
                identity = template_identity_for_endpoint(endpoint)
                self.assertEqual((identity["template_id"], identity["name"]), (template_id, name))
                self.assertEqual(identity["governance_source"], "governance/current/page-surface-template-inventory.md")

    def test_tpl018_variant_is_descriptive_not_a_new_identity(self):
        identity = template_identity_for_endpoint("portal.global_search")
        self.assertEqual(identity["template_id"], "TPL-018")
        self.assertEqual(identity["variant"], "Search")
        self.assertEqual(identity_for_template_id("TPL-018")["template_id"], "TPL-018")
        self.assertNotEqual(identity_for_template_id("TPL-018").get("variant"), "Search")

    def test_unmapped_endpoints_do_not_receive_invented_identity(self):
        for endpoint in ("portal.choose_project", "workspace.publish_procurement_package_route", "made_up.endpoint"):
            with self.subTest(endpoint=endpoint):
                self.assertIsNone(template_identity_for_endpoint(endpoint))

    def test_nested_workspace_identity_remains_parent_tpl(self):
        identity = template_identity_for_endpoint("workspace.show_workspace")
        self.assertEqual(identity["template_id"], "TPL-005")
        self.assertNotIn("layout_id", identity)
        self.assertNotIn("nested_template_id", identity)


if __name__ == "__main__":
    unittest.main()
