"""CLAUDE-PLANNING-VISUAL-ACCEPTANCE-01 - does the picture prove what the prose says?

    A PARCEL BOUNDARY PROVES WHERE THE PROPERTY IS.
    A ZONING BOUNDARY PROVES WHICH REGULATORY GEOGRAPHY APPLIES.
    THEY ARE RELATED EVIDENCE. THEY ARE NOT INTERCHANGEABLE.

That is section 15 verbatim, and it is the only rule this module exists to
enforce. Everything below is a mechanical consequence of it.

WHAT THIS IS NOT. It is not a second opinion about zoning, not a renderer, and
not a retrieval path - it fetches nothing, decides nothing about planning, and
cannot make a result better than it is. It reads a FINISHED result plus the
panels drawn from it and answers one question: is every written conclusion
carried by evidence that is actually present, actually distinct, and actually
bound to the geometry it names?

THE VOCABULARY IS BORROWED, NOT INVENTED. Section 4 asks for five relationship
states and says to use existing governed equivalents where available. There is
one: `services/deterministic_spatial.py` already returns INSIDE / OUTSIDE /
INTERSECTS / AMBIGUOUS / NOT_APPLICABLE with a named `reason`, an engine version
and a basis, and the Toronto runner already computes that token for the parcel
against the zone polygon. So the five acceptance states are DERIVED from that
token rather than computed a second way - `zone_relationship()` is a projection,
not an engine. A parallel spatial implementation would be a second answer to a
question that already has a governed one, and the first time the two disagreed
the wrong one would be indistinguishable.

    WITHIN_SINGLE_ZONE          INSIDE, and exactly one qualified zone
    INTERSECTS_MULTIPLE_ZONES   more than one qualified zone polygon
    BOUNDARY_TOUCH              AMBIGUOUS for REASON_NEAR_BOUNDARY
    NO_QUALIFIED_ZONE_GEOMETRY  no zone geometry was retrieved at all
    AMBIGUOUS                   every other refusal the engine names

THE ASYMMETRY IS DELIBERATE. A missing zone polygon is PARTIAL, never FAIL: a
result that says "the geometry is unresolved" is honest and useful, and failing
it would push the system toward asserting what it cannot prove, which is the
exact behaviour section 8 forbids. What FAILS is SUBSTITUTION and CONTRADICTION -
showing the parcel as zoning proof, claiming one zone while the evidence shows
two, citing an exception nothing bound. Absence is a state. A lie is a failure.
"""
from __future__ import annotations

from typing import Optional

from services import deterministic_spatial as spatial

ACCEPTANCE_VERSION = "planning-acceptance@1"

# -- Section 12: acceptance states ------------------------------------------
PASS = "PASS"
PASS_WITH_UNRESOLVED_EXCEPTION = "PASS_WITH_UNRESOLVED_EXCEPTION"
PARTIAL = "PARTIAL"
FAIL = "FAIL"

#: Worst-first, because a result is only as good as its weakest qualified part.
STATE_SEVERITY = {FAIL: 3, PARTIAL: 2, PASS_WITH_UNRESOLVED_EXCEPTION: 1, PASS: 0}

# -- Section 4: parcel-to-zone relationship ---------------------------------
WITHIN_SINGLE_ZONE = "WITHIN_SINGLE_ZONE"
INTERSECTS_MULTIPLE_ZONES = "INTERSECTS_MULTIPLE_ZONES"
BOUNDARY_TOUCH = "BOUNDARY_TOUCH"
NO_QUALIFIED_ZONE_GEOMETRY = "NO_QUALIFIED_ZONE_GEOMETRY"
AMBIGUOUS = "AMBIGUOUS"

#: Section 9. An exception whose text nobody retrieved does not go away.
EXCEPTION_NONE = "NO_EXCEPTION_FLAGGED"
EXCEPTION_RESOLVED = "EXCEPTION_TEXT_RETRIEVED"
EXCEPTION_TEXT_UNRESOLVED = "EXCEPTION_TEXT_UNRESOLVED"

# -- Section 10: the automatic failures, each named so a report can cite one --
F_ZONE_LABEL_MISMATCH = "written conclusion names a zone the bound evidence does not carry"
F_EXCEPTION_UNBOUND = "written conclusion references an exception no evidence binds"
F_PARCEL_AS_ZONING = "the parcel polygon is presented as zoning geometry"
F_ZONING_OMITTED = "zoning geometry exists in evidence but no zoning panel was drawn"
F_MULTIZONE_REDUCED = "more than one zone applies but the prose claims one without qualification"
F_PROVENANCE_DIVERGED = "the evidence object and the written conclusion cite different sources"
F_EXCEPTION_STATUS_DIVERGED = "exception status differs between the visual and the prose"
F_CONTAINMENT_UNPROVEN = "a containment conclusion is stated that the spatial relation does not support"

