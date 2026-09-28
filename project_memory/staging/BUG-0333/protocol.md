# TSK-0160 / BUG-0333 -- protocol (harness-implementer, written as I go)

Worktree: C:/Offline Repos/v2-testbed/_worktrees/g7-integrate (branch g7/integrate, base 35e929b).
Scratch: C:/Offline Repos/v2-testbed/_round-scratch/BUG-0333/.

## 0. Plan (before building)

Build DEC-0125 as written:

1. `team-kits/kernel/integrate.py` -- the door. `integrate(state, goal, base=None)`:
   - goal must be an ACTIVE item of a root type (`ROOT_TYPE_BY_KIT` values);
   - sources = local branches whose NAME carries the goal id, read with the same shape gate_git
     reads (`<ROOT>-\d{4,}`, word-bounded, case-insensitive); a branch that ALSO names another root
     item is skipped and reported (never pulled in); the base and `integrate/<GOAL>` are never
     sources;
   - base = `--base` or the branch the checkout of the state directory stands on; a base that names
     a root item is refused (it is a work branch by the same reading gate_git softens pushes with);
   - integration branch `integrate/<GOAL>` created from the base or reused; worktree the kernel
     names (the one it is already checked out in, else a sibling of the checkout); must be clean;
   - merges each source `--no-ff`; any failure -> merge aborted, branch reset to the tip it had
     before THIS run, and a branch/worktree created in this run removed again -- atomic; the
     conflicting file list is reported. The base is never written.
2. `kernel/cli.py`: one parser block + one dispatch branch (small hunks, order 7 touches the file).
3. `gate_git.py`: every verdict refusal of a line that runs `git merge` names the door. Mirror to
   research-team (byte-identical, see section 1).
4. Two sentences in dev PM SKILL and parallel-streams SKILL (mirror to research-team, see 1).
5. Tests `tools/test_bug0333_integrate.py`, red first in a copy under the scratch dir.

REJECTED (FR-0084): the forensics' "read the merge TARGET in gate_git" (resolve `cd`/`-C`,
treat a merge into a same-goal work branch as no delivery) -- one more command-line reader, the
class that cost order 7 four reworks (DEC-0070 rule 2, DEC-0125 context). The smaller way (only a
refusal text + skill sentence, no door) would leave the circle closed: there would be no legal path
to a united tree at all.
REJECTED half of DEC-0125 (1) "or the branch recorded on the goal's leases": a lease records a
WORKTREE, not a branch (`dispatch.WORKTREE_FIELD`), and the field forensics measured synaipse's
lease carrying the MAIN checkout (forensics section 4) -- reading the branch checked out there
would attribute the delivery base to the goal. Branch-name attribution only.

## 1. Built (worktree, uncommitted)

- `team-kits/kernel/integrate.py` (new) -- the door; `kernel/cli.py` parser block after the archive
  door + dispatch branch after the archive door's branch + `integrate` in the package import.
- `gate_git.py` -- `_uniting_route(command, goal)`; appended to every VERDICT refusal (fail,
  blocked, none, partial; unnamed fallback fail/blocked/none) when the line runs a `git merge`.
  MIRRORED to `research-team/hooks/gate_git.py`: the item said "gate_git is not in the other kits --
  check"; it IS in research-team, byte-identical (mirror rule, not in KIT_SPECIFIC_HOOKS). Outside
  the item's allowed_scope -- named for the lead.
- two sentences: dev PM SKILL (after the parallel-streams paragraph, ~:234) and parallel-streams
  SKILL §6; §7's "no knowledge of a second tree" bullet amended (the kernel now makes one).
  parallel-streams MIRRORED to research-team (same reason, test_shared_skill_contract).
- command-surface registers: `integrate` appended to the list in the three constitutions (§0) and
  README.md (`test_every_span_that_presents_the_command_surface_names_all_of_it`). Outside
  allowed_scope; order 7 appends `upkeep` to the SAME line in all four -> a certain one-line
  conflict per file at merge (resolution: both words).

