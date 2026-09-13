# Prüfbericht TSK-0150 (PR-0012, Order 5) — Runde 2 — **PASS (ein benannter Rest: Über-Verweigerung bei Lese-Stufe mit unbekanntem Kommandowort)**

Prüfer: `harness-verifier` (Opus, high), 99 min, +79 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-13 15:24, Uhr gelesen).

## Prüfbericht TSK-0150, Runde 2 (Rework 1) — **PASS**

Neue Momentaufnahme `…\_round-scratch\TSK-0150\verify2` (bytegleich zum Repo: 0 Abweichungen über `team-kits/ tools/ docs/ .claude/`), drei frisch gescaffoldete Piloten `pilot2-dev|office|research` aus `fakehome2`, Rig `…\work\rig2.py` (verweigert Start außerhalb des eigenen Verzeichnisses, explizite newline-Politik). Repo nur gelesen. Ganz gelesen: der Abschnitt „Rework 1" des Protokolls (nicht das ganze Dokument).

### F1 — geschlossen (blockierender Befund aus Runde 1)
`team-kits/kernel/state.py:118/127` (`_REQUEST_PATH_FIELDS`, `_request_path_offences`), Aufrufe in `state.py:891` (capture) und `state.py:1504` (update), eine Tür `state.py:1456`.
Prozess-Messung im dev-Piloten — genau meine Zeilen aus Runde 1:
```
update PR-0001 {"unverified_acceptance_answer":"HANDWRITTEN ja"}   -> rc 1  "… the approval REQUEST path is what writes them …"
capture PR  {… ,"unverified_acceptance_answer":"ja (bei capture erfunden)"} -> rc 1
nur das MISSING-Feld / null / ""                                    -> rc 1 rc 1 rc 1
request-approval acceptance PR-0001 --unverified-answer "…"         -> rc 0, Felder auf dem Ziel (Z. 16/17),
   Karte: „Antwort des Nutzers dazu: …; ohne Nachweis geblieben: acceptance / review / test"
update PR-0001 {"title": …}                                         -> rc 0   (kein Falsch-Positiv)
```
Mutationen: Wächter ganz aus → `::test_the_unverified_answer_has_one_writer_and_no_body_may_carry_it` rot (`Failed`); **jede der beiden Türen einzeln** neutralisiert → derselbe Knoten rot. Zusätzlich geprüft, dass es keine dritte Tür gibt: die vier direkten Item-Schreiber in `state.py` sind `capture`, `_update_item_locked` (beide bewacht), `record_invariant_verification` und `_transition_locked` (nehmen keinen Fremdkörper), und `migrate.py:2961` schreibt über `state.capture`.

### F2 — geschlossen (blockierender Befund aus Runde 1)
`gate_write_scope.py` x3, `_the_command_word_is_unknown` + Quellen-Zuordnung im Regelkörper.
```
alle fünf Zeilen (exec -a / nice -n 5 / sudo -u / command -p / env -i)  dev=2 office=2 research=2
dieselben fünf an der VOLLSTÄNDIGEN registrierten PreToolUse-Bash-Batterie des dev-Piloten
   (10 Gates aus dessen settings.json, timeout 120 s / 1800 s)          -> refused by: write_scope=2
Alltag: nice -n 5 make | sudo -u me ls | env -i bash tools/ci.sh | A=1 ./build.sh |
        exec bash tools/ci.sh | bash < tools/ci.sh | bash $(which ci.sh) | heredoc>notes.md
        | die Evidence-Befehlszeile                                      -> überall rc 0
Quellen-Regel: sudo -u root tee run.sh <<'EOF' … ; bash run.sh          -> 2/2/2
Rückfall-Kontrolle: die neun älteren Formen (heredoc+bash, . / source, tee, echo|tee&&sh,
        bash <run.sh, eval "$(cat run.sh)")                             -> alle 2/2/2
```
Zwei neue Schreibweisen von mir: `env -i sudo -u me ./run.sh` (zwei Präfixe mit Optionen) **rc 2**, `A=1 -x ./run.sh` **rc 2**; `nice -n 5 ./run.sh > run.sh` und `bash run.sh > run.sh` **rc 2** (Umleitung bleibt eigene Quelle). Benannte Reste bestätigt: `timeout 5 ./run.sh` und `xargs -a run.sh true` rc 0 — genau wie `docs/holes/H219.md:56-60` es sagt.
Mutationen (x3): Prädikat `return False` → die fünf Zeilen als **Prozesse** wieder `dev=0 office=0 research=0` und `::test_a_prefix_words_own_option_does_not_hide_the_command_word_in_any_kit` rot; Quellen-Zuordnung durch flache Mengen ersetzt → `env -i bash tools/ci.sh` und `nice -n 5 make` werden rc 2 und derselbe Knoten rot. Danach alle vier mutierten Dateien bytegleich zurückgesetzt.

