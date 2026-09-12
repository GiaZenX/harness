#!/usr/bin/env bash
# Scaffold a team kit into the current repository (Unix).
# Usage: scaffold_team.sh dev-team
# Copies the kit's agents into ./.claude/agents/ and its constitution into ./AGENTS.md (+ CLAUDE.md import shim).
# project_memory/ is NOT created here — the entry gate creates it deterministically via
# init_project_memory.sh BEFORE scaffolding (the PM startup backfills it the same way if missing).
set -Eeuo pipefail

TEAM="${1:-}"
if [ -z "$TEAM" ]; then
  echo "Usage: scaffold_team.sh <team> [preset] [--rollback]" >&2
  exit 1
fi
# The flag is read out of ALL remaining words rather than out of one position: the callers are a
# user typing the line and `kernel.kitupdate.rollback_command`, and a flag that only worked in
# position 2 would make "preset plus rollback" a silent preset named `--rollback`.
PRESET=""
ROLLBACK=0
shift
for argument in "$@"; do
  case "$argument" in
    --rollback) ROLLBACK=1 ;;
    *) PRESET="$argument" ;;
  esac
done

KITS_ROOT="$HOME/.claude/team-kits"
KIT="$KITS_ROOT/$TEAM"
if [ ! -d "$KIT" ]; then
  echo "Team kit not found: $KIT" >&2
  exit 1
fi

REPO="$(pwd)"

# Run a text producer and hand back its records WITHOUT the record terminator. The terminator is
# not part of the record, but only PowerShell's readers act on that: `Get-Content` and
# `ConvertFrom-Json` give the .ps1 twin a bare value, while POSIX word splitting gives this script
# whatever byte precedes the newline. On Windows that byte is CR -- the helpers invoked below are
# CPython, whose TEXT stdout writes os.linesep, and the shell running this file is then Git Bash.
# Measured on a Git-Bash scaffold of office-team before this filter existed: `case "$val" in
# worker)` missed on `worker<CR>`, three of four installed agents kept `model: worker`, and
# session_status.model_effort_mismatches reports exactly that as an unresolved tier alias no
# Claude subagent can spawn on. Filtering where the value is BORN, rather than at each `case`/`read`
# that consumes it, is what stops the next helper added here from re-opening this.
#
# EXACTLY WHAT GOES THROUGH IT, so this comment promises no more than the file does: every PYTHON
# helper whose output becomes a value, and every first line taken from a FILE with `head -n 1`.
# Those are the two producers that can disagree with this shell about where a record ends -- the
# first because it is a Windows-native program, the second because a file can have been written by
# one. `pwd`, `date`, `basename`, `dirname` and `find` are NOT routed through it and do not need to
# be: they are the same POSIX toolchain this script is running in, so their idea of a line
# terminator is this shell's by construction. Two further reads take a line by REDIRECTION rather
# than by substitution and handle CR at the record instead: the roles-manifest loop
# (`role_header`/`role`, `${...%$'\r'}`) and the legacy constitution marker, whose capture class
# cannot include CR.
# A literal CR in the pattern, not a `\r` escape: BSD sed (macOS, which this script supports) does
# not understand `\r`. Only the terminator is dropped, so a CR inside a value stays visible.
CR=$'\r'
BOM=$'\xef\xbb\xbf'   # a byte-order mark is not part of a path -- see the rollback reader
no_cr() { "$@" | sed "s/${CR}\$//"; }

# Same-version detection (audit): a redundant re-run stays ALLOWED (it legitimately re-syncs
# roles to the recorded preset and repairs drifted managed files) but must be LOUD about not
# resolving merge tasks, and must NOT reset the merge-backlog escalation counter (a PM who
# "updated again just to be safe" used to silently restart the nag from session 1).
SAME_VERSION=0
if [ "$ROLLBACK" -eq 0 ] && [ -f "$REPO/.claude/kit_version" ] && [ -f "$KIT/VERSION" ] \
    && [ "$(no_cr head -n 1 "$REPO/.claude/kit_version")" = "$(no_cr head -n 1 "$KIT/VERSION")" ]; then
  SAME_VERSION=1
  echo "NOTE: kit '$TEAM' is already at the staged version -- re-applying managed files/roles only. This does NOT resolve .claude/kit_update_pending.* merge tasks (work through them and DELETE the file)."
fi

if [ "$ROLLBACK" -eq 0 ]; then echo "Scaffolding team '$TEAM' into $REPO"; fi

