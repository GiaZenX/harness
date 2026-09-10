# FR-0089 -- Recherche A: was das Feld gemessen hat (Multi-Agent vs. ein starker Agent)

Auftrag: FR-0089. Diese Datei ist reine Web-Recherche (read-only), kein Experiment und
keine Entscheidung. Zitate stehen im Original (Englisch), die Einordnung ist Deutsch.
"Gesehen am" ist das Datum dieser Recherche-Sitzung (2026-09-06), nicht notwendig das
Publikationsdatum -- letzteres steht dazu, wo die Quelle es nennt.

Ein Wort zur Vorsicht: mehrere unten zitierte Sekundärquellen (Medium-Artikel, Blogs)
tragen Veröffentlichungsdaten in der zweiten Jahreshälfte 2026 und referenzieren Paper
ohne verifizierbaren Fundort für die genaue Zahl. Wo das der Fall ist, steht es explizit
dabei ("Sekundärquelle, nicht am Primärpaper geprüft"), damit niemand eine Blog-Paraphrase
für ein Primärergebnis hält.

---

## 1. Anthropics eigene Veröffentlichungen

### 1.1 "How we built our multi-agent research system"
- **Quelle:** Anthropic Engineering Blog, https://www.anthropic.com/engineering/multi-agent-research-system
- **Gesehen am:** 2026-09-06 (Artikel selbst datiert auf Juni 2025)
- **Gemessene Zahl / Aussage (Original):**
  - "agents typically use about 4× more tokens than chat interactions, and multi-agent
    systems use about 15× more tokens than chats"
  - "a multi-agent system with Claude Opus 4 as the lead agent and Claude Sonnet 4
    subagents outperformed single-agent Claude Opus 4 by 90.2%" (auf Anthropics eigenem
    internen Recherche-Eval, nicht auf einem öffentlichen Coding-Benchmark)
  - Wo Multi-Agent NICHT gewinnt: "most coding tasks involve fewer truly parallelizable
    tasks than research" und "some domains that require all agents to share the same
    context or involve many dependencies between agents are not a good fit for
    multi-agent systems"; zusätzlich: "LLM agents are not yet great at coordinating and
    delegating to other agents in real time"
  - Wann es sich lohnt: Aufgaben mit "heavy parallelization, information that exceeds
    single context windows, and interfacing with numerous complex tools" -- und
    ausdrücklich: die Ökonomie trägt nur bei hochwertiger Arbeit (Rechercheaufgaben wie
    Legal Due Diligence, Wettbewerbsanalyse, biomedizinische Literaturreviews), nicht bei
    "consumer-grade Q&A", die den Multiplikator nicht tragen kann.
- **Bedeutung für einen Harness mit Fable/Opus-Orchestrator + Opus/Sonnet-Workern:**
  Anthropics eigene Zahl (15x Tokens) ist eine UNTERGRENZE für den Multiplikator, den
  auch dieser Harness zahlt -- und sie stammt aus einem Anwendungsfall (breite,
  parallelisierbare Recherche), der dem hier gebauten Coding-Fall ausdrücklich NICHT
  entspricht: Anthropic selbst nennt Coding als Fall mit wenig echter Parallelität.

### 1.2 "Building effective agents"
- **Quelle:** Anthropic Engineering Blog, https://www.anthropic.com/engineering/building-effective-agents
- **Gesehen am:** 2026-09-06
- **Gemessene Zahl / Aussage (Original):**
  - "Agentic systems often trade latency and cost for better task performance, and you
    should consider when this tradeoff makes sense."
  - "you should consider adding complexity only when it demonstrably improves outcomes."
  - "For many applications, however, optimizing single LLM calls with retrieval and
    in-context examples is usually enough."
  - "Start with simple prompts, optimize them with comprehensive evaluation, and add
    multi-step agentic systems only when simpler solutions fall short."
  - "This might mean not building agentic systems at all."
