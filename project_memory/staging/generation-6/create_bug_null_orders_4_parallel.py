"""PR-0012 'Bug-Null', order 4 cut into THREE parallel streams by the same measured file families as 3b (DEC-0101; the
3b partition was check-scopes-disjoint and held for five hours). TSK-0145 (single builder) was cancelled in favour of
this cut. Content = the user's decisions DEC-0103/0105/0107/0108 + the in-repo remainder (create_bug_null_order_4.py
docstring). Reserved to the goal round: stamp, full run, known_holes.json, POST_V2_WISHLIST, conftest.py.
Usage: python create_bug_null_orders_4_parallel.py <base-commit> [A|B|C ...]"""
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "create-task"]

COMMON_FORBIDDEN = ["project_memory/**", ".claude/settings.json", ".claude/hooks/gate_*.py", ".claude/hooks/_harness.py",
                    ".claude/agents/**", "team-kits/*/VERSION", "team-kits/kernel/known_holes.json", "tools/conftest.py",
                    "docs/POST_V2_WISHLIST.md", "radar/20*.md", "radar/decided.md"]

A_TESTS = ["tools/test_kernel.py", "tools/test_state.py", "tools/test_report.py", "tools/test_approvals_dispatch.py",
           "tools/test_backlog_types.py", "tools/test_kitupdate.py", "tools/test_migrate.py", "tools/test_board.py",
           "tools/test_board_browser.py", "tools/test_parallel_scopes.py", "tools/test_parallel_streams.py",
           "tools/test_schemas.py", "tools/test_staging_cli.py", "tools/test_pointer_sweep.py", "tools/test_gaplog.py",
           "tools/test_plan_diagram.py", "tools/test_ladder.py", "tools/test_model_ladder.py", "tools/test_light_kit.py",
           "tools/test_research_chain.py", "tools/test_disposition.py", "tools/test_close_measured_pass.py"]
B_TESTS = ["tools/test_hooks.py", "tools/test_hooks_v2.py", "tools/test_office_duties.py", "tools/test_office_package.py",
           "tools/test_role_contracts.py", "tools/test_reference_skills.py", "tools/test_shared_skill_contract.py",
           "tools/test_e2e.py", "tools/test_design_conformance.py", "tools/test_finance_dashboard.py",
           "tools/test_context_budget.py", "tools/test_user_defaults.py", "tools/test_kit_neutrality.py",
           "tools/test_model_pins.py", "tools/test_handover_marker.py", "tools/test_routine_feed.py", "tools/test_presets.py",
           "tools/test_shortening_net.py", "tools/test_parity_sources.py", "tools/parity_sources.py",
           "tools/constitution_section_pins.json", "tools/pin_constitution_sections.py", "tools/provider_observations.json",
           "tools/fixtures/**"]

