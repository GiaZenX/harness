# Radar — 2026-09-25 (claude-watcher, run by claude)

Scan window: Claude Code changelog **2.1.270 → 2.1.282** (Sep 13 → Sep 24, 2026; the prior claude
report covered through 2.1.269). Plus the official model lineup (overview / pricing / deprecations /
anthropic.com), the hooks reference, the subagent reference, the memory doc, and a community sweep.

`radar/decided.md` read first — current through the **2026-09-05 codex triage**; no row below
repeats one of its slugs. The five still-open items from `radar/2026-09-04-claude.md` and the six
from `radar/2026-09-12-claude-by-claude.md` are carried at the bottom as pointers, not re-surfaced.

**This was a heavy week, and the single biggest thing is not a feature — it is a re-tiering that
happened by itself.** Claude Opus 5.5 went GA on 2026-09-22 and became *the default Opus model*.
Because `team-kits/model_tiers.yaml` maps the Claude rungs by **name** (`opus: opus`) rather than by
model id, the `opus` rung — the standing tier of the builder, the orchestrator and the verifier under
DEC-0095 — moved a model generation with **no edit, no proposal and no restamp**, which is exactly
the automatic bump that file's own MAINTENANCE header forbids (item 1). Item 2 is the tier-table
proposal that follows from it, plus a price anchor in that file that is wrong by ~4x. Item 3 is a
source-format item: Claude Code now reads `AGENTS.md` natively, which leaves the kits' 2-line
`CLAUDE.md` shim intact but changes *why* it has to stay.

## Repo health — green (with one honest gap)

- `python tools/validate.py` → **`all structural checks passed.`**
- `python -m ruff check .` → **`All checks passed!`** on the pinned **ruff 0.15.20**
  (note: bare `ruff` is not on PATH in this shell; `python -m ruff` is).
- `python -m pytest tools/ -q` → **not run.** `gate_test_scope.py` refuses the whole declared
  surface from a line that is not a delivery run (`DELIVERY_RUN=<ITEM-ID>`, surface declared at
  3465 s in `tools/test_surface.json`). **That is the gate working as designed, not drift** — a
  watcher run is not a delivery run and must not stamp one. Ran a representative subset instead:
  `pytest tools/test_model_ladder.py tools/test_repo_hygiene.py tools/test_radar_trigger.py -q`
  → **75 passed, 1 warning in 109 s** (the warning is the known CRLF note on
  `project_memory/.audit/hook_events.jsonl`, repaired where it is written).
- Tree at `1f883d2`; the only dirt is `project_memory/staging/generation-6-streams.md` (modified) and
  an untracked `project_memory/.kernel.lock`. **Nothing was written outside `radar/`.**
