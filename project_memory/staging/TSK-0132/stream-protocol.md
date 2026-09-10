# TSK-0132 — G5-3 Office package (PR-0009): stream protocol (round 2)

Worktree `C:/Offline Repos/v2-testbed/_worktrees/g5-office`, branch `g5/office` off `feat/harness-v2`
at `b7f282e`. Scratch only under `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0132/`.
Patch (no VERSION hunks, no repo-`project_memory/` hunks, no CR): `_round-scratch/TSK-0132/stream-office.patch`
— 28 files, `git apply --check --reverse` against the worktree rc 0.
Provisional VERSION stamp: **office-team `2026.09.06-2`**, dev-team and research-team
`2026.09.05-8` (they carry only the shared kernel change of round 1).

Round 1 verdict was **FAIL** (`staging/TSK-0132/verify-round-1.md`): B1–B7 blocking, N1–N7 named.
Round 2 (`verify-round-2.md`) confirmed B1, B2, B3, B5, B6 closed, B4 to five sixths and B7 to
three quarters, and raised R1–R4 blocking with R5–R7 named. This protocol carries all three
rounds; §11 is round 3. AC-1 is finished under **DEC-0082** (the user chose the teachable WORKFLOW).

## 0. VORGEFUNDEN — the predecessor, and one round-1 claim of mine that was not measured

A predecessor agent (Fable, stopped by DEC-0081) worked 2026-09-05 21:11–21:57 and left a green
`tools/test_office_package.py` (32 passed, read 22:12) plus a red-first rig with 20 mutations, all
rc 1. Both were measured before anything was built on them and both were kept.

**A correction to my own round-1 protocol, before anything else.** It said `tools/test_hooks.py` ran
"green (exit 0)". That was **not measured**: the run was piped into `tail`, so the exit code I read
was `tail`'s, and my attempt to grep the summary line returned nothing and I moved on anyway. The
suite is measured now — see §8 — and it was in fact carrying a failure of MY making at that point
(`test_instruction_files_name_only_state_files_a_v2_project_has`, §3, D14). The rule the miss broke
is the plainest one in this repo: a claim is the measurement, never the exit code of a pipeline.

## 1. PLAN — and the way it was rejected (FR-0084 shape)

**Rejected for this round:** answering B1–B7 with the smallest change each (a sentence for B3, four
parametrised cases for B4, five `try/except` for B6). It lost because five of the seven have the
SAME shape — a value read without asking whether it is one, a sentence claiming a protection the
code does not build — and seven local patches would have left the shape intact for the next reader
to hit. What the smaller way would not have covered is precisely what it did cover here: `vat_of`'s
two remaining derived values (D3/D4 of round 1 had closed only the ones the verifier's fixture
reached), the exit-code question B3 raises for FOUR refusals and not the one it names, and the
`level`/`days_after_due` readers B6 does not list.

## 2. Blocking findings of round 1, closed

Mutation names are keys of `_round-scratch/TSK-0132/redfirst_rig.py`; each has its
`redfirst-<name>.log` beside it. All 43 mutations are rc 1 (§6).

### B1 — the intake accepted what its own booking line cannot book, and invented the missing figures

Two answers, because two different things were wrong:

1. **The document's VAT breakdown is read, never derived.** `vat_of` fell back to
   `"standard" if numeric_rate else "exempt"` whenever the document carried no BG-23 — measured by
   the verifier as `rate 0, treatment exempt` on a document stating `tax 40.70`. A document with a
   VAT amount and no breakdown is now refused with all three figures and BG-23 named. The fallback
   survives only where it states nothing the document does not (no breakdown AND no tax).
2. **The verdict never promises a booking the ledger refuses.** The row is now composed as a DICT,
   handed to `ledger_add.validate_row` — the ledger's OWN judgement, imported and not restated —
   and only then rendered into the command line through the one table `ROW_FLAGS`. The verifier's
   first fixture (`19 %` stated with `tax 0.00`) is caught by exactly that: `999.00 * 1.19 =
   1188.81 != 999.00`, in the ledger's own words.
- red-first: `::test_the_intake_refuses_a_document_whose_booking_line_the_ledger_would_refuse`,
  held in BOTH directions — an ACCEPTED document's printed booking line is handed to `ledger_add`
  and taken (rc 0), so a guard that refused everything fails here.
  Mutations `r2-b1-bg23-guard`, `r2-b1-ledger-backstop` → rc 1.

### B2 — the gap refusal printed a way this same script refuses

The old remedy said a cancelled number's "cancellation documents arrive first", which is the one
order `document_type_check` refuses (a 381 on a number no income row carries). The remedy now names
the order the code walks: the cancelled invoice's own 380 first, then its 381.
- red-first: `::test_the_gap_refusal_names_an_order_this_script_actually_walks` EXECUTES both — the
  refused order first (still refused), then the accepted one, end to end to the number that had the
  gap. Mutation `r2-b2-gap-remedy` → rc 1.

### B3 — the contract's exit-code table contradicted the code

Answered as a DEFINITION rather than as the one cell the finding named, and the definition is now
the module docstring's and the contract's: **a no about the DOCUMENT is exit 2, a no about the
PROJECT's own records is exit 1** — the application branches on that number, and an exit 1 is not
worth a retry with a changed document. Four refusals moved to `NotJudgeable` accordingly (the plan
rule count, the unfillable placeholder, the unknown ledger category, two matching ranges), and the
contract page states the rule plus the full case list on both sides.

### B4 — six refusals no test held, four of them literal sentences of the contract

