# Radar — weekly harness intelligence

A **watcher duo** writes dated reports here, same report shape so the two can be laid side by side
(one watcher often finds what the other misses):

- **claude-watcher** (`.claude/agents/claude-watcher.md`) — the Anthropic/Claude half. Also runs
  **repo health** (`tools/validate.py`, `pytest tools/`, `ruff check .`) and notes any drift.
- **codex-watcher** (`.claude/agents/codex-watcher.md`) — the OpenAI/Codex half (Codex CLI
  mechanics, GPT model lineup, AGENTS.md standard).

The duo was renamed in DEC-0090 (1): the Claude half used to be named after this directory, and that
name survives only in history — the dated reports below, `decided.md`, archived items, and the
folder on the maintainer's host named in the bullet list further down. **This directory and
`tools/radar_routine.py` keep their names on purpose**: radar is the DUO's product, not one
watcher's.

## Four reports a week, because each watcher runs under both providers

DEC-0090 (3): every watcher is executed by **both** model families — what one misses the other may
find — so a report name carries the watcher AND the runner:

| file | watcher (what was scanned) | runner (who executed it) |
|---|---|---|
| `radar/<date>-claude-by-claude.md` | claude-watcher | Claude |
| `radar/<date>-claude-by-codex.md` | claude-watcher | Codex |
| `radar/<date>-codex-by-claude.md` | codex-watcher | Claude |
| `radar/<date>-codex-by-codex.md` | codex-watcher | Codex |

The reports written before that decision keep their two-part names (`<date>-claude.md`,
`<date>-codex.md`) — history is not rewritten. `tools/radar_routine.py` counts such a name as a run
of that watcher by its own provider, which keeps the history countable; the file names of those
weeks simply do not record who ran them.

## How a run starts (DEC-0089, DEC-0090 (4))

The mechanism is a **local routine of the app that runs it** — a Claude Desktop scheduled task for
each of the two Claude halves, an Automation of the Codex app for each of the two Codex halves, four
in all and on four evenings so that no two fire at once, and until each of them is created and
recorded the lead starts that run by hand. `python tools/radar_routine.py --describe` prints all
four with the exact Instructions text that creates each one, and the lead reads that out rather than
retyping it here.

- **Recorded and running: the claude-watcher's Friday run.** A Claude Desktop scheduled task
  created by this repository's session agent on 2026-06-30
  (`~/.claude/scheduled-tasks/radar-watcher/SKILL.md` — the folder keeps the name the task was
  created under) started it on Friday evenings, and the reports show it: `2026-07-17` to
  `2026-08-28` were written between 20:10 and 20:47, with one Sunday catch-up on `2026-08-16`. It
  is the one entry in `radar/routine.json`.
- **Not created yet: the other three.** Until the user has made them in the two apps and each has
  run twice on its own evening, the lead starts what is missing by hand — `--run <watcher>` when
  `--due` names it, which starts a Claude run and can start no other.
- **The rejected alternative** — a hosted code routine of the platform, running in a sandbox
  against the remote and returning each report as a pull request (DEC-0085) — is not built;
  `--describe` keeps it under `cloud_option` only as a documented option that says so.

**What the repository can measure of that, and what it cannot.** Every Desktop task and every Codex
Automation keeps its day, hour and enabled flag in the app that owns it and in no file here; what
`radar/routine.json` holds is the schedule as the user stated it to the lead, with its source, and
what the reports themselves show. So
`starts_itself` is derived per watcher from both — a recorded routine AND at least two of that
watcher-and-runner's reports on the recorded weekday, for **every** run that watcher owes — and
whether a recorded task's file is present on THIS host is reported beside it and judged by nothing.
The limit is named rather than hidden: an app fires its routine only while it is open and the
machine awake (one catch-up run within seven days), so a week with an app closed is silent, and
`--due` is what notices.

**The session half** is `tools/radar_routine.py` itself:

- `python tools/radar_routine.py` — which routine owes a run this ISO week, and what its last dated
  report was;
- `python tools/radar_routine.py --run <watcher>` — starts that watcher here and now (the runner is
  Claude, because that is the CLI this starts), and reports which dated file appeared; a second run
  in a week that already has that report is refused unless `--force` is given;
- `python tools/radar_routine.py --describe` — the whole declaration as JSON: the four routines with
  their Instructions texts, what is recorded, and how many reports this directory holds (derived,
  never written into prose that then rots);
- `python tools/radar_routine.py --write-overlays` — regenerates `.codex/agents/<watcher>.toml` from
  the Claude definition and `team-kits/model_tiers.yaml`. The Claude definition is the source a
  human edits; the Codex overlay is generated, which is why the model id and the effort are never
  typed twice.

**These sentences are guarded**: `tools/test_radar_trigger.py` reads this file and both watcher
definitions against `--describe`, per watcher — a sentence about a watcher whose weekly runs are not
all started by a recorded routine has to say who starts the rest, and a sentence that names the
rejected alternative as the mechanism is refused in every state.

**Triage stays the lead's**: no run, however started, writes `decided.md`.

Both scan externally — what's new in their ecosystem plus the **agent community** (orchestration,
eval, prompting), filtered for **relevance to THIS harness**, and both carry the STANDING
source-format divergence duty (see HARNESS_LOG 2026-07-14 trip-wire). Every item carries a
**source URL + the date it was seen** — no source, no item.

The agent **never changes code** — it only writes reports here. You and the assistant then **triage** each
item (accept → becomes a hardening change, or reject) and record the verdict in `decided.md`, which the
watcher reads first each week so nothing is ever re-surfaced.

## Report shape (per candidate)
- **Title** · source URL · date seen
- **What it is** (1–2 lines)
- **Why it could help this repo** (concrete: which gate / skill / flow / artifact it improves)
- **Recommendation**: adopt / watch / ignore · rough effort
- **Status**: NEW (until triaged)

## Triage
Read the latest report, decide per item, and append the decision to `decided.md`
(`<slug> | <title> | accept|reject | <date> | <note>`). A decided line is a POINTER, never the
change itself: an accepted finding becomes an item under the open goal (`capture BUG` / `capture FR`
with `related_pr`) at triage, and a stream works it under that item -- `BUG-0092` measured what
happens otherwise (three reports, one dead line, nothing changed until an item carried it).
Rejected items stay in `decided.md` so the watcher skips them next week.
