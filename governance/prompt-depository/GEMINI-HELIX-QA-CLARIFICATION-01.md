# GEMINI-HELIX-QA-CLARIFICATION-01 — Progressive Helix QA Measurement Framework for ARCHIOSK/GO

| Field | Value |
|---|---|
| Prompt ID | GEMINI-HELIX-QA-CLARIFICATION-01 |
| Title | Progressive Helix QA Measurement Framework for ARCHIOSK/GO |
| Agent | Gemini |
| Status | RUN |
| Purpose | Preserve the complete Gemini Helix QA clarification as immutable source material, distinct from later Product Owner interpretation and GO adoption. |
| Product Owner acceptance | Accepted as source material only; examples and terminology are not automatically governing application doctrine. |
| Lineage | Source for [GO-HELIX-QA-01](GO-HELIX-QA-01.md), related to [GO-GEMINI-DOC-REVIEW-01](GO-GEMINI-DOC-REVIEW-01.md) and [GO-HELIX-01](GO-HELIX-01.md). |
| Superseded by | None |
| Absorbed into | GO-HELIX-QA-01 (concepts only; this source remains preserved) |

## Exact prompt text

```text
Progressive Helix QA Measurement Framework for ARCHIOSK/GO
1. The Operational Core: What Is Progressive Tightening?

In ARCHIOSK/GO, Progressive Tightening is not a static tolerance table. It is the gradual elimination of uncoordinated design freedom.  [0% / RFP Baseline] ────────► [30% SD] ────────► [60% DD] ────────► [90% CD] ────────► [100% / IFC] Spatial reservations Macro zones & Boundaries, Exact dimensions, Fabricated & & design criteria core datums corridors & mains details & tags sealed geometry (Loose Helix) (Coupling) (Interlocking) (Torqued Mesh) (Locked State)   At early stages (RFP to 30%), a project strand (Architecture, Structure, MEP, Civil) is loosely coupled. It is represented by envelopes, capacities, allowances, and general routing corridors. As the design matures, this freedom narrows:

Spatial ambiguity collapses into explicit dimensions tied to established datums.
Abstract performance criteria turn into specific scheduled equipment models, electrical loads, and physical weights.
Cross-disciplinary obligations (e.g., “Structure must provide a slab opening for Mechanical”) transform from general intent notes into dimensioned, located penetrations coordinated across all contract documents.

Definition of Tightness:

A project interface has tightened when the dependent disciplines have exchanged explicit, dimensioned, and mutually consistent evidence that eliminates spatial and operational ambiguity for that stage.
2. Dimensional QA Signals & Reconciliation Mechanics

Dimensions are the primary geometric signals of helix alignment. GO must treat dimensions not merely as text strings, but as relational constraints with context-dependent validation rules.

                      ┌────────────────────────────────────────┐
                      │        DIMENSIONAL EVIDENCE            │
                      └───────────────────┬────────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
     ┌────────────────────────┐                      ┌────────────────────────┐
     │   EXPLICIT DIMENSIONS   │                      │  PARAMETRIC / DERIVED  │
     │ String values on sheet │                      │ Scaled vector bounding │
     │  (e.g., "1800 x 1200") │                      │   (e.g., Grids A-B)    │
     └────────────┬───────────┘                      └────────────┬───────────┘
                  └───────────────────────┬───────────────────────┘
                                          ▼
                      ┌────────────────────────────────────────┐
                      │      TOLERANCE & INTENT CLASSIFIER     │
                      │  • Exact Fit (Grids, Openings, Shafts) │
                      │  • Envelope Bound (Clearance Zones)    │
                      │  • Minimum Ceiling / Egress Thresholds │
                      └────────────────────────────────────────┘
Dimensional Categories & Matching Expectations
Exact-Fit Dimensions (Zero Deviation Permitted at Maturity):
Examples: Column grid spacings, floor-to-floor datum heights, structural slab opening vs. fire-rated shaft inside dimensions, door rough-opening sizes relative to frame schedule.
Behavior: Must match numerically and positional-wise across architectural, structural, and civil sets once the project reaches 60%–90%.
Threshold / Limiting Dimensions (One-Sided Inequality Constraints):
Examples: Clear headroom ($\ge 2100\text{ mm}$), corridor egress width ($\ge 1200\text{ mm}$), ADA turnaround circles ($\ge 1500\text{ mm}$), working clearance in front of switchgear ($\ge 1000\text{ mm}$).
Behavior: Evaluated as $D_{\text{actual}} \ge D_{\text{required}}$. If a structural drop beam reduces ceiling height from $2400\text{ mm}$ to $2050\text{ mm}$ in an accessible route, this triggers an immediate threshold violation, even if no explicit drawing text flags the conflict.
Envelopes and Reservations (Bounded Zones):
Examples: MEP distribution ceiling zones, utility trench depths, elevator pit depths, generator footprint allowances.

Behavior: At 30%, these exist as bounded zones (e.g., "provide $600\text{ mm}$ clear ceiling cavity"). At 60%–90%, the physical equipment plus required installation and maintenance clearances must sum to less than or equal to the reserved envelope:

$$\sum (\text{Duct Outer Dimension} + \text{Insulation} + \text{Hanger Allowance} + \text{Lighting Recess}) \le \text{Ceiling Zone Envelope}$$

Distinguishing Dimensional States
[Observed Difference in Evidence]
               │
               ├─► Explicit value contradicts explicit value? ──────► GENUINE_DISCREPANCY
               │
               ├─► Envelope provided; contents fit inside? ────────► INTENTIONAL_ENVELOPE (Valid)
               │
               ├─► One discipline dimensioned; other blank? ────────► MISSING_EVIDENCE
               │
               ├─► Stage rules permit unlocated elements? ──────────► LEGITIMATE_STAGE_UNRESOLVED
               │
               └─► Metric vs Imperial or string formatting? ────────► COMPATIBLE_REPRESENTATION
3. Observable QA Signals for Helix Tightening

Beyond dimensions, GO must evaluate eight core coordination signals:

┌──────────────────────────────────────────────────────────────────────────────────┐
│                         EIGHT OBSERVABLE QA SIGNALS                              │
├──────────────────────────┬──────────────────────────┬────────────────────────────┤
│ 1. Positional Agreement  │ 2. Interface Definition  │ 3. Cross-Disciplinary      │
│    Grids, datums,        │    Rough openings,       │    Handshakes              │
│    coordinates, levels   │    sleeves, penetrations │    Loads, feeds, hardware  │
├──────────────────────────┼──────────────────────────┼────────────────────────────┤
│ 4. Semantic Agreement    │ 5. Consequential         │ 6. Residual Uncertainty    │
│    Tags, schedules,      │    Completeness          │    Clouded areas, "HOLD",  │
│    capacities, ratings   │    Required sheets & data│    "TBD", "NIC" notes      │
├──────────────────────────┼──────────────────────────┼────────────────────────────┤
│ 7. Revision Propagation │ 8. Authority Alignment   │                            │
│    Cross-discipline      │    Governing document    │                            │
│    delta tracking        │    hierarchy compliance  │                            │
└──────────────────────────┴──────────────────────────┴────────────────────────────┘
Positional Agreement (Spatial Co-location):
Grid line bubbles, offsets, structural levels, and column numbers match across all discipline sheets without unaccounted rotation, scaling, or datum shifts.
Interface Definition:
Transition points between disciplines are explicit. (e.g., Architectural curtain wall embeds are called out on Structural drawings; civil storm invert elevation matches plumbing tie-in elevation at the building boundary).
Cross-Disciplinary Handshake (Obligation $\leftrightarrow$ Fulfillment):
Mechanical $\leftrightarrow$ Electrical: Every motor, fan, chiller, and pump shown on Mechanical plans or schedules has a corresponding circuit, breaker, and disconnect switch on the Electrical panel schedules and single-line diagrams.
Architectural $\leftrightarrow$ Electrical/Security: Every access-controlled door on the Door Schedule has an electrical conduit, power supply, and card reader feed.
Structural $\leftrightarrow$ Architectural/MEP: Every slab opening $> 200\text{ mm}$ on Mechanical or Plumbing plans is documented on the Structural framing plans.
Semantic Agreement (Attribute Uniformity):
Equipment identifiers (AHU-01, P-101), room numbers, fire ratings (1-hr, 2-hr), door marks, and flow rates agree between 2D plan tags, sheet schedules, riser diagrams, and specifications.
Completeness of Consequential Interfaces:
Expected schedules (e.g., Door Schedule, Room Finish Schedule, Luminaire Schedule) exist and are fully populated rather than populated with placeholder dashes.
Residual Uncertainty (Explicit Unresolved Markers):
Tracking the density of risk-bearing markers: "NIC" (Not In Contract), "TBD" (To Be Determined), "HOLD", revision clouds, and open design notes. Progressive tightening means the count of these markers asymptotically approaches zero by IFC.
Revision Propagation:
When an Architectural sheet advances to Revision 3 due to a shifted partition wall, dependent Structural and MEP sheets show corresponding revision flags or addenda acknowledgments rather than referencing superseded floor plans.
Authority Alignment:
Resolving discrepancies by checking against the contractually established Hierarchy of Documents (e.g., Addenda override Specifications; Specifications override Large-Scale Details; Large-Scale Details override Plans).
4. Establishing Project-Specific Expectation Baselines

GO must avoid hardcoded assumptions (such as "60% always means LOD 300"). Instead, the system determines the Expected Tightness Baseline by ingesting project governance metadata during setup.

                          ┌───────────────────────────────┐
                          │   PROJECT GOVERNANCE INPUTS   │
                          └───────────────┬───────────────┘
                                          │
        ┌─────────────────────────┬───────┴─────────────────────────┐
        ▼                         ▼                                 ▼
┌───────────────┐         ┌───────────────┐                 ┌───────────────┐
│ Contract &    │         │ BIM / QA      │                 │ Document      │
│ Delivery Type │         │ Execution Plan│                 │ Stated Purpose│
│ (DBB, DB,     │         │ (Level of Dev,│                 │ (SD, DD, CD,  │
│  CMAR, IPD)   │         │  Matrix, BEP) │                 │  IFT, IFC)    │
└───────┬───────┘         └───────┬───────┘                 └───────┬───────┘
        └─────────────────────────┼─────────────────────────────────┘
                                  ▼
                ┌───────────────────────────────────┐
                │   COMPUTED PROJECT EXPECTATION    │
                │        BASELINE REPOSITORY        │
                └───────────────────────────────────┘
Context Factors Evaluated by GO
Delivery Method:
Design-Bid-Build (DBB): 90% CD and 100% IFT must be nearly 100% resolved because the package is used for binding fixed-price contractor bidding.
Design-Build (DB) / Fast-Track: Foundation/Structural packages are expected to reach 100% IFC early, while Interior Architectural and MEP finishes legitimately remain at 30%–60% loose coupling.
Contractual Purpose of Current Issue:
PURPOSE_PRICING $\rightarrow$ Focus on schedule completeness, equipment counts, and gross boundaries.
PURPOSE_REGULATORY_PERMIT $\rightarrow$ Focus on life safety, egress widths, fire ratings, plumbing fixture counts, and zoning compliance.
PURPOSE_CONSTRUCTION_IFC $\rightarrow$ Zero tolerance for unresolved spatial clashes or missing connection details.
Governing Project Standards:
If a project provides a BIM Execution Plan (BEP) or Design Responsibility Matrix (DRM), GO imports those matrix rules directly as expectation rulesets.
5. QA Expectation-State Vocabulary

For every relationship tested, GO registers an Expectation State to determine whether absence of detail constitutes a failure:

┌─────────────────────────┬────────────────────────────────────────────────────────────────────────┐
│ EXPECTATION STATE       │ MEANING                                                                │
├─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ MANDATORY_STAGE_FIT     │ Must be completely defined and reconciled at this milestone.           │
│ PARTIALLY_CONVERGED     │ Must show directional alignment or envelope reservation at this stage. │
│ PLANNED_DEFERRED        │ Not expected to be resolved at this stage; absence is valid.           │
│ CONDITIONAL_INTERFACE   │ Required only if a specific design option or trigger is present.       │
│ PROJECT_SPECIFIC_RULE   │ Defined by custom Owner Project Requirements (OPR) or local code.      │
│ NOT_APPLICABLE          │ Irrelevant to the current project scope or delivery type.              │
└─────────────────────────┴────────────────────────────────────────────────────────────────────────┘
6. QA Assessment Vocabulary

When evidence is evaluated against an expectation, GO classifies the result using this Assessment Vocabulary:

┌─────────────────────────┬────────────────────────────────────────────────────────────────────────┐
│ ASSESSMENT TYPE         │ MEANING                                                                │
├─────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ CONVERGED               │ Strands reconcile within acceptable criteria for this stage.           │
│ DIMENSION_CONFLICT      │ Explicit numeric or geometric dimensions directly contradict.          │
│ POSITIONAL_CONFLICT     │ Elements occupy the same physical space or reference mismatched datums.│
│ SEMANTIC_MISMATCH       │ Discrepancy in tags, ratings, capacities, schedules, or descriptions.  │
│ HANDSHAKE_DEFICIT       │ One discipline creates an obligation that the other fails to document. │
│ PROPAGATION_LAG         │ One sheet was revised but dependent sheets reference superseded data.  │
│ STAGE_MATURITY_MISMATCH │ One strand has progressed to high detail while dependent strand lags.  │
│ RESIDUAL_AMBIGUITY      │ Excessive "HOLD", "TBD", or clouded areas on critical path interfaces. │
│ EVIDENCE_UNAVAILABLE    │ Necessary sheet, schedule, or detail is missing from uploaded set.     │
│ LEGITIMATE_DEFERRED     │ Interface is uncoordinated, but contractually appropriate for stage.   │
└─────────────────────────┴────────────────────────────────────────────────────────────────────────┘
7. The Unified Spin Record Schema

Instead of flattening results into a single score, ARCHIOSK/GO stores discrete, auditable JSON records for every tested relationship:

JSON

{
  "record_id": "SPIN-REC-2026-0819-0042",
  "project_id": "PRJ-COMMERCIAL-TOWER-B",
  "timestamp": "2026-08-19T04:21:00Z",
  "spin_type": "HORIZONTAL",
  "claimed_milestone": "60_DD",
  "interface": {
    "subsystem": "VERTICAL_CIRCULATION_AND_SERVICES",
    "name": "Main Mechanical/Plumbing Shaft vs Core Slab Opening",
    "disciplines_involved": ["ARCHITECTURAL", "STRUCTURAL", "MECHANICAL", "PLUMBING"]
  },
  "expectation": {
    "state": "MANDATORY_STAGE_FIT",
    "rationale": "At 60% DD, primary riser shafts must be located with bounded structural slab openings."
  },
  "observed_evidence": [
    {
      "source_doc": "A-201_L03_PLAN.pdf",
      "sheet_revision": "Rev 2 (2026-07-15)",
      "element_id": "SHAFT-MEP-01",
      "reported_value": "Shaft Inside Dimension: 2400mm x 1500mm at Grid C-3"
    },
    {
      "source_doc": "S-103_L03_FRAMING.pdf",
      "sheet_revision": "Rev 1 (2026-06-10)",
      "element_id": "SLAB-OPENING-S03",
      "reported_value": "Slab Opening: 2000mm x 1500mm at Grid C-3 (Beam W16x31 trims at 2000mm)"
    },
    {
      "source_doc": "M-301_RISER_DIAGRAM.pdf",
      "sheet_revision": "Rev 2 (2026-07-20)",
      "element_id": "RISER-BUNDLE-01",
      "reported_value": "Calculated Riser Footprint: 2150mm x 1200mm required (Ducts + Chilled Water)"
    }
  ],
  "assessment": {
    "result": "DIMENSION_CONFLICT",
    "governing_principle": "Structural framing opening (2000mm) is smaller than required Mechanical footprint (2150mm) and Architectural shaft (2400mm)."
  },
  "consequence_evaluation": {
    "severity": "CRITICAL",
    "impact_domain": ["CONSTRUCTIBILITY", "REWORK_COST"],
    "rationale": "Slab edge beam framing conflicts directly with primary supply riser installation."
  },
  "propagation_analysis": {
    "lag_detected": true,
    "probable_cause": "Structural sheet S-103 predates Architectural Rev 2 shaft expansion by 35 days."
  },
  "go_action_protocol": {
    "evidence_summary": "Architectural shaft was expanded to 2400mm in Rev 2, but Structural opening remains at 2000mm from Rev 1.",
    "concern": "Mechanical riser bundle (2150mm) will not fit through structural framing opening.",
    "targeted_question": "Has Structural Engineering incorporated Architectural Addendum 2 shaft widening into framing sheet S-103?"
  }
}
8. Horizontal vs. Longitudinal Spin Mechanics
                  ┌────────────────────────────────────────────────────────┐
                  │                 TWO AXES OF VERIFICATION              │
                  └───────────────────────────┬────────────────────────────┘
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
┌───────────────────────────────────────┐   ┌───────────────────────────────────────┐
│           HORIZONTAL SPIN             │   │          LONGITUDINAL SPIN            │
│       (Current Cross-Section)         │   │       (Temporal & Compliance)         │
├───────────────────────────────────────┤   ├───────────────────────────────────────┤
│ • Cross-disciplinary fit at stage     │   │ • Scope drift against 0% RFP / OPR    │
│ • Geometric & spatial clearance       │   │ • Program area & capacity changes     │
│ • Document-to-schedule handshake      │   │ • Regulatory / Code baseline drift    │
│ • Current revision synchronization    │   │ • Historical decision reconciliation  │
└───────────────────────────────────────┘   └───────────────────────────────────────┘
1. Horizontal Spin (Cross-Disciplinary Coordination)
Question: "Do the distinct disciplines fit together without contradiction at this specific moment in time?"
Metrics:
Spatial clearances and penetration alignments.
Plan tags matching Sheet Schedule entries.
Electrical panel feeds matching Mechanical equipment schedules.
Architectural door hardware matching Security access plans.
2. Longitudinal Spin (Temporal Progression & Drift)
Question: "Has the design drifted from binding project agreements, client requirements, or approved prior iterations?"
Metrics:
Program Variance: Comparison of current net square footage against 0% RFP Room Data Sheets.
Capacity Drift: Current electrical service sizing vs. Owner Project Requirements (OPR).
Performance Downgrade: Acoustic STC ratings or envelope U-values drifting below contractual targets.
Resolution of Prior Actions: Ensuring issues flagged in 30% SD Spin are marked resolved in 60% DD Spin.
9. Worked Progression Examples Across Lifecycle Stages
Example A: Primary Vertical Utility Shaft
[0% RFP / Space Program] ──► [30% SD] ─────────────► [60% DD] ─────────────► [90% CD / IFT] ────────► [100% IFC]
Square footage allowance    Shaft reserved in core   Shaft dimensioned,     All penetrations        Spool drawings,
in program narrative        without exact openings   framing beams located  sleeved, fire-stopped   hangers & seals


0% RFP: Narrative program states: "Provide central utility shaft with sufficient area for future 20% vertical expansion."
30% SD: Arch shows generic rectangular shaft in core. Structural shows floor opening with dashed line. Mechanical shows single line riser diagram.
GO Assessment: CONVERGED (Expectation: PARTIALLY_CONVERGED).
60% DD: Arch sheet A-102 dimensions shaft: $2400\times 1500\text{ mm}$. Structural S-102 shows framed opening $2400\times 1500\text{ mm}$. Mechanical M-201 details three ducts and two pipe risers occupying $1800\times 1100\text{ mm}$.
GO Assessment: CONVERGED (Expectation: MANDATORY_STAGE_FIT).
90% CD / IFT: Exact sleeve diameters, fire-damper details, floor curb dimensions, and acoustic wrap allowances are detailed and cross-referenced.
GO Assessment: CONVERGED.
100% IFC: Fully coordinated penetration drawings with approved manufacturer firestop assemblies and clear structural edge clearances ($\ge 50\text{ mm}$ from rebar/post-tensioning tendons).
GO Assessment: CONVERGED.
Example B: Access-Controlled Motorized Door Interface
[0% RFP / OPR] ────────────► [30% SD] ─────────────► [60% DD] ─────────────► [90% CD / IFT] ────────► [100% IFC]
"Card-access security at    Door opening shown on   Door schedule tags:     Junction boxes, conduit  Hardware supplier
all perimeter portals"      floor plan (A-101)      Card reader, power op   runs, panel circuits     shop dwg & wiring
                                                    (A-601). Missing in E.  detailed (E-101, E-401)  interlock verified
0% RFP: OPR Section 08: "All perimeter entry doors shall have automated swing operators and electronic card access."
30% SD: Door 101 shown on Architectural floor plan as a standard opening. No hardware details.
GO Assessment: CONVERGED (Hardware expected later).
60% DD: Architectural Door Schedule designates Door 101 as "Card Access / Low-Energy Auto Operator". Electrical sheet E-101 has no power feed near Door 101.
GO Assessment: HANDSHAKE_DEFICIT (Expectation: MANDATORY_STAGE_FIT).
GO Flag: "Architectural schedule requires power for Door 101 operator, but no electrical branch feed is evidenced on sheet E-101."
90% CD / IFT: Door Schedule specifies hardware set; Electrical sheet E-101 shows 120V power connection; Security sheet SEC-101 shows conduit to card reader and request-to-exit motion sensor.
GO Assessment: CONVERGED.
100% IFC: Verified coordination between architectural frame prep, security card reader backbox, and manufacturer wiring diagram.
GO Assessment: CONVERGED.
Example C: Central Mechanical Equipment Room
[0% RFP / OPR] ────────────► [30% SD] ─────────────► [60% DD] ─────────────► [90% CD / IFT] ────────► [100% IFC]
Allocated Gross Area        Spatial room boundary   Equipment sizes,        Maintenance pull zones,  Vibration isolation,
(e.g., 250 m² basement)     established on Arch     pads, weights, and      feeders, floor drains,   pipe spooling, and
                            basement footprint      electrical loads        control panels shown     rigging path locked
0% RFP: Facility program reserves $250\text{ m}^2$ in basement for Central Plant.
30% SD: Architectural layout defines Room B-04 as $245\text{ m}^2$. Mechanical shows block footprints for 2 Chillers and 2 Pumps.
GO Assessment: CONVERGED (Expectation: PARTIALLY_CONVERGED).
60% DD: Equipment schedule on M-601 specifies Chiller-1: $480\text{V}$, 3-phase, $180\text{ FLA}$, operating weight $8,500\text{ kg}$. Structural S-101 shows housekeeping pad sized for $8,500\text{ kg}$. Electrical Single-Line E-501 shows $200\text{A}$ dedicated breaker.
GO Assessment: CONVERGED.
90% CD / IFT: Tube-pull maintenance clearance envelope shown dashed on M-101; no piping, conduit, or structural columns encroach on the pull zone. Equipment room emergency eye-wash drain plumbed to sanitary.
GO Assessment: CONVERGED.
100% IFC: Rigging and equipment replacement path from loading dock to basement room verified with verified roll-in dimensions and floor live-load capacity.
GO Assessment: CONVERGED.
10. Consequence-Weighted Evaluation

GO must distinguish harmless drafting tolerances from severe coordination failures without overstepping into unauthorized engineering decisions.

                  ┌────────────────────────────────────────┐
                  │          DISCREPANCY DETECTED          │
                  └───────────────────┬────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
┌───────────────┐             ┌───────────────┐             ┌───────────────┐
│ Low / Non-    │             │ Moderate /    │             │ Critical /    │
│ Critical      │             │ Trade Inter-  │             │ Code / Life   │
│ (Drafting /   │             │ face          │             │ Safety / Core │
│  Notation)    │             │ (Piping /     │             │ (Egress, Slab │
│               │             │  Framing)     │             │  Openings)    │
└───────┬───────┘             └───────┬───────┘             └───────┬───────┘
        │                             │                             │
        ▼                             ▼                             ▼
 [Logged for Info]           [Action Item for Coor.]       [Immediate Submittal Blocker]
Consequence Classification Matrix
Life Safety & Regulatory Blocker (Highest Severity):
Triggers: Egress corridor width reductions below code minimums; fire barrier ratings violated by unsealed penetrations; missing emergency power feeds to life-safety equipment.
GO Behavior: Registers as CRITICAL_BLOCKER.
Hard Structural / Spatial Impasse:
Triggers: Large gravity duct or pipe clashing with main structural steel; vertical shafts misaligned with foundation openings.
GO Behavior: Registers as HIGH_SEVERITY_COORDINATION_DEFICIT.
Trade Handshake Gap:
Triggers: Motorized equipment missing electrical connections; plumbing fixture missing water supply line.
GO Behavior: Registers as MEDIUM_HANDSHAKE_GAP.
Drafting / Non-Critical Notation Variance:
Triggers: Non-critical interior partition shifted $15\text{ mm}$ on architectural plan without affecting room classification or MEP clearances.
GO Behavior: Registers as LOW_STAGE_VARIANCE.
11. Governed System Boundaries: "Evidence $\rightarrow$ Concern $\rightarrow$ Question"

ARCHIOSK/GO is a Quality Assurance & Auditing Engine, not an automated engineering design tool. It must never fabricate or prescribe unverified engineering fixes.

┌────────────────────────────────────────────────────────────────────────┐
│               GOVERNED INTERACTION PROTOCOL                            │
├───────────────────┬────────────────────────────────────────────────────┤
│ 1. Evidence       │ Cite exact sheets, revisions, tags, and dimensions.│
├───────────────────┼────────────────────────────────────────────────────┤
│ 2. Concern        │ Explain the geometric, semantic, or operational    │
│                   │ conflict identified by the rules engine.           │
├───────────────────┼────────────────────────────────────────────────────┤
│ 3. Question       │ Formulate a precise, professional query for the    │
│                   │ responsible Engineer of Record (EOR) / Architect.  │
└───────────────────┴────────────────────────────────────────────────────┘


Protocol in Practice
❌ Forbidden Prescriptive Output:
"Duct size is too large for ceiling space. Lower the ceiling to $2400\text{ mm}$ or re-engineer the duct to $600\times 200\text{ mm}$."
✅ Compliant Governed Output:
Evidence: "Sheet A-103 indicates reflected ceiling height of $2700\text{ mm}$ AFF. Sheet M-201 routes $400\text{ mm}$ supply duct with $50\text{ mm}$ insulation below bottom of steel at $2900\text{ mm}$ AFF."
Concern: "Combined depth of ductwork and structure leaves $150\text{ mm}$ cavity, which does not accommodate the $200\text{ mm}$ recessed luminaires specified on Sheet E-201."
Targeted Question: "Please confirm whether the ceiling height on A-103 can be adjusted, or if mechanical routing on M-201 will be modified to maintain luminaire clearance."
12. Measurement Boundaries: Vector PDF vs. Richer Data Formats

To ensure system reliability, GO must maintain a clear distinction between what can be deterministically audited from 2D PDFs and what requires 3D BIM/CAD sources.

┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             MEASUREMENT FEASIBILITY MATRIX                               │
├──────────────────────────────┬──────────────────────────────┬────────────────────────────┤
│ CATEGORY 1: RELIABLY         │ CATEGORY 2: MEASURABLE VIA   │ CATEGORY 3: REQUIRES       │
│ MEASURED FROM 2D PDF         │ VISUAL / VECTOR ANALYSIS     │ BIM / CAD / IFC FORMAT     │
├──────────────────────────────┼──────────────────────────────┼────────────────────────────┤
│ • Explicit dimension strings │ • Scaled 2D spatial overlays │ • Compound 3D spatial skew │
│ • Grid line tags & labels    │ • Grid intersection anchors  │ • Dense rebar clearance    │
│ • Schedule key-value pairs   │ • Bounded corridor routing   │ • Complex pipe slopes in   │
│ • Equipment IDs & tags       │ • Room area polygon geometry │   multi-trade risers       │
│ • Specification text values  │ • 2D clearance zones         │ • True solid-geometry      │
│ • Sheet revision metadata    │ • Door swing conflicts       │   volume intersections     │
│ • General notes & clouds     │ • Wall alignment overlays    │ • Fabrication spooling     │
└──────────────────────────────┴──────────────────────────────┴────────────────────────────┘



Guiding Principle for GO:

When a requested audit requires 3D solid geometry (e.g., compound pipe sloping through complex structural trusses), GO registers EVIDENCE_TYPE_INSUFFICIENT_FOR_AUDIT and prompts the user to provide an IFC/BIM dataset, rather than generating a speculative 2D assessment.

13. Retirement of Prior Exploratory Concepts

To establish this rigorous QA framework, we formally retire several exploratory ideas from earlier discussions:

Universal Millimeter Tolerance Tables:
Why Retired: Tolerances are project- and system-specific. A $25\text{ mm}$ variance on a civil site boundary is acceptable; the same $25\text{ mm}$ on an elevator guide rail or cleanroom envelope is a failure.
Monolithic "Helix Health Score" (0–100%):
Why Retired: A single weighted score hides critical life-safety flaws behind high overall completeness. GO replaces this with discrete, queryable discrepancy records and risk profiles.
Hardcoded Trade Priority Hierarchies (e.g., Structure $>$ Mechanical $>$ Electrical):
Why Retired: Hierarchy is governed by contract, physics, and gravity-dependence (e.g., a $2\%$ sloped sanitary line may dictate structural beam web penetrations). Priority must be contextual, not hardcoded.
Universal Percentage-to-LOD Mapping:
Why Retired: A 60% submittal in Design-Build means something fundamentally different from 60% in Design-Bid-Build. GO binds maturity expectations to project-declared governance baselines.
```

## Execution references

- Run: Gemini clarification supplied by the Product Owner in `CODEX-HELIX-QA-ABSORPTION-01`
- Result: Source preserved; governed absorption is recorded separately in `GO-HELIX-QA-01`
- Commit: Pending
