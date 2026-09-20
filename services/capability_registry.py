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

# Bounded view actions are metadata, not another execution engine. The existing
# source-review dispatcher invokes image_intake and the DerivedView owner.
VIEW_ACTIONS = {
    'ROTATE_90': {'label': 'Rotate clockwise 90 degrees', 'aliases': ('rotate 90 degrees',)},
    'ROTATE_180': {'label': 'Rotate 180 degrees', 'aliases': ('turn this around', 'rotate 180 degrees')},
    'ROTATE_270': {'label': 'Rotate clockwise 270 degrees', 'aliases': ('rotate 270 degrees',)},
    'MIRROR_HORIZONTAL': {'label': 'Mirror horizontally', 'aliases': ('mirror this detail', 'mirror horizontally')},
    'MIRROR_VERTICAL': {'label': 'Mirror vertically', 'aliases': ('mirror vertically',)},
    'CROP': {'label': 'Crop working view', 'aliases': ('crop this view',)},
    'FIT': {'label': 'Fit working view', 'aliases': ('fit this view',)},
    'ALIGN_NORTH_UP': {'label': 'Align established true north up', 'aliases': (), 'requires_premises': True},
}

# Recognized intentions requiring additional governed premises. Resolution does
# not authorize execution and must not silently substitute a rotation or mirror.
VIEW_PREMISE_ACTIONS = {
    'NORTH_UP': ('put north up',),
    'SHEET_READING': ('orient for reading',),
    'ALIGN': ('align these two details',),
    'OPPOSITE_SIDE': ('show the opposite side',),
}

# Capabilities are typed once. Natural-language resolution chooses an entry;
# existing application owners execute it after permission and parameter checks.
ACTION_REGISTRY = {
    'ALIGN_NORTH_UP': dict(action_class='view_only', executor='document_examination.create_working_view',
        description='Orient a derived view using existing established true-north and document-frame premises. Refuse unresolved or distorted frames.',
        parameters={}),
    'ROTATE_VIEW': dict(action_class='view_only', executor='document_examination.create_working_view',
        description='Rotate a derived working view clockwise, preserving the uploaded source.',
        parameters={'degrees': (90, 180, 270)}),
    'MIRROR_VIEW': dict(action_class='view_only', executor='document_examination.create_working_view',
        description='Mirror a derived view on an explicitly selected axis; no viewpoint or authority is inferred.',
        parameters={'axis': ('horizontal', 'vertical')}),
    'FIT_VIEW': dict(action_class='view_only', executor='document_examination.create_working_view',
        description='Create a fitted working view without changing source bytes or analysis.', parameters={}),
}

DOCUMENT_VIEW_ACTION_IDS = tuple(ACTION_REGISTRY)
DOCUMENT_DESK_ACTION_IDS = ('ARCHIVE_ITEMS', 'DELETE_ITEMS', 'REANALYZE_ITEMS', 'COMPARE_ITEMS', 'RELOAD_STATE')
ACTION_REGISTRY.update({
    'RELOAD_STATE': dict(action_class='view_only', executor='portal.document_shop_jobs',
        description='Refresh the current persisted document list/status only. Do not queue analysis or modify records.',
        parameters={}, bulk_action='reload'),
    'ARCHIVE_ITEMS': dict(action_class='workspace_mutation', executor='CaseWorkspaceStore.move_document_shop_case',
        description='Archive exactly the selected active disposable cases; retain their sources and evidence.',
        parameters={}, bulk_action='archive'),
    'DELETE_ITEMS': dict(action_class='destructive', executor='CaseWorkspaceStore.move_document_shop_case',
        description='Request the existing single Delete confirmation for the selection. Never confirm on behalf of the user. Recovery lasts seven days before purge.',
        parameters={}, bulk_action='delete'),
    'REANALYZE_ITEMS': dict(action_class='analytical', executor='document_examination.queue_reanalysis',
        description='Deliberately queue the selected preserved sources through the current analysis pipeline. This is not Reload.',
        parameters={}, bulk_action='reanalyze'),
    'COMPARE_ITEMS': dict(action_class='analytical', executor='document_examination.compare_document_analyses',
        description='Open the existing qualified comparison of exactly two compatible selected documents. Do not alter originals.',
        parameters={}, bulk_action='compare'),
})


def action_catalogue(action_ids):
    """Only caller-enabled capabilities enter the intent-resolution context."""
    return {key: ACTION_REGISTRY[key] for key in action_ids if key in ACTION_REGISTRY}