# A CONTROLLED PATH NAMES NO `..`, and that is a rule about where its words COME FROM rather than
# a normalisation: everything this installer hands to the check below it composed itself out of
# `$REPO` and a name from its own tables, and none of those carries a parent step. Since 2026-09-01
# it is also handed DATA -- the lines of a snapshot's RESTORE_SET -- and that is the reading this
# refusal exists for. Measured 2026-09-01 with `../victim.txt` in a snapshot's manifest: the
# comparison here was TEXTUAL (`case "$target" in "$REPO"/*`), the word matched the prefix, and
# `rm -rf` in the restore deleted a file OUTSIDE the repository at rc 0 -- while the .ps1 twin,
# which resolves through `GetFullPath`, refused the same line. The twins now refuse the same PARENT
# STEP for the same reason (`tools/test_kitupdate.py::test_neither_twin_replays_a_snapshot_that_
# points_out_of_the_repository`).
#
# THEY DO NOT ANSWER AN ABSOLUTE WORD ALIKE, and "no `..`" is an enumeration where the property is
# "a RESTORE_SET line is REPO-RELATIVE". Measured 2026-09-02 with one absolute path in a manifest,
# real installer, both twins: this one reads it as repo-relative (the caller hands over
# `$REPO/$line`), finds nothing under that name in the snapshot and ends at rc 0 with the tree
# unchanged; the .ps1 twin ends at rc 1 -- but on an unhandled `GetFullPath` exception rather than
# through its own refusal. Neither writes outside the repository, so this is a divergence and not
# the deletion above; it stands with that measurement in `H88`.
assert_safe_repo_path() {
  local target="$1" rel current component
  case "$target" in
    "$REPO") return 0 ;;
    "$REPO"/*) rel="${target#"$REPO"/}" ;;
    *) echo "Controlled scaffold path escapes the repository: $target" >&2; exit 1 ;;
  esac
  case "/$rel/" in
    */../*) echo "Controlled scaffold path escapes the repository: $target" >&2; exit 1 ;;
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

# WHAT AN INSTALL PUTS BACK WHEN IT IS UNDONE, and why it is not the same set it BACKS UP.
# `RESTORABLE` is what this installer OWNS: every path it overwrites, prunes or stamps. Those are
# the paths a rollback may replace without destroying somebody else's work, and the paths an
# aborted run must be undone across. `KEPT_ONLY` is backed up and never restored -- both are files
# this installer READS and never writes (a user's local settings, a repository override that stops
# the scaffold), so putting an older copy of one back would overwrite an edit the installer never
# made. The set is DATA here, used three times: the backup pass, the manifest inside the snapshot
# and the restore below, so a path added to it cannot be forgotten by one of the three.
# `.claude/kit_state.json` is on the list because the run REWRITES it (`write_kit_state.py`): until
# 2026-09-01 it was neither backed up nor restored, so an abort after that step restored the old
# bundle and left the NEW bundle's trust hash beside it -- `doctor` then reports `hook_trust`
# against a bundle that is not there. Measured on the ABORT path, which is this list's own path:
# `tools/test_kitupdate.py::test_an_aborted_install_puts_the_trust_record_back_with_the_bundle`.
RESTORABLE=(
  CLAUDE.md AGENTS.md .claude/settings.json .claude/agents .claude/hooks .claude/kernel
  .claude/skills .claude/team_kit_roles.txt .claude/provider_artifacts.json .claude/kit_version
  .claude/kit_state.json .claude/kit_repo_files.json .codex .agents/skills .github/hooks
  .github/agents)
KEPT_ONLY=(AGENTS.override.md .claude/settings.local.json)

in_restorable() { # repo-relative path -> 0 when THIS installer owns it
  local candidate="$1" known
  for known in "${RESTORABLE[@]}"; do
    [ "$known" = "$candidate" ] && return 0
  done
  return 1
}

in_kept_only() { # repo-relative path -> 0 when it is a file this installer READS and never writes
  local candidate="$1" known
  for known in "${KEPT_ONLY[@]}"; do
    [ "$known" = "$candidate" ] && return 0
  done
  return 1
}

# IS THIS MANIFEST LINE A REPO-RELATIVE NAME SEQUENCE -- the shape both twins write and the only
# shape they read ALIKE. A line that carries its own root is not a path into this project, and the
# two launchers do not answer one such word the same way: measured 2026-09-12 with
# `C:/…/victim.txt` in a snapshot's manifest, real installers, this twin came back rc 1 through the
# OWNERSHIP refusal (a sentence about a foreign manifest, which is the wrong reason) while the .ps1
# twin came back rc 1 through an unhandled `GetFullPath` NotSupportedException (no sentence at
# all). Neither wrote outside the project; what neither did was NAME the property. The segments are
# judged rather than the spellings enumerated: every segment is a plain NAME, so nothing empty,
# nothing `.` or `..`, and no character that a path parser of either platform these twins run on
# reads as a root or a separator. `tools/test_hooks.py::test_neither_twin_replays_a_manifest_line_
# that_is_not_the_installers_to_write` holds both ends -- the refusal, and that every path this
# installer itself writes into a manifest passes.
manifest_line_is_a_repo_relative_name() {
  local line="$1" part
  case "$line" in *\\*|*:*) return 1 ;; esac
  local -a segments=()
  IFS='/' read -r -a segments <<< "$line"
  [ "${#segments[@]}" -gt 0 ] || return 1
  for part in "${segments[@]}"; do
    case "$part" in ''|.|..) return 1 ;; esac
  done
  return 0
}

restore_from_snapshot() {
  # $1 = snapshot directory, $2... = the repo-relative paths to put back.
  local snapshot="$1" relative target saved parent
  shift
  for relative in "$@"; do
    target="$REPO/$relative"
    saved="$snapshot/$relative"
    if [ -e "$target" ] || [ -L "$target" ]; then rm -rf -- "$target"; fi
    if [ -e "$saved" ] || [ -L "$saved" ]; then
      parent="$(dirname "$target")"
      mkdir -p "$parent"
      cp -R "$saved" "$target"
    fi
  done
}

PYBIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYBIN" ] || ! "$PYBIN" -c 'import sys, yaml; assert sys.version_info >= (3, 8)' 2>/dev/null; then
  echo "Python 3.8+ with PyYAML is required to validate provider configuration." >&2
  exit 1
fi
# FROM THIS SCRIPT'S OWN DIRECTORY, not from the staging the kit sits in -- the same source
# `gen_provider_artifacts.py` and `preset_config.py` are taken from. What this reads is the
# PROJECT, so the reader belongs to the installer that is running; `write_kit_state.py` is the
# opposite case and says so where it is started.
PREFLIGHT_PATH="$(cd "$(dirname "$0")" && pwd)"
preflight() {
  PYTHONPATH="$PREFLIGHT_PATH" "$PYBIN" -B -c 'import sys
from kernel import kitupdate
sys.exit(kitupdate.preflight_cli(sys.argv[1:]))' "$REPO" "$KIT" "$@" || exit 1
}

if [ "$ROLLBACK" -eq 1 ]; then
  # THE PIN IS ASKED HERE TOO, and it is the whole reason this branch is not the first thing the
  # script does: a rollback replaces the installed bundle exactly as an update does. Until
  # 2026-09-01 it sat in front of every check, and a pinned project could be rolled back to a
  # bundle its own pin then refused to update OR repair.
  preflight rollback
  # ROLLBACK: replay the bundle the LAST install replaced (FR-0041). The snapshot is chosen by
  # name because the stamps are `YYYYmmdd-HHMMSS` plus a collision suffix, so lexical order is
  # chronological; and only a snapshot carrying its own RESTORE_SET is a candidate, because in an
  # older one which paths the installer OWNED is exactly what nobody recorded.
  BACKUPS="$REPO/.claude/backups"
  CHOSEN=""
  if [ -d "$BACKUPS" ]; then
    while IFS= read -r candidate; do
      [ -n "$candidate" ] || continue
      if [ -f "$BACKUPS/$candidate/RESTORE_SET" ]; then CHOSEN="$candidate"; break; fi
    done < <(ls -1 "$BACKUPS" 2>/dev/null | sort -r)
  fi
  if [ -z "$CHOSEN" ]; then
    echo "No snapshot under .claude/backups/ carries a RESTORE_SET, so there is no previous bundle this installer can replay; nothing was changed. Snapshots written before 2026-09-01 do not record which paths the installer owned -- restore those by hand." >&2
    exit 1
  fi
  SNAP="$BACKUPS/$CHOSEN"
  assert_no_symlink_tree "$SNAP"
  # EVERY LINE IS JUDGED BEFORE THE FIRST ONE IS ACTED ON, and this loop is where the judging has
  # to happen: `restore_from_snapshot` DELETES a target before it looks for a saved copy, and that
  # order is right for a path this installer owns -- 2 of the 15 lines a second install records
  # have no copy in the snapshot because the install CREATED them, and a faithful rollback removes
  # exactly those (measured 2026-09-02 on a real second install: 15 lines, 2 without a copy,
  # `.github/hooks` and `.github/agents`, neither of them present in the project). What that order
  # cannot survive is a manifest this installer did not write: a hand-copied or damaged snapshot
  # naming `docs/note.md` deleted that file at rc 0 with "Rollback done." printed over it, in BOTH
  # twins. So the refusal is not about the delete order, it is about OWNERSHIP -- and the proof of
  # ownership is not the manifest (the manifest is the thing in doubt) but `RESTORABLE`, the set
  # this script itself backs up, which is a second and independent record.
  #
  # A LINE PASSES IF IT IS OURS **OR** THE SNAPSHOT HOLDS A COPY OF IT. The second half is what
  # keeps an OLDER snapshot playable after a path leaves `RESTORABLE`: it carries its own copy, so
  # replaying it destroys nothing. Only a line that is neither is refused, and that combination is
  # what a foreign manifest looks like. Measured: zero refusals on a real second install.
  #
  # THE BOM IS STRIPPED, AND THAT IS NOT COSMETIC: the PowerShell twin writes its own RESTORE_SET
  # WITH a UTF-8 BOM (measured 2026-09-02 on a real install, bytes `efbbbf` in front of the first
  # line). So the mark is not a sign of a foreign manifest -- it is what OUR OTHER TWIN produces,
  # and refusing on it would refuse our own snapshots. Two measurements decided it, both on the
  # shipped cross-twin case (ps1 writes, this twin replays): WITHOUT the strip and before the
  # ownership rule below, this twin replayed at rc 0 and silently never put the FIRST recorded path
  # back -- a rollback that reports success and skipped a file; and WITHOUT the strip but WITH the
  # rule, it refuses its own twin's manifest at rc 1, because `<BOM>CLAUDE.md` is a name nobody
  # owns. A byte-order mark is not part of a path. A BOM in front of a line that is NOT ours is
  # still refused, by the rule above, on the line's content.
  set_paths=()
  foreign=()
  rooted=()
  kept=()
  first_line=1
  while IFS= read -r line || [ -n "$line" ]; do
    if [ "$first_line" -eq 1 ]; then line="${line#"$BOM"}"; first_line=0; fi
    line="${line%$CR}"
    case "$line" in ''|'#'*) continue;; esac
    if ! manifest_line_is_a_repo_relative_name "$line"; then
      rooted+=("$line")
      continue
    fi
    assert_safe_repo_path "$REPO/$line"
    # A KEPT_ONLY PATH IN A MANIFEST IS NOT AN OWNERSHIP QUESTION, and until 2026-09-12 the
    # ownership rule let it through: the backup pass copies these files, so the snapshot HOLDS a
    # copy, and "the snapshot holds a copy" is the very half that keeps an older manifest playable.
    # Measured on both twins, real installers, a manifest naming `.claude/settings.local.json`:
    # **rc 0** and the user's file replaced by the snapshot's copy. These two files are the ones
    # this installer reads and never writes, so no copy of them in any snapshot is one it made.
    if in_kept_only "$line"; then
      kept+=("$line")
      continue
    fi
    if ! in_restorable "$line" && [ ! -e "$SNAP/$line" ] && [ ! -L "$SNAP/$line" ]; then
      foreign+=("$line")
    fi
    set_paths+=("$line")
  done < "$SNAP/RESTORE_SET"
  if [ "${#rooted[@]}" -gt 0 ]; then
    echo "This snapshot's RESTORE_SET names path(s) that are not repo-relative names: ${rooted[*]}. A manifest line this installer writes is a sequence of plain names under the repository, and a word carrying its own root is read differently by the two launchers, so replaying it is not one operation. Nothing was changed; report where this snapshot came from rather than retrying." >&2
    exit 1
  fi
  if [ "${#kept[@]}" -gt 0 ]; then
    echo "This snapshot's RESTORE_SET names file(s) this installer backs up and never writes: ${kept[*]}. They are yours, not the bundle's; putting the snapshot's copy back would overwrite an edit this installer never made. Nothing was changed; take the copy out of .claude/backups/ by hand if you want the old one." >&2
    exit 1
  fi
  if [ "${#foreign[@]}" -gt 0 ]; then
    echo "This snapshot's RESTORE_SET names path(s) this installer does not own and did not save a copy of: ${foreign[*]}. Replaying it would DELETE them with nothing to put back, so nothing was changed. A manifest written by this installer names only paths it backs up; report where this snapshot came from rather than retrying." >&2
    exit 1
  fi
  restore_from_snapshot "$SNAP" "${set_paths[@]}"
  echo "  [rollback] replayed .claude/backups/$CHOSEN (${#set_paths[@]} recorded path(s))"
  # The transition this project announced has been undone, so the announcement goes with it; the
  # RESTART marker is raised for the same reason a fresh install raises it -- the bundle under the
  # running session just changed again, and only a session start reads the new one.
  rm -f "$REPO/.claude/kit_updated_from"
  mkdir -p "$REPO/.claude"
  {
    echo "# agents-and-skills handover marker (BUG-0016, DEC-0032)"
    echo "# A ROLLBACK replayed .claude/backups/$CHOSEN over team '$TEAM'. Until the next restart the"
    echo "# global handover guard refuses product-code writes and further derivation in this session."
    echo "# A SessionStart(startup) hook clears this file on the next real restart. Safe to delete."
  } > "$REPO/.claude/HANDOVER_PENDING"
  # WHAT IT DID NOT PUT BACK, derived rather than claimed: everything the installer leaves under
  # .claude/ that is not one of the recorded paths. Naming them is the difference between a
  # rollback and a promise that the project is exactly as it was.
  untouched=""
  while IFS= read -r entry; do
    [ -n "$entry" ] || continue
    case "$entry" in backups) continue;; esac
    if [ "${set_paths[*]}" != "${set_paths[*]/.claude\/$entry/}" ]; then continue; fi
    untouched="$untouched .claude/$entry"
  done < <(ls -1A "$REPO/.claude" 2>/dev/null)
  if [ -n "$untouched" ]; then
    echo "  [rollback] left as they are (not part of the recorded set):$untouched"
  fi
  echo "Rollback done. RESTART the session -- the replayed hooks and agents only load at session start."
  exit 0
fi

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
  .claude/hooks .claude/kernel .claude/skills .claude/team_kit_roles.txt .claude/provider_artifacts.json \
  .claude/kit_repo_files.json \
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
"$PYBIN" "$(cd "$(dirname "$0")" && pwd)/gen_provider_artifacts.py" \
  --repo "$REPO" --project-config "$CFG" --check-config-only
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
preflight

# THE STAGING HAS TO CARRY ITS OWN TRUST RECORDER, and this is asked BEFORE anything is copied.
# `write_kit_state.py` is what vouches for the installed hook bundle, and it is also one of
# `kernel.hashing.kit_hash_inputs` -- so a staging without it installed green on a warning nobody
# reads (`hook_trust: unverified`) while every later stamp comparison refused the SAME staging by
# the hash. Measured 2026-09-11 (BUG-0277): rc 0 on the first install for all three kits,
# `request-approval kit_update` then refused it with "does not hash to the content in its own
# VERSION". A first install that cannot be vouched for is not a first install this scaffold makes.
if [ ! -f "$KITS_ROOT/write_kit_state.py" ]; then
  echo "  [refused] $KITS_ROOT/write_kit_state.py is missing, so nothing could vouch for the" >&2
  echo "            installed hook bundle and every later kit-update check would refuse this" >&2
  echo "            same staging by its hash. Nothing was changed." >&2
  echo "  Remedy: re-install the harness from a complete store (\`install.sh\`)." >&2
  exit 1
fi
# settings.local.json: only ENFORCEMENT-replacing keys block the scaffold. `permissions` is
# where Claude Code records every "Always allow" grant and `model` is a legitimate local
# preference — blocking on those made every actively used project unable to take kit updates.
LOCAL_SETTINGS="$REPO/.claude/settings.local.json"
if [ -f "$LOCAL_SETTINGS" ]; then
  if ! local_keys="$(no_cr "$PYBIN" -c 'import json,sys
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
  rec="$(no_cr "$PYBIN" -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1], encoding="utf-8-sig")) or {}; print((d.get("project") or {}).get("preset") or "")' "$CFG")"
  if [ -n "$rec" ]; then PRESET="$rec"; PRESET_SOURCE="project_config.yaml"; fi
fi
[ -n "$PRESET" ] || { echo "Validated project_config.yaml contains no preset; no scaffold files were changed." >&2; exit 1; }
preset_result="$(no_cr "$PYBIN" "$(cd "$(dirname "$0")" && pwd)/preset_config.py" \
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
for relative in "${RESTORABLE[@]}" "${KEPT_ONLY[@]}"; do
  backup_local "$REPO/$relative" "$relative"
done
if [ -d "$BDIR" ]; then
  # The snapshot carries its OWN restore contract, so a rollback months later replays the set the
  # run that made it owned rather than today's. Repo-relative and POSIX-spelled, because either
  # twin of this installer may be the one that replays it.
  printf '%s\n' "${RESTORABLE[@]}" > "$BDIR/RESTORE_SET"
  echo "  [ok] backed up existing team files -> .claude/backups/$STAMP"
fi
if [ -f "$REPO/AGENTS.override.md" ] || [ -L "$REPO/AGENTS.override.md" ]; then
  echo "Repository AGENTS.override.md takes precedence over the team constitution. It was backed up and left untouched; merge/remove it only after explicit user review, then rerun scaffolding." >&2
  exit 1
fi

restore_scaffold_snapshot() {
  # THE RUN'S OWN SET, not a second copy of it: `RESTORABLE` is what was backed up above and what
  # the snapshot's RESTORE_SET records, so an abort undoes exactly the paths this run owns.
  restore_from_snapshot "$BDIR" "${RESTORABLE[@]}"
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
    # DEC-0039: the same shim/constitution FORM every marker reader uses (session_status,
    # validate.py) -- the marker only counts anchored on line 1 as `<!-- ... -->` with nothing
    # after it, never as a bare occurrence a quote/prose/negation could carry. [[:space:]]*$
    # swallows a trailing CR on a CRLF entry file (read leaves it on the line).
    if [[ "$first_line" =~ ^[[:space:]]*\<!--[[:space:]]*agents-and-skills:team-kit[[:space:]]+([A-Za-z0-9_-]+)[[:space:]]*--\>[[:space:]]*$ ]]; then
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
  # Kit sources carry provider-neutral tier aliases; the INSTALLED Claude frontmatter needs the
  # concrete reference-platform name (model_map stamping may override). WHICH aliases exist is
  # `team-kits/model_tiers.yaml` `aliases:` and nothing else -- `light`/haiku stood here for a
  # rung that table retired (DEC-0076: three rungs, no light row), so this translated a value
  # `gen_provider_artifacts.provider_neutral_model` already refuses in a kit source (BUG-0250).
  # CR-tolerant match: agent .md files may be CRLF on a Windows checkout used from WSL/Linux,
  # and non-MSYS awk keeps the \r in $0 (sub() below preserves the original line ending).
  ap="$AGENTS_DST/$(basename "$f")"
  tmp="$ap.tmp"
  awk '{ line=$0; sub(/\r$/, "", line)
         if (line=="model: lead")        sub(/model: lead/, "model: opus")
         else if (line=="model: worker") sub(/model: worker/, "model: sonnet")
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
      # tier aliases (team-kits/model_tiers.yaml `aliases:`): the map may say lead/worker —
      # Claude agent frontmatter gets the concrete reference-platform name.
      case "$val" in lead) val="opus" ;; worker) val="sonnet" ;; esac
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
    done < <(no_cr "$PYBIN" -c 'import sys,yaml
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
  marker="$(no_cr head -n 1 "$KIT/constitution/AGENTS.md")"
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
  # ...AND REMOVE WHAT THIS KIT DOES NOT SHIP, which the copy loop alone never did. `.claude/hooks`
  # is `sys.path[0]` for every gate process, so a file an EARLIER kit left there is not clutter: it
  # is a module the harness installed and no longer controls, and `write_kit_state.py` now refuses
  # to record trust over anything importable the kit did not deliver. Without this prune the first
  # release to drop a hook (`auto_dashboard.py`, in the V2 monolith) would make every project
  # installed before it un-scaffoldable. `.claude/kernel` needs no equivalent — it is deleted and
  # re-copied wholesale just below. The previous contents were backed up above.
  for f in "$REPO"/.claude/hooks/*; do
    [ -e "$f" ] || continue
    base="$(basename "$f")"
    if [ ! -e "$KIT/hooks/$base" ]; then
      rm -rf "$f"
      echo "  [prune] .claude/hooks/$base (not shipped by '$TEAM')"
    fi
  done
fi
# ...and the V2 state kernel the hooks import. `_kernel.kernel_parents()` names `<repo>/.claude`
# as the FIRST place it looks and says why: a project must run the kernel its hook bundle was
# installed with, not whatever version happens to sit in the global staging. Nothing copied it
# there, so that first candidate never existed and every project silently fell through to
# ~/.claude/team-kits -- or, on a machine without it, got KernelUnavailable from every integrity
# gate. It also carries `known_holes.json`, which `python scripts/harness.py doctor` needs to report any capability
# as verified at all.
if [ -d "$KITS_ROOT/kernel" ]; then
  rm -rf "$REPO/.claude/kernel"
  cp -R "$KITS_ROOT/kernel" "$REPO/.claude/kernel"
  echo "  [ok] .claude/kernel (V2 state kernel)"
fi
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
# different sets -- the shell twins did, and only the Windows one was ever executed by a test.
#
# Guarded by the same condition as the copy above, and for the recorder's reason: a staging too old
# to carry a kernel installs none, so nothing hashes this bundle and nothing records trust for it.
# Refusing the whole scaffold there would break the update path off such a staging instead of
# leaving `hook_trust` unverified, which is the fail-closed direction.
if [ -d "$KITS_ROOT/kernel" ]; then
  "$PYBIN" -B -c 'import sys; sys.path.insert(0, sys.argv[1]); from kernel.hashing import prune_transient; prune_transient(*sys.argv[2:])' \
    "$KITS_ROOT" "$REPO/.claude/hooks" "$REPO/.claude/kernel"
fi
# Role skills travel with the team. Their `skills:` frontmatter REGISTERS them for the role;
# it does not inject them -- measured 2026-08-02 for a role bound as the session agent, and
# unmeasured for the subagent-spawn path (tools/provider_observations.json). Each agent file
# names the retrieval route, which is why the skill directory has to be installed at all.
#
# A SKILL DIRECTORY WHOSE NAME IS NO ROLE OF THIS KIT BELONGS TO EVERY PRESET. The preset filter
# below is a ROLE filter, and it is right for a role's procedure skill; a reference skill belongs
# to no role by construction (constitution 1a), so filtering it by the role list dropped it from
# every preset but `team`. Measured 2026-09-01 against a real installer run into a throwaway HOME:
# preset `team` -> 11 skills including both reference skills, preset `solo` -> 5, neither of them.
# The failure was SILENT ABSENCE, not a dangling pointer -- the derivation reads the project's own
# .claude/skills, so a work order simply names nothing (H83). The question "is this name a role" is
# asked of the kit's own agents directory rather than of a list, so a reference skill added
# tomorrow is covered the day it ships.
if [ -d "$SKILLS_SRC" ]; then
  mkdir -p "$SKILLS_DST"
  for d in "$SKILLS_SRC"/*/; do
    [ -e "$d" ] || continue
    name="$(basename "$d")"
    if [ -f "$AGENTS_SRC/$name.md" ] && ! in_preset "$name"; then continue; fi
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
  # preserve the PREVIOUS version in a one-shot marker BEFORE overwriting: the "KIT UPDATED
  # x->y" announcement is consumed by the NEXT SessionStart — a mid-session update used to
  # lose it entirely when no clean restart followed (audit: a live repo sat two days silent).
  if [ -f "$REPO/.claude/kit_version" ]; then
    OLD_V="$(no_cr head -n 1 "$REPO/.claude/kit_version")"
    NEW_V="$(no_cr head -n 1 "$KIT/VERSION")"
    # never overwrite an unconsumed marker: two scaffolds without a SessionStart in between
    # must announce the EARLIEST from-version, not lose the first transition (audit)
    if [ -n "$OLD_V" ] && [ "$OLD_V" != "$NEW_V" ] && [ ! -f "$REPO/.claude/kit_updated_from" ]; then
      printf '%s\n' "$OLD_V" > "$REPO/.claude/kit_updated_from"
    fi
  fi
  cp -f "$KIT/VERSION" "$REPO/.claude/kit_version"
  echo "  [ok] .claude/kit_version ($(no_cr head -n 1 "$KIT/VERSION"))"
