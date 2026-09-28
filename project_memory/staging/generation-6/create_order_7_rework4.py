"""TSK-0159 verify FAIL (2026-09-28 ~14:3x): capture B1 as a hole (pre-existing kit-gate walk class), create rework 4
(B2 row, B3/B4 text, measure B1's limit). Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory"]
env = dict(os.environ, PYTHONPATH="team-kits")
REP = "project_memory/staging/TSK-0159/verify-round-1.md"

HOLE = {
    "title": "Kit-Gate: der Verzeichnis-Walk nimmt jeden cd/pushd/popd als gelungen an -- auch wenn die Shell "
             "stehen bleibt (Ziel fehlt, Muster trifft nichts/zwei, zwei Operanden, -n/+N, leerer Stapel)",
    "related_pr": "PR-0012",
    "observed": "MEASURED by the TSK-0159 verifier (" + REP + ", B1; rig C:/Offline Repos/v2-testbed/_round-scratch/"
                "TSK-0159-verify/, out2.txt, out4.txt): team-kits/*/hooks/gate_write_scope.py `_walk` (~:1699-1714) "
                "and `_walked_to` (~:1763-1764) take the named target even when the shell does not move. Lead as "
                "caller, bash as arbiter: `cd .claude ; cd ../nope ; echo x > settings.json` and ten more forms rc 0 "
                "on the package, before it and on HEAD, bash writes .claude/settings.json. In a real scaffolded "
                "dev-team project all ten registered Bash PreToolUse hooks answer rc 0 and bash overwrites "
                ".claude/settings.json. This repo's gate 1 refuses all eleven forms (H29/H30 definition); the kits "
                "lack it. PRE-EXISTING (HEAD), not introduced by order 7. VERDICT: open; closing belongs to wave 1 "
                "stream B (the write-target guessing, `_walk` included, is replaced by the kernel write log + "
                "after-check).",
    "expected": "A write after a directory move the shell does not perform is judged at the position the shell "
                "really has (or refused as unknown).",
    "repro": "In a scaffolded dev-team project, as the session agent: `cd .claude ; cd ../nope ; echo x > "
             "settings.json` -> every Bash hook rc 0, the file is overwritten.",
    "severity": "high",
    "acceptance_criteria": [
        {"id": "AC-1", "text": "the eleven measured forms are refused (or caught by the after-check) -- a test naming "
                               "this bug, red on 2026.09.28-1"},
    ],
    "source": REP + " (B1)",
    "limits": "PENDING MEASUREMENT by TSK-0161 (does the kit's bundle/settings hash check detect an overwritten "
              ".claude/settings.json at the next spawn or session start?). Known today: pre-existing since the "
              "kits shipped; needs a deliberately failing cd; nothing is pushed without the user.",
}
r = subprocess.run(BASE + ["capture", "BUG", "--hole"], cwd=ROOT, env=env, input=json.dumps(HOLE),
                   capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-800:])
if r.returncode:
    sys.exit(r.returncode)
hole_bug = r.stdout.split()[1] if r.stdout.startswith("[hole]") else r.stdout.split()[0]

INPUT = (
    "CONTINUES TSK-0159 (CANCELLED for re-planning after its verifier's FAIL; its fix stays uncommitted in the main "
    "tree, stamp 2026.09.28-1 -- do NOT redo it). Read " + REP + " by section. THE LEAD'S DECISION (no more "
    "investment in the old walk than the delivery needs; wave 1 stream B replaces it): (B2, BLOCKING) add the row "
    "`cd ../d\\*cs` (and `cd ../do\\[c]s`) to `_QUOTED_EXPANSION_MOVES` in tools/test_hooks_v2.py and show it RED "
    "with the verifier's mutation glob-quoted-only, green on the package; (B3) the `_walked_to` docstring names the "
    "PowerShell price as a property (PowerShell resolves ~ and wildcards at provider level regardless of quoting, so "
    "a quoted Set-Location target is refused too), mirrored x3; (B4) tools/test_hooks_v2.py:7431-7432 names the "
    "property ('the rows whose shell stays') instead of a count; (B1) do NOT fix the walk -- it is captured as "
    + hole_bug + " (hole). MEASURE its limit instead: in a scaffolded dev-team project (use the verifier's chain.py "
    "as a start), overwrite .claude/settings.json by the chain, then check whether the kit detects it -- the "
    "bundle/installed-files hash check at the next specialist spawn (dispatch) and at session start "
    "(session_status / update-kit check): quote the refusal or say it is NOT detected. Report the measured sentence "
    "for the hole's `limits` (the lead writes it through the kernel). Also fix the `_walk` docstring sentence on "
    "popd (:1678-1682) so it names the empty-stack case as part of " + hole_bug + " (rule 3). ONE stamp at the end; "
    "reading suites: tools/test_hooks_v2.py -k \"bug_0334 or walk or cd or tilde or position\", "
    "tools/test_repo_hygiene.py -k pointer, validate + ruff; each with a time budget. Protocol section 'Rework 4' "
    "in project_memory/staging/TSK-0156/protocol.md as you go. No full run, no commit, no push, no BUG transitions."
)
OUTPUT = ("rework 4: B2 row red-first (glob-quoted-only) and green; B3/B4 texts; the popd docstring sentence; " +
          hole_bug + "'s limit MEASURED (detected by which check, or not); one stamp; reading suites green with "
          "clock times; validate + ruff clean; the full run NOT started")

argv = BASE + ["create-task", "--product-requirement", "PR-0012", "--derives-from", "BUG-0334", "--type",
               "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-1",
               "--rung", "opus", "--effort", "high"]
for p in ["team-kits/**", "tools/**", "docs/**", ".claude/hooks/test_gates.py"]:
    argv += ["--allowed-scope", p]
for p in [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", ".claude/agents/**",
          "project_memory/**", "radar/**", "team-kits/kernel/integrate*.py", "team-kits/dev-team/hooks/gate_git.py"]:
    argv += ["--forbidden-scope", p]
argv += ["--required-input", INPUT, "--expected-output", OUTPUT]
r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-800:])
sys.exit(r.returncode)
