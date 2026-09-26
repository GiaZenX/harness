# TSK-0152 -- Prüfbericht Runde 2 (Prüfer), 2026-09-26, eng: F1/F2/F3 und was ihre Fixes berühren

Kopie: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0152/verify2/` (`repo` = Byte-Kopie ohne
.git/Caches über eigenes `mkcopy.py`; `kits2` = zweite Kernel-Kopie für die Angriffe; Rigs
`rig.py`/`muts.py`/`attack.py`/`fixrun.py` verweigern fremdes cwd, schreiben binär; Logs
`mut.log`, `mut2.log`). Gelesen: verify-round-1.md bis Zeile 62, protocol.md nur "Rework 1"
(Z. 352-421), `archive_door.py` ganz, die berührten Stellen in state.py/report.py/holes.py/Tests.

## Urteil: FAIL

## Befunde

### F4 (blockierend, billig) -- die Checkout-Regel ist lexikalisch; ein Link führt aus dem Checkout und in den Zustandsordner
- `team-kits/kernel/archive_door.py:57-63` `_lies_under` vergleicht `os.path.abspath`, nicht den
  Ort, auf den das Dateisystem zeigt; `team-kits/kernel/holes.py:199` (`os.walk`, unverändert)
  steigt auf Python 3.13/Windows in eine Junction ein, also listet `test_modules_under` das Modul
  hinter dem Link. Damit ist die Docstring-Aussage `archive_door.py:72-73` ("a spelling that ...
  takes a detour is not in that list, so no spelling needs a rule of its own") und die Meldung
  "its module lies outside this checkout" für die Dateisystem-Umleitung falsch.
- Gemessen (`attack.py`, echter `kernel.cli` in eigenem Checkout, Junction per `mklink /J`, ohne Admin):
  - `junction_out  rc=0 written=True new='tools/lnk/test_elsewhere.py::test_far_away'` (Ziel
    außerhalb des Checkouts);
  - `junction_to_staging  rc=0 written=True new='tools/lnk2/test_throwaway.py::test_far_away'`
    (Ziel = `project_memory/staging/X` -- die neue Zustandsordner-Regel umgangen);
  - `symlink_file_out  rc=0 written=True new='tools/test_linked.py::test_far_away'`.
- Warum blockierend: dieselbe Eigenschaft wie F2 der Runde 1 (neuer Knoten außerhalb des
  Checkouts), die Kette läuft in einer Sitzung (ein Link ist ein Befehl mehr als `../`; per
  selbst geschriebenem Skript sieht ihn kein Gate, H11), und der Fix schließt sie nicht.
- Minimaler Fix, gemessen in der Kopie (`fixrun.py`, danach zurückgesetzt): in `_lies_under`
  `os.path.abspath` -> `os.path.realpath`. Ergebnis: alle drei Link-Proben rc=1 ("outside this
  checkout" / "state directory"), `tools/test_archive_door.py` 21 passed, beide Module der
  Lead-Zeilen H138/H155 -> `_why_not_a_test_module` = None. Dazu eine Zeile `junction` (und
  `junction_to_state`) im parametrisierten
  `test_a_new_node_outside_the_checkouts_test_modules_is_refused` -- eine Junction braucht keine
  Admin-Rechte, der Test ist auf Windows also fahrbar; rot gegen den heutigen Stand (oben gemessen).

### F5 (niedrig, Löcherliste) -- "Wegwerfdatei" ist für genau EINEN Ort ausgeschlossen
- `archive_door.py:74-76,84-86`: begründet den Ausschluss des Zustandsordners mit "a throwaway file
  is no regression test even where a bare pytest would collect it" -- gebaut ist das nur für
  `state.root`. Gemessen rc=0 written=True für `.venv/test_throw.py`, `.e2e-sandbox/test_throw.py`
  (in diesem Repo gitignored), `_scratch/test_throw.py` (ungetrackt), `build/test_throw.py`,
  `.claude/worktrees/x/test_throw.py`.
- Mechanismus: das Modul wird nach Name und Lage beurteilt, nicht danach, ob es getrackt ist oder
  ein Lieferlauf es sammelt. DEC-0117 sagt "collectable" -- ein ausdrücklich genannter Pfad ist
  sammelbar, darum kein Verstoß gegen die Entscheidung, aber ein benannter Rest (Löcherliste,
  Mechanismus wie hier), keine Rundenblockade.

## Negative Befunde -- gemessen
- Lead-Zeilen H138/H155 (protocol.md Z. 51-52) wörtlich in der Kopie gefahren: `BUG-0221 rc=0`,
  `BUG-0237 rc=0`; danach `.claude/hooks/test_gates.py -k names_is_one_that_exists` in der Kopie:
  `1 passed` (vorher laut Protokoll rot).
- F2-Schreibweisen: `../`, absolut, absolut mit Leerzeichen (Tests der Runde) und neu:
  UNC `//?/C:/...` und `//localhost/C$/...` -> rc=1 "outside"; `TOOLS/...` rc=1 (Über-Verweigerung,
  harmlos); `PROJECT_MEMORY/staging/...` rc=1 "state directory"; `./tools/...`, `tools//...` rc=1
  mit Umschreib-Hinweis; `tools\test_renamed.py::...` rc=0, gespeichert mit `/`; nicht-Testmodul
  `tools/helper.py::test_far_away` rc=1; nachgestelltes `::` rc=1; Klassenknoten rc=1; `[param]` rc=1.
