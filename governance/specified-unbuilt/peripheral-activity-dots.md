# Specified But Unbuilt — Peripheral Activity Dots (Lists list-item unseen-activity signal)

**Status:** Specified (Product Owner addendum, CLAUDE-CA1D, two messages — the base spec and a
visual refinement), **not implemented**. Deferred by the Product Owner's own explicit instruction:
*"If this materially expands the current tranche beyond the surfaces already being touched, record
the design and defer implementation rather than forcing it in."* It arrived mid-flight on the
CLAUDE-CA1D-COMPOSER-CONTEXT-LABEL-01 tranche (a Chat-composer-only change); a cross-cutting,
multi-entity-type Lists primitive is a different surface and a different scope, so it was recorded
here rather than folded into that commit.

## The request, as given

A small, restrained activity dot beside any Lists item (document, task, investigation, RFI,
delegated work item, or other list entity) that has new/changed state the user hasn't meaningfully
reviewed yet — preserving peripheral awareness without auto-opening, foregrounding, or rearranging
the workspace. A collapsed parent section may carry a quiet aggregate dot without auto-expanding.

Governing principles, verbatim: *"Hidden capability may remain dormant; changed state may still
signal at the edge."* / *"Signal attention without interrupting attention."*

**Visual refinement (second message):** the dot is not the only signal — the item's own name/label
text should render in the same activity-accent color, crisp and fully legible, with **no** colored
row background, no whole-row tint, no reduced opacity, no glow, no badge/pill treatment. Just
"colored dot + crisp same-color item name" against the normal dark navigation background. Both the
dot and the name-color revert to normal once the activity is meaningfully reviewed. Selected
("where I am") and unseen-activity ("something happened here") must stay distinguishable — a
combined state needs its own restrained treatment, never one signal silently erasing the other.

Color rules: one quiet shared accent (ARCHIOSK blue) for ordinary activity; amber/orange only when
attention is genuinely needed; red only for a genuine blocker/error/risk; green only if a
completed/returned state genuinely benefits from separate signaling; no rainbow of status colors;
never infer blocker/attention semantics the underlying domain state doesn't actually support.

## What already exists — grounded, not assumed (repository-inspected before this record was written)

**Count badges** (`.launcher-count`, `static/css/main.css:744-751`) already sit at the trailing
edge of every Lists row (Documents/Requirements/Investigations/RFI Correspondence/Work
Products/Chats/Tasks/Tags — see `templates/base.html`, computed in `routes/workspace.py`), via the
tree-toggle row's own `justify-content: space-between` layout. This is the natural, already-precedented
location for a new dot — the *leading* edge is already claimed (see below).

**The leading edge is already claimed by selection state.** `.launcher-link.active`
(`main.css:635-640`) uses a 2px `border-left` in `--machine-blue` plus a light `color-mix`
background wash — explicitly documented as "machine/system, this is what's displayed." `.current-project`
(`main.css:652-661`) uses a 3px `border-left` in `--border-strong`, no fill. **Any new dot reusing
`--machine-blue` must not collide, spatially or semantically, with `.active`'s own existing use of
that exact color on that exact edge** — this is precisely the "selected vs. unseen must not be
confused" risk the Product Owner named, and it is a real, pre-existing collision risk, not a
hypothetical one. Trailing-edge placement (next to `.launcher-count`) avoids it structurally.

**A real "have they seen this" mechanism already exists — but at the wrong granularity.**
`ProjectWorkspace.last_viewed_by` (`services/case_workspace.py:3812`) + `CaseWorkspaceStore.record_last_viewed`
(lines 4724-4788) persist one timestamp **per reviewer per project** (not per item), updated on
every Project Home visit. `routes/workspace.py:968-988` derives `since_last_visit` — an actual "N
updates since you last looked" count, computed fresh from `GovernanceLog` events newer than that
timestamp — and it already feeds two things: a text banner on Project Home
(`templates/case_workspace.html:1739-1747`) and the unrelated "visual pressure" quieting of settled
Requirements (`routes/workspace.py:1467-1490`, reusing the *same* boundary rather than inventing a
second one — an explicit, stated norm in this codebase worth following here too). **This is real,
reusable groundwork for the "ordinary activity" half of the feature — but it cannot, as it stands,
satisfy "clear only when THIS item was meaningfully reviewed."** Visiting Project Home today would
implicitly clear every item's would-be dot at once, not just the one actually opened. Extending this
to real per-item granularity is a genuine design gap, not a detail to wave away — see Open
Questions below.

**Per-entity recency timestamps already exist and are enough to detect "changed," if not yet "seen":**
- Task (`services/case_workspace.py:1476-1493`): `created_at`/`completed_at`/`reopened_at`.
- RFI (`RFIDraft`, lines 2112-2141): `created_at`/`issued_at`/`responded_at`, status enum
  (`draft`/`issued`/`answered`).
- Requirement adjudication (`RequirementAdjudication`, lines 1664-1721): `adjudicated_at`,
  append-only.
