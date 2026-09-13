# TSK-0150 — the runs behind the evidence

Every line below was typed and its result read; the durations are the wall clock pytest printed.
Host rule: one pytest at a time, selections under three minutes (DEC-0094/0095 (6)).

## Per-item selections (the run each EVD records)

| item | run | result |
|---|---|---|
| BUG-0296 (DEC-0112) | `python -B -m pytest "tools/test_ladder.py::test_a_described_test_buys_nothing_since_the_prose_reader_is_retired" "tools/test_ladder.py::test_the_acceptance_reader_grants_only_a_named_address" "tools/test_ladder.py::test_the_shaped_form_is_an_address_at_three_levels" "tools/test_ladder.py::test_an_ask_below_the_default_is_granted_only_for_a_test_shaped_acceptance" -q` | 4 passed in 10.29s |
| BUG-0151 (DEC-0113) | `python -B -m pytest "tools/test_approvals_dispatch.py::test_a_goal_with_no_verification_run_is_asked_about_once" "tools/test_approvals_dispatch.py::test_a_spoken_manifest_field_reaches_the_sentence_and_no_entry_is_dead" -q` | 2 passed in 4.63s |
| BUG-0197 | `python -B -m pytest "tools/test_office_duties.py::test_a_duty_key_moves_with_each_of_its_three_parts_and_with_nothing_else" "tools/test_office_duties.py::test_a_duty_recorded_done_drops_out_of_the_register_and_only_that_one" "tools/test_office_duties.py::test_every_shipped_feed_gives_its_duties_a_key_that_survives_a_day" -q` | 3 passed in 1.04s |
| BUG-0303 | `python -B -m pytest "tools/test_approvals_dispatch.py::test_an_origin_that_names_no_criterion_excuses_no_architect_step" "tools/test_approvals_dispatch.py::test_only_an_origin_that_carries_criteria_excuses_the_architect_step" -q` | 2 passed in 3.89s |
| BUG-0304 | `python -B -m pytest "tools/test_hooks.py::test_the_write_and_run_rule_reads_the_effective_command_word_in_every_kit" "tools/test_hooks.py::test_every_evaluator_word_refuses_a_line_that_writes_what_it_evaluates" "tools/test_hooks.py::test_a_line_that_writes_a_script_and_runs_it_is_refused_in_every_kit" -q` | 7 passed in 32.57s |

## The reading suites (the suites of the files that were touched)

| selection | result | why this one |
|---|---|---|
| `python -B -m pytest tools/test_ladder.py -q` | 61 passed in 43.68s | the suite of `kernel/dispatch.py`'s ladder half and of the retired prose rows |
| `python -B -m pytest tools/test_approvals_dispatch.py -q` | 235 passed in 122.25s | the suite of `kernel/approvals.py` + `kernel/dispatch.py`; it is also the neighbour the `create_pending_request` contract change reaches through `conftest.walk_to_status` |
| `python -B -m pytest tools/test_office_duties.py tools/test_routine_feed.py -q` | 70 passed in 9.00s | the two suites that read `_duties.py` and the mirrored `_routine.py` |
| `python -B -m pytest tools/test_hooks.py -q -k "effective_command_word or evaluator_word_refuses or writes_a_script_and_runs_it or command_substitution_is_not_read"` | 10 passed in 21.56s | the write-and-run rule and the over-refusal node that bounds it |
| `python -B -m pytest tools/test_hooks.py -q -k "mirror or identical"` | 3 passed in 8.03s | the mirror rule, after `_routine.py` and `gate_write_scope.py` were copied to three kits |

## Red-first (the rig, `_round-scratch/TSK-0150/rig.py`)

The rig refuses to run outside its own directory and writes every restored file in BINARY, for the
two reasons `staging/TSK-0120/merge-protocol.md` section 0 records. A file the base commit does not
have is "restored" by being removed.

| run | restored to 92d746a | result |
|---|---|---|
| `rf-112` | `team-kits/kernel/dispatch.py` | 3 failed — the first is `AssertionError: ein Test wird rot, ohne den Fix / assert True is False` |
| `rf-113` | `kernel/approvals.py`, `kernel/backlog_types.py`, `kernel/report.py`, `kernel/cli.py`, `tools/conftest.py` | 2 failed — `Failed: DID NOT RAISE ApprovalError` (the question was never asked) |
| `rf-197` | `office-team/hooks/_duties.py`, `office-team/hooks/_routine.py`, `kernel/cli.py`, and `kernel/duties.py` REMOVED | 3 failed — `KeyError: 'key'` and `ModuleNotFoundError` |
| `rf-303` | `team-kits/kernel/dispatch.py` | 1 failed — `assert architect_step_owed(...)` is False, i.e. the hollow origin still excused the step |
| `rf-304` | `gate_write_scope.py` in all three kits | 4 failed — `("printf 'x' > run.sh ; A=1 ./run.sh", '', '')`, i.e. rc 0 with empty stderr |

## The one full run and the gate run

| run | clock | result |
|---|---|---|
| `DELIVERY_RUN=TSK-0150 python -B -m pytest tools/ -q` (attempt 1) | 10:10:50 .. 10:16:44 | rc 1, NO summary line, output truncated at ~338 tests. Not a test failure: the three modules that cover that span (test_approvals_dispatch, test_backlog_types, test_board) were re-run together and came back 370 passed in 198 s. Recorded because it happened, not because it means anything. |
| `DELIVERY_RUN=TSK-0150 python -B -m pytest tools/ -q` (attempt 2, THE delivery run) | 10:28:32 .. 12:42:39 | **4 failed, 5144 passed, 14 skipped in 8058.00s (2:14:18)** -- EVD-0456 |
| `DELIVERY_RUN=TSK-0150 python -B -m pytest .claude/hooks/test_gates.py -q` (its own run) | 12:53:20 .. 13:37:45 | **3 failed, 552 passed in 2662.79s (44:22)** |

