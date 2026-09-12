"""PR-0012 'Bug-Null', order 3b -- RE-CUT after the user rejected the first exception question (2026-09-12 09:22:
'Wieso wird das nicht behoben? Verstehe es nicht, will nicht blind Freigabe erteilen'): every hole whose fix lies in
THIS repository is CLOSED red-first with a test that names it -- the 17 CLOSE-class holes TSK-0140 did not reach AND
every hole TSK-0140 classified EXCEPTION in the classes OVERREF / ENUM / INSTR / DESIGN (the fix is in this repo's
hands). Exceptions remain only for provider/platform limits (PROV) and measured world-knowledge holes, and each of
those carries ONE plain-German sentence a non-developer understands. Created in DRAFT; READY after TSK-0140's
commit. Opus high; the builder may be given a second builder only on check-scopes-disjoint file sets (DEC-0087 (2)).
Usage: python create_bug_null_order_3b.py <base-commit>"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]
UNREACHED = ["H47", "H57", "H66", "H94", "H111", "H123", "H130", "H154", "H161", "H164", "H168", "H180", "H181",
             "H191", "H193", "H194"]

ALLOWED = ["team-kits/**", "tools/**", "docs/**", "user/**", "README.md", "CLAUDE.md", ".claude/hooks/test_gates.py",
           ".github/**", ".gitattributes", ".gitignore", "radar/README.md"]
FORBIDDEN = [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", ".claude/agents/**",
             "project_memory/**", "radar/20*.md", "radar/decided.md", "team-kits/*/settings/settings.json"]


def inputs(base):
    return [
        "THE USER'S WORD (2026-09-12 09:22, rejecting the first exception batch): holes are FIXED, not accepted, "
        "wherever the fix lies in this repository; an exception is the rare remainder (a provider/platform limit, a "
        "world-knowledge gap) and its question carries ONE plain-German sentence a non-developer understands. PR-0012 "
        "AC-4 verbatim; DEC-0100 (a bug closes only on a test that NAMES it -- kernel/naming_tests.py); the house rule "
        "(closed OR user-accepted exception, no third state)",
        "staging/TSK-0140/triage-table.md (128 holes: class, limits, verdict) and TSK-0140's rework table 'in-repo fix? "
        "yes/no + where' (protocol, after 09:30) -- your list = the 17 unreached CLOSE holes (" + ", ".join(UNREACHED) +
        ") PLUS every hole of classes OVERREF / ENUM / INSTR / DESIGN that TSK-0140 wrote as EXCEPTION unless its "
        "table says 'in-repo fix: no' with a measurement; the PROV class and measured world-knowledge holes stay "
        "exceptions (their one-sentence German reason is yours to write into the exception list)",
        "the tree after TSK-0140 (base commit %s): the ACCEPTED_EXCEPTION batch route (kernel/approvals.py "
        "hole_exception --batch), the verification batch route, kernel/naming_tests.py; the harness gates of this "
        "repo (.claude/hooks/gate_*.py, _harness.py) are NOT yours -- a hole whose closing edge lives there gets the "
        "exact patch in the protocol for the user's shell (the H182 precedent) and is an exception until applied" % base,
        "ORDER OF WORK: H47 and H57 first (in-session chains); then by class, cheapest first (ENUM enumerations -> a "
        "definition with a two-ended tripwire; INSTR instrument limits -> the reader widened or the limit measured "
        "and turned into a test; OVERREF over-refusals in the KITS' gates -> the reader narrowed with the attack "
        "still refused; DESIGN bounds -> the bound becomes a test or the design changes, per the item's `expected`); "
        "a hole the attempt measures unclosable in this repo is downgraded with the measured reason (the H190 "
        "precedent) -- never with 'later'",
        "HOST RULES (DEC-0094/0095 (6)): one pytest at a time with timeouts derived from measured durations; reading "
        "suites per fix; NO full run (the goal round's); red-first in a copy without .git under C:/Offline Repos/"
        "v2-testbed/_round-scratch/(this task id)/ with the arbiter's line; clock read; read each item and the code it "
        "names; protocol as you go (the weekly limit may end you; report HALF at the class boundary after ENUM+INSTR "
        "with counts); every kit change -> one stamp after the last change; `migrate-holes --reindex` is the lead's",
        "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/; an EVD per closed hole "
        "through the kernel (kind test, run_scope selection, the naming nodes); the batch lines (verification for the "
        "closed; hole_exception for the true remainder, <= 10, with the German sentence per id in the protocol) for "
        "the lead",
    ]


OUTPUTS = [
    "Per hole ONE row: id | class | mechanism | change (file:line) | red-first row (arbiter's line) | naming test | "
    "suites | EVD -- or, for the measured remainder, id | class | why unclosable HERE (measured) | bound | one "
    "plain-German sentence; no third state; the two in-session chains H47/H57 closed or their patch for the user's "
    "shell.",
    "COUNTS at the end, honest: closed / downgraded-with-measurement / remaining exceptions by class; the user's "
    "expectation is that the remainder is small and every remaining sentence is one he understands.",
    "The batch lines for the lead (verification <= 10 per line; hole_exception <= 10 per line), every row built "
    "against a store copy first (0 refused).",
    "RUNS: the reading suites of the changed files, one at a time; ONE stamp after the last kit change; ruff tools "
    "team-kits; validate.py; protocol in project_memory/staging/(this task id)/protocol.md with the table, the (g) "
    "row, the patch path, the EVD lines; no commit, no push, no mint; the FULL run is the goal round's.",
]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: create_bug_null_order_3b.py <base-commit>")
    base = sys.argv[1]
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0012", "--derives-from", "PR-0012",
        "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-4",
        "--dependency", "TSK-0140", "--rung", "opus", "--effort", "high",
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
