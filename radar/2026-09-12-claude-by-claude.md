# Radar — 2026-09-12 (claude-watcher, run by claude)

Scan window: Claude Code changelog **2.1.262 → 2.1.269** (Sep 6 → Sep 11, 2026; prior claude report
covered through 2.1.261). In this window 2.1.262 and 2.1.264 have no published entry and 2.1.263 was
"bug fixes and reliability improvements" only. Plus model lineup + community, same window.

`radar/decided.md` reviewed first — current through the **2026-09-05 codex triage** (all seven
`codex-0905-` rows have decided lines). The five items from **`radar/2026-09-04-claude.md`**
(PreModelSwitch/PostModelSwitch, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`, Fable 5.1 GA, the stale
Sonnet-5 comment, `/skill-doctor`) are **reported but not yet triaged** — they are carried below as
still-open pointers, not re-surfaced as NEW.

The highest-impact item this week is a **fix**, not a feature: `effort:` frontmatter — a field on
almost every kit role and on both watcher definitions — was being **silently ignored** on exactly
the Opus/Fable models the kits' tiers resolve to, until 2.1.267 (item 1). Two more land on existing
open threads: Anthropic's own permission classifier closed four holes that mirror this repo's own
hole-list (item 2), and the task-tracking tools that `gate_todo_items.py` gates are no longer offered
by default on the kits' likely models (item 3).

## Repo health

- **Not run this session.** `python tools/validate.py`, `python -m pytest tools/ -q`, and
  `ruff check .` could not execute: the Linux execution sandbox failed to mount every attempt
  (`Plan9 share "c" … not mounted`), so no Python/ruff was runnable. This is an **environment
  limitation of this run, not a code finding** — nothing observed suggests drift, and nothing was
  measured either way. The file tree was read-only-inspected via the file tools (used to ground
  items 1 and 3 below); no code, config, or `project_memory/` file was written.
- Prior baseline for reference (2026-09-04 report): `validate.py` all structural checks passed;
  `ruff` clean on pinned 0.15.20; a representative pytest subset green; the full `pytest tools/` run
  historically 35–39 min and not completing inside a session window.
- **Housekeeping:** nothing to append to `decided.md` — it is current through 2026-09-05.

---

## Highest-impact

### 1. `effort:` frontmatter was silently ignored on Opus 4.7 / Opus 4.8 / Fable 5 — FIXED 2.1.267
- **Source**: changelog https://code.claude.com/docs/en/changelog — 2.1.267 (Sep 9): *"Fixed
  `effort:` frontmatter on custom commands, skills, and subagents being ignored on models whose
  default effort is still pinned (Opus 4.7, Opus 4.8, Fable 5)."* · seen 2026-09-12
- **What it is**: for some prior span of releases, a subagent/skill/command that declared an
  `effort:` value ran at the model's own pinned default effort instead — the declared value was
  dropped — specifically on Opus 4.7, Opus 4.8, and Fable 5.
- **Why it helps this repo**: this is a measured-by-Anthropic bug on **exactly the fields and models
  the kits use.** `team-kits/model_tiers.yaml:67` defines `effort_field: effort` (vocabulary
  `low|medium|high|xhigh|max`), and the Claude tier rows pass through literally
  (`fable: fable`, `opus: opus`, `sonnet: sonnet`, lines 64–66) — so a role's `model: opus` /
  `model: fable` pin resolves straight onto the current-generation Opus/Fable models this fix names.
  `effort:` is set on essentially every kit role (all three teams' `project-manager.md`,
  `project-auditor.md`, the dev/research/office specialists) **and on both watcher definitions**
  (`.claude/agents/claude-watcher.md:17`, `codex-watcher.md`) and the harness roles
  (`harness-implementer.md`, `harness-verifier.md`). Consequence: from whenever the bug landed until
  2.1.267, any of those roles pinned to `opus`/`fable` ran at the model default effort regardless of
  its declared `effort:` — the verifier's `high`, a specialist's `low`, the watcher's `high`, all
  quietly no-ops on the affected models. Not a security hole; a **silent quality/cost drift** on the
  exact axis DEC-0076/DEC-0096 tune.
- **Recommendation**: **watch + client-version-floor note** (report-only per this role). No kit file
  changes — the fix is upstream. Worth (a) a CC-version-floor line, like FR-0060's BOM/CC-floor note,
  recording that `effort:` pins are only honored ≥ 2.1.267 on Opus 4.7/4.8/Fable 5; (b) a one-time
  check, when a session with a real client is open, that a role actually runs at its declared effort
  (`/status` or telemetry) now that the fix is out. ~15 min. · **Status**: NEW

### 2. Anthropic's own Bash/permission classifier closed FOUR path/command holes this window — direct parallels to this repo's H19/H20/H22/H34
- **Source**: changelog https://code.claude.com/docs/en/changelog · seen 2026-09-12 —
  - 2.1.269 (Sep 11): *"Fixed `Edit()` deny rules and the write-path check not applying to the file a
    Bash `tee` command writes; a `Bash(tee:*)` allow rule no longer covers destinations outside the
    working directories."*
  - 2.1.268 (Sep 10): *"Fixed a case where a Read or Edit deny rule did not apply when an `env -C`,
    `eval` or similar command the permission checker cannot analyze was on the same line"*; and
    *"Fixed deny and ask permission rules on symlinked directories (`/etc`, `/tmp`, `/var` on macOS;
    `/bin` on Linux) not applying when a path was given by its real location…"*
  - 2.1.267 (Sep 9) / 2.1.265 (Sep 8): *"…a marketplace entry path containing a backslash could
    bypass the containment check…"* / *"…a plugin path containing a backslash bypassing the symlink
    containment check on macOS and Linux."*
- **What it is**: Anthropic's own permission/containment classifier had four distinct
  path-spelling / unanalyzable-command bypasses, all now fixed: a write verb the checker doesn't
  treat as a write (`tee`), a command the checker can't analyze on the line (`env -C`, `eval`),
  real-path-vs-symlink spelling, and backslash-escaped containment.
- **Why it helps this repo**: these are the **same vector families** `gate_commit_evidence`
  (`_moves_the_tree_first`) and `gate_lead_write_scope` / `_harness.ProtectedArea` classify against,
  and the repo's own hole-list already names each shape: **H22** (a write the classification reads as
  a read), **H34** (a quoted span behind a flag removed as prose before anyone reads it), **H19**
  (an ancestor-path candidate), **H20** (a directory move the gate can't compute). `tee` is a live
  H22-shaped write vector; `env -C`/`eval` is the "line the checker cannot analyze" case in Anthropic's
  own words; the symlink real-path and backslash cases are path-spelling variants of H19/H20. This is
  the strongest **external confirmation to date** that the family this repo tracks is real and
  actively exploited-then-patched upstream. `FR-0061` ("measure our classifier both directions in a
  clone; an under-read → the hole list with its chain") is the lineage — noted closed/archived in the
  2026-09-04 report, so nothing auto-follows.
- **Recommendation**: **adopt as test vectors / watch** (report-only). Feed `tee`, `env -C`, `eval`,
  symlink-real-path spelling, and backslash containment into `docs/POST_V2_WISHLIST.md` as explicit
  named cases beside H22/H34/H19/H20, so a future classifier round (or a reopened FR-0061) measures
  them both directions rather than re-deriving them. ~30 min to log. · **Status**: NEW

### 3. Task-tracking tools (TaskCreate/Get/Update/List, TodoWrite) no longer offered by default except on older models — 2.1.268
- **Source**: changelog https://code.claude.com/docs/en/changelog — 2.1.268 (Sep 10): *"Changed the
  task-tracking tools (TaskCreate/Get/Update/List, TodoWrite) to be offered only on Claude 3.x, Opus
  4.0–4.7, Sonnet 4.0–4.6, Haiku 4.5; set `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` elsewhere."* · seen
  2026-09-12
- **What it is**: the built-in task/todo tools are now presented **only** on the listed model
  families. The list **excludes** Opus 4.8, Fable 5 / 5.1, Opus 5, and Sonnet 5 — i.e. the
  current-generation models the kits' `opus`/`fable`/`sonnet` tiers most plausibly resolve to.
- **Why it helps this repo**: `gate_todo_items.py` matches `TodoWrite` and refuses a task list with
  more than one item lacking an item-id. If `TodoWrite` isn't **offered** to a role (because its
  pinned model isn't on the list and `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` isn't set), the gate has
  nothing to fire on — it is inert, not because it fails but because its subject tool is absent. Not
  a hole (fewer tools = fewer vectors), but it **changes a standing assumption**: a gate written to
  constrain `TodoWrite` no longer governs anything on the models the harness is most likely running,
  and any harness flow that *relies* on the session task list would also lose it. (This is distinct
  from the `TaskCreate/TaskUpdate` MCP tools available in Cowork, which are a separate surface.)
- **Recommendation**: **watch / confirm** (report-only). When a real client is open, measure whether
  `TodoWrite` is offered under the kits' pinned models; decide deliberately whether the harness wants
  `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` (to keep `gate_todo_items` meaningful and the tool available) or
  is content for the gate to be a no-op there. Source-format: this is a model-gated **tool
  availability** change, not a frontmatter/settings-schema change — no generator impact, but worth a
  line in the ledger. ~20 min check. · **Status**: NEW

---

## Also seen (medium / watch-only)

- **`claude plugin eval` — scored, reproducible plugin eval suite (JSON + HTML report)** · changelog
  2.1.269 (Sep 11) · seen 2026-09-12. *"Run a plugin's eval suite against Claude Code and get scored,
  reproducible results."* This repo is the **source of the team-kits (plugins)**; an eval suite is
  the missing objective measure of a kit's role-**triggering** and tool-**permission** behavior — the
  same "does the description trigger on relevant tasks and not others, are allowed/denied tools
  honored" checks the community subagent-eval playbook describes and that the harness today asserts
  only through `tools/test_role_contracts.py`-style Python tests. **Recommendation**: watch/try — run
  once against one kit to see what it scores; complements, doesn't replace, the `tools/` suite.
  ~1h spike. Status: NEW.
- **`maxEffortLevel` setting + per-model `modelSettings`** · changelog 2.1.267 (Sep 9) · seen
  2026-09-12. Caps effort on every provider (users may still pick lower). Same **effort axis**
  `model_tiers.yaml`'s `effort_field` tracks, and a Claude-side counterpart to the still-open
  codex-watcher effort-ceiling item (`max` vs `ultra`). No kit sets it. **Recommendation**: watch —
  source-format ledger note; relevant only if a round ever wants a harness-wide effort ceiling.
  ~5 min. Status: NEW.
- **Headless hook-firing hardened** · 2.1.268: *"Fixed PermissionRequest hooks not firing in
  `--print` mode"* and *"Fixed policy-helper warnings not printing on headless (`-p`) runs"*; 2.1.267:
  resuming a >5 MB session no longer drops parallel tool calls and their hook output (beside the
  2.1.261 resume-hook-loss fix) · seen 2026-09-12. `FR-0063` asks whether gates fire **at all** under
  headless/restricted invocation — and this repo's radar and scheduled runs *are* headless. The four
  gates are `PreToolUse`, not `PermissionRequest`, so the PermissionRequest fix doesn't touch them
  directly, but it confirms headless hook-firing has been actively buggy and is being hardened.
  **Recommendation**: watch / no-action; pointer for `FR-0063`. Status: NEW (pointer).

## Also seen (no-action)

- **`cd` now persists across turns in non-interactive `-p` / SDK / cloud sessions** (2.1.265). A
  subtle adjacency to `gate_commit_evidence`'s directory-move handling (H20): the gate classifies a
  line's *own* `cd`, so a cwd that now carries across *turns* doesn't change per-line classification —
  noted so a future round doesn't mistake the two. Watch only.
- **Windows: Read/Write/Edit refusing every file under an AppContainer/restricted-token sandbox —
  FIXED** (2.1.265). This repo runs on Windows; pure upside, no action.
- **`.claude` folder permission wording clarified** (2.1.265) — says it allows editing files in the
  project's `.claude` (or `~/.claude`) for the session. The repo protects `.claude/` wholesale via
  `ProtectedArea`; wording-only, no change.
- **Artifact tool now treats an artifact someone else wrote as untrusted and flags embedded
  instructions** (2.1.265) — general prompt-injection hardening, aligns with this repo's
  instruction-source-boundary stance; no kit surface.
- **`Bash(tee:*)` / `env -C` etc.** already itemized under item 2.
- Not itemized (no harness relevance): the large VS Code changelog (agent map, Hooks/Permission-rules
  dialogs, Focus view, accessibility), Claude Tag / Slack items, Claude Code on the web routine and
  cloud-environment items, gateway `pricing:`/`gatewayInternalNetworks`/CIDR-warning plumbing, OTEL
  `vcs.*` attributes, `--output-style`/`/focus`/spinner-tip UX, `bashEditDiffEnabled` diff-in-result
  (cosmetic here), `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` (the harness forbids parallel
  writers), `--system-prompt-snapshot off`, self-hosted-runner and Bedrock/Vertex/Foundry fixes, and
  the 2.1.266 gateway `CLAUDE_CODE_USE_GATEWAY` regression/rollback.

---

## Model lineup — no change

- **No new model and no new deprecation since Fable 5.1 (2026-09-01).** The deprecations table is
  **unchanged** from the 2026-09-04 report: `claude-fable-5-1`, `claude-fable-5`, `claude-opus-5`,
  `claude-opus-4-8/4-7/4-6/4-5`, `claude-sonnet-5/4-6/4-5`, `claude-haiku-4-5` all **Active**; Opus
  4.1 retired 2026-08-05 (closed). Source:
  https://platform.claude.com/docs/en/about-claude/model-deprecations, seen 2026-09-12.
- **No tier-table (`tiers:` values) change proposed.** The `fable`/`opus`/`sonnet` rungs are correct.
- **Stale Sonnet-5 comment (2026-09-04 item 5) — appears ALREADY resolved in the working tree.** The
  dead `2026-08-31 Sonnet-5 intro pricing ends` watch date and the `$3/$15 (intro $2/$10…)` line the
  last three claude reports flagged are **not** in the current `team-kits/model_tiers.yaml`: lines
  37–44 now read *"Sonnet 5 $2/$10 standard (the 2026-08-31 increase was cancelled…)"* and the only
  watch date is `2026-11-21` (future, valid), guarded by
  `test_no_watch_date_in_the_tiers_table_lies_in_the_past`. This is the 2026-09-05 anchor rework the
  codex report noted. **Recommendation**: confirm at triage and mark the 09-04 item **resolved**
  rather than re-flag it. (Not run this session: the guarding test — sandbox down.)
- Standing calendar triggers: Fable-5 subscription-inclusion (2026-07-19), Sonnet-5 intro pricing
  (2026-08-31) and Opus 4.1 shutdown (2026-08-05) are all past and resolved; no live model calendar
  trigger remains on the Claude side this week.

## Community — nothing itemized

Searches on subagent orchestration / eval / plugin-eval returned generic 2026 blog round-ups
(promptessor, thepromptshelf, developersdigest, totalum, ofox, nimbalyst; seen 2026-09-12). Per this
repo's house rule (a blog reading is a lead, not evidence) none is itemized — and their headline
advice ("use a separate verifier instead of the implementer approving its own work," "cap nesting
depth," "evaluate a subagent like a reusable tool") is already the harness's three-role design and
`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` concern. The one **official** primitive that operationalizes
"evaluate a subagent like a tool" is `claude plugin eval` (medium-list above), which is where that
theme is actionable.

## Source-format scan (standing duty)

- **Effort axis touched twice, no vocabulary change.** Item 1 (`effort:` honored again ≥ 2.1.267 on
  Opus 4.7/4.8/Fable 5) and the medium `maxEffortLevel`/`modelSettings` addition both concern the
  effort contract `model_tiers.yaml:67` (`effort_field: effort`) depends on. The vocabulary is
  unchanged (`low|medium|high|xhigh|max`); the generator/overlay need no edit, but the ledger should
  record that a per-model effort **cap** now exists Claude-side (the Codex side already carries the
  `max` vs `ultra` ceiling contradiction).
- **Item 3** (task-tool model-gating) is a **tool-availability** change, not a frontmatter/settings
  field — no `gen_provider_artifacts.py` impact; a Codex-mirror note would read "no parity concern,
  this is a Claude-platform tool-offering rule."
- No frontmatter-field change, no `@import`-semantics change, no hook-registration schema change
  this window. (`PreModelSwitch`/`PostModelSwitch`, last week's new hook events, are unchanged and
  remain pending triage.)

## Still-open prior items (pointers only — not re-surfaced)

Pending triage from `radar/2026-09-04-claude.md` (not yet in `decided.md`):
- `PreModelSwitch` / `PostModelSwitch` deny-capable hook on model changes — the concrete mechanism
  for `FR-0047`'s open half. Unchanged this week.
- `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` — opt-in env var that overrides every subagent's pinned model,
  no gate sees it. Unchanged.
- Fable 5.1 GA — literal-`fable` pin resolution for a plain (non-gateway) session still unmeasured.
- `/skill-doctor` — skill-hygiene tool, watch/try. (Superseded in usefulness by `claude plugin eval`
  above for kit measurement.)
- Stale Sonnet-5 comment (item 5) — **appears resolved in the working tree**, see Model lineup above.

Longer-standing (from earlier reports), unchanged:
- Depth-pin item (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` + no-`Agent`-in-specialist-`tools:` check).
- `gate_subagent_output` → `SubagentStop` refactor.
- Workspace-trust install note.
- Two report-only test hazards (`test_gates.py` destructive `sed -i`; the mis-calibrated 5× ratio
  bound test).
- `FR-0047` open research: `--fallback-model` and the platform safety-redirect classifier (the model
  `:`-pin structural test and BOM tripwire closed 2026-09-02).
