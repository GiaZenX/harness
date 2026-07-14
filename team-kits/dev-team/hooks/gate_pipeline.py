#!/usr/bin/env python3
"""
PreToolUse(Bash) — run the REAL quality pipeline before merge/push and block if it is red.

This is the deterministic teeth behind the Definition of Done. Instead of trusting a `result: pass`
string in a YAML, it executes `scripts/quality.py` (ruff/mypy/pytest+coverage, eslint/tsc/tests, secret/
dep scan) and blocks the merge/push on a non-zero exit. A missing pipeline is itself a block — the
pipeline MUST exist. Give this hook a generous `timeout` in settings.json (it runs tests).

Only fires on `git push`/`git merge`, only when real work exists (a PRD). Hook-execution errors (could
not even launch) -> exit 0 (never brick the repo on infra trouble); a RED pipeline -> exit 2.

Deliberate trade-off (documented after an audit flag): this gate re-runs the FULL pipeline
at merge/push even though QA just ran it - the merge gate is the last deterministic defense
and must not trust any prior run. A commit-hash cache of the last green run is a known
possible optimization, deferred until the cost hurts.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit


def block(why):
    _audit.record("gate_pipeline", why)
    sys.stderr.write("[team-kit gate] Blocked merge/push: %s\n" % why)
    sys.exit(2)


def read(path):
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
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        sys.exit(0)
    low = ((data.get("tool_input") or {}).get("command") or "").lower()
    if "git push" not in low and "git merge" not in low:
        sys.exit(0)

    root = find_repo_root(data.get("cwd"))
    pm = os.path.join(root, "project_memory")
    if not os.path.isdir(pm):
        sys.exit(0)
    if not re.search(r"\n\s*PRD-\d", read(os.path.join(pm, "product_requirements.yaml"))):
        sys.exit(0)  # no real work yet

    runner = os.path.join(root, "scripts", "quality.py")
    if not os.path.isfile(runner):
        block("no quality pipeline found (scripts/quality.py). DevOps must install it before merging — "
              "the merge gate runs the real linters/type-checkers/tests, it does not trust a report.")

    try:
        # subprocess limit is BELOW the hook's settings.json timeout, so we time out first and can BLOCK
        # rather than letting Claude Code kill a slow hook (a killed hook would NOT block — a silent pass).
        p = subprocess.run([sys.executable, runner], cwd=root,
                           capture_output=True, text=True, timeout=1500)
    except subprocess.TimeoutExpired:
        block("the quality pipeline did not finish within the time limit — speed up the test suite or "
              "merge a smaller change. A non-completing pipeline cannot be certified green.")
    except Exception:
        sys.exit(0)  # could not even launch (e.g. no python) -> do not brick the repo on infra trouble
    if p.returncode != 0:
        tail = "\n".join((p.stdout or "").splitlines()[-25:])
        block("the quality pipeline is RED (scripts/quality.py). Fix it before merging:\n" + tail)
    sys.exit(0)


if __name__ == "__main__":
    main()
