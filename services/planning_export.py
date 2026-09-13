"""CLAUDE-PLANNING-WORKSPACE-02A - the governed result in a container people keep.

    RESULT VIEW  ->  ExportDocument  ->  services/document_export.build()

NO NEW EXPORT ENGINE, AND NO NEW DEPENDENCY. `services/document_export.py`
already composes real .docx and .pdf files from a container-neutral
`ExportDocument`, `python-docx` and `reportlab` are already pinned in
`requirements.txt`, and that module's own docstring already states the rule this
one has to obey: "An export is a VIEW of governed state, never a new assertion
about it... nothing is summarised, inferred, ranked or reworded by a model - a
document that quietly editorialised on the way out would be evidence laundering,
and a reader has no way to tell the difference." So this module is a PROJECTION
and nothing else. It decides layout, never content.

A DOCUMENT OUTLIVES THE SCREEN THAT RENDERED IT, which is the whole reason the
qualifications have to travel with it. A planning result read off a page has the
page's context - the banner, the unresolved list, the preview notice. The same
result in a .docx arrives on someone else's desk with none of that, possibly
months later, possibly forwarded by a person who never saw the page. Every export
therefore leads with its status and carries its unresolved items, and section 7's
instruction not to look like a municipal approval is implemented as a first-page
statement rather than as restraint in the styling.

THE FOUR LAYERS SURVIVE THE EXPORT (section 8). When follow-up content is
included, the governed result, what a person supplied, the deterministic
follow-up and the admission decision are four separately titled blocks, each
labelled with its origin. Flattening them into one authority-looking document is
the failure this whole tranche exists to prevent, and an export is where it would
be easiest - a Word file has no badges, no colour and no hover text, so the
labels have to be words.

WHAT IS DELIBERATELY NOT IN THE EXPORT. Map panels. `ExportDocument` carries
titles, preamble lines and tables, with no image channel, and adding one would
mean changing three writers plus deciding what municipal map imagery may be
redistributed inside a file that leaves the application. The visual evidence
panel therefore exports as its PROVENANCE - source, layer, retrieval, geometry
identity - with an explicit line saying the panel itself is on the web surface.
An export that silently dropped the visuals would be worse; one that embedded
imagery whose licensing nobody checked would be worse still.
"""
from __future__ import annotations

from services import document_export
from services import planning_contribution as contribution
from services import planning_result_view as view_module

EXPORT_VERSION = "planning-export@1"

SCOPE_GOVERNED_ONLY = "GOVERNED_RESULT_ONLY"
SCOPE_WITH_FOLLOW_UP = "GOVERNED_RESULT_WITH_FOLLOW_UP"
SCOPES = (SCOPE_GOVERNED_ONLY, SCOPE_WITH_FOLLOW_UP)

FORMATS = (document_export.FORMAT_DOCX, document_export.FORMAT_PDF)

#: Section 7 and section 24, as one sentence each, at the top of every file.
#:
#: THE SECOND LINE IS THE ONE THAT MATTERS AND IT IS DELIBERATELY NOT PADDED.
#: GO-PDZ is an implemented contract and validator series; it has not completed
#: governance ratification, and `governance/STATUS.md` records that gap as open.
#: A metadata line calling it a ratified standard would close a governance gap
#: through a document footer, which is precisely what section 2 forbids.
NOT_AN_APPROVAL = (
    "THIS IS NOT A MUNICIPAL APPROVAL, A PERMIT, OR A DECISION OF ANY "
    "AUTHORITY. It is a pre-design planning reading assembled from municipal "
    "records retrieved at the time stated below.")
CONTRACT_NOTE = (
    "Produced against the GO-PDZ-1.0-ONEPAGE result contract and its VR-series "
    "validator - an implemented internal contract, not a separately ratified "
    "governance standard.")
STRUCTURE_NOTE = (
    "STRUCTURE VALID is not SEMANTICALLY VALID is not GOVERNED AUTHORITY.")


def _statement_rows(statements) -> list:
    """One row per statement, with every qualification it carries.

    `statutory_effect` is included ONLY where the statement declares it, mirroring
    VR-22/23/24's own behaviour: a document written before that field existed says
    nothing about effect, and an export that printed a default would be inventing
    one.
    """
    rows = []
    for item in statements or []:
        effect = item.get("statutory_effect") or ""
        if item.get("effect_basis"):
            effect = "%s on %s" % (effect or "(unstated)", item["effect_basis"])
        rows.append([
            item.get("status") or "",
            item.get("text") or "",
            effect,
            ", ".join(item.get("authority_names") or []) or "",
            item.get("confidence") or "",
        ])
    return rows


