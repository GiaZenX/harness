# TSK-0131 / PR-0008 — Prüfbericht Runde 2 (harness-verifier)

Gemessen 2026-09-06 10:23–10:47 (Uhr gelesen, `date`), Opus 5.
**Frische** Kopie: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0131/verify/r2` (robocopy aus dem
Arbeitsbaum, ohne `.git`). **Frische** Piloten, alle drei Kits, aus echtem `init_project_memory.ps1`
+ `scaffold_team.ps1`: `…/verify/pilots-r2/<kit>/project`. Rig unverändert
(`…/verify/rig.py`: verweigert außerhalb seines Verzeichnisses, schreibt binär). Im Repo wurde
nichts geschrieben außer dieser Datei unter `project_memory/staging/TSK-0131/`.

**Urteil: FAIL.** Die vier Blocker der Runde 1 sind geschlossen und nachgemessen. Die Nacharbeit hat
**zwei neue** aufgemacht — beide von der Klasse, die dieses Projekt sammelt: ein Text, der eine
Mechanik behauptet, die das Paket nicht baut, und dieselbe Leer-Schreibweise-Lücke, die diese Runde
für `expected_outputs` gerade geschlossen hat, eine Datei weiter neu eingebaut.

---

## Teil 1 — die vier Blocker der Runde 1: alle GESCHLOSSEN

### B1 (Sweep fegte Kit-Bäume) — GESCHLOSSEN

Drei frische Scaffolds, das ausgelieferte Kommando durch den Projekteinstiegspunkt:

```
dev-team       clean  rc=0 {}          0 dead pointer(s)   planted rc=1 {'src': 2}  2 dead pointer(s)
office-team    clean  rc=0 {}          0 dead pointer(s)   planted rc=1 {'src': 2}  2 dead pointer(s)
research-team  clean  rc=0 {}          0 dead pointer(s)   planted rc=1 {'src': 2}  2 dead pointer(s)
```

(vorher 39 / 27 / 30.) Der **Quellbaum der Kits behält sein `tools/`**: `sweep-pointers` im
Arbeitsbaum meldet weiter **31**, darunter `tools/test_board.py`, `tools/test_report.py` und
5× `tools/test_review_procedure.py` — die Bedingung an `cli.ENTRY_POINT` wirkt.

Die Ableitung selbst, aus dem laufenden Kernel des Piloten gelesen:

```
installed_kit_paths -> ['.agents/skills', '.agents/skills/backend-developer', …, '.claude',
 '.codex', '.codex/agents/…', '.github/agents', '.github/hooks', 'AGENTS.md',
 'AGENTS.override.md', 'CLAUDE.md', 'scripts', 'tools']
```

Mutationen an den drei Lesern, gegen den **installierten** Kernel des Piloten:

```
as shipped                              rc=1 total=2   {'src': 2}
manifest reader dropped                 rc=1 total=2   {'src': 2}
gate_write_scope import dropped         rc=1 total=2   {'src': 2}
BOTH readers dropped                    rc=1 total=41  {'.agents': 29, '.codex': 10, 'src': 2}
entry-point condition off               rc=1 total=7   {'scripts': 5, 'src': 2}
```

Das ist **keine** Lücke, sondern gewollte Überdeckung: Gate und Manifest nennen dieselben Bäume, also
trägt jeder allein. Es heißt aber, dass der Ausfall **eines** Lesers von nichts bemerkt wird — die
N5-Zeilen „ohne das ausgelieferte Gate / ohne das Provider-Manifest → RED 3 failed" habe ich in
dieser Form **nicht** reproduzieren können; bei mir bleibt jede einzelne Mutation am Piloten grün
und erst beide zusammen sind rot. Falls die N5-Messung gegen den **Quellbaum** lief, misst sie etwas
anderes als der Pilot; das gehört präzisiert, ist aber kein Defekt am Code.

### B2 (Pilot-Test konnte nicht scheitern) — GESCHLOSSEN

Der Test liest jetzt Rückgabecode **und** Zahl, an beiden Enden. Gemessen mit **Neustempelung** nach
jeder Mutation (ohne sie wirft der Scaffold „does not hash to the `content:` in its own VERSION",
und das Rot wäre ein Artefakt — genau der Fehlschluss aus Runde 1):

```
baseline                     rc=0  1 passed, 2 deselected in 22.09s
sweep reports NOTHING        rc=1  AssertionError: dev-team: the planted pointers did not arrive: rc 0, 0
sweep reports EVERYTHING     rc=1  AssertionError: dev-team: a freshly scaffolded project is not clean: rc 1, 298
```

Der zweite Leser (`_sweeping_one_file_speaks`, R3 aus Runde 1) ist weg; der Test fragt
`report.findings_in_text`, also den Leser, der läuft.

### B3 (AC-4 schloss eine Schreibweise) — GESCHLOSSEN

`backlog_types.names_something` liest die **Elemente**. Gemessen an der laufenden Bibliothek und an
der Kommandofläche:

```
names_something: [] [''] [None] ['   '] [[]] '' None [0] [{}] -> False   ['', 'src/z.py'] 'src/z.py' -> True
dispatch.create_task:  alle sieben REFUSED, ['', 'src/z.py'] und der Skalar ACCEPTED
CLI:  --expected-output ''    rc=1     --expected-output '   '   rc=1
      --expected-output '' + real  rc=0 TSK-0003 DRAFT      no --expected-output  rc=1
