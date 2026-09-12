# TSK-0144 -- what the LEAD runs, and what waits on the USER

Written by the merge builder of PR-0012 "Bug-Null" (TSK-0144), 2026-09-12 20:10 (clock read).
Everything below is measured; nothing here is a plan.

---

## 1. The verification batch lines -- ALL ten, 68 ids, 0 refused

ONE dry check over all of them, through the reader `request-approval` itself asks before a question
ever reaches the user (`kernel.approvals.batch_walk_blockers(state, "verification", ids)`):

    C:/Offline Repos/v2-testbed/_round-scratch/TSK-0144/dry_check_lines.py

    A (TSK-0141) 1/3           10 ids  refused 0
    A (TSK-0141) 2/3           10 ids  refused 0
    A (TSK-0141) 3/3            7 ids  refused 0
    B (TSK-0142) 1/3           10 ids  refused 0
    B (TSK-0142) 2/3           10 ids  refused 0
    B (TSK-0142) 3/3            1 ids  refused 0
    B2 (TSK-0142, corrected)    5 ids  refused 0
    B3 (TSK-0142)               3 ids  refused 0
    C (TSK-0143)                9 ids  refused 0
    D (TSK-0144, the merge)     3 ids  refused 0

    10 lines, 68 ids, 68 distinct, refused 0
    ids appearing in more than one line: none

WHERE IT READS AND WHY NOT A COPY: against THIS repository's store, read-only. A copy of the store
is refused to every caller and that was measured rather than assumed -- `robocopy <repo>/project_memory
<scratch>` came back from `.claude/hooks/gate_lead_write_scope.py` with "no tool call in this repo
may write <repo>\project_memory ... It has exactly one writer, the kernel". Nothing in the rig opens
a file under the store for writing; the only file it writes is its own report beside itself, and it
refuses to run from anywhere but its own directory.

**The lines, in the order they were built:**

    python scripts/harness.py request-approval verification --batch BUG-0173 BUG-0193 BUG-0211 BUG-0266 BUG-0195 BUG-0278 BUG-0140 BUG-0236 BUG-0218 BUG-0225
    python scripts/harness.py request-approval verification --batch BUG-0231 BUG-0226 BUG-0224 BUG-0163 BUG-0144 BUG-0281 BUG-0210 BUG-0213 BUG-0238 BUG-0271
    python scripts/harness.py request-approval verification --batch BUG-0246 BUG-0032 BUG-0055 BUG-0190 BUG-0152 BUG-0150 BUG-0192
    python scripts/harness.py request-approval verification --batch BUG-0030 BUG-0107 BUG-0149 BUG-0154 BUG-0156 BUG-0158 BUG-0159 BUG-0160 BUG-0162 BUG-0182
    python scripts/harness.py request-approval verification --batch BUG-0186 BUG-0201 BUG-0207 BUG-0250 BUG-0259 BUG-0262 BUG-0277 BUG-0285 BUG-0288 BUG-0289
    python scripts/harness.py request-approval verification --batch BUG-0294
    python scripts/harness.py request-approval verification --batch BUG-0183 BUG-0196 BUG-0202 BUG-0208 BUG-0222
    python scripts/harness.py request-approval verification --batch BUG-0180 BUG-0167 BUG-0169
    python scripts/harness.py request-approval verification --batch BUG-0008 BUG-0133 BUG-0137 BUG-0165 BUG-0243 BUG-0263 BUG-0274 BUG-0275 BUG-0290
    python scripts/harness.py request-approval verification --batch BUG-0240 BUG-0265 BUG-0280

The last line is this round's; its three closing records are EVD-0410 (`BUG-0240`), EVD-0411
(`BUG-0265`) and EVD-0412 (`BUG-0280`), each with the naming node in its `run_command`.

**ONE THING TO KNOW BEFORE THE LAST LINE IS TYPED.** `BUG-0240` was refused by that reader twice
while this round ran, both times for a reason worth keeping: first because its own
`regression_tests` still named the node this round turned around, then because the new node carried
`BUG-0240` in the SECOND paragraph of its docstring while the reader looks in the FIRST
(`DEC-0100` (3), `H195`). Both are repaired; the third dry check is the one above.

## 2. C's exception update lines -- REFERENCED, not run

`project_memory/staging/TSK-0143/limits-update-lines.md` carries them. They are NOT part of this
package and I ran none of them.

