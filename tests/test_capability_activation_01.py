"""CLAUDE-SURVEY-REFERENCE-01 - a capability is not active because it exists.

    IMPLEMENTED -> REACHABLE FROM A WORKFLOW -> INVOKED UNDER THE RIGHT
    CONDITIONS -> OUTPUT CONSUMED -> SURFACED WHEN RELEVANT -> REGRESSION TESTED

WHY THIS FILE EXISTS, AND WHY 16 TEST FILES DID NOT PREVENT WHAT IT PREVENTS

`services/sheet_vision.py` is the governed drawing-vision path: six structural
properties, egress minimisation, prompt-injection containment, an audit
invariant, and an explicit Product Owner authorization from 2026-08-29. Sixteen
test files exercise it. It has never run in production, because `read_sheet` is
called by NOTHING.

Every one of those sixteen files calls it directly. A unit test CONSTRUCTS its
own caller, so it proves the capability works and says exactly nothing about
whether the product uses it. That is not a gap in those tests - it is a
different question that no unit test can ask.

The same shape produced the defect this tranche repairs. A survey image reported
"no text layer, so there was nothing to read" while 858 characters of its own
OCR text sat in evidence: the reading was INVOKED, its OUTPUT was NOT CONSUMED
by the branch that chose the sentence, and what was consumed was NOT SURFACED.
Two different links in the same chain, in the same file, both green.

THREE RULES MAKE THIS BITE RATHER THAN DECORATE:

1. ASSERT THE CALL, NOT THE IMPORT. A disconnected capability leaves a stale
   import behind, so an import check passes precisely when it matters least.

2. EVERY CAPABILITY IS DECLARED EITHER WIRED OR DORMANT. A capability in
   neither list fails this file. That is the half that catches a NEW capability
   shipping unreachable, and it is why DORMANT entries carry a reason rather
   than simply being omitted.

3. EACH STAGE IS ASSERTED SEPARATELY. `INVOKED_OUTPUT_NOT_CONSUMED` and
   `CONSUMED_NOT_SURFACED` are different failures with different fixes.
   Collapsing them into one boolean loses the diagnosis that makes the report
   actionable.

WHAT THIS FILE IS NOT. It does not wire anything, and it must never be made
green by wiring something in order to satisfy it. A capability that should be
dormant is declared DORMANT with its reason; that is a true answer, not a
failing one.
"""
from __future__ import annotations

import ast
import unittest
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

ACTIVE = "ACTIVE"
DORMANT = "DORMANT"


@dataclass(frozen=True)
class Capability:
    """One capability, and the chain it must survive to be called ACTIVE."""

    name: str
    #: module path and the symbol that IS the capability.
    entry_module: str
    entry_symbol: str
    status: str
    #: Production file that must contain a real Call to `entry_symbol`.
    invoked_by: str = ""
    #: (file, symbol) that must call the reader of this capability's output.
    consumed_by: tuple = ()
    #: (file, marker) that must mention it where a person can see it.
    surfaced_by: tuple = ()
    #: Test files that must exist and name the capability.
    tested_by: tuple = ()
    #: Required for DORMANT: why it is not wired, in one sentence.
    reason: str = ""
    notes: str = field(default="")