Validator ueber STORED:  [] [''] [None] ['   '] [[]] -> warning;  ['', 'src/z.py'] -> keine;
                         Schluessel fehlt -> error 'missing required field'
```

Beide Enden lesen dieselbe Funktion; die Mutationen `bool(value)` und `return True` sind rot
(2 failed je).

### B4 (ungemessene Behauptung im Rollentext) — GESCHLOSSEN

`.claude/agents/harness-implementer.md:13–20` sagt jetzt, **was** gemessen ist und **von wem**: kein
Effort-Parameter am Spawn (`BUG-0251`, gemessen), das Modell „the lead reports it can pass at spawn
… that is the lead's measurement and not this file's, because a subagent has no spawn tool to read
the parameter list from". Das ist die ehrliche Fassung. `BUG-0256` ist `DUPLICATE` und archiviert
(`archive/BUG/2026/BUG-0256.yaml`, `limits` vorhanden).

---

## Teil 2 — die neuen blockierenden Befunde

### N-B1 — die beiden Lead-SKILLs behaupten eine Mechanik, die dieses Paket nicht baut, und widersprechen der Verfassung daneben

`team-kits/dev-team/skills/project-manager/SKILL.md:352–357` und
`team-kits/research-team/skills/project-manager/SKILL.md:287–292` (byte-gleich):

> „**Up-scaling is NOT yours to propose any more:** the rung is DERIVED. The constitution's ladder
> paragraph says out of what … and **the kernel derives it at every `dispatch`, writing the rung and
> the effort on the lease, on the work-order header and on the task item**. … **There is no
> user-gated escalation ladder any more; the constitution's ladder paragraph is the whole rule**."

**Gemessen in genau diesem Baum:**

```
team-kits/dev-team/constitution/AGENTS.md:374  - **Effort:** all `high`. … Escalation
team-kits/dev-team/constitution/AGENTS.md:375    ladder (user-gated, triggered by the FIRST QA fail or user dissatisfaction):
team-kits/dev-team/constitution/AGENTS.md:376    `sonnet-high → sonnet-xhigh → opus-high → opus-xhigh/max`.
(research-team/constitution/AGENTS.md:348 dieselbe Regel)

