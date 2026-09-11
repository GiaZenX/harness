# Arm B — das Kit in der leichten Form (aufgebaut und gemessen; der Lauf und das Urteil gehören dem Nutzer)

## Aufbau (steht unter `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0135/experiment/arm-b/`)

1. Ein Heimverzeichnis mit einer Kopie des gestempelten `team-kits/` dieses Baums als Kit-Store
   (`home/.claude/team-kits`, wie `tools/light_kit_pilot.py` es baut).
2. Ein leerer Projektordner `arm-b/project/` mit `brief.md` und `invoices.json` (dieselben Bytes wie
   in Arm A), `git init`.
3. Der Einstieg wie die Einstiegsdatei ihn vorschreibt: `init_project_memory.ps1 -Team dev-team`,
   Masterplan aus dem Brief (kurz), `project_config.yaml` mit `preset: solo`, ein DRAFT `PR-0001`
   mit den fünf Punkten als Abnahmekriterien, `generate-index`, dann `scaffold_team.ps1 -Team
   dev-team -Preset solo`, Neustart (der SessionStart-Hook räumt den Übergabemarker).
4. Die Sitzung: `claude -p "weiter"` im Projektordner — der gebundene `project-manager` liest den
   Entwurf, stellt die Scope-Frage, schneidet EIN Bauer-Item mit dem ganzen Ziel (`create-task
   --rung opus --effort high`: `DEC-0095` (1) setzt den Bauer-Standard auf Opus, **gebaut ist das
   im Kit noch nicht** — `team-kits/dev-team/ladder.yaml` führt `build: pin` und `top: fable`, also
   trägt der Lauf die Stufe als Bitte des Auftrags), fährt `dispatch` und spawnt den Bauer; am Ziel
   EINE Prüferrunde
   (`quality-engineer`), dann die Lieferfrage.

## Warum der Lauf hier NICHT unbeaufsichtigt gefahren wurde — **gemessen**, nicht behauptet

Bis zur Zielrunde stand hier die Behauptung, eine Headless-Sitzung (`-p`) könne `AskUserQuestion`
nicht beantworten und der PM bleibe am ersten Tor stehen. Der Prüfer hat sie als die einzige
unvermessene Tatsachenbehauptung der Runde gemeldet (B1). Sie ist jetzt gemessen — und sie war in
ihrem Mechanismus falsch:

Aufbau wie oben (Schritte 1–3, `rig/arm_b.py prepare`, alle fünf Schritte rc 0, installierte Rollen
`backend-developer, project-auditor, project-manager, quality-engineer, software-architect`), dann
**zwei** `claude -p "weiter"`-Läufe (Provider 2.1.267, Modell `haiku`, `--max-turns 30`,
`AskUserQuestion` ausdrücklich unter `--allowedTools`; Lauf 2 zusätzlich mit
`--dangerously-skip-permissions`):

| Lauf | Uhr | Züge | Werkzeugaufrufe | `AskUserQuestion` | Ende |
|---|---|---|---|---|---|
| 1 | 08:11:08–08:12:21 | 11 | 10 | **0** | `end_turn`, Frage in **Prosa** an den Nutzer |
| 2 (Rechte übersprungen) | 08:14:02–08:14:33 | 5 | 4 | **0** | `end_turn`, „PR-0001 ist bereit für die Scope-Freigabe. Ich kann die Frage stellen, damit du sie freigeben kannst" |

Der PM las Masterplan, `PR-0001` und die Konfiguration, erzeugte den Sitzungsbrief, fuhr `validate`
— und gab dann ab. Er bleibt also **nicht am Tor stehen, er erreicht es nicht**: kein
`AskUserQuestion`, keine Freigabe-Anfrage, kein Lease, kein Bauer-Spawn, `permission_denials: 0`,
und `--max-turns` war in beiden Läufen weit unausgeschöpft. In `-p` ist die Rückgabe an den Nutzer
das Ende der Sitzung.

Zwei Nebenmessungen aus denselben Strömen: in **beiden** Läufen starteten vier SessionStart-Haken
und antworteten mit Code 0 (`hook_started`/`hook_response` im Rohstrom) — die Haken des Kits liefen
also; was der Provider verweigerte, ist enger als „die Einstellungsdatei": seine Fehlerzeile nennt
die fünf `permissions.allow`-Einträge, die er ohne Vertrauensdialog des Arbeitsbereichs ignoriert,
und `--dangerously-skip-permissions` ändert daran nichts. Der programmatische Freigabeweg
(`kernel/sdk_approval.py`, FR-0083) prägt nur nicht irreversible Arten und bliebe für ein
Experiment, das die NUTZER-Form messen will, das falsche Instrument.

Die Messung liegt als Eintrag `headless_pm_stop_point` in `tools/provider_observations.json`
(Datum, Provider-Version, Methode, Ort, plus die zwei Dinge, die sie **nicht** misst: ein stärkeres
Modell, und eine interaktive Sitzung). Die Rohströme und ihre Zusammenfassungen liegen neben dieser
Datei (`probe-20260911-081108.summary.json`, `probe-20260911-081402.summary.json`).

**Nicht gefahren wird der Arm selbst** — das ist keine technische Grenze, sondern `DEC-0095` (6):
kein Experiment-Arm ohne das Wort des Nutzers, solange das Wochenbudget über der Hälfte steht. Das
löst den Satz des Items („you PREPARE both arms **and run the kit arm**") ab.

Deshalb ist Arm B so vorbereitet, dass der Lead ihn **in einer interaktiven Sitzung** fährt: er
beantwortet die Tore (drei Klicks: Scope, Lieferung, Abnahme), tut sonst nichts, und liest danach
Tokens (`/cost` bzw. das Sitzungs-JSON), Wanduhr (Uhr vor/nach) und Runden
(`project_memory/.audit/hook_events.jsonl`: Spawns, Prüferrunden) ab. Was gezählt wird, steht in
`brief.md`.

## Was diese Runde gemessen hat (ohne den Lauf)

- Der Aufbau bis Schritt 3 läuft als Prozess durch (`tools/light_kit_pilot.py` baut denselben
  Aufbau je Kit in ~20 s; dort ist der Solo-Standard installiert, der PM-Codeschreibzugriff
  verweigert, die drei Bestellungen geleast).
- Die Kosten der leichten Form auf SICH SELBST: dieses Ziel (TSK-0135) ist der erste Lauf der Form
  — die (g)-Tabelle im Protokoll trägt seine Tokens, Runden und Wanduhr gegen die Ströme der
  Generation 5.

## Das Urteil

Das Qualitätsurteil über beide Seiten ist des Nutzers (DEC-0093 (4)): er öffnet zwei
`index.html`, gibt je Punkt 1–5 der Aufgabe eine Note 1–5 und einen Satz.

Was das Urteil seit `DEC-0095` entscheidet, hat sich verschoben: die Standard-Stufe des Bauers ist
dort schon gesetzt (Opus, aus Kosten, (1)), und der Arm B fährt deshalb das Kit **auf Opus**. Das
Experiment misst damit `DEC-0095` (7): das Kit auf Opus gegen Fable allein — die Frage, die der
Nutzer wirklich hat.