### The reds of the delivery run, one line each

| node | what happened |
|---|---|
| `tools/test_hooks.py::test_every_span_that_presents_the_command_surface_names_all_of_it` | FIXED at the mechanism: a NEW subcommand has to stand in every span that presents the surface; `duty-done` added to the three constitutions and README. Re-run green. |
| `tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves` | FIXED: eight sites, five of them this round's own `::test_y` EXAMPLES, which that reader reads as citations of a test nobody wrote; every example is now spelled out in words, and `docs/holes/H155.md` re-points at the test that replaced the one BUG-0303 renamed. Re-run green. |
| `tools/test_shortening_net.py::test_no_section_of_a_pinned_instruction_file_disappears_unnoticed` | FIXED: the edited sections re-pinned with `tools/pin_constitution_sections.py --write --note ...` (7 sections). Re-run green. |
| `tools/test_hooks.py::test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires` | OPEN, and it is BUG-0297 / H213: the text lives in `.claude/hooks/gate_commit_evidence.py`, which is this order's forbidden scope. `.claude/hooks/` is byte-identical to 92d746a (`git status --porcelain .claude/hooks/` empty), so this red is not this round's. |

### The reds of the gate run

| node | what happened |
|---|---|
| `test_the_hole_index_in_the_document_is_the_one_the_items_generate` | FIXED: the hole table is GENERATED from the items and this round had edited five rows by hand. `python tools/migrate_holes.py --root project_memory --reindex` rewrote the section from the store (209 holes); what those rows were meant to say now lives in `docs/holes/H59.md`, `H113.md`, `H212.md`, `H218.md`, `H219.md`, which is where a generated index cannot lose it. Re-run green. |
| `test_gate3_prints_a_remedy_that_runs_as_printed` | OPEN -- BUG-0297 / H213, the same patch, and the test says so itself. |
| `test_every_test_a_hole_names_is_one_that_exists` | OPEN, TWO causes: H138 names a test of `test_design_conformance` that does not exist (pre-existing, named in the order as expected), and H155 names `test_an_empty_origin_excuses_the_step_while_the_root_criteria_measure_it`, the test BUG-0303 replaced. The pointer sits in `project_memory/archive/BUG/2026/BUG-0237.yaml:41` (`regression_tests`) -- canonical state, outside this order's scope. HANDBACK. |

### Two kernel commands driven end to end (not pytest)

* `duty-done --key ... --what ... --note ...` against a COPY of the store: `recorded`, and the
  second call with the same key `already recorded` with the FIRST note -- the idempotence the
  shape asks for.
* `request-approval verification --batch BUG-0151 BUG-0197 BUG-0296 BUG-0303 BUG-0304` against a
  copy of the store inside a copy of the checkout: rc 0, 5 of 5 listed, 0 refused.


## Rework 1 (after verify-round-1.md) -- runs and mutations

| selection | result |
|---|---|
| `python -B -m pytest tools/test_approvals_dispatch.py -q` | 236 passed in 100.49s |
| `python -B -m pytest tools/test_state.py -q` | 67 passed in 8.36s |
| `python -B -m pytest tools/test_kernel.py -q` | 136 passed in 24.68s |
| `python -B -m pytest tools/test_office_duties.py tools/test_routine_feed.py -q` | 74 passed in 7.73s |
| `python -B -m pytest tools/test_hooks.py -q -k "prefix_words_own_option or effective_command_word or evaluator_word_refuses or writes_a_script_and_runs_it or command_substitution_is_not_read or mirror or identical"` | 16 passed in 21.92s |
| `python -B -m pytest .claude/hooks/test_gates.py --collect-only -q` | 555 tests collected in 0.68s |
| `python -B -m pytest .claude/hooks/test_gates.py -q -k "kits_prefix or stage_verb or write_and_run or prefix"` | 4 passed in 23.35s |

### Mutations (`_round-scratch/TSK-0150/mutate.py`, a copy of the tree with ONE mechanism off)

| key | what it switches off | result |
|---|---|---|
| `f1-capture-and-update-guard` | both refusals of DEC-0113's pair | 1 failed -- `Failed: DID NOT RAISE Exception` |
| `f2-unknown-command-word` | the fail-closed reading of a prefix word's option | 3 failed (one per kit) -- `returncode=0, stdout='', stderr=''` on `printf 'x' > run.sh ; exec -a foo bash run.sh` |
| `f3-row-unique-period` | the row-unique period of the receivable feed | 1 failed -- the collision guard reports the verifier's own digest `9fdce45d180fd1c2` |
| `f3-collision-guard` | the guard's effect (`shared = []`) | 1 failed -- two colliding duties keep their key |
| `f4-german-sentence` | the partial branch of the question (`whole = True`) | 1 failed -- the partial case reads as total |

### The gate battery as processes (`probe_f2.py`, all three kits, 27 lines each)

13 attack lines rc 2 (the five of F2, the five of H219, the three older shapes including
`sudo -u root tee run.sh ; bash run.sh`, which is the row the per-source attribution saves) and
14 everyday lines rc 0 (`nice -n 5 make`, `sudo -u me ls`, `env -i bash tools/ci.sh`,
`A=1 ./build.sh`, `exec bash tools/ci.sh`, `bash < tools/ci.sh`, `bash tools/ci.sh`,
`git status --short`, `cp a.txt b.txt ; cat b.txt`, `echo y | tee log.txt ; grep x log.txt`,
`bash $(which ci.sh)` and its quoted twin, `eval "$(cat tools/ci.sh)"`, and the Evidence line).
MISMATCHES 0.
