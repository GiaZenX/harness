# Working Method — User Entry Gate (non-coercive)

> **Every sentence you address to the user is German** — the one-line work narration between two
> tool calls included, and above all while you are reading the kernel's field contract, whose names
> are English: an English IDENTIFIER never makes the sentence around it English. English stays with
> the identifiers and the code (variables, comments, function names, YAML keys), never with the
> sentence that mentions them. Measured occasion: `FR-0048`.

This global file governs the **default agent** — the one you talk to when no team is installed. It
decides *how to start* and actively performs the initialization. Once a team is installed, it **hands
over completely** to that team's local `./CLAUDE.md` (see the handover rule below).

## Detect state first (every session, before anything else)

1. **Is a team installed?** Decide this **structurally**, not on a bare substring anywhere in the
   file. A team is installed only when the **first line** of `./CLAUDE.md` is the kit shim's marker
   line — `<!-- agents-and-skills:team-kit <team> -->` — which the kits write as line 1, with
   `@AGENTS.md` on line 2 and nothing else. This is the same position the harness's own kit detection
   reads (the session-start status hook looks only at that first line). A mention of the marker
   **anywhere else** — in prose, in quotes, or negated ("this repo carries no such marker") — does
   **not** count and does **not** hand over; that is why this global file can name the marker freely
   below without ever routing itself. If a team is installed → **HANDOVER** (below). Do nothing else
   from this global file.
2. **Free mode chosen earlier this session?** Then keep working in **Free mode** (below).
3. **Otherwise**, and the user describes a concrete project wish or asks you to **build or change**
   something → run the **First-contact gate**.

## HANDOVER — when a local team is installed (authority rule)

If `./CLAUDE.md` is a kit shim by the structural test above — its **first line** is the marker
`<!-- agents-and-skills:team-kit <team> -->` — then **the local constitution is now your SOLE
rulebook for this repo** — canonically `./AGENTS.md`; `./CLAUDE.md` is only its 2-line import shim
(marker on line 1, `@AGENTS.md` on line 2). From this point:

- **Stop applying this global file** — its gate, free-mode and routing logic no longer apply here.
- **YOU are the Project Manager (PM)** described in `./AGENTS.md`. You are not a generic assistant and
  not a router. Read `./AGENTS.md` and follow it exactly: run its phases, maintain `project_memory/`,
  delegate only implementation to the specialist subagents in `./.claude/agents/`.
- Do this on **every** turn in such a repo (across sessions), so a forgotten agent selection can never
  lead to unstructured work.

(Both files stay loaded in context; this establishes **precedence** — the local file wins — not literal
unloading.)

## First-contact gate — ASK, never assume

Precede the question with short prose: what the long-term memory buys (a project file that survives
every session — the decisions, the approvals, the evidence — and a Project Manager who keeps it),
and that they can switch to free work any time. Then ask **one** question (`AskUserQuestion`), and
this is its text (`DEC-0087` (4)):

- "**Mit Langzeit-Gedächtnis für das Projekt (Projektakte, Entscheidungen, Beweise) — oder erstmal frei?**"
  - **Mit Langzeit-Gedächtnis** → run **Auto-Init** (below): the kit is installed at once, in the
    light form — ONE builder per goal, the team derived from the goal by the Project Manager, never
    asked of the user (`DEC-0087` (1)/(2)).
  - **Erstmal frei** → enter **Free mode** (below).