fi

# Record WHICH hook bundle this project now carries -- the value `python scripts/harness.py doctor` measures
# `hook_trust` against. Nothing wrote it before, so that comparison had no counterpart and
# `enforcement: hard` was unreachable for a reason nobody could act on. State is
# `restart_required`: the hooks installed above are not running in the session that ran this
# script, and only kit_trust_state.py (a SessionStart hook) may flip it to `active`.
# From the STAGING this scaffold installed from, not from $0's directory. The recorder compares
# the installed bundle against the kit files beside itself and takes no path from its caller -- a
# `--kit-root` flag was tried and became a one-flag way to bless any tampering, by pointing the
# "source" at the installation. A staging too old to carry the recorder records nothing, which
# leaves `hook_trust` unverified: the fail-closed direction.
if [ -f "$KITS_ROOT/write_kit_state.py" ]; then
  "$PYBIN" "$KITS_ROOT/write_kit_state.py" \
    --repo "$REPO" --kit "$TEAM" --kit-version "$(no_cr head -n 1 "$KIT/VERSION" 2>/dev/null || echo '')"
else
  echo "  [warn] $KITS_ROOT/write_kit_state.py is missing -- no hook-bundle trust recorded (\`python scripts/harness.py doctor\` will report hook_trust: unverified)"
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
#
# WHICH repo scripts the KIT owns (always overwritten, never copy-if-absent, never pending) is DATA,
# not a list in this file: `repo_kit_owned.txt` beside this script, read by BOTH scaffold twins so
# the .sh and .ps1 sets cannot drift. WHY a file is on it is written beside each entry in that
# file's header -- the guarded enforcement scripts (no other route can deliver a kit fix to them,
# BUG-0068), the entry point, the check tooling, the money reader (BUG-0072) -- and that header is
# the authority, not this comment.
kit_owned="|"
if [ -f "$KITS_ROOT/repo_kit_owned.txt" ]; then
  while IFS= read -r owned || [ -n "$owned" ]; do
    owned="${owned%$CR}"
    case "$owned" in ''|'#'*) continue;; esac
    kit_owned="$kit_owned$owned|"
  done < "$KITS_ROOT/repo_kit_owned.txt"
