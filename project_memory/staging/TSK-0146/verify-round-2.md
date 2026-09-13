# Prüfbericht TSK-0146 (PR-0012, Order 4, Strom A Kern) — Runde 2 — **FAIL (knapp: R1 Knoten, R3 Satz; R2 Zeile, R4 Wort)**

Prüfer: `harness-verifier` (Opus, high), 19 min, +66 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-13 02:14, Uhr gelesen). DEC-0096 FAIL 2 = Neuschnitt: R1-R4 gehen als Zeilen in die Zielrunde TSK-0149 (ein Bauer, ganzer Baum), Prüfer M misst sie mit.

## Prüfbericht Runde 2 — Strom A (Kernel), TSK-0146

Neuer Snapshot: `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0146\verify\repo` (robocopy /MIR, ohne `.git`/`__pycache__`/`.pytest_cache`). Gemessen mit `verify\rig.py` (verweigert außerhalb des eigenen Verzeichnisses, binäre I/O, setzt jede berührte Datei byte-genau zurück) und eigenen Sonden. Vom Protokoll habe ich diesmal nur die Rework-Abschnitte (Zeilen 468–647) gelesen.

---

### Die drei blockierenden Befunde aus Runde 1: geschlossen und nachgemessen

**F1 — Vokabel-Umgehung.** Gegen die ausgelieferte CLI, meine eigene Zeile aus Runde 1:
```
capture PR {... class:"feature", legacy_fields:{legacy_id:V1-1}} -> rc 1 (Vokabel-Verweigerung)
capture PR {... class:"normal",  legacy_fields:{...}}            -> rc 1 ("capture PR carries `legacy_fields` ... written by the import path alone")
capture PR {... class:"normal"}                                  -> rc 0
update PR-0001 {class:"feature"}                                 -> rc 1
update PR-0001 {class:"feature", legacy_fields:{...}}            -> rc 1 (Provenienz zuerst); gespeichert bleibt class: normal
```
Der Importpfad schreibt weiter seinen Fundwert: `capture("PR", …, imported=True)` → `class='feature'` angenommen; `imported=True` setzen ausschließlich `kernel/migrate.py:2163/:2961` und die zwei Migrations-Preflights (grep über `team-kits`, `tools`, `.claude`: kein weiterer Setzer, die CLI hat kein Flag). Migrationstür über einen ECHT importierten Streuwert: Plan rc 1 mit `UNDECIDED: PR-0001 ('feature')`, `--map feature=normal --apply` rc 0 mit `written:`.
Eigenes Red-first (`rig.py exemption_reads_the_body_again`, Rumpf-Ausnahme + Provenienzfeld wieder frei) → `tools/test_state.py::test_a_legacy_key_in_a_typed_body_opens_no_door` rc 1.
`team-kits/kernel/dispatch.py:2370-2371` nennt jetzt die zwei Fälle, die es wirklich gibt. EVD-0440 nennt BUG-0237, sagt ausdrücklich, dass es EVD-0431 ablöst, und welcher Satz zu weit war. **Geschlossen.**

**F5 — Kommandofläche.** `tools/test_hooks.py::test_every_span_that_presents_the_command_surface_names_all_of_it` → 1 failed, und zwar **nur** noch:
```
team-kits/{dev,office,research}-team/constitution/AGENTS.md: names 36, misses migrate-goal-classes, withdraw-request
README.md: names 36, misses migrate-goal-classes, withdraw-request
```
Die cli.py-Zeile ist weg. Der übergebene Patch-Text ist exakt: beide Anker (`` `sweep-leases`, `sweep-requests`, `checkpoint` `` und `` `migrate`, `migrate-holes`, `sweep-pointers` ``) kommen in jeder der vier Dateien genau einmal vor, und angewandt (`rig.py apply_the_seam_patch`) wird der Knoten **grün (1 passed)**. **Geschlossen, Naht korrekt übergeben.**

**F7 — die zweite Restklasse.** `project_memory/bugs/active/BUG-0303.yaml` existiert (OPEN, `hole_number: H218`, `related_pr: PR-0012`, drei AC, `limits` mit der gemessenen rc-Kette), steht in `docs/POST_V2_WISHLIST.md:2521`, und die Umzeigung des Docstrings ist als Zielrunden-Zeile gelistet (`project_memory/staging/generation-6-streams.md:122`). `tools/test_approvals_dispatch.py:4847` zeigt heute noch auf H155 — erwartungsgemäß, das ist genau die gelistete Zeile, und AC-3 von BUG-0303 trägt sie zusätzlich. **Geschlossen.**

### Die übrigen Befunde aus Runde 1

