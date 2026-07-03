#!/usr/bin/env python3
"""
SessionStart — inject project state so the PM wakes up knowing the situation.

Reinforces the "session 1 = setup, session 2+ = work" model: when the project-manager
session agent starts, it is reminded that it IS the PM, told the git branch, and pointed
at project_memory/ to read before acting. Stdlib + git only (no YAML dependency), so it
never fails on a fresh machine. Cannot block; emits additionalContext.
"""
import sys
import os
import json
import re
import subprocess


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root


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
    cwd = find_repo_root(data.get("cwd"))

    parts = ["You are the Project Manager — the session agent the user talks to. Follow ./CLAUDE.md."]

    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        dirty = git(cwd, "status", "--porcelain")
        parts.append("Git branch: %s%s." % (branch, " (uncommitted changes present)" if dirty else " (clean)"))

    if os.path.isdir(os.path.join(cwd, "project_memory")):
        parts.append(
            "project_memory/ exists. BEFORE acting, read project_memory/progress.yaml, "
            "product_requirements.yaml and any open review/test/acceptance reports, then give the user a "
            "one-line status (active PRD, open tasks, pending QA) and ask what to do next. "
            "Also consult your agent memory."
        )
    else:
        parts.append(
            "No project_memory/ yet. If the user wants to start work, run your startup gate: create "
            "project_memory/ from the kit templates, confirm the team preset + per-specialist models, "
            "then proceed. Do not delegate before project_config.yaml exists."
        )

    # kit-update detection: compare the repo's installed kit stamp with the staged kit version.
    try:
        kit = ""
        cpath = os.path.join(cwd, "CLAUDE.md")
        if os.path.isfile(cpath):
            with open(cpath, encoding="utf-8", errors="ignore") as fh:
                m = re.search(r"agents-and-skills:team-kit\s+([\w-]+)", fh.readline())
            kit = m.group(1) if m else ""
        if kit:
            staged_p = os.path.join(os.path.expanduser("~"), ".claude", "team-kits", kit, "VERSION")
            local_p = os.path.join(cwd, ".claude", "kit_version")
            staged = open(staged_p, encoding="utf-8").read().strip() if os.path.isfile(staged_p) else ""
            local = open(local_p, encoding="utf-8").read().strip() if os.path.isfile(local_p) else ""
            if staged and staged != local:
                lv = local.splitlines()[0].replace("version: ", "") if local else "no version stamp"
                sv = staged.splitlines()[0].replace("version: ", "")
                parts.append(
                    "KIT UPDATE AVAILABLE: the staged '%s' kit (%s) differs from this repo's installed kit "
                    "(%s) — usually a newer harness. Propose the update to the user; on their OK run the "
                    "scaffold_team script and then init_project_memory (both safe: backup first, "
                    "copy-if-absent — project_memory content is NEVER overwritten), then ask for a session "
                    "restart. Never hand-merge harness files. After updating, gates may require newly added "
                    "fields in existing YAMLs — fill those small deltas." % (kit, sv, lv)
                )
    except Exception:
        pass

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
