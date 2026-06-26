#!/usr/bin/env bash
# Scaffold a team kit into the current repository (Unix).
# Usage: scaffold_team.sh dev-team
# Copies the kit's agents into ./.claude/agents/ and its constitution into ./CLAUDE.md.
# project_memory/ is NOT created here — the PM creates it from the global templates at startup.
set -euo pipefail

TEAM="${1:-}"
if [ -z "$TEAM" ]; then
  echo "Usage: scaffold_team.sh <team>" >&2
  exit 1
fi

KIT="$HOME/.claude/team-kits/$TEAM"
if [ ! -d "$KIT" ]; then
  echo "Team kit not found: $KIT" >&2
  exit 1
fi

REPO="$(pwd)"
echo "Scaffolding team '$TEAM' into $REPO"

mkdir -p "$REPO/.claude/agents"
for f in "$KIT"/agents/*.md; do
  [ -e "$f" ] || continue
  cp -f "$f" "$REPO/.claude/agents/$(basename "$f")"
  echo "  [ok] agent: $(basename "$f")"
done

if [ -f "$KIT/constitution/CLAUDE.md" ]; then
  cp -f "$KIT/constitution/CLAUDE.md" "$REPO/CLAUDE.md"
  echo "  [ok] CLAUDE.md (local constitution)"
fi

# Enforcement layer: hooks + settings.json travel with the team.
if [ -d "$KIT/hooks" ]; then
  mkdir -p "$REPO/.claude/hooks"
  for f in "$KIT"/hooks/*; do
    [ -e "$f" ] || continue
    cp -f "$f" "$REPO/.claude/hooks/$(basename "$f")"
    echo "  [ok] hook: $(basename "$f")"
  done
fi
if [ -f "$KIT/settings/settings.json" ]; then
  if [ -f "$REPO/.claude/settings.json" ]; then
    echo "  [skip] .claude/settings.json exists — merge hooks manually"
  else
    mkdir -p "$REPO/.claude"
    cp -f "$KIT/settings/settings.json" "$REPO/.claude/settings.json"
    echo "  [ok] .claude/settings.json (enforcement hooks)"
  fi
fi

echo "Team '$TEAM' installed locally. The main agent is now your Project Manager — just keep prompting."
