# Windows installer for agents-and-skills
# Usage:
#   .\install.ps1                 # Install for Claude Code AND Codex (asks to confirm)
#   .\install.ps1 -Target claude  # Only Claude Code
#   .\install.ps1 -Target codex   # Only the Codex entry gate ($CODEX_HOME/AGENTS.md)
#   .\install.ps1 -Force          # Skip the confirmation prompt (still backs up first)
#
# Behavior: BACKS UP the existing agents-and-skills artifacts to ~/.claude/backups/<timestamp>/,
# shows a notice, asks to confirm, then OVERWRITES them. Your ~/.claude/settings.json is MERGED:
# missing defaults are added, existing personal values win, and permission allow/deny lists are
# unioned. The previous file is backed up. "both" is kept as the historical name for "everything".
# Copilot support was removed; the installer still cleans up previously installed Copilot files.

[CmdletBinding()]
param(
    [ValidateSet("both", "claude", "codex")]
    [string]$Target = "both",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$userClaudeSrc    = Join-Path $repoRoot "user\claude"
$userCodexSrc     = Join-Path $repoRoot "user\codex"
$teamKitsSrc      = Join-Path $repoRoot "team-kits"
$mergeScript      = Join-Path $repoRoot "user\merge_settings.py"

$claudeGlobal   = Join-Path $env:USERPROFILE ".claude"
$claudeSkills   = Join-Path $claudeGlobal "skills"
$claudeAgents   = Join-Path $claudeGlobal "agents"
$claudeTeamKits = Join-Path $claudeGlobal "team-kits"
# Legacy Copilot destinations — only referenced to REMOVE files older installs put there.
$copilotSkills  = Join-Path $env:USERPROFILE ".copilot\skills"
$vscodePrompts  = Join-Path $env:APPDATA "Code\User\prompts"
$codexGlobal = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
    Join-Path $env:USERPROFILE ".codex"
} else {
    $env:CODEX_HOME
}

function Test-ReparsePoint {
    param([string]$Path)
    # [IO.File]::GetAttributes reads the link ITSELF (no follow), so a DANGLING symlink/junction
    # is still detected — Test-Path follows the target and reported dead links as absent.
    try {
        return [bool]([IO.File]::GetAttributes($Path) -band [IO.FileAttributes]::ReparsePoint)
    } catch {
        $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
        if ($null -eq $item) { return $false }
        return [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
    }
}

function Assert-NoReparseComponents {
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    $relative = $full.Substring($root.Length)
    $current = $root
    foreach ($component in ($relative -split '[\\/]' | Where-Object { $_ })) {
        $current = Join-Path $current $component
        if (Test-ReparsePoint $current) {
            throw "Refusing symlink/junction/reparse path '$current'; installation was not started."
        }
    }
}

function Assert-NoReparseTree {
    param([string]$Path)
    Assert-NoReparseComponents $Path
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $pending = New-Object System.Collections.Generic.Stack[string]
    $rootItem = Get-Item -LiteralPath $Path -Force
    if ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refusing symlink/junction/reparse path '$Path'; installation was not started."
    }
    if ($rootItem.PSIsContainer) { $pending.Push($rootItem.FullName) }
    while ($pending.Count -gt 0) {
        foreach ($item in (Get-ChildItem -LiteralPath $pending.Pop() -Force)) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing symlink/junction/reparse path '$($item.FullName)'; installation was not started."
            }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
}

