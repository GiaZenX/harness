#!/usr/bin/env bash
# Linux/macOS installer for agent-skills
# Usage:
#   ./install.sh                  # Install for both Claude Code and Copilot
#   ./install.sh --target claude  # Only Claude Code
#   ./install.sh --target copilot # Only Copilot
#   ./install.sh --force          # Overwrite existing skills/agents

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
AGENTS_SRC="$REPO_ROOT/agents"
INSTRUCTIONS_FILE="$REPO_ROOT/copilot-instructions.md"

CLAUDE_SKILLS="$HOME/.claude/skills"
COPILOT_SKILLS="$HOME/.copilot/skills"

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
            echo "  [skip] $label : $name (already exists, use --force to overwrite)"
            continue
        fi
        rm -rf "$target_dir"
        cp -R "$skill" "$target_dir"
        echo "  [ok]   $label : $name"
    done
}

install_agents() {
    mkdir -p "$VSCODE_PROMPTS"
    for agent in "$AGENTS_SRC"/*.agent.md; do
        [[ -e "$agent" ]] || continue
        name="$(basename "$agent")"
        target_file="$VSCODE_PROMPTS/$name"
        if [[ -e "$target_file" && $FORCE -eq 0 ]]; then
            echo "  [skip] agent : $name (already exists, use --force to overwrite)"
            continue
        fi
        cp "$agent" "$target_file"
        echo "  [ok]   agent : $name"
    done
}

install_instructions() {
    if [[ ! -e "$INSTRUCTIONS_FILE" ]]; then
        echo "  [warn] copilot-instructions.md not found in repo"
        return
    fi

    mkdir -p "$VSCODE_PROMPTS"
    target_file="$VSCODE_PROMPTS/copilot-instructions.md"
    if [[ -e "$target_file" && $FORCE -eq 0 ]]; then
        echo "  [skip] instructions: copilot-instructions.md (already exists, use --force to overwrite)"
        return
    fi
    cp "$INSTRUCTIONS_FILE" "$target_file"
    echo "  [ok]   instructions: copilot-instructions.md"
}

echo "Installing agent-skills..."

if [[ "$TARGET" == "both" || "$TARGET" == "claude" ]]; then
    echo
    echo "-> Claude Code ($CLAUDE_SKILLS)"
    install_skills "$CLAUDE_SKILLS" "claude"
fi

if [[ "$TARGET" == "both" || "$TARGET" == "copilot" ]]; then
    echo
    echo "-> GitHub Copilot ($COPILOT_SKILLS)"
    install_skills "$COPILOT_SKILLS" "copilot"

    echo
    echo "-> VS Code Custom Agents & Instructions ($VSCODE_PROMPTS)"
    install_agents
    install_instructions
fi

echo
echo "Done. Restart VS Code to pick up new skills/agents."
