"""CLAUDE-GO-PDZ-VALIDATOR-01 - is the evidence discipline sound?

The second of three layers, and the only one that can catch the failures that
matter. `go_pdz_contract.validate_structure` answers "are the fields the right
shape". This answers "is what they contain defensible". Neither makes the result
authoritative - see the contract module's own header for why that distinction is
load-bearing rather than pedantic.

FAIL-CLOSED. Any ERROR means the result is NOT PROMOTABLE as a governed GO-PDZ
result. A WARNING leaves it valid but must stay visible. INFO is diagnostic.
There is no severity that quietly downgrades a broken evidence chain.

THE TWO RULES THIS EXISTS FOR, because both were observed for real rather than
imagined:

  - **A SITE-SPECIFIC EXCEPTION THAT CANNOT BE READ MUST NOT FALL BACK TO THE
    PARENT ZONE.** An exception exists precisely to displace the parent standard,
    so applying the parent standard "because the exception text was unavailable"
    inverts the one fact that was established. VR-08 and VR-20.

  - **A SPATIAL PREDICATE MUST COME FROM GEOMETRY, NOT FROM LOOKING.** "The
    parcel appears to be inside the regulated area" is a real observation and a
    useless authority. VR-09 and VR-10 keep `INSIDE`/`OUTSIDE`/`INTERSECTS`
    reserved for a deterministic GIS answer and force everything else down to
    `APPEARS_INSIDE` or `AMBIGUOUS`.

RULE IDS LIVE IN ONE TABLE. `RULES` below is the single place VR-01..VR-20 are
named, described and given a severity. The authorizing prompt referred to a
supplied specification that was not attached, so these are DERIVED from its
stated requirements and its ten negative cases; re-keying them to a canonical
specification is an edit to that table, not to the checks.
"""
from __future__ import annotations

import re

from services.go_pdz_contract import (
    ASSERTIVE_SPATIAL, CONTRACT_ID, GATE_01, GATE_01_FORBIDDEN_TOPICS,
    SCHEMA_VERSION, SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING,
    validate_structure,
)

VALIDATOR_VERSION = "go-pdz-validator@1"

#: rule_id -> (severity, one-line description)
RULES = {
    "VR-01": (SEVERITY_ERROR, "Result declares the Address-Only gate"),
    "VR-02": (SEVERITY_ERROR, "Subject identity resolved before any zoning claim"),
    "VR-03": (SEVERITY_ERROR, "Every statement declares a kind in the vocabulary"),
    "VR-04": (SEVERITY_ERROR, "AUTHORITY_SAYS cites at least one authority"),
    "VR-05": (SEVERITY_ERROR, "AUTHORITY_SAYS is not supported only by GO inference"),
    "VR-06": (SEVERITY_ERROR, "ESTABLISHED is not paired with LOW confidence"),
    "VR-07": (SEVERITY_ERROR, "HIGH confidence rests on an in-force authority"),
    "VR-08": (SEVERITY_ERROR, "Unretrieved site-specific exception forces UNRESOLVED"),
    "VR-09": (SEVERITY_ERROR, "Assertive spatial predicate requires deterministic geometry"),
    "VR-10": (SEVERITY_ERROR, "APPEARS_INSIDE/AMBIGUOUS cannot be ESTABLISHED"),
    "VR-11": (SEVERITY_ERROR, "Conflicting statements cross-reference each other"),
    "VR-12": (SEVERITY_ERROR, "Gate 01 contains no owner-program content"),
    "VR-13": (SEVERITY_ERROR, "No prediction of a municipal approval decision"),
    "VR-14": (SEVERITY_ERROR, "Planning relief is not asserted as definite pre-proposal"),
    "VR-15": (SEVERITY_ERROR, "Material unresolved issues reach the result status"),
    "VR-16": (SEVERITY_WARNING, "Authority carries an effective date or version"),
    "VR-17": (SEVERITY_ERROR, "A superseded authority does not support ESTABLISHED"),
    "VR-18": (SEVERITY_WARNING, "GO_INTERPRETS does not speak in the authority's voice"),
    "VR-19": (SEVERITY_ERROR, "Every authority_ref resolves to a declared authority"),
    "VR-20": (SEVERITY_ERROR, "Parent-zone standards are not applied over an "
                              "unresolved exception"),
}

#: Wording that only an authority may use. A GO interpretation that says "the
#: by-law requires" has stopped interpreting and started legislating.
_AUTHORITY_VOICE = re.compile(
    r"\b(?:shall|must|is required|are required|requires|is permitted|are permitted|"
    r"is prohibited|are prohibited|mandates)\b", re.IGNORECASE)

