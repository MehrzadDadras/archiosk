"""CLAUDE-GO-PDZ-AUTHORITY-01 - an authority-source seam, not web research.

    A SEARCH RESULT IS NOT AN AUTHORITY. A CONSULTANT SUMMARY IS NOT AN AUTHORITY.

GO-PDZ's VR-04 and VR-07 require every AUTHORITY_SAYS statement to name a
retrievable authority with a status and a date. Nothing in ARCHIOSK could supply
one, which is why the blind 35 Taber run had to be performed outside the
application. This is the seam that fixes that, and its defining property is the
allowlist: retrieval is confined to official public-authority sources, and
anything else can inform DISCOVERY but can never satisfy AUTHORITY_SAYS.

THE DISTINCTION THAT DOES THE WORK:

    OFFICIAL   -> may satisfy AUTHORITY_SAYS
    SECONDARY  -> may help you find the official source, and nothing more
    REJECTED   -> not retrieved at all

A law-firm bulletin explaining that PPS 2024 came into force on 20 October 2024
is genuinely useful and is not the Provincial Planning Statement. Classifying it
as SECONDARY rather than blocking it keeps it usable for discovery while making
it structurally incapable of becoming the authority a result rests on.

READ-ONLY AND INJECTABLE. `acquire()` takes a `fetcher`, and every test supplies
one. Nothing here reaches the network by default, which is what lets the seam be
exercised hermetically - the discipline `CLAUDE.md` already requires of any path
that can touch an external service.

AN AUTHORITY IS NOT ITS PROSE. Section 2 is explicit that a record must retain a
stable representation and a provenance hash, not merely extracted text. A
paraphrase cannot be re-checked against the source later, and "the by-law says
14 metres" with no retained bytes is an assertion about a document rather than a
citation of one.

CURRENT IS NOT THE SAME AS APPLICABLE. `CURRENT`, `HISTORICAL`, `SUPERSEDED` and
`UNKNOWN` are tracked separately from the retrieval date, because the state that
caught out the blind reconnaissance was neither current nor historical: Toronto's
OPA 804 is ADOPTED and awaiting ministerial approval. Treating it as binding and
ignoring it are both wrong, and only a vocabulary with that state in it can say
so.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ACQUISITION_METHOD = "public_planning_authority"
ACQUISITION_VERSION = "planning-authority@1"

CLASS_OFFICIAL = "OFFICIAL"
CLASS_SECONDARY = "SECONDARY"
CLASS_REJECTED = "REJECTED"

#: Applicability, tracked apart from retrieval time. `ADOPTED_NOT_IN_FORCE` is
#: the state that matters most and is easiest to lose.
APPLICABILITY_CURRENT = "CURRENT"
APPLICABILITY_ADOPTED_NOT_IN_FORCE = "ADOPTED_NOT_IN_FORCE"
APPLICABILITY_HISTORICAL = "HISTORICAL"
APPLICABILITY_SUPERSEDED = "SUPERSEDED"
APPLICABILITY_UNKNOWN = "UNKNOWN"

#: Official public-authority hosts and host suffixes. An entry here is a claim
#: that the domain is operated BY a public authority - not that its content is
#: correct, and not that every page on it is a governing instrument.
OFFICIAL_HOST_SUFFIXES = (
    ".gc.ca",                 # Government of Canada
    ".gov.on.ca", ".ontario.ca",
    "ero.ontario.ca",
    ".toronto.ca",
    ".mississauga.ca", ".brampton.ca", ".vaughan.ca", ".markham.ca",
    ".oakville.ca", ".burlington.ca", ".hamilton.ca", ".ottawa.ca",
    ".bracebridge.ca", ".orillia.ca", ".cornwall.ca",
    "trca.ca", ".trca.ca",
    ".conservationontario.ca",
    ".arcgis.com",            # official ArcGIS/Open Data endpoints
    ".opendata.arcgis.com",
)

#: Hosts that are informative but never authority. Listed explicitly so the
#: classification is a stated decision rather than a fall-through.
SECONDARY_HOST_HINTS = (
    "wikipedia.org", "mondaq.com", "lexology.com", "blg.com", "mcmillan.ca",
    "airdberlis.com", "overlandllp.ca", "davieshowe.com", "dekrupelaw.ca",
    "insightlawfirm.ca",
)

#: Real-estate and listing sites, blogs and aggregators. Not retrieved at all -
#: they add discovery noise without adding discovery value for this purpose.
REJECTED_HOST_HINTS = (
    "realtor.ca", "zolo.ca", "housesigma.com", "zillow.com", "redfin.com",
    "blogspot.", "wordpress.com", "medium.com", "reddit.com", "facebook.com",
    "x.com", "twitter.com", "pinterest.",
)

#: An ArcGIS/Open Data path that returns machine-readable geometry rather than a
#: rendered map image. Preferred for the spatial seam - see section 7.
_GEOMETRY_PATH = re.compile(
    r"/(?:FeatureServer|MapServer)/\d+/query|/arcgis/rest/|geojson|\.geojson$",
    re.IGNORECASE)


def classify_source(url: Optional[str]) -> dict:
    """OFFICIAL, SECONDARY or REJECTED, with the reason stated."""
    if not url or not isinstance(url, str):
        return {"source_class": CLASS_REJECTED, "host": None,
                "reason": "no locator supplied"}
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001 - an unparseable locator is a result
        return {"source_class": CLASS_REJECTED, "host": None,
                "reason": "locator could not be parsed"}
    host = (parsed.hostname or "").lower()
    if not host:
        return {"source_class": CLASS_REJECTED, "host": None,
                "reason": "locator carries no host"}
    if parsed.scheme not in ("http", "https"):
        return {"source_class": CLASS_REJECTED, "host": host,
                "reason": "only http(s) locators are retrieved"}

    for hint in REJECTED_HOST_HINTS:
        if hint in host:
            return {"source_class": CLASS_REJECTED, "host": host,
                    "reason": "host is a listing, blog or social source"}
    for hint in SECONDARY_HOST_HINTS:
        if hint in host:
            return {"source_class": CLASS_SECONDARY, "host": host,
                    "reason": "informative source; may aid discovery but is "
                              "never the governing authority"}
    for suffix in OFFICIAL_HOST_SUFFIXES:
        if host == suffix.lstrip(".") or host.endswith(suffix):
            return {"source_class": CLASS_OFFICIAL, "host": host,
                    "reason": "host is operated by a public authority",
                    "machine_readable_geometry": bool(
                        _GEOMETRY_PATH.search(parsed.path or ""))}
    return {"source_class": CLASS_SECONDARY, "host": host,
            "reason": "host is not on the official allowlist; discovery only"}


def provenance_hash(payload) -> Optional[str]:
    """A hash of what was actually retrieved, so a record can be re-checked."""
    if payload is None:
        return None
    if isinstance(payload, str):
        payload = payload.encode("utf-8", "replace")
    if not isinstance(payload, (bytes, bytearray)):
        return None
    return "sha256:" + hashlib.sha256(bytes(payload)).hexdigest()


def authority_record(*, authority_id, issuing_authority, official_title, url,
                     retrieved_at, payload=None, effective_date=None,
                     version_identifier=None,
                     applicability=APPLICABILITY_UNKNOWN, jurisdiction=None,
                     spatial_scope=None, provision_locator=None,
                     amendment_history=None, retained_representation=None) -> dict:
    """One acquired authority, with everything section 2 requires retained.

    `source_class` is computed rather than supplied: a caller must not be able
    to declare a blog official by passing a field.
    """
    classification = classify_source(url)
    return {
        "authority_id": authority_id,
        "issuing_authority": issuing_authority,
        "official_title": official_title,
        "url": url,
        "source_class": classification["source_class"],
        "source_class_reason": classification["reason"],
        "host": classification["host"],
        "machine_readable_geometry": classification.get(
            "machine_readable_geometry", False),
        "retrieved_at": retrieved_at,
        "effective_date": effective_date,
        "version_identifier": version_identifier,
        "applicability": applicability,
        "jurisdiction": jurisdiction,
        "spatial_scope": spatial_scope,
        "provision_locator": provision_locator,
        "amendment_history": list(amendment_history or []),
        # NOT only extracted prose - section 2. Either the bytes or a stable
        # retained pointer to them, plus a hash of what was actually seen.
        "retained_representation": retained_representation,
        "provenance_hash": provenance_hash(payload),
        "acquisition_method": ACQUISITION_METHOD,
        "acquisition_version": ACQUISITION_VERSION,
    }


def may_satisfy_authority_says(record) -> bool:
    """Only an OFFICIAL source, actually retrieved, can ground AUTHORITY_SAYS."""
    if not isinstance(record, dict):
        return False
    if record.get("source_class") != CLASS_OFFICIAL:
        return False
    # A record with no hash and no retained representation is a paraphrase.
    return bool(record.get("provenance_hash")
                or record.get("retained_representation"))


def acquire(url, *, fetcher, authority_id, issuing_authority, official_title,
            retrieved_at, **fields) -> dict:
    """Retrieve one authority through an injected reader. Never raises.

    READ-ONLY BY CONSTRUCTION: `fetcher` is the only way bytes enter, there is no
    default, and nothing here writes to any store. A REJECTED host is not
    fetched at all - the classification happens before the call, not after.
    """
    classification = classify_source(url)
    if classification["source_class"] == CLASS_REJECTED:
        return {
            "acquired": False, "url": url,
            "source_class": CLASS_REJECTED,
            "reason": classification["reason"],
            "record": None,
        }
    try:
        payload = fetcher(url)
    except Exception as exc:  # noqa: BLE001 - a failed retrieval is a result
        logger.warning("authority retrieval failed for %s (%s: %s)",
                       url, type(exc).__name__, exc)
        return {"acquired": False, "url": url,
                "source_class": classification["source_class"],
                "reason": "%s: %s" % (type(exc).__name__, exc), "record": None}
    if payload is None:
        return {"acquired": False, "url": url,
                "source_class": classification["source_class"],
                "reason": "retrieval returned nothing", "record": None}

    record = authority_record(
        authority_id=authority_id, issuing_authority=issuing_authority,
        official_title=official_title, url=url, retrieved_at=retrieved_at,
        payload=payload, **fields)
    return {"acquired": True, "url": url,
            "source_class": record["source_class"],
            "reason": classification["reason"], "record": record}


def unresolved_exception(exception_id, *, indicated_by, missing_authority,
                         development_effect, required_next_evidence) -> dict:
    """A site-specific exception whose text could not be retrieved. FAILS CLOSED.

    Section 4, and the one rule this whole programme keeps returning to: an
    exception exists to DISPLACE the parent standard, so falling back to the
    parent standard because the exception could not be read inverts the single
    fact that was established. The record says what is missing and what it would
    change, so the gap is actionable rather than merely admitted.
    """
    return {
        "exception_id": exception_id,
        "indicated_by": indicated_by,
        "text_retrieved": False,
        "authority_ref": None,
        "missing_authority": missing_authority,
        "development_effect": development_effect,
        "required_next_evidence": required_next_evidence,
    }
