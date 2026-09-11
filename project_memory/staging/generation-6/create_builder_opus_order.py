"""DEC-0095's carrier under PR-0011: ONE small work order (Opus, mechanical slice with a complete spec) -- the kits'
ladder classes (build: opus, planning: opus; architecture stays top), the PM pins, this repo's harness-lead pin, the
texts that state the tiers, red-first. Created in DRAFT while TSK-0135's goal round runs; READY after the
generation-6 commit (one writer). Not idempotent -- run once."""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

ALLOWED = [
    "team-kits/dev-team/ladder.yaml", "team-kits/research-team/ladder.yaml", "team-kits/office-team/ladder.yaml",
    "team-kits/dev-team/agents/project-manager.md", "team-kits/research-team/agents/research-lead.md",
    "team-kits/office-team/agents/office-manager.md",
    "team-kits/dev-team/constitution/AGENTS.md", "team-kits/research-team/constitution/AGENTS.md",
    "team-kits/office-team/constitution/AGENTS.md",
    "team-kits/dev-team/skills/project-manager/SKILL.md", "team-kits/research-team/skills/project-manager/SKILL.md",
    "team-kits/office-team/skills/office-manager/SKILL.md",
    "team-kits/model_tiers.yaml", "team-kits/kernel/dispatch.py",
    ".claude/agents/harness-lead.md", ".claude/agents/harness-implementer.md",
    "tools/test_ladder.py", "tools/test_model_ladder.py", "tools/test_light_kit.py", "tools/test_role_contracts.py",
    "tools/test_review_procedure.py", "tools/lead_package_sizes.json", "docs/reviews/phase0-disposition.md",
    "docs/POST_V2_WISHLIST.md", "README.md", "CLAUDE.md",
]
FORBIDDEN = [
    ".claude/settings.json", ".claude/hooks/**", "project_memory/**", "user/**", "radar/**",
    "team-kits/*/hooks/**", "team-kits/*/settings/**",
]
INPUTS = [
    "DEC-0095 (builder default opus; orchestrator opus; verifier opus; Fable only for the architecture step of a "
    "LARGE goal and as the escalation target after a failed opus build; cost discipline) -- cited by every file that "
    "implements it; DEC-0088 (1) is superseded on the tier line and stays on cadence; DEC-0091 (rung per order, "
    "max() with the floor) and DEC-0034 rule 2 (one rung per FAIL) are the mechanics Fable is reached through",
    "the committed generation-6 tree (base after TSK-0135's commit): team-kits/*/ladder.yaml classes today -- dev/"
    "research planning: top, architecture: top, design: opus, qa: opus, build: pin; office planning: top (= opus), "
    "qa: opus, build: pin, reading: pin; pins today -- dev project-manager `model: fable`, office-manager `lead`, "
    "build roles `worker`; this repo: harness-implementer opus, harness-verifier opus, harness-lead NO model line "
    "(the session runs on the platform default); tools/test_ladder.py + test_model_ladder.py + test_light_kit.py "
    "read the ladders, the pins and the constitutions' ladder paragraph (one bold statement carrying both axes)",
    "the (g) tables of generations 5 and 6 (round logs) -- the numbers the change is measured against later: "
    "rounds-to-PASS per rung in report.lease_distribution",
    "HOST RULES: one pytest at a time with timeouts derived from measured durations; reading suites only (a slice "
    "under a goal, DEC-0088 (d)); no full run; clock read; scratch under C:/Offline Repos/v2-testbed/_round-scratch/"
    "(this task id)/; agents read end lines and named sections, never whole logs (DEC-0095 (6))",
    "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/",
]
OUTPUTS = [
    "LADDERS (DEC-0095 (1)/(2)/(4)): in dev-team and research-team ladder.yaml `build: opus` and `planning: opus`, "
    "`architecture: top` kept, design/qa unchanged; office-team UNCHANGED (its floors are DEC-0078's: build "
    "and reading stay pin, top is opus already) -- the protocol states why; each changed "
    "line cites DEC-0095; red-first: the ladder reader (tools/test_ladder.py) has a test asserting the build class of "
    "dev/research starts on opus and the architecture class on top, red on the old `build: pin`.",
    "PINS (DEC-0095 (2)): dev project-manager.md `model: opus`, research-lead.md and office-manager.md on the opus "
    "rung (the `lead` alias resolves to opus -- keep or spell, say which), this repo's .claude/agents/harness-lead.md "
    "gets `model: opus` (effective at the next session start -- the protocol says so), harness-implementer stays "
    "opus; test_model_pins / test_role_contracts red on a `fable` PM pin.",
    "TEXTS: the constitutions' ladder paragraph (the ONE bold statement carrying both axes -- seam N18 / H191's "
    "reader) says: build starts on opus, architecture on the top rung, escalation climbs one rung per failed run, "
    "Fable is reached by failure or by the architecture step, never chosen as a standing tier; the PM skills' "
    "three-line rule (DEC-0091) unchanged; model_tiers.yaml's header names DEC-0095 beside DEC-0076; README's tier "
    "sentence follows; the reading tests (test_review_procedure, test_model_ladder) stay green and one of them is red "
    "on a paragraph that names fable as the build start.",
    "COST DISCIPLINE TEXT (DEC-0095 (6)): the harness-implementer / harness-verifier role texts of this repo and the "
    "kits' implementing roles carry the reading rule (end lines and named sections, never whole logs; short reports) "
    "-- byte-identical where shared (the comment-discipline pattern), with the tripwire test extended.",
    "RUNS: tools/test_ladder.py, test_model_ladder.py, test_light_kit.py, test_role_contracts.py, "
    "test_review_procedure.py, test_model_pins.py in full; `python tools/bump_kit_version.py` (kit files change -> "
    "one stamp); ruff + validate.py green; protocol in project_memory/staging/(this task id)/protocol.md with the "
    "file table, the red-first rows (arbiter's failure line), the (g) row, the patch path; no commit, no push.",
]


def main():
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0011", "--derives-from", "PR-0011",
        "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-3",
        "--dependency", "TSK-0135", "--rung", "opus", "--effort", "high",
    ]
    for path in ALLOWED:
        argv += ["--allowed-scope", path]
    for path in FORBIDDEN:
        argv += ["--forbidden-scope", path]
    for line in INPUTS:
        argv += ["--required-input", line]
    for line in OUTPUTS:
        argv += ["--expected-output", line]
    env = dict(os.environ, PYTHONPATH="team-kits")
    result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    print(result.stdout.strip()[-600:])
    if result.returncode != 0:
        print(result.stderr.strip()[-1500:])
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