- Source revision: no `revised_at` on `Source` itself — a revision creates a **new sibling Source**
  (`register_source_revision`) plus a `Supersession` and a Case-level `RevisionNotice` (its own
  `created_at`) — today's actual "this changed" signal for documents, currently surfaced only at
  the Case level, not per-Source-row in Lists.
- **"Delegated work item" does not exist as a concept anywhere in this codebase** — confirmed by
  direct grep, not assumed absent. The one hit for "delegat-" is explicit unbuilt-scope prose in
  `share_case`: *"No delegated sharing authority exists yet."* Any dot logic for this entity type is
  therefore unbuildable until delegation itself exists — named here so it isn't silently forgotten
  as "should just work like the others."

**No existing "unread dot" CSS.** Closest precedents: `.launcher-tag-swatch` (`main.css:862-869`,
`border-radius: 50%`, already circular, already inside the Lists tree — but represents a *chosen
color*, not activity state) and the `.dot`/`.dot-done`/`.dot-active`/`.dot-pending` family
(`main.css:1437-1440`, `border-radius: 2px` — square-cornered, lifecycle-position semantics, not
recency). The `[data-state]`-driven conditional-color idiom already used by `.voice-input-status`
(quiet by default via `:empty`, colored only when a specific state is true) is a reusable *pattern*
for "quiet unless something is true," even though built for status text, not a dot.

**Color tokens — confirmed exact, not assumed:** `--machine-blue` `#235066` (ordinary/machine),
`--attention-amber` `#7A4A08` (needs attention), `--accepted-green` `#2E5F38` (accepted/confirmed).
**Two different reds exist and must not be conflated:** `--failure-red` `#8C2E22` ("contradiction /
failure") is the correct token for a genuine blocker/error; `--seal-red` `#7A1911` is a *different*
token reserved for "human authority / deliberate commitment," explicitly *not* ordinary
error/failure per `tokens.css`'s own header. A future implementation must use `--failure-red`, never
`--seal-red`, for the blocker/error dot state. `--pressure-quiet-text` (`tokens.css:264`) is the
existing inverse-direction precedent — a token for de-emphasizing settled/old content — confirming
this codebase already has a *recency-weight* concept, just pointed the opposite way from what "new/
unseen" needs.

**Tree collapse/expand state** is tracked via `data-tree-open` (presence-based, on `.tree-children`)
paired with `aria-expanded`, toggled client-side at `templates/base.html:1920-1932`; parent rows
already carry `data-tree-owns` identifying which item family a branch controls — a real, existing
scriptable hook a future aggregate-dot could read, not a new mechanism to invent.

## Explicit assessment: does this fit the smallest-tranche discipline this repository has been
using all session?

No, correctly deferred. It touches Documents, Tasks, Investigations, RFI Correspondence, Work
Products, and (once it exists) delegated work items — six-plus entity families across `services/
case_workspace.py`, multiple `routes/workspace.py` view assemblies, and `templates/base.html`'s
Lists tree — categorically wider than the one Chat-composer surface CLAUDE-CA1D-COMPOSER-CONTEXT-LABEL-01
was scoped to. Forcing it in would have repeated the exact mistake the Instrument Rail plan-mode
report warned against: bundling a UI wiring decision into a change that hadn't yet proven the
underlying mechanism (here: per-item "seen" tracking, which does not yet exist) was reliable.

## Open questions a real implementation pass would need to resolve (not decided here)

1. **Per-item "seen" granularity.** `last_viewed_by` is per-project, per-reviewer. Does closing this
   gap mean a new per-item-per-reviewer acknowledgment store (a real new persisted concept, not
   free), or is a coarser "seen bucket" (e.g. per-branch, mirroring the count-badge granularity)
   an acceptable compromise the Product Owner should explicitly choose, not have assumed for them?
2. **What "meaningfully reviewed" means per entity type** — opening a Document, expanding a Task
   row, viewing an RFI's response, and acknowledging a Requirement adjudication are not the same
   gesture; each needs its own real trigger, not one generic "clicked it once" rule (explicitly
   ruled out: clearing "merely on hover").
3. **Aggregate-dot rule for a collapsed parent** — "any child unseen" vs. a weighted/count-aware
   signal is a real product decision, not an implementation detail.
4. **The combined selected+unseen treatment** the Product Owner asked for explicitly needs its own
   small design pass (not simply layering both CSS states) given `.active` already owns the leading
   edge in `--machine-blue` — the same color ordinary-activity dots would use.
5. **Delegated work items** cannot be built against until delegation itself exists as a real
   concept in this codebase (see above) — this dependency should be stated to the Product Owner
   directly, not discovered again later.

## Smallest future first slice, if approved later (not started)

A single entity type (Tasks is the best-grounded candidate — real `created_at`/`completed_at`/
`reopened_at` timestamps already exist, and its Lists row already has a stable count-badge anchor
point) with a coarse, disclosed "seen" granularity (e.g. per-branch, not per-task), trailing-edge
placement, `--machine-blue` for ordinary/new, reusing the existing `[data-state]`-conditional-color
CSS idiom — before generalizing to every entity family or attempting the collapsed-parent aggregate
case.
