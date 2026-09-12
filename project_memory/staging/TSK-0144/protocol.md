# TSK-0144 -- the GOAL ROUND (merge) of PR-0012 "Bug-Null"

Implementer: `harness-implementer` (Opus, high). Base `10a5127`, the three streams' work
UNCOMMITTED in the tree. I am the only writer from here on.

Clock readings are taken with `date` at the moment the line is written, never rounded.

## Plan, and the way it was REJECTED

**The way taken.** Each seam row is built where its OWNER lives (kernel half in
`team-kits/kernel/report.py`, the kits' half in the mirrored `hooks/_routine.py`, the tools half in
`tools/test_*.py`), each with a node that goes RED when the fix is cut out of a `.git`-less copy,
and an EVD whose `run_command` names that node so `kernel.naming_tests.coverage_blocker` can read
it.

**The way REJECTED: one "merge sweep" test per group** -- a single node per seam group (say
`test_the_seam_rows_of_the_merge_hold`) asserting several properties at once. It loses on a
measured property of this repository: a node is what an EVD names and what a verification batch
line is refused over, so a collapsed node makes every one of its properties share one verdict --
and `kernel.naming_tests.coverage_blocker` would then report one blocker for a group in which only
one member is broken. What the smaller way would NOT have covered is exactly the red-first
measurement per hole that `DEC-0070` asks for: mutating one arm of a five-property test leaves the
node red either way, so the mutation measures nothing about WHICH arm is load-bearing.

## 2026-09-12 15:14 -- start

Scratch: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0144/`.

## Seam (a) -- `BUG-0265`/H183, the kernel half  (clock 2026-09-12 15:23)

`team-kits/kernel/report.py:2582-2593` (`installed_kit_paths`): where the entry point exists, the
prefix set now takes the FILES the installer recorded in `.claude/kit_repo_files.json`; the two
directory names stay as the fallback for a project installed before that record existed, and the
docstring, the constant's comment and the tripwire test's docstring say so in that role instead of
"the kernel holds no other reader".

Naming node: `tools/test_pointer_sweep.py::test_a_projects_own_script_is_swept_while_the_kits_copy_beside_it_is_not`
(new). It installs `office-team` for real, reads the manifest the installer wrote, and sweeps
through the project's own entry point.

RED-FIRST, in the `.git`-less rig (stamped there, since the installer refuses an unstamped staging):

* with the change:    `1 passed in 10.50s`
* fix cut out (the `prefixes |= set(INSTALLER_SCRIPT_DIRS)` line restored):
  **`1 failed in 11.10s`** -- `the project's own scripts were not swept: rc 0, 0` (`assert (0, 0) == (1, 4)`)
* restored, whole file: `8 passed in 40.74s` (the three-kit sibling included, so the refactor into
  `_scaffolded_pilot` and the narrowed exclusion cost the acceptance line nothing).

The second end is in the same node and is what a "just drop the exclusion" fix fails: at least one
recorded kit file under `scripts/`/`tools/` really produces a finding when it IS read (asked with
`report.findings_in_text`), and none of them is reported.

## Seam (b) -- N2 of TSK-0143 verify-round-3  (clock 2026-09-12 15:26)

`tools/test_repo_hygiene.py:1337` -- the first docstring line of `_defined_in` named two of three
answers. It now names all three. Prose correction, no new test: the third answer is already held by
`tools/test_repo_hygiene.py::test_a_suite_file_a_neighbour_is_saving_is_unreadable_and_not_a_dead_pointer`
(the verifier measured its mutation `return UNREADABLE` -> `return None` as `1 failed in 1.95 s`),
and this line is the sentence that pointed away from it.

## Seam (c) -- the evidence-vocabulary corpus, and what it took to make it READ  (clock 2026-09-12 15:41)

The row asked for one line (add `.claude/hooks/*.py` to the corpus). MEASURED FIRST, because the
row's purpose is "the next S2-class break is red in `pytest tools/`": that line alone reads **zero
sentences** out of those files. Three arms, all three load-bearing:

1. **the corpus** -- `tools/test_hooks.py:6902` adds this repository's own gates;
2. **the refusal reader** -- `_refusal_texts` recognised the literal name `block`, which this
   repository's gates never use (`calls named block in .claude/hooks/: 0`). It now asks a PROPERTY:
   a function that CANNOT RETURN to its caller (`_names_that_stop_the_role` / `_cannot_return`).
   The first cut of that derivation said "exits on ANY path" and marked **45** names in this
   bundle -- `decide`, `payload`, `probe`, every gate's entry point -- which would have fed ordinary
   string arguments to the vocabulary checks. The shipped rule says "no `return` anywhere AND the
   last statement cannot fall through", and that is **3** names here (`refuse`,
   `_refuse_the_declaration`, `guarded`) and 15 in the dev-team bundle, 34 refusal texts out of the
   8 repo gates;
3. **the call spelling** -- `_evidence_call_rx` knew only `cli.INVOCATION` (the installed entry
   point). A repository without an installed kit calls the kernel as a MODULE, which is what this
   repo's CLAUDE.md prescribes and what its gates print. Both spellings are now derived from the
   module (`cli.INVOCATION`, `-m` + `cli.__name__`), never typed.

RED-FIRST, in the rig, against a stand-in gate bundle written for it
(`rig/.claude/hooks/_harness.py` + `gate_stand_in.py`; the real one cannot be copied -- a shell line
naming a hooks directory is refused, H80):

