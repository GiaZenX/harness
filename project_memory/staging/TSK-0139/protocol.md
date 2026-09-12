# TSK-0139 -- PR-0012 AC-3: die echten Restfehler

Base: main @ fd7e2fa. One writer: harness-implementer (opus/high).
Clock read by the shell at each section head (DEC-0094 (5)).

## Vorgefunden (for a successor)

- `git status` at start: only kernel writes under `project_memory/generated/`,
  `staging/generation-6-streams.md`, `tasks/active/TSK-0138.yaml`, `tasks/active/TSK-0139.yaml`,
  untracked `evidence/EVD-0283.yaml`. Nothing of mine yet.
- Scratch: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0139/`.

## 0. Bestandsaufnahme (AST scan, not a grep)

`C:/Users/zenti/AppData/Local/Temp/claude/scan_names.py` parses every `tools/test_*.py`,
walks the test functions and asks per bug id whether it stands in the docstring's FIRST
paragraph or in a parametrize/decorator (DEC-0100 (3), H195/BUG-0279). Result on fd7e2fa:

- NAMED (closable route, node re-run needed): BUG-0016, 0017, 0022, 0023, 0026, 0027, 0058,
  0074, 0075, 0076, 0079, 0087, 0092
- MENTIONED ONLY LATER IN THE DOCSTRING (not a naming per DEC-0100): BUG-0044, BUG-0050
- NOT NAMED ANYWHERE: BUG-0010, 0014, 0031, 0034, 0037, 0046, 0052, 0053, 0054, 0055, 0056,
  0057, 0062, 0067, 0077, 0080, 0081, 0082

## 1. Vorgefunden II -- drei ROTE Knoten auf fd7e2fa, die NICHT in AC-3 stehen

Measured 19:07 in isolation, one node per run, so they are not a load artefact:

| node | arbiter's line |
|---|---|
| `tools/test_hooks_v2.py::test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it` | `close_measured_pass.py died on its way in: ... FileNotFoundError: ...project_memory/staging/TSK-0131/survey-table.md` -- the tool TSK-0138 added runs its `plan()` on import-probe defaults |
| `tools/test_hooks_v2.py::test_every_approval_refusal_the_hook_can_surface_speaks_to_the_user` | `ApprovalError without a sentence for the user: [('_assert_the_list_covers', 1524), (…, 1530), (…, 1535)]` -- TSK-0138's batch coverage check raises three bare `ApprovalError`s |
| `tools/test_hooks_v2.py::test_the_lead_of_a_scaffolded_project_is_not_read_as_its_own_subagent` | `the chain let the lead through and never spent the lease: [team-kit gate_dispatch] … the lease for TSK-0001 says rung opus but the spawn names no model` |

All three are in the delivery of TSK-0138 (the batch mint) and none is on this order's list.
They are handed to the lead, not fixed here: fixing another order's delivery while its
verification is the lead's business would be DEC-0094 (2). Reported, with the lines above.

## 2. BUG-0052 -- the suite writes into canonical state

- Mechanism, CORRECTED after the measurement below: `_audit.record` resolves its sink through
  `_root.find_repo_root`, which answers `$CLAUDE_PROJECT_DIR` first and OTHERWISE WALKS UP from the
  payload's `cwd` or `os.getcwd()`. Both doors lead here. The one that was actually open is the
  second: a hook the suite starts inherits the suite's own working directory, which IS the
  repository, and the walk-up then finds the repository's `project_memory/`. An in-process call
  (`hygiene._check_docker` in the case-preservation test) takes the same door with no subprocess at
  all. The first draft of this section named only the environment; the eight trust-hook reds below
  are what corrected it.
- Measured on fd7e2fa, one `tools/test_hooks_v2.py` run (18:55:05-19:06:31):
  `project_memory/.audit/hook_events.jsonl` 697 -> 699 lines, md5 `09b9875a0d9ff3…` ->
  `92d2f0d71343ba…`; the two added records are `gate_needs` "could not be read or parsed"
  (18:55:14, fixture `test_a_gate_that_drains_stdin_itself_breaks_the_chain_fail_closed`, which
  calls `subprocess.run` with no env) and `gate_shell_hygiene` "'OtherDB' belongs to compose
  project 'neighbour-stack'" (19:06:31).
- Change: `tools/conftest.py` -- `AMBIENT_PROJECT_DIR` under `.pytest_cache/ambient-project/`,
  `os.environ["CLAUDE_PROJECT_DIR"]` set to it beside the existing pycache redirect. The
  environment is the one place every child inherits from; a list of fixtures to repair is the
  defect's own shape.
- Test: `tools/test_repo_hygiene.py::test_no_hook_started_by_this_suite_can_write_this_repos_audit_log`
- RED (rig case `case_bug0052.py`, redirect turned into a `setdefault` = the fd7e2fa reading):
  `E AssertionError: a hook this suite started appended to the repo's canonical audit log (BUG-0052)`
- AC-2 MEASURED OVER A WHOLE RUN: `tools/test_hooks_v2.py` + `tools/test_hooks.py`, 3166 passed in
  22:40 (20:00-20:22). The repo's log is byte-identical before and after -- md5
  `92d2f0d71343ba230d7455c5a6091c8e`, 699 lines, both times -- while the fixture events, the
  `'OtherDB' belongs to compose project 'neighbour-stack'` line among them, stand in
  `.pytest_cache/ambient-project/project_memory/.audit/hook_events.jsonl` (mtime 20:10).
- THE PRICE, measured and paid: the redirect makes the ambient variable non-EMPTY, and
  `find_repo_root` prefers it over the payload's `cwd`. Eight trust-hook tests went red on it
  because `_run_trust_hook` started the shipped hook with no environment at all. That helper now
  names `CLAUDE_PROJECT_DIR` the way `run_hook_process` names it for every other hook this suite
  starts -- which is the contract, not a repair of a special case. 8 passed, 33.25 s.

## 3. BUG-0053 -- the compose foreign-project rule

- Mechanism: `_named_projects` read ONE flag pair and split values on `=` only.
- Measured on the SHIPPED gate as real hook processes (probe `probe_bug0053.py`), after the fix:
  seven refusals rc 2 (`-p other`, `--project-name other`, `--project-name=other`, `-pother`,
  `COMPOSE_PROJECT_NAME=other` prefix, `-f ../other/docker-compose.yml`,
  `--project-directory ../other`) and nine counter-probes rc 0, among them
  `docker compose -f docker/docker-compose.yml down` and `docker rm -f mycontainer`.
