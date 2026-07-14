#!/usr/bin/env bash
# Create ./project_memory/ from a team kit's templates -- deterministic, copy-if-absent (Unix).
# Usage: init_project_memory.sh dev-team
# Run by the entry gate BEFORE scaffolding (and as the PM startup backfill) so the project_memory
# bootstrap is a SCRIPT step, not ~20 files copied by hand. Never overwrites a file that already
# exists, so it is safe to re-run and never clobbers a draft/filled artifact.
set -euo pipefail

TEAM="${1:-}"
if [ -z "$TEAM" ]; then
  echo "Usage: init_project_memory.sh <team>" >&2
  exit 1
fi
if [[ ! "$TEAM" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Team must match [A-Za-z0-9_-]+" >&2
  exit 1
fi

SRC="$HOME/.claude/team-kits/$TEAM/templates/project_memory"
if [ ! -d "$SRC" ]; then
  echo "Templates not found: $SRC" >&2
  exit 1
fi

REPO="$(pwd -P)"
DST="$REPO/project_memory"

assert_safe_repo_path() {
  local target="$1" rel current component
  case "$target" in
    "$REPO") return 0 ;;
    "$REPO"/*) rel="${target#"$REPO"/}" ;;
    *) echo "Controlled project-memory path escapes the repository: $target" >&2; exit 1 ;;
  esac
  current="$REPO"
  local -a parts=()
  IFS='/' read -r -a parts <<< "$rel"
  for component in "${parts[@]}"; do
    [ -n "$component" ] || continue
    current="$current/$component"
    if [ -L "$current" ]; then
      echo "Refusing symlink path '$current'; project_memory was left untouched." >&2
      exit 1
    fi
  done
}

assert_no_symlink_components_absolute() {
  local target="$1" current="" component
  case "$target" in /*) ;; *) echo "Refusing non-absolute template path: $target" >&2; exit 1 ;; esac
  local -a parts=()
  IFS='/' read -r -a parts <<< "$target"
  for component in "${parts[@]}"; do
    [ -n "$component" ] || continue
    current="$current/$component"
    if [ -L "$current" ]; then
      echo "Refusing symlink template path '$current'; project_memory was left untouched." >&2
      exit 1
    fi
  done
}

assert_no_symlink_tree() {
  local target="$1" found=""
  if [ -e "$target" ] || [ -L "$target" ]; then
    found="$(find -P "$target" -type l -print -quit 2>/dev/null || true)"
    if [ -n "$found" ]; then
      echo "Refusing symlink template path '$found'; project_memory was left untouched." >&2
      exit 1
    fi
  fi
}

assert_no_symlink_components_absolute "$SRC"
assert_no_symlink_tree "$SRC"
assert_safe_repo_path "$DST"
template_files=()
while IFS= read -r -d '' source_file; do
  rel="${source_file#"$SRC"/}"
  template_files+=("$rel")
  assert_safe_repo_path "$DST/$rel"
done < <(find -P "$SRC" -type f -not -path '*/__pycache__/*' -print0)
assert_safe_repo_path "$REPO/.claude/kit_update_pending.memory"
assert_safe_repo_path "$REPO/.claude/kit_update_pending.state"
mkdir -p "$DST"

copied=0; kept=0
kept_tooling=()
for rel in "${template_files[@]}"; do
  target="$DST/$rel"
  if [ -e "$target" ]; then
    kept=$((kept + 1))
    # TOOLING files (generator/templates/assets — NOT the user's filled YAML state) may lag behind a
    # newer kit: make that visible so the PM can propose the delta. Filled YAMLs always differ — silent.
    case "$rel" in
      *.py|*.template.*|*.tex|reports/assets/*)
        if ! cmp -s "$SRC/$rel" "$target"; then
          echo "  [kept] $rel (tooling differs from the kit template - review/merge manually)"
          kept_tooling+=("$rel")
        fi ;;
    esac
    continue
  fi   # copy-if-absent: never clobber
  mkdir -p "$(dirname "$target")"
  cp "$SRC/$rel" "$target"
  copied=$((copied + 1))
done
# Diverged project_memory TOOLING lands in .claude/kit_update_pending.memory (same contract as the
# scaffold's .repo file): printed [kept] lines were shown but never acted on in a real project --
# session_status reminds the PM until every line is merged or consciously skipped and the file is DELETED.
PEND="$REPO/.claude/kit_update_pending.memory"
if [ ${#kept_tooling[@]} -gt 0 ]; then
  mkdir -p "$REPO/.claude"
  {
    echo "# project_memory TOOLING that DIFFERS from kit '$TEAM' (templates lag behind the kit) -- the PM reviews each against the kit template, merges the kit's fixes (or documents a conscious skip in progress.yaml log:), then DELETES this file. session_status reminds every session until it is gone. Filled YAML state is NOT listed here and is never overwritten."
    printf -- "- %s\n" "${kept_tooling[@]}"
  } > "$PEND"
  rm -f "$REPO/.claude/kit_update_pending.state"   # fresh update -> fresh nag counter
  echo "  [!] ${#kept_tooling[@]} diverged tooling file(s) -> .claude/kit_update_pending.memory (merge or consciously skip, then delete it)"
else
  rm -f "$PEND"
fi
echo "[ok] project_memory/ ready ($copied created, $kept already present) from kit '$TEAM'."
