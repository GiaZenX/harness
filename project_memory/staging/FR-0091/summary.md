# FR-0091 — Welches Modell für welchen Umfang: Synthese des Leads (2026-09-11)

Grundlage: `research-A-anthropic.md` (8 offizielle Quellen), `research-B-practice.md` (19 Quellen, meist
Eindrücke), `research-C-benchmarks.md` (37 Quellen, widersprüchliche Sekundärzahlen ausdrücklich markiert).
Geprüft gegen DEC-0095 (Bauer/Orchestrator Opus, Fable nur Architektur-Schritt + Eskalationsziel) und DEC-0096
(erst Aufwand, dann Sprosse; Fable beim dritten Fehlschlag).

## 1. Was die drei Berichte übereinstimmend sagen

| Befund | Quelle | Trifft unsere Regel |
|---|---|---|
| **Opus ist der Standard, Fable die begründete Ausnahme.** Anthropic wörtlich: „if your evals or internal testing show Opus struggling on some tasks, then Fable is the answer" / „If Opus already clears the quality bar, then its speed and price profile may make it the better choice." Praktiker-Konsens: „Choose Fable only when your evaluation demonstrates that lower-cost models miss critical requirements or require enough retries … to erase their price advantage." | A §1, B §2 | **DEC-0095 (1) bestätigt** |
| **Zwei getrennte Eskalationssignale.** Anthropic: **Modell** wechseln, wenn Claude „confidently wrong no matter how much context you give it" ist (subtle bugs, unfamiliar domains, **architecture decisions**); **Aufwand** erhöhen, wenn das Scheitern an Sorgfalt lag („skipped a file, not running the tests, bailing on a refactor partway through"). | A §3 | **DEC-0096 bestätigt** — und präzisiert: die Befundklasse der Prüfrunde entscheidet, welche Achse zuerst (siehe §3) |
| **Eskalation nach Muster, nicht nach einem Fehlschlag.** „Start with Sonnet. Escalate only if it repeatedly changes unrelated behavior or cannot reconcile the state model"; vorher harte Signale (Tests, Linter) prüfen. | B §4 | DEC-0096 (1) bestätigt (FAIL 1 Aufwand, FAIL 2 Neuschnitt, FAIL 3 Sprosse) |
| **Eskalation passiert nicht von selbst** — aus Trägheit oder Kostenangst bleibt man unten hängen; sie muss durch Tooling/Policy erzwungen werden. | B §4 (Issue #56913) | Genau DEC-0092 (Struktur-Gate + Fakten-Checkpoint) und die Leiter-Regel 2 als Mechanik |
| **Sonnet für mechanische, präzise beschreibbare Änderungen** und „high-volume sub-agents"; für mehrdeutige, mehrstufige Arbeit größere Modelle, weil kleinere „grind toward the limit of their ability, burning iterations". | A §1/§3 | DEC-0088 (2) / DEC-0091 (1) bestätigt (Sonnet = mechanische Scheibe mit vollständiger Spezifikation) |
| **Fable's Vorsprung ist real, aber schmal auf Standard-Coding** (gesättigte Benchmarks: alle Stufen innerhalb ~10–15 Punkte; CursorBench: Opus 5 0,5 Punkte hinter Fable 5 bei halben Kosten) **und breit auf langen agentischen Aufgaben** (Fable 5.1 verdoppelt Fable 5 auf Terminal-Bench-Science / AutomationBench — Anthropics eigene Zahl). | C §1, B §2 | Stützt „Fable für den Architektur-Schritt eines großen Ziels" (Urteil über viele Dateien, lange Horizonte), nicht für den Bau |
| **Kosten je gelöster Aufgabe:** Sonnet ist pro Token am billigsten, aber pro gelöster Aufgabe teils hinter Opus (mehr Versuche); Opus bei niedrigem Aufwand in einer Rechnung am günstigsten pro Erfolg. | C §2 | Stützt Opus als Standard; warnt vor „Sonnet, weil billig" |
| **Mehr Denken hilft nur bis zu einem Punkt** — Sättigung von mittel zu hoch, jenseits ~12 k Denk-Tokens im Schnitt sogar schlechter (arXiv 2604.10739); Opus 5 auf FrontierCode bei **mittlerem** Aufwand am besten. | C §3 | `high` als Standard (DEC-0077) bleibt richtig; `xhigh` nur als Fehlschlag-1-Schritt (DEC-0096) oder benannter Schritt, nie Dauerbetrieb |
| **Fable behauptet auch mal Falsches** („confidently stated it ran X, Y, Z tests" — Tests schlugen fehl; „neither Opus nor Sonnet suffered"). | B §3 | **Der unabhängige Prüfer bleibt** (DEC-0087 (3)) — gerade bei der Top-Stufe |
| **Die Benchmarks messen nicht, was hier zählt:** Architektur-Urteil, Selbstprüfung ohne Test-Orakel, mehrtägige Kontinuität, deutsche Prosa. | C §4 | Die Stufenwahl für diese Klassen bleibt Ermessen + eigene (g)-Zahlen; deshalb `report.lease_distribution` (Runden bis bestanden je Sprosse) |

## 2. Was dem Gefühl des Nutzers widerspricht — oder es einschränkt

- **„Fable versteht Zusammenhänge besser"** hat genau **einen** starken Beleg (der Compiler-Fall: 16 Opus-Fehlversuche, ein Fable-Erfolg, weil Fable eine von beiden geteilte falsche Grundannahme aufgab) — ein Einzelfall, aber exakt die Klasse „confidently wrong mit vollem Kontext", für die Anthropic den **Modellwechsel** nennt. Die Regel „Fable beim dritten Fehlschlag" fängt das; der Neuschnitt beim zweiten darf es früher fangen (siehe §3).
- **„Fable ist autonomer und prüft sich selbst"** — Anthropic sagt das so („verify their work more often than smaller models"), die Praxis widerspricht in Einzelfällen (falsche Testbehauptungen, „unpredictable" jenseits kleiner Aufgaben, 2 000 $ verbrannt). Beides zusammen: Fable ohne Prüfer ist kein Sparmodell.
- **„Sonnet nur für ganz kleine Sachen"** — bestätigt von Anthropic (mechanisch, präzise beschreibbar) **und** von der Kostenrechnung (pro gelöster Aufgabe nicht billiger, sobald Iterationen nötig werden).

## 3. Entscheidungsregel — was sich ändert, was nicht

**Keine Regeländerung nötig.** DEC-0095 und DEC-0096 sind durch A, B und C gedeckt. Zwei Präzisierungen, die in
die Texte gehören (Träger: der Auftrag, der die Checkpoint-Frage und die Leiter-Absätze das nächste Mal anfasst;
heute TSK-0136 nur, soweit sein Auftrag es schon trägt):

1. **Die Checkpoint-Frage nennt Anthropics zwei Signale** statt nur „nötig/ausreichend": *War der letzte Fehlschlag
   Sorgfalt (Datei übersprungen, Tests nicht gefahren, Refactor abgebrochen) → Aufwand. War er „sicher falsch mit
   vollem Kontext" (falsche Grundannahme, unbekannte Domäne, Architekturfrage) → Sprosse.* Das ist DEC-0096 (1) in
   der Sprache, die der PM beim Neuschnitt (FAIL 2) braucht — und die Erlaubnis, dort per Auftrags-Bitte
   (DEC-0091) direkt auf Fable zu gehen, wenn die Befundklasse „Produktfehler / falsche Annahme" ist, statt den
   dritten Fehlschlag abzuwarten.
2. **Sonnet-Scheiben tragen einen Test als Abnahme, nie eine Beschreibung** — Anthropics „if you could describe
   the diff in one sentence" als Schwelle: Was sich in einem Satz beschreiben lässt, ist eine Sonnet-Scheibe; was
   nicht, ist Opus.

**Was nur wir selbst messen können:** ob Opus als Bauer die Prüfrunde am Ziel seltener oder öfter besteht als
Fable — `report.lease_distribution` („runs to done je Sprosse") über die nächsten Ziele, und das FR-0089-
Experiment mit dem Urteil des Nutzers.

## 4. Kosten dieser Recherche

Drei Sonnet-Agenten, ~88 k / ~99 k / ~162 k Tokens, 2–5 Minuten je Bericht — der günstigste Posten des Tages.
