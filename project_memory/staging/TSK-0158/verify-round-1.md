# TSK-0158 verify round 1 -- FAIL (filed by the lead from the verifier's return, 2026-09-27 ~21:10)

Copy: C:\Offline Repos\v2-testbed\_round-scratch\TSK-0158-verify\tree (binary copytree.py, no .git, stamp -8 x3); rig test_zz_verify_0158.py, logs logs-n1.txt, logs-reuse-*.txt.

## Finding A -- BLOCKING, rule 3 (a sentence claims protection the code does not build)
Where: project_memory/bugs/active/BUG-0327.yaml `observed` ("VERDICT: over-refusal, no gap in the protection.") and team-kits/{dev,office,research}-team/hooks/gate_write_scope.py:1269-1278 (`_upkeep_refusal` docstring).
The gate's word list is not the shell's argv. The fix refuses the direction where the gate's parse FAILS; the other direction stays open: the gate's parse SUCCEEDS reading the caller's own role at the role position, while the shell expands one word into several arguments and the kernel's parser reads ANOTHER role. Same class as N1, adding direction; bash expansion rules and PowerShell array arguments reach it. Not new with rework 2 (present since TSK-0156's bound); new is the "no gap" sentence in the very item that should have named it.
Measured (bound backend-developer, real dev-kit gate, then a real shell with a stand-in scripts/harness.py read by the kernel's build_parser()):
`BASH rc 0 | ... | shell: ['upkeep','prune-memory','--retire','a','database-engineer','--retire','backend-developer'] -> cmd=upkeep action=prune-memory role=database-engineer` -- same with four bash and two PowerShell spellings (spellings kept in the rig only).
Severity medium: the chain runs within one session (a subagent prunes another role's craft memory, BUG-0325 in the other direction).
Minimal fix for this round: correct BUG-0327's verdict; name the class as its own hole (mechanism, chain, verdict: open, closing belongs to wave-1 stream B); one docstring sentence naming the succeeding direction as a limit. No code fix (it would be another command-line guess, which the lead rejected).
Boundary: wrapper forms (function, xargs, bash -c, eval, substitution at command position) also pass (rc 0, role=database-engineer) -- named as L43, not a finding.

## Held (measured)
- N1: `_upkeep_refusal` refuses every SystemExit (:1310, md5 39fc46d1... x3). Red-first re-derived: rework 1's pass in the copy -> 8 failed, 2 passed (7 suffixes + help-line test; # and backtick stay green as predicted). Real-shell arbiter 9 passed. Counter-mutation not repeated.
- N2 (dispatch.py:947-948, :1932-1939, cli.py:2376-2380): mutation "new lease keeps CHILD_WAITING" -> test_a_new_lease_after_the_failed_way_out_is_a_new_dispatch_bug_0326 red; "way out always FAILED" -> test_the_sweep_names_each_waiting_tasks_own_way_out_bug_0326 red. Predecessor's chain now: STEP3 dispatch rc 0 LEASED child_waiting None; STEP4 released to READY; STEP6 dispatch rc 0. Status mapping vs automaton: lease-bearing transitions legal (LEASED->READY, IN_PROGRESS->FAILED); READY/DRAFT/CANCELLED/VALIDATED would map to an illegal FAILED but carry no lease (read, not produced). Relet: CHILD_WAITING not cleared; _relet_refusal_locked refuses a relet while a child waits (:1910).
- N3/H225 chain true on the current tree (S3 lease kept False; S4 child write rc 2; S6 lead stop rc 0; S7 dispatch rc 1). Protocol correction at 19:41 present.
- stamp --check rc 0 unchanged -8 x3; 25 shared hooks byte-identical x3; validate clean; ruff clean; tools/test_repo_hygiene.py (main tree, read-only) 21:03:18-21:05:35 44 passed.
- `--retire ../<other role>/...`: gate passes, kitupdate.prune_memory:1811-1816 refuses against the role's topic list (read, not driven to deletion).

## Not measured
H226/BUG-0329 chain; office/research gates as processes (identity by md5); gate runtime on upkeep lines vs the registered deadline; a real deletion through the shipped shim; the full suite.

## Verdict
FAIL on finding A; the fix is an item correction + a hole entry + one docstring sentence. N1, N2, N3 done and measured.

## Lead actions (21:1x)
- Hole filed through the kernel: BUG-0331 = H227 (capture_hole_upkeep_split_word.py); BUG-0327's verdict corrected through `kernel.cli update` to name H227.
- Docstring sentence + hole index regen + stamp: ordered to a small builder on TSK-0158.
