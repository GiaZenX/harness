#!/usr/bin/env python3
"""
PreToolUse(Bash) gate — protects merge/push.

- Force-push is ALWAYS blocked (the constitution forbids it).
- `git push` / `git merge` are blocked once there is real work
  (a PRD/RQ entry exists) but NO passing QA/validation report yet.
  Empty/just-scaffolded repos are not gated.

Reads the hook JSON from stdin; exit 2 + stderr blocks. Any uncertainty -> exit 0.
"""
import sys
import os
import re
import json
import glob


def block(why):
    sys.stderr.write("[team-kit gate] Blocked: %s\n" % why)
    sys.exit(2)


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception:
        return ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = ((data.get("tool_input") or {}).get("command") or "")
    low = cmd.lower()
    if "git push" not in low and "git merge" not in low:
        sys.exit(0)

    # force-push: always forbidden
    if "git push" in low and re.search(r"--force(-with-lease)?|(^|\s)-f(\s|$)", low):
        block("force-push is forbidden by the team constitution.")

    cwd = data.get("cwd") or os.getcwd()
    pm = os.path.join(cwd, "project_memory")
    if not os.path.isdir(pm):
        sys.exit(0)  # nothing to gate yet

    # is there real work? (a requirement/research-question entry exists)
    work = False
    for f in ("product_requirements.yaml", "research_questions.yaml"):
        if re.search(r"\n\s*(PRD|RQ)-\d", read_text(os.path.join(pm, f))):
            work = True
            break
    if not work:
        sys.exit(0)

    # is there at least one passing QA/validation/acceptance report?
    passing = False
    for f in glob.glob(os.path.join(pm, "*report*.yaml")):
        if re.search(r"result:\s*pass|verdict:\s*pass", read_text(f), re.IGNORECASE):
            passing = True
            break
    if not passing:
        block("no passing QA/validation report in project_memory yet — "
              "run the QA/reviewer gate (a passing review/test/acceptance report) before merge/push.")

    sys.exit(0)


if __name__ == "__main__":
    main()