# Procedure declarations for the existing attention/review dispatcher. These
# describe its real executors; they neither execute actions nor admit evidence.
REVIEW_WORK_PROCEDURES = {
    '': ('Set attention', 'record_go_attention', ('ATTENTION',)),
    'requirement_matching': ('Match requirements', 'run_requirement_matching', ('AUTHORITY', 'MATCHING', 'UNCERTAINTY')),
    'role_composition': ('Compose required roles', 'run_role_composition', ('MATCHING', 'ROLE COMPOSITION', 'UNCERTAINTY')),
    'information_comparison': ('Compare normalized information', 'run_information_comparison', ('VIEW-NORMALIZATION', 'COMPARISON', 'UNCERTAINTY')),
    'constraint_review': ('Probe stated constraints', 'run_constraint_review', ('CONSTRAINT PROBING', 'BREAKPOINT SEARCH')),
    'professional_review': ('Run professional review', 'run_professional_review', ('EXPECTED-NEXT', 'SECTION-COVERAGE', 'DISCIPLINE-COVERAGE', 'ROOT-TRACE / RETURN')),
    'professional_presentation': ('Render retained review', 'render_professional_review', ('PROVENANCE PRESERVATION', 'UNCERTAINTY')),
    'transaction_review': ('Review transaction history', 'run_transaction_review', ('TRANSACTION IDENTITY', 'TRANSACTION HISTORY', 'UNCERTAINTY')),
}


def _muscle(name, inputs, outputs, transitions, refusal_states, authority_rule):
    """Contracts describe owned operations; they never execute or admit a result."""
    return dict(name=name, inputs=inputs, outputs=outputs, allowed_transitions=transitions,
        refusal_states=refusal_states, authority_rule=authority_rule,
        provenance_requirements='Retain source/evidence/object identities and applicable premise lineage. '
            'Trace records describe execution and never substitute for evidence.',
        runtime_hooks=('INVOKED', 'RETURNED', 'RAISED'), version='1')


