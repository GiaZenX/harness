# TSK-0137 — DEC-0097: build class DEFAULT vs FLOOR, checkpoint signals, distribution per effort

Implementer protocol. Base `e0e515f`. One writer. Clock read at start `2026-09-11T10:31:10`, at the
end of the runs `2026-09-11T10:57:25`.

## 0. The way I rejected (FR-0084)

`_valid_ladder` could have normalised `classes:` into a mapping of PAIRS (`{name: {default, floor}}`)
— one key instead of two, and the shape DEC-0097 (1) spells in the file. **Rejected**: three readers
outside this item's `allowed_scope` ask `ladder["classes"][name]` for a *rung* and would then read a
dict — `tools/test_model_ladder.py:250` and `:295`, `tools/test_role_contracts.py:2076`. Two of them
live in a suite this item does not name, so the pair form would have gone red in a suite nobody was
asked to run. What the smaller way would not have covered: nothing — `classes` keeps its old meaning
(the rung a class STARTS on = the default) and `class_floors` carries the value DEC-0097 added, both
produced by one normalisation loop so they cannot disagree.

## 1. File table

| File | What changed |
|---|---|
| `team-kits/kernel/dispatch.py` | `CLASS_PAIR_KEYS`; `_valid_ladder` accepts scalar **and** pair, refuses wrong keys / a non-rung end / an inverted band, emits `classes` + `class_floors`; `acceptance_is_test_shaped` + `_NAMES_A_TEST_RX`; `ladder_for_order` derives default and floor per role and grants an ask below the default only inside the band; `"default"` on the answer; checkpoint line (c) shows default/floor; `CHECKPOINT_QUESTION` carries Anthropic's two signals; N2 reword at the DEC-0096 comment |
| `team-kits/{dev,research}-team/ladder.yaml` | `build: {default: opus, floor: pin}` + the band paragraph (cites DEC-0097 (1), `acceptance_is_test_shaped`) |
| `team-kits/office-team/ladder.yaml` | unchanged values; one paragraph saying the bare rung IS the pair whose ends coincide and why office has no band |
| `team-kits/kernel/report.py` | `lease_distribution` counts per rung AND per effort; one loop per axis-value; line shows both |
| `team-kits/kernel/schemas/session_brief.yaml` | the section comment names both axes |
| three `constitution/AGENTS.md` | the bold ladder statement: opus is the class DEFAULT, floor = the coder's/researcher's pin, a test-carrying ask reaches sonnet; office: every class names one rung, no band |
| three lead `SKILL.md` | the three-line rule gains »sonnet only with a TEST as the acceptance« (office: it needs none, its build class IS the pin) |
| `.claude/agents/harness-verifier.md` | the DEC-0095 (6) reading-discipline block, byte-identical to the implementer's |
| `tools/provider_observations.json` | `run_2` label, **measured** (see §5, correction) |
| `tools/lead_package_sizes.json`, `docs/reviews/phase0-disposition.md` | the three package records raised by `record_lead_package_sizes.py --write` (+420 / +225 / +425 B) |
| `tools/test_ladder.py` | `new_goal`, `_class_spellings`, two new tests, four new mutation rows, `_valid_ladder` reading in the DEC-0095 test |
| `tools/test_light_kit.py` | (c)-line and two-signal assertions, the floor wording for a below-floor ask, the pilot's small-order reason |
| `tools/test_report.py` | rows recut so the effort grouping cannot be the rung grouping; effort assertions |
| `tools/test_role_contracts.py` | the duty tripwire gains the verifier file and byte-equality of the two repo role texts |
| `tools/test_schemas.py` | the sample gains both keys + a new test holding it against the producer |

Three kit VERSION files at **2026.09.11-10** (one stamp per pass, after the last kit change of that
pass; the size record does not enter the hash — the re-stamp reported `unchanged`).

## 2. Red-first rows

