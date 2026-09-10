# TSK-0130 — Prüfbericht Runde 2 (harness-verifier), Nacharbeit 1 unter DEC-0084

Gemessen 2026-09-06, **09:04–09:33** (Uhr gelesen). Frische Kopien unter
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0130/verify/`: `tree2/` (Worktree ohne `.git`,
danach eigenes `git init` für die `git ls-files`-Tests), `applied2/` (`git archive b7f282e` + Patch),
`base/` (b7f282e), `rig2/` (eigene Rigs: `verify_rig2.py`, `routine_probe.py`, `auditor_probe.py`,
`counts.py`, `which_probe.py`, `extract_routine.py`). Alle Rigs verweigern den Lauf außerhalb ihres
eigenen Verzeichnisses und schreiben binär bzw. mit ausdrücklicher `newline`-Politik. Host-Regel
eingehalten: immer nur ein pytest, jeder Lauf mit Timeout, keine Vollsuite.

---

## BLOCKIEREND

### R2-1 — Das Paket ist nicht im übergebenen Zustand: der Patch trägt eine andere AC-1-Fläche als Protokoll und Rig-Log beschreiben

Zeitstempel, gelesen:

| Artefakt | geschrieben |
|---|---|
| `_round-scratch/TSK-0130/stream-ladders.patch` | **09:03:35** |
| `staging/TSK-0130/dec-trigger-2.json` | 09:11:38 |
| Worktree `tools/radar_routine.py` | **09:14:05** |
| Worktree `tools/test_radar_trigger.py` | **09:19:34** |
| `_round-scratch/TSK-0130/mutation_rig2.log.json` | **09:26:30** |
| `staging/TSK-0130/stream-protocol.md` | **09:28:40** |

`diff -rq applied2 <worktree>` (ohne `.git`, Caches) — der Patch reproduziert den Baum **nicht mehr**;
die Abweichung ist genau die AC-1-Fläche:

```
applied2/.claude/agents/codex-watcher.md      differs
applied2/.claude/agents/radar-watcher.md      differs
applied2/radar/README.md                      differs   3657 B -> 4222 B
applied2/tools/radar_routine.py               differs  10169 B -> 20720 B  (+104 %)
applied2/tools/test_radar_trigger.py          differs  18136 B -> 27108 B  (6 -> 8 Tests)
```
(dazu die drei `VERSION`-Dateien und `project_memory/.audit/hook_events.jsonl`, beide absichtlich
nicht im Patch — kein Befund.)

Im Worktree heißt der Selbststart-Leser inzwischen `live_triggers` und liest `radar/routine.json`;
`test_the_self_start_reader_answers_off_the_registrations` ist **weg** und durch
`test_the_self_start_reader_answers_off_the_recorded_triggers` ersetzt, dazu kamen
`test_the_two_states_of_the_schedule_claim` und
`test_the_cloud_prompt_states_every_duty_the_declaration_names`. Keine dieser Zeilen existiert im
gelieferten Patch (`grep -rn "live_triggers" tree2/` leer).

**Das Protokoll widerspricht sich deshalb selbst**, und zwar an der Stelle, an der AC-1 hängt:

- `stream-protocol.md:257-258` — „`starts_itself`, which is **derived from the registrations**
  (`starts_itself()` reads `.claude/settings.json` for a hook that names this module)" → die
  **Patch**-Fassung;
- `stream-protocol.md:316` — „`starts_itself` is derived from **`radar/routine.json`**, the record
  the LEAD writes" → die **Worktree**-Fassung;
- Nahttabelle Zeile 788 („Until it exists `starts_itself` stays False", Registrierung) gegen Zeile
  790 (`radar/routine.json`);
- Rig-Tabelle des Protokolls führt M20/M21, das Rig-Log sogar M20–M23
  (`live_triggers`, „the cloud prompt", „recorded trigger ids") — **Mutationen an Code, den der
  Patch nicht enthält**. Der Auftrag des Koordinators nennt „rig 2 now 20 lines … M13-M19"; das Log
  hat 24 Zeilen, die Protokolltabelle 22.
- Abschnitt 10 behauptet weiterhin, `git apply` gegen b7f282e reproduziere den Baum (gemessen
  09:02:54). Das stimmte um 09:03 und stimmt seit 09:14 nicht mehr.
- Abschnitt 10 nennt außerdem `dec-trigger.json` als den beim Nutzer offenen Vorschlag; offen ist
  seit 09:11 `dec-trigger-2.json`.

Der Patch ist laut Item **das Paket** („patch = the worktree diff WITHOUT the VERSION hunks"). Wer
ihn misst, misst nicht das, was das Protokoll beschreibt, und umgekehrt. **Das blockiert die Runde**
— nicht wegen eines inhaltlichen Fehlers, sondern weil kein Prüfergebnis zu AC-1 auf einen Zustand
zeigt, den beide Seiten meinen.

**Minimaler Fix:** Patch neu schneiden, Abschnitt 3c/Nahttabelle auf **eine** Fassung ziehen, die
AC-1-Rig-Zeilen gegen den geschnittenen Baum neu fahren, dann erneut übergeben. Alles außerhalb der
fünf Dateien ist zwischen Patch und Worktree **byte-gleich** — meine Urteile zu AC-3…AC-7 und zur
Runde-1-Nacharbeit stehen unabhängig davon.

---

## Befunde gegen den GELIEFERTEN Patch (können durch die neuere Worktree-Fassung erledigt sein — von mir NICHT gemessen)

### R2-2 — `starts_itself` beantwortet „ist es irgendwo registriert", nicht „läuft es ohne Menschen"

`tools/radar_routine.py:95-114` (Patch-Fassung) parst `.claude/settings.json` und prüft dann
`stem in json.dumps(registered.get("hooks") or {})` — eine **Zeichenkettensuche über den
serialisierten Teilbaum**. Gemessen (`rig2/routine_probe.log.json`, 09:12):

```
starts_itself: a SessionStart hook that RUNS the routine                       {"answer": true}
starts_itself: a hook that runs a DIFFERENT file whose name contains the stem  {"answer": true}
starts_itself: a MATCHER string that merely mentions the file                  {"answer": true}
```

Der Docstring sagt „a registration that **names it** — a hook command in the provider's
`settings.json`" und nennt das Lesen ausdrücklich fail-closed für eine unlesbare Datei. Für eine
bloße **Erwähnung** ist es fail-OPEN, und offen ist hier die permissive Richtung: `starts_itself:
true` erlaubt den Texten mehr. Der mitgelieferte Test
`test_the_self_start_reader_answers_off_the_registrations` prüft nur „Kommando startet sie" gegen
„Kommando startet etwas anderes namens `other.py`" — die Richtung, die der Docstring verneint
(Erwähnung ≠ Start), fehlt.

Zweite Hälfte, und das ist die eigentliche Frage: **eine `SessionStart`-Registrierung — genau die
Naht, die das Protokoll an G5-1 übergibt — kippt das Feld auf True, obwohl eine Sitzung nach wie vor
die Handlung eines Menschen ist.** Danach lässt
`test_no_text_claims_a_schedule_the_repo_does_not_build` einen Satz durch, der einen Zeitplan
behauptet und **niemanden** als Starter nennt („A mechanism that DOES start itself → naming it is
enough"). Gemessen, Fall W6: mit Registrierung **und** dem Satz
„The scan is scheduled weekly by tools/radar_routine.py." lief dieser Test **grün**; rot wurde nur
`test_the_self_start_reader_answers_off_the_registrations` mit seiner Schlusszeile
(„something now registers the radar routine — the texts in %s may say so, and this assertion is the
place that noticed"). Gegenprobe W7 (derselbe Satz **ohne** Registrierung): dieser Test rot.

Das ist ein tragbarer Entwurf — die Schlusszeile holt einen Menschen in die Schleife, statt still zu
kippen — aber der Feldname und die Testverzweigung behaupten mehr, als das Lesen trägt.
**Minimaler Fix:** den Pfad des Kommandos auflösen und mit dem Modul vergleichen statt einer
Teilzeichenkette, und die Verzweigung an „startet ohne Sitzung" hängen, nicht an „registriert".
Der Worktree hat diesen Leser inzwischen durch `live_triggers(record)` ersetzt; ob das die Frage
löst, habe ich **nicht** gemessen (R2-1).

### R2-3 — Der neue Text-Leser prüft die ANWESENHEIT des Wortes „climb", nicht die Aussage

`tools/test_model_ladder.py::test_a_text_that_names_an_excepted_role_says_whether_its_rung_still_climbs`
bildet `said = any(re.search(r"climb", part, re.IGNORECASE) …)` über die Sätze, die den Rollennamen
tragen, und vergleicht `said == still_climbs`. Ein Satz, der den Aufstieg **verneint**, enthält das
Wort ebenfalls.

Gemessen, Fall W1: der Absatz der Büro-Verfassung auf
„…and a FAILED run **never climbs** its rung above sonnet, because the exception holds." geändert,
während die Erklärung den Aufstieg gibt → **rc 0, 46 passed**. Der Text lügt, der Leser schweigt.

Dass der Leser den Runde-1-Defekt trotzdem fängt, habe ich getrennt gemessen (W2b: die
Runde-1-Formulierung „keeps `sonnet`/`low` as the named exception" **vollständig** eingesetzt, sodass
kein `climb` mehr in einem Satz mit dem Rollennamen steht → **rot**, genau in diesem Test). Der
Leser deckt also den Fall ab, für den er geschrieben wurde, und die Nachbarschreibweise nicht.
**Minimaler Fix:** die Verneinung mitlesen (`\bno(?:t|ver)?\b[^.;]{0,40}climb` als Gegenmuster) oder
die Aussage aus einer festen Wendung ziehen, statt aus dem bloßen Vorkommen.

---

## Nicht blockierende Befunde

- **R2-4** `stream-protocol.md` Abschnitt 6: „`test_repo_hygiene` **1 failed**, 30 passed".
  Gemessen auf dem gelieferten Baum: **2 failed, 29 passed** —
  `test_every_hole_has_a_row_in_the_summary_and_every_row_has_a_hole` **und**
  `test_the_known_out_of_scope_trace_is_still_the_only_exception`. **Beide** sind vorbestehend: auf
  einer frischen `git archive b7f282e`-Kopie ebenfalls `2 failed, 29 passed`. Ursache ist bei beiden
  dieselbe (`docs/POST_V2_WISHLIST.md` ohne `### H`-Einträge, BUG-0258/H176), also kein neues Loch —
  aber die Suitentabelle unterschlägt einen roten Test.