All six now have a case, in one parametrised test that also asserts the exit code B3 defines:
`category_check`, `_fill`, `destination_of`'s rule count, `read_document`'s PDF-without-XML,
`range_for`'s ambiguity, `vat_of`'s mixed rates.
- red-first: `::test_a_project_side_gap_is_not_judgeable_and_a_document_fault_is_refused`
  (7 cases); one mutation per reader — `r2-b4-category-check`, `r2-b4-placeholder`,
  `r2-b4-plan-rule-count`, `r2-b4-range-ambiguity`, `r2-b4-pdf-without-xml`, `r2-b4-mixed-rates` →
  all rc 1.
- **A defect inside the fix, found and closed here:** the first cut of `two_ranges` anchored on
  `number_ranges: []`, which `declare_ranges` has already replaced — the helper planted NOTHING and
  its case passed the untouched fixture through as ACCEPTED. Every planting helper now goes through
  `_plant`, which asserts its own anchor exists. A helper that cannot fail to plant is a test that
  cannot go red, which is the very class B4 reported.

### B5 — AC-4's red-first anchor could not go red

Two separate things, and they are kept separate:
- **The reader defect is inherited and is now an item.** `test_repo_hygiene._CODE_SPAN_RX` pairs
  single backticks running across a whole file, so one code fence blinds it for everything below.
  Re-measured here with a fence-aware reader over the same corpus: **486 citations judged by the
  shipped reader against 525**, i.e. 39 citations in 48 files judged by nothing — and the repair is
  measured to be three citations away from green (the three that surface are named in the item).
  Captured through the kernel as **BUG-0263 (H181)** with that chain.
- **The claim was mine and is withdrawn.** The protocol no longer says the repo-wide test holds the
  AC-4 table. `tools/test_office_package.py::test_every_test_the_field_report_verdicts_name_is_one_that_exists`
  reads the TWO documents this package writes, with fences blanked, and resolves every node id
  through `test_repo_hygiene._defined_in` — parsed, never grepped. It carries a FLOOR per
  document, so it cannot pass on a document whose citations were removed rather than repaired,
  and it says in its own comment that it is a second copy of a definition which closing H181
  deletes.
- red-first: mutation `r2-b5-field-report-pointer` plants a nonexistent test name in
  `docs/office-kit-from-field.md` → rc 1 (the shipped reader stays green on the same plant, which
  is the finding).
- **B5's shape found once more, in my own contract page, and closed.** Measured after the fix
  with `_round-scratch/TSK-0132/probe_kit_citations.py` over every text this package writes: the
  46 citations in the kit texts are all SEEN by the shipped reader and all resolve — but
  `docs/office/invoice-app-docking-point.md` contributed **zero**. Its §6 named nine tests as
  BARE names in their own code spans, and the repo's reader states in its own module comment
  that a citation giving only the NAME stays unread. Nine promises to another project about
  test coverage, checked by nothing. §6 is now written as node ids and is the second case of
  the test above.

### B6 — five tracebacks in `letter_draft.py`, the class this stream had closed in the sister file

One reader, `a_value(text, what, read, shape)`, at every place a number or a date arrives from a
person: `--vat-rate`, `--today`, the ledger row's `doc_date`, `correspondence.yaml`'s `valid_days`,
and the ladder's `level` and `days_after_due` (the last two were not in the finding; `level_of`
replaces four hand-spelled `int(one.get("level") or 0)`).
- red-first: `::test_a_value_letter_draft_cannot_read_is_refused_and_never_crashes` (5 cases,
  each asserting rc 1, no `Traceback`, the field named, empty outbox) and
  `::test_a_ledger_date_the_reminder_cannot_read_is_refused`. Mutation `r2-b6-value-reader` → rc 1
  (6 failed).

### B7 — "invents no fee, no term and no sender" was measured false

