# Prüfbericht TSK-0150 (PR-0012, Order 5) — Runde 1 — **FAIL (F1 F2 blockierend; F3 F4 Reste)**

Prüfer: `harness-verifier` (Opus, high), 38 min, 224 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-13 14:23, Uhr gelesen).

## Prüfbericht TSK-0150 (PR-0012, Auftrag 5) — **FAIL**

Arbeitskopie: `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0150\verify` (bytegleich zum Repo geprüft: 0 Abweichungen über `team-kits/ tools/ docs/ .claude/ radar/ user/ .github/`), Piloten `…\pilot-dev`, `…\pilot-office`, `…\pilot-research` (aus dieser Kopie gescaffoldet), Rig `…\work\rig.py` (verweigert Start außerhalb des eigenen Verzeichnisses, schreibt binär/explizite newline-Politik). Repo nur gelesen. Ganz gelesen habe ich `project_memory/staging/TSK-0150/protocol.md` (130 Z.) und `runs.md` (71 Z.) — die Kosten sind damit sichtbar.

### Befunde

**F1 — `team-kits/kernel/approvals.py:2273-2275` (Behauptung) + fehlender Wächter in `team-kits/kernel/state.py:864/1445`: DEC-0113s Antwort ist von Hand schreibbar, die Frage damit ganz überspringbar — BLOCKIEREND**
Der Docstring sagt „This is that write, and it is the only one … die beiden Felder stehen hier, damit die Abnahmekarte zeigt, was der Nutzer wirklich gefragt wurde."
Gemessen als Prozess im dev-Piloten:
```
echo '{"unverified_acceptance_answer":"ja klar (nie gefragt)"}' | kernel.cli update PR-0002  -> PR-0002 DRAFT rev 1
kernel.cli request-approval acceptance PR-0002                  -> rc 0, Karte: "ACHTUNG: Antwort des Nutzers dazu: ja klar (nie gefragt)"
```
Dasselbe über `capture` (PR-0003, Felder im Body) → rc 0, Karte nennt zusätzlich eine erfundene Fehlliste. Folge: die Karte legt dem Nutzer Worte in den Mund, die er nie gesagt hat, und `verification_missing_for_goal` wird nie befragt — „einmal pro Ziel" wird zu „null Mal". DEC-0113 verlangt ausdrücklich „written by the request path, **not by hand**". Minimaler Fix: die beiden Felder in denselben Verweigerungsmechanismus wie `LEGACY_FIELD`/`_role_judged_offences` (state.py:1438-1447) und in die `capture`-Prüfung (state.py:864) aufnehmen, plus zweiseitige Testzeile.

**F2 — `team-kits/dev-team/hooks/gate_write_scope.py:1015-1033` `_command_word_at` (x3 gespiegelt); `docs/holes/H219.md:47-48`: der BUG-0304-Fix wird durch **ein Optionswort** der Präfixe wieder aufgemacht, die er selbst führt — BLOCKIEREND**
Der Leser überspringt `sudo|env|command|exec|time|nice`, aber nicht deren Flags; das Flag wird dann selbst zum „Kommandowort", und das echte Programm rutscht in die Operandenrolle. Gemessen gegen die **vollständige registrierte PreToolUse-Bash-Batterie** des dev-Piloten (10 Gates aus dessen `settings.json`, `timeout` 120 s bzw. 1800 s; Laufzeiten 0,1–0,2 s):
```
printf 'x' > run.sh ; bash run.sh          -> refused by: write_scope=2      (Kontrolle)
printf 'x' > run.sh ; exec -a foo bash run.sh -> refused by: NOBODY (rc 0 all round)
printf 'x' > run.sh ; nice -n 5 ./run.sh      -> refused by: NOBODY (rc 0 all round)
printf 'x' > run.sh ; sudo -u me ./run.sh     -> refused by: NOBODY (rc 0 all round)
```
Und in allen drei Kits rc 0 auch für `command -p ./run.sh`, `env -i ./run.sh`. Die echte Shell führt aus (bash auf diesem Host, Marker-Datei): `exec -a foo ./run.sh`, `nice -n 5 ./run.sh`, `command -p ./run.sh`, `env -i ./run.sh` → alle `executed=True`. `exec -a foo bash run.sh` macht damit sogar das ursprüngliche H214-Paar wieder auf. Es ist **nicht** die im Code und in `H219.md` benannte Restklasse („ein Präfixwort, das `_command_word_at` nicht führt" — `nohup` rc 0 ist erwartet und dokumentiert); es ist eine eigene Mechanik, nirgends benannt. Minimaler Fix in der Richtung, die dieses Repo selbst schon fährt (`_harness._executed_words`: „jeder Operand einer Stufe, deren Verb dieser Leser nicht als Programm benennen kann"): trifft der Lauf nach einem Präfixwort ein Wort mit `-`, ist das Kommandowort **unbekannt** → jeder pfadförmige Operand zählt als RUN (fail-closed; kein Alltagssatz schreibt und startet dieselbe Datei).

