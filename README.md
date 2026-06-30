# Agent Skills

Userwide-installable skills, a global **constitution**, and a **multi-agent role model** for
**GitHub Copilot** and **Claude Code** in VS Code.

Instead of a single assistant, this repo simulates a small software team: you are the **customer**, the
**main agent becomes your Project Manager (PM)** — your only point of contact — and specialized dev roles
(Architect, Backend, Frontend, QA, DevOps) work below it as **stateless subagents**. The role model and
`project_memory/` bookkeeping work in both tools; the **deterministic, blocking enforcement hooks run under
Claude Code** (the Claude Code VS Code extension included) — see [Parity](#parity-claude-code--copilot).

**Two-tier entry.** A user-wide **entry gate** (`CLAUDE.md` / `COPILOT.instructions.md`) drives the
default agent: on your first build/change wish it asks *structured or free*, classifies the effort via the
**team registry**, and **installs the matching team kit locally into the repository** (`./.claude/agents/`,
a local `./CLAUDE.md`, and enforcement hooks). From then on the **main agent itself acts as the PM**,
governed by that local `./CLAUDE.md` — there is **no separate PM subagent** to bypass or forget, and the PM
keeps the full conversation as its memory. The local constitution carries a marker; whenever it is present,
the entry gate **hands over to it completely** (every session). If you don't want the process, you choose
*free* and work without bookkeeping.

Two kits ship today: **`dev-team`** (software/product engineering) and **`research-team`** (research +
experiments with an FZulG R&D-tax-credit documentation layer). The registry maps your intent to the right
one.

Based on [mattpocock/skills](https://github.com/mattpocock/skills) plus a custom role model and a
global workflow standard.

---

## Quickstart

### Windows (PowerShell)

```powershell
git clone https://github.com/GiaZenX/AgentAndSkills.git agent-skills
cd agent-skills
.\install.ps1
```

### macOS / Linux

```bash
git clone https://github.com/GiaZenX/AgentAndSkills.git agent-skills
cd agent-skills
chmod +x install.sh
./install.sh
```

Restart VS Code afterwards.

### Options

| Option | Description |
|---|---|
| `-Target both` (default) | Installs for Claude Code **and** Copilot |
| `-Target claude` | Claude Code only (`~/.claude/skills/` + `~/.claude/CLAUDE.md`) |
| `-Target copilot` | Copilot only (`~/.copilot/skills/` + VS Code agents + instructions) |
| `-Force` | Overwrites already-installed files |

On Linux/Mac use `--target` and `--force` accordingly.

---

## Parity: Claude Code ↔ Copilot

The **shared layer** is installed once and read by **both** tools: the user-scope entry gate, the team
kits, the per-repo `./.claude/…` files, and the constitution. What **differs is enforcement** — the
blocking hooks and the `agent: project-manager` session setting are **Claude Code mechanisms** (the Claude
Code VS Code extension honors them too). Native GitHub Copilot Chat reads the same agent/skill/constitution
**prose** and follows it, but does **not execute** the hooks — so under Copilot the guarantees are
**advisory (prose), not tool-enforced**. For the fully enforced experience (merges actually blocked on a red
pipeline / missing tests / out-of-scope writes), drive the team with **Claude Code**.

| Component | Claude Code | Copilot |
|---|---|---|
| User entry gate | `~/.claude/CLAUDE.md` | `prompts/COPILOT.instructions.md` (`applyTo: **`) |
| Team kit staging | `~/.claude/team-kits/<team>/` | `~/.claude/team-kits/<team>/` (shared) |
| Project team (per repo) | `./.claude/agents/*.md` + `./CLAUDE.md` + `./.claude/settings.json` | same files |
| Role skills (per repo) | `./.claude/skills/<role>/` | same |
| Tool syntax | `AskUserQuestion` | `#tool:vscode_askQuestions` |
| Subagent call | Task tool | `runSubagent` |
| Templates | `~/.claude/team-kits/<team>/templates/project_memory/` | same (shared staging) |
| **Enforcement** (blocking hooks + `agent` setting) | ✅ **deterministic** — hooks fire, bad merges blocked | ⚠️ **prose-only** — no hook execution |

The project team is installed in **Claude format** (`./.claude/…` + root `./CLAUDE.md`), which **both** VS
Code Copilot and Claude Code read — one copy serves both ecosystems; the **hooks only execute under Claude
Code**.

---

## Install paths

| Component | Path |
|---|---|
| User entry gate (Claude Code) | `~/.claude/CLAUDE.md` |
| User entry gate (Copilot, VS Code) | `<vscode prompts>/COPILOT.instructions.md` (`applyTo: "**"`) |
| Team kit staging (shared) | `~/.claude/team-kits/<team>/` (agents, constitution, templates) + scaffold scripts |
| Project team (per repo, created on demand) | `./.claude/agents/*.md` + `./.claude/skills/` + `./CLAUDE.md` + `./.claude/settings.json` |
| Claude Code skills | `~/.claude/skills/<skill>/` |
| Copilot skills | `~/.copilot/skills/<skill>/` |
| VS Code prompts folder | Windows: `%APPDATA%\Code\User\prompts\` <br> macOS: `~/Library/Application Support/Code/User/prompts/` <br> Linux: `~/.config/Code/User/prompts/` |

---

## Repo structure

```
AgentAndSkills/
├── user/                               ← user-scope (~/.claude) install sources
│   ├── claude/
│   │   ├── CLAUDE.md                    ← user entry gate (Claude Code)
│   │   ├── settings.json                ← user defaults merged into ~/.claude/settings.json
│   │   └── statusline.py                ← status line (model · context · cost · branch)
│   ├── copilot/
│   │   └── COPILOT.instructions.md      ← user entry gate (applyTo: **)
│   └── merge_settings.py                ← installer helper: merge keys, preserve personal settings
├── team-kits/
│   ├── registry.yaml                    ← intent → kit routing (single source of truth)
│   ├── scaffold_team.ps1 / .sh          ← installs a kit into the current repo (backs up first)
│   ├── init_project_memory.ps1 / .sh    ← deterministically creates ./project_memory/ from kit templates (copy-if-absent)
│   ├── dev-team/
│   │   ├── agents/                      ← project-manager (session agent) + 7 specialist subagents
│   │   ├── skills/                      ← one role skill per agent (project-manager, software-architect, …)
│   │   ├── constitution/CLAUDE.md       ← project constitution → ./CLAUDE.md (carries team marker)
│   │   ├── hooks/ + settings/           ← deterministic enforcement hooks + .claude/settings.json (agent, model, …)
│   │   └── templates/project_memory/    ← YAML artifact templates
│   └── research-team/
│       ├── agents/ + skills/            ← project-manager + 6 specialists + their role skills
│       ├── constitution/CLAUDE.md       ← project research constitution (carries team marker)
│       ├── hooks/ + settings/           ← enforcement hooks + .claude/settings.json
│       └── templates/project_memory/    ← research artifacts + report template + bundled KaTeX
├── install.ps1                          ← Windows installer (backup + confirm + overwrite)
└── install.sh                           ← macOS/Linux installer
```

---

## How it starts (two-tier flow)

1. **Global gate asks** (non-coercive): on your first build/change wish the global `CLAUDE.md` /
   `COPILOT.instructions.md` asks *structured (PM) or free?*. Choose *free* and you work without
   bookkeeping.
2. **Auto-init (discovery first):** on *structured*, the default agent classifies your intent via
   `team-kits/registry.yaml`, then **interviews you and drafts a plan** (product-level questions + a
   recommended team) **before** installing — it writes that plan as a DRAFT into `project_memory/`. Only
   then does it run the scaffold script.
3. **Local install:** the kit's specialist agents are copied to `./.claude/agents/`, its constitution to
   `./CLAUDE.md` (with a team **marker**), and its enforcement **hooks + settings** to `./.claude/`. The
   first session then asks you to **restart**; from the next session the PM picks up the DRAFT plan.
4. **The main agent becomes the PM.** The kit's `.claude/settings.json` sets `agent: project-manager`, so the
   repo's main session agent **is** the PM (`model: opus`, persistent `memory: project`, a preloaded
   `project-manager` skill) — one identity, no relay, nothing to bypass. (The first session right after install is
   bridged in-session by the `./CLAUDE.md` marker handover; the `agent` setting takes over from the next
   session.) The PM runs the **startup gate** (creates `project_memory/` deterministically via the
`init_project_memory` script if missing, proposes
   preset + specialist models, you confirm, syncs the specialists' frontmatter), then begins the phase model.
   It maintains `project_memory/` itself and delegates only implementation to the stateless specialists.

---

## Multi-agent role model

The workflow lives in each kit's **constitution** (`CLAUDE.md`) and is executed by the **main agent acting
as PM** plus stateless specialist subagents. The PM is the only interface to the user, holds the
conversation as memory, maintains `project_memory/` itself, and delegates only implementation; specialists
return YAML. Roles below are the **`dev-team`**; the **`research-team`** mirrors the same machinery.

### Roles (dev-team)

| Role | File | Job | Talks to user |
|---|---|---|---|
| **Project Manager** | `project-manager` (the repo's session agent — `agent` setting; opus + memory) | Requirements (PRD/CR), `project_memory/` bookkeeping, delegation, merge, user acceptance | **Yes (only one)** |
| **Software Architect** | `software-architect` | System requirements, architecture, ADRs, coding guidelines, test strategy | No |
| **Product Designer** | `product-designer` | UI/UX: screens, flows, design system, accessibility (UI-bearing PRDs) — `design.yaml` | No |
| **Research Engineer** | `research-engineer` | Web-enabled investigation of libs/datasheets/APIs; cited facts — `research_notes.yaml` | No |
| **Backend Developer** | `backend-developer` | Server-side tasks, tests, commits | No |
| **Frontend Developer** | `frontend-developer` | UI tasks, tests, commits | No |
| **Quality Engineer** | `quality-engineer` | Review, tests (sole owner of test completeness), Definition of Done, merge gate | No |
| **DevOps Engineer** | `devops-engineer` | CI/CD, pipelines, environments, release | No |

### Roles (research-team)

Same two-tier machinery, research-flavored. Hierarchy: **Research Question (RQ) → Hypothesis (HYP) +
Experiment Design (EXP) → Tasks**; changes go through **Protocol Amendments (PA)**. The PM (lead) is again
the only customer-facing role.

| Role | File | Job |
|---|---|---|
| **Research Lead (PM)** | `project-manager` (the repo's session agent — `agent` setting; opus + memory) | RQs/PAs, `project_memory/` + **FZulG** bookkeeping, delegation, merge, user acceptance |
| **Methodologist** | `methodologist` | Hypotheses, experiment designs, MDRs, research guidelines, FZulG criteria |
| **Researcher** | `researcher` | Runs experiments, collects raw data, analysis code |
| **Data Analyst** | `data-analyst` | Statistics, effect sizes, visualization, interpretation |
| **Reviewer** | `reviewer` | Reproducibility + validity gate, peer review, merge gate |
| **Research Engineer** | `research-engineer` | Data pipelines, environments, dataset versioning |
| **Report Writer** | `report-writer` | Per-experiment HTML reports with offline LaTeX (KaTeX), fixed template |

### Phase model

`0 READ → 0.5 ASSESSMENT (existing repos only) → 1 PM_DISCOVERY → 2 PM_PROPOSAL →
3 USER_APPROVAL → 4 SYSTEM_PLANNING → 5 IMPLEMENTATION → 6 REVIEW → 7 TEST → 8 QA →
9 INTERNAL_ACCEPTANCE + MERGE → 10 USER_ACCEPTANCE`

- **Two-level acceptance:** PM/QA accept internally per branch/task; the **user only accepts per PRD**
  (on `main`, after the internal merge).
- **ASSESSMENT** runs only for existing repos: PM + Architect + QA produce a **gap report** (missing
  tests, guideline gaps, refactoring candidates, tech debt, security) — the user chooses what becomes
  a PRD/CR.

### Artifacts (`project_memory/`)

Structured YAML files in the repo — the **single source of truth**. Each role writes only its own area
(no overwriting); the **PM** creates `project_memory/` on the first run via the deterministic
`init_project_memory` script (copy-if-absent from the kit templates) and owns the requirement/progress
bookkeeping itself. The project evolves through four explicit requirement types, never silent edits: a
**user-story Feature Request (FR)** for new capability → triaged into a **PRD** (the delivered unit), a
**Change Request (CR)** for a change to an approved PRD, and a **Bug (BUG)** for a defect against approved
behaviour (with a mandatory regression test). **No ad-hoc status/summary/report files** are allowed — findings
go into the predefined YAML (this is also enforced by a hook, see below).

A user-facing **dashboard** (`progress.dashboard.html`) is generated, never hand-edited: the **PM** runs
`generate_dashboard.py`, which reads the requirement/task/CR YAML files, rebuilds the dashboard from a
static shell, archives the previous version under `dashboard_history/`, and lists what changed since the
last run. Bars expand to reveal the items behind each status (id, title, owner, origin, start/end dates).
Running the generator needs PyYAML (`pip install pyyaml`); the generated HTML is dependency-free and opens
by double-click.

### Git, presets & models

- **Branch per PRD** (`feat/PRD-xxx-…`), merge after internal QA, **push only on user confirmation**,
  no force-push, no work on a dirty tree.
- **Team preset** (`solo` | `duo` | `team`) chosen once per project; escalation is user-gated only.
- **Models:** the **PM (session agent) runs on `opus`** (set in the kit's `.claude/settings.json` + the PM's
  agent frontmatter); the **specialists default to `sonnet`** (haiku proved too weak for complex work in a
  real run), controlled per repo via `project_config.yaml` (the PM syncs each specialist's `model:`
  frontmatter — haiku only for simple roles, opus for the hardest). Dial the PM to `sonnet` if opus is too
  costly. Specialist upgrades only after a user OK (triggers: first QA fail or dissatisfaction).

### Memory

- **`project_memory/`** = the project's facts/state (authoritative single source of truth; the PM maintains it).
- **Agent memory** (`memory: project` → `.claude/agent-memory/<role>/MEMORY.md`) — every role keeps reusable
  **craft knowledge** across sessions (preferences, recurring patterns), kept strictly separate from project
  state. This is Claude Code's native persistent-subagent-memory feature.

### Enforcement (hooks)

Because instructions alone get skipped, each kit ships a small **deterministic** layer (Claude Code hooks in
`./.claude/settings.json` + `./.claude/hooks/`, installed by the scaffold):

- **No ad-hoc files** (`guard_no_adhoc`) — blocks writing status/summary/report files outside the allowlist
  (`project_memory/**`, `src/**`, `tests/**`, `docs/**`, configs).
- **No rogue spawns** (`guard_agent_spawn`) — blocks spawning a generic/unnamed agent; only the installed
  specialist roles may be spawned.
- **PM stays out of code** (`guard_pm_scope`) — blocks the PM (main agent) from writing `src/**`, `tests/**`,
  `frontend/**`; code goes to specialists, QA gates it.
- **Guidelines before code** (`guard_guidelines`) — blocks a code-writer from writing a language before its
  `coding_guidelines.yaml` `languages:` block exists, so the architect fills the rules first.
- **Real pipeline at merge** (`gate_pipeline`) — runs `scripts/quality.py` (lint/types/tests+coverage,
  secret/dep scan) and blocks on a red or missing pipeline; a self-reported "pass" does not suffice.
- **Commit / merge gate** (`gate_git`) — always blocks force-push; blocks push/merge without a passing QA
  report in the YAML.
- **Per-area test gate** (`gate_test_coverage`, dev-team) — blocks merge while any source area (e.g.
  `src/`, `frontend/src/`) has no tests, so a strong area can't mask an untested one.
- **Completeness gate** (`gate_memory_complete`) — blocks merge while a required `project_memory/` YAML is
  still empty/template (unless it is explicitly marked `applicable: false`).
- **Packaging gate** (`gate_packaging_decision`, dev-team) — blocks merge while `architecture.yaml`
  `packaging.method` is still TODO, so HOW the software ships is always a conscious decision (even "none /
  library" is valid) — the deterministic guard against a critical packaging tool (e.g. Docker) being forgotten.
- **Auto-dashboard** (`auto_dashboard`) — regenerates `progress.dashboard.html` whenever `project_memory/`
  changed.
- All hooks resolve the repo root via `${CLAUDE_PROJECT_DIR}` / an upward search (`_root.py`), so a shifted
  working directory can't silently disable a guard.

The kit's `.claude/settings.json` also sets `agent: project-manager`, `model: opus`, `plansDirectory: ./plans`,
and `permissions` (allow common build commands; deny reading secrets).

### Quality pipeline (tools, not review)

Clean code is enforced by **tools that block**, not by an agent reading code. The DevOps role sets up a CI +
local pipeline at project start — **format → lint → type-check → unit + integration tests → coverage gate
(≥ threshold) → security (SAST + secret scan) → dependency audit** — and "**pipeline green**" is a hard
Definition-of-Done / merge requirement (QA verifies it; a red pipeline is an automatic FAIL). The research
kit uses the same idea as a **reproducibility pipeline** (format/lint/type + a clean re-run reproducing the
numbers + dependency audit). Any role may flag tech-debt/refactoring to the PM; the architect/methodologist
owns the proposal.

### Status line & install backup

- The installer adds a **status line** (`~/.claude/statusline.py`) showing model · context-usage bar · cost ·
  git branch · 5h rate-limit, and **merges** opinionated global defaults into `~/.claude/settings.json`
  (telemetry off, no commit co-author trailer) — **your personal keys are preserved** and the previous file is
  backed up under `~/.claude/backups/`.
- Both the installer and the scaffold **back up** what they replace before overwriting (with a confirmation
  prompt on install).

### Agent Teams (optional, not default)

This harness uses **subagents** (sequential, dependency-aware, cost-controlled). Claude Code's experimental
**Agent Teams** (parallel teammates that message each other) are *not* enabled by default — our flow is
sequential, where subagents fit better. Enable them yourself (`env: CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`)
for parallel review / competing-hypothesis work if you want.

### Behavior

- **Anti-sycophancy:** never agree silently, justify decisions, push back on the user when needed.
- **The PM speaks plain language** (no jargon); between agents communication is fully technical.

---

## Skills & the three-layer model

Role instructions live in three tiers, each loaded where it's needed — no duplication:

| Tier | Holds | Loads into |
|---|---|---|
| **Constitution** (`./CLAUDE.md`) | shared law: hierarchy, phases, git, anti-sycophancy, memory rules, hard enforcement | the PM + every subagent |
| **Agent body** (short) | who the agent is, who it obeys, its core duty | the agent's system prompt |
| **Role skill** (`skills: [<role>]`) | *how* it works + which `project_memory/` files it reads/writes | preloaded into the agent |

Each team kit ships **one role skill per agent** (incl. the PM's `project-manager`) under
`team-kits/<kit>/skills/`. The scaffold installs them into the repo's `./.claude/skills/`, and each agent
preloads its own via `skills:` frontmatter. There are **no global skills** — everything is scoped to the
team repo and invocable with `/<role>` (e.g. `/project-manager`).

**Coverage guarantee:** every `project_memory/*.yaml` has a write-owner named in a role skill (a few are
partitioned co-owners: `tasks`, `results`, `tests/`), so no artifact is ever left unmaintained. The
`derives_from` chain runs **PRD → SR → TSK**; each owner updates the status of its own items.

---

## Your own fork / customization

To move the repo to a different GitHub account:

```bash
# 1. Create your own empty repo on GitHub (e.g. github.com/your-account/agent-skills)

# 2. Re-point the remote
cd agent-skills
git remote set-url origin https://github.com/your-account/agent-skills.git
git push -u origin main
```

On new machines just clone and run `install.ps1` / `install.sh`.

---

## Update

```powershell
cd ~\agent-skills
git pull
.\install.ps1 -Force
```

```bash
cd ~/agent-skills
git pull
./install.sh --force
```

---

## Uninstall

Delete the folders manually:
- `~/.claude/skills/`, `~/.claude/agents/`, `~/.claude/team-kits/`, `~/.claude/CLAUDE.md`
- `~/.copilot/skills/`
- VS Code prompts folder (see the path table above): the file `COPILOT.instructions.md`
- In each project: the local `./.claude/` (agents, hooks, `settings.json`) and `./CLAUDE.md` (only if you want to remove the team there)

---

## License

Skills from [mattpocock/skills](https://github.com/mattpocock/skills): MIT
Custom additions (workflow docs, installer): MIT
