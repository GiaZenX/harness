# TSK-0154 -- stream B (order flow), order 7 -- protocol (written as I go)

Worktree: C:/Offline Repos/v2-testbed/_worktrees/g7-dispatch (branch g7/dispatch, base 35e929b)
Scratch:  C:/Offline Repos/v2-testbed/_round-scratch/TSK-0154/

## Clock

- 2026-09-26T21:39:32 start; item read verbatim (allowed/forbidden/seam/required_inputs/expected_outputs)
- 21:4x read BUG-0313/0314/0315/0318/0321/0322/0324, FR-0092, DEC-0118/0121/0116/0087/0088, harvest entries

## Measurements of the provider (payload rig)

- 21:47-21:49 rig `_round-scratch/TSK-0154/payload-rig` (claude 2.1.258, headless, haiku; an
  observer hook on PreToolUse/PostToolUse/SubagentStart/SubagentStop/Stop/Notification, logging
  binary to log-run1.jsonl). A child (`bg-child`) starts `sleep 40` with `run_in_background: true`
  and ends its turn. MEASURED:
  * PreToolUse(Agent) `tool_input` carries `description` (the string the lead typed) -> FR-0092's
    compare is on the payload, not assumed.
  * the child's PreToolUse(Bash) carries `agent_id`, `agent_type` and `tool_input.run_in_background`.
  * SubagentStop fires when the child ends its turn to wait (t=13.3 s, last message
    WAITING_ON_BACKGROUND) -- the stop BUG-0313 misread.
  * when the background command completes, SubagentStart fires AGAIN for the SAME agent_id
    (t=51.7 s), the child runs on and stops again (t=59.3 s). A SendMessage resume does the same.
  * SubagentStop AND Stop payloads carry a key `background_tasks` (value logged in run 2).

* run 2 (21:50): `background_tasks` on the CHILD's SubagentStop =
    `[{type: subagent, status: running, ...}, {id, type: shell, status: running, description,
    command: "sleep 40 && echo PROBE_FINISHED"}]`; on the lead's Stop after it the shell entry
    alone. The list is SESSION-wide (the subagent itself is in it) and a shell entry names no
    owner -- so attribution is by the command the child itself started (its PreToolUse).

## Plan (and the way rejected, FR-0084)

- BUG-0313: the child's own background starts are recorded on its LEASE at PreToolUse(Bash|
  PowerShell, run_in_background) of the bound agent; at SubagentStop a child counts as WAITING
  (no CHILD_ENDED) while the stop payload's `background_tasks` lists a RUNNING shell whose command
  it started; SubagentStart of an already-bound agent (the measured resume) clears a recorded end.
  REJECTED: (a) a counter of starts minus stops -- a server a child leaves running, or a start a
  sibling gate refused, reads as waiting forever, and nothing can correct it; the provider's
  live list can. (b) refusing background runs to children -- breaks the dev-server-plus-e2e
  pattern, and the AC asks that a child that DOES start one is not read as stopped.
