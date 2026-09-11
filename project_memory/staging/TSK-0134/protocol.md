# TSK-0134 — Das Watcher-Duo (PR-0011, G6), Umsetzer-Protokoll

Basis: `feat/harness-v2` @ `5048c18`, Haupt-Checkout `C:/Offline Repos/AgentAndSkills`. Arbeitsbaum
beim Start nicht sauber (`project_memory/**` Kernel-Schreibungen des Leads). Ein Schreiber, ein
Baum (`DEC-0087` (1)). Umsetzer: Opus 5, effort high (`DEC-0091` (1)). Rot-zuerst-Messungen in
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0134/` (Kopie **ohne** `.git`). Kein Commit, kein
Push, keine Installation, keine Routine aus dieser Sitzung angelegt (`DEC-0090` (5)).
**Jede Uhrzeit ist gelesen, keine hochgerechnet.**

Gestempelt von diesem Protokollskript: **2026-09-11 02:31:25** (lokale Uhr, gelesen vom schreibenden
Prozess). Rundenbeginn = mtime der ersten Rig-Datei: **2026-09-11 01:59:43**.

---

## 0. Der verworfene Weg, in einer Zeile (FR-0084)

**Verworfen:** `tools/gen_provider_artifacts.py` als eigener Repo-Generator anzulegen — der Pfad,
den `expected_outputs` (RUNGS) zuerst nennt. **Grund, gemessen:** `tools/` ist für jeden
`python tools/<script>.py` schon vor der ersten Zeile `sys.path[0]`, und `tools/validate.py`
schiebt es in Zeile 26 noch einmal vor das `team-kits` aus Zeile 25 — eine Datei dieses Namens
unter `tools/` verdeckt also die des Kits für den Validator, der in Zeile 31 vier Namen daraus
importiert.

    Baseline (Kopie ohne .git):  validate.py: all structural checks passed.
    mit einem 5-Zeilen-Stub in tools/gen_provider_artifacts.py:
      File ".../tree/tools/validate.py", line 31, in <module>
        from gen_provider_artifacts import (  # noqa: E402
      ImportError: cannot import name 'load_tiers' from 'gen_provider_artifacts'
        (C:\...\_round-scratch\TSK-0134\tree\tools\gen_provider_artifacts.py)

Kein einziger struktureller Check lief danach. `tools/test_hooks.py -k neutral_model_values` blieb
dagegen grün (1 passed) — der Test schiebt `team-kits` im Testkörper selbst auf Index 0, die Suite
sieht die Kollision also auch nicht. Das ist die neue Lücke **H192 / BUG-0276**.

**Der kleinere Weg**, den das Item als zweite Möglichkeit nennt, ist deshalb gewählt und um eine
Stufe besser gebaut als „hand-written pin": der Generator existiert, er liegt nur in
`tools/radar_routine.py` (`overlay_text`, `write_overlays`, `--write-overlays`), lädt das
Kit-Modul **über den Pfad** (`_kit_generator`) und liest Modell-Id, Effort-Schlüsselname und die
Verweigerung eines nicht platzierbaren Pins aus `team-kits/model_tiers.yaml` durch dessen eigene
Leser. Nichts ist zweimal getippt. **Was der kleinere Weg NICHT deckt:** es gibt weiterhin keinen
allgemeinen Provider-Generator für dieses Repo — nur die zwei Watcher-Overlays sind abgeleitet,
jede weitere `.codex/agents/*.toml` wäre wieder handgepflegt. Genannt, nicht geschlossen.

---

## 1. Dateitabelle

| Datei | Art | Was |
|---|---|---|
| `.claude/agents/claude-watcher.md` | `git mv` aus `radar-watcher.md` + Inhalt | `name:`, `model: opus`, `effort: high`, Runner-Zeile, Berichtsname, Beschreibung |
| `.claude/agents/codex-watcher.md` | geändert | Gegenverweis, `model: opus`, `effort: high`, Runner-Zeile, Berichtsname, Beschreibung |
| `.codex/agents/claude-watcher.toml` | `git mv` aus `radar-watcher.toml` + **generiert** | `model = "gpt-5.6-sol"`, `model_reasoning_effort = "high"`, Instruktionen = Definition mit getauschter Runner-Zeile |
| `.codex/agents/codex-watcher.toml` | **generiert** | dito |
| `radar/README.md` | umgeschrieben | vier Routinen, vier Berichte, wer wo läuft, App-offen-Grenze, Nachhollauf, „radar/ behält seinen Namen" |
| `radar/routine.json` | neue Form | `routines: [{watcher, runner, kind, schedule_as_told, source, path, first_report, last_report}]` |
| `tools/radar_routine.py` | umgeschrieben | `RUNNERS`, `routine_plan`, `report_name`/`report_runner`, `due` pro Routine, `live_routines`/`starts_itself`, `--write-overlays`, `--describe` mit vier Instruktionstexten |
| `tools/test_radar_trigger.py` | umgeschrieben + 7 neue Tests | s. Abschnitt 2 |
| `docs/POST_V2_WISHLIST.md` | Zeile H192 | vom Kernel geschrieben (`migrate-holes --reindex`, „index rewritten from the store: 182 hole(s)") |
| `project_memory/bugs/active/BUG-0276.yaml` | Kernel `capture BUG --hole` | H192, `related_pr: PR-0011` |
| `project_memory/staging/TSK-0134/` | neu | dieses Protokoll + `tsk-0134.patch` |

`tools/gen_provider_artifacts.py` und `tools/test_gen_provider_artifacts.py` (beide im
`allowed_scope`) sind **nicht** angelegt — Grund in Abschnitt 0, gemessen.

`python tools/bump_kit_version.py` → `dev-team: unchanged (2026.09.06-1)`,
`office-team: unchanged (2026.09.10-1)`, `research-team: unchanged (2026.09.06-1)`.
**Gemessen und nicht angenommen:** `git diff -M 5048c18 --stat -- team-kits` ist leer, keine
berührte Datei geht in einen Kit-Hash ein, kein VERSION-Hunk im Patch.

---

## 2. Rot-zuerst (jede Zeile mit der Fehlerzeile des Schiedsrichters)

Rig: `.../TSK-0134/rig/red_first.py` — kopiert den Baum ohne `.git`, mutiert **eine** Stelle,
fährt den benannten Test, stellt die Datei aus dem Haupt-Checkout wieder her. Das Rig verweigert
den Start außerhalb seines eigenen Verzeichnisses und liest/schreibt mit ausdrücklicher
Zeilenende-Politik (`newline=""`), damit die Mutation keine Zeilenenden umschreibt.
Schiedsrichter überall: `python -B -m pytest tools/test_radar_trigger.py -q -k <Auswahl> -x`.

| # | wiederhergestellter Defekt | roter Test | rc | Fehlerzeile |
|---|---|---|---|---|
| R1 | README nennt den Agenten vor DEC-0090 (1) wieder | `test_no_artifact_of_the_duo_names_a_watcher_the_repo_does_not_define` | 1 | `AssertionError: these files name a watcher this repo has no definition for, so a reader and a run are sent at nothing: {` |
| R2 | Definition pinnt wieder `model: sonnet` | `test_every_codex_overlay_is_the_one_its_claude_definition_generates` | 1 | `AssertionError: .codex/agents/claude-watcher.toml is not what 'python tools/radar_routine.py --write-overlays' produces from .claude/agents/claude-watcher.md` |
| R2b | Generator prüft `table_places` nicht mehr | `test_a_pin_the_ladder_cannot_place_is_refused_before_an_overlay_is_written` | 1 | `Failed: DID NOT RAISE SystemExit` |
| R3 | zweiteiliger Altname zählt für keinen Runner mehr | `test_the_routine_counts_a_run_per_watcher_and_runner_and_period` | 1 | `AssertionError: a two-part name no longer counts as a run by the watcher's own provider, so every report written before DEC-0090 (3) stopped being countable` |
| R3b | `--due` zählt wieder nur pro Watcher | dito | 1 | `AssertionError: one run cleared more than its own routine` |
| R4 | `starts_itself` = `any` statt `all` | `test_the_self_start_reader_answers_off_the_record_and_the_reports` | 1 | `AssertionError: one of two weekly runs counted as the watcher being started by a mechanism` |
| R5 | Anspruchsleser mit dem Wortschatz vor dieser Runde | `test_the_claim_reader_reads_what_it_claims` | 1 | `AssertionError: A scheduled **watcher duo** runs once a week and writes dated reports here.` |
| R6 | Mechanismus-Leser kennt nur Modul + „desktop" | `test_the_mechanism_reader_names_the_apps_and_not_the_watchers` | 1 | `AssertionError: ['desktop', 'radar_routine']` |
| R7 | `--run` erzwingt wieder `--model sonnet` | `test_no_model_is_forced_on_a_hand_started_run` | 1 | `AssertionError: ['claude', '-p', "Run your weekly scan …", '--agent', 'claude-watcher', '--output-format', …]` |
| R8 | handverfälschter Overlay-Text (`platform.Codex.com`) zurück | `test_every_codex_overlay_is_the_one_its_claude_definition_generates` | 1 | `AssertionError: .codex/agents/claude-watcher.toml is not what … produces from …` |
| R9 | zwei Routinen auf denselben Abend | `test_the_routine_plan_covers_every_watcher_on_every_runner_and_staggers_them` | 1 | `AssertionError: two routines share an evening: ['friday', 'friday', 'monday', 'sunday']` |
| R10 | Runner, für den die Leiter keine Zeile hat | `test_the_runner_vocabulary_is_the_ladders_provider_vocabulary` | 1 | `AssertionError: the runners and the ladder's providers disagree: ['claude', 'codex', 'gemini'] vs ['claude', 'codex']` |
| R11 | Berichtsmuster mit vertauschten Hälften | `test_the_report_name_is_spelled_in_exactly_one_place` | 1 | `AssertionError: radar/2026-09-11-codex-by-claude.md reads back as something other than the routine it was written for` |
| R12 | Instruktionstext nennt den Bericht nicht mehr | `test_the_describe_output_hands_the_lead_an_instructions_text_for_every_routine` | 1 | `AssertionError: claude-watcher-by-claude` |

**R11 war beim ersten Durchgang GRÜN** und ist der Befund, den diese Runde an sich selbst gemacht
hat (`DEC-0070`: ein benannter Test muss scheitern können). Der erste Schnitt legte alle vier
Namen hin und verglich die MENGE der zurückgelesenen Paare — die ist unter dem Tausch der beiden
Hälften symmetrisch, also blieb `rc=0  1 passed`. Der Test liest jetzt eine Datei nach der
anderen; die Zeile oben ist die Messung nach der Korrektur.

### Die alten Texte gegen die neuen Tests

Zusätzlich zu den Mutationen: die Texte aus `5048c18` (`radar/README.md`, beide Definitionen,
beide Overlays) unter die Namen nach der Umbenennung gelegt, neue Tests darauf:

| Auswahl | rc | Fehlerzeile |
|---|---|---|
| `no_artifact_of_the_duo_names_a_watcher` | 1 | `AssertionError: these files name a watcher this repo has no definition for …` |
| `no_text_claims_a_schedule_the_repo_does_not_build` | 1 | `AssertionError: {` (Offender-JSON der alten Sätze) |
| `every_codex_overlay_is_the_one` | 1 | `SystemExit: .claude/agents/claude-watcher.md pins no effort, so this generator would have to invent one; DEC-0076 asks for an explicit 'effort:' in the definition` |

Danach wiederhergestellt: `rc=0  3 passed, 15 deselected`.

### Die Auflage einer offenen Lücke (H190/BUG-0274) ist eingelöst

`BUG-0274.limits` verlangt: „the round that changes `radar/README.md` re-runs the verifier's
v04/v05 rows by hand". Gefahren, je ein Satz an den neuen README angehängt, Schiedsrichter die
ganze Suite:

| Zeile | Satz | rc |
|---|---|---|
| v01 | `The claude.ai cloud routine starts the claude-watcher every Friday from the Desktop.` | 1 |
| v02 | `A claude.ai code routine starts both watchers weekly in a cloud sandbox …` | 1 |
| v04 | `The hosted code routine of the platform starts the claude-watcher every Friday from the Desktop.` | 1 |
| v05 | `The platform's sandbox routine against the remote starts the claude-watcher every Friday from the Desktop.` | 1 |
| — | unveränderter README | 0 (`1 passed, 17 deselected`) |

**v04/v05 sind jetzt rot, aber aus dem FALSCHEN Grund, und H190 ist damit NICHT geschlossen.**
Gemessen mit `schedule_claim_offence` in beiden Datensatz-Zuständen:

    v04 state_one: not every weekly run of claude-watcher is started by a recorded routine …
    v04 state_two: None
    v05 state_one: not every weekly run of claude-watcher is started by a recorded routine …
    v05 state_two: None
    v01 state_one/two: names cloud_option ('claude.ai'), which the declaration lists as not built

Die beiden Sätze fallen heute über die Starter-Klausel, weil `starts_itself` seit DEC-0090 (3) für
beide Watcher `False` ist. Sobald der Lead alle vier Routinen eingetragen hat, sind sie wieder
grün. Der Bund von H190 ist damit **enger** als bisher notiert und sollte so gefasst werden: die
Deckung hängt am Datensatz-Zustand, nicht am Leser. (BUG-0274 liegt außerhalb meines
`allowed_scope` — Änderung ist Sache des Leads.)

---

## 3. Die Zeile, die der Lead lokal ersetzen muss

`C:/Users/zenti/.claude/scheduled-tasks/radar-watcher/SKILL.md` ist **nicht** angefasst worden
(Heimatverzeichnis, außerhalb des Repos). Der Ordnername bleibt, wie er ist — die Desktop-App
besitzt ihn. Zu ersetzen ist der **Zeiger im Rumpf**, sonst zeigt die laufende Freitagsroutine
seit dieser Runde ins Leere:

**ALT (Zeile 7 der Datei):**

    Follow .claude/agents/radar-watcher.md exactly. READ-ONLY on the codebase — only write under radar/.

**NEU:**

    Follow .claude/agents/claude-watcher.md exactly. READ-ONLY on the codebase — only write under radar/.

Und der Berichtsname in Schritt 4 derselben Datei:

**ALT:** `4) Write radar/<today YYYY-MM-DD>.md in the shape from radar/README.md`
**NEU:** `4) Write radar/<today YYYY-MM-DD>-claude-by-claude.md in the shape from radar/README.md`

Empfohlen ist aber, den ganzen Rumpf durch den Instruktionstext aus Abschnitt 4 (Routine 1) zu
ersetzen: dann steht der Name an genau einer Stelle und `--describe` bleibt die Quelle.

---

## 4. Die vier Routinen für den Nutzer — Zeitplan und Instruktionstext wörtlich

Alle vier stammen aus `python tools/radar_routine.py --describe` (Feld `routines[].instructions`),
sind also nicht hier getippt, sondern aus der laufenden Deklaration gelesen. Der Zeitplan ist die
Angabe des Nutzers (`DEC-0090` (4)), **nicht von der Platte lesbar**.

### 1) `claude-watcher-by-claude` — Claude Desktop, **Freitag ~20:00** (existiert, nur neu zeigen)

    You are the weekly claude-watcher run of the agents-and-skills harness repository.
    Follow .claude/agents/claude-watcher.md exactly.
    READ-ONLY on the codebase: write nothing outside radar/, change no code, run no git write command, and do not commit.
    Read radar/decided.md and the newest reports of this watcher FIRST, so nothing already decided or already open is re-surfaced.
    Write exactly one file, radar/<YYYY-MM-DD>-claude-by-claude.md, with today's date in YYYY-MM-DD: this run's watcher is claude-watcher and its runner is claude, and the name carries both (DEC-0090 (3)).
    Leave the report for triage and stop -- you cannot ask questions and you decide nothing.

### 2) `codex-watcher-by-claude` — Claude Desktop, **Samstag ~20:00** (neu anzulegen)

    You are the weekly codex-watcher run of the agents-and-skills harness repository.
    Follow .claude/agents/codex-watcher.md exactly.
    READ-ONLY on the codebase: write nothing outside radar/, change no code, run no git write command, and do not commit.
    Read radar/decided.md and the newest reports of this watcher FIRST, so nothing already decided or already open is re-surfaced.
    Write exactly one file, radar/<YYYY-MM-DD>-codex-by-claude.md, with today's date in YYYY-MM-DD: this run's watcher is codex-watcher and its runner is claude, and the name carries both (DEC-0090 (3)).
    Leave the report for triage and stop -- you cannot ask questions and you decide nothing.

### 3) `claude-watcher-by-codex` — Codex-App (Automations), **Sonntag ~20:00** (neu anzulegen)

    You are the weekly claude-watcher run of the agents-and-skills harness repository.
    Run the agent defined in .codex/agents/claude-watcher.toml and follow its developer_instructions exactly.
    READ-ONLY on the codebase: write nothing outside radar/, change no code, run no git write command, and do not commit.
    Read radar/decided.md and the newest reports of this watcher FIRST, so nothing already decided or already open is re-surfaced.
    Write exactly one file, radar/<YYYY-MM-DD>-claude-by-codex.md, with today's date in YYYY-MM-DD: this run's watcher is claude-watcher and its runner is codex, and the name carries both (DEC-0090 (3)).
    Leave the report for triage and stop -- you cannot ask questions and you decide nothing.

### 4) `codex-watcher-by-codex` — Codex-App (Automations), **Montag ~20:00** (neu anzulegen)

    You are the weekly codex-watcher run of the agents-and-skills harness repository.
    Run the agent defined in .codex/agents/codex-watcher.toml and follow its developer_instructions exactly.
    READ-ONLY on the codebase: write nothing outside radar/, change no code, run no git write command, and do not commit.
    Read radar/decided.md and the newest reports of this watcher FIRST, so nothing already decided or already open is re-surfaced.
    Write exactly one file, radar/<YYYY-MM-DD>-codex-by-codex.md, with today's date in YYYY-MM-DD: this run's watcher is codex-watcher and its runner is codex, and the name carries both (DEC-0090 (3)).
    Leave the report for triage and stop -- you cannot ask questions and you decide nothing.

Die Codex-App wählt Modell und Reasoning-Effort im Formular; die Overlays pinnen
`gpt-5.6-sol` / `high` (opus-Sprosse, `DEC-0090` (2)) — wo die App fragt, ist das die Antwort.
**Nicht gemessen** (kann diese Sitzung nicht): dass die Codex-App auf diesem Host Automations
zeigt und dass ein Codex-Lauf über das Overlay einen Bericht in der gelieferten Form schreibt —
genau das verlangt `DEC-0090` (6) beim nächsten lokalen Neustart.

---

## 5. Läufe (welche und warum), Gate 5 lebt

Kein Lauf über die volle erklärte Fläche — dies ist eine Scheibe unter einem Ziel (`DEC-0088` (d)),
und Gate 5 hat genau das einmal durchgesetzt: `python -B -m pytest .claude/hooks/test_gates.py -q`
→ rc 2, „this line runs the WHOLE declared test surface". Danach mit `-k` verengt.

| Lauf | warum | Ergebnis |
|---|---|---|
| `pytest tools/test_radar_trigger.py -q` | die Suite der geänderten Dateien | 18 passed, 0.82 s |
| `pytest tools/test_repo_hygiene.py tools/test_model_pins.py tools/test_model_ladder.py tools/test_role_contracts.py tools/test_review_procedure.py tools/test_migrate_holes.py -q` | Rollen-Definitionen (Name, Pin, Verträge), Zeilenenden, Loch-Index nach dem Reindex | 120 passed, 65.62 s |
| `pytest tools/test_hooks.py -q -k "gen_provider or gen_codex or neutral_model"` | neuer Aufrufer von `gen_provider_artifacts` (`load_tiers`, `provider_model`, `table_places`, `unplaceable_pin_sentence`, `codex_text`, `toml_str`, `parse_frontmatter`) | 17 passed, 6.52 s |
| `pytest tools/test_shortening_net.py -q -k "repo_path or path_reader"` | der Pfad-Sweep liest u. a. `radar/` | 2 passed, 0.32 s |
| `pytest .claude/hooks/test_gates.py -q -k "session_agent_is_bound or gate2_exempts or todowrite_is_gated or constitution_names_only_code"` | die Gate-Tests, die `.claude/agents/` auflisten (Umbenennung) | 4 passed, 6.21 s |
| `python -m ruff check .` | Lieferkriterium | All checks passed! |
| `python -B tools/validate.py` | Lieferkriterium | all structural checks passed |
| `python tools/bump_kit_version.py` | Lieferkriterium | dreimal `unchanged` |

Callers des bewegten Prädikats (`DEC-0080` Regel 2): `tools/radar_routine.py` wird von **keinem**
anderen Modul importiert — `grep -rn "radar_routine"` über `*.py`/`*.json`/`*.md` findet außerhalb
von Modul und eigener Suite nur Prosa-Nennungen (`radar/README.md`, beide Definitionen,
`radar/routine.json`). Deshalb keine weitere Suite.

Jeder Lauf mit Zeitgrenze (`DEC-0094` (6)), nie zwei pytest-Prozesse gleichzeitig.

---

## 6. Patch

`project_memory/staging/TSK-0134/tsk-0134.patch` — `git diff -M 5048c18` über die erlaubten Pfade,
als BYTES gelesen und mit LF geschrieben (`rig/write_patch.py`). 2366 Zeilen, kein `VERSION`-Hunk;
`git diff -M 5048c18 --stat -- team-kits` ist leer.

---

## 7. (g) Runde

| | |
|---|---|
| Rolle / Modell / Sprosse | `harness-implementer`, Opus 5, effort high (`DEC-0091` (1)) |
| Tokens | ~321.000 vom 15.000.000-Budget verbraucht (eigener Restzähler: 15.000.000 → ~14.679.000 beim Schreiben dieses Protokolls) |
| Wanduhr | Beginn 2026-09-11 01:59:43, Stempel 2026-09-11 02:31:25 — beide gelesen, keine gerechnet |
| Neue Löcher | H192 / BUG-0276 (`capture BUG --hole`, Reindex durch den Kernel) |
| Commit/Push/Install | keiner |

---

## 8. Bewusst NICHT geschlossen, aber benannt

1. **H190 / BUG-0274** — der Zwei-Enden-Stolperdraht zwischen `cloud_option.named_as` und dem
   Absatz „The rejected alternative" ist nicht gebaut. Mein Umschreiben macht ihn **nicht** zur
   Einzeiler-Sache: er braucht einen Leser, der die Wortwahl jenes Absatzes gegen die Liste stellt,
   und „welche Wörter dieses Absatzes benennen die Option" ist der schwierige Teil. Messung des
   heutigen Standes in Abschnitt 2 (v04/v05 rot aus der Starter-Klausel, in `state_two` grün).
2. **H191 / BUG-0275** — `_states_the_scaling_rule` liegt in `team-kits/` und damit im
   `forbidden_scope`. Unberührt.
3. **`.claude/hooks/gate_spawn_needs_item.py` Zeile 11** nennt in seinem Kopfkommentar noch
   `radar-watcher` als Beispiel-Rolle. `.claude/hooks/**` ist `forbidden_scope`; der Name löst
   seit dieser Runde auf nichts mehr auf. Es ist ein toter Zeiger in Prosa, kein Code-Pfad — das
   Gate leitet die Ausnahme aus `harness_item: none` ab und liest keine Namensliste. Für den Lead.
4. **`team-kits/model_tiers.yaml`**, MAINTENANCE-Absatz, nennt ebenfalls noch `radar-watcher`.
   `team-kits/**` ist `forbidden_scope`, und eine Änderung dort zöge einen Kit-Versionsstempel nach
   sich. Für den Lead / eine Kit-Runde.
5. **`HARNESS_LOG.md` Zeile 309** und `docs/reviews/*` nennen `radar-watcher` — Historie,
   append-only, wird ausdrücklich nicht umgeschrieben (`DEC-0090` (1): „survives only in history").
6. **`--run` kann nur Claude-Läufe starten.** Ein Codex-Lauf aus dem Repo heraus ist nicht gebaut
   und nicht gemessen; `SESSION_RUNNER` sagt das im Code, `limits` in `--describe` sagt es im
   Datensatz, der README sagt es im Text. Die Codex-Hälfte kommt aus der App.
7. **Die Runner-Zuordnung der alten zweiteiligen Namen ist eine Zählkonvention, keine Herkunft.**
   `DEC-0090` (3) verlangt sie so; `report_runner` schreibt ausdrücklich dazu, dass mindestens ein
   Paar der `-codex`-Berichte über `--run` (also mit `claude` als Runner) entstand. Wer Herkunft
   braucht, findet sie erst ab dem ersten Lauf mit dreiteiligem Namen.
8. **Nicht gemessen:** dass `claude -p --agent <watcher>` ohne `--model` wirklich den Pin der
   Definition zieht. Gemessen ist nur, was diese Runde baut: die Argumentliste enthält kein
   `--model`, solange keines verlangt wird (`test_no_model_is_forced_on_a_hand_started_run`).
9. **Der `git mv` lief aus einem Skript**, weil Gate 1 jede Befehlszeile verweigert, die eine Datei
   unter `.claude/` in einer Startposition nennt (`rc 2`, H80-Text: „no command line in this repo
   may start …/.claude/agents/radar-watcher.md"). Das ist der von H11 benannte Rest; der Auftrag
   nennt Skripte ausdrücklich als Weg.
