# Harness log

## 2026-07-18 — Update-flow round: the evening-chaos forensics fixed (kits 2026.07.18-2)
Two Opus investigators reconstructed the user's three restart symptoms from transcripts + state
files: (1) BuyPlugGo "stale state" = VS Code opened TWO parallel sessions; the fresh one served
its pre-update SessionStart snapshot and re-proposed a finished update; no session started after
the stamp, so last_seen/path.state sat waiting. (2) portfolio "wanted to update again" = the
update was PERFECT; the "KIT UPDATE NOT FINISHED" nag + the false "(applied externally)" banner
read like a hanging update. (3) synaipse = the healthy flow, forced through by the escalating
nag ("5th session" in ONE evening — every window counts). Fixes: scaffold ×2 writes a one-shot
`.claude/kit_updated_from` marker (previous version) that the next SessionStart consumes —
announcement survives broken/parallel restarts and never claims "external" for PM-run updates
(deliberately NOT "write last_seen at scaffold time": that would kill the announcement — audit
warning); same-version re-runs stay allowed (they legitimately re-sync preset/roles) but are
LOUD and no longer reset the pending escalation counter; the nag is renamed KIT MERGE BACKLOG
with explicit "version already current — do NOT re-run the scaffold"; no scolding while
first_seen is today; the UPDATE AVAILABLE text tells the PM to re-read kit_version right before
scaffolding (parallel-session snapshot). NEW alias tripwire: raw `model: worker` in INSTALLED
frontmatter (an OneDrive write artifact left it unresolved — the bookkeeper subagent crashed at
spawn) is now flagged as broken instead of "in sync". NEW handover hint: SessionStart names the
PREVIOUS session's transcript (~/.claude/projects/<key>/, newest jsonl excluding the current
session) and instructs the PM to skim its END before resuming — a real office PM re-proposed
something the prior session had already settled; project_memory stays the truth. PM skills
updated (merge tasks ≠ update; finish merges BEFORE proposing the restart). Field repair:
BuyPlugGo's 8 broken agents fixed (worker→sonnet, lead→opus, map-consistent). 3 new + 3
rewritten tests (243 total).

