# FR-0091 Research A: Was Anthropic selbst zur Modellwahl sagt (Stand September 2026)

Alle Quellen sind offizielle Anthropic-Seiten (claude.com, code.claude.com, platform.claude.com).
Abgerufen am 2026-09-11, sofern nicht anders vermerkt. Unterscheidung: "Anthropic sagt" = wörtliches
Zitat/direkte Aussage; "Anthropic legt nahe" = Schlussfolgerung aus dem Text, nicht wörtlich gesagt.

## 1. Die Stufen und wofür Anthropic sie vorsieht

Anthropic beschreibt vier Modellklassen ([claude.com/blog, "Claude models explained", publiziert 2026-07-24](https://claude.com/blog/claude-models-explained-choosing-the-best-model-for-your-use-case)):

- **Fable/Mythos** (Spitzenklasse): "Mythos is Anthropic's most capable model class, with frontier
  capabilities across domains." Wörtlich wichtig: Fable und Mythos sind **dieselbe zugrunde liegende
  Modellfamilie** in zwei Verpackungen — "The Mythos class ships in two packages of the same
  underlying model." Mythos ist für "trusted organizations handling dual-use cybersecurity and
  biology work", Fable trägt zusätzliche Schutzmechanismen für die breite Öffentlichkeit. Beide gelten
  laut Anthropic als besonders stark bei "coding, long-running agents", und bei bisher ungelösten
  Problemen.
- **Opus**: "Opus is our powerful model class for reasoning-intensive enterprise tasks." Führend bei
  Branchen-Benchmarks wie GDPval-AA (Wissensarbeit) und Terminal-Bench 2.1 (agentisches Programmieren).
- **Sonnet**: "Sonnet is our versatile model class for everyday tasks", empfohlen für
  "high-frequency customer facing workloads" und ausdrücklich auch für "high-volume sub-agents in
  multi-agent orchestration setups".
- **Haiku**: "Haiku is our lowest cost and fastest model class", für "high-frequency workloads where
  latency and cost matter."

Zur Abgrenzung Opus vs. Fable sagt Anthropic wörtlich: "The choice between Opus and Fable may not
seem clear on the surface, as both excel at coding, long-running agents, and knowledge work." Und:
"In real-world situations, larger models such as Fable tend to have more wisdom, creativity, and
writing skills despite having similar benchmark scores to models such as Opus." Die Eskalationsregel
dazu steht wörtlich so da: "The general rule of thumb is if your evals or internal testing show Opus
struggling on some tasks, then Fable is the answer." Umgekehrt: "If Opus already clears the quality
bar, then its speed and price profile may make it the better choice." Eine dritte, günstigere Route
nennt der Artikel als "Advisor-Strategie": "Sonnet 5 with a Fable 5 advisor is within 10% of Fable
5's score at 63% of the price."

Für Claude Code speziell sagt die Dokumentation ([code.claude.com/docs/en/model-config](https://code.claude.com/docs/en/model-config)):
"Fable 5.1 and Claude Fable 5 are the most capable models in Claude Code, suited to tasks larger
than a single sitting. They sustain long autonomous sessions, investigate before acting, and verify
their work more often than smaller models." Empfohlene Praktiken dort: "Describe the outcome, not
the steps", "Hand it ambiguous problems: root-cause investigations, outage debugging, and
architecture decisions", "Skip the verification reminders: it verifies its own work with less
prompting", "Size up larger tasks: give it work you would normally break into pieces."

## 2. Effort-Stufen: was die Doku sagt, dass sie verändern und kosten

Quelle: [platform.claude.com/docs/en/build-with-claude/effort](https://platform.claude.com/docs/en/build-with-claude/effort).
Anthropic sagt wörtlich, dass Effort **alle** Ausgabe-Tokens betrifft — Text, Werkzeugaufrufe und
Denk-Tokens ("The effort parameter affects all tokens in the response, including: Text responses...
Tool calls... Thinking"). Niedrigere Effort-Stufen bedeuten laut Doku weniger und knappere
Werkzeugaufrufe ("fewer and terser tool calls"), mehrere Operationen werden zu einem Aufruf
zusammengefasst, keine Präambel vor dem Handeln, knappe Abschlussmeldungen. Höhere Stufen erklären den
Plan vorher, liefern ausführlichere Zusammenfassungen und mehr Code-Kommentare.

Die offizielle Tabelle nennt fünf Stufen mit Standard-Einsatzzweck:

| Stufe | Beschreibung (Anthropic) | Typischer Einsatz laut Anthropic |
|---|---|---|
| `max` | "Absolute maximum capability with no constraints on token spending" | Tiefstes Reasoning, gründlichste Analyse |
| `xhigh` | "Extended capability for long-horizon work" | Lang laufende agentische/Coding-Aufgaben (über 30 Minuten), Token-Budgets im Millionenbereich |
| `high` | Entspricht dem Weglassen des Parameters (**Standard**) | Komplexes Reasoning, schwierige Coding-Probleme, agentische Aufgaben |
| `medium` | Moderate Token-Ersparnis | Agentische Aufgaben mit Balance aus Geschwindigkeit/Kosten/Leistung |
| `low` | Größte Effizienz, spürbare Fähigkeitseinbuße | Einfache Aufgaben, "such as subagents" |

Wichtiger Hinweis wörtlich: "Effort is a behavioral signal, not a strict token budget." Modellspezifisch
weicht die Empfehlung vom Standard ab — für **Claude Opus 5**: "step up to xhigh for demanding coding
and agentic work"; für **Claude Opus 4.7/4.8**: "Start with xhigh for coding and agentic use cases"
als generelle Empfehlung (nicht nur "demanding"); für **Sonnet 5**: High ist Standard, "Xhigh effort:
For the hardest coding and agentic tasks", Low für "chat and non-coding use cases". Bei `xhigh`/`max`
rät Anthropic zu einem großen `max_tokens` (Startwert 64k), "so the model has room to think and act
across subagents and tool calls." Bei Opus 5 lässt sich Thinking bei `xhigh`/`max` nicht abschalten
(400-Fehler).

Der begleitende Blogpost ([claude.com/blog, "Choosing a Claude model and effort level in Claude
Code", 2026-07-07](https://claude.com/blog/claude-model-and-effort-level-in-claude-code)) unterscheidet
Modellwahl von Effort so: "The model setting decides which weights handle your request, and it also
decides what each output token costs", während Effort steuert, "how much work Claude does on your
request overall" (Dateien lesen, Werkzeugaufrufe, Schritte vor Rückfrage). Konkreter Kostenbeleg:
"The high effort path generates roughly 7x more tokens to reach a higher confidence answer" (gleicher
Prompt, zwei Effort-Stufen).

## 3. Explizite Aussagen zu Aufgabengröße und Eskalation

Anthropic nennt zwei getrennte Eskalationssignale ([Blogpost s.o.]):

- **Modell wechseln**, wenn Claude "confidently wrong no matter how much context you give it" ist,
  bzw. bei "subtle bugs, unfamiliar domains, or architecture decisions": "If Claude has all the
  pertinent context and clearly tried and still got it wrong, that's a signal to pick a larger model."
- **Effort erhöhen**, wenn das Scheitern an Sorgfalt lag: Claude hat "skipped a file, not running the
  tests, or bailing on a refactor partway through."

Für Routineänderungen ("edits you can describe precisely, mechanical changes") empfiehlt Anthropic
kleinere Modelle (Sonnet); für mehrdeutige, mehrstufige Arbeit größere Modelle, da kleinere Modelle
"have to grind toward the limit of their ability, burning iterations."

Die Claude-Code-Best-Practices-Seite ([code.claude.com/docs/en/best-practices](https://code.claude.com/docs/en/best-practices))
liefert eine explizite Schwelle für den Planungsmodus, die sich als Aufgabengrößen-Kriterium lesen
lässt: "For tasks where the scope is clear and the fix is small (like fixing a typo, adding a log
line, or renaming a variable) ask Claude to do it directly." Planung lohnt sich, "when you're
uncertain about the approach, when the change modifies multiple files, or when you're unfamiliar with
the code being modified. If you could describe the diff in one sentence, skip the plan." Das ist eine
Aussage zu Planungsaufwand, nicht direkt zur Modell-/Effort-Wahl — Anthropic **verbindet diese beiden
Achsen an dieser Stelle nicht ausdrücklich** (siehe Lücken, Abschnitt 5).

Zur Selbstprüfung sagt dieselbe Seite wörtlich: "Claude stops when the work looks done. Without a
check it can run, 'looks done' is the only signal available... Give Claude something that produces a
pass or fail, and the loop closes on its own." Vier Eskalationsstufen für die Prüfungsstrenge werden
genannt: im selben Prompt, über eine `/goal`-Bedingung, als deterministisches Stop-Hook-Gate, oder
durch einen zweiten, unabhängigen Prüf-Subagenten ("a fresh model try to refute the result, so the
agent doing the work isn't the one grading it").

Ein älterer Anthropic-Engineering-Beitrag ([anthropic.com/engineering, "Effective harnesses for
long-running agents", **publiziert 2025-11-26**, bezieht sich noch auf "Opus 4.5"](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents))
— also vor der hier betrachteten Fable-5.1/Opus-5-Generation — beschreibt dieselbe Grundidee:
Agenten sollen inkrementell arbeiten und die Umgebung "in a clean state at the end of a session"
hinterlassen, statt "to one-shot the app" zu versuchen. Browser-Automatisierung wurde dort als
Verifikationswerkzeug empfohlen, weil reine Unit-Tests End-to-End-Fehler übersahen. Historisch, aber
inhaltlich konsistent mit der aktuellen Verifikations-Guidance.

## 4. Preistabelle (USD pro Million Tokens, [claude.com/pricing](https://claude.com/pricing), abgerufen 2026-09-11)

| Modell | Input | Output | Cache-Read | Cache-Write |
|---|---|---|---|---|
| Fable 5.1 | $10 | $50 | $0,25 | $12,50 |
| Opus 5 | $5 | $25 | $0,50 | $6,25 |
| Sonnet 5 | $2 | $10 | $0,20 | $2,50 |
| Haiku 4.5 | $1 | $5 | $0,10 | $1,25 |

Batch-Verarbeitung: "Save 50% with batch processing" (gilt modellübergreifend). Weitere Hinweise der
Seite: Prompt-Caching-Preise gelten für eine 5-Minuten-TTL, verlängertes Caching hat andere Sätze,
reine US-Inferenz kostet das 1,1-fache des Standardpreises, Fast Mode für Opus 5 kostet das Doppelte
des Standardsatzes.

## 5. Was Anthropic NICHT sagt (Lücken)

- **Keine einzelne, formale Entscheidungsmatrix** "Aufgabentyp × Modell × Effort" mit klaren Zellen für
  die vier Aufgabengrößen aus der Fragestellung (kleine Änderung / Multi-Datei-Feature /
  repo-weite Analyse / Architektur-Entscheidung). Die Doku trennt zwei unabhängige Heuristiken —
  Planungsmodus-Schwelle (Aufgabengröße) und Modell-vs-Effort-Eskalation (Fehlerursache) — verknüpft
  sie aber an keiner gefundenen Stelle explizit zu einer gemeinsamen Tabelle.
- **Keine öffentliche, kosten-normierte Benchmark-Tabelle**, die Fable/Opus/Sonnet bei gleicher
  Effort-Stufe für autonomes Programmieren direkt vergleicht (die einzige konkrete Zahl ist die
  "63 % des Preises bei 10 % Qualitätsverlust"-Aussage zur Advisor-Kombination Sonnet 5 + Fable-5-Berater).
  Prozentangaben zu Terminal-Bench 2.1 oder GDPval-AA je Modell wurden auf den geprüften Seiten nicht
  genannt.
- **Kein Wort zur Wahl zwischen Fable 5.1 und dem älteren Fable 5** speziell für Coding-Aufgaben
  außerhalb der allgemeinen Aussage, dass beide "the most capable models in Claude Code" sind; ein
  Migrationsgrund (Preis, Geschwindigkeit, Fähigkeit) wird auf den geprüften Seiten nicht benannt.
- **Keine Aussage zu Subagenten-Modellwahl nach Effort-Stufe kombiniert**: Die Sub-Agents-Doku nennt
  `model:` (Alias/ID/`inherit`) und empfiehlt Haiku "for cost control", aber keine Effort-Empfehlung
  speziell für Subagenten-Frontmatter — nur die allgemeine Effort-Tabelle erwähnt "such as subagents"
  einmal unter `low`.
- **Keine Aussage darüber, ob/wie sich die "advisor"-Kostenersparnis auf Coding-Subagenten in Claude
  Code übertragen lässt** — die 63-%-Zahl stammt aus dem allgemeinen Modell-Blogpost, nicht aus der
  Claude-Code-Dokumentation.

## Quellen

- [Claude models explained: choosing the best model for your use case](https://claude.com/blog/claude-models-explained-choosing-the-best-model-for-your-use-case) — claude.com, publiziert 2026-07-24, abgerufen 2026-09-11
- [Choosing a Claude model and effort level in Claude Code](https://claude.com/blog/claude-model-and-effort-level-in-claude-code) — claude.com, publiziert 2026-07-07, abgerufen 2026-09-11
- [Model configuration - Claude Code Docs](https://code.claude.com/docs/en/model-config) — code.claude.com, abgerufen 2026-09-11
- [Create custom subagents - Claude Code Docs](https://code.claude.com/docs/en/sub-agents) — code.claude.com, abgerufen 2026-09-11
- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices) — code.claude.com, abgerufen 2026-09-11
- [Effort - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/effort) — platform.claude.com, abgerufen 2026-09-11
- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — anthropic.com/engineering, publiziert 2025-11-26, abgerufen 2026-09-11
- [Claude Pricing](https://claude.com/pricing) — claude.com, abgerufen 2026-09-11
