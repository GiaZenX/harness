# FR-0091 / Research C: Sonnet vs Opus vs Fable (5.1) — veröffentlichte Benchmarks und Kosten pro Aufgabe

Stand der Recherche: 2026-09-11, per WebSearch. Read-only, keine Codeänderung.

**Vorab-Warnung, weil sie den ganzen Rest einfärbt:** Die Sekundärquellen (SEO-Blogs wie
morphllm.com, benchlm.ai, codingfleet.com) widersprechen sich **direkt** darüber, welches Modell
auf SWE-bench Verified vorne liegt — eine Quelle nennt Opus 5 mit 96,0 %, eine andere Fable 5 mit
95,0 %, eine dritte reiht Mythos 5 dazwischen ein. Das ist kein Rundungsfehler, sondern zeigt: bei
diesen Drittanbieter-Zusammenfassungen ist unklar, welche Scaffold-Version, welcher Stichtag und
welche Anthropic-eigene vs. nachgemessene Zahl jeweils gemeint ist. Wo möglich, unten die
Primärquelle (Anthropic-Ankündigung, Artificial Analysis, offizielles Leaderboard) markiert;
Blog-Zusammenfassungen sind explizit als solche benannt.

## 1) Benchmark-Tabelle: Sonnet / Opus / Fable

