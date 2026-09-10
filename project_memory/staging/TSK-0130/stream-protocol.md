# TSK-0130 -- stream G5-2 protocol (PR-0010: watchers, ladders, escalation)

Role harness-implementer. **Three implementers ran on this item.** The first (Fable 5.1, high) was
stopped by the user a few minutes in on the tier decision DEC-0081; the second (Opus 5, effort high,
DEC-0081) took over the worktree, MEASURED what stood there, kept what held, corrected what did not,
and finished the open sections; the third (Opus 5, effort high) took over after the user's pause
ended the second mid-rework, and did the same to ITS package -- the findings are `R3-1`..`R3-6` at
the end of section 2, the run is run 8, and the cut was re-made because the pause had left patch and
worktree describing two trees. Which is which is said per section, because a handover that hides
its seam is the same defect as a comment that hides a gap.

Worktree `C:/Offline Repos/v2-testbed/_worktrees/g5-ladders` (branch `g5/ladders` off
`feat/harness-v2` at `b7f282e`). Scratch `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0130/`.
Every time below is read off the clock, never extrapolated (DEC-0080 (7)).

## 0. Plan and the rejected alternative (FR-0084 shape)

**Rejected (first implementer, for the mechanic):** deriving rung and effort in the kit hook
`gate_dispatch.py` (three mirrored copies, run at the spawn). It lost because the hook runs AFTER
the lease is minted and the task is LEASED (the DEC-0072 (B) argument), so the record the brief and
the header read would be written by a second reader; the kernel's `create_lease` is the one moment a
dispatch is composed and already derives `worktree`, `hand_back` and `references` there. **The
smaller way** -- one lease field and no re-derivation at the spawn -- would not have covered a
failed run counted between lease and spawn; `validate_dispatch` therefore derives again and refuses
a lease whose answer moved.

**Rejected (second implementer, for the seam work):** *rewriting the five out-of-scope kit texts
that still instruct the retired ladder* -- refused, because `team-kits/*/skills/**`,
`team-kits/office-team/templates/**` and the other two `project_config.yaml` files are outside this
item's `allowed_scope`, and a stream that edits past its boundary is the finding, not the fix. **The
smaller way** -- naming them in the seam table only -- would not have covered the case a seam table
is worst at: a merge that repairs four of five files and leaves the fifth. So the claim became a
two-ended tripwire (`test_no_shipped_kit_text_still_names_the_retired_user_gated_ladder`) plus
BUG-0250, and the prose seam stayed as well.

## 1. What was FOUND in the worktree (the handover measurement)

`git status --porcelain` in the worktree at 22:11, then read file by file:

| Found | Verdict |
|---|---|
| `kernel/dispatch.py` ladder section (+334 lines), `create_lease` / `validate_dispatch` / `dispatch_header` wiring, `cli.py ladder` | KEPT. Read line by line; the `role_tools` refactor is behaviour-identical to b7f282e (diffed against `git show b7f282e:`), the header keeps `parse_header`'s three decided keys, items carry no schema so the three new task fields are tolerated (`state.py` line 21 says so). |
| three `ladder.yaml`, three `gate_dispatch.py` (md5 identical), `model_tiers.yaml`, `gen_provider_artifacts.py`, `validate.py`, the three constitutions, README, radar texts, both watcher definitions | KEPT, with the corrections in section 2. |
| `tools/test_ladder.py` (32), `test_model_ladder.py` (8), `test_radar_trigger.py` (3), edits to `test_model_pins.py` and `test_approvals_dispatch.py` | KEPT and extended (sections 4, 5). |
| `mutation_rig.py` + `mutation_rig.log.json` (19 rows, all red) | KEPT as measurement, and RE-RUN against the shipped tree at 00:51 -- 19/19 red again. |
| `pilot_rig.py` + `pilot_rig.log.json` (3 kits, 22:05:29 -> 22:06:14) and `pilots/` | KEPT and RE-MEASURED live at 22:32:34 (section 4a). |
| `suites.log` | DISCARDED as evidence -- section 2 (b). |
| `staging/TSK-0130/dec-trigger.json` | KEPT and ANSWERED by the user as DEC-0084; its wrong report count corrected in place (section 2 (l)) and the file marked superseded by `dec-trigger-2.json`. |
| five `hole_*.json` drafts in scratch | KEPT, every claim re-measured, then CAPTURED through the kernel; one number in them was wrong and was corrected (section 2 (c)). |

## 2. What was CORRECTED (findings against the first implementer's package)

**(a) A protocol claim the tree did not carry.** The seam table said `team-kits/*/agents/*.md |
office specialists effort: medium (DEC-0078 (2)); no other pin moved`. Measured 22:13:
`git status --porcelain team-kits/office-team/agents` is EMPTY and every office specialist still
carries `effort: high`. Nothing was written there. The row is gone; what it described is the real
gap and is now BUG-0251/H169 plus a seam row. (Whether it SHOULD have been written there: no --
the scaffold stamps `effort:` from the kit's `project_config.yaml` `effort_map`, which is outside
this item's scope, so an edit to the source frontmatter alone is overwritten at the next install.)

**(b) A suite run made under conditions that invalidate it.** `suites.log` recorded five failures in
`test_approvals_dispatch` with rc `3221225794` (`0xC0000142`, Windows DLL-init failure). Measured
cause at 22:25 with `Get-CimInstance Win32_Process`: **two** runner scripts were executing pytest
**concurrently** on this host, which the HOST RULE forbids for exactly this reason. Both were killed
(PIDs 50084/50120/50852/40208, 22:26-22:27). A clean single run of the same suite: **197 passed in
112.21s**. No defect there; the log measured the host.

**(c) A wrong upstream number in a captured claim.** The Codex-spawn hole draft cited
`openai/codex#21753`; the generator comment and `radar/decided.md` both say `#32753`. Corrected in
the item through the kernel (`update BUG-0255`) rather than left as a plausible-looking value.

**(d) An ambiguity the round's own change created.** `README.md` read "Escalation is user-gated
only." in the TEAM PRESET bullet while the same round made the MODEL escalation not user-gated.
Reworded to name which escalation is meant and to point at the ladder bullet.

**(e) Two shipped comments that spelled the retired ladder.** `dev-team/ladder.yaml` and
`research-team/ladder.yaml` explained DEC-0034's T2 as `opus-xhigh` -- the one spelling the new
tripwire refuses. Reworded to "opus at the large-goal effort"; without that the shipped declarations
would have been in their own tripwire's open set.

**(f) A property claim in three shipped files that named code, not a test.** The `classes:` comment
claimed "a build order that reaches this file IS in the build phase". True (both assertions stand at
`create_lease` lines 378/379, above the derivation at 457) -- but SR-0008 (b) makes such a claim a
test. It is now `test_a_build_order_reaches_the_ladder_only_after_the_phase_its_class_assumes`,
named by all three declarations.

**(g) A reader whose weakening no test could see.** `test_model_pins._model_values` was changed to
ask the generator's `rungs()`; its docstring denies the "key in aliases" reading (two of three rows).
Measured: reverting it makes the suite ask about FEWER values and stay GREEN. A count assertion was
added; the revert is now mutation M12 -- red.

**(h) THE DEFECT OF THE ROUND: a rule classified `behalten` was deleted with the ladder paragraph.**
Found by running `tools/test_shortening_net.py`, which the first implementer's suite list did not
contain. The old dev/research §11 bullet carried three things; two are legitimately retired (the
haiku facts, the user-gated ladder) and the THIRD is not: *"QA may classify a fail as
`narrow-mechanical` instead; silently ignoring `escalation: true` is never an option."*
Measured consequences: `docs/reviews/phase0-disposition.md` parity matrix row 43 classifies this
passage `behalten`, and §14a of both constitutions still says "First QA FAIL sets `escalation: true`
(§11)" -- a pointer into a section that no longer explained it. Restored in dev and research, in
each kit's own wording (dev `narrow-mechanical`, research narrow/mechanical -- the research kit
never carried the hyphenated token, and inventing it there would have been a second defect), and
extended with what replaced the user gate. Parity matrix row 43 reclassified from `behalten` to
`bewusst geändert` with its reason; the section pin and the lead-package record re-run with notes.
**And the rule's LEVER is gone**: the dispatcher counts FAILED runs and no classification is part of
that count (`grep -rn narrow team-kits/kernel/` -> no occurrence). Named as **BUG-0260/H178**, and
the constitutions say it plainly instead of implying the old lever.

