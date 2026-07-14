# Radar — weekly harness intelligence

A scheduled **watcher duo** runs once a week and writes dated reports here, same report shape so
the two can be laid side by side (one watcher often finds what the other misses):

- **radar-watcher** (`.claude/agents/radar-watcher.md`) — the Anthropic/Claude half →
  `radar/YYYY-MM-DD-claude.md`. Also runs **repo health** (`tools/validate.py`, `pytest tools/`,
  `ruff check .`) and notes any drift.
- **codex-watcher** (`.claude/agents/codex-watcher.md`) — the OpenAI/Codex half →
  `radar/YYYY-MM-DD-codex.md` (Codex CLI mechanics, GPT model lineup, AGENTS.md standard).

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
(`<slug> | <title> | accept|reject | <date> | <note>`). Accepted items become normal harness changes
(committed); rejected items stay in `decided.md` so the watcher skips them next week.
