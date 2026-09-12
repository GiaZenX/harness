# Prüfbericht TSK-0141 (PR-0012, Order 3b, Strom A Kernel) — Runde 2 — **FAIL (eng)**

Prüfer: `harness-verifier` (Opus, high), 20 min, +99 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 13:07, Uhr gelesen). Nacharbeit 2 an A als enge Liste (DEC-0096: FAIL 2 = Neuschnitt — hier als präzise Zeilenliste); R3 → Nutzer-Patch (Stelle 8); H155/H170/H171 → DEC-Fragen an den Nutzer.

## Prüfbericht Runde 2 — TSK-0141 (Strom A, Kernel), Nacharbeit 1

Baum neu gespiegelt (2913 Dateien, binär, `…\verify\mirror.py`). Am Repo nur gelesen. Protokoll: gelesen wurden die Abschnitte 824–1104 (die Nacharbeit) — der Rest nicht erneut.

---

## BEFUNDE

### R1 — `_CLAUSAL_DENIERS` ist weiter zu kurz, und zwar in der gefährlichen Richtung

`team-kits/kernel/dispatch.py:2904-2905`. B1 ist für meine zwei Sätze erledigt; die Klasse ist es nicht. Gemessen gegen den laufenden Leser (`probe_dispatch3.py`, 27 Zeilen):

```
XX got=True  want=False | Nothing makes a test go red
XX got=True  want=False | Neither the test nor the probe goes red
XX got=True  want=False | Weder ein Test noch ein Nachweis wird rot
```

`none` steht in der Liste, sein unmittelbarer Zwilling `nothing` nicht — dieselbe Asymmetrie, aus der BUG-0278 bestand, nur innerhalb des Englischen. `neither…nor` / `weder…noch` ist die korrelative Verneinung, die beide Sprachen haben. Jeder dieser Sätze **gewährt die billige Sprosse**.

Richtig gebaut ist: `niemals`, `nirgends`, `nirgendwo`, `keinesfalls`, `auf keinen Fall`, `zu keiner Zeit`, `never once` werden alle korrekt verweigert (gemessen, dieselbe Tabelle).

### R2 — `_COMPLEMENT_WORDS = 3` schlägt ab dem vierten Wort in die gefährliche Richtung um, und der Kommentar nennt nur die andere Richtung

`team-kits/kernel/dispatch.py:2920-2930` (Konstante :2930, Leser :2984). Gemessen (`probe_dispatch4.py`):

```
XX got=True  want=False | Das Ergebnis wird ohne einen einzigen neuen Test rot
XX got=True  want=False | Das Ergebnis wird ohne jeden weiteren neuen Regressionstest rot
XX got=True  want=False | The result goes red without any new regression test
XX got=True  want=False | The rename passes without a single new unit test
ok got=False            | Das Ergebnis wird ohne einen neuen Test rot     (3 Wörter -> greift)
```

Rot gezeigt, indem die vier Zeilen in den benennenden Test aufgenommen wurden:

```
FAILED tools/test_ladder.py::test_a_german_acceptance_line_is_read_like_its_english_twin
tools\test_ladder.py:529: AssertionError        1 failed in 2.12s
```

Der Kommentar sagt: „widening it re-opens the fronted row, and both rows stand in the naming test". Er sagt **nicht**, was der gewählte Wert kostet: ein Komplement von vier oder mehr Wörtern entkommt der Verneinung und kauft die billige Sprosse. Das ist Hausregel 3 in der beruhigenden Richtung — die Kalibrierung wird mit ihrem Nutzen, aber ohne ihren Preis hingeschrieben. (Bei `_CLAUSAL_DENIERS` ist es vorbildlich gelöst: dort steht die gefährliche Richtung ausdrücklich im Kommentar.)

Beide, R1 und R2, sind derselbe Mechanismus: **ein Wort-Inventar bzw. eine Fensterbreite entscheidet über eine Verneinung, und jede Lücke darin ist eine Zusage.** Nicht die zwei Schreibweisen, die ich zufällig probiert habe.

