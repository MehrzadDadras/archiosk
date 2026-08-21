# TEMPLATE — Governance Supersession Record (`GOV-S-`)

**Purpose.** Replace or narrow existing governance while preserving the prior
wording and the lineage between them.

**Never erase the superseded record.** It stays where it is, marked `SUPERSEDED`,
so every existing citation to it still resolves and the reasoning that produced it
stays readable. Deleting or retroactively "fixing" a superseded record is
prohibited by `constitutional-invariants.md` #5 and by
`amendment-and-ratification.md`'s historic-preservation rule.

**Partial supersession is the common case, not the exception.** Most changes
replace one clause of a record, not the whole thing. Say which — an unscoped
supersession silently voids clauses nobody intended to touch.

---

```markdown
# GOV-S-nnn — <Title>

- **GOVERNANCE ID:** GOV-S-nnn
- **TITLE:** <what replaces what, in one line>
- **TYPE:** Governance Supersession Record
- **VERSION:** v1.0
- **STATUS:** CURRENT

## Authority

- **AUTHOR / PROPOSER:** <who>
- **APPROVING AUTHORITY:** <who approved the replacement>
- **APPROVAL DATE:** <YYYY-MM-DD>
- **EFFECTIVE DATE:** <YYYY-MM-DD — when the new record starts governing>

## Superseded record

- **RECORD:** <exact id and version, e.g. GOV-P-004 v1.0>
- **SUPERSESSION EXTENT:** `FULL` | `PARTIAL`
- **SUPERSEDED SCOPE:** <if PARTIAL: exactly which clauses, sections, or
  invariants stop governing. Be specific enough that a reader can mark up the old
  record from this line alone.>
- **PRIOR WORDING:**

  > <Verbatim quote of the text that stops governing. This is the record's most
  > important field: after this, the old record is marked SUPERSEDED and a reader
  > may not re-derive what changed from it alone.>

## New governing record

- **RECORD:** <exact id and version, e.g. GOV-P-004 v2.0>
- **NEW WORDING:**

  > <Verbatim quote of the text that now governs.>

## Relationship type

`SUPERSEDED` | `ABSORBED`

<`SUPERSEDED` — the identified earlier rule no longer governs within the stated
scope. `ABSORBED` — the governing concept continues through the named successor
rather than ending. Both must identify scope and successor; similarity or overlap
alone is neither. These meanings are fixed by `amendment-and-ratification.md` and
are not redefined here.>

## Reason

<Why the replacement was made. Cite the `GOV-CN-` that proposed it, the `GOV-CR-`
that exposed the problem, or the Product Owner instruction that directed it.>

## What changed

| Aspect | Before | After |
|---|---|---|
| <invariant / clause> | <before> | <after> |

## What remains in force

<Explicitly list the parts of the superseded record that still govern. On a
`PARTIAL` supersession this section is mandatory and is what stops an unrelated
clause being quietly voided. On a `FULL` supersession, write "Nothing" — and mean
it, having checked.>

## Migration / transition

- **CODE / TESTS:** <what must change, and by when>
- **IN-FLIGHT WORK:** <orders or missions authorized under the prior wording, and
  which wording governs them — normally the version cited at authorization time>
- **CITATIONS:** <records citing the old version, and whether they need restating>

## Historical status

<What the superseded record now is: preserved, readable, citable for lineage, and
non-governing within the superseded scope. Confirm it has been marked
`SUPERSEDED BY: GOV-S-nnn` in place — a status marker is a permitted edit; a
meaning edit is not.>

## Lineage

- **SUPERSEDES:** <id vX.Y>
- **SUPERSEDED BY:** <or None>
- **RELATED DECISIONS:** <GOV-D-* / GOV-CN-* / GOV-CR-* — or None>

## Governance delta

`ADDITIVE`
<!-- A supersession record is itself additive: it adds a record and re-points
     authority. It never removes the superseded document. -->
```

---

## Notes on filling this in

- **Quote both wordings.** A supersession record whose "before" is a summary
  destroys the very thing it exists to preserve.
- **Scope before extent.** Decide precisely what stops governing, then mark `FULL`
  or `PARTIAL` to match. Marking `FULL` because it is simpler is how unrelated
  invariants disappear.
- **Marking the old record is a status edit, not a meaning edit.** Adding
  `SUPERSEDED BY:` to the prior record is required and permitted. Changing anything
  else in it is not.
- **Non-destructive correction of a factual error is a different thing.** If a
  record states something that was simply wrong about the code, leave the sentence
  and add a dated adjacent correction. Reserve `GOV-S-` for changes in what governs.
