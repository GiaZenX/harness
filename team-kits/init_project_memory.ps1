# Create ./project_memory/ from a team kit's templates -- deterministic, copy-if-absent (Windows).
# Usage: init_project_memory.ps1 -Team dev-team
# Run by the entry gate BEFORE scaffolding (and as the PM startup backfill) so the project_memory
# bootstrap is a SCRIPT step, not ~20 files copied by hand. Never overwrites a file that already
# exists, so it is safe to re-run and never clobbers a draft/filled artifact.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Team
)

$ErrorActionPreference = "Stop"
if ($Team -notmatch '^[A-Za-z0-9_-]+$') { throw "Team must match [A-Za-z0-9_-]+" }
$src = Join-Path $env:USERPROFILE ".claude\team-kits\$Team\templates\project_memory"
if (-not (Test-Path $src)) { throw "Templates not found: $src" }

$repo = (Get-Location).Path
$dst = Join-Path $repo "project_memory"

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
        throw "Controlled project-memory path escapes the repository: $full"
    }
    $relative = if ($full -eq $repoFull) { "" } else { $full.Substring($prefix.Length) }
    $current = $repoFull
    foreach ($component in ($relative -split '[\\/]' | Where-Object { $_ })) {
        $current = Join-Path $current $component
        if (Test-ReparsePoint $current) {
            throw "Refusing symlink/junction/reparse path '$current'; project_memory was left untouched."
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
            throw "Refusing symlink/junction/reparse template path '$current'; project_memory was left untouched."
        }
    }
}

function Assert-NoReparseTree {
    param([string]$Path)
    if (Test-ReparsePoint $Path) {
        throw "Refusing symlink/junction/reparse template path '$Path'; project_memory was left untouched."
    }
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $pending = New-Object System.Collections.Generic.Stack[string]
    if ((Get-Item -LiteralPath $Path -Force).PSIsContainer) { $pending.Push($Path) }
    while ($pending.Count -gt 0) {
        foreach ($item in (Get-ChildItem -LiteralPath $pending.Pop() -Force)) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing symlink/junction/reparse template path '$($item.FullName)'; project_memory was left untouched."
            }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
}

Assert-NoReparseComponentsAbsolute $src
Assert-NoReparseTree $src
Assert-SafeRepoPath $dst
$templateFiles = @(Get-ChildItem -LiteralPath $src -Recurse -File -Force | Where-Object { $_.FullName -notmatch '__pycache__' })
foreach ($templateFile in $templateFiles) {
    $relative = $templateFile.FullName.Substring($src.Length).TrimStart('\', '/')
    Assert-SafeRepoPath (Join-Path $dst $relative)
}
foreach ($relative in @(".claude\kit_update_pending.memory", ".claude\kit_update_pending.state")) {
    Assert-SafeRepoPath (Join-Path $repo $relative)
}
if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Force -Path $dst | Out-Null }

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

$copied = 0; $kept = 0
$keptTooling = @()
$templateFiles | ForEach-Object {
    $rel = $_.FullName.Substring($src.Length).TrimStart('\', '/')
    $target = Join-Path $dst $rel
    if (Test-Path $target) {
        $kept++
        # TOOLING files (generator/templates/assets — NOT the user's filled YAML state) may lag behind a
        # newer kit: make that visible so the PM can propose the delta. Filled YAMLs always differ — silent.
        if ($rel -match '\.py$|\.template\.|\.tex$|^reports[\\/]assets[\\/]') {
            if ((Get-FileSha256 $target) -ne (Get-FileSha256 $_.FullName)) {
                Write-Host "  [kept] $rel (tooling differs from the kit template - review/merge manually)" -ForegroundColor Yellow
                $keptTooling += ($rel -replace '\\', '/')
            }
        }
        return
    }   # copy-if-absent: never clobber existing content
    $tdir = Split-Path $target
    if ($tdir -and -not (Test-Path $tdir)) { New-Item -ItemType Directory -Force -Path $tdir | Out-Null }
    Copy-Item $_.FullName $target -Force
    $copied++
}
# Diverged project_memory TOOLING lands in .claude/kit_update_pending.memory (same contract as the
# scaffold's .repo file): printed [kept] lines were shown but never acted on in a real project --
# session_status reminds the PM until every line is merged or consciously skipped and the file is DELETED.
$pendFile = Join-Path $repo ".claude\kit_update_pending.memory"
if ($keptTooling.Count -gt 0) {
    if (-not (Test-Path (Join-Path $repo ".claude"))) { New-Item -ItemType Directory -Force -Path (Join-Path $repo ".claude") | Out-Null }
    $lines = @("# project_memory TOOLING that DIFFERS from kit '$Team' (templates lag behind the kit) -- the PM reviews each against the kit template, merges the kit's fixes (or documents a conscious skip in progress.yaml log:), then DELETES this file. session_status reminds every session until it is gone. Filled YAML state is NOT listed here and is never overwritten.")
    $lines += ($keptTooling | ForEach-Object { "- $_" })
    Set-Content -Path $pendFile -Value $lines -Encoding utf8
    $stateFile = Join-Path $repo ".claude\kit_update_pending.state"
    if (Test-Path $stateFile) { Remove-Item $stateFile -Force }   # fresh update -> fresh nag counter
    Write-Host "  [!] $($keptTooling.Count) diverged tooling file(s) -> .claude/kit_update_pending.memory (merge or consciously skip, then delete it)" -ForegroundColor Yellow
} elseif (Test-Path $pendFile) {
    Remove-Item $pendFile -Force
}
Write-Host "[ok] project_memory/ ready ($copied created, $kept already present) from kit '$Team'." -ForegroundColor Green
