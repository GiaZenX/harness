#!/usr/bin/env python3
"""
SessionStart — inject project state so the Research Lead wakes up knowing the situation.

Reinforces the "session 1 = setup, session 2+ = work" model: when the project-manager
session agent starts, it is reminded that it IS the Research Lead, told the git branch,
and pointed at project_memory/ to read before acting. Stdlib + git only (no YAML
dependency), so it never fails on a fresh machine. Cannot block; emits additionalContext.
"""
import sys
import os
import json
import subprocess


def git(cwd, *args):
    try:
        r = subprocess.run(["git", "-C", cwd, *args],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    cwd = data.get("cwd") or os.getcwd()

    parts = ["You are the Research Lead (Project Manager) — the session agent the user talks to. Follow ./CLAUDE.md."]

    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        dirty = git(cwd, "status", "--porcelain")
        parts.append("Git branch: %s%s." % (branch, " (uncommitted changes present)" if dirty else " (clean)"))

    if os.path.isdir(os.path.join(cwd, "project_memory")):
        parts.append(
            "project_memory/ exists. BEFORE acting, read project_memory/progress.yaml, "
            "research_questions.yaml and any open experiment/review reports, then give the user a "
            "one-line status (active RQ, running experiments, pending validation) and ask what to do next. "
            "Also consult your agent memory."
        )
    else:
        parts.append(
            "No project_memory/ yet. If the user wants to start work, run your startup gate: create "
            "project_memory/ from the kit templates, confirm the team preset + per-specialist models, "
            "then proceed. Do not delegate before project_config.yaml exists."
        )

    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": " ".join(parts),
        }
    }
    sys.stdout.write(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
