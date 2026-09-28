# TSK-0158 verify round 2 -- PASS (filed by the lead from the verifier's return, 2026-09-27 ~21:20)

Scope: finding A's text fix only, and nothing else changed since -8. Base: the verifier's -8 copy (TSK-0158-verify\tree); main tree read only (diff -rq).

## Measured
- Since -8: kit area only gate_write_scope.py x3 + the three VERSION files; otherwise lead files (docs/POST_V2_WISHLIST.md, BUG-0327, new BUG-0331, generated/*, staging/*). No kernel or test code touched.
- Gate diff: docstring of `_upkeep_refusal` only (1271-1272 qualified, 1280-1283 name the succeeding direction open, H227/BUG-0331); code unchanged; ast.parse ok x3; md5 bbf827ebe8520c5bd5f80243840ff55e x3.
- Text vs code: `except SystemExit` refuses every SystemExit (failing direction); a successful parse with the own role returns "" (open direction); the docstring now says both.
- BUG-0327 verdict now "over-refusal in the FAILING direction. It is NOT 'no gap'" -> BUG-0331: true.
- BUG-0331/H227 matches logs-n1.txt (4 bash + 2 PowerShell, gate rc 0, kernel role=database-engineer); "present since TSK-0156" true; limits line not re-measured; POST_V2_WISHLIST.md:2536 is the one new line.
- stamp --check rc 0 unchanged 2026.09.27-9 x3.

## Own error from round 1 -> residue for the hole list (not a package defect)
Round 1 filed a measured form under "wrapper, L43" that does not belong there: the substitution that produces the SUBCOMMAND WORD itself, plus PowerShell splatting of the whole argv (measured, not reported). `_reserved_command` (x3, from :1238) reads the first positional from the gate's words; if the door word comes from a shell expansion the gate sees no reserved command and `_upkeep_refusal` answers "". Measured in round 1: gate rc 0, kernel parser on the real shell argv cmd=upkeep action=prune-memory role=database-engineer, one bash and one PowerShell form (logs-n1.txt). Not H227, not L43; no hole entry found. Reach: `_reserved_command` is the one reader for all rule-4 classes (dispatch/install likely too; read, not measured). Present since rule 4. Needs a hole-list entry before the commit (open until wave-1 stream B).

## Not measured
repo_hygiene after the change (builder: 44 passed 21:09:57-21:12:24); the upkeep selection of test_hooks_v2 (comment-only change); BUG-0331's limits line.

## Verdict
PASS for finding A's fix. Residue above to be named in the hole list before the commit.

## Lead action
Residue captured through the kernel as a hole (capture_hole_reserved_command_expansion.py) + index regenerated.
