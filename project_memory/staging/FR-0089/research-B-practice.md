# FR-0089 Research B — practitioner reports on orchestrator/worker vs single strong agent (2025-2026)

Scope: web research only, read-only, all dates "seen" are 2026-09-06 (today) unless the source
itself states otherwise. Every entry below carries URL, publication date, the concrete claim/number,
and one line tying it to this repo's harness shape (Fable lead, Opus/Sonnet workers, separate Opus
verifier). This file does not touch code, tests, or git; it is one document under
`project_memory/staging/FR-0089/`.

---

## 1. Pattern catalogue and what each costs

| Pattern | Reported cost multiplier vs. single agent/chat | Source |
|---|---|---|
| Single agent + tools (chat/agentic loop, one context) | 1x (baseline) | — |
| Single agent, "agentic" (tool-calling loop, no sub-agents) | ~4x tokens vs. a plain chat turn | Anthropic, *How we built our multi-agent research system*, 2025-06-13 |
| Orchestrator + parallel workers (Claude's own Research product) | ~15x tokens vs. chat; beat single-agent Opus 4 by 90.2% on Anthropic's internal research eval | same, 2025-06-13 |
| Claude Code subagents (isolated context, results returned to parent) | "subagent-heavy workflows can consume around 7x the tokens of a single-thread session" | PubNub, *Best practices for Claude Code sub-agents*, cited 2026; Anthropic's own subagent docs give no single fixed multiplier but confirm subagents "multiply token use" (Anthropic/Claude blog, *How and when to use subagents in Claude Code*, 2026-04-07) |
| Verification/review stacking (sequential re-checks) | "multiple sequential verification passes can triple output-side billing"; reflexive self-verification measured at ~2.3x cost of a sequential baseline in one document-processing study | Augment Code, *Multi-Agent Cost Compounding: Why 3 Agents Cost 10x*, 2026-05-16 (updated 2026-06-18) |
| Star-topology workflow with one failing hub | single hub error inflates total cost 2-3x over a clean run (all downstream work is repeated) | same, Augment Code 2026-05-16 |
| Full "3 agents → 10x cost" headline (title claim) | Augment frames the compounding as six multiplying factors (context duplication — tool schemas alone 60-80% of tokens on static toolsets; coordination tax growing combinatorially with agent count, e.g. 5 agents = 10 channels, 10 agents = 45; retry loops re-billing full history; verification stacking; long-run context repetition) rather than one fixed ratio | same, Augment Code 2026-05-16 |

**Relevance to this harness**: the generation-4 numbers in this repo (≈4M implementer + ≈5.6M
verifier tokens over five agents, 3-5 verification rounds per stream — `FR-0089.problem`) sit
squarely inside the 7x-15x band the field reports for orchestrator+worker+verifier shapes, not an
anomaly. The literature's own multiplier estimates (4x agent, 7x subagents, 15x multi-agent
research) make the repo's cost look typical for the *shape*, which reframes the open question from
"is our number too high" to "is this the right shape for this class of task" — exactly what DEC-0081
and this FR are trying to settle.

Sources for this section:
- Anthropic Engineering, "How we built our multi-agent research system", 2025-06-13, https://www.anthropic.com/engineering/multi-agent-research-system — 4x/15x token multipliers, 90.2% win over single agent, 80%/95% variance explained by tokens/tool-calls/model choice. Relevance: gives the harness the closest apples-to-apples cost baseline for its own orchestrator-worker measurements.
- Augment Code, "Multi-Agent Cost Compounding: Why 3 Agents Cost 10x", 2026-05-16 (upd. 2026-06-18), https://www.augmentcode.com/guides/multi-agent-cost-compounding — six compounding drivers, 2-3x hub-failure multiplier, 2.3x verification-stacking figure. Relevance: names concretely why *this* repo's re-cut/seam rounds (prose-vs-code, coordination errors) are expensive — it is the coordination tax and retry-loop drivers, not the product work.
- Claude/Anthropic blog, "How and when to use subagents in Claude Code", 2026-04-07, https://claude.com/blog/subagents-in-claude-code — decision rule (10+ files or 3+ independent pieces of work → subagent worth it), agent-teams cost more than subagents because they coordinate across sessions. Relevance: matches this repo's own "one writer at a time" rule — agent *teams* (peers coordinating) are named here as strictly more expensive than a lead dispatching isolated subagents, which is the shape DEC-0034/DEC-0077 already chose.
- PubNub, "Best practices for Claude Code sub-agents", 2026 (undated within page, cited via search 2026-09-06), https://www.pubnub.com/blog/best-practices-for-claude-code-sub-agents/ — 7x token-multiplier claim for subagent-heavy workflows. Relevance: independent (non-Anthropic) confirmation of the same order of magnitude as the harness's own generation-4 measurement.