- **R2-5** `--run` fragt `--due` nicht und überschreibt den Tagesbericht stillschweigend. Gemessen
  (`rig2/routine_probe.log.json`, zweimal `--run codex-watcher` am selben Tag, `subprocess.run`
  innerhalb des geladenen Moduls durch einen Rekorder ersetzt, der die argv in eine Datei schreibt):
  ```
  attempt 1: rc 0, new_reports ["2026-09-06-codex"], still_due ["radar-watcher"]
  attempt 2: rc 0, new_reports [],                   still_due ["radar-watcher"]
  what the routine handed to the shell: 2 invocations,
    ["claude","-p","Run your weekly scan now …","--agent","codex-watcher","--model","sonnet","--output-format","json"]
  radar/ after two runs on one day: ["2026-08-31-codex.md","2026-09-06-codex.md"]
  ```
  Der zweite Lauf startet den Watcher erneut (rund 130 k Token, ~4 min laut dem echten Lauf der
  Runde) und produziert nichts Neues. `new_reports: []` sagt es hinterher; eine Warnung vorher gibt
  es nicht. **Minimaler Fix:** eine Zeile in `--run`, die sagt, dass in dieser Periode schon ein
  Bericht steht, und den Lauf nur auf ausdrücklichen Wunsch fortsetzt.
