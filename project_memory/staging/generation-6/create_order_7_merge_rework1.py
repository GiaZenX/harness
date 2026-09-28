"""Order 7 merge REWORK 1 (TSK-0156's work-order fields are frozen once READY; re-planning is a new task, the
kernel's own remedy). Works on the MAIN working tree as TSK-0156 left it (uncommitted merge of A+B+C, stamp
2026.09.27-4). Usage: python create_order_7_merge_rework1.py"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

REWORK = (
    "CONTINUES TSK-0156 (CANCELLED for re-planning; its merge stays uncommitted in the main tree -- do NOT redo it; its protocol is staging/TSK-0156/protocol.md). "

    "REWORK 1 (added 2026-09-27 16:5x by the lead after the verifier's FAIL, "
    "project_memory/staging/TSK-0156/verify-round-1.md -- read it by section): fix F4 = BUG-0326 "
    "(sweep_expired_leases strands CHILD_WAITING; the WAITING branch of dispatch names the FAILED way out) with a "
    "test naming BUG-0326, red first in a copy under the round-scratch dir, and run EVERY suite that reads the "
    "dispatch/lease predicates you change as its own selection (DEC-0080 rule 2: grep the callers). Also the low "
    "findings, since each is one site: F1 (tools/test_light_kit.py:890 comment vs the document-card read text that "
    "still shows a staging path -- fix the card or the comment, measured), F2 (tools/test_presets.py:712/:761 refer "
    "to the removed _preset_target_form), F3 (upkeep --help refused to a subagent; the 'Parsing prints nothing' "
    "claim gets a test that the silencing mutation turns red), F5 (kernel/__init__.py:12 'whichever route' vs a "
    "'.CLAUDE' import leaving .pyc -- make it true or say the limit). The verifier also saw "
    "test_gate1_places_a_tilde_word_where_the_shell_puts_it hang > 9:42 in real `bash -c` calls in its copy: "
    "run that node alone in the main tree with a timeout and record the time or the hang. Re-stamp once at the end. "
    "Protocol: append a 'Rework 1' section to staging/TSK-0156/protocol.md as you go."
)
EXPECTED = (
    "rework 1: BUG-0326 fixed with its naming test (red-before measured), F1/F2/F3/F5 closed or named as a limit, "
    "the reading suites of every changed predicate green with clock times, one re-stamp, validate + ruff clean, "
    "the full run NOT started"
)
INPUTS = [REWORK]
OUTPUTS = [EXPECTED]


def main():
    argv = list(KERNEL) + ["--product-requirement", "PR-0012", "--derives-from", "BUG-0326", "--type", "implementation",
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