STREAMS = {
    "A": {
        "name": "kernel",
        "allowed": ["team-kits/kernel/**", "project_memory/project_config.yaml", ".claude/agents/harness-implementer.md",
                    ".claude/agents/harness-verifier.md"] + A_TESTS
                   + ["tools/close_measured_pass.py", "tools/lead_package.py", "tools/lead_package_sizes.json",
                      "tools/record_lead_package_sizes.py", "tools/harvest_kit_gaps.py"],
        "forbidden": ["team-kits/dev-team/**", "team-kits/office-team/**", "team-kits/research-team/**", "team-kits/*.sh",
                      "team-kits/*.ps1", "team-kits/*.yaml", "team-kits/*.py", "team-kits/*.txt", "tools/test_hooks.py",
                      "tools/test_hooks_v2.py", "docs/**", ".claude/hooks/**"],
        "rows": ("DEC-0103 (goal-size vocabulary in kernel/backlog_types.py with the two-ended tripwire, refusal at capture/update "
                 "with the four words and what each does, migration of the 12 stored goals through kernel/migrate.py -- store copy "
                 "first, then the store, before/after list; the SR/architecture predicates read the set); DEC-0105 (tier file: "
                 "project_config.yaml `model_tiers:` read ONLY without a scaffold record, validated against the kits' "
                 "model_tiers.yaml shape, missing file = 'keine Angabe'; this repo's config names one and the two harness role "
                 "files stop carrying tiers by hand -- .claude/agents/harness-*.md are allowed for exactly that); DEC-0107 kernel "
                 "half (`evidence --kind test --result fail --fail-class mechanical|reasoning`, stamped with the writer's role "
                 "from the lease; `count_failed_run_locked` skips `mechanical`; the gate_dispatch refusal is stream B's -- hand the "
                 "predicate name over as a seam row); BUG-0302 (`withdraw-request <id>` / `sweep-requests --stale <hours>`, "
                 "audit-logged; a request whose items are all archived is reported dead; the hook note in the kits stops counting "
                 "withdrawn ones -- the hook text is B's, the kernel reader yours); BUG-0197/H113 (the deadline register's 'done' "
                 "record -- say its shape in the protocol first); BUG-0151/H59 (write the plain-German question with prices, do "
                 "not build); BUG-0242/H160 (re-measure tools/test_kitupdate.py -k memory_tree_no_installed_role on the stamped "
                 "tree; close or downgrade)"),
        "count": "4 decisions' kernel halves + 3 remainder rows",
    },
    "B": {
        "name": "kits",
        "allowed": ["team-kits/dev-team/**", "team-kits/office-team/**", "team-kits/research-team/**", "team-kits/scaffold_team.sh",
                    "team-kits/scaffold_team.ps1", "team-kits/init_project_memory.sh", "team-kits/init_project_memory.ps1",
                    "team-kits/registry.yaml", "team-kits/repo_kit_owned.txt", "team-kits/preset_config.py",
                    "team-kits/write_kit_state.py", "team-kits/gen_provider_artifacts.py", "team-kits/model_tiers.yaml",
                    "install.sh", "install.ps1"] + B_TESTS,
        "forbidden": ["team-kits/kernel/**", "docs/**", ".claude/**", "tools/test_kernel.py", "tools/test_state.py",
                      "tools/test_report.py", "tools/test_approvals_dispatch.py", "tools/test_review_procedure.py",
                      "tools/test_repo_hygiene.py"],
        "rows": ("BUG-0153/H61 (FIRST a `timeout` on every entry of team-kits/*/settings/settings.json -- measured 2 of 89 carry "
                 "one; this file is ALLOWED here for exactly that -- THEN the fail-closed Deadline reader in _compat, mirrored; "
                 "never the reader alone); DEC-0108 (a mixed-VAT document = one ledger row per rate under a shared invoice number "
                 "in the office kit's invoice_intake.py / ledger_add.py; EUeR sums per rate, document count by distinct invoice "
                 "numbers; BR-CO-14 stays; red-first with a real mixed document); DEC-0107 hook half (gate_dispatch refuses a "
                 "`fail_class` written by any role but the verifying one, as a PROCESS test against a pilot; the QA role texts of "
                 "the three kits say the command; the kernel predicate name arrives from stream A as a seam row -- until then "
                 "build against the field name `fail_class`); BUG-0298/H214 (the one-line `cat <<'EOF' > run.sh ; bash run.sh` "
                 "form refused at gate_write_scope while `cat <<'EOF' > notes.md` alone stays rc 0; multi-line form named as "
                 "the H11 remainder); the hook-side note of BUG-0302 (the approval hook stops counting withdrawn requests -- the "
                 "kernel reader is A's); DEC-0104 sentence in the office lead skill (a larger office job is split into tasks, "
                 "not raised in effort); DEC-0109 sentence kept (what the four-eyes wall does not bind)"),
        "count": "2 decisions' kit halves + H61 + BUG-0298 + two sentences",
    },
    "C": {
        "name": "tools and this repo's own tests",
        "allowed": [".claude/hooks/test_gates.py", "tools/test_review_procedure.py", "tools/test_repo_hygiene.py",
                    "tools/test_radar_trigger.py", "tools/test_design_system_contract.py", "tools/test_migrate_holes.py",
                    "tools/test_surface.json", "tools/test_ci_lint_pinned.py", "tools/gate_suite_margins.py",
                    "tools/gate_suite_rates.py", "tools/migrate_holes.py", "tools/validate.py", "tools/radar_routine.py",
                    "tools/normalise_line_endings.py", "tools/probes/**", "tools/eval/**", "docs/**", "CLAUDE.md", "README.md",
                    "HARNESS_LOG.md", "NOTICES.md", "ruff.toml", ".github/**", ".gitattributes", ".gitignore", "user/**",
                    "radar/README.md"],
        "forbidden": ["team-kits/**", "tools/test_hooks.py", "tools/test_hooks_v2.py", "tools/test_kernel.py",
                      "tools/test_state.py", "tools/test_report.py", "tools/test_approvals_dispatch.py",
                      "tools/test_parallel_streams.py", "tools/test_shortening_net.py", "tools/fixtures/**"],
        "rows": ("BUG-0295/H211 (a triple quote is ONE delimiter in `_dec_citations`' pairing; the DEC-2100/DEC-0000 exhibits stay "
                 "unreported, the two real sites dispatch.py:204 and invoice_intake.py:370 are judged -- READ those files, do not "
                 "edit them); BUG-0297/H213 (build the test that EXECUTES the printed gate-3 remedy parsed from the refusal; it "
                 "stays red until the user's S4 patch -- say so in its docstring and in the protocol; no EVD claiming a close); "
                 "BUG-0299/H215 (the bound-name hop applied to the program word in `_starts_a_hook`; the four live sites stay 0); "
                 "BUG-0300/H216 is in tools/test_hooks.py -> NOT yours, hand the row to B as a seam with the mutation that must "
                 "go red; BUG-0301/H217 likewise tools/test_hooks.py -> seam to B (excuse at most as many missing names as "
                 "computed tokens in the span); BUG-0296/H212 (DEC-first per DEC-0102 (3): write the class question -- does the "
                 "acceptance-line reader keep judging natural-language negation, or ask for the shaped form -- with the measured "
                 "history (four rounds, four holes) and the price of each answer; do not add a word); docs/holes/*.md rows for "
                 "every hole this order closes or bounds"),
        "count": "3 closures + 2 seams + 1 DEC question + docs",
    },
}


