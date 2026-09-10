# TSK-0133 — Merge-Verifikation Runde 1

Prüfer: `harness-verifier` (Opus, high; DEC-0081). Der Bericht wurde vom Prüfer als Text geliefert (seine
Rollenweisung verbietet ihm Bericht-`.md`-Dateien) und vom Lead unverändert hierher gelegt (2026-09-11 01:1x,
Uhr gelesen).

Uhr: Beginn `2026-09-11 00:33:05`, Ende `2026-09-11 01:09:35` (jede Zeit gelesen, `date`).
Gemessen gegen den laufenden Code des Haupt-Checkouts `C:/Offline Repos/AgentAndSkills` (Arbeitsbaum auf
`b7f282e` + Merge, uncommitted). Read-only im Repo. Eigenes Rig unter
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0133/verify/`: `mkcopy.py`, `rig.py`, `ast_union_check.py`,
`batch*.py`, `probe_*.py` — jedes verweigert den Lauf außerhalb seines Verzeichnisses (gemessen: `refused: run me
from …`) und öffnet jede Datei **binär**. Arbeitsbaum `verify/mut/` = echter `git clone --no-local` + binär
kopierter Arbeitsbaum + `git add -A` (378 getrackte `team-kits/`-Dateien, 287 Änderungen gegen HEAD), damit
`git ls-files`-Leser dasselbe sehen wie der Hauptbaum. Volle `tools/`-Suite **nicht** neu gefahren (Gate 5 /
DEC-0050); nur die Suiten, die lesen, was ich angreife — je ein pytest, jeder mit Frist.

---

## 1. Blockierende Befunde

### B1 — Die zwei Lieferartefakte DIESER Runde tragen CRLF; die im Protokoll benannte Abhilfe erreicht sie nicht
`project_memory/staging/TSK-0133/run-full-suite.txt:1` und `run-gates-suite.txt:1`

Gemessen (binär, 01:0x): `run-full-suite.txt` 119 CRLF-Paare / 3 blanke LF, `run-gates-suite.txt` 9 CRLF / 3 LF.
Beide sind heute **untracked** (`git ls-files --others` listet sie), darum ist
`tools/test_repo_hygiene.py::test_no_tracked_text_file_checks_out_with_crlf` im Hauptbaum grün — der vom Lead
gemeldete Stand „32 passed" ist echt, die Gen-4-Dateien sind normalisiert (`git ls-files --eol --
project_memory/staging/TSK-0126/`: `i/lf w/lf` ×8).

Sobald der Lead sie für den Commit stagt — und §13 verlangt genau das, beide sind `--artifact-ref` der zwei
EVD-Zeilen — ist die Lieferkriteriums-Suite rot. In meiner Kopie mit exakt diesem Zustand:

```
i/lf    w/mixed  project_memory/staging/TSK-0133/run-full-suite.txt
i/lf    w/mixed  project_memory/staging/TSK-0133/run-gates-suite.txt
tools/test_repo_hygiene.py: 1 failed, 31 passed
E AssertionError: 2 tracked text file(s) carry CRLF on disk … Files:
  ['project_memory/staging/TSK-0133/run-full-suite.txt',
   'project_memory/staging/TSK-0133/run-gates-suite.txt']
```

Und die Zeile, die §13 als Vorbedingung vorschreibt, **repariert sie nicht** — gemessen, beide Modi:

```
python tools/normalise_line_endings.py --apply   -> rc 1
0 file(s) normalised:
2 file(s) REFUSED -- each one is named with what stopped it:
  project_memory/staging/TSK-0133/run-full-suite.txt: no blob in HEAD -- this file is not committed …
  project_memory/staging/TSK-0133/run-gates-suite.txt: no blob in HEAD -- …