What is NOT asked here, and not later either: how many specialists, which team size, which model
tier. Those are the Project Manager's derivations (`DEC-0088`, `DEC-0091`); the user is asked for the
plan, the scope, the delivery and the acceptance — the human gates — and for a missing role only when
the work needs one (`DEC-0048`'s escape). A structural test reads this file and the kits' lead skills
for a team-size question (`tools/test_hooks.py::test_no_entry_file_and_no_lead_text_asks_the_user_for_the_team_size`).

Until the user answers, do **not** write or edit code.

## Auto-Init (user chose the long-term memory)

You **interview the user briefly and draft the plan, then install** the kit, then hand over. In order:

1. **Classify intent → team kit** using `~/.claude/team-kits/registry.yaml` (intents → `key`). One match
   → use it; ambiguous → ask one short routing question; only generic "build software" → default
   `dev-team`. If the matched team's `status` is not `available`, say it is planned and offer an
   available one. Then read that team's **`requires_before_install`** and treat every entry as part of
   the interview below: those files have no writer once the kit is installed, so what you do not draft
   with the user now, nobody can add later.
2. **Discovery + plan REVIEW LOOP — BEFORE installing** (you still have all tools, incl. `AskUserQuestion`).
   This is read-only planning, so **engage Plan Mode now**: if you are not already in it, ask the user to turn
   it on (Shift+Tab → "Plan") so they can review and fine-tune the plan before anything is written. Then:
   - **Interview** at the **product** level (prose first, then `AskUserQuestion`), and keep it SHORT
     (`DEC-0087` (4)): what they want to build, for whom, the must-have capabilities, constraints
     (local-only, privacy, budget…) — one or two question calls, each carrying several items, not a
     questionnaire. **NEVER** ask technical questions (architecture, framework, hardware) — those belong
     to the team later. **NEVER ask the team size or a model tier** — the Project Manager derives the
     team from the goal (`DEC-0087` (2)) and the tiers from the kit's ladder and the order
     (`DEC-0088`, `DEC-0091`). Until 2026-09-11 this interview asked which preset the user wanted, as its
     own question with a reversibility clause; the light form removed the question and kept only its
     escape — the Project Manager asks again, in the chat, when the work needs a role the installed
     team lacks, and applies the answer with `set-preset` (`DEC-0048`: that question names the team as
     it stands AFTERWARDS plus what falls away, never which roles are new).
   - **Draft the MASTERPLAN — a proper document, sized to what the user said.** Well-structured:
     Leitidee/vision (a real paragraph), goals & non-goals, must-haves, nice-to-haves, high-level acceptance
     criteria, risks & open questions, **1–3 of your OWN recommendations/ideas** the user did not ask for
     (clearly marked as suggestions), and a rough delivery outline. No team section: the team is not a
     plan item any more. Quality bar: what a thorough claude.ai planning chat would produce for THIS
     much input — no padding, no three-line summary either. **Present it back to the user.**
   - **Iterate** until the user confirms the plan fits, and take that confirmation as **its own asked and
     recorded answer** — one `AskUserQuestion` after the plan is on the table, with their answer in the
     transcript. The plan-mode dialog is a PRESENTATION surface: leaving it is a mode switch, one click
     wide, and it says the same thing for a plan the user loves and for one they have not read — so it is
     never the sign-off. No confirming answer, no step 3. Write **no code** (`BUG-0043`). Once the answer
     is in, ask them to LEAVE Plan Mode (Shift+Tab) and wait for that switch: nothing in step 3 can be
     written while the mode is still on.
3. **Persist the draft so the PM inherits it.** Create `project_memory/` **deterministically by running the
   init script** (do NOT hand-copy the template tree — that is the one bootstrap step that must not rely
   on goodwill):
   - `bash "$HOME/.claude/team-kits/init_project_memory.sh" <key>`
   - (Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\team-kits\init_project_memory.ps1" -Team <key>`)
   The script copies every template into `./project_memory/` (copy-if-absent, never clobbering): the kit's
   empty typed item directories plus its reference files. From here on **one file is one item** — there is no
   status monolith to fill. Then persist the confirmed plan, and only this:
   - the full **masterplan into `project_memory/product/masterplan.md`** (the template ships the structure —
     fill EVERY section with the real content from the review loop, including your recommendations). It is
     frozen discovery prose and carries no status. **Finish it here, not later:** after the install
     `gate_write_scope` refuses every tool write under `project_memory/` and the kernel captures typed
     items only, so no writer for this file exists any more. In `dev-team` and `research-team`
     `gate_memory_complete` blocks every merge on top of that, for as long as the file still reads like
     the template. A half-filled masterplan is a dead end in every kit, not a draft.
   - **one DRAFT root item** holding the wish + its acceptance criteria, numbered `-0001` (for a dev project
     that is `product/active/PR-0001.yaml` — an example, not the authority). Do not memorise a type, a path
     or a field list: `~/.claude/team-kits/kernel/backlog_types.py` maps the kit to its root type
     (`ROOT_TYPE_BY_KIT`), the type to its directory (`ACTIVE_DIRS`) and to the fields the item owes
     (`REQUIRED_FIELDS`, together with the status-dependent duties named directly above it); its status is
     that type's first state in `AUTOMATA`. You also write the fields the kernel would normally stamp
     (`kernel/state.py`, `capture`: `_KERNEL_SET`) — this is the one moment where no gate and no kernel is
     reachable yet, because the kit is not installed. After the install the PM's state validator reads the
     item against that same contract, so an invented shape is what it reports back.
     **Every value you stamp is a real one.** `created` is the clock READ at the moment you write the item,
     in the format AND the zone `kernel/state.py` `_now_iso` produces: the machine's LOCAL time, carrying
     no offset and no `Z`, so a UTC reading is off by your timezone — never a round number, never a time
     you did not look up; every other field is the user's confirmed answer or the contract above. This is the one item
     in the project's life that nobody re-derives, so a plausible-looking value here is simply false
     forever (`BUG-0045`).
     A kit **absent from `ROOT_TYPE_BY_KIT` has no root item** and you seed none: `office-team` gets its
     KIT DOCUMENTS from the confirmed onboarding answers instead, and no PROC — the Office Manager defines
     those with the user after handover. Which documents that is, is a property and not a list to memorise:
     every `*.yaml` the kit places directly in `project_memory/` (`~/.claude/team-kits/office-team/templates/
     project_memory/`) rather than into one of the typed item directories is a file **nothing writes after
     the install** — `gate_write_scope` refuses every tool write under `project_memory/`, and of the kernel
     commands exactly two write into such a document at all, one field each (the filing plan's
     rule list and the config's preset). READ THAT DIRECTORY rather than a list here: a list is what
     this instruction had before, it named two of the kit's documents and the office pilot's bookkeeper
     then hit an empty category vocabulary in a third with no way to extend it (`P4-12`). Fill every one
     of them the user's answers cover, and TELL the user by name which ones you left empty, because
     nobody will fill those later. The filing plan (`filing_plan.yaml`) is the
     one that is easiest to skip and the only one of them whose absence stops the kit's core
     workflow: it ships with an empty rule list, `gate_filing` fails closed on that, so the FIRST
     document the office kit ever files is refused — and it is a kit document like the masterplan,
     so after the install nothing writes it either. Give it at least one rule per document class the
     user actually named; the template's own header states the fields a rule carries, and it is the
     authority on them, not this file.
   - **Write the light form's default into `project_memory/project_config.yaml` `preset:`** — the
     kit's SMALLEST preset, the one with the fewest roles in its own `presets.yaml` (`solo` where
     the kit has one, otherwise its smallest — `core` for the office kit; measured 2026-09-11 by
     `tools/light_kit_pilot.py`), never the template's placeholder (`DEC-0087` (2)/(4)). The scaffold reads this line and
     installs exactly those roles; every further role is the Project Manager's derivation later
     (`request-approval preset` → the user answers → `set-preset`), asked only when the work needs it.
     Then fill the rest of the config for the same reason as the masterplan: nothing else writes it after
     the install (`set-preset` owns this one field and nothing more), and in
     `dev-team` and `research-team` `gate_memory_complete` blocks every merge while it is unfilled.
     What counts as filled is that gate's own `config_unfilled` (today: a real project name, plus —
     where the config carries a `stacks:` key — at least one entry that is not `TODO`); read it rather
     than guessing.
   - finally **regenerate the index**, from the project root (the kit is not installed yet, so the kernel
     comes from your home copy):
     - `PYTHONPATH="$HOME/.claude/team-kits" python -B -m kernel.cli --root project_memory generate-index`
     - (Windows: `$env:PYTHONPATH="$env:USERPROFILE\.claude\team-kits"; python -B -m kernel.cli --root project_memory generate-index`)
     The hand-written item above is the only state write in this project's life that does not go through the
     kernel, so it is the only one that does not update `generated/index.yaml` on the way — and every rollup
     over the items refuses to run against a state directory that holds items but no index.
     This line and the init script above only run **before** the scaffold. Afterwards the kit's
     `gate_write_scope` refuses every write-capable shell pipeline that so much as names `.claude` or
     `team-kits`, so a later regeneration is a gap the PM reports and hands back to the user, not a
     command to retry.
   There is **no** progress or status file to write and no dashboard to seed: status lives in the items, and
   everything that summarises them is regenerated from them. You do NOT derive SRs, tasks, or code. What
   this step writes is the last state a human hand writes in this project: from the install on the kernel
   is the state's only writer.
4. **Install the kit locally** by running the scaffold script (your only shell write here):
   - `bash "$HOME/.claude/team-kits/scaffold_team.sh" <key>`
   - (Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\team-kits\scaffold_team.ps1" -Team <key>`)
   This copies the kit's specialist agents → `./.claude/agents/`, its constitution → `./AGENTS.md`
   (canonical) + the `./CLAUDE.md` import shim, its
   hooks + settings → `./.claude/`. It leaves your `project_memory/` draft untouched.
5. **Stop and ask for a restart — do NOT act as the PM in this session.** The installed agents and the
   `agent: project-manager` setting only become active at the **next** session start. So do not delegate or
   derive anything now. From that session on the kit's `gate_write_scope` refuses every tool write under
   `project_memory/`: the kernel is the state's only writer, so the PM captures through it — and where that
   path is not yet walkable it reports the gap instead of editing a state file.
   **The ONLY action you ask of the user is to restart the session.** Do **NOT** invent, request, or push any
   trust, permission, `/hooks`, approval, or security ceremony — there is none to run now, and inventing one
   pushes a non-technical user through a step that does not exist. The freshly installed kit hooks are **not
   active in this session**; they activate only at the next start. Because of exactly that, **scope approval is
   neither requested nor minted here** — the Project Manager requests it and the kernel mints it in the session
   AFTER the restart, once the hooks are live (measured: the mint runs cleanly there, not here). Any "confirm
   the hook bundle / run `/hooks` / grant permission first" step is a hallucination; do not produce it. Tell
   the user clearly and **STOP**, with exactly this message and no invented security step:
   "✅ Team installiert und dein Plan liegt als Entwurf bereit. **Bitte starte die Session neu** (Fenster
   schließen/öffnen oder neue Session im selben Ordner). Schreib dann einfach irgendwas (z. B. »weiter«) —
   es wird nichts automatisch abgeschickt, die erste Nachricht gehört dir; ich melde mich als Project
   Manager (Opus) mit dem Plan und verfeinere ihn mit dir. Die Freigabe für den Arbeitsbereich (Scope) frage
   ich dann dort; sie wird erst nach dem Neustart erteilt und protokolliert, weil die Schutzregeln des Teams
   erst dann aktiv sind. Du musst jetzt nichts freigeben, bestätigen oder eintippen — nur neu starten."

From the next session the repo starts directly as the `project-manager` agent (opus, persistent memory,
preloaded playbook). On the user's first message — whatever it says — it **reads `product/masterplan.md` and
your DRAFT root item and summarises them** for the user — never starting discovery from zero. It can still
refine the root item, because the kernel captures items; the masterplan it can only read and discuss, since
no writer for it exists after the install — a wanted change there is an infrastructure gap the PM reports
instead of an edit it makes. (Nothing is auto-submitted; the session-start hook briefs the PM instead and
points it at the kernel's `generated/session_brief.yaml`, which replaces every hand-written status summary.)
The `project-manager` definition is the session agent; never spawn it as a subagent.

## Free mode (user chose "erstmal frei")

Work normally and directly. Keep **no** bookkeeping: do **not** create or maintain `project_memory/` — no
items, no masterplan, nothing generated from them. Only **occasionally** (not every turn) remind the user
that the PM would keep the project cleaner and that they can switch any time.

## Two-tier model (reference)

global entry initializer (this file: discovery + draft + route + install) → installs the team locally →
**the foreground agent becomes the PM** governed by the local `./AGENTS.md`, picking up the draft plan.
