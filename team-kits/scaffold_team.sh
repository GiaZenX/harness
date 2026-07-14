#!/usr/bin/env bash
# Scaffold a team kit into the current repository (Unix).
# Usage: scaffold_team.sh dev-team
# Copies the kit's agents into ./.claude/agents/ and its constitution into ./CLAUDE.md.
# project_memory/ is NOT created here — the entry gate creates it deterministically via
# init_project_memory.sh BEFORE scaffolding (the PM startup backfills it the same way if missing).
set -euo pipefail

TEAM="${1:-}"
PRESET="${2:-}"
if [ -z "$TEAM" ]; then
  echo "Usage: scaffold_team.sh <team> [preset]" >&2
  exit 1
fi

KIT="$HOME/.claude/team-kits/$TEAM"
if [ ! -d "$KIT" ]; then
  echo "Team kit not found: $KIT" >&2
  exit 1
fi

REPO="$(pwd)"
echo "Scaffolding team '$TEAM' into $REPO"

# Presets are MECHANICAL (a preset that is only a config comment enforces nothing): with a preset
# argument only that preset's roles (+ the lead) are installed; spawning any other role then fails
# natively (missing agent file) and via guard_agent_spawn. Upgrading = re-run with the larger
# preset (additive) + session restart.
# No preset argument? Take the RECORDED, user-confirmed preset from project_config.yaml — else
# the first kit UPDATE would silently install the full roster and the "mechanical preset"
# guarantee evaporates (the exact inert-preset failure mode this design kills).
PRESET_SOURCE="argument"
if [ -z "$PRESET" ] && [ -f "$REPO/project_memory/project_config.yaml" ] && [ -f "$KIT/presets.yaml" ]; then
  rec="$(sed -n 's/^[ \t]*preset:[ \t]*\([A-Za-z0-9_-]*\).*/\1/p' "$REPO/project_memory/project_config.yaml" | head -n 1)"
  if [ -n "$rec" ]; then PRESET="$rec"; PRESET_SOURCE="project_config.yaml"; fi
fi
PRESET_ROLES=""
if [ -n "$PRESET" ]; then
  PF="$KIT/presets.yaml"
  [ -f "$PF" ] || { echo "Kit '$TEAM' ships no presets.yaml but a preset was given" >&2; exit 1; }
  line="$(grep -E "^${PRESET}[ \t]*:" "$PF" | head -n 1 || true)"
  if [ -z "$line" ]; then
    avail="$(grep -E '^[A-Za-z0-9_-]+[ \t]*:' "$PF" | cut -d: -f1 | tr '\n' ' ')"
    if [ "$PRESET_SOURCE" = "project_config.yaml" ]; then
      echo "  [warn] recorded preset '$PRESET' is not in the kit's presets.yaml (available: $avail) -- installing the full roster"
      PRESET=""
    else
      echo "Unknown preset '$PRESET' for kit '$TEAM'. Available: $avail" >&2
      exit 1
    fi
  else
    val="$(echo "$line" | cut -d: -f2- | sed 's/^[ \t]*//;s/[ \t]*$//')"
    if [ "$val" != "all" ]; then PRESET_ROLES=" $val "; fi
    echo "  [preset $PRESET, from $PRESET_SOURCE] specialist roles: ${PRESET_ROLES:-ALL}"
  fi
fi
LEAD="project-manager"
if [ -f "$KIT/settings/settings.json" ]; then
  l="$(sed -n 's/.*"agent"[ \t]*:[ \t]*"\([^"]*\)".*/\1/p' "$KIT/settings/settings.json" | head -n 1)"
  [ -n "$l" ] && LEAD="$l"
fi
in_preset() { # role -> 0 when it must be installed
  [ -z "$PRESET_ROLES" ] && return 0
  [ "$1" = "$LEAD" ] && return 0
  case "$PRESET_ROLES" in *" $1 "*) return 0 ;; *) return 1 ;; esac
}

# Back up any existing local team files before overwriting (project_memory is left untouched).
STAMP="$(date +%Y%m%d-%H%M%S)"
BDIR="$REPO/.claude/backups/$STAMP"
backup_local() { [ -e "$1" ] || return 0; mkdir -p "$BDIR"; cp -R "$1" "$BDIR/$(basename "$1")"; }
backup_local "$REPO/CLAUDE.md"
backup_local "$REPO/.claude/settings.json"
backup_local "$REPO/.claude/agents"
[ -d "$BDIR" ] && echo "  [ok] backed up existing team files -> .claude/backups/$STAMP"

mkdir -p "$REPO/.claude/agents"
for f in "$KIT"/agents/*.md; do
  [ -e "$f" ] || continue
  role="$(basename "$f" .md)"
  in_preset "$role" || continue
  cp -f "$f" "$REPO/.claude/agents/$(basename "$f")"
  echo "  [ok] agent: $(basename "$f")"
done

# §11 map sync: the scaffold resets agent frontmatter to kit defaults — when the project already
# carries user-confirmed model_map/effort_map, stamp them back DETERMINISTICALLY instead of leaving
# an out-of-sync nag for the PM (a real update regressed a user-approved opus role to sonnet).
CFG="$REPO/project_memory/project_config.yaml"
if [ -f "$CFG" ]; then
  synced=0
  for pair in "model_map:model" "effort_map:effort"; do
    mapname="${pair%%:*}"; field="${pair##*:}"
    while IFS= read -r entry; do
      role="${entry%%=*}"; val="${entry##*=}"
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
    done < <(awk -v m="$mapname" '
        $0 ~ "^"m":[ \t]*(#.*)?$" { inmap=1; next }
        inmap && /^[^ \t]/ { inmap=0 }
        inmap && match($0, /^[ \t]+[A-Za-z0-9_-]+:[ \t]*[A-Za-z0-9_-]+/) {
          line=$0; sub(/^[ \t]+/, "", line); split(line, a, ":")
          key=a[1]; valpart=a[2]; sub(/^[ \t]*/, "", valpart); sub(/[ \t].*$/, "", valpart)
          print key"="valpart
        }' "$CFG")
  done
  [ "$synced" -gt 0 ] && echo "  [ok] re-synced $synced model:/effort: line(s) from project_config.yaml (user-confirmed maps win over kit defaults)"
fi

if [ -f "$KIT/constitution/CLAUDE.md" ]; then
  cp -f "$KIT/constitution/CLAUDE.md" "$REPO/CLAUDE.md"
  echo "  [ok] CLAUDE.md (local constitution)"
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
if [ -d "$KIT/skills" ]; then
  mkdir -p "$REPO/.claude/skills"
  for d in "$KIT"/skills/*/; do
    [ -e "$d" ] || continue
    name="$(basename "$d")"
    in_preset "$name" || continue
    rm -rf "$REPO/.claude/skills/$name"
    cp -R "$d" "$REPO/.claude/skills/$name"
    echo "  [ok] skill: $name"
  done
fi
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
