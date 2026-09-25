# TSK-0151 -- user patch for three role files under `.claude/agents/`

Gate 1 refuses `.claude/agents/**` to every role of this repository, so these six text changes are
the user's to apply, from a shell OUTSIDE Claude Code:

```
cd "C:\Offline Repos\AgentAndSkills"
python project_memory\staging\TSK-0151\apply_user_patch.py --check
python project_memory\staging\TSK-0151\apply_user_patch.py
```

The script is the authority on the exact text: every BEFORE below occurs exactly once in its file
(measured on the tree with `--check`, see the protocol), and the script writes ALL six or NOTHING.
After writing it regenerates the two Codex overlays (`python tools/radar_routine.py
--write-overlays`), because `.codex/agents/*-watcher.toml` are generated from the two watcher files
and `tools/test_radar_trigger.py::test_every_codex_overlay_is_the_one_its_claude_definition_generates`
holds them equal. Then start a new session: the lead's `effort:` binds at session start.

## 1 -- `.claude/agents/harness-lead.md`: the lead runs at effort xhigh (DEC-0114 (5))

BEFORE (frontmatter end):
```
harness_item: required
model: opus
---
```
AFTER:
```
harness_item: required
model: opus
effort: xhigh
---
```
Why: the role declares no `effort:` and has run on Opus 5.5's default `medium` since 2026-09-22
(radar/2026-09-25-claude-by-claude.md item 6); the user answered "xhigh".

## 2 -- `.claude/agents/harness-lead.md`: the three FR-0093 order lines

Anchor: the last line of the section "Before an order goes out",
`  order goes out". The order is generated FROM the item, so a coarse item is a coarse round.`
AFTER that line, a new bullet:
```
- **Three cost lines every order carries, word for word** (`FR-0093`, which holds the
  measurement). A rework is a FRESH agent given only the verifier's report, the item and the
  protocol path -- never a resumed implementer, whose context carries the whole first attempt
  into every turn of the second. A run longer than a few minutes starts in the background and
  the agent waits for its completion notice -- no loop of sleeping and looking at a log. A file
  over 2,000 lines, and every protocol, is read by section, never whole.
```

## 3 -- `.claude/agents/claude-watcher.md`: the schedule sentence (DEC-0098)

BEFORE:
```
  report into radar/. Never changes code. Its Friday run is started by a Claude Desktop scheduled
  task on the maintainer's host (DEC-0089; recorded in radar/routine.json, explained in
  radar/README.md); its Sunday run is a Codex app Automation the user has not created yet, and
  until both have been recorded the lead starts the missing run with
```
AFTER:
```
  report into radar/. Never changes code. Its Friday run is started by a Claude Desktop scheduled
  task on the maintainer's host, `watcher-duo`, which runs it first and the codex-watcher second
  (DEC-0089, DEC-0098; recorded in radar/routine.json, explained in radar/README.md); its Codex
  run is a Codex app Automation on the same Friday evening that the user has not created yet, and
  until both have been recorded the lead starts the missing run with
```

## 4 -- `.claude/agents/codex-watcher.md`: the schedule sentence (DEC-0098)

BEFORE:
```
  radar/. Never changes code. Neither of its two weekly runs is recorded yet (DEC-0090 (4): a
  Claude Desktop scheduled task on Saturday and a Codex app Automation on Monday, created at the
  next local session and recorded in radar/routine.json once they have run); until then the lead
```
AFTER:
```
  radar/. Never changes code. Neither of its two weekly runs is recorded yet (DEC-0098: the second
  step of the Claude Desktop scheduled task `watcher-duo` and a Codex app Automation, both on
  Friday evening, recorded in radar/routine.json once they have run); until then the lead
```

## 5 -- `.claude/agents/claude-watcher.md`: the tier-table duty (DEC-0114 (2)/(3))

BEFORE:
```
   - **TIER TABLE (team-kits/model_tiers.yaml):** when a model/price finding changes what `lead`/
     `worker`/`light` should map to on the CLAUDE side, add an explicit tier-change PROPOSAL to the
     report (old -> new + evidence). You never edit the table yourself — re-tiering is always a
     user decision.
```
AFTER:
```
   - **TIER TABLE (team-kits/model_tiers.yaml):** the table carries no prices (DEC-0114 (3)); per
     rung it says what the model is SUITED FOR (`suited_for:`, the vendor's words, source, read
     date). When a finding changes that positioning, or what a rung (`sonnet`/`opus`/`fable`)
     should map to on the CLAUDE side, add an explicit tier-change PROPOSAL to the report (old ->
     new + evidence). The claude row passes the names through on purpose, so a new model behind
     a name is a finding to report, not a defect (DEC-0114 (2)). You never edit the table
     yourself — re-tiering is always a user decision.
```
Why: the old duty names `light`, a rung DEC-0076 retired, and a price the table no longer carries.

## 6 -- `.claude/agents/codex-watcher.md`: the tier-table duty (DEC-0114 (3))

BEFORE:
```
     + pricing — new family members, price changes, deprecations. When a finding changes what
     `lead`/`worker`/`light` should map to for the codex provider, add an explicit tier-change
     PROPOSAL (old -> new + evidence). You never edit the table — re-tiering is a user decision.
```
AFTER:
```
     + pricing — new family members, price changes, deprecations. The table carries no prices
     (DEC-0114 (3)); per rung it says what the model is SUITED FOR (`suited_for:`). When a finding
     changes that positioning, or what a rung (`sonnet`/`opus`/`fable`) should map to for the
     codex provider, add an explicit tier-change PROPOSAL (old -> new + evidence). You never
     edit the table — re-tiering is a user decision.
```