#: Wording that predicts what a decision-maker will do.
_PREDICTIVE_APPROVAL = re.compile(
    r"\b(?:will be approved|will approve|would be approved|is likely to be approved|"
    r"council will|committee will (?:approve|grant)|will be granted|"
    r"approval is (?:assured|expected|guaranteed))\b", re.IGNORECASE)

#: Wording that treats discretionary relief as already obtained.
_DEFINITE_RELIEF = re.compile(
    r"\b(?:the variance (?:is|will be) (?:granted|obtained)|"
    r"minor variance is available|relief is available|"
    r"the rezoning (?:is|will be) (?:granted|obtained)|"
    r"a variance can be obtained)\b", re.IGNORECASE)

#: Topic tokens that belong to Gate 02.
_PROGRAM_HINT = re.compile(
    r"\b(?:unit count|units? proposed|room count|budget|pro ?forma|"
    r"statement of requirements|massing|preferred option|selected option)\b",
    re.IGNORECASE)


def _finding(rule_id, path, subject_id, message, observed=None, expected=None):
    severity, _description = RULES[rule_id]
    return {
        "rule_id": rule_id,
        "severity": severity,
        "status": "FAIL",
        "path": path,
        "subject_id": subject_id,
        "message": message,
        "observed": observed,
        "expected": expected,
    }


