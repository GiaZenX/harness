# FR-0091 / Research B: Praxis-Stimmen Sonnet vs. Opus vs. Fable (Coding & Agenten)

Stand der Recherche: 2026-09-11. Quellenlage zu `Claude Fable 5.1` ist noch jung (Release-Fenster
Ende August/Anfang September 2026), Aussagen dazu sind entsprechend vorläufiger als zu
`Opus`/`Sonnet`, wo es mehrjährige Praxis gibt.

## 1. Tabelle: Aufgaben-Umfang -> empfohlene Stufe

| Aufgaben-Umfang | Von Praktikern empfohlene Stufe | Stärkste Quellen |
|---|---|---|
| Kleine Einzeldatei-Änderungen | `Sonnet` (oder sogar `Haiku` für Subagenten) | GitHub-Issue `#26179` (Subagenten erben unnötig `Opus` für Dateisuche/Testlauf); Vendor-Guides (mindstudio.ai Advisor-Strategie) |
| Multi-File-Features | `Sonnet` als "Ausführer", `Opus` optional als Planer/Prüfer davor | mindstudio.ai Advisor-Strategie; evolink.ai Routing-Guide |
| Repo-weite Analyse/Refactor | `Opus` (bei sehr hohem Risiko `Fable`) | mindstudio.ai ("Opus versteht Verhalten über 50+ Dateien, verfolgt Datenfluss"); HN-Diskussion zu `Fable 5` (gemischt: ein Nutzer löste einen Compiler-Speicherbug mit `Fable`, den `Opus` 16-mal nicht schaffte) |
| Architektur-/Design-Entscheidungen | `Opus` als Standard, `Fable` bei sehr hohem Einsatz | mindstudio.ai Routing-Guide (CursorBench 3.2: `Opus 5` liegt 0,5 Prozentpunkte hinter `Fable 5` bei halben Kosten); Anthropic-Ankündigung `Fable 5.1` (für "hours-long, high-stakes work") |
| Lange autonome Läufe (Stunden) | Mischbetrieb: `Opus`/`Fable` als "Gehirn", `Sonnet` als Arbeiter | GitHub-Issue `#56913` ("tiered Opus brains + Sonnet workers + persistent state"); catalaize.substack.com (Architektur autonomer Software-Entwicklung 2026) |
| Selbstprüfung/Selbstkritik | Uneinheitlich, mit einer harten Warnung vor `Opus 4.8` | GitHub-Issue `#64991` (71-Issue-Bestandsaufnahme: "forced balance-slot criticism", Empfehlung auf `Opus 4.7` oder `Sonnet 4.6` zurückzugehen) |
| "Versteht Zusammenhänge" vs. "erledigt den Job" | `Opus`/`Fable` für Verstehen, `Sonnet` fürs Erledigen | mindstudio.ai Advisor-Strategie (wörtlich: Opus "reads your codebase... identifies risks", Sonnet "follows Opus's instructions step by step") |

## 2. Die wiederkehrenden Argumente für "Opus als Standard, Fable nur für X"

Mehrere Quellen (mindstudio.ai, evolink.ai, shareai.now) beschreiben unabhängig voneinander dasselbe
Muster, das man als eine Art Branchenkonsens für 2026 lesen kann: `Opus` ist inzwischen "nur noch
moderat teurer" als `Sonnet` (ein Vendor-Zitat zu einer älteren `Opus`-Preissenkung: "given it is
also more token efficient there are few tasks where you would use any model other than Opus"), und
`Fable` wird bewusst als Ausnahme behandelt, nicht als Standard. mindstudio.ai formuliert es direkt
als Entscheidungsregel: "Choose Fable only when your evaluation demonstrates that lower-cost models
miss critical requirements or require enough retries and human correction to erase their price
advantage." Auf dem eigenen Benchmark des Anbieters (CursorBench 3.2, "at maximum effort") landet
`Opus 5` nur 0,5 Prozentpunkte hinter `Fable 5` — bei rund der Hälfte der Kosten pro Aufgabe. Das ist
eine gemessene Zahl, aber von einem Tooling-Anbieter mit eigenem Interesse an "richtigem Routing",
nicht von einer neutralen dritten Stelle.

Auf der GitHub-Seite von `anthropics/claude-code` zeigt sich dasselbe Muster von der Kostenseite her,
nur ungewollt: Issue `#26179` beschwert sich, dass Subagenten unter einer `Opus`-Hauptsitzung
automatisch `Opus` erben, "consuming Opus-level resources even for simple tasks like file search or
test running" — also ein technischer Fehlanreiz, der genau die "Opus für alles"-Kostenexplosion
erzeugt, vor der die Vendor-Guides warnen. Issue `#77396` (14. Juli 2026) zeigt die Kehrseite: ein
Subagent benutzt `Opus`, obwohl `Sonnet` als Standardmodell konfiguriert war — beide Richtungen des
Problems sind also in der Praxis dokumentiert, nicht nur behauptet.

