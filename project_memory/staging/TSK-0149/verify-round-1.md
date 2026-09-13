# Prüfbericht TSK-0149 (PR-0012, Order 4, Zielrunde) — Runde 1 — **FAIL (F1 F4 blockierend; F2 Batch-Zeile; F3 lead-lines; F5/F6 Reste)**

Prüfer: `harness-verifier` (Opus, high), 45 min, 238 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-13 07:37, Uhr gelesen). F6 (Rundenlog-Zuordnung) vom Lead korrigiert; F2-Rest als Loch aufgenommen (DEC-0102 (2): zweite Weitung = neu einreihen).

# Prüfbericht TSK-0149 (PR-0012 „Bug-Null", Auftrag 4) — Urteil: **FAIL**

Arbeitskopie: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0149/verify/tree` (robocopy ohne `.git`), drei eigene Piloten (`pilot-dev-team`, `pilot-office-team`, `pilot-research-team`) über `scaffold_team.sh` mit eigenem `HOME`. Rig: `.../verify/rig.py` — verweigert außerhalb des eigenen Verzeichnisses (gemessen: `rig refuses: cwd /c/Offline Repos/AgentAndSkills is not …/verify`), schreibt ausschließlich binär. Kopie nach allen Mutationen wieder byte-identisch zum Repo (`m_treediff.py`: 3072/3072 Dateien, 0 verschieden; am Ende zwei Abweichungen nur in meiner Kopie, weil ich dort `generate-index` fuhr). Das Repo wurde nicht beschrieben.

---

## Befunde

### F1 — BLOCKIEREND. Die Lizenzzahl 5→3 ruht auf einem Leser, den genau diese Runde blind gemacht hat

`docs/reviews/phase0-disposition.md:747` · `tools/test_shortening_net.py:1309` (`_events_reaching`) · `team-kits/*/hooks/gate_dispatch.py:400,405`

DEC-0107 registriert `gate_dispatch` neu auf `PreToolUse('Bash|PowerShell')`. Daraus leitet der Zähler ab, dass `handle_pre_tool_use` und `_refuse_untrusted_bundle` auf Codex erreichbar wurden, und das Dokument sagt jetzt „**3 der 36** wirksamen Lizenzen ruhen auf einem Mechanismus, den Codex nicht starten kann".

Gemessen mit einer Marker-Datei **aus der Funktion heraus**, echte Hook-Prozesse gegen meinen dev-Piloten (`m_reach.py`, nur die Pilotkopie instrumentiert, danach Hash 6a5bc651… wiederhergestellt):

```
rc=0  _refuse_untrusted_bundle entered: False | Bash payload on the NEW registration
rc=0  _refuse_untrusted_bundle entered: False | Bash payload that IS a kernel evidence line
rc=2  _refuse_untrusted_bundle entered: True  | Agent payload on the OLD registration
```

Mechanismus: `_events_reaching` verengt auf das **Ereignis** (`PreToolUse`), nicht auf die **Werkzeugklasse**, die der Handler danach verlangt — `gate_dispatch.py:405` `if data.get("tool_name") not in SPAWN_TOOLS: sys.exit(0)`. `Bash|PowerShell` übersetzt auf Codex, `CODEX_UNSUPPORTED_TOOLS = ('Agent','Task','AskUserQuestion')` (`team-kits/gen_provider_artifacts.py:83`) — also läuft das Symbol dort nie.

Gegenprobe, dass der Zähler wirklich an der Registrierung hängt (`m_licence.py`, Registrierung in allen drei `settings/settings.json` entfernt, danach byte-identisch wiederhergestellt):

```
registration removed -> 1 failed
  AssertionError: the document does not state that 5 licences rest on a mechanism Codex cannot start (4, 15, 41, 54, 56)
restored -> 1 passed
```

Der Docstring des Knotens sagt selbst „THE SUBJECT IS THE CITED SYMBOL, not the file that holds it" — die Verengung hört eine Ebene zu früh auf. Zeile 54 (`gate_dispatch._refuse_untrusted_bundle`) ist nachweislich weiter Codex-blind; Zeile 4 (`handle_pre_tool_use`) läuft zwar, trägt die Regel „Kein Spawn ohne freigegebenen Task" aber hinter derselben Wache. Das ausgelieferte Reviewdokument untertreibt damit die Codex-Lücke — die beruhigende Richtung, die Hausregel 3 genauso verbietet wie die alarmierende.

**Minimalfix:** `_events_reaching` zusätzlich an der `tool_name`-Wache des Handlers verengen (oder die Handler-Karte als Paar Ereignis/Werkzeugklasse führen), dann Zahl und Begründungsabsatz in `phase0-disposition.md` neu ableiten. **Blockiert die Runde.**

### F2 — Die Ein-Aufruf-Klasse von H214 ist in drei Mechanismen offen und nirgends aufgeschrieben

`team-kits/{dev,office,research}-team/hooks/gate_write_scope.py:1610` (Absatz „WHAT IS LEFT OPEN AND NAMED RATHER THAN CLAIMED AWAY")

Echte Hook-Prozesse, alle drei Kits, identische rc (`m_e2.py`), und die echte Shell als Schiedsrichter (`m_realshell.sh`, Marker `project_memory/b1h.yaml`):

| Zeile | gate_write_scope | echte Shell |
|---|---|---|
| `cat <<'EOF' > run.sh … ; bash run.sh` (Baseline) | **rc 2** | EXECUTED |
| `printf 'x' > run.sh ; A=1 ./run.sh` | rc 0 | EXECUTED |
| `printf 'x' > run.sh ; exec ./run.sh` | rc 0 | EXECUTED |
| `printf 'x' > run.sh ; command ./run.sh` | rc 0 | EXECUTED |
| `cat <<'EOF' > run.sh … ; eval "$(cat run.sh)"` | rc 0 | EXECUTED |
| `printf 'x' > run.sh ; bash < run.sh` | rc 0 | EXECUTED |

**Keine Regression von M2:** mit dem Vor-Zustand des Kommandowort-Lesers (an der *Pilotkopie* mutiert, `m_prefix2.py`) sind dieselben fünf ebenfalls rc 0. Der Defekt ist der Docstring: er nennt als Rest nur die Mehrzeilenform und den Interpreter — eine Aufzählung, die drei Mechanismen unterschlägt (Runner hinter einem Präfixwort; Datei über eine Umleitung in den Interpreter; Substitutions-`eval`).

Folge für den Lead: `BUG-0298` steht in Batch-Zeile B auf **ready**; schließt es, macht `migrate-holes --reindex` `H214` VERIFIED, während der Eintragstext genau die Klasse beschreibt, die offen bleibt. `EVD-0444` selbst behauptet nichts Falsches — die Lücke ist die Löcherliste.

**Gehört als benannter Rest in die Löcherliste, bevor BUG-0298 gefragt wird** — blockiert diese eine Batch-Zeile, nicht die Runde.

### F3 — Die Rollup-Buchhaltung in `lead-lines.md` stimmt nicht mit dem gelieferten Store überein

`project_memory/staging/TSK-0149/lead-lines.md:104` und `:108`

Gemessen gegen meine Kopie des Stores (`report.stock_rollup`):

```
n: 14
{'item': 'BUG-0242', 'evidence': ['EVD-0448'], 'unresolved': [], 'status': 'TRIAGED', ...}
active BUGs: 27   NOT in rollup: 13
```

Die Datei sagt „13 rows" und listet 13 Ids **ohne** BUG-0242; sie führt BUG-0242 stattdessen unter „**fourteen** active `BUG` items are NOT in the rollup" — gemessen sind es dreizehn. Ursache: `EVD-0448` wurde `created: '2026-09-13T06:46:50'` geschrieben, `lead-lines.md` um 06:47 — das Rollup wurde vor dem eigenen letzten Beweis gelesen.

Das ist genau das Blatt, aus dem der Lead ableitet, was schließen darf: es zeigt BUG-0242 mit bestandener Evidenz und leerem `unresolved`, also abschlussreif, während derselbe Text sagt, es dürfe nicht transitioniert werden. **Blockiert die AC-5-Lieferung** (Fix: Abschnitt 5 nach EVD-0448 neu lesen und den Widerspruch ausschreiben).

### F4 — Der Docstring des write-and-run-Knotens zählt und zeigt falsch

`tools/test_hooks.py:19964` „THIRTEEN MEASUREMENTS, eight refusals and five everyday lines" — gemessen fährt der Knoten 8 Verweigerungen und **6** Alltagszeilen (die Evidenzzeile wurde in dieser Runde angehängt) = 14.
`tools/test_hooks.py:19994` „The last two are the ones a … reading can break: a copy … und ein `tee` …" — nach dem Anhängen sind „die letzten zwei" `tee` und die Evidenzzeile. Hausregel 3 (Behauptung ≠ Code) und 4 (Zahl in einem Kommentar). **FAIL-Grund, Fix ist zwei Wörter.**

### F5 — Kleinere Zahlen in Kommentaren (vorbestehend, in dieser Runde weiter gealtert)

* `team-kits/kernel/state.py:2010` „the two EVD entries below" — es sind jetzt vier EVD-Paare (kind, result, run_scope und das in dieser Runde abgeleitete `fail_class`). War schon bei 5ecf62a stale.
* `tools/test_hooks.py:2670` „the three kits register 24 / 21 / 22 different ones" — gemessen aus den Registrierungen der drei Piloten (verschiedene Hook-Skripte in `settings.json`, ohne `_gate.py`): **25 / 27 / 22**.
* `tools/test_hooks.py:19542` „every one of the 92 shipped kit entries states a `timeout`" — heute korrekt (32+31+29 = 92, davon 0 ohne `timeout`), aber eine wachsende Zahl in Prosa, während `test_every_shipped_hook_of_this_kit_reaches_the_deadline_that_arms_it` die Eigenschaft hält.

### F6 — Aktenfehler im Rundenlog

`project_memory/staging/generation-6-streams.md` (Zeile mit „TSK-0149 goal round done") nennt als eine der sechs echten Roten aus Lauf 1 „the date-dependent Mahnung test needed `--today`". `fullrun.log` listet genau sieben FAILED, keiner aus `tools/test_office_package.py`; die Datei wurde 03:13:14 zuletzt geschrieben — 16 s **vor** dem Start von Lauf 1 (03:13:30). Die Zuordnung ist falsch.

---

## Negative Befunde — GEMESSEN

* **Stempel:** `bump_kit_version.py` in der Kopie → `unchanged (2026.09.13-2)` x3; drei VERSION-Dateien mit ihren Inhalts-Hashes passen zum Baum.
* **known_holes:** `gen_known_holes.py --check` → „up to date (3 capabilities)"; sha256 `f45e2488…` / `f5bbde32…` wie protokolliert; `git diff HEAD` leer → **Delta null**.
* **Zählungen:** `fullrun2.log` „1 failed, 5139 passed, 14 skipped in 4574.22s"; `gates.log` „2 failed, 553 passed in 2128.34s". Marker 04:42:44→05:59:08 und 05:59:39→06:35:17. Keine Inhaltsänderung an `tools/`, `team-kits/`, `docs/`, `.claude/` nach Laufbeginn (einzige neuere mtime: `_audit.py`, Inhalt identisch zu den beiden Spiegeln und zu HEAD).
* **S4-Patch in meiner Kopie angewandt:** `test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires` **1 passed**, `test_gate3_prints_a_remedy_that_runs_as_printed` **1 passed**; nach Rücknahme wieder 1 failed. Datei-Hash wiederhergestellt.
* **H138-Rot vorbestehend:** `git show 5ecf62a:tools/test_design_conformance.py` enthält den Namen 0×, `5ecf62a:…/BUG-0221.yaml` trägt ihn bereits; beide Dateien in dieser Runde unverändert. Der Ersatzname aus `lead-lines.md` §4 löst genau einmal auf.
* **Naht (a):** Kernel-Prädikat `fail_class_role_refusal` ausgeschaltet → `test_the_fail_classification_is_refused_from_every_writer_but_the_verifying_one` **1 failed**, mit `assert 0 == 2` am echten `gate_dispatch.py`-Prozess. Gekoppelt. Die Sitzungsinstanz wird auch unter der Mutation als Prozess verweigert.
* **Naht (e1), Wertposition ehrlich** (echte Prozesse, dev-Pilot): `"$a$b" mechanical` rc 2 („carries a word the shell builds"); `--run-command "$(cat cmd.txt)"` rc 0; `--related "$ID"` rc 0. Meine Angriffe auf die Optionsposition: quotierte Expansion nach `--summary=x` rc 2, nach `--help` rc 2, als zweite quotierte Expansion rc 2, nach mehrdeutigem Präfix `--r` rc 2, `--summary="$X"` rc 0. Kein Flag des `evidence`-Subparsers ist echtes Präfix einer wertnehmenden Option (Prüfung über `build_parser()`), also heute keine Präfix-Falle.
* **Naht (e2):** neun write-and-run-Formen rc 2 in allen drei Kits (inkl. `./run.sh` als Kommandowort und `.\run.sh`); `bash $(which ci.sh)` rc 0; die Evidenzzeile rc 0 **nach** und rc 2 **vor** der Verengung (an der Pilotkopie gemessen); `cat <<'EOF' > run.sh … ; python run.sh` rc 0 und im Docstring als H11-Rest benannt; die Rot-zuerst-Behauptung real: Bedingung entfernt → `test_a_line_that_writes_a_script_and_runs_it_is_refused_in_every_kit` **3 failed**, wiederhergestellt **3 passed**.
* **(b)/(c)/(d)/(f):** Kommandoflächen-Knoten grün, `README.md:335` nennt `withdraw-request`; `docs/office/invoice-app-docking-point.md:146` beschreibt `booking.rows` / eine Zeile je Satz; `ladder.yaml` validiert über den Kernel, `harness-implementer.md:14-15` zeigt auf `classes.build`; `H155`-Zeiger nur noch historisch, `H218`/`BUG-0303` an Docstring-Zeile 1, letztem Absatz, Assertion-Text und `dispatch._carries_its_own_criteria`.
* **DEC-0105-Wirkung selbst gemessen:** Konfigzeile `model_tiers: ladder.yaml` in der Kopie eingesetzt → `ladder_declaration.source` = „the tier file project_config.yaml names (ladder.yaml)", Rollen planning/build/qa; danach verweigert `fail_class_role_refusal` Lead und Implementer und lässt den Verifier durch. Konfig wieder hergestellt.
* **(g) R1–R4, eigene Mutationen:** „judge and write in one pass" → 1 failed; `("EVD", fail_class)` aus dem Vokabular → 1 failed; Record hinter den Stempel → 1 failed mit „the refused stamp took the Evidence with it: []"; `mint` buchstabiert seine Enden selbst → 1 failed.
* **Zwei der Lauf-1-Reparaturen mutiert:** Timeout-Vertrag (`window is None` entschärft) → `test_two_silent_entries_still_leave_the_gate_deciding` 1 failed; Lizenzzähler siehe F1.
* **H215:** keine Zeilennummern-Zeiger mehr in `docs/holes/H21x.md`; alle vier genannten Funktionsnamen lösen auf.
* **Batch-Zeilen read-only nachgebaut** (`approvals.batch_walk_blockers`, `batch_closing_types('verification') == ['BUG']`): A, A+Naht, B, C und BUG-0253 → **0 Verweigerungen**; `BUG-0296/0297/0303` werden vom Kernel verweigert („has no passing 'test' Evidence naming it"). Für alle elf Ids ist das im Blatt genannte EVD wirklich das jüngste, das sie nennt, und `kind: test, result: pass`.
* **Laufzeit** (Fenster aus der `settings.json` der Piloten: 120 s): gewöhnliche Shell-Zeile median 0,142 s (0,16 % des Fensters), Kernel-Eintrittspunkt ohne Expansion 0,233 s, teurer Pfad mit quotierter Expansion (Parser wird gefragt) 0,400 s / max 0,647 s, verweigernder Pfad 0,516 s. Kein Budgetrisiko durch die neue Registrierung.
* **Hygiene:** ruff über `tools team-kits user` grün; `tools/validate.py` grün; `generate-index` → nur `generated_at` weicht ab, also Index = Store; alle 31 mehrfach ausgelieferten Hook-Dateien byte-identisch außer `format_on_write.py` und `session_status.py`, beide mit Grund in `KIT_SPECIFIC_HOOKS`; `tools/test_context_budget.py` 41 passed / 1 skipped, Decken 61088/66479/62920.
* **QA-Rollentexte (e3):** dev/office/research beschreiben die Regel als „UNQUOTED anywhere on the line, or quoted but not standing as the VALUE of an option" — deckt sich mit dem gemessenen Verhalten.

## Nicht gemessen

* Der Volllauf und die Gate-Suite wurden **nicht** wiederholt (DEC-0050, nachgerechnet statt nachgefahren).
* Die 553 Gate-Suite-Knoten einzeln, außer den beiden Roten und dem S4-Knoten.
* `EVD-0443/0445/0446/0447/0448` habe ich nicht durch Nachfahren ihrer `run_command`-Zeilen bestätigt (nur Existenz, Bezug, kind/result und die Zuordnung im Rollup).
* Das Office-EUeR-Verhalten hinter der Docking-Point-Prosa (nur die Textseite geprüft).
* H215’ „vier Startstellen, null vergesslich" habe ich nicht selbst nachgesondet — nur die vier Funktionsnamen aufgelöst.
* Die Journal-Notizen der beiden Ratschen (`record_lead_package_sizes.py --note`) habe ich nicht Zeile für Zeile gegen die +44 B geprüft.
* Ob F5s „24 / 21 / 22" nach der Zählmethode des Autors falsch ist — meine Methode (verschiedene Hook-Skripte in der Registrierung) ist genannt, die Zahl gehört vom Umsetzer neu abgeleitet.

## Eigene Fehlgriffe

* `m_prefix.py` mutierte den **Baum**, während der Prozess die **Pilotkopie** fuhr — mein erstes „BEFORE" war eine zweite AFTER-Messung. Korrigiert in `m_prefix2.py`; erst dort wurde sichtbar, dass die Evidenzzeile vorher wirklich rc 2 war.
* A7 (`--summary x"$OPT"`) und A10 in meiner e1-Sonde waren Fehlannahmen: dort steht die Expansion tatsächlich in Wertposition, rc 0 ist richtig.
* `node run.js` rc 2 war die Produktionscode-Regel gegen die Sitzungsinstanz, nicht die write-and-run-Regel.
* Die Spiegel-Hashes des Protokolls (`a43bebd1…`, `e95fc831…`) hielt ich kurz für falsch — sie sind **md5** und stimmen; sha256 ist `2f1ffbab…` / `6a5bc651…`, x3 identisch.

## Urteil

**FAIL.** Blockierend für die Runde: **F1** — eine Schutzaussage in einem ausgelieferten Dokument, die genau der Fix dieser Runde falsch gemacht hat, gemessen am echten Prozess. **F4** ist ein FAIL-Grund nach Hausregel 3, Fix zwei Wörter. **F2** blockiert die Batch-Zeile `BUG-0298` (Löcherliste vor dem Schließen), **F3** die AC-5-Lieferung `lead-lines.md`. F5/F6 gehören als benannte Reste in den Bericht, nicht in den Weg.

Dateien zum Nachlesen: `C:\Offline Repos\AgentAndSkills\docs\reviews\phase0-disposition.md`, `C:\Offline Repos\AgentAndSkills\tools\test_shortening_net.py`, `C:\Offline Repos\AgentAndSkills\team-kits\dev-team\hooks\gate_dispatch.py`, `C:\Offline Repos\AgentAndSkills\team-kits\dev-team\hooks\gate_write_scope.py`, `C:\Offline Repos\AgentAndSkills\tools\test_hooks.py`, `C:\Offline Repos\AgentAndSkills\project_memory\staging\TSK-0149\lead-lines.md`. Meine Sonden: `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0149\verify\` (`rig.py`, `m_reach.py`, `m_licence.py`, `m_e1.py`, `m_e2.py`, `m_prefix2.py`, `m_realshell.sh`, `m_r.py`, `m_r3.py`, `m_runtime.py`, `m_batch.py`, `m_treediff.py`).