STATEMENT_HEADERS = ["Status", "Statement", "Statutory effect", "Authority",
                     "Confidence"]


def _section_table(title, statements, note=None):
    return document_export.ExportTable(
        title=title, headers=list(STATEMENT_HEADERS),
        rows=_statement_rows(statements), note=note)


def _identity_table(view) -> document_export.ExportTable:
    identity = view.get("identity") or {}
    rows = [
        ["Address as given", identity.get("address_as_given") or ""],
        ["Normalized address", identity.get("address") or ""],
        ["Municipality", identity.get("municipality") or ""],
        ["Parcel identifier", identity.get("parcel_identifier") or ""],
        ["Identity confidence", identity.get("identity_confidence") or ""],
    ]
    return document_export.ExportTable(
        title="1. Property Identity", headers=["Field", "Value"], rows=rows,
        note="Parcel identity is host-owned and taken from the municipality's "
             "own property record.")


def _framework_table(view) -> document_export.ExportTable:
    framework = view.get("framework") or {}
    rows = []
    for authority in framework.get("authorities") or []:
        rows.append([
            authority.get("name") or "",
            authority.get("instrument") or "",
            authority.get("authority_status") or "",
            authority.get("effective_date") or authority.get(
                "version_identifier") or "",
            authority.get("retrieved_at") or "",
        ])
    return document_export.ExportTable(
        title="2. Governing Planning Framework — authorities relied on",
        headers=["Authority", "Instrument", "Status", "Effective / version",
                 "Retrieved"],
        rows=rows,
        note="An authority's currentness is part of what it establishes. A "
             "superseded or not-yet-in-force instrument cannot support an "
             "established conclusion.")


def _exceptions_table(view):
    exceptions = (view.get("framework") or {}).get("exceptions") or []
    if not exceptions:
        return None
    rows = [[
        item.get("exception_id") or "",
        "retrieved" if item.get("text_retrieved") else "NOT RETRIEVED",
        item.get("indicated_by") or "",
        item.get("development_effect") or "",
    ] for item in exceptions]
    return document_export.ExportTable(
        title="2a. Site-specific exceptions",
        headers=["Exception", "Text", "Indicated by", "Effect if unresolved"],
        rows=rows,
        note="An exception DISPLACES the parent zone standard. Where its text "
             "was not retrieved, every figure above is provisional until it is "
             "read.")


def _options_table(view):
    options = view.get("options") or []
    if not options:
        return None
    rows = []
    for option in options:
        rows.append([
            option.get("option_id") or option.get("label") or "",
            option.get("summary") or option.get("description") or "",
            option.get("posture") or option.get("planning_posture") or "",
            "; ".join(option.get("enabling_conditions") or []) or "",
        ])
    return document_export.ExportTable(
        title="7. Planning-Level Development Options",
        headers=["Option", "Summary", "Posture", "Enabling conditions"],
        rows=rows,
        note="Posture states what an option would depend on. AUTHORITY MAY "
             "IMPROVE POSTURE; DERIVATION ALONE MAY NOT - no option below is "
             "improved by having been drawn, costed or described.")


def _unresolved_table(view) -> document_export.ExportTable:
    rows = [[
        item.get("issue_id") or "",
        item.get("materiality") or "",
        item.get("question") or "",
        item.get("required_evidence") or "",
    ] for item in view.get("unresolved") or []]
    for item in view.get("unretrieved_exceptions") or []:
        rows.append([item.get("exception_id") or "", "MATERIAL",
                     "The text of this site-specific exception was not retrieved.",
                     item.get("required_next_evidence") or ""])
    return document_export.ExportTable(
        title="8. Unresolved / Municipal Confirmation",
        headers=["Issue", "Materiality", "Question", "Evidence required"],
        rows=rows,
        note="A MATERIAL unresolved item is why the result status above is what "
             "it is. These are not caveats; they are the work that remains.")