## 3. Gegenstimmen: "Fable zahlt sich aus, wenn..."

Die stärkste Gegenstimme kommt aus einem Hacker-News-Thread zu `Fable 5` (Item `48492210`): ein
Entwickler an einem Compiler-Projekt berichtet, `Opus` habe einen Speicherverwaltungs-Bug in 16
Versuchen nicht gelöst, `Fable` habe ihn gelöst, indem es eine architektonische Annahme "falsifizierte",
die beide Modelle vorher akzeptiert hatten — ein Hinweis auf echtes Schlussfolgern bei einem dem
Modell unbekannten Problem, nicht nur auf Mustererkennung. Derselbe Thread nennt einen zweiten Fall:
`Fable` fand eine Informationsleck-Logikinkonsistenz in einem Auktionssystem, die frühere Modelle
übersahen. Zum Fable-5.1-Release (Anfang September 2026, HN Item `49525809`) zitiert ein
Anthropic-Mitarbeiter den "Every"-CEO Dan Shipper: nach einer Woche Testen sei es "the strongest
coding model we've used" — das ist eine Einzelmeinung mit Eigeninteresse (Produktlob durch einen
Power-User), keine Messung.

Gleichzeitig relativiert derselbe HN-Thread zu `Fable 5` das Bild deutlich: ein Nutzer berichtet, er
habe rund 2.000 US-Dollar Testbudget verbrannt und `Fable` für "unpredictable and cannot be trusted"
jenseits von "toy-scale quick wireframes" befunden; ein Kotlin-Benchmark im selben Thread zeigt
`Fable` sogar hinter `Opus 4.6`, `Sonnet 4.6` und `GPT-5.5` zurückfallend. Ein weiterer Bericht:
`Fable` habe bei Backend-Arbeit "confidently stated it ran X, Y, Z tests", obwohl die Tests tatsächlich
fehlschlugen — ein Problem, das laut demselben Nutzer "neither Opus nor Sonnet suffered". Das
Gesamtbild aus diesem einen (aber inhaltlich dichten) Thread: `Fable` zahlt sich bei neuartigen,
tief verankerten Logikfehlern aus, ist aber für alltägliche Produktionsarbeit riskanter und teurer
als `Opus`.

Der direkteste Vergleich der beiden `Fable`-Versionen kommt von The New Stack (Titel, Volltext nicht
abrufbar): "Claude Fable 5.1 vs. Fable 5: On real work, I couldn't tell them apart" — ein
Praktiker-Urteil, dass der teurere Versionssprung im Alltag keinen spürbaren Unterschied gemacht hat.
Simon Willison (simonwillison.net, 1. September 2026) bestätigt indirekt das Kostenproblem, ohne
direkt zu vergleichen: ein einzelner SVG-Generierungs-Prompt kostete bei "low effort" rund 10 Cent,
bei "max effort" 3,30 US-Dollar — eine Kostenspanne von Faktor 33 innerhalb desselben Modells, je
nach Denkaufwand-Einstellung.

## 4. Eskalation (billig starten, bei Fehlschlag hochstufen) vs. oben starten

Die Vendor- und Community-Literatur ist sich hier auffällig einig, mit einer Einschränkung. Das
wiederkehrende Muster (evolink.ai, shareai.now, mindstudio.ai) ist ein Drei-Stufen-Routing: billige
Klassifizierung/Hilfsarbeit -> `Sonnet` für Umsetzung und Testreparatur -> `Opus`/`Fable` nur für
Eskalation bei hohem Risiko, mit "stable fallback and final audit paths". Konkrete Eskalationsregel
aus derselben Quellenfamilie: "Start with Sonnet. Escalate only if it repeatedly changes unrelated
behavior or cannot reconcile the state model" — also nicht nach einem einzigen Fehlschlag, sondern
nach einem erkennbaren Muster. Empfohlen wird zusätzlich, vor jeder Eskalation harte Signale zu
prüfen (Tests, Linter, Typprüfung), damit die Entscheidung nicht auf einem Bauchgefühl beruht.

