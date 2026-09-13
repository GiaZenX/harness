# Prüfbericht TSK-0146 (PR-0012, Order 4, Strom A Kern) — Runde 1 — **FAIL (F1 F5 F7 blockierend; F2-F4, F6, F8 Reste)**

Prüfer: `harness-verifier` (Opus, high), 34 min, 245 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-13 01:06, Uhr gelesen).

## Prüfbericht — Strom A (Kernel), TSK-0146 / PR-0012

Arbeitskopie (read-only gegen das Repo gearbeitet): `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0146\verify\` (Rig `verify\rig.py` — verweigert außerhalb des eigenen Verzeichnisses, gemessen: `cwd ... is not the rig's own directory`, und öffnet jede Datei mit expliziter Newline-Politik).
Offenlegung zur Lesedisziplin: `project_memory/staging/TSK-0146/protocol.md` habe ich **ganz** gelesen (453 Zeilen in drei Blöcken) — das war teurer als nötig.

---

### F1 — Die Zielklassen-Vokabel ist an beiden Türen mit EINEM Zusatzfeld umgehbar (blockierend)

`team-kits/kernel/state.py:1955` + `:1970`
```python
imported = isinstance(fields.get(LEGACY_FIELD), dict)
...
if imported and field == GOAL_CLASS_FIELD:      # -> continue
```
Die Ausnahme hängt am **Rumpf**, nicht am **Pfad**. `capture` nimmt seinen Rumpf als beliebiges JSON von stdin, also genügt ein `legacy_fields:`-Schlüssel.

Gemessene Zeile (`verify/clistore`, echte Kernel-CLI):
```
capture PR {... "class":"feature", "legacy_fields":{"legacy_id":"V1-1"}}  -> PR-0001 DRAFT, rc 0
capture PR {... "class":"feature"}                                        -> rc 1 (Verweigerung)
update PR-0002 {"class":"feature","legacy_fields":{...}}                  -> rc 0, gespeichert: class: feature
```
Folge: DEC-0103s „Verweigerung an capture UND update" ist nicht geschlossen; `migrate-goal-classes` räumt den Store auf, und dieselbe Sitzung schreibt einen Streuwert direkt wieder hinein. Die drei Leser fallen bei einem unbekannten Wert sicher aus (Architektenschritt wird gefordert, User Story wird gefordert, kein `large`-Effort) — es ist ein Integritäts-, kein Eskalationsloch.

Dazu Hausregel 3: `team-kits/kernel/dispatch.py:2370-2371` behauptet „a class outside the vocabulary — **only a stored one now, since capture and update refuse it**". Das ist nach obiger Messung falsch. Auch EVD-0431s Zusammenfassung („refusal at capture and update naming the four words") trägt diese Behauptung.

Minimaler Fix: die Ausnahme an den PFAD binden — `_assert_closed_vocabularies(item_type, fields, imported=False)` und `imported=True` nur aus `capture_migrated_*_preflight`; alternativ `LEGACY_FIELD` im gewöhnlichen `capture`/`update`-Rumpf verweigern (wie `status`/`hole_number`). Schwere: **hoch**.

### F2 — Das ZWEITE Ende des Stolperdrahts kann grün bleiben (Reihenfolgeabhängigkeit)

`tools/test_backlog_types.py:948` (`test_every_property_the_vocabulary_declares_is_asked_by_a_reader`) liest `goal_class_properties_asked()`, gefüllt vom Modul-globalen `_GOAL_CLASS_PROPERTIES_ASKED.add(carries)` in `team-kits/kernel/backlog_types.py:558`. Dort landet **jeder** Aufrufer, auch Testcode: `test_the_word_that_lifts_the_effort_is_exactly_one` fragt `the_one_goal_class_where("carries_product_content")` und registriert die Eigenschaft dabei.

