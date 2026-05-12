# Windows installer for agent-skills
# Usage:
#   .\install.ps1                 # Install for both Claude Code and Copilot
#   .\install.ps1 -Target claude  # Only Claude Code
#   .\install.ps1 -Target copilot # Only Copilot
#   .\install.ps1 -Force          # Overwrite existing skills/agents

[CmdletBinding()]
param(
    [ValidateSet("both", "claude", "copilot")]
    [string]$Target = "both",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$skillsSrc = Join-Path $repoRoot "skills"
$agentsSrc = Join-Path $repoRoot "agents"
$instructionsFile = Join-Path $repoRoot "copilot-instructions.md"

$claudeSkills = Join-Path $env:USERPROFILE ".claude\skills"
$copilotSkills = Join-Path $env:USERPROFILE ".copilot\skills"
$vscodePrompts = Join-Path $env:APPDATA "Code\User\prompts"

function Install-Skills {
    param([string]$Destination, [string]$Label)

    if (-not (Test-Path $Destination)) {
        New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    }

    Get-ChildItem -Path $skillsSrc -Directory | ForEach-Object {
        $dest = Join-Path $Destination $_.Name
        if ((Test-Path $dest) -and -not $Force) {
            Write-Host "  [skip] $Label : $($_.Name) (already exists, use -Force to overwrite)" -ForegroundColor Yellow
            return
        }
        if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
        Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force
        Write-Host "  [ok]   $Label : $($_.Name)" -ForegroundColor Green
    }
}

function Install-Agents {
    if (-not (Test-Path $vscodePrompts)) {
        New-Item -ItemType Directory -Path $vscodePrompts -Force | Out-Null
    }

    Get-ChildItem -Path $agentsSrc -Filter "*.agent.md" | ForEach-Object {
        $dest = Join-Path $vscodePrompts $_.Name
        if ((Test-Path $dest) -and -not $Force) {
            Write-Host "  [skip] agent : $($_.Name) (already exists, use -Force to overwrite)" -ForegroundColor Yellow
            return
        }
        Copy-Item -Path $_.FullName -Destination $dest -Force
        Write-Host "  [ok]   agent : $($_.Name)" -ForegroundColor Green
    }
}

function Install-Instructions {
    if (-not (Test-Path $instructionsFile)) {
        Write-Host "  [warn] copilot-instructions.md not found in repo" -ForegroundColor Yellow
        return
    }

    if (-not (Test-Path $vscodePrompts)) {
        New-Item -ItemType Directory -Path $vscodePrompts -Force | Out-Null
    }

    $dest = Join-Path $vscodePrompts "copilot-instructions.md"
    if ((Test-Path $dest) -and -not $Force) {
        Write-Host "  [skip] instructions: copilot-instructions.md (already exists, use -Force to overwrite)" -ForegroundColor Yellow
        return
    }
    Copy-Item -Path $instructionsFile -Destination $dest -Force
    Write-Host "  [ok]   instructions: copilot-instructions.md" -ForegroundColor Green
}

Write-Host "Installing agent-skills..." -ForegroundColor Cyan

if ($Target -eq "both" -or $Target -eq "claude") {
    Write-Host "`n-> Claude Code ($claudeSkills)"
    Install-Skills -Destination $claudeSkills -Label "claude"
}

if ($Target -eq "both" -or $Target -eq "copilot") {
    Write-Host "`n-> GitHub Copilot ($copilotSkills)"
    Install-Skills -Destination $copilotSkills -Label "copilot"

    Write-Host "`n-> VS Code Custom Agents & Instructions ($vscodePrompts)"
    Install-Agents
    Install-Instructions
}

Write-Host "`nDone. Restart VS Code to pick up new skills/agents." -ForegroundColor Cyan
