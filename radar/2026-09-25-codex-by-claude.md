# Radar — 2026-09-25 (codex-watcher, run by claude)

Scan window: **2026-09-06 → 2026-09-25** — everything since this watcher's last report
(`radar/2026-09-06-codex.md`). Codex CLI **0.153.4 → 0.157.0**, the official hooks reference, the
agent-configuration pages (subagents / agents-md / config-advanced), the OpenAI model + deprecation
pages, `openai/codex` issues and releases, and agents.md.

`radar/decided.md` read first — current through the **2026-09-05 codex triage**; no slug below
repeats one of its rows. `radar/2026-09-06-codex.md` read: its three items were pointers, two of
which are still open and are carried at the bottom rather than re-surfaced. Today's sibling report
`radar/2026-09-25-claude-by-claude.md` skimmed: its item 7 (the scaffold's `AGENTS.override.md`
sentence) is the cross-ecosystem finding of this week and lands **there**, not here — this report
does not restate it. Repo health belongs to the claude-watcher (README) and was not re-run here.

**The week in one sentence: the OpenAI lineup moved a whole generation, and both Codex rungs in
`team-kits/model_tiers.yaml` were left behind on models the CLI itself now offers to migrate away
from.** Item 1 is that, with the tier-change proposal. Item 2 is the named unlock this watcher has
been standing watch for — `additionalContext` on `PreToolUse` — which landed, and reaches less of
the kits than it looks like. Item 3 is an enforcement item: Codex worktree sessions went
default-on, and project-local hooks do not load in an untrusted project.

**One limit, stated up front and unchanged since 2026-09-05**: there is no Codex CLI on this host,
so nothing below is measured against a running CLI. Every claim is either a quote from an official
page, a read of a file in this repo, or explicitly marked as a reasoned consequence with the
measurement it needs.

---

## Highest impact