## 2026-07-17 — Double-Fable audit of the consolidation: outbound encoding + crash guards (dev 2026.07.17-9, research -10, office -8)
Auditor A issued the week's first unconditional Freigabe (behavior preservation verified
line-by-line at every migrated call site; quotepath=off proven strictly better; the E2E cache
proof confirmed hard). Auditor B's live simulation found what A's diff view couldn't: (1) the
encoding family was only HALF dead — hooks WRITE their block messages through cp1252 stderr, so
"Käufer" reached a UTF-8 provider as mojibake, and the new E2E test's ASCII assert had sealed
the gap; _compat now pins stdout/stderr to UTF-8 as an IMPORT side effect (every hook imports
it — the six that didn't now do), and the E2E assert demands the umlaut itself survive. (2) The
new structured-first branches CRASHED on scalar-typed knobs (`coverage_gate: streng`,
`project: string` — AttributeError killed the whole pipeline where the old regex fell back);
type guards added, incl. the bool-is-int trap (`threshold: true`) and the scalar source_areas
char-iteration (quality + kit_checks). (3) The two deliberately-stdlib gates were BOM-blind:
a PS-5.1 BOM rewrite of a correctly filled project_config caused a PERMANENT push block with
escalation (live-reproduced); utf-8-sig, one line each (gate_memory_complete ×2,
gate_packaging_decision). Plus: load_project_yaml got the 2 MB cap (9.6 MB YAML cost 15 s per
parse in the BLOCKING hook path), E2E gets a git skipif, CI pins PYTHONUTF8=0 (Python 3.15
flips Windows to UTF-8 — the runner would go green-without-meaning while cp1252 field machines
stay exposed), and the demoted regex fallbacks got their first test (they were dead paths in
CI, which always installs pyyaml). 3 new tests (240 total).

## 2026-07-17 — Consolidation round: kill the bug FAMILIES, not the bugs (dev 2026.07.17-8, research -9, office -7)
User decision after the week's audit pattern (every round introduced ≥1 MAJOR, and the MAJORs
clustered in the same three families): consolidate instead of the next feature. (1) ENCODING:
new _compat.run_captured() — THE hook-side subprocess call with pinned UTF-8/replace decode;
migrated gate_pipeline (git + runner call), gate_git (branch read), session_status ×3 (git),
auto_dashboard ×2; kit_checks got _run_git() with UTF-8 AND core.quotepath=off (git otherwise
octal-escapes umlaut paths and downstream isfile() silently skipped real files — latent bug
found while consolidating); retro.py pinned. Per-call-site encoding choices caused three
separate MAJORs in one week; now there is one choice. (2) PARSERS: new
kit_checks.load_project_yaml() (utf-8-sig, dict-or-{}) is THE structured reader for every
config knob — _yaml_lint_excludes/_budget_config/check_module_invariants refactored onto it;
quality.py's coverage_threshold/declared_stacks/_declared_source_areas and kit_browser_checks'
_config now read structured-FIRST with their regex forms demoted to pyyaml-less fallback (the
audit-found divergence class: same knob, two parsers, different behavior). (3) E2E: new
tools/test_e2e.py — six scenarios emulating the REAL provider path (raw UTF-8 bytes on stdin,
real subprocess chains, umlauts in paths/branches/messages/runner output): red pipeline keeps
its UTF-8 FAIL line in the block, green-tree cache round-trips with umlaut filenames, office
fs-tripwire blocks umlaut-path deletes, umlaut commit prose passes while force blocks,
repo-wide YAML finds a broken Geschäftskonten.yaml by name, session_status briefs an umlaut
branch without mojibake. The unit suite was STRUCTURALLY blind to this class (ASCII-escaped
payloads); these run in CI on both OSes. 6 new tests (237 total).