Four kit-chosen values stood in a customer letter with the terms removed. The four fallbacks are
gone: `address`, `closing` and `offer.valid_days` are read through `a_term`, which refuses with the
`apply-proposal` route (`TERMS_ROUTE`, written once and printed by every refusal about that
document); a ladder step without a `title` is refused. **The fourth value was NOT closed in round 2
and this sentence said it was** — see §11 R1: the argparse `default="19"` stood, an offer run
without the flag still printed the kit's rate, and the named test passed `--vat-rate ""` and therefore
never walked the branch argparse takes when a flag is ABSENT. Closed in round 3. The three sentences
(constitution §5, `skills/correspondence/SKILL.md`, the script's docstring) are now true and each
NAMES the test that holds it.
- red-first: `::test_a_term_the_business_never_recorded_is_refused_with_its_route` (4 cases) and
  `::test_an_offer_states_the_vat_rate_the_business_gave_it_and_no_reminder_goes_to_nobody`.
  Mutation `r2-b7-term-fallback` → rc 1.

## 3. The non-blocking list, and one failure this round produced

| # | What | Done |
|---|---|---|
| N1 | two documents → one filing target, the chain lets the overwrite through | **closed:** the intake refuses a destination that is already taken and names the placeholder that makes the rule unambiguous. The document already AT its destination is not a collision with itself (`--book` re-judges the archived path — the first cut refused its own second run and the suite caught it). `::test_two_documents_never_render_one_filing_destination`, mutation `r2-n1-destination-taken` → rc 1 |
| N2 | "the first attachment ending in `.xml`" is not what the code does | **closed by a property:** an attachment is the invoice when it PARSES as one of the two syntaxes; two of them are refused with both names. The alternative — a table of the file names the norms prescribe — was rejected because it would have to grow per profile and says nothing about a file that carries a prescribed name and something else inside. A missing `defusedxml` now refuses loudly instead of reading as "no e-invoice". `::test_a_pdf_carrying_two_invoice_attachments_is_refused_not_guessed`, mutation `r2-n2-attachment-choice` → rc 1 |
| N3 | "jede Zeile nennt den Test" false for 4 of 9 rows | **closed:** F4 and F5 now name real tests (F5's three `guard_fs_tripwire` tests, F4's two docking-point tests); the closing paragraph says what the table carries — six built points name a test, three absorbed ones name the ITEM that carries their measurement, two rejections carry a reason and no test |
| N4 | BUG-0248/H166 missing from §9 and unnamed at `invoice_intake.py:57` | **closed:** the line reads ``filed as `BUG-0248` (`H166`)`` and §9 below carries it |
| N5 | `series_number` takes what `int()` takes (`1_0` → 10, `٧` → 7) | **closed:** `DECIMAL_RX = [0-9]+`, so the reader is exactly as wide as its own sentence and the contract's "a decimal number". `::test_a_project_side_gap_...[a number the counting part cannot order]`, mutation `r2-n5-decimal-only` → rc 1 |
| N6 | a reminder without a counterparty is written | **closed:** refused, like the missing sender it sat beside. Mutation `r2-n6-recipient` → rc 1 |
| N7 | two more printed `request-approval` sites are placeholders | **named here, no change:** `cli.py:428` (`_line_manifest`'s usage line) and `migrate.py:2817` print FLAG SHAPES (`--key <key>`, `<ID>`), not executable lines — they tell a role which keys a line carries, and `test_the_two_remedies_that_name_no_typed_flag_need_none` covers the two that print a real command. A test executing a placeholder would have to invent the values, and inventing them is what the shape refuses to do |

### D14 — a failure of MY round-1 package, found by the suite I had not really run

`tools/test_hooks.py::test_instruction_files_name_only_state_files_a_v2_project_has` was red:
`skills/correspondence/SKILL.md` sent a role at `project_memory/staging/TSK-0132/dec-correspondence.json`
— a directory of THIS repo that no office project has, and a role told to read one invents it. The
decision is an item now, so the pointer is the item (`DEC-0082`). Green, measured.

## 4. AC-1 under DEC-0082

The user chose the **teachable workflow**. Built accordingly and stated in every text that carries
it: no correspondence role, no preset entry, no model/effort map entry, no ladder rung — and
**what the workflow does not give** (DEC-0082 (3)) is written where a session reads it, not only in
the decision: no second run reads a letter before it leaves (the USER is the second reader) and no
parallel production. Three places say it: constitution §5's correspondence paragraph,
`skills/correspondence/SKILL.md`'s duty list, and `skills/office-manager/SKILL.md`'s letters step.

End to end on a scaffolded pilot, measured: offer, reminder (Mahnung) and customer letter written
from ledger + master data + business profile into `outbox/office-manager/`, each opening with the
line that names the review duty and the user's send; the humanizer bar **measured** on the three
rendered texts (sentence-length spread, no unspaced em dash, no not-only-but-also, no summary
paragraph, one form of address) rather than asserted — `::test_the_three_drafts_pass_the_countable_half_of_the_humanizer_bar`,
mutations `reader-humanizer-emdash` and `reader-humanizer-burst` rc 1. The document route for the
terms is the kernel's (`apply-proposal` / `revise-document`), measured through the entry point.

## 5. Acceptance line per criterion of PR-0009

| AC | Acceptance line | Red-first |
|---|---|---|
| **AC-1** | §4 above: the workflow of DEC-0082, three drafts on a pilot, the review duty named in three texts with its two named limits, the humanizer bar measured, every term read and none invented, every value read or refused | `::test_the_three_drafts_are_written_from_ledger_and_master_data_into_the_outbox`, `::test_the_three_drafts_pass_the_countable_half_of_the_humanizer_bar`, `::test_a_reminder_the_data_does_not_carry_is_refused`, `::test_a_value_letter_draft_cannot_read_is_refused_and_never_crashes`, `::test_a_ledger_date_the_reminder_cannot_read_is_refused`, `::test_a_term_the_business_never_recorded_is_refused_with_its_route`, `::test_an_offer_states_the_vat_rate_the_business_gave_it_and_no_reminder_goes_to_nobody`; mutations `reader-humanizer-emdash`, `reader-humanizer-burst`, `reader-reminder-terms`, `ladder-refusal-without-route`, `r2-b6-value-reader`, `r2-b7-term-fallback`, `r2-n6-recipient` |
| **AC-2** | intake accepts CII XML, ZUGFeRD PDF and XRechnung UBL and moves/books nothing; 14 planted violations refused with the figures; 7 more cases hold the exit-code definition; the booking line is judged by the ledger's own row check before the verdict is printed; the series is ordered by a reader as wide as its sentence; the pipeline after the verdict measured through the REGISTERED hook chain; contract in `docs/office/invoice-app-docking-point.md` updated to what the code does | the AC-2 tests of round 1 plus `::test_the_intake_refuses_a_document_whose_booking_line_the_ledger_would_refuse`, `::test_the_gap_refusal_names_an_order_this_script_actually_walks`, `::test_a_project_side_gap_is_not_judgeable_and_a_document_fault_is_refused`, `::test_two_documents_never_render_one_filing_destination`, `::test_a_pdf_carrying_two_invoice_attachments_is_refused_not_guessed`, `::test_a_series_the_intake_cannot_order_is_refused_and_never_crashes`; 22 mutations |
| **AC-3** | unchanged from round 1 (verifier: PASS): `chart_of_accounts.yaml` with `active: null`, `legal_space: DE`, form year equal to the vocabulary's, 15 categories mapped 1:1 in both frameworks; the booking names its account and refuses 0-or-2 mappings; the report gains `## Nach Konto` and PRINTS a line disagreement; the writer is the generic kernel one | `::test_the_chart_of_accounts_and_the_vocabulary_name_one_form_year`, `::test_the_chart_of_accounts_is_a_kit_document_the_kernel_writes`, `::test_a_booking_names_its_account_and_a_category_the_chart_does_not_map_is_refused`, `::test_the_euer_rollup_reads_the_chart_and_prints_a_disagreement`; mutations `reader-account-one`, `reader-chart-line`, `reader-chart-year`, `chart-account-unanchored` |
| **AC-4** | the verdict table in `docs/office-kit-from-field.md`: six **gebaut** each naming a test, three **aufgenommen** naming the item that carries their measurement, two **abgelehnt** with a reason; the closing paragraph says exactly that instead of claiming a test per row (N3) | `::test_every_test_the_field_report_verdicts_name_is_one_that_exists` — and it can fail: mutation `r2-b5-field-report-pointer` rc 1, on the same plant the repo-wide check stays green for (BUG-0263) |
| **AC-5** | **BUG-0070 and BUG-0071 were built in `f82da60` (TSK-0092), before this stream** — `filing._with_created_rules` and the generic `apply-proposal` route incl. the special-case-vs-general argument with its measured numbers are in `documents.py`'s own header. What this stream adds: the measurement of both through the shipped ENTRY POINT (`scripts/harness.py`), on the shipped document and on an old-stock one, with the booking against the new category and the generated report showing it. Their items still read `status: OPEN` and should be closed against those commits, not against this package | `::test_add_filing_rule_creates_the_rules_list_on_an_old_stock_plan_through_the_entry_point`, `::test_the_bookkeeper_extends_the_category_vocabulary_through_the_kernel_and_books_against_it` (2 ids); mutations `bug0070`, `bug0071` |
| **AC-6** | **BUG-0072 was built in `5c6984d` (TSK-0091), before this stream** (`einvoice_extract.reconciliation_failure`); this stream adds the CII/UBL fields the docking point reads through that same hardened reader, and the attachment-selection fix of N2 — which is BUG-0072's class reached through a file name. **BUG-0079 was genuinely open and is closed here** in both modules, by EXECUTION: the printed line is cut out of the refusal, run through the shipped entry point, and the approval it mints is shown to be the one the command needed. The remaining kernel remedy sites are N7 above | `::test_every_remedy_the_kernel_prints_for_a_document_write_is_a_line_the_kernel_accepts` (3 ids), `::test_the_two_remedies_that_name_no_typed_flag_need_none`, `::test_a_printed_remedy_names_only_the_flags_its_own_line_takes`, `::test_a_pdf_carrying_two_invoice_attachments_is_refused_not_guessed`; mutations `bug0079-documents`, `bug0079-filing`, `bug0072`, `remedy-flags-second-derivation`, `r2-n2-attachment-choice` |

## 6. Reader mutations (DEC-0080 (6))

> **This section is the count as it stood after round 2.** The final one is §12: **53 mutations, 53 logs, every one rc 1**. The eight of round 3 are listed in §11 and the two of the closing round in §12.

**43 mutations, 43 logs, every one rc 1** (counted from `redfirst_rig.py --list` and from the
`redfirst-*.log` files, read 06:39; `r2-b5-field-report-pointer` re-measured 06:45 after the
pointer test was widened to both documents). 20 *(vorgefunden)*, 7 in round 1, **16 in round 2** — one per
reader this round added or changed, which is what duty 7 was partly FAIL for:
`r2-b1-ledger-backstop`, `r2-b1-bg23-guard`, `r2-b2-gap-remedy`, `r2-b4-category-check`,
`r2-b4-placeholder`, `r2-b4-plan-rule-count`, `r2-b4-range-ambiguity`, `r2-b4-pdf-without-xml`,
`r2-b4-mixed-rates`, `r2-b5-field-report-pointer`, `r2-b6-value-reader`, `r2-b7-term-fallback`,
`r2-n1-destination-taken`, `r2-n2-attachment-choice`, `r2-n5-decimal-only`, `r2-n6-recipient`.

The rig now copies `docs/` too, because a judgement of this package is written there and a test of
it reads it. Two anchors of earlier mutations had to be re-cut after the fixes moved their lines
(`reader-credit-original` in round 1, and none in round 2); both were re-measured rc 1.

## 7. Seam table

| Seam file | What this stream writes | Expected at merge |
|---|---|---|
| `team-kits/kernel/cli.py` | one block: `remedy_flags(builder, values)` beside `_line_manifest`; **no new subcommand** | textual merge only |
| `team-kits/kernel/documents.py`, `filing.py` | `quoted_for_a_command_line`; `--reason` in both remedies; `filing.remedy_flags` asking the CLI | reach seam, §8 |
| `office-team/constitution/AGENTS.md` | §5 bookkeeper bullet (chart + docking point, split into two sentences after D9), §5 correspondence paragraph (**DEC-0082**, with the two named limits), §6 two owned documents | §5 is touched by G5-2 as well |
| `office-team/agents/*.md`, `skills/bookkeeper|office-manager|correspondence/SKILL.md` | the duties and the letters step; `office-manager/SKILL.md` names `DEC-0082` | |
| **`DEC-0082` citations** | 4 sites in shipped kit texts | **BLOCKING SEAM:** `tools/test_repo_hygiene.py::test_every_decision_pointer_in_a_shipped_kit_file_resolves` is RED in this worktree because its `project_memory/` is `b7f282e`'s checkout and predates the lead's DEC-0082. Measured against the MAIN repo's store (81 decisions): **65 office-kit DEC citations, 0 unresolved** (`_round-scratch/TSK-0132/probe_dec0082.py`). The merge tree carries both halves; nothing to change here |
| `tools/lead_package_sizes.json` | 56745 → **59369**, five recorded steps, each with a `--note` | RECORD; the journal in `phase0-disposition.md` §10 carries all five |
| `tools/constitution_section_pins.json` | office sections re-pinned across the round, each with a `--note` | RECORD |
| `docs/POST_V2_WISHLIST.md` | L24's place list gains `invoice_intake.py`; the pin moved 7 → 8 with it | |
| `tools/test_kernel.py`, `tools/test_kit_neutrality.py` | the L24 pin; the `chart_of_accounts.yaml:accounts` exception with its own inline tripwire | |
| mirrored files | **none** — office is not mirrored, no dev/research file written | |

**Reach seam (DEC-0080 (1)).** Suites that read the changed kernel functions, all green in §8:
`test_kernel`, `test_staging_cli`, `test_approvals_dispatch`, `test_presets`, `test_state`,
`test_migrate_holes`, `test_hooks` (dev + office + research pilots through the registered chains),
`test_e2e` (dev pilot) and `test_research_chain` (research pilot, both green in the round-1 batch).

## 8. Suites run

| Run (clock read) | Suites | Result |
|---|---|---|
| 05:53 → 06:23 | `test_hooks`, `test_hooks_v2`, `test_kit_neutrality`, `test_role_contracts`, `test_disposition`, `test_shortening_net`, `test_review_procedure`, `test_office_package`, `test_office_duties` | **3338 passed, 13 skipped** / 28:34 |
| 06:33 → 06:39 | `test_kernel`, `test_staging_cli`, `test_approvals_dispatch`, `test_presets`, `test_state`, `test_migrate_holes`, `test_repo_hygiene`, `test_finance_dashboard` | **614 passed, 2 failed** / 5:16 — both explained: the inherited hole-list red (§9) and the DEC-0082 seam (§7) |
| 05:23 → 05:25 | the 16 round-2 mutations | every one rc 1 |
| 06:39 | `tools/validate.py`, `python -m ruff check .` | passed / All checks passed |
| (round 1, 2026-09-05 22:12 – 23:53) | the round-1 batches, the 27 earlier mutations | as recorded in round 1 — with the correction of §0: `test_hooks` was NOT measured then and is measured now |

Host rule kept: one pytest process at a time, every run with a timeout, no CPU-saturating rig.

## 9. What is deliberately NOT closed, and is named

- **BUG-0258 (H176)** — inherited red at `b7f282e`:
  `test_repo_hygiene::test_every_hole_has_a_row_in_the_summary_and_every_row_has_a_hole` asserts a
  floor of 90 `### H` entries in `docs/POST_V2_WISHLIST.md`, which the generation-4 `migrate-holes`
  run emptied. Choosing the check's new corpus is a decision and does not belong inside this package.
- **BUG-0259 (H177)** — the FR-0028 neutrality reader walks only LISTS, so the three scalar terms of
  `correspondence.yaml` still SHIP filled. Round 2 closed the other half the verifier separated out:
  the CODE fallbacks that fired when the user removed them are gone (B7), so a shipped default can
  now only be changed, never silently re-invented.
- **BUG-0248 (H166)** — a mixed-VAT invoice (7 % and 19 % on one document) is refused for booking
  with "by hand"; the ledger row carries one rate. Named at `invoice_intake.py:57` by number (N4).
- **BUG-0263 (H181)** — the fence-blinded citation reader, §B5, with its measured repair distance.
- **The three DEC-0082 alternatives are not built and will not be**: no correspondence role, no
  preset entry, no ladder rung. If the user ever changes that answer, the workflow becomes the new
  role's procedure unchanged — that is DEC-0082's own sentence, and nothing here contradicts it.
- **Not measured here:** the dev/research reach was measured in round 1's batch (`test_e2e`,
  `test_research_chain` inside 2256 passed) and not re-run this round; nothing this round touched
  the kernel.

## 10. Wall-clock and budget

> **This section is the reading as it stood after round 2.** The complete one — every stretch, the span, the token readings and what was NOT read — is the (g) row in §12.

- Predecessor (Fable): 2026-09-05 **21:11 → 21:57**, stopped.
- Round 1 (this session): **22:10:03 → 23:58:40**.
- Round 2 (this session): **2026-09-06 05:04:23 → 06:39:52** — 1 h 35 min, of which ~40 minutes
  were pytest wall time.
- Budget: the harness counter read **14.539 M of 15 M remaining** at 06:40, i.e. ≈ **461 k tokens**
  consumed across both rounds by this session. The predecessor's consumption is not measurable here.

## 11. Round 3 — the four blockers of verify-round-2, and its three notes

Round 2 measured B1, B2, B3, B5, B6 closed with its own mutations and re-computed the DEC-0082 seam
(83 decisions, 322 pointers, 0 unresolved). Four findings blocked. All four are closed red-first;
the mutation names are keys of the rig and every log is rc 1.

### R1 — the fourth default stood while three texts said it was gone
`--vat-rate` kept `default="19"` in argparse, so an offer run WITHOUT the flag put the kit's rate
into a customer's letter; `letter_draft.py`'s docstring, this protocol's §2 B7 and the named
test's own docstring all said otherwise, and the test passed `--vat-rate ""` — the empty-string
branch, never the absent one. The default is now `""`, the test runs BOTH shapes, and the three
sentences say what is built (§2 B7 above carries the correction).
- red-first: `::test_an_offer_states_the_vat_rate_the_business_gave_it_and_no_reminder_goes_to_nobody`;
  mutation `r3-r1-vat-default` → rc 1.

### R2 — the new reader was weaker than the one it stood beside
`a_value` caught only `(ValueError, ArithmeticError)`, and `Decimal("NaN")` and
`Decimal("Infinity")` are valid Decimals: measured, `--vat-rate NaN` came back out of `eur()` as a
traceback, `Infinity` as an `InvalidOperation`, and `-19` was **accepted** with "zuzueglich -19 %
Umsatzsteuer" and a total of 81,00 EUR on a 100,00 EUR offer. `money()` had asked both questions
since it was written, and `einvoice_extract._amount` carries the non-finite half of the lesson with
its own measurement — two readers, one question, two answers.
**Now one numeric reader for the file:** `a_number` (readable, finite, negative only where the
caller allows), `a_count` on top of it for whole numbers, `money` = `a_number` plus the cent, and
`a_date` for the one date shape. `a_value` survives as the "can it be read at all" half and says in
its own docstring why nothing calls it directly any more.
- red-first: `::test_a_number_letter_draft_cannot_write_into_a_letter_is_refused` (4 cases);
  mutations `r3-r2-finite`, `r3-r2-sign` → rc 1.

### R3 — "is an e-invoice" was "parses as XML"
A PDF/A-3 may carry further attachments, and an ordinary note attachment beside `factur-x.xml` was
counted as a second e-invoice and the whole document refused — while the contract page promises
the app project that the kit "takes the one that IS an e-invoice". The definition already existed
twenty lines below, in `parse_xml`'s own branches; it is now `EINVOICE_ROOTS`, ONE declaration read
by both.
- red-first: the third case of `::test_a_pdf_carrying_two_invoice_attachments_is_refused_not_guessed`
  (invoice + note → accepted with the invoice's figures); mutation `r3-r3-einvoice-roots`
  → rc 1.

### R4 — the promise held for the dict, not for the line rendered from it
Two halves, and the second does NOT end where the finding suggested:
1. A buyer named `--doc-type` passed `validate_row` (the value is not empty) and then made argparse
   read the VALUE as an option. The row is now rendered as one `--flag=value` token per flag, where
   the value's first character decides nothing.
2. A buyer carrying a double quote cannot be carried by a printed line at all. The finding proposed
   reusing `kernel.documents.quoted_for_a_command_line`; measured, that is the wrong reader HERE
   — it SWAPS an inner double quote for a single one, which its own docstring justifies for a
   free-text REASON and which would have booked a different customer name. So the answer is a
   property, not a better quoting rule: `printable(argv)` renders the line, splits it back the way a
   POSIX shell splits it, and offers it only when the two agree; otherwise the verdict names
   `--book`, which passes no shell at all. The docstring says the round trip is the POSIX one and
   claims nothing about PowerShell.
- red-first: `::test_the_printed_booking_line_books_what_the_verdict_read`, two cases, comparing the
  booked `counterparty` FIELD (a double quote is doubled again by the CSV writer, so a substring
  test over the file would pass for a name the ledger does not carry); mutations `r3-r4-flag-form`,
  `r3-r4-printable` → rc 1.

### The three notes
* **R5** — the missing case: two plan rules for one class. Added
  (`::test_two_plan_rules_for_one_class_are_not_judgeable`), mutation `r3-r5-plan-rule-count`
  (`!= 1` to `< 1`) → rc 1. Its aside is closed too: the remedy now follows the COUNT, because
  telling the reader of a DOUBLE rule to "add the rule" is the opposite of the move it needs.
* **R6** — `BUG-0263` amended through the kernel (`update BUG-0263`): both figure pairs stand in
  `observed` with the convention that separates them (fenced blocks blanked but their surroundings
  read: 486/525/39; fenced blocks excluded from the corpus altogether: 475/529/54), plus an AC-5
  requiring whoever closes it to count once and say which convention. Neither pair is exact.
* **R7** — `1e2` rendered `1E+2 %` into the letter. `plain()` prints a decimal the way a person
  reads it; `::test_a_rate_a_person_wrote_in_exponent_form_reads_as_a_number_in_the_letter`,
  mutation `r3-r7-plain` → rc 1.

### A defect of my own tooling, recorded because it nearly cost the package
A one-shot edit script matched the FIRST line `plan = repo / "project_memory" / "filing_plan.yaml"`
in the suite — which belongs to the BUG-0070 test, not to the new one — and deleted 118 lines
down to the next line that happened to end the same way, taking `LEDGER_HEADER`, `PILOT_PROFILE`
and `PILOT_PLAN` with it. Recovered from `stream-office.patch`, which carries the file as it stood.
The replacement script anchors on a call that occurs exactly ONCE and asserts the span length before
it writes. The rule this broke is the one `_plant` was added for in round 2: an edit that cannot
fail to find the wrong place is an edit nobody can trust.

### Round-3 measurements
| Run (clock read) | What | Result |
|---|---|---|
| 08:18→08:22 | the 8 round-3 mutations | every one rc 1 |
| 08:23→09:07 | `test_hooks`, `test_hooks_v2`, `test_kit_neutrality`, `test_role_contracts`, `test_disposition`, `test_shortening_net`, `test_review_procedure`, `test_office_package`, `test_office_duties`, `test_finance_dashboard` | **3399 passed, 13 skipped** / 43:16 |
| 09:07→09:16 | `test_kernel`, `test_staging_cli`, `test_approvals_dispatch`, `test_presets`, `test_state`, `test_migrate_holes`, `test_repo_hygiene` | **562 passed, 2 failed** / 8:05 — the same two explained reds (H176 inherited, the DEC-0082 worktree seam) |
| 09:16 | `tools/validate.py`, `ruff check .` | passed / All checks passed |

**51 mutations, 51 logs, every one rc 1** (counted 09:16). Patch: 28 files, no VERSION hunks, no
repo-`project_memory/` hunks, no CR, `git apply --check --reverse` rc 0. Office stamp
**`2026.09.06-3`**. `tools/test_office_package.py`: **70 passed**.

## 12. Closing round — V3-1 to V3-3, and the (g) row

Verify round 3 is **PASS** (`staging/TSK-0132/verify-round-3.md`): AC-1..AC-6 and duties 7-9 pass,
R1-R7 measured closed. The verifier also recorded that its own round-2 recommendation for R4 would
have been wrong — `quoted_for_a_command_line('He said "hi"')` returns `He said 'hi'`, so the
customer would have been booked under a name the document never carried. Three non-blocking rests
were named and are closed here.

* **V3-1** — `a_count` says "A whole, non-negative number" and only the non-negative half had a
  case; the verifier's mutation removing the WHOLE check left all 70 tests green. Two cases added
  (a ladder `level: 1.5`, an offer `valid_days: 2.5`), mutation `r4-v31-count-whole` → rc 1.
* **V3-2** — one rendering convention per letter. `plain()` now sets a decimal the way the money
  beside it is set: `zuzueglich 19,5 % Umsatzsteuer: 19,50 EUR` instead of two conventions in one
  sentence. `::test_a_rate_a_person_wrote_in_exponent_form_reads_as_a_number_in_the_letter` carries
  both halves (the exponent of R7 and the comma), mutation `r4-v32-german-percent` → rc 1.
* **V3-3** — the pointer in `skills/correspondence/SKILL.md` now names BOTH tests, and the
  sentence says which half each holds: unreadable as a number or a date, and readable but
  unwritable (a NaN, an infinity, a negative rate).

### (g) The round, measured

**Wall-clock.** Every time read, none extrapolated.

| Stretch | Clock | Worked |
|---|---|---|
| Fable predecessor (stopped by DEC-0081) | 2026-09-05 21:11 → 21:57 | 0:46 |
| Report round (this agent) | 2026-09-05 22:10 → 23:59 | 1:49 |
| Rework 1 (verify round 1: B1-B7, N1-N7) | 2026-09-06 05:04 → 06:47 | 1:43 |
| Rework 2 (verify round 2: R1-R4, R5-R7) | 2026-09-06 08:01 → 09:20 | 1:19 |
| Closing (verify round 3: V3-1 to V3-3, this section) | 2026-09-06 09:39 → 10:34 | 0:55 |
| **worked, this agent** | | **5:46** |
| **span, first item write to close** | 2026-09-05 21:11 → 2026-09-06 10:34 | **13:23** |

Roughly 2 h 20 min of the worked time was pytest wall time (two 40-minute batches, one 43-minute
batch, the kernel groups and the mutation runs).

**Tokens.** Readings of the harness's remaining-budget counter, which counts the whole session, so
a round's figure is a DIFFERENCE between two readings and carries the reading overhead with it. Two
boundaries were read, the others were not, and that is said rather than interpolated:

| Between | Reading | Consumed |
|---|---|---|
| 2026-09-05 22:10 → 23:58 (report round) | 14.957 M → 14.505 M | ~452 k |
| 2026-09-06 05:04 → 10:34 (rework 1 + rework 2 + closing) | 14.500 M → 14.370 M | ~130 k |
| **session total** | 15.000 M → 14.370 M | **~630 k** |

The predecessor's consumption is not measurable from here; its 46 minutes are its own line above.

**Rounds.** Four deliveries by this agent (1 report + 2 reworks + 1 closing) against three
verifications: **FAIL, FAIL, PASS**. Findings closed across them: 7 blocking (B1-B7), 4 blocking
(R1-R4), 10 non-blocking (N1-N7, R5-R7), 3 rests (V3-1 to V3-3), plus 8 defects this agent found in
the vorgefundenen package before any verification.

**Red-first.** **53 mutations, 53 logs, every one rc 1**, each with its own log beside the rig; 20
came from the predecessor, 33 from this agent. Rig: refuses outside its own directory, opens every
file binary, copies `team-kits`, `tools`, `user`, `docs`, `README.md`, `CLAUDE.md` without the
worktree's `.git`. The verifier ran 35 mutations of its own across three rounds.

**Own findings on the own build** — the three this agent found in its own work and reported
before the verifier could:
1. the round-1 protocol claimed `tools/test_hooks.py` ran "green (exit 0)" when the exit code read
   was `tail`'s at the end of a pipe; the suite was in fact carrying a failure of this package
   (§0, §3 D14). Measured properly from then on — the closing suite run writes to a log and
   reports pytest's OWN exit code;
2. a planting helper that anchored on a string the fixture had already replaced, so its case passed
   the untouched document through as ACCEPTED (`_plant`, §2 B4);
3. a one-off edit script that matched the wrong occurrence of a line and deleted 118 lines of the
   suite, recovered from the patch (§11).

**Seams handed over, per file.**

| Seam | What this stream wrote | What the merge owes |
|---|---|---|
| `team-kits/kernel/cli.py` | ONE block: `remedy_flags(builder, values)` beside `_line_manifest`. No new subcommand, no parser change | textual merge with G5-1/G5-2, which add subcommands elsewhere in `build_parser` |
| `office-team/constitution/AGENTS.md` | §5 bookkeeper bullet (chart of accounts + docking point, two sentences), §5 correspondence paragraph (`DEC-0082`, the two named limits), §6 two more owned documents (`chart_of_accounts.yaml`, `correspondence.yaml`) | G5-1 writes the comment-discipline duty and G5-2 the ladder sentences into the same file; only §5 is touched by both |
| `office-team/agents/bookkeeper.md` | `number_ranges`, `chart_of_accounts.yaml`, the docking-point bullet, a second staged document | G5-1/G5-2 may add duty lines |
| `office-team/agents/office-manager.md` | `correspondence.yaml` as a staged document | as above |
| `office-team/skills/office-manager/SKILL.md` | one new section "Letters that leave the house", naming `DEC-0082` and the limits | lead-package size and section pin re-recorded five times, each with a `--note` |
| `office-team/skills/bookkeeper/SKILL.md`, `skills/correspondence/SKILL.md` | the docking-point step; the correspondence procedure | correspondence is a REFERENCE skill, no role owns it (`DEC-0082`) |
| `tools/lead_package_sizes.json` | 56745 → **59369** in five recorded steps | RECORD, not overwrite — `phase0-disposition.md` §10 carries all five with reasons |
| `tools/constitution_section_pins.json` | office sections re-pinned across the rounds | RECORD |
| `docs/reviews/phase0-disposition.md` | parity lines and size-journal lines, appended | append, never rewrite |
| `docs/POST_V2_WISHLIST.md` | L24's place list gains `invoice_intake.py`; the pin moved 7 → 8 with it | both move together or neither |
| mirrored files | **none** — office is not mirrored, no dev/research file was written | nothing to compare |

**MERGE LINES** — what the merge has to do that this stream could not:
1. **`git add -N` in the main checkout.** Seven files are new and only intent-to-add in the
   worktree, which is what makes them appear in the patch and lets `tools/validate.py` see them as
   tracked. When the patch lands they must be added for real:
   `docs/office/invoice-app-docking-point.md`,
   `team-kits/office-team/skills/correspondence/SKILL.md`,
   `team-kits/office-team/templates/project_memory/chart_of_accounts.yaml`,
   `team-kits/office-team/templates/project_memory/correspondence.yaml`,
   `team-kits/office-team/templates/repo/scripts/invoice_intake.py`,
   `team-kits/office-team/templates/repo/scripts/letter_draft.py`,
   `tools/test_office_package.py`. Without it validate reports "hashed into a kit VERSION but not
   git-tracked" for each.
2. **The office stamp is provisional.** `2026.09.06-4` is this stream's; the merge stamps ONCE over
   all streams. The patch deliberately carries no VERSION hunk.
3. **Two red tests that are not this package's**, both re-measured by the verifier:
   `test_every_hole_has_a_row_in_the_summary_and_every_row_has_a_hole` is red at `b7f282e` itself
   (`git show b7f282e:docs/POST_V2_WISHLIST.md` has 0 `### H` entries — BUG-0258 / H176); and
   `test_every_decision_pointer_in_a_shipped_kit_file_resolves` is red only because the WORKTREE's
   `project_memory/` is `b7f282e`'s checkout and predates `DEC-0082`. Against the main store the
   verifier measured 84 decisions, 322 pointers, **0 unresolved** — the merge tree carries both
   halves and the test goes green there. Nothing to change in the patch.
4. **The interface-contract document for the invoice application** (`DEC-0075`) is
   `docs/office/invoice-app-docking-point.md`. That path is what the app project reads: file shape,
   drop location, the exit-code definition, the norm subset, the three marketplace cases separated
   by law, and §6 naming the test that holds each promise. It is a repo document, not a kit
   template — the office kit's own texts point at it by that path.

**Holes** — four, all captured through the kernel with `limits` and a hole number, none of them
prose: `BUG-0248` (H166, mixed VAT on one document is booked by hand), `BUG-0258` (H176, the
hole-list check has no corpus since the generation-4 migration), `BUG-0259` (H177, the neutrality
reader walks only lists, so three scalar terms still ship filled), `BUG-0263` (H181, the citation
reader is fence-blinded; both counting conventions and their figures stand in the item).

**Final package.** Patch `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0132/stream-office.patch`,
**28 files, 270 991 bytes, 0 CR bytes, no VERSION hunks, no repo-`project_memory/` hunks**,
`git apply --check --reverse` rc 0 against the worktree. Provisional stamp office-team
**`2026.09.06-4`** (dev-team and research-team `2026.09.05-8`, carrying only the shared kernel
change). `tools/test_office_package.py`: **72 passed**. Closing suite run 09:52 → 10:32,
written to a log and read from pytest's OWN exit code: **3378 passed, 13 skipped, 2 failed** —
the two of merge line 3. `tools/validate.py` and `ruff check .` pass. No commit, no push, no
install to the global store.
