# Radar — 2026-09-28 (codex-watcher, ausgeführt von claude) — Sonderlauf „Es gibt neue Modelle"

Suchfenster: **2026-09-25 → 2026-09-28**, also alles seit dem letzten Bericht dieses Wächters
(`radar/2026-09-25-codex-by-claude.md`). Codex CLI **0.157.0 → 0.158.0**, die offiziellen Seiten
zu Modellen, Preisen, Abkündigungen, Denktiefe (reasoning effort), Hooks, Unteragenten und
Konfiguration, dazu der Quelltext von `openai/codex` (dort, wo die Doku etwas behauptet, das unser
Generator bisher für unmöglich hielt).

Vorab gelesen: `radar/decided.md` (Stand: Triage vom 2026-09-05; die Punkte des Berichts vom
25.09. stehen dort noch nicht, Punkt 1 davon ist aber schon umgesetzt — DEC-0114, Commit
`0a79fc5`, `model_tiers.yaml` zeigt jetzt `gpt-6-astra / gpt-6-sol / gpt-6-luna`) und
`radar/2026-09-25-codex-by-claude.md`. Kein Punkt unten wiederholt einen entschiedenen oder
schon gemeldeten Punkt; wo ein alter Punkt berührt wird, steht ein Zeiger. Einen Bericht der
Claude-Hälfte von heute gibt es noch nicht; `radar/2026-09-25-claude-by-claude.md` wurde
überflogen. Der Modell-Vergleich über beide Anbieter hinweg steht darum **hier**, in Teil 1 Punkt 2,
mit einem Zeiger für die Claude-Hälfte.

**Die Grenze vorneweg, unverändert:** Auf diesem Rechner gibt es keine Codex CLI. Nichts unten ist
gegen eine laufende CLI gemessen. Jede Aussage ist ein Zitat einer offiziellen Seite, eine
Stelle im Codex-Quelltext (mit Pfad) oder eine Stelle in diesem Repo — und wo es eine Folgerung
ist, steht das dabei, zusammen mit der Messung, die sie bräuchte.

---

## In einfachen Worten

- **Neue OpenAI-Modelle seit dem letzten Bericht: keine.** Das „neue Modell" von heute ist
  **Claude Sonnet 5.5** (Anthropic, 28.09.). Auf der OpenAI-Seite gilt weiter die GPT-6-Familie
  vom 22.09., und die steht schon in unserer Modell-Tabelle.
- **Die wichtigste Nachricht ist keine Modell-Nachricht:** Codex kann den Start eines
  Unteragenten inzwischen durch eine Schutzregel prüfen, stoppen und sogar umschreiben — und
  zwar seit Mai. Unser Generator geht noch davon aus, dass das nicht geht, und lässt deshalb auf
  Codex genau die Schutzregeln weg, die das Starten von Unteragenten überwachen. Außerdem nimmt
  der Codex-Startbefehl Modell **und Denktiefe pro Start** an — das, was uns auf der Claude-Seite
  fehlt (H169).
- **Ein Modelltausch nach Ankündigung ist nach Plan V2.5 nicht erlaubt.** Der Bericht sagt darum
  nur, **was** eine Messung vergleichen müsste, und schlägt vor, die Codex-Umstellung vom 25.09.
  (die vor dieser Regel lag) nachträglich zu messen, solange die alten Modelle noch erreichbar sind.
- **OpenAI hat eine offizielle Tabelle „welche Denktiefe für welche Aufgabe"** — sie empfiehlt für
  Programmieren eher *niedrig* bis *mittel* und „sehr hoch" nur mit Messbeleg. Unsere Kits laufen
  standardmäßig auf *hoch*, große Ziele auf *sehr hoch*. Das ist Material für die geplante
  „Modell-wofür"-Datei, keine Änderung ohne Messung.

---

# Teil 1 — Was bringt es unserem Repo?

## 1. Codex kann den Start eines Unteragenten abfangen, blockieren und umschreiben — unser Generator hält das für unmöglich (HÖCHSTE PRIORITÄT, Auflösung der Dauerbeobachtung)