- **Bedeutung:** Das ist keine Zahl, sondern eine Grundregel direkt vom Hersteller der
  Modelle, die dieser Harness einsetzt: Komplexität ist nur gerechtfertigt, wenn sie
  MESSBAR bessere Ergebnisse bringt -- die Beweislast liegt bei der Mehr-Agenten-Seite,
  nicht bei der Ein-Agenten-Seite.

### 1.3 Claude Code Doku zu Subagents
- **Quelle:** https://code.claude.com/docs/en/sub-agents (offizielle Doku, vormals unter
  docs.claude.com/.../sub-agents, per 301-Redirect umgezogen)
- **Gesehen am:** 2026-09-06
- **Gemessene Zahl / Aussage (Original):**
  - Nutzen: "Preserve context by keeping exploration and implementation out of your main
    conversation" -- "only the summary returns to your main conversation, while the
    verbose intermediate work stays isolated"
  - Kostenkontrolle primär über MODELLWAHL, nicht über Architektur: "Control costs by
    routing tasks to faster, cheaper models like Haiku"
  - Ausdrückliche Warnung gegen Subagenten bei bestimmten Aufgabenformen: "Use the main
    conversation when: ... Multiple phases share significant context, such as planning,
    implementation, and testing ... Latency matters. A subagent that isn't a fork starts
    fresh and may need time to gather context"
  - Kein Fork-Subagent verliert Kontext neu aufbauen zu müssen; ein normaler (Non-Fork)
    Subagent dagegen: "don't inherit your conversation history ... they start fresh and
    focused on their delegated task" -- exakt der Mechanismus, den der Nutzer als
    "weniger gute Ideen, mehr Runden" beschreibt.
- **Bedeutung:** Die Doku bestätigt strukturell, was der Nutzer beobachtet: ein Worker,
  der ohne die Historie der Orchestrator-Session anfängt, hat einen echten
  Informationsnachteil bei Aufgaben, die auf geteiltem Kontext beruhen (z. B. "passt das
  zum Rest des Frontends?") -- das ist kein Modellversagen, sondern ein
  Architekturmerkmal, das die eigene Doku benennt.

---

## 2. Kritische Gegenstimmen mit Messungen

### 2.1 Cognition: "Don't Build Multi-Agents"
- **Quelle:** https://cognition.com/blog/dont-build-multi-agents (Autor: Walden Yan,
  Cognition/Devin), Original-URL cognition.ai leitet per 301 dorthin um
- **Datum:** 12. Juni 2025 (Artikel selbst datiert)
- **Gesehen am:** 2026-09-06
- **Kernaussage (Original):**
  - "Actions carry implicit decisions, and conflicting decisions carry bad results."
  - "The decision-making ends up being too dispersed and context isn't able to be shared
    thoroughly enough between the agents."
  - Konkretes Beispiel (genau der Frontend-Fall, den der Nutzer beschreibt): beim Bau
    eines Flappy-Bird-Klons baute ein Subagent einen Mario-artigen Hintergrund, während
    ein zweiter Subagent einen Vogel baute, der stilistisch nicht dazu passte --
    "Subagent 1 and subagent 2 cannot see what the other was doing and so their work
    ends up being inconsistent."
  - Zwei Prinzipien, die Multi-Agent-Systeme regelmäßig verletzen: "Share context, and
    share full agent traces, not just individual messages."
  - Empfehlung: "The simplest way to follow the principles is to just use a
    single-threaded linear agent," und das trage für die meisten Anwendungen sehr weit
    ("will get you very far").
  - Ein Jahr später (zitiert über eine spätere Aussage desselben Autors auf X, nicht
    mehr im Originalartikel) relativiert Yan: manche Aufbauten funktionieren doch --
    und zwar solche, in denen EIN Hauptstrang den Zustand hält und Subagenten
    zustandslose, eng geschnittene Arbeiter sind. Das deckt sich mit Punkt 3 unten
    (schmale, testbare Slices statt Spielraum).