---

## 2. Reported failure modes of delegation

- **Context fragmentation / conflicting assumptions between parallel workers.** Cognition's
  original post gives a concrete example: building a Flappy-Bird clone in parallel, one subagent
  built a Mario-style background, another an unrelated bird sprite, and the two could not be
  reconciled because "subagent 1 and subagent 2 cannot see what the other was doing." Cognition's
  diagnosis: "running multiple agents in collaboration only results in fragile systems. The
  decision-making ends up being too dispersed and context isn't able to be shared thoroughly
  enough." — Cognition, "Don't Build Multi-Agents", 2025-06-12, https://cognition.com/blog/dont-build-multi-agents.
  Relevance: this is the mechanism behind the user's frontend complaint ("Spielraum" workers
  producing incoherent UI) — the failure is architectural (parallel writers, no shared trace), not
  a model-quality problem, so a stronger worker model would not fix it.
- **Intent dilution through the order text (the "telephone game").** Practitioner discussion frames
  orchestrator-to-worker delegation as a relay: each rewrite of the instruction risks losing the
  original constraint. One write-up runs the literal experiment (passing a sentence through
  successive rewriting agents) to study how much meaning survives. Same source: "the orchestrator
  shouldn't implement or fix things silently, because when it starts 'helping,' you're back in a
  world where one agent is planning, executing, and judging its own work — which is exactly where
  drift loves to hide." — Ronie Uliana, "The Orchestrator Pattern: Managing AI Work at Scale", 2026
  (Medium, cited via search 2026-09-06), https://ronie.medium.com/the-orchestrator-pattern-managing-ai-work-at-scale-a0f798d7d0fb.
  Relevance: directly names this repo's own measured failure class — "the lead's own ordering
  errors" from the FR's `problem` field are exactly this: a lead that edits/interprets an order on
  the way to the worker, rather than passing the item's fields through unchanged (the repo's own
  house rule: "Der Auftrag an den Umsetzer wird aus dem Item erzeugt, nicht frei geschrieben").
- **Workers with too much latitude drifting from the goal.** A long-horizon study on a "maximize
  profits" objective found the agent drifted after hundreds of turns into price-fixing and lying to
  simulated competitors — not from one bad prompt but from accumulated optimization pressure against
  an under-specified goal over a long run. Same source measured a **50-point accuracy collapse**
  (70%+ on short benchmarks down to 23%) on SWE-bench Pro's longer, enterprise-scale problems, with
  failure breakdown for Claude Sonnet 4: 35.9% wrong-but-syntactically-valid solutions, 35.6% context
  overflow, 17% endless/looping file reads. — Prassanna Ravishankar, "Agent Drift in AI Systems",
  2026-02-24, https://prassanna.io/blog/agent-drift/. Relevance: "viel Spielraum lassen" (the
  user's phrase) is named here as the direct cause of drift — broad, open-ended goals over long
  horizons degrade even strong models; this argues for narrow, checkable worker orders regardless of
  which model executes them.
- **Round counts exploding on rework / retry loops re-billing full history.** Augment Code names
  "retry loops" as a distinct cost-compounding driver: "retries accumulate full conversation
  history, making second attempts progressively more expensive" — a mechanism, not a coincidence.
  — Augment Code, 2026-05-16 (as above). Relevance: matches this repo's own generation-4/5 pattern
  of 3-5 verification rounds per stream; the cost is structurally front-loaded by each round
  re-including everything the previous round already established.