- A **standing suggestion for the watcher contract** (the definition tells me to run the full
  surface, and the repo's own gate forbids it): the health line should name a *bounded* suite, or the
  definition should say "subset + why". Report-only; I do not edit my own definition.

---

## Highest-impact

### 1. Claude Opus 5.5 is GA and is *the default Opus* — so the `opus` rung re-tiered itself, bypassing the "never an automatic bump" rule
- **Sources** (all seen 2026-09-25):
  - changelog https://code.claude.com/docs/en/changelog — **2.1.280 (Sep 22)**, verbatim: *"Added
    Claude Opus 5.5 (`claude-opus-5-5`), now the default Opus model — 1M context, $4/$20 per Mtok
    with $0.20/Mtok cache reads"*; same entry: *"changed the default on Pro and Team Standard from
    Sonnet to Opus."*
  - models overview https://platform.claude.com/docs/en/about-claude/models/overview — Opus 5.5 is
    the recommended starting model ("start with Claude Opus 5.5 for most workloads"); **default
    effort `medium`**, 1M context, 128K max output, retirement not sooner than 2027-09-22.
  - pricing https://platform.claude.com/docs/en/about-claude/pricing — **$4 / $20 per MTok**, cache
    reads **$0.20** (0.05x, a footnoted exception to the standard 0.1x), batch $2/$10; Opus 5 remains
    $5/$25.
  - deprecations https://platform.claude.com/docs/en/about-claude/model-deprecations —
    `claude-opus-5-5` **Active**; nothing newly deprecated or retired this window.
  - https://www.anthropic.com/claude-opus-5-5 — Anthropic's own claim: Opus 5.5 *"performs at the
    level of Claude Fable 5.1 on most work and costs 40% less to run than Opus 5"*; $4/$20 is "20%
    below Opus 5", cache reads "60% less".
- **What it is**: a new top Opus, cheaper than the Opus it replaces, vendor-claimed at Fable-5.1
  quality for most work, and **already the model the bare name `opus` resolves to** in Claude Code.
- **Why it matters HERE — measured against the tree, not assumed**:
  - `team-kits/model_tiers.yaml` `tiers.claude` is pass-through: `fable: fable`, `opus: opus`,
    `sonnet: sonnet`. The Claude rungs are **names, not pinned ids**. So on 2026-09-22 the `opus`
    rung changed model generation everywhere at once.
  - Who that moved, counted in the tree: **10 kit roles pinned `model: lead`** (dev
    `project-manager`, `software-architect`, `quality-engineer`, `product-designer`; research
    `project-manager`, `methodologist`, `reviewer`; office `office-manager`, `office-developer`) plus
    `.claude/agents/harness-lead.md` (`model: opus`), plus — under **DEC-0095 (1)/(2)** — the build,
    the orchestration and the verification, which that decision deliberately moved *onto* `opus` as
    the standing tier. The whole standing tier of every kit moved.
  - The file's own MAINTENANCE header says: *"Changing a rung's model here re-tiers every project on
    the next restamp: always a USER-approved proposal, never an automatic bump."* The alias form
    makes that sentence unenforceable — the bump happened without touching the file, so no restamp,
    no proposal, and no test could see it.
- **Recommendation**: **adopt — capture an item.** Two questions, and only the user can answer the
  second:
  (a) *mechanical*: should the Claude rows carry a **recorded resolution** (an assertion of which
  concrete model each rung resolves to today, red when it moves) so a platform default change is a
  visible failure instead of a silent one? Note the trade-off measured earlier: a hard **pin** is not
  obviously safer — `radar/decided.md radar-0829-model-404-fallback` recorded that a pinned model
  that 404s now *silently falls back*, so a stale pin fails quietly in the other direction. An
  asserted-resolution test is the shape that fails loudly either way.
  (b) *policy*: is `fable` still the right top rung — see item 2.
  Effort: ~2–3 h for (a) including a test that is red without it. · **Status**: NEW

### 2. TIER-TABLE proposal + the Claude price anchor in `model_tiers.yaml` is wrong by ~4x (the 09-05 anchor rework did not fix the Claude side)
- **Sources**: pricing + overview as in item 1, seen 2026-09-25; the stale text is
  `team-kits/model_tiers.yaml`, anchor block, read 2026-09-25.
- **What it is**: the anchor block states, for the Claude side:
  `claude: Opus-class $15/$75 . Sonnet 5 $2/$10 standard … Opus 4.1 was shut down 2026-08-05`.
  **$15/$75 was Opus 4.1's price**, and Opus 4.1 was retired 2026-08-05 — the same line says so two
  clauses later. On the stated read date (2026-09-05) the live Opus price was already **$5/$25**;
  today it is **$4/$20**. The anchor is ~3.75x too high on input and ~3.75x on output.
- **Why it matters HERE**: this is a **material update to already-decided items**, not a new
  discovery of the same dead line. `radar-0904-model-tiers-stale-comment` → **BUG-0092** and
  `codex-0905-price-moves` → *"folded into BUG-0092 / PR-0010 AC-4: one stale-anchor fix, both
  providers"*. Both items are now in `project_memory/archive/` (`archive/BUG/2026/BUG-0092.yaml`,
  `archive/PR/2026/PR-0010.yaml`) — i.e. **closed** — while the Claude half of the anchor they were
  supposed to fix is still wrong, and the Sonnet-5 half and the OpenAI half were fixed. The guard the
  round built (`test_no_watch_date_in_the_tiers_table_lies_in_the_past`) measures **dates**; nothing
  measures **prices**, which is why one of the two halves could pass. That is the BUG-0092 lesson
  repeating one level down: the fix was itemized, the *measurement* covered only the part that was
  easy to measure.
