# TSK-0152 -- implementer protocol

Base commit 5be585c, branch feat/harness-v2. Scratch: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0152/`.

## 2026-09-26T08:01 -- start

Read: TSK-0152 (whole), DEC-0116, DEC-0117, BUG-0305/0308/0069/0264/0139/0105/0161/0233,
staging/TSK-0151/{apply_user_patch.py,user-patch.md,gates-run-final.txt}.

## 2026-09-26T08:26 -- 1. DEC-0117 archive door (built)

PLAN / rejected way: the audit record could have lived in a ledger file of its own that
`generated/index.yaml` reads. Rejected: the index lists ACTIVE items only and showing the archive
there means walking it on every state write -- measured on this repo's store, `_iter_every_stored_item`
over 1248 files took 10.7 s, against 1.5 s for the active board. The record lives ON the archived
item (it travels with git and the item), and the HOLE LIST, whose reader already walks the whole
store (`holes.index_rows`), shows it in the Stand cell. NOT built: a line in `generated/index.yaml`
(archived items never appear there at all).

Built:
- `team-kits/kernel/archive_door.py` (`amend_test_ref`, `COMMAND = "amend-archived-test-ref"`,
  `TEST_REFERENCE_FIELDS = (HOLE_TEST_FIELD,)`). "Resolves" is asked of `holes.citation_resolution`
  (the kernel's one reader), "collectable" = `test_*.py` module + `test*` function.
- `backlog_types.TEST_REF_AMENDMENTS_FIELD` (optional on BUG); `state._ARCHIVE_DOOR_FIELDS` refused
  at capture and update (one writer).
- `kernel.cli`: the subcommand; after a hole item it regenerates the document's hole index
  (`holes.reindex`, the writer `migrate-holes --reindex` runs) where `docs/POST_V2_WISHLIST.md` exists.
- `holes.index_rows` returns a 5th element (`_amendment_note`), `render_index` appends it to Stand.
- tests: `tools/test_archive_door.py` (13 nodes).

Red-first (rig `_round-scratch/TSK-0152/rig_door/rig.py`, .git-less copy of kernel + test file,
result in `rig_door/result.txt`): M0 none 13 passed; M1 active item accepted -> red
`test_an_item_that_is_not_archived_is_refused`; M2 any field -> red `..._not_a_test_reference_is_refused`;
M3 -> red `test_an_old_node_the_item_does_not_name_is_refused`; M4 -> red
`test_an_old_node_that_still_resolves_is_refused`; M5a resolution check off -> 2 of 4 cases red,
M5b collectable check off -> the `helper_not_a_test` case red; M6 -> red
`test_a_correction_nobody_signs_is_refused`; M7 capture refusal off -> red
`test_the_audit_record_has_one_writer`; M8 note off -> red `test_the_hole_list_shows_the_correction`;
M9 status also changed -> red `test_the_door_corrects_one_reference_and_leaves_every_other_field_as_it_was`;
M10 no record -> 3 red.

Rehearsal on a COPY of the repo state (`_round-scratch/TSK-0152/rehearse.py`): both lines rc 0, the
hole document changes in exactly the two rows H138/H155 (Stand gets `; Testverweis korrigiert
2026-09-26 (1x)`), `approved_hash` of BUG-0237 untouched (regression_tests is not in
`HASHED_FIELDS["BUG"]` nor in the hole-exception manifest). The copy carried the live
`.kernel.lock` over and the first run met "kernel lock busy"; removed in the copy, not a door defect.

THE TWO LINES FOR THE LEAD (after the verifier's PASS; from the repo root):

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory amend-archived-test-ref BUG-0221 --old tools/test_design_conformance.py::test_a_record_is_written_even_when_the_checks_find_something_and_the_sighting_gate_still_opens --new tools/test_design_conformance.py::test_a_draft_with_conformance_findings_is_refused_and_an_undecided_one_is_not --reason "renamed in 18f9c24 (bug-null 3b) when BUG-0294 made the sighting gate refuse a draft with findings" --by harness-lead
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory amend-archived-test-ref BUG-0237 --old tools/test_approvals_dispatch.py::test_an_empty_origin_excuses_the_step_while_the_root_criteria_measure_it --new tools/test_approvals_dispatch.py::test_an_origin_that_names_no_criterion_excuses_no_architect_step --reason "replaced in 95df503 (TSK-0150) when BUG-0303/H218 closed the remainder the old test asserted" --by harness-lead
```
Each also rewrites the hole index of `docs/POST_V2_WISHLIST.md` (two rows), so
`test_gates.py::test_the_hole_index_in_the_document_is_the_one_the_items_generate` stays green.
NOT measured: whether gate 1 lets the lead's line through (a hook file cannot be started by hand here, H80).

## 2026-09-26T08:51 -- 2. BUG-0305 / H220 (built, kit gate x3)