## 2. Tests -- tools/test_bug0333_integrate.py (20 cases)

Green in the worktree: 20 passed, 76.7 s / 93 s wall (logs/new2, new3 in scratch).
Red at base 35e929b (git archive + only the test file): collection ImportError -> all red.
Mutation rig (scratch/mutate.py, one defect at a time, binary I/O, refuses outside its dir):
  gate-no-route 7 failed | gate-route-on-push 1 | attr-no-other-goal-skip 1 | attr-substring 1 |
  no-undo 2 | writes-base 1 | base-names-goal-accepted 1 | dirty-accepted 1 | non-root-goal 1 |
  regex-case 1 | gate-softens-integrate 1. Two survived the first rc-only refusal test
  (base-names-goal, non-root-goal: a later check refused instead); the test now asserts each
  refusal's own reason, both red after.

## 3. Before the reading runs (written first)

ruff: clean (changed files and whole tree). validate.py: 7 findings, all expected and none a
defect of the door: VERSION x3 (not stamped, by order); lead package +13 B x3 (the `integrate`
word in the §0 surface list -- the record lives in tools/lead_package_sizes.json, outside my
scope, and order 7's `upkeep` moves the same record: re-record once at merge); integrate.py
untracked -> `git add -N` (intent-to-add, no commit) on the two new files.
Gate chain: the ten Bash PreToolUse gates of the dev settings, run as processes on
`python scripts/harness.py integrate PR-0001` (+ `--base main`) in a project with a root item:
all rc 0 (scratch/gates_probe.py).

Reading suites, found by CALLERS (scratch/select.py: a test whose body, or a module helper it
reaches, names gate_git / build_parser / cli.main / _shipped_texts / _refusal_texts / SKILL.md /
AGENTS.md / constitution / README / _kernel_calls / parallel-streams / project-manager):
  A whole files: test_shared_skill_contract, test_reference_skills, test_parallel_streams,
    test_board, test_gaplog, test_role_contracts, test_shortening_net, test_context_budget,
    test_disposition, test_repo_hygiene, test_parity_sources, test_kit_neutrality,
    test_archive_door, test_parallel_scopes
  B test_hooks.py: 312 of 645 selected; C test_hooks_v2.py: 43 of 671 selected
  D whole files: test_e2e, test_research_chain, test_kitupdate, test_light_kit, test_kernel

## 4. Reading runs (end of each log read, not the log)

A: 7 failed, 364 passed, 643.5 s (wall 646.6 s). Every red is merge-owned:
   test_reference_skills preset [powershell]/[bash] -> scaffold refuses an unstamped kit (VERSION);
   test_shortening_net section pin -> §0 of the three constitutions CHANGED (the `integrate` word);
   test_context_budget x3 -> lead package record (+13 B per kit);
   test_repo_hygiene decision pointers -> DEC-0125 is not in the worktree's project_memory (it
   exists uncommitted in the MAIN tree only).
B (test_hooks.py, 312 caller-selected): 2 failed, 530 passed, 11 skipped, 1599.5 s (wall 1602.8 s).
   Both reds: install.ps1 codex-only tests -> validate.py refuses "VERSION not bumped".
Next: C+D in one run, then a merge simulation (copy + DEC-0125 + re-record + re-pin + stamp) over
the red files only, to show the reds have no other cause.

## STOPPED 14:47 (2026-09-28) -- coordinator's stop (usage limit)

DONE (worktree g7-integrate, uncommitted, new files `git add -N`): the door (kernel/integrate.py +
cli.py registration), gate_git route (dev + research mirror, byte-identical), two sentences in PM
SKILL + parallel-streams SKILL (dev + research mirror), `integrate` in the 4 surface lists,
tools/test_bug0333_integrate.py (20 cases, green; red at base; 11/11 mutations red). Runs A and B
done (section 4), every red merge-owned.