#: THE LEDGER. Adding a capability here is how it becomes accountable; adding
#: one to the codebase without adding it here fails `test_no_capability_is_undeclared`.
CAPABILITIES = (
    Capability(
        name="Document Upload examination",
        entry_module="services/document_examination.py", entry_symbol="build_result",
        status=ACTIVE,
        invoked_by="routes/portal.py",
        consumed_by=("services/document_conversation.py", "build_context"),
        surfaced_by=("templates/document_shop_result.html", "document-shop.result.state"),
        tested_by=("tests/test_document_shop_result_01.py",)),
    Capability(
        name="Raster fallback (local OCR)",
        entry_module="services/raster_extraction.py", entry_symbol="extract_raster_pages",
        status=ACTIVE,
        invoked_by="services/ingestion.py",
        consumed_by=("services/document_examination.py", "_recovered"),
        surfaced_by=("templates/document_shop_result.html", "document-shop.result.recovered"),
        tested_by=("tests/test_go_perception_pdf_ocr_01.py",)),
    Capability(
        name="Image intelligence (capture and crop)",
        entry_module="services/image_intelligence.py", entry_symbol="register_eye_capture",
        status=ACTIVE,
        invoked_by="routes/api.py",
        tested_by=("tests/test_mm5_image_intelligence.py",)),
    Capability(
        name="Drawing classification (intake candidates)",
        entry_module="services/drawing_intake.py", entry_symbol="analyze_upload",
        status=ACTIVE,
        invoked_by="routes/portal.py",
        tested_by=("tests/test_mm4_drawing_intelligence.py",)),
    Capability(
        name="Visual examination (model vision over a raster)",
        entry_module="services/visual_examination.py", entry_symbol="examine",
        status=ACTIVE,
        invoked_by="services/visual_classification.py",
        consumed_by=("services/document_conversation.py", "visual_reading"),
        surfaced_by=("templates/document_shop_result.html", "document-shop.result.reference-title"),
        tested_by=("tests/test_survey_reference_01.py",)),
    Capability(
        name="Vector extraction (local, no network)",
        entry_module="services/sheet_vision.py", entry_symbol="extract_sheet_geometry",
        status=ACTIVE,
        invoked_by="services/visual_classification.py",
        tested_by=("tests/test_survey_reference_01.py",),
        notes="Reaches engine/pdf_extractor.PDFVectorExtractor, which had no "
              "production caller at all before this tranche."),
    Capability(
        name="Vector PDF writing (geometry to a new sheet)",
        entry_module="services/survey_reference.py", entry_symbol="render_pdf",
        status=ACTIVE,
        invoked_by="services/visual_classification.py",
        surfaced_by=("templates/document_shop_result.html",
                     "document-shop.result.reference-download"),
        tested_by=("tests/test_survey_reference_01.py",)),
    Capability(
        name="Composer document context",
        entry_module="services/document_conversation.py", entry_symbol="build_context",
        status=ACTIVE,
        invoked_by="services/document_conversation.py",
        surfaced_by=("templates/document_shop_result.html", "document-shop.conversation.thread"),
        tested_by=("tests/test_document_shop_conversation_01.py",)),

    # -- DORMANT ------------------------------------------------------------
    #
    # Built, tested, and reachable from no workflow. Declared rather than
    # omitted, so that "nobody has looked at this in a while" is a fact on the
    # record instead of a silence. Product Owner, 2026-09-15: these stay DORMANT
    # until real production reachability is proven.
    Capability(
        name="Governed sheet vision (Gemini)",
        entry_module="services/sheet_vision.py", entry_symbol="read_sheet",
        status=DORMANT,
        tested_by=("tests/test_gemini_provider_01.py",),
        reason="Zero call sites repo-wide. The Gemini drawing-vision path was "
               "authorized 2026-08-29 and has never run in production; only its "
               "local, no-network half (extract_sheet_geometry) is wired."),
    Capability(
        name="Drawing segmentation",
        entry_module="services/drawing_segmentation.py", entry_symbol="segment_sheet",
        status=DORMANT,
        reason="No production caller. Title-block segmentation is exercised only "
               "by its own tests."),
    Capability(
        name="Derived view (title block, north, measurability)",
        entry_module="services/derived_view.py", entry_symbol="effective_title_block",
        status=DORMANT,
        reason="No production caller. The only non-test mention in the "
               "application is a comment in services/case_workspace.py."),
)