**(i) Five more failures the first implementer's suite list did not reach** (`tools/test_hooks.py`,
first run 00:0x):
  * `test_gen_accepts_fable_as_lead_tier_pin` asserted `fable -> gpt-5.6-sol`, which is exactly what
    DEC-0076 retires. Rewritten as `test_gen_accepts_fable_as_the_top_rung_pin`, reading the top row
    out of `model_tiers.yaml` (an id spelled in the test would pin it to today's lineup) and
    asserting the top row differs from the lead row.
  * `test_every_span_that_presents_the_command_surface_names_all_of_it`: the new `ladder` command
    made the three constitutions' §0 surface lists incomplete (each named 34 of 35), AND the
    inserted `cli.py` comment spelled `` `dispatch` `` in a code span, which pushed that block to
    three surface words and made it read as a presentation of the whole surface. **Measured that
    this is the round's doing and not pre-existing**: with `b7f282e`'s `cli.py` restored in a copy
    outside the repo the same test is rc 0 (`probe_surface_before.py`, 00:0x). Fixed on both ends --
    the three lists name `ladder`, the comment stops spelling a second command in a code span and
    says why.
  * three tests (`test_the_four_commands_...`, `test_a_shell_less_specialists_result_...`,
    `test_a_role_writes_its_own_craft_memory_...`) plus two in `test_hooks_v2.py`
    (`test_the_trust_message_...`, `test_the_lead_of_a_scaffolded_project_...`) scaffold a project
    from a store under `tmp_path` and then mint a lease with the DEVELOPER'S OWN `~/.claude` still
    in the environment. Since DEC-0078 (4) the lease reads the kit's `ladder.yaml` out of the
    RUNNING home's store, so all five were refused with the DEC-0078 sentence. The fixtures were
    under-specified, not the kernel: they now point the running home at the store they installed
    from, the path composed once inside `_project_the_installers_produce`.

### After the verification round 1 (harness-verifier, `verify-round-1.md`, verdict FAIL)

The verifier read the whole package against the running code, ran 23 own mutations over the FULL
suites and three own pilots as processes, and confirmed AC-3/AC-4/AC-5 PASS, AC-6 PASS but for the
brief half (an item defect: AC-6 demands the display and `forbidden_scope` forbids `report.py` --
BUG-0249 stands and the merge writes the line), AC-7 PASS with B1, AC-1/AC-2 partial as expected.
Two blockers and six residues, all reworked here:

**(j) B1 -- a sentence about the filing pair that the declaration does not carry.** The office
constitution and `office-team/ladder.yaml` said the pair "keeps `sonnet`/`low` as the named
exception". Measured (the verifier's pilot and mine agree): `exceptions:` carries only
`effort: low`; `sonnet` is the PIN under `classes: reading: pin`, and a FAILED run climbs the rung
to `opus`. Behaviour is DEC-0078-conform, the SENTENCE was false (house rule 3). Both texts now say
what happens -- starts on the pin, effort fixed low, still climbs -- and name the open user
question. Two new readers, because the verifier asked for one:
`tools/test_ladder.py::test_the_filing_pair_starts_on_its_pin_at_low_effort_and_still_climbs`
loads the SHIPPED office declaration and measures both halves against the kernel, and
`tools/test_model_ladder.py::test_a_text_that_names_an_excepted_role_says_whether_its_rung_still_climbs`
holds every text that names an excepted role to whether that role's rung still climbs -- in BOTH
directions, so the day the user answers with `top: sonnet` the test demands the other sentence.
Red-first: rig rows **M13**, **M14**, **M15**.

**(k) B2 -- four schedule claims in the enforcement layer.** `gate_spawn_needs_item.py:11/:14/:74`
(the last inside a live refusal text) and `_harness.py:2849` still say the watchers "run on a weekly
schedule", no test reads them, and the reworded watcher definitions point AT that text.
`.claude/hooks/**` is forbidden to this item, so the owed step is a named hole: **BUG-0264/H182**,
with the mechanism, the `limits` (the sentences grant nothing -- the exemption hangs on
`harness_item:`, never on the word) and the pointer at `test_radar_trigger.TEXTS` as the reader that
would have caught them.

**(l) F3 -- a growing number in shipped text.** "twelve runs in nine weeks" was wrong twice over
(measured: 14 dated reports, of which two predate the split and eleven are `-claude`). It is gone
from `radar/README.md` and from the test docstring, and the count now lives where it is derived:
`tools/radar_routine.py --describe` (`"reports"`). `dec-trigger.json` is corrected in place and
marked superseded by DEC-0084.

**(m) F4 -- the kit top lowers a pin, and only the lease said so.** Confirmed with my own fixture:
`top: sonnet` + `pin: opus` dispatches on sonnet. The docstring of `ladder_for_order` said "a class
floor never LOWERS a pin" and nothing about the top. It now states the case, and
`tools/test_ladder.py::test_a_top_below_a_pin_lowers_it_and_the_answer_says_so` measures BOTH the
lowering and the visibility (`why` names pin and top; the `dispatch` line carries it). Red-first:
rig row **M16**. No kernel change: the cap is the rule, the silence was the defect.

**(n) F5 -- three journal lines named a category the matrix does not carry.** "durch Mechanik
ersetzt" is not in the declared vocabulary; the lines now say `bewusst geändert`, and the
office entry no longer claims a row 43 reclassification for a kit that is not among row 43's
sources.

**(o) F6 -- "refuses a spawn that would run below the rung"** was an under-claim in three
constitutions: `spawn_model_refusal` compares for EQUALITY, so a higher model is refused too (the
shipped test measures it). All three now say "any spawn whose `model` is not the rung, a higher one
included".

**(p) F7 -- `radar/decided.md:30`** promised "the round measures the ceiling directly". It could
not (no Codex CLI). The line now says so and points at BUG-0254/H172.

**(q) F8 -- `.ruff_cache` in two template trees** removed.

### After the pause: the handover round (THIRD implementer, Opus 5 high, DEC-0081)

The user's pause ended the second implementer mid-sentence, between the desktop-shape rework
(worktree edits 16:45-16:49) and the run that would have certified it (`suites7.log` was killed at
92% of `test_hooks`, `stream-ladders.patch` still described the tree of 10:39). A third
implementer took the item over and did what the seam demands: measure what stands, correct what
the last correction broke, re-cut ONE consistent package. Findings of this round are numbered
`R3-n`.

**(R3-1) The correction contradicted itself inside its own file.** `dec-trigger-2.json` a4 states
in so many words that "every report was started by a person" is unwarranted -- and the same file's
`a_note_on_counts`, four keys further down, still ended on exactly that sentence. Corrected there;
the superseded `dec-trigger.json` carries two sentences of the same kind in its body (`reports`:
"every one of them started by a person", "No mechanism has ever started a run") and now carries the
correction beside them under `corrected_after_the_fact`, rather than a rewritten history.

**(R3-2) Three shipped citations named the wrong item.** `tools/test_radar_trigger.py` cited
`FR-0089` for the desktop task in its module docstring, at `DISCLAIMER_RX` and in the desktop
test's docstring. Measured: `project_memory/inbox/active/FR-0089.yaml` is the user's
cost/benefit wish about multi-agent vs. one strong agent (created 2026-09-06T16:30:57) and records
nothing about a scheduled task. A pointer that resolves to the wrong record is worse than none.
The finding now HAS an item: `BUG-0269`/`H186`, captured through the kernel from
`hole_desktop_task.json`, with the second consequence (the unsuffixed report name) and its
`limits`; the three citations name it.

**(R3-3) The desktop rework widened the claim reader in the fail-open direction.** To let the
honest desktop sentence through, `DISCLAIMER_RX` gained `only fires while` and
`state .{0,24}unknown` -- a CONDITION on a mechanism and an admission about its STATE, neither of
which says that nothing here can rely on it. Any claim can wear both. Measured on the reader
itself, every spelling in its own copy of the tree in one run (`disclaimer_probe.log.json`,
18:52:05): **each alternative exempts exactly the claim that wears it** -- with `only fires while`,
"The claude.ai routine starts both watchers on a weekly schedule and only fires while the account
has quota" is no claim at all; with `state ... unknown`, the same sentence ending "its state
unknown" is no claim; with `no promise` (the spelling this round shipped for one hour before
measuring it), the same sentence ending "which is no promise" is no claim. As shipped -- ONE
alternative, naming the non-reliance itself (`cannot|nothing here can ask/count on it`) -- all
three are claims again and the desktop sentence stays exempt. The guard test carries all three
claim sentences and the shipped README wording; rig rows **M30** (condition) and **M31** (state)
restore the two widenings -- both red.

**(R3-4) The inserted paragraph broke the pointer of the sentence it was inserted into.**
`radar/README.md` read "... `starts_itself` stays blind to it on purpose. That sentence is
measured, not modest, and it is guarded: ..." -- after the insertion "that sentence" named the
desktop sentence rather than the state sentence the guard actually holds, on a 175-character line
no wrap had touched. The paragraph is now two: the state and its guard, then the two measured
facts beside it (nobody records who started a report; the desktop task, what it cannot promise,
and that its unsuffixed report leaves the radar half owed).

**(R3-5) A claim of my OWN that did not survive its own check, reported rather than dropped.** I
first measured the kernel capture route as "refused to the Bash tool, allowed to PowerShell" and
was about to write that down. Re-measured before writing: `PYTHONPATH=team-kits python -B -m
kernel.cli --root project_memory doctor` is rc 0 in Bash, with and without a `cd` prefix. What
gate 1 refuses is the same line with the host rule's `timeout 120` in front of the interpreter --
a starter word, which `_harness._executed_words` reads. So the finding is an over-refusal of a
starter-prefixed kernel line, not a shell asymmetry; `.claude/hooks/**` is forbidden to this item,
so it is reported here and to the lead and nothing is filed under PR-0010, which it does not
belong to.

The user answered the first proposal with NEITHER option: "Wie jetzt auch: ueber eine Claude
Routine! So wie auch der Project Auditor laufen sollte! Macht er das ueberhaupt?" -- recorded as
**DEC-0084**, which orders the measurement before the build. Everything below is a process
measurement with its log file under `_round-scratch/TSK-0130/`; the clock is read.

### 3a. THE USER'S QUESTION: does the project-auditor routine actually run?

Measured on a scaffolded dev-team pilot, every step as a PROCESS (`routine_probe.py`,
`routine_probe.log.json`, 2026-09-06 07:26:15 -> 07:26:18), plus two entry-point calls at 07:27.

| Question | Answer | The measurement |
|---|---|---|
| Is it DECLARED? | **yes** | `session_status.py` is registered on `SessionStart` in the project's own `settings.json`; the shared `hooks/_routine.py` names `AUDIT_ROLE = project-auditor` and an ISO-week period (`2026-W36`); `.claude/agents/project-auditor.md` is installed. |
| Is it REPORTED DUE? | **yes** | With an empty event log the hook printed: `ROUTINE DUE (2026-08-31): the project-auditor has not run in 2026-W36 (last run in this project's event log: none) - propose it to the user and spawn it yourself; no hook starts a run.` |
| Does a RUN clear it? | **yes** | One record written by the project's own `notify_agent_events.py` as a process (`{"event": "subagent_stop", "reason": "project-auditor"}`) -- the notice is gone. |
| Does the CADENCE bring it back? | **yes** | The same record moved eight days back -- the sentence returns, now naming the older run. |
| Does the PM get to SPAWN it? | **NO, not on its own route** | The constitutions say the dispatch rides on an `APR.kind: routine` or `analysis`. On the pilot's INSTALLED entry point: `request-approval routine PR-0001` -> `invalid choice: 'routine' (choose from acceptance, delivery, document_proposal, document_revision, filing_correction, filing_rule, hole_exception, kit_update, plan, preset, push, scope)`; the same for `analysis`. Neither kind has a producer -- `H111`, re-measured four weeks on. |
| What DOES work? | an ORDINARY work order | `create-task --type analysis --assigned-role project-auditor --allowed-scope docs/audit/` -> `TSK-0003` -> `READY` -> `dispatch` -> a lease (rung `opus`, DEC-0034 rule 5). So the auditor runs only as a task that CARRIES A WRITABLE SCOPE -- exactly what the routine route exists to prevent, and `create-task` makes `--allowed-scope` mandatory. |

**In one sentence for the user:** the auditor is reminded every week, reliably and measurably, and
is never started by itself; the read-only route the constitutions describe does not exist in the
program, so today he can only be run as an ordinary order with write permissions. Captured as
**BUG-0266/H184**, citing `H111` and neighbouring `H158` (which stays true for a different reason:
in THIS repository, which runs no kit, nothing surfaces the run at all).

### 3b. WHAT A "CLAUDE ROUTINE" IS ON THIS HOST -- four candidates, a probe each

Three were probed while the mechanism was being decided; the fourth was found afterwards, on the
host rather than in the repository, and is measured here read-only (`BUG-0269`/`H186`).

