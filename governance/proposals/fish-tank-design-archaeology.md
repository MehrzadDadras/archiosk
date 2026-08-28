# Fish-Tank Design Archaeology

**Status:** investigation record. Proposes; authorizes nothing.
**Date of investigation:** 2026-08-28.
**Method:** read-only inspection of primary artifacts. No file outside this
record was modified during the investigation.

This is an archaeology, not a design. It reports what the artifacts say,
distinguishes what was measured from what was inferred, and records one
correction against work in progress. Where a claim rests on a single
observation it says so.

---

## 0. What the site is, and where

The "fish tank" is **not in this repository and never has been.** It is:

```
C:\Archiosk\holodeck\archive\
```

a directory of **232 files, 19,337,785 bytes, dated 2026-05-03 to 2026-05-10**,
inside a separate git repository (`C:\Archiosk\holodeck\`).

This repository cites it exactly once, in `291d2cf`:

> Visual/atmospheric lineage studied directly from two historical artifacts
> (both outside this repo, at the Product Owner's direction):
> `C:\Archiosk\holodeck\archive\archiosk_holodeck_v_3.html` …

The name collision is worth stating early, because it has already misdirected
one piece of work. `governance/prompt-depository/CLAUDE-HOLODECK-WORLDS-SPIN-01.md`
and `tests/test_holodeck_worlds_spin_01.py` are **not** this. That record is
about Spin Worlds and Survival Mode; its implementation (`f829f27`) adds a
checkbox, prompt framing and a `games_played` trace, and contains no canvas, no
motion and no fish. Two different things share the word "Holodeck."

For completeness, since a previous session's note overstated it:
`CLAUDE-HOLODECK-WORLDS-SPIN-01` is only **partially** superseded. Its own text
scopes the supersession to the PM-facing use of the name; the underlying
architecture is explicitly not superseded, and
`governance/back-catalog/DRIFT-AND-LINEAGE.md` §LC-02 calls it "the corpus's
model example, and the only one of its kind: 1 explicit supersession across 121
records."

### 0.1 Custody — the finding with a deadline

`C:\Archiosk\holodeck\.gitignore` line 1 is:

```
archive/
```

Verified with `git check-ignore -v`. The holodeck repository tracks **5 files**.
Commit `4360f99 v2.21 metabolize archive copies out of active Git tracking`
removed the archive deliberately.

**All 232 artifacts therefore exist as a single uncommitted copy on one disk,
versioned only by filename.** `LAST_ROLLBACK_POINT.txt` is a plain text file
containing one path. Every finding in this document depends on evidence with no
second copy.

This is not a stylistic objection. The archive is the sole record of roughly a
week of design reasoning that this repository is currently mining for product
decisions, and it is one disk failure from being unrecoverable. A backup
strategy is proposed separately in
`governance/proposals/holodeck-archive-custody.md`.

---

## 1. Stratigraphy

The filenames are the record. Reproduced from the directory listing, with the
retreats kept in, because the retreats are the finding.

| Stratum | Artifact | What changed |
|---|---|---|
| v1.4 | `GRAVITATIONAL_DOT_FIELD` | canvas particle field |
| v1.5 | `VISIBLE_GRAVITY_DOT_MATRIX` | the field made legible |
| v1.6 | `EDGE_TO_EDGE_ARCHIOSK_FIELD` | field fills the viewport |
| v1.7 | `AQUATIC_COLOR_FIELD` | the water arrives |
| v1.8 | `TRUE_UNDERWATER_SKIN_FIELD` | |
| **v1.9** | **`WORD_FISH_UNDERWATER`** | **static labels become moving fish** |
| v2.0 | `VISIBLE_WORD_FISH_FIX` | they were not visible enough |
| v2.1 | `PROCUREMENT_MODEL_FISH_TROPICAL` | fish acquire meaning: PDB/CM/DB/… |
| v2.2 | `PROCUREMENT_MODEL_FISH_VISIBLE_SAFE_BASE` | |
| v2.3 | `ANIMATED_PROCUREMENT_MODEL_FISH` | |
| v2.4 | `CLICKABLE_PROCUREMENT_FISH_ENVIRONMENTS` | fish become navigation |
| v2.5 | `CLEAN_FIELD_ENVIRONMENT_START` | |
| v2.6 | `PDB_SCHOOL_OF_FISH_ENVIRONMENT` | |
| v2.7 | `EDGE_TO_EDGE_REPAIR` | |
| **v2.8** | **`ROLLBACK_TO_v2.6`** | **v2.7 abandoned** |
| v2.9 | `CM_SIDE_LIST_RELATIONSHIP_GRAPHIC` | |
| v2.10 | `FISH_IDLE_GLOW_ACTIVATION` | |
| v2.11 | `SUBTLE_JERKY_FISH_MOTION` | motion realism |
| v2.12 | `CONTACT_BUBBLE_STREAM_VISUAL_ONLY` | |
| v2.13 | `RANDOM_DISTANCE_FISH_SWIM` | |
| v2.15 | `SELECTION_RIPPLE` / `AQUEOUS_GHOST_INTRO` | two v2.15s exist |
| v2.16 | `PROJECT_DELIVERY_FISHWORD_LINKS` | |
| v2.17 | `ADD_ALLIANCES_FISHWORD` | |
| v2.17.1 | `…_FISHWORD_LINKS_**FIXED**` | links did not work |
| v2.17.2 | `…_LINKS_**REPAIRED**` | they still did not work |
| v2.18 | `GEOMETRIC_SWIMMER_WORDS` | bespoke swimmer geometry |
| **v2.20** | **`PLAIN_ANCHOR_CLICKABLE_FISHWORDS`** | **"Icons and geometry effects abandoned"** |
| v2.21 | `DELIVERY_MODEL_NARRATIVE_ROOMS` | |
| v2.22 | `MODULAR_ROOMS_REFACTOR` | |
| **v3.0** | **`HOMEPAGE_SIGNAL_FISH_ACTIVATION`** | **fish stop being destinations** |
| V3_ATOMIC… | home / PDB authority / environment screens / DBB rooms / fire beetle / knowledge base / relationship tree | |

Plus ~40 timestamped `before-<change>` rollback snapshots, several of which name
their own failure directly: `before-rollback-to-working-fish-engine`,
`before-fish-click-destination-fix`, `before-fish-destination-visibility-fix`,
`before-v3.1-unlock-all-fish-gates`.

**Read the shape, not the peak.** Four consecutive versions
(v2.16 → v2.17 → v2.17.1 → v2.17.2) are attempts to make a fish reliably
clickable. v2.18 answers with more bespoke geometry. v2.20 abandons the whole
approach and states why in its own header:

> Corrective purpose: Fix clickability using real HTML anchor links only.
> **No JavaScript is required for fish-word navigation.**
> … Icons and geometry effects abandoned.

The experiment ran itself into the ground over five versions and came back with
`<a href="#room">`. That is the most expensive lesson in the archive and the
cheapest one to inherit.

---

## 2. The core invariant

> **Moving things are atmosphere and are unreachable.
> Reachable things do not move.**

The archive is the record of one design attempting to violate this and paying
for it in five versions of rework. This repository, arriving at the same
material independently, wrote the same rule into shipped code.

**Evidence for, from the archive.** v1.9 — the first fish — carried:

```css
.archiosk-field-label {
  pointer-events: none !important;
}
```

The fish were literally unreachable. "Catching" was simulated with cursor
distance arithmetic (`const caught = pointer.active && dist < 54;`) which toggled
a class. There was no focus, no hit-test, no keyboard path. The object wore the
costume of interaction while being incapable of it — which is the failure mode
worth naming, because it is fluent. It reads as interactive to a sighted mouse
user and is inert to everyone else.

Everything from v2.0 to v2.18 is the cost of making that object genuinely
reachable while keeping it in motion.

**Evidence for, from this repository.** `c6b26bd` built the shipped ambient
layer, and `static/js/landing.js` states the boundary in its own comment:

> set from the Product Owner's own list. Not links/buttons (no href,
> no click handler, the whole container is `pointer-events: none`).

And `291d2cf` recorded the refusal explicitly:

> Deliberately NOT carried forward: the swimming "fish" procurement-model
> navigation, the PDB/CM/DB environment rooms and relationship diagrams, and
> the contact-bubble/mailto form.

The repository took the water and refused the fish. On this evidence that was
correct, and the archive is the reason.

**Status:** supported by two independent lines of evidence (the archive's own
five-version retreat, and the shipped landing layer's separate arrival at the
same boundary). Not isolated — no controlled trial was run, and none is
proposed. This is a design rule with a strong evidential base, not a measured
invariant.

---

## 3. Recovered mechanics

Three mechanisms in the archive are load-bearing, and **none of them is written
down anywhere.** They survive only in the artifacts. They are the reason to keep
the archive, and they are recovered here so that the record no longer depends on
one disk.

### 3.1 Channel separation — the motion channel is not the interaction channel

Two engines survive. They were written days apart, in different styles, and they
agree.

**v2.20 (CSS engine)** — motion is a keyframe on **margin**:

```css
@keyframes ahFishSwim {
  0%   { margin-left: 0;                             margin-top: 0; }
  18%  { margin-left: calc(var(--travel) * .28);     margin-top: calc(var(--drift) * -.22); }
  43%  { margin-left: calc(var(--travel) * .68);     margin-top: calc(var(--drift) * .54); }
  72%  { margin-left: calc(var(--travel) * .34);     margin-top: calc(var(--drift) * .94); }
  100% { margin-left: var(--travel);                 margin-top: var(--drift); }
}
```

**`archiosk_holodeck_v_3.html` (JS engine)** — motion is written to **layout
position**:

```js
button.style.left = safe.x + 'px';
button.style.top  = safe.y + 'px';
```

Neither engine writes `transform`. In both, `transform` is reserved exclusively
for interaction state:

```css
.ah-wordfish                              { transform: translate(-50%, -50%); }
.ah-wordfish:hover,
.ah-wordfish:focus-visible                { transform: translate(-50%, -50%) scale(1.08); }
```

**This is not a stylistic preference; it is forced.** A running CSS animation on
`transform` wins the cascade over a non-animated `transform` declaration. Had
either engine animated `transform`, the hover/focus `scale(1.08)` would have
been silently overridden and the focus affordance would have vanished — with no
error, on the one state a keyboard user depends on.

**The rule: the physics owns layout position (`left`/`top`/`margin`); the
interaction state owns `transform`.** Cross them and the interaction feedback
disappears into the animation.

**Status: measured.** Two independent implementations, both consistent, read
directly from the artifacts.

### 3.2 Proximity activation without drift

v1.9 introduced proximity response and got it wrong in an instructive way:

```js
const near   = pointer.active && dist < 150;
const caught = pointer.active && dist < 54;
…
if (near) { f.x += dx * 0.008; f.y += dy * 0.008; }   // attraction toward cursor
```

The fish *moved toward the cursor*. Combined with `pointer-events: none`, the
target both fled its own position and could not be clicked once reached.

`v_3.html` keeps the proximity band and **deletes the drift**:

```js
const near = Math.sqrt(mdx * mdx + mdy * mdy) < 96;
if (near) button.classList.add('is-hovered');
else if (!button.matches(':hover')) button.classList.remove('is-hovered');
```

Proximity now changes **state only**. Position is unaffected. The object
brightens as you approach it and stays exactly where it was.

**The rule: proximity may change appearance; it must never change position.**
An object that moves in response to being approached is an object that cannot be
acquired — and the closer the user gets, the worse it behaves.

**Status: measured**, as a corrected defect across two strata.

### 3.3 Hover-freeze

The mechanism that finally made a moving target acquirable:

```js
const frozen = button.matches(':hover') || button.classList.contains('is-hovered');
if (!frozen) s.angle += s.speed;
```

**Hovering halts the object's orbit.** You can catch a moving target because
approaching it stops it being one. Note that the freeze is driven by the same
proximity band as §3.2, so the object stops *before* the cursor arrives, not on
contact.

This is the single most useful idea in the archive for any future moving-object
work, and it appears in no note, commit message or governance record. It exists
only in `archiosk_holodeck_v_3.html`.

**Status: single observation.** One implementation, no comparative trial, no
recorded user reaction. Whether it is sufficient for acquisition — particularly
for motor-impaired users, for whom it is most relevant — is **unmeasured**.

### 3.4 Territory and separation

For completeness, since work in progress refers to these:

```js
const fishState = {
  PDB:  { angle: 3.60, speed: 0.00105, radiusX: 0.31, radiusY: 0.15, centerX: 0.50, centerY: 0.53, … },
  DB:   { angle: 4.75, speed: 0.00092, radiusX: 0.18, radiusY: 0.12, centerX: 0.50, centerY: 0.40, … },
  …
};
```

Each object holds an **elliptical home orbit** — a centre and two radii — so it
stays roughly findable. `keepOutOfReef()` adds an exclusion zone. Separation is a
per-frame pass with `minGap` of 118px desktop / 86px mobile, pushing overlapping
objects apart.

Both are per-frame forces. Both have exact layout-time equivalents: a home
region becomes a fixed position, and a separation force becomes packing.

---

## 4. The warrant for Still Page-Fields

The strongest finding in this investigation was not in the physics.

`archiosk_holodeck_v_3.html` carries **two** fish taxa, not one.

```html
<!-- taxon 1: navigation. driven by requestAnimationFrame. -->
<button class="procurement-fish fish-pdb" data-env="PDB">…

<!-- taxon 2: signals. -->
<button class="signal-fish signal-risk"       type="button">Risk Register</button>
<button class="signal-fish signal-assumption" type="button">Assumption Log</button>
<button class="signal-fish signal-decision"   type="button">Decision Log</button>
<button class="signal-fish signal-rfi"        type="button">RFI Flow</button>
<button class="signal-fish signal-milestones" type="button">Milestones</button>
<button class="signal-fish signal-cost"       type="button">Cost Validation</button>
<button class="signal-fish signal-fpp"        type="button">FPP / GMP</button>
```

The `signal-fish` are placed by static CSS:

```css
.signal-risk{left:22%;top:30%}  .signal-assumption{left:30%;top:42%}
.signal-decision{left:24%;top:56%} .signal-rfi{left:50%;top:28%}
.signal-milestones{left:52%;top:62%} .signal-cost{left:72%;top:42%}
.signal-fpp{left:76%;top:58%}
```

The animation loop queries `root.querySelectorAll('.procurement-fish')` and
nothing else.

**The signal fish never move.**

Two changes land in the same version, v3.0 `HOMEPAGE_SIGNAL_FISH_ACTIVATION`. The
objects stop meaning *navigation destination* — PDB, CM, DB: where you go — and
start meaning *signal competing for attention* — Risk, Assumption, Decision, RFI,
Cost: what you should look at. And in that same step, they stop swimming.

**The archive independently reached the position the Calm Lake work is now
taking, and reached it because the meaning changed.** Once an object represents
something you must not miss, motion stops being atmosphere and starts being an
obstacle between the reader and a judgement.

This matters for how the current work is justified. Stillness is available as
the archive's own terminal conclusion about attention objects — not as a
restraint imposed on a recovered design, and not as a taste. The stronger
warrant is the one the evidence actually supports, and it is free.

**A miniature is a claim.** A tile showing a picture of a document asserts "this
is what that surface looks like." A stale cached picture makes that assertion
more fluently than a sentence could, and terminates inquiry faster — which is the
same failure the citation-basis vocabulary exists to prevent, in visual form.
The archive's own version of this error is v1.9: an object that *looked*
interactive and was `pointer-events: none`. A miniature must therefore carry its
own basis, exactly as a citation does, and `cached` is deliberately not a member
of that vocabulary: a captured thumbnail is the one representation that cannot
state its own age from inside itself. Standing still is what makes a live
miniature affordable.

---

## 5. Correction recorded against work in progress

At the time of this investigation, `routes/calm_lake_prototype.py` carried an
uncommitted comment reading:

> "The object is a real, focusable `<button>`. In the archive the physics only
> ever wrote `transform` to it, which is why keyboard focus and hit-testing came
> free."

Measured against the artifacts:

| Claim | Verdict |
|---|---|
| real focusable `<button>` | **correct for `v_3.html`**; wrong for v2.20 (`<a href>`) and wrong for v1.9 (`pointer-events: none`, unfocusable) |
| "physics only ever wrote `transform`" | **false in every stratum.** `left`/`top` in `v_3.html`; `margin-left`/`margin-top` in v2.20. `transform` was written by exactly one version — v1.9, the one that was *not* focusable |
| "which is why focus and hit-testing came free" | **inverted.** They came free from being a real `<button>`/`<a>` with `pointer-events: auto`. The archive *avoided* `transform` precisely to protect the focus state (§3.1) |

The conclusion was right and the stated mechanism was a blend of two strata that
holds for neither. This is worth recording rather than quietly fixing, because
it is a small instance of the failure the Calm Lake work exists to address: a
fluent citation to an archive nobody re-opened. The comment was corrected in the
same change that wired the Page-Field through.

---

## 6. What this proposes, and what it does not

**Proposes:**

1. The invariant in §2 as a design rule for this repository's surfaces.
2. §3.1 and §3.2 as binding on any future moving-object work.
3. §4 as the warrant for still Page-Fields, replacing any aesthetic argument.
4. Urgent action on §0.1.

**Does not propose:** recovering the fish, the rooms, the aquatic palette, the
bubble stream or the beetle. `291d2cf`'s refusal stands and this investigation
strengthens it.

**Explicitly unmeasured:**

- Whether hover-freeze (§3.3) is sufficient for acquisition by motor-impaired
  users. One implementation, no trial.
- Why v2.17.1 and v2.17.2 failed. Both are named `FIXED`/`REPAIRED`; neither
  records the defect.
- Whether any of this was ever seen by a user other than the Product Owner. No
  reaction of any kind is recorded in the archive.
- The two artifacts both numbered v2.15 (`SELECTION_RIPPLE`,
  `AQUEOUS_GHOST_INTRO`) — which superseded which is not recoverable from the
  filenames, and their timestamps are 47 minutes apart with no note.

---

## 7. Provenance

Primary artifacts, all read directly:

| Artifact | Role |
|---|---|
| `C:\Archiosk\holodeck\archive\` (232 files) | the site |
| `…\ARCHIOSK_HOLODECK_v1.9_WORD_FISH_UNDERWATER_FULL_REPLACEMENT.txt` | first fish; `pointer-events: none`; drift-toward-cursor |
| `…\ARCHIOSK_HOLODECK_v2.20_PLAIN_ANCHOR_CLICKABLE_FISHWORDS_FULL_REPLACEMENT.txt` | the retreat; CSS engine; margin motion |
| `…\archiosk_holodeck_v_3.html` | JS engine; `left`/`top` motion; hover-freeze; both fish taxa |
| `C:\Archiosk\holodeck\.gitignore`, `git check-ignore -v` | custody |
| `4360f99` (holodeck repo) | archive removed from tracking |

In this repository:

| Artifact | Role |
|---|---|
| `291d2cf` | the citation, and the refusal |
| `c6b26bd` | the shipped ambient layer |
| `static/js/landing.js`, `static/css/landing.css` | the boundary, in shipped code |
| `f829f27`, `governance/prompt-depository/CLAUDE-HOLODECK-WORLDS-SPIN-01.md` | the name collision — unrelated |
| `governance/back-catalog/DRIFT-AND-LINEAGE.md` §LC-02 | supersession scope |

Quotations from artifacts are verbatim. Version names are as they appear in the
directory listing, including the inconsistencies.
