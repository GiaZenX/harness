# FR-0097 — Welche Denktiefe (effort) für welche Rolle? Recherche 2026-09-28

Read-only-Recherche. Alle Webseiten am **2026-09-28** gelesen. Kennzeichnung: **[belegt]** = steht so in
der genannten Quelle (Zahl oder Wortlaut); **[Meinung]** = meine Ableitung/Empfehlung. Beweisstärke in
den Tabellen: **A** = Herstellerdoku + unabhängige Messung stimmen überein; **B** = eine Quelle (Doku
ODER eine Messung); **C** = nur Ableitung/Analogie, keine direkte Messung.

## 0. Kurzantwort

1. **Ja, die Staffelung „planen/klären → bauen niedriger → prüfen hoch" ist belegt** — aber der Hebel
   beim Planen ist laut der Quelle des Videos **das Interview mit dem Menschen und die Spezifikation**,
   nicht eine höhere Denktiefe. Für „Planer auf xhigh" habe ich **keinen** Beleg gefunden.
2. **Bauer auf medium ohne Qualitätsverlust: für Opus 5.5 (Mega) gut gestützt, für Sonnet 5 (Kilo) nicht.**
   Opus 5.5 auf medium ≈ Opus 5 auf high (Anthropic); in einer vorregistrierten Messung lag Opus 5 auf
   `low` auf der Kosten-Erfolgs-Grenze, Sonnet 5 brauchte dagegen `high` (12→19 von 25, signifikant).
3. **xhigh ist für Code-Arbeit eher schlechter als high** (Opus 5 und Sonnet 5, n=25, nicht signifikant,
   aber teurer, alle Timeouts/leeren Patches bei high/xhigh). Der Plan-Befund 0c ist damit **bestätigt,
   mit Einschränkung** (Opus **5**, nicht 5.5; kleine Stichprobe).
4. **Mehr Denktiefe fängt vergessene Fälle, repariert aber keine falsche Lesart.** Das stimmt mit den
   Zahlen; „mehr Denktiefe macht mehr Fehlinterpretationen" ist nur **halb** belegt (eine Unterkategorie
   stieg 25→47, die Summe der Fehlentscheidungen fiel 133→107).
5. **Pro Rolle einstellbar: ja** — Claude Code per Frontmatter `effort:` je Subagent, Codex per
   `model_reasoning_effort` je `.codex/agents/*.toml`. **Pro einzelnem Start (Agent-Tool): in Claude Code
   weiterhin nicht dokumentiert** → H169 bleibt richtig, die Rollenvarianten aus Plan V2.5 §4 sind der Weg.

## 1. Primärquellen

### 1.1 Anthropic — Effort-Doku (platform.claude.com, gelesen 2026-09-28)
Quelle: https://platform.claude.com/docs/en/build-with-claude/effort
- [belegt] Stufentabelle: `low` „Simpler tasks … such as subagents"; `medium` „Agentic tasks that require a
  balance of speed, cost, and performance"; `high` „Complex reasoning, difficult coding problems, agentic
  tasks"; `xhigh` „Long-running agentic and coding tasks (over 30 minutes) with token budgets in the
  millions"; `max` „deepest possible reasoning". Effort ist „a behavioral signal, not a strict token budget"
  und wirkt auf **alle** Ausgabe-Tokens (Text, Werkzeugaufrufe, Denken).
- [belegt] **Opus 5.5: Standard ist `medium`** (alle anderen Modelle `high`); Denken ist immer an; „Run an
  effort sweep on your own evals rather than carrying settings over".
- [belegt] **Sonnet 5.5** (neu, noch nicht in unserer Leiter): „For agentic coding and multistep tool use,
  start with `medium` for well-specified tasks and move to `high` for harder or longer ones … Use `xhigh` or
  `max` only where your evals show a quality gain." — die einzige Herstellerstelle, die **„gut
  spezifiziert → medium"** wörtlich sagt.
- [belegt] Sonnet 5: Standard `high`; `medium` „Cost-saving step-down … Comparable to Claude Sonnet 4.6 at
  high effort"; `xhigh` „For the hardest coding and agentic tasks".
