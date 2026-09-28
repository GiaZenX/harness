# TSK-0157 verify round 1 -- FAIL (filed by the lead, verbatim from the verifier's return, 2026-09-27 ~19:5x)

Copy: C:\Offline Repos\v2-testbed\_round-scratch\TSK-0157-verify\tree; attacks in tree\tools\test_zz_verify_0157.py, shim in ...\TSK-0157-verify\shim\.

## N1 (medium, BLOCKING, new with this rework's F3 fix)
`team-kits/{dev,office,research}-team/hooks/gate_write_scope.py:1305` (`if not exc.code: return ""`), docstring :1275-1276.
The gate hands the parser a `--help` the shell never passes to the kernel -- behind a redirection the gate does not know (`<<<`, `<<`, `<>`) or inside a command/process substitution (`$(: --help)`, `<(echo --help)`). The parser says "clean exit", the gate passes, the kernel runs the door: BUG-0325 reopened (a subagent prunes ANOTHER role's craft memory).
Measured (bound subagent backend-developer, `python scripts/harness.py upkeep prune-memory database-engineer --keep-newest 0` + suffix): ` <<< --help` rc 0, ` <<<--help` rc 0, ` 0<<< --help` rc 0, ` << --help` rc 0, ` <> --help` rc 0, ` $(: --help)` rc 0, ` <(echo --help)` rc 0 -- 7 of 9 pass; only ` # --help` and `` `: --help` `` rc 2. Real `bash -c` with a shim as scripts/harness.py receives `['upkeep','prune-memory','database-engineer','--keep-newest','0']` every time. Before the fix (every SystemExit refused): 9 of 9 rc 2.
Fix: on SystemExit(0) strip -h/--help (+ abbreviations), re-parse and apply the role rule -- or refuse --help again and name the over-refusal. Plus a test over the class "a word the gate reads and the shell does not pass".

## N2 (low-medium, new with the BUG-0326 fix)
`team-kits/kernel/dispatch.py:944` -- create_lease clears only CHILD_ENDED on a new lease, not CHILD_WAITING; :1926 (the predicate reads a task field that outlives its lease); `kernel/cli.py:2376` (hard-coded FAILED).
Chain: child waits -> lead takes the named way out `transition FAILED` -> user approves retry -> dispatch, no spawn within TTL. Measured: CHILD_WAITING survives FAILED, READY and the new lease; sweep "lease kept True status LEASED" + "held by a child WAITING" AND "LEASED without a lease (report only)" in the same run; running_leases ['TSK-0001'] blocks other orders' files without time bound; dispatch rc 1; `transition FAILED` from LEASED illegal. Before the fix: released to READY, dispatch rc 0. Bounded: the lead's Stop hook reports "no child was ever bound" rc 2.
Fix: create_lease clears CHILD_WAITING on a non-relet too ("A NEW LEASE IS A NEW DISPATCH"); the sweep-leases line uses no_progress_status instead of FAILED.

## N3 (low, residue to name)
`dispatch.py:2293` record_child_resume: a kept lease is always expired at resume; resume clears the waiting mark, so the NEXT sweep releases the lease -- BUG-0326 one step later. Measured: second sweep lease kept False; child write rc 2 not bound; lead stop rc 0; dispatch rc 1 (names FAILED). Fix: renew the lease TTL on resume, or name it in the hole list.

## F1 (lead decision, not a package defect)
Test + comment agree (mutation "renderer writes staging/ into the card" -> red). The deviation from DEC-0119 (6) ("no paths") lives only in the staging protocol; approvals.py:2709/:2724 do not name DEC-0119.

## Protocol note
The rejection reason "sweep clears CHILD_WAITING would unblock dispatch" is half wrong: _relet_refusal_locked needs CHILD_ENDED. The rejection stands on the first half (the resumed child would be unbound).

## Held (measured)
BUG-0326 red on before-fix (3 tests), green after; AC-1/AC-2 met. F3b silencing mutation -> red. F5 literal name compare -> only [.CLAUDE] red; limit honest. F2 pointers resolve. Stamp --check unchanged 2026.09.27-5 x3. validate + ruff clean. 25 hooks byte-identical x3 (session_status, format_on_write in KIT_SPECIFIC_HOOKS).

## Not measured
Tilde node; full suite; PowerShell spellings of N1; `_spawn_name_locked` reads "live" by TTL only -> a kept waiting lease frees its letter (possible duplicate spawn name, unmeasured); double naming of an unexpired waiting lease in "still leased" and the WAITING line.

## Verdict
FAIL on N1. N2 a one-liner, better in the same rework. N3 nameable residue. F1 lead decision.
