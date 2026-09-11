"""The carrier of the sonnet-reachable DEC (default vs floor for the build class) plus TSK-0136's residues 1-4/8:
ONE small Opus order under PR-0011, created in DRAFT while TSK-0136's short verify runs; READY after its commit.
Usage: python create_sonnet_floor_order.py DEC-00xx   (the DEC id from capture_dec_sonnet_reachable.py)."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ENV = dict(os.environ, PYTHONPATH="team-kits")

ALLOWED = [
    "team-kits/dev-team/ladder.yaml", "team-kits/research-team/ladder.yaml", "team-kits/office-team/ladder.yaml",
    "team-kits/kernel/dispatch.py", "team-kits/kernel/report.py", "team-kits/kernel/schemas.py",
    "team-kits/*/hooks/gate_dispatch.py",
    "team-kits/dev-team/constitution/AGENTS.md", "team-kits/research-team/constitution/AGENTS.md",
    "team-kits/office-team/constitution/AGENTS.md",
    "team-kits/dev-team/skills/project-manager/SKILL.md", "team-kits/research-team/skills/project-manager/SKILL.md",
    "team-kits/office-team/skills/office-manager/SKILL.md",
    ".claude/agents/harness-verifier.md", ".claude/agents/harness-implementer.md",
    "tools/test_ladder.py", "tools/test_light_kit.py", "tools/test_report.py", "tools/test_schemas.py",
    "tools/test_model_pins.py", "tools/test_role_contracts.py", "tools/test_review_procedure.py",
    "tools/provider_observations.json", "tools/lead_package_sizes.json", "docs/reviews/phase0-disposition.md",
    "docs/POST_V2_WISHLIST.md", "README.md",
]
FORBIDDEN = [
    ".claude/settings.json", ".claude/hooks/**", "project_memory/**", "user/**", "radar/**",
    "team-kits/*/settings/**",
]


def inputs(dec):
    return [
        "%s (default vs floor for the build class; an ask below the default down to the floor only with a "
        "test-shaped acceptance; checkpoint line (c) shows default/floor/ask and carries Anthropic's two signals; "
        "lease_distribution per rung AND effort; the reading-discipline paragraph reaches the verifier text; item "
        "hygiene) -- cited by every file that implements it" % dec,
        "the committed tree after TSK-0136 (base): dev/research ladder.yaml `build: opus` (scalar), office `build: pin`; "
        "kernel/dispatch.py ladder_for_order (start = max(floor, ask), escalation from the order's start per DEC-0096, "
        "the effort exception as floor and ceiling); report.lease_distribution (per rung, 'runs to hand-back'); the "
        "constitutions' ONE bold ladder statement and the reading-discipline paragraph (byte-identical x3 + "
        "harness-implementer.md); tools/test_ladder.py / test_light_kit.py readers",
        "staging/FR-0091/summary.md precisions 1 and 2 (the checkpoint names the two signals; a Sonnet slice carries a "
        "test, never a description) and research-A-anthropic.md section 3 (the two escalation signals, verbatim)",
        "TSK-0136 protocol section 6 residues 1 (report.py), 2 (research PM file = agents/project-manager.md), 3 "
        "(test_model_pins.py docstring), 4 (harness-verifier.md), 8 (run_2 label)",
        "HOST RULES: one pytest at a time with timeouts derived from measured durations; reading suites only (DEC-0088 "
        "(d)); no full run; clock read; scratch under C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/; "
        "read end lines and named sections only (DEC-0095 (6))",
        "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/",
    ]


def outputs(dec):
    return [
        "LADDER SHAPE (%s (1)): dev/research `build: {default: opus, floor: pin}`; office unchanged (`build: pin`); the "
        "ladder reader accepts the scalar form as default = floor; _valid_ladder refuses a default below the floor or "
        "outside the rungs; the two-ended tripwire test covers both spellings; each changed line cites the DEC." % dec,
        "DERIVATION (%s (2)): ladder_for_order -- no ask -> default; ask above -> max(default, ask) capped by top; ask "
        "BELOW default -> allowed down to the floor ONLY when the order's acceptance is test-shaped (an expected_output "
        "naming a test file/path under tools/ or tests/, or --acceptance-ref to an AC whose text names a test) -- else "
        "the default stays and the lease `why` says why; red-first: (a) `--rung sonnet` on a test-carrying build order "
        "-> sonnet, (b) the same ask with a description-only order -> opus with the reason, (c) an ask below the floor "
        "-> refused; measured on a scaffolded dev pilot AND on the office ladder (unchanged behaviour)." % dec,
        "CHECKPOINT (%s (3)): line (c) prints default / floor / ask / chosen; the self-question carries Anthropic's two "
        "signals verbatim from research A ('confidently wrong with full context -> a larger model; skipped a file, "
        "tests not run, bailed -> more effort'); mirrored byte-identical x3 (gate_dispatch.py); process test rc 0." % dec,
        "DISTRIBUTION (%s (4)): report.lease_distribution counts runs-to-hand-back per rung AND per effort; the brief "
        "line shows both; red-first on the effort half; schemas updated." % dec,
        "TEXTS: the PM skills' three-line rule gains the clause 'sonnet only with a test as acceptance' (FR-0091 "
        "precision 2); the constitutions' bold ladder statement says default opus / floor pin / test-carrying slices "
        "may ask sonnet; the reading-discipline paragraph copied byte-identical into .claude/agents/harness-verifier.md "
        "(tripwire extended); tools/test_model_pins.py docstring in scope; provider_observations.json run_2 label "
        "'wall-clock (API)'.",
        "RUNS: tools/test_ladder.py, test_light_kit.py, test_report.py, test_schemas.py, test_model_pins.py, "
        "test_role_contracts.py, test_review_procedure.py in full, one at a time; `python tools/bump_kit_version.py` "
        "(kit files change -> one stamp); ruff on tools and team-kits; validate.py; protocol in project_memory/staging/"
        "(this task id)/protocol.md (file table, red-first rows with the arbiter's line, (g) row, patch path, EVD "
        "lines); no commit, no push.",
    ]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: create_sonnet_floor_order.py DEC-00xx")
    dec = sys.argv[1]
    argv = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task",
            "--product-requirement", "PR-0011", "--derives-from", "PR-0011",
            "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-3",
            "--dependency", "TSK-0136", "--rung", "opus", "--effort", "high"]
    for p in ALLOWED:
        argv += ["--allowed-scope", p]
    for p in FORBIDDEN:
        argv += ["--forbidden-scope", p]
    for line in inputs(dec):
        argv += ["--required-input", line]
    for line in outputs(dec):
        argv += ["--expected-output", line]
    r = subprocess.run(argv, cwd=ROOT, env=ENV, capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip()[-400:])
    if r.returncode != 0:
        print(r.stderr.strip()[-1200:])
        return r.returncode
    tsk = r.stdout.strip().split()[0]
    u = subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "update", dec],
                       cwd=ROOT, env=ENV, input=json.dumps({"work": [tsk, "PR-0011"]}),
                       capture_output=True, text=True, encoding="utf-8")
    print((u.stdout.strip() or u.stderr.strip())[-200:])
    return u.returncode


if __name__ == "__main__":
    sys.exit(main())
