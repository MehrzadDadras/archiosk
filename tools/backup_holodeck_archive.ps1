<#
.SYNOPSIS
    Create a verified, checksummed snapshot of the Holodeck design archive.

.DESCRIPTION
    C:\Archiosk\holodeck\archive\ holds ~232 irreplaceable design artifacts that
    are deliberately .gitignore'd out of their own repository (holodeck commit
    4360f99, "metabolize archive copies out of active Git tracking"). They
    therefore exist as a single uncommitted copy on one disk, versioned only by
    filename. See governance/proposals/holodeck-archive-custody.md.

    This script produces a snapshot that can PROVE it is complete and unaltered,
    which a plain file copy cannot:

      1. SHA-256 every source file into a manifest.
      2. Compress the tree into a single dated .zip.
      3. Re-expand the .zip to a temporary directory and re-hash every file.
      4. Compare hash-for-hash against the manifest. Any mismatch, any missing
         file, any extra file FAILS the run and the snapshot is marked bad.

    Step 4 is the point. An unverified backup is a belief, not a backup.

    Nothing in the source tree is written, moved or deleted. The script is
    read-only with respect to -SourcePath.

.PARAMETER SourcePath
    Directory to preserve. Defaults to the Holodeck archive.

.PARAMETER DestinationRoot
    Where snapshots are written. Defaults to the WD My Cloud EX4100 share,
    which is a different MACHINE rather than merely a different volume - the
    strongest destination reachable without leaving the site.

    A local destination should at minimum be on a different physical volume.
    The same-volume check below is a drive-letter comparison and therefore
    says nothing at all about a UNC path, so that case is reported separately
    rather than silently passing a test it was never subject to.

.PARAMETER KeepLast
    Retain only the N most recent verified snapshots. 0 (default) keeps all.
    Pruning never removes the snapshot just written, and never removes a
    snapshot that failed verification (those are kept for inspection).

.PARAMETER VerifyOnly
    Re-verify the most recent existing snapshot against its own manifest and
    against the live source tree. Writes nothing. Use this as a periodic
    integrity check, and to detect drift between the archive and its backup.

.EXAMPLE
    ./tools/backup_holodeck_archive.ps1
    ./tools/backup_holodeck_archive.ps1 -DestinationRoot D:\archiosk-backups -KeepLast 6
    ./tools/backup_holodeck_archive.ps1 -VerifyOnly

.NOTES
    The archive contains real contact email addresses (info@archiosk.com,
    info@dadras.ca). A pattern scan found no credential literals, but a pattern
    scan is not proof of absence. Treat every snapshot as PRIVATE: private
    remotes only, never a public repository or a shared bucket.
#>