$stampBase = Get-Date -Format "yyyyMMdd-HHmmss"
$stamp = $stampBase
$backupDir = Join-Path $claudeGlobal ("backups\" + $stamp)
$stampSuffix = 1
while (Test-Path -LiteralPath $backupDir) {
    $stamp = "$stampBase-$stampSuffix"
    $backupDir = Join-Path $claudeGlobal ("backups\" + $stamp)
    $stampSuffix++
}

function Backup-Item {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Assert-NoReparseTree $Path
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
        if (Test-Path $d) {
            Assert-NoReparseTree $d
            Remove-Item $d -Recurse -Force
            Write-Host "  [ok]   removed old skill: $s" -ForegroundColor Yellow
        }
    }
}

function Install-File {
    param([string]$Src, [string]$Dest, [string]$Label)
    if (-not (Test-Path $Src)) { Write-Host "  [warn] not found: $Src" -ForegroundColor Yellow; return }
    Assert-NoReparseTree $Src
    Assert-NoReparseComponents $Dest
    $dir = Split-Path $Dest
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [System.IO.File]::WriteAllText($Dest, (Get-Content $Src -Raw -Encoding UTF8), [System.Text.UTF8Encoding]::new($false))
    Write-Host "  [ok]   $Label" -ForegroundColor Green
}

# --- Notice + confirmation -------------------------------------------------
Write-Host "agents-and-skills installer" -ForegroundColor Cyan
Write-Host "This refreshes the shared team-kit staging at ~/.claude/team-kits." -ForegroundColor Yellow
if ($Target -eq "both" -or $Target -eq "claude") {
    Write-Host "It OVERWRITES managed Claude files and MERGES settings.json (existing personal values win; permission lists are unioned)." -ForegroundColor Yellow
}

# Fail closed before backup or confirmation: managed destinations and sources must not traverse a
# symlink/junction/reparse point, otherwise Copy/WriteAllText could modify an external target.
Assert-NoReparseTree $teamKitsSrc
Assert-NoReparseComponents $backupDir
Assert-NoReparseComponents $claudeGlobal
foreach ($path in @($claudeAgents, $claudeSkills, $claudeTeamKits,
        (Join-Path $claudeGlobal "CLAUDE.md"), (Join-Path $claudeGlobal "settings.json"),
        (Join-Path $claudeGlobal "statusline.py"))) {
    Assert-NoReparseTree $path
}
if ($Target -eq "both" -or $Target -eq "codex") {
    Assert-NoReparseComponents $codexGlobal
    Assert-NoReparseTree (Join-Path $codexGlobal "AGENTS.md")
    Assert-NoReparseTree (Join-Path $codexGlobal "AGENTS.override.md")
    Assert-NoReparseTree (Join-Path $codexGlobal "config.toml")
    $codexCommand = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $codexCommand) {
        Write-Host "  [warn] Codex executable not found; entry-gate installation can proceed, but hooks, custom agents, and permission profiles cannot be verified on this host." -ForegroundColor Yellow
    } else {
        try {
            # No stderr redirect: under EAP=Stop, redirecting a native command's stderr wraps each
            # line in an ErrorRecord and would turn version NOISE into a fail-open catch below.
            $codexVersion = (& $codexCommand.Source --version | Select-Object -First 1)
            Write-Host "  [info] detected Codex host: $codexVersion" -ForegroundColor Cyan
            $versionMatch = [regex]::Match([string]$codexVersion, '(\d+)\.(\d+)\.(\d+)')
            if (-not $versionMatch.Success) {
                Write-Host "  [warn] Could not parse the Codex version; verify permission-profile and current hook support before using a structured kit." -ForegroundColor Yellow
            } else {
                $parsedVersion = [Version]::new(
                    [int]$versionMatch.Groups[1].Value,
                    [int]$versionMatch.Groups[2].Value,
                    [int]$versionMatch.Groups[3].Value)
                # Baseline 0.131.0: hooks GA (official changelog 2026-05-14) + the improved
                # per-hash hook trust flow the kits rely on. No older release carries both.
                if ($parsedVersion -lt [Version]"0.131.0") {
                    throw "Codex $parsedVersion is too old (hooks GA + trust flow need 0.131.0+). Upgrade Codex before installing this entry gate."
                }
            }
        } catch {
            if ($_.Exception.Message -match 'too old') { throw }
            Write-Host "  [warn] Codex was found but its version/capabilities could not be verified; use a current build and review /hooks after scaffolding." -ForegroundColor Yellow
        }
    }
    $codexUserConfig = Join-Path $codexGlobal "config.toml"
    if (Test-Path -LiteralPath $codexUserConfig) {
        $configText = Get-Content -LiteralPath $codexUserConfig -Raw
        if ($configText -match '(?m)^\s*sandbox_mode\s*=' -or $configText -match '(?m)^\s*\[sandbox_workspace_write\]\s*(?:#.*)?$') {
            Write-Host "  [warn] $codexUserConfig sets legacy sandbox_mode/sandbox_workspace_write configuration. Codex gives legacy sandbox settings precedence over generated permission profiles; remove/relocate it before relying on team-kit filesystem policy." -ForegroundColor Yellow
        }
    }
}
if ($Target -eq "both" -or $Target -eq "codex") {
    Write-Host "It OVERWRITES the Codex entry gate at $codexGlobal\AGENTS.md." -ForegroundColor Yellow
    $codexOverride = Join-Path $codexGlobal "AGENTS.override.md"
    if (Test-Path $codexOverride) {
        Write-Host "Codex override detected at $codexOverride; it will be backed up and preserved." -ForegroundColor Yellow
        Write-Host "It takes precedence over AGENTS.md, so the installed entry gate stays inactive while the override exists." -ForegroundColor Yellow
    }
}
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
# Legacy Copilot files older installs put into VS Code prompts — backed up before cleanup below.
$legacyCopilotNames = @("COPILOT.instructions.md", "group-leader.agent.md",
    "memory-engineer.agent.md", "project-memory.instructions.md")
