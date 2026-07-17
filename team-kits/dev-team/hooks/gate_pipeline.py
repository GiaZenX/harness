#!/usr/bin/env python3
"""
PreToolUse(Bash) — run the REAL quality pipeline before merge/push and block if it is red.

This is the deterministic teeth behind the Definition of Done. Instead of trusting a `result: pass`
string in a YAML, it executes `scripts/quality.py` (ruff/mypy/pytest+coverage, eslint/tsc/tests, secret/
dep scan) and blocks the merge/push on a non-zero exit. A missing pipeline is itself a block — the
pipeline MUST exist. Give this hook a generous `timeout` in settings.json (it runs tests).

Only fires on `git push`/`git merge`, only when real work exists (a PRD). Hook-execution errors (could
not even launch) -> exit 0 (never brick the repo on infra trouble); a RED pipeline -> exit 2.

Green-tree cache (the cost DID hurt: a real night re-ran the identical full pipeline 13 times):
after a GREEN run on a CLEAN working tree, the git tree hash is recorded in
.claude/.gate_pipeline_green; a later push with the SAME tree skips the re-run. Any dirty tree
or tree change runs the full pipeline as before — the gate never trusts a stale result. The
cache file is agent-write-blocked (guard_harness_selfmod), only this hook's own subprocess
writes it.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
from _compat import wants_push_or_merge
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
    # Detection lives in _compat.wants_push_or_merge (single home): wrapper payloads are CODE,
    # quoted prose is not — a commit MESSAGE once re-triggered the full pipeline (real incident).
    if not wants_push_or_merge(((data.get("tool_input") or {}).get("command") or "")):
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

    def clean_tree_hash():
        """Git tree hash IF the working tree is clean, else None (dirty trees always run)."""
        try:
            status = subprocess.run(["git", "-C", root, "status", "--porcelain"],
                                    capture_output=True, text=True, timeout=30)
            if status.returncode != 0 or status.stdout.strip():
                return None
            tree = subprocess.run(["git", "-C", root, "rev-parse", "HEAD^{tree}"],
                                  capture_output=True, text=True, timeout=30)
            return tree.stdout.strip() if tree.returncode == 0 else None
        except Exception:
            return None

    cache_path = os.path.join(root, ".claude", ".gate_pipeline_green")
    tree_hash = clean_tree_hash()
    if tree_hash:
        try:
            if open(cache_path, encoding="utf-8").read().strip() == tree_hash:
                _audit.record_event("gate_pipeline", "cache_hit",
                                    "tree %s already certified green" % tree_hash[:12])
                sys.exit(0)
        except Exception:
            pass

    try:
        # subprocess limit is BELOW the hook's settings.json timeout, so we time out first and can BLOCK
        # rather than letting Claude Code kill a slow hook (a killed hook would NOT block — a silent pass).
        # stdin=DEVNULL: the child must not inherit the hook's consumed payload pipe (node
        # tooling probes stdin). cwd comes from find_repo_root, which normalizes the Windows
        # drive-letter case — a lowercase c:\ cwd broke vite/rollup ONLY in this hook chain.
        # encoding pinned: the runner writes UTF-8 (it reconfigures its own streams) — reading
        # it with the locale codec (cp1252) killed the reader thread on the first ✓/❯ and the
        # block message lost the ENTIRE pipeline output (audit-proven: p.stdout came back None)
        p = subprocess.run([sys.executable, runner], cwd=root,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1500)
    except subprocess.TimeoutExpired:
        block("the quality pipeline did not finish within the time limit — speed up the test suite or "
              "merge a smaller change. A non-completing pipeline cannot be certified green.")
    except Exception:
        sys.exit(0)  # could not even launch (e.g. no python) -> do not brick the repo on infra trouble
    if p.returncode != 0:
        # FAIL lines FIRST: the plain last-25-lines tail once showed only PASS/warn lines while
        # the actual red check sat above the cut — a night of misdiagnosis followed.
        lines = (p.stdout or "").splitlines()
        fails = [ln for ln in lines if re.search(r"\bFAIL\b|\bERROR\b", ln)][:15]
        tail = "\n".join(fails + ["--- last output lines: ---"] + lines[-10:])
        block("the quality pipeline is RED (scripts/quality.py). Fix it before merging:\n" + tail)
    if tree_hash:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(tree_hash + "\n")
        except Exception:
            pass
    sys.exit(0)


if __name__ == "__main__":
    main()
