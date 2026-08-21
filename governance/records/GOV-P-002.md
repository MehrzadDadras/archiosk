# GOV-P-002 — Work surfaces carry the work; control surfaces carry the machinery

- **GOVERNANCE ID:** GOV-P-002
- **TITLE:** Work surfaces carry the work; control surfaces carry the machinery
- **TYPE:** Governance Principle
- **VERSION:** v1.0
- **STATUS:** CURRENT

## Authority

- **AUTHOR / PROPOSER:** Claude, under `CLAUDE-GOVERNANCE-CLOSEOUT-01`
- **APPROVING AUTHORITY:** Product Owner
- **APPROVAL DATE:** 2026-08-21
- **EFFECTIVE DATE:** 2026-08-21

## Scope

- **GOVERNS:** Where substantive work and context belong across ARCHIOSK's surfaces —
  panels, docks, nested page templates, menus, toolbars, control clusters, settings
  and configuration surfaces. It governs **allocation**: which kind of surface a
  capability belongs on.
- **OUT OF SCOPE:** Panel lifecycle and restoration behaviour, which
  `CIC-PANEL` v1.0 already governs and which this record does not restate — closing
  never deletes data, menus are the canonical restoration path, primary work
  surfaces are not closable. Also out of scope: visual design, layout geometry,
  specific menu contents, and whether any given surface exists at all.

## Principle

> **Work surfaces carry the user's substantive work and context. Control surfaces —
> menus, toolbars, settings and configuration — carry the supporting machinery that
> operates on that work, and must not become substitute workspaces.**

The rule is directional and applies both ways: substantive work does not migrate
into a menu, and a work surface does not degrade into a catalogue of permanent
controls.

## Rationale

The related rules already exist and are consistent, but none of them reaches the
case this principle governs:

| Existing authority | What it covers |
|---|---|
| `CIC-PANEL` v1.0 | "Panel visibility is not data lifecycle; closing never deletes data… Menus are the canonical machinery/restoration path where available." |
| `current/panel-template-system.md`, "Panel behavior principles" | Closing hides only; restoring uses existing menu/route machinery; "panels do not grow scattered reopen buttons"; primary work surfaces are not closable |

Both state that **menus are where machinery lives**. Neither states the converse —
that machinery surfaces must not accumulate substantive work — and nothing prevents
a settings or configuration surface from quietly growing into a second workspace.

**The gap is a scope gap, not an omission.** `CIC-PANEL`'s own `APPLIES WHEN` clause
binds it to work that materially changes "a page layout, panel, dock, nested surface,
or panel visibility/restoration behavior." A menu accumulating substantive work need
not touch a panel at all, so `CIC-PANEL` would not apply to the very change this
principle exists to catch. Extending `CIC-PANEL` was considered first and rejected
for that reason: the rule has to bind surfaces that contract does not govern.

Recorded as drift cluster **DC-04** in
[`../back-catalog/DRIFT-AND-LINEAGE.md`](../back-catalog/DRIFT-AND-LINEAGE.md), which
flagged the concept as cross-cutting but single-sourced. Investigation for this
record found the cross-cutting *lifecycle* half is well covered by the two records
above; the genuinely missing half is allocation.

## Invariants

- Substantive user work and project context are reachable on a work surface, not
  only from inside a menu or configuration surface.
- A control surface may launch, restore, configure or act on work; it does not
  become the place work is performed or read at length.
- A capability added to a menu does not thereby become the only route to the work it
  operates on.
- Work surfaces do not accumulate permanent technical controls in place of the work
  they exist to carry.

## Allowed variation

Deliberately broad — this principle constrains allocation, not design.

- Which surfaces exist, their number, geometry, arrangement and visual treatment.
- Menu contents, grouping, nesting and naming.
- Short-lived or in-context controls placed on a work surface where they operate on
  what is in view — an inline toolbar is machinery *serving* the work, not a
  catalogue replacing it.
- Small, self-contained interactions completed entirely within a menu — choosing a
  setting, toggling visibility, picking a target — none of which is "substantive
  work" in the sense used here.
- Progressive disclosure, drawers, popovers and modals, provided the work itself
  remains reachable on its own surface.
- Any arrangement `CIC-PANEL` and the Page/Surface Template Inventory already permit.

## Prohibited drift

- Reading this as "menus may not be useful", or as a reason to strip machinery out
  of menus. `CIC-PANEL` says menus **are** the canonical machinery path; this record
  does not weaken that.
- Reading it as forbidding controls on work surfaces. The prohibition is on a work
  surface becoming *predominantly* a control catalogue, not on any control appearing.
- Using it to block a UI change on aesthetic grounds. This is an allocation rule; it
  is not a design review.
- Treating "substitute workspace" as satisfied by any menu that renders content. The
  test is whether a user would reasonably do sustained work there, not whether text
  appears.
- Deriving additional rules from the slogan this principle was requested under.
  The slogan is not the governance; this record is, and it says only what is written
  above.

## Verification

- **HOW COMPLIANCE IS DEMONSTRATED:** Review-time, not automated. When a change adds
  substantive capability, the order states which surface class carries it and why.
  `CIC-PANEL`'s existing panel/parity checks continue to cover lifecycle behaviour.
- **TESTS / CHECKS / ORACLES:** **None, and none is proposed.** This principle is
  judged at review, not asserted mechanically. A future `GOV-I` could test narrow
  consequences, but a test that tried to decide "is this a substitute workspace"
  would encode a judgement the principle deliberately leaves to a reviewer.

## Dependencies

- **RELATED GOVERNANCE:** `current/panel-template-system.md` ("Panel behavior
  principles") · `current/page-surface-template-inventory.md` (progressive template
  discipline). This record adds to both; it supersedes neither.
- **STANDING CONTRACTS:** `CIC-PANEL` v1.0 — owns panel identity, lifecycle,
  restoration and the operational obligations. `CIC-PAGE-TEMPLATE` v1.0 — owns
  reference selection and parity discipline. **Neither is amended by this record.**
- **RELATED VISION (explanatory only, non-governing):** [`VIS-001`](../vision/VIS-001.md)
  prefers "intent plus selected context plus conversation" over "a catalogue of
  permanent technical controls." That vision is *consistent with* this principle and
  is **not** its authority — this record stands on the two governance records above.
- **REQUIRED IMPLEMENTATION ORDERS:** None. **No panel, menu, layout or template
  behaviour is changed by this record.**

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** Any widening into layout, visual design or
  specific surface contents; any narrowing of the allowed variation list.
- **AMENDMENT / SUPERSESSION RULE:** New version via `GOV-CN` and `GOV-S`. Never an
  in-place meaning edit.

## Lineage

- **SUPERSEDES:** None. `CIC-PANEL` and `panel-template-system.md` remain in force
  unchanged; this record covers the allocation case neither reaches.
- **SUPERSEDED BY:** None.
- **RELATED DECISIONS:** Product Owner decision 5 of `CLAUDE-GOVERNANCE-CLOSEOUT-01`,
  which directed that the underlying principle be established first and that no
  analogy record be filed for the slogan.

## Governance delta

`ADDITIVE`
