#!/usr/bin/env bash
# Linux/macOS installer for agent-skills
# Usage:
#   ./install.sh                  # Install for both Claude Code and Copilot
#   ./install.sh --target claude  # Only Claude Code
#   ./install.sh --target copilot # Only Copilot
#   ./install.sh --force          # Overwrite existing files

set -euo pipefail

TARGET="both"
FORCE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) TARGET="$2"; shift 2 ;;
        --force) FORCE=1; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$REPO_ROOT/skills"
CLAUDE_SRC="$REPO_ROOT/claude-code"
COPILOT_SRC="$REPO_ROOT/github-copilot"
TEMPLATES_SRC="$REPO_ROOT/templates"

CLAUDE_GLOBAL="$HOME/.claude"
CLAUDE_SKILLS="$HOME/.claude/skills"
CLAUDE_TEMPLATES="$HOME/.claude/templates"
COPILOT_SKILLS="$HOME/.copilot/skills"
COPILOT_TEMPLATES="$HOME/.copilot/templates"

# VS Code user prompts location differs per OS
case "$(uname -s)" in
    Darwin) VSCODE_PROMPTS="$HOME/Library/Application Support/Code/User/prompts" ;;
    Linux)  VSCODE_PROMPTS="$HOME/.config/Code/User/prompts" ;;
    *)      VSCODE_PROMPTS="$HOME/.config/Code/User/prompts" ;;
esac

install_skills() {
    local dest="$1"
    local label="$2"
    mkdir -p "$dest"
    for skill in "$SKILLS_SRC"/*/; do
        name="$(basename "$skill")"
        target_dir="$dest/$name"
        if [[ -e "$target_dir" && $FORCE -eq 0 ]]; then
            echo "  [skip] $label : $name"; continue
        fi
        rm -rf "$target_dir"
        cp -R "$skill" "$target_dir"
        echo "  [ok]   $label : $name"
    done
}

install_file() {
    local src="$1"
    local dest="$2"
    local label="$3"
    if [[ ! -e "$src" ]]; then echo "  [warn] not found: $src"; return; fi
    if [[ -e "$dest" && $FORCE -eq 0 ]]; then
        echo "  [skip] $label (use --force to overwrite)"; return
    fi
    mkdir -p "$(dirname "$dest")"
    cp "$src" "$dest"
    echo "  [ok]   $label"
}

install_templates() {
    local dest="$1"
    local label="$2"
    [[ -d "$TEMPLATES_SRC" ]] || return
    mkdir -p "$dest"
    for tpl in "$TEMPLATES_SRC"/*/; do
        [[ -e "$tpl" ]] || continue
        name="$(basename "$tpl")"
        target_dir="$dest/$name"
        if [[ -e "$target_dir" && $FORCE -eq 0 ]]; then
            echo "  [skip] $label : $name"; continue
        fi
        rm -rf "$target_dir"
        cp -R "$tpl" "$target_dir"
        echo "  [ok]   $label : $name"
    done
}

echo "Installing agent-skills..."

if [[ "$TARGET" == "both" || "$TARGET" == "claude" ]]; then
    echo
    echo "-> Claude Code"
    install_skills "$CLAUDE_SKILLS" "skill"
    install_file "$CLAUDE_SRC/CLAUDE.md" "$CLAUDE_GLOBAL/CLAUDE.md" "CLAUDE.md -> ~/.claude/CLAUDE.md"
    if [[ -d "$CLAUDE_SRC/agents" ]]; then
        for f in "$CLAUDE_SRC/agents"/*.md; do
            [[ -e "$f" ]] || continue
            name="$(basename "$f")"
            install_file "$f" "$CLAUDE_GLOBAL/agents/$name" "agent: $name"
        done
    fi
    install_templates "$CLAUDE_TEMPLATES" "template"
fi

if [[ "$TARGET" == "both" || "$TARGET" == "copilot" ]]; then
    echo
    echo "-> GitHub Copilot"
    install_skills "$COPILOT_SKILLS" "skill"
    for f in "$COPILOT_SRC"/*.instructions.md; do
        [[ -e "$f" ]] || continue
        name="$(basename "$f")"
        install_file "$f" "$VSCODE_PROMPTS/$name" "instructions: $name"
    done
    if [[ -d "$COPILOT_SRC/agents" ]]; then
        for f in "$COPILOT_SRC/agents"/*.agent.md; do
            [[ -e "$f" ]] || continue
            name="$(basename "$f")"
            install_file "$f" "$VSCODE_PROMPTS/$name" "agent: $name"
        done
    fi
    install_templates "$COPILOT_TEMPLATES" "template"
fi

echo
echo "Done. Restart VS Code to pick up new skills/agents."
