# TSK-0156 protocol (merge of order 7: C, B, A) -- written as I go

## 2026-09-27T06:33 start
- Worktrees g7-field / g7-dispatch / g7-approvals: HEAD 35e929b each, everything STAGED, no unstaged,
  no untracked (git status/ls-files --others read 06:34). Main tree: nothing changed outside
  project_memory/ at start.
- Method (instead of `git apply --3way`, which implies --index and would stage in the MAIN index):
  rig `_round-scratch/TSK-0156/merge_stream.py <stream>` -- per file of `git diff --cached 35e929b
  --name-only` in the worktree: main bytes == base blob -> take the worktree file whole (binary);
  main == worktree -> nothing; else `git merge-file main base worktree` (conflict markers, no index).
  Patches exported for the record: `_round-scratch/TSK-0156/{field,dispatch,approvals}.patch`.

## 2026-09-27T06:35 stream C (TSK-0155) merged
- 36 files, all TAKE (main tree at base for every one), 0 conflicts.

## 2026-09-27T06:35:22 stream B (TSK-0154) merged
- 15 files: TAKE 8 (spec, gate_dispatch x3, dispatch.py, report.py, state.py, test_stream_b_order_flow.py);
  MERGE 7, each `git merge-file` rc 0 (no overlapping hunk): README.md, dev/research AGENTS.md,
  cli.py, the three PM skills. Seam read by word diff (dev AGENTS.md): C's hunks (command list
  `upkeep`, kit-update passage) and B's (DEC-0118 ladder clause) sit in different paragraphs.

## 2026-09-27T06:35:40 stream A (TSK-0153) merged
- 20 files: TAKE 11 (POST_V2_WISHLIST, gate_approval x3, guard_question_context x3, approvals.py,
  sdk_approval.py, test_approvals_dispatch.py, test_stream_a_approvals.py); MERGE 9, each rc 0:
  README.md, HARNESS_V2_SPEC.md, AGENTS.md x3, PM skills x3, cli.py. No conflict marker anywhere.
- 06:35:56 A's foreign_tests.patch (staging/TSK-0153, 726 lines) applied with `git apply` (worktree
  only, `--check` rc 0 first): test_hooks_v2, test_hooks, test_light_kit, test_presets,
  test_staging_cli, test_report, test_office_package, test_kernel, test_kitupdate,
  light_kit_pilot.py, .claude/hooks/test_gates.py, user/claude/hooks/handover_guard.py. No CR bytes
  written (Grep over the patched files: 0).

## 2026-09-27T06:38 hand-overs (tests)
- B1 / DEC-0122: tools/test_light_kit.py::test_no_spawn_or_lease_surface_carries_a_free_text_justification_field
  -- tool-input set + "description", validate_dispatch parameters + "spawn_description", DEC-0122
  cited in the docstring. Before: 1 failed ("Extra items in the left set: 'description'").
- B2: tools/test_hooks_v2.py::test_a_running_child_is_not_swept_by_the_reconciliation -- LEASED ->
  IN_PROGRESS (BUG-0314 comment).
- B4: tools/test_board.py `_WRITERS_THE_BOARD_DOES_NOT_RENDER` bind_agent_by_role entry names the
  task write through `_start_the_run_locked` (held by the same file's
  test_no_kernel_writer_of_a_rendered_file_leaves_the_board_behind).
- C: tools/test_hooks_v2.py::test_the_trust_message_names_a_remedy_that_actually_leaves_the_state --
  trigger = a .pyc planted into .claude/kernel/__pycache__ (the import route cannot cache since
  BUG-0310); the existing `== "hooks_trust_required"` assert right after is the trigger's guard.
- 06:37:52 the three nodes: 3 passed (19.9 s).

## 2026-09-27T06:49 upkeep bound (BUG-0325 / H223, captured with --hole 06:42)
- PLAN / rejected way (FR-0084): refusing `upkeep` to a subagent WHOLESALE (a third map beside
  `_ORDERING_COMMANDS`) was rejected -- it re-closes the dead end BUG-0323 opened the door for (a role
  bringing its OWN memory under budget). Reading the role by POSITION was rejected too: `--retire
  <own> <other>` puts the own role where a positional reader looks and the other where argparse
  looks. Built: rule 4's third class in gate_write_scope (x3 mirrored, md5 57ab827a...):
  `_UPKEEP_COMMANDS` + `_upkeep_refusal`, which parses the line with the KERNEL'S parser
  (stdout/stderr swallowed), refuses a door whose parse has no `role` (shared state), and a role
  that is not the payload's `agent_type` (the field the craft-memory write window already decides
  "own" on); an unparsable line is refused (fail-closed). Lead untouched (caller == "").
- Tests (tools/test_hooks_v2.py, batteries READ OFF the kernel parser): test_the_upkeep_batteries_are_not_empty_and_match_the_gates_command_name,
  test_a_subagent_cannot_run_an_upkeep_door_on_shared_state_bug_0325 (x4),
  test_a_subagent_cannot_prune_another_roles_memory_bug_0325 (x3),
  test_a_subagent_still_prunes_its_own_memory, test_the_lead_runs_every_upkeep_door (x14).
- RED on the real tree before the gate edit (06:42:09): 9 failed -- every shared door rc 0 from a
  bound subagent, every foreign prune-memory rc 0, the anonymous own-memory line rc 0.
- Mutation rig `_round-scratch/TSK-0156/redfirst.py` (copy per mutation, binary): control GREEN
  (8 passed); M1 role read by position -> RED (the --retire spelling); M2 shared branch off -> RED 4;
  M3 own-role check off -> RED 4; M4 refusal unwired -> RED 4.
- 06:45:25 rule-4 selection (`-k "upkeep or prune or ordering or installing or install_approval or
  harness_commands"`): 100 passed.

## 2026-09-27T06:57 user patch (H47 / DEC-0120 + FR-0093 lead line), re-pin, size re-record, hole index
- staging/TSK-0156/apply_user_patch.py + user-patch.md: 4 sites (3 in .claude/hooks/_harness.py for
  H47, 1 in .claude/agents/harness-lead.md for the FR-0093 line after BUG-0313). `--check` on the
  merged main tree: "CHECK ONLY -- 4 site(s) to change".
- Test in .claude/hooks/test_gates.py: test_gate1_refuses_a_redirect_into_a_variable_bug_0139 (6 lines
  x 2 callers) + test_gate1_still_passes_a_redirect_with_no_expansion_in_its_target (4).
  Main tree (unpatched) 06:51: 10 failed / 4 passed (before the backtick line); rig
  `_round-scratch/TSK-0156/h47_rig.py` 06:55: unpatched copy 12 failed / 4 passed, patched copy 16
  passed. First patched cut let the backtick line through (2 red) -> site 1b adds the backtick for
  the path position only.
- 06:56 `pin_constitution_sections.py --write` (31 sections) and `record_lead_package_sizes.py --write`
  (+923 / +873 / +913 B dev / office / research), each ONCE, notes naming the three streams.
- 06:56 `migrate-holes --reindex`: 213 holes, H223/BUG-0325 row added (and five stale statuses
  refreshed from the store).

## 2026-09-27T06:58 stamp, validate, ruff
- 06:57:37 ONE stamp: `python tools/bump_kit_version.py` -> 2026.09.27-1 (dev, office, research).
- validate.py first FAILED on the three new `templates/repo/.gitattributes` (C's new files, "hashed
  into a kit VERSION but not git-tracked" -- in C's worktree they were staged). `git add -N` (intent
  to add, no content staged) on exactly those three files -> 06:58:14 "all structural checks passed".
  No other index change.
