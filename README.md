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
marketing planning, business-specific data tools/dashboards — drafts only, no tax/legal advice). The
registry maps your intent to the right one.

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
(`team-kits/model_tiers.yaml`: three rungs per provider, DEC-0076; kit sources carry only the
neutral aliases `lead`/`worker` and the top-rung pin `fable`, resolved per provider at install
time). A namespaced `codex:` frontmatter overlay merges
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
| One-time kit-update bootstrap (BUG-0059) | `~/agents-and-skills/update_kit.py` — deliberately outside `~/.claude`, so a project whose kit predates `update-kit` can still start it |
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
│   │   └── templates/project_memory/    ← the typed state skeleton (empty item directories) + reference files
│   ├── research-team/
│   │   ├── agents/ + skills/            ← project-manager + 6 specialists + their role skills
│   │   ├── constitution/AGENTS.md       ← research constitution source (carries team marker)
│   │   ├── hooks/ + settings/           ← enforcement hooks + .claude/settings.json
│   │   └── templates/project_memory/    ← state skeleton (incl. research/, hypotheses/, experiments/) + LaTeX/HTML report templates + bundled KaTeX preview
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
   and drafts a reviewed plan before installing. It then seeds the frozen `product/masterplan.md`, ONE
   DRAFT root item (dev `PR`, research `RQ`; the office kit gets its business profile instead) and a
   filled `project_config.yaml` — including the confirmed `preset:`, without which every project silently
   starts as `solo` — and regenerates `generated/index.yaml` over the result. The Codex gate additionally
   assesses an existing repository read-only.
   Provider-specific limitations are stated in the parity section above.
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
   decides WHAT gets captured into `project_memory/` (the state kernel performs every write), and
   delegates specialist work to ephemeral subagent runs.

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
| **Project Manager** | `project-manager` (foreground lead; Claude: opus + role memory; Codex: mapped lead tier + checked-in project memory) | Requirements (`PR`/`FR`/`CR`/`BUG`), the masterplan, delegation, merge, user acceptance | **Yes (only one)** |
| **Software Architect** | `software-architect` | System requirements (`SR`), architecture diagrams (`ARC`), decision items, test strategy | No |
| **Product Designer** | `product-designer` | UI/UX: screens, flows, design system, accessibility (UI-bearing `PR`s) — wireframes (`WFR`) + frozen design revisions (`DSN`) | No |
| **Research Engineer** | `research-engineer` | Web-enabled investigation of libs/datasheets/APIs; cited facts as evidence items | No |
| **Backend Developer** | `backend-developer` | Server-side tasks, tests, commits | No |
| **Frontend Developer** | `frontend-developer` | UI tasks, tests, commits | No |
| **Quality Engineer** | `quality-engineer` | Review, tests (sole owner of test completeness), Definition of Done, merge gate | No |
| **DevOps Engineer** | `devops-engineer` | CI/CD, pipelines, environments, release | No |
| **Project Auditor** | `project-auditor` | Weekly / event-triggered READ-ONLY review: samples requirement↔code claims, judge rubric (0.0–1.0 + pass/fail), records evidence (`kind: audit`); every finding becomes a `TSK`/`BUG`/`CR` or a decision item saying why not | No |

### Roles (research-team)