## 2026-07-17 — Fable audit of the blind-decision guard: Windows stdin encoding MAJOR fixed (dev 2026.07.17-7, research -8, office -6)
The cross-checker confirmed the guard's core (incident case blocks, "wie besprochen" legal,
wiring/mirrors/budget correct, chain honest) and found a MAJOR the test suite was STRUCTURALLY
blind to: providers send hook payloads as raw UTF-8, but Windows text-mode stdin decodes cp1252 —
"erwähnt" arrived as mojibake and the umlaut regex alternatives were dead code on the target
platform (json.dumps' default ASCII-escaping meant no test could ever catch it). Fix: _compat.load
reads stdin as BYTES + explicit UTF-8 decode (×3 byte-identical — this also future-proofs German
file paths in every other guard), guard_question_context now goes through _compat.load (which
also fixes the garbage-payload crash class), and a new raw-UTF-8 test helper closes the blind
spot. Audit-reported misses added: "as mentioned/noted/stated/listed above", trailing "the plan
above", "o.g.", "obige/obenstehend", inflected participles ("das oben beschriebene Set"), header
field scanned; FP damping: "oben dargestellt WERDEN" (UI placement) passes via lookahead. Codex
honesty: AskUserQuestion mapped to None in gen_provider_artifacts (the fallthrough used to write
a dead Claude tool name into .codex/hooks.json) and the SKILLs now say the rule binds Codex
without a hook. 2 new tests (231 total).

## 2026-07-17 — Blind-decision guard: questions must carry their context (dev 2026.07.17-6, research -7, office -5)
BuyPlugGo transcript forensics confirmed the user's report: the PM asked "Kategorien-Set
freigeben (wie oben zusammengefasst)?" — but the ENTIRE turn before the question was thinking +
tool calls, zero visible text. The referenced summary existed only in the model's hidden
thinking; the user decided blind (3 of 16 AskUserQuestion turns in that session had NO visible
text in the turn at all). Not a client rendering bug — a PM behavior bug. Fix: NEW
guard_question_context (PreToolUse AskUserQuestion, byte-identical ×3, validate-mirrored,
settings-registered ×3) blocks question/option text referencing invisible context ("wie oben",
"siehe oben", "oben zusammengefasst", "as summarized above", "the above plan", ...) — while "wie
besprochen" stays legal (the user SAW that dialogue); the block message teaches the self-
contained form. Rule documented in the PM/office-manager SKILLs + constitution hook tables (dev/
research stayed at exactly 220 lines by merging the guard_no_adhoc/guard_pm_scope rows). 2 new
tests (229 total). Installed to staging; live projects NOT restamped (user starts fresh sessions
tonight — the update announcement will offer it).

## 2026-07-17 — Double-Fable audit of the upstream round: 2 MAJORs + hardenings (dev 2026.07.17-4, research -5, office unchanged -3)
Both cross-checkers confirmed the round's core (no shell-injection path into run_npm/Popen —
every argument list static; `--only` cannot infect the merge gate or the green-tree cache;
mirrors byte-identical; Windows npm bug + orphan leak empirically re-proven) and each found a
real MAJOR. (1) HALF-SIDED UTF-8: gate_pipeline still read the now-UTF-8 runner with the locale
codec — one Vitest `❯` killed the reader thread and the block message lost the ENTIRE pipeline
output (audit-proven p.stdout=None); the hook now pins utf-8/replace ×2. (2) Missing Chromium
BINARY hard-failed the gate although docstring/SKILL promise warn — and package-yes/browser-no
is every fresh setup's state now that requirements-dev installs playwright; launch errors naming
`playwright install` degrade to warn, everything else stays FAIL. Also fixed from the audits:
kit_browser_checks joined validate's dev↔research mirror list AND kit_checks' _ENFORCEMENT_SOFT
(it was watched by neither drift guard); source_areas parser in quality.py now accepts the same
YAML forms as kit_checks (inline/quoted/comment lines — the block-only version silently skipped
an inline-declared area); browser_smoke config survives trailing comments (silent default
fallback); pytest gets the `python -m` fallback too; a frontend without a build script FAILs
(fidelity to the original); npm audit reports PASS + tail again; module_invariants wraps bare-
string tokens (char-iteration repro) and never counts stale rules as PASS; repo-wide YAML parse
caps files at 1 MB (warn) + uses the C loader; readiness probe hits the server root and fails
fast with output when the preview dies instantly; mypy covers every source area; declared_stacks
survives quoted items/comments; glob-crosses-slashes documented. 4 new tests (227 total).

## 2026-07-17 — quality.py upstream round: synaipse fork distilled into the kits (dev/office 2026.07.17-3, research -4)
The deferred backlog item 7: a forensic inventory of synaipse's 2,348-line quality.py fork (26
commits) + portfolio's 382-line variant classified 21 features into generalizable / parameterizable
/ product-specific; the first two tiers are now kit defaults. HEADLINE KIT BUG: the baseline
check_node was de facto DEAD ON WINDOWS — npm/npx are .cmd shims subprocess cannot exec without
shell=True (WinError 2), so every node check failed as "npm not installed"; run_npm() (shell on
nt, UTF-8 decode, Electron-var-stripped env) fixes it. Also into the template runner: stdout/
stderr UTF-8 reconfigure + run() UTF-8 decode (two projects independently fixed the same cp1252
gate crash — a UnicodeEncodeError used to hide the FAIL it was printing); `vite build` step with
dist/index.html proof + 2 same-criterion retries clearing node_modules/.vite (the documented
stale-cache bug that reproduced ONLY under the hook chain) + a 2000-char fail tail; tool_cmd()
`python -m` fallback (pip drops shims outside PATH); ruff/mypy targets from source_areas instead
of repo root; pip-audit scoped to declared deps; typescript_react/react stack aliases; `--only
<stack>` fast-iteration flag (loudly partial, never merge evidence — pairs with the test-scoping
ladder). NEW kit-owned scripts/kit_browser_checks.py (always overwritten like kit_checks; scaffold
×2 updated): generic Tier-2 browser smoke — vite preview on a FREE port + Playwright chromium,
mount element non-empty + zero console errors, process-TREE kill on Windows (orphaned preview
servers were a real chronic memory leak), degrades to warn without playwright/npx; config knob
`browser_smoke:` in testing_guidelines. kit_checks grew: chunkSizeWarningLimit-assignment guard
(raising the threshold instead of code-splitting is a defect), repo-wide git-tracked YAML parse
(~50 unparsable decisions.yaml items shipped while the dashboard swallowed the error; excludable
via yaml_lint_exclude:), module_invariants (forbidden-token rules as data — synaipse hand-rolled
the same guard three times). requirements-dev += playwright; devops SKILL carries the
container-parity + CSP-smoke recipes as patterns (deliberately NOT kit code: compose/product
bound). NOT upstreamed: container self-delegation, contrast/structure orchestration, product e2e
flows (locator churn: 4 rename commits), axe sweep helpers (valuable but axe-version-calibrated —
own follow-up round). 8 new tests (223 total; an earlier "11" here was a miscount — audit I2).

