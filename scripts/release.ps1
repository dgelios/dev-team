#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Release a new version of the dev-team plugin.

.DESCRIPTION
    Bumps the version in .claude-plugin/plugin.json, rotates CHANGELOG.md
    ([Unreleased] -> [X.Y.Z] - YYYY-MM-DD), commits, tags, and pushes to origin.
    A GitHub Release with extracted CHANGELOG notes is created by the
    .github/workflows/release.yml workflow when the tag push is detected.

.PARAMETER Bump
    One of 'patch', 'minor', 'major'. Mutually exclusive with -Version.

.PARAMETER Version
    Explicit SemVer version like '1.2.3'. Mutually exclusive with -Bump.

.PARAMETER DryRun
    Print what would happen without writing files, committing, tagging, or pushing.

.EXAMPLE
    ./scripts/release.ps1 -Bump patch
    ./scripts/release.ps1 -Bump minor
    ./scripts/release.ps1 -Version 2.0.0
    ./scripts/release.ps1 -Bump patch -DryRun
#>

[CmdletBinding(DefaultParameterSetName = 'Bump')]
param(
    [Parameter(ParameterSetName = 'Bump', Mandatory)]
    [ValidateSet('patch', 'minor', 'major')]
    [string]$Bump,

    [Parameter(ParameterSetName = 'Version', Mandatory)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# Resolve repo root (script lives in scripts/)
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $RepoRoot

$PluginJsonPath = Join-Path $RepoRoot '.claude-plugin/plugin.json'
$ChangelogPath  = Join-Path $RepoRoot 'CHANGELOG.md'

function Assert-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required file not found: $Path"
    }
}

Assert-File $PluginJsonPath
Assert-File $ChangelogPath

# --- Safety checks ---------------------------------------------------------

$currentBranch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($currentBranch -ne 'main') {
    throw "Must be on 'main' branch to release. Current: $currentBranch"
}

$dirty = (git status --porcelain) | Where-Object { $_ }
if ($dirty) {
    throw "Working tree is not clean. Commit or stash changes first:`n$($dirty -join [Environment]::NewLine)"
}

git fetch origin main --quiet
$localSha  = (git rev-parse HEAD).Trim()
$remoteSha = (git rev-parse origin/main).Trim()
if ($localSha -ne $remoteSha) {
    throw "Local main is not in sync with origin/main. Pull/push first."
}

# --- Compute new version ---------------------------------------------------

$pluginJson = Get-Content -LiteralPath $PluginJsonPath -Raw | ConvertFrom-Json
$currentVersion = $pluginJson.version
if (-not $currentVersion) {
    throw "No 'version' field found in $PluginJsonPath"
}

if ($PSCmdlet.ParameterSetName -eq 'Version') {
    $newVersion = $Version
}
else {
    $parts = $currentVersion -split '\.'
    if ($parts.Count -ne 3) {
        throw "Current version '$currentVersion' is not SemVer X.Y.Z"
    }
    $major = [int]$parts[0]; $minor = [int]$parts[1]; $patch = [int]$parts[2]
    switch ($Bump) {
        'major' { $major++; $minor = 0; $patch = 0 }
        'minor' { $minor++; $patch = 0 }
        'patch' { $patch++ }
    }
    $newVersion = "$major.$minor.$patch"
}

if ($newVersion -eq $currentVersion) {
    throw "New version equals current version ($currentVersion). Nothing to release."
}

$tag = "v$newVersion"
$existingTag = git tag --list $tag
if ($existingTag) {
    throw "Tag $tag already exists."
}

$today = (Get-Date).ToString('yyyy-MM-dd')

Write-Host "Release plan:" -ForegroundColor Cyan
Write-Host "  Current version : $currentVersion"
Write-Host "  New version     : $newVersion"
Write-Host "  Tag             : $tag"
Write-Host "  Date            : $today"
Write-Host "  Dry run         : $DryRun"
Write-Host ""

# --- Update plugin.json ----------------------------------------------------

$pluginJson.version = $newVersion
$newPluginJson = ($pluginJson | ConvertTo-Json -Depth 10) + "`n"

if (-not $DryRun) {
    Set-Content -LiteralPath $PluginJsonPath -Value $newPluginJson -NoNewline -Encoding UTF8
}
Write-Host "[OK] plugin.json version -> $newVersion"

# --- Rotate CHANGELOG.md ---------------------------------------------------

$changelog = Get-Content -LiteralPath $ChangelogPath -Raw

# Require an [Unreleased] section with at least one content line, else block.
$unreleasedPattern = '(?ms)^## \[Unreleased\]\s*\r?\n(?<body>.*?)(?=^## \[|\Z)'
$match = [regex]::Match($changelog, $unreleasedPattern)
if (-not $match.Success) {
    throw "CHANGELOG.md has no [Unreleased] section. Add it before running release."
}
$unreleasedBody = $match.Groups['body'].Value

# Trim leading/trailing blank lines; keep internal structure.
$trimmedBody = $unreleasedBody -replace '^(\s*\r?\n)+', '' -replace '(\s*\r?\n)+$', ''

if (-not $trimmedBody.Trim()) {
    throw "CHANGELOG.md [Unreleased] section is empty. Add entries before running release."
}

# Build replacement: new empty [Unreleased] + new [X.Y.Z] with rotated body
$replacement = @"
## [Unreleased]

## [$newVersion] - $today

$trimmedBody

"@

$newChangelog = [regex]::Replace(
    $changelog,
    $unreleasedPattern,
    { param($m) $replacement },
    'Singleline, Multiline'
)

# Update footer compare links if present
$newChangelog = $newChangelog -replace '\[Unreleased\]: https://github.com/dgelios/dev-team/compare/v[\d.]+\.\.\.HEAD', "[Unreleased]: https://github.com/dgelios/dev-team/compare/$tag...HEAD"

# Insert new version compare link if it doesn't exist
if ($newChangelog -notmatch "\[$newVersion\]:") {
    $prevTag = "v$currentVersion"
    $newLink = "[$newVersion]: https://github.com/dgelios/dev-team/compare/$prevTag...$tag"
    # Append before the v-prev line
    $newChangelog = $newChangelog -replace "(\[$currentVersion\]: https://github\.com/dgelios/dev-team/releases/tag/v$currentVersion)", "$newLink`n`$1"
}

if (-not $DryRun) {
    Set-Content -LiteralPath $ChangelogPath -Value $newChangelog -NoNewline -Encoding UTF8
}
Write-Host "[OK] CHANGELOG.md rotated [Unreleased] -> [$newVersion] - $today"

# --- Commit, tag, push -----------------------------------------------------

if ($DryRun) {
    Write-Host ""
    Write-Host "DRY RUN. No commit, tag, or push performed." -ForegroundColor Yellow
    exit 0
}

git add $PluginJsonPath $ChangelogPath
git commit -m "chore(release): $newVersion"
if ($LASTEXITCODE -ne 0) { throw "git commit failed." }

git tag -a $tag -m "dev-team $tag"
if ($LASTEXITCODE -ne 0) { throw "git tag failed." }

git push origin main
if ($LASTEXITCODE -ne 0) { throw "git push main failed." }

git push origin $tag
if ($LASTEXITCODE -ne 0) { throw "git push tag failed." }

Write-Host ""
Write-Host "Released $tag." -ForegroundColor Green
Write-Host "GitHub Actions workflow will create the Release on github.com/dgelios/dev-team/releases shortly."