#: Section 6. Present-or-absent is recorded per field rather than as one
#: boolean, because "no CRS" and "no source" are different audit answers and a
#: single `provenance_complete: False` tells a reader neither.
PARCEL_PROVENANCE_FIELDS = ("source", "layer", "retrieved_at", "spatial_reference",
                            "geometry_id", "parcel_identifier")
ZONING_PROVENANCE_FIELDS = ("source", "layer", "retrieved_at", "spatial_reference",
                            "geometry_id", "feature_identifier")

#: Section 11. Terms that name what the reader is looking at.
REQUIRED_LABELS = ("Subject Parcel", "Applicable Zoning", "Site-Specific Exception",
                   "Official Zoning Source")
#: Ambiguous unless further qualified - each of these describes a picture
#: without saying whether it is property or regulatory geography.
DISCOURAGED_LABELS = ("Property Map", "Zone Shape", "Official Shape")

#: A containment claim in prose. Matched as WORDS rather than by scanning for a
#: zone code, because the failure this guards is a SENTENCE asserting more than
#: the geometry proves, and the sentence is where that happens.
CONTAINMENT_PHRASES = ("lies within", "is contained within", "is located within",
                       "falls within", "is within")


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def zone_relationship(token, *, zone_count=None) -> str:
    """Section 4, projected from the governed token. Never computes geometry.

    `zone_count` is how many qualified zone polygons were found to apply. It is
    passed in rather than inferred because the retrieval knows it and this
    module must not guess: a result carrying one polygon may mean one zone
    applies, or may mean only one was asked for.
    """
    token = token or {}
    relation = token.get("spatial_relation")
    reason = token.get("reason")

    if zone_count is not None and zone_count > 1:
        # Takes precedence over the relation: a parcel can sit INSIDE one of two
        # overlapping zone polygons, and reporting WITHIN_SINGLE_ZONE there
        # would be true of the polygon and false of the property.
        return INTERSECTS_MULTIPLE_ZONES
    if not relation or relation == spatial.RELATION_NOT_APPLICABLE:
        return NO_QUALIFIED_ZONE_GEOMETRY
    if relation == spatial.RELATION_INSIDE:
        return WITHIN_SINGLE_ZONE
    if relation == spatial.RELATION_INTERSECTS:
        return INTERSECTS_MULTIPLE_ZONES
    if relation == spatial.RELATION_AMBIGUOUS:
        if reason == spatial.REASON_NEAR_BOUNDARY:
            return BOUNDARY_TOUCH
        if reason == spatial.REASON_MISSING:
            return NO_QUALIFIED_ZONE_GEOMETRY
        return AMBIGUOUS
    if relation == spatial.RELATION_OUTSIDE:
        # The zone polygon retrieved does not cover the parcel. That is not a
        # zone for this property, so there is no qualified zone geometry - and
        # saying AMBIGUOUS would imply the engine was unsure, which it was not.
        return NO_QUALIFIED_ZONE_GEOMETRY
    return AMBIGUOUS


def exception_status(retrieval) -> str:
    """Section 9. Flagged-but-unretrieved is a state, not a silence."""
    retrieval = retrieval or {}
    attributes = retrieval.get("zoning_attributes") or {}
    record = retrieval.get("exception") or {}
    flagged = attributes.get("ZN_EXCPTN") == "Y" or bool(record)
    if not flagged:
        return EXCEPTION_NONE
    if record.get("acquired") and (record.get("text") or record.get("record")):
        return EXCEPTION_RESOLVED
    return EXCEPTION_TEXT_UNRESOLVED


def _provenance(block, fields, *, retrieved_at) -> dict:
    block = dict(block or {})
    block.setdefault("retrieved_at", retrieved_at)
    return {field: block.get(field) or None for field in fields}


def parcel_evidence(result) -> dict:
    """Section 2A. The property boundary, as its own evidence identity."""
    retrieval = (result or {}).get("retrieval") or {}
    geometry = (retrieval.get("visual_geometry") or {}).get("parcel") or {}
    return {
        "geometry": geometry.get("geometry"),
        "qualified": bool(geometry.get("geometry")),
        "parcel_identifier": geometry.get("parcel_identifier"),
        "provenance": _provenance(geometry, PARCEL_PROVENANCE_FIELDS,
                                  retrieved_at=retrieval.get("retrieved_at")),
    }