RUNNING at the stop: background pytest group C+D (scratch/run.py, log scratch/logs/suiteCD.log,
budget 3600 s, started ~14:25). At 14:47 it stood past 50 % with some E and F. NOT yet read, NOT
yet classified -- they may be stamp/record reds like A/B, or real. The runner kills it at its
budget; the log's last line then says rc and wall.

LEFT:
1. Read the END of logs/suiteCD.log and classify each red (FAILED/ERROR lines, then the E lines).
2. integrate.py module docstring, last paragraph: drop the unmeasured claim "serialised by git's
   own index lock in that worktree" (keep only "not by the kernel's lock").
3. Merge simulation (scratch/merge_sim.py, written, NOT run): copy + DEC-0125 + re-record sizes +
   re-pin sections + stamp, then re-run only the red files of A/B/C+D there.
4. Final report. Stamp file list (for the lead, NOT stamped): team-kits/kernel/integrate.py,
   kernel/cli.py, {dev,research}-team/hooks/gate_git.py, {dev,research}-team/skills/parallel-streams/
   SKILL.md, dev-team/skills/project-manager/SKILL.md, {dev,office,research}-team/constitution/
   AGENTS.md (-> all three kit VERSIONs); outside the kits: README.md, tools/test_bug0333_integrate.py;
   merge-owned records: tools/lead_package_sizes.json, tools/constitution_section_pins.json + their
   journals in docs/reviews/phase0-disposition.md. Certain one-line conflict with order 7's `upkeep`
   in the 4 surface lists.

## C+D result (end of log read after the stop; no new run started)

38 failed, 383 passed, 1 skipped, 10 errors, 1081.6 s (wall 1084.5 s). Two cause classes seen in
the E lines, NOT yet proven per test:
  (a) unstamped kit -- scaffold/installer "does not hash to the `content:` in its own VERSION"
      (35 such lines): test_kitupdate reds, test_research_chain errors (scaffold fixture),
      test_the_shipped_lead_packages_are_within_their_own_record (size record);
  (b) rig artifact, suspected: registered-chain tests in test_hooks_v2 fail with
      "python.exe: can't find '__main__' module in 'C:\Offline'" -- my --basetemp lies under
      "C:/Offline Repos/..." (a SPACE), and the hook command line is split there. To confirm:
      re-run those test_hooks_v2 ids with a basetemp without a space (or at 35e929b with the same
      basetemp: red there too = rig, not change). Left for the next run.

## RESUMED -- lead decisions on the stop report

(1) ACCEPTED deviations from allowed_scope, with reason: research-team/hooks/gate_git.py and
    research-team/skills/parallel-streams/SKILL.md (mirror rule: byte-identical with dev, not in
    KIT_SPECIFIC_HOOKS / KIT_SPECIFIC_SKILL_FILES); `integrate` in the three constitutions' §0 list
    and README.md (DEC-0121 (3): the command-surface register; read by
    test_every_span_that_presents_the_command_surface_names_all_of_it).
(2) conflict with order 7's `upkeep`: keep both words, done by the merge.
(3) parallel-streams §7 old sentence: check against dispatch.WORKTREE_FIELD, correct if false.
(4) red against 35e929b is correct; "red on 2026.09.27-9" in BUG-0333 AC-1 was the lead's order
    error (35e929b carries 2026.09.26-5).

## Resumed work, before the runs