- **PROPOSALS** (I never edit the table; these are for the user's decision):
  - **P-A · anchor correction, no rung move (low risk, recommended).** Replace the Claude anchor with
    the figures read today: `Fable 5.1 $10/$50, cache read $0.25 (0.025x)` · `Opus 5.5 $4/$20, cache
    read $0.20 (0.05x), GA 2026-09-22, the model the name "opus" resolves to` · `Opus 5 $5/$25
    (legacy)` · `Sonnet 5 $2/$10 standard`. And add the thing that would have caught it: a test that
    an anchor line carries a **read date** and that the read date is not older than the newest model
    named on it — the price-side twin of the watch-date test.
  - **P-B · make the rung's resolution visible** — see item 1(a). Old: `opus: opus` (resolves to
    whatever Claude Code calls default Opus). New: `opus: opus` **plus** a recorded
    `resolves_to: claude-opus-5-5 (read 2026-09-25)` that a test reads. Evidence: the 2026-09-22
    silent move. Not a rung change; a visibility change.
  - **P-C · the top rung — a genuine user decision, no recommendation from me.** Evidence both ways.
    *For keeping `fable`*: the models overview still names Fable 5.1 for "demanding reasoning and
    long-horizon agentic work, or when your evals on Claude Opus 5.5 at higher effort still fall
    short" — i.e. the vendor still positions it above Opus 5.5, and DEC-0047 has dev climbing to
    `fable`. *For revisiting*: DEC-0095 removed the top rung as a **standing** tier purely on cost,
    and that arithmetic just changed — the gap is now **$10/$50 vs $4/$20** (2.5x input, 2.5x output,
    and Fable's cache reads $0.25 vs Opus 5.5's $0.20) while Anthropic itself claims Opus 5.5
    "performs at the level of Claude Fable 5.1 on most work". A cheaper `opus` makes the DEC-0096
    escalation (effort before rung) reach further before it needs the top rung at all. **Press
    positioning is a lead, not evidence** — the vendor's own comparison table is the source above,
    and a real answer wants one measured goal run per rung, not a price table.
- **Recommendation**: **adopt P-A now** (~30 min under an item), **P-B as the item from item 1**,
  **P-C to the user**. · **Status**: NEW

### 3. Claude Code now reads `AGENTS.md` natively (2.1.277) — the kits are unaffected, and the shim is now held up by the marker alone
- **Sources** (seen 2026-09-25): changelog 2.1.277 (Sep 18), verbatim: *"Added AGENTS.md support: in
  a project with no CLAUDE.md, Claude Code reads AGENTS.md instead; change it under 'Project
  instructions' in `/config`"*; and the memory doc
  https://code.claude.com/docs/en/memory § **AGENTS.md**, which carries the full resolution table and
  the new setting.
- **What it is**, from the doc's own table (not inferred):
  | repository has | Claude reads |
  |---|---|
  | `AGENTS.md`, no `CLAUDE.md`/`CLAUDE.local.md` at or above cwd | the `AGENTS.md` |
  | `AGENTS.md` **and** a `CLAUDE.md`/`CLAUDE.local.md` | the `CLAUDE.md` files **only** |
  | a `CLAUDE.md` that **imports** `AGENTS.md` | the `CLAUDE.md`, with `AGENTS.md` through the import |
  Plus a new knob: `/config` → **Project instructions**, or in settings under
  `pluginConfigs["agents-md@builtin"].options.instructionFiles` ∈
  `claude-md-or-agents-md` (default) · `claude-md-and-agents-md` · `claude-md` · `managed-only`.
  **It is ignored in project and local settings files** — only `~/.claude/settings.json`, a
  `--settings` file, or managed settings.
- **Why it matters HERE — three distinct consequences, and the first is reassurance**:
  1. **No break.** `scaffold_team.sh:721-725` / `scaffold_team.ps1:627-631` write `AGENTS.md` (the
     constitution) plus a 2-line `CLAUDE.md` = marker + `@AGENTS.md`. That is **row 3** of the table
     verbatim, so a kit install loads exactly what it loaded before, and `@import` semantics are
     unchanged and now *documented as the bridge*. The source contract holds.
  2. **A trip-wire worth writing down before someone "simplifies".** The reflex this release invites
     is: *native AGENTS.md exists, drop the CLAUDE.md shim.* That would break handover, not
     instruction loading — the global entry file and each kit's `session_status.py` decide "is a team
     installed" from **line 1 of `./CLAUDE.md`** and nothing else. Dropping the shim would leave a
     repo whose constitution loads fine and whose PM never becomes the PM. This belongs in the
     source-format ledger and, ideally, in the scaffold's own comment beside line 717.
  3. **A quiet way to switch the constitution off.** `managed-only` leaves out the project
     `CLAUDE.md`, every `AGENTS.md` **and** `.claude/rules/` at launch. A user-level or managed
     setting can therefore run a kit-installed repo with the gates live and the constitution absent —
     the agent obeys hooks but has never read the rules. A kit cannot set it and cannot be broken by
     a committed file (project/local are ignored), which bounds it; it is still the same family as
     **FR-0063** (`--restricted` ignoring user+project settings): *does the harness behave when its
     prose half is missing?*
- **Recommendation**: **adopt (small)** — one ledger entry for the widened instruction-source
  contract plus the (2) trip-wire note; **watch** for (3), folded into FR-0063's question rather than
  a new item. ~30 min. · **Status**: NEW

