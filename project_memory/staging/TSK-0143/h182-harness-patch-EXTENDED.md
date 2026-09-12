# List (i) -- the patch for a shell OUTSIDE Claude Code, extended (stream C, TSK-0143)

This is `project_memory/staging/TSK-0140/h182-harness-patch.md` with the rows this round locked
appended as sites 6 and 7. It is a NEW file rather than an edit of that one, because
`project_memory/staging/TSK-0140/` lies in this item's `forbidden_scope`; the lead carries it over.

**Sites 1-5 are unchanged.** They are in `staging/TSK-0140/h182-harness-patch.md` and are repeated
here so the user has one file to work from. Every one of them is a TEXT change: no gate decides
differently afterwards, and each removes a sentence that claims something the code does not build.

Why a user's shell: `.claude/hooks/**`, `.claude/agents/**` and `.claude/settings.json` are the
forbidden scope of every role in this repository. Gate 1 refuses `.claude/` to the session agent,
and a broken gate cannot be repaired from inside the session that runs it. Apply with an editor or
`git apply`, then restart the session.

---

## Sites 1-3 -- H182 / BUG-0264: four sentences claiming a weekly schedule nothing builds

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

## Sites 4-5 -- two more locked files that still say "four gates" (TSK-0140 check, F7)

### 4. `.claude/agents/harness-lead.md`, line ~33

Replace

```
decision refuses. So the enforcement is four gates of this repo's own, in `.claude/hooks/`,
```

with

```
decision refuses. So the enforcement is this repo's own gates, in `.claude/hooks/`,
```

### 5. `.claude/hooks/_harness.py`, line ~8

Replace

```
replaced by four gates written for this repo, plus a bound session agent so the payload shape the
```

with

```
replaced by gates written for this repo, plus a bound session agent so the payload shape the
```

---

## NEW -- site 6: the third "four gates" in the present tense

MEASURED 2026-09-12 (stream C): `.claude/settings.json` registers **five** gate scripts out of
`.claude/hooks/`, and the docstring of `_harness._expands_a_tilde` still calls that file "the
registration of all four gates". Same class as sites 4 and 5 -- a count in the prose that aged the
day a gate was added (BUG-0268 / H185) -- and the last one of it in this layer that is written in
the present tense. `.claude/hooks/test_gates.py:554-561` says so, with this patch named beside it:
until it is applied, a tripwire over the whole layer would be red for a line nobody here may write.

### 6. `.claude/hooks/_harness.py`, `_expands_a_tilde` docstring (line ~1596)

Replace

```
    chain needs no preparation: end to end the same shape emptied `.claude/settings.json`, which is
    the registration of all four gates.
```

with

```
    chain needs no preparation: end to end the same shape emptied `.claude/settings.json`, which is
    the registration of every gate this repo runs.
```

NOT to change, for the same reason the TSK-0140 patch gives: `.claude/hooks/test_gates.py:1902`
says "Measured on 2026-08-05 ... all four gates exited 1". That is a PAST measurement with its
date, true of the tree it was taken on. Rewriting it would falsify the measurement.

(Both line numbers above were refreshed in rework 1 -- this round's own additions to that file moved
them, and a line pointer that has aged sends a reader to the wrong place even while the anchor text
is still exact. The ANCHOR blocks of every site below carry no line number and resolve on their
text alone; the `line ~n` in their headings is a hint, not the address.)

---

## NEW -- site 7: the registration cites a contract that was replaced (H207 / BUG-0291)

MEASURED 2026-09-12 (stream C, probe `_round-scratch/TSK-0143/probe_contracts.py`, using the
shipped reader `_harness.resolve_references` and the kernel's own contract types): four surfaces
outside the `.py` sources of `.claude/hooks/` were read for a citation of a REPLACED contract that
stands alone -- role definitions **0**, `CLAUDE.md` **0**, `docs/**.md` **4** (all historical
mentions in hole and review entries), the registration **1**.

That one is a LIVE citation in the file the provider reads:

> "The PreToolUse gates below are the replacement SR-0006 specifies"

`SR-0006` was replaced by `SR-0009` and archived on 2026-08-13. The sentence grants nothing -- no
gate decides on it -- but it sends a reader to a rule that does not bind, which is exactly the
defect BUG-0035 was made of. It is also the ONE thing standing between this repository and a
tripwire over those four surfaces: with it repaired, the widened check is buildable and green.

### 7. `.claude/settings.json`, the `_comment` (line 2)

Replace (inside the long `_comment` string, once)

```
The PreToolUse gates below are the replacement SR-0006 specifies
```

with

```
The PreToolUse gates below are the replacement SR-0009 specifies (it replaced SR-0006 on 2026-08-13)
```

## After applying

* `python -B -m pytest .claude/hooks/test_gates.py -q -k "registration or gate_table or spawn"` --
  a control, not a proof: none of the seven sites changes a verdict;
* restart the session. The registration binds at session start; the FILES are read per call, so the
  text takes effect at once and the restart is for cleanliness.

## What is still open after it

* The tripwire that would CATCH a new such sentence in the registration, in a role definition, in
  `CLAUDE.md` or under `docs/` is specified and measured (H207 / BUG-0291) and not built: it is red
  on site 7 until site 7 is applied, and no role of this round may apply it. Once the user has, it
  is a small round.
* Nothing in `.claude/hooks/` is read by `tools/test_radar_trigger.py`, so a NEW schedule claim
  written into the enforcement layer tomorrow is caught by nobody (the TSK-0140 patch says the
  same). That widening is the goal round's.