- ruff: tools/test_hooks.py:15329 unused `request_id` (A's foreign_tests.patch) -> the lookup kept as
  an assert (the card's code must name a pending request). Remaining: 1 error in
  project_memory/staging/generation-6/create_order_7_merge.py:55 (the LEAD's staging script, not
  touched); `ruff check . --exclude project_memory`: All checks passed.
- Mirrors: the 7 hooks the merge touched and that are mirrored are byte-identical x3 (md5); session_status is
  KIT_SPECIFIC_HOOKS.

## 2026-09-27T07:02 self-found defect in the upkeep bound -> SECOND stamp
- Batch 1 of the reading suites started 06:59:15 and was KILLED at ~07:00 (after test_stream_a_approvals
  34 passed) because my own review found: `_upkeep_refusal` handed the kernel's parser the stage WITH
  its redirections (`... --retire t0.md > prune.log`), so a subagent's own-memory prune with any
  redirect failed to parse and was refused (over-refusal). Fixed: operator + consumed word dropped via
  the kits' `_REDIRECT_RX`/`_INPUT_REDIRECT_RX`; the descriptor word of `2>&1` stays in (fail-closed,
  named in the docstring and pinned by test_a_subagent_still_prunes_its_own_memory).
- Mutation rig 07:02: control GREEN 8; M1-M4 RED as before; M5 (no redirect strip) RED 1.
- gate_write_scope re-mirrored x3 (md5 2c5e8bb8...). Kit file changed after the stamp -> 07:02:37
  SECOND stamp 2026.09.27-2 (the first, -1, was taken before this fix). validate green, ruff
  (excluding project_memory) green.
- 07:03 kit_trust_state (x3, md5 4f11a21f...): the hooks_trust_required message named "a python process
  that imports `.claude/kernel` without `-B`" as the commonest cause -- the route BUG-0310 (stream C)
  closes, so the message pointed at a cause that no longer occurs; now "a tool leftover -- a
  `__pycache__`, a linter cache -- inside the hashed bundle" (what `upkeep prune-caches` removes).
  THIRD stamp 2026.09.27-3 (07:03:27), validate + ruff green. Reading suites start after this.

## 2026-09-27T07:14 reading suites, batch 1 (main tree, stamped -3, one pytest at a time via `_round-scratch/TSK-0156/suites.py`, logs in `_round-scratch/TSK-0156/logs/`)
- green so far: test_stream_a_approvals 34 (07:03), test_stream_b_order_flow 17 (07:04),
  test_stream_c_field 12 (07:07), test_light_kit 27, test_board 77, test_state 67, test_report 141,
  test_ladder 67, test_model_ladder 16, test_backlog_types 58, test_schemas 30, test_e2e 20,
  test_routine_feed 32, test_close_measured_pass 12 (07:13:58).
- A's unexplained F located by COUNT, not yet by run: A's progress line
  (staging/TSK-0153/evd/reading-suites.log:41) is `..................................F...` -- the
  35th node in collection order failed and the 39th ran 37 min until the kill. File order of
  test_gates.py: 1 + 1 + 14 (REGISTERED_PAIRS) + 1 + 1 + 1 + 9 + 4 + 2 = 34, so #35 is
  `test_gate1_reads_a_junction_as_the_tree_it_points_at` and #39 is the 4th case of
  `test_gate1_refuses_a_shell_write_into_a_protected_area`. To be run as a selection after batch 1.
- 07:43:02 batch 1 DONE, all 28 suites rc 0: + test_board_browser 5, test_kit_neutrality 7,
  test_role_contracts 37, test_context_budget 42, test_shortening_net 36, test_kernel 136,
  test_staging_cli 99, test_presets 34, test_office_package 75, test_research_chain 10,
  test_pointer_sweep 8, test_approvals_dispatch 236, test_kitupdate 87 + 1 skipped (14:21),
  test_migrate 147 (4:40).

## 2026-09-27T07:46 A's unexplained F in the gate suite
- Collection order confirmed by `--collect-only` (07:44): #35 = test_gate1_reads_a_junction_as_the_tree_it_points_at,
  #36-#47 = test_gate1_refuses_a_shell_write_into_a_protected_area (12), #39 = its `.claude/settings.json` case.
- MERGED TREE: the two suspects alone 13 passed (07:43, 21 s); the whole prefix #1-#47 as ONE
  selection 47 passed (07:45, 36 s).
- A's OWN WORKSPACE (_round-scratch/TSK-0153/foreign/tree): the two suspects 13 passed (07:44); the
  prefix 47 passed (07:46, 35 s).
- So the F does NOT reproduce, in either tree, in the order A's run met it. A's runner captured the
  output (`capture_output=True`, `ws_suites.py`/reading_suites) and was killed, so the F's message
  never reached a file -- its cause cannot be named from the record. What the record DOES show: 38
  nodes in 2343 s where the same 47 take 36 s here, i.e. the run was stalled, not slow; an F under
  those conditions is not evidence about the code. Not a claim that the suite is green: the whole
  suite is the merge's DELIVERY_RUN (DEC-0121 (1)), not run here.

## 2026-09-27T08:06 SEAM DEFECT found by the gate selections: stream C broke this repo's gate 1 on every relative `cd`
- Batch b2 (07:47-08:01, one pytest per selection, main tree stamped -3):
  * `-k "group or walked or directory or cd or position or moves or pushd"`: 11 FAILED / 51 passed --
    every failure "this gate could not decide and therefore refused (fail-closed): _walk() missing 2
    required positional arguments: 'root' and 'moves'" (test_gate1_comes_back_out_of_a_group_it_walked_into x7,
    test_gate1_does_not_read_a_bare_verb_as_a_file_in_the_working_directory x4).
  * `-k "redirect or unresolved or resolve or variable"`: 12 failed = exactly the H47 test before
    the user patch (expected, DEC-0120 (4)), 38 passed.
  * `-k "approval or mint or question or shared_body or cannot_decide or refusable"`: 23 passed.
  * `-k "points_into or cites or registration or table or watch_list or producer or stamper or kit_hash"`: 20 passed.
- Cause: stream C (BUG-0317/0323) grew the kits' `gate_write_scope._walk(pipeline, cwd)` to
  `(pipeline, cwd, root, moves, assignments=None)`; `.claude/hooks/_harness.py` (`WorkingDirectory._resolve`,
  line 2538) borrows the kits' reader and still calls `module._walk(pipeline, <absolute base>)`. A scan of
  every `module._<name>` this repo's hooks borrow against base vs merged signatures: `_walk` is the only one.
  LIVE in this session since the merge: gate 1 refused every line with a relative `cd` (absolute `cd` goes
  another branch, which is why my own lines passed).
- Fix, kit side (in scope, no user patch needed): `root`/`moves` optional; the two-argument call walks the
  same `_walk` rooted at the absolute directory it stands on and answers an absolute directory (or None /
  another-drive absolute as before). Docstring names the caller and the test. Mirrored x3 (md5 7624f518...).
- After: the same selection 08:05:58 -> 62 passed. Every test id containing "cd" is in that selection, so
  no refusal-expecting case that had passed only through the crash's fail-closed answer is left unmeasured.
- FOURTH stamp 2026.09.27-4 (08:06:16); validate + ruff green.
- 08:11:33 b3 gate selection (stamped -4) `-k "starting_a_hook or start_shape or maintaining or startable or
  verb_itself or minted_an_approval or gate3"`: 258 passed (4:50). test_hooks_v2 started 08:11:33.
- 08:34:27 tools/test_hooks_v2.py (stamped -4): 2194 passed (22:50) -- incl. the upkeep bound's 26
  cases, the three hand-over nodes. test_hooks.py started 08:34:27.
- 09:11:31 tools/test_hooks.py (stamped -4): 1087 passed, 14 skipped (37:00).

