# TSK-0152 -- Prüfbericht Runde 1 (Prüfer), 2026-09-26

Kopien (ohne .git, Byte-Kopie, eigenes Rig `mkcopy.py`, verweigert fremdes cwd, schreibt binär):
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0152/verify/{repo,patched,proj}`.
`proj` = eigenes dev-team-Pilotprojekt, per `init_project_memory.sh` + `scaffold_team.sh` aus den
Kits der Kopie gebaut (HOME auf eine Schein-Heimat umgebogen); die Hook-Liste kommt aus dessen
`settings.json` (10 PreToolUse-Hooks auf `Bash`), gefahren mit Git-Bash als echte Prozesse.
Gelesen: TSK-0152, DEC-0117, protocol.md (ganz, 350 Zeilen), user-patch.md (ganz), CI-Log nur an
den Fehlerstellen. Keine volle Suite gefahren (Auftrag).

## Urteil: FAIL

## Befunde

### F2 (blockierend) -- die Archiv-Tür nimmt einen neuen Testknoten AUSSERHALB des Checkouts an
- `team-kits/kernel/archive_door.py:119-127`: "resolves" wird `holes.citation_resolution` ->
  `naming_tests.declares` gefragt, und das rechnet `os.path.join(root, path)` ohne Eingrenzung.
- Gemessen (`verify/door_attack.py`, `verify/door_abs.py`, echtes `kernel.cli.main`):
  - `--new ../outside/test_elsewhere.py::test_far_away` -> **rc=0**, das archivierte Item nennt
    danach `../outside/test_elsewhere.py::test_far_away`;
  - `--new C:/Users/.../scratchpad/outside/test_far.py::test_far_away` (absolut, ohne Leerzeichen)
    -> **rc=0**;
  - `--new project_memory/staging/X/test_throwaway.py::test_scratch` -> **rc=0** (Wegwerfdatei,
    die keine Testfläche fährt).
  Ein absoluter Pfad MIT Leerzeichen wird nur zufällig verweigert: `_node` entfernt jedes
  Leerzeichen ("Offline Repos" -> "OfflineRepos").
- Die Meldung derselben Stelle (`archive_door.py:126`) behauptet "does not resolve to a test in
  this checkout" -- eine Eigenschaft, die der Code nicht baut (Hausregel 3).
- Warum blockierend: das ist die NEUE Fläche der Runde (vorher war das Archiv unerreichbar), die
  Kette läuft in einer Sitzung durch, und sie trifft DEC-0117 (1)/(4) im Kern: der
  Regressionstest eines geschlossenen Bugs verschwindet faktisch. In diesem Repo fängt es
  `.claude/hooks/test_gates.py::test_every_test_a_hole_names_is_one_that_exists` (liest nur
  `tools/test_*.py` + `test_gates.py`) -- in einem Kit-Projekt, in das der Kernel ausgeliefert
  wird, steht dahinter nichts.
- Minimaler Fix: den neuen Knoten verweigern, wenn der normalisierte Pfad absolut ist oder den
  Checkout verlässt (`os.path.normpath(path)` beginnt mit `..`); je Schreibweise (`../`, absolut)
  eine Zeile im parametrisierten `test_a_new_node_that_does_not_resolve_now_is_refused`, rot
  gegen den heutigen Stand. Ob eine Wegwerfdatei unter `project_memory/staging/` zählen darf, ist
  eine Frage an DEC-0117 ("collectable") -- mindestens in die Löcherliste.

### F1 (blockierend, billig) -- `test_the_audit_record_has_one_writer` misst die HÄLFTE seines Docstrings
- `tools/test_archive_door.py:163` Docstring: "Capture and update refuse a body that carries the
  audit field"; `team-kits/kernel/backlog_types.py:727` nennt den Test als Beleg für "capture and
  update refuse". Der Test ruft nur `state.capture`.
- Mutation `team-kits/kernel/state.py:1529` `audited = _archive_door_offences(changes)` ->
  `audited = []` (d. h. `update_item` nimmt `test_ref_amendments` an), gefahren über
  `tools/test_archive_door.py tools/test_kernel.py tools/test_backlog_types.py
  tools/test_approvals_dispatch.py tools/test_migrate_holes.py tools/test_staging_cli.py`:
  **557 passed** (MUTATION rc=0). Kein Test sieht die update-Hälfte (DEC-0080 Regel 6).
- Fix: im selben Test `state.update_item(<aktiver BUG>, {TEST_REF_AMENDMENTS_FIELD: [...]})` mit
  `pytest.raises(StateError, match="archive door")`; rot gegen die Mutation oben.

### F3 (niedrig, Restposten oder mitnehmen) -- BUG-0308: Aufwände je Anbieter behauptet, nicht gemessen
- `team-kits/kernel/report.py:307`: "counted under its own name in `by_provider` -- rungs,
  efforts and runs to hand-back per rung".
- Mutation `for key, bucket in ((RUNG_KEY, "rungs"), (EFFORT_KEY, "efforts"))` ->
  `((RUNG_KEY, "rungs"),)`: `tools/test_ladder.py tools/test_report.py tools/test_schemas.py` ->
  **238 passed** (rc=0). `tools/test_ladder.py:524` prüft `rungs` und Läufe je Stufe, nie
  `efforts`. Die Zeile nennt für andere Anbieter nur Stufen; Läufe je Aufwand gibt es je Anbieter
  gar nicht (DEC-0097 (4): beide Achsen) -- das gehört als Grenze in die Zeile von H221.
- Fix: eine Zusicherung auf `shown["by_provider"]["codex"]["efforts"]`.

## Negative Befunde -- gemessen

- **Archiv-Tür, Verweigerungen:** `--field status` / `--field Regression_tests` rc=1, Item
  unverändert; Mutationen selbst gefahren: `if still:` aus -> rot; update-Verweigerung aus -> grün
  (F1). Die Schreibweise der Feldnamen ist exakter String-Vergleich.
- **Die zwei Zeilen des Leads** (protocol Abschnitt 1) in der Kopie gefahren: beide rc=0, Diff =
  genau `regression_tests` + `test_ref_amendments` (who/when/field/old/new/reason wahrheitsgemäß)
  in BUG-0221/BUG-0237, sonst kein Feld; `docs/POST_V2_WISHLIST.md` ändert genau die Zeilen H138 und
  H155 (Stand "; Testverweis korrigiert 2026-09-26 (1x)"). Danach
  `test_every_test_a_hole_names_is_one_that_exists`, `..._hole_index_in_the_document_...` und
  `test_every_check_this_apparatus_...` **3 passed**; `kernel.cli validate` rc=0, 0 errors. Laufzeit
  je Türaufruf ~18 s (Hole-Index über den ganzen Store; ein CLI-Befehl, kein Hook).
- **Board-Ausnahme:** `board.py` liest aus dem Archiv nur `archived_counts`; die Tür schreibt in
  place. Hält.
- **BUG-0305** an allen 10 registrierten Bash-Hooks des eigenen Piloten
  (`verify/battery_0305.log`): die drei AC-Zeilen plus `command -p cat` / `exec -a foo cat` rc=0;
  alle BUG-0304-/TSK-0150-F2-Angriffszeilen (`A=1 ./run.sh`, `exec ./run.sh`, `command ./run.sh`,
  `bash < run.sh`, `sudo -u me ./run.sh`, `command -p`, `env -i`, `nice -n 5`, `exec -a foo bash`,
  Präfixkette) rc=2; `tee` hinter bekannter Option rc=2 "this line WRITES"; Selbstprüfungsfall
  `sudo -E cat x ; sudo -E wc x ; bash x` rc=2 "may WRITE ... -E", kein "this line WRITES";
  `sudo -E cat x > run.sh ; bash run.sh` sagt "WRITES" (die Umleitung ist ein echter Schreiber) --
  der Satz ist in beiden Richtungen wahr. Mutationen (dev-Kit): may-WRITE-Zweig aus -> BUG-0305-Test
  rot; Options-Schritt aus -> 6 rot. `_compat.py`, `_kernel.py`, `gate_write_scope.py` in allen
  drei Kits hash-identisch.
- **BUG-0264:** Test startet Gate 2 als Prozess, liest keine Prosa, nennt BUG-0264; Mutation
  "`schedule` im Text befreit" -> rot.
- **BUG-0069:** CI-Log an den Fehlerstellen: ubuntu 1 (artifact refs), windows 3 (artifact refs,
  zoneinfo, relpath über Laufwerke) -- genau die drei des Protokolls. Mutationen: `.gitignore`-
  Negation weg (in einer git-initialisierten Kopie) -> BUG-0069-Test rot; `tzdata` weg -> rot;
  `_spelled`-Laufwerksvergleich weg -> rot. Kein messender Test übersprungen (der Laufwerks-Test
  läuft nur auf Windows, sudo-Fall nur wo sudo existiert, beide benannt). `.gitattributes`
  `eol=lf` normalisiert die zwei CRLF-Logs beim Commit.
- **Nutzerpatch in `verify/patched`:** `--check` 7 / apply 7 / `--check` 0 ("already done") /
  apply 0. Gate-Auswahl `bug_0105 or bug_0233 or bug_0161 or watch_list` **6 passed**;
  Mutationen am gepatchten Code: Verzeichnis-Schleife aus -> bug_0105 + bug_0233 rot; CR-Tür aus ->
  bug_0161 [beide Aufrufer] rot. Breitere Auswahl (`gate1 or ... or protected or producer`):
  279 passed, 1 failed = `test_gate1_answers_before_its_registration_gives_up` mit
  "timing noise 0.62s > band 0.55s" -- allein wiederholt **1 passed** (Host unter Fremdlast; kein
  Patchbefund). Payload-Batterie gegen die gepatchten Repo-Gates (`verify/probe_patched.log`):
  Sitzungsagent `Write`/`MultiEdit`/`NotebookEdit`/Bash/PowerShell auf `tools/<neu>`,
  `TOOLS\sub\new.py`, `tools/../tools/new.py`, `tools/test_surface.json`, `cp ... tools/` alle rc=2;
  pytest-Auswahl unter `tools/`, `bump_kit_version.py --check`, `docs/`, `staging/` rc=0; Subagent
  auf `tools/` rc=0; CR-Zeile rc=2 für beide Aufrufer. Langsamster Hook 1,9 s bei 120 s Frist.
  PowerShell mit CR: rc=0 am Gate, und echte PowerShell schreibt NICHT durch (CR ist dort ein
  Zeilenende; `verify/ps_cr.py`: index.yaml unverändert) -- kein Loch.
- **Stempel/Struktur:** `bump_kit_version.py --check` unverändert 2026.09.26-3 (Repo und gepatchte
  Kopie); `ruff` "All checks passed!"; `validate.py` "all structural checks passed".

## Nicht gemessen

- Office-/Research-Pilot als eigene Projekte (Gate-Dateien hash-identisch zum dev-Kit, daher nur
  dev gefahren).
- Die ganze Gate-Suite mit Patch (Auftrag: nur Auswahlen); die volle tools-Suite (Auftrag).
- Ob Gate 1 im echten Repo die zwei Türzeilen des Leads durchlässt.
- `sudo`-Hälfte des Präfix-Stolperdrahts (kein sudo auf diesem Host).
- H47/BUG-0139: `F=tools/new.py; echo x > $F` bleibt rc=0 im gepatchten Stand -- erwartet, als
  Klassenfrage auf Deutsch im Protokoll.
- Ob ein zukünftiger Schreibzugriff der Tür auf ein AKTIVES Item vom Board-Begründungstest gesehen
  würde (der vergleicht Dateinamen und Zählungen, nicht Inhalte) -- heute schreibt die Tür keins.

## Blockiert die Runde?

Ja: F2 und F1 (beide klein). F3 kann als benannter Restposten an H221 gehen oder mitgenommen
werden. Die Türzeilen für H138/H155 erst nach dem Fix von F2 fahren.