---

## Medium

### 4. `.claude/rules/` — a constitution-priority instruction surface no kit knows about
- **Source**: https://code.claude.com/docs/en/memory § *Organize rules with `.claude/rules/`*, seen
  2026-09-25. All `.md` files there are discovered **recursively**; those **without** `paths:`
  frontmatter load at launch *"with the same priority as `.claude/CLAUDE.md`"*; those with `paths:`
  (glob list) load on demand when Claude touches matching files. Skipped only when `project` is
  excluded from `--setting-sources` (and, before v2.1.211, on-demand rules loaded even then).
- **Why it matters HERE**: no kit ships `.claude/rules/`, no constitution mentions it, and no test
  reads it — yet a file placed there carries the **same authority as the constitution**. Two halves,
  both measured in the tree:
  - **Not a write hole.** `team-kits/dev-team/hooks/gate_write_scope.py:667`
    `_ENFORCEMENT_PATHS = (".claude", ".codex", ".agents/skills", ".github/hooks", ".github/agents")`
    is a **prefix**, so `.claude/rules/**` is refused like any other enforcement path. Good.
  - **It is an opportunity.** Path-scoped rules are the platform-native way to attach a constitution
    fragment to a subtree — e.g. `paths: ["project_memory/**"]` → "the kernel is the only writer,
    proposals go to `staging/<item-id>/`" — which today is a paragraph every role must carry in full
    context. That is a context-budget win on exactly the axis the kits' context-budget tests measure.
    Counter-argument to weigh at triage: a second instruction file is a second place for the same
    sentence, which is the defect `SR-0008` exists to prevent.
- **Recommendation**: **watch / consider.** ~20 min for the ledger note; ~2 h of design before any
  kit ships one, and it should not ship one unless the fragment moves *out* of the constitution
  rather than being duplicated. · **Status**: NEW

### 5. `CwdChanged` is the input H20 is missing — and five more hook events the earlier surveys enumerated but never itemized
- **Source**: https://code.claude.com/docs/en/hooks, seen 2026-09-25 — the reference now lists 33
  events. Beyond the ones this radar already tracks, these have never been itemized here:
  `CwdChanged`, `InstructionsLoaded`, `PostToolBatch`, `PermissionDenied`, `TeammateIdle`,
  `TaskCreated`/`TaskCompleted`. (`CwdChanged`, `FileChanged`, `ConfigChange`, `WorktreeCreate/Remove`
  appear once in `radar/2026-08-01-claude.md`, but only inside a list showing that `DirectoryAdded`
  was missing from the reference — none was ever assessed.)
- **Why `CwdChanged` matters HERE**: **H20** is this repo's documented over-refusal — *after a
  directory move the gate cannot compute, its position is unknown, and then **every** relative word
  of a write-capable stage is refused, even one pointing at a free path, for every caller.* On this
  host it is met first at `cd /c/…`, which Git Bash enters and no Windows process does (rc 0 → rc 2,
  while `cd "C:/…"` stays rc 0). A `CwdChanged` hook fires when the working directory changes and
  could persist the *resolved* directory where `_harness`/`gate_lead_write_scope` read it, turning
  "position unknown" into "position known" for exactly the between-calls case.
  **State the limit honestly**: it does **not** close H20. A hook record is a second source of truth
  and lags a `cd` that happens **inside the same line** as the write — and the within-line move is
  the case the gate's own remedy text already tells callers to split apart. So this shrinks a
  measured over-refusal; it does not buy a classification the gate cannot do.
  Worth a look from the same angle: **`InstructionsLoaded`** (fires when a `CLAUDE.md` or
  `.claude/rules/*.md` loads) would make item 3(3) and item 4 *observable* — a session that never
  loaded the constitution could be detected rather than reasoned about; and **`PermissionDenied`**,
  which can set `retry: true` in `hookSpecificOutput`, is the first event that lets a refusal carry a
  correction instead of only a sentence.
- **Also in the reference, for the source-format ledger**: hook handler `type` is now one of five —
  `command`, `http`, `mcp_tool`, `prompt`, **`agent`** (experimental) — and `timeout` defaults differ
  per type (600 s command/http/mcp_tool, 30 s prompt, 60 s agent). The kits register `command` hooks
  only and every entry names an explicit `timeout`, so nothing changes; but the *schema* the
  generator mirrors is wider than "command + timeout". A related fix this window: 2.1.273 — agent-type
  hooks on `PermissionRequest` **no longer run at all** (their answer could not allow or deny), which
  is a live example of the new types not being uniformly available.
