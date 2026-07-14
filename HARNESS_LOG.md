# Harness log

One dated entry per hardening round: WHAT changed and WHY — the tool-neutral entry point into this
repo's history for any agent CLI (Claude Code, Codex) and for humans. Full rationale lives
in the referenced commit messages; project conventions live in the kits themselves. Newest first.
Append an entry with every shipped round (same commit).

## 2026-07-14 — Two-auditor cleanliness sweep after the parity round (kits 2026.07.14-10)
(-9 -> -10 within the hour: the NEW ci-green rule immediately caught its first real bug — on
GitHub's windows runner a pwsh parent hands its PS7 PSModulePath to the powershell-5.1 child, so
`Get-FileHash` (module auto-load) failed with CommandNotFoundException inside
init_project_memory.ps1/scaffold_team.ps1. That also hits real users invoking the scripts from a
pwsh terminal. Fixed by hashing via .NET SHA256 directly (no module resolution); verified locally
under a deliberately poisoned PSModulePath.)
Two INDEPENDENT auditors swept repo + installed state + both live projects. Their unanimous green:
staging/user files byte-identical to sources, both projects contract-clean on -8, the
user/claude-vs-user/codex asymmetry is by design ($CODEX_HOME/config.toml is user-owned; everything
kit-relevant is generated per project — now documented, incl. the deliberate consequence that
user-wide secret denies exist on the Claude side only). One auditor found what every local check
structurally missed: three office template seeds (inbox/archive/outbox README.txt) were shadowed by
the template's own `dir/` .gitignore rules and NEVER tracked — the kit hash walks the filesystem,
so local validate stayed green while GITHUB CI WAS RED and fresh clones could not install. Fixed
via `dir/*` + `!dir/README.txt` negation (a file inside an EXCLUDED DIRECTORY cannot be
re-included), plus a new validate check: every hashed kit file must be git-tracked. PROCESS RULE
ADDED: a push is only "shipped" after the CI run is verified green. Both found the same MAJOR:
two first-generation Copilot files (memory-engineer.agent.md, project-memory.instructions.md — the
latter auto-injecting via `applyTo: "**"`) still in VS Code prompts; the installer cleanup list now
covers them. Also swept: the last ~30 "constitution in ./CLAUDE.md" wordings → ./AGENTS.md
(agents, session_status ×3, scaffold headers, template READMEs), model_tiers "claude-watcher" →
radar-watcher, radar/README describes the watcher DUO, office heading dropped its dangling
"§11-equivalent", stray empty dirs removed, settings.json.bak behavior documented.

## 2026-07-14 — Codex-authored parity deepening, reviewed + hardened; Copilot removed (kits 2026.07.14-8)
(-7 was superseded minutes after push: the live synaipse restamp surfaced that the stricter map
validation rejected `fable` — a legitimate §11 Claude-side pin on its frontend role — so `fable`
is now an accepted lead-tier model value: Claude keeps it literally, every other provider maps it
to its LEAD tier. Shipped as -8 with a regression test.)
An OpenAI Codex (GPT-5.6 Sol) session reworked the provider layer for functional Claude/Codex
parity (transactional scaffold with snapshot/rollback, ownership manifests + symlink/reparse
guards, a runtime hook-bundle hash verifier inside every generated hook command, preset parsing
moved from shell regex to Python/PyYAML, role-scoped specialist hooks, subagent-start auditing,
fail-closed settings merge; left unstaged as kits -6). A three-agent review plus an
official-source fact check (learn.chatgpt.com docs + the openai/codex source) confirmed the
security claims AND the doubted event contracts (PostToolUse and SubagentStart EXIST; `agent_type`
is a required payload field; exit-2 and `decision: block` are both documented), then this round
fixed the regressions before shipping: the settings.local.json gate no longer blocks on
`permissions`/`model` (it had locked every actively used project out of kit updates), a legacy
project_config without `providers:` defaults to [claude, codex] instead of hard-failing (a PRESENT
but invalid line stays fail-closed), install.ps1 no longer swallows merge failures, PS-5.1
`2>$null` footguns removed, bash-3.2 empty-array expansion fixed (macOS), dangling reparse points
detected, install.sh staging litter trapped, dead generator code removed, the unverified 0.138.0
baseline replaced by the documented 0.131.0 hooks-GA+trust baseline, one wrong docs path fixed
(`/docs/build-skills`). DECISIONS: (1) **Copilot support removed** — the kits target Claude Code +
Codex only; installers clean up previously installed Copilot files, the generator rejects
`copilot` with a migration hint but still recognizes and removes stale `.github` artifacts.
(2) **providers default is BOTH** (`[claude, codex]`) everywhere, so a mid-project CLI switch
needs no config edit. (3) **Source-format decision recorded:** the kit source stays Claude-native
(the richest directly-executable format — rich-to-poor translation is deterministic; a neutral
third format would execute nowhere and need two translation layers). Neutral SEMANTICS are
enforced instead: tier aliases `lead`/`worker`/`light` are the ONLY model values in kit sources
(validate-checked; scaffold resolves them per provider), the constitution source is
`constitution/AGENTS.md`, kit settings.json is documented as the Claude REGISTRATION of the shared
hooks, and a namespaced `codex:` frontmatter overlay is the sanctioned divergence valve for
Codex-only TOML keys. TRIP-WIRE for revisiting a full neutral source format (standing watcher
duty): overlays accumulate beyond scattered scalars, a third provider needs artifacts, or the
.md-agent/@import contract breaks. Also: mattpocock references removed (the repo is fully
self-authored today); repo renamed to GiaZenX/harness.