fi
kept_list=()
shipped_list=()
if [ -d "$KIT/templates/repo" ]; then
  while IFS= read -r rel; do
    rel="${rel#./}"
    # WHAT THE KIT PLACES OUTSIDE `.claude/`, recorded where it is placed (BUG-0265). One line at
    # the TOP of the loop rather than one per branch: the kit-owned branch returns, so a per-branch
    # append is three places that can drift from the walk. Every path this loop decides about is
    # the kit's -- overwritten, freshly copied, or kept because the project customised the kit's
    # file -- and a reader asking "is this the project's own file" needs all three.
    shipped_list+=("$rel")
    dst="$REPO/$rel"
    if [ "${kit_owned#*"|$rel|"}" != "$kit_owned" ]; then
      mkdir -p "$(dirname "$dst")"
      cp -f "$KIT/templates/repo/$rel" "$dst"
      echo "  [ok] repo (kit-owned, always updated): $rel"
      continue
    fi
    if [ ! -e "$dst" ]; then
      mkdir -p "$(dirname "$dst")"
      cp "$KIT/templates/repo/$rel" "$dst"
      echo "  [ok] repo: $rel"
    # DIVERGENCE IGNORES LINE-ENDING STYLE: a Windows/OneDrive checkout drifts LF->CRLF, and comparing
    # raw bytes then read EVERY script as "differs" and sent it to the pending list though its content
    # was the kit's own (BUG-0068). Strip CR from both sides before comparing (the .ps1 twin's
    # Get-NormalizedSha256 does the same).
    elif ! cmp -s <(tr -d "$CR" < "$KIT/templates/repo/$rel") <(tr -d "$CR" < "$dst"); then
      # copy-if-absent keeps the project's version — but say so, or a kit fix (e.g. quality.py)
      # silently never reaches existing projects while the update reads as "applied".
      echo "  [kept] repo: $rel (differs from the kit template - review/merge manually)"
      kept_list+=("$rel")
    fi
  done < <(cd "$KIT/templates/repo" && find . -type f -not -path '*/__pycache__/*' \
           -not -path '*/.ruff_cache/*' -not -path '*/.mypy_cache/*' -not -path '*/.pytest_cache/*')
