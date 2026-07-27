---
name: verify-template-refactor
description: Prove a template/macro/CSS-class refactor is behavior-preserving (not just visually similar) by diffing real rendered HTML before and after, across every representative page. Use before calling any templates/ or static/css/main.css restructuring "done" - extracting a macro, consolidating two templates into one family, renaming a CSS class used by markup generation, etc. Not for ordinary content/copy changes, which don't need this.
allowed-tools:
  - Bash
---

# verify-template-refactor — prove a refactor didn't change output

## Why this exists

Two rounds of extracting page geometry into Jinja macros and template
families each needed the same proof: "this is a pure extraction, the
rendered HTML didn't change." Both times the verification script (walk
every captured page, normalize timestamps/UUIDs/whitespace, diff) was
written from scratch in the conversation. `tools/static_preview/diff_snapshot.py`
is that script, written once. Use it instead of rewriting it a third time.

## Procedure

1. **Before touching any template/CSS**, capture a baseline and copy it
   somewhere durable (the build output itself is git-ignored and gets
   overwritten by the next build, so it must be copied out):

   ```bash
   ./venv/Scripts/python.exe tools/static_preview/build_preview.py
   cp -r tools/static_preview/build/_raw <scratchpad>/before_raw
   ```

2. Make the refactor. Run the full test suite (`pytest -q`) - this
   catches Jinja syntax errors and logic breaks, but NOT geometry/markup
   drift, which is what step 3 is for.

3. **Rebuild and diff**:

   ```bash
   ./venv/Scripts/python.exe tools/static_preview/build_preview.py
   ./venv/Scripts/python.exe tools/static_preview/diff_snapshot.py <scratchpad>/before_raw
   ```

   Every page should print `IDENTICAL`. If a page legitimately changed on
   purpose (e.g. a CSS class was renamed as part of the refactor), pass
   it as an explicit old/new pair so it doesn't mask a *different*,
   unintended diff on that same page:

   ```bash
   ./venv/Scripts/python.exe tools/static_preview/diff_snapshot.py <scratchpad>/before_raw \
     'class="old-name"' 'class="new-name"'
   ```

4. For any real `DIFFERS` result, read the printed before/after context
   around the first differing character - it's almost always enough to
   tell whether it's a real regression or another deliberate change that
   needs to be passed as a normalization pair.

## Known limitation

The old/new pairs in step 3 are a plain string `.replace()` across the
whole page - if the *same* old substring needs to become two *different*
new values depending on where it appears (e.g. three elements that all
started as `class="workspace-pane">` and each got a different modifier
class), one pair can't express that and will misreport a real diff.
When that happens, don't force it through a pair - `grep -o` the actual
built HTML for the specific attribute/class directly and eyeball it,
then re-run the diff with the class value itself normalized away
(`class="workspace-pane[^"]*"` → a fixed placeholder) to confirm nothing
*else* changed.

## Don't

- Don't treat a passing test suite alone as proof the refactor is safe.
  This codebase's tests check status codes and data content, not markup
  geometry - a macro that silently drops an attribute or reorders two
  elements can pass every test and still be a real regression this
  script would catch.
- Don't skip capturing the "before" baseline and try to reconstruct it
  from git afterward - `git stash`/`git show` works but is slower and
  more error-prone than just copying the directory before you start.