# One catalogue beside the existing capability/action metadata. Each key names
# its actual implementation. Being registered is not proof of invocation.
MUSCLE_CONTRACTS = {
    'services.case_workspace.CaseWorkspaceStore.admit_reviewed_proposition': _muscle('SCOPED PROPOSITION AUTHORITY',
        'Exact retained Claim, immutable source fingerprints, scoped human checks, Disposition and Apply',
        'Proposition-confined admission with independent historical and current applicability',
        'Reviewed evidence and explicit Apply may admit only the checked scope',
        'UNRESOLVED for incomplete review or missing currentness; evaluation input cannot become project authority',
        'This admission does not alter original observations, raw-source authority, geometry or IFC admission.'),
    'services.case_workspace.CaseWorkspaceStore.record_event_proposition': _muscle('SOURCE EVENT INTERPRETATION',
        'Existing source/page evidence, exact quote and typed identity or event interpretation',
        'Append-only proposed Claim with source fingerprints and occurrence/discovery dates',
        'Source interpretation -> proposed Claim; no factual promotion',
        'REFUSED for foreign references, changed source bytes or removed evaluation ancestry',
        'Source classification, dates and event labels do not establish identity, maturity or authority.'),
    'services.cross_modal_investigation.resolve_transaction_identity': _muscle('TRANSACTION IDENTITY',
        'Source-anchored identity and event Claims, scoped review, Apply and explicit date',
        'Separate project, participant, transaction and temporal closure',
        'Proposed scope -> exact only with admissible scoped review',
        'UNRESOLVED for missing legal identity, authority or applicability; distinct structures stay distinct',
        'Matching names, parent relationships and shared projects do not establish transaction identity.'),
    'services.cross_modal_investigation.investigate_transaction_history': _muscle('TRANSACTION HISTORY',
        'Retained transaction Claims and independent event evidence', 'Maturity, lifecycle and recoverable event history',
        'Evidence-specific maturity and scoped lifecycle transitions; historical events remain retained',
        'UNRESOLVED for missing prerequisites; CONFLICTING for incompatible positive evidence',
        'Discovery order is not event order. Execution, currentness and financial close require separate evidence.'),
    'services.case_workspace.CaseWorkspaceStore.declare_go_work_plan': _muscle('GOVERNED WORK PLAN',
        'Bounded typed action, objective, existing scope and available premise identities', 'Persisted InvestigationStep procedure',
        'Intent -> PLANNED; declaration does not execute the domain action', 'REFUSED for foreign, inactive or unsupported inputs',
        'Plan is neither evidence, authority, execution, result nor approval.'),
    'services.case_workspace.CaseWorkspaceStore.begin_go_work_plan': _muscle('WORK PLAN EXECUTION',
        'Owned persisted plan and current workspace version', 'Single execution start with append-only dependency revision',
        'PLANNED -> RUNNING; changed available premises -> PLAN_REVISION', 'REFUSED for replay, foreign plan or concurrent stale version',
        'Current governance and evidence take precedence over the declared procedure.'),
    'services.cross_modal_investigation.evaluate_requirement_coverage': _muscle('REQUIREMENT COVERAGE',
        'Explicit requirement policies, retained comparison premises and participant configuration', 'Coverage assignments and separate compatibility state',
        'Positive hard conflict > unresolved premise > known partial > covered', 'UNRESOLVED for missing evidence or unsupported combination basis',
        'Conditional additive coverage is not factual authority, commitment, partnership agreement or actual JV.'),
    'services.case_workspace.CaseWorkspaceStore.run_role_composition': _muscle('ROLE COMPOSITION',
        'Retained candidate matching runs, explicit required roles or coverage policies and common temporal scope', 'Conditional minimum coverage configurations',
        'Positive role predicates -> set coverage; mandatory failures exclude candidates', 'REFUSED for foreign/mixed inputs; PARTIAL for missing coverage',
        'Supported conditional quantity addition remains separate from commercial structure, partnership compatibility and verified fit.'),
    'services.cross_modal_investigation.match_normalized_criteria': _muscle('REQUIREMENT MATCHING',
        'Distinct typed required/candidate premises and mandatory obligations', 'Per-criterion model states and mandatory failures',
        'Comparable predicates -> conditional match; mandatory failure dominates', 'UNRESOLVED, PARTIAL, REFUSED; missing and incomparable inputs remain explicit',
        'No score overrides a mandatory failure; model fit does not establish factual fit.'),
    'services.cross_modal_investigation.inspect_declared_temporal_scope': _muscle('DECLARED TEMPORAL SCOPE',
        'Source interpretation, expected temporal meaning and query date', 'Declared interval containment or unresolved currentness',
        'Explicit matching temporal class and date interval -> declared containment only', 'CURRENTNESS_UNRESOLVED for historical activity, missing dates or wrong temporal meaning',
        'Date containment and currentness labels do not verify an actual current mandate.'),
    'services.case_workspace.CaseWorkspaceStore.record_review_subject': _muscle('SUBJECT REFERENCE',
        'Active attention, declared subject name and role', 'Existing Participant identity reference',
        'Declared identity -> project-scoped reference only', 'REFUSED for unavailable scope or invalid name/role',
        'Registering a name or role does not verify identity or capabilities.'),
    'services.case_workspace.CaseWorkspaceStore.record_subject_proposition': _muscle('PROPOSITION NORMALIZATION',
        'Existing subject, cited observation, exact quote, typed interpretation and classifications', 'Individual proposed Claim or immutable successor',
        'Source-anchored interpretation -> proposed Claim; no authority promotion', 'REFUSED for invented quote, foreign subject, malformed value or lost evaluation provenance',
        'Source class and temporal labels do not authenticate a source or establish a current mandate.'),
    'services.case_workspace.CaseWorkspaceStore.review_subject_proposition': _muscle('PROPOSITION CURATION',
        'Current scoped Claim, explicit review action and reason', 'Existing adoption as interpretation or rejection',
        'Proposal -> reviewed interpretation or rejection; downstream re-evaluation remains explicit', 'REFUSED for expired scope, missing source, changed premises or unsupported promotion',
        'Adoption does not strengthen binding, applicability, authority or temporal validity.'),
    'services.case_workspace.CaseWorkspaceStore.record_go_attention': _muscle('ATTENTION',
        'Objective, project evidence, explicit selection and lifetime', 'Persisted analytical attention scope',
        'Selection -> bounded scope; excluded evidence remains present', 'REFUSED: missing objective, foreign evidence or invalid lifetime',
        'Focus does not change binding, authority or certainty.'),
    'services.case_workspace.CaseWorkspaceStore.record_temporary_relationship': _muscle('TEMPORARY RELATIONSHIPS',
        'Active attention, two endpoints, supporting evidence and hypothesis', 'Bounded temporary edge',
        'Hypothesis -> temporary edge only; no automatic promotion', 'REFUSED: expired scope, foreign or unselected endpoints',
        'Temporary relationships are not canonical project truth.'),
    'services.cross_modal_investigation.compare_normalized_information': _muscle('COMPARISON / MATCHING',
        'Two normalized premises, scope, units/vocabulary, qualifiers and viewpoint basis', 'Conditional model predicate and retained qualifications',
        'Explicit comparable premises -> MATCH/NON_MATCH; no factual consistency inferred', 'UNRESOLVED, PARTIAL, INCOMPARABLE, REFUSED',
        'Model agreement grants no authority. Callers preserve evaluation inputs and proposed source interpretations as such.'),
    'services.quantitative_investigation.compare_scalar_values': _muscle('QUANTITATIVE COMPARISON',
        'Finite required/candidate scalars and typed predicate', 'MATCH/NON_MATCH over supplied values',
        'Finite supplied values -> arithmetic predicate only', 'UNRESOLVED for invalid values; REFUSED for unsupported predicate',
        'Computable does not mean established. The caller must govern source premises.'),
    'services.cross_modal_investigation.cover_requirements': _muscle('COMPOSITION / MINIMUM COVERAGE',
        'Required coverage keys and applicable candidate coverage', 'Minimum covering configurations and missing keys',
        'Declared coverage -> bounded set selection; no ranking', 'UNRESOLVED, REFUSED, PARTIAL',
        'Coverage is limited to supplied requirements and established applicability.'),
    'services.cross_modal_investigation.inspect_representation_necessity': _muscle('REPRESENTATION NECESSITY',
        'Required keys and applicable representations', 'Unique contribution, overlap and removal gaps',
        'Known coverage -> essential/representative/unresolved role', 'NECESSITY_UNRESOLVED; duplicate agreement remains UNRESOLVED',
        'Overlap does not prove semantic equivalence or permission to delete.'),
    'services.cross_modal_investigation.inspect_continuum_participation': _muscle('CONTINUUM PARTICIPATION',
        'Scoped evidence, existing relationships and explicit participation expectation', 'Participation, missing connections and qualifications',
        'Expected connections -> participation/gap; legitimate independence is preserved', 'CONTINUUM_PARTICIPATION_UNRESOLVED, ORPHANED_INFORMATION, COORDINATION_GAP',
        'Connected does not mean authoritative; isolated does not mean incorrect.'),
    'services.quantitative_investigation.probe_interval_constraints': _muscle('CONSTRAINT PROBING',
        'Explicit scalar bounds sharing subject, parameter and unit', 'Common admissible interval or incompatibility',
        'Supplied bounds -> conditional intersection; no missing premise invented', 'UNRESOLVED, INCOMPARABLE, REFUSED',
        'Mathematical feasibility does not establish physical adequacy or source authority.'),
    'services.quantitative_investigation.search_interval_breakpoint': _muscle('BREAKPOINT SEARCH',
        'Bounded interval model, hypothetical baseline and direction', 'Boundary, first limiting constraint and margin',
        'Admissible hypothetical baseline -> first constraint boundary', 'UNRESOLVED for missing model or invalid baseline/direction',
        'Test variations remain EVALUATION_INPUT and never become actual project values.'),
    'services.cross_modal_investigation.assess_review_resolution': _muscle('SCALE-SEEKING',
        'Narrative, current/required resolution classes and evidence references', 'Resolution sufficiency and next question',
        'Explicit classes -> QUALIFIED for resolution only or INSUFFICIENT_SCALE', 'UNRESOLVED, INSUFFICIENT_SCALE',
        'Resolution does not establish content sufficiency, applicability or authority.'),
    'services.cross_modal_investigation.expected_next_information': _muscle('EXPECTED-NEXT',
        'Narrative, representation classes, subject, phase, discipline and evidence state', 'Expected next class versus scoped available information',
        'Explicit review sequence -> next information requirement; no sheet-number inference', 'UNRESOLVED, MISSING, SURPRISING, SUPERSEDED',
        'Absence is limited to the reviewed scope; unselected evidence still exists.'),
    'services.drawing_conditions.review_representation_coverage': _muscle('SECTION / DISCIPLINE COVERAGE',
        'Scoped conditions, review requirements and reviewed representation applicability', 'Condition coverage map and remaining gaps',
        'Current reviewed applicability -> qualified coverage of known conditions only', 'SECTION_COVERAGE_GAP, DISCIPLINE_COVERAGE_GAP, PARTIAL, UNRESOLVED',
        'More drawings do not prove complete inventory or engineering adequacy.'),
    'services.cross_modal_investigation.trace_governing_root': _muscle('ROOT-TRACE / RETURN',
        'Focal evidence and bounded governed dependency chain', 'Trace, root if admitted, controlling premise and return target',
        'Confirmed dependency -> next scoped premise; stop on ambiguity or broken authority', 'UNRESOLVED, REFUSED',
        'Connectivity or a terminal reference does not establish governing authority.'),
    'services.document_examination.create_working_view': _muscle('VIEW NORMALIZATION',
        'Immutable source, typed transform, parameters and reason', 'Retained derived view with transform lineage',
        'Original/parent view -> derived representation only', 'REFUSED through owner error for invalid frame, source or transform',
        'View transforms do not mutate the source or establish factual consistency.'),
    'services.package_muscles.inspect_view_normalization': _muscle('VIEW-NORMALIZATION BEFORE CONTRADICTION',
        'Source identities and retained transformed views', 'View-normalization qualification',
        'Retained representation chain -> visible qualification only', 'UNRESOLVED',
        'Visual alignment and mirrored pixels are not proof of consistency.'),
    'services.case_workspace.CaseWorkspaceStore.admit_proposition': _muscle('AUTHORITY / UNCERTAINTY / EVIDENCE SUFFICIENCY',
        'Existing scoped evidence and its governed producer/review lineage', 'Existing admission state and weakest applicable qualification',
        'Evidence -> existing admission rules only; no trace or narrative admission', 'UNRESOLVED, REFUSED, CONTESTED, SOURCE_REFERENCE',
        'No stronger conclusion without the premises required by the existing admission owner.'),
    'services.case_workspace.CaseWorkspaceStore.resolve_anchor_currentness': _muscle('CURRENTNESS',
        'Existing object identity and governed successor relationships', 'Currentness of the referenced anchor',
        'Existing succession -> currentness projection; timestamps alone do not decide', 'Unresolved, unavailable or stale anchors remain qualified',
        'Newer does not mean authoritative.'),
    'services.document_examination.review_text_correction': _muscle('HUMAN READING CORRECTION',
        'Anchored immutable machine read, proposed correction and explicit reviewer action', 'Accept/revert history preserving the original reading',
        'Proposed reading -> reviewed correction; downstream re-evaluation stays explicit', 'Owner refusal for missing source, correction or invalid action',
        'Reading correction does not settle binding, authority, applicability or geometry.'),
    'services.case_workspace.CaseWorkspaceStore.render_professional_review': _muscle('CONSUMER / PROVENANCE PRESERVATION',
        'Committed governed analysis and surviving evidence references', 'Retained presentation of the actual analysis',
        'Persisted analysis -> shared WorkProduct rendering; no new interpretation', 'REFUSED for unavailable analysis or broken lineage',
        'Presentation polish does not strengthen evidence or conceal unresolved states.'),
}


