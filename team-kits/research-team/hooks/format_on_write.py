#!/usr/bin/env python3
"""
PostToolUse(Edit|Write) — auto-format the file a specialist just wrote (shift-left).

Best-effort: runs the matching formatter ONLY if it is installed, so unformatted code
never reaches the validation gate. Never blocks; any problem -> exit 0. The gate
(validity_criteria.yaml) stays the hard enforcement; this just keeps code clean in transit.

Skips project_memory/, .claude/, plans/ and other non-source paths so the PM's
hand-curated YAML state is never reformatted.

Lives in subagent frontmatter (the code-writers), because settings.json tool-hooks fire
only for the main agent, not for subagents.
"""
import sys
import os
import json
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


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") not in ("Edit", "Write"):
        sys.exit(0)
    inp = data.get("tool_input") or {}
    path = inp.get("file_path") or inp.get("path") or ""
    if not path or not os.path.isfile(path):
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    try:
        rel = os.path.relpath(path, cwd).replace("\\", "/")
    except Exception:
        rel = path
    if any(part in SKIP_DIRS for part in rel.split("/")):
        sys.exit(0)

    cands = FORMATTERS.get(os.path.splitext(path)[1].lower())
    if not cands:
        sys.exit(0)

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

    sys.exit(0)


if __name__ == "__main__":
    main()
