"""
CLAUDE-POSTCAMEL-CA1C (Sections 4/13) - Application Capability Knowledge.

A small, centralized, deliberately non-sprawling answer to "what can
ARCHIOSK itself actually do" - distinct from Project Evidence (which
answers "what does this Project's own material say"). Answering a
question like "Can ARCHIOSK create folders?" by searching Project
evidence is a category error (Section 4's own explicit example); this
module exists so that category of question is answered from a real,
audited, truthful source instead.

Every entry below was checked directly against this repository's own
code before being written - never asserted from the product's stated
vision. See each entry's own `description` for what was actually
checked.

Deliberately NOT a general capability ontology (Section 4's own "do not
create a sprawling capability ontology") - only the capabilities a real
PM plausibly asks about in ordinary conversation are listed. Extending
this list is expected to remain cheap and narrow: one more `Capability`
entry plus one more phrase mapping, not a schema change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

CAPABILITY_STATUS_IMPLEMENTED = "implemented"
CAPABILITY_STATUS_PARTIAL = "partial"
CAPABILITY_STATUS_UNAVAILABLE = "unavailable"
CAPABILITY_STATUS_FUTURE = "future"

KNOWN_CAPABILITY_STATUSES = frozenset({
    CAPABILITY_STATUS_IMPLEMENTED, CAPABILITY_STATUS_PARTIAL,
    CAPABILITY_STATUS_UNAVAILABLE, CAPABILITY_STATUS_FUTURE,
})


@dataclass(frozen=True)
class Capability:
    key: str
    status: str
    description: str
    # A truthful alternative action to offer when status is not
    # IMPLEMENTED (Section 5's own "Prepare structure" vs "Create this
    # structure" example) - None when there is no honest alternative.
    alternative: Optional[str] = None
    # CLAUDE-GO-HOWTO-RECIPE-01: an ordered procedure for capabilities that
    # are something the reviewer DOES, rather than a yes/no fact about the
    # application. Rendered as a numbered list. Left empty for genuinely
    # yes/no capabilities ("can you edit spreadsheets"), where numbering a
    # single sentence would be ceremony rather than help.
    steps: tuple = ()


CAPABILITIES: dict[str, Capability] = {
    # CLAUDE-GO-HOWTO-RECIPE-01: the Product Owner asked how to upload a
    # photo and got a long, hedged non-answer - because nothing here described
    # it. The "+" that does it was built in the same session as this entry.
    "add_photo": Capability(
        "add_photo", CAPABILITY_STATUS_IMPLEMENTED,
        "You can add a photo straight from the Composer.",
        steps=(
            "Tap the + beside the message box at the bottom of the screen.",
            "Take a photo, or choose one from your library.",
            "Check the thumbnail that appears - tap the x to swap it if it is the wrong one.",
            "Type what you want to know about it, or leave it blank, and Send.",
        ),
    ),
    "make_investigation_from_photo": Capability(
        "make_investigation_from_photo", CAPABILITY_STATUS_IMPLEMENTED,
        "A photo can start a new investigation, named from what is in it.",
        steps=(
            "Tap the + beside the message box and take or choose the photo.",
            'Type "make a new Q" (or "start an investigation") with it.',
            "Send. I read the photo, propose a name from what is actually in it, "
            "and open the investigation with the photo saved inside.",
            "Rename it whenever you like - the name is a label, not a conclusion.",
        ),
    ),
    "start_new_conversation": Capability(
        "start_new_conversation", CAPABILITY_STATUS_IMPLEMENTED,
        "You can start a fresh conversation, or close one you have finished.",
        steps=(
            'Tap "New" in the conversation header to start a fresh one.',
            'Tap "Archive" to close the current one - it asks you to confirm first.',
            "Archived conversations are preserved, not deleted.",
        ),
    ),
    "create_project": Capability(
        "create_project", CAPABILITY_STATUS_IMPLEMENTED,
        "ARCHIOSK can establish a new Project from one founding document "
        "(the \"+ New Project\" / Establish a Project flow).",
    ),
    "open_source": Capability(
        "open_source", CAPABILITY_STATUS_IMPLEMENTED,
        "ARCHIOSK can open and display a registered Source directly "
        "(the Files view, or a real ?source= link).",
    ),
    "start_investigation": Capability(
        "start_investigation", CAPABILITY_STATUS_IMPLEMENTED,
        "ARCHIOSK can start a real, governed Investigation from a "
        "selected Requirement, Finding, or Source.",
    ),
    "show_evidence": Capability(
        "show_evidence", CAPABILITY_STATUS_IMPLEMENTED,
        "ARCHIOSK can show the Findings, Relationships, and Accepted "
        "Knowledge already linked as evidence for a governed Requirement.",
    ),
    # CLAUDE-POSTCAMEL-CA1C (Section 17, physical folder-creation audit):
    # confirmed by direct reading of services/case_workspace.py's own
    # Folder class and create_folder method - this is a REAL, governed,
    # already-implemented mechanism, but it creates a Design-Builder
    # Workspace Folder record (a virtual organizational container,
    # recoverably deletable, never touching the Data Room or any
    # original Source), never an operating-system directory. Named
    # honestly as its own distinct capability from physical folders,
    # per Section 8's own Territory-Before-Ontology distinction.
    "create_virtual_folder_structure": Capability(
        "create_virtual_folder_structure", CAPABILITY_STATUS_IMPLEMENTED,
        "ARCHIOSK can create real, governed Design-Builder Workspace "
        "folders (including nested ones) to organize a Project - a "
        "virtual organizational structure, never a physical filesystem "
        "folder, and never a change to the original Source or Data Room.",
    ),
    "create_physical_folders": Capability(
        "create_physical_folders", CAPABILITY_STATUS_UNAVAILABLE,
        "ARCHIOSK has no mechanism to create real operating-system "
        "folders anywhere - it has no filesystem access to a Project's "
        "own external Territory at all.",
        alternative="create_virtual_folder_structure",
    ),
    "edit_spreadsheets": Capability(
        "edit_spreadsheets", CAPABILITY_STATUS_UNAVAILABLE,
        "ARCHIOSK cannot open or edit native spreadsheets - upload.html's "
        "own accepted-formats list has never included them.",
    ),
    "open_powerpoint": Capability(
        "open_powerpoint", CAPABILITY_STATUS_UNAVAILABLE,
        "ARCHIOSK cannot open or edit presentation files - not among "
        "the supported ingestion formats.",
    ),
    "send_email": Capability(
        "send_email", CAPABILITY_STATUS_UNAVAILABLE,
        "ARCHIOSK has no external communications integration - it "
        "cannot send email, messages, or any other external "
        "communication on the PM's behalf.",
    ),
    "delegate_work": Capability(
        "delegate_work", CAPABILITY_STATUS_UNAVAILABLE,
        "Delegation is a named future programme (\"Delegation First\") - "
        "no Delegation object or mechanism exists in this codebase today.",
    ),
    # CLAUDE-VOICE1-DIAG-01: updated from FUTURE after VOICE1-PRE's own
    # push-to-talk button and browser-Web-Speech-API wiring landed - PARTIAL
    # (not IMPLEMENTED) because full end-to-end capture-to-transcript could
    # not be conclusively proven in this sandbox (no confirmed microphone
    # hardware/permission grant), only the button, feature-detection, and
    # event wiring. ARCHIOSK never continuously listens, and has no voice
    # OUTPUT (text-to-speech) of its own replies - that is a separate,
    # unimplemented capability, not part of this entry.
    "voice_input": Capability(
        "voice_input", CAPABILITY_STATUS_PARTIAL,
        "ARCHIOSK has a Push-to-Talk microphone button (press, speak, "
        "release) that fills the message composer with a transcript you "
        "can edit before sending - it uses your browser's own built-in "
        "speech recognition, never uploads or stores audio, and only "
        "activates when you press it. ARCHIOSK does not continuously "
        "listen, and cannot speak its own replies aloud or otherwise "
        "process ambient sound.",
    ),
    "biometric_recognition": Capability(
        "biometric_recognition", CAPABILITY_STATUS_FUTURE,
        "Face/voice recognition is a named future programme (Presence "
        "& Re-entry) - not implemented; ARCHIOSK does not recognize who "
        "is speaking or typing beyond the ordinary login session.",
    ),
}


# CLAUDE-POSTCAMEL-CA1C (Section 13): deterministic keyword routing,
# same discipline as every other trigger in this codebase - not an
# attempt at general capability-question understanding. Longer/more
# specific phrases are checked before shorter/more generic ones so
# "create folders" resolves to the real capability rather than a vaguer
# neighboring one.
_PHRASE_TO_CAPABILITY_KEY: tuple[tuple[str, str], ...] = (
    # CLAUDE-GO-HOWTO-RECIPE-01: FIRST, deliberately. Matching is first-hit,
    # and the generic entries below ("investigation", "folder") would
    # otherwise swallow "make a new Q from this photo". These are the
    # questions a reviewer standing on site actually asks, and every one of
    # them used to fall past this table to a model that could only guess at
    # an application it has no reliable knowledge of.
    ("upload a photo", "add_photo"),
    ("upload photo", "add_photo"),
    ("uploading a photo", "add_photo"),
    ("add a photo", "add_photo"),
    ("add photo", "add_photo"),
    ("take a photo", "add_photo"),
    ("attach a photo", "add_photo"),
    ("attach an image", "add_photo"),
    ("add an image", "add_photo"),
    ("upload an image", "add_photo"),
    ("send a photo", "add_photo"),
    ("new q", "make_investigation_from_photo"),
    ("make a q", "make_investigation_from_photo"),
    ("new conversation", "start_new_conversation"),
    ("delete a conversation", "start_new_conversation"),
    ("archive a conversation", "start_new_conversation"),
    ("physical folder", "create_physical_folders"),
    ("real folder", "create_physical_folders"),
    ("actual folder", "create_physical_folders"),
    ("folder", "create_virtual_folder_structure"),
    ("subfolder", "create_virtual_folder_structure"),
    ("investigation", "start_investigation"),
    ("evidence", "show_evidence"),
    ("open a source", "open_source"),
    ("open this source", "open_source"),
    ("new project", "create_project"),
    ("create a project", "create_project"),
    ("spreadsheet", "edit_spreadsheets"),
    ("excel", "edit_spreadsheets"),
    ("powerpoint", "open_powerpoint"),
    ("send", "send_email"),
    ("email", "send_email"),
    ("message sarah", "send_email"),
    ("delegate", "delegate_work"),
    ("delegation", "delegate_work"),
    ("voice", "voice_input"),
    ("microphone", "voice_input"),
    ("speak", "voice_input"),
    # CLAUDE-VOICE1-DIAG-01: a real Product Owner asked "Are you capable
    # of hearing sound?" and "hear me" in the same session - without these,
    # the question fell through to the generic project-QA path and produced
    # a category-confused non-answer instead of a truthful capability one.
    ("hearing sound", "voice_input"),
    ("hear sound", "voice_input"),
    ("capable of hearing", "voice_input"),
    ("process audio", "voice_input"),
    ("process sound", "voice_input"),
    ("recognize my voice", "biometric_recognition"),
    ("recognize me", "biometric_recognition"),
    ("face recognition", "biometric_recognition"),
)


def find_capability_by_phrase(lowered_text: str) -> Optional[Capability]:
    for phrase, key in _PHRASE_TO_CAPABILITY_KEY:
        if phrase in lowered_text:
            return CAPABILITIES[key]
    return None
