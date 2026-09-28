# TSK-0163 block verification (TSK-0160 / TSK-0162 / TSK-0163) -- filed by the lead, 2026-09-28 ~22:3x

Two verifier runs; both were cut by a content filter while replaying writes against the guard, so the guard part (TSK-0162) has NO independent verdict. The user chose (2026-09-28, option A) to ship with TSK-0162 on the builder's evidence and to record the unconfirmed hints for wave-1 stream B (pointer: C:/Offline Repos/v2-testbed/_round-scratch/TSK-0163-verify/out1.txt).

## Run 2 result (the usable one)
- TSK-0163 (merge): PASS -- register lines `..., rollback-kit, upkeep, integrate` in the three constitutions (section 0) and README.md:337; parsers at kernel/cli.py:1065 (upkeep) / :1210 (integrate); bump_kit_version --check unchanged 2026.09.28-4 x3; sizes "every size is the one on record"; pins "129 sections, all pins current"; validate rc 0 (0 errors); ruff clean; mirrors md5-identical.
- TSK-0160 (integrate door): PASS -- test_bug0333_integrate.py 20 passed; mutations I1-I9 (other goal's branch taken, no reset on undo, no clean-worktree check, base naming a goal, merge onto the base, no worktree remove, no branch -D, pattern without word bounds, gate_git not naming the door) all RED; red-first vs 35e929b (gate_git from 35e929b: 7 failed = the names_the_door cases); `integrate` listed by scripts/harness.py --help in a scaffolded project; all registered PreToolUse hooks rc 0 for the door line for main session, backend-developer, quality-engineer.
- COLLECTED (not blocking): C1 integrate.py:25-27 concurrent runs for the same goal are not serialised (a failing second run can undo the first's merges; no data loss, a false 'united' report) -- to the hole list / kernel lock in the next block; C2 integrate.py:250 `merge --abort` untested and redundant (reset --hard covers it).
- TSK-0162: not measured (filter).

## Run 1 (partial, before the cut)
Mirrors identical, stamps -4, scaffolded project built; ordinary cases (mkdir+cd+write, cd into a real subdir, leaving a protected dir to a free one) rc 0; the original BUG-0335 case rc 2.

## Builder evidence for TSK-0162 (protocol staging/TSK-0156/protocol.md 'Rework 5')
Red-first test test_the_walk_takes_no_move_the_shell_may_not_perform_bug_0335 (3 kits), 8 mutations red, real-project chain refused for all forms, 702 tests over every test that moves a directory green.

## Delivery runs (DELIVERY_RUN=TSK-0163, in parallel, started ~19:15)
- .claude/hooks/test_gates.py: 577 passed, 1:20:43, rc 0 (end 20:35).
- tools/: 5338 passed, 15 skipped, 1 failed (3:03:48, end 22:18) -- the failure a 600 s subprocess timeout of test_the_shipped_scaffold_records_the_trays_of_the_kit_it_installs[sh-office-team] under the parallel load; rerun alone: 4 passed in 531.52 s.
- After the watchers added two radar reports: test_radar_trigger + test_model_ladder + test_shortening_net + test_repo_hygiene 116 passed.