## 2026-07-14 — Multi-CLI parity + forensics defect round (kits 2026.07.14-4)
The same harness now runs on Claude Code, Codex CLI (BETA) and GitHub Copilot (generated,
live-unverified) — one kit source, generated provider artifacts (AGENTS.md as the AAIF-standard
constitution + a verified CLAUDE.md `@AGENTS.md` import shim, `.codex/`/`.github/` registrations
via gen_provider_artifacts.py, shared Python hooks behind the `_compat.py` payload adapter),
tier-based model maps (model_tiers.yaml: lead/worker/light → Opus/Sol, Sonnet/Terra, …), a
provider-neutral git-level second line of defense (kit_checks enforcement-diff, incl. trunk
workflows), a claude-watcher/codex-watcher duo, and the eight defects (D1–D8) found by forensics
on the first 2026.07.14-2 production day — incl. two guard_harness_selfmod bypass holes reported
by the project's own security reviews, plus new selfmod protection for the constitution files
themselves. Fable diff-audit: 0 blockers, 5 findings (M1–M5), all incorporated; 129 tests green.

## 2026-07-14 — Research-grounded hardening (`bb8b869`, kits 2026.07.14-2)
Constitution diet to <=220 lines (research: bloated rule files get ignored; subagents inherit them,
so the diet pays on every spawn), opus defaults for judgment roles (architect/designer/QA,
methodologist/reviewer), agent memory scoped to craft roles with a curation cap, mandatory work-order
spawns, SubagentStop output contract, guard_harness_selfmod (no agent edits the enforcement layer),
entry-level QA-verdict binding in gate_git, project-auditor role in all kits, kit-version
announcements at session start. Fresh-eyes Fable audit: 12 objections, all incorporated.

## 2026-07-12 — V1–V7 + file budget + mechanical presets + office-team kit (`3f8ecc6`)
Presets became MECHANICAL (scaffold installs only the confirmed preset's roles), hard 800-line file
budget with architect-owned exemptions (a real App.tsx hit 8,966 lines), kit-owned kit_checks.py that
updates force-overwrite (a project's quality.py fork had silently never run kit checks), and the
third kit (office-team: bookkeeping/filing with append-only ledger scripts and fs tripwires).

## 2026-07-12 — Restamp resync gap + shell bypass (`331a125`)
External restamps now re-stamp model/effort frontmatter from the user-confirmed maps (a project ran
its approved-opus frontend on sonnet for two days), and the progress.yaml contract is enforced at
pipeline time too (a shell heredoc had bypassed the write-time guard).

## 2026-07-10 — Speed + precision round from synaipse forensics (`40af990`)
Fast-iteration path (--frontend-only) so small UI fixes stop paying the full merge gate, plus
precision fixes P1–P7 from real-run friction; radar triage process for external feature watch.

## 2026-07-04 — Design-fidelity chain + enforcement holes (`f6f49d3`)
15 audited fixes: mockup-as-base design chain (frontend builds literally on the designer's
deliverable), cost discipline, and closure of enforcement bypasses found in real runs.

## 2026-07-03 — Kit versioning + guided updates (`20128f8`, `e70045c`, `f140957`)
VERSION stamps per kit (content hash), session-start update detection, guided safe updates with
[kept]-line visibility for diverged files — the foundation the pending-file contract builds on.

## 2026-07-03 — Synaipse forensics round (`75040b5`)
Write-time YAML guard, masterplan-as-log flow, dead-end honesty rule, handover honesty, architect
opus recommendation — the first round fully driven by transcript forensics of a real project.

## 2026-06-30 — Design ambition + a11y (`7175457`, `b4faba9`)
Design-ambition fork (basic consistency vs. final polish), deterministic a11y/contrast gate seed,
security guidance anchored as advisory shift-left in QA/DevOps skills.