[CmdletBinding()]
param(
    [string] $SourcePath      = 'C:\Archiosk\holodeck\archive',
    [string] $DestinationRoot = '\\WDMYCLOUDEX4100\Public\archiosk-backups',
    [int]    $KeepLast        = 0,
    [switch] $VerifyOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-Step { param($m) Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host "    OK   $m" -ForegroundColor Green }
function Write-Warn { param($m) Write-Host "    WARN $m" -ForegroundColor Yellow }
function Write-Bad  { param($m) Write-Host "    FAIL $m" -ForegroundColor Red }

# --- Hash every file under a root, keyed by path relative to that root. -------
# Relative keys are what make a manifest portable: the same tree verifies
# whether it sits in the archive, in a zip, or in a temp expansion directory.
function Get-TreeHashes {
    param([Parameter(Mandatory)][string] $Root)

    $root = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
    $map  = [ordered]@{}

    Get-ChildItem -LiteralPath $root -Recurse -File -Force |
        Sort-Object FullName |
        ForEach-Object {
            $rel = $_.FullName.Substring($root.Length + 1)
            $map[$rel] = [pscustomobject]@{
                Sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
                Bytes  = $_.Length
            }
        }

    return $map
}

# --- Compare two hash maps. Returns a report object; never throws on diff. ----
function Compare-TreeHashes {
    param(
        [Parameter(Mandatory)] $Expected,
        [Parameter(Mandatory)] $Actual,
        [string] $ExpectedLabel = 'manifest',
        [string] $ActualLabel   = 'snapshot'
    )

    $missing  = @($Expected.Keys | Where-Object { -not $Actual.Contains($_) })
    $extra    = @($Actual.Keys   | Where-Object { -not $Expected.Contains($_) })
    $altered  = @(
        $Expected.Keys |
            Where-Object { $Actual.Contains($_) } |
            Where-Object { $Expected[$_].Sha256 -ne $Actual[$_].Sha256 }
    )

    [pscustomobject]@{
        Missing       = $missing
        Extra         = $extra
        Altered       = $altered
        Ok            = ($missing.Count -eq 0 -and $extra.Count -eq 0 -and $altered.Count -eq 0)
        ExpectedLabel = $ExpectedLabel
        ActualLabel   = $ActualLabel
        ExpectedCount = $Expected.Count
        ActualCount   = $Actual.Count
    }
}

function Show-Comparison {
    param([Parameter(Mandatory)] $Report)

    if ($Report.Ok) {
        Write-Ok ("{0} files match {1} hash-for-hash" -f $Report.ExpectedCount, $Report.ExpectedLabel)
        return $true
    }

    Write-Bad ("{0} ({1} files) does not match {2} ({3} files)" -f `
        $Report.ActualLabel, $Report.ActualCount, $Report.ExpectedLabel, $Report.ExpectedCount)

    foreach ($f in $Report.Missing) { Write-Bad "  missing: $f" }
    foreach ($f in $Report.Extra)   { Write-Bad "  extra:   $f" }
    foreach ($f in $Report.Altered) { Write-Bad "  ALTERED: $f" }
    return $false
}

# =============================================================================

if (-not (Test-Path -LiteralPath $SourcePath)) {
    throw "Source path not found: $SourcePath"
}

$sourceFull = (Resolve-Path -LiteralPath $SourcePath).Path

Write-Step "Source: $sourceFull"
$sourceHashes = Get-TreeHashes -Root $sourceFull
$sourceBytes  = ($sourceHashes.Values | Measure-Object -Property Bytes -Sum).Sum
Write-Ok ("{0} files, {1:N0} bytes" -f $sourceHashes.Count, $sourceBytes)

# --- VerifyOnly: check the newest snapshot, write nothing. -------------------
if ($VerifyOnly) {
    Write-Step 'Verify-only: checking the most recent snapshot'

    if (-not (Test-Path -LiteralPath $DestinationRoot)) {
        Write-Bad "No snapshot directory at $DestinationRoot - nothing has ever been backed up."
        exit 2
    }

    $latest = Get-ChildItem -LiteralPath $DestinationRoot -Filter '*.manifest.json' -File |
              Sort-Object Name -Descending | Select-Object -First 1
    if (-not $latest) {
        Write-Bad "No manifest found in $DestinationRoot"
        exit 2
    }

    Write-Ok "Newest manifest: $($latest.Name)"
    $stored = Get-Content -LiteralPath $latest.FullName -Raw | ConvertFrom-Json

    $storedMap = [ordered]@{}
    foreach ($e in $stored.Files) {
        $storedMap[$e.Path] = [pscustomobject]@{ Sha256 = $e.Sha256; Bytes = $e.Bytes }
    }

    $report = Compare-TreeHashes -Expected $storedMap -Actual $sourceHashes `
                                 -ExpectedLabel 'stored manifest' -ActualLabel 'live source tree'

    if ($report.Ok) {
        Write-Ok 'Live archive is identical to the last verified snapshot.'
        exit 0
    }

    # A difference here is NOT automatically corruption. New design work adds
    # files. Say which it looks like rather than guessing.
    Write-Warn 'Live archive differs from the last snapshot.'
    if ($report.Altered.Count -gt 0) {
        Write-Bad 'ALTERED files are present - existing artifacts changed content. Investigate before re-snapshotting.'
        exit 1
    }
    Write-Warn 'Differences are additions/removals only. If that is expected work, take a fresh snapshot.'
    exit 1
}

# --- Snapshot ----------------------------------------------------------------
$stamp    = Get-Date -Format 'yyyyMMdd-HHmmss'
$baseName = "holodeck-archive-$stamp"

if (-not (Test-Path -LiteralPath $DestinationRoot)) {
    New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
    Write-Ok "Created $DestinationRoot"
}
# ProviderPath, not Path. Resolve-Path returns a PROVIDER-QUALIFIED string for
# a UNC target - "Microsoft.PowerShell.Core\FileSystem::\host\share" - so the
# UNC test below saw 'M', reported nothing, and fell through to a drive-letter
# comparison it was never subject to. It passed for the wrong reason, which is
# the failure mode this script exists to refuse.
$destFull = (Resolve-Path -LiteralPath $DestinationRoot).ProviderPath

# A UNC destination is a different MACHINE, which is strictly stronger than a
# different volume. The drive-letter comparison would be meaningless for it -
# and worse, would silently pass - so the two cases are separated.
if ($destFull.StartsWith('\\')) {
    Write-Ok "Destination is a network share: $destFull"
    Write-Ok 'Different machine: survives failure of this computer. NOT offsite.'
} elseif ($sourceFull.Substring(0,1) -eq $destFull.Substring(0,1)) {
    Write-Warn "Destination is on the SAME volume ($($destFull.Substring(0,2))) as the source."
    Write-Warn 'This protects against accidental deletion, NOT against drive failure.'
    Write-Warn 'Pass -DestinationRoot on a different physical volume, and keep an offsite copy.'
}

$zipPath      = Join-Path $destFull "$baseName.zip"
$manifestPath = Join-Path $destFull "$baseName.manifest.json"

Write-Step "Compressing to $([IO.Path]::GetFileName($zipPath))"
Compress-Archive -Path (Join-Path $sourceFull '*') -DestinationPath $zipPath -CompressionLevel Optimal
$zipBytes = (Get-Item -LiteralPath $zipPath).Length
Write-Ok ("{0:N0} bytes ({1:N1}x smaller)" -f $zipBytes, ($sourceBytes / [double]$zipBytes))

Write-Step 'Verifying: re-expanding and re-hashing every file'
$temp = Join-Path ([IO.Path]::GetTempPath()) "holodeck-verify-$stamp"
$verified = $false
try {
    Expand-Archive -LiteralPath $zipPath -DestinationPath $temp -Force
    $roundTripped = Get-TreeHashes -Root $temp
    $report = Compare-TreeHashes -Expected $sourceHashes -Actual $roundTripped `
                                 -ExpectedLabel 'source tree' -ActualLabel 'expanded snapshot'
    $verified = Show-Comparison -Report $report
}
finally {
    if (Test-Path -LiteralPath $temp) {
        Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$manifest = [pscustomobject]@{
    Tool          = 'tools/backup_holodeck_archive.ps1'
    CreatedUtc    = (Get-Date).ToUniversalTime().ToString('o')
    SourcePath    = $sourceFull
    ZipFile       = [IO.Path]::GetFileName($zipPath)
    FileCount     = $sourceHashes.Count
    SourceBytes   = $sourceBytes
    ZipBytes      = $zipBytes
    Verified      = $verified
    ZipSha256     = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
    Files         = @(
        $sourceHashes.Keys | ForEach-Object {
            [pscustomobject]@{ Path = $_; Sha256 = $sourceHashes[$_].Sha256; Bytes = $sourceHashes[$_].Bytes }
        }
    )
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Ok "Manifest: $([IO.Path]::GetFileName($manifestPath))"

if (-not $verified) {
    $bad = Join-Path $destFull "$baseName.UNVERIFIED"
    Rename-Item -LiteralPath $zipPath -NewName ([IO.Path]::GetFileName($bad))
    Write-Bad 'VERIFICATION FAILED. Snapshot renamed .UNVERIFIED and kept for inspection.'
    Write-Bad 'Do not treat this run as a backup.'
    exit 1
}

# --- Prune, but only ever verified snapshots, and never the newest. ----------
if ($KeepLast -gt 0) {
    Write-Step "Pruning to the $KeepLast most recent verified snapshots"
    $zips = @(Get-ChildItem -LiteralPath $destFull -Filter 'holodeck-archive-*.zip' -File |
              Sort-Object Name -Descending)
    if ($zips.Count -gt $KeepLast) {
        foreach ($old in $zips[$KeepLast..($zips.Count - 1)]) {
            $mate = [IO.Path]::ChangeExtension($old.FullName, $null) + 'manifest.json'
            Remove-Item -LiteralPath $old.FullName -Force
            if (Test-Path -LiteralPath $mate) { Remove-Item -LiteralPath $mate -Force }
            Write-Ok "Pruned $($old.Name)"
        }
    }
}

Write-Host ''
Write-Ok "VERIFIED SNAPSHOT: $zipPath"
Write-Host ("    {0} files, {1:N0} -> {2:N0} bytes, every file re-hashed after round-trip." -f `
    $sourceHashes.Count, $sourceBytes, $zipBytes)
exit 0
