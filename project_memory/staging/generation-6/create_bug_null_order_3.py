"""PR-0012 'Bug-Null', order 3 of three: AC-4 -- the hole items (BUG with hole_number), each closed red-first at the
mechanism it names, or written up as an exception (why unclosable, what bounds it) for the user's ACCEPTED_EXCEPTION
batches by mechanism class; plus the five pre-existing red nodes TSK-0139 found on fd7e2fa (assigned here by the
lead unless the check says otherwise) and AC-5 (stock lies upward 0, index = store, one stamp, the full run is the
goal round's). Created in DRAFT while order 2 is checked; READY after its commit. Opus high. Usage:
python create_bug_null_order_3.py <base-commit>"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

ALLOWED = ["team-kits/**", "tools/**", "docs/**", "user/**", "README.md", "CLAUDE.md", ".claude/hooks/test_gates.py",
           ".github/**", ".gitattributes", ".gitignore", "radar/README.md"]
FORBIDDEN = [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", ".claude/agents/**",
             "project_memory/**", "radar/20*.md", "radar/decided.md", "team-kits/*/settings/settings.json"]


def inputs(base):
    return [
        "PR-0012 AC-4 and AC-5 verbatim; DEC-0100 (a bug closes only on a test that NAMES it -- docstring first "
        "paragraph or parametrize id); the house rule of CLAUDE.md: a hole is CLOSED or carries a user-accepted "
        "exception with (why unclosable) and (what bounds it) -- no third state; H195/BUG-0279 (incidental mention)",
        "the store after order 2 (base commit %s): every BUG with `hole_number` in bugs/active (~126, 0 high / ~59 "
        "medium / ~67 low), each with mechanism, chain, verdict and `limits` from its capture; docs/POST_V2_WISHLIST.md "
        "= the generated index; the survey rows (staging/TSK-0131/survey-table.md: OPEN-BY-DESIGN 52, UNMEASURED, the "
        "46 measured-pass holes that no test names); TSK-0138/0139 protocols only for the ids they hand over" % base,
        "the five PRE-EXISTING red nodes on fd7e2fa that TSK-0139 found and did not fix: "
        "test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it, "
        "test_every_approval_refusal_the_hook_can_surface_speaks_to_the_user, "
        "test_the_lead_of_a_scaffolded_project_is_not_read_as_its_own_subagent, "
        "test_the_research_chain_runs_from_the_question_to_a_merge_through_the_shipped_hooks, "
        "test_no_section_of_a_pinned_instruction_file_disappears_unnoticed (the section pins: re-pin ONLY after "
        "reading what drifted and saying it, never silently) -- unless the order-2 check assigned them elsewhere (the "
        "lead says at READY)",
        "HOST RULES (DEC-0094/0095 (6)): one pytest at a time with timeouts derived from measured durations; reading "
        "suites per fix; NO full run inside the order (AC-5's full run is the goal round's, after ONE stamp); red-first "
        "in a copy without .git under C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/ with the arbiter's line "
        "per row; clock read; read each hole's item and `limits`, not the protocols; protocol as you go",
        "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/; state writes through the "
        "kernel: an EVD per closed hole (kind test, run_scope selection, the naming nodes); the exception batches "
        "are LISTS in the protocol -- id | mechanism | why unclosable | bound -- grouped by mechanism class (over-"
        "refusals of gate 1; enumerations awaiting a definition; provider limits; measurement-instrument limits; "
        "by-design bounds), at most 10 per list, the lead asks the user one question per list (the kernel's batch "
        "route extended to ACCEPTED_EXCEPTION is part of THIS order if `verification --batch` cannot carry it -- say "
        "which)",
    ]


OUTPUTS = [
    "TRIAGE TABLE FIRST (before any fix): every hole id with its class, its `limits`, and the verdict CLOSE / EXCEPTION "
    "/ ALREADY-CLOSED (a test names it and measures the gap gone) -- the lead reads this table at your HALF report "
    "and may re-cut; then the fixes in class order, cheapest class first.",
    "CLOSED holes: each red-first with a test that NAMES the hole's bug id (DEC-0100), the reading suites of the "
    "changed files, an EVD through the kernel; the index row moves with the store (`migrate-holes --reindex` is the "
    "lead's line -- say when).",
    "EXCEPTION lists: for every hole not closed, one row -- id | mechanism | why unclosable (a measured reason, not "
    "'later') | what bounds it today -- grouped by class, <= 10 per list, as the exact kernel lines the lead runs "
    "(`request-approval exception --batch ...` or the shape the kernel carries -- if none carries ACCEPTED_EXCEPTION "
    "in a batch, build it in kernel/approvals.py the way `verification` was built, red-first, mirrored).",
    "THE FIVE PRE-EXISTING REDS: each fixed at its mechanism or measured as the goal round's finding with the reason "
    "(the pinned-sections test: what drifted, said in the protocol, then re-pinned once).",
    "AC-5 PREPARED: report.stock_rollup reads `stock lies upward: 0` after the batches; index = store; ONE stamp after "
    "the last kit change; ruff tools team-kits; validate.py; the (g) row; the patch path; EVD lines; no commit, no "
    "push, no mint; the FULL run is the goal round's -- do not run it.",
]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: create_bug_null_order_3.py <base-commit>")
    base = sys.argv[1]
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0012", "--derives-from", "PR-0012",
        "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-4",
        "--dependency", "TSK-0139", "--rung", "opus", "--effort", "high",
    ]
    for p in ALLOWED:
        argv += ["--allowed-scope", p]
    for p in FORBIDDEN:
        argv += ["--forbidden-scope", p]
    for line in inputs(base):
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
