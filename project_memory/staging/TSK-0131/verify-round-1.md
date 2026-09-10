# TSK-0131 / PR-0008 — Prüfbericht Runde 1 (harness-verifier)

Gemessen 2026-09-06 05:03–05:34 (Uhr gelesen, `date`), Opus 5.
Arbeitskopie: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0131/verify/g5-stock` (robocopy aus
dem Arbeitsbaum, **ohne** die `.git`-Zeigerdatei — die kopiert `robocopy /XD .git` nicht mit und sie
wurde einzeln entfernt). Rig: `…/verify/rig.py` — verweigert den Lauf außerhalb seines eigenen
Verzeichnisses (gemessen: `cwd 'C:\Offline Repos\v2-testbed'` → rc 2) und öffnet jede Datei binär
mit ausdrücklicher Kodierung. Piloten: `…/verify/pilots2/<kit>/project`, je aus echtem
`init_project_memory.ps1` + `scaffold_team.ps1`. Im Repo wurde **nichts** geschrieben außer dieser
Datei unter `project_memory/staging/TSK-0131/`.

**Urteil: FAIL.** Vier blockierende Befunde (B1–B4), dazu neun benannte Reste.

---

## Blockierend

### B1 — `pointer_sweep` liest genau die Kit-Bäume, deren Ausschluss sein eigener Docstring behauptet

`team-kits/kernel/report.py:2149–2156` (Docstring `_swept_files`), Ausschlüsse in `:2183` und
`:2187`, Aufzählung in `:2058`.

Der Docstring sagt:

> „FOUR GROUPS ARE LEFT OUT … * **everything the KIT installed**: its home directory (read off
> `presets.KIT_VERSION_FILE` …) and the root files it copies (`SCAFFOLDED_ROOT_FILES`). Those cite
> the items and tests of the kit's SOURCE repository, which this store does not hold and this
> project may not edit … so **a finding there names nobody who could act on it**.“

Gebaut ist: `rel.split("/")[0] == kit_home` mit `kit_home == ".claude"` (`:2236`,
`presets.KIT_VERSION_FILE = .claude/kit_version`) plus drei Wurzeldateinamen. Der Installer schreibt
aber **auch** `.agents/`, `.codex/`, `scripts/` (und im office-Kit `tools/`). Diese Bäume werden
gefegt.

**Gemessene Zeile** — je ein frisch gescaffoldetes Projekt pro Kit, kein einziges eigenes
Codezeichen darin, das ausgelieferte Kommando durch den Projekteinstiegspunkt:

```
dev-team       rc=1  39 dead pointer(s)   {'.agents': 24, '.codex': 10, 'scripts': 5}
office-team    rc=1  27 dead pointer(s)   {'.agents': 11, '.codex': 5, 'scripts': 4, 'tools': 7}
research-team  rc=1  30 dead pointer(s)   {'.agents': 20, '.codex': 10}
```

Erst nach dem Einpflanzen zweier echter toter Zeiger in `src/pricing.py`: 41 / 29 / 32 — Signal zu
Rauschen 2 : 39.

Warum das blockiert: die drei Verfassungen weisen ab dieser Runde **jede** bauende Rolle auf
`python scripts/harness.py sweep-pointers` als die mechanische Hälfte der Kommentarpflicht. Deren
erster Lauf in einem taufrischen Projekt endet rc 1 mit 27–39 Befunden, die niemand bearbeiten kann
(`gate_write_scope` verweigert Schreibzugriffe dorthin) — genau der Zustand, den der Docstring als
ausgeschlossen behauptet. Das ist Hausregel 1 (Aufzählung statt Definition) und Hausregel 3
(Behauptung ohne Bau) in einem.

**Minimaler Fix:** „Kit-Material" aus dem ableiten, was der Installer selbst protokolliert, statt aus
einem Verzeichnisnamen plus drei Dateinamen. Das Manifest liegt im Projekt:
`.claude/provider_artifacts.json` führt `files:`/`dirs:` für `.codex/` und `.agents/` namentlich;
`scripts/` (und office `tools/`) kommen aus demselben Scaffold-Schritt und gehören in dieselbe
Ableitung. Der Stolperdraht dazu ist der Pilot-Test unten (B2).

### B2 — der Pilot-Test von AC-7 kann an dem, was er zu messen behauptet, nicht scheitern

`tools/test_pointer_sweep.py:252` — die einzige Zusicherung über die Ausgabe des ausgelieferten
Kommandos lautet `assert "dead pointer(s)" in ran.stdout`.

Sein Docstring behauptet: „the command is run END TO END through the project's own entry point,
which is the reach `DEC-0080` (1) asks to be measured in every kit rather than in one."

**Gemessene Zeile** — derselbe dev-Pilot, zweimal, einmal mit dem ausgelieferten Sweep und einmal
mit einem `pointer_sweep`, das im **installierten** Kernel des Piloten sofort `return []` macht:

```
as shipped                       rc=1  the assertion holds: True  |  41 dead pointer(s) …
installed sweep reports nothing  rc=0  the assertion holds: True  |   0 dead pointer(s) …
```

Der Test bemerkt weder den Rückgabecode noch die Zahl. Ein vollständig kaputter Sweep ist grün, und
der Lärm aus B1 ist für ihn unsichtbar. (Ein Gegencheck: eine Mutation von `report.py` **im
Kit-Quellbaum** lässt den Test rot werden, aber aus einem anderen Grund — der Scaffold verweigert
mit „does not hash to the `content:` in its own VERSION". Das ist ein Artefakt, keine Messung; die
oben ist die echte.)

**Minimaler Fix:** im Pilot-Test den Rückgabecode und die Zahl lesen — ein frisch gescaffoldetes,
sonst leeres Projekt hat **0** tote Zeiger und rc 0; ein eingepflanzter toter Zeiger hebt sie auf 1
und rc 1. Beide Enden, wie es der Stolperdraht daneben für `SCAFFOLDED_ROOT_FILES` schon tut.

### B3 — AC-4 schließt genau **eine** Schreibweise von „erwartet nichts"

`team-kits/kernel/state.py:848–853` (`capture_preflight`, Prädikat `not fields.get(k)`),
`team-kits/kernel/backlog_types.py:659–664`, `team-kits/kernel/report.py:2777–2797`
(`_check_nonempty_fields`, Prädikat `field in item and not item.get(field)`).

Die Verweigerung behauptet eine Eigenschaft: „`expected_outputs` **must name something** — an empty
list there is the same claim as leaving the field out."

**Gemessene Zeile** — echte CLI, echter Store:

```
--expected-output ''       rc=0  TSK-0001 DRAFT (backend-developer)
--expected-output '   '    rc=0  TSK-0002 DRAFT (backend-developer)
no --expected-output       rc=1  capture TSK: expected_outputs must name something …
```

und über `dispatch.create_task`: `[]` REFUSED, `['']` / `[None]` / `['   ']` / `[[]]` ACCEPTED,
Schlüssel fehlt → REFUSED (das ist die alte `REQUIRED_FIELDS`-Prüfung).

Der Validator schweigt zu allen davon:

```
[error]   TSK-0005: missing required field 'expected_outputs'
[warning] TSK-0002: expected_outputs is empty …
items with NO finding at all: ['TSK-0003' (['']), 'TSK-0004' ([None])]
```

Ein Auftrag mit `expected_outputs: ['']` nennt nichts, ist von jedem Paket erfüllt und ist über eine
einzige Kommandozeile erreichbar — das ist die Klasse, die BUG-0023 meint. Die Kette läuft innerhalb
einer Sitzung durch, also blockierend nach der Hausregel.

**Minimaler Fix:** das Prädikat auf die **Elemente** heben statt auf den Behälter — `NONEMPTY_FIELDS`
ist bereits eine Karte Typ → Felder; die eine Zeile lautet „mindestens ein Element, das nach
`strip()` etwas ist" (dieselbe Fassung an beiden Enden, `state.capture_preflight` und
`report._check_nonempty_fields`), plus je ein roter Fall `['']` in den beiden vorhandenen Tests.

### B4 — eine ungemessene Eigenschaftsbehauptung wird in einem Rollentext ausgeliefert

`.claude/agents/harness-implementer.md`, neuer Absatz Zeilen 13–20:

> „…its record also states that the spawn call offers no effort parameter, so **a caller cannot pick
> either value at spawn time**. That leaves **exactly one way** to run a merge implementer on
> another tier: a SECOND definition beside this one."

Dieselbe Behauptung steht im `observed` von `BUG-0256` (H174).

**Gemessen:** der einzige Datensatz dieses Repos zur Spawn-Fläche nennt **nur** den Effort-Parameter:
`docs/POST_V2_WISHLIST.md:2456` (H169/BUG-0251) — „the Agent tool has **no per-spawn effort
parameter**, so the child runs on its installed `effort:` pin". Über einen `model`-Parameter sagt
nichts im Repo etwas. Die eigene Sondierung des Stroms
(`_round-scratch/TSK-0131/spawn_surface.py`) liefert nachgefahren:

```
spawn events in the audit log: 0
tool_input keys and how often: {}
```

und die Quelle erklärt warum: `project_memory/.audit/hook_events.jsonl` hat 617 Zeilen, **keine**
davon trägt einen Schlüssel `tool_name` — das Protokoll verzeichnet nur Verweigerungen. Die
Behauptung „exactly one way" ist also durch nichts gedeckt, und DEC-0081 (2) verlangt für den Merge
nur **Fable/high** — also nur die Modell-Achse, nicht die Effort-Achse.

Was erreichbar ist und was nicht, präzise: **effort** ist am Spawn nachweislich nicht wählbar
(H169, gemessen). **model** ist in diesem Repo **weder als vorhanden noch als abwesend gemessen**;
solange das so ist, darf kein Rollentext eine Zahl von Wegen behaupten. Wenn der Agent-Aufruf einen
`model`-Parameter trägt, ist DEC-0081 (2) heute ohne zweite Datei erreichbar, und BUG-0256 wäre
allein eine Effort-Lücke (also eine Dublette von H169/BUG-0251).

**Minimaler Fix:** den Satz auf das Gemessene zurücknehmen („der Spawn trägt keinen
Effort-Parameter (`H169`); ob er ein Modell wählen kann, ist hier nicht gemessen") **oder** ihn
messen und die Messung nennen. `BUG-0256` bekommt dieselbe Korrektur und einen Verweis auf
`BUG-0251`, sonst stehen zwei Items für dieselbe Lücke.

---

## Befunde je Kriterium

| AC | Urteil | Kurz |
|---|---|---|
| AC-1 | **FAIL** (benannter Rest, blockiert die Runde nicht) | kein Zustand geschrieben; die Tabelle trägt vier eigene Verdiktwörter statt der drei des AC |
| AC-2 | **TEILWEISE** | 4 MERGED+archiviert korrekt, 8 mit Notiz, 10 FRs unangetastet |
| AC-3 | **PASS** (mit benannter Grenze) | rot-zuerst nachgestellt, alle Angriffe halten |
| AC-4 | **FAIL** (B3) | eine Schreibweise geschlossen, drei offen |
| AC-5 | **PASS** | fünf Mutationen rot, Pilotlauf nachgefahren |
| AC-6 | **TEILWEISE** | Evidenz korrekt, Statuswechsel warten auf Nutzer-Münzungen (Kernel-Regel, nicht Lesart des Stroms) |
| AC-7 Texte | **PASS** (mit B7) | byte-identisch ×3, 9 Rollen abgeleitet, Mutationen rot |
| AC-7 Mechanik | **FAIL** (B1, B2) | |
| AC-7 FR-0012 | **offen wie vorgesehen** | `dec-decision-catcher.json` liegt, nicht gebaut |

### AC-1 — nachgemessen

Store heute: **199** aktive BUG-Items (114 mit `hole_number`), Stand `{'TRIAGED': 142, 'OPEN': 57}`.
Tabelle: 196 Zeilen; die drei fehlenden sind die dieser Runde erfassten (BUG-0261/0262/0263).
**Kein einziger Stand weicht ab** — weil nichts geschrieben wurde. Verdiktspalte:
`MEASURED-PASS 106, OPEN-BY-DESIGN 52, UNMEASURED 32, MEASURED-OPEN 6`. Keines dieser vier Wörter
ist eines der drei, die AC-1 verlangt (VERIFIED+archiviert / OPEN mit nachgemessener Kette und Datum
via `update` / CANCELLED mit dem absorbierenden Item). Die 6 `MEASURED-OPEN` hätten die zweite Route
tragen können — `update` lief in dieser Runde 14×, aber nur für BUG-0069 und die FRs.

Die Begründung des Stroms (H179/BUG-0261: ein bestandener Test, der einen Bug NENNT, ist eine
Messung und kein Urteil) ist **richtig und selbst gemessen** — 106 Zustandsschreibungen aus
Laufausgängen wären 106 mögliche Falschzustände gewesen. Der Rest ist damit ordentlich benannt statt
geraten. Er ist trotzdem der Kern von AC-1, und die Entscheidung dazu
(`dec-bug-closing-route.json`) liegt beim Nutzer.

**Zwölf Zeilen zufällig gezogen (seed 20260906)** und gegen den Store gehalten: BUG-0137, BUG-0081,
BUG-0160, BUG-0202, BUG-0028, BUG-0011, BUG-0203, BUG-0173, BUG-0068, BUG-0208, BUG-0206, BUG-0004
— Stand in der Tabelle = Stand im Store in **allen zwölf**, Lochnummer stimmt in allen sechs
Lochzeilen, die genannten Evidenzitems existieren.

### AC-2 — nachgemessen

`FR-0048 → TSK-0076`, `FR-0064 → TSK-0105`, `FR-0069 → TSK-0105`, `FR-0072 → TSK-0111`, alle
`MERGED` und archiviert, alle mit `resulting_item` ✓. Der zurückgestellte Block trägt die Notiz
wörtlich: „DEFERRED BLOCK, user verdict 2026-09-04/05, recorded in DEC-0080 (9)" in
FR-0019/0020/0022/0023/0024/0025 ✓. FR-0043 und FR-0058 tragen ihre nachgemessene Zeile ✓.
Zehn FRs (FR-0002/0004/0007/0012/0015/0033/0047/0073/0081/0088) haben ein **leeres** `source` und
sind ungemessen — die vom Strom benannte Grenze (Kollision mit G5-2/G5-3). AC-2s letzte Forderung
(„no FR remains whose source describes something already built") ist für diese zehn nicht geprüft.

### AC-3 — PASS, rot zuerst nachgestellt

Rot-zuerst in **meiner** Kopie (jeweils Mutation → Auswahl → zurück):

```
AC-3 confirmation question -> delivery      rc=1  1 failed
AC-3 stock line removed from cli validate   rc=1  1 failed
AC-3 unresolved always empty                rc=1  1 failed
AC-4 NONEMPTY_FIELDS without TSK            rc=1  2 failed
AC-3 validator drops the nonempty check     rc=1  1 failed
```

Angriffe auf den Fix, gegen die laufende Ableitung in einem eigenen Store:

* archiviertes Item mit bestandener bestätigender Evidenz → **nicht** genannt ✓
* Evidenz `result: fail` → **nicht** genannt ✓
* Test, den der Baum nicht definiert → in `unresolved` genannt, die Zeile sagt es ✓
* Item, dessen genannter Test besteht, über den Bug aber **nichts** aussagt → **genannt**. Die
  gedruckte Zeile ist dabei **ehrlich**: „Stock lies upward: N item(s) **whose confirming Evidence
  passes while their status still reads open**" — sie behauptet über den Datensatz, nicht über den
  Fehler. Das ist die richtige Formulierung für H179.

**Benannte Grenze (kein Blocker, R1):** ein Item, dessen bestandene Evidenz **gar kein**
`run_command` trägt, wird genauso genannt, und `unresolved` ist dann `[]` — dieselbe leere Liste wie
bei „alles löst auf". Gemessen:

```
BUG-0002 run_command='… tests/test_nothing.py::test_unrelated -q'  unresolved=[]
BUG-0004 run_command=None                                          unresolved=[]
validate:  BUG-0004 OPEN (test EVD-0004): OPEN -> TRIAGED -> …
```

Die gedruckte Zeile nennt `run_command` überhaupt nicht, also kann ein Leser „nichts
Wiederholbares aufgezeichnet" nicht von „alles vorhanden" unterscheiden. Der Docstring
(`report.py:1979–1983`) verspricht das auch nicht ausdrücklich — er spricht nur vom Fall „names a
test node the tree no longer defines" —, deshalb Grenze und nicht Falschbehauptung.

**Laufzeit gemessen** (die Richtung „Budget", die ein Fix aufreißen kann), echter Store:

```
validate @ b7f282e kernel  2.92 / 2.47 s      doctor @ b7f282e  2.80 s
validate @ stream kernel   3.44 / 3.69 s      doctor @ stream   3.90 s
0 error(s), 67 warning(s) in beiden — Stock lies upward: 5 item(s)
```

`validate_state` selbst wächst nur um `_check_nonempty_fields`; der teure Rollup hängt in
`cli.validate` und `doctor`, **nicht** in `validate_state` — also nicht auf der Merge-/Push-Frist von
`gate_memory_complete`. Kein Fristproblem.

### AC-5 — PASS

`tools/test_hooks.py::test_a_change_to_something_built_walks_the_CR_route_the_constitution_names`
in meiner Kopie: **1 passed in 12.68 s**. Fünf Mutationen, alle rot:

```
AC-5 route names a status the kernel has not   rc=1  1 failed
AC-5 approval kind dropped                     rc=1  1 failed
AC-5 measured occasion (BUG-0022) dropped      rc=1  1 failed
AC-5 replaced root's status dropped            rc=1  1 failed
AC-5 kernel drops the CR/scope binding         rc=1  1 failed
```

Der Test liest die Route wirklich aus dem ausgelieferten Text, hält sie gegen `AUTOMATA["CR"]` und
`APPROVAL_TRANSITIONS[("CR","scope")]` und **läuft** sie auf einem Projekt der echten Installer,
inklusive Münzung durch den projekteigenen Haken. Das ist Text-zu-Verhalten, nicht Zeichenkette.

### AC-6 — nachgemessen, wartet auf den Nutzer

EVD-0086..0091 liegen unter `project_memory/evidence/` und benennen, was sie behaupten
(Läufe, Zeiten, artifact_refs, `run_command`) ✓. Zustände heute:

```
BUG-0025/0033/0069/0088/0090/0091   alle OPEN
BUG-0083/0084/0085/0086/0089        VERIFIED, archiviert (APR-0001..0004, APR-0006)
TSK-0121..0129                      CANCELLED, archiviert
PR-0004..0007                       APPROVED (nicht IN_DELIVERY/DELIVERED)
```

**Warum ein BUG eine Scope-Freigabe braucht, ist Kernel-Regel und nicht Lesart des Stroms:**
`backlog_types.py:96–105` — `chain=("OPEN","TRIAGED","APPROVED","FIXED","VERIFIED")`, `VERIFIED` nur
über die Kette — zusammen mit `approvals.py:207` `("BUG","scope"): ("TRIAGED","APPROVED")`. Die
Kante TRIAGED→APPROVED ist an eine nutzergemünzte Freigabe gebunden; ohne sie gibt es keinen Weg
nach VERIFIED. Und die Münzung ist in **diesem** Repo möglich: `.claude/settings.json` registriert
`team-kits/dev-team/hooks/gate_approval.py` auf `AskUserQuestion` (Pre **und** Post), und
APR-0001..0006 tragen `minted_via: user_answer_via_approval_hook`. Es fehlt also nur der Klick, und
die sechs Zeilen stehen fertig in Abschnitt 6 des Protokolls.

### AC-7, erste Hälfte — PASS

Absatz byte-identisch ×3, gemessen:

```
dev-team       1880 bytes  sha256:63c5ae8b4bcb869c  occurrences=1
office-team    1880 bytes  sha256:63c5ae8b4bcb869c  occurrences=1
research-team  1880 bytes  sha256:63c5ae8b4bcb869c  occurrences=1
```

Der alte Absatz („A comment says what the code cannot") ist in allen drei **weg**, nicht gedoppelt ✓.
Rollendefinitionen: genau **9** tragen den Satz (dev backend/devops/frontend/quality, office
office-developer, research data-analyst/research-engineer/researcher/reviewer), byte-identisch,
437 B, ein SHA ✓.

Die Ableitung der bauenden Rollen mutiert (die Richtung, die der Docstring bestreitet):

```
baseline (unmutated)                                  rc=0  3 passed
(a) neue Rolle, deren SKILL FR-0007 nennt, ohne Satz  rc=1  1 failed
(b) neue Rolle, deren SKILL nichts nennt              rc=0  1 passed   ← die blinde Seite
(c) office-SKILL verliert FR-0007 (leere Menge)       rc=1  1 failed
(d) Satz aus research/reviewer entfernt               rc=1  1 failed
(e) Absatz in EINEM Kit umformuliert                  rc=1  2 failed
(f) DUTY-Absatz nennt kein existierendes Kommando     rc=1  1 failed, 1 passed
(g) Kommandoliste verliert `sweep-pointers`           rc=1  1 failed
```

(b) ist **korrekt** und keine Lücke: `dev-team/agents/research-engineer.md` sagt selbst „never
writes production code" und sein SKILL nennt FR-0007 nicht — die Ableitung trifft. Sie hat aber eine
messbare Kante: eine bauende Rolle, deren SKILL die Regel nicht zitiert, verlangt den Satz nicht.
Der Boden `assert roles` fängt nur den Totalausfall.

---

## Benannte Reste (kein Blocker, gehören in die Löcherliste bzw. auf den Tisch des Leads)

**R1** — die Stock-Zeile unterscheidet „kein `run_command` aufgezeichnet" nicht von „alles löst auf"
(oben unter AC-3, mit Messung). Fix: `run_command` in die gedruckte Zeile, und einen dritten
Zustand für „nichts Wiederholbares".

**R2** — `H175`/`BUG-0257` nennt den Mechanismus **nicht**, den ich gemessen habe. Sein `observed`
und sein `limits` sprechen von Illustration-vs-Zeiger und vom fremden Store; die 27–39 Befunde eines
frischen Piloten sind **keins von beidem** — es ist das kit-eigene Material im Projekt selbst, das
`_swept_files` auszuschließen behauptet. Solange B1 offen ist, gehört diese Klasse mit ihrer Messung
in das Item (oder in ein eigenes), sonst ist sie gemessen und nicht aufgeschrieben.

**R3** — `tools/test_pointer_sweep.py:258–278` (`_sweeping_one_file_speaks`) ist eine **Kopie** der
Sweep-Schleife aus `report.pointer_sweep` (`_CITATION_RX` → `_CITATION_GLUE_RX` →
`_undecorated_citation` → `_TEST_NODE_RX` → `invariant_check_resolution` / `parse_id`). Das „nicht
überflüssig"-Ende des Stolperdrahts misst damit einen **zweiten** Leser, nicht den, der läuft.
Verengt sich `pointer_sweep`, bleibt die Kopie weit und der Stolperdraht behauptet weiter „wird
gebraucht". Fix: eine gemeinsame Hilfsfunktion (`_findings_in_text(state, text, parsed)`), die beide
aufrufen.

**R4** — Die Verfassungen behaupten mehr, als der Sweep baut. Der Absatz (identisch ×3) sagt:
`sweep-pointers` „reports **every** test name that does not resolve in the tree and every item id
this store does not hold". Gemessen im dev-Piloten: ein Zitat per **bloßem Dateinamen**
(`` `test_pricing.py::test_p95_is_under_budget` ``) steht neben einem mit Pfad in derselben Datei —
gemeldet wird nur das mit Pfad (`'src': 2` = ein Item + ein Knoten). Ebenso ungelesen: Knoten über
eine Klasse, Testdateien in Sprachen, die dieser Kernel nicht parst (`H110`). Der README-Absatz
macht es richtig („What it reads and what it deliberately does not is `kernel.report.pointer_sweep`")
— die Verfassung, also der Text, der in **jedes** Projekt geht, tut es nicht. Fix: derselbe
Halbsatz wie im README.

**R5** — Drei Zeilen der Bestandstabelle tragen ein Verdikt, das ihre **eigene** gemessene Zeile
nicht stützt:

```
| BUG-0016 | MEASURED-PASS | –             | 1/2 passed  |
| BUG-0025 | MEASURED-PASS | EVD-0086/pass | 2/5 passed  |
| BUG-0069 | MEASURED-PASS | EVD-0062/pass | 13/14 passed|
```

BUG-0069 ist der schwerwiegende: das Protokoll (Abschnitt 4, AC-6) und `EVD-0091`
(`result: fail`) sagen beide, der Bug **bleibt OPEN**; die Tabelle sagt in derselben Lieferung
MEASURED-PASS und zitiert eine ältere Evidenz. AC-1s Invariante lautet „a verdict without a
measurement is not a verdict" — hier gibt es eine Messung, und sie sagt das Gegenteil. Fix: für
diese drei Zeilen das Verdikt an die Zeile angleichen (bzw. das Vokabular der Tabelle im Kopf
definieren: was heißt MEASURED-PASS bei x < y).

**R6** — Zwei Dokumente behaupten über office und research etwas, was in deren Dateien nicht steht.
`stream-protocol.md` Abschnitt 1: „die office- und research-Verfassung tragen dieselbe Frage
bereits"; `docs/reviews/phase0-disposition.md` (neuer Eintrag +1383 B): „office and research already
carry the same question for their own root types."
**Gemessen:** in `team-kits/office-team/constitution/AGENTS.md` und
`team-kits/research-team/constitution/AGENTS.md` kommt weder `BUG-0022` noch `SUPERSEDED` vor
(0 Treffer). Was dort steht, ist die Frage **CR gegen BUG** (office Zeile 66/71: „is the approved
PROC still what the business wants?"; research Zeile 270/274: „is the approved RQ revision still what
we want to find out?") — nicht die Frage **CR gegen Wurzelersatz**, und der Ersatzweg wird gar nicht
beschrieben. Dabei hat `RQ` denselben Automaten wie `PR` (`_PR_LIKE`, `backlog_types.py:57–65`,
Terminal `SUPERSEDED`), die Klasse aus BUG-0022 ist in research also genauso erreichbar und
textlos. Fix: den Satz in beiden Dokumenten auf das Gemessene korrigieren; ob die research-Verfassung
die Frage bekommt, ist eine Entscheidung, kein Nacharbeitsauftrag dieser Runde.

**R7** — DEC-0080 (6) verlangt „every new READER … gets, before the report, a mutation in the
direction its docstring denies … the mutation and its red line stand in the protocol **per reader**".
Abschnitt 7 des Protokolls listet 27 Mutationen, aber **keine** für die vier Leser, die AC-3/AC-4
tragen: `report.confirmed_but_open`, `report._test_nodes_the_tree_no_longer_defines`,
`report.stock_rollup`, `report._check_nonempty_fields`. Ich habe fünf davon selbst gefahren (oben,
alle rot) — die Pflicht ist damit sachlich erfüllt, die Buchführung nicht. Nachtragen.

**R8** — Der Seiteneffekt im Hauptcheckout ist **im Bereich** (`docs/**` steht in `allowed_scope`),
liegt aber **außerhalb der Lieferung**: `git status` im Hauptcheckout zeigt
`M docs/POST_V2_WISHLIST.md` (+16/−1, 170 Zeilen = 155 verlinkt + 15 unverlinkt), und
`stream-stock.patch` enthält diese Datei nicht. Wer den Patch auf einen sauberen b7f282e anwendet,
bekommt den neuen Renderer und das alte Dokument. Das Protokoll nennt die Abhilfe
(`migrate-holes --reindex` nach dem letzten Loch) — sie muss in den Merge-Ablauf, sonst geht sie
verloren.

**R9** — `CLAUDE.md` sagt „Die vier Gates dieses Repos" und „registriert vier eigene
`PreToolUse`-Hooks aus `.claude/hooks/`". Gemessen in `.claude/settings.json`: fünf eigene
(`gate_lead_write_scope` ×2, `gate_spawn_needs_item`, `gate_commit_evidence`, `gate_test_scope`,
`gate_todo_items`) plus `team-kits/dev-team/hooks/gate_approval.py` auf beiden
`AskUserQuestion`-Ereignissen. `CLAUDE.md` steht in `forbidden_scope` — der Strom hat es richtig
benannt und nicht angefasst. Es steht aber **nur** im Protokoll und in keinem Item; das ist genau
der Zustand, den CLAUDE.md selbst als „verloren, sobald die Sitzung zusammengefasst wird"
beschreibt. Der Lead sollte es als Item führen.

---

## Pflichten 8–10

**Pflicht 8 (Rot-zuerst, Messungen, Mutationen, Löcher, Suiten, Host, Uhr): TEILWEISE.**
Rot-zuerst je Fix in einer Kopie außerhalb des Repos ist nachgestellt und stimmt (16 eigene
Mutationsläufe, alle rot außer den zwei absichtlich grünen Kontrollen (b) und dem Artefakt aus B2).
Die Löcher BUG-0256/0257/0261/0262 sind **kernelvergeben** (`hole_number` H174/H175/H179/H180),
tragen `limits`, `observed` mit MECHANISM, `repro`, und zitieren mit Modulpräfix
(`kernel.report.pointer_sweep`, `holes._prose_link`) ✓ — mit der Einschränkung R2. Die Suitenwahl
nach DEC-0080 (2) ist begründet und die Auswahlbreite hält: der einzige Test in
`.claude/hooks/test_gates.py`, der `validate_state` nennt
(`test_every_hole_states_a_verdict_and_an_unclosed_one_names_its_limit`), liegt **innerhalb** des
gefahrenen `-k "hole or index or agent or marker or statement or spawn or item"` (statisch über den
AST gemessen, nicht über den Namen geraten). Offen: R7.

**Pflicht 9 (Nähte): TEILWEISE.** `cli.py` ist ein eigener Block nach `validate` ✓. Verfassungen
tragen genau die drei angekündigten Änderungen (Kommandoliste ×3, Kommentarpflicht ×3, CR-Absatz nur
dev) — nachgezählt am Diff, nichts weiter ✓. `harness-lead.md` trägt DEC-0080 Regeln **1, 2, 3, 7**
mit Zeiger, `harness-verifier.md` Regel **6**, beide auf `DEC-0080` ✓ (und der Mutationstest dazu
ist rot zu bekommen). Die Modell-Pins sind da, aber B4. Journal additiv, drei Einträge, nicht
überschrieben ✓; `lead_package_sizes.json` konsistent mit dem Journal ✓. README nennt
`sweep-pointers` und sagt, was es **nicht** liest ✓. Reach-Naht: drei Piloten wirklich gefahren ✓ —
und genau dort fällt B1 an.

**Pflicht 10 (Handover): PASS.** Der Patch, unabhängig geprüft:

```
patch bytes=170687  CRLF lines=0  LF-only lines=2336
files with an index line: 32, new files: ['tools/test_pointer_sweep.py']
pre-image mismatches: 0        (jeder `index <old>..` gegen `git rev-parse b7f282e:<pfad>`)
VERSION 0 · project_memory 0 · CLAUDE.md 0 · .claude/hooks 0 · settings.json 0 ·
kit hooks 0 · kit templates 0 · model_tiers 0
```

33 Dateien, alle innerhalb `allowed_scope`. Kein Commit, kein Push, keine Installation. Protokoll
und Bestandstabelle liegen unter `project_memory/staging/TSK-0131/`. Verworfene Alternative in einer
Zeile ✓, Uhr gelesen ✓. **Token fehlen** mit genannter Begründung (der Prozess kann seinen eigenen
Verbrauch nicht lesen) — die (g)-Zeile muss der Lead aus dem Spawn-Protokoll füllen.

Zusätzlich gegengeprüft, weil es eine Eigenschaftsbehauptung im Rollentext ist: Gate 5, als echter
Haken-Prozess gegen meine Kopie, mit TSK-0131 im Store der Kopie:

```
full surface, no prefix         rc=2  … runs the WHOLE declared test surface `tools` …
full surface with DELIVERY_RUN  rc=0
one file / two files / node     rc=0 / rc=0 / rc=0
gate suite, whole file          rc=2
gate suite with -k              rc=0
```

Der Absatz in `harness-implementer.md` stimmt. (Ohne TSK-0131 im Store ist auch die
DELIVERY_RUN-Zeile rc 2 mit „leads no open item" — die Messung ist storeabhängig, was der Absatz
nicht behauptet.)

---

## Ausdrückliche Negativbefunde

**Gemessen und in Ordnung**

* `stock_rollup` als Dict-Display: der Statusschreib-Leser bleibt still; beide früheren Formen rot
  (`dict(found, …, status=…)` → 1 failed, `row["status"] = …` → 1 failed) — die Geschichte in
  Abschnitt 5 des Protokolls stimmt.
* `holes._prose_link` (immer verlinken / nie verlinken) und `_index_row_count` (nur verlinkte
  zählen): 3 Mutationen, alle rot; Basislauf `test_migrate_holes + test_pointer_sweep` 21 passed.
* Patch-Vorbilder, Zeilenenden, Bereich, verbotene Hunks (oben).
* Kein Fristproblem durch den neuen Rollup (Zeiten oben); `validate_state` selbst bleibt billig.
* Die Auswahlbreite der Gate-Suite deckt den einzigen `validate_state`-Leser dort ab.
* EVD-0086..0091 existieren, ihre `run_command`-Knoten sind echte Knoten, ihre Summaries benennen,
  was sie behaupten, und EVD-0091 ist ehrlich `fail`.
* Der Sweep im Arbeitsbaum: 31 Befunde, wie berichtet (davon 5× `DEC-0080` = Store-Naht).
* 12 Stichproben der Tabelle gegen den Store: kein Standabweichung, keine erfundene Evidenz.

**Nicht gemessen (bewusst)**

* Die **volle** Suite — sie gehört dem Merge (DEC-0050); die Zahlen 639 / 3142 / 370 / 360 aus dem
  Protokoll habe ich **nicht** nachgefahren, nur die betroffenen Auswahlen.
* `tools/test_repo_hygiene.py` und `tools/test_context_budget.py` in meiner Kopie: sie brauchen
  einen echten git-Baum, den die Kopie nicht hat. Die Befunde des Stroms dazu bleiben ungeprüft.
* Der gehostete CI-Lauf (BUG-0069) — er wartet auf den Push, wie berichtet.
* Ob der Agent-Aufruf einen `model`-Parameter trägt (B4): in diesem Repo nicht messbar, und ich
  habe kein Spawn-Werkzeug.
* Die Spiegelung `hooks/`/`settings/`/`templates/` (unberührt laut Diff, nicht byteweise
  nachgehasht).
* `office-team` `tools/`-Befunde des Piloten (7) nur gezählt, nicht einzeln gelesen.

---

## Urteil

**FAIL.**

**Blockierend für die Runde:** B1 (der Sweep fegt die Kit-Bäume, deren Ausschluss sein Docstring
behauptet — 39/27/30 unbearbeitbare Befunde in einem taufrischen Projekt jedes Kits), B2 (der
Pilot-Test kann daran nicht scheitern), B3 (`--expected-output ""` rc 0, Validator stumm, während die
Verweigerung „must name something" behauptet), B4 (ausgelieferte Eigenschaftsbehauptung über die
Spawn-Fläche ohne Messung).

**Als benannte Reste in die Löcherliste / auf den Tisch des Leads**, nicht rundenblockierend:
R1, R2 (gehört zu B1 und wird mit ihm aufgeschrieben), R3, R4, R5, R6, R7, R8, R9 — und AC-1/AC-2/
AC-6 als das, was sie sind: sauber gemessen, ehrlich unvollständig, wartend auf zwei
Nutzerentscheidungen (`dec-bug-closing-route.json`, `dec-decision-catcher.json`), sechs
Scope-Münzungen und vier Lieferfreigaben.
