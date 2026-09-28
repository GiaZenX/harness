"""Order 7 MERGE (TSK after the three streams TSK-0153/0154/0155). ONE builder brings the three worktree diffs into
the main working tree, applies the hand-overs, stamps ONCE, runs the reading suites; a fresh verifier judges the
merged package; the delivery run happens AFTER its PASS (DEC-0121 (1)).
Usage: python create_order_7_merge.py <base-commit>"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]
WT = "C:/Offline Repos/v2-testbed/_worktrees/"

INPUTS = [
    "BASE %s. THE THREE STREAMS left their work UNCOMMITTED in their worktrees (gate 3 of this repo measures the MAIN "
    "tree's digest and refused their commits -- a named limit, BUG to capture if not yet): %sg7-approvals (A, TSK-0153), "
    "%sg7-dispatch (B, TSK-0154), %sg7-field (C, TSK-0155), all from 35e929b. Bring each worktree's full diff against "
    "35e929b (staged + unstaged + untracked) into the MAIN working tree C:/Offline Repos/AgentAndSkills, one stream at a "
    "time (order: C, B, A -- A touches the most constitution text and goes last), resolving the declared seam (cli.py, "
    "skills, constitutions, README, docs, _compat/_kernel) hunk by hunk; say every conflict and its resolution in the "
    "protocol. Read each stream's protocol (project_memory/staging/TSK-015x/protocol.md) by section, especially its "
    "hand-over list." % ((sys.argv[1] if len(sys.argv) > 1 else "?"), WT, WT, WT),
    "HAND-OVERS to apply: from B -- tools/test_light_kit.py closed surface set gains `description`/`spawn_description` "
    "per DEC-0122 (cite it); tools/test_hooks_v2.py 'a running child is not swept': LEASED -> IN_PROGRESS; "
    "tools/test_board.py register line for bind_agent_by_role; the section re-pin (`python tools/pin_constitution_"
    "sections.py --write --note ...`) and the lead-package size re-record ONCE after all text is merged; the FR-0093 line "
    "in .claude/agents/harness-lead.md is the USER's file -> one site in a user-patch file (with DEC-0120's redirect "
    "refusal for H47/BUG-0139, which is still owed: build its test in .claude/hooks/test_gates.py red-before/green-after "
    "and the patch site). From C -- tools/test_hooks_v2.py::test_the_trust_message_names_a_remedy_that_actually_leaves_"
    "the_state needs a new trigger (plant a .pyc directly; BUG-0310 now prevents the cache it relied on). From A -- see its "
    "protocol's 'Finish' section.",
    "A NEW HOLE to bound (C's own finding): `kernel.cli upkeep` (prune-caches / resolve-pending / adopt-template / "
    "untrack-ignored / prune-memory) is callable by a SUBAGENT and prune-memory can delete ANOTHER role's craft memory. "
    "Bound it on the running path: the doors that change shared or other roles' state are refused to a subagent (the "
    "dispatch/lease context tells who calls), prune-memory only for the caller's own role or the lead -- a test naming "
    "the new BUG you capture for it (--hole), red-first.",
    "RULES: DEC-0100, DEC-0116, DEC-0121 (resolved paths; new commands join their registers; protocol as you go; NO full "
    "run before the verifier's PASS), DEC-0080 rule 2 (every suite that reads a changed rule as its own selection), "
    "DEC-0102 (4). Kit hooks mirrored x3.",
    "PROCESS: ONE stamp after the merge is complete (`python tools/bump_kit_version.py`), then the reading suites, "
    "one pytest at a time, long ones in the background with a completion wait; red-first copies under "
    "C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/; protocol as you go in project_memory/staging/(this task "
    "id)/protocol.md; state through the kernel only; no commit, no push, no mint, no BUG transitions.",
]
OUTPUTS = [
    "the main working tree holds A+B+C, every seam conflict named with its resolution; the three streams' naming tests "
    "green in the merged tree (list the nodes)",
    "the hand-overs applied (DEC-0122 test change, LEASED->IN_PROGRESS, register line, trust-message trigger, one re-pin "
    "+ one size re-record); the upkeep bound with its test and BUG; the user-patch file for harness-lead.md (FR-0093 "
    "line) + H47 (DEC-0120) with --check green on the current tree and the H47 test in test_gates.py",
    "one stamp; the reading suites with results and clock times; validate + ruff clean; the full run NOT started",
]


def main():
    base = sys.argv[1]
    argv = list(KERNEL) + ["--product-requirement", "PR-0012", "--derives-from", "PR-0012", "--type", "implementation",
                           "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-1",
                           "--rung", "opus", "--effort", "high",
                           "--dependency", "TSK-0153", "--dependency", "TSK-0154", "--dependency", "TSK-0155"]
    for p in ["team-kits/**", "tools/**", "docs/**", "README.md", "CLAUDE.md", "ladder.yaml",
              ".claude/hooks/test_gates.py", ".codex/agents/**", "install.ps1", "install.sh", ".gitattributes"]:
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