**AND THE ONE OPEN QUESTION IN THAT FILE IS STILL OPEN** (C's verifier named it as N3 and C
defended it explicitly not): its "BEFORE THE BATCHES" paragraph claims the 14 `OPEN` items need a
`transition ... TRIAGED` first, while the verifier's round-2 measurement says
`batch_walk_blockers -> []` for `OPEN` in both kinds. My own dry check agrees with the verifier:
line 4 above carries `BUG-0030` at `OPEN` and `BUG-0032`/`BUG-0055` are `OPEN` in line 3, and all
three came back **refused 0**. So the paragraph is wrong and 14 blind transitions would be 14 state
writes nobody needs. Strike the paragraph or write the measurement beside it -- that is a lead
decision, not a builder's.

## 3. The questions that wait on the USER -- by id, with where each one stands

Each of these is a QUESTION with options, not a defect list. The path is where the question's own
wording lives.

| id | what it asks | where the question stands |
|---|---|---|
| `H155` / `BUG-0237` | Which words may the KIND of a goal have? | `project_memory/staging/TSK-0141/protocol.md`, "DEC question 1, rewritten so a non-developer can answer it" (the rewritten Frage 1; the first version is above it and was replaced because a non-developer could not answer it) |
| `H170` / `BUG-0252` | Should the office team get goals at all? | `project_memory/staging/TSK-0141/protocol.md`, Frage 2 |
| `H171` / `BUG-0253` | Where does THIS repository take its model tiers from? | `project_memory/staging/TSK-0141/protocol.md`, Frage 3 (and the DEC proposal in B7b above it) |
| `BUG-0286` / `H202` | A patch FILE the gate cannot read: read it, or refuse the stage? | `project_memory/staging/TSK-0142/protocol.md`, "DEC question BUG-0286 (for the user, in plain German)" -- three ways WITH their prices, including the measured 42.1 s for way 1 |
| `H178` / `BUG-0260` | The QA classification "purely mechanical": drop it, or make it a field only QA may set? | `project_memory/staging/TSK-0142/protocol.md`, the `BUG-0260` row. **The prices were added in this round** (verifier B round 3, D3): (a) the report loses the distinction entirely, (b) every non-QA role needs a round trip per failure |
| `H166` / `BUG-0248` | A tax question, for the user and their Steuerberatung | `project_memory/staging/TSK-0142/protocol.md`, the `BUG-0248` row |
| `H72` / `BUG-0164` | How strict should the four-eyes rule for the archive be? | `project_memory/staging/TSK-0142/protocol.md`, the `BUG-0164` row. **It got the question form in this round** (verifier B round 3, D1): Lage, two options, a price per option. It stands in the measurements AND here, and the row says which half is which |
| `BUG-0056` | Closing the deposit copy under `staging/` means a state scan in the decision path of EVERY write | `project_memory/staging/TSK-0142/protocol.md`, the `BUG-0056` row (half of the item's headline case does not exist -- measured at `kernel/migrate.py:1462`/`:1227`) |

**PLUS ONE THE LEAD HAS TO CARRY THAT WAS NOT ON THE LIST**, because it appeared in the gate run of
this round:

| id | what happened | why it is not mine |
|---|---|---|
| `H138` / `BUG-0221` | The item is ARCHIVED with `status: ACCEPTED_EXCEPTION` and names a test a stream RENAMED. The new node (`tools/test_design_conformance.py::test_a_draft_with_conformance_findings_is_refused_and_an_undecided_one_is_not`) says in its own docstring what really happened: `BUG-0294` -- a rendered draft with findings no longer walks past the sighting gate. **So the exception the USER granted describes behaviour that has been removed** (measured in that test: renderer rc 3, gate rc 2, undecidable counter-end rc 0) | both routes measured and closed to me: a tool write under `project_memory/**` is refused by gate 1, and the kernel has no writer for an archived item -- `update BUG-0221` answers "no active item BUG-0221 ... a finished item lives in the archive". An exception whose reason is gone is the user's to retire |

## 4. The USER'S SHELL PATCH -- the one thing no role here can apply

`project_memory/staging/TSK-0141/s4-gate-commit-evidence-patch.md` (seam S4). Two lines into
`.claude/hooks/gate_commit_evidence.py`'s refusal text, from a shell OUTSIDE Claude Code, then a new
session.

**It now has an arbiter that goes red until it is applied AND green the moment it is**, which is
what this round added:
`tools/test_hooks.py::test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires`.
It is the ONE red of the delivery full run, and the node's own docstring says so and says why no
exception was written for that one file. **Both halves are measured** in a copy with the patch
applied (verifier round 1, B1): unpatched `1 failed` naming only `gate_commit_evidence.py`, patched
**`1 passed in 2.94 s`**, and with the reader's computed-flag skip cut out `1 failed` naming
`gate_test_scope.py` -- which is what the first cut of this round shipped and what would have made
the user's patch change nothing they could see.

**ONE SENTENCE IN THAT PATCH DOCUMENT IS WRONG AND IS THE LEAD'S TO CORRECT.**
`project_memory/staging/TSK-0141/s4-gate-commit-evidence-patch.md` says "`gate_test_scope.py:709-712`
already carries the pair and needs nothing". True of the FILE, false of the reader as it stood this
morning. What is true now: the file needs nothing, and the reader no longer judges it, because it
spells the two flag names through `%s`. I did not edit it -- that file is another task's staging and
this item's `forbidden_scope` excepts only `staging/TSK-0144/`.

## 5. AC-5 -- the accounting, read after the run

`report.stock_rollup` of this store, read out of
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0144/read_stock_rollup.py` (read-only):

* **89 defects carry a PASSING `test` Evidence and stand open** -- they wait on the user's
  verification click and on nothing else.
* **0 of the 89** name a test that does not resolve (`unresolved=[]` in every row). That is the same
  reader the batch lines are refused by, so the rollup and the lines cannot disagree.
* **68 of the 89 stand in the ten lines above. 0 ids of those lines are outside the rollup** -- no
  line asks for a click on something that is not ready.
* **21 stand in the rollup and in no line of this generation**, and they are listed here so the
  lead does not have to derive them:
  `BUG-0102 BUG-0106 BUG-0136 BUG-0174 BUG-0176 BUG-0178 BUG-0181 BUG-0194 BUG-0197 BUG-0203
  BUG-0212 BUG-0214 BUG-0223 BUG-0230 BUG-0233 BUG-0234 BUG-0235 BUG-0237 BUG-0239 BUG-0241
  BUG-0286`.
  TWO of them are question rows of section 3 -- `BUG-0237` (H155) and `BUG-0286` (H202) -- and no
  others: the seven remaining ids of that section (`BUG-0252`, `BUG-0253`, `BUG-0260`, `BUG-0248`,
  `BUG-0164`, `BUG-0056`, `BUG-0221`) are not in this 21, and `BUG-0203`/`BUG-0212` are NOT question
  rows (an earlier version of this sentence said they were; verifier round 1, R5 -- the lead would
  have gone looking for two question texts that do not exist). The rest is earlier generations'
  stock that this generation's streams did not put on a line. Whether they belong on one is a lead reading, and I made none -- what is
  measured is only that the rollup holds them and no line does.
* **Exception questions with a German sentence in `limits`**: C's file (section 2) is the one that
  carries them, and I ran none of its lines, so the count there is C's and not re-derived here.

## 6. What this round did NOT close, in one place

| id | state after this round |
|---|---|
| `BUG-0192` / `H108` (seam S4) | the corpus now READS the file, the remedy text is the user's patch -- section 4 |
| `BUG-0147` / `H55` | the repo line is closed in what the bridge SAYS (`tools/test_kitupdate.py::test_a_stock_without_update_kit_is_lifted_by_the_bootstrap_and_told_about_it`); the world limit -- a copy already on a foreign machine -- stands and cannot be closed from here |
| `BUG-0151` / `H59` | NOT a build: the kernel DERIVES the debt, the validator warns per task and every session start says it (3 nodes, measured). Making that a refusal is a decision, and the function's own docstring argues the other way |
| `BUG-0197` / `H113` | NOT a defect repair: there is no done-record anywhere (grep over `kernel/*.py` + office `_duties.py`: 0 hits), and building one is a new canonical record kind |
| `BUG-0153` / `H61` | untouched: step 1 is `team-kits/*/settings/settings.json`, forbidden here, and applying step 2 alone shuts every kit hook |
| `BUG-0240` / `H158` | CLOSED for the one derivable occasion; the other three occasions are a named limit in the role texts and in `docs/holes/H158.md` |
| `BUG-0240`'s old pointer in earlier staging protocols | four staging documents of earlier rounds still name the renamed node. They are records of what was true then; the repo-side sweep does not read `project_memory/`, so nothing is red, and I changed no historical record |
