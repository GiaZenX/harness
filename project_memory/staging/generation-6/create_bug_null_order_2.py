"""PR-0012 'Bug-Null', order 2 of three: AC-3 -- the real remaining defects, each fixed red-first or measured
already-fixed / unfixable with the reason. Created in DRAFT while order 1 (TSK-0138) runs; READY the moment
TSK-0138 is delivered and checked (DEC-0099 (1)); check-scopes against TSK-0138 measured before READY (they share
cli.py/state.py/constitutions/PM skills -> sequential). Opus high. Not idempotent -- run once."""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

BUGS = ["BUG-0081", "BUG-0074", "BUG-0075", "BUG-0076", "BUG-0058", "BUG-0053", "BUG-0052", "BUG-0026", "BUG-0027",
        "BUG-0016", "BUG-0054", "BUG-0055", "BUG-0077", "BUG-0080", "BUG-0022", "BUG-0023", "BUG-0031", "BUG-0046",
        "BUG-0056", "BUG-0057", "BUG-0067", "BUG-0087", "BUG-0092", "BUG-0010", "BUG-0037", "BUG-0079", "BUG-0082",
        "BUG-0017"]

ALLOWED = ["team-kits/**", "tools/**", "docs/**", "user/**", "README.md", "CLAUDE.md", ".claude/hooks/test_gates.py",
           ".github/**", ".gitignore", ".gitattributes"]
FORBIDDEN = [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", ".claude/agents/**",
             "project_memory/**", "radar/**", "team-kits/*/settings/settings.json"]
INPUTS = [
    "PR-0012 AC-3 verbatim: the bugs " + ", ".join(BUGS) + " -- each read from its item (observed / expected / repro / "
    "acceptance_criteria) and from the survey table's row (staging/TSK-0131/survey-table.md: verdict MEASURED-OPEN / "
    "PARTIAL / UNMEASURED and the note); BUG-0017 is closed as measured-by-design (TSK-0135's headless_pm_stop_point in "
    "tools/provider_observations.json: the PM never reaches the approval gate headless) -- the docs say so and the item "
    "gets its evidence, not a fix",
    "the state of the tree after TSK-0138 (base: its commit hash, named by the lead at READY); the kits' hook files are "
    "yours EXCEPT settings.json (registration) -- a fix inside a kit gate is mirrored x3 with the tripwire; the harness "
    "gates of this repo (.claude/hooks/gate_*.py) are NOT yours: a defect there (BUG-0012, BUG-0020, BUG-0034 if still "
    "open) is measured and handed back with the exact patch in the protocol for the user to apply from a shell outside "
    "Claude Code",
    "HOST RULES (DEC-0094): one pytest at a time, timeouts derived from measured durations, reading suites per fix "
    "(the suites that read the changed files), NO full run inside the order (the goal's final round runs it once); "
    "red-first per fix in a copy without .git under C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/ with the "
    "arbiter's failure line per row; a pilot chain (gate_git, freeze, dispatch, design draft) measured on a scaffolded "
    "pilot as a PROCESS; clock read; read end lines and named sections only (DEC-0095 (6)); every kit change -> one "
    "stamp after the last change",
    "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/; every state write through the "
    "kernel: for a fixed bug you record the EVD (kind test, result pass, run_scope selection, the red-first node) -- the "
    "transitions to FIXED/VERIFIED go through the batch mint the lead asks the user (TSK-0138's route); a bug measured "
    "unfixable is written up with mechanism, chain and bound for the user's ACCEPTED_EXCEPTION batch (order 3's route)",
]
OUTPUTS = [
    "Per bug ONE line in the protocol table: id | mechanism (one sentence) | what changed (file:line) | the red-first "
    "row (arbiter's failure line) | the reading suites run | the EVD id -- or 'already fixed by <commit/test>' with "
    "the passing node re-run, or 'unfixable: <reason> / bound: <what limits it>' for the exception batch; no bug of "
    "the list is left without one of the three.",
    "The six pilot-measured defects FIRST and as processes on a scaffolded pilot: BUG-0081 (the first work-branch push "
    "is not refused for missing acceptance evidence; a later push without it still is), BUG-0074 (freeze-* moves only "
    "the frozen artifact, the rest of the task's staging stays -- red-first with three unfrozen files), BUG-0075/0076 "
    "(the document-owning roles are routed to the document write route; a design draft reaches the user through a "
    "render+review duty the PM carries, measured on the pilot), BUG-0058 (an idle dispatched specialist is reported in "
    "the session brief / by the auditor within one session -- the lease's last activity read, not a prose duty), "
    "BUG-0053 (the compose foreign-project rule decides by the resolved project, not by flag spellings -- both ends of "
    "the tripwire), BUG-0052 (the tools/ suite writes nothing into project_memory/.audit -- the hook events of a test run "
    "go to the test's own tmp store; the repo's .audit is untouched after a full run, measured by mtime).",
    "The rest of the list closed the same way (migration lines BUG-0026/0027; the restart plea BUG-0016; the wireframe/"
    "manifest chain BUG-0054/0055/0077/0080; the CR type BUG-0022 reached or removed with reasons; BUG-0023 measured "
    "as built by G5-1 (NONEMPTY_FIELDS) -> evidence; BUG-0031 the Codex entry file's marker routing; BUG-0046 the "
    "narration leak's kit half; BUG-0056/0057/0067/0087/0092/0010/0037/0079/0082 each at its mechanism); BUG-0017 "
    "closed as measured-by-design with the docs line.",
    "RUNS: the reading suites per fix; `python tools/bump_kit_version.py` once after the last kit change; ruff tools "
    "team-kits; validate.py; protocol in project_memory/staging/(this task id)/protocol.md with the table, the (g) row "
    "(tokens from your counter, wall-clock read), the patch path, the EVD lines already recorded, the two batch lists "
    "for the lead (VERIFIED candidates with their EVD ids; exception candidates with mechanism/bound); no commit, no "
    "push, no mint.",
]


def main():
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0012", "--derives-from", "PR-0012",
        "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-3",
        "--dependency", "TSK-0138", "--rung", "opus", "--effort", "high",
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
