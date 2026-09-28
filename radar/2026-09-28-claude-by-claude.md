# Radar — 2026-09-28 (claude-watcher, run by claude) — Sonderlauf „Es gibt neue Modelle"

Anlass: Wunsch des Nutzers vom 2026-09-28. Der Schwerpunkt liegt auf neuen Anthropic-Modellen und auf
der Pflichtfrage aus Plan V2.5 §4 bzw. `DEC-0124`: *Ersetzt ein neues Modell ein Modell der Leiter?* —
**entschieden wird das nur mit einem Messlauf auf festen Beispielaufgaben, nie auf eine Ankündigung
hin.** Dieser Bericht empfiehlt deshalb **keinen Tausch**. Er sagt, was eine solche Messung vergleichen
müsste. Aufbau nach Plan V2.5: **Teil 1 „Was bringt es unserem Repo?"**, **Teil 2 „Was hat sich
insgesamt getan?"**, in Teil 2 mit einem zweiten Blick auf Dinge, die zunächst nicht zu passen scheinen.

Zeitraum: Claude-Code-Changelog **2.1.283 → 2.1.284** (25. bis 28. Sep.; der letzte Bericht reichte bis
2.1.282), dazu die offiziellen Modellseiten (Übersicht, Sonnet-5.5-Seiten, Effort-Doku, Prompting-Leitfäden
für Opus 5.5 und Sonnet 5.5, Deprecations), anthropic.com/news, die Claude-Code-Doku (model-config,
sub-agents, permission-modes, costs) und ein kurzer Blick in die Community. **Alles gesehen am 2026-09-28.**

Zuerst gelesen: `radar/decided.md` und `radar/2026-09-25-claude-by-claude.md`. **Hinweis zur Buchführung:**
`decided.md` endet mit der Triage vom 2026-09-05. Die Punkte 1, 2 und 6 vom 09-25 sind inzwischen durch
`DEC-0114` entschieden (Namen folgen weiter dem neuesten Modell, keine Preise mehr, Lead auf `xhigh` —
im Baum nachgemessen: `.claude/agents/harness-lead.md:11 effort: xhigh`), stehen aber nicht in `decided.md`.
Nichts davon kommt hier noch einmal.

---

## Gesundheit des Repos — grün, mit einem kleinen lokalen Lint-Fund

- `python tools/validate.py` → **`all structural checks passed.`**
- `python -m ruff check .` (ruff 0.15.20, gepinnt) → **1 Fehler**, F841 (Variable zugewiesen, nie benutzt)
  in `project_memory/staging/generation-6/create_order_7_merge.py:55` (`base = sys.argv[1]`). Die Datei
  ist **nicht eingecheckt** (`??` in `git status`), CI sieht sie also nicht; lokal ist `ruff check .` aber
  rot, bis die Datei aufgeräumt ist oder `staging/` vom Lint ausgenommen wird. Nur gemeldet, nicht behoben.
- `python -m pytest tools/ -q` → **nicht gefahren**, und das ist gewollt: `gate_test_scope.py` verweigert
  den vollen Lauf ohne `DELIVERY_RUN=<ITEM-ID>`, und ein Watcher-Lauf ist keine Lieferung. Teilmenge:
  `tools/test_model_ladder.py tools/test_repo_hygiene.py tools/test_radar_trigger.py` → **80 passed,
  1 warning in 191 s** (die bekannte CRLF-Warnung zu `project_memory/.audit/hook_events.jsonl`).
- **Eine Beobachtung für die §5-Kennzahl „Fehlblockaden" aus Plan V2.5:** In diesem einen, rein lesenden
  Lauf hat `gate_lead_write_scope.py` **dreimal eine Zeile verweigert, die nichts schreibt**: `ls` mit
  `team-kits/*/ladder.yaml`, eine `for`-Schleife mit `head` (das Gate las das Wort `for` als Zielpfad unter
  `decisions/active/`), und ein Python-Aufruf mit einem `*`-Pfad. Das ist genau die Klasse, die Strom B
  ersetzen soll. Die Befehlszeilen sind in diesem Bericht nicht wörtlich festgehalten; der Hook-Audit des
  Laufs hat sie.

---

# Teil 1 — Was bringt es unserem Repo?

## 1. Claude Sonnet 5.5 ist erschienen und hat die `sonnet`-Sprosse („Kilo") heute von selbst übernommen: `DEC-0114` (2) und `DEC-0124` widersprechen sich hier zum ersten Mal

- **Quellen** (alle gesehen 2026-09-28):
  - Changelog 2.1.284 (28. Sep.), wörtlich: *„Added Claude Sonnet 5.5 (`claude-sonnet-5-5`), now the
    default Sonnet model on the Anthropic API — 1M context, $2/$10 per Mtok with $0.20/Mtok cache reads"* —
    https://code.claude.com/docs/en/changelog
  - Modellseite: *„**Latest.** Released September 28, 2026 … The best combination of speed and
    intelligence"*, Standard-Denktiefe `high` (API), Denken „Adaptive", 1M Kontext, 128K Ausgabe,
    Abschaltung nicht vor 2027-09-28 — https://platform.claude.com/docs/en/models/sonnet-5-5/overview
  - Claude-Code-Doku, Tabelle „Alias Resolution by Provider": **Anthropic API: `opus` → Opus 5.5,
    `sonnet` → Sonnet 5.5**. Standard-Denktiefe in Claude Code: *„`medium`: default on Opus 5.5 and
    Sonnet 5.5"* — https://code.claude.com/docs/en/model-config
  - Anthropic, wörtlich: *„In Claude Code and our apps, the default effort is set to Medium, while the
    Claude Platform defaults to High."* und *„At Medium effort, the default in the Claude apps, Sonnet 5.5
    far exceeds Sonnet 5's best score for less than a tenth of the cost per task."* —
    https://www.anthropic.com/claude-sonnet-5-5 (Herstellerangabe, von uns nicht gemessen)