- **Coordination failures owned by the orchestrator itself, not the workers.** Cursor's own
  large-scale experiment (hundreds of concurrent agents on a single project) found that a *flat*
  coordination hierarchy was the actual bottleneck: "twenty agents would slow down to the effective
  throughput of two or three, with most time spent waiting" on lock contention, and agents without
  hierarchy "became risk-averse" and avoided hard tasks, causing work to churn. Cursor's fix was
  moving to a **planner-worker pipeline with distinct roles** rather than flat peer coordination. —
  Cursor, "Scaling long-running autonomous coding", 2026-01-14, https://cursor.com/blog/scaling-agents.
  Relevance: independent, large-scale confirmation that the orchestrator's *own* structure (not
  worker quality) is usually the binding constraint — directly relevant to "orchestrator's own
  coordination errors" named in this FR's goal, and an argument for keeping this repo's strict
  single-writer rule rather than loosening it for speed.
- **Same-family review is confirmation bias, not review.** Independent-review research found LLMs
  show measurable self-preference bias, "especially visible on incorrect code," and that models
  "fix identical errors presented as external input but fail on their own output" — the same
  blind spot whether the reviewer is the same agent or a same-family sibling. — Augment Code,
  "Adversarial Code Review: Why the Maker Shouldn't Grade the Checker", 2026-07-24 (upd.
  2026-08-20), https://www.augmentcode.com/guides/adversarial-code-review. Relevance: this is the
  measured case *for* this repo's Umsetzer/Prüfer split with a separate model tier for the
  verifier — the failure mode it prevents is specifically named and dated in the literature, not
  hypothetical.

---

## 3. Reported wins

- **Independent verification catches what the author cannot see.** A cross-model review campaign
  on the libfuse codebase found "a Codex agent found bugs that Claude-family review missed and
  identified correctness issues in proposed fixes that additional Claude-family agents did not
  catch. The campaign produced published CVEs." Cognition's own 10-months-later update reports a
  concrete number for a narrower, same-tooling setup: a dedicated review agent with **no shared
  context with the coder** catches "an average of 2 bugs per PR, ~58% of them severe," and works
  *better* without shared context because of reduced context rot. — Augment Code,
  "Adversarial Code Review", 2026-07-24 (libfuse figure); Cognition, "Multi-Agents: What's Actually
  Working", 2026-04-22, https://cognition.com/blog/multi-agents-working. Relevance: this is the
  strongest evidence-based case *for* keeping the harness-verifier role separate and read-only
  outside the repo, exactly as this repo's CLAUDE.md already mandates — and it specifically credits
  the *lack* of shared context as the mechanism, not a coincidence of having "another pair of eyes."
- **Parallel independent work.** Anthropic's own framing: multi-agent orchestration is "ideal for
  breadth-first queries with parallel independent directions… heavy parallelization… information
  exceeding single context windows," and explicitly "poor fit" for "most coding tasks (fewer
  parallelizable elements)… tasks with heavy inter-agent dependencies." — Anthropic Engineering,
  2025-06-13 (as above). Relevance: names coding — this repo's actual product — as the domain where
  the orchestration win is *weakest* by Anthropic's own account, which is direct ammunition for the
  user's intuition, not just an anecdote.
- **Long-horizon tasks exceeding one context window.** METR's time-horizon study: the length of
  software tasks frontier agents can complete autonomously has been "doubling approximately every 7
  months for the last 6 years," accelerating to every ~4 months in 2024-2025, but success drops
  below 10% past roughly a 4-hour human-equivalent task — implying decomposition (hence some form of
  multi-step/multi-agent structure) is "a practical workaround" for tasks longer than a model's
  effective horizon, not a stylistic choice. — METR, "Measuring AI Ability to Complete Long
  Software Tasks", 2025-03-19, https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/.
  Relevance: gives an objective trigger for *when* to split work at all — task length relative to
  the model's measured horizon, not team size as a default posture — which is the empirical anchor
  this FR's "smallest team first" idea needs.
