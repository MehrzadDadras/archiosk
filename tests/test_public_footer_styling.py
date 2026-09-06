"""
The public footer must arrive styled on every surface that includes it.

WHAT WENT WRONG

`components/public_footer.html` is included by nine templates. Its CSS lived in
`project_manage.css`, which seven of them load — and the two that matter most do
not. `landing.html` extends `landing_shell.html` (landing.css only) and
`projects.html` extends `base.html` (fish_tank/tokens/main), so on the public
front door and the projects list the footer rendered with NO styling at all:
browser-default 24px <h2> headings and bare <ul> lists, stacking into large
blocks on a phone. It had been that way since the footer was integrated on
2026-08-29 and nothing failed, because no test related a component's markup to
the stylesheet that makes it legible.

That is the gap these tests close. The class of bug is not "wrong CSS" — it is
"a consumer that forgot the stylesheet", and it recurs the moment a tenth
template includes the footer.

WHY THE RULES ARE NOT IN A PAGE STYLESHEET

Loading `project_manage.css` into `base.html` would have been the smaller diff
and is wrong: it also carries `.flash-*` rules that `main.css` already defines,
so it would silently restyle every flash message in the workspace. `tokens.css`
is 221 custom properties and zero selectors; putting real rules there breaks the
one contract that file has. So the component's styles live beside the component,
following the precedent `fish_tank.css` already set.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES = _REPO_ROOT / "templates"
_CSS = _REPO_ROOT / "static" / "css"

# A template that renders the footer through a shell rather than its own <head>.
_SHELL_FOR = {
    "landing.html": "landing_shell.html",
    "projects.html": "base.html",
}


def _includes_footer(path: Path) -> bool:
    return "public_footer.html" in path.read_text(encoding="utf-8")


def _footer_consumers():
    return sorted((p for p in _TEMPLATES.rglob("*.html")
                   if p.name != "public_footer.html" and _includes_footer(p)),
                  key=lambda p: p.name)


class PublicFooterStylingTests(unittest.TestCase):

    def test_there_is_at_least_one_consumer(self):
        """Guards the guard: a rglob typo would otherwise pass everything."""
        self.assertGreaterEqual(len(_footer_consumers()), 5)

    def test_every_consumer_receives_the_footer_stylesheet(self):
        """The actual defect, asserted across all consumers at once.

        Checked through the shell where a template uses one, because that is
        where the <head> really is - asserting against the template's own text
        would have passed for landing.html while it was broken.
        """
        for template in _footer_consumers():
            shell = _SHELL_FOR.get(template.name)
            source = (_TEMPLATES / shell) if shell else template
            markup = source.read_text(encoding="utf-8")
            self.assertIn(
                "public_footer.css", markup,
                "%s renders the footer but %s never loads its stylesheet"
                % (template.name, source.name))

    def test_the_rules_live_in_exactly_one_stylesheet(self):
        """Two copies drift, and the cascade decides which wins by load order."""
        carrying = {p.name for p in _CSS.glob("*.css")
                    if ".site-footer" in p.read_text(encoding="utf-8")}
        self.assertEqual(carrying, {"public_footer.css"})

    def test_the_component_stylesheet_is_self_contained(self):
        """It must style the footer in a shell that defines no design tokens.

        landing_shell.html loads no tokens.css, so any bare var() reference here
        would resolve to nothing on the public front door - the exact surface
        this fix exists for. Every variable must carry a fallback.
        """
        css = (_CSS / "public_footer.css").read_text(encoding="utf-8")
        bare = [m.group(0) for m in re.finditer(r"var\(--[a-z0-9-]+\s*\)", css)]
        self.assertEqual(bare, [], "variable without a fallback: %s" % bare)

    def test_the_footer_still_reflows(self):
        """Preserved from the original rules, not re-derived."""
        css = (_CSS / "public_footer.css").read_text(encoding="utf-8")
        self.assertIn("auto-fit", css)
        self.assertIn("@media (max-width: 420px)", css)
        # No FIXED width anywhere - max-width is a fluid cap and is fine, which
        # the first version of this assertion got wrong by matching the 980px
        # measure and failing on correct CSS.
        fixed = re.findall(r"(?<!max-)(?<!min-)width:\s*\d+px", css)
        self.assertEqual(fixed, [], "fixed pixel width: %s" % fixed)

    def test_project_manage_no_longer_owns_footer_rules(self):
        css = (_CSS / "project_manage.css").read_text(encoding="utf-8")
        self.assertNotIn(".site-footer", css)

    def test_no_consumer_pulls_in_an_unrelated_page_stylesheet_for_this(self):
        """base.html must not have acquired project_manage.css as a shortcut.

        That was the smaller diff and the wrong fix: project_manage.css also
        defines .flash-* rules that main.css already owns, so loading it into
        the workspace shell would restyle every flash message in the app.
        """
        base = (_TEMPLATES / "base.html").read_text(encoding="utf-8")
        self.assertNotIn("project_manage.css", base)
        landing = (_TEMPLATES / "landing_shell.html").read_text(encoding="utf-8")
        self.assertNotIn("project_manage.css", landing)


if __name__ == "__main__":
    unittest.main()
