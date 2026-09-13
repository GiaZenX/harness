# TSK-0149 -- AC-5 prepared for the lead

Written by the goal-round builder of PR-0012 (order 4) after the delivery run. Everything below is
measured; nothing here is a state write. Clock at writing: 2026-09-13T06:47:52, sections 1/5/7 rewritten **2026-09-13T07:52:14**
after verification round 1; the exact reading of
every measurement is in `project_memory/staging/TSK-0149/protocol.md`.

---

## 1. The verification batch lines

Every line was dry-checked with `approvals.verification_batch` against a COPY of the real store
placed INSIDE a `git init` checkout beside `tools/`, `team-kits/` and `.claude/`
(`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0149/batch_dry_check.py`, 2754 files) -- the same
reader the confirming edge uses. **0 refused rows**, last run after the new Evidence of this order.

The EVIDENCE ID IS THE READER'S ANSWER, not a typed one: where this order re-measured a defect, the
reader now picks the newer record by itself, and that is the record the user will be shown.

| line | ids | evidence the reader picks | state |
|---|---|---|---|
| A (kernel, TSK-0146) | `BUG-0237` `BUG-0302` | EVD-0440, EVD-0442 | **ready** |
| A + this order's seam | `BUG-0260` | EVD-0443 (this order) | **ready** -- the kernel/hook seam is wired and measured in both directions |
| B (kits, TSK-0147) | `BUG-0153` `BUG-0248` `BUG-0260` `BUG-0298` `BUG-0300` `BUG-0301` | EVD-0438, EVD-0445, EVD-0443, EVD-0444, EVD-0427, EVD-0428 | **ready** |
| C (tools, TSK-0148) | `BUG-0295` `BUG-0299` | EVD-0417, EVD-0418 | **ready** |
| M (this order) | `BUG-0242` | EVD-0448 | **ready** -- read section 5 before clicking: the report exists, the removal is the item's own stated limit |
| A, deferred | `BUG-0253` | EVD-0432 | **NOT ready -- waits on the user's config line (section 3)** |

Commands, one question each (`BATCH_LIMIT` is 10, so B's six and A's two stay separate lines):

    request-approval verification --batch BUG-0237 --batch BUG-0302
    request-approval verification --batch BUG-0260
    request-approval verification --batch BUG-0153 --batch BUG-0248 --batch BUG-0260 \
                                  --batch BUG-0298 --batch BUG-0300 --batch BUG-0301
    request-approval verification --batch BUG-0295 --batch BUG-0299
    request-approval verification --batch BUG-0242

`BUG-0260` appears in two lines above because both A and B closed a half of it; ask it ONCE (the
store refuses the same id twice inside one batch, and two batches naming it would ask the user the
same question twice).

**Why BUG-0253 is not on a line.** DEC-0105's repo half is built and measured -- `ladder.yaml`
stands at the repository root and validates through the kernel's own `_valid_ladder` -- but the
kernel does not READ it here until `project_memory/project_config.yaml` names it, and that line is
refused to every tool call in this repository. Closing BUG-0253 now would claim the order head says
a rung when it still says "keine Angabe". Ask it after the user has applied section 3.

## 2. What waits on the USER, by id

| id | what is waited for | where it is written out |
|---|---|---|
| `BUG-0296` / H212 | a DECISION between three readings of the ambiguous German genitive article; stream C withdrew its recommendation and says why | `project_memory/staging/TSK-0148/dec-question-BUG-0296.md` |
| `BUG-0151` / H59 | a DECISION between A/B/C on what happens when a small project alone on `main` reaches "done" with nobody having checked | `project_memory/staging/TSK-0146/protocol.md`, section "Row 7 -- BUG-0151 / H59" |
| `BUG-0297` / H213 | the S4 PATCH to `.claude/hooks/gate_commit_evidence.py`, applied from a shell OUTSIDE Claude Code (the file is refused to every role in this session) | `project_memory/staging/TSK-0141/s4-gate-commit-evidence-patch.md` |
| `DEC-0105` | one line in `project_memory/project_config.yaml` (section 3) | here |

## 3. The user's config line for DEC-0105, and the patch sites

Both edits are for a shell **outside** Claude Code. Gate 1 refuses `project_memory/**` to every
tool call in this repository, and `.claude/hooks/` to every role; that refusal is the rule working,
not an obstacle to route around.

### 3a. `project_memory/project_config.yaml` -- ONE new top-level line

Insert directly above the `project:` block (the key is `kernel.dispatch.CONFIG_TIER_FILE_KEY`, and
the value is a path relative to the repository root):

    # DEC-0105: this repository carries no scaffold record, so the kernel takes its rungs from the
    # tier file named here. A missing or invalid file keeps "keine Angabe" -- never a guess.
    model_tiers: ladder.yaml

Nothing else in that file changes. Afterwards the kernel derives a pair for the three harness roles
instead of the `absent` line; `ladder.yaml` is already in the tree and already validates
(`tools/test_ladder.py::test_this_repositorys_own_tier_file_is_one_the_kernel_reads_and_names_roles_it_ships`,
green, and red with a `top:` the file does not declare).

### 3b. `.claude/hooks/gate_commit_evidence.py` -- the S4 patch

The remedy this gate PRINTS is not runnable as printed: it omits `--run-command` and `--run-scope`,
which the kernel's `evidence` parser requires. Two nodes are red until it is applied and go green
with it (measured by stream C in three directions):
`tools/test_hooks.py::test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires`
and `.claude/hooks/test_gates.py::test_gate3_prints_a_remedy_that_runs_as_printed`.
The patch text: `project_memory/staging/TSK-0141/s4-gate-commit-evidence-patch.md`.

## 4. Handed back rather than edited: a hole pointer this order may not repair

