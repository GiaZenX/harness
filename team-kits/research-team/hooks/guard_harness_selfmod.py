#!/usr/bin/env python3
"""
PreToolUse(Edit|Write) — the enforcement layer must not be editable by the agents it enforces.

A real PM silently rewrote the kit settings via Bash to unblock its own spawns; the answer was a
prose rule (§2.10) — this guard is its mechanical backstop, and it applies to EVERY agent (main
AND subagents). Blocked via Edit/Write: `.claude/hooks/**`, `.claude/skills/**`,
`.claude/settings.json`, `.claude/settings.local.json` (hook-affecting overrides land there too —
security-review finding), `.claude/kit_version`, the provider ownership manifests, and the
constitution itself (root `AGENTS.md` + the `CLAUDE.md` import shim — self-rewritten instructions
are the documented compromise pattern).
    Provider control planes (`.codex/**`, `.agents/skills/**`, `.github/hooks/**`,
    `.github/agents/**`) and scaffold backups are protected too.
Paths compare case-INsensitively (Windows FS is;
`.CLAUDE/hooks/x` must not slip through). Still allowed: `.claude/agents/*.md` (the
documented model:/effort: resync), `.claude/agent-memory/**` (the memory feature writes there).
Bash writes bypass Edit/Write hooks — tripwire level, like guard_pm_scope; harness changes belong
in the KIT (via a kit update), never patched live in a project. Uncertainty -> exit 0.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit
import _compat


BLOCKED = ("hooks/", "skills/", "backups/")
BLOCKED_FILES = ("settings.json", "settings.local.json", "kit_version",
                 "provider_artifacts.json", "team_kit_roles.txt")
BLOCKED_PROVIDER_PREFIXES = (".codex/", ".agents/skills/", ".github/hooks/", ".github/agents/")


def block(rel):
    _audit.record("guard_harness_selfmod", rel)
    sys.stderr.write(
        "[team-kit guard] '%s' is part of the ENFORCEMENT LAYER — no agent edits it in a "
        "project, ever (a real PM silently rewrote kit settings to unblock itself). A guard "
        "that seems wrong is an infrastructure defect: report it to the user; the generic fix "
        "belongs in the KIT and arrives via a kit update. Generated .codex/** and "
        ".agents/skills/** are updated only by the scaffold. Allowed here: "
        ".claude/agents/*.md (model:/effort: resync) and .claude/agent-memory/**.\n" % rel
    )
    sys.exit(2)


def check(path, root):
    try:
        rel = os.path.relpath(path, root).replace("\\", "/")
    except ValueError:
        return
    rel_l = rel.lower()  # case-insensitive: the FS on Windows is, so the comparison must be too
    # the constitution itself (root AGENTS.md + the CLAUDE.md import shim) is enforcement
    # knowledge: an agent rewriting its own instructions is the documented compromise pattern
    # (instructions/memory rewritten outside any diff) — constitution changes arrive via kit
    # updates (scaffold), never via agent edits.
    if rel_l in ("agents.md", "claude.md"):
        block(rel)
    if any(rel_l.startswith(prefix) for prefix in BLOCKED_PROVIDER_PREFIXES):
        block(rel)
    if not rel_l.startswith(".claude/"):
        return
    sub = rel_l[len(".claude/"):]
    if any(sub.startswith(b) for b in BLOCKED) or sub in BLOCKED_FILES:
        block(rel)


def main():
    data = _compat.load()
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        sys.exit(0)
    root = find_repo_root(data.get("cwd"))
    for path in _compat.file_paths(data):
        check(path, root)
    sys.exit(0)


if __name__ == "__main__":
    main()