- **R2-6** Zahlen in `dec-trigger-2.json` (dem Dokument, auf dem der Nutzer entscheidet):
  „every one of the **14** reports so far" — gemessen **15** (der eigene End-to-End-Lauf der Runde
  hat den fünfzehnten geschrieben); „every week of the last **nine**" — gemessen **10** ISO-Wochen
  (2026-W27 bis 2026-W36). Die tragende Aussage ist dagegen **wahr** und habe ich nachgerechnet:
  zwischen erstem und letztem Bericht gibt es **keine** Woche ohne Bericht (`rig2/counts.py`:
  „weeks with NO report between first and last: none"), also deckt Option A jede bisher gelebte
  Woche.
- **R2-7** `radar/2026-09-06-codex.md:4-5` — „every 2026-09-05 codex-watcher finding already has a
  decided line (**six accepted, two rejected**)". Gemessen in `radar/decided.md`: **7** `codex-0905-`
  Zeilen, **5** `accept`, **2** `reject`. Text des Watchers, vom Strom mitgeliefert.
- **R2-8** `--due` zählt **ISO-Wochen**, nicht Tage — richtig so und im `--describe` als
  `"period": "ISO week"` deklariert, aber die Auftragsfrage „6 Tage vs. 8 Tage" hat keine Antwort in
  Tagen. Gemessen: ein **6** Tage alter Bericht (2026-09-08, heute 2026-09-14) ist **fällig**, ein
  **3** Tage alter (2026-09-07, heute 2026-09-10) ist es **nicht**; 6 und 8 Tage alt liefern beide
  „fällig", wenn beide in der Vorwoche liegen. Kein Befund, eine Klarstellung: „weekly" in der Prosa
  heißt „einmal je ISO-Woche", nicht „alle sieben Tage".

---

## Angriff auf den FIX — was ich selbst gemessen habe

### Eigenes Mutationsrig (`rig2/verify_rig2.log.json`), volle Suiten, kein enges `-k`

| Fall | Mutation | Auswahl | Ergebnis |
|---|---|---|---|
| W1 | Verfassung **verneint** den Aufstieg, Erklärung gibt ihn (Wort „climb" bleibt) | ladder+model_ladder | **rc 0, 46 passed — BEFUND R2-3** |
| W2b | Verfassung vollständig zurück auf die Runde-1-Formulierung (kein „climb" mehr) | ladder+model_ladder | rc 1 · `test_a_text_that_names_an_excepted_role_says_whether_its_rung_still_climbs` |
| W3 | Erklärung pinnt `records-clerk: top: sonnet` (die offene Nutzerfrage beantwortet) | ladder+model_ladder | rc 1 · 3 failed: `…_decisions_decided`, `…_filing_pair_starts…_still_climbs`, `…_says_whether_its_rung_still_climbs` |
| W4 | Kit-Endpunkt kappt nicht mehr nach unten (F4 rückgängig) | ladder+model_ladder | rc 1 · `test_a_top_below_a_pin_lowers_it_and_the_answer_says_so`, `…_climb_stops_there` |
| W5 | das `why` nennt den Pin nicht mehr (Sichtbarkeitshälfte von F4) | ladder+model_ladder | rc 1 · `…_lowers_it_and_the_answer_says_so`, `…_header_and_the_task_carry…` |
| W6 | `SessionStart`-Registrierung **plus** starterloser Zeitplan-Satz | radar_trigger | rc 1 — aber **nur** `…_answers_off_the_registrations`; die Textprüfung ließ den Satz durch (**R2-2**) |
| W7 | Kontrolle: derselbe Satz **ohne** Registrierung | radar_trigger | rc 1 · `test_no_text_claims_a_schedule_the_repo_does_not_build` |
| W8 | schlichter Zeitplan-Satz in `radar/README.md` (Runde-1-Regression) | radar_trigger | rc 1 · derselbe Test |
| W9 | nur eine **Kadenz** („weekly, once a week") | radar_trigger | **rc 0 — korrekt grün** |
| W10 | `starts_itself` als Konstante **True** | radar_trigger | rc 1 · `…_answers_off_the_registrations` |
| W11 | `starts_itself` als Konstante **False** | radar_trigger | rc 1 (meine Erwartung „grün" war falsch — beide Konstanten werden gefangen, das ist die richtige Antwort) |
| W12 | `due()` zählt jeden datierten Bericht als Lauf jedes Watchers | radar_trigger | rc 1 · `test_the_routine_counts_a_run_per_watcher_and_per_period` |
| W13 | die Erklärung vergisst einen Watcher | radar_trigger | rc 1 · 2 failed (Textprüfung + Zählprüfung) |

### Die Auditor-Kette, auf einem Piloten, den ICH gebaut habe (`rig2/auditor_probe.log.json`, 09:21:00 → 09:21:14)

Eigener HOME-Store (Kopie von `tree2/team-kits`), Projekt über die **ausgelieferten** Installer
(`init_project_memory.ps1` rc 0 „21 created", `scaffold_team.ps1 -Team dev-team -Preset team` rc 0),
Marker über `clear_handover_marker.py` gelöscht, danach jeder Schritt als Prozess:

| Frage | gemessene Antwort |
|---|---|
| deklariert? | `session_status.py` auf **SessionStart** registriert; `_routine.py` trägt `AUDIT_ROLE = "project-auditor"`; `.claude/agents/project-auditor.md` installiert |
| fällig gemeldet? | **ja**, wörtlich: `ROUTINE DUE (2026-08-31): the project-auditor has not run in 2026-W36 (last run in this project's event log: none)` |
| durch einen Lauf gelöscht? | **ja** — ein Datensatz über das projekteigene `notify_agent_events.py` (rc 0, 1 Logzeile) → keine ROUTINE-Zeile mehr |
| kommt sie nach dem Takt zurück? | **ja** — Datensatz acht Tage zurückgesetzt: `ROUTINE DUE (2026-08-31): … (last run in this project's event log: 2026-08-29T09:21:09)` |
| darf der PM sie starten? | **nein.** `request-approval routine PR-0001` → rc 2, `invalid choice: 'routine' (choose from 'acceptance', 'delivery', 'document_proposal', 'document_revision', 'filing_correction', 'filing_rule', 'hole_exception', 'kit_update', 'plan', 'preset', 'push', 'scope')`; dasselbe für `analysis` **und** (von mir ergänzt) für `audit` |
| was geht? | nur ein gewöhnlicher Auftrag — `create-task --help` führt `--allowed-scope` als Pflicht, und ohne es: `error: the following arguments are required: --derives-from, --acceptance-ref, --allowed-scope` |

Das ist **genau** die Kette und die Grenze von BUG-0266/H184, unabhängig nachgestellt; der dort
zitierte Test `tools/test_routine_feed.py` existiert im Baum (AC-3 des Items löst auf).

### Weitere eigene Messungen

- **Patch:** 31 Dateien, **3676** Zeilen (`wc -l`), **0** `VERSION`- und **0** `project_memory/`-Hunks,
  `git apply --check` gegen frisch ausgechecktes b7f282e **rc 0**, nach `git apply` deckungsgleich mit
  `tree2` bis auf VERSION und Audit-Log. `allowed_scope` eingehalten; `.claude/settings.json` und
  `.claude/hooks/_harness.py` **byte-gleich mit b7f282e**. `team-kits/*/hooks/gate_dispatch.py`
  dreimal md5 `fd1712bf268653ed04b68cff42ab60f1`. Stempel **2026.09.06-2** dreimal.
  `.ruff_cache` nirgends mehr (F8 erledigt).
- **Suiten** (je ein pytest, mit Timeout): `test_ladder` + `test_model_ladder` +
  `test_radar_trigger` + `test_model_pins` + `test_routine_feed` = **86 passed** (43,5 s);
  `test_shortening_net` + `test_disposition` + `test_context_budget` + `test_repo_hygiene` =
  **2 failed, 115 passed** (beide Roten vorbestehend, s. R2-4); `tools/validate.py` grün;
  `ruff check .` grün. `test_hooks`, `test_hooks_v2`, `test_approvals_dispatch` sind zwischen Runde 1
  und 2 **byte-gleich** (`diff -q`), in Runde 1 von mir mit 1004+13 / 2138 / 197 gemessen — nicht
  wiederholt.
- **`--describe`** auf dem gelieferten Baum: `"reports": 15`, `"starts_itself": false`,
  `"cadence": "weekly"`, `"period": "ISO week"` — die Zahl ist abgeleitet, in keiner Prosa mehr
  (`grep` nach „twelve runs / 14 reports / 12 claude reports" im Baum: leer). **F3 erledigt.**
- **`--run` mit unbekanntem Watcher:** `unknown watcher 'nope' -- the routine declares
  codex-watcher, radar-watcher`, rc 1, kein Prozess gestartet.
- **End-to-End-Lauf** (`routine_end_to_end.json`): `codex-watcher`, 07:45:18 → 07:49:04, rc 0,
  `new_reports ["2026-09-06-codex"]`, `still_due []`. Die Datei existiert (105 Zeilen) und sagt in
  ihren ersten Absätzen selbst, was sie gestartet hat und dass die Routine keinen Lauf schuldete.
- **Der echte Shell-Schiedsrichter ließ sich hier nicht bauen**, und das ist selbst eine Messung
  (`rig2/which_probe.py`): `shutil.which` findet ein zuerst auf `PATH` gelegtes `claude.CMD`,
  `subprocess.run(["claude","--version"])` liefert aber das **echte** `claude.exe 2.1.258` und
  schreibt kein Shim-Log — Windows `CreateProcess` hängt nur `.exe` an. Für R2-5 habe ich deshalb
  `subprocess.run` **im geladenen Modul** durch einen Rekorder ersetzt, der die argv in eine Datei
  schreibt; was die Routine der Shell übergibt, ist damit gemessen, die Shell selbst nicht erneut.

---

## Urteil je Akzeptanzkriterium

| AC | Urteil |
|---|---|
| **AC-1** Trigger | **FAIL — wegen R2-1, nicht wegen der Substanz.** DEC-0084 ist inhaltlich befolgt: zuerst gemessen (Auditor-Kette, drei Plattform-Kandidaten mit je einer Sonde), dann die Routine in der Auditor-Form gebaut, ein End-to-End-Lauf, die Texte auf das Gemessene gezogen, ein zweiseitiger Leser dahinter, und die gemessene Grenze („nichts auf diesem Host übersteht eine Woche ohne Sitzung UND schreibt in dieses `radar/`") plus ein zweiter Vorschlag statt eines stillen Option-B-Baus. **Aber**: die gelieferte Fläche ist eine andere als die beschriebene. AC-1 ist erst prüfbar, wenn Patch, Protokoll und Rig-Log auf denselben Baum zeigen. Zusatzbefunde gegen die gelieferte Fassung: R2-2, R2-5, R2-6, R2-8. |
| **AC-2** Codex-Bericht / max-vs-ultra | **PARTIAL, ehrlich begrenzt — Fortschritt gegenüber Runde 1.** Der *nächste* Bericht existiert jetzt und wurde **vom Mechanismus** erzeugt (`--run`, 07:45→07:49, rc 0, `radar/2026-09-06-codex.md`); der Bericht sagt selbst, wer ihn gestartet hat. Die Deckenmessung bleibt aus (kein Codex-CLI), sauber begrenzt in `model_tiers.yaml` (keine Decke behauptet) und BUG-0254/H172 — und `radar/decided.md:30` zeigt seit dieser Runde dorthin statt eine Messung zu versprechen (**F7 erledigt**). Kleine Ungenauigkeit im neuen Bericht: R2-7. |
| **AC-3** Drei Sprossen | **PASS** — unverändert gegenüber Runde 1 (Tabelle, Generator-Verweigerung mit DEC-0076, Overlay, jeder Pin löst auf); `test_model_ladder` 11 passed, `test_model_pins` 5 passed in meiner Kopie. |
| **AC-4** Preisanker / Watch-Daten | **PASS** — unverändert; Watch-Datum-Leser und MAINTENANCE-Route in Runde 1 von mir rot-zuerst gemessen (V13/V14/V15). |
| **AC-5** Rollout | **PASS** — unverändert. |
| **AC-6** Eskalationsmechanik | **PASS bis auf die Brief-Hälfte.** B1 ist geschlossen und **gebaut statt behauptet**: die Büro-Verfassung (`AGENTS.md:376-380`) und `office-team/ladder.yaml:9-17` sagen jetzt „starts on its `sonnet` pin … a FAILED run climbs its rung to **opus**", und zwei neue Leser messen es — `test_the_filing_pair_starts_on_its_pin_at_low_effort_and_still_climbs` gegen den **Kernel** und die **ausgelieferte** Erklärung (W3 rot), `test_a_text_that_names_an_excepted_role_says_whether_its_rung_still_climbs` gegen die beiden Texte (W2b rot; Blindstelle R2-3). F4 ist dokumentiert **und** getestet (W4/W5 rot). Offen bleibt allein die Anzeige im Session-Brief (BUG-0249/H167) — der Auftragswiderspruch aus Runde 1 (`report.py` steht im `forbidden_scope` desselben Items) besteht unverändert. |
| **AC-7** Beschlossen vs. gebaut | **PASS.** Die beiden Sätze, die Runde 1 als falsch gemessen hatte, sind korrigiert: die Filing-Ausnahme (B1) und „refuses a spawn that would run below the rung" → „refuses **any spawn whose `model` is not the rung, a higher one included**" in allen drei Verfassungen und der README (**F6 erledigt**). Die drei Journalzeilen nennen jetzt die deklarierte Kategorie `bewusst geändert` und der Office-Eintrag sagt ausdrücklich, dass Zeile 43 ihn nicht betrifft (**F5 erledigt**). |

## Urteil je Pflicht 8–10

| Pflicht | Urteil |
|---|---|
| **8** rot-zuerst, jede Behauptung gemessen, Mutation je Leser, Löcher als Kernel-Items, Host-Regel, Uhr | **PASS mit R2-3 als benannter Blindstelle.** 13 eigene Mutationsfälle, 12 davon wie erwartet, einer (W1) als Befund; die Auditor-Kette unabhängig auf eigenem Piloten nachgestellt. **BUG-0264/H182** (meine Runde-1-Feststellung B2) und **BUG-0266/H184** (die Nutzerfrage) sind über den Kernel erfasst, tragen `limits`, Modulpräfixe (`test_radar_trigger.TEXTS`, `_harness`, `dispatch._covering_routine_apr`) und eine `repro`-Zeile, die ich nachgefahren habe. Der in BUG-0266 AC-3 genannte `tools/test_routine_feed.py` existiert. |
| **9** Nähte | **PASS.** `.claude/settings.json` und `.claude/hooks/**` byte-gleich mit b7f282e; `team-kits/*/agents/*.md` unangetastet; Records und Journal fortgeschrieben; die Registrierung ist als Naht benannt statt still gesetzt. |
| **10** Handover | **FAIL — R2-1.** Der Patch reproduziert den beschriebenen Baum nicht mehr; Protokoll und Rig-Log beschreiben zwei verschiedene Fassungen desselben Lesers. Alles Übrige der Pflicht ist erfüllt (kein Commit, kein Push, keine Store-Installation; Kopien ohne `.git`; Stempel gesetzt; Uhr gelesen; Tokens weiterhin ehrlich als nicht instrumentiert ausgewiesen). |

---

## Ausdrückliche Negativbefunde

**Gemessen, nichts gefunden:** `.claude/settings.json`, `.claude/hooks/_harness.py` und die Gates
byte-gleich mit b7f282e · `gate_dispatch.py` dreifach identisch · `allowed_scope` des Patches
eingehalten, keine VERSION- und keine `project_memory/`-Hunks · `git apply` gegen b7f282e sauber ·
`validate.py` und `ruff` grün · die Zählung „reports" ist abgeleitet und in keiner Prosa mehr ·
`--run` mit unbekanntem Watcher wird mit Satz und rc 1 verweigert · `due()` unterscheidet die beiden
Watcher am Suffix und zählt je ISO-Woche (W12 rot ohne diese Unterscheidung) · die beiden
suffixlosen Altberichte klären niemandes Pflicht · beide Konstanten-Richtungen von `starts_itself`
werden gefangen (W10/W11) · die neuen Ladder-Leser lesen die **ausgelieferte** Erklärung statt einer
Kopie · `test_hooks`, `test_hooks_v2`, `test_approvals_dispatch` zwischen den Runden unverändert.

**Nicht gemessen:** die neuere Worktree-Fassung der fünf AC-1-Dateien (`live_triggers`,
`radar/routine.json`, `cloud_prompt`, die drei neuen Tests) — sie ist nicht Teil des gelieferten
Patches, und R2-2 kann durch sie erledigt sein · ein zweiter echter `claude -p`-Watcherlauf (der
End-to-End-Lauf des Umsetzers ist über die geschriebene Datei und das Log geprüft, nicht wiederholt)
· die Vollsuite und die 13 Suiten, die zwischen Runde 1 und 2 keine geänderte Datei mehr lasen ·
`RemoteTrigger`/Session-Cron-Sonden (nur die Logs gelesen, keine eigene Sonde: eine Cloud-Routine im
Konto des Nutzers ist eine Nebenwirkung, die niemand freigegeben hat) · die Codex-Aufwandsdecke.

---

## Verdikt

**FAIL.**

**Blockierend:** **R2-1** — der Patch (09:03:35) trägt nicht die AC-1-Fläche, die Protokoll (09:28:40)
und Rig-Log (09:26:30) beschreiben; fünf Dateien wurden nach dem Schnitt weitergeschrieben,
`tools/radar_routine.py` hat sich verdoppelt, `test_the_self_start_reader_answers_off_the_registrations`
existiert im Worktree nicht mehr, und das Protokoll beschreibt an zwei Stellen zwei verschiedene
Fassungen desselben Feldes. Vor einer AC-1-Abnahme: Patch neu schneiden, Abschnitt 3c und die
Nahttabelle auf eine Fassung ziehen, die AC-1-Rig-Zeilen gegen den geschnittenen Baum neu fahren.

**Als benannte Restposten** (gegen die gelieferte Fassung gemessen, ggf. durch die neuere erledigt):
**R2-2** (`starts_itself` liest „registriert", nicht „startet ohne Menschen"; Teilzeichenkette statt
aufgelöstem Pfad), **R2-3** (der Text-Leser prüft die Anwesenheit des Wortes „climb", nicht die
Aussage — eine Verneinung passiert ihn), **R2-4** (ein roter Test in der Suitentabelle unterschlagen),
**R2-5** (`--run` fragt `--due` nicht und überschreibt still), **R2-6/R2-7** (drei Zahlen),
**R2-8** (ISO-Woche statt Tagen, nur klarzustellen).

**Weiterhin offen für PR-0010, nicht für diesen Strom:** die Brief-Hälfte von AC-6
(BUG-0249/H167) — der Auftragswiderspruch aus Runde 1 besteht unverändert.

Die Nacharbeit selbst ist gut: **beide blockierenden Befunde der Runde 1 sind geschlossen** — B1
nicht als korrigierter Satz, sondern als zwei Leser, die den Satz gegen Kernel und Erklärung halten
(W2b, W3 rot), B2 als Kernel-Loch mit Kette und Grenze (BUG-0264/H182) — und alle sechs Restposten
F3–F8 sind erledigt. Die Frage des Nutzers nach dem Projekt-Auditor ist beantwortet, und ich habe die
Antwort auf einem eigenen Piloten Wort für Wort reproduziert. Was diese Runde scheitern lässt, ist
nicht das Gebaute, sondern dass das Übergebene und das Beschriebene auseinanderliegen.
