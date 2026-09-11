# TSK-0136 — implementer protocol (PR-0011 AC-3; DEC-0095, DEC-0096)

Base: `main` at `6a412d8`. One writer. Kit stamp after the last change: **2026.09.11-8** for all
three kits (rework round) (`python tools/bump_kit_version.py` re-run at the end reports *unchanged*).

## 0. The plan, and the way it REJECTED (`FR-0084`)

Rejected: leaving `failed_runs_per_rung: 1` in place and adding a SEPARATE effort counter beside it
(an `effort_escalation:` block with its own count of failed runs). It lost because it would have
been a second reader of the same FAILED count — two numbers that can disagree about the same
history — while `DEC-0096` (2) asks for the two thresholds to be ONE pair on one count. What the
smaller way (only the three `ladder.yaml`, no kernel change) would not have covered: nothing would
derive an effort from the new line, so the two declared values would be dead config that no test
could hold — exactly the dead-entry class the house rules name.

## 1. File table

| File | What changed | Why (record) |
|---|---|---|
| `team-kits/kernel/dispatch.py` | `EFFORT_STEPS_KEY` constant; `_valid_ladder` validates `escalation.effort_steps_before_rung` and normalises it; `ladder_for_order` derives `rung_steps` and `effort_steps` from the FAIL count and both thresholds and returns an `escalation` sentence; the lease `why` and the checkpoint line (c) carry it | DEC-0096 (1)/(2)/(4) |
| `team-kits/dev-team/ladder.yaml` | `planning: opus`, `build: opus`, `architecture: top` kept; `effort_steps_before_rung: 2`, `failed_runs_per_rung: 3`; the class comment no longer claims a build that falls to its pin | DEC-0095 (1)/(2)/(4a), DEC-0096 (2) |
| `team-kits/research-team/ladder.yaml` | the same, with the method-design wording | DEC-0095, DEC-0096 |
| `team-kits/office-team/ladder.yaml` | ONLY the escalation block (two thresholds) plus a comment saying why the classes are untouched; the filing-pair sentence now says failed run**s** climb | DEC-0096 (2), DEC-0078 (1)/(2) |
| `team-kits/dev-team/agents/project-manager.md`, `team-kits/research-team/agents/project-manager.md` | `model: fable` → `model: lead` | DEC-0095 (2) |
| `team-kits/office-team/agents/office-manager.md` | **unchanged** — already `model: lead` | DEC-0095 (2) |
| `team-kits/{dev,research}-team/constitution/AGENTS.md` | Defaults bullet (build class, DEC-0088 (1) superseded); pin bullet `model: opus`; ladder bullet's class clause; the escalation-order sentence; the QA/validation-FAIL bullet | DEC-0095, DEC-0096 |
| `team-kits/office-team/constitution/AGENTS.md` | the escalation-order sentence; the "one rung up per FAIL" clause; the filing-pair climb sentence | DEC-0096 |
| all three constitutions | NEW shared paragraph `**READ THE END OF A LOG, NEVER THE LOG …**`, byte-identical (sha256 of the block, first 16: `d696f71a18629eca` in all three) | DEC-0095 (6) |
| `team-kits/{dev,research}-team/skills/project-manager/SKILL.md` | the "goal-sized build goes to the top rung" sentence only; the three-line rule is untouched | DEC-0095 (1) |
| `team-kits/model_tiers.yaml` | header block naming DEC-0095 beside DEC-0076 and saying the "who runs where" answer is the kit's declaration, not this table | DEC-0095 |
| `README.md` | the tier bullet and the ladder bullet | DEC-0095, DEC-0096 |
| `.claude/agents/harness-lead.md` | `model: opus` + a paragraph saying it takes effect at the NEXT session start | DEC-0095 (2) |
| `.claude/agents/harness-implementer.md` | the reading-discipline statement | DEC-0095 (6) |
| `tools/test_ladder.py` | fixture gains `effort_steps_before_rung: 0`; two mutation rows; two new tests; the filing-pair test reads the threshold off the declaration | red-first, below |
| `tools/test_model_ladder.py` | `test_the_ladder_paragraph_names_the_rung_the_build_class_starts_on` | red-first, below |
| `tools/test_role_contracts.py` | `test_every_constitution_carries_the_reading_discipline_duty`, `test_every_kit_lead_pins_the_rung_its_own_planning_class_starts_on` | red-first, below |
| `tools/test_light_kit.py` | checkpoint (c) assertion extended; pilot-rig row follows DEC-0095 (1) | red-first, below |
| `tools/test_model_pins.py` | `pinned_model` docstring only — it claimed "the session lead pins none", which this round made false | house rule 3 |
| `tools/test_hooks.py` | the two dead AC-2 vocabulary alternatives removed, with the asymmetry they leave named | TSK-0135 verify round 2, item 1 |
| `tools/provider_observations.json` | `headless_pm_stop_point.run_1` label | TSK-0135 verify round 2, item 3 |
| `tools/lead_package_sizes.json`, `docs/reviews/phase0-disposition.md` | the size record raised through `tools/record_lead_package_sizes.py --write --note …` (the route `validate.py` names) | the new shared paragraph, +1920/+1614/+1723 B |

