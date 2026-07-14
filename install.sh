#!/usr/bin/env bash
# Linux/macOS installer for agents-and-skills
# Usage:
#   ./install.sh                  # Install for Claude Code AND Codex (asks to confirm)
#   ./install.sh --target claude  # Only Claude Code
#   ./install.sh --target codex   # Only the Codex entry gate ($CODEX_HOME/AGENTS.md)
#   ./install.sh --force          # Skip the confirmation prompt (still backs up first)
#
# Behavior: backs up the existing agents-and-skills artifacts to ~/.claude/backups/<timestamp>/,
# shows a notice, asks to confirm, then overwrites them. ~/.claude/settings.json is MERGED:
# missing defaults are added, existing personal values win, and permission allow/deny lists are
# unioned. The previous file is backed up. Copilot support was removed; the installer still
# cleans up previously installed Copilot files.

set -euo pipefail

TARGET="both"
FORCE=0
CODEX_GLOBAL_SECRETS=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            if [[ $# -lt 2 ]]; then
                echo "Missing value for --target (expected: both, claude, or codex)." >&2
                exit 1
            fi
            TARGET="$2"
            shift 2
            ;;
        --force|-y) FORCE=1; shift ;;
        # OPT-IN: append the user-wide Codex secret shield (marked permission profile denying
        # secret reads) to $CODEX_HOME/config.toml — counterpart of the Claude settings denies.
        --codex-global-secrets) CODEX_GLOBAL_SECRETS=1; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

case "$TARGET" in
    both|claude|codex) ;;
    *)
        echo "Invalid target: $TARGET (expected: both, claude, or codex)." >&2
        exit 1
        ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_CLAUDE_SRC="$REPO_ROOT/user/claude"
USER_CODEX_SRC="$REPO_ROOT/user/codex"
TEAM_KITS_SRC="$REPO_ROOT/team-kits"
MERGE_SCRIPT="$REPO_ROOT/user/merge_settings.py"

CLAUDE_GLOBAL="$HOME/.claude"
CLAUDE_SKILLS="$HOME/.claude/skills"
CLAUDE_AGENTS="$HOME/.claude/agents"
CLAUDE_TEAM_KITS="$HOME/.claude/team-kits"
# Legacy Copilot destination — only referenced to REMOVE files older installs put there.
COPILOT_SKILLS="$HOME/.copilot/skills"
CODEX_GLOBAL="${CODEX_HOME:-$HOME/.codex}"

case "$(uname -s)" in
    Darwin) VSCODE_PROMPTS="$HOME/Library/Application Support/Code/User/prompts" ;;
    *)      VSCODE_PROMPTS="$HOME/.config/Code/User/prompts" ;;
esac

STAMP_BASE="$(date +%Y%m%d-%H%M%S)"
STAMP="$STAMP_BASE"
BACKUP_DIR="$CLAUDE_GLOBAL/backups/$STAMP"
stamp_suffix=1
while [[ -e "$BACKUP_DIR" ]]; do
    STAMP="$STAMP_BASE-$stamp_suffix"
    BACKUP_DIR="$CLAUDE_GLOBAL/backups/$STAMP"
    stamp_suffix=$((stamp_suffix + 1))
done

# Python 3.8+ with PyYAML is required UNCONDITIONALLY (staging copy, settings merge, and every
# scaffold/hook run need it) — checked before any mutation.
PYTHON="$(command -v python3 || command -v python || true)"
if [[ -z "$PYTHON" ]]; then
    echo "Python 3 is required (staging, settings merge, kit hooks)." >&2
    exit 1
fi
if ! "$PYTHON" -c 'import importlib.util, sys; sys.exit(0 if (sys.version_info >= (3, 8) and importlib.util.find_spec("yaml")) else 1)'; then
    echo "Python 3.8+ and PyYAML are required. Run: python3 -m pip install pyyaml" >&2
    exit 1
fi

