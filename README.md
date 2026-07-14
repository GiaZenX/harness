# Agent Skills

A global **entry-gate constitution** and installable **multi-agent team kits** (dev, research,
office) for **Claude Code and Codex CLI**. Role skills ship inside the
team kits (per repo); there are no userwide skills anymore.

Instead of a single assistant, this repo simulates a small software team: you are the **customer**, the
**main agent becomes your Project Manager (PM)** — your only point of contact — and specialized dev roles
(Architect, Backend, Frontend, QA, DevOps) work below it in **ephemeral subagent runs**. Selected
Claude roles may keep role-scoped craft memory; generated Codex projects disable host/task memory
and use checked-in `project_memory/`. The role model and bookkeeping work in both tools. Claude and current Codex builds both provide
blocking pre-tool hooks; Codex additionally uses native permission profiles and event-specific
post/stop outputs. Dev/research add deterministic CI backstops, while Office relies on its blocking
guards, deterministic scripts and external outbound policy — see [Multi-provider support](#multi-provider-support-claude-code--codex-cli).

**Two-tier entry.** A user-wide **entry gate** (`~/.claude/CLAUDE.md` or `$CODEX_HOME/AGENTS.md`)
drives the
default agent: on your first build/change wish it asks *structured or free*, classifies the effort via the
**team registry**, and **installs the matching team kit locally into the repository**. From then on
the **main agent itself acts as the PM**, governed by canonical `./AGENTS.md`: Claude binds it through
`.claude/settings.json`; Codex binds the same lead body, model and native skill through
`.codex/config.toml`. There is **no separate PM subagent** to bypass or forget. The local constitution carries a marker; whenever it is present,
the entry gate **hands over to it completely** (every session). If you don't want the process, you choose
*free* and work without bookkeeping.

Three kits ship today: **`dev-team`** (software/product engineering), **`research-team`** (research +
experiments with an FZulG R&D-tax-credit documentation layer) and **`office-team`** (back-office
automation: inbox-driven filing, bookkeeping preparation, product/content care, compliance research,
marketing planning — drafts only, no tax/legal advice). The registry maps your intent to the right one.

Everything here — role model, constitutions, hooks, skills and workflow standard — is authored in
this repo (early versions started from an external skills collection; none of that content remains).

---

## Quickstart

Prerequisite: Python 3 with PyYAML (`python -m pip install pyyaml`). Codex targets require a
current host; a detected Codex below 0.131.0 (hooks GA + per-hash trust flow) is rejected. The
installer validates the kit before replacing any managed configuration.

### Windows (PowerShell)

```powershell
git clone https://github.com/GiaZenX/harness.git agent-skills
cd agent-skills
.\install.ps1
```

### macOS / Linux

```bash
git clone https://github.com/GiaZenX/harness.git agent-skills
cd agent-skills
chmod +x install.sh
./install.sh
```

Start a new Claude/Codex session afterwards.
An existing `$CODEX_HOME/AGENTS.override.md` is preserved and takes precedence over the installed
`AGENTS.md`, so the Codex gate stays inactive until you deliberately merge/remove that override.

### Options

| Option | Description |
|---|---|
| `-Target both` (default) | Installs for Claude Code **and** Codex CLI |
| `-Target claude` | Claude Code only (`~/.claude/CLAUDE.md` + `~/.claude/team-kits/` + statusline) |
| `-Target codex` | Codex entry gate (`$CODEX_HOME/AGENTS.md`) + shared team-kit staging |
| `-CodexGlobalSecrets` | OPT-IN: appends the user-wide Codex secret shield to `$CODEX_HOME/config.toml` (marked, removable block; see the Codex note under Design decisions) |
| `-Force` | Overwrites already-installed files |

On Linux/Mac use `--target` and `--force` accordingly.

---

## Multi-provider support: Claude Code · Codex CLI

One kit source, generated provider artifacts — never hand-cloned. The shared `.claude/**` baseline
is always installed as the canonical source (Claude itself need not be installed or started). The constitution ships as
**`./AGENTS.md`** (the vendor-neutral Linux-Foundation/AAIF standard that Codex, Cursor
and many other tools read natively) plus a thin **`./CLAUDE.md` import shim** (`@AGENTS.md` —
Anthropic's documented bridge; verified: subagents inherit the imported content). With
`codex` in `providers:` (the template default is `[claude, codex]`, so a mid-project CLI switch
needs no config edit; a legacy config without the line gets the same default) every scaffold run
generates `.codex/config.toml`, `.codex/hooks.json`, `.codex/agents/*.toml` and native
`.agents/skills/` from the installed state (`team-kits/gen_provider_artifacts.py`). Provider
removal and preset downgrades remove only outputs
recorded in generated manifests. Both providers reuse the same `.claude/hooks/*.py` sources;
`hooks/_compat.py` absorbs payload and documented stop-output differences. Models are tier-mapped per provider
(`team-kits/model_tiers.yaml`; kit sources carry only the neutral aliases `lead`/`worker`/`light`,
resolved per provider at install time). A namespaced `codex:` frontmatter overlay merges
Codex-only TOML keys the Claude-native source format cannot express — the sanctioned divergence
valve; both watchers flag when either platform outgrows it (trip-wire criteria in HARNESS_LOG).
Copilot support was removed 2026-07-14 (unused, live-unverified); stale generated `.github`
artifacts from older scaffolds are still recognized and cleaned up.

Honest parity matrix (verified 2026-07 against official docs; the codex-watcher tracks changes):

| Guarantee | Claude Code | Codex CLI (BETA) |
|---|---|---|
| Constitution + skills + project_memory | ✅ native | ✅ `AGENTS.md` + native `.agents/skills` (generated config raises project-doc budget to 64 KiB) |
| Secret-file protection | ✅ Claude permissions | ✅ Codex permission profile (`.env`, keys, PEM, `secrets/**` denied)¹ |
| PreToolUse file/shell guards | ✅ blocking | ✅ command exit 2 + stderr blocks in current Codex; requires project + `/hooks` trust |
| PostToolUse + SubagentStop contracts | ✅ blocking | ✅ event-specific blocking/continuation output after project + `/hooks` trust |
| Spawn guard (work orders, no 2nd PM) | ✅ blocking | ⚠️ exact-role policy + self-validating work orders; built-in roles remain available and `SubagentStart` cannot veto the requested spawn |
| Per-agent tool allowlists | ✅ agent frontmatter | ⚠️ no equivalent custom-agent `tools` field; instructions + sandbox/permissions + blocking hooks enforce boundaries |
| Lead = foreground session | ✅ `agent:` setting | ✅ `.codex/config.toml` model/developer instructions + native lead skill |
| Second line of defense | ✅ dev/research: `kit_checks` + CI; Office: guards + deterministic office scripts | ✅ same kit-specific boundary; Office ships no repo-level CI and needs external outbound policy |

¹ Permission profiles are ignored if a user or CLI explicitly selects legacy `sandbox_mode`; this is
an upstream Codex precedence rule, not something a repository can override.

Bottom line: current Codex has equivalent bootstrap, foreground lead, models, native skills, secret
boundaries and blocking pre-tool enforcement for the registered guards. It is not mechanically
identical to Claude: Codex's built-in roles cannot be disabled by this kit and `SubagentStart` does
not veto a requested spawn. Dev/research therefore retain CI; Office deliberately states its weaker
outbound boundary instead of claiming a CI backstop it does not ship.

Codex mappings follow the official documentation for [project config](https://learn.chatgpt.com/docs/config-file/config-basic),
[custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[skills](https://learn.chatgpt.com/docs/build-skills),
[hooks](https://learn.chatgpt.com/docs/hooks), the current Codex
[PreToolUse implementation](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/events/pre_tool_use.rs),
[PostToolUse implementation](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/events/post_tool_use.rs),
[stop-event implementation](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/events/stop.rs), and
[hook discovery/trust hashing](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/engine/discovery.rs), plus
[permission profiles](https://learn.chatgpt.com/docs/permissions).

The installer ships a user entry gate for both surfaces — `~/.claude/CLAUDE.md` (Claude Code)
and `$CODEX_HOME/AGENTS.md` (Codex). They share the
structured/free choice, intent routing, reviewed masterplan and complete-scaffold principle, but this
README does not claim identical host behavior. Claude consumes the always-present source baseline.
The Codex gate additionally performs explicit greenfield/onboarded assessment, writes the
kit-specific Dev/Research/Office draft, sets the `providers: [claude, codex]` baseline, and
requires project trust plus `/hooks` review. No Claude application or
session is required for that Codex path. Generated hook definitions contain an inline verifier for
the full hook-bundle hash; changed scripts/helpers block until a full scaffold regenerates the
definition and `/hooks` trusts it again.
The scaffold scripts themselves are plain
PowerShell/Bash under the shared `~/.claude/team-kits/` staging — deliberately ONE staging for
every provider.

---

## Install paths

| Component | Path |
|---|---|
| User entry gate (Claude Code) | `~/.claude/CLAUDE.md` |
| User entry gate (Codex CLI) | `$CODEX_HOME/AGENTS.md` (default `~/.codex`; created; `AGENTS.override.md` wins when present) |
| Team kit staging (shared) | `~/.claude/team-kits/<team>/` (agents, constitution, templates) + scaffold scripts + `model_tiers.yaml` + `gen_provider_artifacts.py` |
| Project team (per repo, created on demand) | `./.claude/agents/*.md` + `./.claude/skills/` + `./AGENTS.md` + `./CLAUDE.md` import shim + `./.claude/settings.json`; Codex adds `./.codex/config.toml`, hooks/agents and `./.agents/skills/` |
| Role skills (per repo, via scaffold) | Shared source: `./.claude/skills/<role>/`; Codex-native generated copy: `./.agents/skills/<role>/` |
| VS Code prompts folder (legacy Copilot cleanup only) | Windows: `%APPDATA%\Code\User\prompts\` <br> macOS: `~/Library/Application Support/Code/User/prompts/` <br> Linux: `~/.config/Code/User/prompts/` |

---

## Repo structure

```
harness/
├── user/                               ← user-scope (~/.claude) install sources
│   ├── claude/
│   │   ├── CLAUDE.md                    ← user entry gate (Claude Code)
│   │   ├── settings.json                ← user defaults merged into ~/.claude/settings.json
│   │   └── statusline.py                ← status line (model · context · cost · branch)
│   ├── codex/
│   │   └── AGENTS.md                    ← user entry gate ($CODEX_HOME/AGENTS.md)
│   └── merge_settings.py                ← installer helper: merge keys, preserve personal settings
├── team-kits/
│   ├── registry.yaml                    ← intent → kit routing (single source of truth)
│   ├── scaffold_team.ps1 / .sh          ← installs a kit into the current repo (backs up first)
│   ├── init_project_memory.ps1 / .sh    ← deterministically creates ./project_memory/ from kit templates (copy-if-absent)
│   ├── dev-team/
│   │   ├── agents/                      ← project-manager (session agent) + 7 specialist subagents
│   │   ├── skills/                      ← one role skill per agent (project-manager, software-architect, …)
│   │   ├── constitution/AGENTS.md       ← source → canonical ./AGENTS.md + Claude import shim
│   │   ├── hooks/ + settings/           ← deterministic enforcement hooks + .claude/settings.json (agent, model, …)
│   │   └── templates/project_memory/    ← YAML artifact templates
│   ├── research-team/
│   │   ├── agents/ + skills/            ← project-manager + 6 specialists + their role skills
│   │   ├── constitution/AGENTS.md       ← research constitution source (carries team marker)
│   │   ├── hooks/ + settings/           ← enforcement hooks + .claude/settings.json
│   │   └── templates/project_memory/    ← research artifacts + LaTeX/HTML report templates + bundled KaTeX preview
│   └── office-team/
│       ├── agents/ + skills/            ← office-manager (session agent) + 6 specialists + role skills
│       ├── constitution/AGENTS.md       ← office constitution source: PROC model, outbox-only
│       ├── hooks/ + settings/           ← incl. proc-approval gate, ledger guard, filing gate, fs tripwire
│       └── templates/                   ← office artifacts + deterministic scripts (ledger_add, euer_report, …)
├── install.ps1                          ← Windows installer (backup + confirm + overwrite)
└── install.sh                           ← macOS/Linux installer
```

---

## How it starts (two-tier flow)

1. **Global gate asks** (non-coercive): on your first build/change wish the global `CLAUDE.md`
   or Codex `AGENTS.md` asks *structured (PM) or free?*. Choose *free* and you work without
   bookkeeping.
2. **Auto-init (discovery first):** on *structured*, the default agent classifies intent, interviews
   and drafts a reviewed plan before installing. The Codex gate additionally assesses an existing
   repository read-only and seeds the correct kit artifact: Dev PRD, Research RQ, or Office business
   profile. Provider-specific limitations are stated in the parity section above.
3. **Local install:** specialist agents are copied to `./.claude/agents/`, the canonical constitution
   to `./AGENTS.md`, and hooks/settings to `./.claude/`. On the Codex path, existing managed
   destinations are inventoried and require explicit replacement consent first; Codex then also
   receives config, hooks, exact custom-agent roles and native skills. Trust the project,
   inspect/trust the generated hook definitions under `/hooks`, then start a new session so the local
   layer is discovered. The PM picks up the reviewed draft there.
4. **The main agent becomes the PM.** Claude uses `.claude/settings.json` `agent:` plus its preloaded
   skill/memory. Codex uses generated `.codex/config.toml` lead instructions/model and the native
   `.agents/skills/project-manager` (or office-manager) skill. Both keep one foreground lead; the lead
   is never generated as a spawnable specialist. On Codex, the user entry gate has already created
   and seeded the kit-specific `project_memory/` deterministically, confirmed the preset, and run the
   complete scaffold. The PM's **startup gate** validates that handover and reports an
   incomplete/inactive provider layer instead of silently degrading. It then begins the phase model,
   maintains `project_memory/`, and delegates specialist work to ephemeral subagent runs.

---

## Multi-agent role model

The workflow lives in each kit's canonical **constitution** (`AGENTS.md`; Claude imports it) and is executed by the **main agent acting
as PM** plus ephemeral specialist subagent runs. Selected Claude craft roles have role-scoped memory;
Codex project memory features are disabled for deterministic roles. The PM is the only interface to
the user, keeps current-session conversation context, maintains `project_memory/`, and delegates; specialists
return YAML. Roles below are the **`dev-team`**; the **`research-team`** mirrors the same machinery.

### Roles (dev-team)

| Role | File | Job | Talks to user |
|---|---|---|---|
| **Project Manager** | `project-manager` (foreground lead; Claude: opus + role memory; Codex: mapped lead tier + checked-in project memory) | Requirements (PRD/CR), `project_memory/` bookkeeping, delegation, merge, user acceptance | **Yes (only one)** |
| **Software Architect** | `software-architect` | System requirements, architecture, ADRs, coding guidelines, test strategy | No |
| **Product Designer** | `product-designer` | UI/UX: screens, flows, design system, accessibility (UI-bearing PRDs) — `design.yaml` | No |
| **Research Engineer** | `research-engineer` | Web-enabled investigation of libs/datasheets/APIs; cited facts — `research_notes.yaml` | No |
| **Backend Developer** | `backend-developer` | Server-side tasks, tests, commits | No |
| **Frontend Developer** | `frontend-developer` | UI tasks, tests, commits | No |
| **Quality Engineer** | `quality-engineer` | Review, tests (sole owner of test completeness), Definition of Done, merge gate | No |
| **DevOps Engineer** | `devops-engineer` | CI/CD, pipelines, environments, release | No |
| **Project Auditor** | `project-auditor` | Scheduled daily READ-ONLY review: samples requirements↔code claims, judge rubric (0.0–1.0 + pass/fail), sole writer of `review_findings.yaml`; findings become TSKs or logged skips | No |

### Roles (research-team)

Same two-tier machinery, research-flavored. Hierarchy: **Research Question (RQ) → Hypothesis (HYP) +
Experiment Design (EXP) → Tasks**; changes go through **Protocol Amendments (PA)**. The PM (lead) is again
the only customer-facing role.

| Role | File | Job |
|---|---|---|
| **Research Lead (PM)** | `project-manager` (foreground lead; Claude: opus + role memory; Codex: mapped lead tier + checked-in project memory) | RQs/PAs, `project_memory/` + **FZulG** bookkeeping, delegation, merge, user acceptance |
| **Methodologist** | `methodologist` | Hypotheses, experiment designs, MDRs, research guidelines, FZulG criteria |
| **Researcher** | `researcher` | Runs experiments, collects raw data, analysis code |
| **Data Analyst** | `data-analyst` | Statistics, effect sizes, visualization, interpretation |
| **Reviewer** | `reviewer` | Reproducibility + validity gate, peer review, merge gate |
| **Research Engineer** | `research-engineer` | Data pipelines, environments, dataset versioning |
| **Report Writer** | `report-writer` | Per-experiment scientific report in **LaTeX/PDF** (+ offline HTML preview via KaTeX) and the **BSFZ application draft** from `fzulg_documentation.yaml`, fixed templates |
| **Project Auditor** | `project-auditor` | Scheduled daily READ-ONLY review: samples claims vs evidence, judge rubric (0.0–1.0 + pass/fail), sole writer of `review_findings.yaml`; findings become tasks or logged skips |

### Roles (office-team)

Back-office automation for a small business, PROCESS-shaped: the approval unit is a **PROC**
(`process_definitions.yaml`) — approved once by the user (with a tamper-detecting `approved_hash`),
then routine runs execute autonomously within it. Inbox → verified filing → script-validated
append-only ledger → **generated** quarterly income/expense report (Zufluss/Abfluss; drafts only,
no tax/legal advice, NOTHING is ever sent — `outbox/` is the user's send tray. Claude denies
`mcp__*` by default; Codex has no exact project-local wildcard equivalent, so stronger outbound
enforcement requires external server/tool restrictions or admin policy).

| Role | File | Job |
|---|---|---|
| **Office Manager** | `office-manager` (foreground lead; Claude: opus + role memory; Codex: mapped lead tier + checked-in project memory) | Onboarding interview, business profile/masterplan, PROC lifecycle + approvals, inbox routing, report runs, git |
| **Records Clerk** | `records-clerk` | Filing plan (+ retention), verified filing log, move-only migrations |
| **Bookkeeper** | `bookkeeper` | E-invoice-first extraction, ledger entries via `scripts/ledger_add.py` (validated, append-only), master data, report commentary — **no tax advice** |
| **Product Editor** | `product-editor` | Catalog + content guidelines, article texts, supplier-query drafts (single writer for product copy) |
| **Shop Curator** | `shop-curator` | Read/audit-only SEO/GEO/content audits with sourced findings; page drafts |
| **Compliance Researcher** | `compliance-researcher` | Sourced regulation register per category × market (CE, RoHS, RED, Ökodesign …) with review dates — **no legal advice** |
| **Marketing Planner** | `marketing-planner` | Research-backed channel strategy, account inventory, calendar, post drafts |
| **Project Auditor** | `project-auditor` | Scheduled daily READ-ONLY review: samples filing/ledger/report claims for real, judge rubric, sole writer of `review_findings.yaml` |

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
bookkeeping itself. The user's idea lives as a proper **`masterplan.md`** (seeded richly at onboarding, PM-owned,
critically engaged — never just blessed) — the living north star the PRDs derive from. The project evolves through four explicit requirement types, never silent edits: a
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
- **Team preset** chosen once per project (dev/research: `solo` | `duo` | `team`; office: `core` |
  `commerce` | `full`) — **mechanical**: the scaffold installs only the preset's roles (kit
  `presets.yaml`), so another **custom kit role** is unavailable until an upgrade. Codex's upstream
  built-in roles remain technically selectable and are prohibited by team policy, not removed by
  the scaffold. Upgrading = re-run the scaffold with the larger preset + session restart.
  Escalation is user-gated only.
- **Models:** portable `lead`/`worker`/`light` tiers use canonical Claude aliases
  `opus`/`sonnet`/`haiku`; Codex maps them to Sol/Terra IDs. PM/judgment roles default to lead and
  implementers to worker, controlled via `project_config.yaml` — the scaffold stamps the shared Claude agent
  frontmatter and generates the Codex TOMLs from it; `session_status` nags on drift. Under Codex,
  re-sync only through a user-confirmed full scaffold run (which invokes the generator), request
  explicit filesystem permission escalation for read-only harness paths when needed, verify the
  TOMLs, re-review/re-trust the changed hook bundle in `/hooks`, and start a new session. Never run
  the generator alone or edit one TOML/isolated provider source. Specialist upgrades only after
  user OK; portable ladder: worker-high → worker-xhigh → lead-high → lead-xhigh/max, only when the
  selected concrete model supports that effort.
- **Reasoning effort:** each role also carries an `effort:` (`low|medium|high|xhigh|max`), set per repo via an
  **`effort_map`** in `project_config.yaml` (Claude syncs specialist frontmatter directly; Codex uses
  the same user-confirmed full-scaffold flow as `model:`). Default: **all specialists + the PM run
  `high`**. `xhigh`/`max` are used only when the concrete provider/model supports them; there is no
  blanket provider-independent Sonnet ceiling. Escalation is one combined, user-gated model+effort ladder. Deep effort is reserved for hard cases
  (architect / reviewer-QA / a dev stuck on a bug), never a baseline.

### Memory

- **`project_memory/`** = the project's facts/state (authoritative single source of truth; the PM maintains it).
- **Agent memory** (`memory: project` → `.claude/agent-memory/<role>/MEMORY.md`) is enabled only for
  selected Claude craft roles. Codex has no role-specific equivalent; generated project config sets
  `features.memories=false` and `generate_memories/use_memories=false`, so required facts/rules stay
  in checked-in `project_memory/`, `AGENTS.md`, and skills.

### Enforcement (hooks, permissions, CI)

Because instructions alone get skipped, each kit ships deterministic hook scripts and, where the
kit has a pipeline, pipeline checks. Claude registers hooks through `.claude/settings.json`. Codex
generates `.codex/hooks.json` definitions that the user must inspect/trust, uses a filesystem
permission profile for secret denial and read-only harness control files, and emits event-specific post/stop output. In current Codex,
`PreToolUse` command exit 2 plus stderr is a hard block and the payload includes `agent_id`/
`agent_type`; older Codex hosts must be upgraded rather than treated as equivalent. Codex ignores
all project-local `.codex/` layers until the repository and hooks are trusted.

- **No ad-hoc files** (`guard_no_adhoc`) — blocks writing status/summary/report files outside the allowlist
  (`project_memory/**`, `src/**`, `tests/**`, `docs/**`, configs).
- **No rogue spawns** (`guard_agent_spawn`) — hard-blocking in Claude. Codex installs exact custom
  specialist roles, instructs the lead to use only those, and makes every specialist self-validate
  the work order. Codex's built-in roles remain available upstream, and `SubagentStart` cannot veto
  the requested spawn; this one boundary is policy plus verification, not a hard spawn deny.
- **PM stays out of code** (`guard_pm_scope`) — hard-blocking in both supported providers. Current
  Codex `PreToolUse` supplies `agent_id`/`agent_type`, so the same guard distinguishes the foreground
  lead from specialists; dev/research still retain QA/pipeline as a second line of defense.
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
- **YAML-valid-at-write** (`guard_yaml_valid`) — parses every written `project_memory/*.yaml` immediately
  (parse errors + duplicate keys go straight back to the writer), so a spec role without a shell can never
  leave broken YAML behind; also enforces the `progress.yaml` contract (ONE-line `status`, `log:` present —
  a real PM regrew a 300-line status blob). The pipeline's yaml-lint stage is the merge/CI backstop.
- **Background-agent audit** (`notify_agent_events` + spawn log) — never blocks; logs
  `agent_completed`/`agent_needs_input` notifications AND `SubagentStop` completions to
  `project_memory/.audit/hook_events.jsonl`, while `guard_agent_spawn` logs every allowed spawn —
  accounting is auditable end-to-end (the Notification route alone delivered 0 of 15 completions
  in a real run).
- **Scratchpad-reference guard** (`guard_scratchpad_ref`) — blocks repo source files that reference
  ephemeral session-scratchpad paths (a real fonts.css pointed at a vanished scratchpad tool and
  the pipeline stopped being reproducible).
- **Kit-owned checks + file budget** (`scripts/kit_checks.py`, run by `scripts/quality.py`;
  dev/research kits — the office kit ships deterministic office scripts instead) — the scaffold
  OVERWRITES this file on every update (like the hooks), so kit-level check fixes reach even
  projects whose quality.py runner is a heavy fork; includes the anti-monolith **file budget**
  (max lines per source file, threshold + reasoned exemptions in `coding_guidelines.yaml`
  `file_budget:`, research fallback: `research_guidelines.yaml` — a real App.tsx reached 8,966
  lines while its ui/ library sat unused).
- **Packaging gate** (`gate_packaging_decision`, dev-team) — blocks merge while `architecture.yaml`
  `packaging.method` is still TODO, so HOW the software ships is always a conscious decision (even "none /
  library" is valid) — the deterministic guard against a critical packaging tool (e.g. Docker) being forgotten.
- **Auto-dashboard** (`auto_dashboard`) — regenerates `progress.dashboard.html` whenever `project_memory/`
  changed.
- Note on `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` in the kit settings: meanwhile officially documented;
  it can only LOWER the threshold below the default, and Opus-1M sessions reportedly ignore it
  (open issue) — treat it as best-effort; the real context hygiene is the "fresh session after each
  PRD merge" rule the PM skill enforces.
- Claude hooks resolve via `${CLAUDE_PROJECT_DIR}`/`_root.py`; generated Codex commands resolve the
  Git root or walk upward before launching a shared hook, so subdirectories and greenfield repos
  before `git init` both work.

The kit's `.claude/settings.json` sets Claude's lead/model and permissions. Codex translates the
lead/model into `.codex/config.toml` and maps secret-read denies into a native permission profile.
Claude's generic Bash allowlist and Office's wildcard `mcp__*` deny have no exact project-local Codex
equivalent; they are not misrepresented as translated policy.

### Quality pipeline (tools, not review)

Clean code is enforced by **tools that block**, not by an agent reading code. The DevOps role sets up a CI +
local pipeline at project start — **format → lint → type-check → unit + integration tests → coverage gate
(≥ threshold) → security (SAST + secret scan) → dependency audit** — and "**pipeline green**" is a hard
Definition-of-Done / merge requirement (QA verifies it; a red pipeline is an automatic FAIL). The research
kit uses the same idea as a **reproducibility pipeline** (format/lint/type + a clean re-run reproducing the
numbers + dependency audit). Any role may flag tech-debt/refactoring to the PM; the architect/methodologist
owns the proposal.

### Status line & install backup

- The installer installs the bundled **status-line script** (`~/.claude/statusline.py`) and **merges**
  global defaults into `~/.claude/settings.json` — the FULL list: statusLine, theme,
  alwaysThinkingEnabled, telemetry off,
  empty commit/PR attribution, terminal progress bar, spinner tips, cleanupPeriodDays, plus a UNION of
  permission allow/deny rules. It deliberately does NOT ship `permissions.defaultMode`
  (`bypassPermissions` would remove your veto globally — against the official warning; set it yourself
  per project if you want it), `remoteControlAtStartup` or `effortLevel`. Every existing top-level
  value wins, including a custom `theme` or `statusLine`; only missing defaults are added. Existing
  permission sub-keys also win, except that valid `permissions.allow`/`deny` lists are unioned without
  duplicates. The previous file is backed up under `~/.claude/backups/`; the merge additionally
  leaves its own `~/.claude/settings.json.bak` next to the file (belt and braces — safe to delete).
- Both the installer and the scaffold **back up** what they replace before overwriting (with a confirmation
  prompt on install).
- Codex note: the harness never writes `$CODEX_HOME/config.toml` by default (user-owned — auth,
  model, personality; a legacy `sandbox_mode` there would even override team permission profiles,
  which the installer warns about). Default consequence: the user-wide secret-read denies exist
  on the CLAUDE side only — Codex gets its secret boundary from the GENERATED per-project
  permission profile. The OPT-IN flag `-CodexGlobalSecrets` / `--codex-global-secrets` closes
  that gap: it appends a clearly marked, removable profile (`extends = ":workspace"` + the same
  secret denies as the Claude side + `~/.ssh`) and activates it only when you have no own
  `default_permissions`. Fail-closed: invalid TOML or a present legacy `sandbox_mode` aborts
  without writing (the legacy key would silently disable ALL profiles — upstream precedence).
  Honest behavior change while active: folders WITHOUT a trust decision start with the
  `:workspace` baseline instead of `:read-only` (approval prompts stay unchanged); trusted team
  projects keep their generated profile (CLI precedence; the Codex DESKTOP app currently has an
  open upstream bug applying project profiles, openai/codex#22553).

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
| **Constitution** (`./AGENTS.md`; Claude imports it through `./CLAUDE.md`) | shared law: hierarchy, phases, git, anti-sycophancy, memory rules, enforcement | the PM + every subagent |
| **Agent body** (short) | who the agent is, who it obeys, its core duty | the agent's system prompt |
| **Role skill** (`skills: [<role>]`) | *how* it works + which `project_memory/` files it reads/writes | preloaded into the agent |

Each team kit ships **one role skill per agent** (incl. the PM's `project-manager`) under
`team-kits/<kit>/skills/`. The scaffold installs the shared source into `./.claude/skills/`; Codex
also receives generated native copies under `./.agents/skills/`. Claude preloads via frontmatter;
Codex lead/specialist instructions explicitly require the matching native skill. There are no global
role skills.

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

Team kits are **versioned** (`team-kits/<kit>/VERSION`, content-hashed — `validate.py` fails if a kit changes
without a bump). The scaffold stamps `./.claude/kit_version` into each project; at session start the
`session_status` hook compares it with the staged kit and flags **KIT UPDATE AVAILABLE**. The PM then proposes
the update (scaffold_team + init_project_memory — backup first, copy-if-absent, `project_memory/` content is
never overwritten) and asks for a restart. Under Codex the approved scaffold may need explicit filesystem
permission escalation because harness/provider paths are read-only; never run the provider generator alone.
Afterward verify generated TOMLs, review/re-trust the changed bundle hash in `/hooks`, and start the new
session. Newly required fields in existing YAMLs are requested by the gates.

---

## Uninstall

Delete the folders manually:
- `~/.claude/team-kits/`, `~/.claude/CLAUDE.md`, `~/.claude/statusline.py`
- `$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`)
- In each project: generated `./.claude/`, `./.codex/`, role folders under `./.agents/skills/`,
  `./AGENTS.md`, and the `./CLAUDE.md` import shim (restore backups first when preserving prior files)

---

## License

MIT
