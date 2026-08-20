# CODEX-PSD-TEACHER-ORACLE-02 — PSD Smoke / Horizontal Compartmentation Teacher Key

**Classification:** protected TEST/ORACLE governance.  This record is not project evidence and must never be ingested into either the Owner or Proponent PSD projects.

## 1. Frozen regulatory basis

| Item | Frozen basis |
|---|---|
| Test Code version | 2024 Ontario Building Code, O. Reg. 163/24, as amended by O. Reg. 447/24 |
| Effective/update date | November 4, 2024 update (the first 2024 Compendium amendment package) |
| Primary text | [Official November 4, 2024 Compendium update, Publication 301719](https://www.publications.gov.on.ca/store/20170501121/Free_Download_Files/301719.pdf) |
| Consolidated context | [O. Reg. 163/24 on Ontario e-Laws](https://www.ontario.ca/laws/regulation/r24163) |
| Retrieved package hash | `3c9b0279910986f0aa386421d2f9e0f929b9a49db3b55a9c3e8f9c74fa0fc67c` (301719.pdf) |
| Why this version | The PSD project-side matrix names O. Reg. 163/24 and O. Reg. 447/24. Publication 301719 is the official 2024 Compendium update containing 447/24. O. Reg. 5/25 (January 16, 2025) and later amendments are recorded as later versions, not silently mixed into this key. |

The January 16, 2025 Compendium (Publication 301880/301881) was inspected as a later-version cross-check only. It is not the frozen test basis. A later amendment can change a result and must trigger a new versioned oracle, not an edit to this one.

## 2. PSD body and authority boundary

The frozen project-side body is synthetic: Ontario public-safety/police facility; a proposed Group B, Division 1 detention/custody component; Group D office/investigation component; cells and controlled movement; one below-grade level and two principal storeys above grade; approximately 11,200 m² gross area, 4,400 m² building area and 13.5 m physical height; noncombustible construction and sprinklering proposed; two-stage fire alarm; zoned HVAC/BAS-DDC; emergency power and elevator/security interfaces. Exact compartment geometry, exit locations, travel distances, cell count, receiving capacity, and authoritative classifications are not supplied.

“Project-side proposition” is not an OBC conclusion. The Code Report and OBC Matrix are consultant interpretation/design evidence. Only the admitted official Code text can establish a regulatory answer.

## 3. Teacher Q/A

Each answer uses the required grammar: question, answer/status, project predicates, authority, qualifications, reasoning, expected evidence, ideal discovery, and trap.

### Q1 — What is the occupancy/classification root?

**Correct answer:** The PSD B1 proposition is a project-side classification that requires Code confirmation. The Code definition of **detention occupancy (Group B, Division 1)** is occupancy by persons restrained from, or incapable of, evacuating to a safe location without another person's assistance because of security measures not under their control. A police station with detention quarters has a narrow permission to be classified Group B, Division 2 only when it is not more than one storey and not more than 600 m². PSD's stated size/storey facts do not satisfy that relief on their face.

**Status:** CONDITIONAL.

**Project facts used:** cells/custody, staff-controlled movement, security-controlled doors; preliminary B1 and D labels; two principal above-grade levels, basement, approximately 4,400 m².

**OBC authority:** Div. A, 1.4.1.2.(1), definitions “Detention occupancy (Group B, Division 1)” and “Contained use area”; Div. B, 3.1.2.1.(1), Table 3.1.2.1; 3.1.2.4.(1), Police Stations.

**Qualifications:** The actual use, assistance condition, areas and height must be confirmed. The B1 label in a matrix is not itself authority.

**Expected evidence / ideal discovery:** final plans, operating description, occupant-movement facts, and a Code classification analysis; GO should not promote the consultant label without those predicates.

**Trap:** “Police station means B2” or “B1 is already proven.”

### Q2 — Is the custody area a contained-use area, an impeded-egress zone, or both?

**Correct answer:** The definitions are different. A contained-use area is a supervised area with one or more rooms where occupant movement is restricted to a single room by security measures outside the occupant's control. An impeded-egress zone is supervised, occupants have free movement, but security personnel must release boundary security doors; it excludes a contained-use area.

**Status:** CONDITIONAL.

**OBC authority:** Div. A, 1.4.1.2.(1), definitions “Contained use area” and “Impeded egress zone.”

**Qualifications:** PSD evidence supports a potential contained-use condition for cells and a potential impeded-egress condition for other controlled zones, but the exact room-by-room movement/security facts are missing.

**Ideal discovery:** GO should branch the analysis by zone rather than assign one label to the entire basement.

**Trap:** Treating “detention,” “contained use,” and “impeded egress” as synonyms.

### Q3 — Does 3.3.3.7 require horizontal subdivision into two smoke compartments?

**Correct answer:** **NO — NOT REQUIRED by 3.3.3.7 alone.** It requires a contained-use area to be separated from the remainder of the building by a fire separation rated at least 1 h, and, unless the narrow Sentence (4) alternative applies, requires the building to be sprinklered throughout. It does not require two internal contained-use fire compartments, a receiving-area capacity, or horizontal relocation.

**Status:** VERIFIED for the scope of Article 3.3.3.7; the exact PSD applicability remains CONDITIONAL on the definition predicates.

**OBC authority:** Div. B, 3.3.3.7.(1)–(5), especially (2)–(4).

**Sentence (4) meaning:** It is an alternative to the sprinkler requirement only where Articles 3.2.2.20–3.2.2.93 do not otherwise require sprinklers. It requires 2 h contamination limits at 1% by volume in both directions, remotely released doors under 3.3.1.13.(6), and no combustible padding. It is an alternative compliance condition, not a general smoke-control mandate. A fully sprinklered PSD does not need this exception to satisfy Sentence (3), although its predicates remain relevant if someone proposes to rely on the exception.

**Trap:** Reading the 1%/2 h language as a requirement for two smoke compartments in every detention area.

### Q4 — Does the Code require horizontal relocation from one detention side to another?

**Correct answer:** **NOT YET DETERMINABLE / not established for PSD.** The 2024 text inspected does not make “horizontal relocation” a universal detention rule. Div. B, 3.3.3.5.(2)–(8) does require two fire compartments, travel to an adjoining compartment, and capacity for the largest adjacent compartment—but that Article is expressly for patients' or residents' sleeping rooms in a hospital or long-term care home, not a generic Group B Division 1 detention area. Article 3.4.6.10 supplies capacity rules only if a horizontal exit is used; it does not itself require PSD to use one.

**Status:** UNKNOWN.

**Missing predicates:** final occupancy path, whether any care/LTC use exists, actual horizontal exit design, and authority-approved emergency strategy.

**Trap:** Importing the hospital/LTC “two compartments/2.5 m²” rule into detention without its scope predicate.

### Q5 — What separation follows from B1 and D coexistence?

**Correct answer:** If both are confirmed major occupancies, adjoining major occupancies are separated by fire separations rated from Table 3.1.3.1. The table gives 2 h between B-1 and D. Where one major occupancy is entirely above another, 3.2.2.7 applies each occupancy's Part 3 requirements to its portion and bases the interposed floor rating on the lower occupancy. This is fire-separation logic, not a conclusion that the boundary is a smoke compartment.

**Status:** CONDITIONAL.

**OBC authority:** Div. B, 3.1.3.1.(1), Table 3.1.3.1; 3.2.2.7.(1)–(2).

**Expected evidence:** final occupancy map, same-storey versus superimposed geometry, rated assemblies, openings and penetrations.

**Trap:** Flattening a same-level B1/D separation and a floor assembly above B1 into “a 2-hour ceiling.”

### Q6 — What construction/sprinkler branch is suggested for B1?

**Correct answer:** Article 3.2.2.36 is the Group B Division 1 any-height/any-area sprinklered path: noncombustible construction, sprinklering, 2 h floor assemblies, and supporting construction rated for the supported assembly. Article 3.2.2.37 is a permitted up-to-3-storey sprinklered path with noncombustible construction and 1 h floors, subject to the 3-storey and building-area limits. Article 3.2.2.19 is a narrow impeded-egress relief from 3.2.2.36/.37; it requires, among other things, one-storey height, no contained-use area, and occupant load not over 100, so it is not demonstrated for PSD.

**Status:** CONDITIONAL.

**OBC authority:** Div. B, 3.2.2.19.(1)(a)–(f); 3.2.2.36.(1)–(2); 3.2.2.37.(1)–(2).

**Trap:** Applying the impeded-egress relief to a multi-storey building that also contains a contained-use area.

### Q7 — Is a fire alarm system required?

**Correct answer:** **YES on the current project facts**, subject to final classification/measurements. A sprinklered building generally requires a fire alarm system under 3.2.4.1.(1). Independently, the non-sprinklered triggers in 3.2.4.1.(4) include a contained-use area, impeded-egress zone, more than three storeys including below first, total occupant load over 300, and occupant load over 150 above or below first. PSD proposes sprinklers and reports occupant loads over those thresholds; the final system type and scope still require design verification.

**Status:** VERIFIED for the sprinkler trigger; CONDITIONAL for all project-specific branches.

**OBC authority:** Div. B, 3.2.4.1.(1)–(4); 3.2.4.2.(2)–(4); 3.2.4.3.(1)(b), which requires a 2-stage system in a Group B occupancy except the stated B3 exception.

**Trap:** Treating a two-stage proposal as proof that every downstream sequence is Code-complete.

### Q8 — What smoke detection and staff annunciation are required?

**Correct answer:** Where a fire alarm system is installed, 3.2.4.11.(1)(b) requires smoke detectors in each room in a contained-use area and corridors serving those rooms. 3.2.4.11.(3) requires smoke detectors in sleeping rooms of a care, care-and-treatment or detention occupancy to provide audible and visible staff signals identifying the room/location. The latter is scoped to sleeping rooms; it does not automatically require a detector in every non-sleeping cell without confirming the applicable room/use path.

**Status:** CONDITIONAL.

**OBC authority:** Div. B, 3.2.4.11.(1)(b), (3).

**Expected evidence:** room schedule, sleeping/non-sleeping designation, detector layout, staff annunciator location and cause/effect.

**Trap:** Treating the project narrative's cell detector/control-room sequence as proof of every Code detector location or downstream action.

### Q9 — What does the Code require for HVAC smoke circulation?

**Correct answer:** If a fire alarm system is installed, an air-handling system must be designed to prevent smoke circulation on a duct-type smoke-detector signal when it serves more than one storey, more than one suite in a storey, more than one fire compartment required by 3.3.3.5.(2) or 3.3.4.11.(2), or lacks fire dampers under 3.1.8.8.(4). The sentence identifies the performance trigger; it does not say that every fan in the building must shut down on every alarm.

**Status:** VERIFIED for the trigger; CONDITIONAL for equipment-specific response.

**OBC authority:** Div. B, 3.2.4.12.(1)(a)–(d).

**Expected evidence:** air-system serving map, storey/suite/compartment scope, duct detector locations, shutdown/control sequence, recirculation analysis.

**Trap:** “Fire alarm equals shut every fan down.”

### Q10 — When are fire and smoke dampers required?

**Correct answer:** Ducts or air-transfer openings penetrating an assembly required to be a fire separation require a fire damper under 3.1.8.7.(1), subject to 3.1.8.8 waivers. A smoke damper or combination smoke/fire damper is required under 3.1.8.7.(2) where the separation is, for example, a public corridor, contains the specified egress door, serves an assembly/care/care-and-treatment/detention/residential occupancy, or is a separation required by 3.3.1.7.(1)(b) or 3.3.3.5.(4), subject to 3.1.8.9 waivers. Installation and smoke-detector actuation are governed by 3.1.8.10 and 3.1.8.11.

**Status:** VERIFIED as a rule path; CONDITIONAL for each PSD penetration.

**OBC authority:** Div. B, 3.1.8.7.(1)–(2), 3.1.8.8.(1)–(4), 3.1.8.9.(1)–(2), 3.1.8.10.(1)–(5), 3.1.8.11.(1)–(5).

**Trap:** Calling a fire damper a smoke damper, or treating a listed waiver as universal.

### Q11 — What are the secure-door/locking implications?

**Correct answer:** Doors in an access to exit serving a contained-use area or impeded-egress zone may have locking devices only when locally or remotely releasable under 3.3.1.13.(8) or (9). Electrically operated devices must operate on emergency power and be manually releasable by security personnel under 3.3.1.13.(10). Separately, electromagnetic locks on exit doors are subject to 3.4.6.16.(5), including fire-alarm-system integration and immediate release on the applicable alarm signal, loss of power, and authorized manual switch. Detention-grade locking is not automatically equivalent to an electromagnetic lock; the precise opening class and egress path remain predicates.

**Status:** VERIFIED rule path; CONDITIONAL project application.

**OBC authority:** Div. B, 3.3.1.13.(2), (6)–(10); 3.4.6.16.(1), (5)(a)–(g).

**Trap:** Treating maglocks, detention-grade fail-secure locks, and all power-loss behaviors as one Code category.

### Q12 — Does the high-building smoke branch apply?

**Correct answer:** **NO on the frozen physical/building facts, subject to final Code measurements.** Article 3.2.6.1 applies to Group A/D/E/F buildings over 36 m, or over 18 m with the stated occupant-load/stair-width ratio; to Group B where the highest Group B storey floor is more than 18 m above grade; to Group B Divisions 2/3 above the third storey; and to the other listed branches. PSD's approximately 13.5 m physical height is below those elevation triggers, and its B1 component is below grade. The Code measure is grade-to-floor-level/elevation of the relevant top storey, not a casual overall physical-height label.

**Status:** VERIFIED negative for the stated height/storey facts; CONDITIONAL pending final datum and occupancy map.

**OBC authority:** Div. B, 3.2.6.1.(1)(a)–(e), (2).

**Consequences:** If 3.2.6.1 is not met, the high-building-only measures in 3.2.6.2 (limits to smoke movement), 3.2.6.3 (connected high buildings), 3.2.6.4 (high-building elevator emergency operation), 3.2.6.6 (smoke shafts/mechanical venting), 3.2.6.7–3.2.6.9 (central facility, voice communication, testing), and related high-building references are not on the PSD trajectory solely by virtue of the high-building branch. Other fire alarm, separation, damper, detection and egress rules remain.

**Trap:** “Not high building means no smoke provisions.”

### Q13 — Is PSD a post-disaster building?

**Correct answer:** The definition includes police stations and vehicle housing unless exempted by the principal authority, when the building is necessary for essential public services in a disaster. PSD's project-side “post-disaster = Yes” is not enough to establish that predicate or the exemption status.

**Status:** CONDITIONAL / AUTHORITY UNRESOLVED.

**OBC authority:** Div. A, 1.4.1.2.(1), definition “Post-disaster building.”

**Trap:** Treating a project matrix flag as a Code determination, or assuming post-disaster status itself requires smoke control.

### Q14 — Does the frozen PSD scenario require a dedicated engineered smoke-control system?

**Correct answer:** **NOT YET DETERMINABLE as a project-wide conclusion.** The frozen Code path establishes mandatory or conditional measures—contained-use separation and sprinkler branch, smoke detection in contained-use rooms/corridors when a fire alarm exists, smoke-circulation prevention for qualifying air-handling systems, and damper rules at qualifying penetrations. The high-building smoke-control branch is not triggered on the current stated height/elevation facts. No inspected provision establishes a universal dedicated engineered smoke-control system for every non-high Group B1 detention building. A final YES/NO would require authoritative classification, exact geometry, air-system scope, egress strategy, authority decisions and any Alternative Solution path.

**Status:** UNKNOWN / CONDITIONAL.

**Teacher boundary:** “No dedicated system demonstrated as mandatory on the presently known predicates” is acceptable as a bounded interim observation; it must not be rewritten as “Code says no smoke control.”

**Trap:** Equating absence of a high-building trigger with permission to accept the Stage-1 “no dedicated system” proposition.

## 4. Regulatory path map

```text
PSD custody facts
  -> Div. A definitions (detention / contained-use / impeded-egress)
  -> Div. B 3.1.2 classification and 3.1.2.4 police-station relief
  -> 3.1.3.1 major-occupancy separation + 3.2.2.7 superimposition
  -> 3.2.2.19 / 3.2.2.36 / 3.2.2.37 construction and sprinkler branches
  -> 3.3.3.7 contained-use boundary and sprinkler condition
  -> 3.2.4.1–3.2.4.4 fire-alarm requirement/type
  -> 3.2.4.11 detection/staff signal + 3.2.4.12 smoke circulation
  -> 3.1.8.7–3.1.8.11 fire/smoke dampers and waivers
  -> 3.3.1.13 / 3.4.6.16 secure-door release paths
  -> 3.2.6.1 high-building branch YES/NO
  -> dedicated smoke-control verdict remains conditional until missing predicates resolve
```

3.3.3.5 and 3.4.6.10 are side branches, not automatic PSD requirements: the former is scoped to hospital/LTC sleeping areas; the latter supplies capacity rules if a horizontal exit is actually selected.

## 5. Later consultant comparison framework

For each future Code Report/OBC Matrix assertion, compare:

1. cited article/version against the frozen official text;
2. definition and applicability predicates against PSD facts;
3. exception/qualification path, including 3.3.3.7.(4), 3.1.8.8–.9 and any alternative path;
4. geometry and system evidence (compartments, doors, ducts, dampers, detectors, fans, controls);
5. whether the consultant conclusion is demonstrated, merely proposed, conflicting, or unresolved;
6. whether implementation and commissioning evidence propagate the conclusion.

Do not ingest the consultant report or matrix as authority in this task.

## 6. GO evidence trajectory and target

The Stage-1 documents usefully provide preliminary scale, storeys, custody zoning, sprinkler/fire-alarm/HVAC concepts, damper language and the explicit “no dedicated engineered smoke-control system” proposition. They do not provide authoritative classification, exact containment geometry, compartment/door/duct schedules, travel/exit data, air-system serving maps, detector locations, release cause-and-effect, post-disaster authority, or a verified Code chain.

The next blind Delta should therefore be expected to identify a **regulatory dependency**, not a pre-written smoke finding. A successful trajectory is:

`Owner outcomes → PSD/Proponent facts → consequential no-dedicated-system proposition → missing applicability predicates → governed Airlock request → verified OBC definitions/provisions → qualification/exception traversal → Evidence → Concern → Question`.

The hidden target is not a hard-coded “smoke control” answer. It is recognition that the proposition cannot be accepted or rejected from project evidence alone, followed by verified authority retrieval and an evidence-grounded characterization: demonstrated, not demonstrated, conflicting, unresolved, or supported by an accepted alternative path.

## 7. Unresolved predicates

- final B1/D classifications and any B2 police-station relief;
- exact contained-use versus impeded-egress zoning;
- final storey/grade datums and Code building-height measurement;
- exact fire-compartment and separation geometry;
- horizontal-exit/relocation strategy, if any;
- occupant loads by relevant room/zone and receiving capacity;
- final air-handling service boundaries, recirculation and damper locations;
- detector layout and two-stage cause/effect;
- detention-opening class, release authority and emergency-power behavior;
- post-disaster designation/exemption by principal authority;
- authority review and any accepted Alternative Solution;
- whether any project-specific condition creates a dedicated engineered smoke-control obligation not resolved by the provisions above.

## 8. Governance and storage boundary

This answer key extends `CODEX-PSD-SMA-PLOT-01` as protected oracle material. It is stored outside the PSD sample/project corpus, contains no project Source/EvidenceItem identifiers, and must not be copied into Owner or Proponent documents, Spin prompts, production search hints, or project conversations. No production behavior is tuned to these answers.

**GOVERNANCE DELTA: ADDITIVE** — additive protected test/oracle material only; no project authority, Airlock promotion, schema, Spin rule, or smoke-specific production trigger is created.