def inputs(letter, spec, base):
    others = ", ".join("%s (%s)" % (k, v["name"]) for k, v in STREAMS.items() if k != letter)
    return [
        "THE USER'S DECISIONS of 2026-09-12 as recorded (DEC-0103, DEC-0104, DEC-0105, DEC-0106, DEC-0107, DEC-0108, DEC-0109, "
        "DEC-0110) and his word: every hole whose fix lies in this repository is FIXED; exceptions only with a German sentence. "
        "DEC-0100 (a bug closes only on a test that NAMES it), DEC-0102 (2) (name the MECHANISM, measure every spelling you can "
        "enumerate before the EVD; a closure the verifier widens twice is re-filed, not reworked a third time), DEC-0102 (4) "
        "(a kernel command whose REQUIRED arguments change: grep every caller in the tree FIRST -- kits, tools, .claude/hooks, "
        "README -- list them, seam rows to the owners at once), DEC-0102 (5) (the half report is a protocol section with a "
        "clock reading, never a message). Base commit %s (stamp 2026.09.12-6)" % base,
        "YOUR ROWS -- stream %s (%s), %s: %s. Read each DEC and each item; the DEC is the order, the item carries the "
        "measurement" % (letter, spec["name"], spec["count"], spec["rows"]),
        "THE OTHER STREAMS run at the same time in the SAME working tree: %s. Your allowed_scope is the whole of what you write. "
        "A line outside it goes under 'Seam handoffs' in your protocol AND in your final message as an exact patch; the lead "
        "carries it. A red a neighbour's in-progress edit causes is 'foreign red' with the node id, left alone" % others,
        "HOST RULES with three builders on one machine (DEC-0094/0095 (6)): ONE pytest at a time per builder, SMALL selections "
        "(< 3 min measured; tools/test_hooks*.py only by -k or node ids); no stamp, no full run, no known_holes.json regeneration "
        "(the goal round's); red-first in a .git-less copy under C:/Offline Repos/v2-testbed/_round-scratch/(this task id)/ with "
        "the arbiter's line; clock read for every time you write; protocol as you go in project_memory/staging/(this task id)/"
        "protocol.md; mirrored hook files byte-identical; constitution changes re-pinned after writing what drifted; the research "
        "constitution's ceiling is tools/lead_package_sizes.json",
        "forbidden_scope project_memory/** EXCEPTS project_memory/staging/(this task id)/ (and, for stream A only, "
        "project_memory/project_config.yaml for DEC-0105's one line); state writes through the kernel only: an EVD per closed "
        "item with the naming node in the run command (retry on lock refusals); no transition of BUG items; the verification "
        "batch lines (<= 10 ids) for the lead; no commit, no push, no mint",
    ]


OUTPUTS = [
    "Per row ONE line: id | change (file:line) | red-first row (arbiter's line) | naming node | suites (selection, duration) | "
    "EVD -- or the measured reason, the German sentence, or the question for the user.",
    "COUNTS, honest: closed / downgraded with sentence / questions / seams handed over / not reached; 'Seam handoffs' and "
    "'foreign reds' as their own sections, empty ones written as empty.",
    "The batch lines for the lead (<= 10 ids per line), dry-checked against a store copy inside a checkout, 0 refused.",
    "RUNS: the reading suites of every changed file as small selections with durations; ruff over your files; NO stamp, NO "
    "full run, NO commit, NO push, NO mint; the protocol names the last clock reading.",
]


def create(letter, base):
    spec = STREAMS[letter]
    argv = list(KERNEL) + [
        "--product-requirement", "PR-0012", "--derives-from", "PR-0012",
        "--type", "implementation", "--assigned-role", "harness-implementer", "--acceptance-ref", "AC-4",
        "--dependency", "TSK-0144", "--rung", "opus", "--effort", "high",
    ]
    for p in spec["allowed"]:
        argv += ["--allowed-scope", p]
    for p in COMMON_FORBIDDEN + spec["forbidden"]:
        argv += ["--forbidden-scope", p]
    for line in inputs(letter, spec, base):
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
    if len(sys.argv) < 2:
        sys.exit("usage: create_bug_null_orders_4_parallel.py <base-commit> [A|B|C ...]")
    letters = sys.argv[2:] or list(STREAMS)
    return max(create(letter, sys.argv[1]) for letter in letters)


if __name__ == "__main__":
    sys.exit(main())