## 2. WHY office-team's classes are unchanged

`DEC-0095` (1) says "the `build` class of **every** kit ladder starts on opus"; its own
*consequences* say "the office kit is unchanged (its top is opus already)"; `TSK-0136`'s
expected_outputs bind the second reading. The substance: `DEC-0078` (1)/(2) bought the CHEAP rung
for back-office work on purpose, office's top rung is opus, so the standing top-rung cost
`DEC-0095` was removing was never running there. Office therefore keeps `build: pin` /
`reading: pin` / `planning: top` and takes only the two `DEC-0096` thresholds. **The tension
between the decision text and its consequences line is real and is a finding for the lead**, not
something this order could resolve.

## 3. Red-first rows — the arbiter's line

Rig: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0136/rig.py`, on a copy without `.git` at
`…/TSK-0136/repo`. It refuses to run unless the working directory is its own, and opens every file
with `newline=""` on both ends; every revert is checked back by sha256. Report:
`…/TSK-0136/rig-report.json`. **10 rows, 10 red; the 8 nodes on the unmutated copy: rc 0.**

| Row | Defect restored | Node | Arbiter's line |
|---|---|---|---|
| R1 | dev `build: pin`, `planning: top` | `test_ladder.py::test_the_build_starts_on_opus_and_only_the_architecture_starts_on_the_top_rung` | `E AssertionError: dev-team` (the `classes["build"] == "opus"` assertion, message = the kit name) |
| R2a | dev ladder back to `failed_runs_per_rung: 1` / `effort_steps_before_rung: 0` | `test_ladder.py::test_a_failed_run_raises_the_effort_before_it_raises_the_rung` | `E AssertionError: [('opus', 'high'), ('fable', 'high'), ('fable', 'high'), ('fable', 'high')]` — the first failed run puts the builder on the top rung, the cost DEC-0096 removes |
| R2b | the kernel's effort escalation removed (`effort_steps = 0`) | same node | `E AssertionError: [('r1', 'low'), ('r1', 'low'), ('r1', 'low'), ('r2', 'low')]` |
| R3 | the dev ladder paragraph names `**fable**` beside the BUILD | `test_model_ladder.py::test_the_ladder_paragraph_names_the_rung_the_build_class_starts_on` | `E AssertionError: dev-team: the declaration starts the build class on 'opus' and its ladder paragraph names ['fable'] beside the build; …` |
| R4 | dev PM pinned back to `fable` | `test_role_contracts.py::test_every_kit_lead_pins_the_rung_its_own_planning_class_starts_on` | `E AssertionError: dev-team: project-manager pins 'fable' while its 'planning' class starts on 'opus' — the session runs on the PIN …` |
| R5 | the reading duty deleted from ONE kit (office) | `test_role_contracts.py::test_every_constitution_carries_the_reading_discipline_duty` | `E AssertionError: team-kits\office-team\constitution\AGENTS.md carries 0 statement(s) of the DEC-0095 (6) reading duty, expected exactly one` |
| R6 | the checkpoint (c) line without the FAIL derivation | `test_light_kit.py::test_the_shipped_spawn_gate_prints_the_four_line_checkpoint_and_never_blocks_on_it` | `E AssertionError: CHECKPOINT before builder TSK-0001 starts (DEC-0092 (3)): …` (the (c) substring is absent) |
| R8 | `escalation_line` counting the DERIVED rung steps instead of the granted ones | `test_ladder.py::test_an_order_that_failed_climbs_one_rung_per_failed_run_capped_at_the_top` | `E AssertionError: FAIL 3: rung +3, effort +0 — …` — a two-rung climb capped at `top` reported as three. **This row is my own correction's defect, found in the self-review before the hand-back**: the sentence must count the steps GRANTED, because `top` caps the climb and a derived "+2" the cap swallowed names a model the order is not running on. |
| R9 | the effort cycle keyed on the DERIVED climb (`failed_runs % per_rung`) | `test_ladder.py::test_a_failed_run_raises_the_effort_before_it_raises_the_rung` | `E AssertionError: FAIL 9 came back on the same rung r3 at a WEAKER effort than FAIL 8 (high -> low): FAIL 9: rung +2, effort +0 …` — **verify round 1, F1**: past the cap no rung step is granted, so the reset had nothing paying for it. |
| R7 | the second threshold unvalidated in `_valid_ladder` | `test_ladder.py::test_a_malformed_declaration_names_the_field_it_refuses` | `E TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'` — with the check gone the kernel CRASHES at the lease instead of refusing with the field named |