```

Das ist per Konstruktion so (Modul-Docstring: „a file is rewritten only when its CRLF-normalised bytes are
BYTE-FOR-BYTE the blob `HEAD` holds"). Die Runde reproduziert damit in ihren **eigenen** Artefakten genau den
BUG-0025-Defekt, den sie als M12/Z-Zeile gegen Generation 4 gemeldet hat, und `--result pass` der ersten
EVD-Zeile wird im Moment des Commits falsch.
**Minimaler Fix:** die zwei Dateien vor dem Stagen einmal LF-schreiben (binär lesen, `\r\n`→`\n`, binär zurück —
kein Inhalt ändert sich), dann `tools/test_repo_hygiene.py` voll; erst danach ist der Platzhalter `<its result>`
in EVD-Zeile 1 füllbar. **Blockiert die Runde** (der Commit, den der Lead danach fährt, trägt sonst den Defekt).

### B2 — Rot-zuerst-Zeile `m23` reproduziert nicht: der Gate-2-Test misst die DEC-Tür gar nicht mehr
`.claude/hooks/test_gates.py:1632-1641` (Rumpf + Typwahl), Kommentar `:1628-1631`

Protokoll §5 M13 und Rig-Zeile `m23` behaupten: „der DEC-Rumpf verliert `work`" → **RED**. Gemessen 2026-09-11 in
meiner Kopie, EINE Änderung (`"check": "probe", "work": DEC_WORK_NONE}` → `"check": "probe"}`), Schiedsrichter
genau der genannte Test:

```
unmutiert:  1 passed, 547 deselected in 11.19s   (rc 0)
mutiert:    1 passed, 547 deselected in 11.10s   (rc 0)   <- GRÜN statt RED
```

Der Grund ist die Typwahl direkt darunter, gemessen mit dem Kernel-Vertrag der Kopie:

```
WITH work     candidates=['DEC', 'INV'] -> subject DEC
WITHOUT work  candidates=['INV']        -> subject INV
```

Der Test fällt also nicht, er **wechselt still das Subjekt** — weg von der `DEC`-Tür, um die M13 ging. Damit ist
der Satz im Kommentar („`work` is what the CAPTURE DOOR asks of a decision … a body without it was rc 1 here on
the generation-5 merge's gate run") eine Deckungsbehauptung, die keine Messung trägt, und der Fix hält die
Regression, für die er gebaut wurde, nicht auf. Das ist die Klasse aus `DEC-0080` (6) im Fix selbst.
**Minimaler Fix:** das Subjekt festnageln statt es wählen zu lassen — `assert "DEC" in candidates` vor
`item_type = candidates[0]`, oder über **alle** `candidates` laufen; danach ist die Mutation rot. Zeile `m23` im
Protokoll und in `redfirst.log.json` korrigieren. **Blockiert** (eine als rot protokollierte Zeile, die grün
ist, ist teurer als keine).

### B3 — Der Anspruchs-Leser (DEC-0089 (5)) lässt die verworfene Cloud-Routine als Mechanismus durch, sobald das Wort „Desktop" im Satz steht
`tools/test_radar_trigger.py:187` (`schedule_claim_offence`)

```python
if stem not in sentence and not re.search(r"\bdesktop\b", sentence, re.IGNORECASE):
    return "names neither %s nor the Desktop task as the mechanism" % stem