- **Recommendation**: **watch → a spike item** for `CwdChanged`-against-H20 (measure in a clone: does
  a recorded cwd actually shrink the refusal set, and does it ever *widen* it?), ~3–4 h. Ledger note
  for the five-type schema, ~10 min. · **Status**: NEW

### 6. The 2.1.280 effort reset lands on `harness-lead`, the one role in this repo with no `effort:`
- **Source**: changelog 2.1.280 (Sep 22), verbatim: *"Changed an effort level saved before `/effort`
  became per-model to no longer apply to newly released models such as Opus 5.5; they start at their
  default until you pick a level"*; default efforts from the models overview (Opus 5.5 **`medium`**,
  Fable 5.1 `high`, Sonnet 5 `high`, Haiku 4.5 not supported) — both seen 2026-09-25.
- **Why it matters HERE — measured**: all **33** role pins across the three kits declare `effort:`
  explicitly (31 `high`, and `office-team/filing-reviewer` + `records-clerk` at `low`), so **no kit
  role is affected** — a declared value wins. But `.claude/agents/harness-lead.md` declares
  `model: opus` and **no `effort:` at all**, and so do neither more nor fewer: of this repo's own four
  roles, `claude-watcher`, `codex-watcher`, `harness-implementer` and `harness-verifier` all carry
  `effort: high`; the bound session role does not. On 2026-09-22 that role's model changed *and* any
  previously chosen effort stopped carrying — so the orchestrator of this repo's change circle now
  starts at Opus 5.5's default `medium`, quietly, on the same day.
  (Adjacent and already decided: `radar/2026-09-12` item 1 — `effort:` frontmatter was *ignored* on
  Opus 4.7/4.8/Fable 5 until 2.1.267. The two together mean the effort axis has been unreliable on
  the Claude side for most of September.)
- **Recommendation**: **adopt (tiny)** — a decision, not a finding: should `harness-lead` carry an
  explicit `effort:`? If the answer is "the orchestrator should be deliberate about its own effort",
  it is a one-line frontmatter add under an item, plus a test that every shipped role declaring
  `model:` also declares `effort:` (which would have caught this). Report-only from me. ~15 min.
  · **Status**: NEW

### 7. The scaffold tells the user `AGENTS.override.md` "takes precedence over the team constitution" — Claude Code never reads that file
- **Sources**: the memory doc's AGENTS.md section, verbatim: *"**Not read**: `AGENTS.local.md`,
  `AGENTS.override.md`, or anything under a `.agents/` directory"* (seen 2026-09-25) vs
  `team-kits/scaffold_team.sh:507` and `team-kits/scaffold_team.ps1:461`: *"Repository
  AGENTS.override.md takes precedence over the team constitution. It was backed up and left
  untouched; merge/remove it only after explicit user review, then rerun scaffolding."* (read
  2026-09-25) — and the install **aborts** (`exit 1`) on that sentence.
- **What it is**: `AGENTS.override.md` is a **Codex-side** concept in this repo —
  `gen_provider_artifacts.py:845` emits `"AGENTS.override.md" = "read"` into the Codex artifacts, and
  `kernel/report.py:2510` lists it among `SCAFFOLDED_ROOT_FILES`. On Claude Code it has no effect
  whatsoever, now explicitly so. The **abort** is defensible and has lineage (don't clobber a
  repo-owned file; `docs/holes/H88.md` is the case). The **sentence** is the defect: it asserts a
  load precedence the reference platform contradicts, to a user who is being blocked by it, and this
  repo's own house rule is that no comment may claim what the code does not build.
