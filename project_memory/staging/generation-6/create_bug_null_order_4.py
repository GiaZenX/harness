"""PR-0012 'Bug-Null', order 4 -- what the user's eight decisions of 2026-09-12 ordered plus the in-repo remainder no
stream reached: DEC-0103 (goal-size vocabulary), DEC-0105 (tier file for a kit-less project), DEC-0107 (QA-only fail
class measured by a hook), DEC-0108 (mixed-VAT rows); H61/BUG-0153 (timeouts in every kit hook registration, then the
reader), H113/BUG-0197 (done record), H59/BUG-0151 (refusal vs warning -- read DEC-0110's sibling question first),
H160/BUG-0242 (re-measure after the stamp), the verifiers' remainders BUG-0295..0301, BUG-0302 (withdraw door for
pending requests), BUG-0069 (CI: closes on the first green run after the user's S4 patch). Created DRAFT; the user
decides when it runs (DEC-0093). One builder (Opus high) unless the lead measures a disjoint partition (DEC-0101).
Usage: python create_bug_null_order_4.py <base-commit>"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

ALLOWED = ["team-kits/**", "tools/**", "docs/**", "user/**", "README.md", "CLAUDE.md", ".claude/hooks/test_gates.py",
           ".github/**", ".gitattributes", ".gitignore", "radar/README.md", "project_memory/project_config.yaml"]
FORBIDDEN = [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", ".claude/agents/**",
             "project_memory/**", "radar/20*.md", "radar/decided.md"]


def inputs(base):
    return [
        "THE USER'S DECISIONS of 2026-09-12 as recorded: DEC-0103 (goal size = closed vocabulary small/normal/large/"
        "technical_enabler with a two-ended tripwire, refusal at capture/update, migration of the 12 stored goals), DEC-0105 "
        "(a kit-less project reads its rungs from a tier file its config names; missing file = 'keine Angabe'), DEC-0107 "
        "(`fail_class` written only by the verifying role through the kernel, gate_dispatch refuses any other writer as a "
        "process, the climb counter skips `mechanical`), DEC-0108 (a mixed-VAT document = one ledger row per rate under a "
        "shared invoice number; EUeR sums per rate, document count by distinct invoice numbers; BR-CO-14 stays). Read each "
        "DEC and the item it closes; the DEC is the order, the item carries the measurement",
        "THE IN-REPO REMAINDER (base commit %s): BUG-0153/H61 -- FIRST a `timeout` on every entry of team-kits/*/settings/"
        "settings.json (measured 2 of 89 carry one; this file is ALLOWED here for exactly that), THEN the fail-closed Deadline "
        "reader in _compat -- never the reader alone (it shuts every kit hook); BUG-0197/H113 -- the deadline register's "
        "'done' record (grep: 0 hits; a new canonical record kind -- say its shape in the protocol before building, the lead "
        "reads it); BUG-0151/H59 -- the kernel derives the debt and warns; whether it REFUSES is a decision: write the "
        "plain-German question with prices into the protocol, do not build; BUG-0242/H160 -- re-measure `tools/test_kitupdate.py "
        "-k memory_tree_no_installed_role` on the stamped tree and close or downgrade; BUG-0295 (docstring DEC ids the pairing "
        "swallows: a triple quote is ONE delimiter), BUG-0296 (ambiguous genitive -- DEC-first per DEC-0102 (3): write the class "
        "question, build only if the answer is 'keep judging prose'), BUG-0297 (closes when the user's S4 patch is in and the "
        "test that EXECUTES the printed remedy is built -- build the test, it stays red until the patch), BUG-0298 (one-line "
        "heredoc-to-file-then-run in the kits' gate), BUG-0299 (program word bound to a local name), BUG-0300 (the stopper "
        "reader's distinction gets a red test), BUG-0301 (span-wide computed-flag excuse: excuse at most as many names as "
        "computed tokens), BUG-0302 (`withdraw-request` / `sweep-requests --stale`, audit-logged; the hook note stops counting "
        "withdrawn requests); BUG-0069 -- do not touch: it closes on the first green CI run after the user's patch" % base,
        "RULES: DEC-0100 (a bug closes only on a test that NAMES it), the house rule (closed OR user-accepted exception with a "
        "German sentence), DEC-0102 (2) (name the MECHANISM and measure every spelling you can enumerate before the EVD; a "
        "closure the verifier widens twice is re-filed, not reworked a third time), DEC-0102 (4) (a kernel command whose "
        "REQUIRED arguments change: grep every caller in the tree first -- kits, tools, .claude/hooks, README -- and list them), "
        "DEC-0102 (5) (the half report is a protocol section with a clock reading, never a message)",
        "HOST RULES (DEC-0094/0095 (6)): one pytest at a time, selections < 3 min measured; the full run ONCE at the end with "
        "`DELIVERY_RUN=<this task id>` after ONE stamp (`python tools/bump_kit_version.py`); test_gates.py as its own run; "
        "red-first in a .git-less copy under C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/; clock read for every "
        "time you write; protocol as you go in project_memory/staging/(this task id)/protocol.md",
        "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/ and project_memory/project_config.yaml "
        "(DEC-0105's one line); state writes through the kernel only: an EVD per closed item with the naming node in the run "
        "command; no transition of BUG items; the verification batch lines (<= 10 ids) for the lead; no commit, no push, no mint",
    ]


OUTPUTS = [
    "Per DEC and per remainder item ONE row: id | change (file:line) | red-first row (arbiter's line) | naming node | suites "
    "(selection, duration) | EVD -- or the measured reason and the German sentence / the question for the user.",
    "The migration of the 12 stored goals (DEC-0103) run through kernel/migrate.py on a store copy first, then on the store, "
    "with the before/after list; the tier file of this repository named in project_config.yaml and the two harness role "
    "files no longer carrying the tiers by hand (DEC-0105).",
    "ONE stamp; the full run once (command, duration, counts, EVD), every red fixed at mechanism or measured; ruff; validate; "
    "index = store; mirrors byte-identical; the research constitution under its ceiling (tools/lead_package_sizes.json).",
    "COUNTS, honest: closed / downgraded with sentence / questions for the user / not reached; the batch lines dry-checked "
    "against a store copy inside a checkout (0 refused).",
]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: create_bug_null_order_4.py <base-commit>")
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0012", "--derives-from", "PR-0012",
        "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-4",
        "--dependency", "TSK-0144", "--rung", "opus", "--effort", "high",
    ]
    for p in ALLOWED:
        argv += ["--allowed-scope", p]
    for p in FORBIDDEN:
        argv += ["--forbidden-scope", p]
    for line in inputs(sys.argv[1]):
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
