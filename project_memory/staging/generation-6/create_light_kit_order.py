"""Generation 6, the ONE work order of the light kit (DEC-0087 (7), DEC-0093 (3)): generated FROM PR-0011 -- its
acceptance criteria become the expected_outputs verbatim, so the builder gets the whole goal and an outdated item
produces a visibly wrong order (CLAUDE.md, the rule that carries everything). Created in DRAFT after the
generation-5 commit; the lead measures check-scopes (TSK-0134 runs BEFORE it, sequentially, as the mechanical
slice on the opus rung -- DEC-0091 (1) -- so no two writers overlap), sets READY and spawns ONE Fable builder at
effort high. Not idempotent -- run once; read the id it prints."""
import io
import os
import subprocess
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]
GOAL = os.path.join(ROOT, "project_memory", "product", "active", "PR-0011.yaml")

ALLOWED = [
    "team-kits/**", "tools/**", "docs/**", "user/claude/CLAUDE.md", "user/codex/**",
    ".claude/agents/harness-lead.md", ".claude/agents/harness-implementer.md", ".claude/agents/harness-verifier.md",
    ".claude/hooks/test_gates.py", "README.md", "CLAUDE.md", "NOTICES.md",
]
FORBIDDEN = [
    ".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", "project_memory/**",
    "radar/20*.md", "radar/decided.md",
    # TSK-0134's files: delivered BEFORE this order runs; this order reads them, it does not rewrite them
    ".claude/agents/claude-watcher.md", ".claude/agents/codex-watcher.md", ".codex/agents/**",
]
INPUTS = [
    "PR-0011 (DRAFT at the cut, plan/scope mint deferred to the user's return by DEC-0093 (3)) -- the WHOLE goal: "
    "title, user story, problem, goal, the twelve ACs, invariants, out_of_scope; you build all of it, in the order "
    "the seams dictate (kernel contract first: TSK rung/effort fields and the dispatcher's max(); then the gate "
    "rule and the checkpoint; then the texts that describe them; then the entry file; the experiment arm last)",
    "The decisions this goal implements, each cited by the code that implements it (CLAUDE.md: a built file names "
    "its DEC): DEC-0087 (the light form), DEC-0088 (tiers per goal, cadence, cost discipline), DEC-0091 (rung/effort "
    "per order, max() with the ladder floor), DEC-0092 (no free-text field; structural gate; the fact-based "
    "checkpoint; distribution line; retrospective rule; pilot rig; the honest limit), DEC-0089/DEC-0090 (watcher duo "
    "-- delivered by TSK-0134 before you start: read its protocol, do not redo it), DEC-0093 (this order's mandate); "
    "DEC-0076/0077/0078 (three rungs, two axes, ladders per kit), DEC-0034 (escalation), DEC-0048 (ask again when a "
    "role is missing), DEC-0083 (a decision names its work), DEC-0050/DEC-0080 (test scope, the gen-4 rules)",
    "The defects this goal closes with their chains: BUG-0271 + BUG-0073 (the approval question: kernel/approvals.py "
    "build_question + TARGET_FORMS; gate_approval compares character for character; the value-language rule of "
    "BUG-0073 measured by test_role_contracts), BUG-0266/H184 (the auditor's read-only route: the `routine` "
    "approval kind, session_status/_routine.py, dispatch), FR-0089 + staging/FR-0089/*.md (the experiment design: "
    "same frontend task, two arms, tokens/wall-clock/rounds/the user's verdict -- you PREPARE both arms and run the "
    "kit arm; the user's verdict is his and waits)",
    "The committed generation-5 tree (the base): dev-team/research-team/office-team ladder.yaml, kernel/dispatch.py "
    "(ladder_for_order, create_lease, the escalation count), kernel/report.py (session brief, stock rollup, "
    "decision-carrier validator), kernel/backlog_types.py (TSK contract, TSK_PLAN_FIELDS), kernel/cli.py, the PM "
    "skills and constitutions with their ladder paragraphs (one bold statement carrying both axes -- G5-1's seam "
    "N18), user/claude/CLAUDE.md (the entry gate; FR-0048 lineage), tools/test_ladder.py / test_model_ladder.py / "
    "test_review_procedure.py / test_role_contracts.py / test_hooks*.py as the reading suites",
    "FR-0062 + kernel/gaplog.py + tools/harvest_kit_gaps.py (AC-11: the harvest runs from this repo against the "
    "three installed projects under C:/Offline Repos/ -- read-only on them; its state file lives here)",
    "HOST RULES: one pytest at a time, every run with a timeout, no CPU-saturating rig (four freezes measured); gate 5 "
    "live -- the full tools/ suite ONCE at the end with `DELIVERY_RUN=(this task id)`, after the stamp (DEC-0080 (5)); "
    "clock READ in every protocol time; scratch only under C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/",
    "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/; canonical state through the "
    "kernel only; the lead runs evidence / transitions / migrate-holes --reindex",
]
PROCESS_OUTPUTS = [
    "BUILT IN ITS OWN FORM (AC-10, DEC-0087 (7)): ONE builder (you, Fable high) with the whole goal; red-first per "
    "fix in a copy outside the repo; NO verifier during the build; ONE mid-goal check by the Opus verifier at the "
    "half (this goal is LARGE: you report 'half' when the kernel contract + gate + checkpoint are built and measured, "
    "before the texts and the entry file); ONE verifier round at the goal against the twelve ACs; at most one rework "
    "+ one short second round over failed ACs; the (g) table compares your tokens/rounds/wall-clock against "
    "generation 5's per-stream rows -- the first measurement of the form on itself.",
    "STAMP BEFORE THE FULL RUN: one release stamp across the three kits after the last change (tools/bump_kit_version.py), "
    "THEN the full tools/ suite ONCE with the delivery prefix, plus .claude/hooks/test_gates.py in full, ruff, "
    "tools/validate.py; every red a finding fixed red-first, then the suites that read the changed files, then ONE "
    "more stamp and ONE more full run.",
    "PROTOCOL in project_memory/staging/(this task id)/protocol.md: per AC the measured line (test name, red-first "
    "mutation, run), the seams touched, new holes through the kernel (`capture BUG --hole`, H189+; the lead runs "
    "`migrate-holes --reindex` after your last), the (g) table, the two EVD lines for the lead (state-relative "
    "artifact refs inside the repo, no digest), the user lines (plan/scope mint of PR-0011, the experiment's verdict, "
    "the four local routines, push, acceptance mints), the one-line rejected alternative. No commit, no push, no "
    "install into the user's projects (rollout = the update route at their next session start; you measure that "
    "the route WOULD carry the stamp, on a scaffolded pilot).",
]


def main():
    with io.open(GOAL, encoding="utf-8") as fh:
        goal = yaml.safe_load(fh)
    outputs = ["%s: %s" % (ac["id"], ac["text"]) for ac in goal["acceptance_criteria"]] + PROCESS_OUTPUTS
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0011", "--derives-from", "PR-0011",
        "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-1",
        "--dependency", "TSK-0134",
    ]
    for path in ALLOWED:
        argv += ["--allowed-scope", path]
    for path in FORBIDDEN:
        argv += ["--forbidden-scope", path]
    for line in INPUTS:
        argv += ["--required-input", line]
    for line in outputs:
        argv += ["--expected-output", line]
    env = dict(os.environ, PYTHONPATH="team-kits")
    result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    print(result.stdout.strip()[-600:])
    if result.returncode != 0:
        print(result.stderr.strip()[-1500:])
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