def resolve_view_action(text):
    """Choose a typed action only. Ambiguous viewpoint requests remain unresolved."""
    normalized = ' '.join(str(text or '').lower().strip().rstrip('.').split())
    result = next((key for key, entry in VIEW_ACTIONS.items()
                   if normalized in entry['aliases'] or normalized == key.lower()), None)
    return result or next((key for key, aliases in VIEW_PREMISE_ACTIONS.items() if normalized in aliases), None)


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
    # CLAUDE-GO-DOCUMENT-EXPORT-01: Product Owner: "My Copilot 365 can create
    # PDF and Excel and Word to download. Make our app to have equal
    # capabilities." It can now - and unlike the photo capability before it,
    # this one is described here from the start rather than after someone
    # asked and got an essay.
    "export_document": Capability(
        "export_document", CAPABILITY_STATUS_IMPLEMENTED,
        "ARCHIOSK can produce a real Word, Excel or PDF file of this project's "
        "governed content, for you to download.",
        steps=(
            "Open the project you want to export.",
            "Choose what to export: findings, requirements, investigations, or the whole project.",
            "Pick a format - Word (.docx), Excel (.xlsx) or PDF.",
            "The file downloads directly; nothing is sent anywhere else.",
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
    ("export", "export_document"),
    ("download", "export_document"),
    ("pdf", "export_document"),
    ("excel", "export_document"),
    ("spreadsheet", "export_document"),
    ("word document", "export_document"),
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
