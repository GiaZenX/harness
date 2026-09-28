"""Order 7 merge REWORK 3 (2026-09-28 ~12:3x): the merged `_walk` re-expands a quoted tilde / glob (H31 reopened, gate
suite 16 cells red), plus the pre-existing kit-gate half of the same class. Captures the BUG, then the task.
Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory"]
env = dict(os.environ, PYTHONPATH="team-kits")
DIAG = "project_memory/staging/TSK-0156/protocol.md section 'Gate tilde diagnosis' (from line ~390)"

BUG = {
    "title": "Merge-Regression: `_walk` erweitert eine gequotete Tilde bzw. ein gequotetes Muster ein zweites Mal "
             "-- Gate 1 und das Kit-Gate folgen `cd \"~\"` ins Home, bash bleibt stehen (H31 wieder offen)",
    "related_pr": "PR-0012",
    "observed": "MEASURED by the TSK-0158 gate diagnosis (" + DIAG + "; rig C:/Offline Repos/v2-testbed/_round-scratch/"
                "TSK-0158/tilde-diag/): the delivery run of .claude/hooks/test_gates.py (2026-09-28 11:24) had "
                "test_gate1_refuses_a_line_exactly_where_the_shell_would_write red in 16 cells (`cd \"~\" ; sed -i ... "
                "team-kits/kernel/state.py` rc 0). Cause: the order-7 merge rebuilt team-kits/*/hooks/"
                "gate_write_scope.py `_walk` (stream C, BUG-0323) and `_walked_to` expands the unquoted text again; "
                "probe `_walk(['cd','~'], base)` -> C:/Users/zenti (HEAD: None). NOT user patch 4 (pre-/post-patch "
                "_harness x HEAD/worktree kit: red only with the worktree kit). Same class, untested: a quoted glob "
                "(`cd \"d*cs\"`, `cd 'do[c]s'`) -- gate rc 0 with the worktree kit, rc 2 with HEAD, and bash really "
                "writes the protected file. PRE-EXISTING in the kit gate itself (HEAD too): lead as caller, `cd "
                ".claude ; cd \"~\" ; echo x > settings.json` (also `cd \"../d*cs\"`, `cd \\~`) rc 0 while bash writes "
                ".claude/settings.json.",
    "expected": "A word that carries quoting (or is not the first reading) is not tilde/glob-expanded by the walk: its "
                "position is unknown and a write after it is refused (the over-refusing direction), in gate 1 and in "
                "the kit gate.",
    "repro": "See the diagnosis rig; `cd \"~\" ; sed -i s/a/b/ team-kits/kernel/state.py` against gate 1.",
    "severity": "high",
    "acceptance_criteria": [
        {"id": "AC-1", "text": "the 16 cells of test_gate1_refuses_a_line_exactly_where_the_shell_would_write green; "
                               "a test naming this bug for the quoted-glob half of gate 1 and for the kit gate "
                               "(tilde, glob, backslash), red on 2026.09.27-9"},
    ],
    "source": DIAG + "; project_memory/staging/TSK-0158/walk-quoting-fix.diff",
    "limits": "Bis zum Fix: der Lead kann mit einer absichtlich gequoteten Tilde oder einem gequoteten Muster an "
              "Gate 1 vorbei schreiben; Subagenten ebenso am Kit-Gate. Nicht ausgeliefert (die Regression ist "
              "uncommitted).",
}

r = subprocess.run(BASE + ["capture", "BUG"], cwd=ROOT, env=env, input=json.dumps(BUG), capture_output=True,
                   text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-800:])
if r.returncode:
    sys.exit(r.returncode)
bug = r.stdout.split()[0]

INPUT = (
    "CONTINUES the order-7 merge (TSK-0156 -> 0157 -> 0158, all uncommitted in the main tree, stamp 2026.09.27-9, "
    "user patch 4 applied in .claude/hooks/_harness.py). The tools/ delivery run was GREEN (5310 passed, 2026-09-27 "
    "23:20); the gate suite had 3 red, two fixed by the lead (hole limits + index), the third is " + bug + ": read "
    "it, the diagnosis (" + DIAG + ") and the proposed fix project_memory/staging/TSK-0158/walk-quoting-fix.diff. "
    "BUILD: (1) apply that fix to team-kits/dev-team/hooks/gate_write_scope.py `_walked_to` and mirror x3 "
    "byte-identically (in `_walk`, a reading is not tilde/glob-expanded when the word carries quoting "
    "(ShellWord.spliced) or is not the first reading -> None = position unknown = refuse); (2) the TWO missing "
    "tests, each naming " + bug + ", red first against the current tree in a copy: gate 1's quoted-glob half in "
    ".claude/hooks/test_gates.py, and the kit gate's cases (tilde, glob, backslash; the `cd .claude ; cd \"~\" ; "
    "echo x > settings.json` chain with the lead as caller) in tools/test_hooks_v2.py; (3) the docstring names both "
    "tests and the over-refusal price (`cd ~/\"My Dir\"`); (4) ONE stamp; (5) reading suites as their own "
    "selections, each with a time budget: test_gates.py nodes test_gate1_refuses_a_line_exactly_where_the_shell_"
    "would_write, the bug_0139 pair, test_gate1_comes_back_out_of_a_group_it_walked_into, your new node; "
    "tools/test_stream_c_field.py -k bug_0323; tools/test_hooks.py -k \"directory or walk or cd or pushd or popd or "
    "position or tilde\" (the diagnosis saw 3 copy-only failures there -- run it in the MAIN tree read-only or "
    "explain); tools/test_hooks_v2.py -k \"walk or cd or tilde or position\"; validate + ruff. Protocol section "
    "'Rework 3' in project_memory/staging/TSK-0156/protocol.md as you go. Any hole you file with `capture --hole` "
    "carries `limits` at once (the gate suite demands it). No full run, no commit, no push, no BUG transitions."
)
OUTPUT = ("rework 3: " + bug + " fixed x3 with its two naming tests red-first; the 16 cells green; reading suites "
          "green with clock times; one stamp; validate + ruff clean; the full run NOT started")

argv = BASE + ["create-task", "--product-requirement", "PR-0012", "--derives-from", bug, "--type", "implementation",
               "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-1", "--rung", "opus",
               "--effort", "high", "--dependency", "TSK-0153", "--dependency", "TSK-0154",
               "--dependency", "TSK-0155"]
for p in ["team-kits/**", "tools/**", "docs/**", "README.md", "CLAUDE.md", "ladder.yaml",
          ".claude/hooks/test_gates.py", ".codex/agents/**", "install.ps1", "install.sh", ".gitattributes", "user/**"]:
    argv += ["--allowed-scope", p]
for p in [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", ".claude/agents/**",
          "project_memory/**", "radar/**"]:
    argv += ["--forbidden-scope", p]
argv += ["--required-input", INPUT, "--expected-output", OUTPUT]
r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-800:])
sys.exit(r.returncode)