- BUG-0314: promotion LEASED -> IN_PROGRESS at the BIND (SubagentStart, measured 0.4 s after the
  spawn), so a foreground self-path child can book and a swept lease leaves IN_PROGRESS (bookable);
  the expiry refusal says what really happened; `dispatch` re-leases an IN_PROGRESS task with no
  lease file whose child's end is RECORDED (keeps IN_PROGRESS and the staged work). REJECTED:
  booking from LEASED plus a promoting sweep -- the same rule ("a bound child means the run
  started") spelled in three places instead of one.

CLOCK CORRECTION 22:16:05: the entries below marked [21:58-22:16] carried guessed minute
labels (22:1x..23:0x) that were never read off a clock; the one real reading is 22:16:05, when
all of them were done.

## Red-first (rig `_round-scratch/TSK-0154/redfirst.py`, base copy = git archive 35e929b, kit 2026.09.26-5, no .git)

- 21:58 tools/test_stream_b_order_flow.py on base: 5 failed, 1 passed.
  RED: test_a_child_waiting_on_its_own_background_run_is_not_reported_stopped_bug_0313
  (`assert not '2026-09-26T21:57:32'` = CHILD_ENDED written on the waiting stop);
  test_a_foreground_self_path_child_books_its_own_result_bug_0314 (`'LEASED' == 'IN_PROGRESS'`);
  test_a_swept_lease_leaves_the_started_run_bookable_bug_0314 (`'READY' == 'IN_PROGRESS'`);
  test_an_expired_lease_of_a_started_run_is_leased_again_where_it_stands_bug_0314 (message);
  test_a_started_run_whose_child_has_no_recorded_end_is_not_leased_again_bug_0314 ("LEASED, not READY").
  GREEN on base by design: test_a_running_shell_the_child_did_not_start_does_not_make_its_stop_a_wait_bug_0313
  (counter-direction; its red is a mutation of the fix, below).
- worktree: 6 passed (15.6 s).
- [21:58-22:16] BUG-0324 (kernel `run_can_be_classified` = FAILED or any status the TSK automaton leads
  into FAILED; `drop_an_overruled_classification` on a chain-forward transition, called from
  `state._transition_locked`). Base: test_the_verifier_classifies_the_run_it_judges_and_the_climb_skips_it_bug_0324
  RED (kernel rc 2 "is SUBMITTED ... ended in FAILED"); worktree 2 passed.
- Mutation rig `_round-scratch/TSK-0154/mutate.py` (fresh binary copy of the worktree, one exact
  byte replacement): M1 `drop_an_overruled_classification` -> no-op: 
  test_a_classification_the_verdict_overruled_discounts_nothing_bug_0324 RED (`'fail_class' not in`);
  M2 `runs_still_going` counts every running shell: 
  test_a_running_shell_the_child_did_not_start_does_not_make_its_stop_a_wait_bug_0313 RED (`assert None`).
- [21:58-22:16] BUG-0322 (`starts_on_the_top` = DEC-0118 (1)'s "architecture step" read off the kit
  declaration; `architect_step_examined` counts an ACCEPTED SR for every goal it reaches on ANY path
  (`report._hangs_from`) and names every non-counting SR under the goal in the refusal). Base: both
  bug_0322 tests RED (architect order refused rc 1; no SR named). Worktree: 2 passed. M3 (put the
  one-root reading `origin_root_conflict` back into the count): the second-parent test RED at the
  final lease (rc 1). REJECTED: TSK `type: architecture` as the exemption -- a field the PM writes
  on the order, so any order could claim the exemption by its type; the class comes from the kit.
- [21:58-22:16] BUG-0315 (`report._invoked_script_words_and_launchers`: a launcher's argument is looked
  for beside the launcher, by base name -- the shipped `_gate.py` rule, RUN in the test). Base:
  test_the_launcher_form_of_the_approval_hook_counts_as_wired_bug_0315 RED (`False is True`, shipped
  dev-team settings.json + hooks). Worktree 1 passed.
- [21:58-22:16] BUG-0321: the reader IS in my files -- `report.contradicted_confirmations`; it now asks
  each confirmed item on the question its confirmation was judged on (`CONFIRMING_EVIDENCE` types:
  CONFIRMATION_QUESTION; others: DELIVERY). Base: test_a_later_passing_selection_supersedes_an_older_failing_one_bug_0321
  RED (`{'BUG-0001': ['EVD-0001']} == {}`). Worktree 1 passed. Finding text "current delivery
  verdict(s)" -> "current verdict(s)" (no test pinned the word, grep).
- [21:58-22:16] DEC-0118 in `ladder_for_order`: a class whose declared start is `top`, where the provider
  cap lowered that top, starts at the kit's ceiling effort (one predicate `_declared_start_is_top`
  shared with the BUG-0322 exemption). `kernel.cli ladder --provider` table (scratch
  dec0118_table.py, store outside the repo), every kit, top-starting roles, FAIL 0, normal goal:
    worktree: dev software-architect claude opus/xhigh, codex fable(gpt-6-astra)/high;
              office office-manager claude opus/medium, codex opus(gpt-6-sol)/medium;
              research methodologist claude opus/xhigh, codex fable(gpt-6-astra)/high
    base    : dev + research claude opus/HIGH (everything else identical)
  Base: test_the_architecture_step_starts_at_xhigh_on_claude_and_at_the_default_on_codex_dec_0118
  RED (`('opus', 'high') == ('opus', 'xhigh')`). REJECTED: a new `start_effort:` key in the three
  ladder.yaml files -- a second switch beside `provider_top`, where DEC-0118 (3) wants ONE line.