assert_no_symlink_components() {
    local target="$1" current="" component
    case "$target" in /*) ;; *) echo "Refusing non-absolute managed path: $target" >&2; exit 1 ;; esac
    local -a parts=()
    IFS='/' read -r -a parts <<< "$target"
    for component in "${parts[@]}"; do
        [[ -n "$component" ]] || continue
        current="$current/$component"
        if [[ -L "$current" ]]; then
            echo "Refusing symlink path '$current'; installation was not started." >&2
            exit 1
        fi
    done
}

assert_no_symlink_tree() {
    local target="$1" found=""
    assert_no_symlink_components "$target"
    if [[ -e "$target" || -L "$target" ]]; then
        found="$(find -P "$target" -type l -print -quit 2>/dev/null || true)"
        if [[ -n "$found" ]]; then
            echo "Refusing symlink path '$found'; installation was not started." >&2
            exit 1
        fi
    fi
}

backup_item() {
    local path="$1"
    [[ -e "$path" ]] || return 0
    assert_no_symlink_tree "$path"
    mkdir -p "$BACKUP_DIR"
    cp -R "$path" "$BACKUP_DIR/$(basename "$path")"
}

# Skills are now per-kit (installed by the scaffold into ./.claude/skills). The installer no longer
# installs global skills; it removes the old global ones we used to ship.
OLD_SKILLS="brief-mode debug explain git-safety interview new-skill plan-to-issues plan-to-prd pm-playbook pre-commit refactor review-plan setup-repo tdd triage"
remove_old_skills() {
    local dest="$1"
    [[ -d "$dest" ]] || return 0
    for s in $OLD_SKILLS; do
        if [[ -e "$dest/$s" ]]; then
            assert_no_symlink_tree "$dest/$s"
            rm -rf "$dest/$s"
            echo "  [ok]   removed old skill: $s"
        fi
    done
}

install_file() {
    local src="$1"; local dest="$2"; local label="$3"
    if [[ ! -e "$src" ]]; then echo "  [warn] not found: $src"; return; fi
    assert_no_symlink_tree "$src"
    assert_no_symlink_components "$dest"
    mkdir -p "$(dirname "$dest")"
    cp -f "$src" "$dest"
    echo "  [ok]   $label"
}

# Fail before confirmation or backup if a managed source/destination traverses a symlink. `cp -f`
# follows destination symlinks and could otherwise overwrite a file outside the selected profile.
assert_no_symlink_tree "$TEAM_KITS_SRC"
assert_no_symlink_components "$BACKUP_DIR"
assert_no_symlink_components "$CLAUDE_GLOBAL"
for path in "$CLAUDE_AGENTS" "$CLAUDE_SKILLS" "$CLAUDE_TEAM_KITS" \
            "$CLAUDE_GLOBAL/CLAUDE.md" "$CLAUDE_GLOBAL/settings.json" \
            "$CLAUDE_GLOBAL/statusline.py"; do
    assert_no_symlink_tree "$path"
done
if [[ "$TARGET" == "both" || "$TARGET" == "codex" ]]; then
    assert_no_symlink_components "$CODEX_GLOBAL"
    assert_no_symlink_tree "$CODEX_GLOBAL/AGENTS.md"
    assert_no_symlink_tree "$CODEX_GLOBAL/AGENTS.override.md"
    assert_no_symlink_tree "$CODEX_GLOBAL/config.toml"
    if command -v codex >/dev/null 2>&1; then
        codex_version="$(codex --version 2>/dev/null | head -n 1 || true)"
        if [[ -n "$codex_version" ]]; then
            echo "  [info] detected Codex host: $codex_version"
            if [[ "$codex_version" =~ ([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
                codex_major="${BASH_REMATCH[1]}"; codex_minor="${BASH_REMATCH[2]}"
                # Baseline 0.131.0: hooks GA (official changelog 2026-05-14) + the improved
                # per-hash hook trust flow the kits rely on. No older release carries both.
                if (( codex_major == 0 && codex_minor < 131 )); then
                    echo "Codex ${BASH_REMATCH[0]} is too old (hooks GA + trust flow need 0.131.0+). Upgrade Codex before installing this entry gate." >&2
                    exit 1
                fi
            else
                echo "  [warn] Could not parse the Codex version; verify permission-profile and current hook support before using a structured kit."
            fi
        else
            echo "  [warn] Codex was found but its version/capabilities could not be verified; use a current build and review /hooks after scaffolding."
        fi
    else
        echo "  [warn] Codex executable not found; entry-gate installation can proceed, but hooks, custom agents, and permission profiles cannot be verified on this host."
    fi
    if [[ -f "$CODEX_GLOBAL/config.toml" ]] && grep -Eq '^[[:space:]]*(sandbox_mode[[:space:]]*=|\[sandbox_workspace_write\][[:space:]]*(#.*)?$)' "$CODEX_GLOBAL/config.toml"; then
        echo "  [warn] $CODEX_GLOBAL/config.toml sets legacy sandbox_mode/sandbox_workspace_write configuration. Codex gives legacy sandbox settings precedence over generated permission profiles; remove/relocate it before relying on team-kit filesystem policy."
    fi
fi

echo "agents-and-skills installer"
echo "This refreshes the shared team-kit staging at ~/.claude/team-kits."
if [[ "$TARGET" == "both" || "$TARGET" == "claude" ]]; then
    echo "It OVERWRITES managed Claude files and MERGES settings.json (existing personal values win; permission lists are unioned)."
fi
if [[ "$TARGET" == "both" || "$TARGET" == "codex" ]]; then
    echo "It OVERWRITES the Codex entry gate at $CODEX_GLOBAL/AGENTS.md."
    if [[ -f "$CODEX_GLOBAL/AGENTS.override.md" ]]; then
        echo "Codex override detected at $CODEX_GLOBAL/AGENTS.override.md; it will be backed up and preserved."
        echo "It takes precedence over AGENTS.md, so the installed entry gate stays inactive while the override exists."
    fi
fi
echo "A backup of the current files is saved to: $BACKUP_DIR"
if [[ $FORCE -eq 0 ]]; then
    read -r -p "Continue? (y/N) " answer
    case "$answer" in y|Y|yes|j|ja) ;; *) echo "Aborted."; exit 1 ;; esac
fi

echo
echo "-> Backing up to $BACKUP_DIR"
backup_item "$CLAUDE_GLOBAL/CLAUDE.md"
backup_item "$CLAUDE_GLOBAL/settings.json"
backup_item "$CLAUDE_GLOBAL/statusline.py"
backup_item "$CLAUDE_AGENTS"
backup_item "$CLAUDE_SKILLS"
backup_item "$CLAUDE_TEAM_KITS"
# Legacy Copilot files older installs put into VS Code prompts — backed up before cleanup below.
LEGACY_COPILOT_NAMES="COPILOT.instructions.md group-leader.agent.md memory-engineer.agent.md project-memory.instructions.md"
if [[ -d "$VSCODE_PROMPTS" ]]; then
    for name in $LEGACY_COPILOT_NAMES; do
        [[ -e "$VSCODE_PROMPTS/$name" ]] && backup_item "$VSCODE_PROMPTS/$name"
    done
fi
if [[ "$TARGET" == "both" || "$TARGET" == "codex" ]]; then
    if [[ -f "$CODEX_GLOBAL/AGENTS.md" ]]; then
        # backed up as codex-AGENTS.md so it cannot collide with other backups
        mkdir -p "$BACKUP_DIR"
        cp -f "$CODEX_GLOBAL/AGENTS.md" "$BACKUP_DIR/codex-AGENTS.md"
    fi
    if [[ -f "$CODEX_GLOBAL/AGENTS.override.md" ]]; then
        # Preserve the override itself and store a copy under an unambiguous name. The installer never
        # replaces an override because it is user-owned and intentionally takes precedence over AGENTS.md.
        mkdir -p "$BACKUP_DIR"
        cp -f "$CODEX_GLOBAL/AGENTS.override.md" "$BACKUP_DIR/codex-AGENTS.override.md"
    fi
fi
echo "  [ok]   backup complete"

echo
# Sanity: never stage a broken or unbumped kit
if [[ -f "$REPO_ROOT/tools/validate.py" ]]; then
    if ! "$PYTHON" "$REPO_ROOT/tools/validate.py"; then
        echo "validate.py FAILED - not installing a broken kit. Fix it (e.g. python tools/bump_kit_version.py) and rerun." >&2
        exit 1
    fi
fi

echo "-> Team kits (shared staging)"
if [[ -d "$TEAM_KITS_SRC" ]]; then
    mkdir -p "$CLAUDE_GLOBAL"
    stage="$CLAUDE_GLOBAL/.team-kits.stage.$$.$STAMP"
    previous="$CLAUDE_GLOBAL/.team-kits.previous.$$.$STAMP"
    if [[ -e "$stage" || -e "$previous" ]]; then
        echo "Refusing to reuse an existing team-kit transaction path: $stage / $previous" >&2
        exit 1
    fi
    # If copytree (or anything after it) dies mid-flight, do not leave a half-written stage
    # directory behind — set -e exits through this trap.
    trap '[[ -n "${stage:-}" && -e "$stage" ]] && rm -rf "$stage"' EXIT
    "$PYTHON" -c "import shutil,sys; shutil.copytree(sys.argv[1], sys.argv[2], ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo','.pytest_cache','.ruff_cache','.mypy_cache'))" \
      "$TEAM_KITS_SRC" "$stage"
    if [[ -e "$CLAUDE_TEAM_KITS" ]]; then mv "$CLAUDE_TEAM_KITS" "$previous"; fi
    if ! mv "$stage" "$CLAUDE_TEAM_KITS"; then
        [[ -e "$previous" ]] && mv "$previous" "$CLAUDE_TEAM_KITS"
        exit 1
    fi
    [[ -e "$previous" ]] && rm -rf "$previous"
    trap - EXIT
    echo "  [ok]   team-kits -> ~/.claude/team-kits"
fi

if [[ "$TARGET" == "both" || "$TARGET" == "claude" ]]; then
    echo
    echo "-> Claude Code"
    remove_old_skills "$CLAUDE_SKILLS"
    # group-leader was removed (the plan-first entry gate replaces it) — clean up any stale install.
    [[ -f "$CLAUDE_AGENTS/group-leader.md" ]] && rm -f "$CLAUDE_AGENTS/group-leader.md" && echo "  [ok]   removed old group-leader agent"
    install_file "$USER_CLAUDE_SRC/CLAUDE.md" "$CLAUDE_GLOBAL/CLAUDE.md" "CLAUDE.md -> ~/.claude/CLAUDE.md"
    install_file "$USER_CLAUDE_SRC/statusline.py" "$CLAUDE_GLOBAL/statusline.py" "statusline.py -> ~/.claude/statusline.py"
    if [[ -d "$USER_CLAUDE_SRC/agents" ]]; then
        for f in "$USER_CLAUDE_SRC/agents"/*.md; do
            [[ -e "$f" ]] || continue
            install_file "$f" "$CLAUDE_AGENTS/$(basename "$f")" "agent: $(basename "$f")"
        done
    fi
    if [[ -f "$MERGE_SCRIPT" && -f "$USER_CLAUDE_SRC/settings.json" ]]; then
        if ! "$PYTHON" "$MERGE_SCRIPT" "$USER_CLAUDE_SRC/settings.json" "$CLAUDE_GLOBAL/settings.json"; then
            echo "settings.json merge FAILED (your file was not modified) - fix ~/.claude/settings.json and rerun." >&2
            exit 1
        fi
    else
        echo "  [warn] merge script or shipped settings missing - skipped settings.json merge."
        echo "         Add only missing defaults and union permissions.allow/deny from user/claude/settings.json manually."
    fi
fi

# One-time cleanup of files older installs shipped for the now-removed Copilot support — runs for
# EVERY target (a codex-only profile may still carry them from an earlier "both" install).
remove_old_skills "$COPILOT_SKILLS"
for name in $LEGACY_COPILOT_NAMES; do
    legacy="$VSCODE_PROMPTS/$name"
    if [[ -e "$legacy" ]]; then
        assert_no_symlink_tree "$legacy"
        rm -f "$legacy"
        echo "  [ok]   removed legacy Copilot file: $(basename "$legacy")"
    fi
done

if [[ "$TARGET" == "both" || "$TARGET" == "codex" ]]; then
    echo
    echo "-> Codex CLI (entry gate)"
    if [[ ! -d "$CODEX_GLOBAL" ]]; then
        mkdir -p "$CODEX_GLOBAL"
        echo "  [ok]   created Codex home: $CODEX_GLOBAL"
    fi
    # The entry gate teaches a fresh Codex session how to bootstrap a team-kit project. It owns
    # AGENTS.md, while an existing AGENTS.override.md remains user-owned and untouched.
    install_file "$USER_CODEX_SRC/AGENTS.md" "$CODEX_GLOBAL/AGENTS.md" "AGENTS.md -> $CODEX_GLOBAL/AGENTS.md (entry gate)"
    if [[ -f "$CODEX_GLOBAL/AGENTS.override.md" ]]; then
        echo "  [warn] preserved AGENTS.override.md; Codex will use it instead of the installed entry gate."
    fi
    if [[ $CODEX_GLOBAL_SECRETS -eq 1 ]]; then
        if [[ -f "$CODEX_GLOBAL/config.toml" ]]; then
            mkdir -p "$BACKUP_DIR"
            cp -f "$CODEX_GLOBAL/config.toml" "$BACKUP_DIR/codex-config.toml"
        fi
        if ! "$PYTHON" "$REPO_ROOT/user/codex_global_config.py" "$CODEX_GLOBAL"; then
            echo "  [warn] Codex secret shield was NOT installed (see the message above); your config.toml is unchanged."
        fi
    fi
fi

echo
echo "Done. Backup at $BACKUP_DIR."
if [[ "$TARGET" == "both" || "$TARGET" == "claude" ]]; then
    echo "Start a new Claude Code session to pick up the installed configuration."
fi
if [[ "$TARGET" == "both" || "$TARGET" == "codex" ]]; then
    echo "Start a new Codex session to pick up the entry gate."
fi
