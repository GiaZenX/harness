# Agent Skills

Userwide installierbare Skills und Custom Agents für **GitHub Copilot** und **Claude Code** in VS Code.

Basiert auf [mattpocock/skills](https://github.com/mattpocock/skills) plus eigenen Agents und einem globalen Workflow-Standard.

---

## Quickstart

### Windows (PowerShell)

```powershell
git clone https://github.com/GiaZenX/CopilotAgentAndSkills.git agent-skills
cd agent-skills
.\install.ps1
```

### macOS / Linux

```bash
git clone https://github.com/GiaZenX/CopilotAgentAndSkills.git agent-skills
cd agent-skills
chmod +x install.sh
./install.sh
```

VS Code anschließend neu starten.

### Optionen

| Option | Beschreibung |
|---|---|
| `-Target both` (default) | Installiert für Claude Code **und** Copilot |
| `-Target claude` | Nur Claude Code (`~/.claude/skills/` + `~/.claude/CLAUDE.md`) |
| `-Target copilot` | Nur Copilot (`~/.copilot/skills/` + VS Code Agents + Instructions) |
| `-Force` | Überschreibt bereits installierte Dateien |

Linux/Mac entsprechend `--target` und `--force`.

---

## Parität: Claude Code ↔ Copilot

Beide Tools sind identisch konfiguriert:

| Komponente | Claude Code | Copilot |
|---|---|---|
| Globale Anweisungen | `~/.claude/CLAUDE.md` | `prompts/project-memory.instructions.md` (`applyTo: **`) |
| Workflow | Identisch – `# Working Method` (Englisch, Antwort auf Deutsch) | Identisch – `# Working Method` (Englisch, Antwort auf Deutsch) |
| Tool-Syntax | `AskUserQuestions` | `#tool:vscode_askQuestions` |
| Skills | `~/.claude/skills/` | `~/.copilot/skills/` |
| Agent | – | `prompts/memory-engineer.agent.md` |
| User-Präferenzen | – | Copilot memory (`user-preferences.md`) |

---

## Installationspfade

| Komponente | Pfad |
|---|---|
| Claude Code Skills | `~/.claude/skills/<skill>/` |
| Claude Code Anweisungen | `~/.claude/CLAUDE.md` |
| Copilot Skills | `~/.copilot/skills/<skill>/` |
| Custom Agents (VS Code) | Windows: `%APPDATA%\Code\User\prompts\` <br> macOS: `~/Library/Application Support/Code/User/prompts/` <br> Linux: `~/.config/Code/User/prompts/` |
| Global Instructions | Gleicher Ordner wie Agents, mit `applyTo: "**"` |

---

## Repo-Struktur

```
agent-skills/
├── skills/                              ← gemeinsame Skills (Claude + Copilot)
├── claude-code/
│   └── CLAUDE.md                        ← globale Anweisungen für Claude Code
├── github-copilot/
│   ├── project-memory.instructions.md  ← auto-geladen in Copilot (applyTo: **)
│   ├── memory-engineer.agent.md        ← Agent mit Dialog-Loop + project_memory/
│   └── user-preferences.md             ← Copilot memory (Antwortsprache + Regeln)
├── install.ps1                          ← Windows Installer
└── install.sh                           ← macOS/Linux Installer
```

---

## Custom Agents

### `memory-engineer` — Hauptagent mit Gedächtnis

**Aufruf:** `@memory-engineer` oder Agent-Dropdown → memory-engineer

Mandatory Dialog-Loop + vollständiges Projekt-Memory-System:

- **Dialog vor Umsetzung:** Fragt immer zuerst per `askQuestions` — nie sofort implementieren
- **project_memory/ System:** Liest und pflegt alle sechs `project_memory/`-Dateien bei jedem Prompt
- **Work Loop:** READ → ASK → PROPOSE → CONFIRM → CODE → MEMORY → ASK
- **REQ/TSK-Format:** `REQ-XXXX` / `TSK-XXXX`, Status `PROPOSED → VALIDATED → IN PROGRESS → DONE-VALIDATED`
- **progress.md:** Wird in Schritt MEMORY nach jedem Task verpflichtend mit Metriken aktualisiert
- **Bug-Workflow:** Jeder Bug bekommt ein Requirement + Test

---

## Skills

Skills werden im Chat per `/<skill-name>` aufgerufen oder vom Agent automatisch geladen, wenn die Beschreibung passt.

### Engineering

| Skill | Aufruf | Was es macht |
|---|---|---|
| **debug** | `/debug` | Disziplinierte Bug-Diagnose: Reproduzieren → Minimieren → Hypothese → Instrumentieren → Fixen → Regressionstest |
| **tdd** | `/tdd` | Test-Driven Development mit Red-Green-Refactor-Loop |
| **review-plan** | `/review-plan` | Stresstest deines Plans gegen die Domain-Sprache; aktualisiert CONTEXT.md und ADRs |
| **refactor** | `/refactor` | Findet Refactoring-Chancen; konsolidiert eng gekoppelte Module |
| **plan-to-prd** | `/plan-to-prd` | Wandelt aktuellen Konversationskontext in ein PRD |
| **plan-to-issues** | `/plan-to-issues` | Zerlegt Plan/PRD in unabhängige GitHub-Issues (Vertical Slices) |
| **triage** | `/triage` | Issue-Triage durch Rollen-State-Machine |
| **explain** | `/explain` | Erklärt Code im Kontext des Gesamtsystems |
| **setup-repo** | `/setup-repo` | Einmal pro Repo: konfiguriert Issue-Tracker, Triage-Labels, Domain-Doc-Layout |

### Productivity

| Skill | Aufruf | Was es macht |
|---|---|---|
| **interview** | `/interview` | Befragt dich intensiv zu Plan/Design mit Polls — bis alle Entscheidungen geklärt sind |
| **brief-mode** | `/brief-mode` | Ultra-komprimierter Kommunikationsmodus, spart ~75% Tokens |
| **new-skill** | `/new-skill` | Hilft dir, eigene neue Skills zu erstellen |

### Misc

| Skill | Aufruf | Was es macht |
|---|---|---|
| **pre-commit** | `/pre-commit` | Husky Pre-Commit-Hooks mit Prettier, Type-Checking, Tests |
| **git-safety** | `/git-safety` | Nur Claude Code: blockiert gefährliche Git-Befehle (`push`, `reset --hard`, etc.) |

---

## Empfohlener Workflow

1. **Pro Repo einmal:** `/setup-repo`
2. **Vor jeder Änderung:** `/interview` oder `/review-plan`
3. **Implementierung:** `@memory-engineer <task>` oder `/tdd`
4. **Bei Bugs:** `/debug`
5. **Regelmäßig:** `/refactor`

---

## Eigenes Fork / Anpassungen

So überträgst du das Repo auf einen anderen GitHub-Account:

```bash
# 1. Eigenes leeres Repo auf GitHub erstellen (z.B. github.com/dein-account/agent-skills)

# 2. Remote umstellen
cd agent-skills
git remote set-url origin https://github.com/dein-account/agent-skills.git
git push -u origin main
```

Auf neuen Rechnern dann einfach klonen und `install.ps1` / `install.sh` ausführen.

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

## Deinstallation

Ordner manuell löschen:
- `~/.claude/skills/`
- `~/.copilot/skills/`
- VS Code prompts-Ordner (siehe Pfad-Tabelle oben), nur die `*.agent.md` Dateien

---

## Lizenz

Skills von [mattpocock/skills](https://github.com/mattpocock/skills): MIT
Eigene Ergänzungen (`memory-engineer.agent.md`, Workflow-Docs, Installer): MIT