| Candidate | Exists? | Survives a session end | Survives a week without a session | Can write into this local `radar/` |
|---|---|---|---|---|
| the kits' own routine feed (`hooks/_routine.py` + `session_status.py`) | yes, measured in 3a | **yes** (recomputed from the event log at every session start) | **no** -- it speaks only when a session starts, and starts nothing by design (DEC-0028) | yes, the run it proposes does |
| Claude Code's session cron (`CronCreate`/`CronList`/`CronDelete`) | **yes** -- a denying `PreToolUse` hook SAW the call arrive with keys `cron`, `prompt` | **no** | no | n/a |
| the platform's remote routines (`RemoteTrigger`) | **yes** -- params `action, body, cursor, session_id, trigger_id` | **yes** | **yes** | **no** |
| a Claude **Desktop** scheduled task, found later (`BUG-0269`/`H186`) | **yes, and it was there all along** -- `~/.claude/scheduled-tasks/radar-watcher/SKILL.md`, untouched since 2026-06-30, radar half only | the FILE does; whether the TASK does is **unmeasurable from here** -- its enabled flag is in the Desktop app | **unknown**, same reason, and it fires only while that app is open | it writes `radar/<date>.md` -- unsuffixed, so the routine counts it as **nobody's** run, and nothing here can ask it |

Measured lines:

- `claude --version` 2.1.258; `claude --help` lists 18 subcommands and **none** of them schedules
  anything (`agents, attach, auth, auto-mode, doctor, gateway, import, install, logs, mcp, plugin,
  project, respawn, rm, setup-token, stop, ultrareview, update`) -- `routine_platform_probe.log.json`,
  07:28:36.
- Session cron, `routine_survival_probe.log.json`, 07:29:53 -> 07:31:21: session A created a weekly
  job and `CronList` returned `31158c95 - Every Monday at 6:00 AM (recurring) [session-only]` --
  the platform's own label -- and the schema adds "Recurring tasks auto-expire after 7 days". A
  SECOND `claude -p` process in the same directory: `LIST: empty`. That is the survival question
  answered by two processes, not by a sentence.
- `ScheduleWakeup` also exists (`delaySeconds`, `reason`, `noop`) and schedules a later wake-up
  INSIDE a running session's `/loop` mode.