### F3 — geschlossen
`team-kits/office-team/hooks/_duties.py:515` (`_receivable_period`) und `:600` (`_kept_apart_when_two_share_a_key`).
```
zwei Ledger-Zeilen ohne invoice_no:  key=d027…/period "row 2 (Kunde A)"  und key=3610…/"row 3 (Kunde B)"
duty-done --key d027…               -> recorded; Register danach: Kunde B steht noch
echter Kollisionsfall (zweimal R-7): key=None, key=None, beide gelistet,
   unreadable: "2 duties share the key 9f605e0737441a86 … stay listed and carry no key"
briefing(): beide ohne Schlüssel gedruckt, der keyed-Eintrag mit `key 005e…`, Schlusszeile
   "DEADLINE REGISTER INCOMPLETE: 2 duties share the key …"  (kein „None" im Nutzertext)
```
Mutationen: Periode zurück auf die Rechnungsnummer allein → `::test_two_ledger_rows_without_an_invoice_number_are_two_duties` rot; Kollisionswächter aus → derselbe Knoten rot. Die Ordnungs-Abhängigkeit ist weg: `tools/test_office_duties.py` allein **42 passed**, die drei H113-Knoten isoliert **3 passed**.

### F4 — geschlossen
`team-kits/kernel/approvals.py:2267` (`_the_german_question`).
```
ohne jeden Lauf:  »Für PR-0002 hat niemand geprüft, ob die Arbeit wirklich tut, was sie soll…«
mit test/pass/full: »Für PR-0003 fehlt noch der Nachweis der Art acceptance, review -- diese Prüfung
                     hat niemand gemacht. Ist das so gewollt?«
```
Auch der englische Vorsatz sagt nicht mehr „nothing in this project measured it", sondern „with no passing QA Evidence of kind(s) …". Mutation `whole = True` → `::test_a_goal_with_no_verification_run_is_asked_about_once` rot.

### Neuer Befund (klein, nicht blockierend) — eine Behauptung, die die Messung nicht trägt
`team-kits/dev-team/hooks/gate_write_scope.py` (Docstring `_the_command_word_is_unknown`, „**nothing on an everyday line**, … the rule only refuses a name the SAME LINE also WRITES") und derselbe Satz in `tools/test_hooks.py` („THE EVERYDAY TWINS … because this rule refuses a name only where the SAME LINE also writes it").
```
sudo -u me cat tools/ci.sh ; bash tools/ci.sh   -> rc 2 (dev/office/research)
   Text: "this line WRITES tools/ci.sh and RUNS it in the same call"   <- die Zeile schreibt nichts
nice -n 19 wc -l tools/ci.sh ; bash tools/ci.sh -> rc 2 ;  env -i grep -n x tools/ci.sh ; bash … -> rc 2
```
**Eigener Irrtum, korrigiert:** ich hielt das zuerst für eine Regression der Nacharbeit — gemessen gegen die alten Piloten (Stempel -5) ist dieselbe Zeile ebenfalls rc 2, die Klasse ist also **vorbestehend** und nicht vom Fix erzeugt. Was neu ist, ist der Satz, der sie ausschließt. Mechanismus (nicht die zwei Schreibweisen): *die Operanden einer Stufe mit unbekanntem Kommandowort gelten als GESCHRIEBEN, auch wenn die Stufe ein reiner Leser ist; startet eine spätere Stufe dieselbe Datei, verweigert die Regel mit einem Satz, der faktisch falsch ist.* Minimal: entweder den Kostensatz in beiden Docstrings auf das beschränken, was gilt (fail-closed, Über-Verweigerung möglich), oder die unbekannte Stufe nur als RUN und nicht als WRITTEN lesen, wenn ihre übrigen Wörter sämtlich als lesend eingestuft sind. Gehört als benannter Rest in `docs/holes/H219.md`, nicht in eine Zusage.
Randnotiz derselben Klasse: `H219.md` nennt „sechs Verweigerungen, fünf Alltagszeilen" — stimmt heute exakt mit den Zeilen des Tests, ist aber eine Zahl über etwas, das wächst (SR-0008/Hausregel 4).