| Benchmark (Version) | Sonnet 5 | Opus 5 | Fable 5 | Fable 5.1 | Datum / Quelle |
|---|---|---|---|---|---|
| SWE-bench Verified | 85,2 % | 96,0 % (Anthropic-Launchzahl, umstritten) | 95,0 % | kein Headline-Wert veröffentlicht | Sep 2026, morphllm.com / llm-stats.com — **Widerspruch zwischen Quellen, siehe oben** |
| SWE-bench Pro | 63,2 % | — | 80,0 % | 81,2 % (#1) | Sep 2026, morphllm.com "SWE-bench Pro Leaderboard", codingfleet.com |
| Terminal-Bench 2.1 | 85,2 % | 89,1 % | — | 91,4 % (Adaptive Reasoning, Max Effort); 85,02 % in anderer Quelle als #2 | Sep 2026, Artificial Analysis / vals.ai / benchlm.ai — auch hier zwei verschiedene Fable-5.1-Werte |
| Terminal-Bench 2.0 | 80,4 % (#11) | 74,6 % (Opus 4.8, #16) | 84,3 % (#5) | — | 10.09.2026, codingfleet.com |
| Terminal-Bench 4.0 (neue Skala, NICHT vergleichbar mit 2.x) | — | 51,8 % ± 3,4 | 44,5 % | 57,9 % ± 3,8 (#1) | 01.–02.09.2026 |
| LiveBench (Gesamt) | 76,0 % | 80,1 % | 83,0 % | 83,4 % | Sep 2026, benchlm.ai |
| LiveCodeBench | — | — | — | 90,52 % (#1) | Sep 2026 |
| Artificial-Analysis Intelligence Index | (niedriger als Opus/Fable, kein Einzelwert gefunden) | 61 (max) | 60–62 (max, je nach Quelle) | 66 | Artificial Analysis, Sep 2026 |
| Terminal-Bench-Science (agentische Wissenschaft) | — | — | 24,7 % | 52,6 % (mehr als verdoppelt) | Anthropic-eigene Ankündigung, 01.09.2026 |
| AutomationBench (Büroautomation) | — | — | 17,1 % | 31,4 % | Anthropic-eigene Ankündigung, 01.09.2026 |
| Aider-Polyglot | Claude nicht führend; GPT-5 führt mit 0,880 | — | — | — | Sep 2026, llm-stats.com |

**Deltas, die halbwegs sauber belegt sind:** Fable 5.1 vs. Fable 5 verdoppelt sich fast bis
mehr als doppelt auf den agentischen/langlaufenden Benchmarks (Terminal-Bench-Science: 24,7→52,6,
AutomationBench: 17,1→31,4) — das ist die direkte Anthropic-Ankündigung und die am besten
belegte Zahl in dieser Recherche. Auf den gesättigten Standard-Benchmarks (SWE-bench Verified,
LiveBench) liegen Sonnet 5, Opus 5, Fable 5 und Fable 5.1 dagegen alle innerhalb von grob 10–15
Prozentpunkten beieinander, und mehrere Quellen bemerken ausdrücklich, dass SWE-bench Verified
für Spitzenmodelle inzwischen als gesättigt gilt (Cluster innerhalb von 1 Punkt laut einer
Quelle) — OpenAI hat im Februar 2026 laut Suchergebnis sogar aufgehört, Verified-Werte zu
berichten, weil sie die Aussagekraft anzweifeln.

## 2) Preis pro Stufe und Kosten pro gelöster Aufgabe

Preise (API, Input/Output pro Million Tokens, Stand September 2026):

- Haiku 4.5: 1 $ / 5 $
- Sonnet 5: 2 $ / 10 $
- Opus 5: 5 $ / 25 $
- Fable 5 / Fable 5.1: 10 $ / 50 $ (Fable 5.1 senkt nur den Cache-Lesepreis um 75 % auf 0,25 $/M)

Also: Fable kostet etwa das 5-Fache von Sonnet und das 2-Fache von Opus pro Token — bei einem
Score-Vorsprung, der auf den gesättigten Benchmarks oft nur einstellig in Prozentpunkten ausfällt.

**Kosten pro gelöster Aufgabe (dort, wo eine Quelle die Rechnung explizit vorführt):**

- Artificial-Analysis-Intelligence-Index, pro Aufgabe: Opus 4.8 (max) 1,80 $; Sonnet 5 (max)
  1,53 $ (Einführungspreis, ausgelaufen 31.08.2026) bzw. 2,29 $ zum Normalpreis; Opus 5 (max)
  2,03 $; Fable 5 (mit Fallback) 2,75 $. Rechnung dahinter: Kosten pro Lauf über alle
  Index-Aufgaben geteilt durch die Anzahl gelöster Aufgaben — Artificial Analysis nennt für den
  kompletten Fable-5-Lauf sogar eine Gesamtsumme von ca. 6.200 $, "das teuerste je von ihnen
  benchmarkte Modell".
- SWE-bench-Pro3-Teilmenge (laut morphllm.com, eine sekundäre Zusammenstellung, nicht Anthropic
  selbst): Fable 5.1 bei niedrigem Effort löst 88,6 % für 0,54 $ pro gelöster Aufgabe; Sonnet 5
  im Standard-Effort löst 77,4 % für 0,84 $; Opus 5 bei niedrigem Effort löst 84,0 % für 0,25 $.
  Rechenweg (so wie die Quelle ihn beschreibt): Gesamtkosten des Laufs über alle Aufgaben,
  geteilt durch Anzahl gelöster (nicht aller gestellten) Aufgaben — das erklärt, warum ein
  höherer Score UND ein niedrigerer Preis pro gelöster Aufgabe gleichzeitig auftreten können
  (Opus 5 hier günstiger UND schwächer als Fable 5.1, aber die Kosten-pro-Erfolg-Rechnung
  bevorzugt trotzdem Opus, weil der Nenner — gelöste Aufgaben — bei niedrigem Effort relativ zur
  Tokenmenge stark steigt).

  **Einordnung:** Diese Zahl ist eine Rechnung DRITTER (morphllm.com), nicht von Anthropic
  selbst veröffentlicht, und die genaue Scaffold/Sample-Größe ist aus der Suche nicht
  nachvollziehbar. Als Anhaltspunkt für die Größenordnung brauchbar, nicht als belastbarer
  Einzelwert.

- **Allgemeines Muster über beide Rechnungen:** Ein niedrigerer Preis pro Token macht ein Modell
  nicht automatisch billiger pro gelöster Aufgabe — Sonnet 5 ist pro Token am günstigsten, landet
  aber bei den Kosten pro gelöster Aufgabe teils HINTER Opus 5, weil es mehr Tokens/Versuche
  braucht, um denselben Anteil an Aufgaben zu lösen.

## 3) Effort/Denkbudget: Score gegen Tokens

- Allgemeine Kurvenform, die mehrere Quellen unabhängig beschreiben: steiler Anstieg von
  niedrigem zu mittlerem Effort, dann starkes Abflachen von mittel zu hoch — die klassische
  Sättigungskurve.
- Konkreter Datenpunkt (FrontierCode-Benchmark, laut sitepoint.com-Zusammenfassung, nicht
  Anthropic-Primärquelle): Opus 5 erreicht seinen Spitzenwert (53,4 % auf dem Hauptdatensatz) bei
  MITTLEREM Effort; hoher Effort verbessert nichts mehr oder verschlechtert sich sogar leicht
  gegenüber mittel.
- Ein weiterer Datenpunkt (ältere Generation, Claude 4 Sonnet, Code-Aufgaben): abnehmender
  Grenznutzen ab ca. 16.000 Denk-Tokens.
- Allgemeine LLM-Forschung (nicht Claude-spezifisch, aus einem arXiv-Preprint
  "When More Thinking Hurts", 2604.10739): jenseits von ca. 12.000 Tokens kann der Grenznutzen
  sogar NEGATIV werden — mehr Nachdenken macht die Antwort im Schnitt schlechter, nicht nur
  teurer, vermutlich durch Abschweifen/Overthinking.
- Für die konkrete Preis/Score-Kurve von Fable 5.1 selbst (die für dieses Repo am relevantesten
  wäre) hat die Suche keinen eigenen veröffentlichten Kurvenverlauf ergeben — nur die
  Aufgaben-Kosten-Paare aus Abschnitt 2 bei je EINER Effort-Stufe, keine durchgehende Kurve über
  mehrere Stufen mit Fable als Modell.

## 4) Was diese Benchmarks NICHT messen

Klar gesagt, weil es sonst untergeht:

- **Architektur-Urteilsvermögen.** SWE-bench & Co. bewerten, ob ein vorgegebener, meist gut
  umrissener Patch einen bekannten Test grün macht. Ob ein Modell eine tragfähige
  Systemgrenze zieht, einen Gate-Mechanismus richtig entwirft oder eine Abkürzung erkennt, die
  sich später rächt, wird nirgends gemessen — das sind genau die Entscheidungen, die dieses
  Repos "Umsetzer"/"Prüfer"-Trennung und die DEC-Items abbilden sollen.
- **Selbstprüfung ohne externen Testoracle.** Die Benchmarks laufen fast alle gegen einen fest
  hinterlegten Test/Reward. Die Fähigkeit, die EIGENE Behauptung zu misstrauen und sie gegen den
  laufenden Code zu messen (die Rolle des Prüfers hier), taucht in keinem der gefundenen
  Benchmarks als eigene Metrik auf.
- **Mehrtägige Autonomie.** Terminal-Bench/AutomationBench laufen über Minuten bis wenige
  Stunden ("multi-hour jobs" laut Anthropic-Ankündigung), nicht über Tage mit Unterbrechungen,
  Kontextverlust zwischen Sitzungen und wechselnden menschlichen Vorgaben — genau das Muster
  dieses Projekts über Generationen/Runden hinweg.
- **Deutsche Prosa / Kommunikation mit einem technisch fernen Menschen.** Alle gefundenen
  Benchmarks sind Englisch und codezentriert; keiner bewertet, ob ein Modell einem Laien in
  einfacher Sprache erklären kann, was passiert ist (die Berichtsregel dieses Repos).
- **Echte Multi-File-Kohärenz über eine Million Tokens.** Die Suche fand einen expliziten
  Warnhinweis: Marketing-Zahlen zu 1M-Kontextfenstern verstecken einen Rückgang der
  Retrieval-Genauigkeit von 30–60 Punkten zwischen 200K und 1M bei praktisch jedem
  Spitzenmodell außer einem Konkurrenzmodell. Needle-in-a-Haystack testet das Auffinden EINER
  eingebetteten Tatsache, nicht das Schlussfolgern über verteilte Information — ein Beispielwert
  (ältere Opus-Generation, MRCR-v2-Achternadel-Test bei 1M Tokens): 76 % Trefferquote, während
  eine ältere Sonnet-Generation im selben Test nur 18,5 % erreichte. Für praktische
  Mehrdatei-Arbeitslasten liegt der effektiv nutzbare Kontext laut einer Quelle eher im
  Bereich 200–400K, nicht bei der beworbenen Obergrenze.

## 5) Fazit in einem Absatz

Die Zahlen rechtfertigen die Top-Stufe (Fable 5.1) am ehesten für lange, werkzeugnutzende,
agentische Aufgaben, bei denen der Abstand zu Opus/Sonnet groß und real ist — Anthropics eigene
Zahlen zeigen dort eine Verdopplung (Terminal-Bench-Science, AutomationBench) statt der paar
Prozentpunkte, die auf den gesättigten Standard-Coding-Benchmarks (SWE-bench Verified, LiveBench)
zwischen den Stufen liegen; für kurze, gut umrissene Patch-Aufgaben mit klarem Test ist der
Kosten-pro-gelöster-Aufgabe-Vorteil dagegen keineswegs eindeutig zugunsten der teuersten Stufe —
in mindestens einer Rechnung schneidet Opus 5 bei niedrigem Effort pro gelöster Aufgabe günstiger
ab als sowohl Sonnet 5 im Standardmodus als auch (in absoluten Kosten) Fable 5.1. Für die Fragen,
die in diesem Repo tatsächlich den Unterschied machen — Architekturentscheidung, Selbstprüfung
ohne vorgegebenen Test, mehrtägige Kontinuität über Sitzungen, verständliche deutsche
Kommunikation — liefert KEINER der gefundenen Benchmarks eine direkte Messung; die Wahl der Stufe
für solche Aufgaben ist damit aus diesen Zahlen allein nicht ableitbar und bliebe eine
Ermessensentscheidung, keine benchmarkgestützte.

## Quellen

- https://www.anthropic.com/claude-fable-and-mythos-5-1 (Anthropic-Primärquelle, 01.09.2026)
- https://www.morphllm.com/claude-benchmarks
- https://www.datacamp.com/blog/claude-fable-5-1
- https://www.vellum.ai/blog/claude-fable-5-and-mythos-5-benchmarks-explained
- https://computingforgeeks.com/claude-fable-5-1-released-features-benchmarks/
- https://www.cloudzero.com/blog/claude-pricing/
- https://www.finout.io/blog/anthropic-api-pricing
- https://platform.claude.com/docs/en/about-claude/pricing
- https://benchlm.ai/anthropic/api-pricing
- https://www.aipricing.guru/anthropic-pricing/
- https://www.morphllm.com/swe-bench-pro
- https://llm-stats.com/benchmarks/swe-bench-verified
- https://benchlm.ai/benchmarks/swe-bench-verified
- https://localaimaster.com/models/swe-bench-explained-ai-benchmarks
- https://www.morphllm.com/ai-coding-costs
- https://www.morphllm.com/best-ai-model-for-coding
- https://www.doit.com/research/economics-of-claude-openai-and-grok
- https://www.marktechpost.com/2026/07/13/anthropic-claude-sonnet-5-vs-sonnet-4-6-vs-opus-4-8-agentic-coding-benchmarks-api-pricing-and-cost-performance-tradeoffs-compared/
- https://pricepertoken.com/leaderboards/benchmark/terminalbench
- https://artificialanalysis.ai/evaluations/terminalbench-v2-1
- https://benchlm.ai/benchmarks/terminal-bench-2
- https://www.vals.ai/benchmarks/terminal-bench-2-1
- https://codingfleet.com/blog/terminal-bench-leaderboard-2026/
- https://pre.dev/benchmark
- https://artificialanalysis.ai/models/claude-fable-5
- https://x.com/ArtificialAnlys/status/2067384319942029379
- https://artificialanalysis.ai/articles/opus-5
- https://artificialanalysis.ai/providers/anthropic
- https://llm-stats.com/benchmarks/aider-polyglot
- https://codingfleet.com/blog/swe-bench-pro-leaderboard-2026/
- https://www.mindstudio.ai/blog/claude-effort-levels-better-results-without-overspending
- https://www.sitepoint.com/claude-opus-5-medium-effort-frontiercode-benchmark/
- https://platform.claude.com/docs/en/build-with-claude/extended-thinking
- https://arxiv.org/pdf/2604.10739 (When More Thinking Hurts: Overthinking in LLM Test-Time Compute Scaling)
- https://www.morphllm.com/claude-context-window
- https://www.digitalapplied.com/blog/long-context-retrieval-needle-in-haystack-2026
- https://www.vals.ai/models/anthropic_claude-fable-5-1