## 2026-07-17 — Double-Fable audit of the adoption round: 3 MAJORs fixed (kits 2026.07.17-2)
Two independent Fable cross-checkers on 4e7db52 (both confirmed the chain, the detection
consolidation incl. every prior adversarial case, proc_hash and the PII mechanics) converged on
two MAJORs and B found a third. (1) `..` ESCAPED THE REPO: the area sanitizer's char class blocks
separators but not dot-only names — `source_areas: ['..']` walked the PARENT dir and scanned
NEIGHBOR projects (empirically proven; sites: kit_checks budget, gate_test_coverage areas,
dashboard vitals). Dot-only names are now rejected in all four copies. (2) RENAME TRIPWIRE
false-fired on every mature project without auto-memory — memory is OPT-IN and two of the three
live projects would have been nagged at every session start. Replaced by a DETERMINISTIC signal:
session_status ×3 records the project's abspath in gitignored `.claude/project_path.state`; a
recorded path differing from the current one IS a rename/move (first run records silently;
normcase comparison also kills the drive-case footgun). (3) COMBINED SHORT FLAGS bypassed every
git gate: `bash -lc "git push --force"` — the wrapper regex wanted `-c` as its own token, so the
payload was stripped as prose (carried over from 2026.07.16-2, where consolidation was the moment
to close it). The c-flag now matches inside a cluster (`-lc`, `-xec`) and quoted payloads with
ESCAPED quotes no longer cut the unwrap short (_compat ×3, byte-identical). Plus F5/INFO: the
memory-gate repeat counter now matches the exact reason, not an 80-char prefix. ACCEPTED
tripwire-level residual (both auditors): Bash redirects can still write the green-tree cache —
documented, consistent with the harness's 95%-tripwire philosophy. 3 new regression tests + the
tripwire test rewritten for the deterministic signal (215 total). Live projects again NOT
restamped per user decision.