- parallel-streams §7: the old bullet ("A lease names a task, not a checkout, so nothing can tell
  you which tree an order is working in") was FALSE -- every lease records `worktree`
  (dispatch.WORKTREE_FIELD, dispatch.py:538; `dispatch --worktree`, cli.py:896; default = the tree
  of the state dir). Rewritten to what `_lease_worktree` builds: the field exists, only existence
  of the directory is checked. Mirrored to research (hash c338a332...).
- integrate.py docstring: the unmeasured "serialised by git's own index lock" is gone.
- Scratch slip, named: to test for a space-free directory I created and at once removed
  C:/v2bt-nospace-check on the drive root (empty, gone).
- Pattern-2 check plan: the 13 test_hooks_v2 chain reds (sel-pattern2.txt minus the lead-package
  record test) run (i) in the worktree with pytest's DEFAULT basetemp (system temp, no space --
  the only space-free place, since the scratch root itself has a space), (ii) in the 35e929b copy
  (red-base) with the scratch basetemp (space). Rig if (i) green and (ii) red.

## Pattern-2 result: RIG, not change

(i) worktree, default (space-free) basetemp: 13 passed, 73.8 s. (ii) 35e929b copy, scratch
basetemp (space): 13 failed, 43.5 s, 29x "can't find '__main__' module in 'C:\Offline'". The
chain tests split a hook command line at a space in the project path; my basetemp put one there.
Not caused by TSK-0160. (The underlying behaviour -- a registered hook line breaking on a project
path with a space -- is pre-existing at 35e929b; named for the lead, not filed by me.)

## Merge simulation, before the run

