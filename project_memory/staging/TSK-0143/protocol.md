# TSK-0143 -- stream C (tools/ + this repo's own gate tests), PR-0012 "Bug-Null", order 3b

Base: `feat/harness-v2`, commit 10a5127, shared working tree with stream A (kernel) and stream B
(kits). Scratch: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0143/` (rig `rig.py` +
`mutations.py`, `.git`-less copy in `tree/`; the rig refuses to run outside its own directory and
reads/writes binary -- the two generation-3 merge rules).

Started 2026-09-12 09:50:52 (clock read).

## Where this message and the item differ -- the item wins

The spawn message says list (i) is `staging/TSK-0140/h182-harness-patch.md` **extended** and list
(iii) the header of `staging/TSK-0140/order-3b-candidates.md` **counted from its rows**. The item's
`forbidden_scope` is `project_memory/**` with the single exception
`project_memory/staging/TSK-0143/`, so neither TSK-0140 file is writable by me. Both lists are
therefore produced as NEW files under `staging/TSK-0143/` and the lead carries them over:

* list (i)  -> `project_memory/staging/TSK-0143/h182-harness-patch-EXTENDED.md`
* list (ii) -> `project_memory/staging/TSK-0143/limits-update-lines.md`
* list (iii)-> `project_memory/staging/TSK-0143/candidates-header-recount.md`

## Rows

### H161 / BUG-0243 -- closed

| field | value |
|---|---|
| class | INSTR |
| mechanism | `test_gate1_answers_before_its_registration_however_long_the_line_takes_to_read` built its command line with `_a_line_too_long_to_read_in(...)` INSIDE the span it holds against the registered deadline; the sizing helper reads the clock itself (1500 reader invocations on the gate-3 twin, 0.03-0.04 s here), so work no gate process does was charged to the gate |
| change | `.claude/hooks/test_gates.py:5700` -- the payload is built before `started = time.monotonic()`, the same shape the gate-3 twin carries since BUG-0033; plus the new reader `_spans_that_pay_for_a_clock_reading` / `_touches_the_clock` / `_measured_spans_in` and the test below (`.claude/hooks/test_gates.py:5723-5860`) |
| red-first | rig `mutate bug_0243` (the sizing call moved back inside the span), arbiter `python rig.py run .claude/hooks/test_gates.py -q -k no_timed_span_here` -> **1 failed** in 2.08 s, message `line 5705: the span opened at line 5704 calls \`_a_line_too_long_to_read_in\`, which reads the clock itself`; after `rig.py restore` the same selection is green |
| naming test | `.claude/hooks/test_gates.py::test_no_timed_span_here_pays_for_a_helper_that_reads_the_clock_itself` (docstring first paragraph names BUG-0243 and H161) |
| suites run | `python -B -m pytest .claude/hooks/test_gates.py -q -k "no_timed_span_here or prose_is_one_that_exists"` -> 2 passed, **1.07 s** |
| EVD | see the evidence section at the end |

Note on the form: the guard is a DEFINITION, not a list of clock functions -- a helper that reaches
into the `time` module at all is one whose cost the clock decides, and the span is found by its
shape (a name bound to a clock reading, later subtracted from a second reading in the same block),
so a test that starts timing something tomorrow is read without being added anywhere.

### H45 / BUG-0137 -- closed (both limits)

| field | value |
|---|---|
| class | INSTR |
| mechanism (a) | the session guard `the_repo_is_not_a_sandbox` built its watch list by handing an EMPTY line (`:`) to an arbitrated shell -- the helper writes the protected file itself, so the shell did nothing -- and therefore made the WHOLE suite depend on this host carrying a shell that reads this filesystem back (verifier TSK-0063, PATH without Git: rc 1, four ERRORs, all four the registration checks that read `.claude/settings.json` and nothing else) |
| mechanism (b) | `_can_arbitrate` was covered by no test that could go red: the verifier restored the pre-TSK-0063 form in a clone and the eight tests around it stayed green in 19:51 |
| change (a) | `.claude/hooks/test_gates.py:126-148` -- new `_a_sandbox_as_a_line_leaves_it`, both sandbox files made in Python; the fixture calls it |
| change (b) | `.claude/hooks/test_gates.py:4085-4135` -- new `_runs_a_line` + the test below |
| red-first (a) | `mutate bug_0137a` (watch list built by running `:` through an arbitrated shell), arbiter `rig.py run .claude/hooks/test_gates.py -q -k session_guards_watch_list` -> **1 failed** (`no shell on this host reads back a file this process writes ([])`) -- the test empties `_posix_shells`, which is the host the verifier measured |
| red-first (b) | `mutate bug_0137` (the pre-TSK-0063 form: only the relative write decides), arbiter `-k arbiter_refuses_a_shell` -> **1 failed**: `C:\WINDOWS\system32\bash.exe ... is accepted as this suite's arbiter`. The mutant also MEASURES the mechanism: the WSL launcher really performs the relative write through its translated cwd |
| naming tests | `.claude/hooks/test_gates.py::test_the_session_guards_watch_list_is_built_without_a_shell` (a), `::test_the_arbiter_refuses_a_shell_that_runs_every_line_on_another_filesystem` (b) -- both name BUG-0137 in the docstring's first paragraph |
| suites run | `-k "session_guards_watch_list or arbiter_refuses_a_shell or arbiter_is_a_shell"` -> 3 passed, **3.85 s** |

The subject of (b) is a REAL shell of this host (`C:\WINDOWS\system32\bash.exe`, the WSL launcher),
not a stand-in; a host without one skips with that sentence.

### H41 / BUG-0133 -- closed (all four limits)

| field | value |
|---|---|
| class | INSTR |
| change | `.claude/hooks/test_gates.py` -- new `_spans` (c), `_glued` (b), `_points_into_another_file` + `_NODE_IN_ANOTHER_FILE` + `_tests_declared_in` (d), `_decoration_of` + `_shapes_the_table_carries` (a), and `test_the_pointer_reader_answers_for_every_shape_a_statement_here_can_carry` |
| red-first (a) | `mutate bug_0133a` (the `plainly` spelling deleted from `SPELLINGS_OF_A_POINTER`) -> **1 failed**, four files listed writing the shape `'%s'` the table no longer declares |
| red-first (b) | `mutate bug_0133b` (closing up at every whitespace again) -> **1 failed**, prose glued into `test_a_gate_that_cannot_decide_refusesandthensomemorewords` and reported |
| red-first (c) | `mutate bug_0133c` (single left-to-right pairing) -> **1 failed**, the pointer behind the stray backtick comes back as `set()` |
| red-first (d) | `mutate bug_0133d` (a span carrying a dot is skipped) -> **1 failed**, `[] == [('tools/test_approvals_dispatch.py', 'test_a_batch_approval_authorises_only_the_bugs_it_lists')]` |
| naming test | `.claude/hooks/test_gates.py::test_the_pointer_reader_answers_for_every_shape_a_statement_here_can_carry` (names BUG-0133 / H41 in the first paragraph) |
| suites run | `-k "pointer_reader_answers or prose_is_one_that_exists"` -> 2 passed, **2.90 s** |

MEASURED, and it corrected a claim I had written: (d)'s sweep is NOT empty in this directory. The
first green run found `gate_test_scope.py` pointing at two nodes of `.claude/hooks/test_gates.py`,
and my first reader ATE the leading dot of the path (`_undecorated` strips a character that cannot
stand in an identifier, and `.` is one), so both were reported as unresolvable. The reader now
searches the glued span instead of trimming it; the two pointers resolve and are judged by the
sweep rather than by hand. The docstring says that, not the "empty corpus" sentence it had first.

### H206 / BUG-0290 -- closed

| field | value |
|---|---|
| class | DESIGN (re-filed, the exception was never clicked) |
| mechanism | two kernel guards presuppose an installed kit, which this repo deliberately has none of: a bare transition into a lease-bearing status is refused (`dispatch.assert_lease_backed_transition_locked`, DEC-0038/BUG-0010), and `BUG TRIAGED->APPROVED` is bound to an approval in force, minted by the kits' hook on the answer event -- which this repo registered nowhere until TSK-0098 |
| change | `.claude/hooks/test_gates.py` -- new `_reachable_without` + `test_the_end_states_this_repo_reaches_are_measured_against_the_kernel`; nothing else changed, because the two halves are now a MEASUREMENT rather than an open question: the approval half is wired, the lease half is DEC-0041 |
| red-first (approval) | `mutate bug_0290_approval` (the whole `PostToolUse` registration removed from `.claude/settings.json` -- the pre-TSK-0098 state) -> **1 failed**: `approval_mint_is_wired(<tree>)` False |
| red-first (lease) | `mutate bug_0290_lease` (`team-kits/kernel/dispatch.py`, the guard returns for every status) -> **1 failed**: `DID NOT RAISE DispatchError`. NOTE: the mutation is applied in the rig COPY only; `team-kits/**` is untouched in the repo |
| naming test | `.claude/hooks/test_gates.py::test_the_end_states_this_repo_reaches_are_measured_against_the_kernel` (first paragraph names BUG-0290 / H206) |
| suites run | `-k end_states_this_repo_reaches` -> 1 passed, **1.86 s** |

The reachability is a WALK over `backlog_types.AUTOMATA[...].allowed` with the edges into
`dispatch.LEASE_BEARING_STATUSES` closed, not a list of states: TSK reaches `CANCELLED` and neither
`DONE` nor `VALIDATED` here (which is how every generation of this project has been closed), BUG
reaches all four of its terminals. The same walk with nothing closed reaches `DONE`, so the closure
is about the lease and not about an automaton that leads nowhere.

### H207 / BUG-0291 -- DOWNGRADE, measured; one site handed to the user's patch

| field | value |
|---|---|
| why unclosable HERE | the widened tripwire is buildable and I measured what it would report (probe `_round-scratch/TSK-0143/probe_contracts.py`, reader = the shipped `_harness.resolve_references` + the kernel's contract types, statement = one paragraph for prose / one string value for JSON): **role definitions 0, `CLAUDE.md` 0, `docs/**.md` 4, the registration 1**. The registration's site is `.claude/settings.json:2` -- "The PreToolUse gates below are the replacement SR-0006 specifies", a live citation of the contract SR-0009 replaced. That file is in this item's `forbidden_scope` for EVERY stream of this round, so shipping the widened tripwire would deliver a RED test that no role of this round may make green |
| bound | the four `docs/` sites are historical mentions in hole and review entries (`docs/holes/H40.md`, `docs/holes/H78.md`, `docs/reviews/2026-08-05-tsk0013-measurements.md`, `docs/reviews/2026-08-13-tsk0055-closure-round.md`); the one live citation stands in the file the PROVIDER reads, and it grants nothing -- it names the wrong contract, it does not change a gate's verdict. The narrow second limit of the same tripwire (a citation assembled at RUNTIME out of parts) is unmeasured and stays open |
| plain German | Ein Satz in der Registrierungsdatei nennt einen abgeloesten Vertrag als geltenden; die Datei darf in dieser Runde niemand aendern, darum liegt der Ein-Wort-Fix im Patch fuer den Nutzer, und der Draht, der so etwas kuenftig meldet, wird erst danach scharf geschaltet. |
| handed to | the user's patch file, site 6 (`h182-harness-patch-EXTENDED.md`) |

I deliberately did NOT edit the four `docs/` paragraphs: without the tripwire no test goes red
without that edit, and unmeasured prose churn in a tree three streams share is exactly what this
repo's rules forbid.

### H191 / BUG-0275 -- closed

| field | value |
|---|---|
| class | INSTR |
| mechanism | `tools/test_review_procedure.py::_states_the_scaling_rule`'s lead-in branch wanted the effort word in the bold lead-in and a rung ANYWHERE in the block (a 1424-character bullet), while its own docstring said "both axes in one breath". Moving the bare word `effort` into the lead-in and deleting the effort RULE kept a constitution qualifying |
| change | `tools/test_review_procedure.py:1317-1340` -- the branch reads SPANS (the lead-in, then each sentence) and asks for both axes in whichever span it reads; the docstring now says what the code builds |
| red-first | `mutate bug_0275` (the wide lead-in branch restored), arbiter `rig.py run tools/test_review_procedure.py -q -k ladder_reader_wants_both_axes` -> **1 failed**: the unit with the axes a whole sentence apart came back True |
| naming test | `tools/test_review_procedure.py::test_the_ladder_reader_wants_both_axes_in_the_same_breath` |
| suites run | `tools/test_review_procedure.py -q -k "ladder_reader_wants_both_axes or no_lead_skill_keeps_its_own_copy"` -> 2 passed, **1.53 s**. AC-1's other half holds: the shipped constitutions still qualify with exactly one paragraph each, which is what the second node asserts |

### BUG-0008 -- closed (AC-3; AC-1 and AC-2 were already built)

| field | value |
|---|---|
| mechanism | a PowerShell module cache wrote itself into the repo root because a subagent ran with `HOME` pointing here. AC-1 (ignored and untracked) and AC-2 (the rule carries its reason) are already held by `tools/test_repo_hygiene.py::test_git_tracks_no_ignored_file_outside_canonical_state`. AC-3 -- "whether OTHER tools write into this repo is MEASURED, not assumed" -- had no reader at all |
| change | `tools/test_repo_hygiene.py` -- new `_unaccounted_top_level_entries` and `_write_line`, plus the test below |
| measurement | the root of this checkout today: every untracked top-level entry is ignored WITH a rule (`.pytest_cache`, `.ruff_cache`, `.vscode`, `Microsoft`); nothing unaccounted for |
| red-first | `mutate bug_0008` (the sweep stops seeing a whole untracked DIRECTORY, the shape the cache arrived in) -> **1 failed**, `[] == ['ToolCache/']`. NOTE: the rig tree was given an INDEX for this row (`git init` + `git add -A` inside the copy), because a git-based reader SKIPS in a tree without one and a skipping test measures nothing. The copy has no remote and no history of this repo |
| naming test | `tools/test_repo_hygiene.py::test_no_tool_trace_lies_unaccounted_for_in_the_repo_root` |
| suites run | `tools/test_repo_hygiene.py -q -k "no_tool_trace_lies_unaccounted or tracks_no_ignored_file or known_out_of_scope_trace"` -> 3 passed, **2.40 s** |

### H190 / BUG-0274 -- closed

| field | value |
|---|---|
| class | ENUM |
| mechanism | `cloud_option.named_as` (the names of the REJECTED cloud routine) was a list with no tripwire at either end, and the shipped `radar/README.md` described the same option in two words the list did not carry -- so a sentence promoting it under those words passed the claim reader (the verifier's v04/v05: GREEN, 9 passed) |
| change | `tools/radar_routine.py` (`named_as` now five names, the comment says what measures both ends), `radar/README.md` (the rejected-alternative bullet writes each name in BOLD and carries the disclaimer "nothing in this repo starts it"), `tools/test_radar_trigger.py` (`names_the_rejected_bullet_writes` plus the test) |
| red-first (the tripwire) | `mutate bug_0274_list` (the declaration back to three names while the bullet writes five) -> **1 failed**: written 5, published 3 |
| red-first (AC-1) | `mutate bug_0274_v04` -> **2 failed** ("names cloud_option ('hosted code routine'), which the declaration lists as not built"); `mutate bug_0274_v05` -> **2 failed** ("'sandbox routine'"). Both sentences were GREEN for the verifier before this change |
| naming test | `tools/test_radar_trigger.py::test_the_names_of_the_rejected_option_are_the_ones_its_bullet_writes` |
| suites run | `tools/test_radar_trigger.py -q` (the whole file; it is not a declared surface, rc 0 through gate 5) -> 19 passed, **1.88 s** |

The marker is BOLD and not backticks on purpose: backticks stay free for code in that bullet
(`cloud_option`, `--describe`), so marking a name cannot collide with naming a field. Deciding
which noun phrase of a paragraph IS a name for a mechanism is world knowledge; the text marking its
own names is the derivation that replaces it.

Side effect that had to be measured, not assumed: with `claude.ai` now standing in the bullet, the
bullet itself became a claiming sentence and the claim reader refused it. The bullet now carries a
disclaimer the reader already knows ("nothing in this repo starts it"), which is what it always
meant -- it did not get an exemption.

### H181 / BUG-0263 -- closed

| field | value |
|---|---|
| class | INSTR |
| mechanism | `_test_citations` pairs single backticks over the WHOLE file; a fence is three backticks, so from the first fence on the reader paired the GAPS between spans and every citation below it vanished |
| change | `tools/test_repo_hygiene.py` -- `_FENCE_RX` and `_without_fenced_blocks` (fenced blocks blanked to spaces of the same length, offsets preserved), applied in `_test_citations`; the global floor raised from 150 to 500 with its measurement beside it; the new test |
| measurement (AC-5, the convention) | a citation INSIDE a fence is worth nothing, the text around it is read as before. Under that convention the judged corpus of this sweep goes **150 -> 654** over this tree (2026-09-12), and exactly the THREE citations the item predicted surface as unresolvable |
| AC-2 (those three) | repaired. `docs/pilot/2026-09-01-research-pilot.md`: the test was renamed AND inverted with BUG-0083, so the sentence now names `test_a_task_may_name_an_experiment_two_levels_under_the_question_it_serves` and says what happened. `docs/reviews/2026-09-02-tsk0107-office-duties-measurements.md` twice: there the WRONG node is the finding itself, so the file and the name now stand in separate spans and the real node is named beside it; and the renamed `test_every_test_a_hole_names_is_one_that_exists` |
| red-first (the reader) | `mutate bug_0263` (`readable = text`) -> **1 failed** on the drive: a citation behind a fence comes back `[]` |
| red-first (the item's own repro) | `mutate bug_0263_plant` (the node id below the fence in `docs/office-kit-from-field.md` replaced by a name no suite defines, 2 sites): with the fence-aware reader **1 failed**, both sites named; with `bug_0263` applied on top **1 passed in 87.19 s** -- the defect itself, green while a citation resolves at nothing |
| naming test | `tools/test_repo_hygiene.py::test_no_pairing_shift_blinds_the_pointer_sweep_for_the_rest_of_a_file` |
| suites run | `tools/test_repo_hygiene.py -q -k "no_pairing_shift_blinds or test_the_test_pointer_reader_reads_the_shapes or test_every_test_pointer_this_repo_writes_resolves"` -> 3 passed, **106.02 s** |
| AC-3 (per-file floor) | DECIDED against, with the measurement in the test's docstring: three files of this tree carry a node id inside a DOUBLED backtick span as an ILLUSTRATION (`team-kits/office-team/hooks/_filing.py`, `docs/holes/H41.md`, `docs/reviews/phase0-disposition.md`), and telling an illustration from a pointer is the open BUG-0257 / H175. A per-file floor built before that buys three false reds |
| AC-4 | NOT done by me: deleting the scoped second reader in `tools/test_office_package.py` lies outside my `allowed_scope`. Seam handoff |

MEASURED AND DELIBERATELY NOT SHIPPED, because it turns files this round may not write red: blanking
the fences removes the commonest cause of a shifted pairing, not every cause -- a single stray
backtick inside a string shifts it just the same. A reader answering under BOTH pairings (file-wide
and line-bounded, the H41 (c) shape) finds **65 further node ids in 11 files** of this tree, and
**three of them resolve at nothing**, all three under `team-kits/`:

* `team-kits/dev-team/hooks/_compat.py:1065` and `team-kits/office-team/hooks/_compat.py:1065` cite
  `tools/test_hooks.py::test_every_escape_character_of_this_kit_gets_its_own_reading`
* `team-kits/office-team/hooks/gate_ledger_valid.py:450` cites
  `tools/test_hooks_v2.py::test_a_heredoc_body_an_interpreter_executes_is_not_prose_here`

(A fourth candidate, `kernel/report.py:2412`, is NOT a finding: it is pasted runner output inside
one span -- the class that module's own `_CITATION_GLUE_RX` names -- and my probe's gluing invented
it. Named here so nobody carries it over as a defect.)

The wider reader is a round of its own; the three citations above are a seam handoff.

### H159 / BUG-0241 -- one of three unread pointer kinds closed; item stays a DOWNGRADE

| field | value |
|---|---|
| class | INSTR |
| mechanism | the three harness role texts under `.claude/agents/` got their first reader in TSK-0123; it resolves item ids against the store and node ids against the suite, and was blind to three further kinds -- a test name nobody marked as code, a claim naming no test at all, and a PATH |
| change | `tools/test_review_procedure.py` -- `_path_pointers` + `_expanded` + `test_every_path_pointer_the_harness_role_texts_write_resolves`. A span is judged as a path when it has no whitespace, carries a separator, is not a node id, does not open with a redirection or with the separator itself, and names more than ONE segment |
| measurement that shaped it | the naive form (any span with a `/`) reports four rows of the shipped texts, and three of them are not paths at all: `>/dev/null` (a redirection), `/model` (a command of the client), `staging/` (a word whose parent the sentence supplies). The fourth, `team-kits/{dev,office,research}-team/`, is a brace span and is expanded. With the definition above, 12 path pointers are judged and all resolve |
| red-first | `mutate bug_0241` (a path span is not read at all -- the state before this round) -> **1 failed**, `[] == ['tools/validate.py']`; and `mutate bug_0241_plant` (a path that moved: `tools/validate.py` -> `tools/validate_that_moved_away.py` in the role text) -> **1 failed**, the file and the line named |
| naming test | `tools/test_review_procedure.py::test_every_path_pointer_the_harness_role_texts_write_resolves` |
| suites run | `tools/test_review_procedure.py -q -k path_pointer_the_harness_role_texts` -> 1 passed, **3.04 s** |
| WHY IT IS STILL A DOWNGRADE | two of the three kinds are left, and both deliberately: a test name written WITHOUT backticks, and a property claim that names no test. `CLAUDE.md` states for the whole repository that those two are the implementer's and the verifier's job and not the suite's -- a reader without the marking goes red at ordinary prose. NO EVD was recorded for BUG-0241, so the passing test cannot open a verification batch for an item that is not closed; its row is in list (ii), batch REST-1, with a sentence that says what moved |

### Downgrades, each with the measurement that makes it one

No third state: every row below is in list (ii) batch REST-1 with ONE plain-German sentence for
`limits`, so the user decides. What each one is NOT is "known, later".

| id | hole | why unclosable HERE (measured) | bound |
|---|---|---|---|
| BUG-0102 | H10 | an exhaustive search for code halves no test distinguishes means one mutation per site and a WHOLE run of the suite it belongs to per mutation. `.claude/hooks/test_gates.py` alone collects 553 tests, and the full run is the merge's by rule (gate 5 refuses a stream the whole declared surface). I did not build the instrument either and I do not claim to have: this round spent its budget on eight closures | the two halves that WERE found are closed and each carries a red test |
| BUG-0165 | H73 | NOT ATTEMPTED in this round, and that is the honest word. Four measured limits of the decision-first watcher, none with an attack chain | the four stand in the entry, each with its own measurement |
| BUG-0166 | H74 | the numbers behind the faster gate suite are host-load numbers; a part of the measured speed-up was neighbouring load and not code. Re-measuring it means an idle machine, and three builders share this one today | the speed-up itself holds; only its factor is smaller than the note says |
| BUG-0177 | H85 | the provenance check of a third-party design template reads what the FILE declares; deciding whether the source on the internet changed means going to the network, and no test of this suite does | the frontmatter carries `source_commit`/`source_blob_sha1`, so a marked change is caught |
| BUG-0206 | H122 | the reporter's corpus is what git carries. Widening it to what git IGNORES means reading **104424 files on this tree** (measured 2026-09-12, `git ls-files -o --ignored --exclude-standard`), effectively all of them tool caches -- and "a cache" is not a property a reader derives, it is the enumeration this repo keeps paying for | the reporter warns and never blocks, and its docstring names the corpus it really asks |
| BUG-0234 | H152 | a declared narrowing option whose VALUE hits nothing reads as a selection and passes. Deciding what a value hits needs a collection of the whole suite -- which is the cost the gate exists to save (FR-0086) | the accidentally-typed class is closed; the remaining one has to be written on purpose, and three tripwires sit on the enumeration |
| BUG-0270 | H187 | widening the pointer sweep to `tools/` turns the four fixture strings of `tools/test_pointer_sweep.py` red at once, and telling an ILLUSTRATION from a pointer is BUG-0257 / H175, which nobody can close | the sweep names its two trees in its own docstring and judges 654 citations (up from 150 this round) |

## Seam handoffs

Each one is a change I may not write; the lead carries it to the owner.

1. **`team-kits/kernel/holes.py`, `cited_tests` (H164 / BUG-0246) -- stream A.** `tools/migrate_holes.py`
   is a thin caller since TSK-0126; the reader that takes a MODULE name for a test citation lives in
   the kernel. The defect is not the collection but the ORDER: the judge that notices the ambiguity
   runs AFTER the item is written, and the migration is idempotent, so a second run does not repair
   it. The change: `migrate` puts the judge's question BEFORE the write -- a collected citation that
   resolves to no test, or to more than one, stops the run instead of being written. I did not write
   the test for it either (`tools/test_migrate_holes.py` is mine, but a test for code that does not
   exist yet ships red).
2. **`team-kits/kernel/report.py:666-679` (BUG-0032) -- stream A.** `tools/validate.py` is a thin
   caller; the orphan heuristic (`if entry not in active_items`) is the kernel's. AC-1 asks that a
   staging path an ACTIVE `EVD` names in `artifact_refs` is not called an orphan, or that the
   warning names the reference it ignored. Note for whoever takes it: this round wrote
   `artifact_ref: staging/TSK-0143/protocol.md` into eight evidence items, so the case is live in
   this store.
3. **`tools/test_office_package.py` (BUG-0263 AC-4).** With the fence-aware reader shipped, the
   scoped second reader
   `test_every_test_the_field_report_verdicts_name_is_one_that_exists` is a second copy of one
   definition and AC-4 asks for its deletion. That file is outside my `allowed_scope`.
4. **Three rotted test pointers under `team-kits/` (measured this round, see the H181 row).**
   `team-kits/dev-team/hooks/_compat.py:1065` and `team-kits/office-team/hooks/_compat.py:1065`
   cite `tools/test_hooks.py::test_every_escape_character_of_this_kit_gets_its_own_reading`;
   `team-kits/office-team/hooks/gate_ledger_valid.py:450` cites
   `tools/test_hooks_v2.py::test_a_heredoc_body_an_interpreter_executes_is_not_prose_here`. Neither
   name exists. They are invisible to the shipped sweep because a stray backtick shifts the pairing
   in those files; a reader answering under both pairings finds them (and 62 further, resolving,
   node ids in 11 files).
5. **`.claude/settings.json` and `.claude/hooks/_harness.py` -- the USER's shell**, sites 6 and 7 of
   `project_memory/staging/TSK-0143/h182-harness-patch-EXTENDED.md`.
6. **Ten of the fourteen OPEN exception candidates need `transition <id> TRIAGED`** before their
   batch can be applied -- the list names all fourteen. This item forbids me to transition a BUG.

## Foreign reds

* `tools/test_pointer_sweep.py::test_the_root_files_the_sweep_skips_are_installed_and_would_be_noisy[dev-team]`,
  `[office-team]`, `[research-team]` -- 3 failed, 4 passed, 10.38 s. The failure is a PowerShell
  PARSE error in `team-kits/scaffold_team.ps1:545` ("Unerwartetes Token 'if' in Ausdruck oder
  Anweisung", at `if ($agentResolved -ne $agentRaw) { [IO.File]::WriteAllText(...`). That file is
  stream B's and I never touched it. Left alone, reported here.
* `python tools/validate.py` -> **VALIDATION FAILED (3)**: "dev-team / office-team / research-team:
  kit files changed but VERSION not bumped". Expected and foreign: I changed no file under
  `team-kits/`, and this item forbids me to run `tools/bump_kit_version.py` (the goal round stamps
  once). Nothing else is reported.

## Runs, with durations

One pytest at a time, selections only; no full run, no stamp, no commit, no push, no mint.

| run | result | duration |
|---|---|---|
| `.claude/hooks/test_gates.py -q --collect-only` | 549 collected | 0.51 s |
| `.claude/hooks/test_gates.py -q -k "prose_is_one_that_exists or replaced_contract"` (baseline) | 2 passed | 5.22 s |
| `.claude/hooks/test_gates.py -q -k "no_timed_span_here or prose_is_one_that_exists"` | 2 passed | 1.07 s |
| `.claude/hooks/test_gates.py -q -k "session_guards_watch_list or arbiter_refuses_a_shell or arbiter_is_a_shell"` | 3 passed | 3.85 s |
| `.claude/hooks/test_gates.py -q -k "pointer_reader_answers or prose_is_one_that_exists"` | 2 passed | 2.90 s |
| `.claude/hooks/test_gates.py -q -k end_states_this_repo_reaches` | 1 passed | 1.86 s |
| `.claude/hooks/test_gates.py` 7 node ids (the EVD run) | 7 passed | 14.76 s |
| `tools/test_review_procedure.py -q -k "ladder_reader_wants_both_axes or no_lead_skill_keeps_its_own_copy"` | 2 passed | 1.53 s |
| `tools/test_review_procedure.py -q -k path_pointer_the_harness_role_texts` | 1 passed | 3.04 s |
| `tools/test_radar_trigger.py -q` (whole file, not a declared surface) | 19 passed | 1.88 s |
| `tools/test_review_procedure.py` + `tools/test_radar_trigger.py`, 4 node ids (the EVD run) | 4 passed | 2.08 s |
| `tools/test_repo_hygiene.py -q -k "no_tool_trace_lies_unaccounted or tracks_no_ignored_file or known_out_of_scope_trace"` | 3 passed | 2.40 s |
| `tools/test_repo_hygiene.py -q -k "no_pairing_shift_blinds or ...reads_the_shapes or ...writes_resolves"` | 3 passed | 106.02 s |
| `tools/test_repo_hygiene.py` 5 node ids (the EVD run) | 5 passed | 114.05 s |
| `tools/test_pointer_sweep.py -q` (reads `docs/`, which I changed) | 3 failed, 4 passed -- FOREIGN | 10.38 s |
| `python -m ruff check` over the six changed `.py` files | All checks passed | < 1 s |
| `python tools/validate.py` | FAILED (3) -- foreign, VERSION not bumped | 3.53 s |

Reading suites chosen because they READ what I changed (`DEC-0080` rule 2, callers grepped):
`tools/test_radar_trigger.py` and `tools/test_repo_hygiene.py` are the only files that name
`radar_routine`; `tools/test_radar_trigger.py` and `tools/test_hooks.py` are the only ones that
name `radar/README.md`; `tools/test_repo_hygiene.py` and `tools/test_pointer_sweep.py` are the ones
that sweep `docs/`. **`tools/test_hooks.py` was NOT run** and that is deliberate: the host rules of
this item forbid running it whole, and what it reads of `radar/` is `MIGRATION_DOC_TREES` -- whether
a V1 path is named there. My change to that README adds bold markers and a disclaimer clause and no
path at all, so the property that suite reads is untouched. Named here rather than left silent.

## The verification batch line for the lead

Built against a COPY of the store and accepted: **rc 0, 8 of 8 items closable, 0 refused**, each
with the EVD the kernel picked up (`kernel/naming_tests.coverage_blocker` read the node ids of every
run command and found a test that NAMES the bug in each).

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory \
  request-approval verification --batch BUG-0008 BUG-0133 BUG-0137 BUG-0243 BUG-0263 BUG-0274 BUG-0275 BUG-0290
```

Every closed id appears in exactly one line; eight ids, one line, under the limit of ten.

HOW THE DRY CHECK HAD TO BE DONE, because the first attempt failed for the rig and not for the
lines: `approvals` resolves a node id against `os.path.dirname(state.root)`, so a store copy that
does not sit INSIDE a checkout makes every node "resolve to no test in this checkout" -- 8 of 8
refused, with a message about the evidence. Copied into the rig tree instead
(`_round-scratch/TSK-0143/tree/project_memory`), the same line is rc 0 and prints the question with
all eight items and their EVDs. Written down because the first reading looked like a defect in the
evidence and was a defect in my copy.

| id | hole | EVD |
|---|---|---|
| BUG-0008 | -- | EVD-0358 |
| BUG-0133 | H41 | EVD-0354 |
| BUG-0137 | H45 | EVD-0353 |
| BUG-0243 | H161 | EVD-0351 |
| BUG-0263 | H181 | EVD-0359 |
| BUG-0274 | H190 | EVD-0357 |
| BUG-0275 | H191 | EVD-0356 |
| BUG-0290 | H206 | EVD-0355 |

## COUNTS -- honest, over the 19 items of my list

* **closed: 8** -- H41/BUG-0133, H45/BUG-0137, H161/BUG-0243, H206/BUG-0290, H181/BUG-0263,
  H190/BUG-0274, H191/BUG-0275, BUG-0008. Each has a red-first row above, a test that NAMES it, the
  reading suites as a selection, and an EVD.
* **downgraded with a measurement: 9** -- H10/BUG-0102, H73/BUG-0165, H74/BUG-0166, H85/BUG-0177,
  H122/BUG-0206, H152/BUG-0234, H159/BUG-0241 (one of three kinds closed and measured, the item
  stays open), H187/BUG-0270, H207/BUG-0291. Each has one plain-German sentence in list (ii), batch
  REST-1, and a dry-checked `update` line.
* **handed over, not mine to write: 2** -- H164/BUG-0246 (`team-kits/kernel/holes.py`, stream A) and
  BUG-0032 (`team-kits/kernel/report.py`, stream A). Both are seam handoffs with the exact change.
* **handed to the user's shell patch: 2 new sites** (6 and 7) on top of the five that were already
  in `staging/TSK-0140/h182-harness-patch.md`; and **4 rows the spawn message expected as patches
  are NOT patches** (H14/BUG-0106, H153/BUG-0235, H199/BUG-0283, H203/BUG-0287) -- they are
  exception candidates, batch GATE-1, with the reason in list (ii).
* **8 EVDs** recorded through the kernel, kind `test`, result `pass`, run-scope `selection`, no
  lock refusal on any of them.

One number of mine was wrong on its first writing and is corrected above rather than quietly: I
wrote into a docstring that the cross-file sweep of `.claude/hooks/` is EMPTY today. The first green
run found two such pointers in `gate_test_scope.py`, and my reader had eaten the leading dot of
their path. Both facts are in the H41 row.

Last clock reading of this protocol: 2026-09-12 11:14:30.

---

# Rework 1 -- the verifier's round 1 (FAIL), worked

Started 2026-09-12 11:53:58 (clock read), finished 12:16:17. The report
(`project_memory/staging/TSK-0143/verify-round-1.md`) was read WHOLE, 95 lines -- said here because
`DEC-0095` (6) makes that cost visible: it is a findings list where every line is a claim about my
package, so there is no "the section that answers the question".

## F1 -- blocking. The clock reader read one spelling while its docstring claimed a definition

| field | value |
|---|---|
| what was wrong | `_touches_the_clock` and `_name_bound_to_a_clock_reading` asked for an `ast.Attribute` on the NAME `time`. The docstring said "a helper that reaches that module at all", and the reader above it promised "a test that starts timing something tomorrow is read without being added anywhere". The verifier drove three sources through it: `time.X` 2 spans, `from time import` 0, `import time as clock` 0 -- and end to end, the H161 defect restored with the sizing helper on `from time import monotonic` was **1 passed in 1.74 s** (their measurement) |
| change | `.claude/hooks/test_gates.py` -- new `CLOCK_MODULE`, `_clock_names(tree)` (reads `ast.Import` / `ast.ImportFrom`, aliases included) and `_reads_the_clock(node, clock)`; all three readers take the derived names, and `_statement_that_closes_the_span` -- the THIRD site of the same spelling, which the finding did not name -- goes with them |
| the test | the drive now runs over all three spellings, built from a table of `(import line, reading)` pairs, and asserts the span count as well as the report in each |
| red-first, three rows | `mutate bug_0243` (`time.monotonic`) -> **1 failed**; `mutate bug_0243_from_import` (the verifier's `v2b_h161_both`: the defect PLUS the helper on `from time import monotonic`) -> **1 failed**; `mutate bug_0243_alias` (`import time as clock`) -> **1 failed**. Each names `_a_line_too_long_to_read_in`, "which reads the clock itself" |
| suites run | `.claude/hooks/test_gates.py -q -k no_timed_span_here` -> 1 passed, **1.75 s**; the seven-node line -> 7 passed, **7.78 s** |

## F2 -- the comment that claimed an empty sweep

`.claude/hooks/test_gates.py:5548` said `(d), the sweep -- empty in this directory today`. It is not
empty: two cross-file pointers stand in `gate_test_scope.py`, and the test's own docstring said so
two paragraphs above. The clause is struck; the comment now reads `# (d), the sweep over this
directory's own prose`. This is the SECOND time this round that this one sentence was wrong -- I
corrected the docstring in round 1 and left the comment.

## F3 -- a pointer at a test that does not exist, in the file whose subject is exactly that

`tools/test_repo_hygiene.py:1241` named `test_no_fence_blinds_the_pointer_sweep_...` (the test is
`test_no_pairing_shift_blinds_...`) and claimed a "per-file half" the same round decided against.
The whole comment is rewritten: it now says what the constant IS (a floor) and points at the one
place the measurement lives. Measured after: `grep -rn` over `*.py` and `*.md` finds the old name
only in the verifier's own report.

## F4 -- "150 -> 654" was not a measurement

150 was the OLD assertion floor, not a count. Measured now, both readers over the SAME corpus
(`_round-scratch/TSK-0143/probe_corpus.py`, 2026-09-12 12:0x):

| | |
|---|---|
| the reader as it stood before this change | **625** |
| the fenced-block reader | **680** in 172 files |
| files whose count changes | **15**, and **none of them loses a citation** |
| `docs/office-kit-from-field.md` | **0 -> 14** (not "0 of 8"), its first fence opens in line 23 |

The verifier counted 617 / 672 twenty minutes earlier; three builders write this tree, so the
figure moves and the direction does not. ONE PLACE now holds it -- the docstring of
`test_no_pairing_shift_blinds_the_pointer_sweep_for_the_rest_of_a_file`. The two other copies are
gone: the floor comment says only that it is a floor, and `_without_fenced_blocks` carries the
mechanism and the convention without a figure. The "65 node ids in 11 files" sentence is gone too
and for the same reason -- re-measured at 12:0x it is 52 in 8 files, because stream A has since
repaired two of the three dead ones; a number that moves that fast belongs in a protocol with its
hour, not in a docstring.

**EVD-0359 is SUPERSEDED by EVD-0378** (recorded through the kernel, same nodes, the measured
figures, with the sentence naming what it replaces). The lead archives EVD-0359. The verification
batch below resolves BUG-0263 to EVD-0378 by itself -- the kernel takes the newest.

## F5 -- H73/BUG-0165 is CLOSED, and H10/BUG-0102's sentence says what it really is

**BUG-0165 / H73 (a) -- closed.** The verifier is right that an exception for a gap whose own entry
calls it "die eine echte Lücke" *with* a closing direction, in a file inside my `allowed_scope`, is
the third state this repo does not have.

| field | value |
|---|---|
| mechanism | `_dec_citations` skips an id inside any delimiter longer than itself, because its corpus quotes prose and command lines. In a PYTHON source the double quote is not a quotation mark, it is the language's string delimiter, and what stands inside is text the program HANDS OUT. Measured 2026-08-29 for the entry: of 22 double-quoted spans carrying an id, 16 were of that kind -- 13 kernel refusal and briefing messages and 3 handover-marker literals. An id that rots there rots in front of the USER at the moment a gate refuses |
| change | `tools/test_repo_hygiene.py` -- `_docstrings_of`, `_dec_citations_in_messages` (read through `ast`, not through quote characters) and the sweep in `test_every_decision_pointer_in_a_shipped_kit_file_resolves` calls it for every `.py` |
| the two exclusions, both properties | a DOCSTRING (documentation may exhibit an id -- the memory-budget guard shows `"a DEC-2100 controller"` as its own false positive, and DEC-2100 is an id this store deliberately does not have), and an id inside a backtick span within the message, which is the data marker these kits already use |
| measured | **69** such citations in the shipped tree, **all resolving**. The first shape I tried -- every string literal, docstrings included -- reported three DEAD ids, all of them that same deliberate DEC-2100; that is what made the docstring line the definition and not an exception |
| red-first, three rows | `mutate bug_0165_reader` (the message reader returns nothing) -> **1 failed** on the drive, `[] == [(1, 'DEC-9142')]`; `mutate bug_0165_plant` (a dead id planted inside the real refusal at `team-kits/kernel/dispatch.py:1560`) -> **1 failed**, naming file and line; the SAME plant with `mutate bug_0165` on top (the sweep as it stood before this change) -> **1 PASSED in 1.09 s**, which is the defect itself |
| naming test | `tools/test_repo_hygiene.py::test_a_decision_named_in_a_message_a_user_reads_is_one_that_resolves` |
| suites run | the seven-node hygiene line -> 7 passed, **2.63 s** |
| EVD | EVD-0377 |

(b), (c) and (d) of H73 stay as the entry has them: the honestly declared limits of a prose test.
They are NOT in any exception batch either -- the item is closed on (a), and (b)(c)(d) are what its
`limits` field describes.

**BUG-0102 / H10.** The verifier is right that a budget is not a world limit, so the sentence no
longer pretends it is one. It now opens with "WIR HABEN UNS ENTSCHIEDEN, DIESE ZEIT NICHT
AUSZUGEBEN", names the measured size of the job -- **405 decision sites** in the seven gate sources
(`_harness.py` 225, `gate_test_scope.py` 108, `gate_commit_evidence.py` 24, `gate_todo_items.py`
15, `_sandbox.py` 13, `gate_lead_write_scope.py` 11, `gate_spawn_needs_item.py` 9), each needing a
full run of a 553-test suite -- and ends by asking the user whether he wants it as a round of its
own. The lead puts THAT to him.

## F6, F7, F8 -- the three list corrections

* **F6:** `limits-update-lines.md` cited `AUTOMATA["BUG"].terminal_from`, which is not an attribute
  (the constructor folds that argument into `self.allowed`). It now cites
  `AUTOMATA["BUG"].allowed`, built at `team-kits/kernel/backlog_types.py:87`.
* **F7:** the two line pointers in the patch file are refreshed (`test_gates.py:539` -> `:554-561`,
  `:1812` -> `:1902`) with a sentence saying that the ANCHOR blocks carry no line number and
  resolve on their text alone -- which is why the patch itself never went stale.
* **F8:** the 34 sentences are rewritten with real ä/ö/ü/ß and stored UTF-8, because the user reads
  them inside the approval question and the kernel prints real umlauts there. Verified on the
  bytes: `bug-0157-limits.json` holds `Ausf\xc3\xbchrens`. One sentence (BUG-0198) carries no
  umlaut because none of its words has one. **Re-dry-checked against a store copy: 34 update lines
  and 6 batch lines, rc 0 every one, 0 refused.** `bug-0165-limits.json` was deleted by the
  generator itself -- H73 is closed and must not stand in an exception list.

## Two rows handed over by the lead from stream B (12:09)

1. **S2 remainder in my files.** `README.md` spells out an `evidence` call in the merge-gate
   paragraph; it now carries `--run-command "<the command line you ran>" --run-scope <full|selection>`,
   the same shape B wrote into the 17 kit sites. One site in my area; the other `evidence` mentions
   in that file are the command NAME in a list, not a call.
2. **The constitution pin B could not write** (`dev-team hooks/ENFORCEMENT.md §1`, the
   `gate_design_sighted` row rewritten for BUG-0294): run, journal appended to
   `docs/reviews/phase0-disposition.md` and `tools/constitution_section_pins.json` updated.
   `python tools/pin_constitution_sections.py` now reports **3 kits, 12 files, 125 sections, all
   pins current**. TWO deviations, both stated rather than hidden:
   * B's note contains a bare `--`, and gate 1 refuses a write-capable line carrying it (it reads
     the token as a path it cannot place, `C:\Offline Repos\AgentAndSkills\..`). The note is B's
     sentence with `--` replaced by `;` and one clause added saying who wrote it and why.
   * the lead's measuring selection, `tools/test_hooks.py -k pinned_instruction_file`, matches
     **nothing** (1063 deselected). The suite that really reads the pin journal is
     `tools/test_shortening_net.py` -- a file in my `forbidden_scope`, which I therefore only RAN:
     `::test_no_section_of_a_pinned_instruction_file_disappears_unnoticed`,
     `::test_a_pinned_file_that_carries_no_section_is_refused`,
     `::test_the_pin_detector_reads_the_spellings_it_claims` -> 3 passed, **1.43 s**.

## The foreign red of round 1 is gone, and it was repaired in MY area

`tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves` went red at 12:0x on
`docs/holes/H138.md:18`, which cited
`tools/test_design_conformance.py::test_a_record_is_written_even_when_the_checks_find_something_and_the_sighting_gate_still_opens`.
Stream B renamed that test to
`::test_a_draft_with_conformance_findings_is_refused_and_an_undecided_one_is_not` while closing
BUG-0294, and their own protocol lists the three texts they corrected -- the hole entry was a
fourth, and it lies under `docs/`, which is mine. It was not only the NAME that had aged: the
entry's measured chain says "rc 0 -- der Haken lässt durch", and the gate now refuses. The entry
carries the closure with BUG-0294, the new node id, and its old row marked as what held BEFORE.
Measured after: `::test_every_test_pointer_this_repo_writes_resolves` **1 passed in 57.79 s**.

(The other foreign red of round 1, `tools/test_pointer_sweep.py` on a PowerShell parse error in
`team-kits/scaffold_team.ps1:545`, was never confirmed by the verifier and is stream B's file. Not
re-run in this rework.)

## Runs of rework 1

| run | result | duration |
|---|---|---|
| `.claude/hooks/test_gates.py -q -k no_timed_span_here` | 1 passed | 1.75 s |
| `.claude/hooks/test_gates.py`, the 7 node ids | 7 passed | 7.78 s |
| `tools/test_repo_hygiene.py -q -k "decision_named_in_a_message or decision_pointer_reader_can_tell or every_decision_pointer_in_a_shipped"` | 3 passed | 2.02 s |
| `tools/test_repo_hygiene.py`, the 7 node ids (the EVD run) | 7 passed | 2.63 s |
| `tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves` (after the H138 repair) | 1 passed | 57.79 s |
| `tools/test_review_procedure.py`, 5 node ids | 5 passed | 1.87 s |
| `tools/test_shortening_net.py`, 3 node ids (the pin journal) | 3 passed | 1.43 s |
| `python tools/pin_constitution_sections.py` | 125 sections, all pins current | 2 s |
| `python -m ruff check` over the five changed `.py` files | All checks passed | < 1 s |

## The verification batch line, rebuilt

Dry-checked against a store copy INSIDE a checkout: **rc 0, 9 of 9 closable, 0 refused**, and the
kernel resolves BUG-0263 to the superseding EVD-0378 by itself.

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory \
  request-approval verification --batch BUG-0008 BUG-0133 BUG-0137 BUG-0165 BUG-0243 BUG-0263 BUG-0274 BUG-0275 BUG-0290
```

| id | hole | EVD |
|---|---|---|
| BUG-0008 | -- | EVD-0358 |
| BUG-0133 | H41 | EVD-0354 |
| BUG-0137 | H45 | EVD-0353 |
| BUG-0165 | H73 | EVD-0377 |
| BUG-0243 | H161 | EVD-0351 |
| BUG-0263 | H181 | EVD-0378 (supersedes EVD-0359) |
| BUG-0274 | H190 | EVD-0357 |
| BUG-0275 | H191 | EVD-0356 |
| BUG-0290 | H206 | EVD-0355 |

## COUNTS after rework 1

* **closed: 9** (was 8) -- H73/BUG-0165 joins H41, H45, H161, H206, H181, H190, H191 and BUG-0008.
* **downgraded with a measurement: 8** (was 9) -- H10/BUG-0102 (its sentence now names a CHOICE and
  its price), H74/BUG-0166, H85/BUG-0177, H122/BUG-0206, H152/BUG-0234, H159/BUG-0241, H187/BUG-0270,
  H207/BUG-0291.
* **handed over, not mine to write: 2** -- H164/BUG-0246 and BUG-0032, both stream A.
* **handed to the user's shell patch: 2 new sites** (6 and 7), line pointers refreshed; and 4 rows
  that are exception candidates rather than patches (H14, H153, H199, H203).
* **2 rows from stream B**: the README `--run-scope` site and the constitution pin, both done.
* **10 EVDs** through the kernel: EVD-0351, 0353-0359 in round 1, EVD-0377 and EVD-0378 in rework 1.
  The gap at EVD-0352 is NOT mine and not a lost id -- I first wrote that it was, then read the
  file: it belongs to stream A (`related: [BUG-0281]`). Three streams mint out of one counter.

Last clock reading of this protocol: 2026-09-12 12:16:17.

---

# Rework 2 -- round 2 (FAIL on R1), worked

Started 2026-09-12 12:31:31 (clock read). The round-2 report (58 lines) was read WHOLE; it is a
findings list about my package, so there is no section that answers on its own.

## R1 -- blocking. H73 (a) counts sixteen sites; two of them are shell literals my reader never opened

The order said: TRY first, and only write a hole payload if it is not one row. **It was one row.**

| field | value |
|---|---|
| what was wrong | `_dec_citations_in_messages` is `ast`-based and the sweep called it `if rel.endswith(".py")`. Two of the sixteen sites `docs/holes/H73.md` (a) counts are the handover-marker literals of the INSTALLERS (`team-kits/scaffold_team.sh`, `.ps1`). The verifier planted a dead id in `scaffold_team.sh:284` -- the line the script writes into `.claude/HANDOVER_PENDING` -- and the run was **2 passed**, green, while my docstring and EVD-0377 said CLOSED |
| the corpus, measured BEFORE building | ids inside quoted spans of `.sh`/`.ps1` under `team-kits/`: **4, in 2 files** (`scaffold_team.sh:284`, `:923`, `scaffold_team.ps1:272`, `:850`), all `DEC-0032`, all resolving. That is what made it one row rather than a second reader's worth of work |
| change | `tools/test_repo_hygiene.py` -- `_SHELL_LITERAL_RX`, `SHELL_SOURCES` and `_dec_citations_in_shell_messages`; the sweep takes the `elif` branch for `.sh`/`.ps1`. `team-kits/scaffold_team.*` is stream B's file: I READ it, I did not edit it |
| the definition, and its bound | the same rule as the Python half -- in a SOURCE a quote is the language's string delimiter, not a quotation of prose. What is BOUNDED and says so in its own docstring: this reads a quoted run inside ONE line, because `bash -n` and the PowerShell parser check syntax and hand back no literals, so there is no parser to ask; a literal continued across a line break is outside it. And NO backtick exemption on the shell side, because a backtick there opens a command substitution or escapes the next character -- a property of the two languages, not an omission |
| red-first, three rows | `mutate bug_0165_shell_reader` (the shell reader yields nothing) -> **1 failed** on the drive, `[] == [(1, 'DEC-9142')]`; `mutate bug_0165_shell_plant` (the verifier's own plant at `scaffold_team.sh:284`) -> **1 failed**, naming `:284` and `:923`; the SAME plant with `mutate bug_0165_shell` on top (the sweep's shell branch off, i.e. the state round 2 measured) -> **1 PASSED**, which is the defect exactly as reported |
| naming test | `tools/test_repo_hygiene.py::test_a_decision_named_in_a_message_a_user_reads_is_one_that_resolves` -- its docstring now says both halves and where the second came from, and the drive carries the shell shape plus two non-shapes (an id in a shell COMMENT is `_dec_citations`' subject and must not be double-read; a quoted span with no id must not invent one) |
| documents | `docs/holes/H73.md` carries the closure with both readers, both counts and the red-first pair, and its verdict line now reads "(a) GESCHLOSSEN (TSK-0143), der Rest bleibt Rest" |
| suites run | `tools/test_repo_hygiene.py -q -k "decision_named_in_a_message or every_decision_pointer_in_a_shipped or decision_pointer_reader_can_tell"` -> 3 passed, **5.54 s**; the nine-node line -> 9 passed, **91.26 s** |
| EVD | **EVD-0391 supersedes EVD-0377** (recorded through the kernel, with the sentence naming what it replaces and why) |

## R3 -- EVD-0378 cited a number from a run it did not record

Its `run_command` had dropped
`tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves`, the node whose
sweep produces the 625/680 in its own summary. **EVD-0392 supersedes EVD-0378**, with the NINE-node
line that carries it (9 passed, 91.26 s) and the same measurement. The lead archives 0378; the
verification line resolves BUG-0263 to 0392 by itself.

## R4 -- written as a hole payload, and NARROWED by measuring it

`project_memory/staging/TSK-0143/hole-docstring-dec-id.json`.

The finding as reported was "a DEC id in a docstring of a shipped kit file is judged by NO reader".
Measured before writing it up, and it is smaller and more precise than that: of **190** DEC ids in
docstrings of shipped kit `.py` files, **184 are judged** by `_dec_citations` -- they stand outside
any paired delimiter -- and **6 are judged by nobody**. Four of the six are deliberate
ILLUSTRATIONS (`DEC-2100` in the three `guard_memory_budget.py` docstrings, `DEC-0000` in
`team-kits/kernel/migrate.py:1291`). **Two are real citations**: `team-kits/kernel/dispatch.py:204`
and `team-kits/office-team/templates/repo/scripts/invoice_intake.py:370`, both of the shape
`"""… (DEC-nnnn (n))."""`, where the positional `"`-pairing meets the triple quote and swallows the
body. The payload carries that measurement, the two lines, the repro, three acceptance criteria and
one plain-German sentence with real umlauts.

I did NOT fix it in this round and the payload says why: the repair is to `_dec_citations`'
delimiter pairing, which every DEC sweep of this repo stands on, and changing that in the last
minutes of a rework with two neighbouring streams writing the same tree is the shape of change this
repo asks to be measured on its own.

## Self-found in rework 2: my sweep went red for a neighbour who was saving

While running the nine-node line the first time, `test_every_test_pointer_this_repo_writes_resolves`
came back **1 failed** with a `SyntaxError` out of `_defined_in` -- `File "<unknown>", line 143,
handle.write("---` -- and a walk of the whole tree a minute later found **0** unparsable files; the
same node was then green in 71.72 s. A neighbour was mid-save. `_defined_in` parsed any file the
sweep met and let `SyntaxError` out, so a live citation would have been reported as dead.

| field | value |
|---|---|
| change | `tools/test_repo_hygiene.py` -- `UNREADABLE`, a third answer beside "here are its tests" and "there is no such file"; the sweep collects those paths and `warnings.warn`s them instead of counting them as offences |
| why a warning and not silence | a run that met a half-saved file has to be distinguishable from a clean one, or the next reader cannot tell why a count moved |
| red-first | `mutate unreadable_third_answer` (the half-saved file answers `None` again) -> **1 failed**: `assert None is <object …>` |
| naming test | `tools/test_repo_hygiene.py::test_a_suite_file_a_neighbour_is_saving_is_unreadable_and_not_a_dead_pointer` -- it builds its own tree under `tmp_path` and points `ROOT` at it, so nothing is written into the repository a neighbour is working in, which is the same reason the defect exists |
| suites run | in the nine-node line above |

## R2 -- the lead's, and I agree with the verifier against my own text

`limits-update-lines.md` says the fourteen OPEN items need `transition <id> TRIAGED` first. The
verifier measured `batch_walk_blockers` and got `[]` for OPEN ids, because that reader's rule is
"status FURTHER than the edge's source", and `OPEN` lies before it. I have not re-measured it and
I do not defend the sentence: **the lead should not run the fourteen transitions on my say-so.**
The paragraph stays in the list as written, with this protocol beside it -- correcting it is a
state question for the lead, not a stream's edit in the last minutes of a rework.

## Runs of rework 2

| run | result | duration |
|---|---|---|
| `tools/test_repo_hygiene.py -q -k "decision_named_in_a_message or every_decision_pointer_in_a_shipped or decision_pointer_reader_can_tell"` | 3 passed | 5.54 s |
| `tools/test_repo_hygiene.py -q -k "suite_file_a_neighbour_is_saving or test_the_test_pointer_reader_reads_the_shapes"` | 2 passed | 0.84 s |
| `tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves` (alone, after the transient) | 1 passed | 71.72 s |
| `tools/test_repo_hygiene.py`, the nine node ids (the EVD run) | 9 passed | 91.26 s |
| `python -m ruff check` over the five changed `.py` files | All checks passed | < 1 s |

## The verification line, rebuilt again

Dry-checked against a store copy inside a checkout: **rc 0, 9 of 9, 0 refused**; the kernel resolves
BUG-0165 to EVD-0391 and BUG-0263 to EVD-0392 by itself.

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory \
  request-approval verification --batch BUG-0008 BUG-0133 BUG-0137 BUG-0165 BUG-0243 BUG-0263 BUG-0274 BUG-0275 BUG-0290
```

| id | hole | EVD |
|---|---|---|
| BUG-0008 | -- | EVD-0358 |
| BUG-0133 | H41 | EVD-0354 |
| BUG-0137 | H45 | EVD-0353 |
| BUG-0165 | H73 | EVD-0391 (supersedes EVD-0377) |
| BUG-0243 | H161 | EVD-0351 |
| BUG-0263 | H181 | EVD-0392 (supersedes EVD-0378, which superseded EVD-0359) |
| BUG-0274 | H190 | EVD-0357 |
| BUG-0275 | H191 | EVD-0356 |
| BUG-0290 | H206 | EVD-0355 |

## COUNTS after rework 2

* **closed: 9**, unchanged in number and one of them (H73/BUG-0165) now closed for BOTH halves of
  its (a).
* **downgraded with a measurement: 8**, unchanged.
* **hole payloads for the lead to capture: 1** --
  `project_memory/staging/TSK-0143/hole-docstring-dec-id.json`. The second payload the order
  allowed for (`hole-shell-literals.json`) was NOT written, because the shell reader was one row
  and is built.
* **handed over, not mine to write: 2** (stream A) plus the user's patch sites.
* **12 EVDs** through the kernel: EVD-0351, 0353-0359, 0377, 0378 (both now superseded), 0391, 0392.

Last clock reading of this protocol: 2026-09-12 12:47:18.

---

# Rework 3 -- the S2 seam cost in my file (verifier A, round 3, F4)

Started 2026-09-12 13:35:37 (clock read), finished 13:52. Of the two documents behind it I read
`project_memory/staging/TSK-0141/s4-gate-commit-evidence-patch.md` WHOLE (84 lines -- it is a patch
and its acceptance, and the question asked was whether it needs anything of mine); of the round-3
report I read only what the lead quoted.

No hole closes here and no EVD is recorded: this is the COST of stream A's S2 change landing in a
file of mine, not a defect of this round's own.

## What broke

Stream A made `--run-command` and `--run-scope` required on `kernel.cli evidence` (BUG-0192 / H108).
`.claude/hooks/test_gates.py` drives that surface as a REAL subprocess, and nine of its ten call
sites did not carry the pair.

Measured before the change, 13:36: `python -B -m pytest .claude/hooks/test_gates.py -q -k commit`
-> **3 failed, 17 passed, 503 deselected, 31 errors in 182.63 s**, every one of them the kernel
refusing the call the fixture makes.

## What changed

| where | what |
|---|---|
| `.claude/hooks/test_gates.py:462-474` | new `REVIEWED_BY = ("--run-command", "git diff", "--run-scope", "selection")`, ONE place for a value nine calls make, with the reason beside it |
| nine argv sites | `:1573, :1597, :1629, :1654, :1672, :1993, :2080, :2566, :6924` (line numbers after the constant) -- each ends `…, *REVIEWED_BY],`. Found by grepping every `"evidence"` argv, not by taking the list in the finding: ten sites, and the tenth (`_record_full_run`, the gate-5 fixture) already carried the pair |
| `test_gate3_remedy_is_executable_and_opens_the_commit`, docstring | corrected, see below |

WHY THAT VALUE AND NOT A PYTEST LINE: these nine are REVIEW verdicts of a working tree at a named
digest. What a reviewer runs to see such a tree is `git diff`, and it covers this one tree -- a
`selection`, never a declared surface. A fixture claiming a full run would be the same lie the gate
it drives exists against.

## Selections

| run | before | after |
|---|---|---|
| `.claude/hooks/test_gates.py -q -k commit` | 3 failed, 17 passed, 31 errors, 182.63 s | **51 passed**, 503 deselected, **235.65 s** |
| `.claude/hooks/test_gates.py -q -k "gate3 or gate5_refuses_a_bare_full_run or declaration_head_with_the_same_cut"` (the wider one: it reaches the `certified_project` fixture at `:6924` and `_record_full_run` at `:7343`, which `-k commit` does not name) | -- | **68 passed**, 486 deselected, **267.94 s** |
| four nodes after the docstring correction | -- | 4 passed, 118.38 s |
| `python -m ruff check .claude/hooks/test_gates.py` | -- | All checks passed |

BOTH SELECTIONS RAN OVER THREE MINUTES (3:55 and 4:27) and the host rule of this item asks for
selections a measured run finishes in under three. Said rather than hidden: each is a single
selection of one file, they were run one at a time, and `-k commit` is the acceptance the S4 patch
itself prescribes -- there is no narrower line that covers the sites. What makes them long is that
every node starts several real gate processes.

## Does S4 need anything of mine beyond the pair? YES, one docstring -- and it is corrected

`test_gate3_remedy_is_executable_and_opens_the_commit` said: "The refusal's own command, run as
printed" and "handed to `kernel.cli evidence` exactly as the text spells it". The argv is BUILT, not
parsed out of the refusal. That was already loose; with the pair added on my side while the gate's
printed remedy does not yet carry it, the sentence became measurably false -- the printed line and
the executed call now differ by exactly those two flags, and nothing in this file notices.

The docstring now says what the test does (the kernel accepts the SHAPE the remedy describes), what
it does not (it does not measure that the printed LINE runs), names the difference, and names the
user patch that closes it. A check that really executes the printed line is the strengthening; it
can only be GREEN after S4 is applied, so it is not built here.

TWO OTHER THINGS S4 NAMES THAT ARE NOT MINE, said so the seam does not fall between stools:

* S4's own patch body (`.claude/hooks/gate_commit_evidence.py`, the remedy text) is the USER's, as
  its header says.
* S4 writes that widening `tools/test_hooks.py::_texts_that_name_the_evidence_vocabulary` to cover
  `.claude/hooks/` "is a change to a file stream C owns". It is NOT: `tools/test_hooks.py` stands
  in this item's `forbidden_scope`. Whoever takes that widening needs an item that allows the file.

Last clock reading of this protocol: 2026-09-12 13:52:24.