## 2026-09-27T09:12 close
- Final: `apply_user_patch.py --check` "4 site(s) to change"; validate.py green; ruff green outside
  project_memory (one error in the lead's staging/generation-6/create_order_7_merge.py, not mine).
  Kits at 2026.09.27-4. Rig copies removed (`_round-scratch/TSK-0156/rig`); the rig scripts stay
  (redfirst.py, h47_rig.py, merge_stream.py, mirror.py, suites.py, wait.py; logs/ with every suite's output).
- NOT done, by order: full run (DEC-0121 (1)), commit, push, mint, BUG transitions, applying the user patch.
- Stamps: FOUR, not one -- -1 after the merge, -2 after my own redirect fix in the upkeep bound, -3 after
  the trust-message text, -4 after the `_walk` seam fix. Each fix came after the stamp it invalidated.

## Rework 1 (TSK-0157) -- written as I go

### 2026-09-27T17:0x start
- Order: TSK-0157 (continues TSK-0156). Scratch: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0157/`
  (rig scripts copied from TSK-0156: suites.py now with a per-run timeout that kills the tree and logs
  rc=TIMEOUT; output straight to a file, not a pipe).
- First run (alone, nothing else running): the tilde node, 1500 s timeout.
- PLAN for F4 / BUG-0326, and the way REJECTED (FR-0084): the rejected way is "the sweep drops the
  lease AND clears CHILD_WAITING with it" (the item's second option). It would unblock `dispatch`, but
  the resumed child would still find no lease -- its writes resolve through the lease
  (`task_for_agent`), so it would be an unbound builder -- and the re-lease it unblocks puts a SECOND
  child beside it, which is BUG-0313 again. Taken instead: an expiry does not release the lease of a
  task whose child is WAITING (one predicate, read at both expiry-release sites: `sweep_expired_leases`
  and the expiry branch of `_validate_lease_locked`), the sweep NAMES such a lease, and every refusal
  that meets a waiting child names the FAILED way out (`transition <id> FAILED`, which drops the lease).

### 17:0x-17:15 edits (tilde node running alone meanwhile; nothing else run)
- Snapshot of the UNFIXED tree for the red-first runs: `_round-scratch/TSK-0157/rig/before-fix`
  (taken after the two BUG-0326 tests were written, before any fix).
- F4/BUG-0326: `kernel/dispatch.py` -- `_held_by_a_waiting_child_locked` (one predicate) read at both
  expiry-release sites (`sweep_expired_leases`, `_validate_lease_locked`) and in `create_lease`'s
  lease-exists branch (its old sentence sent the lead to a sweep that now keeps the lease);
  `waiting_leases`; `_relet_refusal_locked` WAITING branch names `transition <id> FAILED`.
  `kernel/cli.py` sweep-leases prints a line for leases held by a waiting child.
  Tests: `tools/test_stream_b_order_flow.py::test_a_swept_lease_of_a_waiting_child_does_not_strand_its_task_bug_0326`,
  `::test_every_refusal_that_meets_a_waiting_child_names_the_failed_way_out_bug_0326`.
- F1: `tools/test_light_kit.py` comment narrowed to what is checked + a new assertion: no word with a
  path separator on any placeholder card (the placeholders carry none, so a separator is the renderer's).
  The card is NOT changed: the document cards' proposal path is the file the card's own limit line
  sends the reader to -- a named deviation from DEC-0119 (6)'s "no paths", for the lead.
- F2: `tools/test_presets.py` two pointers moved to `approvals._preset_lines`.
- F3: kit `gate_write_scope._upkeep_refusal` -- a parse that ends cleanly (SystemExit code 0/None =
  the parser answering --help) passes; mirrored x3 (md5 ea6d0c16...). Test:
  `tools/test_hooks_v2.py::test_an_upkeep_help_line_passes_and_no_parse_prints_on_the_hooks_channels`.
- F5: `kernel/__init__.py` -- `_installed_here` compares the holder as a directory (`samefile` with
  `<parent>/.claude`), limit named (a link under another name). Test parametrized over `.claude`/`.CLAUDE`,
  the second skipped where the filesystem keeps them apart.

### 17:26 tilde node, alone in the main tree
- `.claude/hooks/test_gates.py::test_gate1_places_a_tilde_word_where_the_shell_puts_it`, 17:01:06 ->
  killed by the 1500 s timeout at 17:26:08 (rc=TIMEOUT, 1502 s), no result line.
- NOT a hang: at 17:23:56 the pytest process (pid 41828) had 16 live `bash.exe -c "sed -i ... ~<prefix>/
  team-kits/kernel/state.py"` children created that same second -- the shell arbiter was still
  walking subjects. `len(TILDE_SUBJECTS)` = 7527 (read by import, not by a run). The host was shared
  with another session's runs (synaipse pytest + vitest) during the whole window.
- Verdict for the DELIVERY_RUN: this node needs > 25 min on this host under that load; the delivery run
  of test_gates.py needs a timeout well above that or this node separately.

### 17:26-17:33 red-first (rig `_round-scratch/TSK-0157/redfirst.py`, copies under rig/, logs/red-*.log)
- before-fix snapshot, both BUG-0326 tests: 17:26:55 rc=1 RED, 2 failed -- "the sweep dropped the lease of a
  waiting child" / dispatch said "a lease ... already exists ... (already expired -- the sweep releases it now)".
- one mutation per site, each RED alone: M1 sweep releases a waiting lease -> test 1; M2 expired re-spawn
  releases it -> test 2 ("the expired re-spawn released a waiting child's lease"); M3 create_lease's old
  sentence -> test 2; M4 waiting branch without the way out -> test 2; M5 no waiting line in sweep-leases
  -> test 1.
- SELF-FOUND while reading the callers of the kept lease: `running_leases` read TTL only, so the lease the
  sweep now keeps was "not running" for the file-ownership rule -- a second order over the waiting child's
  files was leasable beside it (BUG-0313 one order over). Not a regression (before, the sweep deleted the
  lease), but the fix made the state explicit, so `running_leases` now counts a waiting child's lease.
  Test `::test_a_waiting_childs_kept_lease_still_owns_its_files_bug_0326`; M6 (TTL-only) -> RED "DID NOT RAISE".
- F3a (every SystemExit refused) -> RED ("do not parse (upkeep --help)"); F3b (silencing removed) -> RED
  ("usage: python scripts/harness.py upkeep [-h]" on the hook's stdout); F5 (name comparison) -> RED only
  the [.CLAUDE] case (3 .pyc under the copy); F1 (renderer writes `staging/` into the proposal card) -> RED.
- Green in the main tree (unstamped, the new nodes only): BUG-0326 x3 17:32:26 3 passed; F3 1 passed;
  F1 1 passed; bug_0310 2 passed + the scaffold test failed on the unstamped kit (expected, VERSION).

### 17:33 stamp (ONE, after the last edit) + checks
- `python tools/bump_kit_version.py` -> 2026.09.27-5 x3; `--check` unchanged x3; `tools/validate.py` "all
  structural checks passed"; ruff: 1 error, only in the lead's `staging/generation-6/create_order_7_merge.py`
  (not mine, as in the round before); pins "all pins current"; sizes "every size is the one on record".
- Reading suites (DEC-0080 rule 2), chosen by grep for the changed names (`create_lease`,
  `validate_dispatch`, `verify_dispatch_identity`, `validate_lease`, `sweep_expired_leases`/`sweep-leases`,
  `CHILD_WAITING`, `_relet_refusal`, `running_leases` via the parallel-lease rules, `dispatched_repo`,
  `run_dispatch`) plus the files touched: stream_b, approvals_dispatch, kernel, ladder, board, staging_cli,
  parallel_streams, light_kit, stream_a, stream_c, presets, report, reference_skills, e2e, kitupdate
  (installed-kernel imports, F5), test_hooks.py as a -k selection of the six tests that name those
  predicates or the installed bytecode producer, test_hooks_v2.py whole (dispatch gate + the upkeep bound).
  `conftest.drive_task_to` calls `create_lease` for ~100 other tests; the changed create_lease branch is
  reachable only with CHILD_WAITING set, which no test outside stream_b writes, so those are not re-run.
  Batch r1 started 17:34, one pytest at a time, timeout 3000 s each.

### 19:22 lead note (the builder died of the usage limit after batch r1, before its report)
- Read from the rig logs: batch r1 17:33-18:37, 17 reading suites, all rc=0 (stream_b 20, approvals_dispatch 236, kernel 136, ladder 67, board 77, staging_cli 99, parallel_streams 34, light_kit 27, stream_a 34, stream_c 13, presets 34, report 141, reference_skills 18, e2e 20, kitupdate 87+1 skip, hooks -k 8, hooks_v2 2195). No file under team-kits/tools/docs newer than 17:34; stamp --check unchanged 2026.09.27-5 x3.

## Rework 2 (TSK-0158) -- written as I go

### 19:41 start
- Order: TSK-0158 (continues TSK-0157, FAIL in staging/TSK-0157/verify-round-1.md). Scratch:
  `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0158/` (suites.py / wait.py / mirror.py copied from
  TSK-0157; a new redfirst.py). Tree state at start: rework 1 as left, stamp 2026.09.27-5.
- PROTOCOL CORRECTION (rework 1, "PLAN for F4", the rejected way): the reason "it would unblock
  `dispatch`" was half wrong -- `_relet_refusal_locked` admits a re-lease only on CHILD_ENDED, so a
  sweep that cleared CHILD_WAITING with the lease would still leave `dispatch` refused. The rejection
  stands on the other half alone: the resumed child finds no lease (`task_for_agent`), so it runs
  unbound -- its writes refused, its end never recorded.
- PLAN, and the ways REJECTED (FR-0084):
  - N1: `_upkeep_refusal` refuses every SystemExit again (rework 1's clean-exit pass out). Rejected:
    strip `-h/--help` on a clean exit and re-parse (the verifier's first option) -- the gate's word
    list and the shell's argv part in both directions (`<(...)` ADDS a word, `<<<` removes one), so a
    re-parse is still a guess about a line; stream B of the next wave replaces the guessing. What the
    smaller way does not cover: a subagent's real `upkeep ... --help` is refused -- named as an
    over-refusal hole.
  - N2: `create_lease` drops CHILD_WAITING with CHILD_ENDED on a non-relet lease; the sweep-leases
    WAITING line names each task's own way out (the status `_relet_refusal_locked` names, one helper
    for both). Rejected: clearing CHILD_WAITING on the transition to FAILED -- it covers the walked
    chain only; every other route into a new dispatch (orphan sweep, any transition off) would need
    the same, while the new lease is the one moment all of them pass.
  - N3 and the spawn-letter suspicion: measured, named as holes (kernel `capture BUG --hole` +
    `migrate-holes --reindex`, the hole list is generated from items), not fixed.

### 19:42-19:48 tests first, snapshot, fix, red-first (rig `_round-scratch/TSK-0158/redfirst.py`)
- Tests written BEFORE the fix: `tools/test_hooks_v2.py::test_a_help_word_the_shell_does_not_hand_over_opens_no_upkeep_door_bug_0325`
  (nine suffixes), `::test_no_help_word_of_the_battery_reaches_the_kernel_through_a_real_shell` (the
  battery's class membership: git's bash + a stand-in harness.py recording argv), the F3 test renamed
  `::test_an_upkeep_help_line_is_refused_and_no_parse_prints_on_the_hooks_channels` (help now rc 2,
  silencing half kept); `tools/test_stream_b_order_flow.py::test_a_new_lease_after_the_failed_way_out_is_a_new_dispatch_bug_0326`,
  `::test_the_sweep_names_each_waiting_tasks_own_way_out_bug_0326`.
- Snapshot `rig/before-fix` 19:43:40 (rework 1 code + new tests). before-fix 19:44:04 rc=1: 7 of 9
  suffixes RED (` # --help` and `` `: --help` `` green, refused on other grounds), the help-line
  test RED, N2 test RED at "assert not CHILD_WAITING" (the mark of the ended run survived FAILED,
  READY and the new lease), way-out test RED (line named "`transition <id> FAILED`" for a LEASED order).
- Fix: gate `_upkeep_refusal` refuses every SystemExit (mirrored x3, md5 39fc46d1...); `create_lease`
  pops CHILD_WAITING with CHILD_ENDED on a non-relet; `dispatch._way_out_status` (one helper, read by
  `_relet_refusal_locked` and `waiting_leases`); sweep-leases WAITING line names per task
  "`transition <id> <way out>`".
- Green, main tree, unstamped: 19:45 upkeep selection of test_hooks_v2 42 passed; 19:46 stream_b 22 passed.
- Mutations on copies of the FIXED tree, each alone: N1-clean-exit-passes -> RED (the same 7 + the
  help-line test); N1-parse-not-silenced -> RED (help-line test); N2-new-lease-keeps-waiting -> RED;
  N2-sweep-names-fixed-failed -> RED; ARB-stand-in-appends-help -> RED 9/9 (the arbiter can fail).

### 19:49 measured on a copy of the FIXED tree (`_round-scratch/TSK-0158/measure.py`, logs/measure-*.txt)
- N3 holds unchanged after the fix: waiting child, lease expired, sweep 1 keeps it; resume clears the
  mark; sweep 2 "lease kept False", status IN_PROGRESS, "lease expired, status left standing: TSK-0001";
  child write rc 2 "not bound to a task"; child stop records no end; lead Stop rc 0 (no finding);
  `dispatch` rc 1 "No record says its child stopped". -> hole.
- Spawn-letter suspicion is REAL: goal with three build orders of one role, check-scopes run; TSK-0001
  dispatched ("Backend Developer · Sonnet high", letter A), its child waits, lease expired and kept by
  the sweep; `dispatch TSK-0002` rc 0 -> letter 'A', name "Backend Developer · Sonnet high" -- the
  same name as the waiting child's, while `running_leases` counts both. `_spawn_name_locked` reads
  "live" by TTL only. -> hole.

### 19:50-19:53 holes, docstrings, stamp
- Captured through the kernel (`capture BUG --hole`, JSON bodies in the scratch dir), then
  `migrate-holes --reindex` (216 holes; the doc diff of this step is the three new rows):
  BUG-0327 = H224 (upkeep --help over-refusal), BUG-0328 = H225 (N3), BUG-0329 = H226 (spawn letter).
- Docstrings that claimed more than the code builds now name the gaps: `_held_by_a_waiting_child_locked`
  (holds only while the child waits -> H225), `_spawn_name_locked` ("live" by TTL -> H226); the gate
  docstring names BUG-0327 and the nine-suffix test.
- 19:52 `bump_kit_version.py` -> 2026.09.27-6 x3, `--check` unchanged x3; `validate.py` all structural
  checks passed; ruff 1 error, only the lead's `staging/generation-6/create_order_7_merge.py` (not mine).
- Reading suites (DEC-0080 rule 2), chosen by grep for the changed names (`_upkeep_refusal`/upkeep,
  `create_lease`, `waiting_leases`/sweep-leases, `_relet_refusal_locked`/`no_progress_status`,
  `running_leases`, the hole index): test_hooks_v2 (whole: the gate + the dispatch gate), stream_b,
  approvals_dispatch, kernel, parallel_streams, stream_c_field (upkeep through the gate),
  migrate_holes + repo_hygiene (the index and the new hole items), test_hooks -k "upkeep or sweep".
  Batch s1, one pytest at a time via suites.py, timeout 3000 s each, logs `_round-scratch/TSK-0158/logs/`.
- SELF-FOUND after the stamp, 19:53: `_held_by_a_waiting_child_locked` still said every refusal names
  "`transition <id> FAILED`" -- for a LEASED order they name READY. Comment-only fix, so a SECOND stamp
  (not the one the order asked for): 19:53:40 -> 2026.09.27-7 x3, `--check` unchanged; validate passed,
  ruff the same single foreign finding. Batch s1 had started 19:53:03 on stream_b (behaviour unchanged
  by a comment). The arbiter helper's docstring in test_hooks_v2 narrowed (outside the kit hash:
  `--check` unchanged after it). 25 shared hooks byte-identical x3 (`hooks_identical.py`; the 9 others
  are kit-specific or dev-only, as in round 1).

### batch s1 (stamp -7 for all but stream_b's first 37 s)
- stream_b 19:53-19:54 22 passed; approvals_dispatch -19:56 236 passed; kernel -19:56 136 passed;
  parallel_streams -19:57 34 passed; stream_c_field -20:02 13 passed; migrate_holes -20:02 14 passed;
  test_hooks -k "upkeep or sweep" -20:05 27 passed.
- repo_hygiene -20:04 rc=1, 2 failed, 42 passed -- BOTH FOREIGN AND PRE-EXISTING (present in TSK-0157's
  before-fix snapshot / dated 09-26): (1) CRLF on disk in `staging/TSK-0152/user-patch3-applied.txt` and
  `staging/generation-6/harvest-synaipse-2026-09-26.txt` (lead's files, under project_memory/, not my
  scope); (2) `team-kits/kernel/migrate.py:260` cites `tools/test_stream_c_field.py::test_an_open_v1_task_is_imported_cancelled_bug_0317`,
  which lives in `tools/test_migrate.py` (order-7 merge seam). Not fixed: not ordered, and (2) would be a
  third stamp. For the lead; the delivery run goes red on both.
- test_hooks_v2 (whole) 20:05:14-20:31:39 rc=0, 2213 passed (round 1's 2195 + the 18 new nodes).

### 20:32 close
- `--check` unchanged 2026.09.27-7 x3; no kit file edited after the -7 stamp. The full run NOT started.
- Open for the lead: the two foreign repo_hygiene findings above; F1 (not mine, approvals stream).

## Rework 2 finish (TSK-0158, 20:33-20:45)

- Fix, one line: `team-kits/kernel/migrate.py:260` pointer `tools/test_stream_c_field.py::test_an_open_v1_task_is_imported_cancelled_bug_0317`
  -> `tools/test_migrate.py::test_an_open_v1_task_is_imported_cancelled_bug_0317` (defined tools/test_migrate.py:7955).
- Sweep for further `tools/test_stream_*::<name>` pointers in team-kits/ + tools/ (AST resolution, scratch
  `_round-scratch/TSK-0158/resolve_pointers.py`, plus the line-wrapped one at kernel/approvals.py:2741): none
  other unresolved; nothing else changed. Outside the ordered pattern and NOT fixed, for the lead:
  `team-kits/kernel/holes.py:216` names `tools/test_migrate_holes.py::test_a_citation_that_names_no_test_stops_the_run_before_it_writes`,
  defined in `tools/test_kernel.py:1273` (the hygiene sweep does not flag it: in holes.py the single backtick literals at :95/:96/:175 shift `_CODE_SPAN_RX` pairing, so the span read at :216 starts at the pointer's CLOSING backtick -- measured with `test_repo_hygiene._test_citations` on the file; a reader limit, not fixed here).
- 20:34:01 `bump_kit_version.py` -> 2026.09.27-8 x3; `--check` rc 0, unchanged -8.
- Red-first in `_round-scratch/TSK-0158/rig` (copy of team-kits, docs, tools, test_gates.py):
  `test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves` 1 passed with the fix; defect
  restored in the copy -> 1 failed, "migrate.py:260 cites tools/test_stream_c_field.py::... -- no such test".
- 20:34:09-20:37:28 `pytest tools/test_repo_hygiene.py -q` 44 passed, 1 warning (CRLF in `.audit/hook_events.jsonl`, a warning, not a failure).
- 20:44:16-20:44:21 `pytest tools/test_migrate.py -k bug_0317` 1 passed, 146 deselected.
- validate.py rc 0; `ruff check team-kits tools` all passed. No commit, no full run, no BUG transition.

## Rework 2 finish B (TSK-0158, 21:08-21:14) -- verify round 1 Finding A, text only

- 21:08:37 read `_upkeep_refusal` docstring, md5 39fc46d1... x3 before.
- `_upkeep_refusal` docstring (gate_write_scope.py, x3): opening qualified -- "THE LINE IS READ BY THE KERNEL'S OWN PARSER (over the words this gate reads, which need not be the shell's -- H227 below), not by position" -- and one sentence added after the BUG-0327 over-refusal: "The other direction is OPEN: a parse that SUCCEEDS can still read other words than the shell hands over -- a word the shell splits into several arguments shifts the role position, so this gate reads the caller's role and the kernel another (H227, BUG-0331; closing it belongs to the next wave's protection-layer stream)." No code change. Mirrored by Edit (a shell `cp` naming a hook file is refused by this repo's gate 1, H80's consequence); md5 bbf827eb... x3 after.
- between 21:09:20 and 21:09:44 (two `date` reads) `kernel.cli --root project_memory migrate-holes --reindex` -> "Index rewritten from the store: 217 hole(s)"; H227 / BUG-0331 / OPEN at docs/POST_V2_WISHLIST.md:2536. (Seen on the way: the same kernel line with a `timeout 300` prefix is refused by gate 1 as a write into project_memory/ -- the kernel form is recognised only without a starter in front. Over-refusal, not measured further, not mine.)
- one stamp: 2026.09.27-8 -> 2026.09.27-9 x3; `--check` rc 0 unchanged -9.
- 21:09:57-21:12:24 `pytest tools/test_repo_hygiene.py -q -p no:cacheprovider` 44 passed, 1 warning.
- 21:12:29-21:12:39 `pytest tools/test_migrate_holes.py -q` 14 passed.
- 21:12:44-21:13:23 `pytest tools/test_hooks_v2.py -k upkeep -q` 33 passed, 2180 deselected.
- 21:13:28-21:13:30 validate.py "all structural checks passed" rc 0; `ruff check team-kits tools` all passed.
- No commit, no push, no full run, no BUG transition.

## Gate tilde diagnosis (TSK-0158, 2026-09-28 11:26-12:34)
Subject: the third red of the delivery run `DELIVERY_RUN=TSK-0158 ... .claude/hooks/test_gates.py` (10:18-11:24),
`test_gate1_refuses_a_line_exactly_where_the_shell_would_write`, 16 cells "cd to a tilde the quoting keeps"
(8 positions x base inside/outside), every one "the gate answered rc 0". Copy: `_round-scratch/TSK-0158/tilde-diag/tree`
(.claude, team-kits, tools, project_memory, CLAUDE.md, ladder.yaml; copied 11:30 by `make_copy.py`, binary);
HEAD `_harness.py` via `git show` (sha256 1b29747b...), working-tree/patch-4 `_harness.py` (6820f89a...).
Swaps by `variant.py`, runs by `run_variants.py` (one node selection, 1500 s budget each, logs in `tilde-diag/runs/`).

- VERDICT: NOT caused by user patch 4. Node matrix (harness x dev-team `gate_write_scope.py`, which `_harness`
  borrows -- `kit_hooks_directories` sorted, first = dev-team):
  * p4 x worktree kit  11:30-11:35 -> 1 failed (`run-patched.log`), 16 tilde cells
  * HEAD x worktree kit 11:39:54-11:44:34 -> 1 failed, the SAME 16 cells (`cmp` of the sorted cell lists: identical)
  * p4 x HEAD kit      11:44:35-11:48:17 -> 1 passed
  * HEAD x HEAD kit    11:48:18-11:52:00 -> 1 passed
- CAUSE: the kits' `gate_write_scope._walk` rewrite of the order-7/TSK-0156 merge (stream C, BUG-0323: absolute
  targets placed, `_absolute_readings`, `_walked_to`; plus the 08:06 seam fix that gave `_walk` its two-argument
  call for `_harness`). `_harness.WorkingDirectory._resolve` decides the tilde itself on the TYPED spelling
  (`readings`/`_expands_a_tilde`, H31) and hands `_walk` only what it read as a literal relative word; the new
  `_walked_to` then expands the de-quoted text again -- `_absolute_readings("~")` = the home directory. Probe
  (`probe_walk.py`, 11:32): worktree `_walk(["cd","~"], base)` -> `C:/Users/zenti`, HEAD -> None. So gate 1
  follows `cd "~"` home while bash stays (H31 reopened). Its sibling in the same class, a quoted PATTERN
  (`_glob_readings` on de-quoted text), is covered by no test: gate 1 on the stand-in (`probe_lines.py`, real hook
  processes) `cd "d*cs" ; sed -i ... team-kits/kernel/state.py` and `cd 'do[c]s' ; ...` rc 0 with the worktree kit,
  rc 2 with the HEAD kit (11:38); bash as arbiter over the sandbox file (`probe_shell.py`, 11:38:47): writes True
  for `cd "~"`, `cd "d*cs"`, `cd 'do[c]s'`; False for `cd ~`, `cd d*cs`. Both are holes of gate 1 in the working tree.
- WHY THE MERGE DID NOT SEE IT: the 08:06 seam selection `-k "group or walked or directory or cd or position or
  moves or pushd"` matches no word of this node's name; its 16 cells are cases INSIDE one node, not test ids.
- The KIT gate itself (not gate 1; `probe_kit.py`, real `gate_write_scope.py` processes, lead caller, bash arbiter,
  12:23): `cd .claude ; cd "~" ; echo x > settings.json`, the same with `cd "../d*cs"` and with `cd \~` -- bash
  writes `.claude/settings.json`, the kit gate rc 0 with the worktree kit AND with the HEAD kit. Pre-existing,
  found on the way, not in the hole list (grep of docs/holes for the shape: only H31, which is gate 1's).
  `R=../docs ; cd '$R'` is rc 2 in all three variants (no residue there).
- FIX (the kits' file, `team-kits/*/hooks/gate_write_scope.py`, in TSK-0158's allowed scope; NO user patch):
  in `_walked_to`, a reading of a word that carries quoting (`ShellWord.spliced`) or that is not the first
  reading (backslash taken out) is not tilde- or glob-expanded; such a word names a place nobody states (None).
  Candidate diff: `project_memory/staging/TSK-0158/walk-quoting-fix.diff` (base = main-tree dev-team file,
  sha256 cbb91f54...). NOT applied to the main tree.
  Measured in the copy with p4 x fix: node + `test_gate1_refuses_a_redirect_into_a_variable_bug_0139` (12) +
  `test_gate1_still_passes_a_redirect_with_no_expansion_in_its_target` (4) +
  `test_gate1_comes_back_out_of_a_group_it_walked_into` 12:18:44-12:22:43 -> 25 passed. Probes with fix: gate 1
  `cd "~"`, `cd '~/x'`, `cd "d*cs"`, `cd 'do[c]s'`, `cd \~` rc 2; `cd ~`, `cd d*cs`, `cd docs`, `cd "docs"` rc 0;
  kit gate `cd "~"`, `cd "../d*cs"`, `cd \~` rc 2, `cd ~`, `cd ../d*cs` rc 0. Fix mirrored x3 + stamped IN THE COPY
  (2026.09.28-1): `tools/test_stream_c_field.py -k bug_0323` 3 passed (12:29); `tools/test_hooks.py -k "directory
  or walk or cd or pushd or popd or position or tilde"` 69 passed / 3 failed, the SAME 3 failed with the worktree
  kit (handover-guard `cd x\n...` x2, `renaming_the_directory`; passed in the main full run, so a copy artefact,
  cause not measured).
  Red without it: the node (16 cells) -- measured both ways above. Tests the fix still owes, none written: the
  glob half for gate 1 and the kit gate's own quoted-tilde/pattern/backslash cases (probe lines above = their shape).
- The previous verifier's "55 of 56 gate-selection nodes green" -- which node was red is not in its record;
  that it was this one is consistent, not measured.
- No commit, no push, no full run, no main-tree file changed but this section and the staging diff.

## Rework 3 (TSK-0159) -- written as I go

### 12:36 start
- Order: TSK-0159 (BUG-0334). Scratch `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0159/`; diagnosis rig
  `_round-scratch/TSK-0158/tilde-diag/` reused. Tree at start: stamp 2026.09.27-9 x3 (`--check` unchanged),
  `gate_write_scope.py` md5 bbf827eb... x3.
- PLAN (FR-0084): apply `staging/TSK-0158/walk-quoting-fix.diff` to `_walked_to` (x3). REJECTED: keeping the
  quote positions through the tokeniser so `cd ~/"My Dir"` stays expandable -- `ShellWord` keeps only
  `spliced` (one bit per word), and carrying spans means changing `_compat.shell_words`, which every gate
  of the three kits reads; the smaller way costs over-refusal on a partly quoted tilde/pattern only, and
  that price is named in the docstring. Also rejected: fixing gate 1 alone in `_harness` (forbidden scope,
  and it would leave the kit gate's own pre-existing hole).

### 12:38-12:43 tests first, snapshot, fix, red-first (rig `_round-scratch/TSK-0159/`, `run.py` one selection + budget, `runs.txt`, logs/)
- Tests written BEFORE the fix: `.claude/hooks/test_gates.py::test_gate1_does_not_expand_a_pattern_the_quoting_keeps_bug_0334`
  (3 pattern forms x 3 quotings + 3 unquoted counter-ends; shell column by the suite's own arbiter, gate 1 real
  process) and `tools/test_hooks_v2.py::test_the_scope_gate_does_not_expand_a_tilde_or_pattern_the_quoting_keeps_bug_0334`
  (x3 kits, lead caller, `cd .claude ; <move> ; echo x > settings.json`, 8 rows: quoted tilde, `\~`, quoted
  pattern x3 spellings, two unquoted counter-ends, the over-refusal price `cd ~/"docs"`; git's bash with HOME
  pointed into the test as arbiter).
- Snapshot `rig/before-fix` 12:40:39 (tree with the new tests, kit unfixed). Red: kit test 12:40:46-12:41:09
  3 failed (every kit: the 5 quoted/escaped rows + the price row rc 0; shell column agreed on all 8 rows);
  gate-1 test 12:41:16-12:41:44 1 failed (all 9 quoted rows rc 0; the 3 unquoted rows right).
- Fix = `staging/TSK-0158/walk-quoting-fix.diff` in dev-team `_walked_to` + docstring (BUG-0334, both tests,
  the price); mirrored by `mirror.py` -> md5 99afc605... x3; `hooks_identical.py`: 34 hooks, the same 9
  kit-specific ones differ as before.
- Green, main tree, unstamped: kit test 12:43:05-12:43:22 3 passed; gate-1 test 12:43:23-12:43:45 1 passed.
- Probe `probe_kit.py` + `lines.txt` (main-tree kit, bash arbiter) 12:42: 16 lines incl. `R="~" ; cd $R`,
  `R='../d*cs' ; cd "$R"`, `pushd "~"`, `cd ~""`, `cd ""~` -- no line where bash writes and the gate passes.
  Over-refusals seen, pre-existing class (variable targets): `R=~ ; cd $R`, `R='../d*cs' ; cd $R` rc 2 while
  bash leaves.

### 12:44-12:47 mutations on `rig/after-fix` (copy of the fixed tree, `mutate.py`, dev-team kit only, restored: md5 99afc605...)
- no-tilde-half: kit test RED (`cd "~"`, `cd \~`, price row), gate-1 pattern test green (its tilde half is the 16-cell node).
- no-glob-half: kit test RED (3 pattern rows), gate-1 pattern test RED.
- quoted-only (drop `index > 0`): kit test RED (`cd \~` row only), gate-1 pattern test green.
- refuse-every-pattern: kit test RED (`cd ../d*cs` counter-end), gate-1 pattern test RED (3 unquoted rows).

### 12:47 ONE stamp + checks
- 12:47:23 `bump_kit_version.py` -> 2026.09.28-1 x3; `--check` unchanged -1 x3; `validate.py` all structural
  checks passed rc 0; `ruff check .` 1 error, only the lead's `staging/generation-6/create_order_7_merge.py:55`
  (foreign, as in rework 2); `ruff check team-kits tools .claude/hooks/test_gates.py` all passed.
- Reading suites (DEC-0080 rule 2): callers of `_walk`/`_walked_to` = the kit gate itself and `.claude/hooks/_harness.py`
  `WorkingDirectory._resolve` (gate 1). Batch `batch.py` (main tree, read-only, one pytest at a time via run.py):
  test_repo_hygiene -k pointer (the two new docstring pointers), stream_c_field -k bug_0323, test_hooks_v2 -k
  "walk or cd or tilde or position", test_hooks -k "directory or walk or cd or pushd or popd or position or tilde",
  test_gates nodes (the 16-cell node, the bug_0139 pair, group node, the new node). Started ~12:48.
- 12:48:2x docstring of the kit test narrowed to what the diagnosis measured (tools/, outside the kit hash).

### batch (main tree, stamp 2026.09.28-1, read-only)
- test_repo_hygiene -k pointer 12:48:11-12:50:02 6 passed; stream_c_field -k bug_0323 12:50:02-12:50:29 3 passed;
  test_hooks_v2 -k "walk or cd or tilde or position" 12:50:29-12:51:59 78 passed; test_hooks -k "directory or
  walk or cd or pushd or popd or position or tilde" 12:51:59-12:53:05 39 passed (the main tree: no copy-only
  failures); test_gates nodes 12:53:05-12:58:17 26 passed (16-cell node, bug_0139 12 + counter-end 4, group 8,
  new node 1).

### 13:40:10 resume check (coordinator reported a network cut; seen from here the run was not cut)
- `gate_write_scope.py` md5 99afc605... x3 (as mirrored at 12:42), `unexpandable` 3x per file = the hunk ONCE,
  `BUG-0334` once; `--check` unchanged 2026.09.28-1 x3. Nothing re-applied.
- After the 12:48 docstring edit: kit test 13:40:24-13:40:50 3 passed; test_repo_hygiene -k pointer
  13:40:50-13:42:50 6 passed.

### close
- No commit, no push, no full run, no BUG transition, no approval mint, no hole captured (none new: the
  over-refusals seen are the named price and the pre-existing variable-target class).

## Rework 4 (TSK-0161) -- written as I go

### 14:34 start
- Order: TSK-0161 (continues TSK-0159; verifier FAIL `staging/TSK-0159/verify-round-1.md`). Scratch
  `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0161/` (run.py, mirror.py from TSK-0159; make_copy.py,
  mutate.py, chain.py from the verifier's rig TSK-0159-verify). Tree at start: stamp 2026.09.28-1 x3
  (`--check` unchanged), `gate_write_scope.py` md5 99afc605... x3.
- PLAN (FR-0084): B2 = two table rows (`cd ../d\*cs`, `cd ../do\[c]s`), no code change; B3/B4/popd = text;
  B1 = NOT fixed (lead: captured as BUG-0335), its limit MEASURED in a scaffolded project. REJECTED: fixing
  the walk now (the verifier's "stays" candidate) -- the lead's decision, wave 1 stream B replaces the walk,
  and a fix here would re-open every reading suite of the gate for a walk that is about to be replaced.

### 14:34-14:36 B2 + B4 (tools/test_hooks_v2.py only), red-first on the rig `tree/` (make_copy 14:35:08-14:35:12)
- Rows `cd ../d\*cs`, `cd ../do\[c]s` (shell stays, gate refuses) added to `_QUOTED_EXPANSION_MOVES`; B4:
  "the first five" -> "the rows whose shell stays".
- mutate.py glob-quoted-only 14:35:35-14:35:52 `1 failed` (-x, dev-team): EXACTLY the two new rows, "the gate
  answered rc 0"; no shell-column disagreement (logs/mut-glob-quoted-only-*.log). none 14:36:04-14:36:26
  `3 passed`. Restored md5 99afc605... after each.

### Rework 4 -- stopped 14:37 (2026-09-28), on the coordinator's order (usage limit)
- DONE: B2 (two rows, red with glob-quoted-only = exactly those rows, green unmutated, rig only); B4 text.
  Both in `tools/test_hooks_v2.py` only (outside the kit hash). No kit file touched, gate md5 still
  99afc605... x3, stamp NOT bumped (still 2026.09.28-1, `--check` unchanged at 14:34).
- LEFT: (1) B3 -- `_walked_to` docstring PowerShell price, x3 mirror. Planned: a pinning test in
  tools/test_hooks_v2.py with a PowerShell-tool payload and a PowerShell arbiter (rows `Set-Location "~"`,
  `Set-Location '~\docs'`, `Set-Location "..\d*cs"`: gate rc 2, PowerShell leaves `.claude`), named by the
  docstring (rule 4b); arbiter env must point USERPROFILE/HOME/HOMEDRIVE+HOMEPATH into the test so the write
  after `~` does not land in the real profile; red-first with mutate.py no-fix. (2) popd sentence of `_walk`
  (:1678-1682) naming the empty-stack case as part of BUG-0335, x3. (3) BUG-0335 limit measurement: reading
  so far (code only, NOT measured yet) -- `kernel.hashing.hook_bundle_hash` covers `BUNDLE_SUBTREES =
  ("hooks", "kernel")` only, so `gate_dispatch._refuse_untrusted_bundle` and `kit_trust_state` do not see
  `settings.json`; the session-start update check compares `kit_version` stamps; `report._trust_hook_registered`
  / `_wired_hooks` (doctor) read settings.json. To measure with chain.py in a scaffolded project. (4) ONE
  stamp, reading suites, validate + ruff.
- Running processes: none. Rig: `_round-scratch/TSK-0161/` (tree/ = copy of 14:35 incl. the B2 rows).

### resumed (coordinator order: 1 measure BUG-0335 limit, 2 B3 test+text, 3 popd text, 4 stamp + suites)
- BUG-0335 rig `measure_0335.py` (from chain.py): scaffold dev-team from tree/ (fake HOME, m-* dirs), the
  SessionStart hooks as processes (flip to active), then per variant (`echo x` = invalid JSON, `echo '{}'` =
  valid, no hooks) the overwrite through the full registered Bash chain + bash, then SessionStart hooks as
  registered BEFORE (as if they still ran), kit_state.json, gate_dispatch on an Agent spawn, doctor; positive
  control = one byte appended to `.claude/hooks/_compat.py`. Output `m-out.txt`, per-hook texts `m-logs/`.
- Runs 15:12-15:24 (m-out.txt..m-out4.txt; the first three probed the spawn with payloads `guard_agent_spawn`
  refused before the trust check -- wrong role, no run_in_background, no objective/output; m-out4.txt is
  the valid one, 15:21:26-15:23:56). Measured (m-out4.txt):
  - chain: both variants, all 10 registered Bash PreToolUse hooks rc 0, bash writes `x\n` / `{}\n`.
  - gate_dispatch spawn: base, invalid, emptyjson ALL the same refusal "no HARNESS_DISPATCH header" -- the
    trust refusal does NOT fire; control (hook byte): "specialist spawn refused: the installed enforcement
    bundle (fb2e65241c3e) is not the one this project trusts (bb0791094d65)." -> the check is live, blind to
    settings.json (`hashing.BUNDLE_SUBTREES` = hooks, kernel).
  - kit_trust_state: state stays `active` after both overwrites (silent); control -> `hooks_trust_required`.
  - SessionStart: the overwritten file registers NONE (`x`: unparseable; `{}`: []), so the next session starts
    no kit hook from it. Run anyway (as registered before): nothing mentions settings.json; session_status
    output loses its UNFILLED PROJECT DOCUMENTS paragraph (3272 -> 1946 chars; it asks registered gates, and
    gate_memory_complete no longer is) -- silently.
  - doctor (`scripts/harness.py doctor`, on demand only, rc 0): DETECTS -- `"spawn_veto": "no gate_dispatch
    registration fires on PreToolUse for Agent/Task — either it is not registered, its matcher excludes those
    tools, the file is missing, or hooks are disabled"`, `"state_write_protection.file": "no gate_write_scope
    registration fires for Edit/Write/MultiEdit"`. Nothing starts doctor automatically (session_status only
    names it as text).
  - `C:/Users/zenti/settings.json`, `.../docs/settings.json`: absent (no probe wrote into the real profile).

### 15:24-15:27 B3 (test + text), popd text
- New `tools/test_hooks_v2.py::test_the_scope_gate_gives_up_a_quoted_powershell_move_the_price_of_bug_0334`
  (x3 kits; PowerShell-tool payload; rows `Set-Location "~"`, `'~\docs'`, `"..\d*cs"`; gate rc 2 AND PowerShell
  writes at the landing dir, not `.claude`; arbiter HOME/USERPROFILE/HOMEDRIVE/HOMEPATH in tmp_path, checked by
  `(Get-Location).Path` after `Set-Location ~` BEFORE any write line). Rig (test file copied, md5 9679f6e1...):
  none 15:25:44-15:26:02 `3 passed`; no-fix 15:26:09-15:26:21 `1 failed` = all three rows "the gate answered
  rc 0", PowerShell column held.
- `_walked_to` docstring: the price has two sources (partly quoted word; PowerShell resolves tilde/wildcard in
  its provider after quote removal), names the new test. `_walk` docstring: popd on an EMPTY stack = no move,
  bash stays, the walk returns to line start -- one case of BUG-0335. Docstring-only diff (checked against the
  rig copy). Mirrored 15:27:30 md5 12bc5cd1... x3.

### 15:27 ONE stamp + checks
- 15:27:45 `bump_kit_version.py` -> 2026.09.28-2 x3; `--check` 15:27:50 unchanged -2 x3. `validate.py`
  15:28:10-15:28:13 all structural checks passed; `ruff check team-kits tools .claude/hooks/test_gates.py` all
  passed; `ruff check .` 1 error = the lead's `staging/generation-6/create_order_7_merge.py:55` F841 (foreign).
- Reading suites next (main tree, one at a time via run.py with budget): test_hooks_v2 -k "bug_0334 or walk or
  cd or tilde or position" (400 s), test_repo_hygiene -k pointer (400 s; the two docstring pointers).
- test_hooks_v2 selection 15:28:36-15:31:03 `81 passed` (78 before + the 3 new PowerShell nodes); test_repo_hygiene
  -k pointer 15:31:12-15:33:05 `6 passed`; test_hooks::test_shared_kit_files_identical 15:33:31-15:33:51 `1 passed`.
  After the runs `C:/Users/zenti/settings.json` absent.

### close
- No commit, no push, no full run, no BUG transition, no approval mint. BUG-0335 `limits` is the lead's to
  write through the kernel (measured sentence in the report).

## Rework 5 (TSK-0162) -- written as I go

### ~15:40 start
- Order: TSK-0162, close BUG-0335 (H229) in the kit gate x3. Scratch `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0162/`.
  Tree at start: stamp 2026.09.28-2 x3, `gate_write_scope.py` md5 12bc5cd1... x3 (= the pre-fix gate for this round).
- PLAN (FR-0084): `_walk` answers from a SET of landings (`_landings`): a move that can fail keeps its start as
  a landing (target no directory at gate time, pattern with 0 or 2+ hits, popd on an empty stack); an operand
  list this reader cannot account for (2+ operands, an option, `+N`, a word in front of the verb) is None;
  every landing is carried to the next move (`moves["also"]`), the protected one wins (`_chosen`).
  REJECTED: the verifier's minimal fix alone (add the stays candidate, keep ONE position): measured with bash
  (bashprobe.py) that `cd .github ; cd nope ; cd hooks ; echo x > note.txt` writes `.github/hooks/note.txt`,
  and a single position picks `.github/nope` (neither landing protected) -> `cd hooks` names `.github/nope/hooks`,
  a pass. Also rejected: None for every failing move (gate 1's `_enter` answer) -- `mkdir x ; cd x ; <write>`
  would be refused, which the order requires rc 0.
- bashprobe (git bash): `env cd ..` stays (writes .claude/settings.json); `command cd ..` moves (price row);
  `cd .. 2>/dev/null`, `cd -- ..`, `mkdir fresh ; cd fresh`, `cd docs ; cd ../data ; cd -`, `pushd .claude ;
  popd` all leave.
- Fix written in dev-team first (before the test -- red-first is re-derived below against the pre-fix gate
  bytes, TSK-0161/tree, md5 99afc605..., docstring-only different from 12bc5cd1...).

### 15:42-15:51 test, red-first, mutations (rig `TSK-0162/tree` = make_copy 15:42:41; swap.py / mutate.py / battery.py)
- `tools/test_hooks_v2.py::test_the_walk_takes_no_move_the_shell_may_not_perform_bug_0335` (x3 kits, lead caller,
  git bash arbiter in a fresh copy of the layout per row): the verifier's 12 forms + `env cd ..` + the carry row
  `cd .github ; cd nope ; cd hooks` + 6 counter-cases (real target, `mkdir fresh ; cd fresh`, `cd -` after a real
  move, pop onto a pushed entry, `&>/dev/null`, `2>/dev/null` outside, `cd -- ..`) + 2 price rows (`command cd ..`;
  `cd .. 2>/dev/null` out of `.claude` -- the tokeniser returns `2>` as `2 >`, a second operand to one reading).
- First after-run 15:43:22-15:44:08: 3 failed, only `cd .. 2>/dev/null` (my first cut read the `2` as a 2nd
  operand -> unknown). Changed: 2+ operands = the shell stays; a digit word before a redirection is ALSO read
  as a descriptor (`_operands` -> descriptors, `_landings` keeps both); row moved to the price list.
- BEFORE (pre-fix gate bytes) 15:46:45-15:47:05 `1 failed`: rc 0 on all 12 verifier forms + the carry row + the
  `2>/dev/null` price row (`env cd ..` was rc 2 before too -- the old walk read `cd` as the target, `.claude/cd`).
- AFTER 15:45:47-15:46:35 `3 passed`; after the `cd --` edit (bare `cd --` goes home) md5 81827825... x3:
  none 15:47:58-15:48:41 `3 passed`.
- Mutations (each red, -x, dev-team; restored md5 81827825...): no-stays-relative (5 forms + carry row),
  no-stays-absolute (`/nope-xyz`), no-carry (carry row), pop-empty-start-only (empty-stack popd),
  pop-keeps-previous (`cd -` after popd), many-takes-first (two operands + the price row), options-ignored
  (`popd +1`, `pushd -n`), prefix-ignored (`env cd ..`, and the `command cd` price row).
- Price row added (Windows only): `cd .claude ; cd "/c/.../docs"` -- the Windows reading `C:/c/...` does not
  exist, so the tree stays a landing; named in `_landings` with the other two prices. 16:02:26-16:03:29 `3 passed`.
- Real project chain (chain.py, scaffold from the rig tree, rig-only stamp -3 because the scaffold refuses an
  unstamped kit; main stays -2 until the ONE stamp) 15:58:16-16:01:23, out-chain.txt: B0 + all 12 verifier
  forms: gate_write_scope rc 2 (bash writes .claude/settings.json in each); counter-cases real target,
  `mkdir fresh ; cd fresh`, `cd -` after a real move: all 10 hooks rc 0, bash writes nothing under .claude.
- Every test whose source carries a directory move (`movers.py`, AST: 52 nodes in test_hooks_v2, test_hooks,
  test_stream_c_field) on the rig 16:04:38-16:10:28: 21 failed / 680 passed. 18 = copy artefacts
  (handover_guard not in the copy; bug_0323 scaffold refuses the rig tree, gate synced after the rig stamp).
  3 real, all a premise the fix makes visible: `test_every_directory_verb...` pop rows (bash stays on an empty
  stack -- rows changed to `pushd hooks ; <pop>` rc 0 plus `cd hooks ; <pop>` rc 2, `.github/hooks` created;
  red on the pre-fix gate 15:54:32), `test_actually_leaving...[cd /tmp]` (measured: Git Bash /tmp =
  C:/Users/zenti/AppData/Local/Temp, `C:/tmp` absent -> the hop now names `tmp_path.parent`),
  `test_the_working_directory_is_tracked_as_a_path[cd ../docs]` (docs absent -> created). Rerun 16:11:41-16:11:55
  `13 passed`.
- Gate-1 nodes on the rig: group + bug_0334 16:12:18-16:12:48 `9 passed`; 16-cell node 16:12:55-16:16:15 `1 passed`.

### 16:16 ONE stamp + checks
- Gate md5 9c3ffbad... x3. 16:16:26 `bump_kit_version.py` -> 2026.09.28-3 x3; `--check` unchanged -3 x3;
  `validate.py` all structural checks passed; `ruff check team-kits tools .claude/hooks/test_gates.py` all passed;
  `ruff check .` 1 error = the lead's `staging/generation-6/create_order_7_merge.py:55` F841 (foreign).
- Reading suites next, main tree, one at a time via run.py with a budget: test_hooks_v2 -k "bug_0334 or bug_0335
  or walk or cd or tilde or position" (600 s), test_hooks -k "directory or walk or cd or pushd or popd or position
  or tilde" (400 s), test_stream_c_field -k bug_0323 (300 s), test_repo_hygiene -k pointer (400 s), gate-1 nodes
  (16-cell 560 s; group + bug_0334 300 s), the 52 movers nodes (900 s), test_shared_kit_files_identical.
- test_hooks_v2 selection 16:16:40-16:18:27 `84 passed`; test_hooks selection 16:18:33-16:19:27 `39 passed`;
  stream_c_field bug_0323 16:19:27-16:19:47 `3 passed`; repo_hygiene pointer 16:19:53-16:21:31 `6 passed`;
  gate-1 group + bug_0334 16:21:32-16:21:58 `9 passed`; gate-1 16-cell 16:22:04-16:25:20 `1 passed`; 52 movers
  nodes + test_shared_kit_files_identical 16:25:43-16:31:33 `702 passed`. `--check` after: unchanged -3 x3.

### close
- No commit, no push, no full run, no BUG transition, no approval mint. The H229 row in docs/POST_V2_WISHLIST.md
  still says OPEN: it mirrors the BUG's status, which is the lead's transition.