## 2026-07-17 — Field-survey adoption round (kits 2026.07.17-1)
Implements the two-Fable field survey's backlog (all three live projects, 2026-07-16); the deep
quality.py upstream is DEFERRED to its own round. (1) FALSE-GREEN HOLE closed: budget/vitals scan
areas are now project-extendable (`source_areas:` in coding/research_guidelines — a real project's
compounder/ was never scanned; the check also WARNS instead of staying silent when NO area
matches) and the per-area test gate honors `coverage_areas:` in testing_guidelines. (2)
proc_hash.py: the (?s)-DOTALL regex let a hash land in the NEIGHBORING PROC block (live incident)
— fixed to (?m)+CRLF-tolerant headers plus a pre-write verification that no other PROC's hash
changes. (3) Office PII package: filing_log + migration manifests are gitignored by design
(names stay out of history; ledger stays tracked — statutory retention), data-minimization rule
in constitution/skill/templates, owner-PII warning in business_profile, office gets its own
security-guidance scoping file. (4) Rename-fallout package: compose `name:` warn-check in
kit_checks, RENAME TRIPWIRE in session_status ×3 (mature project without auto-memory under its
key), devops rules (pin compose name; foreign Docker projects only with user OK — a real OOM hunt
stopped a neighbor's prod DB). (5) gate_pipeline: green-tree cache (identical clean tree skips
the re-run — a night ran 13 identical pipelines; cache file is selfmod-blocked + gitignored),
FAIL-lines-first block output, _audit reason 300→2000 (the cut had hidden the only FAIL line).
(6) gate_subagent_output: retry says "do NOT work further, ONLY print the YAML" (a real retry did
41 min of new work) + gave_up logs what stayed missing; gate_memory_complete escalates on the 3rd
identical block (~14 identical nag-blocks in one night). (7) Field patterns into skills/templates:
screenshot-walkthrough matrix + freshness-as-design-surface (designer), serialize-same-file
agents (PM), standing-rule tests + backfill honesty (guidelines), env.example convention +
compose/docker rules (devops), guidelines versioning + bundle-split/sha256 + Löschen-Quarantäne +
cutover ritual (records-clerk). Detection consolidation: push/merge matching now lives ONCE in
_compat (wants_push_or_merge) — six hook-local copies had already drifted twice. Per user
decision the live projects were NOT restamped (their PMs get the update announcement at next
session start).