- Mutationen (je eine pro Lauf, Kopie danach byte-gleich zurück):
  F1 update `audited = []` -> rc=1 `test_the_audit_record_has_one_writer`; F1 capture
  `audited = []` -> rc=1 dieselbe; F2 Zustandsordner-Zweig `if False` -> rc=1 nur
  `[state_directory-...]`; F2 ganze Regel `why = None` -> rc=1, alle sechs Formen;
  F3 nur Stufen -> rc=1 `..._bug_0308`; F3 Aufwand aus der Referenz-Antwort statt der eigenen des
  Anbieters -> rc=1 `..._bug_0308` (der Test unterscheidet also auch WESSEN Aufwand).
- Stempel: `bump_kit_version.py --check` alle drei Kits "unchanged (2026.09.26-4)" rc=0;
  `validate.py: all structural checks passed.`; ruff auf den berührten Dateien "All checks passed!".
- Lesende Suiten: Leser von `archive_door`/`amend-archived`/`_archive_door_offences`/
  `test_ref_amendments`/`lease_distribution`/`by_provider` in `tools/` und `.claude/` sind
  test_archive_door, test_board, test_ladder, test_migrate, test_report, test_schemas, test_state
  -- alle in der Liste des Umsetzers. `tools/test_kernel.py` liest `holes.citation_resolution`,
  die die Tür benutzt; `holes.py` hat die Nacharbeit nicht geändert (`test_modules_under` und
  `citation_resolution` gegenüber 5be585c unverändert), also fehlt keine Suite.

## Nicht gemessen
- Ob das `gate_write_scope` der Kits `mklink /J` in einem Kit-Projekt verweigert (die Kette
  über ein selbst geschriebenes Skript läuft unabhängig davon, H11).
- Die Laufzeit der Tür in einem Projekt mit `.venv` (`test_modules_under` steigt hinein, weil
  `.venv` kein `is_transient` ist; kein Hook, also keine Fristfrage).
- Volle Suite (Auftrag, DEC-0050).
- Nebenbei: der F3-Rest (Läufe je AUFWAND je Anbieter) steht nur im Protokoll, nicht als Grenze
  in BUG-0308 -- eine Zustandsschreibung des Leads, kein Befund gegen den Code (der Docstring
  sagt ehrlich "per rung").

## Blockiert die Runde?
Ja, F4: Einzeiler plus zwei Testzeilen. F5 gehört als benannter Rest in die Löcherliste.
