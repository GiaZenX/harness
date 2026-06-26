# Scaffold a team kit into the current repository (Windows).
# Usage: scaffold_team.ps1 -Team dev-team
# Copies the kit's agents into ./.claude/agents/ and its constitution into ./CLAUDE.md,
# plus enforcement hooks into ./.claude/. project_memory/ is NOT created here -- the PM
# creates it from the global templates at startup.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Team
)

$ErrorActionPreference = "Stop"
$kit = Join-Path $env:USERPROFILE ".claude\team-kits\$Team"
if (-not (Test-Path $kit)) { throw "Team kit not found: $kit" }

$repo = (Get-Location).Path
Write-Host "Scaffolding team '$Team' into $repo" -ForegroundColor Cyan

$agentsSrc = Join-Path $kit "agents"
$agentsDst = Join-Path $repo ".claude\agents"
if (-not (Test-Path $agentsDst)) { New-Item -ItemType Directory -Force -Path $agentsDst | Out-Null }
Get-ChildItem -Path $agentsSrc -Filter "*.md" | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $agentsDst $_.Name) -Force
    Write-Host "  [ok] agent: $($_.Name)" -ForegroundColor Green
}

$conSrc = Join-Path $kit "constitution\CLAUDE.md"
if (Test-Path $conSrc) {
    Copy-Item $conSrc (Join-Path $repo "CLAUDE.md") -Force
    Write-Host "  [ok] CLAUDE.md (local constitution)" -ForegroundColor Green
}

# Enforcement layer: hooks + settings.json travel with the team.
$hooksSrc = Join-Path $kit "hooks"
if (Test-Path $hooksSrc) {
    $hooksDst = Join-Path $repo ".claude\hooks"
    if (-not (Test-Path $hooksDst)) { New-Item -ItemType Directory -Force -Path $hooksDst | Out-Null }
    Get-ChildItem -Path $hooksSrc -File | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $hooksDst $_.Name) -Force
        Write-Host "  [ok] hook: $($_.Name)" -ForegroundColor Green
    }
}
$settingsSrc = Join-Path $kit "settings\settings.json"
if (Test-Path $settingsSrc) {
    $settingsDst = Join-Path $repo ".claude\settings.json"
    if (Test-Path $settingsDst) {
        Write-Host "  [skip] .claude/settings.json exists - merge hooks manually" -ForegroundColor Yellow
    } else {
        Copy-Item $settingsSrc $settingsDst -Force
        Write-Host "  [ok] .claude/settings.json (enforcement hooks)" -ForegroundColor Green
    }
}

Write-Host "Team '$Team' installed locally. The main agent is now your Project Manager - just keep prompting." -ForegroundColor Cyan
