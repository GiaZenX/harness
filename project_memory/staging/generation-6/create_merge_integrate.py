"""Merge the BUG-0333 fast track (TSK-0160, worktree g7-integrate) into the main tree holding order 7 + reworks 1-5
(stamp 2026.09.28-3). ONE stamp, the records, reading suites -- then ONE verifier over rework 5 + the door.
Not idempotent."""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory"]
env = dict(os.environ, PYTHONPATH="team-kits")
WT = "C:/Offline Repos/v2-testbed/_worktrees/g7-integrate"

INPUT = (
    "MERGE the BUG-0333 stream into the MAIN tree C:/Offline Repos/AgentAndSkills. The main tree holds order 7's "
    "merge + reworks 1-5 UNCOMMITTED (stamp 2026.09.28-3; latest: BUG-0335 closed in the kit gate, protocol "
    "staging/TSK-0156/protocol.md 'Rework 5'). The stream's work is UNCOMMITTED in the worktree " + WT + " (branch "
    "g7/integrate, base 35e929b; two new files only `git add -N`): read its protocol project_memory/staging/BUG-0333/"
    "protocol.md by section, especially 'what a stamp would cover' and the merge-simulation notes. Bring its full "
    "diff against 35e929b (tracked + the two new files) into the main tree with git merge-file per file, hunk by "
    "hunk; the declared seams: team-kits/kernel/cli.py, the three constitution/AGENTS.md, README.md (order 7 put "
    "`upkeep` on the same register lines -- keep BOTH `upkeep` and `integrate`), dev/research gate_git.py and "
    "parallel-streams/SKILL.md, dev project-manager/SKILL.md. Name every conflict and its resolution in the protocol. "
    "Then ONCE: `python tools/bump_kit_version.py` (+ --check), the lead-package size re-record and the section "
    "re-pin (tools/record_lead_package_sizes.py --write --note ..., tools/pin_constitution_sections.py --write "
    "--note ...), validate + ruff. READING SUITES by callers, each with a time budget: tools/test_bug0333_"
    "integrate.py, the gate_git suites (grep the callers of gate_git / its remedy), tools/test_parallel_streams.py, "
    "the shared-skill contract tests, tools/test_repo_hygiene.py, tools/test_kitupdate.py -k scaffold (stamp), "
    "tools/test_hooks.py::test_shared_kit_files_identical, the constitution/README register tests (grep where "
    "`upkeep` is asserted as a command). Protocol section 'Merge integrate' in project_memory/staging/BUG-0333/"
    "protocol.md as you go. Do not remove the worktree (the lead does after the commit). No full run, no commit, "
    "no push, no BUG transitions."
)
OUTPUT = ("the integrate stream in the main tree, every seam conflict named with its resolution; one stamp; size "
          "record + section pins re-recorded once; reading suites green with clock times; validate + ruff clean; "
          "the full run NOT started")
argv = BASE + ["create-task", "--product-requirement", "PR-0012", "--derives-from", "BUG-0333", "--type",
               "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-1",
               "--rung", "opus", "--effort", "medium"]
for p in ["team-kits/**", "tools/**", "docs/**", "README.md", ".claude/hooks/test_gates.py"]:
    argv += ["--allowed-scope", p]
for p in [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", ".claude/agents/**",
          "project_memory/**", "radar/**"]:
    argv += ["--forbidden-scope", p]
argv += ["--required-input", INPUT, "--expected-output", OUTPUT]
r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-800:])
sys.exit(r.returncode)