- **Recommendation**: **adopt — wording only.** Reword to what is true on both providers ("this repo
  carries an `AGENTS.override.md`; Codex reads it, Claude Code does not, and the installer will not
  overwrite a file it does not own — review and remove it, then rerun"). ~15 min under an item.
  · **Status**: NEW

---

## Also seen (no action, with the reason)

- **Recursive-`rm` behind a command substitution now prompts** — 2.1.281: *"Fixed a recursive `rm`
  whose target is only command-substitution output, such as `rm -rf "$(pwd)"`, running unprompted in
  auto and `--dangerously-skip-permissions` mode; it now asks even with a Bash allow rule, unless run
  with `CLAUDE_CODE_DISABLE_SUBSTITUTION_RM_PROMPT=1"`; plus 2.1.271 (*"flag removal at a shell
  variable + top-level dir, at a variable derived from the working dir, or at a backslash-only
  target"*) and 2.1.277/278 (name the flagged command, suggest a `${VAR:?}` guard, 2-minute prompt
  timeout then deny). Seen 2026-09-25. **Why it is only a pointer**: this is the *same family* as
  TSK-0019 / `_harness.command_line` (a command introduced by a command substitution) and as **H34**
  (a quoted span behind a flag spelling, removed as prose before anyone reads it) — external
  confirmation that the family is real and still being patched upstream, and it lands on the *exact*
  vectors `radar/2026-09-12` item 2 already proposed logging beside H22/H34/H19/H20. Add `rm -rf
  "$(pwd)"` and the backslash-only target to that not-yet-triaged list rather than opening a second
  one.
- **Bash permission rules with a mid-pattern `:*` were skipped in settings files** — 2.1.282:
  *"…while `--allowedTools` honored them; they now work from every source, with a startup warning on
  how they match."* Seen 2026-09-25. **Measured: no exposure** — a grep for `:*` across
  `.claude/settings.json` and all three kit `settings.json` files returns nothing; the kits carry no
  such rule. Recorded because a *rule that silently does not match* is the failure mode the kits'
  `deny: Agent(project-manager)` defense-in-depth (radar-0703-agent-permission-rules) relies on not
  having.
- **Plugins from npm are now fetched with `npm pack --ignore-scripts` and integrity-verified; install
  scripts no longer run** — 2.1.274. Seen 2026-09-25. Supply-chain hardening for the distribution
  channel this repo does *not* use (kits ship via `scaffold_team.sh/.ps1`), so no action; worth one
  line only because it is the first sign that the plugin channel is being treated as untrusted input,
  which matters if the kits ever become a marketplace plugin.
- **Server-side auto-mode classifier is now the default** for Claude API/Enterprise, Bedrock, Vertex,
  Foundry and gateways (2.1.278; opt out `CLAUDE_CODE_AUTO_MODE_SERVER=0`), and read-only/sandboxed
  shell commands now also wait for it (2.1.272). Seen 2026-09-25. The kits set no `defaultMode` and
  the gates are `PreToolUse`, which runs regardless — but a *second*, server-side classifier now sits
  beside this repo's own one, and the two can disagree. No action; noted because "whose
  classification wins" is a question this repo answers for itself today.
- **Headless/SDK hardening** — 2.1.281: `-p` and Agent SDK sessions that hit an internal error no
  longer hang with no result (report + exit 1); 2.1.282: `--input-format stream-json` and **scheduled
  cloud sessions** no longer fail on a plain-string earlier assistant message; 2.1.272: `-p --resume`
  reports background tasks a previous process left unfinished; 2.1.280: headless resume no longer
  restarts cost/usage at zero. Seen 2026-09-25. Directly relevant to `tools/radar_routine.py` and the
  four scheduled watcher runs: a hung headless run used to be indistinguishable from a silent week,
  and `--due` is what notices. Pure upside, no change.
- **`SessionStart` hooks were costing the prompt cache** — 2.1.280/282: a `SessionStart` hook that
  prints output made the first message lose the prompt cache; fixed. Seen 2026-09-25. Every kit
  registers a printing `SessionStart` hook (`session_status.py`), so every kit session has been
  paying this; nothing to change, it is fixed upstream — but it belongs in the CC-version-floor note
  beside the `effort:` floor (≥ 2.1.267) from `radar/2026-09-12` item 1: the floor is now **≥ 2.1.282**
  if you want both.
- **`TaskOutput` tool removed** — 2.1.277: *"Removed the deprecated TaskOutput tool; Claude reads a
  background task's output file with Read instead, and the `taskOutputMaxChars` setting and
  `TASK_MAX_OUTPUT_LENGTH` no longer have any effect."* Seen 2026-09-25. No kit registers or matches
  `TaskOutput`; noted only as the continuation of the task-tool retreat reported on 2026-09-12
  (item 3, still open): the built-in task surface keeps shrinking under `gate_todo_items.py`.
- **Not itemized** (no harness relevance, all seen 2026-09-25): `maxProseWidth`; project/local
  settings now ignoring OTel variables; `telemetry.resource_attributes` and the new
  `claude_code.managed_settings_resolved` OTel event; the `effort` attribute on the
  `claude_code.llm_request` span; Bedrock `assume_role` / `guardrail`; Claude-apps-gateway keys;
  Fable always shown in `/model`; ctrl+enter send-now; claude.ai skill/plugin sync
  (`syncClaudeAiSkills`); `/plugin install --marketplace`; memory-pressure warning; the 2.1.276
  gateway `advisor_20260301` hotfix; assorted prompt-cache and Desktop rendering fixes.

---

## Model lineup — ONE change, and it is item 1

Read 2026-09-25 against the three official sources (overview, pricing, deprecations) plus
anthropic.com.

| rung today | model | $/MTok in/out | cache read | default effort | status |
|---|---|---|---|---|---|
| `fable` (top) | Claude Fable 5.1 `claude-fable-5-1` | 10 / 50 | $0.25 (0.025x) | `high` | Active, ≥ 2027-09-01 |
| `opus` | **Claude Opus 5.5 `claude-opus-5-5`** (was Opus 5) | **4 / 20** | **$0.20 (0.05x)** | **`medium`** | Active, ≥ 2027-09-22 |
| `sonnet` | Claude Sonnet 5 `claude-sonnet-5` | 2 / 10 | $0.20 | `high` | Active, ≥ 2027-06-30 |
| (not a rung) | Claude Haiku 4.5 | 1 / 5 | $0.10 | not supported | Active, ≥ 2026-10-15 |

- **New top model**: Opus 5.5, GA 2026-09-22 — a point-bump *below* the Fable line, not a
  Mythos-class GA. Fable 5.1 remains the top of the lineup.
- **No new deprecation and no new retirement this window.** `claude-mythos-5-1` and `claude-mythos-5`
  are listed **Active** (both "not sooner than" 2027-09-01 / 2027-06-09) but remain **limited
  availability, invitation only, Project Glasswing** — pricing $10/$50, same as their Fable twins.
  Mythos 5.1 was already reported on 2026-09-04 (item 4); **not a new top model and not a GA**, so no
  rung question follows from it. `claude-mythos-preview` stays Deprecated with no retirement date.
  `claude-opus-4-1` remains Retired (2026-08-05, closed).
- **Price changes**: Opus 5.5 at $4/$20 is the only move, and it is *downward* on the rung the kits
  stand on. Sonnet 5's $2/$10 is still stated as standard, with the cancelled 2026-09-01 increase
  still footnoted — unchanged, already decided (`radar-0821-sonnet5-price-trigger`).
- **Effort**: no vocabulary change (`low|medium|high|xhigh|max`); the *defaults* differ per model and
  Opus 5.5's is `medium` — see item 6.
- **Standing calendar triggers — all three are now closed.** 2026-07-19 (Fable-5 subscription
  inclusion), 2026-08-31 (Sonnet-5 intro pricing, cancelled) and 2026-08-05 (Opus 4.1 shutdown,
  executed) are past and resolved on the live pages. **No live Claude-side model calendar trigger
  remains.** The only future date in `model_tiers.yaml` is `2026-11-21` (the OpenAI-side Sol promo),
  which is the codex-watcher's.
- **Tier-table proposals**: item 2, P-A / P-B / P-C.

## Community — nothing itemized, one honest note

The sweep (agent-harness architecture, orchestration patterns, verifier gates) returned the usual mix
of 2026 blog round-ups plus three arXiv preprints — *Harness Engineering: Anatomy, Architecture, and
Evolution of Coding Agents* (arxiv.org/pdf/2609.00006), *The Harness Effect: How Orchestration Design
Sets the Token Economics of Enterprise Agentic AI* (arxiv.org/pdf/2607.06906), *Harnessing Agent
Skills* (arxiv.org/pdf/2606.20631) — and a memo, *Harness Is a Gate, Not an Orchestrator*
(dev.to/zxpmail/harness-is-a-gate-not-an-orchestrator-an-engineering-memo-1m65); all seen 2026-09-25.
Per the house rule a reading is a **lead, not evidence**, and their content is either this harness's
existing design stated as a discovery ("the harness must be a gate first"; "planning root → workers →
verifier"; "coordinator-worker behind a spawn-depth setting" — cf. the still-open
`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` item) or unmeasured. **One is worth naming as a lead only**:
the token-economics paper is the nearest outside work to DEC-0095/DEC-0096's question — *what does
the orchestration shape cost per goal* — which item 2's P-C now needs an answer to. If a round ever
wants to justify a rung move with numbers rather than a price table, that is where to start reading;
it is not a candidate.

## Source-format scan (standing duty)

The source contract is **unbroken**, and this was the week to check it — three of the four things
that define it moved.

1. **`@import` semantics: unchanged, and now the documented bridge.** The memory doc's AGENTS.md
   table names "a `CLAUDE.md` that already imports `AGENTS.md`" as its own supported row. The kits'
   2-line shim is exactly that row. **No generator change.** (Item 3.)
2. **Instruction-source surface WIDENED** — `AGENTS.md` read natively, `.claude/rules/**.md` at
   `.claude/CLAUDE.md` priority, and a `pluginConfigs["agents-md@builtin"].instructionFiles` knob
   with four values including `managed-only`, settable only from user/managed/`--settings`. The
   generator produces no instruction files beyond the constitution, so **no generator change** — but
   `gen_provider_artifacts.py` and the CLAUDE.md shim now live in a world with more instruction
   sources than they enumerate, and `managed-only` can remove all of them. Ledger entry, items 3–4.
3. **Agent frontmatter: no removal, several fields the kits do not use.** The subagent reference
   (seen 2026-09-25) lists `name`, `description`, `tools`, `disallowedTools`, `model`,
   `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`,
   `omitClaudeMd`, `effort`, **`isolation: worktree`**, `color`, **`initialPrompt`**,
   `experimental.cacheTtl`. Every field the kits set (`name`, `description`, `model`, `effort`,
   `tools`) is present and unchanged — **no generator change**. Two are worth a second look in a
   later round and are *not* items today because neither is new this window and both need a
   measurement, not a reading: **`isolation: worktree`** (a subagent in its own git worktree is the
   platform-native form of this repo's "only one writes" rule and of the verifier's "read-only copy
   outside the repo" — but it is a *git* worktree, i.e. inside the repo's object store, which is not
   what the scratch-path rule asks for), and **`omitClaudeMd`** (a subagent that skips project
   instructions skips `AGENTS.md` too, per the memory doc — relevant to whether a specialist is
   supposed to have read the constitution at all).
4. **Hook-registration schema: WIDER than the kits use, in a way worth recording.** `type` is one of
   five (`command`, `http`, `mcp_tool`, `prompt`, `agent`), `timeout` defaults differ per type, and
   an `if:` filter in permission-rule syntax exists on tool events. The kits register `command` hooks
   with explicit `timeout`s only, which the reference still supports as the first-class form — **no
   generator change**, but the Codex mirror should not assume "command + timeout" is the whole
   schema. Also: event-type availability is **not** uniform (2.1.273 stopped `agent`-type hooks from
   running on `PermissionRequest`; `SessionStart`/`Setup` cannot use `mcp_tool`), which is the kind
   of asymmetry a generator that translates events one-for-one would get wrong.
5. **Effort vocabulary: unchanged** (`low|medium|high|xhigh|max`). What changed is *defaults* and
   *carry-over*, not the vocabulary — `model_tiers.yaml`'s `effort_field: effort` stands. (Item 6.)
6. **Model-name vocabulary: `fable` still accepted as a `model:` value**, alongside `sonnet`, `opus`,
   `haiku`, `inherit` and full ids such as `claude-opus-5-5`. The rung names the kits use are all
   valid frontmatter values. The *risk* is the opposite of a break: the names are **too** stable —
   they kept resolving while the model under them changed (item 1).

## Still-open prior items (pointers only — not re-surfaced)

From `radar/2026-09-12-claude-by-claude.md`, none yet in `decided.md`:
- `effort:` frontmatter ignored on Opus 4.7/4.8/Fable 5 until 2.1.267 → the CC-version-floor note.
  **Update**: the floor should now read **≥ 2.1.282** if the `SessionStart` prompt-cache fix is
  wanted too (see Also-seen), and item 6 is the second half of the same effort story.
- Anthropic's four permission/containment fixes as test vectors beside H19/H20/H22/H34.
  **Update**: add the 2.1.271/277/278/281 `rm` family (see Also-seen) to the same list.
- Task-tracking tools no longer offered by default except on older models.
  **Update**: 2.1.277 removed `TaskOutput` as well — the surface under `gate_todo_items.py` keeps
  shrinking.
- `claude plugin eval`; `maxEffortLevel` + per-model `modelSettings`; headless hook-firing hardened
  (FR-0063 pointer). All unchanged.

From `radar/2026-09-04-claude.md`, not yet in `decided.md`:
- `PreModelSwitch`/`PostModelSwitch` (still listed in the reference, unchanged) — and now doubly
  relevant: a deny-capable hook on a model change is the one mechanism that could have *seen* item 1.
- `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`; Fable 5.1 GA pin-resolution unmeasured; `/skill-doctor`.
- Stale Sonnet-5 comment — **confirmed resolved** in the tree (the Sonnet line and the watch date are
  correct today). The Claude **price anchor** on the same block is **not** — that is item 2, and it
  is a new finding on an old line, not a fourth report of the same one.

Longer-standing, unchanged: the depth-pin item; `gate_subagent_output` → `SubagentStop`; the
workspace-trust install note; the two report-only test hazards; FR-0047's open research.
