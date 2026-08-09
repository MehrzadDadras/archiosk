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


CAPABILITIES: dict[str, Capability] = {
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
    "voice_input": Capability(
        "voice_input", CAPABILITY_STATUS_FUTURE,
        "Voice input (VOICE-1, Push-to-Talk) has been audited as a "
        "future capability but is not implemented - conversation is "
        "text-only today.",
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
    ("recognize my voice", "biometric_recognition"),
    ("recognize me", "biometric_recognition"),
    ("face recognition", "biometric_recognition"),
)


def find_capability_by_phrase(lowered_text: str) -> Optional[Capability]:
    for phrase, key in _PHRASE_TO_CAPABILITY_KEY:
        if phrase in lowered_text:
            return CAPABILITIES[key]
    return None
