# TSK-0130 — Prüfbericht Runde 1 (harness-verifier)

Gemessen 2026-09-06, 05:03–06:02 (Uhr gelesen, nicht hochgerechnet). Arbeitskopien ausschließlich
unter `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0130/verify/`:
`tree/` (Worktree-Kopie ohne `.git`, danach eigenes `git init` für die `git ls-files`-Tests),
`base/` (`git archive b7f282e`), `applied/` (b7f282e + Patch), `rig/` (eigene Rigs).
Alle drei Rigs (`verify_rig.py`, `pilot.py`, `edge.py`, `wait_for.py`) verweigern den Lauf, wenn das
Arbeitsverzeichnis nicht ihr eigenes ist, und schreiben jede Datei binär (`"rb"`/`"wb"`) bzw. mit
ausdrücklicher `newline`-Politik. Nach 23 Mutationsläufen ist `diff -rq worktree tree` leer.

Host-Regel eingehalten: immer nur EIN pytest gleichzeitig, jeder Lauf mit Timeout, keine Vollsuite,
kein CPU-sättigendes Rig.

---

## Blockierend

### B1 — Die Büro-Verfassung und `office-team/ladder.yaml` behaupten eine Ausnahme, die die Erklärung nicht trägt und der Dispatcher nicht einhält

* `team-kits/office-team/constitution/AGENTS.md:376-378` — »die filing pair **records-clerk** /
  **filing-reviewer** keeps `sonnet`/`low` as the named exception«
* `team-kits/office-team/ladder.yaml:11-13` — »The sonnet-LOW filing floor of DEC-0047 … **stays as
  the named exception**«

Gebaut ist etwas anderes. In `team-kits/office-team/ladder.yaml:72-75` nennt `exceptions:` für beide
Rollen **nur** `effort: low`. Die Sprosse `sonnet` ist keine Ausnahme, sondern schlicht der Pin
(`model: worker` → sonnet) unter `classes: reading: pin` — und sie steigt nach dem ersten FAILED-Lauf.

Gemessene Zeile (mein eigener Drei-Kit-Pilot, `rig/pilot.log.json`, 05:30):

```
climb records-clerk: [(0, 'sonnet'), (1, 'opus'), (2, 'opus'), (3, 'opus')]
records-clerk {"class":"reading","effort":"low","rung":"sonnet",
 "why":"sonnet: pin worker, class reading starts on pin, 0 failed run(s), top opus; effort low: the exception fixes it"}
```

Das Verhalten selbst ist DEC-0078 (1) konform (Top-Sprosse opus für jede Büro-Rolle außer dem
office-developer) und der Umsetzer nennt die Frage im Protokoll (Abschnitt 4a, »A reading this
stream did NOT decide«). **Der Defekt ist der geschriebene Satz**, nicht das Verhalten: der
Verfassungstext ist das, was der Office-Manager auf jeder Runde liest, und er verspricht ein
„keeps/stays", das nach einem Fehllauf nicht gilt. Hausregel 3.

Minimaler Fix (beide Dateien liegen im `allowed_scope`): den Satz auf das Gebaute umschreiben —
»the filing pair STARTS on its `sonnet` pin and its effort is fixed at `low` by the named exception;
a FAILED run still climbs the rung to opus (the kit top)« — und die offene Nutzerfrage dort
verlinken. Die Verhaltensfrage (`exceptions: records-clerk: {top: sonnet}`) bleibt beim Nutzer.

### B2 — Drei Zeitplan-Behauptungen überleben in `.claude/hooks/`, ungemessen und ungenannt

AC-1 verlangt, dass keine Watcher-/README-Prosa einen Zeitplan behauptet, den das Repo nicht baut.
Umgeschrieben wurden `radar/README.md` und beide Watcher-Definitionen; `tools/test_radar_trigger.py`
liest genau diese drei Dateien (`TEXTS`, Zeile 40). Nicht umgeschrieben und von keinem Test gelesen:

* `.claude/hooks/gate_spawn_needs_item.py:11` — »Two agents in this repo **run on a weekly schedule**
  and hold no item (`radar-watcher`, …)«
* `.claude/hooks/gate_spawn_needs_item.py:74` — »If this role legitimately runs without an item (**a
  scheduled watcher**), …« (Text einer laufenden Verweigerung, nicht nur Kommentar)
* `.claude/hooks/_harness.py:2849` — »**the weekly watchers run on a schedule** and write only into
  `radar/`«

Verschärfend: die neu geschriebenen Watcher-Kommentare zeigen ausdrücklich dorthin
(`.claude/agents/radar-watcher.md:12-13`: »Read there for why the exemption is declared here instead
of listed in the gate«). Der Zeiger führt jetzt auf den Satz, den die Runde gerade als unwahr
gemessen hat.

`.claude/hooks/**` steht im `forbidden_scope` — der Strom durfte das nicht anfassen. Genau darum
gehört es als **benanntes Loch** (kernel-vergebenes BUG mit `limits`) in die Liste, so wie BUG-0250
das für die fünf Kit-Texte tut. Das fehlt. Grep, mit dem ich es gefunden habe:
`grep -rn -i "weekly\|schedul" --include=*.py .claude/hooks/`.

