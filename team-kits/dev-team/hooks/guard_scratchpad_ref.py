#!/usr/bin/env python3
"""
PostToolUse(Edit|Write) — block repo source files that reference session-scratchpad paths.

A real run committed a fonts.css saying "Regenerate via scratchpad/vendor_fonts.py" — the tool
lived in the subagent's session scratchpad and is gone forever; the font pipeline stopped being
reproducible and no guard noticed. Scratchpads are session-ephemeral: any tool a repo file depends
on belongs in the repo (scripts/). Scope: source/tooling areas only (src, frontend, scripts, tests,
static, public + repo-root files) so docs/notes can still legitimately mention the word. Claude
uses exit 2; Codex uses a PostToolUse `decision: block` response; uncertainty -> allow.
"""
import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit
import _compat


MARKERS = ("scratchpad/", "scratchpad\\", "Temp/claude", "Temp\\claude")
AREAS = ("src", "frontend", "scripts", "tests", "static", "public")


def check(path, root):
    if not path or not os.path.isfile(path):
        return
    try:
        rel = os.path.relpath(path, root).replace("\\", "/")
    except ValueError:
        return  # different drive etc.
    if rel.startswith(".."):
        return  # outside the repo (e.g. the scratchpad itself)
    parts = rel.split("/")
    in_scope = parts[0] in AREAS or (len(parts) == 1 and not parts[0].startswith("."))
    if not in_scope:
        return

    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except Exception:
        return
    hits = [m for m in MARKERS if m in text]
    if not hits:
        return

    _audit.record("guard_scratchpad_ref", rel)
    message = (
        "[team-kit guard] %s references a session scratchpad path (%s). Scratchpads are EPHEMERAL — "
        "the referenced tool/asset will be gone next session and the pipeline stops being "
        "reproducible (a real fonts.css pointed at a vanished scratchpad/vendor_fonts.py). Put the "
        "tool into the repo (scripts/) and reference it there, then remove the scratchpad "
        "mention.\n" % (rel, ", ".join(hits))
    )
    _compat.stop(message, "PostToolUse")


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
