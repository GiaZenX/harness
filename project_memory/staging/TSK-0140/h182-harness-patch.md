# H182 / BUG-0264 -- the exact patch, for a shell OUTSIDE Claude Code

`.claude/hooks/gate_spawn_needs_item.py` and `.claude/hooks/_harness.py` are the forbidden scope of
every role in this repository (`CLAUDE.md`: gate 1 refuses `.claude/` to the session agent, and a
broken gate cannot be repaired from inside the session that runs it). So this is a patch the USER
applies, from a shell outside Claude Code, followed by a session restart.

## What is wrong

Four sentences in the enforcement layer say the two watchers run on a WEEKLY SCHEDULE. Measured:

* the schedule is a Claude **Desktop** local task the repository can neither ask nor see fire
  (`BUG-0269` / H186) -- its day, hour and enabled flag live in the app, and a week with the app
  closed is silent;
* nothing in the repository states a cadence for the watchers any more. `tools/radar_routine.py
  --describe` is the declaration, and `tools/test_radar_trigger.py` refuses a text that promises a
  schedule without both the lead's record AND the report cadence -- but its subject is
  `radar/README.md` and the two role definitions, so the enforcement layer is outside its reader by
  construction.

The sentences GRANT nothing: `gate_spawn_needs_item` decides the exemption on the frontmatter key
`harness_item:` in the role's own definition, never on the word "schedule". The cost is a false
sentence in the layer a user reads when a spawn is refused.

## The patch

Three text changes, no behaviour. Apply with an editor or with `git apply`.

### 1. `.claude/hooks/gate_spawn_needs_item.py`, module docstring (line ~10)

Replace

```
role names. Two agents in this repo run on a weekly schedule and hold no item (`radar-watcher`,
```

with

```
role names. Two agents in this repo hold no item (`radar-watcher`,
```

and replace

```
frontmatter key `harness_item:` -- `none` for a schedule-driven role, and required for everything
```

with

```
frontmatter key `harness_item:` -- `none` for a role that holds none, and required for everything
```

### 2. `.claude/hooks/gate_spawn_needs_item.py`, the refusal text (line ~74)

Replace

```
        "scheduled watcher), its definition in .claude/agents/%s.md declares `%s: %s` in its "
```

with

```
        "watcher), its definition in .claude/agents/%s.md declares `%s: %s` in its "
```

### 3. `.claude/hooks/_harness.py`, `spawn_needs_an_item` docstring (line ~2849)

Replace

```
    this repo genuinely have no item -- the weekly watchers run on a schedule and write only into
```

with

```
    this repo genuinely have no item -- the watchers write only into
```

## After applying

* `python -B -m pytest .claude/hooks/test_gates.py -k "spawn" -q` -- the gate's behaviour is
  unchanged, so this run is a control and not the proof;
* restart the session (the registration binds at session start; the FILES are read per call, so the
  text takes effect immediately -- the restart is for cleanliness, not for correctness).

## What is still open after it

Nothing in `.claude/hooks/` is read by `tools/test_radar_trigger.py`, so a NEW schedule claim
written into the enforcement layer tomorrow is caught by nobody. Widening that reader's subject
means giving it a second corpus, and its subject today is DERIVED ("a role definition that declares
`harness_item: none` and names `radar/`, plus the radar README" --
`test_radar_trigger.TEXTS`). That widening is the goal round's, not this patch's.

---

# Beside it: two more locked files that still say "four gates" (TSK-0140 check, F7)

`CLAUDE.md` no longer states a count at all -- the table is the one statement and
`.claude/hooks/test_gates.py::test_the_gate_table_of_this_file_is_the_registration_itself` measures
it against the registration. Two files outside every role's reach still carry the old number in the
PRESENT tense, and both are the user's shell to change (`.claude/agents/**` and `.claude/hooks/
_harness.py` are forbidden scope for every role here).

### 4. `.claude/agents/harness-lead.md`, line ~33

Replace

```
decision refuses. So the enforcement is four gates of this repo's own, in `.claude/hooks/`,
```

with

```
decision refuses. So the enforcement is this repo's own gates, in `.claude/hooks/`,
```

(how many there are stands in `CLAUDE.md`'s table and nowhere else -- a count repeated in a role
text is the thing that aged here.)

### 5. `.claude/hooks/_harness.py`, line ~8

Replace

```
replaced by four gates written for this repo, plus a bound session agent so the payload shape the
```

with

```
replaced by gates written for this repo, plus a bound session agent so the payload shape the
```

### Not to change

`.claude/hooks/test_gates.py:1812` says "Measured on 2026-08-05 ... all four gates exited 1". That
is a PAST measurement with its date and it was true of the tree it was taken on -- a record, not a
claim about today. Rewriting it would falsify the measurement.