- [21:58-22:16] BUG-0318: `dispatch.order_cut_facts` (create-task AND capture TSK print `[cut]` lines on
  stderr, rc unchanged); `report.order_cut` in the brief's `lease_distribution` (orders_per_goal,
  verifier_share, parallel_candidates via `scopes.covering_record` on each goal's lowest open build
  order, cut_line). Base: both bug_0318 tests RED (`'[cut]' in ''`; KeyError 'orders_per_goal').
  REJECTED: a refusal at create-task (the bug asks for facts; DEC-0087 leaves the cut to the PM);
  a new top-level brief key (the schema is strict at the top and lives outside my scope).
- [21:58-22:16] FR-0092: `create_lease` composes `spawn_name` ('<Role Name> · <Rung> <effort>' + ' · <letter>'
  when another live lease of the role stands under the goal; every lease holds a letter, the first
  free one), the header carries it, `dispatch` prints `spawn with description: ...` on stderr, the
  checkpoint's (c) line names it, and `validate_dispatch(spawn_description=...)` refuses a
  description that differs (before the claim). A payload with NO description is not refused: the
  provider always sends one (measured), so None is a library caller -- named in
  `dispatch.spawn_name_refusal`. Base: test_the_spawn_carries_the_name_the_lease_composed_fr_0092
  RED (no description line). M4 (refusal -> None): RED (`0 == 2`); M6 (letter = count of taken):
  RED (fourth lease not `· A`). Streams are UTF-8 (`_compat`/`cli` reconfigure), the test reads them
  so. REJECTED: an ASCII-only separator -- the lead's own example uses the middle dot and both
  writers already emit UTF-8.
  REJECTED for BUG-0324: classification "with the FAILED transition itself" -- that transition is the
  lead's, and DEC-0107 gives the PM no writer; the verifier's bound run is the only attributable one.

## Shared-file hunks

(file, section, why)

- team-kits/kernel/cli.py: (1) `capture` branch, TSK case -- `_say_the_cut` after the similar-items
  lines (BUG-0318); (2) `create-task` branch -- `_say_the_cut` after the id line (BUG-0318);
  (3) `dispatch` branch -- stderr line `spawn with description: ...` (FR-0092); (4) NEW function
  `_say_the_cut` beside `_submitted_envelope`. No parser change, no new command.