def validate_semantics(document) -> list:
    """Every VR failure in `document`, in rule order. Never raises."""
    findings = []
    subject = (document.get("subject") or {}) if isinstance(document, dict) else {}
    subject_id = subject.get("subject_id")
    statements = document.get("statements") or []
    authorities = document.get("authorities") or []
    exceptions = document.get("site_specific_exceptions") or []
    unresolved = document.get("unresolved") or []
    by_id = {a.get("authority_id"): a for a in authorities if isinstance(a, dict)}
    statement_ids = {s.get("statement_id") for s in statements if isinstance(s, dict)}
    result_status = document.get("result_status")

    # VR-01
    if document.get("gate") != GATE_01:
        findings.append(_finding(
            "VR-01", "$.gate", subject_id,
            "an Address-Only result must declare the Gate 01 envelope",
            document.get("gate"), GATE_01))

    # VR-02 - identity first. A zoning claim about an unidentified parcel is a
    # claim about nothing in particular.
    if subject.get("identity_confidence") in ("LOW", "UNRESOLVED"):
        zoning_like = [s for s in statements
                       if isinstance(s, dict)
                       and s.get("kind") == "AUTHORITY_SAYS"
                       and s.get("statement_status") == "ESTABLISHED"]
        if zoning_like:
            findings.append(_finding(
                "VR-02", "$.subject.identity_confidence", subject_id,
                "parcel identity is not established, so no authority statement "
                "about it may be ESTABLISHED",
                subject.get("identity_confidence"), "HIGH or MEDIUM"))

    for index, statement in enumerate(statements):
        if not isinstance(statement, dict):
            continue
        path = "$.statements[%d]" % index
        sid = statement.get("statement_id")
        kind = statement.get("kind")
        status = statement.get("statement_status")
        confidence = statement.get("confidence")
        refs = statement.get("authority_refs") or []
        relation = statement.get("spatial_relation")
        basis = statement.get("spatial_basis")
        text = statement.get("text") or ""

        # VR-03
        if kind not in ("AUTHORITY_SAYS", "PROPERTY_FACT", "GO_INTERPRETS"):
            findings.append(_finding("VR-03", path + ".kind", sid,
                                     "unknown statement kind", kind,
                                     "AUTHORITY_SAYS | PROPERTY_FACT | GO_INTERPRETS"))

        if kind == "AUTHORITY_SAYS":
            # VR-04
            if not refs:
                findings.append(_finding(
                    "VR-04", path + ".authority_refs", sid,
                    "an AUTHORITY_SAYS statement must cite the authority it reports",
                    [], "at least one authority_id"))
            # VR-05 - an authority statement derived from a GO interpretation is
            # a GO interpretation wearing an authority's coat. Note this fires
            # EVEN IF an authority is also cited: attaching a citation to an
            # inference does not convert the inference into a report of what the
            # authority said. Deliberately independent of VR-04 so the two
            # failures cannot mask one another.
            derived = statement.get("derived_from") or []
            go_backed = [d for d in derived
                         if any(s.get("statement_id") == d
                                and s.get("kind") == "GO_INTERPRETS"
                                for s in statements if isinstance(s, dict))]
            if go_backed:
                findings.append(_finding(
                    "VR-05", path + ".derived_from", sid,
                    "AUTHORITY_SAYS is derived from a GO interpretation",
                    go_backed, "derivation from an authority, not an inference"))

        # VR-06
        if status == "ESTABLISHED" and confidence == "LOW":
            findings.append(_finding(
                "VR-06", path + ".confidence", sid,
                "ESTABLISHED cannot rest on LOW confidence",
                "%s + %s" % (status, confidence), "ESTABLISHED with HIGH or MEDIUM"))

        # VR-07 / VR-17
        for ref in refs:
            authority = by_id.get(ref)
            if authority is None:
                # VR-19
                findings.append(_finding(
                    "VR-19", path + ".authority_refs", sid,
                    "authority_ref does not resolve to a declared authority",
                    ref, "an authority_id present in $.authorities"))
                continue
            astatus = authority.get("authority_status")
            if confidence == "HIGH" and astatus in ("SUPERSEDED", "UNKNOWN",
                                                    "ADOPTED_NOT_IN_FORCE"):
                findings.append(_finding(
                    "VR-07", path + ".confidence", sid,
                    "HIGH confidence cannot rest on an authority that is not in force",
                    "%s / authority %s" % (confidence, astatus),
                    "IN_FORCE authority, or lower confidence"))
            if status == "ESTABLISHED" and astatus == "SUPERSEDED":
                findings.append(_finding(
                    "VR-17", path + ".authority_refs", sid,
                    "a superseded authority cannot establish a current standard",
                    ref, "an authority that is IN_FORCE"))

        # VR-09 - the deterministic spatial rule.
        if relation in ASSERTIVE_SPATIAL and basis != "DETERMINISTIC_GIS":
            findings.append(_finding(
                "VR-09", path + ".spatial_relation", sid,
                "an assertive spatial predicate requires deterministic geometry",
                "%s from %s" % (relation, basis),
                "DETERMINISTIC_GIS, or APPEARS_INSIDE / AMBIGUOUS"))
        # VR-10
        if relation in ("APPEARS_INSIDE", "AMBIGUOUS") and status == "ESTABLISHED":
            findings.append(_finding(
                "VR-10", path + ".statement_status", sid,
                "an impression of location cannot be an established fact",
                "%s + %s" % (relation, status), "PROVISIONAL or UNRESOLVED"))

        # VR-11 - a conflict that is not cross-referenced is a conflict nobody
        # reading the result can see.
        for ref in statement.get("conflict_refs") or []:
            if ref not in statement_ids:
                findings.append(_finding(
                    "VR-11", path + ".conflict_refs", sid,
                    "conflict_refs names a statement that does not exist",
                    ref, "an existing statement_id"))
                continue
            other = next(s for s in statements
                         if isinstance(s, dict) and s.get("statement_id") == ref)
            if sid not in (other.get("conflict_refs") or []):
                findings.append(_finding(
                    "VR-11", path + ".conflict_refs", sid,
                    "a declared conflict must be visible from both sides",
                    "%s -> %s only" % (sid, ref), "reciprocal conflict_refs"))

        # VR-12
        topic = (statement.get("topic") or "").upper()
        if topic in GATE_01_FORBIDDEN_TOPICS or _PROGRAM_HINT.search(text):
            findings.append(_finding(
                "VR-12", path + ".topic", sid,
                "owner-program content is outside the Address-Only gate",
                topic or text[:60], "a topic obtainable from the address alone"))

        # VR-13
        if _PREDICTIVE_APPROVAL.search(text):
            findings.append(_finding(
                "VR-13", path + ".text", sid,
                "the result predicts a municipal approval decision",
                _PREDICTIVE_APPROVAL.search(text).group(0),
                "the pathway and its tests, not its outcome"))

        # VR-14
        if _DEFINITE_RELIEF.search(text) and status == "ESTABLISHED":
            findings.append(_finding(
                "VR-14", path + ".text", sid,
                "discretionary relief is asserted as definite before a proposal exists",
                _DEFINITE_RELIEF.search(text).group(0),
                "relief described as a pathway, not an entitlement"))

        # VR-18
        if kind == "GO_INTERPRETS" and _AUTHORITY_VOICE.search(text):
            findings.append(_finding(
                "VR-18", path + ".text", sid,
                "a GO interpretation is written in the authority's voice",
                _AUTHORITY_VOICE.search(text).group(0),
                "interpretive wording attributed to GO"))

    # VR-08 / VR-20 - the site-specific exception fail-closed rule.
    unresolved_exceptions = [e for e in exceptions
                             if isinstance(e, dict) and not e.get("text_retrieved")]
    for exception in unresolved_exceptions:
        path = "$.site_specific_exceptions"
        if result_status != "UNRESOLVED":
            findings.append(_finding(
                "VR-08", path, exception.get("exception_id"),
                "a site-specific exception was indicated but its text could not be "
                "verified, so the result cannot stand as a governed result",
                result_status, "UNRESOLVED"))
        for field in ("missing_authority", "development_effect",
                      "required_next_evidence"):
            if not exception.get(field):
                findings.append(_finding(
                    "VR-08", "%s.%s" % (path, field), exception.get("exception_id"),
                    "an unresolved exception must say what is missing and what it "
                    "would change", None, "a stated %s" % field))
        # VR-20 - the substantive half: having found an exception it could not
        # read, the result must not quietly apply the parent zone anyway.
        for index, statement in enumerate(statements):
            if not isinstance(statement, dict):
                continue
            if statement.get("statement_status") != "ESTABLISHED":
                continue
            if statement.get("kind") != "AUTHORITY_SAYS":
                continue
            if (statement.get("topic") or "").upper() in (
                    "ZONING_STANDARD", "HEIGHT", "DENSITY", "SETBACK",
                    "LOT_COVERAGE", "PARKING", "FSI"):
                findings.append(_finding(
                    "VR-20", "$.statements[%d].statement_status" % index,
                    statement.get("statement_id"),
                    "parent-zone standards cannot be ESTABLISHED while a "
                    "site-specific exception (%s) remains unverified"
                    % exception.get("exception_id"),
                    "ESTABLISHED", "PROVISIONAL or UNRESOLVED"))

    # VR-15
    material = [u for u in unresolved
                if isinstance(u, dict) and u.get("materiality") == "MATERIAL"]
    if material and result_status != "UNRESOLVED":
        findings.append(_finding(
            "VR-15", "$.result_status", subject_id,
            "a material unresolved issue must reach the result status",
            result_status, "UNRESOLVED"))

    # VR-16, evaluated ONCE PER AUTHORITY rather than once per citation of one.
    # It previously sat inside the statement loop, so a document citing one
    # by-law from six statements reported six identical warnings - noise that
    # also misstated how many authorities were deficient. And its own message
    # offers "effective date OR version", so a version now satisfies it: a
    # consolidated Official Plan is dated by its consolidation label, not by an
    # in-force date, and rejecting that would penalise the correct record.
    for authority in document.get("authorities") or []:
        if not (authority.get("effective_date")
                or authority.get("version_identifier")):
            findings.append(_finding(
                "VR-16", "$.authorities", authority.get("authority_id"),
                "authority carries no effective date or version",
                None, "an effective_date or a version_identifier"))

    order = list(RULES)
    findings.sort(key=lambda f: (order.index(f["rule_id"]), f["path"]))
    return findings


