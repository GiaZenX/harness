#!/usr/bin/env python3
"""
PostToolUse(Edit|Write) — auto-format the file a specialist just wrote (shift-left).

Best-effort: runs the matching formatter ONLY if it is installed, so unformatted code
never reaches the QA pipeline gate. Never blocks; any problem -> exit 0. The pipeline
gate (definition_of_done.yaml) stays the hard enforcement; this just keeps code clean
in transit.

Skips project_memory/, .claude/, plans/ and other non-source paths so the PM's
hand-curated YAML state is never reformatted.

Lives in subagent frontmatter (the code-writers) to scope it to the roles that write CODE.
NOTE (verified): settings.json tool-hooks fire for the main agent AND all subagents —
frontmatter placement is for per-role scoping, NOT because settings hooks would skip subagents.
"""
import sys
import os
import shutil
import subprocess

# extension -> ordered candidate formatter argv (first available wins); {f} = file path.
FORMATTERS = {
    ".py": [["ruff", "format", "{f}"], ["black", "{f}"]],
    ".js": [["prettier", "--write", "{f}"]],
    ".jsx": [["prettier", "--write", "{f}"]],
    ".ts": [["prettier", "--write", "{f}"]],
    ".tsx": [["prettier", "--write", "{f}"]],
    ".mjs": [["prettier", "--write", "{f}"]],
    ".css": [["prettier", "--write", "{f}"]],
    ".scss": [["prettier", "--write", "{f}"]],
    ".html": [["prettier", "--write", "{f}"]],
    ".json": [["prettier", "--write", "{f}"]],
    ".go": [["gofmt", "-w", "{f}"]],
    ".rs": [["rustfmt", "{f}"]],
}
SKIP_DIRS = ("project_memory", ".claude", "plans", "node_modules", ".git", "dist", "build")


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _compat


def fmt(path, cwd):
    if not path or not os.path.isfile(path):
        return
    try:
        rel = os.path.relpath(path, cwd).replace("\\", "/")
    except Exception:
        rel = path
    if any(part in SKIP_DIRS for part in rel.split("/")):
        return

    cands = FORMATTERS.get(os.path.splitext(path)[1].lower())
    if not cands:
        return

    for cmd in cands:
        exe = cmd[0]
        runner = None
        if shutil.which(exe):
            runner = [c.replace("{f}", path) for c in cmd]
        elif exe == "prettier" and shutil.which("npx"):
            runner = ["npx", "--no-install", "prettier", "--write", path]
        if runner:
            try:
                subprocess.run(runner, cwd=cwd, capture_output=True, timeout=60)
            except Exception:
                pass
            break  # a formatter for this extension was found; stop


def main():
    data = _compat.load()
    allowed_roles = {role for role in os.environ.get("TEAM_KIT_AGENT_TYPES", "").split(",")
                     if role}
    if allowed_roles and str(data.get("agent_type") or "") not in allowed_roles:
        sys.exit(0)
    if data.get("tool_name") not in ("Edit", "Write"):
        sys.exit(0)
    cwd = find_repo_root(data.get("cwd"))
    for path in _compat.file_paths(data):
        fmt(path, cwd)
    sys.exit(0)


if __name__ == "__main__":
    main()