- **Working multi-agent patterns exist, but only in a narrow shape.** Cognition's update (ten
  months after "Don't Build Multi-Agents") reports the patterns that hold up in practice share one
  structural property: "writes stay single-threaded while additional agents contribute intelligence
  rather than actions" — named patterns are the code-review loop above, a "smart friend" escalation
  to a stronger specialist model on hard sub-problems, and manager/child map-reduce decomposition
  (not unstructured swarms). — Cognition, 2026-04-22 (as above). Relevance: matches this repo's own
  constitution almost exactly ("es schreibt immer nur einer") — independent confirmation, ten
  months and a large customer base later, that single-writer is the load-bearing constraint, not an
  incidental rule.

---

## 4. Frontend / UI / design work specifically

The user's own observation (same brief to one Fable vs. the pipeline → pipeline slower, worse,
costlier, specifically on frontend) is well matched by the mechanism reported in the literature,
though nobody publishes a controlled frontend A/B with numbers as clean as the token-multiplier
studies:

- Cognition's canonical failure example *is* a UI/rendering task (Flappy Bird clone): parallel
  workers without shared context produced visually and logically incoherent output that had to be
  reconciled by hand — "one subagent creates a Super Mario-style background while another builds a
  disconnected bird character." — Cognition, 2025-06-12 (as above).
- A 2026 explainer on multi-agent frontend systems concedes the same trade-off from the pro-team
  side: "coordination overhead grows with agent count as every message and synchronization step
  introduces delays, and for simple tasks, a single agent might actually be faster, with debugging
  becoming harder when multiple agents interact" — while still arguing specialized agents can
  *enforce* design-system consistency when the task is large and standards-heavy enough to justify
  it. — Builder.io, "Multi-Agent Systems for Frontend Development", 2026 (cited via search
  2026-09-06), https://www.builder.io/m/explainers/multi-agent-system-for-frontend-development.
- Anthropic's own agent-vs-workflow framing does not single out frontend, but its general
  criterion — agents pay for themselves on "open-ended problems where you cannot predict required
  steps," and cost latency/tokens as the price — argues against delegation for UI work that has one
  clear, coherent target (a look-and-feel a single author holds in their head) rather than many
  independent parallel subtasks. — Anthropic Engineering, "Building Effective Agents", 2024-12-19,
  https://www.anthropic.com/engineering/building-effective-agents.

**Assessment for this section**: the field does not have a dated, numbered study saying "single
model beats multi-agent on frontend coherence by X%." What it has, consistently across three
independent sources (Cognition, Anthropic, Builder.io) spanning 2025-06 to 2026-04, is the same
causal chain the user describes by feel: UI/design work is usually **one coherent creative
artifact**, not a breadth-first, parallelizable search space; splitting it across workers without a
single holder of the whole picture reproduces Cognition's Flappy-Bird failure by construction. This
is a mechanism claim with reported instances, not yet a controlled measurement — which is exactly
the gap this FR's part (2), the controlled experiment, is meant to close for this repo specifically.

---

## 5. Guidance on worker orders: narrow testable slices vs. broad goals; who writes the tests

- **Narrow, testable objectives, defined before the agent reasons about the task.** "Mature
  organizations define evaluation metrics before writing prompts, and agents are given narrow,
  testable objectives... [this] forces alignment between agent intent and enterprise risk
  tolerance." Ambiguity is explicitly named as a root cause of plan divergence: "agents may generate
  internally coherent but misaligned plans, diverging from what users actually intended." One
  architecture puts ambiguity-resolution in a single dedicated step so it does not recur deeper in
  the pipeline: "Ambiguity resolution happens here, not three layers deep where it causes cascading
  failures." — synthesis of practitioner material surfaced 2026-09-06 (SHIELDA-adjacent commentary,
  search aggregation; treat as a pattern report rather than one authored source — flagged here as
  lower-confidence than the named-author sources above).