def zoning_evidence(result) -> dict:
    """Section 2B. The regulatory polygon, and NEVER the parcel standing in.

    `zone_count` reads `zone_features` when the retrieval offers it and falls
    back to "one if a polygon is present". The fallback is honest about what it
    is: a retrieval that never asked how many zones intersect cannot report
    that none were missed, and `multi_zone_examined` says so.
    """
    retrieval = (result or {}).get("retrieval") or {}
    geometry = (retrieval.get("visual_geometry") or {}).get("zoning") or {}
    features = retrieval.get("zone_features")
    # EXAMINED IS ITS OWN FACT, not "a list was present". A retrieval whose zone
    # intersection query FAILED returns an empty list and must not be read as
    # "asked, and exactly one zone applies" - that is the silent reduction this
    # whole correction exists to remove.
    examined = bool(retrieval.get("zone_features_examined")) if (
        "zone_features_examined" in retrieval) else features is not None
    if examined and features is not None:
        # QUALIFIED only. A polygon the engine could not place, or one merely
        # touching the mapped edge, is retained as evidence but does not make a
        # property multi-zone - "touches a boundary" and "is split between two
        # regimes" are different findings with different consequences.
        count = len([f for f in features
                     if (f or {}).get("qualified") and (f or {}).get("geometry")])
    else:
        count = 1 if geometry.get("geometry") else 0
    attributes = retrieval.get("zoning_attributes") or {}
    return {
        "geometry": geometry.get("geometry"),
        "qualified": bool(geometry.get("geometry")),
        "zone_count": count,
        "multi_zone_examined": examined,
        "zone_label": attributes.get("ZN_STRING"),
        "zone_code": attributes.get("ZN_ZONE"),
        "exception_identifier": attributes.get("ZN_EXCPTN_NO"),
        "provenance": _provenance(geometry, ZONING_PROVENANCE_FIELDS,
                                  retrieved_at=retrieval.get("retrieved_at")),
    }


def _zoning_panels(panels) -> list:
    from services import planning_visual

    return [p for p in (panels or [])
            if p.get("kind") == planning_visual.PANEL_ZONING]


def _parcel_panels(panels) -> list:
    from services import planning_visual

    return [p for p in (panels or [])
            if p.get("kind") == planning_visual.PANEL_PARCEL]


def _statements(result) -> list:
    document = (result or {}).get("document") or {}
    return [s for s in (document.get("statements") or []) if isinstance(s, dict)]


#: TOPIC IS THE SELECTOR, and that is a correction rather than a preference.
#: The runner tags its zone statements `spatial_layer="zoning_area"`, but the
#: FINISHED document does not carry that field - `go_pdz_lifecycle` builds
#: contract statements whose keys are topic / kind / statement_status /
#: spatial_relation, and `spatial_layer` is not among them. Selecting on it
#: alone would have matched NOTHING on a real result, leaving every prose check
#: silently satisfied: a false PASS, which is the one outcome an acceptance test
#: may never produce. Verified against a live 1 Cassidy Pl retrieval.
ZONING_TOPICS = ("ZONING_DESIGNATION", "DENSITY", "SITE_SPECIFIC_EXCEPTION")


def _zoning_statements(result) -> list:
    return [s for s in _statements(result)
            if s.get("topic") in ZONING_TOPICS
            or s.get("spatial_layer") == "zoning_area"]