def validate(document) -> dict:
    """Structure then semantics, in one governed envelope.

    Structural failures are reported as `SCHEMA` findings and semantic checking
    still runs, because a document can be structurally wrong in one field and
    evidentially wrong in another, and reporting only the first would send a
    reader round the loop twice.
    """
    findings = []
    for path, message in validate_structure(document):
        findings.append({
            "rule_id": "SCHEMA", "severity": SEVERITY_ERROR, "status": "FAIL",
            "path": path, "subject_id": None, "message": message,
            "observed": None, "expected": None,
        })
    if isinstance(document, dict):
        findings.extend(validate_semantics(document))

    errors = [f for f in findings if f["severity"] == SEVERITY_ERROR]
    warnings = [f for f in findings if f["severity"] == SEVERITY_WARNING]
    return {
        "validator_version": VALIDATOR_VERSION,
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT_ID,
        # FAIL-CLOSED: any ERROR and the result is not promotable. A warning
        # leaves it valid and visible, which is the whole point of having two
        # severities rather than one.
        "valid": not errors,
        "promotable": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "info_count": len([f for f in findings
                           if f["severity"] == SEVERITY_INFO]),
        "findings": findings,
        # Said out loud, every time, because a passing validator is exactly the
        # moment someone starts treating the output as the law.
        "authority_note": ("STRUCTURE VALID != SEMANTICALLY VALID != GOVERNED "
                           "AUTHORITY. The municipal and legislative sources "
                           "remain the authority; this is a governed pre-design "
                           "interpretation of them."),
    }
