# Historic Corpus Inventory and Mapping

**Status:** Inventory and mapping only. **No file in either live repository was touched, moved, renamed, copied, or edited to produce this document.** This maps where each existing document *would* eventually belong under the ratified structure, once migration is separately authorized — it does not perform that migration and does not contain copies of the mapped content.

Re-verified this session via fresh directory enumeration of `C:\Archiosk\App\archiosk-explorer` (not recalled from earlier-round memory) and a fresh line-count/anchor check of `C:\Archiosk\Research\archiosk\services\case_workspace.py`.

---

## Backend repo (`C:\Archiosk\Research\archiosk`)

No `Governance/` or `governance/` folder exists at all. All governance content lives in code (`services/case_workspace.py`, `services/governance.py`) and commit messages — this is the entire source of `current/kernel-object-model.md` above, with no pre-existing documentation corpus to map.

## Explorer repo (`C:\Archiosk\App\archiosk-explorer`) — full inventory, mapped

| Path/family | Target bucket | Notes |
|---|---|---|
| `Architecture/00 Vision.md`, `01 Design Charter.md` | `history/` | Pure historic principles; several design-charter items map directly to a constitutional invariant's origin (e.g. "machine observations must always be reviewer validated" → invariant 2), but the document itself is superseded by `constitutional-invariants.md`. |
| `Architecture/02 Investigation Workflow.md` (606 lines) | `history/`, **flagged mixed** | Only structurally surveyed across this engagement, never read in full. Likely contains both still-relevant lifecycle concepts and superseded detail. Needs a dedicated read-and-decompose pass before final filing — not performed this round. |
| `Architecture/03 Information Model.md` (423 lines) | `history/`, **flagged mixed** | Same status as above — surveyed, not fully read, likely mixed. |
| `Architecture/04 UI Guidelines.md` (634 lines) | `history/` | Explorer-specific UI content, largely orthogonal to the kernel/constitutional material in this baseline. Not mixed with constitutional content, but relevant to a future UI-architecture document once the Explorer side of the product is re-verified. |
| `Architecture/05 AI Engine.md` | `history/`, **flagged high-value** | Contains the `AICapability` boundary design and the explicit, load-bearing cross-reference to the backend's `bhive_parser.py` — genuinely still-accurate design content. Recommended for early promotion to `specified-unbuilt/` once Explorer-side implementation status is re-verified (not done this round — this baseline's `current/` document covers only the backend). |
| `Architecture/07 Decision Log.md` | `history/`, **flagged as promotion source** | Real, substantive decisions (D-001…D-021) plus its own "ADR Promotion Queue" — the likely true content behind the eight empty `ADR-001`…`ADR-008` files below. |
| `Architecture/Laboratory_Governance/Constitution/STONE-WALL-CONSTITUTION.md` | `history/` | Confirmed a near-empty stub (header only, no rule content) in an earlier round. |
| `Architecture/Laboratory_Governance/Constitution/CONSTITUTIONAL-LAYERS.md` | `history/`, **flagged as direct source** | The Layer A/B/C organizing lens was explicitly mined into this baseline's reasoning (though not its structure) — worth an explicit citation from `governance-of-governance/` in a future pass. |
| `Architecture/Laboratory_Governance/protocols/{EVIDENCE-LIFECYCLE-PROTOCOL.md, SPIN-PASS-BUILD-PROTOCOL.md}` | `history/` | Substance already mined into `specified-unbuilt/` (evidence lifecycle, Spin/Pass/Build informing the Water Master pipeline); form not preserved. |
| `Architecture/Laboratory_Governance/schemas/*.md` (39 files, re-counted this session) | `history/`, en masse | ~23 carry an explicit "Regeneration Note" (chat-reconstructed, lower provenance confidence); ~16 are "Baseline Schema" with no such note (higher confidence). Already mined for principle, not preserved as structure, per the ratified architecture. |
| `Architecture/Laboratory_Governance/registry/*.json`, `releases/*`, `indexes/*` | `history/` | Administrative metadata about the schema package itself; `LABORATORY-GOVERNANCE-MASTER-REGISTRY.json` self-reports most entries as "Expected Existing," not verified — pure historic self-description, not authoritative fact. |
| `Architecture/Laboratory_Governance/traceability/CODE-GOVERNANCE-MAP.md` + `.../Archive/CODE-GOVERNANCE-MAP.md-back` | `history/`, **flagged duplicate pair** | A live document alongside its own backup copy under the same directory tree — an internal duplication within the historic corpus, newly named explicitly this round. Not resolved; flagged for whoever eventually curates `history/`. |
| `Architecture/Laboratory_Governance/schemas/UI-PROJECTION-INSPECTOR-AND-BLOCKED-ACTION-SCHEMA - Copy.md` | `history/`, **flagged duplicate filename** | A literal `- Copy` suffixed file sitting in the schemas folder — newly called out by name this round, not previously flagged this specifically. |
| `Governance/manifest.json`, `Governance/baselines/GOVERNANCE-BASELINE-v1.0.0.json`, `Governance/constitution/core-invariants.rules.json` | `history/`, **flagged severe, already resolved** | The 12-rule vs. 65-rule (`stoneWallRules.ts`) Stone Wall conflict found and resolved in an earlier round of this engagement — Stone Wall does not survive by name or structure in the ratified architecture; these files are preserved as the historic record of the first ratified governance baseline. |
| `Governance/{CONTEXT_BASELINE.md, FEATURE_MATRIX.md, SESSION.md, CHANGELOG.md, README.md}` | `history/` | Superseded going forward by `STATUS.md`. |
| `Docs/adr/ADR-001` … `ADR-008` (confirmed empty, 0 bytes, in an earlier round of this engagement) | `history/`, **flagged as promotion targets** | Likely-empty placeholders for content that actually lives in `Architecture/07 Decision Log.md`'s own promotion queue. |
| `Docs/adr/ADR-032 Governance of Forensic Truth.md` | `history/`, **flagged special — cited, not merely archived** | Stays physically in `history/`, untouched, but remains an active citation target from `current/` and `governance-of-governance/` per the "ADR identity is durable" principle — unlike the rest of the historic corpus, which is purely archival. |
| `Docs/adr/README.md` | `history/` | |
| `Docs/{CONTEXT_BASELINE.md, FEATURE_MATRIX.md, SESSION.md, CHANGELOG.md, ROADMAP.md, README.md, feature-register.json, baselines/, glossary/, templates/}` | `history/` | Product/feature-tracking for the Explorer product specifically; `ROADMAP.md` in particular may contain forward-looking content worth a future cross-check against `specified-unbuilt/` — flagged, not checked this round. |
| `Docs/archive/*` (prototype zips, old `.docx`/`.jpg`, `06 Development Journal.md`) | `history/`, already correctly archived | No remapping needed — already filed as historic by the team itself. |
| `Docs/Projects/*` (real client drawing sets, including a "5 Nipigon" project newly noted in this session's inventory) | **Not governance material — explicitly out of scope** | Confidential client content, never part of the governance corpus, not touched, not mapped further. |

---

## Confirmation this mapping loses no information

Every document enumerated above has an assigned bucket; none are silently omitted. The two flagged-mixed documents (`02 Investigation Workflow.md`, `03 Information Model.md`) are explicitly named as needing a future decompose-and-split pass rather than being silently force-fit into one bucket — that is a deliberate incompleteness, recorded here, not an oversight.
