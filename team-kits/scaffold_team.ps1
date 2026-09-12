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
    [string]$Preset = "",
    # Replay the bundle the LAST install replaced (FR-0041). The .sh twin spells the same switch
    # `--rollback`; `kernel.kitupdate.rollback_command` picks the spelling off the script it names.
    [switch]$Rollback
)

$ErrorActionPreference = "Stop"
if ($Team -notmatch '^[A-Za-z0-9_-]+$') { throw "Team must match [A-Za-z0-9_-]+" }
if ($Preset -and $Preset -notmatch '^[A-Za-z0-9_-]+$') { throw "Preset must match [A-Za-z0-9_-]+" }
$kit = Join-Path $env:USERPROFILE ".claude\team-kits\$Team"
if (-not (Test-Path $kit)) { throw "Team kit not found: $kit" }
$kitsRoot = Split-Path -Parent $kit

$repo = (Get-Location).Path

# Same-version detection (audit): a redundant re-run stays ALLOWED (it legitimately re-syncs
# roles to the recorded preset and repairs drifted managed files) but must be LOUD about not
# resolving merge tasks, and must NOT reset the merge-backlog escalation counter (a PM who
# "updated again just to be safe" used to silently restart the nag from session 1).
$script:SameVersion = $false
$installedVersionFile = Join-Path $repo ".claude\kit_version"
$stagedVersionFile = Join-Path $kit "VERSION"
if ((-not $Rollback) -and (Test-Path $installedVersionFile) -and (Test-Path $stagedVersionFile)) {
    $script:SameVersion = ((Get-Content $installedVersionFile -TotalCount 1) -eq (Get-Content $stagedVersionFile -TotalCount 1))
}
if ($script:SameVersion) {
    Write-Host "NOTE: kit '$Team' is already at the staged version -- re-applying managed files/roles only. This does NOT resolve .claude/kit_update_pending.* merge tasks (work through them and DELETE the file)." -ForegroundColor Yellow
}

if (-not $Rollback) { Write-Host "Scaffolding team '$Team' into $repo" -ForegroundColor Cyan }

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

function Get-FileSha256 {
    param([string]$Path)
    # .NET directly instead of Get-FileHash: the cmdlet resolves via PSModulePath auto-loading,
    # which breaks when a pwsh parent (e.g. a CI runner or a pwsh terminal) hands its PS7 module
    # path to this Windows-PowerShell child — a real run failed with CommandNotFoundException.
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $stream = [IO.File]::OpenRead($Path)
        try { return ([BitConverter]::ToString($sha.ComputeHash($stream)) -replace '-', '') }
        finally { $stream.Dispose() }
    } finally { $sha.Dispose() }
}

function Get-NormalizedSha256 {
    param([string]$Path)
    # SHA256 over the file's bytes with every CR (0x0D) removed, so a project copy that differs from
    # the kit template ONLY in line-ending style is not read as a divergence: a Windows/OneDrive
    # checkout drifts LF->CRLF and every script then read as "differs" and landed on the pending list
    # though its content was the kit's own (BUG-0068). Matches the .sh twin's `tr -d '\r'`.
    $bytes = [IO.File]::ReadAllBytes($Path)
    $filtered = [System.Collections.Generic.List[byte]]::new($bytes.Length)
    foreach ($b in $bytes) { if ($b -ne 0x0D) { $filtered.Add($b) } }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($filtered.ToArray())) -replace '-', '') }
    finally { $sha.Dispose() }
}

