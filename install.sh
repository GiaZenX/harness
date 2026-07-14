#!/usr/bin/env bash
# Linux/macOS installer for agents-and-skills
# Usage:
#   ./install.sh                  # Install for Claude Code, Copilot AND Codex (asks to confirm)
#   ./install.sh --target claude  # Only Claude Code
#   ./install.sh --target copilot # Only Copilot
#   ./install.sh --target codex   # Only the Codex entry gate (~/.codex/AGENTS.md)
#   ./install.sh --force          # Skip the confirmation prompt (still backs up first)
#
# Behavior: backs up the existing agents-and-skills artifacts to ~/.claude/backups/<timestamp>/,
# shows a notice, asks to confirm, then overwrites them. ~/.claude/settings.json is MERGED
# (our keys added; your personal keys preserved) and the previous file is backed up.

set -euo pipefail

TARGET="both"
FORCE=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) TARGET="$2"; shift 2 ;;
        --force|-y) FORCE=1; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_CLAUDE_SRC="$REPO_ROOT/user/claude"
USER_COPILOT_SRC="$REPO_ROOT/user/copilot"
USER_CODEX_SRC="$REPO_ROOT/user/codex"
TEAM_KITS_SRC="$REPO_ROOT/team-kits"
MERGE_SCRIPT="$REPO_ROOT/user/merge_settings.py"

CLAUDE_GLOBAL="$HOME/.claude"
CLAUDE_SKILLS="$HOME/.claude/skills"
CLAUDE_AGENTS="$HOME/.claude/agents"
CLAUDE_TEAM_KITS="$HOME/.claude/team-kits"
COPILOT_SKILLS="$HOME/.copilot/skills"
CODEX_GLOBAL="$HOME/.codex"

case "$(uname -s)" in
    Darwin) VSCODE_PROMPTS="$HOME/Library/Application Support/Code/User/prompts" ;;
    *)      VSCODE_PROMPTS="$HOME/.config/Code/User/prompts" ;;
esac

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$CLAUDE_GLOBAL/backups/$STAMP"

PYTHON="$(command -v python3 || command -v python || true)"

backup_item() {
    local path="$1"
    [[ -e "$path" ]] || return 0
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
        if [[ -e "$dest/$s" ]]; then rm -rf "$dest/$s"; echo "  [ok]   removed old skill: $s"; fi
    done
}

install_file() {
    local src="$1"; local dest="$2"; local label="$3"
    if [[ ! -e "$src" ]]; then echo "  [warn] not found: $src"; return; fi
    mkdir -p "$(dirname "$dest")"
    cp -f "$src" "$dest"
    echo "  [ok]   $label"
}

echo "agents-and-skills installer"
echo "This OVERWRITES the agents-and-skills files in ~/.claude (CLAUDE.md, agents, skills,"
echo "team-kits, statusline) and MERGES ~/.claude/settings.json (your personal keys are kept)."
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
if [[ -d "$VSCODE_PROMPTS" ]]; then
    for f in "$VSCODE_PROMPTS"/*.agent.md "$VSCODE_PROMPTS/COPILOT.instructions.md"; do
        [[ -e "$f" ]] && backup_item "$f"
    done
fi
if [[ -f "$CODEX_GLOBAL/AGENTS.md" ]]; then
    # backed up as codex-AGENTS.md so it cannot collide with other backups
    mkdir -p "$BACKUP_DIR"
    cp -f "$CODEX_GLOBAL/AGENTS.md" "$BACKUP_DIR/codex-AGENTS.md"
fi
echo "  [ok]   backup complete"

echo
# Sanity: never stage a broken or unbumped kit
if [[ -f "$REPO_ROOT/tools/validate.py" ]]; then
    PYBIN="$(command -v python3 || command -v python || true)"
    if [[ -n "$PYBIN" ]]; then
        if ! "$PYBIN" "$REPO_ROOT/tools/validate.py"; then
            echo "validate.py FAILED - not installing a broken kit. Fix it (e.g. python tools/bump_kit_version.py) and rerun." >&2
            exit 1
        fi
    fi
fi

echo "-> Team kits (shared staging)"
if [[ -d "$TEAM_KITS_SRC" ]]; then
    rm -rf "$CLAUDE_TEAM_KITS"; mkdir -p "$CLAUDE_TEAM_KITS"
    cp -R "$TEAM_KITS_SRC/." "$CLAUDE_TEAM_KITS/"
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
    if [[ -n "$PYTHON" && -f "$MERGE_SCRIPT" && -f "$USER_CLAUDE_SRC/settings.json" ]]; then
        "$PYTHON" "$MERGE_SCRIPT" "$USER_CLAUDE_SRC/settings.json" "$CLAUDE_GLOBAL/settings.json"
    else
        echo "  [warn] python not found or merge script missing - skipped settings.json merge."
        echo "         Add the keys from user/claude/settings.json to ~/.claude/settings.json manually."
    fi
fi

if [[ "$TARGET" == "both" || "$TARGET" == "copilot" ]]; then
    echo
    echo "-> GitHub Copilot"
    remove_old_skills "$COPILOT_SKILLS"
    [[ -f "$VSCODE_PROMPTS/group-leader.agent.md" ]] && rm -f "$VSCODE_PROMPTS/group-leader.agent.md" && echo "  [ok]   removed old group-leader prompt"
    for f in "$USER_COPILOT_SRC"/*.instructions.md; do
        [[ -e "$f" ]] || continue
        install_file "$f" "$VSCODE_PROMPTS/$(basename "$f")" "instructions: $(basename "$f")"
    done
    if [[ -d "$USER_COPILOT_SRC/agents" ]]; then
        for f in "$USER_COPILOT_SRC/agents"/*.agent.md; do
            [[ -e "$f" ]] || continue
            install_file "$f" "$VSCODE_PROMPTS/$(basename "$f")" "agent: $(basename "$f")"
        done
    fi
fi

if [[ "$TARGET" == "both" || "$TARGET" == "codex" ]]; then
    echo
    echo "-> Codex CLI (entry gate)"
    if [[ -d "$CODEX_GLOBAL" ]]; then
        # ~/.codex exists only when Codex is installed; the entry gate teaches a fresh Codex
        # session how to bootstrap a team-kit project (Codex-first bootstrap gap). OVERWRITES the
        # global AGENTS.md (backed up above as codex-AGENTS.md) -- it is OURS to own, like
        # ~/.claude/CLAUDE.md.
        install_file "$USER_CODEX_SRC/AGENTS.md" "$CODEX_GLOBAL/AGENTS.md" "AGENTS.md -> ~/.codex/AGENTS.md (entry gate)"
    else
        echo "  [skip] ~/.codex not found (Codex CLI not installed) - nothing to do"
    fi
fi

echo
echo "Done. Backup at $BACKUP_DIR. Restart VS Code to pick up new skills/agents."