def _visual_table(panels):
    """Section 23. The panels' PROVENANCE travels even though the images do not."""
    if not panels:
        return None
    rows = [[
        panel.get("title") or "",
        panel.get("source") or "",
        panel.get("layer") or "",
        panel.get("retrieved_at") or "",
        panel.get("evidence_ref") or "",
    ] for panel in panels]
    return document_export.ExportTable(
        title="10a. Official visual evidence — provenance",
        headers=["Panel", "Source authority", "Layer", "Retrieved",
                 "Evidence reference"],
        rows=rows,
        note="The panels themselves are rendered on the ARCHIOSK result "
             "surface. This export carries their provenance rather than the "
             "imagery, so nothing here redistributes municipal map content.")


def _contribution_tables(layered) -> list:
    """Section 8's separation, as three distinctly titled blocks."""
    tables = []
    records = [item["record"] for item in layered.get("contributions") or []]
    if records:
        tables.append(document_export.ExportTable(
            title="11. Information supplied by a person — NOT HOST-OWNED",
            headers=["Classification", "Supplied by", "Submitted", "Content",
                     "Object"],
            rows=[[
                "%s (%s)" % (r.get("classification_label") or "",
                             r.get("classification") or ""),
                r.get("supplied_by") or "",
                r.get("submitted_at") or "",
                r.get("text") or "",
                ("USER-SUPPLIED: %s" % (r["supplied_object"].get("name") or "")
                 if r.get("supplied_object") else ""),
            ] for r in records],
            note="Everything in this block was supplied by a person using "
                 "ARCHIOSK. It is not a municipal record, not a property fact, "
                 "and has not been verified by ARCHIOSK."))

    reviews = [item["review"] for item in layered.get("follow_up") or []]
    if reviews:
        rows = []
        for review in reviews:
            for contradiction in review.get("contradictions") or []:
                rows.append([contradiction.get("kind") or "",
                             contradiction.get("detail") or ""])
            for item in review.get("needs_confirmation") or []:
                rows.append(["NEEDS_CONFIRMATION", item])
        tables.append(document_export.ExportTable(
            title="12. Deterministic follow-up review — ARCHIOSK, not an authority",
            headers=["Finding", "Detail"], rows=rows,
            note="Produced by deterministic comparison against the governed "
                 "result above. No model authored this block, and it decides "
                 "nothing that an authority decides."))

        admission = layered.get("admission") or {}
        tables.append(document_export.ExportTable(
            title="13. Admission decision",
            headers=["Field", "Value"],
            rows=[
                ["Admitted", str(admission.get("admitted", 0))],
                ["Quarantined", str(admission.get("quarantined", 0))],
                ["Posture inherited by derived work",
                 (layered.get("derived_posture") or {}).get("posture") or ""],
                ["Retained as host-owned regardless",
                 ", ".join(admission.get("host_retains") or [])],
            ],
            note="A quarantined contribution is excluded from any governed "
                 "follow-up and preserved here as evidence that it was offered. "
                 "It is not admitted at a lower confidence."))
    return tables