- [belegt] Fable 5.1: Start `high`, `xhigh`/`max` „for the most capability-sensitive agentic and coding
  work", `medium`/`low` für Routine „once your evals show quality holds".

### 1.2 Anthropic — Prompting Claude Opus 5.5 (gelesen 2026-09-28)
Quelle: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5
- [belegt] „at its default `medium` effort the model matched or beat Claude Opus 5 at `high` effort on such
  tasks [agentic coding], in fewer steps and with fewer tokens"; „on several coding evaluations `low` comes
  close to it at much lower cost."
- [belegt] „At a given level, Claude Opus 5.5 tends to think more per turn than Claude Opus 5, especially at
  `xhigh` and `max`" und: „**Reserve `xhigh` and `max` for work where you've measured a quality gain.**"
- [belegt] Stärkere Code-Review als Opus 5: „more bugs caught … and fewer false alarms" (Tester-Berichte).

### 1.3 Claude Code — Model config + Subagents (code.claude.com, gelesen 2026-09-28)
Quellen: https://code.claude.com/docs/en/model-config , https://code.claude.com/docs/en/sub-agents
- [belegt] Tabelle „When to use each level": `low` „brainstorming, first sketches, small changes like
  renames"; `medium` „Day-to-day engineering work with a clear scope"; `high` „Work where verification
  matters or edge cases are likely, such as fixing bugs"; `max` „Hard problems you want Claude to work
  through without you, like finding security vulnerabilities. May show diminishing returns and is prone to
  overthinking". → Das ist **wörtlich die Faustregel des Videos**.
- [belegt] Subagent-Frontmatter `effort`: „Overrides the session effort level. Default: inherits from
  session." Respektiert `maxEffortLevel` und Organisations-Deckel. `/tasks` zeigt die Stufe (ab v2.1.242).
- [belegt] Ein Effort-Parameter **pro Aufruf des Agent-Tools ist nicht dokumentiert**. Der Wunsch danach
  (Frontmatter **und** Aufruf-Parameter) stand in https://github.com/anthropics/claude-code/issues/43083
  (geschlossen 2026-04-03; was davon gebaut wurde, zeigt die Seite nicht — die Doku nennt nur Frontmatter).
- [belegt] Stolperstein: „A top-level `effortLevel` in user settings doesn't apply to Opus 5.5" — für
  Opus 5.5 zählen `/effort`, `--effort`, `modelSettings` je Modell oder Frontmatter.
- [belegt] `opusplan`: Opus im Plan-Modus, Sonnet in der Ausführung — Anthropic liefert die Rollentrennung
  „stark planen, günstiger bauen" als eingebaute Einstellung (auf der **Modell**-Achse, nicht Effort).

### 1.4 Die Quelle des Videos: claude.dev-Blog „Spending your effort" (gelesen 2026-09-28)
Quelle: https://claude.dev/blog/spending-your-effort/ — Autor Thariq Shihipar, **2026-09-25**. Die Seite
nennt keine Zugehörigkeit; ob claude.dev eine Anthropic-Seite ist, konnte ich auf der Seite nicht sehen
(der Autor ist öffentlich als Claude-Code-Mitarbeiter bekannt — nicht auf der Seite belegt).
- [belegt] Terminal-Bench 3.0, **Fable 5.1**, je 370 Versuche: low 140 bestanden (Median 73k Tokens), max 214
  (Median 222k). Fehlerarten low → max: „a bug its tests missed" 40→14, „misread a requirement" 45→26,
  „wrong or incomplete fix" 31→10, „got the domain rule wrong" 32→24, „**picked the wrong reading" 25→47**,
  „close, but not exact" 10→6, „overfit to the examples" 7→3, other 38→25.
- [belegt] Zitat: „Increasing effort tends to reduce failures due to missing edgecases … but does not fix
  when the model has the wrong approach."
- [belegt] Bestandsquote je Bereich low → höchste Stufe: Security 64→87 %, Hardware 34→75 %, **Software
  43→56 %** (kleinster Zuwachs unter den Code-nahen Bereichen), Operations 12→22 %.
- [belegt] Eigene Bauten: unterspezifizierte Fitness-App low/medium/high/max = **1,5 / 4 / 11 / 67 min**;
  nach Interview → Spezifikation **16 / 22 / 33 / 79 min**, und „given this spec, the models behaved much
  more similarly".