| what was cut | `…::test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires` | `…::test_the_refusal_reader_finds_a_stopper_this_repos_own_gates_spell` |
|---|---|---|
| nothing, correct gate text | passed | passed |
| the two run flags dropped from the gate text (the S2-class break) | **FAILED** | passed |
| break planted + arm 1 (corpus) cut | passed (silent again) | **FAILED** |
| break planted + arm 2 (stopper -> `block`) cut | passed (silent again) | **FAILED** |
| break planted + arm 3 (entry spelling) cut | passed (silent again) | passed |
| break planted, all three arms in place | **FAILED** | passed |

Arm 3 is the one the new node does not hold; the break itself is what holds it, which is why the
table is the measurement and not the node count.

**AND THE NODE IS RED IN THIS TREE, on purpose.** `.claude/hooks/gate_commit_evidence.py:418-423`
prints an `evidence` call without `--run-command` / `--run-scope` -- the S4 patch in
`staging/TSK-0141/s4-gate-commit-evidence-patch.md`, which only a shell OUTSIDE Claude Code can
write (the file is refused to every role here). The node's docstring says this and says why no
exception for that one file was added: an exception would restore exactly the silence H108 was
found by hand in. Selection after the change, in the repository:
`tools/test_hooks.py -k "refusal_reader or evidence_kind_or_verdict or evidence_command_a_text or
refusal_text_names_a_kernel or every_command_a_role_is_handed or every_approval_kind_a_role_is_handed
or every_span_that_presents_the_command_surface"` -> **6 passed, 1 failed, 13.63 s**, and the one
failure is that node.

## Seam (d) -- `BUG-0240`/H158, the three-part patch across two owners  (clock 2026-09-12 15:58)

All three parts, in one change, because building one of them alone was exactly the seam damage the
row names:

1. **`hooks/_routine.delivery_occasions`** (new; mirrored byte-identical in all three kits, sha256
   head `07ebce0e7723` in dev = office = research). The DEFINITION is not B3's sketch and the
   difference is measured: B3 proposed "reached a TERMINAL state", and the scenario the pinned test
   builds is a goal walked to `DELIVERED` -- which is NOT terminal for `PR`
   (`_PR_LIKE.terminals` is ACCEPTED/REJECTED/SUPERSEDED), so that definition would have left the
   turned-around test red. What is built is "the record stands at the END of its own automaton":
   a terminal state, OR the status a confirming edge leads from (`backlog_types.confirming_edge`,
   the kernel's own name for "finished, not yet confirmed" -- `DELIVERED` for PR/RQ, `DONE` for TSK,
   `FIXED` for BUG). Both halves come from the automaton.
2. **`tools/test_review_procedure.py::test_a_delivery_since_the_last_run_makes_the_audit_due_and_names_it`**
   -- the node that pinned the seam, turned around, now in THREE states per kit (due on the period,
   silent after a run, due again and BY NAME after a delivery). The middle state is the one a
   register that never clears would pass.
3. **The honesty sentence**, in all three auditing SKILLs and all three `project-auditor`
   definitions: ONE of the four occasions reaches the role as a trigger and three do not, with the
   reader named (`hooks/_routine.delivery_occasions`) and the negation kept for the other three.
   `tools/test_review_procedure.py::test_the_retrospective_step_states_the_limit_it_runs_under`
   still reads that limit, and its own docstring was corrected in the same change -- it claimed
   "the step describes a trigger nothing fires", which is now false for occasion (b).

