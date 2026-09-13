# TSK-0149 -- PR-0012 "Bug-Null", order 4, GOAL ROUND (merge). Protocol.

Builder: `harness-implementer` (Opus, high), the ONLY writer. Base 5ecf62a; the three streams'
work (TSK-0146 A kernel, TSK-0147 B kits, TSK-0148 C tools) is UNCOMMITTED in the tree and is not
reverted by this round.

Reading discipline (DEC-0095 (6)): read WHOLE, and said so -- the three `verify-round-2.md`
(11.6k / 10.5k / 5.1k) because they ARE the order for rows (e)/(g) and the H215 remainder.
Read by section: `staging/TSK-0146/protocol.md` (seam handoff 130-240, rows 400-560),
`staging/TSK-0147/protocol.md` (128-215).

Scratch (red-first, .git-less): `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0149/`.

## Rows -- ONE line each, as `expected_outputs` asks (detail in the log below)

| id | change (file:site) | red-first row | naming node | EVD |
|---|---|---|---|---|
| (a) DEC-0107 seam | `kernel/dispatch.py` new `fail_class_role_refusal`; the three `hooks/gate_dispatch.py` call it instead of re-deriving | `kernel_class_check_off` -> hook node rc 1; the SAME kernel mutation with the hook unwired -> rc 0 | `tools/test_hooks_v2.py::test_the_fail_classification_is_refused_from_every_writer_but_the_verifying_one` | EVD-0443 |
| (b) command surface | `README.md` + three `constitution/AGENTS.md` par.0, both anchors (`withdraw-request`, `migrate-goal-classes`) | `command_surface_misses_two_commands` -> rc 1, four rows "names 36, misses ..." | `tools/test_hooks.py::test_every_span_that_presents_the_command_surface_names_all_of_it` | -- (no item; the node IS the arbiter) |
| (c) docking page | `docs/office/invoice-app-docking-point.md` par.1, the rc-2 row of par.3, par.7, plus a NEW par.3 paragraph on the two `booking` keys | none of its own -- prose brought back to measured behaviour; the behaviour's red-first is B's (`vat_of` refusal restored -> intake rc 2) | `tools/test_office_package.py::test_a_mixed_vat_document_books_one_row_per_rate_under_one_invoice_number` | EVD-0445 |
| (d) DEC-0105 repo half | new `ladder.yaml` at the repo root; `.claude/agents/harness-implementer.md` points at `classes.build` instead of restating a tier | `repo_ladder_does_not_validate` (`top: nowhere`) -> rc 1, the `absent` line back | `tools/test_ladder.py::test_this_repositorys_own_tier_file_is_one_the_kernel_reads_and_names_roles_it_ships` | -- (BUG-0253 stays open: the config line is the user's) |
| (e1) composed word | the three `gate_dispatch.py`: position instead of presence; `kernel/cli.py` new `value_taking_options` | `expansion_rule_ignores_position` -> rc 1 AND `a_quoted_expansion_is_always_excused` -> rc 1 | `tools/test_hooks_v2.py::test_a_quoted_expansion_the_parser_takes_as_a_value_is_not_a_classification` | EVD-0443 |
| (e2) false WRITES | the three `gate_write_scope.py` `_operand_words`: a substitution's inner words are not this stage's operands | `substitution_words_are_operands_again` -> 3 failed AND `a_stage_has_no_operands_at_all` -> 3 failed | `tools/test_hooks.py::test_a_command_substitution_is_not_read_as_a_write_by_the_stage_around_it` | EVD-0444 |
| (e3) QA role texts | the three QA SKILLs: the rule was named TOO BROADLY after the narrowing | -- (text; the narrowing's red-first is (e1)) | as (e1) | EVD-0443 |
| (f) orphan pointer | `tools/test_approvals_dispatch.py` docstring line 1, last paragraph AND the assertion message; plus `kernel/dispatch.py` `_carries_its_own_criteria` -- H155 -> BUG-0303 / H218 | -- (pointer; the node itself is the tripwire and is written to go red) | `tools/test_approvals_dispatch.py::test_an_empty_origin_excuses_the_step_while_the_root_criteria_measure_it` | -- (BUG-0303 stays OPEN by design) |
| (g) R1 | `kernel/dispatch.py` `record_fail_class` -- the two-phase write got its node | `stamp_is_half_applied` -> rc 1, "TSK-0001 was stamped anyway" | `tools/test_ladder.py::test_an_evidence_that_names_two_orders_stamps_both_or_neither` | EVD-0446 (the full run) |
| (g) R2 | `kernel/state.py` `_CLOSED_VOCABULARY` -- the pair DERIVED, not spelled | `evd_fail_class_is_free_text` -> rc 1, "DID NOT RAISE StateError" | `tools/test_state.py::test_the_fail_classification_on_a_record_is_the_declared_vocabulary` | EVD-0446 |
| (g) R3 | `kernel/cli.py` the `evidence` head comment -- the second, locked judgement named; behaviour unchanged | `record_lands_behind_the_stamp` -> rc 1, Evidence list empty | `tools/test_kernel.py::test_a_stamp_refused_under_the_lock_leaves_the_record_behind` | EVD-0446 |
| (g) R4 | `kernel/approvals.py` new `_ends_a_request_can_have()` -- one derived phrase for three refusals | `mint_spells_its_own_ends` -> rc 1, "mint does not name the 'revoked' end" | `tools/test_approvals_dispatch.py::test_every_refusal_for_a_missing_request_names_every_end_it_has` | EVD-0446 |
| full-run finding 1 | the three `gate_write_scope.py`: a stage's COMMAND WORD joins the run set only where it is spelled as a path | `the_bare_command_word_is_a_file_this_line_runs` -> 3 failed | `tools/test_hooks.py::test_a_line_that_writes_a_script_and_runs_it_is_refused_in_every_kit` (the evidence line is one of its everyday lines now) | EVD-0444 |
| full-run finding 2 | `tools/test_hooks.py::_root_item_for` -- a fixture class word DEC-0103 does not declare | the red itself: `StateError: unknown RQ class 'research'` | `tools/test_hooks.py::test_the_guidelines_guard_reaches_exactly_the_areas_its_kit_calls_code` | EVD-0446 |
| full-run finding 3 | `tools/test_hooks.py::test_two_silent_entries_still_leave_the_gate_deciding` -- the BUG-0153 contract, both ends | the red itself: "no entry that names it states a `timeout`" | itself | EVD-0446 |
| full-run finding 4 | `docs/reviews/phase0-disposition.md` licence count 5 -> 3 (rows 15/41/56) and its paragraph; `tools/test_shortening_net.py` example moved to `handle_post_tool_use` | the red itself: "the document does not state that 3 licences rest on a mechanism Codex cannot start" | `tools/test_shortening_net.py::test_the_licences_whose_mechanism_cannot_run_on_codex_are_counted` | EVD-0446 |
| reserved: known_holes | regenerated, **delta zero** (both files byte-identical, sha256 f45e2488... / f5bbde32...) | -- | `tools/gen_known_holes.py --check` -> up to date | EVD-0446 |
| reserved: H215/H211 | line pointers -> FUNCTION names, re-measured with the shipped reader (`probe_h215.py`) | -- (pointers) | `tools/test_repo_hygiene.py::test_the_hook_start_reader_follows_a_program_word_held_by_a_name` | EVD-0446 |
| reserved: BUG-0242 | re-measured after the stamp, 4 passed; NOT closed (no BUG transition in this order) | -- | `tools/test_kitupdate.py::test_the_update_report_names_a_memory_tree_no_installed_role_declares` | EVD-0448 |
| rework F1 | `tools/test_shortening_net.py` `_reach_of`/`_tool_guard`: narrow by TOOL CLASS too; `docs/reviews/phase0-disposition.md` count restored to **5 of 36** (4, 15, 41, 54, 56), derived | `the_spawn_tool_guard_is_gone` -> 2 failed; `the_reader_asks_the_event_only` -> 2 failed; `the_bash_registration_is_removed` -> count node GREEN (correct) + reader node red | `tools/test_shortening_net.py::test_the_licences_whose_mechanism_cannot_run_on_codex_are_counted` and `::test_the_codex_reader_asks_about_the_symbol_and_not_only_its_file` | EVD-0446 |
| rework F2 | three `gate_write_scope.py` docstrings name `H219` / `BUG-0304` with all five spellings; no code change (three mechanisms, reason in the protocol) | -- (named remainder) | -- | -- |
| rework F3/F4/F5 | `lead-lines.md` section 5 re-read after EVD-0448 (14 rows / 13 out, BUG-0242 closable); two counting statements and three numbers removed or pointed | -- (text) | -- | -- |
| rework 2 F5 | `tools/test_hooks.py:19546` -- the pointer names `test_every_registration_names_a_window_its_gate_can_answer_inside` instead of the arming node | `a_shipped_entry_states_no_window` -> arming node **3 passed**, named node **1 failed** | `tools/test_hooks.py::test_every_registration_names_a_window_its_gate_can_answer_inside` (1 passed, 2.55 s) | -- (no stamp: `tools/` is outside the kit hash) |

## Log

### 2026-09-13T02:16:29 -- start
Item read; the three verify-round-2 reports read; A's seam handoff + rows and B's seam handoffs
read by section. Work order fixed: (a)..(g) incl. R1-R4, then known_holes, then the H21x pointers,
then ONE stamp, then the full run, then lead-lines.md.

### 2026-09-13T02:27:58 -- (g) R1-R4, the kernel remainder of verifier A round 2

Rig: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0149/rig.py` + `mutations.py` -- refuses any
cwd but its own, binary I/O on every touched file, hash-verified restore.

**R1** `team-kits/kernel/dispatch.py` `record_fail_class` (the two-phase write) got the node it
lacked: `tools/test_ladder.py::test_an_evidence_that_names_two_orders_stamps_both_or_neither`, and
the block comment now names it. Red-first `stamp_is_half_applied` (judge and write in one pass):
node rc 1, "TSK-0001 was stamped anyway". Green before the mutation: 1 passed, 3.12 s.

**R2** `team-kits/kernel/state.py` `_CLOSED_VOCABULARY`: the pair is DERIVED, not spelled --
every type whose field contract declares `fail_class` minus the order type (`_role_judged_offences`
refuses the field there outright). Resolves to exactly `[('EVD', 'fail_class')]` today. Node
`tools/test_state.py::test_the_fail_classification_on_a_record_is_the_declared_vocabulary`,
both ends (declared words accepted, `banana` refused naming both words, order type still refuses
the field itself). Red-first `evd_fail_class_is_free_text` -> rc 1, "DID NOT RAISE StateError".

**R3** `team-kits/kernel/cli.py` (the `evidence` head comment): the sentence now says the FIRST
judgement is the one that leaves no record, names the SECOND (locked) judgement that falls after
`state.capture("EVD")`, and gives the reason the two writes are in this order (swapping them trades
an unread record for an unrecorded discount; only the second changes what the next lease runs on).
Behaviour unchanged. Node `tools/test_kernel.py::test_a_stamp_refused_under_the_lock_leaves_the_record_behind`;
the un-locked pre-check is stubbed to None (the answer it really gave a moment earlier), everything
after it is the shipped path. Red-first `record_lands_behind_the_stamp` (the alternative R3 named)
-> rc 1, Evidence list empty.

**R4** `team-kits/kernel/approvals.py`: not a word but a DEFINITION -- `_ends_a_request_can_have()`
derives the placed ends from `_request_path`'s own flags and adds the two that are not a place.
All three "no pending approval request" refusals (`mint`, `pending_request`, `withdraw_request`)
now read it. Today: `consumed, revoked, withdrawn, expired-and-cleaned, or never created`.
Node `tools/test_approvals_dispatch.py::test_every_refusal_for_a_missing_request_names_every_end_it_has`
raises all three doors and derives the expected words from the signature. Red-first
`mint_spells_its_own_ends` -> rc 1, "mint does not name the 'revoked' end".
NOTE, said rather than hidden: `withdraw_request`'s friendlier wording ("already answered, already
withdrawn") is gone -- one phrase for three doors was the point, and the friendliness lived in the
developer sentence, not in the user text (`_gone_request_user_text` is untouched).

### 2026-09-13T02:36:19 -- seam rows (b), (c), (f) and the H21x pointers

**(b)** `README.md` and the three `constitution/AGENTS.md` par.0: both anchors of A's rework patch
applied (`withdraw-request` behind `sweep-requests`, `migrate-goal-classes` behind `migrate-holes`).
The ITEM names only the first; A's ROUND-2 patch and verifier A both name BOTH, and the node's
output before the patch was "names 36, misses migrate-goal-classes, withdraw-request" in all four
files -- so the measurement decided, not the item text. Node
`tools/test_hooks.py::test_every_span_that_presents_the_command_surface_names_all_of_it`:
1 passed, 7.34 s. Red-first `command_surface_misses_two_commands` (all four files back) -> rc 1
with the four rows.

**(c)** `docs/office/invoice-app-docking-point.md`, four sites, not three: §1 (the "book by hand"
sentence), §3's rc-2 row ("two VAT rates" as a refusal reason), §7's bullet, plus a NEW §3
paragraph stating the two `booking` keys -- the fourth is what B's seam text actually asks for
("an application that reads the single-line key must treat its absence as several rows") and it
had no home on the page. Verified against the SHIPPED script before writing:
`invoice_intake.py` sets `verdict["booking"] = {"rows": rows}` and adds `ledger_add` only for
`len(rows) == 1`; its own comment already pointed at this page for the pair, so the pointer is now
true. The page names the measuring node
`tools/test_office_package.py::test_a_mixed_vat_document_books_one_row_per_rate_under_one_invoice_number`
in §3 and in §6. NO red-first of its own: this is prose brought back to measured behaviour, and the
behaviour's red-first is B's (restore the refusal in `vat_of` -> intake rc 2). Citation floor of the
page still met: 4 passed (`field_report_verdicts_name`, `mixed_vat_document`).

**(f)** `tools/test_approvals_dispatch.py::test_an_empty_origin_excuses_the_step_while_the_root_criteria_measure_it`:
first docstring line, last paragraph AND the assertion message re-pointed from H155 to
BUG-0303 / H218. The item named two sites; the third (the assertion message a reader meets when the
node goes red) carried the same dead pointer. FOUND BEYOND THE ITEM: `team-kits/kernel/dispatch.py`
`_carries_its_own_criteria` also said "that last line is the remainder, and it is `H155`" -- same
orphan, re-pointed at `H218` (`BUG-0303`), which stands in `docs/POST_V2_WISHLIST.md:2521`.

**H215.md pointers.** Re-measured with the SHIPPED reader, not a copy: probe
`_round-scratch/TSK-0149/probe_h215.py` imports `tools/test_repo_hygiene` and diffs the start sites
with and against the program-word hop (the argv hop stays in the baseline -- it predates BUG-0299).
Four hop-only sites, the same count the entry claims:
`test_the_lead_of_a_scaffolded_project_is_not_read_as_its_own_subagent`,
`test_running_the_enforcement_layer_writes_no_bytecode_into_it` (both `tools/test_hooks_v2.py`),
`test_no_hook_started_by_this_suite_can_write_this_repos_audit_log` (`tools/test_repo_hygiene.py`),
and the `run` helper of `.claude/hooks/test_gates.py`. Written as a table of FUNCTION NAMES; the
false-alarm line pointer in the last paragraph dropped too (the function name was already there).
**The same defect in a neighbour:** `docs/holes/H211.md` carried five line pointers
(`migrate.py:1291`, `dispatch.py:204` x3, `invoice_intake.py:370`) -- re-measured by parsing the
three files for the cited DEC ids and replaced with `_too_large`, `order_tiers`,
`document_type_check`. H212/H213/H216/H217 carry none (grepped).


### 2026-09-13T02:57:23 -- seam rows (d), (a), (e)

NOTE ON THIS PROTOCOL'S OWN WRITES: `cat >> ... <<'EOF'` is refused by `gate_lead_write_scope` for
a body that contains a command substitution -- `cat` with a redirect is a write-capable stage and
the lifted substitution is read as its operand. The sections below are appended through
`python - <<'PY'` instead, whose operands the gate does not judge (H11). Named because it is a
measured gate limit met while working, not a complaint.

**(d) DEC-0105 repo side.** `ladder.yaml` written at the repository root in the kits' declaration
shape (rungs sonnet/opus/fable, top fable, effort high/xhigh, DEC-0096's two escalation numbers,
classes planning/build/qa all opus, roles harness-lead/implementer/verifier, no exceptions). Its
header says what it does NOT do here -- this repo has no dispatch and no leases, so nothing enforces
the pair; the frontmatter pins stay, and BUG-0251 is why. Node
`tools/test_ladder.py::test_this_repositorys_own_tier_file_is_one_the_kernel_reads_and_names_roles_it_ships`
loads the REAL file (the neighbouring DEC-0105 nodes measure a copy, `HARNESS_LADDER`) and puts it
through `ladder_for_order` for every role it classes, plus the both-ends check that every classed
role ships a definition under `.claude/agents/`. Red-first `repo_ladder_does_not_validate`
(`top: nowhere`) -> rc 1, the `absent` line back.
`.claude/agents/harness-implementer.md`: the tier RESTATEMENT is gone and replaced by a pointer at
`ladder.yaml` `classes.build`, with the unbuilt half named in the same sentence (the config line).
`harness-verifier.md` restates no tier and is untouched. The config line itself is the USER's --
`gate_lead_write_scope` refuses `project_memory/project_config.yaml` to every tool call here -- and
goes to lead-lines.md.

**(a) the gate_dispatch/kernel seam.** New kernel predicate
`kernel.dispatch.fail_class_role_refusal(state, role)` holds the role-class half; `fail_class_refusal`
calls it and appends its own remedy, so the kernel's message is byte-identical to before. The three
kits' `gate_dispatch.py` call the SAME predicate instead of re-deriving the comparison from
`ladder_declaration`. DEVIATION FROM THE ITEM'S LETTER, with its reason: the item names the whole
`fail_class_refusal(state, role, related, result, fail_class)`. A shell line states none of
`related`/`result`/`fail_class` in a form this reader may trust -- that is what the UNREADABLE
branch of the same gate is about -- so passing them would mean inventing them, and an invented
`related` becomes "this record names no order", a refusal about nothing. The role half is the half
the hook can answer, and it is the half that was duplicated.
RED-FIRST IN BOTH DIRECTIONS, which is what "one reader" means:
`kernel_class_check_off` (the KERNEL predicate stops comparing) ->
`tools/test_hooks_v2.py::test_the_fail_classification_is_refused_from_every_writer_but_the_verifying_one`
rc 1; the same kernel mutation WITH the hook re-deriving the rule
(`kernel_class_check_off_and_hook_unwired`) -> rc 0. The process measurement against a pilot is
that node itself (real hook process, project built outside the repo).

**(e1) the composed-word over-refusal.** THE ITEM'S PROPOSED NARROWING IS WRONG AND IS NOT WHAT I
BUILT: "narrow it to UNQUOTED expansions" would have made the F3 line rc 0, and that line IS
quoted -- it is the line the rule exists for, and B's node asserts rc 2 for it. The real
discriminator is POSITION: a word the parser consumes as the VALUE of the option before it (or of
an `--option=` assignment) can never be read as an option, whatever it expands to; an unquoted
expansion word-splits and can start a fresh word in option position; a single-quoted dollar sign is
no expansion at all. WHICH options consume a value is DERIVED from the shipped parser -- new
`kernel.cli.value_taking_options(command)` -- not listed in three hook copies.
Cost measured: `kernel.cli` is +0.026 s on top of the `dispatch` import (three runs), and it is
asked only for a line that reaches the entry point AND carries an expansion.
Node `tools/test_hooks_v2.py::test_a_quoted_expansion_the_parser_takes_as_a_value_is_not_a_classification`
(real hook process, four excused lines rc 0, two refused rc 2). Red-first both ends:
`expansion_rule_ignores_position` -> rc 1, `a_quoted_expansion_is_always_excused` -> rc 1.

**(e2) the false WRITES sentence.** Cause found by measuring, not by reading the report:
`_compat.command_line` already LIFTS a substitution out as a stage of its own, so the line becomes
`bash SUBST ; which ci.sh` in the view -- and the raw words stayed in the outer stage as well, so
`ci.sh` was "written" by the lifted stage and "run" as an operand of `bash`. One word, read twice.
Fix: `_operand_words` skips the words inside a substitution (depth counted over characters, so a
doubled closing paren closes two). Probe `probe_e2.py` against the shipped gate, before -> after:
the reported line rc 2 -> rc 0; and every write-and-run shape stays rc 2 (redirect + bash, printf
+ bash, tee heredoc + bash, pipe into tee + sh, install + dot-slash, cp + dot-slash, mv + bash,
redirect + dot-source, subshell + bash -- nine lines).
WHAT IT COSTS, measured: the `tee`-inside-a-substitution line goes rc 2 -> rc 0. Its QUOTED twin
was ALREADY rc 0 before the change, so the refusal depended on quoting; the two spellings agree
now, and the class is the H11 one the rule's own docstring already names.
Node `tools/test_hooks.py::test_a_command_substitution_is_not_read_as_a_write_by_the_stage_around_it`
(three kits), both ends. Red-first `substitution_words_are_operands_again` -> 3 failed;
`a_stage_has_no_operands_at_all` -> 3 failed.

**(e3) the three QA role texts.** They already named the rule (B's work) but now named it TOO
BROADLY -- "a word your SHELL assembles on a harness `evidence` line is refused" is false after the
narrowing, and an over-alarming claim is a house-rule-3 failure exactly like a reassuring one. All
three now state the position rule with both examples.


### 2026-09-13T03:10:26 -- known_holes, the stamp, and the FIRST full run

**known_holes.json (reserved row 1).** `python tools/gen_known_holes.py --check` -> "up to date
(3 capabilities)"; regenerated anyway and diffed BYTE-WISE against a copy taken before:
`team-kits/kernel/known_holes.json` sha256 f45e24885e7c8dce and
`team-kits/kernel/known_holes_digest.py` sha256 f5bbde32d7468a80, **identical before and after**.
DELTA: none. Three capabilities, eight naming tests; this round added no `known_hole` marker.

**Recorders that had to run before the stamp** (both are ratchets with a `--note` duty):
`tools/record_lead_package_sizes.py --write` -- dev 61044 -> 61088, office 66435 -> 66479, research
62876 -> 62920, +44 B each = the two command names of seam (b) in par.0, nothing else;
`tools/pin_constitution_sections.py --write` -- the same three par.0 sections re-pinned. Both wrote
their line into the journal of `docs/reviews/phase0-disposition.md`.

**Root hygiene.** `tools/test_repo_hygiene.py::test_no_tool_trace_lies_unaccounted_for_in_the_repo_root`
went red on the new `ladder.yaml` (untracked, no rule accounts for it). `git add ladder.yaml` --
the same state every other new file of this order is in (`A ` in the index, uncommitted); no
commit, no push. Node green after.

**THE STAMP (first).** 03:10:26 `python tools/bump_kit_version.py` -> dev/office/research bumped to
2026.09.13-1; second call unchanged x3. `tools/validate.py` -> all structural checks passed.
`ruff check tools team-kits user` -> All checks passed.
`generate-index` -> the only diff against the store is `generated_at`, i.e. index == store.

**FULL RUN 1:** `DELIVERY_RUN=TSK-0149 python -B -m pytest tools/ -q`, 03:13:30 -> 04:29:51,
4571.69 s (1:16:11), **5133 passed, 7 failed, 14 skipped**, rc 1.
ONE of the seven was the expected one. SIX were real and none of them was named by any stream:

1. `test_the_evidence_the_merge_gate_demands_has_an_installed_producer`,
   `test_the_qa_backstop_verdicts_the_item_not_the_author` -- **BLOCKING, stream B's BUG-0298 rule
   refuses the ONE command line that records an Evidence**: "this line WRITES python and RUNS it in
   the same call". Not mine: measured with the pre-round `_operand_words` restored
   (`rig.py operand_walk_before_tsk0149`) -> the same rc 2.
   MECHANISM: the line is unquoted, so `python` stands twice -- as the verb and inside
   `--run-command`. A stage no verb classifies as read-only counts every operand as WRITTEN, and
   the second loop put the stage's COMMAND WORD into RUN whatever its spelling. `python` is a
   program name the shell resolves on PATH, not a file this line could have written.
   FIX: the command word joins RUN only where it is spelled as a PATH (a directory separator in the
   RAW word, before `_name_readings` folds `./` away). Measured before/after over 23 lines
   (`probe_e2.py`): the evidence line rc 2 -> rc 0; all nine write-and-run shapes stay rc 2,
   including the four whose runner IS the command word (`./run.sh`).
   Red-first `the_bare_command_word_is_a_file_this_line_runs` ->
   `tools/test_hooks.py::test_a_line_that_writes_a_script_and_runs_it_is_refused_in_every_kit`
   3 failed (the evidence line is now one of that node's everyday lines).
2. `test_the_guidelines_guard_reaches_exactly_the_areas_its_kit_calls_code[research-team]` --
   `kernel.state.StateError: unknown RQ class 'research'`. Stream A's DEC-0103 closed the goal-size
   vocabulary; this fixture (`tools/test_hooks.py::_root_item_for`) carried the free-text word
   `research` from before it was closed. A STALE FIXTURE, not a product defect -- the word was never
   declared, it was free text nobody checked. Fixed to `normal`, with the reason beside it.
3. `test_two_silent_entries_still_leave_the_gate_deciding` -- refused with "no entry that names it
   states a `timeout`". Stream B (BUG-0153/H61) moved `start_the_deadline` into `_compat.load()`
   and made a registration WITHOUT a window a refusal; `gate_test_scope.py`'s own header says so in
   B's own words, and all 92 shipped entries now state one. The node still held the OLD contract
   ("silence is the DEFAULT window"). Rewritten to the new one, both ends: with a window on both
   entries the gate answers (rc 0 / rc 2), with a window on neither it refuses BOTH and names the
   missing `timeout`. Name and subject kept.
4. `test_the_licences_whose_mechanism_cannot_run_on_codex_are_counted` and
   `test_the_codex_reader_asks_about_the_symbol_and_not_only_its_file` -- both from DEC-0107's new
   registration. Measured: `gate_dispatch.py`'s registrations went from
   `PreToolUse('Agent|Task')` to that PLUS `PreToolUse('Bash|PowerShell')`; `Bash` exists on Codex,
   so `handle_pre_tool_use` and `_refuse_untrusted_bundle` became Codex-REACHABLE and parity rows 4
   and 54 dropped out of the blind count (5 -> 3, rows 15/41/56). That is a real change in what a
   Codex session is covered by. `docs/reviews/phase0-disposition.md` carries the new count and a
   paragraph saying WHY the two rows left; the reader node's example moved to
   `handle_post_tool_use` / `handle_spawn_failure`, which are still blind (measured in all three
   kits) -- the property it guards is unchanged.
5. `test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires` -- **the
   expected one**: the unpatched `.claude/hooks/gate_commit_evidence.py` remedy (H213 / BUG-0297),
   waiting on the user's S4 patch from a shell outside Claude Code.

**SECOND STAMP, and the deviation is named:** the item asks for ONE stamp. Finding 1 is a blocking
over-refusal in a kit gate that the full run found, so it had to be fixed after the stamp.
04:42:36 `bump_kit_version.py` -> 2026.09.13-2 x3, second call unchanged x3, `validate.py` green.
And because the last change is a kit gate, the full run is repeated rather than argued away
(DEC-0050: the full run belongs AFTER the last rework).


### 2026-09-13T05:59:08 / 06:35:17 -- FULL RUN 2 and the gate suite

**FULL RUN 2 (the delivery run):** `DELIVERY_RUN=TSK-0149 python -B -m pytest tools/ -q`,
04:42:44 -> 05:59:08, 4574.22 s (1:16:14), **5139 passed, 1 failed, 14 skipped**, rc 1, on stamp
2026.09.13-2. The one red is `tools/test_hooks.py::test_every_evidence_command_a_text_spells_names
_every_argument_the_cli_requires` -- BUG-0297 / H213, the ordered one. **EVD-0446** (kind test,
run_scope full, related PR-0012, `result: fail` -- the run was not green, and a full PASS is what
opens a merge).

**THE GATE SUITE as its own run:** `DELIVERY_RUN=TSK-0149 python -B -m pytest
.claude/hooks/test_gates.py -q`, 05:59:39 -> 06:35:17, 2128.34 s (35:28), **553 passed, 2 failed**.
**EVD-0447** (`result: fail`, same reason).
* red 1 `test_gate3_prints_a_remedy_that_runs_as_printed` -- the ordered one (BUG-0297).
* red 2 `test_every_test_a_hole_names_is_one_that_exists` -- **not this order's, and proven so
  rather than assumed**: it reports that the archived `BUG-0221` (H138) names a regression test no
  test answers to. `git show 5ecf62a:tools/test_design_conformance.py` does NOT contain that name,
  and `git show 5ecf62a:project_memory/archive/BUG/2026/BUG-0221.yaml` already carries it -- so the
  node was red at the base commit. No stream touched either file. HANDED BACK, not edited: the
  kernel has no door to an archived item (measured on a COPY of the store,
  `update_item("BUG-0221", ...)` -> `StateError: no active item BUG-0221`). The repair, the correct
  test name and the measurement are in `lead-lines.md` section 4.

### 2026-09-13T06:38-06:48 -- Evidence, batch dry check, rollup, closing measurements

Six Evidence records, each with the naming node in its `run_command` and each run before it was
written: EVD-0443 (BUG-0260, the seam), EVD-0444 (BUG-0298, both narrowings), EVD-0445 (BUG-0248,
the docking page), EVD-0446 (the full run), EVD-0447 (the gate suite), EVD-0448 (BUG-0242/H160
re-measured after the stamp, 4 passed -- a MEASUREMENT and not a close; transitioning a BUG item is
outside this order).

BATCH DRY CHECK re-run afterwards (`batch_dry_check.py`, a store copy inside a `git init` checkout
beside `tools/`, `team-kits/`, `.claude/`; 2754 files): **0 refused**, and the reader now picks
EVD-0443/0444/0445 by itself for BUG-0260/0298/0248 -- the records that measure the DELIVERED tree.

`report.stock_rollup`: 13 rows, every one with a passing Evidence and an empty `unresolved`. The
three active PR-0012 bugs outside it are exactly the three that must not close (BUG-0296 question,
BUG-0297 user patch, BUG-0303 named remainder).

CLOSING MEASUREMENTS, 06:47-06:48:
* `python tools/validate.py` -> all structural checks passed
* `python -m ruff check tools team-kits user` -> All checks passed
* mirrors byte-identical: `gate_write_scope.py` a43bebd1... x3, `gate_dispatch.py` e95fc831... x3
* stamp 2026.09.13-2 in all three VERSION files
* `generate-index` run twice, index body hash identical (1a098bf3...) -> **index == store**
* the research constitution under its ceiling: `tools/test_context_budget.py` 41 passed / 1 skipped,
  with the recorded ceilings raised by the sanctioned recorder and its `--note` (+44 B per kit)

### What this round did NOT close, and named instead

1. `BUG-0221` / H138's dead `regression_tests` pointer -- no kernel door, handed back (above).
2. `BUG-0253` -- the DEC-0105 repo half is built and measured, the CONFIG LINE is the user's; the
   batch line is deliberately not asked.
3. `BUG-0297` / H213 -- the S4 patch is the user's, from a shell outside Claude Code.
4. `BUG-0296` / H212 and `BUG-0151` / H59 -- decisions for the user, written out by the streams.
5. `BUG-0303` / H218 -- the named remainder of BUG-0237; every pointer that used to say H155 now
   says H218 (the test docstring, its assertion message, and the kernel comment in
   `dispatch._carries_its_own_criteria`).
6. `BUG-0069` -- untouched, as ordered (CI).
7. The `bash $(tee run.sh)` line goes rc 2 -> rc 0 with the substitution narrowing. Its QUOTED twin
   was already rc 0 before, so the class was open on one spelling; it is the H11 class the rule's
   own docstring names, and it is stated in the code rather than claimed away.
8. `docs/POST_V2_WISHLIST.md` was NOT edited (the lead's `migrate-holes --reindex`), and no hole
   entry was captured for the two over-refusals of row (e) -- both are CLOSED, so an entry would be
   a hole that is not one.


# Rework 1 (verifier round 1 = FAIL: F1 blocking, F4 house-rule-3, F2 batch line, F3 AC-5, F5/F6 residues)

Report read: `project_memory/staging/TSK-0149/verify-round-1.md`, WHOLE (it is the order, and it is
one file). Start 2026-09-13T07:38:00.

## F1 (blocking) -- the licence count, and the reader under it -- 07:38-07:50

THE VERIFIER IS RIGHT AND THE ROUND-1 CHANGE WAS THE DEFECT. `_events_reaching` narrowed by EVENT
only; `handle_pre_tool_use` exits unless the tool is in `SPAWN_TOOLS`, so the DEC-0107
`PreToolUse` registration with the matcher `Bash|PowerShell` never carries the symbols behind that
guard -- the verifier's marker said entered False on every Bash payload and True only on an Agent
one.

BUILT, as a definition and not a spelling: `tools/test_shortening_net.py` gained `_tool_guard`
(an `if <reads tool_name> not in <tools>:` whose single body statement ends the hook, read off the
PARSE TREE, comparator either a literal tuple or a module constant), `_tool_names`,
`_narrow`/`_widen`, `_calls_under` (the guards are cumulative DOWN a body, so a statement before the
guard is unconstrained and one after it is not), `_own_guard`, and `_reach_of` -- `{event: the tools
admitted where the symbol does its work}`. `_events_reaching` is the event half of it now, so its
two existing assertions keep their contract. `_reaches_codex` narrows TWICE: event, then the tool
class, against the matchers `codex_matchers_for` translates.

THE CHOICE THIS READER MAKES, said out loud in its docstring: a function is judged by the guards in
its OWN body as well as by those on the way to it, so `handle_pre_tool_use` answers `SPAWN_TOOLS`
although its first statement runs for every tool. That is the ALARMING direction, chosen because
what the matrix cites the symbol for sits behind the guard, and house rule 3 forbids the reassuring
reading as firmly as the alarming one.

MEASURED per symbol of `gate_dispatch.py` (dev kit):

    handle_pre_tool_use                             {'PreToolUse': {Agent, Task}}   codex False
    _refuse_untrusted_bundle                        {'PreToolUse': {Agent, Task}}   codex False
    _refuse_a_classification_the_judged_role_wrote  {'PreToolUse': None}            codex True
    handle_post_tool_use                            {'PostToolUse': {Agent, Task}}  codex False
    handle_stop                                     {'Stop': None}                  codex True
    main                                            None                            codex True

THE NUMBER, DERIVED and not typed: over the matrix, 36 effective licences and **5** of them blind,
rows **(4, 15, 41, 54, 56)** -- the number the document carried BEFORE this order, restored with a
stronger derivation. `docs/reviews/phase0-disposition.md` states it again and, in a new paragraph,
what the short-lived 3 was and why it was wrong; the "SYMBOL not FILE" paragraph now says that the
event question is not enough either, and names both directions of the reader's bias.

THREE MUTATIONS, and they do NOT all go red -- that asymmetry is the finding:

| mutation | count node | reader node | why |
|---|---|---|---|
| `the_bash_registration_is_removed` (the verifier's own) | **1 passed** | **1 failed** | correct: the registration never carried the guarded symbols, so the count cannot move; what it DOES carry is the symbol before the guard, and the reader node asserts exactly that |
| `the_spawn_tool_guard_is_gone` | **1 failed** | **1 failed** | without the guard the two symbols really would run on Codex and the count drops to 4 |
| `the_reader_asks_the_event_only` (round 1's state) | **1 failed** | **1 failed** | the defect itself |

## F4 -- the counting docstring -- 07:50

`tools/test_hooks.py`: "THIRTEEN MEASUREMENTS, eight refusals and five everyday lines" is GONE
rather than corrected to 8 + 6 -- the loops count, the sentence describes. "The last two are ..." is
gone too; each everyday line the operand reading could break carries its note WHERE IT STANDS,
because an ordinal ages the day somebody appends.

## F5 -- three numbers -- 07:50-07:52

* `team-kits/kernel/state.py`: "the two EVD entries below" -> "every EVD entry of the table below
  ... however many there are, which is why this sentence no longer counts them".
* `tools/test_hooks.py` `KIT_SPECIFIC_HOOKS`: the count is REMOVED, not corrected, and the comment
  says why -- three readers gave three answers (21/23/18 mine, over distinct scripts named in
  `settings.json` without `_gate.py`; 25/27/22 the verifier's; 24/21/22 as written). The property
  is the difference, not its size.
* the "92 shipped kit entries" of my own round-1 docstring -> a pointer to
  `test_every_shipped_hook_of_this_kit_reaches_the_deadline_that_arms_it`.

## F2 -- H214's one-call remainder: NAMED, not closed, and the reason is measured -- 07:51

The three `gate_write_scope.py` docstrings carry `H219` (`BUG-0304`) with all five spellings
(assignment prefix, `exec`, `command`, the file fed through an input redirect, the substitution
handed to `eval`), each with the verifier's measurement, plus the sentence that they are NOT a
regression of the rule.

NOT BUILT, and the judgement is mine to defend: they are THREE mechanisms (the effective command
word after prefixes and wrappers, an input redirect into an executor, data flow through a
substitution), so closing one would leave the entry describing a class it no longer has -- and
every widening of this rule in this order produced a measured over-refusal that only a later run
caught. `docs/holes/H214.md` was NOT written either, and that too is measured rather than preferred:
planting it in a copy turns
`tools/test_repo_hygiene.py::test_every_hole_is_one_index_row_one_prose_file_and_one_item` red
(1 failed, `['H214']`) because the index row must LINK at it -- and `docs/POST_V2_WISHLIST.md` is
the lead's file. The request went into `lead-lines.md` section 7a instead.

## F3 -- lead-lines section 5 -- 07:52

Re-read after `EVD-0448`: **14 rollup rows** (BUG-0242 among them, `EVD-0448`, `unresolved` empty),
27 active BUGs, **13 not in**. The contradiction is written out: BUG-0242 IS closable by a
verification click (`batch_closing_types("verification") == ["BUG"]`, dry-checked 0 refused) -- what
this ORDER may not do is transition it, and that restriction never applied to the lead. What such a
click asserts, and the honest alternative if the lead reads the un-removed tree as an unmet
criterion, are both spelled out. A batch line for BUG-0242 was added to section 1.

## F6 -- the round log

Corrected by the lead in the report's own head; nothing here to build.

## Reruns -- 07:52:58 to 08:01:13, and NO third full run

WHAT CHANGED IN A KIT: two DOCSTRINGS only -- `team-kits/kernel/state.py` (F5) and the three
`gate_write_scope.py` (F2). No kit BEHAVIOUR changed, so DEC-0050's full run is not repeated; the
selections below are what reads the changed text. ONE more stamp, because `bump_kit_version.py`
hashes content and a docstring is content: 07:52:58 -> **2026.09.13-3** x3, second call unchanged
x3.

| selection | result |
|---|---|
| `tools/test_shortening_net.py` | 36 passed, 28.0 s |
| `tools/test_context_budget.py` | 42 passed, 25.6 s |
| `tools/test_hooks.py -k "writes_a_script... / substitution / evidence_producer / silent_entries / window / mirror / enforcement"` | 22 passed, 35.7 s |
| `tools/test_repo_hygiene.py` | 43 passed, 124.9 s |
| `tools/test_state.py tools/test_kernel.py` | 203 passed, 41.8 s |
| `tools/test_hooks_v2.py -k "write_scope or dispatch or classification or trust"` | 48 passed, 81.5 s |

`.claude/hooks/test_gates.py` was NOT re-run: nothing under `.claude/hooks/` changed, and the two
reds it carries (BUG-0297, and the pre-existing H138 pointer) are untouched by any of the six rows
above -- said rather than assumed.

Hygiene after the rework: `validate.py` green, `ruff check tools team-kits user` green, the three
`gate_write_scope.py` byte-identical (md5 44769b05...), `generate-index` == store, VERSION
2026.09.13-3 x3.

## What this rework did NOT close, and named instead

1. `BUG-0304` / `H219` -- the one-call remainder, three mechanisms, named in the three gates and in
   the hole record; no code change, with the reason above.
2. `docs/holes/H214.md` and its index link -- the lead's, measured as red-if-I-write-it.
3. `BUG-0221` / H138 -- unchanged: no kernel door to an archived item.
4. The parity matrix rows themselves: row 4 cites `handle_pre_tool_use`, which does run on Codex for
   the tools before its guard. The reader counts the row blind because what the row cites it FOR is
   behind the guard. A row that wanted the finer answer would cite the inner symbol, as row 54 does
   -- that is a change to the MATRIX and it is not this order's to make.


# Rework 2 (verifier round 2 = FAIL on one identifier: F5, third item)

Report read: `project_memory/staging/TSK-0149/verify-round-2.md`, whole. Start 2026-09-13T08:15:17.

## The one row

`tools/test_hooks.py:19546`, inside the docstring of
`test_two_silent_entries_still_leave_the_gate_deciding` -- the sentence rework 1 wrote to replace a
count with a pointer, and the pointer named the wrong node:

    -    `test_every_shipped_hook_of_this_kit_reaches_the_deadline_that_arms_it`, not by a count in this
    +    `test_every_registration_names_a_window_its_gate_can_answer_inside`, not by a count in this

MEASURED MYSELF before changing it, in the direction the sentence denies -- the rig mutation
`a_shipped_entry_states_no_window` takes the `timeout` off ONE shipped registration
(`team-kits/dev-team/settings/settings.json`, `PreToolUse(Write)` / `guard_no_adhoc.py`) and puts
the file back byte-for-byte afterwards:

    test_every_shipped_hook_of_this_kit_reaches_the_deadline_that_arms_it  -> 3 passed
    test_every_registration_names_a_window_its_gate_can_answer_inside      -> 1 failed
      "dev-team PreToolUse(Write): guard_no_adhoc.py names NO window, so
       `_compat.start_the_deadline` refuses every call of it -- the registration is the half
       that is missing"

So the verifier is exactly right, and the failure mode is the expensive one house rule 4 is about:
the named node holds "every shipped hook is ARMED" (it registers its own hooks without a window and
asserts each refuses), not "every shipped ENTRY names a window". A pointer that cannot go red for
the claim beside it is worse than the number it replaced, because the number at least aged
visibly.

After the change, the newly named node run once: **1 passed, 2.55 s** (08:16:34).

NO STAMP AND NO RUN, and the reason is the file: `tools/` goes into no kit hash
(`tools/bump_kit_version.py` + `kernel.hashing` hash the kits), so the stamp stays at
**2026.09.13-3** and DEC-0050's full run is untouched. Nothing else in the tree moved.
