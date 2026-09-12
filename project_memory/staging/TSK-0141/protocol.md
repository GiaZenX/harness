# TSK-0141 -- stream A (kernel), PR-0012 "Bug-Null", order 3b

Base: 10a5127 on feat/harness-v2. Builder: harness-implementer Opus high A.
Clock readings are taken with `date` before every block that is written.

Scratch (red-first, no .git): `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0141/`

## Plan and the way it was REJECTED (FR-0084)

REJECTED: one scratch clone per hole, mutated and run per row. It loses on the host rule --
43 holes x (copy ~30 MB tree + pytest start) is measured in tens of minutes of pure copying on
this host, and three builders share the machine. CHOSEN: ONE `.git`-less clone, and per row the
mutation is applied to the clone, the naming node run there (red), reverted, run again (green).
What the smaller way would NOT have covered: nothing about the arbiter -- the clone is still
outside the repo and still carries the real file, so the red line is still measured against the
running code and not against a diff.

## Rows

### H81 | BUG-0173 | INSTR | CLOSED  (clock 2026-09-12 09:58)

* mechanism: `report._invoked_scripts` could not decompose a quoted path containing a SPACE
  (`False`, over-warning) and never asked whether the resolved file EXISTS (`True`, under-warning).
* change: `team-kits/kernel/report.py` -- new `_SCRIPT_WORD` (one shell word: a quoted span is one
  word), `_script_word`/`_script_basename`/`_first_alternative`, `_invoked_scripts` now derives its
  base names from the new `_invoked_script_words`; new `_runs_no_file` + `_PROJECT_DIR_VARIABLE`
  (the NAME once, the three shells' spellings derived); `approval_mint_is_wired` consults it.
  The docstring paragraph that claimed both defects was replaced -- it claimed a gap the code no
  longer has (house rule 3, the reassuring direction).
* red-first (rig `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0141/rig`, no `.git`):
  - mutation A (`_SCRIPT_WORD` back to the bare run of non-blank characters):
    `FAILED tools/test_report.py::test_a_quoted_path_with_a_space_runs_and_a_named_missing_file_does_not`
    at line 1912 ("a quoted path with a space still runs"), 1 failed 131 deselected in 1.51s
  - mutation B (the `_runs_no_file` guard deleted): same node FAILED at line 1919
    ("a path that resolves to no file starts nothing"), 1 failed 131 deselected in 1.50s
  - reverted, both green.
* naming node: `tools/test_report.py::test_a_quoted_path_with_a_space_runs_and_a_named_missing_file_does_not`
  (BUG-0173 in the docstring's first paragraph).
* suites (selections, one at a time): `tools/test_report.py` 132 passed in 30.2s;
  `tools/test_hooks_v2.py -k "matrix_still_sees_the_gates_behind_the_launcher or accepts or
  registered_chain or tool_set"` 15 passed in 11.0s (the other readers of `_invoked_scripts`).
* EVD-0324.

### H109 | BUG-0193 | INSTR | CLOSED  (clock 2026-09-12 10:02)

* mechanism: `report.invariant_check_resolution` parsed the file for the NAME only, so a test the
  runner is told not to execute (`skip`, an empty parametrisation) counted as a check that exists.
* change: `team-kits/kernel/report.py` -- new `_marker_chain`, `_marker_verdict`,
  `_unrunnable_tests`; the per-file parse cache now carries `(defined, unrunnable)` and the
  resolution consults it. The rule is WHO DECIDES and not a list of markers: `skip` and an empty
  `parametrize` are decided by the source (`False`), `skipif` by the runner (`None`, the module's
  third answer), and only a marker written under `mark` counts, so a project's own decorator that
  ends in the same word is not read as one. The docstring paragraph that carried H109 as an
  accepted cost was replaced by what the code now does plus the one thing still out of reach (a
  marker the project's config deselects -- not in the file).
* red-first: mutation (the `unrunnable` branch deleted from the resolution) ->
  `FAILED tools/test_report.py::test_a_check_whose_test_is_skipped_resolves_to_nothing_it_can_run`
  at line 476 (`assert True is False`), 1 failed 132 deselected in 1.23s; reverted, green.
* naming node: `tools/test_report.py::test_a_check_whose_test_is_skipped_resolves_to_nothing_it_can_run`
  (BUG-0193 in the first paragraph).
* suites: `tools/test_report.py -k "invariant or skipped or one_scan"` 4 passed in 1.13s; the full
  `tools/test_report.py` run is recorded under the next report.py row (one run for the file).
* EVD-0325.

### H127 | BUG-0211 | DESIGN | CLOSED  (clock 2026-09-12 10:08)

* mechanism: `plan_diagram.is_pristine` told hand-edited from stale from pristine and had no caller
  outside its own test -- a hand edit was invisible until the next state write overwrote it.
* change:
  - `team-kits/kernel/plan_diagram.py`: new `verdicts(directory, entries)` -- ONE render, both
    answers, and a file that is not on disk is not judged; `is_pristine` takes the pre-rendered map.
  - `team-kits/kernel/state.py`: `board_row` extracted as the SINGLE definition of the row shape
    (a second copy would make the digest disagree and read every picture as hand-edited),
    `board_entries` public.
  - `team-kits/kernel/report.py`: `_check_generated_diagrams`, wired into `validate_state`; the
    rows are collected in the walk `validate_state` already performs.
* measurement that decided the wiring: a walk of its own cost 0.653 s over this repository's 642
  items, the judgement itself 0.019 s (both readings from the scratchpad measure script against
  the real store, 2026-09-12). The validator is what a merge gate waits for, so the second walk
  was dropped.
* red-first: mutation (the `_check_generated_diagrams` line deleted from `validate_state`) ->
  `FAILED tools/test_report.py::test_a_hand_edited_diagram_is_reported_and_a_missing_one_is_not`
  at line 526 (`0 = len([])`), 1 failed 133 deselected in 1.28s; reverted, green.
* naming node: `tools/test_report.py::test_a_hand_edited_diagram_is_reported_and_a_missing_one_is_not`
  (BUG-0211 in the first paragraph).
* suites: `tools/test_report.py` 134 passed in 28.9s; `tools/test_plan_diagram.py tools/test_board.py`
  91 passed in 27.5s; `tools/test_state.py` 61 passed in 8.4s (the readers of `board_entries`).
* EVD-0326.

### H184 + H111 | BUG-0266 + BUG-0195 | DESIGN | CLOSED  (clock 2026-09-12 10:16)

* mechanism: the auditor's routine approval existed in `approvals` and not on the command surface
  a role types -- `request-approval routine PR-0001` answered `invalid choice`, so the only
  walkable route was an ordinary work order, which `create-task` forces to carry a writable scope.
* measurement first, because the code was already there: PR-0011 AC-8 built the `routine` branch in
  `kernel/cli.py`; measured 2026-09-12 against the shipped parser, `routine` IS a choice and
  `analysis` is not. What was missing is what DEC-0100 asks for -- a passing test that NAMES the
  two items.
* change: `tools/test_approvals_dispatch.py` (new test; `json`, `re`, `cli` imports added). No
  kernel change -- the row is a MEASUREMENT plus its naming test, and it is marked as such.
* red-first: mutation (`routine` subtracted from the parser's `kind` choices in `kernel/cli.py`) ->
  `FAILED tools/test_approvals_dispatch.py::test_the_routine_kind_is_walkable_on_the_command_surface_a_role_actually_types`
  at line 987, 1 failed 224 deselected in 3.12s; reverted, green.
* naming node: `tools/test_approvals_dispatch.py::test_the_routine_kind_is_walkable_on_the_command_surface_a_role_actually_types`
  (BUG-0266 and BUG-0195 in the first paragraph).
* suites: `tools/test_approvals_dispatch.py -k routine` 15 passed in 15.9s; full file 222 passed,
  3 foreign reds (below), 202s.
* EVD-0331.

### The verifier's G3 | tools/test_approvals_dispatch.py | CLOSED  (clock 2026-09-12 10:16)

* mechanism: `test_the_card_of_a_list_bound_approval_counts_what_it_binds` asserted `"2" in card`,
  which a card saying 12, 20 or 32 satisfies -- the count could be wrong by any amount.
* change: `tools/test_approvals_dispatch.py` -- the count is matched with no digit on either side
  and built from `len(holes)`, so the number is the measurement; the card's German wording stays in
  `approvals.approval_card` and is not copied into the test.
* red-first: mutation (`len(listed) + 10` in `kernel/approvals.py`, the verifier's own example) ->
  `FAILED ...::test_the_card_of_a_list_bound_approval_counts_what_it_binds` at line 5100,
  1 failed 224 deselected in 5.12s; reverted, green. With the OLD assertion the same mutation is
  GREEN -- that is the defect.
* no EVD: this is a test-strength repair the order names directly, not a hole with a BUG id.

### H194 | BUG-0278 | ENUM | CLOSED  (clock 2026-09-12 10:20)

* mechanism: `dispatch.acceptance_is_test_shaped` claimed both kit languages and was built on
  English word boundaries -- `ohne` counted as a clausal negator (so "ein Test wird rot, ohne den
  Fix", this repository's own red-first formula, was REFUSED while its English twin was granted),
  and a German compound (`Regressionstest`, `Unittest`) was invisible to `_WORD_TEST_RX`.
* change: `team-kits/kernel/dispatch.py` -- `_DENIES_RX` keeps the CLAUSAL negators (and the German
  declension becomes the pattern `kein\w*` instead of four spellings); `_PREPOSITION_DENIES_RX` is
  the new class that denies only its own COMPLEMENT, read to the end of its clause; new
  `_mentions_a_test` is the one reader both the positive and the denial question use;
  `_COMPOUND_TEST_RX` reads a capitalised noun ending in -test with a stem of at least
  `_COMPOUND_STEM_MIN` = 4. `without` is now in the preposition class, which closes the asymmetry
  the item names. `tools/test_ladder.py`: the row that refused `der Regressionstest wird rot` is
  replaced by the two English tail-collisions it was really guarding, and the comment claiming the
  compound could not be told from `latest` is gone -- it claimed a limit the code no longer has.
* measurement: 19 rows through `dispatch._sentence_names_a_test` against the running code,
  2026-09-12, 0 wrong -- 8 grants (the 5 of the item plus 3 of the verifier's round-1 grants) and
  11 refusals (all 7 of verify-round-2's refused phrasings, plus `ohne Test`, `ohne
  Regressionstest`, `the latest run passes`, `der protest schlaegt fehl`).
* red-first, BOTH halves separately:
  - `ohne` put back into `_DENIES_RX` ->
    `FAILED tools/test_ladder.py::test_a_german_acceptance_line_is_read_like_its_english_twin`
    at line 502 on "ein Test wird rot, ohne den Fix", 1 failed 48 deselected in 2.21s
  - the compound term dropped from the final `bool(...)` -> the same node FAILED at line 502 on
    "der Regressionstest schlaegt fehl", 1 failed 48 deselected in 1.96s
  - reverted, green.
* naming node: `tools/test_ladder.py::test_a_german_acceptance_line_is_read_like_its_english_twin`
  (BUG-0278 in the first paragraph).
* suites: `tools/test_ladder.py` 49 passed in 56.9s; `tools/test_approvals_dispatch.py` (the other
  reader of `dispatch`) 222 passed + 3 foreign reds in 202s.
* EVD-0334.

## Foreign reds

* 2026-09-12 ~10:20, `python -B -m pytest tools/test_approvals_dispatch.py`:
  `test_the_routine_route_leaves_the_other_three_alone`,
  `test_two_same_role_dispatches_refuse_to_guess`,
  `test_different_roles_in_parallel_bind_cleanly` -- all three
  `team-kits/kernel/scopes.py:124: SyntaxError`, which is the line where `scopes` imports the KIT's
  `gate_write_scope` out of a hooks directory this stream does not own. `scopes.py` itself is
  unmodified (mtime 04:01, not in `git diff`), so the broken file was another stream's in-progress
  edit of a kit hook. Re-run of the three nodes alone at 10:23: 3 passed in 8.06s. Left alone.

### H48 | BUG-0140 | DESIGN | CLOSED  (clock 2026-09-12 10:31)

* mechanism: `state._write_board` is fail-soft (a page a viewer holds open must not fail the state
  write) and said so ONCE, on stderr, in the session that hit it -- the next session read a frozen
  page with no word anywhere.
* change: `team-kits/kernel/report.py` `_check_board_is_as_fresh_as_the_index`, wired into
  `validate_state`; this is the closing direction the item's own `limits` names ("eine
  Sitzungsbrief-Zeile 'Board älter als Index'"), built as a standing validator warning, which the
  session brief counts in `budget_status.validator_warnings`.
* why mtime and not the stamp in the page: index and board are written in ONE call from one clock
  reading, index first -- so a board older than the index is exactly a write that did not happen,
  and reading the timestamp out of the rendered HTML would be a second reader of a format
  `kernel.board` owns.
* red-first: mutation (the check's line removed from `validate_state`) ->
  `FAILED tools/test_report.py::test_a_board_that_could_not_be_rewritten_is_reported_as_older_than_the_index`
  (`assert 0 == 1`), 2 failed 134 deselected in 1.57s; reverted, green.
* naming node: `tools/test_report.py::test_a_board_that_could_not_be_rewritten_is_reported_as_older_than_the_index`.
* suites: `tools/test_report.py tools/test_state.py tools/test_migrate_holes.py` 211 passed in 48.3s.
* EVD-0335.

### H154 | BUG-0236 | DESIGN | CLOSED on its second residue, first class unchanged and bolted  (clock 2026-09-12 10:31)

* what was closed: the second residue measured in verify round 1 (F20) -- `state._iter_every_stored_item`
  swallowed a read exception, so an ARCHIVED hole item with broken YAML vanished from all three
  hole checkers at once (measured on H156 with its YAML destroyed: rc 0, silence).
* change: `team-kits/kernel/state.py` -- `_walk_stored_files` is the ONE walk (and yields the plain
  path, not the extended long-path form: the extended one cannot be `relpath`'d against the root,
  measured as `ValueError: path is on mount '\\?\C:'`), `unreadable_stored_files` asks the other
  half of the question; `team-kits/kernel/report.py` `_check_every_stored_file_reads` turns it into
  an error for the files the active walk never opened, so one broken item is ONE finding.
* what was NOT closed and is not a defect: the first class -- `capture_migrated_hole` writes a
  terminal status without the confirming evidence -- stands with the four bolts its `limits`
  already measures (only a body with `hole_number`, only a status the automaton has, a terminal one
  only into the ARCHIVE tree, and an already-used number is returned rather than overwritten).
  This row is a PARTIAL close and says so.
* red-first: same mutation as above -> `FAILED tools/test_report.py::test_an_unreadable_file_in_the_archive_is_a_finding_and_not_a_silence`
  (`assert 0 == 1`), reverted, green.
* naming node: `tools/test_report.py::test_an_unreadable_file_in_the_archive_is_a_finding_and_not_a_silence`.
* EVD-0336.

### H135 | BUG-0218 | INSTR | CLOSED  (clock 2026-09-12 10:37)

* mechanism: `scopes.witnesses` filled each scope entry ALONE, so it answered "what would this
  entry own" and not "what could these two share" -- `a/*x` and `a/y*` were cut as disjoint over an
  empty tree and collided the moment `a/yx` existed.
* change: `team-kits/kernel/scopes.py` -- `_tokens`, `_nullable`, `_unify` (a memoised joint walk
  over the two token lists: where one pattern is literal, it chooses the character the other's
  wildcard stands for), `_one_character` (only `**` crosses a separator), `pair_witnesses`;
  `overlaps` adds them to the universe. SAFE BY CONSTRUCTION on a reader `dispatch` refuses leases
  with: everything the builder produces is a CANDIDATE that `in_scope` judges with the gate's own
  predicate, so it can widen what the check SEES and never what it claims.
* measurement: 11 rows through `scopes._unify` against the running code, 0 wrong -- 7 that must
  unify (incl. the item's own `a/*x` x `a/y*` -> `a/yx` and the legitimate glob seam
  `team-kits/kernel/**` x `team-kits/*/VERSION` -> `team-kits/kernel/VERSION`) and 4 that must
  not (different first segment, different file name, different literal, and `a/*` against `a/b/c`,
  which is the separator rule). AND the live cut: `check-scopes` over TSK-0141/0142/0143 with the
  stronger reader still reports `disjoint` (10:32), so order 3b's cut holds under it.
* red-first, two mutations:
  - `pair_witnesses` dropped from the universe in `overlaps` ->
    `FAILED tools/test_parallel_scopes.py::test_two_orders_that_share_only_a_region_no_single_witness_reaches_collide`
    (`assert 0 == 1` on the end-to-end row), 1 failed 14 deselected in 1.25s
  - the separator rule in `_one_character` disabled -> the same node FAILED on `a/*` x `a/b/c`,
    1 failed 14 deselected in 0.96s
  - reverted, green.
* naming node: `tools/test_parallel_scopes.py::test_two_orders_that_share_only_a_region_no_single_witness_reaches_collide`.
* suites: `tools/test_parallel_scopes.py` 16 passed in 24.4s; `tools/test_parallel_streams.py`
  32 passed in 27.4s (the other reader of `scopes`).
* EVD-0341.

### H142 | BUG-0225 | DESIGN | CLOSED  (clock 2026-09-12 10:37)

* mechanism: `--only` with one real id resolved, compared nothing and answered rc 0 -- which tells
  a script the cut was checked.
* change: `team-kits/kernel/scopes.py` `check` -- a named `--only` that yields fewer than two open
  orders is rc 1 with the ids it named; the run nobody narrowed keeps rc 0, because that run asked
  for nothing (and it is the shape `test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it`
  drives). `tools/test_parallel_streams.py::test_a_route_the_caller_named_has_to_resolve_and_one_nobody_named_does_not`
  had the old rc 0 pinned with a paragraph naming H142 as open -- both were corrected, the
  paragraph because it claimed a gap the code no longer has.
* red-first: mutation (the `if only:` branch removed from `check`) ->
  `FAILED tools/test_parallel_scopes.py::test_a_named_route_that_cannot_be_a_pair_is_a_usage_answer_and_not_a_clean_cut`
  (`assert 0 == 1`), 1 failed 15 deselected in 2.03s; reverted, green.
* naming node: `tools/test_parallel_scopes.py::test_a_named_route_that_cannot_be_a_pair_is_a_usage_answer_and_not_a_clean_cut`.
* EVD-0342.

### H148 | BUG-0231 | DESIGN | CLOSED on its second residue  (clock 2026-09-12 10:42)

* what was closed: the residue -- `pair_seam` intersects the two declarations as STRINGS while the
  gate compares FILE SETS, so two words for one seam left the intersection empty and the pair was
  refused with the ordinary OVERLAP message. Fail-closed, and a worse answer.
* change: `team-kits/kernel/scopes.py` `_spelled_apart` (asked with the GATE's predicate, not with
  a second reader) + a `spelled apart` line in `check`. The verdict is unchanged on purpose.
* MEASURED CORRECTION to the item's own example: against the shipped predicate `docs/` and
  `docs/**` are NOT one set -- `docs/a.md` matches `docs/**` and not `docs/` (probe against
  `scopes._shipped_halves`, 2026-09-12). The residue reproduces on the directory path itself,
  which both declarations match; that is the row the test carries.
* what was NOT closed and is not a defect: the first class -- a declared seam may be WIDER than the
  real intersection -- stands, because the obvious rule ("no wider than the intersection") forbids
  the legitimate glob seam `team-kits/*/VERSION`, which the new `_unify` measurement confirms is a
  real intersection member (`team-kits/kernel/VERSION`).
* red-first: `_spelled_apart` returning `[]` ->
  `FAILED tools/test_parallel_scopes.py::test_two_spellings_of_one_seam_are_named_as_such_and_not_as_a_collision`
  ("Right contains one more item: 'docs/'"), 1 failed 17 deselected in 2.19s; reverted, green.
* naming node: `tools/test_parallel_scopes.py::test_two_spellings_of_one_seam_are_named_as_such_and_not_as_a_collision`.
* EVD-0345.

### H143 | BUG-0226 | DESIGN | CLOSED as a MEASURED BOUND, no code change  (clock 2026-09-12 10:42)

* what the item says is open: a seam that covers only PART of the overlap keeps covering that part.
  That is what a seam IS -- an orchestrator's declaration the merge round applies -- and the item's
  own `limits` names the bound: every covered path is PRINTED, line by line, so a wrongly declared
  seam is a finding against the cut rather than a silence.
* what was missing: nothing measured that bound. A declaration is only as safe as the report is
  complete, and no test held the report.
* change: `tools/test_parallel_scopes.py` only -- both halves in one test (the covered path appears
  as its own `seam` entry; the part the declaration does not reach stays a collision).
* red-first: `pair_seam` stripped of its intersection (`return sorted(set(declared))`) ->
  `FAILED ...::test_a_seam_narrower_than_the_overlap_leaves_the_rest_colliding_and_prints_what_it_covers`
  ("Right contains one more item: 'src/shared.py'"), 1 failed 17 deselected in 2.16s; reverted.
* naming node: `tools/test_parallel_scopes.py::test_a_seam_narrower_than_the_overlap_leaves_the_rest_colliding_and_prints_what_it_covers`.
* suites: `tools/test_parallel_scopes.py` 18 passed in 24.7s.
* EVD-0346.

### H141 | BUG-0224 | ENUM | CLOSED as a two-ended tripwire  (clock 2026-09-12 10:49)

* mechanism: `_CADENCE_IN_PROSE` is a list of adverbs with no tripwire at either end, and its five
  measured blind spellings lived in a docstring where nothing could see them rot. "Is this sentence
  a rhythm" is world knowledge no derivation from this tree produces -- a reader that claimed it
  would be the next enumeration -- so the closure is the tripwire the house rule asks for, not a
  wider reader. This is the verifier's G4 shape: the blind spellings become TESTED ROWS.
* change: `tools/test_parallel_streams.py` -- the vocabulary stands ONCE as `_CADENCE_WORDS` and
  the pattern is built from it; new test with both ends.
* red-first, BOTH ends:
  - a REDUNDANT entry added (`"weekly report"`, which `weekly` already covers) ->
    `FAILED tools/test_parallel_streams.py::test_the_cadence_reader_is_an_enumeration_held_at_both_ends`
    ("the sentence fires without it"), 1 failed 32 deselected in 2.07s
  - a blind spelling made visible (`"once a week"` added) -> the same node FAILED with
    `assert not <re.Match ... match='once a week'>`, 1 failed 32 deselected in 2.04s
  - reverted, green.
  NOTE, because the first attempt did not fail and that is the measurement: adding `"fortnightly"`
  -- a word for a rhythm nobody writes here -- passes BOTH ends, because it is the sole reason its
  own sentence fires. This tripwire sees a REDUNDANT entry, not an unused one; said here rather
  than claimed away.
* naming node: `tools/test_parallel_streams.py::test_the_cadence_reader_is_an_enumeration_held_at_both_ends`.
* suites: `tools/test_parallel_streams.py` 33 passed in 31.4s.
* EVD-0347.

### BUG-0271 | the German approval question | CLOSED as a MEASUREMENT, no code change  (clock 2026-09-12 10:47)

* what the order asked: "PR-0011 AC-7 built KIND_LABELS -- measure what remains".
* measured 2026-09-12 against the running kernel: NOTHING remains. All three acceptance criteria
  are built AND carry a node that names the item in its first paragraph:
  - AC-1 + AC-2 `tools/test_light_kit.py::test_no_approval_question_shows_an_english_enum_word_a_hash_or_a_path`
    -- every kind rendered, no English enum value, no `sha256`, no `approvals/pending` path in the
    sentence; an unlabelled hex run is refused; the hash prefix and the request's path stand in the
    approving option's DESCRIPTION, which `gate_approval` compares character for character.
  - AC-3 `tools/test_light_kit.py::test_every_approval_kind_has_one_plain_word_label_and_no_label_is_orphaned`
    -- kind without a label red, label without a kind red, two kinds sharing a label red, and a
    label equal to its enum value red.
* red-first: `build_question` rebuilt in the rig with the raw kind and the `subject_manifest sha256`
  prefix back in the sentence (the exact text the item quotes) ->
  `FAILED tools/test_light_kit.py::test_no_approval_question_shows_an_english_enum_word_a_hash_or_a_path`
  on `Freigabe erbeten: analysis für ... (subject_manifest sha256 deadbeefdead…)`,
  1 failed 1 passed 24 deselected in 2.43s; reverted, green.
* suites: `tools/test_light_kit.py -k "approval_kind_has_one_plain_word or english_enum_word or
  auditor_runs_on_the_routine_route"` 3 passed in 4.7s.
* EVD-0348.

### H71 | BUG-0163 | INSTR | CLOSED on the one-liner the item names  (clock 2026-09-12 10:58)

* mechanism: `kitupdate.pending_entries` (and its sibling `_same_but_for_line_endings`) caught
  `OSError` alone, so anything else -- a `ValueError` out of a codec is the reachable one -- left
  the reader and aborted `update-kit` AFTER the installer had moved the tree. The hook around the
  call was guarded, the command was not; the item names this as a one-liner.
* change: `team-kits/kernel/kitupdate.py`, both readers -- every failure to read is the SAME third
  answer (`None`, unknown), which is also the safe one: the nag stays.
* the other three limits of the entry stand with their bounds (an undecodable list reads as empty
  and is deleted -- UTF-16 measured, not shipped that way; every `CR` is dropped, deliberately
  matching the two installers; two states nag on purpose).
* red-first: `except Exception` put back to `except OSError` ->
  `FAILED tools/test_kitupdate.py::test_a_pending_list_that_cannot_be_read_at_all_is_unknown_and_not_a_crash`
  with `ValueError: a codec said no`, 1 failed 87 deselected in 2.21s; reverted, green.
* naming node: `tools/test_kitupdate.py::test_a_pending_list_that_cannot_be_read_at_all_is_unknown_and_not_a_crash`.
* suites: node selection 1 passed in 0.96s. The whole `tools/test_kitupdate.py` was run ONCE
  (5m53s -- over the host budget, not repeated) and is recorded under "unstamped-tree reds" below.
* EVD-0349.

## Unstamped-tree reds (not foreign, not mine -- the round's own stamp is missing)

* 2026-09-12 10:48-10:54, `python -B -m pytest tools/test_kitupdate.py`: 23 failed, 64 passed,
  1 skipped. Every failing node is in the installer-twin family, and the measured cause is ONE
  sentence the installer prints:
  `[write_kit_state] ...\team-kits\dev-team does not hash to the 'content:' in its own VERSION --
  the kit source has been edited since it was stamped.`
  That is the documented consequence of three builders editing kit files in one tree before the
  stamp: `team-kits/*/VERSION` is forbidden to every stream and `bump_kit_version.py` belongs to
  the merging item. `team-kits/scaffold_team.{sh,ps1}` were modified at 10:52:33 -- inside my run --
  by another stream, which is a second reason the same family was unstable.
  Re-run of one node at 10:56 alone: still red with the SAME stamp sentence, so it is the stamp and
  not a transient. NOT a finding against this stream; the merging item's `bump_kit_version.py` run
  is what clears it, and it has to be re-measured there.

## HALF-WAY REPORT (clock 2026-09-12 10:58) -- written HERE because a subagent has no mid-turn channel

The order asks for a short message to the lead at half. A subagent's only channel to the lead is
its final message, so the half report stands in the protocol at the point it was due; the lead can
read this section without waiting for the stream to end.

* handled 16 of 43 rows: 14 holes + BUG-0271 + the verifier's G3.
* CLOSED 14: H81, H109, H127, H184, H111, H194, H48, H135, H142, H141, H71 (full);
  H154, H148, H143 (partial or measured-bound, each says which half in its row); plus BUG-0271
  (measured, already built) and G3 (test strength).
* downgraded with a measurement: 0 so far -- the downgrade rows (H108, H134, H106, H58) are
  written at the end of the stream, after every attempt.
* seam handoffs so far: 1 (H108 / BUG-0192 -- see the section below).
* foreign reds: 1 event (3 nodes, a kit hook mid-edit by another stream, re-run green).
* unstamped-tree reds: 1 event (23 nodes in the installer-twin family of `tools/test_kitupdate.py`),
  measured cause = the missing kit stamp, which belongs to the merging item.
* the cut holds: `check-scopes` over TSK-0141/0142/0143 is still `disjoint` under the STRONGER
  overlap reader this stream built (10:32).

### H52 | BUG-0144 | DESIGN | CLOSED on the half that was reachable  (clock 2026-09-12 11:04)

* mechanism: the ambiguity refusal is right (guessing writes a running specialist's end onto the
  wrong task) but its remedy was advice for a project that has not gone wrong yet -- a zombie
  dispatch kept id-less attribution off for its whole role with nothing to do about it.
* change: `team-kits/kernel/dispatch.py` -- the refusal names each candidate with what its lease
  knows about its child (`agent_id` or "no child bound") AND the route out: a lease is released
  with the task's STATUS, so moving the finished task restores attribution.
* the test measures the ROUTE and not the sentence: produce the ambiguity, transition the corpse,
  record the same stop -- it is attributed. Only two facts of the text are asserted, the candidates
  and what each lease knows, because a remedy naming neither cannot be walked.
* red-first: the added half of the message removed ->
  `FAILED tools/test_approvals_dispatch.py::test_the_ambiguous_stop_refusal_names_the_way_out_of_a_zombie_dispatch`,
  1 failed 225 deselected in 4.95s; reverted, green.
* naming node: `tools/test_approvals_dispatch.py::test_the_ambiguous_stop_refusal_names_the_way_out_of_a_zombie_dispatch`.
* suites: `tools/test_approvals_dispatch.py -k "stop or child_end or zombie or ambiguous"`
  13 passed in 19.3s.
* EVD-0350.

### H197 | BUG-0281 | DESIGN | CLOSED in the kernel, consumer handed over  (clock 2026-09-12 11:04)

* mechanism: "terminal" and "finished" are two questions and the kernel had only the first. `SR`
  reaches ACCEPTED and holds there, and ACCEPTED cannot be a terminal (the edge to SUPERSEDED
  leaves it), so every reader that asked `is_terminal` to mean "is this still work" counted every
  agreed system requirement as open work for ever -- measured against this repository's Gate 4.
* change: `team-kits/kernel/backlog_types.py` -- `_Automaton.done_states` (checked against the
  automaton AT IMPORT, both ways: not a state -> AssertionError, already a terminal ->
  AssertionError), `SR` declares `ACCEPTED`, and `is_finished` is the reader.
* what is NOT wired, and the kernel says so in its own docstring rather than implying it: the
  enforcement layer's reader `.claude/hooks/_harness.py::Reference.terminal` still asks
  `is_terminal`, and that file is closed to every role in this repository. The one-line patch is
  under "Seam handoffs" for the user.
* red-first: `done_states=("ACCEPTED",)` removed from the SR automaton ->
  `FAILED tools/test_backlog_types.py::test_an_accepted_system_requirement_is_finished_without_being_terminal`
  (`False = is_finished('SR', 'ACCEPTED')`), 1 failed 51 deselected in 1.95s; reverted, green.
* naming node: `tools/test_backlog_types.py::test_an_accepted_system_requirement_is_finished_without_being_terminal`.
* suites: `tools/test_backlog_types.py` 52 passed in 3.4s.
* EVD-0352.

### H126 | BUG-0210 | DESIGN | CLOSED as a MEASURED BOUND, no code change  (clock 2026-09-12 11:09)

* measured 2026-09-12: the seam the item proposed HAS landed -- `approvals.open_requests` carries
  the optional `now`, and the expiry RULE is asked of `approvals.has_expired` by every reader. What
  is left is the TWO CLOCKS, and that is deliberate: the page stays a pure function of the state it
  was rendered from, and `board.open_requests` says so in its own head. The WALK is not shared
  either, also deliberately (a request file is hand-written and the page's defence against one
  nothing could write is its own; importing `report` would close the package's import graph).
* change: `tools/test_board.py` only -- the parity test now names BUG-0210 and its docstring was
  replaced: it said the copy still stood and the seam was another stream's, which is a claim the
  code no longer supports (house rule 3, the alarming direction).
* naming node: `tools/test_board.py::test_the_board_and_the_session_brief_agree_on_the_open_requests`
  -- 1 passed in 1.35s.
* EVD-0360.

### H160 | BUG-0242 | DESIGN | naming written, MEASUREMENT BLOCKED  (clock 2026-09-12 11:09)

* the non-removal is deliberate with three measured reasons (a provider's behaviour on a tree whose
  role no longer declares `memory:` is unmeasured; the only recoverable quarantine belongs to the
  `scaffold_team` twins; the content is the user's craft knowledge, DEC-0056 (c)). The report IS
  the answer, so the close is the naming node over it.
* change: `tools/test_kitupdate.py` -- the memory-tree test now names BUG-0242 beside BUG-0088.
* BLOCKED, and the reason is measured: the node scaffolds a real kit through the shipped installer,
  and the installer refuses with "the kit source has been edited since it was stamped". That is the
  unstamped-tree class above, not this change. EVD-0361 is recorded as `blocked` with that sentence
  -- the kernel's own instrument for "nothing was checked" -- and the merging item has to re-run
  `tools/test_kitupdate.py -k memory_tree_no_installed_role` after the stamp.
* EVD-0361 (blocked).

### H130 | BUG-0213 | DESIGN | CLOSED  (clock 2026-09-12 11:09)

* mechanism: `filing.retention_refusal` allows two forms -- a countable span, and NONE at all for a
  drawer whose clock does not start at the end of a year -- and the plan's own header documents
  both; but `approvals.filing_rule_subject_manifest` read "empty" as "not said" and refused the
  QUESTION, so the second form could never be minted and only a hand-written rule could carry it.
* change: `team-kits/kernel/approvals.py` -- `retention is None` (the flag nobody typed) stays
  refused, because that refusal exists so the kernel never fills in a decision the user owes;
  `""` (the flag typed empty) is the explicit second form. The question renders it as
  "keine zählbare Frist", never as the `?` a missing answer gets -- what the user signs has to read
  like a decision.
* `tools/test_kernel.py`'s comment calling the form "unreachable through this route ... owned by a
  file this stream may not write" was replaced and its pinning assertion turned into the walked
  route (manifest -> real approval hook -> `filing.apply` -> the rule in the plan).
* red-first: the builder read back to the falsy test ->
  `FAILED tools/test_kernel.py::test_a_filing_rule_with_no_countable_retention_can_be_asked_for`
  with the ApprovalError itself, 1 failed 131 deselected in 2.37s; reverted, green.
* naming node: `tools/test_kernel.py::test_a_filing_rule_with_no_countable_retention_can_be_asked_for`.
* suites: `tools/test_kernel.py -k "retention or filing_rule"` 5 passed in 5.8s.
* EVD-0363.

### H156 | BUG-0238 | DESIGN | CLOSED  (clock 2026-09-12 11:12)

* what changed: nothing in the refusal itself -- it asks `kernel.scopes`, so the BUG-0218 repair
  arrived here with no edit. That arrival is now measured: `a/*x` against `a/y*` over an EMPTY tree,
  the second lease refused naming `a/yx`. Before the pair witnesses it was granted.
* what stays outside the refusal is the division of labour and the test says both halves: two READY
  orders never leased together share no lease, and `check-scopes` sees them because it walks the
  OPEN orders (`scopes.open_orders` reads `is_terminal`, not the lease state); DEC-0070 (1) makes
  that run the rule before a cut.
* the docstring of `_assert_no_running_lease_owns_the_same_file_locked` said it inherits H135 --
  that claim is corrected, because the code no longer has it.
* red-first: `pair_witnesses` dropped from `scopes.overlaps` ->
  `FAILED tools/test_parallel_streams.py::test_the_lease_refusal_reaches_a_region_no_single_witness_reaches`
  ("DID NOT RAISE Exception"), 1 failed 33 deselected in 3.33s; reverted, green.
* naming node: `tools/test_parallel_streams.py::test_the_lease_refusal_reaches_a_region_no_single_witness_reaches`.
* suites: `tools/test_parallel_streams.py -k lease` 4 passed in 7.0s.
* EVD-0365.

## Rows this stream did NOT close, each with what the attempt measured

The user's rule is "closed OR a user-accepted exception, no third state". Every row below is
therefore addressed to the USER through the lead: it says what was measured, why this stream could
not close it, and the one plain-German sentence an exception would carry. None of them is filed as
an exception by me -- that is the user's click, and DEC-0100 forbids a migration standing in for it.

### A. The fix lies OUTSIDE this stream's allowed_scope (seam, not a limit)

* **H183 | BUG-0265** -- the sweep excludes `scripts/` and `tools/` where a kit is installed, so a
  project's OWN script there is unswept. AC-2 asks the INSTALLER to record which files it copied;
  the installer is `team-kits/scaffold_team.{sh,ps1}`, forbidden to this stream (and owned by the
  kit stream). The kernel half cannot be built first: a reader of a manifest nobody writes is the
  partial fix the verifier's G4 names. Bound, measured and unchanged: the two-ended tripwire in
  `tools/test_pointer_sweep.py::test_the_root_files_the_sweep_skips_are_installed_and_would_be_noisy`,
  and the exclusion applies only where a kit is installed. Patch: under "Seam handoffs".
  Plain German: „Beim Aufräumen überspringt das Werkzeug zwei Ordner, in denen das Team-Paket seine
  eigenen Skripte ablegt — liegt dort auch ein eigenes Skript des Projekts, wird es mit übersprungen."
* **H108 | BUG-0192** -- an Evidence that declares NO run scope still counts as a full run. The
  reading end cannot be tightened without turning every record a project already holds into an
  error no command can repair (an `EVD` is immutable). The surface end -- making `--run-scope`
  required on `evidence` -- is buildable in `kernel/cli.py`, but MEASURED it drags 13 shipped
  command lines in the three kits with it:
  `tools/test_hooks.py::test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires`
  reads the parser's required set and holds it against those texts, and they are the kit stream's
  files. So it is ONE patch across two streams; it is written out under "Seam handoffs" rather
  than half-applied, because applying my half alone turns that node red for everybody.
  Plain German: „Ein Prüfbericht, der nicht sagt, wie viel er geprüft hat, zählt weiter wie ein
  vollständiger Lauf."
* **H197 | BUG-0281** -- kernel half CLOSED above; the consumer `.claude/hooks/_harness.py` is
  closed to every role and goes to the user. Patch under "Seam handoffs".

### B. A contract change with a migration -- the user's decision, not a stream's

* **H155 | BUG-0237** -- a root goal's `class` is free text: no schema, no validator, no capture
  restricts it, so the architect duty hangs on an EXEMPTION list rather than on a required one.
  Measured cost today: a typo in a class name asks for an architect round nobody owed -- friction,
  and the remedy is a `capture SR` plus `transition ACCEPTED`. Closing it means a closed vocabulary,
  i.e. a contract change plus a migration for every goal already stored in every project.
  Plain German: „Die Art eines Ziels ist freier Text; ein Tippfehler dort verlangt einen
  Architekturschritt, den niemand schuldete."
* **H170 | BUG-0252** -- the higher effort DEC-0078 names for big office goals is unreachable
  because the office root type carries no class field at all. Same shape: giving it one is a
  contract change with a migration. Bound: the default is `medium`, the value DEC-0078 named for
  ordinary office work, so nothing runs too high, and both the office declaration and the
  constitution state the gap in their own words.
  Plain German: „Für große Büro-Ziele lässt sich die höhere Denk-Intensität nicht anfordern, weil
  dieser Zieltyp keine Größenangabe kennt; er läuft auf der mittleren Stufe."
* **H58 | BUG-0150** -- the edge `TSK DONE -> VALIDATED` demands no Evidence. Adding `TSK` to
  `state.CONFIRMING_EVIDENCE` is a one-liner and MEASURED it does two things at once: it makes the
  V1 import edge `("TSK","VALIDATED")` impossible, and -- by the note `state._migration_write_set`
  carries at its own definition -- it turns a guard that is merely unread into a status that
  escapes. The substitute is built: the validator warns and the session brief announces every
  accepted task with no verdict.
  Plain German: „Eine abgenommene Aufgabe verlangt keinen Nachweis; gemeldet wird sie trotzdem, in
  der Prüfliste und beim Sitzungsstart."
* **H106 | BUG-0190** -- how often a QA suite ran is prose: no field on the immutable `EVD` counts
  runs. Same immutability wall as H108, one step further (a COUNT would have to be written after
  the fact). Bound: the role text, the constitution's GATE step and the PM's ladder.
  Plain German: „Wie oft eine Testsuite gelaufen ist, steht nirgends als Zahl — nur als Text im
  Rollenauftrag."

### C. The answer is not derivable from this tree (world / provider limit)

* **H133 | BUG-0216** -- the SDK bridge cannot carry the third condition of
  `approvals._assert_minting_caller`, because the embedding program IS `__main__`: no derivation
  inside this tree can tell an embedding program from the kernel's own caller. Bound, measured: the
  route stamps every record (`program_answer_via_agent_sdk` against `user_answer_via_approval_hook`)
  and the card reads the stamp out; the kernel refuses every `IRREVERSIBLE_KINDS` on the program
  route (measured at `push`, no live token after it); and `gate_git` refuses, as a process, every
  merge over an item approved that way.
  Plain German: „Wer das Paket in ein eigenes Programm einbaut, kann damit eine Freigabe erzeugen —
  auf jedem solchen Datensatz steht aber, dass ein Programm geantwortet hat, und liefern lässt sich
  damit nichts."
* **H157 | BUG-0239** -- no reader judges the WORDING of a work-order line. A gate over order prose
  falls wrong in both directions, which FR-0010 decided BEFORE the measurement. Bound: the reading
  is a step IN the work loop, each of the five ways names its decision item, and the section claims
  no protection -- all three measured.
  Plain German: „Ob ein Arbeitsauftrag sinnvoll formuliert ist, liest kein Programm nach; das bleibt
  die Aufgabe der Lesung, die im Arbeitsablauf steht."
* **H54 | BUG-0146** -- an unbound but still RUNNING child is reported as "nothing ever tracked this
  run". The statement is TRUE of the record, and the record is all there is: no derivation can see a
  child nothing bound. Bound: gate layer 3 refuses an unbound child every write, so it could not
  have delivered anything that would be lost.
  Plain German: „Ein Helfer, den niemand zuordnen konnte, wird als unverfolgt gemeldet — schreiben
  durfte er ohnehin nichts."
* **H179 | BUG-0261** -- 106 active bugs whose named tests pass have no verdict, because a passing
  run does not say WHICH of the two it means: for a migrated hole the test that names it is usually
  the test that PINS the gap. AC-2 asks for a property in the store that separates "the test proves
  the fix" from "the test pins the gap", and nothing in the store carries it -- `regression_tests`
  names its test either way. That separation is a READING of the item beside its test; inventing it
  from a run outcome would write false verdicts through the kernel, which is exactly what the item
  forbids. THIS STREAM IS ITSELF A DATA POINT: every row above states which of the two its test is,
  in prose, one at a time -- 43 readings is what it costs.
  Plain German: „Dass ein Test grün ist, heißt nicht, dass der Fehler weg ist — manche Tests halten
  die Lücke fest. Das muss ein Mensch je Eintrag lesen."
* **H110 | BUG-0194** -- a check whose file this kernel cannot parse is answered UNDECIDED. Making
  it an error bans the merge of every project whose tests are not Python, with nothing to clear it;
  reading the file would need a parser for a language this tree does not contain. Bound: the
  producer verifies nothing it cannot read, the warning names whose question it is, and the blocker
  stays sharp for readable checks.
  Plain German: „Einen Test in einer anderen Programmiersprache kann der Kern nicht lesen; er sagt
  dann ‚weiß ich nicht' statt den Merge zu sperren."
* **H134 | BUG-0217** -- `blocked` is a state and not a measurement: whether the browser really was
  missing is the truth of a human's sentence, and no derivation from this tree reaches it. Bound:
  a wrong `blocked` buys nothing (it closes the gate exactly as a `fail` does), the record is
  immutable, and the limit stands in the vocabulary comment, in the flag's help and in the refusal.
  Plain German: „Wenn jemand angibt, eine Prüfung sei blockiert gewesen, glaubt das System den
  Grund — nachprüfen kann es ihn nicht; geliefert wird deswegen trotzdem nichts."

### D. A measured design whose substitute is built (no defect found to fix)

* **H44 | BUG-0136** -- four limits of the amendment derivation, none an attack chain. The one that
  looked closable, comparing `target_revision` as a VALUE, was rejected on measurement: the root's
  revision bumps on every hashed-field change, so comparing it would drop the criteria of every
  amendment the moment the root moves -- an over-refusal on a live route, while the amendment
  already borrows nothing but user-signed content.
* **H56 | BUG-0148** -- a killed bridge run leaves a mixed bundle and undoes nothing; the second run
  lifts cleanly (rc 0, `project_memory` intact, no data loss measured). The bridge's own docstring
  says "what a KILLED run leaves is not undone". A transactional copy is a different design, not a
  repair of this one.
* **H132 | BUG-0215** -- the plan approval's list is unbounded. Capping it at `BATCH_LIMIT` was
  rejected on measurement: the cap exists for the per-entry EVIDENCE walk of `verification`, which a
  plan has none of, and a project with twelve goals could then never get a plan approval at all.
  The bounds that do the work are built: the question NAMES every goal (never a count), each goal's
  own scope manifest is hashed so one changed goal falls out and the rest stand, an empty list is
  refused, and delivery and acceptance stay per goal.
* **H86 | BUG-0178** -- three limits of ONE V1 recogniser that `migrate` and `report` share. Closing
  them means writing a SECOND definition of "a V1 record", which is the defect house rule 1 names.
* **H60 | BUG-0152** -- `document_sources` enforces nothing. Bound: an empty filing plan refuses the
  first document anyway, fail-closed, and the coverage gap is announced at every office session
  start.
* **H84 | BUG-0176** -- the reference-skill derivation informs and enforces nothing; the dispatch
  header grants nothing on it, and the second tripwire direction is tautological on a derivation.
* **H79 | BUG-0171** and **H76 | BUG-0168** -- the document write route's measured edges: an
  invented second file without the `staging/` prefix is invisible (the derivation reads NAMES, not
  intentions), the same WRONG route text in every owner definition passes (equality is checked,
  correctness is not), an approval covers a re-write of the same bytes within its hour, and four
  edges with a safe direction. Each is bounded in its entry; none is an attack chain, and each
  closable one would need the same second definition H86 names.
* **H171 | BUG-0253** -- this repository derives no rung because it runs no kit, and DEC-0078 (4)
  forbids a default ladder in the kernel. The item's own AC-1 says a DEC decides whether the
  kit-less kernel may read a declaration from a config value. Building it without that decision
  would preempt the user; it goes to the lead as a DEC-first question.

## Seam handoffs

Each one is a patch this stream measured and may not write. File, line, before, after.

(Rework 1: S2 is CLOSED -- my parser half is applied and stream B's 17 kit call sites landed, so
`tools/test_hooks.py -k evidence_command` is green again. S1 and S3 stand.)

### S1 -- H197 / BUG-0281: the enforcement layer's reader still asks `is_terminal` (USER's shell)

* file: `.claude/hooks/_harness.py`, in `Reference.terminal` (the `automata` branch; the kernel side
  is already built and green).
* BEFORE (the paragraph and the line):

      WHAT IT DOES NOT ASK is whether an item in a NON-terminal status still has work in it:
      `SR` reaches `ACCEPTED` and stays there for good, so it counts as open work for ever
      (`docs/POST_V2_WISHLIST.md` H7). Closing that needs a "done" notion the kernel's `AUTOMATA`
      does not have.

* AFTER (paragraph replaced; the code line that asks the automaton becomes the kernel's own
  `is_finished`):

      A NON-TERMINAL STATUS CAN STILL BE A LIFE END, and the kernel is what says so: `SR` reaches
      `ACCEPTED` and holds, which is why `backlog_types` carries `done_states` beside `terminals`
      (BUG-0281). Asked here through `backlog_types.is_finished`, so this reader and the kernel
      cannot disagree about what "finished" means.

  and the answer for a type WITH an automaton becomes
  `backlog_types.is_finished(self.item_type, self.status)` instead of
  `self.status in automata[self.item_type].terminals`.
* why the user: `.claude/hooks/**` is closed to every role in this repository; the remedy every
  refusal prints is "run the fix from a shell OUTSIDE Claude Code and restart the session".
* arbiter after the patch: `python -B -m pytest .claude/hooks/test_gates.py -q -k "carries_work or
  todo"` plus a task-list entry naming an ACCEPTED `SR`, which must stop being accepted as open work.

### S2 -- H108 / BUG-0192: `--run-scope` mandatory, and the 13 texts that spell the call (KIT stream)

* kernel side (mine to write, NOT written -- see below): `team-kits/kernel/cli.py`, the `evidence`
  subparser.
  BEFORE: `evidence.add_argument("--run-command", metavar="LINE", help=...)` and
  `evidence.add_argument("--run-scope", choices=sorted(RUN_SCOPES), help=...)` -- both optional.
  AFTER: both `required=True`, with the help line saying that an Evidence which does not declare
  its run counts as a full one and that is what BUG-0192 is about.
* kit side (the other stream's): every shipped text that spells out an `evidence` call has to gain
  `--run-command` and `--run-scope`. WHICH texts is not a list to memorise -- it is exactly what
  `tools/test_hooks.py::test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires`
  walks (`_texts_that_name_the_evidence_vocabulary`); that node reads the parser's required set and
  holds it against them, so it names every file that needs the edit the moment the parser changes.
  13 call sites were measured when that test was written (both `gate_git` copies, the three auditor
  SKILLs, the QA and reviewer SKILLs).
* WHY IT IS NOT HALF-APPLIED: making the parser strict without the texts turns that node red for
  every stream in this tree. It is ONE patch in one commit or it is not this round's.

### S3 -- H183 / BUG-0265: the installer records what it copied outside `.claude/` (KIT stream)

* files: `team-kits/scaffold_team.sh` and `team-kits/scaffold_team.ps1` (byte-twins; forbidden to
  this stream, and `KIT_SPECIFIC_HOOKS` does not cover them).
* change: while copying the script templates, append every destination path (repo-relative, forward
  slashes) to a manifest beside the one the provider layer already gets --
  `.claude/provider_artifacts.json` is the shape to follow, and the twin's existing writer for it
  is the place to hang it.
* kernel side, AFTER the installer writes it (mine, one round later): `report.installed_kit_paths`
  reads that manifest instead of `INSTALLER_SCRIPT_DIRS`, and the enumeration plus its two-ended
  tripwire go away with it.
* ORDER MATTERS: the kernel half alone is a reader of a file nobody writes.

## Rows handed over by stream C at 11:14 (its files, my kernel)

### H164 | BUG-0246 | INSTR | CLOSED  (clock 2026-09-12 11:23)

* mechanism, as C handed it over: the defect is the ORDER, not the collection -- the judge that
  notices an unresolvable test citation runs AFTER the item is in the store, and this migration is
  idempotent, so a second run answers "already in the store" and repairs nothing.
* change: `team-kits/kernel/holes.py` -- `test_modules_under` (pytest's own rule, the file NAME,
  applied to the tree), `citation_resolution` (asked through `kernel.naming_tests`, the one reader
  this repository already decides "does this test exist" with), `_assert_every_citation_resolves`,
  called in `migrate` BEFORE `capture_migrated_hole` and on the dry run too.
* MEASURED CORRECTION to the item: the module-name case it names (`tools/test_one.py` in backticks)
  is ALREADY dropped by `cited_tests` -- its citation splitter leaves the tail `py`, which does not
  start with `test_`. What still got through is a plain name that resolves to NO test or to
  SEVERAL; both are rows in the test.
* a checkout that declares no test module at all is not asked -- there every citation resolves to
  nothing, so a refusal would be about the checkout. That is also what keeps the 14 nodes of
  `tools/test_migrate_holes.py` (C's file, not written by me) green over their synthetic trees;
  measured: 11 of them went red on the first, unguarded version.
* red-first: the call removed from `migrate` ->
  `FAILED tools/test_kernel.py::test_a_citation_that_names_no_test_stops_the_run_before_it_writes`
  with "the item was written before its citations were judged" -- the ORDER itself, measured by a
  `capture_migrated_hole` that refuses to be reached. 1 failed 132 deselected in 2.49s; reverted.
* naming node: `tools/test_kernel.py::test_a_citation_that_names_no_test_stops_the_run_before_it_writes`
  (`tools/test_migrate_holes.py` is stream C's file and outside my allowed_scope, so the test for
  the kernel change lives in the kernel suite).
* suites: `tools/test_migrate_holes.py tools/test_gaplog.py` green (28 passed together with
  `test_pointer_sweep`, whose 3 installer nodes are the unstamped-tree class).
* EVD-0368.

### BUG-0032 | the orphan heuristic | CLOSED  (clock 2026-09-12 11:23)

* mechanism: `report.validate_state` called a staging directory an orphan by its NAME alone, so a
  directory an ACTIVE record points into through `artifact_refs` was reported as removable -- and
  the record IS that pointer. Live in this store: the generation-6 streams wrote
  `staging/<task-id>/protocol.md` into their evidence (eight of C's, and every one of mine).
* change: `team-kits/kernel/report.py` -- `_items_pointing_into_staging`, asked of `artifact_refs`
  and of nothing else: a mention in prose is not a reference, and reading prose would make any item
  that discussed a directory keep it alive.
* red-first: the two lines that consult it removed ->
  `FAILED tools/test_report.py::test_a_staging_dir_an_active_record_points_into_is_not_an_orphan`
  ("Left contains one more item: 'staging/TSK-0999'"), 1 failed 136 deselected in 2.87s; reverted.
* naming node: `tools/test_report.py::test_a_staging_dir_an_active_record_points_into_is_not_an_orphan`.
* suites: `tools/test_report.py` 137 passed in 64.7s.
* EVD-0369.

## The verification batch lines for the lead

Every line was built against a STORE COPY first (`rig/project_memory`, copied 11:27 -- it has to
sit beside the rig's `tools/`, because the coverage reader resolves a node against the directory
the state tree sits in; parked anywhere else every id is refused with "no test in this checkout",
which is an answer about the copy and not about the id). All three: **0 refused**.

    request-approval verification --batch BUG-0173 BUG-0193 BUG-0211 BUG-0266 BUG-0195 BUG-0278 BUG-0140 BUG-0236 BUG-0218 BUG-0225
    request-approval verification --batch BUG-0231 BUG-0226 BUG-0224 BUG-0163 BUG-0144 BUG-0281 BUG-0210 BUG-0213 BUG-0238 BUG-0271
    request-approval verification --batch BUG-0246 BUG-0032

22 ids, every closed one in exactly ONE line. BUG-0242 is deliberately in none: its evidence is
`blocked`, not `pass`.

## More unstamped-tree reds (same class as the `tools/test_kitupdate.py` event above)

* `tools/test_light_kit.py::test_the_pilot_rig_leases_three_orders_of_different_size_per_kit`
  (11:15) -- `scaffold_error` with a PowerShell `ParserError: UnexpectedToken` out of
  `team-kits/scaffold_team.ps1`, which another stream was editing (mtime 10:52:33); the rest of the
  file, 25 nodes, passed.
* `tools/test_pointer_sweep.py::test_the_root_files_the_sweep_skips_are_installed_and_would_be_noisy`
  (11:25, all three kits) -- the same installer sentence as before:
  "does not hash to the `content:` in its own VERSION -- the kit source has been edited since it
  was stamped". 28 of 31 nodes in that run passed.
  Both are the missing kit stamp, which belongs to the merging item; neither is a finding against
  this stream, and both have to be re-measured after `bump_kit_version.py`.

## RUNS (selections, one at a time, in the order they were made)

| suite / selection | result | duration | why this one |
|---|---|---|---|
| `tools/test_report.py -k "mint or invoked or quoted or registration_that_could_not_block"` | 5 passed | 1.2s | the mint reader |
| `tools/test_report.py` (three times, last at 11:22) | 132 / 134 / 137 passed | 30.2s / 28.9s / 64.7s | every reader of `report.py` |
| `tools/test_hooks_v2.py -k "matrix_still_sees_the_gates_behind_the_launcher or accepts or registered_chain or tool_set"` | 15 passed | 11.0s | the OTHER callers of `report._invoked_scripts` |
| `tools/test_plan_diagram.py tools/test_board.py` | 91 passed | 27.5s | readers of `plan_diagram` and of `state.board_entries` |
| `tools/test_state.py` / `tools/test_state.py tools/test_backlog_types.py` | 61 / 113 passed | 8.4s / 19.1s | readers of `state.board_row`, `board_entries`, `_walk_stored_files`, `AUTOMATA` |
| `tools/test_report.py tools/test_state.py tools/test_migrate_holes.py` | 211 passed | 48.3s | the three readers of the validator walk |
| `tools/test_approvals_dispatch.py` (full, once) | 222 passed + 3 foreign reds | 202s | readers of `approvals` and `dispatch` |
| `tools/test_approvals_dispatch.py -k "routine or card_of_a_list or zombie or stop or scope or seam"` | 32 passed | 33.4s | the selections this stream touched |
| `tools/test_ladder.py` | 49 passed | 56.9s | the reader of `dispatch.acceptance_is_test_shaped` |
| `tools/test_parallel_scopes.py` | 18 passed | 24.7s | the reader of `scopes.overlaps`/`pair_seam`/`check` |
| `tools/test_parallel_streams.py` | 33 / 34 passed | 31.4s / 30.9s | the second reader of `scopes` and of the cadence vocabulary |
| `tools/test_backlog_types.py` | 52 passed | 3.4s | `AUTOMATA` + `is_finished` |
| `tools/test_kernel.py -k "retention or filing_rule"` / `-k "filing or retention or evidence or approval"` | 5 / 8 passed | 5.8s / 6.8s | the reader of `approvals.filing_rule_subject_manifest` |
| `tools/test_kitupdate.py -k "cannot_be_read_at_all"` / full | 1 passed / 23 failed 64 passed | 1.0s / 353s | `kitupdate.pending_entries`; the full run is the unstamped-tree event |
| `tools/test_light_kit.py` | 25 passed, 1 unstamped-tree red | 40.2s | the readers of `KIND_LABELS` and `build_question` |
| `tools/test_migrate_holes.py tools/test_gaplog.py tools/test_pointer_sweep.py` | 28 passed, 3 unstamped-tree reds | 38.7s | the readers of `kernel.holes` |
| `python -m ruff check team-kits/kernel/ tools/` | All checks passed | - | every file this stream wrote |

NOT run, and deliberately: `bump_kit_version.py` (the merging item stamps once), the full declared
surface (gate 5 refuses it without `DELIVERY_RUN=`, and it is the merge's), `commit`, `push`, any
mint, any BUG transition.

Last clock reading of this protocol: 2026-09-12 11:31.

## COUNTS (honest)

* rows in the order: 41 holes + BUG-0271 + the verifier's G3 = 43, plus 2 handed over by stream C
  at 11:14 (H164/BUG-0246, BUG-0032) = **45**.
* **CLOSED with a naming test and a measured red-first: 23** --
  H81/BUG-0173, H109/BUG-0193, H127/BUG-0211, H184/BUG-0266, H111/BUG-0195, H194/BUG-0278,
  H48/BUG-0140, H154/BUG-0236 (second residue), H135/BUG-0218, H142/BUG-0225, H148/BUG-0231
  (second residue), H143/BUG-0226 (measured bound), H141/BUG-0224 (two-ended tripwire),
  H71/BUG-0163, H52/BUG-0144, H197/BUG-0281 (kernel half), H126/BUG-0210 (measured bound),
  H130/BUG-0213, H156/BUG-0238, BUG-0271 (measured, already built), the verifier's G3,
  H164/BUG-0246, BUG-0032 -- and H160/BUG-0242 is NOT counted here (see below).
* **naming written, measurement BLOCKED: 1** -- H160/BUG-0242 (EVD-0361 blocked; the installer
  refuses on the missing kit stamp).
* **not closed, handed to the USER through the lead: 21** -- three of them because the fix lies
  outside this stream's files (H183, H108, and H197's consumer), the rest with the measurement that
  says why and the one plain-German sentence an exception would carry. NONE of them is filed as an
  exception by me: that is the user's click.
* **downgraded by me: 0.** Every row above is either closed or addressed to the user.

# Rework 1 -- against the verifier's round 1 (FAIL), read WHOLE (147 lines, 2026-09-12 11:52)

The report is short enough that reading it whole was cheaper than opening it twice; the cost is
named here because the reading discipline asks for that.

## B1 + B2 | H194 / BUG-0278 | blocking | CLOSED  (clock 2026-09-12 12:02)

* B1, and it is the dangerous direction: `_DENIES_RX` listed `never`/`none` and not their German
  twins, so "Ein Test wird niemals rot" -- a sentence that DENIES a test -- read as a test-shaped
  acceptance and GRANTED the cheap rung. The module's own comment says this reader fails towards
  the expensive default on purpose.
* B2, which the first repair introduced: the prepositional complement was read "to the end of the
  clause", and in the FRONTED form that swallows the main clause -- "Without the fix a test goes
  red." was a promise before this round and a refusal after it.
* change, `team-kits/kernel/dispatch.py`:
  - `_CLAUSAL_DENIERS` / `_PREPOSITIONAL_DENIERS` are VOCABULARIES now, not regex literals, with
    one spelling convention (a trailing `*` means "and its inflections") and `_word_alternation`
    building the pattern. `nie`, `niemals`, `nirgend*` added.
  - `_COMPLEMENT_WORDS = 3` -- ONE constant with its measurement beside it: "ohne Test" needs 1,
    "ohne einen Test" 2, "without a regression test" 3, and the fronted form puts the test word
    fifth. Widening it re-opens B2, and both rows stand in the naming test.
* measurement: 27 rows through `dispatch._sentence_names_a_test` against the running code,
  0 wrong -- 9 grants (including both fronted forms and both German compounds) and 18 refusals
  (the four German clausal negations of B1, every row round 1 already held, `ohne Test`, `ohne
  Regressionstest`, `without a regression test`, `latest`, `protest`).
* the docstring claim "every clausal negation stays a refusal" is GONE: it claimed a property about
  a LANGUAGE that the code cannot have. What stands there now is the claim the code does build --
  every negator `_CLAUSAL_DENIERS` lists -- with the tripwire that holds the list named beside it.
* red-first, both halves:
  - `nie`/`niemals`/`nirgend*` removed -> `FAILED tools/test_ladder.py::test_a_german_acceptance_line_is_read_like_its_english_twin`
    AND `::test_every_listed_denial_word_is_the_reason_its_sentence_is_refused`, 2 failed in 1.90s
  - the word window dropped back to the clause end -> the first node FAILED on
    "Ohne den Fix wird ein Test rot.", 1 failed in 1.69s
  - reverted, green.
* naming nodes: `tools/test_ladder.py::test_a_german_acceptance_line_is_read_like_its_english_twin`,
  `tools/test_ladder.py::test_every_listed_denial_word_is_the_reason_its_sentence_is_refused`.
* EVD-0381. BUG-0278 goes back into a batch line with this.

## B3 | H135 / BUG-0218 | blocking | header corrected AND the class closed  (clock 12:02)

* the header paragraph of `team-kits/kernel/scopes.py` still described `a/*x` x `a/y*` as the open
  class -- the very pair the round closed (house rule 3, the alarming direction). It now states the
  class the VERIFIER measured by brute force, with its mechanism in one sentence.
* and that class is BUILT, not just named: `_readings` offers a wildcard-free entry in BOTH the
  readings the gate has -- the literal path and the directory prefix -- because that is what the
  gate does with it, and `_unify` could only take the literal.
* measurement: all SIX pairs the verifier measured blind now yield a witness
  (`a/b` x `a/**/c` -> `a/b/c`, `a/b` x `a/*/c`, `a/b` x `a/**/*.py`, `a/b` x `**/c`,
  `a` x `**/c`, `a` x `*/c`), and three disjoint pairs still yield none. The live cut is
  unchanged: `check-scopes` over TSK-0141/0142/0143 at 11:57 -> `disjoint`, rc 0.
* red-first: `_readings` taken back out of `pair_witnesses` ->
  `FAILED tools/test_parallel_scopes.py::test_a_wildcard_free_entry_is_offered_as_the_directory_prefix_the_gate_reads`
  (`assert []`), 1 failed 18 deselected in 2.49s; reverted, green.
* naming node: `tools/test_parallel_scopes.py::test_a_wildcard_free_entry_is_offered_as_the_directory_prefix_the_gate_reads`.
* EVD-0382.

## B4 | H81 / BUG-0173 | blocking | the second copy of the claim is gone  (clock 12:02)

* `team-kits/kernel/approvals.py` still carried the paragraph `report.py` had already lost: it said
  the mint reader prints its sentence at a project that CAN mint, on a quoted path with a space.
  Measured false against the running code by the verifier. Replaced with what the code now does and
  with the one thing that stays undecided, which is stated where it is decided (`_runs_no_file`).
* no red-first: this is a CLAIM, not a branch; what the code does is measured by BUG-0173's own
  naming node, which is green.

## B5 | BUG-0271 | CLOSED  (clock 12:02)

* two defects in the sentence a non-developer answers: "diese 1 Fehler" / "1 Lücken bleiben offen",
  and -- for a list-bound request that carries an item -- a QUESTION about the item beside an
  approving OPTION about the list.
* change, `team-kits/kernel/approvals.py`: `_numerus` (the singular form carries no digit at all),
  used by all four list-bound forms; and `build_question` asks the kind's own `TARGET_FORMS` FIRST,
  so a kind whose subject is not an item describes its subject in both texts.
* `tools/test_light_kit.py`'s older assertion "if there is an item, the sentence names it" was
  narrowed to the kinds WITHOUT their own form -- it had encoded the defect.
* red-first, both halves: `_numerus` forced to the plural -> the naming node FAILED with
  "the singular form still carries a digit: ... diese 1 gemessenen Lücken"; the item test put back
  in front of the form -> FAILED with "PR-0001 is contained here". 1 failed 26 deselected, 2.27s.
* naming node: `tools/test_light_kit.py::test_a_list_bound_question_reads_in_the_right_numerus_and_names_the_same_subject_as_its_card`.
* EVD-0383. The earlier protocol row claiming "NOTHING remains" was wrong and is superseded here.

## B6 | H106 / BUG-0190 | CLOSED  (clock 12:04)

* the verifier is right and my earlier reason was not: an `EVD` being immutable is a fact about the
  RECORD and says nothing about a ROLLUP. Every record already declares its run scope.
* change: `report.generate_session_brief` counts the QA evidence by declared scope into
  `budget_status.qa_runs`, in the walk the brief already does. An UNDECLARED record is its own
  bucket, never folded into `full` -- that silence is BUG-0192 and hiding it here would be a second
  place where an undeclared run counts as a whole one.
* red-first: `or "undeclared"` changed to `or "full"` -> `FAILED tools/test_report.py::test_the_brief_counts_the_qa_runs_by_the_scope_they_declare`
  (`{'full': 3, ...} == {'full': 2, ..., 'undeclared': 1}`); reverted, green.
* naming node: `tools/test_report.py::test_the_brief_counts_the_qa_runs_by_the_scope_they_declare`.
* EVD-0384.

## B7a | H60 / BUG-0152 | CLOSED  (clock 12:06)

* the third answer, as the verifier asked and as `kitupdate.pending_entries` got it this round:
  `filing.coverage_not_compared` tells "every source is covered" from "nothing was compared", and
  `report.validate_state` says it.
* BOUNDED, and the bound was measured rather than reasoned: the first cut fired on 12 nodes of
  `tools/test_migrate.py`, because a fresh office project ships plan and profile BOTH empty and the
  interview fills them. That is `gate_filing`'s case, at the first document. So this reports the
  state it is really about -- documents filed under REAL rules while nobody recorded what the
  business receives.
* red-first: the "names no sources" branch removed -> `FAILED tools/test_kernel.py::test_a_filing_profile_that_answers_nothing_is_told_apart_from_full_coverage`;
  reverted, green.
* naming node: `tools/test_kernel.py::test_a_filing_profile_that_answers_nothing_is_told_apart_from_full_coverage`.
* EVD-0385.

## B7b | H171 / BUG-0253 -- DEC proposal H171 (for the lead to record)

**Decision proposed.** A project with no installed kit reads its model ladder from a declaration
the PROJECT names, not from a kit record: `project_memory/project_config.yaml` gains an optional
`ladder:` key naming a file, and `dispatch.kit_installation` falls back to it when
`.claude/team_kit_roles.txt` is absent. Where neither exists the lease keeps saying `absent`.

**Alternatives, and why they lose.** (1) A DEFAULT ladder in the kernel -- refused by DEC-0078 (4),
and rightly: a kernel that invents a rung decides a cost the project never declared. (2) Reading
the role files' own `model:`/`effort:` pins -- they are provider frontmatter, one per role, with no
statement about which endpoints a project may use; the ladder is a project-level declaration and a
per-role pin is not one. (3) Leaving it: the lease says `absent`, which is honest, but then
FR-0047's visibility rests on a line that says nothing was derived, and this repository -- whose
own implementer and verifier are dispatched by the kernel directly -- can never show a rung.

**Measurement behind it.** `PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory
ladder TSK-0130` answers `{"absent": "no scaffold record (.claude/team_kit_roles.txt) names a kit
for this project ..."}`; every fixture of `tools/test_ladder.py` is such a project, and
`test_a_project_without_a_scaffold_record_gets_no_rung_and_no_refusal` pins today's answer.

**Why the build did not follow in this order.** The decision names a new key on a kit document that
`gate_write_scope` leaves no writer for after an install, so the shape has to be decided WITH the
user before it is built; and `DEC-0078 (4)` is the standing decision the proposal amends. This is
the item's own AC-1 ("a DEC records ..."), not a limit.

## B8 | the count  (clock 12:41)

The earlier table counted `H197` twice -- once among the closed rows (its kernel half) and once
among the not-closed ones (its consumer). One row, one count: H197 counts as CLOSED, and its
consumer is a SEAM, which is its own list. The corrected counts stand at the end of this protocol.

## The contract changes the rework order named

* **H58 / BUG-0150 -- BUILT, with its migration** (clock 12:33). `TSK` joins `CONFIRMING_EVIDENCE`,
  so `DONE -> VALIDATED` owes the `test` Evidence its edge claims. BOTH measured objections are
  answered rather than argued away: `migration_writable_statuses` reads that fourth guard now (the
  note in `state.py` had said in advance that adding such a type would turn an unread guard into a
  status that escapes -- so the guard was built in the same breath), and the V1 row
  `("TSK","VALIDATED")` lands at `DONE`, with the V1 word riding into the archive in the legacy
  field. The import states no verdict nobody made, which is the argument the neighbouring `DONE`
  row already carries. Two tests that encoded the old design were rewritten:
  `test_the_migration_write_set_reads_three_of_the_four_edge_guards` is now `..._all_four_...` and
  measures the DIFFERENCE (every confirming target is out, and at least one comes back in when the
  guard is removed), and the second-opinion walk in
  `test_the_statuses_a_migration_may_write_are_the_ones_reachable_without_an_approval` skips the
  confirming edge too.
  Red-first: with `TSK` out of `CONFIRMING_EVIDENCE` the naming node fails on
  `"VALIDATED" not in migration_writable_statuses("TSK")`; measured as the two suite reds that
  brought the old tests down before they were rewritten (`2 failed, 59 passed`), and green after.
  Naming node: `tools/test_state.py::test_a_validated_task_owes_the_verdict_its_edge_says_it_has`.
  EVD-0386.
* **H155 / BUG-0237 -- MEASURED LARGER THAN THIS ORDER, and the missing piece is not code.**
  Measured 2026-09-12: 51 files spell the field, 108 occurrences; the store carries 12 goals across
  THREE spellings (`technical_enabler` 3, `normal` 4, `large` 5) and the shipped suite exercises at
  least five more (`feature`, `normal`, `research`, `exploratory`, `technical_enabler`), while
  `dispatch.SR_EXEMPT_CLASSES` names two (`small`, `technical_enabler`). Nothing in this tree
  DECLARES the set -- there is no file a closed vocabulary could be derived from, and a set chosen
  here would refuse every stored goal outside it in every project. What is missing is the decision
  "which classes may a goal carry", which is a product vocabulary the user owns; the mechanism
  after it is `state._CLOSED_VOCABULARY` plus one migration row per value.
  Plain German: „Wie groß ein Ziel ist, darf heute jedes Wort sein; eine feste Liste kann erst
  festgelegt werden, wenn jemand sagt, welche Wörter erlaubt sind."
* **H170 / BUG-0252 -- MEASURED: there is no type to put the field on.** `ROOT_TYPE_BY_KIT` names
  `dev-team: PR` and `research-team: RQ` and NOTHING for the office kit -- an office project has no
  goal item at all (its documents take that place), and `class` exists on `PR` and `RQ` only. So
  "give the office goal type a class field" has no subject: closing it means giving the office kit
  a root ITEM TYPE, with its automaton, its approval edges and a migration for every office project
  already running. That is a kit-shaped decision, not a kernel field.
  Plain German: „Im Büro-Team gibt es gar kein Ziel-Item, an dem eine Größe hängen könnte; solange
  das so ist, läuft große Büro-Arbeit auf der mittleren Stufe."

## The rows handed over by stream B at 12:09

* **BUG-0055 -- CLOSED by the PRODUCER, and deliberately NOT by `_SCOPE_FIELDS`** (clock 12:38).
  The item's `expected` offers two shapes and B named the tuple; measured, that shape costs a
  migration of every stored hash and kills every live approval, and it is not needed: `design_refs`
  is ALREADY in `_SCOPE_FIELDS` and in `HASHED_FIELDS`. What was missing is the producer --
  `staging.DESIGN_REF_TYPE`'s own note said exactly that, and said the resolver would follow the
  day the freeze appends. `freeze_wireframe` appends now; `frozen_design_dirs` returns both trays.
  E17 and E18 both answered: a re-freeze moves `design_refs` (and the first one bumps the root's
  revision out of the status a scope approval stands in), and "does this UI scope name a wireframe"
  is a question with a field to read.
  MEASURED while writing the counterweight: the companion schema already refuses a `derives_from`
  that is not a product id, so the reachable "no root" case is a root that is not in the store.
  Red-first: the append removed -> `FAILED tools/test_staging_cli.py::test_a_frozen_wireframe_is_a_design_reference_the_scope_hash_moves_on`
  (`KeyError: 'design_refs'`), 1 failed 98 deselected in 2.94s; reverted, green.
  The superseded `test_a_wireframe_directory_is_not_a_design_reference` was REMOVED -- its own
  docstring said it was written to turn red the day the producer landed. EVD-0389.
* **S2 remainder -- DONE, and the seam is CLOSED.** My parser half is applied (`--run-command` and
  `--run-scope` required), B added the pair to its 17 kit call sites, and I added the two
  spelled-out calls left in the kernel (`staging.py` reports-tray remedy, `state.py` confirming-edge
  remedy) plus the 9 call sites in `tools/test_staging_cli.py`.
  `python -B -m pytest tools/test_hooks.py -k evidence_command` -> **1 passed, 1064 deselected in
  6.81s**. Before B's half landed the same selection was 1 failed with
  "Extra items in the left set: '--run-scope', '--run-command'" -- that is the seam red, measured at
  both ends. EVD-0388.
  `tools/test_staging_cli.py::test_cli_evidence_records_the_run_behind_the_verdict_or_neither_half_of_it`
  measured the OLD contract (an undeclared record carries neither key, which the parser now makes
  unreachable); it is rewritten as `..._and_refuses_a_half_of_it`, with three rows and a different
  refuser in each: the parser for "neither", the KERNEL for "half" (a caller that never met the
  parser), and the recorded pair for the legal call.

## The six rows re-checked against the user's word -- one line each on why the fix is not in this tree

* **H133 / BUG-0216** -- the bridge cannot tell an embedding program from the kernel's own caller,
  because the embedding program IS `__main__`: the fact needed is a property of the HOST process,
  which no derivation inside this tree can produce.
* **H157 / BUG-0239** -- judging whether a work-order LINE is well phrased needs a reading of
  meaning; no predicate over the text decides it, and FR-0010 recorded that before it was measured.
* **H54 / BUG-0146** -- a child nothing bound leaves no record to derive from; the report is
  record-TRUE, and the only other source would be the provider telling us, which it does not.
* **H179 / BUG-0261** -- "does this passing test prove the fix or pin the gap" is a reading of the
  item beside its test; the store carries no property that separates them, and inventing one from
  a run outcome is what the item forbids.
* **H110 / BUG-0194** -- reading a test file in another language needs a parser for that language,
  which is not in this tree; the alternative, refusing, bans the merge of every non-Python project.
* **H134 / BUG-0217** -- whether a blocked run really was blocked is the truth of a human's
  sentence, and no file in this tree records the world it refers to.


## The verification batch lines, REBUILT after the rework (clock 2026-09-12 12:45)

Every line built against the store copy in the rig (`rig/project_memory`, copied 12:44, beside the
rig's own `tools/` so the coverage reader can resolve a node at all). All three: **0 refused**.
BUG-0278 is back in line 1 -- B1 is green and its two naming nodes carry it.

    request-approval verification --batch BUG-0173 BUG-0193 BUG-0211 BUG-0266 BUG-0195 BUG-0278 BUG-0140 BUG-0236 BUG-0218 BUG-0225
    request-approval verification --batch BUG-0231 BUG-0226 BUG-0224 BUG-0163 BUG-0144 BUG-0281 BUG-0210 BUG-0213 BUG-0238 BUG-0271
    request-approval verification --batch BUG-0246 BUG-0032 BUG-0055 BUG-0190 BUG-0152 BUG-0150 BUG-0192

27 ids, every closed one in exactly ONE line. BUG-0242 is in none: its evidence is `blocked`.

## RUNS of the rework (selections, one at a time)

| suite / selection | result | duration |
|---|---|---|
| `tools/test_ladder.py -k "german_acceptance or listed_denial or acceptance_reader"` | 4 passed | 0.7s |
| `tools/test_ladder.py tools/test_parallel_scopes.py tools/test_backlog_types.py` | 121 passed | 76.8s |
| `tools/test_light_kit.py -k "list_bound_question or english_enum_word or approval_kind_has_one_plain_word"` | 3 passed | 1.3s |
| `tools/test_approvals_dispatch.py -k "batch or exception_option or card_of_a_list or list_kind"` | 23 passed | 16.2s |
| `tools/test_report.py` | 139 passed | 38.4s |
| `tools/test_state.py` | 62 passed | 10.2s |
| `tools/test_migrate.py` | 143 passed (after the two remedy rewordings) | 231s |
| `tools/test_migrate_holes.py` | 14 passed | 11.7s |
| `tools/test_staging_cli.py` | 99 passed | 31.4s |
| `tools/test_kernel.py -k "filing_profile or retention or filing_rule"` | 6 passed | 4.5s |
| `tools/test_hooks.py -k evidence_command` | 1 passed (the S2 seam, green) | 6.8s |
| `tools/test_light_kit.py tools/test_parallel_streams.py` | 60 passed, 1 unstamped-tree red | 59.0s |
| `python -m ruff check team-kits/kernel/ tools/` | All checks passed | - |

The one red is the same class as before: `test_the_pilot_rig_leases_three_orders_of_different_size_per_kit`
fails in the installer with "does not hash to the `content:` in its own VERSION". The stamp belongs
to the merging item.

## COUNTS after rework 1 (H197 counted ONCE -- B8)

* rows: 43 of the order + 2 from stream C + 1 from stream B (BUG-0055; the S2 remainder is work on
  H108, not a row of its own) = **46**.
* **CLOSED: 28** -- the 23 of round 1 (BUG-0278 among them, now repaired) plus H106/BUG-0190,
  H60/BUG-0152, H58/BUG-0150, H108/BUG-0192 (parser half + B's half = the seam is closed) and
  BUG-0055; the verifier's G3 and BUG-0271 are counted in this number, BUG-0271 now with its
  numerus and subject repair.
* **naming written, measurement BLOCKED: 1** -- H160/BUG-0242 (EVD-0361, the installer stamp).
* **not closed, addressed to the USER through the lead: 17** (46 - 28 - 1) -- H183 (seam, the
  installer), H155 and H170 (measured sizes above), H171 (the DEC proposal above, for the lead to
  record), the six of group C (H133, H157, H54, H179, H110, H134, each with one measured line on
  why the fix is not in this tree) and the seven of group D still standing (H44, H56, H132, H86,
  H84, H79, H76). H197's CONSUMER is a seam and not a row of its own -- H197 itself is closed, and
  that double count was the verifier's B8.
* **downgraded by me: 0.**

Last clock reading of this protocol: 2026-09-12 12:45.

# Rework 2 -- against the verifier's round 2 (FAIL, narrow), read whole (123 lines, 13:07)

## R1 | BUG-0278 | the denial vocabulary was short in the dangerous direction  (clock 13:10)

* measured by the verifier and reproduced: "Nothing makes a test go red", "Neither the test nor the
  probe goes red", "Weder ein Test noch ein Nachweis wird rot" all GRANTED the cheap rung.
* change, `team-kits/kernel/dispatch.py`: `nothing` joins `_CLAUSAL_DENIERS` (it is the immediate
  twin of the listed `none` -- the same asymmetry BUG-0278 consisted of, inside one language), and
  `_CORRELATIVE_DENIERS = (("neither", "nor"), ("weder", "noch"))` is a PAIR and not a word: the
  first half alone stands in ordinary prose, so what denies is the construction, and both halves
  have to stand in order.
* the tripwire walks the pairs too, with the pair-specific end: the sentence with its SECOND half
  replaced has to be GRANTED, so neither half is carrying the refusal alone.
* red-first: `nothing` and the correlatives removed ->
  `FAILED tools/test_ladder.py::test_a_german_acceptance_line_is_read_like_its_english_twin`
  ("Nothing makes a test go red") AND
  `::test_every_listed_denial_word_is_the_reason_its_sentence_is_refused`
  ("a denial word without a measured sentence ... {'nothing'}"); reverted, green.

## R2 | BUG-0278 | a WIDTH was the wrong definition  (clock 13:10)

* measured: `_COMPLEMENT_WORDS = 3` flipped to the dangerous side from the fourth word --
  "The result goes red without any new regression test" and three German twins were granted.
* change: the complement now ends at the next DETERMINER, or at the clause end, whichever comes
  first, with the determiner that OPENS the complement skipped. A preposition governs exactly ONE
  noun phrase and a noun phrase is opened by its determiner -- that is a definition; a width is a
  calibration, and a calibration of a free-length phrase is what the two earlier readings both
  were. Nothing here has to find the finite verb.
* MEASURED WHILE BUILDING IT, and it narrowed the convention: with the deniers' `*` (`\w*`) the
  entry `ein` swallowed the adjective `einzigen`, so "ohne einen einzigen neuen Test" ended its
  complement before the test word and still granted. A determiner's tail is one of five German
  declension endings, so `_DECLENSION` is that set and the `-` convention is narrower than `*` on
  purpose.
* THE COMMENT NOW STATES THE PRICE, dangerous direction FIRST, which is what the verifier asked
  for: a complement carrying a SECOND determiner inside itself ends early, so a denial phrased over
  a genitive -- "ohne die Hilfe eines Tests" -- reads as a promise and buys the cheap rung. The
  other direction is cheap and is said second: a determiner missing from the list only lengthens a
  complement, which can cost an unnecessary refusal, never a grant.
* measurement: 35 rows through `dispatch._sentence_names_a_test`, **0 wrong** -- 9 grants
  (both fronted forms among them) and 26 refusals (the 3 rows of R1, the 4 of R2, and every row
  the two earlier rounds already held).
* red-first: the word window put back (`[:3]`) -> the naming node FAILED on
  "Das Ergebnis wird ohne einen einzigen neuen Test rot"; reverted, green.
* naming nodes: `tools/test_ladder.py::test_a_german_acceptance_line_is_read_like_its_english_twin`,
  `tools/test_ladder.py::test_every_listed_denial_word_is_the_reason_its_sentence_is_refused`.
* **EVD-0401 SUPERSEDES EVD-0381** -- that run predates both repairs and must not be read as the
  measurement of this reader.

## R3 | Seam S4 (user patch) -- the commit gate's remedy is rc 2 since this round  (clock 13:14)

* BLOCKING and this round built it: S2 made `--run-command`/`--run-scope` required, and
  `.claude/hooks/gate_commit_evidence.py` prints a remedy without them at EVERY blocked hand-over.
* measured by typing the printed line against this repository's own store, 13:14:
  `python scripts/harness.py evidence: error: the following arguments are required:
  --run-command, --run-scope`.
* the exact before/after is in `project_memory/staging/TSK-0141/s4-gate-commit-evidence-patch.md`,
  in the shape of the `h182` patch file, with the arbiter to run after it. The file is closed to
  every role here -- this is the FOURTH seam for the user's shell, beside S1.
* `gate_test_scope.py:709-712` already carries the pair (checked, correct).
* why no test saw it: `tools/test_hooks.py::_texts_that_name_the_evidence_vocabulary` reads the
  three kits' instruction files, the shipped kit modules and the README; `.claude/hooks/` of THIS
  repository is outside its corpus. Widening that corpus is stream C's file, so it is named here.
* THE TREE-WIDE GREP the order asked for, and what it found. Every text that spells a full
  `evidence` call: the three kits' `gate_git.py`/`gate_test_scope.py` and constitutions (stream B,
  already carrying the pair -- the reading test is green), `README.md` (stream C), the two
  `.claude/hooks/` files (S4 above, and `gate_test_scope.py` which is already correct), and FOUR in
  my own scope. Three were still unpaired and are FIXED in this rework:
  `team-kits/kernel/report.py:2217` (the contradicted-confirmation remedy),
  `team-kits/kernel/report.py:3044` (the accepted-task-without-a-verdict remedy) and -- already in
  rework 1 -- `team-kits/kernel/staging.py:525` and `team-kits/kernel/state.py:1599`.
  `team-kits/kernel/approvals.py:1170` already carried both flags.
  The remaining hits are PROSE that names the command without spelling a call (docs, hole files,
  decision records, `guard_no_adhoc.py`, `_kernel.py`) -- they teach no line anybody types.
* `tools/test_hooks.py -k evidence_command` after the three fixes: **1 passed, 1066 deselected in
  5.77s**.

## R4 | BUG-0271 | the card put a main clause into a prepositional phrase  (clock 13:12)

* the option reads "Erteilt die Freigabe ... FÜR <subject>", and the subject was "2 Lücken bleiben
  offen: ..." -- ungrammatical, where its twin at `:1403` delivers a noun phrase.
* change, `team-kits/kernel/approvals.py`: "eine Lücke, die offen bleibt" / "%d Lücken, die offen
  bleiben".
* the row in the naming test asserts the SHAPE that goes wrong -- a finite verb right after the
  count -- rather than the new wording, so a third phrasing of the same mistake is caught too.
* red-first: the main clause put back -> `FAILED tools/test_light_kit.py::test_a_list_bound_question_reads_in_the_right_numerus_and_names_the_same_subject_as_its_card`
  (`match='für 2 Lücken bleiben'`); reverted, green.
* **EVD-0402 SUPERSEDES EVD-0383.**

## DEC questions for the user (H155, H170, H171) -- three questions, not three exceptions

The verifier and the lead agree with each other and with me: all three are in-repo work standing
behind a DECISION. They are written here as questions a non-developer can answer, with what each
option costs. The items stay OPEN.

### Frage 1 (H155 / BUG-0237) -- Wie groß ist ein Ziel?

Jedes Produktziel trägt heute ein Wort für seine Größe, und das darf jedes beliebige Wort sein.
Im Speicher stehen drei Schreibweisen (`technical_enabler`, `normal`, `large` -- 12 Ziele), die
Tests kennen noch weitere. Das kostet: wer sich vertippt, bekommt eine Architekturrunde, die
niemand schuldete.

* **A -- feste Liste.** Sie sagen, welche Wörter erlaubt sind; alles andere wird beim Erfassen
  abgelehnt. Kosten: einmalig muss jedes schon gespeicherte Ziel auf ein erlaubtes Wort umgezogen
  werden (12 in diesem Projekt, unbekannt viele in Ihren anderen), und ein neues Wort braucht
  künftig eine Entscheidung.
* **B -- Liste ohne Zwang.** Die Liste steht da, ein fremdes Wort wird nur gemeldet, nicht
  abgelehnt. Kosten: nichts zieht um, aber der Tippfehler kostet weiterhin die Extrarunde -- er
  wird nur sichtbar.
* **C -- so lassen.** Kosten: bleibt wie heute; der Tippfehler bleibt unsichtbar.

### Frage 2 (H170 / BUG-0252) -- Soll das Büro-Team überhaupt Ziele bekommen?

Im Entwickler- und im Forschungs-Team gibt es ein „Ziel" als eigenen Vorgang. Im Büro-Team gibt es
das nicht -- dort treten die Dokumente an seine Stelle. Deshalb lässt sich für große Büro-Aufgaben
auch keine höhere Denk-Intensität anfordern: es gibt keinen Vorgang, an dem eine Größe hängen
könnte. Heute läuft Büro-Arbeit auf der mittleren Stufe.

* **A -- Büro bekommt einen Ziel-Vorgang.** Wie in den anderen Teams, mit Lebenslauf und Freigaben.
  Kosten: eine größere Umstellung, und jedes laufende Büro-Projekt muss sie mitmachen.
* **B -- Größe an die Aufgabe statt ans Ziel.** Die einzelne Aufgabe sagt, wie groß sie ist.
  Kosten: kleiner Eingriff, aber die Größe ist dann eine Angabe je Aufgabe statt eine Eigenschaft
  des Vorhabens.
* **C -- so lassen.** Kosten: große Büro-Arbeit läuft weiter auf der mittleren Stufe; laut
  Entscheidung DEC-0078 ist das der Wert für gewöhnliche Büro-Arbeit, also nichts läuft zu hoch.

### Frage 3 (H171 / BUG-0253) -- Woher nimmt dieses Repo seine Modellstufen?

Dieses Repo selbst benutzt kein Team-Paket, und deshalb leitet der Kern für seine eigenen Rollen
keine Modellstufe ab: der Auftrag sagt „keine Angabe". Die Stufen stehen stattdessen von Hand in
den Rollendateien.

* **A -- eine eigene Stufendatei.** Das Projekt nennt in seiner Konfiguration eine Datei mit den
  Stufen; der Kern liest sie, wenn kein Paket installiert ist. Kosten: eine neue Zeile in der
  Konfiguration, die nach dem Einbau eines Pakets niemand mehr schreiben kann -- sie muss also
  gleich richtig sein.
* **B -- so lassen.** Kosten: der Auftragskopf sagt weiterhin „keine Angabe", und die Stufen
  dieses Repos stehen nur in den Rollendateien; niemand kann sie an einem Ort nachlesen.

(Die Entscheidung von damals -- DEC-0078 (4) -- verbietet dem Kern ausdrücklich, eine Stufe zu
ERFINDEN. Option A widerspricht ihr nicht: dort wird eine Stufe gelesen, die das Projekt selbst
aufgeschrieben hat.)

## The batch lines after rework 2 (clock 2026-09-12 13:20)

Unchanged in content -- no id entered or left the closed set in this rework -- and rebuilt against
a FRESH store copy (13:19, beside the rig's `tools/`), because the two superseding EVDs changed
which record the coverage reader picks up. All three: **0 refused**.

    request-approval verification --batch BUG-0173 BUG-0193 BUG-0211 BUG-0266 BUG-0195 BUG-0278 BUG-0140 BUG-0236 BUG-0218 BUG-0225
    request-approval verification --batch BUG-0231 BUG-0226 BUG-0224 BUG-0163 BUG-0144 BUG-0281 BUG-0210 BUG-0213 BUG-0238 BUG-0271
    request-approval verification --batch BUG-0246 BUG-0032 BUG-0055 BUG-0190 BUG-0152 BUG-0150 BUG-0192

## RUNS of rework 2

| selection | result | duration |
|---|---|---|
| `tools/test_ladder.py -k "german_acceptance or listed_denial"` | 2 passed | 2.5s |
| `tools/test_ladder.py tools/test_light_kit.py` | 76 passed, 1 unstamped-tree red | 115.5s |
| `tools/test_light_kit.py -k "list_bound_question or english_enum_word"` | 2 passed | 1.1s |
| `tools/test_approvals_dispatch.py -k "batch or exception_option or card_of_a_list or list_kind or acceptance"` | 29 passed | 19.7s |
| `tools/test_report.py -k "brief or verdict or accepted"` | 24 passed | 17.4s |
| `tools/test_hooks.py -k evidence_command` | 1 passed | 5.8s |
| `python -m ruff check team-kits/kernel/ tools/` | All checks passed | - |

The one red is the unstamped-tree class named earlier (the installer refuses because the kit source
does not hash to its own VERSION); the stamp belongs to the merging item.

## COUNTS after rework 2 -- unchanged

46 rows: **28 closed**, 1 blocked measurement (BUG-0242), **17** addressed to the user. Rework 2
repaired two already-counted rows (BUG-0278, BUG-0271) and added one SEAM (S4). Of the 17, three --
H155, H170, H171 -- are now written as DEC QUESTIONS to the user rather than as exceptions.

Seams for the user's shell: **S1** (`.claude/hooks/_harness.py`, `is_finished`) and **S4**
(`.claude/hooks/gate_commit_evidence.py`, the remedy pair) -- the S4 patch file is
`project_memory/staging/TSK-0141/s4-gate-commit-evidence-patch.md`. Seam **S3** (the kit installer's
script manifest) stays with the kit stream; **S2** is closed.

Last clock reading of this protocol: 2026-09-12 13:20.

# Rework 3 -- against the verifier's round 3 (FAIL, two points), read whole (125 lines, 13:35)

## F3 | BUG-0271 | blocking | the form assertion could not fail for the case it claimed  (clock 13:42)

* measured by the verifier: the check was `re.search(r"für \d+ \w+ (bleiben|sind|werden|gehen)")`
  -- a four-verb list behind a DIGIT. Two mutations that put the round-2 defect straight back
  stayed GREEN: the singular as a main clause ("eine Lücke bleibt offen", which carries no digit at
  all) and the plural with a fifth verb ("%d Lücken stehen offen").
* change, `tools/test_light_kit.py`: the test extracts the card's SUBJECT (the text between the
  last `für` and the colon -- the last one, because one kind's own LABEL carries a `für`) and holds
  it against the shipped noun phrase for BOTH numbers, through the new `_card_subject` helper.
* WHY THE WORDING AND NOT A STRUCTURE, said where the helper stands: a structural reader would have
  to find a German finite verb, which needs a lexicon this suite does not have and must not invent.
  The sentence a non-developer signs IS the artefact BUG-0271 is about, so the test holds the
  sentence; a rewording is then a red test, which for a text the user signs is the right cost.
* red-first, BOTH mutations the verifier measured green:
  - singular as a main clause -> `FAILED tools/test_light_kit.py::test_a_list_bound_question_reads_in_the_right_numerus_and_names_the_same_subject_as_its_card`
    (`'eine Lücke bleibt offen' == 'eine Lücke, die offen bleibt'`)
  - plural with a fifth verb -> the same node FAILED (`'2 Lücken stehen offen'`)
  - reverted, green.
* EVD-0405 SUPERSEDES EVD-0402.

## F1 | BUG-0278 | each HALF of a correlative is an ordinary negation  (clock 13:44)

* measured: "Neither of the tests goes red after the rename" and "No fix ships; nor does a test go
  red" both GRANTED the cheap rung -- the sentence split at `;` hands `nor` its own clause.
* change, `team-kits/kernel/dispatch.py`: `neither`, `nor` and `weder` join `_CLAUSAL_DENIERS`.
  `noch` does NOT, and that asymmetry is measured rather than assumed: "noch ein Test wird rot"
  promises a SECOND test, so listing it would refuse a promise. The pair table stays, and its
  tripwire changed to what it can really check -- every OPENING half is a listed denier, and each
  pair carries one measured row for its closing half.
* the idiom stays refused ("neither here nor there the test goes red") -- the cheap side, named in
  the comment.
* red-first: the three words removed -> `FAILED ...::test_a_german_acceptance_line_is_read_like_its_english_twin`
  ("Neither of the tests goes red after the rename") AND `::test_every_listed_denial_word_is_the_reason_its_sentence_is_refused`
  ("an entry nothing holds: {'nor', 'weder', 'neither'}"); reverted, green.

## F2 | BUG-0278 | CLOSED, not just named  (clock 13:44)

* the verifier offered "close it or name the whole class"; it is CLOSED. The class is a noun phrase
  that carries a SECOND one -- German genitive, English `of`-postmodifier -- and the complement now
  runs on through it: a determiner does not end the complement when it is an unambiguous genitive
  form (`des`, `eines`, `dessen`, `deren`) or stands directly after `of`.
* all four measured rows are refusals now ("ohne die Hilfe eines Tests", "ohne den Nachweis eines
  Tests", "without the help of a test", "without the support of any regression test").
* THE RESIDUE IS NAMED WHERE THE RULE IS, dangerous direction first: the AMBIGUOUS German genitive
  articles (`der`, `einer`) are also nominative and dative, nothing here can tell which, so a
  denial phrased over one still ends its complement early.
* red-first: the postmodifier branch disabled -> `FAILED ...::test_a_german_acceptance_line_is_read_like_its_english_twin`
  ("Das Ergebnis wird ohne die Hilfe eines Tests rot"); reverted, green.
* measurement for F1 and F2 together: **41 rows through `dispatch._sentence_names_a_test`, 0
  wrong** -- 10 grants (both fronted forms, and "noch ein Test wird rot") and 31 refusals.
* EVD-0404 SUPERSEDES EVD-0401.

## F5 | the grep claim was wrong, and one hit was MY file  (clock 13:45)

* `tools/test_research_chain.py:286-288` stands in this item's `allowed_scope` and wrote a real
  `evidence` call without the pair while asserting `returncode == 0`. FIXED: the call carries
  `--run-command`/`--run-scope`, with the reason beside it.
* MEASURED AT THE SURFACE, because the suite cannot run on this tree: its fixture scaffolds a kit,
  and the installer refuses with "does not hash to the `content:` in its own VERSION" -- the
  unstamped-tree class, ten errors. So what is measured is what the call meets: the argument list
  BEFORE is refused by the shipped parser with rc 2, the list AFTER is accepted. The end-to-end run
  belongs to the merging item's stamped tree.
* THE CORRECTION to rework 2's grep claim, which said "the remaining hits are prose":
  - `tools/test_research_chain.py:286-288` -- MINE, missed, fixed here;
  - `tools/test_e2e.py:501-504` -- stream B's file (B3), the lead has told them;
  - `.claude/hooks/test_gates.py` -- TEN call sites, stream C's file (TSK-0143), and the S4 patch
    is not acceptable without them (see F4 below);
  - the rest really is prose, and `gate_test_scope.py:709` composes the flags through `%s` at run
    time, which is correct.
  The sentence "why no test saw it" was wrong too: a test DID see it, in the gate suite that
  `CLAUDE.md` starts separately and that runs in neither `pytest tools/` nor a kit run.

## F4 | S4 | not mine to write, carried into the patch file  (clock 13:45)

`.claude/hooks/test_gates.py`'s ten `evidence` call sites belong to TSK-0143. The S4 patch file now
says that the patch is NOT acceptable on its own and names the ten sites with the verifier's
measurement, so the two halves travel together:
`project_memory/staging/TSK-0141/s4-gate-commit-evidence-patch.md`.

## DEC question 1, rewritten so a non-developer can answer it (clock 13:47)

The verifier is right: the question asked the user to fix a vocabulary whose members are explained
nowhere, and one of the three words is not a size at all. Replaces question 1 above.

### Frage 1 (H155 / BUG-0237) -- Welche Wörter darf die Art eines Ziels haben?

Jedes Produktziel trägt ein Wort, das sagt, was für eine Art von Vorhaben es ist. Heute darf das
jedes beliebige Wort sein. Das Wort entscheidet mit, ob vor der Arbeit eine Architekturrunde
stattfindet -- und wer sich vertippt, bekommt eine Runde, die niemand schuldete.

Was die Wörter bedeuten, die dieses Projekt heute benutzt:

* **`small`** -- eine kleine, klar umrissene Änderung; sie überspringt die Architekturrunde.
* **`normal`** -- gewöhnliche Produktarbeit; sie bekommt die Architekturrunde.
* **`large`** -- ein großes Vorhaben mit mehreren Bausteinen; Architekturrunde in jedem Fall.
* **`technical_enabler`** -- Umbau unter der Haube, ohne sichtbares Ergebnis für den Nutzer; er
  überspringt die Architekturrunde, weil es nichts zu entwerfen gibt.
* (in den Tests kommen außerdem `feature`, `research` und `exploratory` vor -- Wörter, die sich
  jemand unterwegs ausgedacht hat und die heute niemand prüft.)

* **A -- feste Liste.** Sie sagen, welche dieser Wörter erlaubt sind; ein anderes Wort wird beim
  Anlegen eines Ziels abgelehnt. Kosten: jedes schon gespeicherte Ziel muss einmal auf ein erlaubtes
  Wort umgezogen werden (12 in diesem Projekt, unbekannt viele in Ihren anderen), und ein neues
  Wort braucht künftig Ihre Entscheidung.
* **B -- Liste ohne Zwang.** Die Liste steht da, ein fremdes Wort wird gemeldet, nicht abgelehnt.
  Kosten: nichts zieht um; der Tippfehler kostet weiterhin die Extrarunde, wird aber sichtbar.
* **C -- so lassen.** Kosten: bleibt wie heute; der Tippfehler bleibt unsichtbar.

## The batch lines after rework 3 (clock 2026-09-12 13:50)

Content unchanged -- no id entered or left the closed set -- rebuilt against a fresh store copy
(13:49) because EVD-0404/0405 changed which record the coverage reader picks up. All three:
**0 refused**.

    request-approval verification --batch BUG-0173 BUG-0193 BUG-0211 BUG-0266 BUG-0195 BUG-0278 BUG-0140 BUG-0236 BUG-0218 BUG-0225
    request-approval verification --batch BUG-0231 BUG-0226 BUG-0224 BUG-0163 BUG-0144 BUG-0281 BUG-0210 BUG-0213 BUG-0238 BUG-0271
    request-approval verification --batch BUG-0246 BUG-0032 BUG-0055 BUG-0190 BUG-0152 BUG-0150 BUG-0192

## RUNS of rework 3

| selection | result | duration |
|---|---|---|
| `tools/test_ladder.py -k "german_acceptance or listed_denial"` | 2 passed | 1.9s |
| `tools/test_ladder.py` | 50 passed | 65.4s |
| `tools/test_light_kit.py -k list_bound_question` | 1 passed | 1.7s |
| `tools/test_light_kit.py -k "not pilot_rig"` | 26 passed | 37.5s |
| `tools/test_approvals_dispatch.py -k "batch or exception_option or card_of_a_list or acceptance"` | 28 passed | 23.3s |
| `tools/test_research_chain.py` | 10 errors -- the unstamped-tree class (the fixture scaffolds a kit) | 59.8s |
| `python -m ruff check team-kits/kernel/ tools/` | All checks passed | - |

The `test_research_chain` errors and the one `test_light_kit` pilot-rig red are the same missing
kit stamp as before; the stamp belongs to the merging item, and the F5 fix was measured at the
parser instead (BEFORE rc 2, AFTER accepted).

## COUNTS after rework 3 -- unchanged

46 rows: **28 closed**, 1 blocked measurement (BUG-0242), **17** addressed to the user, of which
three are the DEC questions (H155 -- rewritten in this rework, H170, H171).

Seams for the user's shell: **S1** and **S4**; S4's patch file now carries the ten call sites in
`.claude/hooks/test_gates.py` (stream C) that its acceptance depends on. **S3** stays with the kit
stream; **S2** is closed.

Last clock reading of this protocol: 2026-09-12 13:50.