function Assert-SafeRepoPath {
    param([string]$Path)
    # A CONTROLLED PATH NAMES NO `..`. `GetFullPath` below already refuses a word that RESOLVES out
    # of the repository, so this adds the one case it accepts: a parent step that happens to come
    # back inside. It is here so the two twins refuse the same PARENT STEP -- the .sh carries the
    # argument and the measurement (a `../victim.txt` line in a snapshot's RESTORE_SET), and also
    # the measured limit: an ABSOLUTE word is answered differently by the two twins, and here it
    # aborts the run through `GetFullPath` rather than through this refusal (`H88`).
    if ($Path -match '(^|[\\/])\.\.([\\/]|$)') {
        throw "Controlled scaffold path escapes the repository: $Path"
    }
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

# WHAT AN INSTALL PUTS BACK WHEN IT IS UNDONE, and why it is not the same set it BACKS UP -- the
# .sh twin carries the argument at the same place. `$restorable` is what this installer OWNS;
# `$keptOnly` is backed up and never restored, because both are files it READS and never writes.
# The set is DATA, used by the backup pass, by the manifest inside the snapshot and by the restore.
# `.claude/kit_state.json` is on it because the run REWRITES it: until 2026-09-01 it was neither
# backed up nor restored, so an abort left the NEW bundle's trust hash beside the OLD bundle.
# Measured on the abort path:
# `tools/test_kitupdate.py::test_an_aborted_install_puts_the_trust_record_back_with_the_bundle`.
# Spelled with forward slashes: either twin may be the one that replays a snapshot.
$restorable = @(
    "CLAUDE.md", "AGENTS.md", ".claude/settings.json", ".claude/agents", ".claude/hooks",
    ".claude/kernel", ".claude/skills", ".claude/team_kit_roles.txt",
    ".claude/provider_artifacts.json", ".claude/kit_version", ".claude/kit_state.json",
    ".claude/kit_repo_files.json",
    ".codex", ".agents/skills", ".github/hooks", ".github/agents")
$keptOnly = @("AGENTS.override.md", ".claude/settings.local.json")

function Test-RepoRelativeName {
    # IS THIS MANIFEST LINE A REPO-RELATIVE NAME SEQUENCE -- the POSIX twin carries the argument and
    # the measurement of what the two twins did with a rooted word before 2026-09-12 (this one: rc 1
    # through an unhandled GetFullPath exception, no sentence). Segments are judged, spellings are
    # not enumerated: every segment is a plain NAME, so nothing empty, nothing `.` or `..`, and no
    # character a path parser of either platform reads as a root or a separator.
    param([string]$Line)
    if ($Line -match '[\\:]') { return $false }
    $segments = $Line -split "/"
    if ($segments.Count -eq 0) { return $false }
    foreach ($part in $segments) {
        if (-not $part -or $part -eq "." -or $part -eq "..") { return $false }
    }
    return $true
}

function Restore-FromSnapshot {
    param([string]$Snapshot, [string[]]$Paths)
    foreach ($relative in $Paths) {
        $native = $relative.Replace("/", [IO.Path]::DirectorySeparatorChar)
        $target = Join-Path $repo $native
        $saved = Join-Path $Snapshot $native
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        if (Test-Path -LiteralPath $saved) {
            $parent = Split-Path -Parent $target
            if ($parent -and -not (Test-Path -LiteralPath $parent)) {
                New-Item -ItemType Directory -Force -Path $parent | Out-Null
            }
            Copy-Item -LiteralPath $saved -Destination $target -Recurse -Force
        }
    }
}

$providerPython = Get-Command python -ErrorAction SilentlyContinue
if (-not $providerPython) { $providerPython = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $providerPython) { throw "Python 3.8+ with PyYAML is required to validate provider configuration." }
# No stderr redirect: under EAP=Stop, 2>$null on a native command turns stderr into a
# terminating NativeCommandError and the friendly message below becomes unreachable.
& $providerPython.Source -c "import importlib.util, sys; sys.exit(0 if (sys.version_info >= (3, 8) and importlib.util.find_spec('yaml')) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.8+ with PyYAML is required to validate provider configuration." }

# FROM THIS SCRIPT'S OWN DIRECTORY, not from the staging the kit sits in -- the same source
# `gen_provider_artifacts.py` and `preset_config.py` are taken from. What this reads is the
# PROJECT, so the reader belongs to the installer that is running; `write_kit_state.py` is the
# opposite case and says so where it is started.
$preflightSource = @'
import sys
from kernel import kitupdate
sys.exit(kitupdate.preflight_cli(sys.argv[1:]))
'@
function Invoke-Preflight {
    param([string[]]$Extra = @())
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = $PSScriptRoot
    try {
        & $providerPython.Source -B -c $preflightSource $repo $kit @Extra
        $code = $LASTEXITCODE
    } finally {
        $env:PYTHONPATH = $previousPythonPath
    }
    if ($code -ne 0) { exit $code }
}

