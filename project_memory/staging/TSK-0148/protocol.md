# TSK-0148 -- stream C (tools/, this repo's own tests, docs), PR-0012 "Bug-Null", order 4

Builder: harness-implementer (opus, effort high). Base `5ecf62a` on `feat/harness-v2`, stamp
2026.09.12-6. Started **2026-09-12 23:03** (clock read). Scratch, per the host rules:
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0148/` -- `rig.py` (refuses to run outside its own
directory, reads and writes BINARY), `mutations.py` (every anchor is the text as it stands at
5ecf62a, so a mutation is a revert), `.git`-less copy in `tree/` (synced 23:09).

Neighbours in the same working tree: A (`team-kits/kernel`), B (the three kits, and
`tools/test_hooks.py` -- which carries two of my rows, handed over as seams below).

## Plan, and the way it REJECTED (FR-0084)

Five rows, three of them mine to build (BUG-0295, BUG-0297, BUG-0299), two handed to B
(BUG-0300, BUG-0301), one DEC-first question (BUG-0296), plus a prose file per hole.

**Rejected for BUG-0295: an exception list for the docstring sites.** The narrow way would have
been to let `_dec_citations_in_messages` stop excluding docstrings and to name the four exhibiting
sites (three `guard_memory_budget.py`, `migrate.py`) as known illustrations. It loses because the
exclusion is a PROPERTY the message reader needs (documentation may exhibit an id; that is what
`DEC-2100` is for), so the list would grow with every future illustration and would not cover the
`invoice_intake.py` half at all -- that file's citation is in a docstring of a *template* script,
where a fifth exhibit is one edit away. What the smaller way would not have covered: the pairing
shift itself, which is the mechanism -- any future one-line triple-quoted span, not only the two
sites measured today.

**Rejected for BUG-0299: matching the spelling.** Adding `str(` / `os.path.join(` to the program
word's pattern would have named the third planting form and nothing else. It loses because the
mechanism is "a value the call gets through a NAME", which the reader already resolves for the
argv -- one hop, in one place, is the same rule applied to the other element, and it covers the
program word assembled in any expression, not the two spellings I could think of.

## Seam handoffs -- TWO ROWS FOR B (owner of `tools/test_hooks.py`), both MEASURED here

Written early on purpose (DEC-0102 (4)): `tools/test_hooks.py` is in my `forbidden_scope`, and both
rows below were measured in my rig against a copy of it, so B gets the mutation, the change and the
three results rather than a description. Nothing of this is written in the repository by me.

A THIRD seam went to the **lead** and not to B; it arose while writing the hole prose, so it stands
where it arose -- "SEAM 3", after the rows. It is **done** (read 2026-09-13 00:18).

### SEAM 1 -- BUG-0300 / H216: the stopper reader's distinction is not held by any row

**Where.** `tools/test_hooks.py::test_the_refusal_reader_finds_a_stopper_this_repos_own_gates_spell`
(the synthetic bundle it writes), and the docstring of `_names_that_stop_the_role`.

**The mutation that must go red** (`_cannot_return` back to the first cut, "exits somewhere"):
replace its body

    if not body:
        return False
    last = body[-1]
    ...

by a walk that answers True as soon as ANY statement of the body raises the exit or calls a known
stopper. Measured in the rig with exactly that mutation (23:30): today's test is **1 passed** --
the distinction the docstring rests on is unmeasured.

**The change** (add ONE function to the bundle and ONE call to it, plus two assertions). In the
`write(str(bundle / "gate_probe.py"), ...)` block, before `def decide():`

    "def sometimes(message):\n"
    "    if message:\n"
    "        helper.stop('A REFUSAL ON ONE BRANCH')\n"
    "    helper.note(message)\n"

and inside `decide()`

    "    sometimes('A MESSAGE TO A FUNCTION THAT SOMETIMES RETURNS')\n"

and after the existing `AN ORDINARY MESSAGE` assertion

    assert "A REFUSAL ON ONE BRANCH" in texts, texts
    assert "A MESSAGE TO A FUNCTION THAT SOMETIMES RETURNS" not in texts, (
        "a function that refuses on ONE branch and hands control back on the other is read as a "
        "stopper, so every argument handed to IT counts as a refusal text -- 'cannot return' and "
        "'exits somewhere' are then the same reader, and this bundle is the only place the "
        "difference is measured")

WHY THAT SHAPE: a function carrying an explicit `return` never enters `bodies` at all, so the row
has to be one with NO `return` statement that still falls through -- a branch that stops and an
implicit fall-through beside it. That is precisely the shape `_cannot_return` decides and the
synthetic bundle lacked.

**Measured, three ways** (rig, 23:30):

| state | result |
|---|---|
| the row added, reader as it is | **1 passed** |
| the mutation, test as it is today | **1 passed** (the defect) |
| the mutation + the row | **1 failed**, `assert 'A MESSAGE TO A FUNCTION THAT SOMETIMES RETURNS' not in [...]` |

**AC-2 of the item** (the docstring's `45 vs 3` becomes a pointer): the paragraph "CANNOT RETURN AND
NOT EXITS SOMEWHERE" should name the row above instead of carrying the count -- the numbers belong
in the round's report, and the sentence then rots visibly. The naming duty (DEC-0100) is already
met: the node's first docstring paragraph names `BUG-0192`; B has to add `BUG-0300` there (or give
the row its own node) or the close cannot be clicked.

### SEAM 2 -- BUG-0301 / H217: a computed flag excuses the whole span

**Where.** `tools/test_hooks.py`, in
`test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires`, the branch
`if _COMPUTED_FLAG_RX.search(match.group(1)): ... continue` (7014-7032 at 5ecf62a).

**The change** (the item's first option -- count instead of skip): drop the branch and judge with

    seen += 1
    missing = sorted(required - flags)
    computed = len(_COMPUTED_FLAG_RX.findall(match.group(1)))
    assert len(missing) <= computed, (
        "%s spells an `evidence` call `%s` that omits %s while only %d of its flag names "
        "are built at runtime. `kernel.cli` requires those arguments, so the role is being "
        "told a command line argparse rejects."
        % (where, match.group(1).rstrip(), ", ".join(missing), computed))

The comment that stood in the skipped branch keeps its content (why a template cannot be judged)
and gains the sentence that a computed token buys ONE name and not the span it sits in.

**The mutation that must go red = run (2) of the item**: add a plausible `--%s <kind>` line to the
UNPATCHED remedy of `.claude/hooks/gate_commit_evidence.py` (in a copy), which is the live S4
defect with a computed token beside it.

**Measured, four ways** (rig, 23:28-23:30):

| state of `tools/test_hooks.py` / of the remedy | result |
|---|---|
| today / unpatched + `--%s <kind>` planted | **1 passed** -- the live S4 defect is silenced (the defect) |
| the change / unpatched + planted | **1 failed**, `assert 2 <= 1` |
| the change / unpatched, nothing planted | **1 failed**, `assert 2 <= 0` -- the real defect is still reported |
| the change / S4 patch applied | **1 passed** -- AC-2: `gate_test_scope.py`'s rendered line (two names missing, two tokens computed) stays accepted, no over-refusal |

**Naming (DEC-0100).** This node is RED in the tree until the user's S4 patch (H213), so it cannot
carry the close of BUG-0301. B needs a SEPARATE node that names `BUG-0301` in its first paragraph
and measures the counting rule on a written text (one span with one computed token and two missing
names -> judged; one with two and two -> excused); that node is green today and can be clicked.

## Rows -- ONE line each, as `expected_outputs` asks (detail in the sections below)

| id | change (file:line) | red-first row (arbiter's line) | naming node | suites (selection, duration) | EVD |
|---|---|---|---|---|---|
| BUG-0295 / H211 | `tools/test_repo_hygiene.py:952` `_LONG_STRING_MARK_RX` + `:982` pairing over the blanked copy | `mutate bug_0295` -> `1 failed` `assert [] == ['DEC-0034']` (1.11 s); planted dead id at `dispatch.py:204`: silent with the defect, reported with the repair | `tools/test_repo_hygiene.py::test_a_decision_cited_in_a_one_line_docstring_is_judged` | 14 reading nodes of that file, 26 s (00:2x re-run below) | EVD-0417 |
| BUG-0299 / H215 | `tools/test_repo_hygiene.py:2706` `_with_one_hop`, `:2756/:2760` program word through it, `:2814` `_binds_a_name` | `mutate bug_0299` -> `1 failed`, 2 of 5 named; `mutate bug_0299_bindings` -> `1 failed`, 3 of 5 | `tools/test_repo_hygiene.py::test_the_hook_start_reader_follows_a_program_word_held_by_a_name` | same selection, plus the two naming nodes by node id, 5.6 s | EVD-0418 |
| BUG-0297 / H213 | `.claude/hooks/test_gates.py:1594-1697` `_printed_command`, `_remedy_with_values`, the new node | today `1 failed` (`required: --run-command, --run-scope`); with the S4 patch `2 passed`; patch minus `--run-scope` `1 failed` | `.claude/hooks/test_gates.py::test_gate3_prints_a_remedy_that_runs_as_printed` | `-k "gate3 or claims_in_its_own_prose or pointer_reader_answers or timed_span"`, 69 passed / 1 failed, 170 s | **none, by order** -- red until the user's S4 patch |
| BUG-0296 / H212 | no code: `staging/TSK-0148/dec-question-BUG-0296.md` (the class question) | -- (DEC-first: nothing built, so nothing to make red) | -- | -- | -- (question for the user) |
| BUG-0300 / H216 | seam to B: the missing bundle row + two assertions | mutation `_cannot_return` -> "exits somewhere": today `1 passed`, with the row `1 failed` | B's to add (`BUG-0300` in the first paragraph) | -- | -- |
| BUG-0301 / H217 | seam to B: count instead of skip (`len(missing) <= computed`) | `--%s <kind>` planted beside the unpatched remedy: today `1 passed`, with the change `1 failed` (`assert 2 <= 1`) | B needs a separate green node naming `BUG-0301` | -- | -- |

---

### BUG-0295 / H211 -- a triple quote is ONE delimiter

**Change.** `tools/test_repo_hygiene.py`: new `_LONG_STRING_MARK_RX = re.compile('"{3,}')` beside
`_DELIMITED_RX` (:940-952) and `_dec_citations` (:970) now pairs over a `readable` copy in which
every run of three or more quotes is blanked to spaces of the same length -- offsets unchanged, so
every caller's line computation still points home. Same correction as `_without_fenced_blocks`
(BUG-0263 / H181) and for the same reason: the mark bounds a literal of the SOURCE LANGUAGE, it
does not quote somebody's prose, so what stands between two marks is prose this reader judges.

**Measured, one reader over one corpus** (`probe_docstrings.py tree`, shipped kit `.py` files,
23:12 and 23:13):

| | ids in docstrings | judged | judged by nobody |
|---|---|---|---|
| before (5ecf62a) | 190 | 184 | 6 |
| after | 190 | **186** | **4** |

The four that remain are exactly the deliberate illustrations (three `DEC-2100` in the
`guard_memory_budget.py` docstrings, `DEC-0000` in `kernel/migrate.py:1291`) -- AC-2. The two that
moved are the real citations `kernel/dispatch.py:204` (DEC-0091) and
`office-team/templates/repo/scripts/invoice_intake.py:370` (DEC-0075). Reach over the whole shipped
tree, prose reader: 700 -> **702** citations (`probe_mechanism.py`), i.e. the repair adds those two
and nothing else.

**Red-first, in the rig** (`_round-scratch/TSK-0148`):

* `rig.py mutate bug_0295` (the two `readable` lines back to `text`) ->
  `rig.py run tools/test_repo_hygiene.py -q -k "one_line_docstring or pointer_reader_can_tell"`
  = **1 failed**, 1 passed, 1.11 s: `assert [] == ['DEC-0034']` at
  `tools/test_repo_hygiene.py:1301`.
* AC-1, the item's own repro: `mutate bug_0295_plant` (`DEC-0091` -> `DEC-9142` at
  `team-kits/kernel/dispatch.py:204`, **in the rig copy only**) with the defect present ->
  `-k decision_pointer_in_a_shipped` = 1 passed (silent, which is the defect); the same planting
  with the repair -> **1 failed**: `['team-kits/kernel/dispatch.py:204 DEC-9142']`.

**MECHANISM sweep before the EVD (DEC-0102 (2)).** The mechanism is "the positional pairing
misreads a delimiter RUN". Spellings enumerated and measured: `'''` docstrings (no single-quote
alternative exists in `_DELIMITED_RX`, so they were never swallowed -- after the repair 0 of the
remaining 4 unjudged ids is one), prefixed long strings (`r"""`, `f"""` -- the prefix is not part
of the run, covered), runs longer than three (`{3,}`), long strings that are NOT docstrings (now
judged as well: that is the +2 reach above, and the sweep over the tree stays green), and the same
mechanism one language further -- a PowerShell here-string / shell heredoc, which a line-bounded
reader cannot pair either: **0 DEC ids stand in one anywhere in the shipped tree today**
(`probe_mechanism.py`), so it is bounded, not closed, and it is written down as the residual in
`docs/holes/H211.md`.

**Naming node.** `tools/test_repo_hygiene.py::test_a_decision_cited_in_a_one_line_docstring_is_judged`
(first docstring paragraph names `BUG-0295` / `H211`, so `kernel.naming_tests.names_the_item`
resolves it).

---

### BUG-0299 / H215 -- the bound-name hop on the PROGRAM word

**Change.** `tools/test_repo_hygiene.py`: new `_with_one_hop(node, bound)` (:2611-2626) and
`_starts_a_hook` (:2645-2650) now asks the pattern about the program word THROUGH that hop, instead
of about its bare source text; the argv fallback goes the same way. The docstring paragraph that
described the argv hop now describes the hop as a property of a VALUE HELD BY A NAME and points at
the new test.

**Red-first, in the rig.** `rig.py mutate bug_0299` -- the faithful first version, both lines of the
loop (`word = ast.unparse(element)` ... `search(word)`); the first attempt replaced only the search
and produced a `NameError`, which is a broken copy and not the defect, so the anchor was widened
(23:16). Arbiter `rig.py run tools/test_repo_hygiene.py -q -k program_word_held_by_a_name` ->
**1 failed** in 1.29 s:

    assert ['argv_held_by_a_name', 'program_word_written_out']
        == ['program_word_held_by_a_name', 'argv_held_by_a_name', 'program_word_written_out']

which is exactly the item's "2 of 3 plantings named".

**AC-2, over the running tree** (`probe_hop.py tree`, 23:17): starts that ONLY the program-word hop
sees (argv written into the call, so the old argv hop cannot explain them) -- **4**, and they are
the four live sites the item counts: `tools/test_hooks_v2.py:13537`, `:14600`,
`tools/test_repo_hygiene.py:2682`, `.claude/hooks/test_gates.py:344`. Forgetful starts over both
suite directories after the widening: **0** (with the defect: 0 new sites, 0 forgetful). So the
widening reaches live code and reports nothing new -- no over-refusal.

**MECHANISM sweep (DEC-0102 (2)).** The mechanism is "the call gets the word through a NAME".
Spellings enumerated and measured against the probe module in the test: program word held by a name
(the defect), argv held by a name (already worked), program word written out (already worked),
program word wrapped in a call (`str(program)`, covered -- the hop walks the expression, not just a
bare `ast.Name`), and the counter-direction the hop could have broken: a start whose PROGRAM is not
a hook while a hooks path stands among its arguments (`['cmd', '/c', 'mklink', ...]`, a real false
alarm of this reader) -- stays silent. NOT covered and named rather than claimed: a name bound from
another name (one hop by construction, `_with_one_hop` says so), and a program word that arrives as
a function PARAMETER -- both report nothing rather than wrongly, and the sweep's floor
(`only_with_the_hop >= 1`) would not notice their absence.

**Naming node.**
`tools/test_repo_hygiene.py::test_the_hook_start_reader_follows_a_program_word_held_by_a_name`.

---

### BUG-0297 / H213 -- the printed gate-3 remedy, executed as printed (STAYS RED)

**Change.** `.claude/hooks/test_gates.py`: `_printed_command` (joins the printed line at its
continuation marks), `_remedy_with_values` (fills a `<placeholder>` by the FLAG it follows and
refuses to invent anything else) and
`test_gate3_prints_a_remedy_that_runs_as_printed` -- it refuses a commit in a copy of the stand-in
project, parses the remedy out of the refusal, runs it through a REAL bash (`shutil.which("bash")`,
skip with a reason where there is none), and asserts the refused commit is open afterwards. The
sibling `test_gate3_remedy_is_executable_and_opens_the_commit` now points at it instead of
describing the gap in prose.

**IT IS RED AND STAYS RED until the user applies the S4 patch**
(`project_memory/staging/TSK-0141/s4-gate-commit-evidence-patch.md`) from a shell outside Claude
Code; `.claude/hooks/gate_commit_evidence.py` is refused to every role here. Said in its docstring,
said here, and **no EVD claims a close for BUG-0297**.

**Measured, three directions** (rig, 23:19-23:22):

| state of `gate_commit_evidence.py` | node | result |
|---|---|---|
| today (5ecf62a) | `-k remedy_that_runs_as_printed` | **1 failed** in 26.8 s -- `error: the following arguments are required: --run-command, --run-scope`, and the failure message prints the line it ran |
| S4 patch applied in the copy | same, plus the sibling | **2 passed** in 40.6 s |
| S4 patch applied, `--run-scope` line taken out again | same | **1 failed** -- `error: the following arguments are required: --run-scope` |

The third row is AC-2: the arbiter is not measuring today's two flags, it measures ANY required
argument the printed text omits.

---

### SEAM 3 -- FOR THE LEAD: six index rows must become LINKS, or a green test goes red -- **DONE 00:18**

`docs/holes/*.md` is mine, the hole INDEX (`docs/POST_V2_WISHLIST.md`) is the lead's -- and the two
answer to each other: `tools/test_repo_hygiene.py::test_every_hole_is_one_index_row_one_prose_file_and_one_item`
refuses a prose file whose row does not LINK at it (that direction was built in TSK-0126 after nine
rows linked at files that did not exist). Writing the six prose files this order owes therefore
turns that node red until the rows carry the link.

**Measured in the repository, 2026-09-12 23:32** (after writing the six files):

    AssertionError: these prose files exist while their row does not link at them:
    H211, H212, H213, H215, H216, H217

**The edit**, on the six rows at `docs/POST_V2_WISHLIST.md:2514-2520` (H214 is NOT one of them --
no prose file was written for it, and its bare row is correct): replace the first cell `H2nn` by
`[H2nn](docs/holes/H2nn.md)`, i.e.

    | [H211](docs/holes/H211.md) | BUG-0295 | ...
    | [H212](docs/holes/H212.md) | BUG-0296 | ...
    | [H213](docs/holes/H213.md) | BUG-0297 | ...
    | [H215](docs/holes/H215.md) | BUG-0299 | ...
    | [H216](docs/holes/H216.md) | BUG-0300 | ...
    | [H217](docs/holes/H217.md) | BUG-0301 | ...

Nothing else in the rows changes. The same node is the arbiter: it goes green the moment the six
links stand (and it also holds the other three directions -- a link at a missing file, a file with
no row, a row naming another item).

---

### BUG-0296 / H212 -- the class question, and NOT a word added

DEC-first per DEC-0102 (3). **Nothing was added to the reader** -- `kernel/dispatch.py` belongs to
stream A and, more to the point, the rule says the class is decided before the next word. What was
written instead is the question for the user, in plain German, with the measured four-round history
and the price of each answer:

    project_memory/staging/TSK-0148/dec-question-BUG-0296.md

Three answers are laid out: (A) keep reading prose and keep patching words -- comfortable, but four
of four rounds found a gap and THIS one cannot be closed by a word at all, because `der`/`einer` is
ambiguous by form; (B) demand the shaped acceptance and switch the prose reading off -- the class
disappears, at the price of more expensive runs and an unmeasurable-from-here number of existing
acceptance lines losing the cheap rung (this repository does not dispatch, so that count lives in
the installed projects and is named as open rather than estimated); (C) keep reading prose but grant
the EXPENSIVE rung wherever the reader cannot decide -- the danger direction flips from quality to
money **for rounds 3 and 4 only**, measured in rework 1 below; the sentence that stood here ("would
have defused all four retroactively") was wrong and is corrected there. No recommendation is given,
and the two measurements that would make one possible are named instead.

One thing measured for the question rather than assumed: the reader ALREADY has a shaped feed --
`acceptance_is_test_shaped` first asks whether `expected_outputs` names a test artefact and only
then reads sentences. Answer (B) is therefore "drop the second feed", not "build a new one".

---

## COUNTS (honest)

* **closed with an EVD: 2** -- BUG-0295 (EVD-0417), BUG-0299 (EVD-0418).
* **built and deliberately RED: 1** -- BUG-0297; no EVD, no close claimed. It goes green the moment
  the user applies the S4 patch, and that is measured in both directions.
* **downgraded with a German sentence: 0.**
* **questions for the user: 1** -- BUG-0296 (the class question, file above).
* **seams handed over: 3** -- **2 to B** (BUG-0300, BUG-0301, both measured here) and **1 to the
  lead** (the six index links). The lead's is **DONE**: read at 2026-09-13 00:18,
  `docs/POST_V2_WISHLIST.md:2514-2520` carries `[H211](docs/holes/H211.md)` and the other five
  (H214 correctly bare, it has no prose file), and the node that refused is green again -- see the
  rework runs. So **2 seams are still open**, both B's.
* **not reached: 0.**

## FOREIGN REDS (a neighbour's in-progress edit, left alone)

* `tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves` -- **1 failed**,
  seven offenders, all in stream B's files: `team-kits/{dev,research}-team/hooks/gate_dispatch.py`
  cite `tools/test_hooks.py::test_the_fail_classification_is_refused_from_every_writer_but_the_verifying_one`
  and `team-kits/{dev,research}-team/hooks/gate_pipeline.py` plus the three
  `hooks/gate_test_scope.py` cite
  `tools/test_hooks.py::test_a_registration_names_a_window_exactly_when_its_gate_can_outlive_the_default`.
  Measured 2026-09-12 23:35: neither name exists anywhere in `tools/test_hooks.py` right now (grep
  count 0), and the citing lines are NOT in the 23:09 snapshot of the tree -- so B has written the
  pointers and the tests have not landed yet. Nothing of mine is in that list; I changed nothing.
* The hole-index node (`test_every_hole_is_one_index_row_one_prose_file_and_one_item`) is red for
  MY six prose files and is not foreign -- it is SEAM 3 above, and the lead's one edit closes it.

## RUNS (all selections; no stamp, no full run, no commit, no push, no mint)

| what | why this one | result |
|---|---|---|
| `tools/test_repo_hygiene.py -q -k "decision_pointer or decision_named_in_a_message or one_line_docstring or pointer_reader_can_tell or test_pointer_this_repo_writes or pairing_shift or test_pointer_reader_reads or hole_is_one_index_row or docs_prose or docs_wire_reader or running_tree_shows_every_wire or artifact_ref or assertion_in_the_suites or starts_a_hook or reach_reader_tells or program_word_held"` | the suite of the file I changed, narrowed to the readers of what I touched: the DEC pointer group, the test-pointer sweep and the hole index (they read `docs/**`, where my six new files landed), the artifact-ref reader (the EVDs point into `staging/`), the static-assertion reader (it reads my new assertions) and the hook-start group | **2 failed, 14 passed, 108 s** (23:33-23:35) -- one foreign, one = SEAM 3 |
| `tools/test_repo_hygiene.py::test_a_decision_cited_in_a_one_line_docstring_is_judged` + `::test_the_hook_start_reader_follows_a_program_word_held_by_a_name` | the two naming nodes, run as the EVDs record them | **2 passed, 47 s** (23:41) |
| `.claude/hooks/test_gates.py -q -k "gate3 or claims_in_its_own_prose or pointer_reader_answers or timed_span"` | the suite of the second file I changed: the whole gate-3 group (my new test sits in it), plus the three readers that judge THIS file's own prose -- a backticked test name must resolve (`_points_into_this_file`), a claimed check must exist, a timed span may not pay for a clock-reading helper | **1 failed, 69 passed, 170 s** (23:37-23:40) -- the one failure is BUG-0297 by design |
| `python -m ruff check tools/test_repo_hygiene.py .claude/hooks/test_gates.py` | the two changed Python files | **All checks passed** (23:40) |
| dry check of the batch line, `dry_check_lines.py` against the store COPY in `tree/project_memory` (synced 23:42) | the order asks for a copy inside a checkout; nothing of the canonical store is opened, not even read | **1 line, 2 ids, refused 0** |

NOT run, with the reason: `tools/bump_kit_version.py` and `tools/validate.py` -- no file under
`team-kits/` was touched by me (the only kit file I mutated lives in the rig copy), and the stamp
belongs to the goal round, not to a stream; the full run likewise (`DEC-0050`, gate 5).

## THE BATCH LINE FOR THE LEAD

    PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory request-approval verification --batch BUG-0295 BUG-0299

Dry-checked through the reader `request-approval` asks first
(`kernel.approvals.batch_walk_blockers`): 2 ids, **refused 0**.

## Last clock reading: 2026-09-12 23:43

---

## SELF-REVIEW PASS (the defect the correction introduces) -- clock 2026-09-12 23:45

Went looking for the gap my own repair opens, in the two places a verifier attacks first.

**BUG-0299, the binding SPELLING.** The hop resolves a name out of a map that was built from
`ast.Assign` alone -- so `program: str = os.path.join(...)` (annotated) and `if (program := ...)`
(walrus) bind a name this reader does not see, and the repair I had just written would have covered
the spelling I happened to use. Fixed at the definition instead of at the list: `_binds_a_name`
answers for all three spellings Python has for binding one name to one expression, and the two new
forms stand in the probe module of
`tools/test_repo_hygiene.py::test_the_hook_start_reader_follows_a_program_word_held_by_a_name`
(five forms and the counter-form now).

Measured, two mutations, each with its own signature (rig, 23:46):

| mutation | arbiter |
|---|---|
| `bug_0299_bindings` (`_binds_a_name` back to "only a plain assignment binds") | **1 failed** -- 3 of 5 named, the annotated and the walrus form vanish |
| `bug_0299` (the program-word hop removed) | **1 failed** -- 2 of 5 named, exactly the item's measurement |

Over the running tree the widening changes nothing: **4** starts seen only through the program-word
hop, **0** forgetful (`probe_hop.py`, 23:46). The four line numbers moved between 23:17 and 23:46
(`tools/test_hooks_v2.py:13537 -> :13626`, `:14600 -> :14689`) because a neighbour is editing that
file; the sites are the same four.

`EVD-0418` was recorded at 23:41, before this extension. Its run command is the node above, and the
node was re-run in the repository at **23:47 -> 2 passed** together with BUG-0295's, so the record
still says what happened -- noted here rather than left for the reader to wonder about.

**BUG-0295, the other delimiter spellings.** Enumerated and measured: `'''` (no single-quote
alternative exists, so those bodies were never swallowed -- and none of the 4 remaining unjudged ids
is one), prefixed long strings, runs longer than three, non-docstring long strings (the +2 reach),
and the multi-line delimiters of the shell languages (0 ids today, written down in `docs/holes/H211.md`
as the residual). ONE behaviour change I did not have to make and am naming anyway: an id a one-line
docstring exhibits inside a `'…'` span is now REPORTED, because a possessive apostrophe cannot be a
delimiter in this corpus (`_DELIMITED_RX` says why, and that decision is older than this round). No
such site exists in the shipped tree -- the sweep is green -- and the direction is the harmless one:
a false report, with "delimit it" as the remedy the reader already prescribes.

## RUNS after the self-review pass

| what | result |
|---|---|
| `python -m ruff check tools/test_repo_hygiene.py` | **All checks passed** (23:46) |
| the two naming nodes by node id, in the repository | **2 passed, 5.6 s** (23:47) |
| `tools/test_repo_hygiene.py -q -k "<the 14 reading nodes, the two known reds excluded>"` | **14 passed, 26 s** (23:47) |
| the two known reds re-read: `-k "test_pointer_this_repo_writes or hole_is_one_index_row"` | **2 failed** -- the pointer sweep now names **8** team-kits sites (was 7 at 23:35: B is still writing), none of them mine; the hole index is SEAM 3 |

`.claude/hooks/test_gates.py` was not touched again after its run at 23:37-23:40, and nothing in
this pass reaches it.

## Last clock reading: 2026-09-12 23:49

---

# Rework 1 -- against verify round 1 (FAIL: B1 B2 text; B3 B4 remainders)

Report read at the four rows it names, not whole (`staging/TSK-0148/verify-round-1.md`, sections
"Befunde" and "Negativbefunde"). All three mechanisms were confirmed by the verifier and **no code
behaviour changed in this rework** -- the two blocking findings are claims my text made and the
running code does not build.

## B1 | `_binds_a_name` claimed "the three spellings Python has" -- narrowed, remainder named (00:14-00:17)

**Reproduced first, in my own rig** (`probe_bindings.py tree`, 00:14) -- five probe functions, each
starting a hook with no project of its own:

    reported: ['bound_by_an_augmented_assign', 'bound_twice_last_one_is_the_hook']
    silent:   ['bound_by_a_with', 'bound_by_a_for', 'bound_twice_last_one_is_harmless']

So `with helper(...) as program:` and `for program in [...]:` are silent (the dangerous direction of
BUG-0280), and with a name bound twice the LAST binding wins in both directions -- a real hook start
goes unseen, a harmless one is reported.

**WHAT I DID: narrowed the sentence and named the remainder** (the verifier's minimal fix), rather
than widening the binder. Two reasons, both measured or structural:

* `with X as p` and `for p in X` do not bind `p` to the VALUE of `X` -- they bind it to something
  derived (the context manager's result, an element of the iterable). Folding them into
  `_binds_a_name` would make that helper's own name false; reading them as a TEXT HINT is a second
  relation, and two relations under one name is how the next round's defect gets written.
* Widening is not free. `probe_widened.py tree` (00:15), the shipped sweep with `with`/`for` added
  to the binder: findings over both suite directories **0 -> 1**, and the one is a **false alarm** --
  `tools/test_hooks_v2.py:13964` (`test_trust_cannot_be_reset_by_re_running_the_recorder`), where a
  `for`-bound argument list `["--kit", "hooks/.."]` reaches the ARGV branch while the program of
  that line (`write_kit_state.py`) is no hook at all. Read at the site to judge it, not inferred.
  **0 real misses in the tree today.**

Changed: `tools/test_repo_hygiene.py:2814` -- "the three ASSIGNMENT spellings", plus a paragraph
naming what does NOT reach the reader and pointing at `docs/holes/H215.md`; `:2955` (the test's
docstring) says the same; `docs/holes/H215.md` replaces the two refuted sentences ("jede
Zusammensetzung abgedeckt", "beide melden nichts statt falsch zu melden") with a table of the five
uncovered forms, their DIRECTION, and the measured reach including the false alarm and the rule that
a later widening touches the program-word branch only.

## B2 | answer C in the DEC question -- the load-bearing sentence was measured false (00:17)

**Re-measured myself** (`probe_answer_c.py tree`, against the running `kernel.dispatch`):

    R1 (BUG-0278, missing word)     names_a_test=False clausal=['niemals'] prepositional=[]
    R2 (correlative)                names_a_test=False clausal=['Weder']   prepositional=[]
    R3 (genitive postmodifier)      names_a_test=False clausal=[]          prepositional=['ohne']
    R4 (BUG-0296, ambiguous)        names_a_test=True  clausal=[]          prepositional=['ohne']
    the red-first formula           names_a_test=True  clausal=[]          prepositional=['Ohne']

C can only fire inside the complement of a PREPOSITIONAL denier, and rounds 1 and 2 carry none --
a missing word yields a confident "no negation", never an "undecidable". **C defuses rounds 3 and 4,
not 1 and 2.** The last line is the second half of the finding: the house's own red-first formula
("Ohne den Fix wird ein Test rot") runs through the very reader C would change, and whether C would
refuse such a sentence **was not measured**.

Rewritten in `dec-question-BUG-0296.md`: the C paragraph now carries the measured table and says in
one sentence that the earlier claim was wrong; the false-alarm cost is written down as UNMEASURED;
and the recommendation is **withdrawn** -- no recommendation is given, with the two measurements
that would make one possible named instead (C's false-alarm rate; B's count of prose-only acceptance
lines in the installed projects). The protocol's own sentence carrying the same claim is corrected
in the BUG-0296 row above. `docs/holes/H212.md` never carried it (checked).

## B3 | the growing number in the assert message

`tools/test_repo_hygiene.py:1310` -- "184 sites the defect did NOT touch" is true for 5ecf62a and
was 216 on the running tree when the verifier read it. Struck: the message now says what the probe
is FOR ("those are the sites the defect did not touch, and losing them would be a repair that breaks
the part that worked"). The number keeps its one place: EVD-0417 and the measured table above.

## B4 | the one-line table and the counts

Filled at "## Rows" above, one line per row with the six columns `expected_outputs` asks for; the
sections below it stay as the detail. COUNTS now says 2 seams to B + 1 to the lead and that the
lead's is done (index rows read at 00:18); the seam section says where the third one stands.

## RERUNS after the rework

| what | why this one | result |
|---|---|---|
| `python -m ruff check tools/test_repo_hygiene.py` | the only file whose code text changed | **All checks passed** (00:19) |
| `tools/test_repo_hygiene.py -q -k "<the same 14 reading nodes>"` | both docstrings and the assert message live there; the selection carries the two naming nodes, the static-assertion reader (it reads the changed message), the docs readers (H215 changed) and the whole hook-start group | **14 passed, 57 s** (00:20) |
| `tools/test_repo_hygiene.py -q -k "hole_is_one_index_row or test_pointer_this_repo_writes"` | the two that were red at hand-in | **1 passed, 1 failed, 89 s** (00:22): the hole index is **GREEN** (seam 3 landed), the pointer sweep is still the FOREIGN red and has shrunk to **3** sites, all `team-kits/{dev,office,research}-team/hooks/gate_test_scope.py:59` citing a `tools/test_hooks.py` node that does not exist -- stream B |
| `.claude/hooks/test_gates.py` | NOT re-run: nothing in this rework touched it, and the reader that walks it from this file (`starts_a_hook`) is in the selection above | -- |

Probes added for this rework, all in `_round-scratch/TSK-0148/`: `probe_bindings.py` (which binding
forms the sweep sees), `probe_widened.py` (what a widened binder would change over the running
tree), `probe_answer_c.py` (where answer C could fire).

**Nothing else changed:** no code behaviour, no EVD, no item transition, no stamp, no full run, no
commit. EVD-0417/0418 stand as recorded; their run commands are the two naming nodes, both green in
the 00:20 selection.

## Last clock reading: 2026-09-13 00:23
