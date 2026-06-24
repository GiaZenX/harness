# Agent Skills

Userwide-installable skills, a global **constitution**, and a **multi-agent role model** for
**GitHub Copilot** and **Claude Code** in VS Code.

Instead of a single assistant, this repo simulates a small software team: you are the **customer**,
a **Project Manager (PM)** is your only point of contact, and below it specialized dev roles
(Architect, Backend, Frontend, QA, DevOps) work as subagents. No matter which tool you code with, the
AI behaves identically.

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

Both tools are configured identically. The whole workflow lives in the **global instructions** and
therefore applies to **every** agent / default mode — no matter what you code with, the AI behaves the
same:

| Component | Claude Code | Copilot |
|---|---|---|
| Global instructions | `~/.claude/CLAUDE.md` | `prompts/COPILOT.instructions.md` (`applyTo: **`) |
| Workflow | Identical — `# Working Method` | Identical — `# Working Method` |
| Tool syntax | `AskUserQuestions` | `#tool:vscode_askQuestions` |
| Agents | `~/.claude/agents/*.md` | VS Code prompts folder `*.agent.md` |
| Subagent call | Task tool | `runSubagent` |
| Templates | `~/.claude/templates/project_memory/` | `~/.copilot/templates/project_memory/` |
| Skills | `~/.claude/skills/` | `~/.copilot/skills/` |

---

## Install paths

| Component | Path |
|---|---|
| Claude Code skills | `~/.claude/skills/<skill>/` |
| Claude Code instructions | `~/.claude/CLAUDE.md` |
| Claude Code agents | `~/.claude/agents/*.md` |
| Claude Code templates | `~/.claude/templates/project_memory/` |
| Copilot skills | `~/.copilot/skills/<skill>/` |
| Copilot templates | `~/.copilot/templates/project_memory/` |
| Copilot agents + global instructions (VS Code) | Windows: `%APPDATA%\Code\User\prompts\` <br> macOS: `~/Library/Application Support/Code/User/prompts/` <br> Linux: `~/.config/Code/User/prompts/` <br> Files `*.agent.md` + `COPILOT.instructions.md` (`applyTo: "**"`) |

---

## Repo structure

```
agent-skills/
├── skills/                              ← shared skills (Claude + Copilot)
├── claude-code/
│   ├── CLAUDE.md                        ← constitution for Claude Code
│   └── agents/                          ← 6 roles (project-manager, architect, …)
├── github-copilot/
│   ├── COPILOT.instructions.md          ← constitution (auto-loaded, applyTo: **)
│   └── agents/                          ← 6 roles as *.agent.md
├── templates/
│   └── project_memory/                  ← YAML artifact templates (the PM copies them into the repo)
├── install.ps1                          ← Windows installer
└── install.sh                           ← macOS/Linux installer
```

---

## Multi-agent role model

The workflow lives in the **constitution** (`CLAUDE.md` / `COPILOT.instructions.md`) and is executed
by **6 role agents**. The PM is the entry point and the only interface to the user; the dev roles work
as subagents and return YAML.

### Roles

| Role | File | Job | Talks to user |
|---|---|---|---|
| **Project Manager** | `project-manager` | Requirements (PRD/CR), delegation, merge, user acceptance | **Yes (only one)** |
| **Architect** | `architect` | System requirements, architecture, ADRs, coding guidelines | No |
| **Backend** | `backend` | Server-side tasks, tests, commits | No |
| **Frontend** | `frontend` | UI tasks, tests, commits | No |
| **QA** | `qa` | Review, tests, Definition of Done, merge gate | No |
| **DevOps** | `devops` | CI/CD, pipelines, environments, release | No |

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

Structured YAML files in the repo. Each role writes only its own area (no overwriting). The PM creates
`project_memory/` on the first run from the globally installed templates.

A user-facing **dashboard** (`progress.dashboard.html`) is generated, never hand-edited: the PM runs
`generate_dashboard.py`, which reads the PRD/task/CR YAML files, rebuilds the dashboard from a static
shell, archives the previous version under `dashboard_history/`, and lists what changed since the last
run. Bars expand to reveal the items behind each status (id, title, owner, origin, start/end dates).
Running the generator needs PyYAML (`pip install pyyaml`); the generated HTML is dependency-free and
opens by double-click.

### Git, presets & models

- **Branch per PRD** (`feat/PRD-xxx-…`), merge after internal QA, **push only on user confirmation**,
  no force-push, no work on a dirty tree.
- **Team preset** (`solo` | `duo` | `team`) chosen once per project; escalation is user-gated only.
- **Models** start on `haiku`; controlled per repo via `project_config.yaml`. Upgrades only after a
  user OK (triggers: 2× QA fail or dissatisfaction). The agent files themselves are model-neutral —
  nothing global is ever rewritten.

### Behavior

- **Anti-sycophancy:** never agree silently, justify decisions, push back on the user when needed.
- **The PM speaks plain language** (no jargon); between agents communication is fully technical.

---

## Skills

Skills are invoked in chat via `/<skill-name>` or loaded automatically by the agent when the
description matches.

### Engineering

| Skill | Invoke | What it does |
|---|---|---|
| **debug** | `/debug` | Disciplined bug diagnosis: reproduce → minimize → hypothesize → instrument → fix → regression test |
| **tdd** | `/tdd` | Test-driven development with the red-green-refactor loop |
| **review-plan** | `/review-plan` | Stress-tests your plan against the domain language; updates CONTEXT.md and ADRs |
| **refactor** | `/refactor` | Finds refactoring opportunities; consolidates tightly coupled modules |
| **plan-to-prd** | `/plan-to-prd` | Turns the current conversation context into a PRD |
| **plan-to-issues** | `/plan-to-issues` | Breaks a plan/PRD into independent GitHub issues (vertical slices) |
| **triage** | `/triage` | Issue triage via a role state machine |
| **explain** | `/explain` | Explains code in the context of the whole system |
| **setup-repo** | `/setup-repo` | Once per repo: configures issue tracker, triage labels, domain doc layout |

### Productivity

| Skill | Invoke | What it does |
|---|---|---|
| **interview** | `/interview` | Interviews you intensively about a plan/design with polls — until every decision is resolved |
| **brief-mode** | `/brief-mode` | Ultra-compressed communication mode, saves ~75% tokens |
| **new-skill** | `/new-skill` | Helps you create your own new skills |

### Misc

| Skill | Invoke | What it does |
|---|---|---|
| **pre-commit** | `/pre-commit` | Husky pre-commit hooks with Prettier, type checking, tests |
| **git-safety** | `/git-safety` | Claude Code only: blocks dangerous git commands (`push`, `reset --hard`, etc.) |

---

## Recommended workflow

1. **Once per repo:** `/setup-repo`
2. **Before any change:** `/interview` or `/review-plan`
3. **Implementation:** `/tdd` or directly in chat (the workflow applies automatically)
4. **On bugs:** `/debug`
5. **Regularly:** `/refactor`

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
- `~/.claude/skills/`, `~/.claude/agents/`, `~/.claude/templates/`
- `~/.copilot/skills/`, `~/.copilot/templates/`
- VS Code prompts folder (see the path table above): the files `*.agent.md` and `COPILOT.instructions.md`

---

## License

Skills from [mattpocock/skills](https://github.com/mattpocock/skills): MIT
Custom additions (workflow docs, installer): MIT