- **Bedeutung:** Das ist die direkteste Bestätigung des Nutzer-Befunds aus einer
  externen, unabhängigen Quelle: bei Aufgaben, die stilistische/gestalterische
  Kohärenz brauchen (UI, Design), zerfällt verteilte Entscheidungsgewalt genau so, wie
  der Nutzer es beim Frontend-Vergleich beobachtet hat -- nicht weil die Worker
  schwächer sind, sondern weil sie sich nicht sehen.

### 2.2 MAST -- "Why Do Multi-Agent LLM Systems Fail?"
- **Quelle:** arXiv 2503.13657, https://arxiv.org/abs/2503.13657 (NeurIPS 2025 Poster);
  Zahlen unten aus der Huggingface-Paper-Zusammenfassung https://huggingface.co/papers/2503.13657,
  da die reine PDF-Textextraktion die Tabellen nicht zuverlässig auflöste
- **Gesehen am:** 2026-09-06
- **Gemessene Zahl / Aussage (Original, so übernommen):**
  - "41% to 86.7% failure rate on 7 state-of-the-art (SOTA) open-source MAS" --
    gemessen über sieben populäre Multi-Agent-Frameworks (u. a. MetaGPT, ChatDev),
    1600+ annotierte Traces, 150 davon von menschlichen Gutachtern kodiert
    (Interrater-Übereinstimmung Cohen's Kappa = 0.88).
  - 14 Fehlermodi in drei Kategorien: (i) system design issues (u. a. "disobeying task
    specification" 11.8%, "step repetition" 15.7%, "unrecognized termination
    conditions" 12.4%), (ii) inter-agent misalignment (u. a. "task derailment" 7.4%,
    "reasoning-action mismatch" 13.2%), (iii) task verification ("incomplete
    verification" 8.2%, "incorrect verification" 9.1%, "premature termination" 6.2%).
  - Einfache Interventionen reichen NICHT: eine verbesserte Rollen-Spezifikation bei
    ChatDev brachte "+9.4% increase in overall task success rate", eine zusätzliche
    High-Level-Verifikation "+15.6%" auf einem Benchmark -- beides deutlich unter dem
    41-87%-Ausgangsfehler, und die Autoren schließen: "more substantial improvements are
    needed" als taktische Einzelfixes.
- **Bedeutung:** Das ist die stärkste quantitative Stütze für die Grundfrage des
  Nutzers: die MEHRHEIT der beobachteten Fehler in Multi-Agent-Systemen ist nicht
  Modellschwäche, sondern System-/Koordinationsdesign -- also genau die Ebene, auf der
  ein Harness wie dieser (Orchestrator + mehrere Worker + Verifier über mehrere Runden)
  ansetzt und potenziell verwundbar ist.

### 2.3 Benchmarkvergleich Single- vs. Multi-Agent auf SWE-bench-artigen Aufgaben
- **Quelle:** Sekundärquelle -- Medium-Artikel "Single-Agent vs Multi-Agent Systems:
  When Coordination Helps, Hurts, and Pays Off" (Autor: Mjgmario),
  https://medium.com/@mjgmario/single-agent-vs-multi-agent-systems-when-coordination-helps-hurts-and-pays-off-57735ee7916d;
  Basis-Trajektorienzahl separat primärquellenbasiert (arXiv 2509.23586, "Reducing Cost
  of LLM Agents with Trajectory Reduction")
- **Gesehen am:** 2026-09-06
- **Gemessene Zahl / Aussage:**
  - Kosten-Baseline (arXiv 2509.23586): eine durchschnittliche Single-Agent-Trajektorie
    zur Lösung EINES GitHub-Issues auf SWE-bench Verified umfasst "48.4K tokens in 40
    steps", davon allein 30.4K Tokens in Tool-Nachrichten.
  - Multi-Agent-Ansätze starten laut der Medium-Zusammenfassung bei "4-220x this
    baseline cost" -- eine sehr grobe Spanne, NICHT am Primärpaper nachgeprüft.
  - Ergebnisqualität: "SWE-bench Verified shows slight degradation across all
    multi-agent system architectures (-2% to -15%), consistent with high single-agent
    baselines (>45%) that leave limited room for coordination gains."
  - Einordnung derselben Quelle: "On focused coding tasks like SWE-bench, single agents
    tend to win. Single-agent workflows fit most coding tasks because code changes are
    usually sequential and stateful."
- **Vorsicht:** Dies ist eine Sekundärquelle (Blog, kein referiertes Paper); die
  genauen Prozentzahlen (-2% bis -15%, 4-220x) konnten in dieser Recherche NICHT gegen
  ein Primärpaper verifiziert werden. Sie werden hier als Hinweis, nicht als belastbarer
  Beleg geführt.
- **Bedeutung:** Selbst mit dem Vorsichtshinweis: die Richtung deckt sich mit Anthropics
  eigener Aussage (1.1) und mit MAST (2.2) -- bei sequenziellen, zustandsbehafteten
  Coding-Aufgaben mit bereits hoher Single-Agent-Erfolgsquote ist der Spielraum für
  Koordinationsgewinne klein, das Mehrkosten-Risiko groß.

### 2.4 Fehlerfortpflanzung über mehrere Schritte/Hops
- **Quelle:** mehrere Sekundärzusammenfassungen; die belastbarste Primärgröße ist rein
  mathematisch (Multiplikation von Pro-Schritt-Genauigkeiten), zusätzlich arXiv
  2603.04474 "From Spark to Fire: Modeling and Mitigating Error Cascades in LLM-Based
  Multi-Agent Collaboration"
- **Gesehen am:** 2026-09-06
- **Gemessene Zahl / Aussage:**
  - Reine Rechnung, oft zitiert: bei 95% Pro-Schritt-Genauigkeit über zehn Schritte:
    0.95^10 ≈ 59%; bei 90%: 0.90^10 ≈ 35%; bei 85%: 0.85^10 ≈ 20% End-zu-Ende-Erfolg.
    Das ist Arithmetik, kein empirischer Fund, aber sie erklärt, warum mehr Hops
    (Orchestrator → Worker → Verifier → Nacharbeit) bei gleicher Einzelschritt-Güte
    strukturell schlechter abschneiden können als ein Agent mit weniger Übergaben.
  - Aus "From Spark to Fire": kleinere Abweichungen bei Faktentreue, ob selbst erzeugt
    oder von außen eingebracht, werden "repeatedly cited and reused within the
    interaction chain," und konvergieren über mehrere Interaktionsrunden zu einem
    "false consensus at the system level" -- also nicht nur Fehlerübertragung, sondern
    gegenseitige Bestätigung eines Fehlers zwischen Agenten.
- **Bedeutung:** Ein Verifier, der einen Fehler übernimmt statt ihn zu erkennen (weil
  er dem Bericht des Workers vertraut), verstärkt genau diesen Effekt -- die
  Rollentrennung (Umsetzer/Prüfer) dieses Repos wirkt dagegen, ist aber kein Garant.

---

## 3. Belege zur WORKER-Qualität: schwächere Modelle als Ausführende, Spielraum vs. enge Slices

### 3.1 Aufgaben-Granularität, kontrollierte Pilotstudie
- **Quelle:** arXiv 2608.23395, "Right-Sizing LLM-Agent Decomposition in VAT
  Determination: A Pilot Controlled Sweep", https://arxiv.org/html/2608.23395
- **Gesehen am:** 2026-09-06
- **Gemessene Zahl / Aussage:**
  - Fünf Konfigurationen, je 40 Fälle x 5 Wiederholungen (200 Läufe/Konfiguration):
    S0 = ein Agent ohne Orchestrator; C1 = ein breiter orchestrierter Worker (alle 5
    Teilaufgaben); C2 = zwei Worker; C3 = drei Worker; C4 = fünf Worker (einer pro
    Teilaufgabe).
  - Ergebnisgenauigkeit (Final-Answer Accuracy): S0 = 0.755, C1 = 0.720, C2 = 0.830,
    C3 = 0.830, C4 = 0.770 -- ein NICHT-monotoner Verlauf mit einem mittleren Optimum
    bei zwei bis drei Workern.
  - Kosten: C1 (ein Worker) am billigsten mit 11.317 Tokens, C4 (fünf Worker) am
    teuersten mit 15.845 Tokens; Latenz steigt monoton von 12.1s (C1) auf 18.4s (C4).
  - Zu grob (C1, ein Worker für alles) UND zu fein (C4, ein Worker pro Mikroaufgabe)
    schneiden schlechter ab als die Zwischenstufen -- die Autoren empfehlen als
    "candidate heuristic, not a rule": die Schnittstelle dort zu legen, wo Vorbereitung
    (Klassifikation) endet und Synthese (Bewertung/Zusammenführung) beginnt.
  - Kontrollversuch: gab man dem einzelnen Agenten (S0) das gleiche Token-Budget wie
    C2, blieb die Genauigkeit bei 0.765 -- UNTER C2s 0.830 -- was nahelegt, dass ein
    Teil des Vorteils von C2 nicht am reinen Token-Budget hängt, sondern an der
    Aufteilung selbst; die Autoren betonen aber, die Konfidenzintervalle ließen keine
    endgültige Aussage zu.
- **Bedeutung für "Spielraum" vs. "enge, testbare Slices":** Diese eine kontrollierte
  Studie (Pilotgröße, ein Anwendungsfall -- Steuerklassifikation, KEIN Coding) stützt
  tendenziell die Position "mittelgroße, klar geschnittene Slices schlagen sowohl einen
  einzelnen Alleskönner als auch zu viele Mikro-Worker" -- deckt sich mit der
  Zielsetzung in FR-0089 ("workers with narrow testable slices instead of Spielraum"),
  aber die Studie ist zu klein und zu domänenfremd, um das als belastbaren Beweis für
  Coding-Harnesses zu behaupten.

### 3.2 Schwacher Orchestrator über starken Workern
- **Quelle:** Sekundärzusammenfassung mehrerer Orchestrator-Worker-Paper (u. a. AOrchestra,
  CASTER), gefunden über Websuche, keine einzelne Primärquelle mit voller Prüfung
- **Gesehen am:** 2026-09-06
- **Gemessene Zahl / Aussage:**
  - "replacing a strong orchestrator with a weaker model (like Qwen3-8B) while keeping
    stronger sub-agents yields lower accuracy (56.97% vs. 80.00%), though still better
    than the weaker model alone" -- Zahl aus Sekundärzusammenfassung, nicht selbst am
    Primärpaper geprüft.
  - Qualitative Einordnung, mehrfach wiederholt: "Below a certain capacity threshold, no
    orchestration strategy compensates for model weakness," und: ein schwacher
    Orchestrator "quietly fails — it passes bad output downstream because it never
    really checked."
- **Bedeutung:** Das spiegelt die Kette in diesem Harness: der Orchestrator (Fable/Opus)
  ist bewusst das stärkste Glied, die Ausführung liegt bei Sonnet -- das ist nach
  diesem (schwach belegten) Fund die richtige Reihenfolge der Stärke, sagt aber
  nichts darüber, ob ein STARKER Orchestrator einen SCHWACHEN Worker vollständig
  kompensieren kann, wenn der Worker mit zu viel "Spielraum" arbeitet statt mit enger
  Spezifikation.

---

## 4. Frontend/UI und Design-Kohärenz

Hier ist die Literaturlage dünn: es gibt (Stand dieser Recherche) **kein** dediziertes
Benchmark-Paper "Single-Agent vs Multi-Agent für Frontend/UI-Design" mit Zahlen. Was
vorliegt:

### 4.1 Cognitions Flappy-Bird-Beispiel (siehe 2.1)
Das bleibt der konkreteste, wenn auch anekdotische Beleg genau für den vom Nutzer
beschriebenen Fall: verteilte visuelle/stilistische Entscheidungen (Hintergrund vs.
Spielfigur) driften auseinander, weil die Subagenten sich nicht sehen. Das ist keine
Zahl, sondern ein dokumentiertes Fallbeispiel von einer Firma, die selbst Coding-Agenten
baut (Devin/Cognition).

### 4.2 Allgemeines Prinzip aus MAS-Literatur (Cognition, Anthropic)
Beide oben zitierten Quellen (1.1 und 2.1) benennen unabhängig voneinander denselben
Mechanismus für Aufgaben mit hoher gegenseitiger Abhängigkeit ("many dependencies
between agents", "share full agent traces"): geteilter EINZEL-Kontext gewinnt, sobald
Kohärenz über viele kleine Entscheidungen hinweg zählt -- und UI/Design ist per
Definition eine Aufgabe mit vielen impliziten, gegenseitig abhängigen
Stil-Entscheidungen (Farbwahl, Abstände, Tonalität, Wiederverwendung von Komponenten).
- **Bedeutung:** Die Literatur STÜTZT die Intuition des Nutzers strukturell (geteilte
  Design-Entscheidungen wollen EINEN Kontext), liefert aber KEINE Kennzahl (Tokens,
  Zeit, Qualitätsurteil) speziell für Frontend-Aufgaben. Genau diese Lücke ist der
  Grund, warum FR-0089 selbst ein kontrolliertes Experiment fordert (Punkt 2 im
  FR-Ziel) -- die Literatur kann diesen Teil der Frage nicht beantworten, nur die
  Richtung stützen.

### 4.3 Was NICHT als Frontend-Beleg zählt
Bei der Recherche tauchten Zahlen zu Multi-Agent-Robustheit unter Last auf (z. B. eine
medizinische/klinische Studie mit Genauigkeitswerten wie "90.6% at 5 tasks vs. 65.3% at
80 tasks" für Multi-Agent gegenüber stark fallender Single-Agent-Genauigkeit). Diese
stammen aus einem KLINISCHEN Kontext (Skalierung auf viele parallele, UNABHÄNGIGE
Fälle), nicht aus UI/Design-Arbeit, und werden hier bewusst NICHT als Frontend-Beleg
verwendet -- sie würden die falsche Analogie stützen (viele unabhängige Fälle statt
eine kohärente Oberfläche).

---

## 5. OpenAI Codex / GPT High-Reasoning-Effort: Tokens ohne Fortschritt

### 5.1 Herstellerseitige Anleitung (Codex Prompting Guide)
- **Quelle:** OpenAI Developers Cookbook, "Codex Prompting Guide",
  https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide
- **Gesehen am:** 2026-09-06
- **Gemessene Zahl / Aussage (Original, so übernommen):**
  - "We recommend 'medium' reasoning effort as a good all-around interactive coding
    model that balances intelligence and speed."
  - Effort-Level: low / medium / high / xhigh, wobei hoher/sehr hoher Effort für die
    "hardest tasks" mit "longer-running autonomy" reserviert ist ("very capable and will
    work autonomously for hours").
  - Explizit zu GPT-5.1-Codex-Max: "achieves better performance than GPT-5.1-Codex with
    the same reasoning effort, while using 30% fewer thinking tokens" -- also ein
    dokumentierter Fortschritt (weniger Denk-Tokens bei gleicher oder besserer
    Leistung) zwischen Modellgenerationen, aber KEINE explizite Warnung im
    Herstellertext davor, dass hoher Effort ohne Fortschritt Tokens verbrennen kann.
- **Bedeutung:** Der Hersteller selbst empfiehlt "medium" als Standard und reserviert
  "high"/"xhigh" für wirklich harte, lang laufende Aufgaben -- ein impliziter Hinweis,
  dass hoher Effort NICHT der Normalfall sein soll, aber keine Zahl zu Leerlauf-Runden.

### 5.2 Dokumentierte Nutzerbeschwerde (Community, nicht Hersteller-Messung)
- **Quelle:** GitHub Issue openai/codex #14593, "Burning tokens very fast",
  https://github.com/openai/codex/issues/14593
- **Gesehen am:** 2026-09-06
- **Gemessene Zahl / Aussage (Original, so übernommen):**
  - "just by writing 1 or 2 prompts, usage drops by 1%, within 2 hours of working I
    managed to burn through ~20% of my tokens" -- gemeldet bei GPT-5.3/5.4 mit hohem
    Reasoning-Effort, einfachen Prompts.
  - Keine Antwort/Klärung von OpenAI im Issue; als "bug"/"rate-limits" gelabelt, aber
    ohne Auflösung geschlossen.
- **Vorsicht:** Ein Einzelbericht ist KEINE Messung im wissenschaftlichen Sinn, sondern
  ein anekdotischer Beleg dafür, dass das Phänomen ("viele Tokens, wenig sichtbarer
  Fortschritt bei hohem Effort") in freier Wildbahn beobachtet und gemeldet wird, ohne
  dass der Hersteller es bislang mit Zahlen erklärt oder widerlegt hat.
- **Bedeutung für den Nutzer-Befund zu Astra/GPT:** Das deckt sich mit der Beobachtung
  des Nutzers ("Tokens sofort weg, kaum Fortschritt"), bleibt aber unbelegt im Sinne
  einer kontrollierten Messung -- weder Hersteller noch unabhängige Forschung liefern
  bislang eine Zahl zu "wie oft hoher Effort in eine Schleife ohne Fortschritt läuft".

---

## Was die Evidenz stützt

Fünf Punkte sind über mehrere unabhängige Quellen hinweg konsistent, nicht nur von
einer einzigen Stimme behauptet:

1. **Mehr Agenten kosten strukturell mehr Tokens, nicht nur gelegentlich.** Anthropics
   eigene Zahl (15x gegenüber Chat, 4x für einfache Agenten) und die SWE-bench-Baseline
   (48.4K Tokens/40 Schritte für EINEN Agenten, mit Multi-Agent-Aufschlägen laut
   Sekundärquelle im niedrigen bis sehr hohen einstelligen bis niedrigen dreistelligen
   Vielfachen) zeigen dieselbe Richtung aus zwei unabhängigen Ökosystemen.
2. **Bei sequenziellen, zustandsbehafteten Aufgaben mit bereits hoher
   Single-Agent-Erfolgsquote ist der Spielraum für Koordinationsgewinne klein bis
   negativ.** Anthropic nennt Coding namentlich als Fall mit "fewer truly
   parallelizable tasks"; die SWE-bench-Sekundärquelle berichtet leichte Verschlechterung
   (-2% bis -15%) für Multi-Agent-Architekturen gegenüber Single-Agent-Baselines >45%.
   Das trifft den Kern der Nutzerfrage direkt: Coding/Frontend ist eher dieser Fall als
   der Recherche-Fall, für den Anthropic sein eigenes System gebaut hat.
3. **Die MEHRHEIT der gemessenen Multi-Agent-Fehler ist Koordinations-/Design-Fehler,
   nicht Modellschwäche.** MAST: 41-87% Fehlerquote über sieben Systeme, mit
   Fehlerkategorien wie Spezifikationsverstoß, Schritt-Wiederholung,
   Rollenkonflikt -- und einfache Einzelfixes bringen nur zweistellige
   Prozentpunkt-Verbesserungen, nicht die Lösung.
4. **Geteilter, ununterbrochener Kontext ist der von mehreren Quellen unabhängig
   benannte Schutzmechanismus gegen genau die Inkohärenz, die der Nutzer beim Frontend
   beschreibt.** Cognitions Flappy-Bird-Beispiel und Anthropics eigene Formulierung
   ("domains that require all agents to share the same context ... are not a good fit")
   zeigen von zwei Seiten (Kritiker und Hersteller) denselben Mechanismus.
5. **Aufgaben-Granularität hat ein Optimum, das weder "ein Worker für alles" noch
   "ein Worker pro Mikroschritt" ist** -- die VAT-Pilotstudie zeigt einen
   nicht-monotonen Verlauf mit mittlerer Worker-Zahl vorn, was die FR-0089-Idee
   "schmale, testbare Slices statt Spielraum" eher stützt als widerlegt, wenn auch nur
   mit einer kleinen Studie aus einer fachfremden Domäne.

## Was die Evidenz nicht klärt

1. **Keine der gefundenen Quellen misst genau den Fall dieses Repos**: Fable/Opus als
   Orchestrator, Sonnet als Worker, ein separater Verifier, mehrere Nacharbeitsrunden,
   auf Coding-/Frontend-Aufgaben. Alle Zahlen sind Analogien aus verwandten, aber
   verschiedenen Aufbauten (Anthropics Recherche-System, generische MAS-Frameworks wie
   MetaGPT/ChatDev, eine Steuerklassifikations-Pilotstudie).
2. **Keine Quelle liefert eine Zahl zu Design-/UI-Kohärenz speziell.** Das ist die
   größte Lücke gegenüber der Nutzerfrage: der Frontend-Vergleich, den der Nutzer
   selbst beobachtet hat, ist bislang nirgends im Feld als kontrolliertes Experiment
   gemessen worden -- nur als Einzelbeispiel (Flappy Bird) und als allgemeines Prinzip.
   Das ist genau die Lücke, die das im FR-0089-Ziel geforderte eigene Experiment
   (Punkt 2) schließen soll.
3. **Kein belastbares Verhältnis "wie viel Spielraum ist zu viel"** für Coding-Worker:
   die einzige kontrollierte Granularitätsstudie (3.1) ist klein (40 Fälle), aus einer
   fachfremden Domäne (Steuerrecht, kein Code) und selbst von den Autoren als
   "candidate heuristic, not a rule" markiert.
4. **Keine belastbare Messung zu OpenAI/Codex-Effort-Schleifen.** Der Hersteller
   empfiehlt "medium" als Default, aber es gibt keine veröffentlichte Zahl dazu, wie oft
   "high"/"xhigh" in einer Schleife ohne Fortschritt endet -- nur eine einzelne,
   ungeklärte Nutzerbeschwerde.
5. **Die Anthropic-90.2%-Zahl ist ein interner Eval auf einer Recherche-Aufgabe**, kein
   öffentlich reproduzierbarer Benchmark -- sie zeigt, dass Multi-Agent GEWINNEN kann,
   aber nicht, unter welchen Bedingungen genau, und sicher nicht für Coding.
6. **Kein Vergleich in der Literatur behandelt explizit "ein starker Agent mit viel
   Kontext" gegen "Orchestrator + schwächere Worker MIT engen, testbaren Slices"** --
   die meisten zitierten Studien vergleichen entweder Ein-Agent gegen Multi-Agent mit
   Spielraum, oder verschiedene Granularitäten ohne einen echten Ein-Agent-Vergleich
   mit gleichem Budget. Genau diese Zelle im Vergleichsraster (Punkt 3 im
   FR-0089-Ziel: "workers with narrow testable slices") ist am dünnsten belegt und am
   direktesten das, was das geforderte eigene Experiment liefern muss.

Kurz: das Feld stützt die RICHTUNG der Nutzer-Intuition (kleinere/keine
Orchestrierung für sequenzielle, kohärenzkritische Aufgaben wie Frontend; Vorsicht bei
hohem Reasoning-Effort ohne Fortschrittskontrolle), liefert aber keine einzige Zahl, die
direkt auf DIESEN Harness übertragbar wäre. Das kontrollierte Experiment, das FR-0089
selbst fordert, bleibt notwendig -- die Recherche ersetzt es nicht, sie begründet nur,
warum es sich lohnt.
