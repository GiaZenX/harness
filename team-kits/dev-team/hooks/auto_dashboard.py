#!/usr/bin/env python3
"""
Stop hook — keeps the dashboard in sync with zero agent effort.

When the agent finishes a turn, if any project_memory/*.yaml is newer than
progress.dashboard.html (or the html is missing), regenerate it by running
generate_dashboard.py. Never blocks; failures are swallowed (exit 0 always).
"""
import sys
import os
import glob
import json
import subprocess


def main():
    cwd = os.getcwd()
    try:
        data = json.load(sys.stdin)
        cwd = data.get("cwd") or cwd
    except Exception:
        pass

    pm = os.path.join(cwd, "project_memory")
    gen = os.path.join(pm, "generate_dashboard.py")
    if not os.path.isfile(gen):
        sys.exit(0)

    yamls = glob.glob(os.path.join(pm, "*.yaml"))
    if not yamls:
        sys.exit(0)
    newest = max(os.path.getmtime(y) for y in yamls)

    html = os.path.join(pm, "progress.dashboard.html")
    if os.path.isfile(html) and os.path.getmtime(html) >= newest:
        sys.exit(0)  # already up to date

    try:
        subprocess.run([sys.executable, gen], cwd=pm, capture_output=True, timeout=60)
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
