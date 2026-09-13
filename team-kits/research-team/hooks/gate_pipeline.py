#!/usr/bin/env python3
"""
PreToolUse(Bash|PowerShell) — run the REAL quality pipeline before merge/push and block if it is red.

This is the deterministic teeth behind the Definition of Done. Instead of trusting a `result: pass`
string in a YAML, it executes `scripts/quality.py` (ruff/mypy/pytest+coverage, eslint/tsc/tests, secret/
dep scan) and blocks the merge/push on a non-zero exit. A missing pipeline is itself a block — the
pipeline MUST exist. Its registration names a LARGE `timeout`, and BUG-0062 is why the number is
not free: a hook is killed at the window that governs it and a killed hook lets the refused call
through, so the window has to sit ABOVE this hook's own child limit -- which is the only kit hook
whose limit exceeds the provider's default (`_compat.HOOK_DEADLINE_SECONDS`). Bigger is not safer
either: the child limit is what turns a hanging suite into a refusal, and it only does so while it
is the smaller of the two.

Only fires on `git push`/`git merge`, only when real work exists (a PRD). Hook-execution errors (could
not even launch) -> exit 0 (never brick the repo on infra trouble); a RED pipeline -> exit 2.

Green-tree cache (the cost DID hurt: a real night re-ran the identical full pipeline 13 times):
after a GREEN run on a CLEAN working tree, the git tree hash is recorded in
.claude/.gate_pipeline_green; a later push with the SAME tree skips the re-run. Any dirty tree
or tree change runs the full pipeline as before — the gate never trusts a stale result. The
cache file is agent-write-blocked (guard_harness_selfmod), only this hook's own subprocess
writes it.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _compat
from _root import find_repo_root, has_root_item
from _compat import run_captured, wants_push_or_merge
import _audit


def block(why):
    # through `_compat.stop`, not a bare stderr write: that is the one funnel every refusal in the
    # kit goes through, and it is where a command whose git VERB the text does not fix gets the
    # sentence that says to spell the subcommand literally. Written by hand, this gate answered
    # `cd C:\src\git\repo` with "no quality pipeline found (scripts/quality.py)" and nothing else.
    _audit.record("gate_pipeline", why)
    _compat.stop("[team-kit gate] Blocked merge/push: %s\n" % why, "PreToolUse")


def read(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception:
        return ""


def main():
    # BOUNDED read (spec II.4). A raw `json.load(sys.stdin)` will happily buffer a
    # payload of any size, and an oversized one is the shape that turns a hook into
    # a memory event rather than a decision. `_compat.load` caps it at STDIN_LIMIT
    # and exits 2, because a gate that cannot read its input has not judged it.
    data = _compat.load()
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        sys.exit(0)
    # Detection lives in _compat.wants_push_or_merge (single home): applicability is decided on
    # the git SUBCOMMAND of a `git` word the shell would execute -- so no quoting, escaping, line
    # break or wrapper word spells the verb past this gate, and a verb the shell only builds at
    # run time counts as every verb. A commit MESSAGE about a push stays a message (it once
    # re-triggered the full pipeline), because it is an argument, not a word git was handed.
    if not wants_push_or_merge(((data.get("tool_input") or {}).get("command") or "")):
        sys.exit(0)

    root = find_repo_root(data.get("cwd"))
    pm = os.path.join(root, "project_memory")
    if not os.path.isdir(pm):
        sys.exit(0)
    if not has_root_item(root):
        sys.exit(0)  # no real work yet

    runner = os.path.join(root, "scripts", "quality.py")
    if not os.path.isfile(runner):
        block("no quality pipeline found (scripts/quality.py). DevOps must install it before merging — "
              "the merge gate runs the real linters/type-checkers/tests, it does not trust a report.")

    def clean_tree_hash():
        """Git tree hash IF the working tree is clean, else None (dirty trees always run)."""
        try:
            status = run_captured(["git", "-C", root, "status", "--porcelain"], timeout=30)
            if status.returncode != 0 or status.stdout.strip():
                return None
            tree = run_captured(["git", "-C", root, "rev-parse", "HEAD^{tree}"], timeout=30)
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
        # THE BOUND THAT MUST ARRIVE FIRST. This gate is the one hook of any kit whose own child
        # may outlive the provider's default window (measured ~600 s -- see
        # `_compat.HOOK_DEADLINE_SECONDS`), so its registration names a LARGER window on purpose
        # and this number has to stay under it: past the window the hook is killed, and a killed
        # gate lets the push it was refusing through, silently. Timing the child out HERE is what
        # turns a hanging pipeline into a refusal instead of that.
        # `tools/test_hooks.py::test_every_registration_names_a_window_its_gate_can_answer_inside`
        # reads this number off the running code and requires the registered window above it.
        # stdin=DEVNULL: the child must not inherit the hook's consumed payload pipe (node
        # tooling probes stdin). cwd comes from find_repo_root, which normalizes the Windows
        # drive-letter case — a lowercase c:\ cwd broke vite/rollup ONLY in this hook chain.
        # run_captured pins UTF-8: the runner writes UTF-8 (it reconfigures its own streams) —
        # the locale codec (cp1252) once killed the reader thread on the first ✓/❯ and the
        # block message lost the ENTIRE pipeline output (audit-proven: p.stdout came back None)
        p = run_captured([sys.executable, runner], cwd=root, timeout=1500,
                         stdin=subprocess.DEVNULL)
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