Gemessene Zeilen (Mutation `report_reader_back_to_a_literal` = `report.PRODUCTLESS_CLASSES` wieder als Literal):
```
python -B rig.py report_reader_back_to_a_literal -- tools/test_backlog_types.py -q        -> 2 failed  (rc 1)
python -B rig.py report_reader_back_to_a_literal -- \
   ...::test_the_word_that_lifts_the_effort_is_exactly_one \
   ...::test_every_property_the_vocabulary_declares_is_asked_by_a_reader -q               -> 2 passed  (rc 0)
```
Heute rettet nur die Dateireihenfolge den Test; ein neuer Test oberhalb (oder `xdist --dist load`, xdist ist installiert) schaltet ihn stumm. Minimaler Fix: in `goal_classes_where` das aufrufende Modul mitschreiben (`sys._getframe(1).f_globals["__name__"]`) und `goal_class_properties_asked()` nur `kernel.*`-Aufrufer melden. Schwere: **mittel** (Restliste, wenn nicht sofort gefixt).
Gegenprobe, die hält: `fifth_word_no_reader` → 1 failed; `sr_exempt_back_to_a_literal` → 2 failed (A's Zeile reproduziert).

### F3 — „Gestempelt mit der Rolle der gebundenen Lease" misst kein Test

`team-kits/kernel/cli.py:1634` `role = dispatch.writing_role(state) ...` ist die einzige Stelle, die den Satz aus EVD-0433 baut — und kein Test fährt `kernel.cli evidence --fail-class` (grep `--fail-class` in `tools/`: nur `test_hooks_v2.py`, und das ist der Hook, nicht die CLI).

Gemessene Zeile (Mutation: die CLI stempelt konstant `quality-engineer`):
```
python -B rig.py cli_role_is_a_constant -- tools/test_ladder.py tools/test_state.py tools/test_kernel.py -q -k "fail or classif or evidence"
   -> 25 passed, rc 0
```
Minimaler Fix: ein Knoten in `tools/test_kernel.py`, der `cli.main(["evidence", ... "--fail-class", "mechanical"])` gegen ein Projekt mit einer gebundenen Lease fährt und prüft, dass `fail_class_by` die Lease-Rolle trägt. Schwere: **mittel** (Hausregel 5).

### F4 — Die Eigenschaft „BOUND lease" ist unmessbar geblieben

`team-kits/kernel/dispatch.py:2990` (`if not lease.get("agent_id"): continue`) ist genau der Satz, der die Rolle unfälschbar macht („das eine Statement, das der laufende Agent nicht selbst verfasst hat").

Gemessene Zeile (Mutation: Bindungsprüfung entfernt, also zählt auch eine ungebundene Lease):
```
python -B rig.py writing_role_ignores_the_binding -- tools/test_ladder.py -q  -> 57 passed, rc 0
```
Der von der Docstring benannte Test (`test_the_classification_is_refused_where_the_state_cannot_say_who_writes`) misst nur den `None`-Fall, nicht die Bindung. Minimaler Fix: ein Fall mit einer UNGEBUNDENEN Lease → `writing_role` muss `None` liefern. Schwere: **mittel**.

### F5 — Der Kommandoflächen-Rot ist breiter als übergeben (blockiert die Zielrunde)

Gemessen: `python -B -m pytest tools/test_hooks.py::test_every_span_that_presents_the_command_surface_names_all_of_it -q` → 1 failed, **fünf** Beanstandungen:
```
team-kits/dev-team/constitution/AGENTS.md: names 36, misses migrate-goal-classes, withdraw-request
team-kits/office-team/constitution/AGENTS.md: ... dito
team-kits/research-team/constitution/AGENTS.md: ... dito
README.md: ... dito
team-kits/kernel/cli.py: names 3, misses <35 Kommandos>
```
Das Protokoll (Row 4) nennt nur `withdraw-request` und nur die vier Dokumente. Zwei Lücken: **`migrate-goal-classes` fehlt in denselben vier Dokumenten** (DEC-0102 (4) gilt auch für Row 1), und A hat den fünften Treffer selbst verursacht: `team-kits/kernel/cli.py:2121` schreibt `` `withdraw-request` `` in Backticks in einen Block, der schon `` `dispatch` `` und `` `validate` `` enthält — damit kippt er über `_SURFACE_SPAN_MIN = 3`.
Gemessene Zeile für die Ursache: Mutation `cli_comment_without_backticks` (Backticks an 2121 weg) → derselbe Knoten meldet nur noch die vier Dokumente.
Minimaler Fix: Backticks an `cli.py:2121` entfernen (A's eigene Datei) + im Seam-Patch **beide** Kommandos in die drei AGENTS.md §0 und `README.md:335` aufnehmen. Schwere: **mittel, blockiert** — der Patch, wie er übergeben wurde, lässt den Knoten rot.

### F6 — Die offengelegte Gate-1-Lücke trägt den falschen Mechanismusnamen

Protokoll Row 3, „MEASURED GATE LIMIT": „ein Pfad, der nur im heredoc-RUMPF steht, ist kein Wort". Gemessen gegen das Gate (Prozess, JSON auf stdin, gegen die KOPIE, kein Schreibzugriff):
```
printf 'x' >> project_memory/project_config.yaml            -> rc 2
cp README.md project_memory/project_config.yaml             -> rc 2
sed -i ... project_memory/project_config.yaml               -> rc 2
bash run.sh project_memory/project_config.yaml              -> rc 2
python -c "open('project_memory/project_config.yaml','a')"  -> rc 2
python tools/x.py project_memory/project_config.yaml        -> rc 0   <- Pfad IST ein Wort der Zeile
python -m json.tool project_memory/project_config.yaml      -> rc 0
python - <<'PY' ... PY                                      -> rc 0
```
Der Mechanismus ist nicht der heredoc, sondern `.claude/hooks/_harness.py:1081-1099` `_runs_a_program`: jedes `python …` außer `-c` gilt als ausführend, seine Operanden werden nicht beurteilt. Das steht dort im Kopfkommentar und liegt als **H11** schon in der Löcherliste. Ein neuer Eintrag „heredoc-Rumpf" wäre eine Dublette mit einer zu engen Beschreibung (DEC-0102 (2)). Schwere: **mittel** (Berichtsfehler, kein Codefehler).

### F7 — EVD-0431 schließt BUG-0237, ohne dessen zweite gemessene Restklasse zu nennen

`project_memory/bugs/active/BUG-0237.yaml` `limits:` trägt eine ZWEITE, am ausgelieferten Haken gemessene Klasse (die Befreiung fragt den TYP des Ursprungs, nicht den WERT; Referenz nur an der WURZEL → rc 0 am Spawn), festgehalten in `tools/test_approvals_dispatch.py:4846` als Test, der mit H155 rot werden soll. EVD-0432 und EVD-0434 tragen je einen „NOT closed"-Satz, **EVD-0431 nicht**. Wird BUG-0237 (hole_number H155) geschlossen, verschwindet der Zeiger des Tests ins Leere. Minimaler Fix: die Restklasse vor dem Schließen als eigenes Loch/Item einreihen oder in einer nachfolgenden EVD benennen. Schwere: **klein, aber Prozess-blockierend für die Batch-Zeile `BUG-0237`.**

### F8 — Kleinere, gemessene Reste (keine Blocker)

- `team-kits/kernel/dispatch.py` `record_fail_class`: schreibt das Item mit `state._write_yaml_atomic` **ohne** `revision`-Erhöhung (Codelesung, nicht gerannt). Wer `revision` als Änderungszähler liest, sieht den Stempel nicht; eine offene Freigabe über denselben TSK bricht dagegen am Manifest-Hash (fail-closed).
- Fenster zwischen Urteil und Stempel: `cli.py:1635` fragt `fail_class_refusal` **ohne** Lock (liest u. a. `status == FAILED`), `record_fail_class` nimmt den Lock erst danach. Ändert sich der Status im Fenster, landet der Stempel auf einem Auftrag, der nicht mehr FAILED ist, und wird bei der nächsten Lease auf einen **anderen** Lauf verbraucht — Richtung: billigeres Modell beim Retry, also die unsichere. Anmerkung zum Auftrag: A benennt diese Lücke **nicht**; die einzige Lock-Notiz im Protokoll (Zeile 218) gehört dem Rückzugspfad.
- `approvals.sweep_expired_requests` (`approvals.py:3542`) meldet `"withdrawn": stale` = die Ids, die es zurückziehen **wollte**; `withdraw_request` läuft außerhalb des Lock-Halts und wirft `ApprovalError`, wenn die Frage inzwischen beantwortet wurde — gemessen, dass so ein Fehler den Aufrufer abbricht (`probe_hook.py`-Traceback an einer nicht-pending Id). Dann ist ein Teil zurückgezogen und der Aufrufer bekommt eine Ausnahme statt eines Berichts.
- `approvals.py:3639` / `:3123`: die Entwickler-Sätze zählen weiter „(consumed, expired-and-cleaned, or never created)" — der vierte Ausgang (withdrawn) fehlt dort; der NUTZER-Satz ist korrekt (gemessen).
- `sweep-requests --stale 1` meldet in derselben Ausgabe Ids unter „dead", die es soeben zurückgezogen hat (kosmetisch, gemessen).

---

## Negativbefunde

**Gemessen und in Ordnung**

- DEC-0103 Ende 1 des Stolperdrahts: `fifth_word_no_reader` → 1 failed; `sr_exempt_back_to_a_literal` → 2 failed (A's Zeile reproduziert).
- Verweigerungstext an **beiden** Türen nennt alle vier Wörter MIT Wirkung und die drei Leser — wörtlich gemessen an `capture` und `update` (`probe_vocab.py`).
- Keine zweite Schreibweise der Menge: grep über `team-kits/` und `tools/` findet `technical_enabler` nur noch in `backlog_types.py` (Definition), in Prosa und in Fixtures; die drei Leser sind abgeleitet.
- Migration: Kopie des echten Stores → `12 stored goal(s)`, alle „already a word of the vocabulary", vorher = nachher; Streuwert-Kopie → Plan rc 1 mit `UNDECIDED`, `--map feature=normal --apply` rc 0 mit `written:`-Zeilen.
- DEC-0107 Verbrauch: Mutation `counter_does_not_consume` → `test_a_mechanical_fail_does_not_climb_and_an_ordinary_one_does` rot (AssertionError `test_ladder.py:1343`); der Test misst genau „zwei FAILED-Läufe, einer mechanisch → 1 gezählt".
- `fail_class`/`fail_class_by` an beiden Türen verweigert, **ohne** Legacy-Ausnahme (Code + Test grün).
- DEC-0105, an echten Projektkopien (nicht an Fixtures): gültige `ladder.yaml` + Config-Zeile → `rung opus / effort xhigh`, Quelle „the tier file project_config.yaml names (ladder.yaml)"; kaputt/fehlend → `absent`-Zeile, die **die Datei mit Pfad nennt**; ohne Config-Zeile → `absent` nennt `model_tiers:`; mit Scaffold-Datensatz → `ladder.yaml of kit 'dev-team'`, die Config-Datei wird ignoriert. `_valid_ladder` existiert genau einmal (`dispatch.py:2696`), beide Pfade rufen sie.
- BUG-0302 an Store-Kopien: `sweep-requests` → 11 offen / 7 tot, nichts gelöscht; `withdraw-request` → Datei in `approvals/withdrawn/` mit `withdrawn_at` + `withdrawn_reason`, `open_requests` 11 → 10; später Klick (`mint`) → verweigert, Nutzertext „diese Frage wurde zurückgenommen … an dir liegt es nicht", 69 APR-Dateien unverändert; `--stale 1` → alle 11 in `withdrawn/`, `pending/` leer, `--stale 100000` → nichts.
- Der Haken als **echter Prozess** (dev-team `_gate.py gate_approval.py`, JSON auf stdin, handgebautes Projekt, Registrierung aus dessen `settings.json` gelesen: PostToolUse/AskUserQuestion, timeout 120): mit offener Anfrage `note: True` („11 approval request(s) outstanding…"), nach `withdraw-request` `note: False` — **True → False bestätigt**.
- Die vier EVDs durch `naming_tests.coverage_blocker`: alle vier „schließt das Item". Alle vier `run_command` nachgefahren: 4/3/5/4 passed.
- Batch-Zeilen gegen die Store-Kopie im Checkout: `["BUG-0237","BUG-0302"]` → 2 Zeilen, alle vier → 4 Zeilen, 0 verweigert. **Das Zurückstellen von BUG-0260 und BUG-0253 ist richtig**: BUG-0260 AC-1 verlangt DEC + Parity-Matrix + die QA-Skills (Strom B/C), BUG-0253 AC-1 verlangt „this repository's roles get one" (die Config-Zeile + `ladder.yaml`, beides offen).
- A's Rückgabe-Begründung zu DEC-0105 ist korrekt: Gate 1 (registriert für `Write|Edit|MultiEdit|NotebookEdit` **und** `Bash|PowerShell`, timeout 120) verweigert jeden Werkzeug-Schreibzugriff auf `project_memory/project_config.yaml` — rc 2 für Bash **und** Write; `ladder.yaml` an der Repo-Wurzel ist rc 0, dort blockiert nur der `allowed_scope` des Items.
- H160: alle drei Kit-Hashes weichen vom Stempel ab (dev `b3d9091678a7…` → `0a109bcf50dd…`, office → `0d22a09ffba7…`, research → `a4b94b63fd92…`); `tools/test_pointer_sweep.py` → 4 failed, alle in der Scaffold-Klasse. A's „erst nach dem Stempel messbar" steht.
- `ruff check team-kits/kernel/ tools/` → All checks passed.
- Jeder in den geänderten Kernel-Dateien in Backticks genannte Testknoten löst auf (158 Nennungen geprüft; die acht „Fehlmeldungen" meines Lesers sind Zeilenumbrüche bzw. Prosa über einen Knoten). `tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves` → 1 passed.
- Scope: die geänderten Dateien in A's Revier (`team-kits/kernel/*.py`, `tools/test_{state,backlog_types,kernel,report,ladder,migrate,approvals_dispatch,board}.py`) liegen alle im `allowed_scope`; `project_memory/project_config.yaml` und die `.claude/agents/harness-*.md` sind unberührt.
- Der reale Store blieb durch meine Läufe unverändert (`git status --porcelain project_memory/approvals` leer).

**Nicht gemessen (offen gelassen)**

- Die volle Suite und alle Dauer-Angaben aus A's Laufprotokoll (Prüferpflicht ist Messung, nicht Wiederholung — die Auswahlen, die Befunde tragen, habe ich selbst gefahren).
- Die vier „foreign/unstamped"-Reds außer `test_pointer_sweep.py` (`test_research_chain`, `test_light_kit`, `test_kitupdate`) — nur A's Ursachenkette wurde stichprobenartig über die Hashes bestätigt.
- Der Lock-Wettlauf in F8 als echtes Rennen (zwei gleichzeitige Schreiber); begründet aus Code + einer gemessenen Fehlerfortpflanzung.
- Ob der reale Gate-1-Durchlass (F6) auch tatsächlich in dieses Repo schreibt — die Messung hätte in den Store geschrieben, den ich nur lesen darf; gemessen ist die Gate-Entscheidung (rc 0) gegen die Kopie.
- H113-Form und H59-Frage inhaltlich nur gelesen, nicht gemessen (es gibt nichts Laufendes).
- `.claude/hooks/test_gates.py` und die Hook-Suiten der Nachbarströme.

---

## Urteil: **FAIL**

**Blockiert die Runde:**
- **F1** — die Vokabel ist mit einem Zusatzfeld an beiden Türen umgehbar, die Kette läuft in einer Sitzung durch (`capture PR … "legacy_fields":{…}` rc 0), und `dispatch.py:2370` behauptet das Gegenteil. Entweder die Ausnahme an den Pfad binden oder die Lücke mit ihrem Mechanismus in die Löcherliste — ein dritter Zustand existiert nicht. EVD-0431 trägt die Behauptung mit und müsste ebenfalls berichtigt werden.
- **F5** — der übergebene Seam-Patch macht den Kommandoflächen-Knoten nicht grün (zweites Kommando + `cli.py:2121`).
- **F7** — solange die zweite Restklasse von BUG-0237 nicht neu eingereiht ist, schließt die Batch-Zeile `BUG-0237` ein gemessenes Loch weg.

**Als benannte Reste in die Löcherliste (nicht rundenblockierend):**
- **F2** (Stolperdraht-Ende 2 reihenfolgeabhängig — Einzeiler-Fix, billiger als der Eintrag),
- **F3** und **F4** (zwei Eigenschaftsbehauptungen von DEC-0107 ohne Test: Stempel aus der Lease, Bindung der Lease),
- **F6** (Korrektur der Mechanismusbeschreibung; der Sachverhalt ist H11 und braucht keinen neuen Eintrag),
- **F8** (Revisionsstempel, Urteil-/Schreib-Fenster, Sweep-Abbruch, dritter Aufzählungssatz in `mint`).