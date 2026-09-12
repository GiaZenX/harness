"""PR-0012 'Bug-Null' -- the GOAL ROUND (merge order) after the three parallel 3b streams (TSK-0141 A kernel, TSK-0142
B kits, TSK-0143 C tools). One builder on the whole tree, sequential: everything the streams RESERVED to the merge
(the shared files, DEC-0070 (1)) plus the seam rows no stream could own, then ONE stamp, then the ONE full run
(DEC-0050: the delivery criterion, once, after the last rework), then AC-5's accounting. Created DRAFT; READY when the
three streams are closed. Opus high. Usage: python create_bug_null_goal_round.py <base-commit> [<remaining-holes-note>]"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

ALLOWED = ["team-kits/**", "tools/**", "docs/**", "user/**", "README.md", "CLAUDE.md", "HARNESS_LOG.md",
           ".claude/hooks/test_gates.py", ".github/**", ".gitattributes", ".gitignore", "radar/README.md"]
FORBIDDEN = [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", ".claude/agents/**",
             "project_memory/**", "radar/20*.md", "radar/decided.md", "team-kits/*/settings/settings.json"]


def inputs(base, remaining):
    return [
        "THE STREAMS' PROTOCOLS as the record of what was built and what was reserved to you: staging/TSK-0141/protocol.md "
        "(A, kernel, 4 verify rounds, PASS), staging/TSK-0142/protocol.md (B/B2/B3, kits), staging/TSK-0143/protocol.md "
        "(C, tools, PASS) and their verify-round-*.md; base commit %s (the streams' work is UNCOMMITTED in the tree -- read "
        "`git status`); PR-0012 AC-4/AC-5 verbatim; DEC-0100; DEC-0050 (the full run is yours and runs ONCE, after the last "
        "change, before the stamp is judged)" % base,
        "RESERVED TO YOU (the shared files no stream could own, DEC-0070 (1)): (1) H196/BUG-0280 -- the 55 call sites across "
        "tools/test_*.py (read the item; closed red-first with a naming test); (2) team-kits/kernel/known_holes.json "
        "regenerated with tools/gen_known_holes.py after the streams removed/added known_hole markers (say the delta); (3) the "
        "docs/POST_V2_WISHLIST.md hole index is the LEAD's (`migrate-holes --reindex`) -- do not edit it; (4) the ONE stamp: "
        "`python tools/bump_kit_version.py` after your last kit change; (5) the ONE full run with the delivery prefix "
        "(`DELIVERY_RUN=<this task id>`), and after it the re-measurement of the stamp-dependent reds the streams listed "
        "(tools/test_kitupdate.py -k memory_tree_no_installed_role for H160/BUG-0242 -> its EVD; test_light_kit pilot rig; "
        "test_pointer_sweep; test_research_chain fixture)",
        "SEAM ROWS no stream could finish, each with its patch text in the named protocol: (a) BUG-0265/H183 kernel half "
        "`report.installed_kit_paths` reading .claude/kit_repo_files.json the installer now writes (patch in TSK-0142 "
        "protocol, 'Seam handoffs (B2)' 1); (b) N2 of TSK-0143 verify-round-3: the first docstring line of "
        "tools/test_repo_hygiene.py::_defined_in names two answers of three; (c) tools/test_hooks.py::"
        "_texts_that_name_the_evidence_vocabulary reads the kits' texts and README but not this repo's .claude/hooks/ -- "
        "extend its corpus to `.claude/hooks/*.py` of THIS repo so the next S2-class break is red in `pytest tools/` (the "
        "gate_commit_evidence.py remedy text stays the user's S4 patch: the test must READ that file, not fix it -- if it is "
        "red until the user patches, say so and mark the node as the S4 arbiter); (d) %s" % remaining,
        "HOST RULES (DEC-0094/0095 (6)): you are the only builder now -- still one pytest at a time; selections while you "
        "build; the full run once, from the repo root, timeout derived from the last measured full run (~40 min on this "
        "host; CI on 1b6d95c: 4895 passed); red-first in a copy without .git under C:/Offline Repos/v2-testbed/_round-scratch/"
        "(this task id)/; clock read for every time you write; protocol as you go in project_memory/staging/(this task id)/"
        "protocol.md",
        "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/; state writes through the kernel "
        "only (an EVD per closed hole with the naming node in the run command; the full run as ONE EVD kind test, run_scope "
        "full, related PR-0012); no transition of BUG items; no commit, no push, no mint",
    ]


OUTPUTS = [
    "The reserved rows and the seam rows, one line each: id | change (file:line) | red-first row | naming node | EVD -- or "
    "the measured reason it is not yours after all.",
    "ONE stamp after the last kit change (three VERSION files, `bump_kit_version.py` -> 'unchanged' x3 on a second call); "
    "known_holes.json regenerated and its delta stated.",
    "THE FULL RUN: one line, its command, duration, counts (passed/failed/skipped), the EVD id; every red either fixed at "
    "its mechanism (red-first) or measured as a finding with the reason -- no red left unnamed; ruff over tools team-kits; "
    "tools/validate.py green; generate-index = store.",
    "AC-5 PREPARED for the lead: `report.stock_rollup` read after your run with the accounting -- how many holes are closed "
    "(await the user's verification clicks), how many stand as exception questions (with the German sentence in `limits`), "
    "how many are DEC questions for the user, how many are the user's shell patch; the lists the lead runs (batch lines of "
    "all streams, collected in one file staging/(this task id)/lead-lines.md, each dry-checked against a store copy inside a "
    "checkout, 0 refused).",
]


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: create_bug_null_goal_round.py <base-commit> [<remaining-holes-note>]")
    base = sys.argv[1]
    remaining = sys.argv[2] if len(sys.argv) > 2 else "no further stream remainder handed over"
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0012", "--derives-from", "PR-0012",
        "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-4",
        "--acceptance-ref", "AC-5", "--dependency", "TSK-0141", "--dependency", "TSK-0142", "--dependency", "TSK-0143",
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
