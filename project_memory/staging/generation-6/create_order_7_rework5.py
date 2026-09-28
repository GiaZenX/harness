"""BUG-0335 (H229): its limit was MEASURED as 'nothing automatic detects it' (TSK-0161, 2026-09-28 15:2x) -- an
overwritten .claude/settings.json unregisters every hook, so no after-check inside the hook system can see it. The
lead closes it now (refusing direction, gate 1's proven definition) instead of asking for an exception.
Records the measured limit, creates rework 5. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory"]
env = dict(os.environ, PYTHONPATH="team-kits")

LIMIT = ("Measured 2026-09-28 (TSK-0161, _round-scratch/TSK-0161/measure_0335.py, m-out4.txt): after `cd .claude ; "
         "cd ../nope ; echo x > settings.json`, which passes all ten registered Bash hooks rc 0, NO automatic kit "
         "path detects the overwritten .claude/settings.json: gate_dispatch's bundle hash covers only hooks/kernel, "
         "kit_trust_state stays active, the overwritten file registers no SessionStart hook; only a hand-run "
         "`python scripts/harness.py doctor` reports it. So nothing takes the place of the protection -- the lead "
         "closes the hole (TSK-0162) instead of asking for an exception.")
r = subprocess.run(BASE + ["update", "BUG-0335"], cwd=ROOT, env=env, input=json.dumps({"limits": LIMIT}),
                   capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-800:])
if r.returncode:
    sys.exit(r.returncode)

INPUT = (
    "CONTINUES TSK-0161 (CANCELLED; order 7 + reworks 1-4 uncommitted in the main tree, stamp 2026.09.28-2). CLOSE "
    "BUG-0335 (H229) in team-kits/*/hooks/gate_write_scope.py, mirrored x3, with the definition this repo's gate 1 "
    "already has (H29/H30 in .claude/hooks/_harness.py -- READ it, do not edit it): a directory move the shell may "
    "not perform does not give a known position. Concretely (verifier's minimal fix, project_memory/staging/TSK-0159/"
    "verify-round-1.md B1): in `_walked_to` add the 'stays' reading (cwd) as a candidate whenever the target is no "
    "existing directory at gate time; in `_walk` read an operand list that is not exactly one target, and -n / +N / "
    "-N, as 'stays or unknown'; popd on an empty stack gets cwd as a candidate. The protected reading wins, so the "
    "direction is refusing; `mkdir x ; cd x` must stay rc 0 (the 'stays' candidate there is harmless) -- measure it. "
    "TEST naming BUG-0335 in tools/test_hooks_v2.py over the verifier's eleven forms (lead as caller, bash as "
    "arbiter; C:/Offline Repos/v2-testbed/_round-scratch/TSK-0159-verify/out2.txt) plus counter-cases (a real "
    "existing target, `mkdir x ; cd x`, `cd -` after a real move), red first against the current tree, and the "
    "real-project chain (chain.py / _round-scratch/TSK-0161/measure_0335.py) showing gate_write_scope rc 2. The "
    "docstrings of `_walk`/`_walked_to` stop calling BUG-0335 open. Reading suites by CALLERS of `_walk` / "
    "`_walked_to` (grep), each with a time budget: at least tools/test_hooks_v2.py -k \"bug_0334 or bug_0335 or walk "
    "or cd or tilde or position\", tools/test_hooks.py -k \"directory or walk or cd or pushd or popd or position or "
    "tilde\", tools/test_stream_c_field.py -k bug_0323, tools/test_repo_hygiene.py -k pointer, the gate-1 nodes in "
    ".claude/hooks/test_gates.py that borrow the kit walk (test_gate1_refuses_a_line_exactly_where_the_shell_would_"
    "write, test_gate1_comes_back_out_of_a_group_it_walked_into, the bug_0334 node). ONE stamp; validate + ruff. "
    "Protocol section 'Rework 5' in project_memory/staging/TSK-0156/protocol.md as you go. No full run, no commit, "
    "no push, no BUG transitions."
)
OUTPUT = ("rework 5: BUG-0335 closed x3 with its naming test red-first (eleven forms + chain) and counter-cases "
          "green; reading suites by callers green with clock times; one stamp; validate + ruff clean; the full run "
          "NOT started")
argv = BASE + ["create-task", "--product-requirement", "PR-0012", "--derives-from", "BUG-0335", "--type",
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
