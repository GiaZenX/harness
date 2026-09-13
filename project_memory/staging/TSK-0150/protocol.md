# TSK-0150 -- PR-0012 "Bug-Null", order 5 (single stream, DEC-0101)

Builder: harness-implementer (opus, high). Base: 92d746a, stamp 2026.09.13-3 -> **2026.09.13-5**
(two bumps: -4 after the last build change, -5 after the text rework the full run asked for; the
second is the correction DEC-0050 puts before the delivery, not a second round).
Scratch (red-first, .git-less): `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0150/`.
The runs and their durations are in `runs.md` beside this file; this is the argument, that is the
measurement.

## 0. Clock

| reading | what |
|---|---|
| 2026-09-13T09:06:18 | start; item + DEC-0112/0113/0111/0102/0100 + the five bug items read |
| 2026-09-13T09:20 | DEC-0112 built (kernel + tests), red-first seen |
| 2026-09-13T09:36 | DEC-0112 kit texts + H212 done |
| 2026-09-13T09:47 | DEC-0113 built, red-first seen; H59 done |
| 2026-09-13T09:52 | BUG-0197 built (kernel writer + kit reader), red-first seen |
| 2026-09-13T10:00 | BUG-0303 built, red-first seen |
| 2026-09-13T10:03 | BUG-0304 built (three mechanisms + one over-refusal caught by its own everyday row), red-first seen |
| 2026-09-13T10:04:39 | HALF REPORT: all five rows built and green in their selections; stamp 2026.09.13-4 |
| 2026-09-13T10:08 | ruff, validate, index = store, five EVDs, batch dry-check rc 0 |
| 2026-09-13T10:13 | the ONE full run started (attempt 1 truncated at 10:16 with no summary; see runs.md) |
| 2026-09-13T10:28..12:42 | the delivery full run: 4 failed, 5144 passed, 14 skipped, 2:14:18 -- EVD-0456 |
| 2026-09-13T12:46..12:52 | three of the four reds fixed at their mechanism and re-run green; `duty-done` into the command surface, no node id written as an example, the sections re-pinned; sizes re-recorded, stamp -5, ruff + validate green |
| 2026-09-13T12:53..13:37 | the gate suite as its own run: 3 failed, 552 passed, 44:22 |
| 2026-09-13T13:40 | the hole index regenerated from the store, index = store, EVD-0456 |

## 1. The rows