if (Test-Path $vscodePrompts) {
    $legacyCopilot = Get-ChildItem $vscodePrompts -Force | Where-Object { $_.Name -in $legacyCopilotNames }
    foreach ($item in $legacyCopilot) { Assert-NoReparseTree $item.FullName; Backup-Item $item.FullName }
}
if ($Target -eq "both" -or $Target -eq "codex") {
    if (Test-Path (Join-Path $codexGlobal "AGENTS.md")) {
        # backed up as codex-AGENTS.md so it cannot collide with other backups
        if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
        Copy-Item (Join-Path $codexGlobal "AGENTS.md") (Join-Path $backupDir "codex-AGENTS.md") -Force
    }
    if (Test-Path (Join-Path $codexGlobal "AGENTS.override.md")) {
        # Preserve the override itself and store a copy under an unambiguous name. The installer never
        # replaces an override because it is user-owned and intentionally takes precedence over AGENTS.md.
        if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
        Copy-Item (Join-Path $codexGlobal "AGENTS.override.md") (Join-Path $backupDir "codex-AGENTS.override.md") -Force
    }
}
Write-Host "  [ok]   backup complete" -ForegroundColor Green

# --- Sanity: never stage a broken or unbumped kit ---------------------------
# Python 3.8+ with PyYAML is required UNCONDITIONALLY (staging copy, settings merge, and every
# scaffold/hook run need it) — checked here, before any mutation, without stderr redirection
# (under EAP=Stop a 2>$null on a native command turns its stderr into a terminating error).
$pyCheck = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCheck) { $pyCheck = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $pyCheck) {
    Write-Host "Python 3 is required (staging, settings merge, kit hooks)." -ForegroundColor Red
    exit 1
}
& $pyCheck.Source -c "import importlib.util, sys; sys.exit(0 if (sys.version_info >= (3, 8) and importlib.util.find_spec('yaml')) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python 3.8+ and PyYAML are required. Run: python -m pip install pyyaml" -ForegroundColor Red
    exit 1
}
$validateScript = Join-Path $repoRoot "tools\validate.py"
if (Test-Path $validateScript) {
    & $pyCheck.Source $validateScript
    if ($LASTEXITCODE -ne 0) {
        Write-Host "validate.py FAILED - not installing a broken kit. Fix it (e.g. python tools/bump_kit_version.py) and rerun." -ForegroundColor Red
        exit 1
    }
}