### Weitere negative Befunde — gemessen
* Stempel **2026.09.13-6** in allen drei Kits, `bump_kit_version.py --check` „unchanged" x3 (Hash deckt den Baum); `ruff` sauber; `tools/validate.py` grün; Kernel-`validate` rc 0; `generate-index` in der Store-Kopie = Store bis auf `generated_at`; Spiegel bytegleich (`gate_write_scope.py` 496bd0d95b8b, `_routine.py` cff86961abc6 in drei Kits); Decken unverändert 61219/66492/63075.
* Batch-Zeile im Store-Klon: rc 0, 5 von 5, 0 verweigert, und die Karte nennt **EVD-0457/0459/0451/0454/0458**; die drei neuen EVDs nennen je ihren Namensknoten im `run_command`.
* Nachgerechnet und exakt getroffen: `test_approvals_dispatch` **236 passed / 97 s**, `test_state` **67 / 9 s**, `test_kernel` **136 / 28 s**, `test_office_duties + test_routine_feed` **74 / 8 s**, die Schreib-und-Start-/Spiegel-Auswahl von `test_hooks` **16 / 26 s**, Gate-Suite sammelt **555**, ihre fünf Knoten zum Präfix-Lauf der Kits grün.
* Zusätzlich von mir gefahren, weil `gate_write_scope.py` die am stärksten geänderte Datei ist: `tools/test_hooks.py -k "gate1 or write or refuse"` → **148 passed / 5:23** (keine Nebenwirkung der Regel-Umschreibung in den übrigen Schreib-Prüfungen).
* **DEC-0050-Urteil für die Nacharbeit:** verändert wurden `state.py`, `approvals.py`, `_duties.py`, `gate_write_scope.py` x3 (alles Verhalten) plus Dokumente. Ihre Lesesuiten sind gefahren und stimmen; die Risiko-Datei habe ich über die 148er-Auswahl zusätzlich abgedeckt. Ein zweiter 2:14-Lauf ist dadurch nicht gerechtfertigt — der Verzicht ist regelkonform.

### Nicht gemessen
`tools/test_hooks.py` **im Ganzen** (gestartet, lief bei Berichtsschluss noch, Ausgabedatei 0 Bytes → als unmessbar markiert, nicht als grün); der volle `tools/`-Lauf; die Gate-Suite im Ganzen (nur Collection + fünf Knoten + der HANDBACK-Knoten aus Runde 1); PowerShell-Pfad der neuen Formen; `bash -c '<payload>'` als eigene Klasse (rc 0, gemessen, aber vorbestehend und von H214s Interpreter-/Mehrzeilen-Rest gedeckt — ich nenne es hier, ohne es dieser Runde zuzuschreiben); Codex-Artefakte; BUG-0069/CI.

### Urteil: **PASS**
F1 und F2 sind als Mechanismus geschlossen und jeweils mit einer eigenen, von mir selbst gefahrenen Mutation rot belegt — F2 zusätzlich als Prozess gegen die vollständige Hook-Batterie; F3 und F4 sind über die benannten Reste hinaus gebaut statt nur notiert. Der eine neue Befund ist eine **Satz**-Korrektur plus ein benannter Rest (vorbestehende Über-Verweigerung) und blockiert die Runde nicht; er gehört in `docs/holes/H219.md` und in die beiden Docstrings, bevor das Paket als „Alltag kostet nichts" gelesen wird. Offen für den Lead bleibt der HANDBACK aus Runde 1 (`project_memory/archive/BUG/2026/BUG-0237.yaml:41`, kein Kernel-Weg dorthin) und BUG-0297/H213 (Nutzer-Patch).