"""
CLAUDE-COMPOSER-EVIDENCE-JOIN-01 - the photo turn joins the shared spine.

Product Owner principle, accepted:

    examine before extending; say what the available evidence does and does not
    demonstrate; reason in prose and dialogue; identify the next most
    informative evidence when needed.

WHY THE JOIN RATHER THAN TEACHING THE PHOTO PATH

_composer_photo_turn was a second, parallel reasoning implementation: its own
system prompt, its own JSON shape, its own model call - receiving the photo and
NOTHING ELSE. No requirements, no source excerpts, no evidence items. A reviewer
photographing a condition got an answer grounded only in pixels, while the same
question typed without a photo was answered against the whole project.

Teaching that path to examine evidence would have required writing the principle
twice, and the moment it lives in a photo-specific path it becomes
"image present -> compare" - the brittle keyword shortcut this work exists to
avoid. Joining means the principle is written ONCE, in the shared contract, and
applies to both modalities because there is only one reasoning core.

WHAT THESE TESTS PROTECT

Most of them assert PRESERVATION, because the risk here is not that the join
fails loudly - it is that a side effect quietly stops firing. Every behaviour the
photo wrapper had before must still be there, in the same order, outside the
reasoning core.

The text path is asserted UNCHANGED: the image parameters default to None, so a
text turn's call is what it always was.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ROUTES = _REPO_ROOT / "routes" / "workspace.py"
_SPINE = _REPO_ROOT / "services" / "conversational_turn.py"

ROUTES_SRC = _ROUTES.read_text(encoding="utf-8")
SPINE_SRC = _SPINE.read_text(encoding="utf-8")


def _strip_prose(source: str) -> str:
    """Drop docstrings and comments before any absence assertion.

    This file's own explanations name the very things it asserts are absent -
    "_admit_residual", "raise", "bytes" - so scanning raw source lets the
    explanation of a prohibition satisfy the test for it. That has happened
    repeatedly in this repository; every negative assertion below goes through
    here.
    """
    without_docstrings = re.sub(r'"""[\s\S]*?"""', "", source)
    return re.sub(r"#[^\n]*", "", without_docstrings)


def _function_body(source: str, name: str) -> str:
    lines = source.splitlines()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(f"{name} not found")


PHOTO_TURN = _function_body(ROUTES_SRC, "_composer_photo_turn")
PHOTO_TURN_CODE = _strip_prose(PHOTO_TURN)


class TheParallelImplementationIsGoneTests(unittest.TestCase):
    def test_the_photo_turn_no_longer_calls_the_model_itself(self):
        self.assertNotIn("call_llm_json", PHOTO_TURN)

    def test_it_calls_the_shared_spine(self):
        self.assertIn("run_conversational_turn(", PHOTO_TURN)
        self.assertIn("build_context_envelope(", PHOTO_TURN)

    def test_it_carries_its_own_system_prompt_no_longer(self):
        # A second contract is exactly what the join removed.
        self.assertNotIn("system_prompt = (", PHOTO_TURN)

    def test_it_does_not_route_through_admit_residual(self):
        # _admit_residual declines when a project has no active Sources. A photo
        # question in a project with no documents must keep working, so the
        # spine is called directly.
        self.assertNotIn("_admit_residual", PHOTO_TURN_CODE)


class EveryWrapperBehaviourSurvivesTests(unittest.TestCase):
    """The real risk: a side effect quietly stops firing."""

    def test_the_external_ai_gate_still_runs(self):
        self.assertIn("_evaluate_security_action", PHOTO_TURN)
        self.assertIn("ACTION_EXTERNAL_AI_REQUEST", PHOTO_TURN)

    def test_the_gate_runs_before_any_reasoning(self):
        self.assertLess(
            PHOTO_TURN.index("_evaluate_security_action"),
            PHOTO_TURN.index("run_conversational_turn("),
            "policy is evaluated after reasoning",
        )

    def test_the_size_ceiling_still_runs_before_the_gate(self):
        self.assertLess(PHOTO_TURN.index("_MAX_IMAGE_BYTES"),
                        PHOTO_TURN.index("_evaluate_security_action"))

    def test_photo_persistence_survives(self):
        self.assertIn("register_eye_capture", PHOTO_TURN)
        self.assertIn("attach_source_to_case", PHOTO_TURN)

    def test_make_a_new_q_survives(self):
        self.assertIn("create_case", PHOTO_TURN)
        self.assertIn("_asked_for_a_new_investigation", PHOTO_TURN)

    def test_add_to_this_q_survives(self):
        self.assertIn("_asked_to_add_to_this_investigation", PHOTO_TURN)

    def test_the_human_message_is_still_recorded(self):
        self.assertIn("store.add_message", PHOTO_TURN)

    def test_all_three_branches_still_exist(self):
        self.assertIn("if wants_add:", PHOTO_TURN)
        self.assertIn("if not wants_new:", PHOTO_TURN)
        self.assertIn('return True, new_case["id"]', PHOTO_TURN)


class CandidateNamingMovedButSurvivesTests(unittest.TestCase):
    def test_naming_still_happens(self):
        self.assertIn("_propose_capture_names", ROUTES_SRC)
        self.assertIn("def _propose_capture_names", ROUTES_SRC)

    def test_it_runs_only_where_it_is_used(self):
        # It was requested on EVERY photo turn and discarded in two branches out
        # of three. It belongs in the branch that creates a Q.
        self.assertEqual(PHOTO_TURN.count("_propose_capture_names("), 1)
        naming_at = PHOTO_TURN.index("_propose_capture_names(")
        new_q_at = PHOTO_TURN.index("if not wants_new:")
        self.assertGreater(naming_at, new_q_at, "naming is not inside the new-Q branch")

    def test_it_is_not_in_the_shared_contract(self):
        # Putting names in the spine's schema would rebuild the parallel
        # multimodal contract this stage just removed.
        self.assertNotIn("proposed_names", SPINE_SRC)

    def test_a_naming_failure_cannot_break_a_capture(self):
        helper = _function_body(ROUTES_SRC, "_propose_capture_names")
        self.assertIn("return []", helper)
        self.assertNotIn("raise", _strip_prose(helper))

    def test_a_name_is_never_a_diagnosis(self):
        helper = _function_body(ROUTES_SRC, "_propose_capture_names")
        self.assertIn("never an identification", helper)
        self.assertIn("do not name a", helper)


class TheTextPathIsUnchangedTests(unittest.TestCase):
    def test_the_image_parameters_are_optional(self):
        signature = SPINE_SRC[SPINE_SRC.index("def run_conversational_turn("):]
        signature = signature[:signature.index(") ->")]
        self.assertIn("image_base64: Optional[str] = None", signature)
        self.assertIn("image_media_type: Optional[str] = None", signature)

    def test_the_text_caller_passes_no_image(self):
        interpreter = (_REPO_ROOT / "services" / "conversation_interpreter.py").read_text(encoding="utf-8")
        call = interpreter[interpreter.index("result = run_conversational_turn("):]
        call = call[:call.index(")") + 1]
        self.assertNotIn("image_base64", call)

    def test_the_envelope_field_defaults_to_absent(self):
        envelope = SPINE_SRC[SPINE_SRC.index("class ContextEnvelope:"):]
        envelope = envelope[:envelope.index("def build_context_envelope")]
        self.assertIn("attached_image: Optional[dict] = None", envelope)


class TheImageIsContextNotASchemaTests(unittest.TestCase):
    def test_the_envelope_carries_provenance_not_bytes(self):
        envelope = SPINE_SRC[SPINE_SRC.index("class ContextEnvelope:"):]
        envelope = envelope[:envelope.index("def build_context_envelope")]
        for token in ("base64", "bytes", "data_url"):
            self.assertNotIn(token, _strip_prose(envelope), token)

    def test_the_bytes_go_straight_to_the_gateway(self):
        turn = _function_body(SPINE_SRC, "run_conversational_turn")
        self.assertIn("image_base64=image_base64", turn)
        self.assertIn("image_media_type=image_media_type", turn)

    def test_an_attached_photo_is_declared_temporary_evidence(self):
        builder = _function_body(SPINE_SRC, "_build_conversational_turn_prompt")
        self.assertIn("attached_image", builder)
        self.assertIn("not a governed project", builder)

    def test_the_photo_turn_supplies_that_provenance(self):
        self.assertIn("attached_image", PHOTO_TURN)
        self.assertIn("provenance", PHOTO_TURN)


class TheExaminationPrincipleIsWrittenOnceTests(unittest.TestCase):
    """Behavioural, not schematic - and in the shared contract only."""

    def setUp(self):
        from services.conversational_turn import CONVERSATIONAL_TURN_BEHAVIORAL_CONTRACT
        self.contract = CONVERSATIONAL_TURN_BEHAVIORAL_CONTRACT

    def test_examine_before_extending_is_instructed(self):
        self.assertIn("EXAMINE FIRST", self.contract)
        self.assertIn("before extending", self.contract)

    def test_the_next_evidence_move_is_instructed(self):
        self.assertIn("what you would", self.contract)
        self.assertIn("look at next", self.contract)

    def test_calibration_cuts_both_ways(self):
        # "Say no more weakly and no more strongly than the evidence warrants."
        # Reflexive hedging is a failure mode too, not just overclaiming.
        self.assertIn("no more weakly and no more strongly", self.contract)
        self.assertIn("reflexive hedging", self.contract)

    def test_no_modality_is_self_interpreting(self):
        self.assertIn("self-interpreting", self.contract)
        self.assertIn("without establishing its cause", self.contract)

    def test_it_must_not_become_a_checklist(self):
        self.assertIn("labelled verdicts", self.contract)
        self.assertIn("not a form", self.contract)

    def test_the_principle_lives_in_exactly_one_place(self):
        # If it appears in the photo path too, the join achieved nothing.
        self.assertNotIn("EXAMINE FIRST", ROUTES_SRC)

    def test_no_verdict_vocabulary_leaked_into_the_contract(self):
        # Spin's evidence_sufficiency labels are internal to Spin and must not
        # surface as conversational language.
        for label in ("directly_supportable", "visual_vector_supportable",
                      "evidence_type_insufficient"):
            self.assertNotIn(label, self.contract, label)


class AuthorityIsUnchangedTests(unittest.TestCase):
    def test_the_spine_still_refuses_to_execute(self):
        turn = _function_body(SPINE_SRC, "run_conversational_turn")
        for token in ("store.save", "create_case", "add_message", "attach_source"):
            self.assertNotIn(token, turn, token)

    def test_visual_inference_does_not_become_a_finding(self):
        # The photo path creates a Case and a Source when asked; it must still
        # never create a Finding.
        self.assertNotIn("create_finding", PHOTO_TURN)
        self.assertNotIn("record_finding", PHOTO_TURN)

    def test_the_contract_still_forbids_self_issuing_governed_records(self):
        from services.conversational_turn import CONVERSATIONAL_TURN_BEHAVIORAL_CONTRACT as c
        self.assertIn("you never create or issue one yourself", c)


if __name__ == "__main__":
    unittest.main()
