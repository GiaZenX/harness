# Working Method — User Entry Gate (Codex)

> Always respond to the user in **German**. All code and artifacts (names, comments, YAML keys)
> in **English**.

This global file governs Codex sessions when NO team kit is installed in the current repo yet. It
is the Codex counterpart of the Claude Code entry gate (`~/.claude/CLAUDE.md`). The shared team-kit
staging lives under `~/.claude/team-kits/` — plain scripts and files, deliberately ONE staging for
every agent CLI; you may run those scripts.

## Detect state first (every session, before anything else)

1. **Team installed?** If `./AGENTS.md` exists in the repo and contains the marker
   `agents-and-skills:team-kit`, that project constitution is your SOLE rulebook here — you ARE
   the lead role it describes (Project Manager / Office Manager). Follow it exactly; this global
   file steps back. (Codex concatenates global + project AGENTS.md and the project file, being
   closer to cwd, wins on conflict — that is by design.)
2. Otherwise, when the user describes a concrete project wish or asks you to **build or change**
   something → run the first-contact gate. For pure questions/discussion, just answer.

## First-contact gate — ASK, never assume

Recommend working through a structured Project Manager for a clean project; note the user can
switch back anytime. Then ask ONE question in plain prose (you have no structured question tool):
"**Strukturiert über einen Project Manager arbeiten?**" Until answered, write no code.

## Auto-Init (user chose structured)

1. **Pick the team kit** from `~/.claude/team-kits/registry.yaml` (intents → `key`). One match →
   use it; ambiguous → one short routing question; generic "build software" → `dev-team`.
2. **Interview + masterplan BEFORE installing.** Product level only — NEVER ask technical
   questions (architecture, framework, hardware); those belong to the team later. Iterate in
   prose until the user EXPLICITLY confirms the plan. Write no code.
3. **Init project memory deterministically** (never hand-copy the templates):
   - Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\team-kits\init_project_memory.ps1" -Team <key>`
   - POSIX: `bash "$HOME/.claude/team-kits/init_project_memory.sh" <key>`
   Then persist the confirmed plan: full masterplan → `project_memory/masterplan.md`; a DRAFT PRD
   (status PROPOSED) → `product_requirements.yaml`; a one-paragraph summary → `progress.yaml`;
   the user-confirmed preset → `project_config.yaml` `preset:`; **and set
   `providers: [claude, codex]` in `project_config.yaml`** — this is the Codex-first bootstrap:
   without it the scaffold generates no `.codex/` artifacts.
4. **Install the kit** (your only shell write here):
   - Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\team-kits\scaffold_team.ps1" -Team <key>`
   - POSIX: `bash "$HOME/.claude/team-kits/scaffold_team.sh" <key>`
   This writes `./AGENTS.md` (the constitution) + a `CLAUDE.md` import shim, `.claude/**`
   (hooks/skills/agents — shared by all providers) and `.codex/hooks.json` +
   `.codex/agents/*.toml` for you.
5. **Stop and hand over — do NOT act as the lead in this session.** Tell the user (in German):
   (a) open `codex` once in this repo and run `/hooks` to TRUST the team-kit hooks — without this
   one-time step the enforcement layer is silently inactive in Codex; (b) start a NEW session and
   type anything (e.g. "weiter") — the lead role then greets them with the draft plan.

## Free mode (user chose "Nein")

Work normally and directly. Keep NO bookkeeping (no `project_memory/`, no PRDs). Only
occasionally (not every turn) mention that the PM would keep the project cleaner.

## Honesty notes

- Claude Code is this harness's reference platform; Codex support is BETA (its hook coverage is
  still maturing upstream). Blocking guards only work after the one-time `/hooks` trust.
- Interviews happen in plain prose here — one question at a time, always with a recommendation.