**F3 — `team-kits/office-team/hooks/_duties.py:504` (period der Forderungs-Speisung): ein `done`-Eintrag löscht mehr als eine Pflicht — benannter Rest (nicht blockierend, aber Löcherliste)**
`_duties.py:24-25` behauptet „nur dieser Schlüssel", der Test heißt `…drops_out_of_the_register_and_only_that_one`. Gemessen im office-Piloten mit einem Ledger ohne `invoice_no`/`id` (der Fallback `or "?"` im Code sagt selbst, dass es den Fall gibt):
```
9fdce45d180fd1c2 | receivable_duties | ? | invoice ? to Kunde A ...
9fdce45d180fd1c2 | receivable_duties | ? | invoice ? to Kunde B ...
kernel.cli duty-done --key 9fdce45d180fd1c2 ... -> recorded
Register danach: nur noch die routine-Pflicht — BEIDE Rechnungen weg
```
Die Tropfrichtung ist die gefährliche (eine offene Forderung verschwindet still). Der Drop-Code selbst ist sauber (beide Mutationen rot, s. u.); die Lücke sitzt im Schlüsselmaterial. Fix: Kollision im `register` erkennen → kollidierende Pflichten stehen lassen + `unreadable`-Zeile, oder Feed-seitig eine zeilen-eindeutige `period`.

