"""Order 7 (2026-09-26), THREE PARALLEL STREAMS on the user's word ('Parallel 3 Stroeme'), each in its own worktree,
then a merge round of its own. The seam table (who owns which file) is the cut; shared files are named with the
section each stream may touch, and git merges distinct hunks. No stream stamps and no stream runs the full suite
(DEC-0121 (1)): the MERGE stamps once and runs the delivery run after the merge verifier's PASS.
Usage: python create_order_7_streams.py <base-commit>"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]
WT = "C:/Offline Repos/v2-testbed/_worktrees/"
KITS = ("dev-team", "office-team", "research-team")

SHARED = ("SHARED FILES (git merges distinct hunks; touch ONLY your section, say every hunk in the protocol): "
          "team-kits/kernel/cli.py (A: request-approval; B: create-task/dispatch/ladder/checkpoint; C: doctor/update-kit/"
          "new doors), the kits' project-manager / office-manager / research-lead SKILL.md and constitution/AGENTS.md "
          "(A: approval passages; B: order, cost-line and slicing passages; C: kit-update and memory passages), "
          "README.md command list, hooks/_compat.py and hooks/_kernel.py (add NEW functions, do not rewrite existing "
          "ones). Existing test files: add new test functions at the end or put new tests in a new file.")

COMMON = [
    "RULES: DEC-0100 (a bug closes on a test that NAMES it), DEC-0116 (structural contracts, the path that runs, no "
    "free-text readers), DEC-0121 (resolved paths; a new kernel command joins its registers -- status-writer bound, "
    "board regeneration list, command-surface listings; protocol as you go), DEC-0080 rule 2 (run every suite that "
    "READS a rule you change, each as its own selection, listed in the protocol), DEC-0102 (2)/(4). Kit hooks are "
    "mirrored x3 (dev/office/research) byte-identical unless KIT_SPECIFIC_HOOKS names the reason.",
    "COST + PROCESS (FR-0093 as corrected by BUG-0313's finding): long commands in the BACKGROUND with a completion "
    "wait are for YOU, not for any agent you might start; one pytest at a time; read files over 2,000 lines by "
    "section; NO stamp and NO full run in a stream (the merge does both, DEC-0121 (1)); red-first in a .git-less copy "
    "under C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/; clock read for every time you write; protocol "
    "as you go in project_memory/staging/(this task id)/protocol.md (the MAIN repo's staging, not the worktree's).",
    "STATE: through the MAIN repo's kernel only (`PYTHONPATH=team-kits python -B -m kernel.cli --root "
    "\"C:/Offline Repos/AgentAndSkills/project_memory\" ...` from the main repo); an EVD per closed bug naming its "
    "node, recorded from the worktree's run; no BUG transitions; no commit on feat/harness-v2, no push, no mint. "
    "Commit your work on YOUR stream branch in YOUR worktree (git commit there is yours; the merge takes the branch).",
]

STREAMS = [
    {
        "key": "A", "branch": "g7/approvals", "wt": WT + "g7-approvals", "derives": "BUG-0315",
        "title": "approvals",
        "allowed": ["team-kits/kernel/approvals.py", "team-kits/kernel/sdk_approval.py"]
                   + ["team-kits/%s/hooks/gate_approval.py" % k for k in KITS]
                   + ["team-kits/%s/hooks/guard_question_context.py" % k for k in KITS]
                   + ["team-kits/kernel/cli.py", "team-kits/*/skills/**", "team-kits/*/constitution/**", "README.md",
                      "tools/test_approval*.py", "tools/test_approvals*.py", "tools/test_stream_a_*.py", "docs/**"],
        "inputs": [
            "DEC-0119 (read whole; it is the order): an approval is an UNDERSTANDING check, never a permission to "
            "continue -- remove/rewrite every kit text that makes a PM ask 'done with X, continue with Y?'; bugs need "
            "no approval; the user's change wishes are captured with his verbatim words and started at once, and ONE "
            "collected understanding card is answered before the goal's acceptance; the guard stays (only the user's "
            "answer mints). FR-0095 (the calm card: 'Freigabe erbeten fuer <Art>', the list id + short German title, "
            "the PM's own explanation INSIDE the signed/hashed text, no checksums/paths/request ids in the read text; "
            "the binding stays machine-checkable). FR-0096 (a SCOPE batch: `request-approval scope --batch <ids>` over "
            "CR/BUG/new goals, list-bound like verification/hole_exception, each entry bound to its own scope hash; the "
            "PM skill collects and asks once). FR-0090 (the expiry date readable, '25.09.2026, 14:30')."],
        "outputs": [
            "the calm card built by approvals.build_question for EVERY kind (a test per kind shape: header line, list "
            "lines, the PM note inside the hash, no 32-hex id / path / checksum in the question or option texts) -- "
            "gate_approval still mints only from the approving option; FR-0090's date format",
            "`request-approval scope --batch` with the refusals of the batch form (a DONE item, a foreign kind, >10 "
            "ids) red-first and the per-entry hash re-checked at use",
            "the kits' PM/lead texts per DEC-0119 (no continue-permission prompts; bugs without approval; change wishes "
            "verbatim + one collected card before acceptance); a structural test that the approval kinds a PM is told "
            "to request are exactly plan/collected-scope/acceptance/delivery/push/kit_update/routine/preset "
            "(read from the skill's kind list, not from prose)"],
    },
    {
        "key": "B", "branch": "g7/dispatch", "wt": WT + "g7-dispatch", "derives": "BUG-0313",
        "title": "order flow",
        "allowed": ["team-kits/kernel/dispatch.py", "team-kits/kernel/state.py", "team-kits/kernel/checkpoints.py",
                    "team-kits/kernel/report.py", "team-kits/kernel/board.py", "team-kits/kernel/schemas.py",
                    "team-kits/kernel/cli.py"]
                   + ["team-kits/%s/hooks/%s" % (k, h) for k in KITS for h in (
                       "gate_dispatch.py", "guard_agent_spawn.py", "gate_subagent_output.py",
                       "notify_agent_events.py", "_compat.py", "_kernel.py")]
                   + ["team-kits/*/ladder.yaml", "ladder.yaml", "team-kits/model_tiers.yaml", "team-kits/*/skills/**",
                      "team-kits/*/constitution/**", "README.md", "tools/test_stream_b_*.py", "tools/test_ladder.py",
                      "tools/test_dispatch*.py", "tools/test_kernel.py", "docs/**"],
        "inputs": [
            "BUG-0313 (URGENT, field regression of TSK-0151): a child waiting on its own background run is read as "
            "stopped by gate_dispatch -> FAILED booking + a second concurrent builder in synaipse. Fix on the running "
            "path (the gate treats a pending background completion as alive, or the kits' order line tells SUBAGENTS "
            "to run long commands in the foreground with a timeout -- whichever the gate can measure); the FR-0093 "
            "order line in every kit corrected accordingly. BUG-0314 (lease dead ends: expired lease left "
            "IN_PROGRESS; foreground self-path child cannot book; swept lease with committed work). BUG-0324 "
            "(fail_class unreachable for the verifier). BUG-0322 (architect-step chicken-and-egg; stray SR parent; "
            "refusal names nothing). BUG-0315 (report._runs_no_file resolves the _gate.py launcher argument against "
            "the repo root). BUG-0321 (a later passing selection never supersedes an older failing one for a bug's "
            "current verdict -- find the reader; if it is not in your files, say so and hand it to the merge).",
            "BUG-0318 (the PM slices into tiny serial orders with a QA order per SR/CR, against DEC-0087/0088 and "
            "the skill's own step 7; nothing notices; no parallel builders): fact lines (NOT refusals) at create-task "
            "for a second build order under the same goal and for a QA order on a one-output change, naming "
            "DEC-0087/0088; orders-per-goal and verifier share in the session brief; parallel candidates from "
            "check-scopes named in the brief. FR-0092 (every started agent's VISIBLE name carries role + model + "
            "effort + stream letter, e.g. 'Frontend Developer · Opus xhigh · A'): the dispatch header hands the PM the "
            "exact description string to spawn with, and the spawn gate compares the description against it "
            "(refuse or fact line -- measure what the payload carries). DEC-0118 (on Claude the architecture class "
            "starts at XHIGH, ceiling xhigh; one-line switch back via provider_top) -- where the start effort is "
            "derived."],
        "outputs": [
            "BUG-0313, 0314, 0315, 0321 (or its hand-over), 0322, 0324 each closed on the running path with a test "
            "naming it (process tests where the defect is a process), red-first",
            "BUG-0318's fact lines + brief lines with tests; FR-0092's spawn-name contract with a test; DEC-0118's "
            "start effort measured through `kernel.cli ladder` for every kit on both providers"],
    },
    {
        "key": "C", "branch": "g7/field", "wt": WT + "g7-field", "derives": "BUG-0310",
        "title": "field repairs",
        "allowed": ["team-kits/kernel/hashing.py", "team-kits/kernel/kitupdate.py", "team-kits/kernel/migrate.py",
                    "team-kits/kernel/presets.py", "team-kits/kernel/layout.py", "team-kits/kernel/cli.py",
                    "team-kits/scaffold_team.ps1", "team-kits/scaffold_team.sh", "team-kits/write_kit_state.py",
                    "team-kits/*/templates/**", "install.ps1", "install.sh"]
                   + ["team-kits/%s/hooks/%s" % (k, h) for k in KITS for h in (
                       "gate_shell_hygiene.py", "guard_memory_budget.py", "gate_write_scope.py", "kit_trust_state.py",
                       "session_status.py", "_compat.py", "_kernel.py")]
                   + ["team-kits/*/skills/**", "team-kits/*/constitution/**", "README.md", "tools/test_stream_c_*.py",
                      "tools/test_kitupdate.py", "tools/test_migrate.py", "tools/test_hashing*.py", "docs/**"],
        "inputs": [
            "BUG-0310 (a route caches bytecode into the installed .claude/kernel -> bundle 'changed', spawns refused; "
            "make every importer covered, e.g. sys.dont_write_bytecode at the kernel package import, AND a session-side "
            "door that prunes transient caches under the bundle and re-checks the hash -- deleting a cache never adds "
            "code). BUG-0311 (update-kit over a directory where a file is expected: empty -> remove and continue, "
            "non-empty -> refuse with the remedy). BUG-0316 (hook_bundle_hash / diagram_hash break on autocrlf CRLF "
            "checkouts; the kit ships no .gitattributes for hashed paths; read-only git check-attr/check-ignore "
            "refused; a scratch-clone checkout read as a branch switch). BUG-0319 (kit-update merge backlog has no "
            "doors: resolve the pending list, adopt a kit template for a listed path, untrack paths the kit now "
            "ignores; the list reports project-vs-template divergence as a kit change; BOM). BUG-0317 (V1->V2 "
            "migration imports undispatchable tasks). BUG-0320 (gate_shell_hygiene: a QA order's own compose project "
            "is uncleanable, and the user's consent cannot be registered). BUG-0323 (craft memory: a shell write after "
            "`cd` into the memory dir unseen; an over-budget memory cannot be pruned)."],
        "outputs": [
            "each of BUG-0310, 0311, 0316, 0317, 0319, 0320, 0323 closed on the running path with a test naming it, "
            "red-first; the new doors joined to their registers (DEC-0121 (3)); installer/scaffold changes run once in "
            "a scratch project under the round-scratch folder (PowerShell; POSIX side by reading if no shell)"],
    },
]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: create_order_7_streams.py <base-commit>")
    base = sys.argv[1]
    env = dict(os.environ, PYTHONPATH="team-kits")
    for s in STREAMS:
        others = [o for o in STREAMS if o is not s]
        forbidden = [".claude/**", "project_memory/**", "radar/**"]
        for o in others:
            forbidden += [p for p in o["allowed"] if p not in s["allowed"]]
        where = ("STREAM %s (%s) of order 7, base commit %s. WORK IN YOUR WORKTREE %s on branch %s (the lead created "
                 "it); the main repo C:/Offline Repos/AgentAndSkills is read-only for you except its "
                 "project_memory/staging/(this task id)/ and the kernel commands. Two other streams run at the same "
                 "time in their own worktrees -- their files are in your forbidden_scope. "
                 % (s["key"], s["title"], base, s["wt"], s["branch"]))
        argv = list(KERNEL) + ["--product-requirement", "PR-0012", "--derives-from", s["derives"],
                               "--type", "implementation", "--assigned-role", "harness-implementer",
                               "--acceptance-ref", "AC-1", "--rung", "opus", "--effort", "high"]
        for p in s["allowed"]:
            argv += ["--allowed-scope", p]
        for p in sorted(set(forbidden)):
            argv += ["--forbidden-scope", p]
        for line in [where + SHARED] + s["inputs"] + COMMON:
            argv += ["--required-input", line]
        for line in s["outputs"] + ["protocol with every shared-file hunk named (file, section, why), the reading "
                                    "suites with results and clock times, the stream branch's final commit id"]:
            argv += ["--expected-output", line]
        r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        print(s["key"], r.stdout.strip()[-120:], (r.stderr.strip()[-800:] if r.returncode else ""))
        if r.returncode:
            return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