- **Quellen** (alle gesehen 2026-09-28):
  - https://learn.chatgpt.com/docs/hooks — wörtlich: *"PreToolUse can intercept Bash, file edits
    performed through apply_patch, MCP tool calls, and other local function tools."* Tabellenzeile:
    *"Other local function tools | PreToolUse: Yes | PostToolUse: Yes | Notes: Match the function
    tool name, such as update_plan. spawn_agent also matches Agent."* Zum Umschreiben: *"To rewrite
    a supported tool call without blocking, return `permissionDecision: "allow"` with
    `updatedInput`"* und *"For MCP and other local function tools, `updatedInput` is the
    replacement arguments object."* Und die Einschränkung: *"Some specialized tool paths can opt
    out of the default hook path. Treat tool hooks as a useful guardrail, not a complete
    enforcement boundary."*
  - Quelltext `openai/codex`, `codex-rs/core/src/tools/hook_names.rs` (gelesen 2026-09-28):
    `HookToolName::spawn_agent()` — *"The serialized name remains `spawn_agent`, while `Agent` is
    accepted as a matcher alias for compatibility with hook configurations that describe sub-agent
    creation using Claude Code-style names."*
  - Eingeführt mit PR https://github.com/openai/codex/pull/23757 *"Default function tools into tool
    hooks"*, **gemergt 2026-05-23** — *"build generic `PreToolUse` and `PostToolUse` payloads from
    the function tool name and arguments; apply `updatedInput` rewrites back into function-tool
    arguments"*.
  - `codex-rs/core/src/tools/handlers/multi_agents/spawn.rs`: die Argumente des Startbefehls sind
    `message`, `items`, `agent_type`, **`model`**, **`reasoning_effort`**, `fork_context`; die
    Tiefenbegrenzung wird dort weiter geprüft (*"Agent depth limit reached. Solve the task
    yourself."*).
  - `codex-rs/core/src/agent/child_config.rs` + `agent/role.rs`: zuerst werden `model` /
    `reasoning_effort` des Startbefehls angewandt, **danach die Rollendatei darüber**; ist dort
    beides gesetzt, sagt Codex dem Modell *"This role's model is set to `{model}` and its reasoning
    effort is set to `{reasoning_effort}`. These settings cannot be changed."* Bestätigt durch das
    geschlossene Ticket https://github.com/openai/codex/issues/33268 (*"spawn_agent model and
    reasoning_effort overrides silently dropped when a non-empty agent role is applied"*).
- **Was es ist:** Auf Codex ist der Start eines Unteragenten ein ganz normales abfangbares Werkzeug.
  Eine `PreToolUse`-Regel mit dem Matcher `Agent` (oder `spawn_agent`) sieht den Auftragstext
  (`message`), die Rolle (`agent_type`), das gewünschte Modell und die gewünschte Denktiefe, kann
  den Start verweigern (Exit 2 oder `deny`) und kann die Argumente umschreiben (`updatedInput`).
- **Warum es HIER zählt — gegen den Baum gemessen, nicht angenommen:**
  - `team-kits/gen_provider_artifacts.py:83` erklärt `CODEX_UNSUPPORTED_TOOLS = frozenset(("Agent",
    "Task", "AskUserQuestion"))`, mit der Begründung in Zeile 60–63: *"Codex exposes SubagentStart,
    but it cannot stop a spawn and does not carry the Claude work-order payload"*. **Beide Hälften
    dieser Begründung sind für `PreToolUse` überholt** — sie beschreiben `SubagentStart`, nicht den
    Werkzeugaufruf. Folge: `codex_matchers` wirft jede Registrierung auf `Agent|Task` weg, also
    `gate_dispatch` (die Prüfung des Arbeitsauftrags, liest `prompt`/`subagent_type`/`model`/
    `description`, `gate_dispatch.py:458-473`) und die Spawn-Wächter. Auf Codex fehlen sie heute
    nicht, weil Codex sie nicht tragen könnte, sondern weil unsere Tabelle es sagt.
  - **H173** (`BUG-0255`, ACCEPTED_EXCEPTION: *"On Codex the spawn-side hold of the rung does not
    exist: the Agent tool is not hookable there"*) steht auf genau dieser überholten Prämisse. Die
    Ausnahme wurde vom Nutzer abgenommen — mit einer Begründung, die nicht mehr stimmt.
  - **H169** (`BUG-0251`, die Denktiefe-Achse wird abgeleitet, aber nie angewandt, weil das
    Claude-Werkzeug keinen Denktiefe-Parameter hat): auf Codex **gibt es** den Parameter. Und eine
    `PreToolUse`-Regel könnte die vom Kernel abgeleitete Denktiefe per `updatedInput` selbst
    einsetzen — Codex wäre damit der **erste Anbieter, auf dem die Denktiefe-Achse tatsächlich
    greift**.
  - **Der Haken, der Plan V2.5 Strom C direkt trifft:** Unser Generator schreibt in jede
    `.codex/agents/*.toml` immer `model =` **und** `model_reasoning_effort =`. Nach dem Quelltext
    oben gewinnt dann die Rollendatei, und ein Denktiefe-Wunsch beim Start ist wirkungslos. Für
    Codex gibt es damit zwei saubere Wege, und die Entscheidung gehört in Strom C:
    (a) wie auf Claude **Rollenvarianten** (Modellklasse × Denktiefe) erzeugen — einheitlich für
    beide Anbieter, aber auf Codex unnötig viele Dateien; oder
    (b) in der Codex-Rollendatei **nur das Modell** festschreiben, die Denktiefe weglassen, und sie
    beim Start setzen lassen — gehalten von einer `PreToolUse`-Regel, die sie aus der Lease des
    Kernels einsetzt oder einen abweichenden Wert verweigert.
  - `_compat.py` müsste die Nutzlast übersetzen: Werkzeugname `spawn_agent` → `Agent`,
    `agent_type` → `subagent_type`, `message` → `prompt`, `model` bleibt, `reasoning_effort` ist
    neu; ein Gegenstück zu `description` hat Codex **nicht** (`_TOOL_ALIASES`,
    `_compat.py:353`, kennt heute nur Shell- und Schreibwerkzeuge).
- **Grenzen, ehrlich benannt:**
  - Die Zuordnung `Agent` gilt nur für `spawn_agent` im Standard- oder V1-Namensraum
    (`codex-rs/core/src/tools/registry.rs:834-843`); ein Start über den **V2**-Multi-Agent-Weg
    heißt anders und trifft den Matcher `Agent` nicht. Welche Variante eine Kit-Sitzung benutzt,
    ist ungemessen.
  - OpenAI selbst nennt Hooks *"a useful guardrail, not a complete enforcement boundary"*. Eine
    Codex-Spawn-Regel wäre also eine echte Sperre für den Normalfall, keine Garantie.
  - Das offene Ticket https://github.com/openai/codex/issues/34370 (*"Subagents ignore requested
    medium reasoning effort and run at high"*, Desktop-App, seit 2026-07-20 offen) zeigt, dass
    „angefordert" und „tatsächlich gelaufen" auseinanderfallen können. Weg (b) braucht darum eine
    Messung, die die **tatsächliche** Denktiefe aus dem Protokoll des Kind-Laufs liest.
  - Unsere früheren Berichte haben die falsche Prämisse übernommen: der Bericht vom 25.09.
    (Punkt 2) schrieb, der Weg sei *"blocked by the matcher"* über `CODEX_UNSUPPORTED_TOOLS`. Das
    stimmte für unseren Generator, nicht für Codex. Offen bleibt, ab welcher **Release** der PR vom
    23.05. ausgeliefert war; die Doku beschreibt es heute als Normalzustand.
- **Messung, die es braucht** (eine Sitzung auf einem Rechner mit Codex CLI): Kit in einem
  Wegwerf-Repo installieren, von Hand eine `PreToolUse`-Registrierung mit Matcher `Agent` auf ein
  Skript setzen, das die Nutzlast protokolliert und mit Exit 2 verweigert; dann den PM einen
  Unteragenten starten lassen. Ablesen: (1) feuert die Regel, (2) welche Felder kommen an, (3) wird
  der Start wirklich verhindert, (4) mit `updatedInput` eine andere Denktiefe einsetzen und im
  Protokoll des Kind-Laufs die **tatsächliche** Denktiefe lesen — einmal mit, einmal ohne
  `model_reasoning_effort` in der Rollendatei.
- **Empfehlung:** **übernehmen — als Item unter dem offenen Ziel, gebündelt mit Strom C.**
  Sofort und klein (~30 min): die Begründung in `gen_provider_artifacts.py:60-63` als überholt
  markieren und H173/H169 um den Codex-Befund ergänzen, damit keine weitere Runde auf der alten
  Prämisse baut. Danach die Messung oben (~1–2 h mit Codex CLI). Erst dann `Agent`/`Task` aus
  `CODEX_UNSUPPORTED_TOOLS` in `CODEX_TOOL_MATCHER` verschieben, `_compat.py` erweitern und den
  Weg (a) oder (b) wählen (~½–1 Tag mit Tests). Die Ausnahmen H173 und H169 (Codex-Hälfte) sollten
  dem Nutzer neu vorgelegt werden, weil ihre Begründung nicht mehr trägt. · **Status:** NEW

## 2. Pflichtfrage „ersetzt ein neues Modell ein Leiter-Modell?" — OpenAI-Seite: nein; aber die Codex-Umstellung vom 25.09. ist ungemessen, und das Zeitfenster für ihre Messung schließt sich

- **Quellen** (alle gesehen 2026-09-28):
  - https://developers.openai.com/api/docs/models — Flaggschiffe weiterhin genau **GPT-6 Astra,
    GPT-6 Sol, GPT-6 Luna**; sonst nur Spezialmodelle (Cyber, Bild, Audio, Life Sciences).
  - https://llmgateway.io/timeline (Sekundärquelle, nur Hinweis) — letzte OpenAI-Einträge am
    2026-09-22; seitdem kein OpenAI-Modell.
  - https://developers.openai.com/api/docs/pricing — pro 1 Mio. Token, unverändert seit 25.09.:
    `gpt-6-astra` $10 / $50 (Cache $1), `gpt-6-sol` $2 / $10 (Cache $0,20), `gpt-6-luna` $0,10 /
    $0,50 (Cache $0,01); `gpt-5.6-sol` $4 / $20, `gpt-5.6-terra` $2 / $12, `gpt-5.6-luna` $0,20 /
    $1,20. Langer Kontext kostet das Doppelte; Batch/Flex die Hälfte.
  - https://learn.chatgpt.com/docs/models — *"GPT-5.6 Sol, GPT-5.6 Terra, and GPT-5.6 Luna remain
    available during the rollout."* (kein Enddatum) und neu: *"On October 14, 2026, GPT-5.5 will
    retire from ChatGPT, ChatGPT Work, and Codex on all plans"*, Ersatz `gpt-6-sol` (bezahlte
    Pläne) bzw. `gpt-6-luna` (Free/Go).
  - https://developers.openai.com/api/docs/deprecations — kein 5.6-Modell und nicht GPT-5.5 als
    abgekündigt gelistet (die Codex-Abschaltung von 5.5 betrifft die ChatGPT-Anmeldung, nicht die API).
  - https://platform.claude.com/docs/en/about-claude/models/overview — **Claude Sonnet 5.5**
    (`claude-sonnet-5-5`) ist gelistet: $2 / $10, 1 Mio. Kontext, Standard-Denktiefe `high`,
    *"The best combination of speed and intelligence"*; Sonnet 5 steht jetzt unter „Legacy".
- **Was es ist:** Auf der OpenAI-Seite nichts Neues. Unsere Codex-Leiter (Giga = `gpt-6-astra`,
  Mega = `gpt-6-sol`, Kilo = `gpt-6-luna`) wurde am 25.09. per DEC-0114 umgestellt — **auf
  Ankündigung, ohne Messung**. Die Regel „kein Tausch ohne Messlauf" kam zwei Tage später
  (DEC-0124, Plan V2.5 §4). Die Umstellung war also regelkonform, als sie geschah, ist aber nach
  der heutigen Regel unbelegt. Besonders die **Kilo-Stufe** hat sich verschoben: von
  `gpt-5.6-terra` (ein mittleres Modell) auf `gpt-6-luna` (das kleinste, 1/20 des Preises).
- **Warum es HIER zählt:** Die alten Modelle sind nur *"during the rollout"* erreichbar, ohne
  Datum. GPT-5.5 zeigt, wie so ein Fenster endet: eine Abschaltung mit gut drei Wochen Vorlauf.
  Solange `gpt-5.6-sol` und `gpt-5.6-terra` noch laufen, lässt sich die Umstellung **nachträglich
  belegen oder widerlegen**; danach nicht mehr.
- **Was eine Messung vergleichen müsste** (Plan V2.5 §4: Lösungsquote, Tokens, Kosten je gelöster
  Aufgabe, gegen das bisherige Modell):
  - **Paare:** Mega `gpt-5.6-sol` gegen `gpt-6-sol`; Kilo `gpt-5.6-terra` gegen `gpt-6-luna`
    (und `gpt-6-sol` als Kontrolle, falls Luna zu klein ist). Giga ist unverändert und braucht
    keinen Lauf. Für die Claude-Seite dasselbe Schema mit Sonnet 5 gegen Sonnet 5.5 — das ist
    Sache der Claude-Hälfte.
  - **Aufgaben:** feste Beispielaufgaben aus **diesem** Repo, die ein objektives Ende haben — am
    besten abgeschlossene `BUG`-Items, zu denen es nach Hausregel einen Test gibt, der ohne den Fix
    rot ist. Den Defekt im Klon unter `C:\Offline Repos\v2-testbed\_round-scratch\<TSK-ID>\`
    wiederherstellen, den Auftrag aus dem Item erzeugen, das Modell lösen lassen. Die Aufgaben
    nach den Klassen der geplanten festen Begründungsliste mischen („mechanisch mit Test",
    „mehrere Dateien", „unklarer Fehler", „Nacharbeit nach Fehlschlag"), weil jede Stufe für
    andere Klassen gedacht ist.
  - **Gemessen je Lauf:** gelöst ja/nein (der rote Test wird grün, sonst nichts in der betroffenen
    Suite rot); Tokens getrennt nach Eingabe, Cache, Ausgabe und **Denk-Ausgabe**; Kosten je
    *gelöster* Aufgabe (Tokens × Preis vom Messtag, der Preis gehört in den Messbericht, nicht in
    `model_tiers.yaml` — DEC-0114 (3)); Züge; Laufzeit; Befunde des Prüfers.
  - **Denktiefe als zweite Achse:** jedes Modell mindestens auf zwei Stufen — der
    Herstellerempfehlung (Sol `medium`, Luna `high`, Astra `low`, Punkt 3) und dem Kit-Standard
    `high` —, sonst misst man Modell und Denktiefe vermischt.
  - **Voraussetzungen, die heute fehlen:** eine Codex CLI auf dem Messrechner (H172, unverändert);
    ein Leser für Codex-Protokolle — `tools/measure_agent_tokens.py` liest nur Claude-Transkripte
    (`~/.claude/projects/...`). Codex führt die Zahlen intern
    (`codex-rs/protocol/src/protocol.rs`: Ereignis `TokenCount` mit `total_token_usage` und
    `reasoning_output_tokens`, gelesen 2026-09-28); ob und wo sie in den Sitzungsprotokollen
    landen, muss die Runde messen. Und wegen Ticket #34370 die **tatsächliche** Denktiefe aus dem
    Protokoll lesen, nicht die angeforderte.
- **Empfehlung:** **übernehmen, als Messauftrag, nicht als Tausch.** Kein Tausch-Vorschlag — es
  gibt keinen neuen OpenAI-Kandidaten, und für die bestehende Belegung keine Messung. Vorschlag an
  den Nutzer: den ersten Messlauf nach Plan V2.5 als **Nachweis für DEC-0114** fahren, solange die
  5.6-Modelle erreichbar sind; ~½ Tag Aufbau (Aufgabenliste + Codex-Protokoll-Leser) plus die
  Läufe. **Zeitkritisch**, weil das Fenster ohne Ankündigung schließen kann. · **Status:** NEW
- **Zeiger für die Claude-Hälfte (nicht doppelt triagieren):** Die Claude-Zeilen der Tabelle sind
  mit Absicht Durchreichnamen (DEC-0114 (2): `sonnet` ist, was Claude Code gerade „sonnet" nennt).
  Wenn Claude Code „sonnet" auf Sonnet 5.5 umstellt — wie es am 25.09. bei Opus 5.5 geschah
  (`radar/2026-09-25-claude-by-claude.md` Punkt 1) —, **wechselt die Kilo-Stufe auf Claude ohne
  jede Messung**. Das widerspricht der Regel aus DEC-0124 („ohne Messung kein Tausch"). Auf Codex
  ist die Regel dagegen durchsetzbar, weil die Zeilen feste Modell-IDs sind. Welche der beiden
  Entscheidungen weichen muss, ist eine Nutzerfrage; ob Claude Code schon umgestellt hat, misst die
  Claude-Hälfte.

## 3. OpenAIs offizielle Leitlinie „welche Denktiefe wofür" — Material für die „Modell-wofür"-Datei aus Strom C

- **Quellen** (alle gesehen 2026-09-28):
  - https://developers.openai.com/api/docs/guides/reasoning — Aufgaben-Tabelle: *`low`* für *"Data
    analysis, drafting, coding, customer support"*; *`medium`* für *"Planning, complex reasoning,
    agentic coding, research"*; *`high`/`xhigh`* für *"Security review, enterprise productivity,
    challenging workflows"*. Zu `xhigh`: *"Only use when your evals show a clear benefit that
    justifies the extra latency and cost"*; zu `max`: prüfen, ob es besser ist als `xhigh`.
    Standard bei GPT-6 ohne Angabe: `medium`. **Astra kennt `none` nicht** — *"Setting
    `reasoning.effort` to `none` returns HTTP 400."* Denk-Tokens *"are billed as output tokens"*.
  - https://developers.openai.com/api/docs/guides/latest-model („Using GPT-6") — Sol *"for strong
    reasoning on demanding tasks"*, Luna *"for efficient, repeatable work at scale"*; beim Umstieg
    *"compare results on representative tasks"*.
  - https://learn.chatgpt.com/docs/models — Startwerte *"Medium effort for Sol, High for Luna, or
    Light for Astra"*, wobei *"Astra's Light setting is `low`"*. Stufen-Bezeichnungen der Oberfläche:
    Low, Medium (default), High, Extra high, Max, Ultra.
  - https://learn.chatgpt.com/docs/agent-configuration/subagents — `gpt-6-sol`: *"Start here for
    demanding agents … ambiguous, multi-step work that needs planning, tool use, validation"*;
    `gpt-6-luna`: *"fast, narrowly scoped agents handling clear, repeatable, or high-volume work"*;
    `high`: *"trace complex logic, check assumptions, or work through edge cases"*; `low`: *"the
    task is straightforward and speed matters most"*.
- **Was es ist:** Zum ersten Mal eine offizielle Zuordnung Denktiefe ↔ Aufgabenart, nicht nur je
  Modell. Sie passt zur Recherche 0c aus Plan V2.5 (*„mehr Denktiefe ist nicht immer besser"*) und
  ist jetzt mit Herstellerquelle belegt.
- **Warum es HIER zählt:** Unsere Kits stehen anders: `team-kits/dev-team/ladder.yaml` `effort:
  default: high`, `large: xhigh`; von den 27 Rollen mit `effort:` stehen weiterhin **25 auf
  `high`**, 2 auf `low` (gezählt 2026-09-28, gleich wie am 25.09.). Für Codex heißt das: Kilo
  (Luna) auf `high` entspricht der Herstellerempfehlung; Mega (Sol) auf `high` liegt eine Stufe
  **über** ihr; Giga (Astra) auf `high` zwei Stufen darüber — und `large: xhigh` genau dort, wo
  OpenAI einen Messbeleg verlangt. Die vier deutschen Stufen des Plans (niedrig · mittel · hoch ·
  sehr hoch) passen auf `low · medium · high · xhigh`; `none` (nur Sol/Luna, bei Astra ein
  Fehler 400), `max` und `ultra` liegen außerhalb — das gehört in die Datei, damit niemand
  `none` für alle Stufen einträgt.
- **Empfehlung:** **übernehmen als Inhalt, nicht als Regeländerung.** Die Zitate oben in die
  geplante „Modell-wofür"-Datei (Strom C) aufnehmen, mit Quelle und Lesedatum. Die Kit-Standards
  **nicht** ändern, bevor die Messung aus Punkt 2 beide Denktiefen vergleicht — dort wird genau
  diese Frage beantwortet. ~30 min als Teil von Strom C. · **Status:** NEW

## 4. Codex 0.158.0 (heute): Windows-Sandbox-Fehler bei „großen Berechtigungsprofilen" behoben, und neue Bestätigungspflicht für erhöhte Befehle

- **Quelle:** https://learn.chatgpt.com/docs/changelog, **0.158.0 (2026-09-28)**, gesehen
  2026-09-28: *"Fixed Windows sandbox failures involving ordinary Windows 10 paths, rejected stored
  credentials, and large permission policies."* und *"Terminal input approval is enabled by default
  for commands running with elevated permissions; runtime-only grants no longer cause unnecessary
  reviews."*
- **Warum es HIER zählt:** Der Generator schreibt ein ausführliches Berechtigungsprofil
  `[permissions.team-kit.filesystem]` mit vielen Einträgen (`gen_provider_artifacts.py` ab Zeile
  838), und der Nutzer arbeitet auf Windows. Wenn „large permission policies" unser Profil
  einschließt, lief die Codex-Sandbox eines Kit-Projekts auf Windows vor 0.158.0 womöglich
  fehlerhaft. Das ist eine Folgerung, keine Messung — was „groß" heißt, sagt der Eintrag nicht.
  Die neue Bestätigungspflicht für erhöhte Befehle kann zusätzliche Klicks bringen (Plan V2.5 §5
  zählt Klicks); der Generator setzt keinen `[windows]`-Schlüssel (geprüft 2026-09-28), welche
  Befehle in einem Kit-Projekt als „erhöht" laufen, ist ungemessen.
- **Empfehlung:** **beobachten; bei der nächsten Codex-Messung mitprüfen** (Profil laden unter
  0.157.x und 0.158.0 auf Windows; Klicks zählen). Falls der Fehler unser Profil betraf: 0.158.0
  als Mindestversion für Windows notieren. ~15 min als Zusatz zur Messung aus Punkt 1. ·
  **Status:** NEW

## 5. Konfigurations-Drift im Generator: `max_threads` ist nur noch ein Alias, `max_depth` fehlt in der Referenz, zwei neue Schlüssel für Unteragenten-Standards

- **Quellen** (gesehen 2026-09-28):
  - https://learn.chatgpt.com/docs/config-file/config-reference — `agents.max_threads`: *"Legacy
    alias for `agents.max_concurrent_threads_per_session`."* Neu dokumentiert:
    `agents.default_subagent_model` (*"Default model for spawned agents. An explicit spawn model
    takes precedence."*) und `agents.default_subagent_reasoning_effort`. `agents.max_depth` steht
    **nicht** mehr auf der Seite.
  - Quelltext: `codex-rs/config/src/key_aliases.rs` bildet `["agents","max_threads"]` auf
    `["agents","max_concurrent_threads_per_session"]` ab; derselbe Code nennt in seinem Kommentar
    `[agents] max_depth = 1` als Beispiel, und `multi_agents/spawn.rs` prüft
    `turn.config.agent_max_depth` weiterhin.
- **Warum es HIER zählt:** `gen_codex_config` schreibt `[agents] max_threads = 6` und
  `max_depth = 1` (`gen_provider_artifacts.py:834-836`). Beides wirkt heute noch (Alias bzw.
  Quelltext), aber `max_depth = 1` ist die Stelle, die verhindert, dass ein Unteragent selbst
  Unteragenten startet — die Grundlage der Rollentrennung. Dass die Doku sie nicht mehr nennt, ist
  ein frühes Warnzeichen, keine Störung. Die beiden neuen Standards würden festlegen, auf welchem
  Modell die **eingebauten** Codex-Rollen laufen (der Generator-Kommentar sagt: *"Built-in Codex
  roles also remain available"*); heute erben sie Modell und Denktiefe der Hauptsitzung.
- **Empfehlung:** **klein übernehmen** — den kanonischen Namen `max_concurrent_threads_per_session`
  schreiben und einen Test, der misst, dass die erzeugte `config.toml` eine Tiefengrenze trägt;
  `max_depth` beim nächsten Codex-Scan erneut prüfen. `default_subagent_*` nur mit Punkt 1
  zusammen entscheiden. ~30 min. · **Status:** NEW

---

# Teil 2 — Was hat sich insgesamt getan? (mit einem zweiten Blick auf das, was nicht sofort passt)

- **Der Hersteller sagt selbst, dass Hooks keine vollständige Sperre sind.** *"Treat tool hooks as
  a useful guardrail, not a complete enforcement boundary."* (https://learn.chatgpt.com/docs/hooks,
  gesehen 2026-09-28). Das passt nicht zum Thema „neue Modelle", stützt aber die Richtung von Plan
  V2.5 Strom B: das Raten von Schreibzielen in Befehlszeilen durch ein Kernel-Schreibprotokoll mit
  Kontrolle danach ersetzen. Der Hersteller setzt dieselbe Grenze an dieselbe Stelle.
- **Messwert für Plan V2.5 §5 aus diesem Lauf selbst:** Dieser Lauf hat **nur gelesen** und nur in
  `radar/` und den eigenen Notizordner geschrieben. Trotzdem hat `gate_lead_write_scope.py` **zehn**
  Befehle verweigert, die nichts Geschütztes schrieben: zwei `for`-Schleifen über Dateien (`$f`,
  `$h`), eine `gh api`-Abfrage mit `?` in der URL, fünf `--jq`-/`python -c`-Ausdrücke mit `[` oder
  `.[]` (drei davon als Schreibzugriff auf den Elternordner `..` gelesen), einen Befehl mit einer
  Variablen (`$F`) und zuletzt eine Textkorrektur an diesem Bericht in `radar/`, weil das Lesen der
  Zeile das Zeitbudget des Gates aufbrauchte. Einer davon meldete einen Schreibzugriff auf
  `project_memory/decisions/active/for` — das Wort `for` einer Schleife, als Pfad gelesen. Umwege
  gab es jedes Mal (Skript in eine Datei, dann starten), aber das sind genau die „Fehlblockaden",
  die §5 gegen null drücken will. Nicht Codex-Stoff, aber ein gemessener Befund; der Lead
  entscheidet, ob er in die §5-Zahlen gehört.
- **Wettbewerb: GitHub lässt den Nutzer die Denktiefe pro Auftrag wählen.** *"Pick a reasoning level
  alongside the model when you start a task, and Copilot cloud agent will use it for the run."*
  (https://github.blog/changelog/2026-08-03-customize-the-reasoning-level-for-copilot-cloud-agent/,
  gesehen 2026-09-28; vom 03.08., bisher nicht aufgeführt). Das ist dieselbe Fähigkeit, die uns auf
  Claude fehlt (H169) und die Codex laut Punkt 1 hat. GitHub listet zudem die neuen GPT-6-Modelle,
  das neue Opus und Grok 4.7 im Modell-Auswahlfeld (Suchergebnis, nur Hinweis).
- **Community-Stimmen, die zeigen, warum gemessen werden muss** (nur Hinweise, keine Belege, gesehen
  2026-09-28 unter
  https://community.openai.com/t/announcing-gpt-6-sol-and-gpt-6-luna-in-the-api-codex-and-chatgpt/1399925):
  ein Nutzer beschreibt die Kette *"Sol High Orc → Luna worker → Astra re-worker → Astra Max
  reviewer"*; ein anderer berichtet von einem eigenen Vergleich („Codexometer"), in dem Luna bei
  einigen Aufgaben **vor** Sol lag. Beides widerspricht der einfachen Annahme „größer ist besser" —
  was genau der Grund für die Messregel aus DEC-0124 ist.
- **„Angefordert" und „tatsächlich gelaufen" fallen bei Codex auseinander:** Ticket #34370 (offen)
  und das geschlossene #33268 (siehe Punkt 1). Für jede künftige Messung und jede Kosten-Aussage
  gilt darum: die tatsächliche Denktiefe aus dem Protokoll lesen.
- **Das Anbieterfeld wird breiter, der Stolperdraht für ein neutrales Quellformat ist aber nicht
  erreicht.** In der Woche kamen Grok 4.7 (xAI, 21.09.) und MiMo V2.6 (Xiaomi, 22.09.) dazu
  (https://llmgateway.io/timeline, nur Hinweis). Keiner davon ist ein Coding-Werkzeug mit eigenem
  Agenten-/Hook-Format, das die Kits bedienen müssten; der Stolperdraht aus HARNESS_LOG 2026-07-14
  („ein dritter Anbieter braucht Artefakte") ist nicht ausgelöst.
- **Quellformat (ständige Pflicht):** Punkt 1 bringt eine neue Fähigkeit, die das Claude-Quellformat
  nicht ausdrücken kann: **Denktiefe pro Start** (`reasoning_effort` am `spawn_agent`). Die
  `codex:`-Überlagerung erreicht nur Felder der Rollendatei, nicht den Startbefehl — genau wie bei
  den fünf Hook-Fähigkeiten aus dem Bericht vom 25.09. (Punkt 5). Das ist die sechste Fähigkeit,
  die das Ventil nicht erreicht; dieser Befund stützt den dort vorgeschlagenen vierten
  Stolperdraht-Punkt, löst aber keinen der bestehenden aus.
- **Kleinkram der Woche ohne Bezug zum Harness** (Changelog, gesehen 2026-09-28): 0.158.0 —
  Kopieren/Einfügen in der Vollbild-Oberfläche, OAuth-Client-Secrets für MCP-Server, Tokens für
  exec-server-WebSockets, transparente Bildhintergründe, Linux-/macOS-Sandbox-Fixes, Mermaid-Fixes,
  *"Approval reviews now retry when new user input arrives"*. 0.157.1 (26.09.): der Changelog
  selbst sagt, die Release-Highlights *"could not be determined"*; ein erster Abruf nannte einen
  macOS-Sicherheitsfix, der zweite nicht — darum hier nicht als Befund geführt.

---

## Auch geprüft — ohne Handlungsbedarf

- **Preise:** unverändert gegenüber dem 25.09. (Quelle in Punkt 2). Die Aktion für `gpt-5.6-sol`
  gilt weiter *"at least through November 21, 2026"*; die Tabelle nennt das Modell nicht mehr, und
  die Beobachtungsliste von `model_tiers.yaml` ist leer (DEC-0114 (1)).
- **GPT-5.5-Abschaltung in Codex am 14.10.:** kein Kit und kein Werkzeug pinnt `gpt-5.5` (Suche über
  `team-kits/`, `tools/`, `.codex/` am 2026-09-28; Treffer nur in Test-Kommentaren und einer
  Test-Vorlage für `gpt-5.6-sol`).
- **Hook-Ereignisse:** unverändert zwölf (`SessionStart`, `SessionEnd`, `SubagentStart`,
  `SubagentStop`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`,
  `UserPromptSubmit`, `Stop`, `Interrupt`). Neu gelesen: bei `PermissionRequest` gilt *"If multiple
  matching hooks return decisions, any deny wins"*; für `PreToolUse` sagt die Seite zu
  widersprüchlichen Entscheidungen weiterhin nichts — die Messung aus dem Bericht vom 25.09.
  (Punkt 6) bleibt nötig. `permissionDecision: "ask"` ist *"parsed but not supported yet"*.
- **Dachticket openai/codex#21753 („Full Claude Code Hook Parity"):** weiter offen, zuletzt
  aktualisiert 2026-09-17. Wie am 25.09. festgestellt, hinkt sein Text der Doku hinterher; Punkt 1
  zeigt, dass der Quelltext sogar vier Monate voraus war.
- **`.codex/agents/*.toml`-Felder:** unverändert (`name`, `description`, `developer_instructions`
  Pflicht; `model`, `model_reasoning_effort`, `sandbox_mode`, `mcp_servers`, `skills.config`
  optional). Neu dokumentiert ist die Registrierung einer Rolle über `agents.<name>.config_file` in
  der `config.toml` — ein zweiter Weg, den der Generator nicht braucht.
- **`model_reasoning_effort`-Werte in der Konfigurationsreferenz:** *"`low`, `medium`, `high`,
  `xhigh`, `max`, or `ultra`. Available levels depend on the model and client."* — der Widerspruch
  `max` gegen `ultra` bleibt (entschieden als `codex-0905-effort-ceiling`, getragen von H172);
  Punkt 3 bringt nur die Aufgaben-Zuordnung dazu.
- **AGENTS.md-Standard:** keine neue Fassung gefunden; die Seite https://agents.md/ nennt weiter
  keine Versionsnummer (gesehen 2026-09-28).

---

## Offene frühere Punkte dieses Wächters (nur Zeiger, nicht neu gemeldet)

- Aus `radar/2026-09-25-codex-by-claude.md` sind **Punkte 2–8 noch nicht triagiert** (nicht in
  `decided.md`): `additionalContext` auf `PreToolUse` (Punkt 2 — **Punkt 1 hier ersetzt dessen
  Aussage über die blockierten Spawn-/Frage-Kanäle**), Worktree-Sitzungen ohne Kit-Regeln (3),
  2.500-Token-Grenze und `timeout`-Obergrenzen (4), Quellformat-Lücke mit fünf Fähigkeiten (5 —
  Teil 2 hier ergänzt eine sechste), Vorrang bei widersprüchlichen Hooks (6), Denktiefe-Vokabular
  (7 — Punkt 3 hier liefert die offizielle Aufgaben-Tabelle dazu), `/usage` als Kostenzahl (8).
- `codex-0905-effort-ceiling` (`max` gegen `ultra`) — unverändert, braucht eine Codex CLI.
- `codex-0905-subagentstart-payload` (#32753, „not planned") — gilt weiter für `SubagentStart`;
  **Punkt 1 zeigt, dass `PreToolUse` auf `spawn_agent` die Nutzlast trägt**, die dort fehlt. Der
  Kommentar im Generator, der sich auf #32753 stützt, sollte das beim nächsten Anfassen sagen.
- `codex-0905-missing-pin-400` (#25440) — unverändert offen.