def build_export_document(view, *, scope=SCOPE_GOVERNED_ONLY, layered=None,
                          panels=None, generated_at=None) -> document_export.ExportDocument:
    """Project one result view into the container-neutral export shape.

    The SAME `ExportDocument` feeds both writers, which is `document_export`'s
    own stated property: "a reviewer who exports the same thing twice in two
    formats must not get two different answers."
    """
    view = view or {}
    identity = view.get("identity") or {}
    retrieval = view.get("retrieval") or {}

    preamble = [
        NOT_AN_APPROVAL,
        "",
        "Result status: %s" % (view.get("result_status") or "UNSTATED"),
        "Subject: %s" % (identity.get("address") or
                         identity.get("address_as_given") or "(unstated)"),
        "Parcel: %s" % (identity.get("parcel_identifier") or "(unresolved)"),
        "Gate: %s (next authorized gate: %s)"
        % (view.get("gate") or "", view.get("next_authorized_gate") or ""),
    ]
    if view.get("preview"):
        # A fixture-rendered page must never export as though it were analysis.
        preamble.append(
            "DEVELOPMENT FIXTURE: this document was produced from a controlled "
            "development fixture and is NOT an analysis of any real property.")
    preamble += [
        "",
        "Generated: %s" % (generated_at or "(unstated)"),
        "Municipal retrieval: %s" % (retrieval.get("retrieved_at") or "(unstated)"),
        "Result contract: %s" % (view.get("contract") or ""),
        "View version: %s / runner %s / export %s"
        % (view.get("view_version") or "", retrieval.get("runner_version") or "",
           EXPORT_VERSION),
        "",
        CONTRACT_NOTE,
        STRUCTURE_NOTE,
    ]
    if scope == SCOPE_WITH_FOLLOW_UP:
        preamble += [
            "",
            "THIS DOCUMENT CONTAINS FOUR DISTINCT LAYERS and they must not be "
            "read as one. Sections 1-10 are the governed result assembled from "
            "municipal records. Section 11 is information a person supplied. "
            "Section 12 is ARCHIOSK's deterministic follow-up. Section 13 is "
            "the admission decision. Only sections 1-10 are host-owned.",
        ]

    tables = [
        _identity_table(view),
        _framework_table(view),
    ]
    exceptions = _exceptions_table(view)
    if exceptions:
        tables.append(exceptions)
    tables += [
        _section_table("3. Permitted Development Context",
                       (view.get("permitted") or {}).get("statements")),
        _section_table("4. Development Envelope",
                       (view.get("envelope") or {}).get("statements")),
        _section_table("5. Mobility / Access Context",
                       (view.get("mobility") or {}).get("statements")),
        _section_table("6. Constraints & Opportunities — constraints",
                       (view.get("interpretation") or {}).get("constraints")),
        _section_table("6a. Constraints & Opportunities — opportunities",
                       (view.get("interpretation") or {}).get("opportunities"),
                       note="An opportunity is a reading of the evidence, not a "
                            "statement by any authority."),
    ]
    options = _options_table(view)
    if options:
        tables.append(options)
    tables.append(_unresolved_table(view))

    conclusion = view.get("conclusion")
    if conclusion:
        tables.append(document_export.ExportTable(
            title="9. Pre-Design Conclusion", headers=["Conclusion"],
            rows=[[conclusion if isinstance(conclusion, str)
                   else str(conclusion)]],
            note="A pre-design reading. It does not anticipate any authority's "
                 "decision."))

    tables.append(document_export.ExportTable(
        title="10. Evidence / Sources",
        headers=["Authority", "Citation", "Status", "Retrieved", "Source"],
        rows=[[
            item.get("name") or "", item.get("citation") or "",
            item.get("authority_status") or "", item.get("retrieved_at") or "",
            item.get("url") or item.get("source_type") or "",
        ] for item in view.get("evidence") or []]))

    visual = _visual_table(panels)
    if visual:
        tables.append(visual)

    if scope == SCOPE_WITH_FOLLOW_UP and layered:
        tables.extend(_contribution_tables(layered))

    return document_export.ExportDocument(
        title="Pre-Design Planning & Zoning Result",
        subtitle=identity.get("address") or identity.get("address_as_given"),
        preamble=preamble, tables=tables)


def export(view, export_format, *, scope=SCOPE_GOVERNED_ONLY, layered=None,
           panels=None, generated_at=None):
    """Build the file. Returns `(BytesIO, filename, mimetype)`.

    Raises ValueError on an unsupported format or scope rather than silently
    producing the default one - an export the caller did not ask for is a file
    somebody will later cite.
    """
    if export_format not in FORMATS:
        raise ValueError("Unsupported planning export format: %r" % export_format)
    if scope not in SCOPES:
        raise ValueError("Unsupported planning export scope: %r" % scope)

    document = build_export_document(view, scope=scope, layered=layered,
                                     panels=panels, generated_at=generated_at)
    stream = document_export.build(document, export_format)
    identity = (view or {}).get("identity") or {}
    return stream, filename_for(identity, export_format, scope), \
        document_export.MIMETYPES[export_format]


def filename_for(identity, export_format, scope=SCOPE_GOVERNED_ONLY) -> str:
    """A filename a person can find again, with no path characters in it."""
    label = (identity or {}).get("address") or (identity or {}).get(
        "address_as_given") or "planning-result"
    safe = "".join(ch if (ch.isalnum() or ch in " -_") else "" for ch in label)
    safe = "-".join(safe.split()).strip("-").lower() or "planning-result"
    suffix = "-with-follow-up" if scope == SCOPE_WITH_FOLLOW_UP else ""
    return "archiosk-planning-%s%s.%s" % (safe[:60], suffix, export_format)


#: Re-exported so a caller does not have to import two modules to learn what a
#: contribution layer looks like in an export.
CONTRIBUTION_VERSION = contribution.CONTRIBUTION_VERSION
VIEW_VERSION = view_module.VIEW_VERSION
