# FR-0098 — Welche Auftrags-Eigenschaften entscheiden die KLASSE (Modell), welche den EFFORT? Recherche 2026-09-28

Read-only-Recherche, Webseiten am **2026-09-28** gelesen. **[belegt]** = steht so in der Quelle; **[Meinung]**
= Ableitung. Stärke: **A** = Hersteller + unabhängige Messung; **B** = eine Quelle; **C** = Ableitung.
Grundlage **DEC-0129**: Klasse = nur das Modell (Milli < Kilo = Haiku < Mega = Sonnet < Giga = Opus < Tera =
Fable < Peta), Effort eigene Achse (DEC-0127, FR-0097 — hier nur abgegrenzt).

## 0. Kurzantwort

1. **Die Trennung hat eine Herstellerregel**: „did it not _try_ hard enough, or did it not _know_ enough?" →
   Effort bzw. Modell (Claude-Code-Blog 2026-07-07). **Klasse = nötiges Wissen/Urteil; Effort = nötige Gründlichkeit.**
2. **Klassenmerkmale**: fremde Domäne/Sprachsemantik, Umfang über mehrere Dateien/Module, stundenlange Ketten,
   Ergebnis vorher prüfbar. **Effortmerkmale**: Randfälle, Planung, Prüfung, Laufzeit. Mehrdeutigkeit: weder — Rückfrage.
