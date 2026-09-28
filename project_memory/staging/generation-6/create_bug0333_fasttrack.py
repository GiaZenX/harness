"""BUG-0333 fast track (2026-09-28 ~12:4x): the synaipse merge deadlock gets its own stream NOW, in a worktree from
HEAD, parallel to order 7's rework 3; merged after order 7's commit. Captures the design DEC, then the task.
Usage: python create_bug0333_fasttrack.py <base-commit>. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory"]
env = dict(os.environ, PYTHONPATH="team-kits")
WT = "C:/Offline Repos/v2-testbed/_worktrees/g7-integrate"
FOR = "project_memory/staging/BUG-0333/forensics-2026-09-28.md"

DEC = {
    "title": "Ein Ziel mit parallelen Arbeitszweigen wird durch den KERNEL auf einem eigenen Integrationszweig "
             "vereint (kein neues Befehlszeilen-Raten im Gate); geprueft wird dieser Zweig, geliefert wird nur er",
    "context": "BUG-0333 (synaipse, field 2026-09-27/28): gate_git treats every `git merge` naming a goal as a "
               "delivery and demands the goal's full passing verdict first, while the kit allows a second builder "
               "under one goal (DEC-0092 (2)) and says only the united tree can be judged (parallel-streams "
               "SKILL.md ~:117, DEC-0063 (1)) -- a circle; P3 is blocked repo-wide by the any-fail fallback. The "
               "forensics' smallest fix was 'read the merge TARGET branch in the tree the command runs in' -- that "
               "is one more command-line reading (cd / -C resolution), the class that cost order 7's merge four "
               "reworks (DEC-0070 rule 2: a guard reading command lines is a design round, not a stream).",
    "decision": "(1) A new kernel door `integrate <GOAL>` performs the uniting itself: it creates (or reuses) the "
                "goal's integration branch `integrate/<GOAL>` from the delivery base and merges into it every work "
                "branch the kernel can attribute to the goal (branch name carries the goal id, as gate_git already "
                "reads; or the branch recorded on the goal's leases), in a worktree the kernel names; conflicts stop "
                "it with the file list and nothing half-merged left behind. No delivery verdict is needed for it: "
                "nothing reaches the delivery base. (2) gate_git stays as it is for `git merge` (still a delivery "
                "when it names a goal), and its refusal text names `integrate <GOAL>` as the route for uniting one "
                "goal's branches. (3) QA judges `integrate/<GOAL>`; the delivery merge of that branch into the "
                "delivery base keeps today's full verdict rule. (4) The PM/parallel-streams texts say this in two "
                "sentences. (5) The masking finding (an order-level pass masking a goal-level fail) and the "
                "rebase/cherry-pick/merge-tree bypass are separate items for wave 1, not this fast track.",
    "consequences": "synaipse unblocks with one kit update: P2's and P3's branches are united by `integrate`, QA "
                    "judges that, delivery unchanged. No new command-line reader. Cost: one kernel door + its "
                    "tests; the kernel runs git (as update-kit already runs file operations).",
    "work": ["PR-0012"],
    "source": FOR + "; user question 2026-09-28 'wann ist der Bug behoben damit synaipse weiterarbeiten kann?'",
}

r = subprocess.run(BASE + ["capture", "DEC"], cwd=ROOT, env=env, input=json.dumps(DEC), capture_output=True,
                   text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-800:])
if r.returncode:
    sys.exit(r.returncode)
dec = r.stdout.split()[0]

base = sys.argv[1]
INPUT = (
    "FAST-TRACK STREAM for BUG-0333, base commit " + base + ". WORK IN YOUR WORKTREE " + WT + " on branch "
    "g7/integrate (the lead creates it). Order 7's merge is being finished at the same time UNCOMMITTED in the main "
    "tree (rework 3 in team-kits/*/hooks/gate_write_scope.py, .claude/hooks/test_gates.py, tools/test_hooks_v2.py); "
    "the lead merges your branch after order 7's commit -- so do NOT stamp (no bump_kit_version; say in the "
    "protocol which files a stamp would cover) and keep kernel/cli.py and report.py hunks small and self-contained "
    "(order 7 changed both). READ: project_memory/bugs/active/BUG-0333.yaml, " + FOR + ", and " + dec + " (the "
    "design -- build exactly that, not the forensics' target-reading proposal). BUILD: the kernel door `integrate "
    "<GOAL>` (team-kits/kernel/, registered in kernel/cli.py and in every register a new command joins -- DEC-0121 "
    "(3): grep the registers the last new command joined), the gate_git refusal naming it (dev-team only; gate_git "
    "is not in the other kits -- check), the two-sentence text in the dev-team PM skill and parallel-streams skill. "
    "TESTS naming BUG-0333, red first in a copy under C:/Offline Repos/v2-testbed/_round-scratch/BUG-0333/: a goal "
    "with two work branches reaches one united branch through `integrate` in a real git repo (tmp), a conflict "
    "stops cleanly, a branch of ANOTHER goal is never pulled in, the delivery merge into the base still needs the "
    "full verdict, and gate_git's refusal names the door. Reading suites of every predicate you change as their own "
    "selections, found by their CALLERS (grep), not by keywords in test names; each run with a time budget. "
    "Protocol as you go in project_memory/staging/BUG-0333/protocol.md (write it BEFORE long runs). Any hole you "
    "file carries `limits` at once. Commit in your worktree is not possible (this repo's gate 3 measures the main "
    "tree) -- leave your work uncommitted there. No push, no full run, no BUG transitions."
)
OUTPUT = ("`integrate <GOAL>` in the kernel + registers, gate_git's refusal naming it, the two skill sentences, "
          "the BUG-0333 tests red-first, reading suites green with clock times, protocol with the file list a stamp "
          "would cover; NOT stamped, NOT merged")

argv = BASE + ["create-task", "--product-requirement", "PR-0012", "--derives-from", "BUG-0333", "--type",
               "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-1",
               "--rung", "opus", "--effort", "high"]
for p in ["team-kits/kernel/**", "team-kits/dev-team/hooks/gate_git.py", "team-kits/dev-team/skills/**",
          "tools/test_integrate*.py", "tools/test_bug0333*.py", "docs/**"]:
    argv += ["--allowed-scope", p]
for p in [".claude/**", "project_memory/**", "radar/**", "team-kits/*/hooks/gate_write_scope.py",
          "team-kits/*/VERSION", "tools/bump_kit_version.py"]:
    argv += ["--forbidden-scope", p]
argv += ["--required-input", INPUT, "--expected-output", OUTPUT]
r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-800:])
sys.exit(r.returncode)