if ($Rollback) {
    # THE PIN IS ASKED HERE TOO, and it is the whole reason this branch is not the first thing the
    # script does: a rollback replaces the installed bundle exactly as an update does. Until
    # 2026-09-01 it sat in front of every check, and a pinned project could be rolled back to a
    # bundle its own pin then refused to update OR repair.
    Invoke-Preflight @("rollback")
    # ROLLBACK (FR-0041): replay the bundle the LAST install replaced. Newest snapshot by name --
    # the stamps are `yyyyMMdd-HHmmss` plus a collision suffix, so lexical order is chronological
    # -- and only one carrying its own RESTORE_SET is a candidate: in an older snapshot, which
    # paths the installer OWNED is exactly what nobody recorded.
    $backups = Join-Path $repo ".claude\backups"
    $chosen = $null
    if (Test-Path -LiteralPath $backups) {
        foreach ($candidate in (Get-ChildItem -LiteralPath $backups -Directory | Sort-Object Name -Descending)) {
            if (Test-Path -LiteralPath (Join-Path $candidate.FullName "RESTORE_SET")) {
                $chosen = $candidate
                break
            }
        }
    }
    if (-not $chosen) {
        throw "No snapshot under .claude/backups/ carries a RESTORE_SET, so there is no previous bundle this installer can replay; nothing was changed. Snapshots written before 2026-09-01 do not record which paths the installer owned -- restore those by hand."
    }
    Assert-NoReparseTree $chosen.FullName
    # EVERY LINE IS JUDGED BEFORE THE FIRST ONE IS ACTED ON -- the POSIX twin carries the argument
    # and the measurements; what stands here is the same rule in this spelling. A line passes if
    # this installer OWNS it (`$restorable`) or the snapshot HOLDS A COPY of it; only a line that is
    # neither is refused, because `Restore-FromSnapshot` deletes a target before it looks for a
    # saved copy and a foreign manifest would use that to delete a file with nothing to put back.
    #
    # READ AS UTF-8 WITH BOM DETECTION, and this half is a PIN rather than a fix -- said so because
    # the POSIX twin's matching comment describes a real defect and this one does not. THIS twin is
    # also the one that WRITES the mark (its own RESTORE_SET starts with `efbbbf`, measured
    # 2026-09-02), and `Get-Content` happened to strip it, so the BOM never hurt here: with the
    # strip removed this reader still replayed the first path at rc 0. What it hurt was the POSIX
    # twin replaying THIS twin's snapshot. `ReadAllText` states the decoding instead of inheriting a
    # `Get-Content` default that differs between PowerShell editions, so the two twins now answer a
    # BOM by the same stated rule rather than by two defaults that happen to agree.
    $setPaths = @()
    $foreign = @()
    $rooted = @()
    $kept = @()
    $manifestText = [IO.File]::ReadAllText((Join-Path $chosen.FullName "RESTORE_SET"))
    foreach ($line in ($manifestText -split "`r?`n")) {
        $entry = $line.Trim()
        if (-not $entry -or $entry.StartsWith("#")) { continue }
        if (-not (Test-RepoRelativeName $entry)) { $rooted += $entry; continue }
        $native = $entry.Replace("/", [IO.Path]::DirectorySeparatorChar)
        Assert-SafeRepoPath (Join-Path $repo $native)
        # A KEPT_ONLY PATH IN A MANIFEST IS NOT AN OWNERSHIP QUESTION -- the POSIX twin carries the
        # argument and the measurement (both twins rc 0, the user's file replaced by the snapshot's
        # copy). The backup pass copies these files, so "the snapshot holds a copy" is true of them
        # and was the half that let them through.
        if ($keptOnly -contains $entry) { $kept += $entry; continue }
        if (($restorable -notcontains $entry) -and
            -not (Test-Path -LiteralPath (Join-Path $chosen.FullName $native))) {
            $foreign += $entry
        }
        $setPaths += $entry
    }
    if ($rooted.Count -gt 0) {
        throw "This snapshot's RESTORE_SET names path(s) that are not repo-relative names: $($rooted -join ', '). A manifest line this installer writes is a sequence of plain names under the repository, and a word carrying its own root is read differently by the two launchers, so replaying it is not one operation. Nothing was changed; report where this snapshot came from rather than retrying."
    }
    if ($kept.Count -gt 0) {
        throw "This snapshot's RESTORE_SET names file(s) this installer backs up and never writes: $($kept -join ', '). They are yours, not the bundle's; putting the snapshot's copy back would overwrite an edit this installer never made. Nothing was changed; take the copy out of .claude/backups/ by hand if you want the old one."
    }
    if ($foreign.Count -gt 0) {
        throw "This snapshot's RESTORE_SET names path(s) this installer does not own and did not save a copy of: $($foreign -join ', '). Replaying it would DELETE them with nothing to put back, so nothing was changed. A manifest written by this installer names only paths it backs up; report where this snapshot came from rather than retrying."
    }
    Restore-FromSnapshot $chosen.FullName $setPaths
    Write-Host "  [rollback] replayed .claude/backups/$($chosen.Name) ($($setPaths.Count) recorded path(s))" -ForegroundColor Yellow
    # The transition this project announced has been undone, so the announcement goes with it; the
    # RESTART marker is raised for the reason a fresh install raises it -- the bundle under the
    # running session just changed again, and only a session start reads the new one.
    $updatedFrom = Join-Path $repo ".claude\kit_updated_from"
    if (Test-Path -LiteralPath $updatedFrom) { Remove-Item -LiteralPath $updatedFrom -Force }
    $claudeDir = Join-Path $repo ".claude"
    if (-not (Test-Path -LiteralPath $claudeDir)) { New-Item -ItemType Directory -Force -Path $claudeDir | Out-Null }
    @(
        "# agents-and-skills handover marker (BUG-0016, DEC-0032)",
        "# A ROLLBACK replayed .claude/backups/$($chosen.Name) over team '$Team'. Until the next restart the",
        "# global handover guard refuses product-code writes and further derivation in this session.",
        "# A SessionStart(startup) hook clears this file on the next real restart. Safe to delete."
    ) | Set-Content -LiteralPath (Join-Path $claudeDir "HANDOVER_PENDING") -Encoding utf8
    # WHAT IT DID NOT PUT BACK, derived rather than claimed: everything under .claude/ that is not
    # one of the recorded paths. Naming them is the difference between a rollback and a promise.
    $recorded = @($setPaths | ForEach-Object { $_.ToLowerInvariant() })
    $untouched = @()
    foreach ($entry in (Get-ChildItem -LiteralPath $claudeDir -Force)) {
        if ($entry.Name -eq "backups") { continue }
        if ($recorded -contains (".claude/" + $entry.Name).ToLowerInvariant()) { continue }
        $untouched += ".claude/" + $entry.Name
    }
    if ($untouched.Count -gt 0) {
        Write-Host "  [rollback] left as they are (not part of the recorded set): $($untouched -join ' ')" -ForegroundColor Yellow
    }
    Write-Host "Rollback done. RESTART the session -- the replayed hooks and agents only load at session start." -ForegroundColor Cyan
    exit 0
}

