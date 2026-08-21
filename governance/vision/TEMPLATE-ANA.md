# TEMPLATE — Analogy / Mental Model Record (`ANA-`)

**Purpose.** Preserve a comparison that helps someone reason about part of
ARCHIOSK — and, just as importantly, record where the comparison stops working.

**Carries no implementation authority.** See [`README.md`](README.md). An analogy
never creates an invariant. If a rule is real, it belongs in a `GOV-*` record or a
contract, stated plainly and without the metaphor.

**`DOES NOT MEAN` is mandatory and may never be empty.** An analogy transfers
structure — including the structure that does not apply. Without stated limits it
quietly becomes a rule nobody voted for, and the first person to over-extend it will
be doing so in good faith.

---

```markdown
# ANA-nnn — <Title>

- **ID:** ANA-nnn
- **TITLE:** <the analogy, in a few words>
- **STATUS:** DRAFT | CURRENT | SUPERSEDED | HISTORICAL | MATURED INTO FORMAL TERM

## Analogy

> <The comparison, stated plainly. One or two sentences.>

## What it helps explain

<The thing that is genuinely easier to understand with this comparison than
without it. If nothing is easier, the analogy is decoration and should not be
filed.>

## ARCHIOSK mapping

| Analogy element | ARCHIOSK element |
|---|---|
| <element> | <what it maps to> |
| <element> | <what it maps to> |

<Map only what actually maps. An incomplete mapping is honest; a forced one is how
the analogy starts generating false expectations.>

## Where it is useful

<Which audience and which situation — explaining to a new contributor, orienting an
agent, naming a boundary in conversation. Also: where it should *not* be reached
for.>

## DOES NOT MEAN

**Mandatory. Never empty.**

<The specific wrong conclusions this analogy invites. Write the ones a reasonable
person would actually draw, not strawmen — the plausible over-extensions are the
dangerous ones. Each entry should name a real inference and deny it.>

- <plausible wrong conclusion> — <why it does not follow>
- <plausible wrong conclusion> — <why it does not follow>

## Related vision

<VIS-* records — or None.>

## Related governance

<GOV-* records, constitutional invariants, or current records that govern in this
area. **If this analogy has a formal governing definition, link it here and do not
restate it** — this record explains the mental model; that record defines the
term — or None.>

## Related contracts

<CIC-* ids and versions — or None.>

## Lineage / first known use

<Where this analogy first appears in the repository, cited. `UNKNOWN` if it cannot
be established from evidence. **Do not manufacture provenance** — an analogy the
Product Owner used in conversation but which appears nowhere in the corpus should
say exactly that.>

<If this analogy has matured into a defined architectural mechanism, say so, name
the term, and set STATUS to `MATURED INTO FORMAL TERM`. The record stays — it is
still the best way to explain the term to someone meeting it for the first time.>
```

---

## Notes on filling this in

- **Write `DOES NOT MEAN` before the mapping.** If you cannot name where the
  analogy breaks, you do not yet understand it well enough to file it.
- **A matured analogy is not a dead analogy.** Airlock and Vestibule are formal
  architectural terms now; the metaphor is still how you explain them in a sentence.
  Mark the maturation, link the definition, keep the record.
- **Do not file every colourful phrase.** File the ones that recur, that shape
  decisions, and that someone would otherwise have to reconstruct from conversation.
