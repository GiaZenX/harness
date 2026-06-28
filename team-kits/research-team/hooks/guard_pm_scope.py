#!/usr/bin/env python3
"""
PreToolUse(Edit|Write) — keep the PM out of production code.

settings.json tool-hooks fire only for the MAIN agent (the PM), not for subagents, so
this hook blocks the PM (and only the PM) from writing code: a real run had the PM make
~60 self-edits instead of delegating. Code goes to specialist subagents; QA gates it.

Allowed for the PM: project_memory/**, .claude/** (it rewrites specialist model frontmatter),
plans/**, docs/** and root config/markdown. Blocked: src/**, tests/**, frontend/** and other
code areas, plus root-level code files. Uncertainty -> exit 0 (never block legitimate upkeep).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit

ALLOW_TOP = {"project_memory", ".claude", "plans", "docs"}
BLOCK_TOP = {"src", "tests", "test", "frontend", "backend", "lib", "server",
             "app", "packages", "cmd", "internal", "api", "ui", "web"}
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".c",
            ".cpp", ".h", ".hpp", ".rb", ".php", ".cs", ".kt", ".swift", ".vue", ".svelte"}


def block(rel):
    _audit.record("guard_pm_scope", rel)
    sys.stderr.write(
        "[team-kit guard] PM blocked from writing '%s'.\n"
        "You are the Project Manager — you do NOT write production code (src/**, tests/**, "
        "frontend/**). Delegate this to the matching specialist subagent; QA gates it. "
        "You may write project_memory/*.yaml, ./.claude/**, docs/ and plans/.\n" % rel
    )
    sys.exit(2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") not in ("Edit", "Write"):
        sys.exit(0)
    inp = data.get("tool_input") or {}
    path = inp.get("file_path") or inp.get("path") or ""
    if not path:
        sys.exit(0)

    root = find_repo_root(data.get("cwd"))
    try:
        rel = os.path.relpath(path, root)
    except Exception:
        sys.exit(0)
    rel = rel.replace("\\", "/").lstrip("./")
    if rel.startswith("../"):
        sys.exit(0)  # outside the repo -> not our business
    segs = [s for s in rel.split("/") if s]
    if not segs:
        sys.exit(0)
    top = segs[0]

    if top in ALLOW_TOP:
        sys.exit(0)
    if top in BLOCK_TOP:
        block(rel)
    # root-level code file (e.g. app.py, server.py, main.ts)
    if len(segs) == 1 and os.path.splitext(top)[1].lower() in CODE_EXT:
        block(rel)
    sys.exit(0)


if __name__ == "__main__":
    main()
