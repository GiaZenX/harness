# TSK-0147 -- stream B (the three kits), PR-0012 "Bug-Null", order 4

Base commit 5ecf62a (stamp 2026.09.12-6). Scratch (red-first, .git-less copies):
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0147/`.

Clock readings are host-local (`date "+%Y-%m-%dT%H:%M:%S"`), the format `kernel/state.py::_now_iso`
writes.

- 23:03:21 -- start, item read, DEC-0104/0107/0108/0109 read, bugs BUG-0153/0298/0302/0260/0248 read.

## PLAN and the way it REJECTED

**H61 (BUG-0153).** Rejected: put `start_the_deadline` calls into the 45 shipped hooks that have
none (17/27 dev, 13/27 office, 15/24 research, measured 23:06 by an AST/ text scan over
`team-kits/*/hooks/*.py`). That is an enumeration -- every hook added later starts unbounded again,
and it would not have covered `format_on_write`/`notify_agent_events`, which never import `_kernel`.
Built instead: ONE home in `_compat` (which every shipped hook imports and whose `load()` every
shipped hook calls -- measured, 0 hooks without it) plus the settings half. What the smaller way
would not have covered: a hook that never imports `_kernel` at all.

## Rows

### BUG-0153 / H61 -- every kit hook notices its window (2 halves, in this order)

- **Change (settings half).** `team-kits/{dev,office,research}-team/settings/settings.json`: a
  `timeout` on every entry -- 30 / 30 / 27 added, 2 kept (dev+research `gate_pipeline` 1800).
  Measured before: 1/31, 0/30, 1/28 = **2 of 89**. Value 120 s is DERIVED, not chosen: the chain's
  own child bounds (AST, `timeout=` keywords) plus the budget one hook process gives itself
  (`_compat.HOOK_DEADLINE_SECONDS` = 60) -- worst shipped case besides `gate_pipeline` is
  `format_on_write` at 60+60 = 120. The window rule comment of each file was rewritten; the
  sentence "nothing in `_compat` notices a deadline" was FALSE after the second half and is gone.
- **Change (reader half).** `team-kits/*/hooks/_compat.py` +205 lines: `registered_window`,
  `start_the_deadline`, `hook_file`, constants `DEFAULT_WINDOW_SECONDS` / `DEADLINE_RESERVE_SECONDS`
  / `UNBOUND`; armed from `load()` (the funnel: 0 of 78 shipped hooks read a payload without it).
  `team-kits/*/hooks/_kernel.py`: the construction reduced to a 6-line delegation, so the numbers
  and the sentences have ONE home. Measured occasion: `_kernel` is imported by 10/27 dev, 14/27
  office, 9/24 research shipped hooks -- the other 45 had no bound at all.
- **Red-first** (rig `redrig.py`, copy `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0147/red`,
  .git-less, refuses to run outside its own directory, explicit newline policy):
  - `defect h61-reader` (the arming call removed) -> the real hook process
    `guard_no_adhoc.py` returns **rc 0 with empty stderr** under a window of 1.5 s; with the fix
    **rc 2** "not enough time". 3 failed / 1073 deselected, 5.67 s.
  - `defect h61-windows` (the 87 windows dropped) ->
    `test_every_registration_names_a_window_its_gate_can_answer_inside` red on every entry.
- **Naming node.** `tools/test_hooks.py::test_a_hook_that_never_imports_the_kernel_is_bounded_by_its_window_too`
  (3 cases, one per kit) + `::test_every_registration_names_a_window_its_gate_can_answer_inside`
  + `::test_a_registration_that_names_a_gate_without_a_window_refuses_every_call_of_it`
  + `::test_a_gate_no_registration_names_falls_back_on_the_measured_default_window`.
- **Suites.** `tools/test_hooks.py -k "window or deadline"` 15 passed 15.3 s (23:16);
  `-k never_imports_the_kernel` 3 passed 3.7 s (23:17); `tools/test_hooks_v2.py` WHOLE FILE rc 0,
  **15 min** (23:19-23:34) -- over the 3-minute rule, reported rather than hidden: it was started
  as a fallout check before the cost was measured, and it is the only run of this round over it.

### DEC-0107 hook half / BUG-0260 -- who may call a failed run mechanical

- **Change.** `team-kits/*/hooks/gate_dispatch.py`: `_names_the_classification` (mechanism, not
  spelling) + `_refuse_a_classification_the_judged_role_wrote`, called at the head of
  `handle_pre_tool_use`; registered on `PreToolUse(Bash|PowerShell)` in the three settings files.
  The class vocabulary stays the kernel's (`dispatch.QA_CLASS`, `ladder_declaration`).
- **Measurement behind the reader.** argparse accepts every unambiguous PREFIX: 23:36,
  `kernel.cli evidence ... --f mechanical` was ACCEPTED (only the missing required arguments were
  complained about), so a reader matching `--fail-class` alone is answered by `--f`.
- **Red-first.** `defect dec0107-hook` (the call removed) -> the session instance's
  `--fail-class` line is **rc 0, empty stderr**; with the fix rc 2.
- **Naming node.** `tools/test_hooks_v2.py::test_the_fail_classification_is_refused_from_every_writer_but_the_verifying_one`
  (six writers: session instance, judged child, stranger, `--f`, ordinary line, verifying child).
- **Suite.** `tools/test_hooks_v2.py -k refused_from_every_writer` 1 passed 5.6 s (23:38).

### BUG-0298 / H214 -- a line that WRITES a script and RUNS it in one call

- **Change.** `team-kits/*/hooks/gate_write_scope.py`: `_refuse_a_script_this_line_writes_and_runs`
  over the WHOLE line (the write and the run may sit in different pipelines), plus
  `_compat.runs_the_file_it_is_handed` -- the vocabulary `_SHELL_NAMES` already held, made public so
  a third reader does not grow a third list. The rule is the PAIR, not the heredoc: any file this
  line writes and hands to a shell.
- **Red-first.** `defect h214` -> `cat <<'EOF' > run.sh ; bash run.sh` **rc 0, empty stderr** in all
  three kits; with the rule rc 2. `cat <<'EOF' > notes.md` alone stays rc 0 (AC-1's second half),
  and `bash tools/ci.sh` stays rc 0.
- **AC-2** (the multi-line form) is named as the H11 remainder in the rule's own docstring, with its
  bound -- not claimed closed.
- **Naming node.** `tools/test_hooks.py::test_a_line_that_writes_a_script_and_runs_it_is_refused_in_every_kit`
  (3 cases). Suite: 3 passed 6.2 s (23:42).

### DEC-0108 / BUG-0248 (H166) -- the mixed-VAT document

- **Change.** `einvoice_extract.py`: BT-116 per category (`tax_basis`, CII `BasisAmount` / UBL
  `TaxableAmount`), read positionally beside BT-95 and BT-117 -- the three are ONE table.
  `invoice_intake.py`: `vat_of` -> `vat_groups`, `_rate_groups` splits on the document's own
  breakdown (never on a derived figure), `judge` builds one row per rate, `book` walks them in order
  and names how many went in if one is refused, the printed line becomes N lines.
  `verdict["booking"]["rows"]` is the whole document; the contract's single-line key `ledger_add` is
  written ONLY for a one-row document -- a missing key is a loud under-booking, the first row under
  that key a silent one. `ledger_add.py`: the duplicate key carries the rate. `euer_report.py`:
  `document_key` (counterparty + invoice number, else the row id) -- the reverse-charge "Belege"
  count and the AfA hint are per DOCUMENT now, which is what keeps the printed sentence "Gemessen
  wird der BELEG, nicht die einzelne Position" true after the split. `tools/finance_dashboard.py`
  counts through the same imported reader, so page and report cannot drift.
- **Red-first / measurement.** `tools/test_office_package.py` case
  "two VAT rates on one document" (rc 2, "carries 2 VAT rates") was the state before; it is replaced
  by the refusal that REMAINS -- a breakdown the intake cannot pair up. The accepted case is a real
  mixed invoice (100.00 at 19 % beside 200.00 at 7 %, header net 300.00 / tax 33.00 / gross 333.00,
  so BR-CO-14 and the reconciliation are silent): two rows, rates 19/7, nets 100.00/200.00, grosses
  119.00/214.00, one invoice number, no `ledger_add` key, both rows booked rc 0 and
  `ledger_add --validate ledger/2026.csv` rc 0 (no duplicate finding).
- **Naming node.** `tools/test_office_package.py::test_a_mixed_vat_document_books_one_row_per_rate_under_one_invoice_number`.
- **Suites.** `tools/test_office_package.py` 73 passed / 1 failed (foreign, below) 62 s (00:02);
  `tools/test_office_duties.py` 38 passed 4.3 s; `tools/test_finance_dashboard.py` 55 passed 50 s.

### DEC-0104 and DEC-0109 -- the two sentences in the office lead skill

- `team-kits/office-team/skills/office-manager/SKILL.md`: a larger office job is SPLIT INTO TASKS
  and never raised in effort (DEC-0104: this kit keeps no goal item and no goal size, so there is
  nothing to read a size off); and a new section on what the archive's four-eyes wall does NOT bind
  (DEC-0109: tidy-up by template, an inbox overwrite, three named over-refusals -- the price of
  closing them is an approval per rename, which the user declined). Neither file is in the lead
  package (`lead_package.files`: constitution + lead agent file only), so no ceiling moved for them.
- No test: both are prose the user asked for, and a test over a sentence measures the file, not a
  behaviour. What IS measured is that they do not break the pins (`pin_constitution_sections.py`,
  re-pinned) and the package sizes.

### DEC-0107 -- the role texts

- Constitution 11 of dev and research: the claim "the classification does not hold the climb back"
  was TRUE until this round and is now false, so it is replaced by who may write the field and where
  the command stands. Both paragraphs got SHORTER (dev -20 B, research -18 B), so
  `tools/lead_package_sizes.json` records two SHRINKS (see "Scope notes").
- The QA role texts of the three kits carry the command: dev `quality-engineer` SKILL 7,
  research `reviewer` SKILL 4, office `project-auditor` SKILL ("How you record it").
- `hooks/ENFORCEMENT.md` of all three kits: the `gate_dispatch` row names the new shell duty.
- Re-pinned: 7 sections, `tools/constitution_section_pins.json` + the journal in
  `docs/reviews/phase0-disposition.md` (written by the tool, see "Scope notes").

### Seam rows from stream C (both in tools/test_hooks.py, mine to build)

- **BUG-0300/H216.** The synthetic bundle gained `sometimes()` -- no `return`, stops on one branch,
  falls through on the other -- and a call with an ordinary message; two assertions. The "45 names"
  count in `_names_that_stop_the_role` became a POINTER to that row. `BUG-0300` stands in the node's
  first docstring paragraph. Red measured with C's mutation (`_cannot_return` back to "exits
  somewhere"): **1 failed**, the ordinary message read as a refusal text.
- **BUG-0301/H217.** The span-wide `continue` became a COUNT: `_evidence_call_findings` excuses as
  many absences as there are computed tokens. Reproduced C's measurement myself in a complete
  .git-less copy with the `--%s <kind>` planting in the UNPATCHED remedy: old reader **1 passed**
  (the live S4 defect silenced), new reader **1 failed**. The arbiter node stays red for the real
  S4 defect (H213, the user's patch) -- measured red at 5ecf62a too -- so the closing node is the
  new `test_a_computed_flag_name_excuses_one_absence_and_not_the_call_it_stands_in`, green today.
- Dead pointers C reported: repaired. `gate_dispatch.py` x3 now cite `tools/test_hooks_v2.py::`
  (that is where the node lives), `gate_pipeline.py` x2 and `tools/provider_observations.json` cite
  the renamed `test_every_registration_names_a_window_its_gate_can_answer_inside`.

### BUG-0302 -- the hook side: nothing to build, and why

`gate_approval` does not count files: it asks `approvals.open_requests(state)` (gate_approval.py
:284). So the hook stops counting a withdrawn request the moment the KERNEL stops returning it --
that is stream A's half, and the property is already measured from the hook side by
`tools/test_hooks_v2.py::test_an_expired_request_is_not_open_and_a_reworded_relay_goes_silent`,
which is the same mechanism with the TTL. A kit change here would be a second reader of "is this
request still open". Seam row to A below.

## COUNTS (honest)

- **closed, with a naming node and an EVD: 6** -- BUG-0153 (EVD-0425), BUG-0248 (EVD-0430),
  BUG-0260 (EVD-0429, kit half; the kernel half is A's), BUG-0298 (EVD-0426), BUG-0300 (EVD-0427),
  BUG-0301 (EVD-0428). (EVD-0419..0424 are the same six with a `-k` run command; the kernel refuses
  those for a close -- DEC-0100 (3) wants a NODE -- so 0425..0430 are the ones the batch reads.)
- **built without a bug item: 2** -- DEC-0104 and DEC-0109 sentences (their items BUG-0252 and
  BUG-0164 are no longer in `bugs/active/`; the lead closed them as decision/exception).
- **downgraded with a sentence: 0.**
- **questions for the user: 0.**
- **seams handed over: 4** (below).
- **not reached: 1** -- BUG-0248 AC-3's other half, the interface contract page
  `docs/office/invoice-app-docking-point.md` §7, which still states the by-hand limit. `docs/**` is
  my forbidden scope; the exact wording is in the seam row.

## Seam handoffs

1. **To stream A (kernel), one word:** `team-kits/kernel/approvals.py:178` names
   `_kernel.DEFAULT_WINDOW_SECONDS` in a comment. The constant moved to `_compat` with the rest of
   the deadline construction (BUG-0153), so the pointer is dead. Patch: `_kernel.` ->
   `_compat.` in that one line.
2. **To stream A (kernel), a contract:** BUG-0302's hook side needs no kit change *provided* a
   withdrawn request stops being returned by `approvals.open_requests` (deleting the pending file,
   or `pending_request` answering "not open"). If the withdrawal is a FIELD only `sweep-requests`
   reads, `gate_approval`'s note keeps counting it and AC-2 is not met.
3. **To the lead (docs/**, forbidden to me):** `docs/office/invoice-app-docking-point.md` §7 states
   "a document with two VAT rates is booked by hand" -- false since DEC-0108. What it has to say
   instead: a mixed-rate document is accepted and books as one ledger row per rate under a shared
   invoice number; the verdict carries `booking.rows` (a list of command lines, in document order)
   and carries `booking.ledger_add` ONLY for a document that books as one row, so an application
   that reads the single-line key must treat its absence as "several rows"; the refusal that remains
   is a per-rate breakdown the intake cannot read as figures.
4. **To the lead, for the merge:** three suites are red for the MISSING STAMP and nothing else --
   `tools/test_presets.py::test_a_lead_can_change_the_preset_end_to_end` and
   `tools/test_reference_skills.py::test_a_reference_skill_reaches_every_preset_and_not_only_team`
   [bash] and [powershell]. Measured in a pristine copy of 5ecf62a: **3 passed**; in this tree the
   scaffold refuses with "does not hash to the `content:` in its own VERSION". `bump_kit_version.py`
   at the merge is the whole remedy (no stamp was mine to write).

## Foreign reds (left alone)

- `tools/test_office_package.py::test_a_term_the_business_never_recorded_is_refused_with_its_route[no title on the ladder step-plant3-argv3-carries no `title`]`
  -- measured red in a pristine copy of 5ecf62a too (00:02), so it is not this stream's. It turned
  red at the midnight rollover to 2026-09-13: the dunning-ladder step is chosen by days overdue, and
  the fixture's invoice reached the step that HAS a title, so nothing refuses.
- `tools/test_hooks.py::test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires`
  -- red at 5ecf62a (measured) for the unpatched `.claude/hooks/gate_commit_evidence.py` remedy
  (H213, the user's patch, from a shell outside Claude Code). My BUG-0301 change does not alter its
  verdict; the reported call is the real one, now with "0 of its flag names are built at runtime".
- The three stamp-dependent nodes of seam 4 above.

## Scope notes (files I wrote that the item's `allowed_scope` list does not name)

- `tools/lead_package_sizes.json` -- through the sanctioned recorder with a `--note`, and only
  DOWNWARDS (dev 61064 -> 61044, research 62894 -> 62876). `test_context_budget.py::test_the_recorded
  _ceiling_is_the_measurement_and_not_a_typed_number` requires equality, so a shrink has to be
  recorded too. The host rule of this item names the file for the research constitution's ceiling.
- `docs/reviews/phase0-disposition.md` -- BOTH `pin_constitution_sections.py --write` and
  `record_lead_package_sizes.py --write` append their journal line there by construction. I wrote no
  prose in that file.

## RUNS (selections, with durations and clock)

| run | result | when |
|---|---|---|
| `test_hooks.py -k "window or deadline"` | 15 passed, 15.3 s | 23:16 |
| `test_hooks.py -k never_imports_the_kernel` | 3 passed, 3.7 s | 23:17 |
| `test_hooks_v2.py` (WHOLE FILE -- over the 3-minute rule, reported) | rc 0, ~15 min | 23:19-23:34 |
| `test_hooks_v2.py -k refused_from_every_writer` | 1 passed, 5.6 s | 23:38 |
| `test_hooks.py -k writes_a_script_and_runs_it` | 3 passed, 6.2 s | 23:42 |
| `test_office_package.py -k "mixed_vat"` | 1 passed, 3.6 s | 23:51 |
| `test_office_package.py` (whole file) | 73 passed, 1 failed (foreign), 62 s | 00:01 |
| `test_office_duties.py` | 38 passed, 4.3 s | 00:03 |
| `test_finance_dashboard.py` | 55 passed, 50 s | 00:03 |
| `test_role_contracts.py` | 37 passed, 3.4 s | 00:04 |
| `test_model_ladder.py test_parity_sources.py test_context_budget.py` | 63 passed, 1 failed -> fixed by the recorder, 42 s | 00:04 |
| `test_hooks.py -k "window/deadline/script/refusal/computed/registration"` | 23 passed, 22 s | 00:05 |
| `test_hooks.py -k "settings/registered/enforcement/mirror/constitution"` | 32 passed, 29 s | 00:06 |
| `test_hooks_v2.py -k "dispatch or spawn or registered or lease"` | 71 passed, 76 s | 00:06 |
| `test_e2e.py` | 20 passed, 14 s | 00:11 |
| `test_reference_skills.py test_shared_skill_contract.py test_presets.py test_model_pins.py test_kit_neutrality.py` | 68 passed, 3 failed (stamp) , 116 s | 00:12 |
| six closing node ids, as node ids | all passed | 00:10 |
| `python -m ruff check team-kits/ tools/` | All checks passed | 00:09 |

Mirrors: every file under `hooks/` compared by sha256 across the three kits -- the only differing
names are the four `KIT_SPECIFIC_HOOKS` entries (`session_status.py`, `format_on_write.py`,
`document_trays.txt`, `ENFORCEMENT.md`). No stamp, no full run, no commit, no push, no mint, no BUG
transition.

## Batch line for the lead (dry-checked in a store copy inside a checkout, rc 0, 0 refused)

```
python scripts/harness.py request-approval verification --batch BUG-0153 BUG-0248 BUG-0260 BUG-0298 BUG-0300 BUG-0301
```
Dry run at 00:11 in `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0147/batchcheck` (a `git init`
checkout carrying copies of `project_memory`, `team-kits` and `tools`): rc 0, the approving option
lists all six with EVD-0425..0430, nothing refused. The pending request it wrote lives only in that
copy.

**Last clock reading: 2026-09-13 00:18.**

## Late corrections (after the first pass, before the report)

- **The kernel lookup in `_names_the_classification` was made LAZY.** Measured as real hook
  processes, three runs each (00:19): `gate_dispatch` on an ordinary shell line cost **0.25 s** with
  the lookup and **0.15 s** without it -- 0.10 s of kernel import on EVERY shell call of every kit
  project, for a check that concerns one command. The word scan now runs first and the kernel is
  asked only when the line carries a long option at all; a line without one measures 0.12-0.16 s.
  The kernel stays the authority on the field name.
- **Three more dead pointers, found by `test_every_test_pointer_this_repo_writes_resolves`** (the
  sweep C named): `gate_test_scope.py:55-59` in all three kits cited the renamed window test AND
  claimed "NO `timeout` ON ITS REGISTRATION, and that is the shipped rule" -- false in both halves
  after this round. The paragraph now says what the entry really carries and why. Sweep green
  afterwards (1 passed, 82 s, 00:24).
- **Two claims in `_compat`'s own budget comment** said "nothing in this module notices either
  window arriving" and "that is the whole of what reads this constant" -- both false once the
  deadline reader moved in beside them. Corrected; `-k "window or deadline or cap_stays_inside"`
  19 passed, 15 s (00:26).

**Last clock reading: 2026-09-13 00:26.**

# Rework 1 (verifier round 1 = FAIL, 2026-09-13 00:57 -- rework 00:58-01:25)

Read whole: `project_memory/staging/TSK-0147/verify-round-1.md` (125 lines; the cost is named here
because the reading discipline asks for it -- it is the report that directs this rework).

### F1 (blocking) -- BUG-0298/H214 was closed on two spellings, not on the mechanism

- **Change.** `_compat.runs_the_file_it_is_handed` gains the dot-source builtins (`source`, `.`) --
  the shell's own way of running a file without naming a program. `gate_write_scope`:
  `_refuse_a_script_this_line_writes_and_runs` now builds WRITTEN out of every file a
  **write-capable** stage names (its own operands via the new `_operand_words`, plus its redirects),
  where write-capable is `_stage_is_read_only`'s existing fail-closed reading -- so `tee`, `cp` and
  the next tool nobody listed are covered without being listed. A RUNNER's operand is not "written",
  which is what keeps `bash tools/ci.sh` rc 0.
- **Measured, as real hook processes in all three kits (01:03):** the verifier's five rc-0 lines --
  `. run.sh`, `source run.sh`, `. ./run.sh`, a heredoc into `tee run.sh` followed by `bash run.sh`,
  `echo x | tee run.sh && sh run.sh` -- plus `tee … ; sh run.sh` and both original forms: **8 of 8
  rc 2**. Everyday lines rc 0: a heredoc into `notes.md`, `bash tools/ci.sh`, `git status --short`,
  `python -m pytest …`, `cp a.txt b.txt ; cat b.txt`, `echo y | tee log.txt ; grep x log.txt`.
  0 wrong of 42 (14 lines x 3 kits).
- **Red-first with the verifier's own state** (`redrig.py defect h214-firstcut` -- the first cut
  restored: runner vocabulary without the builtins, WRITTEN from redirects only): **3 failed**
  (one per kit), 10.5 s. The docstring's `tee` claim -- house rule 3 -- is now built rather than
  claimed; `python`/`node` are named as the H11 remainder in the same paragraph.

### F2 (blocking) -- `curl --fail` was refused on every shell line

- **Change.** The classification question is asked only on a line that can reach the kernel CLI:
  `_compat.names_the_kernel_entry_point`, and the two spellings (`harness.py`, `kernel.cli`) moved
  to `_compat` because two gates ask now -- `gate_write_scope` aliases them, and the pin against
  `kernel.cli.ENTRY_POINT` moved with them.
- **Measured (01:06):** five everyday `--f…` lines (`curl --fail`, `pytest --failed-first`,
  `git log --format=%h --first-parent`, `docker build --file`, `rsync --files-from=`) x two callers
  (session instance, bound child) -> **rc 0**, in a pilot with a declared kit.
- **Red-first** (`defect f2-firstcut`, the entry-point condition removed): the new node fails.
- **The cost the verifier measured, re-measured after the fix (01:11, three runs each):** an
  ordinary line now **0.10 s** whether or not it carries a long option (before: 0.24-0.30 s for
  ANY long option, which is what the verifier found); only a line that names the harness pays the
  kernel import, **0.18-0.20 s**.

### F3 (closed, not left as a remainder) -- the option the shell assembles

- **Change.** On a line that names the kernel entry point AND the `evidence` command, a word the
  shell builds (`$`, backtick) is UNREADABLE and refused -- the same fail-closed direction
  `gate_write_scope` takes for a word it cannot place. Bounded to `evidence` so an ordinary harness
  line with a `$` in it is untouched; the command word is pinned against the shipped parser by
  `tools/test_hooks_v2.py::test_the_gate_knows_the_command_that_writes_the_classification`.
- **Measured:** the verifier's line with `a="--"; b="fail-class"` and `"$a$b" mechanical` on a
  harness `evidence` call -> **rc 2**, "carries a word the shell builds". Red-first
  (`defect f3-open`): the node fails. The three role sentences now say what is built ("refuses the
  flag from the session instance and from any bound role that is not the judging class", plus the
  assembled-word clause) instead of "from anybody else, the PM included".
- **What stays open and is named in the gate's own docstring:** the wider H11 class -- a line that
  runs a SCRIPT which then calls the kernel.

### F4 (blocking) -- two role texts spelled an `evidence` line argparse rejects

- **Change.** dev `quality-engineer` 7 and research `reviewer` 4 now NAME the flag
  (`--fail-class mechanical`) and point at the item that spells the whole command, the form the
  office auditor text already used. Measured: `tools/test_hooks.py -k evidence_command` is red on
  **exactly one** file, `.claude/hooks/gate_commit_evidence.py` -- the user's S4 site (H213).

### F5 -- the report counted rows as Belege

- `euer_report.group_by_document` is now the ONE place rows become Belege: the open-items table (one
  line per document, gross summed), the stdout count, the AfA hints and the reverse-charge count all
  go through it. Red-first (`defect f5-rows`): "2 open items" and two table lines for one document.
  Naming node
  `tools/test_office_package.py::test_a_mixed_vat_document_is_one_beleg_everywhere_the_report_counts_them`.

### F6 -- the tripwire under "a property of being a hook"

- `tools/test_hooks.py::test_every_shipped_hook_of_this_kit_reaches_the_deadline_that_arms_it`
  registers EVERY shipped hook of a kit without a window and runs it as a process (27/27/24 hooks).
  **A finding of its own on the first run:** `record_booking_reading` and `record_filing_reading`
  ARM the deadline and then swallow the refusal, exiting 0 -- deliberate, their `__main__` says why.
  So the property measured is the ARMING (the sentence), and the exit code is each event's own
  contract; the docstring says that rather than pretending to a rule the recorders break.

### F7 -- number to pointer

- `office-manager/SKILL.md`: "three shapes that are harmless" -> the count stands in `BUG-0164` with
  its measurement, and the sentence points there.

## Rework 1 -- EVDs

| item | new EVD | supersedes | why |
|---|---|---|---|
| BUG-0298 | EVD-0435 | EVD-0426, EVD-0420 | closure was too broad (5 of 8 shapes open) |
| BUG-0260 | EVD-0436 | EVD-0429, EVD-0421 | false alarm (F2) + measured bypass (F3) |
| BUG-0248 | EVD-0439 | EVD-0430, EVD-0422, EVD-0437 | F5; 0437's node did not name the bug where the kernel looks |
| BUG-0153 | EVD-0438 | -- (adds to EVD-0425) | F6's tripwire |

Batch line re-dry-checked at 01:24 in the store copy inside a checkout: **rc 0**, six ids, now bound
to EVD-0438/0439/0436/0435/0427/0428.

## Rework 1 -- runs

| run | result | when |
|---|---|---|
| the 14 F1 lines x 3 kits as real processes | 0 wrong | 01:03 |
| `test_hooks.py::…writes_a_script_and_runs_it…` | 3 passed, 8.8 s | 01:04 |
| `defect h214-firstcut` -> same node | **3 failed**, 10.5 s | 01:05 |
| `test_hooks_v2.py -k "fail_classification or only_looks_like or entry_point or command_that_writes"` | 13 passed, 8 s | 01:06 |
| `defect f2-firstcut` / `defect f3-open` | **1 failed** each | 01:07 |
| `test_hooks.py -k evidence_command` | red on gate_commit_evidence.py only | 01:08 |
| `test_office_duties.py test_finance_dashboard.py` | 93 passed, 46 s | 01:09 |
| `test_hooks.py -k reaches_the_deadline_that_arms_it` | 3 passed, 11 s | 01:11 |
| `defect f5-rows` -> the F5 node | **1 failed** | 01:12 |
| `test_hooks.py -k "window/deadline/script/refusal/computed/registration/reaches/evidence_command/borrows"` | 27 passed, 1 failed (S4, foreign), 35 s | 01:13 |
| `test_hooks_v2.py -k "dispatch/spawn/registered/lease/classification/only_looks_like/entry_point"` | 22 failed at 01:14, **187 passed** at 01:16 on the identical tree | 01:14 / 01:16 |
| `test_office_package.py` (whole) | 74 passed, 1 failed (date, foreign), 59 s | 01:19 |
| `test_role_contracts.py test_context_budget.py` | 79 passed, 29 s | 01:20 |
| `test_repo_hygiene.py::…pointer…resolves` | 1 passed, 83 s | 01:21 |
| four closing node ids | all passed | 01:22 |
| `ruff check team-kits/ tools/` | All checks passed | 01:25 |

Mirrors re-checked after every hook edit: differing names are exactly the four `KIT_SPECIFIC_HOOKS`
entries. Constitution/skill pins re-run after F4 and F7; the lead package sizes are the recorded
ones (the office lead skill is not part of that package).

## Rework 1 -- foreign reds

- **New and transient:**
  `tools/test_hooks_v2.py::test_every_registered_shell_gate_answers_every_spelling_of_a_break_alike`
  -- 22 parametrisations failed at 01:14 and the SAME selection was 187 passed at 01:16 with no edit
  of mine in between. The failing rows all judge a write to `.claude/settings.json` through gates
  that load the kernel; a neighbour's in-progress edit under `team-kits/kernel/` is the reading that
  fits. Left alone, reported here with both measurements.
- Unchanged: the date-dependent office row (`…term_the_business_never_recorded…[no title on the
  ladder step…]`, red at 5ecf62a too), and the S4 arbiter node (H213, the user's patch).

**Last clock reading: 2026-09-13 01:25.**