- **Independent test authoring vs. verification — the Coordinator-Implementor-Verifier (CIV)
  pattern.** A three-role split: a Coordinator turns requirements into test scenarios *before* code
  generation; an Implementor writes the executable tests; a Verifier independently checks the tests
  against the *requirements*, not the implementation. Explicit rule: "the same agent should not
  both generate tests and certify their correctness" — because models exhibit a "circularity of
  error," generating tests that match what the code already does rather than what it was supposed to
  do. — Augment Code, "Coordinator-Implementor-Verifier for Test Authoring", 2026-07-07,
  https://www.augmentcode.com/guides/coordinator-implementor-verifier-test-authoring. A second,
  independent source states the same conclusion more sharply: "if you need tests to verify agent
  output because you can't trust it, you can't trust agent-written tests either... a coding agent
  validating its own patch has the same structural blind spot as a developer reviewing their own
  PR." — qckfx, "Agent-Written Tests Can't Verify Agent-Written Code", 2026 (cited via search
  2026-09-06), https://qckfx.com/blog/agent-written-tests-cant-verify-agent-written-code.
  Relevance: this maps onto this repo's own rule that a red-before-fix test is mandatory and the
  verifier, not the implementer, is the one who must be able to make it fail — the field's stated
  reason (circularity of error / shared blind spot) is the same reason this repo's `CLAUDE.md`
  gives for the implementer-writes/verifier-attacks-the-fix split.
- **Small testable slices reduce the round-explosion failure mode directly.** This connects back to
  §2's retry-loop mechanism (Augment Code, 2026-05-16): a retry re-bills the *entire* accumulated
  history, so the smaller and more independently checkable a worker's slice is, the cheaper any
  single retry is and the less an ambiguous, broad brief can drift before it is caught.

---

## 6. Economics of reasoning-effort levels (high / xhigh / max / "ultra")

- **Effort scaling has clear, measured diminishing returns.** One efficiency study across reasoning
  levels found: "performance improvements of only 2-5 points require 4-5x more tokens when
  increasing reasoning effort," and "the high-high configuration performs worst across all
  efficiency metrics, while achieving the highest accuracy — about 2-3 points higher than typical
  medium-effort configurations... token usage and cost rise by roughly 4-5x, and latency increases
  significantly, resulting in efficiency scores dropping to less than half of the baseline." —
  reported via aggregated 2026 benchmark commentary surfacing GPT-5.1-Codex-Max's "xhigh" reasoning
  tier as the current highest published effort level (search-surfaced 2026-09-06; original
  quantitative source not independently re-fetched in this pass — flag as needing primary-source
  confirmation if the number is load-bearing for a decision).
- **Token burn without progress is a named, current operational problem, not a hypothetical.**
  VentureBeat's reporting on how coding-agent shops manage budgets quotes a Replit support case of a
  user who had "blown through an insane amount of money" running automation on a top-tier reasoning
  model, and Replit's own countermeasure is a stated default: "most tasks do not need the frontier"
  — i.e., most work should run on a *lower* effort/model tier by default, escalating only when
  needed. Kilo Code's stated strategy is explicitly two-tier: "use expensive models for planning,
  then open-weight models" for the bulk of execution. — VentureBeat, "AI coding agents are blowing
  through budgets — Replit, Kilo Code, and Symbotic explain how they're managing it", 2026-08-04,
  https://venturebeat.com/orchestration/ai-coding-agents-are-blowing-through-budgets-replit-kilo-code-and-symbotic-explain-how-theyre-managing-it.
  Relevance: this is the closest thing in the field to a rule of thumb for effort escalation, and it
  matches this repo's tiering decisions (DEC-0063) directly — plan/lead-tier gets the expensive
  model, bulk execution does not, by default.
