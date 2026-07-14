#!/usr/bin/env bash
# Scaffold a team kit into the current repository (Unix).
# Usage: scaffold_team.sh dev-team
# Copies the kit's agents into ./.claude/agents/ and its constitution into ./AGENTS.md (+ CLAUDE.md import shim).
# project_memory/ is NOT created here — the entry gate creates it deterministically via
# init_project_memory.sh BEFORE scaffolding (the PM startup backfills it the same way if missing).
set -Eeuo pipefail

TEAM="${1:-}"
PRESET="${2:-}"
if [ -z "$TEAM" ]; then
  echo "Usage: scaffold_team.sh <team> [preset]" >&2
  exit 1
fi

KITS_ROOT="$HOME/.claude/team-kits"
KIT="$KITS_ROOT/$TEAM"
if [ ! -d "$KIT" ]; then
  echo "Team kit not found: $KIT" >&2
  exit 1
fi

REPO="$(pwd)"
echo "Scaffolding team '$TEAM' into $REPO"

assert_safe_repo_path() {
  local target="$1" rel current component
  case "$target" in
    "$REPO") return 0 ;;
    "$REPO"/*) rel="${target#"$REPO"/}" ;;
    *) echo "Controlled scaffold path escapes the repository: $target" >&2; exit 1 ;;
  esac
  current="$REPO"
  local -a parts=()
  IFS='/' read -r -a parts <<< "$rel"
  for component in "${parts[@]}"; do
    [ -n "$component" ] || continue
    current="$current/$component"
    if [ -L "$current" ]; then
      echo "Refusing symlink path '$current'; no scaffold files were changed." >&2
      exit 1
    fi
  done
}

assert_no_symlink_components_absolute() {
  local target="$1" current="" component
  case "$target" in /*) ;; *) echo "Refusing non-absolute source path: $target" >&2; exit 1 ;; esac
  local -a parts=()
  IFS='/' read -r -a parts <<< "$target"
  for component in "${parts[@]}"; do
    [ -n "$component" ] || continue
    current="$current/$component"
    if [ -L "$current" ]; then
      echo "Refusing symlink path '$current'; no scaffold files were changed." >&2
      exit 1
    fi
  done
}

assert_no_symlink_tree() {
  local target="$1" scope="${2:-repo}" found=""
  if [ "$scope" = "repo" ]; then
    assert_safe_repo_path "$target"
  else
    assert_no_symlink_components_absolute "$target"
  fi
  if [ -e "$target" ] || [ -L "$target" ]; then
    found="$(find -P "$target" -type l -print -quit 2>/dev/null || true)"
    if [ -n "$found" ]; then
      echo "Refusing symlink path '$found'; no scaffold files were changed." >&2
      exit 1
    fi
  fi
}

CFG="$REPO/project_memory/project_config.yaml"
if [ ! -f "$CFG" ]; then
  echo "project_memory/project_config.yaml is required before scaffolding; no files were changed." >&2
  exit 1
fi
if [[ ! "$TEAM" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Team must match [A-Za-z0-9_-]+" >&2
  exit 1
fi
if [ -n "$PRESET" ] && [[ ! "$PRESET" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Preset must match [A-Za-z0-9_-]+" >&2
  exit 1
fi
assert_safe_repo_path "$CFG"
assert_no_symlink_tree "$KIT" outside
for relative in \
  AGENTS.md CLAUDE.md AGENTS.override.md .claude/settings.json .claude/agents \
  .claude/hooks .claude/skills .claude/team_kit_roles.txt .claude/provider_artifacts.json \
  .claude/settings.local.json .claude/kit_version .claude/backups .codex .agents/skills \
  .github/hooks .github/agents; do
  assert_no_symlink_tree "$REPO/$relative"
done
for relative in \
  ".claude/team_kit_roles.txt.tmp.$$" .claude/kit_update_pending.repo \
  .claude/kit_update_pending.state; do
  assert_no_symlink_tree "$REPO/$relative"
done
if [ -d "$KIT/templates/repo" ]; then
  while IFS= read -r -d '' source_file; do
    relative="${source_file#"$KIT/templates/repo"/}"
    assert_no_symlink_tree "$REPO/$relative"
  done < <(find -P "$KIT/templates/repo" -type f -print0)
fi
PYBIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYBIN" ] || ! "$PYBIN" -c 'import sys, yaml; assert sys.version_info >= (3, 8)' 2>/dev/null; then
  echo "Python 3.8+ with PyYAML is required to validate provider configuration." >&2
  exit 1
fi
"$PYBIN" "$(cd "$(dirname "$0")" && pwd)/gen_provider_artifacts.py" \
  --repo "$REPO" --project-config "$CFG" --check-config-only
# settings.local.json: only ENFORCEMENT-replacing keys block the scaffold. `permissions` is
# where Claude Code records every "Always allow" grant and `model` is a legitimate local
# preference — blocking on those made every actively used project unable to take kit updates.
LOCAL_SETTINGS="$REPO/.claude/settings.local.json"
if [ -f "$LOCAL_SETTINGS" ]; then
  if ! local_keys="$("$PYBIN" -c 'import json,sys
d=json.load(open(sys.argv[1], encoding="utf-8-sig"))
assert isinstance(d, dict)
hard = sorted(set(d) & {"agent", "hooks", "disableAllHooks"})
soft = sorted(set(d) & {"model"})
print(",".join(hard) + "|" + ",".join(soft))' "$LOCAL_SETTINGS" 2>/dev/null)"; then
    echo "Invalid .claude/settings.local.json; no scaffold files were changed." >&2
    exit 1
  fi
  local_hard="${local_keys%%|*}"
  local_soft="${local_keys#*|}"
  if [ -n "$local_hard" ]; then
    echo ".claude/settings.local.json overrides enforcement key(s): $local_hard. Remove them (they replace the team's PM/hook layer) before scaffolding; no files were changed." >&2
    exit 1
  fi
  if [ -n "$local_soft" ]; then
    echo "  [warn] .claude/settings.local.json sets $local_soft locally; the team model_map is authoritative -- session_status will flag drift."
  fi
fi

# Presets are MECHANICAL (a preset that is only a config comment enforces nothing): with a preset
# argument only that preset's roles (+ the lead) are installed. Other custom kit roles are absent;
# Claude also blocks them in guard_agent_spawn, while Codex uses lead/specialist exact-role policy
# (provider-native built-ins remain technically available). Upgrading = larger preset + restart.
# No preset argument? Take the RECORDED, user-confirmed preset from project_config.yaml — else
# the first kit UPDATE would silently install the full roster and the "mechanical preset"
# guarantee evaporates (the exact inert-preset failure mode this design kills).
PRESET_SOURCE="argument"
if [ -z "$PRESET" ]; then
  rec="$("$PYBIN" -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1], encoding="utf-8-sig")) or {}; print((d.get("project") or {}).get("preset") or "")' "$CFG")"
  if [ -n "$rec" ]; then PRESET="$rec"; PRESET_SOURCE="project_config.yaml"; fi
fi
[ -n "$PRESET" ] || { echo "Validated project_config.yaml contains no preset; no scaffold files were changed." >&2; exit 1; }
preset_result="$("$PYBIN" "$(cd "$(dirname "$0")" && pwd)/preset_config.py" \
  --kit "$KIT" --preset "$PRESET" --source "$PRESET_SOURCE" --format shell)"
IFS=$'\t' read -r LEAD preset_selection <<< "$preset_result"
[ -n "$LEAD" ] && [ -n "$preset_selection" ] || {
  echo "Preset resolver returned invalid output; no scaffold files were changed." >&2
  exit 1
}
PRESET_ROLES=""
if [ "$preset_selection" != "all" ]; then PRESET_ROLES=" $preset_selection "; fi
echo "  [preset $PRESET, from $PRESET_SOURCE] specialist roles: ${PRESET_ROLES:-ALL}"
in_preset() { # role -> 0 when it must be installed
  [ -z "$PRESET_ROLES" ] && return 0
  [ "$1" = "$LEAD" ] && return 0
  case "$PRESET_ROLES" in *" $1 "*) return 0 ;; *) return 1 ;; esac
}

# Back up any existing local team files before overwriting (project_memory is left untouched).
# Preserve repo-relative paths so .claude/skills and .agents/skills cannot collide in the snapshot.
STAMP_BASE="$(date +%Y%m%d-%H%M%S)"
STAMP="$STAMP_BASE"
BDIR="$REPO/.claude/backups/$STAMP"
stamp_suffix=1
while [ -e "$BDIR" ]; do
  STAMP="$STAMP_BASE-$stamp_suffix"
  BDIR="$REPO/.claude/backups/$STAMP"
  stamp_suffix=$((stamp_suffix + 1))
done
backup_local() {
  [ -e "$1" ] || return 0
  dst="$BDIR/$2"
  mkdir -p "$(dirname "$dst")"
  cp -R "$1" "$dst"
}
backup_local "$REPO/CLAUDE.md" "CLAUDE.md"
backup_local "$REPO/AGENTS.md" "AGENTS.md"
backup_local "$REPO/AGENTS.override.md" "AGENTS.override.md"
backup_local "$REPO/.claude/settings.json" ".claude/settings.json"
backup_local "$REPO/.claude/settings.local.json" ".claude/settings.local.json"
backup_local "$REPO/.claude/agents" ".claude/agents"
backup_local "$REPO/.claude/hooks" ".claude/hooks"
backup_local "$REPO/.claude/skills" ".claude/skills"
backup_local "$REPO/.claude/team_kit_roles.txt" ".claude/team_kit_roles.txt"
backup_local "$REPO/.claude/provider_artifacts.json" ".claude/provider_artifacts.json"
backup_local "$REPO/.claude/kit_version" ".claude/kit_version"
backup_local "$REPO/.codex" ".codex"
backup_local "$REPO/.agents/skills" ".agents/skills"
backup_local "$REPO/.github/hooks" ".github/hooks"
backup_local "$REPO/.github/agents" ".github/agents"
[ -d "$BDIR" ] && echo "  [ok] backed up existing team files -> .claude/backups/$STAMP"
if [ -f "$REPO/AGENTS.override.md" ] || [ -L "$REPO/AGENTS.override.md" ]; then
  echo "Repository AGENTS.override.md takes precedence over the team constitution. It was backed up and left untouched; merge/remove it only after explicit user review, then rerun scaffolding." >&2
  exit 1
fi

restore_scaffold_snapshot() {
  local relative target saved parent
  for relative in \
    CLAUDE.md AGENTS.md .claude/settings.json .claude/agents .claude/hooks .claude/skills \
    .claude/team_kit_roles.txt .claude/provider_artifacts.json .claude/kit_version .codex \
    .agents/skills .github/hooks .github/agents; do
    target="$REPO/$relative"
    saved="$BDIR/$relative"
    if [ -e "$target" ] || [ -L "$target" ]; then rm -rf -- "$target"; fi
    if [ -e "$saved" ] || [ -L "$saved" ]; then
      parent="$(dirname "$target")"
      mkdir -p "$parent"
      cp -R "$saved" "$target"
    fi
  done
}

ROLLBACK_ACTIVE=1
rollback_on_exit() {
  local status=$?
  trap - EXIT
  if [ "$ROLLBACK_ACTIVE" -eq 1 ] && [ "$status" -ne 0 ]; then
    set +e
    restore_scaffold_snapshot
    local rollback_status=$?
    if [ "$rollback_status" -eq 0 ]; then
      echo "  [rollback] restored the previous Claude/Codex provider layer from .claude/backups/$STAMP" >&2
    else
      echo "  [rollback] FAILED; restore manually from $BDIR" >&2
      status=1
    fi
  fi
  exit "$status"
}
trap rollback_on_exit EXIT

AGENTS_SRC="$KIT/agents"
AGENTS_DST="$REPO/.claude/agents"
SKILLS_SRC="$KIT/skills"
SKILLS_DST="$REPO/.claude/skills"
ROLES_MANIFEST="$REPO/.claude/team_kit_roles.txt"

# Remove only files previously owned by the kit. The manifest makes preset downgrades and kit
# switches subtractive without deleting unrelated user agents/skills. The versioned header/count
# makes truncated ownership fail closed instead of silently orphaning spawnable roles.
roles_to_remove=()
if [ -f "$ROLES_MANIFEST" ]; then
  invalid_role_manifest=0
  {
    IFS= read -r role_header || true
    role_header="${role_header%$'\r'}"
    if [[ "$role_header" =~ ^#[[:space:]]agents-and-skills:team-kit-roles[[:space:]]v1[[:space:]]team=[A-Za-z0-9_-]+[[:space:]]count=([0-9]+)$ ]]; then
      expected_roles="${BASH_REMATCH[1]}"
    else
      expected_roles=0
      invalid_role_manifest=1
    fi
    while IFS= read -r role || [ -n "$role" ]; do
      role="${role%$'\r'}"
      if [[ ! "$role" =~ ^[A-Za-z0-9_-]+$ ]]; then
        [ -z "$role" ] || invalid_role_manifest=1
        continue
      fi
      # ${arr[@]+...} guards: expanding an EMPTY array under `set -u` errors on bash < 4.4
      # (macOS ships 3.2), and this script explicitly supports macOS.
      for existing in ${roles_to_remove[@]+"${roles_to_remove[@]}"}; do
        [ "$existing" = "$role" ] && invalid_role_manifest=1
      done
      roles_to_remove+=("$role")
    done
  } < "$ROLES_MANIFEST"
  if [ "$invalid_role_manifest" -ne 0 ] || [ "$expected_roles" -lt 1 ] || \
      [ "${#roles_to_remove[@]}" -ne "$expected_roles" ]; then
    echo "Invalid/truncated .claude/team_kit_roles.txt; no role files were changed (restore its scaffold backup)" >&2
    exit 1
  fi
else
  # Legacy installs predate the ownership manifest. Their constitution marker proves which staged
  # kit owned the old roles. Without that proof, same-named user roles are ambiguous: fail closed.
  legacy_team=""
  for entry_file in "$REPO/AGENTS.md" "$REPO/CLAUDE.md"; do
    [ -z "$legacy_team" ] || break
    [ -f "$entry_file" ] || continue
    IFS= read -r first_line < "$entry_file" || true
    if [[ "$first_line" =~ agents-and-skills:team-kit[[:space:]]+([A-Za-z0-9_-]+) ]]; then
      legacy_team="${BASH_REMATCH[1]}"
    fi
  done
  if [ -n "$legacy_team" ] && [ -d "$KITS_ROOT/$legacy_team/agents" ]; then
    for f in "$KITS_ROOT/$legacy_team"/agents/*.md; do
      [ -e "$f" ] || continue
      roles_to_remove+=("$(basename "$f" .md)")
    done
    echo "  [migration] role ownership recovered from the '$legacy_team' constitution marker"
  else
    ambiguous=()
    known_roles=()
    for f in "$KITS_ROOT"/*/agents/*.md; do
      [ -e "$f" ] || continue
      known_roles+=("$(basename "$f" .md)")
    done
    for role in ${known_roles[@]+"${known_roles[@]}"}; do
      collision=0
      if [ -e "$AGENTS_DST/$role.md" ] || [ -L "$AGENTS_DST/$role.md" ] || \
         [ -e "$SKILLS_DST/$role" ] || [ -L "$SKILLS_DST/$role" ]; then
        collision=1
      fi
      if [ "$collision" -eq 1 ]; then
        already=0
        for item in ${ambiguous[@]+"${ambiguous[@]}"}; do [ "$item" = "$role" ] && already=1; done
        [ "$already" -eq 1 ] || ambiguous+=("$role")
      fi
    done
    if [ "${#ambiguous[@]}" -gt 0 ]; then
      echo "Cannot prove ownership of pre-manifest role artifact(s): ${ambiguous[*]}. Existing files were backed up and left untouched; restore/create a valid .claude/team_kit_roles.txt or move the collisions aside." >&2
      exit 1
    fi
  fi
fi

# Never overwrite a target-preset role unless the manifest/legacy marker proved it kit-owned.
target_roles=()
for f in "$AGENTS_SRC"/*.md; do
  [ -e "$f" ] || continue
  role="$(basename "$f" .md)"
  in_preset "$role" && target_roles+=("$role")
done
target_collisions=()
for role in ${target_roles[@]+"${target_roles[@]}"}; do
  owned=0
  for old_role in ${roles_to_remove[@]+"${roles_to_remove[@]}"}; do [ "$old_role" = "$role" ] && owned=1; done
  if [ "$owned" -eq 0 ] && { [ -e "$AGENTS_DST/$role.md" ] || [ -L "$AGENTS_DST/$role.md" ] || \
       [ -e "$SKILLS_DST/$role" ] || [ -L "$SKILLS_DST/$role" ]; }; then
    target_collisions+=("$role")
  fi
done
if [ "${#target_collisions[@]}" -gt 0 ]; then
  echo "Target role collision(s) are not kit-owned: ${target_collisions[*]}. Existing files were backed up and left untouched; move them aside before scaffolding." >&2
  exit 1
fi
removed_role_artifacts=0
for role in ${roles_to_remove[@]+"${roles_to_remove[@]}"}; do
  old_agent="$AGENTS_DST/$role.md"
  old_skill="$SKILLS_DST/$role"
  if [ -e "$old_agent" ] || [ -L "$old_agent" ]; then
    rm -f "$old_agent"
    removed_role_artifacts=$((removed_role_artifacts + 1))
  fi
  if [ -e "$old_skill" ] || [ -L "$old_skill" ]; then
    rm -rf "$old_skill"
    removed_role_artifacts=$((removed_role_artifacts + 1))
  fi
done
if [ "$removed_role_artifacts" -gt 0 ]; then
  echo "  [ok] removed $removed_role_artifacts previously kit-managed agent/skill artifact(s) before refresh"
fi

mkdir -p "$AGENTS_DST"
installed_specialists=()
for f in "$KIT"/agents/*.md; do
  [ -e "$f" ] || continue
  role="$(basename "$f" .md)"
  in_preset "$role" || continue
  cp -f "$f" "$AGENTS_DST/$(basename "$f")"
  # Kit sources carry provider-neutral tier aliases (lead/worker/light); the INSTALLED Claude
  # frontmatter needs the concrete reference-platform name (model_map stamping may override).
  # CR-tolerant match: agent .md files may be CRLF on a Windows checkout used from WSL/Linux,
  # and non-MSYS awk keeps the \r in $0 (sub() below preserves the original line ending).
  ap="$AGENTS_DST/$(basename "$f")"
  tmp="$ap.tmp"
  awk '{ line=$0; sub(/\r$/, "", line)
         if (line=="model: lead")        sub(/model: lead/, "model: opus")
         else if (line=="model: worker") sub(/model: worker/, "model: sonnet")
         else if (line=="model: light")  sub(/model: light/, "model: haiku")
         print }' "$ap" > "$tmp"
  mv "$tmp" "$ap"
  [ "$role" = "$LEAD" ] || installed_specialists+=("$role")
  echo "  [ok] agent: $(basename "$f")"
done

# §11 map sync: the scaffold resets agent frontmatter to kit defaults — when the project already
# carries user-confirmed model_map/effort_map, stamp them back DETERMINISTICALLY instead of leaving
# an out-of-sync nag for the PM (a real update regressed a user-approved opus role to sonnet).
if [ -f "$CFG" ]; then
  synced=0
  for pair in "model_map:model" "effort_map:effort"; do
    mapname="${pair%%:*}"; field="${pair##*:}"
    while IFS=$'\t' read -r role val; do
      [ -n "$role" ] || continue
      # tier aliases (team-kits/model_tiers.yaml): map may say lead/worker/light — Claude agent
      # frontmatter gets the concrete reference-platform name.
      case "$val" in lead) val="opus" ;; worker) val="sonnet" ;; light) val="haiku" ;; esac
      ap="$REPO/.claude/agents/$role.md"
      [ -f "$ap" ] || continue
      tmp="$ap.tmp"
      awk -v f="$field" -v v="$val" 'BEGIN{done=0}
        !done && $0 ~ "^"f":" { print f": "v; done=1; next } { print }' "$ap" > "$tmp"
      if cmp -s "$tmp" "$ap"; then
        rm -f "$tmp"          # no-op: kit default already matches the map — do not count it
      else
        mv "$tmp" "$ap"
        synced=$((synced + 1))
      fi
    done < <("$PYBIN" -c 'import sys,yaml
d=yaml.safe_load(open(sys.argv[1], encoding="utf-8-sig")) or {}
for role,value in (d.get(sys.argv[2]) or {}).items():
    print(f"{role}\t{value}")' "$CFG" "$mapname")
  done
  [ "$synced" -gt 0 ] && echo "  [ok] re-synced $synced model:/effort: line(s) from project_config.yaml (user-confirmed maps win over kit defaults)"
fi

# Constitution: AGENTS.md is the CANONICAL file (AAIF/Linux-Foundation standard, read natively by
# Codex); CLAUDE.md is a thin import shim because Claude Code reads CLAUDE.md
# only -- @AGENTS.md is Anthropic's documented bridge (verified: main agent AND subagents inherit
# the imported content; the kit marker stays on line 1 for the entry gate + session_status).
if [ -f "$KIT/constitution/AGENTS.md" ]; then
  cp -f "$KIT/constitution/AGENTS.md" "$REPO/AGENTS.md"
  marker="$(head -n 1 "$KIT/constitution/AGENTS.md")"
  printf '%s\n@AGENTS.md\n' "$marker" > "$REPO/CLAUDE.md"
  echo "  [ok] AGENTS.md (constitution) + CLAUDE.md (import shim)"
fi

# Enforcement layer: hooks + settings.json travel with the team.
if [ -d "$KIT/hooks" ]; then
  mkdir -p "$REPO/.claude/hooks"
  for f in "$KIT"/hooks/*; do
    [ -f "$f" ] || continue   # skip directories like __pycache__ (cp -f would error + mislead)
    cp -f "$f" "$REPO/.claude/hooks/$(basename "$f")"
    echo "  [ok] hook: $(basename "$f")"
  done
fi
# Role skills travel with the team (preloaded into the agents via their `skills:` frontmatter).
if [ -d "$SKILLS_SRC" ]; then
  mkdir -p "$SKILLS_DST"
  for d in "$SKILLS_SRC"/*/; do
    [ -e "$d" ] || continue
    name="$(basename "$d")"
    in_preset "$name" || continue
    rm -rf "$SKILLS_DST/$name"
    cp -R "$d" "$SKILLS_DST/$name"
    echo "  [ok] skill: $name"
  done
