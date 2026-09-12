"""PR-0012 'Bug-Null', order 3b cut into THREE parallel streams by MEASURED file families (DEC-0101: the lead
measures the partition at every cut; the user, 2026-09-12: 'Koennen wir sie nicht parallel abarbeiten mit
mehreren Stroemen? Es dauert mir wieder zu lange'). Input: staging/TSK-0140/order-3b-candidates.md (121 rows:
95 ja / 8 gesperrt / 18 nein) read by family with families.py, plus the verifier's round-2 corrections (G2: H14 and
H153 are gesperrt; G4: H141 is ja), the 14 re-filed holes (H197-H210, refile_unclicked_exceptions.py), H184 and
the seven real defects. Three allowed_scopes with NO common tracked file (check-scopes is the reading, run before
READY); the shared files -- VERSION stamps, kernel/known_holes.json, docs/POST_V2_WISHLIST.md, tools/conftest.py,
H196's 55 call sites and the full run -- are RESERVED to the goal round. Opus high, one builder per stream.
Usage: python create_bug_null_orders_3b_parallel.py [A|B|C ...]  (default: all three)"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

COMMON_FORBIDDEN = ["project_memory/**", ".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py",
                    ".claude/agents/**", "team-kits/*/VERSION", "team-kits/kernel/known_holes.json", "tools/conftest.py",
                    "docs/POST_V2_WISHLIST.md", "radar/20*.md", "radar/decided.md", "team-kits/*/settings/settings.json"]

STREAMS = {
    "A": {
        "name": "kernel",
        "allowed": ["team-kits/kernel/**", "tools/test_kernel.py", "tools/test_state.py", "tools/test_report.py",
                    "tools/test_approvals_dispatch.py", "tools/test_backlog_types.py", "tools/test_kitupdate.py",
                    "tools/test_migrate.py", "tools/test_board.py", "tools/test_board_browser.py",
                    "tools/test_parallel_scopes.py", "tools/test_parallel_streams.py", "tools/test_schemas.py",
                    "tools/test_staging_cli.py", "tools/test_pointer_sweep.py", "tools/test_gaplog.py",
                    "tools/test_plan_diagram.py", "tools/test_ladder.py", "tools/test_model_ladder.py",
                    "tools/test_light_kit.py", "tools/test_research_chain.py", "tools/test_disposition.py",
                    "tools/test_close_measured_pass.py", "tools/close_measured_pass.py", "tools/lead_package.py",
                    "tools/lead_package_sizes.json", "tools/record_lead_package_sizes.py", "tools/harvest_kit_gaps.py"],
        "forbidden": ["team-kits/dev-team/**", "team-kits/office-team/**", "team-kits/research-team/**",
                      "team-kits/*.sh", "team-kits/*.ps1", "team-kits/*.yaml", "team-kits/*.py", "team-kits/*.txt",
                      "tools/test_hooks.py", "tools/test_hooks_v2.py", "docs/**", ".claude/**"],
        "holes": ("report.py H183 H81 H109 H108 H110 H127 H179; dispatch.py H44 H52 H54 H156 H157 H171 H194 (+ H184/BUG-0266 "
                  "routine dispatch); state.py H48 H58 H106 H134 H154; scopes.py H135 H142 H143 H148; kitupdate.py H71 H56 "
                  "H160; approvals.py H132 H111 H130; documents.py H79 H76; backlog_types.py H155 H170 (+ H197/BUG-0281 "
                  "AUTOMATA done_states, re-filed); migrate.py H86; filing.py H60; references.py H84; board.py H126; "
                  "sdk_approval.py H133; tools/test_parallel_streams.py H141/BUG-0224 (the verifier's G4: the same partial "
                  "fix as H190, the five blind spellings become tested rows); BUG-0271 (the German approval question: PR-0011 "
                  "AC-7 built KIND_LABELS -- measure what remains, close with a test that NAMES BUG-0271); the verifier's G3: "
                  "tools/test_approvals_dispatch.py::test_the_card_of_a_list_bound_approval_counts_what_it_binds cannot see "
                  "`len(listed) + 10` (\"2\" in \"12\") -- assert the exact fragment"),
        "count": "41 holes + BUG-0271 + G3",
    },
    "B": {
        "name": "kits",
        "allowed": ["team-kits/dev-team/**", "team-kits/office-team/**", "team-kits/research-team/**",
                    "team-kits/scaffold_team.sh", "team-kits/scaffold_team.ps1", "team-kits/init_project_memory.sh",
                    "team-kits/init_project_memory.ps1", "team-kits/registry.yaml", "team-kits/repo_kit_owned.txt",
                    "team-kits/preset_config.py", "team-kits/write_kit_state.py", "team-kits/gen_provider_artifacts.py",
                    "team-kits/model_tiers.yaml", "install.sh", "install.ps1",
                    "tools/test_hooks.py", "tools/test_hooks_v2.py", "tools/test_office_duties.py",
                    "tools/test_office_package.py", "tools/test_role_contracts.py", "tools/test_reference_skills.py",
                    "tools/test_shared_skill_contract.py", "tools/test_e2e.py", "tools/test_design_conformance.py",
                    "tools/test_finance_dashboard.py", "tools/test_context_budget.py", "tools/test_user_defaults.py",
                    "tools/test_kit_neutrality.py", "tools/test_model_pins.py", "tools/test_handover_marker.py",
                    "tools/test_routine_feed.py", "tools/test_presets.py", "tools/test_shortening_net.py",
                    "tools/test_parity_sources.py", "tools/parity_sources.py", "tools/constitution_section_pins.json",
                    "tools/pin_constitution_sections.py", "tools/provider_observations.json", "tools/fixtures/**"],
        "forbidden": ["team-kits/kernel/**", "docs/**", ".claude/**", "tools/test_kernel.py", "tools/test_state.py",
                      "tools/test_report.py", "tools/test_approvals_dispatch.py", "tools/test_review_procedure.py",
                      "tools/test_repo_hygiene.py"],
        "holes": ("gate_ledger_valid.py H62 H64 H68 H67 H117 (+ BUG-0030 two literal backspace bytes); gate_write_scope.py H15 H47 "
                  "(+ H201/BUG-0285 Push-Location/Pop-Location vocabulary, H204/BUG-0288 prose removal before the substitution "
                  "reader, H205/BUG-0289 _HEREDOC_RX heredoc handed to a shell, H202/BUG-0286 read-only classification per "
                  "stage while the path travels -- all four re-filed, measure first whether the kits' gate still has them); "
                  "_routine.py H112 H158; _compat.py H57 H66; _kernel.py H61; gate_dispatch.py H51; constitution/AGENTS.md "
                  "H77 H59 H178 H94 (re-pin through tools/pin_constitution_sections.py after reading what drifted); "
                  "skills/project-manager/SKILL.md H168; office guard_fs_tripwire.py H129 H72 H123; office _duties.py H113 "
                  "H124; office templates/repo/scripts H75 H90 H91 H118 H119 H166; office correspondence.yaml H177; dev "
                  "templates/repo/scripts H139 H140 (+ H210/BUG-0294 kit_design_render.py rc 3 and gate_design_sighted, "
                  "re-filed); dev gate_design_sighted.py H82; dev skills H107; scaffold_team.sh H55; scaffold_team.ps1 H88 "
                  "H193; tools/test_hooks_v2.py H70 H180; BUG-0055 (scope manifest without a wireframe field -- FIX, the "
                  "user refused the exception); BUG-0056 (a recorded V1 file outside the state tree is writable -- FIX)"),
        "count": "41 holes + BUG-0030/0055/0056",
    },
    "C": {
        "name": "tools and this repo's own tests",
        "allowed": [".claude/hooks/test_gates.py", "tools/test_review_procedure.py", "tools/test_repo_hygiene.py",
                    "tools/test_radar_trigger.py", "tools/test_design_system_contract.py", "tools/test_migrate_holes.py",
                    "tools/test_surface.json", "tools/test_ci_lint_pinned.py", "tools/gate_suite_margins.py",
                    "tools/gate_suite_rates.py", "tools/migrate_holes.py", "tools/validate.py", "tools/radar_routine.py",
                    "tools/normalise_line_endings.py", "tools/probes/**", "tools/eval/**", "docs/**", "CLAUDE.md",
                    "README.md", "HARNESS_LOG.md", "NOTICES.md", "ruff.toml", ".github/**", ".gitattributes",
                    ".gitignore", "user/**", "radar/README.md"],
        "forbidden": ["team-kits/**", "tools/test_hooks.py", "tools/test_hooks_v2.py", "tools/test_kernel.py",
                      "tools/test_state.py", "tools/test_report.py", "tools/test_approvals_dispatch.py",
                      "tools/test_parallel_streams.py", "tools/test_shortening_net.py", "tools/fixtures/**"],
        "holes": (".claude/hooks/test_gates.py H41 H45 H161 (+ H10/BUG-0102 the mutation run over .claude/hooks as an "
                  "instrument, + H206/BUG-0290 which end states this repo reaches today, + H207/BUG-0291 the "
                  "contract-citation tripwire widened to registration, roles, CLAUDE.md and docs -- both re-filed); "
                  "tools/test_review_procedure.py H73 H159 H191; tools/test_repo_hygiene.py H122 H187 H181; "
                  "tools/test_surface.json H152; tools/test_radar_trigger.py H190 (the two-ended list form); "
                  "tools/gate_suite_margins.py H74; tools/test_design_system_contract.py H85; tools/migrate_holes.py H164; "
                  "BUG-0008 (the untracked PowerShell module cache `Microsoft/` in the repo root -> .gitignore + a hygiene "
                  "test); BUG-0032 (validate.py's orphan heuristic reads staging dirs against active item NAMES). "
                  "AND the lead's two lists, prepared as exact lines: (i) the user's shell patch file "
                  "staging/TSK-0140/h182-harness-patch.md EXTENDED with the newly locked rows -- H14/BUG-0106 "
                  "gate_commit_evidence.py, H153/BUG-0235 gate_test_scope.py (the verifier's G2), H199/BUG-0283 "
                  "gate_spawn_needs_item.py, H203/BUG-0287 _harness.py Deadline, plus _harness.py:1596 'all four gates' "
                  "and the one word at test_gates.py:539 -- each as before/after; (ii) for every `nein` row (18 + "
                  "H198/BUG-0282, H200/BUG-0284, H208/BUG-0292, H209/BUG-0293) ONE `kernel.cli update <BUG> ` JSON line "
                  "that sets `limits` to the plain-German sentence of the candidates table (the exception question prints "
                  "`id (limits)`, so the sentence the user reads IS this field), grouped in batches of <= 10 with the "
                  "`request-approval hole_exception --batch` line under each; (iii) the candidates table header counted "
                  "from its rows (the verifier's G1: 105/79 written, 121/95 measured)"),
        "count": "19 holes + BUG-0008/0032 + the lead's three lists",
    },
}


def inputs(letter, spec):
    others = ", ".join("%s (%s)" % (k, v["name"]) for k, v in STREAMS.items() if k != letter)
    return [
        "THE USER'S WORD (2026-09-12 09:22): every hole whose fix lies in this repository is FIXED, not accepted; "
        "exceptions only for provider/platform/world limits, each with one plain-German sentence. DEC-0100 (a bug closes "
        "only on a passing test that NAMES it -- kernel/naming_tests.py, docstring first paragraph or parametrize id); "
        "the house rule: closed OR user-accepted exception, no third state; DEC-0101 (this cut was measured: "
        "check-scopes over the three orders reports no common tracked file)",
        "YOUR LIST -- stream %s (%s), %s: %s. Read each hole's BUG item (`hole_number`, mechanism, chain, `limits`) and "
        "the code it names; staging/TSK-0140/order-3b-candidates.md carries the class and the file family per row and "
        "is the lead's reading, not the authority -- the item and the code are" % (letter, spec["name"], spec["count"], spec["holes"]),
        "THE OTHER STREAMS run at the same time in the SAME working tree: %s. Your allowed_scope is the whole of what you "
        "write. A fix that needs a line OUTSIDE it (a kernel rule that lands in a constitution, a hook change that needs a "
        "kernel predicate, a test file another stream owns) is NOT written by you: put the exact patch -- file, line, "
        "before/after -- under the heading 'Seam handoffs' in your protocol and repeat it in your final message; the lead "
        "carries it to the owner. A red node in a suite you run that another stream's in-progress edit causes is written "
        "down as 'foreign red' with the node id and left alone" % others,
        "HOST RULES with three builders on one machine (DEC-0094/0095 (6), and the gen-4 power-off events): ONE pytest at "
        "a time per builder, SMALL selections only -- a file or `-k`/node ids that a measured run finishes in under three "
        "minutes; never the whole of tools/test_hooks.py or tools/test_hooks_v2.py in one call; timeouts derived from "
        "measured durations; NO full run (the goal round's); no bump_kit_version.py (the goal round stamps once); no "
        "known_holes.json regeneration; red-first in a copy without .git under C:/Offline Repos/v2-testbed/_round-scratch/"
        "(this task id)/ with the arbiter's line per row; clock read for every time you write; protocol as you go in "
        "project_memory/staging/(this task id)/protocol.md",
        "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/; state writes through the kernel "
        "only: an EVD per closed hole (kind test, run_scope selection, the naming nodes) -- the kernel lock serialises the "
        "three streams, retry on a lock refusal; no transition of BUG items by you; the verification batch lines "
        "(<= 10 ids per line) for the lead at the end; a hole the attempt measures unclosable in this repository is "
        "downgraded with the measured reason and ONE plain-German sentence for `limits` (never 'later')",
    ]


OUTPUTS = [
    "Per hole ONE row: id | class | mechanism | change (file:line) | red-first row (arbiter's line) | naming test node | "
    "suites run (selection, duration) | EVD -- or, for a measured downgrade, id | why unclosable HERE (measured) | bound | "
    "the one plain-German sentence; no third state.",
    "COUNTS at the end, honest: closed / downgraded-with-measurement / handed to the user's patch; 'Seam handoffs' and "
    "'foreign reds' as their own sections, empty sections written as empty.",
    "The batch lines for the lead: `request-approval verification --batch <= 10 ids` per line, every line built against a "
    "store copy first (0 refused); every closed id appears in exactly one line.",
    "RUNS: the reading suites of every changed file as small selections, one at a time, listed with durations; ruff over "
    "your files; NO stamp, NO full run, NO commit, NO push, NO mint; the protocol names the last clock reading.",
]


def create(letter):
    spec = STREAMS[letter]
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0012", "--derives-from", "PR-0012",
        "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-4",
        "--dependency", "TSK-0140", "--rung", "opus", "--effort", "high",
    ]
    for p in spec["allowed"]:
        argv += ["--allowed-scope", p]
    for p in COMMON_FORBIDDEN + spec["forbidden"]:
        argv += ["--forbidden-scope", p]
    for line in inputs(letter, spec):
        argv += ["--required-input", line]
    for line in OUTPUTS:
        argv += ["--expected-output", line]
    env = dict(os.environ, PYTHONPATH="team-kits")
    r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    print(letter, "->", r.stdout.strip()[-300:])
    if r.returncode != 0:
        print(r.stderr.strip()[-1500:])
    return r.returncode


def main():
    letters = sys.argv[1:] or list(STREAMS)
    return max(create(letter) for letter in letters)


if __name__ == "__main__":
    sys.exit(main())
