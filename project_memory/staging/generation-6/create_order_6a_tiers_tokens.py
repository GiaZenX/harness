"""Order 6a (2026-09-25): the user's tier decision DEC-0114 (BUG-0306), DEC-0098 (3) (BUG-0307) and the token levers of
FR-0093 -- ONE builder (Opus, high), because every line spans the kits' texts and tools/ tests (DEC-0101: parallel only
where measured disjoint; here the lead skills carry both the tier prose and the order lines). The user said 'leg los'
to the lead's recommended sequence (tiers first, then FR-0093, then order 6) and the three are cut into one order to
spend one verification instead of three.
Usage: python create_order_6a_tiers_tokens.py <base-commit>"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

ALLOWED = ["team-kits/**", "tools/**", "docs/**", "user/**", "README.md", "CLAUDE.md", "ladder.yaml",
           ".claude/hooks/test_gates.py", ".codex/agents/**", "radar/README.md"]
FORBIDDEN = [".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py", ".claude/agents/**",
             "project_memory/**", "radar/20*.md", "radar/decided.md", "radar/routine.json"]


def inputs(base):
    return [
        "BASE COMMIT %s. THE USER'S DECISION DEC-0114 (read it whole; it is the order): codex rungs opus -> gpt-6-sol, "
        "sonnet -> gpt-6-luna, top gpt-6-astra unchanged; Claude names stay pass-through ON PURPOSE (no resolution test); "
        "NO price anywhere in team-kits/model_tiers.yaml (both providers, and every price-derived watch date) -- instead per "
        "rung and provider WHAT THE MODEL IS SUITED FOR, vendor wording with source URL and read date, sources in "
        "radar/2026-09-25-claude-by-claude.md (model lineup table) and radar/2026-09-25-codex-by-claude.md item 1; the "
        "header sentences that turn false are reworded (no luna row; never an automatic bump); on CLAUDE no class, pin or "
        "escalation step resolves to Fable (the architecture class and the ladders' `top: fable` included) -- the smallest "
        "form is preferred (e.g. the Claude translation of the top rung), say in the protocol which form and why; the "
        "Codex top stays astra. BUG-0306 carries the measurement and two ACs" % base,
        "BUG-0307 / DEC-0098 (3): tools/radar_routine.py SCHEDULE_AS_TOLD -> Friday ~20:00 for all four, source DEC-0098; "
        "the stagger test becomes 'per app one task runs its watchers in sequence' (the Claude Desktop task is "
        "`watcher-duo`, ~/.claude/scheduled-tasks/watcher-duo/SKILL.md, created 2026-09-25; radar/routine.json is the "
        "lead's record and is NOT yours); the watcher definitions' descriptions (.claude/agents/*-watcher.md are the "
        "user's files -> patch file, see below) and .codex/agents/*-watcher.toml (`--write-overlays`) follow",
        "FR-0093 (token levers, measured 2026-09-25: polling 3.5%% of context read, context per turn median 285k / p90 "
        "591k, resumed rework agents 500-750k): put THREE order lines into every kit's lead text that writes orders "
        "(grep the lead skills/constitutions for where an order's rules stand -- one home per kit, no second copy): (1) a "
        "rework is a FRESH agent given only the verify report, the item and the protocol path, never a resume of the "
        "builder; (2) a run longer than a few minutes starts in the background and the agent waits for its completion "
        "notice, no sleep/tail polling loops; (3) files over 2,000 lines and protocols are read by section, never whole. "
        "PLUS a measuring script tools/measure_agent_tokens.py that reads Claude Code subagent transcripts (jsonl under "
        "~/.claude/projects/<project>/<session>/subagents/ -- measure the real layout first) and prints per agent: turns, "
        "context per turn (median/p90), total input read, polling turns; a test on a synthetic transcript. It is the "
        "before/after instrument FR-0093's acceptance asks for; the 'after' is measured on the NEXT order, not this one",
        "THE USER'S FILES (gate 1 refuses them to every role): write ONE patch file "
        "project_memory/staging/(this task id)/user-patch.md with before/after text and anchors that occur exactly once, "
        "for: `effort: xhigh` in .claude/agents/harness-lead.md (DEC-0114 (5)); the FR-0093 three lines in this repo's "
        "role texts where orders are generated (harness-lead.md 'Before an order goes out'); the watcher descriptions' "
        "Sat/Sun/Mon sentences (DEC-0098). Also a runnable apply script beside it in the style of "
        "project_memory/staging/user-patch/apply_user_patch.py (all-or-nothing, --check)",
        "REACH (DEC-0080 rules 1/2, measured by the lead): the tier file is read by team-kits/kernel/dispatch.py, "
        "team-kits/gen_provider_artifacts.py, team-kits/*/hooks/session_status.py, tools/validate.py, tools/radar_routine.py "
        "and the suites tools/test_model_ladder.py test_model_pins.py test_ladder.py test_light_kit.py "
        "test_approvals_dispatch.py test_hooks.py test_radar_trigger.py test_repo_hygiene.py test_review_procedure.py -- "
        "grep again yourself, and run every suite that READS what you changed as its own selection, listed in the protocol",
        "RULES: DEC-0100 (a bug closes only on a test that NAMES it: BUG-0306 and BUG-0307 in the docstring's first "
        "paragraph), red-first in a .git-less copy under C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/, "
        "DEC-0102 (2)/(4)/(5); no comment claims protection the code does not build (SR-0008)",
        "HOST RULES (DEC-0094/0095 (6)) AND FR-0093 APPLIED TO YOURSELF: one pytest at a time, selections < 3 min measured; "
        "any run longer than ~2 min in the BACKGROUND with a completion wait, never a sleep loop; read big files by section; "
        "ONE stamp (`python tools/bump_kit_version.py`) then the full run ONCE at the end with `DELIVERY_RUN=<this task "
        "id>`; `.claude/hooks/test_gates.py` as its own run; clock read for every time you write; protocol as you go in "
        "project_memory/staging/(this task id)/protocol.md",
        "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/; state writes through the kernel "
        "only: an EVD per closed bug with the naming node in the run command; no transition of BUG/FR items; no commit, "
        "no push, no mint, no rollout (the lead rolls out after the verifier)",
    ]


OUTPUTS = [
    "team-kits/model_tiers.yaml per DEC-0114 (codex gpt-6-sol/gpt-6-luna/gpt-6-astra, no prices, a suitability line per "
    "rung and provider with source and read date, true header) + the Claude-side no-Fable form, measured through "
    "`kernel.cli ladder` answers for every kit (BUG-0306 AC-2)",
    "a test naming BUG-0306 (red on the base, green after) and a test naming BUG-0307 (red on the base, green after)",
    "tools/radar_routine.py with DEC-0098's schedule + the reworked stagger test; .codex/agents/*-watcher.toml regenerated",
    "the three FR-0093 order lines, one home per kit, and tools/measure_agent_tokens.py with its test; the script's output "
    "on this repository's last order (TSK-0150's subagents if the transcripts are still on disk) as the BEFORE baseline "
    "in the protocol",
    "project_memory/staging/(this task id)/user-patch.md + apply script (lead effort xhigh, FR-0093 lines in harness-lead.md, "
    "watcher description sentences), --check run on the base green",
    "kit stamp bumped once; full run with DELIVERY_RUN once; test_gates.py run; EVDs per bug; protocol with the suites "
    "that read the changed contract, each with its result and clock time",
]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: create_order_6a_tiers_tokens.py <base-commit>")
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0012", "--derives-from", "BUG-0306", "--type", "implementation",
        "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-1", "--acceptance-ref", "AC-2",
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