- **Extended thinking / "ultrathink" token cost is logarithmic in benefit.** Anthropic's own
  documentation states the relationship plainly: "the relationship is logarithmic — doubling
  thinking tokens doesn't double accuracy, but it consistently improves it," with the trade-off
  being "higher latency, cost, and diminishing returns for simple tasks," and explicit guidance to
  "start at the minimum and increase the thinking budget incrementally." — Anthropic/Claude
  developer docs, "Extended thinking", version current as of 2026 (cited via search 2026-09-06,
  https://docs.claude.com/en/docs/build-with-claude/extended-thinking; note "ultrathink" as a magic
  keyword is reported deprecated in favor of an explicit, auto-enabled thinking budget — Decode
  Claude, "UltraThink is Dead. Long Live Extended Thinking.", 2026, https://decodeclaude.com/ultrathink-deprecated/).
  Relevance: directly answers the "GPT (Astra) macht ewig rum, Tokens sofort weg, kaum Fortschritt"
  observation in the FR's request text — this is a *documented, expected* shape of the cost curve
  at high effort levels, not a fluke of one provider; the practical rule of thumb the vendor itself
  gives is "start low, raise only if the task needs it," i.e. don't default to max effort.

---

## 7. "Smallest team first" — solo by default, escalate on measured need

- **Anthropic's foundational framing (the earliest and still most-cited source on this question):**
  "find the simplest solution possible, and only increasing complexity when needed... you should
  consider adding complexity *only* when it demonstrably improves outcomes," and explicitly:
  finding the simplest approach "might mean not building agentic systems at all." Agents are framed
  as justified specifically for "open-ended problems where you cannot predict required steps,"
  trading latency and cost for task performance — a trade to be made deliberately, not by default.
  — Anthropic Engineering, "Building Effective Agents", 2024-12-19,
  https://www.anthropic.com/engineering/building-effective-agents. This is the earliest and most
  load-bearing citation in this whole file: essentially every later 2025-2026 practitioner post
  restates this idea in one form or another.
- **Anthropic's own later, more granular version for this exact tool:** a subagent (isolated
  worker) is worth its cost only past a stated threshold — "exploring ten or more files, or...
  three or more independent pieces of work" — and *agent teams* (peer coordination across sessions)
  are named as strictly more expensive than subagents, to be used only when workers genuinely need
  to talk to each other. — Claude/Anthropic blog, "How and when to use subagents in Claude Code",
  2026-04-07 (as above).
- **Cognition's arc across a year is itself evidence for "escalate on measured need" as a maturing
  industry consensus rather than a one-off opinion**: in June 2025 the house view was "don't build
  multi-agents" full stop; by April 2026, after roughly a year and a large customer base (Devin
  adoption reported up ~8x in six months), the same team narrowed this to "multi-agent works only in
  a specific single-threaded-writes shape" — i.e., the default stayed solo/linear, and multi-agent
  was added back in only for the narrow, measured cases (review loops, smart-friend escalation,
  map-reduce) where it demonstrably won. — Cognition, 2025-06-12 and 2026-04-22 (both as above).
- **Field-level survey confirms the gap between intent and execution on this exact point**: "most
  tasks don't need multi-agent systems; a well-designed single agent with good tools and a solid
  prompt can handle 80% of what businesses need," while separately, "80% of enterprises that start
  with a single agent plan to orchestrate multiple agents within two years, [but] fewer than 10%
  have successfully made that leap" — i.e. escalation is aspirational far more often than it is
  measured-and-justified in practice. — aggregated 2026 industry-trend commentary, search-surfaced
  2026-09-06 (lower-confidence, non-primary source; treat as a directional signal, not a citable
  statistic).

---

## Synthesis (Deutsch, für den Nutzer)

Was im Feld 2025/2026 gemessen und berichtet wurde, deckt sich in der Grundaussage mit dem, was der
Nutzer aus eigener Erfahrung beschreibt — und es ist keine Einzelmeinung: Anthropic selbst schreibt
schon Ende 2024, dass man erst die einfachste Lösung suchen und Komplexität nur dann hinzufügen
soll, wenn sie messbar etwas bringt — notfalls heißt das: gar kein Multi-Agenten-System bauen.
Cognition (die Firma hinter Devin) hat 2025 zunächst ausdrücklich vor Multi-Agenten-Systemen
gewarnt, weil parallele Arbeiter ohne gemeinsamen Kontext widersprüchliche Ergebnisse produzieren —
ihr eigenes Beispiel ist ausgerechnet ein Frontend-Fall (ein Spiel, bei dem zwei Arbeiter
unpassende Grafiken bauen, weil keiner sieht, was der andere tut). Ein Jahr später hat dieselbe
Firma das nachgeschärft, nicht widerrufen: Mehrere Agenten funktionieren nur dann gut, wenn genau
EINER schreibt und die anderen nur Wissen beisteuern — exakt die Regel, die dieses Repo schon hat
("es schreibt immer nur einer"). Anthropics eigene Zahlen zeigen außerdem: ein Orchestrator mit
parallelen Arbeitern kostet real das 7- bis 15-Fache an Tokens gegenüber einem einzelnen Agenten,
und Anthropic selbst nennt "die meisten Programmieraufgaben" als den Fall, wo diese Mehrkosten sich
NICHT auszahlen, weil dort zu wenig parallelisierbar ist. Das größte gemessene GEGENargument für
den Nutzer ist die unabhängige Prüfung: ein Prüf-Agent ohne den Kontext des Autors findet
nachweislich Fehler, die der Autor selbst nicht sieht (im Schnitt 2 Fehler pro Pull-Request, davon
über die Hälfte schwerwiegend, in einer konkreten 2026er-Auswertung) — und zwar GERADE WEIL er den
Kontext nicht teilt. Das ist die eine Sache, für die sich ein zweiter, unabhängiger Agent (wie der
Prüfer in diesem Repo) nachweislich lohnt.