$cfg = Join-Path $repo "project_memory\project_config.yaml"
if (-not (Test-Path $cfg)) {
    throw "project_memory/project_config.yaml is required before scaffolding; no files were changed."
}
Assert-SafeRepoPath $cfg
Assert-NoReparseTree $kit -AllowOutsideRepo
foreach ($relative in @(
        "AGENTS.md", "CLAUDE.md", "AGENTS.override.md", ".claude\settings.json",
        ".claude\agents", ".claude\hooks", ".claude\kernel", ".claude\skills", ".claude\team_kit_roles.txt",
        ".claude\provider_artifacts.json", ".claude\kit_repo_files.json",
        ".claude\settings.local.json", ".claude\kit_version", ".claude\backups",
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
& $providerPython.Source "$PSScriptRoot\gen_provider_artifacts.py" --repo $repo --project-config $cfg --check-config-only
if ($LASTEXITCODE -ne 0) { throw "Invalid provider configuration; no scaffold files were changed." }
# PRE-FLIGHT (FR-0044/II.12): WHICH STOCK lies here, and may it be written over at all? It runs
# before the first file moves and after the checks that own a FILE of their own -- the config's
# existence and its provider block. Both orders are safe (each refuses and writes nothing), and the
# order is decided by which message a reader can act on: a `project_config.yaml` that does not parse
# is that check's finding, not a sentence about V1 backlog records. That this does not cost the V1
# verdict is measured rather than assumed -- all three field copies under C:/Offline Repos/v2-pilot
# carry a pre-kernel config and all three PASS `--check-config-only` (rc 0, 2026-09-02), so the
# stock verdict is still what they meet. After the snapshot there is a way back; after the
# enforcement layer has been replaced over a state no command can read there is none. The verdict,
# the refusals and the fail-closed rule live in `kernel.kitupdate.preflight_cli`; this line only
# starts it, so the two twins cannot come to classify a project differently.
Invoke-Preflight

# THE STAGING HAS TO CARRY ITS OWN TRUST RECORDER, and this is asked BEFORE anything is copied.
# `write_kit_state.py` is what vouches for the installed hook bundle, and it is also one of
# `kernel.hashing.kit_hash_inputs` -- so a staging without it installed green on a warning nobody
# reads (`hook_trust: unverified`) while every later stamp comparison refused the SAME staging by
# the hash. Measured 2026-09-11 (BUG-0277): rc 0 on the first install for all three kits,
# `request-approval kit_update` then refused it with "does not hash to the content in its own
# VERSION". A first install that cannot be vouched for is not a first install this scaffold makes.
$recorderSource = Join-Path (Split-Path -Parent $kit) "write_kit_state.py"
if (-not (Test-Path -LiteralPath $recorderSource)) {
    throw "$recorderSource is missing, so nothing could vouch for the installed hook bundle and every later kit-update check would refuse this same staging by its hash. Nothing was changed. Remedy: re-install the harness from a complete store (install.ps1)."
}
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
foreach ($relative in ($restorable + $keptOnly)) {
    $native = $relative.Replace("/", [IO.Path]::DirectorySeparatorChar)
    Backup-Local (Join-Path $repo $native) $native
}
if (Test-Path $bdir) {
    # The snapshot carries its OWN restore contract, so a rollback months later replays the set the
    # run that made it owned rather than today's.
    $restorable | Set-Content -LiteralPath (Join-Path $bdir "RESTORE_SET") -Encoding utf8
    Write-Host "  [ok] backed up existing team files -> .claude/backups/$stamp" -ForegroundColor Green
}
if (Test-Path -LiteralPath (Join-Path $repo "AGENTS.override.md")) {
    throw "Repository AGENTS.override.md takes precedence over the team constitution. It was backed up and left untouched; merge/remove it only after explicit user review, then rerun scaffolding."
}

function Restore-ScaffoldSnapshot {
    # THE RUN'S OWN SET, not a second copy of it: `$restorable` is what was backed up above and what
    # the snapshot's RESTORE_SET records, so an abort undoes exactly the paths this run owns.
    Restore-FromSnapshot $bdir $restorable
}

# Treat the Claude base plus all generated provider artifacts as one logical layer. Any normal
# failure before provider generation completes restores the snapshot byte for byte OVER THE PATHS
# THIS INSTALLER OWNS (`$restorable`) -- not over the whole project: records the run writes outside
# that set (the update markers, the pending lists) stay where the failed run left them.
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
            # DEC-0039: the same shim/constitution FORM every marker reader uses (session_status,
            # validate.py) -- the marker only counts anchored on line 1 as `<!-- ... -->` with
            # nothing after it, never as a bare occurrence a quote/prose/negation could carry.
            $marker = [regex]::Match([string]$firstLine,
                '^\s*<!--\s*agents-and-skills:team-kit\s+([A-Za-z0-9_-]+)\s*-->\s*$')
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
    # Kit sources carry provider-neutral tier aliases (`model_tiers.yaml` `aliases:`); the INSTALLED Claude
    # frontmatter needs the concrete reference-platform name (model_map stamping may override).
    # Lookahead keeps the original line ending (no mixed CRLF/LF after the rewrite).
    $agentRaw = [IO.File]::ReadAllText($agentDstPath)
    $agentResolved = (($agentRaw -replace '(?m)^model:[ \t]*lead(?=\s*$)', 'model: opus') `
        -replace '(?m)^model:[ \t]*worker(?=\s*$)', 'model: sonnet')
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
            # tier aliases (team-kits/model_tiers.yaml `aliases:`): map may say lead/worker —
            # Claude agent frontmatter gets the concrete reference-platform name.
            switch ($val) { "lead" { $val = "opus" } "worker" { $val = "sonnet" } }
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
    # ...AND REMOVE WHAT THIS KIT DOES NOT SHIP, which the copy loop alone never did. `.claude/hooks`
    # is `sys.path[0]` for every gate process, so a file an EARLIER kit left there is not clutter:
    # it is a module the harness installed and no longer controls, and `write_kit_state.py` now
    # refuses to record trust over anything importable that the kit did not deliver. Without this
    # prune the first release to drop a hook (`auto_dashboard.py`, in the V2 monolith) would make
    # every project installed before it un-scaffoldable. `.claude/kernel` needs no equivalent — it
    # is deleted and re-copied wholesale just below. The previous contents were backed up above.
    Get-ChildItem -Path $hooksDst -Force |
        Where-Object { -not (Test-Path -LiteralPath (Join-Path $hooksSrc $_.Name)) } |
        ForEach-Object {
            Remove-Item $_.FullName -Recurse -Force
            Write-Host "  [prune] .claude/hooks/$($_.Name) (not shipped by '$Team')" -ForegroundColor Yellow
        }
}
# ...and the V2 state kernel the hooks import. `_kernel.kernel_parents()` names `<repo>/.claude`
# as the FIRST place it looks and says why: a project must run the kernel its hook bundle was
# installed with, not whatever version happens to sit in the global staging. Nothing copied it
# there, so that first candidate never existed and every project silently fell through to
# ~/.claude/team-kits -- or, on a machine without it, got KernelUnavailable from every integrity
# gate. It also carries `known_holes.json`, which `python scripts/harness.py doctor` needs to report any capability
# as verified at all.
$kernelSrc = Join-Path (Split-Path -Parent $kit) "kernel"
if (Test-Path $kernelSrc) {
    $kernelDst = Join-Path $repo ".claude\kernel"
    if (Test-Path $kernelDst) { Remove-Item $kernelDst -Recurse -Force }
    Copy-Item $kernelSrc $kernelDst -Recurse -Force
    Write-Host "  [ok] .claude/kernel (V2 state kernel)" -ForegroundColor Green
}
# THE INSTALLED BUNDLE CARRIES NO TOOL LEFTOVERS. `.claude/hooks` and `.claude/kernel` are what
# `hook_bundle_hash` measures, byte for byte and with nothing excluded -- a `.pyc` there is not a
# cache but an importable module on `sys.path[0]` of every gate process, and a cache directory is a
# file the recorder would bless although no kit stamp covers it. `kit_hash` may leave both out of
# what a KIT contains only because no kit ships any, so this prune is what makes that true at the
# one moment source becomes installation. Afterwards, anything of the kind found under those two
# directories is a stranger, and `write_kit_state.py` reports it as one.
#
# The kernel decides WHAT a leftover is (`kernel.hashing.prune_transient`, the same predicate
# `_shipped_files` excludes by) and both scaffolds call it, so the two platforms cannot prune
# different sets -- the shell twins did, and only this one was ever executed by a test.
#
# Guarded by the same condition as the copy above, and for the recorder's reason: a staging too old
# to carry a kernel installs none, so nothing hashes this bundle and nothing records trust for it.
# Refusing the whole scaffold there would break the update path off such a staging instead of
# leaving `hook_trust` unverified, which is the fail-closed direction.
if (Test-Path $kernelSrc) {
    & $providerPython.Source -B -c "import sys; sys.path.insert(0, sys.argv[1]); from kernel.hashing import prune_transient; prune_transient(*sys.argv[2:])" (Split-Path -Parent $kit) (Join-Path $repo ".claude\hooks") (Join-Path $repo ".claude\kernel")
    if ($LASTEXITCODE -ne 0) { throw "Could not prune tool leftovers out of the installed bundle" }
}
# Role skills travel with the team. Their `skills:` frontmatter REGISTERS them for the role;
# it does not inject them -- measured 2026-08-02 for a role bound as the session agent, and
# unmeasured for the subagent-spawn path (tools/provider_observations.json). Each agent file
# names the retrieval route, which is why the skill directory has to be installed at all.
#
# A SKILL DIRECTORY WHOSE NAME IS NO ROLE OF THIS KIT BELONGS TO EVERY PRESET -- see the POSIX twin
# for the measurement (H83): the preset filter is a ROLE filter, and a reference skill belongs to no
# role by construction (constitution 1a), so it was dropped from every preset but `team`.
if (Test-Path $skillsSrc) {
    if (-not (Test-Path $skillsDst)) { New-Item -ItemType Directory -Force -Path $skillsDst | Out-Null }
    Get-ChildItem -Path $skillsSrc -Directory | ForEach-Object {
        $isRole = Test-Path -LiteralPath (Join-Path $agentsSrc "$($_.Name).md")
        if ($isRole -and $presetRoles -and $_.Name -ne $lead -and $presetRoles -notcontains $_.Name) { return }
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
# BEFORE overwriting, preserve the PREVIOUS version in a one-shot marker: the "KIT UPDATED x->y"
# announcement is consumed by the NEXT SessionStart — a mid-session update used to lose it
# entirely when no clean restart followed (audit: a live repo sat two days without the banner).
$verSrc = Join-Path $kit "VERSION"
if (Test-Path $verSrc) {
    $kvDst = Join-Path $repo ".claude\kit_version"
    $newV = (Get-Content $verSrc -TotalCount 1)
    if (Test-Path $kvDst) {
        $oldV = (Get-Content $kvDst -TotalCount 1)
        $markerDst = Join-Path $repo ".claude\kit_updated_from"
        # never overwrite an unconsumed marker: two scaffolds without a SessionStart in between
        # must announce the EARLIEST from-version, not lose the first transition (audit)
        if ($oldV -and $oldV -ne $newV -and -not (Test-Path $markerDst)) {
            Set-Content -Path $markerDst -Value $oldV -Encoding utf8
        }
    }
    Copy-Item $verSrc $kvDst -Force
    Write-Host "  [ok] .claude/kit_version ($newV)" -ForegroundColor Green
}

# Record WHICH hook bundle this project now carries -- the value `python scripts/harness.py doctor` measures
# `hook_trust` against. Nothing wrote it before, so that comparison had no counterpart and
# `enforcement: hard` was unreachable for a reason nobody could act on. State is
# `restart_required`: the hooks installed above are not running in the session that ran this
# script, and only kit_trust_state.py (a SessionStart hook) may flip it to `active`.
$kitStateVersion = ""
if (Test-Path $verSrc) { $kitStateVersion = (Get-Content $verSrc -TotalCount 1) }
# Invoked from the STAGING this scaffold installed from, not from $PSScriptRoot. The recorder
# compares the installed bundle against the kit files sitting beside itself and takes no path from
# its caller -- a `--kit-root` flag was tried and became a one-flag way to bless any tampering, by
# pointing the "source" at the installation. Running the staging's own copy makes the two agree by
# construction. A staging too old to carry the recorder simply records nothing, which leaves
# `hook_trust` unverified: the fail-closed direction.
$recorder = Join-Path (Split-Path -Parent $kit) "write_kit_state.py"
if (Test-Path -LiteralPath $recorder) {
    & $providerPython.Source $recorder --repo $repo --kit $Team --kit-version $kitStateVersion
    if ($LASTEXITCODE -ne 0) { throw "Could not record the installed hook bundle; backups are under $bdir" }
} else {
    Write-Host "  [warn] $recorder is missing -- no hook-bundle trust recorded (``python scripts/harness.py doctor`` will report hook_trust: unverified)" -ForegroundColor Yellow
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
# WHICH repo scripts the KIT owns (always overwritten, never copy-if-absent, never pending) is DATA,
# not a list in this file: `repo_kit_owned.txt` beside this script, read by BOTH scaffold twins so
# the .ps1 and .sh sets cannot drift. WHY a file is on it is written beside each entry in that
# file's header -- the guarded enforcement scripts (no other route can deliver a kit fix to them,
# BUG-0068), the entry point, the check tooling, the money reader (BUG-0072) -- and that header is
# the authority, not this comment.
$kitOwned = @()
$kitOwnedFile = Join-Path $kitsRoot "repo_kit_owned.txt"
if (Test-Path $kitOwnedFile) {
    $kitOwned = Get-Content $kitOwnedFile | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') }
}
$keptList = @()
$shippedList = [System.Collections.ArrayList]@()
$repoTplSrc = Join-Path $kit "templates\repo"
if (Test-Path $repoTplSrc) {
    Get-ChildItem -Path $repoTplSrc -Recurse -File -Force | Where-Object { $_.FullName -notmatch '__pycache__|\.ruff_cache|\.mypy_cache|\.pytest_cache' } | ForEach-Object {
        $rel = $_.FullName.Substring($repoTplSrc.Length).TrimStart('\', '/')
        # WHAT THE KIT PLACES OUTSIDE `.claude/`, recorded where it is placed (BUG-0265). One line
        # at the TOP of the loop rather than one per branch: the kit-owned branch returns, so a
        # per-branch append is three places that can drift from the walk.
        [void]$shippedList.Add(($rel -replace '\\', '/'))
        $dst = Join-Path $repo $rel
        if (($rel -replace '\\', '/') -in $kitOwned) {
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
        # DIVERGENCE IGNORES LINE-ENDING STYLE (Get-NormalizedSha256): a Windows/OneDrive checkout
        # drifts LF->CRLF, and comparing raw bytes then read EVERY script as "differs" and sent it to
        # the pending list though its content was the kit's own (BUG-0068).
        } elseif ((Get-NormalizedSha256 $dst) -ne (Get-NormalizedSha256 $_.FullName)) {
            # copy-if-absent keeps the project's version — but say so, or a kit fix (e.g. quality.py)
            # silently never reaches existing projects while the update reads as "applied".
            Write-Host "  [kept] repo: $rel (differs from the kit template - review/merge manually)" -ForegroundColor Yellow
            $keptList += ($rel -replace '\\', '/')
        }
    }
}
# THE RECORD ITSELF (BUG-0265). `.claude/provider_artifacts.json` is the shape: a manifest the
# PROJECT holds, so a reader asks the installation instead of carrying a directory name. Until it
# existed, `kernel.report.installed_kit_paths` could only exclude the DIRECTORIES a kit fills
# (`scripts/`, `tools/`) -- which also excluded a project's own script lying beside the kit's, and
# no finding said so. Written unconditionally, empty list included: "no file" and "no entries"
# print the same and mean the opposite things, and the reassuring one would be the wrong default.
# WRITTEN BY THE INTERPRETER, in both twins, and that is not tidiness: `ConvertTo-Json` on Windows
# PowerShell 5.1 unwraps a one-element array into a scalar and writes a BOM, so the two twins would
# hand a reader two different documents for the same installation. The source below is BYTE-
# IDENTICAL with the .sh twin's and carries neither a double quote nor a backslash, because this
# call passes it to a native executable: the first cut reached `python` as
# `open(sys.argv[1], w, encoding=utf-8, newline=\n)` and died on a SyntaxError -- measured, and
# walked past with exit code 0, which is why the status is checked here.
$repoFilesWriter = @'
import json, sys
record = json.dumps({'kit': sys.argv[2], 'repo_files': sorted(sys.argv[3:])}, indent=2) + chr(10)
open(sys.argv[1], 'wb').write(record.encode('utf-8'))
'@
& $providerPython.Source -c $repoFilesWriter (Join-Path $repo ".claude\kit_repo_files.json") $Team @($shippedList)
if ($LASTEXITCODE -ne 0) { throw "Could not write .claude/kit_repo_files.json (exit $LASTEXITCODE)" }
Write-Host "  [ok] .claude/kit_repo_files.json ($($shippedList.Count) file(s) this kit places in the project)" -ForegroundColor Green
$pendFile = Join-Path $repo ".claude\kit_update_pending.repo"
$stateFile = Join-Path $repo ".claude\kit_update_pending.state"
if ($keptList.Count -gt 0) {
    $lines = @("# Repo templates this project customised that ALSO changed in kit $Team $((Get-Content (Join-Path $kit 'VERSION') -TotalCount 1 -ErrorAction SilentlyContinue)) (line-ending style ignored) -- the PM works each through the normal loop: merge the wanted kit fix, or record a conscious skip as a decision item (decisions/active/), then DELETE this file. session_status reminds every session until it is gone. Only PROJECT-CUSTOMISABLE templates appear here; the scripts the KIT owns (listed in the installer's repo_kit_owned.txt, each with the reason it is there -- the enforcement layer, the entry point, the money reader) are refreshed by the installer on every run and never land on this list, so nothing here needs a route a session forbids (BUG-0068).")
    $lines += ($keptList | ForEach-Object { "- $_" })
    Set-Content -Path $pendFile -Value $lines -Encoding utf8
    # fresh REAL update -> fresh nag counter; a same-version re-run must NOT reset the
    # escalation (audit: "updating again just to be safe" kept the backlog forever young)
    if ((Test-Path $stateFile) -and -not $script:SameVersion) { Remove-Item $stateFile -Force }
    Write-Host "  [!] $($keptList.Count) diverged repo file(s) -> .claude/kit_update_pending.repo (merge or consciously skip, then delete it)" -ForegroundColor Yellow
} elseif (Test-Path $pendFile) {
    Remove-Item $pendFile -Force
}

# BUG-0016 handover marker (DEC-0032): set it LAST, when the install has otherwise succeeded, so
# the global ~/.claude/hooks/handover_guard.py refuses product-code writes and further derivation
# for the rest of THIS entry session -- the window in which the project hooks just installed are not
# yet active (settings-watcher gap). The project-owned clear_handover_marker.py
# SessionStart(startup) hook deletes it on the next REAL restart; it is safe to delete by hand.
$claudeDir = Join-Path $repo ".claude"
if (-not (Test-Path $claudeDir)) { New-Item -ItemType Directory -Force -Path $claudeDir | Out-Null }
$handoverMarker = @(
    "# agents-and-skills handover marker (BUG-0016, DEC-0032)",
    "# The entry session installed team '$Team' and asked for a restart. Until that restart the",
    "# global handover guard refuses product-code writes and further derivation in this session.",
    "# A SessionStart(startup) hook clears this file on the next real restart. Safe to delete."
)
Set-Content -Path (Join-Path $claudeDir "HANDOVER_PENDING") -Value $handoverMarker -Encoding utf8

Write-Host "Team '$Team' installed locally. RESTART the session (close/reopen, or start a new session in this folder) -- the new agents and the 'agent: $lead' setting only load at session start. After the restart, type anything (e.g. 'weiter') -- nothing is auto-sent, YOU stay in control of the first message; the '$lead' lead then greets you with a one-line status and picks up any draft plan in project_memory/." -ForegroundColor Cyan
Write-Host "NOTE: if a session is ALREADY running in this folder (even suspended at a usage limit), its hooks are live on the new files from this moment -- a real restamp landed mid-session and entangled kit files with build changes. Finish or restart that session before continuing work there." -ForegroundColor Yellow