| id | change (file:line) | red-first row | naming node | suites | EVD |
|---|---|---|---|---|---|
| DEC-0112 / BUG-0296 | `team-kits/kernel/dispatch.py` (the whole acceptance-reader block, ~3181-3280) + the refused-ask `why` in `ladder_for_order`; `tools/test_ladder.py` rows retired into the measurement; the sentence in dev/research `ladder.yaml`, `constitution/AGENTS.md`, `skills/project-manager/SKILL.md`; `docs/holes/H212.md` | `rf-112`: `dispatch.py` back at 92d746a -> 3 failed, first `assert True is False` on "ein Test wird rot, ohne den Fix" | `tools/test_ladder.py::test_a_described_test_buys_nothing_since_the_prose_reader_is_retired` | test_ladder (61 passed / 43.7 s) | EVD-0451 |
| DEC-0113 / BUG-0151 | `kernel/backlog_types.py` (two optional fields on PR and RQ), `kernel/report.py` (`verification_missing_for_goal`), `kernel/approvals.py` (`_record_the_unverified_answer`, the acceptance manifest, `SPOKEN_MANIFEST_FIELDS`, the sentence), `kernel/cli.py` (`--unverified-answer`), `tools/conftest.py` (the fixture walks the sanctioned route), the two PM skills; `docs/holes/H59.md` | `rf-113`: five kernel files + conftest back at 92d746a -> 2 failed, `Failed: DID NOT RAISE ApprovalError` | `tools/test_approvals_dispatch.py::test_a_goal_with_no_verification_run_is_asked_about_once` | test_approvals_dispatch (235 passed / 122 s) | EVD-0452 |
| BUG-0197 / H113 | NEW `team-kits/kernel/duties.py` (`duty_key`, `done_keys`, `record_done`), `kernel/cli.py` (`duty-done`), `_routine.duty` gains `period` (mirrored x3), `office-team/hooks/_duties.py` (four feeds pass a period, the register drops a done key, the briefing prints the key, the docstring's own limit corrected); `docs/holes/H113.md` | `rf-197`: `_duties.py`, `_routine.py`, `cli.py` back at 92d746a and `kernel/duties.py` REMOVED -> 3 failed (`KeyError: 'key'`, `ModuleNotFoundError`) | `tools/test_office_duties.py::test_a_duty_recorded_done_drops_out_of_the_register_and_only_that_one` (+2 more) | test_office_duties + test_routine_feed (70 passed / 9.0 s) | EVD-0453 |
| BUG-0303 / H218 | `kernel/dispatch.py` `_origin_brings_its_own_criteria` + `architect_step_owed`; the pointer test replaced in the same direction; NEW `docs/holes/H218.md` | `rf-303`: `dispatch.py` back at 92d746a -> 1 failed, `architect_step_owed(...)` False for the hollow origin | `tools/test_approvals_dispatch.py::test_an_origin_that_names_no_criterion_excuses_no_architect_step` | test_approvals_dispatch (same 235-run) | EVD-0454 |
| BUG-0304 / H219 | `gate_write_scope.py` (mirrored x3): `_command_word_at` / `_effective_command_word`, `_executed_input_redirect_targets`, `_EVALUATOR_WORDS`, and `_operand_words` reading from the command word; NEW `docs/holes/H219.md` | `rf-304`: the three gate copies back at 92d746a -> 4 failed; the first row is rc 0 with EMPTY stderr on `printf 'x' > run.sh ; A=1 ./run.sh` | `tools/test_hooks.py::test_the_write_and_run_rule_reads_the_effective_command_word_in_every_kit` (+1) | test_hooks selection (10 passed / 21.6 s) + mirror (3 passed) | EVD-0455 |

## 2. contracts changed (DEC-0111 (8))

| when | contract | callers grepped BEFORE / found | what was done |
|---|---|---|---|
| 09:20 | `dispatch.acceptance_is_test_shaped` stops reading prose; `_denies_a_test`, `_sentence_names_a_test`, `_complement_of`, `_mentions_a_test`, `_DENIES_RX`, `_CORRELATIVE_DENIERS`, `_PREPOSITION_DENIES_RX`, `_CLAUSE_END_RX`, `_DETERMINER_RX`, `_POSTMODIFIER_RX`, `_COMPOUND_TEST_RX`, `_VERDICT_RX`, `_RUNNER_RX` and their vocabularies REMOVED | grep over `*.py`/`*.md`: live callers only in `kernel/dispatch.py` and `tools/test_ladder.py`; prose mentions in dev/research `ladder.yaml` + constitution + PM skill, `docs/holes/H212.md`, two historical log rows | all live callers rewritten; the rows in `docs/reviews/phase0-disposition.md` and the H194 wishlist row left as history |
| 09:22 | the lease `why` on a refused cheap-rung ask: `"refused: the acceptance names no test, only a description"` -> `"... names no test in the shaped form -- write the test's address ..."` | grep of the old sentence: `tools/test_ladder.py` (3 sites), `tools/test_light_kit.py` (1) | all four rewritten |
| 09:44 | `approvals.create_pending_request` takes `unverified_answer=`; the `acceptance` kind WRITES the goal before it builds its manifest; the acceptance manifest gains two optional keys | grep of `create_pending_request`: the kernel CLI branch, `tools/conftest.py` (`approve`, `walk_to_status`) and ~90 test call sites -- all of kind scope/delivery/routine/analysis. The ONLY `acceptance` caller in the whole tree is `conftest.walk_to_status` (generic, through `required_approval_kinds`) | CLI branch + `walk_to_status` updated; the fixture asks the KERNEL whether the question is owed instead of assuming it |
| 09:44 | `backlog_types.OPTIONAL_FIELDS` gains two keys on `PR` and a new `RQ` entry | the contract table; readers are `required_fields_of` / `_contract_fields` | both roots carry `unverified_acceptance_answer` / `unverified_acceptance_missing`; both are optional, so no stored goal becomes a validator error |
| 09:46 | `approvals.SPOKEN_MANIFEST_FIELDS` is NEW: manifest keys that must stand in the question SENTENCE, not only in the compared option | new reader, no prior callers | two-ended tripwire beside it |
| 09:50 | `_routine.duty(what, due, source)` -> `duty(..., period="")`, mirrored in three kits | callers: four in `office-team/hooks/_duties.py`, two in `_routine.routine_duties`; `dev`/`research` call `routine_duties` and never `duty` directly | every shipped feed passes a period; the default keeps a third-party caller working and is named as wrong-for-many-duties in the docstring |
| 10:00 | `dispatch.architect_step_owed` asks the VALUE of the origin's criteria list | callers of `_carries_its_own_criteria`: `dispatch.architect_step_owed` and two tests | the type predicate stays (it is the first half); the value half is a new reader one caller up |
| 10:03 | `gate_write_scope._stage_verb` now derives from `_command_word_at`; `_operand_words` starts after the command word instead of at index 1 | callers of `_stage_verb`: 9 sites in the same file; of `_operand_words`: 2 | one walk for both facts -- splitting them cost a measured over-refusal inside this round (below) |
| 12:53 | ...and the grep MISSED a caller outside the kits: `.claude/hooks/test_gates.py` PARSES the kits' `_stage_verb` SOURCE for its prefix branches, so moving the walk took the whole gate suite down at COLLECTION. The reader now follows the CALL GRAPH from `_stage_verb` breadth-first instead of pinning a name -- a fixed depth was tried and was wrong within the hour, because the walk sits two hops down | callers found by grepping `_stage_verb` in `*.py`: 9 in the kit file + 3 in `.claude/hooks/test_gates.py` -- the last three were read as "the test of the kits' gate" and not as a caller of its SHAPE | `_the_kits_prefix_walk` in `.claude/hooks/test_gates.py` |
| 13:40 | the hole table in `docs/POST_V2_WISHLIST.md` is GENERATED from the items, and five rows had been edited by hand | the generator is `tools/migrate_holes.py --reindex`; the gate test that holds it is `test_the_hole_index_in_the_document_is_the_one_the_items_generate` | the section regenerated; the prose moved into the five `docs/holes/*.md` files, which is where a generated index cannot lose it |

## 3. What the round measured about itself

**The mutation row found the defect, not the review.** `test_the_shaped_form_is_an_address_at_three_levels`
was written with one mutation per level (DEC-0111 (6)) and the TYPOGRAPHY row went green under its
own mutation on the first run: `_path_names_a_test` stripped quotes and backticks a SECOND time, so
the level had two owners and neither could be measured. That is the shape DEC-0111 (6) is about, and
it was caught by the rule rather than by a reader.

**An everyday row caught an over-refusal I introduced.** Closing the prefix class made
`A=1 ./build.sh` -- a line that writes nothing -- rc 2 in all three kits, because `_operand_words`
assumed `stage[0]` is the command word and therefore counted the command word itself as an operand.
The row was in the test before the fix was written, which is the only reason it was seen in this
round instead of in a verification one.

**One deviation from the order's wording, measured rather than argued.** DEC-0112 says "the lead
texts of the kits" and DEC-0113's consequences say "the three PM lead skills". Both were written
into TWO kits, not three, and the reason is the kernel: `backlog_types.ROOT_TYPE_BY_KIT` is
`{dev-team: PR, research-team: RQ}` and `approvals.APPROVAL_TRANSITIONS` carries an `acceptance`
edge for PR and RQ only, so the office kit has no goal to accept and no acceptance question to ask;
and the office `ladder.yaml` declares `build: pin` (a bare rung, default == floor), so an ask below
the default hits the floor branch and `acceptance_is_test_shaped` is never consulted there. Writing
either sentence into the office texts would have promised a mechanism that kit does not have.

## 4. What was deliberately NOT closed, each with its measurement

* **BUG-0303's second class.** An origin that DOES carry criteria still excuses the architect step
  while the order's `acceptance_refs` may name a criterion that exists only on the ROOT --
  `validate_dispatch` resolves against root + origin + amendments together. Closing it means
  narrowing that universe, which is the other direction BUG-0303 offers and a contract change that
  reaches every running project. Measured as row (5) of
  `tools/test_approvals_dispatch.py::test_an_origin_that_names_no_criterion_excuses_no_architect_step`
  and written out in `docs/holes/H218.md`.
* **BUG-0304's prefix vocabulary.** `_command_word_at` steps over the prefixes `_stage_verb` always
  carried (assignment, `sudo`, `env`, `command`, `exec`, `time`, `nice`, `!`). `nohup`, `timeout`,
  `xargs`, `stdbuf` are not in it. The same vocabulary had to grow twice in this repository's own
  `_harness._executed_words`, so the entry says so instead of claiming a closed class.
* **PowerShell's evaluator.** `_EVALUATOR_WORDS` holds `eval` alone. `Invoke-Expression`/`iex` do
  the same thing on the other path and are left out ON PURPOSE: the write-and-run pair was measured
  through a real shell on the POSIX path only, and a word in that set nobody drove through a shell
  is a claim rather than a rule. Named in the code, in `docs/holes/H219.md` and in the test.
* **BUG-0197's archived-task blind spot in DEC-0113's neighbour.** `report.verification_missing_for_goal`
  reads the goal plus its ACTIVE orders, so a goal whose only verified order was archived before the
  acceptance reads as unverified and the user is asked a question they could have been spared. That
  is the over-asking direction; the other one would be silence about a goal nobody measured, which
  is the whole of H59.
* **BUG-0197's missing proof of the DOING.** The done record is a human's statement, not a receipt:
  there is still no submission confirmation, no payment record beyond the ledger column, no
  "handled" flag on a document. Written into `docs/holes/H113.md` as what remains.
* **BUG-0303 as a hook PROCESS.** The measurement in this round is against `dispatch.create_lease`
  and `dispatch.validate_dispatch` in-process -- the same functions the shipped `gate_dispatch`
  calls -- and NOT against the shipped hook as a process, which is how the original chain was
  measured (TSK-0122 verify round 2/3). Nothing here claims the process measurement; what is
  claimed is that the lease refuses, and that is what the test reads.
* **BUG-0069** was not touched (it closes after the user's CI patch), and no BUG was transitioned.
* **THE HANDBACK.** `project_memory/archive/BUG/2026/BUG-0237.yaml` line 41 (`regression_tests`)
  names `tools/test_approvals_dispatch.py::test_an_empty_origin_excuses_the_step_while_the_root_criteria_measure_it`,
  the test BUG-0303 was closed by replacing -- exactly as that test's own docstring said would
  happen. `.claude/hooks/test_gates.py::test_every_test_a_hole_names_is_one_that_exists` is red on
  it. The pointer sits in CANONICAL STATE on an ARCHIVED item, which is this order's forbidden
  scope and which no kernel command this repo has repairs (`sweep-pointers` only reports). It is
  named here and in `runs.md` rather than edited; the new name is
  `tools/test_approvals_dispatch.py::test_an_origin_that_names_no_criterion_excuses_no_architect_step`.
* **THE FULL RUN WAS NOT REPEATED** after the text-only rework that its own four reds asked for.
  What changed afterwards: four surface lists, five docstring/skill sentences, one refusal string,
  one hole document, two pin files, `.claude/hooks/test_gates.py`'s reader and the generated hole
  index. What was re-run instead: the three repaired nodes, `tools/test_ladder.py` and
  `tools/test_role_contracts.py` (98 passed / 75 s), the gate suite in full, plus ruff, validate,
  the stamp x4 and the index. A second 2 h 14 min run over a docstring edit is the cost DEC-0111
  measured; the decision is named here so the verifier judges it rather than discovers it.

## 5. Half report (a protocol section, never a message -- DEC-0102 (5))

At 2026-09-13T10:04:39 all five rows were built, each with its red-first run seen in a .git-less
copy and its naming node green in a selection; the stamp had just gone to 2026.09.13-4. What was
still open at that point: ruff, validate, index, the EVDs, the batch dry-check, the ONE full run and
the gate run. Nothing was left half-written: a next builder could have continued from row 1 of
section 1 above.


## Rework 1 -- after `verify-round-1.md` (FAIL: F1 F2 blocking, F3 F4 remainders)

Read whole: `verify-round-1.md` (67 lines) -- it is the order for this section, so the cost is
visible. Every row below was measured against the SHIPPED artefact, and the red-first line is the
verifier's own measurement reproduced under a mutation.

| clock | row | what changed | mutation that goes RED | selection |
|---|---|---|---|---|
| 14:24 | -- | the report read, rows planned | -- | -- |
| 14:33 | **F1** (blocking) | `kernel/state.py`: `_REQUEST_PATH_FIELDS` + `_request_path_offences` refuse DEC-0113's two fields in a CAPTURE body and in an UPDATE, exactly as `LEGACY_FIELD`/`_role_judged_offences` do; `_record_the_unverified_answer_locked` is the ONE door past it (no revision bump -- a goal's scope approval is signed on `revision` and these two fields are not hashed); `kernel/approvals.py` uses that door and its docstring now says what is built | `mutate.py f1-capture-and-update-guard` (both guard blocks removed) -> `Failed: DID NOT RAISE Exception` | `tools/test_approvals_dispatch.py::test_the_unverified_answer_has_one_writer_and_no_body_may_carry_it` |
| 14:38 | **F2** (blocking) | `gate_write_scope.py` x3: `_the_command_word_is_unknown` -- an OPTION where the command word belongs makes the word unknown and every operand of that stage is read as something it may start; plus the per-SOURCE attribution (a write and a run are compared across different sources), without which `env -i bash tools/ci.sh` would refuse itself | `mutate.py f2-unknown-command-word` (the predicate returns False) -> the five lines come back **rc 0 with empty stderr**, in all three kits | `tools/test_hooks.py::test_a_prefix_words_own_option_does_not_hide_the_command_word_in_any_kit` |
| 14:44 | **F3** | `office-team/hooks/_duties.py`: `_receivable_period` gives every ledger ROW a period of its own (the invoice number, else the row's place in its file), and `_kept_apart_when_two_share_a_key` drops NO duty whose key is not unique -- both stay listed, carry no key, and the paragraph says why | TWO mutations, both red: `f3-row-unique-period` -> the guard fires with the verifier's own digest `9fdce45d180fd1c2`; `f3-collision-guard` -> two colliding duties keep their key | `tools/test_office_duties.py::test_two_ledger_rows_without_an_invoice_number_are_two_duties` |
| 14:45 | **F4** | `kernel/approvals.py`: `_the_german_question` -- the bare sentence only where NO kind of run exists (DEC-0113's own wording), otherwise it names the kinds that are missing | `mutate.py f4-german-sentence` (`whole = True`) -> the partial case reads as total again | row (5) of `::test_a_goal_with_no_verification_run_is_asked_about_once` |

### One more defect, found while reworking and not in the report

The three H113 nodes were ORDER-DEPENDENT: green inside the full run and red when
`tools/test_office_duties.py` runs alone, with `cannot import name 'duties' from 'kernel'` out of
the HOME installation. The register reaches for a kernel through `_kernel.import_kernel`, which for
a project under `tmp_path` falls back to `~/.claude/team-kits` -- and whichever kernel lands in
`sys.modules` first is the one every later reader gets. The module now pins this repo's kernel at
import, with the measurement beside it. An order dependency is not a measurement.

### Documents

`docs/holes/H219.md` carries the option class as its own closed mechanism and says what the
`nohup` class still is AFTER it (such a word becomes the command word itself, so the stage is not
"unknown" and its operands are read as written); `docs/holes/H113.md` carries F3's two halves;
`docs/holes/H59.md` carries F1 and F4. The gate's own remainder paragraph says the same thing in
the file that enforces it.

### Delivery duties of the rework

ONE stamp after the last kit change: **2026.09.13-6** (second call unchanged). `ruff` clean,
`tools/validate.py` green, lead package sizes unchanged against the record, mirrors byte-identical
(`gate_write_scope.py` hash equal in three kits), the gate suite still COLLECTS (555 tests) and its
four nodes about the kits' prefix walk pass. Selections: `test_approvals_dispatch` 236 passed /
100 s, `test_state` 67 passed / 8 s, `test_kernel` 136 passed / 25 s, `test_office_duties` +
`test_routine_feed` 74 passed / 8 s, the write-and-run + mirror selection of `test_hooks` 16 passed
/ 22 s. NO new full run: nothing outside these rows changed behaviour, which is the condition the
order set.

### Evidence superseded

| item | superseded | new | why the claim moved |
|---|---|---|---|
| BUG-0151 | EVD-0452 | **EVD-0457** | the "only writer" is now built, and the German sentence is true for what is missing |
| BUG-0304 | EVD-0455 | **EVD-0458** | the closure claim gained a mechanism (the prefix option) that the old record did not cover |
| BUG-0197 | EVD-0459's subject | **EVD-0459** (supersedes EVD-0453) | "only that one" was false for two rows that name themselves no other way |

BUG-0296 (EVD-0451) and BUG-0303 (EVD-0454) are unchanged -- the verifier measured both as
negative findings, including the BUG-0303 process measurement this round had left open. The batch
line was re-checked against a store copy inside a checkout after the new records: rc 0, 5 of 5,
0 refused, and the card now names EVD-0457/0458/0459.