Minimaler Fix: `capture BUG --hole` mit Mechanismus (»drei Zeitplan-Sätze in der
Durchsetzungsschicht, vom AC-1-Test nicht gelesen, weil `TEXTS` Rollen-Definitionen und
`radar/README.md` ableitet«), `limits` (»die Sätze gewähren nichts; der Gate-Entscheid hängt an
`harness_item:` in der Definition, nicht an dem Wort ,schedule'«) und Verweis auf
`test_radar_trigger.TEXTS` als die Stelle, die sie erfassen würde.

---

## Nicht blockierend — benannte Restposten und Befunde

### F3 — Die Zahl „twelve runs" ist gemessen falsch und wächst wöchentlich

* `radar/README.md:19` — »while **twelve runs in nine weeks** had all been started by hand«
* `tools/test_radar_trigger.py:7` und `:141` — dieselbe Zahl
* `project_memory/staging/TSK-0130/dec-trigger.json:7` — »radar/ holds **12 claude reports** and 1
  codex report«

Gemessen (`ls radar/`): **14** datierte Berichte — `2026-07-03.md`, `2026-07-06.md` (beide echte
Radar-Läufe, Kopfzeile »# Radar — …«, der erste sagt »First dated radar run«), elf `-claude.md` und
ein `-codex.md`. „12" zählt nur die suffigierten; „12 claude reports" im DEC-Vorschlag ist auch
gegen diese Zählweise falsch (es sind elf). Hausregel 4: eine Zahl über etwas Wachsendes gehört in
den Bericht, nicht in einen versendeten Text — nächste Woche ist sie wieder falsch. Der
`dec-trigger.json` geht an den **Nutzer** als Entscheidungsgrundlage; dort wiegt es am schwersten.

Minimaler Fix: die Zahl aus allen drei Stellen entfernen (»jeder Bericht in diesem Verzeichnis wurde
von Hand gestartet« trägt die Aussage allein) bzw. im DEC-Vorschlag korrigieren.

### F4 — Der Kit-Endpunkt senkt einen Rollen-Pin STILL ab; sichtbar nur auf der Lease

Eigene Kantenmessung (`rig/edge.py`, 05:47):

```
A top BELOW the role pin (top sonnet, pin opus)  {"rung":"sonnet", "why":"sonnet: pin opus, class build starts on pin, 0 failed run(s), top sonnet; …"}
B exception rung ABOVE the kit top (rung fable, top opus)  {"rung":"opus", …}
C class floor ABOVE the kit top (qa fable, top opus)       {"rung":"opus", …}
D exception top BELOW the role pin                          {"rung":"sonnet", "why":"… pin fable …"}
```

`ladder_for_order` (`team-kits/kernel/dispatch.py:2419-2424`) dokumentiert korrekt »a class floor
never LOWERS a pin« — über den **Top** sagt es nichts, und der Top senkt sehr wohl. Das ist genau die
„silent downgrade"-Klasse aus FR-0047, die DEC-0077 (5) mit der Session-Brief-Anzeige sichtbar machen
wollte. Sichtbar ist es heute nur im `why`-Feld der Lease und in der `dispatch`-stderr-Zeile — **nicht**
im Header (der trägt nur `rung`/`effort`) und **nicht** im Brief (BUG-0249/H167). Kein heutiges Kit
trifft den Fall (kein gelieferter Pin liegt über seinem Kit-Top), aber eine `model_map`-Zeile des
Nutzers erreicht ihn.

Minimaler Fix: einen Satz in die `ladder_for_order`-Dokumentation (»der Endpunkt kappt auch nach
unten; das `why` sagt es«) und die Sichtbarkeit an BUG-0249 hängen. Kein Kernel-Fix nötig.

### F5 — Das Journal nennt eine Paritätsmatrix-Kategorie, die die Matrix nicht führt

`docs/reviews/phase0-disposition.md` Zeile 828 (Zeile 43 der Matrix) stuft auf
`bewusst geändert (…)` um — richtig, das ist eine deklarierte Klassifikation
(`tools/test_shortening_net.py::test_every_classification_is_one_the_document_declares`, 44 passed
in meinem Lauf). Die drei Journaleinträge desselben Commits (Zeilen ~1701-1703) sagen dagegen
dreimal »Parity matrix row 43 … is **RECLASSIFIED from behalten to durch Mechanik ersetzt**«. Diese
Kategorie existiert nicht. Zusätzlich behauptet der **office**-Journaleintrag die Umstufung von Zeile
43, deren Quellen laut Matrix nur `dev/AGENTS:§11; res/AGENTS:§11` sind.

Minimaler Fix: die drei Journalzeilen auf `bewusst geändert` ziehen; im Office-Eintrag den
Row-43-Satz streichen.

### F6 — „refuses a spawn that would run below the rung" ist zu eng formuliert

`team-kits/dev-team/constitution/AGENTS.md:347`, `research…:323`, `office…:385` und `README.md`
sagen „below". Gebaut ist `spawn_model_refusal` (`dispatch.py:812-832`): jedes `model`, das **nicht
gleich** der Sprosse ist, wird verweigert — auch ein höheres. Gemessen durch den gelieferten Test
selbst (`tools/test_ladder.py:583-584`: Sprosse `sonnet`, `spawn_model="opus"` → `DispatchError`).
Unterbehauptung, kein Loch; sie kostet einen PM einen Fehlversuch. Fix: »eine Spawn-Zeile, deren
`model` nicht die Sprosse ist«.

### F7 — `radar/decided.md:30` verspricht eine Messung, die die Runde nicht machen konnte

»codex-0905-effort-ceiling … PR-0010 AC-2/AC-3: **the round measures the ceiling directly** (a spike
against the CLI)«. Die Runde konnte nicht (kein Codex-CLI auf dem Host, BUG-0254/H172). `radar/**`
liegt im `allowed_scope`; eine angehängte Zeile mit dem Zeiger auf BUG-0254 hätte den Zeiger korrekt
gehalten. Niedrig.

### F8 — `.ruff_cache` in Template-Bäumen des Worktrees

`team-kits/dev-team/templates/repo/.ruff_cache`, `team-kits/research-team/templates/repo/.ruff_cache`
(und `./.ruff_cache`) sind Rückstände des Ruff-Laufs dieser Runde. Sie sind gitignoriert, gehen nicht
in den Patch und nicht in den Kit-Content-Hash (mein `tools/validate.py`-Lauf ist ohne sie grün und
akzeptiert dieselben VERSION-Stempel). Reine Aufräumnotiz für den Merge.

---

## Angriff auf den FIX — was ich selbst gemessen habe

### Eigenes Mutationsrig, 23 Fälle, 23-mal wie erwartet (`rig/verify_rig.log.json`)

Jeder Lauf über die **ganze** betroffene Suite, nicht über ein enges `-k` — genau die
Selektionsbreite, an der eine Mutation „gedeckt" aussehen kann, ohne es zu sein.

| Fall | Mutation | Auswahl | Ergebnis |
|---|---|---|---|
| V1 | `ladder_declaration` verweigert ein Kit ohne `ladder.yaml` nicht mehr | `tools/test_ladder.py` | rc 1 · 1 failed, 32 passed |
| V2 | unbekannter Sprossenname in `classes:` wird nicht mehr verweigert | test_ladder | rc 1 · 1 failed, 32 passed |
| V3 | Kit-Endpunkt kappt den Aufstieg nicht mehr | test_ladder | rc 1 · 1 failed, 32 passed |
| V4 | Klassen-Boden darf einen Pin wieder senken | test_ladder | rc 1 · 1 failed, 32 passed |
| V5 | Regel 2 zählt nicht mehr (kein Aufstieg nach FAILED) | test_ladder | rc 1 · 3 failed, 30 passed |
| V6 | Rollen-Ausnahme ignoriert (office-developer steigt nicht mehr auf fable) | test_ladder | rc 1 · 2 failed, 31 passed |
| V7 | Aufwands-Ausnahme ignoriert (Filing-Boden verliert `low`) | test_ladder | rc 1 · 1 failed, 32 passed |
| V8 | `large`-Zweig des Aufwands entfällt | test_ladder | rc 1 · 1 failed, 32 passed |
| V9 | Sprosse/Aufwand werden nicht mehr auf Lease und Task geschrieben | test_ladder | rc 1 · 13 failed, 20 passed |
| V10 | Kit-Hook reicht `model` nicht mehr an den Kernel | test_ladder | rc 1 · 1 failed, 32 passed |
| V11 | `validate_dispatch` leitet am Spawn nicht mehr neu ab | test_ladder | rc 1 · 1 failed, 32 passed |
| V12 | Office-Top auf fable angehoben | test_ladder + test_model_ladder | rc 1 · 2 failed, 41 passed |
| V13 | **vergangenes** Watch-Datum unter den Marker gepflanzt (2026-09-05) | test_model_ladder | rc 1 · 1 failed, 9 passed |
| V14 | **künftiges** Watch-Datum gepflanzt (2027-01-01) — Kontrolle | test_model_ladder | **rc 0 · 10 passed** |
| V15 | Header nennt die Mechanik wieder „open work item" | test_model_ladder | rc 1 · 1 failed, 9 passed |
| V16 | Generator-Verweigerung nennt DEC-0076 nicht mehr | test_model_ladder | rc 1 · 2 failed, 8 passed |
| V17 | `light`-Alias kehrt in die Tabelle zurück | test_model_ladder | rc 1 · 2 failed, 8 passed |
| V18 | `radar/README.md` behauptet wieder einen Zeitplan | test_radar_trigger | rc 1 · 1 failed, 2 passed |
| V19 | `radar/README.md` nennt nur eine **Kadenz** („weekly") — Kontrolle | test_radar_trigger | **rc 0 · 3 passed** |
| V20 | Watcher-Definition behauptet einen Cron-Job | test_radar_trigger | rc 1 · 1 failed, 2 passed |
| V21 | dev-Erklärung auf `default: medium` (Verfassung sagt **high**) | test_model_ladder | rc 1 · 1 failed, 9 passed |
| V22 | die wiederhergestellte `behalten`-Regel aus dev §11 wieder gelöscht | `test_shortening_net.py::test_no_section_of_a_pinned_instruction_file_disappears_unnoticed` | rc 1 · 1 failed |
| V23 | der `ladder`-Block in `cli.py` nennt einen Nachbarbefehl in einem Code-Span | `test_hooks.py::test_every_span_that_presents_the_command_surface_names_all_of_it` | rc 1 · 1 failed |

V19 ist die Gegenprobe zur Auftragsformulierung: „weekly" in die README pflanzen macht **nicht** rot
— und soll es nicht, `test_radar_trigger` erklärt das in seinem Modul-Docstring (Kadenz ≠
Mechanismus-Behauptung). Rot wird erst ein Satz, der einen Mechanismus behauptet (V18/V20). Die
Behauptung des Readers deckt sich also mit seinem Verhalten.

V23 bestätigt die Angabe aus 2 (i) des Protokolls: der eingefügte `cli.py`-Kommentar ist tatsächlich
an diesem Tripwire hängengeblieben und die Erklärung im Kommentar stimmt.

### Eigener Drei-Kit-Pilot als PROZESS (`rig/pilot.py`, `rig/pilot.log.json`)

Je Kit ein selbstgebautes, scaffold-förmiges Projekt (eigener HOME-Store mit dem Kit + Tiers-Tabelle,
`.claude/team_kit_roles.txt`, echte Rollen-Definitionen), Lease durch den Kernel, Spawn durch das
**gelieferte** `gate_dispatch.py` als echter Prozess.

| Kit | Top | Messung |
|---|---|---|
| dev-team | fable | architect (pin lead) → **fable**/xhigh; designer+QA → **opus**; builder (pin worker) → **sonnet**; PM (pin fable, class planning) → **fable**. Aufstieg backend-developer: sonnet → opus → fable → fable. Hook ohne `model` **rc 2**, mit der Sprosse **rc 0**. |
| research-team | fable | methodologist → **fable**/high (RQ `class: normal`); reviewer + auditor → **opus**; researcher → **sonnet**; Aufstieg sonnet → opus → fable → fable. Hook rc 2 / rc 0. |
| office-team | opus | **keine** Rolle über opus außer office-developer (pin lead → **opus**, Aufstieg → **fable**, `top fable` aus der Ausnahme); office-manager → **opus**; auditor → **opus**; alle übrigen → **sonnet**; filing pair effort **low**; Aufwand durchgehend **medium**, weil `PROC` kein `class` trägt (BUG-0252/H170 bestätigt). Hook rc 2 / rc 0. |

Gemessene stderr-Zeile des Hooks (dev, ohne `model`):
```
… the spawn names no model, so the child would run on the role's own pin (worker) -- the climb the
state derived would not happen (DEC-0077 (2), DEC-0034). Remedy: pass `model: fable` …
```

### Kantenfälle des Lesers (`rig/edge.py`) — siehe F4

Zusätzlich gemessen: `rungs` in umgekehrter Reihenfolge (`[fable, opus, sonnet]`) wird von
`_valid_ladder` **akzeptiert** (die Reihenfolge ist die Erklärung, nichts prüft sie) — für
gelieferte Kits schließt das aber `test_the_shipped_declarations_say_what_the_decisions_decided`
(`assert ladder["rungs"] == ["sonnet","opus","fable"]` für **jedes** Kit-Verzeichnis, also auch für
ein viertes). Kein Befund.

### Verweigerungssätze, die ich gelesen habe

* Kit ohne `ladder.yaml`: »kit 'bare-kit' declares no model ladder: there is no ladder.yaml in its
  store copy at … (DEC-0078 (4)). Remedy: ship ladder.yaml beside the kit's constitution …« —
  nennt Datei, Kit, Entscheidung und Abhilfe.
* Unbekannter Sprossenname: »gives class 'qa' the start 'haiku', which is neither `top`, `pin` nor
  one of its rungs«.
* Pin, den die Tabelle nicht platziert: »role 'product-designer' pins 'haiku', which is neither a
  rung of kit … (sonnet, opus, fable) nor an alias model_tiers.yaml resolves to one (DEC-0076)«.
* Kit-loses Projekt (dieses Repo), gemessen als Prozess in meiner Kopie:
  `PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory ladder TSK-0121` →
  `{"absent": "no scaffold record (.claude/team_kit_roles.txt) names a kit for this project …"}`
  — bestätigt die `repro`-Zeile von BUG-0253/H171.

### Provider-Übersetzung (gemessen über `gen_provider_artifacts` selbst)

```
fable  claude=fable  codex=gpt-6-astra   places=True  neutral=True
lead   …             codex=gpt-5.6-sol   places=True  neutral=True
worker …             codex=gpt-5.6-terra places=True  neutral=True
opus/sonnet          places=True  neutral=False   (Alias-Ziele, im Kit-Quelltext verboten)
haiku/light/luna     places=False neutral=False
aliases = {lead: opus, worker: sonnet}
```
Kein geliefertes Agent-File trägt ein `codex:`-Overlay (`grep -rln "^codex:" team-kits/*/agents/`
leer) — die AC-3-Overlay-Konsistenz ist also die Tabellenübersetzung, und die stimmt.

---

## Urteil je Akzeptanzkriterium

| AC | Urteil | Begründung (gemessen) |
|---|---|---|
| **AC-1** Trigger | **PARTIAL (offen beim Nutzer)** — kein Befund gegen den Strom, aber **B2** | Mechanismus **nicht gebaut** (`tools/radar_trigger.py` existiert nicht; `mechanism_description()` gibt `None`). Der DEC-Vorschlag `dec-trigger.json` trägt zwei Alternativen mit Messungen und benennt, was **nicht** gemessen wurde (Reboot, abgemeldete Sitzung, der ~9-Minuten-Lauf). Der Test, der eine Zeitplan-Behauptung verweigert, ist gebaut und **kann scheitern** (V18/V20 rot, V19 grün). Restposten: **B2** (drei Sätze in `.claude/hooks/`), **F3** (Zahl). |
| **AC-2** Codex-Bericht / max-vs-ultra | **PARTIAL, ehrlich begrenzt** | Der erste Bericht existiert (`radar/2026-09-05-codex.md`, von Hand). Der *nächste* Bericht durch den Trigger hängt an AC-1. Die Deckenmessung ist **nicht** gemacht: kein Codex-CLI auf diesem Host. **Die Begrenzung ist ehrlich**: `model_tiers.yaml:58-61` behauptet **keine** Decke, sondern nennt den Widerspruch und seine Quelle; BUG-0254/H172 nennt Mechanismus, `repro` (`where.exe codex` → not found), `expected` (beide Werte, beide Modelle, gegen die CLI) und `limits` (das geteilte Vokabular `low|medium|high|xhigh|max` steht auf jeder Herstellerseite, `ultra` käme nur bewusst über das `codex:`-Overlay). Was unmessbar bleibt, steht dort. Triage in `radar/decided.md` war vor der Runde da; F7 ist der einzige Zeiger, der nachzieht. |
| **AC-3** Drei Sprossen (DEC-0076) | **PASS** | Tabelle: `aliases` = lead/worker, `claude` = fable/opus/sonnet, `codex` = astra/sol/terra, kein `light`, kein haiku/luna (oben gemessen). Generator verweigert einen `light`/`haiku`-Pin als **Prozess** mit einem Satz, der DEC-0076 nennt (V16 rot ohne die Nennung, V17 rot bei Rückkehr des Alias). Overlay konsistent. Jeder gelieferte Pin löst auf (`tools/test_model_pins.py` grün in meiner Kopie). Rot-zuerst: B1/B2/B5/R11/R12/M2/M12 im Rig des Umsetzers, V16/V17 in meinem. |
| **AC-4** Preisanker / Watch-Daten (BUG-0092) | **PASS** | Anker gegen `radar/2026-09-05-codex.md` Punkte 1-2 nachgerechnet: astra $10/$50, sol $4/$20 promo / $5/$30 Standard, terra $2/$12 seit 2026-07-30, Sonnet-5 $2/$10 mit `radar/decided.md:17` als Beleg — alle vier stimmen. Nur ein Watch-Datum übrig (2026-11-21, belegt). **Selbst gemessen**: vergangenes Datum unter dem Marker → rot (V13), künftiges → grün (V14); `watch_dates` liest nur den Block (beide Kanten im gelieferten Test). MAINTENANCE-Absatz nennt `capture`, `related_pr`, `radar/decided.md` und BUG-0092. Kleine Ungenauigkeit: der Header schreibt »gpt-6-astra … (GA 2026-09-03)«, während der Quellbericht ausdrücklich »staged rollout, **not settled GA**« misst — PR-0010 selbst nennt es allerdings auch GA. Kein Befund, eine Notiz. |
| **AC-5** Rollout-Linie | **PASS** | Protokoll Abschnitt 8: Stempel → Store-Installation → `update-kit` beim nächsten Sitzungsstart → erste Lease liest `ladder.yaml` **aus dem Store**. Beide Fälle „Pin existiert nicht mehr" gemessen und getrennt: Tabelle kann ihn nicht platzieren (Generator-Satz, Dispatch-Satz) vs. Provider hat ihn zurückgezogen (400/`model_not_found`, Watcher-Pflicht). |
| **AC-6** Eskalationsmechanik | **PASS bis auf die Brief-Hälfte — und die ist ein Auftragswiderspruch** | Alles gemessen (siehe Pilot + Rig): Erklärung je Kit, Leser im Dispatcher, Ableitung aus dem Zustand, Verweigerung ohne Erklärung, Regel 2 mit Schwellenwert `escalation.failed_runs_per_rung: 1` samt DEC-Zeile in **jeder** Erklärung, Regeln 1/3/4/5, Sprosse+Aufwand auf Lease, Header und Task-Item, drei Piloten als Prozess, kein Kit-Namens-Zweig (alle Kernel-Tests laufen gegen erfundene Kits), keine Default-Leiter. **Nicht gebaut: die Anzeige im Session-Brief**, die AC-6 und DEC-0077 (5) ausdrücklich verlangen — `kernel/report.py:227-233` baut die `active_tasks`-Zeile aus `id`/`status`/`assigned_role` und sonst nichts (selbst gelesen). `team-kits/kernel/report.py` steht im **`forbidden_scope` desselben Items**. Der Auftrag verlangt also etwas, das er zugleich verbietet; der Strom hat es korrekt als BUG-0249/H167 plus Nahtzeile behandelt. **Das ist ein Item-Defekt, kein Strom-Defekt** — und für PR-0010 AC-6 bleibt es offen, bis der Merge die eine Zeile schreibt. Weiterer Restposten: der Aufwand wird abgeleitet und gezeigt, nie erzwungen (BUG-0251/H169; die Plattform hat keinen Spawn-Parameter dafür — durch `probe-agent-model-result.json` belegt, die Parameterliste des Agent-Tools ist `description, prompt, subagent_type, model, isolation, run_in_background`). |
| **AC-7** Beschlossen vs. gebaut | **PASS mit B1** | DEC-0034/0047/0076/0077/0078 werden vom Code zitiert (Ladder-Abschnitt in `dispatch.py`, drei `ladder.yaml`, `model_tiers.yaml`-Header, Generator). Die Verfassungsabsätze sagen, was gebaut ist — mit **einer** Ausnahme, **B1** (die Filing-Ausnahme). »open work item« ist aus dem Header raus und der Test dagegen kann scheitern (V15 rot). Die wiederhergestellte `behalten`-Regel steht in dev und research in der jeweils eigenen Schreibweise (dev `narrow-mechanical`, research `narrow/mechanical`) — **absichtlich nicht byte-gleich**, weil das Research-Kit den Bindestrich-Token nie trug; Matrixzeile 43 auf `bewusst geändert` umgestuft (gültige Klassifikation, `test_shortening_net` grün), aber siehe **F5** für die drei Journalzeilen. Die Seam-Sentence für die `harness-*.md`-Pins ist geschrieben und die Dateien sind unangetastet. |

## Urteil je Pflicht 8-10

| Pflicht | Urteil | Messung |
|---|---|---|
| **8** Rot-zuerst in einer Kopie, jede Behauptung gemessen | **PASS** | Ich habe 23 eigene Fälle gefahren (Tabelle oben), je einer pro AC und darüber hinaus, jeweils über die **volle** Suite. Die B1-B5-Rückstellungen des Umsetzers habe ich in eigener Form nachgestellt: B1 ≙ V13/V15/V17 (Tabelle), B2 ≙ V16 (Generator-Satz), B3 ≙ V1/V5/V9/V11 (Kernel-Mechanik), B4 ≙ V18/V20 (Radar-Texte), B5 ≙ V21 (Verfassung gegen Erklärung) — **alle rot**. B3 ist im Rig des Umsetzers nur als *collection error* rot; er sagt das selbst und nennt es die schwächste der 19 Zeilen — meine Ersatzmutationen sind echte assertion failures und schließen die Lücke. |
| **8** DEC-0080 (6): Mutation je NEUEM Leser | **PASS** | 14+12 Zeilen im Umsetzer-Rig, dazu meine 23. Ohne eigene Zeile bleiben nur Test-Hilfsleser (`ladder_paragraph`, `shipped_effort_vocabulary`, `tracked_kit_files`) und `role_pin`, dessen beide Richtungen `test_a_role_without_a_class_and_a_role_without_a_readable_pin_are_refused` und `test_a_pin_that_is_an_alias_resolves_through_the_stores_tiers_table` messen. |
| **8** Ein benannter Test muss scheitern können | **PASS** | Jeder in einem geänderten Kommentar in Backticks genannte Testname löst auf (eigener Skript-Abgleich über alle 2737 `def test_`-Namen des Baums, 18 geänderte Dateien, 0 echte Fehlschläge). Für die zwei Behauptungen, die mir am wichtigsten waren, habe ich die Mutation selbst gefahren: der `cli.py`-Kommentar (V23) und der `classes:`-Kommentar der drei Erklärungen (`test_a_build_order_reaches_the_ladder_only_after_the_phase_its_class_assumes` ist in V1/V5-Läufen mitgelaufen und grün, im Baum vorhanden). |
| **8** Löcher als Kernel-BUG-Items mit `limits` + Modulpräfix | **PASS mit B2** | BUG-0249..0255 und BUG-0260 existieren, alle `related_pr: PR-0010`, alle `status: OPEN`, alle mit `hole_number` H167-H173/H178, alle mit gefülltem `limits`, Zitate mit Modulpräfix (`kernel.dispatch.kit_installation`, `gen_provider_artifacts.providers_from_project_config`, …). Keine Handnummern, keine Dokument-Einträge. **Fehlend: B2.** |
| **8** Lesende Suiten + Suiten, die eine geänderte Regel lesen | **PASS (nachgerechnet)** | Ich habe die Zahlen der Runde selbst nachgemessen, jede für sich, ein pytest gleichzeitig: `test_hooks_v2` **2138 passed** (15:19 min, 05:26→05:41), `test_hooks` **1004 passed, 13 skipped** (16:11 min, 05:41→05:58), `test_approvals_dispatch` **197 passed** (98,94 s), `test_shortening_net` + `test_disposition` **44 passed**, `test_ladder` **33 passed**, `test_model_ladder` + `test_radar_trigger` + `test_model_pins` **18 passed**, `tools/validate.py` »all structural checks passed«, `ruff check .` »All checks passed!«. Alle Zahlen des Protokolls, die ich geprüft habe, stimmen. Die Änderungen an `test_hooks*.py` und `test_approvals_dispatch.py` habe ich Zeile für Zeile diffiert: **Fixture-Anpassungen, keine Abschwächung** — `test_gen_accepts_fable_as_the_top_rung_pin` wird sogar strenger (`assert top != lead`). |
| **8** Host-Regel, Uhr gelesen | **PASS** | Ein pytest gleichzeitig (der einzige Grund, warum ich zwischen 05:26 und 05:58 statisch gearbeitet habe); jeder Lauf mit Timeout; kein Burner. Zeiten oben sind gelesen. |
| **9** Nähte | **PASS** | `cli.py` trägt genau einen Block. Die drei Verfassungen tragen nur Leiter-Absätze, die wiederhergestellte QA-Regel und `ladder` in der §0-Befehlsliste — diffiert, nichts anderes. `team-kits/*/agents/*.md`: **nichts geschrieben** (nicht im Patch), was die vom Umsetzer korrigierte Falschbehauptung des Vorgängers bestätigt. `lead_package_sizes.json` und `constitution_section_pins.json` sind angehängt bzw. neu gestempelt, mit Journalzeilen (siehe F5). README aktualisiert. `settings/settings.json` unangetastet — korrekt, der Trigger registriert keinen Hook. Reach-Naht: drei Piloten (meine eigenen bestätigen sie) und die Suitenliste in Abschnitt 6. |
| **9** Merge-blockierende Naht (skills / project_config) | **PASS, und stärker als eine Nahtzeile** | Die fünf Dateien stehen nicht nur in der Tabelle, sondern in einem **zweiseitigen** Tripwire (`STALE_LADDER_TEXTS`): eine claimende Datei außerhalb der Menge ist rot, eine reparierte Datei **in** der Menge ebenso. Beide Enden im Rig des Umsetzers gemessen (M9/M10). Das ist genau die Antwort auf »ein Merge repariert vier von fünf«. BUG-0250 nennt sieben Dateien (die fünf plus `session_status.py` und `scaffold_team.*`) — die Zahl »five« im Modulkommentar und »seven« im Docstring widersprechen sich **nicht**, sie zählen verschiedene Mengen; ich hatte das zunächst als Befund notiert und nehme es nach dem Lesen von BUG-0250 zurück. |
| **10** Handover | **PASS** | Patch: **28 Dateien, 3035 Zeilen**, **keine** `VERSION`-Hunks, **kein** `project_memory/`-Hunk — selbst gezählt. `git apply --check` gegen frisch ausgechecktes **b7f282e** sauber; nach `git apply` ist der Baum bis auf die drei VERSION-Dateien und das Audit-Log **identisch** mit dem Worktree (`diff -rq`). Stempel 2026.09.06-1 dreimal. Protokoll mit Nahttabelle, Per-AC-Zeilen, Leser-Mutationen, gemessenen Zeilen, Löchern, verworfener Alternative (zwei davon, mit dem „kleineren Weg" je Fall), Suitenliste, provisorischem Stempel und **gelesener** Uhr. Kein Commit, kein Push, keine Store-Installation. |
| **10** Tokens | **NICHT GELIEFERT, ehrlich begründet** | Abschnitt 11: »not instrumented for this stream: the session carries no token meter the agent can read, and a figure written here would be an estimate«. Das ist die richtige Antwort auf eine unmessbare Pflicht — eine erfundene Zahl wäre der teurere Fehler. Der Lead muss die Zahl aus dem Transkript nehmen. |

---

## Ausdrückliche Negativbefunde

### Gemessen — und nichts gefunden

* **`started` wird konsumiert, ohne einen anderen Leser zu brechen.** Grep über `team-kits/kernel/`,
  `team-kits/*/hooks/` und `tools/`: die einzigen Vorkommen sind der Schreibvorgang in
  `dispatch.spawn_outcome` (Zeile 1206) und der `pop` in `count_failed_run_locked` (2554). Weder
  `report.py` noch `board.py` noch ein Schema liest es. Die Docstring-Behauptung hält.
* **Die Prämisse des Zählers hält gegen den Automaten.** `AUTOMATA["TSK"]` hat keine Kante
  `IN_PROGRESS → READY`; der einzige direkte Statusschreiber außerhalb von `transition`
  (`_release_lease_locked`, Zeile 3050-3060) setzt READY **nur** aus `LEASED`, wo noch kein
  `started` steht. Der gelieferte Test leitet das aus `AUTOMATA` ab statt es zu behaupten.
* **Kein Pfad-Ausbruch über den Kit-Namen.** Der Ladder-Leser baut seinen Pfad aus
  `presets.installation()["kit"]`; `_ROLES_HEADER_RX` (`presets.py:68-69`) bindet den Namen an
  `[A-Za-z0-9_-]+` — kein Trenner, kein Punkt. `yaml.safe_load` in `_read_yaml_mapping`.
* **Keine Aufzählung von Kit-Namen im Kernel.** `grep -n "dev-team\|office-team\|research-team"
  team-kits/kernel/dispatch.py` leer; alle Kernel-Tests laufen gegen erfundene Kits.
* **Gespiegelte Dateien byte-gleich.** `team-kits/*/hooks/gate_dispatch.py` dreimal
  `fd1712bf268653ed04b68cff42ab60f1` (md5 selbst gerechnet, die Angabe des Protokolls stimmt);
  `tools/validate.py` (das den Spiegel prüft) grün. Die drei Verfassungen sind keine Spiegel.
* **Der `light`-Rückstand bricht kein Scaffold.** Kein `model_map` einer Kit-Vorlage trägt `light`
  (nur Kommentare, BUG-0250). Ein Projekt, das `light` trägt, bekommt die Generator-Verweigerung mit
  DEC-0076-Satz **bevor** etwas geschrieben wird, bzw. am Dispatch den Satz »neither a rung … nor an
  alias«. Fail-closed mit Abhilfe, kein stiller Durchlass.
* **Die neue Store-Kopplung ist absichtlich und benannt.** Seit dieser Runde verweigert jede Lease
  eines *scaffoldeten* Projekts den Dispatch, wenn der laufende HOME-Store das Kit nicht führt — das
  hat genau die fünf Suite-Tests rot gemacht, die aus einem `tmp_path`-Store installierten und dann
  mit dem echten `~/.claude` leasen wollten. Der Verweigerungssatz sagt es (»a project moved to
  another machine or account needs its kit staged there«), Abschnitt 8 des Protokolls sagt es, die
  Fixtures sind korrekt nachgezogen (kein Assertions-Verlust). Ebenso: eine Lease, die vor dem
  Kit-Update geprägt wurde, wird am Spawn verweigert (»carries no ladder answer«) — mit Abhilfe im
  Satz. Beides fail-closed, beides sichtbar.
* **`STALE_LADDER_TEXTS` misst beide Enden** und der Reader liest beide Vokabulare von den
  gelieferten Dateien statt sie zu buchstabieren (`test_the_retired_ladder_reader_reads_both_
  vocabularies_off_the_shipped_files`, in meinen Läufen grün).
* **`radar/decided.md` wurde nicht angefasst** — korrekt, die sieben `codex-0905-*`-Zeilen standen
  vor der Runde (einzige Ausnahme F7, eine veraltete Absichtsnotiz).

### Nicht gemessen (bewusst offengelassen)

* **Die Vollsuite** — sie gehört zum Merge (DEC-0050 / DEC-0080 (2)), nicht zur Prüfrunde. Ich habe
  die lesenden Suiten und die Suiten nachgerechnet, die eine geänderte Regel lesen; die 13
  Run-3-Suiten, die zwischen Run 3 und Run 4 keine geänderte Datei mehr lasen
  (`test_kernel`, `test_e2e`, `test_parallel_streams`, `test_reference_skills`, `test_report`,
  `test_staging_cli`, `test_board`, `test_research_chain`, `test_review_procedure`,
  `test_backlog_types`, `test_state`, `test_finance_dashboard`, `test_repo_hygiene`) habe ich
  **nicht** wiederholt.
* **`test_repo_hygiene`s bekannter Roter** (BUG-0258/H176, `docs/POST_V2_WISHLIST.md` ohne
  `### H`-Einträge) — vorbestehend bei b7f282e, nicht von dieser Runde verursacht; ich habe die
  Suite nicht gefahren und die Zuordnung nur aus dem Patch geprüft (die Datei ist nicht darin).
* **Die Codex-Aufwandsdecke (`max` vs `ultra`)** — kein Codex-CLI auf diesem Host; ich habe die
  Abwesenheit nicht selbst nachgeprüft, sondern nur, dass die Tabelle keine Decke behauptet und
  BUG-0254 die Grenze trägt.
* **Die Plattform-Messung »der `model`-Parameter überschreibt den Pin«** — ich habe die vom Umsetzer
  aufgezeichneten JSON-Ergebnisse gelesen (`probe-agent-override-result.json` zeigt `modelUsage`
  mit `claude-sonnet-5` für den Elternteil und `claude-opus-5[1m]` für das Kind), aber keinen
  eigenen Spawn gefahren.
* **Ein echter Reboot / eine abgemeldete Sitzung** für Alternative B des Triggers — vom Umsetzer
  ausdrücklich als nicht gemessen benannt; ich habe das nur nachgelesen.
* **`docs/`-Änderungen jenseits von `phase0-disposition.md`** — es gibt keine.

---

## Verdikt

**FAIL** — mit zwei Befunden, die **die Runde blockieren**, weil beide billig sind und beide im
`allowed_scope` bzw. in der Loch-Pflicht des Stroms liegen:

* **B1** — Büro-Verfassung (`AGENTS.md:376-378`) und `office-team/ladder.yaml:11-13` behaupten eine
  `sonnet`-Ausnahme, die die Erklärung nicht führt und der Dispatcher nach einem FAILED-Lauf nicht
  einhält (gemessen: `records-clerk` sonnet → **opus**). Hausregel 3. Fix: ein umformulierter Satz je
  Datei; die Verhaltensfrage bleibt beim Nutzer.
* **B2** — drei Zeitplan-Behauptungen in `.claude/hooks/gate_spawn_needs_item.py:11`/`:74` und
  `.claude/hooks/_harness.py:2849` überleben die AC-1-Bereinigung, werden von keinem Test gelesen,
  und die neu geschriebenen Watcher-Kommentare **zeigen ausdrücklich dorthin**. Da `.claude/hooks/**`
  im `forbidden_scope` liegt, ist der geschuldete Schritt kein Fix, sondern ein **benanntes Loch**
  (`capture BUG --hole` mit Mechanismus, `limits` und dem Zeiger auf `test_radar_trigger.TEXTS`) —
  genau die Behandlung, die BUG-0250 für den analogen Fall bekommen hat. Ein gemessenes Loch, das
  nicht aufgeschrieben wird, ist derselbe Fehler wie ein Kommentar, der verspricht, was der Code
  nicht hat.

**Als benannte Restposten** (nicht rundenblockierend, aber vor dem Merge zu erledigen bzw.
aufzuschreiben): **F3** (die Zahl „twelve runs" in `radar/README.md:19`,
`tools/test_radar_trigger.py:7/141` und `dec-trigger.json`), **F4** (der Endpunkt senkt einen Pin
still; ein Satz in `ladder_for_order` plus Anhang an BUG-0249), **F5** (drei Journalzeilen in
`phase0-disposition.md` nennen eine Kategorie, die die Matrix nicht führt), **F6** („below the rung"
zu eng in drei Verfassungen und der README), **F7** (`radar/decided.md:30`), **F8** (`.ruff_cache`
in zwei Template-Bäumen).

**Ausdrücklich NICHT blockierend, aber offen für PR-0010:** die Brief-Hälfte von AC-6
(BUG-0249/H167). Das ist ein **Widerspruch im Auftrag selbst** — AC-6 verlangt die Anzeige,
`forbidden_scope` verbietet `team-kits/kernel/report.py` —, und der Strom hat richtig entschieden,
die Grenze nicht zu überschreiten. Der Merge schreibt die eine Zeile plus ihren Test, oder AC-6
bleibt offen; ein drittes »bekannt, kommt später« gibt es hier nicht.

Substanz und Messdisziplin des Pakets sind hoch: die Mechanik ist gebaut, aus dem Zustand abgeleitet,
ohne Kit-Namens-Zweig und ohne Default-Leiter, an drei selbst gebauten Piloten als Prozess bestätigt,
und jede Regel hat einen Test, der ohne sie rot wird — ich habe 23 davon selbst rot gesehen, über die
volle Suite statt über ein enges `-k`. Die beiden Blocker sind Prosa gegen Code, nicht Code gegen
Code.