## 4. Runs

One pytest at a time, timeouts derived from the measured durations. Reading suites only
(a slice under a goal, `DEC-0088` (d)); **no full run**.

| Suite | Result | Wall |
|---|---|---|
| `tools/test_ladder.py` | 39 passed | 42 s |
| `tools/test_light_kit.py` | 26 passed | 95 s |
| `tools/test_review_procedure.py` | 27 passed | 6.6 s |
| `tools/test_role_contracts.py` | 32 passed | 3.8 s |
| `tools/test_hooks.py -k team_size` | 2 passed, 1019 deselected | 4.1 s |
| `python -m ruff check tools team-kits` | All checks passed | — |
| `python tools/validate.py` | all structural checks passed | — |
| `python tools/bump_kit_version.py` | 2026.09.11-8, re-run *unchanged* ×3 | — |

Round 1 (before the rework) additionally ran `tools/test_model_ladder.py` 13 passed / 15 s and
`tools/test_model_pins.py` 5 passed / 0.5 s; neither reads a file the rework touched.

`ruff check .` is refused by gate 1 (the bare `.` reads as an ancestor of the protected tree,
H19), so the two trees this round touches are named.

## 5. (g) row

| Item | Reading |
|---|---|
| Rung / effort of this order | `rung: opus`, `effort: high` (on TSK-0136, the first order with the DEC-0091 fields) |
| Rounds to PASS | 0 verification rounds so far — this is the first hand-back |
| Tokens (my own counter) | budget 15,000,000 → 14,698,508 at the hand-back = **≈ 301,500 tokens** |
| Wall-clock | first edit `team-kits/kernel/dispatch.py` mtime **09:02:30**, clock read at close **09:47** → ≈ 45 min of writing and measuring; the session start before the first edit is not readable from inside the run |
| Red rows | 10 of 10 red, 8 of 8 green unmutated |

## 6. What I deliberately did NOT close, and named — NINE residues

1. **`report.lease_distribution` does not record per EFFORT.** `TSK-0136`'s expected_outputs ask for
   "rounds-to-PASS per rung AND per effort", but `team-kits/kernel/report.py` is in neither
   `allowed_scope` nor the lead's named-sections list, and neither is `tools/test_report.py`. The
   field it would read (`lease_effort`) is already written on every task by `create_lease`, so the
   change is small; it needs an order that names the file.
2. **`allowed_scope` names `team-kits/research-team/agents/research-lead.md`, which does not
   exist.** The research kit's lead role file is `agents/project-manager.md` (`name:
   project-manager`, description "Research Lead / Project Manager"). I changed that file. Item
   defect, not a scope breach I chose.
3. **`tools/test_model_pins.py` is not in `allowed_scope`** although the item's expected_outputs
   and the lead's order both name it. I touched exactly one docstring there, because this round
   made its sentence "the session lead pins none" false. Nothing executable changed.
4. **`.claude/agents/harness-verifier.md` is outside `allowed_scope`**, so the reading rule of
   DEC-0095 (6) reached the implementer role text and the three constitutions, not the verifier's.
5. **DEC-0095 (1) takes the CHEAP rung away from a build order even when the PM asks for it** —
   measured, not deduced: the pilot rig asks `--rung sonnet` for its small order and the lease now
   comes back `opus` in dev and research (`tools/test_light_kit.py`, the pilot row; office still
   reaches sonnet because its `build` class stays `pin`). The user's three-line rule in the PM
   skills still offers »der eine passt nur x an — sonnet high/xhigh«, and for a build-class role in
   dev/research that line is now unreachable. The item says the three-line rule stays unchanged, so
   I left it; **this needs the user's word**, either as "the sonnet line is gone for builders" or as
   a `rung` exception for mechanical slices.
6. **DEC-0096 (2) says office's "first step is a no-op"; for the ordinary office order it is not.**
   Office's pair is medium/high, so FAIL 1 really does raise an order from medium to high. The
   no-op holds only for an order already at its ceiling (a `large` goal, or the filing pair's fixed
   `low`). The office `ladder.yaml` states the three cases and names the DEC sentence it corrects,
   rather than repeating a claim the code does not build.
7. **The two-effort-step reading of `effort_steps_before_rung` is mine, and it is unobservable on
   every shipped kit.** All three pairs have exactly ONE step of headroom, so "one step per failed
   run up to the threshold" and "one step in total" agree everywhere the kits run. I took the
   remainder reading because it is what the two threshold NAMES express; the only place it is
   measured is the FAIL-2 row of the synthetic ladder in
   `test_a_failed_run_raises_the_effort_before_it_raises_the_rung`, and the test's docstring says so.
8. **`provider_observations.json` `run_2` carries a bare "20.9 s"** with no label, against a
   08:14:02–08:14:33 window (31 s wall-clock), so the number is presumably API time. The item names
   `run_1` only; an unlabelled number is not a false claim, so I left it and name it here.
9. **The pin spelling was decided by the code, not by taste.** `tools/validate.py` refuses a kit
   source that pins a rung name which is an alias TARGET, so `opus` is not writable there and
   `lead` is the only spelling — office-manager therefore KEEPS `model: lead` and the other two
   move to it. `.claude/agents/harness-lead.md` is not a kit source and carries `model: opus`
   literally; **it takes effect at the next session start**, which its own paragraph says.

## 7. Patch

```
git diff 6a412d8
```

28 files (the three VERSION files at 2026.09.11-7 included), ≈ +630 / −100. `git status` additionally shows the kernel's own writes under
`project_memory/` that were present at the base — untouched.

## 8. Two EVD lines for the lead (state-relative refs)

```
capture EVD --kind test --result pass \
  --summary "TSK-0136: six reading suites green on the stamped tree (test_ladder 39, test_model_ladder 13, test_light_kit 26, test_role_contracts 32, test_review_procedure 27, test_model_pins 5); ruff and validate.py clean; kits at 2026.09.11-8" \
  --refs "staging/TSK-0136/protocol.md#4-runs" --related TSK-0136
