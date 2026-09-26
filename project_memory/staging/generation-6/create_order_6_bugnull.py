"""Order 6 (2026-09-26): PR-0012 'Bug-Null' remainder -- DEC-0117 (archive door), BUG-0305/H220, BUG-0308/H221,
BUG-0069 (CI), BUG-0264/H182 (closing test), and PATCH TEMPLATES for the user's files (H47/BUG-0139, H13/BUG-0105,
H69/BUG-0161, H151/BUG-0233). ONE builder (Opus, high): kernel, kit hooks and tools tests interlock and the full suite
spans all of them (DEC-0101); it is also the AFTER measurement of FR-0093 (tools/measure_agent_tokens.py against the
TSK-0150 baseline). The cut applies DEC-0116: no expected output asks a test to find a property in free text, and
every line names the path that runs.
Usage: python create_order_6_bugnull.py <base-commit>"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

ALLOWED = ["team-kits/**", "tools/**", "docs/**", "README.md", "CLAUDE.md", ".claude/hooks/test_gates.py",
           ".github/**", ".gitignore", ".gitattributes"]
FORBIDDEN = [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", ".claude/agents/**",
             "project_memory/**", "radar/**"]


def inputs(base):
    return [
        "BASE COMMIT %s. DEC-0117 (read whole; it is the order): a narrow kernel command that corrects ONLY a test "
        "reference in an ARCHIVED item (old node named there and resolving nowhere -> new node that resolves now), "
        "audited, every other archived field stays frozen, each refusal red-first; the gate test that every named test "
        "exists keeps reading the archive. Do NOT apply it to H138/H155 yourself -- the lead does that after the "
        "verifier's PASS; say in the protocol the two exact command lines" % base,
        "BUG-0305/H220 (over-refusal of the kits' write-and-run rule on a READ-ONLY stage with an unknown command word, "
        "and its false sentence 'this line WRITES ...'): the running path is the kit gate the rule lives in -- close it "
        "so the attack lines of BUG-0304 (TSK-0150 verify rounds) stay refused; test naming BUG-0305. BUG-0308/H221 "
        "(rung bookkeeping counts the Claude answer on a Codex project): the running path is `lease_rung`/"
        "`lease_effort` on the order and every rollup that reads them (grep the readers) -- carry the per-provider "
        "answer the lease already has (`by_provider`, TSK-0151) into the bookkeeping, or state the bound in the "
        "hole row if a provider cannot be known; test naming BUG-0308",
        "BUG-0069 (GitHub CI red): read the FULL logs of run 36187576523 (`gh run view 36187576523 --log`, by "
        "section) -- ubuntu 1 failed ('artifact_refs that resolve nowhere': EVDs point at staging/**/*.log files that "
        "exist locally but are not in the repository), windows 3 failed (names not in the short summary: find them). "
        "Fix at the mechanism (e.g. what is ignored vs what evidence may point at), never by skipping a check that "
        "measures; the item closes on the first green hosted run, which the lead reads after the push",
        "BUG-0264/H182: the user's patch changed its four sentences (2026-09-25). DEC-0116 forbids a test that reads "
        "prose -- find a STRUCTURAL property that names BUG-0264 (e.g. the exemption decided by the frontmatter key "
        "alone, whatever the prose says); if none exists, say so in the protocol and the lead asks the user for an "
        "exception with a German limits sentence -- do not build a prose reader",
        "PATCH TEMPLATES for the user's files (.claude/hooks/*.py are refused to every role): H47/BUG-0139 (repo gate "
        "borrows the kit's target reader but not its line assignment map: `F=team-kits/kernel/state.py; echo x > $F` is "
        "rc 0 at the repo gate, rc 2 at the kit gate -- closing direction (a) pull the resolution into the shared "
        "reader so the kit fix heals it, or (b) the repo gate builds the map), H13/BUG-0105 (a NEW file beside the "
        "stamper is writable), H69/BUG-0161 (CR hardening only half inherited: `echo poison > project_mem<CR>ory/...` "
        "rc 0), H151/BUG-0233 (gate 5's declaration tools/test_surface.json outside its own protected area). For each: "
        "measure the chain on the current tree, write before/after with anchors that occur once into ONE "
        "project_memory/staging/(this task id)/user-patch.md + an idempotent apply script with --check (style of "
        "staging/TSK-0151/apply_user_patch.py), and a red-first test in .claude/hooks/test_gates.py that NAMES the bug "
        "and turns green once the patch is applied (measure that in a copy with the patch applied). If a hole is a "
        "CLASS question (DEC-0070 rule 2: a guard that reads command lines), write the class question in plain German "
        "into the protocol and do not build it",
        "RULES: DEC-0100 (a bug closes only on a test that NAMES it), DEC-0116 (structural contracts, the path that "
        "runs), DEC-0102 (2)/(4)/(5), DEC-0080 rule 2 (run every suite that READS a changed kernel/gate rule, each as "
        "its own selection, listed in the protocol); red-first in a .git-less copy under C:/Offline Repos/v2-testbed/"
        "_round-scratch/(this task id)/",
        "HOST + COST RULES (FR-0093, DEC-0094/0095 (6)): one pytest at a time; any command longer than ~2 min in the "
        "BACKGROUND with a completion wait, never a sleep loop; read files over 2,000 lines by section; ONE stamp "
        "(`python tools/bump_kit_version.py`) at the end, then the full run ONCE with `DELIVERY_RUN=<this task id>`; "
        "`.claude/hooks/test_gates.py` as its own run; clock read for every time you write; protocol as you go in "
        "project_memory/staging/(this task id)/protocol.md",
        "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/; state writes through the "
        "kernel only: an EVD per closed bug naming its node in --run-command (a full-run EVD relates NO bug -- "
        "DEC-0100 (3)); no transition of BUG items; no commit, no push, no mint, no rollout",
    ]


OUTPUTS = [
    "the DEC-0117 kernel command with red-first refusals (not archived / old node not named / old node still resolves "
    "/ new node does not resolve / any other field) and an audit record; the two command lines for H138/H155 in the "
    "protocol",
    "BUG-0305 and BUG-0308 closed on the running path, each with a test naming it (red on the base)",
    "BUG-0069: every hosted failure of run 36187576523 named and fixed at its mechanism; local full run green",
    "BUG-0264: a structural test naming it, or the protocol's statement that none exists (-> exception question)",
    "one user-patch.md + idempotent apply script for H47/H13/H69/H151 with anchors that occur once; per hole a test "
    "in .claude/hooks/test_gates.py naming the bug, red before the patch and green after it (measured in a copy); "
    "class questions written in German where a hole is DEC-first",
    "kit stamp once; full run with DELIVERY_RUN once; test_gates.py run (reds listed with cause: the patch-pending "
    "ones and nothing else); EVDs per closed bug; protocol with the reading suites, results and clock times",
]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: create_order_6_bugnull.py <base-commit>")
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0012", "--derives-from", "BUG-0305", "--type", "implementation",
        "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-1",
        "--rung", "opus", "--effort", "high",
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
