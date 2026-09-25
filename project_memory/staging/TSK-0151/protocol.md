# TSK-0151 -- protocol (harness-implementer)

Base 8677bd2, branch feat/harness-v2. Scratch: `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0151\`.
Every time below is a clock READ (`date`), local time.

## 0. Start -- 2026-09-25T15:06:01

Read: TSK-0151 (whole), DEC-0114, BUG-0306, BUG-0307, FR-0093, DEC-0098; `team-kits/model_tiers.yaml`,
the three kit `ladder.yaml`, this repo's `ladder.yaml`; `kernel.dispatch` by section
(`ladder_for_order` 3323-3560, `spawn_model_refusal` 1066-1098, `_reference_rungs` 255-294,
`_valid_ladder`/`ladder_declaration` 2701-2966); `tools/radar_routine.py` 1-720 in two sections;
radar reports by section only (claude-by-claude items 1/2/6 + lineup table; codex-by-claude item 1).
Vendor wording for the Claude suitability lines fetched 2026-09-25 from
https://platform.claude.com/docs/en/about-claude/models/overview (the "Description" row).

## 1. PLAN -- and the way it REJECTED (FR-0084)

**The no-Fable form on Claude: the LADDER form, not the translation form.** Each kit's `top:` goes
from `fable` to `opus` (dev, research; office's `office-developer: top: fable` exception goes), and
this repo's own `ladder.yaml` likewise. `architecture: top` stays and now resolves to opus. The rung
NAME `fable` stays in `rungs:` and in the tier table (DEC-0114 (4) allows it), so an order's
`--rung fable` ask is still placeable and is capped at the top like any ask above it.

REJECTED: the "Claude translation of the top rung" (`tiers.claude.fable: opus`), which the order
named as the example of a smallest form. Measured against the code, it closes nothing on the path
that runs: (a) the Claude spawn never reads that row -- `dispatch.spawn_model_refusal` compares the
Agent call's `model` with the rung NAME (`str(requested) != rung`), and the constitutions tell the
lead to pass the header's `rung` as `model:`, so a `fable` rung is still spawned as `model: fable`;
(b) it breaks `_reference_rungs`, which finds the reference row by the property "every rung name IS
its model id" and would then find none; (c) the rung step at the third failed run would still be
granted (opus -> fable) and would RESET the effort to the kit default on the same model -- the
opposite of DEC-0114 (4)'s "escalation climbs EFFORT only on Claude, up to the ladder's effort top".
Making the translation real needs a provider-aware ladder answer (the kernel's answer is one per
order, not per provider) -- a kernel change far larger than one line per ladder. The ladder form
gets (c) for free: at the top rung `ladder_for_order` grants no step, so the effort climbs to the
ceiling and stays there.

WHAT THE LADDER FORM DOES NOT COVER, named: the ladder is provider-neutral, so on a Codex project no
shipped ladder reaches the `fable` row (`gpt-6-astra`) either. The row stays in the table as
DEC-0114 (4) says ("the Codex top stays gpt-6-astra"), but it is DORMANT until a ladder names the
top again -- that is the user's separate question (DEC-0114 (4): "the lead puts that question to the
user separately"), and a per-provider top would be its build.

**BUG-0307: the routine declaration gets a TASK per routine** (which app task runs it, and at which
step) instead of a weekday per routine; the test's property becomes "a runner whose app skips a
task while another of its tasks runs has ONE task, and runs its watchers in it in sequence".
REJECTED: one weekday value changed per entry and the stagger assertion simply deleted -- it would
leave nothing measuring DEC-0098's reason (the Desktop skip rule) at all.

AC-1 OF BUG-0307 VS DEC-0098 (2), named: the AC says "no two routines of the same runner as
separate tasks at the same time" for EVERY runner; DEC-0098 (2) orders TWO Codex Automations at the
same minute because the Codex app's skip behaviour is unmeasured. The decision wins; the test
holds the rule for a runner whose app is DECLARED to skip (claude: True, sourced) and lets a runner
keep separate same-time tasks only while its declaration says the skip is unmeasured (codex: None,
sourced to DEC-0098 (2)). The mutation "codex declared as skipping" turns it red (section 3).

## 2. What was built -- 2026-09-25T15:31:10

(1) DEC-0114 / BUG-0306
- `team-kits/model_tiers.yaml`: codex rows `gpt-6-astra` / `gpt-6-sol` / `gpt-6-luna`; price block
  and the price-derived watch date gone (watch-date marker kept with "none today", the reader
  requires it); `suited_for:` per provider and rung (vendor wording, source URL, read 2026-09-25 --
  Claude lines from the models overview fetched 2026-09-25, codex lines from
  radar/2026-09-25-codex-by-claude.md item 1); header: no "luna row" denial, MAINTENANCE no longer
  says "never an automatic bump" (pass-through stated as wanted, DEC-0114 (2)), DEC-0114 (4) named.
  `load_tiers` (the generator's mini-parser) ignores the new top-level key (section-based).
- Ladders: dev/research `top: opus`; office: the `office-developer: top: fable` exception removed;
  this repo's `ladder.yaml` `top: opus`. Comments/constitution paragraphs/lead skills that said the
  top is fable or that fable is bought for architecture/escalation reworded to DEC-0114 (4).
- README.md Models bullet: codex ids + no prices + DEC-0114 (4).
- `tools/test_hooks.py`: six hard-coded codex ids (`gpt-5.6-sol`/`-terra`) now read off the table
  through `_codex_model(rung)` (the pattern `test_gen_accepts_fable_as_the_top_rung_pin` already used).
- Tests: `tools/test_model_ladder.py::test_the_tier_table_carries_no_price_and_says_what_each_rung_is_for_bug_0306`
  (+ its reader floor `::test_the_price_and_row_readers_see_what_they_are_for`),
  `tools/test_ladder.py::test_no_shipped_ladder_answer_reaches_the_top_rung_bug_0306`;
  shipped-ladder expectations updated in `test_the_shipped_declarations_say_what_the_decisions_decided`,
  `test_the_build_starts_on_opus_and_only_the_architecture_starts_on_the_top_rung`,
  `test_a_failed_run_raises_the_effort_before_it_raises_the_rung` (shipped rows now opus/high then
  opus/xhigh held -- no rung step is granted at the top).

(2) DEC-0098 / BUG-0307
- `tools/radar_routine.py`: `SCHEDULE_AS_TOLD` all four friday ~20:00 with `task` + `step`
  (`watcher-duo` steps 1/2, the two codex routines one task each); `SCHEDULE_SOURCE` names DEC-0098;
  `RUNNERS[...]['skips_while_another_runs']` (claude True sourced, codex None sourced);
  `app_tasks()` + `--describe` key `tasks` (one Instructions text per app task; the duo's text runs
  its routines in step order).
- `tools/test_radar_trigger.py`: stagger test replaced by
  `::test_the_routine_plan_puts_every_watcher_on_one_evening_and_one_task_per_skipping_app_bug_0307`;
  the report fixtures SATURDAYS/SUNDAYS/MONDAYS became Friday-dated per-routine sets.
- `.codex/agents/*-watcher.toml` regenerated (`--write-overlays`): only the model line moved,
  `gpt-5.6-sol` -> `gpt-6-sol` (the watcher definitions pin `opus`).
- `radar/README.md` "How a run starts": one Friday evening, the Desktop task `watcher-duo`.

(3) FR-0093
- The three order lines as `**(3) Three cost lines every order carries, word for word (FR-0093).**`
  at the end of each kit lead skill's section "Before the order goes out" (dev/research
  project-manager, office office-manager) -- ONE home per kit, the same text in all three (the
  section is held equal across kits by
  `tools/test_review_procedure.py::test_every_kit_lead_is_given_the_ways_a_work_order_line_goes_wrong`).
- `tools/measure_agent_tokens.py` + `tools/test_measure_agent_tokens.py` (synthetic transcript,
  and the script as a process).

(4) User patch: `project_memory/staging/TSK-0151/user-patch.md` + `apply_user_patch.py` (six sites
in three `.claude/agents/` files; after writing it regenerates the two codex overlays).

## 3. Red-first and mutations -- rig `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0151\`

`rig.py` copies tools/ team-kits/ radar/ .codex/ .claude/ docs/ project_memory/ ladder.yaml
CLAUDE.md ruff.toml into a .git-less copy (binary, refuses to run outside its own directory), puts
named files back at their 8677bd2 bytes (`git show`), runs named nodes. `mutate.py` changes ONE
byte string in a copy of the CURRENT tree, runs one node, restores the bytes.

RED ON THE BASE (8677bd2 bytes of the fix files, everything else current):
- 15:29 `test_the_tier_table_carries_no_price_and_says_what_each_rung_is_for_bug_0306` with base
  `team-kits/model_tiers.yaml`: rc 1, "the tier table still carries price figures (DEC-0114 (3)):
  ['per 1M tok', '$1', '$7', ...]".
- 15:47 `test_no_shipped_ladder_answer_reaches_the_top_rung_bug_0306` with the base three kit
  ladders + base `ladder.yaml`: rc 1, "dev-team ('project-manager', 'lead', 'normal', None): the
  answer names fable at failed run(s) [3..9] -- ... FAIL 3: rung +1 ... top fable".
- 15:46 `test_the_routine_plan_puts_every_watcher_on_one_evening_and_one_task_per_skipping_app_bug_0307`
  with base `tools/radar_routine.py`: rc 1, "DEC-0098 put all four on Friday ~20:00: {saturday,
  friday, monday, sunday}".
All three green on the current tree (15:43 / 15:28 / 15:21 first, again in section 5).

MUTATIONS on the current tree (15:43-15:46), each red unless marked:
| node | mutation | result |
|---|---|---|
| AC-1 | codex mid row back to gpt-5.6-sol | red |
| AC-1 | codex small row back to gpt-5.6-terra | red |
| AC-1 | one suitability line (claude/sonnet) removed | red |
| AC-1 | a read date in the future | red |
| AC-1 | a source that is no URL | red |
| AC-1 | "no haiku or luna row" back in the header | red |
| AC-1 | one price ($4/$20) in a comment | red |
| AC-2 | dev `top:` back to fable | red |
| AC-2 | research `top:` back to fable | red |
| AC-2 | office-developer `top: fable` exception back | red |
| AC-2 | this repo's `top:` back to fable | red |
| AC-2 | kernel: effort cycle keyed on `failed_runs % per_rung` (falls back at the top) | red |
| AC-2 | kernel: escalation raises no effort | red |
| AC-2 | dev `design: fable` as a class start | GREEN -- correct: `top: opus` caps it; this is the ladder form's point |
| BUG-0307 | one routine back on saturday | red |
| BUG-0307 | schedule source back to DEC-0090 (4) | red |
| BUG-0307 | the duo split into two Desktop tasks at one time | red |
| BUG-0307 | steps that are no sequence (1, 3) | red |
| BUG-0307 | codex declared as skipping while its two tasks stay | red |
| BUG-0307 | the duo's text built in reverse step order | red (first cut GREEN -- the test compared the text with the list it was built from; now compares with the plan's steps) |

A DEFECT OF MY OWN, found by the rig: the first `DENIED_ROW_RX` (nested repetition) backtracked
for minutes on the shipped header -- the first mutation run hung 12 min at 15:30 and was killed.
Replaced by one bounded character class over the comment-joined text; the module then ran in 7.7 s.

## 4. FR-0093 BEFORE baseline, the user patch, the stamp

BEFORE baseline -- `python -B tools/measure_agent_tokens.py --item TSK-0150` at 15:23 (layout
measured first: `~/.claude/projects/C--Offline-Repos-AgentAndSkills/<session>/subagents/agent-<id>.jsonl`
+ `.meta.json`; a model call is several lines sharing one `message.id`, so a turn is an id):

| agent | type | turns | ctx median | ctx p90 | input total | polling turns |
|---|---|---|---|---|---|---|
| a52a713107822731c | harness-verifier | 281 | 186,950 | 287,201 | 51,568,023 | 1 |
| a8f6b8de3e9a725e1 | harness-implementer | 383 | 381,612 | 568,352 | 137,484,112 | 27 |
| **TSK-0150 (2 agents)** | | 664 | median of medians 284,281 | | 189,052,135 | 28 = 6.4 % of input |

`--item` finds only the agents whose FIRST prompt names the id; for the whole generation-6 session
(`--session 4c7eb015-...`): 79 agents, 19,360 turns, input 6,204,077,544, 456 polling turns = 3.7 %
of input -- the same order as FR-0093's 3.5 % (its count used a looser turn unit). The AFTER is the
next order's, as FR-0093 says.

USER PATCH -- `python -B project_memory/staging/TSK-0151/apply_user_patch.py --check` on the tree
(whose `.claude/agents/` is byte-identical to 8677bd2, `git status -- .claude/` empty): rc 0, six
sites "would change", no problem. Applied IN A COPY (rig `patched`, 15:48) and the three suites that
read those role files run there and in an unpatched copy of the same parts (`unpatched`): both
`2 failed, 83 passed`, the same two nodes -- both artefacts of a .git-less copy or of the lead's
record (section 6) -- so the patch adds no failure; the codex overlay equality test passes in the
patched copy because the script regenerates them.

STAMP: `python tools/bump_kit_version.py` at 15:49 -> all three 2026.09.25-1; validate then FAILED
on the lead-package size record (dev 61399 > 61219, research 63255 > 63075: my constitution edits
added 180 bytes each). I SHORTENED the two paragraphs rather than raising the record (FR-0093 is
about context cost) -> 188 bytes below the base each, then stamped again at 15:49: dev/research
2026.09.25-2, office stays 2026.09.25-1. Two stamp runs, not one -- the first was invalidated by the
size fix; named here rather than hidden. `python -m ruff check .` all passed; `python
tools/validate.py` 15:49 "all structural checks passed".

## 5. The suites that READ what changed (DEC-0080 rule 2), each its own selection

REACH, grepped (not taken from the order): readers of `model_tiers.yaml` / `ladder.yaml` /
`ladder_for_order` -- `tools/test_{approvals_dispatch,hooks,hooks_v2,ladder,light_kit,model_ladder,
model_pins,radar_trigger,repo_hygiene,review_procedure,role_contracts}.py`; readers of
`radar_routine` or a kit lead SKILL.md -- adds `test_{context_budget,office_package,
shared_skill_contract,parity_sources,shortening_net}.py` (and more generic SKILL readers the full
run covers). Kernel readers of the tier table: `kernel/dispatch.py` (`_reference_rungs`,
`_store_aliases`), `gen_provider_artifacts.py`, `*/hooks/session_status.py`, `tools/validate.py`,
`tools/radar_routine.py` -- none of their CODE changed; the table keeps its shape (the mini-parser
`load_tiers` reads section-wise and ignores `suited_for:`).

| time | suite | result |
|---|---|---|
| 15:50-15:51 | test_ladder.py | 62 passed |
| 15:51 | test_model_ladder.py | 15 passed |
| 15:51 | test_model_pins.py | 6 passed |
| 15:51-15:52 | test_light_kit.py | 1 failed (pilot rig: dev/research large order expected `fable`) -> fixed to `opus` (DEC-0114 (4)); 16:12 the node alone: 1 passed |
| 15:52-15:54 | test_approvals_dispatch.py | 236 passed |
| 15:54 | test_radar_trigger.py | 18 passed, 1 failed: `test_no_artifact_of_the_duo_names_a_watcher_the_repo_does_not_define` -- `radar/routine.json` names `radar-watcher`; that text is the lead's record, unchanged by me and forbidden to me (section 6) |
| 15:54-15:56 | test_repo_hygiene.py | 42 passed, 1 failed: `test_no_tracked_text_file_checks_out_with_crlf` -- `project_memory/staging/user-patch/measure-2026-09-25.txt` (CRLF on disk; not my file, not in my scope; section 6) |
| 15:56 | test_review_procedure.py | 29 passed |
| 15:56 | test_role_contracts.py | 37 passed |
| 15:56 | test_measure_agent_tokens.py | 2 passed |
| 15:56 | test_context_budget.py | 1 failed: the size record must EQUAL the measurement -> `python tools/record_lead_package_sizes.py --write --note ...` (all three SHRANK: dev -8, office -18, research -8) |
| 15:57 | test_office_package.py | 75 passed |
| 15:57 | test_shared_skill_contract.py | 6 passed |
| 15:57 | test_parity_sources.py | 9 passed |
| 15:58 | test_shortening_net.py | 1 failed: section pins -> `python tools/pin_constitution_sections.py --write --note ...` (9 sections, all ones I edited) |
| 16:11-16:12 | test_context_budget.py + test_shortening_net.py again | 78 passed |
| 15:58-16:11 | test_hooks_v2.py | STOPPED after 13 min (cost rule: selections < 3 min); covered by the full run below |

After the section-5 fixes: `python tools/validate.py` 16:13 "all structural checks passed", ruff
all passed. No kit file changed after the second stamp (the record/pin writes are `tools/` +
`docs/reviews/phase0-disposition.md`).

## 6. Delivery run, gates run, evidence -- and what is not mine

FULL RUN, once: `DELIVERY_RUN=TSK-0151 python -B -m pytest tools/ -q -p no:cacheprovider
--tb=line`, 16:13:31 -> 17:14:53 (61:18, the host was loaded by another project's processes):
**2 failed, 5156 passed, 14 skipped**. Tail kept in `staging/TSK-0151/full-run-tail.txt`. Both
failures are OUTSIDE this order's scope and untouched by it (`git status` shows neither changed):
- `tools/test_radar_trigger.py::test_no_artifact_of_the_duo_names_a_watcher_the_repo_does_not_define`:
  `radar/routine.json` (the lead's record, forbidden to me) names `radar-watcher` in its `source`
  text -- the lead's 2026-09-25 re-pointing. Remedy for the lead: word it without the old task name
  (radar/README.md now does: "in place of the first task").
- `tools/test_repo_hygiene.py::test_no_tracked_text_file_checks_out_with_crlf`:
  `project_memory/staging/user-patch/measure-2026-09-25.txt` carries CRLF on disk (committed in
  08b4d96). Remedy printed by the test: `python tools/normalise_line_endings.py --apply`.

GATES RUN, its own: `DELIVERY_RUN=TSK-0151 python -B -m pytest .claude/hooks/test_gates.py -q -p
no:cacheprovider --tb=line`, 17:15:09 -> 17:34:46: **2 failed, 553 passed**. Both read the hole
store and `docs/POST_V2_WISHLIST.md`, neither of which this order touched:
- `test_the_hole_index_in_the_document_is_the_one_the_items_generate`: BUG-0110 (H18) is
  ACCEPTED_EXCEPTION in the store and TRIAGED in the document -- the lead archived BUG-0110/0111/0115/
  0272 this session. Remedy printed: `python tools/migrate_holes.py --root project_memory --reindex`.
- `test_every_test_a_hole_names_is_one_that_exists`: H138 names
  `tools/test_design_conformance.py::test_a_record_is_written_even_when_the_checks_find_something_and_the_sighting_gate_still_opens`,
  H155 `tools/test_approvals_dispatch.py::test_an_empty_origin_excuses_the_step_while_the_root_criteria_measure_it`;
  on 8677bd2 neither is a `def` (the second is only named in a docstring at line 4852). Pre-existing.

EVIDENCE through the kernel (17:38), each with the naming node(s) in the run command, run at
17:35-17:38 (2 passed / 1 passed):
- EVD-0467 BUG-0306 (+TSK-0151), selection, pass.
- EVD-0468 BUG-0307 (+TSK-0151), selection, pass.
No full-run EVD: the full run is not green, and its two reds are the lead's to clear. No BUG/FR
transition, no commit, no mint.

## 7. Named, not closed

- The codex `fable` row (`gpt-6-astra`) is reached by no shipped ladder (the ladder is
  provider-neutral) -- DEC-0114 (4) keeps the row; whether Codex should climb to it is the user's
  separate question, and a per-provider `top` would be its build (section 1).
- BUG-0307 AC-1's wording vs DEC-0098 (2): encoded per DEC-0098 (section 1).
- The `radar_routine` Instructions for `watcher-duo` differ from the live
  `~/.claude/scheduled-tasks/watcher-duo/SKILL.md` in wording (the live one was written by the lead);
  nothing compares the two, because the task file lives in the app's folder, not in the repo.
- Two stamp runs instead of one (section 4); dev/research at 2026.09.25-2, office at -1.
- `test_hooks_v2.py` and `test_hooks.py` ran only inside the full run, not as own selections.
- Watcher bodies still carry the resolved calendar triggers (2026-07-19/08-31/08-05) -- not in
  this order's items; left alone.
- I read no log or transcript whole; the TSK-0150 transcripts were read by the script only.

## Rework F1 -- fresh builder, 2026-09-25T17:41:12 -> 18:25:37

Task: lead finding F1 (`staging/TSK-0151/lead-finding-1.md`): the Codex top must stay reachable,
Claude must never reach Fable. Read by section: the finding, TSK-0151, DEC-0114, this protocol
(sections 1/2/7 decide), `dispatch.ladder_for_order` / `_reference_rungs` / `spawn_model_refusal` /
`_valid_ladder` / `ladder_declaration`, `cli.py` `ladder`.

**FORM: a provider cap in the tier table, applied by the kernel.** `team-kits/model_tiers.yaml`
gets `provider_top: {claude: opus}` (`dispatch.PROVIDER_TOP_KEY`); `ladder_for_order(..., provider=None)`
lowers the role's top to the highest declared rung that is not above the cap in the reference
order; `None` is the reference platform (found by the pass-through row, as `_reference_rungs`
finds it), which is what the lease and the Claude spawn gate derive for -- so neither changed.
The answer carries `provider` and `model` (the row's id for the rung). `kernel.cli ladder` gets
`--provider`. The four ladders go back to their 8677bd2 VALUES (`top: fable` for dev/research/this
repo, the office-developer's `top: fable` exception) -- parsed equal to 8677bd2, measured 18:02 --
so on Codex the derivation is the one before 8677bd2.
REJECTED: a per-provider `top` in each ladder -- four files (three kits + this repo) carrying the
same provider rule, and office would need it per role as well; DEC-0114 (4) is one rule about one
provider, so it lives once, in the table that already holds the per-provider rows. (The first
builder's `tiers.claude.fable: opus` stays rejected for its three measured reasons.) What the
smaller form does not cover: see "Named" below.
One kernel belt beside it: an answer that still names a capped rung (only a declaration ordering
`rungs:` against the reference order can produce one) is REFUSED, not given.

**`kernel.cli ladder` answers, 18:01:11-18:01:19** (`measure_f1.py` in the scratch dir: a kit store
under its own HOME with copies of the three ladders and the tier table, projects with the kits'
shipped role files, `failed_runs` set in the throwaway task; format provider -> rung/effort (model)):

| kit | role | FAIL | default (claude) | `--provider codex` |
|---|---|---|---|---|
| dev | software-architect | 0 | opus/high (opus) | fable/high (gpt-6-astra) |
| dev | software-architect | 3 | opus/xhigh | fable/xhigh (gpt-6-astra) |
| dev | backend-developer | 0 | opus/high | opus/high (gpt-6-sol) |
| dev | backend-developer | 3 | opus/xhigh | fable/high (gpt-6-astra) |
| research | methodologist | 0 / 3 | opus/high / opus/xhigh | fable/high / fable/xhigh (gpt-6-astra) |
| research | researcher | 0 / 3 | opus/high / opus/xhigh | opus/high (gpt-6-sol) / fable/high (gpt-6-astra) |
| office | office-developer | 0 / 3 | opus/medium / opus/high | opus/medium (gpt-6-sol) / fable/medium (gpt-6-astra) |
| office | bookkeeper | 0 / 3 | sonnet/medium / opus/medium | sonnet/medium (gpt-6-luna) / opus/medium (gpt-6-sol) |

**Test** `tools/test_ladder.py::test_no_shipped_ladder_answer_reaches_the_top_rung_bug_0306`
(rewritten: Claude half as before over every pin/ask/class/fail; Codex half per role -- declared top
fable -> reached, architecture class at FAIL 0, model = the codex row's top id read off the table;
declared top below -> never reached; every shipped ladder keeps at least one Codex climber; the
CLI as a process with and without `--provider`) and
`::test_a_declaration_that_orders_a_capped_rung_below_its_top_is_refused_bug_0306` (the belt).

RED-FIRST, rig `rework_f1.py` (a .git-less copy, binary, refuses to run elsewhere), 18:0x-18:08:
| scenario | result |
|---|---|
| pre-rework tree (8677bd2 kernel, first build's ladders, no cap) | red: `AttributeError: ... no attribute 'provider_tiers'` |
| first build's ladders (`top: opus`, no office exception), rework kernel+cap | red: "dev-team: on Codex no role reaches fable (gpt-6-astra) any more" |
| only the office-developer exception removed | red: "office-team: on Codex no role reaches fable" |
| no `provider_top:` in the table | red: "dev-team (project-manager ...): the Claude answer names fable at failed run(s) [3..9]" |
| kernel: top not lowered (belt stays) | red: the belt refuses "would dispatch TSK-9999 on fable" |
| kernel: top not lowered and belt gone | red: Claude answer names fable at [3..9] |
| CLI drops `--provider` | red: `'codex': ('claude', 'opus', 'opus')` |
| codex capped too (`codex: opus`) | red: "on Codex the escalation never reaches fable" |
| belt removed (belt test) | red: DID NOT RAISE DispatchError |
| clean | green (1 passed, 70 s) |
First cut of the Codex half was red on the first build's ladders only through its floor ("codex
reaches: 0") -- the per-role check derived its expectation from the declaration and so passed a
ladder that had lost its top; the per-ladder "at least one Codex climber" assertion now names it.

Tests adapted (provider-neutral declarations again): `test_the_shipped_declarations_say_what_the_decisions_decided`
(dev/research top fable, office-developer exception), `test_the_build_starts_on_opus_...` (top
fable). Seven ladder-RULE tests in test_ladder.py and two in test_light_kit.py measure the
declaration alone and now say so: `Store.without_the_provider_cap()` drops the cap from their store's
table (their answers climb to the declared fable). `tools/light_kit_pilot.py` records the dispatch
ladder line WHOLE (`_ladder_line`) instead of a 400-char tail -- the capped `why` pushed the sentence
the pilot test reads out of that window (18:11, red; green 18:18).

Texts: the three constitutions' ladder paragraphs (dev/research "top rung **fable**, on Claude capped
at **opus**"; office: the office-developer climbs to fable on Codex), the three lead skills' tier
lines, the four ladders' comments, `model_tiers.yaml` header + the new block, README Models bullet.

STAMP: `bump_kit_version.py` 18:01:53 (dev/research -3, office -2), then AGAIN 18:17:29 (dev/research
2026.09.25-4, office 2026.09.25-3): after the first stamp I rewrote the belt's comment in
`dispatch.py` to name its test (rule 4 (b)) -- a kit file, so a second stamp. Named, not hidden.
Sizes re-recorded 18:02 (validate asked: dev +32, office +46, research +32 bytes); section pins
re-recorded 18:17 (test_shortening_net asked: six sections, every anchor kept). ruff all passed,
validate "all structural checks passed" (after the second stamp and again after the re-pin, both 18:17).

SUITES that read what changed (grep: readers of `model_tiers.yaml`, `ladder.yaml`,
`ladder_for_order`, the kit constitutions/lead skills, the kernel command surface), one selection
at a time (`f1_selections.py`):
| time | selection | result |
|---|---|---|
| 18:08-18:10 / 18:21-18:23 | test_ladder.py | 63 passed / 63 passed |
| 18:10 / 18:23 | test_model_ladder.py | 15 passed / 15 passed |
| 18:10 | test_model_pins.py | 6 passed |
| 18:10-18:11 / 18:17-18:18 | test_light_kit.py | 3 failed (above) / 27 passed |
| 18:11 | test_approvals_dispatch.py -k "ladder or rung or tier" | 0 selected (rc 5) -> whole file 18:19-18:21: 236 passed |
| 18:11-18:12 / 18:18-18:19 | test_context_budget.py + test_shortening_net.py | 1 failed (pins) / 78 passed |
| 18:12 | test_role_contracts.py + test_review_procedure.py | 66 passed |
| 18:12-18:14 | test_repo_hygiene.py + test_radar_trigger.py | 62 passed |
| 18:14-18:15 | test_office_package.py + test_shared_skill_contract.py + test_parity_sources.py | 90 passed |
| 18:15-18:16 | test_hooks.py -k "ladder or tier or model or rung or surface or codex" | 51 passed, 3 skipped |
| 18:16 | test_hooks_v2.py -k "ladder or rung or tier" | 1 passed |
| 18:24-18:25 | the three BUG-0306 nodes (EVD run) | 3 passed |
No full run (the lead decides); `.claude/hooks/test_gates.py` not run (nothing under `.claude/`
changed).

**Named, not closed:**
- The LEASE derives for the reference platform only: `dispatch` has no `--provider`, so on a Codex
  session the dispatch header and its ladder line show the Claude answer (opus), and the Codex
  answer is `ladder <TSK> --provider codex`. Nothing on Codex holds the rung at the spawn
  (`gate_dispatch.SPAWN_TOOLS` are Claude's Agent/Task), so no refusal follows from it -- but the
  header a Codex lead reads is not the Codex answer. Closing it needs a provider on `dispatch` and on
  the lease the Claude spawn gate re-derives against; not built.
- The constitutions tell the lead to pass the header's rung as the Agent call's `model:`; the Codex
  lead has no such instruction and no measured per-spawn model parameter -- unchanged by this rework.
- `test_no_shipped_ladder_answer_reaches_the_top_rung_bug_0306` now takes ~70 s of the ~110 s of
  test_ladder.py (the Claude half walks every pin, ask, class and fail as before; each answer now
  also reads the tier table).
- Two stamps in this rework (above).

EVIDENCE: EVD-0469 (BUG-0306 + TSK-0151, test, pass, selection), the three naming nodes in its
run command, run 18:24:16-18:25:33 (3 passed). No BUG transition, no commit, no mint.

## Rework 2 -- fresh builder, 2026-09-25T19:30:42 -> 20:14:23

Task: `verify-round-1.md` V1-V8. Read by section: the report, TSK-0151, DEC-0114, `lead-finding-1.md`,
this protocol (7 and "Rework F1"), `dispatch.create_lease` / `dispatch_header` / `ladder_line` /
`ladder_for_order` / `provider_tiers`, `cli.py` dispatch+ladder, `gen_provider_artifacts`
`providers_from_project_config`, `report.PROVIDER_MARKERS`. No log or transcript read whole.
Rig `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0151\rework2\rig.py` (a .git-less copy, binary,
refuses any other working directory; "pre-rework2" = the file from the verifier's `verify\tree`).

**FORM for V1: the lease carries the answer PER INSTALLED PROVIDER** (`dispatch.PROVIDERS_KEY` =
`by_provider`, `installed_providers`, `ladders_by_provider`). "Installed for" = the project config's
`providers:` (what the scaffold generates each layer from); the reference row is always in (the
scaffold always installs the Claude layer); no readable list -> every `tiers:` row (the generator's
own default; one provider too many misleads nobody). Lease + header carry `{provider: {rung, effort,
model, top}}`; the top-level `rung`/`effort` stay the reference platform's (the pair the Claude
spawn gate holds -- unchanged); the stderr ladder line appends one entry per provider; `ladder <TSK>`
WITHOUT `--provider` prints the same map, so the command the constitutions name shows the Codex top.
REJECTED: deriving "the" provider from the dispatching session -- no client marker in the
environment is measured in this repo (grep: no reader of a client env variable), and the process
that mints need not be the client that reads the header. What the map does NOT buy: on Codex nothing
holds the rung at the spawn (H173, unchanged), and the task item / lease distribution keep counting
the reference rung -> filed as **H221 / BUG-0308** (mechanism, chain, bound in the item).

| V | what changed | red-first (rig, 19:44-19:55) | green |
|---|---|---|---|
| V1 | kernel: `installed_providers`, `ladders_by_provider`, lease `by_provider`, header key, stderr line, `ladder` map. Texts: 3 constitutions (header per provider; on Codex "apply it by choosing the model, nothing holds it (`H173`)"), 3 lead SKILLs, README Models bullet, dev/research `ladder.yaml`, `model_tiers.yaml` provider_top block -- all now say "in the kernel's answer ... nothing on Codex holds it (H173)". Test `test_ladder.py::test_the_lease_and_the_header_carry_the_answer_for_every_installed_provider_bug_0306` (processes `ladder` + `dispatch`; configs [claude,codex] / [claude] / none) | pre-rework2 kernel: `AttributeError ... no attribute 'PROVIDERS_KEY'`; header drops map: `assert None == {'claude': {... 'rung': 'opus' ...}, 'codex': {'rung': 'fable', ... 'model': 'gpt-6-astra' ...}}`; lease drops map: `KeyError: 'by_provider'`; config ignored: red ("claude only" carries codex); no config = reference only: red ("no line" lacks codex); provider not passed: red (codex answers opus/opus); `ladder` drops map: `KeyError`; stderr line drops map: red (stderr lacks `codex rung fable = gpt-6-astra`) | clean: 7 passed (19:55, all new/changed nodes) |
| V2 | `ladder_for_order`: a start above the (capped) top is held at the top before the escalation counts; the `why` says "held at the top". Test `test_ladder.py::test_a_start_above_the_capped_top_buys_no_effort_at_fail_0_bug_0306` (dev backend-developer, ask fable and pin fable, FAIL 0, Claude; Codex ask granted) | pre-rework2 kernel and hold removed: both `effort xhigh ... raised 1 step(s) by 3 failed run(s) on this rung` | green |
| V3 | `PRICE_RX` as a definition: an amount bound to money (a Unicode `Sc` sign on either side, a currency NAME derived from the Sc characters' Unicode names, an ISO-shaped code on either side) or an amount per a count of tokens; amounts in words are not read and the comment says so. Floor test extended | one tier-table comment line each: control `$15/$75`, `15 $ in / 75 $ out`, `15EUR/75EUR` (euro sign), `15 dollars in and 75 dollars out`, `0.002 per 1K tokens`, `0.002 per 1K`, pound sign + 3, `3 cents`, `10 USD` -- all 9 RED on the bug_0306 node; reader mutations (no sign-after / no names / no rate) RED on the floor node | green |
| V4 | `denied_carried_rows`: a clause in which a negation quantifies "row" (negation BEFORE row) and a word from there on is a carried id or a non-numeric part of one; a negation after the row ("the luna row carries no price") denies something else and is not read | control `no luna row`, `no gpt-6-luna row`, `no row for luna`, `never a gpt-6-sol row` -- all RED on the bug_0306 node; reader mutations (ids only / parts only) RED on the floor node | green |
| V5 | `apply_user_patch.py`: AFTER-present is checked before BEFORE-once | executed check `rig.py v5` on a copy of the unpatched role files, pre-rework2 script: `--check 6 / apply 6 / --check 1 / apply 1`, paragraph count **2** | fixed script: `--check 6 / apply 6 / --check 0 / apply 0`, paragraph count **1** |
| V6 | office template `project_config.yaml`: opus for every role but the office-developer, which climbs to fable -- on Codex; on Claude capped at opus | text only (no reader) | -- |
| V7 | dev/research `settings/settings.json` `"model": "opus"`; the `_comment` of all three kits names the new test. Test `test_model_ladder.py::test_every_kit_settings_names_the_tier_its_bound_lead_pins_bug_0306` | pre-rework2 settings: `dev-team: settings.json names 'fable', the bound project-manager pins 'lead'` | green |
| V8 | synthetic transcript: a later user line naming TSK-0151 in agent a1 | "every user line overrides the prompt": `assert [] == ['a1']` | 2 passed |

STAMP once, 19:55:57: dev-team 2026.09.25-5, office-team -4, research-team -5 (`--check` 20:05:
all unchanged). ruff: all checks passed. validate asked for sizes -> `record_lead_package_sizes.py
--write` 19:56 (+525 / +536 / +525 B, the note names V1); test_shortening_net asked for pins ->
`pin_constitution_sections.py --write` 20:04 (six sections, every anchor kept); validate "all
structural checks passed" 20:04:59.

SUITES that read what changed, each its own process (`rework2/selections.py`):
| time | selection | result |
|---|---|---|
| 19:56-19:58 | test_ladder.py | 65 passed |
| 19:58-19:59 | test_model_ladder.py | 16 passed |
| 19:59 | test_model_pins.py | 6 passed |
| 19:59 | test_measure_agent_tokens.py | 2 passed |
| 19:59-20:00 | test_light_kit.py | 27 passed |
| 20:00 / 20:04 | test_context_budget.py + test_shortening_net.py | 1 failed (pins) / the pin node 1 passed after the re-pin |
| 20:00-20:01 | test_role_contracts.py + test_review_procedure.py | 66 passed |
| 20:01 | test_office_package.py + test_shared_skill_contract.py + test_parity_sources.py | 90 passed |
| 20:01-20:04 | test_reference_skills.py + test_research_chain.py + test_staging_cli.py (lease/header readers) | 127 passed |
| 20:05-20:06 | test_approvals_dispatch.py | 236 passed |
| 20:06-20:07 | test_e2e.py | 20 passed |
| 20:07 | test_report.py | 141 passed |
| 20:07-20:09 | test_repo_hygiene.py + test_radar_trigger.py | 62 passed |
| 20:09-20:10 | test_hooks.py -k "ladder or tier or model or rung or surface or codex or settings or readme or header or lease or dispatch" | 73 passed, 3 skipped |
| 20:10-20:11 | test_hooks_v2.py -k "ladder or rung or tier or header or lease or dispatch or settings" | 68 passed |
| 20:12-20:13 | the six BUG-0306 nodes (EVD run) | 6 passed |
No full run, no `test_gates.py` (nothing under `.claude/` changed).

STATE through the kernel: EVD-0470 (BUG-0306 + TSK-0151, test, pass, selection, the six naming
nodes); BUG-0308 captured with `--hole` -> H221, index regenerated (`migrate-holes --reindex`, 211
holes). No transition, no commit, no mint.

**Named, not closed:**
- H221 / BUG-0308 (above). H173 unchanged: the Codex row is shown and applied by the Codex lead,
  held by nothing.
- The spawn re-derivation (`_assert_the_ladder_answer_holds_locked`) compares the reference answer
  only; `by_provider` is not re-derived at the spawn -- on Codex nothing runs at the spawn (H173).
- Whether the Codex CLI lets a lead choose a subagent's model per spawn is not measured; the kit
  texts say "where the CLI lets you", not that it does.
- `docs/PLAN_ANBIETERFREI.md` not read (not in the item).

## Rework 3 -- fresh builder, narrow scope, 2026-09-25T20:43:33 -> 21:01:21

Task: `verify-round-2.md` R2-1..R2-5 with the lead's orders. Read by section: the report (whole, 98
lines), TSK-0151, this protocol's "Rework 2"; `dispatch.installed_providers` / `ladders_by_provider`
/ `ladder_line`, `cli.py` ladder branch, `test_ladder.py` 400-530, `test_model_ladder.py` 80-230. No
log or transcript read whole. Rig `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0151\rework3\`
(`snapshot.py` saved the five files before the change into `pre\`; `rig.py` a .git-less copy, binary,
refuses any other working directory; `rig.out`). REJECTED for R2-2: a second `ladders_by_provider`
call site in `dispatch` (a `next_lease` builder beside `create_lease`) -- the map belongs to the
answer `ladder` prints and the one loop over both answers keeps the two maps from one function.

| R2 | what changed | red-first (rig 20:51:25-20:52:14) | green |
|---|---|---|---|
| R2-1 | `test_ladder.py::test_the_lease_and_the_header_carry_the_answer_for_every_installed_provider_bug_0306` (the test `model_tiers.yaml` names at the `provider_top` block) extended: a dev build order after three failed runs, `ladder` then `dispatch` as processes; codex = fable/gpt-6-astra at FAIL 3, claude = header rung != fable; the architecture class at FAIL 0 stays the first half. BUG-0306 in the docstring's first paragraph (unchanged) | verifier's M5 (`..., 0, provider)`): RED `the map at the old count equals the climb` | clean |
| R2-2 | `cli.py` ladder: the per-provider map also on `next_lease`, from the same `ladders_by_provider`; comment names the test | pre-rework3 `cli.py`: RED `(None, {... header by_provider ...})`; loop over `(answer,)` only: RED, same line | clean |
| R2-3a | `PRICE_RX`: `(?:%(amount)s)?` after `per`; floor test (renamed `test_the_price_reader_sees_what_it_is_for`, the row half is gone) carries the verifier's `2 per million input tokens`, `15/75 per million` | quantifier back to `%(amount)s?`: RED `AssertionError: 2 per million input tokens` | tier node + floor clean |
| R2-3b | NOT widened. The reader's comment now states what it reads, what it does not ('15 US dollars', 'usd 15', words, '15 input / 75 output per 1M') and its false hits ('CLI 0.131', 'GPT6', '2 marks', '3 mill', 'per token'), measured on the reader 20:47; a false hit fails LOUD (the tier test goes red), none in today's file, so no narrowing -- the lead's list stays as it is. Remainder filed: **BUG-0309** (low, German `limits`, no `--hole` needed) | -- (text + item) | -- |
| R2-4 | REMOVED: `DENIAL_RX`, `denied_carried_rows`, `_flat`; from the tier test the assertion `not denied_carried_rows(text, carried)` (the header half) and from the floor test its five denial and four non-denial lines -- a prose negation reader enumerates negations (the class answer of DEC-0112). The tier file's sentence "no `light` alias and no haiku row" is true by its wording (no haiku row exists); the tier test's docstring says no reader holds it | -- (removal) | tier node clean |
| R2-5 | `test_ladder.py::test_the_installed_providers_are_the_config_list_plus_the_reference_bug_0306` (direct call, seven configs); the docstring of `installed_providers` now names the trimming/case-folding it does and points to the new test | M1 reference only if listed: RED `listed without the reference`; M2 unreadable -> reference: RED `unreadable`; M3 names as written: RED `spelled loosely` | clean: 4 passed (all four touched nodes) |

STAMP once, 20:52:31: dev-team 2026.09.25-6, office-team -5, research-team -6 (`--check` 21:01: all
unchanged). ruff: all checks passed. validate 20:52:35: "all structural checks passed".

SUITES that read what changed, each its own process (`rework3/selections.py`, readers by grep of
`"ladder"`/`next_lease` and of the test-pointer resolvers):
| time | selection | result |
|---|---|---|
| 20:52:53-20:55:07 | test_ladder.py | 66 passed |
| 20:55:07-20:55:17 | test_model_ladder.py | 16 passed |
| 20:55:17-20:56:00 | test_review_procedure.py + test_pointer_sweep.py | 37 passed |
| 20:56:00-20:57:53 | test_repo_hygiene.py | 43 passed |
| 20:57:53-20:58:58 | test_light_kit.py (the stamp) | 27 passed |
| 20:59:30-21:01:01 | the seven BUG-0306 nodes (EVD run) | 7 passed |
No full run, no `test_gates.py` (the lead runs both).

STATE through the kernel: BUG-0309 captured 20:51:01; EVD-0471 (BUG-0306 + TSK-0151, test, pass,
selection, the seven naming nodes) 21:01:12. No transition, no commit, no mint.

**Named, not closed:** BUG-0309 (the price reader's limits, above). Unchanged from rework 2: H221 /
BUG-0308, H173.

## Close-out (verifier round 3, F3-1 and F3-2) -- fresh builder, 2026-09-25

- 21:17:00 F3-1, text only: the `PRICE_RX` comment in `tools/test_model_ladder.py` now names the
  false-hit class the optional figure opened (an amount before "per"/"/" and a bare size word:
  "3/k", "1 / M", "5 per k") and "/token" beside "per token" (a path, "docs/tokens.md"). Reader
  unchanged. BUG-0309 `observed` extended the same way through `kernel.cli update` (rev 1, OPEN).
- 21:17:40 F3-2: case `("a scalar", "providers: %s\n" % reference, every)` added to
  `tools/test_ladder.py::test_the_installed_providers_are_the_config_list_plus_the_reference_bug_0306`.
- 21:18:02-21:18:25 red-first, rig `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0151/closeout/rig.py`
  (byte copies of the working tree): `clean rc=0 | 1 passed`; `m16 rc=1 | 1 failed`, message
  `AssertionError: a scalar` (M16 = `named = [named] if isinstance(named, str) else named` before
  the list check in `dispatch.installed_providers`).
- 21:18:38-21:18:43 real tree: the installed_providers node + `test_the_tier_table_carries_no_price_...`
  + `test_the_price_reader_sees_what_it_is_for`: 3 passed; `ruff check` on both files: clean.
  No kit file touched -> no stamp; `tools/validate.py`: all structural checks passed.
- 21:19:06 EVD-0472 (BUG-0306 + TSK-0151, test, pass, selection, the installed_providers node).
  No transition, no commit, no full run.
