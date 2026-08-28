# Holodeck Archive — Custody and Backup

**Status:** proposal. Nothing here has been executed against a permanent
location; the script has been run and verified against a temporary target only.
**Date:** 2026-08-28.
**Companion:** `governance/proposals/fish-tank-design-archaeology.md` §0.1.

---

## 1. The exposure, measured

```
C:\Archiosk\holodeck\archive\
```

| Property | Measured value |
|---|---|
| Files | **232** |
| Size | **19,337,785 bytes** |
| Date range | 2026-05-03 → 2026-05-10 |
| Composition | 129 `.txt`, 100 `.html`, 2 `.bat`, 1 `.ps1` |
| Tracked by git | **No** |
| Copies known to exist | **One** |

The holodeck repository's `.gitignore` line 1 is `archive/`, confirmed with
`git check-ignore -v`. That repository tracks **5 files**. The exclusion was
deliberate — holodeck commit `4360f99 v2.21 metabolize archive copies out of
active Git tracking`.

So the archive is versioned only by filename, on one volume, with no second
copy. `LAST_ROLLBACK_POINT.txt` — the file that records which snapshot is
current — is a single line of text inside the same directory it describes.

**What is lost if that volume fails:** the only record of the design lineage
that `291d2cf` studied and that the Page-Field work is built on, including the
two surviving motion engines and the three mechanisms recovered in the
archaeology §3, which exist in no commit message, note or governance record
anywhere.

### 1.1 Handling classification

A pattern scan for credential literals (`api[_-]?key`, `password`, `bearer`,
`authorization:`, `secret`) returned matches that are, on inspection, **password
input fields** (`<input id="sandboxPassword" type="password">`) and a feature
named "Secret Level B — Extraction Locked". No credential literal was found.

**A pattern scan is not proof of absence.** Independently, the archive contains
two real contact addresses — `info@archiosk.com` and `info@dadras.ca`.

**Therefore: every copy is private.** Private git remotes or private storage
only. Never a public repository, never a shared bucket, never the
`archiosk.com/beehive-preview/` upload path.

---

## 2. Why not just `cp -r`

A plain copy cannot answer the only question that matters when you need it:
*is this complete and unaltered?* Silent truncation, a partial copy interrupted
halfway, or bit rot on the destination all produce a directory that looks
right. The archive is 232 near-identical HTML files; nobody is going to notice
by eye that one is 4KB short.

So the proposed snapshot **verifies itself**: it hashes the source, compresses,
re-expands to a temporary directory, re-hashes, and compares file-for-file. A
snapshot that fails is renamed `.UNVERIFIED` and is not counted as a backup.

Compression is worth having here: **19,337,785 → 3,578,945 bytes, 5.4×**,
measured on a real run. These are near-duplicate text files.

---

## 3. Three tiers

Tier 1 is the one with a deadline. Tiers 2 and 3 need a Product Owner decision
about storage, which is why this is a proposal and not a completed action.

### Tier 1 — verified local snapshot (today, one command)

```powershell
./tools/backup_holodeck_archive.ps1 -DestinationRoot E:\archiosk-backups -KeepLast 6
```

Protects against accidental deletion, a bad edit, and a mistaken cleanup.
**Does not protect against drive failure** if the destination shares a volume
with the source — the script warns explicitly when it does.

### Tier 2 — a dedicated private git repository (durable, versioned)

The archive is 232 near-identical text files. That is close to the ideal case
for git's delta compression, and it gives content-addressed integrity for free:
every file's hash is the thing git stores, so silent alteration is not
representable.

This does **not** mean reverting `4360f99`. That commit removed the archive from
the *working* repository to keep it light, and that judgement stands. The
proposal is a separate repository whose entire purpose is preservation:

```
archiosk-holodeck-archive/     # private remote, preservation only
  archive/                     # the 232 files, tracked
  MANIFEST.sha256              # generated, so integrity survives a clone
  README.md                    # what this is, why it is not in the app repo
```

One commit establishes the baseline. Later design work adds commits. The
working `holodeck` repository is unaffected.

### Tier 3 — offsite

At least one copy not in this building. Any private destination the Product
Owner already trusts is fine; the requirement is only that it is private
(§1.1) and not the same physical machine.

---

## 4. Integrity checking, afterwards

```powershell
./tools/backup_holodeck_archive.ps1 -VerifyOnly
```

Writes nothing. Re-hashes the live archive and compares it to the most recent
manifest, and distinguishes the two cases that matter:

- **Additions/removals only** → likely genuine new design work. Exit 1, advises
  a fresh snapshot.
- **Any ALTERED file** → an existing artifact's content changed. Exit 1, advises
  investigation *before* re-snapshotting, so a corruption is not immediately
  laundered into the backup as though it were the new truth.

That distinction is the reason a manifest exists at all rather than just a zip.

---

## 5. The script

`tools/backup_holodeck_archive.ps1`, committed with this proposal.

It is read-only with respect to the source: it hashes and compresses, and never
writes, moves or deletes anything under `-SourcePath`.

**Verified by running it.** Against a temporary destination, on the real
archive:

```
==> Source: C:\Archiosk\holodeck\archive
    OK   232 files, 19,337,785 bytes
    WARN Destination is on the SAME volume (C:) as the source.
    WARN This protects against accidental deletion, NOT against drive failure.
==> Compressing to holodeck-archive-20260828-170122.zip
    OK   3,578,945 bytes (5.4x smaller)
==> Verifying: re-expanding and re-hashing every file
    OK   232 files match source tree hash-for-hash
    OK   VERIFIED SNAPSHOT
```

and the `-VerifyOnly` path against that snapshot:

```
    OK   Newest manifest: holodeck-archive-20260828-170122.manifest.json
    OK   Live archive is identical to the last verified snapshot.
```

The test snapshot was written to the session scratchpad and is **not** a
backup — it is proof the tool works. Tier 1 still needs to be run against a real
destination.

---

## 6. What this asks for

1. **A destination volume for Tier 1.** One command, today. This is the item
   with actual urgency.
2. **A decision on Tier 2** — whether preservation gets its own private
   repository. Recommended; the archive is exactly the shape git is good at.
3. **A private offsite target for Tier 3.**

## 7. What this does not propose

- Reverting `4360f99` or re-tracking the archive inside the working holodeck
  repository.
- Copying the archive into this repository. It is another project's material,
  19MB of it, and `governance/proposals/fish-tank-design-archaeology.md` already
  carries everything this repository needs to know.
- Any public hosting, for the reasons in §1.1.
- Deleting anything. The script prunes only when `-KeepLast` is passed
  explicitly, never prunes the snapshot just written, and never prunes one that
  failed verification.