# --- Team kits (shared staging) -------------------------------------------
Write-Host "`n-> Team kits (shared staging)"
if (Test-Path $teamKitsSrc) {
    # A Codex-only fresh profile may not have ~/.claude yet, but all providers consume this shared
    # staging area when a project is scaffolded.
    if (-not (Test-Path $claudeGlobal)) { New-Item -ItemType Directory -Path $claudeGlobal -Force | Out-Null }
    $stage = Join-Path $claudeGlobal (".team-kits.stage." + $PID + "." + $stamp)
    $previous = Join-Path $claudeGlobal (".team-kits.previous." + $PID + "." + $stamp)
    if ((Test-Path -LiteralPath $stage) -or (Test-Path -LiteralPath $previous)) {
        throw "Refusing to reuse an existing team-kit transaction path: $stage / $previous"
    }
    try {
        & $pyCheck.Source -c "import shutil,sys; shutil.copytree(sys.argv[1], sys.argv[2], ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo','.pytest_cache','.ruff_cache','.mypy_cache'))" $teamKitsSrc $stage
        if ($LASTEXITCODE -ne 0) { throw "Could not stage a clean team-kits tree" }
        if (Test-Path -LiteralPath $claudeTeamKits) {
            Move-Item -LiteralPath $claudeTeamKits -Destination $previous
        }
        try {
            Move-Item -LiteralPath $stage -Destination $claudeTeamKits
        } catch {
            if (Test-Path -LiteralPath $previous) {
                Move-Item -LiteralPath $previous -Destination $claudeTeamKits
            }
            throw
        }
        if (Test-Path -LiteralPath $previous) { Remove-Item -LiteralPath $previous -Recurse -Force }
    } finally {
        if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    }
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
    # Add missing global defaults while preserving existing personal values; union permission lists.
    $py = $pyCheck
    if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
    $oursSettings = Join-Path $userClaudeSrc "settings.json"
    if ($py -and (Test-Path $mergeScript) -and (Test-Path $oursSettings)) {
        & $py.Source $mergeScript $oursSettings (Join-Path $claudeGlobal "settings.json")
        if ($LASTEXITCODE -ne 0) {
            Write-Host "settings.json merge FAILED (your file was not modified) - fix ~/.claude/settings.json and rerun." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "  [warn] python not found or merge script missing - skipped settings.json merge." -ForegroundColor Yellow
        Write-Host "         Add only missing defaults and union permissions.allow/deny from user/claude/settings.json manually." -ForegroundColor Yellow
    }
}

# One-time cleanup of files older installs shipped for the now-removed Copilot support — runs for
# EVERY target (a codex-only profile may still carry them from an earlier "both" install).
Remove-OldSkills -Destination $copilotSkills
foreach ($legacyName in $legacyCopilotNames) {
    $legacyPath = Join-Path $vscodePrompts $legacyName
    if (Test-Path $legacyPath) {
        Assert-NoReparseTree $legacyPath
        Remove-Item $legacyPath -Force
        Write-Host "  [ok]   removed legacy Copilot file: $legacyName" -ForegroundColor Yellow
    }
}

if ($Target -eq "both" -or $Target -eq "codex") {
    Write-Host "`n-> Codex CLI (entry gate)"
    if (-not (Test-Path $codexGlobal)) {
        New-Item -ItemType Directory -Path $codexGlobal -Force | Out-Null
        Write-Host "  [ok]   created Codex home: $codexGlobal" -ForegroundColor Green
    }
    # The entry gate teaches a fresh Codex session how to bootstrap a team-kit project. It owns
    # AGENTS.md, while an existing AGENTS.override.md remains user-owned and untouched.
    Install-File -Src (Join-Path $userCodexSrc "AGENTS.md") -Dest (Join-Path $codexGlobal "AGENTS.md") -Label "AGENTS.md -> $codexGlobal\AGENTS.md (entry gate)"
    if (Test-Path (Join-Path $codexGlobal "AGENTS.override.md")) {
        Write-Host "  [warn] preserved AGENTS.override.md; Codex will use it instead of the installed entry gate." -ForegroundColor Yellow
    }
}

Write-Host "`nDone. Backup at $backupDir." -ForegroundColor Cyan
if ($Target -eq "both" -or $Target -eq "claude") {
    Write-Host "Start a new Claude Code session to pick up the installed configuration." -ForegroundColor Cyan
}
if ($Target -eq "both" -or $Target -eq "codex") {
    Write-Host "Start a new Codex session to pick up the entry gate." -ForegroundColor Cyan
}
