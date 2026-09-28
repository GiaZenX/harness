# TSK-0159 verify round 1 -- FAIL (filed by the lead from the verifier's return, 2026-09-28 ~14:3x)

Rig: C:/Offline Repos/v2-testbed/_round-scratch/TSK-0159-verify/ (make_copy.py, make_before.py, probe.py, chain.py, mutate.py, runs.txt, out1-7.txt, gate1_probe.txt). States compared: after (md5 99afc605... x3), before (without the BUG-0334 hunk), head (git archive HEAD), mut (`if quoted and expanded`).

## B1 -- the kit gate follows every directory move as if it succeeded (the class BUG-0334 belongs to), unrecorded -- HIGH, PRE-EXISTING (head too)
team-kits/*/hooks/gate_write_scope.py:1699-1714 (`_walk` evaluates `pop` without operand check; with args[0] the other operands are ignored), :1763-1764 (`_walked_to` takes the literal target even when it is no existing directory). When the shell does NOT move (target missing or a file, a pattern matching nothing or two entries, two operands, pushd -n / +N, popd +N, popd on an empty stack) the walk still takes the named target. BUG-0334 is one member (`cd "~"` stays because no dir `~` exists); the new rule enumerates quoting spellings instead of defining "the move does not land" (house rule 1) -- `cd "../nope"` is a quoted spelling it does not cover.
Measured (kit gate, lead as caller, bash as arbiter, out2.txt; all after rc 0, before rc 0, head rc 0, shell-wrote=['.claude\\settings.json']):
`cd .claude ; cd ../nope ; echo x > settings.json`, `cd ../zz*`, `cd ../d*` (two hits), `cd ../README.md`, `cd .. extra`, `cd "../nope"`, `cd /nope-xyz`, `pushd .claude ; popd +1`, `pushd .. ; pushd +1`, `pushd docs ; pushd ../.claude ; popd ; cd -`, `pushd -n ..`, `cd .claude ; popd`.
Full chain in a real scaffolded dev-team project (chain.py, out4.txt): all ten registered Bash PreToolUse hooks rc 0 for `cd .claude ; cd ../nope ; echo x > settings.json`, `cd .. extra`, `pushd -n ..`, `popd`; bash overwrites .claude/settings.json. Control: `cd .claude ; echo x > settings.json` rc 2.
Gate 1 counter-probe (gate1_probe.txt): the same 11 forms against team-kits/kernel/state.py all rc 2 -- this repo's gate has the definition (H29/H30), the kits do not. No hole-list entry for this class in the kit gate.
Text side finding (rule 3): `_walk` docstring :1678-1682 names only "an entry an earlier call pushed" as popd's remainder; popd on an empty stack is read as a return to the line start while bash stays (measured rc 0, file written).
Minimal fix (verifier): in `_walked_to` add the "stays" reading (cwd) as a candidate whenever the target is no existing directory at gate time; in `_walk` read any operand list that is not exactly one target, and -n/+N/-N, as "stays or unknown"; popd on an empty stack gets cwd as a candidate.
Blocks: not TSK-0159's hunk, but the order-7 delivery -- capture now (BUG or --hole with limits), then close or a user-accepted exception.

## B2 -- the glob half of `index > 0` carries weight, no test covers it -- MEDIUM, BLOCKS this round
gate_write_scope.py:1747, :1760; docstring 1733-1735 claims no reading after the first expands. With mutation glob-quoted-only both new tests stay green (runs.txt 14:10:59-14:11:25 test_hooks_v2 bug_0334 3 passed; 14:11:48-14:12:17 test_gates bug_0334 1 passed); under the mutation a real gap opens (out5.txt): `cd .claude ; cd ../d\*cs ; echo x > settings.json` after rc 2, mut rc 0, shell writes. Fix: a row `cd ../d\*cs` (optionally `cd ../do\[c]s`) in `_QUOTED_EXPANSION_MOVES` (tools/test_hooks_v2.py:7403), red with glob-quoted-only.

## B3 -- the named price is too small: PowerShell expands a quoted tilde and a quoted pattern -- LOW (text)
gate_write_scope.py:1727-1736. Measured (out2.txt, real PowerShell arbiter): `cd .claude ; Set-Location "~" ; echo x > settings.json` after rc 2, before/head rc 0, shell-wrote=-; same for `Set-Location '~\docs'`, `Set-Location "..\d*cs"`. Over-refusal, fail-closed. Fix: name the PowerShell price as a property (PowerShell resolves ~ and wildcards at provider level regardless of quoting).

## B4 -- a count in a comment -- LOW
tools/test_hooks_v2.py:7431-7432 "...would pass the first five and fail these" -- a row count (rule 4, SR-0008). Fix: "the rows whose shell stays".

## Held (measured)
Mirror md5 99afc6052563720657ff899c8cb3c1f5 x3; stamp --check unchanged 2026.09.28-1 x3; validate + ruff clean. Red-first re-derived (no-fix): kit test 1 failed, gate-1 test 1 failed, 16-cell node failed (294 s) vs passed (299 s). tilde-quoted-only red, glob-first-reading-only red. BUG-0323 intact (3 passed; quoted absolute targets with spaces to .claude / .claude/hooks then `cd ..` rc 2, .../docs rc 0). Fix lines rc 2 after, rc 0 before/head in all three kits; counter-cases rc 0. Tilde family (~+, ~-, ~user, HOME=$PWD, $'~', R="~", CDPATH) refused. The hunk only adds None candidates. Gate call <= 2.2 s. Reading suites in the copy: hooks_v2 78 passed; test_hooks 36 passed, 3 failed = the copy artefacts (same with no-fix). Forbidden area untouched.

## Not measured
ruff over the whole repo; repo_hygiene -k pointer; test_hooks in the main tree; B1 for office/research (byte-identical), B1 with a PowerShell arbiter; gate 1 on the PowerShell tool.

## Verdict
FAIL: B2 blocks (one table row + red run); B3, B4 text in the same round; B1 blocks the order-7 delivery until captured and closed or excepted.