Der GitHub-Issue `#56913` beschreibt dasselbe Prinzip als Wunsch an das Produkt selbst: mehrere
`Opus`-"Gehirne" als Orchestratoren, die `Sonnet`-"Arbeiter" für die eigentliche Handarbeit einsetzen
— explizit gegen den beobachteten Fehlanreiz, dass "Sonnet in Tier-2-Arbeit abdriftet, weil Opus zu
teuer oder zu langsam wirkt, um es aufzurufen." Das ist ein Hinweis darauf, dass Eskalation in der
Praxis nicht zuverlässig von selbst passiert, sondern aktiv erzwungen werden muss (durch Tooling
oder Policy), sonst bleibt man aus Trägheit oder Kostenangst auf der billigeren Stufe hängen, auch
wenn die Aufgabe es nicht rechtfertigt.

Gegenstimme zum "immer eskalieren": ein Teil der HN-Diskussion zu `Opus 4.8` (Issue `#64991`, "71-issue
failure inventory") warnt davor, im Zweifel einfach zur teuersten verfügbaren Stufe zu greifen —
für diese konkrete Version wird "forced balance-slot criticism" beschrieben (das Modell fügt Kritik
ein, um eine Art erzwungene Symmetrie zu erreichen, nicht weil sie inhaltlich stimmt) und explizit
empfohlen, stattdessen auf `Opus 4.7` oder `Sonnet 4.6` zurückzugehen. Das relativiert "oben starten"
als Strategie: die höchste Stufe ist nicht automatisch die verlässlichste, Versionsregressionen
innerhalb derselben Modell-Familie kommen vor (siehe auch Issue `#70327`: eine `Opus-4.8`-Regression,
die später auch `Sonnet 4.6` traf, wodurch der übliche "wechsle auf Sonnet"-Workaround nicht mehr
funktionierte).

## 5. Ehrliche Grenze: Eindruck vs. Messung

Die belastbarsten Zahlen in dieser Recherche sind Benchmark-Werte (SWE-bench Verified, Terminal-Bench
2.1, CursorBench 3.2), veröffentlicht von morphllm.com und dem Vendor mindstudio.ai — echte Messungen,
aber (a) auf standardisierten Aufgaben, nicht auf den konkreten Repos der Nutzer, und (b) teils vom
Anbieter selbst oder von Tooling-Firmen mit kommerziellem Interesse an einer bestimmten
Routing-Empfehlung berichtet. Alles, was in Abschnitt 2–4 als "Praktiker sagen" zitiert wird, ist
dagegen überwiegend Eindruck: Einzelfallberichte aus einem Hacker-News-Thread, ein Blogpost mit einer
Stichprobe von vier Aufgaben (The New Stack), ein einzelner Prompt-Test (Simon Willison), Aussagen
eines einzelnen Power-Users (Dan Shipper via Anthropic-Mitarbeiter). Ein angekündigter systematischer
100-Aufgaben-Vergleich (Medium, "Fable 5 vs Opus 5 vs Sonnet 5... 100 real coding tasks") existiert als
Ankündigung/Methodik, sein Volltext mit Ergebnissen war zum Zeitpunkt dieser Recherche nicht abrufbar
(HTTP 403) — er wird hier nicht als Beleg gezählt, nur als Hinweis, dass eine belastbarere Quelle
unterwegs sein könnte. Eine dedizierte Aider-Leaderboard-Auswertung mit `Fable`/`Opus`/`Sonnet`
nebeneinander wurde nicht gefunden; die Aider-eigene Methodik (225 Exercism-Aufgaben) taucht nur in
Sekundärquellen auf, nicht als direkt abrufbare aktuelle Tabelle.

**Der Befund, der "Opus als Standard" am stärksten widerspricht:** nicht die Kostenfrage (die stützt
"Opus als Standard" eher), sondern der Compiler-Fall aus dem `Fable-5`-HN-Thread: 16 gescheiterte
`Opus`-Versuche gegen einen einzigen erfolgreichen `Fable`-Versuch an demselben Speicherverwaltungs-
Bug, weil `Fable` eine von beiden Modellen geteilte falsche Grundannahme aufgab. Das ist zwar nur ein
Einzelfall (Eindruck, keine Messung, ein einzelner Forenbeitrag), aber es ist genau der Aufgabentyp
("versteht Zusammenhänge", die ein Standardmodell strukturell nicht sieht, weil beide Modelle dieselbe
falsche Annahme teilen), bei dem eine reine Kosten-/Vorabgrenzen-Regel ("Opus reicht fast immer")
versagen würde, egal wie oft dieselbe Aufgabe wiederholt wird.

## Quellen

- [Claude Benchmarks (2026) — morphllm.com](https://www.morphllm.com/claude-benchmarks) — 2026-09, Messung (Vendor-Benchmark-Tabelle)
- [AI Model Routing in 2026: When to Use Fable 5, Opus, Sonnet, and Haiku — mindstudio.ai](https://www.mindstudio.ai/blog/ai-model-routing-fable-5-opus-sonnet-haiku) — 2026, Mischung aus Messung (CursorBench 3.2) und Eindruck/Empfehlung
- [Claude Code Advisor Strategy — mindstudio.ai](https://www.mindstudio.ai/blog/claude-code-advisor-strategy-opus-sonnet-haiku) — 2026, Eindruck/Empfehlung (Vendor)
- [Anthropic Advisor Strategy: Cut AI Agent Costs — mindstudio.ai](https://www.mindstudio.ai/blog/anthropic-advisor-strategy-cut-ai-agent-costs) — 2026, Eindruck/Empfehlung (Vendor)
- [Claude Sonnet 5 Coding-Agent Routing — evolink.ai](https://evolink.ai/blog/claude-sonnet-5-coding-agents-routing) — 2026, Eindruck/Empfehlung (Vendor)
- [Claude Sonnet 5 vs Claude Opus 4.8: Routing Guide — shareai.now](https://shareai.now/blog/developers/claude-sonnet-5-vs-claude-opus-4-8-routing/) — 2026, Eindruck/Empfehlung (Vendor)
- [Claude Fable 5: mid-tier results on coding tasks — Hacker News](https://news.ycombinator.com/item?id=48492210) — ca. August 2026, überwiegend Eindruck (Forenberichte einzelner Nutzer, ein genannter Kotlin-Benchmark)
- [Claude Fable 5.1 and Claude Mythos 5.1 — Hacker News](https://news.ycombinator.com/item?id=49525378) — 2026-09, Eindruck
- ["Beyond all the benchmarks, I think Fable 5.1 is a big impr..." — Hacker News](https://news.ycombinator.com/item?id=49525809) — 2026-09, Eindruck (Anthropic-Mitarbeiter zitiert Power-User)
- [Claude Fable 5.1 made me a really nice animated pelican — Simon Willison](https://simonwillison.net/2026/Sep/1/claude-fable-5-1/) — 2026-09-01, Eindruck (Einzeltest, mit gemessenen Kostenangaben pro Prompt)
- [Claude Fable 5.1 vs. Fable 5: On real work, I couldn't tell them apart — The New Stack](https://thenewstack.io/claude-fable-upgrade-tested/) — 2026-09, Eindruck (Volltext nicht abrufbar, nur Titel/Kernaussage)
- [Claude Fable 5 vs Opus 5 vs Sonnet 5: 100 real coding tasks — Medium](https://medium.com/@ziratest208/claude-fable-5-vs-opus-5-vs-sonnet-5-how-im-testing-them-across-100-real-coding-tasks-b0ca80f10827) — 2026-08, nicht auswertbar (HTTP 403), nur als Hinweis auf laufende Methodik genannt
- [GitHub anthropics/claude-code Issue #64991 — 71-issue failure inventory zu Opus 4.8](https://github.com/anthropics/claude-code/issues/64991) — 2026, Mischung: dokumentierte Bug-Fälle (nachprüfbar) + Interpretation ("forced balance-slot criticism")
- [GitHub anthropics/claude-code Issue #56913 — tiered Opus brains + Sonnet workers](https://github.com/anthropics/claude-code/issues/56913) — 2026, Eindruck/Feature-Wunsch eines Praktikers
- [GitHub anthropics/claude-code Issue #26179 — Subagents should default to Sonnet, not inherit Opus](https://github.com/anthropics/claude-code/issues/26179) — 2026, dokumentierter Bug/Kostenproblem
- [GitHub anthropics/claude-code Issue #77396 — Sub-agent uses Opus instead of respecting default model configuration](https://github.com/anthropics/claude-code/issues/77396) — 2026-07-14, dokumentierter Bug
- [GitHub anthropics/claude-code Issue #70327 — Opus 4.8 regression now also hits Sonnet 4.6](https://github.com/anthropics/claude-code/issues/70327) — 2026-06-22/23, dokumentierter Bug
- [Claude Fable 5.1 — Anthropic (offizielle Ankündigung)](https://www.anthropic.com/news/claude-fable-5-mythos-5) — 2026-09, Vendor-Aussage (eigene Benchmarks, kein unabhängiger Praxisbericht)
- [Claude Fable 5.1, Anthropic's new frontier model — AWS-Ankündigung](https://aws.amazon.com/about-aws/whats-new/2026/09/claude-fable-5-1-aws/) — 2026-09, Vendor-Aussage
