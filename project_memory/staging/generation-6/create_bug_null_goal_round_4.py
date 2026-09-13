"""PR-0012 'Bug-Null' -- the GOAL ROUND of order 4 (merge after TSK-0146 A kernel, TSK-0147 B kits, TSK-0148 C tools).
One builder on the whole tree: the reserved rows (known_holes.json, ONE stamp, the ONE full run with the delivery
prefix, test_gates.py as its own run, the stamp-dependent reds re-measured), the seam rows the streams could not
finish, the stale line pointers in docs/holes/H215.md turned into function names, then AC-5's accounting and the
lead's lines. Created DRAFT; READY when the three streams are closed. Opus high.
Usage: python create_bug_null_goal_round_4.py <base-commit> [<remaining-note>]"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

ALLOWED = ["team-kits/**", "tools/**", "docs/**", "user/**", "README.md", "CLAUDE.md", "HARNESS_LOG.md", "ladder.yaml",
           ".claude/hooks/test_gates.py", ".claude/agents/harness-implementer.md", ".claude/agents/harness-verifier.md",
           ".github/**", ".gitattributes", ".gitignore", "radar/README.md", "project_memory/project_config.yaml"]
FORBIDDEN = [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", "project_memory/**",
             "radar/20*.md", "radar/decided.md"]


def inputs(base, remaining):
    return [
        "THE STREAMS' PROTOCOLS as the record: staging/TSK-0146/protocol.md (A, kernel), staging/TSK-0147/protocol.md (B, kits), "
        "staging/TSK-0148/protocol.md (C, tools) and their verify-round-*.md; base commit %s; the streams' work is UNCOMMITTED in "
        "the tree (`git status`); PR-0012 AC-4/AC-5; DEC-0050 (the full run is yours, ONCE, after the last change); DEC-0102 "
        "(2)/(4)/(5); the decisions this order builds: DEC-0103, DEC-0105, DEC-0107, DEC-0108" % base,
        "RESERVED TO YOU: (1) team-kits/kernel/known_holes.json regenerated with tools/gen_known_holes.py, delta stated; (2) the "
        "hole index docs/POST_V2_WISHLIST.md is the LEAD's (`migrate-holes --reindex`) -- do not edit it; (3) docs/holes/H215.md "
        "names four hop-only sites by LINE NUMBER and three are stale (verifier C round 2): point at function names instead "
        "of lines, and check every other docs/holes/H21x.md this order wrote for the same defect; (4) the ONE stamp "
        "(`python tools/bump_kit_version.py`) after your last kit change, a second call says unchanged x3; (5) the ONE full run "
        "`DELIVERY_RUN=<this task id> python -B -m pytest tools/ -q` (last measured 68 min; expect the S4 arbiter and BUG-0297's "
        "remedy test red until the user's patch -- both named, no other red left unnamed), then `.claude/hooks/test_gates.py` "
        "as its own run; then the stamp-dependent reds the streams listed re-measured (H160/BUG-0242 among them: close or "
        "downgrade with its EVD); (6) SEAM ROWS the streams could not finish, each with the patch text in the named protocol: "
        "(a) wire B's gate_dispatch fail-class hook (TSK-0147) to A's kernel predicate `kernel.dispatch.fail_class_refusal(state, "
        "role, related, result, fail_class)` (TSK-0146 'Naht 1') so hook and kernel share ONE reader, process test against a "
        "pilot, then BUG-0260's line may be asked; (b) `withdraw-request` added behind `sweep-requests` in the three "
        "constitution/AGENTS.md par.0 and README.md:335 (TSK-0146 'Naht 2'; `tools/test_hooks.py::"
        "test_every_span_that_presents_the_command_surface_names_all_of_it` is red until then); (c) docs/office/"
        "invoice-app-docking-point.md par.7 still says 'von Hand buchen' -- replace with B's text (TSK-0147 'Naht 3'); (d) "
        "DEC-0105's repo side: write `ladder.yaml` at the repository root in the kits' declaration shape with roles "
        "harness-lead: planning, harness-implementer: build, harness-verifier: qa (ladder.yaml is in your allowed_scope); the "
        "config line `model_tiers: ladder.yaml` in project_memory/project_config.yaml is the USER's (gate 1) -- write the exact "
        "line into the lead file; the two role files keep their frontmatter pins (A's measurement); (e) two over-refusals "
        "verifier B round 2 named in the kits' gates, both in the three mirrored gate files: the DEC-0107 composed-word rule "
        "refuses a QUOTED expansion in value position on an evidence line (`--run-command \"$(cat cmd.txt)\"`, `--related "
        "\"$ID\"`) -- narrow it to UNQUOTED expansions (a quoted word cannot introduce an option), red-first with both "
        "directions; and `bash $(which ci.sh)` is refused with the sentence 'this line WRITES ci.sh' (the inner words of an "
        "unquoted substitution land in the WRITTEN set) -- refuse it as unplaceable or exclude substitution-internal stages "
        "from WRITTEN, red-first; the three QA role texts name the composed-word rule so the role is not surprised; (f) "
        "tools/test_approvals_dispatch.py::test_an_empty_origin_excuses_the_step_while_the_root_criteria_measure_it: its docstring "
        "names H155 as the remainder -- re-point it at BUG-0303 / H218 (the second class of BUG-0237, captured by the lead from "
        "TSK-0146's payload) in the first docstring line and the last paragraph, so closing BUG-0237 orphans nothing; (g) %s" % remaining,
        "HOST RULES (DEC-0094/0095 (6)): you are the only builder; one pytest at a time; selections while you build; the full run "
        "once; red-first in a .git-less copy under C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/; clock read for "
        "every time you write; protocol as you go in project_memory/staging/(this task id)/protocol.md; the half report is a "
        "protocol section, not a message",
        "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/ and project_memory/project_config.yaml "
        "(DEC-0105); state writes through the kernel only (an EVD per closed item with the naming node in the run command; the "
        "full run as ONE EVD kind test, run_scope full, related PR-0012); no transition of BUG items; no commit, no push, no mint",
    ]


OUTPUTS = [
    "The reserved and seam rows, one line each: id | change (file:line) | red-first row | naming node | EVD -- or the measured "
    "reason it is not yours.",
    "ONE stamp (three VERSION files, unchanged x3 on the second call); known_holes.json delta stated; H215.md pointers by name.",
    "THE FULL RUN: command, duration, counts, EVD id; every red fixed at mechanism (red-first) or named with its reason (the two "
    "user-patch reds by name); ruff over tools team-kits user; tools/validate.py green; generate-index = store; mirrors "
    "byte-identical; the research constitution under its ceiling (tools/lead_package_sizes.json).",
    "AC-5 PREPARED for the lead in staging/(this task id)/lead-lines.md: all verification batch lines of the three streams and "
    "yours (<= 10 ids each, dry-checked against a store copy inside a checkout, 0 refused); the questions that wait on the user "
    "by id with the protocol path of each (BUG-0296, H59); `report.stock_rollup` read after your run with the accounting.",
]


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: create_bug_null_goal_round_4.py <base-commit> [<remaining-note>]")
    base = sys.argv[1]
    remaining = sys.argv[2] if len(sys.argv) > 2 else "no further stream remainder handed over"
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0012", "--derives-from", "PR-0012",
        "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-4",
        "--acceptance-ref", "AC-5", "--dependency", "TSK-0146", "--dependency", "TSK-0147", "--dependency", "TSK-0148",
        "--rung", "opus", "--effort", "high",
    ]
    for p in ALLOWED:
        argv += ["--allowed-scope", p]
    for p in FORBIDDEN:
        argv += ["--forbidden-scope", p]
    for line in inputs(base, remaining):
        argv += ["--required-input", line]
    for line in OUTPUTS:
        argv += ["--expected-output", line]
    env = dict(os.environ, PYTHONPATH="team-kits")
    r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip()[-300:])
    if r.returncode != 0:
        print(r.stderr.strip()[-1500:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
