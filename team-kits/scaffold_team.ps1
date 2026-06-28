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

# Back up any existing local team files before overwriting (project_memory is left untouched).
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bdir = Join-Path $repo ".claude\backups\$stamp"
function Backup-Local {
    param([string]$p)
    if (Test-Path $p) {
        if (-not (Test-Path $bdir)) { New-Item -ItemType Directory -Force -Path $bdir | Out-Null }
        Copy-Item $p (Join-Path $bdir (Split-Path $p -Leaf)) -Recurse -Force
    }
}
Backup-Local (Join-Path $repo "CLAUDE.md")
Backup-Local (Join-Path $repo ".claude\settings.json")
Backup-Local (Join-Path $repo ".claude\agents")
if (Test-Path $bdir) { Write-Host "  [ok] backed up existing team files -> .claude/backups/$stamp" -ForegroundColor Green }

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
# Role skills travel with the team (preloaded into the agents via their `skills:` frontmatter).
$skillsSrc = Join-Path $kit "skills"
if (Test-Path $skillsSrc) {
    $skillsDst = Join-Path $repo ".claude\skills"
    if (-not (Test-Path $skillsDst)) { New-Item -ItemType Directory -Force -Path $skillsDst | Out-Null }
    Get-ChildItem -Path $skillsSrc -Directory | ForEach-Object {
        $d = Join-Path $skillsDst $_.Name
        if (Test-Path $d) { Remove-Item $d -Recurse -Force }
        Copy-Item $_.FullName $d -Recurse -Force
        Write-Host "  [ok] skill: $($_.Name)" -ForegroundColor Green
    }
}
$settingsSrc = Join-Path $kit "settings\settings.json"
if (Test-Path $settingsSrc) {
    Copy-Item $settingsSrc (Join-Path $repo ".claude\settings.json") -Force
    Write-Host "  [ok] .claude/settings.json (session agent + enforcement hooks)" -ForegroundColor Green
}

# Repo-level quality templates (scripts/quality.py, CI, pre-commit, requirements-dev) -- copy-if-absent
# so DevOps can customise them without a re-scaffold clobbering changes. The merge gate runs quality.py.
$repoTplSrc = Join-Path $kit "templates\repo"
if (Test-Path $repoTplSrc) {
    Get-ChildItem -Path $repoTplSrc -Recurse -File -Force | ForEach-Object {
        $rel = $_.FullName.Substring($repoTplSrc.Length).TrimStart('\', '/')
        $dst = Join-Path $repo $rel
        if (-not (Test-Path $dst)) {
            $dstDir = Split-Path $dst
            if ($dstDir -and -not (Test-Path $dstDir)) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }
            Copy-Item $_.FullName $dst -Force
            Write-Host "  [ok] repo: $rel" -ForegroundColor Green
        }
    }
}

Write-Host "Team '$Team' installed locally. RESTART the session (close/reopen, or start a new session in this folder) -- the new agents and the 'agent: project-manager' setting only load at session start. After the restart, just type 'weiter': this repo then runs directly as your Project Manager and picks up any draft plan in project_memory/." -ForegroundColor Cyan
