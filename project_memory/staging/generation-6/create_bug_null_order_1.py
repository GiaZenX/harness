"""PR-0012 'Bug-Null', order 1 of three (sequential, one writer): AC-1 the BATCH verification mint (kernel) and AC-2
the measured-pass rows re-run and batched for the user. Order 2 = AC-3 (the real defects), order 3 = AC-4 (the
holes) follow after this one is delivered. Opus high (DEC-0095). Not idempotent -- run once."""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

ALLOWED = [
    "team-kits/kernel/approvals.py", "team-kits/kernel/cli.py", "team-kits/kernel/state.py",
    "team-kits/kernel/backlog_types.py", "team-kits/kernel/report.py", "team-kits/*/hooks/gate_approval.py",
    "team-kits/*/hooks/_kernel.py", "team-kits/*/skills/project-manager/SKILL.md",
    "team-kits/office-team/skills/office-manager/SKILL.md", "team-kits/*/constitution/AGENTS.md",
    "tools/test_approvals_dispatch.py", "tools/test_kernel.py", "tools/test_report.py", "tools/test_hooks.py",
    "tools/test_hooks_v2.py", "tools/test_e2e.py", "tools/close_measured_pass.py", "tools/test_close_measured_pass.py",
    "tools/lead_package_sizes.json", "docs/reviews/phase0-disposition.md", "docs/POST_V2_WISHLIST.md", "README.md",
    "CLAUDE.md",
]
FORBIDDEN = [
    ".claude/**", "project_memory/**", "user/**", "radar/**", "team-kits/*/settings/**", "team-kits/*/hooks/gate_*.py:except-gate_approval",
]
FORBIDDEN = [f for f in FORBIDDEN if ":except" not in f] + ["team-kits/*/hooks/gate_dispatch.py", "team-kits/*/hooks/gate_write_scope.py"]
INPUTS = [
    "PR-0012 AC-1 and AC-2 verbatim (product/active/PR-0012.yaml); DEC-0086 (the user's option A: a mint per bug -- "
    "this order builds its BATCH form; a DEC revising DEC-0086 is captured by the LEAD from your protocol's proposal, "
    "not by you); BUG-0090's rule (VERIFIED only on a passing test evidence naming the bug, run_scope declared)",
    "the BUG automaton (kernel/backlog_types.py: OPEN -> TRIAGED -> APPROVED -> FIXED -> VERIFIED; APPROVED needs the "
    "scope approval today) and the approval machinery (kernel/approvals.py: request-approval, build_question -- the "
    "German form of AC-7/PR-0011 -- gate_approval.py PreToolUse/PostToolUse compare + mint, TARGET_FORMS, the option "
    "description as the compared carrier of hash/id/path)",
    "staging/TSK-0131/survey-table.md: the 98 MEASURED-PASS rows with the test node that measured each (column 'first: "
    "tools/test_x.py::test_y') and the evidence refs of 2026-09-06; the store of 2026-09-11 (207 active BUGs; which of "
    "the 98 are still active)",
    "HOST RULES: one pytest NODE at a time with a timeout (the re-runs are ~98 single nodes -- ~10 s collection each; "
    "background them in one sequential script with a log under project_memory/staging/(this task id)/rerun.log, LF); "
    "gate 5 live: no full run inside this order; kit files change (approvals.py, gate_approval.py) -> ONE stamp after "
    "the last change; clock read; scratch under C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/; read end "
    "lines and named sections only (DEC-0095 (6))",
    "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/; every state write through the "
    "kernel (evidence lines you may run yourself for the re-runs -- they are measurements, not verdicts; the batch "
    "questions are asked by the LEAD, the mints are the user's)",
]
OUTPUTS = [
    "AC-1 BATCH VERIFICATION: `request-approval verification --batch BUG-a BUG-b ...` builds ONE pending request whose "
    "subject manifest lists every bug id with the evidence id that measured it; build_question renders a German "
    "sentence naming the count and the compared option text listing 'BUG-xxxx (EVD-yyyy)' per bug; a bug without a "
    "passing test evidence naming it, or not TRIAGED/OPEN, is refused from the batch BY NAME at request time; the mint "
    "(gate_approval PostToolUse, user's answer) walks each listed bug OPEN/TRIAGED -> APPROVED -> FIXED -> VERIFIED with "
    "the evidence as approval_ref/evidence ref and archives it; gate_approval still refuses a paraphrase or a tampered "
    "option (process test); red-first on the refusal, the walk, the archive; mirrored x3 where a kit file carries it; "
    "the PM skills' bug-closing step names the batch form.",
    "AC-2 THE RE-RUNS: tools/close_measured_pass.py reads survey-table.md, takes every MEASURED-PASS row whose item is "
    "still active, re-runs its named test node ONCE on the current tree (one at a time, timeout, log), records an EVD "
    "(kind test, result pass, run_scope selection, run-command = the node) on pass and NO evidence on fail (the row "
    "is listed as 'no longer passes' in the protocol), then prints the batches (<= 25 ids each) as the exact "
    "`request-approval verification --batch ...` lines for the lead; a bug whose row names no test is listed for AC-3.",
    "PROTOCOL in project_memory/staging/(this task id)/protocol.md: the rerun table (id, node, result, EVD), the batch "
    "lines for the lead, the red-first rows with the arbiter's line, the (g) row (tokens from your counter, wall-clock "
    "read), the patch path `git diff 07691ba`, the EVD lines for the lead, the DEC-0086 revision proposal (one "
    "paragraph the lead captures); no commit, no push, no mint.",
    "RUNS: tools/test_approvals_dispatch.py, test_kernel.py, test_report.py, test_close_measured_pass.py in full, "
    "test_hooks -k approval, test_hooks_v2 -k approval, one at a time; `python tools/bump_kit_version.py` once; ruff "
    "tools team-kits; validate.py.",
]


def main():
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0012", "--derives-from", "PR-0012",
        "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-1",
        "--rung", "opus", "--effort", "high",
    ]
    for p in ALLOWED:
        argv += ["--allowed-scope", p]
    for p in FORBIDDEN:
        argv += ["--forbidden-scope", p]
    for line in INPUTS:
        argv += ["--required-input", line]
    for line in OUTPUTS:
        argv += ["--expected-output", line]
    env = dict(os.environ, PYTHONPATH="team-kits")
    r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip()[-400:])
    if r.returncode != 0:
        print(r.stderr.strip()[-1200:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
