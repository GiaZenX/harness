# Radar — weekly harness intelligence

A **watcher duo** writes dated reports here, same report shape so the two can be laid side by side
(one watcher often finds what the other misses):

- **radar-watcher** (`.claude/agents/radar-watcher.md`) — the Anthropic/Claude half →
  `radar/YYYY-MM-DD-claude.md`. Also runs **repo health** (`tools/validate.py`, `pytest tools/`,
  `ruff check .`) and notes any drift.
- **codex-watcher** (`.claude/agents/codex-watcher.md`) — the OpenAI/Codex half →
  `radar/YYYY-MM-DD-codex.md` (Codex CLI mechanics, GPT model lineup, AGENTS.md standard).

**How a run starts (DEC-0089).** The mechanism is a **Claude Desktop scheduled task per watcher**
on the maintainer's host — a local routine of the Desktop app, not anything this repository runs;
where no such task is recorded yet, the lead starts a run by hand.

- **The radar-watcher's Desktop task exists and runs**: created by this repository's session agent
  on 2026-06-30 (`~/.claude/scheduled-tasks/radar-watcher/SKILL.md`, delegating to
  `.claude/agents/radar-watcher.md`), it starts the radar-watcher on Friday evenings, and the
  reports show it — `2026-07-17` to `2026-08-28` were written between 20:10 and 20:47 on Fridays,
  with one Sunday catch-up on `2026-08-16`. It is recorded in `radar/routine.json`.
- **The codex-watcher has no recorded Desktop task yet**: the user creates one of the same kind in
  the Desktop app (DEC-0089 names Saturday ~20:00, a day apart because the app skips a task while
  another is running), and until the lead records it and it has run twice on its weekday, the lead
  starts the codex-watcher by hand with `--run codex-watcher` when `--due` names it.
- **The rejected alternative** — a hosted code routine of the platform, running in a sandbox against
  the remote and returning each report as a pull request (DEC-0085) — is NOT built; `--describe`
  keeps it under `cloud_option` only as a documented option that says so.

**What the repository can measure of that, and what it cannot.** The radar-watcher's task keeps
its day, hour and enabled flag in the Desktop app and in no file here; what `radar/routine.json`
holds is the schedule as the user stated it, with its source, and what the reports themselves show. So `starts_itself` is
derived per watcher from both — a recorded task AND at least two of that watcher's reports on the
recorded weekday — and whether the task file is present on THIS host is reported beside it and
judged by nothing. The limit is named rather than hidden: the app fires the radar-watcher's task
only while it is open and the machine awake (one catch-up run within seven days), so a week with the
app closed is silent, and `--due` is what notices.

**The session half** is `tools/radar_routine.py` itself:

- `python tools/radar_routine.py` — which watcher owes a run this ISO week, and what its last dated
  report was;
- `python tools/radar_routine.py --run <watcher>` — starts that watcher here and now, and reports
  which dated file appeared (a second run in a week that already has its report is refused unless
  `--force` is given);
- `python tools/radar_routine.py --describe` — the whole declaration as JSON, including how many
  reports this directory holds (derived, never written into prose that then rots).

**These sentences are guarded**: `tools/test_radar_trigger.py` reads this file and both watcher
definitions against `--describe`, per watcher — a sentence about a watcher no recorded task starts
has to say who starts a run, and a sentence that names the rejected cloud alternative as the
mechanism is refused in every state.

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