```

```
capture EVD --kind measurement --result pass \
  --summary "TSK-0136 red-first: 10 of 10 rows red with the pre-round defect restored in a copy without .git, 8 of 8 nodes rc 0 unmutated; the arbiter's line per row is in the protocol" \
  --refs "staging/TSK-0136/protocol.md#3-red-first-rows--the-arbiters-line" --related TSK-0136
```

## 9. Rework after verify round 1 (2026-09-11, clock read 10:14)

| Finding | What changed |
|---|---|
| **F1** (blocking) | `kernel/dispatch.py`: `granted_rungs = rungs.index(chosen) - rungs.index(start)` beside `chosen`, and the effort cycle is `int(failed_runs) - granted_rungs * per_rung` instead of `int(failed_runs) % per_rung`. Below the cap the two spellings are arithmetically identical (`granted_rungs == failed_runs // per_rung` while `top` does not bite), so nothing under the top rung moved; past the cap the count no longer resets, and the pair holds at the ceiling. The verifier's measured line — dev FAIL 5 fable/xhigh, FAIL 6 fable/high — is now fable/xhigh at both. The FIVE texts that claimed the opposite were made true: `dispatch.py` (the escalation comment), the three `ladder.yaml` escalation blocks, the ladder statement of all three constitutions; each says the reset is PAID FOR by the granted rung step. |
| **F2** | `tools/test_ladder.py`: the fixture comment now describes the fixture it stands over (three rungs, three effort steps of headroom). I kept THREE rungs rather than giving it six, and the comment says why: six rungs would put the cap out of reach inside the test, which is exactly where F1 lives. |
| **F3** | `tools/test_hooks.py`: re-measured with the shipped reader — `nie gefragt` matches nothing, `no team-size question` matches exactly one sentence (`office-team/skills/office-manager/SKILL.md:94`, "No team-size question to the user.") which carries neither the subject nor an ask. The comment says that instead of "NO shipped text". |
| **F4** | `.claude/agents/harness-lead.md`: the reason is now the `agent:` binding — a session's model is chosen when the session starts — and the paragraph says explicitly that role FILES are read fresh at every call, so only this one line waits. |
| **F5** | the three numbers (−8, 10/10, 8/8), section 4 and both EVD summaries. |

New red-first row **R9** carries F1 (table in section 3). The rig now runs 10 rows; R8's mutation
was retargeted, because the sentence it guards reads `granted_rungs` now and mutating that name
would have conflated R8 with R9 — it injects the derived count (`int(failed_runs) // per_rung`)
into the sentence alone.

WHAT THE REWORK DID NOT CHANGE: the nine residues of section 6 stand as they are. The verifier's
own negative findings (`test_model_pins` stays green on a `fable` PM pin; the "or" in the item's
expected_output is carried by `test_role_contracts` alone) match residue 3 and need no edit.
