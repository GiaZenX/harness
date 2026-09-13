# Prüfbericht TSK-0148 (PR-0012, Order 4, Strom C) — Runde 1 — **FAIL (Text: B1 B2; Reste B3 B4)**

Prüfer: `harness-verifier` (Opus, high), 22 min, 163 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-13 00:13, Uhr gelesen).

## Prüfbericht TSK-0148 / Strom C — **FAIL** (drei Textbefunde, Code-Mechanik sauber)

Gearbeitet read-only gegen einen einmaligen Snapshot in `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0148\verify\tree` (eigenes Rig `…\verify\snapshot.py`: verweigert außerhalb des eigenen Verzeichnisses — gemessen `REFUSED: run this rig from its own directory` —, schreibt binär). Zusätzlich `…\verify\base` (Basis-Commit 5ecf62a via `git show`) und `…\verify\mixed` (aktueller Leser + Kits von 5ecf62a).

### Befunde

**B1 — `tools/test_repo_hygiene.py:2813-2831` (`_binds_a_name`) behauptet Vollständigkeit, die es nicht hat. Blockierend (Textfix).**
Docstring: *„die drei Schreibweisen, die Python dafür hat"* (ein Name an einen Ausdruck gebunden). Python hat mehr, und zwei davon sind genau die BUG-0299-Form. Gemessene Zeile (Sonde gegen `_hook_starts_that_name_no_project`):

```
reported: ['bound_by_an_augmented_assign', 'bound_twice_last_one_is_the_hook']
```

Nicht gemeldet: `with helper(os.path.join(tmp,"gate_write_scope.py")) as program:` und `for program in [os.path.join(tmp,"hooks","gate_git.py")]:` — beide starten einen Haken ohne Projekt und bleiben stumm (die gefährliche Richtung von BUG-0280). `docs/holes/H215.md` verschärft das: *„Damit ist jede Zusammensetzung abgedeckt"* und nennt als Rest nur Name-aus-Name und Parameter. Zusätzlich gemessen: bei Doppelbindung gewinnt die letzte — `bound_twice_last_one_is_harmless` (echter Haken-Start) bleibt stumm, `bound_twice_last_one_is_the_hook` meldet falsch; H215 behauptet *„Beide melden nichts statt falsch zu melden"*.
Reichweite heute: **0 Opfer** (Korpusmessung: mit weiterem Binder entsteht genau ein neuer Treffer, `tools/test_hooks_v2.py:13964`, und der ist ein **Fehlalarm** — der `for`-gebundene `extra` trägt `["--kit","hooks/.."]` in den argv-Zweig; 0 echte übersehene Starts, 0 Doppelbindungen).
Minimalfix: Satz auf *„die drei **Zuweisungs**-Schreibweisen"* ändern **und** `with … as` / `for` sowie die Letzt-Bindung als Rest in H215 aufnehmen. Wer stattdessen erweitert: nur den Programmwort-Zweig, nicht den argv-Zweig — der Fehlalarm oben ist gemessen.

**B2 — `project_memory/staging/TSK-0148/dec-question-BUG-0296.md`, Empfehlung C ist gemessen falsch. Blockierend (geht an den Nutzer).**
Tragender Satz: *„C … ist der einzige der drei, der die bisherigen vier Fälle **rückwirkend** entschärft hätte"*. C feuert nur dort, wo der Leser *weiß*, dass er nicht entscheiden kann — das ist `_complement_of`, erreichbar nur über eine Präpositions-Verneinung. Gemessen gegen `kernel/dispatch.py`:

```
R1 (BUG-0278)      names_a_test=False denies=True  preposition-denier hits=[]
R2 (weder/noch)    names_a_test=False denies=True  preposition-denier hits=[]
R3 (Genitiv)       names_a_test=False denies=True  preposition-denier hits=['ohne']
R4 (BUG-0296)      names_a_test=True  denies=False preposition-denier hits=['ohne']
```

und mit nachgebautem C plus wiederhergestelltem Runde-1-Wortstand:

```
R1 sentence, round-1 word list, answer C applied -> cheap rung granted: True
R4 sentence, answer C applied                    -> cheap rung granted: False
```

C entschärft die Runden 3 und 4, **nicht** 1 und 2: ein fehlendes Wort in `_DENIES_RX`/`_CORRELATIVE_DENIERS` erzeugt kein „unentscheidbar", sondern ein selbstsicheres „keine Verneinung". Der Nutzer entscheidet sonst auf falscher Prämisse. Minimalfix: den Satz durch die gemessene Aussage ersetzen und dazuschreiben, dass die Fehlalarm-Kosten von C (Gegenrichtung „Ohne den Fix wird ein Test rot") ungemessen sind. H212.md trägt die Behauptung **nicht** — nur diese Datei.

**B3 — `tools/test_repo_hygiene.py:1312`: eine wachsende Zahl im Code. Nachgelassener Rest (SR-0008, Hausregel 4).**
`"184 sites the defect did NOT touch"`. 184 gilt nur für 5ecf62a; über den laufenden Baum sind es **216** (gemessen mit der Defekt-Mutation). Die Zahl hat ihren Ort in EVD-0417 und im Protokoll, beide mit Uhrzeit. Fix: Zahl aus der Assert-Meldung streichen.

**B4 — `project_memory/staging/TSK-0148/protocol.md:134-140`: Abweichung von `expected_outputs`. Nachgelassener Rest.**
Verlangt ist „Per row ONE line: id | change | red-first | naming node | suites | EVD"; die Tabelle trägt nur `| (filled in below, one section per row) |`. Inhaltlich vollständig in Prosa, formal nicht geliefert. (Ebenso: COUNTS sagt „seams handed over: 3", die Naht-Überschrift „TWO ROWS FOR B", SEAM 3 steht unter „## Rows".)