- The DESKTOP task, measured here 2026-09-06 after a research agent of another stream found it
  (re-read by the third implementer in the handover round -- the minute was not recorded, so none
  is written here: 1093 bytes, mtime 2026-06-30 10:53:59, the ONLY entry under
  `scheduled-tasks/`); it says "Follow .claude/agents/radar-watcher.md exactly",
  "Write radar/<today YYYY-MM-DD>.md" and "do NOT commit"; `schtasks` lists no Windows task.
  **What it forces me to correct:** the round said "every report was started by a person". No
  report records WHO started it. The two oldest carry exactly the unsuffixed name this task
  writes; every later one carries a `-claude`/`-codex` suffix the task's instruction does not
  produce. So the true sentence is "no report records who started it", and it now stands in
  `radar/README.md` and in the test module's own docstring. The shape is recordable under
  `other_shapes` in `radar/routine.json` and is never counted by `starts_itself` -- a mechanism
  whose state cannot be read is not one this repository may promise
  (`test_a_desktop_task_is_reported_and_never_counted_as_live`, mutations **M28**/**M29**).
  **The second consequence, added in the handover round:** the name that task writes carries no
  watcher suffix, and `--due` tells the two watchers apart BY that suffix -- so even a successful
  desktop run leaves the radar half owed, and on a cloud-routine day it is a second file for the
  same week. That is not a new claim needing a new test: it is the behaviour
  `test_the_routine_counts_a_run_per_watcher_and_per_period` already asserts on a temporary
  directory ("a report with no watcher suffix cleared a named watcher's duty"). Filed with its
  limits as `BUG-0269`/`H186` (payload `hole_desktop_task.json`); the file lives in the user's
  home, outside every stream's allowed scope, so only the user can retire or align it.
- `RemoteTrigger`, `remote_trigger_probe.log.json` / `remote_trigger_list_probe.log.json`, 07:32:
  it drives the claude.ai remote-trigger API and creates or starts a routine that runs in a CLOUD
  session; outlives a session, recurs. A READ-ONLY `action: list` returned
  `{"data":[],"has_more":false}` -- the account holds no trigger today (nothing was created: a
  routine in the user's account is a side effect nobody approved). What it needs: a reachable
  REMOTE repository the sandbox can clone. What it writes back: a commit/PR in that remote or a
  session log at claude.ai -- **never into this local working tree**. (The clause that stood
  here, "and this repository is deliberately not pushed", was FALSE and is corrected in 3d:
  `origin` is github.com/GiaZenX/harness.git and `feat/harness-v2` is on it.)

**The measured limit, stated plainly (DEC-0084 (4)):** nothing on this host both survives a week
without a session AND writes a dated report into this `radar/` **as a file**. That last word is
the one my proposal dropped, and dropping it turned a small limit into a rejection -- see 3d. So the stream did not build option
B silently; it built the shape the user named and proposed once more --
`project_memory/staging/TSK-0130/dec-trigger-2.json`, three options (A the routine as built, B plus
a cloud routine on a pushed copy, C A plus repairing the auditor's route first), recommendation A
now and C next.

### 3c. WHAT WAS BUILT, and the end-to-end run

`tools/radar_routine.py` -- the declaration in the auditor's shape: both watchers, a weekly cadence
in ISO weeks, and three answers.

- `--describe` gives the declaration as JSON, including `starts_itself`, which is **derived** and
  not a constant somebody can flip. (This paragraph described the FIRST derivation, a reading of
  `.claude/settings.json`; DEC-0085 replaced it with the record of the cloud routine, and round 2
  measured why the old one had to go -- 3d, R2-2.) `tools/test_radar_trigger.py` reads that field
  and lets a text go exactly as far as it goes.
- `--due` gives which watcher owes a run this ISO week, derived from the dated reports in `radar/`
  by suffix. It also retires the growing number F3 complained about: the count lives in
  `--describe` (`"reports": 15`), never again in prose.
- `--run <watcher>` starts that watcher headless and reports which dated file appeared, read off
  the DIRECTORY before and after rather than off the model's own account of itself.

**END TO END, started by the mechanism** (`routine_end_to_end.json`): `python tools/radar_routine.py
--run codex-watcher`, started 07:45:18, finished 07:49:04, `rc 0`,
`"new_reports": ["2026-09-06-codex"]`, `"still_due": []`. The file `radar/2026-09-06-codex.md`
(7598 B, 105 lines) is in the shipped report shape, reviewed `radar/decided.md` first as the role
demands, and -- measured, not arranged -- it read the routine itself: "`python
tools/radar_routine.py` reports 'no watcher owes a run in 2026-W36' ... This run happened anyway
because the harness-lead explicitly asked for it, not because the routine says one is due." That is
AC-1's end-to-end run and AC-2's next codex report in one.

**What is NOT built and is a named seam:** the session-start line that would make the lead ask
`--due` (`.claude/settings.json`, `.claude/agents/harness-lead.md` -- both in the item's
forbidden_scope), and, since DEC-0085, the cloud routine itself: the lead creates it, and
`starts_itself` stays False until the lead records it. What the reader measures is the record, not
a registration -- see 3d.

### 3d. DEC-0085: the mechanism is the platform's CLOUD routine -- and a claim of mine was false

The user answered the second proposal: "So wie beim Radar watcher. So eine Routine. Eine Claude
Routine. Geht das nicht?" -- recorded as **DEC-0085**. The lead corrected one of my measurements,
and I re-measured it myself before writing anything on it:

**MY CLAIM WAS FALSE.** `dec-trigger-2.json` said "this repository is deliberately not pushed", and
built the whole rejection of the cloud routine on it. Re-measured 2026-09-06:
`git remote -v` -> `origin https://github.com/GiaZenX/harness.git`; `git ls-remote --heads origin`
-> `refs/heads/feat/harness-v2` at **b7f282e**, plus `main` and `legacy-v1`. I had read CLAUDE.md's
rule "no push without the user's approval" as "never pushed" instead of asking the remote -- a
statement about the WORLD derived from a statement about POLICY. The proposal is corrected in place
and marked superseded; this paragraph is the correction's own record, because a round that quietly
fixes its own false premise teaches nothing.

**What changes with it:** the cloud sandbox CAN clone this repository, so the third candidate of 3b
is not ruled out at all -- it cannot write into the local working TREE, which is a different and
much smaller limit. A report comes back as a commit on a branch and a pull request.

**What this stream built for it** (the lead holds `RemoteTrigger`; the implementer roles hold no
such tool and created nothing):

- `tools/radar_routine.py --describe` now emits the WHOLE specification the lead needs to run
  `RemoteTrigger create`: per watcher the complete, self-contained PROMPT; the cadence with a day
  and a time each (radar-watcher Monday 06:00 UTC, codex-watcher Tuesday 06:00 UTC -- one day
  apart so two cloud runs never race for the same base commit or stack two PRs on one day); the
  remote and base branch; the branch pattern `radar/{date}-{watcher}`; the PR title pattern
  `radar: {watcher} {date}`; what the run may write and what it may never touch; and the limits.
- **The prompt is self-contained on purpose, and the reason is measured**: the sandbox clones
  `feat/harness-v2` as the remote holds it, which today is `b7f282e` -- the commit BEFORE this
  round, still carrying the schedule sentences this round removed. A prompt that said "do what
  radar/README.md tells you" would be steered by the text this round replaced. So the duties are
  in the prompt and the repository files are named as reading for context.
- `starts_itself` is derived from `radar/routine.json`, the record the LEAD writes after creating
  the trigger (shape published in `--describe`). **What makes a recorded trigger LIVE is four
  fields, all of them values the API returns** (`LIVE_TRIGGER_FIELDS`): a watcher this routine
  declares, a trigger id, `enabled: true`, and a `next_run_at`. A disabled trigger and one with no
  next run start nothing, so neither may let a text say a schedule runs. **No string search** --
  the reading this replaced asked `stem in json.dumps(hooks)` over `.claude/settings.json`, and the
  round-2 verifier measured what that came to: a hook running a DIFFERENT file whose name contained
  the stem answered true, and so did a matcher that merely mentioned the file (R2-2). No record ->
  the texts must still say who starts a run. A record naming a live trigger -> they may say the
  cloud routine does, and must then say a report arrives as a PR.
- `--run` **asks `--due` before it starts anything** and refuses a second run in the same ISO week
  unless `--force` is given, naming the cost in the refusal (R2-5): the verifier measured two runs
  of one watcher on one day, each about four minutes and a hundred thousand tokens, the second
  rewriting the same dated file and reporting `new_reports: []` afterwards.
- The cadence is stated where a reader meets it, in the words that are true: **one run per ISO
  week, not one every seven days** (R2-8) -- in `--due`'s own output and in `--describe`.
- `tools/test_radar_trigger.py` walks BOTH states on sentences it writes itself
  (`test_the_two_states_of_the_schedule_claim`), through the one rule reader
  `schedule_claim_offence`, so neither branch waits for the repository to reach it.
- `radar/README.md` and both watcher definitions now describe the two halves; triage stays the
  lead's in both.

**Three more findings of the round-2 verification, folded in here** (its full report is
`project_memory/staging/TSK-0130/verify-round-2.md`):

- **R2-3, the sharpest one**: the climb text reader asked whether the word "climb" OCCURRED, not
  what the sentence SAID. The verifier changed the office paragraph to "a FAILED run **never
  climbs** its rung above sonnet" -- the exact opposite claim, with the word still in it -- and the
  suite stayed green (46 passed). `asserts_a_climb` now reads the denial (never / not / cannot /
  no longer / keeps its rung / stays on its rung), `test_the_climb_reader_reads_the_statement_and_
  not_the_word` walks both directions on literal sentences, and the verifier's own W1 sentence is
  mutation **M25** -- red.
- **R2-7**: the report the routine produced said `radar/decided.md` held "six accepted, two
  rejected" of its own findings. Measured: seven `codex-0905-` rows, **five accepted, two
  rejected**. Corrected in the report itself, with the correction named in the line -- a dated
  report is evidence of the mechanism, not scripture, and a false count in it is a defect like any
  other.
- **R2-6**: two numbers in `dec-trigger-2.json` (reports, weeks) were stale inside the round.
  Both proposals now point at `--describe` for the count and keep only the claim that does not
  grow: no ISO week without a report between the first and the newest, every one started by a
  person.

**A defect of my own, found by my own test and reported rather than quietly fixed:** the claim
reader could not SEE the new claim shape. "Both watchers are started weekly by the claude.ai
routine trg_..." carries none of the four claim words, so the reader looked past it -- and past its
false twin, the same sentence without where the report arrives. `automation_claims` now also treats
a sentence naming a RECORDED trigger id as a claim; the ids come from the declaration's record, so
nothing is guessed. Mutation **M23** restores the blindness and goes red. A second one: the first
cut of `cloud_prompt` built the text from adjacent string literals and Python fused two of them
without the newline between them ("... and skip   every item ..."), which the lead would have
pasted into the trigger unchanged. It is one template now, and
`test_the_cloud_prompt_states_every_duty_the_declaration_names` looks for every duty as a WHOLE
LINE and refuses a line carrying a run of blanks.

**WHAT THE LEAD DOES NEXT, and what is still owed to this protocol.** The `--describe` output is
handed to the lead verbatim. The lead runs `RemoteTrigger create` per watcher with the prompt and
the cadence, `RemoteTrigger run` once, reads `list_runs` / `get_run_log`, writes `radar/routine.json`
with the returned ids, and hands back: the trigger ids, the run log, the PR link. **Those three are
the end-to-end evidence for the cloud half and they are NOT in this protocol yet** -- the row below
is the place they go, and until they are there the cloud half is declared and tested but not
observed. What IS observed end to end is the session half: `--run codex-watcher` produced
`radar/2026-09-06-codex.md` (section 3c).

| owed from the lead | where it lands |
|---|---|
| trigger ids per watcher + `created_at` / `next_run_at` | `radar/routine.json` (shape in `--describe`), and this table |
| the `get_run_log` of the first `RemoteTrigger run` | this protocol, as the cloud half's end-to-end line |
| the PR link of that run | this protocol, and the merge decides it |

**WHERE THAT NOW HAPPENS (handover to the merge, 2026-09-06 19:2x):** this package is delivered
into the generation-5 merge (TSK-0133) and the g5-ladders worktree is a read-only reference from
here on, so the lead writes `radar/routine.json` (data, no code) on the MERGED tree once the two
cloud routines exist, and the round-3 measurement of PR-0010 AC-1 -- a run started by the mechanism
writing a dated report -- is taken there under PR-0010 / TSK-0133, not in this stream.

**SEAM SENTENCE for G5-1** (`.claude/agents/harness-lead.md`, not written by this stream): "The
radar routine has two halves. At session start ask `python tools/radar_routine.py`: it names any
watcher that owes a run this ISO week, and `--run <watcher>` starts one here. Separately, REVIEW
THE OPEN `radar/` PULL REQUESTS -- the claude.ai routine you created opens one per weekly cloud run
(`radar: <watcher> <date>`), it may only add `radar/<date>-<watcher>.md`, and merging it is what
brings the report into the working tree. Triage stays yours; the run never writes
`radar/decided.md`. After creating or changing a trigger, record its id and timestamps in
`radar/routine.json` -- `tools/radar_routine.py --describe` publishes the shape, and the texts about
the cadence are held against that record."

**Cost and limits, stated in the shipped texts and in `--describe.limits`:** a report arrives as a
PR, not a file; the run needs the remote reachable and the account's routine quota; a run that
cannot clone produces nothing and `--due` is what notices; triage stays the lead's.

## 4. Per-criterion acceptance

### AC-1 (trigger) -- DECIDED twice, BUILT in two halves; the cloud half awaits the lead's run

- **Decided** DEC-first (DEC-0084), then **measured first** as that decision orders (section 3a/3b),
  then built: `tools/radar_routine.py`, the routine in the shape the kits declare the
  project-auditor run in.
- **Measured once end to end, started by the mechanism**: `--run codex-watcher`, 07:45:18 ->
  07:49:04, rc 0, `radar/2026-09-06-codex.md` appeared -- detected by the routine reading the
  directory before and after, not by the model's account (section 3c).
- Texts: `radar/README.md` ("How a run starts") and both watcher definitions now name the routine
  and say who starts a run. `tools/test_radar_trigger.py` (6 tests) holds them against
  `--describe`, and the field that decides how far they may go (`starts_itself`) is DERIVED from
  the registrations rather than declared.
- Red-first: **B4** (b7f282e's three texts, `1 failed`), **M3** (the subject drops a watcher),
  **M17** (the self-start reader stops asking the registrations), **M18** (the starter reader
  matches everything), **M19** (a report of the other watcher clears this watcher's duty).
- **The CLOUD half (DEC-0085)**: declared in full by `--describe` -- prompts, cadence per watcher,
  branch and PR patterns, what a run may and may not write, the record shape, the limits. The LEAD
  creates it with `RemoteTrigger create`; this stream holds no such tool and created nothing. Both
  states of the schedule claim are tested (`test_the_two_states_of_the_schedule_claim`), and the
  new mutations M20-M23 are red. **Not yet observed**: the trigger ids, the first `get_run_log` and
  the PR link -- section 3d names the three and where they go.
- **NOT built, named**: the session-start registration that would ask `--due` for the lead
  (`.claude/settings.json`, `.claude/agents/harness-lead.md` -- forbidden here, seam sentence in
  3d), and my own false premise about the remote, corrected in 3d rather than quietly dropped.

### AC-2 (codex report, `max` vs `ultra`) -- report half CLOSED by the routine; the ceiling stays open

- **The next codex report was produced by the built trigger in the shipped shape**:
  `radar/2026-09-06-codex.md`, started by `tools/radar_routine.py --run codex-watcher` (section 3c).
  It reviewed `radar/decided.md` first as its role demands and reported no new item.
- The `max` vs `ultra` ceiling is still NOT measured: the Codex CLI is not installed on this host
  (`codex` not on PATH, no npm global; `~/.codex/config.toml` exists and pins `gpt-6-astra` /
  `model_reasoning_effort = "high"`). `model_tiers.yaml` states the contradiction and claims **no**
  ceiling (DEC-0076 (3)). Item: **BUG-0254 (H172)**, and `radar/decided.md` now points at it
  instead of promising the spike (F7).
- Triage: the seven `codex-0905-*` lines in `radar/decided.md` already point at PR-0010, and the
  items a change follows from now exist (BUG-0092 plus BUG-0249..0255, BUG-0260). Two of those
  lines asked for a code comment rather than an item (`codex-0905-interrupt-event`,
  `codex-0905-subagentstart-payload`) and both comments are in `gen_provider_artifacts.py`. Nothing
  was appended to `decided.md`: a decided line is a pointer and the pointers are correct.

### AC-3 (three rungs, DEC-0076) -- CLOSED

- `team-kits/model_tiers.yaml`: `aliases` = lead/worker; `tiers.claude` = fable/opus/sonnet;
  `tiers.codex` = gpt-6-astra / gpt-5.6-sol / gpt-5.6-terra. **The ids are the codex radar report's,
  not re-fetched from the vendor by this round** -- named as not done.
- `gen_provider_artifacts.py`: `rungs`, `table_places`, `unplaceable_pin_sentence`; `provider_model`
  reads the row by rung name (the `rev` dict is gone); `provider_neutral_model` excludes alias
  TARGETS; `main()` and `providers_from_project_config` ask `table_places` instead of a seven-word
  set.
- The `.codex` overlay: measured -- no shipped agent carries a `codex:` overlay at all, so the
  consistency AC-3 asks for is the table's translation, and
  `test_the_top_rung_translates_to_every_providers_own_top_row` reads it.
- Red-first: **B1** (b7f282e's table, 4 failed), **B2** (b7f282e's generator, 2 failed), **B5**
  (b7f282e's constitutions, 1 failed), **R11**, **R12**, **M2**, **M12**.
- Templates measured for fallout: no `model_map` in any kit template carries `light`, so the new
  refusal breaks no scaffold (the word survives only in COMMENTS -- BUG-0250).

### AC-4 (BUG-0092, both providers) -- CLOSED

- Price anchors reworded to the measured figures; the dead watch dates (2026-08-05, 2026-08-31) are
  gone; Opus 4.1's shutdown stays as a dated FACT in the anchors (BUG-0092 AC-1), not as a watch;
  one watch date remains (2026-11-21, Sol promotional pricing).
- `test_no_watch_date_in_the_tiers_table_lies_in_the_past` -- RED against b7f282e's file (rig row
  **B1**). `test_the_watch_date_reader_reads_the_block_and_only_the_block` mutates both edges (a
  date above the marker is not read; a missing marker is refused, not read as empty) -- rig row
  **R13**.
- MAINTENANCE header names the route (capture + `related_pr`, never a `decided.md` line, BUG-0092);
  `test_the_maintenance_header_names_the_finding_to_item_route` reads it and also asserts the header
  no longer calls the mechanic an open work item (AC-7).

### AC-5 (rollout line) -- CLOSED, see section 8

### AC-6 (escalation mechanic) -- CLOSED except the BRIEF half, which is out of scope and filed

Built in `kernel/dispatch.py`: `kit_installation`, `ladder_declaration`, `_valid_ladder`,
`_store_aliases`, `role_pin` (+ `_role_frontmatter` shared with `role_tools`),
`count_failed_run_locked`, `ladder_for_order`, `_assert_the_ladder_answer_holds_locked`,
`spawn_model_refusal`, `ladder_line`; `create_lease` derives and writes rung/effort on the lease and
on the task; `dispatch_header` carries them; `validate_dispatch` re-derives and, given a spawn
payload, holds the Agent call's `model` against the rung; the three `gate_dispatch.py`
(byte-identical, md5 `fd1712bf268653ed04b68cff42ab60f1`) pass `tool_input.model`. `cli.py`:
`ladder <TSK>` plus the `dispatch` stderr line. Declarations:
`team-kits/{dev,research,office}-team/ladder.yaml`.

**No kit-name branch, no default ladder -- measured rather than asserted:** every kernel test in
`tools/test_ladder.py` runs against kits the kernel has never heard of (`kit`, `odd-kit`,
`bare-kit`, `some-kit`, `no-such-kit`); the shipped names appear only in the one test that compares
declarations with the user's decisions. A kit-name branch would make those fixtures fail.

**Platform facts this rests on** (rigs `probe-agent-model`, `probe-agent-override`; the JSON re-read
by the second implementer):

- the Agent tool's `tool_input` carries `model` when the lead passes it -- the recorded payload's
  key set is exactly `description, model, prompt, run_in_background, subagent_type`, with
  `model: "opus"` and **no `effort` key** although the prompt asked for one;
- a child pinned `sonnet` spawned with `model: opus` ran on opus (`modelUsage` carries both
  `claude-sonnet-5` for the parent and `claude-opus-5[1m]` for the child).

**Tests** (`tools/test_ladder.py`, now 33): rule 1
`test_planning_and_architecture_start_on_the_top_rung_and_the_build_on_its_pin` and
`test_a_build_order_reaches_the_ladder_only_after_the_phase_its_class_assumes` (new, 2 (f));
rule 2 `test_an_order_that_failed_climbs_one_rung_per_failed_run_capped_at_the_top`,
`test_a_lease_that_produced_no_child_counts_no_failed_run`,
`test_every_way_from_a_started_run_back_to_ready_passes_failed` (the premise, derived off
`AUTOMATA`); rule 3
`test_a_change_touching_the_architecture_lifts_that_order_to_the_top_and_the_next_build_falls_back`;
rules 4/5 `test_design_and_qa_start_above_the_build_floor_and_a_floor_never_lowers_a_pin`;
effort `test_the_effort_follows_the_goals_class_and_an_exception_fixes_it`;
endpoints `test_an_exception_moves_one_roles_top_and_the_climb_stops_there`;
refusals `test_a_kit_without_a_ladder_declaration_is_refused_at_dispatch`,
`test_a_record_that_is_present_but_unreadable_is_refused_not_ignored`,
`test_a_malformed_declaration_names_the_field_it_refuses` (11 mutations),
`test_a_role_without_a_class_and_a_role_without_a_readable_pin_are_refused`,
`test_a_pin_that_is_an_alias_resolves_through_the_stores_tiers_table`;
kit-less `test_a_project_without_a_scaffold_record_gets_no_rung_and_no_refusal`;
the spawn `test_a_spawn_below_the_lease_rung_is_refused_and_one_that_names_it_passes`,
`test_an_answer_that_moved_between_lease_and_spawn_is_refused`,
`test_the_shipped_spawn_gate_holds_the_rung_as_a_process`;
surface `test_the_entry_point_shows_the_answer_and_the_dispatch_line_carries_it`;
declarations `test_every_kit_ships_a_declaration_the_kernel_accepts`,
`test_every_kit_role_has_a_class_and_every_classed_role_ships`,
`test_the_shipped_declarations_say_what_the_decisions_decided`.

**Threshold (rule 2):** `escalation.failed_runs_per_rung: 1` in every declaration, carrying its DEC
line. It is the user's rule of 2026-08-10. **Said plainly: the pilot measured that the mechanic
climbs WITH this value; it did NOT measure that 1 is the right value** -- that needs failing runs of
real work, not a scripted FAIL. DEC-0034 names the number as one pilots may still move; this round
did not move it and does not claim to have tuned it.

**The `started` stamp is CONSUMED** by `count_failed_run_locked`. The docstring claims nothing else
reads it; re-measured with a grep over `team-kits/` and `tools/` -- the only other occurrence is the
WRITE in `dispatch.spawn_outcome` (line 1206). The mutation `pop` -> `get` is rig row **R4**, red.

**What the mechanic does NOT do, said plainly:** EFFORT is derived, written and shown, never forced
-- the platform has no per-spawn effort parameter (measured above), so the child runs on its
installed `effort:`. For office that is `high` today although the declaration derives `medium`
(BUG-0251/H169). The SESSION BRIEF shows neither value: `report.generate_session_brief` builds each
`active_tasks` row from a named field set. **Measured 22:18:14** on the dev pilot -- the task item
carries `rung: fable` / `effort: xhigh`, the freshly generated brief's row carries `id`, `status`,
`assigned_role` and nothing else. `kernel/report.py` is in this item's forbidden_scope:
BUG-0249/H167 plus a seam row. On Codex the Agent tool is not hookable
(`CODEX_UNSUPPORTED_TOOLS`), so the spawn-side hold is Claude-only (BUG-0255/H173); the lease, the
header and the task answer are provider-neutral.

### AC-6a pilots -- the mechanic as a PROCESS on a scaffolded pilot per kit

Rig `pilot_rig.py` (refuses to run outside its directory, binary-safe; log `pilot_rig.log.json`,
22:05:29 -> 22:06:14). Per kit: home store = copy of the worktree's `team-kits`; project scaffolded
by `init_project_memory.ps1` + `scaffold_team.ps1 -Preset team|full`; the handover marker cleared the
honest way (the kit's own `clear_handover_marker.py` as a process with a `SessionStart` /
`source: startup` payload -- the rig's first run had every hook probe refused with the marker
sentence, which is the installer's restart rule working); root captured and orders created/readied
through the INSTALLED entry point; scope approval minted through the kit's approval hook; then
`ladder`, `dispatch`, the project's own `gate_dispatch.py` as a process on three Agent payloads
(wrong model / no model / the rung -- in that order, because a passing probe claims the lease), a
FAILED run through `submit_result`, `transition ... READY --approved-retry`, `ladder` again, and the
store's `ladder.yaml` renamed away for one `dispatch`.

| kit / role (pin) | class | header rung / effort | gate: wrong / none / rung | after 1 FAILED + retry | no declaration |
|---|---|---|---|---|---|
| dev software-architect (opus) | architecture | fable / xhigh (PR class large) | 2 / 2 / 0 | fable (top) | rc 1, DEC-0078 sentence |
| dev backend-developer (sonnet) | build | sonnet / xhigh | 2 / 0 / 2 (second claim) | opus | |
| research methodologist (opus) | architecture | fable / high (RQ normal) | 2 / 2 / 0 | fable | rc 1 |
| research researcher (sonnet) | build | sonnet / high | 2 / 0 / 2 (second claim) | opus | |
| office bookkeeper (sonnet) | build | sonnet / medium (PROC: no class) | 2 / 0 / 2 (second claim) | opus | rc 1 |
| office records-clerk (sonnet) | reading | sonnet / low (exception) | 2 / 0 / 2 (second claim) | opus | |
| office office-developer (opus) | build | opus / medium | 2 / 0 / 2 (second claim) | fable (exception top) | |

Every refusal line starts `[team-kit gate_dispatch] specialist spawn refused.`; the `dispatch`
stderr carries the WHY line, copied from the log (dev architect):
`ladder: rung fable, effort xhigh (fable: pin opus, class architecture starts on top, 0 failed run(s), top fable; effort xhigh: the goal's class is large)`.

**RE-MEASURED LIVE at 22:32:34** on the surviving office pilot, because a table copied from a log is
a claim: `harness.py ladder TSK-0002` (records-clerk) -> `rung sonnet, effort low`,
`next_lease.rung opus` with
`"opus: pin sonnet, class reading starts on pin, 1 failed run(s), top opus; effort low: the exception fixes it"`;
`ladder TSK-0003` (office-developer) -> `rung opus, effort medium`, `next_lease.rung fable` with
`top fable`. Both match the table.

**A reading this stream did NOT decide and names for the user:** rule 2 climbs the FILING PAIR too --
after one failed run a `records-clerk` order runs on opus (at effort `low`). DEC-0047 puts that pair
at sonnet-low as a deliberate FLOOR and says nothing about a ceiling, and DEC-0034 rule 2 has no
exception, so the built behaviour follows both. If the user meant the pair never to leave sonnet,
that is one line in `office-team/ladder.yaml` (`exceptions: records-clerk: {top: sonnet}`) and a
question for the lead, not a kernel change.

### AC-7 (decided vs built) -- CLOSED for what is in scope; the rest is BUG-0250

- Code cites DEC-0034/0047/0076/0077/0078 in `dispatch.py` (ladder section), the three
  `ladder.yaml`, `model_tiers.yaml`'s header, `gen_provider_artifacts.py` (DEC-0076).
- Constitutions: dev §11 / research §11 / office §7 ladder paragraphs rewritten to what is built;
  `test_the_constitutions_ladder_paragraph_says_what_the_declaration_says` reads paragraph and
  declaration together, per kit. The office paragraph states the effort gap in plain words, so no
  constitution claims the office runs at medium. §0's command surface list in all three names the
  new `ladder` command.
- The restored QA/escalation bullet and parity matrix row 43: section 2 (h).
- **Five shipped kit files still instruct the retired ladder, all outside this item's scope.**
  Measured, filed as **BUG-0250/H168**, and guarded from both ends by
  `test_no_shipped_kit_text_still_names_the_retired_user_gated_ladder`.
- Records: `tools/lead_package_sizes.json` (+987/+1504/+993, then +634/+650, then +10/+10/+10) and
  `tools/constitution_section_pins.json`, both appended through their own tools with `--note`, both
  journalled in `docs/reviews/phase0-disposition.md`.
- **SEAM SENTENCE for G5-1** (`.claude/agents/harness-*.md`, NOT written by this stream): "Model
  pins of this repo's own roles: `model: opus` / `effort: high` for implementer and verifier,
  `fable` for the lead's session -- three rungs (DEC-0076), placeable per `tools/test_model_pins.py`;
  this repo runs no kit and therefore no `ladder.yaml`, so its dispatches carry `ladder: absent` and
  the role runs on its pin (`kernel.dispatch.kit_installation`)."

## 5. Reader mutations (DEC-0080 (6))

Two rigs, both under `_round-scratch/TSK-0130/`, both refusing to run outside their own directory,
both opening every file with an explicit newline policy (`newline=""`), both copying the worktree
WITHOUT its `.git`. Every row: the reader mutated in the direction its docstring denies, the named
arbiter run against the MUTATED COPY. **Both re-run against the shipped tree at 00:51-00:52.**

**Rig 1** (`mutation_rig.log.json`) -- 14 reader mutations and 5 restore-the-defect rows,
**19 of 19 red**:

| row | reader / defect restored | arbiter | red line |
|---|---|---|---|
| R1 | `kit_installation` reads an unreadable record as "no kit" | `test_a_record_that_is_present_but_unreadable_is_refused_not_ignored` | 1 failed |
| R2 | `ladder_declaration` reads a missing `ladder.yaml` as "no ladder" | `test_a_kit_without_a_ladder_declaration_is_refused_at_dispatch` | 1 failed |
| R3 | `_valid_ladder` stops checking `top` is a rung | `test_a_malformed_declaration_names_the_field_it_refuses[top]` | 1 failed |
| R4 | `count_failed_run_locked` remembers the stamp | `test_a_lease_that_produced_no_child_counts_no_failed_run` | 1 failed |
| R5 | `ladder_for_order` lets a class floor LOWER a pin | `test_design_and_qa_start_above_the_build_floor_and_a_floor_never_lowers_a_pin` | 1 failed |
| R6 | `ladder_for_order` climbs past the role's top | `test_an_exception_moves_one_roles_top_and_the_climb_stops_there` | 1 failed |
| R7 | `validate_dispatch` stops re-deriving at the spawn | `test_an_answer_that_moved_between_lease_and_spawn_is_refused` | 1 failed |
| R8 | `spawn_model_refusal` lets a silent spawn through on a climbed order | `test_a_spawn_below_the_lease_rung_is_refused_and_one_that_names_it_passes` | 1 failed |
| R9 | the kit hook stops passing `model` to the kernel | `test_the_shipped_spawn_gate_holds_the_rung_as_a_process` | 1 failed |
| R10 | `dispatch_header` stops carrying rung and effort | `test_the_header_and_the_task_carry_the_rung_and_effort` | 1 failed |
| R11 | `rungs()` counts the effort-field row as a rung | `test_every_provider_declares_exactly_the_three_rungs` | 1 failed |
| R12 | `table_places` answers True for everything | `test_the_generator_refuses_a_retired_rung_pin_with_a_sentence_naming_the_decision` | 2 failed |
| R13 | the watch-date reader reads the whole file as the block | `test_the_watch_date_reader_reads_the_block_and_only_the_block` | 1 failed |
| R14 | the claim reader reads lines instead of sentences | `test_the_claim_reader_reads_what_it_claims` | 1 failed |
| B1 | b7f282e `model_tiers.yaml` restored | four table/watch/header tests | 4 failed |
| B2 | b7f282e `gen_provider_artifacts.py` restored | the generator refusal test | 2 failed |
| B3 | b7f282e `dispatch.py` restored (no ladder at all) | three ladder tests | 3 errors |
| B4 | b7f282e radar README + both watchers restored | `test_no_text_claims_a_schedule_the_repo_does_not_build` | 1 failed |
| B5 | b7f282e three constitutions restored | `test_the_constitutions_ladder_paragraph_says_what_the_declaration_says` | 1 failed |

B3 is red as **collection errors**, not assertion failures: with b7f282e's `dispatch.py` the module
constants the tests name (`LADDER_FILE`, `RUNG_KEY`) do not exist. Red without the fix, but the
weakest of the nineteen rows and reported as such.

**Rig 2** (`mutation_rig2.log.json`) -- the readers rig 1 did not mutate, **plus a CONTROL row**,
13 of 13 as expected:

| row | reader / mutation | arbiter | outcome |
|---|---|---|---|
| M0 | CONTROL: unmutated full-tree copy | `python tools/validate.py` | **GREEN**, "all structural checks passed" -- so M2's red below is the mutation's |
| M1 | `_store_aliases` answers with no aliases | `test_a_pin_that_is_an_alias_resolves_through_the_stores_tiers_table` | red |
| M2 | `provider_neutral_model` back to refusing every reference row | `python tools/validate.py` | red: "research-team/agents/project-manager.md: model 'fable' ..." |
| M3 | the radar reader's subject drops one watcher | `test_the_texts_this_reads_are_the_ones_that_describe_the_watchers` | red |
| M4 | the office declaration forgets a shipped role's class | `test_every_kit_role_has_a_class_and_every_classed_role_ships` | red |
| M5 | the office declaration raises its top to fable | `test_the_shipped_declarations_say_what_the_decisions_decided` | red |
| M6 | `ladder_line` stops carrying the derivation | `test_the_entry_point_shows_the_answer_and_the_dispatch_line_carries_it` | red |
| M7 | the kernel loses the `ladder` command | the same test | red |
| M8 | `kit_installation` reads an unstaged kit as "no kit" | `test_a_record_that_is_present_but_unreadable_is_refused_not_ignored` | red |
| M9 | the open set loses an entry that still claims (spread end) | `test_no_shipped_kit_text_still_names_the_retired_user_gated_ladder` | red |
| M10 | the open set gains a file that claims nothing (dead-entry end) | the same test | red |
| M11 | the retired-ladder reader spells today's rungs/efforts | `test_the_retired_ladder_reader_reads_both_vocabularies_off_the_shipped_files` | red |
| M12 | the pin suite's row reader tells rungs apart by alias names | `test_the_reader_refuses_what_the_table_cannot_place_and_demands_no_tier_be_pinned` | red |
| M13 | the office declaration pins the filing pair's rung (`top: sonnet`) while the texts still say it climbs | `test_a_text_that_names_an_excepted_role_says_whether_its_rung_still_climbs` | red |
| M14 | the office constitution goes back to "keeps sonnet/low as the named exception" (B1) | the same test | red |
| M15 | the filing pair stops climbing in the kernel while the shipped texts say it does | `test_the_filing_pair_starts_on_its_pin_at_low_effort_and_still_climbs` | red |
| M16 | the kit top stops capping downwards, so a pin above it is no longer lowered (F4) | `test_a_top_below_a_pin_lowers_it_and_the_answer_says_so` | red |
| M17 | the self-start reader stops asking the registrations and answers True | `test_the_self_start_reader_answers_off_the_registrations` | red |
| M18 | the starter reader matches everything, so "who starts a run" stops being asked | `test_the_starter_reader_reads_a_named_starter_and_nothing_else` | red |
| M19 | the routine counts a report of the OTHER watcher as this watcher's run | `test_the_routine_counts_a_run_per_watcher_and_per_period` | red |
| M20 | `live_triggers` counts a record entry that carries no trigger id | `test_the_self_start_reader_answers_off_the_recorded_triggers` | red |
| M21 | the schedule rule stops asking where a report arrives once a routine is recorded | `test_the_two_states_of_the_schedule_claim` | red |
| M22 | the cloud prompt stops forbidding `radar/decided.md` | `test_the_cloud_prompt_states_every_duty_the_declaration_names` | red |
| M23 | the claim reader ignores the recorded trigger ids again (the blindness 3d found) | `test_the_two_states_of_the_schedule_claim` | red |
| M24 | the climb text reader asks for the WORD again, not the statement (R2-3) | `test_the_climb_reader_reads_the_statement_and_not_the_word` | red |
| M25 | the office constitution DENIES the climb the declaration gives -- the verifier's own W1 | `test_a_text_that_names_an_excepted_role_says_whether_its_rung_still_climbs` | red |
| M26 | `--run` stops asking `--due` and starts a second run in the same period (R2-5) | `test_a_second_run_in_the_same_period_is_refused_unless_it_is_asked_for` | red |
| M27 | `live_triggers` counts a DISABLED trigger as live (R2-2) | `test_the_self_start_reader_answers_off_the_recorded_triggers` | red |
| M28 | the record counts a desktop task as a live trigger (`BUG-0269`) | `test_a_desktop_task_is_reported_and_never_counted_as_live` | red |
| M29 | `--describe` stops reporting the other shapes at all | the same test | red |
| M30 | the claim reader excuses a schedule sentence for carrying a CONDITION again (`only fires while`, R3-3) | `test_the_claim_reader_reads_what_it_claims` | red |
| M31 | the same exemption keyed on an admission about the mechanism's STATE (`state ... unknown`, R3-3) | the same test | red |

Rig 2 is **32 rows** after the DEC-0085 rework, the round-2 rework and the handover round -- one
control, 31 red, all as expected (last full run 2026-09-06 19:05:24 -> 19:09:12, against the same
tree the patch and run 8 describe, `every row as expected: True`). **M28 and M29 were GREEN on their first run and are
reported as such**: the test read the reader directly instead of the declaration, and the
desktop entry it used carried none of the fields a merge would have let through. The test
now reads `--describe` and adds an `other_shapes` entry dressed in all the live fields, so
the KIND decides and not the fields -- both rows red afterwards. A mutation that stays green
is worth reporting; one that is quietly dropped is not. M17 was retargeted when the reader it mutated was rebuilt: it used to flip a
`starts_itself` constant, then a settings reading, and now the record reading -- a mutation
row that no longer names what it mutates is a row that measures nothing. Two of
them are corrections of my OWN first attempt and are reported as such: the first M17 flipped a
`starts_itself` CONSTANT and stayed **green**, which is what turned that field into a derived
reader (`starts_itself()` asks the registrations) with its own both-ends test; the first M18
produced a syntax error rather than a behaviour change and was rewritten to a pattern that matches
everything. A mutation that goes red for the wrong reason is worth no more than one that stays
green.

**One more measurement of the same kind, outside the rigs** (`probe_surface_before.py`): with
`b7f282e`'s `cli.py` restored in a copy, `test_every_span_that_presents_the_command_surface_names_all_of_it`
is rc 0 -- so its failure in this round was the round's own comment and not a pre-existing red.

## 6. Suites run

Only the READING suites (DEC-0080 (2)); the full surface belongs to the merge, and no
`DELIVERY_RUN` prefix was used. The list was derived, not remembered -- `grep -rln` over
`tools/*.py` for `create_lease`, `validate_dispatch`, the conftest dispatch helpers
(`drive_task_to`, `leased(`, `dispatch_header`), `architect_step_owed` / `presets.installation`,
and `gen_provider_artifacts` / `model_tiers` -- plus `test_shortening_net`, `test_context_budget`
and `test_disposition` (the three that read the constitutions, the lead package and the
disposition, which this round moved) and `test_finance_dashboard` (which no grep reaches and the
first implementer's list carried). One pytest at a time, every run with a timeout.

**THE AUTHORITATIVE RUN is run 5** (`suites5.log`, START 2026-09-06 07:56:32 -> DONE 09:00:26),
started after the last edit, the re-pin, the two records and the version bump, so nothing in it
straddles a change. **26 suites -- 4347 passed, 14 skipped, ONE failed** (counts added up from the log, not estimated), and that one failure is not this stream's:

| suite | result | | suite | result |
|---|---|---|---|---|
| test_ladder | 35 passed | | test_report | 119 passed |
| test_finance_dashboard | 52 passed | | test_staging_cli | 98 passed |
| test_model_ladder | 11 passed | | test_board | 77 passed |
| test_radar_trigger | 6 passed | | test_research_chain | 10 passed |
| test_model_pins | 5 passed | | test_review_procedure | 18 passed |
| test_shortening_net | 36 passed | | test_presets | 34 passed |
| test_context_budget | 42 passed | | test_kitupdate | 86 passed, 1 skipped |
| test_disposition | 8 passed | | test_backlog_types | 51 passed |
| test_role_contracts | 30 passed | | test_state | 60 passed |
| **test_repo_hygiene** | **1 failed**, 30 passed | | test_hooks | 1004 passed, 13 skipped |
| test_approvals_dispatch | 197 passed | | test_hooks_v2 | 2138 passed |
| test_kernel | 131 passed | | test_e2e | 20 passed |
| test_parallel_streams | 31 passed | | test_reference_skills | 18 passed |

`test_repo_hygiene` -- and the number depends on the SHAPE of the tree, which is why round 2
found a second failure where run 5 reported one (R2-4). Measured by me, both shapes, 10:33:36 -> 10:36:45
(`repo_hygiene_two_shapes.log.json`): in the WORKTREE, with its real `.git`, **1 failed / 30 passed**
(`test_every_hole_has_a_row_in_the_summary_and_every_row_has_a_hole`); in a COPY that is `git init`-ed
after the fact -- the verifier's rig shape -- **2 failed / 29 passed**, the second being
`test_the_known_out_of_scope_trace_is_still_the_only_exception`. Both are the same cause --
**PRE-EXISTING at b7f282e and not this stream's**: both read `docs/POST_V2_WISHLIST.md`, which
this stream never touched (it is not in the patch) and which carries 0 `### H` entries since the
generation-4 hole migration. Another stream already filed it as **BUG-0258/H176**.

`python -m ruff check .` -- all checks passed. `python tools/validate.py` -- all structural checks
passed, after `python tools/bump_kit_version.py` (final stamp **2026.09.06-2** for all three kits).

**THE CONSISTENCY RUN (R2-1), run 7** (`suites7.log`, START 2026-09-06 09:52:25 -> DONE 10:33:08):
one runner, one log, one tree -- started after the LAST edit of the DEC-0085 rework so that patch,
worktree, rig log and protocol describe the same tree, which is exactly what round 2 blocked on.
Subject: every suite that reads a file this round touched after run 5.

| suite | result | | suite | result |
|---|---|---|---|---|
| test_radar_trigger | 9 passed | | test_disposition | 8 passed |
| test_model_ladder | 12 passed | | test_role_contracts | 30 passed |
| test_ladder | 35 passed | | **test_repo_hygiene** | **1 failed**, 30 passed (see above) |
| test_model_pins | 5 passed | | test_hooks | 1004 passed, 13 skipped |
| test_shortening_net | 36 passed | | test_hooks_v2 | 2138 passed |
| test_context_budget | 42 passed | | | |

The remaining 15 suites of run 5 read no file this round touched afterwards and keep their run-5
result; they are listed above. **The host rule was broken twice in this round, by me**: two runner
scripts wrote to one log (once inherited from the first implementer, once my own at 09:48), which
is how a truncated log first read as "all green, seven suites". Run 7's script refuses to start
while another runner is live, which is the one line that would have prevented both.

**THE HANDOVER RUN, run 8** (`suites8.log`, START 2026-09-06 17:27:04 -> DONE 18:42:25), started
after the last worktree edit of the handover round. Run 7 is superseded by it and is NOT the
package's run: the user's pause killed it at 92 % of `test_hooks`, so it has no `DONE` line and no
result for the two hook suites -- a log that stops mid-suite is not evidence, which is the same
rule that discarded the first implementer's log in section 2 (b). Subject: every suite that reads
a file this round touched (the two hook suites among them, and `test_staging_cli`, which reads
`radar/`), one pytest at a time, each with a timeout.

| suite | result | | suite | result |
|---|---|---|---|---|
| test_radar_trigger | 10 passed | | test_disposition | 8 passed |
| test_model_ladder | 12 passed | | test_role_contracts | 30 passed |
| test_ladder | 35 passed | | **test_repo_hygiene** | **1 failed**, 30 passed (BUG-0258/H176, see above) |
| test_model_pins | 5 passed | | test_hooks | 1004 passed, 13 skipped |
| test_staging_cli | 98 passed | | test_hooks_v2 | 2138 passed |
| test_shortening_net | 36 passed | | `python tools/validate.py` | rc 0, all structural checks passed |
| test_context_budget | 42 passed | | `python -m ruff check .` | rc 0, all checks passed |

Two files were touched AFTER that run -- `tools/radar_routine.py` (the `BUG-0269` citations) and
`tools/test_radar_trigger.py` (citations, the tightened `DISCLAIMER_RX`, three guard sentences) --
so the suites that read them were re-run on the FINAL tree: `test_radar_trigger` 10 passed
(18:51), `test_repo_hygiene` 1 failed / 30 passed (18:59:35, the same pre-existing one),
`python -m ruff check .` rc 0 and `python tools/validate.py` rc 0 (18:59:35). The remaining suites
of run 8 read none of the changed lines. The subject was derived, not remembered: `grep -l radar
tools/*.py` names six suites (`test_radar_trigger`, `test_model_ladder`, `test_shortening_net`,
`test_staging_cli`, `test_repo_hygiene`, `test_hooks`) and all six ran in run 8; only the first
loads the changed reader, and `test_repo_hygiene` was re-run afterwards because it walks every
tracked file.

Earlier runs, kept for the record and superseded by run 5: run 3 (25 suites, 23:10:05 -> 00:03:25,
the two `test_hooks*` failures of section 2 (i)), run 4 (12 suites, 00:09:34 -> 00:50:05, those two
green again). The first implementer's own log is discarded as evidence for the reason in
section 2 (b).

## 7. Deliberately not closed, named (hole items, kernel-allocated)

All captured through
`PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory capture BUG --hole`, each with
`related_pr: PR-0010` and a `limits` line.

**(R3-6) The pointer index had NOT been regenerated, although this section said it was.** Measured
in the handover round: `git status` of the repository listed `docs/POST_V2_WISHLIST.md` as
UNCHANGED, and the summary table ended at `H165` -- every hole this round captured (and every one
five other rounds captured before it) was missing from it. `migrate-holes --reindex` run at 17:36
rewrote it from the store: **176 holes**, 21 rows added, `H186` among them. Two things the reader
should know about that table and neither is this round's to fix: its new rows link to
`docs/holes/H<n>.md` files that exist only for the migrated holes (up to `H165`), and
`test_repo_hygiene::test_every_hole_has_a_row_in_the_summary_and_every_row_has_a_hole` is red
before and after for the reason `BUG-0258`/`H176` names -- the document carries no `### H` entry
at all since the generation-4 migration, so the reader aborts before it ever looks at a row.

| item | hole | what is open |
|---|---|---|
| BUG-0249 | H167 | the session brief does not show `rung`/`effort` -- `report.py` builds the row from a named field set and is in this item's forbidden_scope. Measured 22:18:14 on the dev pilot. |
| BUG-0250 | H168 | five shipped kit files still instruct the retired user-gated ladder (two `SKILL.md`, three `project_config.yaml`), plus `session_status.py`'s own `lead/worker/light` map and the scaffold's `light -> haiku` lines. All outside scope; guarded from both ends by a shipped tripwire. |
| BUG-0251 | H169 | the EFFORT axis is derived, written and shown but never applied -- no per-spawn effort parameter exists (measured); for office the stamped `high` contradicts the declared `medium`. |
| BUG-0252 | H170 | a `PROC` root carries no `class`, so office's `large` effort is unreachable today. |
| BUG-0253 | H171 | a project without a scaffold record (this repository) dispatches with `ladder: absent` -- deliberate under DEC-0078 (4), and a DEC-first question for the lead. |
| BUG-0254 | H172 | the Codex effort ceiling (`max` vs `ultra`) is unmeasured: no Codex CLI on this host. |
| BUG-0255 | H173 | on Codex the spawn-side hold does not exist (the Agent tool is not hookable there). |
| BUG-0260 | H178 | a QA fail classified narrow/mechanical still climbs the rung: the classification is invisible to the dispatcher, which counts FAILED runs. The lever parity matrix row 45 gave QA no longer reaches the model. |
| BUG-0264 | H182 | four schedule claims survive in `.claude/hooks/` (`gate_spawn_needs_item.py:11/:14/:74`, `_harness.py:2849`), one of them inside a live refusal text, read by no test -- and the reworded watcher definitions point at them. `.claude/hooks/**` is forbidden to this item (verifier finding B2). |
| BUG-0269 | H186 | a watcher can be started from OUTSIDE this repository: the Claude Desktop scheduled task of section 3b. Its schedule and enabled flag live in the Desktop app, so nothing here can ask it; the report its instruction writes carries no watcher suffix, so `--due` counts it as nobody's run. `limits`: `starts_itself` never counts such a shape, the texts may not promise it, the task's own instruction confines it to `radar/`, and the file lives in the user's home -- outside every stream's allowed scope, so only the user can retire or align it. |
| BUG-0266 | H184 | the project-auditor routine is reminded but cannot be dispatched on its own route: `request-approval` offers twelve kinds and neither `routine` nor `analysis`, so the auditor runs only as an ordinary order with a writable scope. Measured as a process on a dev pilot (DEC-0084 (2)(b)); confirms H111 four weeks on, neighbours H158. |

**Not a hole but a question for the user** (section 4a): whether the office filing pair should climb
at all. **And one pre-existing red this stream did not cause and did not fix**: BUG-0258/H176.

## 8. Rollout line (AC-5)

How the changed ladder and the mechanic reach the user's projects -- four steps, no automatic bump
(the `model_tiers.yaml` header rule, DEC-0076 (5)):

1. **Stamp.** The merge runs `python tools/bump_kit_version.py`; the three kits carry a new
   `version:` and a new `content:` hash over the kit tree (`kernel.hashing`). This stream's
   provisional stamp is **2026.09.06-2** for all three; the merge restamps, so it will move.
2. **Global store install.** The user runs the repo's installer, which copies the kits into
   `~/.claude/team-kits/`. Nothing in a session may do this: `gate_write_scope` refuses every
   write-capable line naming `.claude` or `team-kits`.
3. **`update-kit` in the project.** At the project's NEXT session start the kit shim reports the
   newer store version; the PM runs `python scripts/harness.py update-kit`, which stages the
   release, writes the new `.claude/` tree and sets the handover marker -- and then asks for a
   session restart, because settings, the agent set and the session agent bind at session start.
4. **First dispatch after the restart.** `create_lease` reads the kit's `ladder.yaml` **out of the
   store** (not out of the project), derives rung and effort, and writes them on the lease, the
   header and the task item.

**The order of 1-3 is not cosmetic, and this round measured what happens when it is broken:** five
suite tests scaffolded a project from one store and then minted a lease with a DIFFERENT store in
the environment, and every one was refused with the DEC-0078 sentence naming the kit, the file and
the store path (section 2 (i)). That is the fail-closed direction working -- a project whose store
copy has no `ladder.yaml` dispatches nothing and says why -- and it is also the reason step 2 must
precede step 3 for every project on the machine.

**What a project sees when its pinned model no longer exists.** Two different answers, both measured:

- *The pin is a rung the table cannot place* (a `light`/`haiku` pin surviving in a project's
  `project_config.yaml`): the generator refuses BEFORE it writes anything, with one sentence naming
  the value, DEC-0076 and the pins that would have worked, plus "provider artifacts were left
  untouched" (measured as a process,
  `test_the_generator_refuses_a_retired_rung_pin_with_a_sentence_naming_the_decision`). At dispatch
  the same shape is a refusal from `ladder_for_order`: "role X pins Y, which is neither a rung of
  kit Z's ladder (...) nor an alias model_tiers.yaml resolves to one".
- *The pin resolves in the table but the PROVIDER has retired the model*: nothing in this repo can
  see that -- it is the watchers' standing duty. On Codex the community evidence is a loud 400
  (`radar/decided.md codex-0905-missing-pin-400`), on Claude a `model_not_found` at spawn
  (`docs/reviews/2026-09-02-model-pin-and-bom-measurement.md`). That is why AC-1's trigger matters
  and why `tools/test_model_pins.py` asserts every shipped pin resolves in the table.

## 9. Seam table (received / expected at merge)

| Seam | Received from this stream | Expected at merge |
|---|---|---|
| `team-kits/kernel/cli.py` | ONE block: the `ladder` command + the `dispatch` stderr line | G5-1/G5-3 add their own blocks |
| three constitutions | the ladder paragraph (§11 dev/research, §7 office), the restored QA/escalation bullet (dev/research), and `ladder` in the §0 surface list | G5-1 comment-discipline duty + CR rule; G5-3 office correspondence role |
| `team-kits/*/agents/*.md` | **NOTHING WRITTEN** (the first implementer's protocol claimed otherwise -- 2 (a)) | G5-1/G5-3 texts; the office `effort:` question belongs to BUG-0251 |
| `.claude/agents/harness-*.md` (G5-1) | nothing written | the SEAM SENTENCE in AC-7 |
| `tools/test_hooks.py`, `tools/test_hooks_v2.py` | six fixture/assertion fixes (2 (i)) -- `_project_the_installers_produce` gains an optional `monkeypatch`, five tests point the running home at their own store, one test renamed to the top-rung question | G5-1 owns the test-discipline surface; these are localized and named here so a collision is visible |
| `team-kits/*/skills/project-manager/SKILL.md` (forbidden) | nothing written | **BLOCKING**: the retired ladder bullet -> the built rule; BUG-0250, and the shipped tripwire is red the moment it is half-done |
| `team-kits/*/templates/project_memory/project_config.yaml` (out of scope) | nothing written | **BLOCKING**: same, three files; plus the `haiku < sonnet < opus` and `lead/worker/light` comments; BUG-0250 |
| `team-kits/*/hooks/session_status.py` (out of scope) | nothing written | the `lead/worker/light -> opus/sonnet/haiku` map read out of `model_tiers.yaml`; BUG-0250 |
| `team-kits/scaffold_team.sh` / `.ps1` (forbidden) | nothing written | the dead `light -> haiku` rewrite lines; BUG-0250 |
| `team-kits/kernel/report.py` (forbidden) | nothing written | `active_tasks` rows gain `rung`/`effort`; BUG-0249, one line + one test |
| `team-kits/office-team/templates/.../project_config.yaml` `effort_map` (forbidden) | nothing written | `medium` for the seven non-filing office roles (DEC-0078 (2)); BUG-0251 |
| `tools/lead_package_sizes.json`, `tools/constitution_section_pins.json`, `docs/reviews/phase0-disposition.md` | recorded through their own tools with `--note` (appended, never overwritten); parity matrix row 43 reclassified with its reason | -- |
| `README.md` | command surface (`ladder`), the three-rung and ladder bullets, the preset/escalation disambiguation | -- |
| `team-kits/*/settings/settings.json` | untouched (the trigger, if B, registers no hook) | only if the user picks a mechanism that needs one |
| `tools/test_model_ladder.py` `STALE_LADDER_TEXTS` | five entries, both ends measured | shrinks to `{}` as the files above are repaired; red on a half-done repair |
| `tools/radar_routine.py` (new) | both halves DEC-0084/DEC-0085 chose: the cloud specification (prompts, cadence, branch/PR shape, record shape, limits), `--due`, `--run` (with `--force`), `--describe` with a `starts_itself` derived from the lead's record | the LEAD creates the trigger from `--describe` |
| `radar/2026-09-06-codex.md` (new) | the report the routine produced end to end; triaged as "nothing new" by the watcher itself | the lead triages it like any other report |
| `.claude/settings.json` (forbidden) | nothing written | a `SessionStart` line that runs `tools/radar_routine.py --due`, so the lead meets an owed run the way a kit PM meets the auditor's. It is NOT what `starts_itself` reads any more (DEC-0085, R2-2): a session-start hook still needs a human session |
| `.claude/agents/harness-lead.md` (G5-1, forbidden) | nothing written | the SEAM SENTENCE in 3d: ask `--due` at session start, AND review the open `radar/` pull requests the cloud routine opens, AND record a created trigger in `radar/routine.json` |
| `radar/routine.json` (the lead's) | nothing written -- the shape is published by `--describe` and read by `starts_itself` | the LEAD writes it after `RemoteTrigger create`, with the ids and timestamps the API returned; until then the texts stay in their session-only wording |
| `.claude/hooks/**` (forbidden) | nothing written | **BLOCKING for AC-1's invariant**: four schedule claims, one in a live refusal text; BUG-0264/H182 |

**Reach seam (DEC-0080 (1)):** the dispatcher change touches every kit -- all three pilots measured
(4a), and every suite that reads `create_lease` / `validate_dispatch` / the conftest dispatch
helpers / `architect_step_owed` / the tiers table is in section 6.

## 10. Handover

- Patch (worktree diff WITHOUT the VERSION hunks and without the worktree's own audit log):
  `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0130/stream-ladders.patch` -- **31 files, 4287
  lines**, RE-CUT at 19:04:40 from the tree run 8, the follow-up suites and rig 2 measured. The cut
  is a script now (`cut_patch.py`): it names the excluded paths in the file rather than on a
  command line, writes the patch as bytes, and refuses to run outside its own directory. The
  10:37 cut it replaces described the tree of that hour and not the one the desktop-shape rework
  left behind -- a stale patch is the cut finding round 2 blocked on, and the pause made one again.
- **THE CUT IS CONSISTENT, and that is measured, not asserted** (`cut_check.log.json`, 19:04:46,
  run after the last edit, the last suite and the version bumper, so nothing stands between the
  check and the tree):
  `git archive b7f282e` into a throwaway directory, `git apply` the patch, then compare every file
  as BYTES against the worktree. `git apply` rc 0; the files that differ are exactly the four the
  patch deliberately leaves out (the three `VERSION` stamps and the worktree's audit log); nothing
  is only in one side but `.git`. Round 2 blocked because patch, worktree, rig log and protocol
  described four trees (R2-1) -- this check is the answer to that, and it runs from the round's own
  scratch so the next cut can repeat it.
- Provisional VERSION stamp: **dev-team / office-team / research-team 2026.09.06-2** --
  `python tools/bump_kit_version.py` re-run at 18:48 on the final tree answers `unchanged` for all
  three, which is the expected answer: the handover round touched `tools/` and `radar/` only, and
  neither goes into a kit hash.
- No commit, no push, no install into the global store.
- Verifier copies without the worktree's `.git` file (all three rigs already do that).
- The two DEC-first proposals, both ANSWERED: `dec-trigger.json` -> DEC-0084 (measure first),
  `dec-trigger-2.json` -> DEC-0085 (the platform's cloud routine). Both carry their own
  correction: the first its report count, the second its false "not pushed" premise.
- **Owed from the lead before this is finished**: the trigger ids, the first `get_run_log`
  and the PR link (section 3d names where each goes). Until they are here the cloud half is
  declared, specified and tested, and not observed.
- **Handed to the lead, not filed by this stream** (it belongs to no criterion of PR-0010): the
  over-refusal of R3-5 -- gate 1 refuses `timeout 120 python -B -m kernel.cli --root
  project_memory <command>` while the same line without the starter word is rc 0, so the host
  rule "every run with a timeout" and the gate's own remedy line contradict each other for kernel
  calls. `.claude/hooks/**` is this item's forbidden_scope; the lead decides under which goal it
  is captured.

## 11. (g) row

| | |
|---|---|
| Tier | first implementer Fable 5.1 / high (stopped by the user, DEC-0081); second implementer **Opus 5 (`claude-opus-5[1m]`), effort high** (DEC-0081) |
| Wall-clock (read) | first implementer 21:14:59 (its own first stamp) -> 22:08 (its last scratch write); second implementer, build round 22:12:22 -> 00:57:41 (~2 h 45 min) and rework round after the verification 07:26:15 -> 17:09 (its last write before the pause), of which roughly half is suite, rig and watcher wall time; **third implementer (handover round) 17:15:54 (first probe) -> 19:09:12 (last rig run), ~1 h 53 min, of which 1 h 15 min is the run-8 suite wall time, ~9 min the three follow-up runs of `test_repo_hygiene`, and 4 min 25 s + 4 min 28 s + 3 min 48 s the three mutation-rig runs**. The minutes between 22:08 and 22:12:22 were spent reading the worktree and were not clocked; they are not counted here rather than estimated. |
| Tokens | not instrumented for this stream: the session carries no token meter the agent can read, and a figure written here would be an estimate. The (g) table gets the transcript's own accounting instead. |
| Prose-overclaim findings against the first implementer's package | 9 (section 2 (a)-(i)); the two that matter are a seam-table row the tree did not carry and a `behalten` rule deleted with the paragraph that carried it |
| Findings of the verifier's round 1, reworked here | 2 blocking (B1, B2) + 6 residues (F3-F8), section 2 (j)-(q); plus two mutations of my OWN that measured the wrong thing and were rewritten (section 5) |
| Findings of the handover round against the previous correction | 6 (`R3-1`..`R3-6`): a file contradicting itself, three citations naming the wrong item, a claim reader widened fail-open (rig row M30, red), a paragraph whose pointer the insertion broke, a claim of my own that failed its own re-measurement, and a pointer index the protocol said was regenerated and was not |
| Items this round added | `BUG-0269`/`H186` (the desktop scheduled task, with `limits`), captured through the kernel; pointer index rewritten from the store (176 holes) |
| Provisional VERSION stamp after the rework | dev / office / research **2026.09.06-2** |