fi

# Record exactly the role files managed by this installation. The lead is always first; specialists
# are stable and unique so the next refresh can safely remove only kit-owned names.
mkdir -p "$REPO/.claude"
manifest_count=$((1 + ${#installed_specialists[@]}))
roles_manifest_tmp="$ROLES_MANIFEST.tmp.$$"
{
  printf '# agents-and-skills:team-kit-roles v1 team=%s count=%s\n' "$TEAM" "$manifest_count"
  printf '%s\n' "$LEAD"
  if [ "${#installed_specialists[@]}" -gt 0 ]; then
    printf '%s\n' "${installed_specialists[@]}" | sort -u
  fi
} > "$roles_manifest_tmp"
mv -f "$roles_manifest_tmp" "$ROLES_MANIFEST"
echo "  [ok] .claude/team_kit_roles.txt ($manifest_count managed role(s))"

if [ -f "$KIT/settings/settings.json" ]; then
  mkdir -p "$REPO/.claude"
  cp -f "$KIT/settings/settings.json" "$REPO/.claude/settings.json"
  echo "  [ok] .claude/settings.json (session agent + enforcement hooks)"
fi

# POSIX portability (audit finding): standard macOS/Linux ships `python3` only — a hook command
# that fails to LAUNCH is a NON-blocking error, i.e. every gate would silently degrade to a hint.
# Rewrite the copied hook commands (settings + agent frontmatter) to python3 where available.
if command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  for f in "$REPO/.claude/settings.json" "$REPO/.claude/agents/"*.md; do
    [ -f "$f" ] || continue
    sed -i.bak 's/python \(\\\{0,1\}\)"/python3 \1"/g' "$f" && rm -f "$f.bak"
  done
  echo "  [ok] hook commands rewritten to python3 (no plain 'python' on this system)"
fi
# Stamp the installed kit version (session_status compares it with the staged kit to flag updates).
if [ -f "$KIT/VERSION" ]; then
  cp -f "$KIT/VERSION" "$REPO/.claude/kit_version"
  echo "  [ok] .claude/kit_version ($(head -n 1 "$KIT/VERSION"))"
fi

# Extra providers: the same validated project_config drives exact provider generation/removal.
"$PYBIN" "$(cd "$(dirname "$0")" && pwd)/gen_provider_artifacts.py" \
  --repo "$REPO" --project-config "$CFG" --lead "$LEAD"
ROLLBACK_ACTIVE=0
trap - EXIT

# Repo-level quality templates (scripts/quality.py, CI, pre-commit, requirements-dev) -- copy-if-absent
# so DevOps can customise them without a re-scaffold clobbering changes. The merge gate runs quality.py.
# Diverged files additionally land in .claude/kit_update_pending.repo: printed [kept] lines were shown
# but never acted on in a real project (kit fixes silently never arrived) -- session_status now reminds
# the PM until every line is merged or consciously skipped and the file is DELETED.
kept_list=()
if [ -d "$KIT/templates/repo" ]; then
  while IFS= read -r rel; do
    rel="${rel#./}"
    dst="$REPO/$rel"
    # scripts/kit_checks.py is KIT-OWNED: always overwritten (like the hooks), never pending —
    # so kit-level check fixes reach even projects whose quality.py runner is a heavy fork.
    if [ "$rel" = "scripts/kit_checks.py" ]; then
      mkdir -p "$(dirname "$dst")"
      cp -f "$KIT/templates/repo/$rel" "$dst"
      echo "  [ok] repo (kit-owned, always updated): $rel"
      continue
    fi
    if [ ! -e "$dst" ]; then
      mkdir -p "$(dirname "$dst")"
      cp "$KIT/templates/repo/$rel" "$dst"
      echo "  [ok] repo: $rel"
    elif ! cmp -s "$KIT/templates/repo/$rel" "$dst"; then
      # copy-if-absent keeps the project's version — but say so, or a kit fix (e.g. quality.py)
      # silently never reaches existing projects while the update reads as "applied".
      echo "  [kept] repo: $rel (differs from the kit template - review/merge manually)"
      kept_list+=("$rel")
    fi
  done < <(cd "$KIT/templates/repo" && find . -type f -not -path '*/__pycache__/*' \
           -not -path '*/.ruff_cache/*' -not -path '*/.mypy_cache/*' -not -path '*/.pytest_cache/*')
fi
PEND="$REPO/.claude/kit_update_pending.repo"
STATE="$REPO/.claude/kit_update_pending.state"
if [ ${#kept_list[@]} -gt 0 ]; then
  mkdir -p "$REPO/.claude"
  {
    echo "# Repo templates that DIFFER from kit $TEAM $(head -n 1 "$KIT/VERSION" 2>/dev/null) -- the PM reviews each against the kit template, merges the kit's fixes (or documents a conscious skip in progress.yaml log:), then DELETES this file. session_status reminds every session until it is gone."
    printf -- "- %s\n" "${kept_list[@]}"
  } > "$PEND"
  rm -f "$STATE"   # fresh update -> fresh nag counter
  echo "  [!] ${#kept_list[@]} diverged repo file(s) -> .claude/kit_update_pending.repo (merge or consciously skip, then delete it)"
else
  rm -f "$PEND"
fi

echo "Team '$TEAM' installed locally. RESTART the session (close/reopen, or start a new session in this folder) -- the new agents and the 'agent: $LEAD' setting only load at session start. After the restart, type anything (e.g. 'weiter') -- nothing is auto-sent, YOU stay in control of the first message; the '$LEAD' lead then greets you with a one-line status and picks up any draft plan in project_memory/."
echo "NOTE: if a session is ALREADY running in this folder (even suspended at a usage limit), its hooks are live on the new files from this moment -- a real restamp landed mid-session and entangled kit files with build changes. Finish or restart that session before continuing work there."