**F4 — `team-kits/kernel/approvals.py:2304`: der vorgeschriebene deutsche Satz ist falsch, sobald *eine* Nachweisart fehlt — klein, aber Hausregel 3 (Über-Alarm)**
```
EVD test/pass/full zu PR-0005 vorhanden
-> "PR-0005 is about to be accepted and nothing in this project measured it: no passing QA Evidence of kind(s) acceptance, review ...
   »Für PR-0005 hat niemand geprüft, ob die Arbeit wirklich tut, was sie soll.«"
```
DEC-0113 spricht vom Ziel „without **any** verification run"; gebaut ist „eine Art fehlt". Fix: der Satz nennt die fehlenden Arten auch auf Deutsch, oder die Frage entsteht erst, wenn *keine* Art vorliegt. (Nebenbemerkung, kein Befund: DEC-0113 sagt „no refusal in the kernel", gebaut ist eine Verweigerung der **Anfrage** ohne `--unverified-answer`; der Docstring trennt das sauber, und ohne diese Hälfte gäbe es keinen Zwang zur Frage — das halte ich für getreu, nicht für Abweichung.)

### Negative Befunde — gemessen

* **DEC-0112**: kein Prosa-Negationsleser überlebt (`grep` über `team-kits/ tools/ .claude/` nach `_denies_a_test|_sentence_names_a_test|_complement_of|_DENIES_RX|…` → leer). Alle vier historischen Sätze kaufen nichts (beide Feeds `False`), geformte Formen kaufen (`tools/test_x.py`, Knoten-Id, Backticks, `tests/…`, `x_test.go`, `x_spec.rb` → `True`; `docs/test-plan.md`, `testimonials.md`, `tests`, `test` → `False`). Drei Mutationen von `_names_a_test_artefact` (Typografie-Strip weg / Knoten-Suffix nicht abgeschnitten / Substring-Leser) → jeweils rot, u. a. `test_the_shaped_form_is_an_address_at_three_levels`, `…buys_nothing_since_the_prose_reader_is_retired`. Einziger Aufrufer ist `acceptance_is_test_shaped`; die Verweigerungs-`why` nennt die geformte Form (dispatch.py:3465-3469). Leittexte: dev/research `ladder.yaml:73-80`, beide `AGENTS.md`, beide PM-`SKILL.md`. Die Zwei-statt-drei-Kits-Abweichung ist begründet und stimmt (`ROOT_TYPE_BY_KIT = {dev-team: PR, research-team: RQ}`, office `ladder.yaml:86 build: pin`).
* **DEC-0113 als Prozess** (dev- und research-Pilot): Anfrage ohne Antwort rc 1 mit der deutschen Frage; mit Antwort rc 0, Felder auf dem Ziel, Karte nennt Antwort **und** fehlende Läufe („ohne Nachweis geblieben: acceptance / review / test"); zweite Anfrage fragt nicht erneut; zweite Antwort verweigert; Ziel mit allen drei Pass-Läufen wird nicht gefragt und `--unverified-answer` dort verweigert; RQ-Pfad identisch. `SPOKEN_MANIFEST_FIELDS` ist zweiseitig: toter Eintrag (`revision`) → rot.
* **H113**: `duty-done` über die CLI im office-Piloten — `recorded`, zweiter Aufruf `already recorded` mit der **ersten** Notiz; eigene `period` → Pflichten stehen wieder (R-1/R-2). Mutation `done_keys → set()` **und** Mutation „ein done löscht alles" → beide rot in `test_a_duty_recorded_done_drops_out_of_the_register_and_only_that_one`.
* **BUG-0303 als PROZESS** (die Messung, die der Umsetzer schuldig blieb): hohler BUG-Ursprung + Kriterium nur an der Wurzel → `kernel.cli dispatch TSK-0001` rc 1 mit der Architekten-Begründung. Mit der Wert→Typ-Mutation im Kernel: `dispatch` rc 0 (Lease erteilt) **und** `gate_dispatch.py` als Prozess rc 0 auf den Spawn — die H218-Kette läuft vor dem Fix bis zum Spawn durch, nach dem Fix nicht mehr. Dieselbe Mutation macht `test_an_origin_that_names_no_criterion_excuses_no_architect_step` rot.
* **BUG-0304 Positivseite**: die fünf Formen rc 2 in allen drei Kits; die vier Alltagszeilen und `bash $(which ci.sh)` rc 0; die neun älteren Formen rc 2; zusätzlich rc 2 für `nice`, `time`, `env A=1`, `bash <run.sh` (ohne Leerzeichen), `bash 0< run.sh`, `eval "$(<run.sh)"`. `nohup` rc 0 = benannte Restklasse.
* **Nacharbeit nach dem Volllauf**: alle drei mit eigener Mutation rot — gekürzter Verfassungsabschnitt → `test_no_section_of_a_pinned_instruction_file_disappears_unnoticed`; `duty-done` aus einer Verfassung entfernt → `test_every_span_that_presents_the_command_surface_names_all_of_it`; Beispiel-Knoten-Id wieder in `docs/holes/H113.md` → `test_every_test_pointer_this_repo_writes_resolves`. Der neue Leser `.claude/hooks/test_gates.py::_the_kits_prefix_walk` hält, was sein Docstring behauptet: Walk **eine Ebene tiefer** verschoben → weiter grün (ein Name/eine Tiefe wäre gerissen).
* **DEC-0050-Urteil**: nach dem Lauf (Ende 12:42:39) wurden 20 Dateien berührt — Texte, Pins, Größenjournal, VERSION, generierter Löcher-Index, `document_trays.txt` (inhaltsgleich, git sieht keine Änderung) und **eine** Codedatei: `team-kits/kernel/dispatch.py` 12:45:35 (Kommentar/Docstring). Ich habe deren schwerste Suite auf dem ausgelieferten Baum nachgefahren: `tools/test_approvals_dispatch.py` **235 passed in 104,8 s**. Die Gate-Suite sammelt heute **555 Tests** = die gemeldeten 552+3. Damit ist der Verzicht auf einen zweiten 2:14-Lauf innerhalb DEC-0050 — kein Verhalten hat sich danach geändert.
* **Auslieferungspflichten**: `bump_kit_version.py --check` → alle drei „unchanged (2026.09.13-5)"; `ruff check .` sauber; `tools/validate.py` grün; Kernel-`validate` rc 0 (nur Archiv-Warnungen); `generate-index` in der Kopie = Store bis auf `generated_at`; `gen_known_holes.py` reproduziert beide Dateien bytegleich; Spiegel `gate_write_scope.py`/`_routine.py` in drei Kits bytegleich (Hash), Mirror-Tests 3 passed; Decken 61219/66492/63075 mit Journalzeilen begründet (`docs/reviews/phase0-disposition.md:2139-2141`); Batch-Zeile im Store-Klon: 5 von 5 gelistet, 0 verweigert; EVD-0451..0455 nennen je ihren Namensknoten im `run_command`, EVD-0456 ehrlich `result: fail`.
* **HANDBACK bestätigt**: `project_memory/archive/BUG/2026/BUG-0237.yaml:41` nennt `…test_an_empty_origin_excuses_the_step_while_the_root_criteria_measure_it`; `.claude/hooks/test_gates.py::test_every_test_a_hole_names_is_one_that_exists` ist genau darauf (plus H138) rot — reproduziert, 1 failed in 5,87 s. Der Kernel hat keine Tür: `update BUG-0237` → „no active item BUG-0237"; `read_item` liest nur `active/`; `sweep-pointers` meldet die Stelle nicht einmal (36 tote Zeiger, keiner davon dieser).

### Nicht gemessen

Voller `tools/`-Lauf (nur nachgerechnet: 5144+4+14 = 5162), Gate-Suite im Ganzen (nur zwei Knoten + Collection), die volle Gate-Batterie gegen F2 nur im **dev**-Piloten (write_scope selbst in allen dreien), PowerShell-Pfad der neuen Formen, Codex-Artefakte, `test_ladder.py` als ganze Suite, BUG-0069/CI, die übrigen ~200 Löcher, Office-EÜR/Board-Flächen.

### Urteil: **FAIL**

* **F2 blockiert die Runde**: dieselbe Klasse, die diese Runde geschlossen hat, ist mit einem Optionswort wieder offen — Kette läuft in einer Sitzung durch, gegen die vollständige registrierte Hook-Batterie rc 0, echte Shell führt aus. Schließen (fail-closed, wie oben) **oder** als benannte, vom Nutzer abzunehmende Ausnahme in `docs/holes/H219.md` mit genau dieser Messung.
* **F1 blockiert ebenfalls**: die vom Nutzer beschlossene Mechanik (DEC-0113) ist mit einem Kernel-Befehl zu umgehen und erzeugt dabei eine dem Nutzer zugeschriebene Aussage; zusätzlich behauptet der Docstring die Eigenschaft, die fehlt (Hausregel 3).
* **F3 und F4** gehören als benannte Reste in die Löcherliste (Mechanismus, nicht die zwei Schreibweisen: „ein Feed, dessen `period` nicht pro Pflicht eindeutig ist, teilt einen Schlüssel" bzw. „der Satz behauptet Null-Messung, während der Leser Teil-Messung meint").