### Negativbefunde — **gemessen**

- **BUG-0295**: Mutation (`readable = text`) → `1 failed`, `assert [] == ['DEC-0034']`. Toter Verweis an `team-kits/kernel/dispatch.py:224` gepflanzt → `team-kits/kernel/dispatch.py:224 DEC-0999` gemeldet, mit Defekt stumm. Vier Exponate stumm (3×DEC-2100, 1×DEC-0000). **Nachgezählt gegen 5ecf62a: 190 / 186 / 4, mit Defekt 190 / 184 / 6** mit genau `dispatch.py:204` und `invoice_intake.py:370` — die Zahlen des Umsetzers reproduzieren exakt. Reichweite **700 → 702**, und nur in diesen zwei Dateien. (Ich hatte die Zahl zunächst gegen den laufenden Baum geprüft und für falsch gehalten — das war mein Fehler; A und B haben den Baum seit 23:12 auf 223/219/4 wachsen lassen.)
- **BUG-0299**: Hop entfernt → `1 failed`, 2 von 5 genannt; `_binds_a_name` auf reine Zuweisung verengt → `1 failed`, 3 von 5. Lebende Pflanzung in `tools/test_migrate_holes.py` → `1 hook start(s) … tools/test_migrate_holes.py:582`. Vier Hop-only-Stellen bestätigt (`tools/test_hooks_v2.py:13626`, `:14689`, `tools/test_repo_hygiene.py:2682`, `.claude/hooks/test_gates.py:344`), **0 vergesslich**.
- **BUG-0297**, drei Richtungen mit echter Git-Bash als Schiedsrichter: heute `1 failed` (26,1 s) mit `error: the following arguments are required: --run-command, --run-scope`; mit dem S4-Patch in meiner Kopie `2 passed` (36,6 s); Patch minus `--run-scope` wieder `1 failed` mit `required: --run-scope`. Der Docstring sagt alle drei. **Kein EVD nennt BUG-0297** (grep 0). `_remedy_with_values` stoppt in der verneinten Richtung wie dokumentiert (`the remedy asks for a value this test cannot invent ('mechanical/reasoning')`).
- **Namensknoten**: `kernel.naming_tests.coverage_blocker` → kein Blocker für BUG-0295, BUG-0299 (und BUG-0297).
- **Batch-Zeile**: `approvals.batch_walk_blockers(state,"verification",["BUG-0295","BUG-0299"])` gegen die Store-Kopie im Checkout → `ids: 2   refused: 0`.
- **Indexzeilen**: alle sechs verlinken bereits (`docs/POST_V2_WISHLIST.md:2514-2520`), `test_every_hole_is_one_index_row_one_prose_file_and_one_item` ist in meiner Kopie **grün** — Naht 3 ist erledigt. H211/H213/H215/H216/H217 sagen sauber, was geschlossen und was begrenzt ist; die OPEN-Status im Index decken sich mit den Items (keine BUG-Transition, korrekt).
- **ruff**: `All checks passed!` über beide Dateien. Selbstleser von `test_gates.py`: `3 passed`.
- **Fremdrot**: `test_every_test_pointer_this_repo_writes_resolves` → `1 failed`, drei Stellen, alle `team-kits/{dev,office,research}-team/hooks/gate_test_scope.py:59` mit einem `tools/test_hooks.py`-Knoten, den es nicht gibt → Strom B, nicht C.

### **Nicht** gemessen

- Die Nähte an B selbst (BUG-0300/0301) — ich habe nur geprüft, dass die Zeilen Mechanismus, Mutation und vier Messungen tragen; B's Patch habe ich nicht gefahren.
- Volle Suiten (verboten), `tools/gate_suite_margins.py`/`gate_suite_rates.py` gegen den neuen 26-s-Test.
- H214/BUG-0298 (nicht Strom C).
- Die Fehlalarm-Kosten von Antwort C („Ohne den Fix wird ein Test rot" darf keine Verweigerung werden) — gehört zum Fix von B2.
- Ganz gelesen habe ich: `docs/holes/H212.md`, `docs/holes/H215.md`, `dec-question-BUG-0296.md` und `protocol.md` ab Zeile 230; der Rest nur an den Stellen, die eine Frage beantworten.

### Urteil

**FAIL.** Die drei Mechanismen selbst sind korrekt und reproduzieren exakt — kein Code muss angefasst werden. Blockierend sind **B2** (der Nutzer bekäme eine Empfehlung, deren tragende Behauptung gemessen falsch ist) und **B1** (Docstring und Lochakte behaupten eine Vollständigkeit, die zwei stumme Bindungsformen widerlegen). **B3** und **B4** gehören als benannte Reste in die Löcherliste bzw. ins Protokoll, wenn der Lead sie nicht sofort mitnimmt.