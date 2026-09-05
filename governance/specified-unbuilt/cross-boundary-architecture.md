# Specified But Unbuilt — Cross-Boundary Architecture

**Status:** Specified, not implemented.

> **Governing addition, 2026-09-05 — [`GOV-P-004`](../records/GOV-P-004.md) v1.0,
> "Decoupled Two-Sided Procurement Foundation" (`CURRENT`).** Nothing in this
> document is superseded, narrowed, or corrected; every statement below remains in
> force. `GOV-P-004` states the layer this document left unstated — that Owner and
> Proponent are not merely separate *Projects* but separate *deployments* sharing no
> application, network, runtime, or database, with the issued data room package
> (documents, a zip, or a structured export, moved out-of-band) as the only boundary
> object, and with neither mode depending on the counterparty running ARCHIOSK. Read
> the two together: this document resolves the project-layer design, `GOV-P-004`
> fixes the deployment layer and the standalone-viability rule. The addendum-lineage
> paragraph below is where `GOV-P-004`'s Supersession-via-Delta-Ingestion clause
> lands, bounded by `add-addendum-facility.md` §2 item 6 — an arriving addendum marks
> affected downstream work for review; it never applies itself.

## Owner / Proponent publication

Owner Private Project → authorized publication → immutable **Published Procurement Instrument** → independent, physically separate Proponent Project imports it as its own fresh `Source`. Never one project under differentiated access — tested directly and confirmed: a single shared workspace with visibility flags means every future feature is one bug away from leaking confidential pre-publication owner deliberation to a bidder in an active competition; genuine physical separation fails safe instead, because there is no code path that could leak what was never in the same file. This is the same strict-isolation invariant (constitutional #8) already governing ordinary project-to-project boundaries, now understood to carry a second, independent, higher-stakes justification (procurement integrity) alongside its original one (stale-truth prevention).

The Published Procurement Instrument is **not a fourth top-level domain** — it's a third sub-category within Domain 2 (Domain 2c — Published Cross-Project Artifact), sharing 2a/2b's adoption mechanics (a receiving project creates its own fresh `Source`, never inherits operative truth) while being distinct in kind from both: its authority derives from being the actual governed output of one specific project's own publication act, not an external body or internal QA process.

Addendum lineage (RFP → Addendum 01 → Addendum 02 → clarifications → revised procurement state) is ordinary `Source` revision/`Supersession` — no new mechanism, each addendum preserving issuer, authority, version, time, exact content, and supersession-or-supplement relation.

## Owner-side project inception and pre-publication forensic QA

BEEHIVE may begin at the project seed (need → feasibility → site analysis → program → budget → viability → security policy → procurement strategy → RFQ/RFP development → pre-publication QA → release), not only at RFP publication. **Confirmed, not novel:** the "private synthetic proponent" pre-publication QA capability requires no new mechanism — it is the exact same contradiction-checking, cross-requirement-consistency, and metamorphosis machinery already implemented, applied to a project whose `Source` documents happen to be drafts rather than issued documents. `Source.document_status` already carries exactly this distinction as a free-text field. Nothing in the object model was ever hardwired to a proponent-only assumption.

## Neutral / Adjudication Workspace

Default, and the resolved answer, not an open item: a separately governed workspace, itself its own isolated project, populated only by explicit imports of already-published/shared material from each side via the Domain 2c mechanism above — never a privileged cross-project read into either party's private workspace. Neutral authority never implies private-party visibility.

**Exceptional case, tested and resolved, not carried forward as open:** legally-compelled disclosure (formal arbitration/discovery) does not require a new privileged-read mechanism. It is the *same* publication/export act already designed, triggered by an external legal authority (court/arbitral order) rather than ordinary business judgment — the owning party's own project always performs the export; nothing ever reads directly into another party's private workspace, under any authority. No exceptional cross-project read survives, in any form.

## Experience Corpus

BEEHIVE may learn how to investigate without learning what to believe — a tested, three-constraint distinction, not an unconditional license: (1) content restricted to structured evidence-domain/check-type references, never outcome-shaped prose; (2) outcome-valence stripped from the reusable content itself; (3) every surfacing logged with full provenance. Guides *where to look*, never *what to believe*; never establishes current-project truth.

No person ranking, ever — heuristic usage statistics (independent-use count, reproduction count, jurisdiction/scope, failure count) may be retained, but the "originating reviewer" field must not be jointly queryable alongside those statistics in the same surface, to prevent proxy-reputation reconstruction. Identity remains legitimate for authorship/provenance; no behavioral telemetry, no click-order/dwell-time surveillance; investigative associations recorded as unordered sets, not sequences; precise timestamps remain legitimate for provenance (they answer a different question than behavioral inference).

**Cross-party confidentiality pipeline, the shape resolved, detailed mechanics still open (see `deferred-reserved/reservations.md`):** Private/local investigative activity → generalization/abstraction (domain-only, valence-stripped) → confidentiality/re-identification check → **adversarial-party eligibility check** (content contributed while a project sits on one side of an active or recently-closed procurement relationship must not be retrievable by a project on the opposing side of that same procurement) → authorized promotion → Experience Corpus. The adversarial-party check is the one genuinely new finding this architecture surfaced — Experience Corpus's original input-boundary rule (never from private material) does not, by itself, prevent this specific leak.
