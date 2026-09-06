"""CLAUDE-HELP-CLIP-STUDIO-01 - one scenario in, one governed DRAFT clip out.

WHAT CHANGED, AND WHAT DELIBERATELY DID NOT

The authoring surface built before this was kernel-facing: a reviewer had to
record a Claim, then a narrative unit, then bind one to the other, then re-check
- four correct governance acts standing between a person and the thing they
actually wanted, which was to explain Survival Mode to a new user. This module
moves that construction work to the machine. It does NOT move any of it out of
governance. Every object the generator writes is written through the same
`services/help_mode.py` primitives a human uses, lands in the same reserved
`archiosk-help-library` workspace, and faces the same gate.

The distinction worth keeping in view: this makes the machinery INVISIBLE, not
ABSENT. A generated Script is DRAFT, exactly like a hand-authored one, and
reaches REUSABLE only through the same two human acts. Generation is a
convenience for producing candidates, never a shortcut through the gate - and
the way that is guaranteed is that nothing here calls a validation, adoption or
promotion method. There is no code path from this module to REUSABLE.

WHERE HELP EVIDENCE COMES FROM

The published Help guides. They are the governed, human-written, already-shipped
statements of how ARCHIOSK behaves, which makes them the honest grounding
material for a Help Clip - and using anything else would mean a Help answer
resting on something no one had reviewed. Their prose is registered as ordinary
Sources and EvidenceItems in the Help Library, so a generated Script cites real
evidence through the ordinary citation mechanism rather than through a special
"help content" path that would need its own provenance rules.

The registration is idempotent by source name and re-registers a guide whose
text has changed, so the library tracks the guides rather than snapshotting them
once and quietly going stale. A superseded revision is left in place rather than
deleted: `resolve_claim_status` reads exactly that to decide a claim is stale, so
throwing it away would destroy the signal that tells a reviewer their Script now
rests on prose that has since been rewritten.

NO CUSTOMER PROJECT CONTEXT

Every store access here resolves `HELP_LIBRARY_PROJECT_ID` and nothing else.
There is no project_id parameter to pass, so there is no call that could reach a
customer workspace - the isolation is structural rather than a rule this module
has to remember, which is the same shape `services/help_mode.py` already uses
for the Help/Project boundary.

NOT A RENDERER

`clip_package` assembles everything a downstream presentation renderer needs and
renders nothing. No video encoder, no 2D/3D geometry, no timeline. The Script
stays the governed source of record and presentation stays downstream of it;
building a renderer here would have inverted that and made the artifact
authoritative instead of the Script.
"""
from __future__ import annotations

import html as _html
import re
from html.parser import HTMLParser
from typing import Callable, Optional

from services.case_workspace import (
    CaseWorkspaceStore,
    CLAIM_CLASS_DIRECTLY_VERIFIED,
    CLAIM_CLASS_UNKNOWN,
    CONFIDENCE_STATE_INSUFFICIENT_EVIDENCE,
    CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
    ProjectWorkspace,
    SCRIPT_CHECK_PASS,
)
from services.help_mode import (
    HELP_LIBRARY_PROJECT_ID,
    HelpModeError,
    add_help_claim,
    add_help_script_direction,
    add_help_script_scene,
    create_help_script,
)

# Guide prose is registered under this name prefix so the Help Library's own
# sources are identifiable as guide-derived without a second registry mapping
# them - the name IS the mapping.
HELP_SOURCE_PREFIX = "help-guide:"
HELP_SOURCE_EXTRACTOR = "help-guide-text/1"

# How much governed material one compilation is shown. Enough for the model to
# find the relevant passages, bounded so a growing library cannot silently turn
# one generation into an enormous request.
EVIDENCE_SELECTION_LIMIT = 24

# Block-level tags whose boundaries are real paragraph breaks. The extractor
# below splits on these so `register_plain_text_structure` sees the guide's own
# paragraphs rather than one undifferentiated wall of text - each becomes a
# separately addressable EvidenceItem, which is what lets a claim cite the
# sentence it actually rests on instead of a whole page.
_BLOCK_TAGS = frozenset({
    "p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "dt", "dd",
    "section", "article", "header", "footer", "div", "tr", "figcaption",
})
_SKIP_TAGS = frozenset({"script", "style", "head", "title", "nav"})