## 2026-07-16 — Fable cross-check of the gate fix: wrapper-push regression closed (dev/research 2026.07.16-2)
A user-requested independent Fable audit CONFIRMED the -1 round (root cause reproduced A/B/A;
no fail-open in any guard — ntpath.relpath compares drive case-insensitively; delivery verified in
both projects) and caught what the round itself introduced: plain quote-stripping regressed
`bash -c "git push ..."` / `powershell -Command "git push ..."` PAST both gates (the old substring
check had caught them), and QUOTED force flags (`git push "--force"`, `"+main"`) escaped the
always-forbidden ban. Fix: shell-WRAPPER payloads (bash/sh/zsh/dash/pwsh/powershell/cmd with
-c/-Command//c) are unwrapped as CODE before the remaining quoted spans are stripped as PROSE —
the fixed prose-commit incident stays fixed; the force check now runs on the RAW text (quotes are
shell syntax, git still receives the flag) with the +refspec pattern extended to quoted forms.
4 gate files (dev+research), 2 new regression tests (204 total).

## 2026-07-16 — Drive-letter-casing gate bug solved + prose-push false trigger (kits 2026.07.16-1)
A synaipse push was blocked all night: vite/rollup failed 100% deterministically ONLY inside
gate_pipeline's subprocess chain, 0% in the team's own comparison shells. Their DevOps had
methodically refuted memory/env/cache/spawn-shape hypotheses (including reproduce-first refutation
of ELECTRON_RUN_AS_NODE) but could not see the real delta: the hook chain passes the session's
LOWERCASE drive-letter cwd (`c:\...`) verbatim to node children, while every "direct" comparison
ran through Git-Bash, which silently msys-normalizes to `C:\...`. Controlled A/B here confirmed it:
same build, cwd `c:\...` red, `C:\...` green, and a third run (`C:` + lowercase components) proved
ONLY the drive letter matters. Fix: `_root.find_repo_root` now uppercases a lowercase Windows
drive letter (lexical only — deliberately NOT realpath(), which would resolve junctions and change
path identity for prefix-comparing guards); mirrored ×3 kits, so EVERY hook benefits.
gate_pipeline additionally spawns the pipeline with stdin=DEVNULL. Second field defect fixed in the
same round: gate_git/gate_pipeline matched `git push`/`git merge` as naive substrings, so a commit
MESSAGE describing the bug re-triggered the full RED pipeline; both gates (dev + research) now
strip quoted spans and match a real git invocation (`\bgit\b[^&|;\n]*\b(push|merge)\b`) — unquoted
prose may still over-trigger, the safe direction for a gate. 3 new tests (casing, prose commit
passes + real push still gates, force-check survives quote-stripping).

One dated entry per hardening round: WHAT changed and WHY — the tool-neutral entry point into this
repo's history for any agent CLI (Claude Code, Codex) and for humans. Full rationale lives
in the referenced commit messages; project conventions live in the kits themselves. Newest first.
Append an entry with every shipped round (same commit).

## 2026-07-15 — Test-scoping ladder closes the ORCHESTRATION gap (dev-team 2026.07.15-2)
Live-run finding (user complaint, second occurrence): the synaipse PM ordered the FULL 792-test
suite after every micro-step. Forensics showed the kit already had the staged-testing rule in all
three EXECUTOR skills (QA: full suite exactly once per verdict; frontend/backend: affected tests
only in the dev loop) — the leak was the PM level, which no rule covered. Fix: the PM skill now
carries the orchestration ladder (mid-slice work orders say "affected tests only"; full suite ONCE
per slice end via QA's verdict run; merge/push gate untouched as the guarantee; escalation to full
for cross-cutting changes; pre-push full run may repeat once against flakiness), and the
testing_guidelines template states the ladder as a global project rule. research/office skipped
deliberately (no comparable suite-scale/QA model). Template is copy-if-absent: existing projects
get the ladder via the PM skill on restamp; their filled testing_guidelines.yaml keeps their state.

## 2026-07-15 — office-team gains the office-developer role (kits 2026.07.15-1)
User decision, superseding "dashboards via separate consumer project": dashboards stay OUT of the
kit (business-specific — structures, naming, products differ), but the office kit now ships the
ROLE that builds them per business. `office-developer` (model lead — deliberately the strong tier:
it is the kit's only coding role and office ships no QA/CI net; preset `full` via `all`) is a
STRICT read-consumer: it owns `tools/**` (generator scripts) + `dashboards/**` (rendered output)
and reads the tracked, kit-schema'd data (product_catalog, ledger CSV, registers) — it never
mutates ledger/YAMLs/kit scripts/enforcement; PROC-gated like every specialist; output must be
deterministic, self-contained (no external loads) and honestly labeled (EÜR-style, never "GuV");
self-verification duty replaces the missing QA. Wiring: constitution §2.1/§5/§6, registry roster
(+ summary now says 8 specialists), template model/effort maps. Precedent: research-team's
research-engineer (technical builder inside a domain team). The new validate check 12 caught the
two new files as hashed-but-untracked before they could repeat the CI-red incident.

## 2026-07-14 — Opt-in user-wide Codex secret shield (repo-level, no kit bump)
Closes the last documented Claude/Codex asymmetry on user request: Claude gets user-wide
secret-read denies via the settings.json merge, Codex had them only per generated team project.
New OPT-IN installer flag (`-CodexGlobalSecrets` / `--codex-global-secrets`) runs
user/codex_global_config.py, which appends a marked, removable profile to $CODEX_HOME/config.toml.
Design rests on freshly VERIFIED semantics (learn.chatgpt.com/docs/permissions + openai/codex
source): profiles are CLOSED-WORLD (a naive deny-only profile would have locked everything ->
`extends = ":workspace"` + the Claude-side deny list + `~/.ssh`); `default_permissions` must sit
BEFORE the first TOML table (surgical top-level insertion, block appended at the end); a
`[permissions]` profile without any `default_permissions` is a Codex config ERROR (activation is
skipped only when the user already has their own); legacy `sandbox_mode` in ANY loaded level
silently disables ALL profiles (fail-closed abort with guidance instead of an inert shield).
Honest trade-off documented: no-trust-decision folders start `:workspace` instead of `:read-only`
while the shield is active; trusted team projects keep their generated profile (CLI precedence;
Codex Desktop has an open upstream bug applying project profiles, openai/codex#22553). Never
activated silently: backup first, tomllib re-parse before atomic replace, idempotent marker.

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
