# Windows installer for agent-skills
# Usage:
#   .\install.ps1                 # Install for both Claude Code and Copilot
#   .\install.ps1 -Target claude  # Only Claude Code
#   .\install.ps1 -Target copilot # Only Copilot
#   .\install.ps1 -Force          # Overwrite existing files

[CmdletBinding()]
param(
    [ValidateSet("both", "claude", "copilot")]
    [string]$Target = "both",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$skillsSrc      = Join-Path $repoRoot "skills"
$claudeSrc      = Join-Path $repoRoot "claude-code"
$copilotSrc     = Join-Path $repoRoot "github-copilot"

$claudeSkills   = Join-Path $env:USERPROFILE ".claude\skills"
$claudeGlobal   = Join-Path $env:USERPROFILE ".claude"
$copilotSkills  = Join-Path $env:USERPROFILE ".copilot\skills"
$vscodePrompts  = Join-Path $env:APPDATA "Code\User\prompts"

function Install-Skills {
    param([string]$Destination, [string]$Label)
    if (-not (Test-Path $Destination)) { New-Item -ItemType Directory -Path $Destination -Force | Out-Null }
    Get-ChildItem -Path $skillsSrc -Directory | ForEach-Object {
        $dest = Join-Path $Destination $_.Name
        if ((Test-Path $dest) -and -not $Force) {
            Write-Host "  [skip] $Label : $($_.Name)" -ForegroundColor Yellow; return
        }
        if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
        Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force
        Write-Host "  [ok]   $Label : $($_.Name)" -ForegroundColor Green
    }
}

function Install-File {
    param([string]$Src, [string]$Dest, [string]$Label)
    if (-not (Test-Path $Src)) { Write-Host "  [warn] not found: $Src" -ForegroundColor Yellow; return }
    if ((Test-Path $Dest) -and -not $Force) {
        Write-Host "  [skip] $Label (use -Force to overwrite)" -ForegroundColor Yellow; return
    }
    $dir = Split-Path $Dest
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [System.IO.File]::WriteAllText($Dest, (Get-Content $Src -Raw -Encoding UTF8), [System.Text.UTF8Encoding]::new($false))
    Write-Host "  [ok]   $Label" -ForegroundColor Green
}

Write-Host "Installing agent-skills..." -ForegroundColor Cyan

if ($Target -eq "both" -or $Target -eq "claude") {
    Write-Host "`n-> Claude Code"
    Install-Skills -Destination $claudeSkills -Label "skill"
    Install-File -Src (Join-Path $claudeSrc "CLAUDE.md") -Dest (Join-Path $claudeGlobal "CLAUDE.md") -Label "CLAUDE.md -> ~/.claude/CLAUDE.md"
}

if ($Target -eq "both" -or $Target -eq "copilot") {
    Write-Host "`n-> GitHub Copilot"
    Install-Skills -Destination $copilotSkills -Label "skill"
    Get-ChildItem -Path $copilotSrc -Filter "*.agent.md" | ForEach-Object {
        Install-File -Src $_.FullName -Dest (Join-Path $vscodePrompts $_.Name) -Label "agent: $($_.Name)"
    }
    Get-ChildItem -Path $copilotSrc -Filter "*.instructions.md" | ForEach-Object {
        Install-File -Src $_.FullName -Dest (Join-Path $vscodePrompts $_.Name) -Label "instructions: $($_.Name)"
    }
    # Copilot memory-tool user-preferences
    $copilotMemory = Join-Path $env:APPDATA "Code\User\globalStorage\github.copilot-chat\memory-tool\memories"
    Install-File -Src (Join-Path $copilotSrc "user-preferences.md") -Dest (Join-Path $copilotMemory "user-preferences.md") -Label "user-preferences.md -> Copilot memory"
}

Write-Host "`nDone. Restart VS Code to pick up new skills/agents." -ForegroundColor Cyan