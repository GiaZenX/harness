# Scaffold a team kit into the current repository (Windows).
# Usage: scaffold_team.ps1 -Team dev-team
# Copies the kit's agents into ./.claude/agents/ and its constitution into ./AGENTS.md,
# plus enforcement hooks into ./.claude/. project_memory/ is NOT created here -- the entry gate
# creates it deterministically via init_project_memory.ps1 BEFORE scaffolding (the PM startup
# backfills it the same way if missing). This script never touches project_memory/.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Team,
    [string]$Preset = ""
)

$ErrorActionPreference = "Stop"
if ($Team -notmatch '^[A-Za-z0-9_-]+$') { throw "Team must match [A-Za-z0-9_-]+" }
if ($Preset -and $Preset -notmatch '^[A-Za-z0-9_-]+$') { throw "Preset must match [A-Za-z0-9_-]+" }
$kit = Join-Path $env:USERPROFILE ".claude\team-kits\$Team"
if (-not (Test-Path $kit)) { throw "Team kit not found: $kit" }
$kitsRoot = Split-Path -Parent $kit

$repo = (Get-Location).Path
Write-Host "Scaffolding team '$Team' into $repo" -ForegroundColor Cyan

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

function Assert-SafeRepoPath {
    param([string]$Path)
    $repoFull = [IO.Path]::GetFullPath($repo).TrimEnd('\', '/')
    $full = [IO.Path]::GetFullPath($Path)
    $prefix = $repoFull + [IO.Path]::DirectorySeparatorChar
    if ($full -ne $repoFull -and -not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Controlled scaffold path escapes the repository: $full"
    }
    $relative = if ($full -eq $repoFull) { "" } else { $full.Substring($prefix.Length) }
    $current = $repoFull
    foreach ($component in ($relative -split '[\\/]' | Where-Object { $_ })) {
        $current = Join-Path $current $component
        if (Test-ReparsePoint $current) {
            throw "Refusing symlink/junction/reparse path '$current'; no scaffold files were changed."
        }
    }
}

function Assert-NoReparseComponentsAbsolute {
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    $current = $root
    foreach ($component in ($full.Substring($root.Length) -split '[\\/]' | Where-Object { $_ })) {
        $current = Join-Path $current $component
        if (Test-ReparsePoint $current) {
            throw "Refusing symlink/junction/reparse path '$current'; no scaffold files were changed."
        }
    }
}

function Assert-NoReparseTree {
    param([string]$Path, [switch]$AllowOutsideRepo)
    if ($AllowOutsideRepo) { Assert-NoReparseComponentsAbsolute $Path } else { Assert-SafeRepoPath $Path }
    if (-not (Test-Path -LiteralPath $Path)) { return }
    if (Test-ReparsePoint $Path) {
        throw "Refusing symlink/junction/reparse path '$Path'; no scaffold files were changed."
    }
    $pending = New-Object System.Collections.Generic.Stack[string]
    if ((Get-Item -LiteralPath $Path -Force).PSIsContainer) { $pending.Push($Path) }
    while ($pending.Count -gt 0) {
        $current = $pending.Pop()
        foreach ($item in (Get-ChildItem -LiteralPath $current -Force)) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing symlink/junction/reparse path '$($item.FullName)'; no scaffold files were changed."
            }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
}

$cfg = Join-Path $repo "project_memory\project_config.yaml"
if (-not (Test-Path $cfg)) {
    throw "project_memory/project_config.yaml is required before scaffolding; no files were changed."
}
Assert-SafeRepoPath $cfg
Assert-NoReparseTree $kit -AllowOutsideRepo
foreach ($relative in @(
        "AGENTS.md", "CLAUDE.md", "AGENTS.override.md", ".claude\settings.json",
        ".claude\agents", ".claude\hooks", ".claude\skills", ".claude\team_kit_roles.txt",
        ".claude\provider_artifacts.json", ".claude\settings.local.json", ".claude\kit_version", ".claude\backups",
        ".codex", ".agents\skills", ".github\hooks", ".github\agents")) {
    Assert-NoReparseTree (Join-Path $repo $relative)
}
foreach ($relative in @(
        ".claude\team_kit_roles.txt.tmp.$PID", ".claude\kit_update_pending.repo",
        ".claude\kit_update_pending.state")) {
    Assert-NoReparseTree (Join-Path $repo $relative)
}
$repoTemplatePreflight = Join-Path $kit "templates\repo"
if (Test-Path -LiteralPath $repoTemplatePreflight) {
    Get-ChildItem -LiteralPath $repoTemplatePreflight -Recurse -File -Force | ForEach-Object {
        $relative = $_.FullName.Substring($repoTemplatePreflight.Length).TrimStart('\', '/')
        Assert-NoReparseTree (Join-Path $repo $relative)
    }
}
$providerPython = Get-Command python -ErrorAction SilentlyContinue
if (-not $providerPython) { $providerPython = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $providerPython) { throw "Python 3.8+ with PyYAML is required to validate provider configuration." }
# No stderr redirect: under EAP=Stop, 2>$null on a native command turns stderr into a
# terminating NativeCommandError and the friendly message below becomes unreachable.
& $providerPython.Source -c "import importlib.util, sys; sys.exit(0 if (sys.version_info >= (3, 8) and importlib.util.find_spec('yaml')) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.8+ with PyYAML is required to validate provider configuration." }
& $providerPython.Source "$PSScriptRoot\gen_provider_artifacts.py" --repo $repo --project-config $cfg --check-config-only
if ($LASTEXITCODE -ne 0) { throw "Invalid provider configuration; no scaffold files were changed." }
$configJson = & $providerPython.Source -c "import json,sys,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1], encoding='utf-8-sig'))))" $cfg
if ($LASTEXITCODE -ne 0) { throw "Could not read validated project_config.yaml." }
$configData = $configJson | ConvertFrom-Json
$localSettings = Join-Path $repo ".claude\settings.local.json"
if (Test-Path -LiteralPath $localSettings) {
    try {
        $localData = Get-Content -LiteralPath $localSettings -Raw | ConvertFrom-Json
    } catch {
        throw "Invalid .claude/settings.local.json; no scaffold files were changed."
    }
    if ($null -eq $localData -or -not ($localData -is [PSCustomObject])) {
        throw ".claude/settings.local.json must contain a JSON object; no scaffold files were changed."
    }
    # Only ENFORCEMENT-replacing keys block the scaffold. `permissions` is where Claude Code
    # records every "Always allow" grant and `model` is a legitimate local preference — blocking
    # on those made every actively used project unable to take kit updates.
    $hardLocalKeys = @($localData.PSObject.Properties.Name | Where-Object {
        $_ -in @("agent", "hooks", "disableAllHooks")
    })
    if ($hardLocalKeys.Count -gt 0) {
        throw ".claude/settings.local.json overrides enforcement key(s): $($hardLocalKeys -join ', '). Remove them (they replace the team's PM/hook layer) before scaffolding; no files were changed."
    }
    if ("model" -in @($localData.PSObject.Properties.Name)) {
        Write-Host "  [warn] .claude/settings.local.json sets model locally; the team model_map is authoritative -- session_status will flag drift." -ForegroundColor Yellow
    }
}

# Presets are MECHANICAL (a preset that is only a config comment enforces nothing — the real kits
# shipped years of inert solo/duo/team values): with -Preset only that preset's roles (+ the lead)
# are installed. Other custom kit roles are absent; Claude also blocks them in guard_agent_spawn,
# while Codex enforces the exact-role policy through lead/specialist instructions (native built-ins
# remain technically available). Upgrading = re-run with the larger preset + session restart.
# No -Preset argument? Take the RECORDED, user-confirmed preset from project_config.yaml — else
# the first kit UPDATE would silently install the full roster and the "mechanical preset"
# guarantee evaporates (the exact inert-preset failure mode this design kills).
$presetSource = "argument"
if (-not $Preset) {
    if ($configData.project.preset) {
        $Preset = [string]$configData.project.preset
        $presetSource = "project_config.yaml"
    }
}
if (-not $Preset) { throw "Validated project_config.yaml contains no preset; no scaffold files were changed." }
$presetJson = & $providerPython.Source "$PSScriptRoot\preset_config.py" --kit $kit --preset $Preset --source $presetSource --format json
if ($LASTEXITCODE -ne 0) { throw "Invalid preset configuration; no scaffold files were changed." }
try { $presetData = $presetJson | ConvertFrom-Json } catch {
    throw "Preset resolver returned invalid JSON; no scaffold files were changed."
}
$lead = [string]$presetData.lead
$presetRoles = if ($presetData.all) { $null } else { @($presetData.roles) }
Write-Host "  [preset $Preset, from $presetSource] specialist roles: $(if ($presetData.all) { 'ALL' } else { $presetRoles -join ', ' })" -ForegroundColor Cyan

# Back up any existing local team files before overwriting (project_memory is left untouched).
# Preserve the repo-relative paths inside the snapshot: both .claude/skills and .agents/skills
# otherwise collapse to the same basename and one backup silently replaces the other.
$stampBase = Get-Date -Format "yyyyMMdd-HHmmss"
$stamp = $stampBase
$bdir = Join-Path $repo ".claude\backups\$stamp"
$stampSuffix = 1
while (Test-Path -LiteralPath $bdir) {
    $stamp = "$stampBase-$stampSuffix"
    $bdir = Join-Path $repo ".claude\backups\$stamp"
    $stampSuffix++
}
function Backup-Local {
    param([string]$p, [string]$relativeDestination)
    if (Test-Path -LiteralPath $p) {
        $dst = Join-Path $bdir $relativeDestination
        $dstParent = Split-Path $dst
        if (-not (Test-Path -LiteralPath $dstParent)) {
            New-Item -ItemType Directory -Force -Path $dstParent | Out-Null
        }
        Copy-Item -LiteralPath $p -Destination $dst -Recurse -Force
    }
}
Backup-Local (Join-Path $repo "CLAUDE.md") "CLAUDE.md"
Backup-Local (Join-Path $repo "AGENTS.md") "AGENTS.md"
Backup-Local (Join-Path $repo "AGENTS.override.md") "AGENTS.override.md"
Backup-Local (Join-Path $repo ".claude\settings.json") ".claude\settings.json"
Backup-Local (Join-Path $repo ".claude\settings.local.json") ".claude\settings.local.json"
Backup-Local (Join-Path $repo ".claude\agents") ".claude\agents"
Backup-Local (Join-Path $repo ".claude\hooks") ".claude\hooks"
Backup-Local (Join-Path $repo ".claude\skills") ".claude\skills"
Backup-Local (Join-Path $repo ".claude\team_kit_roles.txt") ".claude\team_kit_roles.txt"
Backup-Local (Join-Path $repo ".claude\provider_artifacts.json") ".claude\provider_artifacts.json"
Backup-Local (Join-Path $repo ".claude\kit_version") ".claude\kit_version"
Backup-Local (Join-Path $repo ".codex") ".codex"
Backup-Local (Join-Path $repo ".agents\skills") ".agents\skills"
Backup-Local (Join-Path $repo ".github\hooks") ".github\hooks"
Backup-Local (Join-Path $repo ".github\agents") ".github\agents"
if (Test-Path $bdir) { Write-Host "  [ok] backed up existing team files -> .claude/backups/$stamp" -ForegroundColor Green }
if (Test-Path -LiteralPath (Join-Path $repo "AGENTS.override.md")) {
    throw "Repository AGENTS.override.md takes precedence over the team constitution. It was backed up and left untouched; merge/remove it only after explicit user review, then rerun scaffolding."
}

function Restore-ScaffoldSnapshot {
    $relativePaths = @(
        "CLAUDE.md", "AGENTS.md", ".claude\settings.json", ".claude\agents",
        ".claude\hooks", ".claude\skills", ".claude\team_kit_roles.txt",
        ".claude\provider_artifacts.json", ".claude\kit_version", ".codex",
        ".agents\skills", ".github\hooks", ".github\agents")
    foreach ($relative in $relativePaths) {
        $target = Join-Path $repo $relative
        $saved = Join-Path $bdir $relative
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        if (Test-Path -LiteralPath $saved) {
            $parent = Split-Path -Parent $target
            if ($parent -and -not (Test-Path -LiteralPath $parent)) {
                New-Item -ItemType Directory -Force -Path $parent | Out-Null
            }
            Copy-Item -LiteralPath $saved -Destination $target -Recurse -Force
        }
    }
}

# Treat the Claude base plus all generated provider artifacts as one logical layer. Any normal
# failure before provider generation completes restores the byte-for-byte scaffold snapshot.
try {
$agentsSrc = Join-Path $kit "agents"
$agentsDst = Join-Path $repo ".claude\agents"
$skillsSrc = Join-Path $kit "skills"
$skillsDst = Join-Path $repo ".claude\skills"
$rolesManifest = Join-Path $repo ".claude\team_kit_roles.txt"

# Remove only files previously owned by the kit. The manifest makes preset downgrades and kit
# switches subtractive without deleting unrelated user agents/skills. The versioned header/count
# makes truncated ownership fail closed instead of silently orphaning spawnable roles.
$rolesToRemove = @()
if (Test-Path -LiteralPath $rolesManifest) {
    $manifestLines = @(Get-Content -LiteralPath $rolesManifest)
    $header = if ($manifestLines.Count -gt 0) { $manifestLines[0].Trim() } else { "" }
    $headerMatch = [regex]::Match($header,
        '^# agents-and-skills:team-kit-roles v1 team=[A-Za-z0-9_-]+ count=([0-9]+)$')
    if (-not $headerMatch.Success) {
        throw "Invalid .claude/team_kit_roles.txt header; no role files were changed (restore its scaffold backup or remove it for legacy migration)"
    }
    $expectedRoles = [int]$headerMatch.Groups[1].Value
    $invalidRoleLine = $false
    $parsedRoles = @()
    foreach ($line in ($manifestLines | Select-Object -Skip 1)) {
        $role = $line.Trim()
        if ($role -match '^[A-Za-z0-9_-]+$') { $parsedRoles += $role }
        elseif ($role) { $invalidRoleLine = $true }
    }
    $rolesToRemove = @($parsedRoles | Sort-Object -Unique)
    if ($invalidRoleLine -or $expectedRoles -lt 1 -or
            $parsedRoles.Count -ne $expectedRoles -or $rolesToRemove.Count -ne $expectedRoles) {
        throw "Invalid/truncated .claude/team_kit_roles.txt; no role files were changed (restore its scaffold backup)"
    }
} else {
    # Legacy installs predate the ownership manifest. Their constitution marker proves which
    # staged kit owned the old roles. Without that proof, a same-named user role is ambiguous and
    # scaffolding must fail closed instead of deleting it.
    $legacyTeam = ""
    foreach ($entryFile in @((Join-Path $repo "AGENTS.md"), (Join-Path $repo "CLAUDE.md"))) {
        if (-not $legacyTeam -and (Test-Path -LiteralPath $entryFile)) {
            $firstLine = Get-Content -LiteralPath $entryFile -TotalCount 1
            $marker = [regex]::Match([string]$firstLine,
                'agents-and-skills:team-kit\s+([A-Za-z0-9_-]+)')
            if ($marker.Success) { $legacyTeam = $marker.Groups[1].Value }
        }
    }
    $legacyAgents = if ($legacyTeam) { Join-Path $kitsRoot "$legacyTeam\agents" } else { "" }
    if ($legacyAgents -and (Test-Path -LiteralPath $legacyAgents)) {
        $rolesToRemove = @(Get-ChildItem -LiteralPath $legacyAgents -Filter "*.md" -File |
                           ForEach-Object { $_.BaseName })
        Write-Host "  [migration] role ownership recovered from the '$legacyTeam' constitution marker" -ForegroundColor Cyan
    } else {
        $knownRoles = @()
        foreach ($kitDir in (Get-ChildItem -LiteralPath $kitsRoot -Directory)) {
            $knownAgents = Join-Path $kitDir.FullName "agents"
            if (Test-Path -LiteralPath $knownAgents) {
                $knownRoles += @(Get-ChildItem -LiteralPath $knownAgents -Filter "*.md" -File |
                                 ForEach-Object { $_.BaseName })
            }
        }
        $ambiguous = @($knownRoles | Sort-Object -Unique | Where-Object {
            (Test-Path -LiteralPath (Join-Path $agentsDst ($_ + ".md"))) -or
            (Test-Path -LiteralPath (Join-Path $skillsDst $_))
        })
        if ($ambiguous.Count -gt 0) {
            throw "Cannot prove ownership of pre-manifest role artifact(s): $($ambiguous -join ', '). Existing files were backed up and left untouched; restore/create a valid .claude/team_kit_roles.txt or move the collisions aside."
        }
    }
}
$rolesToRemove = @($rolesToRemove | Sort-Object -Unique)

# A legacy marker proves only the old kit's files. Never overwrite an unrelated same-named custom
# role that the selected target preset would otherwise install.
$targetRoles = @(Get-ChildItem -LiteralPath $agentsSrc -Filter "*.md" -File | Where-Object {
    -not $presetRoles -or $_.BaseName -eq $lead -or $presetRoles -contains $_.BaseName
} | ForEach-Object { $_.BaseName })
$targetCollisions = @($targetRoles | Where-Object {
    $rolesToRemove -notcontains $_ -and (
        (Test-Path -LiteralPath (Join-Path $agentsDst ($_ + ".md"))) -or
        (Test-Path -LiteralPath (Join-Path $skillsDst $_)))
})
if ($targetCollisions.Count -gt 0) {
    throw "Target role collision(s) are not kit-owned: $($targetCollisions -join ', '). Existing files were backed up and left untouched; move them aside before scaffolding."
}
$removedRoleArtifacts = 0
foreach ($role in $rolesToRemove) {
    $oldAgent = Join-Path $agentsDst ($role + ".md")
    $oldSkill = Join-Path $skillsDst $role
    if (Test-Path -LiteralPath $oldAgent) {
        Remove-Item -LiteralPath $oldAgent -Force
        $removedRoleArtifacts++
    }
    if (Test-Path -LiteralPath $oldSkill) {
        Remove-Item -LiteralPath $oldSkill -Recurse -Force
        $removedRoleArtifacts++
    }
}
if ($removedRoleArtifacts -gt 0) {
    Write-Host "  [ok] removed $removedRoleArtifacts previously kit-managed agent/skill artifact(s) before refresh" -ForegroundColor Green
}

if (-not (Test-Path $agentsDst)) { New-Item -ItemType Directory -Force -Path $agentsDst | Out-Null }
$installedSpecialists = @()
Get-ChildItem -Path $agentsSrc -Filter "*.md" | Sort-Object Name | ForEach-Object {
    if ($presetRoles -and $_.BaseName -ne $lead -and $presetRoles -notcontains $_.BaseName) { return }
    $agentDstPath = Join-Path $agentsDst $_.Name
    Copy-Item $_.FullName $agentDstPath -Force
    # Kit sources carry provider-neutral tier aliases (lead/worker/light); the INSTALLED Claude
    # frontmatter needs the concrete reference-platform name (model_map stamping may override).
    # Lookahead keeps the original line ending (no mixed CRLF/LF after the rewrite).
    $agentRaw = [IO.File]::ReadAllText($agentDstPath)
    $agentResolved = (($agentRaw -replace '(?m)^model:[ \t]*lead(?=\s*$)', 'model: opus') `
        -replace '(?m)^model:[ \t]*worker(?=\s*$)', 'model: sonnet') `
        -replace '(?m)^model:[ \t]*light(?=\s*$)', 'model: haiku'
    if ($agentResolved -ne $agentRaw) { [IO.File]::WriteAllText($agentDstPath, $agentResolved) }
    if ($_.BaseName -ne $lead) { $installedSpecialists += $_.BaseName }
    Write-Host "  [ok] agent: $($_.Name)" -ForegroundColor Green
}

# §11 map sync (the scaffold resets agent frontmatter to kit defaults — when the project already
# carries user-confirmed model_map/effort_map, stamp them back DETERMINISTICALLY instead of leaving
# an out-of-sync nag for the PM: a real update regressed a user-approved opus role to sonnet and
# nothing fixed it for two days).
if (Test-Path $cfg) {
    $synced = 0
    foreach ($mapSpec in @(@("model_map", "model"), @("effort_map", "effort"))) {
        $mapName = $mapSpec[0]
        $field = $mapSpec[1]
        $mapObject = $configData.$mapName
        if (-not $mapObject) { continue }
        foreach ($property in $mapObject.PSObject.Properties) {
            $role = [string]$property.Name
            $val = [string]$property.Value
            # tier aliases (team-kits/model_tiers.yaml): map may say lead/worker/light —
            # Claude agent frontmatter gets the concrete reference-platform name.
            switch ($val) { "lead" { $val = "opus" } "worker" { $val = "sonnet" } "light" { $val = "haiku" } }
            $ap = Join-Path $agentsDst ($role + ".md")
            if (Test-Path $ap) {
                $raw = [IO.File]::ReadAllText($ap)
                $re = [regex]('(?m)^' + $field + ':[^\r\n]*')
                $new = $re.Replace($raw, ($field + ": " + $val), 1)
                if ($new -ne $raw) { [IO.File]::WriteAllText($ap, $new); $synced++ }
            }
        }
    }
    if ($synced -gt 0) { Write-Host "  [ok] re-synced $synced model:/effort: line(s) from project_config.yaml (user-confirmed maps win over kit defaults)" -ForegroundColor Green }
}

# Constitution: AGENTS.md is the CANONICAL file (AAIF/Linux-Foundation standard, read natively by
# Codex); CLAUDE.md is a thin import shim because Claude Code reads CLAUDE.md
# only -- @AGENTS.md is Anthropic's documented bridge (verified: main agent AND subagents inherit
# the imported content; the kit marker stays on line 1 for the entry gate + session_status).
$conSrc = Join-Path $kit "constitution\AGENTS.md"
if (Test-Path $conSrc) {
    Copy-Item $conSrc (Join-Path $repo "AGENTS.md") -Force
    $marker = (Get-Content $conSrc -TotalCount 1)
    [IO.File]::WriteAllText((Join-Path $repo "CLAUDE.md"), "$marker`r`n@AGENTS.md`r`n")
    Write-Host "  [ok] AGENTS.md (constitution) + CLAUDE.md (import shim)" -ForegroundColor Green
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
if (Test-Path $skillsSrc) {
    if (-not (Test-Path $skillsDst)) { New-Item -ItemType Directory -Force -Path $skillsDst | Out-Null }
    Get-ChildItem -Path $skillsSrc -Directory | ForEach-Object {
        if ($presetRoles -and $_.Name -ne $lead -and $presetRoles -notcontains $_.Name) { return }
        $d = Join-Path $skillsDst $_.Name
        if (Test-Path $d) { Remove-Item $d -Recurse -Force }
        Copy-Item $_.FullName $d -Recurse -Force
        Write-Host "  [ok] skill: $($_.Name)" -ForegroundColor Green
    }
}

# Record exactly the role files managed by this installation. The lead is always first; specialists
# are stable and unique so the next refresh can safely remove only kit-owned names.
$manifestRoles = @($lead) + @($installedSpecialists | Sort-Object -Unique)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$manifestHeader = "# agents-and-skills:team-kit-roles v1 team=$Team count=$($manifestRoles.Count)"
$manifestTemp = "$rolesManifest.tmp.$PID"
[IO.File]::WriteAllLines($manifestTemp, [string[]](@($manifestHeader) + $manifestRoles), $utf8NoBom)
Move-Item -LiteralPath $manifestTemp -Destination $rolesManifest -Force
Write-Host "  [ok] .claude/team_kit_roles.txt ($($manifestRoles.Count) managed role(s))" -ForegroundColor Green

$settingsSrc = Join-Path $kit "settings\settings.json"
if (Test-Path $settingsSrc) {
    Copy-Item $settingsSrc (Join-Path $repo ".claude\settings.json") -Force
    Write-Host "  [ok] .claude/settings.json (session agent + enforcement hooks)" -ForegroundColor Green
}
# Stamp the installed kit version (session_status compares it with the staged kit to flag updates).
$verSrc = Join-Path $kit "VERSION"
if (Test-Path $verSrc) {
    Copy-Item $verSrc (Join-Path $repo ".claude\kit_version") -Force
    Write-Host "  [ok] .claude/kit_version ($((Get-Content $verSrc -TotalCount 1)))" -ForegroundColor Green
}

# Extra providers: Python/PyYAML owns parsing so quoted or block-style valid YAML can never be
# mistaken for an empty provider set (which would delete provider artifacts).
if (Test-Path $cfg) {
    $providerArgs = @("--repo", $repo, "--lead", $lead, "--project-config", $cfg)
    & $providerPython.Source "$PSScriptRoot\gen_provider_artifacts.py" @providerArgs
    if ($LASTEXITCODE -ne 0) { throw "Provider artifact generation failed; backups are under $bdir" }
}
} catch {
    $failure = $_
    try {
        Restore-ScaffoldSnapshot
        Write-Host "  [rollback] restored the previous Claude/Codex provider layer from .claude/backups/$stamp" -ForegroundColor Yellow
    } catch {
        throw "Scaffolding failed and rollback also failed. Original error: $failure. Rollback error: $_. Restore manually from $bdir"
    }
    throw $failure
}

# Repo-level quality templates (scripts/quality.py, CI, pre-commit, requirements-dev) -- copy-if-absent
# so DevOps can customise them without a re-scaffold clobbering changes. The merge gate runs quality.py.
# Diverged files additionally land in .claude/kit_update_pending.repo: printed [kept] lines were shown
# but never acted on in a real project (kit fixes silently never arrived) -- session_status now reminds
# the PM until every line is merged or consciously skipped and the file is DELETED.
$keptList = @()
$repoTplSrc = Join-Path $kit "templates\repo"
if (Test-Path $repoTplSrc) {
    Get-ChildItem -Path $repoTplSrc -Recurse -File -Force | Where-Object { $_.FullName -notmatch '__pycache__|\.ruff_cache|\.mypy_cache|\.pytest_cache' } | ForEach-Object {
        $rel = $_.FullName.Substring($repoTplSrc.Length).TrimStart('\', '/')
        $dst = Join-Path $repo $rel
        # scripts/kit_checks.py is KIT-OWNED: always overwritten (like the hooks), never pending —
        # so kit-level check fixes reach even projects whose quality.py runner is a heavy fork.
        if (($rel -replace '\\', '/') -eq 'scripts/kit_checks.py') {
            $dstDir = Split-Path $dst
            if ($dstDir -and -not (Test-Path $dstDir)) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }
            Copy-Item $_.FullName $dst -Force
            Write-Host "  [ok] repo (kit-owned, always updated): $rel" -ForegroundColor Green
            return
        }
        if (-not (Test-Path $dst)) {
            $dstDir = Split-Path $dst
            if ($dstDir -and -not (Test-Path $dstDir)) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }
            Copy-Item $_.FullName $dst -Force
            Write-Host "  [ok] repo: $rel" -ForegroundColor Green
        } elseif ((Get-FileHash $dst -Algorithm SHA256).Hash -ne (Get-FileHash $_.FullName -Algorithm SHA256).Hash) {
            # copy-if-absent keeps the project's version — but say so, or a kit fix (e.g. quality.py)
            # silently never reaches existing projects while the update reads as "applied".
            Write-Host "  [kept] repo: $rel (differs from the kit template - review/merge manually)" -ForegroundColor Yellow
            $keptList += ($rel -replace '\\', '/')
        }
    }
}
$pendFile = Join-Path $repo ".claude\kit_update_pending.repo"
$stateFile = Join-Path $repo ".claude\kit_update_pending.state"
if ($keptList.Count -gt 0) {
    $lines = @("# Repo templates that DIFFER from kit $Team $((Get-Content (Join-Path $kit 'VERSION') -TotalCount 1 -ErrorAction SilentlyContinue)) -- the PM reviews each against the kit template, merges the kit's fixes (or documents a conscious skip in progress.yaml log:), then DELETES this file. session_status reminds every session until it is gone.")
    $lines += ($keptList | ForEach-Object { "- $_" })
    Set-Content -Path $pendFile -Value $lines -Encoding utf8
    if (Test-Path $stateFile) { Remove-Item $stateFile -Force }   # fresh update -> fresh nag counter
    Write-Host "  [!] $($keptList.Count) diverged repo file(s) -> .claude/kit_update_pending.repo (merge or consciously skip, then delete it)" -ForegroundColor Yellow
} elseif (Test-Path $pendFile) {
    Remove-Item $pendFile -Force
}

Write-Host "Team '$Team' installed locally. RESTART the session (close/reopen, or start a new session in this folder) -- the new agents and the 'agent: $lead' setting only load at session start. After the restart, type anything (e.g. 'weiter') -- nothing is auto-sent, YOU stay in control of the first message; the '$lead' lead then greets you with a one-line status and picks up any draft plan in project_memory/." -ForegroundColor Cyan
Write-Host "NOTE: if a session is ALREADY running in this folder (even suspended at a usage limit), its hooks are live on the new files from this moment -- a real restamp landed mid-session and entangled kit files with build changes. Finish or restart that session before continuing work there." -ForegroundColor Yellow