- **F2** — meine eigene Zeile, die in Runde 1 grün blieb: `rig.py report_reader_back_to_a_literal` mit der isolierten Knotenreihenfolge (der fragende Test zuerst) → **rc 1, 1 failed, 1 passed** (Runde 1: rc 0, 2 passed). Der Frame-Leser `_remember_who_asked` läuft aus dem Modul heraus statt in fester Tiefe. **Geschlossen.**
- **F3** — `tools/test_kernel.py::test_the_evidence_command_stamps_the_class_with_the_role_the_lease_names` 1 passed; Mutation „die CLI stempelt `project-manager`" → rc 1. Das Kommando läuft jetzt: der frühere Tod (`capture EVD carries fail_class`) ist weg, `_role_judged_offences` verweigert den AUTOR-Stempel auf jedem Typ und die KLASSE nur auf dem Auftragstyp. **Geschlossen.**
  Eigene Korrektur: meine Runde-1-Mutation `cli_role_is_a_constant` (Konstante `quality-engineer`) bleibt **grün**, weil die Fixture-Lease genau diese Rolle trägt — das ist eine Grenze meiner Mutation, nicht des Tests; mit jeder anderen Konstante ist er rot.
- **F4** — `tools/test_ladder.py::test_an_unbound_lease_names_no_writing_role` 1 passed; Mutation `writing_role_ignores_the_binding` → rc 1 (in Runde 1 blieb die ganze Datei mit 57 passed grün). **Geschlossen.**
- **F6** — Row 3 des Protokolls nennt jetzt `_runs_a_program` / H11 statt „heredoc-Rumpf", ohne neuen Löcher-Eintrag. **Korrekt.**
- **F8** — je einzeln gemessen:
  `stamp_without_a_status_recheck` → `::test_a_stamp_lands_only_while_the_run_it_judges_is_still_failed` rc 1 · `stamp_without_a_revision_bump` → `::test_the_stamp_is_a_change_the_revision_counts` rc 1 · `sweep_reports_its_intention` → rc 1 · `sweep_dies_on_one_bad_id` → rc 1 · `withdrawn_is_still_reported_dead` → rc 1.
  Verhalten am echten Store (Kopie, präparierte Id, deren inneres `request_id` nicht mehr zum Dateinamen passt — der deterministische Stellvertreter für „im Fenster beantwortet"):
  ```
  withdrawn        10 Ids (nicht 11 = die Absicht)
  not_withdrawable ['deadbeef… (no pending approval request … already answered, already withdrawn, expired-and-cleaned, or never created)']
  kept             []            <- die schlechte Id steht NICHT mehr unter "still open"
  dead             ['deadbeef…'] <- die zurückgezogenen sind raus
  ```
  Die CLI druckt die Zeile „could not be taken back (answered or gone in the meantime)". **Geschlossen**, mit einem Rest (R4 unten).

### EVDs, Batch, ruff

`coverage_blocker`: EVD-0440→BUG-0237, EVD-0432→BUG-0253, EVD-0441→BUG-0260, EVD-0442→BUG-0302 alle „OK". Die drei neuen `run_command` nachgefahren: **6 / 8 / 6 passed, rc 0**. EVD-0431/0433/0434 sind nicht mehr aktiv (archiviert). `verification_batch` über alle vier Ids: 4 Zeilen, 0 verweigert, jeweils mit dem ABLÖSENDEN Nachweis. `tools/test_state.py tools/test_backlog_types.py` → 124 passed. `ruff check team-kits/kernel/ tools/` → All checks passed.

---

## Neue Befunde dieser Runde

**R1 (blockierend, ein Knoten) — der Selbstbefund „halb angewandtes Urteil" hat keinen Schiedsrichter.**
`team-kits/kernel/dispatch.py` `record_fail_class`: die Zwei-Phasen-Form (erst alle Aufträge unter dem Lock beurteilen, dann schreiben) ist gebaut und im Kommentar begründet — aber kein Test misst sie.
Gemessene Zeile (getreue Mutation: urteilen und schreiben in EINEM Durchlauf, sodass eine Verweigerung am zweiten Auftrag den ersten gestempelt zurücklässt):
```
python -B rig.py stamp_is_half_applied -- tools/test_ladder.py -q                                  -> 60 passed, rc 0
python -B rig.py stamp_is_half_applied -- tools/test_kernel.py tools/test_state.py -k "evidence or fail or class" -> 18 passed, rc 0
```
Der Einzelauftrags-Fall ist gemessen (`test_a_stamp_lands_only_while_the_run_it_judges_is_still_failed`), der Mehrauftrags-Fall nicht. Minimaler Fix: ein Knoten — ein Nachweis nennt zwei Aufträge, der zweite ist nicht FAILED → `DispatchError` und **keiner** der beiden trägt danach `fail_class`. Hausregel „jeder Fix braucht einen Test, der ohne ihn rot wird".

**R2 (mittel, vom Fix neu geöffnet) — ein EVD darf jetzt jedes Wort als Fail-Klasse tragen.**
`team-kits/kernel/state.py:1978` lässt `fail_class` auf allen Typen außer dem Auftragstyp zu; `_CLOSED_VOCABULARY` schließt für EVD `kind`, `result`, `run_scope` — **nicht** `fail_class`.
Gemessene Zeile:
```
capture EVD {... "fail_class":"banana"} -> EVD-0001, rc 0; gespeichert: fail_class: banana
```
Vor der Nacharbeit war das Paar für jeden Typ verweigert, also ist das eine neue Lücke. Kein Kernel-Leser liest die EVD-Kopie (der Zähler liest `dispatch.py:3144` den AUFTRAG), der Schaden ist also ein Nachweis mit einem erfundenen Wort — aber es ist genau die Asymmetrie, die dieses Projekt sonst schließt. Minimaler Fix: eine Zeile `("EVD", FAIL_CLASS_FIELD): (FAIL_CLASSES, "…")` in `_CLOSED_VOCABULARY`, sonst der Satz im Docstring, dass die EVD-Kopie ungeprüfte Beschreibung ist.

**R3 (blockierend, ein Satz) — ein Kommentar behauptet, was der Code seit der Nacharbeit nicht mehr baut.**
`team-kits/kernel/cli.py:1632-1634`: „ASKED BEFORE THE RECORD IS WRITTEN, because a refused classification must not leave an Evidence item behind that claims one: the record is immutable". Seit F8 gibt es ein ZWEITES Urteil — die Statusprüfung unter dem Lock in `record_fail_class` —, und das fällt **nach** `state.capture("EVD", …)`. Im Rennen bleibt genau das zurück, was der Satz ausschließt: ein unveränderlicher Nachweis mit `fail_class` und ein Auftrag ohne Stempel (rc 1 mit Meldung, kein Traceback — `DispatchError` ist ein `StateError`, gefangen bei `cli.py:2254`). Minimaler Fix: den Satz um das zweite, gesperrte Urteil und seine Folge ergänzen (oder die Erfassung hinter den Stempel ziehen — das wäre eine Verhaltensänderung).

**R4 (klein) — der vierte Ausgang fehlt noch an einer der drei Stellen.**
`team-kits/kernel/approvals.py:3123` (`mint`, der Zweig, den ein später Klick auf eine zurückgenommene Frage nimmt) sagt weiter „(consumed, expired-and-cleaned, or never created)". `pending_request:3659` und `withdraw_request:3627` nennen den Rückzug jetzt. Der NUTZER-Satz war schon in Runde 1 richtig. Ein Wort.

---

## Negativbefunde

**Gemessen und in Ordnung:** alle oben genannten Punkte; zusätzlich: kein zweiter Setzer von `imported=True` außerhalb von `migrate.py`; die Sweep-Ausgabe listet zurückgezogene Fragen nicht mehr unter „dead" (`dead: -` nach `--stale 1` auf einer Kopie des echten Stores); `_remember_who_asked` erkennt nur `kernel.*`-Aufrufer; DispatchError endet als rc 1 mit Satz, nicht als Traceback.

**Nicht gemessen:** die volle Suite und A's Laufzeiten; `tools/test_migrate.py` (280 s) — die Migrationstür habe ich stattdessen von Hand gegen einen echt importierten Streuwert gefahren; die Hook-Suiten der Nachbarströme; das echte Rennen hinter R3 (nur aus Code plus dem gemessenen zweiten Urteil abgeleitet); ob der Zwei-Phasen-Schreiber die Eigenschaft wirklich hält (Codelesung, positiver Fall nicht gefahren — deshalb R1).

## Urteil: **FAIL** (knapp)

Die drei blockierenden Befunde aus Runde 1 sind geschlossen und von mir mit eigenen Mutationen nachgemessen; das Paket ist deutlich besser als in Runde 1.

- **Blockiert die Runde:** **R1** (ein fehlender Knoten für einen Fix, der Zustandshalbschreibung verhindert) und **R3** (ein Kommentar, der Schutz behauptet, den der Code seit der Nacharbeit nicht mehr baut). Beide liegen in A's `allowed_scope` und sind zusammen ein Knoten plus ein Satz.
- **Löcherliste / benannte Reste:** **R2** (EVD-Kopie der Fail-Klasse ohne Vokabel — schließen oder benennen), **R4** (ein Wort in `mint`), sowie unverändert aus Runde 1: die Batch-Zeilen für BUG-0260 und BUG-0253 bleiben zu Recht zurückgestellt (B's Hook-Hälfte bzw. die Nutzer-Aktion), und die vier Dokumente warten auf den Nahtpatch, dessen Wirksamkeit ich verifiziert habe.