class _GuideTextExtractor(HTMLParser):
    """Visible guide prose, one paragraph per block element.

    `services/external_intelligence_airlock.py` has a text extractor already and
    this is deliberately not it: that one collapses ALL whitespace into single
    spaces, which is right for comparing a legal provision and wrong here, where
    the blank lines are the paragraph boundaries the evidence split depends on.
    Reusing it would have produced one giant EvidenceItem per guide.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._blocks: list[list[str]] = [[]]
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS or tag == "br":
            self._blocks.append([])

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag in _BLOCK_TAGS:
            self._blocks.append([])

    def handle_data(self, data):
        if not self._skip_depth:
            self._blocks[-1].append(data)

    def paragraphs(self) -> list[str]:
        out = []
        for block in self._blocks:
            text = " ".join("".join(block).split())
            if text:
                out.append(text)
        return out


def guide_text(markup: str) -> str:
    """Rendered guide HTML as blank-line-delimited paragraphs."""
    parser = _GuideTextExtractor()
    parser.feed(_html.unescape(str(markup or "")))
    return "\n\n".join(parser.paragraphs())


def guide_documents(render: Callable[[str], str], guides: dict) -> list[dict]:
    """Turn the closed guide set into registrable documents.

    Takes the renderer rather than importing Flask: the guides are Jinja
    templates and only the app can render them, but nothing else in this module
    needs a request context and threading one through would make the whole
    service untestable without an app.

    Renders the PUBLISHED guide, not the template file. What a reader is
    actually shown is what a Help answer should rest on - a template carries
    conditionals and comments that no reader ever sees, and grounding a claim in
    an unrendered branch would cite something that is not on the page.
    """
    documents = []
    for key, entry in guides.items():
        try:
            markup = render(entry["template"])
        except Exception:  # noqa: BLE001 - one broken guide must not stop the rest
            continue
        text = guide_text(markup)
        if not text.strip():
            continue
        documents.append({
            "key": key,
            "name": "%s%s" % (HELP_SOURCE_PREFIX, key),
            "title": entry.get("title") or key,
            "text": text,
        })
    return documents


def ensure_help_sources(
    store: CaseWorkspaceStore, documents: list[dict], actor: str = "help-clip-studio",
) -> dict:
    """Register or refresh the Help Library's governed guide evidence.

    Idempotent on unchanged text, so opening the Studio does not grow the
    library on every visit. When a guide's text HAS changed, a new revision is
    registered through `register_source_revision` rather than the old evidence
    being edited in place - that is the mechanism `resolve_claim_status` already
    reads to mark a claim stale, so a Script resting on rewritten prose surfaces
    as needing re-review instead of silently continuing to look checked.
    """
    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    registered, refreshed, unchanged = [], [], []

    for document in documents:
        existing = _live_source_named(workspace, document["name"])
        if existing is not None:
            if _source_text(store, workspace, existing["id"]) == document["text"]:
                unchanged.append(existing["id"])
                continue
            source = store.register_source_revision(
                workspace, superseded_source_id=existing["id"], name=document["name"],
                file_path=document["name"], kind="document", actor=actor,
            )
            refreshed.append(source["id"])
        else:
            source = store.add_source(
                workspace, name=document["name"], file_path=document["name"],
                kind="document", actor=actor,
            )
            registered.append(source["id"])

        store.register_plain_text_structure(
            workspace, source["id"], document["text"],
            extractor_version=HELP_SOURCE_EXTRACTOR, actor=actor,
        )
        workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)

    return {"registered": registered, "refreshed": refreshed, "unchanged": unchanged}


def _live_source_named(workspace: ProjectWorkspace, name: str) -> Optional[dict]:
    """The current, non-superseded Source with this name, if any."""
    for source in workspace.sources:
        if source.get("name") == name and not source.get("superseded_by_source_id"):
            return source
    return None


def _source_text(store: CaseWorkspaceStore, workspace: ProjectWorkspace, source_id: str) -> str:
    items = [item for item in workspace.evidence_items if item.get("source_id") == source_id]
    return "\n\n".join(str(item.get("content", "")).strip() for item in items)


_WORD = re.compile(r"[a-z0-9]+")
# Words that match everything and therefore separate nothing. Deliberately
# short: an aggressive stop list starts discarding real ARCHIOSK vocabulary.
_NOISE = frozenset({
    "the", "and", "for", "that", "this", "with", "from", "what", "when", "where",
    "which", "into", "have", "has", "are", "was", "were", "not", "but", "you",
    "your", "user", "show", "explain", "make", "clear", "about", "them", "they",
    "its", "it", "a", "an", "of", "to", "in", "on", "is", "be", "as", "at", "or",
})


def _terms(text: str) -> set:
    return {word for word in _WORD.findall(str(text or "").lower())
            if len(word) > 2 and word not in _NOISE}


def select_help_evidence(
    store: CaseWorkspaceStore, scenario: str, limit: int = EVIDENCE_SELECTION_LIMIT,
) -> list[dict]:
    """The governed Help evidence most likely to bear on this scenario.

    Deterministic term overlap, not a model call and not an embedding index.
    Two reasons, in order: selection happening before the model means a model
    cannot choose its own evidence, which is what keeps grounding honest; and
    `tools/dependency_fit.py` already settles that a vector store is not a
    dependency this repository takes. Overlap is weaker retrieval and entirely
    adequate at Help-library scale, where the corpus is a handful of guides.

    Only superseded-free Help Library evidence is considered. There is no
    parameter by which a customer project's evidence could enter.
    """
    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    wanted = _terms(scenario)
    if not wanted:
        return []

    live_sources = {
        source["id"]: source for source in workspace.sources
        if not source.get("superseded_by_source_id")
    }

    scored = []
    for item in workspace.evidence_items:
        source = live_sources.get(item.get("source_id"))
        if source is None:
            continue
        text = str(item.get("content", "")).strip()
        if not text:
            continue
        overlap = len(wanted & _terms(text))
        if overlap:
            scored.append((overlap, len(text), item["id"], text, source.get("name")))

    # Overlap first; then the shorter passage, because a tight sentence is
    # better evidence for one claim than a long one that happens to contain it.
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [{"id": item_id, "text": text, "source": name}
            for _, _, item_id, text, name in scored[:limit]]


def help_ui_ref_catalogue(store: CaseWorkspaceStore) -> list:
    """Stable UI identities a generated direction is allowed to target.

    Sourced from refs a reviewer has already bound to Help Scripts, so the
    catalogue grows by curation rather than by a model naming controls it
    imagines. Empty is a supported state and simply yields directions with no
    target - the instruction survives, the highlight waits for a binding.

    Deliberately NOT parsed from UI_REFERENCE_MAP.md: that would make a Markdown
    document a runtime dependency of generation, and a malformed document would
    then break authoring rather than a test.
    """
    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    refs = []
    for script in workspace.work_products:
        for ref in (script.get("help_ui_refs") or []):
            if ref not in refs:
                refs.append(str(ref))
    return refs


class ClipGenerationError(HelpModeError):
    """Generation could not produce a candidate at all."""


def generate_help_clip(
    store: CaseWorkspaceStore,
    scenario: str,
    actor: str,
    policy_decision: str,
    title: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
) -> dict:
    """One scenario in; one governed DRAFT Help Script out.

    The order matters and is not arbitrary. Evidence is selected FIRST, by code,
    so the model is grounded in material it did not choose. It then proposes
    content. Every proposed evidence id is re-resolved against the workspace
    before anything is written, so a hallucinated citation becomes a missing
    binding - which the structural gate then fails honestly - rather than a
    fabricated one that would look fine. Only then is the trust chain run, ONCE,
    at this deliberate checkpoint.

    WHAT THIS CANNOT DO. Validate, adopt, promote, publish. Not by policy but by
    construction: the only store methods reachable from here create a Script,
    record claims and scenes, and read readiness. A generated Script is DRAFT
    and stays DRAFT until a human acts.
    """
    from services.cross_modal_investigation import compile_help_scenario
    from services.script_fit import run_script_trust_chain

    scenario = (scenario or "").strip()
    if not scenario:
        raise ClipGenerationError("A Help Clip needs a scenario to work from.")

    evidence = select_help_evidence(store, scenario)
    compilation = compile_help_scenario(
        scenario, evidence, ui_ref_catalogue=help_ui_ref_catalogue(store),
        api_key=api_key, model=model, timeout=timeout,
    )
    if not compilation.ran:
        raise ClipGenerationError(compilation.reason)

    script = create_help_script(
        store, question=compilation.question,
        title=(title or "").strip() or compilation.title, actor=actor,
    )
    script_id = script["id"]

    known_evidence = {item["id"] for item in evidence}
    claim_ids, ungrounded = [], []
    for proposed in compilation.claims:
        bound = [eid for eid in proposed["evidence_ids"] if eid in known_evidence]
        # An ungrounded proposal is recorded as the kernel's own honest
        # abstention - `unknown` class, insufficient evidence - not as a
        # directly-verified claim with nothing under it. The kernel refuses the
        # latter outright, and it is right to: a claim citing no evidence that
        # is dressed as verified is the exact shape of a laundered assertion.
        # Recording it rather than dropping it keeps the gap visible; the
        # structural gate then fails the Script honestly, which is the point.
        claim = add_help_claim(
            store, script_id=script_id, statement=proposed["statement"],
            actor=actor, evidence_item_ids=bound,
            claim_class=CLAIM_CLASS_DIRECTLY_VERIFIED if bound else CLAIM_CLASS_UNKNOWN,
            confidence_state=(CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT if bound
                              else CONFIDENCE_STATE_INSUFFICIENT_EVIDENCE),
        )
        claim_ids.append(claim["id"])
        if not bound:
            ungrounded.append(proposed["statement"])

    for scene in compilation.scenes:
        add_help_script_scene(
            store, script_id=script_id, text=scene["text"], actor=actor,
            claim_ids=[claim_ids[i] for i in scene["claim_indexes"] if i < len(claim_ids)],
        )

    # Directions AFTER scenes so the narration is the Script's spine and the
    # pointing follows it. They carry no claims by construction.
    for direction in compilation.directions:
        add_help_script_direction(
            store, script_id=script_id, ui_refs=direction["ui_refs"], actor=actor,
            action=direction["action"], text=direction["text"],
        )

    store.record_script_scenario(
        store.get_or_create(HELP_LIBRARY_PROJECT_ID), work_product_id=script_id,
        scenario=scenario, actor=actor,
        compiled_by=compilation.provider, model=compilation.model,
        unsupported=list(compilation.unsupported), ungrounded=ungrounded,
    )

    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    chain = run_script_trust_chain(
        store, workspace, work_product_id=script_id, policy_decision=policy_decision,
        api_key=api_key, model=model, timeout=timeout,
    )

    return {
        "script_id": script_id,
        "chain": chain,
        "unsupported": list(compilation.unsupported),
        "ungrounded": ungrounded,
        "evidence_considered": len(evidence),
    }


def clip_package(store: CaseWorkspaceStore, script_id: str) -> Optional[dict]:
    """Everything a downstream presentation renderer will need, and no rendering.

    ACTION 9's "full Help Clip" for this phase. The Script remains the governed
    source of record; this is a read-only projection of it plus the source and
    trust-chain context a renderer would otherwise have to re-derive - and
    re-deriving it is exactly how a renderer would end up with its own, drifting
    idea of whether a clip was ready to show.
    """
    from services.help_mode import help_script_detail
    from services.script_fit import help_status_for

    detail = help_script_detail(store, script_id)
    if detail is None:
        return None

    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    script = store.get_work_product(workspace, script_id)
    sources, captions = {}, []

    for scene in detail["scenes"]:
        for claim_id in scene["claim_ids"]:
            claim = store.get_claim(workspace, claim_id)
            if claim is None:
                continue
            for link in claim.get("evidence_links", []):
                if link.get("object_type") != "evidence_item":
                    continue
                item = store.get_evidence_item(workspace, link["object_id"])
                if item is None:
                    continue
                source = store._find(workspace.sources, item.get("source_id"))
                if source is not None:
                    sources[source["id"]] = _readable_source_name(source.get("name"))
        captions.append({"order": scene["order_index"], "text": scene["text"]})

    # WHAT IT SAYS and WHERE TO SHOW IT, surfaced separately. A renderer needs
    # both; conflating them is how a highlight target would start reading as a
    # supporting citation.
    visual_targets = [{
        "order": d["order_index"], "action": d["action"],
        "ui_refs": d["ui_refs"], "text": d["text"],
    } for d in detail["directions"]]

    scenario = (script or {}).get("script_scenario") or {}
    return {
        "visual_targets": visual_targets,
        "script_id": script_id,
        "scenario": scenario.get("scenario"),
        "title": detail["title"],
        "question": detail["question"],
        "scenes": detail["scenes"],
        "captions": captions,
        "sources": sorted(sources.values()),
        "status": detail["status"],
        "readiness": detail["readiness"],
        "checks": detail["checks"],
        "reasons": detail["reasons"],
        "verdicts": detail["verdicts"],
        "stale": detail["stale"],
        "unsupported": scenario.get("unsupported") or [],
        "ungrounded": scenario.get("ungrounded") or [],
        "ready_to_present": detail["checks"].get("human_validation") == SCRIPT_CHECK_PASS,
    }


def _readable_source_name(name: Optional[str]) -> str:
    """"help-guide:spin-and-survival-modes" -> "Spin and survival modes"."""
    text = str(name or "").strip()
    if text.startswith(HELP_SOURCE_PREFIX):
        text = text[len(HELP_SOURCE_PREFIX):]
    text = text.replace("-", " ").replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else "Unnamed source"
