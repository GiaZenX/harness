# BUG-0333 field forensics (synaipse-unified, kit 2026.09.25-6) -- read-only, 2026-09-28 ~10:2x

Filed by the lead from the forensic agent's return (Opus, read-only; nothing written in either repo).

## 1. The rule
- synaipse CLAUDE.md line 1 = dev-team marker; `.claude/kit_version` 2026.09.25-6; kit source 2026.09.27-9. `.claude/hooks/gate_git.py` identical to `team-kits/dev-team/hooks/gate_git.py` (diff empty); parallel-streams and PM skills unchanged on parallel branches since.
- Refusals (PM transcript `9e1f8b08-….jsonl`):
  - line 6409, 2026-09-27 21:04:40Z, `git merge --no-ff pr/PR-0020-p2-catalogue -m "merge(PR-0020): …"` in worktree synaipse-p2: "QA has judged PR-0020 only in part — PR-0020: acceptance pass (EVD-0024), and no review/test Evidence covers it at all … a delivery merge rests on all of them" (gate_git.py:541).
  - line 6543, 21:47:24Z, `git merge --no-ff feat/synaipse-unified -m "… (PR-0021)"` in worktree synaipse-p3-foundation: "the current QA verdict is not a pass — PR-0021: acceptance fail (EVD-0078)" (gate_git.py:512).
- Mechanics: only git push/merge (_compat.py:2235); collects every goal id on the line incl. the -m message (gate_git.py:137); with none, reads the MAIN worktree's branch, not the worktree the merge runs in (:143, :631); per goal every verdict kind current and not fail/blocked (:654 -> :482); with no goal named, any failing verdict anywhere refuses (:657, :574).
- Purpose (header :28): nothing reaches the delivery state the check has not seen complete and passing (FR-0083, BUG-0081, DEC-0061/FR-0040).
- Gap: the rule has no notion of the merge TARGET -- every `git merge` naming a goal is a delivery to it.

## 2. The session
- P2 = PR-0020, three parallel branches: pr/PR-0020-p2-runtime (worktree synaipse-p2, TSK-0472), pr/PR-0020-p2-catalogue (TSK-0488), pr/PR-0020-p2-h04 (TSK-0365). P3 = PR-0021, five: api-split, providers-ui, backend-fix, foundation-split, pyarrow.
- The architect planned the integration (staging/TSK-0515/plan.json: "integrate branches pr/PR-0020-p2-runtime and pr/PR-0020-p2-catalogue into its tree first", tree of TSK-0489); the PM ran both merges itself (lines 6407, 6542). First attempt 20:43Z refused for another reason (gate_pipeline quality errors, line 6373).
- PM: two kit-gap entries 23:05 and 23:47 local (.audit/kit_gaps.jsonl ids 2c525bde…, de788fb5…); question to the user 21:48:51Z (line 6571); user answer 08:23Z: "P0/P1 fertig machen und einfach weitermachen was geht", "Ja, neu starten".
- Correction to the PM's sentence: the P3 attempt was not uniting two work branches -- it pulled the main state INTO a P3 branch, refused because P3 was named in -m and EVD-0078 fails.

## 3. The repo
| Goal | acceptance | review | test |
|---|---|---|---|
| PR-0020 | pass EVD-0024 (from research order TSK-0358, not the goal) | none | none |
| PR-0021 | fail EVD-0078 | blocked EVD-0069 | blocked EVD-0075 |
- EVD-0078 measured on a composite state d83f8ca the QA role (TSK-0371) built itself with `git merge-tree --write-tree` + `git commit-tree` -- invisible to the rule (agent-ac59807132544b298.jsonl line 124); a plain merge before was refused for untracked files in the MAIN tree (line 115).
- No state satisfies the rule for a P2/P3 merge; since merge base 1ec95d7 no complete passing verdict set for either goal. P2 branches 47 commits behind feat/synaipse-unified.

## 4. TSK-0365 ("Sitzungen und Budgets")
- Run 1 (a0badde4…) ended 13:06Z "API Error: Connection refused (ECONNREFUSED)" (outage). Run 2 (a2cbeb39…, 13:24:13Z) ends 13:24:48Z mid-command, no end record -- the third outage (commit 240067c), not the usage limit (15:44Z).
- Saved: branch pr/PR-0020-p2-h04, 7ea0800 (work) + 2180ce6 (unverified checkpoint); worktree clean.
- ALREADY RESTARTED today 10:24 local: FAILED -> READY -> dispatched (lease 1aa678d4…, agent a3091999…, failed_runs 2). Safe: own branch only, "Do NOT merge any branch".
- Side finding: the lease carries worktree C:\Offline Repos\synaipse-unified, the order works in synaipse-p2-h04 (AGENTS.md:248-252 says the lease carries the real worktree).

## 5. Verdict
- The kit contradicts itself: a second builder under one goal is allowed (DEC-0092 (2)); only the united tree can be judged ("Only the united tree can be judged", parallel-streams/SKILL.md:117; §6 line 132; PM SKILL :234, :284; DEC-0063 (1)); but the rule demands the goal's passing verdict BEFORE any merge.
- P3: while EVD-0078 fails, no `git merge` in the whole repo passes (named goal, or the any-fail fallback). Real deadlock.
- P2: task-level verdicts are read as goal verdicts (report.py:1870, parent lookup) -- a full review+test pass on TSK-0472 or TSK-0488 would open the merge; technically not circular, but wrong: the same task verdicts would then also open the real delivery.
- SECOND FINDING (worse than the deadlock): a passing verdict on ONE order can mask a failing verdict on the whole goal (newest verdict per kind wins).
- Refusing rebase/cherry-pick is right: the rule does not see them (_compat.py:2235) -- a bypass, like QA's merge-tree/commit-tree. Hole to name.
- Smallest correct kit fix (gate_git): (1) read the merge TARGET branch in the tree the command runs in (resolve cd / -C; unresolvable = delivery); (2) a merge whose target is a work branch of the same goal and whose source is the same branch circle or the integration branch needs no delivery verdict (other rules stay: no force push, valid approval, legal status); (3) delivery into the integration branch / main stays strict; (4) parallel-streams §6: one goal's branches are united on an own integration branch, QA judges exactly that, then delivery; (5) test per AC-1 red on 2026.09.27-9. The masking case as its own BUG.
- PM now, no kit change: finish P0/P1 (unaffected; CR-0017 into main passed 21:19Z with PR-0019); let TSK-0365 run; P3: merge nothing, order no task-level checks just to mask EVD-0078, wait for the fix; P2: one branch per goal, TSK-0489 waits.
