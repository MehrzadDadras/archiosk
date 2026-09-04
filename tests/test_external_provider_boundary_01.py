"""
What may leave this deployment, and through which door.

WHY THIS FILE EXISTS

`test_voice_optin_and_mic_cue_01` and `test_landing_simplify_01` guard the
speech prohibition by scanning `static/js` for `speechSynthesis` and
`SpeechSynthesisUtterance`. A real piece of work exposed what that cannot
see (see `governance/specified-unbuilt/voice-output-read-aloud.md`):

  - a browser-local read-aloud path, no network, no dependency - CAUGHT;
  - a server route POSTing governed project text to OpenAI's speech API -
    NOT caught, because it contains neither string.

The guard caught the harmless half and was silent on the egress. Deleting
the local half alone would have turned the suite green with project
evidence still shipping to a third party.

So these tests do not look for a browser API. They look for the two things
that actually carry risk: an outbound audio/speech-synthesis call, and a
provider SDK reached outside a declared door.

WHERE THE CATCH ACTUALLY LANDS, STATED HONESTLY

Checked against the shelved work rather than assumed: `services/tts.py` is
caught three times over (`audio.speech`, `speech.create`, `tts-1`) plus its
undeclared `openai` import. The ROUTE that called it is NOT caught - it
names no endpoint and imports no SDK, only `create_studio_speech`.

That is the intended shape, not a hole. Egress has to live in whatever
actually reaches the provider, and that is what these patterns look for; a
route calling a service that does not exist fails at import. Naming the
shelved helper here instead would over-fit the guard to one deleted symbol
and miss the next one spelled differently.

WHAT THIS DOES NOT DO

It does not restate the speech prohibition - that stays with
`CLAUDE-MOBILE-Q-TRIAL-01` and its own tests, unamended. A future Device
Voice increment would narrow THOSE guards; it would still have to satisfy
these, because local synthesis has no egress and would trip nothing here.

Source-level, deliberately. These are structural facts about what the code
can reach, checkable without running it or holding a credential.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# Server-side code that could reach an external boundary. `static/` is
# excluded on purpose: the client cannot hold a provider credential, and the
# existing speech tests already own the browser surface.
_SCANNED_DIRS = ("services", "routes", "tools")
_SCANNED_FILES = ("app.py", "config.py")

# Provider SDKs this deployment declares in requirements.txt. Anything else
# is undeclared by construction - it cannot be installed, so importing it is
# either dead code or an intent to add a dependency without saying so.
_DECLARED_SDKS = {"anthropic", "google"}

# Every module allowed to touch a provider SDK directly, and why.
#
# NOT a list of "files that import anthropic" - it is the reviewed set of
# doors to an external boundary. `llm_gateway` is the intended one; the other
# three are the pre-existing copies its own docstring records it was
# "extracted from three duplicated copies of the same client-setup/
# error-handling shape" without finishing the migration. They are grandfathered
# so this guard reflects the tree honestly rather than failing on day one -
# not endorsed, and a good candidate for later convergence.
_PROVIDER_DOORS = {
    "services/llm_gateway.py",
    "services/bhive_parser.py",
    "services/cross_modal_investigation.py",
    "services/investigation_snapshot.py",
}

# Audio/speech-synthesis egress. Matched against code with comments and
# docstrings stripped - `services/capability_registry.py` legitimately
# discusses "text-to-speech" in a comment explaining that ARCHIOSK has no
# such capability, and a guard that fired on that would be unusable.
_AUDIO_EGRESS_PATTERNS = (
    r"audio\s*\.\s*speech",
    r"speech\s*\.\s*create",
    r"\btext[-_]to[-_]speech\b",
    r"\btexttospeech\b",
    r"\bsynthesize_speech\b",
    r"\btts-1\b",
    r"\bSpeechSynthesis\w*",
    r"\belevenlabs\b",
    r"\bpolly\b",
)


def _python_files():
    for name in _SCANNED_DIRS:
        for path in sorted((_ROOT / name).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path
    for name in _SCANNED_FILES:
        path = _ROOT / name
        if path.exists():
            yield path


def _rel(path: Path) -> str:
    return path.relative_to(_ROOT).as_posix()


def _strip_comments_and_docstrings(source: str) -> str:
    """Prose about a boundary is not a crossing of it.

    Uses the parsed tree to blank docstrings, then drops `#` comments, so a
    comment saying a capability does NOT exist cannot be read as evidence
    that it does.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    spans = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            spans.append((first.lineno, first.end_lineno))
    lines = source.splitlines()
    for start, end in spans:
        for i in range(start - 1, min(end, len(lines))):
            lines[i] = ""
    return "\n".join(re.sub(r"#.*$", "", line) for line in lines)