- **Was das heißt, einfach gesagt:** In unserer Stufentabelle steht auf der Claude-Seite nur der **Name**
  `sonnet`, kein fester Modellname (`team-kits/model_tiers.yaml` `tiers.claude.sonnet: sonnet`). Das hat
  der Nutzer am 2026-09-25 ausdrücklich so gewollt (`DEC-0114` (2): *„damit automatisch immer die
  aktuellste Version aufgerufen wird"*). Sobald Claude Code auf 2.1.284 oder neuer aktualisiert ist,
  arbeitet also **jeder Auftrag, der auf `sonnet` läuft, mit Sonnet 5.5 statt Sonnet 5**, ohne dass
  jemand etwas ändert.
  **`DEC-0124` (Plan V2.5, freigegeben am 2026-09-27) sagt aber:** *„a new model replaces a ladder model
  only with measured proof"* — ohne Messung kein Tausch. Auf der Claude-Seite lässt sich beides nicht
  gleichzeitig einhalten. `DEC-0124` nennt in seiner Ablöseliste `DEC-0034/0076-0078/0091/0092/0095-0097`,
  **aber nicht `DEC-0114`**. Welche Regel gilt, ist also nirgends festgehalten.
- **Wen es trifft, im Baum nachgezählt:**
  - **office-team: jede Bau-Arbeit.** `team-kits/office-team/ladder.yaml` hat `build: pin` und
    `reading: pin` mit `effort.default: medium`. Bookkeeper, Product-Editor, Shop-Curator,
    Compliance-Researcher und Marketing-Planner arbeiten **standardmäßig** auf `sonnet`, Records-Clerk und
    Filing-Reviewer mit `effort: low`. Im Office-Kit ist Sonnet also das **tragende** Bau-Modell.
  - **dev-team und research-team: nur Arbeitspakete mit einem benannten Test.** Dort steht `build:
    default: opus, floor: pin`. `sonnet` gibt es nur, wenn ein Auftrag ausdrücklich darum bittet und seine
    Abnahme einen Test nennt (`DEC-0097`/`DEC-0112`).
  - Dieses Repo selbst: alle fünf eigenen Rollen laufen auf `opus`. Nicht betroffen.
- **Die Pflichtfrage, beantwortet:** *Ersetzt Sonnet 5.5 ein Leiter-Modell?* — **Dem Namen nach ja, und
  zwar automatisch.** Belegt ist das nicht: Es gibt **keine Messung** in diesem Repo, und dieser Bericht
  empfiehlt den Tausch nicht. Drei Wege, die nur der Nutzer entscheiden kann:
  - **(a) `DEC-0114` (2) bleibt:** Der Name folgt weiter von selbst. Die Messung aus Punkt 2 wird eine
    **Nachkontrolle mit Rückweg**. Verliert Sonnet 5.5, hält man die Sprosse über
    `env.ANTHROPIC_DEFAULT_SONNET_MODEL: claude-sonnet-5` in den Kit-Einstellungen auf dem alten Modell
    (dokumentierte Variable, https://code.claude.com/docs/en/model-config).
  - **(b) `DEC-0124` gilt auch für Claude:** Die Sprosse bleibt auf Sonnet 5, **bis** die Messung da ist —
    mit derselben Variable, aber jetzt gesetzt. Gegenargument, schon einmal gemessen: Ein fester Name, den
    es irgendwann nicht mehr gibt, fällt **still** auf ein anderes Modell zurück
    (`radar-0829-model-404-fallback`). Für Sonnet 5 ist dieses Risiko vorerst klein, weil es laut
    Deprecations-Seite „Active, not sooner than June 30, 2027" ist.
  - **(c) Eine Zeile Klarstellung in einer neuen DEC:** Welche der beiden Regeln gilt für Claude-Namen,
    und ergänzt `DEC-0124` seine Ablöseliste entsprechend? Ohne diese Zeile widersprechen sich zwei
    gültige Entscheidungen. Das Hausprinzip „Soll-Fragen zuerst gegen `decisions/active/`" liefert dann
    zwei verschiedene Antworten.
- **Empfehlung:** **adopt — als Entscheidungsfrage an den Nutzer** (a / b, dazu in jedem Fall c). Aufwand
  der Entscheidung: gering. Die Umsetzung von (b): eine `env`-Zeile je Kit-`settings.json` unter einem
  Item plus Test, etwa 1 h. · **Status**: NEW

## 2. Was der Messlauf vergleichen müsste (Vorschlag; kein Tausch ohne ihn)

Plan V2.5 §4 nennt die Maßstäbe: *„Lösungsquote, Tokens, Kosten je gelöster Aufgabe"* gegen das
bisherige Modell, auf festen Beispielaufgaben dieses Repos. Konkret, und mit dem, was die
Herstellerseiten heute dazu sagen:

- **Varianten (Arme)** — wegen der neu kalibrierten Denktiefe (Punkt 3) reicht „alt gegen neu auf
  derselben Stufe" nicht:
  1. Sonnet 5 @ `high` — der bisherige Stand der Bau-Sprosse (dev/research), bzw. @ `medium` für das
     Office-Kit
  2. Sonnet 5.5 @ `medium` — Herstellerempfehlung für *„agentic coding … well-specified tasks"*
  3. Sonnet 5.5 @ `high` — dieselbe Stufe wie bisher, die aber jetzt ein anderes Maß an Denken bedeutet
  4. **Opus 5.5 @ `low`** — die Grenze zwischen Kilo und Mega. Hersteller: *„on several coding
     evaluations `low` comes close to [Opus 5 high] at much lower cost"*
     (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5).
     Die Recherche 0c im Plan fand ebenfalls: „Opus low kann Sonnet high schlagen".
- **Feste Aufgaben:** Nur die Art Auftrag, die auf Kilo überhaupt laufen darf — also Aufträge mit einer
  **testförmigen Abnahme** (`dispatch.acceptance_is_test_shaped`, `DEC-0112`). Vorschlag: 6–10
  archivierte `TSK` dieses Repos, deren roter/grüner Test es noch gibt. Jede wird vom Eltern-Commit aus in
  einem Klon unter `C:\Offline Repos\v2-testbed\_round-scratch\<TSK-ID>\` nachgespielt. Für das
  Office-Kit dazu 3–4 Beispielaufgaben aus dem Office-Piloten (`tools/light_kit_pilot.py`), weil dort
  Sonnet der Standard ist.
- **Messgrößen je Lauf:**
  - gelöst — Abnahmetest grün **und** Prüfer-PASS
  - Prüfrunden bis PASS — die (g)-Tabelle aus `DEC-0057` misst das schon
  - Eingabe-Tokens und Züge — `tools/measure_agent_tokens.py` liest genau das aus den Transkripten
  - Ausgabe-Tokens, Kosten je **gelöster** Aufgabe zum Listenpreis, Laufzeit
  - **dazu drei Größen, die die Sonnet-5.5-Doku als Verhaltensänderung nennt** (Punkt 4): Dateien
    außerhalb von `expected_outputs`, „fertig gemeldet ohne Testlauf", „angehalten und zurückgefragt"
- **Wiederholungen:** mindestens 2–3 je Arm und Aufgabe. Ein Community-Messlauf mit dem gleichen Ziel
  sah zwischen `medium` und `high` Kostenschwankungen von −33 % bis +26 %
  (https://github.com/j4th/context-builder-kit/issues/69, 2026-09-26; ein Hinweis, kein Beleg).
- **Modell festhalten, nicht den Namen:** Die Arme brauchen **volle Modell-IDs** (`claude-sonnet-5`,
  `claude-sonnet-5-5`), weil der Name `sonnet` sich gerade bewegt. Und das Ergebnis muss die
  **tatsächlich gelaufene ID** aus dem Transkript tragen (`message.model`), nicht den Namen aus
  `*.meta.json`. Dass beides auseinanderfällt, ist in diesem Lauf gemessen: Die `meta.json` sagt `opus`
  oder gar nichts, das Transkript sagt `claude-opus-5-5` (Punkt 6).
- **Entscheidungsregel** (Plan V2.5): *„das günstigste Modell, das die Stufe im Praxistest löst"*.
- **Empfehlung:** **adopt** als Item unter Strom C („Watcher-Pflichtfrage + Messlauf"). Aufwand: die
  Vorbereitung (Aufgabenliste, Nachspiel-Skript, Auswertung über `measure_agent_tokens.py`) etwa 4–6 h;
  die Läufe selbst kosten Tokens und Stunden, die der Nutzer freigeben muss. · **Status**: NEW

## 3. Denktiefe je Aufgabe und Rolle — was Anthropic offiziell dazu sagt (für die Effort-Recherche des Nutzers und für Strom C)

Der Nutzer hat heute eine Recherche angestoßen: *„PM/Architekt/Designer eher xhigh, Worker eher Medium"*
(`project_memory/staging/generation-6/capture_fr_effort_by_role.py`, Quelle dort ein KI-erzeugtes Video).
Hier stehen die **offiziellen** Aussagen dazu, jeweils wörtlich und mit Quelle (gesehen 2026-09-28):

- **Die Stufen, allgemein** (https://platform.claude.com/docs/en/build-with-claude/effort):
  - `low`: *„Simpler tasks that need the best speed and lowest costs, such as subagents"*
  - `medium`: *„Agentic tasks that require a balance of speed, cost, and performance"*
  - `high`: *„Complex reasoning, difficult coding problems, agentic tasks"*
  - `xhigh`: *„Long-running agentic and coding tasks (over 30 minutes) with token budgets in the millions"*
  - `max`: *„Tasks requiring the deepest possible reasoning"*
  - Dazu die Regel: *„The per-model recommendations that follow override this table where they differ."*
- **Opus 5.5** (die Mega-Sprosse; Planer, Prüfer, Bauer-Standard in dev/research):
  - *„Start at `medium`, the default … Effort level names don't correspond to the same amount of thinking
    across models: … Claude Opus 5.5 at `medium` matches or exceeds Claude Opus 5 at `high` on coding and
    knowledge-work evaluations"*
  - *„At a given level, Claude Opus 5.5 tends to think more per turn than Claude Opus 5, especially at
    `xhigh` and `max`. If you keep the `effort` value you set for Claude Opus 5, expect longer turns and
    more output tokens."*
  - *„Reserve `xhigh` and `max` for work where you've measured a quality gain."*
  - **Was das für uns heißt:** Die Leitern von dev und research fahren jede Klasse auf `high` und große
    Ziele auf `xhigh`. Auf Opus 5.5 ist das **eine Stufe über der Herstellerempfehlung**, und es kostet
    mehr als dieselbe Einstellung vor dem 22. September.
- **Sonnet 5.5** (die Kilo-Sprosse):
  - *„Its levels are recalibrated … Run a fresh effort sweep … For agentic coding and multistep tool use,
    start with `medium` for well-specified tasks and move to `high` for harder or longer ones … Use
    `xhigh` or `max` only where your evals show a quality gain."*
  - **Warnungen, die für Bauer-Unteragenten zählen:**
    - *„At `low`, it keeps its thinking short and can skip verifying a change."*
    - *„At `low` and `medium`, on long agentic tasks, it's more likely to stop and check in with the user
      before it finishes."* Ein Unteragent hat niemanden, den er fragen kann; er liefert dann halb.
    - Quelle: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5
- **Abgleich mit der Hypothese des Nutzers:**
  - **„Worker auf medium"** deckt der Hersteller **nur für genau beschriebene Aufgaben**. Das ist genau
    unsere Regel „Kilo nur mit Test-Abnahme" (`DEC-0097`/`DEC-0112`).
  - **„Planer auf xhigh"** deckt er **nur mit gemessenem Nutzen**. Das entspricht der Leitplanke aus
    Plan V2.5: *„,sehr hoch' nur für benannte Architektur-Schritte"*.
  - Für den **Prüfer** nennt keine offizielle Seite eine Stufe. Der einzige Hinweis ist Anthropics
    Aussage zu Opus 5.5: *„stronger code review, with more bugs caught … and fewer false alarms"*.
  - Die Video-Zahlen (Fable 5.1 low gegen max) sind in keiner offiziellen Quelle zu finden. Nach der
    Hausregel sind sie ein Hinweis, kein Beleg.
- **Empfehlung:** **adopt** — diese Zitate gehören in die geplante Datei „Welches Modell und welche
  Denktiefe wofür" (Plan V2.5 §4, Strom C), mit Quelle und Lesedatum. Die Einstellungen `effort.default`
  und `large` der Leitern werden **im Messlauf aus Punkt 2 mitgemessen** und nicht auf dieses Zitat hin
  geändert. Aufwand: etwa 1 h für die Datei. · **Status**: NEW

## 4. Vier Verhaltensänderungen von Sonnet 5.5, die bei uns Prüfrunden kosten würden — plus fertige Gegenmittel vom Hersteller

Quelle für alle vier: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5
(gesehen 2026-09-28).

1. **Ungefragte Zusätze:** *„The model tends to add tests, documentation, and small supporting files …
   even when you don't ask for them. It does this at every effort level, and more at higher effort."*
   **Bei uns** meldet der Prüfer jede Abweichung eines Pakets von den `expected_outputs` seines Items als
   Befund (Arbeitsregel im `CLAUDE.md` dieses Repos). In den Kits nennt die QA-Rolle `expected_outputs`
   nicht (Grep über `team-kits/dev-team`: nur PM- und research-engineer-Skill) — dort ist offen, ob
   solche Zusätze überhaupt auffallen. Hier jedenfalls wird jede ungefragte Datei eine Prüfrunde — genau die Kennzahl, die Plan V2.5 §5 von ~3 auf ≤ 2 drücken will.
   Gegenmittel, vom Hersteller wörtlich vorgegeben: *„When the work the user asked for is done and
   checked, stop and report. Don't add features, tests, files, docs or refactors that weren't asked
   for. If you think one would help, mention it at the end instead of doing it."*
2. **Prüfung übersprungen bei `low`:** Gegenmittel ist der Absatz „When you change code that can be
   run, built, or type-checked, run a real check …". Er gehört zu jedem Bauer-Auftrag auf `low`. Heute
   sind das im Office-Kit Records-Clerk und Filing-Reviewer.
3. **Vorzeitiges Zurückfragen bei `low`/`medium`:** Gegenmittel ist *„Keep working until everything
   the user asked for is done …"*. Für Unteragenten passt das, weil ohnehin niemand antwortet.
4. **Eigene Prüf-Unteragenten bei `xhigh`/`max`:** *„it can start its own rounds of review and
   verification, sometimes with subagents"*. Der Stopp-Absatz des Herstellers *„cut session cost by
   about a third, with no change in quality"*. **Bei uns** ist jeder Spawn ohne offenes Item ohnehin
   verweigert (`gate_spawn_needs_item.py` hier, `gate_dispatch.py` in den Kits). Die Rechnung dafür
   bleibt aber: Ein verweigerter Spawn ist ein verschwendeter Zug plus eine Fehlblockade.

Dazu eine Aussage zu Opus 5.5, die direkt auf Strom C passt (**Lebenszeichen statt Warten**, parallele
Bauer): *„give the model a time budget: have your harness add a short line … giving the elapsed time
against that budget … `elapsed 340s / 1200s` … In Anthropic's evaluations of small agent teams … both
signals made teams finish sooner"*
(https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5,
Abschnitt „Time signals for multiagent harnesses"). Die Herzschlag-Datei, die Strom C ohnehin baut, ist die
natürliche Quelle für diese Zeile.

- **Empfehlung:** **adopt, klein** — Absatz 1 in den Auftragskopf jedes Bauer-Auftrags auf der
  `sonnet`-Sprosse, die Absätze 2 und 3 nur für `low`/`medium`. Das ist Textarbeit in der Rollenvorlage
  bzw. im Dispatch-Kopf und fällt in Strom C bzw. E (Textdiät, also knapp halten). Die Zeitbudget-Zeile
  kommt als Beobachtungspunkt zu Strom C. **Ob die Absätze wirken, misst der Messlauf aus Punkt 2 mit**
  (Arm mit und ohne Absatz). Aufwand: etwa 1–2 h. · **Status**: NEW

## 5. Auto-Modus ist seit 2.1.283 der Startmodus jeder Terminal-Sitzung — auch in Kit-Projekten, weil die Kits keinen Startmodus setzen

- **Quelle** (gesehen 2026-09-28): https://code.claude.com/docs/en/permission-modes, wörtlich: *„With
  Claude Code v2.1.283 or later, auto mode is the built-in starting permission mode for interactive
  terminal and VS Code sessions."* Changelog 2.1.284: *„Changed interactive terminal/VS Code sessions to
  start in auto mode when no permission mode configured."* In einer Projekt-`settings.json` wird
  `defaultMode: "auto"` ignoriert; `"default"` (Manuell) dagegen wirkt dort. *„Deny rules block in every
  mode."*
- **Gemessen im Baum:** `team-kits/dev-team/settings/settings.json` setzt `agent`, `model`,
  `permissions.allow/deny`, aber **kein** `defaultMode` (unverändert seit `radar-0706-permission-mode-rename`).
  Jede Kit-Sitzung auf 2.1.283 oder neuer startet also im Auto-Modus. Dann entscheidet ein zweites
  Modell, der Klassifizierer, statt einer Rückfrage.
- **Was das heißt:**
  - **Gut für Plan V2.5:** weniger Rückfragen, passend zum §5-Ziel „Klicks je Ziel ~26 → 3–5".
  - **Unverändert:** Die Garantien G1–G6 hängen an unseren `PreToolUse`-Hooks, und die laufen in jedem
    Modus.
  - **Aber:** Der Klassifizierer erlaubt laut Doku *„Pushing to any branch of the repository you're
    working in, including the default branch"*. G4 („kein Push ohne Nutzer") hält dann **allein** das
    Push-Gate der Kits. Bisher gab es keine zweite Schutzschicht: `Bash(git *)` stand schon in `allow`.
  - **Für Strom B:** Punkt (5) will `permissions.deny` „in einer Pilotkopie messen (Windows, bypass,
    Codex)". **Auto gehört jetzt in diese Messreihe**, weil es der Normalfall ist.
  - Ein Werkzeug, das bisher niemand nutzt: Ein `PostToolUse`-Hook kann dem Klassifizierer über
    `classifierContext` Kontext mitgeben (ab v2.1.236, gleiche Doku-Seite).
- **Empfehlung:** **adopt, klein** — (i) „auto" in die Messreihe von Strom B (5) aufnehmen; (ii) eine
  Nutzerfrage: Sollen Kit-Projekte bewusst im Auto-Modus starten (dann in `AGENTS.md` sagen, dass G4 nur
  am Gate hängt), oder mit `defaultMode: "default"` manuell? Aufwand: etwa 30 min plus die Messung, die
  Strom B ohnehin fährt. · **Status**: NEW

## 6. Drei Claude-Code-Versionen auf einem Rechner: derselbe Sprossenname kann drei verschiedene Modelle bedeuten

- **Gemessen am 2026-09-28 auf diesem Rechner:**
  - `claude --version` im Suchpfad (`/c/Users/zenti/.local/bin/claude`) → **2.1.258**
  - Die Desktop-App bringt eigene Versionen mit: `AppData/Roaming/Claude/claude-code/` enthält **2.1.270**
    und **2.1.281**.
  - Die Transkripte der letzten 15 Unteragenten-Läufe und der Hauptsitzung zeigen `message.model =
    claude-opus-5-5`. In ihrer `*.meta.json` steht als Modell `opus` oder gar nichts.
- **Abgeleitet, nicht gemessen:** Die Changelogs führen neue Modelle **mit der Version** ein — Opus 5.5
  mit 2.1.280 („now the default Opus model"), Sonnet 5.5 mit 2.1.284. Welches Modell hinter einem Namen
  steht, hängt dann an der **Version, die die Sitzung fährt**. Folgen:
  - Auf diesem Rechner läuft `sonnet` noch als **Sonnet 5**, bis die Desktop-App auf 2.1.284 oder neuer
    aktualisiert.
  - **`tools/radar_routine.py --run`** startet `["claude", "-p", …]` (Zeile 806), also die Version
    2.1.258 im Suchpfad. Nach dieser Ableitung liefe dort `opus` noch als **Opus 5**.
  - Das gilt genauso für synaipse und jedes andere Kit-Projekt: Welches Modell eine Sprosse bedeutet,
    hängt am Aktualisierungsstand des jeweiligen Rechners.
- **Warum das zählt:** `DEC-0114` (2) geht davon aus, dass der Name „dem aktuellen Modell" folgt.
  Tatsächlich folgt er **der installierten Version**. Für den Messlauf (Punkt 2) und für die geplante
  Datei „welches Modell wofür" heißt das: **Die tatsächlich gelaufene ID wird aus dem Transkript
  gelesen, nie aus dem Namen.** `tools/measure_agent_tokens.py` liest bisher `model` aus der `meta.json`,
  also den Namen.
- **Empfehlung:** **adopt, klein** — (i) `measure_agent_tokens.py` gibt zusätzlich die Menge der
  `message.model`-IDs je Agent aus. Ungefähr 30 min plus ein Test, der ohne die Änderung rot ist. (ii)
  Einmal nachmessen, welches Modell ein `--run` mit 2.1.258 tatsächlich bekommt: ein kurzer Lauf, ID aus
  dem Transkript lesen. · **Status**: NEW

## Vorschlag für die Stufentabelle (`team-kits/model_tiers.yaml`) — nur ein Datum, kein Tausch

- **Alt:** `suited_for.claude.sonnet: model: Claude Sonnet 5 … read: 2026-09-25`
- **Neu:** `model: Claude Sonnet 5.5` (auf der Anthropic API, ab Claude Code 2.1.284). `says:` bleibt
  wörtlich gleich (*„The best combination of speed and intelligence"*, Modellübersicht,
  https://platform.claude.com/docs/en/about-claude/models/overview), dazu `read: 2026-09-28`.
- **Zusatzvorschlag, wegen `DEC-0124`:** ein Feld je Sprosse wie `measured: none` bzw. mit Verweis auf
  den Messlauf. Dann zeigt die Tabelle, dass die Zeile **eine Beobachtung, keine geprüfte Eignung** ist.
- Die Zeilen `opus` und `fable` sind unverändert: Opus 5.5 und Fable 5.1, gleiche Herstellerworte,
  Stand 2026-09-28.
- Ob überhaupt etwas geändert wird, entscheidet der Nutzer. Der Watcher schreibt die Tabelle nie selbst.

---

# Teil 2 — Was hat sich insgesamt getan? (mit einem zweiten Blick)

## Modelle

| Modell | ID | $/MTok ein/aus | Cache-Lesen | Standard-Denktiefe API / Claude Code | Status |
|---|---|---|---|---|---|
| Fable 5.1 | `claude-fable-5-1` | 10 / 50 | 2,5 % | `high` / — | Active, ≥ 2027-09-01 |
| Opus 5.5 | `claude-opus-5-5` | 4 / 20 | 5 % | `medium` / `medium` | Active, ≥ 2027-09-22 |
| **Sonnet 5.5 (NEU, 2026-09-28)** | `claude-sonnet-5-5` | 2 / 10 | 10 % ($0,20) | `high` / **`medium`** | Active, ≥ 2027-09-28 |
| Sonnet 5 (jetzt „Legacy", weiter verfügbar) | `claude-sonnet-5` | 2 / 10 | 10 % | `high` / `high` | Active, ≥ 2027-06-30 |
| Haiku 4.5 (keine Sprosse, `DEC-0076`) | `claude-haiku-4-5-20251001` | 1 / 5 | 10 % | nicht unterstützt | Active, **≥ 2026-10-15** |

Quellen: Modellübersicht, https://platform.claude.com/docs/en/about-claude/models/overview; Deprecations,
https://platform.claude.com/docs/en/about-claude/model-deprecations; model-config (Claude-Code-Spalte).
Alles gesehen 2026-09-28.

- **Neues Spitzenmodell?** Nein. Fable 5.1 bleibt oben. Opus 5.5 (22. 09.) wurde schon am 09-25 gemeldet.
  Mythos 5.1 ist weiter nur auf Einladung (Project Glasswing).
- **Preise:** Sonnet 5.5 kostet je Token **gleich viel** wie Sonnet 5. Laut Anthropic ist es *„30%+
  faster"* und braucht *„fewer tokens per task"* (bis zu 30 % günstiger je Aufgabe). Das ist
  Herstellerangabe. Keine anderen Preisänderungen.
- **Neue Abschaltungen:** keine. Neu in Sichtweite sind aber:
  - **Haiku 4.5 „not sooner than 2026-10-15"** — für die Leiter egal (keine Haiku-Sprosse), wichtig nur,
    falls irgendwo `haiku` fest steht.
  - **Sonnet 4.5 „not sooner than 2026-09-29"** (morgen). Das zählt, weil der Name `sonnet` auf **Bedrock
    und Google Cloud laut model-config auf Sonnet 4.5** zeigt (dort bestimmen die Anbieter ihre eigenen
    Termine). Ein Kit-Projekt über diese Anbieter hätte eine ganz andere Kilo-Sprosse.
- **Angekündigt, nicht erschienen:** *„Claude Haiku 5.5, built for high-volume and cost-sensitive
  applications, will join the Claude 5.5 family in the coming weeks."* —
  https://www.anthropic.com/claude-sonnet-5-5. **Zweiter Blick:** Nach `DEC-0076` und Plan V2.5 (*„Haiku:
  nie zum Coden, nicht in der Leiter"*) gibt es keinen Platz dafür. Einziger denkbarer Nutzen wäre die
  Lese-Klasse des Office-Kits (Records-Clerk, Filing-Reviewer: Ablage lesen, nicht schreiben), und die
  kommt nur mit einem Messlauf in Frage. **Watch** bis zur Veröffentlichung.
- **Stichtage:** Alle drei alten Claude-Stichtage (07-19, 08-05, 08-31) sind erledigt. Neu zu
  beobachten sind nur Haiku 4.5 am 10-15 (nicht leiterrelevant) und die Veröffentlichung von Haiku 5.5.

## Sonnet 5.5 — technische Brüche, geprüft gegen unsere Kits

Quelle: https://platform.claude.com/docs/en/models/sonnet-5-5/whats-new-sonnet-5-5 (gesehen 2026-09-28).

Es gibt fünf API-Brüche:
- `thinking: disabled` gibt Fehler 400; stattdessen `between_tools`.
- Erzwungener Werkzeugaufruf (`tool_choice: any/tool`) gibt Fehler 400.
- Denkblöcke sind an Modell **und** Gespräch gebunden.
- Das alte Computer-Use-Werkzeug `computer_20251124` wird nicht mehr angenommen.
- Beim Advisor-Werkzeug sind bestimmte Paarungen nicht mehr erlaubt.

**Keiner davon trifft die Kits.** Sie rufen die API nicht selbst auf, sondern laufen in Claude Code, und
`kernel/sdk_approval.py` enthält weder `thinking` noch `tool_choice` (Grep, 0 Treffer). Das ist
eine Stichprobe, kein Test. **Zweiter Blick:** Ein Modellwechsel **mitten in einem Gespräch** verliert jetzt das bisherige
Denken (*„one that moves from Claude Sonnet 5.5 to any other model runs the turns after the switch
without it"*). Unsere Eskalation wechselt das Modell aber durch einen **neuen** Unteragenten und nicht in
einem laufenden Gespräch. Also gibt es hier keinen Verlust. Ein `/model`-Wechsel in einer
PM-Sitzung hätte ihn allerdings.

## Zweiter Blick — Dinge, die nicht sofort passen

- **Sonnet 5.5 schreibt Werkzeugnamen manchmal in anderer Groß-/Kleinschreibung** (*„occasionally calls
  a declared tool by a name that differs only in letter case, such as `bash` for `Bash`"*, Prompting-Leitfaden
  Sonnet 5.5). **Warum uns das angeht:** Alle Shell-Gates hängen an Matchern wie `Bash|PowerShell`, und die
  unterscheiden Groß- und Kleinschreibung. Wahrscheinlich weist Claude Code einen unbekannten Namen
  einfach ab; dann ist das harmlos. Käme aber ein `bash`-Aufruf ausgeführt **und** mit `tool_name: "bash"`
  bei den Hooks an, liefen alle Shell-Gates nicht. Das wäre eine Lücke mit einer Angriffskette innerhalb
  einer Sitzung, also nach Hausregel blockierend. **Empfehlung: einmal messen** (etwa 30 min, Klon,
  Sonnet 5.5): Was steht im Hook-Payload, und wird der Aufruf ausgeführt? · NEW
- **`/doctor prompt-audit`** (2.1.283): *„audit CLAUDE.md/skills/agents/commands for older model
  patterns"*, seit 2.1.283 mit *„stale paths/commands/contradicting files lead report"*. **Zweiter
  Blick:** Das ist ein fertiges Werkzeug für Strom E (Textdiät). Es prüft genau die Verfassung, die
  Rollendateien und die Skills, und es sucht nach **widersprüchlichen** Dateien — dem Fehler, gegen den
  `SR-0008` gebaut ist. Außerdem könnte es Anweisungen finden, die das Modell auffordern, sein Denken in
  die Antwort zu schreiben. Die lehnen Sonnet 5.5 und Opus 5.5 inzwischen mit der Kategorie
  `reasoning_extraction` ab (beide Prompting-Leitfäden). **Watch → einmal in einem Klon eines
  Kit-Projekts laufen lassen**, bevor Strom E kürzt. Etwa 30 min. · NEW
- **Claude Design im Terminal: `/design`** (Forschungsvorschau seit 2.1.234, 17. 08.; hier nie gemeldet):
  *„brings Claude Design's artboard workflow into the CLI … Claude publishes a canvas of editable
  artboards for your UI. Pick one, tweak it, then have Claude implement it."* —
  https://code.claude.com/docs/en/whats-new/2026-w34. **Zweiter Blick:** Das passt auf den
  **Designer-Ablauf** des dev-Kits (`product-designer`, Frontend-Prüfung FR-0094/Strom D) und auf die
  „Verständnis-Karte" aus Plan V2.5 §1. Der Nutzer wählt eine Zeichenfläche aus, statt einen Text zu
  lesen. **Grenzen:** Die Flächen werden als Artefakt auf claude.ai veröffentlicht (nur Pro/Max/Team/
  Enterprise). Für Projekte mit „nur lokal"-Vorgabe scheidet das aus. Außerdem ist es eine Vorschau.
  **Watch.** · NEW
- **Eigene Rückfragen-Stopps von Opus 5.5 in unbeaufsichtigten Läufen.** Der Prompting-Leitfaden beschreibt
  vier Arten, wie Opus 5.5 einen Zug beendet, obwohl noch Arbeit offen ist — z. B. mit einer
  Zusammenfassung, die den nächsten Schritt nur ankündigt — und liefert einen Absatz dagegen.
  **Zweiter Blick:** Das ist die Beschwerde aus Plan V2.5 („der PM baut in winzigen seriellen Häppchen").
  **Aber** der Hersteller rät: *„leave the addition out of human-in-the-loop applications"* — und der PM
  ist genau das. Für **Bauer-Unteragenten**, die unbeaufsichtigt laufen, passt der Absatz dagegen.
  **Watch**, zusammen mit Teil 1 Punkt 4.
- **Neue Verwaltungseinstellungen `deniedModels` und `availableModelsMatch: "exact"`** (2.1.283): Damit
  ließe sich ein Modell sperren oder genau festhalten, **bis es gemessen ist**. Das wäre die saubere
  technische Form von Weg (b) aus Punkt 1. Sie wirken allerdings **nur in verwalteten Einstellungen**
  (Organisation), nicht in einer Kit-`settings.json`. **Ignore** für die Kits; als Hinweis notiert.
- **Sonnet 5.5 hält Text, der nach Werkzeug-Ergebnissen eingeschoben wird, manchmal für eine
  Einschleusung.** Gemeint ist Text vom Harness, der *„after the tool results on every step"* kommt.
  **Im Baum geprüft:** Die Kits geben nach einem Werkzeug nur nach `Agent|Task` (`gate_dispatch.py`) und
  nach `AskUserQuestion` (`gate_approval.py`) Text an das Modell weiter. Beides trifft den PM, nicht einen
  Sonnet-Bauer. `guard_yaml_valid`/`guard_scratchpad_ref` melden sich nur bei einem Fehler. **Geringes
  Risiko, ignore.**
- **Windows-Schutz:** 2.1.283 hat eine Lücke geschlossen, durch die das PowerShell-Werkzeug über `cmd /c
  rd/rmdir/del/erase` Laufwerkswurzeln, das Heimatverzeichnis oder Ordner löschen konnte. Das ist dieselbe
  Familie wie G6 und die Befehlszeilen-Vektoren, die am 09-12/09-25 gemeldet wurden. **Zeiger:** zu der
  dort vorgeschlagenen Liste von Testvektoren hinzufügen, keine neue Liste.
- **Community — ein Messmuster, das wir übernehmen könnten.** Ein anderes Harness-Projekt hat Opus 5.5 am
  2026-09-26 nachkalibriert und dabei gemessen:
  - „Unteragent-getriebene Umsetzung" gegen „inline" auf einem nachgespielten echten Issue: *„10% more"*
    Kosten, *„nearly twice as long"*, keine messbare Qualitätsverbesserung, deshalb nicht übernommen.
  - Aufbau: mehrere Arme, Wiederholungen, mehrere Bewerter.
  - Quelle: https://github.com/j4th/context-builder-kit/issues/69
  - **Nach Hausregel ist das ein Hinweis, kein Beleg.** Doppelt nützlich ist es trotzdem: (1) Der Aufbau
    ist eine Vorlage für den Messlauf aus Punkt 2. (2) Es ist ein Gegenhinweis zu Plan V2.5 „parallele
    Bauer als Standard": Bei **einem** zusammenhängenden Arbeitspaket kosteten zusätzliche Unteragenten
    dort nur Geld und Zeit. Die Regel „nur wenn `check-scopes` disjunkt misst" sollte das auffangen. Die
    Zahlen aus Strom C (§5) sollten es trotzdem zeigen.
- **Ohne Relevanz hier** (gesehen 2026-09-28): Ultracode ist ein eigener Schalter in `/effort`.
  Nebenbei widersprechen sich Doku und Changelog: model-config sagt noch *„sends `xhigh` effort"*,
  2.1.284 sagt *„no longer forces xhigh"*. Als `effort`-Wert in einer Rollendatei gilt Ultracode
  ohnehin nicht. Außerdem: Spend-Anzeige, Gateway-Features, Vim-Fixes, Tastenbelegungen, Claude Tag,
  der Fix für die Explore-Unteragenten-Modellwahl, der Fix, dass dynamische Workflows bei einem
  Modell-Fallback alle Agenten auf dem Ersatzmodell starteten, der Fix für
  `.claude/rules`-Symlinks, der Block-Fix für Elicitation-Hooks.

## Quellformat (Pflichtaufgabe) — Vertrag unverändert

- **Frontmatter der Rollen:** keine neuen oder entfernten Felder in 2.1.283–284
  (https://code.claude.com/docs/en/sub-agents, gesehen 2026-09-28). `effort` nimmt weiter
  `low|medium|high|xhigh|max`; `ultracode` und `auto` sind dort ausdrücklich **keine** gültigen Werte.
  `model` nimmt weiter `sonnet|opus|haiku|fable|inherit` und volle IDs. **Keine Änderung am Generator.**
- **Neu dokumentiert und für die Leiter wichtig:** Bei Familiennamen gilt: *„If the main conversation's
  model belongs to that family, the subagent runs on the main conversation's exact model"*. Und ein
  **Modell-Parameter beim einzelnen Aufruf** hat Vorrang vor der Frontmatter. Beides ist nicht neu, aber
  es erklärt, warum eine Rolle mit `model: opus` unter einem Opus-5.5-PM immer Opus 5.5 bekommt. Das ist
  für den Messlauf wichtig: Die Arme müssen die volle ID **beim Aufruf** setzen.
- **Hook-Schema:** keine Änderung in 2.1.283–284, abgesehen vom Block-Fix für Elicitation-Hooks. Für die
  Groß-/Kleinschreibung der Werkzeugnamen siehe den zweiten Blick oben (Messung offen).
- **Einstellungen:** `permissions.defaultMode` gilt weiter aus der Projekt-Datei, außer den Werten
  `auto` und `bypassPermissions` (Punkt 5). **`@import` und `AGENTS.md`:** keine Änderung seit dem 09-25.
- **Wortschatz der Denktiefe:** unverändert. Was sich geändert hat, ist die **Kalibrierung**: Dieselbe
  Stufe bedeutet je Modell ein anderes Maß an Denken (Punkt 3). `effort_field: effort` in
  `model_tiers.yaml` bleibt richtig.

## Offene frühere Punkte (nur Verweise, nichts neu gemeldet)

- Vom 2026-09-25, weder in `decided.md` noch in einer DEC gefunden: Punkt 3 (`AGENTS.md` nativ; der
  Shim hält jetzt nur noch wegen des Markers), 4 (`.claude/rules/`), 5 (`CwdChanged` gegen H20),
  7 (Satz zu `AGENTS.override.md` im Scaffold). **Neu dazu:** Die Mindestversion von Claude Code, die
  am 09-25 bei **≥ 2.1.282** lag, sollte für die Kits jetzt **≥ 2.1.284** lauten, wenn die Sonnet-Sprosse
  Sonnet 5.5 sein soll. Umgekehrt: **höchstens 2.1.283**, solange Weg (b) aus Punkt 1 ohne `env`-Pin
  gelten soll. Diese Version entscheidet jetzt über das Modell, nicht nur über Funktionen.
- Vom 2026-09-12/09-04: die Testvektoren der Befehlszeilen-Familie (heute ergänzt um den
  Windows-`cmd /c rd`-Fix), `PreModelSwitch`/`PostModelSwitch`, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`,
  `maxEffortLevel` + `modelSettings`. **Neu zu `maxEffortLevel`:** In Verbindung mit Punkt 3 wäre das
  eine Obergrenze pro Modell, wie sie Plan V2.5 („sehr hoch nur für benannte Architektur-Schritte") als
  Regel wünscht. Laut model-config ist sie in Einstellungen setzbar; wo genau sie wirkt, ist hier nicht
  nachgemessen.