Same two-tier machinery, research-flavored. Hierarchy: **Research Question (`RQ`) → Hypothesis (`HYP`) +
Experiment (`EXP`) → Tasks (`TSK`)**; a change to an approved `RQ` revision is a **`CR`** (which replaced
V1's Protocol Amendment). The PM (lead) is again the only customer-facing role.

| Role | File | Job |
|---|---|---|
| **Research Lead (PM)** | `project-manager` (foreground lead; Claude: opus + role memory; Codex: mapped lead tier + checked-in project memory) | `RQ`s/`CR`s, the masterplan + **FZulG** bookkeeping, delegation, merge, user acceptance |
| **Methodologist** | `methodologist` | Hypotheses (`HYP`), experiment designs (`EXP`), MDRs, research guidelines, FZulG criteria |
| **Researcher** | `researcher` | Runs experiments, collects raw data, analysis code |
| **Data Analyst** | `data-analyst` | Statistics, effect sizes, visualization, interpretation |
| **Reviewer** | `reviewer` | Reproducibility + validity gate, peer review, merge gate |
| **Research Engineer** | `research-engineer` | Data pipelines, environments, dataset versioning |
| **Report Writer** | `report-writer` | Per-experiment scientific report in **LaTeX/PDF** (+ offline HTML preview via KaTeX) and the **BSFZ application draft** from `fzulg_documentation.yaml`, fixed templates |
| **Project Auditor** | `project-auditor` | Weekly / event-triggered READ-ONLY review: samples claims vs evidence, judge rubric (0.0–1.0 + pass/fail), records evidence (`kind: audit`); every finding becomes a `TSK`/`BUG`/`CR` or a decision item saying why not |

### Roles (office-team)

Back-office automation for a small business, PROCESS-shaped: the approval unit is a **`PROC`**
(one file, `procedures/active/PROC-nnnn.yaml`) — approved once by the user (with a tamper-detecting
`approved_hash` over its steps AND roles), then routine runs execute autonomously within it. Inbox →
verified filing (the archive tree IS the record; there is no filing log to write) → script-validated
append-only ledger → **generated** quarterly income/expense report (Zufluss/Abfluss; drafts only,
no tax/legal advice, NOTHING is ever sent — `outbox/` is the user's send tray. Claude denies
`mcp__*` by default; Codex has no exact project-local wildcard equivalent, so stronger outbound
enforcement requires external server/tool restrictions or admin policy).

| Role | File | Job |
|---|---|---|
| **Office Manager** | `office-manager` (foreground lead; Claude: opus + role memory; Codex: mapped lead tier + checked-in project memory) | Onboarding interview, business profile/masterplan, `PROC` lifecycle + approvals, inbox routing, report runs, git |
| **Records Clerk** | `records-clerk` | Filing plan (+ retention) — the single machine-readable filing truth, move-only migrations |
| **Bookkeeper** | `bookkeeper` | E-invoice-first extraction, ledger entries via `scripts/ledger_add.py` (validated; names the SKR03/SKR04 account once `chart_of_accounts.yaml` is active), master data, the docking point for an external invoice application (`scripts/invoice_intake.py`: norm subset, reconciling triple, number-range continuity, refused with the figures — contract in `docs/office/invoice-app-docking-point.md`), report commentary — **no tax advice** |
| **Product Editor** | `product-editor` | Catalog + content guidelines, article texts, supplier-query drafts (single writer for product copy) |
| **Shop Curator** | `shop-curator` | Read/audit-only SEO/GEO/content audits with sourced findings; page drafts |
| **Compliance Researcher** | `compliance-researcher` | Sourced regulation register per category × market (CE, RoHS, RED, Ökodesign …) with review dates — **no legal advice** |
| **Marketing Planner** | `marketing-planner` | Research-backed channel strategy, account inventory, calendar, post drafts |
| **Project Auditor** | `project-auditor` | Weekly / event-triggered READ-ONLY review: samples filing/ledger/report claims for real, judge rubric, records evidence (`kind: audit`) |

### Phase model

`0 READ → 0.5 ASSESSMENT (existing repos only) → 1 PM_DISCOVERY → 2 PM_PROPOSAL →
3 USER_APPROVAL → 4 SYSTEM_PLANNING → 5 IMPLEMENTATION → 6 REVIEW → 7 TEST → 8 QA →
9 INTERNAL_ACCEPTANCE + MERGE → 10 USER_ACCEPTANCE`

- **Two-level acceptance:** PM/QA accept internally per branch/task; the **user only accepts per `PR`**
  (on `main`, after the internal merge).
- **ASSESSMENT** runs only for existing repos: PM + Architect + QA produce a **gap report** (missing
  tests, guideline gaps, refactoring candidates, tech debt, security) — the user chooses what becomes
  a `PR`/`CR`.

### State (`project_memory/`)

**One file is one item** — the repo's `project_memory/` is the single source of truth, and a status is
written exactly once, in the item that has it. Each item type has its own directory
(`<area>/active/<TYPE>-nnnn.yaml`); which type lives where is defined once in code
(`team-kits/kernel/backlog_types.py`, `ACTIVE_DIRS`), together with the per-type field contract
(`REQUIRED_FIELDS`) and status automaton (`AUTOMATA`) — never as a second list in prose. The typed
directory skeleton is created by the deterministic `init_project_memory` script (copy-if-absent from the
kit templates).

The **state kernel is the only writer.** Roles decide WHAT is captured; the kernel allocates the id,
stamps the timestamps, refuses a status the automaton does not allow, and writes the file atomically
under a lock. `gate_write_scope` closes the tool paths to the state directory (an agent gets only its
task's `staging/<task-id>/`), so "two roles overwrote each other's YAML" is structurally gone rather than
a rule someone follows.

**The kernel has exactly ONE entry point, and it is installed:** `python scripts/harness.py <command>`,
run from the project root. The scaffold writes `scripts/harness.py` into every project as a kit-owned
file (overwritten on every run, like `scripts/kit_checks.py`), the same three tokens are what you type in
bash and in PowerShell alike, and it resolves the state directory itself. That last part is what lets
`gate_write_scope` go on refusing every write-capable pipeline that NAMES the state directory — so
`--root` never belongs on this command line, and the entry point refuses it too, off its own parser.
Measured against a scaffolded project as real hook processes: the `evidence` line below passes all eight
`PreToolUse` gates under both shell tools, `python -B .claude/kernel/cli.py doctor` is refused for naming
the enforcement layer, and `python scripts/harness.py --root project_memory` for naming the state
directory (as do `--roo`, `--ro`, `--r` and the `=` form: argparse takes any unambiguous prefix, and the
entry point asks the shipped parser rather than matching text).

**Its command surface, and what is still missing from it.** `python scripts/harness.py --help` is the
authority: today `doctor`, `validate`, `generate-index`, `verify-invariants`,
`generate-session-brief`, `capture`,
`request-approval`, `create-task`, `dispatch`, `ladder`, `submit-result`, `evidence`, `transition`, `update`,
`archive`, `check-scopes`, `sweep-leases`, `sweep-requests`, `checkpoint`, `checkpoint-status`, `set-preset`, `update-kit`, `add-filing-rule`, `apply-proposal`, `revise-document`,
`freeze-architecture`, `freeze-wireframe`, `freeze-design`, `freeze-report`,
`migrate`, `migrate-holes`, `sweep-pointers`, `report-gap`, `pin-kit`, `unpin-kit`, `rollback-kit`. Of the twelve
spec II.4 asks for, one is absent under that name: `approve` is SPLIT —
`request-approval <kind> <ITEM-ID>` opens the kernel-generated question (phase 1), and the USER mints it
by ANSWERING, which is the whole of why the approval is provable; no command mints, and the mint also
walks the status transition it commits. Kit DOCUMENTS under `project_memory/` (the master data,
the filing plan's neighbours, `project_config.yaml` beyond the one `set-preset` field) gained a
route in TSK-0092: a role stages the document as it should stand, and `apply-proposal` writes it
after a user-minted approval, refusing any removal, change or lost comment. Correcting or removing
what such a document already says has its OWN route since TSK-0106, `revise-document` on its own
approval kind, whose question shows every replaced and every deleted spot with its old and its new
wording. What has no writer at
all either way: the PROSE documents — `product/masterplan.md` and the shipped READMEs — stay
writerless on purpose, so the global entry file's statement about the masterplan stays true.
`set-preset` still owns exactly one field, `project.preset`, on a user-minted approval, because
the roles a project may spawn otherwise had no route after the install at all (BUG-0041). Those are
infrastructure defects to report, not a licence to write state by hand, and the three constitutions
say the same in their §0. The promotion path (II.6a) DOES have one now: an `ARC`/`WFR`/`DSN` is
frozen by `freeze-architecture`/`freeze-wireframe`/`freeze-design`, each taking the operation's own
parameters as a JSON object on stdin. Until 2026-07-31 it did not, and `gate_packaging_decision`
— which refuses every push and merge until some active `ARC` states a `packaging.method` — was
therefore a block with no exit in every scaffolded project.

**`sweep-pointers` is the MECHANICAL half of the comment duty** (`FR-0007`, and the rule itself in `DEC-0008`/`SR-0008`). The duty asks a comment to carry its WHY as a pointer and a claim about a PROPERTY to become a test the comment NAMES; both halves rot the same way, and a pointer that resolves at nothing is worse than none because it reads as covered. The command asks git for the project's own files, reads every backtick citation in them, and reports the ones that resolve at nothing: a `<path>::<test>` the tree does not define, an item id the store holds neither active nor archived. It is a REPORT, not a gate -- it exits 1 and nothing waits on it -- because the two things it cannot tell apart are an ILLUSTRATION and a POINTER (a document teaching by example, a log about another project's store), and because the half that matters most is not mechanical at all: whether a property claim named a test AT ALL is read by nobody. What it reads and what it deliberately does not is `kernel.report.pointer_sweep`; the three constitutions state the duty in their section on the duties no gate carries.

**`migrate` is the V1 import (II.10), and the lead runs it itself** — the alternative was a tool
beside the harness, which would have been the one write route into canonical state that no gate
sees. It has two halves. `--dry-run` reads and writes nothing, and reports three things per
finding: what it found, what it would become, and what it CANNOT do. `--plan <digest>` executes,
and refuses unless it re-derives the digest the dry run printed from the state AND the flags —
so the run that executes is the run somebody read. What it translates is a property, not a list of
file names: a mapping that identifies itself with a `<TYP>-nnnn` id — as its key in an enclosing
mapping **or** in its own `id` field, wherever in the document it lies — and carries a `status`.

**What follows from that id is four answers, and only two of them stop the run.** A type spec
II.10's own table (`backlog_types.map_v1_status`) knows, with a status it knows, is imported. A
type it HAS rows for carrying a status it does not know is a harness gap and BLOCKS — never
guessed. A type no contract in this kernel knows at all is not a backlog record: it is reported
as `not_an_item`, imported by nothing and a blocker for nothing, which is what keeps a project's
own QA reports or catalogues from refusing its whole migration. And a record whose V2 required
fields have no source anywhere is archived with that gap as its written reason instead of
refusing the run (DEC-0009). A field carries over only when both contracts spell it the same;
for the rest there are two different answers. Where the kit's own V1 template documents a field
that carries the same thing, the dry run prints the `--map` flag as a SUGGESTION with its reason
and the run stays unexecutable until a human types it back (SR-0007) — a suggestion is not an
answer. Where nothing can propose one, that is the DEC-0009 archive above. There is exactly one
exception and it is not a guess about the record: a required field whose subject is where the
record CAME FROM (`migrate.PROVENANCE_FIELDS`, today only `source`) is filled by the importer,
which is the only writer that knows the answer — V1 recorded it in no field, so leaving it to
`--map` would have meant naming a V1 field that does not exist.

**A record that is FINISHED in V1 goes straight to `archive/<TYPE>/<year>/`** (SR-0004) at its
mapped status, and the per-item field contract does not apply to it (DEC-0004) — a V1 task is
missing ten of eleven required fields, and a 2025 task will not be executed again. Whether a record
is finished is a fact about the V1 vocabulary and is read off spec II.10's own mapping table
(`archive_candidate`), not off the V2 automaton: V1 `TSK DONE` maps to `DONE`, which is no terminal
of the V2 task automaton — V2 keeps `VALIDATED` for "QA confirmed", a confirmation V1 never
collected and which the import does not invent. Three bolts, and they are not all of one kind: the
first two are refusals `state.capture_migrated_archive` raises — the exemption is reachable through
that method only, `capture` is unchanged; and the status has to be one the type can REACH without a
user approval, which is a walk over its automaton rather than the approval edges read as a set (a
status three steps past an approval stands behind it just as much). A V1 `PRD ACCEPTED` is
therefore NOT archived, and neither is any other V1 value whose V2 status lies behind such an edge:
each is imported at its initial status, because minting one of those without an APR is what II.10
forbids. What that costs today is measured, not asserted here — `tools/test_state.py` walks the
shipped automata and `tools/test_migrate.py` imports such a record. The third bolt is STRUCTURAL
rather than a check: such an item is never written under `active/`, and this kernel has no
operation that moves an item out of the archive, so there is nothing to refuse. The archive YEAR
comes from the record's own newest date; a record that carries no date gets no year guessed for it
— the run blocks and asks for `--archive-year`.

**There is a SECOND archive door and it answers a different question** (DEC-0009): a record that is
still whatever V1 said it was, but whose V2 required fields no `--map` and no suggestion can fill,
is written into the same `archive/<TYPE>/<year>/` at its type's INITIAL status, carrying the
sentence that says which fields had no source (`legacy_fields.unresolved`). It is an outcome and
not an obstacle — the run proceeds — and the dry run lists every record it would take, by name,
before anything is written. What that costs is named there too: nothing brings an item back out of
the archive, and on the two dev field copies the records that meet this most often are the ROOT
requirements, so a migrated project can end up holding no active `PR` at all. Both halves of the
command say so, and they say what it costs: the setup-phase predicate the kits' gates ask
(`hooks/_root.py`) reads whether an active root item FILE exists, so the gate in front of `git
merge` and `git push` stops applying until the project holds one again.

**A V1 parent chain migrates**, which is the normal shape of every V1 store: the plan asks the
writer's verdict against the state the run WILL have reached, orders the writes so a parent exists
before its child, refuses a cycle, and rewrites each binding to the id the parent actually got
(V2 allocates ids, so the V1 number is not the V2 one). A binding whose target is in neither the
plan nor the state is still refused, by the same check as before.

Measured in the suite (`tools/test_migrate.py`) against the office kit's own V1 `project_memory`
templates restored out of this repository's history — the same schemas, no hand-written fixture
anywhere. A separate reading was taken by hand on a real office project outside this repository
and is NOT reproducible from it: the kit version that run was on cannot be re-derived here, so the
numbers it produced are not quoted. **What it does not do,** and this is the half worth reading
twice: it mints no approval. Every imported item carries `imported_from_v1: true` — a mark saying
where its content came from, which nothing in this harness reads as a permission (DEC-0021) —
and `approval_ref: null`, so the import opens no gate that needs an approval — `gate_proc_approved`
still refuses a spawn afterwards, measured, until the user approves each procedure. That is the
property, and the STATUS is not part of it: where a record lands and at which status is per record
— a record V1 had already finished arrives at its MAPPED status, which is what the first archive
door above is for — and the dry run states it for every record before anything is written. It
rewrites no
document a gate reads (a V1 `filing_plan.yaml` in the old `tree:` schema stays a wall).

**It does MOVE one class of file, and exactly one** (SR-0005): a V1 store whose every backlog
record became an item is moved to `project_memory/legacy/`, with its pre-move content hash in the
run's `DEC` receipt — leaving it beside the items that came out of it would be the same thing
twice in one project, and `validate` reports exactly that as an error until it is cleared. A store
that still holds one untranslated backlog record stays where it is, and so does a WALL — a
document a registered, refusal-capable hook reads — because moving one would leave its gate reading
an absent file. `legacy/` is a kernel-written area, so a later run does not read it as a V1 source
and no tool write reaches it. Everything else with no V2 counterpart — a filing log of hundreds of
entries, an audit history — stays exactly where it is and is inventoried with its content hash in
the same receipt. Nothing in this harness blocks a later write to those retained files; spec II.10
asks for such a guard and there is none — as it asks for a separate user consent and a manifest for
the move to `legacy/`, and gets neither (recorded in the spec's own II.10 addendum (e)). **No approval kind covers a migration** and none is bent into covering it: the
item-bound kinds (`approvals.item_derived_kinds()`) hash an item's own fields and a migration has
no item yet, `analysis` wants an analysis question and a cadence, `routine` is a licence for
something recurring, and the line kind is about publishing a commit. The digest proves the state did not move between
the reading and the writing — not that a user consented.

`capture` takes the item's fields as a JSON object on **stdin**, and both halves of that are forced
rather than chosen. Stdin, because an item carries lists of mappings no flag surface expresses and the
obvious alternative — `--from project_memory/staging/…` — is refused by `gate_write_scope` for naming
the state directory (measured, rc 2). JSON and not YAML, although the store is YAML, because the body
decides the item's HASHED fields and YAML 1.1 retypes `no` to false and `12:30` to 750 on the way in —
a value that means one thing to the role and another to the approval hash is the invalidation class this
kernel exists to end.

The user's idea lives as a proper **`product/masterplan.md`** (seeded richly at onboarding, PM-owned,
critically engaged — never just blessed): frozen discovery prose and explicitly **not** a status source.
The project then evolves through explicit item types, never silent edits: a user-story **`FR`** for new
capability, triaged into a **`PR`** (the delivered unit, `RQ` in the research kit), a **`CR`** for a change
to an approved `PR` revision, and a **`BUG`** for a defect against approved behaviour (with a mandatory
regression test). Below a `PR` sit `SR` contracts and `TSK` work orders; approvals (`APR`), decisions,
invariants (`INV`) and evidence are items in exactly the same sense. Architecture diagrams (`ARC`) and
wireframes (`WFR`) are **draw.io `.drawio.svg`** files with a companion YAML, frozen on approval.

What is closed **leaves**: a terminal item is archived to `archive/<TYPE>/<year>/`, so the active
directories ARE the current context. History lives in git, not as a changelog inside an active file.
There is no `progress.yaml`, no narrative status log, no committed dashboard history and no ad-hoc
status/summary/report file (`guard_no_adhoc` blocks the last one).

Everything that summarises the items is **regenerated** from them and lives under `generated/`:
`index.yaml`, the `session_brief.yaml` the session-start hook points the lead at, and the user-facing
`dashboard.html`. `generated/**`, `.claude/kit_state.json` and the kernel lock are deliberately **not
committed** — all regenerable, and generated artifacts never produce merge conflicts. The dashboard is
rendered by `scripts/generate_dashboard.py` from `generated/index.yaml` plus the active items into
`project_memory/generated/dashboard.html`: views over the item types, each row expanding into that item's
detail on demand. It keeps no history and computes no since-last-run diff — the previous state is a git
commit away. Running it needs PyYAML (`pip install pyyaml`); the generated HTML is dependency-free and
opens by double-click.

### Git, presets & models

- **Branch per work item** (`<typ>/<ITEM-ID>-<slug>`, prefixes `pr/ cr/ bug/` — e.g.
  `pr/PR-0012-checkout`), merge after internal QA, **push only on user confirmation**, no force-push,
  no work on a dirty tree.
- **Team preset** chosen at init per project (dev/research: `solo` | `duo` | `team`; office: `core` |
  `commerce` | `full`) — **mechanical**: the scaffold installs only the preset's roles (kit
  `presets.yaml`), so another **custom kit role** is unavailable until the preset changes. Codex's
  upstream built-in roles remain technically selectable and are prohibited by team policy, not
  removed by the scaffold. Changing it later is the LEAD's step and stays inside the chat:
  `request-approval preset --preset <name>` asks the user (the question names every role added and
  removed), `set-preset <name>` records it and installs those roles, and the lead then asks for a
  session restart. Growing the TEAM is user-gated only — the MODEL rung is not, and has not been
  since DEC-0077: the dispatcher derives it (**The ladder is the kernel's**, below).
- **Models:** three rungs per provider (`team-kits/model_tiers.yaml`, DEC-0076) -- `fable` /
  `opus` / `sonnet` on Claude, `gpt-6-astra` / `gpt-5.6-sol` / `gpt-5.6-terra` on Codex; kit
  sources pin the aliases `lead`/`worker` or the top rung `fable`. Judgment roles and the kit
  LEADS pin opus, implementers pin worker and the ladder's `build` class starts them on opus anyway
  (DEC-0095: the top rung is bought for the named architecture step and for the escalation after a
  failed run, never as a standing tier); the specialist map is `project_config.yaml` — the scaffold stamps the
  shared Claude agent frontmatter and generates the Codex TOMLs from it; `session_status` nags on
  drift. Under Codex, re-sync only through a user-confirmed full scaffold run (which invokes the
  generator), request explicit filesystem permission escalation for read-only harness paths when
  needed, verify the TOMLs, re-review/re-trust the changed hook bundle in `/hooks`, and start a new
  session. Never run the generator alone or edit one TOML/isolated provider source.
- **The ladder is the kernel's (DEC-0077, DEC-0078):** every kit declares its own in
  `team-kits/<kit>/ladder.yaml` -- rungs, top rung, effort pair, role classes, named exceptions --
  and `kernel.dispatch.ladder_for_order` derives at every `dispatch` the RUNG (the role's pin, its
  class, the order's failed runs -- DEC-0034 rules 1-5, endpoints per kit DEC-0047) and the EFFORT
  (the goal's `class`) -- and on a failed run the EFFORT climbs before the RUNG, by the two
  thresholds each declaration carries (DEC-0096) -- writes both on the lease, the header and the task item, derives again at
  the spawn and refuses a spawn that names no `model` for a climbed order or the wrong one
  (`python scripts/harness.py ladder <TSK-ID>` shows the answer). A kit without a declaration is
  refused at dispatch; the kernel carries no default.
- **Reasoning effort:** each role also carries an `effort:` (`low|medium|high|xhigh|max`), set per repo via an
  **`effort_map`** in `project_config.yaml` (Claude syncs specialist frontmatter directly; Codex uses
  the same user-confirmed full-scaffold flow as `model:`). The ladder DERIVES an effort per order
  (dev/research `high`, `xhigh` for a large goal; office `medium` / `high`) and shows it; what the
  child RUNS on is the installed `effort:`, because the platform has no per-spawn effort
  parameter (measured 2026-09-05).

### Memory

- **`project_memory/`** = the project's facts/state (authoritative single source of truth; the PM decides
  its content, the state kernel performs every write).
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

- **No ad-hoc files** (`guard_no_adhoc`) — blocks the status/summary/report/result dumps agents keep
  inventing; a finding belongs in a typed item (evidence, decision, `BUG`, `CR`) and work still in flight
  in the task's own `staging/<task-id>/`.
- **The state directory is kernel-only** (`gate_write_scope`) — refuses ANY tool write into
  `project_memory/**` (the exception is a bound specialist's own `staging/<task-id>/`), a bound
  specialist writing outside its task's `allowed_scope`, an unbound subagent writing anything, and from a
  shell every write-capable command line naming the state directory or the enforcement layer. What a
  command line does not reveal it cannot refuse: a script the agent wrote and then ran is bounded by the
  project's permission posture, not by this gate.
- **No spawn without a work order** (`gate_dispatch`) — no subagent starts without a valid dispatch header
  and a live kernel lease: missing task, wrong role, stale root revision, unproven or invalidated
  approval, open dependency, spent lease, or a UI task without the `design_ref` its confirmed design
  requires. It binds the child's `agent_id` to its task and returns the task to `READY` when the platform
  reports the spawn failed.
- **Approvals are minted, not claimed** (`gate_approval`) — a question marked as an approval request must
  match the kernel-generated approval question exactly (text, header, every option) or it is blocked;
  only the verbatim approval label mints the approval.
- **Result contract at stop** (`gate_subagent_output`) — a specialist that ends in prose instead of its
  declared output envelope is blocked; work built on a missing result is work built on air.
- **No rogue spawns** (`guard_agent_spawn`) — hard-blocking in Claude. Codex installs exact custom
  specialist roles, instructs the lead to use only those, and makes every specialist self-validate
  the work order. Codex's built-in roles remain available upstream, and `SubagentStart` cannot veto
  the requested spawn; this one boundary is policy plus verification, not a hard spawn deny.
- **PM stays out of code** (`guard_pm_scope`) — hard-blocking in both supported providers. Current
  Codex `PreToolUse` supplies `agent_id`/`agent_type`, so the same guard distinguishes the foreground
  lead from specialists; dev/research still retain QA/pipeline as a second line of defense.
- **Guidelines before code** (`guard_guidelines`) — blocks a code-writer from writing a language before its
  `coding_guidelines.yaml` `languages:` block exists. CONDITIONAL: V2 ships no template for that file, so
  in a project that does not keep one the hook exits 0 and the rule binds as policy only.
- **Real pipeline at merge** (`gate_pipeline`) — runs `scripts/quality.py` (lint/types/tests+coverage,
  secret/dep scan) and blocks on a red or missing pipeline; a self-reported "pass" does not suffice.
- **Commit / merge gate** (`gate_git`) — always blocks force-push. It also blocks a merge or push whose QA
  **Evidence** is missing, INCOMPLETE or failing: the newest `test`/`review`/`acceptance` Evidence covering
  an item is that kind's current verdict, so a re-run supersedes an older one and a `fail` recorded
  afterwards closes the gate again (`kind: audit` judges the project and never opens a merge). A merge that
  NAMES a root item needs a current non-fail verdict of EVERY one of those kinds — each answers a question
  the others do not, and the refusal says which one is unanswered. Judged for every root id the
  command names, and for the branch's item when the command names none; a merge that names nothing gets
  the weaker question only — it is refused while any item is currently failing, and completeness is not
  asked there, because with no item to bind to it would refuse every push while any item is mid-flight.
  It also refuses a merge for an item still in `DRAFT` or
  already `REJECTED`/`SUPERSEDED`, and it does not apply at all before the project's first PR/RQ exists.
  That evidence has exactly one producer, `python scripts/harness.py evidence`, and it is installed —
  run from the project root, never with `--root`. Measured end to end in a scaffolded project outside
  this repo: `git merge feat/PR-0001-x` refused with "no QA Evidence for PR-0001"; with one `test` pass
  recorded it refused with "QA has judged PR-0001 only in part … no acceptance/review Evidence covers it
  at all"; with `review` added, the same refusal naming `acceptance` alone; each
  `python scripts/harness.py evidence --kind <test|review|acceptance> --result pass --related PR-0001
  --summary "…" --artifact-ref staging/TSK-0001/run.log --run-command "<the command line you ran>"
  --run-scope <full|selection>` passed all eight `PreToolUse` gates as real hook
  processes and then ran; with all three recorded the same merge was allowed. `gate_write_scope`
  still decides by READING the command line, and a text check is enforcement rather than arithmetic, so
  a spelling it does not recognise is a hole in that gate to report — never the way in.
  Plus `gate_push_token`: a `git push` needs a user approval bound to
  remote + branch + HEAD, which a new commit invalidates. Plus `gate_shell_hygiene`: destructive `docker`
  on a foreign compose project or any `prune`, and merge/rebase/pull/`reset --hard`/branch-switch on a
  dirty tree.
- **Per-area test gate** (`gate_test_coverage`, dev-team) — blocks merge while any source area (e.g.
  `src/`, `frontend/src/`) has no tests, so a strong area can't mask an untested one. The default areas
  always count; EXTRA areas come from `testing_guidelines.yaml` `coverage_areas:`, an optional file V2
  ships no template for — without it a source package outside the defaults is not scanned at all.
- **Completeness gate** (`gate_memory_complete`) — blocks merge while the fail-closed state validator
  reports an error, `product/masterplan.md` is still the raw template, or `project_config.yaml` has no
  project name / only TODO stacks.
- **YAML-valid-at-write** (`guard_yaml_valid`) — parses every written `project_memory/*.yaml` immediately
  (parse errors + duplicate keys go straight back to the writer), so a spec role without a shell can never
  leave broken YAML behind. Well-formedness only: what an item must CONTAIN is its type's field contract,
  which the state validator answers. The pipeline's yaml-lint stage is the merge/CI backstop.
- **Memory holds craft, never project status** (`guard_memory_budget`) — blocks an oversized role-memory
  index or topic, a 21st topic for one role, and any project item id written into a role's memory.
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
  (max lines per source file — a real App.tsx reached 8,966 lines while its ui/ library sat unused).
  Its threshold and reasoned exemptions used to live in the guidelines monolith; V2 dissolved that file
  and has not rehomed the config knobs yet, so the budget currently runs on its defaults and the checks
  say so instead of pointing at a file that no longer exists.
- **Packaging gate** (`gate_packaging_decision`, dev-team) — blocks merge while no active architecture item
  states a resolved `packaging.method`, so HOW the software ships is always a conscious decision (even "none /
  library" is valid) — the deterministic guard against a critical packaging tool (e.g. Docker) being forgotten.
- **Which bundle this checkout trusts** (`kit_trust_state`) — records the hook bundle a project has
  actually run in `.claude/kit_state.json` (`restart_required` → `active`, `hooks_trust_required` when the
  bundle changed). It is per-machine runtime state and deliberately not committed, so a clone can never
  inherit "trusted" before a single hook ran in it.
- Note on `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` in the kit settings: meanwhile officially documented;
  it can only LOWER the threshold below the default, and Opus-1M sessions reportedly ignore it
  (open issue) — treat it as best-effort; the real context hygiene is the "fresh session after each
  merged requirement" rule the PM skill enforces.
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
| **Role skill** (`skills: [<role>]`) | *how* it works + which `project_memory/` files it reads/writes | REGISTERED for the agent, not injected -- the agent file names the route (`/<role>`, Codex `.agents/skills/<role>/SKILL.md`); measured 2026-08-02 for a role bound as the session agent, unmeasured for the subagent spawn (`tools/provider_observations.json`) |

Each team kit ships **one role skill per agent** (incl. the PM's `project-manager`) under
`team-kits/<kit>/skills/`. The scaffold installs the shared source into `./.claude/skills/`; Codex
also receives generated native copies under `./.agents/skills/`. Claude preloads via frontmatter;
Codex lead/specialist instructions explicitly require the matching native skill. There are no global
role skills.

**Coverage guarantee:** every item type has a CONTENT owner named in the constitution and its role skill,
so no part of the state is left unmaintained — while the writing itself belongs to the kernel alone. What
an item must contain is not repeated in any skill: it is the type's field contract in
`kernel/backlog_types.py`, which the fail-closed state validator checks. The `derives_from` chain runs
**`PR` → `SR` → `TSK`** (research: **`RQ` → `HYP`/`EXP` → `TSK`**), and each item's status moves only
along its own automaton.

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
`session_status` hook compares it with the staged kit and flags **KIT UPDATE AVAILABLE**. The PM then asks
the user with `request-approval kit_update`, and on their answer runs `update-kit` — the kernel starts the
kit's own installer (backup first, copy-if-absent, `project_memory/` content is never overwritten; the update
adds missing typed directories, it never touches an existing item), refuses a downgrade, and stops the session
so the new registration binds at the next start. **You type no shell commands for this.**

**Holding a project at the release it runs.** A file `./.claude/kit_pin` naming a release refuses
every door into the enforcement layer — the update command, the installer run by hand, and a
rollback — while re-installing that same release stays allowed, so a half-finished install can
still be repaired. `python scripts/harness.py pin-kit` prints the two lines to put in that file,
filled in with the release this project runs; `python scripts/harness.py unpin-kit` prints the pin
it carries and the file to delete.

**Going back.** The installer snapshots what it replaces into `./.claude/backups/<stamp>/` and can
replay exactly the paths that snapshot recorded (`scaffold_team.sh --rollback` /
`scaffold_team.ps1 -Rollback`); `python scripts/harness.py rollback-kit` names the snapshot and
prints that line.

**All three print; none of them writes.** Creating and deleting the pin file is yours alone — a pin
an agent could lift would not be holding anything, and a rollback replaces the enforcement layer
just as an update does.

**A project installed BEFORE that command existed (kits up to `2026.08.14-9`) cannot reach it** — its own
kernel has no `update-kit`, and its own write-scope gate refuses the installer to anything inside the session.
For that ONE lift the installer places a bootstrap outside the protected paths,
`~/agents-and-skills/update_kit.py`, and a user-global SessionStart hook tells that project's PM about it; the
PM asks you in the chat first and then runs it. It refuses to act in any project that already carries
`update-kit`, because there the route that records your approval exists. If you ever want to run it yourself:
`python "~/agents-and-skills/update_kit.py"` from the project folder, then restart the session. `kit_trust_state` records in the uncommitted `.claude/kit_state.json` which hook bundle this
checkout has actually run, so a changed bundle shows up as `hooks_trust_required` rather than being assumed
active. Under Codex the approved scaffold may need explicit filesystem
permission escalation because harness/provider paths are read-only; never run the provider generator alone.
Afterward verify generated TOMLs, review/re-trust the changed bundle hash in `/hooks`, and start the new
session. A field a newer kit version requires is reported per item by the state validator, which the merge
gate relays.

---

## Uninstall

Delete the folders manually:
- `~/.claude/team-kits/`, `~/.claude/CLAUDE.md`, `~/.claude/statusline.py`, `~/.claude/hooks/`
- `~/agents-and-skills/` (the one-time kit-update bootstrap)
- `$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`)
- In each project: generated `./.claude/`, `./.codex/`, role folders under `./.agents/skills/`,
  `./AGENTS.md`, and the `./CLAUDE.md` import shim (restore backups first when preserving prior files)

---

## License

MIT