- team-kits/*/skills PM skill (dev project-manager, office office-manager, research project-manager):
  (1) the FR-0093 cost-line bullet "A run longer than a few minutes..." -- corrected for BUG-0313
  (identical text x3); (2) the DELEGATE/ROUTE step -- the Agent call's `description` (FR-0092);
  (3) dev + research only, the tier/slicing paragraph of step 7 -- the architecture/method-design
  step starts at xhigh on a capped top (DEC-0118).
- team-kits/{dev,research}-team/constitution/AGENTS.md: the ladder paragraph's EFFORT clause
  (DEC-0118). Office untouched (its top is opus by declaration; nothing changes there).
- README.md: the "ladder is the kernel's" bullet (DEC-0118 effort clause, FR-0092 description
  refusal). Command list untouched.
- docs/HARNESS_V2_SPEC.md: the dispatch-lifecycle sentence (IN_PROGRESS at the bind, BUG-0314).
- hooks/_compat.py, hooks/_kernel.py: NOT touched.

## Reading suites

(selection, why, result, clock -- each its own run, one at a time, logs under _round-scratch/TSK-0154/suite-*.log)

- 22:17:56 tools/test_board.py -- reads the kernel writer register (every new writer regenerates:
  `record_background_start`, `_start_the_run_locked`): 77 passed.
- 22:18:26 tools/test_state.py -- `_transition_locked` (fail-class drop), status writers: 67 passed.
- 22:19:30 tools/test_report.py -- contradiction reader, mint wiring, brief: 141 passed.
- 22:22:34 tools/test_ladder.py -- 66 passed, 1 FAILED: test_a_record_that_is_present_but_unreadable_is_refused_not_ignored.
  MY DEFECT: the BUG-0322 exemption asked `ladder_declaration`, which REFUSES on an unreadable
  scaffold record, so `architect_step_owed` raised before the lease could give its own refusal.
  Fixed: `_readable_declaration` (None where the declaration refuses) for the exemption and both
  cut readers (create-task facts, brief) -- a question-asking reader never turns the ladder's
  refusal into its own. Rerun of that node 22:23: passed.
- 22:23:57 tools/test_light_kit.py -- 25 passed, 2 FAILED:
  * test_the_pilot_rig_leases_three_orders_of_different_size_per_kit -- the scaffold refuses an
    unstamped kit. Rig `stampcopy.py` (fresh copy + bump_kit_version.py INSIDE the copy, 2026.09.26-6):
    the node PASSES there (22:25:52) -> stamp-only, the merge's.
  * test_no_spawn_or_lease_surface_carries_a_free_text_justification_field -- the CLOSED set of
    spawn-surface keys (DEC-0092 (1) tripwire, red on purpose for any new key). FR-0092 adds
    `description` (a value the lease dictates and the gate compares exactly -- no free text of
    the lead's) and `validate_dispatch(spawn_description=)`. HANDED TO THE MERGE (file not in my
    scope): the set becomes {"prompt","subagent_type","model","description"} and the parameter list
    gains "spawn_description". The Bash half (`run_in_background`, `command`) I kept OFF the spawn
    surface by naming the shell input `shell_input` -- it is not the Agent call's input.
- 22:28:48 tools/test_approvals_dispatch.py -- 236 passed.
- 22:29 added test_the_cut_line_is_bounded_for_the_brief_budget_bug_0318 (brief byte budget: the
  cut line names at most `report._BRIEF_CUT_SHOWN` goals/pairs); M7 (bound removed): RED (22 == 6).
- 22:30:42 tools/test_kernel.py 136 passed; tools/test_model_ladder.py 16 passed.
- 22:30:53-22:38:06 text readers (run_suites.py): test_role_contracts 37, test_shared_skill_contract 6,
  test_parity_sources 9, test_repo_hygiene 44, test_parallel_streams 34, test_office_package 75 --
  all passed. FAILED:
  * test_context_budget.py (3): my constitution clause grew the lead package past the recorded
    ceiling (dev 61905 > 61795, research 63759 > 63651). FIXED by making both constitution edits
    net-negative (dev -9 bytes, research -8 vs base: the DEC-0118 clause shortened, the
    `kernel.dispatch.ladder_for_order;` pointer dropped where `python scripts/harness.py ladder`
    already stands -- the test that reads the paragraph accepts either).
  * test_shortening_net.py (3): two were MY DEFECT -- `handle_pre_tool_use` lost the one-statement
    tool guard the Codex-reach reader recognises (`if tool_name not in SPAWN_TOOLS: sys.exit(0)`);
    fixed by calling `_remember_a_background_run` before the guard, with its own guard inside
    (reads `dispatch.COMMAND_TOOLS` only after the two cheap checks). Rerun 22:40: passed. The third,
    test_no_section_of_a_pinned_instruction_file_disappears_unnoticed, is the section PIN (by
    design red on every changed lead-package section; re-pin writes tools/constitution_section_pins.json
    -- not my scope): HANDED TO THE MERGE: `python tools/pin_constitution_sections.py --write --note
    "TSK-0154 stream B: FR-0093 line corrected (BUG-0313), spawn description (FR-0092), DEC-0118
    effort clause"`.
  * test_research_chain.py (10 errors): scaffold of a research fixture -- checked in the stamped
    copy below.
- 22:41:17-23:02:07 tools/test_hooks_v2.py -- 2168 passed, 3 FAILED:
  * test_a_running_child_is_not_swept_by_the_reconciliation -- asserts `status == "LEASED"` after
    the child's SubagentStart; the bind now STARTS the run (BUG-0314), so it reads IN_PROGRESS.
    The property it holds (the running child is not swept to READY, its binding stands) still
    holds. HANDED TO THE MERGE (file not in my scope): line `assert state.read_item(task["id"])
    ["status"] == "LEASED"` -> `== "IN_PROGRESS"`.
  * test_the_shipped_lead_packages_are_within_their_own_record -- the record must EQUAL the
    measured size (61795 == 61786 after my net-negative edit). FIXED at 23:03: both constitution
    edits are now byte-neutral against 35e929b (dev: "a capped top's architecture: effort
    **xhigh**" + "shows both"; research: "a capped top's method design: **xhigh**" + "shows the
    answer") -- no record change needed.
  * test_validate_py_is_green -- "VERSION not bumped" x3: stamp-only, the merge's.
- 23:02:53-23:15:17 batch 3 (run_suites.py): test_context_budget 42 passed (after the byte-neutral
  constitution edit); test_review_procedure 29, test_staging_cli 99, test_e2e 20 passed. FAILED:
  * test_backlog_types.py (2): MY DEFECT -- the lease's background runs were stored as a LIST and
    read element-wise, which the reference-list tripwire reads as an undeclared list field
    (`background_runs`). FIXED 23:2x: a MAPPING {command: first start}, asked by membership only.
  * test_reference_skills.py (2) and test_kitupdate.py (23): the scaffold refuses the unstamped kit
    ("validate.py FAILED ... bump_kit_version.py", "does not hash to the `content:`") -- stamp-only,
    confirmed in the stamped copy below.
- 23:15:17-23:42:59 tools/test_hooks.py -- 1079 passed, 14 skipped, 8 FAILED, all installer /
  scaffold runs refusing the unstamped kit ("VALIDATION FAILED ... VERSION not bumped").
- 23:42:59-23:49:59 tools/test_migrate.py -- 146 passed.
- 23:52:05 rerun after the mapping fix: tools/test_backlog_types.py + tools/test_stream_b_order_flow.py
  75 passed.
- 23:5x M2 REDONE on the mapping form (`runs_still_going` without the command filter): the
  attribution test first stayed GREEN (the child had started nothing, so the early return hid the
  filter) -- the test was too weak. Strengthened: the child starts its OWN background run (completed
  by its stop) while a FOREIGN shell runs. M2b now RED (`assert None`), the fix green.
- 23:53:26-00:36:05 stamped copy (team-kits/tools/ladder.yaml only, bump INSIDE the copy ->
  2026.09.26-6) over the 45 stamp-candidate nodes (kitupdate 23, hooks 8, reference_skills 2,
  research_chain 10, light_kit pilot 1, hooks_v2 validate 1): 38 PASSED, 7 failed -- all 7 on files
  the copy did not carry (install.ps1 -> `str + None`; user/bridge/update_kit.py FileNotFound; one
  PowerShell run). Rerun of the 31 hooks/kitupdate nodes in a FULL-tree stamped copy below.
- 00:37:29 consolidated red-first of the whole file on base: 16 failed, 1 passed (the attribution
  counter-test, green on base by design, red under M2b).

- 00:41:0x-01:02:14 FULL-tree stamped copy (everything but .git/project_memory, bump inside ->
  2026.09.27-1) over the 31 hooks/kitupdate nodes: 31 PASSED. So every red that remained in the
  reading suites after my fixes is either stamp-only (45 nodes, all green stamped) or one of the
  handed-over lines below.
- 01:02 final: nothing unstaged in the worktree, the six in-scope hooks IDENTICAL x3,
  `ruff check .` all passed.

## Commit, EVDs

- 00:3x `git commit` in the worktree REFUSED by this repo's gate 3 (gate_commit_evidence): no active
  EVD with result pass names the worktree digest. NOT self-certified: a pass the builder records
  over its own package is what that gate exists against (stream A, TSK-0153, decided the same at
  22:44). Everything is STAGED (`git add`) on g7/dispatch at base 35e929b; the merge takes the tree.
- 00:39:52 per-item selections from the worktree, logs in staging/TSK-0154/evd/*.log (all rc 0):
  BUG-0313 2 passed, BUG-0314 4, BUG-0315 1, BUG-0318 3, BUG-0321 1, BUG-0322 2, BUG-0324 2, FR-0092 1.
- 00:40:46 recorded through the MAIN repo's kernel (kind test, result pass, run_scope selection):
  EVD-0491 BUG-0313, EVD-0492 BUG-0314, EVD-0493 BUG-0315, EVD-0494 BUG-0318, EVD-0495 BUG-0321,
  EVD-0496 BUG-0322, EVD-0497 BUG-0324, EVD-0498 FR-0092. No transition, no mint.

## Handed to the merge (files outside this stream's scope), each named with the exact edit

1. tools/test_light_kit.py::test_no_spawn_or_lease_surface_carries_a_free_text_justification_field --
   the closed spawn-surface set gains "description"; `validate_dispatch`'s parameter list gains
   "spawn_description" (FR-0092 re-decides DEC-0092 (1)'s set for a value the lease dictates and the
   gate compares exactly -- the lead/user's call, stated so).
2. tools/test_hooks_v2.py::test_a_running_child_is_not_swept_by_the_reconciliation -- `== "LEASED"`
   -> `== "IN_PROGRESS"` (the bind starts the run, BUG-0314; the swept-to-READY property holds).
3. Section re-pin: `python tools/pin_constitution_sections.py --write --note "TSK-0154 stream B:
   FR-0093 cost line (BUG-0313), spawn description (FR-0092), DEC-0118 effort clause"`.
4. tools/test_board.py `_WRITERS_THE_BOARD_DOES_NOT_RENDER`: the entry ("dispatch.py",
   "bind_agent_by_role"): "the lease file" is no longer the whole truth -- it now also starts the run
   through `_start_the_run_locked`, which regenerates. Not red (still a writer), but the register's
   sentence under-describes it.
5. .claude/agents/harness-lead.md carries the old FR-0093 background line (this repo's lead); the
   kits' corrected text is in the three PM skills -- a user patch line if the lead's own spawns are
   to follow it.
6. The stamp (bump_kit_version.py) and the full delivery run.

## Named, not closed

- BUG-0313 residues (stated in `dispatch.CHILD_WAITING`'s comment): attribution is by command TEXT,
  so another agent running the identical command in the background turns a child's real end into a
  wait nobody resumes; a child that ends while its own background server runs reads as waiting until
  the server ends; a provider without `background_tasks` (Codex: unmeasured) reads the stop as an
  end as before -- the kits' order line tells the specialist to run in the foreground there.
- Made visible by the measurement, pre-existing: a RESUMED child (SubagentStart again, same
  agent_id, unbound because its lease is gone) of the same role can take an OPEN bind window by role.
  Bounded by the window (120 s) and `prompt_id`; not changed here.
- FR-0092: a spawn payload WITHOUT `description` is not refused (the provider always sends one,
  measured; None is a library caller). FR-0092 (3) -- this repo's lead naming its own spawns -- is
  the lead's.
- BUG-0318 (c) (the migration re-cut not reproducing V1 granularity) is `kernel/migrate.py`,
  forbidden to this stream.
- DEC-0118 (4) (the claude-watcher's standing tier duty) is the user's file, not built here.