### 1. GPT-6 Sol and GPT-6 Luna went GA on 2026-09-22 — both Codex rungs of `model_tiers.yaml` now point at a previous generation the CLI prompts users off. TIER-CHANGE PROPOSAL
- **Sources** (all seen 2026-09-25):
  - https://developers.openai.com/api/docs/models/gpt-6-sol — `gpt-6-sol`, **$2 in / $10 out per
    1M, cached input $0.2**, 1,050,000 context (922,000 max input), 128,000 max output; reasoning
    effort `none`, `low`, `medium` (default), `high`, `xhigh`, `max`.
  - https://developers.openai.com/api/docs/models/gpt-6-luna — `gpt-6-luna`, **$0.1 in / $0.5 out,
    cached $0.01**, same 1,050,000 / 922,000 / 128,000 window, same effort values, positioned as
    *"our most efficient model for focused, high-volume tasks"*.
  - https://developers.openai.com/api/docs/models — the GPT-6 family cards are exactly **three**:
    Astra (*"Our most capable model, built for the hardest end-to-end work"*), Sol (*"Built to power
    complex coding and agentic workflows"*), Luna. **No `gpt-6-terra` exists.**
  - https://developers.openai.com/api/docs/models/gpt-6-astra — `gpt-6-astra` unchanged at **$10 /
    $50, cached $1**; effort `low … max`.
  - https://learn.chatgpt.com/docs/models — verbatim: *"GPT-5.6 Sol, GPT-5.6 Terra, and GPT-5.6
    Luna remain available during the rollout."* They have **no model card of their own on that
    page** any more; the cards are Astra/Sol/Luna plus a "legacy models still available" line for
    5.5/5.4.
  - https://learn.chatgpt.com/docs/changelog — **0.157.0 (2026-09-25)**: *"Added GPT-6 Sol and Luna,
    including Amazon Bedrock support and **migration prompts for older models**."* · **0.156.1
    (2026-09-23)**: *"Choose GPT-6 Sol or GPT-6 Luna from the model picker. The rate-limit switch
    prompt now recommends GPT-6 Luna."*
  - https://developers.openai.com/api/docs/models/gpt-5.6-sol — still live, **$4 / $20, cached
    $0.4**, and still carries *"promotional pricing is available at least through November 21,
    2026"*. Not deprecated; the deprecations page
    (https://developers.openai.com/api/docs/deprecations) lists the 5.6 family only as the
    **replacement target** of older retirements, never as a retiree.
- **What it is**: a full generation step on the two rungs below the top. Astra stays where it is;
  the mid and small rungs of the vendor's own vocabulary are now `gpt-6-sol` and `gpt-6-luna`, at
  half or less of what the 5.6 models cost.
- **Why it matters HERE — measured against the file, not assumed**: `team-kits/model_tiers.yaml`
  `tiers.codex` reads today:
  `fable: gpt-6-astra` · `opus: gpt-5.6-sol` · `sonnet: gpt-5.6-terra`.
  Unlike the Claude rows, these are **hard model ids, not pass-through names** — so nothing moved by
  itself (the opposite failure mode from the sibling report's item 1) and nothing is broken right
  now: both ids still resolve. What changed is that the file now pins **two models whose only
  documented availability statement is "during the rollout"**, on a CLI that shows a migration
  prompt for them, while `gpt-6-sol` costs half of `gpt-5.6-sol` and `gpt-6-luna` costs 1/20th of
  `gpt-5.6-terra` on input. Every Codex-side project of every kit resolves its `lead`/`worker` pins
  through these two rows (`gen_provider_artifacts.provider_neutral_model` →
  `gen_codex_agent`/`gen_codex_config`, which always emit an explicit `model =` line), so this is
  the whole Codex ladder.
- **PROPOSAL (I never edit the table — this is for the user's decision)**:

  | rung | today | proposed | evidence |
  |---|---|---|---|
  | `fable` (top) | `gpt-6-astra` | **unchanged** | still the top card, $10/$50 unchanged |
  | `opus` | `gpt-5.6-sol` ($4/$20 promo) | **`gpt-6-sol`** ($2/$10) | newer generation, same position in the vendor's own three-card lineup, half the price, CLI picker default-eligible |
  | `sonnet` | `gpt-5.6-terra` ($2/$12) | **`gpt-6-luna`** ($0.1/$0.5) | the third and smallest card of the GPT-6 family; `gpt-6-terra` does not exist, so the GPT-6 family maps onto DEC-0076's three rungs exactly |

  Two riders that come with it and are easy to miss:
  - **A sentence in the file's own header becomes false.** The three-rung paragraph says: *"There is
    no `light` alias and no haiku or **luna** row"*. That was written when Luna was the fourth rung
    of the **5.6** family (`codex-0905-astra-ga` records the four-rung finding). Under this proposal
    the `sonnet` row **is** luna, and the sentence has to be reworded — otherwise the file forbids
    in prose what it does in the table. This is the `BUG-0092` shape again (a comment outliving the
    fact), one level down.
  - **The price anchors and the watch date.** The anchor block still reads `gpt-5.6-sol $4/$20
    promotional, $5/$30 standard . gpt-5.6-terra $2/$12 (since 2026-07-30)`, read 2026-09-05, and
    the one live watch date — `2026-11-21 gpt-5.6-sol promotional pricing` — is *about a model this
    proposal would stop naming*. Both still verify against the vendor pages today, so neither is
    a lie yet; adopting the proposal makes both dead lines in the same commit. (The sibling report's
    item 2 P-A proposes the twin correction for the Claude half plus a **price-side** read-date test
    — `test_no_watch_date_in_the_tiers_table_lies_in_the_past` measures dates only. If that test is
    built, it should cover both providers in one go.)
- **Recommendation**: **adopt — capture an item and put the proposal to the user.** The edit itself
  is two lines plus the header rewording plus the anchor block; ~1 h under an item, and it needs the
  user's answer first because re-tiering every Codex project on the next restamp is exactly what the
  MAINTENANCE header reserves for a user-approved proposal. · **Status**: NEW

### 2. `additionalContext` on `PreToolUse` landed and issue #19385 is CLOSED — the named unlock of this watcher's standing watch
- **Sources** (all seen 2026-09-25):
  - https://learn.chatgpt.com/docs/hooks — the events documented as carrying `additionalContext` are
    `SessionStart`, `PreCompact`, `PostCompact`, `UserPromptSubmit`, `SubagentStart`, `SubagentStop`,
    `Stop`, `PreToolUse`, `PostToolUse`; for `PreToolUse` verbatim: *"To add model-visible context
    without blocking, return `hookSpecificOutput.additionalContext`"*; the shape shown is the
    **nested** one, e.g. `{"hookSpecificOutput": {"hookEventName": "SessionStart",
    "additionalContext": "…"}}`.
  - https://github.com/openai/codex/issues/19385 — *"Support additionalContext in PreToolUse hooks
    or clarify Claude-style hook parity"* — **Closed**. Its complaint was a hard error:
    *"PreToolUse hook returned unsupported additionalContext"*.
  - Prior state of this exact question in this repo: `radar/2026-09-05-codex.md` "Also seen" —
    *"`additionalContext` support is real but event-scoped, not yet the general primitive"*, with
    #19385 recorded as unresolved.
- **What it is**: the field the kits already emit, in the nesting the kits already use, is now
  documented on nine Codex events including the two the kits emit it on.
- **Why it matters HERE — and the 2026-09-05 report got one fact wrong, which this corrects**: that
  report said *"No kit today emits `additionalContext` on either provider"*. Measured 2026-09-25
  against the tree, **all three kits emit it from four hooks**:
  `session_status.py:563`, `kit_trust_state.py:162` (both `SessionStart`), `gate_dispatch.py:480`
  (`PreToolUse`, the dispatch reflection checkpoint) and `gate_approval.py:253` (`PostToolUse`, the
  approval record for the model). So the question was never hypothetical.
  What the unlock actually reaches, traced through `gen_provider_artifacts.py`:
  - **SessionStart — reaches Codex and is now documented as supported.** `kit_trust_state` and
    `session_status` are in `CODEX_EVENTS`, matcher-free, and `SessionStart` is on the supported
    list. This is the kits' whole Codex-side briefing channel and it is confirmed, not assumed.
  - **The `PreToolUse` and `PostToolUse` channels do NOT benefit**, and the reason is the **matcher,
    not the field**: `gate_dispatch`'s checkpoint is registered on `Agent|Task` and `gate_approval`'s
    record on `AskUserQuestion`; all three tool names are in `CODEX_UNSUPPORTED_TOOLS`, so
    `codex_matchers` drops those registrations before the output field is ever relevant. The unlock
    does not change that, and a future round should not read it as if it did.
  - **What it does unlock**: a Codex `PreToolUse` gate on a tool Codex *does* have (`Bash`,
    `apply_patch` — i.e. every shell and write gate the kits ship) may now return a **correction**
    alongside allowing, instead of only refusing with exit 2. That is the nearest Codex analogue of
    the `PermissionDenied` + `retry: true` idea the sibling report raises for the Claude side
    (item 5), and it is the first time the two providers have the same primitive there.
- **Recommendation**: **adopt (small)** — one ledger line, plus one sentence in
  `gen_provider_artifacts.py`'s header beside the existing `Interrupt` paragraph recording that the
  field is supported and that the two unreached channels are blocked by `CODEX_UNSUPPORTED_TOOLS`
  and nothing else. Any actual use of the correction channel is its own design round. ~30 min for
  the record; the standing watch item itself can be closed. · **Status**: NEW

### 3. Codex worktree sessions are default-on since 0.156.0 — and project-local hooks do not load in an untrusted project, so a worktree session runs with the kit's entire gate bundle absent
- **Sources** (all seen 2026-09-25):
  - https://learn.chatgpt.com/docs/changelog — **0.156.0 (2026-09-22)**: *"Filter tasks by status
    and create worktree sessions from the agent command center; **worktree support is now enabled by
    default**."*
  - https://learn.chatgpt.com/docs/config-file/config-advanced — verbatim: *"Codex loads
    project-scoped config files only when the project is trusted. If the project is untrusted, Codex
    ignores project `.codex/` layers, including `.codex/config.toml`, project-local hooks, and
    project-local rules."* And on root detection: *"Codex discovers project configuration (for
    example, `.codex/` layers and `AGENTS.md`) by walking up from the working directory until it
    reaches a project root"*, where *"Codex treats a directory containing `.git` as the project
    root"* (configurable via `project_root_markers`).
  - https://learn.chatgpt.com/docs/hooks — *"Project-local hooks load only when the project
    `.codex/` layer is trusted. In untrusted projects, Codex still loads user and system hooks from
    their own active config layers."*
- **The chain, stated as the reasoned consequence it is**: a git worktree is a directory that
  contains a `.git` (a *file*, but the doc's wording is "a directory containing `.git`"), so it is
  its own project root at a **new path**. Trust is a property of that project layer. A worktree
  created from the command center is therefore an untrusted project on first entry → **every**
  `.codex/hooks.json` registration the kit generated is ignored, i.e. all of `gate_write_scope`,
  `gate_git`, `gate_dispatch`, `guard_harness_selfmod` and the rest, while `AGENTS.md` (an
  instruction file, not a project `.codex/` layer) is a separate question. And nothing in the kit
  can report it, because reporting requires a hook: `kit_trust_state.py`'s own header says *"THE
  EVIDENCE THIS HOOK PROVIDES IS ITS OWN EXECUTION."*
- **What this is NOT — one check that came out well and bounds the damage.** There is **no false
  trust**: `.claude/kit_state.json` is gitignored (`team-kits/dev-team/templates/repo/.gitignore`,
  with exactly this reasoning: *"Committing it would let a clone inherit `state: active` with a
  matching hash and read as trusted before a single hook ran in it"*), and a worktree does not carry
  ignored files, so the worktree has no record at all — `kit_trust_state`'s
  `no kit_state.json -> nothing written` rule holds and `doctor` cannot claim `hook_trust`. The
  exposure is **absent enforcement**, not a lie about it. The kernel also already knows the concept:
  a lease carries a worktree (`docs/holes/H156.md`, second residual class).
- **Why it matters HERE**: this is the same question as **FR-0063** (`claude --restricted` ignoring
  user+project settings) on the other provider — *does the harness behave when its enforcement half
  is missing?* — and it is now reachable from a **default-on** UI affordance rather than a flag
  somebody has to type. The two honest outcomes: the user grants trust at the prompt (gates load; the
  kit's bundle-hash review is now attached to a second path record, which nothing in the kit tracks),
  or the user does not (a full session with no gates, silently).
- **Measurement it needs**, named so a round can do it in one sitting: install a kit in a throwaway
  repo, `git worktree add ../wt`, start `codex` in `../wt`, and read (a) whether a trust prompt
  appears, (b) whether any `.codex/hooks.json` hook runs before trust, (c) whether granting trust in
  the worktree also re-validates the bundle hash. ~1 h on a host with Codex CLI — which this host is
  not.
- **Recommendation**: **adopt — capture beside FR-0063** as its Codex half; ~30 min to write the
  item and the hole entry with this chain, the measurement when a host has the CLI. · **Status**: NEW

---

## Medium

### 4. Two generator-level facts about the Codex hook contract that no kit file knows: the ~2500-token context ceiling, and that `timeout` has a per-event maximum
- **Sources** (both https://learn.chatgpt.com/docs/hooks, seen 2026-09-25):
  - *"By default, Codex limits each model-visible hook-output message to roughly 2,500 tokens. If a
    hook returns more, Codex saves the full text under
    `<temp_dir>/hook_outputs/<session_id>/<uuid>.txt` and gives the model a head-and-tail preview
    with the saved-file path."* The knob is the handler field `additionalContextLimit`.
  - *"`SessionEnd` and `Interrupt` use `1` second by default and support up to `3` seconds."*
    (General default is 600 s.)
- **Why it matters HERE — both measured against the tree**:
  - **The ceiling lands on the kits' session briefing.** `session_status.py` assembles its whole
    `additionalContext` from 22 `parts.append(...)` sites and applies **no cap** (`grep` for
    `CAP|budget|truncat` in that file: nothing). A crude static upper bound — the literal text at
    those 22 sites alone — is ~9.6 KB of source, which no single session reaches, but it puts the
    2,500-token (~10 KB) Codex threshold inside the same order of magnitude, and **nothing in this
    repo measures where a real session lands**. On Codex a long brief is silently replaced by a
    head-and-tail preview plus a file path, i.e. the PM is briefed from a truncation it is not told
    about. The knob that would fix it (`additionalContextLimit`) is a Codex-only **handler** field —
    see item 5, the source format cannot express it.
  - **`timeout` is copied verbatim with no ceiling.** `gen_provider_artifacts.py:709-711` writes
    `entry["timeout"] = hook["timeout"]` straight from the Claude registration. Today there is **no
    exposure**: `CODEX_EVENTS` contains neither `SessionEnd` nor `Interrupt`, the only two capped
    events. But the generator holds no notion of a per-event maximum, so the day `SessionEnd` is
    added (a plausible move — it is a real Codex event and the kits have a natural use for it) a
    60-second Claude timeout is emitted into a field whose documented maximum is 3. This is the
    enumeration-vs-definition shape the house rules are about: the safety is currently an unwritten
    agreement between two tuples, exactly as the `Notification`/`CODEX_EVENTS` comment in that same
    file describes for matchers.
- **Recommendation**: **adopt (small)** — (a) measure a real `session_status` brief's size and, if it
  is anywhere near the ceiling, decide between a cap in the hook and an emitted
  `additionalContextLimit`; (b) a per-event timeout ceiling table in the generator plus a test that
  an emitted `timeout` never exceeds its event's documented maximum, red today if `SessionEnd` were
  added. ~2 h together. · **Status**: NEW

### 5. SOURCE-FORMAT DIVERGENCE (standing duty): the `codex:` overlay reaches per-agent TOML only, and the count of Codex-only HOOK-REGISTRATION capabilities it cannot express is now five
- **Sources**: https://learn.chatgpt.com/docs/hooks (seen 2026-09-25) for the handler/registration
  fields; `team-kits/gen_provider_artifacts.py:731-745` (`CODEX_OVERLAY_RESERVED`, `codex_overlay`)
  and its own comment — *"The sanctioned divergence valve … merged into the generated TOML here"* —
  read 2026-09-25; the trip-wire criteria verbatim from `HARNESS_LOG.md` (2026-07-14 entry):
  *"TRIP-WIRE for revisiting a full neutral source format (standing watcher duty): overlays
  accumulate beyond scattered scalars, a third provider needs artifacts, or the .md-agent/@import
  contract breaks."*
- **The inventory, as of today**, of Codex hook-layer capabilities a kit source has **no vehicle
  for** — the overlay reaches per-agent TOML fields, never a `settings.json`-level registration:
  1. the `Interrupt` **event** (already reported 2026-09-05, decided as `codex-0905-interrupt-event`);
  2. `async: true` — run a command hook in the background while Codex continues. The kits ship an
     obvious candidate: `notify_agent_events.py`, a pure audit hook whose latency is on the turn
     today;
  3. `additionalContextLimit` — item 4;
  4. `statusMessage` — UI text shown while a hook runs (a refusal that says *why* it is thinking);
  5. the `mcp_tool` **handler type** (`server`/`tool`/`input` with `${field.nested}` expansion) —
     a hook that calls an MCP tool without shelling out.
  (Dating, honestly: a third-party write-up dates `async` + `mcp_tool` to 0.148.0 / 2026-08-17 and
  `additionalContextLimit` to 0.145.0 / 2026-07-21 — a **lead**, not evidence. The docs are the
  evidence that they exist today; whether they landed since the last scan or were merely never
  itemized by this watcher is not established, and it does not change the count.)
- **Why it matters HERE, and why I am not calling the trip-wire**: the criteria as written do not
  fire. These are **not** accumulating overlays — the valve does not reach this layer *at all*, so
  nothing is piling up in it; there is no third provider; and the `@import` contract holds (the
  sibling report's item 3 re-confirmed it this week). Reporting "trip-wire fired" here would be a
  claim the record does not support. What the record *does* support is that the criteria have a
  blind spot: a capability class the valve cannot express produces **silence**, not accumulation, so
  the trip-wire can never be reached by the thing that is actually happening.
- **Recommendation**: **adopt (decision-shaped, not code)** — put one of two things to the user:
  (a) a **fourth trip-wire criterion**: *"a Codex capability class exists that the valve's reach
  cannot express at all"* — with today's count of five as its first measurement; or (b) a narrowly
  scoped **second valve** at the registration level (a `codex:` block inside the kit's
  `settings.json` hook entries, scalars only, same shape and same reserved-key discipline as the
  frontmatter overlay), which would cover four of the five immediately. ~20 min to write the item;
  (b) is ~3–4 h of generator work plus tests if chosen. · **Status**: NEW

### 6. Hook layers MERGE and cannot replace each other — good news for the gates, with one undocumented question underneath it
- **Source**: https://learn.chatgpt.com/docs/hooks (seen 2026-09-25) — verbatim: *"If more than one
  hook source exists, Codex loads all matching hooks. Higher-precedence config layers don't replace
  lower-precedence hooks."* Sources are `~/.codex/hooks.json` (or `~/.codex/config.toml`),
  `<repo>/.codex/hooks.json` (or its `config.toml`), and plugin bundles (`hooks/hooks.json` in the
  plugin root, or a manifest path); plugin hooks get `PLUGIN_ROOT`/`PLUGIN_DATA` plus
  `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` "for compatibility". Trust as quoted in item 3, plus:
  *"Codex records trust against the hook's current hash, so new or changed hooks are marked for
  review and skipped until trusted."*
- **Why it matters HERE**: this is the **first official statement** that a user-level config cannot
  delete a project's gate — the property the kits' whole second line of defense (the `kit_checks`
  enforcement diff, `guard_harness_selfmod`) assumes but has never had in writing for Codex. Worth
  recording as such. Underneath it sits a question the page does **not** answer: when two
  `PreToolUse` hooks return conflicting decisions — a user-level one saying
  `permissionDecision: "allow"`, the kit's gate saying `deny` or exiting 2 — **which wins?** On
  Claude Code any deny wins. If Codex lets an allow from a layer *outside* the hashed kit bundle
  pre-empt a kit refusal, that is a bypass class living entirely outside every place this repo looks
  (the enforcement diff reads the repo; `guard_harness_selfmod` guards repo files; `~/.codex/` is
  neither).
- **Recommendation**: **watch + one measurement** — two `PreToolUse` hooks on the same `Bash`
  matcher, one from `~/.codex/hooks.json` returning allow, one from the project returning deny; read
  which one the CLI honours. ~30 min on a host with Codex CLI. If allow wins, it is a hole-list entry
  with a chain, not a watch item. · **Status**: NEW

### 7. The effort vocabulary is now contradicted at BOTH ends, and the vendor's own starting advice inverts the kits' uniform `effort: high`
- **Sources** (seen 2026-09-25): the model pages for `gpt-6-sol` and `gpt-6-luna` list
  **`none`, `low`, `medium` (default), `high`, `xhigh`, `max`** (with the caveat *"Chat Completions
  supports function calling only with `reasoning_effort` set to `none`"*); `gpt-6-astra` lists
  `low … max`; https://learn.chatgpt.com/docs/agent-configuration/subagents still names **`ultra`**
  among its levels and says: *"For explicit model settings, start with `medium` for GPT-6 Sol,
  `high` for GPT-6 Luna, or `low` for GPT-6 Astra. Adjust for the task using a level the selected
  model supports."*
- **Why it matters HERE**: `model_tiers.yaml` states the Codex effort field's values as
  *"shared vocabulary low|medium|high|xhigh|max"*. The **top** of that claim was already known to be
  contested (decided as `codex-0905-effort-ceiling`, still unmeasured); what is new is that the
  **bottom** is now wrong too — `none` is a documented value on both GPT-6 rungs the proposal in
  item 1 would pin, and it is not merely "less effort" but a mode with its own API consequence. And
  the vendor's starting advice runs opposite to the kits' practice: measured 2026-09-25, **27 role
  definitions across the three kits declare `effort:` — 25 `high`, 2 `low`** (the office kit's
  `filing-reviewer` and `records-clerk`), i.e. a uniform `high` on a Sol whose recommended start is
  `medium` and an Astra whose recommended start is `low`.
- **Recommendation**: **report only, input to the item-1 decision.** The effort ladder is the kits'
  `ladder.yaml` (DEC-0078) and DEC-0096's climb order, not this table, and "the vendor recommends a
  lower start" is positioning, not a measurement — so I propose no change. What I do recommend: if
  item 1 is adopted, the same item corrects the vocabulary sentence to state both contradictions
  (`none` at the bottom, `max` vs `ultra` at the top) rather than a clean shared list that is
  accurate at neither end. ~15 min as a rider. · **Status**: NEW

### 8. COMPETITIVE PRESSURE: Codex now ships `/usage` — the cost-per-goal number this harness's own rung decisions are missing
- **Source**: https://learn.chatgpt.com/docs/changelog — **0.156.0 (2026-09-22)**: *"Explore account
  usage, token totals, and plugin and skill activity through the `/usage` analytics dashboard."*
  Seen 2026-09-25.
- **Why it matters HERE**: DEC-0095 moved the standing tier onto the middle rung *on cost*, and
  DEC-0096 fixed the order in which a failed run climbs effort before rung. Both are cost arguments,
  and this repo has **no cost surface at all** — no rollup answers "what did goal X cost, per rung".
  The sibling report's item 2 P-C says the same thing from the Claude side (*"a real answer wants one
  measured goal run per rung, not a price table"*). Codex now hands its users that number for free;
  our harness cannot produce it for either provider. The pieces exist: the kernel records leases and
  dispatches per order, and `.audit/` already logs agent events — what is missing is a `report`
  rollup that multiplies a rung's price anchor by recorded usage.
- **Recommendation**: **watch / consider** — a real `FR`, not this week's work: the honest blocker is
  that neither provider's per-call token counts reach a hook payload today, so any rollup would be
  an estimate from the rung and the turn count, and an estimate presented as a cost is worse than no
  number. Name it as the prerequisite. ~30 min to write the FR with that limit stated. · **Status**: NEW

---

## Also checked — findings with their reason for no action

- **Hook event list: unchanged.** The reference still documents the same **12** events this watcher
  recorded on 2026-09-05 (`SessionStart, SessionEnd, PreToolUse, PermissionRequest, PostToolUse,
  PreCompact, PostCompact, UserPromptSubmit, SubagentStart, SubagentStop, Stop, Interrupt`); no new
  event landed in this window. (The page's own prose says "11", which does not match its own list —
  noted so a future scan does not read the discrepancy as a removal.) Seen 2026-09-25.
- **Umbrella issue openai/codex#21753 is still open — and its body is no longer usable as a status
  source.** Seen 2026-09-25: its checklist still lists `SubagentStart`/`SubagentStop` and the
  `mcp_tool`/HTTP/prompt/agent handler types under "missing", while the hooks reference documents
  `SubagentStart`, `SubagentStop` and `mcp_tool` as shipped. The issue body **lags the docs**, so
  "still open" is the only fact I take from it; its matrix is not evidence in either direction. Same
  rendering limitation as the last two scans (the comment thread does not render for this tool), so
  this is weaker than a full read.
- **Effort ceiling `max` vs `ultra`: still contradicted, still unmeasured.** Re-checked both pages
  2026-09-25, no edit to either. Already decided (`codex-0905-effort-ceiling` → `PR-0010` AC-2/AC-3,
  the spike carried by `BUG-0254`/`H172`). Pointer only, not NEW.
- **The CLI's own default model: still no exposure, re-confirmed.** `gen_codex_agent` and
  `gen_codex_config` always emit an explicit `model =` line (checked 2026-09-25 at
  `gen_provider_artifacts.py:810-819, 883-891`), so neither the 0.153.4 default-to-Astra change nor
  0.157.0's migration prompts can move a generated role. The 2026-09-06 report's conclusion holds
  unchanged.
- **`CLAUDE_PROJECT_DIR` cannot be hijacked by Codex's new compat env vars.** Codex now sets
  `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` "for compatibility" (hooks doc, seen 2026-09-25), and
  `_root.find_repo_root` gives `CLAUDE_PROJECT_DIR` absolute precedence — but the generated Codex
  hook command **sets that variable itself** (`posix_env = 'CLAUDE_PROJECT_DIR="$root" …'`,
  `gen_provider_artifacts.py:634`; the PowerShell branch assigns `$env:CLAUDE_PROJECT_DIR = $root`),
  so an inherited value is overwritten before any hook reads it. Confirmed check, no action.
- **AGENTS.md (Codex side): unchanged where it matters.** `project_doc_max_bytes` is still documented
  at a 32 KiB default with silent truncation past it, discovery is still global → project-scope with
  files closer to the cwd overriding, and `AGENTS.override.md` is still checked before `AGENTS.md`
  at each level — all as recorded on 2026-09-05, and `gen_codex_config`'s
  `project_doc_max_bytes = 65536` mitigation still matches the vendor's own worked example. One key
  this watcher had not itemized: **`project_doc_fallback_filenames`**, which lets a repo name
  additional instruction filenames; no kit uses it and nothing in the generator needs it. Seen
  2026-09-25 (https://learn.chatgpt.com/docs/agent-configuration/agents-md).
- **AGENTS.md (the standard): no spec change found.** https://agents.md/ (seen 2026-09-25) publishes
  no version number and no dated changelog; it states the precedence rule this repo already follows
  (*"The closest AGENTS.md to the edited file wins; explicit user chat prompts override
  everything"*), no file-size cap of its own (the 32 KiB cap is Codex's, not the spec's), 30+
  adopting tools and "60k+ open-source projects", and that the spec is *"now stewarded by the
  Agentic AI Foundation under the Linux Foundation"*. Nothing that touches a generator or a gate.
- **`.codex/agents/*.toml` fields: unchanged.** Required `name`, `description`,
  `developer_instructions`; optional `model`, `model_reasoning_effort`, `sandbox_mode`,
  `mcp_servers`, `skills.config`, plus other `config.toml` keys — the same set as 2026-09-05, all
  either emitted by `gen_codex_agent` or reachable through the frontmatter overlay (scalars). Seen
  2026-09-25. No schema step needed for the per-agent layer; the gap is one layer out (item 5).
- **0.156.0 sandbox hardening** — *"Close sandbox isolation gaps involving inbound Windows
  connections, privileged Linux/macOS sockets, and writes through read-only macOS file handles"* —
  and 0.157.0 *"Enforced network restrictions across redirects and ongoing HTTP and WebSocket
  traffic, including cancellation when policy changes revoke access"*. Seen 2026-09-25. Upstream
  hardening of the layer the generator's header calls "defense in depth"; pure upside, and the
  kits' own gates do not depend on any of it. No action.
- **Not itemized** (no harness relevance, all seen 2026-09-25 on the changelog): the `/tui`
  fullscreen UI and fullscreen transcripts by default; voice conversations on by default with F8;
  six terminal themes, Mermaid and display equations; the `f` fork shortcut and `/import` in remote
  and background-server sessions; automatic background-server startup and `/daemon` /
  `--no-daemon`; clipboard/tmux/SSH and proxy fixes; file-upload retries; the iOS 1.2026.258
  release.

---

## Still-open prior items of this watcher (pointers only, not re-surfaced)

- **`Interrupt` has no source-format vehicle** — unchanged; now the first of the five in item 5.
  Decided as `codex-0905-interrupt-event`.
- **Effort ceiling `max` vs `ultra`** — unchanged, needs a live-CLI spike. Decided as
  `codex-0905-effort-ceiling`.
- **`SubagentStart` carries no work-order payload** (openai/codex#32753, closed "not planned") —
  durable gap, already in the generator's own comment. Decided as `codex-0905-subagentstart-payload`.
- **A retired model pin fails loudly (400) on Codex** (openai/codex#25440) — re-checked 2026-09-25,
  still open, no maintainer fix. Decided as `codex-0905-missing-pin-400`; note that item 1, if
  adopted, is the change that would exercise it.