3. **Lead-Fragen unter DEC-0129**: F1 („steuert andere Aufträge") ist jetzt eine **Effort**-Frage; F2
   („durchgefallen → Klasse hoch") widerspricht DEC-0096/DEC-0127 (6); F3 („Test entscheidet") ist die
   **Mega**-Frage, braucht zählbare Grenzen; F4 („sonst") → **Giga**. Es fehlen ein **Boden** für
   Schutzflächen und die **Kilo**-Frage.
4. **Aus dem Auftragstext ist die Klasse nur schwach vorhersagbar** (AUC 0,60) → nur messbare Item-Felder
   abfragen, Eskalation nach der Prüfung bleibt zweiter Riegel.
5. **OpenAI ehrlich eingestuft**: Luna = Kilo (Grenzfall, messen), Sol = Mega, Astra = Tera. **Giga ist bei
   OpenAI leer** — der Standard-Bauer hat dort kein Modell; Nutzerentscheidung nötig (§4.3).

## 1. Wie andere nach Aufgabe routen

### 1.1 Hersteller

- **Anthropic „Choosing the right model"** (https://platform.claude.com/docs/en/about-claude/models/choosing-a-model)
  [belegt]: „Most workloads start with Claude Opus 5.5." Fable 5.1 für „Agent sessions that run for hours";
  Opus 5.5 für „large-scale refactoring, complex systems engineering"; Sonnet 5.5 „everyday coding"; Haiku
  „sub-agent tasks". Fable erst, „If your evals at `xhigh` or `max` effort still fall short"; „Tuning effort
  is often a better lever than switching models."
- **Claude-Code-Blog, L. Hallie, 2026-07-07** (https://claude.com/blog/claude-model-and-effort-level-in-claude-code)
  [belegt]: größeres Modell bei „genuinely hard" (subtile Bugs, fremde Domäne, Architektur), „ambiguity",
  „long, multi-step", oder wenn das kleinere „confidently wrong no matter how much context you give it" ist;
  kleineres bei „edits you can describe precisely or mechanical changes". **Effort** hoch, wenn Claude
  „got it wrong by skipping a file, not running the tests, or bailing on a refactor partway through".
- **Claude Code model-config** (https://code.claude.com/docs/en/model-config) [belegt]: Fable für „hardest and
  longest-running tasks"; „root-cause investigations, outage debugging, and architecture decisions".
- **Anthropic „Optimizing for cost and intelligence"** (https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence)
  [belegt]: Fable-Berater über Opus 5.5: +1,7 Punkte bei ~2,1× Kosten („edge of run-to-run noise").
- **OpenAI Codex** (https://learn.chatgpt.com/docs/models) [belegt]: **Luna** „when you know what a good result
  looks like, such as extraction, classification, transformation, and structured summaries"; **Sol**
  „ambiguous, difficult, or high-value tasks"; **Astra** „sustained reasoning and judgment". API-Leitfaden
  (https://developers.openai.com/api/docs/guides/latest-model): beim Wechsel „compare results on representative tasks".
- **OpenAI Agents-Leitfaden** (https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/,
  Suchauszug) [belegt]: Risiko nach „read-only vs. write access, reversibility" → Menschen einbeziehen.

### 1.2 Werkzeuge

| Werkzeug | Datum | Merkmale | Wie entschieden | Quelle |
|---|---|---|---|---|
| Cursor Router | 2026-08-06 | Domäne (backend, DB-Schema, frontend), Aufgabe (Bugfix, Befehle, Tests), Modifikatoren („bounded edits", „visual-heavy changes"), letzte Werkzeugaufrufe | gelernt aus Live-Verkehr; Erfolg = „Moving on to the next task", Misserfolg = „correcting the agent" | https://cursor.com/blog/how-cursor-router-works |
| GitHub Copilot Auto | 2026-07-01 | „reasoning, code generation complexity, bug diagnosis difficulty, and tool orchestration needs" + Verfügbarkeit | pro Anfrage; Stufen Efficiency/Balance/Intelligence | https://github.blog/changelog/2026-07-01-copilot-cli-auto-model-selection-routes-based-on-task/ |
| Cline | laufend | **Phase**: Plan (Architektur, unklare Ursache, mehrere Dateien) vs. Act (vereinbarter Plan, Routine) | Nutzer wählt je Phase ein Modell | https://docs.cline.bot/core-workflows/plan-and-act |
| Aider | 2024-09-26 | Rolle: Architekt denkt, Editor setzt um | fest je Rolle; Paar schlug Einzelmodell | https://aider.chat/2024/09/26/architect.html |
| Claude Code | 2026-09 | `opusplan` (Opus planen, Sonnet ausführen); `model:` je Subagent; „Control costs by routing tasks to faster, cheaper models like Haiku" | fest je Rolle/Phase | https://code.claude.com/docs/en/sub-agents |

### 1.3 Forschung (RouteLLM, arXiv 2406.18665, 2024, ist Einzelanfragen-Routing und nur Hintergrund)

- **Triage** (Madeyski, arXiv 2604.07494, 2026-04-08) [belegt]: Stufen „light, standard, heavy — mirroring,
  e.g., Haiku, Sonnet, Opus"; Signal = **Codegesundheit**; „medium LLMs benefit from clean code while frontier
  models do not"; lohnt nur, wenn die Bestehensquote der leichten Stufe das Kostenverhältnis übersteigt.
- **Applied Compute** (Becker/Garg, 2026-06-04, https://www.appliedcompute.com/research/training-an-agentic-router)
  [belegt]: bester Einzelwert 0,834, Orakel 0,890. Stärker nötig bei **Sprachsemantik** („dunder methods, MRO,
  metaclasses") und „Cross-file API inconsistencies … when symbol appears in multiple files"; enger lokaler Bug
  → billig; **nicht** vorhersagekräftig: „stack traces", „long problem statements".
- **SWE-Router** (Son u. a., arXiv 2607.00053, 2026-06-30) [belegt]: „a similar issue can hide either a
  localized typo or a multi-module refactor, and the prompt does not separate the two".
- **Scrouting** (Bhola u. a., arXiv 2608.04804, 2026-08-05, https://arxiv.org/html/2608.04804) [belegt]:
  „solve sets are strongly nested: the tasks a weaker model solves are largely a subset of those the strongest
  model solves" (0,941 / 0,912 / 0,773 auf SWE-bench Verified / Multilingual / Pro); „Routing for _cost_ …
  only requires predicting when a cheaper model will suffice". Vorhersage aus Auftragsmerkmalen: **AUC 0,600**
  (Handoff-Text 0,510 ≈ Zufall).

**[Meinung] Folgerungen:** (a) Verschachtelte Lösungsmengen → „kleinere Klasse, bei ‚wusste es nicht' eine
hoch" ist logisch sauber. (b) Schwache Vorhersage → nur messbare Felder abfragen. (c) Mehrere Dateien/Module,
Sprach-/Domänensemantik und Codezustand sind die Vorab-Merkmale mit gemessenem Wert für die **Klasse**.

## 2. Klassen- oder Effort-Merkmal — und was ein PM zuverlässig ablesen kann

### 2.1 Zuordnung der Merkmale

| Merkmal | Achse | Beleg | Aus dem Item ablesbar? |
|---|---|---|---|
| Nur lesen/zusammenfassen aus benannten Quellen, kein Code | **Klasse** (Kilo-Kandidat) | Luna „structured summaries"; Haiku „sub-agent tasks" | **hoch** (Rollen-`tools`, Ausgabe = Dokument) |
| Abnahme nennt einen Test + kleiner Umfang | **Klasse** (Mega) | Luna „when you know what a good result looks like"; Blog „describe precisely" | **hoch** (`acceptance_is_test_shaped`, DEC-0112) + `allowed_scope` zählen |
| Mehrere Dateien/Module, Symbol in mehreren Dateien | **Klasse** (Giga) | Applied Compute; Anthropic „large-scale refactoring" | **mittel–hoch** (`allowed_scope`) |
| Fremde Domäne / Sprachsemantik / subtile Bugs | **Klasse** (Giga) | Blog „unfamiliar domains"; Applied Compute | **niedrig–mittel** (Stack-Liste als Daten möglich) |
| Stundenlanger Lauf, Ursachensuche ohne Spur | **Klasse** (Tera-Kandidat) | Anthropic Matrix, model-config | **niedrig** vorab |
| Schutzfläche (Gates, Hooks, Auth, Rechte) / nicht umkehrbar | **Klasse-Boden** + Effort der Prüfung | Security low→max 64→87 % (FR-0097 §1.4); OpenAI „reversibility" | **mittel** (Pfadliste als Daten) |
| Ausgabe steuert andere Aufträge (Plan, SR/TSK-Schnitt, Architektur, erster Entwurf) | **Effort** (xhigh) — Klasse bleibt Giga | DEC-0127 (1)–(3), DEC-0129 Folgen | **hoch** (Item-Typ, Rolle) |
| Randfälle wahrscheinlich, Fehlersuche, unklare Vorgabe | **Effort** (high) | Claude Code: high „fixing bugs" (FR-0097 §1.3) | mittel |
| Klare Vorgabe + Test | **Effort** (medium) | Opus 5.5 medium ≥ Opus 5 high (FR-0097 §1.2) | hoch |
| Mehrdeutige Anforderung | **weder** — Rückfrage/Interview | FR-0097 §1.4/§5.3, DEC-0127 (6)/(7) | niedrig |

### 2.2 Urteil über die vier Lead-Fragen unter DEC-0129

- **F1 „steuert andere Aufträge → Giga"**: **keine Klassenfrage mehr** — Planung ist Giga wie der Standard,
  unterscheidet sich nur im Effort xhigh (DEC-0127, DEC-0129). [Meinung] → Effort-Liste, gebunden an Item-Typ/Rolle.
- **F2 „schon durchgefallen → eine Klasse hoch"**: **Widerspruch zu DEC-0096** (FAIL 1 → Effort, Klasse erst bei
  FAIL 3; gemessen: „every stream of generations 3-5 … FAILED their first verification round", meist
  Prosa-gegen-Code) und **DEC-0127 (6)** (falsche Lesart → Rückfrage). Anthropic trennt genauso (Blog:
  „not try hard enough" vs. „not know enough"). [Meinung] F2 gehört in die Eskalationsregel; der Hook liest
  den FAIL-Zähler, „wusste es nicht" bleibt PM-Urteil (DEC-0096 verwarf automatische Einstufung).
  **Spannung**: DEC-0096 hebt bei FAIL 3 Opus → Fable, DEC-0128 (2)/DEC-0129 (4) verlangen für Tera einen
  **gemessenen** Vorteil — ob FAIL 3 selbst als diese Messung zählt, muss der Nutzer entscheiden.
- **F3 „Test entscheidet und keine Designwahl → (heute) Mega/Sonnet"**: Testteil messbar (**A**). „Keine
  Designwahl"/„wenige Dateien" sind Auslegung. [Meinung] Zählbar machen: `allowed_scope` ≤ N Dateien in
  einem Verzeichnis, keine Schutzfläche; N wird gemessen (Start 3). Anthropics Schwelle „diff in one
  sentence" steht schon als Begründung in `team-kits/kernel/dispatch.py` (`acceptance_is_test_shaped`).
- **F4 „sonst"** → jetzt **Giga** (DEC-0129 Folgen; Anthropic „Most workloads start with Claude Opus 5.5", **A**).

**Lücken**: (1) kein **Boden** — eine Änderung an Gates/Hooks mit Testabnahme landete bei Mega; (2) keine
**Kilo**-Frage (DEC-0128 (3)); (3) **Tera** ist eine Ausnahme mit Messbeleg-ID, keine Frage.
**Reihenfolge**: Boden vor Senkung, Senkung vor Standard.

## 3. Wie man eine Klasse misst

**Zwei Achsen gleichzeitig messen.** [belegt, AA, §4.1] Opus 5.5 low (42 / 0,55 $) ≈ Sonnet 5.5 medium
(41 / 0,59 $). [Meinung] Klasse und Effort sind auf den Kosten austauschbar → jedes Modell auf ≥ 2 Stufen fahren.

**Aufgabenwahl** [belegt: Anthropic „Demystifying evals for AI agents", 2026-01-09,
https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents]: „20-50 simple tasks drawn from real
failures is a great start"; „two domain experts would independently reach the same pass/fail verdict";
„grade what the agent produced, not the path it took". [Meinung] Archivierte `TSK`/`BUG` mit rot/grünem Test,
vom Eltern-Commit nachgespielt unter `C:\Offline Repos\v2-testbed\_round-scratch\<TSK-ID>\`. Je Nutzungsregel
ein Satz: **Mega** (Test + kleiner Umfang), **Giga** (größer oder frühere FAIL-Runde), **Planung** (Rubrik +
blinder Paarvergleich durch den Nutzer), **Kilo** (Zusammenfassungen mit Hallu-Prüfung). Gelöst = Test grün
**und** Prüfer-PASS gegen `expected_outputs`, plus die Verhaltensgrößen aus radar/2026-09-28-claude-by-claude.md §2.

**Statistik** [belegt: Anthropic 2024-11-19, https://www.anthropic.com/research/statistical-approach-to-model-evals]:
Standardfehler, **gepaarte Differenzen** (Modellkorrelation „typically 0.3–0.7"), Mehrfachläufe,
**Power-Analyse**; „pass^k" misst Verlässlichkeit, jeder Lauf in sauberer Umgebung [Demystifying evals]. Mit
n = 25 war 7 Rettungen : 0 Rückschritte gerade signifikant (p = 0,016, FR-0097 §1.5). [Meinung] ≥ 3 Läufe je
Arm und Aufgabe; ein Modell kommt in eine Klasse / eine Nutzungsregel, wenn es gepaart **nicht schlechter**
löst (≤ 1 Aufgabe Rückschritt) **und** billiger je gelöster Aufgabe ist. Bei 100 % → härtere Aufgaben.

**Kosten je gelöster Aufgabe** = Summe aller Läufe ÷ gelöste. Tokenpreis reicht **nicht** [belegt, AA]:
Sonnet 5.5 max **7,60 $**, Opus 5.5 max **5,98 $** je Aufgabe — trotz halbem Tokenpreis. Cache-Lesepreise
(Fable 0,025×, Opus 5.5 0,05×, sonst 0,1×; Preisseite §4) gehören in die Rechnung.

**Tatsächliches Modell** [belegt, radar/2026-09-28-claude-by-claude.md §6]: `message.model` im Transkript zeigt
`claude-opus-5-5`, `*.meta.json` nur `opus`; was hinter `sonnet` läuft, hängt an der CLI-Version (Sonnet 5.5
ab 2.1.284). [Meinung] Arme mit voller Modell-ID fahren; je Lauf `message.model`, CLI-Version und
Frontmatter-Effort speichern; Läufe mit falschem Modell verwerfen.

**Hallu-Prüfung für Kilo** [belegt: Anthropic „Reduce hallucinations",
https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations]: „Allow
Claude to say 'I don't know'", erst wörtliche Zitate, „If it can't find a quote, it must retract the claim",
Best-of-N. [Meinung] Maschinenprüfbar: (1) jede Aussage trägt ein **wörtliches Zitat** mit Quelldatei;
(2) **Zitat existiert** — exakter Abgleich per Code, erfundene Zitate: Grenze **0**; (3) **jede Zahl** kommt
in der Quelle vor (Code); (4) **Zitat stützt Aussage** — Urteil eines Giga-Modells, Stichprobe vom Menschen;
(5) **Fallen**: 2–3 Fragen je Aufgabe ohne Antwort in den Quellen — richtig ist nur „steht nicht in der
Quelle"; (6) **Auslassung** gegen eine Kernpunktliste. [belegt, AA 2026-09-22,
https://artificialanalysis.ai/articles/gpt-6-sol-and-luna-push-the-cost-efficiency-frontier]:
Halluzinationsrate Sol 60 %, **Luna 77 %** — dieselbe Prüfung gilt für jedes Kilo-Modell jedes Anbieters.

## 4. Aktuelle Belege und ehrliche Einstufung

### 4.1 Zahlen

**Preise je 1 Mio. Tokens** [belegt, https://platform.claude.com/docs/en/about-claude/pricing]: Fable 5.1
**10 / 50 $**; Opus 5.5 **4 / 20 $**; Sonnet 5.5 **2 / 10 $**; Haiku 4.5 1 / 5 $ → Fable = **2,5×** Opus je Token.
OpenAI [belegt, https://developers.openai.com/api/docs/pricing laut radar/2026-09-28-codex-by-claude.md]: Astra
10 / 50 $, Sol 2 / 10 $, Luna 0,10 $ Eingabe.

**Artificial-Analysis-Index (Wert / $ je Aufgabe), Seiten gelesen 2026-09-28** [belegt]:

| Stufe | Opus 5.5 | Sonnet 5.5 | Fable 5.1 | GPT-6 Astra | GPT-6 Sol | GPT-6 Luna |
|---|---|---|---|---|---|---|
| low | 42 / 0,55 | 36 / 0,41 | 47 / 2,37 | – / 0,82 | – / 0,13 | 21 / – |
| medium | 51 / 1,34 | 41 / 0,59 | 49 / 2,98 | | | |
| high | 54 / 1,82 | 47 / 1,08 | 51 / 3,91 | | | 32 / – |
| xhigh | 56 / 3,46 | 52 / 2,74 | 53 / 5,98 | | | |
| max | 58 / 5,98 | 56 / 7,60 | 53 / 7,63 | 53 / 3,26 | 48 / 1,06 | 37 / 0,07 |

Quellen: https://artificialanalysis.ai/models/releases/claude-opus-5-5 , …/claude-sonnet-5-5 , …/claude-fable-5-1 ,
…/gpt-6-sol ; Astra: https://artificialanalysis.ai/articles/benchmarking-gpt-6-astra (2026-09-09: „Astra matches
the score at ~40% of the cost per task" von Fable 5.1); Luna: https://artificialanalysis.ai/models/gpt-6-luna
(Suchauszug). Haiku 4.5 (ohne Reasoning): 15 (https://artificialanalysis.ai/models/claude-4-5-haiku).

[Meinung] Auf diesem Index ist Fable 5.1 auf jeder Stufe von Opus 5.5 dominiert (max 53 < Opus high 54, bei
4× Kosten). **Einschränkung**: kurze Aufgaben; Fables Stärke laut Anthropic („sessions that run for hours")
misst er nicht. Das stützt „Tera nur mit gemessenem Vorteil" (**B**), beweist aber nichts für lange Läufe.

**Sonnet 5.5** (2026-09-28) [belegt, https://www.anthropic.com/claude-sonnet-5-5]: Terminal-Bench 4.0 70,6 %
(Opus 5.5 66,4 %; AA maß 64 % laut https://kingy.ai/blog/claude-sonnet-5-5-specs-benchmarks-pricing/);
„strongest at well-scoped everyday tasks, fixing bugs" — für uns ungemessen. **Haiku 5.5** [belegt, gleiche Seite]: „will join the Claude 5.5 family
in the coming weeks" — kein Datum, keine ID, kein Preis. **DeepSeek/Kimi** [nur Sekundärquelle,
https://llmgateway.io/timeline]: Kimi K3 (2026-07-16), DeepSeek V4.1 Flash (2026-09-10) — ungeprüft.

### 4.2 Ehrliche Einstufung anderer Anbieter (DEC-0129 (3)) [Meinung, auf den Belegen oben]

- **GPT-6 Luna → Kilo, Grenzfall zu Mega.** Beschreibung („high-volume", „structured summaries") und Preis
  (unter Haiku) sagen Kilo; der Index (max 37) liegt aber weit über Haiku 4.5 (15) und nahe Sonnet 5.5 low
  (36). Bis zur Messung Kilo (also **kein Code**, DEC-0129 (4)); besteht Luna den Mega-Satz gepaart gegen
  Sonnet, rückt es auf Mega. **C**.
- **GPT-6 Sol → Mega.** Preis = Sonnet 5.5; Index max 48 zwischen Sonnet 5.5 high (47) und xhigh (52). **B**.
- **GPT-6 Astra → Tera.** Indexwert (53) und Tokenpreis wie Fable 5.1, OpenAIs Spitzenmodell. Aber je Aufgabe
  max 3,26 $ — weniger als Opus 5.5 xhigh (3,46 $); der **Kostengrund** der Tera-Regel (DEC-0128) trifft nicht zu. **B**.
- **Giga bei OpenAI: leer.** Kein OpenAI-Modell liegt zwischen Sol und Astra.

### 4.3 Folge für den Standard-Bauer auf Codex (Entscheidung des Nutzers)

DEC-0129 setzt den Standard-Bauer auf **Giga**; auf Codex gibt es keins. Drei ehrliche Wege: **(a)** auf
Codex nach **unten** (Sol, Mega) als Standard — billiger, ungemessen, ob es für Bauaufträge reicht;
**(b)** nach **oben** (Astra, Tera) — widerspricht dem Wortlaut „Tera nur mit gemessenem Vorteil", obwohl der
Kostengrund bei Astra je Aufgabe nicht gilt; **(c)** die Tera-Regel als **Kostenregel** fassen („die Klasse
über dem Standard nur mit gemessenem Vorteil, wenn sie je gelöster Aufgabe teurer ist") und Astra messen.
[Meinung] (c) hält die Namen ehrlich und die Regel am Grund; bis zur Messung (a) mit Sol auf high.

## 5. Verfeinerte Frageliste (Vorschlag, [Meinung] auf §1–§4)

**Klasse** — der PM beantwortet in dieser Reihenfolge; jede Frage liest ein Feld, keine Einschätzung; die
Antworten sind die feste Begründungsliste für den Hook:

- **K1 Boden: Schutzfläche oder nicht umkehrbar?** `allowed_scope` trifft eine Pfadliste in Daten (Gates,
  Hooks, Auth, Berechtigungen, Migrationen, Löschpfade, Veröffentlichung) → **mindestens Giga**, K2/K3 entfallen. (**B**)
- **K2 Nur lesen und zusammenfassen?** Rolle ohne Code-Schreibwerkzeuge, Ausgabe = Dokument aus benannten
  Quellen → **Kilo**, sobald ein Kilo-Modell die Hallu-Prüfung bestanden hat (DEC-0128 (3)); bis dahin **Mega**. (**C**)
- **K3 Test entscheidet und Umfang klein?** `acceptance_is_test_shaped` wahr **und** `allowed_scope` ≤ N
  Dateien in einem Verzeichnis → **Mega**. N wird gemessen (Start 3). (**A** Testteil, **C** für N)
- **K4 Sonst** → **Giga** (Standard). (**A**)
- **Tera**: keine Frage, sondern Ausnahme mit der ID eines Messbelegs für genau diese Auftragsart
  (DEC-0128 (2)); Kandidaten laut Hersteller: stundenlange Läufe, „root-cause investigations". (**B**)
- **Nach einer Prüfung** (Eskalation, keine Startfrage): „wusste es nicht" („confidently wrong … with full
  context") → Klasse +1; „Fall übersehen" → Effort +1; „falsche Lesart" → Rückfrage über den Planer
  (DEC-0127 (6)); Reihenfolge und Zähler nach DEC-0096; die Tera-Spannung aus §2.2 entscheidet der Nutzer.

**Effort** — getrennt, Inhalte aus DEC-0127, hier nur als Fragen: **E1** Ausgabe steuert andere Aufträge
(Item-Typ/Rolle) → xhigh; **E2** Vorgabe + Testabnahme → medium; **E3** Fehlersuche/unklare Vorgabe/viele
Dateien → high; **E4** Prüfer → high, Schutzfläche (K1) einmal benannt xhigh. Offen: Mega-(Sonnet-)Bauer —
DEC-0127 (4) sagt high, die Sonnet-5.5-Doku sagt medium „for well-specified tasks" (FR-0097 §1.1) → im
Mega-Satz beide fahren.

## 6. Klassentabelle (Zuordnung = Datei-Daten, gepflegt durch Messung, DEC-0126 (3))

| Klasse | Nutzungsregel | Claude | OpenAI | Beweisstärke |
|---|---|---|---|---|
| **Peta** | — | leer | leer | — |
| **Tera** | nur mit Messbeleg-ID | Fable 5.1 (10/50 $) | GPT-6 Astra (10/50 $; je Aufgabe billiger als Opus 5.5 xhigh) | **B** (AA: Fable ≤ Opus 5.5 high; Astra = Fable im Index) |
| **Giga** | Standard (K4), Boden (K1), Planung mit E1 | Opus 5.5 | **leer** → §4.3 | **A** Claude („Most workloads start with Opus 5.5") |
| **Mega** | K3 (Test + klein); K2 bis Kilo offen | Sonnet 5.5 | GPT-6 Sol | Claude **B** (Hersteller + AA-Grenze), Sol **B**; für unsere Aufträge ungemessen |
| **Kilo** | K2 nach Hallu-Messung; **nie Code** | Haiku 4.5 gesperrt; Haiku 5.5 nach Messung | GPT-6 Luna (Grenzfall zu Mega, messen) | **C** — Haiku 5.5 nicht erschienen; Luna Hallu-Rate 77 % |
| **Milli** | — | leer | leer | — |

**Erste Messaufträge** [Meinung]: (1) Mega-Satz: Sonnet 5.5 medium/high gegen Opus 5.5 low/medium, gepaart,
Auswertung nach Dateizahl für N; (2) Kilo-Satz mit Hallu-Prüfung, sobald Haiku 5.5 erscheint (Luna als
Vergleich); (3) Codex: Sol high gegen Astra low/medium auf dem Giga-Satz; (4) Tera je gescheitertem Auftrag.
