# Windows installer for agents-and-skills
# Usage:
#   .\install.ps1                 # Install for both Claude Code and Copilot (asks to confirm)
#   .\install.ps1 -Target claude  # Only Claude Code
#   .\install.ps1 -Target copilot # Only Copilot
#   .\install.ps1 -Force          # Skip the confirmation prompt (still backs up first)
#
# Behavior: BACKS UP the existing agents-and-skills artifacts to ~/.claude/backups/<timestamp>/,
# shows a notice, asks to confirm, then OVERWRITES them. Your ~/.claude/settings.json is MERGED
# (our keys added; your personal keys like model/theme/permissions are preserved) and the previous
# file is backed up.

[CmdletBinding()]
param(
    [ValidateSet("both", "claude", "copilot")]
    [string]$Target = "both",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$userClaudeSrc    = Join-Path $repoRoot "user\claude"
$userCopilotSrc   = Join-Path $repoRoot "user\copilot"
$teamKitsSrc      = Join-Path $repoRoot "team-kits"
$mergeScript      = Join-Path $repoRoot "user\merge_settings.py"

$claudeGlobal   = Join-Path $env:USERPROFILE ".claude"
$claudeSkills   = Join-Path $claudeGlobal "skills"
$claudeAgents   = Join-Path $claudeGlobal "agents"
$claudeTeamKits = Join-Path $claudeGlobal "team-kits"
$copilotSkills  = Join-Path $env:USERPROFILE ".copilot\skills"
$vscodePrompts  = Join-Path $env:APPDATA "Code\User\prompts"

$stamp     = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $claudeGlobal ("backups\" + $stamp)

function Backup-Item {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
    $name = Split-Path $Path -Leaf
    Copy-Item -Path $Path -Destination (Join-Path $backupDir $name) -Recurse -Force
}

# Skills are now per-kit (installed by the scaffold into a repo's ./.claude/skills). The installer no
# longer installs global skills; it removes the old global ones we used to ship.
$oldSkills = @("brief-mode","debug","explain","git-safety","interview","new-skill","plan-to-issues",
    "plan-to-prd","pm-playbook","pre-commit","refactor","review-plan","setup-repo","tdd","triage")
function Remove-OldSkills {
    param([string]$Destination)
    if (-not (Test-Path $Destination)) { return }
    foreach ($s in $oldSkills) {
        $d = Join-Path $Destination $s
        if (Test-Path $d) { Remove-Item $d -Recurse -Force; Write-Host "  [ok]   removed old skill: $s" -ForegroundColor Yellow }
    }
}

function Install-File {
    param([string]$Src, [string]$Dest, [string]$Label)
    if (-not (Test-Path $Src)) { Write-Host "  [warn] not found: $Src" -ForegroundColor Yellow; return }
    $dir = Split-Path $Dest
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [System.IO.File]::WriteAllText($Dest, (Get-Content $Src -Raw -Encoding UTF8), [System.Text.UTF8Encoding]::new($false))
    Write-Host "  [ok]   $Label" -ForegroundColor Green
}

# --- Notice + confirmation -------------------------------------------------
Write-Host "agents-and-skills installer" -ForegroundColor Cyan
Write-Host "This OVERWRITES the agents-and-skills files in ~/.claude (CLAUDE.md, agents, skills," -ForegroundColor Yellow
Write-Host "team-kits, statusline) and MERGES ~/.claude/settings.json (your personal keys are kept)." -ForegroundColor Yellow
Write-Host "A backup of the current files is saved to: $backupDir" -ForegroundColor Yellow
if (-not $Force) {
    $answer = Read-Host "Continue? (y/N)"
    if ($answer -notmatch '^(y|yes|j|ja)$') { Write-Host "Aborted." -ForegroundColor Red; exit 1 }
}

# --- Backup existing artifacts --------------------------------------------
Write-Host "`n-> Backing up to $backupDir"
Backup-Item (Join-Path $claudeGlobal "CLAUDE.md")
Backup-Item (Join-Path $claudeGlobal "settings.json")
Backup-Item (Join-Path $claudeGlobal "statusline.py")
Backup-Item $claudeAgents
Backup-Item $claudeSkills
Backup-Item $claudeTeamKits
if (Test-Path $vscodePrompts) {
    Get-ChildItem $vscodePrompts -Force | Where-Object { $_.Name -like '*.agent.md' -or $_.Name -eq 'COPILOT.instructions.md' } | ForEach-Object { Backup-Item $_.FullName }
}
Write-Host "  [ok]   backup complete" -ForegroundColor Green

# --- Team kits (shared staging) -------------------------------------------
Write-Host "`n-> Team kits (shared staging)"
if (Test-Path $teamKitsSrc) {
    if (Test-Path $claudeTeamKits) { Remove-Item $claudeTeamKits -Recurse -Force }
    Copy-Item -Path $teamKitsSrc -Destination $claudeTeamKits -Recurse -Force
    Write-Host "  [ok]   team-kits -> ~/.claude/team-kits" -ForegroundColor Green
}

if ($Target -eq "both" -or $Target -eq "claude") {
    Write-Host "`n-> Claude Code"
    Remove-OldSkills -Destination $claudeSkills
    # group-leader was removed (the plan-first entry gate replaces it) — clean up any stale install.
    $glOld = Join-Path $claudeAgents "group-leader.md"
    if (Test-Path $glOld) { Remove-Item $glOld -Force; Write-Host "  [ok]   removed old group-leader agent" -ForegroundColor Yellow }
    Install-File -Src (Join-Path $userClaudeSrc "CLAUDE.md") -Dest (Join-Path $claudeGlobal "CLAUDE.md") -Label "CLAUDE.md -> ~/.claude/CLAUDE.md"
    Install-File -Src (Join-Path $userClaudeSrc "statusline.py") -Dest (Join-Path $claudeGlobal "statusline.py") -Label "statusline.py -> ~/.claude/statusline.py"
    $claudeAgentsSrc = Join-Path $userClaudeSrc "agents"
    if (Test-Path $claudeAgentsSrc) {
        Get-ChildItem -Path $claudeAgentsSrc -Filter "*.md" | ForEach-Object {
            Install-File -Src $_.FullName -Dest (Join-Path $claudeAgents $_.Name) -Label "agent: $($_.Name)"
        }
    }
    # Merge global settings (preserves your personal keys; python required).
    $py = (Get-Command python -ErrorAction SilentlyContinue)
    $oursSettings = Join-Path $userClaudeSrc "settings.json"
    if ($py -and (Test-Path $mergeScript) -and (Test-Path $oursSettings)) {
        & $py.Source $mergeScript $oursSettings (Join-Path $claudeGlobal "settings.json")
    } else {
        Write-Host "  [warn] python not found or merge script missing - skipped settings.json merge." -ForegroundColor Yellow
        Write-Host "         Add the keys from user/claude/settings.json to ~/.claude/settings.json manually." -ForegroundColor Yellow
    }
}

if ($Target -eq "both" -or $Target -eq "copilot") {
    Write-Host "`n-> GitHub Copilot"
    Remove-OldSkills -Destination $copilotSkills
    $glCop = Join-Path $vscodePrompts "group-leader.agent.md"
    if (Test-Path $glCop) { Remove-Item $glCop -Force; Write-Host "  [ok]   removed old group-leader prompt" -ForegroundColor Yellow }
    Get-ChildItem -Path $userCopilotSrc -Filter "*.instructions.md" | ForEach-Object {
        Install-File -Src $_.FullName -Dest (Join-Path $vscodePrompts $_.Name) -Label "instructions: $($_.Name)"
    }
    $copilotAgentsSrc = Join-Path $userCopilotSrc "agents"
    if (Test-Path $copilotAgentsSrc) {
        Get-ChildItem -Path $copilotAgentsSrc -Filter "*.agent.md" | ForEach-Object {
            Install-File -Src $_.FullName -Dest (Join-Path $vscodePrompts $_.Name) -Label "agent: $($_.Name)"
        }
    }
}

Write-Host "`nDone. Backup at $backupDir. Restart VS Code to pick up new skills/agents." -ForegroundColor Cyan
