#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Release a new version of the dev-team plugin.

.DESCRIPTION
    Bumps the version in .claude-plugin/plugin.json, commits, tags, and pushes
    to origin. .github/workflows/release.yml then creates a GitHub Release with
    notes auto-generated from commit messages since the previous tag.

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

if (-not (Test-Path -LiteralPath $PluginJsonPath)) {
    throw "Required file not found: $PluginJsonPath"
}

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

Write-Host "Release plan:" -ForegroundColor Cyan
Write-Host "  Current version : $currentVersion"
Write-Host "  New version     : $newVersion"
Write-Host "  Tag             : $tag"
Write-Host "  Dry run         : $DryRun"
Write-Host ""

# --- Preview commit messages that will become release notes ----------------

$prevTag = "v$currentVersion"
$commitList = git log "$prevTag..HEAD" --pretty=format:"- %s" 2>$null
if ($commitList) {
    Write-Host "Commits that will be in the release notes:" -ForegroundColor Cyan
    $commitList | ForEach-Object { Write-Host "  $_" }
    Write-Host ""
}

# --- Update plugin.json ----------------------------------------------------

$pluginJson.version = $newVersion
$newPluginJson = ($pluginJson | ConvertTo-Json -Depth 10) + "`n"

if (-not $DryRun) {
    Set-Content -LiteralPath $PluginJsonPath -Value $newPluginJson -NoNewline -Encoding UTF8
}
Write-Host "[OK] plugin.json version -> $newVersion"

# --- Commit, tag, push -----------------------------------------------------

if ($DryRun) {
    Write-Host ""
    Write-Host "DRY RUN. No commit, tag, or push performed." -ForegroundColor Yellow
    exit 0
}

git add $PluginJsonPath
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