def evaluate(result, *, panels=None) -> dict:
    """Section 10 and 12. Read a finished result; return one acceptance record.

    EVERY FAILURE IS A NAMED CONDITION WITH ITS EVIDENCE ATTACHED, never a bare
    boolean - an acceptance test whose output is "FAIL" tells the person nothing
    about which of seven things went wrong, and the whole value here is telling
    them exactly which.
    """
    result = result or {}
    retrieval = result.get("retrieval") or {}
    parcel = parcel_evidence(result)
    zoning = zoning_evidence(result)
    tokens = result.get("spatial_tokens") or {}
    token = tokens.get("zoning_area") or {}

    relationship = zone_relationship(
        token, zone_count=zoning["zone_count"] if zoning["multi_zone_examined"]
        else None)
    exception = exception_status(retrieval)
    statements = _zoning_statements(result)
    prose = " ".join(_text(s.get("text")) for s in statements)

    failures = []

    def fail(code, **evidence):
        failures.append(dict(code=code, **evidence))

    # -- substitution: the rule this module exists for ----------------------
    for panel in _zoning_panels(panels):
        drawn = panel.get("geometry_id") or panel.get("evidence_ref")
        if (parcel["provenance"].get("geometry_id")
                and drawn == parcel["provenance"]["geometry_id"]
                and drawn != zoning["provenance"].get("geometry_id")):
            fail(F_PARCEL_AS_ZONING, panel=panel.get("title"),
                 geometry_id=drawn)
    if not zoning["qualified"]:
        for panel in _parcel_panels(panels):
            title = _text(panel.get("title")).lower()
            if "zoning" in title or "zone" in title:
                fail(F_PARCEL_AS_ZONING, panel=panel.get("title"),
                     note="parcel panel titled as zoning while no zone geometry exists")

    # -- omission -----------------------------------------------------------
    if zoning["qualified"] and panels is not None and not _zoning_panels(panels):
        fail(F_ZONING_OMITTED, geometry_id=zoning["provenance"].get("geometry_id"))

    # -- label binding ------------------------------------------------------
    label = zoning["zone_label"] or zoning["zone_code"]
    if label and prose and label not in prose:
        # Only checked when the evidence HAS a label: a result with no label is
        # incomplete, not contradictory, and PARTIAL already says that.
        fail(F_ZONE_LABEL_MISMATCH, evidence_label=label)
    if prose and not zoning["qualified"] and label and label in prose:
        # Section 8: a label may still be stated, but not as though geometry
        # backed it. That is only a failure if the prose ALSO claims containment,
        # which the containment check below catches - so nothing is raised here.
        pass

    # -- multi-zone ---------------------------------------------------------
    if zoning["zone_count"] > 1:
        qualified_prose = any(
            s.get("multi_zone_qualified") or "more than one zone" in _text(s.get("text")).lower()
            or "multiple zones" in _text(s.get("text")).lower()
            for s in statements)
        if not qualified_prose:
            fail(F_MULTIZONE_REDUCED, zone_count=zoning["zone_count"])

    # -- containment eligibility (section 7) --------------------------------
    claims_containment = any(phrase in prose.lower() for phrase in CONTAINMENT_PHRASES)
    if claims_containment and relationship != WITHIN_SINGLE_ZONE:
        fail(F_CONTAINMENT_UNPROVEN, relationship=relationship,
             spatial_relation=token.get("spatial_relation"),
             reason=token.get("reason"))

    # -- exception ----------------------------------------------------------
    mentions_exception = "exception" in prose.lower()
    if mentions_exception and exception == EXCEPTION_NONE:
        fail(F_EXCEPTION_UNBOUND)
    panel_exception = None
    for panel in _zoning_panels(panels):
        if panel.get("exception_status"):
            panel_exception = panel["exception_status"]
    if panel_exception and panel_exception != exception:
        fail(F_EXCEPTION_STATUS_DIVERGED, panel=panel_exception, evidence=exception)

    # -- provenance ---------------------------------------------------------
    for panel in _zoning_panels(panels):
        panel_source = panel.get("source")
        evidence_source = zoning["provenance"].get("source")
        if panel_source and evidence_source and panel_source != evidence_source:
            fail(F_PROVENANCE_DIVERGED, panel=panel_source,
                 evidence=evidence_source)

    missing_provenance = sorted(
        [f for f, v in parcel["provenance"].items() if v is None]
        + [f for f, v in zoning["provenance"].items() if v is None and zoning["qualified"]])

    state = _state(parcel, zoning, relationship, exception, failures,
                   missing_provenance)
    return {
        "acceptance_version": ACCEPTANCE_VERSION,
        "state": state,
        "relationship": relationship,
        "exception_status": exception,
        "parcel": parcel,
        "zoning": zoning,
        "failures": failures,
        "missing_provenance": missing_provenance,
        "spatial_token": token or None,
    }


def _state(parcel, zoning, relationship, exception, failures,
           missing_provenance) -> str:
    """Section 12, in the order the directive states them."""
    if failures:
        return FAIL
    if not parcel["qualified"]:
        # Nothing can be qualified without the property boundary. Not a FAIL,
        # because nothing was claimed falsely - there is simply no result.
        return PARTIAL
    if relationship in (NO_QUALIFIED_ZONE_GEOMETRY, AMBIGUOUS, BOUNDARY_TOUCH):
        return PARTIAL
    if missing_provenance:
        # Section 6 requires provenance to remain auditable. Incomplete
        # provenance is a PARTIAL rather than a FAIL: nothing is contradicted,
        # but the chain cannot be audited end to end.
        return PARTIAL
    if exception == EXCEPTION_TEXT_UNRESOLVED:
        return PASS_WITH_UNRESOLVED_EXCEPTION
    return PASS


def label_review(rendered_text) -> dict:
    """Section 11. Reports on wording; decides nothing.

    Deliberately separate from `evaluate`: a result whose evidence is sound and
    whose labels are vague is not a failed result, and folding vocabulary into
    the acceptance state would make a copy edit look like an evidence defect.
    """
    text = _text(rendered_text)
    return {
        "present": [label for label in REQUIRED_LABELS if label in text],
        "missing": [label for label in REQUIRED_LABELS if label not in text],
        "discouraged_present": [label for label in DISCOURAGED_LABELS
                                if label in text],
    }


def summarize(record) -> str:
    """One line a person can read, for a report or a log."""
    record = record or {}
    if record.get("state") == PASS:
        return "PASS - %s, exception %s" % (record.get("relationship"),
                                            record.get("exception_status"))
    reasons = "; ".join(f["code"] for f in record.get("failures") or [])
    return "%s - %s%s" % (record.get("state"), record.get("relationship"),
                          (" - " + reasons) if reasons else "")
