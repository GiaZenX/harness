#!/usr/bin/env python3
"""
PreToolUse(Edit|Write) — the enforcement layer must not be editable by the agents it enforces.

A real PM silently rewrote the kit settings via Bash to unblock its own spawns; the answer was a
prose rule (§2.10) — this guard is its mechanical backstop, and it applies to EVERY agent (main
AND subagents). Blocked via Edit/Write: `.claude/hooks/**`, `.claude/skills/**`,
`.claude/settings.json`, `.claude/kit_version`. Still allowed: `.claude/agents/*.md` (the
documented model:/effort: resync), `.claude/agent-memory/**` (the memory feature writes there).
Bash writes bypass Edit/Write hooks — tripwire level, like guard_pm_scope; harness changes belong
in the KIT (via a kit update), never patched live in a project. Uncertainty -> exit 0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit


BLOCKED = ("hooks/", "skills/")
BLOCKED_FILES = ("settings.json", "kit_version")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        sys.exit(0)
    path = ((data.get("tool_input") or {}).get("file_path")
            or (data.get("tool_input") or {}).get("path") or "")
    if not path:
        sys.exit(0)
    root = find_repo_root(data.get("cwd"))
    try:
        rel = os.path.relpath(path, root).replace("\\", "/")
    except ValueError:
        sys.exit(0)
    if not rel.startswith(".claude/"):
        sys.exit(0)
    sub = rel[len(".claude/"):]
    if any(sub.startswith(b) for b in BLOCKED) or sub in BLOCKED_FILES:
        _audit.record("guard_harness_selfmod", rel)
        sys.stderr.write(
            "[team-kit guard] '%s' is part of the ENFORCEMENT LAYER — no agent edits it in a "
            "project, ever (a real PM silently rewrote kit settings to unblock itself). A guard "
            "that seems wrong is an infrastructure defect: report it to the user; the generic fix "
            "belongs in the KIT and arrives via a kit update. Allowed here: .claude/agents/*.md "
            "(model:/effort: resync) and .claude/agent-memory/**.\n" % rel
        )
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