scratch/merge_sim.py: copy of the worktree (no .git) + DEC-0125 from the main tree + `git init` and
`git add -A` (index only, for validate.py's ls-files) + record_lead_package_sizes --write +
pin_constitution_sections --write + bump_kit_version. Then ONLY the red ids of A/B/C+D minus the
13 rig reds (sel-merge.txt) with the default basetemp, budget 1800 s; then validate.py there.

## Merge simulation, run 1

merge_sim: record_lead_package_sizes rc 0 (+13 B per kit), pin_constitution_sections rc 0 (4
changes), bump_kit_version rc 0 (-> 2026.09.28-1 in the COPY); validate.py in the copy: "all
structural checks passed". sel-merge (44 red ids) with the default basetemp, budget 1800 s:
KILLED at 1800 s -- 30 passed, 0 failed, the 31st did not finish. Next: the remaining 14 ids,
`-v`, budget 1500 s, to name the one that stalls.
Correction: the first text re-run carried an EMPTY test_hooks selection (sed missed the multi-line MARKERS); 60 passed = test_parallel_streams + test_shared_skill_contract + test_bug0333 only. Re-running with the fixed selection.
Text re-run (fixed selection, 40 test_hooks functions): 50 passed, 7 skipped, 74.7 s (wall 77.9 s).

## Final state (not stamped, not committed, not merged)

ruff clean. Mirrors byte-identical (gate_git dev=research, parallel-streams dev=research).
Stamp would cover: team-kits/kernel/integrate.py (new), kernel/cli.py,
{dev,research}-team/hooks/gate_git.py, {dev,research}-team/skills/parallel-streams/SKILL.md,
dev-team/skills/project-manager/SKILL.md, {dev,office,research}-team/constitution/AGENTS.md -> all
three VERSIONs. Outside the kits: README.md, tools/test_bug0333_integrate.py (new). Merge-owned,
re-made at merge (after order 7's `upkeep`): tools/lead_package_sizes.json,
tools/constitution_section_pins.json, their journals in docs/reviews/phase0-disposition.md.

## Merge integrate (TSK-0163, harness-implementer, 2026-09-28)

Into the MAIN tree (order 7 + reworks 1-5 uncommitted, stamp 2026.09.28-3 before this merge).
Scratch: C:/Offline Repos/v2-testbed/_round-scratch/TSK-0163/ (merge.py, resolve.py -- both refuse
outside their dir, binary I/O). Method per tracked file: `git merge-file -p main base(35e929b)
worktree` into scratch/merged/, inspected, then written into main; the two new files copied (both
absent in main before).

| file | main changed since 35e929b | merge-file conflicts |
|---|---|---|
| README.md | yes | 1 |
| team-kits/{dev,office,research}-team/constitution/AGENTS.md | yes | 1 each |
| team-kits/kernel/cli.py | yes | 0 (+23/-1, identical to the stream's own hunk count) |
| team-kits/dev-team/skills/project-manager/SKILL.md | yes | 0 (the 4-line paragraph) |
| team-kits/{dev,research}-team/hooks/gate_git.py | no | 0 |
| team-kits/{dev,research}-team/skills/parallel-streams/SKILL.md | no | 0 |
| team-kits/kernel/integrate.py, tools/test_bug0333_integrate.py | new | copied |

The four conflicts are ONE seam: the command-surface register line, where order 7 appended
`upkeep` and this stream `integrate` to the same last word. Resolution (resolve.py, which refuses
any conflict that is not exactly "the stream's side == main's side with `upkeep` -> `integrate`"):
`..., rollback-kit, upkeep, integrate` -- both words, `upkeep` first, the order of their parser
blocks in the merged cli.py (upkeep :1065, integrate :1210). Mirrors after the merge:
gate_git dev == research (5e722d13...), parallel-streams dev == research (c338a332..., the
stream's own hash). DEC-0125 present in main.

Dry runs before the one stamp: lead-package sizes +13 B per kit (= ", `integrate`"), the same
figure the stream's merge simulation measured; section pins: 4 changed (the three constitutions §0,
dev PM SKILL work-loop section).

Done ONCE: record_lead_package_sizes --write (3 kits +13 B), pin_constitution_sections --write (4
sections), both journals appended in docs/reviews/phase0-disposition.md; bump_kit_version ->
**2026.09.28-4** in all three kits, `--check` rc 0. validate.py first FAILED: "integrate.py is
hashed into a kit VERSION but not git-tracked" -> `git add -N` on the two new files (intent-to-add,
as the stream had them; no content staged) -> "all structural checks passed". ruff: product trees
(team-kits, tools, .claude, README.md) clean; `ruff check .` reports ONE F841 in
project_memory/staging/generation-6/create_order_7_merge.py:55 (untracked lead staging script, not
this merge's, outside allowed_scope -- named, not touched).

### Before the reading runs (written first)

Runner scratch/run.py (budget-killed, binary log, pytest DEFAULT basetemp = system temp without a
space). Selections by callers, scratch/select.py (AST, transitive through module helpers):
- R1 tools/test_bug0333_integrate.py -- 600 s
- R2 tools/test_parallel_streams.py + tools/test_shared_skill_contract.py -- 600 s
- R3 tools/test_repo_hygiene.py -- 900 s
- R4 tools/test_kitupdate.py -k scaffold (the stamp) -- 1200 s
- R5 registers/records: test_hooks.py::test_shared_kit_files_identical,
  ::test_every_span_that_presents_the_command_surface_names_all_of_it, tools/test_context_budget.py,
  tools/test_shortening_net.py, sel-upkeep.txt (7 test_hooks_v2 + 1 test_stream_c_field tests that
  name `upkeep`, i.e. read cli.py's other seam hunk) -- 900 s
- R6 gate_git callers outside test_hooks.py (sel-gg-rest.txt, 46 ids) -- 1200 s
- R7 gate_git callers in test_hooks.py (sel-gg-hooks.txt, 189 ids) -- 2400 s

### Reading runs (last lines of each log read)

- R1 20 passed, 68.6 s | R2 40 passed, 33.4 s | R3 44 passed (1 warning), 150.5 s
- R4 1 passed / 87 deselected, 12.7 s | R5 114 passed, 160.5 s | R6 87 passed, 261.3 s
- R7 347 passed, 1 skipped, 953.4 s (wall 956.6 s)
No space-in-basetemp failures met (default basetemp throughout). After the runs: bump --check
unchanged 2026.09.28-4, validate.py passes. Full run NOT started; nothing committed; worktree
g7-integrate left in place.