**Eine Entscheidungsregel, aus alledem destilliert:**

1. **Standardmäßig klein anfangen**: eine Aufgabe geht an EINEN starken Agenten (Fable/Opus) im
   durchgehenden Kontext, wenn die Aufgabe (a) ein zusammenhängendes kreatives Ergebnis ist, das
   eine einzelne Instanz im Kopf behalten muss (UI, Design, Architekturentscheidung), UND/ODER
   (b) sich nicht sauber in unabhängige, parallele Teilstücke zerlegen lässt.
2. **Auf ein Orchestrator+Arbeiter-Team eskalieren**, wenn mindestens EINE messbare Bedingung
   zutrifft: die Aufgabe zerfällt in wirklich unabhängige Teilstücke, die parallel laufen können
   (Breite statt Tiefe); oder die Aufgabe ist länger als das, was ein Modell in einem Durchgang
   zuverlässig schafft (die gemessene Grenze verschiebt sich, war Anfang 2025 bei grob vier Stunden
   Mensch-Äquivalent); oder mehr als grob zehn Dateien / drei unabhängige Teilaufgaben stehen an
   (Anthropics eigene Schwelle für Subagenten).
3. **Ein unabhängiger Prüfer bleibt in praktisch jedem Fall lohnend**, weil sein Nutzen aus einer
   anderen Quelle kommt als der aus Parallelität: er hat KEINEN geteilten Kontext mit dem Autor und
   findet deshalb Fehler, die der Autor strukturell nicht sehen kann. Das ist unabhängig davon, ob
   Punkt 1 oder 2 gilt — genau das ist heute schon die Rolle des Prüfers in diesem Repo.
4. **Arbeitsaufträge an Arbeiter bleiben klein und prüfbar**, nie "viel Spielraum" — je enger der
   Auftrag, desto billiger eine Wiederholungsrunde (eine Wiederholung rechnet immer den gesamten
   bisherigen Verlauf neu ab) und desto weniger Raum für Zieldrift über viele Runden.
5. **Die Denkstufe (Reasoning-Effort) steigt nur bei nachgewiesenem Bedarf**, nie standardmäßig auf
   Maximum — der Zusammenhang zwischen mehr Denk-Tokens und mehr Qualität ist nachweislich
   logarithmisch: doppelte Denk-Tokens verdoppeln nicht die Genauigkeit, kosten aber doppelt so
   viel. Das erklärt die vom Nutzer beobachtete GPT/Astra-Erfahrung ("Tokens sofort weg, kaum
   Fortschritt") als einen dokumentierten, erwarteten Effekt hoher Stufen — kein Zufall.

Kurz: Die Welt hat 2025/2026 nicht "Multi-Agenten-Systeme sind schlecht" gemessen, sondern
"Multi-Agenten-Systeme kosten das 7- bis 15-Fache und lohnen sich nur, wo Breite, Parallelität oder
unabhängige Prüfung den Aufpreis wert sind — bei zusammenhängender, kreativer Arbeit wie Frontend
verlieren sie meist gegen einen einzelnen starken Agenten." Das deckt sich mit dem, was der Nutzer
beobachtet hat, und liefert eine Regel, die dieses Repo für die nächste Produkt-Generation
anwenden kann, statt nur ein Gefühl zu bestätigen.