- [belegt] Empfohlener Ablauf: „Give Claude a spec and ask it to interview me about any details I'm missing.
  **Implement it on low effort.** Review to make sure it got the gist correct, iterate on low effort as
  needed. **Verify and test on high effort.**"

### 1.5 Studie arXiv 2608.01347 (Weinberger/Hozez, v1 2026-08-02, v6 2026-09-10)
Quelle: https://arxiv.org/abs/2608.01347 (PDF S. 33–35, Anhang N; selbst im Volltext nachgelesen)
- [belegt] Vorregistrierte Kampagne, 25 harte SWE-bench-Verified-Aufgaben, Claude Code 2.1.220, low/high/xhigh
  gepaart (150 Zellen). **Opus 5**: gelöst 17 / 18 / 16 von 25, Kosten je gelöster Aufgabe **0,75 $ / 1,89 $ /
  3,62 $** → „low effort lies on the observed cost–success frontier for Opus 5". **Sonnet 5**: 12 / 19 / 17,
  high vs. low **p = 0,016** (7 Rettungen, 0 Rückschritte), Kosten 1,76 $ / 2,32 $ / 3,00 $ → „xhigh is
  dominated by high in this sample".
- [belegt] „All six timeouts and all four empty patches occurred at high or xhigh effort"; die
  xhigh-Rückschritte: „one scope-expanding edit broke previously passing tests, and one run timed out".
- [belegt] Eine vorregistrierte „Eskalation bei Anzeichen"-Regel verbesserte die Grenze **nicht** (Sonnet ≈
  immer-xhigh, Opus schlechter als immer-low).
- [belegt] Zur Spezifikation (S. 3–4, 9): eine Vorlage mit Umfang, „smallest-sufficient-change" und
  Stoppregel hatte „no measurable cost penalty"; „Bounded-efficiency wording does not reduce diagnosis or
  final validation on **well-specified** tasks", aber bei **mehrdeutiger** Spezifikation 3/5 versteckte
  Testfehler gegen 0/5, weil die Anforderungsdatei im Repo nicht gelesen wurde.
- Einschränkung: Opus **5** und Sonnet **5**, nicht Opus 5.5; n = 25; xhigh vs. high nicht signifikant.

### 1.6 OpenAI / Codex (gelesen 2026-09-28)
- [belegt] Codex-Modellseite https://learn.chatgpt.com/docs/models : Standard-Effort in Codex **Astra = Light/
  Low, Sol = Medium, Luna = High**; mehr Effort, wenn die Aufgabe „more planning, analysis, or checking"
  braucht; Max für außergewöhnlich schwere Probleme; **Ultra** verteilt Arbeit auf Subagenten; „most tasks do
  not need Max or Ultra".
