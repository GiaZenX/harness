# TSK-0133 — Merge-Verifikation Runde 2 (kurz, nur über die Runde-1-Befunde, DEC-0088 (b))

Prüfer: `harness-verifier` (Opus, high). Als Text geliefert, vom Lead unverändert hierher gelegt (2026-09-11 01:4x,
Uhr gelesen).

Uhr: `2026-09-11 01:37:36` bis `01:45:41`, jede Zeit gelesen. Kopie neu gezogen (2355 Dateien, binär, ohne `.git`),
Mutationsbaum neu gebaut als echter `git clone --no-local` + Arbeitsbaum + `git add -A` (378 getrackte
`team-kits/`-Dateien, 291 Änderungen gegen HEAD). Ein pytest zur Zeit, jeder mit Frist, keine volle `tools/`-Suite.

---

## B1 — CRLF in den zwei Lieferartefakten → **GESCHLOSSEN**

`project_memory/staging/TSK-0133/run-full-suite.txt`, `run-gates-suite.txt`

Bytes selbst gezählt (binär): **0 CRLF-Paare** in beiden, ebenso in allen sechs übrigen Staging-Dateien.
`run-full-suite.txt` 9 685 B → **9 566 B**, exakt −119 = die 119 entfernten CR-Bytes, sonst nichts; die Endzeilen
stehen unverändert (`1 failed, 4843 passed, 14 skipped … (0:38:19)` / `rc=1` / `2026-09-10 23:51:26 DONE`).
*Anmerkung, damit die Aktenlage stimmt:* `run-gates-suite.txt` ist **nicht** die normalisierte alte Datei, sondern
das Log des Nachlaufs der Prüfrunde 1 (`548 passed in 648.04s (0:10:48)`, `rc=0`, `2026-09-11 01:35:38 DONE`) —
inhaltlich ein anderer, grüner Lauf. Für den ist „119/9 → 0, kein anderes Byte" so nicht prüfbar; für
`run-full-suite.txt` ist es arithmetisch bewiesen.

Der eigentliche Blocker — rot, sobald gestaged — ist weg. In meiner Kopie, mit **allem** gestaged:

```
i/lf  w/lf  attr/text=auto eol=lf   project_memory/staging/TSK-0133/run-full-suite.txt
i/lf  w/lf  attr/text=auto eol=lf   project_memory/staging/TSK-0133/run-gates-suite.txt
   (ebenso: merge-protocol.md, verify-round-1.md, die vier Payload-/Korrektur-JSONs)

tools/test_repo_hygiene.py voll  ->  32 passed, 1 warning in 125.80s (0:02:05)   rc=0
```

`--result pass` der ersten EVD-Zeile ist damit über den Baum, den der Lead committet, eine wahre Aussage.

## B2 — Rot-zuerst-Zeile `m23` war grün → **GESCHLOSSEN**

`.claude/hooks/test_gates.py:1644-1646` (`assert "DEC" in candidates`), `:1647` (Schleife über **alle** Kandidaten)

Meine unveränderte Runde-1-Mutation, gleicher Schiedsrichter:

| Zeile | eine Änderung | Runde 1 | Runde 2 |
|---|---|---|---|
| `m23` | Rumpf verliert `"work": DEC_WORK_NONE` | GRÜN (1 passed) | **RED**, 6.8 s |

