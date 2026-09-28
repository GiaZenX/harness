# TSK-0156 -- user patch for `.claude/hooks/_harness.py` (H47) and `.claude/agents/harness-lead.md` (FR-0093 line)

Gate 1 refuses `.claude/**` to every role of this repository, so these changes are the user's to
apply, from a shell OUTSIDE Claude Code:

```
cd "C:\Offline Repos\AgentAndSkills"
python project_memory\staging\TSK-0156\apply_user_patch.py --check
python project_memory\staging\TSK-0156\apply_user_patch.py
```

The script is the authority on the exact text: every BEFORE occurs exactly once in its file
(`--check` on the merged tree: 4 sites "would change", protocol entry 06:57), it writes ALL its
sites or NOTHING, and a second run reports every site "already done".

| Site | Hole / item | Test (in `.claude/hooks/test_gates.py`) |
|---|---|---|
| 1a-1c `_harness.py` | H47 / BUG-0139, `DEC-0120` | `test_gate1_refuses_a_redirect_into_a_variable_bug_0139` (12 cases) and its counter-end `test_gate1_still_passes_a_redirect_with_no_expansion_in_its_target` (4) |
| 2 `harness-lead.md` | FR-0093 line after BUG-0313 (stream B hand-over 5) | none -- no test reads the lead's cost lines |

## 1 -- `_harness.py`: a redirect target is a path position (DEC-0120)

`_candidates` gains `path_position`; `written_paths` passes it for every redirect target. In a path
position the word is asked `_unresolved_at` whatever it looks like (before: only with a separator or
in program position, `_could_name_a_path`), so `> $F`, `> "$F"`, `>> ${F}`, `> $(...)` become an
`Unplaceable` and are refused for every caller -- the answer gate 1 already gives a word it cannot
place. A backtick is not in `_UNRESOLVED`; site 1b adds it for the path position only (measured: the
first cut without it let `` > `echo project_memory/...` `` through, 2 of 12 cases red).

Measured (rig `_round-scratch/TSK-0156/h47_rig.py`, copy of the merged tree):
- unpatched: 12 failed (every refused case rc 0, both callers), 4 counter-ends passed;
- patched: 16 passed. `$null` (PowerShell), `/dev/null 2>&1` and an expansion in the DATA of a line
  whose target is a plain free path stay rc 0.

Cost accepted by DEC-0120 (3): `echo x > $LOG` is refused; the remedy text already says to spell
the path.

UNTIL THE PATCH IS APPLIED the 12 cases of `test_gate1_refuses_a_redirect_into_a_variable_bug_0139`
are RED on the main tree -- that is DEC-0120 (4) (red before, green after), not a defect of the merge.

## 2 -- `harness-lead.md`: the background-run cost line

The kits' PM skills now say (BUG-0313) that a child ending its turn to wait on its own background run
is read as waiting only while the provider lists that run; this repo's lead line still said only
"starts in the background and waits for its completion notice". The site adds: the agent does not
END its turn to wait, because an ended turn is its report to the lead, and a child resuming on a
late notice had already been read as finished (BUG-0313's field case).