grep -rn "rung" team-kits/kernel/*.py   -> kein Treffer in einem Kernel-Modul
grep -rn "STALE_LADDER" tools/ team-kits/ .claude/  -> kein Treffer (die Karte liegt in G5-2)
```

Der Absatz, auf den der SKILL zeigt und den er „the whole rule" nennt, sagt **das Gegenteil** von
dem, was der SKILL darüber behauptet; und die Mechanik („the kernel derives it at every `dispatch`,
writing the rung … on the lease, on the work-order header and on the task item") existiert im Paket
nicht. Beide Verfassungsabsätze sind von diesem Paket **unverändert**, also der b7f282e-Text.

Der Wächter kann es nicht sehen. `tools/test_review_procedure.py:1272`
(`test_no_lead_skill_still_prescribes_the_retired_user_gated_ladder`) liest nur eine **Form** im
SKILL (Sprossenname + Effortname mit Bindestrich) und verlangt positiv die Zeichenkette
`constitution's ladder paragraph`. Er liest die Verfassung nie. Gemessen: die alte **Regel** in Prosa
zurückgeschrieben, ohne ein `rung-effort`-Token und mit dem Zeiger:

```
baseline                                             rc=0  1 passed in 0.70s
the retired RULE back, no rung-effort token          rc=0  1 passed in 0.71s
```

Und der Docstring desselben Tests (Zeile 1274–1277) behauptet über die Datei, die er zitiert:

> „MEASURED at b7f282e: two lead skills instructed `sonnet-high -> …` … **while the constitutions of
> the same release say the kernel derives the rung and that there is no user-gated escalation ladder
> any more**."

Gemessen: an b7f282e sagen die Verfassungen genau **das Gegenteil** (Zeilen oben). Der Widerspruch,
den der Test zu beseitigen behauptet, ist der, den er herstellt.

**Warum blockierend:** der SKILL ist der Text, dem ein Lead Schritt für Schritt folgt, und er geht in
**jedes** Projekt beider Kits. Liefert dieses Paket allein (oder rutscht G5-2), bekommt jeder PM eine
falsche Regel und wird angewiesen, das zu unterlassen, was die Verfassung daneben verlangt. Das ist
Hausregel 3, in beide Richtungen zugleich.

**Minimaler Fix:** den SKILL-Schritt auf das zurücknehmen, was in **diesem** Baum wahr ist — die
Leiter steht in der Verfassung, der Lead folgt ihr, und *dass* sie abgelöst wird, ist eine Naht mit
G5-2 —, oder den Verfassungsabsatz im selben Paket mitziehen (er steht in `allowed_scope`). Der
Docstring wird gegen die Datei geprüft, die er zitiert. Der Wächter bekommt seine zweite Hälfte: er
muss den Absatz lesen, auf den der SKILL zeigt.

### N-B2 — FR-0012: vier Leer-Schreibweisen von `work` gehen durch die Tür und bringen die Warnung zum Schweigen

`team-kits/kernel/report.py:2854` (`if work is not None and str(work).strip() != DEC_WORK_NONE:`)
und `:2868` (`if work is not None: continue`), Tür in `team-kits/kernel/cli.py:1518`
(`unsaid = [one for one in CAPTURE_ONLY_REQUIRED… if one not in body]`).

`DEC-0083` (2) sagt: „(b) a DEC in force, `work` absent, and no item anywhere names the DEC →
warning; **(c) `work: none` silences (b)**." Und `backlog_types.py` daneben: „`none` … a closed value
beside the id list, so ‚nothing to build' and ‚nobody wrote the field' are two different states".

**Gemessen** — Kommandofläche und Validator, echter Store:

```
capture DEC   no work at all      rc=1  capture DEC: work is missing. …
              work: none          rc=0  DEC-0001 VALID
              work: []            rc=0  DEC-0002 VALID
              work: ''            rc=0  DEC-0003 VALID
              work: ['']          rc=0  DEC-0004 VALID
              work: ['TSK-9999']  rc=0  DEC-0005 VALID

validate:  no work at all   -> warning 'decision without a carrier'
           work: none       -> SILENT     work: []        -> SILENT
           work: ''         -> SILENT     work: ['']      -> SILENT
           work: '   '      -> SILENT     work: ['none']  -> SILENT
           work: ['TSK-9999'] -> error 'work names TSK-9999, which no item carries'
```

Vier Schreibweisen schweigen die Zeile, ohne je `none` zu sagen — und `work: []` ist genau das, was
ein JSON-Body schreibt, wenn der Autor die Ids noch nicht hat. Damit ist der DEC-0034-Fall wieder
offen: eine Entscheidung mit `work: []` verlangt Arbeit, nennt keinen Träger und wird von niemandem
genannt.

Das ist **dieselbe Klasse**, die diese Nacharbeit für `expected_outputs` geschlossen hat, und die
Funktion dafür liegt in derselben Datei: `backlog_types.names_something`. Der benannte Test
(`tools/test_report.py:3076`) deckt keine davon ab — gemessen an seinem eigenen Rumpf:
`work: []`, `work: ""`, `[""]`, `"   "` kommen dort nicht vor.

**Minimaler Fix:** beide Stellen dieselbe Frage stellen lassen, die die Runde schon gebaut hat —
an der Tür `names_something(body.get(DEC_WORK_FIELD)) or body[DEC_WORK_FIELD] == DEC_WORK_NONE`,
im Validator ein leeres `work` wie ein fehlendes behandeln (die Warnung), und die vier Schreibweisen
in den benannten Test.

### N-B3 — ein Kommentar in `migrate.py` behauptet eine Ausnahme, die der Code nicht hat (und die Datei steht nicht im `allowed_scope`)

`team-kits/kernel/migrate.py:2859`:

> „An imported V1 decision is the other case and gets no value at all (**`state.capture_preflight`
> exempts `IMPORT_MARK`**)."

**Gemessen:** `grep -n IMPORT_MARK team-kits/kernel/state.py` → nur Zeilen 55 (Import), 1212 und 1285
(beide **schreiben** die Marke). `capture_preflight` liest `IMPORT_MARK` nirgends und fragt `work`
überhaupt nicht — die Pflicht sitzt in `cli.py:1518`. Der Import kommt durch, weil er die
Kommandofläche gar nicht betritt, nicht weil ihn irgendwer ausnimmt. Der Kommentar in `cli.py:1509`
sagt es korrekt („exempting the importer needs a READER of `IMPORT_MARK`, which `DEC-0021` refused")
— zwei Kommentare desselben Pakets widersprechen sich, einer ist falsch.

**Bereich:** `allowed_scope` von TSK-0131 zählt fünf Kernel-Dateien auf (`report.py`, `state.py`,
`backlog_types.py`, `cli.py`, `holes.py`). `team-kits/kernel/migrate.py` ist **keine** davon; im
`forbidden_scope` steht sie auch nicht. Der Patch ändert sie (eine Zeile Feld + fünf Zeilen
Kommentar). Das ist eine Bereichsfrage für den Lead, keine Sicherheitslücke — aber sie gehört
entschieden, nicht übersehen.

**Minimaler Fix:** den Klammersatz streichen oder auf das Gemessene setzen („der Import läuft nicht
über die Kommandofläche, an der die Pflicht sitzt"); die `migrate.py`-Änderung vom Lead
nachträglich in den Bereich nehmen oder herauslösen.

---

## Teil 3 — die Reste der Runde 1

| Rest | Stand |
|---|---|
| R1 Stock-Zeile unterscheidet „kein Lauf" nicht | **behoben** — `cli.py:1356–1363` druckt drei Zustände, mit dem Anlass im Kommentar |
| R2 H175 nannte den Mechanismus nicht | **behoben** — `BUG-0265` (H183) benennt die verbleibende Über-Ausschließung (`scripts/`, `tools/`) mit Messung und `limits` |
| R3 Kopie der Sweep-Schleife im Test | **behoben** — `report.findings_in_text` |
| R4 Verfassung überzog („every test name") | **behoben** — der Absatz nennt jetzt, was er **nicht** liest (bloßer Dateiname, Knoten über eine Klasse, fremde Sprache) |
| R5 Tabellen-Verdikte gegen die eigene Zeile | **behoben** — 0 Zeilen mit PASS auf einem kurzen Lauf; BUG-0016/0025 = `MEASURED-PARTIAL`, BUG-0069 = `MEASURED-OPEN` mit `EVD-0091/fail` |
| R6 falsche Behauptung über office/research | **behoben** — research-Verfassung trägt die Wurzelersatz-Regel (`SUPERSEDED`, `BUG-0022`), das Journal sagt „dev-team only in that entry"; office bleibt zu Recht draußen (`PROC` hat kein `SUPERSEDED`, Terminal ist `RETIRED`) |
| R7 fehlende Leser-Mutationen im Protokoll | **behoben** — N5 führt 29, inklusive der vier AC-3/AC-4-Leser |
| R8 WISHLIST außerhalb des Patches | **benannt** — N6 nennt `migrate-holes --reindex` als Merge-Schritt |
| R9 CLAUDE.md „vier Gates" | **erfasst** als `BUG-0267` |

---

## Teil 4 — Urteil je Kriterium und Pflicht

| AC | Runde 1 | Runde 2 | Grund |
|---|---|---|---|
| AC-1 | FAIL | **TEILWEISE** (unverändert offen) | 202 Zeilen = alle aktiven BUGs, 0 Standabweichungen, Verdiktvokabular korrigiert, 7 `update` mit nachgemessener Kette (BUG-0010/0017/0037/0052/0053/0079/0082, alle mit Marke geprüft). Die drei Verdikte des AC stehen weiter nicht im Zustand; `BUG-0261` trägt die 102 Zeilen; wartet auf `dec-bug-closing-route.json` |
| AC-2 | TEILWEISE | **TEILWEISE** | 4 MERGED+archiviert, der zurückgestellte Block mit Notiz, FR-0002/FR-0004 nachgemessen, 6× `related_pr` auf PR-0009/0010 gezogen; 18 aktive FRs |
| AC-3 | PASS | **PASS** | R1 geschlossen |
| AC-4 | FAIL | **PASS** | B3 |
| AC-5 | PASS | **PASS** | research-Verfassung nachgezogen |
| AC-6 | TEILWEISE | **TEILWEISE** | unverändert; wartet auf sechs Scope-Münzungen und vier Lieferfreigaben (Kernel-Regel `("BUG","scope"): ("TRIAGED","APPROVED")`) |
| AC-7 Texte | PASS | **PASS** | Absatz byte-identisch ×3 (2199 B, ein SHA), alter Absatz weg, 9 Rollendefinitionen, ein Text |
| AC-7 Mechanik | FAIL | **PASS** | B1 + B2 |
| **AC-7 FR-0012** | offen (vorgesehen) | **FAIL** | gebaut, aber N-B2 |

**Pflicht 8 (rot-zuerst, Mutationen, Löcher, Suiten, Host, Uhr): TEILWEISE.**
Rot-zuerst je Fix in meiner eigenen Kopie nachgestellt. Löcher: `BUG-0265` (H183) kernelvergeben,
mit `limits` und Modulpräfix (`kernel.report.installed_kit_paths`) ✓; `BUG-0256` DUPLICATE archiviert
✓. **`BUG-0267` trägt weder Lochnummer noch `limits`** — es ist eine gemessene, offene Lücke, taucht
so aber im Zeigerindex nicht auf; die Pflicht des Auftrags nennt `capture BUG --hole`.
Migrationstests, die in der ersten Fassung rot waren: **`tools/test_migrate.py` 141 passed**
(im git-tragenden Arbeitsbaum gefahren; in meiner Kopie ohne `.git` sind sie ERROR — Artefakt, nicht
Befund). Zwei Lücken im benannten Träger-Test, beide gemessen:

```
_check_decision_carriers: `none` stops silencing            rc=1  1 failed   (echte Mutation)
_check_decision_carriers: an ARCHIVED carrier does not count rc=0  1 passed  ← nicht gedeckt
```

Der Archiv-Zweig in `report.py:2859` (`not _in_archive(state, ref)`) ist **heute tragend**:
`DEC-0071..0074` und `DEC-0079` zeigen mit `work: ['TSK-0126']` auf ein **archiviertes** Item.
Nimmt man ihn heraus, bleibt der benannte Test grün und der Validator würde auf dem echten Store
fünf Fehler erfinden. (Eigener Fehler, offen: meine erste `none`-Mutation war äquivalent und sagte
nichts — dieselbe Falle, die N5 selbst protokolliert.)

**Pflicht 9 (Nähte): FAIL** — N-B1. Alles andere hält: `cli.py` eigener Block, Verfassungen tragen
genau Kommentarpflicht + CR-Regel + Kommandoliste + (research) Wurzelersatz, `harness-*.md` sind
diese Runde, Journal additiv, README. Die Naht an G5-2 ist in N6 **benannt** (die zwei Lead-SKILLs
raus aus `STALE_LADDER_TEXTS`, die drei `project_config.yaml` bleiben, `migrate-holes --reindex`) —
der Text selbst ist trotzdem der Befund.

**Pflicht 10 (Handover): PASS, mit dem Bereichspunkt aus N-B3.**

```
patch bytes=230056  CRLF lines=0  LF-only lines=3266
37 Dateien, 36 mit index-Zeile, neu: tools/test_pointer_sweep.py
pre-image mismatches: 0   (jeder `index <old>..` gegen `git rev-parse b7f282e:<pfad>`)
VERSION 0 · project_memory 0 · CLAUDE.md 0 · .claude/hooks 0 · settings.json 0 ·
kit hooks 0 · kit templates 0 · model_tiers 0
```

Hauptstore mit dem Kernel dieses Pakets: **0 error(s), 77 warning(s)**, davon **10** „decision
without a carrier" (die Nacharbeit meldet 11 — nachgezählt sind es 10: DEC-0005/0007/0023/0035/0037/
0049/0052/0054/0058/0085), 0 `work names …`-Fehler, 12 Entscheidungen mit auflösendem `work`,
„Stock lies upward: 5 item(s)".

---

## Ausdrückliche Negativbefunde

**Gemessen und in Ordnung:** die drei frischen Piloten (clean 0 / planted 2, rc 0 / rc 1); der
Quellbaum behält seine 7 `tools/`-Befunde; B2 mit Neustempelung beidseitig rot; alle sieben
`expected_outputs`-Schreibweisen an beiden Türen plus die zwei legalen und die CLI; der Validator
über fünf gespeicherte Leerformen; `tools/test_migrate.py` 141 passed; die drei zuvor roten
`test_hooks`-Knoten (`…name_only_state_files…`, `…on_the_entry_points_surface`,
`…command_surface_names_all_of_it`) 3 passed; der Kommentarabsatz byte-identisch ×3 mit den jetzt
genannten Grenzen; 9 Rollendefinitionen, ein Text; Tabelle 202 Zeilen = 202 aktive BUGs, 0
Standabweichungen, 0 PASS-auf-kurzem-Lauf; 12 Stichproben (4 alte BUGs, 4 Löcher, 4 FRs) gegen Store
und Evidenz stimmig; die sieben nachgemessenen Ketten tragen ihre Marke; `DEC_FIELDS`-Shadowing weg
(`tools/test_report.py:972` Modulebene, der neue Block nutzt `CARRIER_DEC_FIELDS`); Patch sauber.

**Nicht gemessen:** die volle Suite (gehört dem Merge); die Zahlen 747 / 371 / 3142 / 1077 der
Nacharbeit nicht nachgefahren; `tools/test_repo_hygiene.py` und `test_context_budget.py` in meiner
Kopie nicht (brauchen einen git-Baum); der gehostete CI-Lauf (BUG-0069); ob der Agent-Aufruf
wirklich einen `model`-Parameter trägt (kein Spawn-Werkzeug hier — der Rollentext schreibt es jetzt
korrekt dem Lead zu); die Spiegelung nicht byteweise nachgehasht; `office-team`-Piloten-`tools/` nur
gezählt.

---

## Urteil

**FAIL.**

**Blockierend für die Runde:**
* **N-B1** — die beiden Lead-SKILLs (`dev`/`research`, `…/skills/project-manager/SKILL.md:352–357`
  bzw. `:287–292`) behaupten eine abgeleitete Sprosse, die dieses Paket nicht baut (`rung` kommt in
  keinem Kernelmodul vor), und widersprechen dem Verfassungsabsatz, auf den sie als „the whole rule"
  zeigen (`…/constitution/AGENTS.md:374–376`, unverändert seit b7f282e). Der Wächter liest nur eine
  Token-Form im SKILL und bleibt grün, wenn man die alte Regel in Prosa zurückschreibt; sein
  Docstring zitiert die Verfassungen falsch herum.
* **N-B2** — `work: []`, `work: ""`, `work: [""]`, `work: "   "` kommen durch die Kommandotür und
  schweigen die Träger-Warnung, ohne `none` zu sagen; `DEC-0083` (2)(c) nennt genau eine Stille. Die
  Funktion, die diese Klasse eine Datei weiter schon löst (`names_something`), ist hier nicht
  benutzt, und der benannte Test deckt keine der vier Schreibweisen ab.

**Als benannte Reste** (nicht rundenblockierend, gehören auf den Tisch des Leads bzw. in die
Löcherliste): **N-B3** (falscher Klammersatz in `migrate.py:2859` **und** die Bereichsfrage zu
`team-kits/kernel/migrate.py`); der ungedeckte Archiv-Zweig des Träger-Tests, der auf dem echten
Store heute trägt; `BUG-0267` ohne Lochnummer und `limits`; „11 Entscheidungen ohne Träger" gegen
gemessene **10**; N6 sagt, die SKILLs „nennen `ladder.yaml` als Erklärung" — sie nennen den
Verfassungsabsatz; die N5-Zeilen „ohne das Gate / ohne das Manifest → RED" konnte ich am Piloten
nicht reproduzieren (einzeln grün, nur beide zusammen rot) und bitte um die Messfläche, gegen die
sie gefahren wurden. AC-1/AC-2/AC-6 bleiben wie in Runde 1: sauber gemessen, ehrlich unvollständig,
wartend auf zwei Nutzerentscheidungen, sechs Scope-Münzungen und vier Lieferfreigaben.