def _calls_in(path: Path) -> set:
    """Every function NAME called anywhere in a module.

    Deliberately name-based rather than resolved: `store.register_evidence_item`
    and a bare `examine(...)` both count, and this file's job is to notice that
    a call disappeared, not to type-check the call graph.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


def _defines(path: Path, symbol: str) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
               and n.name == symbol for n in ast.walk(tree))


class ImplementedStage(unittest.TestCase):
    """Stage 1. The capability exists where the ledger says it does."""

    def test_every_declared_entry_point_exists(self):
        for capability in CAPABILITIES:
            with self.subTest(capability.name):
                path = _REPO_ROOT / capability.entry_module
                self.assertTrue(path.is_file(), "%s is missing" % capability.entry_module)
                self.assertTrue(
                    _defines(path, capability.entry_symbol),
                    "%s does not define %s" % (capability.entry_module,
                                               capability.entry_symbol))


class InvokedStage(unittest.TestCase):
    """Stage 2-3. ACTIVE means a production module actually CALLS it."""

    def test_every_active_capability_is_called_from_production(self):
        for capability in CAPABILITIES:
            if capability.status != ACTIVE or not capability.invoked_by:
                continue
            with self.subTest(capability.name):
                caller = _REPO_ROOT / capability.invoked_by
                self.assertTrue(caller.is_file(),
                                "%s is missing" % capability.invoked_by)
                self.assertIn(
                    capability.entry_symbol, _calls_in(caller),
                    "%s is declared ACTIVE but %s contains no call to %s() - "
                    "an import alone is exactly what a disconnected capability "
                    "leaves behind"
                    % (capability.name, capability.invoked_by, capability.entry_symbol))

    def test_dormant_capabilities_are_honestly_dormant(self):
        """A DORMANT entry that HAS acquired a production caller is also a
        failure: the ledger would be telling the Product Owner something untrue
        in the direction that matters least but lies most."""
        production = [p for p in (list((_REPO_ROOT / "services").glob("*.py"))
                                  + list((_REPO_ROOT / "routes").glob("*.py")))]
        for capability in CAPABILITIES:
            if capability.status != DORMANT:
                continue
            with self.subTest(capability.name):
                self.assertTrue(capability.reason,
                                "a DORMANT capability must say why")
                callers = [p.name for p in production
                           if p.name != Path(capability.entry_module).name
                           and capability.entry_symbol in _calls_in(p)]
                self.assertEqual(
                    callers, [],
                    "%s is declared DORMANT but is called from %s - promote it "
                    "in the ledger and prove the rest of its chain"
                    % (capability.name, callers))


class ConsumedAndSurfacedStages(unittest.TestCase):
    """Stage 4-5. Output reaching a consumer, and a person."""

    def test_declared_consumers_reference_the_capability(self):
        for capability in CAPABILITIES:
            if not capability.consumed_by:
                continue
            path, symbol = capability.consumed_by
            with self.subTest(capability.name):
                target = _REPO_ROOT / path
                self.assertTrue(target.is_file(), "%s is missing" % path)
                source = target.read_text(encoding="utf-8")
                self.assertIn(symbol, source,
                              "%s no longer consumes %s"
                              % (path, capability.name))

    def test_declared_surfaces_still_render_the_capability(self):
        for capability in CAPABILITIES:
            if not capability.surfaced_by:
                continue
            path, marker = capability.surfaced_by
            with self.subTest(capability.name):
                target = _REPO_ROOT / path
                self.assertTrue(target.is_file(), "%s is missing" % path)
                self.assertIn(marker, target.read_text(encoding="utf-8"),
                              "%s is consumed but no longer surfaced in %s"
                              % (capability.name, path))


class RegressionTestedStage(unittest.TestCase):
    """Stage 6. Something end-to-end actually covers it."""

    def test_every_declared_test_file_exists(self):
        for capability in CAPABILITIES:
            for relative in capability.tested_by:
                with self.subTest("%s -> %s" % (capability.name, relative)):
                    self.assertTrue((_REPO_ROOT / relative).is_file(),
                                    "%s names a test file that does not exist: %s"
                                    % (capability.name, relative))


class LedgerCompleteness(unittest.TestCase):
    """The half that catches a capability shipping unreachable and unnoticed."""

    #: Modules whose whole purpose is a capability someone could disconnect.
    #: Adding one here without a ledger row is the failure this class exists for.
    ACCOUNTABLE_MODULES = (
        "services/document_examination.py",
        "services/raster_extraction.py",
        "services/image_intelligence.py",
        "services/drawing_intake.py",
        "services/visual_examination.py",
        "services/sheet_vision.py",
        "services/survey_reference.py",
        "services/document_conversation.py",
        "services/drawing_segmentation.py",
        "services/derived_view.py",
    )

    def test_no_accountable_module_is_undeclared(self):
        declared = {c.entry_module for c in CAPABILITIES}
        for module in self.ACCOUNTABLE_MODULES:
            with self.subTest(module):
                self.assertIn(
                    module, declared,
                    "%s implements a capability with no row in CAPABILITIES - "
                    "declare it ACTIVE with its chain, or DORMANT with a reason"
                    % module)

    def test_every_capability_declares_a_known_status(self):
        for capability in CAPABILITIES:
            with self.subTest(capability.name):
                self.assertIn(capability.status, (ACTIVE, DORMANT))
                if capability.status == ACTIVE:
                    self.assertTrue(
                        capability.invoked_by,
                        "%s is ACTIVE but names no production caller - ACTIVE "
                        "is a claim about reachability, not about existing"
                        % capability.name)


if __name__ == "__main__":
    unittest.main()
