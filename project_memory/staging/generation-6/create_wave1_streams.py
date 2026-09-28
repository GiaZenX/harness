"""Plan V2.5 (DEC-0124) WELLE 1 -- four parallel streams A-D (D, the frontend review tool FR-0094, held back at first and taken back in 2026-09-27 ~19:4x: the user, 'das Kommentar overlay ist fertig'), each in its own worktree, seam declared up front;
then one merge with one verifier and the full run after its PASS (DEC-0121 (1), counter-review: the full run after a
merge is mandatory). Built on the commit that delivers order 7.
Usage: python create_wave1_streams.py <base-commit>"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]
WT = "C:/Offline Repos/v2-testbed/_worktrees/"
KITS = ("dev-team", "office-team", "research-team")
PLAN = "docs/PLAN_V2_5_VEREINFACHUNG.md"
SEAM = (["README.md", "docs/**", "team-kits/*/skills/**", "team-kits/*/constitution/**", "team-kits/kernel/cli.py",
         "team-kits/kernel/report.py", "team-kits/kernel/board.py"]
        + ["team-kits/%s/hooks/%s" % (k, h) for k in KITS for h in ("_compat.py", "_kernel.py")]
        + ["team-kits/%s/settings/settings.json" % k for k in KITS])

COMMON = [
    "THE PLAN %s (read sections 1, 2, 4, 5 and 8) and DEC-0124 are the order; the baseline "
    "project_memory/staging/FR-0089/metrics-0-baseline-2026-09-27.md is what you improve and must re-measure for "
    "your part. KEY BASELINE FINDING: the PM skill (skills/project-manager/SKILL.md, 50-55 KB) is NOT loaded at a PM "
    "session start and was never invoked in synaipse's sessions -- a rule that lives only there does not reach the PM; "
    "put what must hold into MECHANISM or into a text that is really loaded." % PLAN,
    "RULES: G1-G6 of the plan are held by mechanism; DEC-0100 (a bug closes on a test that NAMES it), DEC-0116 "
    "(structural contracts, the path that runs, no free-text readers), DEC-0121 (resolved paths; new commands join "
    "their registers; protocol as you go), DEC-0080 rule 2 (every suite that READS a changed rule as its own "
    "selection); the counter-review's KEEP list in the plan's section 2 (DEC-0026, DEC-0056 (c), DEC-0097/0112, "
    "DEC-0063 (3), DEC-0107, verifier stays Mega). Every building block you REMOVE names the DEC it supersedes in "
    "your protocol's section 'Supersedes' (stream F collects them). Kit hooks mirrored x3.",
    "PROCESS: work in YOUR worktree on YOUR branch; the main repo is read-only for you except "
    "project_memory/staging/(this task id)/ and kernel commands run from the main repo; commits in the worktree are "
    "refused by this repo's gate 3 (known) -> stage everything (`git add -A` in the worktree), no commit. Red-first "
    "copies under C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/. NO stamp and NO full run in a stream. "
    "Long commands in the background with a completion wait (never a sleep loop); one pytest at a time; read files over "
    "2,000 lines by section; clock read for every time you write; protocol AS YOU GO in "
    "project_memory/staging/(this task id)/protocol.md. State through the main repo's kernel only; an EVD per closed "
    "item naming its node; no transitions, no push, no mint. SHARED SEAM (declared on all four orders): README, "
    "docs, the kits' skills and constitutions, cli.py, report.py, board.py, _compat/_kernel, the kits' settings.json "
    "-- touch only your section, name every hunk in the protocol.",
    "CADENCE AND SPEED (the user 2026-09-28: 'mehr coden, danach gesammelt pruefen', 'muessen schneller werden'; "
    "DEC-0088): no verifier during the stream -- ONE verifier over the merged wave; its BLOCKING findings are only "
    "wrong behaviour, a security gap whose chain runs in one session, data loss, a test that cannot fail -- text, "
    "comments, counts and over-refusals are COLLECTED and fixed in the next block. Build the whole stream in one "
    "pass, touch each file once with all its changes. READING SUITES are found by the CALLERS of every changed "
    "predicate (grep / AST), never by -k keywords; every run with a time budget (a `timeout` prefix is refused by "
    "gate 1 -- use a runner that kills after N s); temp dirs without spaces for hook-chain tests. Every `capture "
    "--hole` carries `limits` at once. Probes of a protected directory write a neutral sentinel file, never a real "
    "configuration file.",
]

STREAMS = [
    ("A", "g8/approvals", "approvals and acceptance walkthrough", "DEC-0123",
     ["team-kits/kernel/approvals.py", "team-kits/kernel/sdk_approval.py", "team-kits/kernel/walkthrough.py"]
     + ["team-kits/%s/hooks/%s" % (k, h) for k in KITS for h in ("gate_approval.py", "guard_question_context.py")]
     + ["tools/test_wave1_a_*.py", "tools/test_approval*.py", "tools/test_approvals*.py"],
     ["DEC-0123 (the acceptance WALKTHROUGH at the end: a kernel command that lists the delivered items in order -- "
      "goal, then its CRs, FRs, BUGs -- each with what was asked (criteria / the user's verbatim words), what was "
      "built (EVD, test nodes, screenshots if any) and ONE question per item; no acceptance/delivery/verification "
      "question while the approved plan's work is still open -- measure where the kernel or the kits' texts ask "
      "early and stop it on the running path). DEC-0119 finished: approval kinds 15 -> ~6 (plan, collected "
      "understanding card, walkthrough acceptance, push, kit_update, routine, preset -- say the final list and what "
      "each removed kind maps to); the change-wish flow 'did I understand you right? -> yes -> build' for EVERY new FR and CR alike (the user 2026-09-28: plan meticulously until a shared understanding, ONE approval, then SRs/TSKs are derived and everything runs autonomously; a new FR/CR is questioned until understood, then approved once and built into the running block); workshop holes "
      "closed by the lead with a protocol and WITHOUT a user click (a new DEC superseding DEC-0056's click for "
      "workshop holes -- capture it). Build on what order 7's stream A delivered (calm card, scope --batch). "
      "ALSO (moved here from TSK-0157's verify F1, staging/TSK-0157/verify-round-1.md): the document "
      "addition/revision cards still show a staging path in their read text (approvals.py ~:2709/:2724), a "
      "deviation from DEC-0119 (6) 'no paths' named only in a protocol -- make the card path-free (say where the "
      "proposal is in words) or, if a path is genuinely needed, name DEC-0119 (6)'s exception at that site."],
     ["the walkthrough command + the PM flow using it, tests naming DEC-0123 (process tests: nothing asked while work "
      "is open; the walkthrough lists items with their proofs)", "the reduced approval-kind set with a structural "
      "test and the mapping table", "the new DEC for workshop holes without clicks, captured"]),
    ("B", "g8/protection", "protection layer", "BUG-0325",
     ["team-kits/kernel/state.py", "team-kits/kernel/writelog.py", "team-kits/kernel/lock.py"]
     + ["team-kits/%s/hooks/%s" % (k, h) for k in KITS for h in (
         "gate_write_scope.py", "gate_git.py", "guard_harness_selfmod.py", "gate_subagent_output.py")]
     + ["tools/test_wave1_b_*.py", "tools/test_hooks.py", "tools/test_hooks_v2.py", ".claude/hooks/test_gates.py"],
     ["PLAN section 4 stream B, in THIS order: (1) a kernel WRITE LOG (path + checksum per state write, append-only, "
      "under the state's .audit/) -- it does not exist today (counter-review); (2) an after-check at Stop and before "
      "every commit/merge: every changed state file is in the write log, else refuse by name; (3) an approval "
      "after-check: every new APR matches a real AskUserQuestion answer in the session transcript (replaces the H80 "
      "wall that falls with the write-target guessing); (4) ONLY THEN remove the WRITE-TARGET GUESSING for shell lines "
      "from gate_write_scope (keep the exact Write/Edit path check; keep _compat's git/push/docker/test-run readers -- "
      "G4/G6/gate 5); (5) measure `permissions.deny` in a pilot copy (Windows, bypass mode, Codex if a CLI is present) "
      "and add it only as an extra layer if it holds. MEASURE before and after on a fixed list: the stored attack "
      "lines of the command-line holes (H11/H16/H204/H214/H219 and friends: each must be caught at the latest by the "
      "after-check) and 50 typical READ commands (0 refusals). This repo's own gate (.claude/hooks/_harness.py) is the "
      "user's file: its part goes into ONE user-patch file + idempotent apply script with --check. "
      "HARD CONSTRAINT measured 2026-09-28 (BUG-0335, TSK-0161 measure_0335.py): a shell write that overwrites "
      ".claude/settings.json UNREGISTERS every hook, so NO after-check inside the hook system can ever see it -- "
      "the removal in (4) must keep a pre-check (or an equivalent the provider enforces, e.g. permissions.deny if "
      "(5) measures it holding for Bash) for shell writes into the provider tree (.claude/ settings + hooks, and "
      "the Codex equivalents); say in the protocol which mechanism carries it. Also in this stream (from BUG-0333's "
      "forensics: BUG-0336 and BUG-0337/H230; plus the accepted exceptions H227/BUG-0331 and H228/BUG-0332, which this stream closes, and the unconfirmed guard hints of the order-7 block verifier at C:/Offline Repos/v2-testbed/_round-scratch/TSK-0163-verify/out1.txt, which the provider-tree write restriction must cover): an order-level pass must not mask a goal-level fail in the "
      "delivery verdict, and rebase/cherry-pick/merge-tree onto a delivery branch meet the delivery rule. READING "
      "SUITES are found by the CALLERS of every changed predicate (grep), never by -k keywords -- order 7's merge "
      "missed a red node that way."],
     ["writelog + after-checks with red-first tests naming the holes they cover", "the write-target guessing removed "
      "from the kits' gate; the attack list caught by the after-check; the 50 read commands pass (a table in the "
      "protocol)", "permissions.deny measured and its verdict", "user-patch file for this repo's gate"]),
    ("C", "g8/pm", "PM intelligence and efficiency", "BUG-0318",
     ["team-kits/kernel/dispatch.py", "team-kits/kernel/scopes.py", "team-kits/kernel/checkpoints.py",
      "team-kits/kernel/heartbeat.py", "team-kits/gen_provider_artifacts.py", "team-kits/model_tiers.yaml",
      "team-kits/scaffold_team.ps1", "team-kits/scaffold_team.sh", "ladder.yaml", "tools/radar_routine.py",
      "radar/README.md", ".codex/agents/**"]
     + ["team-kits/%s/%s" % (k, p) for k in KITS for p in ("ladder.yaml", "agents/**", "presets.yaml")]
     + ["team-kits/%s/hooks/%s" % (k, h) for k in KITS for h in (
         "gate_dispatch.py", "guard_agent_spawn.py", "notify_agent_events.py", "session_status.py")]
     + ["tools/test_wave1_c_*.py", "tools/test_ladder.py", "tools/test_model_ladder.py", "tools/test_radar_trigger.py"],
     ['EFFORT DEFAULTS come from FR-0097 (project_memory/staging/FR-0097/research-effort-by-role-2026-09-28.md, section 5) AS DECIDED BY THE USER IN DEC-0127: PM Giga (Opus) xhigh; designer Giga xhigh for a first draft, high for revisions; builder WITH spec+test Giga medium, builder on an unclear spec or a bug hunt Giga high; Mega (Sonnet) builder for mechanical work high; verifier Giga high (xhigh once, named); class names per DEC-0129; architect xhigh only as DEC-0118 says until measured. Escalation: a MISREAD requirement goes back to the planner with a question (more effort does not fix it), a MISSED case raises effort one step. Effort per role variant via the subagent frontmatter `effort:` (Codex: model_reasoning_effort in .codex/agents/*.toml; Astra needs an explicit level). Order a separate measurement for builder medium vs high and architect xhigh vs high. MODEL CLASS = THE MODEL ONLY (DEC-0129, the user 2026-09-28): Milli < Kilo = Haiku < Mega = Sonnet < Giga = Opus < Tera = Fable < Peta; EFFORT is the separate second axis (DEC-0127 per role); other providers are placed on the same scale by honest capability, empty rungs allowed. Usage rules: Kilo never writes code (a read-only routine use opens only after the DEC-0128 (3) measurement with a hallucination check); Tera only for a named step with a MEASURED advantage over Giga. Task-to-CLASS questions and escalation: DEC-0130 (from the research FR-0098, project_memory/staging/FR-0098/research-model-classes-2026-09-28.md) -- protected surface or irreversible -> never below Giga; read-only summary -> Kilo (once opened); a test decides and at most N files (N=3, measured) -> Mega; else Giga; escalation effort first, class later, a misread goes back as a question; Codex builds with Sol (Mega) high until Astra (Tera) is measured; no automatic Fable after a third failure (re-cut). The answers ARE the closed reason list the hook checks; the class-to-model table per provider is ONE data file maintained by measurement. TEST BENCH per DEC-0131: the mapping changes only on a new model, after a bench measurement, with the user agreeing on a card with the numbers; build the bench (per class fixed real tasks from archived TSKs with red/green tests, >= 3 runs per candidate and effort, cost per SOLVED task, actual model from the transcript) and make the watchers new-model question trigger a bench run. MODELS: DEC-0126 (aliases stay unversioned; measure what each new model is good for; the PM picks the combination from the guide file) -- build the measurement harness (fixed repo tasks with tests; solved / tokens / cost per solved task / rounds; ACTUAL model and effort read from the transcript), first subjects Sonnet 5.5 (incl. the office kit Sonnet default) and builder medium vs high. CODEX (radar/2026-09-28-codex-by-claude.md part 1): Codex now supports a hook on subagent start (inspect/stop/rewrite) and takes model + effort PER START -- our generator still assumes neither; a role file that fixes model/effort makes Codex ignore the per-start request; re-check the reasons of the accepted exceptions H169/H173 and put them to the user again if they no longer hold; max_threads is a legacy alias, keep max_depth.',
      "PLAN section 4 stream C and the user's decisions in section 4 (Welle 0 block): TWO AXES model class "
      "(Kilo/Mega/Giga, Tera free) x effort (niedrig/mittel/hoch/sehr hoch), the PM picks both per order WITH a reason "
      "from a CLOSED list a hook enforces (not free text, DEC-0092 (1)); role VARIANTS generated per class x effort "
      "(effort is not settable per spawn, H169); Haiku never in the ladder; keep the hard-won rules (Kilo only with a "
      "test acceptance, rework not on the top, mechanical fails do not climb, verifier Mega); a MODEL GUIDE file "
      "('which model/effort for what', sourced, measured) in every PM session brief; the watchers BROADER (two parts "
      "per report: what it brings THIS repo, what changed overall with a second look; a mandatory 'does a new model "
      "replace a ladder model?' with a measured proof on fixed sample tasks before any swap; they keep the model guide "
      "current) -- the watcher definition files are the user's (.claude/agents) -> user-patch lines. HEARTBEATS instead "
      "of polling: every long run (test run, subagent, background command) writes a life sign; a missed sign past a "
      "deadline is reported as hung/failed to whoever waits (baseline: a run hung ~42 h unnoticed). BLOCKS instead of "
      "slices: at create-task the kernel says 'these files are already in open block X -> append instead of a new "
      "order', a new CR lands in the running block whose files it touches; parallel builders by default where "
      "check-scopes measures disjoint; a board view 'geliefert / in Arbeit / wartet auf dich / Verbrauch'. And the "
      "baseline finding: the PM's essential rules move into what is really loaded (the constitution's top) or into "
      "mechanism."],
     ["two-axis choice with the closed reason list enforced at spawn, role variants generated, tests",
      "model guide file in the brief; watcher duties + user-patch lines for the watcher definitions",
      "heartbeat module + deadline report with a process test (a silent run reported within the deadline)",
      "block/CR placement hints and parallel-by-default at create-task/dispatch, tests; the board view"]),
    ("D", "g8/frontend", "frontend review tool", "FR-0094",
     ["team-kits/dev-team/templates/repo/scripts/**", "team-kits/dev-team/hooks/gate_design_sighted.py",
      "team-kits/dev-team/skills/product-designer/**", "team-kits/dev-team/agents/product-designer.md",
      "tools/test_wave1_d_*.py", "tools/test_design_conformance.py"],
     ["FR-0094: adopt synaipse's standalone preview comment tool (C:/Offline Repos/synaipse-unified, its PR-0031 "
      "(accepted), PR-0032 and CR-0021 (the finishing touches: the bubble shows existing pins, edit/delete, "
      "multi-spot) -- READ ONLY there; the user said 2026-09-27 ~19:4x 'das Kommentar overlay ist fertig'. Find the "
      "tool at its LATEST state (committed, or still in a synaipse worktree / uncommitted -- say which commit or "
      "file state you adopted), its documented comment file format and its tests) into the dev-team kit as a "
      "kit-owned script next to kit_design_render.py; the product-designer's flow uses it ('#' at the cursor -> pin + "
      "screenshot + element/page/viewport/theme; nothing in the design overwritten); comments become the designer's "
      "input; add the lock synaipse left to the kit: gate_design_sighted refuses freezing a draft while it has open "
      "comments. Keep synaipse's format so both stay compatible. LATEST VERSION RULE (user, 2026-09-27 ~20:5x): read synaipse's tool at the START of your work, not from any earlier note; record the adopted state (commit + file hashes); and ONCE MORE right before you hand over, compare synaipse's current tool against what you adopted -- if it changed, take the change over (same format) and say so in the protocol."],
     ["the tool in the kit with its tests (a synthetic preview + comment file)", "the freeze lock on open comments, "
      "red-first", "the designer's flow text (short)", "the synaipse state adopted, named (commit or file hashes)"]),
]


def main():
    base = sys.argv[1]
    env = dict(os.environ, PYTHONPATH="team-kits")
    for key, branch, title, carrier, allowed, inputs, outputs in STREAMS:
        others = [s for s in STREAMS if s[0] != key]
        forbidden = [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py",
                     ".claude/agents/**", "project_memory/**", "radar/20*.md", "radar/decided.md"]
        for o in others:
            forbidden += [p for p in o[4] if p not in allowed and p not in SEAM]
        where = ("STREAM %s (%s) of WELLE 1 of plan V2.5, base commit %s. WORK IN YOUR WORKTREE %s%s on branch %s "
                 "(the lead creates it). Three other streams run at the same time in their own worktrees."
                 % (key, title, base, WT, "g8-" + branch.split("/")[1], branch))
        argv = list(KERNEL) + ["--product-requirement", "PR-0012", "--derives-from", carrier if carrier.startswith(("BUG", "PR", "CR", "EXP")) else "PR-0012",
                               "--type", "implementation", "--assigned-role", "harness-implementer",
                               "--acceptance-ref", "AC-1", "--rung", "opus", "--effort", "high"]
        for p in allowed + SEAM:
            argv += ["--allowed-scope", p]
        for p in sorted(set(forbidden)):
            argv += ["--forbidden-scope", p]
        for p in SEAM:
            argv += ["--seam-scope", p]
        for line in [where] + inputs + COMMON:
            argv += ["--required-input", line]
        for line in outputs + ["protocol with every seam hunk, the supersession list, the reading suites with results "
                               "and clock times, the section-5 metric of your part before/after"]:
            argv += ["--expected-output", line]
        r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        print(key, r.stdout.strip()[-100:], r.stderr.strip()[-800:] if r.returncode else "")
        if r.returncode:
            return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