Rig: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0137/redfirst.py` — a copy of the tree without
`.git` beside it, refuses any cwd but its own, every file opened with `newline=""`, and each row
restored byte-exact and verified before the next. Log: `redfirst.json` / `redfirst-8-9-10-11-12-13.json`.

| # | Mutation (the state before the change) | Test | Arbiter's line |
|---|---|---|---|
| 1 | dev+research `build:` pair → `build: opus` | `test_an_ask_below_the_default_is_granted_only_for_a_test_shaped_acceptance` | `AssertionError: {'rung': 'opus', ... 'role_class': 'build', ...}` (case (a) came back opus) |
| 2 | `elif acceptance_is_test_shaped(task, root):` → `elif True:` | same | `AssertionError: {'rung': 'sonnet', ... 'role_class': 'build', ...}` (case (b) got the cheap rung) |
| 3 | `elif rungs.index(order_rung) < rungs.index(floor):` → `elif False:` | same | `AssertionError: {'rung': 'sonnet', ... 'role_class': 'qa', ...}` (below the floor was granted) |
| 4 | office `build: pin` → the pair form | `test_both_class_spellings_ship_and_the_scalar_still_means_default_equals_floor` | `AssertionError: ({...}, {'dev-team': ['build'], 'office-team': ['build'], 'research-team': ['build']})` |
| 5 | dev+research pair → scalar | same | `AssertionError: no shipped kit writes a class start as a 'default'/'floor' pair any more ...` |
| 6 | the default-below-floor refusal removed | `test_a_malformed_declaration_names_the_field_it_refuses` | `Failed: DID NOT RAISE DispatchError` |
| 7 | line (c) back to floor-only | `test_the_shipped_spawn_gate_prints_the_four_line_checkpoint_and_never_blocks_on_it` | `AssertionError: CHECKPOINT before builder TSK-0001 starts (DEC-0092 (3)):` |
| 8 | the two signal phrases replaced by "sometimes wrong" / "careless" | same | `AssertionError: ('confidently wrong no matter how much context you give it', "CHECKPOINT before ...")` |
| 9 | `lease_distribution` without the effort axis | `test_the_session_brief_carries_the_lease_distribution_line` | `KeyError: 'efforts'` |
| 10 | the brief sample without the two new keys | `test_the_briefs_distribution_sample_is_the_shape_the_producer_writes` | `AssertionError: assert {'builders_pe...er_rung', ...} == {'builders_pe... 'rungs', ...}` |
| 11 | the duty block deleted from `harness-verifier.md` | `test_every_constitution_carries_the_reading_discipline_duty` | `.claude\agents\harness-verifier.md carries 0 statement(s) of the DEC-0095 (6) reading duty, expected exactly one` |
| 12 | one character changed in the verifier's copy | same | `the two harness role texts carry different copies of the DEC-0095 (6) duty; they agree up to 300 characters, then read:` |
| 13 | `elif acceptance_is_test_shaped(...)` → `elif True:`, **on a scaffolded dev pilot** | `test_the_pilot_rig_leases_three_orders_of_different_size_per_kit` | `assert (['sonnet', 'opus', 'fable'] == ['opus', 'opus', 'fable'] / At index 0 diff: 'sonnet' != 'opus'` |

Every row: green rc 0 before the mutation, rc 1 after, restored byte-exact.

**Row 13 needed a correction, and it is the one worth naming.** The first attempt (in `redfirst.py`)
came back red for the WRONG reason: the pilot installs through the kit's own installer, the installer
refuses a store whose hash does not match its `VERSION`, and `team-kits/kernel/` is inside that hash —
so a kernel mutation alone makes the pilot red for the STAMP. The row above was re-measured with the
mutated copy **re-stamped** first (`row13c.py`), which is what isolates the behaviour. A red that
proves the stamp is not a red-first row.

## 3. Runs (one at a time, timeouts from the measured durations; no full run)

| Suite | Result | Why this one |
|---|---|---|
| `tools/test_ladder.py` | 45 passed, 24.2 s | reads `ladder_for_order`, `_valid_ladder`, the shipped declarations |
| `tools/test_light_kit.py` | 26 passed, 89.1 s | reads the ask derivation, the shipped spawn gate as a process, the pilot |
| `tools/test_report.py` | 126 passed, 52.1 s | reads `lease_distribution` |
| `tools/test_schemas.py` | 30 passed, 0.5 s | reads the brief contract |
| `tools/test_model_pins.py` | 5 passed, 0.7 s | named by the item; nothing there became false, nothing changed |
| `tools/test_role_contracts.py` | 32 passed, 4.0 s | reads the duty tripwire and the lead pins |
| `tools/test_review_procedure.py` | 27 passed, 7.1 s | reads the lead skills (the three-line rule) |
| `tools/test_model_ladder.py` | 13 passed, 9.5 s | **not named by the item** — it reads `ladder["classes"]` and the constitutions' ladder paragraph, both of which I changed (`DEC-0080` rule 2). Item defect, named in §5 |
| `.claude/hooks/test_gates.py -k "spawn or harness_item"` | 7 passed, 36.8 s (541 deselected) | gate 2 re-reads a spawned role's definition and I edited `.claude/agents/harness-verifier.md`; the full surface is the MERGE's and gate 5 refuses it to a stream |

`python -m ruff check tools team-kits` clean; `python tools/validate.py` all structural checks
passed; `python tools/bump_kit_version.py` → 2026.09.11-9 ×3.

## 4. (g) — what this round cost

| | |
|---|---|
| Wall-clock | `2026-09-11T10:31:10` → `10:57:25` for build + runs; the red-first rig and this protocol after it |
| Tokens (my own counter) | ≈ 235 k of the 15 M budget consumed at the end of §3 |
| Rung / effort | opus / high, as the order pins |
| Suites | 8 runs, ≈ 187 s of pytest in total; no full run |

## 5. What I deliberately did NOT close, and named

1. **The test-shaped reader takes the order's WORD.** `acceptance_is_test_shaped` reads a path and a
   criterion text; it never checks that the file exists or that it passes. Deliberate and written in
   its docstring: it decides a RUNG, not a merge, and the same PM who writes the expected output is
   the one who could have skipped the ask entirely. Not filed as a hole — no actor gains anything
   they did not already hold.
2. **The reader does not see a test named without the word.** `unittest`, `checks/`, `spec` are not
   read (measured: `src/x/unittest.py` → False, `docs/latest.md` → False, `tools/test_x.py` → True,
   "ein Test wird rot" → True). Named in the docstring; the remedy is a wider vocabulary, not a list.
3. **`_valid_ladder` compares default and floor only where BOTH are rung names.** `pin` is per role
   and `top` moves with a per-role exception, so an inverted `{default: pin, floor: opus}` is not
   refused at the file — the derivation clamps it instead (`default = max(floor, default)`), so the
   band is lost rather than inverted. Written at the refusal.
4. **`tools/test_model_ladder.py` is in neither `allowed_scope` nor the item's run list**, although
   it reads `ladder["classes"]` and the constitutions' ladder paragraph — both changed here. I ran it
   (green) and changed nothing in it. Item defect, not a scope decision of mine.
5. **`tools/provider_observations.json` residue 8 was WRONG in TSK-0136 and is corrected here, with a
   measurement.** That protocol inferred "20.9 s is presumably API time" from the 31 s window. The raw
   record still exists (`.../TSK-0135/experiment/arm-b/probe-20260911-081402.jsonl`): `duration_ms
   20892`, `duration_api_ms 19329`. So 20.9 s is WALL-CLOCK and 19.3 s is the API time. The label now
   says exactly that, in run_1's form. The item asked for the label »wall-clock (API)« — that is what
   it got, but with the numbers read rather than assumed.
6. **`tools/test_model_pins.py` was in scope and needed nothing.** Its docstring makes no claim this
   round falsified; I left it untouched rather than editing a file to satisfy a list.
7. **The office ladder is a kit file and DID change** — one comment paragraph, no value. It therefore
   carries the new stamp like the other two; its behaviour is asserted unchanged by the office half of
   `test_an_ask_below_the_default_is_granted_only_for_a_test_shaped_acceptance`.
8. **Reading discipline (DEC-0095 (6)):** no file was read whole. Read by named section or end lines:
   `TSK-0137.yaml` (whole item — it IS the order), `DEC-0097` (whole item, 52 lines), FR-0091
   `summary.md` §1–3, `research-A-anthropic.md` §3, `TSK-0136/protocol.md` §6, and named line ranges
   of the eight code/text files above.

## 6. Patch

```
git diff e0e515f
```

24 files under `team-kits/`, `tools/`, `.claude/`, `docs/` (≈ +502 / −83); `git status` additionally
shows the kernel's own writes under `project_memory/` that were present at the base — untouched,
including the three untracked `evidence/EVD-0098..0100.yaml` written at 10:24–10:25, before this
round started.

## 7. EVD lines for the lead (state-relative refs)

```
capture EVD --kind test --result pass \
  --summary "TSK-0137 after the round-1 rework: eight reading suites green on the stamped tree (test_ladder 48, test_light_kit 26, test_report 126, test_schemas 30, test_model_pins 5, test_role_contracts 32, test_review_procedure 27, test_model_ladder 13); ruff and validate.py clean; kits at 2026.09.11-10" \
  --refs "staging/TSK-0137/protocol.md#3-runs-one-at-a-time-timeouts-from-the-measured-durations-no-full-run" --related TSK-0137
```

```
capture EVD --kind review --result pass \
  --summary "TSK-0137 red-first: 22 rows over two rigs, each green rc 0 before the mutation and rc 1 after, restored byte-exact; row 13 measured on a scaffolded dev pilot after re-stamping the mutated copy; row 16 was green on its first attempt and the denial guard got the two rows only it refuses" \
  --refs "staging/TSK-0137/protocol.md#2-red-first-rows" --refs "staging/TSK-0137/protocol.md#83-red-first-rows-of-the-rework" --related TSK-0137
```


---

## 8. Rework after verify round 1 (11:13–11:24)

The verifier's report file `project_memory/staging/TSK-0137/verify-round-1.md` **was not on disk**
when I looked (only `protocol.md` in that directory), so B1 and NEU are taken from the
coordinator's message verbatim and not read from the report.

### 8.1 B1 — the reader read a WORD, now it reads a TEST

`acceptance_is_test_shaped` is three readers instead of one regex, and the property is *a test is a
thing that is run and yields a verdict*:

* `_path_names_a_test` — a component that IS `test`/`tests`, or a basename matching the module
  convention `_TEST_MODULE_RX` (`test_x.py`, `x_test.go`, `x.test.ts`, `x_spec.rb`). A separator
  after or before the word is what every runner's convention shares and what a document title does
  not have, so `docs/test-plan.md` and `docs/testimonials.md` fail it.
* `_sentence_names_a_test` — per SENTENCE (`(?<=[.!?;])\s+`, the shape of
  `tools/test_hooks.py::_team_size_questions`): refused outright when `_DENIES_RX` fires in that
  sentence, otherwise granted for a runner (`_RUNNER_RX`), a test path, or the standalone word plus
  a verdict from `_VERDICT_WORDS`.
* `acceptance_is_test_shaped` — expected outputs through the first, the referenced criteria through
  the second.

`_VERDICT_WORDS` is the ONE enumeration and is held at both ends by
`test_the_acceptance_reader_needs_a_verdict_word_and_every_listed_one_earns_its_place`: it reads
the vocabulary off the module, rebuilds the regex without one entry at a time, and demands that the
sentence built from that entry go from accepted to refused — a dead entry and a redundant entry both
fail it. The other end (`the test is described here`, no verdict) is asserted refused, so the
vocabulary is load-bearing.

### 8.2 N-a / N-b / the texts

* **N-a** `test_a_declared_pin_default_is_clamped_up_to_the_floor_and_the_answer_says_the_clamped_rung`:
  a synthetic kit with `build: {default: pin, floor: opus}` and a builder pinned sonnet — both ends
  come out `opus`, the ask of sonnet is refused as below the floor.
* **N-b** the `why` now echoes the RESOLVED default and names the declared word beside it:
  `class build starts on opus (declared pin)`.
* **N-c** the four texts say what the reader reads — a test module or a `test`/`tests` tray, or a
  criterion sentence with a verdict — and name the two cases they refuse (`docs/test-plan.md`, a
  denial). `under tools/` is gone from all of them.
* Checkpoint (c) names the band **only where there is one**; a class whose ends coincide reads
  `, with no band below it`.
* The lease `why` says `allowed: the acceptance names a test` (it is not one).

### 8.3 Red-first rows of the rework

Rig `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0137/redfirst2.py`, own copy `tree2/`, log
`redfirst2.json`. Nine rows, each green rc 0 → mutated rc 1 → restored byte-exact.

| # | Mutation | Test | Arbiter's line |
|---|---|---|---|
| 14 | both feeds back to the bare-word reader | `test_an_ask_below_the_default_is_granted_only_for_a_test_shaped_acceptance` | `{'rung': 'sonnet', … 'role_class': 'build', …}` (rows (d)/(e) bought the cheap rung) |
| 15 | same | `test_the_acceptance_reader_reads_a_test_and_not_the_word` | `({'expected_outputs': ['lib/x_spec.rb']}, {})` |
| 16 | the denial guard removed | same | `({'acceptance_refs': ['AC-1']}, {…'no test goes red after this rename'…})` |
| 17 | module convention → the bare word | same | `({'expected_outputs': ['lib/x_spec.rb']}, {})` |
| 18 | the verdict requirement dropped | same | `({…'a test plan is written'…})` |
| 19 | same | `test_the_acceptance_reader_needs_a_verdict_word_and_every_listed_one_earns_its_place` | `assert not True` |
| 20 | `default_rung = resolve(rule)` (no clamp) | `test_a_declared_pin_default_is_clamped_up_to_the_floor_…` | `{'rung': 'sonnet', … 'kit': 'inverted', …}` |
| 21 | the `why` echoes the file's word | same | `opus: pin sonnet, class build starts on pin, …` |
| 22 | the band printed where there is none | `test_the_shipped_spawn_gate_prints_the_four_line_checkpoint_and_never_blocks_on_it` | `CHECKPOINT before builder TSK-0001 starts (DEC-0092 (3)):` |

**Row 16 was GREEN on the first attempt and that is a finding of my own**: the denial guard refused
nothing no other half refused, because every denial row I had also lacked a verdict word. Two rows
were added in which the denial is the only reason (`no test goes red after this rename`,
`kein Test schlaegt fehl nach dem Rename`), and the row is red since. A guard nothing measures is a
guard nobody has.

### 8.4 Runs of the rework

`test_ladder` 48 ✓ (23.1 s) · `test_light_kit` 26 ✓ (47.7 s) · `test_role_contracts` 32 ✓ ·
`test_review_procedure` 27 ✓ · `test_model_ladder` 13 ✓ (reads the changed ladder and constitution).
`ruff` clean, `validate.py` clean, ONE restamp → **2026.09.11-10** ×3 (the later change was a test
file, so the re-check reports `unchanged`); package sizes re-recorded (+309 dev / +311 research).

### 8.5 Still not closed, named

* **A German compound (`Regressionstest`) does not count.** No rule here can tell that tail from the
  one in `latest`, and the reader fails in the expensive direction (the order keeps opus). Measured
  as a refusal row, not claimed: `test_the_acceptance_reader_reads_a_test_and_not_the_word`.
* **`_DENIES_RX` over-refuses**: "the test must not fail" carries `not` and is refused. Same
  direction — the default rung stands.
* The verify report file named in the coordinator's message does not exist on disk (§8 opening).