fi
# THE RECORD ITSELF (BUG-0265). `.claude/provider_artifacts.json` is the shape: a manifest the
# PROJECT holds, so a reader asks the installation instead of carrying a directory name. Until it
# existed, `kernel.report.installed_kit_paths` could only exclude the DIRECTORIES a kit fills
# (`scripts/`, `tools/`) -- which also excluded a project's own script lying beside the kit's, and
# no finding said so. Written unconditionally, empty list included: "no file" and "no entries"
# print the same and mean the opposite things, and the reassuring one would be the wrong default.
# The JSON is built by the interpreter this run already validated, not by string concatenation
# here: a path is data, and a shell-quoted JSON writer is one backslash away from a manifest no
# reader can parse. THE SOURCE IS BYTE-IDENTICAL IN BOTH TWINS, and it carries neither a double
# quote nor a backslash for a measured reason: PowerShell strips double quotes and mangles
# backslashes when it hands a string to a native executable, so the first cut of this line reached
# `python` as `open(sys.argv[1], w, encoding=utf-8, newline=\n)` -- a SyntaxError the .ps1 twin
# then walked past, because a failing native call does not stop a PowerShell script by itself.
# `chr(10)` is there instead of an escape for the same reason; the twin checks its exit status.
"$PYBIN" -c "import json, sys
record = json.dumps({'kit': sys.argv[2], 'repo_files': sorted(sys.argv[3:])}, indent=2) + chr(10)
open(sys.argv[1], 'wb').write(record.encode('utf-8'))
" "$REPO/.claude/kit_repo_files.json" "$TEAM" ${shipped_list[@]+"${shipped_list[@]}"}
echo "  [ok] .claude/kit_repo_files.json (${#shipped_list[@]} file(s) this kit places in the project)"
PEND="$REPO/.claude/kit_update_pending.repo"
STATE="$REPO/.claude/kit_update_pending.state"
if [ ${#kept_list[@]} -gt 0 ]; then
  mkdir -p "$REPO/.claude"
  {
    echo "# Repo templates this project customised that ALSO changed in kit $TEAM $(no_cr head -n 1 "$KIT/VERSION" 2>/dev/null) (line-ending style ignored) -- the PM works each through the normal loop: merge the wanted kit fix, or record a conscious skip as a decision item (decisions/active/), then DELETE this file. session_status reminds every session until it is gone. Only PROJECT-CUSTOMISABLE templates appear here; the scripts the KIT owns (listed in the installer's repo_kit_owned.txt, each with the reason it is there -- the enforcement layer, the entry point, the money reader) are refreshed by the installer on every run and never land on this list, so nothing here needs a route a session forbids (BUG-0068)."
    printf -- "- %s\n" "${kept_list[@]}"
  } > "$PEND"
  # fresh REAL update -> fresh nag counter; a same-version re-run must NOT reset the
  # escalation (audit: "updating again just to be safe" kept the backlog forever young)
  if [ "$SAME_VERSION" != "1" ]; then rm -f "$STATE"; fi
  echo "  [!] ${#kept_list[@]} diverged repo file(s) -> .claude/kit_update_pending.repo (merge or consciously skip, then delete it)"
else
  rm -f "$PEND"
fi

# BUG-0016 handover marker (DEC-0032): set it LAST, when the install has otherwise succeeded, so
# the global `~/.claude/hooks/handover_guard.py` refuses product-code writes and further derivation
# for the rest of THIS entry session -- the window in which the project hooks just installed are not
# yet active (settings-watcher gap). The project-owned `clear_handover_marker.py`
# SessionStart(startup) hook deletes it on the next REAL restart; it is safe to delete by hand.
mkdir -p "$REPO/.claude"
{
  echo "# agents-and-skills handover marker (BUG-0016, DEC-0032)"
  echo "# The entry session installed team '$TEAM' and asked for a restart. Until that restart the"
  echo "# global handover guard refuses product-code writes and further derivation in this session."
  echo "# A SessionStart(startup) hook clears this file on the next real restart. Safe to delete."
} > "$REPO/.claude/HANDOVER_PENDING"

echo "Team '$TEAM' installed locally. RESTART the session (close/reopen, or start a new session in this folder) -- the new agents and the 'agent: $LEAD' setting only load at session start. After the restart, type anything (e.g. 'weiter') -- nothing is auto-sent, YOU stay in control of the first message; the '$LEAD' lead then greets you with a one-line status and picks up any draft plan in project_memory/."
echo "NOTE: if a session is ALREADY running in this folder (even suspended at a usage limit), its hooks are live on the new files from this moment -- a real restamp landed mid-session and entangled kit files with build changes. Finish or restart that session before continuing work there."