def _imported_roots(source: str) -> set[str]:
    """Top-level package of every import, from the parsed tree.

    `ast` rather than a regex specifically so a provider named in a comment
    or a string is never mistaken for an import.
    """
    roots = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return roots
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


class NoOutboundAudioSynthesis(unittest.TestCase):
    """The half the speech guards could not see."""

    def test_no_module_reaches_an_audio_or_speech_synthesis_endpoint(self):
        offenders = []
        for path in _python_files():
            code = _strip_comments_and_docstrings(path.read_text(encoding="utf-8"))
            for pattern in _AUDIO_EGRESS_PATTERNS:
                if re.search(pattern, code, re.I):
                    offenders.append(f"{_rel(path)} matches {pattern!r}")
        self.assertEqual(
            offenders, [],
            "Server-side code reaches a speech-synthesis endpoint. Voice output is "
            "NOT AUTHORIZED - see governance/specified-unbuilt/voice-output-read-aloud.md. "
            "Third-party speech egress additionally requires tools/dependency_fit.py, a "
            "declared door, and ACTION_EXTERNAL_AI_REQUEST gating. Do not delete this "
            "assertion to make a feature pass.",
        )

    def test_the_capability_registry_still_says_archiosk_cannot_speak(self):
        # The product tells users this in its own words. If read-aloud ever
        # ships, this entry must change in the SAME commit - a capability
        # claim that has quietly become false is worse than no claim.
        registry = (_ROOT / "services" / "capability_registry.py").read_text(encoding="utf-8")
        self.assertIn("cannot speak its own replies aloud", registry)


class EveryProviderCallGoesThroughADeclaredDoor(unittest.TestCase):
    """The part that keeps this true after today."""

    def test_no_undeclared_provider_sdk_is_imported_anywhere(self):
        # openai is the concrete case: it was imported by shelved work while
        # absent from requirements.txt, so the import could only ever have
        # worked on a machine where someone had installed it by hand.
        declared_or_stdlib = _DECLARED_SDKS
        offenders = []
        for path in _python_files():
            roots = _imported_roots(path.read_text(encoding="utf-8"))
            for suspect in ("openai", "elevenlabs", "boto3", "azure"):
                if suspect in roots and suspect not in declared_or_stdlib:
                    offenders.append(f"{_rel(path)} imports {suspect!r}")
        self.assertEqual(
            offenders, [],
            "An undeclared provider SDK is imported. Declare it in requirements.txt "
            "with tools/dependency_fit.py first, and route it through a declared door.",
        )

    def test_every_provider_sdk_import_sits_in_a_declared_door(self):
        offenders = []
        for path in _python_files():
            rel = _rel(path)
            if rel in _PROVIDER_DOORS or rel.startswith("tools/"):
                # tools/ are operator-run scripts, never request-path code.
                continue
            roots = _imported_roots(path.read_text(encoding="utf-8"))
            hit = roots & _DECLARED_SDKS
            if hit:
                offenders.append(f"{rel} imports {sorted(hit)}")
        self.assertEqual(
            offenders, [],
            "A module reaches a provider SDK outside the declared doors. "
            "services/llm_gateway.py is the intended boundary. Add the module to "
            "_PROVIDER_DOORS deliberately, with a reason, or route the call through "
            "the gateway - do not delete this assertion.",
        )

    def test_the_declared_doors_all_still_exist(self):
        # A door that no longer exists makes the assertion above vacuous for it.
        for rel in sorted(_PROVIDER_DOORS):
            with self.subTest(door=rel):
                self.assertTrue((_ROOT / rel).exists(), f"{rel} is declared but absent")


if __name__ == "__main__":
    unittest.main()