Kontrolle unmutiert `1 passed, 547 deselected`. Ich habe zusätzlich gemessen, **welche Zeile trägt**: die Schleife
allein trägt nichts (`for item_type in candidates[:1]` → grün, wie erwartet, weil mit `work` ohnehin `DEC` an
erster Stelle steht), und mit **entferntem** Wächter *und* fehlendem `work` ist der Test wieder **grün** — das Loch
aus Runde 1 exakt. Es hängt also an genau einer Zeile, und die ist rot-zuerst gemessen. Der Kommentar darüber
(`:1634-1638`) nennt jetzt die Messung („with `work` the candidates were DEC and INV, without it INV alone") und
deckt sich mit meiner eigenen Sondierung.

## B3 — Cloud-Anspruch durch das Wort „Desktop" hindurch → **GESCHLOSSEN (für die gemeldete Klasse)**

`tools/test_radar_trigger.py:188-199` (Vorabprüfung gegen `built: false`), `tools/radar_routine.py:338`
(`cloud_option.named_as`)

| Zeile | Satz in `radar/README.md` | Runde 1 | Runde 2 |
|---|---|---|---|
| `v01` | „The claude.ai cloud routine starts the radar-watcher every Friday **from the Desktop**." | GRÜN (9 passed) | **RED**, 3.6 s |
| `v02` | dieselbe ohne „Desktop" | RED | **RED** |

Kontrolle unmutiert 9 passed. Die Regel fragt jetzt zuerst die Deklaration (`for key, option in
described.items(): … option.get("built") is False`) und ist damit abgeleitet statt aufgezählt — die **Namen**
bleiben allerdings eine Liste (`named_as = ["claude.ai", "cloud routine", "RemoteTrigger"]`). Siehe **N1**.

## B4 — N4-2 nicht geschlossen → **GESCHLOSSEN (für die gemeldete Mutation)**

`tools/test_review_procedure.py:1317-1334` (`_states_the_scaling_rule`)

Meine unveränderte Runde-1-Mutation (EINE zusammenhängende Änderung: die Effort-**Regel** verlässt den
Leiter-Absatz), Schiedsrichter `test_no_lead_skill_keeps_its_own_copy_of_the_scaling_rule`:

| Zeile | Datei | Runde 1 | Runde 2 |
|---|---|---|---|
| `w01` | `team-kits/dev-team/constitution/AGENTS.md` | GRÜN, 2.3 s | **RED**, 1.9 s |
| `w01r` | `team-kits/research-team/constitution/AGENTS.md` (gleicher Absatz) | — | **RED**, 2.0 s |

Direkt am Leser sondiert: qualifizierende Statements ORIGINAL = 1, nach `w01` = **0** → `assert len(paragraphs)
== 1` fällt. Der Angriff des Koordinators (ein Effort-Wort in einem **fremden** Lead-in) erzeugt hier keinen
zweiten Qualifizierer, weil dessen Block keine gebacktickte Sprosse trägt — also kein Fehlalarm. Siehe **N2** für
die Richtung, die ich stattdessen gefunden habe.

**Verfassungen unangetastet, Stempel unverändert:** seit 01:00 geändert sind nur `tools/radar_routine.py`,
`tools/test_radar_trigger.py`, `tools/test_review_procedure.py`, `.claude/hooks/test_gates.py`,
`docs/POST_V2_WISHLIST.md` (und drei `document_trays.txt`, deren Inhalt laut `git diff` unverändert ist — nur
mtime aus einem Testlauf). `python tools/bump_kit_version.py` in meiner Kopie: `dev-team: unchanged
(2026.09.06-1)`, `office-team: unchanged (2026.09.10-1)`, `research-team: unchanged (2026.09.06-1)`, rc 0, keine
`VERSION` angefasst.

---

## P1–P6 — alle nachgelesen und in Ordnung

* **P1** `.claude/hooks/test_gates.py:4708-4718`: der Satz sagt jetzt ausdrücklich „the same question the kernel's
  index renderer asks … **asked here of the path directly, not through that function**, which answers with a table
  cell". Der Docstring behauptet nicht mehr, das Kernel-Prädikat zu benutzen. ✔
* **P2** `BUG-0272` `observed`: „Three neighbours **PASS THE GATE** (the hook let them run; what grep then returned
  is grep's own exit code — `grep -c` exits 1 when the count is 0 …)" mit `rc 0 / rc 1 / rc 1`. Deckt sich Byte für
  Byte mit meiner Messung. ✔
* **P3** „Vorgefunden" trägt jetzt den Absatz „Was NICHT mehr auf der Platte liegt": die Versuch-2-Zahlen stehen
  „aus der Lesung dieses Umsetzers … nicht aus einer erhaltenen Datei". Die Herkunft ist damit benannt statt
  behauptet. ✔
* **P4** §16 nennt **90 / 17** mit dem Befehl, mit dem ich gezählt habe, und erklärt den alten Filterfehler (`grep -v
  project_memory/` traf `team-kits/*/templates/project_memory/` in der Mitte). ✔
* **P5** Naht 2: „**Pins zweimal neu geschrieben**", 20:56:05 und 2026-09-10 23:05:54, Verfassungen ab 20:31
  unverändert. ✔
* **P6** `H189` = `BUG-0273` `OPEN`. Selbst nachgezählt: Index **179** Zeilen ↔ **179** Items mit `hole_number` im
  ganzen Store, **0** einseitig, **0** Zeile mit abweichender Id oder Status. ✔

**Rig und Nachläufe:** `redfirst.log.json` 28 Zeilen, `every_row_as_expected: true`, `m25`/`m26`/`m27`
vorhanden. `reading-suites-round1.log` 68 passed, rc 0, 01:23:32 → 01:24:26; `run-gates-suite-round1.log` **548
passed**, rc 0, 01:25 → 01:35:38. Ich selbst voll nachgefahren: `test_review_procedure` 27, `test_role_contracts`
30, `test_model_ladder` 12, `test_migrate_holes` 14, `test_radar_trigger` 9, `test_repo_hygiene` 32 — alle rc 0.

---

## NEU (nicht aus Runde 1; Zuschnitt-Frage an den Lead, keine Runde 3)

**N1 — `cloud_option.named_as` ist eine Namensliste, und die verworfene Option hat im eigenen Text zwei Namen, die
nicht darin stehen.**
`tools/radar_routine.py:338` · `tools/test_radar_trigger.py:193-199`
Gemessen, je ein Satz in `radar/README.md`, Schiedsrichter die ganze Datei:

| Zeile | Satz | Ergebnis |
|---|---|---|
| `v04` | „The **hosted code routine of the platform** starts the radar-watcher every Friday from the Desktop." | **GRÜN, 9 passed** |
| `v05` | „The platform's **sandbox routine against the remote** starts the radar-watcher every Friday from the Desktop." | **GRÜN, 9 passed** |

„a hosted code routine of the platform, running in a sandbox against the remote" ist die **eigene Formulierung des
ausgelieferten `radar/README.md`** für genau diese Option (Absatz „The rejected alternative", DEC-0085). Keiner
der drei `named_as`-Einträge kommt darin vor. Der Docstring über-behauptet nichts (er sagt „by the names it
publishes"), also keine Regel-3-Verletzung — aber es ist Hausregel 1: eine Aufzählung ohne Stolperdraht an beiden
Enden. Kleinster Zuschnitt: `named_as` um die Wendungen erweitern, die der ausgelieferte Text selbst benutzt,
**und** einen Test, der jede Bezeichnung des Absatzes „The rejected alternative" gegen `named_as` prüft (beide
Enden, wie bei `STALE_LADDER_TEXTS`). Loch-Item wäre die Alternative.

**N2 — Der Lead-in-Zweig der neuen Effort-Regel verlangt die zwei Achsen nicht „in one breath".**
`tools/test_review_procedure.py:1330-1332`
Am Leser sondiert, EINE zusammenhängende Änderung in der dev-Verfassung: die Effort-**Regel** entfernt und das Wort
`effort` in das fette Lead-in desselben Statements verschoben → qualifizierende Statements = **1**, der Test
bliebe grün, obwohl der Absatz keine Effort-Regel mehr aussagt. Grund: Zweig 1 verlangt das Effort-Wort im
Lead-in, die Sprosse aber nur *irgendwo im Block* — die beiden dürfen einen ganzen 1424-Zeichen-Punkt
auseinanderliegen. Der Docstring nennt den Zweig ehrlich („the effort axis in its bold lead-in, or in ONE sentence
together with a rung"), widerspricht damit aber seiner eigenen Begründung zwei Zeilen darunter („A rule states
both axes **in one breath**"). Kleinster Zuschnitt: im Lead-in-Zweig die Sprosse ebenfalls im Lead-in verlangen —
oder den Satz „in one breath" streichen und den Zweig als bewusste Weite benennen. Heute schadet es nichts: der
ausgelieferte Text erfüllt den strengeren Satz-Zweig.

Beides ist **kein Blocker**: N1 braucht eine künftige Textänderung, um zu beißen, N2 eine Umformulierung des
Leiter-Absatzes; beide sind Zuschnitt-Fragen, keine offenen Angriffsketten.

---

## Nicht gemessen (ausdrücklich)

Volle `tools/`-Suite (Gate 5 / DEC-0050) — die Nachlauf-Logs gelesen, nicht wiederholt. Die Token-/Wandzeit-Zeilen
der (g)-Tabelle. Die Zuschnitt-Befunde Z1, Z3, Z4, Z5, Z7, Z8 (fremde Sitzungen). Die Originalzahlen des
Lieferlauf-Versuchs 2 — das Log bleibt überschrieben; das Protokoll sagt das jetzt selbst (P3).

---

## Urteil

**PASS** auf B1, B2, B3, B4.

Jeder der vier Runde-1-Befunde ist mit **meiner unveränderten Mutation** nachgemessen und dreht die Farbe: `m23`
grün → **rot**, `v01` grün → **rot**, `w01` grün → **rot** (in dev *und* research), und der CRLF-Blocker ist mit
allem gestaged **32 passed** statt rot. Die Verfassungen sind unangetastet, die drei Stempel stehen (`unchanged`
×3), Index = Store bei 179 Löchern, und alle sechs Prosa-Befunde P1–P6 sind im Code, im Store und im Protokoll
korrigiert — P4 einschließlich der Zahl, die ich anders gezählt hatte.

Zwei **neue** Fragen (N1, N2) stehen oben mit ihrer gemessenen Zeile. Beide sind nicht blockierend und gehören als
Zuschnitt-Entscheidung bzw. Loch-Item auf den Tisch des Leads — sie rechtfertigen keine dritte Prüfrunde. Aus
meiner Sicht kann der Lead die zwei EVD-Zeilen setzen und committen.