- [belegt] API-Leitfaden https://developers.openai.com/api/docs/guides/reasoning : `medium` „Default
  configuration for most workloads"; `high` „hard reasoning, complex debugging, deep planning"; `xhigh` nur
  „when evals justify the extra cost"; für agentisches Coding „both `medium` and `high`" testen. (API-Standard
  Sol/Luna = medium — weicht von Codex' Luna = High ab.)
- [belegt] Subagents https://learn.chatgpt.com/docs/agent-configuration/subagents : `model` +
  `model_reasoning_effort` je `.codex/agents/*.toml`; Auflösung „from an **explicit spawn value**, then the
  corresponding `[agents]` default, then the parent's value" — ein Startwert pro Aufruf existiert also im
  Modell, **wie** er übergeben wird, sagt die Seite nicht. Beispiel der Seite: Explorer `gpt-6-luna`/`high`,
  **Reviewer `gpt-6-sol`/`medium`**. Werte bis `ultra` „when supported".
- Zu H172 [belegt]: beide OpenAI-Seiten führen heute **max UND ultra** (ultra als Subagenten-Modus, nicht für
  jedes Modell). Gegen die CLI gemessen ist das hier weiterhin nicht.

### 1.7 Ältere, aber einschlägige Messungen zur Rollentrennung
- [belegt] Aider Architect/Editor (2024-09-26, https://aider.chat/2024/09/26/architect.html): Denker +
  Umsetzer schlägt das Einzelmodell (o1-preview + Editor 85 %; Sonnet+Sonnet 80,5 % vs. solo 77,4 %).
- [belegt] Anthropic Multi-Agent-Research (2025-06-13, https://www.anthropic.com/engineering/multi-agent-research-system):
  Opus-Lead + Sonnet-Subagenten +90,2 % gegenüber Opus allein; Subagenten brauchen „an objective, an output
  format, guidance on the tools … and clear task boundaries"; Multi-Agent ≈ 15× Tokens eines Chats.
- Beide betreffen die **Modell**-Achse und ältere Modelle — Analogie für Effort, kein direkter Beleg.

## 2. Prüfung der Video-Behauptungen (YouTube-Short @DIYSmartCode, KI-generiert)

| # | Behauptung im Video | Urteil | Grundlage |
|---|---|---|---|
| 1 | Gleicher Prompt, Opus 5.5 low/medium/high/max = 1,5/4/11/39 min | **teilweise** — 1,5/4/11 stimmen; der Blog nennt für diesen Bau max **67 min**; „39 min" steht laut Auszug bei einem anderen Bau. Welches Modell diese Bauten fuhr, nennt der Auszug nicht | §1.4 |
| 2 | Mit Interview → Spec wurden die Ergebnisse sehr ähnlich | **belegt** (qualitativ, ein Bau, Urteil des Autors); die **Laufzeiten** blieben aber gestreut (16–79 min) | §1.4 |
| 3 | 370 Versuche, Fable 5.1 low vs. max: 140 → 214 bestanden | **belegt** | §1.4 |
| 4 | Übersehene Fälle fielen | **belegt** (z. B. „bug its tests missed" 40→14) | §1.4 |
| 5 | „Picked the wrong reading" stieg 25 → 47 | **Zahl belegt, Deutung nur halb**: „misread a requirement" fiel 45→26, alle Fehlentscheidungen zusammen 133→107; kein Signifikanztest | §1.4 |
| 6 | Tokens verdreifacht, Median 73k → 222k | **belegt** | §1.4 |
| 7 | max fängt fehlende Fälle, repariert keinen falschen Ansatz | **belegt** (Zitat) | §1.4 |
| 8 | Faustregel low=Skizze, medium=Feature, high=Bug/Randfälle, max=schwere Übergabe | **belegt**, sogar in der offiziellen Claude-Code-Doku | §1.3 |
| 9 | „Bauen low/med, selbst reviewen, prüfen high" | **belegt**; der Blog sagt sogar **low** fürs Bauen | §1.4 |
| — | Folgerung des Nutzers „PM/Architekt auf xhigh" | **nicht belegt** — im Blog kommt die Klärung aus dem Interview, nicht aus xhigh; Anthropic: xhigh nur bei gemessenem Gewinn | §1.2, §1.4, §1.5 |

[Meinung] Zu #5: Die Kategorien schließen sich je Fehlversuch aus. Wenn max mehr Versuche an Randfällen
vorbeibringt, scheitern die übrigen öfter erst an der Lesart — ein Anstieg dieser einen Kategorie ist
auch ohne „mehr Fehlinterpretation durch Denken" erklärbar. Sicher ist nur: Effort beseitigt diese
Fehlerklasse nicht. Mehrdeutigkeit wird durch eine Rückfrage behoben, nicht durch mehr Rechnen.

## 3. Mehrkosten je Stufe (was belegt ist)

| Messung | low | medium | high | xhigh | max | Quelle |
|---|---|---|---|---|---|---|
| Fable 5.1, Terminal-Bench 3.0, Median-Tokens | 73k | – | – | – | 222k (≈3×) | §1.4 |
| Eigener Bau ohne Spec, Minuten | 1,5 | 4 | 11 | – | 67 | §1.4 |
| Gleicher Bau mit Spec, Minuten | 16 | 22 | 33 | – | 79 | §1.4 |
| Opus 5, $ je gelöster Aufgabe (SWE-bench hart) | 0,75 | – | 1,89 | 3,62 | – | §1.5 |
| Sonnet 5, $ je gelöster Aufgabe | 1,76 | – | 2,32 | 3,00 | – | §1.5 |
| Ausgabe-Tokens low → xhigh | Sonnet 5 5.253 → 35.113 (6,7×); Opus 5 9.040 → 21.719 (2,4×) | | | | | §1.5 |
| „high effort path … roughly 7x more tokens" (gleicher Prompt, zwei Stufen) | | | | | | claude.com-Blog 2026-07-07, zitiert nach staging/FR-0091/research-A-anthropic.md |

[Meinung] Faustwert: jede Stufe nach oben kostet grob das 1,5- bis 3-fache an Zeit/Tokens; ab high steigt
das Risiko von Zeitüberschreitung und Umfangsausweitung (§1.5).

## 4. Unser Stand (gelesen, nicht geändert)

- DEC-0088 (1)/(3)/(4): Bauer oberste Sprosse auf **high**, Prüfer Opus auf **high**, xhigh/max nur für einen
  benannten Schritt. DEC-0118: Architektur-Schritt auf Claude = **Opus xhigh**, Deckel xhigh.
  DEC-0124 / Plan V2.5 §4: zwei Achsen (Kilo/Mega/Giga × niedrig…sehr hoch) mit Grund aus fester Liste;
  „sehr hoch" nur für benannte Architektur-Schritte.
- Heute tragen **alle** neun dev-team-Rollen `effort: high` in der Frontmatter
  (`team-kits/dev-team/agents/*.md`), `ladder.yaml` `effort: {default: high, large: xhigh}`.
- [Meinung] Folge von §1.1: Unsere Opus-5.5-Rollen laufen damit **eine Stufe über** dem Herstellerstandard.
  Für PM, Prüfer und Architekt ist das gewollt; für Bauer mit fertiger Spezifikation ist es nach §1.2/§1.5
  wahrscheinlich bezahlte Denkzeit ohne Gegenwert.

## 5. Empfehlung: Rolle → Modellklasse + Denktiefe

### 5.1 Claude (Kilo = Sonnet 5, Mega = Opus 5.5, Giga = auf Claude derzeit Opus 5.5)

| Rolle | Klasse | Effort | Grund | Stärke |
|---|---|---|---|---|
| PM / Orchestrator (plant, schneidet, klärt mit dem Nutzer) | Mega | **high** | Dauerkosten (DEC-0095); Klärung kommt aus der Rückfrage an den Nutzer, nicht aus xhigh (§1.4); high = „verification matters" (§1.3) | B |
| Architekt (friert die Details ein, 1 Dokument) | Giga | **xhigh** laut DEC-0118 — **unbelegt**; Beleg spricht eher für high | xhigh laut Hersteller für >30-min-Läufe und nur mit gemessenem Gewinn (§1.1, §1.2); xhigh bei Code ≤ high (§1.5). Vorschlag: DEC-0118 stehen lassen, aber messen (s. §6) | C |
| Designer | Mega | **high** | Urteil + Randfälle; kein Beleg für mehr | C |
| Bauer, Auftrag mit eingefrorener Spec + Test-Abnahme | Mega | **medium** | Opus 5.5 medium ≥ Opus 5 high bei Coding (§1.2); Opus 5 low auf Kosten-Erfolgs-Grenze (§1.5); Blog baut sogar auf low (§1.4) | **A** |
| Bauer, Spec lückenhaft / Fehlersuche / viele Dateien | Mega | **high** | high = „bugs, edge cases" (§1.3); mehrdeutige Spec + Sparmodus → 3/5 Fehler (§1.5) | A |
| Bauer mechanisch (Kilo-Scheibe, DEC-0097/0112) | Kilo | **high** (Sonnet 5) | Sonnet 5 low→high 12→19/25, p=0,016 (§1.5); Hersteller-Standard high (§1.1). Mit Sonnet 5.5: medium bei gut spezifiziert, nach eigenem Sweep | A |
| Prüfer (unabhängig, gegen Abnahmekriterien) | Mega | **high** | Effort senkt genau „übersehene Fälle" (40→14, §1.4); „Verify and test on high" (§1.4); high = „verification matters" (§1.3) | A |
| Prüfer, sicherheitskritisch / großes Ziel, einmal benannt | Mega | **xhigh** (Deckel, kein max) | max „like finding security vulnerabilities" (§1.3), Security-Zuwachs am größten 64→87 % (§1.4); Deckel xhigh nach DEC-0118 | B |
| Explorer / Suche / Zusammenfassung | Kilo | medium–low | `low` „such as subagents" (§1.1); nie Haiku (Plan V2.5) | B |

### 5.2 Codex (Kilo = GPT-6 Luna, Mega = GPT-6 Sol, Giga = GPT-6 Astra)

| Rolle | Klasse | Effort | Grund | Stärke |
|---|---|---|---|---|
| PM / Orchestrator | Mega (Sol) | **high** | API: high für „deep planning" (§1.6) | B |
| Architekt | Giga (Astra) | **high**, xhigh nur benannt | Astra-Standard in Codex ist **Low** → muss ausdrücklich gesetzt werden; xhigh nur „when evals justify" (§1.6) | B |
| Bauer mit Spec + Test | Mega (Sol) | **medium** | Codex-Standard für Sol; „medium … default for most workloads" (§1.6) | B |
| Bauer, unklar / Debugging | Mega (Sol) | **high** | „complex debugging" (§1.6) | B |
| Bauer mechanisch | Kilo (Luna) | **high** | Codex-Standard für Luna (§1.6) | B |
| Prüfer | Mega (Sol) | **high** | Claude-seitige Belege (§1.3/§1.4); **Abweichung:** OpenAIs Beispiel setzt den Reviewer auf medium (§1.6) | C |

### 5.3 Wann eskalieren (passt zu DEC-0088 (c) und DEC-0096)

- [belegt, Anthropic-Blog 2026-07-07 via FR-0091 A §3] **Effort hoch**, wenn das Scheitern an Sorgfalt lag
  (Datei übersprungen, Tests nicht gefahren, Umbau abgebrochen); **Modell hoch**, wenn „confidently wrong"
  mit vollem Kontext.
- [belegt §1.4] Effort beseitigt „übersehene Fälle", nicht „falsche Lesart".
- [Meinung] Daraus eine Zeile für die feste Begründungsliste: Befund „falsche Lesart / Anforderung
  missverstanden" → **zurück zum PM/Architekten mit einer Rückfrage an den Nutzer**, keine
  Effort-Eskalation. Befund „Randfall übersehen / Test fehlt" → Effort eine Stufe hoch (medium → high).
  xhigh für Bauer nur nach zwei gescheiterten Prüfungen **und** wenn der Auftrag nicht enger schneidbar ist.
- [belegt §1.5] Eine automatische „bei Anzeichen hochschalten"-Regel verbesserte in der Studie nichts —
  Eskalation am Befund der Prüfung festmachen, nicht an Laufzeit-Signalen.

## 6. Offene Punkte / was nur wir messen können

- [Meinung] **Bauer medium vs. high auf Opus 5.5** ist die größte Einsparung (Faktor ~1,5–3 je Auftrag) und
  am besten belegt — trotzdem einmal selbst messen: die nächsten Bauaufträge mit Spec + Test abwechselnd
  auf medium/high, Kennzahl „Prüfrunden bis bestanden" (`report.lease_distribution`) und Tokens
  (`tools/measure_agent_tokens.py`).
- [Meinung] **Architekt xhigh vs. high** (DEC-0118): kein externer Beleg in beide Richtungen für
  Planungs-/Spezifikationsarbeit. Zwei, drei Architektur-Schritte doppelt fahren und vom Nutzer blind
  vergleichen lassen, bevor der Deckel festgeschrieben bleibt.
- **Technik Claude:** pro Rolle per Frontmatter geht, pro Start nicht (H169 bleibt). Rollenvarianten
  (z. B. `backend-developer` medium/high) aus dem Generator sind der dokumentierte Weg (Plan V2.5 §4).
- **Technik Codex:** pro Rolle per TOML; ein „explicit spawn value" ist dokumentiert, aber nicht, wie er
  übergeben wird — unmessbar ohne Codex-CLI auf dem Messrechner (wie H172).
- Sonnet 5.5 ist erschienen (Effort-Doku §1.1) und rechnet seine Stufen neu — betrifft Kilo beim nächsten
  Watcher-Bericht (Plan V2.5: Tausch nur mit Messlauf).