```

Die Prüfung ist ein **positiver Worttest**, keine Prüfung, dass der Satz nicht den verworfenen Mechanismus
benennt. Gemessen, je eine Änderung in `radar/README.md`, Schiedsrichter die ganze Datei
`tools/test_radar_trigger.py`:

| Zeile | eingefügter Satz | Ergebnis |
|---|---|---|
| v00 | — (Kontrolle) | GRÜN, 9 passed |
| **v01** | „The claude.ai cloud routine starts the radar-watcher every Friday from the Desktop." | **GRÜN, 9 passed** |
| v02 | „The claude.ai cloud routine is the mechanism that starts both watchers every Friday." | RED (= m10 des Umsetzers) |

Ein einziges Wort trennt die verweigerte von der akzeptierten Fassung. Der eigene Docstring des Lesers
(`:174-176`: „a sentence naming neither (the cloud routine, a bare ‚schedule') is refused **whatever else it
says**") und der Modulkopf („refuses any AUTOMATION claim the declaration does not back") behaupten mehr, als der
Code baut — und `--describe` führt `cloud_option.built: false`, `rejected_by: DEC-0089`. `m10` hat die
Schreibweise gemessen, die der Umsetzer zufällig probiert hat, nicht die Klasse.
**Minimaler Fix:** den Satz gegen die Deklaration prüfen statt gegen ein Wort — ein Satz, der eine
Mechanismus-Vokabel aus `cloud_option` (bzw. irgendeinen Mechanismus mit `built: false`) benennt, ist verweigert,
unabhängig davon, was sonst darin steht; die v01-Zeile als neue Rig-Zeile. **Blockiert** (der Leser ist der
gebaute Nachweis für PR-0010 Invariante 1 und AC-1).

### B4 — N4-2 ist auf dem gemergten Baum nicht geschlossen: die Effort-Achse kann den Leiter-Absatz verlassen, ohne dass etwas rot wird
`tools/test_review_procedure.py:1296-1310` (`_own_block`), `:1422-1427` (Docstring des Tests)

Auftrag: „N4-1 und N4-2 auf dem gemergten Baum mit je EINER Änderung". N4-1 hält (siehe §3). N4-2 nicht:

EINE zusammenhängende Änderung in `team-kits/dev-team/constitution/AGENTS.md:376-381` — die Effort-**Regel** des
Leiter-Absatzes entfernt („effort **high** by default and **xhigh** when the goal's `class` is `large`" … „and
the EFFORT from the goal") —, Schiedsrichter `test_no_lead_skill_keeps_its_own_copy_of_the_scaling_rule`:

```
w01  GREEN (erwartet RED)  2.3s
```

Nachgemessen, warum:

```
ORIGINAL     -> qualifying statements: 1 ; effort words in own block: ['effort','EFFORT','effort','effort','effort']
MUTATED w01  -> qualifying statements: 1 ; effort words in own block: ['effort','effort','effort']
```

Die drei übrigen sind **beiläufige Erwähnungen im selben Aufzählungspunkt** („**What it does not do:** the effort
is derived and shown, never forced", „no per-spawn effort parameter", „the child runs on the `effort:` its
installed definition carries"). `_own_block` schneidet an `^(?:[-*+]\s|#|\s*$)`, und die fettgeführten Einschübe
mitten in der Zeile sind keine Blockgrenze — der „eigene Block" ist der ganze 1424-Zeichen-Punkt. Dev und research
sind identisch gebaut (je 5 `effort`-Wörter, 1429 bzw. 1424 Zeichen).

Damit sagt der Docstring von `_own_block` („so taking the axis out of that one paragraph is the mutation this
block reader has to make red") etwas, das der Code nicht baut. Die Zeiger-Hälfte hält dagegen: `w02` (PM-Skill
verliert „constitution's ladder paragraph") = **RED**.
**Minimaler Fix:** die Effort-Achse dort verlangen, wo sie eine Regel ist — im **Lead-in-Satz** des fetten
Statements bzw. gemeinsam mit einer Sprossen-Nennung in EINEM Satz, statt irgendwo im Block; `w01` als Rig-Zeile.
**Blockiert** nach Hausregel 3 (ein Kommentar, der Schutz behauptet, den der Code nicht baut, ist ein
FAIL-Grund, auch wenn der Code sonst richtig ist).

---

## 2. Nicht blockierend (Prosa gegen Code / Aktenlage, DEC-0088 (c))

**P1 — `_hole_prose` behauptet ein geteiltes Prädikat, das es nicht benutzt.** `.claude/hooks/test_gates.py:4710`:
„The predicate is the kernel's own (`holes._prose_link`: the file `docs/holes/<n>.md` exists)". Der Code
(`:4715-4716`) baut den Pfad selbst; `kernel.holes._prose_link` (`team-kits/kernel/holes.py:285`) nimmt zusätzlich
ein konfigurierbares `holes_dir`. Verhalten heute korrekt (siehe §3, g1/g2/g3 alle RED), aber der Satz ist unwahr
über die Zeile darunter.

**P2 — `BUG-0272.yaml` `observed`, zweiter Aufzählungspunkt: zwei der drei Kontrollen mit falschem rc.** Ich habe
die Kette selbst reproduziert, im Hauptcheckout, als echte Hook-Prozesse:
`grep -c "\`a\`, \`b\`" README.md` → **rc 2**, „no tool call in this repo may write C:\" (H188 reproduziert, wörtlich).
`grep -c "\`ladder\`" README.md` → rc 0, druckt `1` ✔ (wie im Item).
`grep -c "\`a\`.*\`b\`" README.md` → **rc 1**, `grep -c "a.*b, c" README.md` → **rc 1** — das Gate lässt beide
durch (das ist der Punkt), aber das Item schreibt „rc 0". Die Aussage über den Mechanismus hält, die Zahl nicht.

**P3 — Das Protokoll von Lieferlauf-Versuch 2 existiert nicht mehr.** Versuch 3 hat
`project_memory/staging/TSK-0133/run-full-suite.txt` überschrieben (heute: `2026-09-10 23:13:05 START` … `1
failed, 4843 passed, 14 skipped … (0:38:19)` … `23:51:26 DONE`); im Scratch liegt nur
`run-full-suite-attempt1-aborted.txt` (mtime 22:30:59). Damit stützen sich der „Vorgefunden"-Absatz („`3 failed,
4841 passed … DONE 2026-09-07 00:29:09`"), die Versuch-2-Zeile in §10, Z14 und der Summary-Satz der ersten
EVD-Zeile auf ein Artefakt, das niemand mehr lesen kann. Die drei Fixes daraus habe ich stattdessen selbst
rot-zuerst nachgemessen (m20/m21/m22, §3) — die Sache hält, die Akte nicht.

**P4 — Dateizahlen in §16.** „83 geänderte Dateien außerhalb `project_memory/`, 15 davon neu". Gemessen 00:4x:
`git diff --name-only HEAD -- . ':(exclude)project_memory'` = **90**, davon **17** neu (`A`). Die „15" aus §2 ist
die Zahl der Patch-Neudateien und stimmt; die §16-Zahl ist nicht die des Baums.

**P5 — Naht 2 sagt „Pins EINMAL neu geschrieben, nachdem alles stand (§9)", §9 nennt 20:56:05.**
`tools/constitution_section_pins.json` hat mtime `2026-09-10 23:05:55`, also ein zweites Pinnen in Sitzung 2 für
M11 — §10 sagt das auch („Sektion neu gepinnt (23:05:54)"). Die beiden Sätze widersprechen sich; §10 ist der wahre.

**P6 — Erklärte, aber nirgends als Loch geführte Blindstelle des Anspruchs-Lesers.** Ein Kadenz-Satz ohne
Anspruchswort wird angenommen: `„The watcher duo runs once a week without a human."` in `radar/README.md` → **GRÜN**
(v03). Der Modul-Docstring erklärt das ausdrücklich als gewollt („A cadence on its own … is an intent and not a
claim of a mechanism"), also keine Regel-3-Verletzung — aber es ist genau die Umformulierung des Satzes, gegen den
das Modul geschrieben wurde (b7f282e `radar/README.md` Zeile 3), und sie steht in keiner Lochzeile. Gehört neben
H182 in die Liste.

---

## 3. Negative Befunde — **gemessen**

**Naht 1 (`kernel/cli.py`, AST-Vereinigung), mit meinem eigenen Leser** (`ast_union_check.py`: Basis-Blob
`b7f282e` + jeder Patch einzeln in ein Wegwerf-Repo, dann `ast.walk` über alle
`Function/AsyncFunction/ClassDef` und alle `add_parser`-Literale):
```
base 20 defs / 24 commands | ladders 20/25 | stock 20/25 | office 21/24 | merged 21/26 | union 21/26
MISSING defs [] EXTRA defs [] MISSING commands [] EXTRA commands []
je Strom: defs lost [] commands lost []
neue Kommandos gegen Basis: ['ladder', 'sweep-pointers']
```
Keine Definition eines Patches verloren, nichts Überzähliges. (Meine Definitionszählung weicht von der des
Protokolls ab — 20/21 statt 26/27 —, die Kommandozahlen 24→26 stimmen überein; das Urteil „0 fehlend, 0
überzählig" halte ich mit meinem eigenen Leser.)

**Patch-Eingangsmessung selbst nachgerechnet:** 31 / 37 / 28 `diff --git`-Köpfe, 296 181 / 258 531 / 270 991 B.
**Kein VERSION-Hunk**, **kein Hunk in kanonischem `project_memory/`** — die vier `project_memory`-Treffer im
Office-Patch liegen alle unter `team-kits/office-team/templates/project_memory/`.

**Naht 2 (Verfassungen):** Kommentar-Pflicht-Absatz **byte-identisch ×3** (je 2198 B, Vergleich der Bytes).
Mutationen: `q2` (ein Wort Drift in EINER Verfassung) → `test_role_contracts::…share_is_one_text` **RED**; `q3`
derselbe Drift → `test_review_procedure::…comment_discipline_duty` **RED**. §0-Kommandofläche: `q1` (dev-Liste
verliert `sweep-pointers`) → `test_hooks::test_every_span_that_presents_the_command_surface_names_all_of_it`
**RED**; Kontrolle grün.

**Naht 3 (neun Rollen):** 9 bauende Rollen, je **genau ein** Pflicht-Statement, alle neun **byte-identisch** (md5
`cceb8c9230f2`): dev backend/devops/frontend/quality, office office-developer, research
data-analyst/research-engineer/researcher/reviewer.

**Naht 4 (`STALE_LADDER_TEXTS` = `{}`), beide Enden rot:** `y01` (toter Eintrag bleibt stehen) **RED**; `y02`
(dev-Vorlage spricht `sonnet-high -> …` wieder) **RED**. Zeiger-Hälfte: `w02` **RED**.

**Naht 5 (drei Vorlagen):** keine getrackte Kit-Datei buchstabiert noch einen `<rung>-<effort>`-Schritt (Test
grün, `y02` beweist, dass der Leser scharf ist).

**Naht 6 (`_receipt_fields`) — N4-1 in beiden Richtungen und die Zeile selbst:**
`x01` Filter verwirft **jeden** Befund über die Quittung → `test_the_receipt_filter_drops_the_receipt_and_nothing_else` **RED**;
`x02` Filter fällt auf den **Typ** zurück (N3-B1) → derselbe Test **RED**;
`x03` `DEC_WORK_FIELD: DEC_WORK_NONE` aus `migrate.py` entfernt → `test_the_run_receipt_carries_work_none_and_owes_no_carrier_warning` **RED**.

**Naht 7:** `office-team/skills/office-manager/SKILL.md` trägt beide Schritte (`work`-Klausel Z. 110, „Letters
that leave the house" Z. 221, Codex-Route Z. 229).

**Naht 8:** `tools/lead_package_sizes.json` = dev 56 138 / office 62 397 / research 58 060; drei additive
`GREW`-Journalzeilen der Merge-Runde in `docs/reviews/phase0-disposition.md:2020-2022`, die Strom-Zeilen davor
unangetastet (172 `GREW`-Zeilen gesamt). `README.md` nennt `ladder` und `sweep-pointers`.

**Naht 9 (BUG-0249):** `z01` (`for key in (RUNG_KEY, EFFORT_KEY)` → `for key in ()`) →
`test_the_session_brief_shows_the_rung_and_effort_a_lease_wrote_on_the_task` **RED**.

**Naht 10:** kein Strom berührt `.claude/hooks/test_gates.py` — die `.claude`-Köpfe aller drei Patches sind
ausschließlich die fünf `agents/*.md`. Keine AST-Vereinigung nötig, Behauptung korrekt.

**Naht 11 (Zeiger gegen den LIVE-Store):** Kernel-`sweep-pointers` auf dem gemergten Baum: **30 tote Zeiger, 0
unter `team-kits/`**, alle Illustrationsklasse (Platzhalter `PROC-0001`/`DEC-0001`/`TSK-0404`/`BUG-0404`,
Fixture-Strings in `test_pointer_sweep.py`). `tools/test_review_procedure.py -k "pointer or hole or resolves"` 5
passed; `tools/test_pointer_sweep.py` 7 passed; `.claude/hooks/test_gates.py -k hole` **6 passed**; `-k
reference_to_a_measurement` grün.

**DEC-0089 wie getragen:** `--describe` als Prozess: `mechanism` = „a Claude Desktop scheduled task per watcher on
the maintainer's host (DEC-0089)", `starts_itself` = `{radar-watcher: true, codex-watcher: false}`,
`cloud_option.built = false` / `rejected_by: DEC-0089`, Kadenz-Evidenz sieben Freitage. `--due` ehrlich für W37
(beide fällig, Codex mit „no Desktop task with a measured cadence is recorded for it").
`task_file_present_on_this_host` wird nur **gemeldet** — `starts_itself` liest es nicht, kein Test liest es (grep:
kein Treffer in `tools/test_radar_trigger.py`); die erklärte Abweichung von DEC-0089 (3) ist also wahr.
`radar/routine.json` entspricht der von `--describe` veröffentlichten `record.shape`. BUG-0269 im Store korrigiert
(Indexzeile = Store-Titel/Status).

**Lochliste = Store:** `docs/POST_V2_WISHLIST.md` 178 Indexzeilen ↔ 178 Items mit `hole_number` im ganzen Store
(aktiv **und** `archive/BUG/2026/`), **0** in der einen und nicht der anderen Menge, **0** Zeile mit abweichender
Item-Id oder abweichendem Status. H166–H188 einzeln geprüft, inkl. H174 = `BUG-0256` `DUPLICATE` (archiviert).
H188/BUG-0272-Kette reproduziert (siehe P2).

**Stempel:** `python tools/bump_kit_version.py` auf dem Endbaum (in meiner Kopie):
```
dev-team: unchanged (2026.09.06-1) | office-team: unchanged (2026.09.10-1) | research-team: unchanged (2026.09.06-1)
rc 0 ; keine VERSION-Datei angefasst
```

**Die zwei Lieferläufe, Endzeilen selbst gelesen:** `run-full-suite.txt`: `2026-09-10 23:13:05 START` … `1
failed, 4843 passed, 14 skipped, 1 warning in 2299.29s (0:38:19)` … `rc=1` … `2026-09-10 23:51:26 DONE`.
`run-gates-suite.txt`: `00:16:28 START` … `548 passed in 625.69s (0:10:25)` … `rc=0` … `00:26:55 DONE`.
Deckungsgleich mit §10.

**Die vier Lieferlauf-/Gate-Fixes rot-zuerst nachgemessen** (Versuch-2-Log ist weg, P3): `m20`
(`test_e2e`-DEC-Rümpfe verlieren `work: none`) **RED**; `m21` (`letter_draft.py`-Abhilfe nennt wieder
`staging/<TSK-ID>/correspondence.yaml`) →
`test_no_remedy_literal_this_repo_ships_names_a_place_inside_a_state_directory` **RED**; `m22` (Büro-Skill
verliert die Codex-Route) → `test_a_reference_skill_named_for_a_session_agent_is_named_by_a_text_it_reads`
**RED**; `m24`-Äquivalent `g1` (`_hole_prose` liest `source` wieder als Pfad) →
`test_every_reference_to_a_measurement_leads_to_one` **RED**. Zusätzlich mein eigener Angriff auf denselben Leser
in der Richtung, die sein Docstring bestreitet: ein **erfasstes** Loch zitiert ein nicht existierendes
`docs/reviews/…md` (**g2 RED**) bzw. ein existierendes ohne den Eintrag (**g3 RED**) — der erweiterte Leser liest
die 23 erfassten Löcher wirklich.

**Uhr-Abgleich (jede Protokollzeit gegen einen echten mtime):** `letter_draft.py` 23:03:30 / Büro-SKILL 23:03:32
(§10 „23:03") · office `VERSION` 23:11:07 (§9) · dev/research `VERSION` 21:14:39 (§9 „21:14:40") · Sektions-Pins
23:05:55 (§10) · Größenrekord 20:56:00 (§9 „20:55:59") · `radar/routine.json` 20:47:03 (Vorgefunden) ·
`test_gates.py` 00:03:17 · `docs/reviews/…-measurements.md` 00:15:33 · Protokoll 00:30:03 (§16 „00:29:53") ·
Scratch: `patch_intake.log.json` 20:17:28, `describe-merged.json` 20:51:23, `attempt1-aborted` 22:30:59,
`reading-suites` 23:10:24, `redfirst-full.log` 23:12:33, `redfirst.log.json` 00:10:59. **Keine hochgerechnete Zeit
gefunden.** `redfirst.log.json`: 25 Zeilen, `every_row_as_expected: true` — inhaltlich aber siehe **B2**.

**Weitere Lesesuiten, die lesen, was ich angegriffen habe** (je einzeln, mit Frist): `test_office_package` 72 ·
`test_ladder` 35 · `test_model_pins` 5 · `test_shortening_net` 36 · `test_context_budget` 42 ·
`test_role_contracts` 30 · `test_kit_neutrality` 6 · `test_radar_trigger` 9 · `test_repo_hygiene` 31 passed / 1
failed (= B1). Spiegel: `gate_dispatch.py` ×3 md5 `fd1712bf268653ed04b68cff42ab60f1`.

**EVD-Zeilen (§13):** beide `--artifact-ref` sind state-relativ (`staging/TSK-0133/run-full-suite.txt`,
`…/run-gates-suite.txt`), existieren und liegen **innerhalb** des Repos, kein Digest. `--result pass` der
**zweiten** Zeile ist ehrlich (rc 0, 548 passed). `--result pass` der **ersten** ist es erst, wenn B1 behoben ist
— heute steht dahinter ein Log, dessen letzte Zeile `1 failed` sagt, und ein Platzhalter `<its result>`.

---

## 4. **Nicht** gemessen (ausdrücklich)

* Die volle `tools/`-Suite (Gate 5 / DEC-0050 / Auftrag (7)). Ich habe nur die DONE-Zeile gelesen und nachgerechnet.
* Die Token-Zahlen der (g)-Tabelle (Umsetzer/Prüfer aller drei Ströme). Kein Zähler von mir erreicht einen fremden
  Prozess. Die Tabelle sagt für TSK-0131 R1–R3 selbst „die Berichte nennen keine Zahl" — das ist die ehrliche Form;
  geschätzt wird nichts.
* Die Zuschnitt-Befunde **Z1, Z3, Z4, Z5, Z7, Z8** — Aussagen über fremde Sitzungen und den Rundenlog; nicht
  nachgemessen. **Z2, Z6, Z9–Z14** sind durch die Artefakte oben gedeckt bzw. hier bestätigt (Z12 durch die
  Laufzeiten 1:54 vs 0:38 am selben Baum, Z14 nur mittelbar — P3).
* Die drei Roten des Versuchs 2 in ihrer **Originalform** (Log überschrieben, P3). Ersetzt durch meine eigenen
  Mutationen m20–m22.
* Die Wandzeit-/Rundenangaben der Ströme (Spalten 2–6 der (g)-Tabelle) außerhalb der oben geprüften mtimes.
* PR-0009 AC-1/AC-2 und PR-0010 AC-6 als **Pilot-Prozesse** (scaffolded pilot) — ich habe die Suiten gefahren,
  keinen Piloten aufgesetzt.

---

## 5. Pro Ziel, pro AC (Stand des gemergten Baums)

**PR-0008** — AC-1/AC-2 (Bestandsaufnahme): im Store, nicht Gegenstand des Merges, nicht nachgezählt. AC-3:
`report.stock_rollup` + `report["stock_lies_upward"]` gebaut ✔. AC-4: `NONEMPTY_FIELDS = {"EVD": …, "TSK":
("expected_outputs",)}` gebaut ✔. AC-5 (CR-Frage): dev + research tragen sie, office nicht — als G5-1-Runde-2-
Entscheidung R6 benannt ✔. **AC-6: 10 von 11** — BUG-0025/0033/0083/0084/0085/0086/0088/0089/0090/0091
`VERIFIED` und in `archive/BUG/2026/`; **BUG-0069 bleibt `OPEN`**, korrekt als auf den gehosteten CI-Lauf wartend
in §14 geführt ✔. AC-7 (Kommentar-Disziplin): drei Verfassungen byte-identisch, neun Rollen byte-identisch,
mechanische Hälfte `sweep-pointers` gebaut und benannt ✔.

**PR-0009** — AC-1/AC-3/AC-5/AC-6 durch `test_office_package` (72 passed) und die Kit-Dateien getragen; AC-2
(Andockstelle) mit `invoice_intake.py` + `docs/office/invoice-app-docking-point.md` vorhanden. AC-4 (acht
Übernahmen) nicht nachgezählt. **Merge-relevant:** M10 (`letter_draft.py`-Abhilfen, DEC-0024) rot-zuerst gehalten
✔, M11 (Codex-Route) rot-zuerst gehalten ✔. Kein Befund.

**PR-0010** — AC-1: Mechanismus + Leser gebaut, aber der Leser hat das Loch **B3**; die Codex-Hälfte wartet
erklärt auf den Nutzer (§14.4) ✔/✗. AC-2: `radar/2026-09-06-codex.md` liegt ✔. AC-3: `STALE_LADDER_TEXTS = {}`,
Tripwire beidseitig rot ✔. AC-4: nicht gesondert nachgemessen. AC-5: Rollout-Zeile im Protokoll ✔. **AC-6:
Session-Brief-Hälfte (BUG-0249) gebaut und rot-zuerst gehalten** ✔; die Absatz-Hälfte (N4-2) trägt **B4** ✗. AC-7:
Zeiger gegen den Live-Store grün ✔.

---

## 6. Urteil

**FAIL.**

Der Merge selbst ist handwerklich sauber: die elf Nähte sind auflösbar, keine Definition ist verloren, der Stempel
steht, Index = Store, die Uhr ist gelesen, und zehn von vierzehn Rot-zuerst-Zeilen, die ich nachgefahren habe,
sind rot wie protokolliert. Was ihn aufhält, sind vier Befunde — drei davon greifen den **Fix** an, nicht den Strom:

* **B1** blockiert den Commit: die zwei Dateien, auf die die EVD-Zeilen zeigen, machen die Lieferkriteriums-Suite
  rot, sobald sie gestaged werden, und die im Protokoll benannte Abhilfe verweigert sie. Ein Fix von einer Zeile,
  aber ohne ihn ist `--result pass` falsch.
* **B2** blockiert: eine als **RED** protokollierte Zeile ist **GRÜN** — der Gate-2-Test wechselt still das Subjekt
  von `DEC` auf `INV`, statt zu fallen. Deckung behauptet, nicht gebaut.
* **B3** blockiert: der Anspruchs-Leser, der PR-0010s Invariante 1 trägt, hat einen Ein-Wort-Ausweg für genau den
  Mechanismus, den DEC-0089 verworfen hat.
* **B4** blockiert nach Hausregel 3: der Runde-4-Rest N4-2 ist nicht geschlossen, und der Docstring von `_own_block`
  behauptet, er sei es.

Keiner der vier verlangt eine neue Runde über einen Strom; alle vier sind Zeilen im gemergten Baum plus je eine
Rig-Zeile. **B1, B2, B3, B4 blockieren die Runde**; **P1–P6 gehören als benannte Reste** in die Löcherliste bzw.
in die Generation-5-Retrospektive, nicht in einen Blocker. Nach den vier Fixes sind die Lesesuiten der geänderten
Dateien voll zu fahren (`tools/test_repo_hygiene.py`, `tools/test_radar_trigger.py`,
`tools/test_review_procedure.py`, `.claude/hooks/test_gates.py`) — Kit-Dateien berührt keiner der Fixes, ein
Neustempel ist nicht nötig; für B4 ist `team-kits/dev-team|research-team/constitution/AGENTS.md` **nicht** zu
ändern (der Text ist richtig, der Leser ist zu weit), also bleibt auch dort der Stempel stehen.
