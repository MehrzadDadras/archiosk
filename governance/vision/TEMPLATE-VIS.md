# TEMPLATE — Product Vision Record (`VIS-`)

**Purpose.** Preserve a durable statement of where ARCHIOSK is going and why, so
the intent behind the architecture survives the conversation it came from.

**Carries no implementation authority.** See [`README.md`](README.md). A `VIS-`
record explains a destination; it never authorizes travelling there.

**Keep it light.** A vision record that takes an hour to write will not be written.
Omit fields that do not apply rather than padding them.

---

```markdown
# VIS-nnn — <Title>

- **ID:** VIS-nnn
- **TITLE:** <short and quotable>
- **VERSION:** v1.0
- **STATUS:** DRAFT | CURRENT | SUPERSEDED | HISTORICAL

## Origin / lineage

<Where this came from — the record, prompt, or conversation it was first stated in.
Cite it. **Do not invent provenance:** "first known use" with an honest UNKNOWN
beats a plausible attribution.>

## Vision statement

> <One or two sentences. The destination, not the route.>

## Product intent

<What ARCHIOSK is trying to be, in this respect. Plain language — this is the field
a new contributor reads first.>

## Why it matters

<What problem this intent exists to solve, or what failure it avoids. If the honest
answer is "it makes the product nicer", that is worth knowing too.>

## What it enables

<What becomes possible, or easier to decide, once this intent is held. Concrete
where possible.>

## What it does not authorize

<**Mandatory.** The specific work a reader might think this vision green-lights,
and does not. This field is what keeps a vision record from being quoted in a pull
request as justification.>

## Related analogies

<ANA-* records that explain how to reason about this — or None.>

## Related governance

<GOV-* records, constitutional invariants, or current records that actually govern
in this area. This is where a reader goes for rules — or None.>

## Related CIC contracts

<CIC-* ids and versions carrying the operational obligations — or None.>

## Related product surfaces

<Pages, panels, routes, Template-Worthy IDs where this intent is visible — or None.>

## Evolution / lineage notes

<How this intent has changed, and what it grew out of. If a metaphor here later
became a formal architectural term, name the term and link its governing
definition — do not restate the definition.>
```

---

## Notes on filling this in

- **"What it does not authorize" is the load-bearing field.** Everything above it is
  explanation; that field is the boundary.
- **Vision records age differently from governance.** A superseded vision is still
  worth reading — it explains decisions still visible in the code. Mark it
  `SUPERSEDED` or `HISTORICAL`; never delete it.
- **One vision per record.** A record covering three intents will be cited for
  whichever one suits the citer.
