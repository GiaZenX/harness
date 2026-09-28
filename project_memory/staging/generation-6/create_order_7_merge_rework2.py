"""Order 7 merge REWORK 2 (TSK-0156's work-order fields are frozen once READY; re-planning is a new task, the
kernel's own remedy). Works on the MAIN working tree as TSK-0156 left it (uncommitted merge of A+B+C, stamp
2026.09.27-4). Usage: python create_order_7_merge_rework2.py"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

REWORK = (
    "CONTINUES TSK-0157 (CANCELLED for re-planning after its verifier's FAIL; the order-7 merge + rework 1 stay "
    "uncommitted in the main tree, stamp 2026.09.27-5 -- do NOT redo them). Read "
    "project_memory/staging/TSK-0157/verify-round-1.md by section. THE SMALLER PLAN, decided by the lead: "
    "(N1, BLOCKING) take rework 1's F3 pass OUT again -- gate_write_scope._upkeep_refusal refuses every SystemExit "
    "as before (no re-parse cleverness: stream B of the next wave replaces command-line guessing altogether); keep "
    "the silencing test ('Parsing prints nothing'); the test over N1's class (a `--help` the shell does not pass: "
    "<<<, <<, <>, $(: --help), <(echo --help)) must be rc 2 for all nine suffixes and RED against rework 1's pass; "
    "name 'upkeep --help refused to a subagent' as an over-refusal in the hole list of docs/POST_V2_WISHLIST.md "
    "(mechanism, measured chain, verdict). Mirrored x3. "
    "(N2) team-kits/kernel/dispatch.py create_lease clears CHILD_WAITING on a non-relet lease too (same reason as "
    "the comment there: a new lease is a new dispatch), and the sweep-leases line in kernel/cli.py names the "
    "task's no_progress_status instead of a hard-coded FAILED -- a test naming BUG-0326 over the verifier's chain "
    "(wait -> FAILED -> READY -> new lease -> sweep), red first. "
    "(N3) do NOT build: name 'a resumed child's kept lease is released by the next sweep' in the hole list with the "
    "verifier's measured chain (it goes to the heartbeat work of the next wave). Also MEASURE (do not fix) the "
    "unmeasured `_spawn_name_locked` suspicion (a kept waiting lease frees its spawn letter) and name it in the "
    "hole list only if it is real. Correct the protocol's rejection reason for 'sweep clears CHILD_WAITING' "
    "(dispatch needs CHILD_ENDED; the rejection stands on the unbound resumed child). F1 is NOT yours: the lead "
    "moves it to the approvals stream of the next wave. Reading suites of every changed predicate as their own "
    "selections (DEC-0080 rule 2), each with a timeout; ONE re-stamp at the end; validate + ruff; protocol section "
    "'Rework 2' in staging/TSK-0156/protocol.md as you go. The full run NOT started."
)
EXPECTED = (
    "rework 2: N1 closed by refusing --help again (nine-suffix test red against rework 1, green after) + the "
    "over-refusal named in the hole list; N2 fixed with a BUG-0326 test red first; N3 (and the spawn-letter "
    "suspicion if real) named in the hole list with measured chains; reading suites green with clock times; one "
    "re-stamp; validate + ruff clean; the full run NOT started"
)
INPUTS = [REWORK]
OUTPUTS = [EXPECTED]


def main():
    argv = list(KERNEL) + ["--product-requirement", "PR-0012", "--derives-from", "BUG-0325", "--type", "implementation",
                           "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-1",
                           "--rung", "opus", "--effort", "high",
                           "--dependency", "TSK-0153", "--dependency", "TSK-0154", "--dependency", "TSK-0155"]
    for p in ["team-kits/**", "tools/**", "docs/**", "README.md", "CLAUDE.md", "ladder.yaml",
              ".claude/hooks/test_gates.py", ".codex/agents/**", "install.ps1", "install.sh", ".gitattributes",
              "user/**"]:
        argv += ["--allowed-scope", p]
    for p in [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", ".claude/agents/**",
              "project_memory/**", "radar/**"]:
        argv += ["--forbidden-scope", p]
    for line in INPUTS:
        argv += ["--required-input", line]
    for line in OUTPUTS:
        argv += ["--expected-output", line]
    env = dict(os.environ, PYTHONPATH="team-kits")
    r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip()[-200:], r.stderr.strip()[-1200:] if r.returncode else "")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