- Change: `team-kits/*/hooks/gate_shell_hygiene.py` -- `_option_values` (POSIX option syntax, one
  reader for all four spellings), `_environment_project` (the segment's own assignment), `_inside`,
  `_foreign_designations` (compose's documented precedence). `_destructive_docker_calls` now hands
  back the tokens BEFORE the verb and the segment instead of the whole argument list, because
  compose reuses `-f` across the two positions.
- Test: `tools/test_hooks_v2.py::test_every_way_a_line_can_point_compose_at_a_foreign_project_is_refused`
  (four rows = the four sources); counter-battery extended in
  `test_ordinary_docker_work_stays_open` by the four lines the widening could break.
- Caller swept (DEC-0080 rule 2 / DEC-0094 (7)): `_destructive_docker_calls` has exactly one
  caller outside the gate, `tools/test_hooks_v2.py:11744`, and its tuple unpacking was corrected.
- RED (rig case `case_bug0053.py`, the b7f282e enumeration restored in all three kit copies):
  `E AssertionError: ('the attached short form POSIX allows', 'docker compose -pother down', '')`
  / `assert 0 == 2` -- all four rows rc 0.
- Mirrored: three copies md5 `4c2487517be92d838a88f95902e7083e`.

## 4. BUG-0082 -- a metacharacter hides a protected path from the kit gate

- Mechanism: `_names` compares the LITERAL token, so a word the shell expands is never compared.
- Measured (probe `probe_bug0082.py`, shipped kit gate as a real process, scaffolded proxy):
  before, `python .claude/hooks/gate_approval.py` rc 2 and `python .cla*de/...` rc 0, likewise
  `cp .cla*de/... /tmp/x.py` and `rm -f .cla*de/...`; after, all rc 2. TWO ROWS THE ROUND ADDED
  BESIDE THE ITEM: `cp evil.py .cla*de/hooks/gate_new.py` (a leaf that does not exist yet, which a
  whole-word `glob` answers nothing about) and `echo x > project_mem*ry/bugs/active/BUG-9999.yaml`
  (the state-capture carve-out asked the same literal question one level down) -- both rc 0 before,
  rc 2 after.
- Change: `team-kits/*/hooks/gate_write_scope.py` -- `_glob_readings` (per COMPONENT, relative
  answers), `_names_expanded`, wired into both branches and into the `captures_out` carve-out.
  The answer is the shell's own expansion against the same filesystem, so the over-refusal price
  is zero: `cp src/*.js dist/`, `rm -rf dist/*`, `pytest tests/test_*.py`, `npm run build` and
  `cat .cla*de/hooks/gate_approval.py` measured rc 0 before and after.
- Tests: `tools/test_hooks_v2.py::test_a_metacharacter_does_not_hide_a_protected_path_from_the_kit_gate`
  (5 rows) and its counter-end `::test_ordinary_work_with_a_glob_stays_open` (5 rows).
- RED (`case_bug0082.py`, `_names` alone restored in all three kits):
  `E AssertionError: ('python .cla*de/hooks/gate_approval.py < payload.json', '', '') / assert 0 == 2`
  -- and the counter-end stayed GREEN in the same mutated copy (rc 0), which is what shows it
  measures the price and not the fix.
- NOT closed, named: a word whose value comes from the shell's own state (`$VAR`, `${VAR}`,
  `$(cmd)`, a backtick) answers to no filesystem question. Said in `_glob_readings` and in the test.

## 5. BUG-0037 -- prose claiming an arrow the code has

- Mechanism: the module said "nothing here leads OUT of `hooks_trust_required`" while
  `transition(hooks_trust_required, matching hash)` returns `('active', None)`.
- Decision taken and recorded here (a DEC is the lead's to mint): the exit is RIGHT and is NAMED,
  not refused. The state records that the INSTALLED bundle is not the RECORDED one; only
  `write_kit_state.py` (the scaffold) writes the record, so a hash equal to it again IS the
  reviewed bundle. Nothing an agent can do makes an arbitrary bundle match a record it cannot write.
- Change: `team-kits/*/hooks/kit_trust_state.py` header -- the transition table gained the arrow,
  the paragraph says what it used to claim and why the exit is not a leak, and it NAMES its test.
- Test: `tools/test_report.py::test_the_trust_state_exits_on_a_bundle_that_matches_the_record_again`
  (all four state/hash combinations, EXECUTED in all three shipped copies via `_shipped_transitions`).
- RED (`case_bug0037.py`, `transition` made to answer `None` for that record):
  `E AssertionError: ... At index 2 diff: None != 'active'`
- Mirrored: three copies md5 `76d672053aab37565de89269d0b831b8` (before the stamp).

## 6. BUG-0031 -- the Codex entry gate routed on a MENTION

- Mechanism: `user/codex/AGENTS.md` step 1 read "contains the marker `agents-and-skills:team-kit`".
- Change: the rule is anchored to the shim FORM on line 1, the same anchor DEC-0039 gave the
  Claude gate; step 2's `./CLAUDE.md` clause moved with it.
- Test: `tools/test_handover_marker.py::test_an_entry_file_names_the_marker_only_as_the_whole_shim`
  -- parametrized over BOTH entry files, so neither provider's half can drift alone. The property
  is structural and needs no vocabulary: in a file that DECIDES handover, every occurrence of the
  marker stands inside the complete shim.
- RED (`case_bug0031.py`, the `contains` rule restored): the `[codex]` row fails with
  `E AssertionError: ...user/codex/AGENTS.md names the marker outside the shim form` while the
  `[claude]` row stays green -- the pair discriminates.

## 7. BUG-0014 -- a red suite nobody noticed

- AC-1 re-measured: `.claude/hooks/test_gates.py::test_the_measurement_sandbox_leaves_a_child_shell_no_directory_word_that_names_another_tree`
  PASSES on this host today, 1 passed in 28.01 s (19:30:18-19:30:48). The 2026-08-09 red is gone;
  WHY the host could not reproduce the accident then is not re-measurable now and is not claimed.
- AC-3 built: `tools/test_repo_hygiene.py::test_a_suite_the_default_run_does_not_collect_is_named_with_its_own_run_command`
  -- walks the tree for every `test_*.py` OUTSIDE `tools/` and demands a `pytest` line in
  `CLAUDE.md` that names it. A second such suite added tomorrow is covered the day it ships.
  What it does NOT claim: it cannot make anybody RUN the suite, and it says so.
- RED (`case_bug0014.py`, the run command generalised in a copy of CLAUDE.md):
  `E AssertionError: CLAUDE.md carries no pytest line that names these suites ... ['.claude/hooks/test_gates.py']`

## 8. BUG-0034 -- gate 3 asked for the WORD `commit`

- Already built (TSK-0056) and fully measured; what was missing was a test NAMING the bug.
- Change: the docstring of `.claude/hooks/test_gates.py::test_gate3_refuses_a_line_that_records_history_even_with_a_verdict`
  now opens with BUG-0034 and the two measured H2 chains. 20 rows, real hook process, run 17.88 s.
- RED (`case_bug0034.py`, `AUTHORS_A_COMMIT` cut back to `("commit",)` in a COPY -- the gate is
  forbidden scope in the repository, so the copy is the only place the defect may be restored):
  `E AssertionError: a line that can record history ran under a verdict about the tree BEFORE it / assert 0 == 2`

## 9. BUG-0044 -- a preset nobody chose

- The EXPECTATION MOVED and this is the finding, not a side note: DEC-0088/DEC-0091 took the preset
  question out of the light-form interview. So "the interview asks" is no longer the property; what
  must hold is that nothing pretends to know the answer -- the entry gate writes the kit's SMALLEST
  preset (derived from `presets.yaml`) and names `set-preset` for the later change (BUG-0041).
- Test: `tools/test_hooks.py::test_the_preset_an_entry_gate_writes_is_the_smallest_one_and_never_a_chosen_looking_value`
  -- per BLOCK (not per file), and only inside CODE SPANS, because `team`, `core` and `full` are
  ordinary English words and a word-boundary scan failed on "a good starting team".
- RED (`case_bug0044.py`, `preset: duo` put back in the writing block):
  `E AssertionError: user/claude/CLAUDE.md hands the initializer a preset that is not its kit's smallest: ['duo']`

## 10. BUG-0081 -- the first work-branch push

- Mechanism: `gate_git` judges every push like a delivery, so it demanded the `acceptance` verdict
  before the push that CREATES the acceptance surface (a Shopify preview theme). The live PM
  refused to fake it, refused to edit the gate, and asked the USER to run the push.
- Decision taken, measuring: the OCCASION was wrong, not the demand. A push of a branch that NAMES
  its item publishes unfinished work; delivery is the merge. NOTHING is packaging-specific -- a
  `packaging.method` list would have been the next defect, and a theme preview, a store build and a
  staging deployment are the same shape.
- Change: `team-kits/{dev,research}-team/hooks/gate_git.py` -- `OUTSTANDING_UNTIL_PUBLISHED`,
  `_publishes_a_work_branch` (every invocation of the line must be a push AND the branch must name
  an item), `_say_what_stays_outstanding` (a NOTE on stderr plus `_kernel.record_note`, exit 0).
- Tests (all in `tools/test_hooks.py`): `::test_the_first_work_branch_push_is_not_refused_for_a_verdict_the_push_has_to_produce`,
  `::test_the_merge_still_refuses_the_verdict_a_push_may_owe` (AC-2),
  `::test_a_line_that_also_merges_keeps_the_delivery_demand` (2 rows),
  `::test_a_work_branch_push_still_owes_every_verdict_that_can_be_produced_first` (2 rows),
  `::test_a_work_branch_push_with_no_verdict_at_all_is_still_refused`,
  `::test_a_failing_verdict_closes_a_work_branch_push_too`,
  `::test_the_kind_outstanding_at_a_work_branch_push_is_a_real_qa_kind` (the enumeration's tripwire,
  both ends). 9 passed.
- AC-3 is section 13 (the shared hand duty).
- NOT closed, named: AC-2's second half -- a marker the VALIDATOR and the user's overview can see.
  A PreToolUse gate may not write state, so the outstanding verdict is said on stderr and in the
  audit log and nowhere else. A stored field with a producer is the BUG-0054 class of work and is
  handed back rather than implied.

## 11. BUG-0054 -- architecture_refs had no producer

- Mechanism: the delivery manifest hashes `architecture_refs`; `freeze_architecture` wrote only the
  companion, so a second freeze left the approval in force.
- Change: `team-kits/kernel/staging.py` -- `_root_of` (the root is the `derives_from` entry whose
  TYPE is in `ROOT_TYPE_BY_KIT`, the map the plan approval and the scaffold already read) and the
  refs append inside the same lock hold, through `field_elements` (BUG-0038's class).
- Tests: `tools/test_staging_cli.py::test_freezing_the_architecture_again_devalues_the_delivery_approval`
  (with the design-freeze-shaped control IN the test) and
  `::test_an_architecture_that_hangs_off_no_root_writes_no_refs`.
- RED (`case_bug0054.py`, the companion written and the root only READ, which is the shipped shape):
  `E KeyError: 'architecture_refs'` at `assert first["root"]["architecture_refs"] == [expected]`
- NOT closed, named (AC-2): `planned_tasks`, `risks`, `system_requirements`, `delivered_commit` and
  `evidence_refs` are hashed and still have no writer. They are a different question -- each needs
  a command, not a hook into an existing freeze -- and they stay as the item's own residue.

## 12. BUG-0057 -- a capability claimed for a provider nobody measured

- Mechanism: `_wired_hooks` reads the three `.claude` layers, and `spawn_veto` answered `verified`
  out of them for a project that also configures Codex.
- Change: `team-kits/kernel/report.py` -- `PROVIDER_MARKERS` (per provider: the marker that declares
  it configured, and whether this reader opens its registrations) plus `_unmeasured_providers`; the
  verdict is `verified` only when nothing is unmeasured, and the REASON names the provider.
- Tests: `tools/test_report.py::test_the_spawn_veto_is_not_claimed_for_a_provider_this_report_cannot_read`
  (both directions in one repository, one `.codex` directory apart) and
  `::test_every_provider_marker_says_whether_this_report_reads_its_registrations` (the tripwire).
- RED (`case_bug0057.py`, the verdict made to read `spawn` alone again):
  `E AssertionError: ... assert 'verified' == 'unverified'`

## 13. BUG-0080 (+ BUG-0081 AC-3, BUG-0046) -- the user's hand and the specialist's voice

- BUG-0080 / BUG-0081 AC-3: ONE shared paragraph, byte-identical in all three constitutions, placed
  in front of the AND-BOOK-IT gap-route block that already stood there -- so
  `tools/test_role_contracts.py::test_a_paragraph_the_constitutions_share_is_one_text` holds the
  three copies without a new mechanism, and
  `::test_every_constitution_forbids_handing_the_user_a_line_around_a_gate` holds presence and both
  named cases. RED (`case_bug0080.py`, the paragraph cut from the office copy):
  `E AssertionError: team-kits\office-team\constitution\AGENTS.md carries 0 statement(s) of the hand duty`
- BUG-0046: the kit-side half was fixed by TSK-0074; what was missing was a test.
  `::test_no_constitution_promises_that_a_specialists_voice_stays_out_of_the_users_view` finds the
  block by its SUBJECT (the dispatch flag) and asserts the measurement, its uncovered half, and the
  absence of the promise. RED (`case_bug0046.py`, "jargon stays between agents." restored in the
  research copy): `E AssertionError: ... nothing stops the lead promising the user an assurance the kit does not build (BUG-0046)`
- BUG-0080's OTHER half is NOT closed and is named: the freeze-repair path still has no
  in-apparatus writer for its own input (a staged copy of an already-frozen artifact). The route
  that would close it is a kernel command that re-reads the bytes it already holds; that is a new
  command, not a defect fix, and it is handed back.

## 14. BUG-0077 -- a circular ordering

- Mechanism: the PM skill required the approved WIREFRAME to be part of the scope manifest, while
  `gate_dispatch` refused the designer spawn until the scope approval existed. The manifest has no
  wireframe field at all (`approvals._SCOPE_FIELDS`), so the demand was doubly unsatisfiable.
- Change: `team-kits/dev-team/skills/project-manager/SKILL.md` step 4 -- the order is scope approval
  FIRST, wireframe in step 5 as the delivery work it is, bound by the `scope_apr_ref` the freeze
  records. The open decision about a manifest field is named (BUG-0055) instead of assumed.
- Test: `tools/test_role_contracts.py::test_no_kit_text_puts_an_artifact_into_the_scope_manifest_the_kernel_does_not_hash`
  -- the kernel is the authority; a sentence that DENIES the membership is the fix and is skipped.
- RED (`case_bug0077.py`, the sentence restored):
  `E AssertionError: a kit text puts an artifact into the scope manifest that the kernel does not hash (BUG-0077; ...)`

## 15. BUG-0067 -- a run seeded the workshop's own state

- Mechanism: `init_project_memory.sh/.ps1` seed the WORKING DIRECTORY, so a measuring run started in
  the checkout that ships the kits seeded that checkout -- eight office template documents and
  `procedures/` are still in this repo's `project_memory/` (measured today by `ls`).
- Change: both scripts refuse when the working directory carries a kit's own
  `*/templates/project_memory`. A property of the tree, not a path: a repository that SHIPS the
  templates is their source and never a consumer.
- Tests: `tools/test_hooks.py::test_the_seeding_script_refuses_the_tree_that_ships_the_templates`
  (both directions, and NOT skipped on Windows -- the skip guard was narrowed to "no bash at all",
  and the bash EXECUTABLE is resolved with `shutil.which` because a bare `bash` finds WSL here while
  `which` finds Git Bash, and the two spell a Windows path differently) and
  `::test_both_seeding_scripts_carry_the_same_refusal`.
- RED (`case_bug0067.py`, the refusal cut out of the .sh):
  `E AssertionError: [ok] project_memory/ ready (1 created, 0 already present) from kit 'dev-team'. / assert 0 != 0`
- NOT closed (AC-2): the eight leftover files are NOT removed here. `project_memory/` has one
  writer and this order is not it -- the removal is the lead's through the kernel or the user's
  from a shell outside the session.

## 16. BUG-0010 -- LEASED without a lease

- All three halves were already built (DEC-0038) and tested; the naming was missing. The docstring
  of `tools/test_kernel.py::test_a_bare_transition_cannot_mint_leased` now opens with BUG-0010 and
  names its two siblings (the dispatch route still reaching LEASED, and the sweep REPORTING a
  LEASED task whose lease vanished -- the half the item asked for by name). 3 passed.

## 17. BUG-0017 -- measured by design

- `tools/provider_observations.json` -> `headless_pm_stop_point`: two real `claude -p` runs, ZERO
  AskUserQuestion blocks, `stop_reason: end_turn` in both. The PM does not stop AT the approval
  gate; it never reaches one. Nothing to repair.
- Docs: `docs/POST_V2_WISHLIST.md` section 10 gained the second correction, and it NAMES its test
  rather than restating the numbers.
- Test: `tools/test_report.py::test_the_headless_stop_point_is_measured_and_is_not_the_approval_gate`
  -- the record is PARSED, not the prose that cites it.

## 18. The two that are HANDED BACK, with mechanism and bound

These are not "known, comes later": each says why it is not closable by this order and what limits
it meanwhile. Both belong in the user's exception batch or in a decision the lead mints.

### BUG-0055 -- the scope manifest has no wireframe field

- **Mechanism.** `approvals._SCOPE_FIELDS` carries eight fields and no wireframe reference, so a
  re-frozen wireframe devalues nothing (E17) and nothing can check that a UI scope names one (E18).
- **Why this order cannot close it.** The item's own AC-1 asks for a DECISION first, and it is the
  right order: widening `_SCOPE_FIELDS` changes every stored manifest hash, which kills every live
  approval in every project that updates -- a spec decision with a migration attached, not an
  implementation detail (the constant's own comment says so). A DEC is a `project_memory` write and
  this order's forbidden scope excludes it; the builder can measure, not decide.
- **What bounds it today.** The wireframe is not unbound: `freeze_wireframe` records the
  `scope_apr_ref` it was drawn under, so every frozen wireframe carries the approval it belongs to
  even though the approval does not carry the wireframe. What is lost is only the automatic
  devaluation when a wireframe is re-frozen -- the same signal `design_refs` gives. And the FALSE
  claim that made the gap dangerous is gone (section 14): no kit text says the manifest holds one.

### BUG-0056 -- a recorded V1 file outside the state tree is writable

- **Mechanism.** `gate_write_scope` protects the PLACE. `migrate.search_coverage` -- the one record
  of what holds V1 material -- walks the STATE ROOT by construction and gives a verdict per file
  under it; there is no record at all of a V1 file lying outside `project_memory/`. So AC-1
  ("refused wherever it lies") and AC-2 ("derived from the migration's own record, not a path list")
  cannot both be met today: the record the derivation needs is not written by anything.
- **Why this order cannot close it.** Closing it honestly means making the migration RECORD the
  files it read outside the state root, then teaching a gate to open that record on every shell
  command -- a new producer plus a per-command read, which is a feature with a cost decision behind
  it, not a defect fix. Building the gate half against a path list is what AC-2 forbids.
- **What bounds it today.** A V1 file outside the state tree holds no LIVE state: the kernel reads
  `project_memory/` and nothing else, every gate decides on items in it, and every write INTO it is
  refused for every caller. The exposure is a stale copy being edited and later mistaken for state
  by a human -- not a gate being bypassed. Measured neighbours that already refuse: the legacy path
  UNDER the state root and the monolith spelling directly at it are both rc 2.

## 19. What this order did NOT touch, and why

- `.claude/hooks/gate_*.py` and `_harness.py` are forbidden scope. No defect of that class needed a
  patch this round: BUG-0012 and BUG-0020 are measured closed in the survey and BUG-0034 is closed
  in the shipped gate (section 8), so there is no patch to hand the user for a shell outside
  Claude Code. The only change under `.claude/` is a DOCSTRING in `test_gates.py`, which the order's
  allowed scope names explicitly.
- `team-kits/*/settings/settings.json` is forbidden scope, which is why BUG-0062 is closed on the
  PROPERTY (which entries owe a window) and not by adding timeouts.
- `project_memory/**` outside this task's staging directory: no item status was moved, no EVD was
  minted, nothing was archived. The batch route is the lead's.

## 20. The two batch lists for the lead

### (a) Closable by the verification batch -- a passing test NAMES the bug

Every id below has at least one test whose docstring FIRST paragraph names it, re-run on this tree.
The EVD per bug is the lead's to record; this order minted nothing.

Fixed this round (red-first measured, sections 2-17):
BUG-0014, BUG-0031, BUG-0034, BUG-0037, BUG-0044, BUG-0046, BUG-0052, BUG-0053, BUG-0054,
BUG-0057, BUG-0067, BUG-0077, BUG-0080, BUG-0081, BUG-0082

Measured already fixed, naming test re-run on this tree (19:52:48 and 19:53:09 batches, plus the
per-bug runs in the sections above):
BUG-0010, BUG-0016, BUG-0017, BUG-0022, BUG-0023, BUG-0026, BUG-0027, BUG-0050, BUG-0058,
BUG-0062, BUG-0074, BUG-0075, BUG-0076, BUG-0079, BUG-0087, BUG-0092

### (b) For the user's ACCEPTED_EXCEPTION batch

BUG-0055 (decision owed first; bound: the freeze records its `scope_apr_ref`, and the false claim
about the manifest is gone) and BUG-0056 (no record of V1 material outside the state root exists;
bound: nothing outside `project_memory/` is live state and every write into it is refused).

## 21. Vorgefunden, for a successor

If this round is cut short, the disk holds: every change described above already applied, the kits
stamped ONCE (2026.09.11-18, 19:58:22), `tools/lead_package_sizes.json` and the disposition journal
updated for the +805 bytes per kit, `tools/validate.py` green at 19:58:53, `ruff` green over
`tools team-kits .claude`. What is NOT done is named in section 22.

## 22. The table (one line per bug of the GROWN list)

| id | mechanism (one sentence) | what changed | red-first row (the arbiter's line) | reading suites | EVD |
|---|---|---|---|---|---|
| BUG-0010 | `transition` checked the automaton, not whether a lease backed the status | naming only: `tools/test_kernel.py` docstring of `test_a_bare_transition_cannot_mint_leased` | already built (DEC-0038); the three nodes pass, 3 passed 1.73 s | test_kernel | lead |
| BUG-0014 | the gate suite is not collected by `pytest tools/` and nothing tied it to a command | `tools/test_repo_hygiene.py` +`test_a_suite_the_default_run_does_not_collect_is_named_with_its_own_run_command` | `CLAUDE.md carries no pytest line that names these suites ... ['.claude/hooks/test_gates.py']` | test_repo_hygiene, the gate node itself (28.01 s, pass) | lead |
| BUG-0016 | the entry session kept writing after the restart plea | naming only: `tools/test_hooks.py` docstring of `test_handover_guard_blocks_product_code_write_under_marker` | already built (DEC-0032, `user/claude/hooks/handover_guard.py`); 95 handover-guard tests pass | test_hooks | lead |
| BUG-0017 | the mint chain is not broken headless -- the PM never reaches a gate | `docs/POST_V2_WISHLIST.md` §10 + `tools/test_report.py::test_the_headless_stop_point_is_measured_and_is_not_the_approval_gate` | measured by design, no fix | test_report | lead |
| BUG-0022 | a change to something built ran as PR replacement | already built; naming test passes | n/a (already fixed) | test_hooks | lead |
| BUG-0023 | `create-task` took `expected_outputs: []` | already built; two naming tests pass | n/a (already fixed) | test_report, test_state | lead |
| BUG-0026 | `record_deposit_of` dropped the digest | already built; naming test passes | n/a (already fixed) | test_migrate | lead |
| BUG-0027 | the printed READY line dropped the plan's flags | already built; naming test passes | n/a (already fixed) | test_migrate | lead |
| BUG-0031 | the Codex entry gate routed handover on a bare occurrence of the marker | `user/codex/AGENTS.md` step 1+2 anchored to the shim form; `tools/test_handover_marker.py` +pair test | `user/codex/AGENTS.md names the marker outside the shim form` (only the `[codex]` row) | test_handover_marker (16 passed) | lead |
| BUG-0034 | gate 3 asked `runs('commit')`, so merge/revert recorded history unjudged | naming: `.claude/hooks/test_gates.py` docstring of `test_gate3_refuses_a_line_that_records_history_even_with_a_verdict` | `a line that can record history ran under a verdict about the tree BEFORE it / assert 0 == 2` | that node (20 passed, 17.88 s) | lead |
| BUG-0037 | the module denied an exit its own `transition` takes | `team-kits/*/hooks/kit_trust_state.py` header; `tools/test_report.py` +`test_the_trust_state_exits_on_a_bundle_that_matches_the_record_again` | `At index 2 diff: None != 'active'` | test_report | lead |
| BUG-0044 | a preset nobody chose was written as if confirmed | `tools/test_hooks.py` +`test_the_preset_an_entry_gate_writes_is_the_smallest_one_and_never_a_chosen_looking_value` | `hands the initializer a preset that is not its kit's smallest: ['duo']` | test_hooks | lead |
| BUG-0046 | the kits ASSURED that jargon stays between agents | `tools/test_role_contracts.py` +`test_no_constitution_promises_that_a_specialists_voice_stays_out_of_the_users_view` | `nothing stops the lead promising the user an assurance the kit does not build (BUG-0046)` | test_role_contracts | lead |
| BUG-0050 | the no-technical-questions property is hook-carried and had holes | naming: `tools/test_hooks.py` docstring of `test_the_two_escape_classes_warn_and_product_questions_stay_quiet` | already built (TSK-0075); 7 passed | test_hooks | lead |
| BUG-0052 | `_audit` resolves its sink through `$CLAUDE_PROJECT_DIR`, which a suite child inherits | `tools/conftest.py` ambient redirect; `tools/test_repo_hygiene.py` +naming test | `a hook this suite started appended to the repo's canonical audit log (BUG-0052)` | test_repo_hygiene, test_hooks_v2 | lead |
| BUG-0053 | the compose rule enumerated one flag pair and split values on `=` only | `team-kits/*/hooks/gate_shell_hygiene.py` `_option_values` / `_environment_project` / `_inside` / `_foreign_designations`; `tools/test_hooks_v2.py` +4-row test, counter-battery +4 | `('the attached short form POSIX allows', 'docker compose -pother down', '') / assert 0 == 2` | test_hooks_v2 (42 passed on the docker selection) | lead |
| BUG-0054 | `architecture_refs` is hashed and had no writer | `team-kits/kernel/staging.py` `_root_of` + the refs append; `tools/test_staging_cli.py` +2 tests | `KeyError: 'architecture_refs'` | test_staging_cli, test_kernel, test_hooks | lead |
| BUG-0055 | the scope manifest has no wireframe field | NOT CLOSED -- decision owed (section 18) | n/a | n/a | exception batch |
| BUG-0056 | protected is the PLACE, and no record of V1 material outside the state root exists | NOT CLOSED -- the record the derivation needs has no producer (section 18) | n/a | n/a | exception batch |
| BUG-0057 | `spawn_veto` answered `verified` out of the Claude layers for a claude+codex project | `team-kits/kernel/report.py` `PROVIDER_MARKERS` + `_unmeasured_providers`; `tools/test_report.py` +2 tests | `assert 'verified' == 'unverified'` | test_report | lead |
| BUG-0058 | an idle dispatched specialist went unnoticed | already built; two naming tests pass | n/a (already fixed) | test_approvals_dispatch, test_hooks_v2 | lead |
| BUG-0062 | 5 of 28 office hook entries carried a timeout | naming: `tools/test_hooks.py` docstring of `test_a_registration_names_a_window_exactly_when_its_gate_can_outlive_the_default`; re-measured dev 1/31, office 0/30, research 1/28 and every absence right under the rule | already built | test_hooks | lead |
| BUG-0067 | the seeding script seeds the working directory | `team-kits/init_project_memory.{sh,ps1}` refuse a tree that ships kit templates; `tools/test_hooks.py` +2 tests | `[ok] project_memory/ ready (1 created, 0 already present) ... / assert 0 != 0` | test_hooks | lead |
| BUG-0074 | `freeze-*` emptied the task's whole staging folder | already built; naming test passes | n/a (already fixed) | test_staging_cli | lead |
| BUG-0075 | document-owning roles were not routed onto the document write route | already built; two naming tests pass | n/a (already fixed) | test_role_contracts | lead |
| BUG-0076 | a design draft reached the user unrendered | already built; naming test passes | n/a (already fixed) | test_role_contracts, test_hooks | lead |
| BUG-0077 | the PM skill and `gate_dispatch` demanded an impossible order | `team-kits/dev-team/skills/project-manager/SKILL.md` step 4; `tools/test_role_contracts.py` +derived test | `a kit text puts an artifact into the scope manifest that the kernel does not hash (BUG-0077; ...)` | test_role_contracts | lead |
| BUG-0079 | the document remedy the kernel prints was refused by the code printing it | already built; three naming tests pass | n/a (already fixed) | test_office_package | lead |
| BUG-0080 | the freeze repair sent the user to the terminal as the copy machine | the shared hand duty in three constitutions; `tools/test_role_contracts.py` +presence test (the WRITER half stays open, section 13) | `office-team\constitution\AGENTS.md carries 0 statement(s) of the hand duty` | test_role_contracts | lead |
| BUG-0081 | a work-branch push was judged as a delivery | `team-kits/{dev,research}-team/hooks/gate_git.py`; `tools/test_hooks.py` +7 tests (9 rows) | `('python .cla*de/...')` n/a -- see below | test_hooks | lead |
| BUG-0082 | the kit gate compared the literal token, not what the shell expands | `team-kits/*/hooks/gate_write_scope.py` `_glob_readings` / `_names_expanded`; `tools/test_hooks_v2.py` +5-row test +5-row counter-end | `('python .cla*de/hooks/gate_approval.py < payload.json', '', '') / assert 0 == 2` | test_hooks_v2 | lead |
| BUG-0087 | an assert-or-True stood in the suites | already built; naming test passes | n/a (already fixed) | test_repo_hygiene | lead |
| BUG-0092 | a dead pricing comment and a dead watch date | already built; two naming tests pass | n/a (already fixed) | test_model_ladder | lead |

**BUG-0081's red row**, which does not fit the table's width: the fix's own mutation is the
`OUTSTANDING_UNTIL_PUBLISHED` set. The test that cannot pass without it is
`test_the_first_work_branch_push_is_not_refused_for_a_verdict_the_push_has_to_produce`, and the
three tests around it are what keep the softening from being a hole -- the merge row, the
also-merges rows and the review/test rows all stay rc 2. The measured BEFORE state is the item's
own live chain (Canyon 2026-08-31) plus this round's fixture: with the fix removed, the first push
is rc 2 with "QA has judged PR-0001 only in part -- ... and no acceptance Evidence covers it at all".

## 23. The runs, and what they cost

All times read by the shell, not typed. One pytest at a time (DEC-0094); the logs live under
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0139/`, each under its own name, LF-written.

| run | selection | wall clock | result |
|---|---|---|---|
| the naming nodes | 17 nodes of the already-named bugs | 19:52:48, 15.36 s | 19 passed, 1 skipped |
| the office nodes + BUG-0016's | 7 nodes | 19:53:09, 14.31 s | 8 passed, 1 skipped |
| BUG-0052's measurement | `tools/test_hooks_v2.py` whole | 18:55:05-19:06:31, 11:25 | 3 failed (pre-existing), 2136 passed -- and the repo audit log grew by two fixture lines |
| batch 1 | `test_hooks_v2` + `test_hooks` | 20:00-20:22, 22:40 | 11 failed, 3166 passed, 13 skipped |
| batch 2 | report, role_contracts, staging_cli, kernel, repo_hygiene, review_procedure, kit_neutrality, pointer_sweep, reference_skills, disposition | 20:25-20:29, 3:31 | 1 failed, 496 passed |
| batch 3 | migrate, migrate_holes, close_measured_pass, context_budget, shortening_net, approvals_dispatch, state, office_package, model_ladder, board_browser, handover_marker, kitupdate | 20:30-20:42, 11:27 | 2 failed, 710 passed, 1 skipped |
| batch 4 | the remaining 24 modules | 20:43-20:49, 5:19 | 3 failed, 618 passed |
| the kernel re-run | report, kernel, staging_cli, backlog_types, state, schemas, repo_hygiene | 20:55-20:57, 2:10 | 538 passed |
| batch 5 | hooks_v2, hooks, migrate, kitupdate, light_kit -- after the LAST kit change | 20:57-, see below | see below |

`python tools/bump_kit_version.py` ran four times, because three findings after the first stamp
each touched a kit file: the test pointer in `gate_git.py`, `REFERENCE_LIST_FIELDS`, and the
`report.py` docstring beside it. The LAST stamp is the one that stands.
`python tools/validate.py`: green at 19:58:53, 20:30:28 and 20:55:11.
`python -m ruff check tools team-kits .claude`: green.

### What batch 1 cost me, and what it bought

Eleven reds. THREE were on the tree when this order started (section 1). EIGHT were mine, all one
class: the conftest redirect makes `$CLAUDE_PROJECT_DIR` non-empty, `_root.find_repo_root` answers
it BEFORE the payload's `cwd`, and `_run_trust_hook` started the shipped hook with no environment
at all. The helper now names the variable, the way `run_hook_process` names it for every other hook
this suite starts. 8 passed, 33.25 s. A ninth of the same class surfaced in batch 3
(`tools/test_migrate.py`'s `spawn_verdict`) and was repaired the same way, 11.38 s.

### The two reds batch 2 and batch 4 found IN MY OWN WORK

- `tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves`: the comment I
  had just written in `gate_git.py` cited `tools/test_hooks_v2.py::test_the_kind_outstanding_...`
  and the test is in `tools/test_hooks.py`. The repo's own pointer sweep is what caught it -- the
  rule that a named test must RESOLVE, working exactly as intended, on the round that wrote the
  claim. Fixed, mirrored, 1 passed in 35.79 s.
- `tools/test_backlog_types.py::test_the_reference_list_fields_are_what_the_kernel_reads_elementwise`:
  my `freeze_architecture` reads `architecture_refs` through `field_elements`, and the field was
  not in `REFERENCE_LIST_FIELDS`. The tripwire derives the set from the kernel's own sources and
  compares BOTH ways, so it named the new reader by itself. Declared; 51 passed. And the docstring
  of `report._check_design_refs_resolve`, which said "THE ONE FIELD OF `REFERENCE_LIST_FIELDS`
  NOTHING RESOLVED HERE", was corrected in the same stroke -- with the new member's missing
  existence check NAMED and the reason it was not added in this round (a new validator finding
  changes what `validate` says about every existing project, and no stored entry can be stale yet
  because the field had no writer until this hour).

## 24. The reds that were HERE, measured on HEAD content

Five, and none of them is this round's. Each was re-measured in a copy under
`_round-scratch/TSK-0139/` whose `team-kits/` was restored from `git show HEAD:<path>`:

1. `tools/test_hooks_v2.py::test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it`
   -- `tools/close_measured_pass.py` (TSK-0138's own tool) runs its `plan()` on the import probe's
   defaults and dies with `FileNotFoundError: ...staging/TSK-0131/survey-table.md`.
2. `tools/test_hooks_v2.py::test_every_approval_refusal_the_hook_can_surface_speaks_to_the_user`
   -- three `ApprovalError`s raised by TSK-0138's `_assert_the_list_covers` (lines 1524/1530/1535)
   carry no `user_text`.
3. `tools/test_hooks_v2.py::test_the_lead_of_a_scaffolded_project_is_not_read_as_its_own_subagent`
   and 4. `tools/test_research_chain.py::test_the_research_chain_runs_from_the_question_to_a_merge_through_the_shipped_hooks`
   -- the same refusal in both: `the lease for TSK-0001 says rung opus but the spawn names no
   model`. Measured on HEAD content by `check_chain_at_head.py`: identical, rc 1.
5. `tools/test_shortening_net.py::test_no_section_of_a_pinned_instruction_file_disappears_unnoticed`
   -- measured on HEAD content by `check_pins_at_head.py`: 10+ sections CHANGED, among them files
   this round never opened (`dev-team agents/project-manager.md` §'(preamble)',
   `office-team skills/office-manager/SKILL.md`). This round's own constitution paragraph adds two
   further rows to that list.
   **DELIBERATELY NOT RE-PINNED.** `pin_constitution_sections.py --write` would absorb the older
   drift into a fresh pin and destroy the evidence of it -- which is the exact failure the test's
   own docstring warns about ("a pin that healed itself inside the test run would be a record of
   nothing"). The re-pin is one decision over BOTH the pre-existing drift and this round's two
   rows, and it belongs to whoever can look at the older drift and say what it was.

## 25. What is deliberately NOT closed

1. **BUG-0055 and BUG-0056** -- section 18, with mechanism, chain and bound each.
2. **BUG-0081 AC-2's visible marker** and **BUG-0054 AC-2's five other producer-less hashed
   fields** -- sections 10 and 11.
3. **BUG-0080's in-apparatus writer** for a re-freeze input -- section 13.
4. **BUG-0067 AC-2** -- the eight office templates still lying in this repo's `project_memory/`.
5. **The five pre-existing reds** of section 24, including the re-pin decision.
6. **The full `tools/` run.** Gate 5 refuses it inside a round without the `DELIVERY_RUN` prefix,
   and DEC-0050 makes it the goal's final round's job. What ran instead is every module of the
   surface, in five named selections, which is the same coverage at the same cost minus the gate's
   refusal -- but it is NOT one run and this protocol does not call it one.

## 26. The closing run, and the (g) row

**batch 5**, the re-run of the biggest reading surface AFTER the last kit change:
`tools/test_hooks_v2.py tools/test_hooks.py tools/test_migrate.py tools/test_kitupdate.py
tools/test_light_kit.py`, 20:57:24 -> 21:30:40, **33:15, 3 failed, 3429 passed, 14 skipped**.
The three are the three this order FOUND on the tree (section 24 rows 1-3) and none of them is
this round's; every one of the nine regressions batches 1 and 3 exposed is gone.

`project_memory/.audit/hook_events.jsonl` after ~75 minutes of suite runs: md5
`92d2f0d71343ba230d7455c5a6091c8e`, 699 lines -- the same bytes it carried at 19:06, before any of
them. That is BUG-0052 AC-2, measured over the whole surface rather than over one fixture.

| (g) | value |
|---|---|
| wall clock | 18:50:37 start (`git status`, HEAD fd7e2fa) -> 21:31 close-out, ~2 h 40 |
| of which pytest | ~75 min in 9 measured runs, one at a time |
| bugs of the grown list | 33 -- 15 fixed red-first, 16 measured already fixed with a naming test, 2 handed back with mechanism and bound |
| red-first rigs | 14 cases under `_round-scratch/TSK-0139/`, every one recording the arbiter's failure LINE and not only its rc (DEC-0094 (10)) |
| regressions this round caused and closed | 9 (8 + 1 of the `$CLAUDE_PROJECT_DIR` class), plus 2 my own checks caught (the test pointer, `REFERENCE_LIST_FIELDS`) |
| reds found ON the tree | 5, all measured against HEAD content so the attribution is not a guess |
| stamps | 4 bumps; the last is `dev 2026.09.11-21 / office 2026.09.11-20 / research 2026.09.11-21` |
| not minted | no EVD, no transition, no commit, no push -- the batch route is the lead's |

## 27. The rig, for whoever runs it next

`_round-scratch/TSK-0139/rig.py` is the shared half of all 14 cases and obeys the two rules
generation 3 paid for: it REFUSES to run outside its own directory (every path is resolved against
the rig file, and a working directory that is not the rig's own exits 2), and it reads and writes
BINARY only, so a mutation cannot rewrite line endings on this host. `arbiter_line` returns the
assertion the arbiter fell on, which is what a row records -- an rc alone would have passed the
BUG-0054 mutation that raised a `TypeError` for the wrong reason, and that row was rewritten until
the failure was the named one.

`wait_for.py` is the waiter the round used instead of a shell loop: gate 1 refuses a `[` or a
`$var` in a command line, so the loop lives in a file, and it reads only the END of the log.

# ---------------------------------------------------------------------------------------------
# REWORK after verification round 1 (23:35, one rework as ordered)
# ---------------------------------------------------------------------------------------------

## R1. F1 (HIGH, blocking) -- the softening read the branch, not the push TARGET

- **Confirmed as reported.** `_publishes_a_work_branch` asked `target_items`, which answers "which
  item is this line ABOUT": it scans the segment and otherwise falls back to the branch HEAD is on.
  So a push to the trunk from a work branch was handed the lighter rule.
- **Change**: `team-kits/{dev,research}-team/hooks/gate_git.py` -- `_destinations_of` (refspec
  destinations, `_SPREADS_PAST_ITS_REFSPECS`, `_PUSH_OPTIONS_WITH_A_VALUE`), `current_branch` as
  ONE reader for the two rules that need it, and `_publishes_a_work_branch(command, targets,
  repo_root)` requiring EVERY destination to name an item. The trunk is never enumerated: it names
  no item, which is the same `TARGET_RX` `target_items` decides with.
- **The docstring at the old :350 is true now** and says what the first cut got wrong, with the
  three measured lines.
- **Tests** (`tools/test_hooks.py`): `::test_a_push_whose_destination_is_not_a_work_branch_keeps_the_delivery_demand`
  (5 rows), `::test_every_push_option_that_spreads_past_its_refspecs_is_refused_the_softening`
  (6 rows) with its set tripwire `::test_the_spreading_push_options_measured_here_are_the_set_the_gate_decides_on`,
  and the counter-end `::test_a_push_whose_destination_names_the_item_still_gets_the_softening`
  (5 rows, including the bare `git push` whose destination is the current branch's upstream).
  A new `_on_a_work_branch` fixture gives the repo a real git history and branch, without which
  the rows measure the gate's no-item path instead of the one they are about.
- **RED** (`case_f1.py`, the round-1 reading restored in both kits): `git push origin HEAD:main`,
  `git push origin feat/PR-0001-x:main`, `git push origin main`, `git push -o ci.skip origin main`
  and all six spread options come back **rc 0 with the OWED note**; the counter-end stays green in
  the same mutated copy.
- **One row dropped with its reason in the docstring**: `+feat/PR-0001-x:main` is rc 2 from the
  force-push ban, which stands in front of every rule in this file, so a row for it would assert a
  refusal this softening never reaches. `_destinations_of` still strips the marker, as a belt.

## R2. F2 (HIGH, blocked the clicks) -- an evidence that measured a run, not the defect

- **Confirmed**, and the round found a SECOND selection defect beside it (R3).
- **One reader, in the kernel**: new `team-kits/kernel/naming_tests.py` --
  `names_the_item` (the property), `nodes_naming` (the SEARCH, for the tool), `declares` +
  `coverage_blocker` (the CHECK, for the kernel), `nodes_in` (the nodes of a run command).
  `tools/close_measured_pass.py` now imports it; its own copy is gone.
- **The declared places tightened to DEC-0100 (3) / H195**: the docstring's FIRST paragraph or a
  DECORATOR. An id in a body comment or in a later paragraph is a MENTION and no longer a naming --
  `tools/test_close_measured_pass.py::test_the_evidence_comes_from_the_tests_that_name_the_bug_and_from_no_other_node`
  carries both as rows that must come back empty.
- **`batch_walk_blockers` refuses by name** when the chosen evidence's run command names no node,
  names a node this checkout does not declare, or names only tests that do not name the defect.
- **Tests**: `tools/test_approvals_dispatch.py::test_a_bug_whose_evidence_does_not_name_it_is_refused_from_the_batch`
  (3 shapes) and `::test_the_batch_the_request_refused_cannot_be_minted_either`.
- **RED** (`case_f2.py`, the check cut back out): all four rows `Failed: DID NOT RAISE
  ApprovalError` -- the verifier's exact chain closes by one click again.
- **Performance, found by the measurement**: the shared reader re-parsed every module per id; a
  31-id plan took over nine minutes. `_declarations` memoises per file STAT; the same plan prints
  in 5 s.

## R3. The selection defect F2 uncovered -- a parent closed by its child's green run

- **Measured on the REAL store, not a fixture**: `BUG-0082` carries `related_pr: BUG-0075`, so
  `report.evidence_covers` (which accepts an indirect hop, correctly, for the DELIVERY question)
  made the run that measured BUG-0082's fix answer as BUG-0075's current verdict. The third batch
  line was refused with "its evidence names <the child's node>, and none of those tests NAMES
  BUG-0075" -- the refusal was right and the SELECTION was the defect.
- **Change**: `approvals.proofs_naming` -- the newest `proof` Evidence whose `related` names the
  item DIRECTLY, built in ONE pass for the whole batch; used by `batch_walk_blockers` AND by
  `verification_batch`, so the record the question SHOWS is the record the blockers judged.
- **Any result, not only passing**: keeping only passes would hide a FAIL recorded after a PASS.
  Measured -- with a passing-only scan
  `test_a_batch_that_moved_since_the_question_closes_nothing_at_all` reached the WALK and was
  refused there, after the APR exists.
- **Ordered by (created, id)**: `_now_iso` has second resolution, and two Evidences in one second
  compared equal -- the directory listing decided. `_recorded_at` says so.
- **Test**: `::test_a_parent_defect_is_not_closed_by_its_childs_green_run`, with the child's own
  closure as the control.

## R4. F8 -- the EVDs exist now, and the four batch lines are ACCEPTED

`tools/close_measured_pass.py` recorded them: AST-derived naming nodes, one real pytest node at a
time, LF log at `project_memory/staging/TSK-0139/rerun.log`, table at `closable-table.md` (a table
of THIS order's ids in the tool's shape -- its own header says it is not a survey).

**measured: 31, still passing: 31, no longer passing: 0, held back: 0** over 50 nodes.
The first run held 26 back by the tool's own `held_back_by` rule (PR-0012 AC-3 names them as still
to be fixed) -- correct by its contract and wrong for THIS route, which IS AC-3; the second run
passed `--other-route ""` and the reason is recorded here rather than in a flag nobody sees.

Asked of the kernel afterwards (`check_batches.py`, read-only), all four lines are accepted:

```
request-approval verification --batch BUG-0010 BUG-0014 BUG-0016 BUG-0017 BUG-0022 BUG-0023 BUG-0026 BUG-0027 BUG-0031 BUG-0034
request-approval verification --batch BUG-0037 BUG-0044 BUG-0046 BUG-0050 BUG-0052 BUG-0053 BUG-0054 BUG-0057 BUG-0058 BUG-0062
request-approval verification --batch BUG-0067 BUG-0074 BUG-0075 BUG-0076 BUG-0077 BUG-0079 BUG-0080 BUG-0081 BUG-0082 BUG-0087
request-approval verification --batch BUG-0092
```

EVD-0284..EVD-0314, one per id (BUG-0075 -> EVD-0306, BUG-0082 -> EVD-0312 after R3).
**Named rather than tidied**: eleven defects now carry TWO naming-run Evidences, because TSK-0138's
run recorded one for five of them and the first of this order's two runs for the rest. The newest
wins everywhere that decides, and nothing removes an Evidence -- but the store says "measured
twice" and a reader should know why.

## R5. F3, F4, F5, F6 -- the four smaller ones

- **F3**: `_path_as_this_bash_sees_it` translates HOME the same way the script path is translated,
  and the probe asks THIS bash (`shutil.which("bash")`, the resolved executable -- a bare `bash`
  finds WSL on this host while `which` finds Git Bash, and the two spell a Windows path
  differently). Skips only when that bash can see neither spelling. 2 passed, no skip here.
- **F4**: the merge clause has its own rc-2 rows now --
  `("git merge feat/PR-0001-x && git push origin feat/PR-0001-x", "the push half alone would
  qualify")` and `("git $CMD origin feat/PR-0001-x", "a verb the text does not fix could be the
  merge")`. The old second row pushed to `main` and would have been refused by F1's rule instead,
  which is what made the clause mutation-green.
- **F5**: `assert "ZERO AskUserQuestion" in record[run]` -- presence of the word is also what a
  record saying the PM ASKED one would carry.
- **F6**: the negation must stand BETWEEN the artefact word and "scope manifest". A `not` anywhere
  in the sentence excused the whole sentence before. Re-measured on `case_bug0077.py`: still red.

## R6. F7 -- captured as a hole, with its bound

`BUG-0280` / **H196**: a hook a suite starts without its own `CLAUDE_PROJECT_DIR` judges whatever
the ambient variable names. The AST scan measured 65 subprocess starts naming a hooks directory or
a shipped-hook constant, 55 without the literal in the call's own keywords -- but that number is
NOT 55 defects: most pass `env` through a name bound one line above (`run_hook_process` is among
the 55), and telling those apart needs dataflow. That is the hole, and it is why the check was not
built in an hour. The bound is on the item: the ambient value is a throwaway tree, so the worst a
forgetful site does is measure an empty project; the failure direction is LOUD (the nine reds this
round produced failed, they did not pass wrongly); and the one helper every new test is copied
from names the variable.

## R7. The two TSK-0138 regressions, now fixed at the mechanism

- `test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it`: TWO defects in one row.
  `close_measured_pass.py` died on its way in (an unguarded `io.open` on a default path that a
  copy of the tree need not have) -- it now raises a SENTENCE naming the remedy; and it wrote
  `team-kits/kernel/__pycache__` into the HASHED hook bundle -- `sys.dont_write_bytecode = True`
  before the kernel import, with the reason (a moved bundle hash drops a project to
  `hooks_trust_required` and refuses its spawns).
- `test_every_approval_refusal_the_hook_can_surface_speaks_to_the_user`: the three
  `_assert_the_list_covers` refusals reach the person who just CLICKED and had no `user_text`.
  All three now carry one.

## R8. The three that stay for order 3, named

`test_the_lead_of_a_scaffolded_project_is_not_read_as_its_own_subagent` and
`tools/test_research_chain.py::test_the_research_chain_runs_from_the_question_to_a_merge_through_the_shipped_hooks`
-- ONE mechanism in both: `the lease for TSK-0001 says rung opus but the spawn names no model`,
measured identical on HEAD content (`check_chain_at_head.py`). And
`test_no_section_of_a_pinned_instruction_file_disappears_unnoticed`, red on HEAD content with 10+
sections including files this round never opened (`check_pins_at_head.py`); the re-pin is one
decision over the older drift AND this round's two rows, and absorbing the first silently is what
that test's own docstring warns against.

## R9. The rework's runs

| run | selection | wall clock | result |
|---|---|---|---|
| kernel side | approvals_dispatch, close_measured_pass, report, role_contracts, handover_marker, kernel, staging_cli, repo_hygiene | 23:23-23:28, 4:43 | **676 passed** |
| `test_hooks` | `-k git or trust or approval or push or seeding or preset or handover or registration or escape` | 23:28-23:31, 3:02 | **295 passed, 3 skipped** |
| `test_hooks_v2` | `-k git or approval or trust or scope or docker or compose or metacharacter or bytecode` | 23:31-23:35, 3:49 | **604 passed** |

ONE restamp after the last kit change: dev/research `2026.09.11-22`, office `2026.09.11-21`.
`ruff check tools team-kits .claude` green. `validate.py` green at 23:36:00 -- after
`git add team-kits/kernel/naming_tests.py`, which validate demanded by name: a file hashed into a
kit VERSION and not git-tracked makes CI and a fresh clone disagree with the local hash. That is
the ONLY git command this order ran, it stages and nothing else, and no commit was made.
`project_memory/.audit/hook_events.jsonl` unchanged throughout: md5 `92d2f0d71343ba230d7455c5a6091c8e`.

## R10. Vorgefunden at 00:13 on 2026-09-12 -- the lead opened the four questions

Measured, not assumed: `project_memory/approvals/pending/` carries FOUR untracked requests of
`kind: verification` whose `subject_manifest` holds this order's own ids and Evidence (the one read
names BUG-0092 -> EVD-0314), and the audit log has ONE new line, 23:56:34, `gate_approval` noting
"approval question for 9dbbfd63... matched the kernel's". That is the lead putting R4's four batch
lines to the user; the questions are open and no APR exists yet.

TWO CONSEQUENCES FOR THIS PROTOCOL, both small and both worth writing down rather than leaving to
a reader who finds a hash that no longer matches:

* `project_memory/.audit/hook_events.jsonl` is no longer `92d2f0d71343ba230d7455c5a6091c8e`; it is
  `4cbe1108a18d6a43b2531ec4982b2f11`. The measurement in section 2 is NOT invalidated by that: it
  says a SUITE RUN leaves the log untouched, and the line that moved it is a real approval event
  written by the real writer, which is what the log exists for. The suite-run claim is still the
  one `test_no_hook_started_by_this_suite_can_write_this_repos_audit_log` holds.
* Anything a round-2 check measures about the batch route now runs against a store with four OPEN
  requests in it. They are the lead's and this order does not touch them -- no mint, no answer, no
  sweep.