PLAN / rejected ways: (a) "count the unknown stage as RUN only when its remaining words are
read-only" -- rejected, because the word after a prefix option may BE the program (`me` in
`sudo -u me cat`): the readings of `sudo -u me cat tools/ci.sh` and `env -u cat sponge run.sh` are
symmetric (one unclassified word, one read-only verb), so any rule that passes the first passes the
second, which writes run.sh. (b) ask the host's PATH whether a candidate word is a program --
rejected: the hook's PATH is not the shell's (on this host PowerShell's `bash` is the WSL
launcher), so a writer missing from the hook's PATH would read as "cannot start" = fail-open.
Built instead: the pattern `_compat.GIT_READER` already uses for git -- options whose value-taking
is KNOWN are stepped over (value included), every other option keeps the stage UNKNOWN
(fail-closed, as before). `gate_write_scope._PREFIX_OPTIONS` = {sudo -u (value), env -i (flag),
nice -n (value), exec -a (value), command -p (flag)} -- exactly the options of the BUG-0304/0305
lines; `_command_word_at` walks it; the prefix-word list is now its keys (one definition).
Remaining over-refusal (an option NOT in the table, e.g. `sudo -E cat x ; bash x`) now says
"this line may WRITE ... -E stands where a command word belongs ..." instead of "this line WRITES".
Docstrings of `_the_command_word_is_unknown` / the write-and-run rule corrected ("nothing on an
everyday line" removed, the cost stated with the measured line).

Tests (tools/test_hooks.py):
- `test_a_read_only_stage_behind_a_known_prefix_option_is_not_read_as_a_write` [3 kits] -- the
  three AC lines rc 0, the tee attack rc 2 with "this line WRITES run.sh", `sudo -E ...` rc 2 with
  "may WRITE" and without "this line WRITES". RED ON BASE: rig `rig_base.py h220-base` (all three
  kit gates restored to 5be585c) -> 3 failed.
- `test_every_known_prefix_option_is_needed_and_is_what_the_real_program_does` [one node per entry]
  -- NEEDED half: the entry taken out in-process -> the line is refused; TRUE half: the real program
  (`bash -c '<prefix> <opt> [value] "$(type -P printf)" ok'`). Rig `h220-flip` (every value-taking
  flipped) -> 4 failed, sudo skipped (no sudo on this host; on the ubuntu runner it runs).
- existing `test_a_prefix_words_own_option_does_not_hide_the_command_word_in_any_kit`,
  `test_the_write_and_run_rule_reads_the_effective_command_word_in_every_kit`,
  `test_a_line_that_writes_a_script_and_runs_it_is_refused_in_every_kit`,
  `test_every_evaluator_word_refuses_a_line_that_writes_what_it_evaluates` green (BUG-0304 lines
  stay refused); the everyday-twins docstring corrected.
- `docs/holes/H219.md`: a Nachtrag carrying the class (a read-only stage behind a prefix option
  whose value-taking the reader does not know + the same file run on the line), no line count.

## 2026-09-26T09:25 -- 3. BUG-0308 / H221 (built, kernel)

PLAN / rejected way: moving the task's top-level `lease_rung` to the provider that RAN the order --
rejected, no client marker is measured (`dispatch.PROVIDERS_KEY` comment says the same). Built: the
lease writes onto the task `lease_provider` (whose answer `lease_rung`/`lease_effort` are) and
`lease_by_provider` ({provider: {rung, effort}} from the lease's `by_provider`);
`report.lease_distribution` adds `counted_provider` and `by_provider` (rungs, efforts, runs to
hand-back per rung, per provider) and the line says "rungs and efforts counted as answered for
<provider>" plus a per-provider clause for every other provider; the session brief's task row
carries `lease_by_provider`. Readers of `lease_rung` grepped: `report._leased_orders`,
`report.lease_distribution`, `report.generate_session_brief` (task row), `dispatch.reflection_checkpoint`
line (d) (reads `lease_distribution`, so it inherits the provider clause), `tools/light_kit_pilot.py`
(a Claude-only pilot record -- left as it is, named). Bound stated rather than closed: which client
RAN the order stays unknown; the rollup counts what each provider was ANSWERED.
Test: `tools/test_ladder.py::test_the_lease_distribution_names_the_provider_whose_rung_it_counts_bug_0308`
(Codex-installed dev project, backend order after 3 failed runs, `dispatch` as a process, then
SUBMITTED). Red-first (rig_base.py): `h221-base` (dispatch.py + report.py at 5be585c) red;
`h221-no-task` (task keeps no per-provider answer) red; `h221-no-rollup` (rollup ignores it) red.
`tools/test_schemas.py` sample gained the two keys (its test asks the producer's key set).

## 2026-09-26T09:25 -- 4. BUG-0069 (CI run 36187576523, full log read by section)

Log: `gh run view 36187576523 --log` -> `_round-scratch/TSK-0152/ci-run.log` (847 lines, read at the
FAILURES sections: lines 288-320 ubuntu, 700-790 windows). Failures:
1. BOTH runners: `tools/test_repo_hygiene.py::test_every_artifact_ref_still_resolves_where_it_points`
   -- EVD refs to `staging/**/*.log`. MECHANISM: `.gitignore` `*.log` keeps evidence artifacts out of
   every commit. FIX: `.gitignore` `!project_memory/**/*.log`; new test
   `tools/test_repo_hygiene.py::test_no_artifact_ref_points_at_a_file_git_ignores_bug_0069`
   (asks `git check-ignore`, NUL-separated bytes -- a text pipe on Windows turned the list into CRLF
   and the first cut passed vacuously, measured). RED: measured in the repo before the .gitignore line
   (1 failed), green after; the rig copy is .git-less, so this one was not measured there.
   CONSEQUENCE FOR THE LEAD: 17 logs under project_memory/staging/ now show as untracked (`??`) and
   must go into the commit, or CI stays red. Two of them carry CRLF (TSK-0126/redfirst-dec0079.log,
   TSK-0142/run-ledger-gate.log, both named by EVD-0327..0330); once tracked, the working-tree
   line-ending check will list them -- `python tools/normalise_line_endings.py` repairs staging files
   (outside my scope: other items' staging).
2. windows: `tools/test_office_duties.py::test_the_register_reads_the_business_time_zone_and_names_one_it_cannot_resolve`
   -- ZoneInfoNotFoundError: Windows has no IANA database, `zoneinfo` then needs the `tzdata`
   package, and the office requirements (what the CI installs, and what a field machine installs)
   did not list it. FIX: `tzdata` in `team-kits/office-team/templates/repo/requirements-office.txt`;
   test `tools/test_office_duties.py::test_the_office_requirements_carry_the_time_zone_database_zoneinfo_reads_bug_0069`
   (AST: an office file imports zoneinfo -> requirements name tzdata). Red-first `h069-tz` red.
3. windows: `tools/test_radar_trigger.py::test_the_claim_rule_follows_the_record_per_watcher` --
   `os.path.relpath` across drives (checkout D:, tmp C:) in `tools/radar_routine.py`. FIX: one helper
   `_spelled(path)` (relative where a relative path exists, absolute across drives) for the three
   relpath sites; test `tools/test_radar_trigger.py::test_the_record_path_is_spelled_even_when_it_lies_on_another_drive_bug_0069`
   (Windows only -- elsewhere no drive exists, explicit skip). Red-first `h069-drive` red.
The bug closes only on the first green hosted run (the lead reads it after the push).

## 2026-09-26T09:25 -- 5. BUG-0264 / H182 (structural test built)

The user's patch of 2026-09-25 removed the four schedule sentences (grep `weekly|schedul` over
`.claude/hooks/*.py` finds only test prompts). The STRUCTURAL property exists and is the one the
bug's `limits` asserts: the exemption is decided by the frontmatter key alone.
Test: `.claude/hooks/test_gates.py::test_gate2_decides_the_exemption_on_the_frontmatter_key_whatever_the_prose_says`
-- two probe definitions the test writes: key + no prose -> spawn rc 0; the four measured schedule
claims in description and body + no key -> rc 2. No prose is read. Red-first (rig, mutating
`_harness.spawn_needs_an_item` in the copy): see below. AC-2 of BUG-0264 (a reader of prose whose
subject reaches the enforcement layer) is REPLACED by this test per DEC-0116, not built -- the lead
reconciles the AC text.
Red-first (rig_base.py, `_harness.spawn_needs_an_item` mutated in the copy): `h182-prose-exempts`
(a schedule claim in the text exempts) -> red; `h182-prose-required` (the key needs prose beside
it) -> red.

## 2026-09-26T09:58 -- 2b. BUG-0305 follow-up: the H30 cross table

The first cut derived the prefix-word list from `_PREFIX_OPTIONS` (`low in _PREFIX_OPTIONS`). A
probe run of the whole gate suite (by accident, see section 7) showed two NEW reds:
`test_a_hole_states_the_over_refusal_the_table_carries` ("H30 says 64 of 1449 ...; the table has 64
of 1183") and `test_every_cell_a_closed_hole_names_is_one_the_table_carries` -- the cross table
harvests the prefix words from the LITERALS of a pure-`continue` branch of the kits' walk
(`test_gates._skip_branches`), and a dict name carries none. Repaired by keeping the literal
prefix branch and walking the options in their own branch before it; `_PREFIX_OPTIONS` now holds
only prefixes that carry known options (the tripwire's NEEDED half fails for a key the walk does not
step over). Re-run: `-k "over_refusal_the_table or cell_a_closed_hole or kits_reader_steps_over or
exactly_where_the_shell"` 4 passed. BOUND, named: the two option branches are not pure-`continue`
branches, so the H30 cross table does not cross prefix OPTIONS with the directory verbs; the options
are held by the tripwire test instead.

## 2026-09-26T09:58 -- 6. User patch (H13, H151, H69 built as a patch; H47 a class question)

Chains measured on the CURRENT tree as gate-1 processes (probe `_round-scratch/TSK-0152/probe/
test_probe_holes.py`, session agent, result in `probe/probe_result.txt`):
- H47: `F=team-kits/kernel/state.py; echo x > $F` rc 0; `... > "$F"` rc 0;
  `F=project_memory/generated/index.yaml; echo x > $F` rc 0 (canonical state!).
- H13: `Write tools/bump_kit_version_extra.py` rc 0.
- H151: `Write tools/test_surface.json` rc 0; `echo {} > tools/test_surface.json` rc 0.
- H69: `echo poison > project_mem<CR>ory/generated/index.yaml` rc 0.

PLAN / rejected ways: H151 alone could be closed by reading gate 5's constant or by moving the file
under `.claude/` -- rejected: the first is an enumeration of one gate's data file, the second moves
the knob FR-0086 wants in the lead's reach to the user and needs a decision. One DERIVED rule closes
H13 and H151 together: the directory of every producer file is protected for the session agent,
asked LAST in `verdict` so every narrower refusal text stays as it is (the first idea put it beside
the producer check and would have turned `team-kits/kernel/state.py` from "kit content" into
"producer", breaking `test_gate1_protects_every_reader_its_own_answer_came_from`). H69: the kits'
rule moved from `_kernel` (a door `_harness` never passes) into `_compat` (the reader it already
borrows) as `EATEN_IN_FLIGHT` / `eaten_in_flight`; `_kernel` delegates; the patch adds one call in
`_harness.payload`. Kit files `_compat.py`, `_kernel.py` mirrored x3 (hash-identical).

Files: `project_memory/staging/TSK-0152/user-patch.md` + `apply_user_patch.py` (5 sites, all or
nothing, `--check`; the style of staging/TSK-0151). `--check` on this tree: 5 sites "would change".
Tests (`.claude/hooks/test_gates.py`, red before / green after, measured in a copy -- see below):
`test_gate1_refuses_the_lead_a_new_file_beside_the_stamper_bug_0105`,
`test_gate1_refuses_the_lead_gate5s_declaration_bug_0233` (its counter-end: a pytest selection under
tools/ stays rc 0), `test_gate1_refuses_a_character_the_shell_never_sees_bug_0161` [2 callers]
(counter-end: a CRLF line rc 0).

CLASS QUESTION H47 / BUG-0139 (DEC-0070 Regel 2, "die Auflösung"), fuer den Nutzer:

> Die Schutzregel dieses Repos (Gate 1) liest Befehlszeilen, versteht aber keine Variablen. Die
> Zeile `F=team-kits/kernel/state.py; echo x > $F` schreibt in eine geschützte Datei und wird
> durchgelassen; heute gemessen gilt das sogar für den Projektzustand
> (`F=project_memory/generated/index.yaml; echo x > $F`, für jeden Aufrufer). Die Team-Kits lösen
> solche Variablen seit TSK-0070 auf. Welche Richtung soll gelten?
> (a) Die Variablen-Auflösung der Kits wandert in den gemeinsamen Leser, den beide benutzen: jede
> künftige Kit-Korrektur heilt dieses Gate mit, aber jede Kit-Regel liest ab dann aufgelöste
> Variablen -- das kann ändern, was die Kits erlauben und ablehnen.
> (b) Nur dieses Gate baut die Auflösung nach: die Kits bleiben unberührt, aber es gibt dann zwei
> Fassungen derselben Regel, die auseinanderlaufen können.
> (c) Am einfachsten: das Ziel einer Umleitung (`> ...`) ist immer ein Pfad, also lehnt dieses Gate
> eine Umleitung ab, deren Ziel eine Variable enthält, statt sie aufzulösen -- sicher, trifft aber
> auch harmlose Zeilen wie `echo x > $LOG`.
> Empfehlung des Umsetzers: (c), weil es keine zweite Fassung der Kit-Regel baut und die Lücke an
> ihrer Wurzel (ein Pfad, den der Leser nicht kennt) schließt.
MECHANISM behind (c), read in the code and consistent with the rc 0 above: the same gate refuses
`team-kits/$k/...` ("a word this line writes could not be placed", met in this session) but lets
`$F` through, because `_harness._could_name_a_path` reads a word as a possible path only when it
carries a separator or stands where a program starts -- a redirect TARGET is neither. Not built,
per the order.

Patch measured in a COPY (rig_base.py, whole working tree without .git):
`patch-before` -> 4 failed (bug_0105, bug_0233, bug_0161 x2); `patch-after` (the shipped script run
inside the copy: `--check` 5 sites, apply 5 sites, apply AGAIN 0 sites -- idempotent) -> 4 passed.
The whole gate suite with the patch applied: see section 8.

## 2026-09-26T10:19 -- 7. Self-review defect, second stamp, and cost notes

SELF-REVIEW FOUND ONE DEFECT OF MY OWN after the first stamp (10:07): the "may WRITE" sentence was
chosen by `len(distinct options) == len(writers)`, so two fail-closed stages with the SAME option
(`sudo -E cat x ; sudo -E wc x ; bash x`) fell back to "this line WRITES" -- the false sentence
BUG-0305 is about. Fixed (`all(one in guessed for one in writers)`), the BUG-0305 test gained that
line and a counter-line with a real redirect write ("this line WRITES" stays). Red-first
`h220-count` (the first cut restored in all three kits) -> 3 failed; `h220-base` and `h220-flip`
re-run on the final tables: 3 failed / 4 failed + sudo skipped.
The first full run (started 10:07) was stopped before it finished, the kits RE-STAMPED at 10:19:
dev/office/research 2026.09.26-1 -> **2026.09.26-2**. Two stamps instead of the order's one -- the
cost of a defect found after the first; named rather than hidden.
`git add -N` (intent-to-add, no commit) for the two new files `team-kits/kernel/archive_door.py`
and `tools/test_archive_door.py`: `validate.py` refused an untracked file that goes into a kit hash
(precedent TSK-0113). After it: ruff clean, `validate.py: all structural checks passed`.
COST RULE BROKEN TWICE, named: (1) a probe file that did `from test_gates import *` ran the WHOLE
gate suite (33 min, 09:14-09:47) instead of four probes; (2) between ~09:47 and ~10:00 two pytest
processes overlapped (the H30 gate selection beside the re-written probe and the patch rig). Their
results are recorded as they came; none of them was a verdict another run depended on.
NOT MINE, seen in `git status` during the round: `docs/PLAN_ANBIETERFREI.md`,
`project_memory/staging/generation-5/next-session-prompt.md`,
`project_memory/staging/generation-6-streams.md` -- modified by someone else while I worked.

## 2026-09-26T12:16 -- 8. Finish (fresh builder): the three reds of full-run.txt

The first builder stopped (usage limit) after `full-run.txt` (11:39): 3 failed / 5184 passed.
Verified at 12:15: `bump_kit_version.py --check` unchanged at 2026.09.26-2 for all three kits;
the three nodes in `full-run.txt` are all the archive door missing from existing contracts:
`tools/test_approvals_dispatch.py::test_no_direct_status_write_can_produce_a_status_an_approval_commits`,
`tools/test_board.py::test_no_kernel_writer_of_a_rendered_file_leaves_the_board_behind`,
`tools/test_hooks.py::test_every_span_that_presents_the_command_surface_names_all_of_it`.

PLAN / rejected way for (1): widening the test's reader so a whitelist guard (`if field not in
<tuple without "status">: raise`) counts as refusing the key -- rejected: a new guard shape in the
reader needs its own sample set and a tie between the tested name and the written key, all for a
door that opens ONE field. Chosen: the door writes through a module constant the reader resolves
to one string (`archive_door.TEST_REFERENCE_FIELD = HOLE_TEST_FIELD`, was the tuple
`TEST_REFERENCE_FIELDS`); the refusal is `field != TEST_REFERENCE_FIELD`. What that does NOT cover:
a second test-reference field -- the key is computed again and the reader asks for a guard (said
beside the constant).

12:16 RED BEFORE (one pytest, both nodes): `test_no_direct_status_write_can_produce_a_status_an_approval_commits`
FAILED, `test_no_kernel_writer_of_a_rendered_file_leaves_the_board_behind` FAILED (2 failed).
Fixes:
- (1) `team-kits/kernel/archive_door.py` as above; `kernel/cli.py` `--field` default follows.
  The kernel's status-write reader (`_status_writes` over the package constants) now reports NO
  write in `archive_door.py` at all (probe `_round-scratch/TSK-0152/finish/probe_writes.py`).
- (2) `tools/test_board.py::_WRITERS_THE_BOARD_DOES_NOT_RENDER` + `("archive_door.py",
  "amend_test_ref")` with its reason (index = active items; board = archived COUNT per type), and
  that reason is a test: `tools/test_archive_door.py::test_the_door_leaves_the_board_nothing_to_regenerate`
  (counts and file set unchanged by the door). Red-first rig `finish/rig.py` (.git-less copy,
  binary I/O, refuses a foreign cwd): door also writes a 2027 copy -> exactly that node red,
  13 others green.
- (3) the surface lists: `README.md` and the three `constitution/AGENTS.md` name
  `amend-archived-test-ref` after `archive`.
12:17 GREEN AFTER: both nodes passed; 12:18 (3) passed.

Knock-on of (3), measured and closed: `validate.py` refused the office/research lead package
(+27 B over the record) -> `tools/record_lead_package_sizes.py --write --note ...` (3 records,
journal in `docs/reviews/phase0-disposition.md`); `test_shortening_net::test_no_section_of_a_pinned_instruction_file_disappears_unnoticed`
red (section 0 CHANGED x3) -> `tools/pin_constitution_sections.py --write --note ...` -> 36 passed.

STAMP (one, this builder): 12:20 `bump_kit_version.py` dev/office/research 2026.09.26-2 -> **2026.09.26-3**;
`--check` after the record/pin writes: unchanged. ruff clean, `validate.py: all structural checks passed`.

Reading suites, each its own selection (DEC-0080 rule 2; readers found by grep of `archive_door`,
`lead_package`, the cli surface):
12:19 `tools/test_archive_door.py` 14 passed | 12:19 `test_approvals_dispatch.py -k "status_write or
direct_status or reader_that_finds or refuses_the_key"` 2 passed | 12:19 `tools/test_board.py`
77 passed | 12:19 `test_hooks.py -k "surface or subcommand or command_span or constitution"` 9 passed
| 12:20 `tools/test_role_contracts.py` 37 passed | 12:20 `test_context_budget + test_shortening_net
+ test_review_procedure` 1 failed (the pin above) -> 12:22 `test_shortening_net.py` 36 passed |
12:23 `tools/test_gaplog.py` 10 passed | `test_hooks_v2 + test_repo_hygiene -k "lead_package or
package_size or journal or disposition or pins"` 2 passed.

12:24 FULL RUN started in the background: `DELIVERY_RUN=TSK-0152 python -B -m pytest tools/ -q -p no:cacheprovider`
-> `project_memory/staging/TSK-0152/full-run-final.txt`.
13:53 FULL RUN finished: **5188 passed, 15 skipped, 1 warning in 5239.16s (1:27:19), exit 0**
(5184 + the 3 former reds + the new door/board node). The warning is the known CRLF note on
`project_memory/.audit/hook_events.jsonl` (test_repo_hygiene), not a failure.

## 2026-09-26T14:34 -- 9. Gate suite: as the tree stands, and in a copy with the user patch applied

13:54-14:33 `DELIVERY_RUN=TSK-0152 python -B -m pytest .claude/hooks/test_gates.py -q -p no:cacheprovider -rfE`
-> `staging/TSK-0152/gates-run-final.txt`: **5 failed, 555 passed (31:52)**. Every red explained:
- `test_gate1_refuses_the_lead_a_new_file_beside_the_stamper_bug_0105`,
  `test_gate1_refuses_the_lead_gate5s_declaration_bug_0233`,
  `test_gate1_refuses_a_character_the_shell_never_sees_bug_0161[caller0]` / `[caller1]` --
  PATCH-PENDING (section 6): they turn green only when the user applies `user-patch.md`.
- `test_every_test_a_hole_names_is_one_that_exists` -- H138 and H155 name the renamed tests; closes
  when the lead runs the two `amend-archived-test-ref` lines of section 1 after the verifier's PASS.

14:34-15:24 GATE SUITE IN A COPY WITH THE PATCH (`rig_base.py patch-after-full`: .git-less copy of
the tree, the shipped script `--check` / apply / apply again = 5 / 5 / 0 sites): **2 failed, 558
passed (36:24)**. The four patch-pending reds DISAPPEARED; H138/H155 stayed (door lines pending, as
expected); and ONE NEW RED: `test_the_measurement_watch_list_is_the_area_the_gate_protects` --
"protected but not watched: .../project/tools/test_surface.json". A DEFECT OF THE PATCH, not of the
copy: site 1 protected the producers' directories inside `verdict`, while `_sandbox.protected_files`
walks the AREAS = the slots of `ProtectedArea`, so the watch list missed what the new rule protects.
FIX (patch only, `.claude/hooks/` is the user's): site 1 split into 1a (slot `producer_directories`),
1b (filled in `__init__`, root excepted), 1c (`verdict` loops over the slot); `user-patch.md`
section 1 rewritten. 15:25-15:29 `rig_base.py patch-after-sel` (patch tests + watch list): --check 7,
apply 7, again 0; **6 passed**. `--check` on the real tree: 7 sites would change.
15:38-16:19 GATE SUITE IN A COPY WITH THE FINAL PATCH (7 sites; --check 7 / apply 7 / again 0):
**1 failed, 559 passed (41:06)** -- the only red is `test_every_test_a_hole_names_is_one_that_exists`
(H138/H155, the door lines). So with the patch the four patch-pending reds disappear and nothing new
turns red; the tree's gate run (5 red) minus the patch-pending four = that one.
Cost named: the patched gate suite ran twice (the order said once) because the first run found the
patch's own defect.

16:20-16:27 EVIDENCE through the kernel, each on its own selection run with the log beside it:
- EVD-0479 BUG-0305 (`evd-bug-0305.log`: 7 passed, 1 skipped -- sudo absent here)
- EVD-0480 BUG-0308 (`evd-bug-0308.log`: 1 passed)
- EVD-0481 BUG-0264 (`evd-bug-0264.log`: 1 passed)
- EVD-0482 BUG-0069 LOCAL half (`evd-bug-0069.log`: 6 passed); the bug closes on the first green
  HOSTED run, which the summary says.
- EVD-0483 the full run, `--run-scope full`, related TSK-0152 only (DEC-0100 (3)).
No EVD for BUG-0105/0233/0161 (patch-pending) nor BUG-0139 (class question H47, section 6).
After the full run nothing under team-kits/ or tools/ changed (only this staging directory: the
patch script/doc and the logs); `bump_kit_version.py --check` unchanged at 2026.09.26-3.
No commit, no push, no mint, no transition.

## 2026-09-26T17:30 -- Rework 1 (fresh builder): verify-round-1 F2, F1, F3

Read: TSK-0152, verify-round-1.md (whole, 127 lines), DEC-0117, this protocol sections 1, 8, 9.
Scratch: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0152/rework1/`.

PLAN / rejected way (F2): the verifier's minimal fix (refuse when `normpath` starts with `..` or the
path is absolute) -- rejected: a list of spellings; it lets the staging throwaway through and says
nothing about `tools/../tools/...`. Also rejected: `tools/test_surface.json` as the boundary -- it is
this repo's gate-5 declaration and does not ship into a kit project, so the kernel would answer
differently per repo. Chosen DEFINITION (`archive_door._why_not_a_test_module`): the new node's module
is one of `holes.test_modules_under(repo)` (the kernel's one answer to "which files would a runner
collect here", repo-relative, forward slashes) AND does not lie in the state directory (`state.root`,
derived, not the string `project_memory`). The branches only NAME the reason (outside / state
directory / respell as ...). `_node` no longer removes inner whitespace (trim only), so a path with a
space is judged as spelled. `_collectable` now asks the function half only. Cost: the walk over this
repo measured 0.05 s (50 modules).

F1: `test_the_audit_record_has_one_writer` also calls `state.update_item` on an active BUG with the
audit field (and asserts the file does not carry it). F3 (the cheaper honest way): the code already
counts efforts per provider; `test_ladder.py::..._bug_0308` now asserts
`by_provider.codex.efforts == {<the codex answer's effort>: 1}`. NOT closed, named: there is no
per-provider "runs to hand-back per EFFORT" (only per rung); the report.py docstring says exactly
"rungs, efforts and runs to hand-back per rung", so it claims nothing more.

17:31-17:34 RED-FIRST (`rework1/rig.py`: .git-less byte copy of team-kits/ + tools/ + ladder.yaml,
refuses a foreign cwd, binary I/O, one mutation per run; `rework1/result.txt`):
M0 none -> 22 passed | M1 door without the checkout rule -> 6 red (all six shapes of
`test_a_new_node_outside_the_checkouts_test_modules_is_refused`: climbs, absolute_outside,
absolute_outside_with_a_space, state_directory, absolute_inside, detour) | M2 state directory allowed
-> red `[state_directory-...]` only | M3 `_node` strips every space again -> red
`test_a_new_node_whose_path_carries_a_space_is_judged_as_spelled` | M4 the verifier's F1 mutation
(state.py `audited = []`) -> red `test_the_audit_record_has_one_writer` | M5 the verifier's F3
mutation (by_provider counts rungs only) -> red `test_ladder.py::..._bug_0308`.

17:35 `kernel/cli.py` `--new` help names the rule (relative to the checkout root, outside the state
directory). Probe on the REAL tree (read-only, `rework1/probe_lead_lines.py`): both new nodes of the
lead's two lines in section 1 pass `_why_not_a_test_module` (None) and resolve -- the lines stand
unchanged.
17:36 STAMP (one, this rework): dev/office/research 2026.09.26-3 -> **2026.09.26-4**; ruff "All checks
passed!"; `validate.py: all structural checks passed`.

Reading suites, each its own selection (DEC-0080 rule 2; readers by grep of `archive_door` /
`amend_test_ref` / `amend-archived-test-ref` and of `lease_distribution`; log `rework1/suites.log`):
17:36 `test_archive_door.py` 21 passed | 17:36-17:39 `test_ladder.py` 67 passed | 17:39
`test_report.py` 141 passed | 17:40 `test_schemas.py` 30 passed | 17:40 `test_board.py` 77 passed |
17:41 `test_state.py -k "archive or door or amend or audit"` 13 passed | 17:41 `test_migrate.py -k
"archive or door or amend"` 16 passed | 17:42 `test_migrate_holes.py` 14 passed | 17:42
`test_approvals_dispatch.py -k "status_write or direct_status or reader_that_finds or refuses_the_key"`
2 passed | 17:42 `test_hooks.py -k "surface or subcommand or command_span or constitution"` 9 passed |
17:43 `.claude/hooks/test_gates.py -k "names_is_one_that_exists or hole_index_in_the_document or
every_check_this_apparatus"` 2 passed, 1 failed = `test_every_test_a_hole_names_is_one_that_exists`
(H138/H155, the lead's door lines pending -- as in section 9, nothing new).

17:47 THE ORDERED FULL RUN WAS REFUSED BY GATE 5 (rc 2): "TSK-0152 already has a PASSING full run on
record (EVD-0483, `run_scope: full`), so this would be the second one of the same round" (DEC-0063
(4) reading of DEC-0050). Not bypassed. Its first remedy taken instead: the suites that READ what
changed since EVD-0483, each IN FULL (the ones above that ran as `-k` selections re-run whole):
test_state, test_migrate, test_approvals_dispatch, test_hooks (cli surface), test_hooks_v2 +
test_kitupdate (VERSION readers). The second remedy (a full run recorded against a NEW item) needs an
item this builder may not capture -- the lead's call. `full-run-rework1.txt` therefore does not exist.

Full reading suites (`rework1/suites_full.log`): 17:47 `test_state.py` 67 passed | 17:47-17:52
`test_migrate.py` 146 passed | 17:52-17:54 `test_approvals_dispatch.py` 236 passed | 17:54-18:05
`test_kitupdate.py` 87 passed, 1 skipped | 18:05-18:23 `test_hooks_v2.py` 2171 passed | 18:23-18:51
`test_hooks.py` 1087 passed, 14 skipped. No red. NOT run: the remaining ~15 suites that invoke
`kernel.cli` (the cli change is one help string; none of them reads help text) -- the whole surface
is the lead's call against a new item (gate 5, above).
EVD: none new. The nodes of BUG-0305/0308/0264 did not change (BUG-0308's node gained one assertion,
same node id); EVD-0479/0480/0481 stand. No commit, no push, no mint, no transition; the door was not
applied to H138/H155.

## Rework 2 (fresh builder, narrow: F4 build, F5 capture) -- 2026-09-26

Read: verify-round-2.md whole (84 lines), `archive_door.py` whole, `holes.py:185-229`,
`test_archive_door.py:1-205`, this file's tail and lines 45-56.
Rejected way: changing `holes.test_modules_under` (`os.walk` not entering junctions) -- that walk has
other readers (`citation_resolution` for a bare name, the hole migration), would widen the round into
holes.py, and still would not cover a FILE symlink, which the walk lists by name; the door comparing
RESOLVED paths covers both and touches only the door.

19:15:40 start. 19:16:24 red-first rig `_round-scratch/TSK-0152/rework2/rig.py` (refuses a foreign
cwd, copies binary): the three new link shapes against the abspath door -> `3 failed, 6 passed` (rc 0,
item written: `junction_out`, `junction_to_state`, `symlink_file_out`).
19:17 F4 fix: `archive_door._lies_under` compares `os.path.realpath` of node and both roots; docstrings
of `_lies_under` and `_why_not_a_test_module` now say links are judged where they resolve. Copy with the
fix: `24 passed` (file symlink NOT skipped on this host). 19:17:10 mutation realpath -> abspath in the
copy: `3 failed, 21 passed` (the three link shapes), copy reset. Junction via `mklink /J` in tmp_path,
no admin; the symlink shape skips with a stated reason where the host refuses it.
Lead lines H138/H155 (read-only, `rework2/leadlines.py`): both modules `_why_not_a_test_module` =
None, `citation_resolution == [node]`, collectable.
19:18:14 F5 captured through the kernel: BUG-0312 = H222 (low, `limits` in German), then
`migrate-holes --reindex` (212 holes; one row added to docs/POST_V2_WISHLIST.md). The door docstring
names the remainder (BUG-0312) next to the throwaway sentence. Not built.
Stamp once: all three kits 2026.09.26-5; ruff "All checks passed!"; validate.py passed.
19:18:57-19:19:19 selections: `test_archive_door.py` 24 passed | `test_board.py -k no_kernel_writer`
1 passed (writer map names archive_door) | `test_approvals_dispatch.py -k no_direct_status_write`
1 passed (named in the door's module comment) | `test_gates.py -k "hole_index or a_hole_names or
wishlist"` 1 passed, 1 failed = `test_every_test_a_hole_names_is_one_that_exists`, H138/H155 only
(the lead's door lines pending, as before; H222 names no test). No full run.
EVD: none. No commit, no push, no mint, no transition; door not applied to H138/H155.