### R3 — S2 hat die Abhilfe zerbrochen, die das Commit-Gate dieses Repos bei JEDER blockierten Übergabe druckt (blockiert)

`.claude/hooks/gate_commit_evidence.py:418-423` druckt als Remedy:

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory evidence \
    --kind review --result pass --related <ITEM-ID> \
    --summary "verifier PASS for <digest>" \
    --artifact-ref <path/relative/to/project_memory>
```

Diese Zeile, so gefahren, ist seit der Nacharbeit tot — gemessen auf der echten Kommandofläche:

```
python scripts/harness.py evidence: error: the following arguments are required: --run-command, --run-scope
rc=2
```

`gate_test_scope.py:709-712` trägt das Paar bereits (geprüft, korrekt). `gate_commit_evidence.py` nicht. Der Test, der diese Klasse hält, sieht die Stelle nicht: `tools/test_hooks.py::_texts_that_name_the_evidence_vocabulary` (:6883-6889) liest die Instruktionsdateien der drei Kits, die ausgelieferten Kit-Module und die README — `.claude/hooks/` dieses Repos ist außerhalb seines Korpus. Und die Datei ist jeder Rolle verschlossen, also ist das eine **vierte Naht für die Shell des Nutzers**, die die Nacharbeit nicht benannt hat.

### R4 — kleiner Rest aus B5: die Karte der Lücken-Ausnahme setzt einen Hauptsatz in eine Präpositionalphrase

`team-kits/kernel/approvals.py:1568`. Gemessen auf der echten Kommandofläche, 1 und 2 Einträge:

```
"Erteilt die Freigabe „Ausnahme für eine bekannte Lücke“ für eine Lücke bleibt offen: BUG-0136 (…)"
"Erteilt die Freigabe „Ausnahme für eine bekannte Lücke“ für 2 Lücken bleiben offen: BUG-0136 (…); BUG-0148 (…)"
```

Der Numerus stimmt jetzt; der Satz bleibt ungrammatisch. Der Zwilling bei `:1403` macht es richtig, weil er eine Nominalphrase liefert („für einen gemessen behobenen Fehler: BUG-0032 (EVD-0369)"). Eigene Korrektur: mein Runde-1-Befund zielte auf die Ziffer, und die ist erledigt — dieser Teil war in meinem Satz nicht sauber getrennt.

---

## NEGATIVE BEFUNDE — GEMESSEN

* **B1/B2 im Kern erledigt**: „Ein Test wird niemals rot" / „nirgends" → verweigert; „Without the fix a test goes red." und „Ohne den Fix wird ein Test rot." → beide wieder Zusage; die vier Gegengewichte (`ohne Test`, `ohne Regressionstest`, `latest`, `protest`) halten. 23 von 27 meiner Zeilen richtig; die 4 falschen sind R1/R2.
* **Der Stolperdraht `test_every_listed_denial_word_is_the_reason_its_sentence_is_refused`** ist echt zweiendig und mechanisch (Satz je Eintrag, Eintrag herausgenommen → Zusage), und sein Docstring sagt selbst, dass er ein FEHLENDES Wort nicht sehen kann. Ehrlich.
* **B3 geschlossen**: Brute Force über das ausgelieferte Prädikat, 24 Muster, alle Pfade bis Länge 6 → **95 Paare mit echtem gemeinsamem Pfad, 0 ohne Zeugen** (Runde 1: 6 blind). Rot-zuerst selbst nachgefahren: `_readings` aus `pair_witnesses` entfernt → `FAILED …::test_a_wildcard_free_entry_is_offered_as_the_directory_prefix_the_gate_reads`, 1 failed in 2.42s. Kopfabsatz `scopes.py:31-40` beschreibt jetzt die Klasse, die ich gemessen habe, nicht mehr die geschlossene. **Live-Schnitt**: `check-scopes --only TSK-0141 TSK-0142 TSK-0143` → `disjoint`, rc 0.
* **B4 erledigt**: `approvals.py:2124-2129` sagt jetzt, was der Code tut; die falsche Behauptung ist weg.
* **B5 Numerus**: `verification` mit 1 → „für diesen einen Fehler …" / Karte „für einen gemessen behobenen Fehler: BUG-0032 (EVD-0369)"; mit 2 → „diese 2 Fehler". `hole_exception` mit 1 → „diese eine gemessene Lücke"; mit 2 → „diese 2 gemessenen Lücken". Frage und Karte benennen bei beiden listengebundenen Arten denselben Gegenstand (die Liste), nicht mehr das Item.
* **B6 zählt, was es sagt**: Brief `budget_status.qa_runs = {'full': 10, 'selection': 294, 'undeclared': 87}`, meine eigene Zählung über die aktiven EVD der QA-Arten: **identisch**. `undeclared` ist ein eigener Eimer. Der KeyError-Pfad (ein fremder `run_scope`) ist unerreichbar: `state.py:1844` führt `("EVD","run_scope")` als geschlossenes Vokabular.
* **B7a gebunden wie beschrieben**: frisches Büro-Projekt (Plan und Profil leer) → `None`; Regeln ohne Interview → die Meldung; gar kein Profil (dev/research) → `None`; Regeln + Interview → `None`.
* **H58 gebaut und konsistent**: `CONFIRMING_EVIDENCE = {BUG, TSK}`; `migration_writable_statuses("TSK")` enthält `DONE`, nicht `VALIDATED`. Da `tools/test_migrate.py` in einer Kopie ohne `.git` nicht laufen kann (die Fixture stellt den V1-Stand aus der Historie her), habe ich **ein eigenes V1-Fixture** gebaut und `migrate.build_plan` darüber gefahren: `{'legacy_id': 'TSK-0001', 'legacy_status': 'VALIDATED', 'mapped_status': 'DONE', 'archive_candidate': True, 'target': 'archive', 'verdict': 'translatable'}` — das V1-Wort reitet im Legacy-Feld mit.
* **S2 grün**: `tools/test_hooks.py -k evidence_command` → 1 passed, 1064 deselected in 9.10s. Der Parser verlangt beide Flags wirklich (rc 2 gemessen, siehe R3).
* **BUG-0055**: Rot-zuerst nachgefahren — der `design_refs`-Append entfernt → `FAILED tools/test_staging_cli.py::test_a_frozen_wireframe_is_a_design_reference_the_scope_hash_moves_on` (`KeyError: 'design_refs'`), 1 failed in 3.21s. Der Test verengt E17 ehrlich im eigenen Docstring (die zweite Einfrierung hebt die Revision nicht erneut, weil die erste das Item schon aus dem Status geholt hat).
* **H155/H170 Tatsachen bestätigt**: `ROOT_TYPE_BY_KIT = {'dev-team': 'PR', 'research-team': 'RQ'}` (kein Büro-Wurzeltyp); `SR_EXEMPT_CLASSES = ['small', 'technical_enabler']`; gespeicherte Ziel-Klassen über den ganzen Store: `technical_enabler 3, normal 4, large 5` = 12 Ziele, drei Schreibweisen — genau die Zahl des Protokolls. **Urteil:** beide sind *keine* Welt-Limits; das Fehlende ist in beiden Fällen eine **Entscheidung des Nutzers** (welche Wörter erlaubt sind / ob das Büro-Kit einen Wurzel-Item-Typ bekommt), und die Mechanik danach liegt im Repo. Sie gehören damit in dieselbe Schublade wie H171: eine DEC-Frage an den Nutzer, nicht eine Ausnahme, die er nur abnickt. So formuliert sind die beiden deutschen Sätze korrekt und für einen Nicht-Entwickler lesbar.
* **Batchzeilen**: alle drei gegen die Store-Kopie neben `tools/` gefahren, **rc 0 / rc 0 / rc 0**, 27 Ids, alle eindeutig.
* **Neue EVDs von Strom A** (0381–0386, 0388, 0389): alle acht kommen durch `naming_tests.coverage_blocker`. EVD-0361 bleibt der einzige ohne Knoten und ist `result: blocked` — korrekt.
* **Zählung B8 stimmt jetzt**: 46 = 28 + 1 + 17, und H197 wird einmal gezählt (nachgerechnet: geschlossen 23 + H106 + H60 + H58 + H108 + BUG-0055 = 28; offen H183 + H155 + H170 + H171 + 6 aus C + 7 aus D = 17).
* **Reverts sauber**: `tools/test_ladder.py tools/test_parallel_scopes.py` → 69 passed in 91,04 s.

## NEGATIVE BEFUNDE — NICHT GEMESSEN

* `tools/test_migrate.py` lief in meiner Kopie nicht (die Fixture braucht die Git-Historie) — ersetzt durch mein eigenes V1-Fixture; die 143 Knoten des Protokolls habe ich nicht nachgefahren.
* Die Ungültigkeit einer LEBENDEN Scope-Freigabe nach einer Einfrierung habe ich nicht Ende-zu-Ende gegen ein echtes APR gemessen — nur den Revisionssprung, aus dem sie folgt.
* Die sieben verbliebenen Reihen der Gruppe D (H44, H56, H132, H86, H84, H79, H76) und die sechs der Gruppe C habe ich in dieser Runde nicht erneut gemessen; die sechs neuen Ein-Satz-Begründungen (Protokoll 1035–1051) habe ich gelesen und halte sie für tragfähige Welt-/Plattform-Grenzen.
* Dateien von Strom B und C: nicht geprüft.
* **Fremd, gemessen, gehört dem Lead**: drei EVDs von TSK-0142 tragen `result: pass` ohne benennenden Knoten — EVD-0370/BUG-0186 (Knoten existiert im Checkout nicht), EVD-0387/BUG-0196 und EVD-0390/BUG-0208 (Lauf ohne Knoten-Id). EVD-0367 aus meiner Runde-1-Meldung ist repariert.

---

## URTEIL: **FAIL** (eng)

**Blockierend:**

* **R3** — die Abhilfe, die das Commit-Gate dieses Repos bei jeder blockierten Übergabe druckt, wird vom Kernel seit dieser Runde mit rc 2 abgewiesen. Das ist ein Bruch, den diese Runde eingebaut hat, auf dem Weg, den jede Lieferung geht. Die Datei ist jeder Rolle verschlossen → vierte Naht für die Shell des Nutzers, zusammen mit S1. Zwei Zeilen (`--run-scope <full|selection>`, `--run-command "<Zeile>"`) im Remedy-Text.
* **R2, Kommentarhälfte** — `dispatch.py:2920-2930` nennt den Preis der Kalibrierung nicht, und der Preis ist die gefährliche Richtung. Ein Satz.

**Benannte Reste (Löcherliste, mit Mechanismus):**

* **R1 + R2, Codehälfte** — „ein Wortinventar bzw. eine Fensterbreite entscheidet über eine Verneinung; jede Lücke darin ist eine Zusage der billigen Sprosse". Gemessen: `nothing`, `neither…nor`, `weder…noch`, und jedes Präpositionalkomplement ab vier Wörtern. Fix ist je eine Zeile plus die Reihen im benennenden Test — wird das nicht in dieser Runde gemacht, muss es mit dieser Messung in die Löcherliste, sonst ist es der Zustand, den die Hausregel verbietet.
* **R4** — die Karte der Lücken-Ausnahme (`approvals.py:1568`) in eine Nominalphrase bringen, wie ihr Zwilling bei `:1403`.
* **H155, H170, H171** — drei DEC-Fragen an den Nutzer, nicht drei Ausnahmen. Sie sind in-repo-Arbeit hinter einer Entscheidung, und so sollten sie ihm auch vorgelegt werden.

Was die Nacharbeit sonst angeht: B3, B4, B5, B6, B7a, B8, H58, S2 und BUG-0055 sind gemessen erledigt, jeweils mit einem Rot, das ich selbst gesehen habe, wo eines behauptet war.