`.claude/hooks/test_gates.py::test_every_test_a_hole_names_is_one_that_exists` is red, and **not
because of this order** -- proven, not assumed: at base commit `5ecf62a` the file
`tools/test_design_conformance.py` already did NOT contain the name, and `BUG-0221` already carried
it (`git show 5ecf62a:` on both). No stream touched either file this round.

* the archived item `BUG-0221` (H138, `ACCEPTED_EXCEPTION`) has
  `regression_tests: [tools/test_design_conformance.py::test_a_record_is_written_even_when_the_checks_find_something_and_the_sighting_gate_still_opens]`
* no test of this repository answers to that name; the test was renamed in generation 3b (`18f9c24`)
* the name it should carry is the one `docs/holes/H138.md` already names and which exists exactly
  once: `tools/test_design_conformance.py::test_a_draft_with_conformance_findings_is_refused_and_an_undecided_one_is_not`
* THE KERNEL HAS NO DOOR for it, measured on a copy of the store:
  `update_item("BUG-0221", ...)` -> `StateError: no active item BUG-0221 ... a finished item lives
  in the archive rather than among the active ones`

So this is an infrastructure gap to report, not an edit to make. Until it is answered, the gate
suite carries two reds instead of one, and the second one is this.

## 5. `report.stock_rollup`, read after the LAST Evidence of this order

Re-read 2026-09-13T07:51, i.e. after `EVD-0448`. The first cut of this section was read BEFORE that
record and therefore contradicted itself (verifier round 1, F3) -- the numbers below are the ones
the delivered store answers now:

    14 rows, every one with a passing Evidence and an EMPTY `unresolved` list.
    BUG-0153 BUG-0197 BUG-0233 BUG-0237 BUG-0242 BUG-0248 BUG-0253
    BUG-0260 BUG-0295 BUG-0298 BUG-0299 BUG-0300 BUG-0301 BUG-0302

    27 active BUG items, so 13 are NOT in the rollup.

**BUG-0242 (H160) is CLOSABLE BY A CLICK, and this file said the opposite.** The correction, with
what the click would mean: the item is `TRIAGED`, carries `EVD-0448` (`kind: test`, `result: pass`,
naming it), has an empty `unresolved` list and NO acceptance criteria of its own, and
`approvals.batch_closing_types("verification")` is `["BUG"]` -- so a verification approval closes
it, and the dry check above lists it with 0 refusals. What this order could not do is TRANSITION it
(TSK-0149 forbids that); that restriction is on the BUILDER, never on the lead, and the earlier
wording confused the two.

What such a click asserts, so it is not clicked blind: the defect as FILED was that no installer, no
scaffold and no kernel path named the orphaned memory tree at all. `kitupdate.py` now REPORTS it
with path, file count and reason, re-measured after the stamp (4 passed). It still REMOVES nothing,
and that is the item's own recorded `limits` with three measured reasons -- a stated limit, not an
unmet criterion. If the lead reads it as an unmet criterion instead, the honest route is an
exception click rather than a verification one; the difference is a judgement about the item's
scope, and the measurement is the same either way.

The 13 outside the rollup: `BUG-0069` (CI, untouched by order), the ten older ones that carry no
passing test Evidence (`BUG-0105/0110/0111/0115/0139/0151/0161/0264/0272` and `BUG-0296`), and the
two this order is accountable for keeping open -- `BUG-0297` (red by order until the user's S4
patch) and `BUG-0303` (the named remainder of BUG-0237). `BUG-0304` / H219 joins them as of the
verification round: the one-call remainder of H214, filed by the lead and named in the three gates'
own docstrings (section 7).

## 6. Evidence this order wrote

| id | related | scope | what it records |
|---|---|---|---|
| EVD-0443 | BUG-0260 | selection | the DEC-0107 kernel/hook seam, one reader, both directions |
| EVD-0444 | BUG-0298 | selection | the write-and-run rule after both narrowings, all eight refusal shapes intact |
| EVD-0445 | BUG-0248 | selection | the docking-point page brought back to the shipped behaviour |
| EVD-0446 | PR-0012 | **full** | THE delivery run: 5139 passed, 1 failed, 14 skipped, 4574 s. `result: fail`, because the run was not green -- the single red is BUG-0297 |
| EVD-0447 | PR-0012 | **full** | the gate suite as its own run: 553 passed, 2 failed, 2128 s. `result: fail`, the two reds are section 2 (BUG-0297) and section 4 |
| EVD-0448 | BUG-0242 | selection | the stamp-dependent re-measurement, 4 passed |

Neither full-run record claims a pass, and that is deliberate: a `full` PASS is what opens a merge,
and the merge must not open while a gate's own printed remedy does not run. Both reds are named,
both wait on somebody other than this order.

## 7. Two rows this order names for the lead rather than closing

**7a. `H214`'s index row should point at `H219` at the next `migrate-holes --reindex`.** `BUG-0298`
closed the DIRECT-runner mechanism (the file as an operand of a shell, as a dot-source, as the
command word); the one-call remainder is `BUG-0304` / `H219`, and the three kits'
`gate_write_scope.py` docstrings now carry it with all five measured spellings. What this order did
NOT do is write `docs/holes/H214.md`, and the reason is measured rather than preferred: a prose file
whose index row does not LINK at it turns
`tools/test_repo_hygiene.py::test_every_hole_is_one_index_row_one_prose_file_and_one_item` red
(planted in a copy, 1 failed, `['H214']`), and `docs/POST_V2_WISHLIST.md` is the lead's file. So the
prose file and its link belong to the same hand, and that hand is not this one.

**7b. `BUG-0221` / H138** -- section 4 above, unchanged: no kernel door to an archived item.