RED-FIRST, in the rig (two mutations of THIS round's fix, both ends):

| mutation in the rig | result |
|---|---|
| `delivery_occasions` returns the empty list at once (the occasion arm cut out) | **1 failed in 4.90 s** -- "a goal delivered since the last run left the register silent" |
| the `since` comparison dropped (`if stamped > 0`) -- every record is an occasion | **1 failed in 2.07 s** -- the duty stands after a run that followed the delivery |
| neither | 1 passed in 7.65 s |

THE SECOND-RESOLUTION TRAP, measured rather than reasoned: the run record carries SECONDS, so the
first cut of the node recorded the run at now plus one second and then captured the second delivery
immediately -- dev and office passed, **research failed**, because that capture landed inside the
recorded second. Reproduced outside pytest (when = 15:46:52, occasions empty). The node now WAITS
for the wall clock to pass that second instead of stamping a file by hand, and `delivery_occasions`
rounds a file's time UP before comparing -- so a record written in the same second as the run counts
as an occasion (the nagging direction).

Reading suites, all green: `tools/test_routine_feed.py tools/test_review_procedure.py
tools/test_role_contracts.py tools/test_parallel_streams.py` -> **132 passed, 33.82 s**.

`docs/holes/H158.md` rewritten: what is built, the one derivable occasion against the three that are
not, and the second-resolution limit. It also carried the OLD node name in a backtick span, which
`tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves` reads -- see the
reds below.

## Seam (d) -- `BUG-0147`/H55, the repo line  (clock 2026-09-12 16:10)

`user/bridge/update_kit.py`, the success path: the lift now SAYS that no approval covers it, names
the approval kind the old stock does not have (`kitupdate.KIND`), and tells the PM to report that in
the same breath as the restart. What is NOT closed and is not claimed: the unasked run itself, and
every copy already on somebody's disk -- the old hook set is fixed and a caller check in the bridge
would need a payload nobody gives it.

Naming node: `tools/test_kitupdate.py::test_a_stock_without_update_kit_is_lifted_by_the_bootstrap_and_told_about_it`
-- it reads the sentence off the REAL stdout of a REAL lift, not out of the file. Stamp-dependent
(the installer refuses an unstamped staging), so its measurement is in the post-stamp block below.
`docs/holes/H55.md` carries the split verdict.

## Seam (d) -- `BUG-0151`/H59 and `BUG-0197`/H113: NOT MINE AFTER ALL, with the measurement

* **H59.** The kernel half is BUILT and has been for two generations: `report.accepted_without_a_verdict`
  DERIVES the debt off the confirming edge (so the status is not typed anywhere), the state validator
  turns it into a warning per task, and `_kernel.unverified_delivery_briefing` says it at every
  session start in all three kits. Measured: `tools/test_report.py -k "accepted_without_a_qa_verdict
  or failing_verdict_does_not_count or kit_that_produces_no_delivery_verdict"` -> **3 passed, 4.84 s**.
  What is left is not a fix but a DECISION -- turning that warning into a refusal on a line a solo
  project really runs -- and the function's own docstring argues the other way with its reason
  ("standing here is what a task DOES between the developer's handback and QA, so this is a debt,
  not a defect"). A merge round is not where that gets decided; it belongs to the user's list.
* **H113.** There is no done-record anywhere: a grep for `done_record`, `erledigt` and `marked_done`
  over `team-kits/kernel/*.py` and `team-kits/office-team/hooks/_duties.py` gives **0 hits**. Closing
  it means a NEW canonical record kind (its own type, automaton, CLI surface and a register that
  reads it), which is a generation-sized change and not a defect repair. The two nodes the item names
  as its regression tests stand green today and pin the over-reporting direction
  (`tools/test_office_duties.py -k "many_years_past_retention or no_feed_can_take_every_slot"` ->
  **2 passed, 1.87 s**).

## Reserved row -- H196 / `BUG-0280`  (clock 2026-09-12 16:02)

`tools/test_repo_hygiene.py`, two new nodes plus **15 repaired call sites** (14 in
`tools/test_hooks_v2.py`, 1 in `tools/test_research_chain.py`, its `_hook_process`).

AC-1 is the whole point and it is a DATAFLOW, not the scan: the item's own count of 65 starts / 55
without a literal is what produced the item. The reader follows the two shapes the environment
really travels in -- built in the enclosing function, or handed in as a PARAMETER (then every
CALLER must name it) -- and the number it leaves over was measured down step by step:

| reader | starts it names |
|---|---|
| the item's scan (no literal in the call's own keywords) | 55 |
| plus the enclosing-function reach | 14 |
| plus the PROGRAM instead of argv element 0 (a `mklink` line naming a hooks dir as an ARGUMENT was a false alarm) | 13 |
| plus an argv held by a NAME followed to its assignment, and the caller rule for a handed-in `env` | **15** (two more found, none lost) |
| after the 15 call sites were repaired | **0** |

A BIDIRECTIONAL closure was tried first and thrown away, measured: marking a callee covered because
its caller names the variable collapses almost every function of such a module into "covered"
through a shared helper like `write`, so the sweep would have reported nothing and said it had
looked. The docstring says that, because it is the reason the reader is narrow.

RED-FIRST / both ends:
`tools/test_repo_hygiene.py::test_the_project_reach_reader_tells_a_forgetful_fixture_from_an_inherited_one`
runs the reader over a four-function probe it writes itself and demands that exactly `forgets_it` is
named -- the `run_hook_process` shape and the own-keywords shape must stay silent -- plus the real
`run_hook_process` of `tools/test_hooks.py` measured as covered. The sweep node was **RED on this
tree** before the 15 repairs (14, then 15 findings with file, line, function and argv) and is green
after them; selections: `-k "naming_the_project or project_reach_reader"` -> **2 passed, 5.53 s**;
the repaired sites re-run as `tools/test_hooks_v2.py -k "does_not_compile or launcher or chain or
oversized or crashes or drains_stdin or fake or bytecode or importing_the_hook or minted"` ->
**58 passed, 52.54 s**.

## Reserved row -- `known_holes.json`  (clock 2026-09-12 16:05)

`python tools/gen_known_holes.py` -> wrote both files; **DELTA ZERO**, and measured twice rather
than eyeballed: sha256 `f45e24885e7c`, 1044 bytes, before AND after; `git status --porcelain` over
`team-kits/kernel/known_holes.json` and `known_holes_digest.py` is EMPTY. The streams neither added
nor removed a `known_hole` marker: 8 marked tests in 3 capabilities (`approval_provenance` 3,
`hook_trust` 1, `state_write_protection.shell` 4).

## Reserved row -- the three prose rows of verifier B round 3  (clock 2026-09-12 16:08)

In `project_memory/staging/TSK-0142/protocol.md`:
* **D1** -- `BUG-0164`/H72 now asks properly (Lage / two options / a price per option) and says in
  the row that it was corrected here and why; it stands in the measurements AND in the question list.
* **D3** -- the `BUG-0260`/H178 question carries a price per way: (a) the report loses the
  classification entirely, (b) every non-QA role needs a round trip per failure.
* **D2** -- the COUNTS line is split: "downgraded with a measurement: 7" plus `BUG-0147`/H55 as its
  own row, world limit AND repaired repo line, with the naming node.

## A RED THAT WAS ALREADY IN THE TREE, fixed at its mechanism  (clock 2026-09-12 16:15)

`tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves` was red on a
citation stream B left behind: `team-kits/scaffold_team.sh:193` named
`tools/test_hooks.py::test_neither_twin_replays_a_manifest_line_that_is_not_a_repo_relative_name`,
and the node that exists is `..._that_is_not_the_installers_to_write`. Corrected in the comment (the
PowerShell twin carries no such citation -- grep over `scaffold_team.ps1`: 0). After the correction
and after the H158 rename, the sweep plus its own floor node are **2 passed, 84.25 s**.

STILL NAMING THE OLD H158 NODE, and NOT mine to touch: `project_memory/bugs/active/BUG-0240.yaml`
(`observed`, and `regression_tests` as its first entry) and four staging protocols of earlier
rounds. `project_memory/**` is this item's `forbidden_scope` and only the kernel writes items, so
this is handed to the lead: the `regression_tests` entry of BUG-0240 has to become
`tools/test_review_procedure.py::test_a_delivery_since_the_last_run_makes_the_audit_due_and_names_it`
at close-out. The repo-side sweep does NOT read `project_memory/`, so nothing goes red on it today --
which is exactly why it is written here.

## THE STAMP -- three calls, and why the first two were superseded  (clock 2026-09-12 18:21)

| call | versions | why it is not the delivery stamp |
|---|---|---|
| 16:20 | `2026.09.12-3` | I changed a kit file AFTER it: `delivery_occasions` read only `active/`, and a task is ARCHIVED the moment it reaches its terminal status -- so the reader missed exactly the records the feature exists for. `state.read_anywhere` closed that, and it is a kit change. |
| 16:50 | `2026.09.12-4` | the full run of 16:51 found four reds whose mechanism sits in kit files (`kernel/holes.py`, `kernel/state.py` + `kernel/report.py`, `office-team/.../ledger_add.py`, `kernel/approvals.py`) |
| **18:21** | **`2026.09.12-5`** | the delivery stamp: `bump_kit_version.py` a second time -> **unchanged x3**; `validate.py` -> all structural checks passed; `ruff check .` and `ruff check user/` -> All checks passed; `pin_constitution_sections.py` -> 3 kits, 12 files, 125 sections, all pins current; mirror of `_routine.py` sha256 head `ff5c4e7f621c` in all three kits |

THE PROCESS ERROR IS MINE AND IT COST A RUN: the 16:36 full run was started before the last kit
change and had to be killed at ~9 minutes, because a run that reads the tree at test time judges a
tree that no longer exists by the time it finishes. What it cost: one restart. What it bought: the
`read_anywhere` defect, which I found by re-reading my own correction rather than by a test.

## THE FIRST FULL RUN -- the measurement that found the reds  (16:51:41 -> 18:01:51)

    DELIVERY_RUN=TSK-0144 python -B -m pytest tools/ -q
    9 failed, 5068 passed, 14 skipped, 1 warning in 4207.47s (1:10:07)

Nine reds, each named with its mechanism. NONE of them was a flake: every one reproduced in a
narrow selection.

| red | attribution | what happened |
|---|---|---|
| `tools/test_hooks.py::test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires` | MINE, on purpose | the S4 arbiter of seam (c). Red until the user patches `.claude/hooks/gate_commit_evidence.py`; the node's docstring says so and says why no exception was added for that file |
| `tools/test_hooks_v2.py::test_every_approval_refusal_the_hook_can_surface_speaks_to_the_user` | PRE-EXISTING at base `10a5127`, measured | six `ApprovalError` raises in `approvals.consumed_request` carried no `user_text`. ATTRIBUTED by running the node against HEAD's own `approvals.py` in the rig: **1 failed** there too, so no stream put it in. Fixed: six German sentences, one per branch (revoked / no record / unreadable / wrong shape / altered after minting / does not hash to itself). Green after |
| `tools/test_hooks_v2.py::test_no_shipped_script_knows_about_only_some_tool_caches` | stream A/C (`kernel/holes.py`) | `test_modules_under` named `__pycache__` and not the other three caches -- the tripwire's own case. Fixed by DELETING the enumeration: the walk now asks `hashing.is_transient`, the kernel's one answer |
| `tools/test_hooks_v2.py::test_a_malformed_existing_row_stops_the_write` | stream B (`ledger_add.py`) | the duplicate reading added this round sorts a row's own column names, and `csv` files the overflow of an unquoted comma under the `None` key -- so one hand-edited line raised `TypeError: '<' not supported between 'NoneType' and 'str'` instead of "wrong number of columns", one line after the right finding had been produced. Fixed: `is_malformed` is ONE predicate with two readers, and `validate_cross` is not asked about a row whose shape is broken |
| `tools/test_migrate.py::test_the_two_remedies_that_still_move_a_file_differ_in_whether_the_file_was_read` | stream A (`kernel/state.py`) | the new `unreadable_stored_files` walk OPENED every stored `*.yaml` while the document scan in the same validator was refusing to open the very same over-sized file and saying why. On a hook path with a time budget that reads a business export in full on every merge. Fixed: the walk is bounded by `report.DOCUMENT_MAX_BYTES`, and `oversized_stored_files` is the other half so the skip is not silence -- reported only for an ITEM file, because a DOCUMENT is already named by the scan (the line that decides is `parse_id`, not a directory list) |
| `tools/test_hooks.py::test_scaffold_preset_and_map_sync` + `..._ps1_rolls_back_base_after_provider_collision` + `..._ps1_rejects_unknown_quoted_recorded_preset_before_mutation` + `..._ps1_rejects_duplicate_preset_keys_before_mutation` | stream B's `BUG-0277` precondition | the four build a SYNTHETIC staging, and the installer now refuses a staging that carries no trust recorder and one that does not hash to its own VERSION. All four came back with THAT refusal instead of their own subject -- and one of them asserts a refusal, so it was passing for the wrong reason until the message was compared. Fixed with one helper (`_stage_the_trust_recorder`): the recorder, the kernel package beside it (the recorder is RUN, not just looked for -- `ModuleNotFoundError: No module named 'kernel'` was the second step), and the real stamp over the tree as it stands, called where the kit tree is COMPLETE |

A SIXTH FINDING CAME OUT OF THE REPAIR ITSELF, and it is the "a named test must be able to FAIL"
class: `_stage_the_trust_recorder` was first called right after the `kit = ...` line, so the stamp
was computed over a tree the test then went on to write -- and the refusal came back unchanged. The
call now stands at the END of each builder, and the difference is measured (2 of 4 green, then
4 of 4).


## THE DELIVERY FULL RUN  (18:22:09 -> 19:30:45)

    DELIVERY_RUN=TSK-0144 python -B -m pytest tools/ -q
    1 failed, 5077 passed, 14 skipped, 1 warning in 4116.31s (1:08:36)

EVD-0413 (`kind: test`, `result: pass`, `run_scope: full`, `related: PR-0012`) carries that line
verbatim. The ONE red is the S4 arbiter and nothing else; the eight reds of the first run are closed
at their mechanism, each with the selection that proves it.

The one WARNING is not mine and is named where it belongs: `project_memory/.audit/hook_events.jsonl`
carries CRLF in canonical state, which no tool write reaches (gate 1), so the sweep says so instead
of asking for it.

## THE GATE SUITE, as its own run  (19:37 -> 20:02:35)

    DELIVERY_RUN=TSK-0144 python -B -m pytest .claude/hooks/test_gates.py -q
    1 failed, 553 passed in 1493.73s (0:24:53)

It needed the delivery prefix too: gate 5 refused the bare line and named the rule
(`.claude/hooks/test_gates.py` is a declared surface at 1380 s). The ONE red is
`test_every_test_a_hole_names_is_one_that_exists`, and it named TWO stale hole pointers:

1. **`H158`, MINE** -- `BUG-0240.regression_tests` still named the node I turned around. Repaired
   through the kernel (`update BUG-0240`, a field change and not a transition), then
   `generate-index`, then the node re-run: that half is gone.
2. **`H138`, NOT REPAIRABLE BY ME, and the pointer is the small half of it.** `BUG-0221` is
   ARCHIVED with `status: ACCEPTED_EXCEPTION` and names
   `tools/test_design_conformance.py::test_a_record_is_written_even_when_the_checks_find_something_and_the_sighting_gate_still_opens`.
   A stream RENAMED that node to
   `test_a_draft_with_conformance_findings_is_refused_and_an_undecided_one_is_not` -- and the new
   docstring says what really happened: `BUG-0294`, "a rendered draft with findings no longer walks
   past the sighting gate". So the exception the USER granted describes behaviour that has been
   REMOVED: the gate refuses now (measured in that test: renderer rc 3, gate rc 2, and the
   undecidable counter-end rc 0). Two routes are closed to me and both were measured, not assumed:
   a tool write under `project_memory/**` is refused by gate 1, and the kernel has no writer for an
   archived item -- `update BUG-0221` answers "no active item BUG-0221 ... a finished item lives in
   the archive rather than among the active ones". An accepted exception whose reason is gone is the
   user's to retire, so this goes to the lead as a finding with its measurement rather than as a
   pointer patch.

## AFTER the delivery run: ONE docstring line, and why it was not another full run

`tools/test_review_procedure.py:1000` -- the first paragraph of the turned-around node now opens
with `BUG-0240`/`H158`. The reason is mechanical: `kernel.naming_tests.coverage_blocker` looks for
the defect's id in the docstring's FIRST paragraph (`DEC-0100` (3), `H195`), mine had it in the
second, and the batch dry check refused the merge line by name -- "none of those tests NAMES
BUG-0240 where a reader looks for a test's subject". Without the line the closing Evidence cannot be
read, so the line is load-bearing.

WHAT WAS RE-RUN INSTEAD OF THE 68 MINUTES, and why that is the honest trade: the change is a
docstring in one test file. It touches no kit file (`bump_kit_version.py` -> **unchanged x3**), no
behaviour and no assertion. Re-run: `tools/test_review_procedure.py tools/test_routine_feed.py` ->
**61 passed, 59.47 s**; `tools/test_repo_hygiene.py -k "pointer or naming_the_project or
project_reach_reader or unreadable"` -> **8 passed, 56.00 s** (the docstring readers); and the batch
dry check, which is what the line is for -> **0 refused**. A reader who wants the full surface over
this line has it in EVD-0413 minus one docstring.

## AC-5, prepared for the lead  (clock 2026-09-12 20:05)

`report.stock_rollup` read after the run, out of the rig beside the batch dry check
(`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0144/read_stock_rollup.py`, read-only):

* **89 rows** -- every one a defect that carries a PASSING `test` Evidence and still stands open,
  i.e. waiting for the user's verification click and nothing else.
* **0 rows** whose Evidence names a test that does not resolve (`unresolved=[]` in all 89). That is
  the same reader the batch lines are refused by, so the two agree.
* **68 of the 89** stand in the ten verification batch lines of this generation; **21 do not**, and
  they are named in `lead-lines.md` with what each is waiting for instead.
* **0 batch ids outside the rollup** -- no line asks for a click on something that is not ready.

## FINISHING RUNS  (clock 2026-09-12 20:08)

* `python tools/bump_kit_version.py` (the second call after the delivery stamp) -> **unchanged x3**
  (`2026.09.12-5`), asked again after every later `tools/`-only edit, still unchanged.
* `python tools/validate.py` -> **all structural checks passed** (no "VERSION not bumped").
* `python -m ruff check .` and `python -m ruff check user/` -> **All checks passed**.
* `python tools/pin_constitution_sections.py` -> 3 kits, 12 files, 125 sections, all pins current.
* mirror: `_routine.py` sha256 head `ff5c4e7f621c`, identical in dev = office = research;
  `pytest tools/test_hooks.py -k "identical or mirror or shared_kit"` -> 4 passed.
* **generate-index = store**, and MEASURED as idempotence rather than asserted: two consecutive runs
  differ in exactly the TIMESTAMPS and in nothing else -- `index.yaml`'s `generated_at` and
  `board.html`'s `<time data-generated-at=...>`, 2 lines in that file, 0 lines anywhere else
  (`mindmap.drawio.svg` `3b655075da31` and `plan.drawio.svg` `435580d8b9fb` byte-identical across
  both runs).
* NO commit, NO push, NO mint, NO BUG transition. One kernel `update` of `BUG-0240.regression_tests`
  (a field, not a status) and four `evidence` captures: EVD-0410..0412 per closed hole, EVD-0413 for
  the full run.

## THE SUITES THAT READ WHAT I CHANGED, and why those

Read off the predicate each change moved, not off habit (`DEC-0080` rule 2):

| what moved | who reads it | result |
|---|---|---|
| `report.installed_kit_paths` | `tools/test_pointer_sweep.py` (whole file: the new node plus the three-kit tripwire), `tools/test_hooks.py -k kit_repo_files` | 8 passed / green |
| `state._walk_stored_files`, `state.oversized_stored_files`, the validator's new finding | `tools/test_report.py`, `tools/test_migrate.py` (the two nodes that pin the bound) | green |
| `hooks/_routine.py` (all three kits) | `tools/test_routine_feed.py`, `tools/test_review_procedure.py`, `tools/test_role_contracts.py`, `tools/test_parallel_streams.py`, `tools/test_office_duties.py` (the office register is the second caller) | 132 + 99 passed |
| `_refusal_texts` / `_names_that_stop_the_role` (four other nodes call it) | `tools/test_hooks.py -k "refusal_reader or evidence_kind_or_verdict or evidence_command_a_text or refusal_text_names_a_kernel or every_command_a_role_is_handed or every_approval_kind_a_role_is_handed or every_span_that_presents_the_command_surface"` | 6 passed + the S4 arbiter |
| `kernel/holes.py::test_modules_under` | `tools/test_hooks_v2.py -k only_some_tool_caches`, and the hole readers in `.claude/hooks/test_gates.py` | green / green |
| `ledger_add.is_malformed` | `tools/test_finance_dashboard.py`, `tools/test_office_duties.py`, `tools/test_hooks_v2.py -k ledger` | 93 + 680 passed |
| `approvals.consumed_request` user sentences | `tools/test_hooks_v2.py -k "every_approval_refusal or non_minting_exit"` | 2 passed |
| the 15 hook-start call sites | `tools/test_hooks_v2.py -k "does_not_compile or launcher or chain or oversized or crashes or drains_stdin or fake or bytecode or importing_the_hook or minted"`, `tools/test_research_chain.py` | 58 passed / 10 passed |
| `_stage_the_trust_recorder` | `tools/test_hooks.py -k scaffold` | the four target nodes green |

Everything above also ran inside the delivery full run; the selections are what made each fix
measurable on its own.

## THE RIG, and what is left of it

`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0144/`
* `rig/` -- the `.git`-less snapshot the red-first mutations ran in (team-kits, tools, docs, user,
  README.md, CLAUDE.md, plus a two-file stand-in `.claude/hooks/` written for seam (c), because a
  shell line naming a hooks directory is refused to every caller, H80).
* `dry_check_lines.py` + `dry-check.txt` -- the ten batch lines, read-only against this store.
* `read_stock_rollup.py` + `stock-rollup.txt` -- AC-5's reading.

The two scripts are cited in `lead-lines.md` as where their measurements come from, so they stay
until the round is closed.

# Rework 1 -- against the verifier's round 1 (FAIL: B1 B2 B3), report read WHOLE (its own request)

Everything below is in `tools/**` except one COMMENT in `hooks/_routine.py`, which is a kit file and
is stamped for; no behaviour of any kit changed, so the delivery full run of 18:22 is not repeated
(`DEC-0050`) and the reading selections are named with their results.

## B1 | the S4 arbiter was no arbiter  (clock 2026-09-12 20:33)

`tools/test_hooks.py:7003-7013` (the reader), `:6990-7002` (the docstring), `_COMPUTED_FLAG_RX`
beside `_EVIDENCE_FLAG_RX`.

THE DEFECT, in the verifier's words and re-measured here: with the S4 patch applied the node did not
go green -- it moved to `.claude/hooks/gate_test_scope.py:709-719`, whose text is CORRECT. That
module builds the two flag NAMES at runtime (`--%s full --%s "…"`, from `RUN_SCOPE_FIELD` and
`RUN_COMMAND_FIELD`), and `_folded_string` yields the TEMPLATE, because the arguments are runtime
values. So the reader judged a string that is not the message the role gets -- the house rule "a
check must read the part that RUNS", one level down -- at a second file every role here is refused.
The user would have applied their patch and seen the same red.

THE FIX IS A DEFINITION AND NOT A SPELLING LIST: `_COMPUTED_FLAG_RX = --[^\sa-z]` is the COMPLEMENT
of the flag alphabet `_EVIDENCE_FLAG_RX` already declares. A `--` followed by something that is
neither a flag letter nor a space is a name the string builds at runtime (`--%s`, `--{}`,
`--{flag}`); a `-- ` in prose keeps its space and is not one. Such a call is NOT SPELLED OUT, which
is the same verdict the reader already gives a span with no flags at all.

MEASURED, in the rig -- and this time with the REAL gate files, placed from git (`git show
HEAD:.claude/hooks/<file>`), not with the two-file stand-in the first round used:

| rig state | node |
|---|---|
| unpatched, fixed reader | **1 failed**, culprit `.claude/hooks/gate_commit_evidence.py` -- and ONLY it |
| **S4 applied** (`apply_s4.py`, `ast.parse` green, `%s` count unchanged at 18), fixed reader | **1 passed in 2.94 s** |
| S4 applied, the computed-flag skip cut out (`if False`) | **1 failed**, culprit `.claude/hooks/gate_test_scope.py` -- the exact defect the verifier reported |

The docstring now says both halves (red until the patch, GREEN after it) and names what the reader
cannot judge and why.

**THE S4 PATCH DOCUMENT'S SENTENCE IS WRONG AND I DID NOT EDIT IT.**
`project_memory/staging/TSK-0141/s4-gate-commit-evidence-patch.md` says
"`.claude/hooks/gate_test_scope.py:709-712` already carries the pair and needs nothing". True of the
FILE, false of the reader as it stood this morning. What is true now: the file needs nothing, and
the reader no longer judges it, because it spells the two names through `%s`. That file is another
task's staging and this item's `forbidden_scope` excepts only `staging/TSK-0144/`, so the correction
is handed over here and in `lead-lines.md` instead of written into it -- one sentence, the lead's
file.

## B2 | the H196 sweep could not print its own finding  (clock 2026-09-12 20:30)

`tools/test_repo_hygiene.py:2767` -- `"%s:%d  %s" % one` over 4-tuples. The protection held (red
stayed red) but the message was a `TypeError`, so the protocol's red-first line ("14, then 15
findings with file, line, function and argv") was NOT reproducible with the shipped node. The cause
is mine and it is the same class twice in this round: a heredoc replacement whose pattern carried a
real newline where the file has `\n`, applied without an assertion -- the first of the two in that
script matched, this one did not, and nothing said so.

MEASURED, in the rig, with a forgetful fixture planted in a real suite file:

* shipped format: **`TypeError: not all arguments converted during string formatting`**
* `"%s:%d  %s()  %s" % one`: **`1 hook start(s) ... tools/test_hooks_v2.py:16386
  test_a_fixture_this_round_planted_to_see_the_finding_list()  [sys.executable, str(hooks /
  'gate_probe.py')]`** -- file, line, function and argv, as the protocol line claims.

(The first run of this measurement reported 15 instead of 1: the rig still carried my mutant copies
`m1.py`/`m2.py`/`m3.py` and `test_hooks_v2_head.py`, and `test_*.py` collects them. They are gone;
that the sweep SEES a new file next to an existing one is the reader working, not a defect.)

## B3 | the archive arm of H158 was load-bearing and uncovered  (clock 2026-09-12 20:45)

`tools/test_review_procedure.py` -- a FOURTH state in the named node, and a comment correction in
`hooks/_routine.py` (all three kits, mirrored `1333b554cc4a`).

The verifier's measurement was right and I reproduced it: a `PR` at `DELIVERED` is not terminal, so
nothing ever left `active/` and `read_anywhere` was never exercised. The fourth state takes the
delivered record to a terminal and ARCHIVES it, then demands that the duty still NAMES it.

THE TERMINAL IS `SUPERSEDED` AND NOT `ACCEPTED`, measured rather than chosen: `DELIVERED ->
ACCEPTED` is the confirming edge and the kernel refuses it without an acceptance approval ("a status
the supervised party can set itself is a status no gate may read as approval"), while an abandonment
terminal needs none. What is under test is the ARCHIVE arm; which terminal took the record out of
`active/` is not part of it, and `delivery_occasions` reads the end of the automaton and not a
chosen status.

RED-FIRST, per kit, because "red in all three" is three measurements and not one (the node's loop
stops at the first kit that fails, so each was cut on its own):

| cut | node |
|---|---|
| `read_anywhere` -> `read_item` in **dev-team** only | **1 failed**, "dev-team: an archived record is out of `active/` …" |
| in **office-team** only | **1 failed**, "office-team: …" |
| in **research-team** only | **1 failed**, "research-team: …" |
| nothing cut | **1 passed in 7.35 s** |

The mutation rig reports the sha256 of the three files on every run, so a mirror that drifted would
be visible rather than assumed (`d85e52ebb85f` mutated, `1333b554cc4a` shipped, identical each time).

THE COMMENT: "a task is ARCHIVED the moment it reaches its terminal status" was wrong -- archiving
is its own step (`kernel.state.archive`, the entry point's `archive` command) and no transition does
it. The comment now says that, says what archiving nevertheless costs an `active/`-only reader, and
names the fourth state that measures it.

## R2 | the short-row arm of `is_malformed`  (clock 2026-09-12 20:50)

A TEST ROW ONLY -- `team-kits/office-team/templates/repo/scripts/ledger_add.py` is unchanged:
`tools/test_hooks_v2.py::test_a_row_with_too_FEW_columns_stops_the_write_as_well`.

AND THE PATH IS THE MEASUREMENT: the first version of this row drove the APPEND, and cutting the arm
left it **green** -- the append refuses a short row through a second reader of its own. On
`--validate` the sentence comes only through `is_malformed`. Measured with the arm cut in the rig:

* `--validate` with the arm: `line 2 (L2026-0001): wrong number of columns` + five field complaints
* with it cut: the five field complaints and **no** column line
* the two nodes together, arm cut: **1 failed** (the new one), **1 passed** (the neighbour -- which
  is exactly why the neighbour was not the cover)

## R4 | a number at a second place  (clock 2026-09-12 20:51)

`tools/test_role_contracts.py:2258-2259` -- "62894 bytes" replaced by the pointer to
`tools/lead_package_sizes.json`, with the reason (it is re-measured by
`record_lead_package_sizes.py --write`, and a second copy ages at that moment).

## R5 | a false attribution in the hand-over  (clock 2026-09-12 20:52)

`project_memory/staging/TSK-0144/lead-lines.md` -- the sentence claimed four of the 21 rollup ids
were question rows of section 3. TWO are (`BUG-0237`, `BUG-0286`); `BUG-0203`/`BUG-0212` are not, and
the corrected sentence names the seven section-3 ids that are NOT in the 21 as well, so the lead can
check it rather than trust it.

## THE NAMED REMAINDERS (R1, R3, R7) -- one row each, mechanism first

| id | mechanism | what stands instead |
|---|---|---|
| **R1** | `tools/test_repo_hygiene.py::_starts_a_hook` follows an `argv` that a NAME holds (one hop, into the assignment), but not a PROGRAM WORD that a name holds: `program = os.path.join(tmp, "gate_write_scope.py"); subprocess.run([sys.executable, "-B", str(program)], …)` is invisible to it, because the word it inspects is `str(program)` and the regex asks that word, not what the name was bound to. The class is "a program word a local name resolves", not the two spellings anyone happened to try | no victim today, measured by the verifier: with the extra element hop the sweep still reports `0` further forgetful starts, and four live call sites of that shape all name the project. The fix is the SAME `bound` hop applied to the program word |
| **R3** | `tools/test_hooks.py:9131-9137` argues "CANNOT RETURN" against "exits somewhere" with 45 vs 3 names, and the synthetic bundle in `test_the_refusal_reader_finds_a_stopper_this_repos_own_gates_spell` contains no function that refuses in one branch and RETURNS in another -- so the original over-wide rule stays green there. The measurement is real (re-measured by the verifier at 46 vs 3 and 55 vs 15) but it lives only in prose | the arm that IS covered goes red correctly (the name-list cut: `AssertionError: []`). Closing it means one more probe function -- a `decide`-shaped one -- in that bundle |
| **R7** | `tools/test_migrate.py`'s three `oversize` nodes abort in SETUP inside a `.git`-less copy (`git could not read this repository's history`), so the prescribed red-first location cannot run that class at all. My own red-first for the document bound was therefore taken in the REPO by cutting and restoring the reader, which is the weaker form | the bound is measured at both ends by the verifier in his own copy (bound removed -> `test_migrate` red; `oversized_stored_files` silenced -> `test_report` red). The rig rule and this test class need a decision: a copy WITH `.git`, or a fixture that does not ask git for history |

## RUNS OF THE REWORK, and the stamp it needed  (clock 2026-09-12 20:57)

The comment in `hooks/_routine.py` is a KIT file, so one more stamp was owed and taken:
`bump_kit_version.py` -> bumped **`2026.09.12-6`**, second call **unchanged x3**; `validate.py` ->
all structural checks passed; `ruff check .` and `ruff check user/` -> All checks passed. NOTHING
about any kit's behaviour moved -- a comment and a VERSION line -- so the delivery full run of
18:22 (EVD-0413) stands and is not repeated (`DEC-0050`); what was re-run is what READS the changed
files:

| selection | result |
|---|---|
| `tools/test_review_procedure.py tools/test_routine_feed.py tools/test_role_contracts.py tools/test_parallel_streams.py tools/test_office_duties.py tools/test_repo_hygiene.py tools/test_pointer_sweep.py` | **219 passed, 138.20 s** |
| `tools/test_hooks.py -k "evidence or refusal or scaffold or mirror or identical or shared_kit or kit_repo_files or command_surface or approval_kind"` | **51 passed, 6 skipped, 1 failed, 228.01 s** -- the one failure is the S4 arbiter on this UNPATCHED tree, which is what it is for |
| `tools/test_hooks_v2.py -k "ledger or malformed or too_FEW or only_some_tool_caches or approval_refusal or non_minting"` | **688 passed, 83.13 s** |
| `tools/test_review_procedure.py -k delivery_since_the_last_run` (the four-state node) | 1 passed, 7.35 s, and three separate reds under the per-kit cuts |
